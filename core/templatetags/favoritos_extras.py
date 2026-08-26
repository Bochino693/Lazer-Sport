"""Filtros usados pelos botões de curtida e lista de desejos."""

from django import template

register = template.Library()


@register.filter(name="contem")
def contem(colecao, valor) -> bool:
    """Diz se o id está no conjunto de marcados.

    A view entrega conjuntos de ids inteiros; o template não consegue
    fazer busca em dicionário com chave numérica, e sem isto cada card
    precisaria de uma consulta própria só para saber se está curtido.
    """
    if not colecao:
        return False

    try:
        return valor in colecao
    except TypeError:
        return False
