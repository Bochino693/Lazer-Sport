"""Cadastra a Black Friday 2026: os produtos que faltavam e as 11 promoções das artes.

    python manage.py black_friday_2026             # cadastra (rodar de novo não duplica)
    python manage.py black_friday_2026 --simular   # só diz o que faria
    python manage.py black_friday_2026 --forcar    # cria as promoções mesmo depois de 13/11/2026

Normalmente nem é preciso: a migração 0163 faz isto no deploy do Render. O
comando é para quando a subida das fotos falhou ali (ver core/black_friday.py).
"""

from django.core.management.base import BaseCommand

from core import black_friday
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes


class Command(BaseCommand):
    help = "Cadastra a Black Friday 2026 (produtos novos e as 11 promoções com as artes)."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="só mostra o que faria")
        parser.add_argument("--forcar", action="store_true", help="cria as promoções mesmo fora da validade")

    def handle(self, *args, simular=False, forcar=False, **opcoes):
        black_friday.rodar(
            Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes,
            simular=simular, forcar=forcar, avisar=lambda texto: self.stdout.write(texto),
        )
