"""A descrição organizada da ficha de projetos e eventos (core/ficha_texto.py).

    {% load fichas %}
    {% with f=projeto.descricao|ficha %} ... {{ f.lead }} {{ f.secoes }} {{ f.fecho }}
    {{ projeto.descricao|resumo_ficha:160 }}
"""

from django import template

from ..ficha_texto import estruturar, resumo

register = template.Library()


@register.filter
def ficha(texto):
    return estruturar(texto)


@register.filter
def resumo_ficha(texto, limite=170):
    return resumo(texto, int(limite))
