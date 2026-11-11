"""A Black Friday 2026 no ar (LEIA-ME, seção 74).

Os produtos que as artes mostram e o catálogo não tinha (Basquete Duplo,
Basquete Kids, Air Rock, Kid Play e as casinhas cenográficas) e as 11
promoções, válidas até 13/11/2026, com a foto do card e a arte inteira
(core/black_friday.py; as imagens em core/static/site/black_friday/).

Os campos novos da promoção (validade, condições, preço "de", a arte) vêm da
0162, num arquivo à parte: esquema e dados na mesma migração estouram no
Postgres (sistema_interno/tests_migracoes.py).

SÓ NO RENDER (o Cloudinary só está lá). Se a subida falhar, o deploy segue e
o aviso diz o comando: python manage.py black_friday_2026
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import black_friday

    black_friday.subir_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0162_promocoes_validade_condicoes"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
