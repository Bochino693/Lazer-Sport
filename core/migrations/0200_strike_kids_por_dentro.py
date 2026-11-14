"""Strike Kids: as fotos refeitas com o 3D adesivado por dentro (a 0200; LEIA-ME, seção 97).

O dono: "olha a área preta acima da máquina, não é assim, é tudo adesivo com
os LEDs", "o LED poderia ser forte, e o buraco da caída bem definido" e "você
deve completar corretamente o adesivo, você remendou". O 3D
(ferramentas/modelos3d/strike-kids/montar.js, LEIA-ME seção 97) ficou com a
arte da fábrica por dentro, contínua, o LED forte e o buraco do bolsão
definido; as fotos de estúdio do Strike Kids, que mostravam o MDF preto,
foram refeitas com ele (as das categorias Eletrônicos e Boliche Virtual vêm
na 0201).

SÓ DADOS e SÓ NO RENDER, pelos mesmos caminhos da 0196 e da 0197: só a foto
cujo arquivo mudou sobe (o nome leva a assinatura), a foto que a equipe pôs no
painel fica, e o cache é limpo. Rodar de novo não sobe nada.
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import categorias_capas, fotos_estudio

    fotos_estudio.no_deploy(apps, schema_editor)
    categorias_capas.subir_fotos_e_limpar_o_cache(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0199_promocoes_em_10x"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
