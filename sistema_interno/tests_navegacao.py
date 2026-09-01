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

    def test_resposta_antiga_nao_substitui_clique_mais_novo(self):
        """Rede lenta não pode fazer a tela anterior chegar por último."""
        navegacao = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "ls-soft-navigation.js"
        ).read_text(encoding="utf-8")

        self.assertIn("versao !== navegacao", navegacao)
        self.assertIn(
            "trocarDocumento(cache, alvo, modoHistorico || \"push\", minhaNavegacao)",
            navegacao,
        )
        self.assertIn("aplicarTela(novoDoc, url, modoHistorico, versao)", navegacao)

    def test_troca_fecha_gaveta_e_falha_volta_para_navegacao_normal(self):
        """Menu e fetch são acessórios; nenhum deles pode prender a tela."""
        navegacao = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "ls-soft-navigation.js"
        ).read_text(encoding="utf-8")

        self.assertIn("function fecharMenuMovel()", navegacao)
        self.assertIn('sidebar.classList.remove("open")', navegacao)
        self.assertIn('overlay.classList.remove("open")', navegacao)
        self.assertIn("window.location.assign(alvo.href)", navegacao)
        self.assertNotIn("lsNavRecovery", navegacao)

    def test_os_tem_tabela_no_pc_e_card_ordenado_no_tablet(self):
        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

        # A TABELA CHEIA SÓ A PARTIR DE 1200px.
        #
        # Ela começava em 901px, e entre 901 e 1180 não cabia: medido no
        # Chromium, faltavam até 90px numa célula e 67px num cabeçalho.
        # O que se via era uma tabela com as palavras cortadas ao meio.
        # Abaixo disso, o cartão -- que mostra tudo inteiro.
        self.assertIn("@media (min-width:1200px)", folha)
        self.assertIn(".ls-os-body .ls-os-tabela", folha)
        self.assertIn("min-width:0!important;width:100%!important;table-layout:fixed!important", folha)
        self.assertIn("@media (min-width:601px) and (max-width:1199px)", folha)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))!important", folha)

        # E o cabeçalho pode quebrar linha: era `nowrap`, e "Revisão dos
        # blocos" não tinha como caber sem cortar.
        self.assertIn("white-space:normal;font-size:.69rem", folha)

    def test_documentos_ocupam_a_folha_a4_inteira(self):
        """Uma folha só continua sendo a regra -- vazia deixou de ser.

        Para garantir que nunca virasse a página, os dois documentos
        tinham sido encolhidos até caber a maior proposta imaginável:
        corpo de 8px, rótulos de 5,2pt, recuos de 1,2mm. Funcionava, e o
        preço era que TODA proposta pagava pelo tamanho da maior -- o
        cliente recebia uma A4 com o documento espremido no terço de
        cima e quase metade da folha em branco.

        Agora a folha é uma coluna com a altura útil da A4: o rodapé
        prende no pé e os quadros dividem a sobra entre si.
        """
        for nome in ("orcamento_publico.html", "ordem_servico_publica.html"):
            with self.subTest(documento=nome):
                documento = (RAIZ_CORE / "templates" / nome).read_text(encoding="utf-8")
                self.assertIn("@page{size:A4 portrait;margin:9mm}", documento)
                self.assertIn("width:192mm", documento)
                # A coluna que preenche a folha, e o rodapé no pé dela.
                self.assertIn("min-height:277mm", documento)
                self.assertIn("margin-top:auto", documento)
                # O tamanho antigo não volta.
                self.assertNotIn("font-size:8px", documento)

    def test_nenhuma_letra_impressa_desce_abaixo_do_que_o_papel_aguenta(self):
        """5,2pt não se lê em papel, e a laser come a letra fina."""
        import re

        for nome in ("orcamento_publico.html", "ordem_servico_publica.html"):
            with self.subTest(documento=nome):
                documento = (RAIZ_CORE / "templates" / nome).read_text(encoding="utf-8")
                impressao = documento[documento.index("@media print"):]
                impressao = re.sub(r"/\*.*?\*/", " ", impressao, flags=re.S)

                for tamanho in re.findall(r"font-size:([\d.]+)pt", impressao):
                    with self.subTest(tamanho=tamanho):
                        self.assertGreaterEqual(float(tamanho), 6.6)

    def test_a_densidade_da_folha_e_decidida_no_servidor(self):
        """`:nth-of-type` conta por TIPO de elemento, e não por classe.

        No orçamento as linhas de item são `div` no meio de outras `div`
        -- o título do bloco, o cabeçalho da tabela. "O nono div" não é
        "o nono item", e a regra quebraria em silêncio na próxima `div`
        acrescentada antes da lista.
        """
        from core.impressao import densidade, peso_do_documento

        self.assertEqual(densidade(0), "folha-solta")
        self.assertEqual(densidade(10), "folha-solta")
        self.assertEqual(densidade(11), "folha-densa")
        self.assertEqual(densidade(18), "folha-densa")
        self.assertEqual(densidade(19), "folha-apertada")
        self.assertEqual(densidade(200), "folha-apertada")

        # O PESO É DO DOCUMENTO INTEIRO, E NÃO DA TABELA.
        #
        # Uma O.S. de quatro itens com um diagnóstico longo, fotos e o
        # quadro do Pix ocupa mais folha do que uma de doze itens secos.
        # Contar só linhas de tabela acertaria a segunda e erraria a
        # primeira -- e errar aqui é entregar um documento cortado ou uma
        # folha pela metade.
        self.assertEqual(peso_do_documento(itens=4), 4)
        self.assertGreater(
            peso_do_documento(itens=4, textos=("x" * 400,), com_pagamento=True),
            peso_do_documento(itens=12),
        )
        # Texto vazio não pesa; nem `None`, que é o que vem de um campo
        # em branco no banco.
        self.assertEqual(peso_do_documento(itens=2, textos=("", "   ", None)), 2)
        # Fotos entram pela faixa que ocupam: para a folha tanto faz se
        # o que a encheu foi tabela ou imagem.
        self.assertGreater(
            peso_do_documento(itens=2, fotos=6), peso_do_documento(itens=2),
        )
        # Nada de contagem de tipo sobrando nas REGRAS. Os comentários
        # citam `nth-of-type` de propósito, para explicar por que ele não
        # serve aqui -- procurar no arquivo inteiro acusaria a explicação
        # da correção como se fosse a falha.
        import re

        for nome in ("orcamento_publico.html", "ordem_servico_publica.html"):
            with self.subTest(documento=nome):
                documento = (RAIZ_CORE / "templates" / nome).read_text(encoding="utf-8")
                self.assertIn('class="{{ densidade_folha }}"', documento)
                regras = re.sub(r"/\*.*?\*/", " ", documento, flags=re.S)
                self.assertNotIn("nth-of-type", regras)


class IdentidadeVisualTests(SimpleTestCase):
    """Cor é o que diz ao olho em que lugar do sistema se está.

    O aplicativo da fábrica é grafite e âmbar, e isso não é gosto: o /adm
    do site é azul, e quem trabalha nos dois no mesmo dia precisa saber
    onde está antes de ler qualquer título. Telas que nasceram no painel
    antigo trouxeram o azul junto -- as campanhas, e o documento da O.S.
    que o cliente recebe, azul de ponta a ponta ao lado de uma proposta
    comercial que já era cinza-ardósia.

    Estes são os azuis daquele painel. Nenhum deles volta.
    """

    #: Os tons exatos do /adm que vazaram para o aplicativo.
    AZUIS_DO_PAINEL_ANTIGO = (
        "#08266e", "#0d3a91", "#1666c5", "#20a6d8",
        "#edf5ff", "#c9d9ef", "#e8eef8",
        "72,170,255", "31,115,191", "22,71,128",
    )

    def _sem_comentarios(self, texto):
        sem = re.sub(r"{% comment %}.*?{% endcomment %}", "", texto, flags=re.S)
        return re.sub(r"/\*.*?\*/", "", sem, flags=re.S)

    def test_o_aplicativo_nao_tem_azul_do_painel_antigo(self):
        alvos = [
            *sorted(TEMPLATES.rglob("*.html")),
            *sorted((TEMPLATES.parent / "static" / "interno").rglob("*.css")),
        ]
        encontrados = []

        for arquivo in alvos:
            if "vendor" in arquivo.parts:
                continue
            conteudo = self._sem_comentarios(
                arquivo.read_text(encoding="utf-8")
            ).lower()
            for azul in self.AZUIS_DO_PAINEL_ANTIGO:
                if azul in conteudo:
                    encontrados.append(f"{arquivo.name}: {azul}")

        self.assertEqual(
            encontrados, [],
            "Azul do painel antigo no aplicativo da fábrica:\n  "
            + "\n  ".join(encontrados),
        )

    def test_o_documento_da_os_usa_a_mesma_tinta_da_proposta(self):
        """Os dois documentos do cliente têm de parecer da mesma empresa."""
        documento = (
            RAIZ_CORE / "templates" / "ordem_servico_publica.html"
        ).read_text(encoding="utf-8")

        for azul in self.AZUIS_DO_PAINEL_ANTIGO:
            with self.subTest(cor=azul):
                self.assertNotIn(azul, self._sem_comentarios(documento).lower())

        # E o acento passou a ser o âmbar da marca.
        self.assertIn("--blue:#B45309", documento)
