"""O campo `ImagemBrinquedo.papel_na_capa` (LEIA-ME, seção 64).

Marca a capa em cena e a capa de antes dela (que continua na galeria e é a
que o `capas_em_cena --desfazer` põe de volta). Só o esquema: as capas em
si sobem na 0157, num arquivo à parte (no Postgres, esquema e dados na
mesma migração estouram com "pending trigger events").
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0155_imagens_em_alta"),
    ]

    operations = [
        migrations.AddField(
            model_name="imagembrinquedo",
            name="papel_na_capa",
            field=models.CharField(
                blank=True,
                choices=[("cena", "A capa em cena"), ("original", "A capa de antes da cena")],
                default="",
                help_text="Preenchido pelo comando capas_em_cena: a capa em cena e a capa de antes dela.",
                max_length=10,
                verbose_name="Papel na capa em cena",
            ),
        ),
    ]
