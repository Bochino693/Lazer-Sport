"""A câmera da perspectiva da fábrica, calibrada nos cantos da estrutura.

    python3 calibrar.py            # grava camera-perspectiva.json

A perspectiva sem fundo do projeto (1219 × 781 px; no site, a
`perspectiva.webp`, com 55 px a menos em cima) foi feita com uma câmera de
verdade: com os cantos da estrutura que se acham nela (o pixel de cada um
e o ponto dele no `montar.js`, em metros de trabalho: x ao longo da barra,
y para o fundo, z para cima), a DLT acha a matriz 3 × 4 que leva um ponto
ao pixel. Com ela se mede o que a planta não dá (a altura da frente da
perna, a cunha do 2º módulo, o degrau triangular do 4º) e o `gerar.cjs`
desenha o objeto do mesmo ponto (v-projeto.png), para comparar lado a lado.
Erro: ~2 px em média, 4 px no pior ponto.

Python puro (sem numpy): mínimos quadrados com p34 = 1 e a decomposição
RQ feita à mão.
"""

import json
import math
from pathlib import Path

LARGURA, ALTURA = 1219, 781

#: (ponto de trabalho em metros, pixel na perspectiva da fábrica)
PONTOS = [
    ((3.66, 0.04, 1.96), (927, 186)),  # alto da ponta direita, frente
    ((3.66, 0.96, 1.96), (978, 160)),  # alto da ponta direita, fundo
    ((3.66, 0.04, 0.0), (900, 585)),  # pé da coluna da frente, ponta direita
    ((3.66, 0.96, 0.0), (952, 505)),  # pé da coluna do fundo, ponta direita
    ((0.04, 0.04, 1.96), (345, 135)),  # alto da ponta esquerda, frente (onde chega o telhado da perna)
    ((0.04, 0.96, 1.96), (452, 119)),  # alto da ponta esquerda, fundo
    ((1.0, 0.04, 0.0), (495, 472)),  # pé da coluna entre os módulos 1 e 2, frente
    ((2.7, 0.04, 0.0), (728, 537)),  # pé da coluna entre os módulos 3 e 4, frente
    ((0.04, 0.96, 0.0), (475, 390)),  # pé da coluna do fundo, ponta esquerda
    ((0.04, 0.04, 0.0), (388, 438)),  # pé da coluna da frente, ponta esquerda (atrás do escorregador)
]


def resolver(a, b):
    """Resolve a x = b (Gauss com pivô)."""
    n = len(a)
    m = [linha[:] + [b[i]] for i, linha in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(m[i][c]))
        m[c], m[p] = m[p], m[c]
        for i in range(n):
            if i != c:
                f = m[i][c] / m[c][c]
                m[i] = [x - f * y for x, y in zip(m[i], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def dlt(pontos):
    """A matriz 3 × 4 (com p34 = 1) pelos mínimos quadrados (as equações normais)."""
    linhas, alvo = [], []
    for (x, y, z), (u, v) in pontos:
        linhas.append([x, y, z, 1, 0, 0, 0, 0, -u * x, -u * y, -u * z])
        alvo.append(u)
        linhas.append([0, 0, 0, 0, x, y, z, 1, -v * x, -v * y, -v * z])
        alvo.append(v)
    ata = [[sum(l[i] * l[j] for l in linhas) for j in range(11)] for i in range(11)]
    atb = [sum(l[i] * t for l, t in zip(linhas, alvo)) for i in range(11)]
    p = resolver(ata, atb) + [1.0]
    return [p[0:4], p[4:8], p[8:12]]


def projetar(p, ponto):
    h = [sum(p[i][j] * c for j, c in enumerate([*ponto, 1.0])) for i in range(3)]
    return h[0] / h[2], h[1] / h[2]


def decompor(p):
    """P = K [R | -R C]: a lente (K, com K33 = 1), os eixos (R, linhas) e a posição C."""
    m = [linha[:3] for linha in p]
    quarta = [linha[3] for linha in p]
    centro = resolver(m, [-v for v in quarta])
    pt = lambda a, b: sum(x * y for x, y in zip(a, b))
    mais = lambda a, b, k: [x + k * y for x, y in zip(a, b)]
    norma = lambda a: math.sqrt(pt(a, a))
    # o que está na frente da câmera tem profundidade positiva
    sinal = 1 if pt(m[2], [a - c for a, c in zip(PONTOS[0][0], centro)]) > 0 else -1
    m = [[sinal * v for v in linha] for linha in m]
    k33 = norma(m[2])
    r3 = [v / k33 for v in m[2]]
    k23 = pt(m[1], r3)
    resto = mais(m[1], r3, -k23)
    k22 = norma(resto)
    r2 = [v / k22 for v in resto]
    k13, k12 = pt(m[0], r3), pt(m[0], r2)
    resto = mais(mais(m[0], r2, -k12), r3, -k13)
    k11 = norma(resto)
    r1 = [v / k11 for v in resto]
    lente = {"fx": k11 / k33, "fy": k22 / k33, "s": k12 / k33, "cx": k13 / k33, "cy": k23 / k33}
    return lente, (r1, r2, r3), centro


def main():
    p = dlt(PONTOS)
    erros = [math.dist(projetar(p, x), uv) for x, uv in PONTOS]
    lente, (r1, r2, r3), centro = decompor(p)
    w, h, perto, longe = LARGURA, ALTURA, 0.05, 100.0
    fx, fy, s, cx, cy = (lente[k] for k in ("fx", "fy", "s", "cx", "cy"))
    # a projeção do three (a câmera olha para -z, y para cima), linha a linha
    linhas = [
        [2 * fx / w, -2 * s / w, -(2 * cx / w - 1), 0],
        [0, 2 * fy / h, 2 * cy / h - 1, 0],
        [0, 0, -(longe + perto) / (longe - perto), -2 * longe * perto / (longe - perto)],
        [0, 0, -1, 0],
    ]
    camera = {
        "imagem": "a perspectiva sem fundo da fábrica (1219 × 781)",
        "w": w,
        "h": h,
        "pos": [round(v, 5) for v in centro],
        # os eixos da câmera do three em metros de trabalho: x (direita), y (cima), z (para trás)
        "eixos": [[round(v, 6) for v in r1], [round(-v, 6) for v in r2], [round(-v, 6) for v in r3]],
        "proj": [round(linhas[i][j], 7) for j in range(4) for i in range(4)],  # coluna a coluna (fromArray)
        "lente": {k: round(v, 3) for k, v in lente.items()},
        "erro_px": {"medio": round(sum(erros) / len(erros), 2), "maior": round(max(erros), 2)},
        "pontos": [{"trabalho_m": list(x), "pixel": list(uv)} for x, uv in PONTOS],
        "dlt": [[round(v, 8) for v in linha] for linha in p],
    }
    destino = Path(__file__).with_name("camera-perspectiva.json")
    destino.write_text(json.dumps(camera, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("câmera em (m de trabalho):", camera["pos"], "lente:", camera["lente"])
    print("erro (px): médio", camera["erro_px"]["medio"], "maior", camera["erro_px"]["maior"])


if __name__ == "__main__":
    main()
