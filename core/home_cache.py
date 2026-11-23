"""Cache dos dados públicos do catálogo: a home e as telas de produto.

Somente o que é IGUAL PARA TODO VISITANTE entra aqui: a vitrine da home,
os filtros do catálogo e, desde o teste de carga (docs/TESTE_DE_CARGA.md),
os dados de cada tela pública do catálogo -- a lista de brinquedos com os
seus filtros, a página de categoria, a ficha do brinquedo, as peças e o
simulador de jogos. Header, carrinho, mensagens, sessão e o que ESTE
visitante marcou (curtida, lista de desejos, posição no ranking) continuam
sendo resolvidos a cada requisição, fora do cache.

POR QUE ISTO EXISTE. Cada consulta ao banco custa uma ida e volta pela
rede até o Supabase (20-60 ms); uma tela de catálogo fazia de 8 a 12, e
cada uma ocupava uma das poucas vagas públicas do escudo de tráfego por
0,3-0,5 s. Com os dados em cache a tela sai com 0-1 consulta e a mesma
instância atende dez vezes mais gente.

COMO A INVALIDAÇÃO FUNCIONA. Toda chave de tela leva a VERSÃO do catálogo
(`versao_do_catalogo`), que vive no cache e é apagada pelos signals ligados
a produtos, fotos, categorias, tags, peças, jogos e objetos 3D
(core/signals.py). Mudou o cadastro, a versão muda e TODAS as chaves
antigas morrem no mesmo instante, sem varrer o cache. O TTL
(`CATALOG_CACHE_TTL`) é só a rede de segurança.

ATENÇÃO COM MAIS DE UM WORKER. O cache é `LocMemCache`: memória do
processo. Com `WEB_WORKERS=2`, a edição feita pelo worker A invalida só a
versão do worker A; o B segue com a cópia velha até o TTL. Antes de subir
`WEB_WORKERS`, configure um cache compartilhado (Redis) em `CACHES`.
"""

import hashlib
import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.core.paginator import Paginator


HOME_CONTEXT_CACHE_KEY = "home:public-context:v4"
HOME_FRAGMENT_NAME = "home_public_v6"
CATALOG_METADATA_CACHE_KEY = "catalog:public-metadata:v1"
ADMIN_CATALOG_VERSION_KEY = "catalog:admin-version:v1"
CATALOG_PAGE_CACHE_PREFIX = "catalog:page:v1"


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


log = logging.getLogger("core.home_cache")

# ----------------------------------------------------------------------
# A TELA VENCIDA SAI NA HORA E SE REMONTA EM SEGUNDO PLANO (seção 132)
# ----------------------------------------------------------------------
# Antes, quando o prazo da home (30 min) vencia, o PRÓXIMO visitante
# esperava a remontagem inteira: ~50 consultas ao Supabase, 8,8 s medidos no
# ar em 23/11. Agora cada valor é guardado com a hora em que foi montado e
# vive no cache por GUARDA vezes o prazo. Vencido o prazo, quem chega leva a
# versão de antes, na hora, e uma linha de fundo remonta (uma por chave: a
# trava no próprio cache). Só o cache VAZIO (o site acabou de subir, alguém
# editou o catálogo) ainda monta na frente do visitante -- e esse caso o
# aquecimento (core/aquecer.py) já cobre.
GUARDA = 6


def _envelope(valor):
    return {"_feito_em": time.time(), "_valor": valor}


def _e_envelope(guardado):
    return isinstance(guardado, dict) and "_feito_em" in guardado and "_valor" in guardado


def _renovar(chave, builder, prazo, depois=None):
    """Remonta `chave` sem tirar a versão de antes do lugar (uma linha por chave)."""
    trava = chave + ":renovando"
    if not cache.add(trava, 1, 120):
        return False

    def tarefa():
        from django.db import close_old_connections, connection

        try:
            close_old_connections()
            valor = builder()
            if not (isinstance(valor, dict) and valor.pop("_descartavel", False)):
                cache.set(chave, _envelope(valor), prazo * GUARDA)
            if depois is not None:
                depois()
        except Exception:  # noqa: BLE001 -- quem chega segue com a versão de antes
            log.warning("cache: não deu para remontar %s", chave, exc_info=True)
        finally:
            cache.delete(trava)
            if threading.current_thread() is not threading.main_thread():
                connection.close()

    if getattr(settings, "CACHE_RENOVA_EM_SEGUNDO_PLANO", True):
        threading.Thread(target=tarefa, name="renovar-cache", daemon=True).start()
    else:  # nos testes: na mesma linha, para dar para conferir
        tarefa()
    return True


def com_renovacao(chave, builder, prazo, depois=None):
    """O valor de `chave`: montado na hora só se o cache não tem nenhum; vencido, sai e se remonta."""
    guardado = cache.get(chave)
    if not _e_envelope(guardado):
        valor = builder()
        if isinstance(valor, dict) and valor.pop("_descartavel", False):
            return valor
        cache.set(chave, _envelope(valor), prazo * GUARDA)
        return valor
    if time.time() - guardado["_feito_em"] > prazo:
        _renovar(chave, builder, prazo, depois)
    return guardado["_valor"]


def _home_remontada():
    # a vitrine nova pede o HTML novo: o fragmento sai e o aquecimento o monta
    cache.delete(make_template_fragment_key(HOME_FRAGMENT_NAME))
    from .aquecer import agendar

    agendar(atraso=0.5, motivo="home remontada", paginas=("/",))


def get_cached_home_context(builder):
    """Retorna a vitrine pública em cache ou a constrói uma única vez."""
    context = com_renovacao(HOME_CONTEXT_CACHE_KEY, builder, home_cache_timeout(), depois=_home_remontada)

    # Evita que uma view altere acidentalmente o dicionário armazenado.
    return dict(context)


def get_cached_catalog_metadata(builder):
    """Cacheia somente metadados públicos e estáveis do catálogo.

    A lista filtrada, o usuário, o carrinho e a sessão nunca entram nesta
    chave. Assim, categorias, voltagens, totais e limites de preço deixam de
    consultar o banco a cada visita sem compartilhar informação privada.
    """
    metadata = com_renovacao(CATALOG_METADATA_CACHE_KEY, builder, catalog_cache_timeout())
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
    """Invalida de uma vez tudo o que deriva do catálogo.

    Apagar a versão basta para as telas do catálogo: a próxima visita
    ganha uma versão nova e, com ela, chaves novas. As entradas antigas
    ficam no cache até o TTL (ninguém mais as pede) ou até o `LocMemCache`
    descartá-las quando precisar de espaço.
    """
    invalidate_home_cache()
    invalidate_catalog_cache()
    cache.delete(ADMIN_CATALOG_VERSION_KEY)
    # o próximo visitante não paga a reconstrução: o servidor aquece sozinho
    from .aquecer import agendar

    agendar(motivo="catálogo mudou")


def versao_do_catalogo():
    """A versão atual do catálogo: parte de toda chave de cache pública.

    Nasce do relógio na primeira leitura e vive no cache até um signal a
    apagar (`invalidate_public_catalog_caches`). Não custa consulta ao
    banco. `cache.add` + `get` garante que duas threads que chegam juntas
    ao cache vazio fiquem com a MESMA versão.
    """
    versao = cache.get(ADMIN_CATALOG_VERSION_KEY)
    if versao is None:
        nova = str(time.time_ns())
        cache.add(ADMIN_CATALOG_VERSION_KEY, nova, 365 * 24 * 60 * 60)
        versao = cache.get(ADMIN_CATALOG_VERSION_KEY) or nova
    return versao


def chave_de_tela(tela, *partes):
    """A chave de uma tela pública: tela + versão do catálogo + o que a distingue.

    `partes` é o que muda o conteúdo para TODO MUNDO (id, ordem, filtro,
    página) -- nunca algo do visitante. Vai tudo num hash: a querystring
    não limita o tamanho da chave nem entra nela com caractere estranho.
    """
    identidade = "|".join([tela, versao_do_catalogo(), *(str(parte) for parte in partes)])
    resumo = hashlib.sha256(identidade.encode("utf-8")).hexdigest()[:32]
    return f"{CATALOG_PAGE_CACHE_PREFIX}:{tela}:{resumo}"


def get_cached_catalog_page(tela, partes, builder):
    """Os dados públicos de uma tela do catálogo, construídos uma vez por versão.

    `builder()` devolve um dicionário com tudo o que é igual para todo
    visitante (objetos já com `prefetch_related`, totais, textos). Se ele
    levantar (Http404, por exemplo), nada é guardado. Um dicionário com
    `"_descartavel": True` é devolvido mas não guardado -- é o caso de uma
    página fora do intervalo, que um robô poderia pedir aos milhares.
    """
    chave = chave_de_tela(tela, *partes)
    return com_renovacao(chave, builder, catalog_cache_timeout())


def dados_da_pagina(page_obj):
    """O que de uma página do paginador vale guardar: itens, número e total.

    Guardar o próprio `Page` arrastaria o queryset inteiro do paginador
    para o cache (e o avaliaria todo ao serializar). Aqui vão só os itens
    desta página, já avaliados, e dois números.
    """
    return {
        "itens": list(page_obj.object_list),
        "numero": page_obj.number,
        "total": page_obj.paginator.count,
        "por_pagina": page_obj.paginator.per_page,
    }


def pagina_de_cache(dados):
    """Reconstrói o `Page` a partir de `dados_da_pagina`, sem tocar no banco.

    O paginador recebe um `range` do tamanho do total -- o bastante para
    `num_pages`, `page_range`, `has_next`, `start_index`... darem as mesmas
    respostas de antes -- e a lista de objetos da página entra por cima.
    """
    paginador = Paginator(range(dados["total"]), dados["por_pagina"])
    pagina = paginador.page(dados["numero"])
    pagina.object_list = list(dados["itens"])
    return pagina


def admin_catalog_etag(request, tela):
    """ETag privado: o navegador só baixa a lista quando o catálogo mudou.

    A versão vive no cache e é removida pelos signals já ligados a produtos,
    imagens, categorias, tags e relações M2M. Assim a verificação não faz uma
    consulta extra ao banco e nunca compartilha a resposta autenticada.
    """
    versao = versao_do_catalogo()
    identidade = (
        f"{tela}|{request.get_full_path()}|{request.user.pk}|{versao}"
    ).encode("utf-8")
    return '"' + hashlib.sha256(identidade).hexdigest()[:32] + '"'


def aplicar_cache_condicional(response, etag):
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache, max-age=0, must-revalidate"
    response["Vary"] = "Cookie"
    return response
