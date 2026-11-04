"""A coluna id da EmailIdentidade como bigint, no PostgreSQL (ver a 0055).

Só muda se ainda for integer: no banco do Render a 0055 gerada lá já fez
isso, e aqui não sobra nada a fazer. No SQLite (os testes), nada.
"""

from django.db import migrations


def para_bigint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'sistema_interno_emailidentidade' AND column_name = 'id'"
        )
        linha = cursor.fetchone()
        if not linha or linha[0] != "integer":
            return
        cursor.execute("ALTER TABLE sistema_interno_emailidentidade ALTER COLUMN id TYPE bigint")
        cursor.execute("SELECT pg_get_serial_sequence('sistema_interno_emailidentidade', 'id')")
        sequencia = cursor.fetchone()[0]
        if sequencia:
            cursor.execute(f"ALTER SEQUENCE {sequencia} AS bigint")


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0055_alter_emailidentidade_id"),
    ]

    operations = [
        migrations.RunPython(para_bigint, migrations.RunPython.noop),
    ]
