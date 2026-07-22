from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Brinquedos, CategoriasBrinquedos


class PaginasEstaticasSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["home", "brinquedos", "eventos", "projetos", "pecas_reposicao", "estabelecimentos"]

    def location(self, item):
        return reverse(item)


class BrinquedosSitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Brinquedos.objects.all()

    def location(self, obj):
        return reverse("brinquedo_detalhe", args=[obj.id])

    def lastmod(self, obj):
        return obj.atualizado


class CategoriasSitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return CategoriasBrinquedos.objects.all()

    def location(self, obj):
        return reverse("categoria_detalhe", args=[obj.pk])

    def lastmod(self, obj):
        return obj.atualizado