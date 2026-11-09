"""Cadastra o Trampolim de Enterrada (o objeto 3D feito com o .3ds da fábrica).

Como a 0116: se o brinquedo já está no catálogo (pelo nome), ele só ganha o
objeto 3D (`ObjetoTresD`); se não está, no deploy do Render ele entra com as
fotos 2D, que sobem para o Cloudinary -- no computador e nos testes, não há
Cloudinary de verdade e nada é cadastrado. Se o Cloudinary falhar, o deploy
segue: o comando `cadastrar_trampolim_enterrada` refaz. Enquanto isso a Arena
3D já mostra o objeto (core/arena.py, MODELOS_3D).
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0138_montagem_3d"),
    ]

    operations = [
        migrations.RunPython(migracao_objetos_3d("trampolim-enterrada"), migrations.RunPython.noop),
    ]
