"""A Black Friday vai até 21/11/2026 (era até 13/11): a validade e as artes 01-03.

Só a validade (e, no Render, as seis imagens que traziam "válida até 13 de novembro"
escrito); preço, condições e brinquedos que a equipe acertou no painel ficam como estão.
Ver core/black_friday.py (estender_ate_21) e o LEIA-ME, seção 74.
"""

from django.db import migrations


def estender(apps, schema_editor):
    from core import black_friday

    black_friday.estender_ate_21(apps, schema_editor)


def voltar(apps, schema_editor):
    from core import black_friday

    black_friday.voltar_para_13(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0190_air_rock_adesivo_do_air_game_premium"),
    ]

    operations = [
        migrations.RunPython(estender, voltar),
    ]
