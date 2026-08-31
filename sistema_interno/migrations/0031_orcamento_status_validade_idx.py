from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0030_campanhadivulgacao_entregacampanha_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="orcamento",
            index=models.Index(
                fields=["status", "validade"],
                name="orc_status_validade_idx",
            ),
        ),
    ]
