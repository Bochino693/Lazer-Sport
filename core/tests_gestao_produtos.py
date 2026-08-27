"""Painel administrativo: peças de reposição e engajamento.

O que estes testes protegem:

  * a área só abre para quem é administrador de verdade;
  * a peça é cadastrada e publicada pelo painel, sem passar pelo Django;
  * exclusão exige o nome digitado — clique errado não apaga catálogo;
  * o ranking de curtidas conta interesse, não clique repetido.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Brinquedos,
    CategoriaPeca,
    Favorito,
    PecasReposicao,
)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class GestaoProdutosBaseTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="gestor",
            email="gestor@lazersport.com.br",
            password="senha-forte-123",
        )
        self.categoria = CategoriaPeca.objects.create(
            nome_categoria_peca="Motores",
        )
        self.peca = PecasReposicao.objects.create(
            nome="Motor 1/4 CV",
            descricao_peca="Motor para carrossel",
            preco_venda=Decimal("450.00"),
        )
        self.peca.categoria_peca.add(self.categoria)
        self.url = reverse("pecas_admin", urlconf="sistema_interno.urls")
        self.host = "interno.testserver"

    def get(self, url, data=None):
        return self.client.get(url, data or {}, HTTP_HOST=self.host)

    def post(self, url, data):
        return self.client.post(url, data, HTTP_HOST=self.host)


class AcessoTests(GestaoProdutosBaseTests):

    def test_visitante_nao_entra(self):
        resposta = self.get(self.url)

        self.assertRedirects(resposta, "/login/inner/", fetch_redirect_response=False)

    def test_cliente_comum_nao_entra(self):
        cliente = User.objects.create_user(
            username="cliente",
            password="123456789a",
        )
        # Com telefone em branco o middleware desvia antes: o que este
        # teste quer ver é o bloqueio da área administrativa.
        cliente.perfil.telefone = "(11)91234-5678"
        cliente.perfil.save(update_fields=["telefone"])
        self.client.login(username="cliente", password="123456789a")

        resposta = self.get(self.url)

        self.assertRedirects(resposta, "/login/inner/", fetch_redirect_response=False)

    def test_administrador_entra(self):
        self.client.force_login(self.admin)

        resposta = self.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Motor 1/4 CV")


class CadastroDePecaTests(GestaoProdutosBaseTests):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_cadastra_peca_nova(self):
        resposta = self.post(self.url, {
            "action": "save",
            "resposta": "json",
            "nome": "Correia dentada",
            "descricao_peca": "Correia para motor do carrossel",
            "preco_fornecedor": "100,00",
            "categorias": [self.categoria.id],
            "ativo": "1",
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["status"], "sucesso")

        nova = PecasReposicao.objects.get(nome="Correia dentada")
        self.assertTrue(nova.ativo)
        self.assertEqual(list(nova.categoria_peca.all()), [self.categoria])
        # Sem preço de venda, o modelo calcula fornecedor + 12%.
        self.assertEqual(nova.preco_venda, Decimal("112.00"))

    def test_edita_peca_existente(self):
        self.post(self.url, {
            "action": "save",
            "resposta": "json",
            "id": self.peca.id,
            "nome": "Motor 1/2 CV",
            "descricao_peca": "Motor reforçado",
            "preco_venda": "1.250,00",
        })

        self.peca.refresh_from_db()
        self.assertEqual(self.peca.nome, "Motor 1/2 CV")
        self.assertEqual(self.peca.preco_venda, Decimal("1250.00"))
        # Sem o campo "ativo" no formulário, a peça sai do site.
        self.assertFalse(self.peca.ativo)

    def test_nome_vazio_e_recusado(self):
        resposta = self.post(self.url, {
            "action": "save",
            "resposta": "json",
            "nome": "  ",
            "descricao_peca": "Qualquer coisa",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(PecasReposicao.objects.count(), 1)

    def test_preco_invalido_e_recusado(self):
        resposta = self.post(self.url, {
            "action": "save",
            "resposta": "json",
            "nome": "Peça torta",
            "descricao_peca": "Descrição",
            "preco_venda": "cento e vinte",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(PecasReposicao.objects.count(), 1)

    def test_publicar_e_esconder_pela_lista(self):
        self.peca.ativo = True
        self.peca.save(update_fields=["ativo"])

        self.post(self.url, {
            "action": "alternar_ativo",
            "resposta": "json",
            "id": self.peca.id,
        })

        self.peca.refresh_from_db()
        self.assertFalse(self.peca.ativo)

    def test_exclusao_exige_a_frase_certa(self):
        resposta = self.post(self.url, {
            "action": "delete",
            "resposta": "json",
            "id": self.peca.id,
            "confirmacao_exclusao": "apagar",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(
            PecasReposicao.objects.filter(pk=self.peca.pk).exists()
        )

    def test_exclusao_com_a_frase_certa(self):
        self.post(self.url, {
            "action": "delete",
            "resposta": "json",
            "id": self.peca.id,
            "confirmacao_exclusao": f"CONFIRMAR EXCLUSÃO {self.peca.nome}",
        })

        self.assertFalse(
            PecasReposicao.objects.filter(pk=self.peca.pk).exists()
        )

    def test_categoria_nova_pelo_painel(self):
        resposta = self.post(self.url, {
            "action": "categoria",
            "resposta": "json",
            "nome_categoria_peca": "Rolamentos",
        })

        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertTrue(
            CategoriaPeca.objects.filter(
                nome_categoria_peca="Rolamentos",
            ).exists()
        )

    def test_categoria_repetida_nao_duplica(self):
        self.post(self.url, {
            "action": "categoria",
            "resposta": "json",
            "nome_categoria_peca": "motores",
        })

        self.assertEqual(CategoriaPeca.objects.count(), 1)

    def test_lista_paginaa_e_revalida_pelo_etag(self):
        PecasReposicao.objects.bulk_create([
            PecasReposicao(nome=f"Peça {numero:02d}", descricao_peca="Teste")
            for numero in range(30)
        ])
        primeira = self.get(self.url)
        self.assertEqual(len(primeira.context["pecas"]), 18)
        self.assertContains(primeira, "Paginação de peças")
        etag = primeira["ETag"]

        igual = self.client.get(
            self.url,
            HTTP_HOST=self.host,
            HTTP_IF_NONE_MATCH=etag,
        )
        self.assertEqual(igual.status_code, 304)
        self.assertIn("must-revalidate", igual["Cache-Control"])

        with self.captureOnCommitCallbacks(execute=True):
            PecasReposicao.objects.create(nome="Peça nova", descricao_peca="Nova")
        alterada = self.client.get(
            self.url,
            HTTP_HOST=self.host,
            HTTP_IF_NONE_MATCH=etag,
        )
        self.assertEqual(alterada.status_code, 200)
        self.assertNotEqual(alterada["ETag"], etag)

    def test_modal_tem_mascara_monetaria_e_seletor_arejado(self):
        resposta = self.get(self.url)
        self.assertContains(resposta, 'data-mascara="moeda"', count=2)
        self.assertContains(resposta, 'id="buscarCategoriaPeca"')
        self.assertContains(resposta, 'id="modalExcluirPeca"')


class CatalogoBrinquedosResponsivoTests(GestaoProdutosBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.url = reverse("brinquedos_admin", urlconf="sistema_interno.urls")

    def test_lista_paginaa_em_lotes_menores(self):
        Brinquedos.objects.bulk_create([
            Brinquedos(
                nome_brinquedo=f"Brinquedo {numero:02d}",
                descricao="Teste",
                avaliacao=Decimal("5.00"),
                voltz="Bivolt",
            )
            for numero in range(24)
        ])
        resposta = self.get(self.url)
        self.assertEqual(len(resposta.context["brinquedos"]), 18)
        self.assertGreater(resposta.context["page_obj"].paginator.num_pages, 1)

    def test_modal_formata_dinheiro_metros_e_opcoes(self):
        resposta = self.get(self.url)
        self.assertContains(resposta, 'data-mascara="moeda"')
        self.assertContains(resposta, 'data-mascara="medida"', count=3)
        self.assertContains(resposta, 'data-options-tools="categoryGrid"')
        self.assertContains(resposta, 'data-options-tools="tagGrid"')


class EngajamentoAdminTests(GestaoProdutosBaseTests):

    def setUp(self):
        super().setUp()
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Piscina de bolinhas",
            descricao="Piscina 3x3",
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        Favorito.objects.create(
            tipo=Favorito.Tipo.CURTIDA,
            brinquedo=self.brinquedo,
            dispositivo="a" * 32,
            origem=Favorito.Origem.APP,
        )
        Favorito.objects.create(
            tipo=Favorito.Tipo.DESEJO,
            peca=self.peca,
            dispositivo="b" * 32,
        )
        self.client.force_login(self.admin)

    def test_painel_mostra_ranking_e_totais(self):
        resposta = self.get(reverse("engajamento_admin", urlconf="sistema_interno.urls"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["total_curtidas"], 1)
        self.assertEqual(resposta.context["total_desejos"], 1)
        self.assertEqual(resposta.context["total_pelo_app"], 1)
        self.assertEqual(resposta.context["total_pelo_site"], 1)
        self.assertEqual(resposta.context["aparelhos"], 2)
        self.assertContains(resposta, "Piscina de bolinhas")
        self.assertContains(resposta, "Motor 1/4 CV")

    def test_periodo_filtra_o_que_entra_na_conta(self):
        resposta = self.get(
            reverse("engajamento_admin", urlconf="sistema_interno.urls"),
            {"periodo": "7dias"},
        )

        # Tudo foi marcado agora, então continua aparecendo.
        self.assertEqual(resposta.context["periodo"], "7dias")
        self.assertEqual(resposta.context["total_curtidas"], 1)

    def test_painel_nao_abre_para_cliente(self):
        self.client.logout()
        visitante = User.objects.create_user(
            username="visitante",
            password="123456789a",
        )
        visitante.perfil.telefone = "(11)91234-5678"
        visitante.perfil.save(update_fields=["telefone"])
        self.client.login(username="visitante", password="123456789a")

        resposta = self.get(reverse("engajamento_admin", urlconf="sistema_interno.urls"))

        self.assertRedirects(resposta, "/login/inner/", fetch_redirect_response=False)
