"""O site não pode depender de servidor de terceiro para se desenhar.

POR QUE ESTE TESTE EXISTE. CSS, fonte e ícone vinham de CDN. Quando um
CDN não responde -- e acontece por operadora, por DNS, por bloqueio de
rede corporativa --, o site perde TODOS os ícones de uma vez: carrinho,
WhatsApp, coração, seta. A página continua no ar parecendo quebrada, que
é pior do que sair do ar.

Aqui a varredura é sobre o que a página CARREGA (folha de estilo e
script). Link para wa.me, Instagram ou Google Maps é destino de clique,
não dependência de desenho, e continua liberado.
"""

import re
from pathlib import Path

from django.test import TestCase


HOSPEDEIROS_PROIBIDOS = (
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "unpkg.com",
    "stackpath.bootstrapcdn.com",
    "maxcdn.bootstrapcdn.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "code.jquery.com",
    "use.fontawesome.com",
)

# Linhas que realmente puxam arquivo para a página.
CARREGAMENTO = re.compile(
    r"""(<script[^>]+src=|rel=["']stylesheet["']|@import\s+url\()""",
    re.IGNORECASE,
)


class SemCdnNoSiteTests(TestCase):

    def test_nenhum_template_puxa_css_fonte_ou_script_de_fora(self):
        raiz = Path(__file__).resolve().parent / "templates"
        problemas = []

        for template in sorted(raiz.rglob("*.html")):
            for numero, linha in enumerate(
                template.read_text(encoding="utf-8").splitlines(), 1
            ):
                if not CARREGAMENTO.search(linha):
                    continue

                for hospedeiro in HOSPEDEIROS_PROIBIDOS:
                    if hospedeiro in linha:
                        relativo = template.relative_to(raiz)
                        problemas.append(f"{relativo}:{numero} → {hospedeiro}")

        self.assertEqual(
            problemas,
            [],
            "Arquivo carregado de CDN (traga para core/static/vendor/):\n"
            + "\n".join(problemas),
        )

    def test_os_arquivos_locais_existem_de_verdade(self):
        """Referência para um arquivo que não veio junto é o mesmo buraco."""
        estaticos = Path(__file__).resolve().parent / "static" / "vendor"

        obrigatorios = [
            "fontes.css",
            "fontawesome/css/all.min.css",
            "fontawesome/webfonts/fa-solid-900.woff2",
            "fontawesome/webfonts/fa-brands-400.woff2",
            "fontes/manrope-latin-700-normal.woff2",
            "leaflet/leaflet.js",
            "leaflet/leaflet.css",
        ]

        faltando = [
            caminho for caminho in obrigatorios
            if not (estaticos / caminho).exists()
        ]

        self.assertEqual(faltando, [], f"Faltam em static/vendor: {faltando}")

    def test_o_css_de_fontes_aponta_para_arquivos_que_existem(self):
        pasta = Path(__file__).resolve().parent / "static" / "vendor"
        css = (pasta / "fontes.css").read_text(encoding="utf-8")

        referencias = re.findall(r'url\("([^"]+)"\)', css)
        self.assertTrue(referencias, "O CSS de fontes não referencia nada.")

        faltando = [
            referencia for referencia in referencias
            if not (pasta / referencia).exists()
        ]

        self.assertEqual(faltando, [], f"Fonte referenciada e ausente: {faltando}")
