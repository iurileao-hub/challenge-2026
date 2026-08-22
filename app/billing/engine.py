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
from django.db.models import Q
from django.utils import timezone

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
        return round2(self.energy_total + self.availability_collected)


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
    return (
        ChargingSession.objects.filter(
            charge_point__condominium=condominium,
            session_start__gte=start_utc,
            session_start__lt=end_utc,
            status__in=BILLABLE_STATUSES,
            credential__isnull=False,
            applied_tariff_kwh__isnull=False,
        )
        .select_related("credential__user__unit", "charge_point")
        .order_by("session_start", "id")
    )


def _session_description(session: ChargingSession) -> str:
    """Texto do extrato. E o que o morador le -- precisa dizer *quando*, *quem*
    e, se algo saiu do normal, *o que*."""
    from billing.competence import condo_tz

    local = session.session_start.astimezone(condo_tz())
    quem = session.credential.user.name if session.credential else "credencial nao resolvida"
    base = f"Recarga {local.strftime('%d/%m %H:%M')} - {quem}"
    if session.status == ChargingSession.Status.INTERRUPTED:
        base += f" - sessao interrompida ({session.stop_reason or 'motivo nao informado'})"
    elif session.status == ChargingSession.Status.FAULT:
        base += f" - falha no ponto ({session.stop_reason or 'motivo nao informado'})"
    if session.meter_stop is None:
        base += " - leitura final perdida, cobrada a ultima leitura conhecida"
    return base


def _needs_audit(session: ChargingSession, flagged_session_ids: set[int]) -> bool:
    """Uma linha vai para auditoria por dois caminhos, ambos da Sprint 1:
    telemetria perdida (Opcao A, caso degenerado) ou anomalia aberta detectada
    antes do fechamento (Opcao B)."""
    return session.meter_stop is None or session.id in flagged_session_ids


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
    locked = existing.filter(status__in=[Invoice.Status.CLOSED, Invoice.Status.PAID])
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

    sessions = list(billable_sessions(condominium, comp))
    flagged_session_ids = set(
        AnomalyFlag.objects.filter(
            session__in=[s.id for s in sessions], status=AnomalyFlag.Status.OPEN
        ).values_list("session_id", flat=True)
    )

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
    all_unit_ids = set(units_by_id) | set(sessions_by_unit)

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
                    description=_session_description(s),
                    energy_kwh=s.energy_kwh,
                    unit_price_kwh=s.applied_tariff_kwh,
                    amount=round2(Decimal(s.energy_kwh) * Decimal(s.applied_tariff_kwh)),
                    flagged_for_audit=flagged,
                )
            )

        if share:
            cota = availability_share(fee_total, n_enrolled, share)
            desc = f"Taxa de disponibilidade ({comp_str}) - rateio entre {n_enrolled} unidades aderentes"
            if not share.is_full_month:
                desc += f" - pro rata de {share.days_enrolled}/{share.days_in_month} dias"
            lines.append(
                InvoiceLine(
                    invoice=invoice,
                    kind=InvoiceLine.Kind.AVAILABILITY_FEE,
                    description=desc,
                    amount=cota,
                )
            )
            report.availability_collected += cota

        adjustment = _adjustment_line(condominium, unit, comp, invoice)
        if adjustment:
            lines.append(adjustment)

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
            flagged_for_audit=s.meter_stop is None,
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


def _adjustment_line(condominium, unit, comp: Competence, invoice) -> InvoiceLine | None:
    """A linha de ajuste da reconciliacao (decisao 5).

    A fatura de M carrega o ajuste da competencia cujo `settled_in_competence`
    aponta para M -- normalmente M-1. Uma linha por unidade, calculada sobre o
    kWh total que a unidade consumiu na competencia apurada.
    """
    rec = TariffReconciliation.objects.filter(
        condominium=condominium, settled_in_competence=str(comp)
    ).first()
    if not rec or rec.delta_price_kwh == 0:
        return None

    apurada = Competence.parse(rec.competence)
    kwh = sum(
        (Decimal(s.energy_kwh) for s in billable_sessions(condominium, apurada)
         if s.credential and s.credential.user.unit_id == unit.id),
        Decimal("0.000"),
    )
    if kwh == 0:
        # "As aderentes sem consumo nao recebem ajuste -- delta multiplica kWh,
        # e o kWh delas e zero."
        return None

    amount = round2(kwh * Decimal(rec.delta_price_kwh))
    sinal = "Complemento" if rec.delta_price_kwh > 0 else "Devolucao"
    return InvoiceLine(
        invoice=invoice,
        kind=InvoiceLine.Kind.TARIFF_ADJUSTMENT,
        reconciliation=rec,
        description=(
            f"{sinal} de tarifa referente a {rec.competence}: {kwh} kWh x "
            f"R$ {rec.delta_price_kwh}/kWh (efetiva R$ {rec.effective_price_kwh} "
            f"menos provisoria R$ {rec.provisional_price_kwh})"
        ),
        energy_kwh=kwh,
        unit_price_kwh=rec.delta_price_kwh,
        amount=amount,
    )
