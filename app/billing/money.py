"""Aritmetica de dinheiro e energia.

Uma regra so, e ela e inegociavel: **nenhum valor monetario passa por `float`
em nenhum ponto do caminho**. O motor inteiro opera em `decimal.Decimal`.

Nao e purismo. A Opcao A fixou `round2` half-up *por linha* e o dossie escolheu
de proposito um caso que separa as convencoes: a sessao 1006 do mes ficticio da
8,1585, que em half-up e 8,16 e em half-even (o padrao do `round()` do Python e
do IEEE-754) e 8,15. Um centavo -- que numa assembleia de condominio vira uma
hora de discussao, porque o morador refez a conta na calculadora do celular e
achou outro numero.
"""

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
KWH = Decimal("0.001")
TARIFF = Decimal("0.0001")


def round2(value: Decimal) -> Decimal:
    """Arredonda a centavos, meio-para-cima. A `round2` da formula da Opcao A."""
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def round4(value: Decimal) -> Decimal:
    """Arredonda a 4 casas -- precisao de tarifa (R$/kWh)."""
    return Decimal(value).quantize(TARIFF, rounding=ROUND_HALF_UP)


def round3(value: Decimal) -> Decimal:
    """Arredonda a 3 casas -- precisao de energia (kWh)."""
    return Decimal(value).quantize(KWH, rounding=ROUND_HALF_UP)


def line_amount(energy_kwh: Decimal, price_kwh: Decimal) -> Decimal:
    """Valor de uma linha de sessao: kWh x R$/kWh, arredondado a centavos.

    O produto e calculado em precisao total e so entao arredondado -- arredondar
    antes de multiplicar introduziria erro proporcional ao consumo.
    """
    return round2(Decimal(energy_kwh) * Decimal(price_kwh))
