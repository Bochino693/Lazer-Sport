"""A ASSINATURA DO REPRESENTANTE DA EMPRESA nos documentos assinados (LEIA-ME-V10, seção 152).

O dono: "tenho essa assinatura (...) do responsável pela Lazer & Sport e é
ele quem aparece nos doc; você deve, sempre que o cliente assinar, embutir
esta assinatura no lado nosso da Lazer & Sport, com o nome dele e da
fábrica, inclusive ponha em todos os docs já gerados."

COMO FUNCIONA
  * A Gestão envia a FOTO da assinatura (caneta em papel claro) na tela
    "Dados do contrato". O servidor tira o papel -- fica só o traço, em PNG
    transparente --, recorta a margem e limita o tamanho (`tratar`). A tela
    mostra o resultado antes de salvar.
  * A imagem tratada mora no banco (`AssinaturaRepresentante.png`, um
    `BinaryField`, como o traço do cliente). NUNCA vai para o repositório,
    para o armazenamento público nem tem endereço próprio: ela só sai
    DENTRO de um documento (um `data:` na página), para quem pode abrir
    aquele documento.
  * Ela é DESENHADA NA HORA DE MOSTRAR, no lado da empresa, em todo
    documento que o cliente já assinou -- inclusive os antigos. O retrato
    (`conteudo`), o `hash_conteudo` e o `hash_assinado` não mudam: nada é
    regravado no documento. Por isso a folha diz, com todas as letras,
    "Assinatura do representante aplicada pela Lazer & Sport", sem data de
    assinatura inventada.
  * Documento que ainda espera o cliente mostra o lado da empresa em branco,
    como sempre: a assinatura da empresa entra quando o cliente assina.
  * Sem assinatura cadastrada, os documentos saem como antes.

A FOTO É DADO NÃO CONFIÁVEL: o tipo é conferido abrindo o arquivo (JPEG,
PNG ou WebP de verdade; SVG, PDF, GIF e o resto são recusados), o tamanho e
as dimensões têm teto, e o que é guardado é sempre o PNG que o servidor
gerou -- nunca os bytes que chegaram.
"""

from __future__ import annotations

import base64
import hashlib
import io

from .utils import ErroDeFormulario

#: O arquivo enviado: até 8 MB (uma foto de celular) e 40 megapixels.
TETO_DO_ENVIO = 8 * 1024 * 1024
TETO_DE_PIXELS = 40_000_000
#: Menor que isso não dá para ler um traço.
MINIMO = (120, 60)
FORMATOS = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WebP", "MPO": "JPEG"}
#: A foto é reduzida a esta largura antes do tratamento (mais que isso só gasta tempo).
LARGURA_DE_TRABALHO = 1600
#: O PNG guardado: cabe na linha de assinatura com folga para a impressão.
SAIDA_MAXIMA = (900, 380)
TETO_DO_PNG = 400 * 1024

#: Quanto o ponto precisa ser mais escuro que o papel em volta (0-255) para
#: começar a ser traço, e a partir de quanto é traço cheio.
INICIO_DO_TRACO = 30
TRACO_CHEIO = 78

CHAVE_DO_CACHE = "assinatura-representante:data-url:v1"
VIDA_DO_CACHE = 300

#: A frase honesta que vai na folha (o documento não foi regravado).
NOTA = "Assinatura do representante aplicada pela Lazer & Sport"


def _erro(mensagem):
    return ErroDeFormulario(mensagem, titulo="Não deu para usar esta imagem", campo="assinatura_arquivo")


def _abrir(dados: bytes):
    """Abre o arquivo conferindo o tipo de verdade, o tamanho e as dimensões."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not dados:
        raise _erro("Escolha a foto da assinatura (JPEG, PNG ou WebP).")
    if len(dados) > TETO_DO_ENVIO:
        raise _erro("A foto é grande demais (o limite é 8 MB). Tire outra ou reduza o tamanho.")
    try:
        # confere a estrutura do arquivo sem decodificar os pontos
        with Image.open(io.BytesIO(dados)) as conferencia:
            formato = (conferencia.format or "").upper()
            largura, altura = conferencia.size
            if formato not in FORMATOS:
                raise _erro("Envie a assinatura em JPEG, PNG ou WebP. Outros tipos de arquivo não são aceitos.")
            if getattr(conferencia, "is_animated", False):
                raise _erro("Envie uma foto parada da assinatura, e não uma animação.")
            if largura * altura > TETO_DE_PIXELS or max(largura, altura) > 12000:
                raise _erro("A foto tem pontos demais. Tire outra com a câmera normal do celular.")
            if largura < MINIMO[0] or altura < MINIMO[1]:
                raise _erro("A foto é pequena demais para ler o traço. Tire outra mais de perto.")
            conferencia.verify()
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
        imagem = ImageOps.exif_transpose(imagem)
    except ErroDeFormulario:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise _erro("Não consegui abrir este arquivo como imagem. Envie a foto em JPEG, PNG ou WebP.")
    # a transparência (um PNG já recortado) vira papel branco: o tratamento é o mesmo
    if imagem.mode in ("RGBA", "LA", "P"):
        imagem = imagem.convert("RGBA")
        papel = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
        papel.alpha_composite(imagem)
        imagem = papel
    return imagem.convert("RGB")


def tratar(dados: bytes) -> tuple[bytes, int, int]:
    """A foto da assinatura -> (PNG transparente só com o traço, largura, altura).

    O papel não é branco na foto: tem sombra, vinco e cor. Por isso o traço
    é o que fica MAIS ESCURO QUE O PAPEL EM VOLTA (e não "o que não é
    branco"): o papel de cada região é estimado apagando o traço (o ponto
    mais claro da vizinhança, borrado) e a diferença entre o papel e a foto
    vira a opacidade. A cor do traço é uma só -- a média do traço cheio --,
    para sair limpa no papel do contrato e na impressão.
    """
    from PIL import Image, ImageChops, ImageFilter, ImageStat

    foto = _abrir(dados)
    if foto.width > LARGURA_DE_TRABALHO:
        foto = foto.resize(
            (LARGURA_DE_TRABALHO, max(round(foto.height * LARGURA_DE_TRABALHO / foto.width), 1)), Image.LANCZOS,
        )
    largura, altura = foto.size

    # o papel de cada região: numa cópia pequena, o ponto mais claro da
    # vizinhança apaga o traço; borrado e ampliado, é o papel com a sombra
    pequena = foto.resize((max(largura // 8, 16), max(altura // 8, 16)), Image.BILINEAR)
    papel = pequena.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6))
    papel = papel.resize((largura, altura), Image.BILINEAR)
    # papel escuro (ou foto de outra coisa): a conta abaixo só vale para caneta em papel claro
    if ImageStat.Stat(papel.convert("L")).mean[0] < 120:
        raise _erro(
            "A foto está escura demais. Assine num papel branco, num lugar claro, e fotografe de novo."
        )

    # quanto cada ponto é mais escuro que o papel, no canal em que mais é
    # (a caneta azul some no azul e aparece no vermelho)
    diferenca = ImageChops.subtract(papel, foto)
    r, g, b = diferenca.split()
    escuro = ImageChops.lighter(ImageChops.lighter(r, g), b)
    faixa = max(TRACO_CHEIO - INICIO_DO_TRACO, 1)
    opacidade = escuro.point([
        0 if v <= INICIO_DO_TRACO else min(round((v - INICIO_DO_TRACO) * 255 / faixa), 255) for v in range(256)
    ])
    # o grão do papel e do JPEG (pontos soltos) sai; o traço fica
    opacidade = opacidade.filter(ImageFilter.MedianFilter(3))

    cheio = opacidade.point([255 if v >= 200 else 0 for v in range(256)])
    pontos_cheios = ImageStat.Stat(cheio).sum[0] / 255
    total = largura * altura
    if pontos_cheios < max(total * 0.0004, 60):
        raise _erro(
            "Não achei o traço da assinatura nesta foto. Assine com caneta escura num papel branco, "
            "sem sombra forte, e fotografe de perto."
        )
    if pontos_cheios > total * 0.30:
        raise _erro(
            "A foto não parece uma assinatura em papel claro (há escuro demais). "
            "Fotografe só a assinatura, num papel branco."
        )
    caixa = opacidade.point([255 if v >= 48 else 0 for v in range(256)]).getbbox()
    if caixa is None:
        raise _erro("Não achei o traço da assinatura nesta foto.")

    # a cor do traço: a média de onde ele é cheio (escurecida um pouco, para a impressão)
    media = ImageStat.Stat(foto, cheio).mean
    cor = tuple(max(min(round(c * 0.92), 255), 0) for c in media[:3])

    margem = max(round(min(largura, altura) * 0.015), 4)
    caixa = (max(caixa[0] - margem, 0), max(caixa[1] - margem, 0),
             min(caixa[2] + margem, largura), min(caixa[3] + margem, altura))
    opacidade = opacidade.crop(caixa)
    if opacidade.width < 40 or opacidade.height < 16:
        raise _erro("O traço achado é pequeno demais. Fotografe a assinatura mais de perto.")

    escala = min(SAIDA_MAXIMA[0] / opacidade.width, SAIDA_MAXIMA[1] / opacidade.height, 1)
    saida = None
    while True:
        tamanho = (max(round(opacidade.width * escala), 1), max(round(opacidade.height * escala), 1))
        alfa = opacidade.resize(tamanho, Image.LANCZOS) if escala < 1 else opacidade
        traco = Image.new("RGBA", tamanho, cor + (0,))
        traco.putalpha(alfa)
        memoria = io.BytesIO()
        traco.save(memoria, format="PNG", optimize=True)
        saida = memoria.getvalue()
        if len(saida) <= TETO_DO_PNG or escala < 0.2:
            break
        escala *= 0.8
    if len(saida) > TETO_DO_PNG:
        raise _erro("A assinatura tratada ficou grande demais. Fotografe só a assinatura, de mais longe.")
    return saida, traco.width, traco.height


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(bytes(png)).decode("ascii") if png else ""


def esquecer() -> None:
    from django.core.cache import cache

    try:
        cache.delete(CHAVE_DO_CACHE)
    except Exception:  # noqa: BLE001 -- sem cache, nada a esquecer
        pass


def atual():
    """A assinatura cadastrada (a linha, sem os bytes) ou None."""
    from .models import AssinaturaRepresentante

    return AssinaturaRepresentante.objects.defer("png").order_by("id").first()


def imagem_atual() -> str:
    """O `data:` da assinatura cadastrada; "" sem ela. Cinco minutos no cache do servidor."""
    from django.core.cache import cache

    from .models import AssinaturaRepresentante

    try:
        guardado = cache.get(CHAVE_DO_CACHE)
    except Exception:  # noqa: BLE001
        guardado = None
    if guardado is not None:
        return guardado
    png = AssinaturaRepresentante.objects.order_by("id").values_list("png", flat=True).first()
    valor = data_url(png) if png else ""
    try:
        cache.set(CHAVE_DO_CACHE, valor, VIDA_DO_CACHE)
    except Exception:  # noqa: BLE001
        pass
    return valor


def para_o_documento(documento) -> str:
    """A imagem que entra no lado da empresa DESTE documento; "" quando não entra.

    Só no documento que o cliente já assinou. Nada é gravado nele.
    """
    if documento is None or not getattr(documento, "assinado", False):
        return ""
    return imagem_atual()


def salvar(dados: bytes, usuario=None):
    """Trata a foto e guarda o PNG (troca a que havia). Devolve a linha."""
    from django.db import transaction

    from .models import AssinaturaRepresentante

    png, largura, altura = tratar(dados)
    with transaction.atomic():
        AssinaturaRepresentante.objects.all().delete()
        linha = AssinaturaRepresentante.objects.create(
            png=png, largura=largura, altura=altura, sha256=hashlib.sha256(png).hexdigest(),
            enviada_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
    esquecer()
    return linha


def remover() -> bool:
    from .models import AssinaturaRepresentante

    apagadas, _ = AssinaturaRepresentante.objects.all().delete()
    esquecer()
    return bool(apagadas)
