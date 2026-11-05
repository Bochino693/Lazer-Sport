"""O que separa gente de robô no cadastro manual (/registrar/).

Três camadas, baratas e sem atrapalhar quem é gente:

1. CAMPO-ISCA. Um campo escondido por CSS que a pessoa não vê e não
   preenche; o robô que preenche tudo cai aqui.
2. TEMPO. O formulário leva um selo assinado com a hora em que foi
   aberto. Enviado em menos de CADASTRO_TEMPO_MINIMO segundos, é robô;
   velho demais (2 h), expirou e a página pede para recarregar.
3. O DESAFIO. Com as chaves do Cloudflare Turnstile no ambiente
   (TURNSTILE_SITE_KEY/SECRET_KEY, grátis), o site usa o Turnstile e
   confere o token no servidor. SEM as chaves, o site faz o próprio
   desafio: uma imagem com 5 letras e números torcidos, desenhada aqui
   (Pillow), cujo código vai assinado no selo (só o resumo, nunca o
   código). Não depende de ninguém de fora, não pede chave e barra os
   robôs comuns, que leem HTML e não imagem; um robô com leitura de
   imagem (OCR) passa -- para esses, o Turnstile é o caminho.

Nada disto vale para a API do aplicativo nem para o Google/Apple: ali o
freio é o limite de cadastros por IP (core/registro_cadastro.py).
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import random
import secrets
import time

from django.conf import settings
from django.core import signing

log = logging.getLogger(__name__)

CAMPO_ISCA = "site_web"          # o nome parece útil para o robô; a pessoa nunca vê
CAMPO_SELO = "selo_cadastro"
CAMPO_RESPOSTA = "resposta_humana"
CAMPO_TURNSTILE = "cf-turnstile-response"
SAL = "cadastro.captcha"
VALIDADE = 2 * 60 * 60           # 2 h para preencher
TURNSTILE_VERIFICACAO = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

#: Sem I, O, 0 e 1: ninguém precisa adivinhar se é letra ou número.
LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_DO_CODIGO = 5
LARGURA, ALTURA = 210, 70

MENSAGEM_ROBO = "Não conseguimos confirmar que o envio veio de uma pessoa. Tente de novo."
MENSAGEM_EXPIROU = "O formulário ficou aberto por muito tempo. Recarregue a página e tente de novo."
MENSAGEM_RAPIDO = "O envio foi rápido demais. Confira os dados e envie de novo."
MENSAGEM_PERGUNTA = "O código da imagem não está certo. Confira (ou peça outra imagem) e tente de novo."
MENSAGEM_TURNSTILE = "A verificação de segurança não passou. Marque a caixa \"Sou humano\" e tente de novo."


def turnstile_ativo() -> bool:
    return bool(getattr(settings, "TURNSTILE_SITE_KEY", "") and getattr(settings, "TURNSTILE_SECRET_KEY", ""))


def _assinatura(codigo: str) -> str:
    """O resumo do código, com a SECRET_KEY: o selo leva isto, nunca o código."""
    texto = (codigo or "").strip().upper().replace(" ", "")
    return hashlib.sha256(f"{settings.SECRET_KEY}:{SAL}:{texto}".encode("utf-8")).hexdigest()[:32]


def novo_desafio():
    """O que vai para a página: {"selo", "imagem"} (imagem vazia com o Turnstile)."""
    dados = {"t": int(time.time())}
    imagem = ""
    if not turnstile_ativo():
        codigo = "".join(secrets.choice(LETRAS) for _ in range(TAMANHO_DO_CODIGO))
        dados["h"] = _assinatura(codigo)
        imagem = desenhar(codigo)
    return {"selo": signing.dumps(dados, salt=SAL), "imagem": imagem}


def desenhar(codigo: str) -> str:
    """A imagem do código (PNG em data URI): letras torcidas e coloridas sobre o azul do site, com ruído."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    imagem = Image.new("RGB", (LARGURA, ALTURA), (11, 23, 48))
    tinta = ImageDraw.Draw(imagem)
    for _ in range(7):  # riscos
        tinta.line(
            [(random.randint(0, LARGURA), random.randint(0, ALTURA)), (random.randint(0, LARGURA), random.randint(0, ALTURA))],
            fill=(random.randint(30, 80), random.randint(90, 150), random.randint(150, 210)),
            width=random.choice((1, 2, 2, 3)),
        )
    for _ in range(140):  # pontos
        tom = random.randint(70, 130)
        tinta.point((random.randint(0, LARGURA - 1), random.randint(0, ALTURA - 1)), fill=(tom, tom, tom + 30))

    fonte = ImageFont.load_default(size=36)
    cores = ((63, 208, 255), (255, 210, 63), (255, 255, 255), (255, 122, 107), (34, 224, 122), (190, 160, 255))
    x = 12
    for letra in codigo:
        caixa = Image.new("RGBA", (50, 58), (0, 0, 0, 0))
        ImageDraw.Draw(caixa).text((7, 3), letra, font=fonte, fill=random.choice(cores) + (255,))
        caixa = caixa.rotate(random.uniform(-30, 30), resample=Image.BICUBIC)
        imagem.paste(caixa, (x, random.randint(0, 12)), caixa)
        x += random.randint(34, 40)
    imagem = imagem.filter(ImageFilter.SMOOTH)

    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(saida.getvalue()).decode("ascii")


def _resposta_numerica(texto):
    """Os selos antigos (a pergunta de conta) ainda valem até expirarem."""
    texto = (texto or "").strip().lower()
    por_extenso = {
        "tres": 3, "três": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
        "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
        "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    }
    if texto in por_extenso:
        return por_extenso[texto]
    try:
        return int(texto)
    except ValueError:
        return None


def verificar_turnstile(token, ip=None) -> bool:
    """Confere o token do Turnstile no Cloudflare. Sem resposta, é NÃO (fecha, não abre)."""
    import requests

    if not token:
        return False
    try:
        resposta = requests.post(
            TURNSTILE_VERIFICACAO,
            data={"secret": settings.TURNSTILE_SECRET_KEY, "response": token, "remoteip": ip or ""},
            timeout=5,
        )
        return bool(resposta.json().get("success"))
    except Exception as erro:  # noqa: BLE001
        log.warning("Turnstile não respondeu: %r", erro)
        return False


def conferir(dados, ip=None):
    """Mensagem de erro (str) se o envio parece de robô; None se passou.

    `dados` é o request.POST do formulário de cadastro.
    """
    if (dados.get(CAMPO_ISCA) or "").strip():
        return MENSAGEM_ROBO

    try:
        selo = signing.loads(dados.get(CAMPO_SELO) or "", salt=SAL, max_age=VALIDADE)
    except signing.SignatureExpired:
        return MENSAGEM_EXPIROU
    except signing.BadSignature:
        return MENSAGEM_ROBO

    minimo = getattr(settings, "CADASTRO_TEMPO_MINIMO", 4)
    if minimo and time.time() - float(selo.get("t", 0)) < minimo:
        return MENSAGEM_RAPIDO

    if turnstile_ativo():
        return None if verificar_turnstile(dados.get(CAMPO_TURNSTILE), ip) else MENSAGEM_TURNSTILE

    resposta = (dados.get(CAMPO_RESPOSTA) or "").strip()
    if "h" in selo:
        if not resposta or _assinatura(resposta) != selo["h"]:
            return MENSAGEM_PERGUNTA
        return None
    if "r" in selo:
        if _resposta_numerica(resposta) != int(selo["r"]):
            return MENSAGEM_PERGUNTA
        return None
    # selo feito com o Turnstile ligado e conferido com ele desligado: pede de novo
    return MENSAGEM_EXPIROU
