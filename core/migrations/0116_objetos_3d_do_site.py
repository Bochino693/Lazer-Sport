"""Liga os objetos 3D que vêm com o site aos brinquedos do catálogo.

O Strike Kids (o boliche kids) é o primeiro objeto 3D ligado pelo CADASTRO
(`ObjetoTresD`), e não pelo nome no código; o Brinquedão Modelo 2 e o
Espaço Esportivo Modelo 1, que já estavam na Arena, passam a ter o
cadastro também. Se o brinquedo já está no catálogo (com as fotos reais),
ele só ganha o objeto; se não está, no deploy do Render ele entra com as
fotos tiradas do próprio 3D. Ver `core/cadastro_modelos.py`.
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0115_objeto_3d_do_brinquedo"),
    ]

    operations = [
        migrations.RunPython(
            migracao_objetos_3d("strike-kids", "brinquedao-modelo-2", "espaco-esportivo-modelo-1"),
            migrations.RunPython.noop,
        ),
    ]
