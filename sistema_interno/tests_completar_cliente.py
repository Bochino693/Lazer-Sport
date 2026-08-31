"""Completar o que falta sem abrir o cadastro inteiro.

A lista já dizia "Falta contato, endereço". O único caminho para resolver
era "Editar", que abre o formulário completo e espalha os dois campos
vazios no meio de vinte preenchidos -- quem estava com o cliente no
telefone procurava onde digitar.

O RISCO DESTA JANELA É APAGAR O QUE JÁ EXISTIA. `salvar_cliente` lê o
formulário inteiro, e é o certo para a edição: campo ausente ali significa
"o usuário apagou". Numa janela que mostra três campos, a mesma leitura
apagaria o telefone de quem só veio informar o CPF. É contra isso que a
maior parte dos testes daqui aponta.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .completude_clientes import pendencias_do_cliente
from .models import Cliente, EnderecoCliente


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class CompletarCadastroTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-completar", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def completar(self, cliente, **campos):
        dados = {"action": "completar", "id": cliente.pk}
        dados.update(campos)
        return self.client.post(
            "/clientes/", dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_preenche_so_o_que_veio_e_nao_apaga_o_resto(self):
        """O defeito que esta janela poderia ter criado."""
        cliente = Cliente.objects.create(
            nome_cliente="Buffet Alegria",
            telefone="(11) 97777-6655",
            email="contato@alegria.com",
        )

        resposta = self.completar(cliente, documento="111.444.777-35")

        self.assertEqual(resposta.status_code, 200)
        cliente.refresh_from_db()
        self.assertEqual(cliente.documento, "111.444.777-35")
        # O que a janela não mostrou continua onde estava.
        self.assertEqual(cliente.telefone, "(11) 97777-6655")
        self.assertEqual(cliente.email, "contato@alegria.com")
        self.assertEqual(cliente.nome_cliente, "Buffet Alegria")

    def test_o_endereco_que_faltava_e_criado(self):
        cliente = Cliente.objects.create(
            nome_cliente="Joana Ribeiro", telefone="(11) 97777-6655",
        )
        self.assertIn("endereço", pendencias_do_cliente(cliente))

        self.completar(
            cliente, endereco="Rua das Flores", numero="120",
            bairro="Centro", cidade="São Paulo", estado="SP",
        )

        endereco = EnderecoCliente.objects.get(cliente=cliente)
        self.assertEqual(endereco.endereco, "Rua das Flores")
        self.assertEqual(endereco.cidade, "São Paulo")

    def test_documento_invalido_e_recusado_pela_porta_nova_tambem(self):
        """Um CPF errado não fica menos errado por entrar por outro lugar."""
        cliente = Cliente.objects.create(
            nome_cliente="Carlos Dias", telefone="(11) 97777-6655",
        )

        resposta = self.completar(cliente, documento="111.111.111-11")

        self.assertEqual(resposta.status_code, 400)
        cliente.refresh_from_db()
        self.assertEqual(cliente.documento, "")

    def test_nao_deixa_o_cadastro_sem_nenhum_contato(self):
        cliente = Cliente.objects.create(nome_cliente="Sem Contato")

        resposta = self.completar(cliente, documento="111.444.777-35")

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("contato", resposta.json()["msg"])

    def test_desmarcar_a_caixa_confirma_o_whatsapp(self):
        """A pendência tinha de poder ser resolvida.

        Caixa desmarcada não viaja no POST: sem o marcador de "a janela
        perguntou", "sem resposta" e "não perguntamos" chegariam iguais, e
        "WhatsApp não confirmado" voltaria para sempre.
        """
        cliente = Cliente.objects.create(
            nome_cliente="Rita Souza",
            telefone="(11) 97777-6655",
            canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
        )
        self.assertIn("WhatsApp não confirmado", pendencias_do_cliente(cliente))

        self.completar(
            cliente, telefone="(11) 97777-6655", canal_telefone_perguntado="1",
        )

        cliente.refresh_from_db()
        self.assertEqual(cliente.canal_telefone, Cliente.CanalTelefone.WHATSAPP)
        self.assertNotIn("WhatsApp não confirmado", pendencias_do_cliente(cliente))

    def test_marcar_a_caixa_mantem_o_numero_fora_do_whatsapp(self):
        cliente = Cliente.objects.create(
            nome_cliente="Paulo Lima", telefone="(11) 97777-6655",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
        )

        self.completar(
            cliente, telefone="(11) 97777-6655",
            canal_telefone_perguntado="1",
            canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
        )

        cliente.refresh_from_db()
        self.assertEqual(
            cliente.canal_telefone, Cliente.CanalTelefone.NAO_CONFIRMADO
        )

    def test_a_resposta_diz_o_que_ainda_falta(self):
        """É com isso que a linha se atualiza sem recarregar a tela."""
        cliente = Cliente.objects.create(nome_cliente="Meio Cadastro")

        resposta = self.completar(cliente, telefone="(11) 97777-6655")

        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertEqual(corpo["id"], cliente.pk)
        self.assertIn("CPF/CNPJ", corpo["pendencias"])
        self.assertIn("endereço", corpo["pendencias"])
        self.assertNotIn("contato", corpo["pendencias"])

    def test_documento_de_outro_cliente_nao_e_aceito(self):
        """Dois cadastros com o mesmo CPF partem o histórico em dois."""
        Cliente.objects.create(
            nome_cliente="Original", telefone="(11) 97777-6655",
            documento="111.444.777-35",
        )
        duplicado = Cliente.objects.create(
            nome_cliente="Duplicado", telefone="(11) 96666-5544",
        )

        resposta = self.completar(duplicado, documento="111.444.777-35")

        self.assertEqual(resposta.status_code, 400)
        duplicado.refresh_from_db()
        self.assertEqual(duplicado.documento, "")

    def test_a_tela_oferece_a_janela_em_quem_esta_incompleto(self):
        cliente = Cliente.objects.create(nome_cliente="Faltando Tudo")

        html = self.client.get(
            "/clientes/", HTTP_HOST="interno.testserver"
        ).content.decode()

        self.assertIn('data-completar="%d"' % cliente.pk, html)
        self.assertIn('id="modalCompletar"', html)
        self.assertIn('value="completar"', html)
