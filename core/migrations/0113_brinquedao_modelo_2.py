"""Cadastra o Brinquedão Modelo 2 (o objeto 3D feito com o .3ds da fábrica).

Roda no deploy do Render (o migrate do Pre-Deploy Command) e salva o
brinquedo no catálogo com as fotos 2D, que sobem para o Cloudinary. No
computador e nos testes não faz nada: lá não há Cloudinary de verdade.

Se o Cloudinary não responder na hora, o deploy NÃO para: a migração só
avisa, e o cadastro sai com `python manage.py cadastrar_brinquedao_modelo_2`.
Enquanto isso a Arena 3D já mostra o objeto (core/arena.py, exposição).
"""

from django.conf import settings
from django.db import migrations, transaction


def cadastrar(apps, schema_editor):
    if not getattr(settings, "IS_RENDER", False):
        return
    from core.cadastro_modelos import cadastrar_brinquedao_modelo_2

    try:
        with transaction.atomic():
            cadastrar_brinquedao_modelo_2(
                apps.get_model("core", "Brinquedos"),
                apps.get_model("core", "CategoriasBrinquedos"),
                apps.get_model("core", "ImagemBrinquedo"),
            )
    except Exception as erro:  # o deploy segue; o comando refaz depois
        print(f"Brinquedão Modelo 2 não foi cadastrado agora ({erro}). "
              "Rode: python manage.py cadastrar_brinquedao_modelo_2")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0112_recordejogo"),
    ]

    operations = [
        migrations.RunPython(cadastrar, migrations.RunPython.noop),
    ]
