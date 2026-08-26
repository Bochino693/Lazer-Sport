"""A página de orçamento que o cliente abre, e a resposta que ele dá.

O que estes testes protegem, em ordem de importância:

  * um orçamento não vaza por outro — o token é a única chave;
  * rascunho não tem página, porque a equipe ainda está montando;
  * a resposta é registrada UMA vez: aprovada, a proposta vira comprovante
    e para de aceitar mudança, inclusive por quem tem o link;
  * proposta vencida não vira venda por descuido.

São as regras que sustentam a decisão de a página ser aberta por link, sem
login. Se alguma cair, o link deixa de ser seguro.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from sistema_interno.models import Cliente, EnderecoCliente, ItemOrcamento, Orcamento

from .models import Brinquedos, CategoriasBrinquedos


class OrcamentoPublicoTests(TestCase):

    def setUp(self):
        self.categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Infláveis",
        )
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Tobogã inflável",
            descricao="Tobogã de 6 metros",
            valor_brinquedo=Decimal("520.00"),
            avaliacao=Decimal("5.00"),
            voltz="220",
        )
        self.brinquedo.categorias_brinquedos.add(self.categoria)

        self.orcamento = Orcamento.objects.create(
            nome_cliente="Fulano de Tal",
            contato="11 90000-0000",
            status=Orcamento.Status.ENVIADO,
            validade=timezone.localdate() + timedelta(days=7),
            frete=Decimal("100.00"),
            desconto=Decimal("50.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            descricao="Tobogã inflável",
            brinquedo=self.brinquedo,
            quantidade=2,
            valor_unitario=Decimal("520.00"),
        )

    def url(self, orcamento=None):
        alvo = orcamento or self.orcamento
        return reverse("orcamento_publico", args=[alvo.token])

    # ------------------------------------------------------------ leitura
    def test_pagina_mostra_itens_e_total(self):
        resposta = self.client.get(self.url())

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Tobogã inflável")
        self.assertContains(resposta, "Fulano de Tal")
        # 2 x 520 = 1040, + 100 de frete, - 50 de desconto = 1.090,00
        self.assertContains(resposta, "1.090,00")

    def test_documento_mostra_cliente_pagamento_envio_e_decisao(self):
        cliente = Cliente.objects.create(
            nome_cliente="R3 Boteco Original Ltda",
            tipo=Cliente.Tipo.EMPRESA,
            documento="48.646.647/0001-11",
            telefone="(11) 95388-7201",
            email="compras@example.com",
        )
        EnderecoCliente.objects.create(
            cliente=cliente,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="300",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
        )
        self.orcamento.cliente = cliente
        self.orcamento.forma_pagamento = "Pix"
        self.orcamento.forma_envio = "Transportadora"
        self.orcamento.save(update_fields=[
            "cliente", "forma_pagamento", "forma_envio",
        ])

        resposta = self.client.get(self.url())

        self.assertContains(resposta, "Dados do cliente")
        self.assertContains(resposta, "48.646.647/0001-11")
        self.assertContains(resposta, "Praça da Sé")
        self.assertContains(resposta, "Pix")
        self.assertContains(resposta, "Transportadora")
        self.assertContains(resposta, "Aprovar proposta")
        self.assertContains(resposta, "Recusar")

    def test_token_desconhecido_nao_existe(self):
        resposta = self.client.get(
            reverse("orcamento_publico", args=["token-que-nunca-foi-gerado"])
        )
        self.assertEqual(resposta.status_code, 404)

    def test_rascunho_nao_tem_pagina(self):
        """A equipe ainda está montando: para quem tem o link, não existe."""
        self.orcamento.status = Orcamento.Status.RASCUNHO
        self.orcamento.save(update_fields=["status"])

        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_cada_orcamento_tem_token_proprio(self):
        outro = Orcamento.objects.create(
            nome_cliente="Sicrano",
            status=Orcamento.Status.ENVIADO,
        )
        self.assertNotEqual(outro.token, self.orcamento.token)

        # e um não abre a página do outro
        resposta = self.client.get(self.url(outro))
        self.assertNotContains(resposta, "Fulano de Tal")

    # ----------------------------------------------------------- resposta
    def test_aprovar_registra_nome_e_muda_situacao(self):
        resposta = self.client.post(
            self.url(),
            {"decisao": "aprovar", "nome": "Fulano de Tal"},
        )

        self.assertEqual(resposta.status_code, 302)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.APROVADO)
        self.assertEqual(self.orcamento.respondido_por, "Fulano de Tal")
        self.assertIsNotNone(self.orcamento.respondido_em)

    @patch(
        "core.models.geocodificar_endereco",
        return_value=(-23.550520, -46.633308, "rua"),
    )
    def test_aprovacao_do_cliente_publica_o_cadastro_no_mapa(self, _geocodificar):
        cliente = Cliente.objects.create(
            nome_cliente="Colégio Sol",
            telefone="(11) 99999-1111",
        )
        EnderecoCliente.objects.create(
            cliente=cliente,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="20",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
        )
        self.orcamento.cliente = cliente
        self.orcamento.save(update_fields=["cliente"])

        self.client.post(
            self.url(),
            {"decisao": "aprovar", "nome": "Responsável do colégio"},
        )

        cliente.refresh_from_db()
        self.assertIsNotNone(cliente.cliente_mapa_id)
        self.assertEqual(cliente.cliente_mapa.cidade, "São Paulo")

    def test_recusar_guarda_o_motivo(self):
        self.client.post(
            self.url(),
            {
                "decisao": "recusar",
                "nome": "Fulano de Tal",
                "motivo": "Ficou acima do orçamento da festa.",
            },
        )

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.RECUSADO)
        self.assertEqual(
            self.orcamento.motivo_recusa,
            "Ficou acima do orçamento da festa.",
        )

    def test_aprovar_nao_guarda_motivo_de_recusa(self):
        """Motivo é da recusa. Aprovando, some — senão fica pendurado."""
        self.orcamento.motivo_recusa = "sobra de uma recusa anterior"
        self.orcamento.save(update_fields=["motivo_recusa"])

        self.client.post(
            self.url(),
            {"decisao": "aprovar", "nome": "Fulano", "motivo": "qualquer coisa"},
        )

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.motivo_recusa, "")

    def test_sem_nome_nao_registra(self):
        resposta = self.client.post(self.url(), {"decisao": "aprovar", "nome": "  "})

        self.assertEqual(resposta.status_code, 400)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.ENVIADO)

    def test_decisao_invalida_nao_registra(self):
        resposta = self.client.post(
            self.url(),
            {"decisao": "talvez", "nome": "Fulano"},
        )

        self.assertEqual(resposta.status_code, 400)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.ENVIADO)

    def test_resposta_e_definitiva(self):
        """Aprovada, a proposta não vira recusada por um segundo clique."""
        self.client.post(self.url(), {"decisao": "aprovar", "nome": "Fulano"})
        self.client.post(self.url(), {"decisao": "recusar", "nome": "Fulano"})

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.APROVADO)

    def test_vencido_nao_aceita_resposta(self):
        self.orcamento.validade = timezone.localdate() - timedelta(days=1)
        self.orcamento.save(update_fields=["validade"])

        self.client.post(self.url(), {"decisao": "aprovar", "nome": "Fulano"})

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.ENVIADO)

    def test_vencido_ainda_pode_ser_consultado(self):
        """Vencer tira o botão, não a proposta: o cliente ainda quer ver."""
        self.orcamento.validade = timezone.localdate() - timedelta(days=1)
        self.orcamento.save(update_fields=["validade"])

        resposta = self.client.get(self.url())

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Tobogã inflável")
        self.assertContains(resposta, "validade desta proposta terminou")

    def test_pagina_respondida_nao_mostra_botao(self):
        self.client.post(self.url(), {"decisao": "aprovar", "nome": "Fulano"})

        resposta = self.client.get(self.url())

        self.assertContains(resposta, "Resposta registrada")
        self.assertNotContains(resposta, "Aprovar proposta")

    def test_pagina_nao_e_indexada(self):
        """Proposta comercial no Google seria vazamento de preço."""
        resposta = self.client.get(self.url())
        self.assertContains(resposta, "noindex")


class OrcamentoModeloTests(TestCase):
    """Regras que vivem no modelo, sem passar pela página."""

    def test_marcar_enviado_carimba_uma_vez(self):
        orcamento = Orcamento.objects.create(nome_cliente="Fulano")
        self.assertEqual(orcamento.status, Orcamento.Status.RASCUNHO)

        orcamento.marcar_enviado()
        primeira = orcamento.enviado_em

        self.assertEqual(orcamento.status, Orcamento.Status.ENVIADO)
        self.assertIsNotNone(primeira)

        # reenviar não reescreve a data: o que interessa é quando a
        # proposta saiu pela primeira vez
        orcamento.marcar_enviado()
        self.assertEqual(orcamento.enviado_em, primeira)

    def test_dias_para_vencer_distingue_sem_validade_de_vence_hoje(self):
        sem = Orcamento.objects.create(nome_cliente="Sem validade")
        hoje = Orcamento.objects.create(
            nome_cliente="Vence hoje",
            validade=timezone.localdate(),
        )

        self.assertIsNone(sem.dias_para_vencer)
        self.assertEqual(hoje.dias_para_vencer, 0)

    def test_desconto_maior_que_tudo_nao_deixa_total_negativo(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Fulano",
            desconto=Decimal("9999.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Cama elástica",
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )

        self.assertEqual(orcamento.total, Decimal("0.00"))

    def test_item_nao_vem_do_catalogo_e_da_producao_ao_mesmo_tempo(self):
        from django.core.exceptions import ValidationError

        from sistema_interno.models import ProdutoInterno

        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Piscina de bolinhas",
            descricao="3x3",
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        produto = ProdutoInterno.objects.create(nome="Piscina — versão fábrica")

        orcamento = Orcamento.objects.create(nome_cliente="Fulano")
        item = ItemOrcamento(
            orcamento=orcamento,
            descricao="Piscina",
            brinquedo=brinquedo,
            produto=produto,
            quantidade=1,
            valor_unitario=Decimal("340.00"),
        )

        with self.assertRaises(ValidationError):
            item.clean()
