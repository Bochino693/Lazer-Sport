"""A capa QUADRADA de cada adesivo dos nossos 3D (LEIA-ME, seção 80).

O cliente, com os prints do catálogo: "de novo vc errou no dimensionamento de
algumas fotos, elas devem ser padrão. veja que não quero fotos cortadas
menores, deve seguir o mesmo padrão." Todo card de produto mostra a capa
QUADRADA (1600 x 1600) no showroom, com a máquina inteira enchendo o card: sem
faixas e sem zoom. Os que fugiam (conferido no site no ar):
  * o adesivo Alienígenas do Air Game Kids e o Quadrinhos do Basquete Home: a
    primeira foto do adesivo (a "capa" dele no seletor e no card que gira por
    adesivo) era a vista de 3/4 do 3D, 1600 x 1000;
  * os Brinquedões Modelo 4 (1,56 x 1) e Modelo 5 (1,69 x 1): a capa era a
    imagem da fábrica.

A CONVENÇÃO (a mesma das capas em cena, seções 64 e 78): a capa quadrada de um
adesivo é a foto DELE (`ImagemBrinquedo.variante`) na posição "perfil" (a
frente: a primeira da galeria do adesivo) marcada `papel_na_capa = "cena"`. A
do adesivo padrão é também a capa do produto (`imagem_brinquedo`: o card, o
quadro do topo, a API). O card que gira por adesivo usa exatamente essa foto.

A FOTO é a capa do 3D de cada adesivo, feita pelo ferramentas/categorias
(cenas.js, CAPAS; `gerar.cjs capas --compor`): core/static/site/arena/
modelos/<chave>/capa.webp. O Astronautas e os Modelos 4 e 5 ganharam a deles
agora, no showroom (o Modelo 4, um L de 19,6 m, inteiro).

Para cada item de ITENS, `aplicar`:
  * o adesivo que já tem a capa em cena (`papel = "cena"` na frente) fica; se
    é a nossa (`capa-<chave>-<assinatura>`) e a foto mudou, sobe a de hoje;
  * a frente do adesivo já é a nossa capa quadrada (o cadastro dos nossos 3D
    a subiu: `<chave>-capa`): só ganha o papel "cena";
  * a frente é a capa de antes que se conhece (a imagem da fábrica dos
    Modelos 4 e 5): ela sai da frente para a primeira posição livre do adesivo
    (em 3/4, o verso, de cima, os lados) -- CONTINUA NA GALERIA -- e a capa
    quadrada sobe como a frente, em cena;
  * o adesivo sem frente: a capa quadrada sobe como a frente;
  * outra foto qualquer na frente (a equipe trocou no painel): fica como está.
`desfazer` volta tudo: a capa que subiu sai, a de antes volta para a frente, o
papel "cena" que foi posto sai. Nada é apagado além da foto que esta rotina
subiu. Os itens sem 3D (o Azul do Basquete Home, o Premium do Air Game
Premium) só são CONFERIDOS: a capa em cena deles é a do catálogo (seção 64).

    python manage.py capas_em_cena --quadradas --simular
    python manage.py capas_em_cena --quadradas            (todos)
    python manage.py capas_em_cena --quadradas --so "Brinquedão Modelo 4"
    python manage.py capas_em_cena --quadradas --desfazer

A migração 0186 faz o mesmo no deploy, só no Render. O painel avisa quando a
capa enviada não é quadrada (`aviso_de_formato`): avisa e grava.
"""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

from django.core.files import File
from django.db import transaction

PASTA = Path(__file__).resolve().parent / "static" / "site"
MODELOS = PASTA / "arena" / "modelos"

PERFIL = "perfil"
CENA = "cena"
#: As posições livres para a capa de antes (a imagem da fábrica continua na galeria), na ordem.
POSICOES_LIVRES = ("tres_quartos", "verso", "de_cima", "lado_direito", "lado_esquerdo")
#: O lado do card: a capa é quadrada, 1600 x 1600.
LADO = 1600
#: Até onde a capa ainda conta como quadrada no aviso do painel (1,15 : 1).
QUASE_QUADRADA = 1.15

#: (a chave, o produto, o adesivo -- None é o padrão --, a foto quadrada -- None: só conferir --,
#:  as nossas capas quadradas que já podem estar na frente -- o nome do arquivo --,
#:  as capas de antes conhecidas, que saem da frente e ficam na galeria)
ITENS = (
    ("air-game-kids-astronautas", "Air Game Kids", "Astronautas",
     MODELOS / "air-game-kids-astronautas" / "capa.webp", ("air-game-kids-astronautas-capa",), ()),
    ("air-game-kids-alienigenas", "Air Game Kids", "Alienígenas",
     MODELOS / "air-game-kids-alienigenas" / "capa.webp", ("air-game-kids-alienigenas-capa",), ()),
    ("basquete-street-quadrinhos", "Basquete Home", "Quadrinhos",
     MODELOS / "basquete-street-quadrinhos" / "capa.webp", ("basquete-street-quadrinhos-capa",), ()),
    # o Azul não tem 3D: a capa quadrada é a do catálogo (capas_catalogo, seção 64), só conferida
    ("basquete-home", "Basquete Home", None, None, (), ()),
    # o Premium (o padrão do Air Game Premium; o Air Rock vira um adesivo dele): a do catálogo, conferida
    ("air-game-premium", "Air Game Premium", None, None, (), ()),
    ("brinquedao-modelo-4", "Brinquedão Modelo 4", None,
     MODELOS / "brinquedao-modelo-4" / "capa.webp", (), ("brinquedao-modelo-4-perspectiva",)),
    ("brinquedao-modelo-5", "Brinquedão Modelo 5", None,
     MODELOS / "brinquedao-modelo-5" / "capa.webp", (),
     ("brinquedao-modelo-5-salao_frente", "black-friday-2026-produto-brinquedao-modelo-5-")),
    # os nossos 3D de um adesivo só: a capa do cadastro já é quadrada; só ganha o papel "cena"
    ("brinquedao-modelo-2", "Brinquedão Modelo 2", None, MODELOS / "brinquedao-modelo-2" / "capa.webp",
     ("brinquedao-modelo-2-capa",), ()),
    ("brinquedao-modelo-3", "Brinquedão Modelo 3", None, MODELOS / "brinquedao-modelo-3" / "capa.webp",
     ("brinquedao-modelo-3-capa",), ()),
    ("brinquedao-ninja", "Brinquedão Ninja", None, MODELOS / "brinquedao-ninja" / "capa.webp",
     ("brinquedao-ninja-capa",), ()),
    ("espaco-esportivo-modelo-1", "Espaço Esportivo Modelo 1", None,
     MODELOS / "espaco-esportivo-modelo-1" / "capa.webp", ("espaco-esportivo-modelo-1-capa",), ()),
    ("trampolim-enterrada", "Trampolim de Enterrada", None, MODELOS / "trampolim-enterrada" / "capa.webp",
     ("trampolim-enterrada-capa",), ()),
    ("strike-kids", "Strike Kids", None, MODELOS / "strike-kids" / "capa.webp", ("strike-kids-capa",), ()),
)


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def _rotulo(item):
    _chave, produto, adesivo, *_ = item
    return f"{produto} ({adesivo})" if adesivo else produto


def assinatura(caminho):
    return hashlib.sha1(Path(caminho).read_bytes()).hexdigest()[:10]


def nome_no_cadastro(chave, caminho):
    """O nome do arquivo que sobe: `capa-<chave>-<assinatura>` (a capa refeita sobe de novo; a mesma, não)."""
    return f"capa-{chave}-{assinatura(caminho)}.webp"


def _casa(nome, raizes):
    """O arquivo `nome` é uma destas fotos? (a raiz inteira e depois só o sufixo do armazenamento ou a versão)

    A raiz que termina em "-" é um começo (o nome da Black Friday tem a assinatura depois).
    """
    base = Path(nome or "").name
    for raiz in raizes:
        if raiz.endswith("-"):
            if base.startswith(raiz):
                return True
        elif base == raiz or base.startswith((raiz + "_", raiz + ".", raiz + "-v")):
            return True
    return False


def escolher(so=()):
    """Os itens pedidos (`so`: o produto, "produto (adesivo)", o adesivo ou a chave; vazio, todos)."""
    if not so:
        return list(ITENS)
    pedidos = {_normalizar(str(s)) for s in so}
    return [item for item in ITENS
            if {_normalizar(item[0]), _normalizar(item[1]), _normalizar(item[2] or ""), _normalizar(_rotulo(item))} & pedidos]


def _achar(nome, Brinquedos):
    alvo = _normalizar(nome)
    return next((b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo), None)


def _adesivo(brinquedo, nome, VarianteAdesivo):
    """O adesivo pelo nome (None: o padrão). Devolve (adesivo ou None, é o padrão)."""
    if nome is None:
        padrao = None
        if getattr(brinquedo, "adesivo_padrao_id", None):
            padrao = VarianteAdesivo.objects.filter(pk=brinquedo.adesivo_padrao_id).first()
        if padrao is None:
            padrao = VarianteAdesivo.objects.filter(brinquedo=brinquedo, padrao=True).order_by("ordem", "id").first()
        return padrao, True
    alvo = _normalizar(nome)
    variante = next((v for v in VarianteAdesivo.objects.filter(brinquedo=brinquedo) if _normalizar(v.nome) == alvo), None)
    e_padrao = variante is not None and (variante.padrao or variante.pk == getattr(brinquedo, "adesivo_padrao_id", None))
    return variante, e_padrao


def _fotos(brinquedo, variante, e_padrao, ImagemBrinquedo):
    """As fotos do adesivo (as do padrão contam também as ainda sem adesivo, como na galeria)."""
    fotos = ImagemBrinquedo.objects.filter(brinquedo=brinquedo).order_by("ordem", "id")
    if variante is None:
        return list(fotos.filter(variante__isnull=True))
    return [f for f in fotos if f.variante_id == variante.pk or (e_padrao and f.variante_id is None)]


def _a_cena(fotos):
    return next((f for f in fotos if f.tipo == PERFIL and f.papel_na_capa == CENA and f.imagem), None)


def _criar_capa(brinquedo, variante, chave, caminho, ImagemBrinquedo, rotulo):
    foto = ImagemBrinquedo(
        brinquedo=brinquedo, variante=variante, tipo=PERFIL, ordem=1, papel_na_capa=CENA,
        texto_alternativo=f"{rotulo} no showroom da Lazer & Sport"[:180],
    )
    if hasattr(foto, "fundo"):
        foto.fundo = "com"
    with open(caminho, "rb") as origem:
        foto.imagem.save(nome_no_cadastro(chave, caminho), File(origem), save=True)
    return foto


def aplicar_um(item, Brinquedos, ImagemBrinquedo, VarianteAdesivo, simular=False):
    """Põe a capa quadrada em cena no adesivo. Devolve o que fez (uma frase)."""
    chave, produto, adesivo, caminho, nossas, de_antes = item
    rotulo = _rotulo(item)
    brinquedo = _achar(produto, Brinquedos)
    if brinquedo is None:
        return f"{rotulo}: não está no catálogo."
    variante, e_padrao = _adesivo(brinquedo, adesivo, VarianteAdesivo)
    if adesivo is not None and variante is None:
        return f"{rotulo}: o {produto} não tem o adesivo {adesivo}."
    fotos = _fotos(brinquedo, variante, e_padrao, ImagemBrinquedo)
    cena = _a_cena(fotos)
    if cena is not None:
        if variante is not None and cena.variante_id is None:
            # (a foto de antes da estrutura dos adesivos: passa para o padrão, onde ela já contava)
            if not simular:
                ImagemBrinquedo.objects.filter(pk=cena.pk).update(variante=variante)
        if caminho is None or not Path(cena.imagem.name).name.startswith(f"capa-{chave}-"):
            return f"{rotulo}: já está com a capa quadrada em cena."
        novo = nome_no_cadastro(chave, caminho)
        if Path(novo).stem in cena.imagem.name:
            return f"{rotulo}: já está com a capa quadrada em cena."
        if simular:
            return f"{rotulo}: trocaria a capa quadrada pela de hoje."
        with transaction.atomic():
            with open(caminho, "rb") as origem:
                cena.imagem.save(novo, File(origem), save=True)
            if e_padrao:
                Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=cena.imagem.name)
        return f"{rotulo}: a capa quadrada foi trocada pela de hoje."
    if caminho is None:
        return (f"{rotulo}: SEM a capa quadrada em cena e sem 3D para fazer uma -- a do catálogo vem do "
                "capas_em_cena (seção 64); ou ponha uma foto quadrada na frente pelo painel.")
    frente = next((f for f in fotos if f.tipo == PERFIL), None)
    capa_antiga = (brinquedo.imagem_brinquedo.name or "") if e_padrao else ""
    if frente is not None and _casa(frente.imagem.name, nossas):
        # a capa quadrada do cadastro já está na frente: só o papel
        if simular:
            return f"{rotulo}: marcaria a capa quadrada que já está na frente como a capa em cena."
        with transaction.atomic():
            ImagemBrinquedo.objects.filter(pk=frente.pk).update(papel_na_capa=CENA, variante=variante or frente.variante)
            if e_padrao and capa_antiga != frente.imagem.name:
                Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=frente.imagem.name)
        return f"{rotulo}: a capa quadrada da frente agora é a capa em cena."
    if frente is not None and not _casa(frente.imagem.name, de_antes):
        return f"{rotulo}: a frente foi trocada no painel ({frente.imagem.name}); fica como está."
    if frente is None and e_padrao and capa_antiga and not _casa(capa_antiga, nossas + de_antes) \
            and not Path(capa_antiga).name.startswith(f"capa-{chave}-"):
        return f"{rotulo}: a capa foi trocada no painel ({capa_antiga}); fica como está."
    if simular:
        if frente is not None:
            return f"{rotulo}: poria a capa quadrada (a de antes continua na galeria, em outra posição)."
        return f"{rotulo}: poria a capa quadrada como a frente do adesivo."
    with transaction.atomic():
        tomadas = {f.tipo for f in fotos if f.tipo}
        livre = next((p for p in POSICOES_LIVRES if p not in tomadas), None)
        if frente is not None:
            # a capa de antes (a imagem da fábrica) sai da frente e fica na galeria, na primeira posição livre
            ImagemBrinquedo.objects.filter(pk=frente.pk).update(tipo=livre, variante=variante or frente.variante)
        elif e_padrao and capa_antiga and _casa(capa_antiga, de_antes):
            # a capa de antes só no campo do produto: vira uma foto da galeria, para o --desfazer
            guardada = ImagemBrinquedo(brinquedo=brinquedo, variante=variante, tipo=livre, ordem=2,
                                       imagem=capa_antiga, texto_alternativo=f"{rotulo}: a foto da fábrica"[:180])
            guardada.save()
        nova = _criar_capa(brinquedo, variante, chave, caminho, ImagemBrinquedo, rotulo)
        if e_padrao:
            Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=nova.imagem.name)
    if frente is not None and livre is None:
        return f"{rotulo}: a capa agora é a quadrada; a de antes ficou guardada (o adesivo não tinha posição livre)."
    return f"{rotulo}: a capa agora é a quadrada no showroom" + (" (a de antes continua na galeria)." if frente else ".")


def desfazer_um(item, Brinquedos, ImagemBrinquedo, VarianteAdesivo, simular=False):
    """Volta a capa de antes do adesivo. Devolve o que fez (uma frase)."""
    chave, produto, adesivo, caminho, nossas, de_antes = item
    rotulo = _rotulo(item)
    if caminho is None:
        return f"{rotulo}: só conferido; nada a desfazer."
    brinquedo = _achar(produto, Brinquedos)
    if brinquedo is None:
        return f"{rotulo}: não está no catálogo."
    variante, e_padrao = _adesivo(brinquedo, adesivo, VarianteAdesivo)
    if adesivo is not None and variante is None:
        return f"{rotulo}: o {produto} não tem o adesivo {adesivo}."
    fotos = _fotos(brinquedo, variante, e_padrao, ImagemBrinquedo)
    subiu = [f for f in fotos if f.papel_na_capa == CENA and Path(f.imagem.name).name.startswith(f"capa-{chave}-")]
    marcada = [f for f in fotos if f.papel_na_capa == CENA and _casa(f.imagem.name, nossas)]
    if not subiu and not marcada:
        return f"{rotulo}: não está com a capa quadrada desta rotina."
    if simular:
        return f"{rotulo}: voltaria a capa de antes."
    with transaction.atomic():
        for foto in marcada:
            ImagemBrinquedo.objects.filter(pk=foto.pk).update(papel_na_capa="")
        for foto in subiu:
            foto.delete()
        antes = next((f for f in fotos if f not in subiu and f.tipo != PERFIL and _casa(f.imagem.name, de_antes)), None)
        frente_livre = not ImagemBrinquedo.objects.filter(pk__in=[f.pk for f in fotos if f not in subiu], tipo=PERFIL).exists()
        if antes is not None and frente_livre:
            ImagemBrinquedo.objects.filter(pk=antes.pk).update(tipo=PERFIL)
        if e_padrao and subiu:
            capa = (antes.imagem.name if antes is not None else
                    next((f.imagem.name for f in marcada), "")) or ""
            Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=capa)
    return f"{rotulo}: a capa de antes voltou."


def rodar(Brinquedos, ImagemBrinquedo, VarianteAdesivo, so=(), simular=False, desfazer=False, avisar=print):
    """Aplica (ou desfaz) em cada item; um erro num adesivo não para os outros. Devolve {rótulo: frase}."""
    feito = {}
    for item in escolher(so):
        try:
            frase = (desfazer_um if desfazer else aplicar_um)(item, Brinquedos, ImagemBrinquedo, VarianteAdesivo,
                                                               simular=simular)
        except Exception as erro:  # a subida falhou: segue com os outros e avisa o comando
            frase = (f"{_rotulo(item)}: não foi feito agora ({erro!r}). "
                     f"Rode: python manage.py capas_em_cena --quadradas --so \"{item[1]}\"")
        feito[_rotulo(item)] = frase
        avisar(frase)
    return feito


def no_deploy(apps, schema_editor, avisar=print):
    """A migração 0186: só no Render (o Cloudinary só está lá); se algo falhar, o deploy segue."""
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    try:
        feito = rodar(apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"),
                      apps.get_model("core", "VarianteAdesivo"), avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As capas quadradas não subiram agora ({erro!r}). Rode: python manage.py capas_em_cena --quadradas")
        return None
    try:  # os cards, a página e a home guardados em cache passam a mostrar a capa quadrada
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001
        pass
    return feito


# ----------------------------------------------------------------------
# O aviso do painel
# ----------------------------------------------------------------------

def formato(arquivo):
    """A proporção (a maior sobre a menor) da imagem `arquivo` (um caminho ou um arquivo enviado); None se não abre."""
    from PIL import Image

    posicao = arquivo.tell() if hasattr(arquivo, "tell") else None
    try:
        with Image.open(arquivo) as imagem:
            largura, altura = imagem.size
    except Exception:  # noqa: BLE001 -- não é uma imagem que o Pillow abre: o campo de imagem confere
        return None
    finally:
        if posicao is not None:
            arquivo.seek(posicao)
    if not largura or not altura:
        return None
    return largura / altura


def aviso_de_formato(arquivo):
    """O aviso (não bloqueia) para a capa que não é quase quadrada: "" quando está tudo bem."""
    proporcao = formato(arquivo)
    if proporcao is None or max(proporcao, 1 / proporcao) <= QUASE_QUADRADA:
        return ""
    numero = f"{proporcao:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"A capa do card deve ser quadrada (1:1); esta é {numero}:1."
