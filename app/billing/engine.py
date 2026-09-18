"""Motor de rateio -- o coracao auditavel do EV ChargeOps.

Implementa, literalmente, a formula da Opcao A:

    fatura_u = sum(round2(kwh_s x tarifa_s) for s in S_u) + round2(C_disp / N_aderentes)

Tres propriedades sao mantidas de proposito, porque sao o que a plataforma
promete em assembleia:

1. **Cada numero e reproduzivel a partir de linhas.** O total da fatura e a soma
   das linhas persistidas, nunca um calculo paralelo. Se o sindico somar o
   extrato na mao, bate.
2. **Arredondamento por linha, half-up.** Nao no total. E a regra da Opcao A.
3. **A tarifa vem do snapshot da sessao**, nao da vigencia atual. Reajuste
   posterior -- ou ate correcao retroativa da vigencia -- nao reescreve mes
   fechado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from billing.audit import held_session_ids
from billing.competence import Competence
from billing.money import round2
from core.models import (
    AnomalyFlag,
    ChargingSession,
    Condominium,
    Invoice,
    InvoiceLine,
    ProgramEnrollment,
    TariffPeriod,
    TariffReconciliation,
    Unit,
)

BILLABLE_STATUSES = (
    ChargingSession.Status.COMPLETED,
    ChargingSession.Status.INTERRUPTED,
    ChargingSession.Status.FAULT,
)


class BillingError(RuntimeError):
    pass


@dataclass
class EnrollmentShare:
    """A participacao de uma unidade na taxa de disponibilidade do mes."""

    unit: Unit
    days_enrolled: int
    days_in_month: int

    @property
    def is_full_month(self) -> bool:
        return self.days_enrolled >= self.days_in_month


@dataclass
class ClosingReport:
    """O que o fechamento produziu -- material do relatorio de assembleia."""

    competence: str
    invoices: list = field(default_factory=list)
    n_enrolled: int = 0
    availability_fee_total: Decimal = Decimal("0.00")
    availability_collected: Decimal = Decimal("0.00")
    energy_total: Decimal = Decimal("0.00")
    kwh_total: Decimal = Decimal("0.000")
    adjustments_total: Decimal = Decimal("0.00")
    flagged_lines: int = 0

    @property
    def residual(self) -> Decimal:
        """Sobra ou falta do rateio da parcela fixa.

        A Opcao A decidiu que este residuo fica com o caixa do condominio e e
        *declarado* no relatorio mensal -- e por isso que ele e um campo do
        relatorio, e nao um detalhe escondido no motor.
        """
        return round2(self.availability_collected - self.availability_fee_total)

    @property
    def total_billed(self) -> Decimal:
        """A soma das faturas. Inclui os ajustes de reconciliacao: sem eles o
        relatorio de julho divergia das proprias faturas em R$ 37,54."""
        return round2(self.energy_total + self.availability_collected + self.adjustments_total)


def enrolled_units(condominium: Condominium, competence: Competence) -> list[EnrollmentShare]:
    """Unidades aderentes na competencia, com os dias de adesao.

    `N_aderentes` e funcao do tempo (decisao 8): reconstruido a partir das datas
    de `program_enrollment`, e nao de um booleano que nao tem memoria.
    """
    first, last = competence.first_day, competence.last_day
    enrollments = (
        ProgramEnrollment.objects.filter(unit__condominium=condominium)
        .filter(start_date__lte=last)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=first))
        .select_related("unit")
        .order_by("unit__label")
    )

    by_unit: dict[int, EnrollmentShare] = {}
    for e in enrollments:
        overlap_start = max(e.start_date, first)
        overlap_end = min(e.end_date, last) if e.end_date else last
        days = (overlap_end - overlap_start).days + 1
        if days <= 0:
            continue
        share = by_unit.get(e.unit_id)
        if share:
            share.days_enrolled = min(share.days_enrolled + days, competence.days_in_month)
        else:
            by_unit[e.unit_id] = EnrollmentShare(
                unit=e.unit, days_enrolled=days, days_in_month=competence.days_in_month
            )
    return sorted(by_unit.values(), key=lambda s: s.unit.label)


def availability_share(fee_total: Decimal, n_enrolled: int, share: EnrollmentShare) -> Decimal:
    """A cota da unidade na parcela fixa.

    Mes inteiro: `round2(C_disp / N_aderentes)` -- a formula da Opcao A, sem
    desvio. Adesao parcial: pro rata por dias, o "parametro do condominio" que a
    Opcao A previu para entrada/saida no meio do mes.
    """
    if n_enrolled <= 0:
        return Decimal("0.00")
    full = Decimal(fee_total) / Decimal(n_enrolled)
    if share.is_full_month:
        return round2(full)
    return round2(full * Decimal(share.days_enrolled) / Decimal(share.days_in_month))


def billable_sessions(condominium: Condominium, competence: Competence):
    """Sessoes encerradas cuja competencia e `competence`.

    O filtro usa a janela UTC do mes civil (indexavel) em vez de extrair mes de
    `session_start` no banco -- alem de mais rapido, e o unico jeito de acertar
    a virada de mes sem depender do fuso da sessao do Postgres.
    """
    start_utc, end_utc = competence.utc_window()
    billed_elsewhere = InvoiceLine.objects.filter(session=OuterRef("pk")).exclude(
        invoice__competence=str(competence)
    )
    return (
        ChargingSession.objects.filter(
            charge_point__condominium=condominium,
            session_start__gte=start_utc,
            session_start__lt=end_utc,
            status__in=BILLABLE_STATUSES,
            credential__isnull=False,
            applied_tariff_kwh__isnull=False,
        )
        # Ja cobrada como sessao tardia numa competencia posterior: reprocessar
        # o mes de origem nao pode cobra-la de novo.
        .exclude(Exists(billed_elsewhere))
        .select_related("credential__user__unit", "charge_point")
        .order_by("session_start", "id")
    )


def late_sessions(condominium: Condominium, competence: Competence):
    """Sessoes de meses JA FECHADOS que so agora se tornaram cobraveis.

    Dois caminhos levam ate aqui, e os dois sao rotina numa operacao real: a
    sessao orfa que o gestor vinculou a um morador depois do fechamento, e a
    sessao que a fonte entregou com atraso (o pull de reconciliacao que
    recupera o que o webhook perdeu).

    A regra e a mesma da reconciliacao de tarifa: **fatura fechada nao se
    reescreve; o que chega depois entra na proxima**, como linha identificada.
    So vale para competencia que o motor ja fechou -- mes nunca fechado nao tem
    sessao "atrasada", tem sessao a espera do proprio fechamento.
    """
    start_utc, _ = competence.utc_window()
    fechadas = set(
        Invoice.objects.filter(condominium=condominium)
        .exclude(competence=str(competence))
        .values_list("competence", flat=True)
    )
    candidatas = (
        ChargingSession.objects.filter(
            charge_point__condominium=condominium,
            session_start__lt=start_utc,
            status__in=BILLABLE_STATUSES,
            credential__isnull=False,
            applied_tariff_kwh__isnull=False,
        )
        .exclude(Exists(
            InvoiceLine.objects.filter(session=OuterRef("pk")).exclude(
                invoice__competence=str(competence)
            )
        ))
        .select_related("credential__user__unit", "charge_point")
        .order_by("session_start", "id")
    )
    return [s for s in candidatas if str(Competence.of(s.session_start)) in fechadas]


#: Vocabulario OCPP traduzido para quem le a fatura.
#:
#: O codigo cru continua em `ChargingSession.stop_reason` -- e o registro
#: tecnico, e nao se perde. Mas "PowerLoss" na fatura de um morador de 70 anos
#: nao informa nada: informa que o sistema nao foi escrito para ele.
RAZAO_LEGIVEL = {
    "PowerLoss": "queda de energia",
    "EVDisconnected": "o cabo foi retirado do carro",
    "EmergencyStop": "botão de emergência acionado",
    "Local": "encerrada no próprio carregador",
    "Remote": "encerrada pelo aplicativo",
    "PowerPathError": "falha elétrica no carregador",
}


def razao_legivel(reason: str | None) -> str:
    if not reason:
        return "motivo não informado"
    return RAZAO_LEGIVEL.get(reason, reason)


def _session_description(session: ChargingSession, *, com_nome: bool = True) -> str:
    """Texto do extrato. E o que o morador le -- precisa dizer *quando*, *quem*
    e, se algo saiu do normal, *o que*.

    `com_nome=False` serve a tela do proprio morador, onde repetir o nome dele
    em cada linha e ruido: ele ja sabe quem e.
    """
    from billing.competence import condo_tz

    local = session.session_start.astimezone(condo_tz())
    base = f"Recarga de {local.strftime('%d/%m')} às {local.strftime('%H:%M')}"
    if com_nome:
        quem = session.credential.user.name if session.credential else "credencial não resolvida"
        base += f" — {quem}"
    if session.status == ChargingSession.Status.INTERRUPTED:
        base += f" — sessão interrompida: {razao_legivel(session.stop_reason)}"
    elif session.status == ChargingSession.Status.FAULT:
        base += f" — falha no carregador: {razao_legivel(session.stop_reason)}"
    if session.final_reading_lost:
        base += " — a leitura final não chegou, cobrada a última leitura confirmada"
    return base


def _needs_audit(session: ChargingSession, held_ids: set[int]) -> bool:
    """A regra mora em `billing.audit`, compartilhada com o portal."""
    return session.id in held_ids


@transaction.atomic
def close_competence(
    condominium: Condominium,
    competence: Competence | str,
    *,
    due_date: date | None = None,
    force: bool = False,
) -> ClosingReport:
    """Fecha a competencia: gera uma fatura por unidade aderente ou consumidora.

    Idempotente por construcao: faturas ainda abertas (`draft`/`under_review`)
    sao recalculadas do zero; faturas ja fechadas so cedem com `force=True`.
    Reprocessar um mes nunca duplica linha.
    """
    comp = competence if isinstance(competence, Competence) else Competence.parse(competence)
    comp_str = str(comp)

    existing = Invoice.objects.filter(condominium=condominium, competence=comp_str)
    # Travada e toda fatura que ja saiu da mao do motor -- inclusive em atraso.
    locked = existing.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.UNDER_REVIEW])
    if locked.exists() and not force:
        raise BillingError(
            f"competencia {comp_str} ja possui {locked.count()} fatura(s) fechada(s); "
            "use force=True para reprocessar"
        )
    InvoiceLine.objects.filter(invoice__in=existing).delete()
    existing.delete()

    shares = enrolled_units(condominium, comp)
    n_enrolled = len(shares)
    tariff = (
        TariffPeriod.objects.filter(condominium=condominium, valid_from__lte=comp.last_day)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=comp.first_day))
        .order_by("-valid_from")
        .first()
    )
    fee_total = tariff.availability_fee_month if tariff else Decimal("0.00")

    report = ClosingReport(
        competence=comp_str, n_enrolled=n_enrolled, availability_fee_total=round2(fee_total)
    )

    tardias = late_sessions(condominium, comp)
    tardias_ids = {s.id for s in tardias}
    sessions = tardias + list(billable_sessions(condominium, comp))
    flagged_session_ids = held_session_ids(s.id for s in sessions)

    sessions_by_unit: dict[int, list[ChargingSession]] = {}
    visitor_sessions: dict[int, list[ChargingSession]] = {}
    for s in sessions:
        user = s.credential.user
        if user.unit_id:
            sessions_by_unit.setdefault(user.unit_id, []).append(s)
        else:
            # Visitante: fatura avulsa, fora do rateio (art. 554 da REN 1.000).
            visitor_sessions.setdefault(user.id, []).append(s)

    units_by_id = {sh.unit.id: sh for sh in shares}
    reconciliations = list(
        TariffReconciliation.objects.filter(
            condominium=condominium, settled_in_competence=comp_str
        ).order_by("competence")
    )
    # Quem consumiu na competencia apurada deve (ou recebe) o ajuste, ainda que
    # tenha saido do programa e nao carregue em M. Sem isto, a unidade que
    # encerrou a adesao no ultimo dia do mes nunca acertava a diferenca.
    owes_adjustment = set(
        InvoiceLine.objects.filter(
            kind=InvoiceLine.Kind.SESSION,
            invoice__condominium=condominium,
            invoice__competence__in=[r.competence for r in reconciliations],
            invoice__unit__isnull=False,
        ).values_list("invoice__unit_id", flat=True)
    )
    all_unit_ids = set(units_by_id) | set(sessions_by_unit) | owes_adjustment

    issued = timezone.now()
    for unit_id in sorted(all_unit_ids):
        share = units_by_id.get(unit_id)
        unit = share.unit if share else Unit.objects.get(pk=unit_id)
        invoice = Invoice.objects.create(
            condominium=condominium,
            unit=unit,
            competence=comp_str,
            status=Invoice.Status.DRAFT,
            issued_at=issued,
            due_date=due_date,
        )
        lines: list[InvoiceLine] = []
        has_audit = False

        for s in sessions_by_unit.get(unit_id, []):
            flagged = _needs_audit(s, flagged_session_ids)
            has_audit = has_audit or flagged
            lines.append(
                InvoiceLine(
                    invoice=invoice,
                    kind=InvoiceLine.Kind.SESSION,
                    session=s,
                    description=_session_description(s) + (
                        f" — recarga de {Competence.of(s.session_start)}, identificada "
                        "depois do fechamento daquele mês" if s.id in tardias_ids else ""
                    ),
                    energy_kwh=s.energy_kwh,
                    unit_price_kwh=s.applied_tariff_kwh,
                    amount=round2(Decimal(s.energy_kwh) * Decimal(s.applied_tariff_kwh)),
                    flagged_for_audit=flagged,
                )
            )

        if share:
            cota = availability_share(fee_total, n_enrolled, share)
            desc = f"Taxa de disponibilidade ({comp_str}) — rateio entre {n_enrolled} unidades aderentes"
            if not share.is_full_month:
                desc += f" — pro rata de {share.days_enrolled}/{share.days_in_month} dias"
            lines.append(
                InvoiceLine(
                    invoice=invoice,
                    kind=InvoiceLine.Kind.AVAILABILITY_FEE,
                    description=desc,
                    amount=cota,
                )
            )
            report.availability_collected += cota

        for rec in reconciliations:
            adjustment = _adjustment_line(rec, unit, invoice)
            if adjustment:
                lines.append(adjustment)
                report.adjustments_total += adjustment.amount

        InvoiceLine.objects.bulk_create(lines)
        invoice.total_amount = round2(sum((ln.amount for ln in lines), Decimal("0.00")))
        invoice.status = Invoice.Status.UNDER_REVIEW if has_audit else Invoice.Status.CLOSED
        invoice.save(update_fields=["total_amount", "status"])

        report.invoices.append(invoice)
        report.flagged_lines += sum(1 for ln in lines if ln.flagged_for_audit)
        for ln in lines:
            if ln.kind == InvoiceLine.Kind.SESSION:
                report.energy_total += ln.amount
                report.kwh_total += Decimal(ln.energy_kwh)

    for visitor_id, vsessions in visitor_sessions.items():
        _close_visitor_invoice(condominium, visitor_id, vsessions, comp_str, issued, due_date, report)

    return report


def _close_visitor_invoice(condominium, visitor_id, vsessions, comp_str, issued, due_date, report):
    """Visitante paga so o que consumiu, na tarifa propria do condominio, e nao
    entra no rateio da parcela fixa -- ele nao reserva disponibilidade."""
    from core.models import AppUser

    invoice = Invoice.objects.create(
        condominium=condominium,
        visitor_user=AppUser.objects.get(pk=visitor_id),
        competence=comp_str,
        status=Invoice.Status.DRAFT,
        issued_at=issued,
        due_date=due_date,
    )
    lines = [
        InvoiceLine(
            invoice=invoice,
            kind=InvoiceLine.Kind.SESSION,
            session=s,
            description=_session_description(s) + " (visitante)",
            energy_kwh=s.energy_kwh,
            unit_price_kwh=s.applied_tariff_kwh,
            amount=round2(Decimal(s.energy_kwh) * Decimal(s.applied_tariff_kwh)),
            flagged_for_audit=s.final_reading_lost,
        )
        for s in vsessions
    ]
    InvoiceLine.objects.bulk_create(lines)
    invoice.total_amount = round2(sum((ln.amount for ln in lines), Decimal("0.00")))
    invoice.status = Invoice.Status.CLOSED
    invoice.save(update_fields=["total_amount", "status"])
    report.invoices.append(invoice)
    for ln in lines:
        report.energy_total += ln.amount
        report.kwh_total += Decimal(ln.energy_kwh)


def _adjustment_line(rec: TariffReconciliation, unit, invoice) -> InvoiceLine | None:
    """A linha de ajuste de UMA reconciliacao, para UMA unidade (decisao 5).

    A fatura de M carrega o ajuste de toda competencia cujo
    `settled_in_competence` aponta para M -- normalmente so M-1, mas a conta de
    luz que atrasa faz duas cairem no mesmo mes, e cada uma gera a sua linha.

    A base sao as LINHAS FATURADAS da competencia apurada, e nao as sessoes:

    - o ajuste corrige o que foi cobrado. Sessao orfa vinculada depois do
      fechamento nunca foi cobrada; ajusta-la seria cobrar a diferenca de um
      valor que ninguem pagou;
    - cada linha guarda a tarifa que de fato lhe foi aplicada. Se a tarifa
      mudou no meio do mes, o complemento de cada sessao e `efetiva - a SUA
      tarifa`, e nao um delta unico para o mes inteiro.
    """
    billed = list(
        InvoiceLine.objects.filter(
            kind=InvoiceLine.Kind.SESSION,
            invoice__unit=unit,
            invoice__condominium=rec.condominium,
            invoice__competence=rec.competence,
        )
    )
    kwh = sum((Decimal(ln.energy_kwh) for ln in billed), Decimal("0.000"))
    if kwh == 0:
        # "As aderentes sem consumo nao recebem ajuste -- delta multiplica kWh,
        # e o kWh delas e zero."
        return None

    effective = Decimal(rec.effective_price_kwh)
    amount = round2(
        sum((Decimal(ln.energy_kwh) * (effective - Decimal(ln.unit_price_kwh)) for ln in billed),
            Decimal("0"))
    )
    if amount == 0:
        return None

    tarifas = {Decimal(ln.unit_price_kwh) for ln in billed}
    sinal = "Complemento" if amount > 0 else "Devolução"
    if len(tarifas) == 1:
        provisoria = tarifas.pop()
        delta = effective - provisoria
        detalhe = (
            f"{kwh} kWh × R$ {delta}/kWh (efetiva R$ {effective} menos provisória R$ {provisoria})"
        )
    else:
        delta = (amount / kwh).quantize(Decimal("0.0001"))
        detalhe = (
            f"{kwh} kWh, cada sessão pela diferença entre a efetiva (R$ {effective}) "
            f"e a tarifa que lhe foi aplicada; média de R$ {delta}/kWh"
        )
    return InvoiceLine(
        invoice=invoice,
        kind=InvoiceLine.Kind.TARIFF_ADJUSTMENT,
        reconciliation=rec,
        description=f"{sinal} de tarifa referente a {rec.competence}: {detalhe}",
        energy_kwh=kwh,
        unit_price_kwh=delta,
        amount=amount,
    )
