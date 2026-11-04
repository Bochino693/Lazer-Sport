"""Os recursos da máquina, em selos com ícone: `{% faixas brinquedo.nome_brinquedo %}`.

Quais máquinas levam quais está em `core/arena.py` (AVISOS_DO_JOGO). Os
selos vão JUNTO DOS TEXTOS do card (embaixo do nome), e não por cima da
foto; na página do brinquedo, `{% faixas nome "lista" %}` mostra cada um
com a explicação. A Arena 3D não leva. O CSS fica no `site/ls-tema.css`.
(O nome da tag vem do tempo em que eram faixas diagonais na foto.)
"""

from django import template

from .. import arena

register = template.Library()


@register.inclusion_tag("partials/faixas.html")
def faixas(nome, modo="selos"):
    """`selos`: a fileira do card (ícone e nome); `lista`: a da página do produto, com a explicação."""
    return {"avisos": arena.avisos_da_maquina(nome), "modo": modo}

