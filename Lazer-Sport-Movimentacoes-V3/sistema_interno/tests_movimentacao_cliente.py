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
            "tipo": Cliente.Tipo.COMERCIAL,
            "email": "kaio@example.com",
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        dados = resposta.json()
        self.assertEqual(Cliente.objects.get(pk=dados["cliente"]["valor"]).nome_cliente, "Kaio")

    def test_cliente_aparece_somente_quando_tipo_e_saida(self):
        resposta = self.client.get("/stock/", HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="movimentoClienteGrupo" hidden')
        self.assertContains(resposta, 'document.getElementById("movimentoClienteGrupo").hidden = !saida')
        self.assertContains(resposta, 'placeholder: "Buscar cliente cadastrado..."')

    def test_entrada_nao_guarda_cliente_residual(self):
        self.estoque.quantidade = 0
        self.estoque.saldo_valor = 0
        self.estoque.save()
        resposta = self.post("/stock/", {
            "action": "movimento", "id": self.estoque.pk,
            "tipo": "entrada", "quantidade": "2", "valor_unitario": "25,00",
            "cliente": self.marcos.pk,
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIsNone(MovimentoEstoque.objects.get().cliente)

    def test_busca_cliente_do_estoque(self):
        resposta = self.client.get(
            "/estoque/clientes/buscar/", {"q": "Marcos"},
            HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["opcoes"][0]["valor"], str(self.marcos.pk))

    def test_so_superusuario_exclui_ultima_movimentacao_e_restaura_saldo(self):
        movimento = MovimentoEstoque.registrar(
            self.estoque, "saida", 3, cliente=self.marcos,
        )
        resposta = self.post("/estoque/movimentacoes/", {
            "action": "delete_movimento", "movimento_id": movimento.pk,
            "confirmacao_exclusao": "CONFIRMAR",
        })
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 10)
        self.assertFalse(MovimentoEstoque.objects.exists())

        comum = User.objects.create_user("estoquista", password="x")
        self.client.force_login(comum)
        movimento = MovimentoEstoque.objects.create(
            estoque=self.estoque, tipo="ajuste", quantidade=2,
            quantidade_resultante=2,
        )
        resposta = self.post("/estoque/movimentacoes/", {
            "action": "delete_movimento", "movimento_id": movimento.pk,
            "confirmacao_exclusao": "CONFIRMAR",
        })
        self.assertIn(resposta.status_code, (302, 403))
        self.assertTrue(MovimentoEstoque.objects.filter(pk=movimento.pk).exists())

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
