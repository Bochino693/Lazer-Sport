import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import AvaliacaoBlocoOrcamento, AvaliacaoSetor, ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class SetorizacaoInternaTests(TestCase):
    host = "interno.testserver"

    def usuario(self, nome, *funcoes, superusuario=False):
        if superusuario:
            return User.objects.create_superuser(nome, f"{nome}@example.com", "senha-segura")
        usuario = User.objects.create_user(nome, password="senha-segura")
        atribuir_funcoes(usuario, funcoes)
        return usuario

    def post_orcamento(self, usuario, dados):
        self.client.force_login(usuario)
        return self.client.post(
            "/orcamentos/",
            dados,
            HTTP_HOST=self.host,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_ambulante_cria_origem_externa_e_enxerga_so_a_propria_carteira(self):
        ambulante = self.usuario("ana-rua", "ambulante")
        outro = self.usuario("bia-rua", "ambulante")
        resposta = self.post_orcamento(ambulante, {
            "action": "save",
            "nome_cliente": "Buffet visitado",
            "status": "rascunho",
            "itens": json.dumps([{
                "descricao": "Apresentação externa",
                "quantidade": 1,
                "valor_unitario": "150,00",
            }]),
        })
        self.assertEqual(resposta.status_code, 200)
        proposta = Orcamento.objects.get()
        self.assertEqual(proposta.origem, Orcamento.Origem.AMBULANTE)
        self.assertEqual(proposta.responsavel, ambulante)

        Orcamento.objects.create(nome_cliente="Carteira de outra pessoa", responsavel=outro)
        pagina = self.client.get("/orcamentos/", HTTP_HOST=self.host)
        self.assertContains(pagina, "Buffet visitado")
        self.assertNotContains(pagina, "Carteira de outra pessoa")

    def test_financeiro_altera_condicoes_sem_sobrescrever_o_comercial(self):
        financeiro = self.usuario("fin", "financeiro")
        comercial = self.usuario("vendas", "vendas")
        self.client.force_login(financeiro)
        clientes = self.client.get("/clientes/", HTTP_HOST=self.host)
        self.assertRedirects(
            clientes, "/financeiro/", fetch_redirect_response=False,
        )
        proposta = Orcamento.objects.create(
            nome_cliente="Cliente preservado",
            forma_envio="Entrega própria",
            responsavel=comercial,
        )
        ItemOrcamento.objects.create(
            orcamento=proposta,
            descricao="Item preservado",
            quantidade=1,
            valor_unitario=Decimal("100.00"),
        )
        pagina = self.client.get("/orcamentos/", HTTP_HOST=self.host)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Bloco Financeiro")
        self.assertNotContains(pagina, 'id="novoOrcamento"')

        resposta = self.post_orcamento(financeiro, {
            "action": "save",
            "id": proposta.id,
            "nome_cliente": "Tentativa de sobrescrever",
            "frete": "25,90",
            "desconto": "10,00",
            "forma_pagamento": "Pix",
            "itens": "[]",
        })
        self.assertEqual(resposta.status_code, 200)
        proposta.refresh_from_db()
        self.assertEqual(proposta.nome_cliente, "Cliente preservado")
        self.assertEqual(proposta.forma_envio, "Entrega própria")
        self.assertEqual(proposta.frete, Decimal("25.90"))
        self.assertEqual(proposta.forma_pagamento, "Pix")
        self.assertEqual(proposta.itens.get().descricao, "Item preservado")

    def test_superadministrador_avalia_cada_bloco_com_parecer(self):
        superadmin = self.usuario("super", superusuario=True)
        proposta = Orcamento.objects.create(nome_cliente="Cliente")
        resposta = self.post_orcamento(superadmin, {
            "action": "avaliar_bloco",
            "id": proposta.id,
            "bloco": "financeiro",
            "status": "ajustes",
            "observacao": "Rever a condição de parcelamento.",
        })
        self.assertEqual(resposta.status_code, 200)
        avaliacao = proposta.avaliacoes_blocos.get(bloco="financeiro")
        self.assertEqual(avaliacao.status, "ajustes")
        self.assertEqual(avaliacao.avaliador, superadmin)
        self.assertIsNotNone(avaliacao.avaliado_em)

    def test_edicao_reabre_somente_o_bloco_que_mudou(self):
        superadmin = self.usuario("super2", superusuario=True)
        proposta = Orcamento.objects.create(nome_cliente="Cliente")
        ItemOrcamento.objects.create(
            orcamento=proposta,
            descricao="Item",
            quantidade=1,
            valor_unitario=Decimal("100.00"),
        )
        for bloco in AvaliacaoBlocoOrcamento.Bloco.values:
            AvaliacaoBlocoOrcamento.objects.create(
                orcamento=proposta,
                bloco=bloco,
                status="aprovado",
                avaliador=superadmin,
            )

        self.post_orcamento(superadmin, {
            "action": "save",
            "id": proposta.id,
            "nome_cliente": "Cliente",
            "status": "rascunho",
            "forma_envio": "",
            "frete": "20,00",
            "desconto": "0,00",
            "forma_pagamento": "",
            "itens": json.dumps([{
                "descricao": "Item",
                "quantidade": 1,
                "valor_unitario": "100,00",
            }]),
        })
        estados = dict(proposta.avaliacoes_blocos.values_list("bloco", "status"))
        self.assertEqual(estados["comercial"], "aprovado")
        self.assertEqual(estados["financeiro"], "pendente")

    def test_avaliacao_mensal_e_exclusiva_do_superadministrador(self):
        superadmin = self.usuario("super3", superusuario=True)
        gestor = self.usuario("gestor", "gestao")
        self.client.force_login(gestor)
        negada = self.client.get("/equipe/avaliacoes/", HTTP_HOST=self.host)
        self.assertEqual(negada.status_code, 302)

        self.client.force_login(superadmin)
        pagina = self.client.get(
            "/equipe/avaliacoes/", {"periodo": "2026-08"}, HTTP_HOST=self.host,
        )
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Avaliação dos setores")
        resposta = self.client.post(
            "/equipe/avaliacoes/",
            {
                "action": "save",
                "setor": "financeiro",
                "periodo": "2026-08",
                "nota": "4",
                "observacao": "Boa previsibilidade; reduzir atrasos.",
            },
            HTTP_HOST=self.host,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200)
        avaliacao = AvaliacaoSetor.objects.get(setor="financeiro")
        self.assertEqual(avaliacao.nota, 4)
        self.assertEqual(avaliacao.periodo.isoformat(), "2026-08-01")
