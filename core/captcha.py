"""O que separa gente de robô no cadastro manual (/registrar/).

Três camadas, baratas e sem atrapalhar quem é gente:

1. CAMPO-ISCA. Um campo escondido por CSS que a pessoa não vê e não
   preenche; o robô que preenche tudo cai aqui.
2. TEMPO. O formulário leva um selo assinado com a hora em que foi
   aberto. Enviado em menos de CADASTRO_TEMPO_MINIMO segundos, é robô;
   velho demais (2 h), expirou e a página pede para recarregar.
3. O DESAFIO. Com as chaves do Cloudflare Turnstile no ambiente
   (TURNSTILE_SITE_KEY/SECRET_KEY, grátis), o site usa o Turnstile e
   confere o token no servidor. Sem as chaves, uma pergunta simples
   ("Quanto é 3 + 4?") cuja resposta vai assinada no mesmo selo: freia os
   robôs burros, que são a maioria; não freia um robô com cabeça, e o
   Turnstile é o caminho para isso.

Nada disto vale para a API do aplicativo nem para o Google/Apple: ali o
freio é o limite de cadastros por IP (core/registro_cadastro.py).
"""

from __future__ import annotations

import logging
import random
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

MENSAGEM_ROBO = "Não conseguimos confirmar que o envio veio de uma pessoa. Tente de novo."
MENSAGEM_EXPIROU = "O formulário ficou aberto por muito tempo. Recarregue a página e tente de novo."
MENSAGEM_RAPIDO = "O envio foi rápido demais. Confira os dados e envie de novo."
MENSAGEM_PERGUNTA = "A resposta da pergunta não está certa. Confira a conta e tente de novo."
MENSAGEM_TURNSTILE = "A verificação de segurança não passou. Marque a caixa \"Sou humano\" e tente de novo."


def turnstile_ativo() -> bool:
    return bool(getattr(settings, "TURNSTILE_SITE_KEY", "") and getattr(settings, "TURNSTILE_SECRET_KEY", ""))


def novo_desafio():
    """O que vai para a página: {"selo", "pergunta"} (pergunta vazia com o Turnstile)."""
    dados = {"t": int(time.time())}
    pergunta = ""
    if not turnstile_ativo():
        a, b = random.randint(2, 9), random.randint(1, 9)
        pergunta = f"{a} + {b}"
        dados["r"] = a + b
    return {"selo": signing.dumps(dados, salt=SAL), "pergunta": pergunta}


def _resposta_numerica(texto):
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

    if "r" not in selo:
        # selo feito com o Turnstile ligado e conferido com ele desligado: pede de novo
        return MENSAGEM_EXPIROU
    if _resposta_numerica(dados.get(CAMPO_RESPOSTA)) != int(selo["r"]):
        return MENSAGEM_PERGUNTA
    return None
