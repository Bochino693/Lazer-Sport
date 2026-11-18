"""Os e-mails em massa das campanhas (LEIA-ME seções 101 e 107).

O dono: "os emails em massa das campanhas não vão". A causa (seção 108): a
reserva de cada e-mail usava `select_for_update()` com um JOIN que o
PostgreSQL do site recusa ("FOR UPDATE cannot be applied to the nullable side
of an outer join"); o erro morria num log e a fila nunca andava. Os testes
rodam em SQLite, onde `select_for_update` não faz nada -- por isso passavam.

Daqui não sai e-mail de verdade: o provedor é simulado. `TransporteRoteirizado`
é o transporte por trás do MESMO decorador dos e-mails de pedido
(core.email_backend.EmailBackend), com um roteiro do que acontece em cada
envio (entrega, timeout, "421 try again later", endereço recusado...), e
`SMTPFalso` faz o papel do servidor para o backend SMTP de verdade do Django.
"""

import importlib
import inspect
import smtplib
import socket
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.apps import apps as registro_de_apps
from django.contrib.auth.models import User
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.email_branding import EmailComLogo
from core.email_utils import remetente
from core.models import Brinquedos, Promocoes

from . import campanhas, fila_de_emails
from .campanhas import criar_campanha, processar_emails_pendentes
from .models import (
    CampanhaDivulgacao,
    Cliente,
    DescadastroEmail,
    EntregaCampanha,
    EstadoFilaEmails,
)

INTERNO = {"HTTP_HOST": "interno.testserver"}
S = EntregaCampanha.Status


class TransporteRoteirizado(BaseEmailBackend):
    """O provedor simulado: cada envio consome um item do roteiro.

    `None` entrega (vai para mail.outbox); uma exceção é a recusa do provedor.
    Sem roteiro, entrega tudo. `aberturas` conta as conexões (logins).
    """

    roteiro = []
    aberturas = 0

    def open(self):
        type(self).aberturas += 1
        return True

    def close(self):
        pass

    def send_messages(self, mensagens):
        enviados = 0
        for mensagem in mensagens:
            efeito = type(self).roteiro.pop(0) if type(self).roteiro else None
            if efeito is not None:
                raise efeito
            mail.outbox.append(mensagem)
            enviados += 1
        return enviados


ROTEIRIZADO = {
    "EMAIL_BACKEND": "core.email_backend.EmailBackend",
    "EMAIL_TRANSPORT_BACKEND": "sistema_interno.tests_fila_de_emails.TransporteRoteirizado",
}


class SMTPFalso:
    """O servidor SMTP do outro lado, para o backend SMTP de verdade do Django."""

    instancias = []
    roteiro_login = []
    roteiro_envio = []

    def __init__(self, host, port, **parametros):
        type(self).instancias.append(self)
        self.logins = 0
        self.destinos = []

    def starttls(self, context=None):
        return (220, b"pronto")

    def login(self, usuario, senha):
        efeito = type(self).roteiro_login.pop(0) if type(self).roteiro_login else None
        if efeito is not None:
            raise efeito
        self.logins += 1

    def sendmail(self, de, para, mensagem):
        efeito = type(self).roteiro_envio.pop(0) if type(self).roteiro_envio else None
        if efeito is not None:
            raise efeito
        self.destinos.extend(para)
        return {}

    def quit(self):
        pass

    def close(self):
        pass


SMTP_DE_VERDADE = {
    "EMAIL_BACKEND": "core.email_backend.EmailBackend",
    "EMAIL_TRANSPORT_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": "smtp.provedor.test",
    "EMAIL_HOST_USER": "robo@lazersport.test",
    "EMAIL_HOST_PASSWORD": "senha-de-teste",
}


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"], SITE_URL="https://www.lazersport.com.br")
class BaseFila(TestCase):
    clientes = 3

    def setUp(self):
        TransporteRoteirizado.roteiro = []
        TransporteRoteirizado.aberturas = 0
        SMTPFalso.instancias = []
        SMTPFalso.roteiro_login = []
        SMTPFalso.roteiro_envio = []
        # as recusas simuladas viram aviso no log; aqui elas são o assunto, não ruído
        silencio = mock.patch.object(campanhas.log, "warning")
        silencio.start()
        self.addCleanup(silencio.stop)
        self.usuario = User.objects.create_superuser("campanhas", "equipe@example.com", "senha")
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Tobogã oceano", descricao="Tobogã inflável",
            valor_brinquedo=Decimal("5000.00"), avaliacao=Decimal("5.00"), voltz="110",
        )
        self.promocao = Promocoes.objects.create(
            descricao="Férias com diversão", brinquedos=brinquedo,
            preco_promocao=Decimal("4666.33"), ativo=True,
        )
        for i in range(self.clientes):
            Cliente.objects.create(
                nome_cliente=f"Buffet {i}", tipo=Cliente.Tipo.BUFFET, email=f"cliente{i}@example.com",
            )

    def criar(self):
        return criar_campanha(
            tipo=CampanhaDivulgacao.Tipo.PROMOCAO, objeto_id=self.promocao.pk,
            segmento=CampanhaDivulgacao.Segmento.TODOS, email=True, whatsapp=False,
            titulo="", mensagem="", usuario=self.usuario,
        )

    def estado(self):
        return EstadoFilaEmails.atual()

    def despausar(self):
        EstadoFilaEmails.objects.update(pausada_ate=timezone.now() - timedelta(seconds=1))

    def situacoes(self, campanha):
        return sorted(campanha.entregas.values_list("status", flat=True))


class FilaDeEmailsTests(BaseFila):
    def test_esvaziar_manda_toda_a_fila(self):
        campanha = self.criar()
        self.assertEqual(campanha.entregas.filter(status=S.PENDENTE).count(), 3)
        self.assertEqual(fila_de_emails.esvaziar(), 3)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(campanha.entregas.filter(status=S.ENVIADO).count(), 3)
        campanha.refresh_from_db()
        self.assertEqual(campanha.status, CampanhaDivulgacao.Status.CONCLUIDA)
        self.assertEqual(campanha.progresso_percentual, 100)

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
        with mock.patch("sistema_interno.campanhas.smtp_configurado", return_value=False):
            html = self.client.get(f"/site/campanhas/{campanha.token}/", **INTERNO).content.decode()
        self.assertIn("O e-mail do site não está configurado no servidor", html)
        self.assertIn("EMAIL_HOST_PASSWORD", html)
        html = self.client.get(f"/site/campanhas/{campanha.token}/", **INTERNO).content.decode()
        self.assertIn("3 e-mails na fila", html)
        self.assertIn('value="enviar_agora"', html)

    def test_enviar_agora_pelo_painel_tira_a_pausa(self):
        campanha = self.criar()
        EstadoFilaEmails.objects.update_or_create(
            chave=EstadoFilaEmails.CHAVE,
            defaults={"pausada_ate": timezone.now() + timedelta(minutes=30), "motivo_pausa": "421"},
        )
        self.client.force_login(self.usuario)
        with mock.patch("sistema_interno.fila_de_emails.disparar_agora") as disparar, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/site/campanhas/{campanha.token}/", {"acao": "enviar_agora"}, **INTERNO)
        disparar.assert_called_once()
        self.assertIsNone(self.estado().pausada_ate)

    def test_o_gunicorn_liga_a_ronda(self):
        from pathlib import Path
        from django.conf import settings

        conf = (Path(settings.BASE_DIR) / "gunicorn.conf.py").read_text(encoding="utf-8")
        self.assertIn("from sistema_interno.fila_de_emails import ligar", conf)


class CausaDoDefeitoTests(BaseFila):
    """A reserva que o PostgreSQL recusava."""

    def test_a_fila_nao_usa_select_for_update(self):
        """`select_for_update()` + `select_related("campanha__responsavel")` (chave que
        aceita vazio, LEFT OUTER JOIN) é recusado pelo PostgreSQL. O SQLite dos testes
        ignora `select_for_update`, então só ler o código pega a volta do defeito."""
        for funcao in (campanhas.processar_emails_pendentes, campanhas._reservar,
                       campanhas._recolocar_processamentos_abandonados):
            self.assertNotIn("select_for_update", inspect.getsource(funcao), funcao.__name__)

    def test_dois_processos_nao_pegam_o_mesmo_email(self):
        entrega = self.criar().entregas.first()
        agora = timezone.now()
        self.assertTrue(campanhas._reservar(entrega.pk, agora))
        self.assertFalse(campanhas._reservar(entrega.pk, agora))
        entrega.refresh_from_db()
        self.assertEqual((entrega.status, entrega.tentativas), (S.PROCESSANDO, 1))


@override_settings(**ROTEIRIZADO)
class RitmoDoEnvioTests(BaseFila):
    clientes = 5

    @override_settings(CAMPANHA_EMAIL_LOTE=2, CAMPANHA_EMAIL_PAUSA=1.5)
    def test_lote_pequeno_com_pausa_entre_um_email_e_outro(self):
        self.criar()
        with mock.patch("sistema_interno.campanhas.time.sleep") as dormir:
            self.assertEqual(processar_emails_pendentes(), 2)
        self.assertEqual(len(mail.outbox), 2)
        dormir.assert_called_once_with(1.5)
        self.assertEqual(TransporteRoteirizado.aberturas, 1)  # uma conexão para o lote

    @override_settings(CAMPANHA_EMAIL_LOTE=2, CAMPANHA_EMAIL_PAUSA_LOTE=7)
    def test_esvaziar_pausa_entre_os_lotes_ate_acabar(self):
        campanha = self.criar()
        with mock.patch("sistema_interno.fila_de_emails.time.sleep") as dormir:
            self.assertEqual(fila_de_emails.esvaziar(), 5)
        self.assertEqual(len(mail.outbox), 5)
        self.assertTrue(dormir.call_args_list)
        self.assertTrue(all(c.args == (7.0,) for c in dormir.call_args_list))
        self.assertEqual(TransporteRoteirizado.aberturas, 3)  # 2 + 2 + 1
        self.assertEqual(self.situacoes(campanha), [S.ENVIADO] * 5)

    @override_settings(CAMPANHA_EMAILS_POR_DIA=2)
    def test_teto_diario_para_e_continua_amanha(self):
        campanha = self.criar()
        self.assertEqual(fila_de_emails.esvaziar(), 2)
        self.assertEqual(len(mail.outbox), 2)
        estado = self.estado()
        self.assertEqual(estado.enviados_no_dia, 2)
        self.assertIn("CAMPANHA_EMAILS_POR_DIA", estado.motivo_pausa)
        self.assertGreater(estado.pausada_ate, timezone.now() + timedelta(minutes=1))
        self.assertEqual(processar_emails_pendentes(), 0)
        self.assertEqual(campanha.entregas.filter(status=S.PENDENTE).count(), 3)

    def test_cada_rodada_marca_a_hora_em_que_rodou(self):
        self.assertIsNone(self.estado().ultima_rodada_em)
        processar_emails_pendentes()
        self.assertIsNotNone(self.estado().ultima_rodada_em)


@override_settings(**ROTEIRIZADO)
class FalhasDoProvedorTests(BaseFila):
    def test_timeout_pausa_a_fila_inteira_e_ninguem_perde_tentativa(self):
        campanha = self.criar()
        TransporteRoteirizado.roteiro = [TimeoutError("timed out")]
        self.assertEqual(processar_emails_pendentes(), 1)
        self.assertEqual(len(mail.outbox), 0)
        estado = self.estado()
        self.assertEqual(estado.falhas_seguidas, 1)
        self.assertIn("timeout", estado.motivo_pausa)
        self.assertGreater(estado.pausada_ate, timezone.now())
        primeira = campanha.entregas.order_by("criacao", "id").first()
        self.assertEqual(primeira.status, S.PENDENTE)
        self.assertEqual(primeira.tentativas, 0)
        self.assertTrue(primeira.erro.startswith("Aguardando o provedor"))
        # pausada: não tenta, nem com o "Enviar agora" automático da ronda
        self.assertEqual(processar_emails_pendentes(), 0)
        # passou a pausa: sai tudo e o recado some
        self.despausar()
        self.assertEqual(fila_de_emails.esvaziar(), 3)
        self.assertEqual(len(mail.outbox), 3)
        estado = self.estado()
        self.assertEqual((estado.falhas_seguidas, estado.motivo_pausa), (0, ""))
        self.assertEqual(campanha.entregas.get(pk=primeira.pk).erro, "")

    def test_a_pausa_cresce_a_cada_recusa_seguida(self):
        self.criar()
        esperas = []
        for _ in range(3):
            TransporteRoteirizado.roteiro = [smtplib.SMTPServerDisconnected("Connection unexpectedly closed")]
            antes = timezone.now()
            processar_emails_pendentes()
            esperas.append((self.estado().pausada_ate - antes).total_seconds())
            self.despausar()
        self.assertLess(esperas[0], esperas[1])
        self.assertLess(esperas[1], esperas[2])
        self.assertLess(esperas[2], 5 * 60)  # 1, 2, 4 minutos (com folga)

    def test_421_try_again_later_e_limite_do_provedor(self):
        self.criar()
        TransporteRoteirizado.roteiro = [smtplib.SMTPDataError(421, b"4.7.0 Try again later, closing connection.")]
        processar_emails_pendentes()
        self.assertIn("421", self.estado().motivo_pausa)
        self.assertTrue(campanhas.fila_pausada())

    def test_cota_diaria_do_gmail_pausa_em_vez_de_queimar_a_lista(self):
        campanha = self.criar()
        TransporteRoteirizado.roteiro = [smtplib.SMTPDataError(550, b"5.4.5 Daily user sending quota exceeded.")]
        processar_emails_pendentes()
        self.assertTrue(campanhas.fila_pausada())
        self.assertEqual(campanha.entregas.filter(status=S.FALHOU).count(), 0)

    def test_endereco_recusado_falha_na_hora_e_o_resto_sai(self):
        campanha = self.criar()
        TransporteRoteirizado.roteiro = [
            smtplib.SMTPRecipientsRefused({"cliente0@example.com": (550, b"5.1.1 The email account does not exist")}),
        ]
        self.assertEqual(processar_emails_pendentes(), 3)
        falhou = campanha.entregas.get(status=S.FALHOU)
        self.assertIn("550", falhou.erro)
        self.assertIn("recusou este endereço", falhou.erro)
        self.assertEqual(len(mail.outbox), 2)
        self.assertFalse(campanhas.fila_pausada())
        campanha.refresh_from_db()
        self.assertEqual((campanha.status, campanha.total_falhas), (CampanhaDivulgacao.Status.PARCIAL, 1))

    @override_settings(CAMPANHA_EMAIL_TENTATIVAS=3)
    def test_recusa_temporaria_tenta_de_novo_com_espera_crescente(self):
        campanha = self.criar()
        alvo = campanha.entregas.order_by("criacao", "id").first()
        adiado = smtplib.SMTPRecipientsRefused({alvo.destino: (450, b"4.2.1 Mailbox busy, try later")})
        esperas = []
        for _ in range(2):
            TransporteRoteirizado.roteiro = [adiado]
            antes = timezone.now()
            processar_emails_pendentes()
            alvo.refresh_from_db()
            self.assertEqual(alvo.status, S.PENDENTE)
            esperas.append((alvo.proxima_tentativa_em - antes).total_seconds())
            EntregaCampanha.objects.filter(pk=alvo.pk).update(proxima_tentativa_em=timezone.now())
        self.assertLess(esperas[0], esperas[1])
        self.assertEqual(alvo.tentativas, 2)
        TransporteRoteirizado.roteiro = [adiado]
        processar_emails_pendentes()
        alvo.refresh_from_db()
        self.assertEqual(alvo.status, S.FALHOU)
        self.assertIn("Desistiu depois de 3 tentativas", alvo.erro)
        self.assertFalse(campanhas.fila_pausada())

    def test_login_recusado_diz_qual_variavel_conferir(self):
        self.criar()
        TransporteRoteirizado.roteiro = [smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")]
        processar_emails_pendentes()
        self.assertIn("EMAIL_HOST_PASSWORD", self.estado().motivo_pausa)

    def test_remetente_recusado_diz_que_e_o_dominio(self):
        self.criar()
        TransporteRoteirizado.roteiro = [
            smtplib.SMTPSenderRefused(553, b"5.7.1 Sender address rejected: not owned by user", "nao-responda@lazersport.com.br"),
        ]
        processar_emails_pendentes()
        self.assertIn("DEFAULT_FROM_EMAIL", self.estado().motivo_pausa)

    def test_erro_ao_montar_um_email_nao_trava_os_outros(self):
        campanha = self.criar()
        original = campanhas.montar_email
        chamadas = []

        def montar(entrega):
            chamadas.append(entrega.pk)
            if len(chamadas) == 1:
                raise ValueError("template quebrado")
            return original(entrega)

        with mock.patch("sistema_interno.campanhas.montar_email", side_effect=montar), \
                self.assertLogs("sistema_interno.campanhas", level="ERROR"):
            self.assertEqual(processar_emails_pendentes(), 3)
        self.assertEqual(len(mail.outbox), 2)
        problema = campanha.entregas.get(pk=chamadas[0])
        self.assertEqual(problema.status, S.PENDENTE)
        self.assertIn("template quebrado", problema.erro)
        self.assertIsNotNone(problema.proxima_tentativa_em)


@override_settings(**SMTP_DE_VERDADE)
class BackendSMTPDeVerdadeTests(BaseFila):
    """O backend SMTP do Django, com o servidor do outro lado simulado."""

    def test_um_login_por_lote_e_nao_um_por_email(self):
        self.criar()
        with mock.patch("django.core.mail.backends.smtp.smtplib.SMTP", SMTPFalso):
            self.assertEqual(processar_emails_pendentes(), 3)
        self.assertEqual(len(SMTPFalso.instancias), 1)
        self.assertEqual(SMTPFalso.instancias[0].logins, 1)
        self.assertEqual(len(SMTPFalso.instancias[0].destinos), 3)

    def test_timeout_no_login_pausa_a_fila(self):
        campanha = self.criar()
        SMTPFalso.roteiro_login = [socket.timeout("timed out")]
        with mock.patch("django.core.mail.backends.smtp.smtplib.SMTP", SMTPFalso):
            self.assertEqual(processar_emails_pendentes(), 1)
        self.assertTrue(campanhas.fila_pausada())
        self.assertIn("timeout", self.estado().motivo_pausa)
        self.assertEqual(campanha.entregas.filter(status=S.PENDENTE, tentativas=0).count(), 3)

    def test_conexao_que_cai_no_meio_e_trocada_por_uma_nova(self):
        campanha = self.criar()
        SMTPFalso.roteiro_envio = [None, smtplib.SMTPServerDisconnected("Server not connected")]
        with mock.patch("django.core.mail.backends.smtp.smtplib.SMTP", SMTPFalso):
            processar_emails_pendentes()
            self.assertEqual(campanha.entregas.filter(status=S.ENVIADO).count(), 1)
            self.despausar()
            processar_emails_pendentes()
        self.assertEqual(campanha.entregas.filter(status=S.ENVIADO).count(), 3)
        self.assertEqual(len(SMTPFalso.instancias), 2)  # a quebrada foi descartada

    @override_settings(EMAIL_HOST_PASSWORD="")
    def test_sem_senha_nada_sai_e_o_painel_explica(self):
        self.criar()
        with mock.patch("django.core.mail.backends.smtp.smtplib.SMTP", SMTPFalso):
            self.assertEqual(processar_emails_pendentes(), 0)
        self.assertEqual(SMTPFalso.instancias, [])
        self.assertFalse(campanhas.estado_da_fila()["smtp_ok"])


class RetomadaTests(BaseFila):
    def test_o_que_um_processo_largou_no_meio_volta_e_sai(self):
        campanha = self.criar()
        preso = campanha.entregas.first()
        EntregaCampanha.objects.filter(pk=preso.pk).update(
            status=S.PROCESSANDO, tentativas=1,
            processando_desde=timezone.now() - timedelta(minutes=10),
        )
        self.assertEqual(processar_emails_pendentes(), 3)
        preso.refresh_from_db()
        self.assertEqual(preso.status, S.ENVIADO)
        self.assertEqual(len(mail.outbox), 3)

    def test_o_que_esta_saindo_agora_nao_sai_duas_vezes(self):
        campanha = self.criar()
        saindo = campanha.entregas.first()
        EntregaCampanha.objects.filter(pk=saindo.pk).update(
            status=S.PROCESSANDO, processando_desde=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(processar_emails_pendentes(), 2)
        saindo.refresh_from_db()
        self.assertEqual(saindo.status, S.PROCESSANDO)
        campanha.refresh_from_db()
        self.assertEqual(campanha.status, CampanhaDivulgacao.Status.EM_ANDAMENTO)

    def test_erro_da_rodada_vai_para_o_painel_e_a_ronda_nao_morre(self):
        with mock.patch(
            "sistema_interno.campanhas.processar_emails_pendentes",
            side_effect=RuntimeError("banco fora do ar"),
        ), self.assertLogs("sistema_interno.fila_de_emails", level="ERROR"):
            self.assertEqual(fila_de_emails.esvaziar(), 0)
            fila_de_emails._uma_volta()  # não levanta
        self.assertIn("banco fora do ar", self.estado().ultimo_erro)
        with mock.patch("sistema_interno.fila_de_emails.esvaziar", side_effect=RuntimeError("pior ainda")), \
                self.assertLogs("sistema_interno.fila_de_emails", level="ERROR"):
            fila_de_emails._uma_volta()  # também não


class MesmoCaminhoDosEmailsDePedidoTests(BaseFila):
    @override_settings(
        EMAIL_BACKEND="core.email_backend.EmailBackend",
        EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_mesmo_backend_e_mesmo_remetente(self):
        self.criar()
        processar_emails_pendentes()
        mensagem = mail.outbox[0]
        self.assertIsInstance(mensagem, EmailComLogo)  # passou pelo decorador dos e-mails de pedido
        self.assertEqual(mensagem.from_email, remetente())
        self.assertIn("equipe@example.com", mensagem.reply_to)


class DescadastroTests(BaseFila):
    def enviar_um(self):
        campanha = self.criar()
        processar_emails_pendentes()
        return campanha, campanha.entregas.order_by("criacao", "id").first()

    def test_o_email_traz_o_link_e_o_descadastro_de_um_clique(self):
        _campanha, entrega = self.enviar_um()
        url = campanhas.url_descadastro(entrega)
        self.assertTrue(url.startswith("https://www.lazersport.com.br/divulgacao/sair/"))
        mensagem = next(m for m in mail.outbox if m.to == [entrega.destino])
        self.assertIn(f"<{url}>", mensagem.extra_headers["List-Unsubscribe"])
        self.assertEqual(mensagem.extra_headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertIn(url, mensagem.body)
        self.assertIn(url, mensagem.alternatives[0][0])
        self.assertIn("Lazer & Sport", mensagem.body)  # texto puro sem "&amp;"

    def test_o_link_so_pergunta_e_o_botao_descadastra(self):
        _campanha, entrega = self.enviar_um()
        caminho = f"/divulgacao/sair/{entrega.token}/"
        pagina = self.client.get(caminho)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Não quero mais receber")
        self.assertNotContains(pagina, entrega.destino)  # o endereço aparece mascarado
        self.assertFalse(DescadastroEmail.objects.exists())
        feito = self.client.post(caminho)
        self.assertContains(feito, "você saiu da lista")
        registro = DescadastroEmail.objects.get()
        self.assertEqual((registro.email, registro.origem), (entrega.destino, DescadastroEmail.Origem.LINK))
        self.client.post(caminho)  # de novo: nada muda
        self.assertEqual(DescadastroEmail.objects.count(), 1)

    def test_o_botao_do_gmail_funciona_sem_csrf(self):
        _campanha, entrega = self.enviar_um()
        resposta = Client(enforce_csrf_checks=True).post(
            f"/divulgacao/sair/{entrega.token}/", {"List-Unsubscribe": "One-Click"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(DescadastroEmail.objects.get().origem, DescadastroEmail.Origem.UM_CLIQUE)

    def test_quem_saiu_nao_recebe_o_pendente_nem_entra_na_proxima(self):
        primeira = self.criar()
        entrega = primeira.entregas.order_by("criacao", "id").first()
        self.client.post(f"/divulgacao/sair/{entrega.token}/")
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, S.IGNORADO)
        processar_emails_pendentes()
        self.assertNotIn([entrega.destino], [m.to for m in mail.outbox])
        segunda = self.criar()
        self.assertNotIn(entrega.destino, segunda.entregas.values_list("destino", flat=True))
        self.assertEqual(segunda.entregas.count(), 2)

    def test_descadastro_que_chega_depois_barra_na_hora_do_envio(self):
        campanha = self.criar()
        alvo = campanha.entregas.first()
        DescadastroEmail.objects.create(email=alvo.destino)
        processar_emails_pendentes()
        alvo.refresh_from_db()
        self.assertEqual(alvo.status, S.IGNORADO)
        self.assertEqual(len(mail.outbox), 2)
        campanha.refresh_from_db()
        self.assertEqual((campanha.status, campanha.total_ignorados), (CampanhaDivulgacao.Status.CONCLUIDA, 1))


class OfertaEncerradaTests(BaseFila):
    def test_promocao_desligada_no_meio_nao_sai(self):
        campanha = self.criar()
        Promocoes.objects.filter(pk=self.promocao.pk).update(ativo=False)
        processar_emails_pendentes()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.situacoes(campanha), [S.IGNORADO] * 3)
        self.assertIn("A oferta foi desativada ou venceu", campanha.entregas.first().erro)


class PainelDaCampanhaTests(BaseFila):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def falhar_um(self):
        campanha = self.criar()
        TransporteRoteirizado.roteiro = [
            smtplib.SMTPRecipientsRefused({"x": (550, b"5.1.1 user unknown")}),
        ]
        with override_settings(**ROTEIRIZADO):
            processar_emails_pendentes()
        return campanha

    def test_progresso_real_em_json(self):
        campanha = self.falhar_um()
        dados = self.client.get(f"/site/campanhas/{campanha.token}/", {"formato": "json"}, **INTERNO).json()
        self.assertEqual(dados["campanha"]["enviados"], 2)
        self.assertEqual(dados["campanha"]["falhas"], 1)
        self.assertEqual(dados["campanha"]["percentual"], 100)
        self.assertEqual(dados["emails"]["pendentes"], 0)
        self.assertEqual(dados["motivos"][0]["quantidade"], 1)
        self.assertIn("550", dados["motivos"][0]["motivo"])
        self.assertEqual(len(dados["entregas"]), 3)
        self.assertEqual(sorted(e["status"] for e in dados["entregas"]), [S.ENVIADO, S.ENVIADO, S.FALHOU])

    def test_a_tela_mostra_o_motivo_e_o_botao_reenviar_falhas(self):
        campanha = self.falhar_um()
        html = self.client.get(f"/site/campanhas/{campanha.token}/", **INTERNO).content.decode()
        self.assertIn("Reenviar falhas", html)
        self.assertIn("Por que não saíram", html)
        self.assertIn("5.1.1 user unknown", html)
        self.assertIn("data-ls-confirmar", html)
        # as regras do painel: chips e não <select>, a folha do LSAviso e não confirm()/alert()
        from pathlib import Path

        fonte = (Path(__file__).resolve().parent / "templates" / "campanha_detalhe_inner.html").read_text(encoding="utf-8")
        for proibido in ("<select", "confirm(", "alert("):
            self.assertNotIn(proibido, fonte)

    def test_reenviar_falhas_volta_para_a_fila_e_dispara(self):
        campanha = self.falhar_um()
        EstadoFilaEmails.objects.update(pausada_ate=timezone.now() + timedelta(minutes=20), motivo_pausa="x")
        with mock.patch("sistema_interno.fila_de_emails.disparar_agora") as disparar, \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/site/campanhas/{campanha.token}/", {"acao": "reenviar_falhas"}, **INTERNO)
        disparar.assert_called_once()
        voltou = campanha.entregas.get(status=S.PENDENTE)
        self.assertEqual((voltou.tentativas, voltou.erro), (0, ""))
        self.assertFalse(campanhas.fila_pausada())
        processar_emails_pendentes()
        self.assertEqual(campanha.entregas.filter(status=S.ENVIADO).count(), 3)

    def test_quem_se_descadastrou_nao_volta_no_reenvio(self):
        campanha = self.falhar_um()
        falhou = campanha.entregas.get(status=S.FALHOU)
        DescadastroEmail.objects.create(email=falhou.destino)
        self.client.post(f"/site/campanhas/{campanha.token}/", {"acao": "reenviar_falhas"}, **INTERNO)
        falhou.refresh_from_db()
        self.assertEqual(falhou.status, S.FALHOU)

    def test_cancelar_nao_deixa_nada_sair(self):
        campanha = self.criar()
        self.client.post(f"/site/campanhas/{campanha.token}/", {"acao": "cancelar"}, **INTERNO)
        self.assertEqual(processar_emails_pendentes(), 0)
        self.assertEqual(self.situacoes(campanha), [S.IGNORADO] * 3)
        campanha.refresh_from_db()
        self.assertEqual(campanha.progresso_percentual, 100)

    def test_a_lista_mostra_falhas_e_a_pausa_do_provedor(self):
        self.falhar_um()
        EstadoFilaEmails.objects.update(
            pausada_ate=timezone.now() + timedelta(minutes=20),
            motivo_pausa="O provedor pediu para esperar (421 Try again later).",
        )
        html = self.client.get("/site/campanhas/", **INTERNO).content.decode()
        self.assertIn("1 falha", html)
        self.assertIn("Envio de e-mails pausado", html)
        self.assertIn("421 Try again later", html)


class MigracaoDaFilaAntigaTests(BaseFila):
    def test_retem_o_antigo_e_deixa_o_recente_sair(self):
        antiga = self.criar()
        nova = self.criar()
        CampanhaDivulgacao.objects.filter(pk=antiga.pk).update(criacao=timezone.now() - timedelta(days=10))
        migracao = importlib.import_module("sistema_interno.migrations.0069_fila_emails_campanhas_dados")
        migracao.preparar_fila(registro_de_apps, None)
        self.assertEqual(self.situacoes(antiga), [S.FALHOU] * 3)
        self.assertEqual(antiga.entregas.first().erro, migracao.MOTIVO_RETIDO)
        self.assertEqual(self.situacoes(nova), [S.PENDENTE] * 3)
        antiga.refresh_from_db()
        self.assertEqual((antiga.status, antiga.total_falhas), (CampanhaDivulgacao.Status.FALHA, 3))
        migracao.preparar_fila(registro_de_apps, None)  # de novo: nada muda
        self.assertEqual(self.situacoes(nova), [S.PENDENTE] * 3)
