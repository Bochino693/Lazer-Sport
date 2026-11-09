"""O mapa do site (/sitemap.xml).

O ENDEREÇO SAI DO SITE_URL, E NÃO DO CADASTRO "Sites" DO DJANGO. O mapa
pegava o domínio do registro `django.contrib.sites`, que ninguém edita e
nasce como "example.com": o Google recebia um mapa apontando para outro
site e o ignorava inteiro. Agora o domínio e o protocolo vêm de SITE_URL
(https://www.lazersport.com.br), o mesmo do `canonical` das páginas.

SÓ ENTRA O QUE ABRE. Brinquedo inativo dá 404 na página, e um mapa cheio
de 404 faz o Google confiar menos no mapa todo.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from . import arena, paginas_tema
from .models import Brinquedos, CategoriasBrinquedos, PecasReposicao


def _site():
    partes = urlsplit(str(getattr(settings, "SITE_URL", "") or "https://www.lazersport.com.br"))
    return partes.scheme or "https", partes.netloc or "www.lazersport.com.br"


class SitemapDoSite(Sitemap):
    """Todo mapa daqui fala o endereço público do site."""

    def get_protocol(self, protocol=None):
        return _site()[0]

    def get_domain(self, site=None):
        return _site()[1]


class PaginasEstaticasSitemap(SitemapDoSite):
    changefreq = "weekly"

    def items(self):
        return ["home", "brinquedos", "loja", "eventos", "projetos", "pecas_reposicao", "estabelecimentos", "arena", "jogos"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "home" else 0.8


class TemasSitemap(SitemapDoSite):
    """As páginas por tema de busca (boliche, fliperama...): as que disputam a palavra."""

    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return list(paginas_tema.TEMAS)

    def location(self, item):
        return reverse("pagina_tema", args=[item])


class JogosSitemap(SitemapDoSite):
    """Cada jogo do simulador tem a sua página."""

    priority = 0.6
    changefreq = "monthly"

    def items(self):
        return [jogo["slug"] for jogo in arena.JOGOS]

    def location(self, item):
        return reverse("jogo", args=[item])


class BrinquedosSitemap(SitemapDoSite):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Brinquedos.objects.filter(ativo=True).only("id", "atualizado").order_by("id")

    def location(self, obj):
        return reverse("brinquedo_detalhe", args=[obj.id])

    def lastmod(self, obj):
        return obj.atualizado


class CategoriasSitemap(SitemapDoSite):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return CategoriasBrinquedos.objects.filter(ativo=True).only("id", "atualizado").order_by("id")

    def location(self, obj):
        return reverse("categoria_detalhe", args=[obj.pk])

    def lastmod(self, obj):
        return obj.atualizado


class PecasSitemap(SitemapDoSite):
    """As peças de reposição que a vitrine mostra (item de manutenção fica de fora)."""

    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return PecasReposicao.da_vitrine().only("id", "atualizado").order_by("id")

    def location(self, obj):
        return reverse("reposicao_detalhe", args=[obj.id])

    def lastmod(self, obj):
        return obj.atualizado
