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


@register.filter
def tem_foto(imagem):
    """`{% if cliente.logo|tem_foto %}`: falso para a foto que só existe no Cloudinary fora do ar."""
    return fotos.foto_disponivel(imagem)
