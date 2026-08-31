"""Pix Copia e Cola e QR Code para documentos aprovados.

O payload segue o BR Code do Banco Central. Não cria cobrança no banco e
não marca nada como pago sozinho: ele só facilita o pagamento com chave,
valor e referência já preenchidos. A confirmação continua sendo uma ação
consciente da equipe, porque transferência fora do checkout não possui
webhook confiável neste sistema.
"""

import base64
import io
import logging
import re
import unicodedata
from decimal import Decimal
from functools import lru_cache

import qrcode
from django.conf import settings


def _campo(codigo, valor):
    valor = str(valor or "")
    return f"{codigo}{len(valor):02d}{valor}"


def _texto_pix(valor, limite):
    normalizado = unicodedata.normalize("NFKD", str(valor or ""))
    ascii_texto = normalizado.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9 ]", "", ascii_texto).upper().strip()[:limite]


def _crc16(conteudo):
    crc = 0xFFFF
    for byte in conteudo.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def gerar_payload(*, valor, referencia):
    chave = getattr(settings, "PIX_CHAVE", "").strip()
    if not chave:
        return ""

    recebedor = _texto_pix(getattr(settings, "PIX_RECEBEDOR", ""), 25)
    cidade = _texto_pix(getattr(settings, "PIX_CIDADE", ""), 15)
    referencia = _texto_pix(referencia, 25) or "***"
    valor = Decimal(valor or 0).quantize(Decimal("0.01"))

    conta = _campo("00", "BR.GOV.BCB.PIX") + _campo("01", chave)
    payload = "".join([
        _campo("00", "01"),
        _campo("26", conta),
        _campo("52", "0000"),
        _campo("53", "986"),
        _campo("54", f"{valor:.2f}") if valor > 0 else "",
        _campo("58", "BR"),
        _campo("59", recebedor),
        _campo("60", cidade),
        _campo("62", _campo("05", referencia)),
        "6304",
    ])
    return payload + _crc16(payload)


@lru_cache(maxsize=128)
def _qr_base64(payload):
    """O mesmo documento não redesenha a mesma imagem a cada prévia."""
    imagem = qrcode.make(payload)
    arquivo = io.BytesIO()
    imagem.save(arquivo, format="PNG")
    return base64.b64encode(arquivo.getvalue()).decode("ascii")


def dados_pix(documento):
    """Retorna payload e imagem pronta para um orçamento ou uma O.S."""
    valor = getattr(documento, "saldo_pagamento", Decimal("0.00"))
    referencia = getattr(documento, "numero_documento", str(documento.pk))
    try:
        payload = gerar_payload(valor=valor, referencia=referencia)
    except Exception:
        logging.getLogger(__name__).exception(
            "Falha ao montar payload Pix do documento %s", referencia,
        )
        payload = ""
    if not payload:
        return {"pix_configurado": False, "pix_copia_cola": "", "pix_qr": ""}

    try:
        qr = _qr_base64(payload)
    except Exception:
        # O QR ajuda, mas nunca pode transformar uma prévia inteira em 500
        # (que o proxy apresenta para a equipe como Bad Gateway).
        logging.getLogger(__name__).exception(
            "Falha ao gerar QR Pix do documento %s", referencia,
        )
        return {"pix_configurado": False, "pix_copia_cola": "", "pix_qr": ""}
    return {
        "pix_configurado": True,
        "pix_copia_cola": payload,
        "pix_qr": f"data:image/png;base64,{qr}",
    }
