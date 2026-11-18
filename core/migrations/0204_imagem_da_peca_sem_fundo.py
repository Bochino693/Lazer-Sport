"""A foto da peça sem o fundo branco (LEIA-ME, seção 102). SÓ O ESQUEMA.

`imagem_original` guarda a foto que a equipe subiu e `recorte_de` marca o
arquivo já conferido. O recorte das fotos que já existem vem na 0205.
"""

import cloudinary_storage.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0203_boleto_no_checkout"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagempeca",
            name="imagem_original",
            field=models.ImageField(
                blank=True,
                null=True,
                storage=cloudinary_storage.storage.MediaCloudinaryStorage(),
                upload_to="pecas_reposicao/",
                verbose_name="Foto original (antes do recorte)",
            ),
        ),
        migrations.AddField(
            model_name="imagempeca",
            name="recorte_de",
            field=models.CharField(
                blank=True,
                default="",
                editable=False,
                help_text="O arquivo de `imagem` já conferido pelo recorte automático (com ou sem recorte).",
                max_length=255,
            ),
        ),
    ]
