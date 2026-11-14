"""O preço do site em todo card (LEIA-ME seção 98).

O dono: "no Pix é o valor do objeto e no crédito em até 10x o valor deve ser
12% a mais, para todos os brinquedos e peças; apresentar o valor fixo sempre
como valor promocional nos cards, para impressionar os clientes e deixar
nítida a diferença". A conta é uma só, a do checkout (checkout.valor_no_cartao
e checkout.parcelas_maximas): o card promete exatamente o que o pagamento cobra.

    {% load precos %}
    {% preco_pix_cartao brinquedo.valor_brinquedo %}
    {% preco_pix_cartao promo.preco_promocao de=promo.preco_tabela %}
    {% preco_pix_cartao peca.preco_venda compacto=True %}
"""

from django import template

from core import checkout

register = template.Library()


def _valor(valor):
    v = checkout.valor_monetario(valor)
    return v if v is not None and v > 0 else None


@register.filter
def no_cartao(valor):
    """O preço no cartão de crédito: + 12%."""
    v = _valor(valor)
    return checkout.valor_no_cartao(v) if v else None


@register.filter
def parcelas_cartao(valor):
    """Em até quantas vezes sem juros (até 10x; parcela mínima de R$ 5)."""
    v = _valor(valor)
    return checkout.parcelas_maximas(checkout.valor_no_cartao(v)) if v else 1


@register.filter
def parcela_cartao(valor):
    """O valor de cada parcela no máximo de vezes."""
    v = _valor(valor)
    if not v:
        return None
    cartao = checkout.valor_no_cartao(v)
    return checkout.valor_da_parcela(cartao, checkout.parcelas_maximas(cartao))


def dados_do_preco(valor, de=None):
    """O que o bloco de preço mostra (também usado pelo JSON da vitrine)."""
    pix = _valor(valor)
    if not pix:
        return None
    cartao = checkout.valor_no_cartao(pix)
    vezes = checkout.parcelas_maximas(cartao)
    de = _valor(de)
    # o riscado: o "de" da promoção (o preço normal), se houver; senão, o próprio cartão
    riscado = de if de and de > pix else cartao
    return {
        "pix": pix,
        "cartao": cartao,
        "vezes": vezes,
        "parcela": checkout.valor_da_parcela(cartao, vezes),
        "riscado": riscado,
        "riscado_e_cartao": not (de and de > pix),
        "desconto": int(round((1 - pix / riscado) * 100)) if riscado > pix else 0,
    }


@register.inclusion_tag("partials/preco_pix_cartao.html")
def preco_pix_cartao(valor, de=None, compacto=False, rotulo=""):
    dados = dados_do_preco(valor, de) or {}
    return {"p": dados, "compacto": compacto, "rotulo": rotulo}
