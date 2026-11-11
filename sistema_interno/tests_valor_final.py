"""O valor final combinado do orçamento ("fica R$ 18.000 tudo").

O que estes testes protegem:

  * preenchido, o valor final é o total da proposta, seja qual for a soma
    dos itens, do frete e do desconto -- e trocar um item depois não muda o
    total; abaixo da soma a diferença aparece como desconto, acima como
    ajuste;
  * o formulário grava o valor no formato brasileiro e, com ele, zera o
    desconto guardado (senão ele contaria duas vezes); sem o campo, volta à
    conta de sempre;
  * as somas em SQL (o topo da lista de orçamentos e a ficha do cliente)
    usam o valor final igual ao `Orcamento.total`;
  * a página que o cliente abre mostra o "Desconto especial" (ou o ajuste)
    e o total combinado;
  * o retrato assinado de uma proposta sem valor final continua o mesmo de
    antes do campo (o hash dos aceites antigos não muda);
  * a tela tem a chave "Definir o valor final à mão" e o campo do valor.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .assinaturas import conteudo_canonico
from .models import ItemOrcamento, Orcamento


class ValorFinalTests(TestCase):
    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor", password="senha-segura", email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

    def criar(self, **campos):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            contato="(11) 90000-0000",
            frete=Decimal("500.00"),
            **campos,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Brinquedão", quantidade=2,
            valor_unitario=Decimal("9000.00"),
        )
        return orcamento

    def post(self, dados):
        return self.client.post(
            self.URL, dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # ------------------------------------------------------------ a conta
    def test_valor_final_e_o_total_seja_qual_for_a_soma(self):
        orcamento = self.criar(desconto=Decimal("100.00"), valor_final=Decimal("18000.00"))

        self.assertEqual(orcamento.bruto, Decimal("18500.00"))
        self.assertEqual(orcamento.total, Decimal("18000.00"))
        self.assertTrue(orcamento.valor_final_fixo)
        self.assertEqual(orcamento.desconto_aplicado, Decimal("500.00"))
        self.assertEqual(orcamento.acrescimo_aplicado, Decimal("0.00"))

        # trocar um item depois não muda o total combinado
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica", quantidade=1,
            valor_unitario=Decimal("2000.00"),
        )
        orcamento = Orcamento.objects.get(pk=orcamento.pk)
        self.assertEqual(orcamento.total, Decimal("18000.00"))
        self.assertEqual(orcamento.desconto_aplicado, Decimal("2500.00"))

    def test_acima_da_soma_vira_ajuste(self):
        orcamento = self.criar(valor_final=Decimal("19000.00"))

        self.assertEqual(orcamento.total, Decimal("19000.00"))
        self.assertEqual(orcamento.desconto_aplicado, Decimal("0.00"))
        self.assertEqual(orcamento.acrescimo_aplicado, Decimal("500.00"))

    def test_sem_valor_final_e_a_conta_de_sempre(self):
        orcamento = self.criar(desconto=Decimal("300.00"))

        self.assertFalse(orcamento.valor_final_fixo)
        self.assertEqual(orcamento.total, Decimal("18200.00"))
        self.assertEqual(orcamento.desconto_aplicado, Decimal("300.00"))

    # ------------------------------------------------------- o formulário
    def salvar(self, **extra):
        dados = {
            "action": "save",
            "nome_cliente": "Buffet Alegria",
            "status": Orcamento.Status.AGUARDANDO_RESPOSTA,
            "frete": "500,00",
            "desconto": "100,00",
            "itens": '[{"descricao":"Brinquedão","quantidade":"2","valor_unitario":"9.000,00"}]',
        }
        dados.update(extra)
        return self.post(dados)

    def test_formulario_grava_o_valor_final_e_zera_o_desconto(self):
        resposta = self.salvar(valor_final="18.000,00")

        self.assertEqual(resposta.status_code, 200, resposta.content[:400])
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.valor_final, Decimal("18000.00"))
        self.assertEqual(orcamento.desconto, Decimal("0.00"))
        self.assertEqual(orcamento.total, Decimal("18000.00"))

    def test_formulario_sem_valor_final_volta_a_conta(self):
        self.salvar(valor_final="18.000,00")
        orcamento = Orcamento.objects.get()

        resposta = self.salvar(id=str(orcamento.pk))

        self.assertEqual(resposta.status_code, 200, resposta.content[:400])
        orcamento.refresh_from_db()
        self.assertIsNone(orcamento.valor_final)
        self.assertEqual(orcamento.desconto, Decimal("100.00"))
        self.assertEqual(orcamento.total, Decimal("18400.00"))

    def test_valor_final_negativo_e_recusado(self):
        resposta = self.salvar(valor_final="-10,00")

        self.assertNotEqual(resposta.status_code, 200)
        self.assertFalse(Orcamento.objects.exists())

    # ---------------------------------------------------------- somas em SQL
    def test_topo_da_lista_soma_o_valor_final(self):
        self.criar(status=Orcamento.Status.APROVADO, valor_final=Decimal("18000.00"))
        self.criar(status=Orcamento.Status.APROVADO, desconto=Decimal("500.00"))
        esperado = sum((o.total for o in Orcamento.objects.all()), Decimal("0.00"))

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(esperado, Decimal("36000.00"))
        self.assertEqual(resposta.context["total_aprovado"], esperado)

    def test_ficha_do_cliente_soma_o_valor_final(self):
        from .views_clientes import ClientesInnerView

        self.criar(status=Orcamento.Status.APROVADO, valor_final=Decimal("18000.00"))

        linha = ClientesInnerView._orcamentos_resumidos().get()

        self.assertEqual(linha._total_calculado, Decimal("18000.00"))

    # ------------------------------------------------- a página do cliente
    def test_pagina_do_cliente_mostra_desconto_especial_e_total(self):
        orcamento = self.criar(
            status=Orcamento.Status.AGUARDANDO_RESPOSTA, valor_final=Decimal("18000.00"),
        )

        resposta = self.client.get(f"/orcamento/{orcamento.token}/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Desconto especial")
        self.assertContains(resposta, "500,00")
        self.assertContains(resposta, "18.000,00")

    def test_pagina_do_cliente_mostra_ajuste_acima_da_soma(self):
        orcamento = self.criar(
            status=Orcamento.Status.AGUARDANDO_RESPOSTA, valor_final=Decimal("19000.00"),
        )

        resposta = self.client.get(f"/orcamento/{orcamento.token}/")

        self.assertContains(resposta, "Ajuste do valor combinado")
        self.assertNotContains(resposta, "Desconto especial")

    # ------------------------------------------------- aceite e tela
    def test_retrato_assinado_sem_valor_final_nao_muda(self):
        sem = conteudo_canonico(self.criar())
        com = conteudo_canonico(self.criar(valor_final=Decimal("18000.00")))

        self.assertNotIn("valor_final", sem)
        self.assertEqual(com["valor_final"], "18000.00")
        self.assertEqual(com["total"], "18000.00")

    def test_tela_tem_a_chave_e_o_campo_do_valor_final(self):
        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertContains(resposta, 'id="valorFinalFixar"')
        self.assertContains(resposta, 'name="valor_final"')
        self.assertContains(resposta, "Definir o valor final à mão")
