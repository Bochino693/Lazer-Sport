"""Cria, como produtos, os kits eletrônicos iniciais que faltam; com --foto, sobe a arte.

    python manage.py kits_eletronicos            # os kits que faltam (sem tocar nos que existem)
    python manage.py kits_eletronicos --foto     # também a arte do repositório, no kit sem foto (Cloudinary)

O kit é um produto (LEIA-ME seção 107): um `Brinquedos` com `eh_kit`, na
categoria "Kits eletrônicos" e nas da máquina dele. Normalmente nem é
preciso rodar: os kits de produção vieram da migração 0212 (que converteu as
peças-kit). É para um banco novo ou quando um kit inicial foi apagado e o
dono o quer de volta. Os kits são reconhecidos pelo nome (core/kits.py,
KITS_INICIAIS): rodar de novo não duplica nada, e o kit que já tem foto não
ganha outra.
"""

from django.core.management.base import BaseCommand

from core import kits


class Command(BaseCommand):
    help = "Cria os kits eletrônicos iniciais que faltam, como produtos (e sobe a arte com --foto)."

    def add_arguments(self, parser):
        parser.add_argument("--foto", action="store_true",
                            help="sobe a arte do repositório para o kit que ainda não tem foto (Cloudinary)")

    def handle(self, *args, foto=False, **opcoes):
        avisar = self.stdout.write
        resultado = kits.criar_kits_iniciais(avisar=avisar)
        mensagem = f"Kits criados: {len(resultado['criados'])}; já existiam: {len(resultado['existentes'])}."
        if foto:
            fotos = kits.subir_fotos(avisar=avisar)
            mensagem += (f" Fotos: {len(fotos['subidas'])} subida(s), {len(fotos['ja_tinham'])} já tinha(m), "
                         f"{len(fotos['falhas'])} falha(s).")
        kits.limpar_cache()
        self.stdout.write(self.style.SUCCESS(mensagem))
