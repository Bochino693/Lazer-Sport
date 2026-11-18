"""Todo caminho que cria conta ou muda e-mail recusa o e-mail de outra conta.

A conta comercial ("comercial", vendas@example.com) já existe; cada teste
tenta o MESMO endereço com outra caixa ou variante por um caminho:
cadastro do site, perfil, painel (Usuários, Equipe e acessos, Minha conta),
API do aplicativo, "Meus e-mails" e cadastro do allauth, /system/ e o login
pelo Google/Apple. E-mails inventados.
"""

from allauth.account.models import EmailAddress
from allauth.core import context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.internal.flows.login import complete_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser, Group, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.tests_antifraude import dados_do_cadastro

from .models import OcorrenciaSeguranca

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class BaseCaminhos(TestCase):
    def setUp(self):
        self.comercial = User.objects.create_user(
            "comercial", email="vendas@example.com", password="senha-comercial-forte",
        )
        self.comercial.groups.add(Group.objects.get_or_create(name="Equipe · Vendas")[0])

    def contas_com(self, email="vendas@example.com"):
        return User.objects.filter(email__iexact=email).count() + EmailAddress.objects.filter(
            email__iexact=email,
        ).exclude(user=self.comercial).count()


class CadastroDoSiteTests(BaseCaminhos):
    def test_registrar_com_o_mesmo_email_em_maiusculas_e_recusado(self):
        resposta = self.client.post(
            reverse("registrar"),
            dados_do_cadastro(email="VENDAS@Example.com", username="intruso"),
            HTTP_X_FORWARDED_FOR="45.170.20.9",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe uma conta com esse e-mail")
        self.assertFalse(User.objects.filter(username="intruso").exists())
        self.assertEqual(self.contas_com(), 1)

    def test_registrar_com_variante_unicode_e_recusado(self):
        resposta = self.client.post(
            reverse("registrar"),
            dados_do_cadastro(email="vendas@example.com.", username="intruso"),
            HTTP_X_FORWARDED_FOR="45.170.20.9",
        )
        self.assertFalse(User.objects.filter(username="intruso").exists())
        self.assertEqual(resposta.status_code, 200)

    def test_registrar_com_endereco_da_empresa_e_recusado(self):
        resposta = self.client.post(
            reverse("registrar"),
            dados_do_cadastro(email="contato@lazersport.com.br", username="intruso"),
            HTTP_X_FORWARDED_FOR="45.170.20.9",
        )
        self.assertContains(resposta, "própria Lazer &amp; Sport")
        self.assertFalse(User.objects.filter(username="intruso").exists())

    def test_cadastro_bom_grava_normalizado_e_com_endereco_do_allauth(self):
        resposta = self.client.post(
            reverse("registrar"),
            dados_do_cadastro(email="Nova.Cliente@Example.com", username="nova"),
            HTTP_X_FORWARDED_FOR="45.170.20.9",
        )
        self.assertEqual(resposta.status_code, 302, resposta.content[:300])
        conta = User.objects.get(username="nova")
        self.assertEqual(conta.email, "nova.cliente@example.com")
        self.assertTrue(EmailAddress.objects.filter(user=conta, email="nova.cliente@example.com", primary=True).exists())


class PerfilTests(BaseCaminhos):
    def test_trocar_no_perfil_para_o_email_comercial_e_recusado(self):
        cliente = User.objects.create_user("cliente", email="cliente@example.com", password="x")
        cliente.perfil.telefone = "(11)91234-5678"
        cliente.perfil.save()
        self.client.force_login(cliente)
        resposta = self.client.post(reverse("perfil"), {
            "first_name": "Cli", "last_name": "Ente", "email": "Vendas@EXAMPLE.com",
            "nome_completo": "Cli Ente", "telefone": "(11)91234-5678",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "já está em outra conta")
        cliente.refresh_from_db()
        self.assertEqual(cliente.email, "cliente@example.com")

    def test_trocar_no_perfil_leva_o_endereco_do_allauth(self):
        cliente = User.objects.create_user("cliente", email="cliente@example.com", password="x")
        EmailAddress.objects.create(user=cliente, email="cliente@example.com", primary=True)
        cliente.perfil.telefone = "(11)91234-5678"
        cliente.perfil.save()
        self.client.force_login(cliente)
        resposta = self.client.post(reverse("perfil"), {
            "first_name": "Cli", "last_name": "Ente", "email": "Novo.Endereco@example.com",
            "nome_completo": "Cli Ente", "telefone": "(11)91234-5678",
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            list(EmailAddress.objects.filter(user=cliente).values_list("email", flat=True)),
            ["novo.endereco@example.com"],
        )


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class PainelTests(BaseCaminhos):
    def setUp(self):
        super().setUp()
        self.chefe = User.objects.create_superuser("chefe", email="chefe@example.com", password="x")
        self.client.force_login(self.chefe)

    def test_usuarios_do_painel_recusa_email_comercial_em_outra_caixa(self):
        resposta = self.client.post("/site/contas-clientes/", {
            "username": "intruso", "email": "VENDAS@example.com", "password": "girafa-azul-no-telhado",
            "is_active": "on",
        }, follow=True, **INTERNO)
        self.assertContains(resposta, "já está em uso")
        self.assertFalse(User.objects.filter(username="intruso").exists())

    def test_usuarios_do_painel_recusa_endereco_extra_de_outra_conta(self):
        EmailAddress.objects.create(user=self.comercial, email="comercial.extra@example.com")
        self.client.post("/site/contas-clientes/", {
            "username": "intruso", "email": "Comercial.Extra@example.com", "password": "girafa-azul-no-telhado",
        }, **INTERNO)
        self.assertFalse(User.objects.filter(username="intruso").exists())

    def test_usuarios_do_painel_recusa_senha_fraca_e_cria_com_endereco_do_allauth(self):
        self.client.post("/site/contas-clientes/", {
            "username": "nova", "email": "nova@example.com", "password": "12345678",
        }, **INTERNO)
        self.assertFalse(User.objects.filter(username="nova").exists())
        self.client.post("/site/contas-clientes/", {
            "username": "nova", "email": "Nova@Example.com", "password": "girafa-azul-no-telhado",
            "is_active": "on",
        }, **INTERNO)
        conta = User.objects.get(username="nova")
        self.assertEqual(conta.email, "nova@example.com")
        self.assertTrue(EmailAddress.objects.filter(user=conta, email="nova@example.com").exists())

    def test_equipe_e_acessos_recusa_email_comercial(self):
        resposta = self.client.post("/equipe/", {
            "action": "save", "username": "novo-vendedor", "email": " VENDAS@example.com ",
            "password": "girafa-azul-no-telhado", "funcoes": ["vendas"], "is_active": "on",
        }, **INTERNO, **AJAX)
        self.assertEqual(resposta.status_code, 400, resposta.content)
        self.assertIn("já está em uso", resposta.json()["msg"])
        self.assertFalse(User.objects.filter(username="novo-vendedor").exists())

    def test_equipe_e_acessos_recusa_endereco_extra_do_allauth(self):
        EmailAddress.objects.create(user=self.comercial, email="comercial.extra@example.com")
        resposta = self.client.post("/equipe/", {
            "action": "save", "username": "novo-vendedor", "email": "comercial.extra@example.com",
            "password": "girafa-azul-no-telhado", "funcoes": ["vendas"], "is_active": "on",
        }, **INTERNO, **AJAX)
        self.assertEqual(resposta.status_code, 400)

    def test_minha_conta_recusa_email_de_outra_conta(self):
        resposta = self.client.post("/minha-conta/", {
            "first_name": "Chefe", "last_name": "", "email": "Vendas@Example.com",
        }, **INTERNO)
        self.assertEqual(resposta.status_code, 400)
        self.chefe.refresh_from_db()
        self.assertEqual(self.chefe.email, "chefe@example.com")

    def test_minha_conta_recusa_senha_fraca(self):
        self.client.post("/minha-conta/", {
            "first_name": "Chefe", "email": "chefe@example.com",
            "senha_atual": "x", "senha_nova": "senha12345", "senha_confirmacao": "senha12345",
        }, **INTERNO)
        self.chefe.refresh_from_db()
        self.assertTrue(self.chefe.check_password("x"))


class ApiTests(BaseCaminhos):
    def test_registro_pelo_aplicativo_recusa_email_comercial_em_outra_caixa(self):
        resposta = self.client.post("/api/v1/auth/registro/", {
            "nome_completo": "Intruso", "email": "VENDAS@Example.com",
            "telefone": "11988887777", "senha": "girafa-azul-no-telhado",
        }, content_type="application/json")
        self.assertEqual(resposta.status_code, 400, resposta.content)
        self.assertIn("email", resposta.json())
        self.assertEqual(self.contas_com(), 1)

    def test_registro_pelo_aplicativo_recusa_senha_fraca(self):
        resposta = self.client.post("/api/v1/auth/registro/", {
            "nome_completo": "Nova Pessoa", "email": "nova@example.com",
            "telefone": "11988887777", "senha": "senha12345",
        }, content_type="application/json")
        self.assertEqual(resposta.status_code, 400, resposta.content)
        self.assertIn("senha", resposta.json())

    def test_usuario_antigo_igual_ao_email_ganha_sufixo(self):
        User.objects.create_user("nova@example.com", email="outra@example.com")
        resposta = self.client.post("/api/v1/auth/registro/", {
            "nome_completo": "Nova Pessoa", "email": "Nova@Example.com",
            "telefone": "11988887777", "senha": "girafa-azul-no-telhado",
        }, content_type="application/json")
        self.assertEqual(resposta.status_code, 201, resposta.content)
        self.assertEqual(User.objects.get(email="nova@example.com").username, "nova")


class AllauthTests(BaseCaminhos):
    def test_meus_emails_nao_acrescenta_o_email_de_outra_conta(self):
        cliente = User.objects.create_user("cliente", email="cliente@example.com", password="x")
        cliente.perfil.telefone = "(11)91234-5678"
        cliente.perfil.save()
        self.client.force_login(cliente)
        self.client.post(reverse("account_email"), {"action_add": "1", "email": "Vendas@Example.com"})
        self.assertFalse(EmailAddress.objects.filter(user=cliente, email__iexact="vendas@example.com").exists())

    def test_o_adapter_recusa_no_cadastro_do_allauth(self):
        from allauth.account.adapter import get_adapter

        request = RequestFactory().get("/accounts/signup/")
        request.user = AnonymousUser()
        adapter = get_adapter(request)
        self.assertEqual(adapter.clean_email(" Pessoa@Example.COM "), "pessoa@example.com")
        with self.assertRaises(Exception) as erro:
            adapter.validate_unique_email("vendas@example.com")
        self.assertIn("já está em outra conta", str(erro.exception))


class AdminTests(BaseCaminhos):
    def test_system_recusa_email_de_outra_conta(self):
        from .forms import UsuarioAdminForm

        cliente = User.objects.create_user("cliente", email="cliente@example.com")
        form = UsuarioAdminForm(instance=cliente, data={
            "username": "cliente", "email": "VENDAS@example.com",
            "date_joined_0": "2026-01-01", "date_joined_1": "10:00",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


GOOGLE = {
    "google": {
        "APPS": [{"client_id": "id-de-teste", "secret": "segredo-de-teste", "key": ""}],
        "SCOPE": ["profile", "email"],
        "EMAIL_AUTHENTICATION": True,
    },
}


@override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE, CADASTRO_LIMITE_POR_IP=0)
class LoginSocialTests(BaseCaminhos):
    """O e-mail do Google/Apple só liga a uma conta quando o provedor garante."""

    def entrar(self, email, *, verificado=True, uid="google-uid-1", provedor="google"):
        request = RequestFactory().get(f"/accounts/{provedor}/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        with context.request_context(request):
            provider = get_social_adapter().get_provider(request, provedor)
            dados = {"sub": uid, "email": email, "email_verified": verificado,
                     "given_name": "Pessoa", "family_name": "Teste"}
            sociallogin = provider.sociallogin_from_response(request, dados)
            sociallogin.state = {"process": "login"}
            resposta = complete_login(request, sociallogin)
        return resposta, request

    def test_google_verificado_liga_a_conta_daquele_email_sem_criar_outra(self):
        # o e-mail da conta da equipe gravado com maiúsculas (dado antigo,
        # pela porta que não normalizava): o allauth não o achava
        User.objects.filter(pk=self.comercial.pk).update(email="Vendas@Example.com")
        total = User.objects.count()
        resposta, request = self.entrar("vendas@example.com")
        self.assertEqual(User.objects.count(), total)
        self.assertTrue(SocialAccount.objects.filter(user=self.comercial, provider="google").exists())
        self.assertEqual(int(request.session["_auth_user_id"]), self.comercial.pk)
        # conta da equipe: a senha do painel continua valendo
        self.comercial.refresh_from_db()
        self.assertTrue(self.comercial.check_password("senha-comercial-forte"))
        self.assertTrue(EmailAddress.objects.get(user=self.comercial).verified)

    def test_google_sem_garantia_nao_liga_nem_cria_outra_conta(self):
        total = User.objects.count()
        resposta, request = self.entrar("VENDAS@example.com", verificado=False)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("login"))
        self.assertEqual(User.objects.count(), total)
        self.assertFalse(SocialAccount.objects.exists())
        self.assertNotIn("_auth_user_id", request.session)
        ocorrencia = OcorrenciaSeguranca.objects.get()
        self.assertEqual(ocorrencia.tipo, OcorrenciaSeguranca.Tipo.SOCIAL_RECUSADO)
        self.assertEqual(ocorrencia.usuario, self.comercial)

    def test_cliente_com_email_nao_confirmado_perde_a_senha_ao_ligar_o_google(self):
        cliente = User.objects.create_user("cliente", password="senha-que-alguem-pos")
        User.objects.filter(pk=cliente.pk).update(email="Cliente@Example.com")
        self.entrar("cliente@example.com", uid="google-uid-2")
        cliente.refresh_from_db()
        self.assertTrue(SocialAccount.objects.filter(user=cliente).exists())
        self.assertFalse(cliente.has_usable_password())

    def test_conta_nova_pelo_google_com_email_livre(self):
        self.entrar("Pessoa.Nova@Example.com", uid="google-uid-3")
        conta = User.objects.get(socialaccount__uid="google-uid-3")
        self.assertEqual(conta.email, "pessoa.nova@example.com")

    def test_endereco_da_empresa_nao_cria_conta_pelo_google(self):
        total = User.objects.count()
        resposta, _ = self.entrar("alguem@lazersport.com.br", uid="google-uid-4")
        self.assertEqual(User.objects.count(), total)
        self.assertEqual(resposta.url, reverse("login"))
        self.assertTrue(OcorrenciaSeguranca.objects.filter(tipo="social_recusado").exists())

    def test_cadastro_social_confere_de_novo_antes_de_gravar(self):
        from allauth.socialaccount.models import SocialLogin

        from .adapters import SocialAccountAdapter

        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request._messages = FallbackStorage(request)
        sociallogin = SocialLogin(
            user=User(email="vendas@example.com"),
            account=SocialAccount(provider="google", uid="corrida"),
            email_addresses=[EmailAddress(email="vendas@example.com", verified=True)],
        )
        with self.assertRaises(ImmediateHttpResponse):
            SocialAccountAdapter().save_user(request, sociallogin)
