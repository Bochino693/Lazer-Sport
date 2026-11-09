"""Cadastra o Trampolim de Enterrada no catálogo, com as fotos e o objeto 3D.

    python manage.py cadastrar_trampolim_enterrada
    python manage.py cadastrar_trampolim_enterrada --fotos   # refaz a galeria

O mesmo que `cadastrar_modelo_3d trampolim-enterrada`. Normalmente nem é
preciso: a migração 0139 cadastra no deploy (ver `core/cadastro_modelos.py`).
Rodar de novo não duplica. As fotos ainda são vistas do próprio objeto 3D:
quando chegarem as do projeto, troque os .webp de
`core/static/site/arena/modelos/trampolim-enterrada/` e rode com `--fotos`.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cadastra o Trampolim de Enterrada (fotos, medidas e o objeto 3D); o objeto já está no site."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, fotos=False, **opcoes):
        call_command("cadastrar_modelo_3d", "trampolim-enterrada", fotos=fotos, stdout=self.stdout)
