"""Resume os objetos cinzas do trampo.3ds (a grade das camas, postes...). Usa o ../brinquedao-modelo-2/ler_3ds.py."""
import struct, sys, collections, json
exec(open(__file__.replace('espaco-esportivo-modelo-1/ler_parque.py', 'brinquedao-modelo-2/ler_3ds.py')).read().split("andar(0, len(dados), 0, {})")[0])
andar(0, len(dados), 0, {})
dim = [o for o in objs if o['mats'] and o['mats'][0] == '0134_Dim' and 'bb' in o]
# tamanhos dos objetos cinzas
tam = collections.Counter()
for o in dim:
    x0,x1,y0,y1,z0,z1 = o['bb']; dx,dy,dz = x1-x0,y1-y0,z1-z0
    tam[(round(dx/100)*100, round(dy/100)*100, round(dz/100)*100)] += 1
for k,v in tam.most_common(40): print(v, k)
print('---- maiores')
for o in sorted(dim, key=lambda o: -(o['bb'][1]-o['bb'][0])*(o['bb'][3]-o['bb'][2]))[:30]:
    print(o['nome'], o['f'], [round(v) for v in o['bb']])
