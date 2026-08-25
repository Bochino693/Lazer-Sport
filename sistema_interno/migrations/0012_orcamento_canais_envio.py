from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0011_orcamento_token_resposta_item_brinquedo"),
    ]

    operations = [
        migrations.AddField(
            model_name="orcamento",
            name="email_cliente",
            field=models.EmailField(
                blank=True,
                help_text="Endereço que recebe a proposta comercial.",
                max_length=254,
                verbose_name="E-mail do cliente",
            ),
        ),
        migrations.AddField(
            model_name="orcamento",
            name="whatsapp_cliente",
            field=models.CharField(
                blank=True,
                help_text="Número com DDD usado no envio da proposta.",
                max_length=24,
                verbose_name="WhatsApp do cliente",
            ),
        ),
    ]
