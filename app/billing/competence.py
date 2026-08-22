"""Competencia: o mes civil a que uma sessao pertence.

A Opcao A definiu que a sessao pertence ao mes civil do seu **inicio** -- o caso
"virada de mes". A armadilha e que "mes civil" e um conceito de fuso local,
enquanto o banco guarda UTC (decisao da Frente 3-C).

Concretamente, no mes ficticio: a sessao 1010 comeca em 30/06 23:40 BRT, o que
em UTC e 01/07 02:40. Calcular a competencia sobre o timestamp armazenado
jogaria a sessao para julho e a fatura da unidade 105 fecharia em R$ 52,17 em
vez de R$ 72,33.

Por isso a conversao acontece aqui, num lugar so, e o resto do motor nunca toca
em fuso.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings

COMPETENCE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def condo_tz() -> ZoneInfo:
    return ZoneInfo(settings.CONDOMINIUM_TIME_ZONE)


@dataclass(frozen=True, order=True)
class Competence:
    """Um mes civil no fuso do condominio, no formato `YYYY-MM`."""

    year: int
    month: int

    @classmethod
    def parse(cls, text: str) -> "Competence":
        if not COMPETENCE_RE.match(text or ""):
            raise ValueError(f"competencia invalida: {text!r} (esperado YYYY-MM)")
        y, m = text.split("-")
        return cls(int(y), int(m))

    @classmethod
    def of(cls, moment: datetime) -> "Competence":
        """A competencia de um instante -- convertido para o fuso civil antes
        de olhar o mes. E a linha que decide o caso da virada de mes."""
        local = moment.astimezone(condo_tz())
        return cls(local.year, local.month)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def last_day(self) -> date:
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    @property
    def days_in_month(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    def next(self) -> "Competence":
        return Competence(self.year + 1, 1) if self.month == 12 else Competence(self.year, self.month + 1)

    def previous(self) -> "Competence":
        return Competence(self.year - 1, 12) if self.month == 1 else Competence(self.year, self.month - 1)

    def utc_window(self) -> tuple[datetime, datetime]:
        """Intervalo semiaberto [inicio, fim) em UTC que cobre este mes civil.

        Semiaberto de proposito: uma sessao que comeca exatamente a meia-noite
        do dia 1 pertence ao mes novo, nao aos dois. E a forma indexavel de
        filtrar competencia -- o banco usa o indice de `session_start` em vez de
        aplicar uma funcao de fuso linha a linha.
        """
        tz = condo_tz()
        start_local = datetime.combine(self.first_day, time.min, tzinfo=tz)
        end_local = datetime.combine(self.next().first_day, time.min, tzinfo=tz)
        return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))
