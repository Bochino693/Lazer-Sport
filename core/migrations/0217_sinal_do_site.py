"""O sinal entre os processos do site (LEIA-ME-V10, seção 131). Só a tabela."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0216_arquivos_no_banco"),
    ]

    operations = [
        migrations.CreateModel(
            name="SinalDoSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chave", models.CharField(max_length=40, unique=True)),
                ("versao", models.BigIntegerField(default=0)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Sinal entre processos",
                "verbose_name_plural": "Sinais entre processos",
            },
        ),
    ]
