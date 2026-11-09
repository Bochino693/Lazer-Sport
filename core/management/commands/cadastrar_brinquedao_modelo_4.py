"""Cadastra o Brinquedão Modelo 4 no catálogo, com as imagens do projeto e o objeto 3D.

    python manage.py cadastrar_brinquedao_modelo_4

O mesmo que `cadastrar_modelo_3d brinquedao-modelo-4`. Normalmente nem é
preciso: a migração 0142 cadastra no deploy (ver `core/cadastro_modelos.py`).
Se ele já está no catálogo (cadastrado no painel), só ganha o objeto 3D.
Rodar de novo não duplica; `--fotos` refaz a galeria.
"""

from core.management.commands.cadastrar_modelo_3d import Command as CadastrarModelo3D


class Command(CadastrarModelo3D):
    help = "Cadastra o Brinquedão Modelo 4 (fotos, medidas e o objeto 3D do site)."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, fotos=False, **opcoes):
        super().handle(modelo="brinquedao-modelo-4", fotos=fotos, **opcoes)
