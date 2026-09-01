from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0038_item_os_quantidade_inteira"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemordemservico",
            name="quantidade",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
