"""O cliente também é avisado -- com o texto dele, no canal dele.

O BURACO QUE ISTO FECHA. A central de avisos já cobrava a EQUIPE quando
uma proposta estava para vencer. O cliente não recebia nada. Ou seja: o
sistema sabia que a data ia passar, avisava quem não podia decidir, e
ficava calado com quem podia. A proposta expirava, e o motivo mais comum
não era "o cliente não quis" -- era "o cliente esqueceu".

Os testes abaixo protegem as quatro condições do lembrete e, principalmente,
as duas coisas que fazem dele uma ajuda em vez de um incômodo: sai UMA vez
por proposta, e sai ANTES de a proposta expirar.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .automacoes import executar_automacoes_operacionais
from .models import EnvioOrcamento, ItemOrcamento, Orcamento
from .notificacoes_cliente import (
    DIAS_PARA_LEMBRAR,
    lembrar_propostas_a_vencer,
    propostas_a_lembrar,
)


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="https://www.lazersport.com.br",
)
class LembreteDeValidadeTests(TestCase):

    def setUp(self):
        self.atendente = User.objects.create_user(
            username="atendente", password="x", email="a@example.com",
        )

    def proposta(self, *, dias, status=Orcamento.Status.AGUARDANDO_RESPOSTA, email="cliente@example.com"):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            email_cliente=email,
            status=status,
            validade=timezone.localdate() + timedelta(days=dias),
            responsavel=self.atendente,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=Decimal("480.00"),
        )
        return orcamento

    # ------------------------------------------------- quem entra na fila
    def test_lembra_a_proposta_que_esta_para_vencer(self):
        perto = self.proposta(dias=DIAS_PARA_LEMBRAR)

        self.assertIn(perto, list(propostas_a_lembrar()))

    def test_nao_lembra_a_que_ainda_tem_prazo_de_sobra(self):
        longe = self.proposta(dias=DIAS_PARA_LEMBRAR + 10)

        self.assertNotIn(longe, list(propostas_a_lembrar()))

    def test_nao_lembra_rascunho(self):
        """Rascunho não foi para ninguém: não há o que lembrar."""
        rascunho = self.proposta(dias=1, status=Orcamento.Status.RASCUNHO)

        self.assertNotIn(rascunho, list(propostas_a_lembrar()))

    def test_nao_lembra_proposta_ja_respondida(self):
        respondida = self.proposta(dias=1, status=Orcamento.Status.APROVADO)

        self.assertNotIn(respondida, list(propostas_a_lembrar()))

    def test_nao_lembra_proposta_ja_vencida(self):
        """Perdeu o assunto: quem cuida dela é a automação que expira."""
        vencida = self.proposta(dias=-1)

        self.assertNotIn(vencida, list(propostas_a_lembrar()))

    # ------------------------------------------------------- o envio
    def test_o_lembrete_chega_com_o_link_e_o_prazo(self):
        orcamento = self.proposta(dias=2)

        self.assertEqual(lembrar_propostas_a_vencer(), 1)
        self.assertEqual(len(mail.outbox), 1)

        enviado = mail.outbox[0]
        self.assertEqual(enviado.to, ["cliente@example.com"])
        self.assertIn(str(orcamento.pk), enviado.subject)
        self.assertIn("em 2 dias", enviado.subject)
        self.assertIn(orcamento.token, enviado.body)
        # O link é o do site do cliente, nunca o do subdomínio interno.
        self.assertNotIn("interno.", enviado.body)

    def test_sai_uma_vez_so_por_proposta(self):
        """Perseguir cliente por e-mail é o caminho curto para o spam."""
        self.proposta(dias=1)

        self.assertEqual(lembrar_propostas_a_vencer(), 1)
        self.assertEqual(lembrar_propostas_a_vencer(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_o_lembrete_entra_no_historico_de_envios_da_proposta(self):
        """O comercial abre a tela e vê que o lembrete saiu -- e quando."""
        orcamento = self.proposta(dias=1)

        lembrar_propostas_a_vencer()

        envio = orcamento.envios.get()
        self.assertEqual(envio.canal, EnvioOrcamento.Canal.EMAIL)
        self.assertTrue(envio.sucesso)
        self.assertIn("lembrete", envio.detalhe)

    def test_proposta_sem_email_nao_gera_tentativa(self):
        self.proposta(dias=1, email="")

        self.assertEqual(lembrar_propostas_a_vencer(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EnvioOrcamento.objects.exists())

    # ------------------------------------------------ a ordem do ciclo
    def test_lembra_antes_de_expirar_e_nao_depois(self):
        """Expirar primeiro mataria a proposta e avisaria sobre um 404.

        A proposta que vence HOJE ainda dá tempo de resposta; a que venceu
        ontem já não. As duas passam pelo mesmo ciclo, e cada uma tem de
        sair dele de um jeito.
        """
        vence_hoje = self.proposta(dias=0)
        venceu_ontem = self.proposta(dias=-1)

        resultado = executar_automacoes_operacionais()

        self.assertEqual(resultado["lembretes_ao_cliente"], 1)
        self.assertEqual(resultado["orcamentos_expirados"], 1)

        vence_hoje.refresh_from_db()
        venceu_ontem.refresh_from_db()
        self.assertEqual(vence_hoje.status, Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertEqual(venceu_ontem.status, Orcamento.Status.EXPIRADO)
        self.assertEqual(mail.outbox[0].to, ["cliente@example.com"])
        self.assertIn("hoje", mail.outbox[0].subject)


class OsDoisPublicosSaoAtendidosPorArquivosDiferentesTests(TestCase):
    """A separação é de objetivo, não de arrumação.

    Se um dia alguém juntar os dois, o texto de um vai contaminar o do
    outro: ou o cliente recebe uma cobrança, ou a equipe recebe um recado
    ameno sobre algo que precisa ser feito agora.
    """

    def test_o_modulo_da_equipe_manda_push_e_o_do_cliente_nao(self):
        import inspect

        from . import notificacoes, notificacoes_cliente

        self.assertIn("push", inspect.getsource(notificacoes))
        self.assertNotIn(
            "import push", inspect.getsource(notificacoes_cliente),
            "O cliente não instala o painel nem se inscreve em push: "
            "escrever para esse canal seria escrever para o vazio.",
        )

    def test_o_modulo_do_cliente_nao_conhece_as_funcoes_da_equipe(self):
        from . import notificacoes_cliente

        self.assertFalse(hasattr(notificacoes_cliente, "avisar_resposta_do_cliente"))
