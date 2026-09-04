"""O recibo de pagamento: o documento que faltava depois do dinheiro.

POR QUE ESTE ARQUIVO EXISTE. O painel registrava o recebimento
(`valor_pago`, o selo "Pago" na lista) e parava ali. Para a empresa
bastava; para quem paga, não: buffet, condomínio e prefeitura precisam
anexar o comprovante à prestação de contas, e o que existia era alguém
da equipe escrevendo um recibo à mão num modelo de Word, com o número
do orçamento copiado de cabeça.

O que os testes protegem, e que já é fácil quebrar sem perceber:

  * o recibo sai do dinheiro REGISTRADO, nunca de um valor digitado --
    recibo e planilha divergindo é um papel que deixa de valer;
  * cada recibo cobre a PARCELA que entrou desde o anterior. Somando os
    recibos de uma proposta paga em duas vezes tem de dar a venda, e não
    o dobro dela;
  * apertar o botão duas vezes não gera dois números para o mesmo
    dinheiro;
  * o documento é imutável e conferível: o que o cliente guardou não
    muda de valor depois.

O painel responde no subdomínio interno, então todo teste de tela usa
HTTP_HOST="interno.testserver" -- sem isso o SubdomainURLMiddleware não
liga `is_interno` e a view devolve um desvio para a loja.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import ItemOrcamento, Orcamento, ReciboOrcamento
from .permissoes import atribuir_funcoes
from .recibos import (
    ReciboIndisponivel,
    conferir,
    emitir_recibo,
    hash_recibo,
    valor_a_documentar,
)


def proposta_paga(valor_pago="520.00", total_unitario="520.00", quantidade=1):
    """Uma proposta aprovada com dinheiro registrado, como o painel faz."""
    orcamento = Orcamento.objects.create(
        nome_cliente="Matheus Silva",
        contato="(11) 90000-0000",
        status=Orcamento.Status.APROVADO,
        forma_pagamento="Pix",
    )
    ItemOrcamento.objects.create(
        orcamento=orcamento,
        descricao="Locação de cama elástica",
        quantidade=quantidade,
        valor_unitario=Decimal(total_unitario),
    )
    orcamento.registrar_pagamento(Decimal(valor_pago), "sinal via Pix")
    return orcamento


class EmissaoDoReciboTests(TestCase):

    def test_o_recibo_sai_do_que_foi_recebido(self):
        orcamento = proposta_paga()

        recibo = emitir_recibo(orcamento)

        self.assertEqual(recibo.valor, Decimal("520.00"))
        self.assertEqual(recibo.total_documento, Decimal("520.00"))
        self.assertTrue(recibo.quitacao)
        self.assertEqual(recibo.sequencia, 1)
        self.assertEqual(recibo.pagador_nome, "Matheus Silva")
        self.assertEqual(recibo.forma_pagamento, "Pix")
        self.assertEqual(recibo.observacao, "sinal via Pix")

    def test_sem_dinheiro_registrado_nao_ha_recibo(self):
        """Recibo de um valor que não entrou é um papel que mente.

        E é o caminho mais curto para isso acontecer: emitir antes de o
        financeiro registrar, "porque o cliente já mandou o comprovante".
        """
        orcamento = Orcamento.objects.create(
            nome_cliente="Sem pagamento",
            status=Orcamento.Status.APROVADO,
        )

        with self.assertRaises(ReciboIndisponivel):
            emitir_recibo(orcamento)

    def test_proposta_nao_aprovada_nao_emite(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Rascunho",
            status=Orcamento.Status.RASCUNHO,
        )

        with self.assertRaises(ReciboIndisponivel):
            emitir_recibo(orcamento)

    def test_o_segundo_recibo_cobre_apenas_a_parcela_nova(self):
        """Somar os recibos tem de dar a venda -- e não o dobro dela.

        Se cada recibo trouxesse o acumulado, os dois papéis somariam
        mais do que o cliente pagou, e é a soma dos recibos que a
        contabilidade de quem recebe lança.
        """
        orcamento = proposta_paga(valor_pago="5000.00", total_unitario="23980.00")

        primeiro = emitir_recibo(orcamento)
        self.assertEqual(primeiro.valor, Decimal("5000.00"))
        self.assertFalse(primeiro.quitacao)
        self.assertEqual(primeiro.saldo, Decimal("18980.00"))

        orcamento.registrar_pagamento(Decimal("23980.00"))
        segundo = emitir_recibo(orcamento)

        self.assertEqual(segundo.valor, Decimal("18980.00"))
        self.assertEqual(segundo.valor_acumulado, Decimal("23980.00"))
        self.assertTrue(segundo.quitacao)
        self.assertEqual(segundo.sequencia, 2)
        self.assertEqual(
            primeiro.valor + segundo.valor, orcamento.total,
        )

    def test_emitir_duas_vezes_seguidas_nao_duplica_o_papel(self):
        """Dois números para o mesmo dinheiro é receita duplicada."""
        orcamento = proposta_paga()
        emitir_recibo(orcamento)

        with self.assertRaises(ReciboIndisponivel):
            emitir_recibo(orcamento)

        self.assertEqual(orcamento.recibos.count(), 1)

    def test_o_que_falta_documentar_e_a_diferenca(self):
        orcamento = proposta_paga(valor_pago="200.00", total_unitario="520.00")
        self.assertEqual(valor_a_documentar(orcamento), Decimal("200.00"))

        emitir_recibo(orcamento)
        self.assertEqual(valor_a_documentar(orcamento), Decimal("0.00"))

        orcamento.registrar_pagamento(Decimal("520.00"))
        self.assertEqual(valor_a_documentar(orcamento), Decimal("320.00"))

    def test_o_recibo_e_imutavel(self):
        """O papel que o cliente guardou não pode mudar de valor depois."""
        recibo = emitir_recibo(proposta_paga())

        recibo.valor = Decimal("1.00")
        with self.assertRaises(ValueError):
            recibo.save()

    def test_o_documento_confere_consigo_mesmo(self):
        recibo = emitir_recibo(proposta_paga())
        recibo.refresh_from_db()

        self.assertTrue(conferir(recibo))
        self.assertEqual(recibo.conteudo_hash, hash_recibo(recibo))

        # Mexer na linha por fora quebra a conferência -- que é o que dá
        # valor ao código impresso no rodapé do recibo.
        ReciboOrcamento.objects.filter(pk=recibo.pk).update(valor=Decimal("99.00"))
        self.assertFalse(conferir(ReciboOrcamento.objects.get(pk=recibo.pk)))

    def test_o_token_do_recibo_nao_e_o_da_proposta(self):
        """Quem paga nem sempre é quem negociou.

        Com o token da proposta, o link do comprovante entregaria junto o
        preço unitário de cada item e a margem da negociação.
        """
        orcamento = proposta_paga()
        recibo = emitir_recibo(orcamento)

        self.assertNotEqual(recibo.token, orcamento.token)
        self.assertNotIn(orcamento.token, recibo.caminho_publico)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ReciboNoPainelTests(TestCase):

    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_a_acao_emite_e_devolve_o_link_pronto(self):
        """Quem emite manda o recibo em seguida; o link vem na resposta."""
        orcamento = proposta_paga()

        resposta = self.post({"action": "recibo", "id": orcamento.pk})
        corpo = resposta.json()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(corpo["status"], "sucesso")
        recibo = orcamento.recibos.get()
        self.assertEqual(corpo["recibo"]["numero"], recibo.numero_documento)
        self.assertIn(recibo.token, corpo["recibo"]["link"])
        self.assertTrue(corpo["recibo"]["quitacao"])

    def test_a_acao_nao_aceita_valor_vindo_da_tela(self):
        """O valor é o do pagamento registrado, e nada mais.

        Se um POST pudesse ditar a quantia, o recibo deixaria de ser
        prova: bastaria mandar outro número.
        """
        orcamento = proposta_paga(valor_pago="200.00", total_unitario="520.00")

        self.post({"action": "recibo", "id": orcamento.pk, "valor": "520,00"})

        self.assertEqual(orcamento.recibos.get().valor, Decimal("200.00"))

    def test_comercial_nao_emite_recibo(self):
        """Quem não declara o recebimento não assina o documento dele."""
        vendedor = User.objects.create_user(
            username="vendedor", password="senha-segura",
        )
        atribuir_funcoes(vendedor, ["vendas"])
        self.client.force_login(vendedor)
        orcamento = proposta_paga()

        resposta = self.post({"action": "recibo", "id": orcamento.pk})

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(orcamento.recibos.count(), 0)

    def test_a_lista_oferece_o_recibo_de_quem_ja_pagou(self):
        pago = proposta_paga()
        aberto = Orcamento.objects.create(
            nome_cliente="Ainda não pagou",
            status=Orcamento.Status.APROVADO,
        )

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        conteudo = resposta.content.decode()

        self.assertIn(f'data-recibo="{pago.pk}"', conteudo)
        self.assertNotIn(f'data-recibo="{aberto.pk}"', conteudo)

    def test_a_lista_mostra_o_recibo_ja_emitido(self):
        orcamento = proposta_paga()
        recibo = emitir_recibo(orcamento, self.gestor)

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        conteudo = resposta.content.decode()

        self.assertIn(recibo.numero_documento, conteudo)
        self.assertIn(recibo.token, conteudo)


class PaginaDoReciboTests(TestCase):
    """A página que o cliente abre pelo link do comprovante."""

    def test_a_pagina_mostra_valor_extenso_e_conferencia(self):
        orcamento = proposta_paga(valor_pago="1520.00", total_unitario="1520.00")
        recibo = emitir_recibo(orcamento)

        resposta = self.client.get(f"/recibo/{recibo.token}/")
        conteudo = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("1.520,00", conteudo)
        # O extenso é o que impede um "1.520,00" de virar outro número a
        # caneta depois de impresso.
        self.assertIn("mil, quinhentos e vinte reais", conteudo)
        self.assertIn(str(recibo.codigo_publico), conteudo)
        self.assertIn("Matheus Silva", conteudo)

    def test_o_recibo_parcial_diz_o_saldo(self):
        orcamento = proposta_paga(valor_pago="500.00", total_unitario="1520.00")
        recibo = emitir_recibo(orcamento)

        conteudo = self.client.get(f"/recibo/{recibo.token}/").content.decode()

        self.assertIn("Recebimento parcial", conteudo)
        self.assertIn("1.020,00", conteudo)

    def test_a_pagina_avisa_quando_o_documento_foi_alterado(self):
        """Recibo mexido no banco não pode aparecer com cara de bom."""
        orcamento = proposta_paga()
        recibo = emitir_recibo(orcamento)
        ReciboOrcamento.objects.filter(pk=recibo.pk).update(valor=Decimal("99.00"))

        conteudo = self.client.get(f"/recibo/{recibo.token}/").content.decode()

        self.assertIn("não confere com o registro original", conteudo)

    def test_token_desconhecido_nao_existe(self):
        self.assertEqual(self.client.get("/recibo/naoexiste/").status_code, 404)

    def test_a_pagina_nao_expoe_o_preco_unitario_da_negociacao(self):
        """O recibo vai para quem paga, e não necessariamente para quem
        negociou: a composição do preço continua na proposta."""
        orcamento = proposta_paga(
            valor_pago="1000.00", total_unitario="500.00", quantidade=2,
        )
        recibo = emitir_recibo(orcamento)

        conteudo = self.client.get(f"/recibo/{recibo.token}/").content.decode()

        self.assertIn("Locação de cama elástica", conteudo)
        self.assertNotIn("500,00", conteudo)
