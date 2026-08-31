"""O contrato entre o HTML do painel e a troca de tela sem recarregar.

POR QUE ESTE ARQUIVO EXISTE. A troca de tela deixou de ser
`document.write` -- que jogava o documento fora e o remontava do zero,
com uma janela de tempo sem CSS em que o logotipo aparecia do tamanho do
arquivo e os ícones viravam símbolo aleatório. No lugar dela, o
JavaScript troca só a área de conteúdo e reaproveita o cabeçalho, o menu
e as folhas de estilo que já estão na página.

Isso só funciona porque o HTML cumpre quatro combinados. Nenhum deles é
visível olhando uma tela isolada, e quebrar qualquer um só aparece no
navegador, depois do segundo clique -- que é justamente onde ninguém
testa à mão. Daí os testes abaixo.
"""

import re
from pathlib import Path

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings


TEMPLATES = Path(__file__).resolve().parent / "templates"
RAIZ_CORE = Path(__file__).resolve().parent.parent / "core"


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ContratoDaTrocaDeTelaTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor", password="senha-segura", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def abrir(self, rota="/orcamentos/"):
        return self.client.get(rota, HTTP_HOST="interno.testserver")

    def test_a_folha_do_painel_tem_ancora_para_a_cascata(self):
        """Sem a âncora, o CSS de tela entra no fim e ganha do painel.

        A mesma tela ficaria com uma aparência ao ser aberta direto e
        outra ao ser alcançada pelo menu.
        """
        self.assertContains(self.abrir(), 'id="lsFolhaBase"')

    def test_o_script_da_tela_mora_numa_caixa_propria(self):
        """É a caixa que a troca esvazia e reescreve.

        Sem ela não há como separar o script que morre com a tela do
        script do painel, que atravessa a sessão.
        """
        self.assertContains(self.abrir(), 'id="lsTelaScripts"')

    def test_o_estilo_de_sobrevivencia_esta_no_proprio_html(self):
        """Ele existe para valer ANTES de qualquer folha chegar.

        Num arquivo separado ele chegaria junto com o problema que
        deveria evitar.
        """
        html = self.abrir().content.decode()
        self.assertIn('data-ls-base="1"', html)
        self.assertIn("img,svg,video{max-width:100%}", html)

    def test_a_tela_oferece_o_gancho_de_partida_para_o_script(self):
        self.assertContains(self.abrir(), "window.LSTela")


class ScriptDeTelaNaoEsperaDOMContentLoadedTests(SimpleTestCase):
    """`DOMContentLoaded` acontece uma vez por PÁGINA, não por TELA.

    O painel troca de tela sem recarregar a página. Um script de tela que
    espere esse evento roda na primeira tela e nunca mais: os botões
    aparecem, e nenhum deles faz nada. Foi assim que a janela de edição
    parou de abrir depois de trocar de tela uma vez.

    `LSTela.pronto(fn)` cobre os dois casos -- espera quando há o que
    esperar, roda na hora quando não há.
    """

    def test_nenhuma_tela_do_painel_espera_o_evento_da_pagina(self):
        culpados = []
        for arquivo in sorted(TEMPLATES.rglob("*.html")):
            texto = arquivo.read_text(encoding="utf-8")
            # As telas soltas -- login, sessão encerrada, erro -- têm
            # cabeçalho próprio e são sempre carregadas de verdade.
            if "{% extends" not in texto:
                continue
            if "DOMContentLoaded" in texto:
                culpados.append(str(arquivo.relative_to(TEMPLATES)))

        self.assertEqual(
            culpados,
            [],
            "Tela do painel esperando DOMContentLoaded. O evento não "
            "acontece de novo quando a tela é trocada sem recarregar a "
            "página, e o script nunca roda. Troque por LSTela.pronto():\n  "
            + "\n  ".join(culpados),
        )

    def test_folha_de_tela_se_declara_como_tal(self):
        """`extra_css` sem `data-ls-tela` gruda no painel para sempre.

        As folhas do painel valem em toda tela e ficam. As de uma tela só
        precisam sair quando a tela sai -- e a marca é como a troca sabe a
        diferença. Sem ela, o CSS do catálogo do site entrava na primeira
        tela de /site/ e continuava valendo em cima da lista de orçamentos
        e da produção pelo resto da sessão: a tela certa, com as regras de
        outra. É uma das caras de "o CSS bugou quando troquei de tela".
        """
        marcados = re.compile(
            r"""<link[^>]*rel=["']stylesheet["'][^>]*>""", re.I
        )
        desmarcados = []

        for pasta in (TEMPLATES, RAIZ_CORE / "templates"):
            for arquivo in sorted(pasta.rglob("*.html")):
                texto = arquivo.read_text(encoding="utf-8")
                bloco = re.search(
                    r"{% block extra_css %}(.*?){% endblock %}", texto, re.S
                )
                if not bloco:
                    continue
                for folha in marcados.findall(bloco.group(1)):
                    if "data-ls-tela" not in folha:
                        desmarcados.append(f"{arquivo.name}: {folha.strip()}")

        self.assertEqual(
            desmarcados,
            [],
            "Folha de estilo em extra_css sem data-ls-tela. Ela entraria "
            "no <head> na primeira tela que a pedisse e continuaria "
            "valendo em todas as seguintes:\n  " + "\n  ".join(desmarcados),
        )

    def test_a_navegacao_suave_e_registrada_antes_da_barra_de_carregamento(self):
        """Ouvinte de bolha roda na ordem em que foi registrado.

        Os dois escutam clique no documento. A navegação suave chama
        `preventDefault` nos links do painel, e é isso que diz à barra que
        não haverá troca de página para acompanhar. Se a barra for
        registrada primeiro, ela decide antes de saber -- e volta a piscar
        a cada clique, que é a "sensação de carregamento" numa troca que
        não carrega nada.
        """
        base = (TEMPLATES / "base_inner.html").read_text(encoding="utf-8")

        posicao_navegacao = base.index("ls-soft-navigation.js")
        posicao_barra = base.index("ls-page-loader.js")

        self.assertLess(
            posicao_navegacao, posicao_barra,
            "ls-soft-navigation.js precisa vir antes de ls-page-loader.js "
            "no <head>: script defer executa na ordem do documento, e o "
            "primeiro a executar é o primeiro a escutar o clique.",
        )

    def test_a_barra_de_carregamento_respeita_o_clique_ja_tratado(self):
        """A barra some do caminho de quem trata o clique por fetch.

        O comentário do arquivo sempre disse que era assim -- os ouvintes
        ficam na bolha justamente para enxergar o `preventDefault` --, mas
        a conferência existia só no envio de formulário, não no clique.
        """
        barra = (
            RAIZ_CORE / "static" / "site" / "ls-page-loader.js"
        ).read_text(encoding="utf-8")

        trecho = barra[barra.index('addEventListener("click"'):]
        trecho = trecho[:trecho.index("addEventListener(\"submit\"")]

        self.assertIn("evento.defaultPrevented", trecho)

    def test_a_troca_de_tela_nao_reescreve_o_documento(self):
        """Reescrever o documento é a origem do instante sem estilo.

        O comentário do próprio arquivo explica o defeito e cita o nome
        da chamada; por isso a busca é feita no CÓDIGO, com os
        comentários removidos -- senão a explicação reprovaria a correção.
        """
        navegacao = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "ls-soft-navigation.js"
        ).read_text(encoding="utf-8")

        codigo = re.sub(r"/\*.*?\*/", "", navegacao, flags=re.S)
        codigo = re.sub(r"^\s*//.*$", "", codigo, flags=re.M)

        self.assertNotIn("document.write", codigo)
        self.assertNotIn("document.open", codigo)
        self.assertIn("garantirFolhas", codigo)
