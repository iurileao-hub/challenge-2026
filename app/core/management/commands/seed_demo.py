"""Popula o banco com um condominio de demonstracao.

Dois modos, e a diferenca entre eles importa:

- `--scenario aurora` (padrao): o mes ficticio de junho/2026 do dossie, exato,
  10 sessoes escritas a mao. E o que serve de prova: os numeros da fatura sao
  conferiveis contra o documento da Sprint 1.
- `--months N`: alem do mes ficticio, gera N meses sinteticos calibrados no
  dado real de Asensio et al., com anomalias injetadas e gabarito. E o que da
  volume para a IA ter o que aprender e para o painel ter o que mostrar.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    AnomalyFlag,
    AppUser,
    ChargePoint,
    ChargingSession,
    Condominium,
    Credential,
    Invoice,
    InvoiceLine,
    ProgramEnrollment,
    TariffPeriod,
    TariffReconciliation,
    TelemetryReading,
    Unit,
    Vehicle,
)
from core.scenarios import build_jardim_aurora

#: Ordem de remocao do cenario de demonstracao.
#:
#: As FKs de faturamento sao `PROTECT` de proposito -- ninguem apaga um
#: condominio que tem fatura emitida por descuido de query. O preco e que o
#: reset da demo precisa descer a arvore na mao, das folhas para a raiz.
TEARDOWN_ORDER = [
    AnomalyFlag, InvoiceLine, Invoice, TelemetryReading, ChargingSession,
    Vehicle, Credential, AppUser, ProgramEnrollment, TariffReconciliation,
    TariffPeriod, ChargePoint, Unit, Condominium,
]


class Command(BaseCommand):
    help = "Popula o banco com o condominio de demonstracao (mes ficticio + meses sinteticos)."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=0,
                            help="Meses sinteticos a gerar ANTES de junho/2026.")
        parser.add_argument("--seed", type=int, default=20260831)
        parser.add_argument("--anomaly-rate", type=float, default=0.06)
        parser.add_argument("--reset", action="store_true",
                            help="Apaga o condominio de demonstracao antes.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            total = 0
            for model in TEARDOWN_ORDER:
                n, _ = model.objects.all().delete()
                total += n
            self.stdout.write(f"  removidos {total} objetos do cenario anterior")

        scenario = build_jardim_aurora(extra_residents=opts["months"] > 0)
        condo = scenario["condominium"]
        self.stdout.write(self.style.SUCCESS(
            f"Cenario do dossie criado: {condo.name} "
            f"({len(scenario['units'])} unidades, {len(scenario['sessions'])} sessoes de junho/2026)"
        ))

        months = opts["months"]
        if months > 0:
            from ingestion.generator import SyntheticGenerator

            gen = SyntheticGenerator(
                condo, seed=opts["seed"], anomaly_rate=opts["anomaly_rate"]
            )
            end = date(2026, 5, 31)
            start_month = 6 - months
            start = date(2026, max(start_month, 1), 1)
            result = gen.generate(start, end)
            self.stdout.write(self.style.SUCCESS(
                f"Historico sintetico {start:%m/%Y} a {end:%m/%Y}: "
                f"{result.sessions_created} sessoes, {result.kwh_total} kWh, "
                f"{result.readings_created} leituras de telemetria, "
                f"{result.anomalies_injected} anomalias injetadas (com gabarito)"
            ))
            for kind in ("consumption", "idle", "power_degradation", "metering", "health"):
                n = sum(1 for g in result.ground_truth if g.category == kind)
                self.stdout.write(f"    {kind:<20} {n}")
