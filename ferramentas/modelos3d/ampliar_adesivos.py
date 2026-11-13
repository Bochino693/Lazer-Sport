"""Os adesivos em alta definição: cada peça recortada da folha, ampliada 4x com nitidez.

A folha de adesivos da fábrica tem pouca resolução (~400 a 600 px nas peças
grandes). Ampliada com suavização (o que o .glb fazia antes), a arte fica
borrada de perto: a letra, o contorno preto dos desenhos e as bordas das cores
viram uma névoa. Aqui cada peça passa pelo Real-ESRGAN (o modelo
RealESRGAN_x4plus_anime_6B, feito para arte desenhada de cores chapadas, como a
dos adesivos), que amplia 4x refazendo as bordas nítidas -- a arte é a mesma
(nada redesenhado, recolorido nem tirado), só com a definição que a impressão
de verdade tem.

    python ampliar_adesivos.py <pasta do modelo> [--modelo realesrgan_anime6b.onnx] [--lado 2048] [--reduzir 0.5]

Lê <pasta>/adesivos/*.png e grava <pasta>/adesivos-hd/<peça>.webp (WebP de
qualidade 94, o lado maior até --lado px). O montar.js usa a versão HD quando
ela existe. Precisa de: pip install onnxruntime numpy pillow e do modelo em
ONNX (licença BSD-3, a do Real-ESRGAN), que não vai para o repositório:
    https://huggingface.co/RekluzLabs/realesrgan_anime6b.onnx (realesrgan_anime6b.onnx, 18 MB)
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
LADO = 2048  # o lado maior de um adesivo no .glb (as peças grandes)
BLOCO = 192  # o pedaço da imagem que vai de cada vez ao modelo (a memória fica pequena)
SOBRA = 12  # a borda a mais de cada pedaço (sem emenda entre eles)


def ampliar(sessao, imagem):
    """A imagem RGB ampliada 4x pelo modelo, em pedaços com sobra (sem emenda)."""
    a = np.asarray(imagem.convert("RGB")).astype(np.float32) / 255.0
    h, w, _ = a.shape
    saida = np.zeros((h * 4, w * 4, 3), np.float32)
    entrada = sessao.get_inputs()[0].name
    for y0 in range(0, h, BLOCO):
        for x0 in range(0, w, BLOCO):
            y1, x1 = min(h, y0 + BLOCO), min(w, x0 + BLOCO)
            ya, xa = max(0, y0 - SOBRA), max(0, x0 - SOBRA)
            yb, xb = min(h, y1 + SOBRA), min(w, x1 + SOBRA)
            pedaco = a[ya:yb, xa:xb].transpose(2, 0, 1)[None]
            r = sessao.run(None, {entrada: np.ascontiguousarray(pedaco)})[0][0].transpose(1, 2, 0)
            saida[y0 * 4:y1 * 4, x0 * 4:x1 * 4] = r[(y0 - ya) * 4:(y0 - ya + y1 - y0) * 4, (x0 - xa) * 4:(x0 - xa + x1 - x0) * 4]
    return Image.fromarray((np.clip(saida, 0, 1) * 255 + 0.5).astype(np.uint8))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("pasta")
    p.add_argument("--modelo", default=str(AQUI / "realesrgan_anime6b.onnx"))
    p.add_argument("--lado", type=int, default=LADO)
    p.add_argument("--so", nargs="*", default=None, help="só estas peças (o nome sem .png)")
    p.add_argument("--reduzir", type=float, default=1.0,
                   help="reduz a peça antes (a que já foi ampliada com suavização: o modelo quer a resolução de origem)")
    args = p.parse_args()
    import onnxruntime as ort

    pasta = Path(args.pasta)
    destino = pasta / "adesivos-hd"
    destino.mkdir(exist_ok=True)
    sessao = ort.InferenceSession(args.modelo, providers=["CPUExecutionProvider"])
    for arquivo in sorted((pasta / "adesivos").glob("*.png")):
        if args.so and arquivo.stem not in args.so:
            continue
        original = Image.open(arquivo)
        entrada = original
        if args.reduzir < 1:
            entrada = original.resize((round(original.width * args.reduzir), round(original.height * args.reduzir)), Image.LANCZOS)
        grande = ampliar(sessao, entrada)
        if max(grande.size) > args.lado:
            k = args.lado / max(grande.size)
            grande = grande.resize((round(grande.width * k), round(grande.height * k)), Image.LANCZOS)
        grande.save(destino / f"{arquivo.stem}.webp", "WEBP", quality=94, method=6)
        print(f"{arquivo.name}: {original.size} -> {grande.size}", file=sys.stderr)


if __name__ == "__main__":
    main()
