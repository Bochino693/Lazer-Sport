"""Marca única para e-mails, preservando texto, HTML, destinatários e anexos."""
from functools import lru_cache
from io import BytesIO
import logging
from email.mime.image import MIMEImage
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.core.mail.message import SafeMIMEMultipart
from django.utils.html import strip_tags, urlize
from PIL import Image, ImageOps

log = logging.getLogger(__name__)
CID_LOGO = "ls-logoofi@lazersport"


@lru_cache(maxsize=1)
def logo_email():
    """Deriva em memória um PNG pequeno; o original do static não é alterado."""
    caminho = finders.find("images/logoofi.png")
    if not caminho:
        caminho = Path(settings.BASE_DIR) / "core/static/images/logoofi.png"
    with Image.open(caminho) as origem:
        imagem = ImageOps.exif_transpose(origem).convert("RGBA")
        imagem.thumbnail((320, 240), Image.Resampling.LANCZOS)
        saida = BytesIO()
        imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


class EmailComLogo(EmailMultiAlternatives):
    def _create_message(self, msg):
        corpo = self._create_alternatives(msg)
        if self._logo_bytes:
            relacionado = SafeMIMEMultipart(_subtype="related", encoding=self.encoding or settings.DEFAULT_CHARSET)
            relacionado.attach(corpo)
            imagem = MIMEImage(self._logo_bytes, _subtype="png")
            imagem.add_header("Content-ID", f"<{CID_LOGO}>")
            imagem.add_header("Content-Disposition", "inline", filename="logoofi.png")
            relacionado.attach(imagem)
            corpo = relacionado
        # PDFs e outros anexos continuam fora do multipart/related da mensagem.
        return self._create_attachments(corpo)


def aplicar_logo(original):
    if isinstance(original, EmailComLogo):
        return original
    try:
        logo = logo_email()
    except (OSError, ValueError):
        # Uma imagem faltante não pode impedir recuperação de senha ou pedidos.
        log.exception("Logo logoofi.png indisponível; e-mail mantido com identificação textual.")
        logo = None
    marca = (
        f'<img src="cid:{CID_LOGO}" alt="Lazer &amp; Sport Brinquedos" width="160" '
        'style="display:block;width:160px;max-width:100%;height:auto;border:0;margin:0 auto">'
        if logo else '<strong style="color:#17213a">Lazer &amp; Sport Brinquedos</strong>'
    )
    cabecalho = (
        '<table data-ls-email-brand="1" role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="width:100%;background:#ffffff"><tr><td align="center" style="padding:18px 12px">'
        + marca + '</td></tr></table>'
    )

    def decorar(html):
        html = str(html)
        corpo = re.search(r"<body\b[^>]*>", html, flags=re.I)
        if corpo:
            return html[:corpo.end()] + cabecalho + html[corpo.end():]
        return cabecalho + html

    alternativas = list(getattr(original, "alternatives", []))
    texto = original.body
    if original.content_subtype == "html":
        alternativas.insert(0, (texto, "text/html"))
        texto = strip_tags(texto)
    if not any(tipo == "text/html" for _, tipo in alternativas):
        html = '<div style="max-width:600px;margin:0 auto;padding:20px;font-family:Arial,sans-serif;line-height:1.6;color:#17213a">' + str(urlize(texto, autoescape=True)).replace("\n", "<br>\n") + '</div>'
        alternativas.append((html, "text/html"))
    mensagem = EmailComLogo(
        subject=original.subject, body=texto, from_email=original.from_email,
        to=list(original.to), cc=list(original.cc), bcc=list(original.bcc),
        reply_to=list(original.reply_to), headers=dict(original.extra_headers),
        attachments=list(original.attachments),
        alternatives=[(decorar(conteudo) if tipo == "text/html" else conteudo, tipo) for conteudo, tipo in alternativas],
    )
    mensagem.encoding = original.encoding
    mensagem.mixed_subtype = original.mixed_subtype
    mensagem._logo_bytes = logo
    return mensagem
