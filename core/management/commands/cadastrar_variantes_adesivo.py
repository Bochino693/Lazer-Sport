"""Cadastra as máquinas com os adesivos novos: o Air Game Kids Alienígenas e o Basquete Street Quadrinhos.

    python manage.py cadastrar_variantes_adesivo
    python manage.py cadastrar_variantes_adesivo --so air-game-kids-alienigenas
    python manage.py cadastrar_variantes_adesivo --so basquete-street-quadrinhos
    python manage.py cadastrar_variantes_adesivo --fotos   # refaz a galeria (as fotos novas do 3D)

Cada uma é a MESMA máquina do Air Game Kids e do Basquete Street, só com
outra adesivagem: o cadastro novo copia da máquina de antes o preço, a
voltagem, a loja, a avaliação, as medidas, as categorias e as tags, e ganha a
descrição da arte nova, as fotos (vistas do próprio 3D) e o objeto 3D ligado.
O mesmo que `cadastrar_modelo_3d <id>` para cada uma. Normalmente nem é
preciso: as migrações 0145 e 0146 cadastram no deploy (ver
`core/cadastro_modelos.py`). O Air Game Kids Alienígenas se chamava "Air Game
Hockey Espacial" (`--so air-game-hockey-espacial` ainda vale: é o novo); se
sobrou um com o nome antigo, este comando o renomeia antes, como a 0146.
Se a máquina já está no catálogo (cadastrada no painel), só ganha o objeto
3D. Rodar de novo não duplica. O 3D e as fotos saem da folha de adesivos da
fábrica (ferramentas/modelos3d/<id>/README.md): quando forem refeitos (uma
folha nova), ou se o produto foi cadastrado antes da arte de verdade, rode com
`--fotos`.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.cadastro_modelos import APELIDOS, CADASTROS, VARIANTES_DE_ADESIVO, _chave, renomear_variante
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD


class Command(BaseCommand):
    help = "Cadastra o Air Game Kids Alienígenas e o Basquete Street Quadrinhos (copiando a máquina de antes) com o objeto 3D."

    def add_arguments(self, parser):
        parser.add_argument("--so", nargs="+", choices=VARIANTES_DE_ADESIVO + tuple(APELIDOS), help="só estas")
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, so=None, fotos=False, **opcoes):
        for chave in dict.fromkeys(_chave(c) for c in so or VARIANTES_DE_ADESIVO):
            # o cadastro com o nome de antes (o da 0145) passa para o de hoje, como a 0146
            for antiga, nome_antigo in CADASTROS[chave].get("antes", {}).items():
                renomear_variante(antiga, nome_antigo, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD,
                                  avisar=self.stdout.write)
            call_command("cadastrar_modelo_3d", chave, fotos=fotos, stdout=self.stdout)
