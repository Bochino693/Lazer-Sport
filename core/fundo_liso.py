"""A foto de produto num AMBIENTE, nunca num fundo liso (LEIA-ME V10, seção 118).

O dono, com o print do catálogo (o card do Air Game Kids e os dos basquetes com o fundo azul
liso do estúdio da seção 96): "esses brinquedos com o fundo azul devem ser de ambiente como
falei, nada de fundos singulares." Toda foto de produto mostra a máquina num lugar -- o
showroom da Lazer & Sport (seção 64) --, nunca num fundo de cor única, num degradê ou no
"fundo infinito" de estúdio.

A RÉGUA (só o Pillow: roda no servidor e nos testes): a foto é reduzida a 320 px no lado maior
e olha-se a MOLDURA (16 px de cada lado, em blocos de 8 x 8):
  * a TEXTURA: o desvio da luz dentro de cada bloco; vale o 3º quartil (75% dos blocos). O
    lugar de verdade tem o rejunte do piso, as folhas, os adesivos, as quinas da parede, as
    luzes; o fundo de estúdio é um degradê macio, sem nada dentro dos blocos;
  * a COR QUASE ÚNICA: a fração da moldura numa família de cor só (o matiz e os dois vizinhos,
    de 30 em 30 graus; ou, no cinza/preto/branco, a faixa de luz e a vizinha).
FUNDO LISO = as duas coisas juntas: a cor quase única E pouca textura. Uma só não basta: o
galpão claro do Espaço Esportivo é quase todo de um tom, mas tem as treliças e o piso; a vitrine
preta do Top Racer é lisa, mas tem o piso claro embaixo.

Calibrada (outubro de 2026) contra as fotos do repositório:
  * as de estúdio da seção 96 (o azul marinho com o brilho royal): cor 0,78 a 1,00 e textura
    0,7 a 2,4 -- todas reprovadas;
  * as do showroom (as 46 capas do catálogo, as capas e as vistas dos nossos 3D, a da Black
    Friday): cor até 0,70, ou textura de 3,9 para cima (o galpão do Espaço Esportivo: cor 0,79 e
    0,82, textura 3,9 e 4,2) -- todas aprovadas.

Usada pelo teste que segura as fotos do repositório (core/tests_fundo_liso.py) e pelo AVISO do
painel (não bloqueia): a capa do produto ou a frente de um adesivo enviada com o fundo liso
grava e ganha `aviso_de_fundo`.
"""

from __future__ import annotations

from PIL import Image

#: O lado maior da foto na medida (a textura é a do card, não a do grão do sensor).
LADO = 320
#: O bloco e a moldura (em blocos): 16 px de cada lado numa foto de 320.
BLOCO = 8
MOLDURA = 2
#: A cor quase única: a família de cor da moldura passa desta fração...
COR_QUASE_UNICA = 0.75
#: ... e a textura (o 3º quartil do desvio da luz nos blocos da moldura) fica nisto ou abaixo.
POUCA_TEXTURA = 3.0
#: O que conta como cor (e não cinza): o croma (máximo - mínimo do RGB, de 0 a 1) e a saturação.
CROMA_MINIMO = 0.06
SATURACAO_MINIMA = 0.2

AVISO = "A foto do card deve mostrar o brinquedo num ambiente (o showroom), não num fundo liso."


def _reduzir(imagem):
    imagem = imagem.convert("RGB")
    largura, altura = imagem.size
    if largura >= altura:
        tamanho = (LADO, max(1, round(LADO * altura / largura)))
    else:
        tamanho = (max(1, round(LADO * largura / altura)), LADO)
    return imagem.resize(tamanho, Image.BOX)


def _blocos_da_moldura(largura, altura):
    faixa = BLOCO * MOLDURA
    return [
        (x, y)
        for y in range(0, altura - BLOCO + 1, BLOCO)
        for x in range(0, largura - BLOCO + 1, BLOCO)
        if y < faixa or x < faixa or y + BLOCO > altura - faixa or x + BLOCO > largura - faixa
    ]


def _quartil(valores, fracao=0.75):
    """O percentil (interpolado, como o numpy) de uma lista."""
    ordem = sorted(valores)
    if not ordem:
        return 0.0
    posicao = fracao * (len(ordem) - 1)
    baixo = int(posicao)
    alto = min(baixo + 1, len(ordem) - 1)
    return ordem[baixo] + (ordem[alto] - ordem[baixo]) * (posicao - baixo)


def medir(origem):
    """(cor, textura) da moldura da foto: a fração na família de cor mais comum (0 a 1) e o 3º quartil
    do desvio da luz nos blocos de 8 px (0 a ~128). `origem`: um caminho, um arquivo ou uma imagem PIL."""
    if isinstance(origem, Image.Image):
        imagem = origem
        imagem.load()
    else:
        posicao = origem.tell() if hasattr(origem, "tell") else None
        if posicao is not None:
            origem.seek(0)
        try:
            with Image.open(origem) as aberta:
                aberta.load()
                imagem = aberta.convert("RGBA") if "A" in aberta.getbands() else aberta.convert("RGB")
        finally:
            if posicao is not None:
                origem.seek(posicao)
    if "A" in imagem.getbands():  # (o transparente conta como branco, como o recorte sem fundo)
        fundo = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
        fundo.alpha_composite(imagem.convert("RGBA"))
        imagem = fundo
    imagem = _reduzir(imagem)
    largura, altura = imagem.size
    blocos = _blocos_da_moldura(largura, altura)
    if not blocos:
        return 0.0, 0.0
    rgb = imagem.tobytes()
    luz = imagem.convert("L").tobytes()
    familias = [0] * 16
    desvios = []
    total = 0
    for x0, y0 in blocos:
        soma = soma2 = 0
        for y in range(y0, y0 + BLOCO):
            linha = y * largura
            for x in range(x0, x0 + BLOCO):
                i = linha + x
                l = luz[i]
                soma += l
                soma2 += l * l
                r, g, b = rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2]
                maximo, minimo = max(r, g, b), min(r, g, b)
                croma = maximo - minimo
                if croma >= CROMA_MINIMO * 255 and croma >= SATURACAO_MINIMA * maximo:
                    if maximo == r:
                        matiz = ((g - b) / croma) % 6
                    elif maximo == g:
                        matiz = (b - r) / croma + 2
                    else:
                        matiz = (r - g) / croma + 4
                    familias[int(matiz * 60 // 30) % 12] += 1
                else:
                    familias[12 + min(3, l * 4 // 256)] += 1
                total += 1
        n = BLOCO * BLOCO
        media = soma / n
        desvios.append(max(0.0, soma2 / n - media * media) ** 0.5)
    cor = max(
        max(familias[k] + familias[(k + 1) % 12] + familias[(k - 1) % 12] for k in range(12)),
        max(familias[k] + (familias[k + 1] if k < 15 else 0) for k in range(12, 16)),
    ) / total
    return cor, _quartil(desvios)


def e_fundo_liso(origem):
    """A foto está num fundo liso (a cor quase única E pouca textura na moldura)?"""
    cor, textura = medir(origem)
    return cor >= COR_QUASE_UNICA and textura <= POUCA_TEXTURA


def aviso_de_fundo(arquivo):
    """O aviso do painel (não bloqueia) para a capa / a frente com o fundo liso: "" quando está tudo bem.

    A foto sem fundo (branca ou transparente) não ganha este aviso: ela já vira o recorte para as artes
    (core.conferir_fotos.sem_fundo) e o painel diz isso. O arquivo volta para o começo (o painel o grava).
    """
    from . import conferir_fotos

    posicao = arquivo.tell() if hasattr(arquivo, "tell") else None
    try:
        if conferir_fotos.sem_fundo(arquivo):
            return ""
        return AVISO if e_fundo_liso(arquivo) else ""
    except Exception:  # noqa: BLE001 -- não é uma imagem que o Pillow abre: o campo de imagem confere
        return ""
    finally:
        if posicao is not None:
            arquivo.seek(posicao)
