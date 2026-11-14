"""Black Friday: "tudo em 6x" -- as condições gravadas acertadas.

As promoções diziam "Em até 10x sem juros", mas o checkout e o Mercado Pago
aceitam uma parcela a cada R$ 1.000, até 6x (core/parcelas_texto.py). Cada
linha que promete mais parcelas do que o preço deixa é reescrita com o
número certo e o valor da parcela; o resto do texto fica. Só dados.

Rodar de novo não muda nada (a linha já certa fica). Desfazer não volta o
"10x": não há o que desfazer de uma promessa que o cartão não cumpria.
"""

from django.db import migrations

from core.parcelas_texto import condicoes_em_6x


def em_6x(apps, schema_editor):
    Promocoes = apps.get_model("core", "Promocoes")
    for promocao in Promocoes.objects.exclude(condicoes=""):
        novo = condicoes_em_6x(promocao.condicoes, promocao.preco_promocao)
        if novo != promocao.condicoes:
            promocao.condicoes = novo
            promocao.save(update_fields=["condicoes"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0194_vendas_dos_pedidos_pagos"),
    ]

    operations = [
        migrations.RunPython(em_6x, migrations.RunPython.noop),
    ]
