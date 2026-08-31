"""Filtrar sem ir ao servidor -- e sem mentir sobre o que existe.

A busca das listas era um formulário GET: cada palavra digitada só valia
depois de apertar a lupa, e a tela inteira recarregava. Agora o servidor
manda, junto da página, um índice enxuto de TODOS os registros do filtro,
e quem procura é o aparelho.

O RISCO DESSA TROCA É A MENTIRA. A lista vem por página; se o índice
viesse só da página desenhada, procurar um cliente da página 2 diria
"nada encontrado" sobre um cadastro que existe. Por isso os testes daqui
insistem em duas coisas: o índice cobre o filtro inteiro, e ele carrega os
mesmos campos que a busca do servidor percorre -- se divergissem, digitar
e apertar "Trazer todos" dariam respostas diferentes.
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .busca_local import montar_indice, sem_acento
from .models import Cliente, ItemOrcamento, Orcamento


class NormalizacaoTests(TestCase):

    def test_tira_acento_e_caixa(self):
        # Quem digita "orcamento" tem de achar "Orçamento"; quem digita
        # "JOAO" tem de achar "João".
        self.assertEqual(sem_acento("Orçamento"), "orcamento")
        self.assertEqual(sem_acento("JOÃO"), "joao")
        self.assertEqual(sem_acento("  Buffet Alegria  "), "buffet alegria")
        self.assertEqual(sem_acento(None), "")

    def test_indice_junta_os_pedacos_numa_linha_so(self):
        indice = montar_indice([(7, ["Buffet Alegria", None, "", "Tobogã"])])

        self.assertEqual(indice, [{"i": "7", "t": "buffet alegria toboga"}])

    def test_o_identificador_vira_texto(self):
        """O JavaScript compara com `tr.dataset.registro`, que é string."""
        self.assertEqual(montar_indice([(12, ["x"])])[0]["i"], "12")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class IndiceDaListaDeOrcamentosTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-filtro", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def proposta(self, nome, item="Cama elástica"):
        orcamento = Orcamento.objects.create(
            nome_cliente=nome, email_cliente="c@example.com",
            status=Orcamento.Status.RASCUNHO,
            validade=timezone.localdate() + timedelta(days=5),
            responsavel=self.gestor,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao=item,
            quantidade=1, valor_unitario=Decimal("100.00"),
        )
        return orcamento

    def indice(self, resposta):
        html = resposta.content.decode()
        marca = '<script id="indiceOrcamentos" type="application/json">'
        inicio = html.index(marca) + len(marca)
        return json.loads(html[inicio:html.index("</script>", inicio)])

    def test_o_indice_cobre_o_filtro_inteiro_e_nao_so_a_pagina(self):
        """A LISTA VEM POR PÁGINA; O ÍNDICE, NÃO.

        Sem isto o navegador responderia "nada encontrado" sobre uma
        proposta que está na página seguinte.
        """
        for numero in range(30):
            self.proposta("Enchimento %02d" % numero)
        escondida = self.proposta("Zulmira Agulha no Palheiro")

        resposta = self.client.get("/orcamentos/", HTTP_HOST="interno.testserver")
        indice = self.indice(resposta)

        self.assertEqual(len(indice), 31)
        self.assertEqual(resposta.content.decode().count('<tr data-registro='), 25)
        self.assertIn(str(escondida.pk), [registro["i"] for registro in indice])

    def test_o_indice_acha_pelo_nome_sem_acento_pelo_numero_e_pelo_item(self):
        orcamento = self.proposta("Buffet Ação", item="Tobogã inflável")

        indice = self.indice(
            self.client.get("/orcamentos/", HTTP_HOST="interno.testserver")
        )
        texto = next(r["t"] for r in indice if r["i"] == str(orcamento.pk))

        # Os mesmos campos que a busca do servidor percorre.
        self.assertIn("buffet acao", texto)
        self.assertIn(str(orcamento.pk), texto)
        self.assertIn("toboga inflavel", texto)

    def test_cada_linha_se_identifica_para_o_filtro(self):
        orcamento = self.proposta("Buffet Alegria")

        html = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver"
        ).content.decode()

        self.assertIn('data-registro="%d"' % orcamento.pk, html)
        self.assertIn('data-filtro-indice="indiceOrcamentos"', html)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class TodasAsListasFiltramLocalmenteTests(TestCase):
    """Uma tela sem o índice volta a recarregar a página a cada palavra."""

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-listas", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)
        Cliente.objects.create(nome_cliente="Buffet Alegria")

    def test_as_tres_listas_mandam_o_indice_e_marcam_as_linhas(self):
        telas = {
            "/orcamentos/": "indiceOrcamentos",
            "/ordens-servico/": "indiceOrdens",
            "/clientes/": "indiceClientes",
        }
        for url, indice in telas.items():
            with self.subTest(tela=url):
                html = self.client.get(
                    url, HTTP_HOST="interno.testserver"
                ).content.decode()

                self.assertIn('id="%s" type="application/json"' % indice, html)
                self.assertIn('data-filtro-indice="%s"' % indice, html)
                self.assertIn("data-filtro-alvo=", html)

    def test_o_cliente_entra_no_indice_pelo_telefone_sem_mascara(self):
        """Quem procura "977776655" tem de achar "(11) 97777-6655"."""
        Cliente.objects.create(
            nome_cliente="Joana Ribeiro", telefone="(11) 97777-6655",
        )

        html = self.client.get(
            "/clientes/", HTTP_HOST="interno.testserver"
        ).content.decode()
        marca = '<script id="indiceClientes" type="application/json">'
        inicio = html.index(marca) + len(marca)
        indice = json.loads(html[inicio:html.index("</script>", inicio)])

        self.assertTrue(
            any("11977776655" in registro["t"] for registro in indice),
            "o número sem máscara não entrou no índice",
        )
