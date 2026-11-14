"""Renderiza as fotos das categorias no Blender Cycles (o módulo bpy) -- ver cena.py e cenas.py.

    python gerar.py                         (todas, no tamanho final: render/<chave>.png)
    python gerar.py kids fliperama          (só estas)
    python gerar.py --previa [chaves]       (pequenas e rápidas: render/previa/<chave>.png)
    python gerar.py --arranjo [chaves]      (sem render: só as medidas, as colisões e o enquadramento)

O Python é o do ambiente com o bpy (o Blender 5 como módulo, Python 3.11):
    python3.11 -m venv venv && venv/bin/pip install bpy==5.0.1 pillow
Depois: python compor.py [chaves] (o acabamento e o .webp em core/static/site/categorias/).

CPU só: OpenImageDenoise, amostragem adaptativa, 3 threads (`--threads`). Cada foto final
(1600 x 1200) leva de 4 a 10 minutos numa CPU de 4 núcleos dividida.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402

import cena as C  # noqa: E402
from cenas import CENAS  # noqa: E402

PASTA = Path(__file__).resolve().parent
RENDER = PASTA / "render"
#: A lista das máquinas de cada foto: o teste confere que cada uma é da categoria no site.
LISTA = C.RAIZ / "ferramentas" / "categorias" / "maquinas-das-fotos.json"
#: A Área Baby não tem produto no catálogo: fica fora da lista (o que aparece é o cantinho baby do Modelo 4).
FORA_DA_LISTA = {"area-baby"}


def montar(chave):
    dados = CENAS[chave]
    C.limpar()
    # o formato da foto já no começo: as medidas na foto (o arranjo, o enquadramento) são em 4:3
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = 1600, 1200
    if "montar" in dados:  # a cena que monta tudo sozinha (as peças no balcão)
        return dados["montar"]()
    cam = C.camera(**dados.get("cam", {}))
    maquinas = dados["maquinas"]()
    # o enquadramento: o grupo no meio, a base na linha de baixo (o .glb grande: a câmera anda)
    enquadrar = dados.get("enquadrar", {"dolly": False})
    if enquadrar is not None:
        C.enquadrar(maquinas, **enquadrar)
    # o salão em volta: a parede do fundo sempre atrás da máquina mais longe (com o ar de uma sala)
    amb = dict(dados.get("amb", {}))
    longe = max(C.extensao_no_chao(m)[3] for m in maquinas)
    amb["fundo"] = max(amb.get("fundo", C.AMBIENTE["fundo"]), longe + amb.get("folga_fundo", 2.2))
    C.ambiente(amb)
    if "foco" not in dados.get("cam", {}):
        # o foco no grupo: a distância média das máquinas (a profundidade de campo leve)
        dists = [math.hypot(m["pos"][0] - cam.location.x, m["pos"][1] - cam.location.y) for m in maquinas]
        cam.data.dof.focus_distance = sum(dists) / len(dists) - 0.3
    return maquinas


def conferir(chave, maquinas):
    """As colisões e o enquadramento (nada cortado, a folga de cima para a etiqueta do card)."""
    problemas = []
    for a, b in C.colisoes(maquinas):
        problemas.append(f"colisão: {a} x {b}")
    for m in C.projetar_bases(maquinas):
        x0, y0, x1, y1 = m["caixa"]
        if x0 < 0.02 or x1 > 0.98 or y1 > 0.97 or y0 < 0.08:
            problemas.append(f"perto da borda: {m['nome']} ({x0:.2f}, {y0:.2f}, {x1:.2f}, {y1:.2f})")
    for m in maquinas:
        if m.get("alerta"):
            problemas.append(f"conferir o giro da foto: {m['nome']}")
    for p in problemas:
        print("  !", p)
    return problemas


def lista_das_maquinas(maquinas):
    nomes = []
    for m in maquinas:
        if m["tipo"] == "glb":
            nome = f"{m['nome']} (3D)"
        elif m["tipo"] == "peca":
            nome = f"{m['nome']} (peça)"
        else:
            nome = m["nome"]
        nomes.append(nome + (" (ao fundo)" if m.get("ao_fundo") else ""))
    return nomes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chaves", nargs="*")
    ap.add_argument("--previa", action="store_true")
    ap.add_argument("--arranjo", action="store_true")
    ap.add_argument("--largura", type=int)
    ap.add_argument("--amostras", type=int)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--para", help="outra pasta para os renders (as provas)")
    args = ap.parse_args([a for a in sys.argv[1:] if a != "--"])
    chaves = args.chaves or list(CENAS)
    largura = args.largura or (640 if args.previa else 1600)
    amostras = args.amostras or (24 if args.previa else 192)
    destino = Path(args.para) if args.para else (RENDER / "previa" if args.previa else RENDER)
    destino.mkdir(parents=True, exist_ok=True)
    lista = json.loads(LISTA.read_text(encoding="utf-8")) if LISTA.exists() else {}
    for chave in chaves:
        print(f"== {chave}")
        inicio = time.time()
        maquinas = montar(chave)
        problemas = conferir(chave, maquinas)
        if args.arranjo:
            continue
        dados = CENAS[chave]
        C.configurar(largura, largura * 3 // 4, amostras, threads=args.threads, **dados.get("render", {}))
        bpy.context.scene.render.filepath = str(destino / f"{chave}.png")
        bpy.ops.render.render(write_still=True)
        info = {
            "maquinas": lista_das_maquinas(maquinas),
            "bases": C.projetar_bases(maquinas),
            "problemas": problemas,
            "segundos": round(time.time() - inicio),
            "largura": largura,
            "amostras": amostras,
        }
        (destino / f"{chave}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"   {info['segundos']} s")
        if not args.previa and not args.para and chave not in FORA_DA_LISTA:
            lista[chave] = info["maquinas"]
            LISTA.write_text(json.dumps(lista, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
