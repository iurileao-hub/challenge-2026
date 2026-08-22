"""Testes do gateway de ingestao.

O teste que carrega o argumento do projeto e
`test_duas_fontes_diferentes_produzem_o_mesmo_tipo_de_sessao`: um JSON no
formato SEMS e um TSV de 2014 de um estacionamento americano entram pelo mesmo
cano e saem como a mesma coisa. E a diferenca entre dizer que a arquitetura e
plugavel e mostrar.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import ChargingSession, Credential, TelemetryReading
from core.scenarios import build_jardim_aurora
from ingestion.adapters import AsensioDatasetAdapter, SemsStubAdapter
from ingestion.calibration import DATASET_PATH
from ingestion.gateway import IngestionGateway

FIXTURES = Path(__file__).parent / "fixtures"
SERIAL = "57000HPA247L0002"


@pytest.fixture
def cenario(db):
    return build_jardim_aurora()


def test_adaptador_sems_mapeia_o_contrato(cenario):
    gw = IngestionGateway(cenario["condominium"])
    report = gw.ingest(SemsStubAdapter(), payload_path=FIXTURES / "sems_payload.json")

    assert report.sessions_ingested == 2
    assert report.readings_ingested == 3

    s = ChargingSession.objects.get(auth_id="RFID-ANA", session_start__month=7)
    assert s.energy_kwh == Decimal("21.350")
    assert s.meter_start == Decimal("1203.120")
    assert s.status == "completed"
    assert s.stop_reason == "Local"
    # A tarifa e congelada pelo gateway no momento da entrada (decisao 4).
    assert s.applied_tariff_kwh == Decimal("0.7252")
    assert s.credential == cenario["credentials"]["RFID-ANA"]


def test_credencial_desconhecida_vira_sessao_orfa_e_nao_e_descartada(cenario):
    """Descartar perderia consumo real; atribuir a alguem seria pior.

    A sessao entra com o auth_id BRUTO e sem credencial -- fica fora do rateio
    ate um humano vincular, e a trilha preserva o que o equipamento reportou.
    """
    gw = IngestionGateway(cenario["condominium"])
    report = gw.ingest(SemsStubAdapter(), payload_path=FIXTURES / "sems_payload.json")

    orfa = ChargingSession.objects.get(auth_id="RFID-DESCONHECIDO")
    assert orfa.credential is None
    assert orfa.energy_kwh == Decimal("12.430")
    assert "RFID-DESCONHECIDO" in report.unresolved_credentials


def test_reingestao_do_mesmo_payload_nao_duplica(cenario):
    """Deduplicacao pela chave natural do equipamento (ponto + inicio).

    Sem isto, rodar o importador duas vezes cobraria a mesma recarga duas
    vezes -- o erro mais caro que uma plataforma de rateio pode cometer.
    """
    gw = IngestionGateway(cenario["condominium"])
    gw.ingest(SemsStubAdapter(), payload_path=FIXTURES / "sems_payload.json")
    n1 = ChargingSession.objects.count()

    segundo = gw.ingest(SemsStubAdapter(), payload_path=FIXTURES / "sems_payload.json")

    assert ChargingSession.objects.count() == n1
    assert segundo.sessions_ingested == 0
    assert segundo.sessions_skipped == 2


@pytest.mark.skipif(not DATASET_PATH.exists(), reason="dataset de Asensio nao baixado")
def test_adaptador_do_dataset_real(cenario):
    gw = IngestionGateway(cenario["condominium"])
    report = gw.ingest(
        AsensioDatasetAdapter(),
        charge_point_serial=SERIAL,
        limit=50,
        shift_to="2026-07-01",
    )

    assert report.sessions_ingested == 50
    ingeridas = ChargingSession.objects.filter(auth_id__startswith="DS-")
    assert ingeridas.count() == 50
    # Dado real entra COM as sujeiras: sessoes de 0 kWh existem no dataset e
    # nao sao limpas na entrada -- limpar esconderia o que a deteccao procura.
    assert ingeridas.filter(energy_kwh=Decimal("0.000")).exists()


@pytest.mark.skipif(not DATASET_PATH.exists(), reason="dataset de Asensio nao baixado")
def test_duas_fontes_diferentes_produzem_o_mesmo_tipo_de_sessao(cenario):
    """A tese da camada de ingestao plugavel, verificada.

    Um JSON de API de fabricante chines de 2026 e um TSV academico americano de
    2014 nao tem um campo em comum. Depois do gateway, sao indistinguiveis para
    o motor de rateio.
    """
    gw = IngestionGateway(cenario["condominium"])
    gw.ingest(SemsStubAdapter(), payload_path=FIXTURES / "sems_payload.json")
    gw.ingest(AsensioDatasetAdapter(), charge_point_serial=SERIAL, limit=20, shift_to="2026-08-01")

    do_sems = ChargingSession.objects.get(auth_id="RFID-ANA", session_start__month=7)
    do_dataset = ChargingSession.objects.filter(auth_id__startswith="DS-").first()

    for s in (do_sems, do_dataset):
        assert s.charge_point.serial_number == SERIAL
        assert isinstance(s.energy_kwh, Decimal)
        assert s.applied_tariff_kwh == Decimal("0.7252")
        assert s.measurement_source == "cloud"
        assert s.status in ("completed", "interrupted", "fault", "in_progress")
