"""Lê o .3ds e guarda a estrutura (colunas, barras e a rede) em mm, sem duplicatas."""
import json, sys
exec(open(__file__.replace('extrair.py', 'ler_3ds.py')).read().split("andar(0, len(dados), 0, {})")[0])
andar(0, len(dados), 0, {})
r = lambda v, q=10: int(round(v / q) * q)
colunas = {}; barras = set(); rede = []
for o in objs:
    if 'bb' not in o or o['f'] < 50: continue
    x0, x1, y0, y1, z0, z1 = o['bb']; dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    m = o['mats'][0] if o['mats'] else '-'
    if m == '_0101_Co':
        rede.append([r(x0), r(x1), r(y0), r(y1), r(z0), r(z1)]); continue
    if dz > 300 and dx < 200 and dy < 200:
        chave = (r((x0 + x1) / 2, 40), r((y0 + y1) / 2, 40))
        a, b = colunas.get(chave, (1e9, -1e9))
        colunas[chave] = (min(a, z0), max(b, z1))
    elif dx > 300 and dy < 200 and dz < 200:
        barras.add(((r(x0), r((y0 + y1) / 2), r((z0 + z1) / 2)), (r(x1), r((y0 + y1) / 2), r((z0 + z1) / 2))))
    elif dy > 300 and dx < 200 and dz < 200:
        barras.add(((r((x0 + x1) / 2), r(y0), r((z0 + z1) / 2)), (r((x0 + x1) / 2), r(y1), r((z0 + z1) / 2))))
saida = {
    'colunas': [[x, y, max(0, r(a)), r(b)] for (x, y), (a, b) in sorted(colunas.items())],
    'barras': sorted([list(a) + list(b) for a, b in barras]),
    'rede': rede,
}
json.dump(saida, open(__file__.replace('extrair.py', 'estrutura.json'), 'w'))
print(len(saida['colunas']), 'colunas', len(saida['barras']), 'barras', len(rede), 'peças de rede')
