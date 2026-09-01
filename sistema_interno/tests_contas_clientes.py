"""Contas de clientes: modais e ações administrativas sensíveis."""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import ClientePerfil, Cupom

from .models import CampanhaDivulgacao, EntregaCampanha


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ContasClientesTests(TestCase):
    rota = "/site/contas-clientes/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-contas",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.cliente_conta = User.objects.create_user(
            username="cliente-modal",
            password="senha-cliente",
            email="cliente@example.com",
        )
        self.perfil = ClientePerfil.objects.get(user=self.cliente_conta)
        self.perfil.nome_completo = "Cliente dos Modais"
        self.perfil.telefone = "(11)91234-5678"
        self.perfil.save(update_fields=("nome_completo", "telefone"))
        self.client.force_login(self.gestor)

    def abrir(self):
        return self.client.get(self.rota, HTTP_HOST="interno.testserver")

    def enviar(self, dados):
        return self.client.post(
            self.rota,
            dados,
            HTTP_HOST="interno.testserver",
        )

    def test_tela_entrega_os_quatro_modais_no_ciclo_da_navegacao_suave(self):
        resposta = self.abrir()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="userModal"')
        self.assertContains(resposta, 'id="statusModal"')
        self.assertContains(resposta, 'id="deleteModal"')
        self.assertContains(resposta, 'id="offerModal"')
        self.assertContains(resposta, 'name="confirmacao_exclusao"')
        self.assertContains(resposta, 'id="accountOffersData"')
        self.assertContains(resposta, "LSTela.pronto(function ()")
        self.assertContains(resposta, "data-open-status")
        self.assertContains(resposta, "data-open-offer")

    def test_inativacao_exige_confirmacao_e_e_idempotente(self):
        sem_confirmacao = self.enviar({
            "acao": "alternar",
            "usuario_id": self.cliente_conta.pk,
            "novo_status": "0",
        })
        self.assertEqual(sem_confirmacao.status_code, 302)
        self.cliente_conta.refresh_from_db()
        self.assertTrue(self.cliente_conta.is_active)

        dados = {
            "acao": "alternar",
            "usuario_id": self.cliente_conta.pk,
            "novo_status": "0",
            "confirmacao": "INATIVAR",
        }
        self.enviar(dados)
        self.cliente_conta.refresh_from_db()
        self.assertFalse(self.cliente_conta.is_active)

        # Clique repetido ou repetição da rede preserva o estado desejado.
        self.enviar(dados)
        self.cliente_conta.refresh_from_db()
        self.assertFalse(self.cliente_conta.is_active)

        self.enviar({
            "acao": "alternar",
            "usuario_id": self.cliente_conta.pk,
            "novo_status": "1",
            "confirmacao": "ATIVAR",
        })
        self.cliente_conta.refresh_from_db()
        self.assertTrue(self.cliente_conta.is_active)

    def test_exclusao_so_ocorre_depois_de_digitar_excluir(self):
        self.enviar({
            "acao": "excluir",
            "usuario_id": self.cliente_conta.pk,
            "confirmacao_exclusao": "apagar",
        })
        self.assertTrue(User.objects.filter(pk=self.cliente_conta.pk).exists())

        self.enviar({
            "acao": "excluir",
            "usuario_id": self.cliente_conta.pk,
            "confirmacao_exclusao": "EXCLUIR",
        })
        self.assertFalse(User.objects.filter(pk=self.cliente_conta.pk).exists())

    def test_cupom_exclusivo_e_preparado_para_a_conta_nos_dois_canais(self):
        cupom = Cupom.objects.create(
            codigo="VIP20",
            desconto_percentual="20.00",
            quantidade_uso=1,
            todos_usuarios=False,
        )

        resposta = self.client.post(
            self.rota,
            {
                "acao": "oferta",
                "usuario_id": self.cliente_conta.pk,
                "tipo": "cupom",
                "objeto": cupom.pk,
                "email": "1",
                "whatsapp": "1",
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 201, resposta.content)
        self.assertEqual(resposta.json()["status"], "sucesso")
        campanha = CampanhaDivulgacao.objects.get()
        self.assertEqual(campanha.cupom, cupom)
        self.assertTrue(campanha.canal_email)
        self.assertTrue(campanha.canal_whatsapp)
        self.assertEqual(campanha.total_destinatarios, 2)
        self.assertTrue(cupom.cliente.filter(pk=self.perfil.pk).exists())
        self.assertEqual(
            set(campanha.entregas.values_list("canal", "status")),
            {
                (EntregaCampanha.Canal.EMAIL, EntregaCampanha.Status.PENDENTE),
                (
                    EntregaCampanha.Canal.WHATSAPP,
                    EntregaCampanha.Status.AGUARDANDO_ACAO,
                ),
            },
        )

    def test_conta_inativa_nao_recebe_oferta(self):
        self.cliente_conta.is_active = False
        self.cliente_conta.save(update_fields=("is_active",))
        cupom = Cupom.objects.create(
            codigo="BLOQUEADO",
            desconto_percentual="10.00",
            todos_usuarios=True,
        )

        resposta = self.client.post(
            self.rota,
            {
                "acao": "oferta",
                "usuario_id": self.cliente_conta.pk,
                "tipo": "cupom",
                "objeto": cupom.pk,
                "email": "1",
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["status"], "erro")
        self.assertFalse(CampanhaDivulgacao.objects.exists())

