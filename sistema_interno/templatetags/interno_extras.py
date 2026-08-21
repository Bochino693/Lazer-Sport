"""Formatação de números do painel interno.

`{{ valor|floatformat:2|intcomma }}` parece o caminho óbvio, mas em
pt-BR devolve "5,140,00": o intcomma não consegue converter a string
que o floatformat já localizou e cai no separador americano. Aqui o
número é formatado uma vez só, direto do Decimal.
"""

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format

register = template.Library()


def _para_decimal(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return None


@register.filter
def moeda(valor):
    """1234567.8 -> 1.234.567,80"""
    numero = _para_decimal(valor)
    if numero is None:
        return "0,00"

    return number_format(
        numero.quantize(Decimal("0.01")),
        decimal_pos=2,
        force_grouping=True,
    )


@register.filter
def numero(valor):
    """5140 -> 5.140"""
    convertido = _para_decimal(valor)
    if convertido is None:
        return "0"

    return number_format(int(convertido), force_grouping=True)
