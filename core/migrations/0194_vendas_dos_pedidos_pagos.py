# O pedido pago do site é venda (LEIA-ME-V10, seção 89).
#
# SÓ DADOS: cada pedido que JÁ estava pago (pago, em preparação, saiu para
# entrega ou finalizado) e não tinha venda ganha a dela -- confirmada (o
# Mercado Pago aprovou), com o total cobrado (produtos + frete), a forma do
# checkout (crédito e débito viram "cartão") e o CPF/CNPJ que o cliente
# digitou no carrinho. Até esta versão a venda do site só nascia no
# `Pedido.finalizar()`, que nenhuma tela chamava: o dinheiro do site não
# entrava na receita do Financeiro.
#
# A DATA DA VENDA É A DO PEDIDO. A receita do Financeiro é contada pelo mês
# da venda; o pedido nasce no início do pagamento (a reserva do checkout),
# minutos antes da aprovação. Um pedido pago em agosto não pode aparecer
# como receita do mês do deploy. O mesmo dia vira o começo da contagem do
# prazo de produção (`producao_inicio`), quando ainda não havia.
#
# Separada da 0193 (o esquema) de propósito: gravar linha com chave
# estrangeira no mesmo arquivo que um ALTER TABLE estoura no PostgreSQL com
# "pending trigger events" -- ver sistema_interno/tests_migracoes.py.
#
# RODAR DE NOVO NÃO DUPLICA: só entra o pedido pago que ainda não tem
# venda. DESFAZER apaga só as vendas que ESTA migração criou -- as que têm
# a data exata do pedido (a venda que nasce no pagamento tem a data do
# pagamento, e a de um `finalizar()` antigo, a da finalização).

from django.db import migrations
from django.db.models import F
from django.utils import timezone

#: As situações pagas e as formas, copiadas: a migração não pode depender
#: do código de hoje, que muda (`Pedido.SITUACOES_PAGAS`, `FORMA_DA_VENDA`).
PAGAS = ("pago", "em_preparacao", "saiu_entrega", "finalizado")
FORMAS = {"pix": "pix", "credito": "cartao", "debito": "cartao"}


def _documento(pedido, Carrinho, banco):
    if not pedido.carrinho_origem_id:
        return None
    texto = (
        Carrinho.objects.using(banco)
        .filter(pk=pedido.carrinho_origem_id)
        .values_list("cpf_cnpj", flat=True)
        .first()
    ) or ""
    chave = "".join(letra for letra in texto if letra.isalnum()).upper()[:14]
    return chave or None


def _dia(momento):
    if momento is None:
        return None
    if timezone.is_aware(momento):
        momento = timezone.localtime(momento)
    return momento.date()


def preencher(apps, schema_editor):
    banco = schema_editor.connection.alias
    Pedido = apps.get_model("core", "Pedido")
    Venda = apps.get_model("core", "Venda")
    Carrinho = apps.get_model("core", "Carrinho")

    pagos = (
        Pedido.objects.using(banco)
        .filter(status__in=PAGAS, venda__isnull=True)
        .order_by("pk")
    )
    for pedido in pagos.iterator():
        valor = pedido.total_final
        if valor is None:
            valor = (pedido.total_liquido or 0) + (pedido.valor_frete or 0)
        venda = Venda.objects.using(banco).create(
            pedido_id=pedido.pk,
            valor_pago=valor,
            confirmado=True,
            forma_pagamento=FORMAS.get(pedido.forma_pagamento or ""),
            cpf=_documento(pedido, Carrinho, banco),
        )
        # `criacao` é auto_now_add: o create grava "agora". O mês da
        # receita é o do pedido, então a data vem depois, por update.
        if pedido.criacao:
            Venda.objects.using(banco).filter(pk=venda.pk).update(criacao=pedido.criacao)
        if pedido.producao_inicio is None and pedido.criacao:
            Pedido.objects.using(banco).filter(pk=pedido.pk).update(
                producao_inicio=_dia(pedido.criacao),
            )


def desfazer(apps, schema_editor):
    banco = schema_editor.connection.alias
    Pedido = apps.get_model("core", "Pedido")
    Venda = apps.get_model("core", "Venda")

    minhas = Venda.objects.using(banco).filter(
        pedido__isnull=False, criacao=F("pedido__criacao"),
    )
    pedidos = list(minhas.values_list("pedido_id", flat=True))
    minhas.delete()
    Pedido.objects.using(banco).filter(
        pk__in=pedidos, prazo_producao_dias__isnull=True,
    ).update(producao_inicio=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0193_prazo_de_producao_do_pedido'),
    ]

    operations = [
        migrations.RunPython(preencher, desfazer),
    ]
