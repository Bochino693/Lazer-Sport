"""As capas em cena dos produtos do catálogo (core/capas_catalogo.py; LEIA-ME, seções 64 e 78).

    python manage.py capas_em_cena --simular            (lista o que faria)
    python manage.py capas_em_cena                       (todos os da lista de fundo branco)
    python manage.py capas_em_cena --so 13 "Sonic Kids"  (só estes: o id no site ou o nome)
    python manage.py capas_em_cena --desfazer [--so 13]  (a capa de antes volta)

As máquinas da Black Friday (o fundo de neon vermelho do cartaz e as fotos
panorâmicas: Basquete Duplo, Basquete Kids, Air Rock, Kid Play e as três
casinhas) e a foto da categoria "Casinhas Cenográficas" (seção 78):

    python manage.py capas_em_cena --vermelhas --simular
    python manage.py capas_em_cena --vermelhas
    python manage.py capas_em_cena --so "Basquete Kids"
    python manage.py capas_em_cena --vermelhas --desfazer (o recorte do cartaz volta)

A capa QUADRADA de cada adesivo dos nossos 3D (seção 80: o Air Game Kids
Astronautas e Alienígenas, o Basquete Home Quadrinhos, os Brinquedões Modelo 4
e 5 e os outros 3D; core/capas_quadradas.py):

    python manage.py capas_em_cena --quadradas --simular
    python manage.py capas_em_cena --quadradas
    python manage.py capas_em_cena --quadradas --so "Brinquedão Modelo 4" "Air Game Kids (Alienígenas)"
    python manage.py capas_em_cena --quadradas --desfazer

Normalmente nem é preciso: as migrações 0157, 0180 e 0186 fazem isso no deploy. A
foto em cena vira a capa; a de antes continua na galeria (na Black Friday, o
recorte do cartaz fica guardado, fora da galeria pública). Um produto cuja
capa a equipe já trocou no painel fica como está. Rodar de novo não duplica.
"""

from django.core.management.base import BaseCommand

from core import capas_catalogo, capas_quadradas
from core.models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, VarianteAdesivo


class Command(BaseCommand):
    help = "Põe (ou tira, com --desfazer) a capa em cena dos produtos do catálogo de fundo branco e da Black Friday."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="só lista o que faria")
        parser.add_argument("--so", nargs="+", default=(), help="só estes produtos (o id no site ou o nome)")
        parser.add_argument("--desfazer", action="store_true", help="volta a capa de antes")
        parser.add_argument("--vermelhas", action="store_true",
                            help="as máquinas da Black Friday (o fundo vermelho e as panorâmicas) e a categoria das casinhas")
        parser.add_argument("--quadradas", action="store_true",
                            help="a capa quadrada de cada adesivo dos nossos 3D (o Air Game Kids, o Basquete Home, os Brinquedões)")

    def handle(self, *args, simular=False, so=(), desfazer=False, vermelhas=False, quadradas=False, **opcoes):
        if quadradas:
            if so and not capas_quadradas.escolher(so):
                self.stdout.write("Nenhum item com esse nome. Os da lista:")
                for item in capas_quadradas.ITENS:
                    self.stdout.write(f"  {capas_quadradas._rotulo(item)}")
                return
            capas_quadradas.rodar(Brinquedos, ImagemBrinquedo, VarianteAdesivo, so=so, simular=simular,
                                  desfazer=desfazer, avisar=self.stdout.write)
            if not simular:
                from django.core.cache import cache

                cache.clear()  # os cards (as fotos que giram por adesivo), a página e a home
            return
        lista = capas_catalogo.VERMELHAS if vermelhas else None
        if so and not capas_catalogo.escolher(so, lista):
            self.stdout.write("Nenhum produto da lista com esse id ou nome. Os da lista:")
            for _chave, i, nome, _ in (lista or capas_catalogo.LISTA + capas_catalogo.VERMELHAS):
                self.stdout.write(f"  {i:>3}  {nome}")
            return
        capas_catalogo.rodar(
            Brinquedos, ImagemBrinquedo, so=so, simular=simular, desfazer=desfazer, avisar=self.stdout.write,
            lista=lista, CategoriasBrinquedos=CategoriasBrinquedos if vermelhas and not so else None,
        )
        if not simular:
            # o menu do topo guarda as categorias (neste processo); os cards caem pelos sinais das fotos
            from core.context_processors import limpar_cache_global

            limpar_cache_global()
