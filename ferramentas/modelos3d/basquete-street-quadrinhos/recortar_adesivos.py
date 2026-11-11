"""Recorta a folha de adesivos da fábrica nas peças do Basquete Home Quadrinhos (adesivos/<peça>.png).

    python3 recortar_adesivos.py folha-adesivos.jpg --previa   # desenha as caixas na folha (previa-recortes.jpg)
    python3 recortar_adesivos.py folha-adesivos.jpg            # recorta as peças
    python3 recortar_adesivos.py --so prancha                  # só esta (a folha do recortes.json)

O recortes.json diz onde está cada peça na folha: a "caixa" [x0, y0, x1, y1]
em px da folha (ou "caixa_rel", em frações de 0 a 1), quanto "girar" (0, 90,
180 ou 270 graus, anti-horário) para a peça ficar em pé, vista de fora (ou
de dentro da pista, as de dentro), como o pecas.json descreve, e "espelhar"
se precisar. Avisa quando a proporção do recorte não bate com a da peça no
3D. Depois: node gerar.cjs glb fotos e o gltfpack (ver o README). Só precisa
do Pillow.
"""

import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))

from adesivos_comum import recortar  # noqa: E402

if __name__ == "__main__":
    recortar(PASTA)
