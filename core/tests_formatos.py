"""Dinheiro e medida escritos como se lê em português.

POR QUE ISTO É UM ARQUIVO DE TESTE, E NÃO UM DETALHE. O mesmo valor
aparecia de três jeitos na mesma tela: "R$ 1250.00" na lista, "R$
1.250,00" na proposta e "1250,0" no resumo. Preço com ponto decimal é
lido como milhar por quem trabalha em português -- "R$ 1.250" e "R$
1250.00" são números diferentes para o olho antes de serem iguais para a
conta. E uma medida "2.00m" no papel do cliente parece o começo de outro
número.

A causa era não haver onde formatar: cada template resolvia sozinho, com
`floatformat`, com filtro, ou com nada.
"""

from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings

from core.formatos import dimensoes, dinheiro, medida


class DinheiroTests(SimpleTestCase):

    def test_separador_de_milhar_e_virgula_decimal(self):
        self.assertEqual(dinheiro(Decimal("1234567.8")), "1.234.567,80")
        self.assertEqual(dinheiro(1250), "1.250,00")

    def test_dinheiro_sempre_tem_duas_casas(self):
        """Recibo com "R$ 1.250,5" parece truncado -- e assusta."""
        self.assertEqual(dinheiro(Decimal("1250.5")), "1.250,50")

    def test_vazio_e_nulo_viram_zero(self):
        """Aqui zero é a resposta certa: um total sem itens é R$ 0,00."""
        self.assertEqual(dinheiro(None), "0,00")
        self.assertEqual(dinheiro(""), "0,00")

    def test_o_que_nao_e_numero_nao_derruba_a_pagina(self):
        self.assertEqual(dinheiro("abacaxi"), "0,00")

    def test_prefixo_junta_o_cifrao(self):
        self.assertEqual(dinheiro(1250, prefixo="R$"), "R$ 1.250,00")


class MedidaTests(SimpleTestCase):

    def test_zeros_a_direita_caem(self):
        """"2 m" é como se fala e como se lê na fita métrica."""
        self.assertEqual(medida(Decimal("2.00")), "2 m")
        self.assertEqual(medida(Decimal("2.50")), "2,5 m")

    def test_a_casa_que_importa_fica(self):
        self.assertEqual(medida(Decimal("0.375")), "0,38 m")

    def test_medida_vazia_continua_vazia(self):
        """Medida que ninguém informou não é medida zero.

        Escrever "0 m" no papel do cliente afirma uma coisa que o
        cadastro não sabe.
        """
        self.assertEqual(medida(None), "")
        self.assertEqual(medida(""), "")

    def test_a_unidade_e_escolhida_por_quem_chama(self):
        self.assertEqual(medida(Decimal("12.5"), "m³"), "12,5 m³")
        self.assertEqual(medida(Decimal("80"), "kg"), "80 kg")

    def test_milhar_tambem_na_medida(self):
        self.assertEqual(medida(Decimal("1234.5")), "1.234,5 m")


class DimensoesTests(SimpleTestCase):

    def test_a_ficha_inteira_em_uma_linha(self):
        self.assertEqual(
            dimensoes(Decimal("2"), Decimal("3"), Decimal("3")),
            "Altura 2 m × Largura 3 m × Profundidade 3 m",
        )

    def test_meia_medida_nao_vira_ficha(self):
        """"Altura 2 m x Largura —" vale menos que nada: quem lê pergunta
        de qualquer jeito, e ainda desconfia do resto do documento."""
        self.assertEqual(dimensoes(Decimal("2"), None, Decimal("3")), "")


@override_settings(ALLOWED_HOSTS=["testserver"])
class FiltrosDeTemplateTests(TestCase):

    def render(self, corpo, **contexto):
        return Template(
            "{% load interno_extras %}" + corpo
        ).render(Context(contexto)).strip()

    def test_moeda_e_reais_no_template(self):
        self.assertEqual(self.render("{{ v|moeda }}", v=Decimal("1250")), "1.250,00")
        self.assertEqual(self.render("{{ v|reais }}", v=Decimal("1250")), "R$ 1.250,00")

    def test_medida_no_template_com_unidade_escolhida(self):
        self.assertEqual(self.render("{{ v|medida }}", v=Decimal("2.50")), "2,5 m")
        self.assertEqual(self.render('{{ v|medida:"kg" }}', v=Decimal("80")), "80 kg")

    def test_o_catalogo_escreve_a_ficha_do_brinquedo_em_portugues(self):
        """A ficha vai para a proposta impressa do cliente."""
        from core.models import Brinquedos

        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Piscina de bolinhas",
            descricao="3x3",
            avaliacao=Decimal("0"),
            altura_m=Decimal("2.00"),
            largura_m=Decimal("3.00"),
            profundidade_m=Decimal("3.00"),
        )

        self.assertEqual(
            brinquedo.dimensoes_m, "Altura 2 m × Largura 3 m × Profundidade 3 m",
        )
        self.assertEqual(brinquedo.volume_formatado, "18 m³")
