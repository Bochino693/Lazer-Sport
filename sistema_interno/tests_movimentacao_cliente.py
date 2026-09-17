from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Cliente, EstoqueMaterial, Material, MovimentoEstoque


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class MovimentacaoClienteTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("gestor-mov", "mov@example.com", "x"))
        material = Material.objects.create(nome_material="Arduino Nano")
        self.estoque = EstoqueMaterial.objects.create(
            material=material, descricao_local="Gaveta A", quantidade=10,
            preco_fornecedor=25, saldo_valor=250,
        )
        self.marcos = Cliente.objects.create(nome_cliente="Marcos Top Games")

    def post(self, url, dados):
        return self.client.post(
            url, dados, HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_saida_subtrai_e_grava_cliente_data_e_responsavel(self):
        resposta = self.post("/stock/", {
            "action": "movimento", "id": self.estoque.pk,
            "tipo": "saida", "quantidade": "3",
            "cliente": self.marcos.pk, "motivo": "Envio ao cliente",
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 7)
        movimento = MovimentoEstoque.objects.get()
        self.assertEqual(movimento.cliente, self.marcos)
        self.assertIsNotNone(movimento.ocorrido_em)
        self.assertEqual(movimento.responsavel.username, "gestor-mov")

    def test_saida_sem_cliente_e_bloqueada_sem_alterar_saldo(self):
        resposta = self.post("/stock/", {
            "action": "movimento", "id": self.estoque.pk,
            "tipo": "saida", "quantidade": "2",
        })
        self.assertEqual(resposta.status_code, 400)
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 10)
        self.assertFalse(MovimentoEstoque.objects.exists())

    def test_cadastro_rapido_retorna_cliente_para_o_modal(self):
        resposta = self.post("/stock/", {
            "action": "save_cliente_rapido",
            "nome_cliente": "Kaio",
            "tipo_cliente": Cliente.Tipo.COMERCIAL,
            "telefone_cliente": "11999999999",
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        dados = resposta.json()
        self.assertEqual(Cliente.objects.get(pk=dados["id"]).nome_cliente, "Kaio")

    def test_setter_completa_saida_antiga(self):
        antigo = MovimentoEstoque.objects.create(
            estoque=self.estoque, tipo="saida", quantidade=2,
            quantidade_resultante=8,
        )
        resposta = self.post("/estoque/movimentacoes/", {
            "action": "associar_cliente",
            "movimento_id": antigo.pk,
            "cliente": self.marcos.pk,
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        antigo.refresh_from_db()
        self.assertEqual(antigo.cliente, self.marcos)
