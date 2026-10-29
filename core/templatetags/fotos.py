"""Filtros das fotos: `{{ brinquedo.imagem_brinquedo|foto:720 }}`.

`foto` devolve a URL da foto com no máximo aquela largura (ver
core/fotos.py).
"""

from django import template

from .. import fotos

register = template.Library()


@register.filter
def foto(imagem, largura=720):
    return fotos.reduzir_imagem(fotos.url_da_imagem(imagem), int(largura))
