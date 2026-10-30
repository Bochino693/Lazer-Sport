"""Cadastra no catálogo um brinquedo que já tem o objeto 3D feito aqui.

    python manage.py cadastrar_modelo_3d espaco-esportivo-modelo-1
    python manage.py cadastrar_modelo_3d brinquedao-modelo-2

Normalmente nem é preciso: as migrações de dados cadastram no deploy. Este
comando é para quando elas não conseguiram (ver `core/cadastro_modelos.py`).
Rodar de novo não duplica; `--fotos` refaz a galeria.
"""

from django.core.management.base import BaseCommand

from core.cadastro_modelos import CADASTROS, cadastrar
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo


class Command(BaseCommand):
    help = "Cadastra um brinquedo que já tem o objeto 3D no site (fotos, medidas e categoria)."

    def add_arguments(self, parser):
        parser.add_argument("modelo", choices=sorted(CADASTROS), help="qual brinquedo")
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, modelo, fotos=False, **opcoes):
        cadastrar(modelo, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=fotos, avisar=self.stdout.write)
