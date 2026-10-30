"""Faixas diagonais de aviso na foto da máquina: `{% faixas brinquedo.nome_brinquedo %}`.

Quais máquinas levam quais avisos está em `core/arena.py` (AVISOS_DO_JOGO).
A faixa vai DENTRO da caixa da foto (a que tem `position: relative`), e
o CSS fica no `site/ls-tema.css`, que toda página carrega.
"""

from django import template

from .. import arena

register = template.Library()


@register.inclusion_tag("partials/faixas.html")
def faixas(nome):
    return {"avisos": arena.avisos_da_maquina(nome)}


@register.inclusion_tag("partials/faixas.html")
def faixas_modelo():
    """Todos os avisos, para o JavaScript copiar (a ficha da Arena 3D)."""
    return {"avisos": [{"id": chave, **aviso} for chave, aviso in arena.AVISOS.items()], "modelo": True}
