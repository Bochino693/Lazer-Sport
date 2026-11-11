"""As capas em cena dos produtos do catálogo (core/capas_catalogo.py; LEIA-ME, seção 64).

    python manage.py capas_em_cena --simular            (lista o que faria)
    python manage.py capas_em_cena                       (todos os da lista)
    python manage.py capas_em_cena --so 13 "Sonic Kids"  (só estes: o id no site ou o nome)
    python manage.py capas_em_cena --desfazer [--so 13]  (a capa de antes volta)

Normalmente nem é preciso: a migração 0156 faz isso no deploy. A foto em cena
vira a capa; a de antes continua na galeria. Um produto cuja capa a equipe já
trocou no painel fica como está. Rodar de novo não duplica.
"""

from django.core.management.base import BaseCommand

from core import capas_catalogo
from core.models import Brinquedos, ImagemBrinquedo


class Command(BaseCommand):
    help = "Põe (ou tira, com --desfazer) a capa em cena dos produtos do catálogo de fundo branco."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="só lista o que faria")
        parser.add_argument("--so", nargs="+", default=(), help="só estes produtos (o id no site ou o nome)")
        parser.add_argument("--desfazer", action="store_true", help="volta a capa de antes")

    def handle(self, *args, simular=False, so=(), desfazer=False, **opcoes):
        if so and not capas_catalogo.escolher(so):
            self.stdout.write("Nenhum produto da lista com esse id ou nome. Os da lista:")
            for chave, i, nome, _ in capas_catalogo.LISTA:
                self.stdout.write(f"  {i:>3}  {nome}")
            return
        capas_catalogo.rodar(Brinquedos, ImagemBrinquedo, so=so, simular=simular, desfazer=desfazer, avisar=self.stdout.write)
