"""Solta os gatilhos de e-mail antes de a reserva mudar de forma.

Primeiro passo de três (0045 solta, 0046 troca a tabela, 0047 instala a
regra nova). Está sozinho num arquivo porque `tests_migracoes` exige que
dados e esquema andem em migrações separadas -- e, aqui, porque o SQLite
confere o esquema INTEIRO ao reescrever uma tabela: com um gatilho ainda
apontando para a reserva antiga, a troca falharia com "no such table".
"""
from django.db import migrations

from ._email_escopo import soltar_gatilhos


def soltar(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        soltar_gatilhos(cursor, schema_editor.connection.vendor)


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0044_endereco_unico_esquema"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    # Sem reverso: a 0047 é quem sabe montar os gatilhos, e desfazê-la já
    # os solta. Repetir a queda aqui não acrescentaria nada.
    operations = [migrations.RunPython(soltar, migrations.RunPython.noop)]
