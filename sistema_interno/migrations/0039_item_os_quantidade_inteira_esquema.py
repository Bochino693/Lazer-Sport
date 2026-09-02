from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Mantenha aqui a migration 0038 exata que já estava no seu arquivo
        ('sistema_interno', '0038_auto_...'),
    ]

    operations = [
        # 1. Remove a constraint caso ela já exista no PostgreSQL (evita o erro DuplicateObject)
        migrations.RunSQL(
            sql="""
            ALTER TABLE sistema_interno_itemordemservico 
            DROP CONSTRAINT IF EXISTS sistema_interno_itemordemservico_quantidade_b70424d2_check;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 2. Executa a alteração do campo quantidade normalmente
        migrations.AlterField(
            model_name='itemordemservico',
            name='quantidade',
            field=models.PositiveIntegerField(default=1),
        ),
    ]