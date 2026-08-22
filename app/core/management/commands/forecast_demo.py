"""Roda a previsao de 7 dias e mostra a curva, o backtest e os alertas."""

from datetime import date

from django.core.management.base import BaseCommand

from core.models import Condominium
from intelligence.forecast import forecast


class Command(BaseCommand):
    help = "Previsao de demanda de 7 dias para o condominio de demonstracao."

    def add_arguments(self, parser):
        parser.add_argument("--today", default="2026-05-31")

    def handle(self, *args, **opts):
        condo = Condominium.objects.first()
        if not condo:
            self.stderr.write("nenhum condominio; rode seed_demo antes")
            return
        today = date.fromisoformat(opts["today"])
        r = forecast(condo, today=today)

        self.stdout.write(f"Condominio: {condo.name}")
        self.stdout.write(f"Metodo: {r.method}")
        self.stdout.write(f"Treinado em {r.trained_on_days} dias de historico\n")
        if r.backtest_mae_kwh is not None:
            veredito = (
                "modelo VENCE a media por dia da semana"
                if r.beats_baseline else "modelo NAO vence a media por dia da semana"
            )
            self.stdout.write(
                f"Backtest (ultimos 14 dias): MAE {r.backtest_mae_kwh:.1f} kWh/dia "
                f"| baseline {r.baseline_mae_kwh:.1f} kWh/dia -> {veredito}\n"
            )
        self.stdout.write("Curva prevista:")
        for d in r.days:
            barra = "#" * int(d.predicted_kwh / 3)
            self.stdout.write(
                f"  {d.day:%a %d/%m}  {d.predicted_kwh:6.1f} kWh  "
                f"{d.predicted_sessions:4.1f} sessoes  {barra}"
            )
        self.stdout.write(f"\nTotal previsto em 7 dias: {r.total_predicted_kwh:.1f} kWh")
        self.stdout.write(f"\nAlertas ({len(r.alerts)}):")
        for a in r.alerts:
            self.stdout.write(f"  [{a.severity.upper():<8}] {a.message}")
        if not r.alerts:
            self.stdout.write("  nenhum -- operacao dentro dos limites")
