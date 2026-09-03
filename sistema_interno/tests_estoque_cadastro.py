"""Cadastrar material, tipo e fornecedor sem sair do lançamento.

O DEFEITO QUE ORIGINOU ISTO. A tela de estoque exigia escolher um
material que já existisse, e oferecia um link: "Material novo? Cadastre
em Materiais". Quem estava lançando a compra de uma lona teria de
abandonar o formulário meio preenchido, cadastrar na outra tela, voltar e
digitar tudo de novo.

Na prática ninguém faz isso -- escolhe um material parecido que já existe
e segue. O resultado é o defeito mais caro desta tela: o saldo some para
dentro do item errado, e a lista de reposição passa a mentir.

As regras continuam sendo UMAS SÓ (`CadastrosDeEstoqueMixin`): duas
portas para o mesmo cadastro só valem enquanto forem o mesmo cadastro.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import EstoqueMaterial, Fornecedor, Material, TipoMaterial


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class CadastroDentroDoEstoqueTests(TestCase):

    URL = "/stock/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            "gestor-estoque", "estoque@example.com", "x",
        )
        self.client.force_login(self.gestor)

    def post(self, dados):
        return self.client.post(
            self.URL, dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_a_tela_de_estoque_cadastra_material_e_devolve_para_a_linha(self):
        tipo = TipoMaterial.objects.create(descricao="Lona")

        dados = self.post({
            "action": "save_material",
            "nome_material": "Lona PVC 0,45 mm",
            "descricao": "Azul, para piscina de bolinhas",
            "codigo_interno": "LN-045",
            "tipo_material": tipo.pk,
            "unidade": "m2",
            "ativo": "on",
        }).json()

        material = Material.objects.get(nome_material="Lona PVC 0,45 mm")
        self.assertEqual(material.tipo_material, tipo)
        self.assertEqual(material.unidade, "m2")
        # id E nome: é o que faz o material aparecer JÁ ESCOLHIDO na
        # linha, sem recarregar a tela e perder o lançamento.
        self.assertEqual(dados["id"], material.pk)
        self.assertEqual(dados["nome"], "Lona PVC 0,45 mm")

    def test_a_tela_de_estoque_cadastra_tipo_e_fornecedor(self):
        tipo = self.post({"action": "save_tipo", "descricao": "Motor"}).json()
        fornecedor = self.post({
            "action": "save_fornecedor",
            "nome": "Lonas do Brás",
            "telefone": "(11) 3333-4444",
            "ativo": "on",
        }).json()

        self.assertEqual(TipoMaterial.objects.get().descricao, "Motor")
        self.assertEqual(Fornecedor.objects.get().nome, "Lonas do Brás")
        self.assertEqual(tipo["nome"], "Motor")
        self.assertEqual(fornecedor["nome"], "Lonas do Brás")

    def test_o_lancamento_completo_acontece_em_uma_visita_so(self):
        """O caminho inteiro: tipo, material, fornecedor e o item."""
        tipo = self.post({"action": "save_tipo", "descricao": "Lona"}).json()
        material = self.post({
            "action": "save_material",
            "nome_material": "Lona PVC 0,45 mm",
            "tipo_material": tipo["id"],
            "unidade": "m2",
            "ativo": "on",
        }).json()
        fornecedor = self.post({
            "action": "save_fornecedor", "nome": "Lonas do Brás", "ativo": "on",
        }).json()

        resposta = self.post({
            "action": "save",
            "material": material["id"],
            "fornecedor": fornecedor["id"],
            "descricao_local": "Galpão A, prateleira 3",
            "quantidade": "40",
            "preco_fornecedor": "1.250,00",
            "estoque_minimo": "10",
        })

        self.assertEqual(resposta.status_code, 200, resposta.content)
        item = EstoqueMaterial.objects.get()
        self.assertEqual(item.material.nome_material, "Lona PVC 0,45 mm")
        self.assertEqual(item.fornecedor.nome, "Lonas do Brás")
        self.assertEqual(item.quantidade, 40)
        self.assertEqual(item.preco_fornecedor, Decimal("1250.00"))

    def test_as_regras_sao_as_mesmas_das_duas_portas(self):
        """Unidade inválida é recusada aqui como é recusada em Materiais.

        Se a segunda porta aceitasse o que a primeira recusa, ela seria a
        que estraga o cadastro -- e ninguém saberia por qual delas o dado
        ruim entrou.
        """
        for url in (self.URL, "/estoque/materiais/"):
            with self.subTest(url=url):
                resposta = self.client.post(
                    url,
                    {
                        "action": "save_material",
                        "nome_material": "Material torto",
                        "unidade": "parsec",
                    },
                    HTTP_HOST="interno.testserver",
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(resposta.status_code, 400)

        self.assertFalse(Material.objects.exists())

    def test_a_janela_de_material_novo_esta_na_tela_de_estoque(self):
        """Sem os campos no HTML, o atalho não existe para quem usa."""
        html = self.client.get(
            self.URL, HTTP_HOST="interno.testserver",
        ).content.decode()

        self.assertIn('id="modalMaterialRapido"', html)
        self.assertIn('id="modalTipoRapido"', html)
        self.assertIn('id="modalFornecedorRapido"', html)
        # E a unidade de medida precisa estar preenchida: sem a lista, o
        # material rápido nasceria sempre "Unidade" e a lona entraria
        # contada em peça.
        self.assertIn('name="unidade"', html)
        self.assertIn('value="m2"', html)
