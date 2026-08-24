"""Cria colunas que faltam sem passar pelo add_field do Django.

Por que não usar `schema_editor.add_field`: no SQLite ele não sabe alterar
a tabela no lugar — reconstrói a tabela inteira a partir de
`model._meta.local_fields`. Numa migração `SeparateDatabaseAndState`, o
modelo histórico que chega ao RunPython ainda não conhece os campos novos,
então cada reconstrução apagava a coluna criada na chamada anterior: das
três colunas do cupom, só a última sobrevivia.

Aqui o ALTER TABLE é emitido direto, uma vez por coluna que realmente
falta. Nada é reconstruído, então nada se perde no caminho. O tipo e o
padrão saem do próprio campo, via `db_type` e `quote_value`, então isto
continua valendo para PostgreSQL e para SQLite.
"""


def colunas_existentes(schema_editor, tabela):
    with schema_editor.connection.cursor() as cursor:
        descricao = schema_editor.connection.introspection.get_table_description(
            cursor,
            tabela,
        )
    return {coluna.name for coluna in descricao}


def criar_colunas_faltantes(schema_editor, tabela, campos):
    """Adiciona as colunas ausentes. Devolve os nomes que foram criados.

    `campos` é uma sequência de (nome, instância de Field).
    """
    existentes = colunas_existentes(schema_editor, tabela)
    conexao = schema_editor.connection
    citar = schema_editor.quote_name
    criadas = []

    for nome, campo in campos:
        if nome in existentes:
            continue

        campo.set_attributes_from_name(nome)

        tipo = campo.db_type(conexao)
        nulo = "NULL" if campo.null else "NOT NULL"

        # Coluna NOT NULL só entra numa tabela com linhas se trouxer um
        # padrão — é o que preenche o que já está lá.
        padrao = ""
        if campo.has_default():
            padrao = f" DEFAULT {schema_editor.quote_value(campo.get_default())}"

        schema_editor.execute(
            f"ALTER TABLE {citar(tabela)} "
            f"ADD COLUMN {citar(nome)} {tipo} {nulo}{padrao}"
        )
        criadas.append(nome)
        existentes.add(nome)

    return criadas
