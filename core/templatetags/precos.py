"""O preço do site em todo card (LEIA-ME seções 98 e 99).

O dono: "no Pix é o valor do objeto e no crédito o valor deve ser 12% a mais,
para todos os brinquedos e peças; apresentar o valor fixo sempre como valor
promocional nos cards, para impressionar os clientes e deixar nítida a
diferença" e "com as promoções, mantenha os 10x sem juros; com os brinquedos
normais, até 6x sem juros, acima disso com juros, podendo manipular isso pelo
objeto". A conta é uma só, a de core/parcelas_texto.py (a mesma do checkout):
o card promete exatamente o que o pagamento cobra.

    {% load precos %}
    {% preco_pix_cartao brinquedo.valor_brinquedo sem_juros=brinquedo.sem_juros_no_cartao %}
    {% preco_pix_cartao promo.preco_promocao de=promo.preco_tabela sem_juros=promo.sem_juros_no_cartao %}
    {% preco_pix_cartao peca.preco_venda compacto=True sem_juros=peca.sem_juros_no_cartao %}

Sem `sem_juros`, vale o padrão dos brinquedos (6x).
"""

from django import template

from core import checkout, parcelas_texto

register = template.Library()


def _valor(valor):
    v = checkout.valor_monetario(valor)
    return v if v is not None and v > 0 else None


def _sem_juros(sem_juros):
    return parcelas_texto.normalizar_sem_juros(sem_juros, parcelas_texto.SEM_JUROS_PADRAO)


@register.filter
def no_cartao(valor):
    """O preço no cartão de crédito sem juros: + 12%."""
    v = _valor(valor)
    return checkout.valor_no_cartao(v) if v else None


@register.filter
def parcelas_cartao(valor, sem_juros=None):
    """Em até quantas vezes sem juros (as do objeto; parcela mínima de R$ 5)."""
    resumo = parcelas_texto.resumo_do_cartao(_valor(valor), _sem_juros(sem_juros))
    return resumo["vezes"] if resumo else 1


@register.filter
def parcela_cartao(valor, sem_juros=None):
    """O valor de cada parcela no máximo de vezes sem juros."""
    resumo = parcelas_texto.resumo_do_cartao(_valor(valor), _sem_juros(sem_juros))
    return resumo["parcela"] if resumo else None


def dados_do_preco(valor, de=None, sem_juros=None):
    """O que o bloco de preço mostra (também usado pelo JSON da vitrine)."""
    pix = _valor(valor)
    if not pix:
        return None
    resumo = parcelas_texto.resumo_do_cartao(pix, _sem_juros(sem_juros))
    cartao = resumo["cartao"]
    de = _valor(de)
    # o riscado: o "de" da promoção (o preço normal), se houver; senão, o próprio cartão
    riscado = de if de and de > pix else cartao
    return {
        "pix": pix,
        "cartao": cartao,
        "vezes": resumo["vezes"],
        "parcela": resumo["parcela"],
        "vezes_com_juros": resumo["vezes_com_juros"],
        "parcela_com_juros": resumo["parcela_com_juros"],
        "riscado": riscado,
        "riscado_e_cartao": not (de and de > pix),
        "desconto": int(round((1 - pix / riscado) * 100)) if riscado > pix else 0,
    }


@register.inclusion_tag("partials/preco_pix_cartao.html")
def preco_pix_cartao(valor, de=None, compacto=False, rotulo="", sem_juros=None):
    dados = dados_do_preco(valor, de, sem_juros) or {}
    return {"p": dados, "compacto": compacto, "rotulo": rotulo}
