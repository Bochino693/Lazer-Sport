"""As fotos de estúdio dos nossos 3D no cadastro (LEIA-ME, seção 96). Só dados.

O chefe, sobre o Basquete Home, o Boliche Kids (o Strike Kids) e o Air Game Kids
Alienígenas: "como o McDonald's: você olha a foto do lanche e quer comer, porque tem vida e
nitidez. As nossas estão apagadas, sem vida; os fundos parecem muito falsos, não uma foto
de câmera 4K". E: "o Basquete Home normal e o preto: a máquina encolheu".

As fotos foram refeitas no estúdio do Blender (ferramentas/fotos3d/: o Cycles, o fundo
infinito azul, o softbox, as luzes de recorte da marca, os adesivos de vinil brilhante e os
LEDs acesos), com UM enquadramento por máquina -- o azul e o preto do Basquete Home, os
Astronautas e os Alienígenas do Air Game Kids saem do mesmo tamanho na mesma foto. Os
arquivos do site são os mesmos de antes (core/static/site/arena/modelos/<pasta>/*.webp e as
capas do catálogo, core/static/site/capas_catalogo/), com a foto nova.

O site mostra as fotos do Cloudinary (ImagemBrinquedo). Para cada foto de ITENS, `aplicar`:
  * a posição (a frente/capa, em 3/4, os lados, o verso, de cima) do adesivo que está com a
    NOSSA foto de antes (o nome do arquivo que o cadastro, as capas em cena, as capas
    quadradas ou as posições do 3D subiram: `antes`) ganha a foto de estúdio, que sobe com o
    nome `estudio-<pasta>-<vista>-<assinatura>` -- a foto que mudou sobe de novo; a mesma,
    não. A de antes CONTINUA no adesivo, sem a posição (fora da galeria pública), para a volta;
  * a capa (a frente, "perfil") fica com o papel "cena"; a do adesivo padrão também é a capa
    do produto (`imagem_brinquedo`: o card, o quadro do topo, a API);
  * a posição que estava vazia (o Strike Kids em 3/4 e de cima; o Quadrinhos de cima, com o
    detalhe de quem joga) ganha a foto;
  * a foto que a equipe pôs no painel numa posição fica como está.
`desfazer` volta tudo: a foto de estúdio sai do cadastro (o arquivo fica no Cloudinary) e a
de antes volta para a posição (a capa, com o papel "cena" e de volta no produto).

SÓ NO RENDER (o Cloudinary só está lá; a migração 0197). Se uma subida falhar, o deploy
segue e o aviso diz o comando:
    python manage.py fotos_de_estudio [--simular] [--so "Strike Kids"] [--desfazer]
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from django.core.files import File
from django.db import transaction

ESTATICO = Path(__file__).resolve().parent / "static"
PERFIL = "perfil"
CENA = "cena"
#: Os papéis de foto guardada (fora do site): nunca são a foto "de antes" de uma posição.
FORA_DO_SITE = ("original", "recorte")
#: O sufixo que o armazenamento põe no nome (o Cloudinary e o disco: _ e 5 a 8 letras) e a extensão.
_SUFIXO = r"(_[A-Za-z0-9]{5,8})?(\.[A-Za-z0-9]+)?"
_ASSINATURA = r"[0-9a-f]{10}"


def _vista(pasta, stem, versoes=True):
    """O nome que o cadastro / as posições do 3D davam: `<pasta>-<vista>` (e as versões -v2...)."""
    return re.escape(f"{pasta}-{stem}") + (r"(-v\d+)?" if versoes else "")


def _capa_quadrada(pasta):
    """O nome da capa quadrada (core/capas_quadradas.py): `capa-<pasta>-<assinatura>`."""
    return re.escape(f"capa-{pasta}-") + _ASSINATURA


def _cena(chave):
    """O nome da capa em cena do catálogo (core/capas_catalogo.py): `cena-<chave>-<assinatura>`."""
    return re.escape(f"cena-{chave}-") + _ASSINATURA


def _foto(arquivo, posicao, rotulo, antes, nova=False):
    """Uma foto: o arquivo (em core/static/), a posição, o rótulo e os nomes da NOSSA foto de antes.

    `nova`: a posição não tinha foto nossa (na volta, nenhuma volta para ela).
    """
    return {"arquivo": arquivo, "posicao": posicao, "rotulo": rotulo, "antes": tuple(antes), "nova": nova}


_BQ = "basquete-street-quadrinhos"
_AL = "air-game-kids-alienigenas"
_AS = "air-game-kids-astronautas"
_SK = "strike-kids"
_M = "site/arena/modelos"

#: (produto, adesivo -- None: o adesivo padrão --, [fotos]). As vistas: ferramentas/fotos3d/produtos.py.
ITENS = (
    ("Basquete Home", "Quadrinhos", (
        _foto(f"{_M}/{_BQ}/capa.webp", PERFIL, "no estúdio, de 3/4",
              (_vista(_BQ, "capa", False), _capa_quadrada(_BQ))),
        _foto(f"{_M}/{_BQ}/frente.webp", "tres_quartos", "de frente, em 3/4: o console com o POW! e a pista",
              (_vista(_BQ, "frente"),)),
        _foto(f"{_M}/{_BQ}/lado_direito.webp", "lado_direito", "o lado direito, por trás: a bola grande e as crianças",
              (_vista(_BQ, "lado_direito"),)),
        _foto(f"{_M}/{_BQ}/lado_esquerdo.webp", "lado_esquerdo", "o lado esquerdo: a bola grande e as crianças",
              (_vista(_BQ, "lado_esquerdo"),)),
        _foto(f"{_M}/{_BQ}/verso.webp", "verso", "visto por trás", (_vista(_BQ, "verso"),)),
        # o detalhe de perto: a quadra, as bolas, a cesta, o BOOM! e o placar, do alto
        _foto(f"{_M}/{_BQ}/jogador.webp", "de_cima", "de quem joga, do alto: a cesta, o placar e as bolas",
              (_vista(_BQ, "jogador"),), nova=True),
    )),
    # o azul (o padrão) ainda não tem 3D: a foto da fábrica no mesmo estúdio, no mesmo tamanho do Quadrinhos
    ("Basquete Home", None, (
        _foto("site/capas_catalogo/basquete-home.webp", PERFIL, "no estúdio, de 3/4", (_cena("basquete-home"),)),
    )),
    ("Air Game Kids", "Alienígenas", (
        _foto(f"{_M}/{_AL}/capa.webp", PERFIL, "no estúdio, de 3/4", (_vista(_AL, "capa", False), _capa_quadrada(_AL))),
        _foto(f"{_M}/{_AL}/frente.webp", "tres_quartos", "de frente, em 3/4", (_vista(_AL, "frente"),)),
        _foto(f"{_M}/{_AL}/lado_direito.webp", "lado_direito", "o lado direito", (_vista(_AL, "lado_direito"),)),
        _foto(f"{_M}/{_AL}/lado_esquerdo.webp", "lado_esquerdo", "o lado esquerdo, na altura das crianças",
              (_vista(_AL, "lado_esquerdo"),)),
        _foto(f"{_M}/{_AL}/verso.webp", "verso", "a cabeceira", (_vista(_AL, "verso"),)),
        _foto(f"{_M}/{_AL}/tampo.webp", "de_cima", "o tampo, de cima", (_vista(_AL, "tampo"),)),
    )),
    # o padrão do Air Game Kids: a capa do produto é a do catálogo (a mesma foto da capa do 3D)
    ("Air Game Kids", "Astronautas", (
        _foto("site/capas_catalogo/air-game-kids.webp", PERFIL, "no estúdio, de 3/4",
              (_cena("air-game-kids"), _vista(_AS, "capa", False), _capa_quadrada(_AS))),
        _foto(f"{_M}/{_AS}/frente.webp", "tres_quartos", "de frente, em 3/4", (_vista(_AS, "frente"),)),
        _foto(f"{_M}/{_AS}/lado_direito.webp", "lado_direito", "o lado direito", (_vista(_AS, "lado_direito"),)),
        _foto(f"{_M}/{_AS}/lado_esquerdo.webp", "lado_esquerdo", "o lado esquerdo, na altura das crianças",
              (_vista(_AS, "lado_esquerdo"),)),
        _foto(f"{_M}/{_AS}/verso.webp", "verso", "a cabeceira", (_vista(_AS, "verso"),)),
        _foto(f"{_M}/{_AS}/tampo.webp", "de_cima", "o tampo, de cima", (_vista(_AS, "tampo"),)),
    )),
    ("Strike Kids", None, (
        _foto(f"{_M}/{_SK}/capa.webp", PERFIL, "no estúdio, de 3/4", (_vista(_SK, "capa", False), _capa_quadrada(_SK))),
        # o estúdio apagado: os LEDs, a tela e o neon acesos
        _foto(f"{_M}/{_SK}/tres_quartos_esquerda.webp", "tres_quartos", "de 3/4 pelo lado esquerdo, com as luzes acesas",
              (_vista(_SK, "tres_quartos_esquerda"),), nova=True),
        _foto(f"{_M}/{_SK}/lado_direito.webp", "lado_direito", "o lado direito, com a arte dos pinos",
              (_vista(_SK, "lado_direito"),)),
        _foto(f"{_M}/{_SK}/lado_esquerdo.webp", "lado_esquerdo", "o lado esquerdo, com a arte dos pinos",
              (_vista(_SK, "lado_esquerdo"),)),
        _foto(f"{_M}/{_SK}/verso.webp", "verso", "visto por trás", (_vista(_SK, "verso"),)),
        _foto(f"{_M}/{_SK}/de_cima.webp", "de_cima", "do alto: a pista inteira, as bolas e a tela",
              (_vista(_SK, "de_cima"),), nova=True),
    )),
)


# ----------------------------------------------------------------------
# Os nomes
# ----------------------------------------------------------------------

def _normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def caminho(foto):
    return ESTATICO / foto["arquivo"]


def _pasta_e_vista(foto):
    arquivo = Path(foto["arquivo"])
    pasta = "catalogo" if arquivo.parent.name == "capas_catalogo" else arquivo.parent.name
    return pasta, arquivo.stem


def assinatura(foto):
    return hashlib.sha1(caminho(foto).read_bytes()).hexdigest()[:10]


def nome_no_cadastro(foto):
    """O nome do arquivo que sobe: `estudio-<pasta>-<vista>-<assinatura>.webp` (a foto refeita sobe de novo)."""
    pasta, vista = _pasta_e_vista(foto)
    return f"estudio-{pasta}-{vista}-{assinatura(foto)}.webp"


def _base(nome):
    return Path(nome or "").name


def e_de_estudio(nome, foto):
    """O arquivo é uma foto de estúdio desta vista (de qualquer versão)?"""
    pasta, vista = _pasta_e_vista(foto)
    return re.fullmatch(re.escape(f"estudio-{pasta}-{vista}-") + _ASSINATURA + _SUFIXO, _base(nome)) is not None


def _versao(nome):
    achado = re.search(r"-v(\d+)(?:_[A-Za-z0-9]{5,8})?(?:\.[A-Za-z0-9]+)?$", _base(nome))
    return int(achado.group(1)) if achado else 1


def e_a_de_antes(nome, foto):
    """O arquivo é a NOSSA foto de antes desta vista (o nome que o cadastro / as rotinas deram)?"""
    return any(re.fullmatch(raiz + _SUFIXO, _base(nome)) for raiz in foto["antes"])


# ----------------------------------------------------------------------
# O adesivo e as fotos dele
# ----------------------------------------------------------------------

def _achar(nome, Brinquedos):
    alvo = _normalizar(nome)
    return next((b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo), None)


def _adesivo(brinquedo, nome, VarianteAdesivo):
    """(o adesivo, é o padrão). `nome` None: o padrão do brinquedo."""
    padrao_id = getattr(brinquedo, "adesivo_padrao_id", None)
    if nome is None:
        variante = VarianteAdesivo.objects.filter(pk=padrao_id).first() if padrao_id else None
        variante = variante or VarianteAdesivo.objects.filter(brinquedo=brinquedo, padrao=True).order_by("ordem", "id").first()
        return variante, True
    alvo = _normalizar(nome)
    variante = next((v for v in VarianteAdesivo.objects.filter(brinquedo=brinquedo) if _normalizar(v.nome) == alvo), None)
    return variante, variante is not None and (variante.padrao or variante.pk == padrao_id)


def _fotos_do_adesivo(brinquedo, variante, e_padrao, ImagemBrinquedo):
    """As fotos do adesivo (as do padrão contam também as ainda sem adesivo, como na galeria)."""
    fotos = ImagemBrinquedo.objects.filter(brinquedo=brinquedo).order_by("ordem", "id")
    if variante is None:
        return list(fotos.filter(variante__isnull=True))
    return [f for f in fotos if f.variante_id == variante.pk or (e_padrao and f.variante_id is None)]


def _rotulo(produto, adesivo):
    return f"{produto} ({adesivo})" if adesivo else produto


# ----------------------------------------------------------------------
# Aplicar e desfazer
# ----------------------------------------------------------------------

def _subir(foto, destino):
    with open(caminho(foto), "rb") as origem:
        destino.imagem.save(nome_no_cadastro(foto), File(origem), save=True)


def aplicar_foto(brinquedo, variante, e_padrao, foto, Brinquedos, ImagemBrinquedo, rotulo, simular=False):
    """Põe a foto de estúdio na posição dela. Devolve o que fez (uma frase)."""
    posicao = foto["posicao"]
    vista = f"{rotulo}, {foto['rotulo']}"
    fotos = _fotos_do_adesivo(brinquedo, variante, e_padrao, ImagemBrinquedo)
    na_posicao = [f for f in fotos if f.tipo == posicao and f.papel_na_capa not in FORA_DO_SITE and f.imagem]
    atual = na_posicao[0] if na_posicao else None
    if atual is not None and e_de_estudio(atual.imagem.name, foto):
        if Path(nome_no_cadastro(foto)).stem in atual.imagem.name:
            return f"{vista}: já está com a foto de estúdio."
        if simular:
            return f"{vista}: trocaria pela foto de estúdio de hoje."
        with transaction.atomic():
            _subir(foto, atual)
            if posicao == PERFIL and e_padrao:
                Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=atual.imagem.name)
        return f"{vista}: a foto de estúdio foi trocada pela de hoje."
    if atual is not None and not e_a_de_antes(atual.imagem.name, foto):
        return f"{vista}: a foto foi trocada no painel ({_base(atual.imagem.name)}); fica como está."
    if simular:
        return f"{vista}: poria a foto de estúdio" + (" (a de antes fica guardada no adesivo)." if atual else ".")
    with transaction.atomic():
        nova = ImagemBrinquedo(
            brinquedo=brinquedo, variante=variante, tipo=posicao,
            ordem=atual.ordem if atual is not None else max((f.ordem for f in fotos), default=0) + 1,
            papel_na_capa=CENA if posicao == PERFIL else "",
            texto_alternativo=(f"{brinquedo.nome_brinquedo}" + (f" ({variante.nome})" if variante and not e_padrao else "")
                               + f": {foto['rotulo']}")[:180],
        )
        if hasattr(nova, "fundo"):
            nova.fundo = "com"  # o fundo azul do estúdio: a conferência do fundo não precisa baixar
        if atual is not None:  # a de antes fica guardada no adesivo, sem a posição (fora da galeria)
            ImagemBrinquedo.objects.filter(pk=atual.pk).update(tipo=None, papel_na_capa="")
        _subir(foto, nova)
        if posicao == PERFIL and e_padrao:
            Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=nova.imagem.name)
    return f"{vista}: a foto de estúdio entrou" + (" (a de antes ficou guardada no adesivo)." if atual else ".")


def desfazer_foto(brinquedo, variante, e_padrao, foto, Brinquedos, ImagemBrinquedo, rotulo, simular=False):
    """Tira a foto de estúdio e volta a de antes para a posição. Devolve o que fez (uma frase)."""
    posicao = foto["posicao"]
    vista = f"{rotulo}, {foto['rotulo']}"
    fotos = _fotos_do_adesivo(brinquedo, variante, e_padrao, ImagemBrinquedo)
    de_estudio = [f for f in fotos if e_de_estudio(f.imagem.name, foto)]
    if not de_estudio:
        return f"{vista}: não está com a foto de estúdio."
    if simular:
        return f"{vista}: voltaria a foto de antes."
    with transaction.atomic():
        for f in de_estudio:
            f.delete()  # (o arquivo continua no Cloudinary: o Django não apaga o arquivo com a linha)
        if foto["nova"]:
            return f"{vista}: a foto de estúdio saiu (a posição era nova)."
        guardadas = [f for f in fotos if f not in de_estudio and not f.tipo and f.papel_na_capa not in FORA_DO_SITE
                     and e_a_de_antes(f.imagem.name, foto)]
        ocupada = ImagemBrinquedo.objects.filter(
            pk__in=[f.pk for f in fotos if f not in de_estudio], tipo=posicao).exists()
        # a que saiu da posição: a da versão mais nova (a -v2 tinha tirado a -v1) e, nela, a mais recente
        antes = max(guardadas, key=lambda f: (_versao(f.imagem.name), f.pk)) if guardadas else None
        if antes is None or ocupada:
            return f"{vista}: a foto de estúdio saiu."
        ImagemBrinquedo.objects.filter(pk=antes.pk).update(
            tipo=posicao, papel_na_capa=CENA if posicao == PERFIL else antes.papel_na_capa)
        if posicao == PERFIL and e_padrao:
            Brinquedos.objects.filter(pk=brinquedo.pk).update(imagem_brinquedo=antes.imagem.name)
    return f"{vista}: a foto de antes voltou."


def escolher(so=()):
    """Os itens pedidos (`so`: o produto, o adesivo ou "produto (adesivo)"; vazio, todos)."""
    if not so:
        return list(ITENS)
    pedidos = {_normalizar(str(s)) for s in so}
    return [item for item in ITENS
            if {_normalizar(item[0]), _normalizar(item[1] or ""), _normalizar(_rotulo(item[0], item[1]))} & pedidos]


def rodar(Brinquedos, ImagemBrinquedo, VarianteAdesivo, so=(), simular=False, desfazer=False, avisar=print):
    """Aplica (ou desfaz) cada foto; um erro numa foto não para as outras. Devolve {vista: frase}."""
    feito = {}
    funcao = desfazer_foto if desfazer else aplicar_foto
    for produto, adesivo, fotos in escolher(so):
        rotulo = _rotulo(produto, adesivo)
        brinquedo = _achar(produto, Brinquedos)
        if brinquedo is None:
            feito[rotulo] = f"{rotulo}: não está no catálogo."
            avisar(feito[rotulo])
            continue
        variante, e_padrao = _adesivo(brinquedo, adesivo, VarianteAdesivo)
        if adesivo is not None and variante is None:
            feito[rotulo] = f"{rotulo}: o {produto} não tem o adesivo {adesivo}."
            avisar(feito[rotulo])
            continue
        for foto in fotos:
            chave = f"{rotulo}: {foto['arquivo']}"
            try:
                frase = funcao(brinquedo, variante, e_padrao, foto, Brinquedos, ImagemBrinquedo, rotulo, simular=simular)
            except Exception as erro:  # a subida falhou: segue com as outras e avisa o comando
                frase = (f"{rotulo}, {foto['rotulo']}: não foi feito agora ({erro!r}). "
                         f"Rode: python manage.py fotos_de_estudio --so \"{produto}\"")
            feito[chave] = frase
            avisar(frase)
    if not simular:
        try:  # os cards, a página e a home guardados em cache passam a mostrar as fotos novas
            from django.core.cache import cache

            cache.clear()
        except Exception:  # noqa: BLE001
            pass
    return feito


def no_deploy(apps, schema_editor=None, avisar=print):
    """A migração 0197: só no Render (o Cloudinary só está lá); se algo falhar, o deploy segue."""
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return None
    try:
        return rodar(apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"),
                     apps.get_model("core", "VarianteAdesivo"), avisar=avisar)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"As fotos de estúdio não subiram agora ({erro!r}). Rode: python manage.py fotos_de_estudio")
        return None


def volta_do_deploy(apps, schema_editor=None, avisar=print):
    """A volta da 0197 (em todo lugar: só o banco; fora do Render não há nada a desfazer)."""
    return rodar(apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"),
                 apps.get_model("core", "VarianteAdesivo"), desfazer=True, avisar=avisar)
