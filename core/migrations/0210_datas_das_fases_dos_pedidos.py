"""As datas das fases dos pedidos de antes (LEIA-ME-V10, seção 106). SÓ DADOS.

A 0209 criou as datas vazias; daqui em diante o `Pedido.save()` grava cada
uma quando a situação muda. Os pedidos que já estavam no banco ganham o
melhor palpite que existe, para a linha do tempo de Meus pedidos não
mostrar fase "feita" sem dia:

  * PAGO EM (os pagos, e o cancelado que tinha sido pago -- o Mercado Pago
    aprovou ou a contagem da produção começou): o dia do pagamento
    aprovado (`producao_inicio`, seção 89). Quando é o mesmo dia em que o
    pedido foi feito, vale a hora do pedido (a reserva nasce minutos antes
    da aprovação); dia depois (o boleto pago dias mais tarde), meio-dia
    daquele dia -- a tela mostra só o dia. Sem `producao_inicio`, o dia do
    pedido;
  * SAIU PARA ENTREGA / PRONTO PARA RETIRADA EM (quem está nessa fase
    agora), ENTREGUE EM (os finalizados) e CANCELADO EM (os cancelados): a
    última gravação do pedido (`atualizado`), que é quando ele chegou à
    situação de agora -- ninguém mexe no pedido entregue ou cancelado;
  * EM PREPARAÇÃO fica vazia: a fase de agora não precisa do dia (a nota é
    "Começou em <pagamento> · previsão ..."), e inventar o dia em que a
    fábrica começou seria mentir para o cliente.

Separada da 0209 (regra do projeto: esquema e dados nunca no mesmo
arquivo, ver sistema_interno/tests_migracoes.py). RODAR DE NOVO NÃO MUDA
NADA: só preenche data vazia. DESFAZER não apaga: as datas somem junto com
as colunas quando a 0209 é desfeita.
"""

import datetime as dt

from django.db import migrations
from django.utils import timezone

#: Copiadas: a migração não pode depender do código de hoje, que muda.
PAGAS = ("pago", "em_preparacao", "saiu_entrega", "finalizado")


def _dia(momento):
    if momento is None:
        return None
    if timezone.is_aware(momento):
        momento = timezone.localtime(momento)
    return momento.date()


def quando_foi_pago(pedido):
    """O palpite do pagamento: o dia do `producao_inicio`, a hora do pedido."""
    inicio = pedido.producao_inicio
    if inicio is None or (pedido.criacao is not None and _dia(pedido.criacao) >= inicio):
        return pedido.criacao
    meio_dia = dt.datetime.combine(inicio, dt.time(12, 0))
    return timezone.make_aware(meio_dia) if timezone.is_naive(meio_dia) else meio_dia


def datas_de_antes(pedido):
    """As datas que o pedido antigo ganha (só as que estão vazias)."""
    novas = {}
    foi_pago = pedido.status in PAGAS or (
        pedido.status == "cancelado"
        and (pedido.mp_status == "approved" or pedido.producao_inicio is not None)
    )
    if foi_pago and pedido.pago_em is None:
        novas["pago_em"] = quando_foi_pago(pedido)
    ultima = pedido.atualizado or pedido.criacao
    if pedido.status == "saiu_entrega" and pedido.enviado_em is None:
        novas["enviado_em"] = ultima
    if pedido.status == "finalizado" and pedido.entregue_em is None:
        novas["entregue_em"] = ultima
    if pedido.status == "cancelado" and pedido.cancelado_em is None:
        novas["cancelado_em"] = ultima
    return {campo: valor for campo, valor in novas.items() if valor is not None}


def preencher(apps, schema_editor):
    banco = schema_editor.connection.alias
    Pedido = apps.get_model("core", "Pedido")

    antigos = (
        Pedido.objects.using(banco)
        .exclude(status="aguardando_pagamento")
        .only(
            "pk", "status", "mp_status", "criacao", "atualizado", "producao_inicio",
            "pago_em", "enviado_em", "entregue_em", "cancelado_em",
        )
        .order_by("pk")
    )
    for pedido in antigos.iterator():
        novas = datas_de_antes(pedido)
        if novas:
            # `update`, e não `save`: o `atualizado` (auto_now) fica como
            # estava -- é a data que acabamos de ler.
            Pedido.objects.using(banco).filter(pk=pedido.pk).update(**novas)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0209_pedido_fases_e_rastreio"),
    ]

    operations = [
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
