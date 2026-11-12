"""Todo brinquedo com o adesivo padrão, com as fotos das posições e o 3D (a 0173; LEIA-ME 72). Só dados.

Em todo lugar, idempotente (core.variantes.padronizar): o adesivo padrão de
cada brinquedo (o que já existe -- Astronautas, Azul -- ou um "Padrão") vira o
`adesivo_padrao`; as fotos sem adesivo passam para ele; o 3D do brinquedo é
copiado para ele (o mesmo arquivo); e as fotos dos outros adesivos voltam a
ter a posição (a frente, os lados, o verso do Alienígenas e do Quadrinhos),
pelo nome do arquivo. Nada sobe para o Cloudinary (isso é a 0174, no Render).
"""

from django.db import migrations


def padronizar(apps, schema_editor):
    from core import variantes

    variantes.padronizar(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0172_adesivo_padrao_e_posicoes"),
    ]

    operations = [
        migrations.RunPython(padronizar, migrations.RunPython.noop),
    ]
