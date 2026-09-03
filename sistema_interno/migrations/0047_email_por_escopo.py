"""Reconstrói as reservas de e-mail e instala a regra por escopo.

Último passo de três (ver 0045 e 0046).

O QUE MUDA NA PRÁTICA. A migração 0042 reservava cada endereço UMA vez
para o sistema inteiro: auth_user, os aliases do allauth e
sistema_interno_cliente dividiam a mesma gaveta. Isso proibia o caso mais
comum da casa -- o dono do buffet que tem login para acompanhar as
propostas e é, ele mesmo, o cliente que recebe o orçamento. São dois
cadastros diferentes, com vidas diferentes, e nenhum caminho do sistema
junta um ao outro pelo e-mail: a trava só criava trabalho.

Continua impossível ter dois CLIENTES com o mesmo contato (duplicidade
de cadastro) e duas CONTAS com o mesmo endereço (recuperação de senha
ambígua) -- que são os problemas de verdade.
"""
from django.db import migrations

from ._email_escopo import (
    REGISTRO,
    criar_gatilhos,
    reservas_existentes,
    soltar_gatilhos,
)


def instalar(apps, schema_editor):
    conexao = schema_editor.connection
    if conexao.vendor not in ("sqlite", "postgresql"):
        raise RuntimeError("A proteção de e-mail exige PostgreSQL ou SQLite.")

    with conexao.cursor() as cursor:
        # A 0045 já soltou os gatilhos; repetir aqui deixa esta migração
        # segura para rodar sozinha num banco que tenha ficado no meio do
        # caminho.
        soltar_gatilhos(cursor, conexao.vendor)
        cursor.execute(f"DELETE FROM {REGISTRO}")

        for (escopo, email), titular in reservas_existentes(cursor).items():
            cursor.execute(
                f"INSERT INTO {REGISTRO} (escopo, email, titular) "
                "VALUES (%s, %s, %s)",
                [escopo, email, titular],
            )

        criar_gatilhos(cursor, conexao.vendor)


def remover(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        soltar_gatilhos(cursor, schema_editor.connection.vendor)
        cursor.execute(f"DELETE FROM {REGISTRO}")


class Migration(migrations.Migration):
    dependencies = [("sistema_interno", "0046_email_por_escopo_esquema")]

    operations = [migrations.RunPython(instalar, remover)]
