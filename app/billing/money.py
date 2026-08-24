"""Aritmetica de dinheiro e energia.

Uma regra so, e ela e inegociavel: **nenhum valor monetario passa por `float`
em nenhum ponto do caminho**. O motor inteiro opera em `decimal.Decimal`.

Nao e purismo, e a Opcao A fixou `round2` half-up *por linha* justamente por
isso. A convencao so importa quando o produto cai **exatamente** na metade de um
centavo, e nesse ponto ela decide sozinha o valor: 12,500 kWh x 0,7252 da
9,06500 exato, que e 9,07 em half-up e 9,06 em half-even (o padrao do IEEE-754).
Nessa mesma conta o `float` erra: `round(12.5 * 0.7252, 2)` devolve 9,06, porque
0,7252 nao tem representacao binaria exata e o produto armazenado fica um fio
abaixo do empate. Um centavo -- que numa assembleia de condominio vira uma hora
de discussao, porque o morador refez a conta na calculadora do celular e achou
outro numero.

Cuidado com o exemplo errado: a sessao 1006 do mes ficticio da 11,250 x 0,7252 =
8,1585, que arredonda para 8,16 em qualquer convencao (a fracao descartada e 0,85
do centavo, nao metade dele). Ela exercita o arredondamento, nao a escolha da
convencao. A versao anterior desta docstring, do teste correspondente e dos
documentos afirmava que 8,1585 daria 8,15 em half-even; nao da.
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
