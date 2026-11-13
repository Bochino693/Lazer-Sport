# O pagamento 100% do orçamento vira venda (LEIA-ME-V10, seção 81).
#
# SÓ DADOS: cada orçamento que JÁ estava pago antes desta versão ganha a
# venda dele, como se tivesse sido quitado hoje -- valor recebido (ou o
# total, se o recebido não foi anotado), confirmada, com o CPF/CNPJ do
# cliente. A data da venda é a do pagamento (`pago_em`): a receita do
# Financeiro é contada pelo mês da venda, e um orçamento quitado em agosto
# não pode aparecer como receita de novembro.
#
# Separada da 0059 (o esquema) de propósito: gravar linha com chave
# estrangeira no mesmo arquivo que um ALTER TABLE estoura no PostgreSQL
# com "pending trigger events" -- ver tests_migracoes.py.
#
# RODAR DE NOVO NÃO DUPLICA: só entra o orçamento pago que ainda não tem
# venda. Desfazer apaga as vendas ligadas a orçamentos (as do site ficam).

import re
from decimal import Decimal

from django.db import migrations

ZERO = Decimal("0.00")

#: As mesmas palavras de `sistema_interno.models.forma_da_venda`, copiadas:
#: a migração não pode depender do código de hoje, que muda.
FORMAS = (
    ("pix", ("pix",)),
    ("cartao", ("cartão", "cartao", "crédito", "credito", "débito", "debito")),
    ("dinheiro", ("dinheiro", "espécie", "especie")),
)


def _forma(texto):
    texto = (texto or "").lower()
    achadas = [codigo for codigo, palavras in FORMAS if any(p in texto for p in palavras)]
    return achadas[0] if len(achadas) == 1 else None


def _chave(valor):
    return re.sub(r"[^0-9A-Z]", "", (valor or "").upper())[:14]


def _total(orcamento, Item, banco):
    """O `Orcamento.total` de hoje, refeito (o modelo histórico não tem as
    propriedades): o valor final combinado, ou itens + frete - desconto."""
    if orcamento.valor_final is not None:
        return Decimal(orcamento.valor_final).quantize(Decimal("0.01"))
    soma = sum(
        (
            (item.valor_unitario * item.quantidade).quantize(Decimal("0.01"))
            for item in Item.objects.using(banco).filter(orcamento_id=orcamento.pk)
        ),
        ZERO,
    )
    liquido = soma + (orcamento.frete or ZERO) - (orcamento.desconto or ZERO)
    return max(liquido, ZERO).quantize(Decimal("0.01"))


def _documento(orcamento, Documento, banco):
    """O do cadastro, ou o de quem assinou o termo (como `documento_da_venda`)."""
    cliente = orcamento.cliente
    if cliente is not None:
        chave = cliente.documento_chave or _chave(cliente.documento)
        if chave:
            return chave
    assinado = (
        Documento.objects.using(banco)
        .filter(orcamento_id=orcamento.pk, situacao="assinado")
        .exclude(assinante_documento="")
        .values_list("assinante_documento", flat=True)
        .first()
    )
    return _chave(assinado)


def preencher(apps, schema_editor):
    banco = schema_editor.connection.alias
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    Item = apps.get_model("sistema_interno", "ItemOrcamento")
    Documento = apps.get_model("sistema_interno", "DocumentoAssinatura")
    Venda = apps.get_model("core", "Venda")

    pagos = (
        Orcamento.objects.using(banco)
        .filter(status_pagamento="pago", venda__isnull=True)
        .select_related("cliente")
        .order_by("pk")
    )
    for orcamento in pagos.iterator():
        recebido = orcamento.valor_pago or ZERO
        if recebido <= 0:
            recebido = _total(orcamento, Item, banco)
        venda = Venda.objects.using(banco).create(
            valor_pago=recebido,
            confirmado=True,
            cpf=_documento(orcamento, Documento, banco)[:16] or None,
            forma_pagamento=_forma(orcamento.forma_pagamento),
        )
        # `criacao` é auto_now_add: o create sempre grava "agora". O mês da
        # receita é o do pagamento, então a data vem depois, por update.
        quando = orcamento.pago_em or orcamento.atualizado or orcamento.criacao
        if quando:
            Venda.objects.using(banco).filter(pk=venda.pk).update(criacao=quando)
        Orcamento.objects.using(banco).filter(pk=orcamento.pk).update(venda=venda)


def desfazer(apps, schema_editor):
    banco = schema_editor.connection.alias
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    Venda = apps.get_model("core", "Venda")

    ids = list(
        Orcamento.objects.using(banco)
        .filter(venda__isnull=False)
        .values_list("venda_id", flat=True)
    )
    Orcamento.objects.using(banco).filter(venda_id__in=ids).update(venda=None)
    Venda.objects.using(banco).filter(pk__in=ids, pedido__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0059_orcamento_venda"),
    ]

    operations = [
        migrations.RunPython(preencher, desfazer),
    ]
