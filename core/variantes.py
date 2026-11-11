"""Os adesivos de um produto: a mesma máquina com outra arte (LEIA-ME, seção 72).

O cliente, mostrando os cards "Air Game Kids" (os astronautas) e "Air Game
Kids Alienígenas" (os alienígenas) lado a lado: "os dois devem se tornar o
mesmo objeto, como um adesivo diferente, ele quem deve ser o diferencial,
rodando as duas imagens em todo objeto também canalizando os dois objetos 3d
... vamos ter mais exemplos assim então se atente em como fazer".

O MECANISMO (para este par e os próximos):
  * o produto é um só; cada adesivo (core.models.VarianteAdesivo) mostra as
    fotos e o 3D de uma ficha do cadastro (`origem`; o padrão, o próprio
    produto);
  * a ficha que era um produto à parte fica DESATIVADA (sai das listas; nada
    é apagado: pedidos, orçamentos e favoritos seguem apontando para ela) e o
    endereço dela redireciona, permanente, para o produto com
    `?adesivo=<slug>`;
  * na página do produto, as fichas "Adesivo: A · B" trocam as fotos e o 3D
    (o .glb da ficha do adesivo) e o endereço; o adesivo vai para o carrinho
    e para a mensagem do orçamento;
  * nos cards (a home, as categorias, /brinquedos/, a loja, a busca), o
    produto aparece uma vez, com as capas dos adesivos se revezando e o selo
    "2 adesivos"; na Arena, uma vez, com o 3D do adesivo que tem.

JUNTAR UM PAR NOVO: um item em PARES e uma migração de dados que chame
`juntar` (como a 0160). Fora das migrações, o painel (o admin dos adesivos)
faz o mesmo à mão.
"""

import json
import unicodedata

from django.core.cache import cache
from django.db import transaction

#: Os pares juntados: o produto (o adesivo padrão, as fotos dele) e as fichas que viram adesivos dele.
#: (nome do produto, (nome do adesivo padrão, slug)), [(nome da ficha, nome do adesivo, slug)].
PARES = (
    (("Air Game Kids", ("Astronautas", "astronautas")),
     [("Air Game Kids Alienígenas", "Alienígenas", "alienigenas")]),
    # o gabinete do Basquete Home (o azul) e o mesmo gabinete com os adesivos em quadrinhos (o
    # "Basquete Street Quadrinhos" de antes: a folha é a do Basquete Home, LEIA-ME 61). O
    # Basquete Street (a estrutura aberta com a rede) fica sozinho.
    (("Basquete Home", ("Azul", "azul")),
     [("Basquete Home Quadrinhos", "Quadrinhos", "quadrinhos")]),
)

#: As fichas renomeadas antes de virar adesivo: (a chave do cadastro, o nome de antes).
RENOMEADAS = (("basquete-street-quadrinhos", "Basquete Street Quadrinhos"),)

#: A chave do cache do mapa dos cards (a versão muda quando um adesivo, uma foto ou um produto muda).
CHAVE_DO_MAPA = "variantes-adesivo:mapa"


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def _achar(nome, Brinquedos):
    alvo = _normalizar(nome)
    achados = [b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo]
    return achados[0] if achados else None


def juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=print):
    """Junta as `fichas` ao `produto` como adesivos dele. Pode rodar de novo (não duplica).

    `produto`: o nome; `padrao`: (nome do adesivo, slug) do próprio produto;
    `fichas`: [(nome da ficha, nome do adesivo, slug)]. A ficha vira um adesivo
    (as fotos e o 3D dela) e é desativada. Sem o produto, não faz nada.
    """
    base = _achar(produto, Brinquedos)
    if base is None:
        avisar(f"{produto}: não está no catálogo; nada a juntar.")
        return None
    with transaction.atomic():
        VarianteAdesivo.objects.update_or_create(
            brinquedo=base, slug=padrao[1],
            defaults={"nome": padrao[0], "ordem": 1, "padrao": True, "origem": None},
        )
        for ordem, (nome_da_ficha, nome, slug) in enumerate(fichas, start=2):
            ficha = _achar(nome_da_ficha, Brinquedos)
            if ficha is None or ficha.pk == base.pk:
                avisar(f"{nome_da_ficha}: não está no catálogo; o adesivo {nome} fica para depois.")
                continue
            VarianteAdesivo.objects.update_or_create(
                brinquedo=base, slug=slug,
                defaults={"nome": nome, "ordem": ordem, "padrao": False, "origem": ficha},
            )
            if ficha.ativo:
                ficha.ativo = False
                ficha.save(update_fields=["ativo"])
            avisar(f"{nome_da_ficha} agora é o adesivo {nome} do {base.nome_brinquedo} (a ficha saiu das listas).")
    return base


def separar(produto, Brinquedos, VarianteAdesivo, avisar=print):
    """Desfaz `juntar`: as fichas voltam a ser produtos (ativos) e os adesivos saem."""
    base = _achar(produto, Brinquedos)
    if base is None:
        return None
    with transaction.atomic():
        for variante in VarianteAdesivo.objects.filter(brinquedo=base).select_related("origem"):
            if variante.origem is not None and not variante.origem.ativo:
                variante.origem.ativo = True
                variante.origem.save(update_fields=["ativo"])
        VarianteAdesivo.objects.filter(brinquedo=base).delete()
    avisar(f"{base.nome_brinquedo}: os adesivos voltaram a ser produtos à parte.")
    return base


def migrar(apps, schema_editor, avisar=print):
    """A migração de dados (a 0160): junta os PARES em todo lugar (só o banco: nada sobe).

    Antes, as fichas de RENOMEADAS ganham o nome de hoje (o "Basquete Street
    Quadrinhos" vira o "Basquete Home Quadrinhos", com as descrições das fotos).
    """
    from .cadastro_modelos import renomear_variante

    Brinquedos = apps.get_model("core", "Brinquedos")
    VarianteAdesivo = apps.get_model("core", "VarianteAdesivo")
    for chave, nome_antigo in RENOMEADAS:
        renomear_variante(
            chave, nome_antigo, Brinquedos, apps.get_model("core", "CategoriasBrinquedos"),
            apps.get_model("core", "ImagemBrinquedo"), apps.get_model("core", "ObjetoTresD"), avisar=avisar,
        )
    for (produto, padrao), fichas in PARES:
        juntar(produto, padrao, fichas, Brinquedos, VarianteAdesivo, avisar=avisar)


# ----------------------------------------------------------------------
# O que as telas usam
# ----------------------------------------------------------------------


def _url(imagem, largura):
    from .fotos import reduzir_imagem, url_da_imagem

    return reduzir_imagem(url_da_imagem(imagem), largura) if imagem else ""


def _objeto_3d(ficha):
    """O .glb da ficha: o do cadastro (ativo) ou o do site ligado pelo nome; None sem nenhum."""
    from . import arena
    from .models import ObjetoTresD
    from .objetos_3d import tabela_pronta

    registro = ObjetoTresD.objects.filter(brinquedo=ficha).first() if tabela_pronta() else None
    if registro is not None:
        if registro.ativo and registro.url:
            return {"url": registro.url, "codigo": registro.codigo or "", "cores": list(registro.cores or [])}
        return None
    modelo = arena.modelo_da_maquina(ficha.nome_brinquedo)
    if modelo:
        from sistema_interno.templatetags.interno_extras import estatico

        return {"url": estatico(modelo["arquivo"]), "codigo": modelo["id"], "cores": []}
    return None


def variantes_do_produto(brinquedo):
    """Os adesivos do produto para a página dele: [] quando não tem.

    Cada um: nome, slug, padrão, as fotos (a galeria pública da ficha: as
    três primeiras com tipo), a capa e o 3D (ou None).
    """
    from .models import VarianteAdesivo

    variantes = list(VarianteAdesivo.objects.filter(brinquedo=brinquedo, ativo=True).select_related("origem"))
    if len(variantes) < 2:
        return []
    saida = []
    for variante in variantes:
        ficha = variante.ficha
        imagens = list(ficha.imagens_ordenadas)
        fotos = [
            {"url": _url(foto.imagem, 1400), "miniatura": _url(foto.imagem, 240), "alt": foto.texto_alternativo or ficha.nome_brinquedo}
            for foto in imagens
        ]
        capa = ficha.imagem_catalogo
        saida.append({
            "nome": variante.nome,
            "slug": variante.slug,
            "padrao": variante.padrao,
            # as fotos da galeria pública da ficha (a página as mostra como as do produto)
            "imagens": imagens,
            "fotos": fotos or ([{"url": _url(capa, 1400), "miniatura": _url(capa, 240), "alt": ficha.nome_brinquedo}] if capa else []),
            "capa": _url(capa, 720),
            "objeto_3d": _objeto_3d(ficha),
        })
    if not any(v["padrao"] for v in saida):
        saida[0]["padrao"] = True
    return saida


def escolhida(variantes, slug):
    """O adesivo do `slug` (o ?adesivo= do endereço), ou o padrão."""
    return next((v for v in variantes if slug and v["slug"] == slug), None) or next((v for v in variantes if v["padrao"]), None)


def redirecionamento(brinquedo_id):
    """O produto e o adesivo para onde vai o endereço da ficha que virou adesivo, ou None."""
    from .models import VarianteAdesivo

    variante = (
        VarianteAdesivo.objects.filter(origem_id=brinquedo_id, origem__ativo=False, brinquedo__ativo=True, ativo=True)
        .select_related("brinquedo")
        .first()
    )
    return (variante.brinquedo_id, variante.slug) if variante else None


def mapa_dos_cards():
    """{id do produto: {"total": n, "capas": [{"nome", "url"}]}} dos produtos com adesivos (em cache).

    Uma consulta pequena (a tabela dos adesivos) e as capas das fichas; o
    cache cai quando um adesivo, uma foto ou um produto muda (os signals).
    """
    mapa = cache.get(CHAVE_DO_MAPA)
    if mapa is not None:
        return mapa
    from .models import VarianteAdesivo

    mapa = {}
    try:
        variantes = list(
            VarianteAdesivo.objects.filter(ativo=True, brinquedo__ativo=True)
            .select_related("brinquedo", "origem")
            .order_by("brinquedo_id", "ordem", "id")
        )
    except Exception:  # a tabela ainda não existe (o código chegou antes da migração)
        return {}
    for variante in variantes:
        ficha = variante.ficha
        item = mapa.setdefault(variante.brinquedo_id, {"total": 0, "capas": []})
        item["total"] += 1
        capa = ficha.imagem_catalogo
        if capa:
            item["capas"].append({"nome": variante.nome, "url": _url(capa, 720)})
    mapa = {k: v for k, v in mapa.items() if v["total"] > 1}
    cache.set(CHAVE_DO_MAPA, mapa, 60 * 30)
    return mapa


def do_card(brinquedo_id):
    """Os adesivos de um card: {"total", "capas", "json"} ou None."""
    item = mapa_dos_cards().get(brinquedo_id)
    if not item:
        return None
    return {**item, "json": json.dumps([c["url"] for c in item["capas"]])}


def limpar_cache(**_kwargs):
    cache.delete(CHAVE_DO_MAPA)


def modelos_das_variantes():
    """Os códigos dos objetos 3D que são de um adesivo (a Arena não os mostra à parte)."""
    from .models import VarianteAdesivo

    try:
        variantes = list(VarianteAdesivo.objects.filter(ativo=True, origem__isnull=False).select_related("origem", "brinquedo"))
    except Exception:
        return {}
    saida = {}
    for variante in variantes:
        objeto = _objeto_3d(variante.origem)
        if objeto:
            saida.setdefault(variante.brinquedo_id, []).append({**objeto, "adesivo": variante.nome})
    return saida


def completar_na_arena(dados):
    """Na Arena (core/views_arena.py): o produto com adesivos leva o 3D dos adesivos.

    `modelos_variantes`: os códigos dos .glb dos adesivos (a Arena não os põe à
    parte, como objetos fora do catálogo); sem 3D próprio, o produto fica com o
    do primeiro adesivo que tem (e entra na roda).
    """
    from . import arena

    por_produto = modelos_das_variantes()
    for item in dados:
        extras = por_produto.get(item.get("id"))
        if not extras:
            continue
        item["modelos_variantes"] = [e["codigo"] for e in extras if e["codigo"]]
        item["adesivos"] = [e["adesivo"] for e in extras]
        if item.get("modelo"):
            continue
        primeiro = extras[0]
        modelo = next((m for m in arena.MODELOS_3D if m["id"] == primeiro["codigo"]), None)
        item["modelo"] = primeiro["url"]
        item["modelo_id"] = primeiro["codigo"]
        item["cores_modelo"] = primeiro["cores"]
        if modelo:
            item["medidas_modelo"] = list(modelo["medidas"])
            item["grupo"] = modelo.get("grupo", item.get("grupo"))
            item["reino"] = bool(modelo.get("reino"))
            item["jogos_no_espaco"] = arena.jogos_do_modelo(modelo)
