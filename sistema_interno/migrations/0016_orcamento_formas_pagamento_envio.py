from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0015_cliente_mapa_item_orcamento_peca"),
    ]

    operations = [
        migrations.AddField(
            model_name="orcamento",
            name="forma_envio",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Ex.: retirada, transportadora ou entrega Lazer & Sport."
                ),
                max_length=120,
                verbose_name="Forma de envio",
            ),
        ),
        migrations.AddField(
            model_name="orcamento",
            name="forma_pagamento",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Ex.: Pix, boleto, 50% na entrada e 50% na entrega."
                ),
                max_length=120,
                verbose_name="Forma de pagamento",
            ),
        ),
    ]
