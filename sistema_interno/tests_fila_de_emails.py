"""As campanhas mandam e-mail sem o worker (LEIA-ME seção 101, fila_de_emails.py)."""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from core.models import Brinquedos, Promocoes

from . import fila_de_emails
from .campanhas import criar_campanha
from .models import CampanhaDivulgacao, Cliente, EntregaCampanha

INTERNO = {"HTTP_HOST": "interno.testserver"}


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"], SITE_URL="https://www.lazersport.com.br")
class FilaDeEmailsTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser("campanhas", "equipe@example.com", "senha")
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Tobogã oceano", descricao="Tobogã inflável",
            valor_brinquedo=Decimal("5000.00"), avaliacao=Decimal("5.00"), voltz="110",
        )
        self.promocao = Promocoes.objects.create(
            descricao="Férias com diversão", brinquedos=brinquedo,
            preco_promocao=Decimal("4666.33"), ativo=True,
        )
        for i in range(3):
            Cliente.objects.create(
                nome_cliente=f"Buffet {i}", tipo=Cliente.Tipo.BUFFET, email=f"cliente{i}@example.com",
            )

    def criar(self):
        return criar_campanha(
            tipo=CampanhaDivulgacao.Tipo.PROMOCAO, objeto_id=self.promocao.pk,
            segmento=CampanhaDivulgacao.Segmento.TODOS, email=True, whatsapp=False,
            titulo="", mensagem="", usuario=self.usuario,
        )

    def test_esvaziar_manda_toda_a_fila(self):
        campanha = self.criar()
        self.assertEqual(campanha.entregas.filter(status=EntregaCampanha.Status.PENDENTE).count(), 3)
        with mock.patch("sistema_interno.fila_de_emails.time.sleep"):
            self.assertEqual(fila_de_emails.esvaziar(), 3)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(campanha.entregas.filter(status=EntregaCampanha.Status.ENVIADO).count(), 3)
        campanha.refresh_from_db()
        self.assertEqual(campanha.status, CampanhaDivulgacao.Status.CONCLUIDA)

    def test_criar_pelo_painel_dispara_na_hora(self):
        self.client.force_login(self.usuario)
        with mock.patch("sistema_interno.fila_de_emails.disparar_agora") as disparar, \
                self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post("/site/campanhas/criar/", {
                "tipo": "promocao", "objeto": self.promocao.pk, "segmento": "todos", "email": "1",
            }, **INTERNO)
        self.assertEqual(resposta.status_code, 201, resposta.content[:300])
        self.assertIn("já estão saindo", resposta.json()["msg"])
        disparar.assert_called_once()

    def test_o_painel_avisa_quando_o_smtp_falta(self):
        campanha = self.criar()
        self.client.force_login(self.usuario)
        with mock.patch("sistema_interno.views_campanhas.smtp_configurado", return_value=False):
            html = self.client.get(f"/site/campanhas/{campanha.token}/", **INTERNO).content.decode()
        self.assertIn("O e-mail do site não está configurado no servidor", html)
        self.assertIn("EMAIL_HOST_PASSWORD", html)
        html = self.client.get(f"/site/campanhas/{campanha.token}/", **INTERNO).content.decode()
        self.assertIn("3 e-mails na fila", html)
        self.assertIn('value="enviar_agora"', html)

    def test_enviar_agora_pelo_painel(self):
        campanha = self.criar()
        self.client.force_login(self.usuario)
        with mock.patch("sistema_interno.fila_de_emails.disparar_agora") as disparar, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/site/campanhas/{campanha.token}/", {"acao": "enviar_agora"}, **INTERNO)
        disparar.assert_called_once()

    def test_o_gunicorn_liga_a_ronda(self):
        from pathlib import Path
        from django.conf import settings

        conf = (Path(settings.BASE_DIR) / "gunicorn.conf.py").read_text(encoding="utf-8")
        self.assertIn("from sistema_interno.fila_de_emails import ligar", conf)
