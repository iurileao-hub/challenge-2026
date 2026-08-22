"""Testes da deteccao de anomalias.

O teste central deste arquivo nao e "o detector acha anomalia" -- e
`test_anomalia_aberta_marca_a_linha_e_segura_a_fatura`, que prova a afirmacao
da Sprint 1 de que a IA e **estrutural**: ela se interpoe entre a sessao e o
fechamento da fatura. Se alguem remover a deteccao, esse teste quebra por
quebrar o ciclo de estados da fatura -- que e a definicao operacional de "nao
decorativa".
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from billing.competence import Competence
from billing.engine import close_competence
from core.models import AnomalyFlag, ChargingSession, Invoice, InvoiceLine, TelemetryReading
from core.scenarios import build_jardim_aurora
from ingestion.generator import SyntheticGenerator
from intelligence.anomalies import (
    IDLE_HOURS_THRESHOLD,
    detect_point_health,
    run_detection,
)
from intelligence.evaluation import evaluate

BRT = ZoneInfo("America/Sao_Paulo")
JUNHO = Competence(2026, 6)


@pytest.fixture
def cenario(db):
    return build_jardim_aurora()


def janela(inicio: date, fim: date):
    return (
        datetime.combine(inicio, time.min, tzinfo=BRT),
        datetime.combine(fim, time.max, tzinfo=BRT),
    )


# --------------------------------------------------------------------------
# A tese: IA estrutural, nao decorativa
# --------------------------------------------------------------------------

def test_anomalia_aberta_marca_a_linha_e_segura_a_fatura(cenario):
    """A deteccao roda ANTES do fechamento e muda o resultado do fechamento.

    Este e o teste que sustenta a afirmacao de que a IA e estrutural: remover a
    deteccao nao apagaria um grafico -- deixaria a fatura fechar sem auditoria.
    """
    sessao = cenario["sessions"][1003]   # 40 kWh, unidade 105, sem problema aparente
    AnomalyFlag.objects.create(
        session=sessao,
        category=AnomalyFlag.Category.CONSUMPTION,
        explanation="consumo atipico para esta credencial",
        status=AnomalyFlag.Status.OPEN,
    )

    close_competence(cenario["condominium"], JUNHO)
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))
    linha = inv.lines.get(session=sessao)

    assert linha.flagged_for_audit is True
    assert inv.status == Invoice.Status.UNDER_REVIEW
    # E o valor NAO muda: a IA produz evidencia, nao altera cobranca.
    assert linha.amount == Decimal("29.01")
    assert inv.total_amount == Decimal("72.33")


def test_anomalia_ja_revisada_nao_segura_a_fatura(cenario):
    """Flag descartada pelo humano deixa de bloquear -- quem decide e a pessoa."""
    AnomalyFlag.objects.create(
        session=cenario["sessions"][1003],
        category=AnomalyFlag.Category.CONSUMPTION,
        explanation="revisada e descartada pelo sindico",
        status=AnomalyFlag.Status.DISMISSED,
        reviewed_by_user=cenario["users"]["gestor"],
    )
    close_competence(cenario["condominium"], JUNHO)
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))

    assert inv.lines.get(session=cenario["sessions"][1003]).flagged_for_audit is False
    assert inv.status == Invoice.Status.CLOSED


def test_sessao_sem_leitura_final_vai_para_auditoria_sem_precisar_de_ia(cenario):
    """A auditoria por telemetria perdida e regra do motor, nao da IA -- o
    caminho existe mesmo com a deteccao desligada."""
    close_competence(cenario["condominium"], JUNHO)
    linha = InvoiceLine.objects.get(session=cenario["sessions"][1005])

    assert linha.flagged_for_audit is True
    assert AnomalyFlag.objects.count() == 0


# --------------------------------------------------------------------------
# Regras da fase 1
# --------------------------------------------------------------------------

def test_regra_pega_energia_acima_da_bateria(cenario):
    """Sessao com mais kWh do que a bateria comporta e impossivel, nao alta."""
    s = cenario["sessions"][1003]
    s.energy_kwh = Decimal("120.000")   # Davi tem BYD Seal de 82,5 kWh
    s.save(update_fields=["energy_kwh"])

    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)
    flag = AnomalyFlag.objects.get(session=s, category="consumption")

    assert "impossivel" in flag.explanation
    assert "82" in flag.explanation          # cita a capacidade cadastrada
    assert flag.detector == "rule"
    assert flag.status == AnomalyFlag.Status.OPEN


def test_regra_pega_ociosidade_com_base_na_telemetria(cenario):
    """Ociosidade sai da telemetria (quando a potencia zerou), nao da sessao."""
    s = cenario["sessions"][1001]
    inicio = s.session_start
    # Carregou 1 h, ficou plugado ate o fim (quase 8 h) -- carro-tampao.
    TelemetryReading.objects.create(
        charge_point=s.charge_point, session=s, ts=inicio + timedelta(hours=1),
        kind=TelemetryReading.Kind.METER_VALUE,
        state=TelemetryReading.State.CHARGING, power_kw=Decimal("7.00"),
        energy_kwh_total=Decimal("1007.000"),
    )
    TelemetryReading.objects.create(
        charge_point=s.charge_point, session=s, ts=inicio + timedelta(hours=2),
        kind=TelemetryReading.Kind.METER_VALUE,
        state=TelemetryReading.State.FINISHED, power_kw=Decimal("0.00"),
        energy_kwh_total=Decimal("1018.400"),
    )

    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)
    flag = AnomalyFlag.objects.get(session=s, category="idle")

    assert "conectado apos concluir" in flag.explanation
    assert s.duration_hours - 1 > IDLE_HOURS_THRESHOLD


def test_regra_pega_leitura_perdida(cenario):
    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)
    flag = AnomalyFlag.objects.get(session=cenario["sessions"][1005], category="metering")

    assert "ultima leitura periodica" in flag.explanation
    assert "conservador" in flag.explanation


def test_saude_do_ponto_vem_da_ausencia_de_heartbeat(cenario):
    """O sinal de ponto morto e a AUSENCIA de dado -- por isso a telemetria
    precisa existir fora de sessao."""
    ponto = cenario["charge_point"]
    t = datetime(2026, 6, 1, 0, 0, tzinfo=BRT)
    for i in range(48):
        # Buraco de 8 h no meio da serie.
        if 10 <= i < 18:
            continue
        TelemetryReading.objects.create(
            charge_point=ponto, ts=t + timedelta(hours=i),
            kind=TelemetryReading.Kind.HEARTBEAT,
            state=TelemetryReading.State.CONNECTED,
        )

    deteccoes = detect_point_health(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)))

    assert len(deteccoes) == 1
    assert deteccoes[0].category == "health"
    assert "sem comunicar" in deteccoes[0].explanation


def test_deteccao_e_idempotente(cenario):
    """Reprocessar o mes nao pode inundar a fila do sindico com duplicatas."""
    args = janela(date(2026, 6, 1), date(2026, 6, 30))
    run_detection(cenario["condominium"], *args, use_isolation_forest=False)
    n1 = AnomalyFlag.objects.count()
    run_detection(cenario["condominium"], *args, use_isolation_forest=False)

    assert AnomalyFlag.objects.count() == n1


def test_toda_flag_tem_explicacao_legivel(cenario):
    """Requisito da Opcao B: nenhuma flag sem explicacao que um humano leia."""
    s = cenario["sessions"][1003]
    s.energy_kwh = Decimal("120.000")
    s.save(update_fields=["energy_kwh"])
    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)

    for flag in AnomalyFlag.objects.all():
        assert len(flag.explanation) > 40
        assert flag.explanation[0].isupper()


# --------------------------------------------------------------------------
# Metrica contra gabarito
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_recall_contra_gabarito_do_gerador(db):
    """Mede a deteccao contra o que o gerador sabidamente injetou.

    Recall e a metrica exigida: o gabarito e completo quanto ao que foi
    injetado (todo injetado esta la), mas incompleto quanto ao que e anomalo
    (o modelo fisico produz extremos legitimos que ninguem marcou) -- por isso
    nao se afere precisao contra ele.
    """
    cenario = build_jardim_aurora(extra_residents=True)
    condo = cenario["condominium"]
    gen = SyntheticGenerator(condo, seed=20260831, anomaly_rate=0.08)
    resultado = gen.generate(date(2026, 1, 1), date(2026, 5, 31))

    run_detection(condo, *janela(date(2026, 1, 1), date(2026, 5, 31)))
    report = evaluate(resultado.ground_truth, condo)

    assert report.total_injected >= 15, "gabarito pequeno demais para a metrica valer"
    assert report.overall_recall == 1.0, (
        f"deteccao perdeu anomalias injetadas:\n{report.render()}"
    )
