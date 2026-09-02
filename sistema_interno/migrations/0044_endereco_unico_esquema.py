import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sistema_interno", "0043_endereco_sem_duplicata")]
    operations = [
        migrations.AddConstraint(
            model_name='enderecocliente',
            constraint=models.UniqueConstraint(models.F('cliente'), django.db.models.functions.text.Lower(django.db.models.functions.text.Trim(models.F('endereco'))), django.db.models.functions.text.Lower(django.db.models.functions.text.Trim(models.F('numero'))), django.db.models.functions.text.Lower(django.db.models.functions.text.Trim(models.F('complemento'))), django.db.models.functions.text.Lower(django.db.models.functions.text.Trim(models.F('cidade'))), django.db.models.functions.text.Lower(django.db.models.functions.text.Trim(models.F('estado'))), django.db.models.functions.text.Lower(django.db.models.functions.text.Trim(models.F('pais'))), name='endereco_cliente_local_unico'),
        ),
    ]
