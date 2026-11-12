"""Todo brinquedo com o adesivo padrão; uma foto por posição em cada adesivo (a 0172; LEIA-ME 72). Só esquema.

O cliente: "cada adesivo deve ter fotos das posições e um objeto 3d, um outro
adesivo, mesmas fotos das posições e referente a ele um objeto 3d, padronize
isso para todos". Entram o `Brinquedos.adesivo_padrao` (o adesivo cujas fotos
e 3D o card, a capa e a Arena usam) e, na `ImagemBrinquedo`, a regra "uma foto
por posição em cada adesivo" (no lugar de "uma por posição no brinquedo": o
Astronautas e o Alienígenas têm cada um a sua frente). Os dados vêm na 0173.
(Depende da 0170; na mescla, da última de core que houver.)
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0170_variantes_sem_origem"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="imagembrinquedo",
            name="uniq_imagem_brinquedo_tipo",
        ),
        migrations.AddField(
            model_name="brinquedos",
            name="adesivo_padrao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.varianteadesivo",
                verbose_name="Adesivo padrão",
            ),
        ),
        migrations.AddConstraint(
            model_name="imagembrinquedo",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tipo__isnull", False)),
                fields=("variante", "tipo"),
                name="uniq_imagem_adesivo_tipo",
            ),
        ),
    ]
