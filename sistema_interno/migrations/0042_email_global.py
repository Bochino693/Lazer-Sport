"""Unicidade entre Cliente, User e aliases allauth, inclusive gravações concorrentes."""
from django.db import migrations

TABELAS = (("auth_user", "id", "u:"),
           ("account_emailaddress", "user_id", "u:"),
           ("sistema_interno_cliente", "id", "c:"))
REGISTRO = "sistema_interno_emailidentidade"


def instalar(apps, schema_editor):
    con = schema_editor.connection
    if con.vendor not in ("sqlite", "postgresql"):
        raise RuntimeError("A proteção de e-mail exige PostgreSQL ou SQLite.")
    # Não adivinhamos se duas pessoas são a mesma: o operador corrige antes.
    reservas = {}
    with con.cursor() as c:
        for tabela, coluna, prefixo in TABELAS:
            c.execute(f"SELECT id, {coluna}, email FROM {tabela}")
            for pk, dono, email in c.fetchall():
                chave = (email or "").strip().lower()
                if not chave:
                    continue
                titular = prefixo + str(dono)
                if chave in reservas and reservas[chave] != titular:
                    raise RuntimeError("E-mails duplicados entre cadastros. Execute python manage.py auditar_identidades e corrija antes de migrate. Nenhum cadastro foi mesclado.")
                reservas[chave] = titular
        for email, titular in reservas.items():
            c.execute(f"INSERT INTO {REGISTRO} (email, titular) VALUES (%s, %s)", [email, titular])
        for tabela, coluna, prefixo in TABELAS:
            dono = f"'{prefixo}' || CAST(NEW.{coluna} AS TEXT)"
            old = f"'{prefixo}' || CAST(OLD.{coluna} AS TEXT)"
            chave = "lower(trim(coalesce(NEW.email, '')))"
            # Limpeza mantém os aliases reservados enquanto qualquer registro os usa.
            limpeza = f"""DELETE FROM {REGISTRO} WHERE titular = {old}
                AND NOT EXISTS (SELECT 1 FROM auth_user u WHERE 'u:' || CAST(u.id AS TEXT) = titular AND lower(trim(u.email)) = {REGISTRO}.email)
                AND NOT EXISTS (SELECT 1 FROM account_emailaddress a WHERE 'u:' || CAST(a.user_id AS TEXT) = titular AND lower(trim(a.email)) = {REGISTRO}.email)
                AND NOT EXISTS (SELECT 1 FROM sistema_interno_cliente c WHERE 'c:' || CAST(c.id AS TEXT) = titular AND lower(trim(c.email)) = {REGISTRO}.email);"""
            if con.vendor == "sqlite":
                for evento in ("INSERT", "UPDATE"):
                    c.execute(f"""CREATE TRIGGER ls_email_{tabela}_{evento.lower()} AFTER {evento} ON {tabela}
                    BEGIN
                      INSERT OR IGNORE INTO {REGISTRO}(email, titular) SELECT {chave}, {dono} WHERE {chave} <> '';
                      SELECT CASE WHEN {chave} <> '' AND EXISTS(SELECT 1 FROM {REGISTRO} WHERE email={chave} AND titular <> {dono}) THEN RAISE(ABORT, 'ls_email_duplicado') END;
                      {limpeza if evento == 'UPDATE' else ''}
                    END""")
                c.execute(f"CREATE TRIGGER ls_email_{tabela}_delete AFTER DELETE ON {tabela} BEGIN {limpeza} END")
            else:
                c.execute(f"""CREATE FUNCTION ls_email_{tabela}() RETURNS trigger AS $$
                BEGIN
                  IF TG_OP <> 'DELETE' THEN
                    IF {chave} <> '' THEN
                      INSERT INTO {REGISTRO}(email,titular) VALUES ({chave},{dono}) ON CONFLICT(email) DO NOTHING;
                      IF EXISTS(SELECT 1 FROM {REGISTRO} WHERE email={chave} AND titular <> {dono}) THEN
                        RAISE EXCEPTION 'ls_email_duplicado' USING ERRCODE='23505';
                      END IF;
                    END IF;
                  END IF;
                  IF TG_OP <> 'INSERT' THEN
                    {limpeza}
                  END IF;
                  RETURN NULL;
                END;
                $$ LANGUAGE plpgsql""")
                c.execute(f"CREATE TRIGGER ls_email_{tabela}_guard AFTER INSERT OR UPDATE OR DELETE ON {tabela} FOR EACH ROW EXECUTE FUNCTION ls_email_{tabela}()")


def remover(apps, schema_editor):
    with schema_editor.connection.cursor() as c:
        for tabela, _, _ in TABELAS:
            if schema_editor.connection.vendor == "sqlite":
                for evento in ("insert", "update", "delete"):
                    c.execute(f"DROP TRIGGER IF EXISTS ls_email_{tabela}_{evento}")
            else:
                c.execute(f"DROP TRIGGER IF EXISTS ls_email_{tabela}_guard ON {tabela}")
                c.execute(f"DROP FUNCTION IF EXISTS ls_email_{tabela}()")
        c.execute(f"DELETE FROM {REGISTRO}")


class Migration(migrations.Migration):
    dependencies = [("sistema_interno", "0041_identidade_email"),
                    ("account", "0009_emailaddress_unique_primary_email")]
    operations = [migrations.RunPython(instalar, remover)]
