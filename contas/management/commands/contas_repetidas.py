"""Lista (e, com --aplicar, resolve) as contas com o mesmo e-mail.

    python manage.py contas_repetidas            # só mostra
    python manage.py contas_repetidas --aplicar  # bloqueia as repetidas

É a mesma regra da migração contas/0002 (a conta canônica fica, as outras
são bloqueadas e viram ocorrência na tela "Segurança das contas"). Serve
para o caso raro de o índice da 0003 não subir porque uma conta repetida
apareceu entre uma migração e outra. O e-mail sai mascarado na tela.
"""

import importlib
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand

MIGRACAO = importlib.import_module("contas.migrations.0002_contas_com_email_repetido")


def mascarar(email: str) -> str:
    local, _, dominio = (email or "").partition("@")
    if not dominio:
        return "***"
    return f"{local[:1]}***@{dominio}"


class Command(BaseCommand):
    help = "Lista e resolve contas com o mesmo e-mail (a regra da migração contas/0002)."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Bloqueia as contas repetidas.")

    def handle(self, *args, aplicar=False, **options):
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model

        User = get_user_model()
        donos = defaultdict(set)
        for pk, email in User.objects.values_list("pk", "email"):
            if MIGRACAO.normalizar(email):
                donos[MIGRACAO.normalizar(email)].add(pk)
        for user_id, email in EmailAddress.objects.values_list("user_id", "email"):
            if MIGRACAO.normalizar(email):
                donos[MIGRACAO.normalizar(email)].add(user_id)
        repetidos = {chave: ids for chave, ids in donos.items() if len(ids) > 1}

        if not repetidos:
            self.stdout.write(self.style.SUCCESS("Nenhum e-mail em mais de uma conta."))
            return
        for chave in sorted(repetidos):
            contas = ", ".join(f"#{pk}" for pk in sorted(repetidos[chave]))
            self.stdout.write(f"{mascarar(chave)}: contas {contas}")
        if not aplicar:
            self.stdout.write(f"{len(repetidos)} e-mail(s) repetido(s). Rode com --aplicar para resolver.")
            return
        MIGRACAO.resolver(apps)
        self.stdout.write(self.style.SUCCESS(
            "Resolvido: as contas bloqueadas estão na tela Segurança das contas."
        ))
