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

        self._create_logins(scenario)
        n = self._add_operational_telemetry(scenario)
        self.stdout.write(f"  telemetria de junho/2026: {n} leituras")

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

    def _create_logins(self, scenario):
        """Logins do portal para a demonstracao.

        Nem todo morador tem login -- o cartao RFID sozinho ja gera sessao e
        fatura. O login existe para quem quer ver o extrato, e e por isso que
        `app_user` e separado de `auth.User`.
        """
        from django.contrib.auth.models import User

        contas = [
            ("sindica", scenario["users"]["gestor"], True),
            ("ana", scenario["users"]["ana"], False),
            ("carla", scenario["users"]["carla"], False),
            ("davi", scenario["users"]["davi"], False),
        ]
        for username, app_user, is_staff in contas:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": app_user.email, "first_name": app_user.name.split()[0]},
            )
            user.set_password("chargeops")
            user.is_staff = is_staff
            user.is_superuser = is_staff
            user.save()
            app_user.auth_user = user
            app_user.save(update_fields=["auth_user"])
        self.stdout.write(
            "Logins criados (senha 'chargeops'): sindica (gestora), ana, carla, davi"
        )

    def _add_operational_telemetry(self, scenario) -> int:
        """Telemetria de junho para as sessoes do mes ficticio.

        O dossie descreve as 10 sessoes por energia e horario, sem telemetria --
        e suficiente para conferir a fatura, mas deixa o ponto parecendo morto no
        painel (nenhum heartbeat) e cega a deteccao de ociosidade, que le a
        telemetria e nao a sessao.

        Os heartbeats horarios e os MeterValues a cada 15 min sao reconstruidos
        a partir da energia e da duracao ja declaradas: nao inventam consumo, so
        distribuem no tempo o consumo que o dossie ja fixou.
        """
        from datetime import datetime, time, timedelta
        from decimal import Decimal
        from zoneinfo import ZoneInfo

        from core.models import TelemetryReading

        BRT = ZoneInfo("America/Sao_Paulo")
        ponto = scenario["charge_point"]
        leituras = []

        for sessao in scenario["sessions"].values():
            duracao = (sessao.session_end - sessao.session_start).total_seconds() / 3600
            if duracao <= 0:
                continue
            potencia = float(sessao.energy_kwh) / duracao
            acc = Decimal(sessao.meter_start)
            passo = timedelta(minutes=15)
            t = sessao.session_start
            leituras.append(TelemetryReading(
                charge_point=ponto, session=sessao, ts=t,
                kind=TelemetryReading.Kind.STATUS_CHANGE,
                state=TelemetryReading.State.CHARGING,
                power_kw=Decimal(str(round(potencia, 2))), energy_kwh_total=acc,
            ))
            while t < sessao.session_end:
                t = min(t + passo, sessao.session_end)
                acc = acc + Decimal(str(round(potencia * 0.25, 3)))
                leituras.append(TelemetryReading(
                    charge_point=ponto, session=sessao, ts=t,
                    kind=TelemetryReading.Kind.METER_VALUE,
                    state=TelemetryReading.State.CHARGING,
                    power_kw=Decimal(str(round(potencia, 2))),
                    energy_kwh_total=acc,
                ))

        # Heartbeats horarios de junho -- o sinal de que o ponto esta vivo.
        t = datetime.combine(date(2026, 6, 1), time(0), tzinfo=BRT)
        limite = datetime.combine(date(2026, 6, 30), time(23), tzinfo=BRT)
        while t <= limite:
            leituras.append(TelemetryReading(
                charge_point=ponto, session=None, ts=t,
                kind=TelemetryReading.Kind.HEARTBEAT,
                state=TelemetryReading.State.CONNECTED,
            ))
            t += timedelta(hours=1)

        TelemetryReading.objects.bulk_create(leituras, batch_size=2000)
        return len(leituras)
