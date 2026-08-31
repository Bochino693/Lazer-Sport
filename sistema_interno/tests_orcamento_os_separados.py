"""Regras de negócio que mantêm proposta e execução independentes."""

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import (
    ItemOrcamento,
    ItemOrdemServico,
    Orcamento,
    OrdemServico,
)


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    SITE_URL="https://www.lazersport.com.br",
    PIX_CHAVE="54.486.908/0001-86",
    PIX_RECEBEDOR="LAZER SPORT BRINQUEDOS",
    PIX_CIDADE="SAO PAULO",
)
class OrcamentoEOrdemServicoSeparadosTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-os",
            password="senha-segura",
            email="gestor-os@example.com",
        )
        self.client.force_login(self.gestor)

    def post_interno(self, caminho, dados):
        return self.client.post(
            caminho,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @staticmethod
    def criar_orcamento(status=Orcamento.Status.APROVADO):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            whatsapp_cliente="(11) 99999-1111",
            email_cliente="cliente@example.com",
            forma_pagamento="Pix",
            status=status,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Revisão do brinquedo",
            quantidade=1,
            valor_unitario=Decimal("450.00"),
        )
        return orcamento

    def test_pedido_de_ajuste_preserva_versao_e_refazer_cria_outra(self):
        anterior = self.criar_orcamento(Orcamento.Status.AGUARDANDO_RESPOSTA)

        resposta = self.client.post(
            anterior.caminho_publico,
            {
                "decisao": "ajustes",
                "nome": "Ana Cliente",
                "motivo": "Preciso de desconto e sem o frete.",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        anterior.refresh_from_db()
        self.assertEqual(anterior.status, Orcamento.Status.EM_NEGOCIACAO)
        self.assertIn("desconto", anterior.motivo_negociacao)

        tentativa = self.post_interno("/orcamentos/", {
            "action": "save",
            "id": anterior.pk,
            "itens": "[]",
        })
        self.assertEqual(tentativa.status_code, 409)

        resposta = self.post_interno("/orcamentos/", {
            "action": "refazer",
            "id": anterior.pk,
        })
        self.assertEqual(resposta.status_code, 200)
        nova = Orcamento.objects.get(pk=resposta.json()["id"])
        anterior.refresh_from_db()

        self.assertEqual(anterior.status, Orcamento.Status.SUBSTITUIDO)
        self.assertEqual(nova.status, Orcamento.Status.RASCUNHO)
        self.assertEqual(nova.versao, 2)
        self.assertEqual(nova.orcamento_anterior, anterior)
        self.assertEqual(nova.itens.get().descricao, "Revisão do brinquedo")
        self.assertNotEqual(nova.token, anterior.token)

    def test_cards_filtram_por_fase_sem_select_horizontal(self):
        negociacao = self.criar_orcamento(Orcamento.Status.EM_NEGOCIACAO)
        aprovado = self.criar_orcamento(Orcamento.Status.APROVADO)

        resposta = self.client.get(
            "/orcamentos/",
            {"filtro": "negociacao"},
            HTTP_HOST="interno.testserver",
        )

        ids = [orcamento.pk for orcamento in resposta.context["orcamentos"]]
        self.assertEqual(ids, [negociacao.pk])
        self.assertNotIn(aprovado.pk, ids)
        self.assertContains(resposta, 'aria-current="page"', count=1)
        self.assertContains(resposta, "ls-budget-filter-card")
        self.assertNotContains(resposta, 'name="status" multiple')

    def test_ordem_gerada_nao_herda_pagamento_do_orcamento(self):
        orcamento = self.criar_orcamento()
        orcamento.registrar_pagamento(Decimal("450.00"), "Quitado na proposta")

        resposta = self.post_interno("/orcamentos/", {
            "action": "gerar_ordem_servico",
            "id": orcamento.pk,
        })

        self.assertEqual(resposta.status_code, 200)
        ordem = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertEqual(ordem.orcamento, orcamento)
        self.assertEqual(ordem.status_pagamento, OrdemServico.StatusPagamento.PENDENTE)
        self.assertEqual(ordem.valor_pago, Decimal("0.00"))
        self.assertEqual(ordem.itens.get().descricao, "Revisão do brinquedo")

        refazer = self.post_interno("/orcamentos/", {
            "action": "refazer",
            "id": orcamento.pk,
        })
        self.assertEqual(refazer.status_code, 400)
        self.assertFalse(hasattr(orcamento, "orcamento_refeito"))

        ordem.registrar_pagamento(Decimal("100.00"), "Entrada da O.S.")
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PAGO)
        self.assertEqual(orcamento.valor_pago, Decimal("450.00"))

        envio = self.post_interno("/ordens-servico/", {
            "action": "enviar",
            "id": ordem.pk,
            "canal": "link",
        })
        self.assertEqual(envio.status_code, 200)
        ordem.refresh_from_db()
        self.assertEqual(
            ordem.status, OrdemServico.Status.AGUARDANDO_RESPOSTA
        )
        self.client.post(ordem.caminho_publico, {"nome": "Ana Cliente"})
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, OrdemServico.Status.ABERTA)
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)

    def test_ordem_direta_salva_itens_e_tem_cards_proprios(self):
        resposta = self.post_interno("/ordens-servico/", {
            "action": "save",
            "nome_cliente": "Cliente balcão",
            "tipo": OrdemServico.Tipo.MANUTENCAO,
            "status": OrdemServico.Status.EM_EXECUCAO,
            "prioridade": OrdemServico.Prioridade.ALTA,
            "equipamento": "Tobogã inflável",
            "itens": json.dumps([{
                "tipo": ItemOrdemServico.Tipo.SERVICO,
                "descricao": "Troca de costura",
                "quantidade": "2,00",
                "valor_unitario": "125,00",
            }]),
        })

        self.assertEqual(resposta.status_code, 200)
        ordem = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertEqual(ordem.total, Decimal("250.00"))
        self.assertIsNotNone(ordem.iniciada_em)
        self.assertIsNone(ordem.orcamento_id)

        pagina = self.client.get(
            "/ordens-servico/",
            {"filtro": "execucao"},
            HTTP_HOST="interno.testserver",
        )
        self.assertContains(pagina, ordem.numero_documento)
        self.assertEqual(pagina.context["filtro_ativo"], "execucao")

    def test_envio_publicacao_impressao_pix_e_ciencia_sao_da_os(self):
        ordem = OrdemServico.objects.create(
            nome_cliente="Cliente técnico",
            whatsapp_cliente="(11) 99999-2222",
            equipamento="Cama elástica",
            status=OrdemServico.Status.CONCLUIDA,
            responsavel=self.gestor,
        )
        ItemOrdemServico.objects.create(
            ordem=ordem,
            tipo=ItemOrdemServico.Tipo.PECA,
            descricao="Lona de salto",
            quantidade=1,
            valor_unitario=Decimal("380.00"),
        )

        self.assertEqual(self.client.get(ordem.caminho_publico).status_code, 404)
        resposta = self.post_interno("/ordens-servico/", {
            "action": "enviar",
            "id": ordem.pk,
            "canal": "link",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(ordem.caminho_publico, resposta.json()["link"])

        pagina = self.client.get(ordem.caminho_publico)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Imprimir ou salvar em PDF")
        self.assertContains(pagina, "Copiar Pix")
        self.assertContains(pagina, "Confirmar recebimento")
        self.assertContains(pagina, "data:image/png;base64,")

        resposta = self.client.post(ordem.caminho_publico, {"nome": "Carlos Cliente"})
        self.assertEqual(resposta.status_code, 302)
        ordem.refresh_from_db()
        self.assertEqual(ordem.cliente_ciente_por, "Carlos Cliente")

    def test_pagamentos_permanecem_em_historicos_separados(self):
        orcamento = self.criar_orcamento()
        ordem = OrdemServico.objects.create(
            orcamento=orcamento,
            nome_cliente="Buffet Alegria",
            equipamento="Brinquedo",
        )
        ItemOrdemServico.objects.create(
            ordem=ordem,
            descricao="Manutenção",
            quantidade=1,
            valor_unitario=Decimal("300.00"),
        )

        resposta = self.post_interno("/ordens-servico/", {
            "action": "pagamento",
            "id": ordem.pk,
            "valor_pago": "150,00",
            "observacao_pagamento": "Sinal",
        })
        self.assertEqual(resposta.status_code, 200)
        ordem.refresh_from_db()
        orcamento.refresh_from_db()
        self.assertEqual(ordem.status_pagamento, OrdemServico.StatusPagamento.PARCIAL)
        self.assertEqual(ordem.valor_pago, Decimal("150.00"))
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PENDENTE)
        self.assertEqual(orcamento.valor_pago, Decimal("0.00"))
