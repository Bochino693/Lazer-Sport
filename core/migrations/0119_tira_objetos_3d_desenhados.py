"""Tira dos brinquedos os objetos 3D desenhados do Lazer Shot e do Boliche Virtual.

Eles não saíram das fotos das máquinas (ver a 0118). Sem a ligação, as duas
máquinas voltam a aparecer na Arena 3D com o volume montado das fotos reais
de cada brinquedo -- e o Dragon Bowling de cada cor, com as suas fotos.
Só sai a ligação com o objeto que vinha com o site (`arquivo_estatico`):
um .glb enviado pelo painel fica.
"""

from django.db import migrations


def tirar(apps, schema_editor):
    ObjetoTresD = apps.get_model("core", "ObjetoTresD")
    ObjetoTresD.objects.filter(
        codigo__in=("lazer-shot", "boliche-virtual"),
        arquivo="",
        arquivo_estatico__in=(
            "site/arena/modelos/lazer-shot.glb",
            "site/arena/modelos/boliche-virtual.glb",
        ),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0118_objetos_3d_dos_jogos_da_casa"),
    ]

    operations = [
        migrations.RunPython(tirar, migrations.RunPython.noop),
    ]
