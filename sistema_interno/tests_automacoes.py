from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .automacoes import expirar_orcamentos_vencidos
from .models import Orcamento


class ExpiracaoAutomaticaOrcamentoTests(TestCase):
    def criar(self, status, dias):
        return Orcamento.objects.create(
            nome_cliente="Cliente de teste",
            status=status,
            validade=timezone.localdate() + timedelta(days=dias),
        )

    def test_expira_somente_proposta_enviada_e_vencida(self):
        vencido = self.criar(Orcamento.Status.AGUARDANDO_RESPOSTA, -1)
        futuro = self.criar(Orcamento.Status.AGUARDANDO_RESPOSTA, 2)
        rascunho = self.criar(Orcamento.Status.RASCUNHO, -2)
        negociacao = self.criar(Orcamento.Status.EM_NEGOCIACAO, -3)

        self.assertEqual(expirar_orcamentos_vencidos(), 1)

        vencido.refresh_from_db()
        futuro.refresh_from_db()
        rascunho.refresh_from_db()
        negociacao.refresh_from_db()
        self.assertEqual(vencido.status, Orcamento.Status.EXPIRADO)
        self.assertEqual(futuro.status, Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertEqual(rascunho.status, Orcamento.Status.RASCUNHO)
        self.assertEqual(negociacao.status, Orcamento.Status.EM_NEGOCIACAO)

    def test_repetir_o_ciclo_nao_refaz_trabalho(self):
        self.criar(Orcamento.Status.AGUARDANDO_RESPOSTA, -1)
        self.assertEqual(expirar_orcamentos_vencidos(), 1)
        self.assertEqual(expirar_orcamentos_vencidos(), 0)
