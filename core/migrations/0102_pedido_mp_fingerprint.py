# Assinatura da cobrança no pedido.
#
# Escrita à mão pelo mesmo motivo da 0100: o makemigrations insiste em trazer
# junto a divergência antiga do app (campos de Cupom e a ordem de
# ImagemBrinquedo), que é anterior a esta alteração e precisa ser resolvida
# com o estado real do banco em mãos.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0101_confirmacoes_antigas_ja_vistas"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="mp_fingerprint",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="Assinatura da cobrança",
            ),
        ),
    ]
