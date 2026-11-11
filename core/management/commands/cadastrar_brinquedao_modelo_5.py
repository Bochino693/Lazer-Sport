"""Cadastra o Brinquedão Modelo 5 no catálogo, com as fotos e o objeto 3D.

    python manage.py cadastrar_brinquedao_modelo_5
    python manage.py cadastrar_brinquedao_modelo_5 --fotos   # refaz a galeria

O mesmo que `cadastrar_modelo_3d brinquedao-modelo-5`. Normalmente nem é
preciso: a migração 0151 cadastra no deploy do Render (ver
`core/cadastro_modelos.py`); este comando é para quando a subida das fotos
falhou ali. Se ele já está no catálogo (cadastrado no painel), só ganha o
objeto 3D. Rodar de novo não duplica. A galeria: a perspectiva da fábrica
(a principal), as vistas do 3D (a frente, os dois lados e a perspectiva),
a planta e as duas vistas do salão, de
`core/static/site/arena/modelos/brinquedao-modelo-5/`.
"""

from core.management.commands.cadastrar_modelo_3d import Command as CadastrarModelo3D


class Command(CadastrarModelo3D):
    help = "Cadastra o Brinquedão Modelo 5 (fotos, medidas e o objeto 3D do site)."

    def add_arguments(self, parser):
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, fotos=False, **opcoes):
        super().handle(modelo="brinquedao-modelo-5", fotos=fotos, **opcoes)
