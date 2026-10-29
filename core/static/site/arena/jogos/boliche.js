/* ======================================================================
   BOLICHE — um motor, três pistas (api.variante):

     "strike-kids"  Strike Kids: o boliche infantil do Bob e da Mia. Pista
                    de madeira com trilha de estrelas, para-choques de doce,
                    pinos com carinha, um cenário por rodada e os letreiros
                    do jogo (STRIKE!, SPARE!, BOA!, UAU!, SUPER!, QUASE!,
                    OPS!, PEGANDO FOGO!). Placar da máquina: 10 por pino,
                    +50 no strike e +20 no spare.
     "dragon"       Dragon Bowling: a pista do dragão, a bola roxa e os
                    quadros de queda dos pinos. STRIKE / ACERTO / PRA FORA
                    no telão, mapa dos pinos, e a "bolinha do meio": rack
                    cheio acertado no centro do pino 1 é strike garantido.
     "dragon2"      Dragon Bowling 2: bola azul marmorizada com rastro azul e
                    dourado, tranco de câmera, faíscas e anel de choque. O
                    centro nem sempre é strike: o destino é sorteado no
                    impacto (DESTINOS_DO_MEIO do game.gd), um vizinho pode
                    cair "de tabela" e aparecem SPLIT! e QUASE!.

   COMO FUNCIONA

   O jogo acontece num MUNDO plano visto de cima: a pista tem 1 de largura
   (x de -0,5 a 0,5) e a bola sai de z = 0 rumo aos pinos (z cresce para o
   fundo). Bola e pinos são círculos que se empurram (impulso com massa e
   quique); o pino que leva um tranco acima do limiar tomba na direção do
   golpe, escorrega, a "cabeça" dele bate nos vizinhos (reação em cadeia),
   deita e some. Só o DESENHO é em perspectiva: cada variante diz em que
   altura da tela fica cada z e qual a largura da pista em cada altura (no
   Dragon, medida na própria arte da pista).

   A jogada: arraste a bola (para os lados escolhe de onde lançar) e solte
   com um gesto para cima. A direção do gesto é a mira, a velocidade é a
   força e a curva do gesto vira efeito (a bola "engancha" no fim da pista).
   Teclado: ← → posicionam, A D miram e Espaço lança.

   Partida: 5 rodadas de até 2 bolas. No Dragon a conta é a do boliche de
   verdade (strike soma as 2 bolas seguintes, spare a seguinte, e a última
   rodada ganha as bolas de bônus).

   As artes são carregadas aqui mesmo (e não por `artes`), por variante:
   quem abre o Strike Kids não baixa a pista do dragão.
   ====================================================================== */

const PASTA = new URL("./boliche/", import.meta.url);
const TAU = Math.PI * 2;
const PASSO = 1 / 240;          // passo da física (bola rápida não atravessa pino)
const DUR_QUEDA = 0.34;         // segundos do pino tombando até deitar
const TEMPO_DEITADO = 0.8;      // deitado, ainda escorrega um pouco antes de sumir
const EM_PE = 0;
const CAINDO = 1;
const FORA = 2;

const lim = (v, a, b) => (v < a ? a : v > b ? b : v);
const mistura = (a, b, t) => a + (b - a) * t;
const suave = (t) => t * t * (3 - 2 * t);
// TRANS_BACK + EASE_OUT do Godot: passa do ponto e volta
const voltaElastica = (t) => {
  const s = 1.70158;
  const u = t - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};

/* ----------------------------------------------------------------------
   AS TRÊS PISTAS
   geo:  medidas no mundo (largura da pista = 1)
   tela: onde o mundo cai na tela -- y0 é a bola em repouso, y1 o pino 1,
         y2 a última fileira; a largura da pista na altura y é k*(y - yV)
   tempos: segundos da bola até o pino 1, no talo e no fraquinho
   ---------------------------------------------------------------------- */
const VARIANTES = {
  "strike-kids": {
    tipo: "kids",
    // medidas do Strike Kids (scripts/medidas.gd) divididas pela largura da
    // pista com as bordas (1,35 m): pinos a 0,38 m, fileiras a 0,329 m,
    // barriga do pino 0,083 m, bola de 0,14 m e para-choques até perto dos pinos
    geo: {
      zPino1: 1.6, espaco: 0.281, fileira: 0.244, raioPino: 0.062, raioBola: 0.1,
      alturaPino: 0.34, massaBola: 6, limiarQueda: 0.26, calha: 0.085,
      bumper: 0.5, fimBumper: 1.32, expBola: 0.8,
    },
    tela: { y0: 850, y1: 470, y2: 350, cx: 270, k: 0.349, yV: -272 },
    tempos: [0.7, 1.75],
    sensMira: 0.45,
    quadros: 5,
    assistencia: "tabela",
  },
  dragon: {
    tipo: "dragon",
    geo: {
      zPino1: 1.2, espaco: 0.17, fileira: 0.147, raioPino: 0.043, raioBola: 0.05,
      alturaPino: 0.24, massaBola: 4.6, limiarQueda: 0.22, calha: 0.1,
      bumper: 0, fimBumper: 0, expBola: 0.6,
    },
    // a pista da arte (ball-new.png) medida pixel a pixel: centro em 270 e
    // bordas da madeira convergindo para y = 168 (largura = 1,319 * (y - 168))
    tela: { y0: 845, y1: 465, y2: 355, cx: 270, k: 1.319, yV: 168 },
    tempos: [0.65, 1.5],
    sensMira: 0.9,
    quadros: 5,
    assistencia: "strike",
  },
  dragon2: {
    tipo: "dragon2",
    geo: {
      zPino1: 1.2, espaco: 0.17, fileira: 0.147, raioPino: 0.043, raioBola: 0.05,
      alturaPino: 0.24, massaBola: 4.6, limiarQueda: 0.22, calha: 0.1,
      bumper: 0, fimBumper: 0, expBola: 0.6,
    },
    tela: { y0: 845, y1: 465, y2: 355, cx: 270, k: 1.319, yV: 168 },
    tempos: [0.62, 1.45],
    sensMira: 0.9,
    quadros: 5,
    assistencia: "destino",
  },
};

const ARTES = {
  kids: {
    pista: "strike-kids/pista.webp", rostos: "strike-kids/rostos.webp",
    bola_bob: "strike-kids/bola_bob.webp", bola_mia: "strike-kids/bola_mia.webp",
    retrato_bob: "strike-kids/retrato_bob.webp", retrato_bob_empolgado: "strike-kids/retrato_bob_empolgado.webp",
    retrato_mia: "strike-kids/retrato_mia.webp", retrato_mia_empolgado: "strike-kids/retrato_mia_empolgado.webp",
    aviso_strike: "strike-kids/aviso_strike.webp", aviso_spare: "strike-kids/aviso_spare.webp",
    aviso_boa: "strike-kids/aviso_boa.webp", aviso_uau: "strike-kids/aviso_uau.webp",
    aviso_quase: "strike-kids/aviso_quase.webp", aviso_ops: "strike-kids/aviso_ops.webp",
    aviso_super: "strike-kids/aviso_super.webp", aviso_pegando_fogo: "strike-kids/aviso_pegando_fogo.webp",
    cen_parque: "strike-kids/cen_parque.webp", cen_dinos: "strike-kids/cen_dinos.webp",
    cen_espaco: "strike-kids/cen_espaco.webp", cen_mar: "strike-kids/cen_mar.webp",
    cortina: "strike-kids/cortina.webp", ceu_sol: "strike-kids/ceu_sol.webp",
    ceu_lua: "strike-kids/ceu_lua.webp", ceu_baleia: "strike-kids/ceu_baleia.webp",
    estrelas_ceu: "strike-kids/estrelas_ceu.webp", bolha: "strike-kids/bolha.webp",
    estrela: "strike-kids/estrela.webp", chama: "strike-kids/chama.webp",
    estrela_placar: "strike-kids/estrela_placar.webp", estrela_vazia: "strike-kids/estrela_vazia.webp",
  },
  dragon: {
    pista: "dragon/pista.webp", brilho_canaleta: "dragon/brilho_canaleta.webp",
    brilho_ouro: "dragon/brilho_ouro.webp", bola: "dragon/bola.webp", pinos: "dragon/pinos.webp",
  },
  dragon2: {
    pista: "dragon/pista.webp", brilho_canaleta: "dragon/brilho_canaleta.webp",
    brilho_ouro: "dragon/brilho_ouro.webp", bola: "dragon2/bola.webp", pino: "dragon2/pino.webp",
    fx: "dragon2/fx.webp",
  },
};

/* Os 4 cenários do Strike Kids (scripts/temas.gd: CONFIG) -- céu, chão,
   neon das bordas, calha de doce, para-choques e a faixa da cortina da
   boca dos pinos (texturas/cortina_bola.png: parque, espaço, mar, selva). */
const CENARIOS = {
  dinos: {
    ceu: ["#3FA7E8", "#9BD8F0", "#FFE4AE"], chao: ["#46A44E", "#57B948"], flor: ["#FF9F33", "#FFE65A"],
    neon: "#B6FF3B", calha: ["#6DBB45", "#D4F58A"], bumper: ["#FFE65A", "#2E9A3E"],
    gabinete: "#8A5228", coluna: "#2E9A3E", portal: ["#9BE04A", "#FF8A1E"], faixa: 3, astro: "sol",
  },
  parque: {
    ceu: ["#2F7FFF", "#6CBBFF", "#E4F4FF"], chao: ["#6BCB5D", "#5BB54E"], flor: ["#FFFFFF", "#FFE873"],
    neon: "#FF4FC8", calha: ["#FF6FAE", "#FFF3E2"], bumper: ["#FFFFFF", "#FF3B50"],
    gabinete: "#E8384F", coluna: "#1E62C8", portal: ["#FFC21A", "#E8384F"], faixa: 0, astro: "sol",
  },
  espaco: {
    ceu: ["#040A26", "#0E2560", "#2C6AB8"], chao: ["#9AA8C4", "#8494B3"], flor: ["#C3CEE2", "#E2F5FF"],
    neon: "#4FE3FF", calha: ["#26357A", "#9FB4FF"], bumper: ["#FFFFFF", "#3B8BFF"],
    gabinete: "#3B3FA8", coluna: "#6A3FD0", portal: ["#4FD8FF", "#3B2FA8"], faixa: 1, astro: "lua",
  },
  mar: {
    ceu: ["#0A4F86", "#1A94C0", "#86E6DE"], chao: ["#F0C47C", "#E0AC62"], flor: ["#FF9A86", "#7CD2E0"],
    neon: "#5CFFD8", calha: ["#0C86A6", "#56E0EA"], bumper: ["#FFFFFF", "#FF7A5C"],
    gabinete: "#0E8C9C", coluna: "#FF7A5C", portal: ["#2EE6C8", "#FF7A5C"], faixa: 2, astro: "baleia",
  },
};
// a Selva dos Dinos é sempre a primeira fase (temas.gd: ORDEM)
const ORDEM_CENARIOS = ["dinos", "parque", "espaco", "mar"];

const COR_BOB = "#169BD5";
const COR_MIA = "#FF7A21";
const MARINHO = "#0B1F45";
const CREME = "#FFF6A8";
const CORES_BICHOS = ["#FF9F2E", "#FFD43B", "#4FD8FF", "#FF4B5C", "#8DFF6A", "#2E7BFF"];

// Dragon (game.gd: COR_STRIKE, COR_SPARE, COR_MISS, ACERTO e ROUND)
const COR_STRIKE = "rgb(255,128,20)";
const COR_SPARE = "rgb(255,199,56)";
const COR_MISS = "rgb(255,64,56)";
const COR_ACERTO = "rgb(255,237,64)";
const COR_ROUND = "rgb(140,235,255)";

// Dragon Bowling 2 (game.gd): bolinha (meio) com o rack cheio -> [quem fica em pé, peso]
const DESTINOS_DO_MEIO = [
  [[], 55.0],      // strike
  [[7], 14.0],     // sobra a ponta esquerda
  [[10], 14.0],    // sobra a ponta direita
  [[7, 10], 8.0],  // split das pontas
  [[4], 4.5],
  [[6], 4.5],
];
const CHANCE_DE_TABELA = 0.3;

// Strike Kids (scripts/jogada.gd: TABELA "normal"): chance de strike na 1ª
// bola jogada no CENTRO. O jogo sorteia quão boa foi a jogada e a bola
// "engancha" para a linha do bolso -- quem derruba os pinos é a física.
const STRIKE_NO_CENTRO = 0.42;

const FILEIRAS = [[1], [2, 3], [4, 5, 6], [7, 8, 9, 10]];
const VIZINHOS = {
  1: [2, 3], 2: [1, 3, 4, 5], 3: [1, 2, 5, 6], 4: [2, 5, 7, 8], 5: [2, 3, 4, 6, 8, 9],
  6: [3, 5, 9, 10], 7: [4, 8], 8: [4, 5, 7, 9], 9: [5, 6, 8, 10], 10: [6, 9],
};

/* ----------------------------------------------------------------------
   IMAGENS — carregadas uma vez por página, por variante
   ---------------------------------------------------------------------- */
const cacheImagens = new Map();
function imagem(caminho) {
  if (!cacheImagens.has(caminho)) {
    const img = new Image();
    img.decoding = "async";
    img.src = new URL(caminho, PASTA).href;
    cacheImagens.set(caminho, img);
  }
  return cacheImagens.get(caminho);
}
const pronta = (img) => !!img && img.complete && img.naturalWidth > 0;

function novaTela(w, h) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}

/* uma imagem branca (só alfa) pintada numa cor -- o brilho das canaletas
   do Dragon, as faíscas do Dragon 2 e as estrelinhas do Strike Kids */
function tingir(img, cor) {
  const c = novaTela(img.naturalWidth, img.naturalHeight);
  const x = c.getContext("2d");
  x.drawImage(img, 0, 0);
  x.globalCompositeOperation = "source-in";
  x.fillStyle = cor;
  x.fillRect(0, 0, c.width, c.height);
  return c;
}

function caminhoArredondado(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function estrelaPath(ctx, x, y, r1, r2, n) {
  ctx.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const a = -Math.PI / 2 + (i * Math.PI) / n;
    const r = i % 2 ? r2 : r1;
    ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
  }
  ctx.closePath();
}

function hexRgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function hexA(h, a) {
  const [r, g, b] = hexRgb(h);
  return `rgba(${r},${g},${b},${a})`;
}
function misturaCor(h1, h2, t) {
  const a = hexRgb(h1);
  const b = hexRgb(h2);
  return `rgb(${Math.round(mistura(a[0], b[0], t))},${Math.round(mistura(a[1], b[1], t))},${Math.round(mistura(a[2], b[2], t))})`;
}

/* sorteio que se repete: o cenário sai sempre com o mesmo desenho */
function semente(n) {
  let s = n >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/* O PINO DO STRIKE KIDS (desenhado): perfil de um pino de boliche com
   altura 1, base em y = 0 e cabeça em y = -1 */
let PINO_KIDS = null;
function pinoKids() {
  if (PINO_KIDS) return PINO_KIDS;
  // meia-largura em cada altura (fração da altura do pino)
  const perfil = [
    [0, 0.085], [0.06, 0.125], [0.17, 0.162], [0.3, 0.172], [0.42, 0.155], [0.52, 0.115],
    [0.6, 0.076], [0.66, 0.068], [0.74, 0.08], [0.83, 0.094], [0.91, 0.086], [0.97, 0.055], [1, 0],
  ];
  const p = new Path2D();
  p.moveTo(-perfil[0][1], 0);
  for (let i = 1; i < perfil.length; i++) {
    const [h0, r0] = perfil[i - 1];
    const [h1, r1] = perfil[i];
    p.quadraticCurveTo(-(r0 + r1) / 2 - 0.004, -(h0 + h1) / 2, -r1, -h1);
  }
  for (let i = perfil.length - 2; i >= 0; i--) {
    const [h0, r0] = perfil[i + 1];
    const [h1, r1] = perfil[i];
    p.quadraticCurveTo((r0 + r1) / 2 + 0.004, -(h0 + h1) / 2, r1, -h1);
  }
  p.closePath();
  PINO_KIDS = p;
  return p;
}

export default {
  largura: 540,
  altura: 960,
  artes: {},

  criar(api) {
    const V = VARIANTES[api.variante] || VARIANTES["strike-kids"];
    const KIDS = V.tipo === "kids";
    const D2 = V.tipo === "dragon2";
    const g = V.geo;
    const t = V.tela;
    const W = api.W;
    const H = api.H;
    const NQ = V.quadros;
    const real = !KIDS; // conta do boliche de verdade nos Dragons

    // ---------------------------------------------------------- artes
    const img = {};
    if (typeof Image !== "undefined") {
      const lista = ARTES[KIDS ? "kids" : V.tipo];
      for (const nome of Object.keys(lista)) img[nome] = imagem(lista[nome]);
    }

    // ---------------------------------------------------------- perspectiva
    // y(z) = yH + K / (z + B): passa por (0, y0), (pino 1, y1) e (última
    // fileira, y2) -- uma perspectiva suave que deixa o rack com a altura
    // que a arte pede.
    const zP = g.zPino1;
    const fundoRack = 3 * g.fileira;
    const zFim = zP + fundoRack + 0.3; // fim da mesa dos pinos: depois é o fosso
    const P = (() => {
      const r = (t.y0 - t.y1) / (t.y1 - t.y2);
      const B = (zP * (zP + fundoRack)) / (r * fundoRack - zP);
      const K = ((t.y0 - t.y1) * B * (zP + B)) / zP;
      return { B, K, yH: t.y0 - K / B };
    })();
    const yDe = (z) => P.yH + P.K / (z + P.B);
    const zDe = (y) => P.K / (y - P.yH) - P.B;
    const lDe = (y) => t.k * (y - t.yV);
    const cx = t.cx;
    // resultado da última projeção (sem criar objetos a cada ponto)
    let PX = 0;
    let PY = 0;
    let PW = 0;
    const projetar = (x, z) => {
      PY = yDe(z);
      PW = lDe(PY);
      PX = cx + x * PW;
    };
    const larguraPino1 = lDe(t.y1);
    // a bola de perto é desenhada um pouco menor que a perspectiva pede (a
    // pista da arte do Dragon abre muito embaixo); perto dos pinos, onde ela
    // bate, o tamanho é o exato
    const raioBolaTela = (y) => g.raioBola * larguraPino1 * Math.pow(Math.max(0.2, lDe(y) / larguraPino1), g.expBola);

    // ---------------------------------------------------------- estado
    const pinos = [];
    for (let n = 1; n <= 10; n++) {
      let fil = 0;
      while (!FILEIRAS[fil].includes(n)) fil++;
      const k = FILEIRAS[fil].indexOf(n);
      pinos.push({
        n, x0: (k - fil / 2) * g.espaco, z0: zP + fil * g.fileira, fileira: fil,
        x: 0, z: 0, vx: 0, vz: 0, estado: EM_PE, queda: 0, dx: 0, dz: 1, tDeitado: 0,
        alfa: 1, bal: 0, balFase: n, bateu: 0, protegido: false, entrada: 1, giro: 0, lado: 0, fumaca: false,
      });
    }
    const bola = {
      x: 0, z: 0, vx: 0, vz: 0, curva: 0, plano: null, planejada: false, giro: 0, estado: "pronta",
      canaleta: false, atravessa: false, tocou: false, ergue: 0, fogo: false,
    };
    const RASTRO = 28;
    const rastroX = new Float32Array(RASTRO);
    const rastroZ = new Float32Array(RASTRO);
    let rastroN = 0;
    let rastroI = 0;
    let rastroT = 0;

    let fase = "pronta";
    let tFase = 0;
    let relogio = 0;
    let acumulador = 0;
    let comecou = false;
    let terminou = false;
    let pontos = 0;
    let quadros = [];
    let iQuadro = 0;
    let pinosAntes = 10;
    let strikes = 0;
    let spares = 0;
    let pinosTotal = 0;
    let seguidos = 0;
    let jogadaForcada = false;
    let tabelaFeita = false;
    let tBolaFim = 0;
    let resultadoDur = 1.5;
    let agenda = [];
    let ultimoSomPino = 0;
    let somPinosNaJogada = 0;
    let dicaVista = false;
    let tParado = 0;
    let usouTeclado = false;
    let miraTeclado = 0;
    const teclas = { esq: false, dir: false, miraEsq: false, miraDir: false };
    let zoomSoco = 0;
    let flash = null;
    let canaletaModo = "normal";
    let tCanaleta = 0;
    let faseSobe = 0;
    let cenario = "dinos";
    let ordemCen = ORDEM_CENARIOS.slice();
    const festa = [0, 0];
    const triste = [0, 0];
    const bumperBrilho = [0, 0];

    // gesto: as últimas posições do dedo (anel fixo, sem criar nada)
    let arrastando = false;
    let idArrasto = null;
    const AMOSTRAS = 32;
    const amX = new Float32Array(AMOSTRAS);
    const amY = new Float32Array(AMOSTRAS);
    const amT = new Float64Array(AMOSTRAS);
    let amN = 0;
    let amI = 0;
    let dedoY = 0;

    const avisos = [];          // letreiros e textos grandes
    const parts = [];           // estrelinhas, confete, faíscas, fumaça, lascas
    const MAX_PARTS = 260;

    const agora = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

    /* ======================================================================
       PARTIDA
       ====================================================================== */
    function montarRack(entrada) {
      for (const p of pinos) {
        p.x = p.x0;
        p.z = p.z0;
        p.vx = p.vz = 0;
        p.estado = EM_PE;
        p.queda = 0;
        p.tDeitado = 0;
        p.alfa = 1;
        p.bal = 0;
        p.bateu = 0;
        p.protegido = false;
        p.giro = 0;
        p.fumaca = false;
        // montagem fileira por fileira, de trás para a frente (como a mesa
        // de pinos do Dragon)
        p.entrada = entrada ? -(3 - p.fileira) * 0.11 : 1;
      }
    }

    function bolaNaMao() {
      bola.x = 0;
      bola.z = 0;
      bola.vx = bola.vz = 0;
      bola.curva = 0;
      bola.plano = null;
      bola.planejada = false;
      bola.giro = 0;
      bola.estado = "pronta";
      bola.canaleta = false;
      bola.atravessa = false;
      bola.tocou = false;
      bola.ergue = 0;
      rastroN = 0;
      miraTeclado = 0;
    }

    function emPe() {
      let n = 0;
      for (const p of pinos) if (p.estado === EM_PE) n++;
      return n;
    }

    function infoPlacar() {
      const q = quadros[iQuadro];
      const bolaN = (q ? q.bolas.length : 0) + 1;
      return `${KIDS ? "RODADA" : "ROUND"} ${iQuadro + 1}/${NQ} · BOLA ${bolaN}`;
    }

    function iniciar() {
      fase = "pronta";
      tFase = 0;
      relogio = 0;
      acumulador = 0;
      comecou = false;
      terminou = false;
      pontos = 0;
      quadros = [];
      for (let i = 0; i < NQ; i++) quadros.push({ bolas: [], tipos: [], total: null });
      iQuadro = 0;
      pinosAntes = 10;
      strikes = spares = pinosTotal = seguidos = 0;
      jogadaForcada = false;
      tabelaFeita = false;
      agenda = [];
      avisos.length = 0;
      parts.length = 0;
      flash = null;
      zoomSoco = 0;
      canaletaModo = "normal";
      festa[0] = festa[1] = triste[0] = triste[1] = 0;
      dicaVista = false;
      tParado = 0;
      arrastando = false;
      idArrasto = null;
      bola.fogo = false;
      // a selva é sempre a primeira; as outras três vêm sorteadas e a 5ª
      // rodada volta a uma das primeiras
      const resto = ORDEM_CENARIOS.slice(1).sort(() => Math.random() - 0.5);
      ordemCen = ["dinos", ...resto, ORDEM_CENARIOS[Math.floor(Math.random() * 3)]];
      cenario = ordemCen[0];
      montarRack(false);
      bolaNaMao();
      api.placar({ pontos: 0, tempo: null, info: infoPlacar() });
    }

    /* começo de rodada: rack novo e os avisos de cada jogo */
    function abrirQuadro(primeiro) {
      if (KIDS) {
        cenario = ordemCen[iQuadro % ordemCen.length];
        // o nome do cenário (ui/cen_*.png) e a faixa "VEZ DO BOB!"
        aviso({ img: "cen_" + cenario, dur: 1.7, y: 300, larg: 400 });
        aviso({ faixa: true, nome: iQuadro % 2 ? "mia" : "bob", dur: 1.6, y: 560 });
        api.som(primeiro ? "nota" : "moeda");
      } else {
        aviso({ texto: `ROUND ${iQuadro + 1}`, cor: COR_ROUND, tam: 66, dur: 1.15, y: 560 });
        api.som("nota");
      }
      montarRack(!primeiro);
      bolaNaMao();
      pinosAntes = 10;
      fase = primeiro ? "pronta" : "montando";
      tFase = 0;
      api.placar({ info: infoPlacar() });
    }

    /* ======================================================================
       O LANÇAMENTO
       ====================================================================== */
    function lancar(inclinacao, velocidade, curva) {
      const n = Math.sqrt(1 + inclinacao * inclinacao);
      bola.vx = (velocidade * inclinacao) / n;
      bola.vz = velocidade / n;
      bola.curva = curva;
      bola.estado = "rolando";
      bola.ergue = 0;
      fase = "rolando";
      tFase = 0;
      tBolaFim = 0;
      jogadaForcada = false;
      tabelaFeita = false;
      somPinosNaJogada = 0;
      pinosAntes = emPe();
      dicaVista = true;
      tParado = 0;
      api.som("whoosh");
      api.vibrar(15);
    }

    /* o gesto vira jogada: velocidade dos últimos ~100 ms (força e mira) e
       a "barriga" do caminho (efeito). Devolve false se foi só um arrasto. */
    function lancarPeloGesto() {
      if (amN < 2) return false;
      const ult = (amI - 1 + AMOSTRAS) % AMOSTRAS;
      let j = ult;
      for (let usados = 1; usados < amN; usados++) {
        const k = (j - 1 + AMOSTRAS) % AMOSTRAS;
        if (amT[ult] - amT[k] > 110) break;
        j = k;
      }
      if (j === ult) j = (ult - 1 + AMOSTRAS) % AMOSTRAS;
      const dt = Math.max(0.012, (amT[ult] - amT[j]) / 1000);
      const vx = (amX[ult] - amX[j]) / dt;
      const vy = (amY[ult] - amY[j]) / dt;
      const subida = -vy;
      if (subida < 240) return false;

      // força: 240 px/s (fraquinha) a 2400 px/s (no talo)
      const f = Math.pow(lim((subida - 240) / 2000, 0, 1), 0.85);
      const velocidade = zP / mistura(V.tempos[1], V.tempos[0], f);

      // mira: o gesto na tela convertido para a pista, na altura da bola
      const dydz = Math.abs(yDe(0.05) - yDe(0)) / 0.05;
      const inclinacao = lim((((vx / subida) * dydz) / lDe(t.y0)) * V.sensMira, -0.42, 0.42);

      // efeito: quanto o caminho do dedo "barrigou" para um lado
      let ini = ult;
      let n = 1;
      while (n < amN) {
        const k = (ini - 1 + AMOSTRAS) % AMOSTRAS;
        if (amT[ult] - amT[k] > 320) break;
        ini = k;
        n++;
      }
      const ex = amX[ult] - amX[ini];
      const ey = amY[ult] - amY[ini];
      const corda = Math.hypot(ex, ey);
      let barriga = 0;
      if (corda > 60) {
        const ux = ex / corda;
        const uy = ey / corda;
        for (let i = 0, k = ini; i < n; i++, k = (k + 1) % AMOSTRAS) {
          const d = ux * (amY[k] - amY[ini]) - uy * (amX[k] - amX[ini]);
          if (Math.abs(d) > Math.abs(barriga)) barriga = d;
        }
        barriga /= corda;
      }
      // caminho barrigudo para a direita = o dedo terminou virando para a
      // esquerda: a bola engancha para a esquerda (e vice-versa)
      const curva = lim(barriga * 5.5, -0.75, 0.75) * zP;
      lancar(inclinacao, velocidade, curva);
      return true;
    }

    /* ======================================================================
       FÍSICA
       ====================================================================== */
    function somPino(forte) {
      const t0 = agora();
      if (t0 - ultimoSomPino < 70 || somPinosNaJogada > 6) return;
      ultimoSomPino = t0;
      somPinosNaJogada++;
      api.som(forte ? "batida" : "quica");
    }

    function derrubar(p, dx, dz) {
      if (p.estado !== EM_PE || p.protegido) return;
      // um pino de verdade nunca cai igual duas vezes: a direção varia um pouco
      const desvio = (Math.random() - 0.5) * 0.5;
      const c = Math.cos(desvio);
      const s = Math.sin(desvio);
      const m = Math.hypot(dx, dz) || 1;
      p.estado = CAINDO;
      p.queda = 0;
      p.dx = (dx * c - dz * s) / m;
      p.dz = (dx * s + dz * c) / m;
      p.tDeitado = 0;
      p.bateu = 0;
      p.giro = (Math.random() - 0.5) * 2;
      // para que lado ele cai na tela (escolhe os quadros de queda do Dragon)
      projetar(p.x, p.z);
      const bx = PX;
      const by = PY;
      projetar(p.x + p.dx * 0.1, p.z + p.dz * 0.1);
      const ex = PX - bx;
      const mm = Math.hypot(ex, PY - by) || 1;
      p.lado = ex / mm < -0.35 ? -1 : ex / mm > 0.35 ? 1 : 0;
      somPino(true);
      if (D2) faiscasPino(p);
    }

    function empurrar(p, ix, iz) {
      if (p.estado === FORA) return;
      if (p.protegido) {
        // o destino sorteado mandou ficar em pé: só balança
        p.bal = Math.min(1, p.bal + Math.hypot(ix, iz) * 2.5);
        return;
      }
      p.vx += ix;
      p.vz += iz;
      if (p.estado === EM_PE) {
        const dv = Math.hypot(ix, iz);
        if (dv > g.limiarQueda) derrubar(p, p.vx, p.vz);
        else p.bal = Math.min(1, p.bal + dv * 3);
      }
    }

    /* a cabeça do pino que tomba bate nos vizinhos: a reação em cadeia */
    function pontaBate(p) {
      const s = Math.sin((p.queda * Math.PI) / 2);
      const L = g.alturaPino * 0.85;
      const tx = p.x + p.dx * L * s;
      const tz = p.z + p.dz * L * s;
      const alcance = g.raioPino * 1.9;
      const vPonta = L * (Math.PI / 2 / DUR_QUEDA) * Math.cos((p.queda * Math.PI) / 2) * 0.55 + Math.hypot(p.vx, p.vz) * 0.35;
      for (const q of pinos) {
        if (q === p || q.estado !== EM_PE || p.bateu & (1 << q.n)) continue;
        const ddx = q.x - tx;
        const ddz = q.z - tz;
        if (ddx * ddx + ddz * ddz > alcance * alcance) continue;
        p.bateu |= 1 << q.n;
        let nx = p.dx + ddx * 6;
        let nz = p.dz + ddz * 6;
        const m = Math.hypot(nx, nz) || 1;
        nx /= m;
        nz /= m;
        empurrar(q, nx * vPonta, nz * vPonta);
      }
    }

    function primeiroToque(p) {
      // a pancada do contato: tranco curto na câmera, maior no rack cheio
      const cheio = pinosAntes === 10;
      if (KIDS) {
        api.tremer(4);
      } else {
        api.tremer(cheio ? 8.5 : 5);
        if (!api.reduzido) zoomSoco = Math.max(zoomSoco, cheio ? 0.045 : 0.025);
        if (D2) choqueD2(p);
      }
      api.som("batida");
      if ((V.assistencia !== "strike" && V.assistencia !== "destino") || !cheio || p.n !== 1) return;
      // a "bolinha do meio": rack cheio acertado bem no centro do pino 1
      if (Math.abs(bola.x - p.x) > (g.raioBola + g.raioPino) * 0.72) return;
      if (Math.hypot(bola.vx, bola.vz) < (zP / V.tempos[1]) * 1.15) return;
      let protegidos = [];
      if (V.assistencia === "destino") {
        let total = 0;
        for (const d of DESTINOS_DO_MEIO) total += d[1];
        let sorte = Math.random() * total;
        for (const d of DESTINOS_DO_MEIO) {
          sorte -= d[1];
          if (sorte <= 0) {
            protegidos = d[0];
            break;
          }
        }
      }
      strikeEmCascata(protegidos);
    }

    /* strike garantido (Dragon) / destino sorteado (Dragon 2): os pinos caem
       fileira por fileira, voando para longe do contato, e a bola atravessa
       o rack sem parar (game.gd: _forcar_strike_central_se_preciso) */
    function strikeEmCascata(protegidos) {
      jogadaForcada = true;
      bola.atravessa = true;
      for (const p of pinos) p.protegido = protegidos.includes(p.n);
      const pausas = [0, 0.055, 0.12, 0.2];
      for (let i = 0; i < FILEIRAS.length; i++) {
        for (const n of FILEIRAS[i]) {
          agenda.push({ t: relogio + pausas[i] + Math.random() * 0.03 * i, tipo: "voar", n, x: bola.x });
        }
      }
    }

    function voar(p, xImpacto) {
      if (p.estado !== EM_PE) return;
      if (p.protegido) {
        p.bal = 1;
        return;
      }
      const intens = { 7: 1.56, 10: 1.56, 8: 1.44, 9: 1.44, 4: 1.38, 6: 1.38, 2: 1.3, 3: 1.3 }[p.n] || 1.34;
      const dx = (p.x - xImpacto) * 3.2 + (Math.random() - 0.5) * 0.25;
      const v = (zP / V.tempos[0]) * 0.55 * intens;
      const m = Math.hypot(dx, 1);
      p.vx = (dx / m) * v;
      p.vz = (1 / m) * v;
      derrubar(p, p.vx, p.vz);
    }

    function fisica(h) {
      // ------------------------------------------------ bola
      if (bola.estado === "rolando") {
        if (!bola.canaleta && bola.curva) {
          // o efeito pega no fim da pista (onde acaba o óleo)
          const ramp = suave(lim((bola.z - zP * 0.35) / (zP * 0.45), 0, 1));
          bola.vx += bola.curva * ramp * h * (bola.tocou ? 0.4 : 1);
        }
        // a bola nunca para na pista: o embalo leva até o fosso
        if (bola.vz < 0.35 * zP) bola.vz += (0.35 * zP - bola.vz) * Math.min(1, 5 * h);
        bola.x += bola.vx * h;
        bola.z += bola.vz * h;
        if (bola.plano) {
          // a linha do bolso (Strike Kids): sai da linha jogada e entra reta
          const pl = bola.plano;
          const prog = lim((bola.z - pl.z0) / (pl.z1 - pl.z0), 0, 1);
          const xNovo = mistura(pl.x0 + pl.inc * (bola.z - pl.z0), pl.alvo, suave(prog));
          bola.vx = (xNovo - (bola.x - bola.vx * h)) / h;
          bola.x = xNovo;
          if (prog >= 1) {
            bola.plano = null;
            bola.vx = 0;
          }
        }
        bola.giro += (Math.hypot(bola.vx, bola.vz) * h) / g.raioBola;
        const lado = bola.x < 0 ? -1 : 1;
        if (g.bumper && bola.z < g.fimBumper && Math.abs(bola.x) > g.bumper - g.raioBola) {
          // para-choque de doce: a bola volta para a pista
          bola.x = lado * (g.bumper - g.raioBola);
          if (bola.vx * lado > 0) {
            bola.vx = -bola.vx * 0.55;
            bola.curva *= 0.5;
            bumperBrilho[lado < 0 ? 0 : 1] = 1;
            api.som("quica");
          }
        } else if (!bola.canaleta && Math.abs(bola.x) > 0.5) {
          bola.canaleta = true;
          bola.vx = 0;
          if (!KIDS) canaleta("erro");
        }
        if (bola.canaleta) {
          const meio = lado * (0.5 + g.calha * 0.5);
          bola.x += (meio - bola.x) * Math.min(1, 12 * h);
          bola.vx = 0;
        }
        if (bola.z > zFim + g.raioBola * 2) bola.estado = "fim";
      }

      // ------------------------------------------------ pinos
      const parede = 0.5 + g.calha + 0.02;
      for (const p of pinos) {
        if (p.estado === FORA) continue;
        if (p.estado === EM_PE) {
          // pino em pé quase não escorrega
          const f = Math.exp(-16 * h);
          p.vx *= f;
          p.vz *= f;
          p.x += p.vx * h;
          p.z += p.vz * h;
          p.bal *= Math.exp(-2.6 * h);
          p.balFase += h * 17;
          // empurrado para fora da mesa: conta como derrubado
          if (Math.abs(p.x) > 0.5 + g.raioPino || p.z > zFim) derrubar(p, p.vx || 0.01, p.vz || 0.01);
        } else {
          const f = Math.exp(-(p.queda < 1 ? 1.4 : 3.4) * h);
          p.vx *= f;
          p.vz *= f;
          p.x += p.vx * h;
          p.z += p.vz * h;
          if (p.queda < 1) {
            p.queda = Math.min(1, p.queda + h / DUR_QUEDA);
            pontaBate(p);
          } else {
            p.tDeitado += h;
          }
          // as paredes do lado da mesa devolvem o pino (o "mixer")
          if (Math.abs(p.x) > parede) {
            const s = Math.sign(p.x);
            p.x = s * parede;
            if (p.vx * s > 0) p.vx = -p.vx * 0.5;
          }
          if (p.z > zFim) p.alfa -= h * 4;
          if (p.tDeitado > TEMPO_DEITADO) p.alfa -= h / 0.35;
          if (p.alfa <= 0) {
            p.alfa = 0;
            p.estado = FORA;
          }
        }
      }

      // ------------------------------------------------ bola x pinos
      if (bola.estado === "rolando" && !bola.canaleta && !bola.atravessa) {
        for (const p of pinos) {
          if (p.estado === FORA) continue;
          const rp = p.estado === EM_PE ? g.raioPino : g.raioPino * 1.15;
          const R = rp + g.raioBola;
          const dx = p.x - bola.x;
          const dz = p.z - bola.z;
          const d2 = dx * dx + dz * dz;
          if (d2 >= R * R || d2 < 1e-10) continue;
          const d = Math.sqrt(d2);
          const nx = dx / d;
          const nz = dz / d;
          const vrel = (bola.vx - p.vx) * nx + (bola.vz - p.vz) * nz;
          if (vrel > 0 && !bola.tocou) {
            bola.tocou = true;
            primeiroToque(p);
            if (bola.atravessa) break;
          }
          const pen = R - d;
          p.x += nx * pen * 0.85;
          p.z += nz * pen * 0.85;
          bola.x -= nx * pen * 0.15;
          bola.z -= nz * pen * 0.15;
          if (vrel <= 0) continue;
          // impulso com massa (a bola pesa várias vezes o pino) e quique
          const mb = g.massaBola;
          const j = ((1.55 + Math.random() * 0.15) * vrel) / (1 / mb + 1);
          bola.vx -= (j / mb) * nx;
          bola.vz -= (j / mb) * nz;
          empurrar(p, j * nx, j * nz);
        }
      }

      // ------------------------------------------------ pino x pino
      for (let a = 0; a < 10; a++) {
        const p = pinos[a];
        if (p.estado === FORA) continue;
        for (let b = a + 1; b < 10; b++) {
          const q = pinos[b];
          if (q.estado === FORA) continue;
          if (p.estado === EM_PE && q.estado === EM_PE && p.vx * p.vx + p.vz * p.vz + q.vx * q.vx + q.vz * q.vz < 1e-4) continue;
          const rp = p.estado === EM_PE ? g.raioPino : g.raioPino * 1.12;
          const rq = q.estado === EM_PE ? g.raioPino : g.raioPino * 1.12;
          const R = rp + rq;
          const dx = q.x - p.x;
          const dz = q.z - p.z;
          const d2 = dx * dx + dz * dz;
          if (d2 >= R * R || d2 < 1e-10) continue;
          const d = Math.sqrt(d2);
          const nx = dx / d;
          const nz = dz / d;
          const pen = (R - d) * 0.5;
          if (!p.protegido) {
            p.x -= nx * pen;
            p.z -= nz * pen;
          }
          if (!q.protegido) {
            q.x += nx * pen;
            q.z += nz * pen;
          }
          const vrel = (p.vx - q.vx) * nx + (p.vz - q.vz) * nz;
          if (vrel <= 0) continue;
          const j = ((1.35 + Math.random() * 0.2) * vrel) / 2;
          empurrar(p, -j * nx, -j * nz);
          empurrar(q, j * nx, j * nz);
        }
      }
    }

    /* ======================================================================
       RESULTADO DE CADA BOLA
       ====================================================================== */
    function contar() {
      const ficaram = emPe();
      const n = pinosAntes - ficaram;
      const q = quadros[iQuadro];
      q.bolas.push(n);
      const strike = pinosAntes === 10 && ficaram === 0;
      const spare = pinosAntes < 10 && ficaram === 0;
      const tipo = strike ? "strike" : spare ? "spare" : n === 0 ? "zero" : "normal";
      q.tipos.push(tipo);
      pinosTotal += n;
      if (strike) strikes++;
      if (spare) spares++;
      let ganho = 0;
      if (KIDS) {
        // scripts/placar.gd: cada pino = 10, STRIKE +50, SPARE +20
        ganho = n * 10 + (strike ? 50 : spare ? 20 : 0);
        pontos += ganho;
        q.total = (q.total || 0) + ganho;
      } else {
        const antes = pontos;
        pontos = pontuacaoReal();
        ganho = pontos - antes;
      }
      // strikes seguidos (rodada sem strike zera a sequência)
      const passo = proximoPasso();
      if (strike) seguidos++;
      else if (passo !== "mesmoRack" && passo !== "rackNovo") seguidos = 0;
      api.placar({ pontos });
      return { tipo, n, ficaram, ganho };
    }

    /* a conta do boliche de verdade, com o que já foi jogado */
    function pontuacaoReal() {
      const todas = [];
      for (const q of quadros) for (const b of q.bolas) todas.push(b);
      let total = 0;
      let i = 0;
      for (let f = 0; f < NQ; f++) {
        const q = quadros[f];
        if (!q.bolas.length) {
          q.total = null;
          continue;
        }
        if (f < NQ - 1) {
          if (q.bolas[0] === 10) {
            total += 10 + (todas[i + 1] || 0) + (todas[i + 2] || 0);
            i += 1;
          } else if (q.bolas.length > 1 && q.bolas[0] + q.bolas[1] === 10) {
            total += 10 + (todas[i + 2] || 0);
            i += 2;
          } else {
            total += q.bolas[0] + (q.bolas[1] || 0);
            i += q.bolas.length;
          }
        } else {
          for (const b of q.bolas) total += b;
        }
        q.total = total;
      }
      return total;
    }

    /* o que vem depois desta bola: "mesmoRack", "rackNovo" (bônus da
       última rodada), "quadroNovo" ou "fim" */
    function proximoPasso() {
      const b = quadros[iQuadro].bolas;
      const ultimo = iQuadro === NQ - 1;
      if (real && ultimo) {
        if (b.length === 1) return b[0] === 10 ? "rackNovo" : "mesmoRack";
        if (b.length === 2) {
          if (b[0] === 10) return b[1] === 10 ? "rackNovo" : "mesmoRack";
          if (b[0] + b[1] === 10) return "rackNovo";
          return "fim";
        }
        return "fim";
      }
      if (emPe() === 0 || b.length >= 2) return ultimo ? "fim" : "quadroNovo";
      return "mesmoRack";
    }

    function reagir(r) {
      if (KIDS) reagirKids(r);
      else reagirDragon(r);
      // os pontos voando (no Dragon o strike e o spare só fecham a conta
      // nas bolas seguintes: o placar de cima mostra)
      if (KIDS && r.ganho > 0) api.efeitos.texto(`+${r.ganho}`, cx, yDe(zP) + 70, { cor: CREME, tamanho: 46, vida: 1.2 });
    }

    /* scripts/principal.gd: _finalizar_jogada */
    function reagirKids(r) {
      const vez = iQuadro % 2;
      const outro = 1 - vez;
      const meio = yDe(zP + fundoRack * 0.5) - 30;
      if (r.tipo === "strike") {
        aviso({ img: "aviso_strike", dur: 1.9, y: 400 });
        brilhoTela("#FFF6A8", 0.75, 0.75);
        api.som("strike");
        api.vibrar(60);
        festa[vez] = 2.6;
        festa[outro] = 2.2;
        estrelas(cx, meio, 40, 1.3);
        confete(90);
        if (seguidos >= 2) {
          // 2 ou mais strikes seguidos: a bola pega fogo
          bola.fogo = true;
          agenda.push({ t: relogio + 1.0, tipo: "fogo", n: seguidos });
        }
      } else if (r.tipo === "spare") {
        aviso({ img: "aviso_spare", dur: 1.7, y: 400 });
        brilhoTela("#C9F7FF", 0.55, 0.55);
        api.som("acerto");
        festa[vez] = 1.8;
        festa[outro] = 1.8;
        estrelas(cx, meio, 28, 1.0);
      } else if (r.tipo === "zero") {
        aviso({ img: "aviso_ops", dur: 1.5, y: 400 });
        api.som("erro");
        triste[vez] = 1.6;
      } else {
        let nome = "boa";
        if (r.n >= 7) nome = Math.random() < 0.5 ? "super" : "uau";
        else if (r.ficaram === 1) nome = "quase";
        aviso({ img: "aviso_" + nome, dur: 1.5, y: 400, sub: `${r.n} ${r.n === 1 ? "PINO" : "PINOS"}!` });
        api.som("ponto");
        if (r.ficaram === 1) triste[vez] = 0.9;
        else festa[vez] = 1.2;
        if (r.n >= 5) estrelas(cx, meio, 16, 0.8);
      }
      if (r.tipo !== "strike") bola.fogo = false;
    }

    /* scripts/game.gd: _on_bola_impacto_no_deck + mostrar_banner */
    function reagirDragon(r) {
      const y = 610;
      const meio = yDe(zP + fundoRack * 0.5) - 30;
      if (r.tipo === "strike") {
        aviso({ texto: "STRIKE!", cor: COR_STRIKE, tam: 92, dur: 1.5, y, strike: true });
        // efeito_strike_total: clarão quente + branco e a câmera sacudindo
        brilhoTela("rgb(255,158,31)", 0.22, 0.3);
        brilhoTela("#ffffff", 0.28, 0.14);
        api.tremer(9.5);
        api.som("strike");
        api.vibrar(70);
        canaleta("strike");
        if (D2) estrelasD2(cx, meio, 30);
        else faiscasDragon(cx, meio, 40);
      } else if (r.tipo === "spare") {
        aviso({ texto: "SPARE!", cor: COR_SPARE, tam: 84, dur: 1.3, y });
        api.som("acerto");
        if (D2) estrelasD2(cx, meio, 18);
        else faiscasDragon(cx, meio, 22);
      } else if (r.tipo === "zero") {
        aviso({ texto: "PRA FORA!", cor: COR_MISS, tam: 76, dur: 1.3, y });
        api.som("erro");
        canaleta("erro");
      } else {
        let texto = "ACERTO!";
        if (D2 && quadros[iQuadro].bolas.length === 1 && pinosAntes === 10) {
          // game.gd: _texto_do_resultado
          if (r.ficaram === 2 && pinos[6].estado === EM_PE && pinos[9].estado === EM_PE) texto = "SPLIT!";
          else if (r.ficaram === 1) texto = "QUASE!";
        }
        aviso({ texto, cor: COR_ACERTO, tam: 80, dur: 1.2, y });
        api.som(r.n === 1 ? "nota" : "ponto");
      }
    }

    function terminarPartida() {
      if (terminou) return;
      terminou = true;
      fase = "fim";
      if (KIDS) {
        // placar.gd: estrelas do fim (fração do máximo possível)
        const maximo = NQ * (10 * 10 + 50);
        const f = pontos / maximo;
        const n = f >= 0.62 ? 3 : f >= 0.38 ? 2 : 1;
        api.terminar({
          pontos,
          titulo: n === 3 ? "Parabéns!" : "Muito bem!",
          detalhe: `${"★".repeat(n)}${"☆".repeat(3 - n)}  ${strikes} strike${strikes === 1 ? "" : "s"} · ${spares} spare${spares === 1 ? "" : "s"} · ${pinosTotal} pinos`,
        });
      } else {
        const media = (pinosTotal / NQ).toFixed(1).replace(".", ",");
        api.terminar({
          pontos,
          titulo: "Fim de jogo",
          detalhe: `PINOS: ${pinosTotal} · STRIKES: ${strikes} · MÉDIA: ${media}`,
        });
      }
    }

    /* ======================================================================
       EFEITOS
       ====================================================================== */
    function aviso(a) {
      a.t = 0;
      a.dur = a.dur || 1.5;
      avisos.push(a);
    }

    function brilhoTela(cor, alfa, dur) {
      flash = { cor, alfa: api.reduzido ? alfa * 0.4 : alfa, dur, t: 0, prox: flash };
    }

    function canaleta(modo) {
      canaletaModo = modo;
      tCanaleta = 0;
    }

    function particula(o) {
      if (parts.length >= MAX_PARTS) return;
      if (api.reduzido && Math.random() < 0.6) return;
      o.t = 0;
      parts.push(o);
    }

    function estrelas(x, y, n, forca) {
      for (let i = 0; i < n; i++) {
        const a = Math.random() * TAU;
        const v = (140 + Math.random() * 260) * forca;
        particula({
          tipo: "estrela", cor: i % CORES_BICHOS.length, x, y,
          vx: Math.cos(a) * v, vy: Math.sin(a) * v - 220 * forca, g: 520,
          rot: Math.random() * TAU, vr: (Math.random() - 0.5) * 8,
          tam: 14 + Math.random() * 16, vida: 0.9 + Math.random() * 0.6,
        });
      }
    }

    function confete(n) {
      for (let i = 0; i < n; i++) {
        particula({
          tipo: "confete", cor: CORES_BICHOS[i % CORES_BICHOS.length],
          x: Math.random() * W, y: -20 - Math.random() * 200,
          vx: (Math.random() - 0.5) * 80, vy: 160 + Math.random() * 160, g: 60,
          rot: Math.random() * TAU, vr: (Math.random() - 0.5) * 10,
          tam: 7 + Math.random() * 6, vida: 2.2 + Math.random() * 1.2,
        });
      }
    }

    function faiscasDragon(x, y, n) {
      for (let i = 0; i < n; i++) {
        const a = Math.random() * TAU;
        const v = 120 + Math.random() * 320;
        particula({
          tipo: "brasa", cor: i % 3 === 0 ? "#ffe066" : i % 3 === 1 ? "#ff8a1e" : "#ffffff",
          x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 160, g: 380,
          tam: 2 + Math.random() * 3.5, vida: 0.5 + Math.random() * 0.6, rot: 0, vr: 0,
        });
      }
    }

    /* Dragon 2 (scripts/fx_pino.gd): clarão, anel de choque deitado na
       pista, faíscas em estrela de 4 pontas e lascas brancas e vermelhas */
    function choqueD2(p) {
      projetar(p.x, p.z);
      const x = PX;
      const y = PY - PW * g.alturaPino * 0.35;
      particula({ tipo: "fx", quadro: 1, x, y, vx: 0, vy: 0, g: 0, rot: 0, vr: 0, tam: PW * 0.7, cresce: 2.2, vida: 0.32, luz: true });
      particula({ tipo: "anel", x: PX, y: PY, vx: 0, vy: 0, g: 0, rot: 0, vr: 0, tam: PW * 0.25, cresce: 5, vida: 0.45 });
      estrelasD2(x, y, 14);
    }

    function estrelasD2(x, y, n) {
      for (let i = 0; i < n; i++) {
        const a = Math.random() * TAU;
        const v = 120 + Math.random() * 300;
        particula({
          tipo: "fx", quadro: 2, x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 120, g: 300,
          rot: Math.random() * TAU, vr: (Math.random() - 0.5) * 9, tam: 18 + Math.random() * 22,
          cresce: -0.5, vida: 0.55 + Math.random() * 0.4, luz: true, tinta: i % 2 ? "ouroFx" : "azulFx",
        });
      }
    }

    function faiscasPino(p) {
      projetar(p.x, p.z);
      const x = PX;
      const y = PY - PW * g.alturaPino * 0.4;
      for (let i = 0; i < 4; i++) {
        const a = -Math.PI / 2 + (Math.random() - 0.5) * 2.4;
        const v = 140 + Math.random() * 200;
        particula({
          tipo: "fx", quadro: 4, x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, g: 700,
          rot: Math.random() * TAU, vr: (Math.random() - 0.5) * 22, tam: 10 + Math.random() * 7,
          cresce: 0, vida: 0.6, tinta: i % 2 ? "vermelhoFx" : null,
        });
      }
      particula({ tipo: "fx", quadro: 2, x, y, vx: 0, vy: -40, g: 0, rot: 0, vr: 3, tam: 26, cresce: -0.6, vida: 0.35, luz: true });
    }

    function fumacaD2(p) {
      projetar(p.x, p.z);
      particula({
        tipo: "fx", quadro: 3, x: PX, y: PY - 6, vx: (Math.random() - 0.5) * 30, vy: -18, g: 0,
        rot: Math.random() * TAU, vr: 0.6, tam: PW * 0.22, cresce: 1.4, vida: 0.7, alfa: 0.55,
      });
    }

    /* ======================================================================
       ATUALIZAR
       ====================================================================== */
    function atualizar(dt) {
      relogio += dt;
      tFase += dt;
      if (!comecou) {
        comecou = true;
        abrirQuadro(true);
      }

      // agenda: quedas em cascata, pino "de tabela", aviso de fogo
      for (let i = agenda.length - 1; i >= 0; i--) {
        const a = agenda[i];
        if (relogio < a.t) continue;
        agenda.splice(i, 1);
        if (a.tipo === "voar") voar(pinos[a.n - 1], a.x);
        else if (a.tipo === "tabela") {
          const p = pinos[a.n - 1];
          if (p.estado === EM_PE) {
            const vv = (zP / V.tempos[1]) * 0.6;
            p.vx = (p.x - a.x >= 0 ? 1 : -1) * vv * 0.6;
            p.vz = vv;
            derrubar(p, p.vx, p.vz);
          }
        } else if (a.tipo === "fogo") {
          aviso({ img: "aviso_pegando_fogo", dur: 1.6, y: 560, sub: `${a.n} STRIKES SEGUIDOS!` });
          api.som("combo");
        }
      }

      planejarKids();
      // física em passos fixos
      acumulador = Math.min(acumulador + dt, 0.1);
      while (acumulador >= PASSO) {
        fisica(PASSO);
        acumulador -= PASSO;
      }
      // Dragon 2: no pouso, uma fumacinha rasteira
      if (D2) {
        for (const p of pinos) {
          if (p.estado === CAINDO && p.queda >= 1 && !p.fumaca) {
            p.fumaca = true;
            fumacaD2(p);
          }
        }
      }
      for (const p of pinos) if (p.entrada < 1) p.entrada = Math.min(1, p.entrada + dt / 0.32);

      // teclado: posição e mira
      if (fase === "pronta" && !arrastando) {
        const lado = (teclas.dir ? 1 : 0) - (teclas.esq ? 1 : 0);
        if (lado) {
          const limite = (g.bumper || 0.5) - g.raioBola;
          bola.x = lim(bola.x + lado * 0.55 * dt, -limite, limite);
        }
        const mira = (teclas.miraDir ? 1 : 0) - (teclas.miraEsq ? 1 : 0);
        if (mira) miraTeclado = lim(miraTeclado + mira * 0.35 * dt, -0.3, 0.3);
      }

      // rastro da bola
      if (bola.estado === "rolando") {
        rastroT += dt;
        if (rastroT > 1 / 60) {
          rastroT = 0;
          rastroX[rastroI] = bola.x;
          rastroZ[rastroI] = bola.z;
          rastroI = (rastroI + 1) % RASTRO;
          rastroN = Math.min(RASTRO, rastroN + 1);
        }
        if (bola.fogo && Math.random() < 0.7) {
          projetar(bola.x, bola.z);
          const r = raioBolaTela(PY);
          particula({
            tipo: "chama", x: PX + (Math.random() - 0.5) * r, y: PY - r, vx: (Math.random() - 0.5) * 40,
            vy: -60 - Math.random() * 60, g: 0, rot: 0, vr: 0, tam: r * 0.9, vida: 0.35,
          });
        }
      } else if (rastroN > 0) {
        rastroT += dt;
        if (rastroT > 1 / 60) {
          rastroT = 0;
          rastroN--;
        }
      }

      // personagens e efeitos
      for (let i = 0; i < 2; i++) {
        festa[i] = Math.max(0, festa[i] - dt);
        triste[i] = Math.max(0, triste[i] - dt);
        bumperBrilho[i] = Math.max(0, bumperBrilho[i] - dt * 2.5);
      }
      zoomSoco = Math.max(0, zoomSoco - dt * 0.22);
      tCanaleta += dt;
      if (canaletaModo !== "normal" && tCanaleta > 2.9) canaletaModo = "normal";
      for (let f = flash, ant = null; f; f = f.prox) {
        f.t += dt;
        if (f.t >= f.dur) {
          if (ant) ant.prox = f.prox;
          else flash = f.prox;
        } else ant = f;
      }
      for (let i = avisos.length - 1; i >= 0; i--) {
        avisos[i].t += dt;
        if (avisos[i].t > avisos[i].dur + 0.35) avisos.splice(i, 1);
      }
      for (let i = parts.length - 1; i >= 0; i--) {
        const q = parts[i];
        q.t += dt;
        if (q.t >= q.vida) {
          parts[i] = parts[parts.length - 1];
          parts.pop();
          continue;
        }
        q.vy += q.g * dt;
        q.x += q.vx * dt;
        q.y += q.vy * dt;
        q.rot += q.vr * dt;
      }

      // ------------------------------------------------ a jogada
      if (fase === "montando") {
        if (tFase > 0.75) {
          fase = "pronta";
          tFase = 0;
        }
      } else if (fase === "pronta") {
        tParado = arrastando ? 0 : tParado + dt;
      } else if (fase === "rolando") {
        if (bola.estado === "fim") tBolaFim += dt;
        let parado = true;
        for (const p of pinos) {
          if (p.estado === CAINDO && p.queda < 1) parado = false;
          if (p.estado === EM_PE && p.vx * p.vx + p.vz * p.vz > 1e-4) parado = false;
        }
        const pronto = bola.estado === "fim" && ((parado && tBolaFim > 0.45) || tBolaFim > 1.8);
        if (pronto && D2 && !tabelaFeita) {
          tabelaFeita = true;
          if (talvezDeTabela()) return;
        }
        if (pronto || tFase > 7) {
          const r = contar();
          for (const p of pinos) p.protegido = false;
          reagir(r);
          fase = "resultado";
          tFase = 0;
          // a pausa do resultado (game.gd: ESPERA_STRIKE_S; principal.gd)
          resultadoDur = r.tipo === "strike" ? (KIDS ? 2.4 : 1.9) : r.tipo === "spare" ? 1.7 : 1.4;
        }
      } else if (fase === "resultado") {
        if (tFase > resultadoDur) {
          const passo = proximoPasso();
          if (passo === "fim") {
            fase = "encerrando";
            tFase = 0;
          } else if (passo === "quadroNovo") {
            iQuadro++;
            abrirQuadro(false);
          } else if (passo === "rackNovo") {
            montarRack(true);
            bolaNaMao();
            pinosAntes = 10;
            fase = "montando";
            tFase = 0;
            api.placar({ info: infoPlacar() });
            api.som("nota");
          } else {
            // segunda bola: os caídos já foram varridos, os em pé ficam onde estão
            for (const p of pinos) {
              if (p.estado !== EM_PE) {
                p.estado = FORA;
                p.alfa = 0;
              }
              p.vx = p.vz = 0;
            }
            bolaNaMao();
            fase = "pronta";
            tFase = 0;
            api.placar({ info: infoPlacar() });
          }
        }
      } else if (fase === "encerrando") {
        if (tFase > 0.6) terminarPartida();
      }
    }

    /* Strike Kids: no meio da pista, a 1ª bola jogada no centro sorteia se
       vai ser strike; se for, ela engancha de leve para o bolso (entre o 1
       e o 3, ou o 1 e o 2) e a física faz o resto */
    function planejarKids() {
      if (V.assistencia !== "tabela" || bola.planejada || bola.estado !== "rolando" || bola.z < zP * 0.35) return;
      bola.planejada = true;
      if (pinosAntes !== 10 || bola.canaleta || bola.vz <= 0) return;
      const inc = bola.vx / bola.vz;
      const xPrev = bola.x + inc * (zP - bola.z);
      if (Math.abs(xPrev) > 0.14 || Math.random() >= STRIKE_NO_CENTRO) return;
      const lado = Math.abs(xPrev) > 0.01 ? Math.sign(xPrev) : Math.random() < 0.5 ? -1 : 1;
      bola.curva = 0;
      bola.plano = { x0: bola.x, z0: bola.z, inc, z1: zP - 0.3, alvo: lado * (0.042 + Math.random() * 0.018) };
    }

    /* Dragon 2: às vezes um vizinho dos que caíram vai junto (game.gd:
       _talvez_derrubar_um_de_tabela) -- nunca no destino sorteado */
    function talvezDeTabela() {
      if (jogadaForcada || bola.canaleta || Math.random() >= CHANCE_DE_TABELA) return false;
      if (emPe() === pinosAntes || emPe() === 0) return false;
      const candidatos = [];
      for (const p of pinos) {
        if (p.estado === EM_PE) continue;
        for (const n of VIZINHOS[p.n]) {
          if (pinos[n - 1].estado === EM_PE && !candidatos.includes(n)) candidatos.push(n);
        }
      }
      if (!candidatos.length) return false;
      const n = candidatos[Math.floor(Math.random() * candidatos.length)];
      agenda.push({ t: relogio + 0.1 + Math.random() * 0.12, tipo: "tabela", n, x: bola.x });
      tBolaFim = -0.45; // espera o vizinho cair antes de contar
      return true;
    }

    /* ======================================================================
       DESENHO — comum às três pistas
       ====================================================================== */
    let escalaCache = 0;
    let fundoCache = null;
    let fundoCacheNome = "";
    let fundoCacheCompleto = false;
    let tFundoTentativa = 0;
    let tintas = null;
    let gradPinoKids = null;

    function escalaDo(ctx) {
      const m = ctx.getTransform ? ctx.getTransform() : null;
      return lim(m ? Math.round(Math.hypot(m.a, m.b) * 4) / 4 : 1, 1, 2);
    }

    function desenhar(ctx) {
      const tDecor = agora() / 1000;
      ctx.save();
      if (zoomSoco > 0.0005) {
        // o soco de zoom do contato, centrado no pino 1
        const s = 1 + zoomSoco;
        const fy = yDe(zP);
        ctx.translate(cx, fy);
        ctx.scale(s, s);
        ctx.translate(-cx, -fy);
      }
      if (KIDS) desenharCenarioKids(ctx, tDecor);
      else desenharPistaDragon(ctx, tDecor);
      desenharMiraTeclado(ctx);
      desenharRastro(ctx);
      desenharObjetos(ctx, tDecor);
      ctx.restore();

      desenharParticulas(ctx, false);
      if (KIDS) {
        desenharPersonagens(ctx, tDecor);
        desenharHudKids(ctx);
      } else {
        desenharHudDragon(ctx);
      }
      desenharDica(ctx, tDecor);
      desenharParticulas(ctx, true);
      desenharAvisos(ctx);
      for (let f = flash; f; f = f.prox) {
        const a = f.alfa * (1 - f.t / f.dur);
        if (a <= 0) continue;
        ctx.save();
        ctx.globalAlpha = a;
        ctx.fillStyle = f.cor;
        ctx.fillRect(0, 0, W, H);
        ctx.restore();
      }
    }

    /* pinos e bola de trás para a frente */
    const ordem = [];
    function desenharObjetos(ctx, tDecor) {
      ordem.length = 0;
      for (const p of pinos) if (p.estado !== FORA && p.entrada > 0) ordem.push(p);
      ordem.push(bola);
      // poucos itens: ordenação por inserção, sem criar nada
      for (let i = 1; i < ordem.length; i++) {
        const o = ordem[i];
        let j = i - 1;
        while (j >= 0 && ordem[j].z < o.z) {
          ordem[j + 1] = ordem[j];
          j--;
        }
        ordem[j + 1] = o;
      }
      // sombras primeiro (no chão, por baixo de tudo)
      for (const o of ordem) {
        if (o === bola) sombraBola(ctx);
        else sombraPino(ctx, o);
      }
      for (const o of ordem) {
        if (o === bola) desenharBola(ctx, tDecor);
        else if (KIDS) desenharPinoKids(ctx, o, tDecor);
        else if (D2) desenharPinoD2(ctx, o);
        else desenharPinoDragon(ctx, o);
      }
    }

    // entrada do rack novo: os pinos descem e aparecem
    const entradaAlfa = (p) => lim(p.entrada, 0, 1);
    const entradaDy = (p) => (1 - suave(lim(p.entrada, 0, 1))) * -140;

    function sombraPino(ctx, p) {
      projetar(p.x, p.z);
      const e = entradaAlfa(p);
      const r = g.raioPino * PW;
      const deita = p.estado === CAINDO ? p.queda : 0;
      ctx.save();
      ctx.globalAlpha = (KIDS ? 0.26 : 0.38) * p.alfa * e;
      ctx.fillStyle = KIDS ? "#5a2e0a" : "#000";
      ctx.beginPath();
      ctx.ellipse(PX + p.dx * deita * r * 1.6, PY + 1, r * (1.15 + deita * 0.9), r * 0.42, 0, 0, TAU);
      ctx.fill();
      ctx.restore();
    }

    /* eixo do pino na tela, da base até a cabeça: tomba em 3D e encurta
       quando deita rumo ao fundo */
    let EX = 0;
    let EY = 0;
    let EL = 0;
    let EA = 0;
    function eixoPino(p, alturaTela, tDecor) {
      projetar(p.x, p.z);
      const bx = PX;
      const by = PY;
      let ax = 0;
      let ay = -alturaTela;
      if (p.estado === CAINDO) {
        const th = Math.pow(p.queda, 1.35) * (Math.PI / 2);
        const L = g.alturaPino;
        const s = Math.sin(th);
        projetar(p.x + p.dx * L * s, p.z + p.dz * L * s);
        ax = PX - bx;
        ay = PY - by - Math.cos(th) * alturaTela;
      } else if (p.bal > 0.01) {
        const a = Math.sin(p.balFase) * p.bal * 0.2;
        ax = Math.sin(a) * alturaTela;
        ay = -Math.cos(a) * alturaTela;
      } else if (KIDS && fase === "pronta") {
        // os pinos do Strike Kids se mexem de leve, esperando a bola
        const a = Math.sin(tDecor * 2.2 + p.n * 1.7) * 0.025;
        ax = Math.sin(a) * alturaTela;
        ay = -Math.cos(a) * alturaTela;
      }
      EX = bx;
      EY = by;
      EL = Math.hypot(ax, ay);
      EA = Math.atan2(ax, -ay);
    }

    function sombraBola(ctx) {
      if (bola.estado === "fim") return;
      projetar(bola.x, bola.z);
      const r = raioBolaTela(PY);
      ctx.save();
      ctx.globalAlpha = bola.canaleta ? 0.2 : 0.35;
      ctx.fillStyle = KIDS ? "#5a2e0a" : "#000";
      ctx.beginPath();
      ctx.ellipse(PX, PY + 1, r * 1.05, r * 0.36, 0, 0, TAU);
      ctx.fill();
      ctx.restore();
    }

    function desenharBola(ctx, tDecor) {
      if (bola.estado === "fim") return;
      projetar(bola.x, bola.z);
      const r = raioBolaTela(PY);
      const x = PX;
      let y = PY - r * 0.92 - bola.ergue;
      if (bola.canaleta) y += r * 0.35;
      // no fosso ela some
      const a = bola.z > zFim ? lim(1 - (bola.z - zFim) / (g.raioBola * 2), 0, 1) : 1;
      if (a <= 0) return;
      ctx.save();
      ctx.globalAlpha = a;
      if (fase === "pronta" && !arrastando && comecou) {
        // a bola chamando a jogada
        const pulso = 0.5 + 0.5 * Math.sin(tDecor * 4);
        ctx.strokeStyle = KIDS ? "rgba(255,246,168,.9)" : D2 ? "rgba(90,170,255,.85)" : "rgba(255,190,60,.85)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(x, y, r + 6 + pulso * 6, 0, TAU);
        ctx.stroke();
      }
      if (KIDS) desenharBolaKids(ctx, x, y, r);
      else desenharBolaSprite(ctx, x, y, r);
      ctx.restore();
    }

    function desenharRastro(ctx) {
      if (rastroN < 2) return;
      ctx.save();
      ctx.lineCap = "round";
      if (KIDS) {
        // rastro de arco-íris (o do replay do Strike Kids)
        for (let c = 0; c < 6; c++) {
          ctx.strokeStyle = ARCO_IRIS[c];
          for (let i = 1; i < rastroN; i++) {
            const k0 = (rastroI - i - 1 + RASTRO * 2) % RASTRO;
            const k1 = (rastroI - i + RASTRO * 2) % RASTRO;
            projetar(rastroX[k0], rastroZ[k0]);
            const x0 = PX + (c - 2.5) * PW * 0.024;
            const y0 = PY;
            ctx.lineWidth = PW * 0.024;
            projetar(rastroX[k1], rastroZ[k1]);
            ctx.globalAlpha = (1 - i / rastroN) * 0.75;
            ctx.beginPath();
            ctx.moveTo(x0, y0 - 2);
            ctx.lineTo(PX + (c - 2.5) * PW * 0.024, PY - 2);
            ctx.stroke();
          }
        }
      } else {
        // Dragon: brilho dourado; Dragon 2: azul por fora e dourado no miolo
        ctx.globalCompositeOperation = "lighter";
        const camadas = D2 ? RASTRO_D2 : RASTRO_D1;
        for (let c = 0; c < camadas.length; c += 2) {
          ctx.strokeStyle = camadas[c];
          const larg = camadas[c + 1];
          for (let i = 1; i < rastroN; i++) {
            const k0 = (rastroI - i - 1 + RASTRO * 2) % RASTRO;
            const k1 = (rastroI - i + RASTRO * 2) % RASTRO;
            const f = 1 - i / rastroN;
            projetar(rastroX[k0], rastroZ[k0]);
            const x0 = PX;
            const y0 = PY;
            const r = raioBolaTela(PY);
            projetar(rastroX[k1], rastroZ[k1]);
            ctx.globalAlpha = f * (D2 ? 0.55 : 0.35);
            ctx.lineWidth = r * larg * (0.4 + f * 0.6);
            ctx.beginPath();
            ctx.moveTo(x0, y0 - r * 0.5);
            ctx.lineTo(PX, PY - r * 0.5);
            ctx.stroke();
          }
        }
      }
      ctx.restore();
    }

    function desenharParticulas(ctx, frente) {
      for (const q of parts) {
        const naFrente = q.tipo === "confete" || q.tipo === "estrela";
        if (naFrente !== frente) continue;
        const f = q.t / q.vida;
        ctx.save();
        if (q.tipo === "confete") {
          ctx.globalAlpha = Math.min(1, (1 - f) * 3);
          ctx.translate(q.x, q.y);
          ctx.rotate(q.rot);
          ctx.scale(1, Math.abs(Math.cos(q.rot * 1.7)) * 0.8 + 0.2);
          ctx.fillStyle = q.cor;
          ctx.fillRect(-q.tam / 2, -q.tam * 0.3, q.tam, q.tam * 0.6);
        } else if (q.tipo === "estrela") {
          const tinta = tintas && tintas.estrelas ? tintas.estrelas[q.cor] : null;
          if (tinta) {
            ctx.globalAlpha = Math.min(1, (1 - f) * 2.5);
            ctx.translate(q.x, q.y);
            ctx.rotate(q.rot);
            const s = q.tam * (f < 0.15 ? f / 0.15 : 1);
            ctx.drawImage(tinta, -s / 2, -s / 2, s, s);
          }
        } else if (q.tipo === "chama") {
          if (pronta(img.chama)) {
            ctx.globalCompositeOperation = "lighter";
            ctx.globalAlpha = 1 - f;
            const s = q.tam * (1 - f * 0.5);
            ctx.drawImage(img.chama, q.x - s / 2, q.y - s, s, s * 2);
          }
        } else if (q.tipo === "brasa") {
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = 1 - f;
          ctx.fillStyle = q.cor;
          ctx.beginPath();
          ctx.arc(q.x, q.y, q.tam, 0, TAU);
          ctx.fill();
        } else if (q.tipo === "anel") {
          if (pronta(img.fx)) {
            ctx.globalCompositeOperation = "lighter";
            ctx.globalAlpha = (1 - f) * 0.9;
            const s = q.tam * (1 + q.cresce * f);
            ctx.translate(q.x, q.y);
            ctx.scale(1, 0.32);
            ctx.drawImage(img.fx, 0, 0, 64, 64, -s, -s, s * 2, s * 2);
          }
        } else if (q.tipo === "fx") {
          const fonte = q.tinta && tintas ? tintas[q.tinta] : img.fx;
          if (pronta(img.fx) && fonte) {
            if (q.luz) ctx.globalCompositeOperation = "lighter";
            ctx.globalAlpha = (q.alfa || 1) * (1 - f);
            const s = Math.max(1, q.tam * (1 + q.cresce * f));
            ctx.translate(q.x, q.y);
            ctx.rotate(q.rot);
            if (q.quadro === 4) ctx.drawImage(fonte, 256, 16, 64, 32, -s / 2, -s / 4, s, s / 2);
            else ctx.drawImage(fonte, q.quadro * 64, 0, 64, 64, -s / 2, -s / 2, s, s);
          }
        }
        ctx.restore();
      }
    }

    /* letreiros: as imagens do Strike Kids (hud.gd: letreiro) e os textos
       de arcade do Dragon (game.gd: _animar_label_arcade) */
    function desenharAvisos(ctx) {
      for (const a of avisos) {
        const t0 = a.t;
        ctx.save();
        if (a.faixa) desenharFaixaVez(ctx, a);
        else if (a.img) desenharLetreiro(ctx, a, t0);
        else if (a.texto) desenharTextoArcade(ctx, a, t0);
        ctx.restore();
      }
    }

    function desenharLetreiro(ctx, a, t0) {
      const im = img[a.img];
      if (!pronta(im)) return;
      // entra girando de -12° e passa do tamanho (TRANS_BACK), assenta,
      // respira e sai subindo
      let esc;
      let rot = 0;
      let dy = 0;
      let alfa = 1;
      if (t0 < 0.22) {
        esc = 1.18 * voltaElastica(t0 / 0.22);
        rot = mistura(-12, 3, t0 / 0.22);
      } else if (t0 < 0.4) {
        esc = mistura(1.18, 1, suave((t0 - 0.22) / 0.18));
        rot = mistura(3, 0, (t0 - 0.22) / 0.18);
      } else {
        esc = 1 + 0.05 * Math.min(1, (t0 - 0.4) / (a.dur * 0.5));
      }
      if (t0 > a.dur) {
        const s = Math.min(1, (t0 - a.dur) / 0.3);
        dy = -120 * s * s;
        alfa = 1 - s;
      }
      const larg = Math.min(a.larg || 460, W * 0.9);
      const alt = (larg * im.naturalHeight) / im.naturalWidth;
      ctx.save();
      ctx.globalAlpha = lim(alfa, 0, 1);
      ctx.translate(W / 2, a.y + dy);
      ctx.rotate((rot * Math.PI) / 180);
      ctx.scale(Math.max(0.001, esc), Math.max(0.001, esc));
      ctx.drawImage(im, -larg / 2, -alt / 2, larg, alt);
      ctx.restore();
      if (a.sub && t0 > 0.18) {
        const s2 = Math.max(0.001, voltaElastica(Math.min(1, (t0 - 0.18) / 0.3)));
        ctx.globalAlpha = lim(t0 > a.dur ? 1 - (t0 - a.dur) / 0.3 : 1, 0, 1);
        ctx.translate(W / 2, a.y + alt / 2 + 26 + dy);
        ctx.scale(s2, s2);
        api.texto(ctx, a.sub, 0, 0, { tamanho: 40, cor: "#fff", contorno: MARINHO, peso: 800 });
      }
    }

    function desenharTextoArcade(ctx, a, t0) {
      const pico = a.strike ? 1.28 : 1.1;
      const ini = a.strike ? 0.44 : 0.58;
      let esc = 1;
      let alfa = 1;
      if (t0 < 0.16) {
        esc = mistura(ini, pico, voltaElastica(t0 / 0.16));
        alfa = Math.min(1, t0 / 0.1);
      } else if (t0 < 0.28) {
        esc = mistura(pico, 1, suave((t0 - 0.16) / 0.12));
      }
      if (t0 > a.dur) {
        const s = Math.min(1, (t0 - a.dur) / 0.22);
        alfa = 1 - s;
        esc = mistura(1, 0.96, s);
      }
      ctx.globalAlpha = lim(alfa, 0, 1);
      ctx.translate(W / 2, a.y);
      ctx.font = `800 ${a.tam}px Poppins, Manrope, system-ui, sans-serif`;
      const largura = ctx.measureText(a.texto).width;
      const caber = Math.min(1, (W * 0.92) / (largura + a.tam * 0.3));
      ctx.scale(Math.max(0.001, esc * caber), Math.max(0.001, esc * caber));
      // sombra deslocada (5, 5), contorno grosso escuro e o brilho da cor
      api.texto(ctx, a.texto, 6, 6, { tamanho: a.tam, cor: "rgba(0,0,0,.7)", peso: 800 });
      ctx.shadowColor = a.cor;
      ctx.shadowBlur = a.strike ? 34 : 22;
      api.texto(ctx, a.texto, 0, 0, { tamanho: a.tam, cor: a.cor, contorno: "#030306", peso: 800 });
      ctx.shadowBlur = 0;
      api.texto(ctx, a.texto, 0, 0, { tamanho: a.tam, cor: a.cor, peso: 800 });
    }

    /* "ARRASTE E SOLTE": até a primeira jogada, e de novo se a pessoa
       ficar parada um tempo */
    function desenharDica(ctx, tDecor) {
      if (fase !== "pronta" || arrastando || !comecou || (dicaVista && tParado < 6)) return;
      projetar(bola.x, 0);
      const r = raioBolaTela(PY);
      const x = PX;
      const y0 = PY - r;
      const ciclo = (tDecor % 1.4) / 1.4;
      const sobe = suave(Math.min(1, ciclo / 0.75));
      const some = ciclo < 0.85 ? 1 : 1 - (ciclo - 0.85) / 0.15;
      ctx.save();
      ctx.lineWidth = 5;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = KIDS ? "#fff" : "#ffd23f";
      for (let i = 0; i < 3; i++) {
        const yy = y0 - 34 - i * 24 - sobe * 12;
        ctx.globalAlpha = some * (0.95 - i * 0.22);
        ctx.beginPath();
        ctx.moveTo(x - 15, yy + 11);
        ctx.lineTo(x, yy);
        ctx.lineTo(x + 15, yy + 11);
        ctx.stroke();
      }
      // o dedo subindo
      const yd = y0 + 22 - sobe * 120;
      ctx.globalAlpha = some * 0.95;
      ctx.fillStyle = "rgba(255,255,255,.92)";
      ctx.strokeStyle = KIDS ? MARINHO : "#000";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(x + 26, yd + 16, 15, 0, TAU);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
      // o texto numa placa, para ler em cima da pista
      const yt = y0 - 142;
      ctx.save();
      ctx.fillStyle = KIDS ? "rgba(11,31,69,.72)" : "rgba(3,5,11,.75)";
      caminhoArredondado(ctx, W / 2 - 200, yt - 22, 400, 66, 18);
      ctx.fill();
      ctx.restore();
      const texto = KIDS ? "ARRASTE A BOLA E SOLTE!" : "ARRASTE PARA MIRAR E SOLTE!";
      api.texto(ctx, texto, W / 2, yt - 2, { tamanho: 23, cor: KIDS ? "#fff" : "#ffe9a8", peso: 800 });
      api.texto(ctx, "teclado: ← → posição · A D mira · espaço lança", W / 2, yt + 26, {
        tamanho: 14, cor: "rgba(255,255,255,.85)", peso: 600,
      });
    }

    /* mira do teclado: setinha pontilhada */
    function desenharMiraTeclado(ctx) {
      if (!usouTeclado || fase !== "pronta" || arrastando) return;
      ctx.save();
      ctx.fillStyle = KIDS ? "rgba(255,255,255,.85)" : "rgba(255,220,90,.9)";
      for (let i = 1; i <= 9; i++) {
        const z = (i / 9) * zP * 0.85;
        projetar(bola.x + miraTeclado * z, z);
        ctx.beginPath();
        ctx.arc(PX, PY, Math.max(2, PW * 0.012), 0, TAU);
        ctx.fill();
      }
      ctx.restore();
    }

    /* o mapa dos pinos (hud.gd: mostrar_mapa / game.gd: MAPA DOS PINOS) */
    function desenharMapa(ctx, x, y, w, h, e) {
      ctx.save();
      ctx.fillStyle = e.fundo;
      caminhoArredondado(ctx, x, y, w, h, 14);
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = e.borda;
      if (e.brilho) {
        ctx.shadowColor = e.borda;
        ctx.shadowBlur = 10;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;
      api.texto(ctx, e.titulo, x + w / 2, y + 14, { tamanho: 11, cor: e.corTitulo, peso: 800 });
      const passoX = w / 4.6;
      const passoY = (h - 30) / 3.5;
      const r = Math.min(passoX, passoY) * 0.4;
      for (const p of pinos) {
        const k = FILEIRAS[p.fileira].indexOf(p.n);
        const px = x + w / 2 + (k - p.fileira / 2) * passoX;
        const py = y + h - 15 - p.fileira * passoY;
        const de = p.estado === EM_PE;
        ctx.fillStyle = de ? e.emPe : e.caido;
        ctx.beginPath();
        ctx.arc(px, py, r, 0, TAU);
        ctx.fill();
        if (de) {
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = e.contorno;
          ctx.stroke();
        }
        if (e.numeros) api.texto(ctx, String(p.n), px, py + 0.5, { tamanho: r * 1.05, cor: de ? "#04140a" : "rgba(255,255,255,.35)", peso: 800 });
      }
      ctx.restore();
    }

    /* ======================================================================
       DESENHO — STRIKE KIDS
       ====================================================================== */
    function prepararTintasKids() {
      if (tintas || !pronta(img.estrela)) return;
      tintas = { estrelas: CORES_BICHOS.map((c) => tingir(img.estrela, c)) };
    }

    function vDe(z) {
      // a textura da pista vai da linha de falta (v = 0) ao fim da mesa
      // (v = 1); o pino 1 do desenho fica em v = 0,879 e a última fileira em
      // 0,962 -- as marcas do chão caem embaixo dos pinos
      if (z <= zP) return lim((0.879 * z) / zP, 0.002, 0.879);
      return lim(0.879 + ((z - zP) * 0.083) / fundoRack, 0, 0.998);
    }

    function quadAoLongo(x, x0, x1, z0, z1) {
      projetar(x0, z0);
      x.moveTo(PX, PY);
      projetar(x1, z0);
      x.lineTo(PX, PY);
      projetar(x1, z1);
      x.lineTo(PX, PY);
      projetar(x0, z1);
      x.lineTo(PX, PY);
      x.closePath();
    }

    /* o cenário parado (céu, chão, boca dos pinos, pista, calhas e
       para-choques) é pintado uma vez por rodada numa tela à parte */
    function montarFundoKids(nome, esc) {
      const x = fundoCache.getContext("2d");
      x.setTransform(esc, 0, 0, esc, 0, 0);
      x.clearRect(0, 0, W, H);
      x.imageSmoothingQuality = "high";
      const cen = CENARIOS[nome];
      const rnd = semente(nome.length * 7919 + 11);
      const yFimMesa = yDe(zFim);
      const yHor = yFimMesa - 40;
      let completo = true;

      // céu
      let gr = x.createLinearGradient(0, 0, 0, yHor);
      gr.addColorStop(0, cen.ceu[0]);
      gr.addColorStop(0.6, cen.ceu[1]);
      gr.addColorStop(1, cen.ceu[2]);
      x.fillStyle = gr;
      x.fillRect(0, 0, W, yHor + 4);
      if (nome === "espaco") {
        if (pronta(img.estrelas_ceu)) {
          x.globalAlpha = 0.9;
          x.drawImage(img.estrelas_ceu, 0, 0, W, (W * img.estrelas_ceu.naturalHeight) / img.estrelas_ceu.naturalWidth);
          x.globalAlpha = 1;
        } else completo = false;
        // planeta de anel
        x.save();
        x.translate(440, 196);
        x.fillStyle = "#FF9F2E";
        x.beginPath();
        x.arc(0, 0, 26, 0, TAU);
        x.fill();
        x.fillStyle = "rgba(255,255,255,.25)";
        x.beginPath();
        x.arc(-8, -8, 10, 0, TAU);
        x.fill();
        x.strokeStyle = "#FFE14D";
        x.lineWidth = 4;
        x.beginPath();
        x.ellipse(0, 0, 44, 10, -0.3, 0, TAU);
        x.stroke();
        x.restore();
      } else if (nome === "mar") {
        // raios de sol dentro d'água
        x.save();
        x.globalAlpha = 0.16;
        x.fillStyle = "#E6FFF8";
        for (let i = 0; i < 6; i++) {
          const xx = 40 + i * 95;
          x.beginPath();
          x.moveTo(xx, 0);
          x.lineTo(xx + 40, 0);
          x.lineTo(xx + 120, yHor);
          x.lineTo(xx + 50, yHor);
          x.closePath();
          x.fill();
        }
        x.restore();
      } else if (nome === "dinos") {
        // o vulcão com lava
        x.fillStyle = "#7a5a46";
        x.beginPath();
        x.moveTo(330, yHor + 4);
        x.lineTo(420, 156);
        x.lineTo(450, 156);
        x.lineTo(540, yHor + 4);
        x.closePath();
        x.fill();
        x.fillStyle = "#FF8A1E";
        x.beginPath();
        x.moveTo(418, 160);
        x.quadraticCurveTo(436, 146, 452, 160);
        x.lineTo(446, 196);
        x.lineTo(431, 178);
        x.lineTo(424, 206);
        x.closePath();
        x.fill();
      }

      // morros no horizonte
      x.fillStyle = misturaCor(cen.chao[1], cen.ceu[2], 0.35);
      x.beginPath();
      x.moveTo(0, yHor + 6);
      for (let i = 0; i <= 6; i++) {
        const xx = (i / 6) * W;
        x.quadraticCurveTo(xx - 45, yHor - 30 - rnd() * 30, xx, yHor + 2);
      }
      x.lineTo(W, yHor + 10);
      x.lineTo(0, yHor + 10);
      x.fill();

      // chão com florzinhas / crateras / conchinhas (tools/assar_chao.py)
      gr = x.createLinearGradient(0, yHor, 0, H);
      gr.addColorStop(0, cen.chao[1]);
      gr.addColorStop(1, cen.chao[0]);
      x.fillStyle = gr;
      x.fillRect(0, yHor, W, H - yHor);
      for (let i = 0; i < 110; i++) {
        const yy = yHor + 8 + Math.pow(rnd(), 0.8) * (H - yHor);
        const lado = rnd() < 0.5 ? -1 : 1;
        const meiaPista = lDe(yy) * (0.5 + g.calha) + 8;
        const xx = cx + lado * (meiaPista + rnd() * (W / 2));
        if (xx < -10 || xx > W + 10) continue;
        const s = 2 + ((yy - yHor) / (H - yHor)) * 5;
        x.fillStyle = cen.flor[i % 2];
        x.globalAlpha = nome === "espaco" ? 0.45 : 0.85;
        x.beginPath();
        if (nome === "espaco") x.ellipse(xx, yy, s * 2.2, s * 0.9, 0, 0, TAU);
        else x.arc(xx, yy, s, 0, TAU);
        x.fill();
      }
      x.globalAlpha = 1;

      // a BOCA DOS PINOS: gabinete, colunas e a cortina da bola
      const wFim = lDe(yFimMesa);
      const bocaX0 = cx - wFim * (0.5 + g.calha) - 10;
      const bocaX1 = cx + wFim * (0.5 + g.calha) + 10;
      const bocaTopo = yFimMesa - 98;
      x.fillStyle = cen.gabinete;
      caminhoArredondado(x, bocaX0 - 16, bocaTopo - 16, bocaX1 - bocaX0 + 32, yFimMesa - bocaTopo + 22, 26);
      x.fill();
      x.strokeStyle = MARINHO;
      x.lineWidth = 3;
      x.stroke();
      gr = x.createLinearGradient(0, bocaTopo, 0, yFimMesa);
      gr.addColorStop(0, "#1b1036");
      gr.addColorStop(1, "#05030d");
      x.fillStyle = gr;
      caminhoArredondado(x, bocaX0, bocaTopo, bocaX1 - bocaX0, yFimMesa - bocaTopo + 4, 18);
      x.fill();
      if (pronta(img.cortina)) {
        x.save();
        caminhoArredondado(x, bocaX0, bocaTopo, bocaX1 - bocaX0, yFimMesa - bocaTopo + 4, 18);
        x.clip();
        const ch = img.cortina.naturalHeight / 4;
        x.drawImage(img.cortina, 0, cen.faixa * ch, img.cortina.naturalWidth, ch, bocaX0, bocaTopo, bocaX1 - bocaX0, 64);
        gr = x.createLinearGradient(0, bocaTopo + 50, 0, bocaTopo + 80);
        gr.addColorStop(0, "rgba(0,0,0,.55)");
        gr.addColorStop(1, "rgba(0,0,0,0)");
        x.fillStyle = gr;
        x.fillRect(bocaX0, bocaTopo + 50, bocaX1 - bocaX0, 30);
        x.restore();
      } else completo = false;
      // os dois pilares, com o enfeite da fase em cima (temas.gd: _nos_pilares)
      for (const lado of [-1, 1]) {
        const xc = lado < 0 ? bocaX0 - 34 : bocaX1 + 34;
        x.fillStyle = cen.coluna;
        caminhoArredondado(x, xc - 13, bocaTopo - 10, 26, yFimMesa - bocaTopo + 26, 8);
        x.fill();
        x.strokeStyle = MARINHO;
        x.lineWidth = 2.5;
        x.stroke();
        x.fillStyle = "rgba(255,255,255,.25)";
        x.fillRect(xc - 8, bocaTopo - 4, 5, yFimMesa - bocaTopo + 14);
        x.fillStyle = cen.portal[0];
        x.strokeStyle = MARINHO;
        x.lineWidth = 2.5;
        if (nome === "parque") {
          // torre listrada com telhado de cone e bandeirinha
          x.beginPath();
          x.moveTo(xc - 18, bocaTopo - 10);
          x.lineTo(xc, bocaTopo - 46);
          x.lineTo(xc + 18, bocaTopo - 10);
          x.closePath();
          x.fill();
          x.stroke();
          x.fillStyle = cen.portal[1];
          x.fillRect(xc, bocaTopo - 62, 14, 9);
          x.fillRect(xc - 1, bocaTopo - 62, 2, 18);
        } else if (nome === "dinos") {
          // ovo de dinossauro
          x.beginPath();
          x.ellipse(xc, bocaTopo - 26, 13, 17, 0, 0, TAU);
          x.fill();
          x.stroke();
          x.fillStyle = cen.portal[1];
          x.beginPath();
          x.arc(xc - 4, bocaTopo - 30, 3, 0, TAU);
          x.arc(xc + 5, bocaTopo - 20, 2.5, 0, TAU);
          x.fill();
        } else {
          // estrela (espaço) ou estrela-do-mar (mar)
          estrelaPath(x, xc, bocaTopo - 28, 18, 8, 5);
          x.fill();
          x.stroke();
        }
      }

      // calhas de doce (listras)
      const zIni = zDe(H + 2);
      const passoZ = 0.07;
      for (const lado of [-1, 1]) {
        let k = 0;
        for (let z = zIni; z < zFim; z += passoZ, k++) {
          x.beginPath();
          quadAoLongo(x, lado * 0.5, lado * (0.5 + g.calha), z, Math.min(zFim, z + passoZ + 0.004));
          x.fillStyle = cen.calha[k % 2];
          x.fill();
        }
        x.beginPath();
        quadAoLongo(x, lado * 0.5, lado * (0.5 + g.calha * 0.35), zIni, zFim);
        x.fillStyle = "rgba(0,0,0,.18)";
        x.fill();
      }
      // a pista: a textura assada do jogo (texturas/pista_pronta.png), linha
      // a linha em perspectiva
      if (pronta(img.pista)) {
        const tex = img.pista;
        const passo = 1 / esc;
        for (let y = Math.floor(yFimMesa); y < H; y += passo) {
          const z = zDe(y + passo / 2);
          const w = lDe(y + passo / 2);
          x.drawImage(tex, 0, vDe(z) * tex.naturalHeight, tex.naturalWidth, 1, cx - w / 2, y, w, passo + 0.5 / esc);
        }
        // verniz: o portal colorido refletido no fundo da pista
        gr = x.createLinearGradient(0, yFimMesa, 0, yDe(zP * 0.6));
        gr.addColorStop(0, hexA(cen.portal[0], 0.38));
        gr.addColorStop(0.5, hexA(cen.portal[1], 0.12));
        gr.addColorStop(1, hexA(cen.portal[1], 0));
        x.fillStyle = gr;
        x.beginPath();
        quadAoLongo(x, -0.5, 0.5, zP * 0.6, zFim);
        x.fill();
      } else {
        completo = false;
        x.fillStyle = "#E79A4C";
        x.beginPath();
        quadAoLongo(x, -0.5, 0.5, zIni, zFim);
        x.fill();
      }
      // beirada do fosso
      x.fillStyle = "rgba(0,0,0,.35)";
      x.beginPath();
      quadAoLongo(x, -0.5 - g.calha, 0.5 + g.calha, zFim - 0.02, zFim);
      x.fill();
      // neon das bordas, sempre aceso na cor do cenário
      x.save();
      x.strokeStyle = cen.neon;
      x.shadowColor = cen.neon;
      x.shadowBlur = 10;
      x.lineWidth = 3;
      for (const lado of [-1, 1]) {
        x.beginPath();
        projetar(lado * 0.5, zIni);
        x.moveTo(PX, PY);
        projetar(lado * 0.5, zFim);
        x.lineTo(PX, PY);
        x.stroke();
      }
      x.restore();
      // para-choques: um tubo listrado de cada lado, terminando antes dos
      // pinos (a barra varredora passa sem encostar neles)
      const RB = 0.034;
      for (const lado of [-1, 1]) {
        const xb = lado * (0.5 + 0.03);
        let k = 0;
        const passoB = 0.055;
        for (let z = zIni; z < g.fimBumper; z += passoB, k++) {
          const z1 = Math.min(g.fimBumper, z + passoB + 0.003);
          projetar(xb, z);
          const xa = PX;
          const ya = PY;
          const ra = PW * RB;
          projetar(xb, z1);
          const rb = PW * RB;
          x.fillStyle = cen.bumper[k % 2];
          x.beginPath();
          x.moveTo(xa - ra, ya - ra * 1.8);
          x.lineTo(xa + ra, ya - ra * 0.2);
          x.lineTo(PX + rb, PY - rb * 0.2);
          x.lineTo(PX - rb, PY - rb * 1.8);
          x.closePath();
          x.fill();
        }
        projetar(xb, zIni);
        const x0 = PX;
        const y0 = PY;
        const r0 = PW * RB;
        projetar(xb, g.fimBumper);
        const r1 = PW * RB;
        x.strokeStyle = "rgba(255,255,255,.6)";
        x.lineWidth = 2;
        x.beginPath();
        x.moveTo(x0 - r0 * 0.4, y0 - r0 * 1.4);
        x.lineTo(PX - r1 * 0.4, PY - r1 * 1.4);
        x.stroke();
        x.fillStyle = cen.bumper[1];
        x.strokeStyle = MARINHO;
        x.lineWidth = 1.5;
        x.beginPath();
        x.arc(PX, PY - r1, r1 * 1.05, 0, TAU);
        x.fill();
        x.stroke();
      }
      return completo;
    }

    function desenharCenarioKids(ctx, tDecor) {
      prepararTintasKids();
      const esc = escalaDo(ctx);
      if (esc !== escalaCache || fundoCacheNome !== cenario || (!fundoCacheCompleto && tDecor - tFundoTentativa > 0.25)) {
        escalaCache = esc;
        fundoCacheNome = cenario;
        tFundoTentativa = tDecor;
        if (!fundoCache || fundoCache.width !== Math.round(W * esc)) fundoCache = novaTela(W * esc, H * esc);
        fundoCacheCompleto = montarFundoKids(cenario, esc);
      }
      ctx.drawImage(fundoCache, 0, 0, W, H);
      const cen = CENARIOS[cenario];
      const yFimMesa = yDe(zFim);

      // o céu que mexe: sol e lua com carinha, nuvens, baleia e bolhas
      if (cen.astro === "sol" || cen.astro === "lua") {
        const im = cen.astro === "sol" ? img.ceu_sol : img.ceu_lua;
        if (pronta(im)) {
          const pisca = tDecor % 4 < 0.18 ? 1 : 0;
          const s = 92;
          const xs = 74;
          const ys = 168 + Math.sin(tDecor * 1.3) * 5;
          if (cen.astro === "sol") {
            ctx.save();
            ctx.globalAlpha = 0.25;
            ctx.fillStyle = "#FFE7B0";
            ctx.beginPath();
            ctx.arc(xs, ys, s * 0.62 + Math.sin(tDecor * 2) * 4, 0, TAU);
            ctx.fill();
            ctx.restore();
          }
          const meia = im.naturalWidth / 2;
          ctx.drawImage(im, pisca * meia, 0, meia, im.naturalHeight, xs - s / 2, ys - s / 2, s, s);
        }
        if (cenario !== "espaco") {
          ctx.fillStyle = "rgba(255,255,255,.92)";
          for (let i = 0; i < 3; i++) {
            const xn = ((tDecor * (8 + i * 3) + i * 230) % (W + 200)) - 100;
            nuvem(ctx, xn, 128 + i * 36, 1 - i * 0.18);
          }
        } else {
          ctx.fillStyle = "#fff";
          for (let i = 0; i < 14; i++) {
            ctx.globalAlpha = 0.5 + 0.5 * Math.sin(tDecor * (2 + (i % 4)) + i * 2.1);
            ctx.beginPath();
            ctx.arc((i * 137) % W, 90 + ((i * 71) % 150), 1.6, 0, TAU);
            ctx.fill();
          }
          ctx.globalAlpha = 1;
        }
      } else if (cen.astro === "baleia") {
        if (pronta(img.ceu_baleia)) {
          const xb = ((tDecor * 14) % (W + 260)) - 130;
          const yb = 160 + Math.sin(tDecor * 0.9) * 8;
          const olho = tDecor % 5 < 0.2 ? 1 : 0;
          const meia = img.ceu_baleia.naturalWidth / 2;
          ctx.drawImage(img.ceu_baleia, olho * meia, 0, meia, img.ceu_baleia.naturalHeight, xb - 55, yb - 55, 110, 110);
        }
        if (pronta(img.bolha)) {
          for (let i = 0; i < 9; i++) {
            const ciclo = (tDecor * (0.12 + (i % 3) * 0.03) + i * 0.37) % 1;
            const yb = yFimMesa - ciclo * 260;
            const xb = (i * 97 + Math.sin(tDecor * 2 + i) * 10 + 40) % W;
            const s = 10 + (i % 4) * 5;
            ctx.globalAlpha = 0.8 * (1 - ciclo);
            ctx.drawImage(img.bolha, xb - s / 2, yb - s / 2, s, s);
          }
          ctx.globalAlpha = 1;
        }
      }

      // lâmpadas em volta da boca dos pinos, piscando em sequência
      const wFim = lDe(yFimMesa);
      const bocaX0 = cx - wFim * (0.5 + g.calha) - 10;
      const bocaX1 = cx + wFim * (0.5 + g.calha) + 10;
      const bocaTopo = yFimMesa - 98;
      for (let i = 0; i < 14; i++) {
        const xx = mistura(bocaX0 - 4, bocaX1 + 4, i / 13);
        const acesa = Math.floor(tDecor * 6 + i) % 3 === 0;
        ctx.fillStyle = acesa ? CREME : i % 2 ? cen.portal[0] : cen.portal[1];
        ctx.beginPath();
        ctx.arc(xx, bocaTopo - 8, acesa ? 4.5 : 3.5, 0, TAU);
        ctx.fill();
      }

      // luzes correndo pelo neon rumo aos pinos (o convite) e o brilho dos
      // para-choques quando a bola bate
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = cen.neon;
      const rolando = fase === "rolando";
      const zIni = zDe(H);
      for (const lado of [-1, 1]) {
        for (let i = 0; i < 7; i++) {
          const f = (tDecor * (rolando ? 0.9 : 0.35) + i / 7) % 1;
          projetar(lado * 0.5, mistura(zIni, zFim, f));
          ctx.globalAlpha = (rolando ? 1 : 0.6) * (0.5 + 0.5 * Math.sin(f * Math.PI));
          ctx.beginPath();
          ctx.arc(PX, PY, Math.max(2, PW * 0.014), 0, TAU);
          ctx.fill();
        }
        const bb = bumperBrilho[lado < 0 ? 0 : 1];
        if (bb > 0) {
          ctx.globalAlpha = bb * 0.6;
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 6;
          projetar(lado * 0.53, zIni);
          ctx.beginPath();
          ctx.moveTo(PX, PY - PW * 0.034);
          projetar(lado * 0.53, g.fimBumper);
          ctx.lineTo(PX, PY - PW * 0.034);
          ctx.stroke();
        }
      }
      // o brilho que acompanha a bola na jogada
      if (rolando && bola.estado === "rolando") {
        projetar(bola.x, bola.z);
        ctx.globalAlpha = 0.35;
        const gr = ctx.createRadialGradient(PX, PY, 0, PX, PY, PW * 0.3);
        gr.addColorStop(0, cen.neon);
        gr.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = gr;
        ctx.fillRect(PX - PW * 0.3, PY - PW * 0.3, PW * 0.6, PW * 0.6);
      }
      ctx.restore();
    }

    function nuvem(ctx, x, y, s) {
      ctx.beginPath();
      ctx.arc(x, y, 20 * s, 0, TAU);
      ctx.arc(x + 22 * s, y - 10 * s, 24 * s, 0, TAU);
      ctx.arc(x + 48 * s, y, 19 * s, 0, TAU);
      ctx.arc(x + 24 * s, y + 6 * s, 20 * s, 0, TAU);
      ctx.fill();
    }

    /* o pino com carinha: branco com volume, listras vermelhas e o rosto
       (texturas/rosto_pino.png, 4 x 2 expressões) */
    function desenharPinoKids(ctx, p, tDecor) {
      projetar(p.x, p.z);
      const alturaTela = g.alturaPino * PW * 0.9;
      eixoPino(p, alturaTela, tDecor);
      const forma = pinoKids();
      ctx.save();
      ctx.globalAlpha = p.alfa * entradaAlfa(p);
      ctx.translate(EX, EY + entradaDy(p));
      ctx.rotate(EA);
      ctx.scale(alturaTela, Math.max(0.05, EL));
      if (!gradPinoKids) {
        gradPinoKids = ctx.createLinearGradient(-0.18, 0, 0.18, 0);
        gradPinoKids.addColorStop(0, "#b9c7e6");
        gradPinoKids.addColorStop(0.32, "#ffffff");
        gradPinoKids.addColorStop(0.62, "#f1f5fc");
        gradPinoKids.addColorStop(1, "#a9b9da");
      }
      ctx.fillStyle = gradPinoKids;
      ctx.fill(forma);
      ctx.save();
      ctx.clip(forma);
      ctx.fillStyle = "#FF3B50";
      ctx.fillRect(-0.2, -0.665, 0.4, 0.04);
      ctx.fillRect(-0.2, -0.735, 0.4, 0.04);
      if (pronta(img.rostos)) {
        let rosto = 0;                                   // contente
        if (p.estado === CAINDO) rosto = 3;              // tontinho
        else if (fase === "rolando" && bola.estado === "rolando" && bola.z > zP - 0.9) rosto = bola.z > zP - 0.35 ? 5 : 2;
        else if (fase === "resultado") rosto = 4;        // sobrou em pé: comemora
        else if ((tDecor + p.n * 0.37) % 3.5 < 0.15) rosto = 1; // pisca
        const cel = img.rostos.naturalWidth / 4;
        ctx.drawImage(img.rostos, (rosto % 4) * cel, Math.floor(rosto / 4) * cel, cel, cel, -0.19, -0.6, 0.38, 0.38);
      }
      ctx.restore();
      ctx.lineWidth = 0.018;
      ctx.strokeStyle = MARINHO;
      ctx.stroke(forma);
      ctx.restore();
    }

    /* a bola do Bob (vermelha com patinhas) ou da Mia (laranja com
       estrelas): a textura rola por dentro do círculo */
    function desenharBolaKids(ctx, x, y, r) {
      const mia = iQuadro % 2 === 1;
      const tex = mia ? img.bola_mia : img.bola_bob;
      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.fillStyle = mia ? "#FF7A21" : "#E0252F";
      ctx.fill();
      if (pronta(tex)) {
        ctx.clip();
        const tw = tex.naturalWidth;
        const th = tex.naturalHeight;
        const off = ((((bola.giro / TAU) * th * 2) % th) + th) % th;
        const u0 = tw * 0.25 + Math.sin(bola.x * 3) * tw * 0.05;
        const d = r * 2;
        ctx.drawImage(tex, u0, 0, th, th - off, x - r, y - r + (off / th) * d, d, ((th - off) / th) * d);
        if (off > 0.5) ctx.drawImage(tex, u0, th - off, th, off, x - r, y - r, d, (off / th) * d);
      }
      // volume: luz em cima à esquerda, sombra na borda
      const gr = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r);
      gr.addColorStop(0, "rgba(255,255,255,.55)");
      gr.addColorStop(0.35, "rgba(255,255,255,0)");
      gr.addColorStop(0.8, "rgba(0,0,0,.1)");
      gr.addColorStop(1, "rgba(30,0,40,.45)");
      ctx.fillStyle = gr;
      ctx.fillRect(x - r, y - r, r * 2, r * 2);
      ctx.restore();
      ctx.lineWidth = 2;
      ctx.strokeStyle = MARINHO;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.stroke();
    }

    /* Bob e Mia à beira da pista: quem joga fica maior; no strike pulam
       empolgados, no OPS balançam a cabeça */
    function desenharPersonagens(ctx, tDecor) {
      const vez = iQuadro % 2;
      for (let lado = 0; lado < 2; lado++) {
        const nome = lado === 0 ? "bob" : "mia";
        const ativo = vez === lado;
        const em = festa[lado] > 0;
        const im = img[em ? `retrato_${nome}_empolgado` : `retrato_${nome}`];
        if (!pronta(im)) continue;
        const s = ativo ? 132 : 108;
        const xc = lado === 0 ? 58 : W - 58;
        let yb = 598;
        if (em) yb -= Math.abs(Math.sin(tDecor * 9)) * 26 * Math.min(1, festa[lado]);
        else yb -= Math.abs(Math.sin(tDecor * 2.2 + lado)) * 3;
        const rot = triste[lado] > 0 ? Math.sin(tDecor * 16) * 0.09 * Math.min(1, triste[lado]) : 0;
        ctx.save();
        ctx.globalAlpha = ativo ? 1 : 0.88;
        ctx.fillStyle = "rgba(11,31,69,.35)";
        ctx.beginPath();
        ctx.ellipse(xc, 600, s * 0.42, 10, 0, 0, TAU);
        ctx.fill();
        ctx.translate(xc, yb);
        ctx.rotate(rot);
        ctx.drawImage(im, -s / 2, -s, s, s);
        ctx.restore();
        ctx.save();
        ctx.globalAlpha = ativo ? 1 : 0.8;
        ctx.fillStyle = lado === 0 ? COR_BOB : COR_MIA;
        caminhoArredondado(ctx, xc - 34, 604, 68, 26, 13);
        ctx.fill();
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = MARINHO;
        ctx.stroke();
        api.texto(ctx, nome.toUpperCase(), xc, 618, { tamanho: 17, cor: "#fff", contorno: MARINHO, peso: 800 });
        if (ativo && fase === "pronta" && comecou) {
          api.texto(ctx, "SUA VEZ!", xc, 644 + Math.sin(tDecor * 5) * 2, { tamanho: 14, cor: CREME, contorno: MARINHO, peso: 800 });
        }
        ctx.restore();
      }
    }

    /* a faixa "VEZ DO BOB!" / "VEZ DA MIA!" atravessando a tela */
    function desenharFaixaVez(ctx, a) {
      const bob = a.nome === "bob";
      const t0 = a.t;
      const entra = suave(Math.min(1, t0 / 0.25));
      const sai = t0 > a.dur ? suave(Math.min(1, (t0 - a.dur) / 0.3)) : 0;
      ctx.translate(mistura(-W, 0, entra) + sai * W, a.y);
      ctx.fillStyle = bob ? COR_BOB : COR_MIA;
      ctx.beginPath();
      ctx.moveTo(20, -34);
      ctx.lineTo(W - 10, -34);
      ctx.lineTo(W - 34, 34);
      ctx.lineTo(-4, 34);
      ctx.closePath();
      ctx.fill();
      ctx.lineWidth = 4;
      ctx.strokeStyle = MARINHO;
      ctx.stroke();
      const im = img[`retrato_${a.nome}`];
      if (pronta(im)) ctx.drawImage(im, 30, -64, 100, 100);
      api.texto(ctx, bob ? "VEZ DO BOB!" : "VEZ DA MIA!", 300, 2, { tamanho: 40, cor: "#fff", contorno: MARINHO, peso: 800 });
    }

    /* as 5 rodadas em cartõezinhos (estrela no strike, barra no spare) e o
       mapa dos pinos */
    function desenharHudKids(ctx) {
      const w = 52;
      const gap = 8;
      const y0 = 12;
      ctx.save();
      for (let i = 0; i < NQ; i++) {
        const q = quadros[i];
        const x = 12 + i * (w + gap);
        const atual = i === iQuadro && fase !== "fim";
        ctx.fillStyle = atual ? CREME : "rgba(255,255,255,.92)";
        caminhoArredondado(ctx, x, y0, w, 58, 12);
        ctx.fill();
        ctx.lineWidth = atual ? 4 : 2.5;
        ctx.strokeStyle = atual ? "#FFC21A" : MARINHO;
        ctx.stroke();
        if (atual) {
          ctx.lineWidth = 2;
          ctx.strokeStyle = MARINHO;
          caminhoArredondado(ctx, x - 2, y0 - 2, w + 4, 62, 13);
          ctx.stroke();
        }
        ctx.fillStyle = i % 2 ? COR_MIA : COR_BOB;
        caminhoArredondado(ctx, x + 4, y0 + 4, w - 8, 15, 7);
        ctx.fill();
        api.texto(ctx, String(i + 1), x + w / 2, y0 + 12, { tamanho: 12, cor: "#fff", peso: 800 });
        const b = q.bolas;
        if (q.tipos.includes("strike")) {
          if (pronta(img.estrela_placar)) ctx.drawImage(img.estrela_placar, x + w / 2 - 17, y0 + 21, 34, 34);
        } else if (q.tipos.includes("spare")) {
          api.texto(ctx, "/", x + w / 2, y0 + 39, { tamanho: 30, cor: COR_BOB, contorno: MARINHO, peso: 800 });
        } else if (b.length) {
          let soma = 0;
          for (const v of b) soma += v;
          api.texto(ctx, String(soma), x + w / 2, y0 + 39, { tamanho: 24, cor: MARINHO, peso: 800 });
        } else if (pronta(img.estrela_vazia)) {
          ctx.globalAlpha = 0.5;
          ctx.drawImage(img.estrela_vazia, x + w / 2 - 13, y0 + 25, 26, 26);
          ctx.globalAlpha = 1;
        }
      }
      ctx.restore();
      desenharMapa(ctx, W - 132, 12, 120, 100, MAPA_KIDS);
    }

    /* ======================================================================
       DESENHO — DRAGON / DRAGON 2
       ====================================================================== */
    function prepararTintasDragon() {
      if (tintas) return;
      if (!pronta(img.brilho_canaleta) || !pronta(img.brilho_ouro)) return;
      if (D2 && !pronta(img.fx)) return;
      tintas = {
        ciano: tingir(img.brilho_canaleta, "rgb(0,242,255)"),
        vermelho: tingir(img.brilho_canaleta, "rgb(255,0,0)"),
        ouro: tingir(img.brilho_ouro, "rgb(255,224,77)"),
      };
      if (D2) {
        tintas.azulFx = tingir(img.fx, "rgb(110,180,255)");
        tintas.ouroFx = tingir(img.fx, "rgb(255,214,90)");
        tintas.vermelhoFx = tingir(img.fx, "rgb(255,70,70)");
      }
    }

    /* a pista do dragão e o brilho dela (shaders/brilho_pista.shader): luz
       subindo pelas canaletas, pulso geral e o dourado pulsando; vermelho
       no PRA FORA, acelerado no STRIKE */
    function desenharPistaDragon(ctx, tDecor) {
      prepararTintasDragon();
      if (pronta(img.pista)) ctx.drawImage(img.pista, 0, 0, W, H);
      else {
        const gr = ctx.createLinearGradient(0, 0, 0, H);
        gr.addColorStop(0, "#0b1a44");
        gr.addColorStop(1, "#c98a3c");
        ctx.fillStyle = gr;
        ctx.fillRect(0, 0, W, H);
      }
      if (!tintas) return;
      let erro = 0;
      let vel = 1;
      if (canaletaModo === "erro") {
        erro = tCanaleta < 2.2 ? 1 : Math.max(0, 1 - (tCanaleta - 2.2) / 0.7);
        vel = mistura(1, 2.2, erro);
      } else if (canaletaModo === "strike") {
        vel = tCanaleta < 2 ? 3.5 : mistura(3.5, 1, Math.min(1, (tCanaleta - 2) / 0.75));
      }
      faseSobe = (faseSobe + (1 / 60) * 0.6 * vel) % 1;
      const mascara = erro > 0.5 ? tintas.vermelho : tintas.ciano;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = (0.16 + 0.1 * Math.sin(tDecor * 1.7)) * (1 + erro * 0.6);
      ctx.drawImage(mascara, 0, 0, W, H);
      for (let i = 0; i < 3; i++) {
        const f = (faseSobe + i / 3) % 1;
        const yb = H - f * H * 1.1;
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, yb - 120, W, 120);
        ctx.clip();
        ctx.globalAlpha = (canaletaModo === "erro" ? 0.75 : 0.55) * Math.sin(f * Math.PI) * (canaletaModo === "strike" ? 1.4 : 1);
        ctx.drawImage(mascara, 0, 0, W, H);
        ctx.restore();
      }
      ctx.globalAlpha = (0.08 + 0.08 * Math.sin(tDecor * 2.3)) * (1 - erro);
      ctx.drawImage(tintas.ouro, 0, 0, W, H);
      ctx.restore();
    }

    function desenharBolaSprite(ctx, x, y, r) {
      const sheet = img.bola;
      if (!pronta(sheet)) {
        ctx.fillStyle = D2 ? "#1f4fd8" : "#6a2bb8";
        ctx.beginPath();
        ctx.arc(x, y, r, 0, TAU);
        ctx.fill();
        return;
      }
      const n = D2 ? 16 : 8;
      const cel = sheet.naturalWidth / 4;
      // o giro anda com a distância rolada
      const quadro = bola.estado === "pronta" ? 0 : Math.floor((bola.giro / TAU) * n * 0.5) % n;
      const d = r * 2 * 1.03;
      ctx.drawImage(sheet, (quadro % 4) * cel, Math.floor(quadro / 4) * cel, cel, cel, x - d / 2, y - d / 2, d, d);
      if (D2 && bola.estado === "rolando") {
        // brilho azul em volta da bola rolando
        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        const gr = ctx.createRadialGradient(x, y, r * 0.6, x, y, r * 1.7);
        gr.addColorStop(0, "rgba(70,150,255,.35)");
        gr.addColorStop(1, "rgba(70,150,255,0)");
        ctx.fillStyle = gr;
        ctx.fillRect(x - r * 1.7, y - r * 1.7, r * 3.4, r * 3.4);
        ctx.restore();
      }
    }

    /* Dragon: os quadros de queda do pino.tscn (idle, down_left, down_rt e
       strike), escolhidos pelo lado para onde o pino cai na tela */
    function desenharPinoDragon(ctx, p) {
      const sheet = img.pinos;
      if (!pronta(sheet)) return;
      projetar(p.x, p.z);
      const alturaTela = g.alturaPino * PW;
      const cel = sheet.naturalWidth / 6;
      const s = alturaTela / (cel * 0.875);
      ctx.save();
      ctx.globalAlpha = p.alfa * entradaAlfa(p);
      ctx.translate(PX, PY + entradaDy(p));
      if (p.estado === CAINDO) {
        const q = p.queda;
        let col;
        let lin;
        if (p.lado > 0) {
          col = Math.min(5, Math.floor(q * 5.99));
          lin = 0;
        } else if (p.lado < 0) {
          col = Math.min(4, Math.floor(q * 4.99));
          lin = 1;
        } else if (q < 0.5) {
          // rumo ao fundo: começa tombando e termina nos quadros "strike"
          col = Math.min(3, Math.floor(q * 2 * 3.99));
          lin = p.dx < 0 ? 1 : 0;
        } else {
          col = q < 0.8 ? 1 : 0;
          lin = 2;
        }
        const sobe = cel * s * mistura(0.5, 0.3, q);
        ctx.drawImage(sheet, col * cel, lin * cel, cel, cel, (-cel * s) / 2, -sobe - (cel * s) / 2, cel * s, cel * s);
      } else {
        if (p.bal > 0.01) ctx.rotate(Math.sin(p.balFase) * p.bal * 0.2);
        ctx.drawImage(sheet, 5 * cel, 2 * cel, cel, cel, (-cel * s) / 2, -cel * s * 0.94, cel * s, cel * s);
      }
      ctx.restore();
    }

    /* Dragon 2: o pino (sprites/boliccheeee.png) tomba em 3D -- voa pista
       acima, deita em perspectiva (encurtando) e gira na diagonal */
    function desenharPinoD2(ctx, p) {
      const im = img.pino;
      if (!pronta(im)) return;
      projetar(p.x, p.z);
      const alturaTela = g.alturaPino * PW;
      eixoPino(p, alturaTela, 0);
      const iw = im.naturalWidth;
      const ih = im.naturalHeight;
      ctx.save();
      ctx.globalAlpha = p.alfa * entradaAlfa(p);
      ctx.translate(EX, EY + entradaDy(p));
      ctx.rotate(EA + (p.estado === CAINDO ? p.giro * p.queda * 0.5 : 0));
      ctx.scale(alturaTela / ih, Math.max(0.05, EL) / ih);
      ctx.drawImage(im, -iw / 2, -ih);
      ctx.restore();
    }

    /* o placar do boliche (5 rodadas, a última com 3 casas), a tentativa e
       o MAPA DOS PINOS */
    function desenharHudDragon(ctx) {
      const borda = D2 ? "rgba(47,123,255,.9)" : "rgba(38,191,255,.75)";
      const destaque = D2 ? "#ffc94a" : "rgba(255,209,36,.95)";
      const larguras = [92, 92, 92, 92, 124];
      const gap = 6;
      const y0 = 10;
      ctx.save();
      ctx.fillStyle = "rgba(3,5,11,.88)";
      caminhoArredondado(ctx, 6, y0 - 4, 528, 74, 14);
      ctx.fill();
      ctx.shadowColor = borda;
      ctx.shadowBlur = 12;
      ctx.lineWidth = 2;
      ctx.strokeStyle = borda;
      ctx.stroke();
      ctx.shadowBlur = 0;
      let x = 10;
      for (let i = 0; i < NQ; i++) {
        const q = quadros[i];
        const w = larguras[i];
        const atual = i === iQuadro && fase !== "fim";
        const ultimo = i === NQ - 1;
        ctx.fillStyle = atual ? "rgba(255,209,36,.12)" : "rgba(255,255,255,.04)";
        caminhoArredondado(ctx, x, y0, w, 66, 8);
        ctx.fill();
        ctx.lineWidth = atual ? 2.5 : 1.2;
        ctx.strokeStyle = atual ? destaque : "rgba(140,235,255,.35)";
        ctx.stroke();
        api.texto(ctx, String(i + 1), x + 12, y0 + 13, { tamanho: 12, cor: "rgba(140,235,255,.85)", peso: 800 });
        const casas = ultimo ? 3 : 2;
        const cw = 26;
        for (let c = 0; c < casas; c++) {
          const xc = x + w - (casas - c) * (cw + 3);
          ctx.strokeStyle = "rgba(140,235,255,.35)";
          ctx.lineWidth = 1;
          ctx.strokeRect(xc, y0 + 3, cw, 24);
          const m = marca(q, c, ultimo);
          if (m) {
            const cor = m === "X" ? COR_STRIKE : m === "/" ? COR_SPARE : "#eaf6ff";
            api.texto(ctx, m, xc + cw / 2, y0 + 16, { tamanho: 18, cor, peso: 800 });
          }
        }
        if (q.total != null) {
          api.texto(ctx, String(q.total), x + w / 2, y0 + 47, { tamanho: 22, cor: "#fff", peso: 800, contorno: "rgba(0,0,0,.5)" });
        }
        x += w + gap;
      }
      // a tentativa (game.gd: "TENTATIVA %d / %d")
      const q = quadros[iQuadro];
      const jogadas = q ? q.bolas.length : 0;
      const bolaN = Math.max(1, Math.min(fase === "resultado" || fase === "encerrando" ? jogadas : jogadas + 1, iQuadro === NQ - 1 ? 3 : 2));
      ctx.fillStyle = "rgba(3,5,11,.85)";
      caminhoArredondado(ctx, 10, 92, 170, 30, 15);
      ctx.fill();
      ctx.strokeStyle = destaque;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      api.texto(ctx, `ROUND ${iQuadro + 1} · BOLA ${bolaN}`, 95, 107.5, { tamanho: 14, cor: D2 ? "#ffd98a" : "rgb(255,230,51)", peso: 800 });
      ctx.restore();
      desenharMapa(ctx, W - 136, 90, 126, 112, D2 ? MAPA_D2 : MAPA_D1);
    }

    /* as casas do placar: X, /, - e números (a última rodada tem 3) */
    function marca(q, c, ultimo) {
      const b = q.bolas;
      if (!ultimo) {
        if (b[0] === 10) return c === 1 ? "X" : "";
        if (c >= b.length) return "";
        if (c === 1 && b[0] + b[1] === 10) return "/";
        return b[c] === 0 ? "-" : String(b[c]);
      }
      if (c >= b.length) return "";
      const v = b[c];
      const rackCheio = c === 0 || (c === 1 && b[0] === 10) || (c === 2 && ((b[0] === 10 && b[1] === 10) || (b[0] !== 10 && b[0] + b[1] === 10)));
      if (v === 10 && rackCheio) return "X";
      if (!rackCheio && b[c - 1] + v === 10) return "/";
      return v === 0 ? "-" : String(v);
    }

    /* ======================================================================
       ENTRADA
       ====================================================================== */
    function amostra(x, y) {
      amX[amI] = x;
      amY[amI] = y;
      amT[amI] = agora();
      amI = (amI + 1) % AMOSTRAS;
      amN = Math.min(AMOSTRAS, amN + 1);
    }

    function posicionarPeloDedo(x, y) {
      const limite = (g.bumper || 0.5) - g.raioBola;
      bola.x = lim((x - cx) / lDe(t.y0), -limite, limite);
      bola.ergue = lim((t.y0 - y) * 0.25, 0, 26);
    }

    function apertar(x, y, id) {
      if (fase !== "pronta" || arrastando) return;
      projetar(bola.x, 0);
      const r = raioBolaTela(PY);
      const perto = Math.hypot(x - PX, y - (PY - r)) < r + 90;
      // pega a bola perto dela ou em qualquer lugar da parte de baixo
      if (!perto && y < t.y0 - 220) return;
      arrastando = true;
      idArrasto = id;
      amN = 0;
      amI = 0;
      dedoY = y;
      amostra(x, y);
      posicionarPeloDedo(x, y);
      usouTeclado = false;
      api.som("clique");
    }

    function mover(x, y, id) {
      if (!arrastando || id !== idArrasto) return;
      amostra(x, y);
      dedoY = y;
      posicionarPeloDedo(x, y);
      // o dedo foi longe pista acima: a bola sai na hora
      if (y < t.y0 - 240) {
        arrastando = false;
        idArrasto = null;
        if (!lancarPeloGesto()) bola.ergue = 0;
      }
    }

    function soltar(x, y, id) {
      if (!arrastando || id !== idArrasto) return;
      amostra(x, y);
      arrastando = false;
      idArrasto = null;
      if (!lancarPeloGesto()) {
        bola.ergue = 0;
        if (dedoY < t.y0 - 60) aviso({ texto: "MAIS RÁPIDO!", cor: KIDS ? "#ffffff" : COR_ACERTO, tam: 40, dur: 0.8, y: t.y0 - 260 });
      }
    }

    function tecla(codigo, apertada) {
      if (codigo === "ArrowLeft") teclas.esq = apertada;
      else if (codigo === "ArrowRight") teclas.dir = apertada;
      else if (codigo === "KeyA" || codigo === "ArrowUp") teclas.miraEsq = apertada;
      else if (codigo === "KeyD" || codigo === "ArrowDown") teclas.miraDir = apertada;
      else if ((codigo === "Space" || codigo === "Enter") && apertada) {
        if (fase === "pronta" && !arrastando) lancar(miraTeclado, zP / mistura(V.tempos[0], V.tempos[1], 0.3), 0);
        return;
      }
      if (apertada) usouTeclado = true;
    }

    return {
      iniciar,
      atualizar,
      desenhar,
      apertar,
      mover,
      soltar,
      tecla,
      _pinos: () => pinos.filter((p) => p.estado === EM_PE).map((p) => p.n).join(",") || "-",
      destruir() {
        avisos.length = 0;
        parts.length = 0;
        fundoCache = null;
      },
    };
  },
};

const ARCO_IRIS = ["#FF4B5C", "#FF9F2E", "#FFD43B", "#8DFF6A", "#4FD8FF", "#B57BFF"];
const RASTRO_D1 = ["rgba(255,170,40,1)", 0.55];
const RASTRO_D2 = ["rgba(60,140,255,1)", 1.1, "rgba(255,210,90,1)", 0.42];
const MAPA_KIDS = {
  fundo: "rgba(11,31,69,.82)", borda: CREME, emPe: CREME, caido: "rgba(255,255,255,.14)",
  contorno: MARINHO, titulo: "PINOS", corTitulo: CREME,
};
const MAPA_D1 = {
  fundo: "rgba(1,10,3,.82)", borda: "rgba(71,255,71,.6)", emPe: "rgb(31,245,112)", caido: "rgba(26,31,41,.98)",
  contorno: "#021", titulo: "◆ MAPA DOS PINOS ◆", corTitulo: "rgb(56,255,56)", numeros: true, brilho: true,
};
const MAPA_D2 = {
  fundo: "rgba(2,8,26,.86)", borda: "rgba(80,150,255,.9)", emPe: "#4f9dff", caido: "rgba(26,30,40,.95)",
  contorno: "#021", titulo: "◆ MAPA DOS PINOS ◆", corTitulo: "#9cc8ff", numeros: true, brilho: true,
};
