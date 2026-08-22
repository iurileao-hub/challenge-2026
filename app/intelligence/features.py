"""Extracao de features das sessoes.

Um lugar so para derivar features, usado pelas duas abordagens de IA e pela
avaliacao. Se a definicao de "ociosidade" mudar, muda aqui e vale para o
detector, para a metrica e para o painel -- e o que impede a plataforma de ter
tres numeros diferentes para a mesma palavra.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
from django.db.models import Max, Q

from billing.competence import condo_tz
from core.models import ChargingSession, TelemetryReading


@dataclass
class SessionFeatures:
    session_id: int
    credential_id: int | None
    unit_label: str | None
    start_hour: int
    weekday: int
    energy_kwh: float
    plugged_hours: float
    charging_hours: float
    idle_hours: float
    kwh_per_hour: float
    max_power_kw: float
    power_ratio: float          # potencia observada / nominal do ponto
    battery_capacity_kwh: float
    energy_over_battery: float  # > 1 e fisicamente impossivel
    meter_consistent: bool
    second_half_power_ratio: float  # potencia da 2a metade / 1a metade
    has_telemetry: bool = True      # False = nao ha base para julgar ociosidade


def _charging_end(session: ChargingSession):
    """Ultimo instante com potencia > 0 -- a fronteira entre carregar e ocupar
    a vaga. Vem da telemetria, nao da sessao: e a diferenca entre o que o
    equipamento fez e o que o usuario declarou.

    Devolve `(instante, houve_telemetria)`. A segunda parte importa mais do que
    parece: **ausencia de telemetria nao e evidencia de ociosidade**. Um
    carregador que nao reporta MeterValues e caso comum -- o proprio HCA G2 so
    fala Modbus TCP -- e tratar silencio como prova acusaria o morador de
    ocupar a vaga por um defeito do equipamento. Sem base, o detector se abstem.
    """
    tem_leitura = TelemetryReading.objects.filter(session=session).exists()
    if not tem_leitura:
        return session.session_end or session.session_start, False
    last = (
        TelemetryReading.objects.filter(session=session, power_kw__gt=0)
        .aggregate(last=Max("ts"))["last"]
    )
    return (last or session.session_start), True


def _half_power_ratio(session: ChargingSession) -> float:
    """Razao entre a potencia media da segunda metade e a da primeira.

    Perto de 1 = entrega estavel. Bem abaixo de 1 = degradacao ao longo da
    sessao, que e o sinal de cabo/conector/contator em fim de vida (o caso
    Copel: o equipamento entregando menos do que promete, silenciosamente).
    """
    readings = list(
        TelemetryReading.objects.filter(
            session=session, kind=TelemetryReading.Kind.METER_VALUE, power_kw__gt=0
        ).order_by("ts").values_list("power_kw", flat=True)
    )
    if len(readings) < 4:
        return 1.0
    mid = len(readings) // 2
    first = sum(float(p) for p in readings[:mid]) / mid
    second = sum(float(p) for p in readings[mid:]) / (len(readings) - mid)
    return second / first if first > 0 else 1.0


def extract(sessions) -> list[SessionFeatures]:
    tz = condo_tz()
    out = []
    for s in sessions:
        local = s.session_start.astimezone(tz)
        plugged = s.duration_hours or 0.0
        charge_end, tem_telemetria = _charging_end(s)
        charging = max((charge_end - s.session_start).total_seconds() / 3600, 0.0)
        energy = float(s.energy_kwh)
        vehicles = list(s.credential.user.vehicles.all()) if s.credential else []
        capacity = float(vehicles[0].battery_capacity_kwh) if vehicles else 0.0
        nominal = float(s.charge_point.rated_power_kw) or 1.0
        max_power = float(s.max_power_kw or 0)

        meter_ok = True
        if s.meter_stop is not None:
            meter_ok = abs((Decimal(s.meter_stop) - Decimal(s.meter_start)) - Decimal(s.energy_kwh)) <= Decimal("0.05")

        out.append(
            SessionFeatures(
                session_id=s.id,
                credential_id=s.credential_id,
                unit_label=(s.credential.user.unit.label if s.credential and s.credential.user.unit else None),
                start_hour=local.hour,
                weekday=local.weekday(),
                energy_kwh=energy,
                plugged_hours=plugged,
                charging_hours=charging,
                idle_hours=max(plugged - charging, 0.0),
                kwh_per_hour=(energy / charging if charging > 0.05 else 0.0),
                max_power_kw=max_power,
                power_ratio=(max_power / nominal if nominal else 0.0),
                battery_capacity_kwh=capacity,
                energy_over_battery=(energy / capacity if capacity > 0 else 0.0),
                meter_consistent=meter_ok,
                second_half_power_ratio=_half_power_ratio(s),
                has_telemetry=tem_telemetria,
            )
        )
    return out


def to_frame(features: list[SessionFeatures]) -> pd.DataFrame:
    return pd.DataFrame([f.__dict__ for f in features])
