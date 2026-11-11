"""A lateral do Air Game Kids (astronautas) da foto do catálogo, desentortada pela perspectiva.

Homografia de 4 pontos: os cantos e os pés da lateral na foto (433x577) para o
contorno da lateral da folha dos alienígenas (a mesma mesa). Só a lateral que a
foto mostra; o resto da mesa não aparece na foto.
"""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
M = AQUI.parent / "air-game-kids-alienigenas"
W, H = 988, 592  # 2x a peça da folha (494x296)
foto = Image.open(AQUI / "foto-do-catalogo.png").convert("RGBA")
contorno = json.load(open(f"{M}/formas.json"))["lateral-esquerda"]["contorno"]

# os cantos e os pés da lateral na foto, ajustados à silhueta (erro médio de 0,7 px na borda)
pontos_foto = json.loads(sys.argv[1]) if len(sys.argv) > 1 else [[51.4, 250.0], [409.5, 173.8], [145.4, 437.5], [369.9, 336.1]]
pontos_peca = [[0.02429, 0.16554], [0.96761, 0.15878], [0.12551, 0.99662], [0.88866, 0.98311]]


def homografia(origem, destino):
    linhas = []
    for (x, y), (u, v) in zip(origem, destino):
        linhas.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        linhas.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(linhas, float))
    h = vt[-1].reshape(3, 3)
    return h / h[2, 2]


# PIL quer a ida da saída (a peça) para a entrada (a foto)
destino = [[u * W, v * H] for u, v in pontos_peca]
h = homografia(destino, pontos_foto)
coef = h.flatten()[:8]
peca = foto.transform((W, H), Image.PERSPECTIVE, coef, Image.BICUBIC)
mascara = Image.new("L", (W, H), 0)
ImageDraw.Draw(mascara).polygon([(u * W, v * H) for u, v in contorno], fill=255)
fundo = Image.new("RGBA", (W, H), (255, 255, 255, 255))
fundo.paste(peca, (0, 0), Image.composite(peca.getchannel("A"), Image.new("L", (W, H), 0), mascara))
fundo.convert("RGB").save(AQUI / "lateral-desentortada.png")

# a conferência: o contorno da peça levado de volta à foto
inv = np.linalg.inv(h)
ida = homografia(pontos_foto, destino)
volta = np.linalg.inv(ida)
prova = Image.new("RGBA", foto.size, (255, 255, 255, 255))
prova.alpha_composite(foto)
d = ImageDraw.Draw(prova)
poli = []
for u, v in contorno:
    p = volta @ np.array([u * W, v * H, 1.0])
    poli.append((p[0] / p[2], p[1] / p[2]))
d.line(poli + [poli[0]], fill=(255, 0, 0, 255), width=2)
for x, y in pontos_foto:
    d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(0, 255, 0, 255), width=2)
prova.convert("RGB").resize((866, 1154), Image.LANCZOS).save(AQUI / "previa-contorno.png")
print("ok")
