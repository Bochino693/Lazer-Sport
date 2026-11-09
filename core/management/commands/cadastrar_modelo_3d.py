"""Cadastra no catálogo um brinquedo que já tem o objeto 3D feito aqui.

    python manage.py cadastrar_modelo_3d espaco-esportivo-modelo-1
    python manage.py cadastrar_modelo_3d brinquedao-modelo-2
    python manage.py cadastrar_modelo_3d brinquedao-ninja
    python manage.py cadastrar_modelo_3d brinquedao-modelo-4
    python manage.py cadastrar_modelo_3d strike-kids

Normalmente nem é preciso: as migrações de dados cadastram no deploy. Este
comando é para quando elas não conseguiram (ver `core/cadastro_modelos.py`).
Rodar de novo não duplica; `--fotos` refaz a galeria. O brinquedo ganha
também o objeto 3D no cadastro (`ObjetoTresD`); se ele já está no catálogo
(o Strike Kids pode estar como "Boliche Kids"), só é ligado e as fotos
reais dele ficam.
"""

from django.core.management.base import BaseCommand

from core.cadastro_modelos import CADASTROS, achar_no_catalogo, cadastrar, garantir_strike_kids, ligar_objeto_3d
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD


class Command(BaseCommand):
    help = "Cadastra um brinquedo que já tem o objeto 3D no site (fotos, medidas e categoria)."

    def add_arguments(self, parser):
        parser.add_argument("modelo", choices=sorted(CADASTROS), help="qual brinquedo")
        parser.add_argument("--fotos", action="store_true", help="refaz a galeria de um cadastro que já existe")

    def handle(self, *args, modelo, fotos=False, **opcoes):
        dados = CADASTROS[modelo]
        if modelo == "strike-kids" and not fotos:
            # conta o que achou no banco e deixa ativo, com as fotos e o 3D;
            # um erro (a subida das fotos, por exemplo) aparece aqui na tela
            garantir_strike_kids(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ObjetoTresD, avisar=self.stdout.write)
            return
        brinquedo = achar_no_catalogo(modelo, Brinquedos) if "objeto_3d" in dados else None
        if brinquedo is None or fotos:
            brinquedo, _criado = cadastrar(
                modelo, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=fotos, avisar=self.stdout.write,
            )
        if "objeto_3d" in dados:
            ligar_objeto_3d(modelo, brinquedo, ObjetoTresD)
            self.stdout.write(f"Objeto 3D ligado a {brinquedo.nome_brinquedo} (id {brinquedo.pk}).")
