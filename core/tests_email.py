"""Como o e-mail sai da Lazer & Sport.

O que estes testes protegem:

  * o cliente vê o nome da empresa na caixa de entrada, não um endereço
    solto de Gmail — é o que separa proposta de spam;
  * "responder" volta para quem atende, e não para a conta técnica do
    SMTP, mesmo com o provedor exigindo enviar pelo endereço autenticado;
  * sem credencial de SMTP, a tela avisa antes em vez de fingir que
    enviou.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .email_utils import remetente, responder_para, smtp_configurado


class RemetenteTests(TestCase):

    @override_settings(DEFAULT_FROM_EMAIL="Lazer & Sport <contato@lazer.com>")
    def test_remetente_leva_o_nome_da_empresa(self):
        self.assertEqual(remetente(), "Lazer & Sport <contato@lazer.com>")

    @override_settings(EMAIL_RESPOSTA="vendas@lazersport.com.br", ORCAMENTO_EMAIL="")
    def test_resposta_padrao_vem_do_ambiente(self):
        self.assertEqual(responder_para(), ["vendas@lazersport.com.br"])

    @override_settings(EMAIL_RESPOSTA="vendas@lazersport.com.br", ORCAMENTO_EMAIL="")
    def test_quem_envia_recebe_a_resposta_na_frente(self):
        atendente = User.objects.create_user(
            username="marina",
            email="marina@lazersport.com.br",
            password="123456789a",
        )

        self.assertEqual(
            responder_para(atendente),
            ["marina@lazersport.com.br", "vendas@lazersport.com.br"],
        )

    @override_settings(EMAIL_RESPOSTA="", ORCAMENTO_EMAIL="")
    def test_sem_configuracao_nao_inventa_endereco(self):
        self.assertEqual(responder_para(), [])

    @override_settings(EMAIL_RESPOSTA="", ORCAMENTO_EMAIL="orcamento@lazersport.com.br")
    def test_o_comercial_e_a_ultima_rede_de_seguranca(self):
        """Sem EMAIL_RESPOSTA, a resposta ainda cai no comercial.

        `ORCAMENTO_EMAIL` existe justamente para a proposta nunca sair com
        um Reply-To vazio: sem ele, "responder" volta para a conta técnica
        do SMTP, que ninguém lê.
        """
        self.assertEqual(responder_para(), ["orcamento@lazersport.com.br"])

    @override_settings(
        EMAIL_RESPOSTA="vendas@lazersport.com.br",
        ORCAMENTO_EMAIL="vendas@lazersport.com.br",
    )
    def test_o_mesmo_endereco_nao_entra_duas_vezes(self):
        self.assertEqual(responder_para(), ["vendas@lazersport.com.br"])

    @override_settings(EMAIL_RESPOSTA="", ORCAMENTO_EMAIL="")
    def test_usuario_sem_email_nao_vira_reply_to(self):
        sem_email = User.objects.create_user(
            username="sem-email",
            password="123456789a",
        )

        self.assertEqual(responder_para(sem_email), [])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
    )
    def test_smtp_sem_credencial_e_reconhecido(self):
        self.assertFalse(smtp_configurado())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST_USER="contato@lazersport.com.br",
        EMAIL_HOST_PASSWORD="senha-de-aplicativo",
    )
    def test_smtp_completo_libera_o_envio(self):
        self.assertTrue(smtp_configurado())
