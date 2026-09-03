from collections import defaultdict
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Lista conflitos de e-mail sem alterar ou mesclar cadastros.'

    def handle(self, *args, **options):
        # CONFLITO É DENTRO DO MESMO CADASTRO.
        #
        # O mesmo endereço em um cliente e numa conta de acesso é o caso
        # normal -- é a mesma pessoa em dois papéis, e o sistema aceita
        # (ver `core/identidade_email.py`). A chave carrega o escopo
        # justamente para não acusar isso como problema.
        emails = defaultdict(set)
        with connection.cursor() as cursor:
            for tabela, coluna, escopo in (("auth_user", "id", "usuario"),
                    ("account_emailaddress", "user_id", "usuario"),
                    ("sistema_interno_cliente", "id", "cliente")):
                cursor.execute(f'SELECT {coluna}, email FROM {tabela}')
                for pk, email in cursor.fetchall():
                    if email and email.strip():
                        emails[(escopo, email.strip().lower())].add(f'{escopo} #{pk}')
        conflitos = [(chave, donos) for chave, donos in emails.items() if len(donos) > 1]
        for (escopo, email), donos in conflitos:
            self.stdout.write(f'{email} ({escopo}): {", ".join(sorted(donos))}')
        locais = defaultdict(list)
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, cliente_id, endereco, numero, complemento, cidade, estado, pais FROM sistema_interno_enderecocliente")
            for pk, cliente, *campos in cursor.fetchall():
                if cliente is not None:
                    locais[(cliente, *[(v or '').strip().lower() for v in campos])].append(pk)
        enderecos_repetidos = [(chave[0], ids) for chave, ids in locais.items() if len(ids) > 1]
        for cliente, ids in enderecos_repetidos:
            self.stdout.write(f'Cliente #{cliente}: endereços repetidos {ids}')
        if enderecos_repetidos:
            raise CommandError('Há endereços repetidos no mesmo cliente. Revise os IDs antes de migrate. Nada foi alterado.')
        if conflitos:
            raise CommandError(f'{len(conflitos)} e-mails repetidos dentro do mesmo cadastro. Corrija os registros indicados antes de migrar; nada foi alterado.')
        self.stdout.write(self.style.SUCCESS('Nenhum conflito de e-mail encontrado.'))
