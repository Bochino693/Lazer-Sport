"""Põe nas categorias as fotos novas do repositório (e, se pedir, refaz os nomes e as áreas).

    python manage.py atualizar_capas_categorias                 # as fotos que faltam
    python manage.py atualizar_capas_categorias --simular       # só diz o que faria
    python manage.py atualizar_capas_categorias --so kids fliperama
    python manage.py atualizar_capas_categorias --refazer       # sobe de novo, mesmo as que já estão
    python manage.py atualizar_capas_categorias --areas         # cria as áreas que ganharam produto
    python manage.py atualizar_capas_categorias --nomes         # passa os nomes em caixa-alta para Maiúsculas e Minúsculas

Normalmente nem é preciso: a migração 0147 faz tudo no deploy do Render. É
para quando a subida para o Cloudinary falhou ali, quando as fotos de
core/static/site/categorias/ foram refeitas (ferramentas/categorias/) ou
quando um produto de área nova entrou no catálogo (um "Área Baby" ativo
faz nascer a categoria Área Baby, já com a foto). Cada categoria é
reconhecida pelo nome (core/categorias_capas.py, CAPAS); a foto sobe com a
assinatura do arquivo no nome, então rodar de novo não sobe o que já está lá.
"""

from django.core.management.base import BaseCommand

from core import categorias_capas
from core.context_processors import limpar_cache_global
from core.models import Brinquedos, CategoriaPeca, CategoriasBrinquedos, PecasReposicao


class Command(BaseCommand):
    help = "Põe nas categorias as fotos de core/static/site/categorias/ (e refaz nomes e áreas, se pedir)."

    def add_arguments(self, parser):
        chaves = [chave for chave, _ in categorias_capas.CAPAS]
        parser.add_argument("--so", nargs="+", choices=chaves, metavar="CHAVE", help="só estas fotos: " + ", ".join(chaves))
        parser.add_argument("--refazer", action="store_true", help="sobe de novo mesmo a foto que já está na categoria")
        parser.add_argument("--simular", action="store_true", help="não muda nada: só diz o que faria")
        parser.add_argument("--areas", action="store_true", help="cria as categorias de área que já têm produto e liga os produtos")
        parser.add_argument("--nomes", action="store_true", help="os nomes em caixa-alta viram Maiúsculas e Minúsculas")

    def handle(self, *args, so=None, refazer=False, simular=False, areas=False, nomes=False, **opcoes):
        avisar = self.stdout.write
        if nomes and not simular:
            trocas = categorias_capas.arrumar_nomes(Brinquedos, CategoriasBrinquedos, PecasReposicao, CategoriaPeca, avisar=avisar)
            avisar(f"Nomes arrumados: {len(trocas)}.")
        if areas and not simular:
            categorias_capas.garantir_areas(Brinquedos, CategoriasBrinquedos, avisar=avisar)
        resultado = categorias_capas.atualizar_capas(
            CategoriasBrinquedos, so=tuple(so or ()), refazer=refazer, simular=simular, avisar=avisar,
        )
        if not simular:
            # o menu do topo guarda as categorias por 10 minutos (neste processo)
            limpar_cache_global()
        verbo = "subiriam" if simular else "trocadas"
        self.stdout.write(self.style.SUCCESS(
            f"Fotos {verbo}: {len(resultado['trocadas'])}; já estavam certas: {len(resultado['iguais'])}; "
            f"sem foto no repositório: {len(resultado['sem_foto'])}."
        ))
