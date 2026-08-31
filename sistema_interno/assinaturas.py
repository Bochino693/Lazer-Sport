"""Aceite eletrônico com trilha de auditoria e mínimo de dados pessoais."""

from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings

from core.email_utils import cnpj_empresa, nome_empresa

from .models import AceiteOrcamento
from .validacoes import chave_documento, mascarar_documento


TERMOS_VERSAO = "2026-08"


def _dinheiro(valor) -> str:
    return f"{valor:.2f}"


def conteudo_canonico(orcamento) -> dict:
    """Retrato comercial assinado, sem PK, token ou outro ID interno."""
    return {
        "empresa": nome_empresa(),
        "empresa_cnpj": cnpj_empresa(),
        "numero": orcamento.numero_documento,
        "versao": orcamento.versao,
        "cliente": orcamento.destinatario,
        "validade": orcamento.validade.isoformat() if orcamento.validade else "",
        "forma_pagamento": orcamento.forma_pagamento or "",
        "forma_envio": orcamento.forma_envio or "",
        "observacoes": orcamento.observacoes or "",
        "subtotal": _dinheiro(orcamento.subtotal),
        "desconto": _dinheiro(orcamento.desconto),
        "frete": _dinheiro(orcamento.frete),
        "total": _dinheiro(orcamento.total),
        "itens": [
            {
                "descricao": item.descricao,
                "quantidade": str(item.quantidade),
                "valor_unitario": _dinheiro(item.valor_unitario),
                "subtotal": _dinheiro(item.subtotal),
            }
            for item in orcamento.itens.all()
        ],
    }


def hash_proposta(orcamento) -> str:
    serializado = json.dumps(
        conteudo_canonico(orcamento),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serializado).hexdigest()


def _hmac_contexto(rotulo: str, valor: str) -> str:
    chave = settings.SECRET_KEY.encode("utf-8")
    mensagem = f"aceite-orcamento:{rotulo}:{valor or '-'}".encode("utf-8")
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def criar_aceite(orcamento, request, *, nome: str, documento: str):
    """Cria uma única prova do aceite; a transação externa trava a proposta."""
    return AceiteOrcamento.objects.create(
        orcamento=orcamento,
        assinante_nome=(nome or "").strip()[:120],
        assinante_documento=chave_documento(documento),
        consentimento=True,
        proposta_hash=hash_proposta(orcamento),
        ip_hash=_hmac_contexto("ip", request.META.get("REMOTE_ADDR", "")),
        navegador_hash=_hmac_contexto(
            "navegador", request.META.get("HTTP_USER_AGENT", "")[:500]
        ),
        termos_versao=TERMOS_VERSAO,
    )


def documento_mascarado(aceite) -> str:
    return mascarar_documento(aceite.assinante_documento) if aceite else ""
