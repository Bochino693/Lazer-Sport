from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth.models import User
from django.core.management import call_command
from unittest.mock import patch

from core.models import Pedido

from .models import Cliente
from .avisos import Aviso
from .notificacoes import avisar_novo_pedido_id
from .validacoes import documento_valido


class DocumentoBrasileiroTests(SimpleTestCase):
    def test_aceita_cpf_cnpj_classico_e_cnpj_alfanumerico(self):
        self.assertTrue(documento_valido("529.982.247-25"))
        self.assertTrue(documento_valido("54.486.908/0001-86"))
        self.assertTrue(documento_valido("00.000.000/E08G-12"))

    def test_recusa_sequencia_e_digito_incorreto(self):
        self.assertFalse(documento_valido("111.111.111-11"))
        self.assertFalse(documento_valido("54.486.908/0001-85"))


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class CadastroValidadoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser(
            username="gestor-validacao", password="senha", email="gestor@example.com"
        )
        self.client.force_login(self.usuario)

    def _salvar(self, **dados):
        payload = {
            "action": "save",
            "nome_cliente": "Cliente Validado",
            "email": "cliente@example.com",
        }
        payload.update(dados)
        return self.client.post(
            "/clientes/",
            payload,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_documento_invalido_nao_e_salvo(self):
        resposta = self._salvar(documento="111.111.111-11")
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Cliente.objects.filter(nome_cliente="Cliente Validado").exists())

    def test_documento_normalizado_nao_duplica(self):
        Cliente.objects.create(
            nome_cliente="Primeiro cadastro",
            email="um@example.com",
            documento="54.486.908/0001-86",
        )
        resposta = self._salvar(documento="54486908000186")
        self.assertEqual(resposta.status_code, 400)

    def test_numero_nao_confirmado_exige_decisao_explicita(self):
        resposta = self._salvar(
            telefone="(11) 99999-1111",
            canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
        )
        self.assertEqual(resposta.status_code, 400)
        resposta = self._salvar(
            telefone="(11) 99999-1111",
            canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
            confirmar_telefone_sem_whatsapp="1",
        )
        self.assertEqual(resposta.status_code, 200)
        cliente = Cliente.objects.get(nome_cliente="Cliente Validado")
        self.assertEqual(cliente.canal_telefone, Cliente.CanalTelefone.NAO_CONFIRMADO)


class NovoPedidoNotificacaoTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_superuser(
            username="super-pedidos", password="senha", email=""
        )

    @patch("sistema_interno.notificacoes._entregar")
    def test_push_nao_expoe_pk_nem_cliente(self, entregar):
        pedido = Pedido.objects.create()
        avisar_novo_pedido_id(pedido.pk, bloqueante=True)
        dados = entregar.call_args.args[1]
        self.assertNotIn(str(pedido.pk), dados["titulo"] + dados["corpo"] + dados["url"])
        self.assertEqual(dados["url"], "/pedidos/inner/")
        self.assertTrue(dados["urgente"])

    def test_criacao_dispara_aviso_somente_depois_do_commit(self):
        with patch(
            "sistema_interno.notificacoes.avisar_novo_pedido_id"
        ) as avisar:
            with self.captureOnCommitCallbacks(execute=True):
                pedido = Pedido.objects.create()
            avisar.assert_called_once_with(pedido.pk)


class ObservadorUrgenciasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser(
            username="super-observador", password="senha", email="super@example.com"
        )

    @patch(
        "sistema_interno.management.commands.observar_pendencias.enviar_pendencias_urgentes",
        return_value=True,
    )
    @patch("sistema_interno.management.commands.observar_pendencias.coletar")
    def test_estado_igual_nao_repete_email(self, coletar, enviar):
        coletar.return_value = [Aviso(
            chave="estoque",
            titulo="Material para repor",
            detalhe="No mínimo.",
            quantidade=2,
            url="/stock/",
            nivel="critico",
            icone="bi-box",
        )]
        call_command("observar_pendencias", "--uma-vez", verbosity=0)
        call_command("observar_pendencias", "--uma-vez", verbosity=0)
        enviar.assert_called_once()
