"""A O.S. pergunta o que a situação dela já sabe responder.

O FORMULÁRIO PEDIA TUDO NO PRIMEIRO SEGUNDO. Abrir uma O.S. de um chamado
que acabou de entrar mostrava, lado a lado, "defeito relatado" e "serviço
executado" -- e ninguém executou nada ainda. Pedia diagnóstico técnico
antes de o técnico ver o equipamento, e exigia ao menos um item antes de
alguém saber que peça seria usada.

Campo que aparece antes da hora ensina duas coisas erradas: que ele é
opcional, porque fica em branco toda vez, e que o formulário não sabe o
que está fazendo. Pior: quem escreve algo ali para "não deixar vazio"
está inventando, e um diagnóstico escrito antes da visita vai para o
documento do cliente com cara de laudo.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import PecasReposicao

from .models import ItemOrdemServico, OrdemServico


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    SITE_URL="https://www.lazersport.com.br",
)
class EtapasDaOrdemTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="etapas", password="x", email="e@example.com",
        )
        self.client.force_login(self.gestor)

    def post(self, **dados):
        base = {
            "action": "save",
            "nome_cliente": "Buffet Alegria",
            "equipamento": "Cama elástica 3,05 m",
            "tipo": OrdemServico.Tipo.MANUTENCAO,
            "status": OrdemServico.Status.ABERTA,
            "prioridade": OrdemServico.Prioridade.NORMAL,
            "itens": "[]",
        }
        base.update(dados)
        return self.client.post(
            "/ordens-servico/", base,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # ------------------------------------------------- a ordem das etapas
    def test_cada_situacao_sabe_ate_onde_chegou(self):
        """É esta tabela que decide qual bloco do formulário aparece."""
        E = OrdemServico.Etapa
        S = OrdemServico.Status

        self.assertEqual(OrdemServico.ETAPA_DA_SITUACAO[S.ABERTA], E.ABERTURA)
        self.assertEqual(OrdemServico.ETAPA_DA_SITUACAO[S.AGENDADA], E.AGENDA)
        self.assertEqual(OrdemServico.ETAPA_DA_SITUACAO[S.EM_EXECUCAO], E.EXECUCAO)
        self.assertEqual(OrdemServico.ETAPA_DA_SITUACAO[S.CONCLUIDA], E.ENTREGA)
        # Cancelar não entrega nada, mas o motivo do cancelamento quase
        # sempre é o que se descobriu ao olhar o equipamento -- e esse
        # texto é o diagnóstico.
        self.assertEqual(OrdemServico.ETAPA_DA_SITUACAO[S.CANCELADA], E.EXECUCAO)

    def test_o_chamado_recem_aberto_nao_fala_de_execucao(self):
        """Diagnóstico e serviço executado ainda não existem."""
        E = OrdemServico.Etapa

        self.assertTrue(
            OrdemServico.etapa_alcancada(OrdemServico.Status.ABERTA, E.ABERTURA)
        )
        for adiante in (E.AGENDA, E.EXECUCAO, E.ENTREGA):
            with self.subTest(etapa=adiante):
                self.assertFalse(
                    OrdemServico.etapa_alcancada(OrdemServico.Status.ABERTA, adiante)
                )

    def test_quem_registra_atendimento_passado_ve_tudo(self):
        """Metade das O.S. da fábrica é digitada DEPOIS do atendimento.

        Escondendo por etapa, esse caminho precisava continuar aberto:
        quem escolhe "Concluída" está registrando algo que já aconteceu e
        tem todas as respostas na mão.
        """
        for etapa in OrdemServico.SEQUENCIA_DE_ETAPAS:
            with self.subTest(etapa=etapa):
                self.assertTrue(
                    OrdemServico.etapa_alcancada(
                        OrdemServico.Status.CONCLUIDA, etapa,
                    )
                )

    def test_a_tela_manda_as_etapas_para_o_formulario(self):
        """Servidor e tela leem a mesma tabela, ou discordam em silêncio."""
        contexto = self.client.get(
            "/ordens-servico/", HTTP_HOST="interno.testserver",
        ).context
        mapa = contexto["etapas_por_situacao"]

        self.assertEqual(mapa[OrdemServico.Status.ABERTA], ["abertura"])
        self.assertEqual(
            mapa[OrdemServico.Status.CONCLUIDA],
            ["abertura", "agenda", "execucao", "entrega"],
        )

    # ------------------------------------------ o que se exige, e quando
    def test_abrir_um_chamado_nao_exige_item(self):
        """Não se sabe que peça vai ser usada antes de abrir o equipamento.

        A exigência antiga obrigava quem abria a inventar uma linha de
        R$ 0,00 só para conseguir salvar -- e essa linha inventada ia
        junto para o documento do cliente.
        """
        resposta = self.post()

        self.assertEqual(resposta.status_code, 200)
        ordem = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertEqual(ordem.itens.count(), 0)
        self.assertEqual(ordem.total, Decimal("0.00"))

    def test_nao_se_conclui_sem_dizer_o_que_foi_feito(self):
        """É a contrapartida de não perguntar cedo demais.

        "Serviço executado" saiu da abertura porque lá ninguém sabe a
        resposta. Na conclusão ele É a resposta: é o que o cliente lê
        para entender pelo que está pagando, e o que a garantia cobre.
        """
        resposta = self.post(status=OrdemServico.Status.CONCLUIDA)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("serviço executado", resposta.json()["msg"].lower())
        self.assertFalse(OrdemServico.objects.exists())

        completa = self.post(
            status=OrdemServico.Status.CONCLUIDA,
            servico_executado="Troca da lona e de seis molas.",
        )
        self.assertEqual(completa.status_code, 200)

    def test_a_garantia_se_conclui_sem_cobrar_nada(self):
        """Atendimento em garantia é O.S. de total zero, e não erro."""
        resposta = self.post(
            status=OrdemServico.Status.CONCLUIDA,
            servico_executado="Troca da lona em garantia.",
            itens="[]",
        )
        self.assertEqual(resposta.status_code, 200)

        ordem = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertEqual(ordem.total, Decimal("0.00"))
        # E ela vai ao cliente assim mesmo: o documento diz o que precisa
        # dizer, e o total zerado é a informação correta.
        envio = self.client.post(
            "/ordens-servico/",
            {"action": "enviar", "id": ordem.pk, "canal": "link"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(envio.status_code, 200)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class LinhaDeItemPorTipoTests(TestCase):
    """Cada tipo de linha precisa saber uma coisa diferente."""

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="itens", password="x", email="i@example.com",
        )
        self.client.force_login(self.gestor)

    def salvar(self, itens):
        return self.client.post(
            "/ordens-servico/",
            {
                "action": "save", "nome_cliente": "Buffet Alegria",
                "equipamento": "Tobogã 4 m", "tipo": OrdemServico.Tipo.MANUTENCAO,
                "status": OrdemServico.Status.EM_EXECUCAO,
                "prioridade": OrdemServico.Prioridade.NORMAL,
                "itens": itens,
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_mao_de_obra_pede_so_o_valor(self):
        """Pedir que alguém escreva "mão de obra" na linha "mão de obra"
        é pedir para repetir o rótulo. O que falta saber é o valor."""
        resposta = self.salvar(
            '[{"tipo":"servico","descricao":"","quantidade":"1","valor_unitario":"180,00"}]'
        )
        self.assertEqual(resposta.status_code, 200)

        item = OrdemServico.objects.get(pk=resposta.json()["id"]).itens.first()
        self.assertEqual(item.descricao, "Serviço / mão de obra")
        self.assertEqual(item.valor_unitario, Decimal("180.00"))

    def test_deslocamento_e_outro_tambem(self):
        resposta = self.salvar(
            '[{"tipo":"deslocamento","descricao":"","quantidade":"1","valor_unitario":"90,00"},'
            '{"tipo":"outro","descricao":"","quantidade":"1","valor_unitario":"20,00"}]'
        )
        self.assertEqual(resposta.status_code, 200)

        itens = list(OrdemServico.objects.get(pk=resposta.json()["id"]).itens.all())
        self.assertEqual([i.descricao for i in itens], ["Deslocamento", "Outro"])

    def test_peca_sem_nome_nao_passa(self):
        """"Peça" não identifica peça nenhuma.

        Ali a descrição é o que vai no documento e o que o cliente
        confere ao receber a caixa.
        """
        resposta = self.salvar(
            '[{"tipo":"peca","descricao":"","quantidade":"1","valor_unitario":"450,00"}]'
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("qual peça", resposta.json()["msg"].lower())

    def test_a_o_s_cadastra_peca_sem_passar_pela_tela_de_propostas(self):
        """O técnico está com o equipamento aberto na frente dele.

        Mandá-lo abrir a tela de produtos e voltar significa perder a
        O.S. -- e, na prática, significa escrever "retentor" na descrição
        e seguir, o que deixa a peça fora de qualquer controle.
        """
        resposta = self.client.post(
            "/ordens-servico/",
            {
                "action": "peca_nova",
                "nome": "Retentor do motor 2019",
                "preco_venda": "80,00",
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200)

        peca = PecasReposicao.objects.get(nome="Retentor do motor 2019")
        # Mesma regra do orçamento, porque é o mesmo código: nasce fora
        # da vitrine. Ver `sistema_interno/pecas.py`.
        self.assertFalse(peca.ativo)
        self.assertEqual(peca.uso, PecasReposicao.Uso.MANUTENCAO)
        self.assertEqual(resposta.json()["peca"]["grupo"], "Itens de manutenção")

    def test_a_linha_liga_no_catalogo_quando_a_peca_existe(self):
        peca = PecasReposicao.objects.create(
            nome="Bucha 2019", descricao_peca="Oficina",
            uso=PecasReposicao.Uso.MANUTENCAO, ativo=False,
        )
        resposta = self.salvar(
            '[{"tipo":"peca","peca":"%d","descricao":"Bucha 2019",'
            '"quantidade":"2","valor_unitario":"35,00"}]' % peca.pk
        )
        self.assertEqual(resposta.status_code, 200)

        item = OrdemServico.objects.get(pk=resposta.json()["id"]).itens.first()
        self.assertEqual(item.peca_id, peca.pk)
        self.assertEqual(item.tipo, ItemOrdemServico.Tipo.PECA)
