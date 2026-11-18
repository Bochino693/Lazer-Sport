"""A marcação de ponto não se edita nem se apaga -- nem direto no banco.

O modelo já recusa (`save` de algo existente, `delete`, `QuerySet.update`
e `delete`). Este gatilho fecha o último caminho: um UPDATE ou DELETE
escrito à mão no SQL, por script ou pelo console do Supabase. No
PostgreSQL (produção) e no SQLite (testes e desenvolvimento), o banco
devolve erro.

Só a marcação. O ajuste, o termo e a trilha de auditoria têm a regra no
modelo (um ajuste pendente pode ser apagado; a chave estrangeira da trilha
precisa poder virar NULL quando um documento é removido).

Arquivo só de "dados" (DDL), separado do esquema -- a regra do projeto
(sistema_interno/tests_migracoes.py).
"""

from django.db import migrations

TABELA = "rh_marcacaoponto"

SQLITE_CRIAR = [
    f"""CREATE TRIGGER IF NOT EXISTS rh_marcacao_sem_update BEFORE UPDATE ON {TABELA}
        BEGIN SELECT RAISE(ABORT, 'marcacao de ponto nao se edita: use um ajuste'); END;""",
    f"""CREATE TRIGGER IF NOT EXISTS rh_marcacao_sem_delete BEFORE DELETE ON {TABELA}
        BEGIN SELECT RAISE(ABORT, 'marcacao de ponto nao se apaga: use um ajuste'); END;""",
]
SQLITE_DESFAZER = [
    "DROP TRIGGER IF EXISTS rh_marcacao_sem_update;",
    "DROP TRIGGER IF EXISTS rh_marcacao_sem_delete;",
]

POSTGRES_CRIAR = [
    """CREATE OR REPLACE FUNCTION rh_marcacao_imutavel() RETURNS trigger AS $$
       BEGIN
         RAISE EXCEPTION 'marcacao de ponto nao se edita nem se apaga: use um ajuste';
       END;
       $$ LANGUAGE plpgsql;""",
    f"DROP TRIGGER IF EXISTS rh_marcacao_imutavel ON {TABELA};",
    f"""CREATE TRIGGER rh_marcacao_imutavel BEFORE UPDATE OR DELETE ON {TABELA}
        FOR EACH ROW EXECUTE FUNCTION rh_marcacao_imutavel();""",
]
POSTGRES_DESFAZER = [
    f"DROP TRIGGER IF EXISTS rh_marcacao_imutavel ON {TABELA};",
    "DROP FUNCTION IF EXISTS rh_marcacao_imutavel();",
]


def _rodar(schema_editor, comandos):
    with schema_editor.connection.cursor() as cursor:
        for comando in comandos:
            cursor.execute(comando)


def criar(apps, schema_editor):
    fornecedor = schema_editor.connection.vendor
    if fornecedor == "sqlite":
        _rodar(schema_editor, SQLITE_CRIAR)
    elif fornecedor == "postgresql":
        _rodar(schema_editor, POSTGRES_CRIAR)


def desfazer(apps, schema_editor):
    fornecedor = schema_editor.connection.vendor
    if fornecedor == "sqlite":
        _rodar(schema_editor, SQLITE_DESFAZER)
    elif fornecedor == "postgresql":
        _rodar(schema_editor, POSTGRES_DESFAZER)


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0001_inicial"),
    ]

    operations = [
        migrations.RunPython(criar, desfazer),
    ]
