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
from core.policy import IDLE_HOURS_THRESHOLD, contended_hours
from core.models import (
    ChargingSession,
    Condominium,
    Credential,
    MeasurementSource,
    TelemetryReading,
)
from ingestion.calibration import CalibrationParams
from ingestion.gateway import (
    CanonicalReading,
    CanonicalSession,
    IngestionGateway,
    IngestionReport,
)
from ingestion.models import IngestionRun, RawEvent

#: Quanto um morador espera por um conector ocupado antes de desistir e
#: carregar em outro lugar. Premissa declarada, como o perfil semanal.
MAX_WAIT = timedelta(hours=6)
#: Folga entre um carro sair e o seguinte plugar.
TURNAROUND = timedelta(minutes=10)

#: Intervalo entre amostras de telemetria dentro da sessao (OCPP MeterValues).
METER_INTERVAL = timedelta(minutes=15)
#: Intervalo entre heartbeats do ponto fora de sessao.
HEARTBEAT_INTERVAL = timedelta(hours=1)

#: Anomalias injetaveis EM SESSAO. `health` nao esta aqui de proposito: saude do
#: ponto nao pertence a sessao nenhuma (um ponto morto nao gera sessao para
#: reclamar por ele) e e injetada na geracao de heartbeats.
ANOMALY_KINDS = ("consumption", "idle", "power_degradation", "metering")


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
    #: intensidade do que foi injetado, na unidade do limiar da regra (horas
    #: ociosas; razao de potencia). E o eixo da curva de sensibilidade.
    magnitude: float | None = None


@dataclass
class GenerationResult:
    sessions_created: int = 0
    #: o conector estava ocupado e o carro esperou a vez
    sessions_deferred: int = 0
    #: a espera passaria de `MAX_WAIT`: o morador desistiu -- demanda reprimida
    sessions_lost: int = 0
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
        spread: bool = False,
    ):
        self.condo = condominium
        self.params = params or CalibrationParams.load()
        self.rng = np.random.default_rng(seed)
        self.anomaly_rate = anomaly_rate
        # `spread=False`: anomalias NITIDAS, bem alem do limiar das regras. Serve
        # a demonstracao e ao teste de integracao ("o que e obvio e pego?").
        # `spread=True`: intensidades espalhadas, inclusive ABAIXO do limiar.
        # Serve a medicao: recall sobre anomalia que sempre ultrapassa o limiar
        # e 100% por construcao, e nao diz nada sobre onde o detector opera.
        self.spread = spread
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

    # Potencia efetiva do ponto = nominal x fator em [0,72; 0,96]: perdas e
    # limitacao do veiculo (nem todo EV aceita a potencia toda do wallbox). O
    # fator e sorteado em `_plan_session`.

    def _battery_demand(self, credential: Credential) -> tuple[float, float]:
        """Quanto a bateria aceita nesta chegada: o carro nao chega vazio."""
        vehicles = list(credential.user.vehicles.all())
        capacity = float(vehicles[0].battery_capacity_kwh) if vehicles else 50.0
        soc = float(self.rng.uniform(0.25, 0.75))
        return capacity * (1.0 - soc), capacity

    @transaction.atomic
    def generate(
        self,
        start: date,
        end: date,
        *,
        credentials: Iterable[Credential] | None = None,
        reserved: Iterable[tuple[datetime, datetime]] = (),
        heartbeats: bool = True,
    ) -> GenerationResult:
        """Gera o periodo [start, end] para todos os pontos do condominio.

        O gerador e uma FONTE como as outras: monta registros canonicos e os
        entrega ao gateway, que valida, resolve credencial e congela tarifa. A
        primeira versao gravava direto no banco -- e com isso a "ingestao
        plugavel" do projeto so era exercitada pelos testes, nunca pelo dado
        que a demonstracao mostra.

        `reserved` sao intervalos em que o conector ja esta tomado por sessoes
        que ainda vao chegar por outra fonte (o historico real do SEMS+).
        """
        result = GenerationResult()
        points = list(self.condo.charge_points.order_by("id"))
        if not points:
            raise ValueError("condominio sem ponto de recarga cadastrado")

        if credentials is None:
            credentials = Credential.objects.filter(
                user__unit__condominium=self.condo, status=Credential.Status.ACTIVE
            )
        credentials = list(
            Credential.objects.filter(pk__in=[c.pk for c in credentials])
            .select_related("user__unit").prefetch_related("user__vehicles").order_by("id")
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

        # Um conector atende um carro por vez. A primeira versao sorteava os
        # instantes de forma independente e produziu 205 pares de sessoes
        # SOBREPOSTAS em 366, num unico carregador de 7 kW: dois carros no mesmo
        # cabo. Agora cada ponto tem agenda, semeada com o que ja existe no
        # banco (as sessoes do mes ficticio) e com os intervalos reservados.
        agenda: dict[int, list[tuple[datetime, datetime]]] = {p.id: list(reserved) for p in points}
        for s_ in ChargingSession.objects.filter(charge_point__in=points, session_end__isnull=False):
            agenda[s_.charge_point_id].append((s_.session_start, s_.session_end))

        # Estado do medidor por ponto -- acumulado, como no equipamento real.
        meters = {p.id: Decimal("1000.000") for p in points}

        self._gateway = IngestionGateway(self.condo)
        self._run = IngestionRun.objects.create(
            condominium=self.condo, source="synthetic", mode=IngestionRun.Mode.FILE
        )
        self._report = IngestionReport(source="synthetic", run_id=self._run.id)

        for i, (moment, cred) in enumerate(planned):
            kind = (
                ANOMALY_KINDS[int(self.rng.integers(0, len(ANOMALY_KINDS)))]
                if i in anomaly_idx
                else None
            )
            plan = self._plan_session(cred, kind)
            slot = self._first_free_slot(agenda, points, moment, plan["plugged_hours"])
            if slot is None:
                result.sessions_lost += 1
                continue
            point, begin = slot
            if begin.astimezone(self.tz).date() > end:
                # A espera empurraria a recarga para DEPOIS do periodo pedido.
                # Sem este corte, uma sessao planejada para a noite de 31/05
                # comecava as 02h43 de 01/06 -- dentro da competencia de junho,
                # alterando a fatura de uma unidade do mes ficticio do dossie.
                result.sessions_lost += 1
                continue
            if begin > moment:
                result.sessions_deferred += 1
            session, n_readings, truth = self._build_session(point, cred, begin, meters, plan)
            agenda[point.id].append((session.session_start, session.session_end))
            result.sessions_created += 1
            result.readings_created += n_readings
            result.kwh_total += Decimal(session.energy_kwh)
            if truth:
                result.ground_truth.append(truth)

        if heartbeats:
            beats = self._heartbeats(points, start, end, result)
            TelemetryReading.objects.bulk_create(beats, batch_size=2000)
            result.readings_created += len(beats)
            # Heartbeat sintetico nao ganha um registro bruto por linha: sao
            # milhares de linhas identicas, e o diario existe para auditar o que
            # vira COBRANCA. Entra como um resumo so.
            RawEvent.objects.create(
                run=self._run, source="synthetic", outcome=RawEvent.Outcome.TELEMETRY,
                payload={"heartbeats": len(beats), "de": start.isoformat(), "ate": end.isoformat()},
            )
        self._report.readings_ingested = result.readings_created
        self._gateway.finish(self._run, self._report)
        return result

    def _first_free_slot(self, agenda, points, moment, plugged_hours):
        """O primeiro conector que libera. Devolve (ponto, inicio) ou None."""
        dur = timedelta(hours=plugged_hours)
        melhor = None
        for p in points:
            begin = moment
            for a, b in sorted(agenda[p.id]):
                if b + TURNAROUND <= begin:
                    continue
                if a >= begin + dur + TURNAROUND:
                    break
                begin = b + TURNAROUND
            if melhor is None or begin < melhor[1]:
                melhor = (p, begin)
        if melhor is None or melhor[1] - moment > MAX_WAIT:
            return None
        return melhor

    def _months_between(self, start: date, end: date) -> list[tuple[date, date]]:
        out, cur = [], date(start.year, start.month, 1)
        while cur <= end:
            nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
            out.append((max(cur, start), min(nxt - timedelta(days=1), end)))
            cur = nxt
        return out

    def _random_moment(self, start: date, end: date) -> datetime:
        """Sorteia o instante da sessao.

        O dia e ponderado pelo perfil semanal RESIDENCIAL -- premissa declarada
        da equipe, nao derivada do workplace (ver `calibration.py`). Usar o peso
        do dataset original zerava sabado e domingo, que e verdade para um
        escritorio e falso para um predio.

        A ponderacao importa: com dia uniforme o historico nao teria
        sazonalidade alguma, e um modelo de previsao treinado nele estaria
        aprendendo ruido -- foi o que o backtest acusou na primeira rodada.
        """
        span = (end - start).days
        candidates = [start + timedelta(days=i) for i in range(max(span, 1) + 1)]
        w = np.array([self.params.residential_weekday_weights[d.weekday()] for d in candidates], dtype=float)
        day = candidates[int(self.rng.choice(len(candidates), p=w / w.sum()))]
        hour = self._sample_hour()
        minute = int(self.rng.integers(0, 60))
        return datetime.combine(day, time(hour, minute), tzinfo=self.tz)

    def _plan_session(self, cred: Credential, anomaly: str | None) -> dict:
        """Sorteia a fisica da sessao ANTES de saber quando ela comeca.

        A duracao precisa existir antes do encaixe na agenda do conector; por
        isso o sorteio saiu de dentro da construcao.
        """
        plugged_hours = self._sample_duration_hours()
        power_factor = float(self.rng.uniform(0.72, 0.96))
        demand, capacity = self._battery_demand(cred)

        force_idle_hours = None
        degraded_from = None
        degraded_to = 0.35
        force_energy_factor = None
        if anomaly == "idle":
            # Carro-tampao. O tempo ocioso e fixado DEPOIS de saber quanto tempo
            # a recarga leva -- multiplicar o tempo plugado nao bastava, porque
            # a energia demandada crescia junto e a ociosidade nao aparecia.
            force_idle_hours = float(self.rng.uniform(*((1.0, 11.0) if self.spread else (5.0, 11.0))))
        elif anomaly == "power_degradation":
            degraded_from = 0.45  # a partir de 45% da sessao a potencia despenca
            degraded_to = float(self.rng.uniform(0.25, 0.90)) if self.spread else 0.35
        elif anomaly == "consumption":
            # Energia acima do que a bateria comporta -- fisicamente impossivel,
            # portanto medicao ou desvio, nunca recarga legitima.
            #
            # Aplicada na energia FINAL, e nao na demanda: aumentar a demanda so
            # fazia o `min(demanda, potencia x tempo)` truncar a anomalia de
            # volta ao normal. O gabarito acusou isso com recall zero.
            force_energy_factor = float(self.rng.uniform(1.15, 1.45))
        return {
            "anomaly": anomaly, "plugged_hours": plugged_hours, "power_factor": power_factor,
            "demand": demand, "capacity": capacity, "force_idle_hours": force_idle_hours,
            "degraded_from": degraded_from, "degraded_to": degraded_to,
            "force_energy_factor": force_energy_factor,
        }

    def _build_session(self, point, cred, start_moment, meters, plan: dict):
        """Monta a sessao canonica, com telemetria, e a entrega ao gateway."""
        anomaly = plan["anomaly"]
        plugged_hours = plan["plugged_hours"]
        power = float(point.rated_power_kw) * plan["power_factor"]
        demand, capacity = plan["demand"], plan["capacity"]
        degraded_from = plan["degraded_from"]

        charging_hours = min(demand / power, plugged_hours)
        if plan["force_idle_hours"] is not None:
            plugged_hours = min(charging_hours + plan["force_idle_hours"], 22.0)
        if degraded_from:
            full = charging_hours * degraded_from
            rest = (charging_hours - full) * 2.2   # leva mais tempo pela queda
            charging_hours = min(full + rest, plugged_hours)
            energy = full * power + (charging_hours - full) * power * plan["degraded_to"]
        else:
            energy = charging_hours * power

        if plan["force_energy_factor"] is not None:
            energy = capacity * plan["force_energy_factor"]
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

        session_end = start_moment + timedelta(hours=plugged_hours)
        readings = list(self._session_readings(
            start_moment, session_end, meter_start, power, charging_hours, degraded_from,
            plan["degraded_to"],
        ))
        canonical = CanonicalSession(
            charge_point_serial=point.serial_number,
            auth_id=cred.auth_tag,
            auth_method=(
                ChargingSession.AuthMethod.RFID
                if cred.kind == Credential.Kind.RFID
                else ChargingSession.AuthMethod.APP
            ),
            session_start=start_moment,
            session_end=session_end,
            meter_start=meter_start,
            meter_stop=None if lost_reading else meter_stop,
            energy_kwh=energy_dec,
            max_power_kw=round2(Decimal(str(power))),
            status=status,
            stop_reason=stop_reason,
            measurement_source=MeasurementSource.CLOUD,
            readings=readings,
        )
        antes = len(self._report.sessions)
        desfecho = self._gateway.process(canonical, self._run, self._report)
        if len(self._report.sessions) == antes:
            raise RuntimeError(f"gateway recusou sessao sintetica ({desfecho}): {self._report.rejections[-1:]}")
        session = self._report.sessions[-1]

        truth = None
        idle_disputado = contended_hours(
            start_moment + timedelta(hours=charging_hours), session_end, self.tz
        )
        if anomaly == "idle" and not self.spread and idle_disputado < IDLE_HOURS_THRESHOLD + 0.5:
            # A ociosidade injetada caiu no pernoite: pela politica do condominio
            # isto e um morador que deixou o carro na vaga ate de manha, nao um
            # carro-tampao. Nao entra no gabarito como anomalia.
            anomaly = None
        if anomaly:
            truth = GroundTruth(
                session_id=session.id,
                charge_point_id=None,
                category=anomaly,
                detail={
                    "consumption": f"energia {energy_dec} kWh acima da capacidade da bateria ({capacity:.1f} kWh)",
                    "idle": f"{idle_disputado:.1f} h plugado sem carregar, fora do pernoite",
                    "power_degradation": f"potencia cai a {plan['degraded_to']:.0%} no meio da sessao",
                    "metering": "leitura final do medidor perdida",
                }[anomaly],
                magnitude={
                    "idle": idle_disputado,
                    "power_degradation": plan["degraded_to"],
                }.get(anomaly),
            )
        return session, len(readings), truth

    def _session_readings(self, start, end, meter_start, power, charging_hours, degraded_from,
                          degraded_to=0.35):
        """MeterValues a cada 15 min, com a potencia caindo a zero quando a
        bateria enche -- e o sinal que a deteccao de ociosidade le."""
        t = start
        acc = Decimal(meter_start)
        charge_end = start + timedelta(hours=charging_hours)
        step_h = METER_INTERVAL.total_seconds() / 3600

        yield CanonicalReading(
            ts=t, kind=TelemetryReading.Kind.STATUS_CHANGE,
            state=TelemetryReading.State.CHARGING,
            power_kw=round2(Decimal(str(power))), energy_kwh_total=acc,
        )
        while t < end:
            t += METER_INTERVAL
            charging = t <= charge_end
            p = power
            if charging and degraded_from:
                frac = (t - start).total_seconds() / max((charge_end - start).total_seconds(), 1)
                if frac > degraded_from:
                    p = power * degraded_to
            if not charging:
                p = 0.0
            else:
                acc = acc + round3(Decimal(str(p * step_h)))
            yield CanonicalReading(
                ts=min(t, end), kind=TelemetryReading.Kind.METER_VALUE,
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
