"""O dinheiro que já tinha entrado também é venda.

Sem esta migração, a tela de Vendas nasceria vazia e o financeiro
passaria a contar só o que for recebido de amanhã em diante -- como se a
empresa tivesse começado hoje. Cada proposta e cada ordem de serviço com
valor recebido ganha aqui a sua venda inicial.

A DATA É A MELHOR QUE EXISTE, e não a de hoje: `pago_em` quando o
documento foi quitado, senão a última atualização dele, senão a criação.
Um pagamento parcial antigo não carimba `pago_em` (o modelo só carimba na
quitação), então nesses casos a data é aproximada -- e é melhor uma data
aproximada, que põe o valor no mês certo ou vizinho, do que empilhar o
histórico inteiro no dia da migração.
"""

from decimal import Decimal

from django.db import migrations

ZERO = Decimal("0.00")


def _total(documento, itens):
    """Total do documento sem depender dos métodos do modelo.

    Migração roda com o modelo histórico, que não tem `@property total`.
    A conta é a mesma do `Orcamento.total`: itens + frete − desconto.
    """
    subtotal = sum((item.subtotal or ZERO for item in itens), ZERO)
    bruto = subtotal + (documento.frete or ZERO)
    return max(bruto - (documento.desconto or ZERO), ZERO).quantize(Decimal("0.01"))


def _quando(documento):
    return documento.pago_em or documento.atualizado or documento.criacao


def criar_vendas_do_historico(apps, schema_editor):
    Orcamento = apps.get_model("sistema_interno", "Orcamento")
    OrdemServico = apps.get_model("sistema_interno", "OrdemServico")
    Venda = apps.get_model("sistema_interno", "Venda")

    if Venda.objects.exists():
        return

    novas = []

    for orcamento in Orcamento.objects.filter(valor_pago__gt=0).prefetch_related("itens"):
        itens = list(orcamento.itens.all())
        novas.append(Venda(
            origem="orcamento",
            orcamento=orcamento,
            cliente_id=orcamento.cliente_id,
            nome_cliente=(orcamento.nome_cliente or "")[:120],
            valor=orcamento.valor_pago,
            valor_documento=_total(orcamento, itens),
            forma_pagamento=(orcamento.forma_pagamento or "")[:120],
            observacao=(orcamento.observacao_pagamento or "")[:240],
            recebida_em=_quando(orcamento),
            situacao="registrada",
        ))

    for ordem in OrdemServico.objects.filter(valor_pago__gt=0).prefetch_related("itens"):
        itens = list(ordem.itens.all())
        novas.append(Venda(
            origem="ordem_servico",
            ordem_servico=ordem,
            cliente_id=ordem.cliente_id,
            nome_cliente=(ordem.nome_cliente or "")[:120],
            valor=ordem.valor_pago,
            valor_documento=_total(ordem, itens),
            forma_pagamento=(ordem.forma_pagamento or "")[:120],
            observacao=(ordem.observacao_pagamento or "")[:240],
            recebida_em=_quando(ordem),
            situacao="registrada",
        ))

    # `token` tem default no modelo histórico, então cada linha já nasce
    # com o seu -- e o bulk_create preserva isso.
    Venda.objects.bulk_create(novas, batch_size=200)


def apagar_vendas_do_historico(apps, schema_editor):
    """Volta atrás sem levar junto o que foi registrado depois."""
    Venda = apps.get_model("sistema_interno", "Venda")
    Venda.objects.filter(situacao="registrada", documento_emitido_em__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0053_vendas"),
    ]

    operations = [
        migrations.RunPython(criar_vendas_do_historico, apagar_vendas_do_historico),
    ]
