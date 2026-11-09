"""Cadastra as máquinas com os adesivos novos: o Air Game Hockey Espacial e o Basquete Street Quadrinhos.

    python manage.py cadastrar_variantes_adesivo
    python manage.py cadastrar_variantes_adesivo --so basquete-street-quadrinhos
    python manage.py cadastrar_variantes_adesivo --fotos   # refaz a galeria (as fotos novas do 3D)

Cada uma é a MESMA máquina do Air Game Hockey e do Basquete Street, só com
outra adesivagem: o cadastro novo copia da máquina de antes o preço, a
voltagem, a loja, a avaliação, as medidas, as categorias e as tags, e ganha a
descrição da arte nova, as fotos (vistas do próprio 3D) e o objeto 3D ligado.
O mesmo que `cadastrar_modelo_3d <id>` para cada uma. Normalmente nem é
preciso: a migração 0145 cadastra no deploy (ver `core/cadastro_modelos.py`).
Se a máquina já está no catálogo (cadastrada no painel), só ganha o objeto
3D. Rodar de novo não duplica. Quando a folha de adesivos chegar e o 3D e as
fotos forem refeitos (ferramentas/modelos3d/<id>/README.md), rode com `--fotos`.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.cadastro_modelos import VARIANTES_DE_ADESIVO


class Command(BaseCommand):
    help = "Cadastra o Air Game Hockey Espacial e o Basquete Street Quadrinhos (copiando a máquina de antes) com o objeto 3D."

    def add_arguments(self, parser):
        parser.add_argument("--so", nargs="+", choices=VARIANTES_DE_ADESIVO, help="só estas")
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, so=None, fotos=False, **opcoes):
        for chave in so or VARIANTES_DE_ADESIVO:
            call_command("cadastrar_modelo_3d", chave, fotos=fotos, stdout=self.stdout)
