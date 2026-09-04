"""O que uma pessoa de fora NÃO pode fazer neste site.

Cada teste aqui nasceu de um buraco real, encontrado numa varredura do
projeto. O nome de cada um diz o que estava aberto, para que a correção
não seja desfeita sem alguém ler o motivo.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ClientePerfil, Pedido


@override_settings(ALLOWED_HOSTS=["testserver", "interno.testserver"])
class ApiDeImpressaoTests(TestCase):
    """A lista de pedidos para impressão era pública.

    Um GET sem nenhuma credencial devolvia, em JSON, o nome, o telefone e
    o endereço completo de cada cliente com pedido em aberto -- e um POST
    igualmente aberto marcava qualquer pedido como impresso, fazendo com
    que ele nunca fosse impresso de verdade.
    """

    def setUp(self):
        cache.clear()
        self.pedido = Pedido.objects.create(status="aguardando_pagamento")

    def test_visitante_nao_le_a_lista_de_pedidos(self):
        resposta = self.client.get("/api/v1/pedidos-impressao/")

        self.assertEqual(resposta.status_code, 403)

    def test_visitante_nao_marca_pedido_como_impresso(self):
        resposta = self.client.post(
            f"/api/v1/pedido-impresso/{self.pedido.pk}/"
        )

        self.assertEqual(resposta.status_code, 403)
        self.pedido.refresh_from_db()
        self.assertFalse(self.pedido.impresso)

    @override_settings(IMPRESSAO_API_TOKEN="segredo-da-estacao")
    def test_a_estacao_entra_com_o_token(self):
        resposta = self.client.get(
            "/api/v1/pedidos-impressao/",
            HTTP_AUTHORIZATION="Token segredo-da-estacao",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("pedidos", resposta.json())

    @override_settings(IMPRESSAO_API_TOKEN="segredo-da-estacao")
    def test_token_errado_continua_do_lado_de_fora(self):
        resposta = self.client.get(
            "/api/v1/pedidos-impressao/",
            HTTP_AUTHORIZATION="Token quase-o-segredo",
        )

        self.assertEqual(resposta.status_code, 403)

    def test_conta_da_equipe_entra_pela_sessao(self):
        gestor = User.objects.create_user(
            username="impressao", password="senha-longa-de-teste", is_staff=True
        )
        self.client.force_login(gestor)

        resposta = self.client.get("/api/v1/pedidos-impressao/")

        self.assertEqual(resposta.status_code, 200)


class OraculoDeSenhasTests(TestCase):
    """`verify_auth_api` dizia a qualquer um se um par usuário/senha valia.

    A única tranca era um texto de exemplo escrito no próprio repositório.
    A view não existe mais; este teste impede que ela volte por cópia.
    """

    def test_a_view_que_provava_senhas_nao_existe_mais(self):
        import core.views

        self.assertFalse(hasattr(core.views, "verify_auth_api"))

    def test_a_chave_de_exemplo_nao_esta_no_codigo(self):
        from pathlib import Path

        fonte = (Path(__file__).resolve().parent / "views.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("SUA_CHAVE_DE_SEGURANCA_ENTRE_APPS", fonte)


class RotasDoCarrinhoTests(TestCase):
    """Gravações do carrinho exigem login -- e CSRF.

    `calcular_frete` era isenta de CSRF e gravava o endereço de entrega no
    carrinho de quem estivesse logado: bastava uma página aberta noutra
    aba para trocar o endereço sem o cliente saber.
    """

    def setUp(self):
        cache.clear()

    def test_frete_sem_login_nao_grava_nada(self):
        resposta = self.client.post(
            reverse("calcular_frete"),
            data='{"cep": "01001000"}',
            content_type="application/json",
        )

        self.assertIn(resposta.status_code, (302, 403))

    def test_frete_recusa_csrf_ausente(self):
        usuario = User.objects.create_user(
            username="cliente-frete", password="senha-longa-de-teste"
        )
        # Com o telefone em branco, o TelefoneObrigatorioMiddleware desvia
        # a requisição antes do CSRF e o teste mediria a coisa errada.
        ClientePerfil.objects.update_or_create(
            user=usuario, defaults={"telefone": "(11) 90000-0000"}
        )
        cliente = self.client_class(enforce_csrf_checks=True)
        cliente.force_login(usuario)

        resposta = cliente.post(
            reverse("calcular_frete"),
            data='{"cep": "01001000"}',
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 403)

    def test_cpf_do_carrinho_exige_login(self):
        resposta = self.client.post(
            reverse("salvar_cpf_carrinho"),
            data='{"cpf": "529.982.247-25"}',
            content_type="application/json",
        )

        self.assertIn(resposta.status_code, (302, 403))


@override_settings(ALLOWED_HOSTS=["testserver"])
class CabecalhosDeSegurancaTests(TestCase):
    """A resposta precisa dizer ao navegador o que ele pode carregar."""

    def test_a_pagina_sai_com_politica_de_conteudo(self):
        resposta = self.client.get("/healthz/")
        politica = resposta.headers.get("Content-Security-Policy", "")

        self.assertIn("default-src 'self'", politica)
        self.assertIn("object-src 'none'", politica)
        self.assertIn("frame-ancestors 'none'", politica)
        self.assertIn("form-action 'self'", politica)
        self.assertIn("base-uri 'self'", politica)

    def test_a_resposta_limita_o_que_o_site_pode_pedir_ao_aparelho(self):
        resposta = self.client.get("/healthz/")

        self.assertIn(
            "geolocation=()", resposta.headers.get("Permissions-Policy", "")
        )


@override_settings(ALLOWED_HOSTS=["testserver"])
class FreioDeTentativasTests(TestCase):
    """Senha errada em série passa a custar espera.

    Antes, o login do site, o do painel e o do /system/ aceitavam
    tentativas sem limite nenhum -- uma lista de senhas comuns rodando a
    noite inteira não encontrava obstáculo.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(
            username="alvo", password="senha-longa-de-teste"
        )

    def _errar(self, vezes):
        for _ in range(vezes):
            resposta = self.client.post(
                reverse("login"),
                {"username": "alvo", "password": "chute-errado"},
            )
        return resposta

    def test_depois_de_muitas_falhas_a_porta_fecha_por_um_tempo(self):
        from core import protecao_login

        resposta = self._errar(protecao_login.LIMITE_POR_CONTA + 1)

        self.assertEqual(resposta.status_code, 429)
        self.assertTrue(resposta.headers.get("Retry-After"))

    def test_a_senha_certa_ainda_entra_antes_do_limite(self):
        self._errar(2)

        resposta = self.client.post(
            reverse("login"),
            {"username": "alvo", "password": "senha-longa-de-teste"},
        )

        self.assertNotEqual(resposta.status_code, 429)

    def test_o_freio_vale_para_a_api_do_aplicativo(self):
        from core import protecao_login

        for _ in range(protecao_login.LIMITE_POR_ORIGEM + 1):
            resposta = self.client.post(
                "/api/v1/auth/login/",
                {"login": "alvo", "senha": "chute-errado"},
            )

        self.assertEqual(resposta.status_code, 429)


class SegredosForaDoRepositorioTests(TestCase):
    """Banco de desenvolvimento e .env não são conteúdo de código."""

    def test_o_gitignore_barra_banco_e_env(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent
        ignorados = (raiz / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".env", ignorados)
        self.assertIn("*.sqlite3", ignorados)


@override_settings(ALLOWED_HOSTS=["testserver"], MP_WEBHOOK_SECRET="segredo-mp")
class WebhookDoMercadoPagoTests(TestCase):
    """Notificação de pagamento forjada não custa nem uma consulta.

    Quem decide se um pagamento foi aprovado sempre foi a consulta que o
    servidor faz ao Mercado Pago com a nossa credencial -- forjar a
    mensagem nunca aprovou pedido nenhum. O que faltava era barrar o
    disparo em massa de avisos falsos, que nos fazia consultar a API de
    terceiros a pedido de qualquer um.
    """

    URL = "/api/webhook-mp/"
    CORPO = '{"type": "payment", "data": {"id": "123"}}'

    def test_sem_assinatura_a_notificacao_e_descartada(self):
        resposta = self.client.post(
            self.URL, data=self.CORPO, content_type="application/json"
        )

        self.assertEqual(resposta.status_code, 401)

    def test_assinatura_errada_tambem(self):
        resposta = self.client.post(
            self.URL,
            data=self.CORPO,
            content_type="application/json",
            HTTP_X_SIGNATURE="ts=1,v1=nao-e-o-hash",
            HTTP_X_REQUEST_ID="abc",
        )

        self.assertEqual(resposta.status_code, 401)

    @override_settings(MP_WEBHOOK_SECRET="")
    def test_sem_segredo_configurado_nada_muda(self):
        """Quem ainda não cadastrou a chave no painel do Mercado Pago
        continua recebendo notificação como antes -- a proteção, nesse
        caso, é a consulta que vem logo depois.

        A consulta é dublada aqui: o teste é sobre a porta, e sair para a
        internet no meio da suíte a deixaria lenta e instável.
        """
        with patch("core.views.mercadopago.SDK") as sdk:
            sdk.return_value.payment.return_value.get.return_value = {
                "response": {"status": "pending", "id": "123"}
            }
            resposta = self.client.post(
                self.URL, data=self.CORPO, content_type="application/json"
            )

        self.assertEqual(resposta.status_code, 200)
