"""Fuso de APRESENTACAO.

O banco guarda UTC e toda regra de negocio converte explicitamente para o fuso
civil do condominio (`billing.competence.condo_tz`). Faltava a ultima perna: o
template. Com `TIME_ZONE = "UTC"` e nenhum fuso ativo, o filtro `|date` do Django
renderiza em UTC -- a recarga de 12/06 as 22:30 aparecia no painel do sindico
como "13/06 as 01:30", enquanto o extrato do morador, que convertia a mao,
mostrava 22:45 para a mesma noite. Duas telas discordando sobre quando algo
aconteceu e o tipo de coisa que derruba a confianca numa fatura.
"""

from django.utils import timezone

from billing.competence import condo_tz


class CondoTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timezone.activate(condo_tz())
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
