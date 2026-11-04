"""Troca a senha de uma conta de superadministrador por uma senha forte, nova.

POR QUE EXISTE. A senha do admin foi escrita num chat. Senha que já
apareceu em texto não é mais senha: tem de ser trocada, e a nova não pode
passar por nenhum lugar onde possa ser copiada -- por isso ela é gerada
aqui, mostrada UMA vez no terminal de quem rodou o comando e não fica em
log nenhum. Quem roda anota num gerenciador de senhas e fecha o terminal.

    python manage.py trocar_senha_admin                # a conta superadministradora (se for uma só)
    python manage.py trocar_senha_admin --usuario thiag
    python manage.py trocar_senha_admin --usuario thiag --tamanho 24

No Render: Shell do serviço > o comando acima. Trocar a senha também
encerra as sessões abertas dessa conta em outros navegadores (o Django
amarra a sessão ao hash da senha).
"""

import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

ALFABETO = string.ascii_letters + string.digits + "-_.!@#%&*+=?"


def senha_forte(tamanho=20):
    """Letras, números e sinais, com pelo menos um de cada."""
    while True:
        senha = "".join(secrets.choice(ALFABETO) for _ in range(tamanho))
        if (any(c.islower() for c in senha) and any(c.isupper() for c in senha)
                and any(c.isdigit() for c in senha) and any(c in "-_.!@#%&*+=?" for c in senha)):
            return senha


class Command(BaseCommand):
    help = "Gera uma senha forte nova para uma conta de superadministrador e a mostra uma única vez."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", help="O username da conta. Sem ele, a única conta superadministradora.")
        parser.add_argument("--tamanho", type=int, default=20, help="Tamanho da senha (mínimo 16).")

    def handle(self, *args, **opcoes):
        tamanho = max(16, opcoes["tamanho"])
        if opcoes["usuario"]:
            conta = User.objects.filter(username=opcoes["usuario"]).first()
            if conta is None:
                raise CommandError(f"Não existe a conta '{opcoes['usuario']}'.")
            if not conta.is_superuser:
                raise CommandError(f"'{conta.username}' não é superadministrador. Use a tela Equipe e acessos para as outras contas.")
        else:
            supers = list(User.objects.filter(is_superuser=True, is_active=True).order_by("pk"))
            if len(supers) != 1:
                nomes = ", ".join(u.username for u in supers) or "nenhuma"
                raise CommandError(f"Há {len(supers)} contas superadministradoras ({nomes}). Diga qual com --usuario.")
            conta = supers[0]

        nova = senha_forte(tamanho)
        conta.set_password(nova)
        conta.save(update_fields=["password"])

        self.stdout.write(self.style.SUCCESS(f"Senha de '{conta.username}' trocada."))
        self.stdout.write("A nova senha (guarde num gerenciador de senhas; ela não aparece de novo):")
        self.stdout.write("")
        self.stdout.write(f"    {nova}")
        self.stdout.write("")
        self.stdout.write("As sessões abertas dessa conta em outros navegadores foram encerradas.")
