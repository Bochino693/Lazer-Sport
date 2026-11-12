"""O Kit Sucesso e Inovação da Black Friday é Air Game + MATRIX + Boliche Kids.

O cliente, com a arte do kit: "arrume a nomenclatura, não é o nervo teste, é o
matrix" -- a máquina das luzes ("Quantas luzes você consegue apagar?") é o
Matrix. A promoção criada pela 0163 com o nome antigo e o Nervo Teste ligado
ganha o nome certo e o Matrix no lugar (em todo lugar); no Render, a arte e o
card corrigidos ("MATRIX" no rótulo) sobem (core/black_friday.py,
kit_sucesso_com_matrix; LEIA-ME, seção 74).

Rodar de novo não muda nada. Sem a promoção, ou sem o Matrix no catálogo, nada
muda. Se a subida falhar, o deploy segue e o aviso diz o comando.
"""

from django.db import migrations


def acertar(apps, schema_editor):
    from core import black_friday

    black_friday.kit_sucesso_com_matrix(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0171_analises_e_presenca"),
    ]

    operations = [
        migrations.RunPython(acertar, migrations.RunPython.noop),
    ]
