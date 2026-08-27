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
        # As linhas já foram copiadas (0021) e a coluna que apontava para
        # cá já caiu (0022). Sem a 0022 antes, esta tabela ainda teria uma
        # chave estrangeira apontando para ela e não poderia ser apagada.
        ("sistema_interno", "0022_remove_cliente_mapa"),
    ]

    operations = [
        migrations.DeleteModel(name="Clientes"),
    ]
