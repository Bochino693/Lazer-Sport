"""O painel nunca entrega um endereço que a página do cliente recusa.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO. As páginas públicas do orçamento e
da O.S. respondem 404 enquanto o documento não foi enviado -- e isso é
proposital: enquanto a equipe monta a proposta, quem tiver o link não
deve ver nada. O painel, porém, montava o endereço para qualquer
documento e o colocava no botão "Abrir página pública" da janela de
envio. Quem conferia a proposta ANTES de mandar levava uma página de
erro, e a leitura óbvia era "o sistema quebrou".

São duas telas, dois modelos e três lugares que montam o endereço. Por
isso o teste não confere um botão: ele confere a REGRA, comparando o que
o painel oferece com o que a página pública realmente responde.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import (
    ItemOrcamento,
    ItemOrdemServico,
    Orcamento,
    OrdemServico,
)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class LinkPublicoSoExisteDepoisDoEnvioTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-links", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    # ------------------------------------------------------------ apoio
    def orcamento(self):
        orcamento = Orcamento.objects.create(nome_cliente="Buffet Alegria")
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=Decimal("280.00"),
        )
        return orcamento

    def ordem(self):
        ordem = OrdemServico.objects.create(
            nome_cliente="Cliente balcão", equipamento="Tobogã",
        )
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
            descricao="Reparo", quantidade=1, valor_unitario=Decimal("120.00"),
        )
        return ordem

    def publico(self, documento):
        """O que o CLIENTE recebe ao abrir o endereço, de verdade."""
        return self.client.get(
            documento.caminho_publico, HTTP_HOST="testserver",
        ).status_code

    # ---------------------------------------------------------- orçamento
    def test_a_regra_do_painel_e_a_da_pagina_do_cliente_sao_a_mesma(self):
        """`publicado` tem de prever o que a página pública responde.

        Se as duas se separarem, volta o 404: o painel oferece, a página
        recusa. Este teste compara as duas em cada situação.
        """
        rascunho = self.orcamento()
        self.assertFalse(rascunho.publicado)
        self.assertEqual(self.publico(rascunho), 404)

        rascunho.marcar_enviado()
        rascunho.refresh_from_db()
        self.assertTrue(rascunho.publicado)
        self.assertEqual(self.publico(rascunho), 200)

    def test_a_lista_de_orcamentos_nao_mostra_link_de_rascunho(self):
        rascunho = self.orcamento()

        html = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        ).content.decode()

        self.assertNotIn(rascunho.token, html)

    def test_a_lista_mostra_o_link_da_proposta_enviada(self):
        enviada = self.orcamento()
        enviada.marcar_enviado()

        html = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        ).content.decode()

        self.assertIn(enviada.token, html)

    # --------------------------------------------------------------- O.S.
    def test_a_regra_da_os_tambem_acompanha_a_pagina_do_cliente(self):
        ordem = self.ordem()
        self.assertFalse(ordem.publicado)
        self.assertEqual(self.publico(ordem), 404)

        ordem.marcar_enviada()
        ordem.refresh_from_db()
        self.assertTrue(ordem.publicado)
        self.assertEqual(self.publico(ordem), 200)

    def test_a_lista_de_os_nao_mostra_link_de_os_nao_enviada(self):
        ordem = self.ordem()

        html = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).content.decode()

        self.assertNotIn(ordem.token, html)
        # A prévia interna é da equipe e abre em qualquer situação: ela
        # é a resposta para "quero conferir antes de mandar".
        self.assertIn(f"/ordens-servico/{ordem.pk}/previa/", html)

    # -------------------------------------------------- a prévia interna
    def test_a_previa_interna_abre_o_que_a_publica_recusa(self):
        """É a razão de a prévia existir: conferir antes de liberar."""
        rascunho = self.orcamento()
        ordem = self.ordem()

        for caminho in (
            f"/orcamentos/{rascunho.pk}/previa/",
            f"/ordens-servico/{ordem.pk}/previa/",
        ):
            with self.subTest(caminho=caminho):
                resposta = self.client.get(
                    caminho, HTTP_HOST="interno.testserver",
                )
                self.assertEqual(resposta.status_code, 200)


class PaginasDeErroNaoPodemFalharTests(TestCase):
    """A página de erro que depende de outra coisa falha quando é chamada.

    A 404 estendia um template que usava `{% static %}` sem carregar a
    biblioteca. Era erro de sintaxe: estourava ao desenhar, o handler
    engolia a exceção e devolvia um <h1> preto no branco, sem estilo e
    sem saída -- escrito para nunca acontecer, e era o que o cliente via
    ao abrir o link de uma proposta ainda não enviada.
    """

    def test_a_404_desenha_de_verdade(self):
        from django.template.loader import render_to_string

        html = render_to_string("404.html")

        self.assertIn("<html", html)
        self.assertNotIn("Página não encontrada (404)</h1>", html.split("<body")[0])
        self.assertGreater(len(html), 1000)

    def test_a_500_desenha_de_verdade(self):
        from django.template.loader import render_to_string

        html = render_to_string("500.html")

        self.assertIn("<html", html)
        self.assertGreater(len(html), 1000)

    def test_nenhuma_pagina_de_erro_depende_de_arquivo_externo(self):
        """Sem `{% static %}`, sem `extends`, sem folha de fora.

        Se o servidor está com problema, a última coisa em que se pode
        confiar é que ele vá servir mais dois arquivos.
        """
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent / "core" / "templates"
        for nome in ("404.html", "500.html"):
            with self.subTest(pagina=nome):
                texto = (raiz / nome).read_text(encoding="utf-8")
                # O comentário no alto de cada página EXPLICA o defeito e
                # cita os nomes; a conferência é no markup, sem ele.
                markup = re.sub(
                    r"{% comment %}.*?{% endcomment %}", "", texto, flags=re.S
                )
                self.assertNotIn("{% static", markup)
                self.assertNotIn("{% extends", markup)
                self.assertNotIn('<link rel="stylesheet"', markup)
