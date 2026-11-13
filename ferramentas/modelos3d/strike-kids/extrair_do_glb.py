"""As artes e os contornos do Strike Kids, tirados do .glb que a fábrica mandou.

O Strike Kids chegou como um .glb pronto (feito com o trimesh, com as artes de
verdade de cada peça em PNG: as laterais, a testeira, o painel da tela, a pista,
a frente, o acabamento de dentro e o jogo na tela). Este script guarda essas
artes como vieram (adesivos/<peça>.png) e, de cada peça recortada (as laterais,
a testeira e a frente), o CONTORNO de verdade: as arestas da borda da malha, em
coordenadas da imagem (u, v de 0 a 1, v para baixo, como no formas.json das
outras máquinas).

    python extrair_do_glb.py <strike_kids.glb da fábrica>

O .glb da fábrica (2,1 MB, as artes em PNG) não vai para o repositório; o
core/static/site/arena/modelos/strike-kids.glb de antes desta versão era ele
mesmo com as artes em JPEG (serve também, com um pouco menos de nitidez).
"""

import io
import json
import struct
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
TIPOS = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4)}
COMPONENTES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}
#: a malha da fábrica -> o nome da peça aqui
ARTES = {
    "lateral_esquerda_arte": "lateral-esquerda",
    "lateral_direita_arte": "lateral-direita",
    "testeira_arte": "testeira",
    "frente_arte": "frente",
    "painel_tela": "painel-tela",
    "pista": "pista",
    "acab_esq": "acabamento-esquerda",
    "acab_dir": "acabamento-direita",
    "monitor": "tela-do-jogo",
}
COM_CONTORNO = ("lateral-esquerda", "lateral-direita", "testeira", "frente")


def main(caminho):
    b = Path(caminho).read_bytes()
    n_json, = struct.unpack("<I", b[12:16])
    d = json.loads(b[20:20 + n_json])
    inicio = 20 + n_json + 8

    def acessor(i):
        a = d["accessors"][i]
        v = d["bufferViews"][a["bufferView"]]
        letra, tam = TIPOS[a["componentType"]]
        n = COMPONENTES[a["type"]]
        off = inicio + v.get("byteOffset", 0) + a.get("byteOffset", 0)
        passo = v.get("byteStride", tam * n)
        return [struct.unpack_from("<" + letra * n, b, off + k * passo) for k in range(a["count"])]

    formas = {}
    (AQUI / "adesivos").mkdir(exist_ok=True)
    for malha in d["meshes"]:
        peca = ARTES.get(malha.get("name"))
        if not peca:
            continue
        prim = malha["primitives"][0]
        mat = d["materials"][prim["material"]]
        textura = mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]
        imagem = d["images"][d["textures"][textura]["source"]]
        v = d["bufferViews"][imagem["bufferView"]]
        dados = b[inicio + v.get("byteOffset", 0):inicio + v.get("byteOffset", 0) + v["byteLength"]]
        figura = Image.open(io.BytesIO(dados)).convert("RGB")
        figura.save(AQUI / "adesivos" / f"{peca}.png", optimize=True)
        info = {"px": list(figura.size)}
        if peca in COM_CONTORNO:
            uv = acessor(prim["attributes"]["TEXCOORD_0"])
            tri = [t[0] for t in acessor(prim["indices"])]
            # as arestas da borda: as que só um triângulo usa (pela posição no uv: os vértices repetidos contam como um)
            chave = {}
            ids = []
            for u, w in uv:
                k = (round(u, 5), round(w, 5))
                ids.append(chave.setdefault(k, len(chave)))
            pontos = {i: k for k, i in chave.items()}
            contagem = {}
            for t in range(0, len(tri), 3):
                a, c, e = ids[tri[t]], ids[tri[t + 1]], ids[tri[t + 2]]
                for p, q in ((a, c), (c, e), (e, a)):
                    contagem[(min(p, q), max(p, q))] = contagem.get((min(p, q), max(p, q)), 0) + 1
            vizinhos = {}
            for (p, q), n in contagem.items():
                if n == 1:
                    vizinhos.setdefault(p, []).append(q)
                    vizinhos.setdefault(q, []).append(p)
            # o laço mais comprido (o contorno de fora)
            vistos, lacos = set(), []
            for comeco in vizinhos:
                if comeco in vistos:
                    continue
                laco, atual, antes = [comeco], comeco, None
                vistos.add(comeco)
                while True:
                    proximos = [x for x in vizinhos[atual] if x != antes]
                    if not proximos or proximos[0] == comeco:
                        break
                    antes, atual = atual, proximos[0]
                    if atual in vistos:
                        break
                    vistos.add(atual)
                    laco.append(atual)
                lacos.append(laco)
            laco = max(lacos, key=len)
            # glTF: v para baixo (como a imagem); guarda u, v de 0 a 1
            info["contorno"] = [[round(pontos[i][0], 5), round(pontos[i][1], 5)] for i in laco]
        formas[peca] = info
        print(peca, info["px"], len(info.get("contorno", [])), "pontos", file=sys.stderr)
    destino = AQUI / "formas.json"
    antes = json.loads(destino.read_text()) if destino.exists() else {}
    antes.update(formas)
    destino.write_text(json.dumps(antes, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
