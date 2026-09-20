"""Testes do favicon.

O defeito que interessa aqui e silencioso: `<link rel="icon">` apontando para
arquivo que nao existe, ou SVG malformado, nao quebra pagina nenhuma -- a aba
so fica sem icone, e ninguem percebe ate a apresentacao. Por isso o teste segue
a corrente inteira: a pagina declara o link, o link aponta para um estatico que
o Django encontra, e o estatico e um SVG que um parser aceita.

As duas superficies sao testadas porque nao compartilham `<head>`: o portal
herda de `portal/base.html`, o admin herda dos templates do proprio Django.
"""

from pathlib import Path
from xml.etree import ElementTree

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

FAVICON = "img/favicon.svg"


def declara_o_favicon(html: str) -> bool:
    return f'<link rel="icon" type="image/svg+xml" href="{static(FAVICON)}">' in html


@pytest.mark.django_db
def test_portal_declara_o_favicon(client):
    html = client.get(reverse("login")).content.decode()

    assert declara_o_favicon(html)
    # O emoji embutido dependia da fonte do sistema de quem abria a pagina.
    assert "data:image/svg+xml" not in html


@pytest.mark.django_db
def test_admin_declara_o_mesmo_favicon(client):
    html = client.get(reverse("admin:login")).content.decode()

    assert declara_o_favicon(html)


def test_favicon_existe_e_e_um_svg_valido():
    caminho = finders.find(FAVICON)
    assert caminho, f"{FAVICON} nao foi encontrado pelos finders de estaticos"

    raiz = ElementTree.parse(Path(caminho)).getroot()
    assert raiz.tag == "{http://www.w3.org/2000/svg}svg"
    assert raiz.get("viewBox") == "0 0 32 32"
