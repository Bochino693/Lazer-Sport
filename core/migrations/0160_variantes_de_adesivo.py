"""Os adesivos de um produto: VarianteAdesivo e o adesivo do item do carrinho (LEIA-ME, seção 72).

O produto passa a ter adesivos (a mesma máquina com outra arte), cada um com
as fotos e o 3D de uma ficha do cadastro. Só o esquema: o Air Game Kids e o
Air Game Kids Alienígenas viram um produto só na 0161, num arquivo à parte
(esquema e dados não andam juntos: sistema_interno/tests_migracoes.py).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0159_promocoes_brinquedos_extras"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemcarrinho",
            name="adesivo",
            field=models.CharField(
                blank=True, default="", max_length=60, verbose_name="Adesivo"
            ),
        ),
        migrations.CreateModel(
            name="VarianteAdesivo",
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
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                (
                    "nome",
                    models.CharField(
                        help_text='Como aparece na escolha: "Alienígenas".',
                        max_length=60,
                        verbose_name="Adesivo",
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="?adesivo=<este> abre a página neste adesivo.",
                        max_length=60,
                        verbose_name="No endereço",
                    ),
                ),
                (
                    "ordem",
                    models.PositiveSmallIntegerField(default=1, verbose_name="Ordem"),
                ),
                (
                    "padrao",
                    models.BooleanField(
                        default=False,
                        help_text="O adesivo que a página abre.",
                        verbose_name="Padrão",
                    ),
                ),
                (
                    "brinquedo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variantes_adesivo",
                        to="core.brinquedos",
                        verbose_name="Produto",
                    ),
                ),
                (
                    "origem",
                    models.ForeignKey(
                        blank=True,
                        help_text="A ficha com as fotos e o objeto 3D deste adesivo; vazio, as do próprio produto.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="variante_de",
                        to="core.brinquedos",
                        verbose_name="Fotos e 3D de",
                    ),
                ),
            ],
            options={
                "verbose_name": "Adesivo do produto",
                "verbose_name_plural": "Adesivos do produto",
                "ordering": ["ordem", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("brinquedo", "slug"), name="uniq_variante_adesivo_slug"
                    )
                ],
            },
        ),
    ]
