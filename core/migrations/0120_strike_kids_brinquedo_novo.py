"""O Strike Kids como brinquedo do catálogo, com a foto 2D sem fundo e o objeto 3D.

Cadastra o "Strike Kids" (o boliche infantil da casa) com a foto principal
sem fundo e as dos lados e das costas, as medidas, a descrição (câmera e 5
sensores de precisão) e o objeto 3D ligado. Se o site já o tinha
cadastrado antes (a 0117, como "Strike Kids Boliche"), ele passa a se
chamar "Strike Kids" e ganha as fotos novas; se alguém o cadastrou no
painel, só ganha o 3D. Ver `core/cadastro_modelos.strike_kids_no_catalogo`.
"""

from django.db import migrations

from core.cadastro_modelos import strike_kids_no_catalogo


def cadastrar(apps, schema_editor):
    strike_kids_no_catalogo(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0119_tira_objetos_3d_desenhados"),
    ]

    operations = [
        migrations.RunPython(cadastrar, migrations.RunPython.noop),
    ]
