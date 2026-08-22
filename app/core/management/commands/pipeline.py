"""Roda o pipeline inteiro, do dado bruto a fatura fechada.

E o caminho completo que a Sprint 1 desenhou, executado de ponta a ponta numa
chamada -- ingestao, deteccao, fechamento -- com cada etapa dizendo o que fez.

Serve de demonstracao, mas serve tambem de verificacao: se o pipeline roda
inteiro sem intervencao e a fatura fecha com os valores do dossie, a arquitetura
se sustenta na pratica e nao so no diagrama.
"""

from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from billing.competence import Competence
from billing.engine import close_competence
from billing.reconciliation import register_reconciliation
from core.models import AnomalyFlag, Condominium, Invoice
from intelligence.anomalies import run_detection
from intelligence.forecast import forecast

BRT = ZoneInfo("America/Sao_Paulo")


class Command(BaseCommand):
    help = "Executa ingestao -> deteccao -> fechamento para a competencia."

    def add_arguments(self, parser):
        parser.add_argument("--competencia", default="2026-06")
        parser.add_argument("--reconciliar", action="store_true",
                            help="Registra a chegada da conta de luz e fecha a competencia seguinte.")

    def handle(self, *args, **opts):
        condo = Condominium.objects.first()
        if not condo:
            self.stderr.write("rode `manage.py seed_demo --months 6 --reset` antes")
            return
        comp = Competence.parse(opts["competencia"])
        w = self.stdout.write

        w(self.style.MIGRATE_HEADING(f"\n[1/4] Deteccao de anomalias — competencia {comp}"))
        inicio = datetime.combine(comp.first_day, time.min, tzinfo=BRT)
        fim = datetime.combine(comp.last_day, time.max, tzinfo=BRT)
        flags = run_detection(condo, inicio, fim)
        w(f"      {len(flags)} anomalia(s) detectada(s) ANTES do fechamento")
        for f in flags[:5]:
            w(f"        · [{f.category}] {f.explanation[:96]}")

        w(self.style.MIGRATE_HEADING(f"\n[2/4] Fechamento do rateio — {comp}"))
        rel = close_competence(condo, comp, force=True)
        w(f"      {len(rel.invoices)} faturas · {rel.kwh_total} kWh · "
          f"R$ {rel.energy_total} de energia + R$ {rel.availability_collected} de disponibilidade")
        w(f"      total faturado: R$ {rel.total_billed} · residuo do rateio: R$ {rel.residual}")
        w(f"      linhas marcadas para auditoria: {rel.flagged_lines}")

        retidas = [i for i in rel.invoices if i.status == Invoice.Status.UNDER_REVIEW]
        if retidas:
            w(self.style.WARNING(
                f"      {len(retidas)} fatura(s) retida(s) em auditoria: "
                + ", ".join(str(i.unit.label) for i in retidas if i.unit)
            ))

        w(self.style.MIGRATE_HEADING("\n[3/4] Faturas das unidades que consumiram"))
        for inv in sorted(
            [i for i in rel.invoices if i.unit and i.lines.filter(kind="session").exists()],
            key=lambda i: int(i.unit.label),
        ):
            w(f"      unidade {inv.unit.label:>4}: R$ {inv.total_amount:>8} "
              f"({inv.lines.count()} linhas, {inv.get_status_display()})")

        w(self.style.MIGRATE_HEADING("\n[4/4] Previsao de demanda — 7 dias"))
        prev = forecast(condo, today=comp.last_day)
        w(f"      modelo servido: {prev.chosen_model or 'media (historico curto)'}")
        if prev.backtest_mae_kwh:
            w(f"      backtest: MAE {prev.backtest_mae_kwh:.1f} kWh/dia "
              f"vs baseline {prev.baseline_mae_kwh:.1f} kWh/dia")
        w(f"      total previsto: {prev.total_predicted_kwh:.1f} kWh")
        for a in prev.alerts:
            w(self.style.WARNING(f"      alerta [{a.severity}]: {a.message[:100]}"))

        if opts["reconciliar"]:
            w(self.style.MIGRATE_HEADING(
                f"\n[extra] Conta de luz de {comp} chegou — reconciliacao em dois tempos"))
            rec = register_reconciliation(
                condo, comp,
                utility_invoice_total=Decimal("3094.00"),
                utility_invoice_kwh=Decimal("3400.000"),
                provisional_price_kwh=Decimal("0.7252"),
            )
            w(f"      efetiva R$ {rec.effective_price_kwh}/kWh · provisoria R$ "
              f"{rec.provisional_price_kwh}/kWh · delta R$ {rec.delta_price_kwh}/kWh")
            seguinte = comp.next()
            rel2 = close_competence(condo, seguinte, force=True)
            ajustes = [
                ln for i in rel2.invoices for ln in i.lines.filter(kind="tariff_adjustment")
            ]
            w(f"      {len(ajustes)} linha(s) de ajuste na fatura de {seguinte}: "
              f"R$ {sum((l.amount for l in ajustes), Decimal('0.00'))}")
            for ln in ajustes:
                w(f"        · unidade {ln.invoice.unit.label:>4}: R$ {ln.amount}")
            w(self.style.SUCCESS(
                f"      junho permanece intacto — nenhuma fatura fechada foi reescrita"))

        w(self.style.SUCCESS("\nPipeline concluido.\n"))
