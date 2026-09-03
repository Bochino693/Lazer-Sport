"""A reserva de e-mail passa a ter escopo: conta de acesso ou cliente.

Segundo passo de três (ver 0045 e 0047). A tabela guarda reservas
DERIVADAS dos cadastros -- a 0047 as reconstrói inteiras logo em
seguida --, então recriá-la é mais honesto, e muito mais legível, do que
costurar a troca da chave primária.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sistema_interno", "0045_email_por_escopo_soltar")]

    operations = [
        migrations.DeleteModel(name="EmailIdentidade"),
        migrations.CreateModel(
            name="EmailIdentidade",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "escopo",
                    models.CharField(
                        choices=[
                            ("usuario", "Conta de acesso"),
                            ("cliente", "Cliente"),
                        ],
                        max_length=8,
                    ),
                ),
                ("email", models.CharField(max_length=254)),
                ("titular", models.CharField(max_length=64)),
            ],
        ),
        migrations.AddConstraint(
            model_name="emailidentidade",
            constraint=models.UniqueConstraint(
                fields=("escopo", "email"), name="email_unico_por_escopo"
            ),
        ),
    ]
