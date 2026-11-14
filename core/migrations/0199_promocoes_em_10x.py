"""O preço do site: Pix pelo preço, cartão + 12% em até 10x sem juros (a 0199; LEIA-ME seção 98).

As condições gravadas das promoções falavam do parcelamento da regra antiga
("Em até 6x sem juros de R$ 5.328,33", sobre o preço do Pix). Cada linha que
fala de parcelas é reescrita com a regra nova ("Em até 10x de R$ 3.580,64 sem
juros no cartão"), pela mesma conta do checkout (core/parcelas_texto.py). O resto
do texto fica. Só dados; rodar de novo não muda nada.
"""

from django.db import migrations

from core.parcelas_texto import condicoes_em_6x


def em_10x(apps, schema_editor):
    Promocoes = apps.get_model("core", "Promocoes")
    for promocao in Promocoes.objects.exclude(condicoes=""):
        novo = condicoes_em_6x(promocao.condicoes, promocao.preco_promocao)
        if novo != promocao.condicoes:
            promocao.condicoes = novo
            promocao.save(update_fields=["condicoes"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0198_valor_cobrado_do_pedido"),
    ]

    operations = [
        migrations.RunPython(em_10x, migrations.RunPython.noop),
    ]
