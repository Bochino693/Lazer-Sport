"""`{% avisos_do_app %}`: os recados do Django como avisos de aplicativo.

Vai uma vez por página, no `base.html` do site e no `base_inner.html` do
painel. O que ela desenha, e a convenção do `extra_tags`, estão em
`core/ls_aviso.py`.
"""

from django import template

from .. import ls_aviso

register = template.Library()


@register.inclusion_tag("partials/ls_avisos.html", takes_context=True)
def avisos_do_app(context, recuperado=""):
    """Os recados da requisição; `recuperado="pagina"` soma o do endereço antigo."""
    return ls_aviso.avisos_da_pagina(
        context.get("messages"), recuperado=recuperado == "pagina",
    )
