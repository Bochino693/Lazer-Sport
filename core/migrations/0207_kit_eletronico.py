"""O kit eletrônico (LEIA-ME, seção 105). SÓ O ESQUEMA.

O dono: "precisamos agora também do chamado kit [...] os componentes
eletrônicos sem a máquina para troca ou semi instalação". O kit é uma peça
marcada (`eh_kit`), ligada à máquina a que se destina (`maquina`), com a lista
do que vem dentro (`ComponenteKit`). Os três kits iniciais vêm na 0208 (só
dados: a regra do projeto é nunca misturar esquema e RunPython).
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0206_pecas_sem_fundo_de_novo"),
    ]

    operations = [
        migrations.AddField(
            model_name="pecasreposicao",
            name="eh_kit",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Os componentes eletrônicos de uma máquina, sem a máquina: aparece em /kits/, não na lista de peças.",
                verbose_name="É um kit eletrônico",
            ),
        ),
        migrations.AddField(
            model_name="pecasreposicao",
            name="maquina",
            field=models.ForeignKey(
                blank=True,
                help_text="A máquina em que o kit é instalado (a página dela chama para o kit).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="kits_eletronicos",
                to="core.brinquedos",
                verbose_name="Máquina do kit",
            ),
        ),
        migrations.CreateModel(
            name="ComponenteKit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80, verbose_name="Item")),
                (
                    "detalhe",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Uma linha a mais na página do kit, ex.: com o jogo Boliche dos Bichinhos.",
                        max_length=120,
                        verbose_name="Detalhe",
                    ),
                ),
                (
                    "quantidade",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(99),
                        ],
                    ),
                ),
                ("ordem", models.PositiveSmallIntegerField(db_index=True, default=0)),
                (
                    "kit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="componentes_kit",
                        to="core.pecasreposicao",
                        verbose_name="Kit",
                    ),
                ),
                (
                    "peca",
                    models.ForeignKey(
                        blank=True,
                        help_text="Opcional: a peça da vitrine que é este item (o cliente pode abri-la).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="em_kits",
                        to="core.pecasreposicao",
                        verbose_name="Peça vendida avulsa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Item do kit eletrônico",
                "verbose_name_plural": "Itens do kit eletrônico",
                "ordering": ["ordem", "id"],
            },
        ),
    ]
