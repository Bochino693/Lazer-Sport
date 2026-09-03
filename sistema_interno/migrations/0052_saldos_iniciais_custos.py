from decimal import Decimal
from django.db import migrations


def preencher(apps, schema_editor):
    Estoque = apps.get_model("sistema_interno", "EstoqueMaterial")
    for item in Estoque.objects.using(schema_editor.connection.alias).all().iterator():
        saldo = (item.preco_fornecedor * max(item.quantidade, 0)).quantize(Decimal("0.01"))
        Estoque.objects.using(schema_editor.connection.alias).filter(pk=item.pk).update(
            saldo_valor=saldo, custo_estimado=item.quantidade > 0,
        )
    # Sem inventar custos de saídas ou fornecedores de compras históricas.


class Migration(migrations.Migration):
    dependencies = [("sistema_interno", "0051_custos_historico_estoque")]
    operations = [migrations.RunPython(preencher, migrations.RunPython.noop)]
