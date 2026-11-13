"""O selo de presença da lista de Usuários: "Online agora", "Visto há 2 h", "Nunca entrou".

    {% load analises %}
    {% selo_presenca usuario %}
    <tr data-presenca="{% grupos_presenca usuario %}">

    {% cartao_presenca usuario as cartao %}   {# nome, iniciais, cor, papel #}

A conta precisa vir com `select_related("presenca")`: o selo não consulta
nada sozinho (uma lista de duzentas contas não pode virar duzentas consultas).
Para o `cartao_presenca` (as iniciais, a cor do avatar e o papel -- Admin,
Equipe ou Cliente --, os mesmos da faixa "Agora"), a consulta anota
`_tem_funcao` (core.presenca.tem_funcao_de_equipe); sem a anotação a tag
pergunta ao banco, conta por conta.

`grupos_presenca` escreve em quais contadores do topo a conta entra
("online hoje semana mes", "mes", "nunca"...), pela MESMA regra de
`core.presenca.resumo`: é o que deixa o toque num contador filtrar a lista
na hora, sem ir ao servidor. O selo leva `data-lsa-selo` porque o
gestao-analises.js o reescreve quando a conta entra ou sai do ar com a tela
aberta.
"""

from django import template
from django.utils.html import format_html

from core.presenca import cartao_da_conta, grupos_da_conta, situacao_da_conta

register = template.Library()


@register.simple_tag
def selo_presenca(usuario):
    estado = situacao_da_conta(usuario)
    if estado["online"]:
        return format_html(
            '<span class="lsa-presenca is-online" data-lsa-selo title="Deu sinal de vida nos últimos minutos">'
            '<span class="lsa-ponto-vivo" aria-hidden="true"></span>{}</span>',
            estado["texto"],
        )
    icone = "bi-person-dash" if estado["codigo"] == "nunca" else "bi-clock-history"
    return format_html(
        '<span class="lsa-presenca" data-lsa-selo title="{}"><i class="bi {}" aria-hidden="true"></i>{}</span>',
        "A última vez em que a conta usou o site, o aplicativo ou o painel",
        icone,
        estado["texto"],
    )


@register.simple_tag
def grupos_presenca(usuario):
    return " ".join(grupos_da_conta(usuario))


@register.simple_tag
def cartao_presenca(usuario):
    return cartao_da_conta(usuario)
