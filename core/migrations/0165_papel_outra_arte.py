"""A foto da outra arte do mesmo brinquedo na galeria (a 0165; LEIA-ME, seção 72). Só o esquema.

`ImagemBrinquedo.papel_na_capa` ganha o valor "outra_arte": as fotos da ficha
juntada ao produto (os Alienígenas no Air Game Kids, os Quadrinhos no
Basquete Home), na galeria dele, depois das dele. Os dados vêm na 0166, num
arquivo à parte (esquema e dados não andam juntos: sistema_interno/
tests_migracoes.py).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0164_strike_kids_mais_vivo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="imagembrinquedo",
            name="papel_na_capa",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cena", "A capa em cena"),
                    ("original", "A capa de antes da cena"),
                    ("outra_arte", "Outra arte do mesmo brinquedo"),
                ],
                default="",
                help_text="Preenchido pelo comando capas_em_cena: a capa em cena e a capa de antes dela.",
                max_length=10,
                verbose_name="Papel na capa em cena",
            ),
        ),
    ]
