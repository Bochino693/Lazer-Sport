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

# ----------------------------------------------------------------------
# A FAIXA SAI DO CACHE (LEIA-ME-V10, seção 120)
#
# Ela está em TODA tela do painel, inclusive na que o painel recarrega
# depois de cada gravação, e custava duas ou três viagens ao Supabase
# (~170 ms cada) para responder, quase sempre, o mesmo: a contagem de quem
# não assinou e a ficha (e o termo) de quem está olhando. Agora a resposta
# fica guardada por pessoa, com a VERSÃO do RH na chave: salvar ou apagar
# uma ficha ou um termo (assinar, enviar, substituir -- rh/sinais.py) troca
# a versão, e a próxima tela de qualquer pessoa lê de novo. O prazo curto
# é só a rede de segurança para mais de um worker sem cache compartilhado
# (o mesmo aviso de gunicorn.conf.py).
# ----------------------------------------------------------------------
CHAVE_VERSAO_DA_FAIXA = "rh:faixa:versao"
PRAZO_DA_FAIXA = 60


def versao_da_faixa():
    from django.core.cache import cache

    versao = cache.get(CHAVE_VERSAO_DA_FAIXA)
    if versao is None:
        _trocar_versao_da_faixa()
        versao = cache.get(CHAVE_VERSAO_DA_FAIXA) or 0
    return versao


def _trocar_versao_da_faixa():
    import time

    from django.core.cache import cache

    try:
        cache.set(CHAVE_VERSAO_DA_FAIXA, time.time_ns(), None)
    except Exception:  # noqa: BLE001 -- sem cache, a faixa vence sozinha
        pass


def esquecer_faixa(**kwargs):
    """Uma ficha ou um termo mudou: toda faixa guardada perde a validade.

    Na hora e de novo depois do commit: uma tela montada por outra thread no
    meio da gravação não fica com a contagem velha guardada na versão nova.
    """
    from django.db import transaction

    _trocar_versao_da_faixa()
    try:
        transaction.on_commit(_trocar_versao_da_faixa)
    except Exception:  # noqa: BLE001
        pass


def _dados_da_faixa(usuario, acesso, termo):
    """O que a faixa mostra para esta pessoa -- só dados, sem endereço."""
    if acesso.gere(usuario):
        pendentes = termo.pendentes().count()
        if pendentes:
            return {
                "mostrar": True,
                "tipo": "gestao",
                "quantos": pendentes,
                "proprio": _proprio_pendente(usuario, acesso, termo),
            }
    if _proprio_pendente(usuario, acesso, termo):
        return {"mostrar": True, "tipo": "proprio"}
    return {"mostrar": False}


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
        from django.core.cache import cache

        # Quem gere vê a faixa da equipe; mudar a função muda a chave.
        chave = f"rh:faixa:v1:{usuario.pk}:{int(acesso.gere(usuario))}:{versao_da_faixa()}"
        dados = cache.get(chave)
        if dados is None:
            dados = _dados_da_faixa(usuario, acesso, termo)
            cache.set(chave, dados, PRAZO_DA_FAIXA)
        if not dados.get("mostrar"):
            return vazio
        dados = dict(dados)
        if dados["tipo"] == "gestao":
            dados["url"] = reverse("rh_colaboradores") + "?termo=pendente"
        else:
            dados["url"] = reverse("rh_meu_termo")
        return dados
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
