"""Cache dos dados e do fragmento público da página inicial.

Somente a vitrine compartilhada entre todos os visitantes entra aqui. Header,
carrinho, mensagens e dados de sessão continuam sendo renderizados por request.
"""

import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key


HOME_CONTEXT_CACHE_KEY = "home:public-context:v2"
HOME_FRAGMENT_NAME = "home_public_v2"
CATALOG_METADATA_CACHE_KEY = "catalog:public-metadata:v1"
ADMIN_CATALOG_VERSION_KEY = "catalog:admin-version:v1"


def home_cache_timeout():
    """Tempo configurável, com um mínimo que evita cache desligado por engano."""
    try:
        return max(60, int(getattr(settings, "HOME_CACHE_TTL", 1800)))
    except (TypeError, ValueError):
        return 1800


def catalog_cache_timeout():
    """TTL dos filtros públicos, sempre limitado a pelo menos um minuto."""
    try:
        return max(60, int(getattr(settings, "CATALOG_CACHE_TTL", 1800)))
    except (TypeError, ValueError):
        return 1800


def get_cached_home_context(builder):
    """Retorna a vitrine pública em cache ou a constrói uma única vez."""
    context = cache.get(HOME_CONTEXT_CACHE_KEY)
    if context is None:
        context = builder()
        cache.set(HOME_CONTEXT_CACHE_KEY, context, home_cache_timeout())

    # Evita que uma view altere acidentalmente o dicionário armazenado.
    return dict(context)


def get_cached_catalog_metadata(builder):
    """Cacheia somente metadados públicos e estáveis do catálogo.

    A lista filtrada, o usuário, o carrinho e a sessão nunca entram nesta
    chave. Assim, categorias, voltagens, totais e limites de preço deixam de
    consultar o banco a cada visita sem compartilhar informação privada.
    """
    metadata = cache.get(CATALOG_METADATA_CACHE_KEY)
    if metadata is None:
        metadata = builder()
        cache.set(
            CATALOG_METADATA_CACHE_KEY,
            metadata,
            catalog_cache_timeout(),
        )

    return dict(metadata)


def invalidate_home_cache():
    """Remove dados e HTML da Home para a próxima visita reconstruí-los."""
    cache.delete_many([
        HOME_CONTEXT_CACHE_KEY,
        make_template_fragment_key(HOME_FRAGMENT_NAME),
    ])


def invalidate_catalog_cache():
    """Expira os filtros públicos assim que o catálogo é alterado."""
    cache.delete(CATALOG_METADATA_CACHE_KEY)


def invalidate_public_catalog_caches():
    """Invalida de uma vez as duas vitrines derivadas do catálogo."""
    invalidate_home_cache()
    invalidate_catalog_cache()
    cache.delete(ADMIN_CATALOG_VERSION_KEY)


def admin_catalog_etag(request, tela):
    """ETag privado: o navegador só baixa a lista quando o catálogo mudou.

    A versão vive no cache e é removida pelos signals já ligados a produtos,
    imagens, categorias, tags e relações M2M. Assim a verificação não faz uma
    consulta extra ao banco e nunca compartilha a resposta autenticada.
    """
    versao = cache.get(ADMIN_CATALOG_VERSION_KEY)
    if versao is None:
        versao = str(time.time_ns())
        cache.set(ADMIN_CATALOG_VERSION_KEY, versao, 365 * 24 * 60 * 60)
    identidade = (
        f"{tela}|{request.get_full_path()}|{request.user.pk}|{versao}"
    ).encode("utf-8")
    return '"' + hashlib.sha256(identidade).hexdigest()[:32] + '"'


def aplicar_cache_condicional(response, etag):
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache, max-age=0, must-revalidate"
    response["Vary"] = "Cookie"
    return response
