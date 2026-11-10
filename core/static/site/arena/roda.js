/* ======================================================================
   A RODA DA ARENA 3D: QUEM FICA NELA E ONDE CADA UM FICA (sem DOM nem
   three.js: o arena3d.js usa, e o core/tests_js/roda.mjs confere no node).

   UM DE CADA POR VEZ: brinquedão, área ninja, área baby e área esportiva
   têm cada uma UM LUGAR FIXO na roda (a "vaga"). Os modelos da mesma
   categoria se revezam nesse lugar -- a pessoa troca qual aparece, um de
   cada vez --, e só o que está à vista é baixado e desenhado: os grandes
   nunca vão para a placa de vídeo todos juntos. A vaga tem o tamanho do
   MAIOR modelo da categoria: trocar nunca encosta nos vizinhos nem mexe na
   roda. Quem entra numa categoria depois (outra área ninja, outro
   brinquedão) cai na vaga dela sozinho, pelo nome e pelas categorias do
   cadastro (`vagaDe`). As máquinas pequenas (boliche, air game, basquete,
   o trampolim de enterrada) não se revezam: ficam todas.

   O LUGAR DE CADA UM (`arrumarRoda`): cada estande (a plataforma do
   grande, o pedestal redondo do pequeno, e a placa com o nome na frente)
   é um polígono de verdade, virado de frente para o meio. Entre um e o
   próximo, a conta acha o menor ângulo que deixa FOLGA metros de chão
   livre entre os dois polígonos (os cantos de dentro e de fora contam,
   não só a largura no arco), e o raio é o menor em que a volta inteira
   fecha. O que sobra da volta se reparte por igual. O grande demais para
   a roda (o Espaço Esportivo, 39 x 23 m) fica no mesmo círculo, mais para
   fora (o recuo que deixa o parque menor), do lado oposto à entrada.
   ====================================================================== */

export const PI = Math.PI;

/** As categorias que se revezam (uma vaga cada), na ordem em que aparecem no "1 de 3". */
export const VAGAS = {
  brinquedao: { id: "brinquedao", nome: "Brinquedão" },
  ninja: { id: "ninja", nome: "Área ninja" },
  baby: { id: "baby", nome: "Área baby" },
  esportiva: { id: "esportiva", nome: "Área esportiva" },
};

const semAcento = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/**
 * A vaga de uma máquina da arena (os dados que o servidor manda), ou "" se
 * ela fica sempre na roda. Pelo nome e pelas categorias do cadastro: um
 * modelo novo da mesma categoria entra na mesma vaga, sem mexer em código.
 */
export function vagaDe(dados) {
  if (dados.vaga && VAGAS[dados.vaga]) return dados.vaga;
  const nome = semAcento(`${dados.nome || ""} ${dados.modelo_id || ""}`);
  const categorias = (dados.categorias || []).map(semAcento);
  const tudo = `${nome} ${categorias.join(" ")}`;
  if (/\bninja\b/.test(tudo)) return "ninja";
  if (/\bbaby\b|\bbebe\b/.test(tudo)) return "baby";
  if (dados.reino || categorias.some((c) => /espacos? esportivos?|areas? esportivas?/.test(c)) || /espaco esportivo/.test(nome)) return "esportiva";
  if (categorias.some((c) => /brinquedo(es|ao)/.test(c)) || /brinquedao/.test(nome)) return "brinquedao";
  return "";
}

/**
 * Os lugares da roda: as máquinas fixas e uma entrada por vaga, na ordem
 * de chegada (a vaga entra onde chegou o primeiro da categoria). Cada vaga
 * traz os membros (na ordem de chegada) e o tamanho do maior.
 * `itens`: [{ dados, largura, fundo }] (largura e fundo do objeto, em m).
 */
export function montarVagas(itens) {
  const lugares = [];
  const vagas = {};
  itens.forEach((item) => {
    const id = vagaDe(item.dados);
    if (!id) {
      lugares.push({ fixo: item, largura: item.largura, fundo: item.fundo, grupo: item.dados.grupo });
      return;
    }
    if (!vagas[id]) {
      vagas[id] = { id, nome: VAGAS[id].nome, membros: [], largura: 0, fundo: 0, grupo: item.dados.grupo };
      lugares.push({ vaga: vagas[id] });
    }
    const v = vagas[id];
    v.membros.push(item);
    v.largura = Math.max(v.largura, item.largura);
    v.fundo = Math.max(v.fundo, item.fundo);
  });
  lugares.forEach((l) => {
    if (l.vaga) Object.assign(l, { largura: l.vaga.largura, fundo: l.vaga.fundo, grupo: l.vaga.grupo });
  });
  return { lugares, vagas };
}

/** O estande de um lugar: grande (plataforma retangular) ou pequeno (pedestal redondo que gira). */
export function estande(largura, fundo) {
  const grande = Math.max(largura, fundo) > 4.5;
  if (grande) {
    const raio = fundo / 2 + 0.55; // até a placa do nome
    return { grande, w: largura + 0.9, d: fundo + 0.9, raio, placa: { z: raio + 0.5, w: 2.4 } };
  }
  const raio = Math.max(largura, fundo) * 0.62 + 0.45;
  return { grande, raio, placa: { z: raio + 0.5, w: Math.min(2.4, raio * 1.7) } };
}

/** O contorno do estande no chão (x para o lado, z para a frente, que olha o meio), convexo. */
export function pegada(e) {
  const pts = [];
  if (e.grande) {
    pts.push([-e.w / 2, -e.d / 2], [e.w / 2, -e.d / 2], [e.w / 2, e.d / 2], [-e.w / 2, e.d / 2]);
  } else {
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * PI * 2;
      // o polígono por fora do círculo (o raio do vértice cobre o lado)
      const r = e.raio / Math.cos(PI / 14);
      pts.push([Math.cos(a) * r, Math.sin(a) * r]);
    }
  }
  // a placa do nome, deitada no chão na frente do estande
  const p = e.placa;
  pts.push([-p.w / 2, p.z - 0.25], [p.w / 2, p.z - 0.25], [p.w / 2, p.z + 0.25], [-p.w / 2, p.z + 0.25]);
  return casco(pts);
}

/** O casco convexo (anti-horário). */
function casco(pontos) {
  const p = pontos.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cruz = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const baixo = [];
  for (const q of p) {
    while (baixo.length >= 2 && cruz(baixo[baixo.length - 2], baixo[baixo.length - 1], q) <= 0) baixo.pop();
    baixo.push(q);
  }
  const cima = [];
  for (let i = p.length - 1; i >= 0; i--) {
    const q = p[i];
    while (cima.length >= 2 && cruz(cima[cima.length - 2], cima[cima.length - 1], q) <= 0) cima.pop();
    cima.push(q);
  }
  return baixo.slice(0, -1).concat(cima.slice(0, -1));
}

/**
 * O contorno no mundo: o estande no ângulo `a` (posição sin a, cos a, como
 * no arena3d.js) a `r` metros do meio, de frente para ele (giro a + PI).
 */
export function noMundo(contorno, a, r) {
  const g = a + PI;
  const c = Math.cos(g);
  const s = Math.sin(g);
  const cx = Math.sin(a) * r;
  const cz = Math.cos(a) * r;
  return contorno.map(([x, z]) => [cx + x * c + z * s, cz - x * s + z * c]);
}

function distanciaSegmentos(a, b, c, d) {
  const cruza = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const d1 = cruza(a, b, c);
  const d2 = cruza(a, b, d);
  const d3 = cruza(c, d, a);
  const d4 = cruza(c, d, b);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) return 0;
  const pontoSeg = (p, u, v) => {
    const dx = v[0] - u[0];
    const dz = v[1] - u[1];
    const t = Math.max(0, Math.min(1, ((p[0] - u[0]) * dx + (p[1] - u[1]) * dz) / (dx * dx + dz * dz || 1)));
    return Math.hypot(p[0] - u[0] - dx * t, p[1] - u[1] - dz * t);
  };
  return Math.min(pontoSeg(a, c, d), pontoSeg(b, c, d), pontoSeg(c, a, b), pontoSeg(d, a, b));
}

function dentro(p, poli) {
  let sinal = 0;
  for (let i = 0; i < poli.length; i++) {
    const a = poli[i];
    const b = poli[(i + 1) % poli.length];
    const c = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
    if (c === 0) continue;
    if (!sinal) sinal = Math.sign(c);
    else if (Math.sign(c) !== sinal) return false;
  }
  return true;
}

/** A menor distância entre dois polígonos convexos (0 se encostam ou se cruzam). */
export function distancia(p, q) {
  if (dentro(p[0], q) || dentro(q[0], p)) return 0;
  let melhor = Infinity;
  for (let i = 0; i < p.length; i++) {
    const a = p[i];
    const b = p[(i + 1) % p.length];
    for (let j = 0; j < q.length; j++) {
      const d = distanciaSegmentos(a, b, q[j], q[(j + 1) % q.length]);
      if (d < melhor) melhor = d;
      if (melhor === 0) return 0;
    }
  }
  return melhor;
}

/** O menor ângulo entre o lugar `i` (em 0) e o `j` (depois dele) que deixa `folga` m de chão livre. */
function separacao(pi, ri, pj, rj, folga) {
  const A = noMundo(pi, 0, ri);
  // o círculo em volta de cada um: longe o bastante, nem precisa do polígono
  const ci = Math.max(...pi.map(([x, z]) => Math.hypot(x, z)));
  const cj = Math.max(...pj.map(([x, z]) => Math.hypot(x, z)));
  const longe = (da) => {
    const centros = Math.hypot(Math.sin(da) * rj, Math.cos(da) * rj - ri);
    if (centros - ci - cj >= folga) return true;
    return distancia(A, noMundo(pj, da, rj)) >= folga;
  };
  let lo = 0;
  let hi = PI;
  if (!longe(hi)) return PI;
  for (let k = 0; k < 22; k++) {
    const meio = (lo + hi) / 2;
    if (longe(meio)) hi = meio;
    else lo = meio;
  }
  return hi;
}

/**
 * Arruma a roda. `lugares`: [{ largura, fundo, grupo, estande? }] na ordem da volta.
 * Devolve { raio, beira, dentro, itens: [{ a, r, estande, contorno }], trechos: [{ id, a0, a1, dentro, fora }] }.
 * Opções: folga (m entre estandes da mesma área), folgaEntreAreas, raioDentro
 * (o círculo do meio que fica livre: o símbolo e as placas das áreas),
 * frente (o ângulo da entrada: o maior fica do lado oposto).
 */
export function arrumarRoda(lugares, opcoes = {}) {
  const { folga = 2.8, folgaEntreAreas = 3.2, raioDentro = 8.5, frente = 0.5 } = opcoes;
  const n = lugares.length;
  if (!n) return { raio: 6.5, beira: 11, dentro: 6.5, itens: [], trechos: [] };
  const itens = lugares.map((l) => {
    const e = l.estande || estande(l.largura, l.fundo);
    const contorno = pegada(e);
    const zFrente = Math.max(...contorno.map((p) => p[1])); // o ponto mais perto do meio
    return { lugar: l, estande: e, contorno, zFrente, area: (e.grande ? e.w * e.d : PI * e.raio * e.raio) };
  });
  // o grande demais (bem maior que os outros): no mesmo círculo, mais para fora
  const maiorArea = Math.max(...itens.map((i) => i.area));
  const outras = itens.filter((i) => i.area < maiorArea).map((i) => i.area);
  const gigante = n > 2 && maiorArea > 3 * Math.max(...outras, 1) ? itens.find((i) => i.area === maiorArea) : null;
  const folgaEntre = (i) => (lugares[i].grupo !== lugares[(i + 1) % n].grupo ? folgaEntreAreas : folga);
  const raios = (R, recuo) => itens.map((i) => (i === gigante ? R + recuo : R));
  const volta = (R, recuo) => {
    const r = raios(R, recuo);
    let soma = 0;
    const seps = [];
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      const s = n === 1 ? PI * 2 : separacao(itens[i].contorno, r[i], itens[j].contorno, r[j], folgaEntre(i));
      seps.push(s);
      soma += s;
    }
    return { soma, seps, r };
  };
  // o menor raio em que todos cabem na volta (e ninguém entra no círculo do meio)
  const menorRaio = (recuo) => {
    let lo = Math.max(6.5, ...itens.map((i) => raioDentro + i.zFrente - (i === gigante ? recuo : 0)));
    if (volta(lo, recuo).soma <= PI * 2) return lo;
    let hi = lo * 2 + 20;
    while (volta(hi, recuo).soma > PI * 2 && hi < 400) hi *= 1.5;
    for (let k = 0; k < 20; k++) {
      const meio = (lo + hi) / 2;
      if (volta(meio, recuo).soma <= PI * 2) hi = meio;
      else lo = meio;
    }
    return hi;
  };
  const longeDoMeio = (R, recuo) => {
    const r = raios(R, recuo);
    let maior = 0;
    itens.forEach((it, k) => {
      for (const [x, z] of it.contorno) maior = Math.max(maior, Math.hypot(x, r[k] - z));
    });
    return maior;
  };
  let recuo = 0;
  let R = menorRaio(0);
  if (gigante) {
    // o recuo que deixa o parque (o círculo que cobre tudo) menor
    let melhor = longeDoMeio(R, 0);
    const tentar = (tentativa) => {
      if (tentativa < 0) return;
      const Rk = menorRaio(tentativa);
      const tamanho = longeDoMeio(Rk, tentativa);
      if (tamanho < melhor - 0.05) { melhor = tamanho; recuo = tentativa; R = Rk; }
    };
    for (let k = 1; k <= 16; k++) tentar(k * 1.5);
    const grosso = recuo;
    [-1, -0.5, 0.5, 1].forEach((d) => tentar(grosso + d));
  }
  const { soma, seps, r } = volta(R, recuo);
  // o que sobra da volta se reparte por igual entre os vãos
  const sobra = Math.max(0, PI * 2 - soma) / n;
  const angulos = [0];
  for (let i = 1; i < n; i++) angulos.push(angulos[i - 1] + seps[i - 1] + sobra);
  // o maior (o gigante, ou o primeiro) fica do lado oposto à entrada
  const ancora = gigante ? itens.indexOf(gigante) : itens.reduce((m, it, k) => (it.area > itens[m].area ? k : m), 0);
  const giro = frente + PI - angulos[ancora];
  const normal = (a) => ((a % (PI * 2)) + PI * 2) % (PI * 2);
  const saida = itens.map((it, k) => ({
    a: normal(angulos[k] + giro), r: r[k], estande: it.estande, contorno: it.contorno,
    mundo: noMundo(it.contorno, angulos[k] + giro, r[k]),
  }));
  // as áreas: do meio do vão de antes ao meio do vão de depois
  const trechos = [];
  for (let k = 0; k < n; k++) {
    const id = lugares[k].grupo;
    const anterior = (k + n - 1) % n;
    const vaoAntes = (seps[anterior] + sobra) / 2;
    const vaoDepois = (seps[k] + sobra) / 2;
    const a0 = angulos[k] + giro - vaoAntes;
    const a1 = angulos[k] + giro + vaoDepois;
    const dentroK = r[k] - saida[k].contorno.reduce((m, p) => Math.max(m, p[1]), 0);
    const foraK = r[k] + Math.min(7, -saida[k].contorno.reduce((m, p) => Math.min(m, p[1]), 0));
    const ultimo = trechos[trechos.length - 1];
    if (ultimo && ultimo.id === id) {
      ultimo.a1 = a1;
      ultimo.dentro = Math.min(ultimo.dentro, dentroK);
      ultimo.fora = Math.max(ultimo.fora, foraK);
      ultimo.itens.push(k);
    } else {
      trechos.push({ id, a0, a1, dentro: dentroK, fora: foraK, itens: [k] });
    }
  }
  // a última área volta para a primeira, se forem a mesma (a volta fechou)
  if (trechos.length > 1 && trechos[0].id === trechos[trechos.length - 1].id) {
    const ultimo = trechos.pop();
    trechos[0].a0 = ultimo.a0 - PI * 2;
    trechos[0].dentro = Math.min(trechos[0].dentro, ultimo.dentro);
    trechos[0].fora = Math.max(trechos[0].fora, ultimo.fora);
    trechos[0].itens.unshift(...ultimo.itens);
  }
  trechos.forEach((t) => {
    // o trecho em [0, 2PI) pelo começo (o fim pode passar de 2PI)
    const deslocar = Math.floor(t.a0 / (PI * 2)) * PI * 2;
    t.a0 -= deslocar;
    t.a1 -= deslocar;
  });
  const dentroDaRoda = Math.min(...saida.map((s) => s.r - Math.max(...s.contorno.map((p) => p[1]))));
  return { raio: R, recuo, beira: longeDoMeio(R, recuo) + 4.5, dentro: dentroDaRoda, itens: saida, trechos };
}

/** A menor folga entre estandes vizinhos (m), para conferir: [menor, entre quem]. */
export function menorFolga(arrumado) {
  const it = arrumado.itens;
  let menor = Infinity;
  let par = null;
  for (let i = 0; i < it.length; i++) {
    for (let j = i + 1; j < it.length; j++) {
      const d = distancia(it[i].mundo, it[j].mundo);
      if (d < menor) { menor = d; par = [i, j]; }
    }
  }
  return [menor, par];
}
