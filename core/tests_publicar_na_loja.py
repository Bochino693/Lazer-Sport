"""Publicar na loja pelo painel, do jeito que a equipe faz (LEIA-ME seções 99 e 100).

Cada teste cadastra pelo PAINEL (o POST da tela interna) e confere a LOJA
pública logo depois: o item aparece na hora (o cache do catálogo se apaga
sozinho ao salvar), com o preço no Pix, o cartão + 12% e as vezes sem juros
certas -- o padrão (promoção 10x; brinquedo, peça e combo 6x) ou o que o
painel escolheu no item.
"""

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import Brinquedos, CategoriaPeca, Combos, PecasReposicao, Promocoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class PublicarNaLojaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.equipe = User.objects.create_superuser("equipe", "equipe@exemplo.com", "x")
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="Mesa de air game",
            imagem_brinquedo="brinquedos/air.jpg", avaliacao=Decimal("5"),
            valor_brinquedo=Decimal("6990.00"), exibir_na_loja=True,
        )

    def tearDown(self):
        cache.clear()

    # ------------------------------------------------------------------
    def painel(self, rota, dados, **cabecalhos):
        self.client.force_login(self.equipe)
        resposta = self.client.post(rota, dados, **(cabecalhos or INTERNO))
        self.client.logout()
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        return resposta

    def card_na_loja(self, nome):
        """O texto do bloco de preço do card com este nome na loja pública."""
        html = self.client.get("/loja/").content.decode()
        for card in html.split('<article class="loja-card"')[1:]:
            if nome in card:
                bloco = card.split('class="ls-preco', 1)[1].split("</div>", 1)[0]
                return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", bloco)).strip()
        self.fail(f"{nome} não apareceu na loja")

    # ------------------------------------------------------------------ promoções
    def test_promocao_nova_sai_em_10x_sem_juros(self):
        self.painel("/site/promocoes/", {
            "acao": "criar", "descricao": "Air Game em oferta", "brinquedos": [str(self.brinquedo.pk)],
            "preco_promocao": "5.990,00", "ativo": "on", "parcelas_sem_juros": "",
        })
        promo = Promocoes.objects.get()
        self.assertIsNone(promo.parcelas_sem_juros)
        texto = self.card_na_loja("Air Game em oferta")
        self.assertIn("R$ 5.990,00", texto)
        self.assertIn("em até 10x de R$ 670,88 sem juros", texto)
        self.assertNotIn("com juros", texto)

    def test_promocao_com_vezes_escolhidas_no_painel(self):
        self.painel("/site/promocoes/", {
            "acao": "criar", "descricao": "Oferta relâmpago", "brinquedos": [str(self.brinquedo.pk)],
            "preco_promocao": "5.990,00", "ativo": "on", "parcelas_sem_juros": "4",
        })
        self.assertEqual(Promocoes.objects.get().parcelas_sem_juros, 4)
        texto = self.card_na_loja("Oferta relâmpago")
        self.assertIn("em até 4x de R$ 1.677,20 sem juros", texto)
        self.assertIn("ou em até 10x", texto)
        self.assertIn("com juros", texto)

    def test_promocao_com_vezes_invalidas_nao_salva(self):
        self.client.force_login(self.equipe)
        self.client.post("/site/promocoes/", {
            "acao": "criar", "descricao": "Errada", "brinquedos": [str(self.brinquedo.pk)],
            "preco_promocao": "5.990,00", "ativo": "on", "parcelas_sem_juros": "11",
        }, **INTERNO)
        self.assertFalse(Promocoes.objects.exists())

    # ------------------------------------------------------------------ brinquedos
    def test_brinquedo_editado_no_painel(self):
        self.assertIn("em até 6x de R$ 1.304,80 sem juros", self.card_na_loja("Air Game Kids"))
        self.painel("/site/brinquedos/", {
            "action": "save", "id": self.brinquedo.pk, "nome_brinquedo": "Air Game Kids",
            "descricao": "Mesa de air game", "valor_brinquedo": "6990", "exibir_na_loja": "on",
            "voltz": "220V", "parcelas_sem_juros": "10",
        }, **AJAX)
        self.brinquedo.refresh_from_db()
        self.assertEqual(self.brinquedo.parcelas_sem_juros, 10)
        texto = self.card_na_loja("Air Game Kids")
        self.assertIn("em até 10x de R$ 782,88 sem juros", texto)
        self.assertNotIn("com juros", texto)

    # ------------------------------------------------------------------ peças
    def test_peca_nova_pelo_painel(self):
        categoria = CategoriaPeca.objects.create(nome_categoria_peca="Air Game")
        self.painel("/site/pecas/", {
            "action": "save", "resposta": "json", "nome": "Disco de air game",
            "descricao_peca": "Disco oficial", "preco_venda": "49,90", "categorias": [categoria.pk],
            "ativo": "1", "parcelas_sem_juros": "",
        })
        peca = PecasReposicao.objects.get(nome="Disco de air game")
        self.assertIsNone(peca.parcelas_sem_juros)
        texto = self.card_na_loja("Disco de air game")
        self.assertIn("R$ 49,90", texto)
        self.assertIn("em até 6x de R$ 9,32 sem juros", texto)

    # ------------------------------------------------------------------ combos
    def test_combo_novo_com_10x(self):
        self.painel("/site/combos/", {
            "acao": "criar", "descricao": "Combo festa", "brinquedos": [str(self.brinquedo.pk)],
            "valor_combo": "6500.00", "ativo": "on", "parcelas_sem_juros": "10",
        })
        self.assertEqual(Combos.objects.get().parcelas_sem_juros, 10)
        texto = self.card_na_loja("Combo festa")
        self.assertIn("em até 10x de R$ 728,00 sem juros", texto)
