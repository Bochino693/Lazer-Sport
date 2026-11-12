"""O selo de presença da lista de Usuários: "Online agora", "Visto há 2 h", "Nunca entrou".

    {% load analises %}
    {% selo_presenca usuario %}

A conta precisa vir com `select_related("presenca")`: o selo não consulta
nada sozinho (uma lista de duzentas contas não pode virar duzentas consultas).
"""

from django import template
from django.utils.html import format_html

from core.presenca import situacao_da_conta

register = template.Library()


@register.simple_tag
def selo_presenca(usuario):
    estado = situacao_da_conta(usuario)
    if estado["online"]:
        return format_html(
            '<span class="lsa-presenca is-online" title="Deu sinal de vida nos últimos minutos">'
            '<span class="lsa-ponto-vivo" aria-hidden="true"></span>{}</span>',
            estado["texto"],
        )
    icone = "bi-person-dash" if estado["codigo"] == "nunca" else "bi-clock-history"
    return format_html(
        '<span class="lsa-presenca" title="{}"><i class="bi {}" aria-hidden="true"></i>{}</span>',
        "Último sinal de vida (ou último login, para quem não voltou desde que a presença existe)",
        icone,
        estado["texto"],
    )
