"""As telas de gestão do painel (site/...) seguem as cores do tema.

POR QUE ESTE TESTE EXISTE. As telas herdadas do antigo /adm traziam a
paleta dele escrita à mão: fundo marrom-café (#1E1913, #231D16, #1A1610),
tinta creme (#E7DDCB, #FCF8F1), âmbar velho (#F2A93B) e as mesmas cores com
opacidade (rgba(44, 37, 27, ...), rgba(242, 169, 59, ...)). No tema escuro
era o "marrom em todo lado"; no claro, caixas escuras com o texto sumindo no
papel. Cor escrita à mão não muda de tema.

Agora toda cor dessas telas sai das variáveis do painel (--text, --panel,
--bg-1, --acento, --green... de interno_modern.css), e o topo de cada tela
(o "hero") e os números seguem um desenho só, em gestao_integrada.css.

O que se cobra:
  * nenhuma das cores da paleta antiga nos CSS, JS e templates de gestão;
  * as telas refeitas (Brinquedos, Promoções) sem cor fixa nenhuma, fora o
    branco do botão da chave e o preto das sombras;
  * a camada comum: o topo sem a caixa marrom, os cabeçalhos de tabela na
    tinta do tema, e todo topo de tela de gestão com o nome que ela pega.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent
PAGINAS = RAIZ / "static" / "site" / "paginas"
TEMPLATES = RAIZ / "templates" / "gestao"
INTEGRADA = RAIZ.parent / "sistema_interno" / "static" / "interno" / "gestao_integrada.css"

#: A paleta do /adm antigo: superfícies café, tinta creme, âmbar velho e
#: os vizinhos de cada um que apareciam pelas telas.
HEX_PROIBIDOS = {
    "1E1913", "231D16", "1A1610", "181410", "13100B", "2B241B", "2C251B", "342B20",
    "3F3527", "7A6540", "211605", "E7DDCB", "C4B6A0", "A2917A", "FCF8F1", "D8CCB9",
    "C4B49B", "766A5A", "F5C070", "F2A93B", "D98E22", "FFC46B", "E8B060", "FFD08A",
    "FF7A6B", "FF9AAA", "FFB2A9", "5FD68A", "7CE7BC", "9DEBC0", "3DD9C0", "FFC94D",
    "FFD77A", "F3EADB",
}
#: As mesmas cores com opacidade, pelo trio de números.
RGB_PROIBIDOS = {
    (44, 37, 27), (63, 53, 39), (43, 36, 27), (52, 43, 32), (90, 70, 112),
    (122, 101, 64), (35, 29, 22), (30, 25, 19), (26, 22, 16), (24, 20, 16),
    (19, 16, 11), (242, 169, 59), (217, 142, 34), (255, 122, 107), (110, 64, 56),
    (95, 214, 138), (63, 107, 82), (255, 201, 77), (252, 248, 241), (196, 182, 160),
    (9, 7, 4),
}


def sem_comentarios(texto):
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    texto = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", texto, flags=re.S)
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    return texto


def arquivos_de_gestao():
    yield from sorted(PAGINAS.glob("gestao-*.css"))
    yield from sorted(PAGINAS.glob("gestao-*.js"))
    yield from sorted(TEMPLATES.glob("*.html"))
    yield INTEGRADA


def cores_da_paleta_antiga(texto):
    achadas = []
    for m in re.finditer(r"#([0-9a-fA-F]{6})\b", texto):
        if m.group(1).upper() in HEX_PROIBIDOS:
            achadas.append(m.group(0))
    for m in re.finditer(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", texto):
        trio = tuple(int(n) for n in m.groups())
        if trio in RGB_PROIBIDOS:
            achadas.append(m.group(0))
    return achadas


class PaletaAntigaTests(SimpleTestCase):

    def test_nenhuma_tela_de_gestao_traz_a_paleta_marrom(self):
        problemas = {}
        for arquivo in arquivos_de_gestao():
            achadas = cores_da_paleta_antiga(sem_comentarios(arquivo.read_text(encoding="utf-8")))
            if achadas:
                problemas[arquivo.name] = sorted(set(achadas))[:8]
        self.assertEqual(
            problemas, {},
            "Cor fixa da paleta do /adm antigo numa tela de gestão: use as "
            "variáveis do tema (var(--panel), var(--text), var(--acento)...).",
        )

    def test_as_telas_refeitas_nao_tem_cor_fixa_nenhuma(self):
        """Brinquedos e Promoções: só variável de tema.

        Ficam de fora o branco (a bolinha da chave liga/desliga, a letra do
        selo sobre a foto), o preto das sombras e a cor de reserva dentro de
        `var(--x, reserva)`, que só vale se o tema faltar.
        """
        for nome in ("gestao-brinquedos_adm.css", "gestao-promocoes_adm.css"):
            with self.subTest(folha=nome):
                css = sem_comentarios((PAGINAS / nome).read_text(encoding="utf-8"))
                css = re.sub(r"var\(--[\w-]+\s*,[^()]*\)", "var()", css)
                hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", css)}
                self.assertLessEqual(hexes, {"#fff", "#ffffff"}, nome)
                trios = {tuple(int(n) for n in t) for t in
                         re.findall(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", css)}
                self.assertLessEqual(trios, {(0, 0, 0)}, nome)

    def test_o_svg_do_grafico_de_vendas_usa_o_tema(self):
        """O gráfico do Dashboard é SVG montado no JS: a cor vai em `style`,
        que aceita var(); atributo de apresentação (fill="...") não aceita."""
        js = (PAGINAS / "gestao-dashboard.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r'(fill|stroke|stop-color)="#')
        self.assertIn("stroke:var(--acento)", js)


class TelaNaoMexeNoPainelTests(SimpleTestCase):
    """O estilo de uma tela não pode reescrever o painel em volta.

    A tela de Banners trazia `:root { --shadow: ...; --card: ...; --bg: ... }`
    e `body { background }` e `button { ... }` soltos: trocava a sombra de
    todo o painel por uma cor, pintava o fundo da página inteira e o sino
    da barra de cima, que saía da tela no celular.
    """

    def tokens_do_tema(self):
        folha = RAIZ.parent / "sistema_interno" / "static" / "interno" / "interno_modern.css"
        css = folha.read_text(encoding="utf-8")
        inicio = css.index(':root,\n:root[data-tema="lua"]{')
        bloco = css[inicio:css.index("\n}", inicio)]
        return set(re.findall(r"(--[a-z0-9-]+)\s*:", bloco))

    def estilos(self):
        for arquivo in sorted(PAGINAS.glob("gestao-*.css")):
            yield arquivo.name, sem_comentarios(arquivo.read_text(encoding="utf-8"))
        for arquivo in sorted(TEMPLATES.glob("*.html")):
            if arquivo.name == "acesso_negado.html":
                continue  # página que se basta, sem o painel em volta
            html = arquivo.read_text(encoding="utf-8")
            blocos = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
            yield arquivo.name, sem_comentarios("".join(blocos))

    def test_nenhuma_tela_redefine_variavel_do_tema(self):
        tema = self.tokens_do_tema()
        for nome, css in self.estilos():
            for bloco in re.findall(r":root\s*\{([^}]*)\}", css):
                definidas = set(re.findall(r"(--[a-z0-9-]+)\s*:", bloco))
                with self.subTest(tela=nome):
                    self.assertEqual(sorted(definidas & tema), [])

    def test_nenhuma_tela_pinta_o_corpo_ou_todo_botao(self):
        soltos_proibidos = {"body", "button", "button:hover", "button:disabled", "*"}
        for nome, css in self.estilos():
            seletores = re.findall(r"(?:^|[{}])\s*([^{}@]+?)\s*\{", css)
            soltos = [
                parte.strip() for seletor in seletores for parte in seletor.split(",")
                if parte.strip() in soltos_proibidos
            ]
            with self.subTest(tela=nome):
                self.assertEqual(soltos, [])

    def test_a_pagina_de_acesso_negado_se_basta(self):
        """Ela não carrega a folha do painel: var(--x) ali não pinta nada."""
        html = (TEMPLATES / "acesso_negado.html").read_text(encoding="utf-8")
        self.assertNotIn("interno_modern.css", html)
        estilo = sem_comentarios(html[html.index("<style>"):html.index("</style>")])
        self.assertNotIn("var(--bg-", estilo)
        self.assertNotIn("var(--acento", estilo)


class CamadaComumTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = sem_comentarios(INTEGRADA.read_text(encoding="utf-8"))

    def regra(self, seletor):
        m = re.search(re.escape(seletor) + r"\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, f"falta a regra {seletor}")
        return m.group(1)

    def test_o_topo_das_telas_nao_e_mais_a_caixa_marrom(self):
        corpo = self.regra('.gestao-integrada .ls-content [class$="-hero"]')
        self.assertIn("background:none!important", corpo)
        self.assertIn("border:0!important", corpo)
        self.assertIn("box-shadow:none!important", corpo)
        self.assertIn("flex-wrap:wrap", corpo)
        # o brilho e o anel decorativos saem
        self.assertRegex(self.css, r'\[class\$="-hero"\]::after\{content:none!important')

    def test_o_cabecalho_das_tabelas_usa_a_tinta_do_tema(self):
        corpo = self.regra(".gestao-integrada .ls-content th")
        self.assertIn("color:var(--text-2)!important", corpo)
        self.assertIn("background:var(--acento-fundo)!important", corpo)
        self.assertNotIn("acento-texto", corpo)

    def test_o_botao_principal_do_topo_cabe_no_celular(self):
        self.assertRegex(
            self.css,
            r'@media \(max-width:640px\)\{\s*\.gestao-integrada \.ls-content \[class\$="-hero"\]'
            r'\{flex-direction:column;align-items:stretch\}',
        )
        self.assertIn('[class$="-hero"]>button', self.css)

    def test_todo_topo_de_tela_de_gestao_tem_o_nome_que_a_regra_pega(self):
        """A regra comum pega classe que TERMINA em "-hero". Um topo chamado
        "xyz-hero algo" escaparia dela e voltaria a ter caixa própria."""
        for arquivo in sorted(TEMPLATES.glob("*.html")):
            html = arquivo.read_text(encoding="utf-8")
            for classe in re.findall(r'<section class="([^"]*-hero[^"]*)"', html):
                with self.subTest(tela=arquivo.name, classe=classe):
                    self.assertRegex(classe, r"-hero$")

    def test_a_onda_do_sino_nao_faz_a_tela_rolar_de_lado(self):
        """O anel do sino cresce 1,55x e passava da borda no celular."""
        self.assertIn(".gestao-integrada .ls-topbar{overflow-x:clip}", self.css)

    def test_os_numeros_sem_o_sufixo_kpi_tambem_sao_cartao(self):
        for classe in (".ekpi", ".pkpi", ".okpi", ".kpi-box"):
            with self.subTest(classe=classe):
                self.assertIn(f".gestao-integrada .ls-content {classe}", self.css)
