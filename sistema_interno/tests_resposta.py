"""A resposta JSON do painel não pode mentir sobre o resultado.

POR QUE ESTE ARQUIVO EXISTE. A ação de enviar orçamento passava a
situação do registro como `status=...`. No dicionário final isso ocupava
a chave que diz se a requisição deu certo, e a resposta saía com
`"status": "rascunho"`. O JavaScript confere `json.status !== "sucesso"`,
então tratava um envio bem sucedido como falha: o link da proposta nunca
aparecia e a mensagem de sucesso ia parar na tarja vermelha.

O servidor respondia 200 e todos os testes de servidor passavam — por
isso o problema durou. Estes testes olham para o formato da resposta, que
é o contrato entre as duas metades do painel.
"""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from core.models import Brinquedos
from decimal import Decimal

from .models import ItemOrcamento, Orcamento


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class RespostaDoPainelTests(TestCase):

    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Cama elástica",
            descricao="Cama elástica 3m",
            valor_brinquedo=Decimal("280.00"),
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        self.orcamento = Orcamento.objects.create(
            nome_cliente="Festa da Ana",
            whatsapp_cliente="(11) 99999-8888",
            email_cliente="ana@example.com",
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            descricao="Cama elástica",
            brinquedo=self.brinquedo,
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_enviar_responde_sucesso_de_verdade(self):
        """O bug: a situação do orçamento ocupava a chave do resultado."""
        resposta = self.post({"action": "enviar", "id": self.orcamento.pk})

        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso")
        self.assertEqual(dados["situacao"], Orcamento.Status.ENVIADO)

    def test_enviar_devolve_o_link_publico(self):
        dados = self.post({
            "action": "enviar",
            "id": self.orcamento.pk,
        }).json()

        self.orcamento.refresh_from_db()
        self.assertIn(self.orcamento.token, dados["link"])
        self.assertTrue(dados["link"].startswith("http"))
        # O link do cliente NUNCA pode apontar para o subdomínio interno:
        # ele abriria numa tela de login de equipe.
        self.assertNotIn("interno.", dados["link"])

    def test_enviar_devolve_o_endereco_da_previa(self):
        dados = self.post({
            "action": "enviar",
            "id": self.orcamento.pk,
        }).json()

        self.assertIn("/previa/", dados["preview_url"])

    def test_extra_com_nome_reservado_nao_derruba_o_resultado(self):
        """Proteção do mixin, testada direto na fonte."""
        from .views import RespostaJSONMixin

        class Fake(RespostaJSONMixin):
            rota_padrao = "orcamentos_inner"

        pedido = RequestFactory().post(
            "/orcamentos/",
            {},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        resposta = Fake().sucesso(pedido, "deu certo", status="rascunho", msg="x")
        import json as _json

        corpo = _json.loads(resposta.content)
        self.assertEqual(corpo["status"], "sucesso")
        self.assertEqual(corpo["msg"], "deu certo")
        self.assertEqual(corpo["status_do_registro"], "rascunho")
        self.assertEqual(corpo["msg_do_registro"], "x")
