"""Quando uma linha de fatura fica retida -- a regra, num lugar so.

O motor de rateio (ao fechar) e o portal (quando alguem decide ou contesta)
precisam responder a mesma pergunta: *esta sessao esta em auditoria?* Ja
responderam diferente, e a divergencia apagava contestacao de morador. Agora os
dois chamam daqui.

Uma sessao segura a sua linha por dois caminhos, ambos da Sprint 1:

1. **Anomalia sem desfecho que duvida do NUMERO cobrado** (Opcao B): medicao,
   consumo impossivel ou atipico, contestacao do morador. Ociosidade, potencia
   degradada e saude do ponto NAO seguram: o kWh cobrado esta certo, o problema
   e de convivencia ou de manutencao, e vai para a fila operacional. Achado da
   fase 2 (Isolation Forest) e sugestao: so segura depois que o gestor o
   confirma. A regra mora em `AnomalyFlag.holds_billing`.
2. **Leitura final perdida** (Opcao A, caso degenerado): a cobranca usou a ultima
   leitura periodica, o valor mais conservador, e vai para conferencia humana.
   Conferencia que TERMINA: quando o gestor encerra a flag de medicao daquela
   sessao, aceitou a leitura conservadora e a linha e liberada. Sem isso a
   fatura ficava retida para sempre -- a tela oferecia "esta tudo certo", o
   gestor clicava, e nada mudava.
"""

from __future__ import annotations

from core.models import AnomalyFlag, ChargingSession, Invoice, InvoiceLine


def held_session_ids(session_ids) -> set[int]:
    """Das sessoes dadas, quais estao retidas. Duas consultas, nao N."""
    ids = list(session_ids)
    held = set(
        AnomalyFlag.objects.filter(session_id__in=ids).holding()
        .values_list("session_id", flat=True)
    )
    leitura_aceita = set(
        AnomalyFlag.objects.filter(
            session_id__in=ids, category=AnomalyFlag.Category.METERING,
            status__in=AnomalyFlag.RELEASED,
        ).values_list("session_id", flat=True)
    )
    for s in ChargingSession.objects.filter(id__in=ids, meter_stop__isnull=True):
        if s.final_reading_lost and s.id not in leitura_aceita:
            held.add(s.id)
    return held


def sync_session(session_id: int) -> None:
    """Propaga o estado de auditoria da sessao para as linhas e as faturas."""
    held = session_id in held_session_ids([session_id])
    for linha in InvoiceLine.objects.filter(session_id=session_id).select_related("invoice"):
        if linha.flagged_for_audit != held:
            linha.flagged_for_audit = held
            linha.save(update_fields=["flagged_for_audit"])
        inv = linha.invoice
        tem_retida = inv.lines.filter(flagged_for_audit=True).exists()
        if tem_retida and inv.status == Invoice.Status.CLOSED:
            inv.status = Invoice.Status.UNDER_REVIEW
            inv.save(update_fields=["status"])
        elif not tem_retida and inv.status == Invoice.Status.UNDER_REVIEW:
            inv.status = Invoice.Status.CLOSED
            inv.save(update_fields=["status"])
