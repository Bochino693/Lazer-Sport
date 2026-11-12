"""Sai o `origem` do adesivo (a 0170; LEIA-ME, seção 72). Só o esquema.

Depois da 0169, o adesivo não aponta mais para outro produto: as fotos e o 3D
são dele, e a ficha à parte foi apagada.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0169_um_objeto_no_banco"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="varianteadesivo",
            name="origem",
        ),
    ]
