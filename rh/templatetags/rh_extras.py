"""A faixa do termo de exclusividade, no alto de TODAS as telas do painel.

"O aviso de falta de assinatura virando um grande tópico no sistema." Duas
faixas, conforme quem olha:

  * GESTÃO (e o superusuário): "N colaboradores sem o termo de
    exclusividade assinado" + "Resolver" (a lista já filtrada, com "Enviar
    para assinatura" em cada um e "Enviar para todos").
  * O PRÓPRIO COLABORADOR sem o termo assinado: "Assine o termo de
    exclusividade" + o botão que abre a assinatura. O ponto continua
    funcionando -- a faixa avisa, não trava.

Some sozinha quando não há mais ninguém pendente. Custa uma consulta para a
Gestão (a contagem) e uma para quem tem ficha (o termo dele); nada para o
resto. Fica dentro da área de conteúdo, então a navegação suave a traz (ou
a tira) junto com a tela.
"""

from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag("rh/partes/faixa_termo.html", takes_context=True)
def faixa_do_termo(context):
    request = context.get("request")
    usuario = getattr(request, "user", None)
    vazio = {"mostrar": False}
    if not getattr(usuario, "is_authenticated", False):
        return vazio
    # Na própria tela de assinar, a faixa só repetiria o que está embaixo.
    rota = getattr(getattr(request, "resolver_match", None), "url_name", "")
    if rota == "rh_meu_termo":
        return vazio
    try:
        from rh import acesso, termo
    except Exception:  # noqa: BLE001 -- sem o app, sem faixa
        return vazio

    try:
        if acesso.gere(usuario):
            pendentes = termo.pendentes().count()
            if pendentes:
                return {
                    "mostrar": True,
                    "tipo": "gestao",
                    "quantos": pendentes,
                    "url": reverse("rh_colaboradores") + "?termo=pendente",
                    "proprio": _proprio_pendente(usuario, acesso, termo),
                }
        if _proprio_pendente(usuario, acesso, termo):
            return {"mostrar": True, "tipo": "proprio", "url": reverse("rh_meu_termo")}
    except Exception:  # noqa: BLE001 -- a faixa nunca derruba a tela
        import logging

        logging.getLogger(__name__).exception("Faixa do termo não pôde ser montada")
    return vazio


def _proprio_pendente(usuario, acesso, termo):
    meu = acesso.colaborador_de(usuario)
    if meu is None or meu.situacao == "desligado":
        return False
    return termo.situacao_de(meu) != "assinado"


@register.filter
def hm(minutos):
    from rh.ponto import hm as formatar

    try:
        return formatar(int(minutos or 0))
    except (TypeError, ValueError):
        return ""


@register.filter
def iniciais(nome):
    partes = [p for p in str(nome or "").split() if p]
    if not partes:
        return "?"
    return (partes[0][:1] + (partes[-1][:1] if len(partes) > 1 else "")).upper()


@register.filter
def get_item(dicionario, chave):
    try:
        return dicionario.get(chave, "")
    except AttributeError:
        return ""
