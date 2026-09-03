"""Os gatilhos que reservam um e-mail POR CADASTRO.

Este arquivo não é uma migração -- o carregador do Django ignora módulos
que começam com "_". Ele existe porque a troca de regra acontece em três
migrações (soltar os gatilhos antigos, trocar a tabela, instalar os
novos), e a trava de `tests_migracoes` exige que dados e esquema morem
em arquivos separados. O SQL fica aqui, uma vez só, em vez de ser
copiado três vezes.

A REGRA, EM UMA FRASE: o mesmo endereço pode estar numa conta de acesso
E num cliente -- é a mesma pessoa em dois papéis --, mas nunca em dois
clientes nem em duas contas. Ver `core/identidade_email.py`.
"""

#: Tabela, coluna que identifica o dono, prefixo do titular e escopo.
#: auth_user e os aliases do allauth compartilham o escopo `usuario`
#: porque são a mesma conta vista por endereços diferentes.
TABELAS = (
    ("auth_user", "id", "u:", "usuario"),
    ("account_emailaddress", "user_id", "u:", "usuario"),
    ("sistema_interno_cliente", "id", "c:", "cliente"),
)

REGISTRO = "sistema_interno_emailidentidade"

#: Quem ainda usa um endereço, dentro de cada escopo. É o que a limpeza
#: consulta antes de liberar uma reserva: enquanto qualquer registro do
#: mesmo escopo mantiver o endereço, a reserva fica de pé.
DONOS = {
    "usuario": (
        "SELECT 1 FROM auth_user u "
        "WHERE 'u:' || CAST(u.id AS TEXT) = {reg}.titular "
        "AND lower(trim(u.email)) = {reg}.email",
        "SELECT 1 FROM account_emailaddress a "
        "WHERE 'u:' || CAST(a.user_id AS TEXT) = {reg}.titular "
        "AND lower(trim(a.email)) = {reg}.email",
    ),
    "cliente": (
        "SELECT 1 FROM sistema_interno_cliente c "
        "WHERE 'c:' || CAST(c.id AS TEXT) = {reg}.titular "
        "AND lower(trim(c.email)) = {reg}.email",
    ),
}


def soltar_gatilhos(cursor, vendor):
    """Tira os gatilhos de e-mail das três tabelas, nos dois bancos."""
    for tabela, _coluna, _prefixo, _escopo in TABELAS:
        if vendor == "sqlite":
            for evento in ("insert", "update", "delete"):
                cursor.execute(f"DROP TRIGGER IF EXISTS ls_email_{tabela}_{evento}")
        else:
            cursor.execute(f"DROP TRIGGER IF EXISTS ls_email_{tabela}_guard ON {tabela}")
            cursor.execute(f"DROP FUNCTION IF EXISTS ls_email_{tabela}()")


def _limpeza(escopo, old):
    faltas = " AND ".join(
        f"NOT EXISTS ({consulta.format(reg=REGISTRO)})"
        for consulta in DONOS[escopo]
    )
    return (
        f"DELETE FROM {REGISTRO} WHERE escopo = '{escopo}' "
        f"AND titular = {old} AND {faltas};"
    )


def reservas_existentes(cursor):
    """Uma reserva por (escopo, e-mail), lida dos cadastros de hoje.

    Não adivinhamos se dois cadastros são a mesma pessoa: quando o mesmo
    endereço aparece duas vezes DENTRO de um escopo, a migração para e o
    operador corrige. O cruzamento entre escopos deixou de ser conflito.
    """
    reservas = {}
    for tabela, coluna, prefixo, escopo in TABELAS:
        cursor.execute(f"SELECT {coluna}, email FROM {tabela}")
        for dono, email in cursor.fetchall():
            chave = (email or "").strip().lower()
            if not chave:
                continue
            titular = prefixo + str(dono)
            if reservas.get((escopo, chave), titular) != titular:
                raise RuntimeError(
                    "E-mails repetidos dentro do mesmo cadastro. Execute "
                    "python manage.py auditar_identidades e corrija antes de "
                    "migrate. Nenhum cadastro foi mesclado."
                )
            reservas[(escopo, chave)] = titular
    return reservas


def criar_gatilhos(cursor, vendor):
    """Instala a checagem por escopo em cada uma das três tabelas."""
    for tabela, coluna, prefixo, escopo in TABELAS:
        dono = f"'{prefixo}' || CAST(NEW.{coluna} AS TEXT)"
        velho = f"'{prefixo}' || CAST(OLD.{coluna} AS TEXT)"
        chave = "lower(trim(coalesce(NEW.email, '')))"
        limpeza = _limpeza(escopo, velho)

        if vendor == "sqlite":
            for evento in ("INSERT", "UPDATE"):
                cursor.execute(f"""
                CREATE TRIGGER ls_email_{tabela}_{evento.lower()}
                AFTER {evento} ON {tabela}
                BEGIN
                  INSERT OR IGNORE INTO {REGISTRO}(escopo, email, titular)
                    SELECT '{escopo}', {chave}, {dono} WHERE {chave} <> '';
                  SELECT CASE WHEN {chave} <> '' AND EXISTS(
                    SELECT 1 FROM {REGISTRO}
                    WHERE escopo = '{escopo}' AND email = {chave}
                      AND titular <> {dono}
                  ) THEN RAISE(ABORT, 'ls_email_duplicado_{escopo}') END;
                  {limpeza if evento == 'UPDATE' else ''}
                END""")
            cursor.execute(
                f"CREATE TRIGGER ls_email_{tabela}_delete AFTER DELETE ON {tabela} "
                f"BEGIN {limpeza} END"
            )
        else:
            cursor.execute(f"""
            CREATE FUNCTION ls_email_{tabela}() RETURNS trigger AS $$
            BEGIN
              IF TG_OP <> 'DELETE' THEN
                IF {chave} <> '' THEN
                  INSERT INTO {REGISTRO}(escopo, email, titular)
                    VALUES ('{escopo}', {chave}, {dono})
                    ON CONFLICT(escopo, email) DO NOTHING;
                  IF EXISTS(
                    SELECT 1 FROM {REGISTRO}
                    WHERE escopo = '{escopo}' AND email = {chave}
                      AND titular <> {dono}
                  ) THEN
                    RAISE EXCEPTION 'ls_email_duplicado_{escopo}'
                      USING ERRCODE='23505';
                  END IF;
                END IF;
              END IF;
              IF TG_OP <> 'INSERT' THEN
                {limpeza}
              END IF;
              RETURN NULL;
            END;
            $$ LANGUAGE plpgsql""")
            cursor.execute(
                f"CREATE TRIGGER ls_email_{tabela}_guard "
                f"AFTER INSERT OR UPDATE OR DELETE ON {tabela} "
                f"FOR EACH ROW EXECUTE FUNCTION ls_email_{tabela}()"
            )
