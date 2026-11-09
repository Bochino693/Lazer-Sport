"""Cadastra o Brinquedão Ninja no catálogo, com as fotos do projeto e o objeto 3D.

    python manage.py cadastrar_brinquedao_ninja

O mesmo que `cadastrar_modelo_3d brinquedao-ninja`. Normalmente nem é
preciso: a migração 0139 cadastra no deploy (ver `core/cadastro_modelos.py`).
Se ele já está no catálogo (cadastrado no painel), só ganha o objeto 3D.
Rodar de novo não duplica; `--fotos` refaz a galeria.
"""

from core.management.commands.cadastrar_modelo_3d import Command as CadastrarModelo3D


class Command(CadastrarModelo3D):
    help = "Cadastra o Brinquedão Ninja (fotos, medidas e o objeto 3D do site)."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, fotos=False, **opcoes):
        super().handle(modelo="brinquedao-ninja", fotos=fotos, **opcoes)
