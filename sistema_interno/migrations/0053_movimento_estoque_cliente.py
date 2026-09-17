from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0052_saldos_iniciais_custos"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimentoestoque",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                help_text="Destinatário do material nas saídas. Registros antigos podem ser completados depois.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="movimentos_estoque",
                to="sistema_interno.cliente",
            ),
        ),
    ]
