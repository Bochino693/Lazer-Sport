from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from . import arena
from .models import Brinquedos, CategoriasBrinquedos


class PaginasEstaticasSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["home", "brinquedos", "eventos", "projetos", "pecas_reposicao", "estabelecimentos", "arena", "jogos"]

    def location(self, item):
        return reverse(item)


class JogosSitemap(Sitemap):
    """Cada jogo do simulador tem a sua página."""

    priority = 0.6
    changefreq = "monthly"

    def items(self):
        return [jogo["slug"] for jogo in arena.JOGOS]

    def location(self, item):
        return reverse("jogo", args=[item])


class BrinquedosSitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Brinquedos.objects.only("id", "atualizado").order_by("id")

    def location(self, obj):
        return reverse("brinquedo_detalhe", args=[obj.id])

    def lastmod(self, obj):
        return obj.atualizado


class CategoriasSitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return CategoriasBrinquedos.objects.only("id", "atualizado").order_by("id")

    def location(self, obj):
        return reverse("categoria_detalhe", args=[obj.pk])

    def lastmod(self, obj):
        return obj.atualizado