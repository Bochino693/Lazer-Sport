"""A tela "Segurança das contas" (interno.) e as regras de desenho do painel."""

import re
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from . import freio
from .models import OcorrenciaSeguranca

INTERNO = {"HTTP_HOST": "interno.testserver"}
ROTA = "/seguranca/contas/"
RAIZ = Path(__file__).resolve().parent.parent
TEMPLATE = RAIZ / "contas" / "templates" / "contas" / "seguranca_contas.html"
CSS = RAIZ / "sistema_interno" / "static" / "interno" / "gestao_integrada.css"


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class TelaTests(TestCase):
    def setUp(self):
        self.chefe = User.objects.create_superuser("chefe", email="chefe@example.com", password="x")
        self.comercial = User.objects.create_user("comercial", email="vendas@example.com")
        self.bloqueada = User.objects.create_user("bloqueada", email="", is_active=False)
        self.repetido = OcorrenciaSeguranca.objects.create(
            tipo=OcorrenciaSeguranca.Tipo.EMAIL_REPETIDO, usuario=self.bloqueada,
            conta_mantida=self.comercial, username="bloqueada",
            email_original="vendas@example.com", origem="migracao", motivo="O mesmo e-mail.",
        )

    def abrir(self, **params):
        return self.client.get(ROTA, params, **INTERNO)

    def acao(self, acao, ocorrencia):
        return self.client.post(ROTA, {"action": acao, "id": ocorrencia.pk}, **INTERNO)

    def test_gestao_e_super_abrem_a_tela(self):
        self.client.force_login(self.chefe)
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Segurança das contas")
        self.assertContains(resposta, "@bloqueada")
        self.assertContains(resposta, 'data-ls-confirmar=')
        self.assertContains(resposta, 'href="/seguranca/contas/"')  # o atalho no menu

        gestor = User.objects.create_user("gestor", password="x")
        gestor.groups.add(Group.objects.get_or_create(name="Equipe · Gestão")[0])
        self.client.force_login(gestor)
        self.assertEqual(self.abrir().status_code, 200)

    def test_quem_nao_e_gestao_nao_entra(self):
        vendedor = User.objects.create_user("vendedor", password="x")
        vendedor.groups.add(Group.objects.get_or_create(name="Equipe · Vendas")[0])
        self.client.force_login(vendedor)
        self.assertEqual(self.abrir().status_code, 302)
        self.assertEqual(self.acao("reativar", self.repetido).status_code, 302)
        self.bloqueada.refresh_from_db()
        self.assertFalse(self.bloqueada.is_active)

        self.client.logout()
        self.assertEqual(self.abrir().status_code, 302)

    def test_reativar_volta_a_conta_sem_email_e_registra_quem(self):
        self.client.force_login(self.chefe)
        resposta = self.acao("reativar", self.repetido)
        self.assertEqual(resposta.status_code, 302)
        self.bloqueada.refresh_from_db()
        self.repetido.refresh_from_db()
        self.assertTrue(self.bloqueada.is_active)
        self.assertEqual(self.bloqueada.email, "")
        self.assertEqual(self.repetido.situacao, OcorrenciaSeguranca.Situacao.REATIVADA)
        self.assertEqual(self.repetido.resolvido_por, self.chefe)
        self.assertIsNotNone(self.repetido.resolvido_em)
        # resolvida não se resolve de novo
        resposta = self.client.post(ROTA, {"action": "manter", "id": self.repetido.pk},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 400)

    def test_manter_bloqueada(self):
        self.client.force_login(self.chefe)
        self.acao("manter", self.repetido)
        self.bloqueada.refresh_from_db()
        self.repetido.refresh_from_db()
        self.assertFalse(self.bloqueada.is_active)
        self.assertEqual(self.repetido.situacao, OcorrenciaSeguranca.Situacao.MANTIDA)

    def test_filtros_de_situacao_e_tipo(self):
        self.client.force_login(self.chefe)
        OcorrenciaSeguranca.objects.create(
            tipo=OcorrenciaSeguranca.Tipo.LOGIN_BLOQUEADO, login_tentado="alguem",
            situacao=OcorrenciaSeguranca.Situacao.CIENTE,
        )
        self.assertNotContains(self.abrir(), "alguem")
        self.assertContains(self.abrir(situacao="resolvidas"), "alguem")
        self.assertNotContains(self.abrir(situacao="todas", tipo="email_repetido"), "alguem")

    @override_settings(LOGIN_FREIO_ATIVO=True, LOGIN_FREIO_POR_CONTA=2)
    def test_liberar_o_login_pausado(self):
        cache.clear()
        pessoa = User.objects.create_user("pessoa", password="girafa-azul-no-telhado")
        from django.test import RequestFactory

        request = RequestFactory().post("/login/")
        freio.registrar_falha(request, "pessoa")
        freio.registrar_falha(request, "pessoa")
        self.assertTrue(freio.segundos_de_bloqueio(request, "pessoa"))
        ocorrencia = OcorrenciaSeguranca.objects.get(tipo="login_bloqueado")
        self.assertEqual(ocorrencia.usuario, pessoa)

        self.client.force_login(self.chefe)
        self.acao("liberar", ocorrencia)
        self.assertEqual(freio.segundos_de_bloqueio(request, "pessoa"), 0)
        ocorrencia.refresh_from_db()
        self.assertEqual(ocorrencia.situacao, OcorrenciaSeguranca.Situacao.LIBERADA)
        cache.clear()

    def test_acao_errada_para_o_tipo(self):
        self.client.force_login(self.chefe)
        resposta = self.client.post(ROTA, {"action": "liberar", "id": self.repetido.pk},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 400)


class RegrasDeDesenhoTests(SimpleTestCase):
    """As regras do painel: sem <select>, sem alert/confirm, sem cor fixa, {# #} de uma linha."""

    def test_template(self):
        texto = TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("<select", texto)
        self.assertNotRegex(texto, r"\balert\(|\bconfirm\(")
        self.assertNotIn("DOMContentLoaded", texto)
        for numero, linha in enumerate(texto.splitlines(), 1):
            for achado in re.finditer(r"\{#(?![A-Za-z_-])", linha):
                self.assertIn("#}", linha[achado.end():], f"linha {numero}")
        self.assertIn('type="radio"', texto)
        self.assertIn("data-ls-confirmar", texto)

    def test_css_da_tela_so_com_variaveis_do_tema(self):
        css = CSS.read_text(encoding="utf-8")
        bloco = css[css.index("SEGURANÇA DAS CONTAS"):]
        bloco = re.sub(r"/\*.*?\*/", "", bloco, flags=re.S)
        self.assertNotRegex(bloco, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotRegex(bloco, r"rgba?\(\s*\d")
        self.assertNotRegex(bloco, r"\b(white|gray|grey|silver|whitesmoke)\b")
