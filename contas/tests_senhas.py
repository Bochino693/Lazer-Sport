"""Senha forte para conta nova e troca; as contas de hoje continuam entrando.

E os cabeçalhos de segurança que o settings escreve por extenso.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .senhas import validar_senha


class ValidadoresTests(TestCase):
    def test_fracas_sao_recusadas(self):
        conta = User(username="maria.souza", email="maria@example.com", first_name="Maria")
        for senha in (
            "abc12345",            # curta
            "senha12345",          # previsível em português
            "Lazersport2026!",     # o nome da casa
            "1234567890",          # só números e sequência
            "aaaaaaaaaaaa",        # sem variedade
            "qwertyuiop",          # teclado
            "mariasouza123",       # parecida com a conta
        ):
            with self.subTest(senha=senha):
                self.assertTrue(validar_senha(senha, conta), senha)

    def test_boas_passam(self):
        for senha in ("girafa-azul-no-telhado", "Trem das 11 em 2026!", "x7#Kp2!vQm9z"):
            with self.subTest(senha=senha):
                self.assertEqual(validar_senha(senha, User(username="pessoa")), [])

    def test_conta_antiga_com_senha_fraca_continua_entrando(self):
        conta = User.objects.create_user("antiga", password="12345678")
        conta.perfil.telefone = "(11)91234-5678"
        conta.perfil.save()
        resposta = self.client.post(reverse("login"), {"username": "antiga", "password": "12345678"})
        self.assertEqual(resposta.status_code, 302)

    def test_cadastro_do_site_recusa_senha_fraca(self):
        from core.tests_antifraude import dados_do_cadastro

        resposta = self.client.post(
            reverse("registrar"),
            dados_do_cadastro(password="senha12345", password2="senha12345"),
            HTTP_X_FORWARDED_FOR="45.170.20.9",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(username="maria.souza").exists())


class CabecalhosTests(TestCase):
    def test_settings(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertFalse(settings.SECURE_HSTS_PRELOAD)
        self.assertEqual(settings.AUTHENTICATION_BACKENDS[0], "contas.backends.FreioDeLoginBackend")
        self.assertFalse([o for o in settings.CSRF_TRUSTED_ORIGINS if "*" in o])

    def test_resposta_traz_os_cabecalhos(self):
        resposta = self.client.get(reverse("login"))
        self.assertEqual(resposta["X-Frame-Options"], "DENY")
        self.assertEqual(resposta["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resposta["Referrer-Policy"], "same-origin")


class HstsEmProducaoTests(SimpleTestCase):
    """O settings de produção, lido num processo à parte (sem mexer neste)."""

    def test_hsts_moderado_so_no_ar(self):
        import json
        import os
        import subprocess
        import sys
        from pathlib import Path

        ambiente = {
            **os.environ,
            "ENVIRONMENT": "production", "SECRET_KEY": "chave-de-teste",
            "SUPABASE_DATABASE_URL": "sqlite:///ignorado.sqlite3",
            "CLOUDINARY_CLOUD_NAME": "x", "CLOUDINARY_API_KEY": "x", "CLOUDINARY_API_SECRET": "x",
            "RENDER_EXTERNAL_HOSTNAME": "servico-de-teste.onrender.com",
        }
        # sem o settings de teste: o cloudinary leria o Django por ele
        ambiente.pop("DJANGO_SETTINGS_MODULE", None)
        codigo = (
            "import json, lazer.settings as s; print(json.dumps([s.SECURE_HSTS_SECONDS, "
            "s.SECURE_HSTS_INCLUDE_SUBDOMAINS, s.SECURE_HSTS_PRELOAD, s.SESSION_COOKIE_SECURE, "
            "s.CSRF_TRUSTED_ORIGINS]))"
        )
        processo = subprocess.run(
            [sys.executable, "-c", codigo], env=ambiente, capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent, timeout=60,
        )
        self.assertEqual(processo.returncode, 0, processo.stderr[-2000:])
        saida = processo.stdout.strip().splitlines()[-1]
        hsts, subdominios, preload, cookie_seguro, origens = json.loads(saida)
        self.assertEqual(hsts, 2592000)
        self.assertFalse(subdominios)
        self.assertFalse(preload)
        self.assertTrue(cookie_seguro)
        self.assertIn("https://servico-de-teste.onrender.com", origens)
        self.assertFalse([o for o in origens if "*" in o])
