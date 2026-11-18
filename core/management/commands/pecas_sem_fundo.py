"""As fotos das peças de reposição sem o fundo branco (LEIA-ME, seção 102).

    python manage.py pecas_sem_fundo --simular          (só diz o que faria)
    python manage.py pecas_sem_fundo                    (as fotos ainda não conferidas)
    python manage.py pecas_sem_fundo --so 3 7           (só as peças 3 e 7: o id no site)
    python manage.py pecas_sem_fundo --desfazer [--so 3] (a foto que a equipe subiu volta)
    python manage.py pecas_sem_fundo --refazer --so 3   (confere de novo, mesmo já conferida)

Normalmente nem é preciso: a migração 0205 faz isso no deploy e a foto nova
subida pelo painel é recortada sozinha logo depois de salvar. Precisa do
Cloudinary (rode no Render). Rodar de novo não refaz a que já foi conferida.
"""

from django.core.management.base import BaseCommand

from core import recorte_peca
from core.models import ImagemPeca


class Command(BaseCommand):
    help = "Tira o fundo branco das fotos das peças de reposição (ou, com --desfazer, devolve a foto original)."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="só diz o que faria")
        parser.add_argument("--so", nargs="+", type=int, default=(), help="só estas peças (o id no site)")
        parser.add_argument("--desfazer", action="store_true", help="devolve a foto que a equipe subiu")
        parser.add_argument("--refazer", action="store_true", help="confere de novo as já conferidas (desfaz antes)")

    def handle(self, *args, simular=False, so=(), desfazer=False, refazer=False, **opcoes):
        fotos = ImagemPeca.objects.exclude(imagem="").exclude(imagem__isnull=True).order_by("pk")
        if so:
            fotos = fotos.filter(peca_reposicao_id__in=so)
        if desfazer or refazer:
            for foto in fotos:
                if simular:
                    if foto.imagem_original:
                        self.stdout.write(f"  foto {foto.pk}: voltaria para {foto.imagem_original.name}")
                    continue
                if recorte_peca.desfazer(foto):
                    self.stdout.write(f"  foto {foto.pk}: a original voltou")
                if refazer:
                    type(foto).objects.filter(pk=foto.pk).update(recorte_de="")
            if desfazer:
                recorte_peca._limpar_cache()
                return
        if simular:
            pendentes = [f for f in fotos if recorte_peca.precisa_conferir(f)]
            self.stdout.write(f"{len(pendentes)} fotos seriam conferidas: " + ", ".join(str(f.pk) for f in pendentes))
            return
        resumo = recorte_peca.processar_todas(ImagemPeca, avisar=self.stdout.write, so=so or None)
        recorte_peca._limpar_cache()
        self.stdout.write(
            f"Recortadas: {resumo['recortada']} · sem fundo branco (ficam como estão): {resumo['sem_recorte']} · "
            f"já conferidas: {resumo['ja_conferida']} · não deu agora: {resumo['falhou']}"
        )
