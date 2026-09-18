"""O que o gateway garante quando a fonte se comporta como fonte de verdade.

Cada teste aqui nasceu de um defeito REPRODUZIDO na primeira versao do gateway,
ou de uma propriedade que as arquiteturas de integracao propostas em
`docs/sprint2-ingestao-e-integracao.md` exigem. O nome do teste e a garantia.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction

from billing.competence import Competence
from billing.engine import close_competence
from core.models import (
    ChargePoint,
    ChargingSession,
    Credential,
    ProgramEnrollment,
    TariffPeriod,
    TelemetryReading,
)
from core.scenarios import build_jardim_aurora
from ingestion.adapters import EventStreamAdapter, SemsPlusLogAdapter, SemsStubAdapter
from ingestion.gateway import CanonicalSession, IngestionGateway
from ingestion.models import IngestionRun, RawEvent
from ingestion.replay import replay_quarantine
from ingestion.views import sign

BRT = ZoneInfo("America/Sao_Paulo")
SERIAL = "57000HPA247L0002"


@pytest.fixture
def cenario(db):
    return build_jardim_aurora()


@pytest.fixture
def gw(cenario):
    return IngestionGateway(cenario["condominium"])


def _payload(tmp_path, records):
    p = tmp_path / "sems.json"
    p.write_text(json.dumps({"code": 0, "data": {"records": records}}))
    return p


def _rec(**over):
    rec = {
        "id": "EVC-1", "sn": SERIAL, "card_no": "RFID-ANA",
        "start_time": "2026-07-10T20:00:00", "end_time": "2026-07-10T23:00:00",
        "start_kwh": 2000.0, "end_kwh": 2015.5, "charge_kwh": 15.5,
        "max_power": 6.9, "stop_reason": "Local",
    }
    rec.update(over)
    return rec


# --------------------------------------------------------------- ciclo de vida

def test_sessao_em_andamento_e_encerrada_pela_entrega_seguinte(gw, tmp_path):
    """Na v1 a segunda entrega era descartada como duplicata: a sessao ficava
    `in_progress` para sempre, fora do rateio, e o kWh nunca era cobrado."""
    aberta = _rec(end_time=None, end_kwh=None, charge_kwh=4.2, stop_reason=None)
    gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, [aberta]))
    s = ChargingSession.objects.get(source_ref="sems:EVC-1")
    assert s.status == "in_progress"
    assert s.applied_tariff_kwh is None

    r = gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, [_rec()]))

    s.refresh_from_db()
    assert (r.created, r.updated, r.duplicates) == (0, 1, 0)
    assert s.status == "completed"
    assert s.energy_kwh == Decimal("15.500")
    assert s.meter_stop == Decimal("2015.500")
    # A tarifa congela quando a sessao ENCERRA na plataforma, nao quando abre.
    assert s.applied_tariff_kwh == Decimal("0.7252")
    assert ChargingSession.objects.filter(charge_point__serial_number=SERIAL,
                                          session_start=s.session_start).count() == 1


def test_sessao_de_tarifa_ja_encerrada_recebe_a_vigencia_da_sua_data(cenario, gw, tmp_path):
    """Backfill depois de um reajuste. A v1 so enxergava a vigencia ABERTA:
    a sessao antiga saia sem tarifa, violava o CHECK e derrubava o lote."""
    antiga = TariffPeriod.objects.get(condominium=cenario["condominium"])
    antiga.valid_to = date(2026, 7, 31)
    antiga.save()
    TariffPeriod.objects.create(
        condominium=cenario["condominium"], price_kwh=Decimal("0.8100"),
        availability_fee_month=Decimal("180.00"), basis="reajuste ago/2026",
        valid_from=date(2026, 8, 1),
    )
    recs = [
        _rec(id="JUL", start_time="2026-07-31T22:00:00", end_time="2026-07-31T23:30:00"),
        _rec(id="AGO", start_time="2026-08-01T22:00:00", end_time="2026-08-01T23:30:00",
             start_kwh=2015.5, end_kwh=2031.0),
    ]
    r = gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, recs))

    assert r.created == 2 and r.rejected == 0
    assert ChargingSession.objects.get(source_ref="sems:JUL").applied_tariff_kwh == Decimal("0.7252")
    assert ChargingSession.objects.get(source_ref="sems:AGO").applied_tariff_kwh == Decimal("0.8100")


# ---------------------------------------------------- isolamento e quarentena

def test_um_registro_torto_nao_derruba_os_outros(gw, tmp_path):
    recs = [
        _rec(id="BOM-1"),
        {"id": "SEM-SERIAL", "card_no": "X", "start_time": "2026-07-11T10:00:00"},
        _rec(id="FIM-ANTES", start_time="2026-07-12T20:00:00", end_time="2026-07-12T19:00:00"),
        _rec(id="DATA-LIXO", start_time="ontem a noite"),
        _rec(id="FUTURO", start_time="2031-01-01T10:00:00", end_time="2031-01-01T11:00:00"),
        _rec(id="BOM-2", start_time="2026-07-13T20:00:00", end_time="2026-07-13T22:00:00",
             start_kwh=2015.5, end_kwh=2025.5, charge_kwh=10.0),
    ]
    r = gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, recs))

    assert (r.received, r.created, r.rejected) == (6, 2, 4)
    run = IngestionRun.objects.get(pk=r.run_id)
    assert run.status == IngestionRun.Status.PARTIAL
    recusados = RawEvent.objects.filter(run=run, outcome="rejected")
    # Nada se perde: o registro fica guardado COMO CHEGOU, com motivo legivel.
    assert {e.payload.get("id") for e in recusados} == {"SEM-SERIAL", "FIM-ANTES", "DATA-LIXO", "FUTURO"}
    assert all(e.reason for e in recusados)
    assert "anterior ao inicio" in recusados.get(payload__id="FIM-ANTES").reason


def test_carregador_desconhecido_vai_para_quarentena_e_volta_no_replay(cenario, gw, tmp_path):
    """Na v1 contava como "sessao ja existente" e sumia. Agora espera o cadastro."""
    r = gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, [_rec(sn="SN-NOVO")]))
    assert (r.created, r.unknown_point, r.duplicates) == (0, 1, 0)
    assert not ChargingSession.objects.filter(source_ref="sems:EVC-1").exists()

    ChargePoint.objects.create(
        condominium=cenario["condominium"], serial_number="SN-NOVO", model="HCA G2 11 kW",
        location="G2 vaga 14", rated_power_kw=Decimal("11.00"), commissioned_at=date(2026, 7, 1),
    )
    (rep,) = replay_quarantine(cenario["condominium"])

    assert rep.created == 1
    assert ChargingSession.objects.get(source_ref="sems:EVC-1").charge_point.serial_number == "SN-NOVO"
    assert RawEvent.objects.get(outcome="unknown_point").resolved_at is not None
    assert replay_quarantine(cenario["condominium"]) == []   # nao ha mais o que reprocessar


def test_sessao_sem_vigencia_de_tarifa_espera_na_quarentena(gw, tmp_path):
    rec = _rec(start_time="2025-12-30T20:00:00", end_time="2025-12-30T22:00:00")
    r = gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, [rec]))
    assert r.rejected == 1
    assert "vigencia de tarifa" in r.rejections[0]


def test_horario_com_offset_explicito_e_respeitado(gw, tmp_path):
    """A v1 fazia `replace(tzinfo=BRT)` incondicional: um `Z` virava BRT sem
    converter -- tres horas de erro, o bastante para trocar a competencia."""
    rec = _rec(start_time="2026-07-01T01:30:00Z", end_time="2026-07-01T03:00:00Z")
    gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, [rec]))
    s = ChargingSession.objects.get(source_ref="sems:EVC-1")
    assert s.session_start == datetime(2026, 6, 30, 22, 30, tzinfo=BRT)
    assert Competence.of(s.session_start) == Competence.parse("2026-06")


# ---------------------------------------------------------------- idempotencia

def test_pull_incremental_so_traz_o_que_e_novo(gw, tmp_path):
    dia1 = [_rec(id="A")]
    dia2 = dia1 + [_rec(id="B", start_time="2026-07-11T20:00:00", end_time="2026-07-11T22:00:00",
                        start_kwh=2015.5, end_kwh=2025.5, charge_kwh=10.0)]
    r1 = gw.ingest(SemsStubAdapter(), resume=True, payload_path=_payload(tmp_path, dia1))
    r2 = gw.ingest(SemsStubAdapter(), resume=True, payload_path=_payload(tmp_path, dia2))

    assert (r1.received, r1.created) == (1, 1)
    assert (r2.received, r2.created, r2.duplicates) == (1, 1, 0)   # "A" nem foi relido
    run2 = IngestionRun.objects.get(pk=r2.run_id)
    assert run2.cursor_before == IngestionRun.objects.get(pk=r1.run_id).cursor_after
    assert run2.cursor_after > run2.cursor_before


def test_chave_natural_e_garantida_pelo_banco_e_nao_so_pelo_codigo(cenario):
    """Duas entregas simultaneas do mesmo evento passam as duas pelo
    "ja existe?". Quem decide a corrida e o UNIQUE do Postgres."""
    s = next(iter(cenario["sessions"].values()))
    with pytest.raises(IntegrityError), transaction.atomic():
        ChargingSession.objects.create(
            charge_point=s.charge_point, auth_id="X", auth_method="rfid",
            session_start=s.session_start, energy_kwh=Decimal("1"), status="in_progress",
        )


def test_mesma_sessao_por_duas_fontes_nao_cobra_duas_vezes(gw, tmp_path):
    """Nuvem e borda descrevem a mesma recarga com relogios que divergem em
    segundos, e ids diferentes. E uma sessao so -- e vale a medicao de maior
    lastro metrologico (Frente 2: medidor MID > Modbus local > nuvem)."""
    gw.ingest(SemsStubAdapter(), payload_path=_payload(tmp_path, [_rec()]))
    evento = {
        "type": "session_ended", "charge_point": SERIAL, "transaction_id": "tx-77",
        "session_start": "2026-07-10T20:00:41-03:00", "ts": "2026-07-10T23:00:10-03:00",
        "auth_id": "RFID-ANA", "energy_kwh": 15.31, "measurement_source": "mid_meter",
    }
    r = gw.ingest(EventStreamAdapter([evento], source="edge_gateway"))

    assert (r.created, r.updated) == (0, 1)
    s = ChargingSession.objects.get(source_ref="sems:EVC-1")
    assert s.energy_kwh == Decimal("15.310")
    assert s.measurement_source == "mid_meter"
    assert "cloud -> mid_meter" in RawEvent.objects.get(run_id=r.run_id).reason


def test_fatura_fechada_nao_e_reescrita_por_correcao_tardia_da_fonte(cenario, gw):
    """Imutabilidade do fechamento vale tambem contra a propria ingestao."""
    close_competence(cenario["condominium"], Competence.parse("2026-06"), force=True)
    alvo = ChargingSession.objects.filter(
        invoice_lines__invoice__status="closed"
    ).first()
    assert alvo is not None
    antes = alvo.energy_kwh
    evento = {
        "type": "session_ended", "charge_point": SERIAL, "transaction_id": "tx-tardia",
        "session_start": alvo.session_start.isoformat(),
        "ts": alvo.session_end.isoformat(), "auth_id": alvo.auth_id,
        "energy_kwh": float(antes) + 3, "measurement_source": "mid_meter",
    }
    r = gw.ingest(EventStreamAdapter([evento], source="edge_gateway"))

    alvo.refresh_from_db()
    assert alvo.energy_kwh == antes
    assert r.conflicts == 1
    assert "nao se reescreve" in RawEvent.objects.get(run_id=r.run_id).reason


# ------------------------------------------------------------ fluxo de eventos

def _fluxo(tx="tx-1", auth="RFID-CARLA"):
    return [
        {"type": "session_started", "charge_point": SERIAL, "transaction_id": tx,
         "ts": "2026-07-15T19:00:00-03:00", "auth_id": auth, "meter_kwh": 3000.0},
        {"type": "meter_value", "charge_point": SERIAL, "ts": "2026-07-15T19:15:00-03:00",
         "power_kw": 6.9, "meter_kwh": 3001.7, "state": "charging"},
        {"type": "meter_value", "charge_point": SERIAL, "ts": "2026-07-15T20:00:00-03:00",
         "power_kw": 6.8, "meter_kwh": 3006.9, "state": "charging"},
        {"type": "session_ended", "charge_point": SERIAL, "transaction_id": tx,
         "ts": "2026-07-15T21:30:00-03:00", "meter_kwh": 3017.1, "stop_reason": "EVDisconnected"},
        {"type": "heartbeat", "charge_point": SERIAL, "ts": "2026-07-15T22:00:00-03:00"},
    ]


def test_eventos_fora_de_ordem_e_repetidos_montam_uma_sessao_so(cenario):
    gw = IngestionGateway()   # push: o condominio se descobre pelo numero de serie
    ev = _fluxo()
    embaralhado = [ev[3], ev[1], ev[0], ev[4], ev[2], ev[1], ev[0]]

    r = gw.ingest(EventStreamAdapter(embaralhado, source="goodwe_push"))

    s = ChargingSession.objects.get(source="goodwe_push", source_ref="goodwe_push:tx-1")
    assert s.status == "completed" and s.stop_reason == "EVDisconnected"
    assert s.energy_kwh == Decimal("17.100")           # derivada do medidor: 3017.1 - 3000.0
    assert s.credential == cenario["credentials"]["RFID-CARLA"]
    assert s.applied_tariff_kwh == Decimal("0.7252")
    assert s.readings.count() == 2                     # as duas leituras, sem a repetida
    fora = TelemetryReading.objects.get(kind="heartbeat", ts__hour=1)   # 22h BRT = 01h UTC
    assert fora.session is None                        # heartbeat depois do fim: fora de sessao
    assert r.rejected == 0

    de_novo = gw.ingest(EventStreamAdapter(ev, source="goodwe_push"))
    assert (de_novo.created, de_novo.updated, de_novo.readings_ingested) == (0, 0, 0)
    assert de_novo.duplicates == len(ev)


def test_fim_que_chega_antes_do_inicio_espera_e_se_resolve(cenario):
    gw = IngestionGateway()
    ev = _fluxo(tx="tx-2")
    r1 = gw.ingest(EventStreamAdapter([ev[3]], source="goodwe_push"))
    assert r1.rejected == 1 and "sem session_started" in r1.rejections[0]

    gw.ingest(EventStreamAdapter([ev[0]], source="goodwe_push"))
    assert ChargingSession.objects.get(source_ref="goodwe_push:tx-2").status == "in_progress"

    replay_quarantine()
    assert ChargingSession.objects.get(source_ref="goodwe_push:tx-2").status == "completed"


# ---------------------------------------------------------------- dado real

def test_as_18_sessoes_reais_do_hca_g2_atravessam_o_gateway(cenario, gw):
    """O limite declarado da Sprint 2, fechado: dado real de um HCA G2."""
    r = gw.ingest(SemsPlusLogAdapter())

    reais = ChargingSession.objects.filter(source="semsplus_log")
    assert (r.received, r.created, r.rejected) == (18, 18, 0)
    assert sum(s.energy_kwh for s in reais) == Decimal("136.660")     # o total do dossie
    assert reais.filter(energy_kwh=0).count() == 1                    # a sessao #8, como veio
    # A fonte nao reporta medidor: nulo declarado, e NAO "leitura final perdida".
    assert all(s.meter_start is None and not s.final_reading_lost for s in reais)
    # Auto-start: o cartao e o proprio numero de serie. Ninguem se identificou.
    assert all(s.credential is None and s.auth_id == SERIAL for s in reais)

    assert gw.ingest(SemsPlusLogAdapter()).duplicates == 18


def test_sessao_orfa_real_nao_entra_no_rateio_nem_retem_fatura(cenario, gw):
    """Energia que ninguem assumiu nao pode ser cobrada de quem se identificou."""
    antes = close_competence(cenario["condominium"], Competence.parse("2026-06"), force=True)
    gw.ingest(SemsPlusLogAdapter())
    depois = close_competence(cenario["condominium"], Competence.parse("2026-06"), force=True)
    assert depois.total_billed == antes.total_billed
    assert depois.kwh_total == antes.kwh_total


# --------------------------------------------------------------------- push

@pytest.fixture
def push(client, settings):
    settings.INGEST_PUSH_SECRETS = {"goodwe_push": "segredo-de-teste"}

    def _post(body, secret="segredo-de-teste", source="goodwe_push"):
        raw = json.dumps(body).encode()
        return client.post(
            f"/api/v1/ingest/{source}/", data=raw, content_type="application/json",
            headers={"X-ChargeOps-Signature": sign(raw, secret)},
        )
    return _post


def test_push_assinado_entra_e_assinatura_errada_nao(cenario, push):
    assert push({"events": _fluxo(tx="tx-9")}, secret="chute").status_code == 401
    assert not ChargingSession.objects.filter(source="goodwe_push").exists()

    resp = push({"events": _fluxo(tx="tx-9")})
    assert resp.status_code == 200
    assert resp.json()["created"] == 1 and resp.json()["quarantined"] == 0
    assert ChargingSession.objects.get(source_ref="goodwe_push:tx-9").status == "completed"


def test_push_de_fonte_sem_segredo_configurado_fica_desligado(cenario, push):
    assert push({"events": []}, source="fonte-qualquer").status_code == 503


def test_push_com_lixo_responde_200_e_guarda_o_lixo(cenario, push):
    """4xx faria a fonte reenviar para sempre um lote que nunca vai passar."""
    resp = push({"events": [{"type": "explodiu"}, "nem objeto", _fluxo()[4]]})
    assert resp.status_code == 200
    assert resp.json()["quarantined"] == 2 and resp.json()["telemetry"] == 1


# ---------------------------------------------------- invariantes de banco

def test_invariantes_de_banco_vigencias_nao_se_sobrepoem(cenario):
    """A migracao 0003 (autogerada) tinha REMOVIDO estas constraints sem que
    ninguem notasse, porque nenhum teste tentava viola-las. Este tenta."""
    condo = cenario["condominium"]
    with pytest.raises(IntegrityError), transaction.atomic():
        TariffPeriod.objects.create(
            condominium=condo, price_kwh=Decimal("0.9"), availability_fee_month=Decimal("1"),
            basis="sobreposta", valid_from=date(2026, 5, 1),
        )
    unit = ProgramEnrollment.objects.first().unit
    with pytest.raises(IntegrityError), transaction.atomic():
        ProgramEnrollment.objects.create(unit=unit, start_date=date(2026, 6, 1))


def test_vigencia_que_termina_no_dia_em_que_a_outra_comeca_e_recusada(cenario):
    """Intervalo FECHADO: `valid_to` e inclusivo no motor, tem de ser no banco."""
    t = TariffPeriod.objects.get(condominium=cenario["condominium"])
    t.valid_to = date(2026, 7, 10)
    t.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        TariffPeriod.objects.create(
            condominium=cenario["condominium"], price_kwh=Decimal("0.9"),
            availability_fee_month=Decimal("1"), basis="mesmo dia", valid_from=date(2026, 7, 10),
        )
    TariffPeriod.objects.create(
        condominium=cenario["condominium"], price_kwh=Decimal("0.9"),
        availability_fee_month=Decimal("1"), basis="dia seguinte", valid_from=date(2026, 7, 11),
    )
