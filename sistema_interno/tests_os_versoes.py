"""Refazer a O.S., e o item que não vai para a vitrine do site.

O QUE ESTAS DUAS COISAS TÊM EM COMUM. As duas nasceram do mesmo hábito:
gravar por cima. A O.S. era reescrita quando o diagnóstico mudava, e a
peça criada no meio de um documento era publicada no site como se alguém
tivesse decidido anunciá-la. Nos dois casos, o que se perdia era a
escolha original -- o papel que o cliente leu, a vitrine que alguém
montou.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import PecasReposicao

from .models import ItemOrdemServico, Orcamento, OrdemServico


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    SITE_URL="https://www.lazersport.com.br",
)
class RefazerOrdemServicoTests(TestCase):
    """A versão anterior fica; a nova nasce rascunho."""

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-versao", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def post(self, dados):
        return self.client.post(
            "/ordens-servico/",
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def tela(self):
        resposta = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    def criar_ordem(self, status=OrdemServico.Status.ABERTA, **extra):
        ordem = OrdemServico.objects.create(
            nome_cliente="Buffet Alegria",
            equipamento="Cama elástica 3,05 m",
            defeito_relatado="Lona rasgada na emenda",
            status=status,
            **extra,
        )
        ItemOrdemServico.objects.create(
            ordem=ordem,
            tipo=ItemOrdemServico.Tipo.PECA,
            descricao="Lona de salto",
            quantidade=Decimal("1.00"),
            valor_unitario=Decimal("450.00"),
        )
        return ordem

    def refazer(self, ordem, motivo="Ao abrir, o defeito era o motor."):
        return self.post({
            "action": "refazer", "id": ordem.pk, "motivo_refacao": motivo,
        })

    # ------------------------------------------------------ o caminho feliz
    def test_refazer_congela_a_anterior_e_abre_a_seguinte(self):
        """O papel que o cliente leu continua existindo, inteiro."""
        ordem = self.criar_ordem()
        resposta = self.refazer(ordem)
        self.assertEqual(resposta.status_code, 200)

        ordem.refresh_from_db()
        nova = OrdemServico.objects.get(pk=resposta.json()["id"])

        self.assertEqual(ordem.status, OrdemServico.Status.SUBSTITUIDA)
        self.assertEqual(nova.ordem_anterior_id, ordem.pk)
        self.assertEqual(nova.versao, 2)
        # Rascunho: a versão nova ainda vai ser ajustada, e até ser
        # enviada ela não é documento de cliente nenhum.
        self.assertEqual(nova.status, OrdemServico.Status.RASCUNHO)
        self.assertEqual(nova.equipamento, ordem.equipamento)
        self.assertEqual(nova.itens.count(), 1)
        self.assertEqual(nova.total, ordem.total)

    def test_o_motivo_da_troca_e_obrigatorio(self):
        """Duas O.S. com totais diferentes e sem explicação não se defendem.

        Meses depois, quando o cliente reclama do preço, alguém precisa
        conseguir dizer o que mudou entre uma versão e a outra.
        """
        ordem = self.criar_ordem()
        resposta = self.post({"action": "refazer", "id": ordem.pk})

        self.assertEqual(resposta.status_code, 400)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, OrdemServico.Status.ABERTA)

    def test_o_valor_recebido_nao_acompanha_a_versao_nova(self):
        """Copiar o recebido faria a mesma entrada existir duas vezes."""
        ordem = self.criar_ordem()
        ordem.registrar_pagamento(Decimal("100.00"))

        nova = OrdemServico.objects.get(pk=self.refazer(ordem).json()["id"])

        self.assertEqual(nova.valor_pago, Decimal("0.00"))
        self.assertEqual(nova.status_pagamento, OrdemServico.StatusPagamento.PENDENTE)
        ordem.refresh_from_db()
        self.assertEqual(ordem.valor_pago, Decimal("100.00"))

    # ------------------------------------------- o que a situação não deixa
    def test_a_quitada_nao_ganha_versao(self):
        """Congelar o documento contra o qual o dinheiro entrou o apagaria."""
        ordem = self.criar_ordem()
        ordem.registrar_pagamento(ordem.total)

        self.assertEqual(self.refazer(ordem).status_code, 400)
        ordem.refresh_from_db()
        self.assertNotEqual(ordem.status, OrdemServico.Status.SUBSTITUIDA)

    def test_o_rascunho_se_edita_no_lugar(self):
        """Versão de um papel que nunca saiu da mesa é histórico de nada."""
        ordem = self.criar_ordem(status=OrdemServico.Status.RASCUNHO)
        self.assertEqual(self.refazer(ordem).status_code, 400)

    def test_a_cancelada_nao_foi_trocada_por_outra(self):
        """Ela foi encerrada. Recomeçar dali é abrir uma O.S. nova."""
        ordem = self.criar_ordem(status=OrdemServico.Status.CANCELADA)
        self.assertEqual(self.refazer(ordem).status_code, 400)

    def test_refazer_duas_vezes_devolve_a_versao_que_ja_existe(self):
        """Dois cliques no botão não podem criar duas versões irmãs."""
        ordem = self.criar_ordem()
        primeira = self.refazer(ordem).json()["id"]
        segunda = self.refazer(ordem)

        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["id"], primeira)
        self.assertEqual(OrdemServico.objects.count(), 2)

    # ------------------------------------ as ações são em cima da situação
    def test_a_versao_congelada_nao_se_edita_nem_se_envia(self):
        """Editar a versão que o cliente leu apagaria o papel na mão dele."""
        ordem = self.criar_ordem()
        self.refazer(ordem)
        ordem.refresh_from_db()

        self.assertFalse(ordem.pode_editar)
        self.assertFalse(ordem.pode_enviar)
        self.assertFalse(ordem.pode_refazer)
        self.assertFalse(ordem.pode_receber_pagamento)

        salvar = self.post({
            "action": "save", "id": ordem.pk, "equipamento": "Outra coisa",
            "tipo": "manutencao", "status": "aberta", "prioridade": "normal",
            "itens": "[]",
        })
        self.assertEqual(salvar.status_code, 400)
        ordem.refresh_from_db()
        self.assertEqual(ordem.equipamento, "Cama elástica 3,05 m")

    def test_a_cancelada_nao_vai_mais_ao_cliente(self):
        """Pedir decisão sobre um serviço encerrado é pedir o quê?"""
        ordem = self.criar_ordem(status=OrdemServico.Status.CANCELADA)
        self.assertFalse(ordem.pode_enviar)

        resposta = self.post({
            "action": "enviar", "id": ordem.pk, "canal": "link",
        })
        self.assertEqual(resposta.status_code, 400)

    def test_substituida_nao_e_uma_situacao_que_se_escolhe(self):
        """Escolhê-la congelaria uma O.S. sem criar a versão que a substitui."""
        html = self.tela()
        self.assertNotIn('<option value="substituida"', html)

        ordem = self.criar_ordem()
        resposta = self.post({
            "action": "save", "id": ordem.pk,
            "equipamento": ordem.equipamento, "tipo": "manutencao",
            "status": "substituida", "prioridade": "normal",
            "itens": '[{"tipo":"servico","descricao":"x","quantidade":"1","valor_unitario":"10"}]',
        })
        self.assertEqual(resposta.status_code, 400)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, OrdemServico.Status.ABERTA)

    # ------------------------------------------------- a lista e o histórico
    def test_a_versao_anterior_sai_da_lista_e_ganha_um_cartao_proprio(self):
        """Duas linhas do mesmo serviço, com totais diferentes, é cobrança dupla."""
        ordem = self.criar_ordem()
        self.refazer(ordem)
        ordem.refresh_from_db()

        html = self.tela()
        self.assertNotIn(f'data-registro="{ordem.pk}"', html)
        self.assertIn("Versões anteriores", html)

        # Ela não sumiu: o cartão dedicado a traz de volta.
        arquivadas = self.client.get(
            "/ordens-servico/?filtro=substituidas", HTTP_HOST="interno.testserver",
        ).content.decode()
        self.assertIn(f'data-registro="{ordem.pk}"', arquivadas)

    def test_o_recebido_do_topo_nao_conta_a_versao_congelada(self):
        """Somar as duas deixaria o total do topo maior que a soma da lista."""
        ordem = self.criar_ordem()
        ordem.registrar_pagamento(Decimal("200.00"))
        self.refazer(ordem)

        contexto = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).context
        self.assertEqual(contexto["total_recebido"] or Decimal("0.00"), Decimal("0.00"))

    def test_a_faixa_do_topo_responde_com_numero(self):
        """Três das quatro caixas eram frase fixa no lugar de valor.

        "Documento: Operacional", "Orçamento: Negociação separada" e
        "Impressão: A4 e PDF" são verdadeiras e inúteis: não mudam, não
        respondem nada, e ocupavam o topo da tela.
        """
        aberta = self.criar_ordem(status=OrdemServico.Status.ABERTA)
        aberta.registrar_pagamento(Decimal("150.00"))
        concluida = self.criar_ordem(status=OrdemServico.Status.CONCLUIDA)

        contexto = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).context

        # Cada O.S. de teste tem um item de R$ 450,00.
        self.assertEqual(contexto["total_em_servico"], Decimal("450.00"))
        self.assertEqual(contexto["total_concluido"], Decimal("450.00"))
        self.assertEqual(contexto["total_recebido"], Decimal("150.00"))
        # Falta R$ 300,00 da aberta e R$ 450,00 da concluída.
        self.assertEqual(contexto["total_a_receber"], Decimal("750.00"))
        self.assertEqual(concluida.status, OrdemServico.Status.CONCLUIDA)

    def test_o_a_receber_nao_deixa_uma_o_s_paga_a_mais_abater_as_outras(self):
        """Subtrair somas faria a entrada dobrada de um perdoar a dívida de outro."""
        devedora = self.criar_ordem()
        adiantada = self.criar_ordem()
        # Mais do que o total: entrada dobrada, troco pendente.
        adiantada.valor_pago = Decimal("900.00")
        adiantada.status_pagamento = OrdemServico.StatusPagamento.PARCIAL
        adiantada.save(update_fields=["valor_pago", "status_pagamento"])

        contexto = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).context

        # Só o que a devedora deve. A adiantada contribui com zero, e
        # não com −450.
        self.assertEqual(contexto["total_a_receber"], Decimal("450.00"))
        self.assertEqual(devedora.saldo_pagamento, Decimal("450.00"))

    def test_a_faixa_do_topo_ignora_a_versao_congelada(self):
        """Somá-la contaria o mesmo serviço duas vezes."""
        ordem = self.criar_ordem()
        self.refazer(ordem)

        contexto = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).context
        # Sobrou só a versão nova, que nasce rascunho: rascunho não está
        # em serviço aberto nem entra no que há para receber.
        self.assertEqual(contexto["total_em_servico"], Decimal("0.00"))
        self.assertEqual(contexto["total_a_receber"], Decimal("0.00"))

    def test_a_corrente_de_versoes_viaja_com_a_o_s(self):
        """Escondida da lista não pode ser escondida do sistema."""
        ordem = self.criar_ordem()
        nova = OrdemServico.objects.get(pk=self.refazer(ordem).json()["id"])

        versoes = nova.cadeia_de_versoes()
        self.assertEqual([v.pk for v in versoes], [ordem.pk, nova.pk])
        self.assertEqual(nova.numero_com_versao, f"{nova.numero_documento} · v2")
        # A primeira versão não anuncia "v1": isso sugeriria um
        # histórico que a maioria das O.S. não tem.
        self.assertEqual(ordem.numero_com_versao, ordem.numero_documento)

    def test_a_versao_congelada_continua_consultavel(self):
        """É nela que se confere o que tinha sido combinado antes."""
        ordem = self.criar_ordem()
        self.refazer(ordem)

        resposta = self.client.get(
            f"/ordens-servico/{ordem.pk}/previa/", HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 200)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ItemDeManutencaoTests(TestCase):
    """A peça cadastrada dentro de um documento não vira anúncio."""

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-peca", password="x", email="p@example.com",
        )
        self.client.force_login(self.gestor)

    def cadastrar(self, **extra):
        dados = {
            "action": "peca_nova",
            "nome": "Retentor do motor 2019",
            "preco_venda": "80,00",
        }
        dados.update(extra)
        return self.client.post(
            "/orcamentos/", dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_a_peca_nova_nao_entra_no_site(self):
        """Ninguém escolheu publicá-la: foi efeito de precisar cobrar."""
        self.assertEqual(self.cadastrar().status_code, 200)

        peca = PecasReposicao.objects.get(nome="Retentor do motor 2019")
        self.assertFalse(peca.ativo)
        # Sem escolha, o caminho de dentro do documento é o item que a
        # loja não vende.
        self.assertEqual(peca.uso, PecasReposicao.Uso.MANUTENCAO)
        self.assertFalse(PecasReposicao.da_vitrine().filter(pk=peca.pk).exists())

    def test_dá_para_cadastrar_como_peca_da_loja_e_ainda_assim_nao_publicar(self):
        """Publicar continua sendo uma decisão da tela de Produtos."""
        self.assertEqual(self.cadastrar(uso="loja").status_code, 200)

        peca = PecasReposicao.objects.get(nome="Retentor do motor 2019")
        self.assertEqual(peca.uso, PecasReposicao.Uso.LOJA)
        self.assertFalse(peca.ativo)

    def test_item_de_manutencao_nao_aparece_na_vitrine_nem_ativo(self):
        """Ele não foi cadastrado para ser vendido a ninguém."""
        peca = PecasReposicao.objects.create(
            nome="Hora de solda",
            descricao_peca="Mão de obra",
            uso=PecasReposicao.Uso.MANUTENCAO,
            ativo=True,
        )
        self.assertFalse(PecasReposicao.da_vitrine().filter(pk=peca.pk).exists())
        self.assertTrue(peca.de_manutencao)

    def test_a_lista_publica_de_reposicao_mostra_so_a_vitrine(self):
        """Era `.all()`: até a desativada aparecia para o visitante."""
        escondida = PecasReposicao.objects.create(
            nome="Bucha interna 2019", descricao_peca="Só na oficina",
            uso=PecasReposicao.Uso.MANUTENCAO, ativo=True,
        )
        vendida = PecasReposicao.objects.create(
            nome="Lona de salto 3,05 m", descricao_peca="Reposição",
            uso=PecasReposicao.Uso.LOJA, ativo=True,
        )

        html = self.client.get("/pecas-reposicao/", HTTP_HOST="testserver").content.decode()
        self.assertIn(vendida.nome, html)
        self.assertNotIn(escondida.nome, html)

    def test_item_de_manutencao_nao_tem_pagina_de_produto(self):
        """A página anunciaria um custo interno como se fosse oferta."""
        peca = PecasReposicao.objects.create(
            nome="Retentor interno", descricao_peca="Oficina",
            uso=PecasReposicao.Uso.MANUTENCAO, ativo=True,
        )
        resposta = self.client.get(
            f"/pecas/{peca.pk}/", HTTP_HOST="testserver",
        )
        self.assertEqual(resposta.status_code, 404)

    # ---------------------------------------- a versatilidade dentro da O.S.
    def test_a_o_s_usa_peca_da_loja_ou_item_de_manutencao_na_mesma_linha(self):
        """É essa a versatilidade: as duas origens servem à mesma cobrança."""
        peca = PecasReposicao.objects.create(
            nome="Bucha 2019", descricao_peca="Oficina",
            uso=PecasReposicao.Uso.MANUTENCAO, ativo=False,
            preco_venda=Decimal("35.00"),
        )
        resposta = self.client.post(
            "/ordens-servico/",
            {
                "action": "save", "equipamento": "Tobogã 4 m",
                "tipo": "manutencao", "status": "aberta", "prioridade": "normal",
                "itens": (
                    '[{"tipo":"peca","peca":"%d","descricao":"Bucha 2019",'
                    '"quantidade":"2","valor_unitario":"35,00"},'
                    '{"tipo":"servico","descricao":"Recolar a emenda da lona",'
                    '"quantidade":"1","valor_unitario":"120,00"}]' % peca.pk
                ),
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200)

        ordem = OrdemServico.objects.get(pk=resposta.json()["id"])
        vinculado, avulso = list(ordem.itens.all())
        self.assertEqual(vinculado.peca_id, peca.pk)
        # A linha escrita à mão não precisa de cadastro nenhum: metade do
        # que entra numa O.S. é o serviço daquele dia.
        self.assertIsNone(avulso.peca_id)
        self.assertEqual(ordem.total, Decimal("190.00"))

    def test_a_busca_da_o_s_alcanca_quem_nao_tem_acesso_a_propostas(self):
        """Apontar para a rota do orçamento daria 403 para o técnico."""
        resposta = self.client.get(
            "/ordens-servico/itens/buscar/?q=bucha",
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["status"], "sucesso")

    def test_a_busca_do_painel_oferece_o_que_da_para_cobrar(self):
        """`ativo` responde "está no site?", e não "posso cobrar isto?"."""
        PecasReposicao.objects.create(
            nome="Bucha de manutenção", descricao_peca="Oficina",
            uso=PecasReposicao.Uso.MANUTENCAO, ativo=False,
        )
        resposta = self.client.get(
            "/ordens-servico/itens/buscar/?q=bucha",
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        opcoes = resposta.json()["opcoes"]
        rotulos = [o["rotulo"] for o in opcoes]
        self.assertIn("Bucha de manutenção", rotulos)
        # O grupo é o que separa, na lista, o que a loja vende do que a
        # oficina consome.
        self.assertEqual(
            [o["grupo"] for o in opcoes if o["rotulo"] == "Bucha de manutenção"],
            ["Itens de manutenção"],
        )


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class HistoricoDeVersoesDaPropostaTests(TestCase):
    """Escondida da lista não pode ser escondida do sistema."""

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-proposta", password="x", email="pr@example.com",
        )
        self.client.force_login(self.gestor)

    def refazer(self, orcamento):
        return self.client.post(
            "/orcamentos/",
            {"action": "refazer", "id": orcamento.pk},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def criar(self):
        return Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
        )

    def test_a_versao_anterior_sai_da_lista_mas_nao_do_sistema(self):
        """Misturadas, a mesma negociação parece três orçamentos."""
        proposta = self.criar()
        nova = Orcamento.objects.get(pk=self.refazer(proposta).json()["id"])
        proposta.refresh_from_db()

        self.assertEqual(proposta.status, Orcamento.Status.SUBSTITUIDO)

        html = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        ).content.decode()
        self.assertNotIn(f'data-registro="{proposta.pk}"', html)
        self.assertIn(f'data-registro="{nova.pk}"', html)
        self.assertIn("Versões anteriores", html)

    def test_a_corrente_de_versoes_viaja_dentro_da_proposta_atual(self):
        """Quando o cliente pergunta pelo preço antigo, é aqui que se responde."""
        proposta = self.criar()
        nova = Orcamento.objects.get(pk=self.refazer(proposta).json()["id"])

        cadeia = nova.cadeia_de_versoes()
        self.assertEqual([o.pk for o in cadeia], [proposta.pk, nova.pk])

        contexto = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        ).context
        atual = [
            dado for dado in contexto["orcamentos_dados"]
            if dado["id"] == nova.pk
        ][0]
        self.assertEqual(len(atual["versoes"]), 2)
        self.assertEqual(atual["versoes"][0]["id"], proposta.pk)
        self.assertTrue(atual["versoes"][-1]["atual"])
        # A prévia é o caminho: a substituída não está na lista da
        # página, então reabri-la pelo id não acharia nada.
        self.assertEqual(
            atual["versoes"][0]["previa"], f"/orcamentos/{proposta.pk}/previa/",
        )

    def test_proposta_sem_historico_nao_carrega_corrente_nenhuma(self):
        """"1 versão" em toda proposta sugere um histórico que não existe."""
        self.criar()
        contexto = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        ).context
        self.assertEqual(contexto["orcamentos_dados"][0]["versoes"], [])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class DesenhoDaListaDeOrdensTests(TestCase):
    """O que a tela promete no tablet e no computador."""

    @staticmethod
    def folha():
        from pathlib import Path

        return (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

    def test_o_tom_da_o_s_mora_em_um_lugar_so(self):
        """Vinte `rgba(61,217,192,...)` soltos eram vinte opacidades na mão.

        Era isso que produzia contorno invisível num canto e berrante em
        outro: cada regra escolhia a sua, sem saber das outras.
        """
        folha = self.folha()
        secao = folha[folha.index(".ls-os-body{"):]
        secao = secao[:secao.index("/* ======")]

        for chave in ("--os-acento", "--os-tinta", "--os-linha", "--os-linha-forte"):
            with self.subTest(chave=chave):
                self.assertIn(chave + ":", secao)

    def test_o_tablet_da_o_s_segue_o_mesmo_desenho_do_orcamento(self):
        """Esticado de borda a borda, o card obriga a varrer 900px com os olhos."""
        folha = self.folha()
        faixa = folha[folha.index(
            "@media (min-width:601px) and (max-width:900px){\n  /* Cabeçalho"
        ):]
        faixa = faixa[:faixa.index("@media (max-width:600px)")]

        # Cabeçalho e busca centrados, e a coluna de cards com largura
        # útil em vez da largura inteira da tela.
        self.assertIn("margin-inline:auto", faixa)
        self.assertIn("max-width:860px", faixa)
        self.assertIn("text-align:center", faixa)
