"""Cache dos dados e do fragmento público da página inicial.

Somente a vitrine compartilhada entre todos os visitantes entra aqui. Header,
carrinho, mensagens e dados de sessão continuam sendo renderizados por request.
"""

from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key


HOME_CONTEXT_CACHE_KEY = "home:public-context:v2"
HOME_FRAGMENT_NAME = "home_public_v2"


def home_cache_timeout():
    """Tempo configurável, com um mínimo que evita cache desligado por engano."""
    try:
        return max(60, int(getattr(settings, "HOME_CACHE_TTL", 1800)))
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


def invalidate_home_cache():
    """Remove dados e HTML da Home para a próxima visita reconstruí-los."""
    cache.delete_many([
        HOME_CONTEXT_CACHE_KEY,
        make_template_fragment_key(HOME_FRAGMENT_NAME),
    ])
