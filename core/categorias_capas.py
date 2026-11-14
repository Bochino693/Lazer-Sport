"""As categorias da vitrine: as áreas que faltavam, os nomes e as fotos novas.

O cliente pediu (as palavras dele): "veja se área ninja, entre outros tem
categoria, se não adicione e recrie as fotos das categorias [...] uma imagem
que combine e tenha o corte favorável a aparecer. além de deixar tudo
maiúscula e minúscula, boliche virtual tem tudo maiúsculo."

TRÊS COISAS, NUMA MIGRAÇÃO SÓ (`0147_categorias_capas_e_nomes`) E NUM
COMANDO PARA REFAZER (`python manage.py atualizar_capas_categorias`):

1. AS ÁREAS DA FÁBRICA. O "Monte seu espaço" oferece cinco áreas
   (core/projeto3d.py, AREAS): espaço esportivo kids, brinquedão, área baby,
   trampolim park e área ninja. A vitrine tinha categoria para três. As que
   faltam nascem aqui -- mas SÓ quando já há um produto ATIVO com o nome
   dela ("ninja" -> Área Ninja): categoria vazia não aparece na home (a home
   só mostra categoria com brinquedo, `HomeView`), mas aparecia no menu de
   sugestões do topo e levava a uma página sem nada. E os produtos da área
   que estavam fora da categoria dela entram (o Trampolim de Enterrada nos
   Trampolins, o Espaço Esportivo Modelo 1 no Espaço Esportivo Kids). Só
   acrescenta: nenhum produto sai de categoria nenhuma.

2. OS NOMES em maiúsculas e minúsculas (`core/nomes.py`): as categorias, os
   produtos, as peças de reposição e as categorias das peças. Só o nome
   todo em caixa-alta (ou todo em minúsculas) muda; o resto fica como está.
   Os endereços são pelo número e a Arena compara sem caixa: nada se perde.

3. AS FOTOS. Uma por categoria, feita para o nome dela, em
   core/static/site/categorias/<chave>.webp (1200 × 900, o 4:3 que enche o
   card da home sem faixa vazia). Saem do ferramentas/categorias/ (as cenas
   3D com os objetos da fábrica). A foto sobe para o Cloudinary como as do
   painel, com a assinatura do arquivo no nome: rodar de novo não sobe o
   que já está lá, e trocar a foto no repositório sobe a nova.
   A categoria é reconhecida pelo nome, sem acento nem caixa (CAPAS); a que
   não tem foto aqui (uma criada no painel depois) fica com a dela.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.core.files import File
from django.db import transaction

from .arena import _contem, _normalizar
from .nomes import nome_bonito

PASTA = Path(__file__).resolve().parent / "static" / "site" / "categorias"

#: (chave da foto, nomes da categoria que levam esta foto -- sem acento nem caixa).
CAPAS = (
    ("brinquedao", ("brinquedao", "brinquedoes")),
    ("area-ninja", ("area ninja", "ninja")),
    ("area-baby", ("area baby", "baby", "area bebe", "espaco baby")),
    ("trampolins", ("trampolins", "trampolim", "trampolim park", "cama elastica", "camas elasticas")),
    ("espaco-esportivo-kids", ("espaco esportivo kids", "espaco esportivo")),
    ("espaco-kids-play", ("espaco kids play", "kids play", "kid play")),
    ("boliche-virtual", ("boliche virtual", "boliche", "boliches")),
    ("eletronicos", ("eletronicos", "eletronico")),
    ("fliperama", ("fliperama", "fliperamas")),
    ("simuladores", ("simuladores", "simulador")),
    ("mecanicos", ("mecanicos", "mecanico")),
    ("jogos-de-mesa", ("jogos de mesa",)),
    ("competitivos", ("competitivos",)),
    ("famosos", ("famosos",)),
    ("esportivos", ("esportivos",)),
    ("kids", ("kids",)),
    # a categoria nova da Black Friday (seção 78): as três casinhas na brinquedoteca, com as crianças
    ("casinhas-cenograficas", ("casinhas cenograficas", "casinhas", "casinha cenografica", "cenograficos")),
)

#: As áreas da fábrica: (nome da categoria, nomes que já valem como ela, palavras
#: do nome do produto que é dela). A categoria que não existe só é criada com
#: produto ativo; a que existe só ganha os produtos que faltavam.
AREAS = (
    ("Área Ninja", ("area ninja", "ninja"), ("ninja",)),
    ("Área Baby", ("area baby", "baby", "area bebe", "espaco baby"), ("baby", "bebe")),
    ("Trampolins", ("trampolins", "trampolim", "trampolim park"), ("trampolim", "trampolins", "cama elastica")),
    ("Espaço Esportivo Kids", ("espaco esportivo kids", "espaco esportivo"), ("espaco esportivo",)),
    ("Brinquedão", ("brinquedao", "brinquedoes"), ("brinquedao",)),
)


def chave_da_capa(nome):
    """A chave da foto da categoria `nome` (pelo nome inteiro, sem acento nem caixa), ou None."""
    normal = _normalizar(nome)
    return next((chave for chave, nomes in CAPAS if normal in nomes), None)


def arquivo_da_capa(chave):
    return PASTA / f"{chave}.webp"


def assinatura(caminho):
    """Os 10 primeiros dígitos do SHA-1 do arquivo: muda quando a foto muda."""
    return hashlib.sha1(Path(caminho).read_bytes()).hexdigest()[:10]


def nome_no_cadastro(chave):
    """O nome do arquivo que sobe: `<chave>-<assinatura>` (o storage ainda pode pôr um sufixo)."""
    return f"{chave}-{assinatura(arquivo_da_capa(chave))}"


# ----------------------------------------------------------------------
# 1. AS ÁREAS
# ----------------------------------------------------------------------

def criar_sem_foto(CategoriasBrinquedos, nome):
    """A categoria nova, ativa e ainda sem foto (NULL, e não "").

    O campo da foto é único, e o arquivo vazio é gravado como "": duas
    categorias sem foto brigariam pelo mesmo "". Nasce com um nome de
    passagem, único, e o UPDATE seguinte grava NULL (que não briga com
    ninguém); a foto vem depois (`atualizar_capas`).
    """
    with transaction.atomic():
        categoria = CategoriasBrinquedos.objects.create(
            nome_categoria=nome, ativo=True, imagem_categoria=f"categorias/sem-foto-{uuid.uuid4().hex}",
        )
        CategoriasBrinquedos.objects.filter(pk=categoria.pk).update(imagem_categoria=None)
    return CategoriasBrinquedos.objects.get(pk=categoria.pk)


def garantir_areas(Brinquedos, CategoriasBrinquedos, avisar=print):
    """Cria as categorias de área que faltam (com produto ativo) e liga os produtos de cada uma.

    Devolve {nome da área: [nomes dos produtos ligados agora]} (as criadas
    vêm com " (nova)" no nome).
    """
    ativos = list(Brinquedos.objects.filter(ativo=True).order_by("id"))
    feito = {}
    for nome, nomes_da_categoria, palavras in AREAS:
        produtos = [b for b in ativos if any(_contem(_normalizar(b.nome_brinquedo), p) for p in palavras)]
        categoria = next(
            (c for c in CategoriasBrinquedos.objects.order_by("id") if _normalizar(c.nome_categoria) in nomes_da_categoria),
            None,
        )
        criada = False
        if categoria is None:
            if not produtos:
                # (num banco sem brinquedo nenhum -- o dos testes, um novo -- não há o que dizer)
                if ativos:
                    avisar(f"{nome}: nenhum produto ativo com o nome da área; a categoria não foi criada.")
                continue
            categoria = criar_sem_foto(CategoriasBrinquedos, nome)
            criada = True
        ja = set(categoria.brinquedos.values_list("id", flat=True))
        novos = [b for b in produtos if b.pk not in ja]
        if novos:
            categoria.brinquedos.add(*novos)
        if criada or novos:
            rotulo = f"{categoria.nome_categoria} (nova)" if criada else categoria.nome_categoria
            feito[rotulo] = [b.nome_brinquedo for b in novos]
            avisar(f"{rotulo}: " + (", ".join(b.nome_brinquedo for b in novos) or "nenhum produto novo"))
    return feito


# ----------------------------------------------------------------------
# 2. OS NOMES
# ----------------------------------------------------------------------

def arrumar_nomes(Brinquedos, CategoriasBrinquedos, PecasReposicao, CategoriaPeca, avisar=print):
    """Passa os nomes em caixa-alta (ou em minúsculas) por `nome_bonito`. Devolve [(antes, depois)]."""
    trocas = []
    for modelo, campo in (
        (CategoriasBrinquedos, "nome_categoria"),
        (Brinquedos, "nome_brinquedo"),
        (PecasReposicao, "nome"),
        (CategoriaPeca, "nome_categoria_peca"),
    ):
        for pk, antes in modelo.objects.order_by("id").values_list("id", campo):
            depois = nome_bonito(antes)
            if depois and depois != antes:
                # update(): não mexe no "atualizado" nem dispara o save() de ninguém
                modelo.objects.filter(pk=pk).update(**{campo: depois})
                trocas.append((antes, depois))
                avisar(f"{antes} -> {depois}")
    return trocas


# ----------------------------------------------------------------------
# 3. AS FOTOS
# ----------------------------------------------------------------------

def atualizar_capas(CategoriasBrinquedos, so=(), refazer=False, simular=False, avisar=print):
    """Põe a foto do repositório em cada categoria que tem uma (CAPAS).

    `so`: só estas chaves; `refazer`: sobe de novo mesmo a que já está lá;
    `simular`: só conta o que faria. Devolve {"trocadas", "iguais", "sem_foto"}:
    listas com o nome das categorias.
    """
    resultado = {"trocadas": [], "iguais": [], "sem_foto": []}
    for categoria in CategoriasBrinquedos.objects.order_by("id"):
        chave = chave_da_capa(categoria.nome_categoria)
        if chave is None or not arquivo_da_capa(chave).exists():
            resultado["sem_foto"].append(categoria.nome_categoria)
            continue
        if so and chave not in so:
            continue
        nome = nome_no_cadastro(chave)
        atual = categoria.imagem_categoria.name or ""
        if not refazer and nome in atual:
            resultado["iguais"].append(categoria.nome_categoria)
            continue
        if not simular:
            with transaction.atomic(), open(arquivo_da_capa(chave), "rb") as origem:
                # o campo é único: o storage dá a cada categoria o seu arquivo
                categoria.imagem_categoria.save(f"{nome}.webp", File(origem), save=False)
                categoria.save(update_fields=["imagem_categoria", "atualizado"])
        resultado["trocadas"].append(categoria.nome_categoria)
        avisar(f"{categoria.nome_categoria}: {'subiria' if simular else 'nova foto'} {chave}.webp"
               + (f" (era {atual})" if atual else ""))
    if resultado["sem_foto"]:
        avisar("Sem foto no repositório (ficam com a do painel): " + ", ".join(resultado["sem_foto"]))
    return resultado


# ----------------------------------------------------------------------
# AS MIGRAÇÕES
# ----------------------------------------------------------------------

def subir_fotos_no_deploy(apps, schema_editor, avisar=print):
    """A migração que troca as fotos (a 0149: as fotos nos lugares).

    Só no Render (o Cloudinary só está lá); todas as categorias, e sobe só
    o que mudou (a assinatura no nome). Se a subida falhar, o deploy segue
    e o aviso diz o comando que refaz.
    """
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    try:
        return atualizar_capas(apps.get_model("core", "CategoriasBrinquedos"), avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As fotos das categorias não subiram agora ({erro!r}). "
               "Rode: python manage.py atualizar_capas_categorias")
        return None


def subir_fotos_e_limpar_o_cache(apps, schema_editor, avisar=print):
    """A 0196: as fotos das categorias refeitas no salão (ferramentas/fotos-categorias/, Blender).

    Só no Render (o Cloudinary só está lá): sobe só as fotos que mudaram -- o nome
    leva a assinatura do arquivo (`nome_no_cadastro`), então a foto igual não sobe de
    novo e a nova ganha outro nome (o CDN não serve a velha) -- e limpa o cache (a
    home e a busca guardadas passam a mostrar as novas; o card "Peças e acessórios",
    que é estático, também). Se a subida falhar, o deploy segue e o aviso diz o
    comando. Fora do Render não faz nada.
    """
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    resultado = subir_fotos_no_deploy(apps, schema_editor, avisar=avisar)
    try:
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001 -- o deploy segue
        pass
    return resultado


def migrar(apps, schema_editor, avisar=print):
    """A 0147: os nomes e as áreas em todo lugar (só o banco); as fotos, só no Render.

    As fotos sobem para o Cloudinary, que só está configurado no Render: no
    computador e nos testes a migração não sobe nada. Se a subida falhar, o
    deploy segue e `python manage.py atualizar_capas_categorias` refaz.
    """
    from django.conf import settings

    Brinquedos = apps.get_model("core", "Brinquedos")
    CategoriasBrinquedos = apps.get_model("core", "CategoriasBrinquedos")
    arrumar_nomes(
        Brinquedos,
        CategoriasBrinquedos,
        apps.get_model("core", "PecasReposicao"),
        apps.get_model("core", "CategoriaPeca"),
        avisar=avisar,
    )
    garantir_areas(Brinquedos, CategoriasBrinquedos, avisar=avisar)
    if not getattr(settings, "IS_RENDER", False):
        return
    try:
        atualizar_capas(CategoriasBrinquedos, avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As fotos das categorias não subiram agora ({erro!r}). "
               "Rode: python manage.py atualizar_capas_categorias")
