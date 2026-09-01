from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def normalizar_quantidades(apps, schema_editor):
    """Converte o histórico antes de trocar NUMERIC por inteiro.

    A interface sempre trabalhou com unidades, mas o campo antigo aceitava
    casas decimais. Valores legados são arredondados pelo critério comercial
    (meio para cima) e nunca ficam abaixo de uma unidade.
    """
    Item = apps.get_model("sistema_interno", "ItemOrdemServico")
    alterados = []
    for item in Item.objects.only("id", "quantidade").iterator(chunk_size=500):
        atual = Decimal(str(item.quantidade or 1))
        inteiro = max(
            1,
            int(atual.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        )
        if atual != Decimal(inteiro):
            item.quantidade = inteiro
            alterados.append(item)
    if alterados:
        Item.objects.bulk_update(alterados, ["quantidade"], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0037_atividade_orcamento"),
    ]

    operations = [
        migrations.RunPython(normalizar_quantidades, migrations.RunPython.noop),
    ]
