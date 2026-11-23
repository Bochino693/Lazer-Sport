"""Grava site/fotos-reserva.json: as cópias locais das fotos do Cloudinary.

Rode depois de acrescentar uma capa, arte de kit, categoria ou arte da
Black Friday em core/static/site/ (o teste tests_foto_reserva reprova a
lista desatualizada).

    python manage.py fotos_reserva
"""

from django.core.management.base import BaseCommand

from core.fotos_reserva import gravar_indice, montar_indice


class Command(BaseCommand):
    help = "Grava a lista das cópias locais das fotos (reserva quando o Cloudinary não entrega)."

    def handle(self, *args, **options):
        caminho = gravar_indice()
        indice = montar_indice()
        total = sum(len(grupo) for grupo in indice.values())
        self.stdout.write(self.style.SUCCESS(f"{total} fotos de reserva em {caminho}"))
