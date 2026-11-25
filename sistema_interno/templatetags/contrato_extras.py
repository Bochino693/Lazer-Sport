"""Filtros da folha do contrato (`documento_assinatura/contrato.html`).

`destaque_contrato`: o texto das cláusulas vem do retrato como texto puro
(é ele que entra no hash). Na folha, os nomes das partes -- VENDEDOR e
COMPRADOR -- e o nome do instrumento saem em negrito, como no contrato da
empresa. O texto é escapado ANTES: nada do retrato vira HTML.

`texto_de_rodape`: a linha do rodapé de cada página impressa (o código do
contrato) vai dentro de uma regra CSS (`@page`). Só passam letras,
números e a pontuação de um número de documento -- aspas, barra
invertida e chaves nunca chegam ao CSS.
"""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# A ordem de serviço (seção 124) tem as partes dela: CONTRATADA e CONTRATANTE.
_DESTAQUES = re.compile(
    r"\b(INSTRUMENTO PARTICULAR DE COMPRA E VENDA|INSTRUMENTO PARTICULAR DE PRESTAÇÃO DE SERVIÇOS"
    r"|ORDEM DE SERVIÇO|VENDEDOR|COMPRADOR|CONTRATADA|CONTRATANTE)\b"
)


@register.filter
def destaque_contrato(texto):
    return mark_safe(_DESTAQUES.sub(r"<strong>\1</strong>", escape(texto or "")))


_FORA_DO_RODAPE = re.compile(r"[^0-9A-Za-zÀ-ÿºª/.,:·\- ]")


@register.filter
def texto_de_rodape(texto):
    return mark_safe(_FORA_DO_RODAPE.sub("", str(texto or ""))[:120])


@register.simple_tag
def minutos_do_link():
    """Os minutos que cada link de assinatura vale ("cada um válido por 10
    minutos"), lidos da regra -- o texto da folha não fica para trás quando
    o tempo muda."""
    from sistema_interno.documento_assinatura import minutos_do_link as minutos

    return minutos()


@register.simple_tag
def prazo_do_link():
    """O tempo que cada link de assinatura vale, em palavras ("cada um válido
    por 24 horas"), lido da regra -- o texto da folha não fica para trás
    quando o tempo muda."""
    from sistema_interno.documento_assinatura import prazo_do_link as prazo

    return prazo()
