"""As fotos sem fundo (branca ou transparente) saem do site e ficam como recorte para artes (LEIA-ME 72).

    python manage.py fotos_sem_fundo --simular     # só lista o que marcaria
    python manage.py fotos_sem_fundo              # marca (a mesma varredura da 0177)
    python manage.py fotos_sem_fundo --com-black-friday

Confere só as fotos ainda não conferidas; pode rodar de novo. Nada é apagado.
"""

from django.core.management.base import BaseCommand

from core import conferir_fotos
from core.models import Brinquedos, ImagemBrinquedo


class Command(BaseCommand):
    help = "Confere o fundo das fotos: a sem fundo vira recorte para artes (fora do site); a capa sem fundo dá lugar a uma com fundo."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="Só lista o que marcaria (não muda nada).")
        parser.add_argument("--com-black-friday", action="store_true",
                            help="Confere também as máquinas da Black Friday (por padrão ficam de fora).")

    def handle(self, *args, **opcoes):
        simular = opcoes["simular"]
        resumo = conferir_fotos.marcar_sem_fundo(
            Brinquedos, ImagemBrinquedo, simular=simular, avisar=self.stdout.write,
            com_black_friday=opcoes["com_black_friday"],
        )
        verbo = "marcaria" if simular else "marcou"
        self.stdout.write(f"{resumo['conferidas']} fotos conferidas; {verbo} {len(resumo['marcadas'])} como recorte para artes:")
        for linha in resumo["marcadas"]:
            self.stdout.write(f"  - {linha}")
        if resumo["capas"]:
            self.stdout.write(f"Capas sem fundo {'que dariam' if simular else 'que deram'} lugar a uma com fundo: "
                              + ", ".join(resumo["capas"]))
        if resumo["sem_foto_com_fundo"]:
            self.stdout.write("PRECISAM DE FOTO COM FUNDO (o site mostra o que tem): " + ", ".join(resumo["sem_foto_com_fundo"]))
        if resumo["falhas"]:
            self.stdout.write(f"{len(resumo['falhas'])} fotos não foram conferidas agora (rode de novo):")
            for linha in resumo["falhas"]:
                self.stdout.write(f"  - {linha}")
        if resumo["black_friday"]:
            self.stdout.write("Black Friday (de fora; use --com-black-friday): " + ", ".join(resumo["black_friday"]))
