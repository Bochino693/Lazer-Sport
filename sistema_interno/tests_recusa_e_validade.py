"""Quando o cliente não aceita, e até quando o documento vale.

Duas regras que andavam juntas e estavam pela metade.

A PRIMEIRA. "Refazer" é o caminho de quando o cliente não aceita a
proposta -- e ele diz não de dois jeitos: pela página que recebeu, ou
pelo telefone. As duas recusas valiam o mesmo para o negócio e valores
diferentes para o sistema: a do site guardava motivo, autor e instante; a
verbal guardava só o carimbo "Recusado". A versão seguinte então nascia
sem memória nenhuma -- e, pior, nascia com a MESMA validade vencida da
anterior, o que a deixava impossível de enviar no instante em que era
criada.

A SEGUNDA. O botão de enviar respeitava a validade só na tela. Escondê-lo
é conveniência; a regra tem de estar onde a gravação acontece, senão uma
aba aberta desde ontem publica o link de um documento que o cliente
abriria vendo "proposta expirada".
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ItemOrcamento, Orcamento, OrdemServico


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class RecusaERefazerTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-recusa",
            password="senha-segura",
            email="gestor-recusa@example.com",
        )
        self.client.force_login(self.gestor)

    def post(self, dados):
        return self.client.post(
            "/orcamentos/",
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def criar_proposta(self, **extras):
        dados = dict(
            nome_cliente="Buffet Alegria",
            whatsapp_cliente="(11) 99999-1111",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() + timedelta(days=5),
        )
        dados.update(extras)
        orcamento = Orcamento.objects.create(**dados)
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Castelo inflável",
            quantidade=1,
            valor_unitario=Decimal("900.00"),
        )
        return orcamento

    # ------------------------------------------------------------------
    # A recusa verbal
    # ------------------------------------------------------------------
    def test_recusa_verbal_guarda_motivo_autor_e_instante(self):
        """Antes ela era só um carimbo, e o "por quê" se perdia."""
        orcamento = self.criar_proposta()

        resposta = self.post({
            "action": "status",
            "id": orcamento.pk,
            "status": Orcamento.Status.RECUSADO,
            "motivo": "Achou caro o frete e fechou com o concorrente.",
        })

        self.assertEqual(resposta.status_code, 200)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.RECUSADO)
        self.assertIn("frete", orcamento.motivo_recusa)
        self.assertIn("gestor-recusa", orcamento.respondido_por)
        self.assertIn("informado pela equipe", orcamento.respondido_por)
        self.assertIsNotNone(orcamento.respondido_em)

    def test_recusa_sem_motivo_e_recusada_pelo_servidor(self):
        """É o único dado que só existe se alguém escrever na hora."""
        orcamento = self.criar_proposta()

        resposta = self.post({
            "action": "status",
            "id": orcamento.pk,
            "status": Orcamento.Status.RECUSADO,
            "motivo": "   ",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("motivo da recusa", resposta.json()["msg"])
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)

    def test_aprovar_continua_sem_exigir_motivo(self):
        """A exigência é da recusa; aprovar não precisa de justificativa."""
        orcamento = self.criar_proposta()

        resposta = self.post({
            "action": "status",
            "id": orcamento.pk,
            "status": Orcamento.Status.APROVADO,
        })

        self.assertEqual(resposta.status_code, 200)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)

    # ------------------------------------------------------------------
    # Refazer
    # ------------------------------------------------------------------
    def test_a_versao_nova_nasce_com_prazo_novo(self):
        """Era o defeito mais caro: o remédio saía com a doença.

        Refazer é o caminho oficial da proposta vencida, e a versão nova
        copiava a validade vencida da anterior. Nascia impossível de
        enviar, sem nada na tela explicando por quê.
        """
        vencida = self.criar_proposta(
            validade=timezone.localdate() - timedelta(days=10),
        )
        self.assertTrue(vencida.vencido)

        resposta = self.post({"action": "refazer", "id": vencida.pk})

        self.assertEqual(resposta.status_code, 200)
        nova = Orcamento.objects.get(pk=resposta.json()["id"])
        self.assertGreaterEqual(nova.validade, timezone.localdate())
        self.assertFalse(nova.vencido)
        self.assertTrue(nova.pode_enviar)

    def test_o_motivo_da_recusa_atravessa_para_a_versao_nova(self):
        orcamento = self.criar_proposta()
        self.post({
            "action": "status",
            "id": orcamento.pk,
            "status": Orcamento.Status.RECUSADO,
            "motivo": "Preço acima do orçado pelo cliente.",
        })

        resposta = self.post({"action": "refazer", "id": orcamento.pk})

        nova = Orcamento.objects.get(pk=resposta.json()["id"])
        self.assertIn("Preço acima do orçado", nova.motivo_negociacao)

    def test_o_que_a_equipe_escreve_soma_ao_que_o_cliente_disse(self):
        """Duas informações diferentes: a objeção e a resposta a ela."""
        orcamento = self.criar_proposta()
        self.post({
            "action": "status",
            "id": orcamento.pk,
            "status": Orcamento.Status.RECUSADO,
            "motivo": "Achou caro.",
        })

        resposta = self.post({
            "action": "refazer",
            "id": orcamento.pk,
            "motivo": "Desconto de 10% e frete por conta da casa.",
        })

        nova = Orcamento.objects.get(pk=resposta.json()["id"])
        self.assertIn("Achou caro.", nova.motivo_negociacao)
        self.assertIn("Desconto de 10%", nova.motivo_negociacao)

    def test_a_versao_anterior_fica_intacta_e_congelada(self):
        orcamento = self.criar_proposta()

        self.post({"action": "refazer", "id": orcamento.pk})

        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.SUBSTITUIDO)
        self.assertEqual(orcamento.itens.count(), 1)
        self.assertFalse(orcamento.pode_enviar)

    def test_a_substituida_nao_ganha_outra_versao_pelo_servidor(self):
        """A tela escondia o botão; o servidor aceitava o POST.

        `pode_refazer` já barrava a substituída, mas a view reimplementava
        um subconjunto das regras à mão e não a incluía.
        """
        orcamento = self.criar_proposta()
        self.post({"action": "refazer", "id": orcamento.pk})
        orcamento.refresh_from_db()
        # Desfaz só o vínculo para chegar ao caso que a view não barrava.
        nova = orcamento.orcamento_refeito
        nova.orcamento_anterior = None
        nova.save(update_fields=["orcamento_anterior"])

        resposta = self.post({"action": "refazer", "id": orcamento.pk})

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("substituída", resposta.json()["msg"])

    def test_rascunho_nao_refaz_e_a_recusa_explica_a_saida(self):
        rascunho = self.criar_proposta(status=Orcamento.Status.RASCUNHO)

        resposta = self.post({"action": "refazer", "id": rascunho.pk})

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("edite-a no lugar", resposta.json()["msg"])

    def test_o_segundo_clique_devolve_a_versao_que_ja_existe(self):
        """Rede lenta e dedo duplo não podem virar erro vermelho."""
        orcamento = self.criar_proposta()
        primeira = self.post({"action": "refazer", "id": orcamento.pk}).json()

        segunda = self.post({"action": "refazer", "id": orcamento.pk})

        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["id"], primeira["id"])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EnviarSoDentroDaValidadeTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-envio",
            password="senha-segura",
            email="gestor-envio@example.com",
        )
        self.client.force_login(self.gestor)

    def enviar_orcamento(self, orcamento, canal="preparar"):
        return self.client.post(
            "/orcamentos/",
            {"action": "enviar", "id": orcamento.pk, "canal": canal},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def criar_proposta(self, **extras):
        dados = dict(
            nome_cliente="Buffet Alegria",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() + timedelta(days=5),
        )
        dados.update(extras)
        orcamento = Orcamento.objects.create(**dados)
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Castelo inflável",
            quantidade=1,
            valor_unitario=Decimal("900.00"),
        )
        return orcamento

    def test_proposta_dentro_do_prazo_continua_saindo(self):
        resposta = self.enviar_orcamento(self.criar_proposta())

        self.assertEqual(resposta.status_code, 200)

    def test_proposta_vencida_nao_sai_nem_por_post_direto(self):
        """A tela escondia o botão; só isso não é regra.

        Uma aba aberta desde ontem publicaria o link de um documento que
        o cliente abre e lê "proposta expirada".
        """
        vencida = self.criar_proposta(
            validade=timezone.localdate() - timedelta(days=1),
        )

        resposta = self.enviar_orcamento(vencida)

        self.assertEqual(resposta.status_code, 400)
        recado = resposta.json()["msg"]
        self.assertIn("venceu", recado)
        self.assertIn("Nova proposta", recado)
        vencida.refresh_from_db()
        self.assertIsNone(vencida.enviado_em)

    def test_proposta_ja_respondida_nao_e_reenviada(self):
        recusada = self.criar_proposta(status=Orcamento.Status.RECUSADO)

        resposta = self.enviar_orcamento(recusada)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("já respondeu", resposta.json()["msg"])

    def test_versao_substituida_manda_enviar_a_que_vale(self):
        substituida = self.criar_proposta(status=Orcamento.Status.SUBSTITUIDO)

        resposta = self.enviar_orcamento(substituida)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("substituída", resposta.json()["msg"])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AgendaVencidaDaOrdemDeServicoTests(TestCase):
    """A validade da O.S. é o compromisso de data.

    O orçamento tem "Válido até". A O.S. tem a data marcada, e é ela que
    envelhece: uma O.S. da terça passada, ainda parada em "Agendada", é um
    papel que promete ao cliente um dia que não existe mais -- e, pior que
    a proposta vencida, ele não avisa que está velho, ele afirma.
    """

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-os-agenda",
            password="senha-segura",
            email="gestor-os-agenda@example.com",
        )
        self.client.force_login(self.gestor)

    def criar_os(self, **extras):
        dados = dict(
            nome_cliente="Buffet Alegria",
            equipamento="Castelo inflável",
            status=OrdemServico.Status.AGENDADA,
            responsavel=self.gestor,
        )
        dados.update(extras)
        return OrdemServico.objects.create(**dados)

    def enviar(self, ordem):
        return self.client.post(
            "/ordens-servico/",
            {"action": "enviar", "id": ordem.pk, "canal": "link"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_agenda_futura_continua_enviando(self):
        ordem = self.criar_os(
            agendada_para=timezone.now() + timedelta(days=2),
        )

        self.assertFalse(ordem.agenda_vencida)
        self.assertTrue(ordem.pode_enviar)

    def test_sem_agenda_marcada_nao_ha_o_que_vencer(self):
        self.assertTrue(self.criar_os(agendada_para=None).pode_enviar)

    def test_agenda_vencida_com_servico_parado_bloqueia_o_envio(self):
        ordem = self.criar_os(
            agendada_para=timezone.now() - timedelta(days=3),
        )

        self.assertTrue(ordem.agenda_vencida)
        self.assertFalse(ordem.pode_enviar)

        resposta = self.enviar(ordem)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Reagende", resposta.json()["msg"])

    def test_servico_que_andou_nao_vence_pela_agenda(self):
        """Data passada de serviço feito é histórico, e histórico não vence.

        A segunda via do documento de um serviço concluído é pedida com
        frequência, e recusá-la seria trocar um defeito por outro.
        """
        for situacao in (
            OrdemServico.Status.EM_EXECUCAO,
            OrdemServico.Status.AGUARDANDO_PECA,
            OrdemServico.Status.CONCLUIDA,
        ):
            with self.subTest(situacao=situacao):
                ordem = self.criar_os(
                    status=situacao,
                    agendada_para=timezone.now() - timedelta(days=30),
                )
                self.assertFalse(ordem.agenda_vencida)
                self.assertTrue(ordem.pode_enviar)

    def test_refazer_nao_carrega_a_agenda_vencida_para_a_versao_nova(self):
        """Senão a versão nova nasce sem poder ser enviada."""
        ordem = self.criar_os(
            status=OrdemServico.Status.AGENDADA,
            agendada_para=timezone.now() - timedelta(days=3),
        )

        resposta = self.client.post(
            "/ordens-servico/",
            {
                "action": "refazer",
                "id": ordem.pk,
                "motivo_refacao": "Cliente pediu outra data.",
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        nova = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertIsNone(nova.agendada_para)
        self.assertTrue(nova.pode_enviar)

    def test_agenda_futura_acompanha_a_versao_nova(self):
        """Ali a data ainda é o combinado, e redigitá-la seria trabalho."""
        marcada = (timezone.now() + timedelta(days=5)).replace(microsecond=0)
        ordem = self.criar_os(
            status=OrdemServico.Status.AGENDADA, agendada_para=marcada,
        )

        resposta = self.client.post(
            "/ordens-servico/",
            {
                "action": "refazer",
                "id": ordem.pk,
                "motivo_refacao": "Trocou a peça combinada.",
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        nova = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertEqual(nova.agendada_para, marcada)
