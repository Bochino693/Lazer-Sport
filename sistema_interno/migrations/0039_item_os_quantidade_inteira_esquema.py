from django.db import migrations, models


def soltar_check_antigo(apps, schema_editor):
    """Tira a checagem antiga de quantidade antes de o campo mudar.

    `ALTER TABLE ... DROP CONSTRAINT` é sintaxe do PostgreSQL, que é o
    banco da hospedagem. O SQLite -- usado nos testes e no ambiente de
    desenvolvimento -- não conhece o comando e derrubava a migração
    inteira com "near CONSTRAINT: syntax error", deixando `manage.py
    test` sem nem chegar a rodar um caso.

    No SQLite não há o que soltar: a checagem viaja dentro da definição
    da tabela e o próprio `AlterField` a seguir reescreve a tabela.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE sistema_interno_itemordemservico "
            "DROP CONSTRAINT IF EXISTS "
            "sistema_interno_itemordemservico_quantidade_b70424d2_check"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('sistema_interno', '0038_item_os_quantidade_inteira'),
    ]

    operations = [
        # Remove a constraint se ela já existir para evitar o erro DuplicateObject
        migrations.RunPython(soltar_check_antigo, migrations.RunPython.noop),
        # Aplica a alteração do campo quantidade
        migrations.AlterField(
            model_name='itemordemservico',
            name='quantidade',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
