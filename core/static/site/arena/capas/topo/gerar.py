"""AS ARTES DO DESTAQUE da biblioteca (/jogos/): uma cena de verdade de cada jogo da casa.

O carrossel do alto do portal abre com o jogo numa arte larga, de ponta a
ponta. Antes, a arte era o pôster esticado e desfocado -- um borrão marrom.
Agora é o próprio jogo: a cena fotografada jogando no navegador (o Bob e a
Mia pulando no parque, o boxeador no ringue, o estádio com os anéis
acesos), escurecida do lado do texto para o nome e o botão lerem bem. A
logo do jogo continua por cima, à direita (o template, não a arte).

São duas artes por jogo, porque o destaque muda de forma:
  * <slug>.webp            1600 x 680: computador, o texto à esquerda;
  * <slug>-estreito.webp    900 x 900: tablet em pé e celular, o texto embaixo.

COMO REFAZER (três passos; o terceiro é o único que precisa rodar de novo
quando só o acabamento muda):

  1. com o site no ar, jogar e fotografar (Playwright):
         node ferramentas/artes_do_topo/filmar.js http://127.0.0.1:8000 /tmp/quadros
  2. escolher os momentos (a tabela CENAS, abaixo: o quadro e o recorte) e guardar
     as cenas cruas no repositório (ferramentas/artes_do_topo/cenas/):
         python core/static/site/arena/capas/topo/gerar.py --escolher /tmp/quadros [outra pasta...]
  3. montar as artes desta pasta a partir das cenas:
         python core/static/site/arena/capas/topo/gerar.py

Precisa do Pillow. Nenhuma imagem de fora: só o que os jogos desenham.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[5]
PASTA_DAS_CENAS = RAIZ / "ferramentas" / "artes_do_topo" / "cenas"
LARGO = (1600, 680)
ESTREITO = (900, 900)
ESCURO = (4, 7, 15)

#: O momento de cada jogo: o quadro do filmar.js e o recorte (x0, y0, x1, y1), em frações do quadro.
#: "lugar": onde o meio do recorte cai na arte larga (0 = na esquerda, 1 = encostado na direita). O
#: texto ocupa a esquerda e a logo do jogo, a direita: o que importa da cena fica entre os dois.
#: "inclinar": o campo visto de cima ganha a perspectiva de uma câmera de TV (0 = reto).
#: "lateral": quando a cena (de um jogo em pé) não enche a faixa, o que vai dos lados: "espelho" (a
#: própria cena espelhada na emenda -- pista, quadra, estádio) ou "cor" (a cor da borda da cena,
#: para cena com número ou letra perto da borda, que espelhada ficaria de trás para a frente).
#: Nenhuma cena pega o vídeo da música do Hit Music (o painel de cima): só o que o jogo desenha.
CENAS = {
    "strike-kids": {
        # o Bob e a Mia pulando de alegria na frente da pista, no parque dos dinossauros (3D, tela deitada)
        "largo": {"quadro": "strike-kids-amigos-02.png", "recorte": (0, 0, 1, 1), "lugar": 0.58},
        "estreito": {"quadro": "strike-kids-amigos-02.png", "recorte": (0.22, 0, 0.78, 1)},
    },
    "dragon-bowling": {
        # o dragão da pista, com as bolas de fogo e o rastro de estrelas
        "largo": {"quadro": "dragon-bowling-pista.png", "recorte": (0, 0.37, 1, 0.66), "lugar": 1, "lateral": "cor"},
        "estreito": {"quadro": "dragon-bowling-pista.png", "recorte": (0, 0.08, 1, 0.64)},
    },
    "lazer-shot": {
        # Atlântida no fundo do mar: as águas-vivas, os baús e as bombas do alvo
        "largo": {"quadro": "lazer-shot-tiro12.png", "recorte": (0, 0.22, 1, 0.52), "lugar": 1, "lateral": "cor"},
        "estreito": {"quadro": "lazer-shot-tiro12.png", "recorte": (0, 0.2, 1, 0.76)},
    },
    "super-boxing": {
        # o adversário no ringue, com a torcida e o neon da arena (3D, tela deitada)
        "largo": {"quadro": "super-boxing-ringue-00.png", "recorte": (0.14, 0.2, 0.98, 0.84), "lugar": 0.56},
        "estreito": {"quadro": "super-boxing-ringue-00.png", "recorte": (0.26, 0.17, 0.74, 1)},
    },
    "slam-arena": {
        # a cesta caindo, o SWISH! e a explosão de luz da arena acesa
        "largo": {"quadro": "slam-arena-arremesso4-05.png", "recorte": (0, 0.32, 1, 0.63), "lugar": 1, "lateral": "cor"},
        "estreito": {"quadro": "slam-arena-arremesso4-05.png", "recorte": (0, 0.2, 1, 0.76)},
    },
    "swish-arena": {
        # a cesta caindo, com as faíscas e o placar de LED
        "largo": {"quadro": "swish-arena-arremesso1-04.png", "recorte": (0, 0.12, 1, 0.88), "lugar": 0.56},
        "estreito": {"quadro": "swish-arena-arremesso1-04.png", "recorte": (0.25, 0.2, 0.75, 1)},
    },
    "gol-flash-arena": {
        # o estádio iluminado e os anéis de luz acesos no gol
        "largo": {"quadro": "gol-flash-arena-t2.png", "recorte": (0, 0.09, 1, 0.82), "lugar": 0.56},
        "estreito": {"quadro": "gol-flash-arena-t2.png", "recorte": (0.18, 0.06, 0.82, 1)},
    },
    "craque-de-botao": {
        # o chute mirado no gol, com o estádio em volta; o campo ganha a perspectiva da TV
        "largo": {"quadro": "craque-de-botao-chute2-04.png", "recorte": (0, 0.1, 1, 0.92), "lugar": 0.56, "inclinar": 0.2,
                  "lateral": "cor"},
        "estreito": {"quadro": "craque-de-botao-chute2-04.png", "recorte": (0.4, 0.1, 1, 1), "inclinar": 0.16},
    },
    "hit-music": {
        # a roda da música acesa no meio da partida (só a roda: o vídeo da música fica de fora)
        "largo": {"quadro": "hit-music-musica04.png", "recorte": (0, 0.4, 1, 0.99), "lugar": 0.56, "lateral": "cor"},
        "estreito": {"quadro": "hit-music-musica04.png", "recorte": (0, 0.42, 1, 0.985)},
    },
}


def _resolver(n, linhas):
    """Eliminação de Gauss (o sistema 8 x 8 da perspectiva; sem numpy)."""
    m = [linha[:] + [v] for linha, v in zip(linhas, n)]
    for i in range(8):
        pivo = max(range(i, 8), key=lambda k: abs(m[k][i]))
        m[i], m[pivo] = m[pivo], m[i]
        for k in range(8):
            if k != i:
                f = m[k][i] / m[i][i]
                m[k] = [a - f * b for a, b in zip(m[k], m[i])]
    return [m[i][8] / m[i][i] for i in range(8)]


def _inclinar(imagem, forca):
    """O retângulo visto de cima vira um trapézio (o fundo mais estreito): a câmera de TV no estádio."""
    if not forca:
        return imagem
    w, h = imagem.size
    recuo = w * forca / 2
    # para cada ponto da saída, de onde ele vem na imagem (o PERSPECTIVE do Pillow é assim, de trás para a frente)
    destino = [(recuo, 0), (w - recuo, 0), (w, h), (0, h)]
    origem = [(0, 0), (w, 0), (w, h), (0, h)]
    linhas, n = [], []
    for (x, y), (u, v) in zip(destino, origem):
        linhas.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); n.append(u)
        linhas.append([0, 0, 0, x, y, 1, -v * x, -v * y]); n.append(v)
    inclinada = imagem.transform((w, h), Image.PERSPECTIVE, _resolver(n, linhas), Image.BICUBIC, fillcolor=ESCURO)
    # os cantos de cima que sobram (fora do trapézio) somem no escuro
    return inclinada.crop((round(recuo * 0.55), 0, w - round(recuo * 0.55), h))


def _degrade(tamanho, pontos, vertical=False):
    """Máscara de escuro: `pontos` são (posição de 0 a 1, opacidade de 0 a 1), em ordem."""
    largura, altura = tamanho
    n = altura if vertical else largura
    linha = Image.new("L", (1, n) if vertical else (n, 1))
    for i in range(n):
        f = i / max(1, n - 1)
        valor = pontos[-1][1]
        for (p0, a0), (p1, a1) in zip(pontos, pontos[1:]):
            if p0 <= f <= p1:
                t = (f - p0) / max(1e-6, p1 - p0)
                t = t * t * (3 - 2 * t)  # suave nas pontas (sem degrau)
                valor = a0 + (a1 - a0) * t
                break
        linha.putpixel((0, i) if vertical else (i, 0), round(255 * valor))
    return linha.resize(tamanho)


def _escurecer(tela, mascara):
    return Image.composite(Image.new("RGB", tela.size, ESCURO), tela, mascara)


def _vinheta(tamanho, forca=0.45):
    """Os cantos um pouco mais escuros (o olho vai para o meio)."""
    pequeno = Image.radial_gradient("L").resize((256, 256))
    pequeno = pequeno.point(lambda v: round(255 * forca * max(0.0, (v / 255 - 0.55) / 0.45) ** 1.6))
    return pequeno.resize(tamanho, Image.BICUBIC)


def _acabamento(tela):
    """Um pouco mais de cor e de contraste, e a nitidez de volta depois do redimensionamento."""
    tela = ImageEnhance.Color(tela).enhance(1.08)
    tela = ImageEnhance.Contrast(tela).enhance(1.05)
    return tela.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))


def _cor_da_borda(cena, lado):
    """A cor média de uma beirada da cena (para encher o lado sem espelhar)."""
    faixa = cena.crop((0, 0, 6, cena.height) if lado == "esquerda" else (cena.width - 6, 0, cena.width, cena.height))
    return faixa.resize((1, 1), Image.BOX).getpixel((0, 0))


def _faixa_larga(cena, lugar, lateral="espelho"):
    """A cena na faixa larga: altura inteira; se faltar largura, o espelho da borda (ou a cor dela) completa."""
    largura, altura = LARGO
    escala = altura / cena.height
    cena = cena.resize((max(1, round(cena.width * escala)), altura), Image.LANCZOS)
    meio = round(lugar * largura)
    if cena.width >= largura:
        x = min(max(0, cena.width // 2 - meio), cena.width - largura)
        return cena.crop((x, 0, x + largura, altura))
    tela = Image.new("RGB", LARGO, ESCURO)
    x = min(max(0, meio - cena.width // 2), largura - cena.width)
    tela.paste(cena, (x, 0))
    fim = x + cena.width
    if lateral == "cor":
        # a cor da borda, com a emenda suave (a cena some nela)
        if x > 0:
            tela.paste(_cor_da_borda(cena, "esquerda"), (0, 0, x + 1, altura))
        if fim < largura:
            tela.paste(_cor_da_borda(cena, "direita"), (fim - 1, 0, largura, altura))
        borda = max(24, cena.width // 6)
        mascara = _degrade((cena.width, altura), ((0, 0.0), (borda / cena.width, 1.0), (1 - borda / cena.width, 1.0), (1, 0.0)))
        tela.paste(cena, (x, 0), mascara)
        return tela
    # as sobras: a cena espelhada na emenda, sumindo (o lado do texto fica escuro de todo jeito)
    if x > 0:
        espelho = ImageOps.mirror(cena.crop((0, 0, min(x, cena.width), altura)))
        tela.paste(espelho, (x - espelho.width, 0))
        costura = _degrade((x, altura), ((0, 1), (0.75, 0.35), (1, 0)))
        tela.paste(Image.composite(Image.new("RGB", (x, altura), ESCURO), tela.crop((0, 0, x, altura)), costura), (0, 0))
    if fim < largura:
        sobra = largura - fim
        espelho = ImageOps.mirror(cena.crop((cena.width - min(sobra, cena.width), 0, cena.width, altura)))
        tela.paste(espelho, (fim, 0))
    return tela


def montar_largo(cena, lugar=0.5, lateral="espelho"):
    tela = _acabamento(_faixa_larga(cena.convert("RGB"), lugar, lateral))
    # o escuro do texto (à esquerda) e do chão (os pontinhos do carrossel), e a vinheta
    tela = _escurecer(tela, _degrade(LARGO, ((0, 0.94), (0.3, 0.74), (0.6, 0.0), (1, 0.0))))
    tela = _escurecer(tela, _degrade(LARGO, ((0, 0.18), (0.18, 0.0), (0.62, 0.0), (1, 0.55)), vertical=True))
    tela = _escurecer(tela, _vinheta(LARGO, 0.4))
    return tela


def montar_estreito(cena):
    tela = cena.convert("RGB")
    lado = min(tela.size)
    x, y = (tela.width - lado) // 2, (tela.height - lado) // 2
    tela = _acabamento(tela.crop((x, y, x + lado, y + lado)).resize(ESTREITO, Image.LANCZOS))
    # o texto fica embaixo: o escuro sobe de baixo; em cima, só um véu para a logo
    tela = _escurecer(tela, _degrade(ESTREITO, ((0, 0.2), (0.16, 0.0), (0.26, 0.0), (0.5, 0.74), (0.72, 0.9), (1, 0.96)), vertical=True))
    tela = _escurecer(tela, _vinheta(ESTREITO, 0.4))
    return tela


def _achar(pastas, nome):
    for pasta in pastas:
        if (pasta / nome).exists():
            return pasta / nome
    raise FileNotFoundError(f"{nome} não está em {', '.join(map(str, pastas))}")


def escolher(pastas: list[Path]):
    """Recorta os momentos da tabela CENAS e guarda as cenas cruas (webp quase sem perda)."""
    PASTA_DAS_CENAS.mkdir(parents=True, exist_ok=True)
    for slug, artes in CENAS.items():
        for forma, escolha in artes.items():
            quadro = Image.open(_achar(pastas, escolha["quadro"])).convert("RGB")
            x0, y0, x1, y1 = escolha["recorte"]
            cena = _inclinar(quadro.crop((round(x0 * quadro.width), round(y0 * quadro.height),
                                          round(x1 * quadro.width), round(y1 * quadro.height))), escolha.get("inclinar", 0))
            # a cena crua guarda o bastante para a arte (um quarto a mais que ela), não o quadro inteiro
            limite = (LARGO if forma == "largo" else ESTREITO)[1] * 1.25
            if cena.height > limite:
                cena = cena.resize((round(cena.width * limite / cena.height), round(limite)), Image.LANCZOS)
            destino = PASTA_DAS_CENAS / f"{slug}-{forma}.webp"
            cena.save(destino, "WEBP", quality=88, method=6)
            print(f"{destino.relative_to(RAIZ)}  {cena.width}x{cena.height}  {destino.stat().st_size // 1024} KB")


def montar_todas():
    for slug, artes in CENAS.items():
        largo = PASTA_DAS_CENAS / f"{slug}-largo.webp"
        estreito = PASTA_DAS_CENAS / f"{slug}-estreito.webp"
        if largo.exists():
            destino = AQUI / f"{slug}.webp"
            escolha = artes["largo"]
            arte = montar_largo(Image.open(largo), escolha.get("lugar", 0.5), escolha.get("lateral", "espelho"))
            arte.save(destino, "WEBP", quality=80, method=6)
            print(f"{destino.relative_to(RAIZ)}  {destino.stat().st_size // 1024} KB")
        if estreito.exists():
            destino = AQUI / f"{slug}-estreito.webp"
            montar_estreito(Image.open(estreito)).save(destino, "WEBP", quality=80, method=6)
            print(f"{destino.relative_to(RAIZ)}  {destino.stat().st_size // 1024} KB")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--escolher":
        escolher([Path(p) for p in sys.argv[2:]])
    else:
        montar_todas()
