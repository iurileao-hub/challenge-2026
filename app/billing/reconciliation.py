"""Reconciliacao tarifaria em dois tempos (decisao 5 da Frente 3-C).

O problema que ela resolve e uma contradicao real entre duas promessas do
dossie:

- a Opcao A fixou `tarifa_s` como snapshot no encerramento da sessao -- sem
  isso, a fatura de um mes fechado mudaria a cada reajuste;
- a posicao de tributos manda cobrar o R$/kWh **efetivo** da fatura do
  condominio -- que so existe semanas depois, quando a distribuidora emite.

A saida nao e escolher uma das duas: e as duas, em tempos diferentes. A fatura
de M fecha no dia certo com a tarifa provisoria; quando a conta de luz de M
chega, apura-se o efetivo e a fatura de M+1 carrega **uma linha de ajuste por
unidade**, positiva ou negativa.

Uma linha por unidade (e nao recalculo sessao a sessao) mantem o extrato
legivel e limita o erro de arredondamento a um centavo por unidade.
"""

from __future__ import annotations

from decimal import Decimal

from billing.competence import Competence
from billing.money import round4
from core.models import Condominium, TariffReconciliation


def register_reconciliation(
    condominium: Condominium,
    competence: Competence | str,
    *,
    utility_invoice_total: Decimal,
    utility_invoice_kwh: Decimal,
    provisional_price_kwh: Decimal,
    settle_in: Competence | str | None = None,
) -> TariffReconciliation:
    """Apura o efetivo da competencia e agenda o ajuste.

    `settle_in` default = competencia seguinte, que e o comportamento descrito
    no dossie; o parametro existe porque a conta de luz pode atrasar e o ajuste
    entao escorrega para o mes subsequente, sem virar excecao no codigo.
    """
    comp = competence if isinstance(competence, Competence) else Competence.parse(competence)
    if Decimal(utility_invoice_kwh) <= 0:
        raise ValueError("kWh faturados pela distribuidora precisa ser positivo")

    effective = round4(Decimal(utility_invoice_total) / Decimal(utility_invoice_kwh))
    provisional = round4(Decimal(provisional_price_kwh))
    settle = settle_in or comp.next()
    settle_str = str(settle) if isinstance(settle, Competence) else settle

    rec, _ = TariffReconciliation.objects.update_or_create(
        condominium=condominium,
        competence=str(comp),
        defaults=dict(
            utility_invoice_total=Decimal(utility_invoice_total),
            utility_invoice_kwh=Decimal(utility_invoice_kwh),
            effective_price_kwh=effective,
            provisional_price_kwh=provisional,
            delta_price_kwh=round4(effective - provisional),
            settled_in_competence=settle_str,
        ),
    )
    return rec
