"""Promoções com vários brinquedos, a tela nova do painel e o quadro da home.

O que estes testes protegem:

  * a promoção guarda vários brinquedos: o primeiro escolhido é o principal
    (a foto, o carrinho e a divulgação saem dele) e os outros ficam em
    `brinquedos_extras`; o preço vale para o conjunto, comparado com a soma
    dos preços de tabela (`preco_tabela`, `desconto_percentual`);
  * o painel salva um ou vários brinquedos, liga e desliga a promoção pelo
    cartão (resposta em JSON) e exclui sem pedir para digitar nada;
  * a tela do painel não tem mais o <select> de brinquedos: a escolha é a
    grade, com os brinquedos (foto, preço, categorias) num JSON na página;
  * a página pública da promoção lista todos os brinquedos e o preço do
    conjunto; a divulgação cita todos;
  * o quadro inicial da home gira as promoções entre os brinquedos em
    destaque (brinquedo, promoção, brinquedo...).
"""

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Brinquedos, Promocoes
from .views import intercalar_vitrine

INTERNO = {"HTTP_HOST": "interno.testserver"}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.equipe = User.objects.create_superuser("criacao", "criacao@exemplo.com", "x")
        self.brinquedos = [
            Brinquedos.objects.create(
                nome_brinquedo=nome, descricao=f"Descrição do {nome}",
                imagem_brinquedo=f"brinquedos/{i}.jpg", avaliacao=Decimal("4.5"),
                valor_brinquedo=Decimal(valor), exibir_na_loja=True,
            )
            for i, (nome, valor) in enumerate([
                ("Air Game Kids", "9000.00"),
                ("Basquete Street", "12000.00"),
                ("Pega Toupeira", "4000.00"),
            ])
        ]

    def tearDown(self):
        cache.clear()

    def painel(self, dados, **extra):
        self.client.force_login(self.equipe)
        resposta = self.client.post("/site/promocoes/", dados, **INTERNO, **extra)
        self.client.logout()
        return resposta


class ModeloTests(Base):
    def test_conjunto_soma_a_tabela_e_calcula_o_desconto(self):
        air, basquete, toupeira = self.brinquedos
        promocao = Promocoes.objects.create(
            descricao="Pacote", brinquedos=air, preco_promocao=Decimal("20000.00"), ativo=True,
        )
        promocao.brinquedos_extras.set([basquete, air])  # o principal repetido não conta duas vezes

        self.assertEqual([b.pk for b in promocao.todos_brinquedos], [air.pk, basquete.pk])
        self.assertEqual(promocao.preco_tabela, Decimal("21000.00"))
        self.assertEqual(promocao.desconto_percentual, 5)

    def test_um_brinquedo_so_continua_como_antes(self):
        promocao = Promocoes.objects.create(
            descricao="Só um", brinquedos=self.brinquedos[2], preco_promocao=Decimal("3600.00"), ativo=True,
        )
        self.assertEqual(promocao.preco_tabela, Decimal("4000.00"))
        self.assertEqual(promocao.desconto_percentual, 10)


class PainelTests(Base):
    def test_salva_varios_brinquedos_o_primeiro_e_o_principal(self):
        air, basquete, toupeira = self.brinquedos
        resposta = self.painel({
            "acao": "criar", "descricao": "Leve 3 com desconto",
            "brinquedos": [str(toupeira.pk), str(air.pk), str(basquete.pk)],
            "preco_promocao": "22000.00", "ativo": "on",
        })

        self.assertEqual(resposta.status_code, 302)
        promocao = Promocoes.objects.get()
        self.assertEqual(promocao.brinquedos, toupeira)
        self.assertEqual(set(promocao.brinquedos_extras.values_list("pk", flat=True)), {air.pk, basquete.pk})
        self.assertEqual(promocao.preco_promocao, Decimal("22000.00"))

    def test_editar_troca_os_brinquedos(self):
        air, basquete, toupeira = self.brinquedos
        promocao = Promocoes.objects.create(descricao="X", brinquedos=air, preco_promocao=Decimal("8000"), ativo=True)
        promocao.brinquedos_extras.set([basquete, toupeira])

        self.painel({
            "acao": "editar", "promocao_id": promocao.pk, "descricao": "Só o basquete",
            "brinquedos": [str(basquete.pk)], "preco_promocao": "10.990,00", "ativo": "on",
        })

        promocao.refresh_from_db()
        self.assertEqual(promocao.brinquedos, basquete)
        self.assertFalse(promocao.brinquedos_extras.exists())
        self.assertEqual(promocao.preco_promocao, Decimal("10990.00"))

    def test_sem_brinquedo_nao_salva(self):
        self.painel({"acao": "criar", "descricao": "Nada", "preco_promocao": "100", "ativo": "on"})
        self.assertFalse(Promocoes.objects.exists())

    def test_liga_e_desliga_pelo_cartao(self):
        promocao = Promocoes.objects.create(
            descricao="X", brinquedos=self.brinquedos[0], preco_promocao=Decimal("8000"), ativo=True,
        )
        resposta = self.painel(
            {"acao": "alternar", "promocao_id": promocao.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"ok": True, "ativo": False})
        promocao.refresh_from_db()
        self.assertFalse(promocao.ativo)

    def test_excluir_sem_digitar_nada(self):
        promocao = Promocoes.objects.create(
            descricao="X", brinquedos=self.brinquedos[0], preco_promocao=Decimal("8000"), ativo=True,
        )
        # a janela manda a confirmação sozinha (campo escondido)
        self.painel({"acao": "excluir", "promocao_id": promocao.pk, "confirmacao": "EXCLUIR"})
        self.assertFalse(Promocoes.objects.exists())

    def test_tela_sem_select_e_com_a_grade(self):
        self.client.force_login(self.equipe)
        resposta = self.client.get("/site/promocoes/", **INTERNO)

        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        # nenhum <select> na tela de promoções nem no editor (o resto do
        # painel em volta, como a janela de divulgação, não é desta tela)
        tela = html.split('<main class="pr-tela">')[1].split("</main>")[0]
        editor = html.split('id="prEditor"')[1].split("</dialog>")[0]
        self.assertNotIn("<select", tela)
        self.assertNotIn("<select", editor)
        self.assertIn('id="pr-brinquedos"', html)
        dados = json.loads(html.split('id="pr-brinquedos" type="application/json">')[1].split("</script>")[0])
        nomes = {b["nome"] for b in dados}
        self.assertEqual(nomes, {"Air Game Kids", "Basquete Street", "Pega Toupeira"})
        self.assertTrue(all("preco" in b and "foto" in b and "categorias" in b for b in dados))


class SiteTests(Base):
    def criar_pacote(self):
        air, basquete, _ = self.brinquedos
        promocao = Promocoes.objects.create(
            descricao="Pacote de férias", brinquedos=air, preco_promocao=Decimal("18900.00"), ativo=True,
        )
        promocao.brinquedos_extras.set([basquete])
        return promocao

    def test_pagina_lista_todos_e_o_preco_do_conjunto(self):
        promocao = self.criar_pacote()
        resposta = self.client.get(reverse("promocao", args=[promocao.pk]))

        self.assertContains(resposta, "2 brinquedos nesta promoção")
        self.assertContains(resposta, "Air Game Kids")
        self.assertContains(resposta, "Basquete Street")
        self.assertContains(resposta, "21.000,00")  # a soma de tabela
        self.assertContains(resposta, "18.900,00")
        self.assertContains(resposta, "10% de desconto")

    def test_quadro_da_home_gira_as_promocoes_entre_os_brinquedos(self):
        self.criar_pacote()
        resposta = self.client.get("/")

        vitrine = resposta.context["vitrine_quadro"]
        tipos = [item.get("tipo", "brinquedo") for item in vitrine]
        self.assertIn("promocao", tipos)
        # a promoção vem logo depois do primeiro brinquedo
        self.assertEqual(tipos[:2], ["brinquedo", "promocao"])
        slide = next(item for item in vitrine if item.get("tipo") == "promocao")
        self.assertEqual(slide["nome"], "Pacote de férias")
        self.assertEqual(slide["selo"], "-10%")
        self.assertIn("Air Game Kids + Basquete Street", slide["brinquedos"])
        self.assertContains(resposta, "ls-vitrine-slide--promo")

    def test_intercalar(self):
        self.assertEqual(intercalar_vitrine([1, 2, 3], ["a"]), [1, "a", 2, 3])
        self.assertEqual(intercalar_vitrine([1], ["a", "b"]), [1, "a", "b"])

    def test_divulgacao_cita_todos(self):
        from sistema_interno.campanhas import conteudo_do_objeto
        from sistema_interno.models import CampanhaDivulgacao

        promocao = self.criar_pacote()
        conteudo = conteudo_do_objeto(CampanhaDivulgacao.Tipo.PROMOCAO, promocao.pk)
        self.assertIn("Air Game Kids e Basquete Street", conteudo.mensagem)
        self.assertIn("os 2 por R$ 18.900,00", conteudo.mensagem)
