"""Roda o pipeline inteiro, do dado bruto a fatura fechada.

E o caminho completo que a Sprint 1 desenhou, executado de ponta a ponta numa
chamada -- ingestao, deteccao, fechamento -- com cada etapa dizendo o que fez.

Serve de demonstracao, mas serve tambem de verificacao: se o pipeline roda
inteiro sem intervencao e a fatura fecha com os valores do dossie, a arquitetura
se sustenta na pratica e nao so no diagrama.
"""

from datetime import datetime, time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from billing.competence import Competence, condo_tz
from billing.engine import BillingError, close_competence
from billing.reconciliation import register_reconciliation
from core.models import AnomalyFlag, Condominium, Invoice, TariffPeriod
from ingestion.adapters import SemsPlusLogAdapter
from ingestion.gateway import IngestionGateway
from ingestion.orphans import orphan_summary
from intelligence.anomalies import run_detection
from intelligence.forecast import forecast


def _rotulo(unit_label: str):
    """Ordena "12" antes de "105", sem quebrar em rotulo como "12A"."""
    digitos = "".join(ch for ch in unit_label if ch.isdigit())
    return (int(digitos) if digitos else 0, unit_label)


class Command(BaseCommand):
    help = "Executa ingestao -> deteccao -> fechamento -> previsao para a competencia."

    def add_arguments(self, parser):
        parser.add_argument("--competencia", default="2026-06")
        parser.add_argument("--reconciliar", action="store_true",
                            help="Registra a chegada da conta de luz e fecha a competencia seguinte.")
        parser.add_argument("--force", action="store_true",
                            help="Reprocessa a competencia mesmo que ja tenha fatura fechada.")

    def handle(self, *args, **opts):
        condo = Condominium.objects.order_by("id").first()
        if not condo:
            self.stderr.write("rode `manage.py seed_demo --months 6 --reset` antes")
            return
        comp = Competence.parse(opts["competencia"])
        w = self.stdout.write
        tz = condo_tz()

        w(self.style.MIGRATE_HEADING("\n[1/5] Ingestao — historico REAL do HCA G2 (SEMS+, LAB FIAP)"))
        rep = IngestionGateway(condo).ingest(SemsPlusLogAdapter())
        for linha in rep.render().splitlines():
            w("      " + linha)
        if rep.duplicates and not rep.created:
            w("      (tudo ja estava na plataforma: reentregar nao duplica cobranca)")
        orfas = orphan_summary(condo)
        if orfas["n"]:
            w(self.style.WARNING(
                f"      {orfas['n']} recarga(s) SEM DONO: {orfas['kwh']} kWh, R$ {orfas['valor']} "
                "fora do rateio ate alguem assumir (painel > Entrada de dados)"
            ))

        w(self.style.MIGRATE_HEADING(f"\n[2/5] Deteccao de anomalias — competencia {comp}"))
        inicio = datetime.combine(comp.first_day, time.min, tzinfo=tz)
        fim = datetime.combine(comp.last_day, time.max, tzinfo=tz)
        novas = run_detection(condo, inicio, fim)
        do_mes = AnomalyFlag.objects.filter(
            session__session_start__gte=inicio, session__session_start__lte=fim
        )
        w(f"      {len(novas)} anomalia(s) nova(s) nesta rodada · {do_mes.count()} registrada(s) no mes, "
          f"{do_mes.filter(status__in=AnomalyFlag.AWAITING).count()} a espera de decisao")
        # So segura fatura o que duvida do NUMERO cobrado. O resto informa.
        w(f"      {do_mes.holding().count()} seguram cobranca (duvida sobre o valor) · "
          "as demais sao aviso de operacao ou sugestao, e nao retem fatura")
        for f in (novas or list(do_mes.filter(status__in=AnomalyFlag.AWAITING)))[:6]:
            efeito = "RETEM" if f.holds_billing else ("sugere" if f.is_suggestion else "avisa")
            w(f"        · [{efeito} · {f.category} · {f.detector}] {f.explanation[:84]}")

        w(self.style.MIGRATE_HEADING(f"\n[3/5] Fechamento do rateio — {comp}"))
        try:
            rel = close_competence(condo, comp, force=opts["force"])
        except BillingError:
            w(self.style.WARNING(
                f"      {comp} ja tem fatura fechada: MANTIDA. Fatura fechada nao se reescreve "
                "(use --force para reprocessar de proposito)."
            ))
            rel = None
        faturas = Invoice.objects.filter(condominium=condo, competence=str(comp))
        if rel:
            w(f"      {len(rel.invoices)} faturas · {rel.kwh_total} kWh · "
              f"R$ {rel.energy_total} de energia + R$ {rel.availability_collected} de disponibilidade")
            w(f"      total faturado: R$ {rel.total_billed} · residuo do rateio: R$ {rel.residual}")
            w(f"      linhas marcadas para auditoria: {rel.flagged_lines}")
        else:
            total = faturas.aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")
            w(f"      {faturas.count()} faturas · total faturado: R$ {total}")

        retidas = faturas.filter(status=Invoice.Status.UNDER_REVIEW).select_related("unit")
        if retidas:
            w(self.style.WARNING(
                f"      {retidas.count()} fatura(s) retida(s) em auditoria: "
                + ", ".join(str(i.unit.label) for i in retidas if i.unit)
            ))

        w(self.style.MIGRATE_HEADING("\n[4/5] Faturas das unidades que consumiram"))
        consumiram = [i for i in faturas.select_related("unit") if i.unit and i.lines.filter(kind="session").exists()]
        for inv in sorted(consumiram, key=lambda i: _rotulo(i.unit.label)):
            w(f"      unidade {inv.unit.label:>4}: R$ {inv.total_amount:>8} "
              f"({inv.lines.count()} linhas, {inv.get_status_display()})")

        w(self.style.MIGRATE_HEADING("\n[5/5] Previsao de demanda — 7 dias"))
        prev = forecast(condo, today=comp.last_day)
        w(f"      modelo servido: {prev.chosen_model or 'media (historico curto)'}")
        if prev.backtest_mae_kwh:
            w(f"      backtest: MAE {prev.backtest_mae_kwh:.1f} kWh/dia "
              f"vs baseline {prev.baseline_mae_kwh:.1f} kWh/dia")
        w(f"      total previsto: {prev.total_predicted_kwh:.1f} kWh")
        for a in prev.alerts:
            w(self.style.WARNING(f"      alerta [{a.severity}]: {a.message[:100]}"))

        if opts["reconciliar"]:
            self._reconciliar(condo, comp, faturas)

        w(self.style.SUCCESS("\nPipeline concluido.\n"))

    def _reconciliar(self, condo, comp, faturas):
        w = self.stdout.write
        w(self.style.MIGRATE_HEADING(
            f"\n[extra] Conta de luz de {comp} chegou — reconciliacao em dois tempos"))
        vigente = TariffPeriod.objects.in_force_on(condo, comp.last_day)
        antes = {i.pk: i.total_amount for i in faturas}
        rec = register_reconciliation(
            condo, comp,
            utility_invoice_total=Decimal("3094.00"),
            utility_invoice_kwh=Decimal("3400.000"),
            provisional_price_kwh=vigente.price_kwh,
        )
        w(f"      efetiva R$ {rec.effective_price_kwh}/kWh · provisoria R$ "
          f"{rec.provisional_price_kwh}/kWh · delta R$ {rec.delta_price_kwh}/kWh")
        seguinte = comp.next()
        try:
            rel2 = close_competence(condo, seguinte)
        except BillingError:
            w(self.style.WARNING(f"      {seguinte} ja estava fechada: mantida."))
            return
        ajustes = [ln for i in rel2.invoices for ln in i.lines.filter(kind="tariff_adjustment")]
        w(f"      {len(ajustes)} linha(s) de ajuste na fatura de {seguinte}: R$ {rel2.adjustments_total}")
        for ln in sorted(ajustes, key=lambda ln: _rotulo(ln.invoice.unit.label))[:12]:
            w(f"        · unidade {ln.invoice.unit.label:>4}: R$ {ln.amount}")
        # So afirma o que conferiu: compara os totais de antes e depois.
        depois = {i.pk: i.total_amount for i in Invoice.objects.filter(pk__in=antes)}
        if depois == antes:
            w(self.style.SUCCESS(
                f"      {comp} conferido: as {len(antes)} faturas tem o mesmo total de antes. "
                "O acerto entrou como linha nova no mes seguinte."))
        else:
            w(self.style.ERROR(f"      ATENCAO: faturas de {comp} mudaram durante a reconciliacao."))
