"""Cadastra o Brinquedão Modelo 3 (o objeto 3D feito com as três imagens do projeto).

O brinquedão em L de 10 m × 5,20 m, altura de 3,75 m. Como a 0140: o objeto
3D se liga ao brinquedo que já estiver no catálogo (pelo nome), em todo
lugar; se ele ainda não está, no deploy do Render o brinquedo entra com as
quatro fotos (a frente, os dois lados e a planta, vistas do próprio 3D), que
sobem para o Cloudinary. No computador e nos testes não cadastra nada; se o
Cloudinary falhar, o deploy segue e `python manage.py cadastrar_brinquedao_modelo_3`
refaz. Enquanto isso a Arena 3D já mostra o objeto (core/arena.py, MODELOS_3D).
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0141_pedido_projeto_3d"),
    ]

    operations = [
        migrations.RunPython(migracao_objetos_3d("brinquedao-modelo-3"), migrations.RunPython.noop),
    ]
