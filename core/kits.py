"""O KIT ELETRÔNICO: a parte elétrica de uma máquina, sem a máquina (LEIA-ME seções 105 e 107).

O PEDIDO, nas palavras do dono: "no site, precisamos agora também do chamado
kit, ele deve ter espaço entre os demais produtos, o kit seria o seguinte, os
componentes eletrônicos sem a máquina para troca ou semi instalação, por
exemplo, strike kids, uma tv box, 5 sensores de precisão, a câmera e etc, para
o cara instalar toda parte elétrica na máquina caso ele só tenha a máquina, no
lazer shot, a arma, a tv box".

O KIT É UM PRODUTO (seção 107). Ele nasceu como uma peça marcada, com vitrine
própria; o dono: "vc criou outra sub section e nem sei se outro objeto, mas
eles devem estar junto com os produtos". Agora é um `Brinquedos` com
`eh_kit` -- o mesmo objeto das máquinas, nas mesmas grades (home, /brinquedos/,
loja, categorias, busca), com a mesma página, o mesmo carrinho e a mesma tela
do painel. A categoria "Kits eletrônicos" junta todos. O que é só do kit mora
aqui:

  * o ícone e a foto de cada item na página (`icone_do_componente`,
    `foto_do_componente`) e a lista curta do card ("7 itens: TV Box, ...",
    `resumo_dos_itens`);
  * a categoria dos kits (`categoria_dos_kits`, `url_dos_kits`);
  * os três kits iniciais (`KITS_INICIAIS`) e o comando que cria os que
    faltam: `python manage.py kits_eletronicos` (a arte sobe só com --foto).

SEM PREÇO o kit é "Sob consulta", como as máquinas fora da loja: o carrinho só
aceita o produto da loja com preço (`views._item_vendavel`).
"""


from __future__ import annotations

import hashlib
from pathlib import Path

from .arena import _contem, _normalizar

PASTA = Path(__file__).resolve().parent / "static" / "site" / "kits"

#: A coluna do arquivo (ImageField) guarda até 100 caracteres. O último deploy
#: caiu por um nome comprido (core/recorte_peca.py, LIMITE_DO_NOME): o nome da
#: foto do kit é curto e é conferido antes de gravar.
LIMITE_DO_NOME = 100

#: O ícone de cada item, pela primeira palavra-chave que aparece no nome. Só
#: ícones do recorte do Font Awesome do site (vendor/fontawesome-site/).
ICONES = (
    (("tv box", "tvbox", "android box"), "fa-tv"),
    (("sensor", "sensores"), "fa-wave-square"),
    (("webcam", "camera", "cameras"), "fa-camera"),
    (("arma", "pistola"), "fa-crosshairs"),
    (("placa", "zero delay", "interface"), "fa-microchip"),
    (("chicote",), "fa-network-wired"),
    (("hdmi", "cabo", "cabos"), "fa-plug"),
    (("fonte",), "fa-bolt"),
    (("botao", "botoes", "controle", "joystick"), "fa-gamepad"),
    (("monitor", "tela", "televisao"), "fa-tv"),
)
ICONE_PADRAO = "fa-puzzle-piece"


def icone_do_componente(nome):
    """A classe do ícone do item: "TV Box" -> fa-tv, "Barra com 5 sensores" -> fa-wave-square."""
    texto = _normalizar(nome)
    for palavras, icone in ICONES:
        if any(_contem(texto, palavra) for palavra in palavras):
            return icone
    return ICONE_PADRAO


#: A FOTO DE CADA ITEM (o dono: "nos itens do kit, realmente ponha fotos dos
#: produtos, algumas temos em peça de reposição outros puxe da web"). Primeiro
#: a foto da PEÇA ligada ao item (cadastrada no painel, com o recorte
#: automático); sem ela, a da biblioteca dos kits (site/kits/itens/<nome>.webp:
#: fotos NOSSAS, ou de licença livre -- nunca de outra loja). Sem nenhuma, o
#: ícone. Pela primeira palavra-chave do nome, como o ícone.
FOTOS_DOS_ITENS = (
    (("tv box", "tvbox", "android box"), "tv-box"),
    (("webcam", "camera", "cameras"), "camera"),
    (("zero delay",), "placa-zero-delay"),
    (("sensor", "sensores"), "barra-de-sensores"),
    (("arma", "pistola"), "arma"),
    (("chicote",), "chicote"),
    (("hdmi",), "cabo-hdmi"),
    (("fonte",), "fonte"),
)
PASTA_DOS_ITENS = PASTA / "itens"


def foto_da_biblioteca(nome):
    """O endereço da foto do item na biblioteca dos kits, ou "" (sem foto para ele)."""
    from django.templatetags.static import static

    texto = _normalizar(nome)
    for palavras, arquivo in FOTOS_DOS_ITENS:
        if any(_contem(texto, palavra) for palavra in palavras):
            if (PASTA_DOS_ITENS / f"{arquivo}.webp").exists():
                return static(f"site/kits/itens/{arquivo}.webp")
            return ""
    return ""


def foto_do_componente(item):
    """A foto do item do kit: a da peça ligada a ele, a da biblioteca, ou ""."""
    peca = item.peca if item.peca_id else None
    if peca is not None:
        for foto in peca.imagens_ordenadas:
            if foto.imagem:
                try:
                    return foto.imagem.url
                except Exception:  # noqa: BLE001 -- arquivo sumido: segue para a biblioteca
                    break
    return foto_da_biblioteca(item.nome)


def resumo_dos_itens(componentes, quantos=3):
    """A lista curta do card: "7 itens: TV Box, Barra com 5 sensores, Câmera…".

    `componentes` é a lista (já trazida por prefetch) dos itens do kit, na
    ordem do cadastro. Conta as LINHAS (o que o cliente vê na lista), não as
    unidades: a barra com 5 sensores é um item.
    """
    itens = [c for c in componentes if (c.nome or "").strip()]
    if not itens:
        return ""
    nomes = [c.nome.strip() for c in itens[:quantos]]
    total = len(itens)
    texto = f"{total} ite{'m' if total == 1 else 'ns'}: " + ", ".join(nomes)
    return texto + ("…" if total > quantos else "")


# ----------------------------------------------------------------------
# OS KITS INICIAIS
# ----------------------------------------------------------------------

#: (nome do kit, nome da máquina no catálogo, chave da foto ou "", descrição,
#:  [(item, detalhe, quantidade)]). Os detalhes da câmera, da arma e dos
#: sensores são os da própria máquina (core/arena.py, AVISOS).
KITS_INICIAIS = (
    (
        "Kit Boliche Virtual",
        "Boliche Virtual",
        "kit-boliche-virtual",
        "A parte eletrônica completa do Boliche Virtual, sem a máquina: placa Zero Delay, "
        "TV Box com o jogo Dragon Bowling, chicote, cabo HDMI, fonte, webcam e a barra "
        "com 5 sensores. Para montar a sua própria máquina, trocar a eletrônica de uma que "
        "parou ou instalar tudo na máquina que você já tem. Kit completo e pronto para instalar.",
        (
            ("Placa Zero Delay", "", 1),
            ("TV Box", "Com o jogo Dragon Bowling", 1),
            ("Chicote", "", 1),
            ("Cabo HDMI", "", 1),
            ("Fonte", "", 1),
            ("Webcam", "", 1),
            ("Barra com 5 sensores", "Leem cada jogada da bola na pista", 1),
        ),
    ),
    (
        "Kit Strike Kids",
        "Strike Kids",
        "kit-strike-kids",
        "A parte eletrônica completa do Strike Kids, sem a máquina: TV Box com o jogo Strike "
        "Kids, a barra com 5 sensores de precisão, a câmera que tira a foto do jogador para o "
        "ranking, placa Zero Delay, chicote, cabo HDMI e fonte. Para montar a sua própria "
        "máquina, trocar a eletrônica de uma que parou ou instalar tudo na máquina que você "
        "já tem. Kit completo e pronto para instalar.",
        (
            ("TV Box", "Com o jogo Strike Kids", 1),
            ("Barra com 5 sensores de precisão", "Leem cada jogada da bola na pista", 1),
            ("Câmera", "Tira a foto do jogador para o ranking", 1),
            ("Placa Zero Delay", "", 1),
            ("Chicote", "", 1),
            ("Cabo HDMI", "", 1),
            ("Fonte", "", 1),
        ),
    ),
    (
        "Kit Lazer Shot",
        "Lazer Shot",
        "kit-lazer-shot",
        "A parte eletrônica completa do Lazer Shot, sem a máquina: a arma personalizada "
        "(a pistola de luz feita para a máquina), TV Box com o jogo Lazer Shot, a câmera que "
        "tira a foto do jogador para o ranking, placa Zero Delay, chicote, cabo HDMI e fonte. "
        "Para montar a sua própria máquina, trocar a eletrônica de uma que parou ou instalar "
        "tudo na máquina que você já tem. Kit completo e pronto para instalar.",
        (
            ("Arma personalizada", "Pistola de luz feita para a máquina", 1),
            ("TV Box", "Com o jogo Lazer Shot", 1),
            ("Câmera", "Tira a foto do jogador para o ranking", 1),
            ("Placa Zero Delay", "", 1),
            ("Chicote", "", 1),
            ("Cabo HDMI", "", 1),
            ("Fonte", "", 1),
        ),
    ),
)


#: O item que é também uma peça vendida avulsa (pelo nome da peça).
PECAS_AVULSAS = {"cabo hdmi": "cabo hdmi"}

#: A categoria que junta os kits (criada pela migração 0212; o menu e /kits/ levam a ela).
NOME_DA_CATEGORIA = "Kits eletrônicos"


def _pelo_nome(objetos, campo, nome):
    """O primeiro objeto cujo nome é `nome` (sem acento, caixa nem pontuação), ou None."""
    alvo = _normalizar(nome)
    return next((o for o in objetos if _normalizar(getattr(o, campo)) == alvo), None)


# ----------------------------------------------------------------------
# A CATEGORIA, A PÁGINA E OS CARDS
# ----------------------------------------------------------------------

def categoria_dos_kits(so_ativa=True):
    """A categoria "Kits eletrônicos" (pelo nome, sem acento nem caixa), ou None."""
    from .models import CategoriasBrinquedos

    categorias = CategoriasBrinquedos.objects.order_by("id").only("id", "nome_categoria", "ativo")
    if so_ativa:
        categorias = categorias.filter(ativo=True)
    return _pelo_nome(list(categorias), "nome_categoria", NOME_DA_CATEGORIA)


def url_dos_kits():
    """A página da categoria dos kits, ou "" (sem a categoria, ou sem kit no ar)."""
    from django.conf import settings
    from django.urls import reverse

    from .models import Brinquedos

    categoria = categoria_dos_kits()
    if categoria is None or not Brinquedos.objects.filter(ativo=True, eh_kit=True).exists():
        return ""
    return reverse("categoria_detalhe", args=[categoria.pk], urlconf=settings.ROOT_URLCONF)


def preparar_cards(brinquedos):
    """Traz os itens e a máquina dos KITS da lista (a linha "7 itens: ..." e o "Para a máquina X").

    Só os kits: a lista sem kit nenhum não paga consulta nenhuma. Devolve a lista.
    """
    from django.db.models import prefetch_related_objects

    kits = [b for b in brinquedos if getattr(b, "eh_kit", False)]
    if kits:
        prefetch_related_objects(kits, "componentes_kit", "maquina")
    return brinquedos


def url_da_peca_avulsa(item):
    """A página da peça vendida sozinha (o Cabo HDMI), só se ela está na vitrine; senão ""."""
    from django.conf import settings
    from django.urls import reverse

    from .models import PecasReposicao

    peca = item.peca if item.peca_id else None
    if peca is None or not peca.ativo or peca.uso != PecasReposicao.Uso.LOJA:
        return ""
    return reverse("reposicao_detalhe", args=[peca.pk], urlconf=settings.ROOT_URLCONF)


def itens_da_pagina(kit):
    """O que vem no kit, para a página: nome, detalhe, quantidade, ícone, foto e a peça avulsa."""
    return [
        {
            "nome": item.nome,
            "detalhe": item.detalhe,
            "quantidade": item.quantidade,
            "icone": item.icone,
            "foto": foto_do_componente(item),
            "url_peca": url_da_peca_avulsa(item),
        }
        for item in kit.componentes_kit.select_related("peca").prefetch_related("peca__imagem_peca_reposicao")
    ]


# ----------------------------------------------------------------------
# OS KITS INICIAIS (o comando `kits_eletronicos`)
# ----------------------------------------------------------------------

def criar_kits_iniciais(avisar=print):
    """Cria, como produtos, os kits iniciais que faltam. Devolve {"criados": [...], "existentes": [...]}.

    IDEMPOTENTE: o kit é procurado pelo nome entre os produtos antes; o que
    já existe não é tocado (o dono pode ter mudado o nome dos itens, a
    máquina ou o preço no painel). A máquina é ligada pelo nome INTEIRO
    ("Strike Kids" não pega o "Strike Kids Boliche"); dela vêm a voltagem, a
    nota e as categorias, e o kit entra também em "Kits eletrônicos" (criada
    se falta). Sem preço: "Sob consulta". Num banco sem máquina nenhuma não
    há kit a criar.
    """
    from django.db import transaction

    from .categorias_capas import criar_sem_foto
    from .models import Brinquedos, CategoriasBrinquedos, ComponenteKit, PecasReposicao

    resultado = {"criados": [], "existentes": []}
    produtos = list(Brinquedos.objects.order_by("-ativo", "id").only("id", "nome_brinquedo", "ativo", "eh_kit"))
    maquinas = [b for b in produtos if not b.eh_kit]
    if not maquinas:
        return resultado
    avulsas = list(PecasReposicao.objects.order_by("-ativo", "id").only("id", "nome", "ativo"))
    categoria = categoria_dos_kits(so_ativa=False)
    for nome, nome_maquina, _chave, descricao, itens in KITS_INICIAIS:
        if _pelo_nome(produtos, "nome_brinquedo", nome) is not None:
            resultado["existentes"].append(nome)
            continue
        with transaction.atomic():
            if categoria is None:
                categoria = criar_sem_foto(CategoriasBrinquedos, NOME_DA_CATEGORIA)
            maquina = _pelo_nome(maquinas, "nome_brinquedo", nome_maquina)
            if maquina is not None:
                maquina = Brinquedos.objects.get(pk=maquina.pk)
            kit = Brinquedos.objects.create(
                nome_brinquedo=nome,
                descricao=descricao,
                valor_brinquedo=None,  # o dono põe no painel; até lá, "Sob consulta"
                avaliacao=maquina.avaliacao if maquina is not None else 5,
                voltz=(maquina.voltz if maquina is not None else "") or "",
                exibir_na_loja=True,
                eh_kit=True,
                maquina=maquina,
            )
            kit.categorias_brinquedos.add(categoria)
            if maquina is not None:
                kit.categorias_brinquedos.add(*maquina.categorias_brinquedos.all())
            for ordem, (item, detalhe, quantidade) in enumerate(itens, start=1):
                alvo = PECAS_AVULSAS.get(_normalizar(item))
                ComponenteKit.objects.create(
                    kit=kit, nome=item, detalhe=detalhe, quantidade=quantidade, ordem=ordem,
                    peca=_pelo_nome(avulsas, "nome", alvo) if alvo else None,
                )
        resultado["criados"].append(nome)
        avisar(f"{nome}: criado" + (f" (máquina {maquina.nome_brinquedo})" if maquina else " (sem máquina no catálogo)"))
    return resultado


# ----------------------------------------------------------------------
# A FOTO DO KIT (só com --foto: sobe para o Cloudinary)
# ----------------------------------------------------------------------

def arquivo_da_foto(chave):
    return PASTA / f"{chave}.webp"


def assinatura(caminho):
    """Os 10 primeiros dígitos do SHA-1 do arquivo: muda quando a arte muda."""
    return hashlib.sha1(Path(caminho).read_bytes()).hexdigest()[:10]


def subir_fotos(avisar=print):
    """Sobe a arte do repositório como capa do kit inicial que ainda NÃO tem foto.

    A foto que a equipe pôs no painel fica. Cada kit no seu ponto de
    salvamento; o nome do arquivo é curto e conferido contra os 100
    caracteres da coluna. A capa vira a frente da galeria
    (`sincronizar_imagem_legada_com_galeria`), marcada "com fundo" (a arte
    tem fundo de verdade). Devolve {"subidas": [...], "ja_tinham": [...], "falhas": [...]}.
    """
    from django.core.files import File
    from django.db import transaction

    from .models import Brinquedos, ImagemBrinquedo

    resultado = {"subidas": [], "ja_tinham": [], "falhas": []}
    kits = list(Brinquedos.objects.filter(eh_kit=True).order_by("id"))
    for nome, _maquina, chave, _descricao, _itens in KITS_INICIAIS:
        if not chave or not arquivo_da_foto(chave).exists():
            continue
        kit = _pelo_nome(kits, "nome_brinquedo", nome)
        if kit is None:
            continue
        if kit.imagem_brinquedo:
            resultado["ja_tinham"].append(nome)
            continue
        try:
            with transaction.atomic(), open(arquivo_da_foto(chave), "rb") as origem:
                kit.imagem_brinquedo.save(f"{chave}-{assinatura(arquivo_da_foto(chave))}.webp", File(origem),
                                          save=False)
                guardado = kit.imagem_brinquedo.name or ""
                if len(guardado) > LIMITE_DO_NOME:
                    raise ValueError(f"nome do arquivo com mais de {LIMITE_DO_NOME} caracteres: {guardado!r}")
                Brinquedos.objects.filter(pk=kit.pk).update(imagem_brinquedo=guardado)
                frente = kit.sincronizar_imagem_legada_com_galeria()
                if frente is not None:
                    ImagemBrinquedo.objects.filter(pk=frente.pk).update(fundo="com")
            resultado["subidas"].append(nome)
            avisar(f"{nome}: foto de capa ({guardado})")
        except Exception as erro:  # noqa: BLE001 -- os outros seguem
            resultado["falhas"].append(nome)
            avisar(f"{nome}: a foto não subiu agora ({erro!r}). Rode de novo: python manage.py kits_eletronicos --foto")
    return resultado


def limpar_cache():
    """A home, as categorias, a loja e as páginas guardadas passam a mostrar os kits."""
    try:
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001 -- o comando segue
        pass
