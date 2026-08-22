"""Gerador de dados sinteticos calibrado no dado real.

Produz sessoes e telemetria diretamente no esquema da Frente 3-C, e -- o que o
torna util alem da demo -- **injeta anomalias com gabarito conhecido**. Sem
gabarito, "a deteccao funciona" e opiniao; com gabarito, vira precisao e recall
sobre um conjunto que se sabe de antemao quem e quem.

O modelo fisico da sessao, que e onde mora a analise propria:

    o carro chega com carga parcial e fica plugado por um tempo que vem da
    distribuicao real; a energia que entra e o menor entre o que a bateria
    aceita e o que o ponto entrega naquele tempo.

Disso cai de graca um fenomeno que interessa ao produto: **ociosidade**. Se o
carro termina de carregar em 3 h mas fica plugado 9 h, sao 6 h de vaga ocupada
sem entregar energia -- o "carro-tampao" que a Frente 1 identificou como dor, e
que aqui nasce da mecanica do modelo, nao de uma regra colada por cima.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Iterable

import numpy as np
from django.db import transaction

from billing.competence import condo_tz
from billing.money import round2, round3
from core.models import (
    ChargePoint,
    ChargingSession,
    Condominium,
    Credential,
    MeasurementSource,
    TariffPeriod,
    TelemetryReading,
)
from ingestion.calibration import CalibrationParams

#: Intervalo entre amostras de telemetria dentro da sessao (OCPP MeterValues).
METER_INTERVAL = timedelta(minutes=15)
#: Intervalo entre heartbeats do ponto fora de sessao.
HEARTBEAT_INTERVAL = timedelta(hours=1)

ANOMALY_KINDS = ("consumption", "idle", "power_degradation", "metering", "health")


@dataclass
class GroundTruth:
    """O gabarito: o que foi injetado, onde e por que.

    E contra isto que a deteccao e medida. Sem ele nao ha metrica objetiva,
    so impressao.
    """

    session_id: int | None
    charge_point_id: int | None
    category: str
    detail: str


@dataclass
class GenerationResult:
    sessions_created: int = 0
    readings_created: int = 0
    ground_truth: list[GroundTruth] = field(default_factory=list)
    kwh_total: Decimal = Decimal("0.000")

    @property
    def anomalies_injected(self) -> int:
        return len(self.ground_truth)


class SyntheticGenerator:
    """Gera meses de operacao de um condominio.

    Deterministico por `seed`: a mesma semente reproduz exatamente o mesmo mes,
    o que e requisito para que a metrica da deteccao seja compar 'avel entre
    execucoes e para que a demo nao mude debaixo do pe.
    """

    def __init__(
        self,
        condominium: Condominium,
        *,
        params: CalibrationParams | None = None,
        seed: int = 20260831,
        anomaly_rate: float = 0.06,
    ):
        self.condo = condominium
        self.params = params or CalibrationParams.load()
        self.rng = np.random.default_rng(seed)
        self.anomaly_rate = anomaly_rate
        self.tz = condo_tz()

    # -- amostragem calibrada -------------------------------------------------

    def _sample_hour(self) -> int:
        return int(self.rng.choice(24, p=np.array(self.params.hour_weights)))

    def _sample_duration_hours(self) -> float:
        """Lognormal ajustada ao dado real, truncada nos percentis 1 e 99 para
        nao gerar a cauda de 55 h que e cabo esquecido, nao recarga."""
        d = float(self.rng.lognormal(self.params.duration_log_mu, self.params.duration_log_sigma))
        return float(np.clip(d, 0.5, 14.0))

    def _sample_sessions_per_month(self) -> int:
        mean = self.params.sessions_per_user_month_mean
        sd = self.params.sessions_per_user_month_sd
        # Condominio recarrega menos vezes que workplace (a recarga noturna e
        # mais longa e cobre mais dias), por isso a media entra reduzida.
        n = self.rng.normal(mean * 0.6, sd * 0.5)
        return int(np.clip(round(n), 1, 25))

    # -- construcao -----------------------------------------------------------

    def _effective_power(self, point: ChargePoint) -> float:
        """Potencia efetiva do ponto: nominal com perdas e limitacao do
        veiculo (nem todo EV aceita a potencia toda do wallbox)."""
        nominal = float(point.rated_power_kw)
        return nominal * float(self.rng.uniform(0.72, 0.96))

    def _battery_demand(self, credential: Credential) -> tuple[float, float]:
        """Quanto a bateria aceita nesta chegada: o carro nao chega vazio."""
        vehicles = list(credential.user.vehicles.all())
        capacity = float(vehicles[0].battery_capacity_kwh) if vehicles else 50.0
        soc = float(self.rng.uniform(0.25, 0.75))
        return capacity * (1.0 - soc), capacity

    @transaction.atomic
    def generate(self, start: date, end: date) -> GenerationResult:
        """Gera o periodo [start, end] para todos os pontos do condominio."""
        result = GenerationResult()
        points = list(self.condo.charge_points.all())
        if not points:
            raise ValueError("condominio sem ponto de recarga cadastrado")

        credentials = list(
            Credential.objects.filter(
                user__unit__condominium=self.condo, status=Credential.Status.ACTIVE
            ).select_related("user__unit").prefetch_related("user__vehicles")
        )
        if not credentials:
            raise ValueError("condominio sem credenciais ativas")

        months = self._months_between(start, end)
        planned: list[tuple[datetime, Credential]] = []
        for month_start, month_end in months:
            for cred in credentials:
                for _ in range(self._sample_sessions_per_month()):
                    moment = self._random_moment(month_start, month_end)
                    planned.append((moment, cred))

        planned.sort(key=lambda t: t[0])
        n_anomalies = int(len(planned) * self.anomaly_rate)
        anomaly_idx = set(
            self.rng.choice(len(planned), size=min(n_anomalies, len(planned)), replace=False).tolist()
        ) if planned else set()

        # Estado do medidor por ponto -- acumulado, como no equipamento real.
        meters = {p.id: Decimal("1000.000") for p in points}
        readings: list[TelemetryReading] = []

        for i, (moment, cred) in enumerate(planned):
            point = points[i % len(points)]
            kind = (
                ANOMALY_KINDS[int(self.rng.integers(0, len(ANOMALY_KINDS)))]
                if i in anomaly_idx
                else None
            )
            session, session_readings, truth = self._build_session(
                point, cred, moment, meters, anomaly=kind
            )
            result.sessions_created += 1
            result.kwh_total += Decimal(session.energy_kwh)
            readings.extend(session_readings)
            if truth:
                result.ground_truth.append(truth)

        readings.extend(self._heartbeats(points, start, end, result))
        TelemetryReading.objects.bulk_create(readings, batch_size=2000)
        result.readings_created = len(readings)
        return result

    def _months_between(self, start: date, end: date) -> list[tuple[date, date]]:
        out, cur = [], date(start.year, start.month, 1)
        while cur <= end:
            nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
            out.append((max(cur, start), min(nxt - timedelta(days=1), end)))
            cur = nxt
        return out

    def _random_moment(self, start: date, end: date) -> datetime:
        span = (end - start).days
        day = start + timedelta(days=int(self.rng.integers(0, max(span, 1) + 1)))
        hour = self._sample_hour()
        minute = int(self.rng.integers(0, 60))
        return datetime.combine(day, time(hour, minute), tzinfo=self.tz)

    def _tariff_for(self, moment: datetime) -> TariffPeriod | None:
        d = moment.astimezone(self.tz).date()
        return (
            TariffPeriod.objects.filter(condominium=self.condo, valid_from__lte=d)
            .filter(valid_to__isnull=True)
            .order_by("-valid_from")
            .first()
        )

    def _build_session(self, point, cred, start_moment, meters, anomaly: str | None):
        """Monta uma sessao e sua telemetria, aplicando a anomalia quando houver."""
        plugged_hours = self._sample_duration_hours()
        power = self._effective_power(point)
        demand, capacity = self._battery_demand(cred)

        degraded_from = None
        if anomaly == "idle":
            # Carro-tampao: fica plugado muito depois de terminar.
            plugged_hours = min(plugged_hours * float(self.rng.uniform(2.5, 4.0)), 20.0)
        elif anomaly == "power_degradation":
            degraded_from = 0.45  # a partir de 45% da sessao a potencia despenca
        elif anomaly == "consumption":
            # Energia acima do que a bateria comporta -- fisicamente impossivel,
            # portanto medicao ou desvio, nunca recarga legitima.
            demand = capacity * float(self.rng.uniform(1.15, 1.45))

        charging_hours = min(demand / power, plugged_hours)
        if degraded_from:
            full = charging_hours * degraded_from
            rest = (charging_hours - full) * 2.2   # leva mais tempo pela queda
            charging_hours = min(full + rest, plugged_hours)
            energy = full * power + (charging_hours - full) * power * 0.35
        else:
            energy = charging_hours * power

        energy_dec = round3(Decimal(str(max(energy, 0.05))))
        meter_start = meters[point.id]
        meter_stop = meter_start + energy_dec
        meters[point.id] = meter_stop

        status = ChargingSession.Status.COMPLETED
        stop_reason = "Local"
        lost_reading = anomaly == "metering"
        if lost_reading:
            status = ChargingSession.Status.INTERRUPTED
            stop_reason = "PowerLoss"

        tariff = self._tariff_for(start_moment)
        session = ChargingSession.objects.create(
            charge_point=point,
            credential=cred,
            auth_id=cred.auth_tag,
            auth_method=(
                ChargingSession.AuthMethod.RFID
                if cred.kind == Credential.Kind.RFID
                else ChargingSession.AuthMethod.APP
            ),
            session_start=start_moment,
            session_end=start_moment + timedelta(hours=plugged_hours),
            meter_start=meter_start,
            meter_stop=None if lost_reading else meter_stop,
            energy_kwh=energy_dec,
            max_power_kw=round2(Decimal(str(power))),
            status=status,
            stop_reason=stop_reason,
            measurement_source=MeasurementSource.CLOUD,
            applied_tariff=tariff,
            applied_tariff_kwh=tariff.price_kwh if tariff else Decimal("0.7252"),
        )

        readings = list(
            self._session_readings(session, point, power, charging_hours, plugged_hours, degraded_from)
        )

        truth = None
        if anomaly and anomaly != "health":
            truth = GroundTruth(
                session_id=session.id,
                charge_point_id=None,
                category=anomaly,
                detail={
                    "consumption": f"energia {energy_dec} kWh acima da capacidade da bateria ({capacity:.1f} kWh)",
                    "idle": f"{plugged_hours - charging_hours:.1f} h plugado sem carregar",
                    "power_degradation": "potencia cai a 35% no meio da sessao",
                    "metering": "leitura final do medidor perdida",
                }[anomaly],
            )
        elif anomaly == "health":
            truth = GroundTruth(
                session_id=None,
                charge_point_id=point.id,
                category="health",
                detail="janela sem heartbeat apos a sessao",
            )
        return session, readings, truth

    def _session_readings(self, session, point, power, charging_hours, plugged_hours, degraded_from):
        """MeterValues a cada 15 min, com a potencia caindo a zero quando a
        bateria enche -- e o sinal que a deteccao de ociosidade le."""
        t = session.session_start
        end = session.session_end
        acc = Decimal(session.meter_start)
        charge_end = session.session_start + timedelta(hours=charging_hours)
        step_h = METER_INTERVAL.total_seconds() / 3600

        yield TelemetryReading(
            charge_point=point, session=session, ts=t,
            kind=TelemetryReading.Kind.STATUS_CHANGE,
            state=TelemetryReading.State.CHARGING,
            power_kw=round2(Decimal(str(power))), energy_kwh_total=acc,
        )
        while t < end:
            t += METER_INTERVAL
            charging = t <= charge_end
            p = power
            if charging and degraded_from:
                frac = (t - session.session_start).total_seconds() / max(
                    (charge_end - session.session_start).total_seconds(), 1
                )
                if frac > degraded_from:
                    p = power * 0.35
            if not charging:
                p = 0.0
            else:
                acc = acc + round3(Decimal(str(p * step_h)))
            yield TelemetryReading(
                charge_point=point, session=session, ts=min(t, end),
                kind=TelemetryReading.Kind.METER_VALUE,
                state=(
                    TelemetryReading.State.CHARGING if charging
                    else TelemetryReading.State.FINISHED
                ),
                power_kw=round2(Decimal(str(p))), energy_kwh_total=acc,
            )

    def _heartbeats(self, points, start: date, end: date, result: GenerationResult):
        """Heartbeats fora de sessao. A *ausencia* deles e o sinal de ponto
        offline -- por isso a saude do ponto precisa de tabela propria."""
        out = []
        offline_windows = {p.id: [] for p in points}
        for p in points:
            # Uma janela offline por ponto no periodo, com gabarito.
            day = start + timedelta(days=int(self.rng.integers(0, max((end - start).days, 1))))
            begin = datetime.combine(day, time(int(self.rng.integers(2, 20))), tzinfo=self.tz)
            offline_windows[p.id].append((begin, begin + timedelta(hours=7)))
            result.ground_truth.append(
                GroundTruth(
                    session_id=None, charge_point_id=p.id, category="health",
                    detail=f"ponto sem heartbeat de {begin:%d/%m %H:%M} por 7 h",
                )
            )

        for p in points:
            t = datetime.combine(start, time(0), tzinfo=self.tz)
            limit = datetime.combine(end, time(23, 59), tzinfo=self.tz)
            while t <= limit:
                if not any(a <= t <= b for a, b in offline_windows[p.id]):
                    out.append(
                        TelemetryReading(
                            charge_point=p, session=None, ts=t,
                            kind=TelemetryReading.Kind.HEARTBEAT,
                            state=TelemetryReading.State.CONNECTED,
                        )
                    )
                t += HEARTBEAT_INTERVAL
        return out
