"""Recargas sem dono: energia que o condominio pagou e ninguem ressarciu.

O carregador entrega a sessao; quem e a pessoa e o cadastro da plataforma que
resolve. Quando nao resolve -- cartao nao cadastrado, ou auto-start, em que o
"cartao" reportado e o proprio numero de serie do equipamento -- a sessao entra
orfa: persistida, fora do rateio, a espera de gente.

Ha duas formas de dar dono a uma sessao, e a diferenca importa:

- **Atribuir ESTA recarga** a um morador. So a sessao muda. O `auth_id` bruto
  permanece intacto: a trilha continua dizendo o que o equipamento reportou, e
  o vinculo diz o que o gestor decidiu. E para isso que os dois campos existem
  separados (decisao de modelagem 2).
- **Cadastrar o cartao** para um morador. Cria a credencial e resolve todas as
  orfas daquele cartao, inclusive as futuras. Recusado quando o "cartao" e o
  numero de serie de um carregador: isso e assinatura de auto-start, e
  cadastra-la daria a um unico morador toda recarga anonima do predio.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.money import round2
from core.models import AppUser, ChargePoint, ChargingSession, Credential


class OrphanError(Exception):
    pass


def orphan_sessions(condominium):
    return (
        ChargingSession.objects.filter(
            charge_point__condominium=condominium, credential__isnull=True
        )
        .exclude(status=ChargingSession.Status.IN_PROGRESS)
        .select_related("charge_point")
        .order_by("-session_start")
    )


def orphan_summary(condominium) -> dict:
    sessoes = list(orphan_sessions(condominium))
    kwh = sum((Decimal(s.energy_kwh) for s in sessoes), Decimal("0.000"))
    valor = sum(
        (round2(Decimal(s.energy_kwh) * Decimal(s.applied_tariff_kwh or 0)) for s in sessoes),
        Decimal("0.00"),
    )
    return {"sessoes": sessoes, "n": len(sessoes), "kwh": kwh, "valor": valor}


def is_autostart(auth_id: str) -> bool:
    return bool(auth_id) and ChargePoint.objects.filter(serial_number=auth_id).exists()


def _credential_of(user: AppUser) -> Credential:
    cred = user.credentials.filter(status=Credential.Status.ACTIVE).order_by("id").first()
    if cred is None:
        raise OrphanError(f"{user.name} nao tem credencial ativa: cadastre um cartao antes")
    return cred


@transaction.atomic
def assign_session(session: ChargingSession, user: AppUser) -> ChargingSession:
    if session.credential_id is not None:
        raise OrphanError("esta recarga ja tem dono")
    session.credential = _credential_of(user)
    session.save(update_fields=["credential"])
    return session


@transaction.atomic
def register_card(condominium, auth_id: str, user: AppUser) -> int:
    if not auth_id:
        raise OrphanError("sessao sem identificador de cartao")
    if is_autostart(auth_id):
        raise OrphanError(
            "este identificador e o numero de serie de um carregador (partida sem cartao): "
            "cadastra-lo atribuiria a um morador toda recarga anonima. Atribua as recargas uma a uma"
        )
    cred, _ = Credential.objects.get_or_create(
        auth_tag=auth_id,
        defaults={"user": user, "kind": Credential.Kind.RFID,
                  "valid_from": timezone.localdate()},
    )
    if cred.user_id != user.id:
        raise OrphanError(f"o cartao {auth_id} ja esta cadastrado para {cred.user.name}")
    return orphan_sessions(condominium).filter(auth_id=auth_id).update(credential=cred)
