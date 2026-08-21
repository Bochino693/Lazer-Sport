from django.db import migrations, models


TIPOS_INICIAIS = (
    "perfil",
    "verso",
    "lado_direito",
)


def classificar_imagens_existentes(apps, schema_editor):
    ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")

    brinquedo_ids = (
        ImagemBrinquedo.objects
        .order_by()
        .values_list("brinquedo_id", flat=True)
        .distinct()
    )

    for brinquedo_id in brinquedo_ids.iterator():
        fotos = list(
            ImagemBrinquedo.objects
            .filter(brinquedo_id=brinquedo_id)
            .order_by("ordem", "id")[:3]
        )

        for foto, tipo in zip(fotos, TIPOS_INICIAIS):
            foto.tipo = tipo
            foto.save(update_fields=["tipo"])


def desfazer_classificacao(apps, schema_editor):
    ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")
    ImagemBrinquedo.objects.update(tipo=None)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0098_galerias_ordenadas_catalogo"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagembrinquedo",
            name="tipo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("perfil", "Perfil / Frente"),
                    ("verso", "Verso / Costas"),
                    ("lado_direito", "Lado direito"),
                    ("lado_esquerdo", "Lado esquerdo"),
                ],
                db_index=True,
                max_length=20,
                null=True,
                verbose_name="Tipo da imagem",
            ),
        ),
        migrations.RunPython(
            classificar_imagens_existentes,
            desfazer_classificacao,
        ),
        migrations.AddConstraint(
            model_name="imagembrinquedo",
            constraint=models.UniqueConstraint(
                fields=("brinquedo", "tipo"),
                name="uniq_imagem_brinquedo_tipo",
            ),
        ),
    ]
