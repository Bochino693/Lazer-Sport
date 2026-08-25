"""Orçamento visto de dentro: catálogo, cadastro na hora e envio.

O painel responde no subdomínio interno, então todo teste aqui usa
HTTP_HOST="interno.testserver" — sem isso o SubdomainURLMiddleware não
liga `is_interno` e a view devolve um desvio para a loja, que é o mesmo
que o usuário veria.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Brinquedos, CategoriasBrinquedos

from .models import ItemOrcamento, Orcamento, ProdutoInterno


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class OrcamentoInternoTests(TestCase):

    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

        self.categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Infláveis",
        )
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Cama elástica",
            descricao="Cama elástica 3m",
            valor_brinquedo=Decimal("280.00"),
            avaliacao=Decimal("5.00"),
            voltz="110",
        )

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # -------------------------------------------------------- catálogo
    def test_tela_oferece_o_catalogo_do_site(self):
        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(self.brinquedo, resposta.context["brinquedos"])

        # O seletor é montado no navegador a partir deste payload, e não
        # em HTML por linha: a tela abre com uma linha e ganha outras
        # conforme a pessoa digita, e recriar centenas de <option> a cada
        # linha travava a digitação no tablet. Então é o payload que
        # precisa trazer o catálogo -- procurar o nome no HTML acharia
        # só a versão escapada pelo json_script ("el\u00e1stica").
        nomes = [b["nome"] for b in resposta.context["catalogo_dados"]]
        self.assertIn("Cama elástica", nomes)

        # e o atalho de cadastrar na hora está na tela
        self.assertContains(resposta, "Novo brinquedo")

    def test_catalogo_inclui_o_que_nao_esta_na_loja(self):
        """A vitrine é um recorte; orçamento alcança o cadastro inteiro."""
        fora = Brinquedos.objects.create(
            nome_brinquedo="Tobogã antigo",
            descricao="Fora da vitrine",
            avaliacao=Decimal("0.00"),
            voltz="220",
            exibir_na_loja=False,
        )
        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        self.assertIn(fora, resposta.context["brinquedos"])

    def test_item_salvo_fica_ligado_ao_brinquedo(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Cama elástica","brinquedo":"%s",'
                '"quantidade":"2","valor_unitario":"280,00"}]' % self.brinquedo.id
            ),
        })

        self.assertEqual(resposta.status_code, 200)
        item = ItemOrcamento.objects.get()
        self.assertEqual(item.brinquedo, self.brinquedo)
        self.assertIsNone(item.produto)
        self.assertEqual(item.subtotal, Decimal("560.00"))

    def test_linha_com_catalogo_e_producao_fica_so_com_o_catalogo(self):
        """São origens exclusivas: gravar as duas criaria item inválido."""
        produto = ProdutoInterno.objects.create(nome="Cama — versão fábrica")

        self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Cama","brinquedo":"%s","produto":"%s",'
                '"quantidade":"1","valor_unitario":"280,00"}]'
                % (self.brinquedo.id, produto.id)
            ),
        })

        item = ItemOrcamento.objects.get()
        self.assertEqual(item.brinquedo, self.brinquedo)
        self.assertIsNone(item.produto)

    def test_item_sem_catalogo_ainda_aceita_produto_de_producao(self):
        produto = ProdutoInterno.objects.create(nome="Máquina de algodão doce")

        self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Algodão doce","produto":"%s",'
                '"quantidade":"1","valor_unitario":"150,00"}]' % produto.id
            ),
        })

        item = ItemOrcamento.objects.get()
        self.assertEqual(item.produto, produto)
        self.assertIsNone(item.brinquedo)

    # ------------------------------------------- cadastrar sem sair daqui
    def test_cadastra_brinquedo_novo_e_devolve_para_a_linha(self):
        resposta = self.post({
            "action": "brinquedo_novo",
            "nome": "Piscina de bolinhas",
            "valor": "340,00",
            "categoria": self.categoria.id,
        })

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso")

        novo = Brinquedos.objects.get(nome_brinquedo="Piscina de bolinhas")
        self.assertEqual(dados["brinquedo"]["id"], novo.id)
        self.assertEqual(dados["brinquedo"]["valor"], "340,00")
        self.assertEqual(novo.valor_brinquedo, Decimal("340.00"))
        self.assertIn(self.categoria, novo.categorias_brinquedos.all())

    def test_brinquedo_novo_nasce_fora_da_vitrine(self):
        """Publicar é decisão de quem cuida do site, com foto e texto."""
        self.post({"action": "brinquedo_novo", "nome": "Touro mecânico"})

        novo = Brinquedos.objects.get(nome_brinquedo="Touro mecânico")
        self.assertFalse(novo.exibir_na_loja)

    def test_nao_duplica_brinquedo_existente(self):
        # A diferença de caixa é só em letra ASCII de propósito. O SQLite
        # destes testes dobra maiúscula/minúscula apenas em ASCII, então
        # "ELÁSTICA" x "elástica" não casaria aqui -- no PostgreSQL da
        # produção casa. Testar com "C"/"c" verifica a regra sem depender
        # de qual banco está rodando.
        resposta = self.post({"action": "brinquedo_novo", "nome": "cama elástica"})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Brinquedos.objects.count(), 1)

    def test_brinquedo_novo_exige_nome(self):
        resposta = self.post({"action": "brinquedo_novo", "nome": "   "})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Brinquedos.objects.count(), 1)

    # -------------------------------------------------------- envio
    def _orcamento_com_item(self):
        orcamento = Orcamento.objects.create(nome_cliente="Fulano")
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Cama elástica",
            brinquedo=self.brinquedo,
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )
        return orcamento

    def test_enviar_devolve_o_link_do_site_publico(self):
        orcamento = self._orcamento_com_item()

        resposta = self.post({"action": "enviar", "id": orcamento.id})
        dados = resposta.json()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(orcamento.token, dados["link"])
        # o link é do site do cliente, nunca do subdomínio interno
        self.assertNotIn("interno.", dados["link"])

        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.ENVIADO)
        self.assertIsNotNone(orcamento.enviado_em)

    def test_enviar_orcamento_vazio_e_recusado(self):
        """Link para uma proposta sem itens é constrangimento na frente do cliente."""
        vazio = Orcamento.objects.create(nome_cliente="Fulano")

        resposta = self.post({"action": "enviar", "id": vazio.id})

        self.assertEqual(resposta.status_code, 400)
        vazio.refresh_from_db()
        self.assertEqual(vazio.status, Orcamento.Status.RASCUNHO)

    def test_reenviar_nao_reescreve_a_data_de_envio(self):
        orcamento = self._orcamento_com_item()

        self.post({"action": "enviar", "id": orcamento.id})
        orcamento.refresh_from_db()
        primeira = orcamento.enviado_em

        self.post({"action": "enviar", "id": orcamento.id})
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.enviado_em, primeira)

    # ------------------------------------------------------- a vencer
    def test_tela_separa_os_que_vencem_em_ate_tres_dias(self):
        perto = Orcamento.objects.create(
            nome_cliente="Vence logo",
            status=Orcamento.Status.ENVIADO,
            validade=timezone.localdate() + timedelta(days=2),
        )
        longe = Orcamento.objects.create(
            nome_cliente="Tem tempo",
            status=Orcamento.Status.ENVIADO,
            validade=timezone.localdate() + timedelta(days=20),
        )
        aprovado = Orcamento.objects.create(
            nome_cliente="Já fechou",
            status=Orcamento.Status.APROVADO,
            validade=timezone.localdate() + timedelta(days=1),
        )

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        vencendo = resposta.context["vencendo"]

        self.assertIn(perto, vencendo)
        self.assertNotIn(longe, vencendo)
        # proposta já aprovada não é cobrança pendente
        self.assertNotIn(aprovado, vencendo)

    def test_busca_orcamento_pelo_numero(self):
        encontrado = Orcamento.objects.create(nome_cliente="Cliente pelo número")
        Orcamento.objects.create(nome_cliente="Outro cliente")

        resposta = self.client.get(
            self.URL,
            {"q": str(encontrado.pk)},
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(list(resposta.context["orcamentos"]), [encontrado])

    # -------------------------------------------------------- acesso
    def test_colaborador_sem_gerencia_nao_entra(self):
        operador = User.objects.create_user(
            username="operador",
            password="senha-segura",
            is_staff=True,
        )
        self.client.force_login(operador)

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("producao", resposta["Location"])
