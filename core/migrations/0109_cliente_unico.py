"""Apaga o cadastro de cliente da vitrine.

Ele existia só para pôr um alfinete no mapa da página inicial, em paralelo
ao cadastro do painel -- e as duas cópias divergiam. As linhas já foram
trazidas para `sistema_interno.Cliente` pela migração
`sistema_interno/0020_cliente_unico`, de que esta depende; aqui só resta
derrubar a tabela vazia.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0108_vitrine_cupons"),
        # Garante que as linhas já foram copiadas antes de a tabela cair.
        ("sistema_interno", "0020_cliente_unico"),
    ]

    operations = [
        migrations.DeleteModel(name="Clientes"),
    ]
