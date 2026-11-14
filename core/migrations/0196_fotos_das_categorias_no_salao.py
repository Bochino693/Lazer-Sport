"""As fotos das categorias no salão, só com as máquinas de verdade (a 0196; LEIA-ME, seção 95).

O dono: "fotos realistas só das máquinas no ambiente, sem crianças artificiais" e
"deve ficar bem posicionado [...] tem brinquedos flutuando... não está certo". As
18 fotos de core/static/site/categorias/ foram refeitas no Blender (Cycles), numa
área de diversão de shopping (o piso de resina que reflete, a parede azul-marinho
com o neon que ilumina, o teto com as luminárias), com as máquinas de cada
categoria de pé no chão, na escala de verdade e sem ninguém
(ferramentas/fotos-categorias/).

SÓ DADOS (nenhum campo novo) e SÓ NO RENDER (o Cloudinary só está lá): sobem as
fotos das categorias que mudaram (o nome leva a assinatura do arquivo: a igual não
sobe de novo) e o cache é limpo. Se a subida falhar, o deploy segue e o aviso diz
o comando:
    python manage.py atualizar_capas_categorias
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import categorias_capas

    categorias_capas.subir_fotos_e_limpar_o_cache(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0195_promocoes_em_6x"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
