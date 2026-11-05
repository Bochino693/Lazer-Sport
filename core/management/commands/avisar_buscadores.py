"""python manage.py avisar_buscadores -- manda as páginas do sitemap ao IndexNow (Bing e outros)."""
from django.core.management.base import BaseCommand, CommandError

from core import indexnow


class Command(BaseCommand):
    help = "Avisa o Bing (IndexNow) das páginas do sitemap. Rode depois de cada publicação."

    def handle(self, *args, **opcoes):
        try:
            enderecos = indexnow.enderecos_do_sitemap()
            resultado = indexnow.avisar(enderecos)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        # 200 e 202 são "recebido"; 422 quer dizer endereço fora do domínio da chave
        self.stdout.write(f"IndexNow respondeu {resultado['status']} para {resultado['enviados']} páginas.")
