"""Cadastra o Brinquedão Ninja (o objeto 3D feito com o .3ds da fábrica e as imagens do projeto).

O brinquedão de dois andares com as duas camas elásticas é UM brinquedo.
Como a 0116: o objeto 3D se liga ao brinquedo que já estiver no catálogo
(pelo nome), em todo lugar; se ele ainda não está, no deploy do Render o
brinquedo entra com as duas fotos do projeto (a frente e a planta), que
sobem para o Cloudinary. No computador e nos testes não cadastra nada; se o
Cloudinary falhar, o deploy segue e `python manage.py cadastrar_brinquedao_ninja`
refaz. Enquanto isso a Arena 3D já mostra o objeto (core/arena.py, MODELOS_3D).
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0138_montagem_3d"),
    ]

    operations = [
        migrations.RunPython(migracao_objetos_3d("brinquedao-ninja"), migrations.RunPython.noop),
    ]
