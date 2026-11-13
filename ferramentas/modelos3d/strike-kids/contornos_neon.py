"""O caminho do neon flex: o contorno do logotipo "Strike Kids" (com os pinos) em cada arte.

Na máquina de verdade, o neon flex (a mangueira de LED) contorna o logotipo das
duas laterais (vermelho) e o da frente (azul); o da testeira segue a linha que
a própria arte marca (o montar.js a tira do contorno da peça). Aqui o contorno
sai da própria arte: o logotipo (os dois pinos, o "Strike", o "Kids" e a bola)
é separado do fundo de raios pelo GrabCut do OpenCV, dentro de uma caixa
aproximada (CAIXAS, em frações da imagem), suavizado e afastado alguns
milímetros para fora (o neon passa em volta do desenho, sem cobri-lo). Grava
em formas.json, em cada peça, `neon`: [[u, v], ...] (de 0 a 1, v para baixo).

    python contornos_neon.py [--previa]

Precisa do OpenCV (pip install opencv-python-headless numpy). --previa grava
previa-neon.png (as artes com o caminho por cima) para conferir.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
#: a caixa aproximada do logotipo (x0, y0, x1, y1, em frações da arte) e o
#: quanto o neon fica para fora do desenho (fração da largura da caixa)
CAIXAS = {
    "frente": ((0.17, 0.04, 0.60, 0.95), 0.03),
    "lateral-esquerda": ((0.62, 0.66, 0.92, 0.985), 0.025),
    "lateral-direita": ((0.09, 0.66, 0.42, 0.985), 0.025),
}


def caminho(imagem, caixa, folga):
    h, w = imagem.shape[:2]
    x0, y0, x1, y1 = int(caixa[0] * w), int(caixa[1] * h), int(caixa[2] * w), int(caixa[3] * h)
    mascara = np.zeros((h, w), np.uint8)
    fundo, frente = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(imagem, mascara, (x0, y0, x1 - x0, y1 - y0), fundo, frente, 8, cv2.GC_INIT_WITH_RECT)
    m = np.where((mascara == cv2.GC_FGD) | (mascara == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    # o desenho inteiro, sem os buracos de dentro das letras e sem os fiapos
    r = max(3, int(0.02 * (x1 - x0)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    n, rotulos, info, _ = cv2.connectedComponentsWithStats(m)
    maior = 1 + int(np.argmax(info[1:, cv2.CC_STAT_AREA]))
    m = np.where(rotulos == maior, 255, 0).astype(np.uint8)
    contornos, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    m = np.zeros_like(m)
    cv2.drawContours(m, contornos, -1, 255, cv2.FILLED)
    # para fora do desenho e arredondado (a mangueira faz curva, não canto)
    d = max(2, int(folga * (x1 - x0)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
    m = cv2.dilate(m, k)
    m = cv2.GaussianBlur(m, (0, 0), d * 0.8)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    contornos, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(contornos, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 0.0025 * (x1 - x0), True)[:, 0, :].astype(float)
    return [[round(x / w, 5), round(y / h, 5)] for x, y in c]


def main():
    formas = json.loads((AQUI / "formas.json").read_text())
    previas = []
    for peca, (caixa, folga) in CAIXAS.items():
        hd = AQUI / "adesivos-hd" / f"{peca}.webp"
        arquivo = hd if hd.exists() else AQUI / "adesivos" / f"{peca}.png"
        imagem = cv2.imread(str(arquivo), cv2.IMREAD_COLOR)
        # o GrabCut não precisa da alta definição: a arte em ~900 px basta (e é rápido)
        k = 900 / max(imagem.shape[:2])
        if k < 1:
            imagem = cv2.resize(imagem, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        pontos = caminho(imagem, caixa, folga)
        formas[peca]["neon"] = pontos
        print(peca, len(pontos), "pontos", file=sys.stderr)
        if "--previa" in sys.argv:
            h, w = imagem.shape[:2]
            p = np.array([[u * w, v * h] for u, v in pontos], np.int32)
            cv2.polylines(imagem, [p], True, (60, 60, 255), 3)
            previas.append(cv2.resize(imagem, (int(w * 500 / h), 500)))
    (AQUI / "formas.json").write_text(json.dumps(formas, ensure_ascii=False, indent=1) + "\n")
    if previas:
        cv2.imwrite(str(AQUI / "previa-neon.png"), np.hstack(previas))


if __name__ == "__main__":
    main()
