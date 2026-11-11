"""Os adesivos nos cards: `{% adesivos_do_card brinquedo.id %}` (LEIA-ME, seção 72).

Num produto com adesivos (core/variantes.py), põe no card o selo "2 adesivos"
e a lista das capas de cada adesivo (`data-adesivos-capas`), que o
ls-adesivos.js revezam na foto do card ("rodando as duas imagens"). Aceita o id
do produto ou o endereço da página dele (a loja e a busca só têm o endereço).
Sem adesivos, não escreve nada.
"""

import re

from django import template
from django.utils.html import format_html

from .. import variantes

register = template.Library()

_ID_NA_URL = re.compile(r"/brinquedo/(\d+)/")


@register.simple_tag
def adesivos_do_card(alvo):
    if isinstance(alvo, str):
        achado = _ID_NA_URL.search(alvo)
        if not achado:
            return ""
        alvo = int(achado.group(1))
    if not alvo:
        return ""
    dados = variantes.do_card(int(alvo))
    if not dados:
        return ""
    nomes = " · ".join(c["nome"] for c in dados["capas"])
    return format_html(
        '<span class="card-adesivos" data-adesivos-capas="{}" title="Adesivos: {}">'
        '<i class="fa-solid fa-note-sticky" aria-hidden="true"></i> {} adesivos</span>',
        dados["json"], nomes, dados["total"],
    )
