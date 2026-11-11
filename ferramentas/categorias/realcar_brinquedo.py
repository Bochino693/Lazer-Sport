"""Realça um brinquedo escuro (a capa e as vistas do Strike Kids, LEIA-ME 74).

Só onde há cor (o brinquedo): os meios-tons sobem (gama 0,6), a cor (1,2x),
o volume (unsharp largo) e a nitidez (unsharp fino); o fundo só ganha nitidez.

    python ferramentas/categorias/realcar_brinquedo.py origem.webp destino.webp [...]
"""
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

def realcar(im):
    im = im.convert("RGB")
    hsv = np.asarray(im.convert("HSV"), dtype=np.float32)
    s, v = hsv[..., 1] / 255, hsv[..., 2] / 255
    # o brinquedo (e o que tem cor): saturado e nem preto nem estourado
    m = np.clip((s - 0.18) / 0.17, 0, 1) * np.clip((v - 0.10) / 0.12, 0, 1) * np.clip((0.97 - v) / 0.05, 0, 1)
    mask = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4))
    # luz: os meios-tons sobem (gama), o preto e o branco quase não mudam
    arr = np.asarray(im, dtype=np.float32) / 255
    claro = np.power(arr, 0.6)
    claro = Image.fromarray((np.clip(claro, 0, 1) * 255).astype(np.uint8))
    claro = ImageEnhance.Color(claro).enhance(1.2)
    claro = claro.filter(ImageFilter.UnsharpMask(radius=max(2, im.width // 90), percent=40, threshold=2))  # volume
    claro = claro.filter(ImageFilter.UnsharpMask(radius=1.3, percent=120, threshold=2))  # nitidez
    claro = ImageEnhance.Contrast(claro).enhance(1.08)
    # o fundo só ganha nitidez
    fundo = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=50, threshold=3))
    return Image.composite(claro, fundo, mask)

if __name__ == "__main__":
    for origem, destino in zip(sys.argv[1::2], sys.argv[2::2]):
        im = Image.open(origem)
        realcar(im).save(destino, "WEBP", quality=90, method=6)
        print(destino)
