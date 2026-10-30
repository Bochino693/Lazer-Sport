"""Cadastra o Espaço Esportivo Modelo 1 (o objeto 3D feito com o trampo.3ds).

Como a 0113: roda no deploy do Render e salva o brinquedo no catálogo com
as fotos 2D; no computador e nos testes não faz nada, e se o Cloudinary
falhar o deploy segue (o comando `cadastrar_modelo_3d` refaz). Enquanto
isso a Arena 3D já mostra o espaço (core/arena.py, exposição).
"""

from django.db import migrations

from core.cadastro_modelos import migracao


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0113_brinquedao_modelo_2"),
    ]

    operations = [
        migrations.RunPython(migracao("espaco-esportivo-modelo-1"), migrations.RunPython.noop),
    ]
