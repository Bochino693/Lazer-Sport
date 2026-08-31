"""A O.S. também mostra só o que cabe, e cobra o que de fato custou.

Duas coisas que a Ordem de Serviço herdou tarde do orçamento.

A PRIMEIRA é a pergunta "isto cabe agora?". A linha trazia "Pagamento" em
toda O.S., inclusive nas já quitadas -- e a janela abria pedindo um valor
que já estava lá. A leitura de quem via era "será que não registrou?", e
registrava de novo: dinheiro contado duas vezes no mesmo documento.

A SEGUNDA é o total. A O.S. somava só os itens, e o total saía errado nos
dois casos mais comuns do atendimento: o deslocamento até o cliente, que
existe em toda visita e não é peça nem mão de obra, e o abatimento dado na
hora para fechar. Sem lugar para eles, ou o técnico embutia o frete no
preço de uma peça -- e o documento passava a mentir sobre o que custou o
quê -- ou o desconto ficava fora do papel e só na conversa.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Cliente, ItemOrdemServico, OrdemServico


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AcoesDaOrdemConformeASituacaoTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-os", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)
        self.cliente = Cliente.objects.create(
            nome_cliente="Buffet Alegria", telefone="(11) 97777-6655",
        )

    def ordem(self, *, valor="200.00", status=OrdemServico.Status.ABERTA, pago="0"):
        ordem = OrdemServico.objects.create(
            nome_cliente="Buffet Alegria", cliente=self.cliente,
            equipamento="Tobogã", status=status,
        )
        if Decimal(valor) > 0:
            ItemOrdemServico.objects.create(
                ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
                descricao="Reparo", quantidade=1, valor_unitario=Decimal(valor),
            )
        ordem.refresh_from_db()
        if Decimal(pago) > 0:
            ordem.registrar_pagamento(Decimal(pago))
        return ordem

    def lista(self):
        return self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).content.decode()

    def botao_pagamento(self, ordem):
        # O atributo com o id daquela linha, e não o seletor solto: a tela
        # sempre carrega `querySelectorAll("[data-pagamento-os]")`.
        return 'data-pagamento-os="%d"' % ordem.pk

    def test_quitada_esconde_o_botao_e_anuncia_que_esta_paga(self):
        ordem = self.ordem(pago="200.00")

        self.assertTrue(ordem.quitado)
        self.assertFalse(ordem.pode_receber_pagamento)

        html = self.lista()
        self.assertNotIn(self.botao_pagamento(ordem), html)
        self.assertIn("ls-pago", html)

    def test_parcial_convida_a_completar_e_diz_quanto_falta(self):
        ordem = self.ordem(pago="80.00")

        self.assertTrue(ordem.pode_receber_pagamento)
        html = self.lista()
        self.assertIn(self.botao_pagamento(ordem), html)
        self.assertIn("Completar pagamento", html)
        self.assertIn("faltam R$ 120,00", html)

    def test_cancelada_nao_recebe_pagamento(self):
        """O serviço não aconteceu; não há o que cobrar."""
        ordem = self.ordem(status=OrdemServico.Status.CANCELADA)

        self.assertFalse(ordem.pode_receber_pagamento)
        self.assertNotIn(self.botao_pagamento(ordem), self.lista())

    def test_sem_itens_nao_ha_valor_a_cobrar(self):
        """O.S. sem item ainda não sabe quanto custa."""
        ordem = self.ordem(valor="0")

        self.assertEqual(ordem.total, Decimal("0.00"))
        self.assertFalse(ordem.pode_receber_pagamento)

    def test_cancelada_nao_e_enviada_ao_cliente(self):
        ordem = self.ordem(status=OrdemServico.Status.CANCELADA)

        self.assertFalse(ordem.pode_enviar)
        self.assertNotIn('data-enviar-os="%d"' % ordem.pk, self.lista())

    def test_rascunho_pode_ser_enviado_porque_o_envio_e_que_publica(self):
        """Ao contrário do orçamento: `marcar_enviada` promove o rascunho."""
        ordem = self.ordem(status=OrdemServico.Status.RASCUNHO)

        self.assertTrue(ordem.pode_enviar)
        self.assertIn('data-enviar-os="%d"' % ordem.pk, self.lista())

    def test_o_servidor_recusa_o_pagamento_que_a_tela_nao_oferece(self):
        """Aba antiga e POST à mão continuam chegando."""
        quitada = self.ordem(pago="200.00")

        resposta = self.client.post(
            "/ordens-servico/",
            {"action": "pagamento", "id": quitada.pk, "valor_pago": "200,00"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("já está paga", resposta.json()["msg"])

    def test_o_servidor_recusa_pagamento_de_ordem_cancelada(self):
        cancelada = self.ordem(status=OrdemServico.Status.CANCELADA)

        resposta = self.client.post(
            "/ordens-servico/",
            {"action": "pagamento", "id": cancelada.pk, "valor_pago": "200,00"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 400)
        cancelada.refresh_from_db()
        self.assertEqual(cancelada.valor_pago, Decimal("0.00"))


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class DeslocamentoEDescontoDaOrdemTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-financeiro-os", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def ordem_de_200(self):
        ordem = OrdemServico.objects.create(
            nome_cliente="Buffet Alegria", equipamento="Tobogã",
            status=OrdemServico.Status.ABERTA,
        )
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
            descricao="Reparo", quantidade=1, valor_unitario=Decimal("200.00"),
        )
        ordem.refresh_from_db()
        return ordem

    def test_o_total_soma_deslocamento_e_abate_desconto(self):
        ordem = self.ordem_de_200()
        ordem.frete = Decimal("80.00")
        ordem.desconto = Decimal("28.00")
        ordem.save()
        ordem.refresh_from_db()

        self.assertEqual(ordem.subtotal_itens, Decimal("200.00"))
        self.assertEqual(ordem.total, Decimal("252.00"))

    def test_desconto_maior_que_tudo_nao_deixa_o_total_negativo(self):
        """Total negativo diria que a empresa deve ao cliente."""
        ordem = self.ordem_de_200()
        ordem.desconto = Decimal("500.00")
        ordem.save()
        ordem.refresh_from_db()

        self.assertEqual(ordem.total, Decimal("0.00"))

    def test_o_saldo_a_receber_acompanha_o_total_novo(self):
        ordem = self.ordem_de_200()
        ordem.frete = Decimal("50.00")
        ordem.save()
        ordem.refresh_from_db()
        ordem.registrar_pagamento(Decimal("100.00"))

        self.assertEqual(ordem.total, Decimal("250.00"))
        self.assertEqual(ordem.saldo_pagamento, Decimal("150.00"))
        self.assertEqual(
            ordem.status_pagamento, OrdemServico.StatusPagamento.PARCIAL
        )

    def test_o_bloco_do_dinheiro_vem_depois_dos_itens(self):
        """Só se sabe quanto dar de desconto depois de ver a soma."""
        from pathlib import Path

        modal = (
            Path(__file__).resolve().parent
            / "templates" / "ordens_servico_inner.html"
        ).read_text(encoding="utf-8")

        itens = modal.index("Serviços, peças e materiais")
        financeiro = modal.index("Bloco Financeiro")
        total = modal.index('id="osTotal"')

        self.assertLess(itens, financeiro)
        self.assertLess(financeiro, total)

    def test_a_tela_grava_os_dois_campos(self):
        ordem = self.ordem_de_200()

        self.client.post(
            "/ordens-servico/",
            {
                "action": "save", "id": ordem.pk,
                "nome_cliente": "Buffet Alegria", "equipamento": "Tobogã",
                "tipo": ordem.tipo, "status": ordem.status,
                "prioridade": ordem.prioridade,
                "frete": "80,00", "desconto": "28,00",
                "itens": '[{"tipo":"servico","descricao":"Reparo",'
                         '"quantidade":"1","valor_unitario":"200,00"}]',
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        ordem.refresh_from_db()
        self.assertEqual(ordem.frete, Decimal("80.00"))
        self.assertEqual(ordem.desconto, Decimal("28.00"))
        self.assertEqual(ordem.total, Decimal("252.00"))
