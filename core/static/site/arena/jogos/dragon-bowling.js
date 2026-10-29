/* ======================================================================
   DRAGON BOWLING — a máquina de boliche do dragão, no simulador.

   Esta é a tela da máquina de verdade (dragonbowling1-android7.1, o jogo
   da TV Box, Godot 3.6) portada para o canvas. Nada aqui é física
   inventada: a jogada, a queda dos pinos, os textos, o placar e as telas
   são os do game.gd, pino.gd e bola.gd, traduzidos linha a linha.

   COMO A MÁQUINA JOGA

   A pista do gabinete tem 5 sensores de bola, ligados na placa Zero Delay
   como botões (autoload/ArcadeControls.gd):

     Z  JOGADA ESQUERDA ..... a bola vai no pino 7 (só ele cai)
     X  MEIO ESQUERDO ....... faixa dos pinos 2, 4 e 8
     C  STRIKE (CENTRO) ..... faixa dos pinos 1 e 5 ("bolinha": com o rack
                              cheio na primeira bola é strike garantido)
     V  MEIO DIREITO ........ faixa dos pinos 3, 6 e 9
     B  JOGADAS EXTREMAS .... a bola vai no pino 10 (só ele cai)

   O game.gd transforma o sensor em tudo o resto: o caminho da bola (curva
   de Bézier do bola.gd), o primeiro pino tocado (PINOS_DA_FAIXA e o
   corredor da bola), a energia passada de pino a pino
   (_aplicar_impulso_realista, _propagar_colisao_curta, receber_forca e
   simular_empurrao do pino.gd), as quedas forçadas (Z/B pino único, fundo
   de X/V, strike do centro, "C depois de lateral"), os avisos (STRIKE!,
   SPARE!, ACERTO!, PRA FORA!), o tremor da câmera, o brilho das canaletas
   e as regras (3 rounds, até 3 tentativas, placar = pinos derrubados).

   NO SIMULADOR

   A pessoa arrasta a bola e solta. O ponto em que o gesto cruza a linha
   dos sensores (ou o prolongamento do gesto até ela) escolhe o sensor,
   da esquerda para a direita: Z, X, C, V, B -- as 5 faixas iguais da
   largura da pista ali. Toque sem arrasto não joga. Teclado: Z X C V B
   (e A S D F G, o modo teclado da Zero Delay); Espaço e Enter são o C.

   A tela é a lógica do jogo (1024 x 1536, autoload/Tela.gd) esticada até
   540 x 960 do mesmo jeito que a TV da máquina estica (aspecto ignorado):
   tudo é desenhado em coordenadas do jogo.

   O MOTOR

   O GDScript espera com yield (timer, quadro, tween). Aqui as mesmas
   funções são geradores (function*): o Motor retoma cada uma na mesma
   ordem do Godot 3 (quadro novo, nós, timers, tweens), e os Tweens seguem
   as regras do SceneTreeTween (etapas, paralelo, encadear, valor inicial
   lido quando a etapa começa, o último tween a escrever vence).

   Desempenho: nada de shadowBlur por quadro e nada alocado nos laços de
   desenho. A pista fica pronta numa tela fora (copiada inteira a cada
   quadro), a HUD em pedaços prontos que só se redesenham quando um valor
   muda, e o brilho da pista (shaders/brilho_pista.shader) é feito numa
   tela pequena com as máscaras do jogo e somado à pista uma vez só.
   ====================================================================== */

const LARGURA = 540;
const ALTURA = 960;

// A tela do jogo: sempre em pé, 1024 x 1536 (autoload/Tela.gd).
const TELA_W = 1024;
const TELA_H = 1536;
const SX = LARGURA / TELA_W;
const SY = ALTURA / TELA_H;
const TAU = Math.PI * 2;

const PASTA = new URL("./boliche/dragon/", import.meta.url);

/* ----------------------------------------------------------------------
   AS LETRAS DO JOGO (fonts/*.ttf, reduzidas às letras usadas)
   As métricas são as da tabela hhea de cada fonte: o Godot 3 centra o
   Label pela altura ascendente + descendente da fonte.
   ---------------------------------------------------------------------- */
const FONTE_ARCADE = "DB Arcade";     // arcade_impact.ttf (Luckiest Guy): avisos e títulos
const FONTE_PAINEL = "DB Painel";     // painel_arcade.ttf (Bungee): placar e painéis
const FONTE_PADRAO = "DB Padrao";     // padrao_opensans.ttf (Open Sans SemiBold): o tema padrão
const RESERVA = {
  [FONTE_ARCADE]: `"${FONTE_ARCADE}", "Luckiest Guy", Impact, sans-serif`,
  [FONTE_PAINEL]: `"${FONTE_PAINEL}", "Bungee", Impact, sans-serif`,
  [FONTE_PADRAO]: `"${FONTE_PADRAO}", "Open Sans", Arial, sans-serif`,
};
const METRICAS = {
  [FONTE_ARCADE]: { asc: 1440 / 2048, desc: 608 / 2048 },
  [FONTE_PAINEL]: { asc: 1020 / 1000, desc: 300 / 1000 },
  [FONTE_PADRAO]: { asc: 2189 / 2048, desc: 600 / 2048 },
};
const ARQUIVOS_DE_FONTE = [
  [FONTE_ARCADE, "fontes/luckiest-guy.woff2"],
  [FONTE_PAINEL, "fontes/bungee.woff2"],
  [FONTE_PADRAO, "fontes/open-sans-semibold.woff2"],
];
const ESPACO_ENTRE_LINHAS = 3;        // constante "line_spacing" do Label no Godot 3

// Os dois emojis do jogo (fonts/emoji_do_jogo.ttf, Noto Color Emoji em
// bitmap de 136 x 128 no tamanho 109): o desenho é posto na linha de base
// da fonte principal, com o avanço e a altura da fonte de emoji.
const EMOJI = { "\u{1F3B3}": 0, "\u{1F3C6}": 1 };   // 🎳 e 🏆
const EMOJI_CEL_W = 136;
const EMOJI_CEL_H = 128;
const EMOJI_LARGURA = 136 / 109;
const EMOJI_ALTURA = 128 / 109;
const EMOJI_TOPO = 101 / 109;

/* ----------------------------------------------------------------------
   AS CORES DO game.gd (Color do Godot, de 0 a 1)
   ---------------------------------------------------------------------- */
const COR_STRIKE = [1.0, 0.50, 0.08];
const COR_SPARE = [1.0, 0.78, 0.22];
const COR_MISS = [1.0, 0.25, 0.22];
const COR_ACERTO = [1.0, 0.93, 0.25];
const COR_ROUND = [0.55, 0.92, 1.0];
const COR_BG_PANEL = [0.012, 0.020, 0.042, 0.97];
const COR_BORDA_CYAN = [0.15, 0.75, 1.00, 0.70];
const COR_BORDA_YELLOW = [1.00, 0.82, 0.14, 0.75];
const COR_BORDA_GREEN = [0.20, 1.00, 0.20, 0.85];
const COR_BORDA_PURPLE = [0.75, 0.20, 1.00, 0.70];
const COR_GLOW_CYAN = [0.15, 0.75, 1.00, 0.08];
const COR_GLOW_PURPLE = [0.75, 0.20, 1.00, 0.08];
const COR_TEXTO_CYAN = [0.55, 0.92, 1.00];
const COR_TEXTO_YELLOW = [1.00, 0.90, 0.20];
const COR_TEXTO_GREEN = [0.22, 1.00, 0.22];
const COR_TEXTO_ORANGE = [1.00, 0.65, 0.10];
const COR_TEXTO_PURPLE = [0.90, 0.40, 1.00];
const COR_TEXTO_BRANCO = [0.92, 0.97, 1.00];
const COR_CONTORNO_PAINEL = [0.01, 0.01, 0.02];
const COR_CONTORNO_LABEL = [0.03, 0.04, 0.08];
const SOMBRA_PAINEL = [0, 0, 0, 0.45];

/* ----------------------------------------------------------------------
   AS REGRAS E OS TEMPOS (game.gd)
   ---------------------------------------------------------------------- */
const TAM_AVISO_PADRAO = 88;
const TAM_AVISO_STRIKE = 108;
const TAM_ROUND_AVISO = 78;
const ROUNDS = 3;                     // round_base_por_jogador (1 jogador)
const MAX_TENTATIVAS = 3;
const ESPERA_FISICA_S = 1.2;
const ESPERA_STRIKE_S = 1.8;
const ESPERA_ROUND_FECHADO_S = 1.6;
const ESPERA_PROXIMA_TENTATIVA_S = 0.3;
const ESPERA_FIM_DE_ROUND_S = 1.5;
const MESMA_BOLA_S = 1.2;             // MESMA_BOLA_MS: outro sensor logo depois é a mesma bola
const VALIDADE_JOGADA_PENDENTE_S = 10;
const DESCIDA_MONTAGEM_PINOS = 120;
const TEMPO_TELA_FINAL = 17;
// end-game.wav tem 6,163 s e o jogo corta os 2 últimos (_tocar_audio_unico_ate_fim)
const ESPERA_SOM_FIM_DE_JOGO = 6.163 - 2.0;
// No simulador o console mostra o "jogar de novo" depois de a tela final aparecer.
const ESPERA_ENTREGAR_RESULTADO = 2.6;

const CONFIG_JOGADAS = {
  Z: { dir: [-0.74, -1.0], forca: 0.96, spin: -0.10 },
  X: { dir: [-0.48, -1.0], forca: 1.08, spin: -0.04 },
  C: { dir: [0.00, -1.0], forca: 1.08, spin: 0.00 },
  V: { dir: [0.48, -1.0], forca: 1.08, spin: 0.04 },
  B: { dir: [0.74, -1.0], forca: 0.96, spin: 0.10 },
};

// A faixa de cada tecla: os pinos que a bola daquela tecla alcança de frente.
const PINOS_DA_FAIXA = { Z: [7], X: [2, 4, 8], C: [1, 5], V: [3, 6, 9], B: [10] };

const VIZINHOS_PINOS = {
  1: [2, 3, 5], 2: [1, 3, 4, 5], 3: [1, 2, 5, 6], 4: [2, 5, 7, 8],
  5: [1, 2, 3, 4, 6, 8, 9], 6: [3, 5, 9, 10], 7: [4, 8], 8: [4, 5, 7, 9],
  9: [5, 6, 8, 10], 10: [6, 9],
};

// organizar_pinos: o rack em perspectiva, do pino 1 (frente) às pontas.
const RACK_CENTRO_X = 512;
const RACK_BASE_Y = 755;
const RACK_ESP_X = 74;
const RACK_ESP_Y = 63;
const RACK = {
  1: [0, 0, 1.00, 72],
  2: [-0.5, -1, 0.988, 66], 3: [0.5, -1, 0.988, 66],
  4: [-1, -2, 0.972, 60], 5: [0, -2, 0.972, 60], 6: [1, -2, 0.972, 60],
  7: [-1.5, -3, 0.952, 54], 8: [-0.5, -3, 0.952, 54], 9: [0.5, -3, 0.952, 54], 10: [1.5, -3, 0.952, 54],
};

/* pino.gd */
const PINO = {
  empurraoMaxX: 28, empurraoMaxY: 22, duracaoEmpurrao: 0.080, duracaoTombo: 0.17,
  rotacaoMaxQueda: 138, distanciaVooMax: 70,
  atritoPlano: 0.94, atritoRotacional: 0.91, limiarDeslocamento: 0.08,
  limiarColisaoEmCadeia: 0.12, ganhoRotacao: 108, ganhoDeslocamento: 68, deslocamentoMaxSemCair: 12,
  larguraVisual: 76, alturaVisual: 144, larguraColisao: 48, alturaColisao: 88,
  limiarQueda: 0.15, limiarQuaseQueda: 0.07, linhaBase: 26,
  intensidadeQuique: 1.32, quiqueY: 20, quiqueX: 8, rotacaoQuique: 11,
  esperaAposQueda: 0.85, fadeAposQueda: 0.28,
};
const REF_IDLE_W = 128;               // o quadro "idle" do pino.tscn (pino_em_pe.png)
const REF_IDLE_H = 256;
const ROTULO_PINO_W = 56;
const ROTULO_PINO_H = 32;

/* bola.gd */
const BOLA = {
  escalaPerto: 0.82, escalaLonge: 0.58, opacidadeLonge: 0.90,
  margemSpawnInferior: 180, yImpacto: 745, yCacapa: 500, deslocamentoCacapaX: 12,
  meiaBase: 236, meiaTopo: 166, fps: 27, quadros: 8, celW: 153, celH: 204,
};
const BOLA_INICIO = [TELA_W * 0.5, TELA_H + BOLA.margemSpawnInferior];

/* A pista (ajustar_fundo_fullscreen): cobre a tela com 2% de sobra,
   centrada 8 px acima do meio. */
const PISTA_ESCALA = 1.02;
const PISTA = {
  x: TELA_W * 0.5 - TELA_W * PISTA_ESCALA * 0.5,
  y: TELA_H * 0.5 - 8 - TELA_H * PISTA_ESCALA * 0.5,
  w: TELA_W * PISTA_ESCALA,
  h: TELA_H * PISTA_ESCALA,
};

/* O brilho da pista (shaders/brilho_pista.shader + Compat.avancar_brilho). */
const BRILHO_INTENSIDADE = 0.55;
const BRILHO_VELOCIDADE = 1.2;
const MASCARA_W = 256;
const MASCARA_H = 384;

/* O ARRASTO DO SIMULADOR (a única coisa que a máquina não tem: lá a bola
   é de verdade). A bola descansa embaixo; arrastada para cima e solta, o
   ponto em que o gesto cruza a linha dos sensores escolhe a tecla. */
const BOLA_DE_MAO = [512, 1430];
const LINHA_DOS_SENSORES = 1150;
const INICIO_DO_ARRASTO = 760;        // o dedo pega a bola da metade de baixo para baixo
const ARRASTO_MINIMO = 60;            // em pontos do jogo, para cima
const TECLAS_DOS_SENSORES = ["Z", "X", "C", "V", "B"];

const TECLAS = {
  KeyZ: "Z", KeyX: "X", KeyC: "C", KeyV: "V", KeyB: "B",
  KeyA: "Z", KeyS: "X", KeyD: "C", KeyF: "V", KeyG: "B",
  Space: "C", Enter: "C", NumpadEnter: "C",
};

/* ----------------------------------------------------------------------
   CONTINHAS
   ---------------------------------------------------------------------- */
const lim = (v, a, b) => (v < a ? a : v > b ? b : v);
const mistura = (a, b, t) => a + (b - a) * t;
const inverso = (a, b, v) => (a === b ? 0 : (v - a) / (b - a));
const aleatorio = (a, b) => a + Math.random() * (b - a);
const sinal = (v) => (v > 0 ? 1 : v < 0 ? -1 : 0);
const posmod = (v, m) => ((v % m) + m) % m;
const dist = (ax, ay, bx, by) => Math.hypot(ax - bx, ay - by);

function css(c, alfa = 1) {
  const a = (c.length > 3 ? c[3] : 1) * alfa;
  return `rgba(${Math.round(lim(c[0], 0, 1) * 255)},${Math.round(lim(c[1], 0, 1) * 255)},${Math.round(lim(c[2], 0, 1) * 255)},${a})`;
}

function novaTela(w, h) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.ceil(w));
  c.height = Math.max(1, Math.ceil(h));
  return c;
}

/* ----------------------------------------------------------------------
   AS CURVAS DO TWEEN DO GODOT (Tween.TRANS_* e EASE_*), de 0 a 1
   ---------------------------------------------------------------------- */
const T = { LINEAR: 0, SINE: 1, QUINT: 2, QUART: 3, QUAD: 4, EXPO: 5, CUBIC: 7, CIRC: 8, BOUNCE: 9, BACK: 10 };
const E = { IN: 0, OUT: 1, IN_OUT: 2, OUT_IN: 3 };
const BACK_S = 1.70158;

function bounceOut(t) {
  if (t < 1 / 2.75) return 7.5625 * t * t;
  if (t < 2 / 2.75) { t -= 1.5 / 2.75; return 7.5625 * t * t + 0.75; }
  if (t < 2.5 / 2.75) { t -= 2.25 / 2.75; return 7.5625 * t * t + 0.9375; }
  t -= 2.625 / 2.75;
  return 7.5625 * t * t + 0.984375;
}

function curvaIn(trans, t) {
  switch (trans) {
    case T.SINE: return 1 - Math.cos(t * Math.PI / 2);
    case T.QUINT: return t * t * t * t * t;
    case T.QUART: return t * t * t * t;
    case T.QUAD: return t * t;
    case T.EXPO: return t === 0 ? 0 : Math.pow(2, 10 * (t - 1)) - 0.001;
    case T.CUBIC: return t * t * t;
    case T.CIRC: return -(Math.sqrt(1 - t * t) - 1);
    case T.BOUNCE: return 1 - bounceOut(1 - t);
    case T.BACK: return t * t * ((BACK_S + 1) * t - BACK_S);
    default: return t;
  }
}

function curvaOut(trans, t) {
  switch (trans) {
    case T.SINE: return Math.sin(t * Math.PI / 2);
    case T.QUINT: { const u = t - 1; return u * u * u * u * u + 1; }
    case T.QUART: { const u = t - 1; return -(u * u * u * u - 1); }
    case T.QUAD: return -t * (t - 2);
    case T.EXPO: return t === 1 ? 1 : 1.001 * (-Math.pow(2, -10 * t) + 1);
    case T.CUBIC: { const u = t - 1; return u * u * u + 1; }
    case T.CIRC: { const u = t - 1; return Math.sqrt(1 - u * u); }
    case T.BOUNCE: return bounceOut(t);
    case T.BACK: { const u = t - 1; return u * u * ((BACK_S + 1) * u + BACK_S) + 1; }
    default: return t;
  }
}

function curva(trans, ease, t) {
  if (trans === T.LINEAR) return t;
  if (ease === E.IN) return curvaIn(trans, t);
  if (ease === E.OUT) return curvaOut(trans, t);
  if (ease === E.IN_OUT) {
    // As duas do Godot que não são o "meio in, meio out" comum:
    if (trans === T.BACK) {
      const s = BACK_S * 1.525;
      let u = t * 2;
      if (u < 1) return 0.5 * (u * u * ((s + 1) * u - s));
      u -= 2;
      return 0.5 * (u * u * ((s + 1) * u + s) + 2);
    }
    if (trans === T.EXPO) {
      if (t === 0) return 0;
      if (t === 1) return 1;
      const u = t * 2;
      if (u < 1) return 0.5 * Math.pow(2, 10 * (u - 1)) - 0.0005;
      return 0.5 * 1.0005 * (-Math.pow(2, -10 * (u - 1)) + 2);
    }
    return t < 0.5 ? curvaIn(trans, t * 2) * 0.5 : curvaOut(trans, t * 2 - 1) * 0.5 + 0.5;
  }
  return t < 0.5 ? curvaOut(trans, t * 2) * 0.5 : curvaIn(trans, t * 2 - 1) * 0.5 + 0.5;
}

/* ----------------------------------------------------------------------
   O TWEEN (SceneTreeTween do Godot 3.5)

   Cada tween_* entra numa ETAPA: em sequência abre uma etapa nova; com
   parallel() (ou set_parallel) entra na etapa atual; chain() volta a
   abrir. A etapa acaba quando todos os seus terminam, e o tempo que sobrou
   passa para a seguinte. O valor inicial de cada propriedade é lido quando
   a etapa dela começa. Uma propriedade é um número ou uma lista (Vector2,
   Color), e "campo:a"/"campo:x"/"campo:y" mexe num item só.
   ---------------------------------------------------------------------- */
const INDICE_DO_CAMPO = { x: 0, y: 1, r: 0, g: 1, b: 2, a: 3 };

class Interpolador {
  constructor(obj, chave, alvo, duracao, trans, ease) {
    const partes = chave.split(":");
    this.obj = obj;
    this.campo = partes[0];
    this.indice = partes.length > 1 ? INDICE_DO_CAMPO[partes[1]] : -1;
    this.alvo = Array.isArray(alvo) ? alvo.slice() : alvo;
    this.duracao = duracao;
    this.trans = trans;
    this.ease = ease;
    this.atraso = 0;
    this.inicial = null;
  }

  com(trans) { this.trans = trans; return this; }
  suave(ease) { this.ease = ease; return this; }
  depois(atraso) { this.atraso = atraso; return this; }

  comecar() {
    this.decorrido = 0;
    this.terminou = false;
    this.lerInicial = true;
  }

  ler() {
    const v = this.obj[this.campo];
    return this.indice >= 0 ? v[this.indice] : v;
  }

  escrever(t) {
    const destino = this.obj[this.campo];
    if (Array.isArray(this.alvo)) {
      for (let i = 0; i < this.alvo.length; i++) destino[i] = mistura(this.inicial[i], this.alvo[i], t);
    } else if (this.indice >= 0) {
      destino[this.indice] = mistura(this.inicial, this.alvo, t);
    } else {
      this.obj[this.campo] = mistura(this.inicial, this.alvo, t);
    }
  }

  /** Avança; devolve o tempo que sobrou (>= 0) quando termina, ou -1. */
  passo(dt) {
    if (this.terminou) return dt;
    this.decorrido += dt;
    if (this.decorrido < this.atraso) return -1;
    if (this.lerInicial) {
      const v = this.ler();
      this.inicial = Array.isArray(v) ? v.slice() : v;
      this.lerInicial = false;
    }
    const tempo = this.decorrido - this.atraso;
    if (tempo < this.duracao) {
      this.escrever(curva(this.trans, this.ease, tempo / this.duracao));
      return -1;
    }
    this.escrever(1);
    this.terminou = true;
    return tempo - this.duracao;
  }
}

class Intervalo {
  constructor(duracao) { this.duracao = duracao; }
  comecar() { this.decorrido = 0; this.terminou = false; }
  passo(dt) {
    if (this.terminou) return dt;
    this.decorrido += dt;
    if (this.decorrido < this.duracao) return -1;
    this.terminou = true;
    return this.decorrido - this.duracao;
  }
}

class Chamada {
  constructor(fn) { this.fn = fn; }
  comecar() { this.terminou = false; }
  passo(dt) {
    if (!this.terminou) { this.terminou = true; this.fn(); }
    return dt;
  }
}

class Tween {
  constructor(motor, dono) {
    this.motor = motor;
    this.dono = dono || null;
    this.etapas = [];
    this.etapa = -1;
    this.paraleloPadrao = false;
    this.paralelo = false;
    this.trans = T.LINEAR;
    this.ease = E.IN_OUT;
    this.voltas = 1;
    this.voltasFeitas = 0;
    this.atual = 0;
    this.comecou = false;
    this.morto = false;
    this.esperando = [];
    this.aoTerminar = null;
  }

  definirParalelo(p = true) { this.paraleloPadrao = p; this.paralelo = p; return this; }
  junto() { this.paralelo = true; return this; }
  encadear() { this.paralelo = false; return this; }
  transicao(t) { this.trans = t; return this; }
  suavizar(e) { this.ease = e; return this; }
  repetir(n = 0) { this.voltas = n; return this; }

  anexar(item) {
    if (this.paralelo) this.etapa = Math.max(this.etapa, 0);
    else this.etapa++;
    this.paralelo = this.paraleloPadrao;
    if (!this.etapas[this.etapa]) this.etapas[this.etapa] = [];
    this.etapas[this.etapa].push(item);
    return item;
  }

  prop(obj, chave, alvo, duracao) {
    return this.anexar(new Interpolador(obj, chave, alvo, duracao, this.trans, this.ease));
  }

  intervalo(duracao) { return this.anexar(new Intervalo(duracao)); }
  chamar(fn) { return this.anexar(new Chamada(fn)); }
  matar() { this.morto = true; }

  comecarEtapa() {
    const etapa = this.etapas[this.atual];
    for (let i = 0; i < etapa.length; i++) etapa[i].comecar();
  }

  passo(dt) {
    if (this.morto) return;
    if (this.dono && this.dono.liberado) { this.morto = true; return; }
    if (!this.etapas.length) { this.terminar(); return; }
    if (!this.comecou) { this.comecou = true; this.atual = 0; this.comecarEtapa(); }
    let resto = dt;
    while (resto > 0 && !this.morto) {
      const etapa = this.etapas[this.atual];
      let ativa = false;
      let menor = resto;
      for (let i = 0; i < etapa.length; i++) {
        const sobra = etapa[i].passo(resto);
        if (sobra < 0) { ativa = true; menor = 0; } else if (sobra < menor) menor = sobra;
      }
      resto = menor;
      if (!ativa) {
        this.atual++;
        if (this.atual >= this.etapas.length) {
          this.voltasFeitas++;
          if (this.voltas > 0 && this.voltasFeitas >= this.voltas) { this.terminar(); return; }
          this.atual = 0;
          // volta sem tempo nenhum (tudo de duração zero): segura até o próximo quadro
          if (resto <= 0) { this.comecarEtapa(); return; }
        }
        this.comecarEtapa();
      }
    }
  }

  terminar() {
    this.morto = true;
    if (this.aoTerminar) this.aoTerminar();
    const lista = this.esperando;
    for (let i = 0; i < lista.length; i++) this.motor.retomar(lista[i]);
    lista.length = 0;
  }
}

/* ----------------------------------------------------------------------
   O MOTOR: corrotinas (geradores), timers e tweens na ordem do Godot 3.

   Num gerador:  yield 0.3      espera um timer de 0,3 s (create_timer)
                 yield QUADRO   espera o próximo quadro (idle_frame)
                 yield tween    espera o tween acabar ("finished")
                 yield* f()     chama outra corrotina e espera por ela
   motor.correr(f()) é chamar sem esperar: roda até o primeiro yield.
   ---------------------------------------------------------------------- */
const QUADRO = { quadro: true };

class Motor {
  constructor() {
    this.timers = [];
    this.quadros = [];
    this.quadrosReserva = [];
    this.disparados = [];
    this.tweens = [];
  }

  limpar() {
    this.timers.length = 0;
    this.quadros.length = 0;
    this.disparados.length = 0;
    this.tweens.length = 0;
  }

  tween(dono) {
    const tw = new Tween(this, dono);
    this.tweens.push(tw);
    return tw;
  }

  correr(gen) { this.retomar(gen); }

  retomar(gen) {
    const r = gen.next();
    if (r.done) return;
    const v = r.value;
    if (typeof v === "number") this.timers.push({ gen, resta: v });
    else if (v instanceof Tween && !v.morto) v.esperando.push(gen);
    else this.quadros.push(gen);
  }

  /** O sinal "idle_frame": quem esperava um quadro volta antes de tudo. */
  passoQuadros() {
    if (!this.quadros.length) return;
    const lista = this.quadros;
    this.quadros = this.quadrosReserva;
    this.quadrosReserva = lista;
    for (let i = 0; i < lista.length; i++) this.retomar(lista[i]);
    lista.length = 0;
  }

  /** Os timers da árvore: os criados enquanto eles disparam ficam para o próximo quadro. */
  passoTimers(dt) {
    const timers = this.timers;
    const n = timers.length;
    if (!n) return;
    const disparados = this.disparados;
    let w = 0;
    for (let i = 0; i < n; i++) {
      const t = timers[i];
      t.resta -= dt;
      if (t.resta <= 0) disparados.push(t.gen);
      else timers[w++] = t;
    }
    for (let i = n; i < timers.length; i++) timers[w++] = timers[i];
    timers.length = w;
    for (let i = 0; i < disparados.length; i++) this.retomar(disparados[i]);
    disparados.length = 0;
  }

  /** Os tweens, na ordem em que nasceram (o último a escrever vence). */
  passoTweens(dt) {
    const lista = this.tweens;
    const n = lista.length;
    let w = 0;
    for (let i = 0; i < n; i++) {
      const tw = lista[i];
      tw.passo(dt);
      if (!tw.morto) lista[w++] = tw;
    }
    for (let i = n; i < lista.length; i++) lista[w++] = lista[i];
    lista.length = w;
  }
}

/* ----------------------------------------------------------------------
   LETRAS COM CONTORNO E SOMBRA DO GODOT 3

   O Label do Godot 3 com fonte de contorno (FontDrawer) desenha, para
   cada letra, primeiro o CONTORNO -- inclusive na posição da sombra -- e
   só no fim os miolos: o da sombra (cor da sombra) e o da letra. É isso
   que dá o "degrau" escuro dos avisos do jogo. Só se desenha numa tela
   pronta (nunca a cada quadro).
   ---------------------------------------------------------------------- */
let emojisImg = null;
let fontesProntas = false;

function estiloTexto(fonte, tamanho, cor, contorno, opcoes = {}) {
  return {
    fonte, tamanho, cor,
    contorno: Math.ceil(Math.max(0, contorno) * 0.5),   // Compat.contorno: o raio é a metade
    corContorno: opcoes.corContorno || COR_CONTORNO_PAINEL,
    sombra: opcoes.sombra || null,
    sombraX: opcoes.sombraX || 0,
    sombraY: opcoes.sombraY || 0,
    alinhar: opcoes.alinhar || "centro",
  };
}

// _aplicar_fonte_painel: Bungee, contorno escuro, sombra (0,0,0,0.55) a 3 px
const painel = (tamanho, cor, contorno = 4, alinhar = "centro") =>
  estiloTexto(FONTE_PAINEL, tamanho, cor, contorno, { sombra: [0, 0, 0, 0.55], sombraX: 3, sombraY: 3, alinhar });
// _aplicar_fonte_arcade: Luckiest Guy, contorno 14, sombra (0,0,0,0.70) a 5 px
const arcade = (tamanho, cor) =>
  estiloTexto(FONTE_ARCADE, tamanho, cor, 14, { sombra: [0, 0, 0, 0.70], sombraX: 5, sombraY: 5 });
// _criar_label: a fonte padrão do tema, contorno (0.03, 0.04, 0.08), sem sombra
const padrao = (tamanho, cor, contorno = 5, alinhar = "centro") =>
  estiloTexto(FONTE_PADRAO, tamanho, cor, contorno, { corContorno: COR_CONTORNO_LABEL, alinhar });

function partesDaLinha(linha) {
  const partes = [];
  let texto = "";
  for (const ch of linha) {
    if (EMOJI[ch] !== undefined) {
      if (texto) partes.push({ texto });
      texto = "";
      partes.push({ emoji: EMOJI[ch] });
    } else texto += ch;
  }
  if (texto) partes.push({ texto });
  return partes;
}

/**
 * Escreve um Label do Godot no retângulo (x, y, w, h). `mod` é o modulate
 * do Label (multiplica a cor da letra, do contorno e da sombra; o emoji só
 * recebe o alfa, como no Godot 3).
 */
function escrever(g, texto, x, y, w, h, e, mod = null) {
  const S = e.tamanho;
  const met = METRICAS[e.fonte];
  const asc = Math.ceil(met.asc * S);
  const alt = asc + Math.ceil(met.desc * S);
  const linhas = String(texto).split("\n");
  const total = linhas.length * alt + (linhas.length - 1) * ESPACO_ENTRE_LINHAS;
  const topo = y + Math.floor((h - total) / 2);
  const mr = mod ? mod[0] : 1;
  const mg = mod ? mod[1] : 1;
  const mb = mod ? mod[2] : 1;
  const cor = css([e.cor[0] * mr, e.cor[1] * mg, e.cor[2] * mb, e.cor.length > 3 ? e.cor[3] : 1]);
  const corContorno = css([e.corContorno[0] * mr, e.corContorno[1] * mg, e.corContorno[2] * mb]);
  const corSombra = e.sombra ? css([e.sombra[0] * mr, e.sombra[1] * mg, e.sombra[2] * mb, e.sombra[3]]) : null;
  g.save();
  g.font = `${S}px ${RESERVA[e.fonte]}`;
  g.textBaseline = "alphabetic";
  g.textAlign = "left";
  g.lineJoin = "round";
  if ("fontKerning" in g) g.fontKerning = "none";
  const emojiW = S * EMOJI_LARGURA;
  const emojiH = S * EMOJI_ALTURA;
  const linhasProntas = linhas.map((linha, i) => {
    const partes = partesDaLinha(linha);
    let largura = 0;
    for (const p of partes) {
      p.w = p.emoji !== undefined ? emojiW : g.measureText(p.texto).width;
      largura += p.w;
    }
    const x0 = e.alinhar === "centro" ? x + Math.floor((w - largura) / 2) : x;
    return { partes, x0, base: topo + i * (alt + ESPACO_ENTRE_LINHAS) + asc };
  });
  const passar = (dx, dy, faz) => {
    for (const l of linhasProntas) {
      let px = l.x0;
      for (const p of l.partes) {
        faz(p, px + dx, l.base + dy);
        px += p.w;
      }
    }
  };
  if (e.contorno > 0) {
    g.lineWidth = e.contorno * 2;
    g.strokeStyle = corContorno;
    if (corSombra) passar(e.sombraX, e.sombraY, (p, px, py) => { if (p.texto) g.strokeText(p.texto, px, py); });
    passar(0, 0, (p, px, py) => { if (p.texto) g.strokeText(p.texto, px, py); });
  }
  const emoji = (p, px, py, alfa) => {
    if (!emojisImg) return;
    g.globalAlpha = alfa;
    g.drawImage(emojisImg, p.emoji * EMOJI_CEL_W, 0, EMOJI_CEL_W, EMOJI_CEL_H, px, py - S * EMOJI_TOPO, emojiW, emojiH);
    g.globalAlpha = 1;
  };
  if (corSombra) {
    g.fillStyle = corSombra;
    passar(e.sombraX, e.sombraY, (p, px, py) => {
      if (p.texto) g.fillText(p.texto, px, py);
      else emoji(p, px, py, e.sombra[3]);
    });
  }
  g.fillStyle = cor;
  passar(0, 0, (p, px, py) => {
    if (p.texto) g.fillText(p.texto, px, py);
    else emoji(p, px, py, 1);
  });
  g.restore();
}

/* ----------------------------------------------------------------------
   CAIXAS (o StyleBoxFlat do Godot 3)

   A borda fica por dentro do retângulo e o fundo só no miolo; a sombra é
   cheia por baixo da caixa e esmaece em linha reta até `tamSombra` px.
   ---------------------------------------------------------------------- */
function caminhoArredondado(g, x, y, w, h, r) {
  const raios = Array.isArray(r) ? r : [r, r, r, r];   // sup. esq., sup. dir., inf. dir., inf. esq.
  const m = Math.min(w, h) / 2;
  const [a, b, c, d] = raios.map((v) => Math.max(0, Math.min(v, m)));
  g.moveTo(x + a, y);
  g.lineTo(x + w - b, y);
  if (b) g.arcTo(x + w, y, x + w, y + b, b); else g.lineTo(x + w, y);
  g.lineTo(x + w, y + h - c);
  if (c) g.arcTo(x + w, y + h, x + w - c, y + h, c); else g.lineTo(x + w, y + h);
  g.lineTo(x + d, y + h);
  if (d) g.arcTo(x, y + h, x, y + h - d, d); else g.lineTo(x, y + h);
  g.lineTo(x, y + a);
  if (a) g.arcTo(x, y, x + a, y, a); else g.lineTo(x, y);
  g.closePath();
}

function caixa(g, x, y, w, h, est) {
  const r = est.raio || 0;
  const bw = est.borda ? est.larguraBorda || 0 : 0;
  const crescer = (v, d) => (Array.isArray(v) ? v.map((q) => Math.max(0, q + d)) : Math.max(0, v + d));
  if (est.sombra && est.tamSombra > 0 && est.sombra[3] > 0) {
    const n = est.tamSombra;
    g.lineWidth = 1;
    for (let i = 0; i < n; i++) {
      const d = i + 0.5;
      g.strokeStyle = css(est.sombra, 1 - d / n);
      g.beginPath();
      caminhoArredondado(g, x - d, y - d, w + 2 * d, h + 2 * d, crescer(r, d));
      g.stroke();
    }
    g.fillStyle = css(est.sombra);
    g.beginPath();
    caminhoArredondado(g, x, y, w, h, r);
    g.fill();
  }
  if (est.bg && (est.bg.length < 4 || est.bg[3] > 0)) {
    g.fillStyle = css(est.bg);
    g.beginPath();
    caminhoArredondado(g, x + bw, y + bw, w - 2 * bw, h - 2 * bw, crescer(r, -bw));
    g.fill();
  }
  if (bw > 0) {
    g.fillStyle = css(est.borda);
    g.beginPath();
    caminhoArredondado(g, x, y, w, h, r);
    caminhoArredondado(g, x + bw, y + bw, w - 2 * bw, h - 2 * bw, crescer(r, -bw));
    g.fill("evenodd");
  }
}

// _estilo_neon: fundo, borda, cantos e a sombra de 18 px
const neon = (bg, borda, raio = 28, espessura = 3) =>
  ({ bg, borda, larguraBorda: espessura, raio, sombra: SOMBRA_PAINEL, tamSombra: 18 });

function retangulo(g, x, y, w, h, c) {
  g.fillStyle = css(c);
  g.fillRect(x, y, w, h);
}

function brilhoTopo(g, largPai, cor, ox = 14, oy = 10, menos = 28, alt = 28, raio = 20) {
  caixa(g, ox, oy, largPai - menos, alt, { bg: cor, raio });
}

function linhaDecorativa(g, largPai, y, cor, margem = 22, espessura = 2) {
  retangulo(g, margem, y, largPai - margem * 2, espessura, cor);
}

/* Um pedaço da HUD pronto numa tela fora, na resolução do aparelho. */
function criarCamada(w, h, margem, pintar) {
  return { w, h, margem, pintar, tela: null, g: null, sujo: true, escala: 0 };
}

function prepararCamada(c, escala) {
  if (!c.sujo && c.escala === escala && c.tela) return;
  const rx = SX * escala;
  const ry = SY * escala;
  const W = Math.ceil((c.w + 2 * c.margem) * rx);
  const H = Math.ceil((c.h + 2 * c.margem) * ry);
  if (!c.tela) {
    c.tela = novaTela(W, H);
    c.g = c.tela.getContext("2d");
  } else if (c.tela.width !== W || c.tela.height !== H) {
    c.tela.width = W;
    c.tela.height = H;
  } else {
    c.g.setTransform(1, 0, 0, 1, 0, 0);
    c.g.clearRect(0, 0, W, H);
  }
  c.g.setTransform(rx, 0, 0, ry, c.margem * rx, c.margem * ry);
  c.g.imageSmoothingQuality = "high";
  c.pintar(c.g);
  c.sujo = false;
  c.escala = escala;
  c.fw = W / rx;
  c.fh = H / ry;
}

function desenharCamada(ctx, c, x, y) {
  if (!c.tela) return;
  ctx.drawImage(c.tela, x - c.margem, y - c.margem, c.fw, c.fh);
}

/* As fontes: pedidas uma vez, para o arquivo todo. */
let fontesPedidas = null;
function carregarFontes() {
  if (fontesPedidas) return fontesPedidas;
  if (typeof FontFace === "undefined" || !document.fonts) {
    fontesPedidas = Promise.resolve();
    return fontesPedidas;
  }
  fontesPedidas = Promise.all(ARQUIVOS_DE_FONTE.map(([nome, arquivo]) => {
    const fonte = new FontFace(nome, `url("${new URL(arquivo, PASTA).href}")`);
    return fonte.load().then((f) => { document.fonts.add(f); }).catch(() => {});
  })).then(() => { fontesProntas = true; });
  return fontesPedidas;
}

/* ======================================================================
   O JOGO
   ====================================================================== */
export default {
  largura: LARGURA,
  altura: ALTURA,
  artes: {
    pista: "boliche/dragon/pista_hd.webp",
    mascara: "boliche/dragon/pista_mascara.webp",
    pino: "boliche/dragon/pino_em_pe.webp",
    bola: "boliche/dragon/bola_rolando.webp",
    logo: "boliche/dragon/logo_lazer_sport.webp",
    emojis: "boliche/dragon/emojis.webp",
  },

  criar(api) {
    const img = api.img;
    emojisImg = img.emojis || null;
    const motor = new Motor();
    const som = (nome) => api.som(nome);
    let destruido = false;

    /* ------------------------------------------------------------------
       O ESTADO DA PARTIDA (as variáveis do game.gd)
       ------------------------------------------------------------------ */
    let roundAtual = 1;
    let tentativaAtual = 1;
    let pinosDerrubadosNoRound = 0;
    let pinosAntesDaJogada = 10;
    let jogoFinalizado = false;
    let historicoRounds = [];
    let contadorStrikesNoJogo = 0;
    let processandoImpacto = false;
    let aguardandoFimBola = false;
    let introEmAndamento = true;
    let aceitandoInput = false;
    let jogandoTrajeto = false;
    let transicaoRoundEmAndamento = false;
    let ultimaTeclaJogada = "";
    let teclaAnteriorNoRound = "";
    let bloquearSparePosC = false;
    let bloquearSparePosLateralC = false;
    let lateralAnteriorParaC = "";
    let jogadaPendente = "";
    let jogadaPendenteEm = 0;
    let jogadaPendenteRound = -1;
    let ultimaJogadaEm = -100;
    let telaFinalAtiva = false;
    let finalIntroEmAndamento = false;
    let tempoRestanteTelaFinal = 0;
    let segundosMostrados = -1;
    let animTelaFinalT = 0;
    let hudSujo = true;
    let tempoHudAcc = 0;
    let relogio = 0;                  // tempo de jogo (s): o Time.get_ticks_msec das regras
    let introPendente = false;

    /* ------------------------------------------------------------------
       A CÂMERA (Camera2D no centro, zoom 1; o Godot 3 aproxima com zoom < 1)
       ------------------------------------------------------------------ */
    const CAMERA_BASE = [TELA_W * 0.5, TELA_H * 0.5];
    const camera = { pos: CAMERA_BASE.slice(), offset: [0, 0], zoom: [1, 1] };
    const CAMERA_ZOOM_JOGADA = 0.972;
    const CAMERA_FOCO_JOGADA = [0, -18];

    /* ------------------------------------------------------------------
       O BRILHO DA PISTA

       O shader soma à pista: (1) a luz das canaletas, m.r x pulso que corre
       pela pista (fract(UV.y * 1,5 - fase)), em ciano; (2) o dourado, m.g x
       (0,70 + 0,30 sen(fase + 12v + 5u)) x (0,55 + 0,45 sen(fase + 18u)).
       Aqui cada fator é uma faixa pronta deslizada pela fase, multiplicada
       pela máscara numa tela pequena; a soma entra na pista de uma vez. No
       PRA FORA a luz fica vermelha e a madeira perto das canaletas escurece
       (erro_forca); no STRIKE as canaletas aceleram.
       ------------------------------------------------------------------ */
    const brilho = {
      t: 0, velocidade: BRILHO_VELOCIDADE, intensidade: BRILHO_INTENSIDADE, erro: 0, ativo: false,
      fSobe: 0, fPulso: 0, fOuro: 0,
    };
    const PERIODO_FAIXA = MASCARA_H / 1.5;
    const PERIODO_P = MASCARA_H * TAU / 12;
    const PERIODO_Q = MASCARA_W * TAU / 18;
    let telas = null;

    function prepararBrilho() {
      if (!img.mascara) return null;
      const mascara = novaTela(MASCARA_W, MASCARA_H);
      const gm = mascara.getContext("2d");
      gm.drawImage(img.mascara, 0, 0, MASCARA_W, MASCARA_H);
      let dados;
      try { dados = gm.getImageData(0, 0, MASCARA_W, MASCARA_H).data; } catch (erro) { return null; }
      const nova = (w, h, pintar) => {
        const c = novaTela(w, h);
        const g = c.getContext("2d");
        const im = g.createImageData(c.width, c.height);
        pintar(im.data, c.width, c.height);
        g.putImageData(im, 0, 0);
        return c;
      };
      const daMascara = (fn) => nova(MASCARA_W, MASCARA_H, (d) => {
        for (let i = 0; i < d.length; i += 4) {
          const r = dados[i] / 255;
          const gg = dados[i + 1] / 255;
          const cor = fn(r, gg);
          d[i] = cor[0] * 255; d[i + 1] = cor[1] * 255; d[i + 2] = cor[2] * 255; d[i + 3] = 255;
        }
      });
      const pulso = (l) => {
        const s1 = lim(l / 0.18, 0, 1);
        const sobe = s1 * s1 * (3 - 2 * s1);
        const s2 = lim((l - 0.18) / (0.55 - 0.18), 0, 1);
        return sobe * (1 - s2 * s2 * (3 - 2 * s2));
      };
      const cinza = (d, i, v) => { d[i] = d[i + 1] = d[i + 2] = lim(v, 0, 1) * 255; d[i + 3] = 255; };
      const faixa = (extra) => nova(MASCARA_W, MASCARA_H + PERIODO_FAIXA, (d, w, h) => {
        for (let y = 0; y < h; y++) {
          const v = Math.min(1, pulso(posmod(1.5 * y / MASCARA_H, 1)) + extra);
          for (let x = 0; x < w; x++) cinza(d, (y * w + x) * 4, v);
        }
      });
      const t = {
        ciano: daMascara((r) => [0, 0.95 * BRILHO_INTENSIDADE * r, BRILHO_INTENSIDADE * r]),
        vermelho: daMascara((r) => [r, 0, 0]),
        ouro: daMascara((r, gg) => [gg, 0.88 * gg, 0.30 * gg]),
        escurecer: daMascara((r) => [1, 1 - 0.65 * r, 1 - 0.85 * r]),
        faixa: faixa(0),
        // luz_erro = vermelho x m.r x (2,2 x 0,75 x pulso + 0,10) = 1,65 x m.r x (pulso + 0,06)
        faixaErro: faixa(0.10 / 1.65),
        ondaP: nova(MASCARA_W, MASCARA_H + PERIODO_P, (d, w, h) => {
          for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) cinza(d, (y * w + x) * 4, 0.70 + 0.30 * Math.sin(12 * y / MASCARA_H + 5 * x / MASCARA_W));
          }
        }),
        ondaQ: nova(MASCARA_W + PERIODO_Q, 1, (d, w) => {
          for (let x = 0; x < w; x++) cinza(d, x * 4, 0.55 + 0.45 * Math.sin(18 * x / MASCARA_W));
        }),
        a: novaTela(MASCARA_W, MASCARA_H),
        b: novaTela(MASCARA_W, MASCARA_H),
        c: novaTela(MASCARA_W, MASCARA_H),
      };
      t.ga = t.a.getContext("2d");
      t.gb = t.b.getContext("2d");
      t.gc = t.c.getContext("2d");
      // Onde a máscara é preta o shader não soma nada: o brilho só é
      // desenhado nos trechos (faixas de 8 px da máscara) que têm luz. No
      // canvas sem placa de vídeo isso corta mais da metade do trabalho.
      const TRECHO = 8;
      const LIMIAR = 8;
      const trechos = [];
      for (let ty = 0; ty < MASCARA_H; ty += TRECHO) {
        let inicio = -1;
        for (let tx = 0; tx <= MASCARA_W; tx += TRECHO) {
          let tem = false;
          if (tx < MASCARA_W) {
            for (let y = ty; y < ty + TRECHO && !tem; y++) {
              for (let x = tx; x < tx + TRECHO; x++) {
                const i = (y * MASCARA_W + x) * 4;
                if (dados[i] + dados[i + 1] > LIMIAR) { tem = true; break; }
              }
            }
          }
          if (tem && inicio < 0) inicio = tx;
          else if (!tem && inicio >= 0) {
            trechos.push(inicio, ty, tx - inicio, TRECHO);
            inicio = -1;
          }
        }
      }
      t.trechos = new Float32Array(trechos);
      return t;
    }

    // soma (ou multiplica) uma tela do tamanho da máscara na pista, só nos trechos com luz
    function aplicarNaPista(ctx, tela) {
      const tr = telas.trechos;
      const kx = PISTA.w / MASCARA_W;
      const ky = PISTA.h / MASCARA_H;
      for (let i = 0; i < tr.length; i += 4) {
        ctx.drawImage(tela, tr[i], tr[i + 1], tr[i + 2], tr[i + 3],
          PISTA.x + tr[i] * kx, PISTA.y + tr[i + 1] * ky, tr[i + 2] * kx, tr[i + 3] * ky);
      }
    }

    function avancarBrilho(dt) {
      brilho.t = posmod(brilho.t + dt * brilho.velocidade, 3600);
      brilho.fSobe = posmod(brilho.t * 0.28, 1);
      brilho.fPulso = posmod(brilho.t * 1.8, TAU);
      brilho.fOuro = posmod(brilho.t * 2.6, TAU);
    }

    // _efeito_canaleta_erro: vermelho por 2,2 s e volta em 18 passos de 0,04 s
    function* efeitoCanaletaErro(duracao = 2.2) {
      if (brilho.ativo) return;
      brilho.ativo = true;
      brilho.erro = 1;
      brilho.velocidade = BRILHO_VELOCIDADE * 2.2;
      brilho.intensidade = Math.max(BRILHO_INTENSIDADE, 0.75);
      yield duracao;
      const passos = 18;
      for (let i = 0; i < passos; i++) {
        const t = (i + 1) / passos;
        brilho.erro = mistura(1, 0, t);
        brilho.velocidade = mistura(BRILHO_VELOCIDADE * 2.2, BRILHO_VELOCIDADE, t);
        yield 0.04;
      }
      brilho.erro = 0;
      brilho.velocidade = BRILHO_VELOCIDADE;
      brilho.intensidade = BRILHO_INTENSIDADE;
      brilho.ativo = false;
    }

    // _efeito_canaleta_strike: as canaletas aceleram 3,5x por 2 s e desaceleram
    function* efeitoCanaletaStrike(duracao = 2.0) {
      if (brilho.ativo) return;
      brilho.ativo = true;
      brilho.erro = 0;
      brilho.velocidade = BRILHO_VELOCIDADE * 3.5;
      yield duracao;
      const passos = 15;
      for (let i = 0; i < passos; i++) {
        brilho.velocidade = mistura(BRILHO_VELOCIDADE * 3.5, BRILHO_VELOCIDADE, (i + 1) / passos);
        yield 0.05;
      }
      brilho.velocidade = BRILHO_VELOCIDADE;
      brilho.ativo = false;
    }

    /* ------------------------------------------------------------------
       OS PINOS (pino.gd)
       ------------------------------------------------------------------ */
    let pins = [];
    let pinsPorZ = [];

    function novoPino(numero) {
      const [cx, cy, fator, z] = RACK[numero];
      const x = RACK_CENTRO_X + cx * RACK_ESP_X;
      const y = RACK_BASE_Y + cy * RACK_ESP_Y;
      const p = {
        numero, z, fator,
        pos: [x, y], base: [x, y], introBase: null, mod: [1, 1, 1, 1],
        sprPos: [0, 0], sprRot: 0, sprEscala: [1, 1], sprMod: [1, 1, 1, 1],
        rotPos: [0, 0], rotMod: [1, 1, 1, 1], rotEscala: [1, 1], rotVisivel: true,
        derrubado: false, empurrando: false, vel: [0, 0], velRot: 0, forca: [0, 0], origem: [0, 0],
        emQuaseQueda: false, finalizandoQueda: false, sumindo: false, animacao: "idle",
        travarEscala: false, escalaTravada: null, liberado: false,
      };
      atualizarTamanhoBase(p);
      return p;
    }

    // atualizar_tamanho_base + ajustar_ancora_visual: o quadro "idle" no
    // tamanho 76 x 144 (vezes a profundidade), apoiado na linha de base.
    function atualizarTamanhoBase(p) {
      if (p.derrubado) { fixarTamanhoVisualDerrubado(p); return; }
      const ef = Math.min(PINO.larguraVisual / REF_IDLE_W, PINO.alturaVisual / REF_IDLE_H) * p.fator;
      p.sprEscala[0] = ef;
      p.sprEscala[1] = ef;
      ajustarAncora(p, ef);
    }

    function ajustarAncora(p, escalaY) {
      p.sprPos[0] = 0;
      p.sprPos[1] = PINO.linhaBase - REF_IDLE_H * escalaY;
      p.rotPos[0] = p.sprPos[0] - ROTULO_PINO_W * 0.5;
      p.rotPos[1] = p.sprPos[1] + REF_IDLE_H * escalaY * 0.12;
    }

    function fixarTamanhoVisualDerrubado(p) {
      const e = p.escalaTravada || p.sprEscala;
      p.sprEscala[0] = e[0];
      p.sprEscala[1] = e[1];
      ajustarAncora(p, e[1]);
    }

    function areaColisao(p) {
      let w = PINO.larguraColisao * p.fator;
      let h = PINO.alturaColisao * p.fator;
      if (p.numero === 1) { w *= 1.06; h *= 1.08; }
      else if (p.numero === 2 || p.numero === 3) { w *= 1.03; h *= 1.04; }
      else if (p.numero === 7 || p.numero === 10) w *= 0.98;
      return [w, h];
    }

    function receberForca(p, fx, fy, magnitude, ox, oy) {
      if (p.derrubado) return;
      let len = Math.hypot(fx, fy);
      let dx;
      let dy;
      if (len <= 0.001) {
        dx = p.pos[0] - ox; dy = p.pos[1] - oy; len = Math.hypot(dx, dy) || 1;
        dx /= len; dy /= len;
      } else { dx = fx / len; dy = fy / len; }
      p.origem[0] = ox;
      p.origem[1] = oy;
      let peso = 1;
      if (p.numero === 1) peso = 0.92;
      else if (p.numero === 2 || p.numero === 3) peso = 0.95;
      else if (p.numero === 7 || p.numero === 10) peso = 1.03;
      const ganho = magnitude / peso;
      p.forca[0] += dx * ganho;
      p.forca[1] += dy * ganho;
      p.vel[0] += dx * 1.05 * ganho * PINO.ganhoDeslocamento;
      p.vel[1] += -Math.abs(dy) * 0.62 * ganho * PINO.ganhoDeslocamento;
      p.velRot += dx * ganho * PINO.ganhoRotacao;
      p.empurrando = true;
      const total = Math.hypot(p.forca[0], p.forca[1]);
      let limiar = PINO.limiarQueda;
      if (p.numero >= 7) limiar *= 0.70;
      else if (p.numero >= 4) limiar *= 0.82;
      if (total >= limiar) {
        let lado = p.forca[0] >= 0 ? "down_rt" : "down_left";
        if (Math.abs(p.forca[0]) < 0.05) lado = "strike";
        motor.correr(cairVoando(p, lado, lim(total, 0.98, 1.72), ox, oy));
        p.forca[0] = p.forca[1] = 0;
      } else if (total >= PINO.limiarQuaseQueda * 0.85) {
        if (!p.emQuaseQueda && !p.finalizandoQueda) oscilar(p, dx, total);
      }
    }

    function simularEmpurrao(p, dt) {
      if (p.derrubado || !p.empurrando) return;
      p.pos[0] += p.vel[0] * dt;
      p.pos[1] += p.vel[1] * dt;
      const atrito = Math.pow(PINO.atritoPlano, dt * 60);
      p.vel[0] *= atrito;
      p.vel[1] *= atrito;
      p.sprRot += p.velRot * dt;
      p.velRot *= Math.pow(PINO.atritoRotacional, dt * 60);
      const desloc = dist(p.pos[0], p.pos[1], p.base[0], p.base[1]);
      const forca = Math.hypot(p.forca[0], p.forca[1]);
      if (desloc >= PINO.deslocamentoMaxSemCair || forca >= PINO.limiarColisaoEmCadeia) {
        let lado = p.vel[0] >= 0 ? "down_rt" : "down_left";
        if (Math.abs(p.vel[0]) < 1.2) lado = "strike";
        motor.correr(cairVoando(p, lado, lim(Math.max(forca, 0.98), 0.98, 1.60), p.origem[0], p.origem[1]));
        p.forca[0] = p.forca[1] = 0;
        return;
      }
      if (Math.hypot(p.vel[0], p.vel[1]) < PINO.limiarDeslocamento && Math.abs(p.velRot) < 1) {
        p.empurrando = false;
        p.vel[0] = p.vel[1] = 0;
        p.velRot = 0;
        const tw = motor.tween(p).transicao(T.SINE).suavizar(E.OUT);
        tw.prop(p, "pos", p.base, 0.08);
        tw.junto().prop(p, "sprRot", 0, 0.08);
      }
    }

    // _oscilar: o "quase caiu" (só visual)
    function oscilar(p, dirX, magnitude) {
      if (p.derrubado) return;
      p.emQuaseQueda = true;
      let lado = dirX;
      if (Math.abs(lado) < 0.05) lado = Math.random() > 0.5 ? 1 : -1;
      const f = inverso(0.65, 1.15, lim(magnitude, 0.65, 1.15));
      const ampRot = mistura(8, 18, f) * sinal(lado);
      const ampX = mistura(3, 7, f) * sinal(lado);
      const base = p.sprPos.slice();
      const rot = p.sprRot;
      const tw = motor.tween(p).transicao(T.SINE).suavizar(E.IN_OUT);
      tw.prop(p, "sprRot", rot + ampRot, 0.055);
      tw.junto().prop(p, "sprPos", [base[0] + ampX, base[1] - Math.abs(ampX) * 0.25], 0.055);
      tw.prop(p, "sprRot", rot - ampRot * 0.82, 0.095);
      tw.junto().prop(p, "sprPos", [base[0] - ampX * 0.72, base[1]], 0.095);
      tw.prop(p, "sprRot", rot + ampRot * 0.26, 0.055);
      tw.junto().prop(p, "sprPos", [base[0] + ampX * 0.20, base[1]], 0.055);
      tw.prop(p, "sprRot", rot, 0.070);
      tw.junto().prop(p, "sprPos", base, 0.070);
      tw.aoTerminar = () => { p.emQuaseQueda = false; p.forca[0] = p.forca[1] = 0; };
    }

    /*
     * cair_voando: o pino é empurrado, tomba girando, quica no chão e some.
     * O atraso simula a onda do impacto chegando (no jogo ele é esperado
     * duas vezes: o pino fica parado o dobro do pedido).
     */
    function* cairVoando(p, animacao, intensidade, ox, oy, atraso = 0) {
      if (p.derrubado) return;
      if (atraso > 0.001) {
        yield atraso;
        if (p.derrubado || p.liberado) return;
        yield atraso;
        if (p.derrubado || p.liberado) return;
      }
      p.derrubado = true;
      p.sumindo = false;
      p.finalizandoQueda = false;
      p.emQuaseQueda = false;
      p.empurrando = false;
      p.forca[0] = p.forca[1] = 0;
      p.vel[0] = p.vel[1] = 0;
      p.velRot = 0;

      // o número some em 0,05 s
      p.rotMod[3] = 1;
      p.rotVisivel = true;
      const twNum = motor.tween(p);
      twNum.prop(p, "rotMod", [1, 1, 1, 0], 0.05);
      twNum.aoTerminar = () => { p.rotVisivel = false; };

      const tipo = animacao === "down_left" || animacao === "down_rt" ? animacao : "strike";
      p.animacao = tipo;
      p.travarEscala = true;
      p.escalaTravada = p.sprEscala.slice();
      fixarTamanhoVisualDerrubado(p);

      // o clarão do contato
      const twFlash = motor.tween(p).definirParalelo(true);
      twFlash.prop(p, "sprMod", [1.55, 1.45, 1.30, 1], 0.020);
      twFlash.encadear().prop(p, "sprMod", [1, 1, 1, 1], 0.052);

      let dx = p.pos[0] - ox;
      let dy = p.pos[1] - oy;
      let len = Math.hypot(dx, dy);
      if (len < 0.5) { dx = Math.random() > 0.5 ? 1 : -1; dy = -0.06; len = Math.hypot(dx, dy); }
      dx /= len;
      dy /= len;

      const forca = lim(intensidade, 0.90, 1.28);
      const tf = inverso(0.90, 1.65, forca);
      const lateralBase = mistura(12, PINO.empurraoMaxX * 1.12, tf);
      const frenteBase = mistura(9, PINO.empurraoMaxY * 1.18, tf);
      const vooBase = mistura(20, PINO.distanciaVooMax * 1.12, tf);
      const empurraoX = dx * lateralBase;
      const empurraoY = -mistura(2.5, 8, tf);
      let deslizX = dx * vooBase;
      const deslizY = frenteBase;
      if (tipo === "down_left") deslizX = -Math.abs(deslizX);
      else if (tipo === "down_rt") deslizX = Math.abs(deslizX);
      let ladoRot = sinal(deslizX);
      if (ladoRot === 0) ladoRot = dx !== 0 ? sinal(dx) : 1;
      if (tipo === "down_left") ladoRot = -1;
      else if (tipo === "down_rt") ladoRot = 1;
      const rotPico = ladoRot * mistura(20, 40, tf);
      const rotFinal = ladoRot * mistura(90, PINO.rotacaoMaxQueda, tf) + aleatorio(-14, 14);
      const squashX = mistura(1.10, 1.18, tf);
      const squashY = mistura(0.90, 0.82, tf);
      const base = p.pos.slice();
      const baseMod = p.sprMod.slice();
      const e0 = p.escalaTravada;

      const tw = motor.tween(p).transicao(T.CUBIC).suavizar(E.OUT);
      tw.junto().prop(p, "sprEscala", [e0[0] * squashX, e0[1] * squashY], 0.032);
      // fase 1: o empurrão
      tw.prop(p, "pos", [base[0] + empurraoX, base[1] + empurraoY], PINO.duracaoEmpurrao);
      tw.junto().prop(p, "sprRot", rotPico, PINO.duracaoEmpurrao);
      tw.junto().intervalo(PINO.duracaoEmpurrao);
      tw.junto().prop(p, "sprMod", [1.08, 1.06, 1.04, 1], PINO.duracaoEmpurrao);
      tw.junto().prop(p, "sprEscala", e0, PINO.duracaoEmpurrao + 0.035);
      // fase 2: o tombo
      tw.transicao(T.QUART);
      tw.prop(p, "pos", [base[0] + deslizX, base[1] + deslizY], PINO.duracaoTombo);
      tw.junto().prop(p, "sprRot", rotFinal, PINO.duracaoTombo);
      tw.junto().intervalo(PINO.duracaoTombo);
      tw.junto().prop(p, "sprMod", baseMod, PINO.duracaoTombo);
      tw.aoTerminar = () => {
        if (p.liberado) return;
        fixarTamanhoVisualDerrubado(p);
        quiqueNoTatame(p, forca);
      };
    }

    // _aplicar_quique_no_tatame: o pino deitado quica e assenta
    function quiqueNoTatame(p, forca) {
      if (p.finalizandoQueda) return;
      p.finalizandoQueda = true;
      const rot = p.sprRot;
      const base = p.pos.slice();
      const intensidade = lim(forca * PINO.intensidadeQuique, 0.90, 1.55);
      let lado = 1;
      if (p.animacao === "down_left") lado = -1;
      else if (p.animacao !== "down_rt") lado = Math.random() < 0.5 ? -1 : 1;
      const qy = PINO.quiqueY * intensidade;
      const qx = PINO.quiqueX * intensidade * lado;
      const qr = PINO.rotacaoQuique * intensidade * lado;
      const e = p.escalaTravada;
      const tw = motor.tween(p).transicao(T.CUBIC).suavizar(E.OUT);
      tw.junto().prop(p, "sprEscala", [e[0] * 1.15, e[1] * 0.86], 0.030);
      tw.prop(p, "pos", [base[0] + qx, base[1] - qy * 0.38], 0.042);
      tw.junto().prop(p, "sprRot", rot + qr, 0.042);
      tw.junto().prop(p, "sprEscala", e, 0.055);
      tw.prop(p, "pos", [base[0] + qx * 0.54, base[1] + qy * 0.27], 0.080);
      tw.junto().prop(p, "sprRot", rot - qr * 0.40, 0.080);
      tw.prop(p, "pos", [base[0] + qx * 0.17, base[1] - qy * 0.09], 0.055);
      tw.junto().prop(p, "sprRot", rot + qr * 0.15, 0.055);
      tw.prop(p, "pos", base, 0.088);
      tw.junto().prop(p, "sprRot", rot, 0.088);
      tw.aoTerminar = () => {
        p.finalizandoQueda = false;
        sumirAposQueda(p);
      };
    }

    function sumirAposQueda(p) {
      if (p.sumindo) return;
      p.sumindo = true;
      const tw = motor.tween(p);
      tw.intervalo(PINO.esperaAposQueda);
      tw.prop(p, "sprMod", [1, 1, 1, 0], PINO.fadeAposQueda);
      tw.junto().prop(p, "rotMod", [1, 1, 1, 0], PINO.fadeAposQueda);
    }

    function forcarQuedaImediata(p, animacao, intensidade, ox, oy) {
      if (p.derrubado) return;
      p.emQuaseQueda = false;
      p.finalizandoQueda = false;
      p.empurrando = false;
      p.forca[0] = p.forca[1] = 0;
      p.vel[0] = p.vel[1] = 0;
      p.velRot = 0;
      p.sprRot = 0;
      p.sprMod[0] = p.sprMod[1] = p.sprMod[2] = p.sprMod[3] = 1;
      motor.correr(cairVoando(p, animacao, intensidade, ox, oy, 0));
    }

    // impacto_visual: o tranquinho do pino que a bola pegou
    function impactoVisual(p, intensidade, ox) {
      const ganho = lim(intensidade, 0.92, 1.50);
      const k = lim((ganho - 0.9) / 0.6, 0, 1);
      const lado = sinal(p.pos[0] - ox) || 1;
      const base = p.sprPos.slice();
      const baseMod = p.sprMod.slice();
      const tw = motor.tween(p).transicao(T.CUBIC).suavizar(E.OUT);
      tw.prop(p, "sprPos", [base[0] + lado * mistura(1.2, 2.8, k), base[1] - mistura(2.4, 4.6, k)], 0.040);
      tw.junto().prop(p, "sprRot", p.sprRot + lado * mistura(2.0, 4.4, k), 0.045);
      tw.junto().prop(p, "sprMod", [1.14, 1.14, 1.14, 1], 0.040);
      tw.prop(p, "sprPos", base, 0.065);
      tw.junto().prop(p, "sprMod", baseMod, 0.065);
    }

    // destacar_acerto: o número do pino pisca
    function destacarAcerto(p) {
      const escala = p.rotEscala.slice();
      const brilhoRot = p.rotMod.slice();
      const tw = motor.tween(p);
      tw.prop(p, "rotEscala", [escala[0] * 1.12, escala[1] * 1.12], 0.05);
      tw.junto().prop(p, "rotMod", [1.18, 1.18, 0.70, 1], 0.04);
      tw.prop(p, "rotEscala", escala, 0.10);
      tw.junto().prop(p, "rotMod", brilhoRot, 0.10);
    }

    function obterPino(numero) {
      return pins[numero - 1] || null;
    }

    function contarPinosEmPe() {
      let n = 0;
      for (let i = 0; i < pins.length; i++) if (!pins[i].derrubado) n++;
      return n;
    }

    function criar10Pinos() {
      for (const p of pins) p.liberado = true;
      pins = [];
      for (let n = 1; n <= 10; n++) pins.push(novoPino(n));
      // ordem de desenho: z (o 1 na frente) e, no mesmo z, a ordem da árvore
      pinsPorZ = pins.slice().sort((a, b) => a.z - b.z || a.numero - b.numero);
    }

    /* ------------------------------------------------------------------
       A BOLA (bola.gd)
       ------------------------------------------------------------------ */
    const bola = {
      pos: BOLA_INICIO.slice(), visivel: false, mod: [1, 1, 1, 1], rot: 0, z: 300,
      escala: [BOLA.escalaPerto, BOLA.escalaPerto], rolando: false, tempoAnim: 0,
      emMovimento: false, passando: false, tempo: 0, duracao: 1,
      p0: [0, 0], p1: [0, 0], p2: [0, 0], p3: [0, 0], forca: 1, spin: 0, lateral: 0,
      introBase: null,
    };

    function meiaLarguraPista(y) {
      const t = lim(inverso(BOLA_INICIO[1], BOLA.yImpacto, y), 0, 1);
      return mistura(BOLA.meiaBase, BOLA.meiaTopo, t);
    }

    function xNaPista(x, y) {
      const meia = meiaLarguraPista(y);
      return lim(x, BOLA_INICIO[0] - meia, BOLA_INICIO[0] + meia);
    }

    function resetarBola() {
      bola.emMovimento = false;
      bola.passando = false;
      bola.tempo = 0;
      bola.forca = 1;
      bola.spin = 0;
      bola.lateral = 0;
      bola.pos[0] = BOLA_INICIO[0];
      bola.pos[1] = BOLA_INICIO[1];
      bola.visivel = false;
      bola.mod[3] = 1;
      bola.rot = 0;
      bola.escala[0] = bola.escala[1] = BOLA.escalaPerto;
      bola.rolando = false;
    }

    function lancarBola(dirX, forca, spin) {
      if (bola.emMovimento) return;
      bola.emMovimento = true;
      bola.passando = false;
      bola.tempo = 0;
      bola.forca = forca;
      bola.spin = spin;
      bola.lateral = lim(dirX, -0.78, 0.78);
      bola.duracao = lim(mistura(0.82, 0.68, inverso(0.96, 1.14, lim(forca, 0.96, 1.14))), 0.68, 0.82);
      const y0 = BOLA_INICIO[1];
      const y1 = mistura(y0, BOLA.yImpacto, 0.20);
      const y2 = mistura(y0, BOLA.yImpacto, 0.56);
      const y3 = BOLA.yImpacto;
      const l = bola.lateral;
      let a1;
      let a2;
      let a3;
      if (l <= -0.58) { a1 = -0.16; a2 = -0.44; a3 = -0.58; }
      else if (l >= 0.58) { a1 = 0.16; a2 = 0.44; a3 = 0.58; }
      else if (l < -0.12 || l > 0.12) { a1 = l * 0.40; a2 = l * 0.70; a3 = l * 0.84; }
      else { a1 = spin * 0.002; a2 = spin * 0.005; a3 = spin * 0.007; }
      bola.p0[0] = BOLA_INICIO[0]; bola.p0[1] = y0;
      bola.p1[0] = xNaPista(BOLA_INICIO[0] + a1 * meiaLarguraPista(y1), y1); bola.p1[1] = y1;
      bola.p2[0] = xNaPista(BOLA_INICIO[0] + a2 * meiaLarguraPista(y2), y2); bola.p2[1] = y2;
      bola.p3[0] = xNaPista(BOLA_INICIO[0] + a3 * meiaLarguraPista(y3), y3); bola.p3[1] = y3;
      bola.pos[0] = bola.p0[0];
      bola.pos[1] = bola.p0[1];
      bola.visivel = true;
      bola.mod[3] = 1;
      bola.rot = 0;
      bola.escala[0] = bola.escala[1] = BOLA.escalaPerto;
      bola.z = 300;
      bola.rolando = true;
    }

    function processarBola(dt) {
      if (bola.rolando) bola.tempoAnim += dt;
      if (!bola.emMovimento) return;
      bola.tempo += dt;
      const t = lim(bola.tempo / bola.duracao, 0, 1);
      const u = 1 - t;
      const a = u * u * u;
      const b = 3 * u * u * t;
      const c = 3 * u * t * t;
      const d = t * t * t;
      bola.pos[0] = a * bola.p0[0] + b * bola.p1[0] + c * bola.p2[0] + d * bola.p3[0];
      bola.pos[1] = a * bola.p0[1] + b * bola.p1[1] + c * bola.p2[1] + d * bola.p3[1];
      const escala = mistura(BOLA.escalaPerto, BOLA.escalaLonge, t);
      bola.escala[0] = bola.escala[1] = escala;
      bola.mod[3] = mistura(1, BOLA.opacidadeLonge, t);
      bola.rot = mistura(0, bola.lateral * 14, t);
      bola.z = Math.trunc(300 - t * 220);
      if (t >= 1) {
        bola.emMovimento = false;
        motor.correr(aoImpactoNoDeck(bola.pos[0], bola.pos[1], bola.forca, bola.lateral, bola.spin));
      }
    }

    // tocar_passagem_por_cima_dos_pinos: a bola atravessa o rack e some no fosso
    function* passagemPorCima(ax, ay, alvoZ) {
      if (bola.passando) return;
      bola.emMovimento = false;
      bola.passando = true;
      bola.visivel = true;
      const e0 = bola.escala[0];
      const yMeio = mistura(ay, BOLA.yCacapa, 0.45);
      const xMeio = xNaPista(ax + bola.lateral * 10 + bola.spin * 0.4, yMeio);
      const xFim = xNaPista(ax + bola.lateral * BOLA.deslocamentoCacapaX, BOLA.yCacapa);
      bola.z = Math.max(1, alvoZ - 8);
      bola.rolando = true;
      const tw = motor.tween().transicao(T.SINE).suavizar(E.OUT);
      tw.prop(bola, "pos", [xMeio, yMeio], 0.070);
      tw.junto().prop(bola, "mod", [1, 1, 1, 0.92], 0.070);
      tw.junto().prop(bola, "escala", [e0 * 0.84, e0 * 0.84], 0.070);
      tw.prop(bola, "pos", [xFim, BOLA.yCacapa], 0.115);
      tw.junto().prop(bola, "mod", [1, 1, 1, 0.42], 0.115);
      tw.junto().prop(bola, "escala", [e0 * 0.52, e0 * 0.52], 0.115);
      tw.prop(bola, "mod", [1, 1, 1, 0], 0.040);
      tw.junto().prop(bola, "escala", [e0 * 0.34, e0 * 0.34], 0.040);
      yield tw;
      bola.rolando = false;
      bola.visivel = false;
      bola.passando = false;
      motor.correr(aoBolaFinalizada());
    }

    // tocar_passagem_reta: a bola que não pegou pino nenhum
    function* passagemReta() {
      if (bola.passando) return;
      bola.emMovimento = false;
      bola.passando = true;
      bola.visivel = true;
      bola.rot = 0;
      const base = bola.pos.slice();
      const e0 = bola.escala[0];
      bola.z = 2;
      bola.rolando = true;
      const tw = motor.tween().transicao(T.CUBIC).suavizar(E.OUT);
      tw.prop(bola, "pos", [base[0] + bola.lateral * 6, base[1] - 34], 0.060);
      tw.junto().prop(bola, "mod", [1, 1, 1, 0.90], 0.060);
      tw.junto().prop(bola, "escala", [e0 * 0.72, e0 * 0.72], 0.060);
      tw.prop(bola, "pos", [base[0] + bola.lateral * 12, BOLA.yCacapa], 0.130);
      tw.junto().prop(bola, "mod", [1, 1, 1, 0.46], 0.130);
      tw.junto().prop(bola, "escala", [e0 * 0.40, e0 * 0.40], 0.130);
      tw.prop(bola, "mod", [1, 1, 1, 0], 0.055);
      tw.junto().prop(bola, "escala", [e0 * 0.20, e0 * 0.20], 0.055);
      yield tw;
      bola.rolando = false;
      bola.visivel = false;
      bola.passando = false;
      motor.correr(aoBolaFinalizada());
    }

    /* ------------------------------------------------------------------
       A HUD (configurar_hud e as funções _criar_*): cada painel é uma
       camada pronta; o que muda (números, round, mapa) redesenha só ela.
       ------------------------------------------------------------------ */
    const hud = {
      fundo: { pos: [28, 4], escala: [1, 1], mod: [1, 1, 1, 0] },
      placar: { pos: [42, 12], escala: [1, 1], mod: [1, 1, 1, 0] },
      status: { pos: [54, 168], escala: [1, 1], mod: [1, 1, 1, 0] },
      play: { pos: [710, 12], escala: [1, 1], mod: [1, 1, 1, 0] },
      mapa: { pos: [716, 382], escala: [1, 1], mod: [1, 1, 1, 0] },
      flashPlay: { mod: [1, 0.85, 0.25, 0] },
      bolas: [0, 1, 2].map(() => ({ escala: [1, 1], estado: 0 })),
    };
    const valores = {
      total: 0, emPe: 10, caidos: 0, round: "", derrubados: "", tentativa: "", mapa: 0, placarInfo: "",
    };
    const POSICOES_BOLAS_PLAY = [58, 152, 246];
    const ESTADOS_BOLA = [                       // atualizar_hub_play: modulate de cada 🎳
      [1, 1, 1, 1],                              // a da vez (escala 1,12)
      [0.26, 0.26, 0.30, 0.90],                  // usada
      [0.84, 0.90, 1.0, 0.90],                   // ainda por jogar
      [0.30, 0.30, 0.34, 0.90],                  // jogo acabado
    ];

    const camadaFundo = criarCamada(692, 342, 20, (g) => {
      caixa(g, 0, 0, 692, 342, neon([0.008, 0.016, 0.036, 0.55], [0.15, 0.75, 1.0, 0.70 * 0.35], 42, 3));
      brilhoTopo(g, 692, [0.20, 0.80, 1.0, 0.08], 20, 14, 40, 26, 26);
    });

    const camadaPlacar = criarCamada(660, 152, 20, (g) => {
      caixa(g, 0, 0, 660, 152, neon(COR_BG_PANEL, COR_BORDA_CYAN, 34, 3));
      brilhoTopo(g, 660, [0.25, 0.85, 1.0, 0.13], 14, 10, 28, 26, 22);
      escrever(g, "\u{1F3B3}", 14, 18, 56, 116, painel(40, [1, 1, 1], 0));
      retangulo(g, 78, 16, 2, 118, [0.20, 0.80, 1.0, 0.30]);
      escrever(g, "TOTAL DERRUBADOS", 88, 8, 190, 30, painel(14, COR_TEXTO_CYAN, 4));
      escrever(g, String(valores.total), 88, 38, 190, 76, painel(54, COR_TEXTO_BRANCO, 8));
      retangulo(g, 286, 16, 2, 118, [0.20, 0.80, 1.0, 0.38]);
      escrever(g, "EM PÉ", 298, 8, 150, 30, painel(17, COR_TEXTO_GREEN, 4));
      escrever(g, String(valores.emPe), 298, 38, 150, 76, painel(44, COR_TEXTO_GREEN, 6));
      retangulo(g, 456, 16, 2, 118, [0.20, 0.80, 1.0, 0.26]);
      escrever(g, "CAÍDOS", 466, 8, 174, 30, painel(17, COR_TEXTO_ORANGE, 4));
      escrever(g, String(valores.caidos), 466, 38, 174, 76, painel(44, COR_TEXTO_ORANGE, 6));
      retangulo(g, 26, 128, 608, 2, [0.20, 0.80, 1.0, 0.32]);
    });

    function linhaStatus(g, y, borda, glow, icone, corIcone, titulo, tamTitulo) {
      caixa(g, 0, y, 626, 76, neon([COR_BG_PANEL[0], COR_BG_PANEL[1], COR_BG_PANEL[2], 0.96], borda, 24, 3));
      caixa(g, 0, y, 70, 76, { bg: [glow[0], glow[1], glow[2], glow[3] * 2], raio: [22, 0, 0, 22] });
      escrever(g, icone, 0, y, 70, 76, padrao(30, corIcone, 0));
      escrever(g, titulo, 78, y + 6, 626 - 92, 26, padrao(tamTitulo, borda === COR_BORDA_CYAN ? COR_TEXTO_CYAN : COR_TEXTO_PURPLE, 4, "esquerda"));
    }

    const camadaStatus = criarCamada(626, 166, 20, (g) => {
      linhaStatus(g, 0, COR_BORDA_CYAN, COR_GLOW_CYAN, "\u{1F3C6}", COR_TEXTO_CYAN, "ROUND ATUAL", 16);
      escrever(g, valores.round, 78, 30, 530, 40, painel(27, COR_TEXTO_BRANCO, 6, "esquerda"));
      linhaStatus(g, 88, COR_BORDA_PURPLE, COR_GLOW_PURPLE, "\u{1F3B3}", COR_TEXTO_PURPLE, "DERRUBADOS NO ROUND", 15);
      escrever(g, valores.derrubados, 78, 88 + 30, 530, 40, painel(27, COR_TEXTO_BRANCO, 6, "esquerda"));
    });

    const camadaPlay = criarCamada(304, 210, 20, (g) => {
      caixa(g, 0, 0, 304, 210, neon(COR_BG_PANEL, COR_BORDA_YELLOW, 32, 3));
      brilhoTopo(g, 304, [0.90, 0.75, 0.10, 0.13], 14, 12, 28, 26, 22);
      for (let i = 0; i < 3; i++) {
        retangulo(g, 14 + i * 9, 14, 5, 5, COR_BORDA_YELLOW);
        retangulo(g, 304 - 30 + i * 9, 14, 5, 5, COR_BORDA_YELLOW);
      }
      escrever(g, "PLAY", 14, 10, 276, 42, painel(30, COR_TEXTO_YELLOW, 7));
      linhaDecorativa(g, 304, 58, [0.30, 0.85, 1.0, 0.45], 20, 2);
      caixa(g, 18, 66, 268, 34, { bg: [0.005, 0.012, 0.030, 0.90], borda: [1.0, 0.82, 0.14, 0.75 * 0.5], larguraBorda: 1, raio: 10 });
      escrever(g, valores.tentativa, 18, 66, 268, 34, painel(18, COR_TEXTO_BRANCO, 4));
      linhaDecorativa(g, 304, 106, [0.30, 0.85, 1.0, 0.38], 20, 2);
      linhaDecorativa(g, 304, 210 - 14, [1.0, 0.82, 0.14, 0.38], 20, 2);
    });

    // _criar_mapa_visual: o triângulo dos pinos, verde em pé e cinza caído
    const MAPA_PITCH_X = 56;
    const MAPA_PITCH_Y = 52;
    const MAPA_PONTO = 38;
    const MAPA_ORIGEM_X = 20 + (238 - (MAPA_PITCH_X * 3 + MAPA_PONTO)) * 0.5;
    const MAPA_ORIGEM_Y = 118 + 4;
    const MAPA_POSICOES = {
      7: [0, 0], 8: [1, 0], 9: [2, 0], 10: [3, 0], 4: [0.5, 1], 5: [1.5, 1], 6: [2.5, 1], 2: [1, 2], 3: [2, 2], 1: [1.5, 3],
    };
    const camadaMapa = criarCamada(278, 370, 20, (g) => {
      caixa(g, 0, 0, 278, 370, neon([0.003, 0.038, 0.010, 0.30], COR_BORDA_GREEN, 34, 4));
      brilhoTopo(g, 278, [0.22, 1.0, 0.28, 0.08], 14, 12, 28, 28, 22);
      escrever(g, "\u25C6\u25C6  MAPA DOS PINOS  \u25C6\u25C6", 8, 16, 262, 40, painel(17, COR_TEXTO_GREEN, 5));
      linhaDecorativa(g, 278, 62, [0.28, 1.0, 0.28, 0.34], 22, 3);
      // COR_TEXTO_GREEN * Color(1, 1, 1, 0.74): a letra do subtítulo é translúcida
      escrever(g, "\u2014  FORMAÇÃO DO RACK  \u2014", 8, 70, 262, 45, painel(15, [COR_TEXTO_GREEN[0], COR_TEXTO_GREEN[1], COR_TEXTO_GREEN[2], 0.74], 4));
      for (let n = 1; n <= 10; n++) {
        const [cx, cy] = MAPA_POSICOES[n];
        const x = MAPA_ORIGEM_X + MAPA_PITCH_X * cx;
        const y = MAPA_ORIGEM_Y + MAPA_PITCH_Y * cy;
        const caido = (valores.mapa >> n) & 1;
        g.save();
        if (caido) {
          g.globalAlpha = 0.5;
          g.translate(x, y);
          g.scale(0.9, 0.9);
          caixa(g, 0, 0, MAPA_PONTO, MAPA_PONTO, { bg: [0.10, 0.12, 0.16, 0.98], borda: [0.28, 0.30, 0.36, 0.85], larguraBorda: 2, raio: 999 });
        } else {
          caixa(g, x, y, MAPA_PONTO, MAPA_PONTO, { bg: [0.12, 0.96, 0.44, 1.0], borda: [0.02, 0.08, 0.04, 0.95], larguraBorda: 2, raio: 999 });
        }
        g.restore();
        escrever(g, String(n), x, y, MAPA_PONTO, MAPA_PONTO, painel(20, [0.94, 1.0, 0.92], 4));
      }
      linhaDecorativa(g, 278, 370 - 20, [0.28, 1.0, 0.28, 0.34], 22, 3);
    });

    const camadas = [camadaFundo, camadaPlacar, camadaStatus, camadaPlay, camadaMapa];

    /* Os Labels animados: RoundLabel, BannerLabel e os da tela final. A
       tela pronta de cada um é refeita só quando o texto ou a cor mudam. */
    function criarRotulo(x, y, w, h, estilo) {
      return {
        pos: [x, y], tam: [w, h], estilo, texto: "", escala: [1, 1], pivo: [0, 0], mod: [1, 1, 1, 1],
        tela: null, g: null, folga: 1.35, feito: { texto: null, estilo: null, cor: -1, escala: 0, fontes: false },
      };
    }

    // a cor do modulate em 32 degraus: o tween de cor refaz a tela poucas vezes
    const degrau = (v) => Math.round(lim(v, 0, 1) * 32);

    function prepararRotulo(r, escala) {
      const e = r.estilo;
      const cor = (degrau(r.mod[0]) << 12) | (degrau(r.mod[1]) << 6) | degrau(r.mod[2]);
      if (r.tela && r.feito.texto === r.texto && r.feito.estilo === e && r.feito.cor === cor &&
          r.feito.escala === escala && r.feito.fontes === fontesProntas) return;
      r.feito.texto = r.texto;
      r.feito.estilo = e;
      r.feito.cor = cor;
      r.feito.escala = escala;
      r.feito.fontes = fontesProntas;
      const k = r.folga * escala;
      const margem = 40;
      const W = Math.ceil((r.tam[0] + margem * 2) * SX * k);
      const H = Math.ceil((r.tam[1] + margem * 2) * SY * k);
      if (!r.tela) { r.tela = novaTela(W, H); r.g = r.tela.getContext("2d"); }
      else if (r.tela.width !== W || r.tela.height !== H) { r.tela.width = W; r.tela.height = H; }
      else { r.g.setTransform(1, 0, 0, 1, 0, 0); r.g.clearRect(0, 0, W, H); }
      r.g.setTransform(SX * k, 0, 0, SY * k, margem * SX * k, margem * SY * k);
      if (r.texto) escrever(r.g, r.texto, 0, 0, r.tam[0], r.tam[1], e, [lim(r.mod[0], 0, 1), lim(r.mod[1], 0, 1), lim(r.mod[2], 0, 1)]);
      r.margem = margem;
    }

    function desenharRotulo(ctx, r, escala, deslocX = 0, deslocY = 0) {
      if (!r.texto || r.mod[3] <= 0.003) return;
      prepararRotulo(r, escala);
      const x = r.pos[0] + deslocX;
      const y = r.pos[1] + deslocY;
      const px = x + r.pivo[0];
      const py = y + r.pivo[1];
      ctx.globalAlpha = lim(r.mod[3], 0, 1);
      ctx.setTransform(SX * r.escala[0], 0, 0, SY * r.escala[1], SX * (px - r.pivo[0] * r.escala[0]), SY * (py - r.pivo[1] * r.escala[1]));
      ctx.drawImage(r.tela, -r.margem, -r.margem, r.tam[0] + r.margem * 2, r.tam[1] + r.margem * 2);
      ctx.globalAlpha = 1;
    }

    const roundLabel = criarRotulo(112, 560, 800, 120, arcade(TAM_ROUND_AVISO, COR_TEXTO_CYAN));
    const bannerLabel = criarRotulo(42, 585, 940, 170, arcade(TAM_AVISO_PADRAO, COR_TEXTO_YELLOW));
    roundLabel.mod[3] = 0;
    bannerLabel.mod[3] = 0;

    /* As telas que cobrem a pista (CanvasLayer 40 e 45): os clarões. */
    const flashes = {
      miss: { cor: "rgb(255,51,46)", a: 0 },          // Color(1.0, 0.20, 0.18)
      quente: { cor: "rgb(255,158,31)", a: 0 },       // Color(1.0, 0.62, 0.12)
      branco: { cor: "rgb(255,255,255)", a: 0 },
      spare: { cor: "rgb(255,214,87)", a: 0 },        // Color(1.0, 0.84, 0.34)
    };
    // na ordem das camadas: o PRA FORA (40) embaixo, o strike e o spare (45) em cima
    const listaFlashes = [flashes.miss, flashes.quente, flashes.branco, flashes.spare];

    /* ------------------------------------------------------------------
       A TELA FINAL (criar_tela_final, _efeito_fim_de_jogo_visual,
       mostrar_tela_final)
       ------------------------------------------------------------------ */
    const PAINEL_FINAL = { x: (TELA_W - 940) * 0.5, y: (TELA_H - 790) * 0.5, w: 940, h: 790 };
    const final = {
      visivel: false, bg: 0,
      painel: { mod: [1, 1, 1, 0] },
      card: { pos: [PAINEL_FINAL.x + 200, PAINEL_FINAL.y + 260], escala: [1, 1], mod: [1, 1, 1, 0], stats: "" },
      logo: { pos: [0, 0], tam: [280, 105], escala: [1, 1], pivo: [140, 52.5], mod: [1, 1, 1, 0] },
      botao: { visivel: false, escala: [1, 1] },
      titulo: criarRotulo(PAINEL_FINAL.x + 40, PAINEL_FINAL.y + 42, 860, 74, arcade(48, COR_TEXTO_YELLOW)),
      recorde: criarRotulo(PAINEL_FINAL.x + 60, PAINEL_FINAL.y + 540, 820, 50, painel(24, COR_TEXTO_CYAN, 5)),
      timer: criarRotulo(PAINEL_FINAL.x + 60, PAINEL_FINAL.y + 605, 820, 44, painel(24, COR_TEXTO_YELLOW, 5)),
    };
    final.titulo.folga = 1.2;
    final.recorde.folga = 1;
    final.timer.folga = 1;

    const camadaPainelFinal = criarCamada(940, 790, 56, (g) => {
      caixa(g, 0, 0, 940, 790, {
        bg: [0.006, 0.014, 0.040, 0.97], borda: [0.18, 0.82, 1.0, 0.95], larguraBorda: 5, raio: 44,
        sombra: [0.0, 0.70, 1.0, 0.55], tamSombra: 52,
      });
    });
    const camadaCardFinal = criarCamada(540, 265, 46, (g) => {
      const c = COR_TEXTO_CYAN;
      caixa(g, 0, 0, 540, 265, {
        bg: [c[0] * 0.10, c[1] * 0.10, c[2] * 0.10, 0.94], borda: c, larguraBorda: 5, raio: 28,
        sombra: [c[0], c[1], c[2], 0.70], tamSombra: 42,
      });
      escrever(g, "RESULTADO", 28, 22, 484, 48, painel(25, COR_TEXTO_CYAN, 5));
      escrever(g, final.card.stats, 36, 88, 468, 140, painel(25, COR_TEXTO_BRANCO, 5));
    });
    const BOTAO_FINAL = { w: 660, h: 84 };
    const camadaBotaoFinal = criarCamada(BOTAO_FINAL.w, BOTAO_FINAL.h, 28, (g) => {
      caixa(g, 0, 0, BOTAO_FINAL.w, BOTAO_FINAL.h, {
        bg: [0.08, 0.42, 1.0, 0.98], borda: [1.0, 0.92, 0.32, 1.0], larguraBorda: 4, raio: 24,
        sombra: [0.0, 0.65, 1.0, 0.45], tamSombra: 24,
      });
      retangulo(g, 28, 12, BOTAO_FINAL.w - 56, 4, [1.0, 0.96, 0.72, 0.28]);
      escrever(g, "PRESSIONE START PARA RECOMEÇAR", 0, 0, BOTAO_FINAL.w, BOTAO_FINAL.h,
        estiloTexto(FONTE_PAINEL, 24, [1, 1, 1], 6, { corContorno: [0, 0, 0] }));
    });
    const camadasFinais = [camadaPainelFinal, camadaCardFinal, camadaBotaoFinal];

    function sujarTudo() {
      for (const c of camadas) c.sujo = true;
      for (const c of camadasFinais) c.sujo = true;
      fotoValida = false;
    }
    carregarFontes().then(() => { if (!destruido) sujarTudo(); });

    /* ------------------------------------------------------------------
       PLACAR, STATUS, PLAY E MAPA (atualizar_*)
       ------------------------------------------------------------------ */
    function totalPinosDerrubadosPartida() {
      let total = 0;
      for (const item of historicoRounds) total += item.derrubados;
      if (!jogoFinalizado && !transicaoRoundEmAndamento) total += pinosDerrubadosNoRound;
      return total;
    }

    function atualizarPlacar() {
      const emPe = contarPinosEmPe();
      const caidos = lim(pinosDerrubadosNoRound, 0, 10);
      const total = totalPinosDerrubadosPartida();
      if (emPe !== valores.emPe || caidos !== valores.caidos || total !== valores.total) {
        valores.emPe = emPe;
        valores.caidos = caidos;
        valores.total = total;
        camadaPlacar.sujo = true;
      }
      informarConsole();
    }

    function informarConsole() {
      const info = `ROUND ${Math.min(roundAtual, ROUNDS)}/${ROUNDS} · BOLA ${tentativaAtual}`;
      const chave = `${valores.total}|${info}`;
      if (chave === valores.placarInfo) return;
      valores.placarInfo = chave;
      api.placar({ pontos: valores.total, info });
    }

    function atualizarStatus() {
      const round = `ROUND  ${roundAtual}  /  ${ROUNDS}`;
      const derrubados = `${pinosDerrubadosNoRound}  /  10  PINOS DERRUBADOS`;
      if (round !== valores.round || derrubados !== valores.derrubados) {
        valores.round = round;
        valores.derrubados = derrubados;
        camadaStatus.sujo = true;
      }
    }

    function atualizarHubPlay() {
      const usadas = lim(tentativaAtual - 1, 0, MAX_TENTATIVAS);
      const tentativa = `TENTATIVA ${tentativaAtual} / ${MAX_TENTATIVAS}`;
      if (tentativa !== valores.tentativa) {
        valores.tentativa = tentativa;
        camadaPlay.sujo = true;
      }
      for (let i = 0; i < 3; i++) {
        const b = hud.bolas[i];
        let estado;
        let escala;
        if (jogoFinalizado) { estado = 3; escala = 0.90; }
        else if (i < usadas) { estado = 1; escala = 0.90; }
        else if (i === usadas) { estado = 0; escala = 1.12; }
        else { estado = 2; escala = 1.0; }
        b.estado = estado;
        b.escala[0] = b.escala[1] = escala;
      }
    }

    function animarConsumoTentativa(indice) {
      if (indice < 0 || indice > 2) return;
      const b = hud.bolas[indice];
      const tw = motor.tween().transicao(T.BACK).suavizar(E.OUT);
      tw.prop(b, "escala", [1.22, 1.22], 0.08);
      tw.prop(b, "escala", [0.92, 0.92], 0.14);
      hud.flashPlay.mod[3] = 0;
      const tw2 = motor.tween();
      tw2.prop(hud.flashPlay, "mod", [1, 0.85, 0.25, 0.12], 0.05);
      tw2.prop(hud.flashPlay, "mod", [1, 0.85, 0.25, 0], 0.16);
    }

    function atualizarMapaVisual() {
      let mapa = 0;
      for (const p of pins) if (p.derrubado) mapa |= 1 << p.numero;
      if (mapa !== valores.mapa) {
        valores.mapa = mapa;
        camadaMapa.sujo = true;
      }
    }

    function marcarHudComoSuja() {
      hudSujo = true;
    }

    function registrarResultadoRound(derrubados, strike, spare) {
      historicoRounds.push({ round: roundAtual, tentativas: tentativaAtual, derrubados, strike, spare });
    }

    /* ------------------------------------------------------------------
       A CÂMERA: tremor e soco de zoom (shake_camera, efeito_impacto_deck)
       ------------------------------------------------------------------ */
    function shakeCamera(forca = 5, duracao = 0.15, passos = 8) {
      if (api.reduzido) return;
      motor.correr(shakeCameraAsync(forca, duracao, passos));
    }

    function* shakeCameraAsync(forca, duracao, passos) {
      passos = Math.max(passos, 1);
      for (let i = 0; i < passos; i++) {
        const decai = 1 - i / passos;
        camera.offset[0] = aleatorio(-forca, forca) * decai;
        camera.offset[1] = aleatorio(-forca * 0.9, forca * 0.9) * decai;
        yield duracao / passos;
      }
      camera.offset[0] = camera.offset[1] = 0;
    }

    function efeitoImpactoDeck(intensidade) {
      const cheio = tentativaAtual === 1 && contarPinosEmPe() === 10;
      const forte = ultimaTeclaJogada === "C" && cheio;
      shakeCamera((forte ? 8.5 : 5.0) * intensidade, forte ? 0.10 : 0.08, forte ? 7 : 5);
      if (api.reduzido) return;
      const z = forte ? 1.045 : 1.025;
      const tw = motor.tween();
      tw.prop(camera, "zoom", [z, z], 0.05).com(T.EXPO).suave(E.OUT);
      tw.prop(camera, "zoom", [1, 1], 0.22).com(T.SINE).suave(E.OUT);
    }

    function aplicarZoomJogada() {
      if (api.reduzido) return;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(camera, "zoom", [CAMERA_ZOOM_JOGADA, CAMERA_ZOOM_JOGADA], 0.08).com(T.SINE).suave(E.OUT);
      tw.prop(camera, "pos", [CAMERA_BASE[0] + CAMERA_FOCO_JOGADA[0], CAMERA_BASE[1] + CAMERA_FOCO_JOGADA[1]], 0.08).com(T.SINE).suave(E.OUT);
      tw.encadear().definirParalelo(true);
      tw.prop(camera, "zoom", [1, 1], 0.15).com(T.SINE).suave(E.IN_OUT);
      tw.prop(camera, "pos", CAMERA_BASE, 0.15).com(T.SINE).suave(E.IN_OUT);
    }

    // _animar_rastro_bola_ao_lancar: a compressão da câmera no lançamento
    function animarRastroBolaAoLancar() {
      if (api.reduzido) return;
      const z = CAMERA_ZOOM_JOGADA * 0.985;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(camera, "zoom", [z, z], 0.06).com(T.EXPO).suave(E.OUT);
      tw.encadear().definirParalelo(true);
      tw.prop(camera, "zoom", [1, 1], 0.22).com(T.SINE).suave(E.IN_OUT);
    }

    /* ------------------------------------------------------------------
       OS AVISOS (mostrar_banner, mostrar_round_banner, _animar_label_arcade)
       O modulate do Label também é a cor: a letra sai cor x cor.
       ------------------------------------------------------------------ */
    function animarLabelArcade(lbl, cor, strike) {
      lbl.pivo[0] = lbl.tam[0] * 0.5;
      lbl.pivo[1] = lbl.tam[1] * 0.5;
      lbl.mod[0] = cor[0]; lbl.mod[1] = cor[1]; lbl.mod[2] = cor[2]; lbl.mod[3] = 0;
      const inicio = strike ? 0.44 : 0.58;
      const pico = strike ? 1.28 : 1.10;
      lbl.escala[0] = lbl.escala[1] = inicio;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(lbl, "mod", [cor[0], cor[1], cor[2], 1], 0.10);
      tw.prop(lbl, "escala", [pico, pico], 0.16).com(T.BACK).suave(E.OUT);
      tw.encadear().prop(lbl, "escala", [1, 1], 0.12).com(T.SINE).suave(E.OUT);
      tw.encadear().intervalo(0.70);
      tw.encadear().prop(lbl, "mod", [cor[0], cor[1], cor[2], 0], 0.22);
      tw.junto().prop(lbl, "escala", [0.96, 0.96], 0.22);
    }

    function mostrarBanner(texto, cor) {
      const eStrike = texto.toUpperCase().includes("STRIKE");
      bannerLabel.texto = texto;
      bannerLabel.estilo = arcade(eStrike ? TAM_AVISO_STRIKE : TAM_AVISO_PADRAO, cor);
      animarLabelArcade(bannerLabel, cor, eStrike);
    }

    function mostrarRoundBanner(n) {
      roundLabel.texto = `ROUND ${n}`;
      roundLabel.estilo = arcade(TAM_ROUND_AVISO, COR_ROUND);
      animarLabelArcade(roundLabel, COR_ROUND, false);
    }

    function* mostrarRoundBannerIntro(n) {
      roundLabel.texto = `ROUND ${n}`;
      roundLabel.escala[0] = roundLabel.escala[1] = 0.72;
      roundLabel.mod[0] = COR_ROUND[0]; roundLabel.mod[1] = COR_ROUND[1]; roundLabel.mod[2] = COR_ROUND[2]; roundLabel.mod[3] = 0;
      const tw = motor.tween().transicao(T.SINE).suavizar(E.OUT);
      tw.prop(roundLabel, "mod", [COR_ROUND[0], COR_ROUND[1], COR_ROUND[2], 1], 0.18);
      tw.junto().prop(roundLabel, "escala", [1, 1], 0.18);
      tw.intervalo(1.10);
      tw.prop(roundLabel, "mod", [COR_ROUND[0], COR_ROUND[1], COR_ROUND[2], 0], 0.24);
      tw.junto().prop(roundLabel, "escala", [1.03, 1.03], 0.24);
      yield tw;
    }

    function efeitoStrikeTotal() {
      shakeCamera(9.5, 0.22, 14);
      motor.correr(efeitoCanaletaStrike(2.0));
      return efeitoStrikeTotalAsync();
    }

    function* efeitoStrikeTotalAsync() {
      flashes.quente.a = 0;
      flashes.branco.a = 0;
      bannerLabel.escala[0] = bannerLabel.escala[1] = 0.86;
      bannerLabel.mod[0] = 1.0; bannerLabel.mod[1] = 0.96; bannerLabel.mod[2] = 0.72; bannerLabel.mod[3] = 0;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(flashes.branco, "a", 0.28, 0.035);
      tw.prop(flashes.quente, "a", 0.22, 0.08);
      tw.prop(bannerLabel, "mod", [1.0, 0.96, 0.72, 1.0], 0.08);
      tw.prop(bannerLabel, "escala", [1.18, 1.18], 0.11);
      yield 0.09;
      const tw2 = motor.tween().definirParalelo(true);
      tw2.prop(flashes.branco, "a", 0, 0.10);
      tw2.prop(flashes.quente, "a", 0, 0.18);
      tw2.prop(bannerLabel, "escala", [0.98, 0.98], 0.14);
      yield 0.05;
      motor.tween().prop(bannerLabel, "escala", [1.06, 1.06], 0.10);
      yield 0.08;
      motor.tween().prop(bannerLabel, "escala", [1.0, 1.0], 0.12);
      yield 0.20;
      flashes.quente.a = 0;
      flashes.branco.a = 0;
    }

    function* efeitoSpareTotal() {
      shakeCamera(4.0, 0.12, 7);
      flashes.spare.a = 0;
      bannerLabel.escala[0] = bannerLabel.escala[1] = 0.94;
      bannerLabel.mod[0] = 1.0; bannerLabel.mod[1] = 0.95; bannerLabel.mod[2] = 0.82; bannerLabel.mod[3] = 0;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(flashes.spare, "a", 0.12, 0.08);
      tw.prop(bannerLabel, "mod", [1.0, 0.95, 0.82, 1.0], 0.10);
      tw.prop(bannerLabel, "escala", [1.08, 1.08], 0.12);
      yield 0.12;
      const tw2 = motor.tween().definirParalelo(true);
      tw2.prop(flashes.spare, "a", 0, 0.18);
      tw2.prop(bannerLabel, "escala", [1.0, 1.0], 0.16);
      yield 0.18;
      flashes.spare.a = 0;
    }

    function efeitoMissTotal() {
      mostrarBanner("PRA FORA!", [1.0, 0.35, 0.30]);
      shakeCamera(4.2, 0.08, 6);
      motor.correr(efeitoCanaletaErro(2.2));
      flashes.miss.a = 0;
      const tw = motor.tween();
      tw.prop(flashes.miss, "a", 0.18, 0.035);
      tw.prop(flashes.miss, "a", 0, 0.08);
    }

    /* ------------------------------------------------------------------
       A JOGADA (game.gd): do sensor até o resultado
       ------------------------------------------------------------------ */
    function pinosDaFaixaEmPe(tecla) {
      const lista = [];
      for (const n of PINOS_DA_FAIXA[tecla] || []) {
        const p = obterPino(n);
        if (p && !p.derrubado) lista.push(p);
      }
      return lista;
    }

    function garantiaBordaNaAbertura() {
      return tentativaAtual === 1 && pinosAntesDaJogada >= 10;
    }

    // faixa_valida_por_tecla: o x em que a bola de cada tecla pode tocar pino
    function faixaValidaPorTecla(tecla) {
      const emPe = contarPinosEmPe();
      const amp = emPe <= 4 ? 30 : emPe <= 6 ? 16 : 0;
      const faixas = { Z: [360, 432], X: [420, 530], C: [440, 584], V: [494, 620], B: [592, 664] };
      const f = faixas[tecla] || [0, 1024];
      return [f[0] - amp, f[1] + amp];
    }

    function larguraCorredorPorTecla(tecla) {
      if (tecla === "Z" || tecla === "B") return 10;
      if (tecla === "X" || tecla === "V") return 20;
      if (tecla === "C") return 34;
      return 12;
    }

    function raioColisaoPino(p) {
      const [w, h] = areaColisao(p);
      return Math.max(18, Math.min(w, h) * 0.34);
    }

    // _obter_segmento_trajetoria_bola: da bola até o fundo do rack
    function segmentoTrajetoriaBola(px, py) {
      const a = [bola.pos[0], bola.pos[1]];
      let b = [px, py];
      if (ultimaTeclaJogada === "C") b = [px, Math.min(py, 580)];
      else if (ultimaTeclaJogada === "X" || ultimaTeclaJogada === "V") b = [px, Math.min(py, 620)];
      return [a, b];
    }

    function obterPinosNoCaminhoBola(px, py) {
      const [a, b] = segmentoTrajetoriaBola(px, py);
      const lista = [];
      let largura = larguraCorredorPorTecla(ultimaTeclaJogada);
      const faixa = faixaValidaPorTecla(ultimaTeclaJogada);
      const emPe = contarPinosEmPe();
      if (emPe <= 3) largura *= 0.72;
      else if (emPe <= 5) largura *= 0.86;
      if (ultimaTeclaJogada === "C") {
        const p1 = obterPino(1);
        if (p1 && !p1.derrubado) lista.push({ pin: p1, proj: -1, dist: 0 });
      }
      const abx = b[0] - a[0];
      const aby = b[1] - a[1];
      const comp2 = abx * abx + aby * aby;
      const comp = Math.sqrt(comp2);
      for (const p of pins) {
        if (p.derrubado) continue;
        if (p.pos[0] < faixa[0] || p.pos[0] > faixa[1]) continue;
        if (ultimaTeclaJogada === "C" && p.numero === 1) continue;
        const proj = comp <= 0.0001 ? 0 : ((p.pos[0] - a[0]) * abx + (p.pos[1] - a[1]) * aby) / comp;
        if (proj < 0) continue;
        let d;
        if (comp2 <= 0.0001) d = dist(p.pos[0], p.pos[1], a[0], a[1]);
        else {
          const t = lim(((p.pos[0] - a[0]) * abx + (p.pos[1] - a[1]) * aby) / comp2, 0, 1);
          d = dist(p.pos[0], p.pos[1], a[0] + abx * t, a[1] + aby * t);
        }
        if (d <= raioColisaoPino(p) + largura) lista.push({ pin: p, proj, dist: d });
      }
      lista.sort((x, y) => x.proj - y.proj);
      return lista;
    }

    // _primeiro_pino_da_faixa: o primeiro do caminho que é da faixa da tecla
    function primeiroPinoDaFaixa(px, py) {
      const daFaixa = pinosDaFaixaEmPe(ultimaTeclaJogada);
      if (!daFaixa.length) return null;
      for (const item of obterPinosNoCaminhoBola(px, py)) if (daFaixa.includes(item.pin)) return item.pin;
      return daFaixa[0];
    }

    function calcularPontoContatoNoPino(p, px, py) {
      const [w, h] = areaColisao(p);
      let dx = p.pos[0] - px;
      let dy = p.pos[1] - py;
      const len = Math.hypot(dx, dy);
      if (len < 0.001) { dx = 0; dy = 1; } else { dx /= len; dy /= len; }
      let fator = 0.20;
      let ofsY = 7.5;
      if (p.numero === 1) { fator = 0.16; ofsY = 5.5; }
      else if (p.numero <= 3) { fator = 0.15; ofsY = 5.0; }
      else if (p.numero <= 6) { fator = 0.18; ofsY = 7.0; }
      const m = Math.min(w, h) * fator;
      return [p.pos[0] - dx * m, p.pos[1] - dy * m + ofsY];
    }

    function energiaMinimaParaCair(n) {
      switch (ultimaTeclaJogada) {
        case "Z": case "B":
          if (n === 7 || n === 10) return garantiaBordaNaAbertura() ? 0.20 : 0.30;
          if (n === 4 || n === 6) return 0.44;
          if (n === 8 || n === 9) return 0.48;
          return 0.54;
        case "X": case "V":
          if (n === 2 || n === 3 || n === 4 || n === 6) return 0.24;
          if (n === 7 || n === 9) return 0.18;
          if (n === 8 || n === 10) return 0.22;
          return 0.38;
        case "C":
          if (n === 1) return 0.15;
          if (n === 2 || n === 3 || n === 5) return 0.18;
          if (n === 4 || n === 6) return 0.20;
          if (n === 8 || n === 9) return 0.17;
          if (n === 7 || n === 10) return 0.14;
          return 0.28;
        default: return 0.30;
      }
    }

    function maxSecundariosPorTecla() {
      const emPe = contarPinosEmPe();
      switch (ultimaTeclaJogada) {
        case "Z": case "B": return emPe <= 3 ? 1 : 2;
        case "X": case "V": return emPe <= 3 ? 1 : emPe <= 6 ? 3 : 5;
        case "C": return emPe <= 3 ? 2 : emPe <= 6 ? 5 : 8;
        default: return 2;
      }
    }

    // _empurrar_pinos_proximos_da_passagem: o vento da bola nos vizinhos
    function empurrarPinosProximosDaPassagem(px, py, principal, forca) {
      const t = ultimaTeclaJogada;
      for (const p of pins) {
        if (p === principal || p.derrubado) continue;
        const n = p.numero;
        if (t === "V" && n === 2) continue;
        if (t === "X" && n === 3) continue;
        if (t === "X" && ![4, 5, 7, 8, 9].includes(n)) continue;
        if (t === "V" && ![5, 6, 8, 9, 10].includes(n)) continue;
        const d = dist(p.pos[0], p.pos[1], px, py);
        if (d > 92) continue;
        const intensidade = lim((92 - d) / 92, 0, 1) * forca * 0.34;
        receberForca(p, p.pos[0] - px, p.pos[1] - py, intensidade, px, py);
      }
    }

    function energiaBasePorTecla(tecla) {
      if (tecla === "Z" || tecla === "B") return 0.98;
      if (tecla === "X" || tecla === "V") return 1.04;
      if (tecla === "C") return 1.18;
      return 1;
    }

    function* aplicarImpulsoRealista(principal, px, py, forca, lateral) {
      let impactos = obterPinosNoCaminhoBola(px, py);
      if (!impactos.length) impactos = [{ pin: principal, proj: 0, dist: 0 }];
      const origem = segmentoTrajetoriaBola(px, py)[0];
      let dirX = px - origem[0];
      let dirY = py - origem[1];
      let len = Math.hypot(dirX, dirY);
      if (len <= 0.001) { dirX = lateral; dirY = -1; len = Math.hypot(dirX, dirY); }
      dirX /= len;
      dirY /= len;
      let energia = lim(energiaBasePorTecla(ultimaTeclaJogada) * forca, 0.98, 1.30);
      const t = ultimaTeclaJogada;
      if (t === "Z" || t === "B") energia = lim(energia, 0.96, 1.02);
      else if (t === "X" || t === "V") energia = lim(energia, 1.00, 1.10);
      else if (t === "C") energia = lim(energia, 1.18, 1.30);
      let maxDiretos = t === "C" ? 6 : t === "X" || t === "V" ? 2 : 1;
      if (contarPinosEmPe() <= 3) maxDiretos = 1;
      const processados = [];
      for (const item of impactos) {
        if (processados.length >= maxDiretos) break;
        const p = item.pin;
        if (!p || p.derrubado) continue;
        let e = energia;
        const k = processados.length;
        if (k === 1) e *= 0.97;
        else if (k === 2) e *= 0.93;
        else if (k >= 3) e *= 0.88;
        if (t === "C") {
          const n = p.numero;
          if (n === 1) e += 0.14;
          else if (n === 2 || n === 3) e += 0.12;
          else if (n === 5) e += 0.16;
          else if (n === 4 || n === 6) e += 0.18;
          else if (n === 8 || n === 9) e += 0.30;
          else if (n === 7 || n === 10) e += 0.38;
        }
        receberForca(p, dirX, dirY, e, px, py);
        processados.push({ pin: p, energia: e });
      }
      if (processados.length) yield QUADRO;
      for (const item of processados) propagarColisaoCurta(item.pin, item.energia * 1.08, dirX, dirY);
      if (t === "C" && contarPinosEmPe() >= 6) {
        yield QUADRO;
        for (const n of [5, 4, 6, 2, 3, 8, 9, 7, 10]) {
          const p = obterPino(n);
          if (!p || p.derrubado) continue;
          let extra = 0.88;
          if (n === 8 || n === 9) extra = 0.98;
          else if (n === 7 || n === 10) extra = 1.08;
          receberForca(p, 0, -1, extra, px, py);
          propagarColisaoCurta(p, extra * 0.94, 0, -1);
        }
      }
    }

    // _propagar_colisao_curta: um pino derruba os vizinhos da frente
    function propagarColisaoCurta(origem, energiaBase, dirX, dirY) {
      if (!origem) return;
      const t = ultimaTeclaJogada;
      const maxSec = maxSecundariosPorTecla();
      const candidatos = [];
      for (const nv of VIZINHOS_PINOS[origem.numero] || []) {
        const alvo = obterPino(nv);
        if (!alvo || alvo.derrubado) continue;
        const vx = alvo.pos[0] - origem.pos[0];
        const vy = alvo.pos[1] - origem.pos[1];
        const d = Math.hypot(vx, vy);
        const dMax = t === "C" ? 160 : t === "X" || t === "V" ? 120 : 92;
        if (d > dMax) continue;
        const ux = vx / (d || 1);
        const uy = vy / (d || 1);
        const alinhamento = Math.max(0, dirX * ux + dirY * uy);
        const frente = lim((origem.pos[1] - alvo.pos[1] + 18) / 64, 0, 1);
        const lateralidade = lim(Math.abs(vx) / 86, 0, 1);
        let e = energiaBase * mistura(0.18, 0.66, alinhamento) + frente * 0.32 - lateralidade * 0.14;
        const n = alvo.numero;
        const o = origem.numero;
        if (t === "C") {
          if (o === 1 && (n === 2 || n === 3 || n === 5)) e += 0.12;
          else if (o === 5 && (n === 4 || n === 6)) e += 0.14;
          else if (o === 5 && (n === 8 || n === 9)) e += 0.55;
          else if (n === 7 || n === 10) e += 0.40;
        } else if (t === "X") {
          if (n === 7 || n === 8) e += 0.38;
          else if (n === 4 || n === 5) e += 0.22;
        } else if (t === "V") {
          if (n === 9 || n === 10) e += 0.38;
          else if (n === 5 || n === 6) e += 0.22;
        } else if (t === "Z") {
          if (n === 4) e += 0.04;
          else if (n === 8) e += 0.02;
          else e -= 0.12;
        } else if (t === "B") {
          if (n === 6) e += 0.04;
          else if (n === 9) e += 0.02;
          else e -= 0.12;
        }
        if (contarPinosEmPe() <= 4 && t !== "C") e *= 0.82;
        if (e < energiaMinimaParaCair(n)) continue;
        const score = frente * 1.95 + alinhamento * 1.00 - lateralidade * 0.78 - d * 0.0035;
        candidatos.push({ pin: alvo, energia: e, ux, uy, score, atraso: d / 520 + aleatorio(0, 0.02) });
      }
      candidatos.sort((a, b) => b.score - a.score);
      let aplicados = 0;
      for (const c of candidatos) {
        if (aplicados >= maxSec) break;
        if (!c.pin.derrubado) {
          if (c.atraso > 0.008) motor.correr(aplicarForcaComAtraso(c.pin, c.ux, c.uy, c.energia, origem.pos[0], origem.pos[1], c.atraso));
          else receberForca(c.pin, c.ux, c.uy, c.energia, origem.pos[0], origem.pos[1]);
        }
        aplicados++;
      }
    }

    function* aplicarForcaComAtraso(alvo, ux, uy, energia, ox, oy, atraso) {
      yield atraso;
      if (!alvo.derrubado && !alvo.liberado) receberForca(alvo, ux, uy, energia, ox, oy);
    }

    // _forcar_fundo_xv_agora: no X o 8 cai, no V o 9 (e o 5 depois do C)
    function* forcarFundoXvAgora(px, py) {
      const t = ultimaTeclaJogada;
      if (t !== "X" && t !== "V") return;
      const alvos = [];
      if (bloquearSparePosC) {
        const p5 = obterPino(5);
        if (p5 && !p5.derrubado) alvos.push(5);
      }
      alvos.push(t === "X" ? 8 : 9);
      for (const n of alvos) {
        const p = obterPino(n);
        if (!p || p.derrubado) continue;
        const atraso = lim(dist(p.pos[0], p.pos[1], px, py) / 520, 0.04, 0.22);
        const anim = n === 8 ? "down_rt" : n === 9 ? "down_left" : "strike";
        motor.correr(cairVoando(p, anim, 3.0, px, py, atraso));
      }
      yield QUADRO;
      marcarHudComoSuja();
      atualizarMapaVisual();
      atualizarPlacar();
    }

    // _forcar_c_depois_lateral: C depois de X/V derruba o 1 e o fundo do outro lado
    function* forcarCDepoisLateral(px, py) {
      if (!bloquearSparePosLateralC) return;
      const alvos = [];
      const p1 = obterPino(1);
      if (p1 && !p1.derrubado) alvos.push(1);
      if (lateralAnteriorParaC === "V") alvos.push(8);
      else if (lateralAnteriorParaC === "X") alvos.push(9);
      for (const n of alvos) {
        const p = obterPino(n);
        if (!p || p.derrubado) continue;
        const anim = n === 8 ? "down_rt" : n === 9 ? "down_left" : "strike";
        forcarQuedaImediata(p, anim, 3.0, px, py);
      }
      yield QUADRO;
      marcarHudComoSuja();
      atualizarMapaVisual();
      atualizarPlacar();
    }

    // _forcar_strike_central_se_preciso: a bolinha no rack cheio é strike garantido
    function* forcarStrikeCentralSePreciso(px, py) {
      if (ultimaTeclaJogada !== "C" || tentativaAtual !== 1 || pinosAntesDaJogada !== 10) return;
      const grupos = [[1], [2, 3], [4, 5, 6], [7, 8, 9, 10]];
      for (let gi = 0; gi < grupos.length; gi++) {
        for (const n of grupos[gi]) {
          const p = obterPino(n);
          if (!p || p.derrubado) continue;
          let anim = "strike";
          if ([2, 4, 7, 8].includes(n)) anim = "down_rt";
          else if ([3, 6, 9, 10].includes(n)) anim = "down_left";
          let intensidade = 1.34;
          if (n === 8 || n === 9) intensidade = 1.44;
          else if (n === 7 || n === 10) intensidade = 1.56;
          else if (n === 4 || n === 6) intensidade = 1.38;
          else if (n === 2 || n === 3) intensidade = 1.30;
          motor.correr(cairVoando(p, anim, intensidade, px, py, aleatorio(0, 0.03) * gi));
        }
        yield mistura(0.055, 0.095, gi / 3);
      }
      yield 0.15;
      yield QUADRO;
      marcarHudComoSuja();
    }

    // _aplicar_quase_queda_ao_redor: os vizinhos balançam (só visual)
    function aplicarQuaseQuedaAoRedor(principal, px, py) {
      const t = ultimaTeclaJogada;
      const maxQuases = t === "C" ? 3 : t === "X" || t === "V" ? 2 : 1;
      const candidatos = [];
      for (const nv of VIZINHOS_PINOS[principal.numero] || []) {
        const p = obterPino(nv);
        if (!p || p.derrubado) continue;
        let score = dist(principal.pos[0], principal.pos[1], p.pos[0], p.pos[1]);
        if (t === "C" && [4, 6, 8, 9].includes(p.numero)) score -= 18;
        else if (t === "X" && [4, 5, 7, 8].includes(p.numero)) score -= 12;
        else if (t === "V" && [5, 6, 9, 10].includes(p.numero)) score -= 12;
        candidatos.push({ p, score });
      }
      candidatos.sort((a, b) => a.score - b.score);
      let aplicados = 0;
      for (const c of candidatos) {
        if (aplicados >= maxQuases) break;
        if (c.p.derrubado) continue;
        let dx = c.p.pos[0] - px;
        const dy = c.p.pos[1] - py;
        const len = Math.hypot(dx, dy);
        dx = len > 0.001 ? dx / len : 1;
        oscilar(c.p, dx, 0.92);
        aplicados++;
      }
    }

    /* executar_jogada_por_tecla: o sensor acionou */
    function executarJogadaPorTecla(tecla) {
      if (introEmAndamento || !aceitandoInput || transicaoRoundEmAndamento) return;
      if (jogandoTrajeto || jogoFinalizado || !CONFIG_JOGADAS[tecla]) return;
      aceitandoInput = false;
      jogandoTrajeto = true;
      ultimaJogadaEm = relogio;
      bloquearSparePosC = tentativaAtual >= 2 && teclaAnteriorNoRound === "C" && (tecla === "X" || tecla === "V");
      bloquearSparePosLateralC = tentativaAtual >= 2 && tecla === "C" && (teclaAnteriorNoRound === "X" || teclaAnteriorNoRound === "V");
      lateralAnteriorParaC = bloquearSparePosLateralC ? teclaAnteriorNoRound : "";
      ultimaTeclaJogada = tecla;
      pinosAntesDaJogada = contarPinosEmPe();
      animarConsumoTentativa(lim(tentativaAtual - 1, 0, 2));
      marcarHudComoSuja();
      const cfg = CONFIG_JOGADAS[tecla];
      let dirX = cfg.dir[0] + aleatorio(-0.0015, 0.0015);
      let forca = cfg.forca + aleatorio(-0.004, 0.004);
      let spin = cfg.spin + aleatorio(-0.05, 0.05);
      if (tecla === "X") { dirX = -0.48; forca = 1.08; spin = -0.04; }
      else if (tecla === "V") { dirX = 0.48; forca = 1.08; spin = 0.04; }
      else if (tecla === "C") { dirX = 0; forca = 1.06; spin = 0; }
      lancarBola(dirX, forca, spin);
      som("whoosh");                   // o rolar da bola (bola-roll_.wav)
      aplicarZoomJogada();
      animarRastroBolaAoLancar();
    }

    /* _on_bola_impacto_no_deck: a bola chegou nos pinos */
    function* aoImpactoNoDeck(ix, iy, forca, lateral) {
      if (processandoImpacto) return;
      processandoImpacto = true;
      const emPeAntes = pins.map((p) => !p.derrubado);

      if (!pinosDaFaixaEmPe(ultimaTeclaJogada).length) {
        yield* tratarJogadaSemAlvoNaFaixa();
        processandoImpacto = false;
        return;
      }

      const principal = primeiroPinoDaFaixa(ix, iy);
      const [cx, cy] = calcularPontoContatoNoPino(principal, ix, iy);
      efeitoImpactoDeck(lim(forca, 0.96, 1.22));
      // a bola não para no pino: atravessa na hora, junto com a pancada
      motor.correr(passagemPorCima(cx, cy, principal.z));
      destacarAcerto(principal);
      impactoVisual(principal, lim(forca, 0.95, 1.18), cx);

      if (ultimaTeclaJogada === "Z" || ultimaTeclaJogada === "B") {
        // um único pino, sem propagação para os vizinhos
        forcarQuedaImediata(principal, ultimaTeclaJogada === "Z" ? "down_rt" : "down_left", 1.08, cx, cy);
      } else if (bloquearSparePosLateralC) {
        yield* forcarCDepoisLateral(cx, cy);
      } else {
        empurrarPinosProximosDaPassagem(cx, cy, principal, forca);
        yield* aplicarImpulsoRealista(principal, cx, cy, forca, lateral);
        if (ultimaTeclaJogada === "X" || ultimaTeclaJogada === "V") yield* forcarFundoXvAgora(cx, cy);
      }
      if (ultimaTeclaJogada === "C") {
        yield* forcarStrikeCentralSePreciso(cx, cy);
        aplicarQuaseQuedaAoRedor(principal, cx, cy);
      }

      yield 0.06;
      atualizarPlacar();

      const contarDerrubados = () => {
        let n = 0;
        for (let i = 0; i < pins.length; i++) if (emPeAntes[i] && pins[i].derrubado) n++;
        return n;
      };
      let derrubados = contarDerrubados();
      let emPeDepois = contarPinosEmPe();
      let total = pinosDerrubadosNoRound + derrubados;
      const foiStrike = emPeDepois === 0 && tentativaAtual === 1 && pinosAntesDaJogada === 10;
      const foiSpare = !foiStrike && !bloquearSparePosC && !bloquearSparePosLateralC && total >= 10 && tentativaAtual === 2;

      if (foiStrike) {
        for (const n of [7, 10, 8, 9, 4, 6, 2, 3, 5, 1]) {
          const p = obterPino(n);
          if (!p || p.derrubado) continue;
          let anim = "strike";
          if ([7, 8, 2, 4].includes(n)) anim = "down_rt";
          else if ([10, 9, 3, 6].includes(n)) anim = "down_left";
          motor.correr(cairVoando(p, anim, 1.42, cx, cy));
        }
        yield 0.10;
        atualizarPlacar();
        derrubados = contarDerrubados();
        emPeDepois = contarPinosEmPe();
        total = pinosDerrubadosNoRound + derrubados;
      }

      if (derrubados > 0) {
        if (foiStrike) {
          if (ultimaTeclaJogada !== "Z" && ultimaTeclaJogada !== "B") som("batida");
          yield 0.03;
          som("strike");                // strike-1/2/3.wav
          contadorStrikesNoJogo++;
          mostrarBanner("STRIKE!", COR_STRIKE);
          yield* efeitoStrikeTotal();
        } else if (foiSpare) {
          som("batida");
          yield 0.03;
          som("combo");                 // spare.wav
          mostrarBanner("SPARE!", COR_SPARE);
          yield* efeitoSpareTotal();
        } else if (derrubados === 1) {
          som("acerto");                // song_ini.wav: um pino só
          mostrarBanner("ACERTO!", COR_ACERTO);
        } else {
          if (ultimaTeclaJogada !== "Z" && ultimaTeclaJogada !== "B") som("batida");
          mostrarBanner("ACERTO!", COR_ACERTO);
        }
      } else {
        som("erro");                    // erro.wav
        mostrarBanner("PRA FORA!", COR_MISS);
        efeitoMissTotal();
      }

      processandoImpacto = false;
      if (aguardandoFimBola) {
        aguardandoFimBola = false;
        jogandoTrajeto = false;
        yield* finalizarJogada();
        resetarBola();
        if (!transicaoRoundEmAndamento && !jogoFinalizado) aceitandoInput = true;
      }
    }

    function* tratarJogadaSemAlvoNaFaixa() {
      processandoImpacto = false;
      yield* passagemReta();
      som("erro");
      mostrarBanner("PRA FORA!", COR_MISS);
      efeitoMissTotal();
      if (aguardandoFimBola) {
        aguardandoFimBola = false;
        jogandoTrajeto = false;
        yield* finalizarJogada();
        resetarBola();
        if (!transicaoRoundEmAndamento && !jogoFinalizado) aceitandoInput = true;
      }
    }

    /* _on_bola_jogada_finalizada */
    function* aoBolaFinalizada() {
      if (processandoImpacto) {
        aguardandoFimBola = true;
        return;
      }
      jogandoTrajeto = false;
      yield* finalizarJogada();
      resetarBola();
      if (!transicaoRoundEmAndamento && !jogoFinalizado) aceitandoInput = true;
    }

    /* finalizar_jogada: conta os pinos e decide o round */
    function* finalizarJogada() {
      aceitandoInput = false;
      yield ESPERA_FISICA_S;
      const emPe = contarPinosEmPe();
      const derrubados = Math.max(0, pinosAntesDaJogada - emPe);
      pinosDerrubadosNoRound = Math.min(pinosDerrubadosNoRound + derrubados, 10);
      atualizarPlacar();
      atualizarStatus();
      atualizarMapaVisual();
      const foiStrike = derrubados === 10 && tentativaAtual === 1;
      let roundFechado = pinosDerrubadosNoRound >= 10;
      if ((bloquearSparePosC || bloquearSparePosLateralC) && tentativaAtual >= 2) roundFechado = false;
      if (foiStrike) {
        registrarResultadoRound(10, true, false);
        transicaoRoundEmAndamento = true;
        descartarJogadaPendente();
        yield ESPERA_STRIKE_S;
        yield* avancarRound();
        return;
      }
      if (roundFechado) {
        registrarResultadoRound(pinosDerrubadosNoRound, false, tentativaAtual >= 2);
        transicaoRoundEmAndamento = true;
        descartarJogadaPendente();
        yield ESPERA_ROUND_FECHADO_S;
        yield* avancarRound();
        return;
      }
      if (tentativaAtual < MAX_TENTATIVAS) {
        teclaAnteriorNoRound = ultimaTeclaJogada;
        tentativaAtual++;
        yield ESPERA_PROXIMA_TENTATIVA_S;
        atualizarStatus();
        atualizarHubPlay();
        atualizarPlacar();
        atualizarMapaVisual();
        aceitandoInput = true;
        return;
      }
      registrarResultadoRound(pinosDerrubadosNoRound, false, false);
      transicaoRoundEmAndamento = true;
      descartarJogadaPendente();
      yield ESPERA_FIM_DE_ROUND_S;
      yield* avancarRound();
    }

    function* avancarRound() {
      aceitandoInput = false;
      transicaoRoundEmAndamento = true;
      descartarJogadaPendente();
      ultimaTeclaJogada = "";
      processandoImpacto = false;
      aguardandoFimBola = false;
      teclaAnteriorNoRound = "";
      bloquearSparePosC = false;
      bloquearSparePosLateralC = false;
      lateralAnteriorParaC = "";
      roundAtual++;
      if (roundAtual > ROUNDS) {
        transicaoRoundEmAndamento = false;
        yield* finalizarJogo();
        return;
      }
      tentativaAtual = 1;
      pinosDerrubadosNoRound = 0;
      atualizarHubPlay();
      atualizarPlacar();
      atualizarMapaVisual();
      mostrarRoundBanner(roundAtual);
      yield 0.28;
      yield* animarMontagemRoundOuPlayer();
      atualizarStatus();
      atualizarHubPlay();
      atualizarPlacar();
      atualizarMapaVisual();
      descartarJogadaPendente();
      transicaoRoundEmAndamento = false;
      aceitandoInput = true;
    }

    // animar_montagem_round_ou_player: o rack velho some e o novo desce
    function* animarMontagemRoundOuPlayer() {
      aceitandoInput = false;
      for (const p of pins) motor.tween(p).prop(p, "mod:a", 0, 0.16);
      yield 0.18;
      criar10Pinos();
      for (const p of pins) {
        p.mod[3] = 0;
        p.introBase = p.pos.slice();
        p.pos[1] -= DESCIDA_MONTAGEM_PINOS;
      }
      yield* animarPinosEmCascata();
      resetarBola();
      yield* animarBolaEntrada();
    }

    // animar_pinos_em_cascata: a máquina baixa o rack, do fundo para a frente
    function* animarPinosEmCascata() {
      let ultimo = null;
      for (const fileira of [[7, 8, 9, 10], [4, 5, 6], [2, 3], [1]]) {
        for (const n of fileira) {
          const p = obterPino(n);
          if (!p) continue;
          const base = p.introBase || p.pos.slice();
          const tw = motor.tween(p).definirParalelo(true);
          tw.prop(p, "mod:a", 1, 0.16);
          tw.prop(p, "pos", base, 0.34).com(T.BOUNCE).suave(E.OUT);
          ultimo = tw;
          yield 0.03;
        }
        yield 0.07;
      }
      if (ultimo && !ultimo.morto) yield ultimo;
      for (const p of pins) {
        if (p.introBase) { p.pos[0] = p.introBase[0]; p.pos[1] = p.introBase[1]; }
        p.mod[3] = 1;
      }
    }

    // animar_bola_entrada: a bola volta para o lugar dela (abaixo da tela)
    function* animarBolaEntrada() {
      const base = bola.introBase || BOLA_INICIO;
      const tw = motor.tween().transicao(T.BACK).suavizar(E.OUT);
      tw.junto().prop(bola, "mod:a", 1, 0.20);
      tw.junto().prop(bola, "pos", base, 0.26);
      yield tw;
    }

    function* finalizarJogo() {
      jogoFinalizado = true;
      aceitandoInput = false;
      jogandoTrajeto = false;
      processandoImpacto = false;
      aguardandoFimBola = false;
      let total = 0;
      let strikes = 0;
      for (const item of historicoRounds) {
        total += item.derrubados;
        if (item.strike) strikes++;
      }
      valores.total = total;
      camadaPlacar.sujo = true;
      atualizarHubPlay();
      const recorde = salvarEObterRecorde(total, strikes);
      yield* sequenciaFimDeJogo(total, strikes, recorde);
    }

    function salvarEObterRecorde(total, strikes) {
      const CHAVE = "ls-dragon-bowling:recorde";
      let melhor = { best_total: 0, best_strikes: 0 };
      try { melhor = { ...melhor, ...JSON.parse(window.localStorage.getItem(CHAVE) || "{}") }; } catch (erro) { /* sem armazenamento */ }
      let novo = false;
      if (total > melhor.best_total) { melhor.best_total = total; novo = true; }
      if (strikes > melhor.best_strikes) { melhor.best_strikes = strikes; novo = true; }
      try { window.localStorage.setItem(CHAVE, JSON.stringify(melhor)); } catch (erro) { /* aba anônima */ }
      return { novo, ...melhor };
    }

    // _efeito_fim_de_jogo_visual: "FIM DE JOGO" com a marca da casa
    function* efeitoFimDeJogoVisual() {
      shakeCamera(6.0, 0.16, 10);
      final.visivel = true;
      final.bg = 0;
      final.botao.visivel = false;
      final.painel.mod[3] = 0;
      final.card.mod[3] = 0;
      final.recorde.mod[3] = 0;
      final.timer.mod[3] = 0;
      const t = final.titulo;
      t.texto = "FIM DE JOGO";
      t.estilo = { ...t.estilo, cor: [1.0, 0.42, 0.18], corContorno: [1.0, 0.86, 0.32], contorno: 5 };
      t.mod[0] = t.mod[1] = t.mod[2] = 1; t.mod[3] = 0;
      t.escala[0] = t.escala[1] = 1;
      t.pos[0] = TELA_W * 0.5 - t.tam[0] * 0.5;
      t.pos[1] = TELA_H * 0.5 - 110;
      const l = final.logo;
      l.tam[0] = 440; l.tam[1] = 165;
      l.pivo[0] = 220; l.pivo[1] = 82.5;
      l.mod[3] = 0;
      l.escala[0] = l.escala[1] = 0.72;
      l.pos[0] = TELA_W * 0.5 - 220;
      l.pos[1] = TELA_H * 0.5;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(final, "bg", 0.86, 0.12);
      tw.prop(t, "mod:a", 1, 0.10);
      tw.prop(l, "mod:a", 1, 0.14);
      tw.prop(l, "escala", [1.55, 1.55], 0.22);
      yield tw;
      // o brilho (modulate 1,08) e a volta: só o tempo deles
      yield 0.10;
      yield 0.12;
    }

    function* sequenciaFimDeJogo(total, strikes, recorde) {
      finalIntroEmAndamento = true;
      telaFinalAtiva = true;
      tempoRestanteTelaFinal = TEMPO_TELA_FINAL;
      animTelaFinalT = 0;
      yield* efeitoFimDeJogoVisual();
      som("fim");                       // end-game.wav
      yield ESPERA_SOM_FIM_DE_JOGO;
      yield* mostrarTelaFinal(total, strikes, recorde);
      finalIntroEmAndamento = false;
      yield ESPERA_ENTREGAR_RESULTADO;
      const rounds = Math.max(historicoRounds.length, 1);
      api.terminar({
        pontos: total,
        titulo: "Fim de jogo",
        detalhe: `${strikes} strike${strikes === 1 ? "" : "s"} · média ${(total / rounds).toFixed(1).replace(".", ",")} por round · eficiência ${Math.round((total / (rounds * 10)) * 100)}%`,
      });
    }

    function* mostrarTelaFinal(total, strikes, recorde) {
      telaFinalAtiva = true;
      tempoRestanteTelaFinal = TEMPO_TELA_FINAL;
      animTelaFinalT = 0;
      final.visivel = true;
      const l = final.logo;
      l.tam[0] = 280; l.tam[1] = 105;
      l.pivo[0] = 140; l.pivo[1] = 52.5;
      l.escala[0] = l.escala[1] = 1;
      l.pos[0] = PAINEL_FINAL.x + (PAINEL_FINAL.w - 280) * 0.5;
      l.pos[1] = PAINEL_FINAL.y + 115;
      const rounds = Math.max(historicoRounds.length, 1);
      const media = total / rounds;
      const eficiencia = Math.round((total / (rounds * 10)) * 100);
      const t = final.titulo;
      t.texto = "RESULTADO FINAL";
      t.estilo = arcade(52, COR_TEXTO_YELLOW);
      t.pos[0] = PAINEL_FINAL.x + 40;
      t.pos[1] = PAINEL_FINAL.y + 42;
      final.card.stats = `PINOS:  ${total}\nSTRIKES:  ${strikes}\nRODADAS:  ${rounds}\nMÉDIA:  ${media.toFixed(1)}\nEFICIÊNCIA:  ${eficiencia}%`;
      camadaCardFinal.sujo = true;
      if (recorde.novo) {
        final.recorde.texto = "\u{1F3C6}  NOVO RECORDE!";
        final.recorde.estilo = painel(29, COR_TEXTO_YELLOW, 5);
      } else {
        final.recorde.texto = `RECORDE  \u2022  PINOS: ${recorde.best_total}  \u2022  STRIKES: ${recorde.best_strikes}`;
        final.recorde.estilo = painel(24, COR_TEXTO_CYAN, 5);
      }
      final.timer.texto = `RETORNO EM: ${Math.ceil(tempoRestanteTelaFinal)}`;
      segundosMostrados = Math.ceil(tempoRestanteTelaFinal);
      final.bg = 0.86;
      final.painel.mod[3] = 0;
      t.mod[3] = 0;
      l.mod[3] = 0;
      final.recorde.mod[3] = 0;
      final.timer.mod[3] = 0;
      final.card.mod[3] = 0;
      final.card.escala[0] = final.card.escala[1] = 1;
      final.botao.visivel = false;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(final.painel, "mod:a", 1, 0.22);
      tw.prop(t, "mod:a", 1, 0.25);
      tw.prop(l, "mod:a", 1, 0.32);
      tw.prop(final.recorde, "mod:a", 1, 0.45);
      tw.prop(final.timer, "mod:a", 1, 0.52);
      tw.prop(final.card, "mod:a", 1, 0.38);
      tw.prop(final.card, "escala", [1.04, 1.04], 0.24).com(T.BACK).suave(E.OUT);
      yield tw;
      final.botao.visivel = true;
      final.botao.escala[0] = final.botao.escala[1] = 1;
      const idle = motor.tween().repetir(0);
      idle.prop(final.botao, "escala", [1.04, 1.04], 0.80).com(T.SINE).suave(E.IN_OUT);
      idle.prop(final.botao, "escala", [1, 1], 0.80).com(T.SINE).suave(E.IN_OUT);
    }

    /* A jogada guardada: o sensor que dispara com a pista ocupada não se perde. */
    function guardarJogadaPendente(tecla) {
      if (introEmAndamento || transicaoRoundEmAndamento || jogoFinalizado || telaFinalAtiva) return;
      if (relogio - ultimaJogadaEm < MESMA_BOLA_S) return;
      jogadaPendente = tecla;
      jogadaPendenteEm = relogio;
      jogadaPendenteRound = roundAtual;
    }

    function descartarJogadaPendente() {
      jogadaPendente = "";
      jogadaPendenteRound = -1;
    }

    function soltarJogadaPendente() {
      if (relogio - jogadaPendenteEm > VALIDADE_JOGADA_PENDENTE_S || jogoFinalizado || telaFinalAtiva) {
        descartarJogadaPendente();
        return;
      }
      if (jogadaPendenteRound !== roundAtual) { descartarJogadaPendente(); return; }
      if (introEmAndamento || !aceitandoInput || transicaoRoundEmAndamento || jogandoTrajeto) return;
      const tecla = jogadaPendente;
      descartarJogadaPendente();
      executarJogadaPorTecla(tecla);
    }

    /* _input: o sensor (ou a tecla) acionou */
    function sensor(tecla) {
      if (introEmAndamento || telaFinalAtiva || jogoFinalizado) return;
      if (!aceitandoInput || transicaoRoundEmAndamento || jogandoTrajeto) {
        guardarJogadaPendente(tecla);
        return;
      }
      executarJogadaPorTecla(tecla);
    }

    /* ------------------------------------------------------------------
       O COMEÇO DA PARTIDA (iniciar_jogo + preparar_intro_visual)
       ------------------------------------------------------------------ */
    function iniciarJogo() {
      motor.limpar();
      roundAtual = 1;
      tentativaAtual = 1;
      pinosDerrubadosNoRound = 0;
      pinosAntesDaJogada = 10;
      jogoFinalizado = false;
      historicoRounds = [];
      contadorStrikesNoJogo = 0;
      processandoImpacto = false;
      aguardandoFimBola = false;
      transicaoRoundEmAndamento = false;
      jogandoTrajeto = false;
      ultimaTeclaJogada = "";
      teclaAnteriorNoRound = "";
      bloquearSparePosC = false;
      bloquearSparePosLateralC = false;
      lateralAnteriorParaC = "";
      descartarJogadaPendente();
      ultimaJogadaEm = -100;
      telaFinalAtiva = false;
      finalIntroEmAndamento = false;
      relogio = 0;
      arrasto.ativo = false;
      for (const k in teclasPresas) teclasPresas[k] = false;

      camera.pos[0] = CAMERA_BASE[0]; camera.pos[1] = CAMERA_BASE[1];
      camera.offset[0] = camera.offset[1] = 0;
      camera.zoom[0] = camera.zoom[1] = 1;
      brilho.velocidade = BRILHO_VELOCIDADE;
      brilho.intensidade = BRILHO_INTENSIDADE;
      brilho.erro = 0;
      brilho.ativo = false;
      for (const f of listaFlashes) f.a = 0;
      final.visivel = false;
      final.bg = 0;
      final.botao.visivel = false;

      criar10Pinos();
      resetarBola();
      atualizarStatus();
      atualizarHubPlay();
      atualizarMapaVisual();
      valores.placarInfo = "";
      atualizarPlacar();

      // preparar_intro_visual: painéis apagados, pinos 120 px acima, bola embaixo
      for (const k of ["fundo", "placar", "status", "play", "mapa"]) {
        hud[k].mod[3] = 0;
        hud[k].escala[0] = hud[k].escala[1] = 1;
      }
      hud.mapa.pos[0] = 716; hud.mapa.pos[1] = 382;
      hud.play.pos[0] = 710; hud.play.pos[1] = 12;
      hud.fundo.pos[0] = 28; hud.fundo.pos[1] = 4;
      hud.placar.pos[0] = 42; hud.placar.pos[1] = 12;
      hud.status.pos[0] = 54; hud.status.pos[1] = 168;
      hud.flashPlay.mod[3] = 0;
      roundLabel.mod[3] = 0;
      bannerLabel.mod[3] = 0;
      for (const p of pins) {
        p.introBase = p.pos.slice();
        p.pos[1] -= DESCIDA_MONTAGEM_PINOS;
        p.mod[3] = 0;
      }
      bola.introBase = BOLA_INICIO.slice();
      bola.pos[1] = BOLA_INICIO[1] + 85;
      bola.mod[3] = 0;
      bola.visivel = true;

      introEmAndamento = true;
      aceitandoInput = false;
      introPendente = true;
    }

    // animar_intro_partida: a HUD entra, o rack desce e aparece o ROUND 1
    function* animarIntroPartida() {
      introEmAndamento = true;
      aceitandoInput = false;
      const tw = motor.tween().definirParalelo(true);
      tw.prop(hud.fundo, "pos", [28, 4], 0.78).com(T.CUBIC).suave(E.OUT);
      tw.prop(hud.fundo, "mod:a", 1, 0.42).com(T.SINE).suave(E.OUT);
      tw.prop(hud.placar, "pos", [42, 12], 0.82).com(T.BACK).suave(E.OUT);
      tw.prop(hud.placar, "escala", [1, 1], 0.82).com(T.BACK).suave(E.OUT);
      tw.prop(hud.placar, "mod:a", 1, 0.42).com(T.SINE).suave(E.OUT);
      tw.prop(hud.status, "pos", [54, 170], 0.86).com(T.BACK).suave(E.OUT);
      tw.prop(hud.status, "escala", [1, 1], 0.86).com(T.BACK).suave(E.OUT);
      tw.prop(hud.status, "mod:a", 1, 0.46).com(T.SINE).suave(E.OUT);
      tw.prop(hud.mapa, "pos", [738, 382], 0.72).com(T.CUBIC).suave(E.OUT);
      tw.prop(hud.mapa, "mod:a", 1, 0.40).com(T.SINE).suave(E.OUT);
      tw.prop(hud.play, "pos", [710, 12], 0.78).com(T.CUBIC).suave(E.OUT);
      tw.prop(hud.play, "mod:a", 1, 0.44).com(T.SINE).suave(E.OUT);
      tw.prop(camera, "zoom", [1, 1], 0.90).com(T.SINE).suave(E.OUT);
      yield tw;
      yield* animarPinosEmCascata();
      yield* animarBolaEntrada();
      motor.correr(mostrarRoundBannerIntro(1));
      descartarJogadaPendente();
      introEmAndamento = false;
      aceitandoInput = true;
    }

    /* ------------------------------------------------------------------
       O ARRASTO E AS TECLAS
       ------------------------------------------------------------------ */
    const arrasto = { ativo: false, id: null, x0: 0, y0: 0, x: 0, y: 0, cruzouX: NaN, hx: new Float64Array(12), hy: new Float64Array(12), ht: new Float64Array(12), n: 0 };
    const teclasPresas = {};

    function podeArrastar() {
      return !introEmAndamento && !transicaoRoundEmAndamento && !jogoFinalizado && !telaFinalAtiva;
    }

    function amostrar(x, y) {
      const i = arrasto.n % 12;
      arrasto.hx[i] = x;
      arrasto.hy[i] = y;
      arrasto.ht[i] = performance.now();
      arrasto.n++;
    }

    // A tecla da faixa: a largura da pista na linha dos sensores, em 5 partes.
    function teclaNoX(x) {
      const meia = meiaLarguraPista(LINHA_DOS_SENSORES);
      const esquerda = BOLA_INICIO[0] - meia;
      const i = Math.floor((x - esquerda) / (meia * 2 / 5));
      return TECLAS_DOS_SENSORES[lim(i, 0, 4)];
    }

    function soltarArrasto() {
      const a = arrasto;
      a.ativo = false;
      if (a.y0 - a.y < ARRASTO_MINIMO) return;     // toque ou gesto para baixo: não joga
      let x = a.cruzouX;
      if (Number.isNaN(x)) {
        // o gesto dos últimos ~90 ms (ou o arrasto todo) prolongado até a linha
        const agora = performance.now();
        let vx = a.x - a.x0;
        let vy = a.y - a.y0;
        for (let k = 1; k <= Math.min(a.n, 12); k++) {
          const i = (a.n - k) % 12;
          if (agora - a.ht[i] > 90) {
            if (a.y - a.hy[i] < -8) { vx = a.x - a.hx[i]; vy = a.y - a.hy[i]; }
            break;
          }
        }
        x = a.y > LINHA_DOS_SENSORES && vy < 0 ? a.x + (vx / vy) * (LINHA_DOS_SENSORES - a.y) : a.x;
      }
      sensor(teclaNoX(x));
    }

    /* ------------------------------------------------------------------
       DESENHO
       ------------------------------------------------------------------ */
    let escalaAtual = 0;
    let pistaPronta = null;
    /* O console continua desenhando atrás da capa, da contagem e da tela de
       fim sem chamar atualizar: nada muda. O segundo quadro igual vira uma
       foto, e dali em diante só a foto é copiada (uma cópia, e não a pista,
       o brilho e a HUD de novo). */
    let atualizouDesdeODesenho = true;
    let foto = null;
    let fotoValida = false;
    let pistaDispositivo = { x: 0, y: 0 };

    function prepararPista(escala) {
      if (!img.pista) return;
      const rx = SX * escala;
      const ry = SY * escala;
      const x0 = PISTA.x * rx;
      const y0 = PISTA.y * ry;
      const ix = Math.floor(x0);
      const iy = Math.floor(y0);
      const w = Math.ceil(x0 + PISTA.w * rx) - ix;
      const h = Math.ceil(y0 + PISTA.h * ry) - iy;
      if (!pistaPronta) pistaPronta = novaTela(w, h);
      else { pistaPronta.width = w; pistaPronta.height = h; }
      const g = pistaPronta.getContext("2d");
      g.imageSmoothingQuality = "high";
      g.drawImage(img.pista, x0 - ix, y0 - iy, PISTA.w * rx, PISTA.h * ry);
      pistaDispositivo = { x: ix, y: iy };
    }

    function cameraParada() {
      return camera.zoom[0] === 1 && camera.zoom[1] === 1 && camera.offset[0] === 0 && camera.offset[1] === 0 &&
        camera.pos[0] === CAMERA_BASE[0] && camera.pos[1] === CAMERA_BASE[1];
    }

    // O mundo (pista, pinos, bola) passa pela câmera: tela = (mundo - câmera) / zoom + centro.
    let mundoA = SX;
    let mundoD = SY;
    let mundoE = 0;
    let mundoF = 0;

    function calcularMundo() {
      const zx = 1 / camera.zoom[0];
      const zy = 1 / camera.zoom[1];
      mundoA = SX * zx;
      mundoD = SY * zy;
      mundoE = SX * (CAMERA_BASE[0] - (camera.pos[0] + camera.offset[0]) * zx);
      mundoF = SY * (CAMERA_BASE[1] - (camera.pos[1] + camera.offset[1]) * zy);
    }

    function transformarNoMundo(ctx, x, y, rotGraus, ex, ey) {
      const r = rotGraus * Math.PI / 180;
      const c = Math.cos(r);
      const s = Math.sin(r);
      ctx.setTransform(mundoA * c * ex, mundoD * s * ex, -mundoA * s * ey, mundoD * c * ey, mundoA * x + mundoE, mundoD * y + mundoF);
    }

    function desenharPista(ctx, escala) {
      const qualidade = ctx.imageSmoothingQuality;
      // o brilho é macio: a ampliação simples basta (a "alta" custa o dobro sem placa de vídeo)
      ctx.imageSmoothingQuality = "low";
      if (cameraParada() && pistaPronta) {
        ctx.setTransform(1 / escala, 0, 0, 1 / escala, 0, 0);
        ctx.drawImage(pistaPronta, pistaDispositivo.x, pistaDispositivo.y);
      } else if (pistaPronta) {
        // câmera tremendo ou com zoom: a mesma pista pronta, pela câmera
        const rx = SX * escala;
        const ry = SY * escala;
        ctx.setTransform(mundoA / rx, 0, 0, mundoD / ry, mundoA * (pistaDispositivo.x / rx) + mundoE, mundoD * (pistaDispositivo.y / ry) + mundoF);
        ctx.drawImage(pistaPronta, 0, 0);
      } else if (img.pista) {
        ctx.setTransform(mundoA, 0, 0, mundoD, mundoE, mundoF);
        ctx.drawImage(img.pista, PISTA.x, PISTA.y, PISTA.w, PISTA.h);
      } else {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = "#0b1a44";
        ctx.fillRect(0, 0, LARGURA, ALTURA);
      }
      if (!telas) { ctx.imageSmoothingQuality = qualidade; return; }
      // o brilho, calculado na tela pequena e somado à pista
      const t = telas;
      const ga = t.ga;
      ga.globalCompositeOperation = "copy";
      ga.drawImage(t.faixa, 0, -(1 - brilho.fSobe) * PERIODO_FAIXA);
      ga.globalCompositeOperation = "multiply";
      ga.drawImage(t.ciano, 0, 0);
      const gb = t.gb;
      gb.globalCompositeOperation = "copy";
      gb.drawImage(t.ondaP, 0, -(brilho.fPulso / TAU) * PERIODO_P);
      gb.globalCompositeOperation = "multiply";
      gb.drawImage(t.ondaQ, -(brilho.fOuro / TAU) * PERIODO_Q, 0, t.ondaQ.width, MASCARA_H);
      gb.drawImage(t.ouro, 0, 0);
      ga.globalCompositeOperation = "lighter";
      ga.globalAlpha = BRILHO_INTENSIDADE * 0.45;
      ga.drawImage(t.b, 0, 0);
      ga.globalAlpha = 1;
      ctx.setTransform(mundoA, 0, 0, mundoD, mundoE, mundoF);
      const erro = brilho.erro;
      if (erro > 0.001) {
        ctx.globalCompositeOperation = "multiply";
        ctx.globalAlpha = erro;
        aplicarNaPista(ctx, t.escurecer);
      }
      ctx.globalCompositeOperation = "lighter";
      if (erro < 0.999) {
        ctx.globalAlpha = 1 - erro;
        aplicarNaPista(ctx, t.a);
      }
      if (erro > 0.001) {
        const gc = t.gc;
        gc.globalCompositeOperation = "copy";
        gc.drawImage(t.faixaErro, 0, -(1 - brilho.fSobe) * PERIODO_FAIXA);
        gc.globalCompositeOperation = "multiply";
        gc.drawImage(t.vermelho, 0, 0);
        let forca = 2.2 * brilho.intensidade * erro;
        while (forca > 0.001) {
          ctx.globalAlpha = Math.min(1, forca);
          aplicarNaPista(ctx, t.c);
          forca -= 1;
        }
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
      ctx.imageSmoothingQuality = qualidade;
    }

    function desenharPino(ctx, p) {
      const a = p.mod[3] * p.sprMod[3];
      if (a <= 0.003 || !img.pino) return;
      transformarNoMundo(ctx, p.pos[0] + p.sprPos[0], p.pos[1] + p.sprPos[1], p.sprRot, p.sprEscala[0], p.sprEscala[1]);
      ctx.globalAlpha = lim(a, 0, 1);
      ctx.drawImage(img.pino, -REF_IDLE_W / 2, -REF_IDLE_H / 2, REF_IDLE_W, REF_IDLE_H);
      // modulate acima de 1 (o clarão) clareia: a mesma figura somada por cima
      const claro = (p.sprMod[0] + p.sprMod[1] + p.sprMod[2]) / 3 - 1;
      if (claro > 0.01) {
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = lim(a * claro, 0, 1);
        ctx.drawImage(img.pino, -REF_IDLE_W / 2, -REF_IDLE_H / 2, REF_IDLE_W, REF_IDLE_H);
        ctx.globalCompositeOperation = "source-over";
      }
    }

    function desenharBola(ctx) {
      if (!bola.visivel || bola.mod[3] <= 0.003 || !img.bola) return;
      const metadeAltura = BOLA.celH * 0.5 * bola.escala[1];
      if (bola.pos[1] - metadeAltura > TELA_H + 40) return;
      const quadro = bola.rolando ? Math.floor(bola.tempoAnim * BOLA.fps) % BOLA.quadros : 0;
      desenharSpriteBola(ctx, bola.pos[0], bola.pos[1], bola.rot, bola.escala[0], quadro, bola.mod[3]);
    }

    function desenharSpriteBola(ctx, x, y, rot, escala, quadro, alfa) {
      transformarNoMundo(ctx, x, y, rot, escala, escala);
      ctx.globalAlpha = lim(alfa, 0, 1);
      ctx.drawImage(img.bola, (quadro % 4) * BOLA.celW, Math.floor(quadro / 4) * BOLA.celH, BOLA.celW, BOLA.celH,
        -BOLA.celW / 2, -BOLA.celH / 2, BOLA.celW, BOLA.celH);
    }

    // os números dos pinos (Label do pino.tscn, z 1000: por cima de tudo no mundo)
    const numerosProntos = [];
    let numerosEscala = 0;
    let numerosFontes = false;
    function prepararNumeros(escala) {
      if (numerosEscala === escala && numerosFontes === fontesProntas && numerosProntos.length) return;
      numerosEscala = escala;
      numerosFontes = fontesProntas;
      const rx = SX * escala * 1.15;
      const ry = SY * escala * 1.15;
      for (let n = 1; n <= 10; n++) {
        const c = numerosProntos[n] || novaTela(1, 1);
        c.width = Math.ceil((ROTULO_PINO_W + 16) * rx);
        c.height = Math.ceil((ROTULO_PINO_H + 16) * ry);
        const g = c.getContext("2d");
        g.setTransform(rx, 0, 0, ry, 8 * rx, 8 * ry);
        escrever(g, String(n), 0, 0, ROTULO_PINO_W, ROTULO_PINO_H,
          estiloTexto(FONTE_PADRAO, 24, [1.0, 0.97, 0.35], 5, { corContorno: [0.05, 0.05, 0.10] }));
        numerosProntos[n] = c;
      }
    }

    function desenharNumero(ctx, p) {
      if (!p.rotVisivel) return;
      const a = p.mod[3] * p.rotMod[3];
      if (a <= 0.003) return;
      const c = numerosProntos[p.numero];
      if (!c) return;
      const x = p.pos[0] + p.rotPos[0];
      const y = p.pos[1] + p.rotPos[1];
      ctx.setTransform(mundoA * p.rotEscala[0], 0, 0, mundoD * p.rotEscala[1], mundoA * x + mundoE, mundoD * y + mundoF);
      ctx.globalAlpha = lim(a, 0, 1);
      ctx.drawImage(c, -8, -8, ROTULO_PINO_W + 16, ROTULO_PINO_H + 16);
    }

    function desenharCamadaHud(ctx, c, no, escala) {
      const a = no.mod[3];
      if (a <= 0.003 || !c.tela) return;
      ctx.globalAlpha = lim(a, 0, 1);
      if (no.escala[0] === 1 && no.escala[1] === 1) {
        // sem escala: cópia pixel a pixel, presa à grade do aparelho (sem reamostrar)
        ctx.setTransform(1 / escala, 0, 0, 1 / escala, 0, 0);
        ctx.drawImage(c.tela, Math.round((no.pos[0] - c.margem) * SX * escala), Math.round((no.pos[1] - c.margem) * SY * escala));
        return;
      }
      // rect_scale sem pivô: cresce do canto de cima
      ctx.setTransform(SX * no.escala[0], 0, 0, SY * no.escala[1], SX * no.pos[0], SY * no.pos[1]);
      desenharCamada(ctx, c, 0, 0);
    }

    // as três 🎳 do PLAY, prontas nas quatro cores do atualizar_hub_play
    let bolasProntas = null;
    function prepararBolasPlay() {
      if (bolasProntas || !emojisImg) return;
      bolasProntas = ESTADOS_BOLA.map((cor) => {
        const c = novaTela(EMOJI_CEL_W, EMOJI_CEL_H);
        const g = c.getContext("2d");
        g.drawImage(emojisImg, 0, 0, EMOJI_CEL_W, EMOJI_CEL_H, 0, 0, EMOJI_CEL_W, EMOJI_CEL_H);
        if (cor[0] < 1 || cor[1] < 1 || cor[2] < 1) {
          g.globalCompositeOperation = "multiply";
          g.fillStyle = css(cor.slice(0, 3));
          g.fillRect(0, 0, c.width, c.height);
          g.globalCompositeOperation = "destination-in";
          g.drawImage(emojisImg, 0, 0, EMOJI_CEL_W, EMOJI_CEL_H, 0, 0, EMOJI_CEL_W, EMOJI_CEL_H);
        }
        return c;
      });
    }

    function desenharBolasPlay(ctx) {
      const no = hud.play;
      if (no.mod[3] <= 0.003 || !bolasProntas) return;
      // Label 72 x 72 com a 🎳 no tamanho 44 sobre a linha de base da fonte padrão
      const S = 44;
      const met = METRICAS[FONTE_PADRAO];
      const asc = Math.ceil(met.asc * S);
      const alt = asc + Math.ceil(met.desc * S);
      const base = Math.floor((72 - alt) / 2) + asc;
      const w = S * EMOJI_LARGURA;
      const h = S * EMOJI_ALTURA;
      for (let i = 0; i < 3; i++) {
        const b = hud.bolas[i];
        const lx = no.pos[0] + POSICOES_BOLAS_PLAY[i] - 36;
        const ly = no.pos[1] + 112;
        ctx.setTransform(SX * b.escala[0], 0, 0, SY * b.escala[1], SX * lx, SY * ly);
        ctx.globalAlpha = no.mod[3] * ESTADOS_BOLA[b.estado][3];
        ctx.drawImage(bolasProntas[b.estado], Math.floor((72 - w) / 2), base - S * EMOJI_TOPO, w, h);
      }
      const f = hud.flashPlay.mod[3];
      if (f > 0.003) {
        ctx.setTransform(SX, 0, 0, SY, SX * no.pos[0], SY * no.pos[1]);
        ctx.globalAlpha = f * no.mod[3];
        ctx.fillStyle = "rgb(255,217,64)";
        ctx.fillRect(0, 0, 304, 210);
      }
      ctx.globalAlpha = 1;
    }

    function desenharTelaFinal(ctx, escala) {
      if (!final.visivel) return;
      if (final.bg > 0.003) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.globalAlpha = lim(final.bg, 0, 1);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, LARGURA, ALTURA);
      }
      if (final.painel.mod[3] > 0.003) {
        prepararCamada(camadaPainelFinal, escala);
        prepararCamada(camadaCardFinal, escala);
        ctx.setTransform(SX, 0, 0, SY, 0, 0);
        ctx.globalAlpha = lim(final.painel.mod[3], 0, 1);
        desenharCamada(ctx, camadaPainelFinal, PAINEL_FINAL.x, PAINEL_FINAL.y);
        const card = final.card;
        if (card.mod[3] > 0.003) {
          ctx.setTransform(SX * card.escala[0], 0, 0, SY * card.escala[1], SX * card.pos[0], SY * card.pos[1]);
          ctx.globalAlpha = lim(final.painel.mod[3] * card.mod[3], 0, 1);
          desenharCamada(ctx, camadaCardFinal, 0, 0);
        }
      }
      ctx.globalAlpha = 1;
      desenharRotulo(ctx, final.titulo, escala);
      const l = final.logo;
      if (l.mod[3] > 0.003 && img.logo) {
        // TextureRect "manter proporção, centrado"
        const prop = img.logo.naturalWidth / img.logo.naturalHeight;
        let w = l.tam[0];
        let h = w / prop;
        if (h > l.tam[1]) { h = l.tam[1]; w = h * prop; }
        const px = l.pos[0] + l.pivo[0];
        const py = l.pos[1] + l.pivo[1];
        ctx.setTransform(SX * l.escala[0], 0, 0, SY * l.escala[1], SX * px, SY * py);
        ctx.globalAlpha = lim(l.mod[3], 0, 1);
        ctx.drawImage(img.logo, (l.tam[0] - w) / 2 - l.pivo[0], (l.tam[1] - h) / 2 - l.pivo[1], w, h);
        ctx.globalAlpha = 1;
      }
      desenharRotulo(ctx, final.recorde, escala);
      desenharRotulo(ctx, final.timer, escala);
      if (final.botao.visivel) {
        prepararCamada(camadaBotaoFinal, escala);
        const bx = PAINEL_FINAL.x + (PAINEL_FINAL.w - BOTAO_FINAL.w) * 0.5;
        const by = PAINEL_FINAL.y + 668;
        const e = final.botao.escala[0];
        const cx = bx + BOTAO_FINAL.w / 2;
        const cy = by + BOTAO_FINAL.h / 2;
        ctx.setTransform(SX * e, 0, 0, SY * e, SX * (cx - BOTAO_FINAL.w / 2 * e), SY * (cy - BOTAO_FINAL.h / 2 * e));
        desenharCamada(ctx, camadaBotaoFinal, 0, 0);
      }
    }

    function desenharFlashes(ctx) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      for (let i = 0; i < listaFlashes.length; i++) {
        const f = listaFlashes[i];
        if (f.a <= 0.003) continue;
        ctx.globalAlpha = lim(f.a, 0, 1);
        ctx.fillStyle = f.cor;
        ctx.fillRect(0, 0, LARGURA, ALTURA);
      }
      ctx.globalAlpha = 1;
    }

    /* ------------------------------------------------------------------
       A PARTIDA PARA O CONSOLE
       ------------------------------------------------------------------ */
    telas = prepararBrilho();
    iniciarJogo();

    return {
      iniciar() {
        iniciarJogo();
        fotoValida = false;
        atualizouDesdeODesenho = true;
      },

      atualizar(dt) {
        if (destruido) return;
        atualizouDesdeODesenho = true;
        relogio += dt;
        // 1. idle_frame
        motor.passoQuadros();
        if (introPendente) {
          introPendente = false;
          motor.correr(animarIntroPartida());
        }
        // 2. os nós: a bola, os pinos e o _process do jogo
        processarBola(dt);
        for (let i = 0; i < pins.length; i++) simularEmpurrao(pins[i], dt);
        avancarBrilho(dt);
        if (telaFinalAtiva) {
          animTelaFinalT += dt;
          if (!finalIntroEmAndamento) {
            final.titulo.escala[0] = final.titulo.escala[1] = 1 + Math.sin(animTelaFinalT * 3.8) * 0.015;
            tempoRestanteTelaFinal = Math.max(0, tempoRestanteTelaFinal - dt);
            const segundos = Math.ceil(tempoRestanteTelaFinal);
            if (segundos !== segundosMostrados) {
              segundosMostrados = segundos;
              final.timer.texto = `RETORNO EM: ${segundos}`;
            }
          }
        } else {
          if (jogadaPendente) soltarJogadaPendente();
          tempoHudAcc += dt;
          if (hudSujo && tempoHudAcc >= 0.05) {
            tempoHudAcc = 0;
            hudSujo = false;
            atualizarPlacar();
          }
        }
        // 3. os timers e 4. os tweens
        motor.passoTimers(dt);
        motor.passoTweens(dt);
      },

      desenhar(ctx) {
        const escala = ctx.canvas.width / LARGURA;
        if (!atualizouDesdeODesenho && fotoValida && escala === escalaAtual) {
          ctx.setTransform(1 / escala, 0, 0, 1 / escala, 0, 0);
          ctx.drawImage(foto, 0, 0);
          ctx.setTransform(1, 0, 0, 1, 0, 0);
          return;
        }
        // pinos, bola e letras em reamostragem média (com mipmap): a "alta"
        // do console é bicúbica e pesa no celular sem placa de vídeo
        const qualidade = ctx.imageSmoothingQuality;
        ctx.imageSmoothingQuality = "medium";
        if (escala !== escalaAtual) {
          escalaAtual = escala;
          prepararPista(escala);
          sujarTudo();
        }
        for (let i = 0; i < camadas.length; i++) prepararCamada(camadas[i], escala);
        prepararNumeros(escala);
        prepararBolasPlay();
        calcularMundo();

        // o mundo: pista, pinos e bola pela ordem de z
        desenharPista(ctx, escala);
        let bolaDesenhada = false;
        for (let i = 0; i < pinsPorZ.length; i++) {
          const p = pinsPorZ[i];
          if (!bolaDesenhada && bola.z < p.z) { desenharBola(ctx); bolaDesenhada = true; }
          desenharPino(ctx, p);
        }
        if (!bolaDesenhada) desenharBola(ctx);
        // a bola de mão do simulador: parada embaixo na vez de jogar, e no dedo
        if (arrasto.ativo) {
          desenharSpriteBola(ctx, arrasto.x, arrasto.y, 0, BOLA.escalaPerto, 0, 1);
        } else if (aceitandoInput && !jogandoTrajeto && !introEmAndamento && !transicaoRoundEmAndamento && !jogoFinalizado) {
          desenharSpriteBola(ctx, BOLA_DE_MAO[0], BOLA_DE_MAO[1], 0, BOLA.escalaPerto, 0, 0.92);
        }
        for (let i = 0; i < pinsPorZ.length; i++) desenharNumero(ctx, pinsPorZ[i]);
        ctx.globalAlpha = 1;

        // a HUD (CanvasLayer): fundo (z -20), status (z -5), mapa, placar, play
        desenharCamadaHud(ctx, camadaFundo, hud.fundo, escala);
        desenharCamadaHud(ctx, camadaStatus, hud.status, escala);
        desenharCamadaHud(ctx, camadaMapa, hud.mapa, escala);
        desenharCamadaHud(ctx, camadaPlacar, hud.placar, escala);
        desenharCamadaHud(ctx, camadaPlay, hud.play, escala);
        desenharBolasPlay(ctx);
        desenharRotulo(ctx, roundLabel, escala);
        desenharRotulo(ctx, bannerLabel, escala);
        desenharFlashes(ctx);
        desenharTelaFinal(ctx, escala);

        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "source-over";
        ctx.imageSmoothingQuality = qualidade;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        if (!atualizouDesdeODesenho) {
          if (!foto) foto = novaTela(ctx.canvas.width, ctx.canvas.height);
          else if (foto.width !== ctx.canvas.width || foto.height !== ctx.canvas.height) {
            foto.width = ctx.canvas.width;
            foto.height = ctx.canvas.height;
          }
          const gf = foto.getContext("2d");
          gf.globalCompositeOperation = "copy";
          gf.drawImage(ctx.canvas, 0, 0);
          fotoValida = true;
        } else fotoValida = false;
        atualizouDesdeODesenho = false;
      },

      apertar(x, y, id) {
        if (!podeArrastar() || arrasto.ativo) return;
        const gx = x / SX;
        const gy = y / SY;
        if (gy < INICIO_DO_ARRASTO) return;
        arrasto.ativo = true;
        arrasto.id = id;
        arrasto.x0 = arrasto.x = gx;
        arrasto.y0 = arrasto.y = gy;
        arrasto.cruzouX = NaN;
        arrasto.n = 0;
        amostrar(gx, gy);
      },

      mover(x, y, id) {
        if (!arrasto.ativo || (id !== undefined && id !== arrasto.id)) return;
        const gx = x / SX;
        const gy = y / SY;
        if (arrasto.y > LINHA_DOS_SENSORES && gy <= LINHA_DOS_SENSORES) {
          // cruzou a linha dos sensores subindo: é ali que a bola passa
          const t = (arrasto.y - LINHA_DOS_SENSORES) / (arrasto.y - gy);
          arrasto.cruzouX = mistura(arrasto.x, gx, t);
        }
        arrasto.x = gx;
        arrasto.y = gy;
        amostrar(gx, gy);
      },

      soltar(x, y, id) {
        if (!arrasto.ativo || (id !== undefined && id !== arrasto.id)) return;
        this.mover(x, y, id);
        if (!podeArrastar()) { arrasto.ativo = false; return; }
        soltarArrasto();
      },

      tecla(codigo, apertada) {
        const tecla = TECLAS[codigo];
        if (!tecla) return;
        if (!apertada) { teclasPresas[codigo] = false; return; }
        if (teclasPresas[codigo]) return;   // cada aperto é um clique: segurar não repete
        teclasPresas[codigo] = true;
        sensor(tecla);
      },

      destruir() {
        destruido = true;
        motor.limpar();
      },

      /** Só para os testes automáticos: o estado da partida agora. */
      depurar() {
        return {
          round: roundAtual, tentativa: tentativaAtual, emPe: contarPinosEmPe(), derrubadosNoRound: pinosDerrubadosNoRound,
          total: totalPinosDerrubadosPartida(), aceitando: aceitandoInput, intro: introEmAndamento,
          finalizado: jogoFinalizado, telaFinal: telaFinalAtiva, banner: bannerLabel.mod[3] > 0.05 ? bannerLabel.texto : "",
          historico: historicoRounds.map((h) => ({ ...h })), pinosEmPe: pins.filter((p) => !p.derrubado).map((p) => p.numero),
          teclaNoX: (x) => teclaNoX(x), ultimaTecla: ultimaTeclaJogada,
        };
      },
    };
  },
};
