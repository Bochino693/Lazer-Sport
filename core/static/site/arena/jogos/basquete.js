/* ======================================================================
   BASQUETE — SLAM ARENA (em pé) e SWISH ARENA (deitado)

   As duas máquinas de basquete da Lazer & Sport num motor só. A
   `api.variante` escolhe a quadra:

     "slam"  -> SLAM ARENA, o basquete de neon em pé (540 x 960): 3 fases
                com META, cestas seguidas multiplicam (x2, x3, x4 = MODO
                ENTERRADA), bola de ouro, bônus de sequência entre as
                fases, o piso de LED que acende em onda, raios caindo na
                cesta -- e, como na máquina, nenhum botão: a primeira
                cesta liga a arena e começa o jogo. Na FINAL o aro anda.
     "swish" -> SWISH ARENA, o basquete deitado (960 x 540) das máquinas
                modernas: placar de LED gigante, fases com META, 2 pontos
                por cesta e 3 nos últimos 10 s, 4 seguidas em menos de 3 s
                = EM CHAMAS (pontos x2 por 8 s), as lâmpadas da moldura
                acendendo em sequência e o letreiro de neon passando atrás
                da tabela.

   A MINIATURA: na máquina a bola é de verdade e a cesta é um sensor. Aqui
   a pessoa arrasta a bola e solta (o "flick"), e a bola voa num pequeno
   mundo 3D em metros -- gravidade, aro de ferro que devolve a bola,
   tabela que rebate, rede que segura a bola que entrou -- desenhado em
   perspectiva (longe = menor). As bolas voltam pela rampa como na
   máquina: dá para soltar uma atrás da outra.

   A ARTE é a dos jogos de verdade (basquete/*.webp: o fundo de neon do
   Slam, a arena do Swish, a máscara das luzes dela, coroa, medalhas e as
   texturas de efeito). O que os jogos desenham em código, este também
   desenha: a bola é a mesma "bola.shader" dos dois jogos, calculada pixel
   a pixel uma vez e guardada em quadros; o placar é LED de 7 segmentos.
   ====================================================================== */

const TAMANHOS = { slam: [540, 960], swish: [960, 540] };
const SLUGS = { slam: "slam-arena", swish: "swish-arena" };

const ARTES = {
  // Slam Arena (basquete-vertical/imagens)
  slamFundo: "basquete/slam-fundo.webp",
  slamAura: "basquete/slam-jogador-aura.webp",
  coroa: "basquete/coroa.webp",
  medalha1: "basquete/medalha-1.webp",
  medalha2: "basquete/medalha-2.webp",
  medalha3: "basquete/medalha-3.webp",
  brilho: "basquete/fx-brilho.webp",
  anel: "basquete/fx-anel.webp",
  estrela: "basquete/fx-estrela.webp",
  faisca: "basquete/fx-faisca.webp",
  fumaca: "basquete/fx-fumaca.webp",
  feixe: "basquete/fx-feixe.webp",
  ladrilho: "basquete/fx-ladrilho.webp",
  confete: "basquete/fx-confete.webp",
  // Swish Arena (basquete-horizontal-android/imagens)
  swishFundo: "basquete/swish-fundo.webp",
  swishNeon: "basquete/swish-neon.webp",
  swishBrilho: "basquete/swish-brilho.webp",
  swishRaios: "basquete/swish-raios.webp",
  swishRastro: "basquete/swish-rastro.webp",
  swishAnel: "basquete/swish-anel.webp",
  swishEstrela: "basquete/swish-estrela.webp",
  swishFaisca: "basquete/swish-faisca.webp",
};

/* Qual quadra a página está abrindo. O console lê largura e altura do
   módulo ANTES de criar a partida, e guarda o módulo por endereço -- os
   dois basquetes dividem este arquivo. Então o tamanho sai da página: o
   endereço #jogar-<slug> leva ao cartão do jogo, e o cartão diz a
   variante. */
function varianteDaPagina() {
  try {
    const pedido = window.location.hash.match(/^#jogar-([\w-]+)/);
    if (pedido) {
      const cartao = document.querySelector(`[data-jogo="${pedido[1]}"]`);
      const variante = cartao && cartao.dataset.jogoVariante;
      if (variante && TAMANHOS[variante]) return variante;
      if (pedido[1].includes("swish")) return "swish";
    }
  } catch (erro) { /* fora do navegador */ }
  return "slam";
}

function tamanhoDaPagina(i) {
  return (TAMANHOS[varianteDaPagina()] || TAMANHOS.slam)[i];
}

function slugDaPagina(variante) {
  try {
    const pedido = window.location.hash.match(/^#jogar-([\w-]+)/);
    if (pedido) return pedido[1];
  } catch (erro) { /* fora do navegador */ }
  return SLUGS[variante];
}

/* ----------------------------------------------------------------------
   O MUNDO DA BOLA (metros). A altura h é medida a partir do aro (h = 0
   é o plano do aro), z é a distância até a câmera, x é o lado.
   ---------------------------------------------------------------------- */
const ZR = 3.0;                  // distância do aro
const R_ARO = 0.23;              // raio do aro
const TUBO = 0.018;              // o ferro do aro
const RB = 0.115;                // raio da bola
const ZB = ZR + R_ARO + 0.1;     // a tabela, logo atrás do aro
const REDE = 0.26;               // altura da rede
const G = 14;                    // gravidade "de fliperama": o arco é rápido
const N_BOLAS = 5;               // bolas na máquina (rampa + mão + no ar)
const E_ARO = 0.5;               // quanto o ferro devolve
const E_TABELA = 0.52;

/* A câmera de cada quadra foi ajustada para o aro cair em cima da arte:
   no Slam, pendurado na caixa da fase (que vira a tabela); no Swish,
   no suporte da tabela de vidro desenhada na arena. */
const CENAS = {
  slam: {
    f: 756, cx: 270, yHor: 286, hc: 0.66,
    mao: [270, 868], raioMao: 72, raioFila: 46,
    fila: [[388, 922], [468, 936], [546, 946]],
    entrada: [640, 952],
    dIdeal: 300, apice: 1.0,
    tabela: { meia: 0.42, h0: -0.045, h1: 0.449 },
  },
  swish: {
    f: 913, cx: 480, yHor: 309, hc: 0.47,
    mao: [480, 548], raioMao: 78, raioFila: 56,
    fila: [[606, 566], [708, 572], [806, 576]],
    entrada: [1040, 580],
    dIdeal: 210, apice: 0.85,
    tabela: { meia: 0.575, h0: -0.13, h1: 0.736 },
  },
};

/* As regras são as das máquinas (os scripts GDScript); só os tempos e as
   metas encolheram para caber numa partida de site (~1 minuto e meio). */
const REGRAS = {
  slam: { nomes: ["FASE 1", "FASE 2", "FINAL"], tempos: [30, 25, 25], metas: [10, 16], janela: 4.0 },
  swish: {
    nomes: ["FASE 1", "FASE 2", "FINAL"], tempos: [30, 25, 25], metas: [14, 18],
    janela: 3.0, cesta: 2, sprint: 3, segSprint: 10, cestasFogo: 4, fogoDur: 8,
  },
};

// cores do Slam Arena (Arte.gd / jogo.gd)
const SL = {
  laranja: "#ff750a", laranjaClaro: "#ffb84d", ouro: "#ffcc1f", ciano: "#59f2ff",
  violeta: "#b880ff", verde: "#4dff80", vermelho: "#ff3829", rosa: "#ff4db8", azul: "#409eff",
};
const CORES_FASE = ["#ff750a", "#409eff", "#b873ff"];
// cores do Swish Arena (jogo.gd)
const SW = {
  laranja: "#ff7a1a", amarelo: "#ffd61f", rosa: "#ff2e8c", roxo: "#8c3dff",
  ciano: "#21e0ff", verde: "#38ff6b", vermelho: "#ff2929",
};

/* A cor da sequência (Grade.cor_do_combo do Slam). */
function corDoCombo(n) {
  if (n >= 13) return "#ff0f08";
  if (n >= 9) return "#d133ff";
  if (n >= 6) return "#1f8cff";
  if (n >= 3) return "#ff940a";
  return "#ffc247";
}

/* ----------------------------------------------------------------------
   Pequenas ferramentas
   ---------------------------------------------------------------------- */
const TAU = Math.PI * 2;
const limitar = (v, a, b) => (v < a ? a : v > b ? b : v);
const mix = (a, b, k) => a + (b - a) * k;
const fract = (x) => x - Math.floor(x);
const modPos = (a, n) => ((a % n) + n) % n;
function suave(a, b, x) {
  const t = limitar((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
}
// entra passando um pouco do ponto e volta (o "pop" dos textos)
function saiDeTras(t) {
  const u = limitar(t, 0, 1) - 1;
  return 1 + 2.70158 * u * u * u + 1.70158 * u * u;
}

const RGB = new Map();
function rgbDe(hex) {
  let c = RGB.get(hex);
  if (!c) {
    const n = parseInt(hex.slice(1), 16);
    c = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    RGB.set(hex, c);
  }
  return c;
}
function rgba(hex, a) {
  const c = rgbDe(hex);
  return `rgba(${c[0]},${c[1]},${c[2]},${a})`;
}
function misturaCor(a, b, k) {
  const x = rgbDe(a);
  const y = rgbDe(b);
  let s = "#";
  for (let i = 0; i < 3; i++) s += Math.round(mix(x[i], y[i], k)).toString(16).padStart(2, "0");
  return s;
}

function novaTela(w, h) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}

function caminhoArredondado(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

/* Texturas brancas da arte pintadas numa cor (guardadas: cada cor é feita
   uma vez só). "source-in" troca a cor e mantém a transparência. */
const TINTAS = new Map();
let idImagem = 0;
function tingir(img, cor) {
  if (!img) return null;
  if (!img.__lsBasquete) img.__lsBasquete = ++idImagem;
  const chave = img.__lsBasquete + cor;
  let t = TINTAS.get(chave);
  if (!t) {
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    t = novaTela(w, h);
    const g = t.getContext("2d");
    g.drawImage(img, 0, 0, w, h);
    g.globalCompositeOperation = "source-in";
    g.fillStyle = cor;
    g.fillRect(0, 0, w, h);
    TINTAS.set(chave, t);
  }
  return t;
}

/* ----------------------------------------------------------------------
   A BOLA — a "bola.shader" dos dois jogos (esfera com luz, gomos e as
   costuras que giram), calculada aqui pixel a pixel UMA vez, em 24
   quadros do giro, normal e de ouro. Por quadro, desenhar a bola é só
   recortar um quadro: nítida do tamanho do aro ao tamanho da mão.
   ---------------------------------------------------------------------- */
let FOLHA_BOLA = null;
const COSTURA = [0.10, 0.03, 0.01];

function folhaBola() {
  if (FOLHA_BOLA) return FOLHA_BOLA;
  const N = 24;
  const L = 112;
  const fazer = (ouro) => {
    const tela = novaTela(L * N, L);
    const g = tela.getContext("2d");
    const dados = g.createImageData(L * N, L);
    const d = dados.data;
    const ci = Math.cos(0.45);
    const si = Math.sin(0.45);
    const base = [mix(0.96, 1.0, ouro), mix(0.45, 0.78, ouro), mix(0.10, 0.18, ouro)];
    const borda = [1.0, mix(0.45, 0.9, ouro), mix(0.1, 0.4, ouro)];
    const w = 0.045;
    for (let k = 0; k < N; k++) {
      const giro = (k / N) * TAU;
      const cg = Math.cos(giro);
      const sg = Math.sin(giro);
      for (let py = 0; py < L; py++) {
        const y = ((py + 0.5) / L) * 2 - 1;
        for (let px = 0; px < L; px++) {
          const x = ((px + 0.5) / L) * 2 - 1;
          const r2 = x * x + y * y;
          if (r2 >= 1) continue;
          const r = Math.sqrt(r2);
          const nz = Math.sqrt(1 - r2);
          const qx = cg * x + sg * nz;
          const qz0 = -sg * x + cg * nz;
          const qy = ci * y - si * qz0;
          const qz = si * y + ci * qz0;
          let linha = 1 - limitar(Math.abs(qx) / w - 0.4, 0, 1);
          linha = Math.max(linha, 1 - limitar(Math.abs(qy) / w - 0.4, 0, 1));
          linha = Math.max(linha, 1 - limitar(Math.abs(Math.abs(qz) - 0.7) / w - 0.4, 0, 1));
          const luz = 0.32 + 0.68 * Math.max(0, -0.45 * x - 0.55 * y + 0.7 * nz);
          const brilho = Math.pow(Math.max(0, -0.35 * x - 0.45 * y + 0.82 * nz), 18) * 0.55;
          const aro = limitar((r - 0.86) * 7, 0, 1) * 0.35;
          const i = (py * L * N + k * L + px) * 4;
          for (let c = 0; c < 3; c++) {
            const v = mix(base[c], COSTURA[c], linha * 0.92) * luz + brilho + borda[c] * aro;
            d[i + c] = limitar(v * 255, 0, 255);
          }
          d[i + 3] = limitar((1 - r) * 30, 0, 1) * 255;
        }
      }
    }
    g.putImageData(dados, 0, 0);
    return tela;
  };
  FOLHA_BOLA = { normal: fazer(0), ouro: fazer(1), n: N, lado: L };
  return FOLHA_BOLA;
}

function desenharBola(ctx, folha, x, y, r, giro, ouro) {
  if (r < 0.5) return;
  const k = Math.floor(fract(giro / TAU) * folha.n) % folha.n;
  ctx.drawImage(ouro ? folha.ouro : folha.normal, k * folha.lado, 0, folha.lado, folha.lado, x - r, y - r, r * 2, r * 2);
}

/* ----------------------------------------------------------------------
   PLACAR DE LED (7 segmentos), como os displays dos dois jogos: o miolo
   quase branco (o LED quente), o brilho da cor em volta e os segmentos
   apagados aparecendo escuros. Cada dígito de cada cor e tamanho é
   desenhado uma vez numa telinha e guardado.
   ---------------------------------------------------------------------- */
// a..g, em frações da largura x altura do dígito
const SEGMENTOS = [
  [0.17, 0.055, 0.83, 0.055], [0.93, 0.115, 0.93, 0.47], [0.93, 0.53, 0.93, 0.885],
  [0.17, 0.945, 0.83, 0.945], [0.07, 0.53, 0.07, 0.885], [0.07, 0.115, 0.07, 0.47],
  [0.17, 0.5, 0.83, 0.5],
];
const DIGITOS = { 0: 63, 1: 6, 2: 91, 3: 79, 4: 102, 5: 109, 6: 125, 7: 7, 8: 127, 9: 111, "-": 64, " ": 0 };
const LEDS = new Map();

function barraLed(g, x1, y1, x2, y2, t) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const L = Math.hypot(dx, dy) || 1;
  const ux = dx / L;
  const uy = dy / L;
  const m = t / 2;
  g.moveTo(x1, y1);
  g.lineTo(x1 + ux * m - uy * m, y1 + uy * m + ux * m);
  g.lineTo(x2 - ux * m - uy * m, y2 - uy * m + ux * m);
  g.lineTo(x2, y2);
  g.lineTo(x2 - ux * m + uy * m, y2 - uy * m - ux * m);
  g.lineTo(x1 + ux * m + uy * m, y1 + uy * m - ux * m);
  g.closePath();
}

function spriteLed(ch, h, cor) {
  const chave = ch + "|" + h + "|" + cor;
  let s = LEDS.get(chave);
  if (s) return s;
  const E = 2;
  const W = h * 0.56;
  const T = h * 0.13;
  const incl = h * 0.08;
  const pad = h * 0.3;
  const tela = novaTela((W + incl + pad * 2) * E, (h + pad * 2) * E);
  const g = tela.getContext("2d");
  g.scale(E, E);
  const bits = DIGITOS[ch] !== undefined ? DIGITOS[ch] : 0;
  const caminho = (mascara, esp) => {
    g.beginPath();
    for (let i = 0; i < 7; i++) {
      if (!(mascara & (1 << i))) continue;
      const sg = SEGMENTOS[i];
      barraLed(g, pad + sg[0] * W + (1 - sg[1]) * incl, pad + sg[1] * h,
        pad + sg[2] * W + (1 - sg[3]) * incl, pad + sg[3] * h, esp);
    }
  };
  g.fillStyle = rgba(cor, 0.11);
  caminho(127 & ~bits, T);
  g.fill();
  if (bits) {
    g.shadowColor = cor;
    g.shadowBlur = h * 0.32 * E;
    g.fillStyle = cor;
    caminho(bits, T);
    g.fill();
    g.fill();
    g.shadowBlur = 0;
    g.fillStyle = misturaCor(cor, "#ffffff", 0.62);
    caminho(bits, T * 0.42);
    g.fill();
  }
  s = { tela, pad, E };
  LEDS.set(chave, s);
  return s;
}

/* Escreve `texto` (dígitos, espaço, "-") em LED, centrado em (cx, cy). */
function led(ctx, texto, cx, cy, h, cor, alinhar = "center") {
  h = Math.round(h);
  const passo = h * 0.78;
  const total = texto.length * passo - h * 0.22 + h * 0.08;
  let x = alinhar === "center" ? cx - total / 2 : alinhar === "right" ? cx - total : cx;
  const y = cy - h / 2;
  for (let i = 0; i < texto.length; i++) {
    const s = spriteLed(texto[i], h, cor);
    ctx.drawImage(s.tela, x - s.pad, y - s.pad, s.tela.width / s.E, s.tela.height / s.E);
    x += passo;
  }
}

function numeroLed(valor, digitos) {
  const s = String(Math.max(0, Math.floor(valor)));
  return s.length >= digitos ? s : " ".repeat(digitos - s.length) + s;
}

/* ----------------------------------------------------------------------
   FAÍSCAS: um conjunto fixo de partículas reaproveitadas (nada é criado a
   cada quadro). Aditivas (luz) ou normais (confete).
   ---------------------------------------------------------------------- */
class Faiscas {
  constructor(n) {
    this.lista = [];
    for (let i = 0; i < n; i++) this.lista.push({ vivo: false });
    this.i = 0;
  }

  novo(x, y, vx, vy, vida, tam, spr) {
    const L = this.lista;
    let p = null;
    for (let k = 0; k < L.length; k++) {
      const j = (this.i + k) % L.length;
      if (!L[j].vivo) {
        p = L[j];
        this.i = (j + 1) % L.length;
        break;
      }
    }
    if (!p) {
      p = L[this.i];
      this.i = (this.i + 1) % L.length;
    }
    p.vivo = true;
    p.x = x; p.y = y; p.vx = vx; p.vy = vy;
    p.vida = vida; p.total = vida;
    p.t0 = tam; p.t1 = tam;
    p.spr = spr; p.spr2 = null; p.spr3 = null;
    p.g = 0; p.arrasto = 0; p.rot = 0; p.vrot = 0;
    p.alinhar = false; p.aditivo = true; p.alfa = 1; p.razao = 1; p.cor = "#ffffff";
    p.entra = 0;
    return p;
  }

  limpar() {
    for (const p of this.lista) p.vivo = false;
  }

  atualizar(dt) {
    for (const p of this.lista) {
      if (!p.vivo) continue;
      p.vida -= dt;
      if (p.vida <= 0) {
        p.vivo = false;
        continue;
      }
      if (p.arrasto) {
        const k = Math.max(0, 1 - p.arrasto * dt);
        p.vx *= k;
        p.vy *= k;
      }
      p.vy += p.g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.rot += p.vrot * dt;
    }
  }

  desenhar(ctx, aditivo) {
    ctx.save();
    ctx.globalCompositeOperation = aditivo ? "lighter" : "source-over";
    for (const p of this.lista) {
      if (!p.vivo || p.aditivo !== aditivo) continue;
      const k = p.vida / p.total;           // 1 -> 0
      const idade = 1 - k;
      const tam = mix(p.t1, p.t0, k);
      let a = p.alfa * Math.min(1, k * 2.2);
      if (p.entra > 0) a *= Math.min(1, idade / p.entra);
      if (a <= 0.01 || tam <= 0.3) continue;
      ctx.globalAlpha = a;
      let spr = p.spr;
      if (p.spr3 && idade > 0.66) spr = p.spr3;
      else if (p.spr2 && idade > 0.33) spr = p.spr2;
      if (!spr) {
        ctx.fillStyle = p.cor;
        ctx.beginPath();
        ctx.arc(p.x, p.y, tam / 2, 0, TAU);
        ctx.fill();
        continue;
      }
      const w = tam * p.razao;
      const h = tam;
      if (p.alinhar || p.rot) {
        const ang = p.alinhar ? Math.atan2(p.vy, p.vx) + Math.PI / 2 : p.rot;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(ang);
        ctx.drawImage(spr, -w / 2, -h / 2, w, h);
        ctx.restore();
      } else {
        ctx.drawImage(spr, p.x - w / 2, p.y - h / 2, w, h);
      }
    }
    ctx.restore();
  }
}

/* ======================================================================
   A PARTIDA
   ====================================================================== */
class Partida {
  constructor(api) {
    this.api = api;
    this.v = api.variante === "swish" ? "swish" : "slam";
    this.ehSlam = this.v === "slam";
    this.LW = TAMANHOS[this.v][0];
    this.LH = TAMANHOS[this.v][1];
    this.cena = CENAS[this.v];
    this.regras = REGRAS[this.v];
    this.img = api.img || {};
    this.reduzido = !!api.reduzido;
    // a quadra pede retrato ou paisagem; se a tela do console vier na outra
    // forma, a quadra se encaixa no meio (sem esticar)
    this.esc = Math.min(api.W / this.LW, api.H / this.LH);
    this.ox = (api.W - this.LW * this.esc) / 2;
    this.oy = (api.H - this.LH * this.esc) / 2;
    this.encaixe = Math.abs(this.esc - 1) > 0.002 || Math.abs(this.ox) > 0.5 || Math.abs(this.oy) > 0.5;
    this.slug = slugDaPagina(this.v);
    this.folha = folhaBola();

    // o aro e a bola na tela (a câmera de cada quadra)
    const c = this.cena;
    this.z0 = (c.f * RB) / c.raioMao;
    this.aroRX = (c.f * R_ARO) / ZR;
    const yAtras = c.yHor + (c.f * c.hc) / (ZR + R_ARO);
    const yFrente = c.yHor + (c.f * c.hc) / (ZR - R_ARO);
    this.aroY = (yAtras + yFrente) / 2;
    this.aroRY = (yFrente - yAtras) / 2;
    this.redeH = (c.f * REDE) / ZR;
    this.P = { x: 0, y: 0, s: 1 };

    this.fx = new Faiscas(this.reduzido ? 260 : 560);
    this.bolas = [];
    for (let i = 0; i < N_BOLAS; i++) this.bolas.push({ estado: "fila", i });
    this.caindo = [];
    for (let i = 0; i < 12; i++) this.caindo.push({ viva: false });
    this.aneis = [];
    for (let i = 0; i < 10; i++) this.aneis.push({ vivo: false });
    this.raios = [];
    for (let i = 0; i < 6; i++) this.raios.push({ vivo: false, pts: new Float32Array(34), ramo: new Float32Array(18) });
    this.flutuantes = [];
    for (let i = 0; i < 6; i++) this.flutuantes.push({ vivo: false });
    this.ondasPiso = [];
    this.agendaLogica = [];
    this.agendaFx = [];
    // a rede: 16 fios em volta x 5 anéis (só números, nada criado por quadro)
    this.redeX = new Float32Array(16 * 5);
    this.redeY = new Float32Array(16 * 5);
    this.amostras = new Float64Array(3 * 24);

    if (this.ehSlam) this.prepararSlam();
    else this.prepararSwish();
    this.tv = 0;
    this.ultimoQuadro = 0;
  }

  /* ==================================================================
     PREPARAÇÃO (uma vez): tudo o que dá para desenhar antes fica pronto
     ================================================================== */
  prepararSlam() {
    const fundo = this.img.slamFundo;
    this.fundos = { normal: fundo || null };
    if (fundo) {
      // a arena azul elétrica (MODO ENTERRADA), vermelha (últimos 10 s) e
      // verde (PASSOU): a mesma arte com o matiz trocado ("hue" mantém o
      // brilho de cada linha de neon)
      const matiz = (cor) => {
        const t = novaTela(540, 960);
        const g = t.getContext("2d");
        g.drawImage(fundo, 0, 0, 540, 960);
        g.globalCompositeOperation = "hue";
        g.fillStyle = cor;
        g.fillRect(0, 0, 540, 960);
        return t;
      };
      this.fundos.azul = matiz("#2f86ff");
      this.fundos.vermelho = matiz("#ff2216");
      this.fundos.verde = matiz("#2bff63");
    }
    this.montarPiso();
    // os dois holofotes do canto da quadra (o cone do holofotes.gd com a
    // textura fx_feixe)
    const cone = novaTela(240, 575);
    const g = cone.getContext("2d");
    g.beginPath();
    g.moveTo(240 * 0.44, 0);
    g.lineTo(240 * 0.56, 0);
    g.lineTo(240, 575);
    g.lineTo(0, 575);
    g.closePath();
    g.clip();
    if (this.img.feixe) g.drawImage(this.img.feixe, 0, 0, 240, 575);
    this.coneHolofote = cone;
    // a tabela-caixa de neon (fixa nas fases 1 e 2; anda na final)
    this.tabelaPx = { meia: (this.cena.tabela.meia * this.cena.f) / ZB };
    this.tabelaPx.cima = this.cena.yHor + ((this.cena.hc - this.cena.tabela.h1) * this.cena.f) / ZB;
    this.tabelaPx.baixo = this.cena.yHor + ((this.cena.hc - this.cena.tabela.h0) * this.cena.f) / ZB;
  }

  /* O PISO DE LED (grade.gd + piso.shader): ladrilhos em perspectiva nas
     linhas da quadra da arte, da linha de fundo para a frente. Parados
     cintilam de leve; na cesta acendem e sobem em onda. */
  montarPiso() {
    const FUGA = [270, 44];
    const TOPO = 497;
    const FUNDO = 965;
    const PASSO = 31;
    const d0 = TOPO - FUGA[1];
    const linhas = [TOPO];
    let y = TOPO;
    while (y < FUNDO) {
      y += ((PASSO * (y - FUGA[1])) / d0) * 0.6;
      linhas.push(y);
    }
    const ladrilhos = [];
    let semente = 2024;
    const sorteio = () => {
      semente = (semente * 16807) % 2147483647;
      return semente / 2147483647;
    };
    for (let j = 0; j < linhas.length - 1; j++) {
      const ya = linhas[j];
      const yb = linhas[j + 1];
      const sa = (ya - FUGA[1]) / d0;
      const sb = (yb - FUGA[1]) / d0;
      const prof = limitar(((ya + yb) / 2 - TOPO) / (FUNDO - TOPO), 0, 1);
      const n = Math.ceil(270 / (PASSO * sa)) + 1;
      for (let c = -n; c <= n; c++) {
        const xa0 = FUGA[0] + (c - 0.5) * PASSO * sa;
        const xa1 = FUGA[0] + (c + 0.5) * PASSO * sa;
        const xb0 = FUGA[0] + (c - 0.5) * PASSO * sb;
        const xb1 = FUGA[0] + (c + 0.5) * PASSO * sb;
        if (Math.max(xa1, xb1) < -10 || Math.min(xa0, xb0) > 550) continue;
        ladrilhos.push({
          x: (xa0 + xa1 + xb0 + xb1) / 4,
          y: (ya + yb) / 2,
          w: ((xa1 - xa0 + xb1 - xb0) / 2) * 0.88,
          h: (yb - ya) * 0.88,
          prof,
          s: sorteio(),
        });
      }
    }
    this.ladrilhos = ladrilhos;
    // o piso parado já desenhado (uma camada laranja e uma azul)
    const camada = (cor) => {
      const t = novaTela(540, 480);
      const g = t.getContext("2d");
      const spr = tingir(this.img.ladrilho, cor);
      if (!spr) return t;
      for (const l of ladrilhos) {
        g.globalAlpha = 0.11 * (0.45 + 0.55 * l.prof) * (0.7 + 0.6 * l.s);
        const w = l.w * 0.64;
        const h = l.h * 0.64;
        g.drawImage(spr, l.x - w / 2, l.y - 490 - h / 2, w, h);
      }
      return t;
    };
    this.pisoBase = { laranja: camada(SL.laranja), azul: camada("#2a86ff") };
  }

  prepararSwish() {
    // a onda de luz que corre pelos tubos de neon (luzes_arena.shader):
    // uma faixa de listras já pintada na cor do neon, que só desliza, e a
    // máscara dos tubos (o canal R da máscara do jogo) que recorta
    const NW = 480;
    const NH = 270;
    const listras = (cor, forca) => {
      const t = novaTela(NW + 96, NH);
      const g = t.getContext("2d");
      const dados = g.createImageData(NW + 96, NH);
      const d = dados.data;
      const c = rgbDe(cor);
      for (let y = 0; y < NH; y++) {
        for (let x = 0; x < NW + 96; x++) {
          const onda = 0.5 + 0.5 * Math.sin(TAU * ((5 * x) / NW + (3 * y) / NH));
          const v = (0.15 + 0.85 * onda * onda * onda) * 0.6 * forca;
          const i = (y * (NW + 96) + x) * 4;
          d[i] = Math.min(255, c[0] * v);
          d[i + 1] = Math.min(255, c[1] * v);
          d[i + 2] = Math.min(255, c[2] * v);
          d[i + 3] = 255;
        }
      }
      g.putImageData(dados, 0, 0);
      return t;
    };
    this.neonListras = listras("#ffc738", 1.0);
    this.neonListrasFogo = listras("#ff5214", 1.35);
    this.neonTela = novaTela(NW, NH);
    this.neonCtx = this.neonTela.getContext("2d");
    // as 54 lâmpadas da moldura (posição e ordem tiradas da máscara do
    // jogo: canal G = lâmpada, B = a ordem na volta)
    this.lampadas = [];
    for (let i = 0; i < 12; i++) this.lampadas.push([22.9, 214.9 + 26 * i, i]);
    for (let i = 0; i < 30; i++) this.lampadas.push([59.9 + 29 * i, 517.9, 12 + i]);
    for (let i = 0; i < 12; i++) this.lampadas.push([936.9, 500.9 - 26 * i, 42 + i]);
    this.montarLetreiro();
    // o facho dos holofotes do teto: um cone macio
    const cone = novaTela(200, 520);
    const g = cone.getContext("2d");
    for (let k = 0; k < 6; k++) {
      const abre = 1 - k * 0.15;
      const gr = g.createLinearGradient(0, 0, 0, 520);
      gr.addColorStop(0, "rgba(255,255,255,0.22)");
      gr.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = gr;
      g.beginPath();
      g.moveTo(100 - 7 * abre, 0);
      g.lineTo(100 + 7 * abre, 0);
      g.lineTo(100 + 100 * abre, 520);
      g.lineTo(100 - 100 * abre, 520);
      g.closePath();
      g.fill();
    }
    this.coneFacho = cone;
  }

  /* O LETREIRO DA ARENA (letreiro_led.gd): SWISH ARENA, SHOW YOUR GAME e
     LAZER & SPORT GAMES em letras de neon correndo na faixa atrás da
     tabela. A tira é desenhada uma vez; por quadro ela só anda. */
  montarLetreiro() {
    const FRASES = [["SWISH ARENA", "#ffa129"], ["SHOW YOUR GAME", "#c778ff"], ["LAZER & SPORT GAMES", "#29dbff"]];
    const PONTO = "#ffe696";
    const E = 2;
    const ALT = 23;
    const fonte = "900 15px Poppins, Manrope, system-ui, sans-serif";
    const medir = novaTela(4, 4).getContext("2d");
    medir.font = fonte;
    let soma = 0;
    for (const [t] of FRASES) soma += medir.measureText(t).width + medir.measureText("•").width;
    const espaco = Math.max(16, (915 - soma) / (FRASES.length * 2));
    const L = soma + espaco * FRASES.length * 2;
    const tela = novaTela(L * E, ALT * E);
    const g = tela.getContext("2d");
    g.scale(E, E);
    g.font = fonte;
    g.textBaseline = "middle";
    let x = espaco / 2;
    for (const [t, cor] of FRASES) {
      for (const [parte, c] of [[t, cor], ["•", PONTO]]) {
        g.shadowColor = c;
        g.shadowBlur = 7 * E;
        g.fillStyle = misturaCor(c, "#ffffff", 0.25);
        g.fillText(parte, x, ALT / 2 + 1);
        g.shadowBlur = 0;
        g.fillText(parte, x, ALT / 2 + 1);
        x += medir.measureText(parte).width + espaco;
      }
    }
    this.letreiro = { tela, L, ALT };
  }

  /* ==================================================================
     VIDA DA PARTIDA
     ================================================================== */
  iniciar() {
    const R = this.regras;
    this.estado = this.ehSlam ? "aquece" : "jogando";
    this.tEstado = 0;
    this.fase = 0;
    this.pontos = 0;
    this.cestas = 0;
    this.maiorCombo = 0;
    this.combo = 0;
    this.pontosFase = [0, 0, 0];
    this.comboFase = [0, 0, 0];
    this.passou = [false, false, false];
    this.total = R.tempos[0];
    this.tempo = this.total;
    this.decorrido = 0;
    this.ultimaCesta = -100;
    this.alvo = this.ehSlam ? R.metas[0] : R.metas[0];
    this.mult = 1;
    this.enterrada = false;
    this.azul = 0;
    this.azulPulso = 0;
    this.alerta = false;
    this.apagado = this.ehSlam ? 0.5 : 0;
    this.apagadoAlvo = this.apagado;
    this.fogo = 0;
    this.sprint = false;
    this.metaBatida = false;
    this.recordeAntigo = this.lerRecorde();
    this.recordeVivo = false;
    this.festa = false;
    this.hoje = this.lerHoje();
    this.ouro = { em: [], ativo: false, resta: 0, some: 0, y: 0 };
    this.segundo = -1;
    this.esperando = 0;
    this.chips = { combo: 0, fogo: 0, sprint: 0 };
    this.energia = 0;
    this.energiaAlvo = 0;
    this.barras = 0.2;
    this.aroX = 0;
    this.aroAmp = 0;
    this.tAro = 0;
    this.rede = { estica: 0, vel: 0, bal: 0 };
    this.tremor = 0;
    this.zoom = 0;
    this.zoomT = 9;
    this.zoomForca = 0;
    this.clarao = 0;
    this.claraoCor = "#ffffff";
    this.tabelaBrilho = 0;
    this.tabelaCor = "#ffffff";
    this.borda = 0;
    this.auraT = 9;
    this.ondaFundo = 9;
    this.ondaFundoCor = "normal";
    this.ondaFundoX = 0;
    this.ondaFundoY = 0;
    this.faseOnda = 0;
    this.faseLampada = 0;
    this.andado = 0;
    this.proximoRaio = 0;
    this.proximaBolaFogo = 0;
    this.av = null;
    this.avPrio = 0;
    this.avAte = 0;
    this.comboTxt = null;
    this.faixa = null;
    this.mapa = null;
    this.contagem = null;
    this.liga = 0;
    this.fimTxt = null;
    this.flutuaLado = 1;
    this.agendaLogica.length = 0;
    this.agendaFx.length = 0;
    this.fx.limpar();
    for (const b of this.caindo) b.viva = false;
    for (const a of this.aneis) a.vivo = false;
    for (const r of this.raios) r.vivo = false;
    for (const f of this.flutuantes) f.vivo = false;
    this.ondasPiso.length = 0;
    // as bolas: todas na rampa, a primeira já vai para a mão
    this.fila = [];
    this.bolas.forEach((b, i) => {
      b.estado = "fila";
      const slot = this.cena.fila[Math.min(i, this.cena.fila.length - 1)];
      b.sx = i < this.cena.fila.length ? slot[0] : this.cena.entrada[0] + (i - this.cena.fila.length) * 80;
      b.sy = i < this.cena.fila.length ? slot[1] : this.cena.entrada[1];
      b.giro = Math.random() * TAU;
      b.ouroBola = false;
      this.fila.push(b);
    });
    this.mao = null;
    this.rearme = 0;
    this.puxarProxima(true);
    this.arrasto = null;
    this.teclas = { esq: false, dir: false, carga: false };
    this.mira = 0;
    this.carga = 0;
    this.usouTeclado = false;
    this.arremessos = 0;
    this.ultimoPlacar = { p: null, t: null, i: null };
    this.mandarPlacar();
    if (!this.ehSlam) {
      this.agendar(0.9, () => this.aviso(`META: ${R.metas[0]} PONTOS!`, SW.ciano, 1.3));
    }
  }

  destruir() {
    this.agendaLogica.length = 0;
    this.agendaFx.length = 0;
    this.fx.limpar();
  }

  /* --------------------------------------------------- recorde e ranking */
  lerRecorde() {
    try {
      return Number(window.localStorage.getItem("ls-jogo-recorde:" + this.slug)) || 0;
    } catch (erro) {
      return 0;
    }
  }

  diaDeHoje() {
    const d = new Date();
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }

  // os 3 melhores de hoje NESTE aparelho (o "MELHORES DE HOJE" da máquina)
  lerHoje() {
    try {
      const d = JSON.parse(window.localStorage.getItem("ls-basquete-hoje:" + this.v) || "null");
      if (d && d.dia === this.diaDeHoje() && Array.isArray(d.top)) return d.top.slice(0, 3);
    } catch (erro) { /* sem armazenamento */ }
    return [];
  }

  gravarHoje(pontos) {
    if (pontos <= 0) return;
    const top = this.lerHoje().concat([pontos]).sort((a, b) => b - a).slice(0, 3);
    this.hoje = top;
    try {
      window.localStorage.setItem("ls-basquete-hoje:" + this.v, JSON.stringify({ dia: this.diaDeHoje(), top }));
    } catch (erro) { /* aba anônima */ }
  }

  /* ------------------------------------------------------------ agenda */
  agendar(seg, fn) {
    this.agendaLogica.push({ t: seg, fn });
  }

  agendarFx(seg, fn) {
    this.agendaFx.push({ t: seg, fn });
  }

  passarAgenda(lista, dt) {
    for (let i = 0; i < lista.length; i++) {
      const a = lista[i];
      a.t -= dt;
      if (a.t <= 0) {
        lista.splice(i, 1);
        i--;
        a.fn();
      }
    }
  }

  som(nome) {
    this.api.som(nome);
  }

  mandarPlacar() {
    const u = this.ultimoPlacar;
    const dados = {};
    let mudou = false;
    if (u.p !== this.pontos) {
      dados.pontos = this.pontos;
      u.p = this.pontos;
      mudou = true;
    }
    const t = Math.ceil(this.tempo);
    if (u.t !== t) {
      dados.tempo = this.tempo;
      u.t = t;
      mudou = true;
    }
    const info = this.infoPlacar();
    if (u.i !== info) {
      dados.info = info;
      u.i = info;
      mudou = true;
    }
    if (mudou) this.api.placar(dados);
  }

  infoPlacar() {
    const nome = this.regras.nomes[this.fase];
    if (this.ehSlam) {
      if (this.estado === "aquece") return "ACERTE A CESTA!";
      if (this.enterrada) return "x4 MODO ENTERRADA";
      if (this.fase === 2) return `FINAL · x${this.mult} TURBO`;
      if (this.passou[this.fase]) return `${nome} · PASSOU!`;
      return `${nome} · META ${this.alvo}`;
    }
    if (this.fogo > 0) return "x2 EM CHAMAS";
    if (this.sprint) return "CESTA VALE 3";
    if (this.fase === 2) return "FINAL · VALE TUDO";
    return `${nome} · META ${this.regras.metas[this.fase]}`;
  }

  /* ==================================================================
     LÓGICA (só durante a partida)
     ================================================================== */
  atualizar(dt) {
    this.passarAgenda(this.agendaLogica, dt);
    this.tEstado += dt;
    switch (this.estado) {
      case "aquece":
        // ninguém acertou em 12 s: a arena liga assim mesmo
        if (this.tEstado > 12) this.ligarArena(false);
        break;
      case "mapa":
        if (this.tEstado >= 2.3) this.pularMapa();
        break;
      case "contagem":
        this.passoContagem();
        break;
      case "jogando":
        this.jogando(dt);
        break;
      default:
        break;
    }
    this.mandarPlacar();
  }

  jogando(dt) {
    const R = this.regras;
    this.decorrido += dt;
    this.tempo = Math.max(0, this.total - this.decorrido);
    const seg = Math.ceil(this.tempo);
    if (seg !== this.segundo) {
      this.segundo = seg;
      if (this.ehSlam) {
        if (seg <= 10 && seg > 0) {
          if (!this.alerta) {
            this.alerta = true;
            if (this.fase < 2 && !this.passou[this.fase]) this.aviso(`ÚLTIMOS 10 s! FALTAM ${this.alvo - this.pontos}`, SL.vermelho, 1.2, 2);
            else this.aviso("ÚLTIMOS 10 SEGUNDOS!", SL.vermelho, 1.2, 2);
          }
          this.som(seg <= 5 ? "batida" : "nota");
        }
      } else {
        if (seg <= 5 && seg > 0) this.som("nota");
        if (!this.sprint && this.tempo <= R.segSprint) {
          // ÚLTIMOS SEGUNDOS: a cesta vale 3
          this.sprint = true;
          this.chips.sprint = 0.001;
          this.aviso(`ÚLTIMOS ${R.segSprint} s!`, SW.amarelo, 1.4);
          this.flash(SW.amarelo, 0.35);
          this.som("apito");
        }
      }
    }
    // a sequência acaba se demorar
    if (this.combo > 0 && this.decorrido - this.ultimaCesta > R.janela) {
      this.combo = 0;
      if (this.ehSlam) {
        const base = this.multBase();
        if (this.mult > base) this.som("clique");
        this.mult = base;
        this.sairEnterrada();
        this.barras = 0.2;
      }
    }
    if (!this.ehSlam && this.fogo > 0) {
      this.fogo -= dt;
      if (this.fogo <= 0) this.sairFogo();
    }
    if (this.ehSlam) {
      // bola de ouro: uma vez por fase, por 6 s
      if (this.ouro.em.length && this.decorrido >= this.ouro.em[0] && this.tempo > 6) {
        this.ouro.em.shift();
        this.mostrarOuro();
      }
      if (this.ouro.ativo) {
        this.ouro.resta -= dt;
        if (this.ouro.resta <= 0) this.perderOuro();
      }
      // MODO ENTERRADA: raios caindo na cesta e bolas de fogo saindo dela
      if (this.enterrada) {
        this.proximoRaio -= dt;
        if (this.proximoRaio <= 0) {
          this.proximoRaio = mix(0.45, 1.0, Math.random());
          this.raioEnterrada();
        }
        this.proximaBolaFogo -= dt;
        if (this.proximaBolaFogo <= 0) {
          this.proximaBolaFogo = mix(0.45, 0.85, Math.random());
          this.soltarCaindo(1, "fogo");
        }
      }
    }
    this.esperando = this.decorrido - Math.max(this.ultimaCesta, 0);
    if (this.tempo <= 0) this.fimDaFase();
  }

  multBase() {
    return this.fase === 2 ? 2 : 1;
  }

  /* 3 seguidas = x2, 6 = x3, 10 = x4. Na FINAL (turbinado): já começa
     em x2, 3 = x3, 6 = x4 (jogo.gd: _mult_do_combo). */
  multDoCombo(c) {
    if (this.fase === 2) return c >= 6 ? 4 : c >= 3 ? 3 : 2;
    return c >= 10 ? 4 : c >= 6 ? 3 : c >= 3 ? 2 : 1;
  }

  /* ---------------------------------------------- Slam: a arena liga */
  ligarArena(comCesta) {
    if (this.estado !== "aquece") return;
    this.estado = "liga";
    this.tEstado = 0;
    this.liga = 0.001;
    this.apagadoAlvo = 0;
    this.som("strike");
    this.tremer(7);
    if (comCesta) this.comboTexto("VALENDO!", "#ffffff", SL.laranja);
    else this.comboTexto("VAMOS LÁ!", "#ffffff", SL.laranja);
    this.dispararPiso(this.aroTelaX(), this.aroY, 6, SL.laranja);
    this.agendar(0.75, () => this.iniciarFase(0));
  }

  /* ------------------------------------------------- fases (Slam e Swish) */
  prepararFase(i) {
    const R = this.regras;
    this.fase = i;
    this.total = R.tempos[i];
    this.tempo = this.total;
    this.decorrido = 0;
    this.segundo = -1;
    this.combo = 0;
    this.alerta = false;
    if (this.ehSlam) {
      this.alvo = i < 2 ? this.pontos + R.metas[i] : 0;
      this.mult = this.multBase();
    } else {
      this.metaBatida = i >= 2;
      this.sprint = false;
      this.chips.sprint = 0;
    }
  }

  iniciarFase(i) {
    this.prepararFase(i);
    this.estado = this.ehSlam ? "mapa" : "faixa";
    this.tEstado = 0;
    if (this.ehSlam) {
      this.mapa = { t: 0, sai: 0 };
      this.som("whoosh");
      this.agendar(0.36, () => {
        if (this.estado !== "mapa") return;
        this.som("batida");
        this.tremer(7);
        this.dispararPiso(270, 580, 6, CORES_FASE[i]);
        if (i === 2) {
          this.auraT = 0;
          this.azulPulso = 0.8;
        }
      });
    } else {
      const final = i === 2;
      const f = this.regras;
      this.mostrarFaixa(final ? "FINAL!" : `FASE ${i + 1}`,
        final ? "FAÇA O MÁXIMO DE PONTOS" : `META: ${f.metas[i]} PONTOS EM ${f.tempos[i]} s`,
        final ? SW.rosa : SW.roxo, 1.7);
      this.agendar(1.95, () => this.comecarContagem());
    }
  }

  pularMapa() {
    if (this.estado !== "mapa") return;
    this.mapa.sai = 0.001;
    this.comecarContagem();
  }

  comecarContagem() {
    this.estado = "contagem";
    this.tEstado = 0;
    this.contagem = { n: 4, t: 0 };
  }

  passoContagem() {
    // 3-2-1 (0,55 s cada) e VAI!
    const c = this.contagem;
    const n = this.tEstado < 1.65 ? 3 - Math.floor(this.tEstado / 0.55) : 0;
    if (n !== c.n) {
      c.n = n;
      c.t = 0;
      if (n > 0) {
        this.som("contagem");
        const cor = this.ehSlam ? CORES_FASE[this.fase] : SW.amarelo;
        if (this.ehSlam) this.dispararPiso(270, 700, 1, cor, true);
      } else {
        this.som("vai");
        this.comecarTempo();
      }
    }
  }

  comecarTempo() {
    this.estado = "jogando";
    this.tEstado = 0;
    this.decorrido = 0;
    this.tempo = this.total;
    this.ultimaCesta = -100;
    this.combo = 0;
    this.segundo = -1;
    this.contagem = { n: 0, t: 0, vai: 0.001 };
    this.som("apito");
    this.tremer(5);
    if (this.ehSlam) {
      this.mult = this.multBase();
      this.sairEnterrada(true);
      this.alerta = false;
      this.dispararPiso(this.aroTelaX(), this.aroY, 3, CORES_FASE[this.fase]);
      // a bola de ouro aparece uma vez, num momento sorteado da fase
      this.ouro.em = this.total >= 20 ? [this.total * mix(0.22, 0.64, Math.random())] : [];
      this.ouro.ativo = false;
    } else {
      this.flash(SW.verde, 0.4);
    }
  }

  fimDaFase() {
    this.estado = "fimFase";
    this.tEstado = 0;
    this.tempo = 0;
    this.som("apito");
    this.combo = 0;
    this.chips.combo = 0;
    if (this.ehSlam) {
      this.sairEnterrada();
      this.alerta = false;
      if (this.ouro.ativo) this.perderOuro();
      this.mult = this.multBase();
      this.barras = 0.2;
      this.aviso("TEMPO!", CORES_FASE[this.fase], 1.0, 9);
      this.agendar(1.4, () => this.depoisDoTempoSlam());
    } else {
      if (this.fogo > 0) {
        this.fogo = 0;
        this.sairFogo();
      }
      this.chips.sprint = 0;
      this.aviso("TEMPO!", SW.amarelo, 0.9);
      this.agendar(1.2, () => this.depoisDoTempoSwish());
    }
  }

  depoisDoTempoSlam() {
    const f = this.fase;
    if (f === 2) {
      this.encerrar(true);
      return;
    }
    if (!this.passou[f]) {
      // NÃO PASSOU: a arena apaga e é o fim
      this.som("erro");
      this.aviso(`NÃO PASSOU!  FALTARAM ${this.alvo - this.pontos}`, SL.vermelho, 2.0, 9);
      this.apagadoAlvo = 0.6;
      this.tremer(8);
      this.agendar(2.2, () => this.encerrar(false));
      return;
    }
    this.som("strike");
    this.aviso(`${this.regras.nomes[f]} CONCLUÍDA!`, SL.verde, 1.3, 9);
    this.dispararPiso(270, 930, 9, SL.verde);
    this.agendar(1.7, () => {
      // BÔNUS DE SEQUÊNCIA: o maior combo da fase vira pontos, contados
      const bonus = this.comboFase[f] >= 3 ? this.comboFase[f] : 0;
      if (!bonus) {
        this.iniciarFase(f + 1);
        return;
      }
      this.aviso(`BÔNUS DE SEQUÊNCIA +${bonus}`, SL.ouro, 1.6, 9);
      this.som("moeda");
      const passos = Math.min(bonus, 20);
      let resto = bonus;
      for (let k = 0; k < passos; k++) {
        const n = Math.ceil(resto / (passos - k));
        resto -= n;
        this.agendar(0.06 * k, () => {
          this.somar(n);
          this.popPontos = 1;
          this.som("nota");
        });
      }
      this.agendar(0.06 * passos + 0.1, () => {
        this.flutuar(`+${bonus}`, 431, 330, SL.ouro, 40);
        this.conferirRecorde();
      });
      this.agendar(0.06 * passos + 1.1, () => this.iniciarFase(f + 1));
    });
  }

  depoisDoTempoSwish() {
    const f = this.fase;
    const ultima = f === 2;
    if (this.metaBatida && !ultima) {
      this.mostrarFaixa("FASE CONCLUÍDA!", `${this.pontosFase[f]} PONTOS NESTA FASE`, SW.verde, 1.6);
      this.som("strike");
      this.agendar(1.9, () => this.iniciarFase(f + 1));
      return;
    }
    if (!this.metaBatida) {
      this.som("erro");
      this.mostrarFaixa("NÃO BATEU A META", `FALTARAM ${this.regras.metas[f] - this.pontosFase[f]} PONTOS`, SW.vermelho, 1.8);
      this.agendar(2.0, () => this.encerrar(false));
      return;
    }
    this.encerrar(true);
  }

  encerrar(campeao) {
    if (this.estado === "fim") return;
    this.estado = "fim";
    this.tEstado = 0;
    const fase = this.regras.nomes[this.fase];
    const plural = this.cestas === 1 ? "cesta" : "cestas";
    let titulo;
    let detalhe;
    if (this.ehSlam) {
      titulo = campeao ? "Campeão da arena!" : this.fase === 0 ? "Tente de novo!" : "Não passou!";
      detalhe = `${this.cestas} ${plural} · maior combo ${this.maiorCombo} · ` +
        (campeao ? "jogou a FINAL" : `parou na ${fase}`);
      if (campeao) {
        this.aviso("CAMPEÃO DA ARENA!", SL.ouro, 1.6, 10);
        this.confete(70);
        this.som("strike");
      }
    } else {
      titulo = campeao ? "Campeão!" : "Não bateu a meta";
      detalhe = `${this.cestas} ${plural} · maior combo x${this.maiorCombo} · ` +
        (campeao ? "venceu a FINAL" : `parou na ${fase}`);
      if (campeao) {
        this.mostrarFaixa("CAMPEÃO!", `${this.pontos} PONTOS`, SW.amarelo, 1.4);
        this.fogos(5, [SW.amarelo, SW.rosa, SW.ciano, SW.laranja, "#ffffff"]);
        this.som("strike");
      }
    }
    this.gravarHoje(this.pontos);
    this.agendar(campeao ? 1.5 : 0.4, () => {
      this.api.terminar({ pontos: this.pontos, titulo, detalhe });
    });
  }

  somar(n) {
    this.pontos += n;
    this.pontosFase[this.fase] += n;
  }

  /* ==================================================================
     A CESTA
     ================================================================== */
  aoPontuar(b) {
    const limpa = !b.tocouAro && !b.tocouTabela;
    // a rede estica e a cesta brilha mesmo fora do tempo (é a bola de verdade)
    this.rede.vel = 9;
    this.rede.bal = 1;
    const x = this.aroTelaX();
    const y = this.aroY;
    this.api.vibrar(18);
    if (this.estado === "aquece") {
      this.faiscasAro(x, y, SL.laranja, 26);
      this.anel(x, y, this.aroRX, this.aroRY, SL.laranja, 0.6, 1.6);
      this.ligarArena(true);
      return;
    }
    if (this.estado !== "jogando") {
      this.faiscasAro(x, y, this.ehSlam ? SL.laranja : SW.laranja, 12);
      this.som("ponto");
      return;
    }
    if (this.ehSlam) this.cestaSlam(limpa, x, y);
    else this.cestaSwish(limpa, x, y);
  }

  cestaSlam(limpa, x, y) {
    const R = this.regras;
    const intervalo = this.decorrido - this.ultimaCesta;
    this.ultimaCesta = this.decorrido;
    this.combo = intervalo <= R.janela ? this.combo + 1 : 1;
    this.maiorCombo = Math.max(this.maiorCombo, this.combo);
    this.comboFase[this.fase] = Math.max(this.comboFase[this.fase], this.combo);
    this.cestas++;
    const multAntes = this.mult;
    this.mult = this.multDoCombo(this.combo);
    let ganho = this.mult;
    let ouro = false;
    if (this.ouro.ativo) {
      ouro = true;
      ganho += 5;
      this.pegarOuro();
    }
    this.somar(ganho);
    this.popPontos = 1;
    const n = this.combo;
    const cor = corDoCombo(n);
    this.conferirRecorde();
    if (this.festa) {
      this.dispararPiso(x, y, 9, SL.ouro);
    } else {
      this.dispararPiso(x, y, n);
      if (n >= 9) this.dispararPiso(x, y, n, null, false, 0.14);
    }
    this.anel(x, y, this.aroRX, this.aroRY, n >= 3 ? cor : SL.laranjaClaro, 0.6, 1.8 + Math.min(n, 10) * 0.12);
    this.ondaNoFundo(x, y);
    this.raiosDaCesta(n);
    // a bola que entrou já sai como uma das que caem; com sequência saem mais
    const extras = (n >= 10 ? 4 : n >= 6 ? 3 : n >= 3 ? 2 : 1) - 1 + (this.enterrada ? 1 : 0);
    if (extras > 0) this.soltarCaindo(extras, ouro || this.festa ? "ouro" : this.enterrada ? "fogo" : "normal", cor);
    this.energiaAlvo = Math.max(this.energiaAlvo, 0.25 + Math.min(n, 10) * 0.075);
    if (n >= 6) this.flashesTorcida(2 + Math.floor(Math.min(n, 14) / 4));
    this.faiscasAro(x, y, n >= 3 ? cor : "#ffa64d", 30 + Math.min(n, 10) * 3);
    if (n >= 13 && (n - 13) % 6 === 0) this.alemDoLimite(x, y);
    this.som(n >= 2 ? "combo" : limpa ? "acerto" : "ponto");
    this.mostrarComboSlam(n, limpa);
    this.flutuar(`+${ganho}`, x + mix(-75, 75, Math.random()), 537, ouro ? SL.ouro : n >= 3 ? cor : SL.laranja, 46);
    this.tremer(2 + Math.min(n, 12) * 0.45);
    this.barras = limitar(0.2 + this.combo * 0.08, 0.2, 1);
    if (this.mult > multAntes) this.subiuMult();
    this.conferirPassou();
  }

  mostrarComboSlam(n, limpa) {
    let txt;
    if (n === 1) txt = limpa ? "SWISH!" : "BOA!";
    else if (n <= 3) txt = `${n} SEGUIDAS!`;
    else if (n === 4) txt = "ESQUENTOU 4!";
    else if (n === 5) txt = "PEGOU FOGO 5!";
    else if (n <= 8) txt = `EM CHAMAS ${n}!`;
    else if (n <= 12) txt = `IMPARÁVEL ${n}!`;
    else if (n === 13) txt = "ALÉM DO LIMITE!";
    else txt = `LENDÁRIO ${n}!`;
    let contorno = "#ff6105";
    let cor = "#ffffff";
    if (n === 13) contorno = "#ff1ac7";
    else if (n > 13) { contorno = "#ff0500"; cor = "#ffe0d6"; }
    else if (n >= 9) { contorno = "#cc33ff"; cor = "#f5e0ff"; }
    else if (n >= 6) { contorno = "#146bff"; cor = "#e0f0ff"; }
    else if (n >= 4) { contorno = "#ff6b05"; cor = "#ffe06b"; }
    this.comboTexto(txt, cor, contorno, limpa && n > 1);
  }

  comboTexto(txt, cor, contorno, swish = false) {
    this.comboTxt = { txt, cor, contorno, t: 0, rot: mix(-0.06, 0.06, Math.random()), swish };
  }

  subiuMult() {
    if (this.mult >= 4 && !this.enterrada) this.entrarEnterrada();
    else if (this.mult < 4) this.aviso(`PONTOS x${this.mult}!`, corDoCombo(this.mult === 2 ? 3 : 6), 0.9);
    this.popMult = 1;
  }

  conferirPassou() {
    const f = this.fase;
    if (f >= 2 || this.passou[f] || this.pontos < this.alvo) return;
    this.passou[f] = true;
    this.som("strike");
    this.aviso(`PASSOU!  RUMO À ${this.regras.nomes[f + 1]}`, SL.verde, 1.5, 3);
    this.dispararPiso(108, 270, 9, SL.verde, false, 0.05);
    this.anel(108, 270, 90, 50, SL.verde, 0.8, 1.6);
    this.ondaNoFundo(108, 270, "verde");
    this.tremer(6);
    this.api.vibrar(40);
  }

  conferirRecorde() {
    if (this.festa || this.pontos <= this.recordeAntigo || this.recordeAntigo < 3) return;
    this.festa = true;
    this.som("vitoria");
    this.aviso("RECORDE BATIDO!", SL.ouro, 1.6, 4);
    this.borda = 1;
    this.flashesTorcida(8);
    this.soltarCaindo(4, "ouro");
    this.faiscasAro(this.aroTelaX(), this.aroY, SL.ouro, 60);
    this.tremer(8);
  }

  alemDoLimite(x, y) {
    this.flashesTorcida(8);
    this.soltarCaindo(5, "ouro", "#ff4df2");
    this.anel(x, y, this.aroRX, this.aroRY, "#ff59f2", 0.8, 3);
    this.dispararPiso(x, y, 13, "#ff59f2", false, 0.1);
    this.tremer(11);
  }

  entrarEnterrada() {
    this.enterrada = true;
    this.proximoRaio = 0;
    this.proximaBolaFogo = 0.3;
    this.som("strike");
    this.aviso("MODO ENTERRADA!  PONTOS x4", SL.ciano, 1.4, 3);
    this.tremer(9);
    this.flashesTorcida(6);
    this.auraT = 0;
    this.api.vibrar(60);
  }

  sairEnterrada(imediato = false) {
    if (!this.enterrada && !imediato) return;
    this.enterrada = false;
    if (imediato) this.azul = 0;
  }

  /* ---------------------------------------------- Slam: bola de ouro */
  mostrarOuro() {
    this.ouro.ativo = true;
    this.ouro.resta = 6;
    this.ouro.some = 0;
    this.ouro.entra = 0;
    this.som("moeda");
    this.aviso("BOLA DE OURO!  VALE +5", SL.ouro, 1.0, 2);
  }

  pegarOuro() {
    this.ouro.ativo = false;
    this.ouro.some = 0.001;
    this.som("moeda");
    const x = 84;
    const y = 640;
    this.faiscasAro(x, y, SL.ouro, 40);
    this.anel(x, y, 46, 46, SL.ouro, 0.6, 1.8);
    this.flutuar("+5", x, y - 40, SL.ouro, 40);
  }

  perderOuro() {
    this.ouro.ativo = false;
    this.ouro.some = 0.001;
  }

  /* ---------------------------------------------- Swish: a cesta */
  cestaSwish(limpa, x, y) {
    const R = this.regras;
    this.cestas++;
    if (this.decorrido - this.ultimaCesta <= R.janela) this.combo++;
    else this.combo = 1;
    this.ultimaCesta = this.decorrido;
    this.maiorCombo = Math.max(this.maiorCombo, this.combo);
    let entrouFogo = false;
    if (this.combo >= R.cestasFogo) {
      if (this.fogo <= 0) entrouFogo = true;
      this.fogo = R.fogoDur;
    }
    const sprint = this.tempo <= R.segSprint;
    let valor = sprint ? R.sprint : R.cesta;
    if (this.fogo > 0) valor *= 2;
    this.somar(valor);
    this.popPontos = 1;
    this.popCestas = 1;
    const cor = this.fogo > 0 ? SW.vermelho : sprint ? SW.amarelo : SW.laranja;
    // o SWISH no aro: a tabela acende, ondas, raios, faíscas e o "zoom"
    const forte = this.fogo > 0 || this.combo >= 3;
    this.tabelaBrilho = 1;
    this.tabelaCor = misturaCor(cor, "#ffffff", 0.35);
    this.tremor = Math.max(this.tremor, this.fogo > 0 ? 4 : 2);
    if (forte) this.flash(cor, 0.3);
    this.zoomT = 0;
    this.zoomForca = forte ? 0.045 : 0.03;
    this.anel(x, y, this.aroRX, this.aroRY, cor, 0.6, 1.6);
    this.raiosSwish = { t: 0, giro: mix(-0.5, 0.5, Math.random()), cor: misturaCor(cor, "#ffffff", 0.45) };
    this.faiscasAro(x, y, cor, 34);
    this.estrelasAro(x, y, cor);
    if (limpa) this.flutuar("SWISH!", x, y - 120, cor, 34, 30, 0, true);
    this.flutuaLado = -this.flutuaLado;
    const lado = this.flutuaLado * mix(30, 75, Math.random()) * 0.75;
    this.flutuar(`+${valor}`, x + lado, y - 30, misturaCor(cor, "#ffffff", 0.3), 46, 50, 0, true);
    this.conferirRecordeSwish();
    if (this.combo >= 2) {
      this.som("combo");
      this.chips.combo = this.chips.combo > 0 ? Math.max(this.chips.combo, 0.25) : 0.001;
      this.popChipCombo = 1;
      const frases = { 3: "EM SEQUÊNCIA!", 5: "IMPARÁVEL!", 8: "MÃO QUENTE!", 10: "LENDÁRIO!" };
      if ([3, 5, 8, 10, 15, 20].includes(this.combo)) this.aviso(frases[this.combo] || `COMBO x${this.combo}!`, SW.ciano, 1.1);
    } else {
      this.som(limpa ? "acerto" : "ponto");
    }
    if (entrouFogo) this.entrarFogo();
    if (!this.metaBatida && this.pontosFase[this.fase] >= R.metas[this.fase]) {
      this.metaBatida = true;
      this.som("strike");
      this.aviso("META BATIDA!", SW.verde, 1.6);
      this.flash(SW.verde, 0.45);
      this.fogos(3, [SW.verde, SW.ciano, "#ffffff"]);
      this.api.vibrar(40);
    }
  }

  conferirRecordeSwish() {
    if (this.recordeVivo || this.recordeAntigo <= 0 || this.pontos <= this.recordeAntigo) return;
    this.recordeVivo = true;
    this.som("vitoria");
    this.aviso("NOVO RECORDE!", SW.amarelo, 1.6, 1, true);
    this.fogos(5, [SW.amarelo, SW.rosa, SW.ciano, SW.laranja, "#ffffff"]);
  }

  entrarFogo() {
    this.som("strike");
    this.chips.fogo = 0.001;
    this.aviso("EM CHAMAS!", "#ff8c1a", 1.5, 1, true);
    this.fogos(2, [SW.laranja, SW.vermelho]);
    this.api.vibrar(60);
  }

  sairFogo() {
    this.fogo = 0;
    this.chips.fogo = -0.3;
  }

  /* ==================================================================
     A BOLA: mão, arremesso, física
     ================================================================== */
  puxarProxima(imediato = false) {
    if (this.mao || !this.fila.length) return;
    const b = this.fila.shift();
    b.estado = "mao";
    b.chega = imediato ? 1 : 0;
    b.deX = b.sx;
    b.deY = b.sy;
    b.dragX = 0;
    b.dragY = 0;
    this.mao = b;
  }

  podeArremessar() {
    return this.estado === "aquece" || this.estado === "jogando" || this.estado === "liga";
  }

  paraLogico(x, y) {
    return [(x - this.ox) / this.esc, (y - this.oy) / this.esc];
  }

  apertar(xo, yo, id) {
    const [x, y] = this.paraLogico(xo, yo);
    if (this.estado === "mapa" && this.tEstado > 0.5) {
      this.pularMapa();
      return;
    }
    if (this.arrasto || !this.mao || this.mao.chega < 0.6 || !this.podeArremessar()) return;
    this.arrasto = { id, x0: x, y0: y, x, y, n: 0 };
    this.anotarAmostra(x, y);
  }

  anotarAmostra(x, y) {
    const a = this.arrasto;
    const k = (a.n % 24) * 3;
    this.amostras[k] = performance.now();
    this.amostras[k + 1] = x;
    this.amostras[k + 2] = y;
    a.n++;
  }

  mover(xo, yo, id) {
    const a = this.arrasto;
    if (!a || a.id !== id) return;
    const [x, y] = this.paraLogico(xo, yo);
    a.x = x;
    a.y = y;
    this.anotarAmostra(x, y);
  }

  soltar(xo, yo, id) {
    const a = this.arrasto;
    if (!a || a.id !== id) return;
    const [x, y] = this.paraLogico(xo, yo);
    a.x = x;
    a.y = y;
    this.anotarAmostra(x, y);
    this.arrasto = null;
    const b = this.mao;
    if (!b || !this.podeArremessar()) return;
    // força: o quanto a bola subiu arrastada OU a velocidade do flick
    // (um peteleco rápido e curto também arremessa)
    const D = a.y0 - y;
    // a velocidade do fim do gesto: da amostra de ~90 ms atrás até a soltura
    const agora = performance.now();
    let vy = 0;
    let vx = 0;
    const n = Math.min(a.n, 24);
    for (let i = 1; i < n; i++) {
      const k = ((a.n - 1 - i) % 24) * 3;
      const dtA = (agora - this.amostras[k]) / 1000;
      if (dtA >= 0.09 || i === n - 1) {
        if (dtA > 0.012) {
          vy = (this.amostras[k + 2] - y) / dtA;
          vx = (x - this.amostras[k + 1]) / dtA;
        }
        break;
      }
    }
    const c = this.cena;
    const efetivo = Math.max(D, Math.min(vy * 0.16, c.dIdeal * 1.12));
    if (efetivo < 26 || D < 6) return;    // só encostou: a bola volta para a mão
    const potencia = efetivo / c.dIdeal;
    // mira: a inclinação do arrasto (para cima = reto na cesta); num
    // peteleco rápido conta também a direção do fim do gesto
    let ang = Math.atan2(x - a.x0, Math.max(1, D));
    if (vy > 900) ang = mix(ang, Math.atan2(vx, vy), 0.5);
    this.arremessar(b, potencia, ang);
  }

  tecla(codigo, apertada) {
    if (codigo === "ArrowLeft" || codigo === "KeyA") this.teclas.esq = apertada;
    else if (codigo === "ArrowRight" || codigo === "KeyD") this.teclas.dir = apertada;
    else if (codigo === "Space" || codigo === "ArrowUp" || codigo === "KeyW" || codigo === "Enter") {
      if (apertada) {
        if (this.estado === "mapa" && this.tEstado > 0.5) {
          this.pularMapa();
          return;
        }
        if (!this.teclas.carga && this.mao && this.podeArremessar()) {
          this.teclas.carga = true;
          this.carga = 0;
          this.usouTeclado = true;
        }
      } else if (this.teclas.carga) {
        this.teclas.carga = false;
        if (this.mao && this.podeArremessar() && this.mao.chega >= 0.6) {
          this.arremessar(this.mao, this.potenciaTeclado(), this.mira);
        }
      }
    }
    if (apertada && (codigo === "ArrowLeft" || codigo === "ArrowRight" || codigo === "KeyA" || codigo === "KeyD")) {
      this.usouTeclado = true;
    }
  }

  // segurar o espaço: a força sobe e desce (0 -> 1,6 -> 0) como um medidor
  potenciaTeclado() {
    const k = fract(this.carga / 2.4);
    return (k < 0.5 ? k * 2 : 2 - k * 2) * 1.6;
  }

  /* O arremesso: o ponto onde a bola cruzaria a altura do aro na descida.
     Força certa = no aro; fraca = curta (aro da frente); forte = longa
     (tabela, aro de trás). Uma faixa pequena em volta do certo não erra:
     é um jogo de fliperama, não de simulação. */
  arremessar(b, potencia, ang) {
    const c = this.cena;
    // onde a bola está na tela -> no mundo (na profundidade da mão)
    const z0 = this.z0;
    b.x = ((b.px - c.cx) * z0) / c.f;
    b.h = c.hc - ((b.py - c.yHor) * z0) / c.f;
    b.z = z0;
    let e = potencia - 1;
    e = Math.sign(e) * Math.max(0, Math.abs(e) - 0.1);
    const alvoZ = ZR + limitar(e, -0.9, 1.3) * 0.85;
    let a = Math.sign(ang) * Math.max(0, Math.abs(ang) - 0.03);
    a = limitar(a, -1.1, 1.1);
    const apice = Math.max(b.h, 0) + c.apice * (0.9 + 0.12 * limitar(potencia, 0, 1.6));
    const vh = Math.sqrt(2 * G * Math.max(0.05, apice - b.h));
    const T = vh / G + Math.sqrt((2 * apice) / G);
    // na final do Slam o aro anda: a mira ajuda a "puxar" um pouco à frente
    const aroLa = this.aroXEm(this.tAro + T * 0.6);
    const alvoX = aroLa + Math.tan(a) * 1.05;
    b.vx = (alvoX - b.x) / T;
    b.vz = (alvoZ - b.z) / T;
    b.vh = vh;
    b.estado = "voo";
    b.tVoo = 0;
    b.tocouAro = false;
    b.tocouTabela = false;
    b.pontuou = false;
    b.naRede = false;
    b.hAnt = b.h;
    b.alfa = 1;
    b.somAro = -1;
    b.vgiro = -(6 + Math.random() * 4);
    b.ouroBola = !this.ehSlam && this.sprint && this.estado === "jogando";
    b.fogoBola = !this.ehSlam && this.fogo > 0 && this.estado === "jogando";
    b.sxAnt = b.px;
    b.syAnt = b.py;
    this.projetarBola(b);
    this.mao = null;
    this.rearme = 0.16;
    this.arremessos++;
    this.som("whoosh");
  }

  aroXEm(t) {
    return this.aroAmp * Math.sin((t * TAU) / 4.2);
  }

  aroTelaX() {
    return this.cena.cx + (this.cena.f * this.aroX) / ZR;
  }

  projetar(x, h, z) {
    const c = this.cena;
    const s = c.f / z;
    this.P.x = c.cx + x * s;
    this.P.y = c.yHor + (c.hc - h) * s;
    this.P.s = s;
    return this.P;
  }

  projetarBola(b) {
    const p = this.projetar(b.x, b.h, b.z);
    b.sx = p.x;
    b.sy = p.y;
    b.sr = RB * p.s;
  }

  fisica(b, dt) {
    const passos = 3;
    const h = dt / passos;
    const t = this.cena.tabela;
    for (let i = 0; i < passos; i++) {
      b.vh -= G * h;
      if (b.naRede) {
        // a rede segura: puxa a bola para o meio e freia a queda
        if (b.h > -REDE - RB * 0.5) {
          b.vx += ((this.aroX - b.x) * 30 - b.vx * 7) * h;
          b.vz += ((ZR - b.z) * 30 - b.vz * 7) * h;
          b.vh -= b.vh * 3.2 * h;
        }
      }
      const zAnt = b.z;
      b.x += b.vx * h;
      b.h += b.vh * h;
      b.z += b.vz * h;
      if (!b.naRede) {
        // a tabela (só para quem chega pela frente: a bola que passou por
        // cima dela segue e cai atrás)
        if (b.vz > 0 && b.z + RB > ZB && zAnt + RB <= ZB + 1e-4 && Math.abs(b.x - this.aroX) < t.meia + RB * 0.5 &&
          b.h > t.h0 - RB * 0.5 && b.h < t.h1 + RB * 0.5) {
          b.z = ZB - RB;
          if (b.vz > 0.45) this.batidaTabela(b);
          b.vz = -b.vz * E_TABELA;
          b.vx *= 0.85;
          b.vh *= 0.92;
          b.tocouTabela = true;
        }
        this.colidirAro(b);
        // passou por dentro do aro, descendo: CESTA
        if (!b.pontuou && b.hAnt >= 0 && b.h < 0 && b.vh < 0) {
          const d = Math.hypot(b.x - this.aroX, b.z - ZR);
          if (d < R_ARO - RB * 0.3) {
            b.pontuou = true;
            b.naRede = true;
            this.aoPontuar(b);
          }
        }
      }
      b.hAnt = b.h;
    }
    b.tVoo += dt;
    b.giro += b.vgiro * dt;
  }

  colidirAro(b) {
    const dx = b.x - this.aroX;
    const dz = b.z - ZR;
    const d = Math.hypot(dx, dz) || 1e-6;
    const qx = this.aroX + (dx / d) * R_ARO;
    const qz = ZR + (dz / d) * R_ARO;
    let nx = b.x - qx;
    let nh = b.h;
    let nz = b.z - qz;
    const dist = Math.hypot(nx, nh, nz);
    const min = RB + TUBO;
    if (dist >= min || dist < 1e-6) return;
    nx /= dist;
    nh /= dist;
    nz /= dist;
    b.x = qx + nx * min;
    b.h = nh * min;
    b.z = qz + nz * min;
    const vn = b.vx * nx + b.vh * nh + b.vz * nz;
    if (vn < 0) {
      // devolve a parte normal e o ferro "segura" um pouco da tangencial
      const tx = b.vx - vn * nx;
      const th = b.vh - vn * nh;
      const tz = b.vz - vn * nz;
      b.vx = tx * 0.9 - vn * E_ARO * nx;
      b.vh = th * 0.9 - vn * E_ARO * nh;
      b.vz = tz * 0.9 - vn * E_ARO * nz;
      b.tocouAro = true;
      if (-vn > 0.5 && this.tv - b.somAro > 0.12) {
        b.somAro = this.tv;
        this.som("quica");
        const p = this.projetar(qx, 0, qz);
        this.faiscasAro(p.x, p.y, this.ehSlam ? "#ffa64d" : "#ffb070", 6, 0.5);
        b.vgiro = -b.vgiro * 0.7;
      }
    }
  }

  batidaTabela(b) {
    this.som("batida");
    if (!this.ehSlam) {
      this.tabelaBrilho = Math.max(this.tabelaBrilho, 0.35);
      this.tabelaCor = "#bfe6ff";
    } else {
      this.tabelaBrilho = Math.max(this.tabelaBrilho, 0.6);
    }
  }

  // a bola saiu do jogo: volta pela rampa depois de um tempinho
  recolher(b) {
    b.estado = "volta";
    b.espera = mix(0.5, 0.75, Math.random());
  }

  /* ==================================================================
     ANIMAÇÃO (todo quadro, também fora da partida: a física e os
     efeitos terminam o que começaram mesmo depois do apito)
     ================================================================== */
  animar(dt) {
    this.tv += dt;
    this.passarAgenda(this.agendaFx, dt);
    // o aro da final anda
    const ampAlvo = this.ehSlam && this.fase === 2 && this.estado !== "aquece" ? 0.26 : 0;
    this.aroAmp += (ampAlvo - this.aroAmp) * Math.min(1, dt * 2.5);
    if (this.aroAmp > 0.001) this.tAro += dt;
    else this.tAro = 0;
    this.aroX = this.aroXEm(this.tAro);
    // a mão
    if (!this.mao) {
      this.rearme -= dt;
      if (this.rearme <= 0) this.puxarProxima();
    } else if (this.mao.chega < 1) {
      this.mao.chega = Math.min(1, this.mao.chega + dt / 0.2);
      this.mao.giro += dt * 9;
    }
    // teclado: mira e força
    if (this.teclas.esq) this.mira = Math.max(-0.4, this.mira - dt * 0.55);
    if (this.teclas.dir) this.mira = Math.min(0.4, this.mira + dt * 0.55);
    if (this.teclas.carga) this.carga += dt;
    // a rampa: cada bola rola até o lugar dela
    const slots = this.cena.fila;
    for (let i = 0; i < this.fila.length; i++) {
      const b = this.fila[i];
      const alvo = i < slots.length ? slots[i] : [this.cena.entrada[0] + (i - slots.length) * 80, this.cena.entrada[1]];
      const k = Math.min(1, dt * 9);
      const ax = b.sx;
      b.sx += (alvo[0] - b.sx) * k;
      b.sy += (alvo[1] - b.sy) * k;
      b.giro += (b.sx - ax) / (this.cena.raioFila * 0.9);
    }
    // as bolas no ar
    for (const b of this.bolas) {
      if (b.estado === "voo") {
        b.sxAnt = b.sx;
        b.syAnt = b.sy;
        this.fisica(b, dt);
        this.projetarBola(b);
        this.saiuDoJogo(b, dt);
        if (b.fogoBola && b.estado === "voo") this.fogoNaBola(b, dt);
      } else if (b.estado === "volta") {
        b.espera -= dt;
        if (b.espera <= 0) {
          b.estado = "fila";
          b.sx = this.cena.entrada[0];
          b.sy = this.cena.entrada[1];
          this.fila.push(b);
        }
      }
    }
    this.animarCaindo(dt);
    // a rede é uma mola (rede_mola.shader)
    const r = this.rede;
    r.vel += (-r.estica * 60 - r.vel * 7) * dt;
    r.estica += r.vel * dt;
    r.bal = Math.max(0, r.bal - dt * 1.6);
    this.fx.atualizar(dt);
    for (const a of this.aneis) {
      if (!a.vivo) continue;
      a.t += dt;
      if (a.t >= a.dur) a.vivo = false;
    }
    for (const rr of this.raios) {
      if (!rr.vivo) continue;
      rr.t += dt;
      rr.troca -= dt;
      if (rr.t >= rr.dur) rr.vivo = false;
      else if (rr.troca <= 0) this.gerarRaio(rr);
    }
    for (const f of this.flutuantes) {
      if (!f.vivo) continue;
      f.t += dt;
      if (f.t > 1.0) f.vivo = false;
    }
    for (let i = this.ondasPiso.length - 1; i >= 0; i--) {
      const o = this.ondasPiso[i];
      o.t += dt;
      if (o.t >= o.dur) this.ondasPiso.splice(i, 1);
    }
    if (this.av) {
      this.av.t += dt;
      if (this.av.t > this.av.dur + 0.55) this.av = null;
    }
    if (this.comboTxt) {
      this.comboTxt.t += dt;
      if (this.comboTxt.t > 0.8) this.comboTxt = null;
    }
    if (this.faixa) {
      this.faixa.t += dt;
      if (this.faixa.t > this.faixa.dur + 0.3) this.faixa = null;
    }
    if (this.mapa) {
      this.mapa.t += dt;
      if (this.mapa.sai > 0) {
        this.mapa.sai += dt;
        if (this.mapa.sai > 0.3) this.mapa = null;
      }
    }
    if (this.contagem) {
      this.contagem.t += dt;
      if (this.contagem.vai > 0) {
        this.contagem.vai += dt;
        if (this.contagem.vai > 0.75) this.contagem = null;
      }
    }
    if (this.raiosSwish) {
      this.raiosSwish.t += dt;
      if (this.raiosSwish.t > 0.5) this.raiosSwish = null;
    }
    this.tremor = Math.max(0, this.tremor - dt * 30);
    this.clarao = Math.max(0, this.clarao - dt * 2.2);
    this.tabelaBrilho = Math.max(0, this.tabelaBrilho - dt * 2.2);
    this.borda = Math.max(0, this.borda - dt * 0.6);
    this.zoomT += dt;
    this.auraT += dt;
    this.ondaFundo += dt;
    this.popPontos = Math.max(0, (this.popPontos || 0) - dt * 4);
    this.popCestas = Math.max(0, (this.popCestas || 0) - dt * 4);
    this.popMult = Math.max(0, (this.popMult || 0) - dt * 2.5);
    this.popChipCombo = Math.max(0, (this.popChipCombo || 0) - dt * 4);
    for (const k of ["combo", "fogo", "sprint"]) {
      const v = this.chips[k];
      if (v > 0) this.chips[k] = Math.min(1, v + dt / 0.3);
      else if (v < 0) this.chips[k] = Math.min(0, v + dt);
    }
    if (this.chips.combo > 0 && this.combo < 2) this.chips.combo = -0.25;
    if (this.liga > 0) this.liga += dt;
    this.apagado += (this.apagadoAlvo - this.apagado) * Math.min(1, dt * (this.apagadoAlvo > this.apagado ? 1.5 : 3));
    // a energia dos holofotes cai devagar até o repouso
    this.energiaAlvo = Math.max(0, this.energiaAlvo - dt * 0.18);
    this.energia += (this.energiaAlvo - this.energia) * Math.min(1, dt * 1.2);
    if (this.ehSlam) {
      const azulAlvo = this.enterrada ? 1 : 0;
      this.azul += (azulAlvo - this.azul) * Math.min(1, dt * (this.enterrada ? 3 : 2));
      if (this.azulPulso > 0) this.azulPulso = Math.max(0, this.azulPulso - dt * 1.6);
      if (this.ouro.some > 0) this.ouro.some += dt;
      if (this.ouro.ativo) this.ouro.entra = Math.min(1, (this.ouro.entra || 0) + dt / 0.4);
    } else {
      const vel = this.fogo > 0 ? 2.4 : 1;
      this.faseOnda = (this.faseOnda + dt * 3.5 * vel) % TAU;
      this.faseLampada = (this.faseLampada + dt * 1.6 * vel) % 1;
      this.andado += dt * (this.fogo > 0 ? 144 : 72);
      this.emitirAmbienteSwish(dt);
    }
  }

  saiuDoJogo(b, dt) {
    if (this.ehSlam) {
      // abaixo do aro a bola vira uma das que caem na quadra e quicam
      // para a frente (bolas_caindo.gd) -- é a volta dela até a rampa
      const limite = b.pontuou ? -(REDE + RB * 1.1) : -0.4;
      if (b.h < limite) {
        this.converterEmCaindo(b);
        this.recolher(b);
        return;
      }
    } else if (b.pontuou && b.h < -(REDE + RB * 0.6)) {
      // passou pela rede: some embaixo dela (cesta.gd)
      b.alfa -= dt / 0.15;
      if (b.alfa <= 0) {
        this.recolher(b);
        return;
      }
    }
    if (b.sy - b.sr > this.LH + 30 || b.sx < -200 || b.sx > this.LW + 200 || b.tVoo > 5) this.recolher(b);
  }

  /* ---------------------------------------------- Slam: bolas que caem */
  converterEmCaindo(b) {
    const k = this.pegarCaindo();
    const FY = 44;
    const TOPO = 497;
    let s = 1;
    let h = 0;
    if (b.sy <= TOPO) {
      h = TOPO - b.sy;
    } else {
      s = (b.sy - FY) / (TOPO - FY);
    }
    k.viva = true;
    k.s = s;
    k.h = h;
    k.x = (b.sx - 270) / s;
    k.raio0 = b.sr / s;
    k.vx = ((b.sx - b.sxAnt) / (1 / 60)) / s * 0.25 + mix(-30, 30, Math.random());
    k.vh = -mix(40, 200, Math.random());
    k.vs = mix(0.42, 0.58, Math.random());
    k.espera = 0;
    k.t = 0.2;
    k.quiques = 0;
    k.tipo = b.pontuou && (this.festa || this.ouro.some > 0 && this.ouro.some < 0.3) ? "ouro" : this.enterrada && b.pontuou ? "fogo" : "normal";
    k.cor = SL.laranja;
    k.giro = b.giro;
    k.vgiro = b.vgiro;
  }

  pegarCaindo() {
    let velha = this.caindo[0];
    for (const k of this.caindo) {
      if (!k.viva) return k;
      if (k.t > velha.t) velha = k;
    }
    return velha;
  }

  // bolas extras saindo da cesta (combo, ouro, MODO ENTERRADA)
  soltarCaindo(n, tipo, cor = SL.laranja) {
    for (let i = 0; i < n; i++) {
      const k = this.pegarCaindo();
      const lado = i - (n - 1) / 2;
      // nascem na boca de baixo da rede, já na quadra (um pouco à frente
      // da linha de fundo)
      k.viva = true;
      k.s = (this.aroY + this.redeH - 44) / 453;
      k.h = 6;
      k.x = (this.aroTelaX() - 270) / k.s + mix(-12, 12, Math.random()) + lado * 15;
      k.raio0 = (this.cena.f * RB) / ZR / k.s;
      k.vx = lado * 95 + mix(-35, 35, Math.random());
      k.vh = -mix(20, 130, Math.random());
      k.vs = mix(0.42, 0.58, Math.random());
      k.espera = i * 0.08;
      k.t = 0;
      k.quiques = 0;
      k.tipo = tipo;
      k.cor = cor;
      k.giro = Math.random() * TAU;
      k.vgiro = mix(7, 11, Math.random()) * (Math.random() < 0.5 ? 1 : -1);
    }
  }

  animarCaindo(dt) {
    for (const k of this.caindo) {
      if (!k.viva) continue;
      if (k.espera > 0) {
        k.espera -= dt;
        continue;
      }
      k.t += dt;
      // vem para a frente: a escala da perspectiva cresce cada vez mais rápido
      k.s += k.vs * dt * k.s * k.s;
      k.x += k.vx * dt;
      k.vh -= 750 * dt;
      k.h += k.vh * dt;
      k.giro += k.vgiro * dt;
      if (k.h <= 0 && k.vh < 0) {
        k.h = 0;
        const forca = Math.abs(k.vh);
        k.vh = forca > 70 ? forca * 0.56 : 0;
        k.quiques++;
        const chaoX = 270 + k.x * k.s;
        const chaoY = 44 + 453 * k.s;
        const cor = k.tipo === "fogo" ? "#59ccff" : k.tipo === "ouro" ? SL.ouro : k.cor;
        this.anel(chaoX, chaoY, k.raio0 * k.s * 1.5, k.raio0 * k.s * 0.57, cor, 0.45, 1.3, limitar(forca / 350, 0.25, 0.9));
        if (k.quiques <= 2 && forca > 120) this.som("quica");
      }
      const y = 44 + 453 * k.s - k.h * k.s;
      if (y - k.raio0 * k.s > 980 || Math.abs(k.x * k.s) > 420) k.viva = false;
      if (k.tipo !== "normal" && !this.reduzido && Math.random() < dt * 30) {
        const r = k.raio0 * k.s;
        const p = this.fx.novo(270 + k.x * k.s + mix(-r, r, Math.random()) * 0.4, y, 0, -40, 0.4, r * 1.3,
          tingir(this.img.brilho, k.tipo === "fogo" ? "#4db8ff" : SL.ouro));
        p.t1 = r * 0.3;
        p.alfa = 0.7;
      }
    }
  }

  /* ==================================================================
     EFEITOS
     ================================================================== */
  tremer(f) {
    this.tremor = Math.max(this.tremor, this.reduzido ? f * 0.3 : f);
  }

  flash(cor, forca) {
    this.clarao = forca;
    this.claraoCor = cor;
  }

  aviso(txt, cor, dur = 1.1, prio = 1, grande = false) {
    if (prio < this.avPrio && this.tv < this.avAte) return;
    this.avPrio = prio;
    this.avAte = this.tv + dur + 0.4;
    this.av = { txt, cor, t: 0, dur, grande };
  }

  mostrarFaixa(titulo, sub, cor, dur) {
    this.av = null;
    this.faixa = { titulo, sub, cor, t: 0, dur };
  }

  flutuar(txt, x, y, cor, tam, sobe = 68, atraso = 0, corTexto = false) {
    let f = this.flutuantes.find((q) => !q.vivo);
    if (!f) f = this.flutuantes.reduce((a, q) => (q.t > a.t ? q : a));
    f.vivo = true;
    f.txt = txt;
    f.x = x;
    f.y = y;
    f.cor = cor;
    f.tam = tam;
    f.sobe = sobe;
    f.t = -atraso;
    f.corTexto = corTexto;
  }

  anel(x, y, rx, ry, cor, dur, cresce, alfa = 0.95) {
    let a = this.aneis.find((q) => !q.vivo);
    if (!a) a = this.aneis.reduce((m, q) => (q.t / q.dur > m.t / m.dur ? q : m));
    a.vivo = true;
    a.x = x;
    a.y = y;
    a.rx = rx;
    a.ry = ry;
    a.dur = dur;
    a.t = 0;
    a.cresce = cresce;
    a.alfa = alfa;
    a.spr = tingir(this.ehSlam ? this.img.anel : this.img.swishAnel, cor);
  }

  faiscasAro(x, y, cor, n, forca = 1) {
    const qtd = Math.ceil((this.reduzido ? n * 0.4 : n));
    const spr = this.ehSlam ? tingir(this.img.faisca, misturaCor(cor, "#ffffff", 0.35)) : tingir(this.img.swishFaisca, misturaCor(cor, "#ffffff", 0.3));
    for (let i = 0; i < qtd; i++) {
      const ang = -Math.PI / 2 + mix(-1.25, 1.25, Math.random());
      const v = (this.ehSlam ? 300 : 270) * mix(0.5, 1, Math.random()) * forca;
      const p = this.fx.novo(x + mix(-this.aroRX, this.aroRX, Math.random()) * 0.8, y, Math.cos(ang) * v, Math.sin(ang) * v,
        mix(0.5, 0.9, Math.random()), this.ehSlam ? mix(14, 26, Math.random()) : mix(10, 18, Math.random()), spr);
      p.g = 520 * (this.ehSlam ? 0.5 : 0.75);
      if (this.ehSlam) {
        p.alinhar = true;
        p.razao = 0.3;
      }
    }
  }

  estrelasAro(x, y, cor) {
    const spr = tingir(this.img.swishEstrela, misturaCor(cor, "#ffffff", 0.5));
    for (let i = 0; i < (this.reduzido ? 4 : 10); i++) {
      const ang = -Math.PI / 2 + mix(-1.2, 1.2, Math.random());
      const v = 270 * mix(0.5, 1, Math.random());
      const p = this.fx.novo(x + mix(-50, 50, Math.random()), y, Math.cos(ang) * v, Math.sin(ang) * v, 0.9, mix(18, 30, Math.random()), spr);
      p.g = 390;
      p.vrot = mix(-4, 4, Math.random());
      p.rot = 0.01;
    }
  }

  // FOGOS DE ARTIFÍCIO (fogos.gd): estouros um depois do outro no alto
  fogos(n, cores) {
    for (let k = 0; k < n; k++) {
      this.agendarFx(k * 0.22, () => {
        const x = 120 + Math.random() * 720;
        const y = 45 + Math.random() * 190;
        const cor = cores[k % cores.length];
        const spr = tingir(this.img.swishFaisca, misturaCor(cor, "#ffffff", 0.3));
        const qtd = this.reduzido ? 16 : 46;
        for (let i = 0; i < qtd; i++) {
          const ang = Math.random() * TAU;
          const v = 218 * mix(0.65, 1, Math.random());
          const p = this.fx.novo(x, y, Math.cos(ang) * v, Math.sin(ang) * v, mix(0.9, 1.25, Math.random()), mix(9, 15, Math.random()), spr);
          p.g = 172;
          p.arrasto = 1.4;
        }
        const c = this.fx.novo(x, y, 0, 0, 0.35, 50, tingir(this.img.swishBrilho, cor));
        c.t1 = 180;
        c.alfa = 0.6;
        if (k === 0) this.som("tiro");
      });
    }
  }

  confete(n) {
    const spr = ["#ff4d4d", "#ffd21f", "#4dff88", "#4db8ff", "#ff4dd2", "#ffffff"].map((c) => tingir(this.img.confete, c));
    for (let i = 0; i < (this.reduzido ? n / 3 : n); i++) {
      const p = this.fx.novo(Math.random() * this.LW, -20 - Math.random() * 200, mix(-40, 40, Math.random()), mix(60, 180, Math.random()),
        mix(2.5, 3.5, Math.random()), mix(10, 16, Math.random()), spr[i % spr.length]);
      p.aditivo = false;
      p.g = 120;
      p.razao = 0.6;
      p.rot = Math.random() * TAU;
      p.vrot = mix(-6, 6, Math.random());
    }
  }

  fogoNaBola(b, dt) {
    if (this.reduzido || Math.random() > dt * 70) return;
    const s = b.sr / 42;
    const p = this.fx.novo(b.sx + mix(-b.sr, b.sr, Math.random()) * 0.35, b.sy + mix(-b.sr, b.sr, Math.random()) * 0.35,
      mix(-20, 20, Math.random()), -60, 0.42, 58 * s, tingir(this.img.swishBrilho, "#fff28c"));
    p.spr2 = tingir(this.img.swishBrilho, "#ff8014");
    p.spr3 = tingir(this.img.swishBrilho, "#cc0d1a");
    p.g = -240;
    p.t1 = 20 * s;
    p.alfa = 0.85;
  }

  emitirAmbienteSwish(dt) {
    // faíscas subindo devagar do chão da arena (fundo_animado.gd)
    if (Math.random() < dt * (this.reduzido ? 3 : 7)) {
      const p = this.fx.novo(Math.random() * 960, 545, mix(-8, 8, Math.random()), -30 * mix(0.4, 1, Math.random()), 5, mix(5, 14, Math.random()),
        tingir(this.img.swishFaisca, "#ffbf59"));
      p.spr2 = tingir(this.img.swishFaisca, "#d17aff");
      p.spr3 = tingir(this.img.swishFaisca, "#b366ff");
      p.g = -6;
      p.alfa = 0.85;
      p.entra = 0.2;
    }
    // EM CHAMAS: chamas subindo do pé da tela e no aro
    if (this.fogo > 0 && !this.reduzido) {
      const cor0 = tingir(this.img.swishBrilho, "#ffe666");
      const cor1 = tingir(this.img.swishBrilho, "#ff590d");
      const cor2 = tingir(this.img.swishBrilho, "#b30033");
      const quantos = (x) => Math.floor(x) + (Math.random() < x % 1 ? 1 : 0);
      const nTela = quantos(dt * 36);
      for (let i = 0; i < nTela; i++) {
        const p = this.fx.novo(Math.random() * 990 - 15, 560, mix(-8, 8, Math.random()), -128 * mix(0.5, 1.5, Math.random()), 1.1,
          mix(35, 86, Math.random()), cor0);
        p.spr2 = cor1;
        p.spr3 = cor2;
        p.g = -90;
        p.alfa = 0.55;
        p.t1 = 10;
      }
      const nAro = quantos(dt * 60);
      const x = this.aroTelaX();
      for (let i = 0; i < nAro; i++) {
        const ang = Math.random() * Math.PI;
        const p = this.fx.novo(x + Math.cos(ang) * this.aroRX * mix(0.3, 1, Math.random()), this.aroY + Math.sin(ang) * this.aroRY,
          mix(-6, 6, Math.random()), -68 * mix(0.5, 1.5, Math.random()), 0.7, mix(26, 52, Math.random()), cor0);
        p.spr2 = cor1;
        p.spr3 = cor2;
        p.g = -195;
        p.alfa = 0.8;
        p.t1 = 8;
      }
    }
  }

  /* O piso de LED acende em onda (grade.gd: disparar). */
  dispararPiso(x, y, combo = 1, cor = null, inverso = false, atraso = 0) {
    if (!this.ehSlam) return;
    const n = Math.max(1, combo);
    let dur = 1.12;
    let larg = 100;
    if (n >= 13) { dur = 1.34; larg = 149; }
    else if (n >= 9) { dur = 1.26; larg = 139; }
    else if (n >= 6) { dur = 1.18; larg = 130; }
    else if (n >= 3) { dur = 0.84; larg = 113; }
    if (this.ondasPiso.length >= 4) this.ondasPiso.shift();
    this.ondasPiso.push({ x, y, t: -atraso, dur, larg, cor: cor || corDoCombo(n), inv: inverso, ida: n >= 6 && !inverso });
  }

  // a onda de luz que acende as linhas de neon da própria arte
  ondaNoFundo(x, y, cor = "normal") {
    this.ondaFundo = 0;
    this.ondaFundoX = x;
    this.ondaFundoY = y;
    this.ondaFundoCor = cor;
  }

  /* Os raios de energia (raio_eletrico.gd): em toda cesta caem do alto
     da tela na caixa da fase -- 1, 2 ou 3 conforme a sequência. */
  raiosDaCesta(n) {
    const qtd = n < 3 ? 1 : n < 9 ? 2 : 3;
    const cor = n >= 3 ? misturaCor(corDoCombo(n), "#80d9ff", 0.25) : "#73d1ff";
    for (let i = 0; i < qtd; i++) {
      const x = mix(80, 460, Math.random());
      this.dispararRaio(x, -15, limitar(x, 190, 350) + mix(-30, 30, Math.random()), 334, cor, 0.85 + 0.05 * Math.min(n, 10), 0.26 + 0.02 * Math.min(n, 6));
    }
  }

  raioEnterrada() {
    const origens = [[20, 30], [520, 30], [15, 450], [525, 450], [270, 10]];
    const o = origens[Math.floor(Math.random() * origens.length)];
    this.dispararRaio(o[0], o[1], this.aroTelaX() + mix(-30, 30, Math.random()), this.aroY + mix(-15, 15, Math.random()), "#59ccff", 1.3, 0.3);
    if (Math.random() < 0.35) this.som("batida");
  }

  dispararRaio(x0, y0, x1, y1, cor, esp, dur) {
    let r = this.raios.find((q) => !q.vivo);
    if (!r) r = this.raios[0];
    r.vivo = true;
    r.x0 = x0; r.y0 = y0; r.x1 = x1; r.y1 = y1;
    r.cor = cor;
    r.esp = esp;
    r.dur = dur;
    r.t = 0;
    this.gerarRaio(r);
    // o clarão onde o raio bate
    const p = this.fx.novo(x1, y1, 0, 0, dur * 1.2, 60 * esp, tingir(this.img.brilho, cor));
    p.t1 = 110 * esp;
    p.alfa = 0.8;
    const f = this.fx.novo(x1, y1, 0, -20, 0.6, 30, tingir(this.img.fumaca, cor));
    f.t1 = 70;
    f.alfa = 0.35;
  }

  // o caminho do raio muda a cada tremida (deslocamento do ponto do meio)
  gerarRaio(r) {
    const p = r.pts;
    p[0] = r.x0; p[1] = r.y0; p[32] = r.x1; p[33] = r.y1;
    const comp = Math.hypot(r.x1 - r.x0, r.y1 - r.y0);
    let desvio = comp * 0.16;
    for (let passo = 16; passo > 1; passo /= 2) {
      for (let i = 0; i < 16; i += passo) {
        const a = i * 2;
        const b = (i + passo) * 2;
        const m = (i + passo / 2) * 2;
        const dx = p[b] - p[a];
        const dy = p[b + 1] - p[a + 1];
        const L = Math.hypot(dx, dy) || 1;
        const off = (Math.random() - 0.5) * 2 * desvio;
        p[m] = (p[a] + p[b]) / 2 - (dy / L) * off;
        p[m + 1] = (p[a + 1] + p[b + 1]) / 2 + (dx / L) * off;
      }
      desvio *= 0.55;
    }
    // um galho saindo do meio do caminho
    const q = r.ramo;
    const k = (4 + Math.floor(Math.random() * 6)) * 2;
    q[0] = p[k]; q[1] = p[k + 1];
    const ang = Math.atan2(r.y1 - r.y0, r.x1 - r.x0) + (Math.random() < 0.5 ? -1 : 1) * mix(0.4, 0.9, Math.random());
    const passoR = comp * 0.035;
    for (let i = 1; i < 9; i++) {
      q[i * 2] = q[i * 2 - 2] + Math.cos(ang) * passoR + (Math.random() - 0.5) * passoR * 1.2;
      q[i * 2 + 1] = q[i * 2 - 1] + Math.sin(ang) * passoR + (Math.random() - 0.5) * passoR * 1.2;
    }
    r.troca = mix(0.04, 0.09, Math.random());
  }

  // câmeras da torcida piscando nas laterais (holofotes.gd: flashes)
  flashesTorcida(n) {
    for (let i = 0; i < n; i++) {
      this.agendarFx(i * 0.06 + Math.random() * 0.12, () => {
        const esq = Math.random() < 0.5;
        const x = esq ? mix(20, 95, Math.random()) : mix(445, 520, Math.random());
        const y = mix(505, 820, Math.random());
        const p = this.fx.novo(x, y, 0, 0, 0.32, 20, this.img.estrela);
        p.t1 = 46;
        const g = this.fx.novo(x, y, 0, 0, 0.25, 50, this.img.brilho);
        g.t1 = 20;
        g.alfa = 0.8;
      });
    }
  }

  /* ==================================================================
     DESENHO
     ================================================================== */
  desenhar(ctx) {
    const agora = performance.now();
    const dt = this.ultimoQuadro ? Math.min(0.05, Math.max(0, (agora - this.ultimoQuadro) / 1000)) : 0;
    this.ultimoQuadro = agora;
    this.animar(dt);
    ctx.save();
    if (this.encaixe) {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, this.api.W, this.api.H);
      ctx.translate(this.ox, this.oy);
      ctx.scale(this.esc, this.esc);
      ctx.beginPath();
      ctx.rect(0, 0, this.LW, this.LH);
      ctx.clip();
    }
    if (this.ehSlam) this.desenharSlam(ctx);
    else this.desenharSwish(ctx);
    ctx.restore();
  }

  tremido() {
    if (this.tremor <= 0.1) return [0, 0];
    return [(Math.random() - 0.5) * 2 * this.tremor, (Math.random() - 0.5) * 2 * this.tremor];
  }

  txt(ctx, s, x, y, tam, cor, contorno = null, alinhar = "center", peso = 900, sombra = null) {
    this.api.texto(ctx, s, x, y, { tamanho: tam, cor, contorno, alinhar, peso, sombra });
  }

  /* ================================================== SLAM ARENA ==== */
  desenharSlam(ctx) {
    const [tx, ty] = this.tremido();
    ctx.save();
    ctx.translate(tx, ty);
    this.fundoSlam(ctx);
    this.pisoSlam(ctx);
    this.auraSlam(ctx);
    this.holofotesSlam(ctx);
    this.barrasSlam(ctx);
    this.hudSlam(ctx);
    this.ouroSlam(ctx);
    this.tabelaSlam(ctx);
    this.desenharCestaECamadas(ctx);
    this.desenharCaindo(ctx);
    this.desenharRaios(ctx);
    // a arena apagada (antes da primeira cesta, ou quando não passou)
    if (this.apagado > 0.01) {
      ctx.fillStyle = `rgba(0,0,0,${this.apagado})`;
      ctx.fillRect(-20, -20, this.LW + 40, this.LH + 40);
    }
    if (this.liga > 0 && this.liga < 0.7) {
      // a arena liga como neon: pisca antes de firmar
      const on = Math.sin(this.liga * 70) > 0.2 || this.liga > 0.5;
      if (!on) {
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.fillRect(-20, -20, this.LW + 40, this.LH + 40);
      }
    }
    this.desenharBolasCamada(ctx, 2);
    this.fx.desenhar(ctx, true);
    this.desenharAneis(ctx, true);
    this.fx.desenhar(ctx, false);
    this.desenharMaoEFila(ctx);
    ctx.restore();
    this.desenharFlutuantes(ctx);
    this.comboSlam(ctx);
    this.avisoSlam(ctx);
    this.bordaRecorde(ctx);
    this.aquecerSlam(ctx);
    this.mapaSlam(ctx);
    this.contagemTela(ctx);
  }

  /* O jogador do pôster (a aura dele) aparece enorme atrás da cesta no
     MODO ENTERRADA e na abertura da FINAL. */
  auraSlam(ctx) {
    const pulso = this.enterrada ? 0.1 + 0.05 * Math.sin(this.tv * 4) : 0;
    const flash = this.auraT < 1.3 ? (1 - this.auraT / 1.3) * 0.65 : 0;
    const a = Math.max(pulso, flash);
    if (a <= 0.01) return;
    const spr = tingir(this.img.slamAura, this.fase === 2 && !this.enterrada ? "#b873ff" : "#40a6ff");
    if (!spr) return;
    const esc = 1 + (this.auraT < 1.3 ? (1 - this.auraT / 1.3) * 0.08 : 0);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = a;
    const w = 380 * esc;
    const h = 497 * esc;
    ctx.drawImage(spr, 270 - w / 2, 720 - h / 2, w, h);
    ctx.restore();
  }

  fundoSlam(ctx) {
    const F = this.fundos;
    if (!F.normal) {
      ctx.fillStyle = "#120600";
      ctx.fillRect(0, 0, 540, 960);
      return;
    }
    ctx.drawImage(F.normal, 0, 0, 540, 960);
    const azul = Math.max(this.azul, this.azulPulso || 0);
    if (azul > 0.01 && F.azul) {
      ctx.globalAlpha = azul;
      ctx.drawImage(F.azul, 0, 0);
      ctx.globalAlpha = 1;
    }
    if (this.alerta && F.vermelho && this.estado === "jogando") {
      ctx.globalAlpha = 0.35 + 0.3 * Math.sin(this.tv * 9);
      ctx.drawImage(F.vermelho, 0, 0);
      ctx.globalAlpha = 1;
    }
    const base = azul > 0.5 && F.azul ? F.azul : F.normal;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    // o neon respira
    ctx.globalAlpha = 0.1 + 0.1 * (0.5 + 0.5 * Math.sin(this.tv * 1.5));
    ctx.drawImage(base, 0, 0, 540, 960);
    // a faixa de luz que desce (radar)
    const radar = this.tv % 6;
    if (radar < 2.2) {
      const y = limitar(mix(-50, 1025, radar / 2.2) - 30, 0, 900);
      ctx.globalAlpha = 0.55;
      ctx.drawImage(base, 0, y, 540, 60, 0, y, 540, 60);
    }
    // a onda da cesta: as linhas de neon acendem quando ela passa
    if (this.ondaFundo < 1.2) {
      const r = this.ondaFundo * 875;
      const forca = 1 - this.ondaFundo / 1.2;
      const img = this.ondaFundoCor === "verde" && F.verde ? F.verde : base;
      const ri = Math.max(0, r - 20);
      ctx.beginPath();
      ctx.arc(this.ondaFundoX, this.ondaFundoY, r + 70, 0, TAU);
      ctx.moveTo(this.ondaFundoX + ri, this.ondaFundoY);
      ctx.arc(this.ondaFundoX, this.ondaFundoY, ri, 0, TAU, true);
      ctx.clip("evenodd");
      ctx.globalAlpha = forca;
      ctx.drawImage(img, 0, 0, 540, 960);
      ctx.drawImage(img, 0, 0, 540, 960);
    }
    ctx.restore();
  }

  pisoSlam(ctx) {
    const L = this.ladrilhos;
    if (!L) return;
    const base = this.azul > 0.5 ? this.pisoBase.azul : this.pisoBase.laranja;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.8 + 0.2 * Math.sin(this.tv * 1.3);
    ctx.drawImage(base, 0, 490);
    if (this.enterrada) ctx.drawImage(base, 0, 490);   // no MODO ENTERRADA o piso fica mais aceso
    const corBase = this.azul > 0.5 ? "#2a86ff" : SL.laranja;
    const sprBase = tingir(this.img.ladrilho, corBase);
    // a faixa de luz que corre do fundo para a frente de tempos em tempos
    const varre = fract(this.tv * 0.11) * 1.6 - 0.3;
    // ondas
    const ondas = this.ondasPiso;
    const rec = this.festa && this.estado !== "fim";
    const recX = this.aroTelaX();
    const recY = this.aroY - 15;
    const recA = fract(this.tv * 0.675);
    const recB = fract(this.tv * 0.675 + 0.5);
    for (let i = 0; i < L.length; i++) {
      const l = L[i];
      let k = 0;
      let cor = null;
      for (let j = 0; j < ondas.length; j++) {
        const o = ondas[j];
        if (o.t < 0) continue;
        const p = limitar(o.t / o.dur, 0, 1);
        let pr = p;
        let fade = 1 - p;
        if (o.ida) {
          pr = p <= 0.5 ? p * 2 : (1 - p) * 2;
          fade = 1 - Math.abs(p - 0.5) * 0.72;
        }
        const raio = o.inv ? (1 - pr) * 729 : pr * 729;
        const d = Math.hypot(l.x - o.x, l.y - o.y);
        let kk = limitar(1 - Math.abs(d - raio) / o.larg, 0, 1) * fade;
        kk *= kk;
        if (kk > k) {
          k = kk;
          cor = o.cor;
        }
      }
      if (rec) {
        // RECORDE: duas ondas douradas sem fim, cada uma com um rastro branco
        const d = Math.hypot(l.x - recX, l.y - recY);
        for (let w = 0; w < 2; w++) {
          const f = w ? recB : recA;
          const rr = mix(70, 750, f);
          const e = Math.pow(Math.max(0, Math.sin(f * Math.PI)), 0.72) * 0.9;
          const ouro = limitar(1 - Math.abs(d - rr) / 30, 0, 1) * e;
          const branco = limitar(1 - Math.abs(d - rr + 60) / 25, 0, 1) * e * 0.85;
          if (ouro > k) {
            k = ouro;
            cor = SL.ouro;
          }
          if (branco > k) {
            k = branco;
            cor = "#ffffff";
          }
        }
      }
      const faixa = limitar(1 - Math.abs(l.prof - varre) / 0.12, 0, 1) * 0.22;
      if (k < 0.03 && faixa < 0.03) continue;
      const sc = 0.64 + 0.48 * Math.min(k * 1.6, 1);
      const w = l.w * sc;
      const h = l.h * sc;
      const sobe = k * (2.5 + 4.5 * l.prof);
      const spr = k >= 0.03 && cor ? tingir(this.img.ladrilho, cor) : sprBase;
      ctx.globalAlpha = Math.min(1, faixa + k * 0.95);
      ctx.drawImage(spr, l.x - w / 2, l.y - h / 2 - sobe, w, h);
    }
    ctx.restore();
  }

  holofotesSlam(ctx) {
    if (!this.coneHolofote) return;
    const modo = this.enterrada ? 1 : this.festa ? 2 : 0;
    const cor = ["#ff9e38", "#59c7ff", "#ffd140"][modo];
    const spr = tingir(this.coneHolofote, cor);
    const rapido = modo === 1 ? 2.6 : 1;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let lado = 0; lado < 2; lado++) {
      const sinal = lado === 0 ? 1 : -1;
      const ang = -0.62 * sinal + Math.sin(this.tv * 0.45 * rapido + lado * 2.1) * 0.3 * sinal;
      const forca = 0.1 + 0.24 * this.energia + (modo ? 0.08 : 0);
      ctx.globalAlpha = forca * (0.85 + 0.15 * Math.sin(this.tv * 3.1 + lado));
      ctx.save();
      ctx.translate(lado === 0 ? -15 : 555, 480);
      ctx.rotate(ang);
      ctx.drawImage(spr, -120, 0, 240, 575);
      ctx.restore();
    }
    ctx.restore();
  }

  // o equalizador nas "asas" da arena (barras.gd)
  barrasSlam(ctx) {
    const azul = this.azul > 0.5;
    const c0 = azul ? "#1a73ff" : "#ff5205";
    const c1 = azul ? "#99f2ff" : "#ffd966";
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let lado = 0; lado < 2; lado++) {
      const x0 = lado === 0 ? 39 : 419;
      for (let i = 0; i < 8; i++) {
        const ruido = Math.abs(Math.sin(this.tv * (5 + i * 0.9 + lado) + i * 1.7)) * 0.6 + Math.abs(Math.sin(this.tv * 2.3 + i)) * 0.4;
        const h = 54 * (0.12 + 0.88 * this.barras * ruido);
        const gr = ctx.createLinearGradient(0, 226, 0, 226 - h);
        gr.addColorStop(0, rgba(c0, 0.55));
        gr.addColorStop(1, rgba(c1, 0.8));
        ctx.fillStyle = gr;
        ctx.fillRect(x0 + i * 11, 226 - h, 7, h);
      }
    }
    ctx.restore();
  }

  // a moldura de uma caixa da arte pintada na cor da informação dela
  molduraCor(ctx, pts, cor, espelho = false) {
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const x = espelho ? 540 - pts[i][0] : pts[i][0];
      if (i === 0) ctx.moveTo(x, pts[i][1]);
      else ctx.lineTo(x, pts[i][1]);
    }
    ctx.closePath();
    ctx.strokeStyle = rgba(cor, 0.28);
    ctx.lineWidth = 9;
    ctx.stroke();
    ctx.strokeStyle = cor;
    ctx.lineWidth = 2.6;
    ctx.stroke();
    ctx.strokeStyle = rgba("#ffffff", 0.55);
    ctx.lineWidth = 0.9;
    ctx.stroke();
  }

  hudSlam(ctx) {
    const f = this.fase;
    const final = f === 2;
    const passou = !final && this.passou[f];
    // RELÓGIO (o círculo da arte): 60 tracinhos, o arco fino e os números
    const cx = 269.7;
    const cy = 149.5;
    const frac = this.estado === "jogando" ? this.tempo / this.total : this.estado === "fimFase" || this.estado === "fim" ? 0 : 1;
    const corT = this.alerta ? SL.vermelho : SL.laranja;
    const pisca = this.alerta ? 0.55 + 0.45 * Math.abs(Math.sin(this.tv * 6)) : 1;
    ctx.save();
    ctx.lineCap = "round";
    const acesos = frac * 60;
    ctx.beginPath();
    for (let i = 0; i < 60; i++) {
      if (i < acesos) continue;
      const a = -Math.PI / 2 + (i / 60) * TAU;
      ctx.moveTo(cx + Math.cos(a) * 95.5, cy + Math.sin(a) * 95.5);
      ctx.lineTo(cx + Math.cos(a) * 102.5, cy + Math.sin(a) * 102.5);
    }
    ctx.strokeStyle = "rgba(60,25,5,0.8)";
    ctx.lineWidth = 3.2;
    ctx.stroke();
    ctx.beginPath();
    for (let i = 0; i < 60; i++) {
      if (i >= Math.ceil(acesos)) break;
      const a = -Math.PI / 2 + (i / 60) * TAU;
      ctx.moveTo(cx + Math.cos(a) * 95.5, cy + Math.sin(a) * 95.5);
      ctx.lineTo(cx + Math.cos(a) * 102.5, cy + Math.sin(a) * 102.5);
    }
    ctx.globalAlpha = pisca;
    ctx.strokeStyle = rgba(corT, 0.35);
    ctx.lineWidth = 7;
    ctx.stroke();
    ctx.strokeStyle = misturaCor(corT, "#ffffff", 0.3);
    ctx.lineWidth = 3.2;
    ctx.stroke();
    // o arco fino com a cabeça brilhante
    if (frac > 0.001) {
      const a1 = -Math.PI / 2 + frac * TAU;
      ctx.beginPath();
      ctx.arc(cx, cy, 88, -Math.PI / 2, a1);
      ctx.strokeStyle = corT;
      ctx.lineWidth = 2.4;
      ctx.stroke();
      const spr = tingir(this.img.brilho, misturaCor(corT, "#ffffff", 0.4));
      if (spr) ctx.drawImage(spr, cx + Math.cos(a1) * 88 - 12, cy + Math.sin(a1) * 88 - 12, 24, 24);
    }
    // o rastro de luz que gira sem parar no círculo da arte
    ctx.globalCompositeOperation = "lighter";
    const giro = this.tv * 1.6;
    for (let k = 0; k < 10; k++) {
      ctx.beginPath();
      ctx.arc(cx, cy, 112.5, giro - (k + 1) * 0.12, giro - k * 0.12);
      ctx.strokeStyle = rgba("#ffd98c", 0.5 * (1 - k / 10));
      ctx.lineWidth = 3.2;
      ctx.stroke();
    }
    ctx.restore();
    this.txt(ctx, "TEMPO", cx, 101, 19, "#ffffff", corT);
    const seg = this.estado === "aquece" || this.estado === "liga" || this.estado === "mapa" || this.estado === "contagem" ? this.total : Math.ceil(this.tempo);
    ctx.save();
    ctx.globalAlpha = pisca;
    led(ctx, numeroLed(seg, 2), cx, 163, 66, corT);
    ctx.restore();

    // RECORDE (topo esquerdo), com a coroa
    const corRec = SL.violeta;
    if (this.img.coroa) ctx.drawImage(this.img.coroa, 22, 23, 30, 21.6);
    this.txt(ctx, "RECORDE", 56, 35, 16, corRec, "#0d0021", "left");
    const rec = Math.max(this.recordeAntigo, this.festa ? this.pontos : 0);
    led(ctx, numeroLed(rec, 4), 86, 76, 32, corRec);
    // MELHORES DE HOJE (topo direito)
    this.txt(ctx, "MELHORES DE HOJE", 514, 35, 13.5, corRec, "#0d0021", "right");
    for (let i = 0; i < 3; i++) {
      const y = 60 + i * 20;
      const m = this.img["medalha" + (i + 1)];
      if (m) ctx.drawImage(m, 428, y - 9, 18, 18);
      this.txt(ctx, this.hoje[i] !== undefined ? String(this.hoje[i]) : "-", 510, y + 1, 15, "#ffffff", "#000000", "right");
    }

    // META (esquerda) e PONTOS (direita): as caixas da arte com a cor de cada informação
    const MOLDURA = [[33.9, 233.6], [164.2, 233.6], [182.5, 256], [182.5, 305.9], [52.8, 305.9], [33.9, 286.4]];
    const corMeta = passou ? SL.verde : final ? SL.violeta : SL.ciano;
    this.molduraCor(ctx, MOLDURA, corMeta);
    this.molduraCor(ctx, MOLDURA, SL.rosa, true);
    if (final) {
      this.txt(ctx, "RECORDE", 108, 247, 16, SL.violeta, "#0d0021");
      led(ctx, numeroLed(Math.max(this.recordeAntigo, this.pontos), 3), 108, 283, 32, SL.violeta);
    } else if (passou) {
      this.txt(ctx, "PASSOU!", 108, 247, 17, SL.verde, "#001a08");
      this.letreiroPassou(ctx, MOLDURA, `PASSOU DE FASE  •  RUMO À ${this.regras.nomes[f + 1]}  •  `);
    } else {
      this.txt(ctx, "META", 108, 247, 17, SL.ciano, "#001a26");
      led(ctx, numeroLed(this.alvo, 3), 108, 283, 32, SL.ciano);
    }
    this.txt(ctx, "PONTOS", 432, 247, 17, SL.rosa, "#1a000d");
    const pop = 1 + (this.popPontos || 0) * 0.25;
    ctx.save();
    ctx.translate(432, 283);
    ctx.scale(pop, pop);
    led(ctx, numeroLed(this.pontos, 3), 0, 0, 32, SL.rosa);
    ctx.restore();

    // MULTIPLICADOR (a caixa do meio) e a barrinha do tempo da sequência
    let corM = SL.laranja;
    if (this.mult === 2) corM = "#ff940a";
    else if (this.mult === 3) corM = "#1f8cff";
    else if (this.mult >= 4) corM = "#59e6ff";
    this.txt(ctx, final ? "MULTIPLICADOR TURBINADO" : "MULTIPLICADOR", 270, 274, 9.5, "#ffffff", "#0d0500");
    const pm = 1 + (this.popMult || 0) * 0.5;
    this.txt(ctx, `x${this.mult}`, 270, 291, 24 * pm, "#ffffff", corM);
    if (this.combo > 0 && this.estado === "jogando") {
      const resta = limitar(1 - (this.decorrido - this.ultimaCesta) / this.regras.janela, 0, 1);
      ctx.fillStyle = corM;
      ctx.fillRect(270 - 68 * resta, 303, 136 * resta, 3);
    }
  }

  // PASSOU: no lugar da meta, um letreiro de LED com lâmpadas correndo na moldura
  letreiroPassou(ctx, moldura, texto) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(44, 266, 132, 34);
    ctx.clip();
    const largura = texto.length * 9.6;
    const x0 = 176 - ((this.tv * 60) % largura);
    for (let x = x0; x < 176 + largura; x += largura) {
      if (x > 176) break;
      this.txt(ctx, texto, x, 283, 16, SL.verde, "#002208", "left");
      this.txt(ctx, texto, x + largura, 283, 16, SL.verde, "#002208", "left");
    }
    ctx.restore();
    // lâmpadas correndo em cima da moldura
    const spr = tingir(this.img.brilho, SL.verde);
    if (!spr) return;
    let per = 0;
    const seg = [];
    for (let i = 0; i < moldura.length; i++) {
      const a = moldura[i];
      const b = moldura[(i + 1) % moldura.length];
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      seg.push([a, b, L, per]);
      per += L;
    }
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const n = 18;
    for (let k = 0; k < n; k++) {
      const d = modPos((k / n) * per + this.tv * 70, per);
      for (const [a, b, L, ini] of seg) {
        if (d >= ini && d < ini + L) {
          const t = (d - ini) / L;
          ctx.globalAlpha = k % 2 ? 0.9 : 0.5;
          ctx.drawImage(spr, mix(a[0], b[0], t) - 7, mix(a[1], b[1], t) - 7, 14, 14);
          break;
        }
      }
    }
    ctx.restore();
  }

  ouroSlam(ctx) {
    const o = this.ouro;
    if (!o.ativo && !(o.some > 0 && o.some < 0.35)) return;
    const x = 84;
    const y = 640 - Math.abs(Math.sin(this.tv * 3.2)) * 10;
    let s = o.ativo ? saiDeTras(o.entra || 0) : 1 + o.some * 2.5;
    const alfa = o.ativo ? 1 : Math.max(0, 1 - o.some / 0.35);
    ctx.save();
    ctx.globalAlpha = alfa;
    const halo = tingir(this.img.brilho, SL.ouro);
    if (halo) {
      ctx.globalCompositeOperation = "lighter";
      ctx.drawImage(halo, x - 70 * s, y - 70 * s, 140 * s, 140 * s);
      ctx.globalCompositeOperation = "source-over";
    }
    if (o.ativo) {
      ctx.beginPath();
      ctx.arc(x, y, 46 * s, -Math.PI / 2, -Math.PI / 2 + (o.resta / 6) * TAU);
      ctx.strokeStyle = SL.ouro;
      ctx.lineWidth = 3;
      ctx.stroke();
    }
    desenharBola(ctx, this.folha, x, y, 34 * s, this.tv * 5, true);
    ctx.restore();
    if (o.ativo) this.txt(ctx, "+5", x, y + 66, 22, SL.ouro, "#4d1a00");
  }

  /* A tabela do Slam é a caixa da fase da arte: o vidro, o neon na cor
     da fase e o nome da fase dentro. Na FINAL ela anda com o aro. */
  tabelaSlam(ctx) {
    const T = this.tabelaPx;
    const dx = (this.cena.f * this.aroX) / ZB;
    const x0 = 270 - T.meia + dx;
    const w = T.meia * 2;
    const y0 = T.cima;
    const h = T.baixo - T.cima;
    const f = this.fase;
    const passou = f < 2 && this.passou[f];
    const cor = passou ? SL.verde : CORES_FASE[f];
    ctx.save();
    // trilho da tabela na final
    if (this.aroAmp > 0.01) {
      ctx.strokeStyle = rgba(cor, 0.35 * (this.aroAmp / 0.26));
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(60, y0 - 6);
      ctx.lineTo(480, y0 - 6);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.beginPath();
    caminhoArredondado(ctx, x0, y0, w, h, 6);
    const vidro = ctx.createLinearGradient(x0, y0, x0 + w, y0 + h);
    vidro.addColorStop(0, "rgba(30,14,40,0.82)");
    vidro.addColorStop(0.5, "rgba(14,6,22,0.88)");
    vidro.addColorStop(1, "rgba(30,14,40,0.82)");
    ctx.fillStyle = vidro;
    ctx.fill();
    // o reflexo no vidro
    ctx.save();
    ctx.clip();
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = "rgba(255,255,255,0.05)";
    ctx.beginPath();
    ctx.moveTo(x0 + w * 0.55, y0);
    ctx.lineTo(x0 + w * 0.75, y0);
    ctx.lineTo(x0 + w * 0.35, y0 + h);
    ctx.lineTo(x0 + w * 0.15, y0 + h);
    ctx.fill();
    ctx.restore();
    const brilho = 0.3 + 0.7 * this.tabelaBrilho;
    ctx.beginPath();
    caminhoArredondado(ctx, x0, y0, w, h, 6);
    ctx.strokeStyle = rgba(cor, 0.25 + 0.25 * brilho);
    ctx.lineWidth = 10;
    ctx.stroke();
    ctx.strokeStyle = cor;
    ctx.lineWidth = 2.8;
    ctx.stroke();
    ctx.beginPath();
    caminhoArredondado(ctx, x0 + 6, y0 + 6, w - 12, h - 12, 4);
    ctx.strokeStyle = rgba(cor, 0.6);
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
    // o nome da fase e a frase do momento (dentro da caixa, como na máquina)
    const cx = x0 + w / 2;
    this.txt(ctx, this.regras.nomes[f], cx, y0 + 26, 25, passou ? SL.verde : cor, "#000000");
    let sub;
    let corSub = "#ffe69e";
    if (this.estado === "aquece") sub = "ACERTE A CESTA!";
    else if (this.esperando > 6 && this.estado === "jogando" && Math.floor(this.tv * 2) % 2 === 0) sub = "ARREMESSE!";
    else if (f < 2) {
      if (passou) {
        sub = this.festa ? "VOCÊ É O RECORDE!" : "PASSOU! SIGA PONTUANDO";
        corSub = SL.verde;
      } else sub = `FALTAM ${Math.max(0, this.alvo - this.pontos)} PARA PASSAR`;
    } else if (this.festa || (this.recordeAntigo < 3 && this.pontos > this.recordeAntigo && this.pontos > 0)) {
      sub = "VOCÊ É O RECORDE DA ARENA!";
    } else if (this.recordeAntigo > 0) {
      sub = `FALTAM ${this.recordeAntigo + 1 - this.pontos} PARA O RECORDE`;
    } else sub = "FAÇA O PRIMEIRO RECORDE!";
    this.txt(ctx, sub, cx, y0 + 54, sub.length > 20 ? 11.5 : 13, corSub, "#000000");
  }

  /* ---------------------- a cesta (aro, rede) e as bolas em camadas */
  desenharCestaECamadas(ctx) {
    this.calcularRede();
    this.desenharBolasCamada(ctx, 0);
    this.desenharAro(ctx, false);
    this.desenharRede(ctx, false);
    this.desenharBolasCamada(ctx, 1);
    this.desenharRede(ctx, true);
    this.desenharAro(ctx, true);
  }

  // em que camada a bola está: 0 atrás do aro, 1 dentro, 2 na frente
  camada(b) {
    if (b.naRede) return 1;
    const dz = b.z - ZR;
    if (dz > R_ARO * 0.55) return 0;
    if (dz > -R_ARO * 0.8 && b.h < RB * 1.1 && b.h > -REDE - RB) return 1;
    return 2;
  }

  desenharBolasCamada(ctx, camada) {
    for (const b of this.bolas) {
      if (b.estado !== "voo" || this.camada(b) !== camada) continue;
      this.desenharBolaVoo(ctx, b);
    }
  }

  desenharBolaVoo(ctx, b) {
    const r = b.sr;
    const x = b.sx;
    const y = b.sy;
    ctx.save();
    ctx.globalAlpha = limitar(b.alfa, 0, 1);
    const cor = this.ehSlam ? (this.enterrada ? "#59ccff" : SL.laranja) : b.fogoBola ? SW.vermelho : b.ouroBola ? SW.amarelo : SW.laranja;
    const entra = limitar(b.tVoo * 8, 0, 1);
    if (!b.pontuou) {
      ctx.globalCompositeOperation = "lighter";
      // o rastro de luz atrás da bola (arremesso.gd)
      const vx = (b.sx - b.sxAnt) * 60;
      const vy = (b.sy - b.syAnt) * 60;
      const vel = Math.hypot(vx, vy);
      const rastro = this.ehSlam ? tingir(this.img.feixe, cor) : tingir(this.img.swishRastro, misturaCor(cor, "#ffffff", 0.25));
      if (rastro && vel > 30) {
        const comp = limitar(vel * 0.11, r * 1.6, r * 6.4);
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(Math.atan2(vx, -vy));
        ctx.globalAlpha = entra * 0.85 * b.alfa;
        if (this.ehSlam) ctx.drawImage(rastro, -r * 1.1, 0, r * 2.2, comp);
        else ctx.drawImage(rastro, -r * 0.95, 0, r * 1.9, comp);
        ctx.restore();
      }
      const halo = tingir(this.ehSlam ? this.img.brilho : this.img.swishBrilho, cor);
      if (halo) {
        ctx.globalAlpha = 0.32 * entra * b.alfa;
        ctx.drawImage(halo, x - r * 2.1, y - r * 2.1, r * 4.2, r * 4.2);
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = limitar(b.alfa, 0, 1);
    }
    desenharBola(ctx, this.folha, x, y, r, b.giro, b.ouroBola);
    ctx.restore();
  }

  // a rede: 16 fios em volta, 5 anéis (cesta.gd + rede_mola.shader)
  calcularRede() {
    const N = 16;
    const cx = this.aroTelaX();
    const r = this.rede;
    const est = limitar(r.estica, -0.3, 1.4);
    const balanco = Math.sin(this.tv * 2.2) * 2.2;
    // as bolas dentro da rede esticam os anéis em volta delas
    let bolaK = -10;
    let bolaR = 0;
    for (const b of this.bolas) {
      if (b.estado === "voo" && b.naRede && b.h < 0.05) {
        bolaK = limitar(-b.h / REDE, -0.2, 1.3) * 4;
        bolaR = b.sr;
      }
    }
    for (let k = 0; k < 5; k++) {
      const f = k / 4;
      let rx = this.aroRX * mix(1, 0.55, f) * (1 - 0.218 * f * Math.max(0, est));
      const ry = this.aroRY * mix(1, 0.5, f);
      const w = 1 - Math.abs(k - bolaK) / 1.5;
      if (w > 0) rx = Math.max(rx, mix(rx, bolaR * 1.12, w));
      const y = this.aroY + this.redeH * f * (1 + 0.35 * Math.max(0, est)) + r.bal * 13 * f * f;
      const desl = k % 2 ? 0.5 : 0;
      for (let i = 0; i < N; i++) {
        const a = ((i + desl) / N) * TAU;
        const onda = Math.sin(this.tv * 22 + f * 5 + i) * 7 * r.bal * f;
        this.redeX[k * N + i] = cx + Math.cos(a) * rx + balanco * f + onda;
        this.redeY[k * N + i] = y + Math.sin(a) * ry;
      }
    }
  }

  desenharRede(ctx, frente) {
    const N = 16;
    const X = this.redeX;
    const Y = this.redeY;
    ctx.save();
    ctx.beginPath();
    for (let k = 0; k < 4; k++) {
      const desl = k % 2 ? 0.5 : 0;
      for (let i = 0; i < N; i++) {
        const meio = Math.sin(((i + desl + 0.25) / N) * TAU);
        if ((meio > 0) !== frente) continue;
        const a = k * N + i;
        const b1 = (k + 1) * N + i;
        const b2 = (k + 1) * N + (k % 2 ? (i + 1) % N : (i - 1 + N) % N);
        ctx.moveTo(X[a], Y[a]);
        ctx.lineTo(X[b1], Y[b1]);
        ctx.moveTo(X[a], Y[a]);
        ctx.lineTo(X[b2], Y[b2]);
      }
    }
    if (frente) {
      for (let i = 0; i <= N / 2; i++) {
        const a = 4 * N + (i % N);
        if (i === 0) ctx.moveTo(X[a], Y[a]);
        else ctx.lineTo(X[a], Y[a]);
      }
    }
    const cor = this.ehSlam ? "#e6f2ff" : "#ffffff";
    if (this.ehSlam) ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    if (frente) {
      ctx.strokeStyle = rgba(cor, 0.16);
      ctx.lineWidth = 4.5;
      ctx.stroke();
    }
    ctx.strokeStyle = rgba(cor, frente ? 0.85 : 0.35);
    ctx.lineWidth = frente ? 1.5 : 1.1;
    ctx.stroke();
    ctx.restore();
  }

  desenharAro(ctx, frente) {
    const cx = this.aroTelaX();
    const cy = this.aroY;
    const rx = this.aroRX;
    const ry = this.aroRY;
    let cor = this.ehSlam ? (this.enterrada ? "#59ccff" : SL.laranja) : "#ff7314";
    if (!this.ehSlam && this.fogo > 0) cor = misturaCor("#ffbf33", "#ff8c33", 0.5 + 0.5 * Math.sin(this.tv * 20));
    ctx.save();
    if (!frente) {
      // o halo do aro e o suporte na tabela
      const halo = tingir(this.ehSlam ? this.img.brilho : this.img.swishBrilho, this.fogo > 0 ? "#ff4010" : cor);
      if (halo) {
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = (this.fogo > 0 ? 0.55 : 0.3) + Math.sin(this.tv * 3) * 0.08;
        ctx.drawImage(halo, cx - rx * 1.7, cy - ry * 3.2 + 10, rx * 3.4, ry * 6.4);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = "#1a1a24";
      ctx.fillRect(cx - 9, cy - ry - 7, 18, 7);
    }
    ctx.beginPath();
    if (frente) ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI);
    else ctx.ellipse(cx, cy, rx, ry, 0, Math.PI, TAU);
    ctx.lineCap = "round";
    ctx.strokeStyle = rgba(cor, frente ? 0.4 : 0.3);
    ctx.lineWidth = frente ? 10 : 8;
    ctx.stroke();
    ctx.strokeStyle = frente ? cor : misturaCor(cor, "#000000", 0.25);
    ctx.lineWidth = frente ? 4.6 : 3.6;
    ctx.stroke();
    if (frente) {
      ctx.beginPath();
      ctx.ellipse(cx, cy - 1.2, rx, ry, 0, 0.15, Math.PI - 0.15);
      ctx.strokeStyle = "rgba(255,242,204,0.85)";
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }
    ctx.restore();
  }

  desenharAneis(ctx, frente) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const a of this.aneis) {
      if (!a.vivo || !a.spr) continue;
      const k = a.t / a.dur;
      const s = 1 + k * a.cresce;
      ctx.globalAlpha = (1 - k) * a.alfa;
      ctx.drawImage(a.spr, a.x - a.rx * s * 1.16, a.y - a.ry * s * 1.16, a.rx * s * 2.32, a.ry * s * 2.32);
    }
    ctx.restore();
  }

  desenharRaios(ctx) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    for (const r of this.raios) {
      if (!r.vivo) continue;
      const fade = (1 - r.t / r.dur) * (0.75 + 0.25 * Math.random());
      const p = r.pts;
      const q = r.ramo;
      for (const [larg, alfa, branco] of [[10, 0.16, false], [4.5, 0.5, false], [1.7, 0.95, true]]) {
        ctx.beginPath();
        ctx.moveTo(p[0], p[1]);
        for (let i = 1; i < 17; i++) ctx.lineTo(p[i * 2], p[i * 2 + 1]);
        ctx.moveTo(q[0], q[1]);
        for (let i = 1; i < 9; i++) ctx.lineTo(q[i * 2], q[i * 2 + 1]);
        ctx.strokeStyle = branco ? `rgba(255,255,255,${alfa * fade})` : rgba(r.cor, alfa * fade);
        ctx.lineWidth = larg * r.esp;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  desenharCaindo(ctx) {
    for (const k of this.caindo) {
      if (!k.viva || k.espera > 0) continue;
      const s = k.s;
      const chaoX = 270 + k.x * s;
      const chaoY = 44 + 453 * s;
      const r = k.raio0 * s;
      const y = chaoY - k.h * s;
      const aparece = limitar(k.t / 0.12, 0, 1);
      // a sombra no chão: menor e mais fraca com a bola no alto
      const alto = limitar(k.h / 130, 0, 1);
      const sombra = tingir(this.img.brilho, "#000000");
      ctx.save();
      if (sombra) {
        const lado = r * 2.6 * (1 - alto * 0.4);
        ctx.globalAlpha = 0.6 * (1 - alto * 0.6) * aparece;
        ctx.drawImage(sombra, chaoX - lado / 2, chaoY + r * 0.15 - lado * 0.18, lado, lado * 0.36);
      }
      if (k.tipo !== "normal") {
        const halo = tingir(this.img.brilho, k.tipo === "fogo" ? "#59ccff" : SL.ouro);
        if (halo) {
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = 0.55 * aparece;
          ctx.drawImage(halo, chaoX - r * 2.1, y - r * 2.1, r * 4.2, r * 4.2);
          ctx.globalCompositeOperation = "source-over";
        }
      }
      ctx.globalAlpha = aparece;
      desenharBola(ctx, this.folha, chaoX, y, r * mix(0.6, 1, aparece), k.giro, k.tipo === "ouro");
      ctx.restore();
    }
  }

  /* --------------------------------- a bola na mão e as da rampa */
  desenharMaoEFila(ctx) {
    const c = this.cena;
    const rf = c.raioFila;
    // a rampa: um trilho de neon por onde as bolas voltam
    ctx.save();
    const cor = this.ehSlam ? CORES_FASE[this.fase] : SW.laranja;
    ctx.strokeStyle = rgba(cor, 0.35);
    ctx.lineWidth = 3;
    ctx.beginPath();
    const s0 = c.fila[0];
    ctx.moveTo(c.mao[0] + c.raioMao * 0.6, c.mao[1] + c.raioMao * 0.72);
    ctx.lineTo(s0[0], s0[1] + rf * 0.9);
    ctx.lineTo(this.LW + 10, s0[1] + rf * 0.9 + (this.ehSlam ? 26 : 12));
    ctx.stroke();
    ctx.restore();
    for (let i = this.fila.length - 1; i >= 0; i--) {
      const b = this.fila[i];
      if (b.sx - rf > this.LW) continue;
      desenharBola(ctx, this.folha, b.sx, b.sy, rf, b.giro, !this.ehSlam && this.sprint && this.estado === "jogando");
    }
    const b = this.mao;
    if (!b) return;
    const ch = saiDeTras(b.chega);
    let x = mix(b.deX, c.mao[0], ch);
    let y = mix(b.deY, c.mao[1], ch);
    let r = mix(rf, c.raioMao, Math.min(1, b.chega));
    const a = this.arrasto;
    if (a) {
      // a bola acompanha o dedo (um pouco, como se fosse levantada)
      let dx = a.x - a.x0;
      let dy = a.y - a.y0;
      const L = Math.hypot(dx, dy);
      const max = this.ehSlam ? 95 : 70;
      if (L > max) {
        dx = (dx / L) * max;
        dy = (dy / L) * max;
      }
      x += dx * 0.9;
      y += dy * 0.9;
    }
    b.px = x;
    b.py = y;
    // o brilho de "pegue a bola"
    const halo = tingir(this.ehSlam ? this.img.brilho : this.img.swishBrilho, this.ehSlam ? SL.laranja : SW.laranja);
    if (halo) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.28 + 0.12 * Math.sin(this.tv * 4);
      ctx.drawImage(halo, x - r * 1.9, y - r * 1.9, r * 3.8, r * 3.8);
      ctx.restore();
    }
    const ouroMao = !this.ehSlam && this.sprint && this.estado === "jogando";
    desenharBola(ctx, this.folha, x, y, r, b.giro, ouroMao);
    // medidor de força enquanto arrasta (anel em volta da bola)
    if (a) {
      const D = Math.max(0, a.y0 - a.y);
      const p = D / c.dIdeal;
      if (D > 12) {
        const fr = limitar(p / 1.6, 0, 1);
        ctx.save();
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.arc(x, y, r + 9, -Math.PI / 2, -Math.PI / 2 + TAU);
        ctx.strokeStyle = "rgba(255,255,255,0.12)";
        ctx.lineWidth = 5;
        ctx.stroke();
        // a faixa certa
        ctx.beginPath();
        ctx.arc(x, y, r + 9, -Math.PI / 2 + (0.9 / 1.6) * TAU, -Math.PI / 2 + (1.1 / 1.6) * TAU);
        ctx.strokeStyle = "rgba(77,255,128,0.35)";
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y, r + 9, -Math.PI / 2, -Math.PI / 2 + fr * TAU);
        ctx.strokeStyle = p >= 0.9 && p <= 1.1 ? "#4dff80" : p < 0.9 ? "#ffcc33" : "#ff5a3d";
        ctx.stroke();
        ctx.restore();
      }
    }
    // teclado: a seta da mira e o medidor de força
    if (this.usouTeclado && this.podeArremessar()) {
      ctx.save();
      ctx.translate(x, y - r - 8);
      ctx.rotate(this.mira);
      ctx.strokeStyle = "rgba(255,255,255,0.7)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(0, -46);
      ctx.moveTo(-8, -36);
      ctx.lineTo(0, -48);
      ctx.lineTo(8, -36);
      ctx.stroke();
      ctx.restore();
      if (this.teclas.carga) {
        const p = this.potenciaTeclado() / 1.6;
        const bx = x + r + 16;
        const by = y + r * 0.6;
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(bx, by - 100, 12, 100);
        ctx.fillStyle = "rgba(77,255,128,0.35)";
        ctx.fillRect(bx, by - 100 * (1.1 / 1.6), 12, 100 * (0.2 / 1.6));
        ctx.fillStyle = "#ffcc33";
        ctx.fillRect(bx + 2, by - 100 * p, 8, 100 * p);
      }
    }
    // a dica até o primeiro arremesso
    if (this.arremessos === 0 && !a && this.podeArremessar()) {
      const k = fract(this.tv * 1.2);
      ctx.save();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 4;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      for (let i = 0; i < 3; i++) {
        const t = fract(k + i / 3);
        const yy = y - r - 18 - t * (this.ehSlam ? 110 : 90);
        ctx.globalAlpha = Math.sin(t * Math.PI) * 0.9;
        ctx.beginPath();
        ctx.moveTo(x - 16, yy + 9);
        ctx.lineTo(x, yy);
        ctx.lineTo(x + 16, yy + 9);
        ctx.stroke();
      }
      ctx.restore();
      if (this.ehSlam) this.txt(ctx, "ARRASTE A BOLA PARA CIMA E SOLTE", 270, 772, 15, "#ffffff", "#000000");
      else this.txt(ctx, "ARRASTE A BOLA PARA CIMA E SOLTE", 480, 222, 16, "#ffffff", "#000000");
    }
  }

  desenharFlutuantes(ctx) {
    for (const f of this.flutuantes) {
      if (!f.vivo || f.t < 0) continue;
      const t = f.t;
      let esc = 1;
      if (t < 0.25) esc = 0.5 + 0.5 * saiDeTras(t / 0.25);
      else if (t > 0.75) esc = Math.max(0, 1 - (t - 0.75) / 0.2);
      if (esc <= 0.02) continue;
      const y = f.y - f.sobe * Math.sin((Math.min(1, t / 0.95) * Math.PI) / 2);
      if (f.corTexto) this.txt(ctx, f.txt, f.x, y, f.tam * esc, f.cor, "rgba(0,0,0,0.75)");
      else this.txt(ctx, f.txt, f.x, y, f.tam * esc, "#ffffff", f.cor);
    }
  }

  comboSlam(ctx) {
    const c = this.comboTxt;
    if (!c) return;
    let esc;
    if (c.t < 0.18) esc = 0.35 + 0.7 * saiDeTras(c.t / 0.18);
    else if (c.t < 0.6) esc = 1.05;
    else esc = Math.max(0, 1.05 * (1 - (c.t - 0.6) / 0.16));
    if (esc <= 0.02) return;
    ctx.save();
    ctx.translate(270, 592);
    ctx.rotate(c.rot);
    ctx.scale(esc, esc);
    const tam = c.txt.length > 13 ? 44 : 54;
    this.txt(ctx, c.txt, 0, 0, tam, c.cor, c.contorno);
    if (c.swish) this.txt(ctx, "SWISH!", 0, 44, 22, "#ffffff", SL.ciano);
    ctx.restore();
  }

  avisoSlam(ctx) {
    const a = this.av;
    if (!a) return;
    let sx;
    let sy;
    if (a.t < 0.3) {
      const k = saiDeTras(a.t / 0.3);
      sx = mix(0.6, 1, k);
      sy = mix(0.05, 1, k);
    } else if (a.t < 0.3 + a.dur) {
      sx = 1;
      sy = 1;
    } else {
      const k = limitar((a.t - 0.3 - a.dur) / 0.2, 0, 1);
      sx = mix(1, 1.04, k);
      sy = 1 - k;
    }
    if (sy <= 0.01) return;
    ctx.save();
    ctx.translate(270, 692);
    ctx.scale(sx, sy);
    ctx.beginPath();
    caminhoArredondado(ctx, -232, -40, 464, 80, 14);
    ctx.fillStyle = rgba(misturaCor(a.cor, "#000000", 0.82), 0.9);
    ctx.fill();
    ctx.strokeStyle = rgba(a.cor, 0.35);
    ctx.lineWidth = 10;
    ctx.stroke();
    ctx.strokeStyle = a.cor;
    ctx.lineWidth = 3;
    ctx.stroke();
    const tam = Math.min(33, 440 / (a.txt.length * 0.66));
    this.txt(ctx, a.txt, 0, 1, tam, "#ffffff", a.cor);
    ctx.restore();
  }

  bordaRecorde(ctx) {
    if (this.borda <= 0.01) return;
    const k = this.borda;
    const a = k > 0.6 ? (Math.sin((1 - k) * 25) > 0 ? 1 : 0.3) : k / 0.6;
    ctx.save();
    ctx.strokeStyle = rgba(SL.ouro, a * 0.8);
    ctx.lineWidth = 14;
    ctx.strokeRect(7, 7, this.LW - 14, this.LH - 14);
    ctx.restore();
  }

  /* Slam: antes da primeira cesta a arena está "desligada" */
  aquecerSlam(ctx) {
    if (this.estado !== "aquece") return;
    const aura = tingir(this.img.slamAura, SL.laranja);
    ctx.save();
    if (aura) {
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.16 + 0.06 * Math.sin(this.tv * 2);
      ctx.drawImage(aura, 270 - 150, 470, 300, 392);
      ctx.globalCompositeOperation = "source-over";
    }
    ctx.restore();
    const pulso = 1 + 0.05 * Math.sin(this.tv * 5);
    ctx.save();
    ctx.translate(270, 590);
    ctx.scale(pulso, pulso);
    this.txt(ctx, "ACERTE A CESTA", 0, 0, 40, "#ffffff", SL.laranja);
    this.txt(ctx, "PARA LIGAR A ARENA!", 0, 38, 22, SL.laranjaClaro, "#000000");
    ctx.restore();
  }

  /* O MAPA DAS FASES: abre cada fase (sozinho; um toque pula). */
  mapaSlam(ctx) {
    const m = this.mapa;
    if (!m) return;
    const i = this.fase;
    const cor = CORES_FASE[i];
    const entra = 1 - Math.pow(1 - limitar(m.t / 0.25, 0, 1), 3);
    const sai = m.sai > 0 ? Math.pow(limitar(m.sai / 0.24, 0, 1), 2) : 0;
    const dy = (1 - entra) * 960 - sai * 960;
    ctx.save();
    ctx.fillStyle = `rgba(0,0,0,${0.78 * (1 - sai)})`;
    ctx.fillRect(0, 0, 540, 960);
    ctx.translate(0, dy);
    ctx.beginPath();
    caminhoArredondado(ctx, 30, 235, 480, 450, 18);
    ctx.fillStyle = rgba(misturaCor(cor, "#000000", 0.88), 0.96);
    ctx.fill();
    ctx.strokeStyle = rgba(cor, 0.35);
    ctx.lineWidth = 12;
    ctx.stroke();
    ctx.strokeStyle = cor;
    ctx.lineWidth = 3;
    ctx.stroke();
    // o nome da fase entra batendo
    const tt = limitar((m.t - 0.08) / 0.32, 0, 1);
    const esc = tt <= 0 ? 2.6 : mix(2.6, 1, saiDeTras(tt));
    ctx.save();
    ctx.translate(270, 292);
    ctx.scale(esc, esc);
    this.txt(ctx, this.regras.nomes[i], 0, 0, 62, "#ffffff", cor);
    ctx.restore();
    const R = this.regras;
    const final = i === 2;
    this.txt(ctx, final ? "SEM META: FAÇA O MÁXIMO!" : `FAÇA ${R.metas[i]} PONTOS EM ${R.tempos[i]} SEGUNDOS`, 270, 345, 19, SL.laranjaClaro, "#000000");
    for (let k = 0; k < 3; k++) {
      const x = 47 + k * 153;
      const y = 378;
      const ck = CORES_FASE[k];
      let corCard = ck;
      let status = "DEPOIS";
      let corStatus = "#b3b3bf";
      let tom = 0.6;
      if (k < i) {
        corCard = SL.verde;
        status = `OK  ${this.pontosFase[k]} PTS`;
        corStatus = SL.verde;
        tom = 0.75;
      } else if (k === i) {
        status = "AGORA!";
        corStatus = "#ffffff";
        tom = 1;
      }
      let pop = 1;
      if (k === i && m.t > 0.42 && m.t < 0.76) pop = 1 + 0.1 * Math.sin(((m.t - 0.42) / 0.34) * Math.PI);
      ctx.save();
      ctx.translate(x + 70, y + 75);
      ctx.scale(pop, pop);
      ctx.globalAlpha = tom;
      ctx.beginPath();
      caminhoArredondado(ctx, -70, -75, 140, 150, 13);
      ctx.fillStyle = rgba(misturaCor(corCard, "#000000", 0.85), 0.9);
      ctx.fill();
      ctx.strokeStyle = corCard;
      ctx.lineWidth = k === i ? 3 : 1.5;
      ctx.stroke();
      this.txt(ctx, R.nomes[k], 0, -51, 18, ck, "#000000");
      this.txt(ctx, k < 2 ? `META ${R.metas[k]}` : "VALE TUDO", 0, -12, 20, "#ffffff", "#000000");
      this.txt(ctx, `${R.tempos[k]} SEGUNDOS`, 0, 19, 13.5, "#d9e0f2", "#000000");
      this.txt(ctx, status, 0, 50, 16, corStatus, "#000000");
      ctx.restore();
    }
    const info = final ? ["FINAL: MULTIPLICADOR TURBINADO!", "COMEÇA EM x2  •  MODO ENTERRADA COM 6 SEGUIDAS"]
      : i === 0 ? ["CESTAS SEGUIDAS MULTIPLICAM OS PONTOS", "x2  •  x3  •  x4 = MODO ENTERRADA"]
        : [`META ${this.alvo}  •  VOCÊ TEM ${this.pontos} PONTOS`, "BATA A META PARA CHEGAR NA FINAL"];
    this.txt(ctx, info[0], 270, 566, 15, "#ebebf5", "#000000");
    this.txt(ctx, info[1], 270, 588, 13, "#ebebf5", "#000000");
    if (final) this.txt(ctx, "NA FINAL O ARO ANDA!", 270, 614, 15, SL.ciano, "#000000");
    const p = 0.8 + 0.2 * (0.5 + 0.5 * Math.sin(this.tv * 6));
    ctx.globalAlpha = p;
    this.txt(ctx, "PREPARE-SE!", 270, 652, 31, "#ffffff", cor);
    ctx.restore();
  }

  contagemTela(ctx) {
    const c = this.contagem;
    if (!c) return;
    const cx = this.LW / 2;
    const cy = this.ehSlam ? 480 : 232;
    const tam = this.ehSlam ? 165 : 150;
    ctx.save();
    if (c.vai > 0) {
      const t = c.vai;
      let esc = t < 0.26 ? mix(0.6, 1.12, saiDeTras(t / 0.26)) : t < 0.48 ? 1.12 : Math.max(0, 1.12 * (1 - (t - 0.48) / 0.2));
      if (esc > 0.02) {
        ctx.translate(cx, cy);
        ctx.scale(esc, esc);
        this.txt(ctx, "VAI!", 0, 0, tam * 0.75, "#ffffff", this.ehSlam ? "#000000" : SW.verde);
      }
      ctx.restore();
      return;
    }
    if (this.estado !== "contagem" || c.n <= 0) {
      ctx.restore();
      return;
    }
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, this.LW, this.LH);
    const t = c.t;
    let esc = t < 0.3 ? mix(0.3, 1, saiDeTras(t / 0.3)) : t > 0.41 ? Math.max(0, 1 - (t - 0.41) / 0.14) : 1;
    const prog = (3 - c.n) / 2;
    const cor = this.ehSlam ? misturaCor(CORES_FASE[this.fase], "#ff4005", prog * 0.6) : SW.amarelo;
    ctx.translate(cx, cy);
    ctx.scale(esc, esc);
    this.txt(ctx, String(c.n), 0, 0, tam, "#ffffff", cor);
    ctx.restore();
  }

  /* ================================================== SWISH ARENA === */
  desenharSwish(ctx) {
    const [tx, ty] = this.tremido();
    // a ARENA (fundo, tabela, aro) dá o "zoom" de impacto e treme; o
    // placar e os textos ficam firmes
    let z = 0;
    if (this.zoomT < 0.33 && !this.reduzido) {
      z = this.zoomT < 0.07 ? (this.zoomT / 0.07) * this.zoomForca : this.zoomForca * (1 - saiDeTras((this.zoomT - 0.07) / 0.26));
    }
    ctx.save();
    ctx.translate(480 + tx, 452 + ty);
    ctx.scale(1 + z, 1 + z);
    ctx.translate(-480, -452);
    if (this.img.swishFundo) ctx.drawImage(this.img.swishFundo, 0, 0, 960, 540);
    else {
      ctx.fillStyle = "#0a0518";
      ctx.fillRect(0, 0, 960, 540);
    }
    this.neonSwish(ctx);
    this.lampadasSwish(ctx);
    this.letreiroSwish(ctx);
    this.fachosSwish(ctx);
    this.tabelaSwish(ctx);
    this.desenharCestaECamadas(ctx);
    this.desenharAneis(ctx, true);
    this.raiosNoAro(ctx);
    ctx.restore();
    if (this.clarao > 0.01) {
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = rgba(this.claraoCor, this.clarao);
      ctx.fillRect(0, 0, 960, 540);
      ctx.restore();
    }
    this.hudSwish(ctx);
    this.fx.desenhar(ctx, true);
    this.desenharBolasCamada(ctx, 2);
    this.fx.desenhar(ctx, false);
    this.desenharMaoEFila(ctx);
    this.desenharFlutuantes(ctx);
    this.avisoSwish(ctx);
    this.faixaSwish(ctx);
    this.contagemTela(ctx);
  }

  neonSwish(ctx) {
    const mascara = this.img.swishNeon;
    if (!mascara) return;
    const g = this.neonCtx;
    const desl = ((this.faseOnda / TAU) * 96) % 96;
    g.globalCompositeOperation = "copy";
    g.drawImage(this.fogo > 0 ? this.neonListrasFogo : this.neonListras, desl - 96, 0);
    g.globalCompositeOperation = "multiply";
    g.drawImage(mascara, 0, 0, 480, 270);
    g.globalCompositeOperation = "source-over";
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.drawImage(this.neonTela, 0, 0, 960, 540);
    ctx.restore();
  }

  lampadasSwish(ctx) {
    const fogo = this.fogo > 0;
    const glow = tingir(this.img.swishBrilho, fogo ? "#ff7333" : "#ffdb73");
    const miolo = this.img.swishBrilho;
    if (!glow) return;
    const forca = fogo ? 1.35 : 1;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const [x, y, i] of this.lampadas) {
      const seq = fract((i + 0.42) / 3 - this.faseLampada);
      const acesa = suave(0.56, 0.66, seq) * (1 - suave(0.92, 1, seq));
      if (acesa < 0.03) continue;
      ctx.globalAlpha = Math.min(1, acesa * forca);
      ctx.drawImage(glow, x - 17, y - 17, 34, 34);
      ctx.globalAlpha = acesa * 0.7;
      ctx.drawImage(miolo, x - 6, y - 6, 12, 12);
    }
    ctx.restore();
  }

  letreiroSwish(ctx) {
    const L = this.letreiro;
    if (!L) return;
    const JANELAS = [[38, 314], [647, 923]];
    for (const [x0, x1] of JANELAS) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(x0, 365, x1 - x0, L.ALT);
      ctx.clip();
      // a mesma faixa para as duas janelas: some atrás da tabela de uma e
      // volta na outra
      let x = x0 + (modPos(923 - x0 - this.andado, L.L) - L.L);
      while (x < x1) {
        ctx.drawImage(L.tela, x, 365, L.L, L.ALT);
        x += L.L;
      }
      ctx.restore();
    }
  }

  fachosSwish(ctx) {
    if (!this.coneFacho) return;
    const fontes = [[90, 24, "#ffebbf"], [280, 24, "#a666ff"], [680, 24, "#ff9940"], [870, 24, "#ffebbf"]];
    const intens = this.fogo > 0 ? 2.2 : 1;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    fontes.forEach(([x, y, cor], i) => {
      const spr = tingir(this.coneFacho, cor);
      ctx.globalAlpha = (0.16 + 0.06 * Math.sin(this.tv * 1.3 + i * 1.7)) * Math.min(intens, 1.8);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.sin(this.tv * 0.45 + i * 1.9) * 0.26);
      ctx.drawImage(spr, -100, 0, 200, 520);
      ctx.restore();
    });
    ctx.restore();
  }

  // a tabela de vidro da arte acende a cada cesta (no EM CHAMAS pulsa laranja)
  tabelaSwish(ctx) {
    let a = this.tabelaBrilho;
    let cor = this.tabelaCor;
    if (this.fogo > 0) {
      const base = 0.28 + 0.12 * Math.sin(this.tv * 9);
      if (a < base) {
        a = base;
        cor = "#ff7319";
      }
    }
    if (a <= 0.01) return;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.beginPath();
    caminhoArredondado(ctx, 322, 236, 316, 238, 7);
    ctx.moveTo(408, 346);
    ctx.rect(408, 346, 145, 102);
    ctx.strokeStyle = rgba(cor, 0.3 * a);
    ctx.lineWidth = 22;
    ctx.stroke();
    ctx.strokeStyle = rgba(cor, 0.85 * a);
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();
  }

  raiosNoAro(ctx) {
    const r = this.raiosSwish;
    if (!r || !this.img.swishRaios) return;
    const k = r.t / 0.5;
    const s = mix(0.5, 2.3, 1 - Math.pow(1 - k, 3));
    const spr = tingir(this.img.swishRaios, r.cor);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = (1 - k) * (1 - k);
    ctx.translate(this.aroTelaX(), this.aroY - 4);
    ctx.rotate(r.giro * k);
    const w = 256 * s * 1.25 * 0.75;
    const h = 256 * s * 0.85 * 0.75;
    ctx.drawImage(spr, -w / 2, -h / 2, w, h);
    ctx.restore();
  }

  painel(ctx, x, y, w, h, cor, raio = 16, fundo = "rgba(10,5,26,0.8)") {
    ctx.beginPath();
    caminhoArredondado(ctx, x, y, w, h, raio);
    ctx.fillStyle = fundo;
    ctx.fill();
    ctx.strokeStyle = rgba(cor, 0.25);
    ctx.lineWidth = 9;
    ctx.stroke();
    ctx.strokeStyle = cor;
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }

  hudSwish(ctx) {
    const R = this.regras;
    const f = this.fase;
    const final = f === 2;
    const fogo = this.fogo > 0;
    // FASE + META (esquerda)
    const corFase = this.metaBatida && !final ? SW.verde : SW.roxo;
    this.painel(ctx, 18, 12, 192, 140, corFase);
    this.txt(ctx, final ? "FINAL" : `FASE ${f + 1}`, 114, 46, 34, "#ffffff", "#140a33");
    this.txt(ctx, final ? "VALENDO TUDO!" : `META ${R.metas[f]}`, 114, 82, 15.5, SW.ciano, "#00141a");
    const bx = 36;
    const by = 100;
    const bw = 156;
    const bh = 26;
    ctx.beginPath();
    caminhoArredondado(ctx, bx, by, bw, bh, 13);
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    ctx.fill();
    const meta = final ? 0 : R.metas[f];
    const fr = final ? 1 : limitar(this.pontosFase[f] / meta, 0, 1);
    if (fr > 0) {
      ctx.save();
      ctx.beginPath();
      caminhoArredondado(ctx, bx, by, bw, bh, 13);
      ctx.clip();
      const gr = ctx.createLinearGradient(bx, 0, bx + bw, 0);
      gr.addColorStop(0, final ? SW.rosa : SW.ciano);
      gr.addColorStop(1, final ? SW.amarelo : SW.verde);
      ctx.fillStyle = gr;
      ctx.fillRect(bx, by, bw * fr, bh);
      ctx.restore();
    }
    this.txt(ctx, final ? `${this.pontosFase[f]} PTS` : `${Math.min(this.pontosFase[f], 999)} / ${meta}`, bx + bw / 2, by + bh / 2 + 1, 14, "#ffffff", "#000000");

    // PLACAR CENTRAL: o LED gigante
    const corPlacar = fogo ? SW.vermelho : SW.laranja;
    const pop = 1 + (this.popPontos || 0) * 0.06;
    ctx.save();
    ctx.translate(480, 82);
    ctx.scale(pop, pop);
    ctx.translate(-480, -82);
    this.painel(ctx, 225, 12, 510, 140, corPlacar);
    ctx.restore();
    this.txt(ctx, "PONTOS", 480, 30, 16, SW.amarelo, "#1a1000");
    led(ctx, numeroLed(this.pontos, 6), 480, 92, 68, fogo ? SW.amarelo : SW.laranja);

    // TEMPO (direita): o anel e os números
    const sprint = this.sprint && this.estado === "jogando";
    const corTempo = sprint ? SW.vermelho : SW.verde;
    this.painel(ctx, 750, 12, 192, 140, corTempo);
    const cx = 846;
    const cy = 82;
    const frac = this.estado === "jogando" ? this.tempo / this.total : this.estado === "fimFase" || this.estado === "fim" ? 0 : 1;
    ctx.save();
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.arc(cx, cy, 54, 0, TAU);
    ctx.strokeStyle = "rgba(255,255,255,0.09)";
    ctx.lineWidth = 9;
    ctx.stroke();
    if (frac > 0.001) {
      const corArco = frac > 0.5 ? SW.verde : frac > 0.25 ? SW.amarelo : SW.vermelho;
      const a1 = -Math.PI / 2 + frac * TAU;
      ctx.beginPath();
      ctx.arc(cx, cy, 54, -Math.PI / 2, a1);
      ctx.strokeStyle = rgba(corArco, 0.3);
      ctx.lineWidth = 15;
      ctx.stroke();
      ctx.strokeStyle = corArco;
      ctx.lineWidth = 8;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(cx + Math.cos(a1) * 54, cy + Math.sin(a1) * 54, 5, 0, TAU);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
    }
    ctx.restore();
    const seg = this.estado === "jogando" ? Math.ceil(this.tempo) : this.estado === "fimFase" || this.estado === "fim" ? 0 : this.total;
    const piscar = sprint && seg <= 5 ? 0.6 + 0.4 * Math.abs(Math.sin(this.tv * 6)) : 1;
    ctx.save();
    ctx.globalAlpha = piscar;
    led(ctx, numeroLed(seg, 2), cx, cy + 2, 40, sprint ? SW.vermelho : "#ffffff");
    ctx.restore();

    // CHIPS (embaixo do placar): COMBO, EM CHAMAS, CESTA VALE 3
    this.chip(ctx, 225, 160, `COMBO x${Math.max(this.combo, 2)}`, SW.ciano, this.chips.combo, this.popChipCombo || 0);
    this.chip(ctx, 399, 160, "EM CHAMAS x2", SW.vermelho, this.chips.fogo, 0);
    this.chip(ctx, 573, 160, `CESTA VALE ${R.sprint}`, SW.amarelo, this.chips.sprint, 0);

    // RECORDE e CESTAS (embaixo, nas laterais)
    const corRec = this.recordeVivo ? SW.rosa : SW.amarelo;
    this.painel(ctx, 40, 400, 176, 78, corRec, 14, "rgba(10,5,26,0.7)");
    if (this.img.coroa) ctx.drawImage(this.img.coroa, 54, 405, 26, 18.7);
    this.txt(ctx, "RECORDE", 134, 415, 13, SW.amarelo, "#1a1000");
    led(ctx, numeroLed(this.recordeVivo ? this.pontos : this.recordeAntigo, 4), 128, 451, 32, SW.amarelo);
    this.painel(ctx, 744, 400, 176, 78, SW.ciano, 14, "rgba(10,5,26,0.7)");
    this.txt(ctx, "CESTAS", 832, 415, 13, SW.ciano, "#00141a");
    const pc = 1 + (this.popCestas || 0) * 0.3;
    this.txt(ctx, String(this.cestas), 832, 452, 38 * pc, "#ffffff", "#000000");
  }

  chip(ctx, x, y, texto, cor, estado, pop) {
    if (estado === 0) return;
    let esc = 1;
    if (estado > 0 && estado < 1) esc = saiDeTras(estado);
    if (estado < 0) esc = Math.max(0, -estado / 0.3);
    esc *= 1 + pop * 0.12;
    if (esc <= 0.02) return;
    ctx.save();
    ctx.translate(x + 81, y + 17);
    ctx.scale(esc, esc);
    ctx.beginPath();
    caminhoArredondado(ctx, -81, -17, 162, 34, 17);
    ctx.fillStyle = rgba(misturaCor(cor, "#000000", 0.75), 0.92);
    ctx.fill();
    ctx.strokeStyle = rgba(cor, 0.4);
    ctx.lineWidth = 8;
    ctx.stroke();
    ctx.strokeStyle = cor;
    ctx.lineWidth = 2;
    ctx.stroke();
    this.txt(ctx, texto, 0, 1, 15, misturaCor(cor, "#ffffff", 0.35), "#000000");
    ctx.restore();
  }

  avisoSwish(ctx) {
    const a = this.av;
    if (!a) return;
    let esc;
    if (a.t < 0.3) esc = mix(0.3, 1, 1 - Math.pow(1 - a.t / 0.3, 4));
    else if (a.t < a.dur - 0.2) esc = 1;
    else esc = Math.max(0, 1 - (a.t - (a.dur - 0.2)) / 0.2);
    if (a.t > a.dur) esc = 0;
    if (esc <= 0.02) return;
    ctx.save();
    ctx.translate(480, 289);
    ctx.scale(esc, esc);
    this.txt(ctx, a.txt, 0, 0, a.grande ? 66 : 54, a.cor, "rgba(0,0,0,0.85)");
    ctx.restore();
  }

  // a faixa grande no meio da tela: título + subtítulo (partida.gd: _banner)
  faixaSwish(ctx) {
    const f = this.faixa;
    if (!f) return;
    const t = f.t;
    let sy = 1;
    if (t < 0.28) sy = 1 - Math.pow(1 - t / 0.28, 4);
    else if (t > f.dur) sy = Math.max(0, 1 - (t - f.dur) / 0.25);
    if (sy <= 0.01) return;
    const k1 = 1 - Math.pow(1 - limitar((t - 0.1) / 0.45, 0, 1), 5);
    const k2 = 1 - Math.pow(1 - limitar((t - 0.18) / 0.45, 0, 1), 5);
    ctx.save();
    ctx.translate(0, 270);
    ctx.scale(1, sy);
    ctx.fillStyle = rgba(misturaCor(f.cor, "#000000", 0.65), 0.92);
    ctx.fillRect(0, -82, 960, 165);
    ctx.fillStyle = f.cor;
    ctx.fillRect(0, -82, 960, 4);
    ctx.fillRect(0, 79, 960, 4);
    this.txt(ctx, f.titulo, 480 + (1 - k1) * -675, -18, 76, "#ffffff", "#000000");
    this.txt(ctx, f.sub, 480 + (1 - k2) * 675, 50, 24, misturaCor(f.cor, "#ffffff", 0.5), "#000000");
    ctx.restore();
  }
}

/* ======================================================================
   O MÓDULO
   ====================================================================== */

/* O console copia este objeto ao carregar (com largura/altura já lidas) e
   reaproveita a cópia quando a outra quadra abre. Ao criar uma partida a
   cópia passa a perguntar o tamanho à página também, como o original; se
   não der, a partida se encaixa na tela que vier. */
function ensinarTamanho(copia) {
  if (!copia || typeof copia !== "object") return;
  try {
    [["largura", 0], ["altura", 1]].forEach(([nome, i]) => {
      const atual = Object.getOwnPropertyDescriptor(copia, nome);
      if (atual && atual.get) return;
      Object.defineProperty(copia, nome, { get: () => tamanhoDaPagina(i), configurable: true, enumerable: true });
    });
  } catch (erro) { /* objeto travado: o encaixe da partida resolve */ }
}

export default {
  get largura() { return tamanhoDaPagina(0); },
  get altura() { return tamanhoDaPagina(1); },
  artes: ARTES,
  criar(api) {
    ensinarTamanho(this);
    return new Partida(api);
  },
};
