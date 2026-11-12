"""Todo brinquedo com o adesivo padrão; uma foto por posição em cada adesivo (a 0181; LEIA-ME 72). Só esquema.

O cliente: "cada adesivo deve ter fotos das posições e um objeto 3d, um outro
adesivo, mesmas fotos das posições e referente a ele um objeto 3d, padronize
isso para todos". Entram o `Brinquedos.adesivo_padrao` (o adesivo cujas fotos
e 3D o card, a capa e a Arena usam) e, na `ImagemBrinquedo`, a regra "uma foto
por posição em cada adesivo" (no lugar de "uma por posição no brinquedo": o
Astronautas e o Alienígenas têm cada um a sua frente). Entram também as
posições que saem do 3D (em 3/4, de cima) e o papel "recorte para artes" (a
foto sem fundo, guardada no adesivo e só no painel). Os dados vêm na 0182.
(Depende da 0180, a última da main: as máquinas vermelhas no showroom.)

No ar: só esquema, rápido; a regra nova (por adesivo) aceita todas as fotos
de antes (ainda sem adesivo). Volta (migrate core 0180) depois da volta da
0182, que devolve uma posição por brinquedo.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0180_maquinas_vermelhas_no_showroom"),
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
        migrations.AlterField(
            model_name="imagembrinquedo",
            name="tipo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("perfil", "Perfil / Frente"),
                    ("verso", "Verso / Costas"),
                    ("lado_direito", "Lado direito"),
                    ("lado_esquerdo", "Lado esquerdo"),
                    ("tres_quartos", "Em 3/4"),
                    ("de_cima", "De cima"),
                ],
                db_index=True,
                max_length=20,
                null=True,
                verbose_name="Tipo da imagem",
            ),
        ),
        migrations.AlterField(
            model_name="imagembrinquedo",
            name="papel_na_capa",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cena", "A capa em cena"),
                    ("original", "A capa de antes da cena"),
                    ("outra_arte", "Outra arte do mesmo brinquedo"),
                    ("recorte", "Recorte para artes (sem fundo: só no painel)"),
                ],
                default="",
                help_text="A capa em cena e a capa de antes dela (capas_em_cena); o recorte para artes (sem fundo, só no painel).",
                max_length=10,
                verbose_name="Papel na capa em cena",
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
