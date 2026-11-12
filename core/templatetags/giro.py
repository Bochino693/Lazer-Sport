"""As fotos que giram no card, uma por adesivo: `{% fotos_do_card brinquedo.id %}` (LEIA-ME, seção 72).

Num brinquedo com mais de um adesivo (core/fotos_dos_cards.py), põe dentro
da caixa da foto do card a lista (`data-fotos-card`: [{"src", "adesivo"}],
a capa quadrada de cada adesivo, o padrão primeiro), que o site/ls-giro.js
reveza com o nome do adesivo. Aceita o id do brinquedo ou o endereço da
página dele (a loja e a busca só têm o endereço). Com um adesivo só, não
escreve nada.
"""

import json
import re

from django import template
from django.utils.html import format_html

from .. import fotos_dos_cards

register = template.Library()

_ID_NA_URL = re.compile(r"/brinquedo/(\d+)/")


@register.simple_tag
def fotos_do_card(alvo):
    if isinstance(alvo, str):
        achado = _ID_NA_URL.search(alvo)
        if not achado:
            return ""
        alvo = int(achado.group(1))
    if not alvo:
        return ""
    fotos = fotos_dos_cards.do_card(int(alvo))
    if not fotos:
        return ""
    return format_html('<span class="card-giro" hidden data-fotos-card="{}"></span>', json.dumps(fotos))
