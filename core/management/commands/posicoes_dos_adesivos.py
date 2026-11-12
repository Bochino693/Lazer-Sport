"""Sobe as posições tiradas do 3D como fotos do adesivo (core.variantes.POSICOES_DO_3D; LEIA-ME 72).

    python manage.py posicoes_dos_adesivos

Pode rodar de novo: a posição que o adesivo já tem fica.
"""

from django.core.management.base import BaseCommand

from core import variantes
from core.models import Brinquedos, ImagemBrinquedo, VarianteAdesivo


class Command(BaseCommand):
    help = "Sobe as posições tiradas do 3D (os Astronautas do Air Game Kids) como fotos do adesivo."

    def handle(self, *args, **opcoes):
        variantes.subir_posicoes(Brinquedos, VarianteAdesivo, ImagemBrinquedo, avisar=self.stdout.write)
