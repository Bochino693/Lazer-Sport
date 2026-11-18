"""Os três kits eletrônicos iniciais (LEIA-ME, seção 105). SÓ DADOS.

Kit Boliche Virtual, Kit Strike Kids e Kit Lazer Shot, cada um com os seus
itens (core/kits.py, KITS_INICIAIS) e ligado à máquina do catálogo com o mesmo
nome (sem máquina, o kit nasce sem ela). SEM PREÇO: o dono põe no painel; até
lá o site mostra "Sob consulta". O item "Cabo HDMI" liga à peça "Cabo HDMI"
quando ela existe.

IDEMPOTENTE: o kit é procurado pelo nome antes de ser criado; o que já existe
não é tocado. A foto de capa do Kit Boliche Virtual (a arte do dono, em
core/static/site/kits/) sobe para o Cloudinary SÓ NO RENDER; se não subir, o
deploy segue e `python manage.py kits_eletronicos --foto` refaz.
"""

from django.db import migrations


def criar(apps, schema_editor):
    from core import kits

    kits.semear(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0207_kit_eletronico"),
    ]

    operations = [
        migrations.RunPython(criar, migrations.RunPython.noop),
    ]
