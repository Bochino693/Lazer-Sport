"""Garante o Strike Kids no catálogo: ativo, com a foto 2D, as outras fotos e o 3D.

A 0120 chegou a rodar no banco do site sem o brinquedo aparecer (o erro da
subida das fotos era engolido, ou ela achava um "Strike Kids" desativado e
só ligava o 3D nele). Esta roda a garantia de novo, que agora conta o que
achou e não conta brinquedo desativado. O servidor também a roda ao subir.
"""

from django.db import migrations

from core.cadastro_modelos import strike_kids_no_catalogo


def garantir(apps, schema_editor):
    strike_kids_no_catalogo(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0120_strike_kids_brinquedo_novo"),
    ]

    operations = [
        migrations.RunPython(garantir, migrations.RunPython.noop),
    ]
