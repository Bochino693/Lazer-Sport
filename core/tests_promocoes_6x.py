"""O preço do site (LEIA-ME seções 98 e 99): Pix pelo preço, cartão + 12%.

O nome do arquivo ficou da seção 94 ("tudo em 6x"). A regra agora: no Pix, o
valor do objeto; no crédito, 12% a mais, em até 10x; SEM JUROS até as vezes de
cada objeto (promoções 10x, brinquedos, peças e combos 6x, ou o que o painel
disser) e, acima, com juros (tabela Price, 2,99% ao mês).
"""

from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

from . import checkout
from .parcelas_texto import (
    ACRESCIMO_CARTAO, PARCELA_MINIMA, PARCELAS_NO_MAXIMO, condicao_em_6x, condicoes_em_6x,
    e_linha_do_pagamento, ler_sem_juros, maximo_de_parcelas, no_cartao, resumo_do_cartao,
    sem_juros_do_objeto,
)


class RegraDoCartaoTests(SimpleTestCase):
    def test_a_mesma_regra_do_checkout(self):
        self.assertEqual(ACRESCIMO_CARTAO, checkout.ACRESCIMO_CARTAO)
        self.assertEqual(PARCELAS_NO_MAXIMO, checkout.PARCELAS_NO_MAXIMO)
        self.assertEqual(PARCELA_MINIMA, checkout.PARCELA_MINIMA)
        for valor in ("4.40", "39.90", "999", "4990", "31970"):
            v = Decimal(valor)
            self.assertEqual(no_cartao(v), checkout.valor_no_cartao(v), valor)
            # a promoção (10x sem juros): até 10x, parcela mínima de R$ 5
            self.assertEqual(maximo_de_parcelas(v, 10), checkout.parcelas_maximas(checkout.valor_no_cartao(v)), valor)

    def test_cartao_e_12_por_cento_a_mais(self):
        self.assertEqual(checkout.valor_no_cartao(Decimal("4990")), Decimal("5588.80"))
        self.assertEqual(checkout.valor_no_cartao(Decimal("31970")), Decimal("35806.40"))
        self.assertEqual(checkout.valor_no_cartao(Decimal("39.90")), Decimal("44.69"))

    def test_ate_10x_com_parcela_minima_de_5_reais(self):
        self.assertEqual(checkout.parcelas_maximas(Decimal("5588.80")), 10)
        self.assertEqual(checkout.parcelas_maximas(Decimal("44.69")), 8)
        self.assertEqual(checkout.parcelas_maximas(Decimal("4.99")), 1)


class VezesSemJurosPorObjetoTests(SimpleTestCase):
    def test_o_padrao_promocao_10x_o_resto_6x(self):
        from types import SimpleNamespace
        promo = SimpleNamespace(_meta=SimpleNamespace(model_name="promocoes"), parcelas_sem_juros=None)
        brinquedo = SimpleNamespace(_meta=SimpleNamespace(model_name="brinquedos"), parcelas_sem_juros=None)
        peca = SimpleNamespace(_meta=SimpleNamespace(model_name="pecasreposicao"), parcelas_sem_juros=None)
        self.assertEqual(sem_juros_do_objeto(promo), 10)
        self.assertEqual(sem_juros_do_objeto(brinquedo), 6)
        self.assertEqual(sem_juros_do_objeto(peca), 6)
        # o painel manda: uma promoção em 3x, um brinquedo em 10x
        promo.parcelas_sem_juros = 3
        brinquedo.parcelas_sem_juros = 10
        self.assertEqual(sem_juros_do_objeto(promo), 3)
        self.assertEqual(sem_juros_do_objeto(brinquedo), 10)

    def test_o_campo_do_painel(self):
        self.assertIsNone(ler_sem_juros(""))
        self.assertIsNone(ler_sem_juros("padrão"))
        self.assertEqual(ler_sem_juros("8"), 8)
        self.assertEqual(ler_sem_juros("8x"), 8)
        for ruim in ("0", "11", "dez"):
            with self.assertRaises(ValueError):
                ler_sem_juros(ruim)

    def test_brinquedo_6x_sem_juros_e_10x_com_juros(self):
        r = resumo_do_cartao(Decimal("4990"), 6)
        self.assertEqual((r["cartao"], r["vezes"], r["parcela"]), (Decimal("5588.80"), 6, Decimal("931.47")))
        self.assertEqual((r["vezes_com_juros"], r["parcela_com_juros"], r["total_com_juros"]),
                         (10, Decimal("654.84"), Decimal("6548.44")))
        r = resumo_do_cartao(Decimal("4990"), 10)
        self.assertEqual((r["vezes"], r["parcela"], r["vezes_com_juros"]), (10, Decimal("558.88"), 0))

    def test_a_taxa_vem_do_settings(self):
        from django.test import override_settings
        with override_settings(JUROS_CARTAO_AO_MES="0"):
            r = resumo_do_cartao(Decimal("4990"), 6)
            self.assertEqual(r["total_com_juros"], None)  # sem taxa, sem juros


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
        # o brinquedo: 6x sem juros e, fora do card compacto, até 10x com juros
        self.assertIn("em até 6x de R$ 931,47 sem juros", html)
        self.assertIn("ou em até 10x de R$ 654,84 com juros", html)
        compacto = self.render("{% preco_pix_cartao v compacto=True %}", v=Decimal("4990"))
        self.assertIn("em até 6x de R$ 931,47 sem juros", compacto)
        self.assertNotIn("com juros", compacto)

    def test_promocao_mostra_o_de_e_o_total_no_cartao(self):
        html = self.render("{% preco_pix_cartao v de=d sem_juros=10 %}", v=Decimal("18900"), d=Decimal("21000"))
        self.assertIn("<s>R$ 21.000,00</s>", html)
        self.assertIn("ou R$ 21.168,00 em até 10x de R$ 2.116,80 sem juros", html)
        self.assertNotIn("com juros", html)
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
