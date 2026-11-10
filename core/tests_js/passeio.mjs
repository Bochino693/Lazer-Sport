// O PASSEIO POR DENTRO, conferido com a geometria de verdade de cada objeto
// (core/static/site/arena/caminhos.js x o .glb do site). Para cada amostra do
// caminho (a cada 6 cm, com a altura dos olhos daquele trecho e o quique da
// cama elástica), a menor distância dos olhos (a câmera) até um triângulo do
// objeto:
//   * em todo trecho, pelo menos FOLGA (a câmera nunca entra numa peça: o
//     plano de perto, a 5 cm, corta o que estiver mais perto que isso);
//   * nos túneis (tubo), pelo menos FOLGA_TUNEL, e no tobogã (os olhos no
//     eixo do tubo), FOLGA_TOBOGA: nada (coluna, barra, ferro, aro de junta)
//     passa por dentro do túnel por onde a câmera passa.
// node core/tests_js/passeio.mjs [ids...]  -- sai com 1 e a lista dos trechos que encostam.
// Com --relatorio, imprime todos os trechos mais perto que 15 cm (para ajustar).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const ESTATICO = path.join(AQUI, "..", "static");
const { CAMINHOS, MODOS_DO_PASSEIO, amostrarCaminho } = await import(pathToFileURL(path.join(ESTATICO, "site/arena/caminhos.js")));

const FOLGA = 0.1;
const FOLGA_TUNEL = 0.12;
// no tobogã fechado os olhos vão no eixo do tubo (raio de 25 a 29 cm): nada a menos de 20 cm dele
const FOLGA_TOBOGA = 0.2;
// cair na piscina de bolinhas ou de espuma é afundar nelas: ali basta não entrar no cubo (a bola)
const FOLGA_CAIR = 0.05;
// a passagem estreita marcada no caminho ({ rente: true }: entre a beira de um piso e a de outro, a
// cabeça passa no meio): o plano de perto (5 cm) não corta nada
const FOLGA_RENTE = 0.075;
const TUNEIS = new Set(["tubo", "escorregar"]);
// o que é para afundar dentro (as bolinhas, os cubos de espuma): perto delas, em qualquer trecho, vale a folga de cair
const PISCINA = new Set(["bolinhas", "cubos-de-espuma"]);
const argumentos = process.argv.slice(2);
const relatorio = argumentos.includes("--relatorio");
const pedidos = argumentos.filter((a) => !a.startsWith("--"));

/* ---------------------------------------------------------------- o .glb, lido à mão
   Só o que estes arquivos usam: malhas de triângulos, com a posição em float
   ou quantizada (KHR_mesh_quantization, a escala no nó), índices, e nós com
   matriz ou TRS. */
function lerGlb(arquivo) {
  const b = fs.readFileSync(arquivo);
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  const tamanhoJson = dv.getUint32(12, true);
  const json = JSON.parse(b.subarray(20, 20 + tamanhoJson).toString("utf8"));
  const inicioBin = 20 + tamanhoJson + 8;
  const bin = new DataView(b.buffer, b.byteOffset + inicioBin, dv.getUint32(20 + tamanhoJson, true));
  const ler = (indice) => {
    const ac = json.accessors[indice];
    const bv = json.bufferViews[ac.bufferView];
    const comp = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 }[ac.componentType];
    const n = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[ac.type];
    const passo = bv.byteStride || comp * n;
    const base = (bv.byteOffset || 0) + (ac.byteOffset || 0);
    const leitor = {
      5120: (o) => bin.getInt8(o), 5121: (o) => bin.getUint8(o), 5122: (o) => bin.getInt16(o, true),
      5123: (o) => bin.getUint16(o, true), 5125: (o) => bin.getUint32(o, true), 5126: (o) => bin.getFloat32(o, true),
    }[ac.componentType];
    const norm = ac.normalized ? { 5120: (v) => Math.max(v / 127, -1), 5121: (v) => v / 255, 5122: (v) => Math.max(v / 32767, -1), 5123: (v) => v / 65535 }[ac.componentType] : (v) => v;
    const saida = new Float64Array(ac.count * n);
    for (let i = 0; i < ac.count; i++) for (let k = 0; k < n; k++) saida[i * n + k] = norm(leitor(base + i * passo + k * comp));
    return saida;
  };
  const mult = (a, c) => {
    const r = new Array(16).fill(0);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 4; k++) r[j * 4 + i] += a[k * 4 + i] * c[j * 4 + k];
    return r;
  };
  const trs = (no) => {
    if (no.matrix) return no.matrix;
    const [x, y, z, w] = no.rotation || [0, 0, 0, 1];
    const [sx, sy, sz] = no.scale || [1, 1, 1];
    const [tx, ty, tz] = no.translation || [0, 0, 0];
    return [
      (1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + z * w) * sx, 2 * (x * z - y * w) * sx, 0,
      2 * (x * y - z * w) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + x * w) * sy, 0,
      2 * (x * z + y * w) * sz, 2 * (y * z - x * w) * sz, (1 - 2 * (x * x + y * y)) * sz, 0,
      tx, ty, tz, 1,
    ];
  };
  const tris = [];
  const nomes = [];
  const visitar = (indice, pai) => {
    const no = json.nodes[indice];
    const m = mult(pai, trs(no));
    if (no.mesh !== undefined) {
      for (const prim of json.meshes[no.mesh].primitives) {
        if ((prim.mode ?? 4) !== 4) continue;
        const pos = ler(prim.attributes.POSITION);
        const nome = prim.material !== undefined ? json.materials[prim.material].name || `material-${prim.material}` : json.meshes[no.mesh].name || "";
        const k = nomes.push(nome) - 1;
        const v = (i) => {
          const x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
          return [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]];
        };
        const idx = prim.indices !== undefined ? ler(prim.indices) : null;
        const total = idx ? idx.length : pos.length / 3;
        for (let t = 0; t + 2 < total; t += 3) {
          const [a, b2, c] = idx ? [idx[t], idx[t + 1], idx[t + 2]] : [t, t + 1, t + 2];
          tris.push([...v(a), ...v(b2), ...v(c), k]);
        }
      }
    }
    for (const filho of no.children || []) visitar(filho, m);
  };
  const identidade = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  for (const raiz of json.scenes[json.scene || 0].nodes) visitar(raiz, identidade);
  // como na Arena: o objeto pousa no chão (a caixa dele começa em y = 0)
  let menorY = Infinity;
  for (const t of tris) menorY = Math.min(menorY, t[1], t[4], t[7]);
  for (const t of tris) { t[1] -= menorY; t[4] -= menorY; t[7] -= menorY; }
  return { tris, nomes };
}

/* ---------------------------------------------------------------- a menor distância (um hash de 25 cm) */
function indexar(tris) {
  const C = 0.25;
  const hash = new Map();
  tris.forEach((t, n) => {
    const lo = [0, 1, 2].map((e) => Math.floor(Math.min(t[e], t[e + 3], t[e + 6]) / C));
    const hi = [0, 1, 2].map((e) => Math.floor(Math.max(t[e], t[e + 3], t[e + 6]) / C));
    if ((hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1) > 6000) return; // o piso inteiro: os pés pisam nele
    for (let i = lo[0]; i <= hi[0]; i++) for (let j = lo[1]; j <= hi[1]; j++) for (let k = lo[2]; k <= hi[2]; k++) {
      const c = `${i},${j},${k}`;
      if (!hash.has(c)) hash.set(c, []);
      hash.get(c).push(n);
    }
  });
  return { C, hash };
}

/** O ponto do triângulo mais perto de p (Ericson, "Real-Time Collision Detection"). */
function distanciaAoTriangulo(p, t) {
  const a = [t[0], t[1], t[2]], b = [t[3], t[4], t[5]], c = [t[6], t[7], t[8]];
  const sub = (u, v) => [u[0] - v[0], u[1] - v[1], u[2] - v[2]];
  const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
  const ab = sub(b, a), ac = sub(c, a), ap = sub(p, a);
  const dist = (q) => Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
  const d1 = dot(ab, ap), d2 = dot(ac, ap);
  if (d1 <= 0 && d2 <= 0) return dist(a);
  const bp = sub(p, b);
  const d3 = dot(ab, bp), d4 = dot(ac, bp);
  if (d3 >= 0 && d4 <= d3) return dist(b);
  const vc = d1 * d4 - d3 * d2;
  if (vc <= 0 && d1 >= 0 && d3 <= 0) { const v = d1 / (d1 - d3); return dist([a[0] + ab[0] * v, a[1] + ab[1] * v, a[2] + ab[2] * v]); }
  const cp = sub(p, c);
  const d5 = dot(ab, cp), d6 = dot(ac, cp);
  if (d6 >= 0 && d5 <= d6) return dist(c);
  const vb = d5 * d2 - d1 * d6;
  if (vb <= 0 && d2 >= 0 && d6 <= 0) { const w = d2 / (d2 - d6); return dist([a[0] + ac[0] * w, a[1] + ac[1] * w, a[2] + ac[2] * w]); }
  const va = d3 * d6 - d5 * d4;
  if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) {
    const w = (d4 - d3) / (d4 - d3 + (d5 - d6));
    return dist([b[0] + (c[0] - b[0]) * w, b[1] + (c[1] - b[1]) * w, b[2] + (c[2] - b[2]) * w]);
  }
  const den = 1 / (va + vb + vc);
  const v = vb * den, w = vc * den;
  return dist([a[0] + ab[0] * v + ac[0] * w, a[1] + ab[1] * v + ac[1] * w, a[2] + ab[2] * v + ac[2] * w]);
}

/** O triângulo que mais "encosta": a menor distância menos a folga dele (a da piscina é menor). */
function maisPerto(indice, tris, p, raio, folgaDe = () => 0) {
  const { C, hash } = indice;
  let melhor = raio;
  let margem = Infinity;
  let quem = -1;
  const vistos = new Set();
  const lo = p.map((x) => Math.floor((x - raio) / C));
  const hi = p.map((x) => Math.floor((x + raio) / C));
  for (let i = lo[0]; i <= hi[0]; i++) for (let j = lo[1]; j <= hi[1]; j++) for (let k = lo[2]; k <= hi[2]; k++) {
    const lista = hash.get(`${i},${j},${k}`);
    if (!lista) continue;
    for (const n of lista) {
      if (vistos.has(n)) continue;
      vistos.add(n);
      const d = distanciaAoTriangulo(p, tris[n]);
      const m = d - folgaDe(tris[n][9]);
      if (m < margem) { margem = m; melhor = d; quem = tris[n][9]; }
    }
  }
  return [melhor, quem, margem];
}

/* ---------------------------------------------------------------- cada objeto com caminho próprio */
const problemas = [];
const ids = pedidos.length ? pedidos : Object.keys(CAMINHOS);
for (const id of ids) {
  const arquivo = path.join(ESTATICO, "site/arena/modelos", `${id}.glb`);
  if (!fs.existsSync(arquivo)) { problemas.push(`${id}: sem o .glb`); continue; }
  const { tris, nomes } = lerGlb(arquivo);
  const indice = indexar(tris);
  const pontos = CAMINHOS[id]().map(([x, y, z, modo = "andar", extras = {}]) => ({ p: [x, y, z], modo, ...extras }));
  const { amostras } = amostrarCaminho(pontos);
  const trechos = [];
  let atual = null;
  // onde começa e acaba cada descida de tobogã (a boca e a saída valem como túnel comum)
  const borda = amostras.map(() => false);
  for (let i = 0; i < amostras.length; i++) {
    if (amostras[i].modo !== "escorregar" || (i && amostras[i - 1].modo === "escorregar")) continue;
    let j = i;
    while (j + 1 < amostras.length && amostras[j + 1].modo === "escorregar") j++;
    for (let k = i; k <= j; k++) borda[k] = amostras[k].s - amostras[i].s < 0.8 || amostras[j].s - amostras[k].s < 0.8;
  }
  for (const [n, q] of amostras.entries()) {
    const jeito = MODOS_DO_PASSEIO[q.modo] || MODOS_DO_PASSEIO.andar;
    // os olhos, e no quique da cama elástica o alto do pulo também
    const alturas = [q.olhos];
    if (jeito.quique) alturas.push(q.olhos + jeito.quique / 2, q.olhos + jeito.quique);
    if (["rede", "viga", "tirolesa"].includes(q.modo)) alturas.push(q.olhos + 0.04, q.olhos - 0.04);
    if (["andar", "subir"].includes(q.modo)) alturas.push(q.olhos + 0.03);
    const limiteDoModo = q.rente ? FOLGA_RENTE : q.modo === "escorregar" && !borda[n] ? FOLGA_TOBOGA : TUNEIS.has(q.modo) ? FOLGA_TUNEL : q.modo === "cair" ? FOLGA_CAIR : FOLGA;
    const folgaDe = (k) => (PISCINA.has(nomes[k]) ? Math.min(FOLGA_CAIR, limiteDoModo) : limiteDoModo);
    let d = Infinity;
    let quem = -1;
    let margem = Infinity;
    for (const h of alturas) {
      const [dh, qh, mh] = maisPerto(indice, tris, [q.p[0], q.p[1] + h, q.p[2]], 0.3, folgaDe);
      if (mh < margem) { margem = mh; d = dh; quem = qh; }
    }
    const limite = quem >= 0 ? folgaDe(quem) : limiteDoModo;
    const ruim = relatorio ? d < 0.15 : d < limite;
    if (ruim) {
      if (!atual || atual.modo !== q.modo) {
        atual = { modo: q.modo, s0: q.s, s1: q.s, min: d, quem: new Set(), p: [q.p[0], q.p[1] + q.olhos, q.p[2]], limite };
        trechos.push(atual);
      }
      atual.s1 = q.s;
      if (d < atual.min) { atual.min = d; atual.p = [q.p[0], q.p[1] + q.olhos, q.p[2]]; }
      if (quem >= 0) atual.quem.add(nomes[quem]);
    } else {
      atual = null;
    }
  }
  const p3 = (p) => p.map((x) => x.toFixed(2)).join(", ");
  for (const t of trechos) {
    const texto = `${id}: ${t.modo} de ${t.s0.toFixed(2)} a ${t.s1.toFixed(2)} m do caminho -- ${t.min.toFixed(3)} m de ${[...t.quem].join(", ")} (olhos em ${p3(t.p)})`;
    if (t.min < t.limite) problemas.push(texto);
    else if (relatorio) console.log("  (perto) " + texto);
  }
  if (relatorio) console.log(`${id}: ${amostras.length} amostras, ${tris.length} triângulos, ${trechos.filter((t) => t.min < t.limite).length} trechos encostando`);
}
if (problemas.length) {
  console.log(problemas.join("\n"));
  process.exit(1);
}
console.log("ok: os olhos do passeio não entram em nenhuma peça e nada atravessa os túneis");
