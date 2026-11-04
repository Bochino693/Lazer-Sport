"""Liga os objetos 3D do Lazer Shot e do Boliche Virtual aos brinquedos do catálogo.

Os dois jogos da casa que já estão no catálogo ganham o objeto 3D feito
com a arte de cada jogo (o Boliche Virtual é a máquina do Dragon Bowling).
A ligação é pelo nome ("Lazer Shot"; "Boliche Virtual" ou "Dragon
Bowling"), e nada é criado: quem não está no catálogo aparece só na Arena
3D, com o objeto. Ver `core/cadastro_modelos.py`.
"""

from django.db import migrations

from core.cadastro_modelos import migracao_objetos_3d


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0117_strike_kids_no_catalogo"),
    ]

    operations = [
        migrations.RunPython(
            migracao_objetos_3d("lazer-shot", "boliche-virtual", cadastrar_no_banco_real=True),
            migrations.RunPython.noop,
        ),
    ]
