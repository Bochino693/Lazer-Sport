"""O registro de cada cadastro (de onde veio) e o freio de contas falsas.

O que se garante: os três caminhos que criam conta (formulário, API do
aplicativo, Google/Apple) deixam um RegistroCadastro com IP, navegador e
origem; um defeito no registro nunca impede o cadastro; a região só é
consultada depois do commit, numa thread, e nunca para IP privado; o
formulário barra robô (campo-isca, envio rápido demais, pergunta errada,
selo inválido); contas demais do mesmo IP fecham o cadastro nos três
caminhos; quem cria conta recebe o e-mail de confirmação; e a política de
privacidade existe e está linkada.
"""
import time
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail, signing
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from . import captcha, registro_cadastro
from .adapters import AccountAdapter, SocialAccountAdapter
from .models import RegistroCadastro

IP = "45.170.20.9"


def selo(segundos_atras=30, codigo="ABC23"):
    return signing.dumps({"t": int(time.time()) - segundos_atras, "h": captcha._assinatura(codigo)}, salt=captcha.SAL)


def dados_do_cadastro(**extra):
    base = {
        "first_name": "Maria",
        "last_name": "Souza",
        "username": "maria.souza",
        "email": "maria@example.com",
        "telefone": "(11)99999-8888",
        "password": "senha-forte-123",
        "password2": "senha-forte-123",
        "selo_cadastro": selo(),
        "resposta_humana": "abc23",
        "site_web": "",
    }
    base.update(extra)
    return base


@override_settings(CADASTRO_LIMITE_POR_IP=5, CADASTRO_JANELA_HORAS=24, CADASTRO_TEMPO_MINIMO=4, GEOIP_ATIVO=False)
class CadastroPeloSiteTests(TestCase):
    def cadastrar(self, **extra):
        return self.client.post(
            reverse("registrar"), dados_do_cadastro(**extra),
            HTTP_X_FORWARDED_FOR=f"{IP}, 10.0.0.2", HTTP_USER_AGENT="Mozilla/5.0 (teste)",
        )

    def test_cadastro_grava_o_registro_e_manda_o_email(self):
        resposta = self.cadastrar()
        self.assertEqual(resposta.status_code, 302, resposta.content[:300])
        usuario = User.objects.get(username="maria.souza")
        registro = RegistroCadastro.objects.get(usuario=usuario)
        self.assertEqual(registro.ip, IP)
        self.assertEqual(registro.origem, RegistroCadastro.Origem.SITE)
        self.assertIn(f"X_FORWARDED_FOR={IP}, 10.0.0.2", registro.cabecalhos_ip)
        self.assertEqual(registro.navegador, "Mozilla/5.0 (teste)")
        self.assertEqual(registro.email, "maria@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirme o seu e-mail", mail.outbox[0].subject)
        self.assertIn("/accounts/confirm-email/", mail.outbox[0].body)

    def test_campo_isca_preenchido_e_robo(self):
        resposta = self.cadastrar(site_web="http://spam.example")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, captcha.MENSAGEM_ROBO)
        self.assertFalse(User.objects.filter(username="maria.souza").exists())

    def test_rapido_demais_pergunta_errada_e_selo_invalido(self):
        self.assertContains(self.cadastrar(selo_cadastro=selo(segundos_atras=1)), captcha.MENSAGEM_RAPIDO)
        self.assertContains(self.cadastrar(resposta_humana="zzz99"), "código da imagem")
        self.assertContains(self.cadastrar(selo_cadastro="lixo"), captcha.MENSAGEM_ROBO)
        self.assertContains(self.cadastrar(selo_cadastro=""), captcha.MENSAGEM_ROBO)
        self.assertFalse(User.objects.filter(username="maria.souza").exists())

    def test_maiusculas_ou_minusculas_tanto_faz_e_o_selo_antigo_de_conta_ainda_vale(self):
        self.assertEqual(self.cadastrar(resposta_humana="AbC 23").status_code, 302)
        antigo = signing.dumps({"t": int(time.time()) - 30, "r": 7}, salt=captcha.SAL)
        self.assertEqual(self.client.post(reverse("registrar"), dados_do_cadastro(username="outra", email="outra@example.com", selo_cadastro=antigo, resposta_humana="sete"), HTTP_X_FORWARDED_FOR="45.170.20.11").status_code, 302)

    def test_outra_imagem_vem_por_json(self):
        resposta = self.client.get(reverse("registrar_desafio"))
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["imagem"].startswith("data:image/png;base64,"))
        self.assertIn("h", signing.loads(dados["selo"], salt=captcha.SAL))
        self.assertEqual(resposta["Cache-Control"], "no-store")

    def test_a_pagina_traz_o_desafio_a_isca_e_a_privacidade(self):
        pagina = self.client.get(reverse("registrar"))
        self.assertContains(pagina, 'name="selo_cadastro"')
        self.assertContains(pagina, 'name="site_web"')
        self.assertContains(pagina, "data:image/png;base64")
        self.assertContains(pagina, reverse("registrar_desafio"))
        self.assertContains(pagina, reverse("privacidade"))
        self.assertNotContains(pagina, "cf-turnstile")

    @override_settings(TURNSTILE_SITE_KEY="chave-site", TURNSTILE_SECRET_KEY="segredo")
    def test_com_as_chaves_o_turnstile_entra_no_lugar_da_pergunta(self):
        pagina = self.client.get(reverse("registrar"))
        self.assertContains(pagina, 'data-sitekey="chave-site"')
        self.assertNotContains(pagina, "data:image/png;base64")
        # sem o token (ou sem resposta do Cloudflare), não passa
        with mock.patch.object(captcha, "verificar_turnstile", return_value=False) as conferiu:
            resposta = self.cadastrar(selo_cadastro=signing.dumps({"t": int(time.time()) - 30}, salt=captcha.SAL))
        self.assertContains(resposta, "A verificação de segurança não passou")
        conferiu.assert_called_once()
        with mock.patch.object(captcha, "verificar_turnstile", return_value=True):
            resposta = self.cadastrar(**{"selo_cadastro": signing.dumps({"t": int(time.time()) - 30}, salt=captcha.SAL), "cf-turnstile-response": "token"})
        self.assertEqual(resposta.status_code, 302)

    def test_contas_demais_do_mesmo_ip_fecham_o_cadastro(self):
        for i in range(5):
            RegistroCadastro.objects.create(username=f"falso{i}", ip=IP, origem="site")
        resposta = self.cadastrar()
        self.assertContains(resposta, "várias contas")
        self.assertFalse(User.objects.filter(username="maria.souza").exists())
        # outro IP segue livre
        resposta = self.client.post(reverse("registrar"), dados_do_cadastro(), HTTP_X_FORWARDED_FOR="45.170.20.10")
        self.assertEqual(resposta.status_code, 302)

    def test_um_defeito_no_registro_nao_impede_o_cadastro(self):
        with mock.patch.object(RegistroCadastro.objects, "create", side_effect=RuntimeError("tabela sumiu")):
            resposta = self.cadastrar()
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(User.objects.filter(username="maria.souza").exists())
        self.assertFalse(RegistroCadastro.objects.exists())

    def test_falha_no_email_nao_derruba_o_cadastro(self):
        with mock.patch("allauth.account.models.EmailAddress.send_confirmation", side_effect=OSError("smtp fora")):
            resposta = self.cadastrar()
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(User.objects.filter(username="maria.souza").exists())


@override_settings(CADASTRO_LIMITE_POR_IP=3, GEOIP_ATIVO=False)
class CadastroPeloAplicativoTests(TestCase):
    URL = "/api/v1/auth/registro/"

    def dados(self, email="app@example.com"):
        return {"nome_completo": "João do App", "email": email, "telefone": "11988887777", "senha": "senha-forte-123"}

    def test_registra_com_origem_app_e_manda_o_email(self):
        resposta = self.client.post(self.URL, self.dados(), content_type="application/json", HTTP_X_FORWARDED_FOR=IP, HTTP_USER_AGENT="LazerApp/2.0")
        self.assertEqual(resposta.status_code, 201, resposta.content)
        registro = RegistroCadastro.objects.get(email="app@example.com")
        self.assertEqual(registro.origem, RegistroCadastro.Origem.APP)
        self.assertEqual(registro.ip, IP)
        self.assertEqual(registro.navegador, "LazerApp/2.0")
        self.assertEqual(len(mail.outbox), 1)

    def test_limite_por_ip_devolve_429(self):
        for i in range(3):
            RegistroCadastro.objects.create(username=f"falso{i}", ip=IP, origem="app")
        resposta = self.client.post(self.URL, self.dados(), content_type="application/json", HTTP_X_FORWARDED_FOR=IP)
        self.assertEqual(resposta.status_code, 429)
        self.assertFalse(User.objects.filter(email="app@example.com").exists())


@override_settings(CADASTRO_LIMITE_POR_IP=2, GEOIP_ATIVO=False)
class GoogleAppleEPainelTests(TestCase):
    """Sem o Google de verdade: o que importa é o caminho e o freio do allauth."""

    def criar_dentro_de(self, caminho, host="testserver", **meta):
        fabrica = RequestFactory()
        request = fabrica.get(caminho, HTTP_HOST=host, **meta)
        request.is_interno = host.startswith("interno.")
        criado = {}

        def resposta(_request):
            nome = "pessoa." + caminho.strip("/").replace("/", ".")
            criado["user"] = User.objects.create_user(username=nome, email=f"{nome}@example.com", password="x")
            return None

        registro_cadastro.RequisicaoAtualMiddleware(resposta)(request)
        return criado["user"]

    def test_origem_pelo_caminho(self):
        casos = {
            "/accounts/google/login/callback/": RegistroCadastro.Origem.GOOGLE,
            "/accounts/apple/login/callback/": RegistroCadastro.Origem.APPLE,
            "/api/v1/auth/registro/": RegistroCadastro.Origem.APP,
            "/registrar/": RegistroCadastro.Origem.SITE,
            "/system/auth/user/add/": RegistroCadastro.Origem.PAINEL,
            "/qualquer/": RegistroCadastro.Origem.OUTRO,
        }
        for caminho, origem in casos.items():
            with self.subTest(caminho=caminho):
                usuario = self.criar_dentro_de(caminho, REMOTE_ADDR=IP)
                self.assertEqual(RegistroCadastro.objects.get(usuario=usuario).origem, origem)

    def test_conta_criada_pelo_painel_interno(self):
        usuario = self.criar_dentro_de("/equipe/", host="interno.testserver", REMOTE_ADDR="10.0.0.9")
        registro = RegistroCadastro.objects.get(usuario=usuario)
        self.assertEqual(registro.origem, RegistroCadastro.Origem.PAINEL)
        self.assertEqual(registro.ip, "10.0.0.9")

    def test_sem_requisicao_nada_e_registrado(self):
        User.objects.create_user(username="pelo.shell", password="x")
        self.assertFalse(RegistroCadastro.objects.exists())

    def test_allauth_fecha_o_cadastro_quando_o_ip_estourou(self):
        request = RequestFactory().get("/accounts/google/login/callback/", REMOTE_ADDR=IP)
        self.assertTrue(AccountAdapter().is_open_for_signup(request))
        self.assertTrue(SocialAccountAdapter().is_open_for_signup(request, mock.Mock()))
        for i in range(2):
            RegistroCadastro.objects.create(username=f"falso{i}", ip=IP, origem="google")
        self.assertFalse(AccountAdapter().is_open_for_signup(request))
        self.assertFalse(SocialAccountAdapter().is_open_for_signup(request, mock.Mock()))
        # e a página que o allauth mostra nesse caso existe e é nossa
        pagina = self.client.get("/accounts/signup/", REMOTE_ADDR=IP)
        self.assertContains(pagina, "Cadastro pausado")


class IPETests(TestCase):
    def test_qual_cabecalho_traz_o_ip(self):
        fabrica = RequestFactory()
        r = fabrica.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.7, 172.16.0.1")
        self.assertEqual(registro_cadastro.ip_da_requisicao(r)[0], "203.0.113.7")
        r = fabrica.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.7, 172.16.0.1", HTTP_CF_CONNECTING_IP="198.51.100.3")
        self.assertEqual(registro_cadastro.ip_da_requisicao(r)[0], "198.51.100.3")
        with override_settings(IP_REAL_CABECALHO="HTTP_X_FORWARDED_FOR"):
            self.assertEqual(registro_cadastro.ip_da_requisicao(r)[0], "203.0.113.7")
        r = fabrica.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="nao-e-ip")
        self.assertEqual(registro_cadastro.ip_da_requisicao(r)[0], "10.0.0.1")

    def test_ip_privado_nunca_estoura_o_limite(self):
        for i in range(10):
            RegistroCadastro.objects.create(username=f"local{i}", ip="127.0.0.1", origem="site")
        r = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1")
        with override_settings(CADASTRO_LIMITE_POR_IP=2):
            self.assertFalse(registro_cadastro.limite_de_cadastros_estourado(r))


class RegiaoTests(TestCase):
    def _resposta(self, dados):
        resposta = mock.Mock()
        resposta.json.return_value = dados
        resposta.raise_for_status.return_value = None
        return resposta

    def test_le_os_dois_formatos_de_servico(self):
        with mock.patch("requests.get", return_value=self._resposta({"city": "São Paulo", "region": "São Paulo", "country_name": "Brazil"})):
            self.assertEqual(registro_cadastro.consultar_regiao(IP), {"cidade": "São Paulo", "estado": "São Paulo", "pais": "Brazil"})
        with mock.patch("requests.get", return_value=self._resposta({"status": "success", "city": "Curitiba", "regionName": "Paraná", "country": "Brazil"})):
            self.assertEqual(registro_cadastro.consultar_regiao(IP)["estado"], "Paraná")
        with mock.patch("requests.get", return_value=self._resposta({"error": True, "reason": "RateLimited"})):
            self.assertEqual(registro_cadastro.consultar_regiao(IP), {})
        with mock.patch("requests.get", side_effect=OSError("sem rede")):
            self.assertEqual(registro_cadastro.consultar_regiao(IP), {})

    @override_settings(GEOIP_ATIVO=True)
    def test_a_consulta_so_depois_do_commit_e_nunca_para_ip_privado(self):
        request = RequestFactory().get("/registrar/", REMOTE_ADDR=IP)
        with mock.patch.object(registro_cadastro, "_em_segundo_plano") as fundo:
            with self.captureOnCommitCallbacks(execute=True):
                registro_cadastro.registrar(User.objects.create_user("a", password="x"), request)
            fundo.assert_called_once()
            fundo.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                registro_cadastro.registrar(User.objects.create_user("b", password="x"), RequestFactory().get("/registrar/", REMOTE_ADDR="192.168.0.5"))
            fundo.assert_not_called()

    def test_preencher_regiao_grava_no_registro(self):
        registro = RegistroCadastro.objects.create(username="x", ip=IP, origem="site")
        with mock.patch.object(registro_cadastro, "consultar_regiao", return_value={"cidade": "Recife", "estado": "Pernambuco", "pais": "Brasil"}):
            self.assertTrue(registro_cadastro.preencher_regiao(registro.pk))
        registro.refresh_from_db()
        self.assertEqual((registro.cidade, registro.pais, registro.regiao_conferida), ("Recife", "Brasil", True))

    def test_o_comando_completa_o_que_ficou_vazio(self):
        publico = RegistroCadastro.objects.create(username="a", ip=IP, origem="site")
        privado = RegistroCadastro.objects.create(username="b", ip="10.1.1.1", origem="site")
        feito = RegistroCadastro.objects.create(username="c", ip="198.51.100.1", origem="site", pais="Brasil", regiao_conferida=True)
        with mock.patch.object(registro_cadastro, "consultar_regiao", return_value={"cidade": "Belém", "estado": "Pará", "pais": "Brasil"}) as consulta:
            call_command("preencher_regioes", pausa=0)
        self.assertEqual(consulta.call_count, 1)
        publico.refresh_from_db(); privado.refresh_from_db(); feito.refresh_from_db()
        self.assertEqual(publico.cidade, "Belém")
        self.assertTrue(privado.regiao_conferida and not privado.pais)
        self.assertEqual(feito.pais, "Brasil")


class PrivacidadeEAdminTests(TestCase):
    def test_a_politica_existe_e_fala_do_ip(self):
        pagina = self.client.get(reverse("privacidade"))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "região aproximada")
        self.assertContains(self.client.get("/"), reverse("privacidade"))

    def test_o_admin_mostra_os_registros_so_leitura(self):
        chefe = User.objects.create_superuser("chefe", "c@example.com", "senha-segura")
        registro = RegistroCadastro.objects.create(username="alguem", ip=IP, origem="site", cidade="Santos", pais="Brasil")
        self.client.force_login(chefe)
        lista = self.client.get("/system/core/registrocadastro/")
        self.assertContains(lista, "Santos")
        self.assertContains(lista, "Cadastros neste IP")
        self.assertEqual(self.client.get("/system/core/registrocadastro/add/").status_code, 403)
        detalhe = self.client.get(f"/system/core/registrocadastro/{registro.pk}/change/")
        self.assertEqual(detalhe.status_code, 200)
        self.assertNotContains(detalhe, 'name="_save"')


class ConfirmacaoDeEmailTests(TestCase):
    def test_a_pagina_do_link_confirma_o_email(self):
        from allauth.account.models import EmailAddress, EmailConfirmationHMAC

        usuario = User.objects.create_user("ana", email="ana@example.com", password="senha-forte-123")
        endereco = EmailAddress.objects.create(user=usuario, email="ana@example.com", primary=True, verified=False)
        chave = EmailConfirmationHMAC(endereco).key

        pagina = self.client.get(f"/accounts/confirm-email/{chave}/")
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Confirme o seu e-mail")
        self.assertContains(pagina, "ana@example.com")

        resposta = self.client.post(f"/accounts/confirm-email/{chave}/")
        self.assertEqual(resposta.status_code, 302)
        endereco.refresh_from_db()
        self.assertTrue(endereco.verified)

        invalida = self.client.get("/accounts/confirm-email/chave-que-nao-existe/")
        self.assertContains(invalida, "Este link não vale mais")
