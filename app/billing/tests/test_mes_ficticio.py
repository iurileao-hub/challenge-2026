"""Teste de aceitacao do motor de rateio contra o mes ficticio da Sprint 1.

Todos os valores esperados neste arquivo foram copiados de
`docs/frente-3-arquitetura.md`, secao "Um mes ficticio: junho/2026 no
Residencial Jardim Aurora" -- escrita e conferida em junho/2026, meses antes de
existir uma linha do motor. Nenhum numero aqui foi lido da implementacao.

E o que a Frente 3-C chamou de "aposta verificavel": se o motor reproduzir a
fatura linha a linha usando somente as 14 entidades, sem migracao de
emergencia, o contrato cumpriu seu papel.
"""

from decimal import Decimal

import pytest

from billing.competence import Competence
from billing.engine import ClosingReport, close_competence
from billing.money import round2
from billing.reconciliation import register_reconciliation
from core.models import Invoice, InvoiceLine
from core.scenarios import build_jardim_aurora

JUNHO = Competence(2026, 6)
JULHO = Competence(2026, 7)


@pytest.fixture
def cenario(db):
    return build_jardim_aurora()


@pytest.fixture
def fechamento(cenario) -> ClosingReport:
    return close_competence(cenario["condominium"], JUNHO)


def fatura(cenario, label: str) -> Invoice:
    return Invoice.objects.get(unit=cenario["units"][label], competence=str(JUNHO))


# --------------------------------------------------------------------------
# Os tres totais de fatura do dossie
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label,total_esperado",
    [("72", "53.21"), ("34", "66.76"), ("105", "72.33")],
)
def test_total_da_fatura_bate_com_o_dossie(cenario, fechamento, label, total_esperado):
    assert fatura(cenario, label).total_amount == Decimal(total_esperado)


def test_unidade_72_tem_uma_fatura_para_dois_veiculos(cenario, fechamento):
    """Caso 3 do enunciado: o casal com dois carros recebe UMA fatura, com o
    extrato discriminando qual credencial iniciou cada sessao."""
    inv = fatura(cenario, "72")
    sessoes = inv.lines.filter(kind=InvoiceLine.Kind.SESSION).order_by("id")

    assert Invoice.objects.filter(unit=cenario["units"]["72"], competence=str(JUNHO)).count() == 1
    assert [ln.amount for ln in sessoes] == [Decimal("13.34"), Decimal("18.13"), Decimal("6.74")]
    # O extrato nomeia quem carregou -- e o que torna a fatura discutivel em casa.
    assert "Ana Ribeiro" in sessoes[0].description
    assert "Bruno Ribeiro" in sessoes[1].description
    # Taxa de disponibilidade e UNICA por unidade, nao por veiculo.
    assert inv.lines.filter(kind=InvoiceLine.Kind.AVAILABILITY_FEE).count() == 1


def test_unidade_34_cobra_o_medido_ate_a_interrupcao(cenario, fechamento):
    """Caso 1: sessao interrompida cobra exatamente o kWh entregue, com o
    motivo na linha, e vai para auditoria por ter perdido a leitura final."""
    inv = fatura(cenario, "34")
    linha = inv.lines.get(session=cenario["sessions"][1005])

    assert linha.energy_kwh == Decimal("6.020")
    assert linha.amount == Decimal("4.37")
    assert linha.flagged_for_audit is True
    assert "interrompida" in linha.description
    assert "PowerLoss" in linha.description
    assert "leitura final perdida" in linha.description
    # Fatura com linha em auditoria nao fecha silenciosamente.
    assert inv.status == Invoice.Status.UNDER_REVIEW


def test_unidade_105_inclui_a_sessao_da_virada_do_mes(cenario, fechamento):
    """A sessao 1010 comeca 30/06 23:40 BRT (= 01/07 02:40 UTC) e pertence a
    JUNHO -- competencia e o mes civil do inicio."""
    inv = fatura(cenario, "105")
    s1010 = cenario["sessions"][1010]

    assert inv.lines.filter(session=s1010).exists()
    assert inv.lines.get(session=s1010).amount == Decimal("20.16")
    assert not Invoice.objects.filter(
        unit=cenario["units"]["105"], competence=str(JULHO)
    ).exists()


def test_arredondamento_e_half_up_e_nao_half_even(cenario, fechamento):
    """A sessao 1006 da 11,250 x 0,7252 = 8,1585 exatamente.

    Half-up (a regra da Opcao A) -> 8,16. Half-even (o padrao do IEEE-754 e do
    `round()` do Python) -> 8,15. O dossie escolheu este caso de proposito.
    """
    linha = fatura(cenario, "105").lines.get(session=cenario["sessions"][1006])

    assert Decimal("11.250") * Decimal("0.7252") == Decimal("8.1585")
    assert linha.amount == Decimal("8.16")
    assert linha.amount != Decimal("8.15")


# --------------------------------------------------------------------------
# Rateio da parcela fixa
# --------------------------------------------------------------------------

def test_aderente_que_nao_carregou_paga_so_a_disponibilidade(cenario, fechamento):
    """Caso 2 do enunciado: `S_u` vazio -> so a parcela fixa."""
    inv = fatura(cenario, "12")

    assert inv.total_amount == Decimal("15.00")
    assert inv.lines.count() == 1
    assert inv.lines.first().kind == InvoiceLine.Kind.AVAILABILITY_FEE


def test_unidade_nao_aderente_nao_recebe_fatura(cenario, fechamento):
    """"Unidade que nunca aderiu nao paga nada" -- o rateio alcanca so quem
    optou pelo servico."""
    nao_aderentes = set(cenario["units"]) - set(cenario["enrolled_labels"])
    assert len(nao_aderentes) == 36

    faturadas = set(
        Invoice.objects.filter(competence=str(JUNHO)).values_list("unit__label", flat=True)
    )
    assert faturadas & nao_aderentes == set()


def test_doze_aderentes_e_cota_de_quinze_reais(cenario, fechamento):
    assert fechamento.n_enrolled == 12
    cotas = InvoiceLine.objects.filter(
        invoice__competence=str(JUNHO), kind=InvoiceLine.Kind.AVAILABILITY_FEE
    )
    assert cotas.count() == 12
    assert {ln.amount for ln in cotas} == {Decimal("15.00")}


# --------------------------------------------------------------------------
# Agregados do mes
# --------------------------------------------------------------------------

def test_agregados_do_mes(cenario, fechamento):
    """"Receita do mes: R$ 147,30 de energia + R$ 180,00 de disponibilidade =
    R$ 327,30 sobre 203,120 kWh entregues"."""
    assert fechamento.kwh_total == Decimal("203.120")
    assert fechamento.energy_total == Decimal("147.30")
    assert fechamento.availability_collected == Decimal("180.00")
    assert fechamento.total_billed == Decimal("327.30")
    assert fechamento.residual == Decimal("0.00")


def test_total_da_fatura_e_a_soma_das_linhas(cenario, fechamento):
    """Invariante de auditabilidade: o total nunca e calculado por fora. Se o
    sindico somar o extrato na calculadora, tem de bater."""
    for inv in Invoice.objects.filter(competence=str(JUNHO)):
        soma = sum((ln.amount for ln in inv.lines.all()), Decimal("0.00"))
        assert inv.total_amount == round2(soma), f"fatura {inv.pk} nao fecha"


# --------------------------------------------------------------------------
# Reconciliacao em dois tempos (decisao 5)
# --------------------------------------------------------------------------

@pytest.fixture
def reconciliacao(cenario, fechamento):
    """"Em 10/07 chega a fatura Enel de junho: R$ 3.094,00 por 3.400 kWh
    -> efetivo = R$ 0,9100/kWh"."""
    return register_reconciliation(
        cenario["condominium"],
        JUNHO,
        utility_invoice_total=Decimal("3094.00"),
        utility_invoice_kwh=Decimal("3400.000"),
        provisional_price_kwh=Decimal("0.7252"),
    )


def test_apuracao_do_efetivo(reconciliacao):
    assert reconciliacao.effective_price_kwh == Decimal("0.9100")
    assert reconciliacao.delta_price_kwh == Decimal("0.1848")
    assert reconciliacao.settled_in_competence == "2026-07"


@pytest.mark.parametrize(
    "label,ajuste_esperado", [("72", "9.74"), ("34", "13.19"), ("105", "14.61")]
)
def test_ajuste_entra_como_linha_na_fatura_seguinte(
    cenario, reconciliacao, label, ajuste_esperado
):
    """O ajuste nao reescreve junho: entra como UMA linha explicada na fatura
    de julho."""
    close_competence(cenario["condominium"], JULHO)
    inv = Invoice.objects.get(unit=cenario["units"][label], competence=str(JULHO))
    linha = inv.lines.get(kind=InvoiceLine.Kind.TARIFF_ADJUSTMENT)

    assert linha.amount == Decimal(ajuste_esperado)
    assert linha.unit_price_kwh == Decimal("0.1848")
    assert "2026-06" in linha.description
    # Junho continua intacto -- e o ponto do desenho em dois tempos.
    assert fatura(cenario, label).total_amount == Decimal(
        {"72": "53.21", "34": "66.76", "105": "72.33"}[label]
    )


def test_aderente_sem_consumo_nao_recebe_ajuste(cenario, reconciliacao):
    """"Delta multiplica kWh, e o kWh delas e zero"."""
    close_competence(cenario["condominium"], JULHO)
    inv = Invoice.objects.get(unit=cenario["units"]["12"], competence=str(JULHO))

    assert not inv.lines.filter(kind=InvoiceLine.Kind.TARIFF_ADJUSTMENT).exists()
    assert inv.total_amount == Decimal("15.00")


def test_soma_dos_ajustes_bate_com_o_dossie(cenario, reconciliacao):
    """"Total de ajustes: R$ 37,54"."""
    close_competence(cenario["condominium"], JULHO)
    total = sum(
        (
            ln.amount
            for ln in InvoiceLine.objects.filter(
                invoice__competence=str(JULHO), kind=InvoiceLine.Kind.TARIFF_ADJUSTMENT
            )
        ),
        Decimal("0.00"),
    )
    assert total == Decimal("37.54")
