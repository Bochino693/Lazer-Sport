/* ======================================================================
   LAZER SHOT — a miniatura do estande de pistola de luz da Lazer & Sport.

   O jogo de verdade (Godot 3.6 GLES2, TV Box Mali-450, tela em pé
   1024x1820) tem quatro cenários 2D. Aqui ele cabe no console do site em
   540x960, com as artes do próprio jogo (sprites/, reduzidas para WebP em
   site/arena/jogos/lazer-shot/) e as regras copiadas dos scripts:

     ESCOLHA   os quatro cartões, como em cenarios.gd: toque num cenário,
               ALEATÓRIO sorteia na hora e, parado, a roleta escolhe.
     MISSÃO    o objetivo do cenário (missao.gd) por um instante.
     PARTIDA   60 s (o original deixa 120 na máquina), 30 balas com recarga
               de 1,1 s (fase.gd), combo com anunciador (anuncio_combo.gd)
               e o tiro de cada cenário (trajetoria.gd).

   Os cenários (bar.gd, deserto.gd, mar.gd, arena.gd):
     BAR       garrafas nas prateleiras: GIN 20, RUM 50, VODKA 80, WHISKY
               100. A VERDE DE CAVEIRA tira 500 (+20 a cada erro seguido).
               Barril +40 por furo (até 6), janela +50 nos 5 primeiros.
     DESERTO   de dia o SOL, de noite a LUA (troca aos 30 s): 20 a 100; o
               astro errado tira. Combo do mesmo astro; de 3 em diante cada
               acerto ganha combo x 5. O cristal carrega com os acertos e
               descarrega (POWER OF RA!); 9 tiros quebram o cristal (+300),
               4 a ponta de um obelisco (+150).
     MAR       água-viva 20, pote 80, baú 100. BOMBA não: a 3ª encerra.
               Cardume dourado: +40 por peixe, +200 o cardume inteiro.
     ARENA     lanternas na ordem das cores (azul, verde, amarelo,
               vermelho, roxo = 20 a 100): rodada de memória e rodada fixa;
               ordem errada -100; o LED do alto vale +50.

   COORDENADAS: tudo em pontos da tela lógica 540x960. As medidas do
   original estão em pixels da tela 1024x1820 (vezes K) ou da imagem
   1024x1536 da versão 4.6 (t46x/t46y, o tela() de fase.gd); os fundos
   1080x1920 caem exatos em 540x960. Opções de partículas, velocidades e
   tamanhos ficam nas unidades do original (o sistema multiplica por K):
   assim os números batem com os scripts e dá para conferir um a um.
   ====================================================================== */

const W = 540;
const H = 960;
const K = W / 1024;
const t46x = (x) => x * 0.625 - 50;
const t46y = (y) => y * 0.625;
const p46 = (lista) => lista.map((v, i) => (i % 2 === 0 ? t46x(v) : t46y(v)));

const TEMPO_PARTIDA = 60;
const MUNICAO = 30;
const TEMPO_ESCOLHA = 8;
const TEMPO_MISSAO = 2.6;
const TOQUE = 10;             // folga do dedo, em pontos: o dedo é maior que a mira
const HUD_Y = 902;            // a faixa das balas embaixo (tocar nela recarrega)
const OURO = "#ffdb4d";
const VERMELHO = "#ff5247";
const BRANCO = "#ffffff";
const RAD = Math.PI / 180;
const VOLTA = Math.PI * 2;
const PASTA = "lazer-shot/";

/* ----------------------------------------------------------------------
   AS FOLHAS DE ALVO (dados_arte.gd, gerado por tools/preparar_mali.py)

   w/h: a célula original em px (a imagem WebP é menor, mas as contas usam
   o tamanho original: o desenho pede o recorte pela largura real). m: a
   máscara de acerto 24x24 do quadro parado, em hexadecimal por linha.
   ---------------------------------------------------------------------- */
const FOLHAS = {
  garrafa_gin: { q: 1, w: 146, h: 298, parado: [0], acerto: [], fator: 1.0,
    m: "001fc0001fc0001fc0001fc0001fc0001fc0003fe001fff803fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffc03fffe03fffe01fffc" },
  garrafa_rum: { q: 1, w: 118, h: 298, parado: [0], acerto: [], fator: 1.0,
    m: "01fe0001ff0001ff0001ff0003ff0003ff0003ff001fffe07ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff87ffff81ffff0" },
  garrafa_vodka: { q: 1, w: 100, h: 294, parado: [0], acerto: [], fator: 1.0,
    m: "01ff0003ff8001ff8001ff8001ff8003ff800fffe07ffffc7ffffefffffefffffefffffefffffefffffefffffe7ffffe7ffffe7ffffe7ffffe7ffffe7ffffe7ffffe7ffffe3ffffc" },
  garrafa_whisky: { q: 1, w: 102, h: 262, parado: [0], acerto: [], fator: 1.0,
    m: "01ff0003ff0001ff0001ff0001ff0003ff8003ff8007ffc03ffffc7ffffe7fffff7fffff7fffff7fffff7fffff7fffff7fffff7fffff7fffff7fffff7fffff7fffff7fffff3ffffc" },
  garrafa_falsa: { q: 8, w: 136, h: 204, parado: [0], acerto: [1, 2, 3, 4, 5, 6, 7], fator: 1.0,
    m: "00000000780000780000780000780000780000fc0001fe0003ff0003ff8007ff8007ff8007ff8003ff8003ff8003ff8003ff8003ff8003ff0003ff0001fe00000000000000000000" },
  brasao_sol: { q: 4, w: 216, h: 216, parado: [0], acerto: [1, 2, 3], fator: 1.0,
    m: "00180000ff0003ffc007ffe00ffff01ffff83ffffc3ffffc7ffffe7ffffe7ffffeffffffffffff7ffffe7ffffe7ffffe3ffffc3ffffc1ffff80ffff007ffe003ffc000ff00001800" },
  brasao_lua: { q: 4, w: 216, h: 216, parado: [0], acerto: [1, 2, 3], fator: 1.0,
    m: "00000000ff0003ffc007ffe00ffff01ffff83ffffc3ffffc7ffffe7ffffe7ffffe7ffffe7ffffe7ffffe7ffffe7ffffe3ffffc3ffffc1ffff80ffff007ffe003ffc000ff00000000" },
  aguaviva: { q: 7, w: 216, h: 150, parado: [0, 1, 2, 3], acerto: [4, 5, 6], fator: 1.371,
    m: "000000007e0000ff8001ffc003ffc003ffe007ffe007ffe007fff007fff007fff003ffe003fff001ffc001ffc001ffe003ffe003fff007fff003ffc000ffc0003900000000000000" },
  aguaviva_a: { q: 6, w: 216, h: 124, parado: [0, 1, 2], acerto: [3, 4, 5], fator: 1.371,
    m: "00000000fe0001ff0001ff8003ffc007ffc007ffe007ffe007ffe00fffe00fffe00fffe007ffe007ffe003ffc003ffc007ffe007fff00ffff00bfff80abfe000bd40008140000000" },
  vaso: { q: 5, w: 190, h: 212, parado: [0], acerto: [1, 2, 3, 4], fator: 1.0,
    m: "00000000000000000003ff8003ff8003ff8007ffc00fffe00fffe00fffe00fffe00fffe007ffc007ffc003ffe00fffe01ffff01ffff0000000000000000000000000000000000000" },
  bau: { q: 6, w: 188, h: 188, parado: [0], acerto: [1, 2, 3, 4, 5], fator: 1.5,
    m: "00000000000000000000000000000000000000000003fff807fffc07fffc07fffc07fffc07fffc07fffc07fffc07fffc07fffc07fffc07fffc07fffc03fff8000000000000000000" },
  bomba: { q: 9, w: 224, h: 224, parado: [0], acerto: [1, 2, 3, 4, 5, 6, 7, 8], fator: 1.35,
    m: "000000000000000000000000000000000000000000000c00063f9807fff803fff001fff003fff00ffffe0ffffe07fffc03fff001fff003fff007fff8037fd8001e00000c00000000" },
  lanterna: { q: 12, w: 314, h: 304, parado: [0, 1, 2, 3, 4, 5], acerto: [6, 7, 8, 9, 10, 11], fator: 1.2143,
    m: "000000000000000000007c0000fc0000fc0000fe0001ff0003ff8007ffc00fffc00fffe00fffe00fffe00fffe00fffe00fffc007ffc007ff8003ff0000fe0000fc0000fc00007c00" },
};

// A máscara vira 576 bytes uma vez só (a conta do tiro só lê o array).
for (const f of Object.values(FOLHAS)) {
  const m = new Uint8Array(576);
  for (let y = 0; y < 24; y++) {
    const linha = parseInt(f.m.substr(y * 6, 6), 16);
    for (let x = 0; x < 24; x++) m[y * 24 + x] = (linha >> (23 - x)) & 1;
  }
  f.mascara = m;
}

// Os efeitos pequenos (fx_*, mira, cartucho, furo, bolha, peixe, olho do
// astro) vêm num atlas só: um arquivo em vez de vinte e um.
const ATLAS = {
  fx_anel: [372, 102, 64, 64],
  fx_brilho: [440, 102, 64, 64],
  fx_caco: [2, 270, 32, 32],
  fx_estrela: [2, 202, 64, 64],
  fx_faisca: [74, 270, 48, 12],
  fx_fumaca: [70, 202, 64, 64],
  fx_furo_areia: [310, 202, 64, 42],
  fx_furo_pedra: [378, 202, 40, 40],
  fx_ponto: [206, 202, 48, 48],
  fx_nuvem: [138, 202, 64, 64],
  hud_bala: [206, 102, 24, 68],
  ui_mira: [2, 2, 96, 96],
  ui_mira_sombra: [102, 2, 96, 96],
  bar_furo_madeira: [258, 202, 48, 48],
  mar_bolha: [38, 270, 32, 32],
  mar_peixe_dourado: [422, 202, 80, 40],
  mar_farpa: [126, 270, 48, 12],
  astro_sol_esclera: [202, 2, 200, 96],
  astro_sol_iris: [234, 102, 65, 65],
  astro_lua_esclera: [2, 102, 200, 96],
  astro_lua_iris: [303, 102, 65, 65],
};

const ARTES = { fx: PASTA + "fx.webp" };
for (const n of ["fundo_bar", "fundo_egito_sol", "fundo_egito_lua", "fundo_mar", "fundo_arena",
  "cartao_desert", "cartao_mar", "cartao_bar", "cartao_arena", "astro_sol_disco", "astro_lua_disco"]) {
  ARTES[n] = PASTA + n + ".webp";
}
for (const n of Object.keys(FOLHAS)) ARTES[n] = PASTA + "alvo_" + n + ".webp";

/* ----------------------------------------------------------------------
   OS CENÁRIOS (cenarios.gd + missao.gd + estilo.gd)
   ---------------------------------------------------------------------- */
const CENARIOS = [
  { id: "deserto", nome: "DESERTO SAGRADO", titulo: "Deserto Sagrado", curto: "DESERTO", cartao: "cartao_desert",
    fundo: "fundo_egito_sol", cor: "#ffb814", tema: "#ffbd38", nivel: "DIFÍCIL", estrelas: 3,
    missao: ["DE DIA, ACERTE O SOL.", "DE NOITE, ACERTE A LUA."], janela: 2.2, recarga: 1.1 },
  { id: "mar", nome: "FUNDO DO MAR", titulo: "Fundo do Mar", curto: "MAR", cartao: "cartao_mar",
    fundo: "fundo_mar", cor: "#00a6ff", tema: "#3db8ff", nivel: "FÁCIL", estrelas: 1,
    missao: ["ACERTE OS TESOUROS.", "3 BOMBAS E A PARTIDA ACABA."], janela: 1.15, recarga: 1.15 },
  { id: "bar", nome: "BAR DO FAROESTE", titulo: "Bar do Faroeste", curto: "BAR", cartao: "cartao_bar",
    fundo: "fundo_bar", cor: "#40ff59", tema: "#57f26b", nivel: "MÉDIO", estrelas: 2,
    missao: ["QUEBRE AS GARRAFAS.", "NUNCA A VERDE DE CAVEIRA."], janela: 2.2, recarga: 1.1 },
  { id: "arena", nome: "ARENA LAZER SHOT", titulo: "Arena Lazer Shot", curto: "ARENA", cartao: "cartao_arena",
    fundo: "fundo_arena", cor: "#ff0505", tema: "#ff3d33", nivel: "EXPERT", estrelas: 4,
    missao: ["ACERTE AS LANTERNAS", "NA ORDEM DAS CORES."], janela: Infinity, recarga: 1.1 },
];

// O anunciador de combos (anuncio_combo.gd): níveis e a cara de cada tela.
const NIVEIS_COMBO = [
  [2, "DOUBLE HIT"], [3, "TRIPLE HIT"], [4, "QUADRA HIT"], [5, "PENTA HIT"], [6, "MEGA COMBO"],
  [8, "SUPER COMBO"], [10, "INSANE"], [13, "UNSTOPPABLE"], [16, "LEGENDARY"],
];
const TEMAS = {
  mar: { texto: "#b8faff", contorno: "#00244d", clarao: "#33bfff", faisca: "#e0faff", y: 0.205, estilo: "agua" },
  deserto: { texto: "#ffdb57", contorno: "#521a00", clarao: "#ff992e", faisca: "#fff5b3", y: 0.31, estilo: "sol" },
  bar: { texto: "#ffd161", contorno: "#291205", clarao: "#ff8524", faisca: "#ffc75c", y: 0.152, estilo: "saloon" },
  arena: { texto: "#9eff80", contorno: "#0a1a42", clarao: "#4dbfff", faisca: "#8cf2ff", y: 0.335, estilo: "neon" },
};

// O tiro de cada cenário (trajetoria.gd): voo do pulso, vida do feixe,
// [cor, alfa] de halo, faixa e miolo, e as larguras (px do original).
const FEIXES = {
  laser: [0.07, 0.17, [["#ff2933", 0.36], ["#ff383d", 0.66], ["#ffdbdb", 1]], [64, 24, 7]],
  sol: [0.08, 0.26, [["#ff991a", 0.32], ["#ffd147", 0.66], ["#fffacc", 1]], [84, 28, 8]],
  lua: [0.08, 0.28, [["#cce0ff", 0.28], ["#f0f7ff", 0.62], ["#ffffff", 1]], [76, 26, 8]],
  mar: [0.09, 0.2, [["#1ab8d6", 0.34], ["#66ebff", 0.66], ["#dbffff", 1]], [64, 22, 7]],
};
const IMPACTO = 0.35;
const BALA_VOO = 0.07;

/* ----------------------------------------------------------------------
   AJUDANTES
   ---------------------------------------------------------------------- */
const aleatorio = (a, b) => a + Math.random() * (b - a);
const sorteio = (lista) => lista[(Math.random() * lista.length) | 0];
const limitar = (v, a, b) => (v < a ? a : v > b ? b : v);
const misturar = (a, b, k) => a + (b - a) * k;
const saidaVolta = (k) => { const t = k - 1; return 1 + 2.70158 * t * t * t + 1.70158 * t * t; };
const entradaVolta = (k) => 2.70158 * k * k * k - 1.70158 * k * k;
const suave = (k) => k * k * (3 - 2 * k);
const senoEntra = (k) => 1 - Math.cos((k * Math.PI) / 2);
const senoSai = (k) => Math.sin((k * Math.PI) / 2);

function quique(k) {
  const n = 7.5625;
  const d = 2.75;
  if (k < 1 / d) return n * k * k;
  if (k < 2 / d) { k -= 1.5 / d; return n * k * k + 0.75; }
  if (k < 2.5 / d) { k -= 2.25 / d; return n * k * k + 0.9375; }
  k -= 2.625 / d;
  return n * k * k + 0.984375;
}

function embaralhar(lista) {
  for (let i = lista.length - 1; i > 0; i--) {
    const j = (Math.random() * (i + 1)) | 0;
    const t = lista[i];
    lista[i] = lista[j];
    lista[j] = t;
  }
  return lista;
}

// Ponto dentro do polígono (lista plana x0, y0, x1, y1...).
function dentro(x, y, pts) {
  let d = false;
  for (let i = 0, j = pts.length - 2; i < pts.length; j = i, i += 2) {
    const xi = pts[i], yi = pts[i + 1], xj = pts[j], yj = pts[j + 1];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) d = !d;
  }
  return d;
}

function caminhoPoligono(ctx, pts) {
  ctx.beginPath();
  ctx.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
  ctx.closePath();
}

function caminhoArredondado(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

const cacheClaro = new Map();
// Cor rumo ao branco (o linear_interpolate(Color.white, k) do Godot).
function clarear(hex, k) {
  const chave = hex + k;
  let r = cacheClaro.get(chave);
  if (r) return r;
  const v = parseInt(hex.slice(1), 16);
  const f = (c) => Math.round(c + (255 - c) * k).toString(16).padStart(2, "0");
  r = "#" + f((v >> 16) & 255) + f((v >> 8) & 255) + f(v & 255);
  cacheClaro.set(chave, r);
  return r;
}

// O tiro pega o desenho? (lx, ly) em px do quadro original, a partir do
// centro; a folga (px do quadro) abre a máscara para o dedo.
function naMascara(f, lx, ly, folgaX, folgaY) {
  const u = lx / f.w + 0.5;
  const v = ly / f.h + 0.5;
  const fu = folgaX / f.w;
  const fv = folgaY / f.h;
  if (u < -fu || u > 1 + fu || v < -fv || v > 1 + fv) return false;
  const x0 = Math.max(0, Math.floor((u - fu) * 24));
  const x1 = Math.min(23, Math.floor((u + fu) * 24));
  const y0 = Math.max(0, Math.floor((v - fv) * 24));
  const y1 = Math.min(23, Math.floor((v + fv) * 24));
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) if (f.mascara[y * 24 + x]) return true;
  }
  return false;
}

// Ponto da tela para o quadro de um alvo (centro em cx, cy, girado e em escala).
function paraQuadro(x, y, cx, cy, rot, escX, escY, saida) {
  const dx = x - cx;
  const dy = y - cy;
  const c = Math.cos(-rot);
  const s = Math.sin(-rot);
  saida[0] = (dx * c - dy * s) / escX;
  saida[1] = (dx * s + dy * c) / escY;
  return saida;
}
const LOCAL = [0, 0];

/* ----------------------------------------------------------------------
   PARTÍCULAS (particulas.gd): um vetor fixo reaproveitado — tiro atrás de
   tiro não cria objeto novo. Cor por imagem tingida (cache).
   ---------------------------------------------------------------------- */
const V_PADRAO = [100, 300];
const ANG_PADRAO = [0, 360];
const VIDA_PADRAO = [0.4, 0.8];
const TAM_PADRAO = [8, 16];

class Particulas {
  constructor(jogo, max, somar) {
    this.j = jogo;
    this.somar = somar;
    this.max = max;
    this.p = [];
    for (let i = 0; i < max; i++) {
      this.p.push({ vivo: false, x: 0, y: 0, vx: 0, vy: 0, t: 0, vida: 1, tam0: 1, tam1: 0, a0: 1,
        img: null, grav: 0, arrasto: 1, rot: 0, giro: 0, estica: 0 });
    }
    this.prox = 0;
    this.vivos = 0;
  }

  limpar() {
    for (const q of this.p) q.vivo = false;
    this.vivos = 0;
  }

  soltar(x, y, vx, vy, vida, tam0, tam1, img, alfa = 1, grav = 0, arrasto = 1, giro = 0, estica = 0) {
    if (!img) return;
    let q = null;
    for (let i = 0; i < this.max; i++) {
      const c = this.p[(this.prox + i) % this.max];
      if (!c.vivo) { q = c; this.prox = (this.prox + i + 1) % this.max; break; }
    }
    if (!q) { q = this.p[this.prox]; this.prox = (this.prox + 1) % this.max; }
    q.vivo = true; q.x = x; q.y = y; q.vx = vx; q.vy = vy; q.t = 0; q.vida = Math.max(0.05, vida);
    q.tam0 = tam0; q.tam1 = tam1; q.img = img; q.a0 = alfa; q.grav = grav; q.arrasto = arrasto;
    q.rot = Math.random() * VOLTA; q.giro = giro; q.estica = estica;
    this.vivos++;
  }

  // Opções em unidades do original (px da tela 1024): n, tex, cor, alfa,
  // vel, ang (graus), vida, tam, fim (fator do tamanho), grav, arrasto,
  // giro, estica, espalha.
  explosao(x, y, o) {
    const n = Math.max(1, Math.round((o.n ?? 12) * this.j.fator));
    const img = this.j.tinta(o.tex || "fx_ponto", o.cor || BRANCO);
    if (!img) return;
    const vel = o.vel || V_PADRAO;
    const ang = o.ang || ANG_PADRAO;
    const vida = o.vida || VIDA_PADRAO;
    const tam = o.tam || TAM_PADRAO;
    const fim = o.fim ?? 0.2;
    const grav = (o.grav ?? 0) * K;
    const arrasto = o.arrasto ?? 1;
    const giro = o.giro;
    const espalha = (o.espalha ?? 0) * K;
    const alfa = o.alfa ?? 1;
    for (let i = 0; i < n; i++) {
      const a = aleatorio(ang[0], ang[1]) * RAD;
      const dx = Math.cos(a);
      const dy = Math.sin(a);
      const v = aleatorio(vel[0], vel[1]) * K;
      const t0 = aleatorio(tam[0], tam[1]) * K;
      const e = Math.random() * espalha;
      this.soltar(x + dx * e, y + dy * e, dx * v, dy * v, aleatorio(vida[0], vida[1]), t0, t0 * fim, img, alfa,
        grav, arrasto, giro ? aleatorio(giro[0], giro[1]) : 0, o.estica || 0);
    }
  }

  atualizar(dt) {
    if (!this.vivos) return;
    let vivos = 0;
    for (const q of this.p) {
      if (!q.vivo) continue;
      q.t += dt;
      if (q.t >= q.vida) { q.vivo = false; continue; }
      if (q.arrasto > 0) {
        const k = Math.exp(-q.arrasto * dt);
        q.vx *= k;
        q.vy *= k;
      }
      q.vy += q.grav * dt;
      q.x += q.vx * dt;
      q.y += q.vy * dt;
      // nada quica: o que sai da tela some na hora (como no original)
      if (q.y > H + 42 || q.y < -60 || q.x < -42 || q.x > W + 42) { q.vivo = false; continue; }
      q.rot += q.giro * dt;
      vivos++;
    }
    this.vivos = vivos;
  }

  desenhar(ctx) {
    if (!this.vivos) return;
    ctx.globalCompositeOperation = this.somar ? "lighter" : "source-over";
    for (const q of this.p) {
      if (!q.vivo) continue;
      const k = q.t / q.vida;
      const tam = q.tam0 + (q.tam1 - q.tam0) * k;
      if (tam <= 0.3) continue;
      ctx.globalAlpha = q.a0 * (1 - k);
      if (q.estica > 0) {
        const comp = tam + Math.hypot(q.vx, q.vy) * q.estica;
        const ang = Math.atan2(q.vy, q.vx);
        ctx.translate(q.x, q.y);
        ctx.rotate(ang);
        ctx.drawImage(q.img, -comp * 0.5, -tam * 0.25, comp, tam * 0.5);
        ctx.rotate(-ang);
        ctx.translate(-q.x, -q.y);
      } else if (q.giro !== 0) {
        ctx.translate(q.x, q.y);
        ctx.rotate(q.rot);
        ctx.drawImage(q.img, -tam * 0.5, -tam * 0.5, tam, tam);
        ctx.rotate(-q.rot);
        ctx.translate(-q.x, -q.y);
      } else {
        ctx.drawImage(q.img, q.x - tam * 0.5, q.y - tam * 0.5, tam, tam);
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
  }
}

/* ----------------------------------------------------------------------
   CACOS DA PRÓPRIA IMAGEM (cacos.gd): o alvo se parte num leque de
   pedaços a partir do ponto do tiro — pequenos perto dele, grandes longe.
   Cada pedaço recorta a imagem do alvo e voa, gira e cai.
   ---------------------------------------------------------------------- */
class Cacos {
  constructor(jogo, max) {
    this.j = jogo;
    this.max = max;
    this.lista = [];
  }

  limpar() {
    this.lista.length = 0;
  }

  // img/sx/sy/sw/sh: o recorte na imagem; rw/rh: o tamanho da região em px
  // do quadro original; cx/cy/esc/rot: onde ela está na tela; tx/ty: o tiro.
  estourar(img, sx, sy, sw, sh, rw, rh, cx, cy, esc, rot, tx, ty, o = {}) {
    if (!img) return;
    const n = Math.max(4, Math.round((o.n ?? 14) * 0.6 * this.j.fator));
    const forca = o.forca ?? 1;
    const grav = (o.grav ?? 1500) * K;
    const vida = o.vida ?? 1.1;
    const sobe = (o.sobe ?? 260) * K;
    const giro = o.giro ?? 9;
    const mx = rw / 2;
    const my = rh / 2;
    paraQuadro(tx, ty, cx, cy, rot, esc, esc, LOCAL);
    const lx = limitar(LOCAL[0], -mx * 0.8, mx * 0.8);
    const ly = limitar(LOCAL[1], -my * 0.8, my * 0.8);
    const borda = [];
    const base = Math.random() * VOLTA;
    for (let i = 0; i < n; i++) {
      const a = base + (VOLTA * (i + aleatorio(-0.3, 0.3))) / n;
      const dx = Math.cos(a);
      const dy = Math.sin(a);
      const ex = Math.abs(dx) < 1e-4 ? Infinity : ((dx > 0 ? mx : -mx) - lx) / dx;
      const ey = Math.abs(dy) < 1e-4 ? Infinity : ((dy > 0 ? my : -my) - ly) / dy;
      const e = Math.min(ex, ey);
      borda.push(lx + dx * e, ly + dy * e);
    }
    const comum = { img, sx, sy, sw, sh, rw, rh, cx, cy, esc, rot, tx, ty, grav, vida, sobe, giro };
    for (let i = 0; i < n; i++) {
      const ax = borda[i * 2], ay = borda[i * 2 + 1];
      const b = ((i + 1) % n) * 2;
      const bx = borda[b], by = borda[b + 1];
      const k = aleatorio(0.3, 0.5);
      const a2x = misturar(lx, ax, k), a2y = misturar(ly, ay, k);
      const b2x = misturar(lx, bx, k), b2y = misturar(ly, by, k);
      this.pedaco([lx, ly, a2x, a2y, b2x, b2y], comum, forca * 1.25);
      this.pedaco([a2x, a2y, ax, ay, bx, by, b2x, b2y], comum, forca);
    }
    while (this.lista.length > this.max) this.lista.shift();
  }

  pedaco(pts, c, forca) {
    let px = 0, py = 0;
    const n = pts.length / 2;
    for (let i = 0; i < pts.length; i += 2) { px += pts[i]; py += pts[i + 1]; }
    px /= n;
    py /= n;
    const co = Math.cos(c.rot), si = Math.sin(c.rot);
    const wx = c.cx + (px * co - py * si) * c.esc;
    const wy = c.cy + (px * si + py * co) * c.esc;
    let dx = wx - c.tx, dy = wy - c.ty;
    const d = Math.hypot(dx, dy);
    if (d < 1) { dx = aleatorio(-1, 1); dy = -1; } else { dx /= d; dy /= d; }
    const v = aleatorio(160, 460) * forca * K;
    this.lista.push({
      img: c.img, sx: c.sx, sy: c.sy, sw: c.sw, sh: c.sh, rw: c.rw, rh: c.rh, pts, px, py, esc: c.esc, rot0: c.rot,
      x: wx, y: wy, vx: dx * v + aleatorio(-60, 60) * K, vy: dy * v - c.sobe * aleatorio(0.5, 1.2),
      rot: 0, giro: aleatorio(-c.giro, c.giro), t: 0, vida: c.vida * aleatorio(0.75, 1.25), grav: c.grav,
    });
  }

  atualizar(dt) {
    for (let i = this.lista.length - 1; i >= 0; i--) {
      const c = this.lista[i];
      c.t += dt;
      c.vy += c.grav * dt;
      c.x += c.vx * dt;
      c.y += c.vy * dt;
      c.rot += c.giro * dt;
      if (c.t >= c.vida || c.y > H + 50 || c.x < -70 || c.x > W + 70) this.lista.splice(i, 1);
    }
  }

  desenhar(ctx) {
    for (const c of this.lista) {
      const a = (1 - c.t / c.vida) * 3;
      ctx.globalAlpha = a < 1 ? Math.max(0, a) : 1;
      ctx.save();
      ctx.translate(c.x, c.y);
      ctx.rotate(c.rot + c.rot0);
      ctx.scale(c.esc, c.esc);
      ctx.translate(-c.px, -c.py);
      caminhoPoligono(ctx, c.pts);
      ctx.clip();
      ctx.drawImage(c.img, c.sx, c.sy, c.sw, c.sh, -c.rw / 2, -c.rh / 2, c.rw, c.rh);
      ctx.restore();
    }
    ctx.globalAlpha = 1;
  }
}

/* ======================================================================
   BAR DO FAROESTE (bar.gd)
   ====================================================================== */
const BAR = {
  colunas: { 100: [190, 315, 440, 565, 690], 80: [190, 355, 520, 685], 50: [190, 355, 520, 685],
    20: [110, 220, 330, 440, 550, 660] },
  pe: { 100: 589, 80: 853, 50: 1146, 20: 1424 },      // onde o pé da garrafa pisa (tela 1024)
  base: { 100: 621, 80: 890, 50: 1202, 20: 1480 },    // a base da frente da tábua
  beiradas: [[307, 328], [446, 470]],                  // a frente das duas tábuas de cima (pontos)
  escala: { 100: 0.5, 80: 0.56, 50: 0.62, 20: 0.58 },
  escalaFalsa: { 100: 0.81, 80: 0.85, 50: 0.96, 20: 1.0 },
  nomes: { 100: "whisky", 80: "vodka", 50: "rum", 20: "gin" },
  chanceFalsa: { 100: [0.52, 0.68, 0.88, 0.96], 80: [0.44, 0.58, 0.8, 0.9], 50: [0.34, 0.46, 0.68, 0.78],
    20: [0.24, 0.34, 0.52, 0.62] },
  idadeTroca: { 100: 1.2, 80: 1.55, 50: 2.15, 20: 3.2 },
};
// As garrafas saem 15% maiores que no original: no celular o dedo cobre a
// garrafa de whisky inteira, e a tábua tem folga para isso.
const TOQUE_GARRAFA = 1.15;
const LIQUIDO = {
  gin: ["#d9f2ff", 0.85], rum: ["#c7661a", 0.9], vodka: ["#e6f7ff", 0.85], whisky: ["#cc801f", 0.9], falsa: ["#59d940", 0.9],
};
// madeira molhada escurece (a cor da bebida só tinge): a fórmula de _manchar()
const MANCHA = {};
for (const [tipo, [hex]] of Object.entries(LIQUIDO)) {
  const v = parseInt(hex.slice(1), 16);
  const r = ((v >> 16) & 255) / 255, g = ((v >> 8) & 255) / 255, b = (v & 255) / 255;
  const f = (c) => Math.round(c * 255).toString(16).padStart(2, "0");
  MANCHA[tipo] = "#" + f(0.16 + r * 0.14) + f(0.07 + g * 0.08) + f(0.02 + b * 0.05);
}
const VIDRACAS = [[90, 82, 48, 56], [144, 82, 46, 56], [211, 82, 47, 56], [264, 82, 46, 56],
  [90, 145, 48, 55], [144, 145, 46, 55], [211, 145, 47, 55], [264, 145, 46, 55]];
const CARTAZ_BAR = p46([797, 1022, 992, 1027, 1002, 1360, 800, 1335]);
const BARRIL_BAR = p46([800, 995, 1024, 995, 1024, 1435, 810, 1425, 785, 1300, 776, 1160, 785, 1060]);
const FEIXE_BAR = p46([18.3, 30.6, 31.6, 17.4, 79.5, 18.0, 84.6, 28.0, 135.9, 140.3, 230.5, 364.6, 234.5, 384.0,
  163.8, 384.0, 21.0, 58.8, 18.1, 49.7].map((v) => v * 4));
const POEIRA_BAR = p46([400, 590, 656, 1139, 438, 748, 348, 309, 619, 955, 134, 198, 558, 936, 513, 1024, 468, 966,
  340, 603, 191, 218, 377, 571, 438, 701, 595, 896, 352, 406, 597, 1059, 640, 1099, 350, 474, 217, 436, 290, 501,
  467, 566, 514, 741, 365, 423, 110, 138, 367, 699, 492, 737, 287, 390, 315, 638, 248, 419, 396, 347, 294, 305]);

class CenarioBar {
  constructor(j) {
    this.j = j;
    this.api = j.api;
    this.garrafas = [];
    this.slots = new Map();
    this.vagoAte = new Map();
    this.spawnT = 0.4;
    this.trocaT = 2.5;
    this.errosSeguidos = 0;
    this.nivel = 0;
    this.barrilFuros = 0;
    this.jatos = [];
    this.poca = 0;
    this.janela = VIDRACAS.map(([x, y, w, h]) => ({ x0: t46x(x), y0: t46y(y), x1: t46x(x + w), y1: t46y(y + h),
      quebrada: false, trincas: [] }));
    this.janelaPagos = 0;
    this.furos = [];
    this.nFuro = 0;
    this.manchas = [];
    this.t = 0;
    this.solForca = 1;
  }

  preparar() {}

  comecar() {
    this.spawnT = 0.1;
    this.trocaT = 2.5;
    for (let i = 0; i < 6; i++) this.spawnar();
  }

  podeAtirar() { return true; }

  extra() {
    const c = this.j.combo;
    const cor = c >= 5 ? "#ff59e6" : c >= 3 ? "#ffbf33" : c >= 2 ? "#80ff8c" : "#cccccc";
    return ["COMBO", c >= 2 ? "x" + c : "-", cor];
  }

  // ---------------------------------------------------------------- partida
  atualizar(dt) {
    const j = this.j;
    this.nivel = Math.floor(Math.max(j.pontos, 0) / 3000);
    this.spawnT -= dt;
    if (this.spawnT <= 0) {
      this.spawnT = aleatorio(0.35, 0.95);
      for (let k = 0; k < 3; k++) if (this.spawnar()) break;
    }
    this.trocaT -= dt;
    if (this.trocaT <= 0) {
      let de = 2.0, ate = 3.2;
      if (j.pontos >= 14000) { de = 0.65; ate = 1.2; } else if (j.pontos >= 7000) { de = 0.85; ate = 1.55; } else if (j.pontos >= 3000) { de = 1.15; ate = 2.0; }
      this.trocaT = aleatorio(de, ate);
      const trocas = j.pontos >= 9000 ? 3 : j.pontos >= 3000 ? 2 : 1;
      for (let k = 0; k < trocas; k++) this.forcarTroca();
    }
    for (let i = this.garrafas.length - 1; i >= 0; i--) {
      const g = this.garrafas[i];
      if (g.saindo) continue;
      g.idade += dt;
      if (g.idade >= g.vida) {
        if (g.tipo === "falsa") this.retirar(g);
        else if (Math.random() <= this.chanceFalsa(g.prat)) this.virarFalsa(g);
        else this.retirar(g);
      }
    }
  }

  spawnar() {
    let vivas = 0;
    for (const g of this.garrafas) if (!g.saindo) vivas++;
    if (vivas >= Math.min(22, 13 + this.nivel)) return false;
    const opcoes = [];
    for (const prat of [100, 80, 50, 20]) for (const x of BAR.colunas[prat]) opcoes.push([prat, x]);
    embaralhar(opcoes);
    for (const [prat, x] of opcoes) {
      const chave = prat + "|" + x;
      if (this.slots.has(chave) || (this.vagoAte.get(chave) || 0) > this.t) continue;
      this.criarGarrafa(prat, x, BAR.nomes[prat]);
      return true;
    }
    return false;
  }

  criarGarrafa(prat, xTela, tipo) {
    const falsa = tipo === "falsa";
    const g = {
      tipo, prat, chave: prat + "|" + xTela, x: xTela * K, pe: BAR.pe[prat] * K,
      pontos: falsa ? 0 : prat, f: FOLHAS["garrafa_" + tipo], img: this.api.img["garrafa_" + tipo],
      esc: (falsa ? BAR.escalaFalsa : BAR.escala)[prat] * K * TOQUE_GARRAFA,
      vazio: falsa ? 28 : 0,       // px vazios embaixo do desenho da verde parada
      idade: 0, vida: 0, saindo: false, entra: 0, sai: -1, estalo: -1, acertoT: -1, frame: 0,
      balanco: 0, balancoT: 0, rot: 0,
    };
    g.vida = this.vidaDe(g);
    this.slots.set(g.chave, g);
    this.garrafas.push(g);
    return g;
  }

  vidaDe(g) {
    const red = Math.min(1.8, this.nivel * 0.22);
    if (g.tipo === "falsa") return aleatorio(2.8, 3.8);
    switch (g.prat) {
      case 100: return aleatorio(Math.max(1.65, 2.8 - red), Math.max(2.25, 3.7 - red));
      case 80: return aleatorio(Math.max(2.25, 3.7 - red), Math.max(3.0, 4.8 - red));
      case 50: return aleatorio(Math.max(3.2, 4.8 - red), Math.max(4.1, 6.1 - red));
      default: return aleatorio(Math.max(4.4, 6.4 - red), Math.max(5.6, 8.0 - red));
    }
  }

  chanceFalsa(prat) {
    const p = this.j.pontos;
    const i = p >= 7000 ? 3 : p >= 3000 ? 2 : p >= 1500 ? 1 : 0;
    return BAR.chanceFalsa[prat][i];
  }

  retirar(g) {
    g.saindo = true;
    g.sai = 0;
    this.slots.delete(g.chave);
  }

  // A garrafa vira a verde de caveira no mesmo lugar (um estalo).
  virarFalsa(g) {
    const i = this.garrafas.indexOf(g);
    if (i >= 0) this.garrafas.splice(i, 1);
    this.slots.delete(g.chave);
    const nova = this.criarGarrafa(g.prat, g.chave.split("|")[1] | 0, "falsa");
    nova.entra = -1;
    nova.estalo = 0;
    this.j.part.explosao(nova.x, nova.pe - 60 * K, { n: 4, tex: "fx_nuvem", vel: [10, 40], vida: [0.5, 0.9],
      tam: [30, 50], fim: 1.6, cor: "#66d94d", alfa: 0.45 });
  }

  // De tempos em tempos uma garrafa boa troca: sai ou vira a verde,
  // garantindo um mínimo de verdes na estante.
  forcarTroca() {
    const p = this.j.pontos;
    const normais = [];
    let falsas = 0;
    for (const g of this.garrafas) {
      if (g.saindo) continue;
      if (g.tipo === "falsa") falsas++;
      else normais.push(g);
    }
    const minimo = p >= 14000 ? 4 : p >= 7000 ? 3 : p >= 3000 ? 2 : 1;
    const precisa = falsas < minimo;
    embaralhar(normais);
    for (const g of normais) {
      let idadeMin = BAR.idadeTroca[g.prat];
      if (precisa) idadeMin *= 0.72;
      if (g.idade < idadeMin) continue;
      if (precisa) { this.virarFalsa(g); return; }
      const chance = this.chanceFalsa(g.prat) + (g.prat >= 80 ? 0.1 : 0);
      if (Math.random() <= Math.min(chance, 0.98)) this.virarFalsa(g);
      else this.retirar(g);
      return;
    }
  }

  // ---------------------------------------------------------------- tiro
  garrafaNoPonto(x, y) {
    // primeiro a máscara justa; sem acerto, a folga do dedo (a mais perto)
    let melhor = null;
    let dMelhor = Infinity;
    for (let passo = 0; passo < 2 && !melhor; passo++) {
      for (let i = this.garrafas.length - 1; i >= 0; i--) {
        const g = this.garrafas[i];
        if (g.saindo) continue;
        paraQuadro(x, y, g.x, g.pe, g.rot, g.esc, g.esc, LOCAL);
        const lx = LOCAL[0];
        const ly = LOCAL[1] + g.f.h / 2 - g.vazio;
        const folga = passo === 0 ? g.f.w / 24 : TOQUE / g.esc;
        if (!naMascara(g.f, lx, ly, folga, folga)) continue;
        if (passo === 0) return g;
        const d = Math.hypot(lx, ly);
        if (d < dMelhor) { dMelhor = d; melhor = g; }
      }
    }
    return melhor;
  }

  tiro(x, y) {
    const g = this.garrafaNoPonto(x, y);
    if (g) { this.acertar(g, x, y); return; }
    const emCartaz = dentro(x, y, CARTAZ_BAR);
    const noBarril = emCartaz || dentro(x, y, BARRIL_BAR);
    if (noBarril && this.barrilFuros < 6) { this.tiroNoBarril(x, y, emCartaz); return; }
    const vidro = this.tiroNaJanela(x, y);
    if (vidro === "quebrou") {
      let quebradas = 0;
      for (const v of this.janela) if (v.quebrada) quebradas++;
      this.solForca = Math.min(2.2, 1 + 0.15 * quebradas);
      if (this.janelaPagos < 5) { this.pagarJanela(x, y); return; }
    }
    this.errosSeguidos++;
    this.j.errar(x, y, "ERROU!");
    if (vidro === "fora") this.lascar(x, y, emCartaz);
  }

  acertar(g, x, y) {
    const j = this.j;
    g.saindo = true;
    this.slots.delete(g.chave);
    this.vagoAte.set(g.chave, this.t + 1.3);
    if (g.tipo === "falsa") {
      this.errosSeguidos++;
      j.perder(500 + 20 * this.errosSeguidos, g.x, g.pe - 90 * K, "GARRAFA IMPOSTORA");
      this.api.som("erro");
      this.api.som("batida");
      j.clarao("#e61a0d", 0.22, 0.3);
      j.tremer(8);
      j.part.explosao(g.x, g.pe - 70 * K, { n: 6, tex: "fx_fumaca", vel: [30, 110], ang: [200, 340], vida: [0.9, 1.5],
        tam: [50, 80], fim: 2, cor: "#4dbf40", alfa: 0.6, grav: -40 });
      this.balancar(g.prat, g.x, 0.07);
      g.acertoT = 0;
      g.vazio = 7;
      return;
    }
    this.errosSeguidos = 0;
    j.registrarCombo();
    j.ganhar(g.pontos, g.x, g.pe - g.f.h * g.esc * 0.62, OURO, 1 + (g.pontos - 20) / 400);
    this.api.som("vidro");
    this.estourar(g, x, y);
    this.garrafas.splice(this.garrafas.indexOf(g), 1);
  }

  // A garrafa estoura: cacos da própria imagem, a bebida espirra na cor
  // dela, pinga da tábua e mancha a parede.
  estourar(g, x, y) {
    const j = this.j;
    const [liq, aLiq] = LIQUIDO[g.tipo];
    const cy = g.pe - (g.f.h / 2) * g.esc;
    j.cacos.estourar(g.img, 0, 0, g.img.width, g.img.height, g.f.w, g.f.h, g.x, cy, g.esc, g.rot, x, y,
      { n: 10, forca: 1, grav: 1700, vida: 1.3, sobe: 240 });
    j.part.explosao(x, y, { n: 16, tex: "fx_ponto", vel: [120, 460], vida: [0.5, 1.0], tam: [8, 18], fim: 0.6,
      cor: liq, alfa: aLiq, grav: 1300, arrasto: 0.6 });
    j.part.explosao(x, y, { n: 3, tex: "fx_nuvem", vel: [20, 80], vida: [0.4, 0.7], tam: [60, 90], fim: 1.5, cor: liq, alfa: 0.35 });
    j.luz.explosao(x, y, { n: 9, vel: [150, 420], vida: [0.25, 0.5], tam: [6, 12], cor: "#fff2d9", grav: 500, estica: 0.03 });
    j.brilho(x, y, 220, "#ffebbf", 0.75, 0.25);
    j.part.explosao(g.x, BAR.base[g.prat] * K + 1, { n: 5, tex: "fx_ponto", vel: [0, 30], ang: [80, 100], vida: [1.0, 1.6],
      tam: [6, 9], fim: 0.8, cor: liq, alfa: aLiq, grav: 900, espalha: 30 });
    this.manchar(g.x + aleatorio(-5, 5), g.pe - (140 * g.esc) / TOQUE_GARRAFA, MANCHA[g.tipo], 1.1, 1.3);
    if (g.prat <= 50) this.manchar(g.x + 3, g.pe + 1, MANCHA[g.tipo], 1.4, 0.22);
    this.balancar(g.prat, g.x, 0.09);
  }

  tiroNoBarril(x, y, cartaz) {
    this.barrilFuros++;
    this.lascar(x, y, cartaz);
    this.j.bonus(40, x, y, "#ff7385", 1.1);
    this.jatos.push({ x, y, t: 0, lado: x < t46x(900) ? -1 : 0 });
    this.api.som("quica");
    if (this.barrilFuros === 1) this.j.instrucao("VINHO VAZANDO! +40 POR FURO", "#ffb8c2");
    else if (this.barrilFuros === 6) this.j.instrucao("BARRIL ESGOTADO", "#ffb8c2");
  }

  // A vidraça leva o tiro: "fora" (não é a janela), "vazio" (o vidro dali
  // já caiu) ou "quebrou".
  tiroNaJanela(x, y) {
    for (const v of this.janela) {
      if (x < v.x0 || x > v.x1 || y < v.y0 || y > v.y1) continue;
      if (v.quebrada) return "vazio";
      this.quebrarVidraca(v, x, y, true);
      return "quebrou";
    }
    return "fora";
  }

  quebrarVidraca(v, x, y, comSom) {
    v.quebrada = true;
    v.trincas.length = 0;
    // trincas saindo do furo até a moldura
    const n = 6 + ((Math.random() * 3) | 0);
    for (let i = 0; i < n; i++) {
      let ang = (VOLTA * (i + Math.random() * 0.6)) / n;
      let px = x, py = y;
      const linha = [px, py];
      for (let k = 0; k < 4; k++) {
        ang += aleatorio(-0.35, 0.35);
        px = limitar(px + Math.cos(ang) * aleatorio(5, 11), v.x0, v.x1);
        py = limitar(py + Math.sin(ang) * aleatorio(5, 11), v.y0, v.y1);
        linha.push(px, py);
      }
      v.trincas.push(linha);
    }
    v.fx = x;
    v.fy = y;
    const j = this.j;
    j.part.explosao(x, y, { n: 10, tex: "fx_caco", vel: [60, 260], ang: [20, 160], vida: [0.6, 1.2], tam: [8, 16],
      cor: "#dff3ff", alfa: 0.85, grav: 1200, giro: [-12, 12] });
    j.brilho(x, y, 160, "#fff0c7", 0.7, 0.3);
    if (comSom) this.api.som("vidro");
  }

  // Os 5 primeiros tiros na janela valem +50 (bônus, sem combo); no 5º o
  // que sobrou do vidro desaba.
  pagarJanela(x, y) {
    const j = this.j;
    this.janelaPagos++;
    j.bonus(50, x, y + 21 * K, "#c7edff", 1.1);
    if (this.janelaPagos === 1) j.instrucao("JANELA! +50 NOS 5 PRIMEIROS TIROS", "#d1f0ff");
    if (this.janelaPagos >= 5) {
      for (const v of this.janela) if (!v.quebrada) this.quebrarVidraca(v, (v.x0 + v.x1) / 2, (v.y0 + v.y1) / 2, false);
      this.solForca = 2.2;
      j.tremer(5);
      j.instrucao("JANELA DESTRUÍDA!", "#d1f0ff");
    }
  }

  lascar(x, y, papel) {
    const j = this.j;
    this.furo(x, y);
    // tiro na tábua sacode as garrafas que estão em cima dela
    for (const prat of [100, 80, 50, 20]) {
      if (y > (BAR.pe[prat] - 10) * K && y < (BAR.base[prat] + 4) * K) this.balancar(prat, x, 0.06);
    }
    if (papel) {
      j.part.explosao(x, y, { n: 7, tex: "fx_caco", vel: [60, 180], vida: [0.9, 1.6], tam: [10, 18], cor: "#ebd9a8",
        grav: 260, giro: [-6, 6], arrasto: 2 });
    } else {
      j.part.explosao(x, y, { n: 9, tex: "mar_farpa", vel: [140, 340], vida: [0.5, 0.9], tam: [18, 30], cor: "#9e6633",
        grav: 1200, giro: [-16, 16] });
      j.part.explosao(x, y, { n: 2, tex: "fx_nuvem", vel: [10, 30], vida: [0.5, 0.9], tam: [28, 40], fim: 1.6,
        cor: "#8c6640", alfa: 0.45 });
    }
    this.api.som("quica");
  }

  // O furo da bala: na frente das tábuas de cima ele fica por cima das
  // garrafas. Os mais velhos são reaproveitados (no máximo 24).
  furo(x, y) {
    let f;
    if (this.furos.length >= 24) {
      f = this.furos.shift();
    } else {
      f = {};
    }
    f.x = x;
    f.y = y;
    f.tam = 80 * aleatorio(0.42, 0.55) * K;
    f.rot = Math.random() * VOLTA;
    f.frente = BAR.beiradas.some(([a, b]) => y >= a && y <= b);
    this.furos.push(f);
  }

  manchar(x, y, cor, sx, sy) {
    let m;
    if (this.manchas.length >= 8) m = this.manchas.shift();
    else m = {};
    const e = aleatorio(0.85, 1.15) * 0.55 * 128 * K;
    m.x = x; m.y = y; m.w = sx * e; m.h = sy * e; m.rot = aleatorio(-0.3, 0.3); m.cor = cor; m.a = 0.5; m.t = 0;
    this.manchas.push(m);
  }

  // Tiro perto: as garrafas da mesma tábua balançam (mais forte quanto
  // mais perto), girando no pé.
  balancar(prat, x, forca) {
    for (const g of this.garrafas) {
      if (g.saindo || g.prat !== prat) continue;
      const f = forca * (1 - Math.abs(g.x - x) / (210 * K));
      if (f > Math.abs(g.balanco)) {
        g.balanco = Math.random() < 0.5 ? f : -f;
        g.balancoT = 0;
      }
    }
  }

  encerrou() {
    for (const g of this.garrafas) if (!g.saindo) this.retirar(g);
    this.slots.clear();
    this.vagoAte.clear();
  }

  // ---------------------------------------------------------------- vida
  sempre(dt) {
    const j = this.j;
    this.t += dt;
    for (let i = this.garrafas.length - 1; i >= 0; i--) {
      const g = this.garrafas[i];
      if (g.entra >= 0) {
        g.entra += dt;
        if (g.entra >= 0.22) {
          g.entra = -1;
          // assentou na tábua: balança um pouco
          if (!g.saindo && Math.abs(g.balanco) < 0.045) { g.balanco = 0.045; g.balancoT = 0; }
        }
      }
      if (g.estalo >= 0) { g.estalo += dt; if (g.estalo >= 0.12) g.estalo = -1; }
      if (g.sai >= 0) { g.sai += dt; if (g.sai >= 0.26) { this.garrafas.splice(i, 1); continue; } }
      if (g.acertoT >= 0) {
        g.acertoT += dt;
        const q = Math.floor(g.acertoT * 16);
        if (q < g.f.acerto.length) g.frame = g.f.acerto[q];
        else if (g.acertoT > g.f.acerto.length / 16 + 0.2) { this.garrafas.splice(i, 1); continue; }
      }
      if (g.balanco !== 0) {
        g.balancoT += dt;
        const am = Math.exp(-g.balancoT * 5.5);
        if (am < 0.03) { g.balanco = 0; g.rot = 0; } else g.rot = g.balanco * am * Math.sin(g.balancoT * 23);
      }
    }
    // de vez em quando um reflexo corre no vidro de uma garrafa
    if (this.garrafas.length && Math.random() < dt * 0.9 * j.fator) {
      const g = sorteio(this.garrafas);
      if (!g.saindo && g.entra < 0) {
        const img = j.tinta("fx_estrela", "#fff2d1");
        j.luz.soltar(g.x - g.f.w * g.esc * aleatorio(0.05, 0.2), g.pe - g.f.h * g.esc * aleatorio(0.45, 0.7), 0,
          -aleatorio(4, 10) * K, aleatorio(0.35, 0.55), aleatorio(16, 26) * K, 2 * K, img, 0.85, 0, 0, 2.5);
      }
    }
    // poeira brilhando dentro do feixe de sol
    if (Math.random() < dt * 7 * j.fator) {
      const i = ((Math.random() * POEIRA_BAR.length) / 2) | 0;
      j.luz.soltar(POEIRA_BAR[i * 2] + aleatorio(-6, 6), POEIRA_BAR[i * 2 + 1] + aleatorio(-6, 6),
        aleatorio(-4, 8) * K, aleatorio(-2, 9) * K, aleatorio(3, 5), aleatorio(4, 7) * K, 2 * K,
        j.tinta("fx_ponto", "#ffe699"), 0.6, 0, 0);
    }
    if (this.jatos.length) {
      for (const jt of this.jatos) jt.t += dt;
      this.poca = Math.min(1, this.poca + dt * 0.05 * this.jatos.length);
    }
    // a bebida espirrada seca devagar
    for (const m of this.manchas) {
      m.t += dt;
      if (m.t > 4) m.a = Math.max(0, m.a - dt * 0.12);
    }
  }

  // ---------------------------------------------------------------- desenho
  desenharFundo(ctx) {
    const j = this.j;
    const fundo = this.api.img.fundo_bar;
    if (fundo) ctx.drawImage(fundo, 0, 0, W, H);
    // manchas da bebida na parede e no tampo
    for (const m of this.manchas) {
      if (m.a <= 0) continue;
      const img = j.tinta("fx_nuvem", m.cor);
      if (!img) break;
      ctx.globalAlpha = m.a;
      ctx.translate(m.x, m.y);
      ctx.rotate(m.rot);
      ctx.drawImage(img, -m.w / 2, -m.h / 2, m.w, m.h);
      ctx.rotate(-m.rot);
      ctx.translate(-m.x, -m.y);
    }
    ctx.globalAlpha = 1;
    this.desenharFuros(ctx, false);
    this.desenharVinho(ctx);
    this.desenharJanela(ctx);
  }

  desenharFuros(ctx, frente) {
    const img = this.j.peca;
    for (const f of this.furos) {
      if (f.frente !== frente) continue;
      ctx.translate(f.x, f.y);
      ctx.rotate(f.rot);
      img(ctx, "bar_furo_madeira", -f.tam / 2, -f.tam / 2, f.tam, f.tam);
      ctx.rotate(-f.rot);
      ctx.translate(-f.x, -f.y);
    }
  }

  // A janela: a vidraça estourada deixa o sol entrar mais forte, com as
  // trincas saindo do furo e as pontas presas na moldura.
  desenharJanela(ctx) {
    for (const v of this.janela) {
      if (!v.quebrada) continue;
      const w = v.x1 - v.x0, h = v.y1 - v.y0;
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.32 + 0.06 * Math.sin(this.t * 1.7);
      ctx.fillStyle = "#ffcf80";
      ctx.fillRect(v.x0, v.y0, w, h);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 0.45;
      ctx.fillStyle = "#e6f6ff";
      ctx.beginPath();
      ctx.moveTo(v.x0, v.y0); ctx.lineTo(v.x0 + w * 0.35, v.y0); ctx.lineTo(v.x0, v.y0 + h * 0.3); ctx.closePath();
      ctx.moveTo(v.x1, v.y1); ctx.lineTo(v.x1 - w * 0.4, v.y1); ctx.lineTo(v.x1, v.y1 - h * 0.25); ctx.closePath();
      ctx.moveTo(v.x1, v.y0); ctx.lineTo(v.x1, v.y0 + h * 0.22); ctx.lineTo(v.x1 - w * 0.18, v.y0); ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 0.75;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 0.9;
      ctx.beginPath();
      for (const l of v.trincas) {
        ctx.moveTo(l[0], l[1]);
        for (let i = 2; i < l.length; i += 2) ctx.lineTo(l[i], l[i + 1]);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // O vinho do barril: jato forte logo depois do tiro, que vira um fio
  // escorrendo até o pé do barril; a poça no chão cresce.
  desenharVinho(ctx) {
    if (!this.jatos.length) return;
    const pe = t46y(1424);
    if (this.poca > 0) {
      const cx = t46x(880), cy = pe + 7;
      const r = (40 + 150 * this.poca) * K;
      ctx.fillStyle = "#400309";
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      ctx.ellipse(cx, cy, r, r * 0.22, 0, 0, VOLTA);
      ctx.fill();
      ctx.fillStyle = "#8c1f29";
      ctx.globalAlpha = 0.35;
      const r2 = (20 + 70 * this.poca) * K;
      ctx.beginPath();
      ctx.ellipse(cx - 10, cy - 5, r2, r2 * 0.22, 0, 0, VOLTA);
      ctx.fill();
    }
    ctx.lineCap = "round";
    for (const jt of this.jatos) {
      const pressao = Math.exp(-jt.t);
      if (jt.t < 13) {
        ctx.globalAlpha = 0.85 * limitar((13 - jt.t) / 3, 0, 1);
        ctx.strokeStyle = "#4d050d";
        ctx.lineWidth = misturar(2, 7, pressao) * K;
        ctx.beginPath();
        ctx.moveTo(jt.x, jt.y);
        ctx.lineTo(jt.x + 2, pe);
        ctx.stroke();
      }
      if (pressao > 0.15) {
        const v0x = (-260 * pressao + jt.lado * 80) * K, v0y = -40 * pressao * K;
        ctx.globalAlpha = 0.95;
        ctx.strokeStyle = "#6b050f";
        ctx.lineWidth = (6 * pressao + 2) * K;
        ctx.beginPath();
        for (let i = 0; i < 12; i++) {
          const s = (i / 11) * 0.6;
          const px = jt.x + v0x * s, py = jt.y + v0y * s + 0.5 * 1400 * K * s * s;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  desenharAlvos(ctx) {
    const sombra = this.j.tinta("fx_brilho", "#0d0500");
    for (const g of this.garrafas) {
      if (!g.img) continue;
      let dy = 0, alfa = 1, esc = g.esc;
      if (g.entra >= 0) {
        const k = Math.min(1, g.entra / 0.22);
        dy = -70 * K * (1 - quique(k));
        alfa = Math.min(1, g.entra / 0.1);
      }
      if (g.sai >= 0) { const k = g.sai / 0.26; dy = -26 * K * k; alfa = 1 - k; }
      if (g.estalo >= 0) esc *= misturar(1.12, 1, saidaVolta(g.estalo / 0.12));
      if (g.acertoT >= 0) {
        const fimQ = g.f.acerto.length / 16;
        if (g.acertoT > fimQ) alfa = 1 - (g.acertoT - fimQ) / 0.2;
      }
      if (alfa <= 0) continue;
      // sombra de contato no tampo das tábuas de baixo (a luz vem da janela)
      if (g.prat <= 50 && g.acertoT < 0 && sombra) {
        const sw = g.f.w * g.esc * 1.5, sh = 25.6 * K;
        ctx.globalAlpha = alfa * 0.65 * (g.entra >= 0 ? Math.min(1, g.entra / 0.22) : 1);
        ctx.drawImage(sombra, g.x + 2.6 - sw / 2, g.pe + 0.5 - sh / 2, sw, sh);
      }
      ctx.globalAlpha = alfa;
      const dw = g.f.w * esc, dh = g.f.h * esc;
      const cw = g.img.width / g.f.q;
      ctx.translate(g.x, g.pe);
      if (g.rot) ctx.rotate(g.rot);
      ctx.drawImage(g.img, g.frame * cw, 0, cw, g.img.height, -dw / 2, -dh + g.vazio * esc + dy, dw, dh);
      if (g.rot) ctx.rotate(-g.rot);
      ctx.translate(-g.x, -g.pe);
    }
    ctx.globalAlpha = 1;
  }

  desenharFrente(ctx) {
    // A frente das duas tábuas de cima de novo, por cima do pé das garrafas
    // (o mesmo pedaço do fundo): a garrafa fica EM CIMA da tábua, atrás
    // da beirada — profundidade sem 3D, como na Mali-450.
    const fundo = this.api.img.fundo_bar;
    if (fundo) {
      const k = fundo.width / W;
      for (const [a, b] of BAR.beiradas) ctx.drawImage(fundo, 0, a * k, fundo.width, (b - a) * k, 0, a, W, b - a);
    }
    this.desenharFuros(ctx, true);
    // o sol pela janela: um feixe que respira, na frente das garrafas
    const nuvem = 0.86 + 0.14 * Math.sin(this.t * 0.21) * Math.sin(this.t * 0.137 + 1.3);
    if (!this.gradFeixe) {
      const g = ctx.createLinearGradient(40, 50, 420, 900);
      g.addColorStop(0, "rgba(255, 214, 140, 0.55)");
      g.addColorStop(0.45, "rgba(255, 190, 110, 0.22)");
      g.addColorStop(1, "rgba(255, 170, 90, 0)");
      this.gradFeixe = g;
    }
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.32 * nuvem * this.solForca;
    ctx.fillStyle = this.gradFeixe;
    caminhoPoligono(ctx, FEIXE_BAR);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
  }
}

/* ======================================================================
   DESERTO SAGRADO (deserto.gd)
   ====================================================================== */
const COR_SOL = "#ffbd2e";
const COR_LUA = "#8fd6ff";
const DES = {
  astro: [270, 187.5],
  poente: t46y(880) + 14,
  cristal: p46([506, 626, 546, 668, 560, 720, 558, 900, 536, 968, 478, 968, 454, 900, 452, 720, 466, 668]),
  pontas: [p46([209, 760, 195, 790, 193, 842, 225, 842, 223, 790]), p46([812, 760, 799, 790, 797, 842, 830, 842, 826, 790])],
  pontasCentro: [[t46x(209), t46y(800)], [t46x(812), t46y(800)]],
  ouro: [p46([509, 447, 449, 524, 509, 501, 546, 497]), p46([229, 519, 170, 580, 229, 558, 256, 554]),
    p46([774, 519, 721, 582, 774, 560, 806, 556])],
  piramides: [p46([508, 444, 298, 742, 718, 742]), p46([229, 516, 120, 700, 340, 700]), p46([775, 516, 680, 700, 900, 700])],
  feixes: [p46([488, 664, 207, 783]), p46([528, 666, 815, 783]), p46([482, 856, 224, 992]), p46([536, 862, 800, 992])],
  saidas: [[t46x(507), t46y(760)], [t46x(209), t46y(880)], [t46x(812), t46y(880)]],
  horizonte: p46([224, 516, 200, 550, 200, 998, 822, 998, 822, 574, 778, 514, 770, 518, 690, 632, 666, 660, 636, 624,
    510, 444, 502, 448, 382, 620, 348, 660, 336, 660, 326, 650, 230, 514]),
  horizonteY: t46y(700),
  centroCristal: [t46x(506), t46y(800)],
  brilhosOuro: [[t46x(229), t46y(520)], [t46x(509), t46y(448)], [t46x(774), t46y(520)]],
};
// O olho do astro (ASTRO de deserto.gd): px da textura do olho, que na
// tela lógica valem a metade.
const OLHO = { cx: -7.48, cy: -1.875, irisY: -2.14, esclW: 145, esclH: 69.5, iris: 47, disco: 174.5 };
const HUMORES = {
  calmo: { topo: 0.16, alcance: 0.55 }, feliz: { topo: 0.08, alcance: 0.35 }, radiante: { topo: 0.1, alcance: 0.25 },
  atento: { topo: 0.1, alcance: 1 }, bravo: { topo: 0.42, alcance: 0.7 }, surpreso: { topo: 0.04, alcance: 0.3 },
};
const OLHADAS = [[0, 0], [-0.3, 0], [0.3, 0], [-0.22, -0.04], [0.22, -0.04], [0, -0.04], [-0.12, 0.03], [0.12, 0.03]];
const TRACO = [7, 15];
const SEM_TRACO = [];

class CenarioDeserto {
  constructor(j) {
    this.j = j;
    this.api = j.api;
    this.modo = "sol";
    this.tempoModo = 0;
    this.nivel = 1;
    this.alvos = [];
    this.spawnT = 0;
    this.noite = 0;
    this.troca = null;
    this.astros = { sol: this.novoAstro(true), lua: this.novoAstro(false) };
    this.carga = 0;
    this.cristal = { danos: 0, quebrado: false, volta: 0, trincas: [], tremor: 0 };
    this.pontas = [{ danos: 0, quebrada: false, volta: 0 }, { danos: 0, quebrada: false, volta: 0 }];
    this.raios = [];
    this.furos = [];
    this.humor = "calmo";
    this.reacao = "";
    this.reacaoT = 0;
    this.espiarT = 0;
    this.espiarX = 0;
    this.espiarY = 0;
    this.errosRecentes = 0;
    this.t = 0;
    this.estrelas = [];
    for (let i = 0; i < 16; i++) {
      this.estrelas.push({ x: aleatorio(120, 904) * K, y: aleatorio(70, 560) * K, tam: aleatorio(12, 26) * K,
        fase: Math.random() * VOLTA, vel: aleatorio(1.2, 3.6), brilho: aleatorio(0.35, 0.9) });
    }
  }

  novoAstro(visivel) {
    return { visivel, y: DES.astro[1], sono: 0, sonoAlvo: 0, olharX: 0, olharY: 0, alvoX: 0, alvoY: 0, prox: 1,
      piscarT: aleatorio(1.5, 3.5), fase: -1, dupla: false, topo: 0.16 };
  }

  preparar() {}

  comecar() {
    this.modo = "sol";
    this.tempoModo = 0;
    this.spawnT = 0;
    for (let i = 0; i < 3; i++) this.nascer(i === 0 ? this.modo : this.sortearTipo());
  }

  podeAtirar() { return true; }

  estiloTiro() { return this.modo; }

  extra() {
    return ["MODO", this.modo === "sol" ? "SOL" : "LUA", this.modo === "sol" ? COR_SOL : COR_LUA];
  }

  // ---------------------------------------------------------------- partida
  atualizar(dt) {
    const p = this.j.pontos;
    this.nivel = p < 800 ? 1 : Math.min(5.2, 1 + Math.floor((p - 800) / 450) * 0.55);
    this.tempoModo += dt;
    if (this.tempoModo >= 30) {
      this.tempoModo = 0;
      this.trocarModo();
    }
    this.spawn(dt);
    this.moverAlvos(dt);
    this.errosRecentes = Math.max(0, this.errosRecentes - dt * 0.4);
  }

  // O dia vira noite: o astro de agora fecha o olho e se põe atrás das
  // pirâmides, o céu escurece e o outro nasce do mesmo lugar.
  trocarModo() {
    const antigo = this.modo;
    this.modo = antigo === "sol" ? "lua" : "sol";
    this.j.instrucao("MODO " + this.modo.toUpperCase(), clarear(this.modo === "sol" ? COR_SOL : COR_LUA, 0.3));
    this.troca = { t: 0, sai: this.astros[antigo], entra: this.astros[this.modo], paraNoite: this.modo === "lua" };
    this.troca.sai.sonoAlvo = 1;
    this.troca.entra.sono = 1;
    this.troca.entra.sonoAlvo = 1;
    this.troca.entra.visivel = true;
    this.troca.entra.y = DES.poente;
    this.j.clarao(this.modo === "sol" ? "#ffd999" : "#80a6ff", 0.12, 0.8);
    this.api.som("whoosh");
  }

  maxAlvos() {
    let base = 7;
    if (this.j.pontos >= 1500) base++;
    return Math.min(11, base + Math.floor(this.nivel - 1));
  }

  sortearTipo() {
    let certo = this.j.pontos < 1500 ? 0.58 : 0.5;
    certo = limitar(certo - (this.nivel - 1) * 0.03, 0.4, 0.62);
    if (Math.random() < certo) return this.modo;
    return this.modo === "sol" ? "lua" : "sol";
  }

  spawn(dt) {
    if (this.alvos.length >= this.maxAlvos()) return;
    this.spawnT -= dt;
    if (this.spawnT > 0) return;
    const intervalo = Math.max(0.36, 0.595 - (this.nivel - 1) * 0.07);
    this.spawnT = aleatorio(intervalo * 0.65, intervalo * 1.35);
    this.nascer(this.sortearTipo());
  }

  nascer(tipo) {
    const a = { tipo, idade: 0, flash: 0, preso: 0, lVirou: false, trocou: true, trocaEm: 0, fase: Math.random() * 9 };
    let rapidez = aleatorio(215, 330) * (1 + (this.nivel - 1) * 0.15);
    if (this.j.pontos >= 800) rapidez *= 1.1;
    rapidez *= K;
    a.velBase = rapidez;
    a.tam = aleatorio(0.86, 1.16);
    a.saida = Math.random() < 0.5 ? "perto" : "longe";
    const r = Math.random();
    a.estilo = r < 0.45 ? "lado" : r < 0.72 ? "alto_l" : "surge";
    const yMin = 330 * K, yMax = H - 180 * K;
    let vx, vy;
    if (a.estilo === "alto_l") {
      a.entrada = 0.8;
      a.x = aleatorio(170 * K, W - 170 * K);
      a.y = yMin - 260 * K;
      vx = aleatorio(-0.1, 0.1); vy = 1;
      const n = Math.hypot(vx, vy);
      vx = (vx / n) * rapidez * 1.3; vy = (vy / n) * rapidez * 1.3;
    } else if (a.estilo === "surge") {
      // sai de trás do cristal ou de um obelisco, num clarão
      a.entrada = 0.55;
      const c = sorteio(DES.saidas);
      a.x = c[0]; a.y = c[1];
      const lado = Math.abs(c[0] - W / 2) > 21 ? Math.sign(c[0] - W / 2) : Math.random() < 0.5 ? 1 : -1;
      vx = lado; vy = aleatorio(-0.7, -0.15);
      const n = Math.hypot(vx, vy);
      vx = (vx / n) * rapidez; vy = (vy / n) * rapidez;
      this.j.luz.explosao(c[0], c[1], { n: 10, vel: [60, 200], vida: [0.3, 0.6], tam: [10, 22],
        cor: clarear(tipo === "sol" ? COR_SOL : COR_LUA, 0.4), arrasto: 2 });
    } else {
      a.entrada = 0.6;
      const m = (Math.random() * 3) | 0;
      if (m === 0) { a.x = -58; a.y = aleatorio(yMin + 32, yMax - 32); vx = aleatorio(230, 360); vy = aleatorio(-120, 120); }
      else if (m === 1) { a.x = W + 58; a.y = aleatorio(yMin + 32, yMax - 32); vx = -aleatorio(230, 360); vy = aleatorio(-120, 120); }
      else { a.x = aleatorio(84, W - 84); a.y = H + 58; vx = aleatorio(-140, 140); vy = -aleatorio(240, 380); }
      const n = Math.hypot(vx, vy);
      vx = (vx / n) * rapidez; vy = (vy / n) * rapidez;
    }
    a.vx = vx; a.vy = vy;
    a.vida = Math.max(2.4, aleatorio(3.0, 3.8) - (this.nivel - 1) * 0.2);
    a.guinada = aleatorio(0.5, 1.1);
    a.valor = sorteio([20, 50, 80, 100]);
    a.penal = sorteio([20, 50, 80, 100]);
    // alguns trocam de brasão no meio do voo (mais com os pontos)
    let chance = 0.25 + (this.nivel - 1) * 0.06;
    if (tipo === this.modo) {
      chance += Math.floor(this.j.pontos / 1000) * 0.07;
      chance += limitar(this.tempoModo / 30, 0, 1) * 0.12;
    }
    chance = limitar(chance, 0, 0.55);
    if (a.vida >= 1.8 && Math.random() < chance) {
      const tMin = misturar(0.55, 0.35, chance / 0.55), tMax = misturar(0.75, 0.6, chance / 0.55);
      a.trocaEm = Math.max(a.vida * aleatorio(tMin, tMax), a.entrada + 0.2);
      a.trocou = false;
    }
    a.esc = 0;
    a.alfa = 0;
    a.rot = 0;
    this.alvos.push(a);
  }

  diametro(a) {
    return misturar(196, 128, limitar(a.idade / Math.max(a.vida, 0.01), 0, 1)) * a.tam * K;
  }

  moverAlvos(dt) {
    for (let i = this.alvos.length - 1; i >= 0; i--) {
      const a = this.alvos[i];
      a.idade += dt;
      if (a.flash > 0) a.flash = Math.max(0, a.flash - dt);
      if (!a.trocou && a.idade >= a.trocaEm) this.trocarTipo(a);
      if (a.idade >= a.vida) { this.alvos.splice(i, 1); continue; }
      const entrando = a.idade < a.entrada;
      const saindo = a.idade > a.vida - 0.55;
      if (a.estilo === "alto_l" && !a.lVirou && a.idade >= a.entrada * 0.8) {
        a.lVirou = true;
        const lado = a.x < W / 2 ? 1 : -1;
        let vx = lado, vy = aleatorio(-0.18, 0.12);
        const n = Math.hypot(vx, vy);
        a.vx = (vx / n) * a.velBase; a.vy = (vy / n) * a.velBase;
      }
      if (!entrando) {
        a.guinada -= dt;
        if (a.guinada <= 0) {
          a.guinada = aleatorio(0.55, 1.3) / Math.sqrt(this.nivel);
          const ang = aleatorio(35, 85) * RAD * (Math.random() < 0.5 ? 1 : -1);
          const c = Math.cos(ang), s = Math.sin(ang);
          const vx = a.vx * c - a.vy * s;
          a.vy = a.vx * s + a.vy * c;
          a.vx = vx;
        }
      }
      const raio = this.diametro(a) * 0.5;
      const x0 = raio, x1 = W - raio, y0 = 330 * K + raio * 0.3, y1 = H - raio - 120 * K;
      if (!entrando && !saindo) {
        const empurra = () => aleatorio(20, 70) * K;
        if (a.x < x0) { a.x = x0; a.vx = Math.abs(a.vx) + empurra(); a.vy += aleatorio(-60, 60) * K; }
        if (a.x > x1) { a.x = x1; a.vx = -(Math.abs(a.vx) + empurra()); a.vy += aleatorio(-60, 60) * K; }
        if (a.y < y0) { a.y = y0; a.vy = Math.abs(a.vy) + empurra(); a.vx += aleatorio(-60, 60) * K; }
        if (a.y > y1) { a.y = y1; a.vy = -(Math.abs(a.vy) + empurra()); a.vx += aleatorio(-60, 60) * K; }
      }
      let vm = Math.hypot(a.vx, a.vy);
      const teto = a.velBase * (entrando ? 1.35 : 1.15);
      if (vm > teto) { a.vx *= teto / vm; a.vy *= teto / vm; vm = teto; }
      if (vm < 140 * K) {
        if (vm < 0.01) { const ang = Math.random() * VOLTA; a.vx = Math.cos(ang); a.vy = Math.sin(ang); vm = 1; }
        a.vx = (a.vx / vm) * 140 * K; a.vy = (a.vy / vm) * 140 * K;
      }
      const canto = !entrando && !saindo && (a.x <= x0 + 4 || a.x >= x1 - 4) && (a.y <= y0 + 4 || a.y >= y1 - 4);
      if (canto) {
        a.preso += dt;
        if (a.preso >= 0.35) {
          const dx = W / 2 - a.x, dy = (y0 + y1) / 2 - a.y, n = Math.hypot(dx, dy) || 1;
          a.vx = (dx / n) * 308 * K; a.vy = (dy / n) * 308 * K;
          a.preso = 0;
        }
      } else a.preso = 0;
      a.x += a.vx * dt;
      a.y += a.vy * dt;
      // tamanho: entra crescendo, sai para perto (cresce e some) ou longe
      let esc = this.diametro(a) / FOLHAS.brasao_sol.w;
      let alfa = 1;
      if (entrando) {
        const k = a.idade / a.entrada;
        esc *= a.estilo === "surge" ? k : misturar(0.7, 1, k);
        alfa = limitar(k * 2, 0, 1);
      } else if (saindo) {
        const k = (a.idade - (a.vida - 0.55)) / 0.55;
        esc *= a.saida === "perto" ? 1 + 0.35 * k : 1 - 0.6 * k;
        alfa = 1 - k;
      }
      a.esc = esc;
      a.alfa = alfa;
      a.rot = Math.sin(a.idade * 2.3 + a.fase) * 0.12;
    }
    // brasões não se sobrepõem: os que se encostam se empurram
    const n = this.alvos.length;
    for (let i = 0; i < n; i++) {
      const a = this.alvos[i];
      for (let k = i + 1; k < n; k++) {
        const b = this.alvos[k];
        const dx = b.x - a.x, dy = b.y - a.y;
        const r = (this.diametro(a) + this.diametro(b)) * 0.4;
        const d = Math.hypot(dx, dy);
        if (d > 0.01 && d < r) {
          const ex = (dx / d) * (r - d) * 0.5, ey = (dy / d) * (r - d) * 0.5;
          a.x -= ex; a.y -= ey; b.x += ex; b.y += ey;
          const vn = (b.vx - a.vx) * (dx / d) + (b.vy - a.vy) * (dy / d);
          if (vn < 0) {
            a.vx += (dx / d) * vn * 0.6; a.vy += (dy / d) * vn * 0.6;
            b.vx -= (dx / d) * vn * 0.6; b.vy -= (dy / d) * vn * 0.6;
          }
        }
      }
    }
  }

  trocarTipo(a) {
    a.trocou = true;
    a.tipo = a.tipo === "sol" ? "lua" : "sol";
    a.flash = 0.45;
    a.vida = a.idade + aleatorio(1.4, 2.2) + 0.55;
    const ang = aleatorio(-Math.PI * 0.25, Math.PI * 0.25);
    const c = Math.cos(ang), s = Math.sin(ang);
    const vx = a.vx * c - a.vy * s;
    a.vy = a.vx * s + a.vy * c;
    a.vx = vx;
    this.j.luz.explosao(a.x, a.y, { n: 8, vel: [80, 220], vida: [0.25, 0.5], tam: [10, 20], cor: BRANCO, alfa: 0.9, arrasto: 2.5 });
  }

  alvoNoPonto(x, y) {
    let melhor = -1, dMelhor = Infinity;
    for (let passo = 0; passo < 2 && melhor < 0; passo++) {
      for (let i = this.alvos.length - 1; i >= 0; i--) {
        const a = this.alvos[i];
        if (a.alfa < 0.5 || a.esc <= 0) continue;
        const f = FOLHAS["brasao_" + a.tipo];
        paraQuadro(x, y, a.x, a.y, a.rot, a.esc, a.esc, LOCAL);
        const folga = passo === 0 ? f.w / 24 : TOQUE / a.esc;
        if (!naMascara(f, LOCAL[0], LOCAL[1], folga, folga)) continue;
        if (passo === 0) return i;
        const d = Math.hypot(LOCAL[0], LOCAL[1]);
        if (d < dMelhor) { dMelhor = d; melhor = i; }
      }
    }
    return melhor;
  }

  // ---------------------------------------------------------------- tiro
  tiro(x, y) {
    this.espiarX = x;
    this.espiarY = y;
    this.espiarT = 0.6;
    const i = this.alvoNoPonto(x, y);
    if (i >= 0) { this.acertouBrasao(i, x, y); return; }
    if (dentro(x, y, DES.cristal)) { this.ferirCristal(x, y); return; }
    for (let k = 0; k < 2; k++) if (dentro(x, y, DES.pontas[k])) { this.ferirPonta(k, x, y); return; }
    this.errosRecentes += 1;
    this.j.errar(x, y, "ERRO!");
    this.reagir("atento", 1);
    for (const o of DES.ouro) {
      if (dentro(x, y, o)) {
        // o ouro das pirâmides solta faíscas
        this.j.luz.explosao(x, y, { n: 10, tex: "fx_faisca", vel: [80, 240], vida: [0.3, 0.6], tam: [10, 16], cor: "#ffd966",
          grav: 600, estica: 0.04 });
        return;
      }
    }
    for (const p of DES.piramides) if (dentro(x, y, p)) return;   // lá longe: a bala não chega
    if (y <= DES.horizonteY) return;                               // céu
    const qx = (x + 50) / 0.625, qy = y / 0.625;
    if (qx < 120 || qx > 904 || Math.hypot(qx - 510, qy - 1180) < 300) this.lascarPedra(x, y, true);
    else if (qy < 1010) this.lascarPedra(x, y, false);
    else this.furarAreia(x, y);
  }

  acertouBrasao(i, x, y) {
    const j = this.j;
    const a = this.alvos[i];
    this.alvos.splice(i, 1);
    const lua = a.tipo === "lua";
    if (a.tipo === this.modo) {
      j.registrarCombo(a.tipo);
      const bonusCombo = j.combo >= 3 ? j.combo * 5 : 0;
      j.ganhar(a.valor + bonusCombo, a.x, a.y, lua ? "#e0f0ff" : "#ffd64d", 1 + (bonusCombo > 0 ? 0.2 : 0));
      this.api.som("acerto");
      this.explodirBrasao(a, x, y, true);
      this.carregarCristal();
      this.reagir(j.combo < 6 ? "feliz" : "radiante", 1.2);
    } else {
      this.carga = Math.max(0, this.carga - 0.25);
      j.perder(a.penal, a.x, a.y, a.tipo.toUpperCase() + " -" + a.penal);
      this.api.som("erro");
      this.explodirBrasao(a, x, y, false);
      j.clarao("#ff1a0d", 0.16, 0.25);
      this.reagir("bravo", 1.6);
    }
  }

  // O brasão trinca (o quadro mais quebrado) e se parte em cacos de ouro
  // ou prata; um clarão e faíscas na cor do astro.
  explodirBrasao(a, x, y, certo) {
    const j = this.j;
    const f = FOLHAS["brasao_" + a.tipo];
    const img = this.api.img["brasao_" + a.tipo];
    const c = a.tipo === "sol" ? COR_SOL : COR_LUA;
    if (img) {
      const cw = img.width / f.q;
      j.cacos.estourar(img, cw * 3, 0, cw, img.height, f.w, f.h, a.x, a.y, a.esc, a.rot, x, y,
        { n: 12, forca: certo ? 1.1 : 0.8, vida: 0.9, sobe: 200 });
    }
    j.luz.explosao(a.x, a.y, { n: 18, vel: [180, 520], vida: [0.3, 0.7], tam: [8, 16], cor: certo ? clarear(c, 0.35) : "#ff4d33",
      grav: 300, estica: 0.03, arrasto: 1.2 });
    j.brilho(a.x, a.y, (this.diametro(a) / K) * 2.2, certo ? c : "#ff4033", certo ? 0.8 : 0.7, 0.35);
  }

  // Cada acerto certo carrega o cristal; cheio, ele descarrega nos
  // brasões certos da tela (POWER OF RA!). Quebrado, não carrega.
  carregarCristal() {
    if (this.cristal.quebrado) return;
    this.carga = Math.min(1, this.carga + 0.125);
    if (this.carga < 1) return;
    this.carga = 0;
    const j = this.j;
    const pegos = [];
    for (let i = this.alvos.length - 1; i >= 0; i--) {
      const a = this.alvos[i];
      if (a.tipo === this.modo && a.alfa >= 0.5) { this.alvos.splice(i, 1); pegos.push(a); }
    }
    j.especial("POWER OF RA!");
    j.clarao("#ffd966", 0.28, 0.5);
    j.tremer(10);
    const origens = [];
    for (let k = 0; k < 2; k++) {
      if (!this.pontas[k].quebrada) origens.push([DES.pontasCentro[k][0], DES.pontasCentro[k][1] - 30 * 0.625]);
    }
    if (!origens.length) origens.push([t46x(506), t46y(640)]);
    let soma = 0;
    for (const a of pegos) {
      const o = sorteio(origens);
      this.raios.push({ t: 0, pts: this.raioQuebrado(o[0], o[1], a.x, a.y) });
      soma += a.valor;
      j.pontos += a.valor;
      j.pop(a.x, a.y, "+" + a.valor, "#ffe680", 1.1);
      this.explodirBrasao(a, a.x, a.y, true);
    }
    j.instrucao(pegos.length ? "DESCARGA DO CRISTAL! +" + soma : "DESCARGA DO CRISTAL!", "#ffdb5c");
  }

  raioQuebrado(x0, y0, x1, y1) {
    const pts = [x0, y0];
    const n = 9;
    const d = Math.hypot(x1 - x0, y1 - y0) || 1;
    const px = -(y1 - y0) / d, py = (x1 - x0) / d;
    for (let i = 1; i < n; i++) {
      const k = i / n;
      const e = aleatorio(-36, 36) * K * Math.sin(k * Math.PI);
      pts.push(misturar(x0, x1, k) + px * e, misturar(y0, y1, k) + py * e);
    }
    pts.push(x1, y1);
    return pts;
  }

  ferirCristal(x, y) {
    const j = this.j;
    const cr = this.cristal;
    if (cr.quebrado) {
      j.part.explosao(x, y, { n: 4, tex: "fx_caco", vel: [80, 180], vida: [0.4, 0.7], tam: [8, 14], cor: "#595973", grav: 900, giro: [-10, 10] });
      j.errar(x, y, "CRISTAL QUEBRADO");
      return;
    }
    cr.danos++;
    cr.tremor = 1;
    this.reagir("surpreso", 0.8);
    // trinca: 2 a 3 galhos saindo do ponto, presos dentro do cristal
    const galhos = 2 + ((Math.random() * 2) | 0);
    for (let g = 0; g < galhos; g++) {
      const linha = [x, y];
      let ang = Math.random() * VOLTA;
      const passos = 4 + ((Math.random() * 4) | 0);
      for (let k = 0; k < passos; k++) {
        ang += aleatorio(-0.6, 0.6);
        const qx = linha[linha.length - 2] + Math.cos(ang) * aleatorio(9, 21) * K;
        const qy = linha[linha.length - 1] + Math.sin(ang) * aleatorio(9, 21) * K;
        if (!dentro(qx, qy, DES.cristal)) break;
        linha.push(qx, qy);
      }
      if (linha.length > 2) cr.trincas.push(linha);
    }
    while (cr.trincas.length > 40) cr.trincas.shift();
    const c = this.noite > 0.5 ? "#ff4059" : "#ff8ce6";
    j.part.explosao(x, y, { n: 9, tex: "fx_caco", vel: [140, 300], vida: [0.4, 0.8], tam: [8, 16], cor: c, grav: 900,
      giro: [-12, 12], fim: 0.6 });
    j.brilho(x, y, 150, c, 1, 0.35);
    if (cr.danos >= 9) this.quebrarCristal(x, y);
    else {
      this.api.som("nota");
      j.mostrar(x, y, "CRISTAL " + cr.danos + "/9", clarear(c, 0.4));
    }
  }

  quebrarCristal(x, y) {
    const j = this.j;
    const cr = this.cristal;
    cr.quebrado = true;
    cr.volta = 30;
    cr.trincas.length = 0;
    this.carga = 0;
    // o cristal se parte em cacos da própria pintura do fundo
    const fundo = this.api.img[this.modo === "lua" ? "fundo_egito_lua" : "fundo_egito_sol"];
    if (fundo) {
      const k = fundo.width / W;
      const rx = 242, ry = 395, rw = 48, rh = 205;
      j.cacos.estourar(fundo, rx * k, ry * k, rw * k, rh * k, rw, rh, rx + rw / 2, ry + rh / 2, 1, 0, x, y,
        { n: 18, forca: 1.5, vida: 1.3, sobe: 380 });
    }
    const c = this.noite > 0.5 ? "#ff4d66" : "#ff99f2";
    const [cx, cy] = DES.centroCristal;
    j.luz.explosao(cx, cy, { n: 30, vel: [200, 650], vida: [0.4, 0.9], tam: [10, 22], cor: c, grav: 500, estica: 0.03, espalha: 60 });
    j.brilho(cx, cy, 700, c, 1, 0.6);
    j.clarao("#ffffff", 0.35, 0.45);
    j.tremer(12);
    this.api.som("strike");
    j.bonus(300, x, y, this.modo === "sol" ? "#ffcc3d" : "#e6f2ff", 1.5);
    j.instrucao("CRISTAL QUEBRADO! +300", "#ffd980");
  }

  ferirPonta(k, x, y) {
    const j = this.j;
    const pt = this.pontas[k];
    this.carga = Math.max(0, this.carga - 0.5);
    if (pt.quebrada) {
      this.lascarPedra(x, y, true);
      j.errar(x, y, "ERRO!");
      return;
    }
    pt.danos++;
    const c = this.noite > 0.5 ? "#ff4d66" : "#ff80d9";
    j.part.explosao(x, y, { n: 6, tex: "fx_caco", vel: [120, 260], vida: [0.4, 0.7], tam: [7, 12], cor: c, grav: 900, giro: [-12, 12] });
    j.brilho(x, y, 110, c, 1, 0.35);
    if (pt.danos >= 4) {
      pt.quebrada = true;
      pt.volta = 22;
      const [cx, cy] = DES.pontasCentro[k];
      j.luz.explosao(cx, cy, { n: 16, vel: [150, 420], vida: [0.3, 0.7], tam: [8, 16], cor: c, grav: 600, estica: 0.03 });
      j.part.explosao(cx, cy, { n: 4, tex: "fx_fumaca", vel: [10, 50], ang: [240, 300], vida: [1, 1.8], tam: [30, 50], fim: 2,
        cor: "#40332e", alfa: 0.6, grav: -30 });
      this.api.som("vidro");
      j.bonus(150, x, y, this.modo === "sol" ? "#ffcc3d" : "#e6f2ff", 1.3);
      j.instrucao("CRISTAL DO OBELISCO! +150", "#ffd980");
    } else this.api.som("nota");
  }

  lascarPedra(x, y, furo) {
    const j = this.j;
    j.part.explosao(x, y, { n: 7, tex: "fx_caco", vel: [120, 280], ang: [190, 350], vida: [0.4, 0.8], tam: [6, 11],
      cor: "#9c7a52", grav: 900, giro: [-12, 12] });
    j.part.explosao(x, y, { n: 2, tex: "fx_nuvem", vel: [10, 30], vida: [0.6, 1.0], tam: [30, 44], fim: 1.7, cor: "#b39470", alfa: 0.4 });
    if (furo) this.furo(x, y, "fx_furo_pedra", 26);
  }

  furarAreia(x, y) {
    const j = this.j;
    this.furo(x, y, "fx_furo_areia", 52);
    j.part.explosao(x, y, { n: 3, tex: "fx_nuvem", vel: [20, 60], ang: [220, 320], vida: [0.8, 1.3], tam: [44, 64], fim: 2,
      cor: "#d9b880", alfa: 0.5, grav: -20 });
    j.part.explosao(x, y, { n: 6, tex: "fx_ponto", vel: [80, 220], ang: [230, 310], vida: [0.4, 0.7], tam: [5, 9],
      cor: "#e6c38c", grav: 900 });
  }

  furo(x, y, tex, tam) {
    const f = this.furos.length >= 16 ? this.furos.shift() : {};
    f.x = x; f.y = y; f.tex = tex; f.tam = tam * aleatorio(0.85, 1.15); f.rot = aleatorio(-0.4, 0.4); f.t = 0;
    this.furos.push(f);
  }

  reagir(h, dur) {
    this.reacao = h;
    this.reacaoT = dur;
  }

  encerrou() {
    for (const a of this.alvos) a.vida = Math.min(a.vida, a.idade + 0.55);
    this.reagir("calmo", 99);
  }

  // ---------------------------------------------------------------- vida
  sempre(dt) {
    const j = this.j;
    this.t += dt;
    if (j.estado === "fim") {
      // os brasões que sobraram somem para longe
      for (let i = this.alvos.length - 1; i >= 0; i--) {
        const a = this.alvos[i];
        a.idade += dt;
        const k = (a.idade - (a.vida - 0.55)) / 0.55;
        if (k >= 1) { this.alvos.splice(i, 1); continue; }
        if (k > 0) a.alfa = 1 - k;
      }
    }
    // a troca do dia: um se põe, o outro nasce
    const tr = this.troca;
    if (tr) {
      tr.t += dt;
      tr.sai.y = misturar(DES.astro[1], DES.poente, senoEntra(Math.min(1, tr.t / 2.6)));
      if (tr.t > 1.5) tr.entra.y = misturar(DES.poente, DES.astro[1], senoSai(Math.min(1, (tr.t - 1.5) / 2.8)));
      const k = limitar((tr.t - 0.5) / 2.6, 0, 1);
      this.noite = tr.paraNoite ? k : 1 - k;
      if (tr.t > 1.5 + 2.8 * 0.55) tr.entra.sonoAlvo = 0;
      if (tr.t >= 1.5 + 2.8) {
        tr.sai.visivel = false;
        tr.sai.sono = 0;
        tr.sai.sonoAlvo = 0;
        this.troca = null;
      }
    }
    if (this.reacaoT > 0) { this.reacaoT -= dt; if (this.reacaoT <= 0) this.reacao = ""; }
    this.espiarT = Math.max(0, this.espiarT - dt);
    for (const nome of ["sol", "lua"]) if (this.astros[nome].visivel) this.animarOlho(this.astros[nome], dt);
    // o cristal e as pontas se refazem
    const cr = this.cristal;
    cr.tremor = Math.max(0, cr.tremor - dt * 2.5);
    if (cr.quebrado) {
      cr.volta -= dt;
      if (cr.volta <= 0) {
        cr.quebrado = false;
        cr.danos = 0;
        j.instrucao("O CRISTAL SE REFEZ", "#ffb3f0");
        j.brilho(DES.centroCristal[0], DES.centroCristal[1], 500, "#ff99f2", 0.8, 0.6);
      }
    }
    for (const pt of this.pontas) {
      if (pt.quebrada) { pt.volta -= dt; if (pt.volta <= 0) { pt.quebrada = false; pt.danos = 0; } }
    }
    for (let i = this.raios.length - 1; i >= 0; i--) {
      this.raios[i].t += dt;
      if (this.raios[i].t >= 0.45) this.raios.splice(i, 1);
    }
    for (const f of this.furos) f.t += dt;
    // poeira dourada de dia
    if (this.noite < 0.5 && Math.random() < dt * 3 * j.fator) {
      j.luz.soltar(Math.random() * W, aleatorio(450, 900), aleatorio(4, 16) * K, -aleatorio(2, 10) * K, aleatorio(2.5, 4),
        aleatorio(5, 9) * K, 2 * K, j.tinta("fx_ponto", "#ffd98c"), 0.5, 0, 0);
    }
  }

  humorAtual() {
    if (this.reacao) return this.reacao;
    const j = this.j;
    if (j.combo >= 6) return "radiante";
    if (j.combo >= 3) return "feliz";
    if (j.estado === "jogo" && (j.tempo < 15 || this.errosRecentes > 2.5)) return "atento";
    return "calmo";
  }

  // O olho vivo: olha em sacadas rápidas, segue o tiro, pisca (às vezes
  // duas vezes) e fecha devagar na troca do dia.
  animarOlho(d, dt) {
    const h = HUMORES[this.humorAtual()] || HUMORES.calmo;
    const ux = 26.95, uy = 2.67;     // até onde a íris anda (pontos)
    let seguindo = false;
    if (this.espiarT > 0) {
      d.alvoX = limitar((this.espiarX - W / 2) / (320 * K), -1, 1) * ux;
      d.alvoY = limitar((this.espiarY - d.y) / (420 * K), -1, 1) * uy;
      seguindo = true;
    } else {
      d.prox -= dt;
      if (d.prox <= 0) {
        d.prox = aleatorio(0.7, 2.6);
        if (Math.random() < 0.35) {
          d.alvoX = limitar((this.j.mira.x - W / 2) / (320 * K), -1, 1) * ux * h.alcance;
          d.alvoY = limitar((this.j.mira.y - d.y) / (420 * K), -1, 1) * uy;
        } else {
          const e = sorteio(OLHADAS);
          d.alvoX = e[0] * h.alcance * ux * 3.3;
          d.alvoY = e[1] * uy * 20;
        }
      }
    }
    const k = 1 - Math.exp(-dt * (seguindo ? 14 : 38));
    d.olharX += (d.alvoX - d.olharX) * k;
    d.olharY += (d.alvoY - d.olharY) * k;
    d.topo += (h.topo - d.topo) * (1 - Math.exp(-dt * 7));
    d.sono += (d.sonoAlvo - d.sono) * (1 - Math.exp(-dt * 2.2));
    let p = 0;
    if (d.fase < 0) {
      d.piscarT -= dt;
      if (d.piscarT <= 0 && d.sono < 0.5) d.fase = 0;
    } else {
      d.fase += dt;
      const f = d.fase;
      if (f < 0.07) p = f / 0.07;
      else if (f < 0.11) p = 1;
      else if (f < 0.27) p = 1 - (f - 0.11) / 0.16;
      else {
        d.fase = -1;
        if (!d.dupla && Math.random() < 0.22) { d.dupla = true; d.piscarT = 0.12; }
        else { d.dupla = false; d.piscarT = aleatorio(2.5, 6); }
      }
    }
    d.fecha = Math.max(suave(p), d.sono);
  }

  // ---------------------------------------------------------------- desenho
  desenharFundo(ctx) {
    const j = this.j;
    const sol = this.api.img.fundo_egito_sol, lua = this.api.img.fundo_egito_lua;
    if (sol && this.noite < 1) ctx.drawImage(sol, 0, 0, W, H);
    if (lua && this.noite > 0) { ctx.globalAlpha = this.noite; ctx.drawImage(lua, 0, 0, W, H); ctx.globalAlpha = 1; }
    // estrelas piscando de noite
    if (this.noite > 0.05) {
      const img = j.tinta("fx_estrela", "#d9e6ff");
      ctx.globalCompositeOperation = "lighter";
      for (const e of this.estrelas) {
        ctx.globalAlpha = this.noite * e.brilho * (0.5 + 0.5 * Math.sin(this.t * e.vel + e.fase));
        if (img) ctx.drawImage(img, e.x - e.tam / 2, e.y - e.tam / 2, e.tam, e.tam);
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    }
    for (const nome of ["sol", "lua"]) if (this.astros[nome].visivel) this.desenharAstro(ctx, nome, this.astros[nome]);
    // o horizonte por cima do astro: ele se põe atrás das pirâmides
    if (this.troca) {
      ctx.save();
      caminhoPoligono(ctx, DES.horizonte);
      ctx.clip();
      if (sol && this.noite < 1) ctx.drawImage(sol, 0, 0, W, H);
      if (lua && this.noite > 0) { ctx.globalAlpha = this.noite; ctx.drawImage(lua, 0, 0, W, H); }
      ctx.restore();
    }
    this.desenharEnergia(ctx);
    // furos de bala na areia e na pedra
    for (const f of this.furos) {
      const a = f.t > 8 ? 1 - (f.t - 8) / 2 : 1;
      if (a <= 0) continue;
      ctx.globalAlpha = a * 0.9;
      const r = ATLAS[f.tex];
      const w = f.tam, hh = (f.tam * r[3]) / r[2];
      ctx.translate(f.x, f.y);
      ctx.rotate(f.rot);
      j.peca(ctx, f.tex, -w / 2, -hh / 2, w, hh);
      ctx.rotate(-f.rot);
      ctx.translate(-f.x, -f.y);
    }
    ctx.globalAlpha = 1;
  }

  desenharAstro(ctx, nome, d) {
    const j = this.j;
    const x = DES.astro[0], y = d.y;
    // de dia o olho de Rá, de noite o de Hórus; afundando atrás das
    // pirâmides ele some antes de chegar no chão
    const alfa = limitar((DES.poente - y) / 70, 0, 1);
    if (alfa <= 0) return;
    const c = nome === "sol" ? COR_SOL : COR_LUA;
    const halo = j.tinta("fx_brilho", c);
    ctx.globalAlpha = 0.55 * alfa;
    ctx.globalCompositeOperation = "lighter";
    if (halo) ctx.drawImage(halo, x - 200, y - 200, 400, 400);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = alfa;
    const ex = x + OLHO.cx, ey = y + OLHO.cy;
    j.peca(ctx, "astro_" + nome + "_esclera", ex - OLHO.esclW / 2, ey - OLHO.esclH / 2, OLHO.esclW, OLHO.esclH);
    const ix = ex + d.olharX, iy = ey + OLHO.irisY + d.olharY;
    j.peca(ctx, "astro_" + nome + "_iris", ix - OLHO.iris / 2, iy - OLHO.iris / 2, OLHO.iris, OLHO.iris);
    ctx.fillStyle = "#050302";
    ctx.beginPath();
    ctx.arc(ix, iy, 10 + 2 * this.noite, 0, VOLTA);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.beginPath();
    ctx.arc(ix - 4.5, iy - 5, 2.75, 0, VOLTA);
    ctx.arc(ix + 4, iy + 4.5, 1.2, 0, VOLTA);
    ctx.fill();
    // a pálpebra desce de cima (o disco por cima esconde as bordas)
    const topo = misturar(d.topo, 1, d.fecha || 0);
    const desce = topo * OLHO.esclH;
    if (desce > 0.5) {
      const y0 = ey - OLHO.esclH / 2;
      ctx.fillStyle = nome === "sol" ? "#d9a23a" : "#8f9ec7";
      ctx.fillRect(ex - OLHO.esclW / 2, y0, OLHO.esclW, desce);
      ctx.fillStyle = "#1d3c9c";
      ctx.fillRect(ex - OLHO.esclW / 2, y0 + desce - 2.5, OLHO.esclW, 2.5);
    }
    const disco = this.api.img["astro_" + nome + "_disco"];
    if (disco) ctx.drawImage(disco, x - OLHO.disco / 2, y - OLHO.disco / 2, OLHO.disco, OLHO.disco);
    ctx.globalAlpha = 1;
  }

  // O cristal do meio e os feixes de energia até os obeliscos: engrossam
  // e correm com a carga; quebrado, ele corta a energia.
  desenharEnergia(ctx) {
    const j = this.j;
    const cr = this.cristal;
    const corCristal = this.noite > 0.5 ? "#ff4059" : "#ff8ce6";
    const pulso = 0.8 + 0.2 * Math.sin(this.t * 2.2);
    ctx.globalCompositeOperation = "lighter";
    if (!cr.quebrado) {
      const brilho = j.tinta("fx_brilho", corCristal);
      const pisca = cr.tremor > 0 && Math.sin(this.t * 60) > 0 ? 0.4 : 1;
      ctx.globalAlpha = (0.3 + 0.25 * this.carga) * pulso * pisca * (1 - cr.danos / 14);
      if (brilho) ctx.drawImage(brilho, DES.centroCristal[0] - 110, DES.centroCristal[1] - 199, 221, 398);
      ctx.lineCap = "round";
      ctx.strokeStyle = corCristal;
      for (let i = 0; i < 4; i++) {
        if (this.pontas[i % 2].quebrada) continue;
        const f = DES.feixes[i];
        ctx.globalAlpha = (0.16 + 0.24 * this.carga) * pisca;
        ctx.lineWidth = 4 + 6 * this.carga;
        ctx.beginPath(); ctx.moveTo(f[0], f[1]); ctx.lineTo(f[2], f[3]); ctx.stroke();
        ctx.globalAlpha = (0.5 + 0.4 * this.carga) * pisca;
        ctx.lineWidth = 1.6 + this.carga;
        ctx.setLineDash(TRACO);
        ctx.lineDashOffset = -this.t * (50 + 140 * this.carga);
        ctx.beginPath(); ctx.moveTo(f[0], f[1]); ctx.lineTo(f[2], f[3]); ctx.stroke();
        ctx.setLineDash(SEM_TRACO);
      }
    }
    const ponta = j.tinta("fx_brilho", this.noite > 0.5 ? "#ff4d66" : "#ff73cc");
    for (let k = 0; k < 2; k++) {
      if (this.pontas[k].quebrada || cr.quebrado || !ponta) continue;
      const [x, y] = DES.pontasCentro[k];
      ctx.globalAlpha = 0.6 * pulso;
      ctx.drawImage(ponta, x - 32, y - 32, 64, 64);
    }
    const ouro = j.tinta("fx_brilho", "#ffcc6b");
    if (ouro && !cr.quebrado) {
      for (let i = 0; i < 3; i++) {
        const [x, y] = DES.brilhosOuro[i];
        ctx.globalAlpha = (0.22 + 0.12 * Math.sin(this.t * 1.3 + i * 2)) * (1 - this.noite * 0.5);
        ctx.drawImage(ouro, x - 48, y - 48, 96, 96);
      }
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    // trincas do cristal
    if (cr.trincas.length) {
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      for (const [cor, larg] of [["rgba(64, 13, 51, 0.55)", 2.2], ["rgba(255, 235, 255, 0.85)", 1]]) {
        ctx.strokeStyle = cor;
        ctx.lineWidth = larg;
        ctx.beginPath();
        for (const l of cr.trincas) {
          ctx.moveTo(l[0], l[1]);
          for (let i = 2; i < l.length; i += 2) ctx.lineTo(l[i], l[i + 1]);
        }
        ctx.stroke();
      }
    }
    // quebrados: o cristal e as pontas escurecem
    if (cr.quebrado) {
      ctx.globalAlpha = 0.8;
      ctx.fillStyle = "#1c1020";
      caminhoPoligono(ctx, DES.cristal);
      ctx.fill();
    }
    for (let k = 0; k < 2; k++) {
      if (!this.pontas[k].quebrada) continue;
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = "#2a2230";
      caminhoPoligono(ctx, DES.pontas[k]);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  desenharAlvos(ctx) {
    const j = this.j;
    for (const a of this.alvos) {
      if (a.esc <= 0 || a.alfa <= 0) continue;
      const img = this.api.img["brasao_" + a.tipo];
      if (!img) continue;
      const f = FOLHAS["brasao_" + a.tipo];
      const c = a.tipo === "sol" ? COR_SOL : COR_LUA;
      const halo = j.tinta("fx_brilho", c);
      const tam = 260 * a.esc;   // o halo é filho do brasão: 260 px na escala dele
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.42 * a.alfa;
      if (halo) ctx.drawImage(halo, a.x - tam / 2, a.y - tam / 2, tam, tam);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = a.alfa;
      const cw = img.width / f.q;
      const dw = f.w * a.esc, dh = f.h * a.esc;
      ctx.translate(a.x, a.y);
      ctx.rotate(a.rot);
      ctx.drawImage(img, 0, 0, cw, img.height, -dw / 2, -dh / 2, dw, dh);
      if (a.flash > 0) {
        // a troca de astro no meio do voo: clarão branco
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = Math.min(1, a.flash * 2.2) * a.alfa;
        ctx.drawImage(img, 0, 0, cw, img.height, -dw / 2, -dh / 2, dw, dh);
        ctx.globalCompositeOperation = "source-over";
      }
      ctx.rotate(-a.rot);
      ctx.translate(-a.x, -a.y);
    }
    ctx.globalAlpha = 1;
  }

  desenharFrente(ctx) {
    if (!this.raios.length) return;
    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const r of this.raios) {
      const a = 1 - r.t / 0.45;
      for (const [cor, alfa, larg] of [["#ffbf4d", 0.6, 14 * K], ["#fff7d9", 1, 4 * K]]) {
        ctx.globalAlpha = a * alfa;
        ctx.strokeStyle = cor;
        ctx.lineWidth = larg;
        ctx.beginPath();
        ctx.moveTo(r.pts[0], r.pts[1]);
        for (let i = 2; i < r.pts.length; i += 2) ctx.lineTo(r.pts[i], r.pts[i + 1]);
        ctx.stroke();
      }
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
  }
}

/* ======================================================================
   FUNDO DO MAR (mar.gd)
   ====================================================================== */
const MAR = {
  pontos: { aguaviva: 20, vaso: 80, bau: 100, bomba: 0 },
  queda: { aguaviva: 5.7, vaso: 6.6, bau: 4.6, bomba: 5.0 },
  escala: { aguaviva: [1.0, 1.25], vaso: [0.78, 0.95], bau: [1.25, 1.45], bomba: [1.0, 1.2] },
  chao: 1565 * K,
  porta: [t46x(439), t46y(724)],
};
const PERIODO_AGUAVIVA = 1.15;
const TRANCO_AGUAVIVA = 0.8;

class CenarioMar {
  constructor(j) {
    this.j = j;
    this.api = j.api;
    this.objs = [];
    this.spawnT = 0.3;
    this.bombas = 0;
    this.nivel = 0;
    this.furos = [];
    this.t = 0;
    this.cardume = { visivel: false, espera: 12, t: 0, dur: 7, de: [0, 0], ate: [0, 0], pegos: 0, pressa: 1, peixes: [] };
    for (let i = 0; i < 9; i++) {
      const fila = Math.floor(Math.sqrt(i) + 0.0001);
      this.cardume.peixes.push({ ox: (-fila * 70 + aleatorio(-14, 14)) * K, oy: ((i - fila * fila - fila) * 46 + aleatorio(-10, 10)) * K,
        fase: Math.random() * VOLTA, pego: -1, fx: 0, fy: 0, giro: 0, rot: 0, x: 0, y: 0, a: 1, vivo: true });
    }
    this.raios = [];
    for (let i = 0; i < 4; i++) {
      this.raios.push({ x: (120 + i * 260 + aleatorio(-40, 40)) * K, larg: 64 * aleatorio(2.2, 3.4) * K,
        comp: 256 * aleatorio(4.2, 5.6) * K, fase: Math.random() * VOLTA, vel: aleatorio(0.25, 0.45), rot: aleatorio(-0.28, -0.08) });
    }
  }

  preparar() {}

  comecar() {
    this.spawnT = 0.2;
    this.cardume.espera = aleatorio(10, 14);
    this.spawnar("aguaviva");
    this.spawnar("aguaviva");
    this.spawnar("bau");
  }

  podeAtirar() { return true; }

  estiloTiro() { return "mar"; }

  extra() {
    const r = Math.max(0, 3 - this.bombas);
    return ["BOMBAS", r + "/3", r === 3 ? "#8cff99" : r === 2 ? "#ffcc4d" : "#ff4d40"];
  }

  atualizar(dt) {
    const n = Math.floor(Math.max(this.j.pontos, 0) / 3000);
    if (n !== this.nivel) {
      this.nivel = n;
      if (n > 0) this.j.instrucao("NÍVEL " + (n + 1), "#99f2ff");
    }
    this.spawnT -= dt;
    if (this.spawnT <= 0) {
      this.spawnT = aleatorio(0.18, 0.42);
      this.tentarSpawn();
    }
    this.mover(dt);
    this.cardumeTick(dt);
  }

  contar(tipo) {
    let n = 0;
    for (const o of this.objs) if (o.tipo === tipo && !o.atingido) n++;
    return n;
  }

  tentarSpawn() {
    if (this.contar("aguaviva") < 6 && Math.random() <= 0.81 * 0.5) this.spawnar("aguaviva");
    if (this.contar("vaso") < 3 && Math.random() < 0.42 * 0.5) this.spawnar("vaso");
    if (this.contar("bau") < 2 && Math.random() < 0.28) this.spawnar("bau");
    let chance = 0.39 + (this.j.pontos < 1500 ? 0.1 : 0) + this.nivel * 0.06 + (this.nivel >= 1 ? 0.1 : 0);
    chance = Math.min(0.9, chance);
    let vivas = this.contar("bomba");
    for (let i = 0; i < 1 + this.nivel; i++) {
      if (vivas >= 6 + this.nivel * 2) break;
      if (Math.random() < chance) { this.spawnar("bomba"); vivas++; }
    }
  }

  raio(o) {
    return Math.max(o.f.w, o.f.h) * o.esc * 0.42;
  }

  conflita(x, y, r) {
    for (const o of this.objs) {
      if (o.atingido) continue;
      if (Math.hypot(o.x - x, o.y - y) < r + this.raio(o)) return true;
    }
    return false;
  }

  spawnar(tipo) {
    let variante = tipo;
    if (tipo === "aguaviva" && Math.random() < 0.5) variante = "aguaviva_a";
    const f = FOLHAS[variante];
    const faixa = MAR.escala[tipo];
    let esc = aleatorio(faixa[0], faixa[1]) * aleatorio(0.88, 1.12);
    if (tipo === "bomba") esc += this.nivel * 0.07;
    // a folha nítida é maior que a de antes: a mesma figura na tela
    esc = (esc / f.fator) * K;
    const o = { tipo, variante, f, img: this.api.img[variante], esc, dur: MAR.queda[tipo] / (1 + this.nivel * 0.07), t: 0,
      atingido: false, acertoT: 0, anim: Math.random() * 4, bolhaT: 0.3, visto: false, deCima: false, frame: 0 };
    const fora = 79;
    const r = Math.max(f.w, f.h) * esc * 0.42;
    let achou = false;
    for (let tent = 0; tent < 16 && !achou; tent++) {
      let ix, iy, fx, fy;
      if (tipo === "aguaviva") {
        const m = (Math.random() * 3) | 0;
        if (m < 2) {
          const x = aleatorio(58, W - 58);
          ix = x; iy = H + fora; fx = x + aleatorio(-1, 1) * (m === 0 ? 63 : 32); fy = -fora;
        } else {
          const y = aleatorio(200, H - 158);
          if (Math.random() < 0.5) { ix = -fora; iy = y; fx = W + fora; fy = y - aleatorio(32, 137); }
          else { ix = W + fora; iy = y; fx = -fora; fy = y - aleatorio(32, 137); }
        }
      } else if (tipo === "bomba") {
        const m = (Math.random() * 4) | 0;
        if (m === 0) { ix = aleatorio(37, W - 37); iy = -fora; fx = aleatorio(37, W - 37); fy = H + fora; }
        else if (m === 1) { ix = aleatorio(37, W - 37); iy = H + fora; fx = aleatorio(37, W - 37); fy = -fora; }
        else if (m === 2) { ix = -fora; iy = aleatorio(137, H - 84); fx = W + fora; fy = aleatorio(137, H - 84); }
        else { ix = W + fora; iy = aleatorio(137, H - 84); fx = -fora; fy = aleatorio(137, H - 84); }
      } else {
        const x = aleatorio(47, W - 47);
        ix = x; iy = -fora; fx = x + aleatorio(-32, 32); fy = H + fora;
      }
      let livre = true;
      for (const k of [0.2, 0.35, 0.5, 0.65]) {
        if (this.conflita(misturar(ix, fx, k), misturar(iy, fy, k), r)) { livre = false; break; }
      }
      if (livre) { o.ix = ix; o.iy = iy; o.fx = fx; o.fy = fy; achou = true; }
    }
    if (!achou) return;
    // o que cai de cima passa reto pela tela e some lá embaixo
    if (tipo !== "aguaviva" && o.iy < 0 && o.fy > H) o.deCima = true;
    if (tipo === "aguaviva") {
      o.pulsos = Math.max(2, Math.round(o.dur / PERIODO_AGUAVIVA));
      o.rot0 = aleatorio(-8, 8) * RAD;
      o.rot1 = o.rot0;
    } else if (tipo === "bomba") {
      o.rot0 = aleatorio(-180, 180) * RAD;
      o.rot1 = o.rot0 + aleatorio(320, 560) * RAD * (Math.random() < 0.5 ? 1 : -1);
    } else {
      o.rot0 = aleatorio(-6, 6) * RAD;
      o.rot1 = aleatorio(-14, 14) * RAD;
    }
    o.x = o.ix; o.y = o.iy; o.rot = o.rot0; o.sx = 1; o.sy = 1;
    this.objs.push(o);
  }

  mover(dt) {
    const j = this.j;
    for (let i = this.objs.length - 1; i >= 0; i--) {
      const o = this.objs[i];
      if (o.atingido) continue;
      o.t += dt / Math.max(o.dur, 0.1);
      if (o.t >= 1) { this.objs.splice(i, 1); continue; }
      let k = o.t;
      o.sx = 1; o.sy = 1;
      if (o.tipo === "aguaviva") {
        // nada em pulsos: o sino empurra e desliza
        k = o.t + (TRANCO_AGUAVIVA * Math.sin(VOLTA * o.pulsos * o.t)) / (VOLTA * o.pulsos);
        const fase = (o.t * o.pulsos) % 1;
        o.sx = 1 + 0.06 * Math.sin(fase * VOLTA);
        o.sy = 1 - 0.06 * Math.sin(fase * VOLTA);
      } else if (o.deCima) {
        k = o.t * o.t * (3 - 2 * o.t) * 0.35 + o.t * o.t * 0.65;
      }
      o.x = misturar(o.ix, o.fx, k);
      o.y = misturar(o.iy, o.fy, k);
      // o que já passou pela tela e saiu some na hora
      const meio = Math.max(o.f.w, o.f.h) * o.esc * 0.6;
      const dentroTela = o.x > -meio && o.x < W + meio && o.y > -meio && o.y < H + meio;
      if (dentroTela) o.visto = true;
      else if (o.visto) { this.objs.splice(i, 1); continue; }
      o.rot = misturar(o.rot0, o.rot1, o.t);
      o.anim += dt;
      o.frame = o.f.parado[Math.floor(o.anim * 6) % o.f.parado.length];
      o.bolhaT -= dt;
      if (o.bolhaT <= 0) {
        o.bolhaT = aleatorio(0.14, 0.34);
        j.part.explosao(o.x + aleatorio(-10, 10), o.y - 5, { n: 1 + ((Math.random() * 2) | 0), tex: "mar_bolha", vel: [10, 40],
          ang: [240, 300], vida: [0.8, 1.4], tam: [6, 14], fim: 1, cor: "#d9f7ff", alfa: 0.7, grav: -120 });
      }
    }
  }

  alvoNoPonto(x, y) {
    let melhor = null, dMelhor = Infinity;
    for (let passo = 0; passo < 2 && !melhor; passo++) {
      for (let i = this.objs.length - 1; i >= 0; i--) {
        const o = this.objs[i];
        if (o.atingido) continue;
        paraQuadro(x, y, o.x, o.y, o.rot, o.esc * o.sx, o.esc * o.sy, LOCAL);
        const folga = passo === 0 ? o.f.w / 24 : TOQUE / o.esc;
        if (!naMascara(o.f, LOCAL[0], LOCAL[1], folga, folga)) continue;
        if (passo === 0) return o;
        const d = Math.hypot(LOCAL[0], LOCAL[1]);
        if (d < dMelhor) { dMelhor = d; melhor = o; }
      }
    }
    return melhor;
  }

  tiro(x, y) {
    const o = this.alvoNoPonto(x, y);
    if (o) { this.acertar(o, x, y); return; }
    if (this.acertarCardume(x, y)) return;
    if (y > MAR.chao - 120 * K) this.furarChao(x, y);
    this.j.errar(x, y, "SPLASH!");
  }

  acertar(o, x, y) {
    const j = this.j;
    o.atingido = true;
    o.acertoT = 0;
    if (o.tipo === "bomba") { this.explodirBomba(o); return; }
    const pts = MAR.pontos[o.tipo];
    j.registrarCombo();
    j.ganhar(pts, o.x, o.y, OURO, 1 + (pts >= 80 ? 0.15 : 0));
    if (o.tipo === "aguaviva") {
      this.api.som("nota");
      j.clarao("#5ce0ff", 0.14, 0.2);
      j.tremer(2);
      const c = o.variante === "aguaviva" ? "#d980ff" : "#ff73a6";
      j.luz.explosao(o.x, o.y, { n: 26, vel: [60, 260], vida: [0.5, 1.0], tam: [8, 18], cor: c, grav: -80, arrasto: 2, espalha: 30 });
      j.part.explosao(o.x, o.y, { n: 8, tex: "mar_bolha", vel: [40, 160], ang: [200, 340], vida: [0.6, 1.2], tam: [8, 18], fim: 1,
        cor: "#e6f7ff", alfa: 0.8, grav: -260, arrasto: 1.2 });
    } else if (o.tipo === "vaso") {
      this.api.som("vidro");
      j.clarao("#fff2b3", 0.12, 0.2);
      j.tremer(3.5);
      if (o.img) {
        const cw = o.img.width / o.f.q;
        j.cacos.estourar(o.img, 0, 0, cw, o.img.height, o.f.w, o.f.h, o.x, o.y, o.esc, o.rot, x, y, { n: 12, forca: 1, vida: 1 });
      }
    } else {
      this.api.som("moeda");
      j.clarao("#fff2b3", 0.12, 0.2);
      j.tremer(3.5);
      j.luz.explosao(o.x, o.y, { n: 24, vel: [180, 460], ang: [200, 340], vida: [0.5, 0.9], tam: [8, 14], cor: "#ffd14d",
        grav: 900, estica: 0.02 });
      j.part.explosao(o.x, o.y, { n: 14, tex: "fx_ponto", vel: [120, 380], ang: [200, 340], vida: [0.8, 1.3], tam: [10, 16], fim: 1,
        cor: "#ffc733", grav: 1100, giro: [-10, 10] });
    }
  }

  explodirBomba(o) {
    const j = this.j;
    this.bombas++;
    j.quebrarCombo();
    j.acertos++;
    this.api.som("soco");
    this.api.som("batida");
    j.clarao("#ff7333", 0.22, 0.35);
    j.tremer(13);
    j.vibrar(80);
    j.brilho(o.x, o.y, 520, "#ff9940", 0.95, 0.45);
    j.anel(o.x, o.y, 80, 7, "#ffbf73", 0.9, 0.5);
    j.anel(o.x, o.y, 80, 10, "#ffbf73", 0.9, 0.65);
    j.luz.explosao(o.x, o.y, { n: 30, vel: [250, 700], vida: [0.3, 0.7], tam: [8, 16], cor: "#ffb34d", grav: 300, estica: 0.03 });
    j.part.explosao(o.x, o.y, { n: 7, tex: "fx_fumaca", vel: [30, 120], vida: [1, 1.8], tam: [60, 100], fim: 2.2, cor: "#262124",
      alfa: 0.7, grav: -40 });
    j.part.explosao(o.x, o.y, { n: 12, tex: "fx_caco", vel: [200, 520], vida: [0.6, 1.1], tam: [8, 16], cor: "#1f1f24", grav: 900,
      giro: [-14, 14] });
    j.part.explosao(o.x, o.y, { n: 14, tex: "mar_bolha", vel: [80, 260], vida: [0.8, 1.5], tam: [10, 26], fim: 1, cor: "#e6f7ff",
      alfa: 0.85, grav: -300 });
    o.fps = 16;
    const restam = Math.max(0, 3 - this.bombas);
    if (this.bombas >= 3) {
      j.encerrar("3 BOMBAS!");
    } else {
      j.mostrar(o.x, o.y, "BOMBA!", VERMELHO);
      j.instrucao("NÃO ACERTE BOMBAS! RESTAM " + restam + " CHANCES", "#ff8066");
    }
  }

  furarChao(x, y) {
    const f = this.furos.length >= 16 ? this.furos.shift() : {};
    f.x = x; f.y = y; f.tam = 64 * 0.8 * aleatorio(0.85, 1.15) * K * 1.6; f.rot = aleatorio(-0.4, 0.4); f.t = 0;
    this.furos.push(f);
    this.j.part.explosao(x, y, { n: 3, tex: "fx_nuvem", vel: [10, 40], ang: [220, 320], vida: [0.9, 1.5], tam: [44, 64], fim: 2,
      cor: "#9ec7d1", alfa: 0.5, grav: -20 });
  }

  // O cardume dourado atravessa de tempos em tempos: cada peixe +40, o
  // cardume inteiro +200 (POSEIDON'S TREASURE!).
  cardumeTick(dt) {
    const c = this.cardume;
    if (!c.visivel) {
      c.espera -= dt;
      if (c.espera <= 0) this.soltarCardume();
      return;
    }
    c.t += dt * c.pressa;
    const k = c.t / c.dur;
    if (k >= 1) { c.visivel = false; c.espera = aleatorio(14, 22); return; }
    const cx = misturar(c.de[0], c.ate[0], k);
    const cy = misturar(c.de[1], c.ate[1], k) + Math.sin(k * VOLTA * 1.2) * 40 * K;
    const dir = Math.sign(c.ate[0] - c.de[0]);
    for (const p of c.peixes) {
      if (!p.vivo) continue;
      let ox = p.ox * 1.6 * dir + Math.sin(c.t * 1.7 + p.fase) * 10 * K;
      let oy = p.oy * 1.6 + Math.sin(c.t * 2.3 + p.fase * 1.3) * 8 * K;
      if (p.pego >= 0) {
        p.pego += dt;
        ox += p.fx * p.pego;
        oy += p.fy * p.pego;
        p.rot += p.giro * dt;
        p.a = Math.max(0, 1 - p.pego * 1.6);
        if (p.a <= 0) p.vivo = false;
      }
      p.x = cx + ox;
      p.y = cy + oy;
    }
    c.dir = dir;
    if (Math.random() < dt * 10 * this.j.fator) {
      this.j.luz.explosao(cx, cy, { n: 1, vel: [10, 30], vida: [0.5, 0.8], tam: [8, 14], cor: "#ffd966", espalha: 80 });
    }
  }

  soltarCardume() {
    const c = this.cardume;
    const direita = Math.random() < 0.5;
    const y = aleatorio(0.36, 0.62) * H;
    c.de = [direita ? -137 : W + 137, y];
    c.ate = [direita ? W + 137 : -137, y + aleatorio(-84, 84)];
    c.dur = aleatorio(6, 7.5);
    c.t = 0;
    c.pegos = 0;
    c.pressa = 1;
    for (const p of c.peixes) { p.pego = -1; p.vivo = true; p.a = 1; p.rot = 0; p.x = -999; p.y = -999; }
    c.visivel = true;
  }

  acertarCardume(x, y) {
    const c = this.cardume;
    if (!c.visivel) return false;
    const j = this.j;
    for (const p of c.peixes) {
      if (!p.vivo || p.pego >= 0) continue;
      if (Math.hypot(p.x - x, p.y - y) >= 46 * K + TOQUE) continue;
      p.pego = 0;
      p.fx = aleatorio(-120, 120) * K;
      p.fy = aleatorio(-260, -120) * K;
      p.giro = aleatorio(-12, 12);
      c.pegos++;
      c.pressa = 1.6;
      const todos = c.pegos >= c.peixes.length;
      j.registrarCombo();
      j.bonus(40 + (todos ? 200 : 0), p.x, p.y, "#ffdb73", todos ? 1.25 : 1);
      this.api.som("moeda");
      j.luz.explosao(p.x, p.y, { n: 14, vel: [100, 300], vida: [0.3, 0.6], tam: [8, 14], cor: "#ffd959", estica: 0.03, arrasto: 2 });
      if (c.pegos === 1) j.instrucao("PEIXES DOURADOS! +40 CADA", "#ffdb73");
      if (todos) {
        j.especial("POSEIDON'S TREASURE!");
        j.instrucao("CARDUME INTEIRO! +200", "#ffdb73");
        j.clarao("#ffd966", 0.16, 0.3);
      }
      return true;
    }
    return false;
  }

  encerrou() {
    for (const o of this.objs) if (!o.atingido) { o.atingido = true; o.acertoT = 0; o.sumir = true; }
    this.cardume.visivel = false;
  }

  sempre(dt) {
    const j = this.j;
    this.t += dt;
    // a animação de acerto da folha (estoura, abre, desfaz) e some
    for (let i = this.objs.length - 1; i >= 0; i--) {
      const o = this.objs[i];
      if (!o.atingido) continue;
      o.acertoT += dt;
      if (o.sumir) {
        if (o.acertoT >= 0.4) this.objs.splice(i, 1);
        continue;
      }
      const fps = o.fps || 9;
      const q = Math.floor(o.acertoT * fps);
      if (q < o.f.acerto.length) o.frame = o.f.acerto[q];
      else if (o.acertoT > o.f.acerto.length / fps + 0.2) this.objs.splice(i, 1);
    }
    for (const f of this.furos) f.t += dt;
    // neve marinha
    if (Math.random() < dt * 6 * j.fator) {
      j.luz.soltar(Math.random() * W, aleatorio(0, H * 0.8), aleatorio(-5, 5) * K, aleatorio(8, 22) * K, aleatorio(3, 5),
        aleatorio(4, 8) * K, 3 * K, j.tinta("fx_ponto", "#cfefff"), 0.5, 0, 0);
    }
  }

  desenharFundo(ctx) {
    const j = this.j;
    const fundo = this.api.img.fundo_mar;
    if (fundo) ctx.drawImage(fundo, 0, 0, W, H);
    // fachos de sol balançando, vindos da superfície
    if (!this.gradRaio) {
      const g = ctx.createLinearGradient(0, 0, 0, 1);
      g.addColorStop(0, "rgba(140, 230, 255, 0.5)");
      g.addColorStop(1, "rgba(140, 230, 255, 0)");
      this.gradRaio = g;
    }
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = this.gradRaio;
    for (const r of this.raios) {
      const a = 0.12 + 0.1 * Math.sin(this.t * r.vel + r.fase);
      if (a <= 0) continue;
      const ang = r.rot + Math.sin(this.t * r.vel * 0.7 + r.fase) * 0.06;
      ctx.globalAlpha = a;
      ctx.translate(r.x, -21);
      ctx.rotate(ang);
      ctx.scale(1, r.comp);
      ctx.beginPath();
      ctx.moveTo(-r.larg * 0.3, 0);
      ctx.lineTo(r.larg * 0.3, 0);
      ctx.lineTo(r.larg * 0.5, 1);
      ctx.lineTo(-r.larg * 0.5, 1);
      ctx.closePath();
      ctx.fill();
      ctx.scale(1, 1 / r.comp);
      ctx.rotate(-ang);
      ctx.translate(-r.x, 21);
    }
    // luz da porta do templo, respirando
    const porta = j.tinta("fx_brilho", "#66f2ff");
    if (porta) {
      ctx.globalAlpha = 0.45 * (0.75 + 0.25 * Math.sin(this.t * 1.6));
      ctx.drawImage(porta, MAR.porta[0] - 68, MAR.porta[1] - 68, 137, 137);
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    const areia = j.tinta("fx_furo_areia", "#bfd9f2");
    if (areia) {
      for (const f of this.furos) {
        const a = f.t > 8 ? 1 - (f.t - 8) / 2 : 1;
        if (a <= 0) continue;
        ctx.globalAlpha = a * 0.9;
        ctx.drawImage(areia, f.x - f.tam / 2, f.y - f.tam * 0.33, f.tam, f.tam * 0.66);
      }
      ctx.globalAlpha = 1;
    }
  }

  desenharAlvos(ctx) {
    const j = this.j;
    for (const o of this.objs) {
      if (!o.img) continue;
      let alfa = 1;
      if (o.sumir) alfa = 1 - o.acertoT / 0.4;
      else if (o.atingido) {
        const fps = o.fps || 9;
        const fim = o.f.acerto.length / fps;
        if (o.acertoT > fim) alfa = 1 - (o.acertoT - fim) / 0.2;
      }
      if (alfa <= 0) continue;
      // o brilho em volta (filho do alvo: cresce com ele)
      let corHalo = null, tamHalo = 0, aHalo = 0;
      if (o.tipo === "bau" || o.tipo === "vaso") { corHalo = "#ffd966"; tamHalo = 230; aHalo = 0.22; }
      else if (o.tipo === "aguaviva") { corHalo = o.variante === "aguaviva" ? "#cc66ff" : "#ff4d8c"; tamHalo = 200; aHalo = 0.25; }
      if (corHalo && !o.atingido) {
        const halo = j.tinta("fx_brilho", corHalo);
        const tam = tamHalo * o.esc;
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = aHalo * alfa * 1.4;
        if (halo) ctx.drawImage(halo, o.x - tam / 2, o.y - tam / 2, tam, tam);
        ctx.globalCompositeOperation = "source-over";
      }
      ctx.globalAlpha = alfa;
      const cw = o.img.width / o.f.q;
      const dw = o.f.w * o.esc * o.sx, dh = o.f.h * o.esc * o.sy;
      ctx.translate(o.x, o.y);
      ctx.rotate(o.rot);
      ctx.drawImage(o.img, o.frame * cw, 0, cw, o.img.height, -dw / 2, -dh / 2, dw, dh);
      ctx.rotate(-o.rot);
      ctx.translate(-o.x, -o.y);
    }
    ctx.globalAlpha = 1;
    // o cardume dourado
    const c = this.cardume;
    if (c.visivel) {
      for (const p of c.peixes) {
        if (!p.vivo) continue;
        const s = 0.9 + 0.08 * Math.sin(c.t * 9 + p.fase);
        const w = 128 * s * K, h = 64 * s * K;
        ctx.globalAlpha = p.a;
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        if (c.dir < 0) ctx.scale(-1, 1);
        j.peca(ctx, "mar_peixe_dourado", -w / 2, -h / 2, w, h);
        if (c.dir < 0) ctx.scale(-1, 1);
        ctx.rotate(-p.rot);
        ctx.translate(-p.x, -p.y);
      }
      ctx.globalAlpha = 1;
    }
  }

  desenharFrente() {}
}

/* ======================================================================
   ARENA LAZER SHOT (arena.gd)
   ====================================================================== */
const CORES_SEQ = ["azul", "verde", "amarelo", "vermelho", "roxo"];
const QUADRO_COR = { apagada: 0, azul: 1, verde: 2, amarelo: 3, vermelho: 4, roxo: 5 };
const CORES_FX = { apagada: "#bfc7d9", azul: "#409eff", verde: "#40ff59", amarelo: "#ffdb26", vermelho: "#ff241a", roxo: "#c752ff" };
const NOMES_COR = { azul: "AZUL", verde: "VERDE", amarelo: "AMARELO", vermelho: "VERMELHO", roxo: "ROXO" };
// os 9 furos da parede (centro do anel no fundo 1080x1920 = metade em pontos)
const FUROS_ARENA = [[113, 391], [269, 390.5], [421, 390.5], [113, 549], [269, 549], [421, 549], [113, 709], [269, 709], [421, 708.5]];
const ESC_LANTERNA = (0.66 / 0.7 / 1.2143) * K;
const ARENA = {
  giroflex: [t46x(510), t46y(190)],
  led: [t46x(484 - 16), t46y(177 - 16), t46x(484 + 54 + 16), t46y(177 + 25 + 16)],
  ledCaixa: [t46x(484), t46y(177), 54 * 0.625, 25 * 0.625],
  logo: [26, 74, 498, 228],
  yOrdem: t46y(1318),
  vapor: [[t46x(150), t46y(748)], [t46x(804), t46y(944)], [t46x(842), t46y(1128)], [t46x(118), t46y(1180)]],
  caixa: [t46x(842), t46y(956)],
};

class CenarioArena {
  constructor(j) {
    this.j = j;
    this.api = j.api;
    this.lanternas = [null, null, null, null, null, null, null, null, null];
    this.sequencia = [];
    this.indice = 0;
    this.nivel = 1;
    this.mostrando = false;
    this.bloqueado = true;
    this.modoFixo = false;
    this.rodada = 0;
    this.fixaNasceu = [];
    this.semJogada = 0;
    this.repetindo = false;
    this.avisoEspera = 0;
    this.agenda = [];
    this.marcas = [];
    this.led = 0;
    this.giro = 0;
    this.giroCor = "#ff1f0f";
    this.pisca = 0;
    this.piscaCor = BRANCO;
    this.proxVapor = 3;
    this.proxFaisca = 6;
    this.t = 0;
  }

  preparar() {
    // as lanternas apagadas já ficam nos furos durante a missão
    for (let i = 0; i < 9; i++) this.nascer(i, "apagada", false);
  }

  comecar() {
    this.nivel = 1;
    this.indice = 0;
    this.sequencia = [];
    this.novaSequencia();
  }

  estiloTiro() { return "laser"; }

  extra() {
    if (this.modoFixo) return ["FIXA", this.indice + "/5", "#ffd94d"];
    return ["NÍVEL", String(this.nivel), "#8ce6ff"];
  }

  // As esperas da rodada (os yield do original): cada uma lembra a rodada
  // em que nasceu e morre se a rodada mudou — o "minha != _rodada".
  depois(s, fn) {
    this.agenda.push({ quando: this.j.relogio + s, fn, rodada: this.rodada });
  }

  atualizar(dt) {
    this.avisoEspera = Math.max(0, this.avisoEspera - dt);
    for (let i = 0; i < this.agenda.length;) {
      const a = this.agenda[i];
      if (this.j.relogio < a.quando) { i++; continue; }
      this.agenda.splice(i, 1);
      if (a.rodada === this.rodada && this.j.estado === "jogo") a.fn();
    }
    // parado muito tempo na memória: a sequência que falta acende de novo
    if (this.mostrando || this.bloqueado || this.modoFixo || !this.sequencia.length || this.indice >= this.sequencia.length) {
      this.semJogada = 0;
      return;
    }
    this.semJogada += dt;
    if (this.semJogada >= 20) { this.semJogada = 0; this.repetirSequencia(); }
  }

  // Na hora de ver a sequência o gatilho não gasta bala (como na 4.6).
  podeAtirar() {
    if (this.mostrando || this.bloqueado || !this.sequencia.length || this.indice >= this.sequencia.length) {
      if (this.avisoEspera <= 0) {
        this.avisoEspera = 1.5;
        this.j.instrucao(this.mostrando ? "OBSERVE A SEQUÊNCIA!" : "AGUARDE...", "#8ce6ff");
      }
      return false;
    }
    return true;
  }

  tiro(x, y) {
    const j = this.j;
    this.semJogada = 0;
    const l = this.lanternaNoPonto(x, y);
    if (!l) {
      if (this.tiroNoLed(x, y)) {
        j.bonus(50, x, y, "#ff7359");
        j.instrucao("LED ESTOURADO! +50", "#ffb89e");
        return;
      }
      this.marcaLaser(x, y);
      j.errar(x, y);
      return;
    }
    if (l.quebrando) return;
    const ordem = this.sequencia.indexOf(l.slot);
    if (ordem === this.indice && (!this.modoFixo || l.cor !== "apagada")) this.acertar(l, ordem, x, y);
    else if (ordem >= 0 || !this.modoFixo) this.erroOrdem(l);
    else { this.marcaLaser(x, y); j.errar(x, y); }
  }

  acertar(l, ordem, x, y) {
    const j = this.j;
    const nomeCor = CORES_SEQ[ordem];
    const c = CORES_FX[nomeCor];
    let valor = (this.indice + 1) * 20;
    let rapido = false;
    if (this.modoFixo && ordem < this.fixaNasceu.length) {
      rapido = j.relogio - this.fixaNasceu[ordem] < 1.1;
      if (rapido) valor += 10;
    }
    this.indice++;
    const completa = this.indice >= this.sequencia.length;
    if (completa) this.bloqueado = true;
    j.pontos += valor;
    j.acertos++;
    const [fx, fy] = FUROS_ARENA[l.slot];
    j.pop(fx, fy - 63, "+" + valor, clarear(c, 0.3), 1 + ordem * 0.08);
    if (rapido) j.mostrar(fx, fy - 112, "RÁPIDO! +10", clarear(c, 0.5));
    // combo de acertos seguidos; a sequência completa ganha o especial
    j.combo++;
    j.comboT = Infinity;
    j.melhorCombo = Math.max(j.melhorCombo, j.combo);
    if (completa) j.especial("PERFECT SEQUENCE!");
    else j.anunciarCombo(j.combo);
    if (this.modoFixo) l.quebrando = true;
    this.api.som("vidro");
    this.quebrarVidro(l, c, x, y, this.modoFixo ? Infinity : 0.22);
    this.depois(0.22, () => {
      if (this.modoFixo) this.tirar(l.slot);
      else this.trocarCor(l.slot, nomeCor);
      if (!completa) return;
      if (this.modoFixo) {
        // o bônus da fixa não conta como acerto (não é tiro)
        j.pontos += 50;
        j.pop(W / 2, H / 2, "+50", OURO, 1.5);
        j.instrucao("SEQUÊNCIA FIXA COMPLETA! +50", "#ffd94d");
      } else {
        j.instrucao("SEQUÊNCIA COMPLETA! NÍVEL " + this.nivel + "!", "#4dff80");
        this.nivel++;
      }
      this.vitoria();
      // cicla: memória -> fixa -> memória (um nível acima) -> ...
      this.depois(0.85, () => (this.modoFixo ? this.novaSequencia() : this.rodadaFixa()));
    });
  }

  erroOrdem(l) {
    const j = this.j;
    const [fx, fy] = FUROS_ARENA[l.slot];
    j.perder(100, fx, fy - 63, "ORDEM ERRADA!");
    this.bloqueado = true;
    this.rodada++;
    this.api.som("erro");
    j.instrucao("ORDEM ERRADA! -100 · RECOMEÇANDO...", VERMELHO);
    // a lanterna quebra na cor em que estava, com cacos vermelhos, e volta
    this.quebrarVidro(l, "#ff140d", fx, fy, 0.24);
    j.clarao("#ff0d05", 0.24, 0.6);
    j.tremer(6);
    this.giro = 1.3;
    this.giroCor = "#ff1409";
    for (const a of this.lanternas) if (a) a.vermelho = 0;
    this.depois(1.45, () => {
      if (this.modoFixo) this.rodadaFixa();
      else { this.nivel = 1; this.novaSequencia(); }
    });
  }

  // ---------------------------------------------------------------- rodadas
  novaSequencia() {
    if (this.j.estado !== "jogo") return;
    this.rodada++;
    this.modoFixo = false;
    this.bloqueado = true;
    this.mostrando = true;
    this.indice = 0;
    this.sequencia = [];
    this.semJogada = 0;
    this.repetindo = false;
    const nasceram = this.preencher();
    this.apagarTodas();
    this.depois(nasceram ? 0.55 : 0.35, () => {
      this.apagarTodas();
      const furos = embaralhar([0, 1, 2, 3, 4, 5, 6, 7, 8]);
      for (let i = 0; i < Math.min(this.nivel, 5); i++) this.sequencia.push(furos[i]);
      this.j.instrucao("MEMORIZE A ORDEM DAS CORES! (" + this.sequencia.length + ")", "#4dd9ff");
      this.mostrarSequencia(false, () => {
        this.mostrando = false;
        this.bloqueado = false;
        this.j.instrucao("REPITA NA ORDEM DAS CORES!", "#4dd9ff");
      });
    });
  }

  // Depois do nível 5 a sequência continua com 5, mas acende mais rápido.
  tempoMostrar() {
    return Math.max(0.3, 0.55 - 0.05 * Math.max(0, this.nivel - 5));
  }

  mostrarSequencia(soFaltantes, fim) {
    this.depois(0.05, () => {
      if (soFaltantes) this.restaurarMemoria();
      const passo = (i) => {
        if (i >= this.sequencia.length) {
          if (soFaltantes) this.restaurarMemoria();
          fim();
          return;
        }
        const slot = this.sequencia[i];
        const cor = CORES_SEQ[i];
        this.trocarCor(slot, cor);
        this.brilhoSequencia(slot, CORES_FX[cor]);
        this.bip();
        this.depois(this.tempoMostrar(), () => {
          this.trocarCor(slot, "apagada");
          this.depois(0.2, () => passo(i + 1));
        });
      };
      passo(soFaltantes ? limitar(this.indice, 0, this.sequencia.length) : 0);
    });
  }

  repetirSequencia() {
    if (this.repetindo || !this.sequencia.length) return;
    this.repetindo = true;
    this.bloqueado = true;
    this.mostrando = true;
    this.j.instrucao("RELEMBRANDO A SEQUÊNCIA...", "#4dd9ff");
    this.depois(0.35, () => {
      this.mostrarSequencia(true, () => {
        this.repetindo = false;
        this.mostrando = false;
        this.bloqueado = false;
        this.semJogada = 0;
        this.j.instrucao("CONTINUE DE ONDE PAROU! " + this.indice + "/" + this.sequencia.length, "#4dff99");
      });
    });
  }

  restaurarMemoria() {
    this.apagarTodas();
    for (let i = 0; i < Math.min(this.indice, this.sequencia.length); i++) this.trocarCor(this.sequencia[i], CORES_SEQ[i]);
  }

  apagarTodas() {
    for (let i = 0; i < 9; i++) this.trocarCor(i, "apagada");
  }

  rodadaFixa() {
    if (this.j.estado !== "jogo") return;
    this.rodada++;
    this.modoFixo = true;
    this.bloqueado = true;
    this.mostrando = false;
    this.indice = 0;
    this.sequencia = [];
    this.semJogada = 0;
    this.j.instrucao("SEQUÊNCIA FIXA! ACERTE NA ORDEM DAS CORES", "#ffd94d");
    const algum = this.recolher();
    this.depois(algum ? 0.75 : 0.45, () => {
      const furos = embaralhar([0, 1, 2, 3, 4, 5, 6, 7, 8]);
      for (let i = 0; i < 5; i++) this.sequencia.push(furos[i]);
      this.fixaNasceu = [];
      this.bloqueado = false;
      // 5 lanternas acesas sobem uma depois da outra, já na cor da vez
      const nasce = (i) => {
        this.nascer(this.sequencia[i], CORES_SEQ[i], true);
        this.fixaNasceu.push(this.j.relogio);
        this.bip();
        this.pisca = 1;
        this.piscaCor = CORES_FX[CORES_SEQ[i]];
        if (i < 4) this.depois(aleatorio(1, 1.5), () => nasce(i + 1));
      };
      nasce(0);
    });
  }

  vitoria() {
    this.giro = 1.4;
    this.giroCor = "#ffd94d";
    const [gx, gy] = ARENA.giroflex;
    for (let i = 0; i < 2; i++) {
      this.j.luz.explosao(gx + aleatorio(-21, 21), gy + 5, { n: 10, tex: "fx_faisca", vel: [80, 280], ang: [200, 340],
        vida: [0.4, 0.9], tam: [10, 16], cor: "#ffd980", grav: 900, estica: 0.04 });
    }
  }

  // ---------------------------------------------------------------- lanternas
  preencher() {
    let nasceu = false;
    for (let i = 0; i < 9; i++) if (!this.lanternas[i]) { this.nascer(i, "apagada", true); nasceu = true; }
    return nasceu;
  }

  nascer(slot, cor, animar) {
    if (this.lanternas[slot]) return;
    this.lanternas[slot] = { slot, cor, sobe: animar ? 0 : -1, desce: null, quebrando: false, quebraT: 0,
      flash: 0, pulo: -1, puloForca: 0, vermelho: -1 };
    if (animar && cor !== "apagada") this.j.brilho(FUROS_ARENA[slot][0], FUROS_ARENA[slot][1], 260, CORES_FX[cor], 0.7, 0.4);
  }

  trocarCor(slot, cor) {
    const l = this.lanternas[slot];
    if (!l || l.quebrando) return;
    l.cor = cor;
    l.quebraT = 0;
    l.flash = 0;
    l.pulo = -1;
  }

  // Todas descem para dentro dos furos. true = havia alguma.
  recolher() {
    let algum = false;
    for (let i = 0; i < 9; i++) {
      const l = this.lanternas[i];
      if (!l) continue;
      algum = true;
      this.descer(l, 70, 0.26);
      this.lanternas[i] = null;
    }
    return algum;
  }

  tirar(slot) {
    const l = this.lanternas[slot];
    if (!l) return;
    this.lanternas[slot] = null;
    this.descer(l, 50, 0.22);
  }

  descer(l, dist, dur) {
    l.quebrando = true;
    l.desce = { t: 0, dist: dist * K, dur };
    (this.descendo || (this.descendo = [])).push(l);
  }

  lanternaNoPonto(x, y) {
    const f = FOLHAS.lanterna;
    let melhor = null, dMelhor = Infinity;
    for (let passo = 0; passo < 2 && !melhor; passo++) {
      for (const l of this.lanternas) {
        if (!l) continue;
        const [fx, fy] = FUROS_ARENA[l.slot];
        paraQuadro(x, y, fx, fy + this.deslocamento(l), 0, ESC_LANTERNA, ESC_LANTERNA, LOCAL);
        const folga = passo === 0 ? f.w / 24 : TOQUE / ESC_LANTERNA;
        if (!naMascara(f, LOCAL[0], LOCAL[1], folga, folga)) continue;
        if (passo === 0) return l;
        const d = Math.hypot(LOCAL[0], LOCAL[1]);
        if (d < dMelhor) { dMelhor = d; melhor = l; }
      }
    }
    return melhor;
  }

  deslocamento(l) {
    if (l.sobe >= 0) return 190 * K * (1 - saidaVolta(Math.min(1, l.sobe / 0.22)));
    if (l.desce) return l.desce.dist * entradaVolta(Math.min(1, l.desce.t / l.desce.dur));
    return 0;
  }

  // O acerto: a lanterna estoura na cor dela (quadro quebrado, clarão,
  // cacos de vidro colorido, faíscas e a luz batendo na parede).
  quebrarVidro(l, c, x, y, dur) {
    const j = this.j;
    l.quebraT = dur;
    l.flash = 1;
    l.flashCor = c;
    l.pulo = 0;
    l.puloForca = 1.22;
    const [cx, cy] = FUROS_ARENA[l.slot];
    j.part.explosao(cx, cy, { n: 22, tex: "fx_caco", vel: [220, 620], vida: [0.45, 1.1], tam: [8, 18], cor: clarear(c, 0.15),
      grav: 1100, arrasto: 0.4, giro: [-14, 14], espalha: 22 });
    j.part.explosao(cx, cy, { n: 8, tex: "fx_caco", vel: [160, 420], vida: [0.4, 0.9], tam: [6, 12], cor: "#fff0f0", grav: 1100,
      giro: [-14, 14], espalha: 18 });
    j.luz.explosao(cx, cy, { n: 16, vel: [180, 520], vida: [0.3, 0.7], tam: [6, 14], cor: c, grav: 400, estica: 0.03 });
    j.luz.explosao(x, y, { n: 6, tex: "fx_estrela", vel: [40, 160], vida: [0.25, 0.45], tam: [26, 44], fim: 0.1, cor: clarear(c, 0.4) });
    j.brilho(cx, cy, 360, c, 0.85, 0.45);
    j.brilho(cx, cy, 150, BRANCO, 0.8, 0.18);
  }

  // A lanterna da vez acende na sequência: pulo, clarão e faíscas na cor.
  brilhoSequencia(slot, c) {
    const l = this.lanternas[slot];
    if (!l) return;
    l.flash = 0.7;
    l.flashCor = BRANCO;
    l.pulo = 0;
    l.puloForca = 1.18;
    const [x, y] = FUROS_ARENA[slot];
    this.j.luz.explosao(x, y, { n: 14, vel: [160, 480], vida: [0.4, 0.9], tam: [6, 14], cor: c, arrasto: 1.2 });
    this.j.brilho(x, y, 320, c, 0.75, 0.5);
    this.pisca = 1;
    this.piscaCor = c;
  }

  bip() {
    this.api.som("nota");
  }

  // O laser que erra queima a parede: marca escura com a borda em brasa
  // que esfria, fumaça subindo e lascas de metal.
  marcaLaser(x, y) {
    const j = this.j;
    this.marcas.push({ x, y, r: aleatorio(7, 10) * K * 1.4, t: 0 });
    while (this.marcas.length > 40) this.marcas.shift();
    j.part.explosao(x, y, { n: 5, tex: "fx_fumaca", vel: [20, 70], ang: [230, 310], vida: [0.7, 1.3], tam: [26, 40], fim: 2.2,
      cor: "#141417", alfa: 0.5, grav: -60, giro: [-1, 1] });
    j.luz.explosao(x, y, { n: 12, tex: "fx_faisca", vel: [120, 380], vida: [0.25, 0.6], tam: [8, 14], cor: "#ffbf73", grav: 700, estica: 0.035 });
    j.part.explosao(x, y, { n: 6, tex: "fx_caco", vel: [90, 300], vida: [0.3, 0.7], tam: [4, 8], cor: "#9e9ea8", grav: 1000, giro: [-12, 12] });
    j.brilho(x, y, 90, "#ff7359", 0.7, 0.2);
  }

  // Tiro no LED do alto: estoura (só se estiver aceso) e volta piscando.
  tiroNoLed(x, y) {
    if (this.led > 0) return false;
    const [x0, y0, x1, y1] = ARENA.led;
    if (x < x0 || x > x1 || y < y0 || y > y1) return false;
    const j = this.j;
    this.led = 7;
    const [gx, gy] = ARENA.giroflex;
    j.luz.explosao(gx, gy, { n: 26, tex: "fx_faisca", vel: [120, 360], ang: [180, 360], vida: [0.4, 0.9], tam: [10, 16],
      cor: "#ffcc73", grav: 900, estica: 0.04 });
    const fundo = this.api.img.fundo_arena;
    if (fundo) {
      const [lx, ly, lw, lh] = ARENA.ledCaixa;
      const k = fundo.width / W;
      j.cacos.estourar(fundo, lx * k, ly * k, lw * k, lh * k, lw, lh, lx + lw / 2, ly + lh / 2, 1, 0, x, y,
        { n: 8, forca: 0.7, grav: 1200, vida: 1.3, sobe: 120 });
    }
    j.part.explosao(gx, gy, { n: 14, tex: "fx_caco", vel: [60, 200], ang: [200, 340], vida: [0.8, 1.4], tam: [5, 10], cor: "#ff402e",
      grav: 900, giro: [-14, 14] });
    this.api.som("vidro");
    j.tremer(4);
    return true;
  }

  ledAceso() {
    if (this.led <= 0) return 1;
    if (this.led < 1.4) return ((this.led * 6.5) % 1) > 0.35 + 0.4 * (this.led / 1.4) ? 1 : 0;
    return 0;
  }

  encerrou() {
    this.rodada++;
    this.bloqueado = true;
    this.mostrando = false;
    for (let i = 0; i < 9; i++) {
      const l = this.lanternas[i];
      if (!l) continue;
      l.some = 0;
      (this.descendo || (this.descendo = [])).push(l);
      this.lanternas[i] = null;
    }
  }

  // ---------------------------------------------------------------- vida
  sempre(dt) {
    const j = this.j;
    this.t += dt;
    for (const l of this.lanternas) if (l) this.animar(l, dt);
    if (this.descendo) {
      for (let i = this.descendo.length - 1; i >= 0; i--) {
        const l = this.descendo[i];
        this.animar(l, dt);
        if (l.desce) l.desce.t += dt;
        if (l.some >= 0) l.some += dt;
        if ((l.desce && l.desce.t >= l.desce.dur) || l.some >= 0.4) this.descendo.splice(i, 1);
      }
    }
    for (const m of this.marcas) m.t += dt;
    if (this.led > 0) {
      this.led = Math.max(0, this.led - dt);
      // a lâmpada queimada solta fumaça
      if (this.led > 1.4 && Math.random() < dt * 4 * j.fator) {
        j.part.explosao(ARENA.giroflex[0], ARENA.giroflex[1], { n: 1, tex: "fx_fumaca", vel: [10, 30], ang: [250, 290], vida: [1, 1.6],
          tam: [24, 40], fim: 2, cor: "#33302e", alfa: 0.5, grav: -50 });
      }
    }
    this.giro = Math.max(0, this.giro - dt);
    this.pisca = Math.max(0, this.pisca - dt * 2.5);
    // vapor dos canos e faíscas da caixa elétrica, de vez em quando
    this.proxVapor -= dt;
    if (this.proxVapor <= 0) {
      this.proxVapor = aleatorio(4, 8.5);
      const v = sorteio(ARENA.vapor);
      const ang = v[0] > W / 2 ? [192, 230] : [-50, -12];
      j.part.explosao(v[0], v[1], { n: 9, tex: "fx_nuvem", vel: [40, 110], ang, vida: [1.2, 2.0], tam: [30, 50], fim: 3,
        cor: "#c7ccd6", alfa: 0.3, grav: -16, arrasto: 0.6 });
    }
    this.proxFaisca -= dt;
    if (this.proxFaisca <= 0) {
      this.proxFaisca = aleatorio(6, 13);
      const [cx, cy] = ARENA.caixa;
      j.luz.explosao(cx, cy, { n: 8 + ((Math.random() * 7) | 0), tex: "fx_faisca", vel: [80, 300], ang: [190, 350], vida: [0.4, 0.9],
        tam: [8, 14], cor: "#ffbf4d", grav: 900, estica: 0.035 });
      j.brilho(cx, cy, 120, "#ffb34d", 0.6, 0.3);
    }
  }

  animar(l, dt) {
    if (l.sobe >= 0) { l.sobe += dt; if (l.sobe >= 0.22) l.sobe = -1; }
    if (l.quebraT > 0 && l.quebraT !== Infinity) l.quebraT = Math.max(0, l.quebraT - dt);
    if (l.flash > 0) l.flash = Math.max(0, l.flash - dt / 0.2);
    if (l.pulo >= 0) { l.pulo += dt; if (l.pulo >= 0.22) l.pulo = -1; }
    if (l.vermelho >= 0) { l.vermelho += dt; if (l.vermelho >= 0.82) l.vermelho = -1; }
  }

  // ---------------------------------------------------------------- desenho
  desenharFundo(ctx) {
    const j = this.j;
    const fundo = this.api.img.fundo_arena;
    if (fundo) ctx.drawImage(fundo, 0, 0, W, H);
    // a parede vive: o logo e os anéis dos furos acendem com a música
    const batida = Math.pow(Math.max(0, Math.cos(this.t * VOLTA * 2.133)), 6);
    if (fundo) {
      const k = fundo.width / W;
      ctx.globalCompositeOperation = "lighter";
      const [lx, ly, lw, lh] = ARENA.logo;
      ctx.globalAlpha = 0.08 + 0.16 * batida;
      ctx.drawImage(fundo, lx * k, ly * k, lw * k, lh * k, lx, ly, lw, lh);
      ctx.globalAlpha = 0.06 + 0.14 * batida;
      for (const [x, y] of FUROS_ARENA) ctx.drawImage(fundo, (x - 46) * k, (y - 46) * k, 92 * k, 92 * k, x - 46, y - 46, 92, 92);
      // na rodada fixa os anéis viram azuis (a arte "fixa" da 4.6)
      if (this.modoFixo) {
        const anel = j.tinta("fx_anel", "#59c8ff");
        ctx.globalAlpha = 0.45 + 0.3 * batida;
        if (anel) for (const [x, y] of FUROS_ARENA) ctx.drawImage(anel, x - 44, y - 44, 88, 88);
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    }
    // marcas do laser na parede
    if (this.marcas.length) {
      ctx.fillStyle = "#0c0b0d";
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      for (const m of this.marcas) { ctx.moveTo(m.x + m.r, m.y); ctx.arc(m.x, m.y, m.r, 0, VOLTA); }
      ctx.fill();
      ctx.globalCompositeOperation = "lighter";
      ctx.strokeStyle = "#ff7a33";
      ctx.lineWidth = 1.6;
      for (const m of this.marcas) {
        const a = 1 - m.t / 1.8;
        if (a <= 0) continue;
        ctx.globalAlpha = a;
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.r * 0.9, 0, VOLTA);
        ctx.stroke();
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    }
    // o LED do alto: aceso brilha vermelho; queimado fica escuro
    const [gx, gy] = ARENA.giroflex;
    const aceso = this.ledAceso();
    if (aceso > 0) {
      const brilho = j.tinta("fx_brilho", "#ff2e1f");
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.45 + 0.25 * batida;
      if (brilho) ctx.drawImage(brilho, gx - 40, gy - 40, 80, 80);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    } else {
      const [lx, ly, lw, lh] = ARENA.ledCaixa;
      ctx.fillStyle = "#140606";
      ctx.globalAlpha = 0.88;
      caminhoArredondado(ctx, lx + 3, ly + 2, lw - 6, lh - 3, 4);
      ctx.fill();
      ctx.globalAlpha = 1;
    }
    // o giroflex gira na troca de rodada
    if (this.giro > 0) {
      const a = Math.min(1, this.giro / 0.4) * 0.22;
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = this.giroCor;
      const ang = this.t * 9;
      for (let i = 0; i < 2; i++) {
        const b = ang + i * Math.PI;
        ctx.globalAlpha = a;
        ctx.beginPath();
        ctx.moveTo(gx, gy);
        ctx.lineTo(gx + Math.cos(b - 0.2) * 520, gy + Math.sin(b - 0.2) * 520);
        ctx.lineTo(gx + Math.cos(b + 0.2) * 520, gy + Math.sin(b + 0.2) * 520);
        ctx.closePath();
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    }
    this.desenharOrdem(ctx);
  }

  // A faixa da ordem embaixo dos furos: as cinco cores e a da vez acesa.
  desenharOrdem(ctx) {
    const y = ARENA.yOrdem;
    const larg = 76, esp = 10;
    const x0 = (W - (larg * 5 + esp * 4)) / 2;
    for (let i = 0; i < 5; i++) {
      const c = CORES_FX[CORES_SEQ[i]];
      const x = x0 + i * (larg + esp);
      const vez = !this.bloqueado && !this.mostrando && i === this.indice && this.sequencia.length > i;
      const feito = i < this.indice;
      ctx.globalAlpha = 0.85;
      ctx.fillStyle = "#070a12";
      caminhoArredondado(ctx, x, y - 13, larg, 26, 13);
      ctx.fill();
      ctx.globalAlpha = vez ? 1 : feito ? 0.75 : 0.5;
      ctx.strokeStyle = c;
      ctx.lineWidth = vez ? 2.5 : 1.2;
      ctx.stroke();
      if (vez) {
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = 0.25 + 0.2 * Math.sin(this.t * 8);
        ctx.fillStyle = c;
        ctx.fill();
        ctx.globalCompositeOperation = "source-over";
      }
      ctx.globalAlpha = vez ? 1 : feito ? 0.8 : 0.6;
      this.api.texto(ctx, i + 1 + "º", x + larg / 2, y + 1, { tamanho: 15, cor: c, peso: 900 });
    }
    ctx.globalAlpha = 1;
  }

  vermelhoDe(l) {
    if (l.vermelho < 0) return 0;
    const t = l.vermelho;
    if (t < 0.18) return t / 0.18;
    if (t < 0.36) return 1 - (t - 0.18) / 0.18;
    if (t < 0.58) return (t - 0.36) / 0.22;
    return Math.max(0, 1 - (t - 0.58) / 0.24);
  }

  desenharLanterna(ctx, l) {
    const img = this.api.img.lanterna;
    if (!img) return;
    const f = FOLHAS.lanterna;
    const [x, y0] = FUROS_ARENA[l.slot];
    let alfa = 1;
    if (l.sobe >= 0) alfa = Math.min(1, l.sobe / 0.16);
    if (l.desce) alfa = 1 - Math.min(1, l.desce.t / (l.desce.dur - 0.02));
    if (l.some >= 0) alfa = 1 - l.some / 0.4;
    if (alfa <= 0) return;
    const y = y0 + this.deslocamento(l);
    let esc = ESC_LANTERNA;
    if (l.pulo >= 0) {
      const extra = l.puloForca - 1;
      esc *= l.pulo < 0.06 ? 1 + extra * (l.pulo / 0.06) : 1 + extra * Math.max(0, 1 - (l.pulo - 0.06) / 0.16);
    }
    const quadro = l.quebraT > 0 ? f.acerto[QUADRO_COR[l.cor]] : QUADRO_COR[l.cor];
    const cw = img.width / f.q;
    const dw = f.w * esc, dh = f.h * esc;
    ctx.globalAlpha = alfa;
    ctx.drawImage(img, quadro * cw, 0, cw, img.height, x - dw / 2, y - dh / 2, dw, dh);
    const verm = this.vermelhoDe(l);
    if (verm > 0) {
      const vermelha = this.j.lanternaVermelha();
      if (vermelha) {
        ctx.globalAlpha = alfa * verm * 0.85;
        ctx.drawImage(vermelha, quadro * cw, 0, cw, img.height, x - dw / 2, y - dh / 2, dw, dh);
      }
    }
    if (l.flash > 0) {
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = alfa * l.flash * 0.9;
      ctx.drawImage(img, quadro * cw, 0, cw, img.height, x - dw / 2, y - dh / 2, dw, dh);
      ctx.globalCompositeOperation = "source-over";
    }
    ctx.globalAlpha = 1;
  }

  desenharAlvos(ctx) {
    if (this.descendo) for (const l of this.descendo) this.desenharLanterna(ctx, l);
    for (const l of this.lanternas) if (l) this.desenharLanterna(ctx, l);
    // a lanterna da vez acesa pisca a luz na parede
    if (this.pisca > 0) {
      const brilho = this.j.tinta("fx_brilho", this.piscaCor);
      if (brilho) {
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = this.pisca * 0.18;
        ctx.drawImage(brilho, -60, 180, W + 120, 720);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 1;
      }
    }
  }

  desenharFrente() {}
}

const CLASSES = { deserto: CenarioDeserto, mar: CenarioMar, bar: CenarioBar, arena: CenarioArena };

/* ======================================================================
   A PARTIDA: escolha, missão, jogo e fim; tudo o que é igual nas quatro
   fases (fase.gd): tempo, munição, recarga, combo, placar, mira, avisos.
   ====================================================================== */
class Partida {
  constructor(api) {
    this.api = api;
    this.fator = api.reduzido ? 0.45 : 1;
    this.tintas = new Map();
    this.medidas = new Map();
    this.medidor = document.createElement("canvas").getContext("2d");
    this.part = new Particulas(this, 240, false);
    this.luz = new Particulas(this, 280, true);
    this.cacos = new Cacos(this, 64);
    this.brilhos = [];
    for (let i = 0; i < 12; i++) this.brilhos.push({ vivo: false, x: 0, y: 0, tam: 0, img: null, a: 1, t: 0, dur: 1, anel: 0 });
    this.trajetos = [];
    for (let i = 0; i < 8; i++) this.trajetos.push({ vivo: false, x: 0, y: 0, dx: 0, dy: 0, t: 0, estilo: "laser", giro: 0, impacto: false });
    this.avisos = [];
    this.pops = [];
    this.mira = { x: W / 2, y: H * 0.55, pulso: 0 };
    this.teclas = new Set();
    this.relogio = 0;
    this.cartoes = CENARIOS.map((c, i) => ({ x: 35, y: 128 + i * 160, w: 470, h: 146 }));
    this.botaoAleatorio = { x: 160, y: 786, w: 220, h: 52 };
    // o peca() é passado adiante como função solta (cenários desenham pelo atlas)
    this.peca = (ctx, nome, x, y, w, h) => {
      const r = ATLAS[nome];
      const img = this.api.img.fx;
      if (r && img) ctx.drawImage(img, r[0], r[1], r[2], r[3], x, y, w, h);
    };
  }

  /* ---------------------------------------------------------- contrato */
  iniciar() {
    this.estado = "escolha";
    this.cen = null;
    this.cenario = null;
    this.autoT = TEMPO_ESCOLHA;
    this.roleta = null;
    this.escolhido = -1;
    this.escolhaT = 0;
    this.realce = (Math.random() * 4) | 0;
    this.tempo = TEMPO_PARTIDA;
    this.pontos = 0;
    this.disparos = 0;
    this.acertos = 0;
    this.balas = MUNICAO;
    this.recarregando = false;
    this.recargaFalta = 0;
    this.tempoRecarga = 1.1;
    this.combo = 0;
    this.comboTipo = "";
    this.melhorCombo = 0;
    this.comboT = 0;
    this.janelaCombo = 2.2;
    this.nivelAnuncio = -1;
    this.anuncio = null;
    this.instr = null;
    this.avisos.length = 0;
    this.pops.length = 0;
    this.faixaObj = null;
    this.claraoObj = null;
    this.fimT = 0;
    this.terminou = false;
    this.motivo = "";
    this.missaoT = 0;
    this.avisoRecarga = 0;
    this.part.limpar();
    this.luz.limpar();
    this.cacos.limpar();
    for (const b of this.brilhos) b.vivo = false;
    for (const s of this.trajetos) s.vivo = false;
    this.relogio = 0;
    this.placarAntes = { pontos: null, tempo: null, info: null };
    this.api.placar({ pontos: 0, tempo: TEMPO_PARTIDA, info: "ESCOLHA" });
  }

  atualizar(dt) {
    this.relogio += dt;
    this.moverMiraTeclado(dt);
    if (this.mira.pulso > 0) this.mira.pulso = Math.max(0, this.mira.pulso - dt * 6);
    if (this.estado === "escolha") this.atualizarEscolha(dt);
    else if (this.estado === "missao") {
      this.missaoT -= dt;
      if (this.missaoT <= 0) this.comecarPartida();
    } else if (this.estado === "jogo") this.atualizarJogo(dt);
    else if (this.estado === "fim") {
      this.fimT += dt;
      if (this.fimT >= 1.5 && !this.terminou) this.terminar();
    }
    if (this.cenario) this.cenario.sempre(dt);
    this.atualizarEfeitos(dt);
    this.atualizarPlacar();
  }

  desenhar(ctx) {
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    if (this.estado === "escolha" || !this.cenario) {
      this.desenharEscolha(ctx);
      this.desenharTrajetos(ctx);
      this.luz.desenhar(ctx);
      this.desenharMira(ctx);
      return;
    }
    const c = this.cenario;
    c.desenharFundo(ctx);
    c.desenharAlvos(ctx);
    c.desenharFrente(ctx);
    this.cacos.desenhar(ctx);
    this.part.desenhar(ctx);
    this.desenharBrilhos(ctx);
    this.luz.desenhar(ctx);
    this.desenharTrajetos(ctx);
    this.desenharAnuncio(ctx);
    this.desenharAvisos(ctx);
    this.desenharHud(ctx);
    if (this.estado === "missao") this.desenharMissao(ctx);
    this.desenharFaixa(ctx);
    this.desenharClarao(ctx);
    this.desenharMira(ctx);
  }

  apertar(x, y) {
    this.mira.x = x;
    this.mira.y = y;
    if (this.estado === "escolha") { this.tocarEscolha(x, y); return; }
    if (this.estado === "missao") { this.comecarPartida(); return; }
    if (this.estado !== "jogo") return;
    if (y >= HUD_Y) { this.recarregar(); return; }
    this.atirar(x, y);
  }

  mover(x, y) {
    this.mira.x = x;
    this.mira.y = y;
    if (this.estado === "escolha" && !this.roleta && this.escolhido < 0) {
      const i = this.cartaoEm(x, y);
      if (i >= 0) this.realce = i;
    }
  }

  tecla(codigo, apertada) {
    if (apertada) this.teclas.add(codigo);
    else { this.teclas.delete(codigo); return; }
    if (this.estado === "escolha") {
      if (this.roleta || this.escolhido >= 0) return;
      if (codigo === "ArrowUp") this.realce = (this.realce + 3) % 4;
      else if (codigo === "ArrowDown") this.realce = (this.realce + 1) % 4;
      else if (codigo === "Enter" || codigo === "Space") this.escolher(this.realce);
      else if (/^Digit[1-4]$/.test(codigo)) this.escolher(Number(codigo.slice(5)) - 1);
      else if (codigo === "KeyA") this.iniciarRoleta();
      return;
    }
    if (this.estado === "missao") {
      if (codigo === "Enter" || codigo === "Space") this.comecarPartida();
      return;
    }
    if (this.estado !== "jogo") return;
    if (codigo === "Space" || codigo === "Enter" || codigo === "KeyF") this.atirar(this.mira.x, this.mira.y);
    else if (codigo === "KeyR") this.recarregar();
  }

  destruir() {
    this.teclas.clear();
  }

  /* ---------------------------------------------------------- utilidades */
  // A imagem do atlas multiplicada pela cor (o modulate do Godot), guardada.
  tinta(nome, cor = BRANCO) {
    const chave = nome + cor;
    let c = this.tintas.get(chave);
    if (c !== undefined) return c;
    const img = this.api.img.fx;
    const r = ATLAS[nome];
    if (!img || !r) { this.tintas.set(chave, null); return null; }
    c = document.createElement("canvas");
    c.width = r[2];
    c.height = r[3];
    const g = c.getContext("2d");
    g.drawImage(img, r[0], r[1], r[2], r[3], 0, 0, r[2], r[3]);
    if (cor !== BRANCO) {
      g.globalCompositeOperation = "multiply";
      g.fillStyle = cor;
      g.fillRect(0, 0, r[2], r[3]);
      g.globalCompositeOperation = "destination-in";
      g.drawImage(img, r[0], r[1], r[2], r[3], 0, 0, r[2], r[3]);
    }
    this.tintas.set(chave, c);
    return c;
  }

  // A folha das lanternas em vermelho (todas piscam vermelho na ordem errada).
  lanternaVermelha() {
    if (this.vermelha !== undefined) return this.vermelha;
    const img = this.api.img.lanterna;
    if (!img) { this.vermelha = null; return null; }
    const c = document.createElement("canvas");
    c.width = img.width;
    c.height = img.height;
    const g = c.getContext("2d");
    g.drawImage(img, 0, 0);
    g.globalCompositeOperation = "multiply";
    g.fillStyle = "#ff2626";
    g.fillRect(0, 0, c.width, c.height);
    g.globalCompositeOperation = "destination-in";
    g.drawImage(img, 0, 0);
    this.vermelha = c;
    return c;
  }

  largura(texto, tamanho, peso = 800) {
    const chave = texto + "|" + tamanho + "|" + peso;
    let w = this.medidas.get(chave);
    if (w === undefined) {
      this.medidor.font = `${peso} ${Math.round(tamanho)}px Poppins, Manrope, system-ui, sans-serif`;
      w = this.medidor.measureText(texto).width;
      this.medidas.set(chave, w);
    }
    return w;
  }

  /* ---------------------------------------------------------- escolha */
  cartaoEm(x, y) {
    for (let i = 0; i < this.cartoes.length; i++) {
      const r = this.cartoes[i];
      if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return i;
    }
    return -1;
  }

  tocarEscolha(x, y) {
    if (this.roleta || this.escolhido >= 0) return;
    const b = this.botaoAleatorio;
    if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) { this.iniciarRoleta(); return; }
    const i = this.cartaoEm(x, y);
    if (i >= 0) {
      this.disparar(x, y, "menu");
      this.escolher(i);
    }
  }

  // A roleta corre pelos cartões, rápida no começo e freando.
  iniciarRoleta() {
    if (this.roleta || this.escolhido >= 0) return;
    this.roleta = { passo: 0.06, t: 0, giros: 0, total: 9 + ((Math.random() * 4) | 0) };
    this.api.som("whoosh");
  }

  atualizarEscolha(dt) {
    if (this.escolhido >= 0) {
      this.escolhaT += dt;
      if (this.escolhaT >= 0.6) this.irParaMissao(this.escolhido);
      return;
    }
    if (this.roleta) {
      const r = this.roleta;
      r.t += dt;
      if (r.t >= r.passo) {
        r.t = 0;
        r.giros++;
        r.passo *= 1.17;
        this.realce = (this.realce + 1) % 4;
        this.api.som("clique");
        if (r.giros >= r.total) { this.roleta = null; this.escolher(this.realce); }
      }
      return;
    }
    this.autoT -= dt;
    if (this.autoT <= 0) this.iniciarRoleta();
  }

  escolher(i) {
    if (this.escolhido >= 0) return;
    this.escolhido = i;
    this.realce = i;
    this.escolhaT = 0;
    this.api.som("moeda");
    const r = this.cartoes[i];
    this.luz.explosao(r.x + r.w / 2, r.y + r.h / 2, { n: 26, vel: [200, 600], vida: [0.3, 0.7], tam: [8, 14],
      cor: CENARIOS[i].cor, estica: 0.03, arrasto: 1.5, espalha: 200 });
  }

  irParaMissao(i) {
    const cen = CENARIOS[i];
    this.cen = cen;
    this.cenario = new CLASSES[cen.id](this);
    this.cenario.preparar();
    this.estado = "missao";
    this.missaoT = TEMPO_MISSAO;
    this.janelaCombo = cen.janela;
    this.tempoRecarga = cen.recarga;
    this.corMira = clarear(cen.tema, 0.12);
    this.part.limpar();
    this.luz.limpar();
    this.api.placar({ info: cen.curto });
    this.api.som("whoosh");
  }

  comecarPartida() {
    if (this.estado !== "missao") return;
    this.estado = "jogo";
    this.instrucao("COMEÇOU!", clarear(this.cen.tema, 0.4));
    this.api.som("nota");
    this.cenario.comecar();
  }

  /* ---------------------------------------------------------- jogo */
  atualizarJogo(dt) {
    this.tempo -= dt;
    if (this.recarregando) {
      this.recargaFalta -= dt;
      if (this.recargaFalta <= 0) {
        this.recarregando = false;
        this.balas = MUNICAO;
        this.api.som("clique");
      }
    }
    if (this.comboT > 0 && this.comboT !== Infinity) {
      this.comboT -= dt;
      if (this.comboT <= 0) { this.combo = 0; this.comboTipo = ""; this.nivelAnuncio = -1; }
    }
    this.avisoRecarga = Math.max(0, this.avisoRecarga - dt);
    this.cenario.atualizar(dt);
    if (this.tempo <= 0 && this.estado === "jogo") {
      this.tempo = 0;
      this.encerrar("TEMPO ESGOTADO!");
    }
  }

  moverMiraTeclado(dt) {
    if (!this.teclas.size) return;
    const v = 520 * dt;
    if (this.teclas.has("ArrowLeft")) this.mira.x -= v;
    if (this.teclas.has("ArrowRight")) this.mira.x += v;
    if (this.estado !== "escolha") {
      if (this.teclas.has("ArrowUp")) this.mira.y -= v;
      if (this.teclas.has("ArrowDown")) this.mira.y += v;
    }
    this.mira.x = limitar(this.mira.x, 0, W);
    this.mira.y = limitar(this.mira.y, 0, H);
  }

  estiloTiro() {
    return this.cenario.estiloTiro ? this.cenario.estiloTiro() : "bar";
  }

  atirar(x, y) {
    if (this.recarregando) {
      if (this.avisoRecarga <= 0) { this.avisoRecarga = 1; this.instrucao("RECARREGANDO...", "#59ebff"); }
      return;
    }
    if (!this.cenario.podeAtirar()) return;
    if (this.balas <= 0) {
      // sem bala: o gatilho estala e a arma já recarrega (no celular não
      // há o botão do lado da arma)
      this.api.som("clique");
      this.recarregar();
      return;
    }
    this.balas--;
    this.disparos++;
    this.mira.pulso = 1;
    this.api.som("tiro");
    this.disparar(x, y, this.estiloTiro());
    this.cenario.tiro(x, y);
    if (this.balas === 0 && this.estado === "jogo") this.instrucao("SEM BALA! TOQUE PARA RECARREGAR", "#ff7359");
  }

  recarregar() {
    if (this.estado !== "jogo" || this.recarregando || this.balas >= MUNICAO) return;
    this.recarregando = true;
    this.recargaFalta = this.tempoRecarga;
    this.api.som("whoosh");
  }

  ganhar(valor, x, y, cor = OURO, esc = 1) {
    this.pontos += valor;
    this.acertos++;
    this.pop(x, y, "+" + valor, cor, esc);
  }

  // Bônus (barril, janela, cristal, LED, peixe): pontos e acerto, sem combo.
  bonus(valor, x, y, cor = OURO, esc = 1.15) {
    this.pontos += valor;
    this.acertos++;
    this.pop(x, y, "+" + valor, cor, esc);
  }

  perder(valor, x, y, texto) {
    this.pontos -= valor;
    this.pop(x, y, "-" + valor, VERMELHO, 1.1);
    if (texto) this.mostrar(x, y, texto, VERMELHO);
    this.quebrarCombo();
  }

  errar(x, y, texto = "ERROU!") {
    this.quebrarCombo();
    this.mostrar(x, y, texto, "#ffd1c7");
  }

  // Mais um acerto seguido (tipo: no Egito o combo é do mesmo astro).
  registrarCombo(tipo = "") {
    if (this.comboT > 0 && tipo === this.comboTipo) this.combo++;
    else this.combo = 1;
    this.comboTipo = tipo;
    this.comboT = this.janelaCombo;
    this.melhorCombo = Math.max(this.melhorCombo, this.combo);
    this.anunciarCombo(this.combo);
  }

  quebrarCombo() {
    this.combo = 0;
    this.comboTipo = "";
    this.comboT = 0;
    this.nivelAnuncio = -1;
  }

  encerrar(texto) {
    if (this.estado === "fim") return;
    this.estado = "fim";
    this.fimT = 0;
    this.motivo = texto;
    this.recarregando = false;
    this.cenario.encerrou();
    this.faixa(texto, clarear(this.cen.tema, 0.3), 1.4);
    this.api.som("apito");
  }

  terminar() {
    this.terminou = true;
    const precisao = this.disparos ? Math.round((this.acertos / this.disparos) * 100) : 0;
    const combo = this.melhorCombo >= 2 ? ` · melhor combo x${this.melhorCombo}` : "";
    this.api.terminar({
      pontos: Math.max(0, Math.round(this.pontos)),
      titulo: this.motivo === "3 BOMBAS!" ? "Três bombas!" : "Tempo esgotado!",
      detalhe: `${this.cen.titulo}: ${this.acertos} acertos em ${this.disparos} tiros (${precisao}% de precisão)${combo}`,
    });
  }

  atualizarPlacar() {
    const a = this.placarAntes;
    const pontos = Math.round(this.pontos);
    const tempo = this.estado === "escolha" ? TEMPO_PARTIDA : Math.ceil(Math.max(0, this.tempo));
    if (pontos !== a.pontos || tempo !== a.tempo) {
      a.pontos = pontos;
      a.tempo = tempo;
      this.api.placar({ pontos, tempo: Math.max(0, this.tempo) });
    }
  }

  vibrar(ms) {
    this.api.vibrar(ms);
  }

  tremer(forca) {
    // forca em px da tela 1024 (como em fase.gd)
    this.api.tremer(forca * K * 1.3);
  }

  /* ---------------------------------------------------------- efeitos */
  atualizarEfeitos(dt) {
    this.part.atualizar(dt);
    this.luz.atualizar(dt);
    this.cacos.atualizar(dt);
    for (const b of this.brilhos) {
      if (!b.vivo) continue;
      b.t += dt;
      if (b.t >= b.dur) b.vivo = false;
    }
    for (const s of this.trajetos) {
      if (!s.vivo) continue;
      s.t += dt;
      const voo = FEIXES[s.estilo] ? FEIXES[s.estilo][0] : BALA_VOO;
      if (!s.impacto && s.t >= voo) { s.impacto = true; this.impacto(s); }
      const fim = FEIXES[s.estilo] ? Math.max(FEIXES[s.estilo][1], voo + IMPACTO) : voo + IMPACTO;
      if (s.t > fim) s.vivo = false;
    }
    for (let i = this.avisos.length - 1; i >= 0; i--) {
      this.avisos[i].t += dt;
      if (this.avisos[i].t > 0.8) this.avisos.splice(i, 1);
    }
    for (let i = this.pops.length - 1; i >= 0; i--) {
      this.pops[i].t += dt;
      if (this.pops[i].t > 1) this.pops.splice(i, 1);
    }
    if (this.instr) { this.instr.t += dt; if (this.instr.t > 2.4) this.instr = null; }
    if (this.anuncio) { this.anuncio.t += dt; if (this.anuncio.t > this.anuncio.fim) this.anuncio = null; }
    if (this.faixaObj) { this.faixaObj.t += dt; if (this.faixaObj.t > this.faixaObj.dur) this.faixaObj = null; }
    if (this.claraoObj) { this.claraoObj.t += dt; if (this.claraoObj.t > this.claraoObj.dur) this.claraoObj = null; }
  }

  // Clarão redondo que cresce e some (luz_sprite_breve): poucos, em rodízio.
  brilho(x, y, tam, cor, alfa = 0.8, dur = 0.35) {
    let b = this.brilhos.find((q) => !q.vivo);
    if (!b) b = this.brilhos.reduce((m, q) => (q.t > m.t ? q : m));
    b.vivo = true; b.x = x; b.y = y; b.tam = tam * 0.6 * K; b.img = this.tinta("fx_brilho", cor); b.a = alfa; b.t = 0; b.dur = dur; b.anel = 0;
  }

  // Anel de choque (a bomba): cresce `mult` vezes e some.
  anel(x, y, tam, mult, cor, alfa, dur) {
    let b = this.brilhos.find((q) => !q.vivo);
    if (!b) b = this.brilhos.reduce((m, q) => (q.t > m.t ? q : m));
    b.vivo = true; b.x = x; b.y = y; b.tam = tam * K; b.img = this.tinta("fx_anel", cor); b.a = alfa; b.t = 0; b.dur = dur; b.anel = mult;
  }

  desenharBrilhos(ctx) {
    ctx.globalCompositeOperation = "lighter";
    for (const b of this.brilhos) {
      if (!b.vivo || !b.img) continue;
      const k = b.t / b.dur;
      const tam = b.anel ? b.tam * misturar(1, b.anel, 1 - (1 - k) * (1 - k)) : b.tam * (1 + 0.7 * k);
      ctx.globalAlpha = b.a * (1 - k);
      ctx.drawImage(b.img, b.x - tam / 2, b.y - tam / 2, tam, tam);
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
  }

  clarao(cor, alfa, dur = 0.18) {
    this.claraoObj = { cor, a: this.api.reduzido ? alfa * 0.5 : alfa, t: 0, dur };
  }

  desenharClarao(ctx) {
    const c = this.claraoObj;
    if (!c) return;
    ctx.globalAlpha = c.a * (1 - c.t / c.dur);
    ctx.fillStyle = c.cor;
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 1;
  }

  // Faixa grande no meio da tela (TEMPO ESGOTADO!, 3 BOMBAS!).
  faixa(texto, cor, dur = 1.3) {
    this.faixaObj = { texto, cor, t: 0, dur };
  }

  desenharFaixa(ctx) {
    const f = this.faixaObj;
    if (!f) return;
    const esc = f.t < 0.3 ? misturar(1.6, 1, saidaVolta(f.t / 0.3)) : 1;
    const alfa = f.t > f.dur - 0.3 ? Math.max(0, (f.dur - f.t) / 0.3) : 1;
    const larg = this.largura(f.texto, 50, 900);
    const tam = 50 * esc * Math.min(1, (W - 40) / larg);
    ctx.globalAlpha = alfa * 0.55;
    ctx.fillStyle = "#03060f";
    ctx.fillRect(0, H / 2 - 48, W, 96);
    ctx.globalAlpha = alfa;
    this.api.texto(ctx, f.texto, W / 2, H / 2, { tamanho: tam, cor: f.cor, contorno: "rgba(0,0,0,0.75)", peso: 900 });
    ctx.globalAlpha = 1;
  }

  /* ---------------------------------------------------------- avisos */
  mostrar(x, y, texto, cor = "#ffd1c7") {
    for (let i = this.avisos.length - 1; i >= 0; i--) {
      const a = this.avisos[i];
      if (Math.hypot(a.x - x, a.y - y) < 84) this.avisos.splice(i, 1);
    }
    this.avisos.push({ x: limitar(x, 70, W - 70), y, texto, cor, t: 0 });
    while (this.avisos.length > 4) this.avisos.shift();
  }

  pop(x, y, texto, cor, esc = 1) {
    this.pops.push({ x: limitar(x, 34, W - 34), y, texto, cor, esc: limitar(esc, 0.6, 1.6), t: 0 });
    while (this.pops.length > 8) this.pops.shift();
  }

  instrucao(texto, cor = BRANCO) {
    this.instr = { texto, cor, t: 0 };
  }

  desenharAvisos(ctx) {
    const api = this.api;
    for (const a of this.avisos) {
      const k = a.t / 0.8;
      ctx.globalAlpha = limitar((1 - k) * 2.5, 0, 1) * limitar(a.t * 12, 0, 1);
      api.texto(ctx, a.texto, a.x, a.y - 41 - 21 * k, { tamanho: 19, cor: a.cor, contorno: "rgba(0,0,0,0.7)", peso: 900 });
    }
    for (const p of this.pops) {
      const k = p.t;
      const s = p.esc * (1 + 0.6 * Math.max(0, 1 - p.t * 7));
      ctx.globalAlpha = limitar((1 - k) * 2.2, 0, 1);
      api.texto(ctx, p.texto, p.x, p.y - 21 - 47 * k, { tamanho: 27 * s, cor: p.cor, contorno: "rgba(0,0,0,0.72)", peso: 900 });
    }
    const ins = this.instr;
    if (ins) {
      const t = ins.t;
      const a = limitar(t * 6, 0, 1) * limitar((2.4 - t) * 3, 0, 1);
      const w = Math.min(W - 24, this.largura(ins.texto, 15, 800) + 30);
      const tam = 15 * Math.min(1, (W - 54) / this.largura(ins.texto, 15, 800));
      ctx.globalAlpha = 0.62 * a;
      ctx.fillStyle = "#000000";
      caminhoArredondado(ctx, (W - w) / 2, 14, w, 30, 15);
      ctx.fill();
      ctx.globalAlpha = 0.18 * a;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.globalAlpha = a;
      api.texto(ctx, ins.texto, W / 2, 30, { tamanho: tam, cor: ins.cor, peso: 800 });
    }
    ctx.globalAlpha = 1;
  }

  /* ---------------------------------------------------------- anunciador */
  anunciarCombo(n) {
    if (n < 2 || !this.cen) return;
    let nivel = -1;
    for (let i = 0; i < NIVEIS_COMBO.length; i++) if (n >= NIVEIS_COMBO[i][0]) nivel = i;
    if (nivel < 0) return;
    let novo = nivel !== this.nivelAnuncio;
    if (!novo && nivel === NIVEIS_COMBO.length - 1 && (n - NIVEIS_COMBO[nivel][0]) % 4 === 0) novo = true;
    this.nivelAnuncio = nivel;
    this.mostrarAnuncio(NIVEIS_COMBO[nivel][1], n > 2 ? "x" + n : "", novo, 1 + 0.06 * nivel);
    if (novo) this.api.som("combo");
  }

  // Anúncio especial (POWER OF RA!, PERFECT SEQUENCE!, POSEIDON'S TREASURE!).
  especial(texto) {
    this.mostrarAnuncio(texto, "", true, 1.25);
    this.api.som("strike");
  }

  mostrarAnuncio(texto, numero, forte, forca) {
    const tema = TEMAS[this.cen.id];
    // texto comprido diminui até caber na tela
    forca = Math.min(forca, (W - 37) / (this.largura(texto, 55, 900) + 13));
    const entra = forte ? 0.28 : 0.16;
    const fica = entra + (forte ? 0.55 : 0.4);
    this.anuncio = { texto, numero, forte, forca, tema, t: 0, entra, fica, fim: fica + 0.45 };
    if (!forte) return;
    const x = W / 2, y = H * tema.y;
    if (tema.estilo === "agua") {
      this.part.explosao(x, y, { n: 16, tex: "mar_bolha", vel: [60, 260], ang: [200, 340], vida: [0.6, 1.2], tam: [12, 26], fim: 0.9,
        cor: "#d9f7ff", alfa: 0.9, grav: -300, espalha: 260 });
    } else if (tema.estilo === "saloon") {
      this.luz.explosao(x, y, { n: 22, vel: [250, 700], vida: [0.25, 0.55], tam: [6, 12], cor: "#ffb34d", grav: 900, estica: 0.04, espalha: 200 });
    } else {
      this.luz.explosao(x, y, { n: Math.round(24 * forca), vel: [200, 620], vida: [0.3, 0.7], tam: [7, 14], cor: tema.faisca, grav: 300,
        estica: 0.03, arrasto: 1.5, espalha: 220 });
    }
  }

  desenharAnuncio(ctx) {
    const a = this.anuncio;
    if (!a) return;
    const tema = a.tema;
    let esc = a.forca, dy = 0, alfa = 1;
    if (a.t < a.entra) esc = misturar(a.forte ? 1.9 : 1.12, 1, saidaVolta(a.t / a.entra)) * a.forca;
    if (a.t > a.fica) {
      const k = Math.min(1, (a.t - a.fica) / 0.45);
      dy = -37 * senoEntra(k);
      alfa = 1 - k;
    }
    const x = W / 2, y = H * tema.y + dy;
    // clarão e raios de luz saindo de trás do texto
    const clarao = this.tinta("fx_brilho", tema.clarao);
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = alfa * (a.forte ? misturar(1, 0.25, Math.min(1, a.t / 0.5)) : 0.25);
    if (clarao) ctx.drawImage(clarao, x - 253 * esc, y - 81 * esc, 506 * esc, 162 * esc);
    if (!tema.grad) {
      const g = ctx.createRadialGradient(0, 0, 10, 0, 0, 210);
      g.addColorStop(0, tema.clarao);
      g.addColorStop(1, "rgba(0,0,0,0)");
      tema.grad = g;
    }
    ctx.globalAlpha = alfa * 0.45;
    ctx.fillStyle = tema.grad;
    const giro = this.relogio * 0.8;
    ctx.translate(x, y);
    ctx.rotate(giro);
    ctx.scale(esc, esc);
    ctx.beginPath();
    for (let i = 0; i < 14; i++) {
      const b = (i / 14) * VOLTA;
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.cos(b - 0.05) * 210, Math.sin(b - 0.05) * 210);
      ctx.lineTo(Math.cos(b + 0.05) * 210, Math.sin(b + 0.05) * 210);
      ctx.closePath();
    }
    ctx.fill();
    ctx.scale(1 / esc, 1 / esc);
    ctx.rotate(-giro);
    ctx.translate(-x, -y);
    ctx.globalCompositeOperation = "source-over";
    // no Bar o texto vem numa tábua do saloon, com veios e pregos
    if (tema.estilo === "saloon") {
      ctx.globalAlpha = alfa * 0.96;
      ctx.translate(x, y);
      ctx.scale(esc, esc);
      ctx.fillStyle = "#4d290f";
      caminhoArredondado(ctx, -200, -38, 400, 76, 6);
      ctx.fill();
      ctx.strokeStyle = "#1f0d03";
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.strokeStyle = "rgba(122, 71, 31, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < 5; i++) { ctx.moveTo(-188, -24 + i * 12.6); ctx.lineTo(188, -24 + i * 12.6 + (i % 2) * 1.6); }
      ctx.stroke();
      ctx.fillStyle = "#1f1a14";
      for (const [px, py] of [[-186, -25], [186, -25], [-186, 25], [186, 25]]) { ctx.beginPath(); ctx.arc(px, py, 3.7, 0, VOLTA); ctx.fill(); }
      ctx.scale(1 / esc, 1 / esc);
      ctx.translate(-x, -y);
    }
    ctx.globalAlpha = alfa;
    this.api.texto(ctx, a.texto, x, y - (a.numero ? 6 : 0) * esc, { tamanho: 50 * esc, cor: tema.texto, contorno: tema.contorno, peso: 900 });
    if (a.numero) this.api.texto(ctx, a.numero, x, y + 30 * esc, { tamanho: 28 * esc, cor: BRANCO, contorno: tema.contorno, peso: 900 });
    ctx.globalAlpha = 1;
  }

  /* ---------------------------------------------------------- o tiro */
  disparar(x, y, estilo) {
    let s = this.trajetos.find((q) => !q.vivo);
    if (!s) s = this.trajetos.reduce((m, q) => (q.t > m.t ? q : m));
    s.vivo = true; s.x = x; s.y = y; s.t = 0; s.estilo = estilo; s.giro = Math.random() * VOLTA; s.impacto = false;
    // a arma fica embaixo da tela, puxada para o lado da mira
    s.dx = misturar(W / 2, x, 0.3);
    s.dy = H + 21;
    if (FEIXES[estilo]) this.peloCaminho(s);
  }

  // O que o laser deixa no caminho na hora em que acende.
  peloCaminho(s) {
    const dx = s.x - s.dx, dy = s.y - s.dy;
    const d = Math.hypot(dx, dy) || 1;
    const lx = -dy / d, ly = dx / d;
    if (s.estilo === "sol") {
      const img = this.tinta("fx_ponto", "#ffd973");
      for (let i = 0; i < Math.round(7 * this.fator); i++) {
        const k = aleatorio(0.15, 0.95), e = aleatorio(-8, 8) * K, a = aleatorio(230, 310) * RAD, v = aleatorio(10, 50) * K, t = aleatorio(5, 10) * K;
        this.luz.soltar(s.dx + dx * k + lx * e, s.dy + dy * k + ly * e, Math.cos(a) * v, Math.sin(a) * v, aleatorio(0.35, 0.7), t, t * 0.2,
          img, 1, -40 * K, 1);
      }
    } else if (s.estilo === "lua") {
      const img = this.tinta("fx_ponto", "#ebf5ff");
      for (let i = 0; i < Math.round(9 * this.fator); i++) {
        const k = aleatorio(0.12, 0.95), e = aleatorio(-10, 10) * K, a = Math.random() * VOLTA, v = aleatorio(5, 30) * K, t = aleatorio(3, 7) * K;
        this.luz.soltar(s.dx + dx * k + lx * e, s.dy + dy * k + ly * e, Math.cos(a) * v, Math.sin(a) * v, aleatorio(0.4, 0.8), t, t * 0.2,
          img, 1, 10 * K, 1);
      }
    } else if (s.estilo === "mar") {
      const img = this.tinta("mar_bolha", "#d9f7ff");
      const n = Math.round(limitar(d / K / 60, 8, 20) * this.fator);
      for (let i = 0; i < n; i++) {
        const k = (i + Math.random()) / n, e = aleatorio(-10, 10) * K, a = aleatorio(250, 290) * RAD, v = aleatorio(15, 60) * K, t = aleatorio(6, 14) * K;
        this.part.soltar(s.dx + dx * k + lx * e, s.dy + dy * k + ly * e, Math.cos(a) * v, Math.sin(a) * v, aleatorio(0.6, 1.1), t, t * 0.9,
          img, 0.8, -160 * K, 1.5);
      }
    }
  }

  impacto(s) {
    const x = s.x, y = s.y;
    switch (s.estilo) {
      case "laser":
        this.luz.explosao(x, y, { n: 22, vel: [220, 640], vida: [0.35, 0.6], tam: [4, 8], cor: "#fff2b3", grav: 1200, estica: 0.03 });
        break;
      case "sol":
        this.luz.explosao(x, y, { n: 10, vel: [60, 220], ang: [200, 340], vida: [0.4, 0.8], tam: [8, 16], cor: "#ffd966", grav: -60, arrasto: 2 });
        break;
      case "lua":
        this.luz.explosao(x, y, { n: 12, vel: [40, 170], vida: [0.5, 0.9], tam: [6, 12], cor: "#e0f0ff", grav: 40, arrasto: 2.5 });
        break;
      case "mar":
        this.part.explosao(x, y, { n: 7, tex: "mar_bolha", vel: [30, 110], ang: [220, 320], vida: [0.6, 1.1], tam: [10, 22], fim: 0.9,
          cor: "#d9f7ff", alfa: 0.85, grav: -220, arrasto: 1.5, espalha: 10 });
        break;
      case "bar":
        this.luz.explosao(x, y, { n: 8, vel: [180, 420], vida: [0.15, 0.32], tam: [5, 9], cor: "#ffbf59", grav: 600, estica: 0.05 });
        this.part.explosao(x, y, { n: 3, tex: "fx_fumaca", vel: [10, 40], ang: [240, 300], vida: [0.7, 1.2], tam: [26, 40], fim: 2.2,
          cor: "#bfb8ad", alfa: 0.45, grav: -40 });
        break;
      default:
        this.luz.explosao(x, y, { n: 9, vel: [120, 360], vida: [0.18, 0.4], tam: [5, 10], cor: "#ff7a73", estica: 0.04, arrasto: 2 });
    }
  }

  desenharTrajetos(ctx) {
    let algum = false;
    for (const s of this.trajetos) if (s.vivo) { algum = true; break; }
    if (!algum) return;
    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    for (const s of this.trajetos) {
      if (!s.vivo) continue;
      if (FEIXES[s.estilo]) this.desenharLaser(ctx, s);
      else if (s.estilo === "bar") this.desenharBala(ctx, s);
      else this.desenharAneis(ctx, s);
    }
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
  }

  glow(ctx, x, y, r, cor, a) {
    const img = this.tinta("fx_brilho", cor);
    if (!img || a <= 0) return;
    ctx.globalAlpha = Math.min(1, a);
    ctx.drawImage(img, x - r, y - r, r * 2, r * 2);
  }

  // Laser (arena, sol, lua, mar): acende inteiro na hora e apaga; um pulso
  // corre da arma até o ponto e lá fica o impacto do cenário.
  desenharLaser(ctx, s) {
    const [voo, vida, cores, larg] = FEIXES[s.estilo];
    const a = limitar(1 - s.t / vida, 0, 1);
    if (a > 0) {
      for (let i = 0; i < 3; i++) {
        ctx.strokeStyle = cores[i][0];
        ctx.globalAlpha = cores[i][1] * a;
        ctx.lineWidth = larg[i] * K;
        ctx.beginPath();
        ctx.moveTo(s.dx, s.dy);
        ctx.lineTo(s.x, s.y);
        ctx.stroke();
      }
    }
    const halo = cores[0][0];
    if (s.t < voo) {
      const k = s.t / voo;
      const cx = misturar(s.dx, s.x, k), cy = misturar(s.dy, s.y, k);
      this.glow(ctx, cx, cy, 34 * K, halo, 0.9);
      this.glow(ctx, cx, cy, 10 * K, cores[2][0], 1);
      // o clarão da arma na beirada de baixo
      const img = this.tinta("fx_brilho", halo);
      if (img) { ctx.globalAlpha = (1 - k) * 0.5; ctx.drawImage(img, s.dx - 137, H - 105, 274, 210); }
      return;
    }
    const k2 = limitar((s.t - voo) / IMPACTO, 0, 1);
    const fade = 1 - k2;
    if (s.estilo === "laser") {
      this.glow(ctx, s.x, s.y, (22 + 96 * k2) * K, "#ff9973", 0.7 * fade);
      const r = (12 + 64 * k2) * K;
      const anel = this.tinta("fx_anel", "#ff4d40");
      if (anel) { ctx.globalAlpha = fade; ctx.drawImage(anel, s.x - r, s.y - r, r * 2, r * 2); }
      this.glow(ctx, s.x, s.y, (14 * fade + 4) * K, "#ffe6d9", fade);
    } else if (s.estilo === "sol") {
      const r = (40 + 70 * k2) * K;
      const est = this.tinta("fx_estrela", "#ffe68c");
      if (est) {
        const g = s.giro + k2 * 2;
        ctx.globalAlpha = fade;
        ctx.translate(s.x, s.y);
        ctx.rotate(g);
        ctx.drawImage(est, -r, -r, r * 2, r * 2);
        ctx.rotate(-g);
        ctx.translate(-s.x, -s.y);
      }
      this.glow(ctx, s.x, s.y, (34 * fade + 10) * K, "#ffcc59", fade);
    } else if (s.estilo === "lua") {
      const r = (16 + 70 * k2) * K;
      const anel = this.tinta("fx_anel", "#d9ebff");
      if (anel) { ctx.globalAlpha = fade; ctx.drawImage(anel, s.x - r, s.y - r, r * 2, r * 2); }
      this.glow(ctx, s.x, s.y, (30 * fade + 8) * K, "#f2f7ff", fade);
    } else {
      const anel = this.tinta("fx_anel", "#80ebff");
      for (let i = 0; i < 2; i++) {
        const kk = limitar(k2 * 1.2 - i * 0.25, 0, 1);
        const r = (14 + 80 * kk) * K;
        if (anel) { ctx.globalAlpha = (1 - kk) * 0.7; ctx.drawImage(anel, s.x - r, s.y - r * 0.8, r * 2, r * 1.6); }
      }
      this.glow(ctx, s.x, s.y, (24 * fade + 6) * K, "#99f2ff", fade);
    }
  }

  // Bar: a BALA, sem laser — o clarão da boca da arma e a bala traçante
  // correndo até o ponto.
  desenharBala(ctx, s) {
    if (s.t < 0.06) {
      const f = 1 - s.t / 0.06;
      const a = this.tinta("fx_brilho", "#ffb34d"), b = this.tinta("fx_brilho", "#fff2cc");
      if (a) { ctx.globalAlpha = 0.85 * f; ctx.drawImage(a, s.dx - 158, H - 127, 316, 253); }
      if (b) { ctx.globalAlpha = f; ctx.drawImage(b, s.dx - 58, H - 63, 116, 127); }
    }
    if (s.t < BALA_VOO) {
      const k = s.t / BALA_VOO;
      const vx = s.x - s.dx, vy = s.y - s.dy;
      const d = Math.hypot(vx, vy) || 1;
      const cx = s.dx + vx * k, cy = s.dy + vy * k;
      const comp = Math.min(150 * K, d * k);
      ctx.strokeStyle = "#ff9e38";
      ctx.globalAlpha = 0.95;
      ctx.lineWidth = 9 * K;
      ctx.beginPath();
      ctx.moveTo(cx - (vx / d) * comp, cy - (vy / d) * comp);
      ctx.lineTo(cx, cy);
      ctx.stroke();
      ctx.strokeStyle = "#fff7d9";
      ctx.lineWidth = 3.5 * K;
      ctx.beginPath();
      ctx.moveTo(cx - (vx / d) * comp * 0.75, cy - (vy / d) * comp * 0.75);
      ctx.lineTo(cx, cy);
      ctx.stroke();
      this.glow(ctx, cx, cy, 14 * K, "#ffd98c", 0.9);
      return;
    }
    const fade = 1 - limitar((s.t - BALA_VOO) / IMPACTO, 0, 1);
    this.glow(ctx, s.x, s.y, (30 * fade + 6) * K, "#ffb852", fade);
  }

  // Fora das fases (a escolha): anéis fechando no ponto.
  desenharAneis(ctx, s) {
    const voo = 0.07;
    const anel = this.tinta("fx_anel", "#ff3338");
    if (s.t < voo) {
      const k = s.t / voo;
      const r = misturar(90, 10, k * k) * K;
      const a = 0.35 + 0.65 * k;
      if (anel) {
        ctx.globalAlpha = a * 0.8;
        ctx.drawImage(anel, s.x - r, s.y - r, r * 2, r * 2);
        ctx.globalAlpha = a * 0.5;
        ctx.drawImage(anel, s.x - r * 0.6, s.y - r * 0.6, r * 1.2, r * 1.2);
      }
      this.glow(ctx, s.x, s.y, (10 + 18 * (1 - k)) * K, "#ffd9cc", 1);
      return;
    }
    const k2 = limitar((s.t - voo) / IMPACTO, 0, 1);
    const fade = 1 - k2;
    const r = (12 + 64 * k2) * K;
    if (anel) { ctx.globalAlpha = fade; ctx.drawImage(anel, s.x - r, s.y - r, r * 2, r * 2); }
    this.glow(ctx, s.x, s.y, (30 * fade + 6) * K, "#ffd9cc", fade);
  }

  /* ---------------------------------------------------------- mira e placar */
  // A mira (mira_desenho.gd): a cruz na cor da tela, o contorno escuro por
  // baixo, um pulo a cada tiro e o anel da recarga enchendo.
  desenharMira(ctx) {
    const m = this.mira;
    const tam = 58 * (1 + 0.22 * m.pulso);
    const cor = this.estado === "escolha" || !this.corMira ? "#ff2e38" : this.corMira;
    const sombra = this.tinta("ui_mira_sombra", "#000000");
    const cruz = this.tinta("ui_mira", cor);
    if (sombra) { ctx.globalAlpha = 0.55; ctx.drawImage(sombra, m.x - tam / 2, m.y - tam / 2, tam, tam); }
    ctx.globalAlpha = 1;
    if (cruz) ctx.drawImage(cruz, m.x - tam / 2, m.y - tam / 2, tam, tam);
    if (this.recarregando) {
      const r = 58 * 0.62;
      const p = limitar(1 - this.recargaFalta / this.tempoRecarga, 0, 1);
      ctx.lineCap = "butt";
      ctx.strokeStyle = "rgba(0,0,0,0.55)";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(m.x, m.y, r, 0, VOLTA);
      ctx.stroke();
      ctx.strokeStyle = "#59ebff";
      ctx.lineWidth = 3.4;
      ctx.beginPath();
      ctx.arc(m.x, m.y, r, -Math.PI / 2, -Math.PI / 2 + VOLTA * p);
      ctx.stroke();
    }
  }

  // O placar de baixo: ACERTOS | as 30 balas | o campo da fase. As balas
  // são os próprios cartuchos (hud_bala): os gastos escuros, na recarga
  // voltam um a um, com pouca bala piscam laranja e vazia, vermelho.
  desenharHud(ctx) {
    const api = this.api;
    const tema = this.cen.tema;
    const y = HUD_Y, h = 52;
    ctx.globalAlpha = 0.66;
    ctx.fillStyle = "#03050a";
    caminhoArredondado(ctx, 8, y, W - 16, h, 13);
    ctx.fill();
    ctx.globalAlpha = 0.8;
    ctx.strokeStyle = tema;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.globalAlpha = 0.3;
    ctx.fillStyle = tema;
    ctx.fillRect(126, y + 10, 1.5, h - 20);
    ctx.fillRect(W - 128, y + 10, 1.5, h - 20);
    ctx.globalAlpha = 1;
    const clara = clarear(tema, 0.35);
    api.texto(ctx, "ACERTOS", 67, y + 14, { tamanho: 10, cor: clara, peso: 700 });
    api.texto(ctx, this.acertos + "/" + this.disparos, 67, y + 35, { tamanho: 19, cor: BRANCO, peso: 800 });
    const e = this.cenario.extra();
    api.texto(ctx, e[0], W - 67, y + 14, { tamanho: 10, cor: clara, peso: 700 });
    api.texto(ctx, e[1], W - 67, y + 35, { tamanho: 19, cor: e[2], peso: 800 });
    // as balas: duas fileiras de 15
    const x0 = 140, larg = W - 280;
    const esp = larg / 15;
    const bh = 17, bw = (bh * 24) / 68;
    const baixa = this.balas <= Math.max(3, MUNICAO / 5);
    const piscar = 0.55 + 0.45 * Math.abs(Math.sin(this.relogio * 9));
    const cheia = this.tinta("hud_bala", BRANCO);
    const gasta = this.tinta("hud_bala", "#4d4a52");
    const laranja = this.tinta("hud_bala", "#ff9e59");
    const vermelha = this.tinta("hud_bala", "#ff3830");
    const prog = this.recarregando ? limitar(1 - this.recargaFalta / this.tempoRecarga, 0, 1) : 0;
    for (let i = 0; i < MUNICAO; i++) {
      const fila = (i / 15) | 0;
      const bx = x0 + (i % 15) * esp + (esp - bw) / 2;
      const by = y + 7 + fila * 20;
      let img, a = 1;
      if (this.recarregando) {
        const k = limitar(prog * MUNICAO - i, 0, 1);
        if (k > 0.5) img = cheia; else { img = gasta; a = 0.55; }
      } else if (i < this.balas) { img = baixa ? laranja : cheia; a = baixa ? piscar : 1; }
      else if (this.balas <= 0) { img = vermelha; a = 0.35 + 0.4 * piscar; }
      else { img = gasta; a = 0.55; }
      if (!img) continue;
      ctx.globalAlpha = a;
      ctx.drawImage(img, bx, by, bw, bh);
    }
    ctx.globalAlpha = 1;
  }

  /* ---------------------------------------------------------- telas */
  desenharEscolha(ctx) {
    const api = this.api;
    const cen = CENARIOS[this.realce];
    const fundo = api.img[cen.fundo];
    if (fundo) ctx.drawImage(fundo, 0, 0, W, H);
    else { ctx.fillStyle = "#050812"; ctx.fillRect(0, 0, W, H); }
    ctx.fillStyle = "rgba(2, 4, 12, 0.66)";
    ctx.fillRect(0, 0, W, H);
    api.texto(ctx, "ESCOLHA SEU CENÁRIO", W / 2, 58, { tamanho: 30, cor: BRANCO, contorno: "rgba(0,0,0,0.7)", peso: 900 });
    let sub;
    if (this.escolhido >= 0) sub = CENARIOS[this.escolhido].nome + "!";
    else if (this.roleta) sub = "SORTEANDO...";
    else sub = "A ROLETA ESCOLHE EM " + Math.max(1, Math.ceil(this.autoT));
    api.texto(ctx, sub, W / 2, 96, { tamanho: 16, cor: "#ffd34d", peso: 800 });
    for (let i = 0; i < 4; i++) this.desenharCartao(ctx, i);
    // ALEATÓRIO
    const b = this.botaoAleatorio;
    const ativo = !!this.roleta;
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = ativo ? "#3a0b10" : "#0b0f1c";
    caminhoArredondado(ctx, b.x, b.y, b.w, b.h, 26);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#ff2e38";
    ctx.lineWidth = ativo ? 3 : 2;
    ctx.stroke();
    api.texto(ctx, "ALEATÓRIO", b.x + b.w / 2, b.y + b.h / 2 + 1, { tamanho: 19, cor: BRANCO, peso: 900 });
    api.texto(ctx, "Toque num cenário · 60 s de partida", W / 2, 872, { tamanho: 14, cor: "#c9d3e6", peso: 600 });
    api.texto(ctx, "30 balas · toque nas balas para recarregar", W / 2, 896, { tamanho: 13, cor: "#93a0b8", peso: 600 });
  }

  desenharCartao(ctx, i) {
    const api = this.api;
    const c = CENARIOS[i];
    const r = this.cartoes[i];
    const ativo = i === this.realce;
    let esc = ativo ? 1.03 : 1;
    if (this.escolhido === i) esc = 1.03 + 0.04 * Math.sin(this.escolhaT * 30);
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(esc, esc);
    caminhoArredondado(ctx, -r.w / 2, -r.h / 2, r.w, r.h, 16);
    ctx.save();
    ctx.clip();
    const img = api.img[c.cartao];
    if (img) {
      // o cartão (436x210) recortado na faixa mais larga
      const sh = img.width * (r.h / r.w);
      ctx.drawImage(img, 0, (img.height - sh) / 2, img.width, sh, -r.w / 2, -r.h / 2, r.w, r.h);
    } else {
      ctx.fillStyle = "#101626";
      ctx.fillRect(-r.w / 2, -r.h / 2, r.w, r.h);
    }
    if (!this.gradCartao) {
      const g = ctx.createLinearGradient(0, -r.h / 2 + 30, 0, r.h / 2);
      g.addColorStop(0, "rgba(0,0,0,0)");
      g.addColorStop(1, "rgba(0,0,0,0.82)");
      this.gradCartao = g;
    }
    ctx.fillStyle = this.gradCartao;
    ctx.fillRect(-r.w / 2, -r.h / 2, r.w, r.h);
    if (!ativo && this.escolhido < 0) {
      ctx.fillStyle = "rgba(0,0,0,0.25)";
      ctx.fillRect(-r.w / 2, -r.h / 2, r.w, r.h);
    }
    ctx.restore();
    if (ativo) { ctx.shadowColor = c.cor; ctx.shadowBlur = 18; }
    ctx.strokeStyle = c.cor;
    ctx.lineWidth = ativo ? 3.5 : 1.5;
    ctx.globalAlpha = ativo ? 1 : 0.7;
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
    api.texto(ctx, c.nome, -r.w / 2 + 18, r.h / 2 - 42, { tamanho: 23, cor: BRANCO, alinhar: "left", contorno: "rgba(0,0,0,0.75)", peso: 900 });
    api.texto(ctx, c.nivel, -r.w / 2 + 18, r.h / 2 - 17, { tamanho: 13, cor: c.cor, alinhar: "left", peso: 800 });
    api.texto(ctx, "★".repeat(c.estrelas) + "☆".repeat(4 - c.estrelas), r.w / 2 - 18, r.h / 2 - 18,
      { tamanho: 18, cor: c.cor, alinhar: "right", contorno: "rgba(0,0,0,0.6)", peso: 800 });
    api.texto(ctx, String(i + 1), r.w / 2 - 22, -r.h / 2 + 22, { tamanho: 14, cor: "rgba(255,255,255,0.65)", peso: 800 });
    ctx.restore();
  }

  desenharMissao(ctx) {
    const api = this.api;
    const c = this.cen;
    const passou = TEMPO_MISSAO - this.missaoT;
    const entra = Math.min(1, passou / 0.25);
    const esc = misturar(0.85, 1, saidaVolta(entra));
    ctx.globalAlpha = 0.45 * entra;
    ctx.fillStyle = "#02040c";
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = entra;
    ctx.save();
    ctx.translate(W / 2, 470);
    ctx.scale(esc, esc);
    ctx.fillStyle = "rgba(3, 6, 14, 0.86)";
    caminhoArredondado(ctx, -230, -125, 460, 250, 22);
    ctx.fill();
    ctx.strokeStyle = c.cor;
    ctx.lineWidth = 2.5;
    ctx.stroke();
    api.texto(ctx, "MISSÃO", 0, -96, { tamanho: 14, cor: "#c9d3e6", peso: 800 });
    api.texto(ctx, c.nome, 0, -62, { tamanho: 30, cor: c.cor, contorno: "rgba(0,0,0,0.6)", peso: 900 });
    api.texto(ctx, c.missao[0], 0, -12, { tamanho: 21, cor: BRANCO, peso: 800 });
    api.texto(ctx, c.missao[1], 0, 20, { tamanho: 21, cor: BRANCO, peso: 800 });
    const k = limitar(passou / TEMPO_MISSAO, 0, 1);
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    caminhoArredondado(ctx, -170, 60, 340, 8, 4);
    ctx.fill();
    ctx.fillStyle = c.cor;
    caminhoArredondado(ctx, -170, 60, Math.max(8, 340 * k), 8, 4);
    ctx.fill();
    api.texto(ctx, "TOQUE PARA COMEÇAR", 0, 96, { tamanho: 14, cor: "#c9d3e6", peso: 700 });
    ctx.restore();
    ctx.globalAlpha = 1;
  }
}

export default {
  largura: W,
  altura: H,
  artes: ARTES,
  criar(api) {
    return new Partida(api);
  },
};
