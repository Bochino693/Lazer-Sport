"""O preço do site (LEIA-ME seção 98): Pix pelo preço, cartão + 12% em até 10x sem juros.

O nome do arquivo ficou da seção 94 ("tudo em 6x"); a regra agora é a do dono:
"todo site deve cobrir 10x sem juros; no Pix, o valor do objeto; no crédito, em
até 10x, 12% a mais, para todos os brinquedos e peças".
"""

from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

from . import checkout
from .parcelas_texto import (
    ACRESCIMO_CARTAO, PARCELA_MINIMA, PARCELAS_NO_MAXIMO, condicao_em_6x, condicoes_em_6x,
    e_linha_do_pagamento, maximo_de_parcelas, no_cartao,
)


class RegraDoCartaoTests(SimpleTestCase):
    def test_a_mesma_regra_do_checkout(self):
        self.assertEqual(ACRESCIMO_CARTAO, checkout.ACRESCIMO_CARTAO)
        self.assertEqual(PARCELAS_NO_MAXIMO, checkout.PARCELAS_NO_MAXIMO)
        self.assertEqual(PARCELA_MINIMA, checkout.PARCELA_MINIMA)
        for valor in ("4.40", "39.90", "999", "4990", "31970"):
            v = Decimal(valor)
            self.assertEqual(no_cartao(v), checkout.valor_no_cartao(v), valor)
            self.assertEqual(maximo_de_parcelas(v), checkout.parcelas_maximas(checkout.valor_no_cartao(v)), valor)

    def test_cartao_e_12_por_cento_a_mais(self):
        self.assertEqual(checkout.valor_no_cartao(Decimal("4990")), Decimal("5588.80"))
        self.assertEqual(checkout.valor_no_cartao(Decimal("31970")), Decimal("35806.40"))
        self.assertEqual(checkout.valor_no_cartao(Decimal("39.90")), Decimal("44.69"))

    def test_ate_10x_com_parcela_minima_de_5_reais(self):
        self.assertEqual(checkout.parcelas_maximas(Decimal("5588.80")), 10)
        self.assertEqual(checkout.parcelas_maximas(Decimal("44.69")), 8)
        self.assertEqual(checkout.parcelas_maximas(Decimal("4.99")), 1)


class TextoDasParcelasTests(SimpleTestCase):
    def test_qualquer_regra_antiga_vira_a_de_hoje(self):
        for linha in ("Em até 10x sem juros de R$ 3.197,00", "Em até 6x sem juros de R$ 5.328,33", "Em até 3x sem juros"):
            self.assertEqual(condicao_em_6x(linha, Decimal("31970")), "Em até 10x de R$ 3.580,64 sem juros no cartão", linha)
        self.assertEqual(condicao_em_6x("Ou em 10x de R$ 599,90 no cartão", Decimal("4990")),
                         "Ou em até 10x de R$ 558,88 sem juros no cartão")
        self.assertEqual(condicao_em_6x("Parcelamos em até 6x sem juros", None),
                         "Parcelamos em até 10x sem juros no cartão")

    def test_o_que_nao_fala_de_parcelas_fica(self):
        for linha in ("À vista no PIX: R$ 4.990,00", "Prazo de produção: 45 a 50 dias", "Garantia de 6 meses",
                      "Boliche Kids 32\" R$ 7.990", "Na compra de 3 cenográficos, leve 4!"):
            self.assertEqual(condicao_em_6x(linha, Decimal("31970")), linha)

    def test_campo_inteiro_linha_a_linha(self):
        self.assertEqual(condicoes_em_6x("Em até 6x sem juros\nFrete por conta do cliente", Decimal("12990")),
                         "Em até 10x de R$ 1.454,88 sem juros no cartão\nFrete por conta do cliente")

    def test_linhas_do_pagamento_saem_do_card(self):
        self.assertTrue(e_linha_do_pagamento("Em até 10x de R$ 558,88 sem juros no cartão"))
        self.assertTrue(e_linha_do_pagamento("Pagamento à vista no PIX: R$ 4.990,00"))
        self.assertTrue(e_linha_do_pagamento("À vista com 7% de desconto: R$ 29.732,10"))
        self.assertFalse(e_linha_do_pagamento("Ganhe um kit de mesinha kids de cortesia"))


class BlocoDePrecoTests(SimpleTestCase):
    def render(self, trecho, **ctx):
        return Template("{% load precos %}" + trecho).render(Context(ctx))

    def test_pix_em_destaque_e_o_cartao_riscado(self):
        html = self.render("{% preco_pix_cartao v %}", v=Decimal("4990"))
        self.assertIn("R$ 5.588,80", html)  # o cartão, riscado
        self.assertIn("R$ 4.990,00", html)  # o Pix
        self.assertIn("no Pix", html)
        self.assertIn("-11%", html)
        self.assertIn("em até 10x de R$ 558,88 sem juros", html)

    def test_promocao_mostra_o_de_e_o_total_no_cartao(self):
        html = self.render("{% preco_pix_cartao v de=d %}", v=Decimal("18900"), d=Decimal("21000"))
        self.assertIn("<s>R$ 21.000,00</s>", html)
        self.assertIn("ou R$ 21.168,00 em até 10x de R$ 2.116,80 sem juros", html)
        self.assertIn("-10%", html)

    def test_sem_preco_nao_mostra_nada(self):
        self.assertEqual(self.render("{% preco_pix_cartao v %}", v=None).strip(), "")


class PromocaoNaTelaTests(TestCase):
    def test_lista_condicoes_corrige_mesmo_o_que_foi_digitado_no_painel(self):
        from .models import Brinquedos, Promocoes
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5"), valor_brinquedo=Decimal("6990"),
        )
        promo = Promocoes(descricao="BF", brinquedos=brinquedo, preco_promocao=Decimal("16990"),
                          condicoes="Em até 12x sem juros\nGarantia de 6 meses")
        self.assertEqual(promo.lista_condicoes, ["Em até 10x de R$ 1.902,88 sem juros no cartão", "Garantia de 6 meses"])
        self.assertEqual(promo.condicoes_extras, ["Garantia de 6 meses"])
