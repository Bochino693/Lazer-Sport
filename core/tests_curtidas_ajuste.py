"""O ajuste de curtidas do painel: adicionar ou remover curtidas de um produto.

O que se garante: o número público é curtidas de verdade + ajuste, nunca
abaixo de zero, igual no serviço (core/favoritos.py), na listagem e na
API; o ajuste entra no ranking geral da tela Curtidas e desejos e fica de
fora dos recortes por período; só o superadministrador grava; e as
curtidas das pessoas não são tocadas.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from . import favoritos as servico
from .models import Brinquedos, Favorito, PecasReposicao

from sistema_interno.permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AjusteDeCurtidasTests(TestCase):
    def setUp(self):
        # a API do catálogo é cacheada: nada daqui pode sobrar para o teste seguinte
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)
        self.toy = Brinquedos.objects.create(nome_brinquedo="Strike Kids", descricao="x", avaliacao=5, voltz="220V")
        self.peca = PecasReposicao.objects.create(nome="Botão", descricao_peca="x")
        for i in range(3):
            Favorito.objects.create(tipo="curtida", brinquedo=self.toy, dispositivo=f"d{i}", origem="app")
        self.chefe = User.objects.create_superuser("chefe", "c@example.com", "senha-segura")
        self.criador = User.objects.create_user("criador", password="senha-segura", is_staff=True)
        atribuir_funcoes(self.criador, ["criacao"])

    def test_total_soma_o_ajuste_e_nunca_fica_negativo(self):
        self.assertEqual(servico.total_curtidas(self.toy), 3)
        self.toy.ajuste_curtidas = 40
        self.toy.save()
        self.assertEqual(servico.total_curtidas(self.toy), 43)
        self.assertEqual(servico.contagem_curtidas([self.toy]), {self.toy.pk: 43})
        self.assertEqual(servico.contagem_curtidas([self.peca]), {self.peca.pk: 0})
        self.toy.ajuste_curtidas = -10
        self.toy.save()
        self.assertEqual(servico.total_curtidas(self.toy), 0)
        self.assertEqual(servico.curtidas_reais(self.toy), 3)  # as curtidas das pessoas continuam lá
        self.assertEqual(Favorito.objects.filter(brinquedo=self.toy).count(), 3)

    def test_a_api_mostra_o_mesmo_numero(self):
        self.toy.ajuste_curtidas = 7
        self.toy.save()
        resposta = self.client.get(f"/api/v1/brinquedos/{self.toy.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json().get("total_curtidas", resposta.json().get("curtidas")), 10)

    def test_so_o_superadministrador_ajusta(self):
        self.client.force_login(self.criador)
        pagina = self.client.get("/site/engajamento/", HTTP_HOST="interno.testserver")
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, "Adicionar ou remover curtidas")
        self.client.post("/site/engajamento/", {"produto": "brinquedo", "id": self.toy.pk, "ajuste": "50"}, HTTP_HOST="interno.testserver")
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.ajuste_curtidas, 0)

    def test_superadministrador_adiciona_e_remove(self):
        self.client.force_login(self.chefe)
        pagina = self.client.get("/site/engajamento/", HTTP_HOST="interno.testserver")
        self.assertContains(pagina, "Adicionar ou remover curtidas")
        self.assertContains(pagina, 'name="ajuste" value="0"')

        resposta = self.client.post("/site/engajamento/", {"produto": "brinquedo", "id": self.toy.pk, "ajuste": "50"}, HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 302)
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.ajuste_curtidas, 50)
        pagina = self.client.get("/site/engajamento/", HTTP_HOST="interno.testserver")
        self.assertContains(pagina, 'name="ajuste" value="50"')
        self.assertContains(pagina, "<strong class=\"eng-total\">53</strong>", html=False)

        self.client.post("/site/engajamento/", {"produto": "peca", "id": self.peca.pk, "ajuste": "-5"}, HTTP_HOST="interno.testserver")
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.ajuste_curtidas, -5)
        self.assertEqual(servico.total_curtidas(self.peca), 0)

        resposta = self.client.post("/site/engajamento/", {"produto": "brinquedo", "id": self.toy.pk, "ajuste": "muitas"}, HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 302)
        self.toy.refresh_from_db()
        self.assertEqual(self.toy.ajuste_curtidas, 50)

    def test_ranking_geral_usa_o_ajuste_e_o_periodo_nao(self):
        outro = Brinquedos.objects.create(nome_brinquedo="Pembolim", descricao="x", avaliacao=4, voltz="110V", ajuste_curtidas=100)
        self.client.force_login(self.chefe)
        geral = self.client.get("/site/engajamento/?periodo=geral", HTTP_HOST="interno.testserver")
        itens = geral.context["brinquedos_curtidos"]
        self.assertEqual([i["nome"] for i in itens][:2], ["Pembolim", "Strike Kids"])
        self.assertEqual(itens[0]["total"], 100)
        semana = self.client.get("/site/engajamento/?periodo=7dias", HTTP_HOST="interno.testserver")
        self.assertEqual([i["nome"] for i in semana.context["brinquedos_curtidos"]], ["Strike Kids"])
        self.assertTrue(outro.pk)
