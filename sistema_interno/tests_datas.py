"""Nenhum documento sai da fábrica com data para trás.

DUAS COISAS DIFERENTES, PELO MESMO MOTIVO.

O orçamento tem validade. Sem prazo nenhum, ele some da fila de cobrança
da central de avisos e fica parado esperando uma resposta que ninguém vai
cobrar; com prazo de ontem, o cliente abre a página e lê "proposta
expirada" num documento que acabou de receber. Por isso proposta nova
nasce com cinco dias, e data anterior a hoje é recusada.

A O.S. tem agendamento, e aqui o cuidado é o inverso do óbvio: metade das
O.S. é digitada DEPOIS do atendimento -- o técnico foi ontem, alguém
registra hoje. Recusar data passada nesse caso impediria de fechar a O.S.
do trabalho que já foi feito. O que não pode existir é O.S. que ainda VAI
acontecer marcada para um dia que já passou: ninguém vai, ela não aparece
na agenda de amanhã nem em atraso em lugar nenhum, e o cliente espera.
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ItemOrdemServico, Orcamento, OrdemServico


ITEM = json.dumps([{
    "descricao": "Cama elástica",
    "quantidade": "1",
    "valor_unitario": "500,00",
}])

ITEM_OS = json.dumps([{
    "tipo": ItemOrdemServico.Tipo.SERVICO,
    "descricao": "Troca de lona",
    "quantidade": "1",
    "valor_unitario": "300,00",
}])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ValidadeDoOrcamentoTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-datas", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def salvar(self, **extras):
        dados = {
            "action": "save",
            "nome_cliente": "Buffet Alegria",
            "itens": ITEM,
        }
        dados.update(extras)
        return self.client.post(
            "/orcamentos/", dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_proposta_nova_sem_prazo_escolhido_nasce_com_cinco_dias(self):
        resposta = self.salvar()

        self.assertEqual(resposta.status_code, 200)
        orcamento = Orcamento.objects.get(pk=resposta.json()["id"])
        self.assertEqual(
            orcamento.validade,
            timezone.localdate() + timedelta(days=5),
        )
        self.assertEqual(Orcamento.DIAS_DE_VALIDADE_PADRAO, 5)

    def test_o_prazo_escrito_pela_pessoa_manda_no_padrao(self):
        escolhida = timezone.localdate() + timedelta(days=45)

        resposta = self.salvar(validade=escolhida.isoformat())

        orcamento = Orcamento.objects.get(pk=resposta.json()["id"])
        self.assertEqual(orcamento.validade, escolhida)

    def test_validade_de_ontem_e_recusada(self):
        ontem = timezone.localdate() - timedelta(days=1)

        resposta = self.salvar(validade=ontem.isoformat())

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("anterior a hoje", resposta.json()["msg"])
        self.assertFalse(Orcamento.objects.exists())

    def test_validade_de_hoje_passa(self):
        """Vence hoje ainda é hoje: quem faz proposta para o mesmo dia usa."""
        resposta = self.salvar(validade=timezone.localdate().isoformat())

        self.assertEqual(resposta.status_code, 200)
        orcamento = Orcamento.objects.get(pk=resposta.json()["id"])
        self.assertEqual(orcamento.validade, timezone.localdate())

    def test_sem_prazo_continua_sendo_uma_escolha_possivel_na_edicao(self):
        """O botão "Sem prazo" existe e tem de continuar funcionando.

        O padrão de cinco dias é para quem não pensou no assunto; para
        quem pensou e decidiu que não há prazo, o campo vazio vale.
        """
        criado = Orcamento.objects.get(pk=self.salvar().json()["id"])

        self.salvar(id=criado.pk, validade="")

        criado.refresh_from_db()
        self.assertIsNone(criado.validade)

    def test_a_tela_oferece_o_atalho_do_prazo_padrao(self):
        resposta = self.client.get(
            "/orcamentos/", HTTP_HOST="interno.testserver",
        )

        self.assertContains(resposta, 'data-validade-dias="5"')
        self.assertContains(resposta, "data-nao-passado")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AgendamentoDaOrdemDeServicoTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-os-datas", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def salvar(self, **extras):
        dados = {
            "action": "save",
            "nome_cliente": "Cliente balcão",
            "equipamento": "Tobogã inflável",
            "tipo": OrdemServico.Tipo.MANUTENCAO,
            "status": OrdemServico.Status.AGENDADA,
            "prioridade": OrdemServico.Prioridade.NORMAL,
            "itens": ITEM_OS,
        }
        dados.update(extras)
        return self.client.post(
            "/ordens-servico/", dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @staticmethod
    def momento(dias):
        return timezone.localtime(
            timezone.now() + timedelta(days=dias)
        ).strftime("%Y-%m-%dT%H:%M")

    def test_nao_da_para_agendar_um_servico_para_ontem(self):
        resposta = self.salvar(agendada_para=self.momento(-1))

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("passado", resposta.json()["msg"])
        self.assertFalse(OrdemServico.objects.exists())

    def test_agendar_para_depois_de_agora_passa(self):
        resposta = self.salvar(agendada_para=self.momento(3))

        self.assertEqual(resposta.status_code, 200)
        self.assertIsNotNone(
            OrdemServico.objects.get(pk=resposta.json()["id"]).agendada_para
        )

    def test_servico_que_ja_foi_feito_pode_ser_registrado_com_data_de_ontem(self):
        """É metade das O.S. da fábrica: o técnico foi ontem, digita-se hoje.

        Recusar aqui impediria de fechar a O.S. do trabalho já executado
        -- e a regra passaria de proteção a estorvo.
        """
        resposta = self.salvar(
            status=OrdemServico.Status.CONCLUIDA,
            agendada_para=self.momento(-1),
            # Concluir exige dizer o que foi feito -- e uma O.S. que o
            # técnico executou ontem obviamente tem essa resposta.
            servico_executado="Troca da lona e reaperto das molas.",
        )

        self.assertEqual(resposta.status_code, 200)
        ordem = OrdemServico.objects.get(pk=resposta.json()["id"])
        self.assertLess(ordem.agendada_para, timezone.now())

    def test_os_antiga_continua_salvando_com_a_agenda_que_sempre_teve(self):
        """Editar outro campo não pode exigir remarcar o que já passou."""
        ordem = OrdemServico.objects.create(
            nome_cliente="Cliente antigo",
            equipamento="Piscina de bolinhas",
            status=OrdemServico.Status.AGENDADA,
            agendada_para=timezone.now() - timedelta(days=10),
        )
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
            descricao="Reparo", quantidade=1, valor_unitario=Decimal("50.00"),
        )
        agenda_original = ordem.agendada_para

        resposta = self.salvar(
            id=ordem.pk,
            nome_cliente="Cliente antigo",
            equipamento="Piscina de bolinhas",
            agendada_para=timezone.localtime(agenda_original).strftime("%Y-%m-%dT%H:%M"),
            observacoes="Cliente pediu retorno",
        )

        self.assertEqual(resposta.status_code, 200)
        ordem.refresh_from_db()
        self.assertEqual(ordem.observacoes, "Cliente pediu retorno")

    def test_garantia_nao_pode_terminar_antes_de_comecar(self):
        ontem = (timezone.localdate() - timedelta(days=1)).isoformat()

        resposta = self.salvar(garantia_ate=ontem)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("garantia", resposta.json()["msg"].lower())
