"""A loja é do cliente; o painel é da equipe.

O QUE ORIGINOU ESTE ARQUIVO. A conta de quem trabalha na fábrica é um
`auth.User` como a de qualquer cliente, então o site tratava um gerente
como trata um comprador: carrinho, lista de desejos e "meus pedidos"
apareciam para ele. Não é enfeite fora de lugar --

  * pedido criado por conta interna entra na mesma fila de produção e no
    mesmo relatório de vendas, e não é de cliente nenhum quando alguém
    pergunta quem comprou;
  * carrinho e lista de desejos da equipe se misturam aos indicadores de
    interesse, que existem para dizer o que os CLIENTES querem.

Do outro lado da mesma regra: a equipe precisa CHEGAR ao site (conferir a
página que o cliente vai abrir) e voltar ao painel sem decorar endereço.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from sistema_interno.permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["testserver", "interno.testserver"])
class LojaSomenteDeClienteTests(TestCase):

    #: Uma de cada família de endereço da compra. A regra mora em
    #: `LojaSomenteDeClienteMiddleware.ROTAS_DE_COMPRA`; aqui se confere
    #: que ela vale de verdade, e não só no papel.
    ROTAS = ("/carrinho/", "/meus-pedidos/", "/lista-desejos/")

    def setUp(self):
        self.vendedor = User.objects.create_user(
            "vendedor", email="vendedor@example.com", password="x",
        )
        atribuir_funcoes(self.vendedor, ["vendas"])
        self.cliente = User.objects.create_user(
            "cliente", email="cliente@example.com", password="x",
        )
        perfil = self.cliente.perfil
        perfil.telefone = "11999990000"
        perfil.save()

    def test_conta_interna_nao_entra_no_carrinho_nem_nos_pedidos(self):
        self.client.force_login(self.vendedor)

        for rota in self.ROTAS:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta["Location"], "/")

    def test_superusuario_tambem_nao_compra_na_propria_loja(self):
        chefe = User.objects.create_superuser("chefe", "chefe@example.com", "x")
        self.client.force_login(chefe)

        self.assertEqual(self.client.get("/carrinho/").status_code, 302)

    def test_o_cliente_continua_com_a_loja_inteira(self):
        self.client.force_login(self.cliente)

        for rota in self.ROTAS:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertNotEqual(
                    (resposta.status_code, resposta.get("Location", "")),
                    (302, "/"),
                    "cliente não pode ser mandado embora da própria loja",
                )

    def test_visitante_sem_conta_continua_vendo_a_lista_de_desejos(self):
        """Ela funciona sem login -- é a porta de entrada, não um extra."""
        resposta = self.client.get("/lista-desejos/")

        self.assertNotEqual(resposta.get("Location", ""), "/")

    def test_chamada_de_javascript_recebe_json_e_nao_um_desvio(self):
        """Redirecionar um `fetch` devolve HTML no meio de um JSON.parse.

        O erro aparece na tela como "algo deu errado" e não explica nada;
        um 403 com texto diz o que houve.
        """
        self.client.force_login(self.vendedor)

        resposta = self.client.post(
            "/favoritos/alternar/",
            {"tipo": "desejo", "id": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertIn("interno", resposta.json()["erro"])

    def test_o_painel_nao_e_afetado_pela_regra_da_loja(self):
        """No subdomínio interno estes caminhos nem existem -- e a regra
        não pode inventar um desvio para dentro de casa."""
        self.client.force_login(self.vendedor)

        resposta = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)


@override_settings(ALLOWED_HOSTS=["testserver", "interno.testserver"])
class CaminhoEntreLojaEPainelTests(TestCase):
    """A equipe chega ao site, e volta do site, sem decorar endereço."""

    def setUp(self):
        self.vendedor = User.objects.create_user("vendedora", password="x")
        atribuir_funcoes(self.vendedor, ["vendas"])

    def test_o_painel_oferece_a_loja_a_toda_a_equipe(self):
        """O atalho vivia dentro do bloco da função Criação.

        Quem monta uma proposta e precisa conferir a página que o cliente
        vai abrir -- Vendas, Ambulante, Gestão -- não tinha caminho
        nenhum. O botão não dá permissão de nada: abre a vitrine, que é
        pública.
        """
        self.client.force_login(self.vendedor)

        html = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        ).content.decode()

        self.assertIn("Abrir a loja", html)

    def test_no_site_a_equipe_ve_o_painel_no_lugar_do_carrinho(self):
        self.client.force_login(self.vendedor)

        html = self.client.get("/").content.decode()

        self.assertIn("Painel da fábrica", html)
        self.assertNotIn('id="carrinho-float-btn"', html)
        # A folha de estilo cita as classes dos botões de qualquer jeito;
        # o que não pode existir é o LINK.
        self.assertNotIn('class="float-btn float-desejos"', html)
        self.assertNotIn('href="/meus-pedidos/#pedidos"', html)

    def test_o_cliente_ve_o_carrinho_e_nao_ve_o_painel(self):
        cliente = User.objects.create_user("compradora", password="x")
        perfil = cliente.perfil
        perfil.telefone = "11999990000"
        perfil.save()
        self.client.force_login(cliente)

        html = self.client.get("/").content.decode()

        self.assertIn('id="carrinho-float-btn"', html)
        self.assertNotIn("Painel da fábrica", html)
