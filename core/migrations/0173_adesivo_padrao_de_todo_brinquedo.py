"""Todo brinquedo com o adesivo padrão, com as fotos das posições e o 3D (a 0173; LEIA-ME 72). Só dados.

Em todo lugar, idempotente (core.variantes.padronizar; rodar de novo não muda
nada): o adesivo padrão de cada brinquedo (o que já existe -- Astronautas,
Azul -- ou um "Padrão") vira o `adesivo_padrao`; as fotos sem adesivo passam
para ele; o 3D do brinquedo é copiado para ele quando ele ainda não tem um (o
3D que um adesivo já tem nunca é trocado); as fotos dos outros adesivos voltam
a ter a posição pelo nome do arquivo (a frente em 3/4, os lados, o verso, o
tampo do Alienígenas e do Quadrinhos), só onde ela está livre; e as fotos sem
fundo (a cópia da de fundo branco, a do remove.bg, as vistas sem fundo dos
nossos 3D) viram "recorte para artes": guardadas, só no painel. Nenhuma foto
e nenhum 3D é apagado; nada sobe para o Cloudinary (isso é a 0174, no Render).
As máquinas da Black Friday só ganham o adesivo padrão.

A volta (core.variantes.despadronizar) devolve o banco como a 0172 o achou.
"""

from django.db import migrations


def padronizar(apps, schema_editor):
    from core import variantes

    variantes.padronizar(apps, schema_editor)


def despadronizar(apps, schema_editor):
    from core import variantes

    variantes.despadronizar(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0172_adesivo_padrao_e_posicoes"),
    ]

    operations = [
        migrations.RunPython(padronizar, despadronizar),
    ]
