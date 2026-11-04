"""(Desfeita) ligava objetos 3D desenhados para o Lazer Shot e o Boliche Virtual.

Aqueles objetos foram montados sem as fotos das máquinas -- não eram as
máquinas de verdade -- e saíram do site. A migração fica, sem fazer nada,
para os bancos que já a aplicaram não ficarem com o histórico furado; a
0119 tira as ligações que ela tiver feito.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0117_strike_kids_no_catalogo"),
    ]

    operations = []
