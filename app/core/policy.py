"""Parametros de POLITICA do condominio.

Nao sao constantes fisicas nem hiperparametros de modelo: sao decisoes que uma
assembleia pode querer mudar. Ficam num lugar so, fora da deteccao, porque mais
de um modulo precisa concordar sobre elas (o detector que aplica a regra e o
gerador que produz o gabarito contra o qual ela e medida).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

#: A partir de quantas horas de vaga ocupada sem carregar a sessao vai para a
#: fila do sindico.
IDLE_HOURS_THRESHOLD = 4.0

#: Janela de pernoite, no fuso do condominio: [inicio, fim). Tempo ocioso dentro
#: dela NAO conta.
#:
#: Ociosidade so e problema quando impede alguem de carregar. Num predio, o uso
#: tipico e chegar a noite, plugar e so descer de manha: o carro que termina de
#: carregar as 23h30 e sai as 7h ficou sete horas "ocioso" sem ter bloqueado
#: ninguem, porque ninguem desce a garagem as 3h para trocar de vaga. A primeira
#: versao da regra media ociosidade como num estacionamento de escritorio (que e
#: de onde vem o dataset de calibracao) e acusaria o comportamento mais comum e
#: mais desejavel de um morador: recarregar fora do pico.
QUIET_START = time(22, 0)
QUIET_END = time(7, 0)


def contended_hours(start: datetime, end: datetime, tz) -> float:
    """Horas de [start, end) FORA da janela de pernoite, no fuso `tz`."""
    if end <= start:
        return 0.0
    start, end = start.astimezone(tz), end.astimezone(tz)
    total = 0.0
    dia = start.date() - timedelta(days=1)
    while dia <= end.date():
        # trecho disputado do dia: das QUIET_END as QUIET_START
        a = datetime.combine(dia, QUIET_END, tzinfo=tz)
        b = datetime.combine(dia, QUIET_START, tzinfo=tz)
        ini, fim = max(a, start), min(b, end)
        if fim > ini:
            total += (fim - ini).total_seconds() / 3600
        dia += timedelta(days=1)
    return total
