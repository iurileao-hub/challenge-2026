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
from core.models import AnomalyFlag, AppUser, ChargingSession, Invoice, InvoiceLine
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
    assert "Prestação de contas" in client.get("/painel/").content.decode()
    client.logout()

    entrar(client, "carla")
    corpo = client.get("/extrato/").content.decode()
    assert "Minha conta" in corpo
    assert "Prestação de contas" not in corpo


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
    flag de OUTRO assunto nao apaga o motivo estrutural da auditoria."""
    sessao = cenario["sessions"][1005]      # meter_stop nulo
    outra = AnomalyFlag.objects.create(
        session=sessao, category=AnomalyFlag.Category.CONSUMPTION,
        explanation="consumo atipico", status=AnomalyFlag.Status.OPEN,
    )
    close_competence(cenario["condominium"], JUNHO, force=True)
    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{outra.id}/revisar/", {"decisao": "dismissed"})

    linha = InvoiceLine.objects.get(session=sessao)
    assert linha.flagged_for_audit is True
    assert linha.invoice.status == Invoice.Status.UNDER_REVIEW


def test_aceitar_a_leitura_conservadora_libera_a_fatura(cenario, client):
    """A conferencia humana da leitura perdida precisa TERMINAR.

    Antes, a tela oferecia "Esta tudo certo -- a fatura fica liberada", o
    gestor clicava, e a fatura seguia retida para sempre: a unica pendencia da
    demonstracao nao tinha saida. Encerrar a flag de MEDICAO e o gestor dizendo
    que aceita a ultima leitura periodica, o valor mais conservador.
    """
    sessao = cenario["sessions"][1005]
    flag = AnomalyFlag.objects.create(
        session=sessao, category=AnomalyFlag.Category.METERING,
        explanation="leitura perdida", status=AnomalyFlag.Status.OPEN,
    )
    close_competence(cenario["condominium"], JUNHO, force=True)
    linha = InvoiceLine.objects.get(session=sessao)
    assert linha.flagged_for_audit is True

    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "dismissed"})

    linha.refresh_from_db()
    assert linha.flagged_for_audit is False
    assert linha.invoice.status == Invoice.Status.CLOSED
    # E a liberacao sobrevive ao reprocessamento do mes.
    close_competence(cenario["condominium"], JUNHO, force=True)
    assert InvoiceLine.objects.get(session=sessao).flagged_for_audit is False


def test_caso_confirmado_tem_saida_e_ela_exige_registro(client, cenario):
    flag = AnomalyFlag.objects.create(
        session=cenario["sessions"][1003], category=AnomalyFlag.Category.CONSUMPTION,
        explanation="consumo atipico", status=AnomalyFlag.Status.OPEN,
    )
    close_competence(cenario["condominium"], JUNHO, force=True)
    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "accepted"})
    inv = Invoice.objects.get(unit=cenario["units"]["105"], competence=str(JUNHO))
    assert inv.status == Invoice.Status.UNDER_REVIEW
    assert "à espera de desfecho" in client.get("/painel/").content.decode()

    client.post(f"/painel/anomalia/{flag.id}/resolver/", {"desfecho": "  "})
    inv.refresh_from_db()
    assert inv.status == Invoice.Status.UNDER_REVIEW        # sem texto, nao libera

    client.post(f"/painel/anomalia/{flag.id}/resolver/", {"desfecho": "conferido com o morador"})
    inv.refresh_from_db()
    flag.refresh_from_db()
    assert inv.status == Invoice.Status.CLOSED
    assert (flag.status, flag.resolution) == ("resolved", "conferido com o morador")


def test_decisao_tomada_nao_e_sobrescrita(client, cenario):
    flag = AnomalyFlag.objects.create(
        session=cenario["sessions"][1003], category=AnomalyFlag.Category.CONSUMPTION,
        explanation="x", status=AnomalyFlag.Status.OPEN,
    )
    entrar(client, "sindica")
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "accepted"})
    client.post(f"/painel/anomalia/{flag.id}/revisar/", {"decisao": "dismissed"})
    flag.refresh_from_db()
    assert flag.status == "accepted"


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
    import re

    entrar(client, "sindica")
    corpo = client.get("/painel/relatorio/").content.decode()
    # Le a coluna de unidade pelo `data-rotulo`, nao pela marcacao interna da
    # celula: o teste vigia a ORDEM, e nao pode quebrar quando a apresentacao
    # da celula muda.
    rotulos = re.findall(r'data-rotulo="Unidade">\s*(?:<strong>)?\s*([^<\s]+)', corpo)
    posicoes = [rotulos.index(l) for l in ["12", "34", "72", "105", "110"]]
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


def test_extrato_de_unidade_compartilhada_diz_quem_carregou(client, cenario):
    """A unidade 72 tem duas pessoas credenciadas (Ana no RFID, Bruno no app) e
    uma fatura so. Sem o rotulo, a recarga do Bruno fica indistinguivel das da
    Ana, e o caso excepcional 'dois veiculos na mesma unidade' some da tela."""
    entrar(client, "ana")
    corpo = client.get("/extrato/").content.decode()
    assert "Bruno Ribeiro" in corpo
    assert "Ana Ribeiro" in corpo
    assert "Conta no app" in corpo


def test_extrato_de_unidade_individual_nao_repete_o_nome(client, cenario):
    """A contrapartida: na unidade 34 so a Carla carrega, e repetir o nome dela
    em cada linha da propria fatura e ruido. O rotulo e condicional, nao fixo."""
    entrar(client, "carla")
    corpo = client.get("/extrato/").content.decode()
    assert "Iniciada por" not in corpo


def test_contestacao_chega_a_fila_do_sindico_e_sobrevive_ao_refechamento(client, cenario):
    """Tres defeitos do mesmo desencontro: a fila so listava `open`, o motor so
    retinha `open`, e o pipeline refecha com force. A contestacao do morador
    nao tinha destinatario e sumia na rodada seguinte."""
    close_competence(cenario["condominium"], JUNHO, force=True)
    linha = InvoiceLine.objects.get(session=cenario["sessions"][1007])
    entrar(client, "carla")
    client.post(f"/extrato/linha/{linha.id}/contestar/", {"motivo": "nao carreguei nesse dia"})
    client.post(f"/extrato/linha/{linha.id}/contestar/", {"motivo": "de novo"})
    assert AnomalyFlag.objects.filter(detector="morador").count() == 1     # sem duplicar
    client.post("/sair/")

    entrar(client, "sindica")
    html = client.get("/painel/").content.decode()
    assert "Contestação do morador" in html and "nao carreguei nesse dia" in html

    close_competence(cenario["condominium"], JUNHO, force=True)
    assert InvoiceLine.objects.get(session=cenario["sessions"][1007]).flagged_for_audit is True


def test_contestar_linha_que_nao_e_recarga_nao_quebra(client, cenario):
    close_competence(cenario["condominium"], JUNHO, force=True)
    taxa = InvoiceLine.objects.filter(
        invoice__unit=cenario["units"]["34"], kind=InvoiceLine.Kind.AVAILABILITY_FEE
    ).first()
    entrar(client, "carla")
    resp = client.post(f"/extrato/linha/{taxa.id}/contestar/", {"motivo": "x"})
    assert resp.status_code == 302
    assert not AnomalyFlag.objects.exists()


def test_competencia_invalida_na_url_e_404_e_nao_500(client, cenario):
    entrar(client, "sindica")
    assert client.get("/painel/relatorio/?competencia=abc").status_code == 404
    client.post("/sair/")
    entrar(client, "carla")
    assert client.get("/extrato/?competencia=2026-13").status_code == 404


def test_recarga_sem_dono_ganha_dono_e_entra_na_proxima_fatura(client, cenario):
    """O caminho inteiro do dado real: entra orfa, o gestor atribui, e o motor
    a cobra na proxima competencia sem reescrever o mes fechado."""
    from billing.competence import Competence
    from ingestion.adapters import SemsPlusLogAdapter
    from ingestion.gateway import IngestionGateway

    condo = cenario["condominium"]
    junho = close_competence(condo, JUNHO, force=True)
    total_carla = Invoice.objects.get(unit=cenario["units"]["34"], competence=str(JUNHO)).total_amount
    IngestionGateway(condo).ingest(SemsPlusLogAdapter())

    entrar(client, "sindica")
    html = client.get("/painel/entrada/").content.decode()
    assert "18 recargas sem dono" in html and "136,66 kWh" in html
    assert "Partida sem cartão" in html

    orfa = ChargingSession.objects.filter(source="semsplus_log", energy_kwh="10.70").get()
    carla = cenario["users"]["carla"]
    # Auto-start: cadastrar o "cartao" daria a Carla toda recarga anonima do predio.
    client.post(f"/painel/entrada/recarga/{orfa.id}/atribuir/", {"morador": carla.id, "alcance": "cartao"})
    orfa.refresh_from_db()
    assert orfa.credential is None
    client.post(f"/painel/entrada/recarga/{orfa.id}/atribuir/", {"morador": carla.id, "alcance": "sessao"})
    orfa.refresh_from_db()
    assert orfa.credential.user == carla
    assert orfa.auth_id == "57000HPA247L0002"          # o que o equipamento disse fica na trilha

    julho = close_competence(condo, Competence.parse("2026-07"))
    tardia = InvoiceLine.objects.get(session=orfa)
    assert tardia.invoice.competence == "2026-07" and "2026-06" in tardia.description
    assert tardia.amount == Decimal("7.76")            # 10,70 kWh x R$ 0,7252
    # Junho, fechado, nao foi tocado -- nem se for reprocessado depois.
    assert Invoice.objects.get(unit=cenario["units"]["34"], competence=str(JUNHO)).total_amount == total_carla
    assert close_competence(condo, JUNHO, force=True).total_billed == junho.total_billed


def test_morador_nao_acessa_a_entrada_de_dados(client, cenario):
    entrar(client, "carla")
    assert client.get("/painel/entrada/").status_code == 404
    assert client.post("/painel/entrada/recarga/1/atribuir/", {"morador": 1}).status_code == 404


def test_painel_e_extrato_concordam_sobre_a_hora_da_recarga(client, cenario):
    """O painel renderizava em UTC: 22h45 de 12/06 virava 01h45 de 13/06."""
    sessao = cenario["sessions"][1005]      # 12/06 as 22:45 BRT
    AnomalyFlag.objects.create(
        session=sessao, category=AnomalyFlag.Category.METERING,
        explanation="leitura perdida", status=AnomalyFlag.Status.OPEN,
    )
    entrar(client, "sindica")
    html = client.get("/painel/").content.decode()
    assert "12/06 às 22:45" in html and "13/06 às 01:45" not in html
