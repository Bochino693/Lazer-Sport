"""O id da EmailIdentidade como BigAutoField, igual ao resto do sistema.

Esta é a migração que o `makemigrations` gerou e o `migrate` aplicou no
Render em 2026-11-04 (o mesmo nome): o modelo já pedia BigAutoField e o
arquivo não estava no repositório.

Aqui ela muda só o que o Django sabe do modelo. A coluna fica com a 0056,
só no PostgreSQL e só se ainda for integer (no Render, ela já é bigint).
No SQLite dos testes o inteiro já tem 64 bits, e refazer a tabela, como o
Django faria lá, quebraria o gatilho de e-mail que aponta para ela.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0054_movimento_cliente_anonimo"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="emailidentidade",
                    name="id",
                    field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
            ],
            database_operations=[],
        ),
    ]
