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
# Reter pelo que se duvida, nao por quem detectou
# --------------------------------------------------------------------------

def test_consulta_e_propriedade_concordam_sobre_quem_retem(cenario):
    """A regra de retencao existe em duas formas: consulta (o motor de rateio
    pergunta ao banco) e propriedade (a tela pergunta ao objeto). Duas formas da
    mesma regra divergem no primeiro ajuste; aqui todas as combinacoes de
    categoria x detector x situacao passam pelas duas."""
    sessao = cenario["sessions"][1003]
    for categoria in AnomalyFlag.Category.values:
        for detector in ("rule", "isolation_forest", "morador"):
            for situacao in AnomalyFlag.Status.values:
                AnomalyFlag.objects.create(
                    session=sessao, category=categoria, detector=detector,
                    status=situacao, explanation=f"{categoria}/{detector}/{situacao}",
                )

    pela_consulta = set(AnomalyFlag.objects.holding().values_list("explanation", flat=True))
    pela_propriedade = {f.explanation for f in AnomalyFlag.objects.all() if f.holds_billing}
    assert pela_consulta == pela_propriedade

    # Ancoras, para a concordancia nao ser a de dois erros iguais.
    assert "consumption/rule/open" in pela_consulta
    assert "metering/rule/accepted" in pela_consulta
    assert "consumption/morador/contested" in pela_consulta
    assert "consumption/isolation_forest/accepted" in pela_consulta
    assert "consumption/isolation_forest/open" not in pela_consulta
    assert "idle/rule/open" not in pela_consulta
    assert "power_degradation/rule/accepted" not in pela_consulta
    assert "health/rule/open" not in pela_consulta
    assert "consumption/rule/resolved" not in pela_consulta


@pytest.mark.parametrize("categoria", ["idle", "power_degradation"])
@pytest.mark.parametrize("situacao", ["open", "accepted"])
def test_aviso_de_operacao_nao_segura_a_fatura(cenario, categoria, situacao):
    """Carro-tampao e carregador fraco sao problemas reais, e nenhum dos dois
    torna errado o kWh cobrado. Vao a fila do sindico; a fatura do vizinho fecha."""
    sessao = cenario["sessions"][1003]
    AnomalyFlag.objects.create(
        session=sessao, category=categoria, status=situacao,
        explanation="problema de operacao, nao de cobranca",
    )
    close_competence(cenario["condominium"], JUNHO)
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))

    assert inv.lines.get(session=sessao).flagged_for_audit is False
    assert inv.status == Invoice.Status.CLOSED


def test_sugestao_da_fase_2_so_retem_depois_de_confirmada(cenario):
    """Outlier estatistico diz que a sessao e DIFERENTE, nao o que esta errado.
    Chama a atencao do sindico; so segura dinheiro depois que ele confirma."""
    sessao = cenario["sessions"][1003]
    flag = AnomalyFlag.objects.create(
        session=sessao, category=AnomalyFlag.Category.CONSUMPTION,
        detector="isolation_forest", explanation="fora do padrao historico",
    )
    close_competence(cenario["condominium"], JUNHO)
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))
    assert inv.status == Invoice.Status.CLOSED

    flag.status = AnomalyFlag.Status.ACCEPTED
    flag.save(update_fields=["status"])
    close_competence(cenario["condominium"], JUNHO, force=True)
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))
    assert inv.lines.get(session=sessao).flagged_for_audit is True
    assert inv.status == Invoice.Status.UNDER_REVIEW


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

    assert "impossível" in flag.explanation
    assert "82" in flag.explanation          # cita a capacidade cadastrada
    assert flag.detector == "rule"
    assert flag.status == AnomalyFlag.Status.OPEN


def _carregou_uma_hora_e_ficou(s):
    """Telemetria: potencia ate 1 h depois do inicio, zero dai em diante."""
    inicio = s.session_start
    TelemetryReading.objects.filter(session=s).delete()
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


def test_regra_pega_ociosidade_com_base_na_telemetria(cenario):
    """Ociosidade sai da telemetria (quando a potencia zerou), nao da sessao.

    De dia: carregou 1 h e segurou a vaga das 10h as 17h55. Carro-tampao."""
    s = cenario["sessions"][1001]
    tz = ZoneInfo("America/Sao_Paulo")
    s.session_start = datetime(2026, 6, 3, 9, 0, tzinfo=tz)
    s.session_end = datetime(2026, 6, 3, 17, 55, tzinfo=tz)
    s.save(update_fields=["session_start", "session_end"])
    _carregou_uma_hora_e_ficou(s)

    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)
    flag = AnomalyFlag.objects.get(session=s, category="idle")

    assert "conectado após concluir" in flag.explanation
    assert s.duration_hours - 1 > IDLE_HOURS_THRESHOLD


def test_pernoitar_plugado_nao_e_carro_tampao(cenario):
    """O MESMO padrao, a noite: plugou as 22h10, carregou 1 h, saiu as 6h05.

    Sao sete horas "ociosas" em que ninguem foi impedido de carregar. E o uso
    mais comum de um predio, e o mais desejavel (fora do pico). A regra antiga,
    calibrada num estacionamento de escritorio, acusaria esse morador."""
    s = cenario["sessions"][1001]           # 02/06 22:10 -> 03/06 06:05
    _carregou_uma_hora_e_ficou(s)

    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)

    assert not AnomalyFlag.objects.filter(session=s, category="idle").exists()


def test_so_conta_a_ociosidade_fora_do_pernoite():
    from core.policy import contended_hours

    tz = ZoneInfo("America/Sao_Paulo")
    h = lambda d, hh, mm=0: datetime(2026, 6, d, hh, mm, tzinfo=tz)   # noqa: E731
    assert contended_hours(h(2, 23, 10), h(3, 6, 5), tz) == 0.0       # toda no pernoite
    assert contended_hours(h(3, 10), h(3, 17), tz) == 7.0             # toda em horario de uso
    assert contended_hours(h(2, 19), h(3, 9), tz) == 5.0              # 19-22h e 7-9h
    assert contended_hours(h(2, 12), h(4, 12), tz) == 30.0            # dois dias: 48 h - 2 x 9 h
    assert contended_hours(h(3, 9), h(3, 9), tz) == 0.0


def test_regra_pega_leitura_perdida(cenario):
    run_detection(cenario["condominium"], *janela(date(2026, 6, 1), date(2026, 6, 30)),
                  use_isolation_forest=False)
    flag = AnomalyFlag.objects.get(session=cenario["sessions"][1005], category="metering")

    assert "última leitura periódica" in flag.explanation
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


def test_gerador_respeita_o_conector_e_o_periodo(db):
    """Duas propriedades fisicas que a primeira versao do gerador violava.

    Um conector atende um carro por vez (eram 205 pares de sessoes sobrepostas
    em 366). E a fila do conector nao pode empurrar recarga para fora do periodo
    pedido: uma sessao de 31/05 adiada para a madrugada de 01/06 entrava na
    competencia de junho e alterava uma fatura do mes ficticio do dossie.
    """
    from django.db import connection

    from core.models import ChargingSession
    from core.scenarios import build_jardim_aurora
    from ingestion.generator import SyntheticGenerator

    condo = build_jardim_aurora(extra_residents=True)["condominium"]
    antes = set(ChargingSession.objects.values_list("id", flat=True))
    r = SyntheticGenerator(condo, seed=7).generate(date(2026, 4, 1), date(2026, 5, 31))

    with connection.cursor() as c:
        c.execute(
            "select count(*) from charging_session a join charging_session b "
            "on a.charge_point_id = b.charge_point_id and a.id < b.id "
            "and a.session_start < b.session_end and b.session_start < a.session_end"
        )
        assert c.fetchone()[0] == 0
    novas = ChargingSession.objects.exclude(id__in=antes)
    assert novas.count() == r.sessions_created > 50
    assert all(str(Competence.of(s.session_start)) in ("2026-04", "2026-05") for s in novas)
    assert set(novas.values_list("source", flat=True)) == {"synthetic"}      # entrou pelo gateway
    assert r.sessions_deferred > 0          # houve disputa pelo conector, e ela foi resolvida


def test_fase_2_se_abstem_quando_a_fonte_nao_entrega_telemetria(db):
    """Desconhecido nao e zero. O historico real do SEMS+ nao traz potencia nem
    MeterValues; preenchido com 0,0, fez o Isolation Forest acusar 17 das 18
    recargas reais do HCA G2 de "potencia zero"."""
    from ingestion.adapters import SemsPlusLogAdapter
    from ingestion.gateway import IngestionGateway

    condo = build_jardim_aurora(extra_residents=True)["condominium"]
    SyntheticGenerator(condo, seed=3).generate(date(2026, 4, 1), date(2026, 5, 31))
    IngestionGateway(condo).ingest(SemsPlusLogAdapter())

    tz = ZoneInfo("America/Sao_Paulo")
    run_detection(condo, datetime(2026, 5, 25, tzinfo=tz), datetime(2026, 6, 30, 23, 59, tzinfo=tz))

    assert ChargingSession.objects.filter(source="semsplus_log").count() == 72
    assert not AnomalyFlag.objects.filter(session__source="semsplus_log").exists()


def test_alerta_de_fila_olha_tempo_de_conector_e_nao_energia(db):
    """12 unidades num conector de 7 kW: em kWh o ponto esta folgado, e o painel
    dizia "nenhum risco de fila". Em tempo de cabo, ha gente esperando."""
    from intelligence.forecast import forecast

    condo = build_jardim_aurora(extra_residents=True)["condominium"]
    SyntheticGenerator(condo, seed=11).generate(date(2026, 3, 1), date(2026, 5, 31))

    prev = forecast(condo, today=date(2026, 5, 31))

    fila = [a for a in prev.alerts if a.kind == "contention"]
    assert len(fila) == 1 and "esperando o cabo" in fila[0].message
    assert "cabe na potência declarada" in fila[0].message     # 7 + 7 <= 22 kW
    assert not [a for a in prev.alerts if a.kind == "saturation"]
