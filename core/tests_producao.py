"""O tempo de produção em dias úteis (core/producao.py, LEIA-ME-V10 seção 89).

"O tempo de produção a gente deve poder informar em cada pedido ou
orçamento." A equipe diz quantos dias ÚTEIS; a previsão sai sozinha. O que
estes testes protegem: o fim de semana e os feriados nacionais não contam,
o dia do começo não conta, zero é pronta entrega, e o que a tela manda é
lido com a frase certa quando não é um número.
"""

import datetime as dt

from django.test import SimpleTestCase

from .producao import (
    PRAZO_MAXIMO,
    dia_util,
    feriados_nacionais,
    ler_prazo,
    pascoa,
    somar_dias_uteis,
    texto_da_producao,
    texto_dos_dias,
)

SEXTA = dt.date(2026, 11, 13)  # sexta-feira


class DiasUteisTests(SimpleTestCase):

    def test_a_pascoa_e_a_sexta_feira_santa(self):
        self.assertEqual(pascoa(2025), dt.date(2025, 4, 20))
        self.assertEqual(pascoa(2026), dt.date(2026, 4, 5))
        self.assertEqual(pascoa(2027), dt.date(2027, 3, 28))
        self.assertIn(dt.date(2026, 4, 3), feriados_nacionais(2026))

    def test_os_feriados_nacionais_fixos(self):
        feriados = feriados_nacionais(2026)
        for dia in ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)):
            with self.subTest(dia=dia):
                self.assertIn(dt.date(2026, *dia), feriados)
        # A Consciência Negra é nacional desde 2024.
        self.assertNotIn(dt.date(2023, 11, 20), feriados_nacionais(2023))
        self.assertIn(dt.date(2024, 11, 20), feriados_nacionais(2024))

    def test_fim_de_semana_e_feriado_nao_sao_dia_util(self):
        self.assertTrue(dia_util(SEXTA))
        self.assertFalse(dia_util(dt.date(2026, 11, 14)))  # sábado
        self.assertFalse(dia_util(dt.date(2026, 11, 15)))  # domingo (e feriado)
        self.assertFalse(dia_util(dt.date(2026, 11, 20)))  # sexta, Consciência Negra

    def test_o_dia_do_comeco_nao_conta(self):
        # Pago na sexta, 3 dias úteis: segunda, terça e quarta.
        self.assertEqual(somar_dias_uteis(SEXTA, 3), dt.date(2026, 11, 18))
        self.assertEqual(somar_dias_uteis(SEXTA, 1), dt.date(2026, 11, 16))

    def test_o_feriado_no_meio_empurra_a_previsao(self):
        # seg 16, ter 17, qua 18, qui 19, (sex 20 é feriado), seg 23
        self.assertEqual(somar_dias_uteis(SEXTA, 5), dt.date(2026, 11, 23))
        # Natal e Ano-Novo no caminho.
        self.assertEqual(
            somar_dias_uteis(dt.date(2026, 12, 23), 3), dt.date(2026, 12, 29),
        )

    def test_zero_e_pronta_entrega_e_sem_dado_nao_ha_previsao(self):
        self.assertEqual(somar_dias_uteis(SEXTA, 0), SEXTA)
        self.assertIsNone(somar_dias_uteis(None, 5))
        self.assertIsNone(somar_dias_uteis(SEXTA, None))

    def test_comecar_no_fim_de_semana_ou_com_hora(self):
        sabado = dt.date(2026, 11, 14)
        self.assertEqual(somar_dias_uteis(sabado, 1), dt.date(2026, 11, 16))
        self.assertEqual(
            somar_dias_uteis(dt.datetime(2026, 11, 13, 22, 30), 3), dt.date(2026, 11, 18),
        )

    def test_vinte_dias_uteis_sao_quatro_semanas_sem_feriado(self):
        inicio = dt.date(2026, 6, 1)  # segunda, sem feriado nacional em junho
        self.assertEqual(somar_dias_uteis(inicio, 20), dt.date(2026, 6, 29))


class TextoDaProducaoTests(SimpleTestCase):

    def test_as_frases(self):
        self.assertEqual(texto_dos_dias(15), "15 dias úteis")
        self.assertEqual(texto_dos_dias(1), "1 dia útil")
        self.assertEqual(texto_dos_dias(0), "pronta entrega")
        self.assertEqual(texto_dos_dias(None), "")
        self.assertEqual(
            texto_da_producao(15, dt.date(2026, 12, 4)),
            "Produção: 15 dias úteis — previsão 04/12",
        )
        self.assertEqual(texto_da_producao(15), "Produção: 15 dias úteis")
        self.assertEqual(texto_da_producao(None, dt.date(2026, 12, 4)), "")

    def test_o_campo_da_tela(self):
        self.assertIsNone(ler_prazo(""))
        self.assertIsNone(ler_prazo(None))
        self.assertEqual(ler_prazo(" 15 "), 15)
        self.assertEqual(ler_prazo("0"), 0)
        for errado in ("abc", "-3", "1,5", "15 dias"):
            with self.subTest(valor=errado), self.assertRaises(ValueError):
                ler_prazo(errado)
        with self.assertRaisesMessage(ValueError, f"O máximo é {PRAZO_MAXIMO}"):
            ler_prazo(str(PRAZO_MAXIMO + 1))
