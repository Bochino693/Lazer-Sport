"""O acabamento das fotos do estúdio (só Pillow e numpy: roda com qualquer Python).

Do mestre (o PNG do Blender, já na transformação de cor) para a foto do site: a vinheta leve
(a das lentes de verdade), a curva em S leve (o contraste de foto), um tico de vibração na cor
(as cores fracas sobem mais que as fortes: a pele e o branco não "estouram"), a redução com
Lanczos (o render grande vira detalhe na foto pequena) e o realce de borda na medida da foto
final. O .webp sai na qualidade 90 e desce de 2 em 2 só
o necessário para caber no limite de peso do card (250 KB, como os testes do site pedem).

Também cola a foto da fábrica no lugar do cartão (o adesivo sem 3D: `colar_foto`) e monta as
folhas de contato (o antes e o depois).
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

LIMITE = 250 * 1024


def _vinheta(img, forca=0.2):
    """Escurece as bordas de leve (a vinheta da lente): 0 no meio, `forca` nos cantos."""
    w, h = img.size
    y, x = np.ogrid[0:h, 0:w]
    r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    t = np.clip((r - 0.4) / 0.6, 0, 1)
    fator = 1 - forca * (t * t * (3 - 2 * t))
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) * fator[..., None]
    return Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8))


def _vibracao(img, quanto=0.22):
    """A saturação sobe mais onde ela é baixa (s' = s + quanto * s * (1 - s))."""
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32)
    s = hsv[..., 1] / 255
    hsv[..., 1] = np.clip(s + quanto * s * (1 - s), 0, 1) * 255
    return Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")


def _contraste(img, quanto=0.18):
    """A curva em S leve (o "punch" da foto): as sombras descem e as luzes sobem, o meio fica."""
    x = np.arange(256, dtype=np.float32) / 255
    y = x - quanto * np.sin(2 * np.pi * x) / (2 * np.pi)
    tabela = np.clip(y * 255 + 0.5, 0, 255).astype(np.uint8).tolist()
    return img.point(tabela * 3)


def acabar(mestre, tamanho, transparente=False, vinheta=0.2, vibracao=0.22, contraste=0.18, nitidez=(0.9, 70, 2)):
    """A foto final (PIL) no `tamanho` (largura, altura), a partir do mestre (caminho ou PIL)."""
    img = Image.open(mestre) if isinstance(mestre, (str, Path)) else mestre
    alfa = img.getchannel("A") if transparente and "A" in img.getbands() else None
    rgb = img.convert("RGB")
    if not transparente:
        rgb = _vinheta(rgb, vinheta)
    rgb = _contraste(rgb, contraste)
    rgb = _vibracao(rgb, vibracao)
    rgb = rgb.resize(tamanho, Image.LANCZOS)
    raio, porcento, limiar = nitidez
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=raio, percent=porcento, threshold=limiar))
    if alfa is not None:
        rgb.putalpha(alfa.resize(tamanho, Image.LANCZOS))
    return rgb


def gravar_webp(img, destino, qualidade=90, limite=LIMITE, minima=72):
    """Grava o .webp na `qualidade` (descendo de 2 em 2 até caber no `limite`). Devolve a qualidade usada."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    q = qualidade
    while True:
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() <= limite or q <= minima:
            destino.write_bytes(buf.getvalue())
            return q
        q -= 2


def colar_foto(render, foto, caixa, contraste=1.06, cor=1.08, nitidez=True):
    """Cola a foto recortada (RGBA) na `caixa` (frações x0, y0, x1, y1) do render (PIL RGB)."""
    w, h = render.size
    x0, y0, x1, y1 = caixa
    largura, altura = round((x1 - x0) * w), round((y1 - y0) * h)
    img = Image.open(foto).convert("RGBA") if isinstance(foto, (str, Path)) else foto.convert("RGBA")
    alfa = img.getchannel("A")
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(contraste)
    rgb = ImageEnhance.Color(rgb).enhance(cor)
    rgb = rgb.resize((largura, altura), Image.LANCZOS)
    if nitidez:
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=2))
    alfa = alfa.resize((largura, altura), Image.LANCZOS)
    saida = render.convert("RGB").copy()
    saida.paste(rgb, (round(x0 * w), round(y0 * h)), alfa)
    return saida


def folha_de_contato(itens, destino, colunas=4, largura=520, titulo=None):
    """Monta a folha de contato: `itens` = [(caminho ou PIL, rótulo)]. Grava JPEG."""
    fotos = []
    for item, rotulo in itens:
        img = Image.open(item) if isinstance(item, (str, Path)) else item
        if "A" in img.getbands():  # o recorte sem fundo: num xadrez
            fundo = Image.new("RGB", img.size, (60, 60, 60))
            xadrez = ImageDraw.Draw(fundo)
            passo = max(8, img.width // 40)
            for yy in range(0, img.height, passo):
                for xx in range((yy // passo) % 2 * passo, img.width, 2 * passo):
                    xadrez.rectangle((xx, yy, xx + passo - 1, yy + passo - 1), fill=(90, 90, 90))
            fundo.paste(img, (0, 0), img.getchannel("A"))
            img = fundo
        img = img.convert("RGB")
        escala = largura / img.width
        img = img.resize((largura, round(img.height * escala)), Image.LANCZOS)
        faixa = ImageDraw.Draw(img)
        faixa.rectangle((0, 0, largura, 20), fill=(0, 0, 0))
        faixa.text((5, 4), rotulo, fill=(255, 230, 80), font=ImageFont.load_default())
        fotos.append(img)
    linhas = [fotos[i:i + colunas] for i in range(0, len(fotos), colunas)]
    topo = 34 if titulo else 0
    altura = topo + sum(max(f.height for f in linha) for linha in linhas)
    folha = Image.new("RGB", (largura * colunas, altura), (24, 24, 28))
    if titulo:
        ImageDraw.Draw(folha).text((10, 10), titulo, fill=(255, 255, 255), font=ImageFont.load_default())
    y = topo
    for linha in linhas:
        for i, foto in enumerate(linha):
            folha.paste(foto, (i * largura, y))
        y += max(f.height for f in linha)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    folha.save(destino, quality=88)
    return destino
