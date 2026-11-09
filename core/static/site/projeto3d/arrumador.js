/* ======================================================================
   O ARRUMADOR do "Monte seu espaço" (na Arena 3D, arena.html;
   as regras de cada área e de cada máquina vêm do servidor, em
   core/projeto3d.py, para o painel e o site falarem a mesma língua).

   O cliente diz SÓ o tamanho do lugar (largura × comprimento e, se quiser,
   o pé-direito) e escolhe: o modelo do espaço (o principal), as outras
   áreas e as máquinas. O arrumador põe tudo na planta e diz o que coube:

     * a ENTRADA fica no meio da parede da frente, com um hall livre;
     * primeiro o PRINCIPAL (no fundo, no meio), depois as outras áreas e
       os brinquedos grandes (nos cantos; a área baby perto da entrada),
       depois as máquinas que ficam no meio (mesa de hockey, pebolim,
       carrossel) e por fim as de PAREDE (fliperama, basquete, boliche...),
       de costas para a parede, lado a lado, as iguais juntas;
     * cada uma ocupa o CORPO (a medida dela) e a ZONA: o corpo mais o
       lugar de quem joga na frente (ou a faixa de segurança em volta dos
       brinquedões e das camas). Zona não se sobrepõe a nada;
     * depois de cada uma, confere a PASSAGEM: da entrada até a zona de
       cada coisa tem de haver um corredor de 1,20 m (a rota acessível da
       NBR 9050). A que fecharia a passagem tenta outro lugar; sem lugar,
       fica de fora, com o motivo;
     * as áreas SOB MEDIDA (o brinquedão, o espaço esportivo...) entram no
       tamanho mínimo e, no fim, crescem no que sobrou (o principal até o
       máximo, as outras até o ideal), sem fechar passagem nenhuma.

   É um rascunho para conversar com o cliente: o projeto final segue a
   norma de playgrounds (ABNT NBR 16071) e a engenharia da fábrica.

   Tudo aqui é cálculo (nada de three.js): roda igual no navegador, no
   painel e nos testes (sistema_interno/tests_js/... via node).
   ====================================================================== */

export const REGRAS = {
  corredor: 1.2, // a passagem até cada coisa (NBR 9050: rota acessível de 1,20 m)
  parede: 0.1, // a folga atrás da máquina (ventilação e tomada)
  ladoMinimo: 0.08, // metade da folga entre duas máquinas lado a lado
  porta: 1.6, // o vão da entrada
  hall: 2.2, // o fundo do hall livre na entrada
  ladoDaPorta: 0.8, // o livre de cada lado da porta, no hall
  folgaTeto: 0.15, // o que sobra entre o alto do brinquedo e o teto
  passoCrescer: 0.25,
};

const EPS = 1e-6;
const arred = (v) => Math.round(v * 1000) / 1000;
export const metros = (v) => (Math.round(v * 100) / 100).toFixed(2).replace(".", ",");

/* ---------------------------------------------------------------- retângulos */
const ret = (x0, z0, x1, z1) => ({ x0, z0, x1, z1 });
const cruza = (a, b) => a.x0 < b.x1 - EPS && b.x0 < a.x1 - EPS && a.z0 < b.z1 - EPS && b.z0 < a.z1 - EPS;
const cabeEm = (a, s) => a.x0 >= s.x0 - EPS && a.x1 <= s.x1 + EPS && a.z0 >= s.z0 - EPS && a.z1 <= s.z1 + EPS;
const crescer = (a, m) => ret(a.x0 - m, a.z0 - m, a.x1 + m, a.z1 + m);
const larg = (a) => a.x1 - a.x0;
const fundo = (a) => a.z1 - a.z0;

/** O retângulo local (frente em +z) girado de r graus (0, 90, 180, 270) e posto em (x, z). */
function noMundo(l, r, x, z) {
  switch (((r % 360) + 360) % 360) {
    case 90: return ret(x + l.z0, z - l.x1, x + l.z1, z - l.x0);
    case 180: return ret(x - l.x1, z - l.z1, x - l.x0, z - l.z0);
    case 270: return ret(x - l.z1, z + l.x0, x - l.z0, z + l.x1);
    default: return ret(x + l.x0, z + l.z0, x + l.x1, z + l.z1);
  }
}

/** Quanto da borda de `a` encosta na sala e nas zonas já postas (0 a 1). */
function toque(a, sala, outras) {
  let t = 0;
  if (Math.abs(a.x0 - sala.x0) < 0.02) t += fundo(a);
  if (Math.abs(a.x1 - sala.x1) < 0.02) t += fundo(a);
  if (Math.abs(a.z0 - sala.z0) < 0.02) t += larg(a);
  if (Math.abs(a.z1 - sala.z1) < 0.02) t += larg(a);
  for (const o of outras) {
    const sobreZ = Math.max(0, Math.min(a.z1, o.z1) - Math.max(a.z0, o.z0));
    const sobreX = Math.max(0, Math.min(a.x1, o.x1) - Math.max(a.x0, o.x0));
    if (Math.abs(a.x0 - o.x1) < 0.03 || Math.abs(a.x1 - o.x0) < 0.03) t += sobreZ;
    if (Math.abs(a.z0 - o.z1) < 0.03 || Math.abs(a.z1 - o.z0) < 0.03) t += sobreX;
  }
  return t / (2 * (larg(a) + fundo(a)));
}

function sorteio(semente) {
  let a = (Number(semente) >>> 0) || 1;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------------------------------------------------------------- a passagem */
/**
 * A grade da passagem: o centro de quem anda tem de ficar a meio corredor
 * (0,60 m) de toda zona e de toda parede. `livre` marca esses centros; a
 * busca a partir do hall diz até onde se chega.
 */
class Passagem {
  constructor(sala, hall, corredor) {
    const maior = Math.max(larg(sala), fundo(sala));
    this.g = maior <= 40 ? 0.1 : maior <= 80 ? 0.2 : 0.3;
    this.sala = sala;
    this.hall = hall;
    this.meio = corredor / 2 - this.g / 2;
    this.nx = Math.max(1, Math.round(larg(sala) / this.g));
    this.nz = Math.max(1, Math.round(fundo(sala) / this.g));
    this.base = new Uint8Array(this.nx * this.nz);
    // as paredes (a da frente tem o vão da porta: por ali se entra)
    for (let k = 0; k < this.nz; k++) {
      for (let i = 0; i < this.nx; i++) {
        const x = sala.x0 + (i + 0.5) * this.g, z = sala.z0 + (k + 0.5) * this.g;
        const perto = x - sala.x0 < this.meio || sala.x1 - x < this.meio || z - sala.z0 < this.meio
          || (sala.z1 - z < this.meio && !(x >= hall.x0 + this.meio && x <= hall.x1 - this.meio));
        this.base[k * this.nx + i] = perto ? 0 : 1;
      }
    }
  }
  _faixa(r) {
    const g = this.g, s = this.sala;
    return [
      Math.max(0, Math.ceil((r.x0 - s.x0) / g - 0.5)), Math.min(this.nx - 1, Math.floor((r.x1 - s.x0) / g - 0.5)),
      Math.max(0, Math.ceil((r.z0 - s.z0) / g - 0.5)), Math.min(this.nz - 1, Math.floor((r.z1 - s.z0) / g - 0.5)),
    ];
  }
  /** Os centros alcançados a partir do hall, com estas zonas no caminho. */
  alcance(zonas) {
    const livre = this.base.slice();
    for (const z of zonas) {
      const [i0, i1, k0, k1] = this._faixa(crescer(z, this.meio));
      if (i1 >= i0) for (let k = k0; k <= k1; k++) livre.fill(0, k * this.nx + i0, k * this.nx + i1 + 1);
    }
    const visto = new Uint8Array(livre.length);
    const fila = new Int32Array(livre.length);
    let ini = 0, fim = 0;
    const [h0, h1, hk0, hk1] = this._faixa(this.hall);
    for (let k = hk0; k <= hk1; k++) {
      for (let i = h0; i <= h1; i++) {
        const c = k * this.nx + i;
        if (livre[c] && !visto[c]) { visto[c] = 1; fila[fim++] = c; }
      }
    }
    while (ini < fim) {
      const c = fila[ini++];
      const i = c % this.nx, k = (c / this.nx) | 0;
      if (i > 0 && livre[c - 1] && !visto[c - 1]) { visto[c - 1] = 1; fila[fim++] = c - 1; }
      if (i < this.nx - 1 && livre[c + 1] && !visto[c + 1]) { visto[c + 1] = 1; fila[fim++] = c + 1; }
      if (k > 0 && livre[c - this.nx] && !visto[c - this.nx]) { visto[c - this.nx] = 1; fila[fim++] = c - this.nx; }
      if (k < this.nz - 1 && livre[c + this.nx] && !visto[c + this.nx]) { visto[c + this.nx] = 1; fila[fim++] = c + this.nx; }
    }
    return visto;
  }
  /** Chega-se à zona? Algum centro alcançado encosta nela (a meio corredor, com a tolerância da grade). */
  chega(visto, zona) {
    const [i0, i1, k0, k1] = this._faixa(crescer(zona, this.meio + this.g * 1.6));
    for (let k = k0; k <= k1; k++) {
      for (let i = i0; i <= i1; i++) if (visto[k * this.nx + i]) return true;
    }
    return false;
  }
}

/* ---------------------------------------------------------------- o que entra */
/**
 * As peças do arrumador, a partir da escolha do cliente.
 * `escolha`: { principal: {tipo:"area", area} | {tipo:"item", id} | null,
 *              areas: ["baby", ...], itens: [{id, qtd}], semente }
 * `catalogo`: { areas: {chave: {...}}, itens: [{id, nome, desenho, tipo, medidas:[h,w,d], uso, parede}] }
 */
function pecasDaEscolha(escolha, catalogo) {
  const pecas = [];
  const porId = new Map((catalogo.itens || []).map((i) => [String(i.id), i]));
  const areaPeca = (chave, principal) => {
    const a = (catalogo.areas || {})[chave];
    if (!a) return null;
    // o porte que o cliente escolheu (compacto, médio, grande): o mínimo e o ideal são os dele, e
    // ela cresce só até o mínimo do porte de cima (escolheu o compacto, fica compacto)
    const portes = a.portes || [];
    const i = portes.findIndex((p) => p.chave === ((escolha.opcoes || {})[chave] || {}).porte);
    const porte = i >= 0 ? portes[i] : null;
    const min = porte ? porte.min : a.min, ideal = porte ? porte.ideal : a.ideal;
    const max = porte && portes[i + 1] ? portes[i + 1].min : a.max;
    return {
      chave: (principal ? "principal-" : "area-") + chave, ref: chave, nome: a.nome, tipo: "area", area: chave, principal,
      w: min[0], d: min[1], h: a.pe_direito_minimo || 0, flex: true, min, ideal, max,
      seg: a.seguranca || 0, uso: { frente: a.seguranca || 0, tras: a.seguranca || 0, lados: a.seguranca || 0 },
      prefere: principal ? "principal" : (a.prefere || "canto"),
    };
  };
  const itemPeca = (item, n, principal) => {
    const [h, w, d] = (item.medidas || []).map(Number);
    const uso = item.uso || {};
    const todos = Number(uso.todos) || 0;
    const parede = !!item.parede;
    return {
      chave: (principal ? "principal-" : "item-") + item.id + "-" + n, ref: String(item.id), nome: item.nome, tipo: item.tipo || "maquina",
      desenho: item.desenho, principal, w: w || 1, d: d || 1, h: h || 1.8, flex: false,
      uso: {
        frente: Math.max(todos, Number(uso.frente) || 0),
        tras: Math.max(todos, Number(uso.tras) || 0),
        lados: Math.max(todos, Number(uso.lados) || 0, parede ? REGRAS.ladoMinimo : 0),
      },
      parede,
      prefere: principal ? "principal" : (item.tipo === "grande" ? "canto" : parede ? "parede" : "meio"),
    };
  };
  const p = escolha.principal;
  if (p && p.tipo === "area") {
    const a = areaPeca(p.area, true);
    if (a) pecas.push(a);
  } else if (p && p.tipo === "item" && porId.has(String(p.id))) {
    pecas.push(itemPeca(porId.get(String(p.id)), 1, true));
  }
  const itens = [];
  for (const chave of escolha.areas || []) {
    if (p && p.tipo === "area" && p.area === chave) continue;
    const a = areaPeca(chave, false);
    if (a) itens.push(a);
  }
  for (const { id, qtd } of escolha.itens || []) {
    const item = porId.get(String(id));
    if (!item) continue;
    const n = Math.max(0, Math.min(30, Math.round(Number(qtd) || 0)));
    for (let k = 1; k <= n; k++) itens.push(itemPeca(item, k, false));
  }
  // as áreas e os grandes primeiro, depois os do meio, depois os de parede; em cada um, o maior
  // primeiro (as unidades da mesma máquina seguem juntas: lado a lado na parede)
  const ordem = { grande: 0, meio: 1, parede: 2 };
  const peso = (x) => (x.tipo === "grande" || x.tipo === "area" ? "grande" : x.parede ? "parede" : "meio");
  const zonaArea = (x) => (x.flex ? x.ideal[0] * x.ideal[1] : (x.w + 2 * x.uso.lados) * (x.d + x.uso.frente + x.uso.tras));
  itens.sort((a, b) => ordem[peso(a)] - ordem[peso(b)] || zonaArea(b) - zonaArea(a) || (a.ref < b.ref ? -1 : a.ref > b.ref ? 1 : 0)
    || a.chave.localeCompare(b.chave, "en", { numeric: true }));
  return pecas.concat(itens);
}

/** O corpo e a zona (no local, frente em +z) de uma peça. */
function locais(p) {
  const corpo = ret(-p.w / 2, -p.d / 2, p.w / 2, p.d / 2);
  const zona = ret(-p.w / 2 - p.uso.lados, -p.d / 2 - p.uso.tras, p.w / 2 + p.uso.lados, p.d / 2 + p.uso.frente);
  return { corpo, zona };
}

/* ---------------------------------------------------------------- os lugares possíveis */
function candidatos(p, sala, postos, hall) {
  const { zona: zl } = locais(p);
  const lista = [];
  const bordas = (eixo) => {
    const v = new Set();
    for (const o of postos) { v.add(eixo === "x" ? o.zona.x1 : o.zona.z1); v.add(eixo === "x" ? o.zona.x0 : o.zona.z0); }
    v.add(eixo === "x" ? hall.x1 : hall.z1);
    v.add(eixo === "x" ? hall.x0 : hall.z0);
    return [...v];
  };
  const xs = bordas("x"), zs = bordas("z");
  if (p.parede) {
    // de costas para cada parede: 0 = a do fundo, 90 = a da esquerda, 270 = a da direita, 180 = a da frente
    for (const r of [0, 90, 270, 180]) {
      const base = noMundo(zl, r, 0, 0);
      const zw = larg(base), zd = fundo(base);
      // a zona encosta na parede pela parte de trás: o corpo fica a "parede" (0,10 m) dela
      const atras = REGRAS.parede - p.uso.tras;
      let fixo, ao;
      if (r === 0) { fixo = { z0: sala.z0 + atras }; ao = "x"; }
      else if (r === 180) { fixo = { z0: sala.z1 - atras - zd }; ao = "x"; }
      else if (r === 90) { fixo = { x0: sala.x0 + atras }; ao = "z"; }
      else { fixo = { x0: sala.x1 - atras - zw }; ao = "z"; }
      const inicio = ao === "x" ? [sala.x0, sala.x1 - zw, ...xs, ...xs.map((v) => v - zw)] : [sala.z0, sala.z1 - zd, ...zs, ...zs.map((v) => v - zd)];
      for (const v of inicio) {
        const z0 = ao === "x" ? fixo.z0 : v, x0 = ao === "x" ? v : fixo.x0;
        lista.push({ r, x0, z0, zw, zd, parede: r });
      }
    }
  } else {
    const giros = p.flex ? [0] : (Math.abs(p.w - p.d) < 0.01 && p.uso.frente === p.uso.lados && p.uso.tras === p.uso.lados) ? [0] : [0, 90];
    for (const r of giros) {
      const base = noMundo(zl, r, 0, 0);
      const zw = larg(base), zd = fundo(base);
      const x0s = [sala.x0, sala.x1 - zw, (sala.x0 + sala.x1) / 2 - zw / 2, ...xs, ...xs.map((v) => v - zw)];
      const z0s = [sala.z0, sala.z1 - zd, ...zs, ...zs.map((v) => v - zd)];
      for (const x0 of x0s) for (const z0 of z0s) lista.push({ r, x0, z0, zw, zd });
    }
  }
  // a peça posta pela zona: o centro do corpo sai da diferença entre o canto da zona e o do local
  return lista.map((c) => {
    const base = noMundo(zl, c.r, 0, 0);
    const x = c.x0 - base.x0, z = c.z0 - base.z0;
    const { corpo, zona } = locais(p);
    return { r: c.r, x: arred(x), z: arred(z), corpo: noMundo(corpo, c.r, x, z), zona: noMundo(zona, c.r, x, z), parede: c.parede };
  });
}

function nota(p, c, sala, postos, rnd) {
  const W = larg(sala), D = fundo(sala);
  const cx = (c.zona.x0 + c.zona.x1) / 2, cz = (c.zona.z0 + c.zona.z1) / 2;
  const fundoRel = (cz - sala.z0) / D; // 0 no fundo, 1 na frente
  // encostar (na parede e nos outros) aproveita o espaço; o principal, porém, fica no meio do
  // fundo, para as duas paredes do lado sobrarem para as máquinas
  let s = toque(c.zona, sala, postos.map((o) => o.zona)) * (p.prefere === "principal" ? 0.3 : 1.2);
  if (p.prefere === "principal") s += 1.4 - (2 * Math.abs(cx - (sala.x0 + sala.x1) / 2)) / W - fundoRel * 1.2;
  else if (p.prefere === "perto_da_entrada") s += fundoRel * 1.2 - Math.abs(cx - (sala.x0 + sala.x1) / 2) / W * 0.2;
  else if (p.prefere === "canto") s += (1 - fundoRel) * 0.6 + Math.abs(cx - (sala.x0 + sala.x1) / 2) / W * 0.4;
  else if (p.prefere === "meio") s += 0.3 - fundoRel * 0.2;
  else if (p.prefere === "parede") {
    s += { 0: 0.6, 90: 0.45, 270: 0.45, 180: 0.15 }[c.parede] || 0;
    // as iguais juntas
    for (const o of postos) {
      if (o.ref === p.ref && o.parede === c.parede) {
        const perto = Math.abs(c.zona.x0 - o.zona.x1) < 0.03 || Math.abs(c.zona.x1 - o.zona.x0) < 0.03
          || Math.abs(c.zona.z0 - o.zona.z1) < 0.03 || Math.abs(c.zona.z1 - o.zona.z0) < 0.03;
        if (perto) s += 0.8;
      }
    }
  }
  return s + rnd() * 0.06;
}

/* ---------------------------------------------------------------- crescer as áreas sob medida */
function crescerArea(p, sala, postos, hall, passagem, alvo) {
  const outras = postos.filter((o) => o !== p);
  const seg = p.seg, passo = REGRAS.passoCrescer;
  const [maxW, maxD] = alvo;
  const corpoDe = (z) => ret(z.x0 + seg, z.z0 + seg, z.x1 - seg, z.z1 - seg);
  // um lado a mais: dentro da sala, fora do hall e das outras, sem passar da medida (de qualquer lado)
  const tentar = (zona, lado) => {
    const nova = { ...zona };
    nova[lado] += lado.endsWith("0") ? -passo : passo;
    const c = corpoDe(nova);
    const w = larg(c), d = fundo(c);
    const cabe = Math.max(w, d) <= Math.max(maxW, maxD) + EPS && Math.min(w, d) <= Math.min(maxW, maxD) + EPS;
    return cabe && cabeEm(nova, sala) && !cruza(nova, hall) && outras.every((o) => !cruza(nova, o.zona)) ? nova : null;
  };
  const passa = (z) => {
    const visto = passagem.alcance(outras.map((o) => o.zona).concat([z]));
    return passagem.chega(visto, z) && outras.every((o) => passagem.chega(visto, o.zona));
  };
  // em voltas, um passo de cada lado; a passagem (a parte cara) é conferida por volta e,
  // quando a volta fecha alguma, lado a lado (o lado que fecha para de crescer)
  let zona = { ...p.zona };
  const ativos = new Set(["x0", "x1", "z1", "z0"]);
  for (let volta = 0; volta < 600 && ativos.size; volta++) {
    const antes = zona;
    let rodada = zona;
    const mexidos = [];
    for (const lado of [...ativos]) {
      const nova = tentar(rodada, lado);
      if (nova) { rodada = nova; mexidos.push(lado); } else ativos.delete(lado);
    }
    if (!mexidos.length) break;
    if (passa(rodada)) { zona = rodada; continue; }
    zona = antes;
    for (const lado of mexidos) {
      const nova = tentar(zona, lado);
      if (nova && passa(nova)) zona = nova; else ativos.delete(lado);
    }
  }
  p.zona = zona;
  p.corpo = corpoDe(zona);
  p.x = arred((p.corpo.x0 + p.corpo.x1) / 2);
  p.z = arred((p.corpo.z0 + p.corpo.z1) / 2);
  p.w = arred(larg(p.corpo));
  p.d = arred(fundo(p.corpo));
}

/* ---------------------------------------------------------------- arrumar */
/** O tamanho por onde o principal sob medida começa: o que o espaço dá, tirando o que os outros pedem. */
function tamanhoAlvo(p, outras, W, D) {
  const demanda = outras.reduce((s, o) => { const z = locais(o).zona; return s + larg(z) * fundo(z); }, 0);
  const temParede = outras.some((o) => o.parede);
  const faixa = temParede ? 2.6 : REGRAS.corredor;
  const livreW = W - 2 * p.seg - 2 * faixa;
  const livreD = D - 2 * p.seg - REGRAS.hall - REGRAS.corredor - (temParede ? 2.6 : 0);
  // o lado maior da área vai no lado maior do espaço
  const [grande, pequeno] = [Math.max(...p.max), Math.min(...p.max)];
  const [gMin, pMin] = [Math.max(...p.min), Math.min(...p.min)];
  const deitado = W >= D;
  let w = Math.min(deitado ? grande : pequeno, livreW), d = Math.min(deitado ? pequeno : grande, livreD);
  w = Math.max(deitado ? gMin : pMin, w);
  d = Math.max(deitado ? pMin : gMin, d);
  // o que os outros pedem (com a passagem) sai do total
  const orcamento = W * D * 0.85 - demanda * 1.6 - REGRAS.hall * 3;
  if (w * d > orcamento) {
    const k = Math.sqrt(Math.max(orcamento, gMin * pMin) / (w * d));
    w = Math.max(deitado ? gMin : pMin, w * k);
    d = Math.max(deitado ? pMin : gMin, d * k);
  }
  return [arred(w), arred(d)];
}

/**
 * Arruma a escolha no espaço. `espaco`: { largura, comprimento, pe_direito }.
 * Volta { sala, hall, itens, recusados, numeros, passagem }.
 *
 * As áreas sob medida começam grandes (o principal, no que o espaço dá; as
 * outras, no ideal) e encolhem só se algo ficou de fora por falta de lugar:
 * o principal fica do maior tamanho em que tudo cabe. `opcoes.rapido`
 * começa direto do mínimo (para a conta do espaço que caberia tudo).
 */
export function arrumar(espaco, escolha, catalogo, opcoes = {}) {
  const W = Math.max(3, Math.min(150, Number(espaco.largura) || 0));
  const D = Math.max(3, Math.min(150, Number(espaco.comprimento) || 0));
  const pecas = pecasDaEscolha(escolha, catalogo);
  const flex = pecas.filter((p) => p.flex);
  if (!flex.length || opcoes.rapido) return montar(espaco, escolha, catalogo, {});
  const principal = flex.find((p) => p.principal);
  const alvo = principal ? tamanhoAlvo(principal, pecas.filter((p) => p !== principal), W, D) : null;
  const tamanhos = (f) => {
    const t = {};
    for (const p of flex) {
      const topo = p === principal ? alvo : p.ideal;
      const quarto = (v) => Math.round(v * 4) / 4; // de 25 em 25 cm, como o crescer
      t[p.chave] = [quarto(p.min[0] + (topo[0] - p.min[0]) * f), quarto(p.min[1] + (topo[1] - p.min[1]) * f)];
    }
    return t;
  };
  let melhor = null;
  for (const f of [1, 0.75, 0.5, 0.25, 0]) {
    const r = montar(espaco, escolha, catalogo, tamanhos(f));
    const fora = r.recusados.filter((x) => x.codigo === "lugar" || x.codigo === "passagem");
    const nota = fora.filter((x) => x.principal).length * 1000 + fora.length;
    if (!melhor || nota < melhor.nota) melhor = { r, nota };
    if (!nota) break;
  }
  return melhor.r;
}

function montar(espaco, escolha, catalogo, tamanhos) {
  const W = Math.max(3, Math.min(150, Number(espaco.largura) || 0));
  const D = Math.max(3, Math.min(150, Number(espaco.comprimento) || 0));
  const H = Math.max(2, Math.min(20, Number(espaco.pe_direito) || 4));
  const sala = ret(-W / 2, -D / 2, W / 2, D / 2);
  const porta = Math.min(REGRAS.porta, W - 0.4);
  // o hall: o vão da porta com 0,8 m livre de cada lado (ninguém joga colado na porta)
  const meioHall = Math.min(W / 2 - 0.3, Math.max(porta, REGRAS.corredor + 0.4) / 2 + REGRAS.ladoDaPorta);
  const hall = ret(-meioHall, D / 2 - Math.min(REGRAS.hall, D * 0.4), meioHall, D / 2);
  const passagem = new Passagem(sala, hall, REGRAS.corredor);
  const rnd = sorteio((Number(escolha.semente) || 1) * 2654435761);
  const postos = [];
  const recusados = [];
  const recusar = (p, codigo, motivo) => recusados.push({ chave: p.chave, ref: p.ref, nome: p.nome, tipo: p.tipo, principal: !!p.principal, codigo, motivo });

  for (const p of pecasDaEscolha(escolha, catalogo)) {
    // a área sob medida começa no tamanho da vez (e cresce no fim); a medida mínima decide se cabe
    if (p.flex && tamanhos[p.chave]) [p.w, p.d] = tamanhos[p.chave];
    // a altura: o brinquedo não passa do teto (com folga); a área sob medida pede o pé-direito mínimo dela
    if (p.flex ? H + EPS < p.h : p.h + REGRAS.folgaTeto > H + EPS) {
      recusar(p, "altura", p.flex
        ? `pede pé-direito de pelo menos ${metros(p.h)} m; o seu tem ${metros(H)} m`
        : `tem ${metros(p.h)} m de altura; o pé-direito é ${metros(H)} m`);
      continue;
    }
    const { zona: zl } = locais(p);
    const zMin = p.flex ? locais({ ...p, w: p.min[0], d: p.min[1] }).zona : zl;
    const cabeVazia = [0, 90].some((r) => { const z = noMundo(zMin, r, 0, 0); return larg(z) <= W + EPS && fundo(z) <= D + EPS; });
    if (p.flex && cabeVazia && !(larg(zl) <= W + EPS && fundo(zl) <= D + EPS)) {
      // a área deste tamanho não entra: começa do mínimo
      [p.w, p.d] = p.min;
    }
    if (!cabeVazia) {
      recusar(p, "tamanho", `precisa de ${metros(larg(zMin))} × ${metros(fundo(zMin))} m${p.uso.frente || p.uso.lados ? " com a área de uso" : ""}; o espaço tem ${metros(W)} × ${metros(D)} m`);
      continue;
    }
    const lugares = candidatos(p, sala, postos, hall)
      .filter((c) => cabeEm(c.zona, sala) && !cruza(c.zona, hall) && postos.every((o) => !cruza(c.zona, o.zona)));
    if (!lugares.length) {
      const zAgora = locais(p).zona;
      recusar(p, "lugar", `não coube com a entrada e o que já está no espaço (precisa de ${metros(larg(zAgora))} × ${metros(fundo(zAgora))} m livres${p.parede ? " numa parede" : ""})`);
      continue;
    }
    // os melhores primeiro; a passagem é conferida só nos primeiros (é a parte cara)
    const vistos = new Set();
    const unicos = lugares.filter((c) => { const k = `${c.r}|${c.x}|${c.z}`; if (vistos.has(k)) return false; vistos.add(k); return true; });
    unicos.forEach((c) => { c.nota = nota(p, c, sala, postos, rnd); });
    unicos.sort((a, b) => b.nota - a.nota);
    let posto = null;
    for (const c of unicos.slice(0, 10)) {
      const zonas = postos.map((o) => o.zona).concat([c.zona]);
      const visto = passagem.alcance(zonas);
      if (passagem.chega(visto, c.zona) && postos.every((o) => passagem.chega(visto, o.zona))) { posto = c; break; }
    }
    if (!posto) {
      recusar(p, "passagem", "não sobrou passagem de 1,20 m até ele (ou ele fecharia a de outro)");
      continue;
    }
    Object.assign(p, { x: posto.x, z: posto.z, r: posto.r, corpo: posto.corpo, zona: posto.zona, parede: p.parede ? posto.parede : null });
    postos.push(p);
  }

  // as áreas sob medida crescem no que sobrou: o principal até o máximo, as outras até o ideal
  for (const p of postos.filter((o) => o.flex).sort((a, b) => Number(b.principal) - Number(a.principal))) {
    crescerArea(p, sala, postos, hall, passagem, p.principal ? p.max : p.ideal);
  }

  const visto = passagem.alcance(postos.map((o) => o.zona));
  const itens = postos.map((p) => {
    const saida = {
      chave: p.chave, ref: p.ref, nome: p.nome, tipo: p.tipo, desenho: p.desenho || "", principal: !!p.principal,
      x: arred(p.x), z: arred(p.z), r: p.r || 0, w: arred(p.w), d: arred(p.d), h: arred(p.h),
      corpo: mapa(p.corpo, arred), zona: mapa(p.zona, arred), parede: p.parede ?? null,
    };
    if (p.flex) {
      // o gerador desenha com a largura no x: a área mais funda que larga vai girada
      const girar = p.d > p.w + EPS;
      saida.area = { tipo: p.area, largura: girar ? saida.d : saida.w, profundidade: girar ? saida.w : saida.d, girar };
    }
    return saida;
  });
  const areaCorpos = itens.reduce((s, i) => s + larg(i.corpo) * fundo(i.corpo), 0);
  const areaZonas = itens.reduce((s, i) => s + larg(i.zona) * fundo(i.zona), 0);
  return {
    sala: { largura: arred(W), comprimento: arred(D), pe_direito: arred(H), ...mapa(sala, arred) },
    hall: mapa(hall, arred),
    porta: arred(porta),
    itens,
    recusados,
    numeros: {
      area: arred(W * D),
      ocupada: arred(areaCorpos),
      uso: arred(areaZonas - areaCorpos),
      livre: arred(Math.max(0, W * D - areaZonas)),
      ocupacao: Math.round((areaZonas / (W * D)) * 100),
    },
    passagem: { g: passagem.g, nx: passagem.nx, nz: passagem.nz, x0: sala.x0, z0: sala.z0, meio: passagem.meio, alcance: visto },
  };
}

function mapa(r, f) { return { x0: f(r.x0), z0: f(r.z0), x1: f(r.x1), z1: f(r.z1) }; }

/**
 * O espaço que caberia tudo (o que ficou de fora por falta de lugar, não pela altura):
 * aumenta largura e comprimento juntos, de 10 em 10%, até caber. null quando não há o que caber
 * ou quando nem com o triplo coube.
 */
export function espacoParaTudo(espaco, escolha, catalogo) {
  const conta = (res) => res.recusados.filter((r) => r.codigo !== "altura").length;
  const primeiro = arrumar(espaco, escolha, catalogo);
  if (!conta(primeiro)) return null;
  // nas contas de "e se fosse maior", as áreas sob medida no mínimo (é o que basta para caber)
  for (let f = 1.1; f <= 3.001; f += 0.1) {
    const maior = { ...espaco, largura: Math.ceil(espaco.largura * f * 2) / 2, comprimento: Math.ceil(espaco.comprimento * f * 2) / 2 };
    if (!conta(arrumar(maior, escolha, catalogo, { rapido: true }))) return { largura: maior.largura, comprimento: maior.comprimento };
  }
  return null;
}
