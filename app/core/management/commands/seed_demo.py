"""Popula o banco com um condominio de demonstracao.

Dois modos, e a diferenca entre eles importa:

- `--scenario aurora` (padrao): o mes ficticio de junho/2026 do dossie, exato,
  10 sessoes escritas a mao. E o que serve de prova: os numeros da fatura sao
  conferiveis contra o documento da Sprint 1.
- `--months N`: alem do mes ficticio, gera N meses sinteticos calibrados no
  dado real de Asensio et al., com anomalias injetadas e gabarito. E o que da
  volume para a IA ter o que aprender e para o painel ter o que mostrar.

  Os N meses TERMINAM em junho/2026. Em junho, o gerador so produz recargas das
  unidades que o dossie nao descreve: as faturas das unidades 72, 34 e 105
  continuam sendo, centavo a centavo, as do documento da Sprint 1. A versao
  anterior parava em maio, e junho ficava so com as 10 sessoes escritas a mao
  -- 9 das 12 unidades aderentes sem recarregar nenhuma vez no mes. Essa
  quebra de regime era o que o modelo de previsao "aprendia": o backtest
  vencia a linha de base por adivinhar o degrau, nao por entender a demanda.
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
from ingestion.models import IngestionRun, RawEvent

#: Unidades cujas sessoes de junho/2026 sao as do dossie, escritas a mao.
DOSSIER_UNITS = ("72", "34", "105")

#: Ordem de remocao do cenario de demonstracao.
#:
#: As FKs de faturamento sao `PROTECT` de proposito -- ninguem apaga um
#: condominio que tem fatura emitida por descuido de query. O preco e que o
#: reset da demo precisa descer a arvore na mao, das folhas para a raiz.
TEARDOWN_ORDER = [
    RawEvent, IngestionRun, AnomalyFlag, InvoiceLine, Invoice, TelemetryReading, ChargingSession,
    Vehicle, Credential, AppUser, ProgramEnrollment, TariffReconciliation,
    TariffPeriod, ChargePoint, Unit, Condominium,
]


class Command(BaseCommand):
    help = "Popula o banco com o condominio de demonstracao (mes ficticio + meses sinteticos)."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=0,
                            help="Meses sinteticos, terminando em junho/2026 (6 = jan a jun).")
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
            anteriores = min(months - 1, 5)
            if anteriores:
                start = date(2026, 6 - anteriores, 1)
                result = gen.generate(start, date(2026, 5, 31))
                self._report_generation(f"{start:%m/%Y} a 05/2026", result)

            outras = Credential.objects.filter(
                user__unit__condominium=condo, status=Credential.Status.ACTIVE
            ).exclude(user__unit__label__in=DOSSIER_UNITS)
            junho = gen.generate(
                date(2026, 6, 1), date(2026, 6, 30), credentials=outras,
                reserved=self._real_log_intervals(), heartbeats=False,
            )
            self._report_generation("06/2026 (unidades fora do dossie)", junho)

    def _report_generation(self, periodo, result):
        self.stdout.write(self.style.SUCCESS(
            f"Historico sintetico {periodo}: {result.sessions_created} sessoes, "
            f"{result.kwh_total} kWh, {result.readings_created} leituras, "
            f"{result.anomalies_injected} anomalias injetadas (com gabarito)"
        ))
        self.stdout.write(
            f"    conector ocupado: {result.sessions_deferred} esperaram a vez, "
            f"{result.sessions_lost} desistiram (demanda reprimida)"
        )
        for kind in ("consumption", "idle", "power_degradation", "metering", "health"):
            n = sum(1 for g in result.ground_truth if g.category == kind)
            if n:
                self.stdout.write(f"    {kind:<20} {n}")

    def _real_log_intervals(self):
        """Horarios em que o conector REAL esteve ocupado (historico do SEMS+).

        O log real chega depois, pelo `pipeline`. O gerador deixa esses
        intervalos livres para que dado sintetico e dado real nao disputem o
        mesmo cabo na mesma hora.
        """
        from ingestion.adapters import SemsPlusLogAdapter
        from ingestion.gateway import CanonicalSession

        return [
            (i.session_start, i.session_end) for i in SemsPlusLogAdapter().fetch()
            if isinstance(i, CanonicalSession)
        ]

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
                proximo = min(t + passo, sessao.session_end)
                # O ultimo intervalo costuma ser parcial. Somar 15 min inteiros
                # fazia o medidor da telemetria fechar ACIMA do `meter_stop` da
                # propria sessao (1018,592 contra 1018,400 na sessao 1001).
                horas = (proximo - t).total_seconds() / 3600
                t = proximo
                acc = acc + Decimal(str(round(potencia * horas, 3)))
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
