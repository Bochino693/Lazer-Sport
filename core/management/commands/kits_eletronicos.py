"""Cria os kits eletrônicos iniciais que faltam e, se pedir, sobe a foto de capa.

    python manage.py kits_eletronicos            # os kits que faltam (sem tocar nos que existem)
    python manage.py kits_eletronicos --foto     # também a arte do Kit Boliche Virtual (Cloudinary)

Normalmente nem é preciso: a migração 0208 faz isso no deploy do Render. É
para quando a foto não subiu ali (o aviso do deploy diz) ou quando um kit
inicial foi apagado e o dono quer de volta. Os kits são reconhecidos pelo nome
(core/kits.py, KITS_INICIAIS): rodar de novo não duplica nada, e o kit que já
tem foto não ganha outra.
"""

from django.core.management.base import BaseCommand

from core import kits
from core.models import Brinquedos, ComponenteKit, ImagemPeca, PecasReposicao


class Command(BaseCommand):
    help = "Cria os kits eletrônicos iniciais que faltam (e sobe a foto de capa com --foto)."

    def add_arguments(self, parser):
        parser.add_argument("--foto", action="store_true",
                            help="sobe a arte do repositório para o kit que ainda não tem foto (Cloudinary)")

    def handle(self, *args, foto=False, **opcoes):
        avisar = self.stdout.write
        resultado = kits.criar_kits_iniciais(PecasReposicao, Brinquedos, ComponenteKit, avisar=avisar)
        mensagem = f"Kits criados: {len(resultado['criados'])}; já existiam: {len(resultado['existentes'])}."
        if foto:
            fotos = kits.subir_fotos(PecasReposicao, ImagemPeca, avisar=avisar)
            mensagem += (f" Fotos: {len(fotos['subidas'])} subida(s), {len(fotos['ja_tinham'])} já tinha(m), "
                         f"{len(fotos['falhas'])} falha(s).")
        kits.limpar_cache()
        self.stdout.write(self.style.SUCCESS(mensagem))
