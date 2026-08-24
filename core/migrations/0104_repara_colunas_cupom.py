"""Repara bancos onde a 0103 rodou no formato antigo.

A 0103 criava as colunas com `schema_editor.add_field`. No SQLite — e em
qualquer backend que reconstrói a tabela em vez de alterá-la no lugar —
cada chamada refazia `core_cupom` a partir do modelo histórico, que ainda
não conhecia os campos novos: a coluna criada na chamada anterior era
descartada e apenas a última sobrevivia.

Efeito prático: um banco criado do zero depois daquela migração ficava sem
`reutilizavel` e sem `data_expiracao`, e a página do carrinho respondia
500 com "no such column". O PostgreSQL de produção não foi afetado — lá o
add_field emite ALTER TABLE ADD COLUMN, sem reconstruir nada — mas todo
ambiente novo nascia quebrado.

Esta migração roda a mesma verificação de novo, agora pelo caminho certo.
Onde as colunas já existem, ela não faz nada.

Os campos são redeclarados aqui de propósito: migração é registro
histórico e precisa continuar valendo mesmo que o modelo mude depois.
"""

from django.db import migrations, models

from ._colunas_faltantes import criar_colunas_faltantes

CAMPOS_CUPOM = (
    (
        "data_expiracao",
        models.DateTimeField(null=True, blank=True),
    ),
    (
        "reutilizavel",
        models.BooleanField(default=False),
    ),
    (
        "todos_usuarios",
        models.BooleanField(default=True),
    ),
)


def reparar(apps, schema_editor):
    Cupom = apps.get_model("core", "Cupom")
    criar_colunas_faltantes(
        schema_editor,
        Cupom._meta.db_table,
        CAMPOS_CUPOM,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0103_cupom_data_expiracao_cupom_reutilizavel_and_more"),
    ]

    operations = [
        # Só banco: o estado do Django já ficou correto na 0103.
        migrations.RunPython(reparar, migrations.RunPython.noop),
    ]
