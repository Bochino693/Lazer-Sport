"""O banco recusa duas contas com o mesmo e-mail (só o índice).

Depois da 0002, nenhum endereço está em duas contas e todos estão
gravados normalizados. Estes dois índices únicos fazem o banco garantir
isso daqui para a frente, inclusive contra duas gravações ao mesmo tempo
(as telas e a guarda do pre_save conferem antes, mas duas requisições
simultâneas passariam as duas pela conferência):

  * auth_user: lower(email), só para e-mail preenchido (conta sem e-mail
    continua podendo existir, várias);
  * account_emailaddress (os endereços do allauth): lower(email) -- o
    allauth só exigia unicidade entre os CONFIRMADOS, e um endereço não
    confirmado de outra pessoa podia ser acrescentado a qualquer conta.

`CREATE UNIQUE INDEX IF NOT EXISTS ... WHERE ...` vale igual no PostgreSQL
e no SQLite. A volta apaga os dois.

Se esta migração falhar no ar com "could not create unique index", alguma
conta ganhou um e-mail repetido entre a 0002 e esta: rode de novo
`python manage.py migrate contas` -- a 0002 já aplicada não volta, então
resolva pela tela "Segurança das contas" ou pelo comando
`python manage.py contas_repetidas` (que repete a 0002) e migre de novo.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("contas", "0002_contas_com_email_repetido")]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS contas_auth_user_email_unico "
                "ON auth_user (lower(email)) WHERE email <> ''"
            ),
            reverse_sql="DROP INDEX IF EXISTS contas_auth_user_email_unico",
        ),
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS contas_emailaddress_email_unico "
                "ON account_emailaddress (lower(email))"
            ),
            reverse_sql="DROP INDEX IF EXISTS contas_emailaddress_email_unico",
        ),
    ]
