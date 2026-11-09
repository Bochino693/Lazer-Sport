"""Lê o .3ds do Brinquedão Modelo 4 e guarda a estrutura de tubos azuis em mm (estrutura.json).

    /home/user/.venv-ls/bin/python extrair.py caminho/do/brinquedao.3ds

O .3ds da fábrica tem ~295 mil triângulos (cada tubo com 408) em 716
objetos: 709 "Group#" -- as colunas e as barras, quase todas em DUAS cópias
(uma a 2,54 m e outra a 2,55 m, uma em y = 6590 e outra em y = 6600...) --,
o arco azul da entrada da piscina do tobogã e uns "Mesh#" soltos (um plano
a 20 m dali, dois pontos a 28 m: sobras de desenho, que saem). Aqui ele
vira uma lista leve; o montar.js refaz cada tubo no mesmo lugar e medida.

Lê com o leitor do site (core/conversor_3d.py: ler_3ds, Modelo), com o
teto de triângulos levantado só aqui.

O que sai (tudo em mm; x ao longo, y para o FUNDO, z para cima):
  colunas  [x, y, z0, z1]          os três lances de cada coluna viram um
  barras   [x0, y0, z0, x1, y1, z1, raio]   as cópias repetidas viram uma
  arco     [x0, x1, y, z0, z1]     o arco da entrada da piscina do tobogã
  marca    [x, y, z, raio]         o disco solto a 2,92 m no 3º módulo do
                                   trecho de 9 m: o lugar do rolo em pé
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from core import conversor_3d  # noqa: E402

conversor_3d.TRIANGULOS_MAXIMOS = 1_000_000  # o arquivo tem ~295 mil; o site aceita 400 mil
modelo, _info = conversor_3d.ler_3ds(Path(sys.argv[1]).read_bytes(), conversor_3d.Arquivos())

r = lambda v, q=10: int(round(v / q) * q)
pecas = []
for nome, triangulos in modelo.grupos.items():
    pontos = [p for _m, tri, _uv in triangulos for p in tri]
    caixa = [f(p[i] for p in pontos) for i in range(3) for f in (min, max)]
    pecas.append({"nome": nome, "n": len(triangulos), "bb": caixa})

# as sobras: o que fica longe do brinquedo (y > 9 m) ou é só um plano/ponto
dentro = [p for p in pecas if p["bb"][3] < 9000]


def agrupar(valores, folga=45):
    """Os valores parecidos (duas cópias do mesmo tubo a 1-2 cm) viram um só: {valor: o do grupo}."""
    grupos = []
    for v in sorted(set(valores)):
        if grupos and v - grupos[-1][-1] <= folga:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return {v: r(sum(g) / len(g)) for g in grupos for v in g}


tubos = [p for p in dentro if p["nome"].startswith("Group") and p["n"] == 408]
arco = [p for p in dentro if p["nome"].startswith("Group") and p["n"] > 2000]
marca = [p for p in dentro if p["nome"].startswith("Mesh") and p["n"] == 100]

colunas, barras = [], []
for p in tubos:
    x0, x1, y0, y1, z0, z1 = p["bb"]
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dz > 200 and dx < 120 and dy < 120:
        colunas.append(((x0 + x1) / 2, (y0 + y1) / 2, z0, z1))
    elif dx > 200:
        barras.append(("x", x0, x1, (y0 + y1) / 2, (z0 + z1) / 2, max(dy, dz) / 2))
    elif dy > 200:
        barras.append(("y", y0, y1, (x0 + x1) / 2, (z0 + z1) / 2, max(dx, dz) / 2))

# as linhas da grade: x e y de todas as colunas e barras, e as alturas
gx = agrupar([c[0] for c in colunas] + [b[3] for b in barras if b[0] == "y"])
gy = agrupar([c[1] for c in colunas] + [b[3] for b in barras if b[0] == "x"])
gz = agrupar([b[4] for b in barras], 30)
# as pontas das barras caem na grade (ou ficam onde estão, nas que passam do último pilar)
px = agrupar([c[0] for c in colunas] + [v for b in barras if b[0] == "x" for v in b[1:3]], 45)
py = agrupar([c[1] for c in colunas] + [v for b in barras if b[0] == "y" for v in b[1:3]], 45)

# cada coluna: os lances empilhados no mesmo (x, y) viram uma coluna só
porLugar = {}
for x, y, z0, z1 in colunas:
    chave = (gx[x], gy[y])
    a, b = porLugar.get(chave, (1e9, -1e9))
    porLugar[chave] = (min(a, z0), max(b, z1))
saida_colunas = [[x, y, r(a), r(b)] for (x, y), (a, b) in sorted(porLugar.items())]

# cada barra: as cópias (mesma linha, trechos que se sobrepõem) viram uma
linhas = {}
for eixo, a, b, fixo, z, raio in barras:
    f = (gy if eixo == "x" else gx)[fixo]
    p = px if eixo == "x" else py
    linhas.setdefault((eixo, f, gz[z]), []).append([p[a], p[b], raio])
saida_barras = []
for (eixo, f, z), trechos in sorted(linhas.items()):
    trechos.sort()
    juntos = []
    for a, b, raio in trechos:
        # a mesma barra repetida (início e fim iguais, a menos de 5 cm) fica uma vez só
        if juntos and abs(a - juntos[-1][0]) < 50 and abs(b - juntos[-1][1]) < 50:
            continue
        juntos.append([a, b, raio])
    for a, b, raio in juntos:
        if eixo == "x":
            saida_barras.append([r(a), f, z, r(b), f, z, round(raio)])
        else:
            saida_barras.append([f, r(a), z, f, r(b), z, round(raio)])

x0, x1, y0, y1, z0, z1 = arco[0]["bb"]
saida = {
    "colunas": saida_colunas,
    "barras": saida_barras,
    "arco": [r(x0), r(x1), r((y0 + y1) / 2), r(z0), r(z1)],
    "marca": [r((marca[0]["bb"][0] + marca[0]["bb"][1]) / 2), r((marca[0]["bb"][2] + marca[0]["bb"][3]) / 2),
              r(marca[0]["bb"][4]), r(max(marca[0]["bb"][1] - marca[0]["bb"][0], marca[0]["bb"][3] - marca[0]["bb"][2]) / 2)],
    "caixa": [r(min(p["bb"][i] for p in tubos + arco)) if i % 2 == 0 else r(max(p["bb"][i] for p in tubos + arco)) for i in range(6)],
}
Path(__file__).with_name("estrutura.json").write_text(json.dumps(saida))
print(len(pecas) - len(dentro), "sobras longe do brinquedo;", len(tubos), "tubos ->",
      len(saida_colunas), "colunas e", len(saida_barras), "barras; caixa (mm):", saida["caixa"])
