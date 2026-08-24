"""Alinha o estado dos cupons sem recriar colunas já existentes.

Alguns bancos receberam estes campos antes de a migração entrar no histórico
do Django. Uma AddField comum falha nesses ambientes com DuplicateColumn.
Esta migração consulta o schema primeiro: cria somente o que estiver faltando
e, separadamente, atualiza o estado que o Django usa nas próximas migrações.
"""

from django.db import migrations, models


def garantir_colunas_cupom(apps, schema_editor):
    Cupom = apps.get_model("core", "Cupom")
    tabela = Cupom._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        descricao = schema_editor.connection.introspection.get_table_description(
            cursor,
            tabela,
        )
    existentes = {coluna.name for coluna in descricao}

    campos = (
        (
            "data_expiracao",
            models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "Data e horário após os quais o cupom deixa de ser aceito."
                ),
            ),
        ),
        (
            "reutilizavel",
            models.BooleanField(
                default=False,
                help_text=(
                    "Permite que o mesmo cliente use este cupom em mais de "
                    "um pedido."
                ),
            ),
        ),
        (
            "todos_usuarios",
            models.BooleanField(
                default=True,
                help_text=(
                    "Quando ativo, qualquer cliente pode usar o cupom. "
                    "Quando desativado, somente os clientes selecionados "
                    "podem usar."
                ),
            ),
        ),
    )

    for nome, campo in campos:
        if nome in existentes:
            continue
        campo.set_attributes_from_name(nome)
        campo.model = Cupom
        schema_editor.add_field(Cupom, campo)
        existentes.add(nome)

    # Garante que bancos onde os booleanos foram criados manualmente como
    # anuláveis fiquem compatíveis com o modelo. Em SQLite (usado apenas em
    # testes) os campos novos já nascem com a restrição correta.
    if schema_editor.connection.vendor == "postgresql":
        qn = schema_editor.quote_name
        tabela_sql = qn(tabela)
        for nome, padrao in (("reutilizavel", False), ("todos_usuarios", True)):
            coluna_sql = qn(nome)
            schema_editor.execute(
                f"UPDATE {tabela_sql} SET {coluna_sql} = %s "
                f"WHERE {coluna_sql} IS NULL",
                [padrao],
            )
            schema_editor.execute(
                f"ALTER TABLE {tabela_sql} "
                f"ALTER COLUMN {coluna_sql} SET NOT NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0102_pedido_mp_fingerprint"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    garantir_colunas_cupom,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="cupom",
                    name="data_expiracao",
                    field=models.DateTimeField(
                        blank=True,
                        help_text=(
                            "Data e horário após os quais o cupom deixa de "
                            "ser aceito."
                        ),
                        null=True,
                    ),
                ),
                migrations.AddField(
                    model_name="cupom",
                    name="reutilizavel",
                    field=models.BooleanField(
                        default=False,
                        help_text=(
                            "Permite que o mesmo cliente use este cupom em "
                            "mais de um pedido."
                        ),
                    ),
                ),
                migrations.AddField(
                    model_name="cupom",
                    name="todos_usuarios",
                    field=models.BooleanField(
                        default=True,
                        help_text=(
                            "Quando ativo, qualquer cliente pode usar o "
                            "cupom. Quando desativado, somente os clientes "
                            "selecionados podem usar."
                        ),
                    ),
                ),
                migrations.AlterField(
                    model_name="imagembrinquedo",
                    name="ordem",
                    field=models.PositiveSmallIntegerField(
                        db_index=True,
                        default=1,
                        help_text="A ordem visual é definida pelo tipo da imagem.",
                        verbose_name="Posição na galeria",
                    ),
                ),
            ],
        ),
    ]
