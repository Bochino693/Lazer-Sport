from unittest.mock import patch
from email import policy
from email.parser import BytesParser

from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection, send_mail
from django.test import SimpleTestCase, override_settings

from .email_branding import CID_LOGO, aplicar_logo, logo_email
from .email_utils import smtp_configurado


@override_settings(EMAIL_BACKEND="core.email_backend.EmailBackend", EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class IdentidadeEmailTests(SimpleTestCase):
    def test_texto_simples_ganha_html_logo_e_links_sem_alterar_original(self):
        original = EmailMessage("Aviso", 'Olá <cliente>\nhttps://example.com/confirmar/?token=seguro', "site@example.com", ["cliente@example.com"])
        self.assertEqual(original.send(), 1)
        enviado = mail.outbox[-1]
        self.assertEqual(enviado.body, original.body)
        html = enviado.alternatives[0].content
        self.assertIn('cid:' + CID_LOGO, html)
        self.assertIn('&lt;cliente&gt;', html)
        self.assertIn('href="https://example.com/confirmar/?token=seguro"', html)
        self.assertFalse(hasattr(original, 'alternatives'))

    def test_html_anexos_destinatarios_e_resposta_preservados(self):
        original = EmailMultiAlternatives("Orçamento", "Texto", "de@example.com", ["para@example.com"], cc=["cc@example.com"], bcc=["bcc@example.com"], reply_to=["vendedor@example.com"], headers={"X-Teste": "ok"})
        original.attach_alternative('<html><body><a href="https://example.com/aceite?token=abc">Aceitar</a></body></html>', "text/html")
        original.attach("orcamento.pdf", b"%PDF-teste", "application/pdf")
        original.send()
        enviado = mail.outbox[-1]
        for nome in ("subject", "body", "from_email", "to", "cc", "bcc", "reply_to", "extra_headers", "attachments"):
            self.assertEqual(getattr(enviado, nome), getattr(original, nome))
        html = enviado.alternatives[0].content
        self.assertIn('href="https://example.com/aceite?token=abc"', html)
        self.assertEqual(html.count('data-ls-email-brand="1"'), 1)
        self.assertLess(html.index('<body>'), html.index('data-ls-email-brand'))
        mime = BytesParser(policy=policy.default).parsebytes(enviado.message().as_bytes())
        self.assertEqual(mime.get_content_type(), "multipart/mixed")
        imagens = [p for p in mime.walk() if p.get_content_type() == "image/png"]
        self.assertEqual(len(imagens), 1)
        self.assertEqual(imagens[0]['Content-ID'], f'<{CID_LOGO}>')
        self.assertEqual(imagens[0].get_content_disposition(), 'inline')
        self.assertEqual(imagens[0].get_payload(decode=True), logo_email())
        self.assertTrue(any(p.get_content_type() == 'multipart/related' for p in mime.walk()))
        self.assertTrue(any(p.get_filename() == 'orcamento.pdf' for p in mime.walk()))

    def test_reenvio_nao_duplica_logo(self):
        original = EmailMessage("Aviso", "Texto", "de@example.com", ["para@example.com"])
        with get_connection() as conexao:
            self.assertEqual(conexao.send_messages([original, original]), 2)
        for enviado in mail.outbox:
            self.assertEqual(enviado.alternatives[0].content.count('data-ls-email-brand="1"'), 1)
            self.assertIs(aplicar_logo(enviado), enviado)

    def test_send_mail_padrao_tambem_recebe_logo(self):
        send_mail("Teste", "Mensagem automática", "de@example.com", ["para@example.com"])
        self.assertIn('cid:' + CID_LOGO, mail.outbox[-1].alternatives[0].content)

    def test_html_no_corpo_e_outros_formatos_preservados(self):
        original = EmailMultiAlternatives("Teste", "Texto", "de@example.com", ["para@example.com"])
        original.attach_alternative("BEGIN:VCALENDAR\nEND:VCALENDAR", "text/calendar")
        novo = aplicar_logo(original)
        self.assertIn(("BEGIN:VCALENDAR\nEND:VCALENDAR", "text/calendar"), novo.alternatives)
        html = EmailMessage("Teste", '<p>Texto <strong>original</strong></p>')
        html.content_subtype = 'html'
        novo = aplicar_logo(html)
        self.assertEqual(novo.body, 'Texto original')
        self.assertIn('<strong>original</strong>', novo.alternatives[0].content)

    def test_logo_invalida_nao_bloqueia_email_critico(self):
        with patch('core.email_branding.logo_email', side_effect=OSError('arquivo ausente')), self.assertLogs('core.email_branding', level='ERROR'):
            send_mail("Senha", "Link para recuperação", "de@example.com", ["para@example.com"])
        enviado = mail.outbox[-1]
        self.assertIn('Lazer &amp; Sport', enviado.alternatives[0].content)
        self.assertNotIn('src="cid:', enviado.alternatives[0].content)

    @override_settings(EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="")
    def test_checagem_smtp_continua_detectando_credencial_ausente(self):
        self.assertFalse(smtp_configurado())

    def test_logo_compacta(self):
        self.assertLess(len(logo_email()), 60 * 1024)
