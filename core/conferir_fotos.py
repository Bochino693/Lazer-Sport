"""A conferência das fotos de um adesivo (LEIA-ME 72): a quase igual e a sem fundo.

Duas regras do cliente para as fotos das posições de cada adesivo:

  * nada de duas fotos quase iguais no mesmo adesivo (a mesma sala, o mesmo
    ângulo): `parecidas` compara a "assinatura" das duas (um dHash de 16 x 16,
    256 bits, também contra a outra espelhada -- o lado esquerdo de uma
    máquina simétrica é o direito ao contrário). Usada no painel (a foto nova
    de uma posição), na ferramenta que sobe as posições tiradas do 3D
    (core.variantes.subir_posicoes) e no teste das vistas de cada adesivo;
  * nada de foto sem fundo no site: `sem_fundo` diz se a foto é um recorte
    (transparente, como as do remove.bg) ou de fundo branco (a de estúdio).
    Essas ficam guardadas como "recorte para artes" (só no painel).
"""

from PIL import Image

#: Quantos bits (de 256) separam, no máximo, duas fotos "quase iguais".
LIMITE = 32


def _abrir(origem):
    """A imagem (RGBA) de um caminho, de um arquivo enviado ou de um campo de imagem."""
    if hasattr(origem, "seek"):
        origem.seek(0)
    imagem = Image.open(origem)
    imagem.load()
    if hasattr(origem, "seek"):
        origem.seek(0)
    return imagem.convert("RGBA")


def _bits(cinza, lado):
    px = cinza.load()
    bits = 0
    for y in range(lado):
        for x in range(lado):
            bits = (bits << 1) | (px[x, y] > px[x + 1, y])
    return bits


def assinatura(origem, lado=16):
    """(a assinatura, a da foto espelhada): dois inteiros de lado x lado bits."""
    imagem = _abrir(origem)
    fundo = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
    fundo.alpha_composite(imagem)
    cinza = fundo.convert("L").resize((lado + 1, lado), Image.LANCZOS)
    espelho = fundo.convert("L").transpose(Image.FLIP_LEFT_RIGHT).resize((lado + 1, lado), Image.LANCZOS)
    return _bits(cinza, lado), _bits(espelho, lado)


def distancia(a, b):
    """Os bits diferentes entre duas assinaturas (a menor: direta ou espelhada)."""
    return min(bin(a[0] ^ b[0]).count("1"), bin(a[0] ^ b[1]).count("1"))


def parecidas(a, b, limite=LIMITE):
    """As duas assinaturas são de fotos quase iguais?"""
    return distancia(a, b) <= limite


def repetidas(assinaturas, limite=LIMITE):
    """Os pares (i, j) quase iguais de uma lista de assinaturas."""
    return [
        (i, j)
        for i in range(len(assinaturas))
        for j in range(i + 1, len(assinaturas))
        if parecidas(assinaturas[i], assinaturas[j], limite)
    ]


def sem_fundo(origem):
    """A foto é um recorte (transparente) ou de fundo branco? Olha a moldura (6% de cada lado)."""
    imagem = _abrir(origem)
    imagem.thumbnail((200, 200))
    largura, altura = imagem.size
    if largura < 8 or altura < 8:
        return False
    borda = max(1, round(min(largura, altura) * 0.06))
    px = imagem.load()
    moldura = [
        px[x, y]
        for y in range(altura)
        for x in range(largura)
        if x < borda or y < borda or x >= largura - borda or y >= altura - borda
    ]
    transparentes = sum(1 for p in moldura if p[3] < 200)
    if transparentes > 0.10 * len(moldura):
        return True
    brancos = sum(1 for p in moldura if p[3] >= 200 and min(p[:3]) >= 236)
    return brancos > 0.60 * len(moldura)
