"""As posições do Air Game Kids dos Astronautas, tiradas do 3D (a 0174; LEIA-ME 72). Só dados, só no Render.

O adesivo padrão do Air Game Kids (os Astronautas) ganha as fotos das posições
renderizadas do 3D dele no showroom, como as do Strike Kids e as do
Alienígenas (core/static/site/arena/modelos/air-game-kids-astronautas/: os
lados, o verso, a frente em 3/4 e o tampo); a frente (a capa) continua a foto
de verdade do catálogo, em cena. Só no Render (o Cloudinary só está lá); se a
subida falhar, o deploy segue e o comando refaz:
    python manage.py posicoes_dos_adesivos
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import variantes

    variantes.subir_posicoes_no_deploy(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0173_adesivo_padrao_de_todo_brinquedo"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
