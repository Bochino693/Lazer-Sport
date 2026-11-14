"""Black Friday "tudo em 6x": o texto nunca promete mais parcelas que o cartão."""

from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from . import checkout
from .parcelas_texto import (
    PARCELAS_NO_MAXIMO, VALOR_POR_PARCELA, condicao_em_6x, condicoes_em_6x, maximo_de_parcelas,
)


class TextoDasParcelasTests(SimpleTestCase):
    def test_mesma_regra_do_checkout(self):
        self.assertEqual(PARCELAS_NO_MAXIMO, checkout.PARCELAS_NO_MAXIMO)
        self.assertEqual(VALOR_POR_PARCELA, checkout.VALOR_POR_PARCELA)
        for valor in ("999", "1999", "4990", "5999.99", "6000", "31970"):
            self.assertEqual(maximo_de_parcelas(Decimal(valor)), checkout.parcelas_maximas(Decimal(valor)), valor)

    def test_dez_vezes_vira_o_que_o_cartao_aceita(self):
        self.assertEqual(condicao_em_6x("Em até 10x sem juros de R$ 3.197,00", Decimal("31970")),
                         "Em até 6x sem juros de R$ 5.328,33")
        self.assertEqual(condicao_em_6x("Em até 10x sem juros", Decimal("19990")),
                         "Em até 6x sem juros de R$ 3.331,67")
        self.assertEqual(condicao_em_6x("Ou em 10x de R$ 599,90 no cartão", Decimal("4990")),
                         "Ou em até 4x de R$ 1.247,50 sem juros no cartão")
        self.assertEqual(condicao_em_6x("Parcelamos em até 10x sem juros", None),
                         "Parcelamos em até 6x sem juros no cartão (uma parcela a cada R$ 1.000)")

    def test_o_que_ja_esta_certo_nao_muda(self):
        for linha in ("Em até 6x sem juros", "À vista no PIX: R$ 4.990,00", "Prazo de produção: 45 a 50 dias",
                      "Garantia de 6 meses", "Boliche Kids 32\" R$ 7.990", "Na compra de 3 cenográficos, leve 4!"):
            self.assertEqual(condicao_em_6x(linha, Decimal("31970")), linha)

    def test_campo_inteiro_linha_a_linha(self):
        texto = "Em até 10x sem juros\nFrete por conta do cliente"
        self.assertEqual(condicoes_em_6x(texto, Decimal("12990")),
                         "Em até 6x sem juros de R$ 2.165,00\nFrete por conta do cliente")


class PromocaoNaTelaTests(TestCase):
    def test_lista_condicoes_corrige_mesmo_o_que_foi_digitado_no_painel(self):
        from .models import Brinquedos, Promocoes
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5"), valor_brinquedo=Decimal("6990"),
        )
        promo = Promocoes(descricao="BF", brinquedos=brinquedo, preco_promocao=Decimal("16990"),
                          condicoes="Em até 10x sem juros\nGarantia de 6 meses")
        self.assertEqual(promo.lista_condicoes, ["Em até 6x sem juros de R$ 2.831,67", "Garantia de 6 meses"])
