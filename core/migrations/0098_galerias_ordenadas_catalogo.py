# Generated manually to preserve the current catalog images during the
# transition from a single image to ordered galleries.

import cloudinary_storage.storage
import django.db.models.deletion
from django.db import migrations, models


def preparar_imagens_existentes(apps, schema_editor):
    Brinquedos = apps.get_model("core", "Brinquedos")
    ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")
    PecasReposicao = apps.get_model("core", "PecasReposicao")
    ImagemPeca = apps.get_model("core", "ImagemPeca")

    brinquedos = (
        Brinquedos.objects
        .exclude(imagem_brinquedo__isnull=True)
        .exclude(imagem_brinquedo="")
        .only("id", "nome_brinquedo", "imagem_brinquedo")
    )
    for brinquedo in brinquedos.iterator():
        if ImagemBrinquedo.objects.filter(
            brinquedo_id=brinquedo.id,
            ordem=1,
        ).exists():
            continue

        ImagemBrinquedo.objects.create(
            brinquedo_id=brinquedo.id,
            imagem=str(brinquedo.imagem_brinquedo),
            ordem=1,
            texto_alternativo=(
                f"Foto principal de {brinquedo.nome_brinquedo}"[:180]
            ),
        )

    for peca_id in PecasReposicao.objects.values_list("id", flat=True).iterator():
        imagens = list(
            ImagemPeca.objects
            .filter(peca_reposicao_id=peca_id)
            .only("id", "posicao")
        )
        imagens.sort(key=lambda imagem: (imagem.posicao != "frente", imagem.id))
        for ordem, imagem in enumerate(imagens, start=1):
            ImagemPeca.objects.filter(pk=imagem.pk).update(ordem=ordem)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0097_manutencao_brinquedo_descricao_livre_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImagemBrinquedo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                (
                    "criacao",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                (
                    "atualizado",
                    models.DateTimeField(auto_now=True, null=True),
                ),
                (
                    "imagem",
                    models.ImageField(
                        storage=(
                            cloudinary_storage.storage.MediaCloudinaryStorage()
                        ),
                        upload_to="imagens_brinquedos/galeria/",
                        verbose_name="Imagem",
                    ),
                ),
                (
                    "ordem",
                    models.PositiveSmallIntegerField(
                        db_index=True,
                        default=1,
                        help_text=(
                            "Use 1 para a foto principal, 2 para a segunda "
                            "e assim por diante."
                        ),
                        verbose_name="Posição na galeria",
                    ),
                ),
                (
                    "texto_alternativo",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Descreva o que aparece na foto para "
                            "acessibilidade e busca."
                        ),
                        max_length=180,
                        verbose_name="Descrição da imagem",
                    ),
                ),
                (
                    "brinquedo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="imagens_brinquedo",
                        to="core.brinquedos",
                        verbose_name="Brinquedo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Imagem de Brinquedo",
                "verbose_name_plural": "Imagens de Brinquedos",
                "ordering": ["ordem", "id"],
            },
        ),
        migrations.AddField(
            model_name="imagempeca",
            name="ordem",
            field=models.PositiveSmallIntegerField(
                db_index=True,
                default=1,
                help_text=(
                    "Use 1 para a foto principal, 2 para a segunda "
                    "e assim por diante."
                ),
                verbose_name="Posição na galeria",
            ),
        ),
        migrations.AlterModelOptions(
            name="imagempeca",
            options={
                "ordering": ["ordem", "id"],
                "verbose_name": "Imagem de Peça de Reposição",
                "verbose_name_plural": "Imagens de Peças de Reposição",
            },
        ),
        migrations.RunPython(
            preparar_imagens_existentes,
            migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="imagembrinquedo",
            index=models.Index(
                fields=["brinquedo", "ordem"],
                name="img_brinquedo_ordem_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="imagempeca",
            index=models.Index(
                fields=["peca_reposicao", "ordem"],
                name="img_peca_ordem_idx",
            ),
        ),
    ]
