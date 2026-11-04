"""Garante o Strike Kids no catálogo, com o .glb dele ligado.

A 0116 só cadastrava o brinquedo no deploy do Render: quem rodou o
`migrate` no computador (no banco de verdade do site, o PostgreSQL) ficou
sem o Strike Kids no catálogo -- só a ligação, que não acha nada para
ligar. Esta roda de novo, e agora cadastra também no banco de verdade
fora do Render: o brinquedo "Strike Kids Boliche", com as quatro fotos
tiradas do objeto (que sobem para o Cloudinary, como as do painel), as
medidas e o objeto 3D. Se o catálogo já tem o Strike Kids (ou "Boliche
Kids"), ele só ganha o objeto. Não duplica, e se a subida das fotos
falhar o `migrate` segue: `python manage.py cadastrar_modelo_3d
strike-kids` refaz. Nos testes (SQLite) não cadastra nada.
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0116_objetos_3d_do_site"),
    ]

    operations = [
        migrations.RunPython(
            migracao_objetos_3d("strike-kids", cadastrar_no_banco_real=True),
            migrations.RunPython.noop,
        ),
    ]
