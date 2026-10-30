"""Cadastra o Brinquedão Modelo 2 no catálogo, com as fotos do projeto.

    python manage.py cadastrar_brinquedao_modelo_2

Normalmente nem é preciso: a migração 0113 cadastra no deploy. Este
comando é para quando ela não conseguiu (ver `core/cadastro_modelos.py`).
Rodar de novo não duplica; `--fotos` refaz a galeria.
"""

from django.core.management.base import BaseCommand

from core.cadastro_modelos import cadastrar_brinquedao_modelo_2
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo


class Command(BaseCommand):
    help = "Cadastra o Brinquedão Modelo 2 (fotos e medidas); o objeto 3D já está no site."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, fotos=False, **opcoes):
        cadastrar_brinquedao_modelo_2(
            Brinquedos, CategoriasBrinquedos, ImagemBrinquedo,
            refazer_fotos=fotos, avisar=self.stdout.write,
        )
