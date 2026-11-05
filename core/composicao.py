"""Brinquedo que contém outros: o brinquedão, o espaço esportivo (`ComponenteBrinquedo`).

AS REGRAS DE COERÊNCIA
* Quem contém é um CONJUNTO: brinquedão, espaço esportivo, parque,
  trampolim park... -- pela categoria ou pelo nome (`pode_conter`). O que
  vem dentro pode ser qualquer brinquedo do catálogo (o Gol Flash, o Swish,
  uma piscina de bolinhas), e pode estar em vários conjuntos.
* Nada contém a si mesmo, nem em volta: se o Espaço tem o Circuito Kids,
  o Circuito Kids não pode ter o Espaço (`ancestrais`).
* A quantidade conta: "dois círculos do Gol Flash".

A AGILIDADE: AS SUGESTÕES (`sugestoes`)
1. O objeto 3D do conjunto já sabe o que tem desenhado: o do Espaço
   Esportivo Modelo 1 tem os círculos do Gol Flash e as cestas do Swish
   (`arena.MODELOS_3D[...]["componentes"]`). Essas máquinas do catálogo
   vêm sugeridas com a quantidade.
2. A descrição do conjunto cita outros brinquedos pelo nome: cada um que
   existe no catálogo vem sugerido.
O painel liga cada sugestão com um toque.
"""

from __future__ import annotations

import unicodedata

from . import arena

#: Pedaços de nome de categoria (ou do nome do brinquedo) que fazem dele um conjunto.
SINAIS_DE_CONJUNTO = ("brinquedao", "espaco esportivo", "espaco kids", "parque", "trampolim", "playground", "circuito")


def _normal(texto):
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto or "") if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def pode_conter(brinquedo, categorias=None):
    """É um conjunto (brinquedão, espaço esportivo...) -- pode ter outros brinquedos dentro."""
    if categorias is None:
        categorias = [c.nome_categoria for c in brinquedo.categorias_brinquedos.all()]
    textos = [_normal(n) for n in categorias] + [_normal(brinquedo.nome_brinquedo)]
    return any(sinal in texto for texto in textos for sinal in SINAIS_DE_CONJUNTO)


def ancestrais(brinquedo_id, ligacoes):
    """Todos os conjuntos que contêm este brinquedo, direta ou indiretamente.

    `ligacoes`: {conjunto_id: {item_id, ...}} -- o grafo inteiro, lido uma vez.
    """
    pais = {}
    for conjunto, itens in ligacoes.items():
        for item in itens:
            pais.setdefault(item, set()).add(conjunto)
    vistos, fila = set(), [brinquedo_id]
    while fila:
        atual = fila.pop()
        for pai in pais.get(atual, ()):
            if pai not in vistos:
                vistos.add(pai)
                fila.append(pai)
    return vistos


def grafo():
    from .models import ComponenteBrinquedo

    ligacoes = {}
    for conjunto, item in ComponenteBrinquedo.objects.values_list("conjunto_id", "item_id"):
        ligacoes.setdefault(conjunto, set()).add(item)
    return ligacoes


def conferir(conjunto, itens, ligacoes=None):
    """Confere a lista nova [(item_id, quantidade)] do conjunto; devolve a lista limpa ou levanta ValueError."""
    from .models import Brinquedos

    ligacoes = grafo() if ligacoes is None else ligacoes
    proibidos = ancestrais(conjunto.pk, ligacoes) | {conjunto.pk}
    limpos, vistos = [], set()
    nomes = dict(Brinquedos.objects.filter(pk__in=[i for i, _ in itens]).values_list("pk", "nome_brinquedo"))
    for item_id, quantidade in itens:
        if item_id not in nomes:
            raise ValueError("Um dos brinquedos escolhidos não existe mais.")
        if item_id in proibidos:
            raise ValueError(
                f"“{nomes[item_id]}” não pode vir dentro de “{conjunto.nome_brinquedo}”: "
                + ("é ele mesmo." if item_id == conjunto.pk else "ele já contém este conjunto (ficaria em volta).")
            )
        if item_id in vistos:
            continue
        vistos.add(item_id)
        limpos.append((item_id, max(1, min(99, int(quantidade or 1)))))
    return limpos


def salvar(conjunto, itens):
    """Troca o que vem dentro do conjunto pela lista [(item_id, quantidade)] (já conferida)."""
    from .models import ComponenteBrinquedo

    from django.db import transaction

    from .home_cache import invalidate_public_catalog_caches

    limpos = conferir(conjunto, itens)
    ComponenteBrinquedo.objects.filter(conjunto=conjunto).delete()
    ComponenteBrinquedo.objects.bulk_create([
        ComponenteBrinquedo(conjunto=conjunto, item_id=item_id, quantidade=quantidade, ordem=ordem)
        for ordem, (item_id, quantidade) in enumerate(limpos)
    ])
    # bulk_create não avisa os sinais: a página do conjunto e a de cada item
    # estão em cache e precisam sair dele agora (e de novo depois do commit)
    invalidate_public_catalog_caches()
    transaction.on_commit(invalidate_public_catalog_caches)
    return limpos


def sugestoes(conjunto, catalogo, ja_dentro=()):
    """[{id, nome, quantidade, motivo}] -- o que provavelmente vem dentro do conjunto.

    `catalogo`: [(id, nome)] dos brinquedos ativos. `ja_dentro`: ids já ligados.
    """
    ja_dentro = set(ja_dentro)
    achados = {}
    modelo = arena.modelo_da_maquina(conjunto.nome_brinquedo)
    por_jogo = {}
    for item_id, nome in catalogo:
        slug = arena.jogo_da_maquina(nome)
        if slug:
            por_jogo.setdefault(slug, []).append((item_id, nome))
    for slug, quantidade in (modelo or {}).get("componentes", ()):
        for item_id, nome in por_jogo.get(slug, ()):
            achados.setdefault(item_id, {
                "id": item_id, "nome": nome, "quantidade": quantidade, "motivo": "está no objeto 3D deste conjunto",
            })
    descricao = _normal(conjunto.descricao or "")
    if descricao:
        for item_id, nome in catalogo:
            normal = _normal(nome)
            if item_id == conjunto.pk or item_id in achados or len(normal) < 5:
                continue
            if normal in descricao:
                achados[item_id] = {"id": item_id, "nome": nome, "quantidade": 1, "motivo": "citado na descrição"}
    return [s for s in achados.values() if s["id"] not in ja_dentro and s["id"] != conjunto.pk]
