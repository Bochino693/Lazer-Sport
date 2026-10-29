/* ======================================================================
   HIT MUSIC — miniatura do jogo de ritmo da mesa circular.

   A máquina de verdade (projeto Godot "hit-music-game", versão R7) tem um
   HUD retangular em cima e um campo circular grande embaixo: anel branco
   contínuo, oito marcadores de faixa fixos e notas que nascem no centro e
   correm até o anel. Esta miniatura copia esse desenho e as regras:

   - TAP: o tazo (arte real, quadro 0 amarelo, 1 vermelho, 2 ciano) corre
     do centro até o marcador. Toque a faixa quando ele encaixar no anel.
   - HOLD: uma fita fina de energia na cor do tazo; segure até ela drenar.
   - SLIDE: trilho com setas e uma estrela; encoste no começo e ARRASTE
     o dedo pelo corredor até o fim (pular direto para o fim não vale).
   - A nota pode ser tocada assim que aparece (o estouro sai onde ela
     está), mas encaixar no tempo vale mais — igual ao `_timing_quality`
     do stage.gd. Errar é silencioso no campo e ABAIXA o volume da música;
     acertar devolve o volume (a "energia da música" do original).
   - No fim: CLASSIFICADO com 70% de precisão ou mais.

   Não há música licenciada aqui: a trilha "Pulso Neon" é composta e
   tocada pelo próprio jogo (WebAudio), e a fase é gerada a partir do BPM
   dela com a mesma lógica do chart_factory_v9.gd (frases de 4 compassos,
   arquétipos, notas presas na grade da batida, gesto longo bloqueia o
   resto). Assim cada nota cai exatamente em cima da bateria.
   ====================================================================== */

const LARGURA = 540;
const ALTURA = 960;

/* ---------- a música ---------- */
const BPM = 128;
const BATIDA = 60 / BPM;
const COMPASSO = BATIDA * 4;
const PASSO = BATIDA / 4; // semicolcheia: a menor divisão do sequenciador
const COMPASSOS = 32;
const PASSOS = COMPASSOS * 16;
const DURACAO = COMPASSOS * COMPASSO; // 60 s
const NOME_MUSICA = "PULSO NEON";

/* ---------- geometria (mesmas proporções do stage.gd em 1080x1920) ---------- */
const R = 258; // raio do campo: 98,5% da metade da largura útil
const CX = LARGURA / 2;
const CY = ALTURA - 12 - R; // o círculo encosta na margem de baixo
const R_ANEL = R * 0.905; // linha branca onde os tazos encaixam
const FAIXAS = 8;
const HUD = { x: 14, y: 12, w: LARGURA - 28, h: 178 };

/* ---------- tempo de jogo (rhythm_profile.gd, fase fácil a 128 BPM) ---------- */
const APROXIMACAO = 1.4; // segundos do centro até o anel
const JANELA_PERFEITO = 0.075;
const JANELA_OTIMO = 0.15;
const JANELA_ACERTO = 0.26; // batida × 0,58, como o fácil do original
const ESCALA_JANELA_ARRASTO = 2.1; // achar o começo do arrasto leva mais tempo
const FOLGA_ARRASTO = 0.45;
const ARRASTO_COMPLETO = 0.93;
const CORREDOR = R * 0.2; // folga de um dedo inteiro em volta do trilho
const AVANCO_MAXIMO = 0.22; // o quanto uma amostra pode andar no trilho

const TAP = 0;
const HOLD = 1;
const SLIDE = 2;

/* ---------- cores: a ordem é a dos quadros da arte (tap_palette.gd) ---------- */
const COR = ["#ffb800", "#ff060e", "#00dbff"];
const COR_CLARA = ["#ffe38f", "#ff9aa0", "#a6f2ff"];
const RGB = [[255, 184, 0], [255, 6, 14], [0, 219, 255], [255, 61, 242], [255, 255, 255]];
const ROSA = 3;
const COR_TEMA = "#ff3df2";
const COR_TEMA2 = "#3ff0ff";

const JULGAMENTOS = [
  { nome: "PERFECT", pontos: 300, qualidade: 1, cor: "#fff27a" },
  { nome: "GREAT", pontos: 200, qualidade: 0.85, cor: "#3ff0ff" },
  { nome: "GOOD", pontos: 100, qualidade: 0.72, cor: "#ff8ae8" },
  { nome: "MISS", pontos: 0, qualidade: 0, cor: "#ff5468" },
];

/* Teclas: A S D F J K L Ç seguem o anel no sentido do relógio a partir
   do topo (Ç chega como "Semicolon" no teclado ABNT2). O teclado numérico
   aponta a direção da faixa; as setas dão as quatro faixas retas e, em
   dupla (cima+direita), as diagonais. */
const TECLAS = {
  KeyA: 0, KeyS: 1, KeyD: 2, KeyF: 3, KeyJ: 4, KeyK: 5, KeyL: 6, Semicolon: 7,
  Numpad8: 0, Numpad9: 1, Numpad6: 2, Numpad3: 3, Numpad2: 4, Numpad1: 5, Numpad4: 6, Numpad7: 7,
};
const SETAS = { ArrowUp: 0, ArrowRight: 2, ArrowDown: 4, ArrowLeft: 6 };
const ROTULOS = ["A", "S", "D", "F", "J", "K", "L", "Ç"];

/* Silhuetas das setas do arrasto (quatro estilos, como no renderer):
   chevron cheio, dardo, duplo e pena. Pontos em múltiplos do tamanho. */
const FORMAS_SETA = [
  [[[1.05, 0], [-0.75, 0.88], [-0.35, 0], [-0.75, -0.88]]],
  [[[1.3, 0], [-0.9, 0.55], [-0.45, 0], [-0.9, -0.55]]],
  [[[1.05, 0], [0.05, 0.75], [0.35, 0], [0.05, -0.75]], [[0.15, 0], [-0.85, 0.75], [-0.55, 0], [-0.85, -0.75]]],
  [[[1.1, 0], [-0.6, 0.9], [-0.25, 0.1], [-1.1, 0.1], [-1.1, -0.1], [-0.25, -0.1], [-0.6, -0.9]]],
];

/* ======================================================================
   A FASE — gerada uma vez, sempre igual (semente fixa)
   ====================================================================== */

/* Passos de faixa do rhythm_profile.gd: o normal é andar um botão por
   nota, com saltos curtos de vez em quando — a mão passeia pela mesa em
   vez de atravessá-la a cada nota. */
const PASSOS_FACIL = [1, 1, -1, 2, 1, -1, -1, 2, 1, 1, -2, 1, 1, -1, 2, -1];
const PASSOS_DIFICIL = [1, 1, 2, -1, 1, 1, -2, 1, 1, 3, -1, -1, 1, 2, -1, 1, 1, -2, -1, 1, 2, 1, -1, 1];

const CORRIDA = 0;
const QUEBRA = 1;
const VIRADA = 2;
const PAR = 3;
const MISTO = 4;
const RESPIRO = 5;
const FINAL = 6;

/* No original o arquétipo de cada frase é sorteado. Aqui a música é
   composta junto com a fase, então cada seção recebe o arquétipo que
   combina com ela: o break (sem bumbo) ganha os gestos longos, o drop
   ganha contratempo e par de mãos. As notas dentro da frase continuam
   sorteadas com semente fixa, como lá. Especiais: [tipo, batida da frase]. */
const FRASES = [
  { compasso: 2, compassos: 4, tipo: CORRIDA, dificil: false, especiais: [] },
  { compasso: 6, compassos: 4, tipo: QUEBRA, dificil: false, especiais: [[HOLD, 12]] },
  { compasso: 10, compassos: 4, tipo: VIRADA, dificil: false, especiais: [[SLIDE, 12]] },
  { compasso: 14, compassos: 4, tipo: MISTO, dificil: true, especiais: [[HOLD, 14]] },
  { compasso: 18, compassos: 4, tipo: RESPIRO, dificil: false, especiais: [[SLIDE, 4], [HOLD, 12]] },
  { compasso: 22, compassos: 4, tipo: CORRIDA, dificil: true, especiais: [] },
  { compasso: 26, compassos: 4, tipo: PAR, dificil: true, especiais: [[SLIDE, 12]] },
  { compasso: 30, compassos: 1.25, tipo: FINAL, dificil: false, especiais: [] },
];

function semente(a) {
  // mulberry32: pequeno, rápido e igual em todo navegador
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function naSubdivisao(batida, passo) {
  const resto = ((batida % passo) + passo) % passo;
  return resto < 0.0005 || resto > passo - 0.0005;
}

/* _slot_is_active do chart_factory_v9.gd. O fácil só pisa nas batidas
   (1 e 3 sempre); o "difícil" daqui anda em colcheias, mas com o
   contratempo um pouco mais raro, porque a mesa virou tela de celular. */
function slotAtivo(aleatorio, frase, batidaNoCompasso) {
  const naBatida = naSubdivisao(batidaNoCompasso, 1);
  const forte = naSubdivisao(batidaNoCompasso, 2);
  if (frase.tipo === RESPIRO) return forte;
  if (frase.tipo === FINAL) return naBatida;
  if (!frase.dificil) {
    if (!naBatida) return false;
    if (forte || frase.tipo === CORRIDA) return true;
    return aleatorio() < 0.45;
  }
  if (naBatida) return true;
  if (frase.tipo === CORRIDA) return aleatorio() < 0.62 * 0.7;
  if (frase.tipo === PAR) return aleatorio() < 0.3 * 0.7;
  return aleatorio() < 0.42 * 0.7;
}

function posicaoFaixa(faixa) {
  const a = -Math.PI / 2 + (Math.PI * 2 * faixa) / FAIXAS;
  return [CX + Math.cos(a) * R_ANEL, CY + Math.sin(a) * R_ANEL];
}

/* Trilho do arrasto amostrado em pontos (path_builder.gd). */
function montarCaminho(nota) {
  const ancoras = nota.caminho.map(posicaoFaixa);
  const pts = [];
  if (nota.forma === "arco") {
    // curva quadrática que estufa para fora, no mesmo sentido da mesa
    const a = ancoras[0];
    const b = ancoras[ancoras.length - 1];
    const mx = (a[0] + b[0]) / 2;
    const my = (a[1] + b[1]) / 2;
    let nx = -(b[1] - a[1]);
    let ny = b[0] - a[0];
    const l = Math.hypot(nx, ny) || 1;
    nx /= l; ny /= l;
    if (nx * (mx - CX) + ny * (my - CY) < 0) { nx = -nx; ny = -ny; }
    const cx = mx + nx * R * nota.curva * 0.6;
    const cy = my + ny * R * nota.curva * 0.6;
    for (let i = 0; i <= 42; i++) {
      const t = i / 42;
      const u = 1 - t;
      pts.push([u * u * a[0] + 2 * u * t * cx + t * t * b[0], u * u * a[1] + 2 * u * t * cy + t * t * b[1]]);
    }
  } else {
    const n = ancoras.length > 2 ? 14 : 42;
    for (let k = 0; k < ancoras.length - 1; k++) {
      const a = ancoras[k];
      const b = ancoras[k + 1];
      for (let i = k === 0 ? 0 : 1; i <= n; i++) pts.push([a[0] + (b[0] - a[0]) * (i / n), a[1] + (b[1] - a[1]) * (i / n)]);
    }
  }
  const n = pts.length;
  nota.px = new Float32Array(n);
  nota.py = new Float32Array(n);
  nota.acum = new Float32Array(n);
  let total = 0;
  for (let i = 0; i < n; i++) {
    nota.px[i] = pts[i][0];
    nota.py[i] = pts[i][1];
    if (i > 0) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    nota.acum[i] = total;
  }
  nota.total = total;
  // fração do trilho em que cada âncora (faixa) fica: o teclado anda por elas
  nota.ancoras = ancoras.map((p) => {
    let melhor = 0;
    let menor = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.hypot(nota.px[i] - p[0], nota.py[i] - p[1]);
      if (d < menor) { menor = d; melhor = i; }
    }
    return nota.acum[melhor] / total;
  });
}

function montarFase() {
  const aleatorio = semente(1001 * 7919 + 15485863);
  const notas = [];
  const base = 1001 % FAIXAS;
  // Desenhos de arrasto do rhythm_profile.gd (fácil, fácil, difícil):
  // todos avançam no mesmo sentido de rotação, nenhum na contramão.
  const arrastos = [
    { caminho: [base, (base + 4) % 8], forma: "reta", curva: 0 },
    { caminho: [(base + 2) % 8, (base + 5) % 8], forma: "arco", curva: 0.38 },
    { caminho: [base, (base + 2) % 8, (base + 4) % 8], forma: "zigue", curva: 0 },
  ];
  let faixa = base;
  const direcao = 1001 % 2 === 0 ? 1 : -1;
  let passoFacil = 0;
  let passoDificil = 0;
  let indiceNota = 0;
  let indiceArrasto = 0;
  let ocupadoAte = -1; // gesto longo em andamento: nada mais é cobrado

  for (const frase of FRASES) {
    const inicio = frase.compasso * COMPASSO;
    const grade = frase.dificil ? 0.5 : 1;
    const slots = Math.round((frase.compassos * 4) / grade);
    const feitos = frase.especiais.map(() => false);
    const recuperacao = frase.dificil ? 0.5 : 1;

    for (let slot = 0; slot < slots; slot++) {
      const batidas = slot * grade;
      const t = inicio + batidas * BATIDA;
      if (t >= DURACAO - 1) break;
      if (t < ocupadoAte - 1e-6) continue;

      // a jogada especial entra na primeira posição livre depois da reservada
      const k = frase.especiais.findIndex((e, i) => !feitos[i] && batidas >= e[1]);
      if (k >= 0) {
        feitos[k] = true;
        if (frase.especiais[k][0] === HOLD) {
          const dur = (frase.dificil ? 3.5 : 4.5) * BATIDA;
          notas.push({ tipo: HOLD, t, fim: t + dur, faixa, cor: indiceNota % 3 });
          ocupadoAte = t + dur + recuperacao * BATIDA;
        } else {
          const molde = arrastos[indiceArrasto % arrastos.length];
          const dur = (indiceArrasto >= 2 ? 4 : 5) * BATIDA;
          const nota = {
            tipo: SLIDE, t, fim: t + dur, faixa: molde.caminho[0], cor: indiceNota % 3,
            caminho: molde.caminho, forma: molde.forma, curva: molde.curva,
            estiloSeta: indiceArrasto % 4, estiloEstrela: (indiceArrasto * 3 + 1) % 4,
          };
          montarCaminho(nota);
          notas.push(nota);
          indiceArrasto++;
          ocupadoAte = t + dur + recuperacao * BATIDA;
        }
        indiceNota++;
        continue;
      }

      if (!slotAtivo(aleatorio, frase, batidas % 4)) continue;

      notas.push({ tipo: TAP, t, fim: t, faixa, cor: indiceNota % 3 });
      // Par de mãos: faixas opostas (distância 4), só na batida forte;
      // a última nota da música também vem em par, em cima do prato.
      const ultimo = frase.tipo === FINAL && slot === slots - 1;
      if ((frase.tipo === PAR && naSubdivisao(batidas % 4, 2) && aleatorio() < 0.72) || ultimo) {
        notas.push({ tipo: TAP, t, fim: t, faixa: (faixa + 4) % 8, cor: (indiceNota + 1) % 3 });
      }
      indiceNota++;
      const passo = frase.dificil
        ? PASSOS_DIFICIL[passoDificil++ % PASSOS_DIFICIL.length]
        : PASSOS_FACIL[passoFacil++ % PASSOS_FACIL.length];
      faixa = (faixa + passo * direcao + 16) % 8;
    }
  }
  notas.sort((a, b) => a.t - b.t || a.faixa - b.faixa);
  return notas;
}

/* ======================================================================
   A TRILHA — sequenciador de 16 passos por compasso
   ====================================================================== */
const INTRO = 0;
const VERSO = 1;
const REFRAO = 2;
const PAUSA = 3;
const QUEDA = 4;

function secao(c) {
  if (c < 2) return INTRO;
  if (c < 10) return VERSO;
  if (c < 18) return REFRAO;
  if (c < 22) return PAUSA;
  if (c < 30) return QUEDA;
  return 5; // saída
}

// vi–IV–I–V em lá menor: Am, F, C, G. Cada seção começa no Am.
const ACORDES = [
  { baixo: 45, notas: [57, 60, 64] },
  { baixo: 41, notas: [53, 57, 60] },
  { baixo: 48, notas: [60, 64, 67] },
  { baixo: 43, notas: [55, 59, 62] },
];
const acordeDo = (c) => ACORDES[(c + 2) & 3];

// Melodia de 4 compassos: [passo, nota MIDI, duração em passos].
const MELODIA = new Int8Array(64);
const DURACAO_MELODIA = new Int8Array(64);
[
  [0, 69, 3], [3, 72, 3], [6, 76, 2], [8, 74, 2], [10, 72, 2], [12, 69, 4],
  [16, 69, 2], [18, 72, 2], [20, 72, 2], [22, 74, 2], [24, 72, 3], [27, 69, 3], [30, 67, 2],
  [32, 76, 3], [35, 79, 3], [38, 76, 2], [40, 74, 2], [42, 72, 2], [44, 76, 4],
  [48, 74, 2], [50, 71, 2], [52, 67, 4], [56, 74, 2], [58, 76, 2], [60, 74, 4],
].forEach(([p, n, d]) => { MELODIA[p] = n; DURACAO_MELODIA[p] = d; });
const ARPEJO = [0, 1, 2, 1];

const hz = (midi) => 440 * Math.pow(2, (midi - 69) / 12);

/* ======================================================================
   O JOGO
   ====================================================================== */
export default {
  largura: LARGURA,
  altura: ALTURA,
  artes: {
    abertura: "hit-music/abertura.webp",
    roda: "hit-music/roda.webp",
    tazos: "hit-music/tazos.webp",
    selo: "hit-music/selo.webp",
    logo: "hit-music/logo.webp",
  },

  criar(api) {
    const img = api.img;
    const NOTAS = montarFase();
    const TOTAL_NOTAS = NOTAS.length;
    const PRIMEIRA_NOTA = NOTAS[0].t;
    const MARCAS = Array.from({ length: FAIXAS }, (_, i) => posicaoFaixa(i));
    const temMouse = !!(window.matchMedia && window.matchMedia("(hover: hover)").matches);

    /* ---------- brilhos pré-desenhados (um por cor) ----------
       Gradiente radial custa caro se for criado a cada quadro; um
       canvas pequeno pintado uma vez e esticado com drawImage sai de
       graça e dá o mesmo "neon". */
    const BRILHOS = RGB.map(([r, g, b]) => {
      const c = document.createElement("canvas");
      c.width = c.height = 64;
      const x = c.getContext("2d");
      const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
      gr.addColorStop(0, `rgba(${r},${g},${b},1)`);
      gr.addColorStop(0.35, `rgba(${r},${g},${b},0.42)`);
      gr.addColorStop(1, `rgba(${r},${g},${b},0)`);
      x.fillStyle = gr;
      x.fillRect(0, 0, 64, 64);
      return c;
    });
    // camadas do estouro: a cor do tazo clareando aos poucos para o branco
    const MISTURA = RGB.map(([r, g, b]) => [0, 1, 2, 3, 4].map((camada) => {
      const k = 0.28 - camada * 0.045;
      return `rgb(${Math.round(r + (255 - r) * k)},${Math.round(g + (255 - g) * k)},${Math.round(b + (255 - b) * k)})`;
    }));

    let gradientes = null;
    function prepararGradientes(ctx) {
      if (gradientes) return;
      const fundo = ctx.createLinearGradient(0, 0, 0, ALTURA);
      fundo.addColorStop(0, "#0d0326");
      fundo.addColorStop(0.45, "#070118");
      fundo.addColorStop(1, "#020007");
      const disco = ctx.createRadialGradient(CX, CY, R * 0.1, CX, CY, R);
      disco.addColorStop(0, "#1c0a3d");
      disco.addColorStop(0.7, "#0c0424");
      disco.addColorStop(1, "#05010f");
      const borda = ctx.createLinearGradient(HUD.x, 0, HUD.x + HUD.w, 0);
      borda.addColorStop(0, COR_TEMA);
      borda.addColorStop(0.5, "#8a5cff");
      borda.addColorStop(1, COR_TEMA2);
      const barras = ctx.createLinearGradient(HUD.x, 0, HUD.x + HUD.w, 0);
      barras.addColorStop(0, "#ff3df2");
      barras.addColorStop(0.5, "#9a6bff");
      barras.addColorStop(1, "#3ff0ff");
      gradientes = { fundo, disco, borda, barras };
    }

    /* ======================================================================
       SOM — trilha própria, num AudioContext só do jogo
       ====================================================================== */
    const Contexto = window.AudioContext || window.webkitAudioContext;
    const botaoSom = document.querySelector("[data-console-som]");
    const audio = { ctx: null, mestre: null, bus: null, ruido: null, cursor: 0, ligado: true, checar: 0, deslocamento: null };

    /* O console não expõe o mudo para o jogo. O botão dele, porém, diz o
       estado em aria-pressed (e o mesmo valor fica no localStorage); é o
       que a pessoa vê, então é a fonte certa para a trilha obedecer. */
    function somLigado() {
      if (botaoSom) return botaoSom.getAttribute("aria-pressed") !== "false";
      try { return window.localStorage.getItem("ls-jogos-som") !== "0"; } catch (erro) { return true; }
    }

    // Só chamar a partir de um gesto (ou depois que a página já teve um):
    // é a regra dos navegadores para tocar som.
    function acordarAudio() {
      if (!Contexto || !somLigado()) return;
      if (!audio.ctx) {
        try { audio.ctx = new Contexto(); } catch (erro) { return; }
        const c = audio.ctx;
        const compressor = c.createDynamicsCompressor();
        compressor.threshold.value = -14;
        compressor.ratio.value = 4;
        audio.mestre = c.createGain();
        audio.mestre.gain.value = 0.3; // trilha baixa: os sons do console vêm por cima
        audio.mestre.connect(compressor).connect(c.destination);
        const quadros = Math.floor(c.sampleRate);
        audio.ruido = c.createBuffer(1, quadros, c.sampleRate);
        const dados = audio.ruido.getChannelData(0);
        for (let i = 0; i < quadros; i++) dados[i] = Math.random() * 2 - 1;
        novoBus();
      }
      if (audio.ctx.state === "suspended") audio.ctx.resume().catch(() => {});
    }

    // Cada partida toca num "bus" novo: desligar o antigo cala na hora as
    // notas que já estavam agendadas (o sequenciador agenda um pouco à frente).
    function novoBus() {
      if (!audio.ctx) return;
      if (audio.bus) { try { audio.bus.disconnect(); } catch (erro) { /* já solto */ } }
      audio.bus = audio.ctx.createGain();
      audio.bus.gain.value = 1;
      audio.bus.connect(audio.mestre);
    }

    function silenciar(segundos) {
      if (!audio.ctx || !audio.bus) return;
      const g = audio.bus.gain;
      const agora = audio.ctx.currentTime;
      g.cancelScheduledValues(agora);
      g.setValueAtTime(g.value, agora);
      g.linearRampToValueAtTime(0, agora + segundos);
    }

    let soVisual = false; // o mesmo roteiro alimenta o som e as barras do HUD
    const espectro = new Float32Array(32);
    function marcar(centro, largura, forca) {
      const a = Math.max(0, Math.floor(centro - largura));
      const b = Math.min(31, Math.ceil(centro + largura));
      for (let i = a; i <= b; i++) {
        const v = forca * (1 - Math.abs(i - centro) / (largura + 1));
        if (v > espectro[i]) espectro[i] = v;
      }
    }

    function ruido(quando, dur, volume, tipo, freq, q) {
      const c = audio.ctx;
      const fonte = c.createBufferSource();
      fonte.buffer = audio.ruido;
      const f = c.createBiquadFilter();
      f.type = tipo;
      f.frequency.value = freq;
      f.Q.value = q;
      const g = c.createGain();
      g.gain.setValueAtTime(volume, quando);
      g.gain.exponentialRampToValueAtTime(0.0001, quando + dur);
      fonte.connect(f).connect(g).connect(audio.bus);
      fonte.start(quando, Math.random() * 0.5);
      fonte.stop(quando + dur + 0.02);
      return f;
    }

    function bumbo(q) {
      if (soVisual) { marcar(2, 3, 1); return; }
      const c = audio.ctx;
      const o = c.createOscillator();
      const g = c.createGain();
      o.frequency.setValueAtTime(155, q);
      o.frequency.exponentialRampToValueAtTime(46, q + 0.13);
      g.gain.setValueAtTime(0.95, q);
      g.gain.exponentialRampToValueAtTime(0.0001, q + 0.34);
      o.connect(g).connect(audio.bus);
      o.start(q);
      o.stop(q + 0.36);
    }

    function palma(q, vol = 0.32) {
      if (soVisual) { marcar(13, 4, 0.75); return; }
      ruido(q, 0.03, vol, "bandpass", 1400, 0.9);
      ruido(q + 0.011, 0.03, vol, "bandpass", 1400, 0.9);
      ruido(q + 0.022, 0.18, vol, "bandpass", 1300, 0.8);
    }

    function chimbal(q, aberto, vol) {
      if (soVisual) { marcar(28, 3, aberto ? 0.7 : 0.45 + vol); return; }
      ruido(q, aberto ? 0.24 : 0.045, vol, "highpass", 7600, 0.7);
    }

    function baixo(q, midi, dur, vol = 0.3) {
      if (soVisual) { marcar(5, 3, 0.85); return; }
      const c = audio.ctx;
      const f = c.createBiquadFilter();
      f.type = "lowpass";
      f.Q.value = 5;
      f.frequency.setValueAtTime(1500, q);
      f.frequency.exponentialRampToValueAtTime(260, q + dur);
      const g = c.createGain();
      g.gain.setValueAtTime(vol, q);
      g.gain.exponentialRampToValueAtTime(0.0001, q + dur);
      f.connect(g).connect(audio.bus);
      const a = c.createOscillator();
      a.type = "sawtooth";
      a.frequency.value = hz(midi);
      const b = c.createOscillator();
      b.type = "sine";
      b.frequency.value = hz(midi - 12);
      a.connect(f);
      b.connect(f);
      a.start(q); b.start(q);
      a.stop(q + dur + 0.02); b.stop(q + dur + 0.02);
    }

    function acorde(q, notas, dur, vol, ataque = 0.006, corte = 1900) {
      if (soVisual) { marcar(12, 6, 0.55 + vol); return; }
      const c = audio.ctx;
      const f = c.createBiquadFilter();
      f.type = "lowpass";
      f.frequency.value = corte;
      const g = c.createGain();
      g.gain.setValueAtTime(0.0001, q);
      g.gain.exponentialRampToValueAtTime(vol, q + ataque);
      g.gain.setValueAtTime(vol, q + Math.max(ataque, dur * 0.6));
      g.gain.exponentialRampToValueAtTime(0.0001, q + dur);
      f.connect(g).connect(audio.bus);
      for (let i = 0; i < notas.length; i++) {
        for (let d = -6; d <= 6; d += 12) {
          const o = c.createOscillator();
          o.type = "sawtooth";
          o.frequency.value = hz(notas[i]);
          o.detune.value = d;
          o.connect(f);
          o.start(q);
          o.stop(q + dur + 0.03);
        }
      }
    }

    function melodia(q, midi, dur) {
      if (soVisual) { marcar(12 + (midi - 64) * 0.9, 2, 0.9); return; }
      const c = audio.ctx;
      const f = c.createBiquadFilter();
      f.type = "lowpass";
      f.frequency.value = 3400;
      const g = c.createGain();
      g.gain.setValueAtTime(0.0001, q);
      g.gain.exponentialRampToValueAtTime(0.13, q + 0.008);
      g.gain.exponentialRampToValueAtTime(0.07, q + dur * 0.5);
      g.gain.exponentialRampToValueAtTime(0.0001, q + dur);
      f.connect(g).connect(audio.bus);
      const a = c.createOscillator();
      a.type = "square";
      a.frequency.value = hz(midi);
      const b = c.createOscillator();
      b.type = "triangle";
      b.frequency.value = hz(midi + 12);
      a.connect(f); b.connect(f);
      a.start(q); b.start(q);
      a.stop(q + dur + 0.03); b.stop(q + dur + 0.03);
    }

    function arpejo(q, midi, vol) {
      if (soVisual) { marcar(20 + (midi % 12) * 0.5, 2, 0.5); return; }
      const c = audio.ctx;
      const o = c.createOscillator();
      const g = c.createGain();
      o.type = "triangle";
      o.frequency.value = hz(midi);
      g.gain.setValueAtTime(0.0001, q);
      g.gain.exponentialRampToValueAtTime(vol, q + 0.005);
      g.gain.exponentialRampToValueAtTime(0.0001, q + 0.11);
      o.connect(g).connect(audio.bus);
      o.start(q);
      o.stop(q + 0.14);
    }

    function subida(q, dur) {
      if (soVisual) return;
      const f = ruido(q, dur, 0.16, "bandpass", 400, 2);
      f.frequency.setValueAtTime(400, q);
      f.frequency.exponentialRampToValueAtTime(7000, q + dur);
    }

    function prato(q) {
      if (soVisual) { marcar(26, 6, 1); return; }
      ruido(q, 1.5, 0.2, "highpass", 5200, 0.6);
    }

    /* Um passo da música. É chamado duas vezes por passo: uma adiantada
       para agendar o som (soVisual = false) e outra no instante exato
       para mexer nas barras do HUD — que assim dançam até no mudo. */
    function passoMusica(i, q) {
      const c = i >> 4;
      const s = i & 15;
      const sec = secao(c);
      const ac = acordeDo(c);
      if (c >= 31) {
        if (c === 31 && s === 0) {
          bumbo(q);
          prato(q);
          acorde(q, ACORDES[0].notas, 2.6, 0.06, 0.01, 2400);
          baixo(q, ACORDES[0].baixo, 1.6, 0.34);
        }
        return;
      }
      const virada = c === 21 && s >= 8;
      if ((sec !== PAUSA || virada) && (s & 3) === 0) bumbo(q);
      if (sec !== INTRO && sec !== PAUSA && (s === 4 || s === 12)) palma(q);
      if (virada) palma(q, 0.1 + (s - 8) * 0.035);
      if (sec !== PAUSA) {
        if ((s & 3) === 2) chimbal(q, false, 0.15);
        else if ((sec === REFRAO || sec === QUEDA) && (s & 1) === 1) chimbal(q, false, 0.05);
        if ((sec === REFRAO || sec === QUEDA) && s === 14) chimbal(q, true, 0.09);
      }
      if (c >= 1 && sec !== PAUSA && (s & 3) === 2) baixo(q, ac.baixo, PASSO * 1.7);
      if (sec === QUEDA && (s & 3) === 3) baixo(q, ac.baixo + 12, PASSO * 0.8, 0.16);
      if (sec === VERSO && (s === 2 || s === 10)) acorde(q, ac.notas, 0.2, 0.05);
      if (sec === PAUSA && s === 0) acorde(q, ac.notas, COMPASSO, 0.045, 0.3, 900);
      if (sec === PAUSA || sec === QUEDA) arpejo(q, ac.notas[ARPEJO[s & 3]] + 12 + (s >= 8 ? 12 : 0), sec === PAUSA ? 0.07 : 0.035);
      if (sec === REFRAO || sec === QUEDA || c === 30) {
        const k = ((c + 2) & 3) * 16 + s;
        if (MELODIA[k]) melodia(q, MELODIA[k], DURACAO_MELODIA[k] * PASSO * 0.95);
      }
      if (c === 21 && s === 0) subida(q, COMPASSO);
      if ((c === 10 || c === 22) && s === 0) prato(q);
    }

    // Agenda o que cai entre agora e um pouco adiante. O relógio-mestre é
    // o do jogo (t): a música segue a fase, e não o contrário — assim a
    // pausa do console (aba escondida) não descasa nota e batida.
    function agendarMusica() {
      const c = audio.ctx;
      if (!c || !audio.bus || c.state !== "running" || !audio.ligado) {
        // sem som: só acompanha o relógio, para retomar no lugar certo
        while (audio.cursor < PASSOS && audio.cursor * PASSO < t + 0.02) audio.cursor++;
        audio.deslocamento = null;
        return;
      }
      // Diferença entre o relógio do áudio e o do jogo, suavizada: o quadro
      // da tela oscila alguns milissegundos e a batida não pode oscilar junto.
      const alvo = c.currentTime - t;
      if (audio.deslocamento === null || Math.abs(alvo - audio.deslocamento) > 0.05) audio.deslocamento = alvo;
      else audio.deslocamento += (alvo - audio.deslocamento) * 0.05;
      // e o atraso da saída de som entra adiantando o agendamento
      const atraso = Math.min(0.08, (c.baseLatency || 0) + (c.outputLatency || 0));
      soVisual = false;
      while (audio.cursor < PASSOS && audio.cursor * PASSO < t + 0.12 + atraso) {
        const quando = audio.cursor * PASSO + audio.deslocamento - atraso;
        if (quando >= c.currentTime - 0.03) passoMusica(audio.cursor, Math.max(c.currentTime, quando));
        audio.cursor++;
      }
    }

    function atualizarVolume() {
      if (!audio.ctx || !audio.bus || fase !== "tocando") return;
      // energia cheia ≈ -1 dB, vazia ≈ -14 dB (MUSIC_VOLUME_MIN/MAX_DB)
      const db = -14 + 13 * energiaMusica;
      audio.bus.gain.setTargetAtTime(Math.pow(10, db / 20), audio.ctx.currentTime, 0.12);
    }

    /* ======================================================================
       ESTADO DA PARTIDA
       ====================================================================== */
    let chamadasIniciar = 0;
    let fase = "capa"; // capa → pronto (contagem) → tocando → fim
    let t = 0;
    let relogio = 0; // relógio visual (anda até atrás da capa)
    let quadroPerf = 0;
    let pontos = 0;
    let combo = 0;
    let comboMax = 0;
    let multiplicador = 1;
    let somaQualidade = 0;
    let julgados = 0;
    let erros = 0;
    const contagem = [0, 0, 0, 0];
    let vida = 100;
    let energiaMusica = 1;
    let energiaAcerto = 0;
    let proxNascer = 0;
    let primeiraViva = 0;
    let passoVisual = 0;
    let ultimoJulgamento = -1;
    let tempoJulgamento = -9;
    let comboPulo = 0;
    let tempoMostrado = -1;
    let infoMostrada = null;
    let classificado = false;
    const flash = new Float32Array(FAIXAS);
    const corFlash = new Uint8Array(FAIXAS);
    const toque = new Float32Array(FAIXAS);
    const ponteiros = new Map();
    const teclasPresas = new Set();
    const setaFaixa = {};
    let setaPendente = null;

    // Pools fixos: nada de criar objeto novo a cada estouro.
    const efeitos = Array.from({ length: 24 }, () => ({ vivo: false, tipo: 0, x: 0, y: 0, cor: 0, ini: 0, dur: 0.5, rot: 0, estilo: 0 }));
    const pulsosAnel = Array.from({ length: 10 }, () => ({ vivo: false, ang: 0, cor: 0, ini: 0, dur: 0.85 }));

    function novoEfeito(tipo, x, y, cor, dur, estilo = 0) {
      let e = efeitos[0];
      for (const f of efeitos) { if (!f.vivo) { e = f; break; } if (f.ini < e.ini) e = f; }
      e.vivo = true; e.tipo = tipo; e.x = x; e.y = y; e.cor = cor; e.ini = t; e.dur = dur;
      e.rot = Math.random() * Math.PI; e.estilo = estilo;
    }

    function pulsarAnel(faixa, cor, intensidade) {
      flash[faixa] = Math.min(1.6, flash[faixa] + intensidade);
      corFlash[faixa] = cor;
      let p = pulsosAnel[0];
      for (const f of pulsosAnel) { if (!f.vivo) { p = f; break; } if (f.ini < p.ini) p = f; }
      p.vivo = true; p.ang = -Math.PI / 2 + (Math.PI * 2 * faixa) / FAIXAS; p.cor = cor; p.ini = t;
      p.dur = 0.85 * (0.55 + Math.min(intensidade, 1.4) * 0.5);
    }

    function precisao() {
      return julgados ? (100 * somaQualidade) / julgados : 100;
    }

    function formatarPct(v) {
      return v.toFixed(2).replace(".", ",") + "%";
    }

    function atualizarPlacar() {
      api.placar({ pontos });
      // a caixa do console é estreita no celular: só o multiplicador cabe
      // inteiro (o combo e a precisão já estão no HUD do próprio jogo)
      const info = multiplicador > 1 ? `x${multiplicador}` : "";
      if (info !== infoMostrada) { infoMostrada = info; api.placar({ info }); }
    }

    /* ---------- posição das coisas no tempo (sem alocar: px/py/pang) ---------- */
    let px = 0;
    let py = 0;
    let pang = 0;

    function chegada(nota, tempo) {
      return Math.min(1, Math.max(0, (tempo - (nota.t - APROXIMACAO)) / APROXIMACAO));
    }
    // Sai rápido do centro e desacelera perto do anel (no original a curva
    // é mais fechada; aqui um pouco mais aberta para ler no celular).
    const suavizar = (p) => 1 - (1 - p) * (1 - p);

    function posicaoTap(nota, tempo) {
      const m = MARCAS[nota.faixa];
      const p = (tempo - (nota.t - APROXIMACAO)) / APROXIMACAO;
      // atrasado: o tazo passa do anel e some — é o MISS chegando
      const k = p <= 1 ? suavizar(Math.max(0, p)) : 1 + (p - 1) * 0.55;
      px = CX + (m[0] - CX) * k;
      py = CY + (m[1] - CY) * k;
    }

    function pontoDoCaminho(nota, prog) {
      const alvo = Math.max(0, Math.min(1, prog)) * nota.total;
      const a = nota.acum;
      let i = 1;
      while (i < a.length - 1 && a[i] < alvo) i++;
      const seg = Math.max(0.001, a[i] - a[i - 1]);
      const k = Math.max(0, Math.min(1, (alvo - a[i - 1]) / seg));
      px = nota.px[i - 1] + (nota.px[i] - nota.px[i - 1]) * k;
      py = nota.py[i - 1] + (nota.py[i] - nota.py[i - 1]) * k;
      pang = Math.atan2(nota.py[i] - nota.py[i - 1], nota.px[i] - nota.px[i - 1]);
    }

    /* ======================================================================
       JULGAMENTO
       ====================================================================== */
    function julgar(dif) {
      const a = Math.abs(dif);
      if (a <= JANELA_PERFEITO) return 0;
      if (a <= JANELA_OTIMO) return 1;
      return 2;
    }
    // Antecipar muito ainda vale (a nota pode ser tocada assim que aparece),
    // mas paga menos: de 0,72 caindo até 0,50, como no stage.gd.
    function qualidade(dif, j) {
      const a = Math.abs(dif);
      if (a <= JANELA_ACERTO) return JULGAMENTOS[j].qualidade;
      return 0.72 - 0.22 * Math.min(1, (a - JANELA_ACERTO) / APROXIMACAO);
    }

    function acertar(nota, j, q, x, y, bonus) {
      nota.resolvida = true;
      nota.segurando = false;
      nota.ativa = false;
      combo++;
      comboMax = Math.max(comboMax, combo);
      const multAntes = multiplicador;
      multiplicador = Math.min(4, 1 + Math.floor(combo / 10));
      pontos += (JULGAMENTOS[j].pontos + bonus) * multiplicador;
      somaQualidade += q;
      julgados++;
      contagem[j]++;
      vida = Math.min(100, vida + (q >= 0.99 ? 1.15 : 0.55));
      energiaMusica = Math.min(1, energiaMusica + 0.1);
      energiaAcerto = Math.min(1, energiaAcerto + 0.3 + q * 0.3);
      ultimoJulgamento = j;
      tempoJulgamento = t;
      comboPulo = 1;

      // Uma cor só governa o feedback inteiro: estouro, anel e faíscas.
      const faixaFinal = nota.tipo === SLIDE ? nota.caminho[nota.caminho.length - 1] : nota.faixa;
      if (nota.tipo !== SLIDE) novoEfeito(nota.tipo, x, y, nota.cor, nota.tipo === HOLD ? 0.62 : 0.5);
      pulsarAnel(faixaFinal, nota.cor, 0.95 + q * 0.35);
      api.efeitos.explosao(x, y, {
        cor: [COR[nota.cor], COR_CLARA[nota.cor], "#ffffff"],
        n: nota.tipo === TAP ? 8 : 16, velocidade: nota.tipo === TAP ? 200 : 300,
        tamanho: 3, gravidade: 0, vida: 0.45,
      });
      if (nota.tipo !== TAP) { api.tremer(4); api.vibrar(18); }

      if (combo % 25 === 0) {
        api.efeitos.texto(`COMBO ${combo}!`, CX, 392, { cor: COR_TEMA2, tamanho: 34, vida: 1 });
        api.som("combo");
        api.tremer(5);
      } else if (multiplicador > multAntes) {
        api.efeitos.texto(`x${multiplicador}`, CX + 120, 336, { cor: "#fff27a", tamanho: 40, vida: 0.9 });
        api.som("ponto");
      }
      atualizarVolume();
      atualizarPlacar();
    }

    // Erro silencioso no campo (sem X sobre a próxima nota), como no R7:
    // quem avisa é o rótulo MISS e a música, que perde volume.
    function errar(nota) {
      nota.resolvida = true;
      nota.segurando = false;
      nota.ativa = false;
      combo = 0;
      multiplicador = 1;
      julgados++;
      erros++;
      contagem[3]++;
      vida = Math.max(0, vida - 6);
      energiaMusica = Math.max(0, energiaMusica - 0.16);
      ultimoJulgamento = 3;
      tempoJulgamento = t;
      atualizarVolume();
      atualizarPlacar();
    }

    function concluirArrasto(nota) {
      pontoDoCaminho(nota, nota.desenho);
      acertar(nota, 0, 1, px, py, 200);
      nota.finalizando = true;
    }

    /* ---------- entrada ---------- */
    function tempoAgora() {
      // o toque cai entre dois quadros: soma o pedaço que já passou
      return t + Math.min(0.05, Math.max(0, (performance.now() - quadroPerf) / 1000));
    }

    function faixaDoPonto(x, y) {
      const dx = x - CX;
      const dy = y - CY;
      const d = Math.hypot(dx, dy);
      if (d < R * 0.16 || d > R * 1.4) return -1; // miolo ambíguo / longe demais
      const a = Math.atan2(dy, dx) + Math.PI / 2;
      return ((Math.round(a / (Math.PI / 4)) % 8) + 8) % 8;
    }

    function pressionarFaixa(faixa, fonte, tp, x, y, temPonteiro) {
      toque[faixa] = 1;
      // Arrasto pelo teclado: não há dedo, então a estrela anda de faixa em
      // faixa, na ordem do trilho. (Na mesa isso foi proibido de propósito
      // — lá o arrasto é gesto. Aqui é a única forma de jogar um SLIDE sem
      // tela de toque, e a estrela ainda percorre o caminho inteiro.)
      if (!temPonteiro) {
        for (let i = primeiraViva; i < proxNascer; i++) {
          const n = NOTAS[i];
          if (n.tipo !== SLIDE || n.resolvida || !n.iniciada || n.fonte !== "t") continue;
          if (n.caminho[n.proximaAncora] === faixa) {
            n.progresso = n.ancoras[n.proximaAncora];
            n.proximaAncora++;
            if (n.progresso >= ARRASTO_COMPLETO) n.aguardandoEstrela = true;
            return;
          }
        }
      }

      // Vence a nota mais perto do próprio tempo, seja qual for o tipo.
      let melhor = null;
      let menor = Infinity;
      for (let i = primeiraViva; i < proxNascer; i++) {
        const n = NOTAS[i];
        if (n.resolvida) continue;
        if (n.tipo === SLIDE) {
          if (n.iniciada || n.caminho[0] !== faixa) continue;
          if (tp > n.t + JANELA_ACERTO * ESCALA_JANELA_ARRASTO) continue;
        } else {
          if (n.faixa !== faixa || n.segurando) continue;
          if (tp > n.t + JANELA_ACERTO) continue;
        }
        const d = Math.abs(tp - n.t);
        if (d < menor) { menor = d; melhor = n; }
      }
      if (!melhor) return;

      const dif = tp - melhor.t;
      const j = julgar(dif);
      if (melhor.tipo === TAP) {
        posicaoTap(melhor, tp);
        acertar(melhor, j, qualidade(dif, j), px, py, Math.abs(dif) > JANELA_ACERTO ? -50 : 0);
      } else if (melhor.tipo === HOLD) {
        melhor.segurando = true;
        melhor.fonte = fonte;
        melhor.julgamento = j;
        melhor.qualidade = qualidade(dif, j);
        pulsarAnel(melhor.faixa, melhor.cor, 0.6);
      } else {
        melhor.iniciada = true;
        melhor.ativa = true;
        melhor.fonte = temPonteiro ? fonte : "t";
        melhor.proximaAncora = 1;
        melhor.ux = temPonteiro ? x : melhor.px[0];
        melhor.uy = temPonteiro ? y : melhor.py[0];
        pulsarAnel(melhor.faixa, melhor.cor, 0.5);
      }
    }

    function soltarFonte(fonte, tp) {
      for (let i = primeiraViva; i < proxNascer; i++) {
        const n = NOTAS[i];
        if (n.resolvida || n.fonte !== fonte) continue;
        if (n.tipo === HOLD && n.segurando) {
          if (tp >= n.fim - 0.12) acertar(n, n.julgamento, n.qualidade, MARCAS[n.faixa][0], MARCAS[n.faixa][1], 200);
          else errar(n);
        } else if (n.tipo === SLIDE && n.ativa) {
          // Soltar no meio não é erro na hora: o trecho feito fica guardado
          // e dá para retomar enquanto a nota viver.
          n.ativa = false;
        }
      }
    }

    // O trilho avança só pelo que o dedo realmente varreu: cada amostra
    // entre a posição anterior e a atual precisa cair dentro do corredor.
    function avancarArrasto(n, x, y) {
      const passo = R * 0.045;
      const dx = x - n.ux;
      const dy = y - n.uy;
      const k = Math.min(96, Math.max(1, Math.ceil(Math.hypot(dx, dy) / passo)));
      let prog = n.progresso;
      const ultimo = n.acum.length - 1;
      for (let s = 1; s <= k; s++) {
        const sx = n.ux + (dx * s) / k;
        const sy = n.uy + (dy * s) / k;
        const de = prog * n.total;
        const ate = Math.min(1, prog + AVANCO_MAXIMO) * n.total;
        let menor = Infinity;
        let melhor = prog;
        for (let i = 0; i <= ultimo; i++) {
          if (n.acum[i] < de - 1) continue;
          if (n.acum[i] > ate) break;
          const d = (n.px[i] - sx) * (n.px[i] - sx) + (n.py[i] - sy) * (n.py[i] - sy);
          if (d < menor) { menor = d; melhor = n.acum[i] / n.total; }
        }
        if (Math.sqrt(menor) > CORREDOR) break;
        if (melhor > prog) prog = melhor;
      }
      n.progresso = prog;
      n.ux = x;
      n.uy = y;
      if (prog >= ARRASTO_COMPLETO && !n.resolvida) concluirArrasto(n);
    }

    function arrastoParaRetomar(x, y) {
      for (let i = primeiraViva; i < proxNascer; i++) {
        const n = NOTAS[i];
        if (n.tipo !== SLIDE || n.resolvida || !n.iniciada || n.ativa) continue;
        pontoDoCaminho(n, n.progresso);
        if (Math.hypot(px - x, py - y) <= CORREDOR * 1.4) return n;
      }
      return null;
    }

    function diagonal(a, b) {
      const d = (b - a + 8) % 8;
      if (d === 2) return (a + 1) % 8;
      if (d === 6) return (b + 1) % 8;
      return -1;
    }

    function descarregarSeta() {
      const s = setaPendente;
      setaPendente = null;
      setaFaixa[s.codigo] = s.faixa;
      pressionarFaixa(s.faixa, "t" + s.faixa, s.tempo, 0, 0, false);
    }

    /* ======================================================================
       DESENHO
       ====================================================================== */
    function brilho(ctx, cor, x, y, raio, alfa) {
      if (alfa <= 0.01 || raio <= 0.5) return;
      ctx.globalAlpha = Math.min(1, alfa);
      ctx.drawImage(BRILHOS[cor], x - raio, y - raio, raio * 2, raio * 2);
    }

    function retanguloRedondo(ctx, x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }

    function losango(ctx, x, y, tam, rot) {
      const c = Math.cos(rot) * tam;
      const s = Math.sin(rot) * tam;
      ctx.beginPath();
      ctx.moveTo(x + c, y + s);
      ctx.lineTo(x - s, y + c);
      ctx.lineTo(x - c, y - s);
      ctx.lineTo(x + s, y - c);
      ctx.closePath();
    }

    function poligono(ctx, x, y, raio, lados, rot) {
      ctx.beginPath();
      for (let i = 0; i <= lados; i++) {
        const a = rot + (Math.PI * 2 * i) / lados;
        if (i === 0) ctx.moveTo(x + Math.cos(a) * raio, y + Math.sin(a) * raio);
        else ctx.lineTo(x + Math.cos(a) * raio, y + Math.sin(a) * raio);
      }
    }

    // 5 pontas clássica, 6 de cristal, 4 de brilho e 8 de explosão.
    const PONTAS = [5, 6, 4, 8];
    const CINTURA = [0.44, 0.54, 0.4, 0.6];
    function caminhoEstrela(ctx, x, y, raio, interno, pontas, rot) {
      ctx.beginPath();
      for (let i = 0; i < pontas * 2; i++) {
        const r = i % 2 === 0 ? raio : interno;
        const a = rot + (Math.PI * i) / pontas;
        if (i === 0) ctx.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
        else ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
      }
      ctx.closePath();
    }

    function estrela(ctx, x, y, rot, tam, cor, estilo, alfa) {
      const pulso = 0.5 + 0.5 * Math.sin(relogio * 9);
      const pontas = PONTAS[estilo];
      const cintura = CINTURA[estilo];
      ctx.globalCompositeOperation = "lighter";
      brilho(ctx, cor, x, y, tam * 1.7, (0.36 + pulso * 0.12) * alfa);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = alfa;
      caminhoEstrela(ctx, x, y, tam * (1 + pulso * 0.045), tam * cintura, pontas, rot);
      ctx.fillStyle = COR[cor];
      ctx.fill();
      ctx.lineWidth = 2.4;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();
      caminhoEstrela(ctx, x, y, tam * 0.62, tam * cintura * 0.62, pontas, rot);
      ctx.fillStyle = COR_CLARA[cor];
      ctx.fill();
      caminhoEstrela(ctx, x, y, tam * 0.3, tam * cintura * 0.3, pontas, rot);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    function seta(ctx, x, y, ang, tam, estilo) {
      const c = Math.cos(ang) * tam;
      const s = Math.sin(ang) * tam;
      const formas = FORMAS_SETA[estilo];
      ctx.beginPath();
      for (let f = 0; f < formas.length; f++) {
        const pts = formas[f];
        for (let i = 0; i < pts.length; i++) {
          const u = pts[i][0];
          const v = pts[i][1];
          const ax = x + c * u - s * v;
          const ay = y + s * u + c * v;
          if (i === 0) ctx.moveTo(ax, ay);
          else ctx.lineTo(ax, ay);
        }
        ctx.closePath();
      }
      ctx.fill();
    }

    function desenharFundo(ctx) {
      ctx.fillStyle = gradientes.fundo;
      ctx.fillRect(0, 0, LARGURA, ALTURA);
      // Poeira em paralaxe: nasce perto do meio, acelera para fora,
      // cresce e brilha, e some na borda (README do R7).
      const qtd = api.reduzido ? 18 : 46;
      const giro = fase === "tocando" ? 0.35 + energiaAcerto * 0.4 : 0.25;
      ctx.globalCompositeOperation = "lighter";
      for (let i = 0; i < qtd; i++) {
        const a = i * 2.39996 + relogio * 0.05;
        const vel = 0.06 + ((i * 37) % 11) / 90;
        const fasei = (relogio * vel + ((i * 0.6180339) % 1)) % 1;
        const dist = 20 + fasei * fasei * 640;
        const x = CX + Math.cos(a + fasei * giro) * dist;
        const y = CY - 60 + Math.sin(a + fasei * giro) * dist * 0.92;
        const tam = 0.6 + fasei * 2.4;
        ctx.globalAlpha = Math.sin(Math.PI * fasei) * 0.75;
        ctx.fillStyle = i % 3 === 0 ? COR_TEMA : i % 3 === 1 ? COR_TEMA2 : "#ffffff";
        ctx.fillRect(x - tam / 2, y - tam / 2, tam, tam);
      }
      // dois cometas cruzando devagar
      for (let k = 0; k < 2; k++) {
        const ciclo = (relogio / (7 + k * 3) + k * 0.5) % 1;
        if (ciclo > 0.45) continue;
        const p = ciclo / 0.45;
        const sentido = k ? -1 : 1;
        const x = (k ? LARGURA + 40 : -40) + sentido * p * (LARGURA + 80);
        const y = 230 + k * 120 + p * 140;
        ctx.fillStyle = k ? COR_TEMA : COR_TEMA2;
        for (let j = 0; j < 7; j++) {
          ctx.globalAlpha = (1 - j / 7) * 0.5 * Math.sin(Math.PI * p);
          ctx.fillRect(x - sentido * j * 6, y - j * 1.6, 2.4 - j * 0.25, 2.4 - j * 0.25);
        }
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    }

    function batidaPulso() {
      return Math.pow(1 - ((t / BATIDA) % 1), 3);
    }

    function desenharDisco(ctx) {
      ctx.fillStyle = "#000";
      ctx.beginPath();
      ctx.arc(CX, CY, R * 1.012, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = gradientes.disco;
      ctx.beginPath();
      ctx.arc(CX, CY, R * 0.995, 0, Math.PI * 2);
      ctx.fill();

      // A arte da roda (abertura do jogo) bem apagada dentro do disco: um
      // único fundo, sem camadas brigando com as notas.
      if (img.roda) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(CX, CY, R * 0.985, 0, Math.PI * 2);
        ctx.clip();
        ctx.globalAlpha = 0.13 + energiaAcerto * 0.08 + batidaPulso() * 0.04;
        const lado = R * 2.12;
        ctx.drawImage(img.roda, CX - lado / 2, CY - lado / 2, lado, lado);
        ctx.restore();
      }

      // onda da batida saindo do centro
      if (fase === "tocando" && secao(Math.floor(t / COMPASSO)) !== PAUSA) {
        const fasei = (t / BATIDA) % 1;
        ctx.globalAlpha = (1 - fasei) * 0.22;
        ctx.strokeStyle = COR_TEMA;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(CX, CY, R * 0.18 + fasei * (R_ANEL - R * 0.18), 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // guias finas das oito faixas
      ctx.strokeStyle = "rgba(255,255,255,0.06)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let f = 0; f < FAIXAS; f++) {
        const m = MARCAS[f];
        ctx.moveTo(CX + (m[0] - CX) * 0.2, CY + (m[1] - CY) * 0.2);
        ctx.lineTo(CX + (m[0] - CX) * 0.93, CY + (m[1] - CY) * 0.93);
      }
      ctx.stroke();

      // brilho da borda do disco na cor da música
      ctx.globalAlpha = 0.16;
      ctx.strokeStyle = COR_TEMA;
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(CX, CY, R * 1.002, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    function desenharAnel(ctx) {
      const largura = 4;
      const reacao = energiaAcerto + Math.min(1, combo / 40) * 0.26;
      const pulso = fase === "tocando" ? batidaPulso() : 0;
      ctx.strokeStyle = COR_TEMA;
      ctx.globalAlpha = 0.1 + pulso * 0.05 + reacao * 0.12;
      ctx.lineWidth = largura * (3.4 + reacao * 1.6);
      ctx.beginPath();
      ctx.arc(CX, CY, R_ANEL + 1, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = largura;
      ctx.beginPath();
      ctx.arc(CX, CY, R_ANEL, 0, Math.PI * 2);
      ctx.stroke();

      // onda do acerto que corre pelo anel nos dois sentidos
      ctx.lineCap = "round";
      for (const p of pulsosAnel) {
        if (!p.vivo) continue;
        const k = (t - p.ini) / p.dur;
        if (k >= 1 || k < 0) { p.vivo = false; continue; }
        const viagem = (1 - Math.pow(1 - k, 2.2)) * Math.PI * 1.02;
        const some = Math.pow(1 - k, 1.4);
        const rastro = Math.min(viagem, Math.PI * 0.34);
        for (let lado = -1; lado <= 1; lado += 2) {
          const cabeca = p.ang + viagem * lado;
          ctx.strokeStyle = COR[p.cor];
          ctx.globalAlpha = some * 0.45;
          ctx.lineWidth = largura * (2.4 + some * 1.6);
          ctx.beginPath();
          if (lado > 0) ctx.arc(CX, CY, R_ANEL, cabeca - rastro, cabeca);
          else ctx.arc(CX, CY, R_ANEL, cabeca, cabeca + rastro);
          ctx.stroke();
          ctx.globalAlpha = some;
          ctx.strokeStyle = COR_CLARA[p.cor];
          ctx.lineWidth = largura * (1.9 + some * 1.1);
          ctx.beginPath();
          ctx.arc(CX, CY, R_ANEL, cabeca - 0.045, cabeca + 0.045);
          ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;

      // marcadores: miolo escuro + anel branco grosso = leitura de "alvo"
      const rm = R * 0.046;
      for (let f = 0; f < FAIXAS; f++) {
        const mx = MARCAS[f][0];
        const my = MARCAS[f][1];
        const fl = Math.min(1.6, flash[f]);
        const mix = Math.min(1, fl);
        const corF = corFlash[f];
        const pulsoF = reacao * (0.5 + 0.5 * Math.sin(relogio * 7 + f));
        ctx.globalCompositeOperation = "lighter";
        brilho(ctx, mix > 0.05 ? corF : ROSA, mx, my, rm * (2.6 + pulsoF * 0.8 + fl * 1.6), 0.18 + pulsoF * 0.2 + mix * 0.6 + toque[f] * 0.35);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 1;
        const tam = rm * (1 + pulsoF * 0.16 + fl * 0.32);
        ctx.fillStyle = "rgba(3,4,8,0.92)";
        ctx.beginPath();
        ctx.arc(mx, my, tam, 0, Math.PI * 2);
        ctx.fill();
        const corMarca = mix > 0.05 ? COR_CLARA[corF] : "#ffffff";
        ctx.strokeStyle = corMarca;
        ctx.lineWidth = Math.max(2, tam * 0.34);
        ctx.beginPath();
        ctx.arc(mx, my, tam * 0.8, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = corMarca;
        ctx.beginPath();
        ctx.arc(mx, my, tam * 0.26, 0, Math.PI * 2);
        ctx.fill();
        if (fl > 0.02) {
          // arco de energia na linha, saindo do ponto de encaixe
          const abre = (9 + fl * 30) * (Math.PI / 180);
          const base = -Math.PI / 2 + (Math.PI * 2 * f) / FAIXAS;
          ctx.globalAlpha = mix * 0.85;
          ctx.strokeStyle = COR[corF];
          ctx.lineWidth = largura * (1.5 + fl * 2.1);
          ctx.beginPath();
          ctx.arc(CX, CY, R_ANEL, base - abre, base + abre);
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }
      ctx.lineCap = "butt";
    }

    function desenharRotulosTeclas(ctx) {
      if (!temMouse) return;
      for (let f = 0; f < FAIXAS; f++) {
        const a = -Math.PI / 2 + (Math.PI * 2 * f) / FAIXAS;
        const x = CX + Math.cos(a) * (R_ANEL + 24);
        const y = CY + Math.sin(a) * (R_ANEL + 24);
        ctx.fillStyle = "rgba(8,3,24,0.85)";
        ctx.beginPath();
        ctx.arc(x, y, 11, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.35)";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        api.texto(ctx, ROTULOS[f], x, y + 1, { tamanho: 13, peso: 800, cor: "rgba(255,255,255,0.85)" });
      }
    }

    function desenharSelo(ctx) {
      if (!img.selo) return;
      const tocando = fase === "tocando";
      const batida = Math.floor((tocando ? t : relogio) / BATIDA);
      const quadro = ((batida % 8) + 8) % 8;
      const pulso = tocando ? batidaPulso() : 0.5 + 0.5 * Math.sin(relogio * 3);
      const tam = R * 0.36 * (1 + pulso * 0.06);
      ctx.globalCompositeOperation = "lighter";
      brilho(ctx, ROSA, CX, CY, tam * 1.1, 0.35 + pulso * 0.3);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      ctx.drawImage(img.selo, (quadro % 4) * 100, Math.floor(quadro / 4) * 100, 100, 100, CX - tam / 2, CY - tam / 2, tam, tam);
    }

    function desenharArcoAproximacao(ctx, nota) {
      // o arco em volta do marcador enche até fechar no instante do acerto
      const p = chegada(nota, t);
      if (p <= 0 || p >= 1) return;
      const m = MARCAS[nota.faixa];
      ctx.globalAlpha = 0.22 + p * 0.65;
      ctx.strokeStyle = COR[nota.cor];
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(m[0], m[1], R * (0.062 + p * 0.03), -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * p);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    function desenharTap(ctx, nota) {
      const p = (t - (nota.t - APROXIMACAO)) / APROXIMACAO;
      if (p < 0) return;
      posicaoTap(nota, t);
      const x = px;
      const y = py;
      const e = suavizar(Math.min(1, p));
      const alfa = p > 1 ? Math.max(0, 1 - (p - 1) / 0.19) : 1;
      const tam = R * 0.2 * (0.58 + 0.42 * e);
      const pulso = 0.5 + 0.5 * Math.sin(relogio * 16 + nota.faixa);
      ctx.globalCompositeOperation = "lighter";
      // rastro: quatro brilhos voltando para o centro
      const dx = CX - x;
      const dy = CY - y;
      for (let i = 0; i < 4; i++) {
        const k = 0.16 + i * 0.13;
        brilho(ctx, nota.cor, x + dx * k, y + dy * k, tam * (0.42 - i * 0.06), (0.3 - i * 0.05) * (0.35 + e * 0.65) * alfa);
      }
      brilho(ctx, nota.cor, x, y, tam * (0.95 + pulso * 0.08), (0.42 + pulso * 0.1) * alfa);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = alfa;
      if (img.tazos) ctx.drawImage(img.tazos, nota.cor * 112, 0, 112, 112, x - tam / 2, y - tam / 2, tam, tam);
      ctx.globalAlpha = 1;
    }

    function desenharHold(ctx, nota) {
      if (t < nota.t - APROXIMACAO || t > nota.fim + 0.25) return;
      if (nota.resolvida) return;
      const m = MARCAS[nota.faixa];
      const dirx = (m[0] - CX) / R_ANEL;
      const diry = (m[1] - CY) / R_ANEL;
      let hx = m[0];
      let hy = m[1];
      let progresso = 0;
      let comprimento = R * 0.52;
      if (t < nota.t) {
        const e = suavizar(chegada(nota, t));
        hx = CX + (m[0] - CX) * e;
        hy = CY + (m[1] - CY) * e;
        comprimento = Math.min(comprimento, Math.hypot(hx - CX, hy - CY));
      } else {
        progresso = Math.min(1, (t - nota.t) / (nota.fim - nota.t));
        comprimento = R * Math.max(0.06, 0.52 * (1 - progresso));
      }
      // nos últimos 0,16 s a fita recolhe para dentro do alvo
      const falta = nota.fim - t;
      const recolhe = falta >= 0.16 ? 0 : Math.min(1, 1 - falta / 0.16);
      comprimento *= 1 - recolhe;
      const tx = hx - dirx * comprimento;
      const ty = hy - diry * comprimento;
      const ativa = nota.segurando;
      const meia = R * 0.03;
      const pulso = 0.5 + 0.5 * Math.sin(relogio * (ativa ? 7.5 : 3.2));
      const fade = 1 - recolhe;
      ctx.lineCap = "round";
      ctx.strokeStyle = COR[nota.cor];
      ctx.globalAlpha = (ativa ? 0.2 : 0.11) * fade;
      ctx.lineWidth = meia * (3.4 + pulso * 0.4);
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy); ctx.stroke();
      ctx.globalAlpha = (ativa ? 0.7 : 0.45) * fade;
      ctx.lineWidth = meia * 1.55;
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy); ctx.stroke();
      ctx.strokeStyle = COR_CLARA[nota.cor];
      ctx.globalAlpha = (ativa ? 0.95 : 0.62) * fade;
      ctx.lineWidth = Math.max(1.5, meia * 0.52);
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy); ctx.stroke();
      // pulsos curtos correndo para o alvo
      const n = ativa ? 3 : 2;
      const fasei = (relogio * (ativa ? 1.35 : 0.55)) % 1;
      const vao = Math.min(comprimento * 0.2, R * 0.05);
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = Math.max(1.5, meia * 0.44);
      for (let i = 0; i < n; i++) {
        const v = (fasei + i / n) % 1;
        const ax = tx + (hx - tx) * v;
        const ay = ty + (hy - ty) * v;
        ctx.globalAlpha = Math.sin(Math.PI * v) * (ativa ? 0.85 : 0.4) * fade;
        ctx.beginPath(); ctx.moveTo(ax - dirx * vao, ay - diry * vao); ctx.lineTo(ax, ay); ctx.stroke();
      }
      // alvo do hold: anel fino com arco de progresso
      const tam = meia * (1.9 + pulso * (ativa ? 0.12 : 0.04));
      ctx.globalCompositeOperation = "lighter";
      brilho(ctx, nota.cor, hx, hy, tam * 1.9, (ativa ? 0.45 : 0.22) * fade);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 0.45 * fade;
      ctx.strokeStyle = COR[nota.cor];
      ctx.lineWidth = Math.max(1.5, meia * 0.3);
      ctx.beginPath(); ctx.arc(hx, hy, tam, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = (ativa ? 0.98 : 0.7) * fade;
      ctx.strokeStyle = COR_CLARA[nota.cor];
      ctx.lineWidth = Math.max(2, meia * 0.42);
      ctx.beginPath(); ctx.arc(hx, hy, tam, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (progresso > 0 ? progresso : 1)); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.lineCap = "butt";
      // dica para quem nunca jogou
      if (!ativa && t > nota.t - APROXIMACAO * 0.7) {
        api.texto(ctx, "SEGURE", CX + (m[0] - CX) * 0.7, CY + (m[1] - CY) * 0.7 - 22, {
          tamanho: 15, peso: 900, cor: COR_CLARA[nota.cor], contorno: "rgba(0,0,0,.75)",
        });
      }
    }

    function desenharSlide(ctx, nota) {
      if (t < nota.t - APROXIMACAO) return;
      if (nota.resolvida && !nota.finalizando) return;
      let aparece = 1;
      if (t < nota.t) {
        aparece = Math.min(1, Math.max(0, (t - (nota.t - APROXIMACAO)) / (APROXIMACAO * 0.55)));
        aparece = aparece * aparece * (3 - 2 * aparece);
      }
      const n = nota.px.length;
      if (!nota.resolvida) {
        // trilho: faixa escura e fio fino na cor do tazo
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.beginPath();
        ctx.moveTo(nota.px[0], nota.py[0]);
        for (let i = 1; i < n; i++) ctx.lineTo(nota.px[i], nota.py[i]);
        ctx.globalAlpha = 0.78 * aparece;
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = R * 0.07;
        ctx.stroke();
        ctx.globalAlpha = 0.35 * aparece;
        ctx.strokeStyle = COR[nota.cor];
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.lineCap = "butt";
        // setas em cascata, da primeira para a última
        const tam = R * 0.05;
        const qtd = Math.max(3, Math.floor(nota.total / (tam * 3.2)));
        const de = nota.iniciada ? Math.floor(nota.desenho * qtd) : 0;
        for (let i = de; i < qtd; i++) {
          const escalonado = Math.min(1, Math.max(0, aparece * qtd - (i - de) * 0.55));
          if (escalonado <= 0.02) break;
          pontoDoCaminho(nota, (i + 0.5) / qtd);
          ctx.globalAlpha = escalonado;
          ctx.fillStyle = i % 3 === 1 ? COR_CLARA[nota.cor] : COR[nota.cor];
          seta(ctx, px, py, pang, tam, nota.estiloSeta);
        }
        ctx.globalAlpha = 1;
      }
      // a estrela: viaja do centro ao começo do trilho, depois persegue o dedo
      let sx;
      let sy;
      let ang;
      if (!nota.iniciada && t < nota.t) {
        const e = suavizar(chegada(nota, t));
        sx = CX + (nota.px[0] - CX) * e;
        sy = CY + (nota.py[0] - CY) * e;
        ang = Math.atan2(nota.py[0] - CY, nota.px[0] - CX);
      } else {
        pontoDoCaminho(nota, nota.desenho);
        sx = px; sy = py; ang = pang;
      }
      if (nota.ativa || nota.finalizando) {
        ctx.globalCompositeOperation = "lighter";
        for (let g = 1; g <= 3; g++) {
          pontoDoCaminho(nota, Math.max(0, nota.desenho - g * 0.04));
          brilho(ctx, nota.cor, px, py, R * (0.075 - g * 0.012), 0.35);
        }
        ctx.globalCompositeOperation = "source-over";
      }
      estrela(ctx, sx, sy, ang + relogio * 1.5, R * 0.1, nota.cor, nota.estiloEstrela, Math.max(0.35, aparece));
      if (!nota.iniciada && t > nota.t - APROXIMACAO * 0.7) {
        api.texto(ctx, "ARRASTE", nota.px[0] + (CX - nota.px[0]) * 0.28, nota.py[0] + (CY - nota.py[0]) * 0.28 - 26, {
          tamanho: 15, peso: 900, cor: COR_CLARA[nota.cor], contorno: "rgba(0,0,0,.75)",
        });
      }
    }

    function desenharEfeitos(ctx) {
      ctx.lineJoin = "round";
      for (const e of efeitos) {
        if (!e.vivo) continue;
        const prog = (t - e.ini) / e.dur;
        if (prog >= 1 || prog < 0) { e.vivo = false; continue; }
        const vida = 1 - prog;
        if (e.tipo === TAP) {
          // prisma em camadas: losangos girados, estilhaços e polígonos
          const r = R * (0.055 + prog * 0.19);
          ctx.globalCompositeOperation = "lighter";
          brilho(ctx, e.cor, e.x, e.y, r * 1.9, vida * 0.6);
          ctx.globalCompositeOperation = "source-over";
          ctx.globalAlpha = vida * 0.3;
          ctx.fillStyle = "#ffffff";
          ctx.beginPath(); ctx.arc(e.x, e.y, r, 0, Math.PI * 2); ctx.fill();
          for (let c = 0; c < 5; c++) {
            ctx.globalAlpha = vida * (1 - c * 0.135);
            ctx.strokeStyle = MISTURA[e.cor][c];
            ctx.lineWidth = Math.max(2, R * (0.014 - c * 0.0015));
            losango(ctx, e.x, e.y, R * (0.082 + c * 0.031) * (0.34 + prog * 1.34), e.rot + c * Math.PI * 0.2);
            ctx.stroke();
          }
          ctx.globalAlpha = vida * 0.88;
          ctx.strokeStyle = COR[e.cor];
          ctx.lineWidth = 2.5;
          for (let i = 0; i < 12; i++) {
            const a = e.rot + (Math.PI * 2 * i) / 12;
            const d = R * (0.075 + prog * 0.235);
            losango(ctx, e.x + Math.cos(a) * d, e.y + Math.sin(a) * d, R * (0.018 + prog * 0.026), a);
            ctx.stroke();
          }
          for (let c = 0; c < 2; c++) {
            ctx.globalAlpha = vida * (0.76 - c * 0.18);
            poligono(ctx, e.x, e.y, R * (0.08 + c * 0.065 + prog * 0.185), c ? 6 : 8, e.rot * (c ? -1 : 1));
            ctx.stroke();
          }
        } else if (e.tipo === HOLD) {
          // anéis que abrem e raios curtos
          ctx.globalCompositeOperation = "lighter";
          brilho(ctx, e.cor, e.x, e.y, R * (0.12 + prog * 0.3), vida * 0.7);
          ctx.globalCompositeOperation = "source-over";
          for (let c = 0; c < 3; c++) {
            ctx.globalAlpha = vida * (0.9 - c * 0.25);
            ctx.strokeStyle = c === 1 ? COR_CLARA[e.cor] : COR[e.cor];
            ctx.lineWidth = 4 - c;
            ctx.beginPath();
            ctx.arc(e.x, e.y, R * (0.05 + c * 0.05 + prog * (0.2 + c * 0.06)), 0, Math.PI * 2);
            ctx.stroke();
          }
          ctx.globalAlpha = vida;
          ctx.strokeStyle = COR_CLARA[e.cor];
          ctx.lineWidth = 3;
          ctx.beginPath();
          for (let i = 0; i < 10; i++) {
            const a = e.rot + (Math.PI * 2 * i) / 10;
            const d0 = R * (0.08 + prog * 0.2);
            const d1 = d0 + R * 0.06 * vida;
            ctx.moveTo(e.x + Math.cos(a) * d0, e.y + Math.sin(a) * d0);
            ctx.lineTo(e.x + Math.cos(a) * d1, e.y + Math.sin(a) * d1);
          }
          ctx.stroke();
        } else {
          // arrasto: estrelas vazadas abrindo e girando, com setas para fora
          ctx.globalCompositeOperation = "lighter";
          brilho(ctx, e.cor, e.x, e.y, R * (0.14 + prog * 0.32), vida * 0.75);
          ctx.globalCompositeOperation = "source-over";
          for (let c = 0; c < 3; c++) {
            ctx.globalAlpha = vida * (1 - c * 0.25);
            ctx.strokeStyle = c === 1 ? "#ffffff" : COR[e.cor];
            ctx.lineWidth = 3;
            const r = R * (0.08 + c * 0.06 + prog * 0.3);
            caminhoEstrela(ctx, e.x, e.y, r, r * CINTURA[e.estilo], PONTAS[e.estilo], e.rot + prog * (c % 2 ? -2 : 2));
            ctx.stroke();
          }
          ctx.globalAlpha = vida;
          ctx.fillStyle = COR_CLARA[e.cor];
          for (let i = 0; i < 6; i++) {
            const a = e.rot + (Math.PI * 2 * i) / 6;
            const d = R * (0.12 + prog * 0.34);
            seta(ctx, e.x + Math.cos(a) * d, e.y + Math.sin(a) * d, a, R * 0.035, 0);
          }
        }
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    }

    function desenharHud(ctx) {
      const { x, y, w, h } = HUD;
      ctx.fillStyle = "rgba(10,4,30,0.9)";
      retanguloRedondo(ctx, x, y, w, h, 18);
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = gradientes.borda;
      ctx.stroke();

      api.texto(ctx, NOME_MUSICA, x + 20, y + 30, { tamanho: 25, peso: 900, alinhar: "left", cor: "#ffffff" });
      api.texto(ctx, `NORMAL • ${BPM} BPM`, x + 20, y + 56, { tamanho: 14, peso: 800, alinhar: "left", cor: "#ff8ae8" });
      api.texto(ctx, formatarPct(precisao()), x + w - 20, y + 31, { tamanho: 30, peso: 900, alinhar: "right", cor: COR_TEMA2 });
      api.texto(ctx, `COMBO ${combo}`, x + w - 20, y + 57, { tamanho: 15, peso: 800, alinhar: "right", cor: "#ffffff" });

      // Espectro no lugar do vídeo da música (o retângulo central do HUD)
      const ex = x + 20;
      const ew = w - 40;
      const ey = y + 72;
      const eh = 62;
      ctx.fillStyle = "rgba(255,255,255,0.04)";
      ctx.fillRect(ex, ey, ew, eh);
      const passo = ew / 32;
      ctx.fillStyle = gradientes.barras;
      const energia = 0.45 + energiaMusica * 0.55;
      for (let i = 0; i < 32; i++) {
        const ocioso = 0.06 + 0.04 * Math.sin(relogio * 2.2 + i * 0.7);
        const v = Math.min(1, Math.max(ocioso, espectro[i]) * energia);
        const bh = Math.max(3, v * (eh - 6));
        ctx.globalAlpha = 0.45 + v * 0.55;
        ctx.fillRect(ex + i * passo + 1.5, ey + eh - bh - 3, passo - 3, bh);
      }
      ctx.globalAlpha = 1;

      // vida, multiplicador e andamento da música
      const by = y + 150;
      api.texto(ctx, "LIFE", x + 20, by, { tamanho: 13, peso: 900, alinhar: "left", cor: "#ffffff" });
      ctx.fillStyle = "rgba(255,255,255,0.12)";
      ctx.fillRect(x + 58, by - 5, 150, 10);
      ctx.fillStyle = vida > 35 ? "#3dff9a" : "#ff5468";
      ctx.fillRect(x + 58, by - 5, 150 * (vida / 100), 10);
      api.texto(ctx, `${Math.round(vida)}%`, x + 216, by, { tamanho: 13, peso: 800, alinhar: "left", cor: "#ffffff" });
      const mx = x + 272;
      api.texto(ctx, `x${multiplicador}`, mx, by, { tamanho: 18, peso: 900, alinhar: "left", cor: multiplicador > 1 ? "#fff27a" : "rgba(255,255,255,0.45)" });
      const bx = mx + 40;
      const bw = x + w - 72 - bx;
      ctx.fillStyle = "rgba(255,255,255,0.12)";
      ctx.fillRect(bx, by - 3, bw, 6);
      ctx.fillStyle = COR_TEMA;
      ctx.fillRect(bx, by - 3, bw * Math.min(1, t / DURACAO), 6);
      const restante = Math.max(0, Math.ceil(DURACAO - t));
      api.texto(ctx, `${Math.floor(restante / 60)}:${String(restante % 60).padStart(2, "0")}`, x + w - 20, by, {
        tamanho: 13, peso: 800, alinhar: "right", cor: "rgba(255,255,255,0.75)",
      });
    }

    function desenharMeio(ctx) {
      // faixa entre o HUD e o círculo: dica inicial, julgamento e combo
      if (fase === "pronto" || (fase === "tocando" && t < PRIMEIRA_NOTA - 0.9)) {
        ctx.globalAlpha = fase === "pronto" ? 1 : Math.min(1, (PRIMEIRA_NOTA - 0.9 - t) * 2);
        api.texto(ctx, "TOQUE NA FAIXA QUANDO", CX, 268, { tamanho: 24, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.6)" });
        api.texto(ctx, "O TAZO ENCAIXAR NO ANEL", CX, 300, { tamanho: 24, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.6)" });
        api.texto(ctx, temMouse ? "Teclas A S D F J K L Ç • segure as fitas • arraste as estrelas" : "Segure as fitas • arraste as estrelas", CX, 340, {
          tamanho: 15, peso: 700, cor: "#ff8ae8",
        });
        ctx.globalAlpha = 1;
      }
      const idade = t - tempoJulgamento;
      if (ultimoJulgamento >= 0 && idade < 0.7) {
        const j = JULGAMENTOS[ultimoJulgamento];
        const k = idade / 0.7;
        const escala = k < 0.12 ? 0.7 + (k / 0.12) * 0.45 : 1.15 - Math.min(0.15, (k - 0.12) * 0.6);
        ctx.globalAlpha = k > 0.7 ? (1 - k) / 0.3 : 1;
        api.texto(ctx, j.nome, CX, 262, { tamanho: 50 * escala, peso: 900, cor: j.cor, contorno: "rgba(0,0,0,.65)" });
        ctx.globalAlpha = 1;
      }
      if (combo >= 3) {
        api.texto(ctx, String(combo), CX, 336, { tamanho: 56 + comboPulo * 10, peso: 900, cor: "#ffffff", contorno: COR_TEMA });
        api.texto(ctx, "COMBO", CX, 378, { tamanho: 15, peso: 900, cor: "#ff8ae8" });
      }
    }

    function desenharCapa(ctx) {
      if (img.abertura) ctx.drawImage(img.abertura, 0, 0, LARGURA, ALTURA);
      else { ctx.fillStyle = "#0d0326"; ctx.fillRect(0, 0, LARGURA, ALTURA); }
      // as áreas neon da arte "respiram", como o shader da abertura
      const pulso = 0.5 + 0.5 * Math.sin(relogio * 2.4);
      ctx.globalCompositeOperation = "lighter";
      brilho(ctx, ROSA, LARGURA / 2, ALTURA * 0.47, 330, 0.08 + pulso * 0.1);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      if (img.logo) ctx.drawImage(img.logo, LARGURA / 2 - 60, ALTURA - 96, 120, 120 * (img.logo.height / img.logo.width));
    }

    /* ======================================================================
       A PARTIDA (contrato do console)
       ====================================================================== */
    return {
      iniciar() {
        chamadasIniciar++;
        // a primeira chamada é a do console montando o jogo (atrás da capa);
        // as próximas são "Jogar" — e aí já houve um gesto da pessoa.
        fase = chamadasIniciar === 1 ? "capa" : "pronto";
        t = 0;
        pontos = 0; combo = 0; comboMax = 0; multiplicador = 1;
        somaQualidade = 0; julgados = 0; erros = 0;
        contagem.fill(0);
        vida = 100; energiaMusica = 1; energiaAcerto = 0;
        proxNascer = 0; primeiraViva = 0; passoVisual = 0;
        ultimoJulgamento = -1; tempoJulgamento = -9; comboPulo = 0;
        tempoMostrado = -1; classificado = false;
        flash.fill(0); toque.fill(0); espectro.fill(0);
        ponteiros.clear(); teclasPresas.clear(); setaPendente = null;
        for (const k of Object.keys(setaFaixa)) delete setaFaixa[k];
        for (const e of efeitos) e.vivo = false;
        for (const p of pulsosAnel) p.vivo = false;
        for (const n of NOTAS) {
          n.resolvida = false; n.segurando = false; n.ativa = false;
          n.iniciada = false; n.finalizando = false; n.aguardandoEstrela = false;
          n.progresso = 0; n.desenho = 0; n.fonte = null; n.proximaAncora = 1;
        }
        audio.cursor = 0;
        audio.deslocamento = null;
        if (fase === "pronto") {
          const ativacao = navigator.userActivation;
          if (!ativacao || ativacao.isActive || ativacao.hasBeenActive) acordarAudio();
          novoBus();
        }
        api.placar({ pontos: 0, tempo: DURACAO, info: "" });
        infoMostrada = "";
      },

      atualizar(dt) {
        quadroPerf = performance.now();
        if (fase === "pronto") {
          fase = "tocando";
          audio.ligado = somLigado();
          if (audio.ligado) acordarAudio();
          atualizarVolume();
        }
        if (fase !== "tocando") return;
        t += dt;

        // mudo do console: confere algumas vezes por segundo
        audio.checar -= dt;
        if (audio.checar <= 0) {
          audio.checar = 0.25;
          const ligado = somLigado();
          if (ligado !== audio.ligado) {
            audio.ligado = ligado;
            if (ligado) { acordarAudio(); atualizarVolume(); }
            else if (audio.ctx) audio.ctx.suspend().catch(() => {});
          }
        }
        agendarMusica();

        // barras do HUD batem no instante exato de cada passo
        soVisual = true;
        while (passoVisual < PASSOS && passoVisual * PASSO <= t) passoMusica(passoVisual++, 0);
        soVisual = false;
        const queda = Math.exp(-dt * 7);
        for (let i = 0; i < 32; i++) espectro[i] *= queda;

        if (setaPendente && tempoAgora() - setaPendente.tempo > 0.05) descarregarSeta();

        while (proxNascer < TOTAL_NOTAS && NOTAS[proxNascer].t - APROXIMACAO <= t) proxNascer++;

        for (let i = primeiraViva; i < proxNascer; i++) {
          const n = NOTAS[i];
          if (n.tipo === SLIDE && (n.iniciada || n.finalizando)) {
            // a estrela desenhada persegue o progresso real a velocidade
            // limitada: o gesto sempre aparece percorrendo o trilho
            const alvo = n.finalizando ? 1 : n.progresso;
            const vel = n.finalizando || n.aguardandoEstrela ? 5.2 : 2.6;
            n.desenho = Math.min(alvo, n.desenho + dt * vel);
            if (n.aguardandoEstrela && !n.resolvida && n.desenho >= n.progresso - 0.001) concluirArrasto(n);
            if (n.finalizando && n.desenho >= 0.999) {
              n.finalizando = false;
              const ultima = MARCAS[n.caminho[n.caminho.length - 1]];
              novoEfeito(SLIDE, ultima[0], ultima[1], n.cor, 0.6, n.estiloEstrela);
            }
          }
          if (n.resolvida) continue;
          if (n.tipo === TAP) {
            if (t > n.t + JANELA_ACERTO) errar(n);
          } else if (n.tipo === HOLD) {
            if (n.segurando) {
              if (t >= n.fim) acertar(n, n.julgamento, n.qualidade, MARCAS[n.faixa][0], MARCAS[n.faixa][1], 200);
            } else if (t > n.t + JANELA_ACERTO) errar(n);
          } else if (n.iniciada) {
            if (t > n.fim + FOLGA_ARRASTO) errar(n);
          } else if (t > n.t + JANELA_ACERTO * ESCALA_JANELA_ARRASTO) errar(n);
        }
        while (primeiraViva < proxNascer && NOTAS[primeiraViva].resolvida && !NOTAS[primeiraViva].finalizando) primeiraViva++;

        for (let f = 0; f < FAIXAS; f++) {
          flash[f] = Math.max(0, flash[f] - dt * 3.1);
          toque[f] = Math.max(0, toque[f] - dt * 5);
        }
        energiaAcerto = Math.max(0, energiaAcerto - dt * 1.6);
        comboPulo = Math.max(0, comboPulo - dt * 6);

        const restante = Math.max(0, Math.ceil(DURACAO - t));
        if (restante !== tempoMostrado) { tempoMostrado = restante; api.placar({ tempo: restante }); }

        if (t >= DURACAO + 0.8 && primeiraViva >= TOTAL_NOTAS) {
          fase = "fim";
          silenciar(0.5);
          window.setTimeout(() => { if (fase === "fim" && audio.ctx) audio.ctx.suspend().catch(() => {}); }, 700);
          const pct = precisao();
          classificado = pct >= 70;
          api.terminar({
            pontos,
            titulo: classificado ? "CLASSIFICADO!" : "NÃO CLASSIFICADO",
            detalhe: `Precisão ${formatarPct(pct)} · ${contagem[0]} PERFECT · ${erros} MISS · combo máx. ${comboMax}`
              + (classificado ? "" : " · mínimo 70%"),
          });
        }
      },

      desenhar(ctx) {
        relogio = performance.now() / 1000;
        prepararGradientes(ctx);
        if (fase === "capa") { desenharCapa(ctx); return; }
        desenharFundo(ctx);
        desenharDisco(ctx);
        desenharAnel(ctx);
        desenharSelo(ctx);
        for (let i = primeiraViva; i < proxNascer; i++) {
          const n = NOTAS[i];
          if (!n.resolvida && (n.tipo === TAP || (n.tipo === HOLD && !n.segurando))) desenharArcoAproximacao(ctx, n);
        }
        // gestos longos por baixo, tazos por cima; o mais próximo do anel
        // é desenhado por último para ficar na frente
        for (let i = proxNascer - 1; i >= primeiraViva; i--) {
          const n = NOTAS[i];
          if (n.tipo === HOLD) desenharHold(ctx, n);
          else if (n.tipo === SLIDE) desenharSlide(ctx, n);
        }
        for (let i = proxNascer - 1; i >= primeiraViva; i--) {
          const n = NOTAS[i];
          if (n.tipo === TAP && !n.resolvida) desenharTap(ctx, n);
        }
        desenharEfeitos(ctx);
        // toque do dedo: anel fino onde ele está (o jogo não tem cursor)
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.5;
        for (const p of ponteiros.values()) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 22, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        desenharRotulosTeclas(ctx);
        desenharHud(ctx);
        desenharMeio(ctx);
        if (fase === "fim") {
          ctx.fillStyle = "rgba(3,1,12,0.55)";
          ctx.fillRect(0, 0, LARGURA, ALTURA);
          api.texto(ctx, classificado ? "CLASSIFICADO" : "NÃO CLASSIFICADO", CX, CY, {
            tamanho: 40, peso: 900, cor: classificado ? "#3dff9e" : "#ff5468", contorno: "rgba(0,0,0,.7)",
          });
          api.texto(ctx, formatarPct(precisao()), CX, CY + 48, { tamanho: 30, peso: 900, cor: "#ffffff" });
        }
      },

      apertar(x, y, id) {
        if (fase !== "tocando") return;
        acordarAudio();
        const tp = tempoAgora();
        ponteiros.set(id, { x, y });
        const retomar = arrastoParaRetomar(x, y);
        if (retomar) {
          retomar.ativa = true;
          retomar.fonte = id;
          retomar.ux = x;
          retomar.uy = y;
          return;
        }
        const faixa = faixaDoPonto(x, y);
        if (faixa >= 0) pressionarFaixa(faixa, id, tp, x, y, true);
      },

      mover(x, y, id) {
        const p = ponteiros.get(id);
        if (!p) return;
        p.x = x;
        p.y = y;
        if (fase !== "tocando") return;
        for (let i = primeiraViva; i < proxNascer; i++) {
          const n = NOTAS[i];
          if (n.tipo === SLIDE && n.ativa && !n.resolvida && n.fonte === id) avancarArrasto(n, x, y);
        }
      },

      soltar(x, y, id) {
        if (!ponteiros.has(id)) return;
        ponteiros.delete(id);
        if (fase !== "tocando") return;
        soltarFonte(id, tempoAgora());
      },

      tecla(codigo, apertada) {
        if (fase !== "tocando") return;
        const tp = tempoAgora();
        if (codigo in SETAS) {
          if (apertada) {
            if (teclasPresas.has(codigo)) return;
            teclasPresas.add(codigo);
            acordarAudio();
            const f = SETAS[codigo];
            if (setaPendente) {
              const dg = diagonal(setaPendente.faixa, f);
              if (dg >= 0) {
                const tempo = setaPendente.tempo;
                setaFaixa[setaPendente.codigo] = dg;
                setaFaixa[codigo] = dg;
                setaPendente = null;
                pressionarFaixa(dg, "t" + dg, tempo, 0, 0, false);
                return;
              }
              descarregarSeta();
            }
            // espera um instante: pode ser a primeira metade de uma diagonal
            setaPendente = { codigo, faixa: f, tempo: tp };
          } else {
            teclasPresas.delete(codigo);
            if (setaPendente && setaPendente.codigo === codigo) descarregarSeta();
            const f = setaFaixa[codigo];
            if (f === undefined) return;
            for (const c of Object.keys(setaFaixa)) if (setaFaixa[c] === f) delete setaFaixa[c];
            soltarFonte("t" + f, tp);
          }
          return;
        }
        const faixa = TECLAS[codigo];
        if (faixa === undefined) return;
        if (apertada) {
          if (teclasPresas.has(codigo)) return; // repetição automática do teclado
          teclasPresas.add(codigo);
          acordarAudio();
          pressionarFaixa(faixa, "t" + faixa, tp, 0, 0, false);
        } else {
          teclasPresas.delete(codigo);
          soltarFonte("t" + faixa, tp);
        }
      },

      destruir() {
        fase = "fim";
        if (audio.ctx) {
          try { audio.ctx.close(); } catch (erro) { /* já fechado */ }
        }
        audio.ctx = null;
        audio.bus = null;
      },
    };
  },
};
