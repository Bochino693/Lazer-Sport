"""O acabamento das fotos das categorias e o .webp do site.

Lê o render do gerar.py (render/<chave>.png, 1600 x 1200, já com a cor do Khronos
PBR Neutral: a foto do produto com a cor que ela tem) e grava
core/static/site/categorias/<chave>.webp -- o arquivo que o cadastro sobe para a
categoria (core/categorias_capas.py) e que o card da home mostra.

O acabamento é o de uma foto de câmera, sem filtro de aplicativo:
  * o brilho do neon e das luzes (o "bloom" da lente: o que é quase branco
    espalha um halo leve da própria cor);
  * a cor viva (o "vibrance": puxa a cor fraca e quase nada a que já é forte;
    o branco, o cinza e o preto não mudam);
  * a clareza (o contraste local, como o de uma câmera boa) e a nitidez fina;
  * a vinheta bem leve da lente.
O arquivo fica abaixo de ~250 KB: a qualidade do WebP desce até caber.

    python compor.py                    (todas as que têm render)
    python compor.py kids fliperama     (só estas)
    python compor.py --para <pasta>     (as provas, fora do site)
    python compor.py --previa           (a partir das prévias, em render/previa/; nunca no site)
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

PASTA = Path(__file__).resolve().parent
RENDER = PASTA / "render"
DESTINO = PASTA.parent.parent / "core" / "static" / "site" / "categorias"
LARGURA, ALTURA = 1600, 1200
TETO_KB = 245

#: Quanto de cada coisa (as cenas podem pedir outro: ACABAMENTO[chave]).
PADRAO = {
    "bloom": 0.32,        # o halo das luzes
    "bloom_limiar": 0.80, # a partir de que luz (0-1) o halo nasce
    "vibrance": 0.22,
    "clareza": 0.16,      # o contraste local (raio grande)
    "nitidez": 0.55,      # a nitidez fina
    "vinheta": 0.10,
    "gama": 1.0,          # < 1 clareia os meios-tons
}
#: As cenas mais escuras (o salão de esporte, o galpão dos trampolins) ganham um tanto de luz nos meios-tons.
ACABAMENTO: dict[str, dict] = {
    "competitivos": {"gama": 0.75},
    "trampolins": {"gama": 0.66},
    "simuladores": {"gama": 0.90},
    "area-ninja": {"gama": 0.92},
    "espaco-esportivo-kids": {"gama": 0.92},
}


def _borrar(arr, raio):
    img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(raio))).astype(np.float32) / 255


def acabar(img: Image.Image, op: dict) -> Image.Image:
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255
    escala = a.shape[1] / LARGURA
    # o bloom: o que passa do limiar, desfocado em dois raios, somado como luz ("screen")
    luma = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    alto = np.clip((luma - op["bloom_limiar"]) / (1 - op["bloom_limiar"]), 0, 1)[..., None] * a
    halo = 0.6 * _borrar(alto, 6 * escala) + 0.4 * _borrar(alto, 22 * escala)
    a = 1 - (1 - a) * (1 - np.clip(halo * op["bloom"] * 2.2, 0, 1))
    # o vibrance: a saturação sobe mais onde ela é baixa (o cinza/branco/preto puro ficam)
    mx = a.max(-1, keepdims=True)
    mn = a.min(-1, keepdims=True)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    cinza = a.mean(-1, keepdims=True)
    ganho = op["vibrance"] * (1 - sat) * np.clip(sat * 4, 0, 1)
    a = np.clip(cinza + (a - cinza) * (1 + ganho), 0, 1)
    if op["gama"] != 1.0:
        a = a ** op["gama"]
    # a clareza: o contraste local na luz (raio grande), poupando o branco e o preto
    luma = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    base = _borrar(luma[..., None].repeat(3, -1), 28 * escala)[..., 0]
    detalhe = luma - base
    peso = np.clip(luma * 3, 0, 1) * np.clip((1 - luma) * 3, 0, 1)
    a = np.clip(a + (op["clareza"] * detalhe * peso)[..., None], 0, 1)
    # a vinheta leve
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    a = a * (1 - op["vinheta"] * np.clip(d - 0.35, 0, 1.5) / 1.5)[..., None]
    out = Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8))
    if out.size != (LARGURA, ALTURA):
        out = out.resize((LARGURA, ALTURA), Image.LANCZOS)
    # a nitidez fina (a de uma câmera boa, sem halo)
    return out.filter(ImageFilter.UnsharpMask(radius=1.1, percent=int(op["nitidez"] * 100), threshold=2))


def salvar_webp(img: Image.Image, destino: Path, teto_kb=TETO_KB):
    for q in range(92, 50, -2):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() <= teto_kb * 1024:
            break
    destino.write_bytes(buf.getvalue())
    return q, buf.tell() // 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chaves", nargs="*")
    ap.add_argument("--para")
    ap.add_argument("--previa", action="store_true")
    args = ap.parse_args()
    origem = RENDER / "previa" if args.previa else RENDER
    destino = Path(args.para) if args.para else (RENDER / "previa-webp" if args.previa else DESTINO)
    destino.mkdir(parents=True, exist_ok=True)
    chaves = args.chaves or sorted(p.stem for p in origem.glob("*.png"))
    for chave in chaves:
        arquivo = origem / f"{chave}.png"
        if not arquivo.exists():
            print(f"{chave}: sem render ({arquivo})")
            continue
        op = dict(PADRAO)
        op.update(ACABAMENTO.get(chave, {}))
        img = acabar(Image.open(arquivo), op)
        q, kb = salvar_webp(img, destino / f"{chave}.webp")
        print(f"{chave}: {destino / f'{chave}.webp'} (qualidade {q}, {kb} KB)")


if __name__ == "__main__":
    main()
