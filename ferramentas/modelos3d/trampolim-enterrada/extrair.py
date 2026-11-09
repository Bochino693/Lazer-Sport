"""Lê o .3ds do trampolim e guarda só as medidas da estrutura, em mm (estrutura.json).

    python3 extrair.py caminho/do/trampolim.3ds

O .3ds da fábrica tem 832 objetos (~20 mil faces): as quatro colunas, o
quadro de tubos de cima, a armação de aço da base (três módulos) e a da
parede inclinada, e centenas de parafusos e cantoneiras. O montar.js não
precisa de nada disso peça por peça -- a base fica coberta pelo caixote e a
parede pelo estofado --, só de ONDE cada coisa está: o centro e a altura das
colunas, o retângulo do quadro de cima, onde começa e acaba cada módulo, a
altura das camas e a linha da parede inclinada. É isso que sai daqui.

Usa o leitor de .3ds do ../brinquedao-modelo-2/ (ler_3ds.py).
"""
import json, sys

exec(open(__file__.replace('trampolim-enterrada/extrair.py', 'brinquedao-modelo-2/ler_3ds.py')).read().split("andar(0, len(dados), 0, {})")[0])
andar(0, len(dados), 0, {})

r = lambda v: int(round(v))
pecas = []
for o in objs:
    if 'bb' not in o or not o['f'] or not o['mats']:
        continue
    x0, x1, y0, y1, z0, z1 = o['bb']
    pecas.append({'mat': o['mats'][0], 'bb': (x0, x1, y0, y1, z0, z1), 'tam': (x1 - x0, y1 - y0, z1 - z0)})
escuras = [p for p in pecas if p['mat'] == '0135_Dar']   # o aço cinza-escuro
amarelas = [p for p in pecas if p['mat'] == '_0063_Gr']  # o quadro de cima (difusa 252, 219, 0)

# as quatro colunas: tubos de pé com quase 3 m
colunas = sorted(
    [r((p['bb'][0] + p['bb'][1]) / 2), r((p['bb'][2] + p['bb'][3]) / 2), max(0, r(p['bb'][4])), r(p['bb'][5]), r(p['tam'][0] / 2)]
    for p in escuras if p['tam'][2] > 2500 and p['tam'][0] > 90
)

# o quadro de cima: as linhas de centro dos quatro tubos amarelos
ao_longo = [p for p in amarelas if p['tam'][0] > p['tam'][1]]
de_lado = [p for p in amarelas if p['tam'][1] > p['tam'][0]]
meio = lambda p, i: (p['bb'][i] + p['bb'][i + 1]) / 2
quadro = {
    'x0': r(min(meio(p, 0) for p in de_lado)), 'x1': r(max(meio(p, 0) for p in de_lado)),
    'y0': r(min(meio(p, 2) for p in ao_longo)), 'y1': r(max(meio(p, 2) for p in ao_longo)),
    'z': r(sum(meio(p, 4) for p in amarelas) / len(amarelas)),
    'raio': r(sum(p['tam'][2] for p in amarelas) / len(amarelas) / 2),
}

# a base: as pernas de ~1 m (dos dois lados) dizem onde começa e acaba cada módulo
pernas = []  # [x0, x1] de cada perna; a da frente e a de trás do mesmo ponto viram uma
for p in sorted((p for p in escuras if 900 < p['tam'][2] < 1100 and p['bb'][4] < 10 and p['tam'][0] < 150), key=lambda p: p['bb'][0]):
    x0, x1 = p['bb'][0], p['bb'][1]
    if pernas and abs((x0 + x1) / 2 - sum(pernas[-1]) / 2) < 40:
        pernas[-1] = [min(pernas[-1][0], x0), max(pernas[-1][1], x1)]
    else:
        pernas.append([x0, x1])
# cada módulo tem as suas duas pernas (entre um módulo e o outro há uma
# folga de ~4 cm, coberta pela divisória amarela): em ordem, de duas em duas
modulos = [[r(pernas[i][0]), r(pernas[i + 1][1])] for i in range(0, len(pernas) - 1, 2)]
trilhos = [p for p in escuras if 940 < p['bb'][4] < 960 and p['tam'][2] < 60]
base = {
    'y0': r(min(p['bb'][2] for p in trilhos)), 'y1': r(max(p['bb'][3] for p in trilhos)),
    'z': r(max(p['bb'][5] for p in trilhos)),
}

# a parede inclinada: as duas vigas em diagonal (de baixo, na beira das
# camas, até o alto, junto da cabeceira) e os montantes de pé atrás delas
vigas = [p for p in escuras if p['tam'][2] > 1500 and p['tam'][0] > 400]
montantes = [p for p in escuras if p['tam'][2] > 2500 and p['tam'][0] < 60]
parede = {
    'x_baixo': r(max(p['bb'][1] for p in vigas)), 'z_baixo': r(min(p['bb'][4] for p in vigas)),
    'x_alto': r(min(p['bb'][0] for p in vigas)), 'z_alto': r(max(p['bb'][5] for p in vigas)),
    'x_atras': r(min(p['bb'][0] for p in montantes)),
}

saida = {
    'caixa': [r(min(p['bb'][i] for p in pecas)) if i % 2 == 0 else r(max(p['bb'][i] for p in pecas)) for i in range(6)],
    'colunas': colunas, 'quadro': quadro, 'modulos': modulos, 'base': base, 'parede': parede,
}
json.dump(saida, open(__file__.replace('extrair.py', 'estrutura.json'), 'w'), indent=1)
print(json.dumps(saida))
