from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from core.models import Brinquedos, Cupom, Promocoes

from .campanhas import ErroCampanha, criar_campanha, processar_emails_pendentes
from .models import CampanhaDivulgacao, Cliente, EntregaCampanha


@override_settings(
    ALLOWED_HOSTS=["interno.testserver", "testserver"],
    SITE_URL="https://www.lazersport.com.br",
)
class CampanhasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser(
            username="campanhas", password="senha", email="equipe@example.com"
        )
        self.client.force_login(self.usuario)
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Tobogã oceano",
            descricao="Tobogã inflável",
            valor_brinquedo=Decimal("5000.00"),
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        self.promocao = Promocoes.objects.create(
            descricao="Férias com diversão",
            brinquedos=self.brinquedo,
            preco_promocao=Decimal("4666.33"),
            ativo=True,
        )
        self.cliente = Cliente.objects.create(
            nome_cliente="Buffet Azul",
            tipo=Cliente.Tipo.BUFFET,
            email="cliente@example.com",
            telefone="(11) 99999-1122",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
        )

    def criar(self, **extras):
        dados = {
            "tipo": CampanhaDivulgacao.Tipo.PROMOCAO,
            "objeto_id": self.promocao.pk,
            "segmento": CampanhaDivulgacao.Segmento.TODOS,
            "email": True,
            "whatsapp": True,
            "titulo": "",
            "mensagem": "",
            "usuario": self.usuario,
        }
        dados.update(extras)
        return criar_campanha(**dados)

    def test_fila_deduplica_e_so_usa_whatsapp_confirmado(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cliente.objects.create(
                nome_cliente="Cadastro repetido",
                email="CLIENTE@example.com",
                telefone="(11) 98888-0000",
                canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
            )
        campanha = self.criar()

        self.assertEqual(
            campanha.entregas.filter(canal=EntregaCampanha.Canal.EMAIL).count(), 1
        )
        self.assertEqual(
            campanha.entregas.filter(canal=EntregaCampanha.Canal.WHATSAPP).count(), 1
        )
        whatsapp = campanha.entregas.get(canal=EntregaCampanha.Canal.WHATSAPP)
        self.assertEqual(whatsapp.status, EntregaCampanha.Status.AGUARDANDO_ACAO)
        self.assertEqual(whatsapp.destino, "5511999991122")

    def test_processador_de_email_e_idempotente(self):
        campanha = self.criar(whatsapp=False)
        self.assertEqual(processar_emails_pendentes(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(processar_emails_pendentes(), 0)
        self.assertEqual(len(mail.outbox), 1)
        entrega = campanha.entregas.get()
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, EntregaCampanha.Status.ENVIADO)
        campanha.refresh_from_db()
        self.assertEqual(campanha.status, CampanhaDivulgacao.Status.CONCLUIDA)

    def test_endpoint_cria_e_publico_nao_expoe_pk_do_objeto(self):
        resposta = self.client.post(
            "/site/campanhas/criar/",
            {
                "tipo": "promocao",
                "objeto": self.promocao.pk,
                "segmento": "todos",
                "email": "1",
                "whatsapp": "1",
                "titulo": "Oferta segura",
                "mensagem": "Uma condição especial preparada para você.",
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 201)
        campanha = CampanhaDivulgacao.objects.get(titulo="Oferta segura")
        pagina = self.client.get(f"/divulgacao/{campanha.token}/", HTTP_HOST="testserver")
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, f"/promocao/{self.promocao.pk}")
        self.assertNotContains(pagina, f'data-objeto="{self.promocao.pk}"')

    def test_card_oferece_divulgacao_e_previa_conta_canais(self):
        pagina = self.client.get("/site/promocoes/", HTTP_HOST="interno.testserver")
        self.assertContains(pagina, 'data-campanha-tipo="promocao"')
        previa = self.client.get(
            "/site/campanhas/preparar/",
            {"tipo": "promocao", "objeto": self.promocao.pk, "segmento": "todos", "email": 1, "whatsapp": 1},
            HTTP_HOST="interno.testserver",
        )
        self.assertEqual(previa.status_code, 200)
        self.assertEqual(previa.json()["email"], 1)
        self.assertEqual(previa.json()["whatsapp"], 1)

    def test_cupom_exclusivo_nao_vira_disparo_amplo(self):
        cupom = Cupom.objects.create(
            codigo="PRIVADO10",
            desconto_percentual=Decimal("10.00"),
            todos_usuarios=False,
            ativo=True,
        )
        with self.assertRaisesMessage(ErroCampanha, "exclusivo"):
            criar_campanha(
                tipo=CampanhaDivulgacao.Tipo.CUPOM,
                objeto_id=cupom.pk,
                segmento=CampanhaDivulgacao.Segmento.TODOS,
                email=True,
                whatsapp=False,
                titulo="",
                mensagem="",
                usuario=self.usuario,
            )

    def test_whatsapp_e_marcado_quando_conversa_e_aberta(self):
        campanha = self.criar(email=False)
        entrega = campanha.entregas.get()
        lista = self.client.get("/site/campanhas/", HTTP_HOST="interno.testserver")
        detalhe = self.client.get(
            f"/site/campanhas/{campanha.token}/", HTTP_HOST="interno.testserver"
        )
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, "WhatsApp assistido")
        resposta = self.client.post(
            f"/site/campanhas/{campanha.token}/whatsapp/{entrega.token}/",
            HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("https://wa.me/5511999991122"))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, EntregaCampanha.Status.ENVIADO)
