"""Testes das interfaces.

Alem do caminho feliz, dois grupos importam mais:

- **acesso**: morador nao entra no painel do gestor e nao le fatura alheia. A
  verificacao e feita pela CARGA REAL da URL, e nao lendo a definicao do
  decorador -- guard declarado nao e guard executado.
- **volta da decisao**: revisar uma anomalia e contestar uma linha precisam
  mudar o estado da FATURA, e nao so o da flag. Sem isso a fila de auditoria
  vira um mural sem efeito.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.competence import Competence
from billing.engine import close_competence
from core.models import AnomalyFlag, AppUser, Invoice, InvoiceLine
from core.scenarios import build_jardim_aurora

JUNHO = Competence(2026, 6)


@pytest.fixture
def cenario(db):
    c = build_jardim_aurora()
    for username, app_user, staff in [
        ("sindica", c["users"]["gestor"], True),
        ("carla", c["users"]["carla"], False),
        ("ana", c["users"]["ana"], False),
    ]:
        u = User.objects.create_user(username=username, password="x")
        u.is_staff = staff
        u.save()
        app_user.auth_user = u
        app_user.save(update_fields=["auth_user"])
    close_competence(c["condominium"], JUNHO)
    return c


def entrar(client, username):
    assert client.login(username=username, password="x")


# --------------------------------------------------------------------------
# Acesso
# --------------------------------------------------------------------------

def test_anonimo_e_mandado_para_o_login(client):
    r = client.get("/painel/")
    assert r.status_code == 302
    assert "/entrar/" in r["Location"]


def test_morador_nao_entra_no_painel_do_gestor(client, cenario):
    """Carga real da URL, nao leitura do decorador."""
    entrar(client, "carla")
    assert client.get("/painel/").status_code == 404
    assert client.get("/painel/relatorio/").status_code == 404


def test_gestor_entra_no_painel(client, cenario):
    entrar(client, "sindica")
    r = client.get("/painel/")
    assert r.status_code == 200
    assert "Residencial Jardim Aurora" in r.content.decode()


def test_cada_morador_ve_a_propria_fatura(client, cenario):
    entrar(client, "carla")
    corpo = client.get("/extrato/").content.decode()
    assert "Unidade 34" in corpo
    assert "66,76" in corpo
    # Nao vaza o valor da unidade vizinha.
    assert "53,21" not in corpo


def test_morador_nao_contesta_linha_de_outra_unidade(client, cenario):
    """A autorizacao e por dono do recurso, nao por 'estar logado'."""
    linha_da_72 = InvoiceLine.objects.get(session=cenario["sessions"][1001])
    entrar(client, "carla")   # Carla e da unidade 34
    r = client.post(f"/extrato/linha/{linha_da_72.id}/contestar/", {"motivo": "nao fui eu"})
    assert r.status_code == 404
    assert not AnomalyFlag.objects.exists()


def test_menu_do_gestor_e_do_morador_sao_diferentes(client, cenario):
    """O `e_gestor` do context processor: variavel ausente em template Django e
    silenciosamente vazia, e o menu aparecia errado sem quebrar nada."""
    entrar(client, "sindica")
    assert "Relatório da assembleia" in client.get("/painel/").content.decode()
    client.logout()

    entrar(client, "carla")
    corpo = client.get("/extrato/").content.decode()
    assert "Minha fatura" in corpo
    assert "Relatório da assembleia" not in corpo


# --------------------------------------------------------------------------
# A decisao humana volta para a fatura
# --------------------------------------------------------------------------

def test_descartar_anomalia_libera_a_fatura(client, cenario):
    sessao = cenario["sessions"][1003]     # unidade 105, com leitura final
    flag = AnomalyFlag.objects.create(
        session=sessao, category=AnomalyFlag.Category.CONSUMPTION,
        explanation="consumo atipico", status=AnomalyFlag.Status.OPEN,
    )
    close_competence(cenario["condominium"], JUNHO, force=True)
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))
    assert inv.status == Invoice.Status.UNDER_REVIEW

    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "dismissed"})

    flag.refresh_from_db(); inv.refresh_from_db()
    assert flag.status == AnomalyFlag.Status.DISMISSED
    assert flag.reviewed_by_user == cenario["users"]["gestor"]
    assert flag.reviewed_at is not None
    assert inv.status == Invoice.Status.CLOSED
    assert inv.lines.get(session=sessao).flagged_for_audit is False
    # O valor nunca muda por decisao de auditoria.
    assert inv.total_amount == Decimal("72.33")


def test_confirmar_anomalia_mantem_a_fatura_retida(client, cenario):
    flag = AnomalyFlag.objects.create(
        session=cenario["sessions"][1003], category=AnomalyFlag.Category.CONSUMPTION,
        explanation="consumo atipico", status=AnomalyFlag.Status.OPEN,
    )
    close_competence(cenario["condominium"], JUNHO, force=True)
    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "accepted"})

    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))
    assert inv.status == Invoice.Status.UNDER_REVIEW


def test_leitura_perdida_nao_e_liberada_por_decisao_sobre_outra_flag(cenario, client):
    """A marcacao por telemetria perdida vem do motor, nao da IA: descartar uma
    flag nao apaga o motivo estrutural da auditoria."""
    sessao = cenario["sessions"][1005]      # meter_stop nulo
    flag = AnomalyFlag.objects.create(
        session=sessao, category=AnomalyFlag.Category.METERING,
        explanation="leitura perdida", status=AnomalyFlag.Status.OPEN,
    )
    close_competence(cenario["condominium"], JUNHO, force=True)
    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "dismissed"})

    linha = InvoiceLine.objects.get(session=sessao)
    assert linha.flagged_for_audit is True
    assert linha.invoice.status == Invoice.Status.UNDER_REVIEW


def test_contestacao_do_morador_retem_a_fatura(client, cenario):
    linha = InvoiceLine.objects.get(session=cenario["sessions"][1007])
    entrar(client, "carla")
    r = client.post(f"/extrato/linha/{linha.id}/contestar/",
                    {"motivo": "estava viajando neste dia"})
    assert r.status_code == 302

    linha.refresh_from_db()
    flag = AnomalyFlag.objects.get(session=linha.session)
    assert linha.flagged_for_audit is True
    assert flag.status == AnomalyFlag.Status.CONTESTED
    assert flag.detector == "morador"
    assert "estava viajando" in flag.explanation
    assert linha.invoice.status == Invoice.Status.UNDER_REVIEW


def test_contestacao_sem_motivo_e_recusada(client, cenario):
    linha = InvoiceLine.objects.get(session=cenario["sessions"][1007])
    entrar(client, "carla")
    client.post(f"/extrato/linha/{linha.id}/contestar/", {"motivo": "   "})

    assert not AnomalyFlag.objects.exists()
    linha.refresh_from_db()
    assert linha.flagged_for_audit is False


# --------------------------------------------------------------------------
# Relatorio
# --------------------------------------------------------------------------

def test_relatorio_lista_as_unidades_em_ordem_numerica(client, cenario):
    """Ordem de texto produz 102, 105, 110, 12, 21 -- correto para o banco e
    absurdo para quem le uma lista de apartamentos."""
    entrar(client, "sindica")
    corpo = client.get("/painel/relatorio/").content.decode()
    posicoes = [corpo.index(f">{l}</td>") for l in ["12", "34", "72", "105", "110"]]
    assert posicoes == sorted(posicoes)


def test_relatorio_csv_traz_todas_as_linhas(client, cenario):
    entrar(client, "sindica")
    r = client.get("/painel/relatorio/?formato=csv")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/csv")
    linhas = r.content.decode().strip().split("\n")
    assert len(linhas) == InvoiceLine.objects.filter(invoice__competence=str(JUNHO)).count() + 1
    # O CSV exporta LINHAS, nao totais: 53,21 e a soma da fatura 72 e nao
    # aparece; suas linhas (13,34 + 18,13 + 6,74 + 15,00), sim.
    corpo = r.content.decode()
    for valor in ("13,34", "18,13", "6,74", "15,00"):
        assert valor in corpo, f"{valor} ausente do CSV"


def test_total_do_relatorio_bate_com_a_soma_das_faturas(client, cenario):
    entrar(client, "sindica")
    corpo = client.get("/painel/relatorio/").content.decode()
    assert "327,30" in corpo     # 147,30 de energia + 180,00 de disponibilidade
    assert "147,30" in corpo
    assert "180,00" in corpo
