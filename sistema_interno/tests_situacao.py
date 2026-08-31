"""Cada situação mostra só o que faz sentido fazer nela.

O PROBLEMA ERA A LISTA SEMPRE IGUAL. Os mesmos botões apareciam em toda
linha, independentemente do estado do documento, e cada um deles falhava
de um jeito diferente quando não cabia:

  * "Pagamento" numa proposta já quitada abria uma janela pedindo um
    valor que já estava lá. A leitura era "será que não registrou?".
  * "Enviar" numa proposta vencida gerava o link de uma página que
    anuncia "proposta expirada" -- mandar isso ao cliente é pior do que
    não mandar nada.

Botão que não cabe não é neutro: ele ensina a duvidar dos outros.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ItemOrcamento, Orcamento


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AcoesConformeASituacaoTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-situacao", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def proposta(self, *, status=Orcamento.Status.RASCUNHO, dias=5, pago="0.00"):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            email_cliente="cliente@example.com",
            status=status,
            validade=timezone.localdate() + timedelta(days=dias),
            responsavel=self.gestor,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=Decimal("500.00"),
        )
        if Decimal(pago) > 0:
            orcamento.registrar_pagamento(Decimal(pago))
        return orcamento

    # PROCURAR PELO ID, E NÃO PELO ATRIBUTO SOLTO. A tela sempre carrega
    # `document.querySelectorAll("[data-enviar]")` e as fichas de atalho
    # `data-pagamento-atalho`; procurar só "data-enviar" acharia o script
    # e diria que o botão está lá mesmo quando nenhuma linha o traz.
    def botao_enviar(self, orcamento):
        return 'data-enviar="%d"' % orcamento.pk

    def botao_pagamento(self, orcamento):
        return 'data-pagamento="%d"' % orcamento.pk

    def lista(self):
        return self.client.get(
            "/orcamentos/", {"filtro": "todos"}, HTTP_HOST="interno.testserver",
        ).content.decode()

    # -------------------------------------------------------- enviar
    def test_rascunho_pode_ser_enviado(self):
        self.proposta()

        rascunho = Orcamento.objects.get()
        self.assertTrue(rascunho.pode_enviar)
        self.assertIn(self.botao_enviar(rascunho), self.lista())

    def test_vencida_nao_gera_mais_link(self):
        """O link levaria a uma página que anuncia "proposta expirada"."""
        vencida = self.proposta(
            status=Orcamento.Status.AGUARDANDO_RESPOSTA, dias=-1,
        )

        self.assertTrue(vencida.vencido)
        self.assertFalse(vencida.pode_enviar)
        self.assertNotIn(self.botao_enviar(vencida), self.lista())

    def test_vencida_oferece_refazer_no_lugar(self):
        """Não é só tirar o botão: o caminho certo tem de aparecer."""
        vencida = self.proposta(
            status=Orcamento.Status.AGUARDANDO_RESPOSTA, dias=-1,
        )

        self.assertTrue(vencida.pode_refazer)
        self.assertIn('value="refazer"', self.lista())

    def test_respondida_nao_e_reenviada(self):
        """Reenviar pediria uma decisão que o cliente já tomou."""
        for status in (Orcamento.Status.APROVADO, Orcamento.Status.RECUSADO):
            with self.subTest(status=status):
                Orcamento.objects.all().delete()
                self.proposta(status=status)

                self.assertFalse(Orcamento.objects.get().pode_enviar)

    def test_substituida_nao_e_reenviada_nem_refeita(self):
        self.proposta(status=Orcamento.Status.SUBSTITUIDO)

        orcamento = Orcamento.objects.get()
        self.assertFalse(orcamento.pode_enviar)
        self.assertFalse(orcamento.pode_refazer)

    def test_todos_mostra_somente_versao_atual(self):
        anterior = self.proposta(status=Orcamento.Status.SUBSTITUIDO)
        atual = self.proposta(status=Orcamento.Status.RASCUNHO)

        todos = self.lista()
        self.assertNotIn(f'data-registro="{anterior.pk}"', todos)
        self.assertIn(f'data-registro="{atual.pk}"', todos)

        historico = self.client.get(
            "/orcamentos/", {"filtro": "substituidos"},
            HTTP_HOST="interno.testserver",
        ).content.decode()
        self.assertIn(f'data-registro="{anterior.pk}"', historico)
        self.assertNotIn(f'data-registro="{atual.pk}"', historico)

    def test_quitada_nao_e_refeita(self):
        """Refazer substitui a atual -- e o dinheiro entrou contra ela."""
        self.proposta(status=Orcamento.Status.APROVADO, pago="500.00")

        quitada = Orcamento.objects.get()
        self.assertTrue(quitada.quitado)
        self.assertFalse(quitada.pode_refazer)

    def test_o_servidor_recusa_refazer_uma_proposta_paga(self):
        quitada = self.proposta(status=Orcamento.Status.APROVADO, pago="500.00")

        resposta = self.client.post(
            "/orcamentos/",
            {"action": "refazer", "id": quitada.pk},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 400)
        quitada.refresh_from_db()
        self.assertEqual(quitada.status, Orcamento.Status.APROVADO)
        self.assertFalse(hasattr(quitada, "orcamento_refeito"))

    # ------------------------------------------------------ pagamento
    def test_aprovada_sem_pagamento_mostra_o_botao(self):
        self.proposta(status=Orcamento.Status.APROVADO)

        aprovada = Orcamento.objects.get()
        self.assertTrue(aprovada.pode_receber_pagamento)
        self.assertIn(self.botao_pagamento(aprovada), self.lista())

    def test_edicao_do_orcamento_traz_resumo_e_abertura_do_pagamento(self):
        aprovada = self.proposta(
            status=Orcamento.Status.APROVADO, pago="200.00",
        )

        html = self.lista()
        self.assertIn('id="orcamentoPagamentoResumo"', html)
        self.assertIn('id="abrirPagamentoOrcamento"', html)
        self.assertIn('"pode_receber_pagamento": true', html)
        self.assertIn('"valor_pago": "200,00"', html)
        self.assertIn('"saldo_pagamento": "300,00"', html)
        self.assertIn(f'"id": {aprovada.pk}', html)

    def test_parcial_convida_a_completar(self):
        self.proposta(status=Orcamento.Status.APROVADO, pago="200.00")

        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.status_pagamento, Orcamento.StatusPagamento.PARCIAL)
        self.assertTrue(orcamento.pode_receber_pagamento)

        html = self.lista()
        self.assertIn("Completar pagamento", html)
        # E diz quanto falta, que é o número que a pessoa procura ali.
        self.assertIn("faltam R$ 300,00", html)

    def test_quitada_esconde_o_botao_e_anuncia_que_esta_paga(self):
        """O botão continuava aparecendo, e apertar abria uma janela
        pedindo um valor que já estava lá."""
        self.proposta(status=Orcamento.Status.APROVADO, pago="500.00")

        orcamento = Orcamento.objects.get()
        self.assertTrue(orcamento.quitado)
        self.assertFalse(orcamento.pode_receber_pagamento)

        html = self.lista()
        self.assertNotIn(self.botao_pagamento(orcamento), html)
        self.assertIn("ls-pago", html)

    def test_nao_aprovada_nao_recebe_pagamento(self):
        """Pagamento antes da aprovação é dinheiro sem documento."""
        self.proposta(status=Orcamento.Status.AGUARDANDO_RESPOSTA)

        self.assertFalse(Orcamento.objects.get().pode_receber_pagamento)

    def test_o_servidor_recusa_o_pagamento_que_a_tela_nao_oferece(self):
        """A tela é sugestão; a regra é aqui, que é por onde os dados entram."""
        aguardando = self.proposta(status=Orcamento.Status.AGUARDANDO_RESPOSTA)

        resposta = self.client.post(
            "/orcamentos/",
            {"action": "pagamento", "id": aguardando.pk, "valor_pago": "500,00"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 400)
        aguardando.refresh_from_db()
        self.assertEqual(aguardando.valor_pago, Decimal("0.00"))


class QuadroDePagamentoTests(TestCase):
    """O resumo era um `alert-light` do Bootstrap: branco no escuro.

    O "total a pagar" -- o número mais importante da janela -- saía branco
    no branco. Não era descuido de cor: era uma classe do Bootstrap que o
    tema da casa nunca cobriu.
    """

    def test_nenhuma_janela_de_pagamento_usa_o_alerta_branco(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent / "templates"
        for nome in ("orcamentos_inner.html", "ordens_servico_inner.html"):
            with self.subTest(tela=nome):
                texto = (raiz / nome).read_text(encoding="utf-8")
                self.assertNotIn("alert-light", texto)
                self.assertIn("ls-pagamento-quadro", texto)


class RefinamentosDaListaDeOrcamentosTests(TestCase):
    def test_id_substitui_a_cerquilha(self):
        from pathlib import Path

        texto = (
            Path(__file__).resolve().parent / "templates" / "orcamentos_inner.html"
        ).read_text(encoding="utf-8")
        self.assertIn("<th>ID</th>", texto)
        self.assertIn('data-rotulo="ID"', texto)
        self.assertNotIn("<th>#</th>", texto)

    def test_filtro_atualiza_a_lista_sem_alterar_a_url_visivel(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent
        tela = (raiz / "templates" / "orcamentos_inner.html").read_text(encoding="utf-8")
        navegacao = (raiz / "static" / "interno" / "ls-soft-navigation.js").read_text(encoding="utf-8")
        self.assertIn("data-orcamento-filtro", tela)
        self.assertIn("LSNavigation.silent(card.href)", tela)
        self.assertIn('silent: function (url) { navegar(url, "none"); }', navegacao)

    def test_cadastrar_fica_antes_da_lista_de_resultados(self):
        from pathlib import Path

        busca = (
            Path(__file__).resolve().parent / "static" / "interno" / "ls-busca.js"
        ).read_text(encoding="utf-8")
        criar = busca.index("painel.appendChild(rodape)")
        resultados = busca.index("painel.appendChild(lista)")
        self.assertLess(criar, resultados)

    def test_tablet_usa_grade_centralizada_de_tres_colunas(self):
        from pathlib import Path

        css = (
            Path(__file__).resolve().parent / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")
        self.assertIn("ORÇAMENTOS — LARGURA ÚTIL NO PC", css)
        self.assertIn(".ls-orcamentos-table tbody{max-width:860px;margin-inline:auto}", css)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))!important", css)


class OrdemDeLeituraDoModalTests(TestCase):
    """O bloco do dinheiro vinha antes dos itens que ele soma.

    Quem monta a proposta preenchia frete e desconto de um documento que
    ainda não tinha um único item -- e o desconto em "%" mostrava dez por
    cento de zero. Ou se preenchia fora da ordem da tela, ou se voltava
    lá em cima depois de montar a lista.
    """

    def test_o_financeiro_vem_depois_dos_itens(self):
        from pathlib import Path

        modal = (
            Path(__file__).resolve().parent / "templates" / "orcamentos_inner.html"
        ).read_text(encoding="utf-8")

        comercial = modal.index("Bloco Comercial")
        itens = modal.index("Itens da proposta")
        financeiro = modal.index("Bloco Financeiro")
        total = modal.index('id="resumoTotal"')

        # A leitura desce na ordem em que a conta acontece: quem é o
        # cliente, o que ele leva, quanto isso muda o preço, e o total.
        self.assertLess(comercial, itens)
        self.assertLess(itens, financeiro)
        self.assertLess(financeiro, total)
