from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0053_movimento_estoque_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimentoestoque",
            name="cliente_anonimo",
            field=models.BooleanField(
                default=False,
                help_text="Saída autorizada sem identificar o destinatário.",
            ),
        ),
    ]
