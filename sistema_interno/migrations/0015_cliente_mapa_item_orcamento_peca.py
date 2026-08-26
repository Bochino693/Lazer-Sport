import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0108_vitrine_cupons"),
        ("sistema_interno", "0014_cliente_telefone_digitos"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="cliente_mapa",
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    "Vínculo automático criado quando um orçamento deste cliente "
                    "é aprovado. Buffets usam o vínculo de parceiro do site."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cliente_interno",
                to="core.clientes",
                verbose_name="Cliente publicado no mapa",
            ),
        ),
        migrations.AddField(
            model_name="itemorcamento",
            name="peca",
            field=models.ForeignKey(
                blank=True,
                help_text="Peça de reposição do catálogo da loja.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="itens_orcamento",
                to="core.pecasreposicao",
            ),
        ),
    ]
