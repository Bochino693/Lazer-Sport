"""Lê o .3ds do Brinquedão Ninja e guarda a estrutura (colunas, barras, corrimãos) em mm.

    python3 extrair.py caminho/do/estrutura.3ds      # escreve estrutura.json

O .3ds da fábrica tem ~270 mil faces (cada tubo com 1.416): aqui ele vira uma
lista leve, e o montar.js refaz cada peça no mesmo lugar e na mesma medida.
Os materiais do arquivo dizem o que é cada coisa:
  _15       colunas rosa/magenta (em três lances: 0-1,2 m, 1,2-2,25 m, 2,25-3,3 m)
  _1        barras laranja (o chão de cada andar, o corrimão de cima, as bordas)
  0065_Lim  as duas barras azuis de cima da rede em V (a 3 m)
  Line*     os corrimãos rosa das entradas da frente (piscina e camas elásticas)
"""
import json, sys
exec(open(__file__.replace('brinquedao-ninja/extrair.py', 'brinquedao-modelo-2/ler_3ds.py')).read().split("andar(0, len(dados), 0, {})")[0])
andar(0, len(dados), 0, {})
r = lambda v, q=10: int(round(v / q) * q)
colunas = {}; barras = set(); azuis = []; corrimaos = []
for o in objs:
    if 'bb' not in o or o['f'] < 50: continue
    x0, x1, y0, y1, z0, z1 = o['bb']; dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    m = o['mats'][0] if o['mats'] else '-'
    if o['nome'].startswith('Line'):
        # o corrimão da entrada: sobe da borda da cama e faz a curva para a direita
        corrimaos.append([r(x0), r(x1), r((y0 + y1) / 2), r(z0), r(z1)]); continue
    if m == '0065_Lim':
        azuis.append([r(x0), r((y0 + y1) / 2), r((z0 + z1) / 2), r(x1), r((y0 + y1) / 2), r((z0 + z1) / 2)]); continue
    if m not in ('_1', '_15'): continue  # as duas sapatas cinza (5 cm) e o plano solto do topo
    if dz > 300 and dx < 200 and dy < 200:
        # os três lances de cada coluna viram uma coluna só
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
    'barras_azuis': sorted(azuis),
    'corrimaos': sorted(corrimaos),
}
json.dump(saida, open(__file__.replace('extrair.py', 'estrutura.json'), 'w'))
print(len(saida['colunas']), 'colunas', len(saida['barras']), 'barras', len(azuis), 'barras azuis', len(corrimaos), 'corrimãos')
