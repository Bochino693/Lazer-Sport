"""As fotos das categorias Eletrônicos e Boliche Virtual com o Strike Kids novo (LEIA-ME, seção 97).

A 0200 subiu as fotos de estúdio do Strike Kids refeitas com o 3D adesivado
por dentro; as duas fotos de categoria que mostram a máquina (renderizadas em
ferramentas/fotos-categorias, ~50 min) vêm aqui, pelo mesmo caminho da 0196:
só a foto cujo arquivo mudou sobe (o nome leva a assinatura), a foto que a
equipe pôs no painel fica, e o cache é limpo.

SÓ DADOS e SÓ NO RENDER. Rodar de novo não sobe nada.
"""

from django.db import migrations


def subir(apps, schema_editor):
    from core import categorias_capas

    categorias_capas.subir_fotos_e_limpar_o_cache(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0201_parcelas_sem_juros_por_objeto"),
    ]

    operations = [
        migrations.RunPython(subir, migrations.RunPython.noop),
    ]
