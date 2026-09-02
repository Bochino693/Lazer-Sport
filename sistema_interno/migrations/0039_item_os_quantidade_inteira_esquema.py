from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sistema_interno', '0038_item_os_quantidade_inteira'),
    ]

    operations = [
        # Remove a constraint se ela já existir para evitar o erro DuplicateObject
        migrations.RunSQL(
            sql="""
            ALTER TABLE sistema_interno_itemordemservico 
            DROP CONSTRAINT IF EXISTS sistema_interno_itemordemservico_quantidade_b70424d2_check;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Aplica a alteração do campo quantidade
        migrations.AlterField(
            model_name='itemordemservico',
            name='quantidade',
            field=models.PositiveIntegerField(default=1),
        ),
    ]