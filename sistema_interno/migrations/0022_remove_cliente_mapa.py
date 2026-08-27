"""Derruba a coluna que ligava o cliente ao cadastro paralelo do site.

Separada da 0021 porque um `ALTER TABLE` logo depois de escrever linhas, na
mesma transação, é recusado pelo Postgres:

    cannot ALTER TABLE "sistema_interno_cliente"
    because it has pending trigger events

Ver a explicação inteira na 0020.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0021_trazer_clientes_do_site"),
    ]

    operations = [
        migrations.RemoveField(model_name="cliente", name="cliente_mapa"),
    ]
