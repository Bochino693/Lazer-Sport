"""Lê um .3ds (blocos MAIN/EDIT/OBJECT/TRIMESH) e lista objetos, materiais e medidas.

    python ler_3ds.py arquivo.3ds
"""
import struct, sys, collections
dados = open(sys.argv[1], 'rb').read()
nomes = {0x4D4D:'MAIN',0x3D3D:'EDIT',0x4000:'OBJECT',0x4100:'TRIMESH',0x4110:'VERTS',0x4120:'FACES',0x4130:'FACEMAT',0x4140:'UV',0x4160:'MATRIX',0xAFFF:'MATERIAL',0xA000:'MATNAME',0xA200:'TEXMAP',0xA300:'MAPFILE',0xA010:'AMBIENT',0xA020:'DIFFUSE',0xA030:'SPECULAR',0x0100:'SCALE', 0x3D3E:'MESHVER'}
objs = []; mats = []; mapas = []
total_v = 0; total_f = 0
def cstr(off):
    fim = dados.index(b'\0', off); return dados[off:fim].decode('latin1'), fim + 1
def ler_cor(off, fim):
    # sub-chunks 0x0010 float rgb / 0x0011 byte rgb
    while off < fim:
        cid, clen = struct.unpack_from('<HI', dados, off)
        if cid == 0x0011: return tuple(dados[off+6:off+9])
        if cid == 0x0010: return tuple(int(x*255) for x in struct.unpack_from('<fff', dados, off+6))
        off += clen
    return None
def andar(off, fim, prof, ctx):
    global total_v, total_f
    while off < fim:
        cid, clen = struct.unpack_from('<HI', dados, off)
        corpo = off + 6
        if cid in (0x4D4D, 0x3D3D, 0x4100, 0xAFFF, 0xA200):
            if cid == 0xAFFF: ctx = {'mat': {}}; mats.append(ctx['mat'])
            andar(corpo, off + clen, prof + 1, ctx)
        elif cid == 0x4000:
            nome, p = cstr(corpo); o = {'nome': nome, 'v': 0, 'f': 0, 'mats': []}; objs.append(o)
            andar(p, off + clen, prof + 1, {'obj': o})
        elif cid == 0x4110:
            n = struct.unpack_from('<H', dados, corpo)[0]; ctx['obj']['v'] = n; total_v += n
            if 'bb' not in ctx['obj']:
                pts = struct.unpack_from('<%df' % (3*n), dados, corpo + 2)
                xs, ys, zs = pts[0::3], pts[1::3], pts[2::3]
                ctx['obj']['bb'] = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
        elif cid == 0x4120:
            n = struct.unpack_from('<H', dados, corpo)[0]; ctx['obj']['f'] = n; total_f += n
            andar(corpo + 2 + n * 8, off + clen, prof + 1, ctx)
        elif cid == 0x4130:
            nome, p = cstr(corpo); ctx['obj']['mats'].append(nome)
        elif cid == 0x4140:
            ctx['obj']['uv'] = True
        elif cid == 0xA000:
            ctx['mat']['nome'] = cstr(corpo)[0]
        elif cid == 0xA020:
            ctx['mat']['difusa'] = ler_cor(corpo, off + clen)
        elif cid == 0xA300:
            f = cstr(corpo)[0]; mapas.append(f); ctx['mat']['mapa'] = f
        off += clen
andar(0, len(dados), 0, {})
print('objetos', len(objs), 'vertices', total_v, 'faces', total_f, 'materiais', len(mats))
print('mapas', collections.Counter(mapas))
for m in mats: print('  MAT', m)
bb = [min(o['bb'][0] for o in objs if 'bb' in o), max(o['bb'][1] for o in objs if 'bb' in o), min(o['bb'][2] for o in objs if 'bb' in o), max(o['bb'][3] for o in objs if 'bb' in o), min(o['bb'][4] for o in objs if 'bb' in o), max(o['bb'][5] for o in objs if 'bb' in o)]
print('caixa', [round(x, 2) for x in bb])
c = collections.Counter(tuple(o['mats']) for o in objs)
for o in sorted(objs, key=lambda o: -o['f'])[:25]: print('  OBJ', o['nome'], o['v'], o['f'], o['mats'][:3], o.get('uv', False), [round(x,1) for x in o.get('bb', ())])
print('---- por material')
porm = collections.defaultdict(lambda: [0, 0, [1e9,-1e9,1e9,-1e9,1e9,-1e9]])
for o in objs:
    k = ','.join(o['mats']) or '(sem)'
    porm[k][0] += 1; porm[k][1] += o['f']
    if 'bb' in o:
        b = porm[k][2]; ob = o['bb']
        b[0]=min(b[0],ob[0]); b[1]=max(b[1],ob[1]); b[2]=min(b[2],ob[2]); b[3]=max(b[3],ob[3]); b[4]=min(b[4],ob[4]); b[5]=max(b[5],ob[5])
for k, (n, f, b) in porm.items(): print(k, n, 'objs', f, 'faces', [round(x) for x in b])
print('---- objetos grandes fora do padrão')
for o in objs:
    if o['f'] != 1416 and 'bb' in o: print(o['nome'], o['f'], o['mats'], [round(x) for x in o['bb']])
