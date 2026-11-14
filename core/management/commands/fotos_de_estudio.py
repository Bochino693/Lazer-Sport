"""As fotos de estúdio dos nossos 3D no cadastro (core/fotos_estudio.py; LEIA-ME, seção 96).

    python manage.py fotos_de_estudio --simular            (lista o que faria)
    python manage.py fotos_de_estudio                       (todas)
    python manage.py fotos_de_estudio --so "Strike Kids"    (o produto, o adesivo ou "produto (adesivo)")
    python manage.py fotos_de_estudio --desfazer            (as fotos de antes voltam)

Normalmente nem é preciso: a migração 0197 faz isso no deploy. Refez as fotos
(ferramentas/fotos3d/renderizar.py --site)? Rode de novo: só as que mudaram sobem.
"""

from django.core.management.base import BaseCommand

from core import fotos_estudio
from core.models import Brinquedos, ImagemBrinquedo, VarianteAdesivo


class Command(BaseCommand):
    help = "Põe (ou tira, com --desfazer) as fotos de estúdio do Basquete Home, do Air Game Kids e do Strike Kids."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="só lista o que faria")
        parser.add_argument("--so", nargs="+", default=(), help="só estes (o produto, o adesivo ou \"produto (adesivo)\")")
        parser.add_argument("--desfazer", action="store_true", help="volta as fotos de antes")

    def handle(self, *args, simular=False, so=(), desfazer=False, **opcoes):
        if so and not fotos_estudio.escolher(so):
            self.stdout.write("Nenhum item com esse nome. Os da lista:")
            for produto, adesivo, _fotos in fotos_estudio.ITENS:
                self.stdout.write(f"  {fotos_estudio._rotulo(produto, adesivo)}")
            return
        fotos_estudio.rodar(Brinquedos, ImagemBrinquedo, VarianteAdesivo, so=so, simular=simular,
                            desfazer=desfazer, avisar=self.stdout.write)
