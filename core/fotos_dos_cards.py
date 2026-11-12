"""As fotos que giram nos cards dos brinquedos (LEIA-ME, seção 72).

O cliente: "quando o brinquedo tiver mais que uma, no card de apresentação
em home ou em brinquedos, deve ficar rodando as fotos". Todo brinquedo com
mais de uma foto na galeria pública (a mesma da página dele:
`core.models.galeria_publica`) leva no card a lista das fotos
(`{% fotos_do_card %}`, core/templatetags/giro.py), e o site/ls-giro.js as
reveza com uma troca suave, só com o card na tela. A primeira é a capa.

O mapa {id do brinquedo: [endereços]} sai de UMA consulta (as fotos de
todos os brinquedos ativos) e fica em cache; cai quando um brinquedo ou uma
foto muda (core/signals.py).
"""

from collections import defaultdict

from django.core.cache import cache

CHAVE = "fotos-dos-cards:mapa"
#: No máximo tantas fotos por card (a capa e mais três).
MAXIMO = 4
#: A largura das fotos do card (a mesma das capas dos cards).
LARGURA = 720


def _url(imagem):
    from .fotos import reduzir_imagem, url_da_imagem

    return reduzir_imagem(url_da_imagem(imagem), LARGURA) if imagem else ""


def mapa():
    """{id: [endereço, ...]} dos brinquedos ativos com mais de uma foto (em cache)."""
    dados = cache.get(CHAVE)
    if dados is not None:
        return dados
    from .models import Brinquedos, ImagemBrinquedo, galeria_publica

    por_brinquedo = defaultdict(list)
    try:
        padroes = dict(Brinquedos.objects.filter(ativo=True).values_list("id", "adesivo_padrao_id"))
        fotos = (
            ImagemBrinquedo.objects.filter(brinquedo__ativo=True)
            .only("id", "brinquedo_id", "imagem", "tipo", "ordem", "papel_na_capa", "variante")
        )
        for foto in fotos:
            por_brinquedo[foto.brinquedo_id].append(foto)
    except Exception:  # a tabela ainda sem a coluna (o código chegou antes da migração)
        return {}
    dados = {}
    for brinquedo_id, lista in por_brinquedo.items():
        # as fotos do adesivo PADRÃO, a capa (a frente) primeiro; nunca as de fundo branco
        galeria = galeria_publica(lista, padroes.get(brinquedo_id))
        urls = []
        for foto in galeria:
            url = _url(foto.imagem)
            if url and url not in urls:
                urls.append(url)
        if len(urls) > 1:
            dados[brinquedo_id] = urls[:MAXIMO]
    cache.set(CHAVE, dados, 60 * 30)
    return dados


def do_card(brinquedo_id):
    """As fotos do card do brinquedo (a capa primeiro), ou None com uma foto só."""
    return mapa().get(brinquedo_id)


def limpar_cache(**_kwargs):
    cache.delete(CHAVE)
