"""Testes do admin de inspecao.

O admin quase todo e configuracao declarativa, e o `manage.py check` ja a
valida contra os campos reais. O que merece teste e o unico ponto em que o
admin REESCREVE uma regra de dominio: o filtro de retencao de fatura, terceira
forma da regra que ja existe como consulta (`holding()`) e como propriedade
(`holds_billing`).
"""

import pytest
from django.urls import reverse

from core.models import AnomalyFlag
from core.scenarios import build_jardim_aurora

CHANGELIST = "admin:core_anomalyflag_changelist"


@pytest.fixture
def todas_as_combinacoes(db):
    """Uma flag para cada categoria x detector x situacao, como em
    `test_consulta_e_propriedade_concordam_sobre_quem_retem`."""
    sessao = build_jardim_aurora()["sessions"][1003]
    for categoria in AnomalyFlag.Category.values:
        for detector in ("rule", "isolation_forest", "morador"):
            for situacao in AnomalyFlag.Status.values:
                AnomalyFlag.objects.create(
                    session=sessao, category=categoria, detector=detector,
                    status=situacao, explanation=f"{categoria}/{detector}/{situacao}",
                )


def filtradas(admin_client, segura):
    resposta = admin_client.get(reverse(CHANGELIST), {"segura": segura})
    assert resposta.status_code == 200
    # `cl.queryset` e o resultado do filtro inteiro, antes da paginacao.
    return set(resposta.context["cl"].queryset.values_list("explanation", flat=True))


def test_filtro_segurando_mostra_exatamente_as_flags_que_retem(admin_client, todas_as_combinacoes):
    esperadas = {f.explanation for f in AnomalyFlag.objects.all() if f.holds_billing}

    assert filtradas(admin_client, "1") == esperadas
    assert "consumption/rule/open" in esperadas  # ancora: o conjunto nao e vazio


def test_filtro_nao_segura_e_o_complemento_e_concorda_com_a_coluna(admin_client, todas_as_combinacoes):
    """Toda linha que a coluna `segura fatura` marca com X aparece aqui -- as
    encerradas E as operacionais, que nunca seguraram nada."""
    esperadas = {f.explanation for f in AnomalyFlag.objects.all() if not f.holds_billing}

    nao_seguram = filtradas(admin_client, "0")
    assert nao_seguram == esperadas
    assert "consumption/rule/dismissed" in nao_seguram  # caso encerrado
    assert "idle/rule/open" in nao_seguram  # operacao: aberta, mas nao trava dinheiro
