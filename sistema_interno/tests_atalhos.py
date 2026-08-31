"""A fila de urgências resolve, e não só aponta.

O AVISO SOZINHO NÃO RESOLVE NADA. "Esta proposta vence em 2 dias" era só
um aviso: para agir, a pessoa abria a tela de Orçamentos, achava a linha,
abria a janela de envio, conferia o telefone e mandava. Cinco passos para
a única coisa que a urgência pedia. Na prática o item era lido, adiado, e
a proposta vencia -- que é exatamente o que o aviso existia para evitar.

O atalho é a mesma ação que o observador faz sozinho, com a mesma função
por trás: duas portas para uma ação, e não duas ações parecidas. O
registro, o texto e a regra de "uma vez por proposta" valem tenha vindo
do relógio ou do dedo de alguém.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import EnvioOrcamento, ItemOrcamento, Orcamento
from .permissoes import atribuir_funcoes


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="https://www.lazersport.com.br",
)
class AtalhoDeLembrarClienteTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-atalho", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def proposta(self, *, dias=2, email="cliente@example.com",
                 status=Orcamento.Status.AGUARDANDO_RESPOSTA):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            email_cliente=email,
            status=status,
            validade=timezone.localdate() + timedelta(days=dias),
            responsavel=self.gestor,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=Decimal("480.00"),
        )
        return orcamento

    def lembrar(self, orcamento):
        return self.client.post(
            f"/orcamentos/{orcamento.pk}/lembrar/",
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_um_clique_manda_o_lembrete(self):
        orcamento = self.proposta()

        resposta = self.lembrar(orcamento)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["cliente@example.com"])
        self.assertIn("cliente@example.com", resposta.json()["msg"])

    def test_o_atalho_e_a_automacao_deixam_o_mesmo_registro(self):
        """Duas portas para a MESMA ação, e não duas ações parecidas."""
        orcamento = self.proposta()

        self.lembrar(orcamento)

        envio = orcamento.envios.get()
        self.assertEqual(envio.canal, EnvioOrcamento.Canal.EMAIL)
        self.assertIn("lembrete", envio.detalhe)

        # E a regra de "uma vez por proposta" continua valendo: o
        # observador não vai mandar de novo o que a pessoa já mandou.
        from .notificacoes_cliente import lembrar_propostas_a_vencer
        self.assertEqual(lembrar_propostas_a_vencer(), 0)

    def test_proposta_que_nao_espera_resposta_recusa_com_explicacao(self):
        aprovada = self.proposta(status=Orcamento.Status.APROVADO)

        resposta = self.lembrar(aprovada)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("não há o que lembrar", resposta.json()["msg"])
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="",
    )
    def test_hospedagem_sem_email_diz_isso_em_vez_de_pedir_para_tentar_de_novo(self):
        """Sem esta conferência a recusa saía como 5xx.

        E a camada de resiliência transforma 5xx em "a conexão oscilou,
        tente de novo" -- a pessoa tentaria a vida inteira, porque não há
        o que oscilar: falta configuração.
        """
        orcamento = self.proposta()

        resposta = self.lembrar(orcamento)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("não está ligado nesta hospedagem", resposta.json()["msg"])
        self.assertIn("WhatsApp", resposta.json()["msg"])

    def test_cliente_sem_email_recusa_dizendo_o_caminho(self):
        sem_email = self.proposta(email="")

        resposta = self.lembrar(sem_email)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("WhatsApp", resposta.json()["msg"])

    def test_o_ambulante_nao_lembra_a_proposta_de_um_colega(self):
        """A carteira individual vale no atalho como vale na lista."""
        alheia = self.proposta()

        ambulante = User.objects.create_user(
            username="ambulante-atalho", password="x", email="a@example.com",
        )
        atribuir_funcoes(ambulante, ["ambulante"])
        self.client.force_login(ambulante)

        # 409, e não 404: para um pedido JSON o painel converte "não
        # existe" em "este registro saiu da sua vista, atualize a lista"
        # (ver `resiliencia.pagina_interna_nao_encontrada`). O que importa
        # aqui é que a proposta do colega não foi tocada.
        self.assertEqual(self.lembrar(alheia).status_code, 409)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(alheia.envios.exists())

    # ------------------------------------------------------- na tela
    def test_a_fila_da_home_traz_o_botao_quando_ele_tem_como_funcionar(self):
        self.proposta(dias=1)

        html = self.client.get("/", HTTP_HOST="interno.testserver").content.decode()

        self.assertIn('data-atalho="lembrar"', html)

    def test_sem_email_no_cadastro_o_botao_nao_aparece(self):
        """Botão que falha ao ser tocado ensina a não tocar em botão nenhum."""
        self.proposta(dias=1, email="")

        html = self.client.get("/", HTTP_HOST="interno.testserver").content.decode()

        self.assertNotIn('data-atalho="lembrar"', html)

    def test_proposta_ja_vencida_nao_oferece_lembrete(self):
        """Lembrar de um prazo que passou não ajuda ninguém.

        Ali o caminho é refazer a proposta ou falar com o cliente -- e o
        item continua levando para a tela onde isso se faz.
        """
        self.proposta(dias=-2)

        html = self.client.get("/", HTTP_HOST="interno.testserver").content.decode()

        self.assertNotIn('data-atalho="lembrar"', html)
        self.assertIn("Vencido há", html)
