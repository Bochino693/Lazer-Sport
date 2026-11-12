"""As fotos que giram nos cards dos brinquedos: UMA POR ADESIVO (LEIA-ME, seção 72).

O cliente: "o carrossel não deve ser por posição e sim por adesivos,
entendeu? com uma transição suave e legal". Todo brinquedo com mais de um
adesivo leva no card a lista [{"src", "adesivo"}] (`{% fotos_do_card %}`,
core/templatetags/giro.py): de cada adesivo, a CAPA QUADRADA dele no
showroom (a `ImagemBrinquedo` do adesivo com `papel_na_capa = "cena"`); sem
ela, a primeira foto das posições dele (`core.models.galeria_publica`:
nunca a sem fundo). O padrão primeiro. O site/ls-giro.js as reveza com a
troca suave e o nome do adesivo no card, só com o card na tela. Com um
adesivo só, o card não gira.

O mapa {id do brinquedo: [endereços]} sai de UMA consulta (as fotos de
todos os brinquedos ativos) e fica em cache; cai quando um brinquedo ou uma
foto muda (core/signals.py).
"""

from collections import defaultdict

from django.core.cache import cache

CHAVE = "fotos-dos-cards:mapa"
#: No máximo tantos adesivos por card (o padrão e mais três).
MAXIMO = 4
#: A largura das fotos do card (a mesma das capas dos cards).
LARGURA = 720


def _url(imagem):
    from .fotos import reduzir_imagem, url_da_imagem

    return reduzir_imagem(url_da_imagem(imagem), LARGURA) if imagem else ""


def mapa():
    """{id: [{"src", "adesivo"}, ...]} dos brinquedos ativos com mais de um adesivo com foto (em cache)."""
    dados = cache.get(CHAVE)
    if dados is not None:
        return dados
    from .models import ImagemBrinquedo, VarianteAdesivo, galeria_publica

    por_brinquedo = defaultdict(list)
    adesivos = defaultdict(list)
    padroes = {}
    try:
        # (duas consultas para o catálogo inteiro: os adesivos, com o padrão de cada brinquedo, e as fotos)
        for adesivo in VarianteAdesivo.objects.filter(ativo=True, brinquedo__ativo=True).values(
                "id", "brinquedo_id", "nome", "padrao", "ordem", "brinquedo__adesivo_padrao_id"):
            adesivos[adesivo["brinquedo_id"]].append(adesivo)
            padroes[adesivo["brinquedo_id"]] = adesivo["brinquedo__adesivo_padrao_id"]
        fotos = (
            ImagemBrinquedo.objects.filter(brinquedo__ativo=True)
            .only("id", "brinquedo_id", "imagem", "tipo", "ordem", "papel_na_capa", "variante")
        )
        for foto in fotos:
            por_brinquedo[foto.brinquedo_id].append(foto)
    except Exception:  # a tabela ainda sem a coluna (o código chegou antes da migração)
        return {}
    dados = {}
    for brinquedo_id, lista in adesivos.items():
        if len(lista) < 2:
            continue  # um adesivo só: o card não gira
        padrao_id = padroes.get(brinquedo_id) or next((a["id"] for a in lista if a["padrao"]), None)
        fotos_dele = sorted(por_brinquedo.get(brinquedo_id, []), key=lambda f: (f.ordem, f.id))
        cartoes, urls = [], set()
        for adesivo in sorted(lista, key=lambda a: (a["id"] != padrao_id, a["ordem"], a["id"])):
            e_padrao = adesivo["id"] == padrao_id
            do_adesivo = [f for f in fotos_dele if f.variante_id == adesivo["id"] or (e_padrao and f.variante_id is None)]
            capa = next((f for f in do_adesivo if f.papel_na_capa == "cena" and f.imagem), None)
            if capa is None:
                galeria = (galeria_publica(fotos_dele, padrao_id) if e_padrao
                           else galeria_publica(fotos_dele, adesivo_id=adesivo["id"]))
                capa = galeria[0] if galeria else None
            url = _url(capa.imagem) if capa is not None else ""
            if url and url not in urls:
                urls.add(url)
                cartoes.append({"src": url, "adesivo": adesivo["nome"]})
        if len(cartoes) > 1:
            dados[brinquedo_id] = cartoes[:MAXIMO]
    cache.set(CHAVE, dados, 60 * 30)
    return dados


def do_card(brinquedo_id):
    """As fotos do card do brinquedo, uma por adesivo ({"src", "adesivo"}; o padrão primeiro), ou None."""
    return mapa().get(brinquedo_id)


def limpar_cache(**_kwargs):
    cache.delete(CHAVE)
