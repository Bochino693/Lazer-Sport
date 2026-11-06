"""AS ARTES DO TOPO da biblioteca (/jogos/): uma faixa larga por jogo da casa.

A biblioteca abre como uma loja de jogos: no alto, o jogo em destaque numa arte
larga, de ponta a ponta. Os jogos da casa só tinham a capa quadrada e o pôster
(alguns em pé): este script monta a faixa de cada um com o que já existe --
o pôster (ou a capa) esticado e desfocado de fundo, a luz na cor do jogo, a arte
do jogo à direita e o escuro à esquerda, onde vai o nome e o botão Jogar.

Rodar de novo depois de trocar uma capa ou um pôster (ou de pôr um jogo novo
em core/arena.JOGOS):

    python core/static/site/arena/capas/topo/gerar.py

Saída: <slug>.webp (1600 x 600) nesta pasta. Precisa do Pillow.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

AQUI = Path(__file__).resolve().parent
ESTATICO = AQUI.parents[3]  # core/static
RAIZ = ESTATICO.parents[1]
LARGURA, ALTURA = 1600, 600


def _cor(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _cobrir(imagem, largura, altura):
    """Redimensiona cobrindo a área toda (o que sobra sai das bordas)."""
    escala = max(largura / imagem.width, altura / imagem.height)
    nova = imagem.resize((max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala))), Image.LANCZOS)
    x, y = (nova.width - largura) // 2, (nova.height - altura) // 2
    return nova.crop((x, y, x + largura, y + altura))


def _degrade_horizontal(largura, altura, cor, inicio, fim, opaco_ate=0.0):
    """Máscara: opaco à esquerda (até `opaco_ate`), sumindo até `fim` (frações da largura)."""
    mascara = Image.new("L", (largura, 1))
    for x in range(largura):
        f = x / largura
        if f <= opaco_ate:
            a = inicio
        elif f >= fim:
            a = 0
        else:
            t = (f - opaco_ate) / (fim - opaco_ate)
            a = round(inicio * (1 - t) ** 1.6)
        mascara.putpixel((x, 0), a)
    camada = Image.new("RGBA", (largura, altura), cor + (0,))
    camada.putalpha(mascara.resize((largura, altura)))
    return camada


def _degrade_vertical(largura, altura, cor, forca):
    mascara = Image.new("L", (1, altura))
    for y in range(altura):
        f = y / altura
        mascara.putpixel((0, y), round(forca * max(0.0, (f - 0.45) / 0.55) ** 1.4))
    camada = Image.new("RGBA", (largura, altura), cor + (0,))
    camada.putalpha(mascara.resize((largura, altura)))
    return camada


def _luz(largura, altura, cor, centro, raio, forca):
    """Uma luz redonda na cor do jogo (somada por cima, como um holofote)."""
    luz = Image.new("L", (largura, altura), 0)
    ImageDraw.Draw(luz).ellipse((centro[0] - raio, centro[1] - raio, centro[0] + raio, centro[1] + raio), fill=forca)
    luz = luz.filter(ImageFilter.GaussianBlur(raio * 0.55))
    colorida = Image.new("RGB", (largura, altura), cor)
    return Image.composite(colorida, Image.new("RGB", (largura, altura), (0, 0, 0)), luz)


def _arredondar(imagem, raio):
    mascara = Image.new("L", imagem.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, imagem.width - 1, imagem.height - 1), raio, fill=255)
    saida = imagem.convert("RGBA")
    saida.putalpha(ImageChops.multiply(saida.getchannel("A"), mascara))
    return saida


def _sombra(imagem, cor, raio=36, forca=170):
    """O brilho em volta da arte: a forma dela, borrada, na cor do jogo."""
    margem = raio * 2
    base = Image.new("RGBA", (imagem.width + margem * 2, imagem.height + margem * 2), cor + (0,))
    alfa = Image.new("L", base.size, 0)
    alfa.paste(imagem.getchannel("A").point(lambda v: forca if v > 8 else 0), (margem, margem))
    base.putalpha(alfa.filter(ImageFilter.GaussianBlur(raio)))
    return base, margem


def _riscos(largura, altura, cor):
    """Riscos de luz em diagonal, bem leves (o "movimento" das artes de loja)."""
    camada = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for i, (x, grossura, alfa) in enumerate(((0.52, 10, 40), (0.6, 3, 70), (0.71, 22, 26), (0.83, 4, 60), (0.9, 14, 30))):
        x0 = int(largura * x)
        d.line((x0, altura + 40, x0 + int(altura * 0.55), -40), fill=cor + (alfa,), width=grossura)
    return camada.filter(ImageFilter.GaussianBlur(2.2))


def montar(jogo):
    cor = _cor(jogo["cor"])
    poster = Image.open(ESTATICO / jogo["poster"]).convert("RGBA") if jogo.get("poster") else None
    capa = Image.open(ESTATICO / jogo["capa"]).convert("RGBA") if jogo.get("capa") else None
    # o pôster deitado vai inteiro, nítido, encostado à direita; o logo (Strike Kids) vai
    # por cima do fundo desfocado
    deitado = poster is not None and poster.width / poster.height >= 1.3 and not jogo.get("logo")

    # o fundo: a arte do jogo, grande e desfocada
    origem = (poster if deitado or not capa else capa).convert("RGB")
    fundo = _cobrir(origem, LARGURA, ALTURA).filter(ImageFilter.GaussianBlur(30))
    fundo = ImageEnhance.Brightness(ImageEnhance.Color(fundo).enhance(1.35)).enhance(0.42)
    tela = fundo.convert("RGB")
    tela = ImageChops.add(tela, _luz(LARGURA, ALTURA, cor, (int(LARGURA * 0.74), int(ALTURA * 0.5)), 430, 120))
    tela = Image.alpha_composite(tela.convert("RGBA"), _riscos(LARGURA, ALTURA, cor))

    if deitado:
        # a altura toda, encostado à direita, sumindo à esquerda (sem emenda com o fundo)
        largo = poster.resize((round(poster.width * ALTURA / poster.height), ALTURA), Image.LANCZOS)
        largo = largo.crop((max(0, largo.width - int(LARGURA * 0.72)), 0, largo.width, ALTURA))
        mascara = Image.new("L", (largo.width, 1))
        for x in range(largo.width):
            mascara.putpixel((x, 0), round(255 * min(1.0, x / (largo.width * 0.32)) ** 1.3))
        largo.putalpha(ImageChops.multiply(largo.getchannel("A"), mascara.resize(largo.size)))
        tela.alpha_composite(largo, (LARGURA - largo.width, 0))

    # a arte do jogo, à direita: o pôster em pé, a capa ou o logo
    arte = None
    if jogo.get("logo"):
        logo = Image.open(ESTATICO / jogo["logo"]).convert("RGBA")
        largura_logo = 600
        arte = logo.resize((largura_logo, round(logo.height * largura_logo / logo.width)), Image.LANCZOS)
    elif not deitado:
        if poster is not None and poster.height > poster.width * 1.2:
            alto = 520
            arte = _arredondar(poster.resize((round(poster.width * alto / poster.height), alto), Image.LANCZOS), 26)
        elif capa is not None:
            lado = 470
            arte = _arredondar(capa.resize((lado, round(capa.height * lado / capa.width)), Image.LANCZOS), 34)
    if arte is not None:
        brilho, margem = _sombra(arte, cor)
        cx = int(LARGURA * 0.76) - arte.width // 2
        cy = (ALTURA - arte.height) // 2
        tela.alpha_composite(brilho, (cx - margem, cy - margem))
        tela.alpha_composite(arte, (cx, cy))

    # o escuro onde vai o texto (à esquerda) e o chão (embaixo)
    escuro = (4, 7, 16)
    tela = Image.alpha_composite(tela, _degrade_horizontal(LARGURA, ALTURA, escuro, 238, 0.58, opaco_ate=0.1))
    tela = Image.alpha_composite(tela, _degrade_vertical(LARGURA, ALTURA, escuro, 170))
    return tela.convert("RGB")


def jogos_da_casa():
    sys.path.insert(0, str(RAIZ))
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lazer.settings")
    import django

    django.setup()
    from core.arena import JOGOS

    logos = {"strike-kids": "site/arena/capas/strike-kids-logo.webp"}
    saida = []
    for jogo in JOGOS:
        capa = jogo.get("capa") or ""
        # a "capa" do Strike Kids é o logo (o pôster dele é o fundo, deitado)
        saida.append({"slug": jogo["slug"], "cor": jogo.get("cor") or "#ff3df2", "poster": jogo.get("poster") or "",
                      "capa": "" if capa == logos.get(jogo["slug"]) else capa, "logo": logos.get(jogo["slug"], "")})
    return saida


if __name__ == "__main__":
    for jogo in jogos_da_casa():
        destino = AQUI / f"{jogo['slug']}.webp"
        montar(jogo).save(destino, "WEBP", quality=82, method=6)
        print(f"{destino.relative_to(RAIZ)}  {destino.stat().st_size // 1024} KB")
