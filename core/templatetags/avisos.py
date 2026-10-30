"""Faixas diagonais de aviso na foto da máquina: `{% faixas brinquedo.nome_brinquedo %}`.

Quais máquinas levam quais avisos está em `core/arena.py` (AVISOS_DO_JOGO).
Só nas fotos comuns (cards, catálogo, loja, produto, galeria): a Arena 3D
não leva faixa.
A faixa vai DENTRO da caixa da foto (a que tem `position: relative`), e
o CSS fica no `site/ls-tema.css`, que toda página carrega.
"""

from django import template

from .. import arena

register = template.Library()


@register.inclusion_tag("partials/faixas.html")
def faixas(nome):
    return {"avisos": arena.avisos_da_maquina(nome)}

