"""Adaptador de FLUXO DE EVENTOS -- a forma que dado operacional tem de verdade.

Os outros adaptadores recebem a sessao pronta, do inicio ao fim. Nenhuma das
integracoes realistas entrega assim. Webhook da nuvem GoodWe, gateway de borda
lendo Modbus na garagem e carregador OCPP falam a mesma lingua: **eventos**, um
por vez, na ordem em que as coisas acontecem -- e, com rede de garagem, as vezes
fora dela.

    session_started  ->  meter_value*  ->  session_ended
    (StartTransaction)   (MeterValues)    (StopTransaction)

mais `status` e `heartbeat`, que chegam com ou sem sessao aberta.

Este e o contrato que a plataforma PROPOE a quem for entregar o dado (a
especificacao completa, com exemplos, esta em
`docs/sprint2-ingestao-e-integracao.md`). Um evento e um objeto JSON:

    event_id            id unico da entrega (chave de idempotencia do transporte)
    type                session_started | meter_value | session_ended | status | heartbeat
    charge_point        numero de serie do carregador
    ts                  ISO 8601 COM offset (evento sem fuso e recusado)
    transaction_id      id da transacao na fonte; liga started/ended
    auth_id             cartao ou conta (em session_started)
    auth_method         rfid | app
    meter_kwh           medidor acumulado, se a fonte tiver
    energy_kwh          energia da sessao (em session_ended; senao, deriva do medidor)
    power_kw, state     telemetria instantanea
    stop_reason         vocabulario OCPP (Local, EVDisconnected, PowerLoss...)
    measurement_source  cloud | modbus_local | mid_meter

O adaptador nao guarda estado entre entregas. O estado e o banco: `session_started`
cria a sessao `in_progress`; `session_ended` a encerra pelo `transaction_id`; o
gateway cuida do resto (congelar tarifa, deduplicar, anexar telemetria). E por
isso que reentregar um lote inteiro e inofensivo -- inclusive para quem o
reenviar de ma-fe.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core.models import ChargingSession, MeasurementSource
from ingestion.gateway import (
    CanonicalReading,
    CanonicalSession,
    CanonicalTelemetry,
    SourceAdapter,
)
from ingestion.models import IngestionRun

#: Dentro do mesmo instante, a ordem logica desempata: abrir antes de medir,
#: medir antes de fechar.
_ORDER = {"session_started": 0, "status": 1, "heartbeat": 1, "meter_value": 2, "session_ended": 3}

_TELEMETRY_KIND = {
    "meter_value": "meter_value",
    "status": "status_change",
    "heartbeat": "heartbeat",
}


def _dec(value) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _ts(value) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"instante sem offset de fuso: {value!r}")
    return dt


class EventStreamAdapter(SourceAdapter):
    mode = IngestionRun.Mode.PUSH

    def __init__(self, events: list[dict], source: str = "event_push"):
        super().__init__()
        self.name = source
        self.events = events

    def ref_of(self, raw: dict) -> str | None:
        tx = raw.get("transaction_id")
        return f"{self.name}:{tx}" if tx else None

    def iter_raw(self, *, since: str | None = None, **kwargs):
        def chave(ev):
            try:
                return (0, _ts(ev.get("ts")), _ORDER.get(ev.get("type"), 9))
            except (ValueError, TypeError, AttributeError):
                # Evento sem instante legivel vai para o fim: sera recusado em
                # `to_canonical`, e nao pode atrapalhar a ordenacao dos bons.
                return (1, datetime.max, 9)

        yield from sorted((e for e in self.events if isinstance(e, dict)), key=chave)
        for lixo in (e for e in self.events if not isinstance(e, dict)):
            yield lixo

    def to_canonical(self, ev: dict):
        kind = ev.get("type")
        serial = str(ev["charge_point"])
        ts = _ts(ev["ts"])
        msource = ev.get("measurement_source") or MeasurementSource.CLOUD

        if kind in _TELEMETRY_KIND:
            return CanonicalTelemetry(
                charge_point_serial=serial,
                measurement_source=msource,
                reading=CanonicalReading(
                    ts=ts, kind=_TELEMETRY_KIND[kind], state=ev.get("state"),
                    power_kw=_dec(ev.get("power_kw")),
                    energy_kwh_total=_dec(ev.get("meter_kwh")),
                ),
            )

        if kind == "session_started":
            if not ev.get("transaction_id"):
                raise ValueError("session_started sem transaction_id: nao ha como encerra-la depois")
            return CanonicalSession(
                charge_point_serial=serial,
                auth_id=str(ev.get("auth_id") or "").strip(),
                auth_method=ev.get("auth_method") or "rfid",
                session_start=ts, session_end=None,
                energy_kwh=Decimal("0.000"),
                meter_start=_dec(ev.get("meter_kwh")),
                status="in_progress",
                measurement_source=msource,
                source_ref=self.ref_of(ev),
            )

        if kind == "session_ended":
            aberta = ChargingSession.objects.filter(
                source=self.name, source_ref=self.ref_of(ev)
            ).first() if ev.get("transaction_id") else None
            if aberta is None and not ev.get("session_start"):
                raise ValueError(
                    f"session_ended da transacao {ev.get('transaction_id')!r} sem session_started "
                    "conhecido: fica na quarentena ate o inicio chegar (ou o pull de reconciliacao trazer a sessao)"
                )
            start = aberta.session_start if aberta else _ts(ev["session_start"])
            meter_start = aberta.meter_start if aberta else _dec(ev.get("meter_start_kwh"))
            meter_stop = _dec(ev.get("meter_kwh"))
            energy = _dec(ev.get("energy_kwh"))
            if energy is None:
                if meter_start is None or meter_stop is None:
                    raise ValueError("session_ended sem energy_kwh e sem medidor para deriva-la")
                energy = meter_stop - meter_start
            motivo = ev.get("stop_reason")
            return CanonicalSession(
                charge_point_serial=serial,
                auth_id=(aberta.auth_id if aberta else str(ev.get("auth_id") or "")).strip(),
                auth_method=(aberta.auth_method if aberta else ev.get("auth_method") or "rfid"),
                session_start=start, session_end=ts,
                energy_kwh=energy, meter_start=meter_start, meter_stop=meter_stop,
                max_power_kw=_dec(ev.get("max_power_kw")),
                status="interrupted" if motivo in ("PowerLoss", "EmergencyStop") else "completed",
                stop_reason=motivo,
                measurement_source=msource,
                source_ref=self.ref_of(ev),
            )

        raise ValueError(f"tipo de evento desconhecido: {kind!r}")
