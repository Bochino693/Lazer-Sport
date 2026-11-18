"""O KIT ELETRÔNICO: a parte elétrica de uma máquina, sem a máquina (LEIA-ME seção 105).

O PEDIDO, nas palavras do dono: "no site, precisamos agora também do chamado
kit, ele deve ter espaço entre os demais produtos, o kit seria o seguinte, os
componentes eletrônicos sem a máquina para troca ou semi instalação, por
exemplo, strike kids, uma tv box, 5 sensores de precisão, a câmera e etc, para
o cara instalar toda parte elétrica na máquina caso ele só tenha a máquina, no
lazer shot, a arma, a tv box". E a arte de exemplo: "KIT BOLICHE VIRTUAL --
Monte sua própria máquina! Kit completo e pronto para instalar".

O KIT É UMA PEÇA MARCADA (`PecasReposicao.eh_kit`), e não um tipo novo no
carrinho: a peça já passa pelo carrinho, pelo Pix/cartão/boleto, pelas
parcelas sem juros, pelo pedido, pelas etiquetas e pelo painel. O que é só do
kit mora aqui:

  * o ícone de cada item na página do kit (`icone_do_componente`);
  * a lista curta do card ("7 itens: TV Box, ...", `resumo_dos_itens`);
  * os três kits iniciais (`KITS_INICIAIS`) e quem os cria -- a migração
    0208 e o comando `python manage.py kits_eletronicos`;
  * a foto do Kit Boliche Virtual (a arte do dono, em
    core/static/site/kits/), que sobe para o Cloudinary SÓ NO RENDER.

SEM PREÇO. Os kits nascem sem preço: o dono põe o preço no painel (Peças).
Até lá o site mostra "Sob consulta" e o botão do WhatsApp, como os
brinquedos fora da loja; o carrinho recusa o kit sem preço
(`views._item_vendavel`).
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


def _pelo_nome(objetos, campo, nome):
    """O primeiro objeto cujo nome é `nome` (sem acento, caixa nem pontuação), ou None."""
    alvo = _normalizar(nome)
    return next((o for o in objetos if _normalizar(getattr(o, campo)) == alvo), None)


def maquina_do_kit(Brinquedos, nome):
    """A máquina do catálogo com este nome (a ativa primeiro), ou None.

    Pelo nome INTEIRO: "Strike Kids" não pode pegar o "Strike Kids Boliche".
    """
    candidatos = list(Brinquedos.objects.order_by("-ativo", "id").only("id", "nome_brinquedo", "ativo"))
    return _pelo_nome(candidatos, "nome_brinquedo", nome)


def peca_avulsa(PecasReposicao, nome_do_item):
    """A peça da vitrine que é este item (o Cabo HDMI), se ela existir; senão None."""
    alvo = PECAS_AVULSAS.get(_normalizar(nome_do_item))
    if not alvo:
        return None
    pecas = list(
        PecasReposicao.objects.filter(eh_kit=False).order_by("-ativo", "id").only("id", "nome", "ativo")
    )
    return _pelo_nome(pecas, "nome", alvo)


def criar_kits_iniciais(PecasReposicao, Brinquedos, ComponenteKit, avisar=print):
    """Cria os kits que ainda não existem. Devolve {"criados": [nomes], "existentes": [nomes]}.

    IDEMPOTENTE: o kit é procurado pelo nome antes (sem acento nem caixa); o
    que já existe não é tocado -- o dono pode ter mudado o nome dos itens, a
    máquina ou o preço no painel. Recebe os modelos para servir à migração
    (modelos históricos) e ao comando.
    """
    resultado = {"criados": [], "existentes": []}
    existentes = list(PecasReposicao.objects.only("id", "nome"))
    for nome, nome_maquina, _chave, descricao, itens in KITS_INICIAIS:
        if _pelo_nome(existentes, "nome", nome) is not None:
            resultado["existentes"].append(nome)
            continue
        maquina = maquina_do_kit(Brinquedos, nome_maquina)
        kit = PecasReposicao.objects.create(
            nome=nome,
            descricao_peca=descricao,
            uso="loja",
            ativo=True,
            eh_kit=True,
            maquina=maquina,
            # sem preço: o dono põe no painel; até lá, "Sob consulta"
            preco_venda=None,
            preco_fornecedor=None,
        )
        for ordem, (item, detalhe, quantidade) in enumerate(itens, start=1):
            ComponenteKit.objects.create(
                kit=kit, nome=item, detalhe=detalhe, quantidade=quantidade, ordem=ordem,
                peca=peca_avulsa(PecasReposicao, item),
            )
        resultado["criados"].append(nome)
        avisar(f"{nome}: criado" + (f" (máquina {maquina.nome_brinquedo})" if maquina else " (sem máquina no catálogo)"))
    return resultado


# ----------------------------------------------------------------------
# A FOTO DO KIT
# ----------------------------------------------------------------------

def arquivo_da_foto(chave):
    return PASTA / f"{chave}.webp"


def assinatura(caminho):
    """Os 10 primeiros dígitos do SHA-1 do arquivo: muda quando a arte muda."""
    return hashlib.sha1(Path(caminho).read_bytes()).hexdigest()[:10]


def subir_fotos(PecasReposicao, ImagemPeca, avisar=print):
    """Sobe a foto de capa dos kits que têm arte no repositório e ainda não têm foto.

    Só o kit SEM foto ganha a arte: a foto que a equipe pôs no painel fica.
    Cada foto no seu ponto de salvamento (no PostgreSQL um erro de banco
    aborta a transação inteira da migração). A arte do kit tem fundo de
    verdade (escuro): o recorte automático das peças (core/recorte_peca.py)
    não tem o que tirar dela, e `recorte_de` já nasce marcado para ele nem
    baixar a foto de novo. Devolve {"subidas": [...], "ja_tinham": [...], "falhas": [...]}.
    """
    from django.core.files import File
    from django.db import transaction

    resultado = {"subidas": [], "ja_tinham": [], "falhas": []}
    kits = list(PecasReposicao.objects.filter(eh_kit=True).only("id", "nome"))
    for nome, _maquina, chave, _descricao, _itens in KITS_INICIAIS:
        if not chave or not arquivo_da_foto(chave).exists():
            continue
        kit = _pelo_nome(kits, "nome", nome)
        if kit is None:
            continue
        if ImagemPeca.objects.filter(peca_reposicao_id=kit.pk).exists():
            resultado["ja_tinham"].append(nome)
            continue
        try:
            with transaction.atomic(), open(arquivo_da_foto(chave), "rb") as origem:
                foto = ImagemPeca(peca_reposicao_id=kit.pk, posicao="frente", ordem=1)
                foto.imagem.save(f"{chave}-{assinatura(arquivo_da_foto(chave))}.webp", File(origem), save=False)
                guardado = foto.imagem.name or ""
                if len(guardado) > LIMITE_DO_NOME:
                    raise ValueError(f"nome do arquivo com mais de {LIMITE_DO_NOME} caracteres: {guardado!r}")
                foto.recorte_de = guardado
                foto.save()
            resultado["subidas"].append(nome)
            avisar(f"{nome}: foto de capa ({guardado})")
        except Exception as erro:  # noqa: BLE001 -- o deploy segue; o comando refaz
            resultado["falhas"].append(nome)
            avisar(f"{nome}: a foto não subiu agora ({erro!r}). Rode: python manage.py kits_eletronicos --foto")
    return resultado


def limpar_cache():
    """A home, /kits/, a loja e as páginas das máquinas guardadas passam a mostrar os kits."""
    try:
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001 -- o deploy segue
        pass


def semear(apps, schema_editor=None, avisar=print):
    """A migração 0208: cria os kits que faltam; a foto sobe SÓ NO RENDER.

    O Cloudinary só está configurado no Render: no computador e nos testes
    nada sobe (o kit sem foto mostra a foto da máquina, com o selo).

    Num banco SEM máquina nenhuma -- o dos testes, um novo -- não há kit a
    criar (a mesma regra das áreas, core/categorias_capas.py): o kit é a
    eletrônica de uma máquina do catálogo. No banco do site, com o catálogo,
    os três nascem (o da máquina que não existir, sem máquina). Para criar
    depois: python manage.py kits_eletronicos.
    """
    from django.conf import settings

    PecasReposicao = apps.get_model("core", "PecasReposicao")
    Brinquedos = apps.get_model("core", "Brinquedos")
    if not Brinquedos.objects.exists():
        return {"criados": [], "existentes": [], "catalogo_vazio": True}
    resultado = criar_kits_iniciais(
        PecasReposicao,
        Brinquedos,
        apps.get_model("core", "ComponenteKit"),
        avisar=avisar,
    )
    if getattr(settings, "IS_RENDER", False):
        resultado["fotos"] = subir_fotos(PecasReposicao, apps.get_model("core", "ImagemPeca"), avisar=avisar)
    limpar_cache()
    return resultado
