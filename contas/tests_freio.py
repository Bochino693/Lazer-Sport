"""O freio do login: por conta e por IP, em todas as portas.

O freio fica desligado no resto da suíte (settings_test): aqui ele é
ligado, com o cache limpo antes e depois de cada teste.
"""

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import freio
from .models import OcorrenciaSeguranca

IP_PUBLICO = "45.170.20.9"
SENHA = "girafa-azul-no-telhado"


@override_settings(
    LOGIN_FREIO_ATIVO=True, LOGIN_FREIO_POR_CONTA=5, LOGIN_FREIO_POR_IP=8,
    LOGIN_FREIO_JANELA_MIN=15, LOGIN_FREIO_BLOQUEIO_MIN=15,
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
)
class FreioTests(TestCase):
    def setUp(self):
        cache.clear()
        self.conta = User.objects.create_user("pessoa", email="pessoa@example.com", password=SENHA)
        self.conta.perfil.telefone = "(11)91234-5678"
        self.conta.perfil.save()

    def tearDown(self):
        cache.clear()

    def entrar_no_site(self, login, senha, ip="127.0.0.1"):
        return self.client.post(reverse("login"), {"username": login, "password": senha}, REMOTE_ADDR=ip)

    def test_cinco_senhas_erradas_pausam_a_conta_mesmo_com_a_senha_certa(self):
        for _ in range(4):
            self.assertEqual(self.entrar_no_site("pessoa", "errada").status_code, 200)
        resposta = self.entrar_no_site("PESSOA@example.com", "errada")  # o e-mail conta na mesma conta
        self.assertEqual(resposta.status_code, 429)
        resposta = self.entrar_no_site("pessoa", SENHA)
        self.assertEqual(resposta.status_code, 429)
        self.assertContains(resposta, "pausado", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

        ocorrencia = OcorrenciaSeguranca.objects.get()
        self.assertEqual(ocorrencia.tipo, OcorrenciaSeguranca.Tipo.LOGIN_BLOQUEADO)
        self.assertEqual(ocorrencia.usuario, self.conta)
        self.assertEqual(ocorrencia.origem, "site")

    def test_liberar_tira_a_pausa(self):
        for _ in range(5):
            self.entrar_no_site("pessoa", "errada")
        freio.liberar(conta=self.conta)
        resposta = self.entrar_no_site("pessoa", SENHA)
        self.assertEqual(resposta.status_code, 302)

    def test_acerto_zera_a_contagem_da_conta(self):
        for _ in range(4):
            self.entrar_no_site("pessoa", "errada")
        self.assertEqual(self.entrar_no_site("pessoa", SENHA).status_code, 302)
        self.client.logout()
        for _ in range(4):
            self.assertEqual(self.entrar_no_site("pessoa", "errada").status_code, 200)

    def test_login_que_nao_existe_tambem_e_pausado(self):
        for _ in range(5):
            resposta = self.entrar_no_site("ninguem@example.com", "errada")
        self.assertEqual(resposta.status_code, 429)

    def test_ip_publico_que_chuta_em_muitas_contas_e_pausado(self):
        for numero in range(8):
            self.entrar_no_site(f"conta-{numero}", "errada", ip=IP_PUBLICO)
        resposta = self.entrar_no_site("pessoa", SENHA, ip=IP_PUBLICO)
        self.assertEqual(resposta.status_code, 429)
        # de outro lugar, a conta entra
        self.assertEqual(self.entrar_no_site("pessoa", SENHA, ip="45.170.20.10").status_code, 302)
        self.assertTrue(OcorrenciaSeguranca.objects.filter(usuario__isnull=True, ip=IP_PUBLICO).exists())

    def test_ip_privado_nao_e_pausado_pelo_ip(self):
        for numero in range(12):
            self.entrar_no_site(f"conta-{numero}", "errada")
        self.assertEqual(self.entrar_no_site("pessoa", SENHA).status_code, 302)

    def test_painel_interno(self):
        equipe = User.objects.create_user("vendedor", email="vendedor@example.com", password=SENHA)
        equipe.groups.add(Group.objects.get_or_create(name="Equipe · Vendas")[0])
        for _ in range(5):
            self.client.post("/login/inner/", {"login": "vendedor", "password": "errada"}, HTTP_HOST="interno.testserver")
        resposta = self.client.post("/login/inner/", {"login": "vendedor", "password": SENHA}, HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 429)
        self.assertContains(resposta, "pausado", status_code=429)
        self.assertEqual(OcorrenciaSeguranca.objects.get().origem, "painel")

    def test_system_do_admin(self):
        User.objects.create_superuser("chefe", email="chefe@example.com", password=SENHA)
        for _ in range(5):
            self.client.post("/system/login/", {"username": "chefe", "password": "errada"})
        resposta = self.client.post("/system/login/", {"username": "chefe", "password": SENHA})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "pausado")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(OcorrenciaSeguranca.objects.get().origem, "admin")

    def test_aplicativo(self):
        for _ in range(5):
            self.client.post("/api/v1/auth/login/", {"login": "pessoa", "senha": "errada"}, content_type="application/json")
        resposta = self.client.post("/api/v1/auth/login/", {"login": "pessoa", "senha": SENHA}, content_type="application/json")
        self.assertEqual(resposta.status_code, 429)
        self.assertIn("pausado", resposta.json()["detail"])
        self.assertIn("Retry-After", resposta)

    def test_quem_chama_authenticate_direto_tambem_e_barrado(self):
        """O allauth (/accounts/login/) e qualquer tela futura: o backend do freio."""
        from django.contrib.auth import authenticate
        from django.test import RequestFactory

        request = RequestFactory().post("/accounts/login/")
        for _ in range(5):
            self.assertIsNone(authenticate(request, username="pessoa", password="errada"))
        # as falhas de fora foram contadas pelo sinal; a pausa vale no authenticate
        self.assertIsNone(authenticate(request, username="pessoa", password=SENHA))
        self.assertEqual(OcorrenciaSeguranca.objects.get().origem, "allauth")

    @override_settings(LOGIN_FREIO_ATIVO=False)
    def test_desligado_nao_pausa(self):
        for _ in range(8):
            self.entrar_no_site("pessoa", "errada")
        self.assertEqual(self.entrar_no_site("pessoa", SENHA).status_code, 302)
