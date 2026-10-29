/* ======================================================================
   CRAQUE DE BOTÃO — a miniatura do futebol de mesa da Lazer & Sport.

   A mesa, as medidas, a física e as regras vêm do jogo da máquina
   (Godot: scripts/campo.gd, corpo.gd, fisica.gd, ia.gd, partida.gd).
   Tudo acontece nas medidas da MESA ORIGINAL (1280 x 720) e só o desenho
   é reduzido para a tela lógica (960 x 540): assim os números do jogo de
   verdade -- raio do botão, atrito, força do peteleco, tamanho do gol --
   valem aqui sem conversão, e a sensação na mão é a mesma.

   COMO SE JOGA (você é o Brasil, a máquina é a Argentina):
     * Na sua vez, arraste a partir de um botão amarelo PARA TRÁS e solte:
       é um estilingue. Quanto mais longe puxar, mais forte o peteleco.
       Voltar com o dedo para cima do botão e soltar = desistir.
     * Teclado, como o manche da máquina: ↑/↓ troca o botão, ←/→ gira a
       seta, SEGURE espaço (a barra sobe e desce) e solte na força certa.
       Na vez da máquina, ↑/↓ mexe o seu goleiro.

   REGRAS COPIADAS DA MÁQUINA:
     * Cada vez, um botão joga. Tocou na bola: joga de novo, até 3 toques.
       Não tocou: a vez passa. Relógio da vez (aqui 15 s; na máquina 20).
     * Acertou um botão rival SEM tocar na bola: FALTA. Batida forte =
       amarelo; muito forte (ou reincidente) = vermelho e o botão sai.
       Falta dentro da própria área = PÊNALTI.
     * Bola pela lateral = LATERAL; pela linha de fundo = ESCANTEIO (se o
       defensor tocou por último) ou TIRO DE META.
     * Goleiro "caixinha": fica parado no lance e se posiciona sozinho
       entre a bola e o gol na vez de jogar.
     * Gol quando o centro da bola passa a linha entre as traves. Quem
       marca fica EMBALADO (chute mais forte por 40 s); saída de bola para
       quem tomou.
   MINIATURA: um tempo de 2 minutos, ou quem fizer 3 gols primeiro.
   PONTOS: 100 por gol seu + 300 pela vitória (100 pelo empate) + 5 por
   segundo que sobrou quando a vitória vem pelos 3 gols antes do apito.

   api.variante === "demo": máquina contra máquina (vitrine e testes).
   ====================================================================== */

const TAU = Math.PI * 2;
const GRAU = Math.PI / 180;
const K = 0.75;                     // mesa (1280 x 720) -> tela lógica (960 x 540)

/* ---------- a mesa (campo.gd) ---------- */
const MURO = { x0: 96, y0: 88, x1: 1184, y1: 702 };      // placas: ninguém passa
const CAMPO = { x0: 140, y0: 110, x1: 1140, y1: 680 };   // linhas do campo
const CX = 640, CY = 395;                                 // centro do campo
const GOL_MEIA = 78, GOL_FUNDO = 38;
const AREA_P = 172, AREA_MEIA = 192, AREA_G = 64, MARCA_PEN = 114;
const RAIO_BOTAO = 31, RAIO_BOLA = 9, GOLEIRO_RAIO = 10, RAIO_TRAVE = 4;
// saída: 2 zagueiros, 2 meias, 2 atacantes (frações do campo do time da esquerda)
const FORMACAO = [[0.14, 0.30], [0.14, 0.70], [0.30, 0.22], [0.30, 0.78], [0.43, 0.38], [0.43, 0.62]];
const NUMEROS = [3, 4, 6, 8, 10, 9];

/* ---------- física e regras (fisica.gd, ia.gd, partida.gd) ---------- */
const VMAX = 1150, VMIN = 90;
const ATRITO_BOTAO = 700, ATRITO_BOLA = 260, AMORTECE_BOLA = 0.35;
const GANHO_BOLA = 1.335;           // (1 + e) * m_botão / (m_botão + m_bola)
const SUBPASSOS_MAX = 6, PASSO_MAX = 5, PARADO = 5;
const AMARELO_V = 430, VERMELHO_V = 930;
const TOQUES = 3;
const LATERAL_DENTRO = 40;
const DIFICULDADE = 1;              // 0 fácil, 1 médio (o padrão da máquina), 2 difícil
// Na máquina cada um tem o seu manche; aqui o jogador mira com o dedo numa
// mesa pequena, então a CPU erra um pouco mais que o "médio" do original.
const ERRO_MINI = 1.4;

/* ---------- da miniatura ---------- */
const DURACAO = 90;               // um tempo só, de 90 s (ou até alguém fazer 3 gols)
const GOLS_VITORIA = 3;
const RELOGIO_VEZ = 15;
const EMBALO_S = 40;
// o original pega o botão a 1,9 raio do dedo; no celular a mesa fica
// pequena, então o alcance é um pouco maior
const TOQUE_ALCANCE = 2.2;
const PUXAO_MAX = 150;              // puxar isso (px da mesa) = força máxima
const PUXAO_MIN = RAIO_BOTAO * 0.55; // soltou mais perto que isso = desistiu

const BOLA = 0, BOTAO = 1, GOLEIRO = 2;

// dados/times.json (uniforme 1 de cada seleção)
const TIMES = [
  { sigla: "BRA", nome: "BRASIL", chute: 92, controle: 94, defesa: 86, camisa: "#FFD200",
    torcida: ["#FFD200", "#009C3B"], botao: "botaoBra", goleiro: "goleiroBra", bandeira: "bandeiraBra" },
  { sigla: "ARG", nome: "ARGENTINA", chute: 91, controle: 93, defesa: 88, camisa: "#75AADB",
    torcida: ["#75AADB", "#FFFFFF"], botao: "botaoArg", goleiro: "goleiroArg", bandeira: "bandeiraArg" },
];
// faixa de aviso na cor do time (camisa escurecida, como _cor_banner)
const COR_BANNER = ["rgba(140,116,0,.86)", "rgba(64,94,120,.86)"];
const AMARELO = "#ffd61f", LARANJA = "#ff8c1a", VERMELHO = "#ff2e2e";

/* ---------- contas pequenas ---------- */
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const lerp = (a, b, t) => a + (b - a) * t;
const nivel = (v) => clamp((v - 70) / 25, 0, 1);
const voltaAtras = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2; };
const gauss = () => clamp((Math.random() + Math.random() + Math.random() - 1.5) * 1.4, -2.2, 2.2);

const linhaGol = (t) => (t === 0 ? CAMPO.x0 : CAMPO.x1);   // o time 0 defende a esquerda
const sentido = (t) => (t === 0 ? 1 : -1);                  // para onde o time ataca
const xGoleiro = (t) => linhaGol(t) + sentido(t) * (GOLEIRO_RAIO + 3);

function naArea(x, y, t) {
  const dx = (x - linhaGol(t)) * sentido(t);
  return dx >= -4 && dx <= AREA_P && Math.abs(y - CY) <= AREA_MEIA;
}

function dentroDoCampo(x, y, folga) {
  return x >= CAMPO.x0 - folga && x <= CAMPO.x1 + folga && y >= CAMPO.y0 - folga && y <= CAMPO.y1 + folga;
}

/* Atributos do time (Jogo.parametros): chute = força, controle = barra
   mais calma e mira da CPU, defesa = goleiro maior e mais rápido. */
function parametros(t, embalado) {
  const time = TIMES[t];
  const ch = nivel(time.chute), co = nivel(time.controle), de = nivel(time.defesa);
  const p = {
    vmax: VMAX * lerp(0.9, 1.06, ch),
    cicloBarra: lerp(0.72, 1.12, co),
    massa: lerp(2.7, 3.3, (ch + de) * 0.5),
    goleiroMeio: lerp(20, 27, de),
    goleiroVel: lerp(170, 270, de),
    erroCpu: lerp(1.35, 0.7, co),
  };
  if (embalado) { p.vmax *= 1.08; p.cicloBarra *= 1.25; p.erroCpu *= 0.7; }
  return p;
}
const PARAMS = [[parametros(0, false), parametros(0, true)], [parametros(1, false), parametros(1, true)]];

/* Distância que a bola anda saindo com velocidade v (atrito + arrasto). */
function distanciaBola(v) {
  const k = AMORTECE_BOLA, a = ATRITO_BOLA;
  return v / k - (a / (k * k)) * Math.log(1 + (k * v) / a);
}

function velocidadeBola(d) {
  let lo = 0, hi = 4000;
  for (let i = 0; i < 24; i++) {
    const m = (lo + hi) * 0.5;
    if (distanciaBola(m) < d) lo = m; else hi = m;
  }
  return hi;
}

/* Ponto do segmento ab mais perto de p (escreve em saida). */
function pontoNoSegmento(px, py, ax, ay, bx, by, saida) {
  const dx = bx - ax, dy = by - ay;
  const l2 = dx * dx + dy * dy;
  const t = l2 > 0 ? clamp(((px - ax) * dx + (py - ay) * dy) / l2, 0, 1) : 0;
  saida.x = ax + dx * t;
  saida.y = ay + dy * t;
  return saida;
}

/* Menor distância entre os segmentos p1q1 e p2q2 (o goleiro é um segmento). */
function distSegSeg(p1x, p1y, q1x, q1y, p2x, p2y, q2x, q2y) {
  const d1x = q1x - p1x, d1y = q1y - p1y, d2x = q2x - p2x, d2y = q2y - p2y;
  const rx = p1x - p2x, ry = p1y - p2y;
  const a = d1x * d1x + d1y * d1y, e = d2x * d2x + d2y * d2y, f = d2x * rx + d2y * ry;
  let s = 0, t = 0;
  if (a <= 1e-9 && e <= 1e-9) return Math.hypot(rx, ry);
  if (a <= 1e-9) t = clamp(f / e, 0, 1);
  else {
    const c = d1x * rx + d1y * ry;
    if (e <= 1e-9) s = clamp(-c / a, 0, 1);
    else {
      const b = d1x * d2x + d1y * d2y, den = a * e - b * b;
      s = den !== 0 ? clamp((b * f - c * e) / den, 0, 1) : 0;
      t = (b * s + f) / e;
      if (t < 0) { t = 0; s = clamp(-c / a, 0, 1); } else if (t > 1) { t = 1; s = clamp((b - c) / a, 0, 1); }
    }
  }
  return Math.hypot(p1x + d1x * s - (p2x + d2x * t), p1y + d1y * s - (p2y + d2y * t));
}

/* MIRA DA CPU (ia.gd): para mandar a bola na direção d, em que direção
   lançar o botão? Traça o caminho do botão até o ponto em que ele encosta
   na bola (a bola sai na linha entre os centros nesse instante) e procura
   o ângulo que faz a bola sair em d. Busca grossa (5°) e depois fina (1°). */
function mirar(bx, by, ox, oy, dx, dy, rb) {
  const baseX = ox - dx * rb - bx, baseY = oy - dy * rb - by;
  const ang0 = Math.hypot(baseX, baseY) > 2 ? Math.atan2(baseY, baseX) : Math.atan2(dy, dx);
  let melhor = testarAngulos(bx, by, ox, oy, dx, dy, rb, ang0, 5 * GRAU, 12, null);
  if (melhor) melhor = testarAngulos(bx, by, ox, oy, dx, dy, rb, melhor.ang, GRAU, 5, melhor);
  return melhor;
}

function testarAngulos(bx, by, ox, oy, dx, dy, rb, centro, passo, n, melhor) {
  let melhorErro = melhor ? melhor.erro : 9;
  const mx = bx - ox, my = by - oy;
  const cc = mx * mx + my * my - rb * rb;
  for (let i = -n; i <= n; i++) {
    const ang = centro + i * passo;
    const ux = Math.cos(ang), uy = Math.sin(ang);
    const bb = mx * ux + my * uy;
    const disc = bb * bb - cc;
    if (disc < 0) continue;
    const s = -bb - Math.sqrt(disc);
    if (s < -0.5) continue;
    const sp = Math.max(s, 0);
    const nx = (ox - (bx + ux * sp)) / rb, ny = (oy - (by + uy * sp)) / rb;
    const erro = Math.abs(Math.atan2(nx * dy - ny * dx, nx * dx + ny * dy));
    if (erro < melhorErro) {
      melhorErro = erro;
      const nl = Math.hypot(nx, ny) || 1;
      melhor = { ux, uy, D: sp, cos: (ux * nx + uy * ny) / nl, erro, ang };
    }
  }
  return melhor;
}

/* Cor da força: verde -> amarelo -> vermelho (mira.gd). */
function corForca(f) {
  let r, g, b;
  if (f < 0.5) { const k = f * 2; r = lerp(0.25, 1, k); g = lerp(1, 0.9, k); b = lerp(0.35, 0.1, k); }
  else { const k = (f - 0.5) * 2; r = 1; g = lerp(0.9, 0.2, k); b = lerp(0.1, 0.15, k); }
  return `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})`;
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

/* Pinta uma arte branca (anel, brilho, estrela, confete) numa cor: feito
   uma vez na entrada, nunca por quadro. */
function tingir(imagem, cor) {
  if (!imagem || typeof document === "undefined") return null;
  const tela = document.createElement("canvas");
  tela.width = imagem.width;
  tela.height = imagem.height;
  const c = tela.getContext("2d");
  c.drawImage(imagem, 0, 0);
  c.globalCompositeOperation = "source-in";
  c.fillStyle = cor;
  c.fillRect(0, 0, tela.width, tela.height);
  return tela;
}

/* A torcida vem num atlas SEM transparência (o canal alfa dos torcedores
   miudinhos triplicava o peso do arquivo): sobre preto. Aqui, uma vez na
   entrada, o preto vira transparente -- quanto mais escuro o pixel, mais
   transparente --, e por quadro a torcida é desenhada do jeito comum.
   (Somar as cores com "lighter" a cada quadro dispensaria isso, mas em
   alguns aparelhos esse modo de mistura é dezenas de vezes mais lento.) */
function torcidaSemFundo(imagem) {
  if (!imagem || typeof document === "undefined") return null;
  const tela = document.createElement("canvas");
  tela.width = imagem.width;
  tela.height = imagem.height;
  const c = tela.getContext("2d", { willReadFrequently: true });
  c.drawImage(imagem, 0, 0);
  try {
    const dados = c.getImageData(0, 0, tela.width, tela.height);
    const px = dados.data;
    for (let i = 0; i < px.length; i += 4) {
      const m = Math.max(px[i], px[i + 1], px[i + 2]);
      // até ~20 é o preto do fundo (com o chuvisco da compressão)
      px[i + 3] = m <= 20 ? 0 : Math.min(255, (m - 20) * 2.6);
    }
    c.putImageData(dados, 0, 0);
  } catch (erro) {
    return null;                     // sem acesso aos pixels: desenha somando
  }
  // copia para uma tela comum: a de leitura fica na memória do processador
  // e seria reenviada à placa de vídeo a cada quadro
  const pronta = document.createElement("canvas");
  pronta.width = tela.width;
  pronta.height = tela.height;
  pronta.getContext("2d").drawImage(tela, 0, 0);
  return pronta;
}

const ARTE = "craque-de-botao/";

export default {
  largura: 960,
  altura: 540,
  artes: {
    estadioBra: ARTE + "estadio_bra.webp",
    estadioArg: ARTE + "estadio_arg.webp",
    torcida: ARTE + "torcida.webp",
    botaoBra: ARTE + "botao_bra.webp",
    botaoArg: ARTE + "botao_arg.webp",
    goleiroBra: ARTE + "goleiro_bra.webp",
    goleiroArg: ARTE + "goleiro_arg.webp",
    bandeiraBra: ARTE + "bandeira_bra.webp",
    bandeiraArg: ARTE + "bandeira_arg.webp",
    bola: ARTE + "bola.webp",
    sombra: ARTE + "sombra.webp",
    anel: ARTE + "anel.webp",
    brilho: ARTE + "brilho.webp",
    rede: ARTE + "rede.webp",
    estrela: ARTE + "estrela.webp",
    faisca: ARTE + "faisca.webp",
    confete: ARTE + "confete.webp",
    trofeu: ARTE + "trofeu.webp",
    logo: ARTE + "logo.webp",
  },

  criar(api) {
    const img = api.img;
    const demo = api.variante === "demo";
    const humano = [!demo, false];

    /* ---------- artes pintadas na entrada ---------- */
    const anelAmarelo = tingir(img.anel, "#ffe640");
    const aura = [tingir(img.brilho, "#fff07a"), tingir(img.brilho, "#b8dcff")];
    const estrelas = TIMES.map((t) => [tingir(img.estrela, t.torcida[0]), tingir(img.estrela, t.torcida[1])]);
    const estrelaBranca = tingir(img.estrela, "#fff6c8");
    const confetes = TIMES.map((t) => [tingir(img.confete, t.torcida[0]), tingir(img.confete, t.torcida[1])]);
    const poeira = tingir(img.faisca, "#c8ffb0");
    const torcidaPronta = torcidaSemFundo(img.torcida);

    /* ---------- as peças (corpo.gd) ---------- */
    function novoCorpo(tipo, time, numero) {
      return {
        tipo, time, numero, x: 0, y: 0, vx: 0, vy: 0, raio: RAIO_BOTAO, massa: 3,
        atrito: ATRITO_BOTAO, amortece: 0, fixo: false, meio: 0, ativo: true,
        amarelos: 0, faltas: 0, slot: 0,
        // só do desenho
        dx: 0, dy: 0, suave: 0, pulo: -1, puloAtraso: 0, giro: 0, sumir: 0, cartao: 1,
      };
    }

    const bola = novoCorpo(BOLA, -1, 0);
    bola.raio = RAIO_BOLA;
    bola.massa = 1;
    bola.atrito = ATRITO_BOLA;
    bola.amortece = AMORTECE_BOLA;
    const goleiros = [novoCorpo(GOLEIRO, 0, 1), novoCorpo(GOLEIRO, 1, 1)];
    const botoes = [[], []];
    const corpos = [bola];
    for (let t = 0; t < 2; t++) {
      const g = goleiros[t];
      g.fixo = true;
      g.raio = GOLEIRO_RAIO;
      g.meio = PARAMS[t][0].goleiroMeio;        // defesa melhor = goleiro maior
      corpos.push(g);
      for (let i = 0; i < 6; i++) {
        const b = novoCorpo(BOTAO, t, NUMEROS[i]);
        b.massa = PARAMS[t][0].massa;           // time forte: botão mais pesado
        b.slot = i;
        botoes[t].push(b);
        corpos.push(b);
      }
    }

    // traves e redes (fisica.gd): postes e segmentos [ax, ay, bx, by, restituição]
    const POSTES = [];
    const SEGMENTOS = [];
    for (let t = 0; t < 2; t++) {
      const x = linhaGol(t), fundo = x - sentido(t) * GOL_FUNDO;
      const y0 = CY - GOL_MEIA, y1 = CY + GOL_MEIA;
      POSTES.push([x, y0], [x, y1]);
      SEGMENTOS.push([x, y0, fundo, y0, 0.25], [x, y1, fundo, y1, 0.25], [fundo, y0, fundo, y1, 0.12]);
    }
    // rascunhos: a física e o desenho rodam todo quadro sem alocar nada
    const P = { x: 0, y: 0 };
    const PT = { x: 0, y: 0 };
    const F = { dx: 0, dy: 0, f: 0, v: 0, dist: 0 };

    /* ---------- estado da partida ---------- */
    let estado = "pronto";      // pronto | preparo | vez | movendo | evento | fim
    let vez = 0, toques = 0, tempo = DURACAO, relogioVez = RELOGIO_VEZ;
    let relogio = 0, tEstado = 0, estadoAnt = "";
    const placar = [0, 0];
    const embalo = [0, 0];
    let jogada = null;
    let cobranca = "", cobrador = null, penaltiCobrador = null;
    let ultimoToque = -1, ultimoBotaoBola = null;
    let tJogada = 0, pararEm = -1;
    let agenda = [];
    let partidasJogadas = 0;    // alterna o estádio a cada partida
    let estadio = img.estadioBra;
    let primeiroToque = true;
    let goleiroManual = false;
    const somPronto = {};

    // controle do jogador
    let sel = null, ang = 0, modoTeclado = false, carregando = false, tCarga = 0, tGirar = 0;
    let mirando = null, ponteiro = null, dedoX = 0, dedoY = 0;
    const teclas = { cima: false, baixo: false, esq: false, dir: false };

    // CPU
    let cpu = null;

    // efeitos
    let aviso = null;           // faixa grande: {txt, sub, cor, dur, grande, t}
    let flash = null;           // {cor, a}
    let dica = "";
    let final = null;           // tela de fim: {t, venceu, empate}
    const rede = [-1, -1];      // segundos desde o gol em cada rede (-1: parada)
    const torcida = { fase: 0, pulo: [0.15, 0.15], alvo: [0.15, 0.15], vel: 1, calma: 0 };
    const rastro = [];          // últimas posições da bola rápida (x, y, x, y...)
    let confete = null;         // {resta, time, acumulado}
    let fogos = [];             // explosões agendadas
    let anim = 0, ultimoQuadro = 0;
    let placarMostrado = "";
    let segundosMostrados = -1;

    // partículas num estoque fixo: o mais velho é reaproveitado
    const MAX_PART = 420;
    const parts = [];
    for (let i = 0; i < MAX_PART; i++) {
      parts.push({ vivo: false, x: 0, y: 0, vx: 0, vy: 0, vida: 0, total: 1, tam: 1, cresce: 0, img: null,
        aditivo: false, grav: 0, amort: 0, giro: 0, vgiro: 0, alfa: 1, larg: 1, alt: 1, confete: false });
    }
    let cursorPart = 0;

    function particula() {
      cursorPart = (cursorPart + 1) % MAX_PART;
      const p = parts[cursorPart];
      p.vivo = true; p.cresce = 0; p.giro = 0; p.vgiro = 0; p.alfa = 1; p.confete = false; p.amort = 0; p.grav = 0;
      return p;
    }

    /* ---------- agenda: "daqui a tantos segundos, faça isto" ---------- */
    function depois(seg, fn) { agenda.push({ t: relogio + seg, fn }); }

    function rodarAgenda() {
      for (let i = 0; i < agenda.length;) {
        if (agenda[i].t <= relogio) {
          const fn = agenda[i].fn;
          agenda.splice(i, 1);
          fn();
        } else i++;
      }
    }

    /* =============================================================== FÍSICA
       (fisica.gd) discos deslizando com atrito, choques elásticos, goleiro
       "cápsula" fixo, traves, redes e as placas em volta. Os subpassos
       seguem a peça mais rápida: nada anda mais que 5 px por subpasso,
       então nada atravessa nada. */
    function passoFisica(dt) {
      let vmax = 0;
      for (const c of corpos) {
        if (c.ativo && !c.fixo) { const v = Math.hypot(c.vx, c.vy); if (v > vmax) vmax = v; }
      }
      if (vmax <= 0) return;
      const n = clamp(Math.ceil((vmax * dt) / PASSO_MAX), 1, SUBPASSOS_MAX);
      const h = dt / n;
      for (let s = 0; s < n; s++) {
        moverCorpos(h);
        colisoes();
      }
    }

    function moverCorpos(h) {
      for (const c of corpos) {
        if (!c.ativo || c.fixo) continue;
        const v = Math.hypot(c.vx, c.vy);
        if (v <= 0) continue;
        const nova = v - (c.atrito + c.amortece * v) * h;
        if (nova < PARADO) { c.vx = 0; c.vy = 0; continue; }
        const k = nova / v;
        c.vx *= k;
        c.vy *= k;
        c.x += c.vx * h;
        c.y += c.vy * h;
      }
    }

    function colisoes() {
      const n = corpos.length;
      for (let i = 0; i < n; i++) {
        const a = corpos[i];
        if (!a.ativo || a.fixo || (a.vx === 0 && a.vy === 0)) continue;
        const alcance = a.raio + a.meio;
        for (let j = 0; j < n; j++) {
          if (j === i) continue;
          const b = corpos[j];
          if (!b.ativo) continue;
          // par de dois em movimento: resolve uma vez só
          if (j < i && !b.fixo && (b.vx !== 0 || b.vy !== 0)) continue;
          const lim = alcance + b.raio + b.meio;
          if (Math.abs(b.x - a.x) < lim && Math.abs(b.y - a.y) < lim) choque(a, b);
        }
        // traves, redes e a boca do gol: só perto de um dos gols
        const perto = (a.x < CAMPO.x0 + alcance + 8 && a.x > CAMPO.x0 - GOL_FUNDO - alcance - 8)
          || (a.x > CAMPO.x1 - alcance - 8 && a.x < CAMPO.x1 + GOL_FUNDO + alcance + 8);
        if (perto && Math.abs(a.y - CY) < GOL_MEIA + alcance + 8) {
          for (const q of POSTES) choqueEstatico(a, q[0], q[1], RAIO_TRAVE, 0.55, "trave");
          for (const sg of SEGMENTOS) {
            pontoNoSegmento(a.x, a.y, sg[0], sg[1], sg[2], sg[3], P);
            choqueEstatico(a, P.x, P.y, 0, sg[4], "rede");
          }
          if (a.tipo === BOTAO) bocaDoGol(a);
        }
        const r = a.raio;
        if (a.x < MURO.x0 + r || a.x > MURO.x1 - r || a.y < MURO.y0 + r || a.y > MURO.y1 - r) placas(a);
      }
    }

    /* Botão não entra no gol: uma parede invisível na linha entre as
       traves só para os botões (a bola passa). Botão parado dentro do gol
       impedia gols. */
    function bocaDoGol(a) {
      const r = a.raio;
      const dy = Math.abs(a.y - CY);
      if (dy > GOL_MEIA + r) return;
      for (let l = 0; l < 2; l++) {
        const x = l === 0 ? CAMPO.x0 : CAMPO.x1;
        const dentro = l === 0 ? 1 : -1;
        const limite = dy <= GOL_MEIA ? r : 0;
        const rel = (a.x - x) * dentro;
        if (rel < limite && rel > -GOL_FUNDO - r) {
          a.x = x + dentro * r;
          if (a.vx * dentro < 0) {
            const vn = Math.abs(a.vx);
            a.vx = -a.vx * 0.35;
            aoBater("placa", a, null, vn);
          }
        }
      }
    }

    function choque(a, b) {
      // ponto do "osso" de cada corpo mais perto do outro (goleiro = cápsula)
      let pay = a.y, pby = b.y;
      if (a.meio > 0) pay = clamp(b.y, a.y - a.meio, a.y + a.meio);
      if (b.meio > 0) pby = clamp(pay, b.y - b.meio, b.y + b.meio);
      if (a.meio > 0) pay = clamp(pby, a.y - a.meio, a.y + a.meio);
      const dx = b.x - a.x, dy = pby - pay;
      const minimo = a.raio + b.raio;
      const d2 = dx * dx + dy * dy;
      if (d2 >= minimo * minimo) return;
      const dist = Math.sqrt(d2);
      let nx = 1, ny = 0;
      if (dist > 0.0001) { nx = dx / dist; ny = dy / dist; }
      const invA = a.fixo ? 0 : 1 / a.massa;
      const invB = b.fixo ? 0 : 1 / b.massa;
      const soma = invA + invB;
      if (soma <= 0) return;
      const sobra = minimo - dist;
      a.x -= (nx * sobra * invA) / soma;
      a.y -= (ny * sobra * invA) / soma;
      b.x += (nx * sobra * invB) / soma;
      b.y += (ny * sobra * invB) / soma;
      const rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
      if (rel >= 0) return;
      let e = 0.82;
      if (a.tipo === BOLA || b.tipo === BOLA) e = 0.78;
      if (a.fixo || b.fixo) e = 0.45;
      const j = (-(1 + e) * rel) / soma;
      a.vx -= nx * j * invA;
      a.vy -= ny * j * invA;
      b.vx += nx * j * invB;
      b.vy += ny * j * invB;
      aoBater("corpo", a, b, -rel);
    }

    function choqueEstatico(a, qx, qy, raioQ, e, tipo) {
      const dx = a.x - qx, dy = a.y - qy;
      const minimo = a.raio + raioQ;
      const d2 = dx * dx + dy * dy;
      if (d2 >= minimo * minimo) return;
      const dist = Math.sqrt(d2);
      let nx = 0, ny = -1;
      if (dist > 0.0001) { nx = dx / dist; ny = dy / dist; }
      a.x = qx + nx * minimo;
      a.y = qy + ny * minimo;
      const vn = a.vx * nx + a.vy * ny;
      if (vn < 0) {
        a.vx -= nx * vn * (1 + e);
        a.vy -= ny * vn * (1 + e);
        if (tipo === "rede") { a.vx *= 0.6; a.vy *= 0.6; }
        aoBater(tipo, a, null, -vn);
      }
    }

    function placas(a) {
      const r = a.raio;
      let bateu = 0;
      if (a.x < MURO.x0 + r) {
        a.x = MURO.x0 + r;
        if (a.vx < 0) { bateu = -a.vx; a.vx = -a.vx * 0.45; }
      } else if (a.x > MURO.x1 - r) {
        a.x = MURO.x1 - r;
        if (a.vx > 0) { bateu = a.vx; a.vx = -a.vx * 0.45; }
      }
      if (a.y < MURO.y0 + r) {
        a.y = MURO.y0 + r;
        if (a.vy < 0) { bateu = Math.max(bateu, -a.vy); a.vy = -a.vy * 0.45; }
      } else if (a.y > MURO.y1 - r) {
        a.y = MURO.y1 - r;
        if (a.vy > 0) { bateu = Math.max(bateu, a.vy); a.vy = -a.vy * 0.45; }
      }
      if (bateu > 0) aoBater("placa", a, null, bateu);
    }

    function tudoParado() {
      for (const c of corpos) if (c.ativo && (c.vx !== 0 || c.vy !== 0)) return false;
      return true;
    }

    function pararTudo() {
      for (const c of corpos) { c.vx = 0; c.vy = 0; }
    }

    /* Som com intervalo mínimo e força mínima: encostadinhas não fazem
       barulho e um monte de choques juntos não vira um ruído só. */
    function somDe(nome, v, intervalo, minimo = 40) {
      if (v < minimo) return;
      if ((somPronto[nome] || 0) > relogio) return;
      somPronto[nome] = relogio + intervalo;
      api.som(nome);
    }

    /* Cada choque vira um "evento" para as regras: quem tocou na bola, falta. */
    function aoBater(tipo, a, b, v) {
      if (!jogada) return;
      if (tipo === "corpo") {
        let outro = null;
        if (a === bola) outro = b; else if (b === bola) outro = a;
        if (outro) {
          ultimoToque = outro.time;
          ultimoBotaoBola = outro;
          if (outro === jogada.botao) jogada.tocou = true;
          somDe("quica", v, 0.05);
        } else {
          const j = jogada.botao;
          let rival = null;
          if (a === j && b.time !== j.time) rival = b;
          else if (b === j && a.time !== j.time) rival = a;
          // encostadinha não conta: falta é batida de verdade
          if (rival && !jogada.tocou && !jogada.rival && v > 60) {
            jogada.rival = rival;
            jogada.impacto = v;
            jogada.lx = rival.x;
            jogada.ly = rival.y;
          }
          somDe(v > 260 ? "batida" : "clique", v, 0.06, 70);
          if (v > 500) faisca((a.x + b.x) * 0.5, (a.y + b.y) * 0.5);
        }
      } else if (tipo === "trave") {
        if (a === bola) {
          jogada.trave = true;
          somDe("nota", Math.max(v, 450), 0.3);
          if (v > 250 && jogada.gol < 0 && (somPronto.uuu || 0) <= relogio) {
            somPronto.uuu = relogio + 2.5;
            const x = clamp(a.x, 230, 1050), y = clamp(a.y, 160, 640);
            api.efeitos.texto("NA TRAVE!", x * K, y * K - 20, { cor: AMARELO, tamanho: 34 });
            api.tremer(5);
            faisca(a.x, a.y);
          }
        }
      } else if (tipo === "rede") {
        if (a === bola) somDe("whoosh", v, 0.25);
      } else if (tipo === "placa") {
        somDe("quica", v, 0.1, 120);
      }
    }

    /* Gol: o centro da bola passou a linha entre as traves. Fora: a bola
       inteira saiu pela linha de fundo ou pela lateral. */
    function verificarBola() {
      if (jogada.gol >= 0 || jogada.fora) return;
      const r = RAIO_BOLA;
      for (let lado = 0; lado < 2; lado++) {
        const dentroDoGol = Math.abs(bola.y - CY) < GOL_MEIA;
        let passou;
        if (dentroDoGol) passou = lado === 0 ? bola.x < CAMPO.x0 : bola.x > CAMPO.x1;
        else passou = lado === 0 ? bola.x < CAMPO.x0 - r : bola.x > CAMPO.x1 + r;
        if (!passou) continue;
        if (dentroDoGol) {
          jogada.gol = 1 - lado;            // marca quem NÃO defende esse lado
          pararEm = tJogada + 1.0;          // a bola ainda corre para a rede
          rede[lado] = 0;
        } else {
          jogada.fora = { tipo: "fundo", lado, x: bola.x, y: bola.y };
          pararEm = tJogada + 0.3;
        }
        return;
      }
      if (bola.y < CAMPO.y0 - r || bola.y > CAMPO.y1 + r) {
        jogada.fora = { tipo: "lateral", x: bola.x, y: bola.y };
        pararEm = tJogada + 0.3;
      }
    }

    /* ================================================================ FLUXO */
    function maisPerto(time, x, y) {
      let melhor = null, md = 1e9;
      for (const b of botoes[time]) {
        if (!b.ativo) continue;
        const d = Math.hypot(b.x - x, b.y - y);
        if (d < md) { md = d; melhor = b; }
      }
      return melhor;
    }

    /* Nenhum botão dentro do gol: o que ficou atrás da linha, entre as
       redes, vai para a frente da boca do gol (senão ficava preso lá). */
    function foraDoGol(b) {
      if (!b.ativo || b.tipo !== BOTAO) return;
      const r = b.raio;
      if (Math.abs(b.y - CY) > GOL_MEIA + r + RAIO_TRAVE) return;
      for (let l = 0; l < 2; l++) {
        const x = l === 0 ? CAMPO.x0 : CAMPO.x1;
        const dentro = l === 0 ? 1 : -1;
        const fundo = (b.x - x) * dentro;
        if (fundo < (Math.abs(b.y - CY) <= GOL_MEIA ? r : 0) && fundo > -GOL_FUNDO - r - 8) {
          b.x = x + dentro * (r + 3);
          b.vx = 0; b.vy = 0;
          b.suave = 0.7;
        }
      }
    }

    /* Separa peças que ficaram umas em cima das outras depois de posicionar. */
    function desencavalar(fixo) {
      for (const t of [0, 1]) for (const b of botoes[t]) foraDoGol(b);
      for (let it = 0; it < 12; it++) {
        let mexeu = false;
        for (const a of corpos) {
          if (!a.ativo || a.tipo !== BOTAO || a === fixo) continue;
          for (const b of corpos) {
            if (a === b || !b.ativo) continue;
            const qy = b.meio > 0 ? clamp(a.y, b.y - b.meio, b.y + b.meio) : b.y;
            const dx = a.x - b.x, dy = a.y - qy;
            const minimo = a.raio + b.raio + 2;
            const d = Math.hypot(dx, dy);
            if (d < minimo) {
              let nx, ny;
              if (d > 0.5) { nx = dx / d; ny = dy / d; } else { const g = Math.random() * TAU; nx = Math.cos(g); ny = Math.sin(g); }
              a.x = clamp(b.x + nx * minimo, MURO.x0 + a.raio, MURO.x1 - a.raio);
              a.y = clamp(qy + ny * minimo, MURO.y0 + a.raio, MURO.y1 - a.raio);
              a.suave = 0.7;
              mexeu = true;
            }
          }
        }
        if (!mexeu) break;
      }
      for (const t of [0, 1]) for (const b of botoes[t]) foraDoGol(b);
    }

    function posicaoFormacao(b) {
      const f = FORMACAO[b.slot];
      b.x = b.time === 0 ? CAMPO.x0 + f[0] * 1000 : CAMPO.x1 - f[0] * 1000;
      b.y = CAMPO.y0 + f[1] * 570;
    }

    function saidaDeBola(time) {
      estado = "preparo";
      cobranca = "";
      cobrador = null;
      penaltiCobrador = null;
      pararTudo();
      for (const t of [0, 1]) {
        for (const b of botoes[t]) if (b.ativo) { posicaoFormacao(b); b.suave = 0.7; }
        goleiros[t].x = xGoleiro(t);
        goleiros[t].y = CY;
      }
      bola.x = CX; bola.y = CY; bola.suave = 0.5;
      const batedor = maisPerto(time, CX, CY);
      if (batedor) {
        batedor.x = CX - sentido(time) * (RAIO_BOTAO + RAIO_BOLA + 3);
        batedor.y = CY;
      }
      desencavalar(null);
      api.som("apito");
      mostrarAviso("SAÍDA DE BOLA", TIMES[time].nome, COR_BANNER[time], 1.3);
      depois(1.2, () => novaVez(time, false));
    }

    function novaVez(time, manterToques) {
      if (estado === "fim") return;
      const outroTime = vez !== time;
      vez = time;
      if (!manterToques) toques = 0;
      estado = "vez";
      relogioVez = RELOGIO_VEZ;
      mirando = null;
      ponteiro = null;
      carregando = false;
      cpu = null;
      goleiroManual = false;
      sel = null;
      if (!humano[time]) {
        cpu = { t: 0, pensar: api.aleatorio(0.6, 1.0), decisao: null, pensou: false, inicioMira: -1, ang0: 0 };
        dica = "";
        return;
      }
      escolherInicial();
      const fixo = cobradorFixo();
      if (cobranca === "penalti") dica = "PÊNALTI: CHUTE NO CANTO, LONGE DO GOLEIRO";
      else if (fixo) dica = `${cobranca.toUpperCase()}: QUEM COBRA É O BOTÃO DESTACADO`;
      else if (primeiroToque) dica = "ARRASTE UM BOTÃO AMARELO PARA TRÁS E SOLTE";
      else dica = "";
      if (sel && !demo && (manterToques || outroTime || primeiroToque)) {
        api.efeitos.texto(manterToques ? "MAIS UM TOQUE!" : "SUA VEZ!", sel.x * K, (sel.y - 58) * K,
          { cor: AMARELO, tamanho: manterToques ? 20 : 26, vida: 0.9 });
      }
    }

    function passarVez(de) { novaVez(1 - de, false); }

    /* Bola parada com cobrador (falta, lateral, escanteio): só ele joga.
       No pênalti, só o batedor. */
    function cobradorFixo() {
      if (cobranca === "penalti") return penaltiCobrador;
      if ((cobranca === "falta" || cobranca === "lateral" || cobranca === "escanteio")
        && cobrador && cobrador.ativo && cobrador.time === vez) return cobrador;
      return null;
    }

    function podeJogar(b) {
      const fixo = cobradorFixo();
      return b.ativo && (!fixo || b === fixo);
    }

    /* Botões do time do mais perto ao mais longe da bola (↑/↓ percorre). */
    function listaEscolha(time) {
      let lista = botoes[time].filter(podeJogar);
      if (!lista.length) lista = botoes[time].filter((b) => b.ativo);
      lista.sort((a, b) => Math.hypot(a.x - bola.x, a.y - bola.y) - Math.hypot(b.x - bola.x, b.y - bola.y));
      return lista;
    }

    function escolherInicial() {
      const lista = listaEscolha(vez);
      if (!lista.length) return;
      if (cobranca && cobrador && lista.includes(cobrador)) selecionar(cobrador);
      else selecionar(lista[0]);
    }

    function selecionar(b) {
      sel = b;
      let ax = bola.x, ay = bola.y;
      if (cobranca === "penalti") { ax = linhaGol(1 - vez); ay = CY; }
      ang = Math.atan2(ay - b.y, ax - b.x);
      carregando = false;
    }

    function trocarBotao(passo) {
      const lista = listaEscolha(vez);
      if (lista.length < 2) return;
      let i = lista.indexOf(sel);
      i = (i + passo + lista.length) % lista.length;
      selecionar(lista[i]);
      api.som("clique");
    }

    const vmaxDe = (t) => PARAMS[t][embalo[t] > 0 ? 1 : 0].vmax;
    const velocidadeDaForca = (t, f) => lerp(VMIN, vmaxDe(t), Math.pow(clamp(f, 0.04, 1), 1.1));

    /* Barra do manche: sobe e desce (0..1..0) enquanto o chute está apertado. */
    function valorBarra() {
      const ciclo = PARAMS[vez][embalo[vez] > 0 ? 1 : 0].cicloBarra;
      const f = (tCarga / ciclo) % 2;
      return f <= 1 ? f : 2 - f;
    }

    /* Estilingue: o dedo puxa para trás, o botão sai para o lado oposto. */
    function forcaDoToque(b, px, py) {
      const ox = px - b.x, oy = py - b.y;
      const dist = Math.hypot(ox, oy);
      F.dist = dist;
      F.f = clamp((dist - PUXAO_MIN) / (PUXAO_MAX - PUXAO_MIN), 0, 1);
      if (dist > 0.5) { F.dx = -ox / dist; F.dy = -oy / dist; } else { F.dx = sentido(b.time); F.dy = 0; }
      F.v = lerp(VMIN, vmaxDe(b.time), Math.pow(F.f, 1.25));
      return F;
    }

    function chutar(b, vx, vy) {
      jogada = { botao: b, time: b.time, tocou: false, rival: null, impacto: 0, lx: 0, ly: 0, gol: -1, fora: null, trave: false };
      b.vx = vx;
      b.vy = vy;
      const v = Math.hypot(vx, vy);
      // LATERAL e ESCANTEIO: a bola sai do meio do cobrador, exatamente na
      // direção da mira; o cobrador fica parado e a bola leva a força
      if ((cobranca === "lateral" || cobranca === "escanteio") && b === cobrador && v > 1) {
        bola.x = b.x + (vx / v) * (b.raio + bola.raio + 1);
        bola.y = b.y + (vy / v) * (b.raio + bola.raio + 1);
        bola.vx = vx * 1.45;
        bola.vy = vy * 1.45;
        b.vx = 0; b.vy = 0;
        jogada.tocou = true;
        ultimoToque = b.time;
        ultimoBotaoBola = b;
      }
      if (humano[b.time]) primeiroToque = false;
      estado = "movendo";
      tJogada = 0;
      pararEm = -1;
      carregando = false;
      mirando = null;
      sel = null;
      dica = "";
      const f = Math.min(1, v / VMAX);
      api.som(f > 0.55 ? "whoosh" : "clique");
      if (f > 0.85) api.tremer(3);
      // poeira de grama no peteleco
      const n = api.reduzido ? 5 : 14;
      for (let i = 0; i < n; i++) {
        const p = particula();
        const g = Math.random() * TAU, vel = 90 * (1 - 0.6 * Math.random()) * (0.6 + f);
        p.x = b.x; p.y = b.y; p.vx = Math.cos(g) * vel; p.vy = Math.sin(g) * vel;
        p.vida = p.total = 0.5; p.tam = 14 * (1 - 0.5 * Math.random()); p.img = poeira; p.aditivo = false;
        p.amort = 120; p.alfa = 0.8;
      }
    }

    /* =============================================================== REGRAS */
    function resolver() {
      const j = jogada;
      if (j.gol >= 0) { gol(j.gol); return; }
      const eraPenalti = cobranca === "penalti";
      cobranca = "";
      if (j.rival && !j.tocou) { falta(j); return; }
      if (tempo <= 0) { fimDoTempo(); return; }
      if (j.fora) { bolaFora(j.fora); return; }
      if (eraPenalti) { passarVez(j.time); return; }
      if (j.tocou) {
        toques += 1;
        if (toques >= TOQUES) {
          const x = clamp(bola.x, 230, 1050), y = clamp(bola.y, 160, 640);
          api.efeitos.texto(`${toques} TOQUES!`, x * K, y * K - 30, { cor: "#fff", tamanho: 28 });
          api.som("combo");
          estado = "evento";
          depois(0.5, () => passarVez(j.time));
        } else novaVez(j.time, true);
      } else passarVez(j.time);
    }

    function falta(j) {
      estado = "evento";
      const faltoso = j.botao;
      const time = j.time;
      api.som("apito");
      const lx = clamp(j.lx, CAMPO.x0 + 14, CAMPO.x1 - 14);
      const ly = clamp(j.ly, CAMPO.y0 + 14, CAMPO.y1 - 14);
      const penalti = naArea(lx, ly, time);
      // cartão: batida forte, ou o mesmo botão fazendo a 2ª falta
      let cartao = "";
      const reincidente = faltoso.faltas >= 1;
      faltoso.faltas += 1;
      if (j.impacto >= VERMELHO_V) cartao = "vermelho";
      else if (j.impacto >= AMARELO_V || reincidente) cartao = faltoso.amarelos >= 1 ? "vermelho" : "amarelo";
      mostrarAviso(penalti ? "PÊNALTI!" : "FALTA!", `de ${TIMES[time].nome} nº ${faltoso.numero}`,
        penalti ? "rgba(140,13,13,.85)" : "rgba(25,25,25,.8)", 1.6);
      let espera = 1.7;
      if (cartao) {
        depois(1.8, () => mostrarCartao(faltoso, cartao));
        espera = 4.0;
      }
      if (penalti) depois(espera, () => cobrancaPenalti(1 - time));
      else {
        const gx = linhaGol(time) - lx, gy = CY - ly, l = Math.hypot(gx, gy) || 1;
        depois(espera, () => cobrar("FALTA", 1 - time, lx, ly, gx / l, gy / l));
      }
    }

    function mostrarCartao(b, tipo) {
      api.som(tipo === "vermelho" ? "erro" : "apito");
      if (tipo === "amarelo") {
        b.amarelos += 1;
        b.cartao = 0;                     // anima o cartão grudando no botão
        mostrarAviso("CARTÃO AMARELO", `${TIMES[b.time].nome} nº ${b.numero}`, "rgba(150,118,0,.88)", 1.8);
      } else {
        mostrarAviso("CARTÃO VERMELHO", `${TIMES[b.time].nome} nº ${b.numero} • EXPULSO`, "rgba(150,10,10,.88)", 1.8);
        b.ativo = false;                  // expulso: sai da mesa
        b.sumir = 1;
        b.vx = 0; b.vy = 0;
      }
    }

    function bolaFora(f) {
      estado = "evento";
      const quem = ultimoToque >= 0 ? ultimoToque : jogada.time;
      if (f.tipo === "lateral") {
        const time = 1 - quem;
        const emCima = f.y < CY;
        // a bola fica um pouco DENTRO do campo e o cobrador ao lado dela
        const x = clamp(f.x, CAMPO.x0 + 70, CAMPO.x1 - 70);
        const y = emCima ? CAMPO.y0 + LATERAL_DENTRO : CAMPO.y1 - LATERAL_DENTRO;
        const dx = sentido(time), dy = (emCima ? 1 : -1) * 0.75;
        const l = Math.hypot(dx, dy);
        cobrar("LATERAL", time, x, y, dx / l, dy / l);
        return;
      }
      const lado = f.lado;                // time que defende essa linha de fundo
      const emCima = f.y < CY;
      if (quem === lado) {
        // escanteio: bola perto do canto, mas dentro; mira na marca do pênalti
        const x = linhaGol(lado) + sentido(lado) * 34, y = emCima ? CAMPO.y0 + 46 : CAMPO.y1 - 46;
        const mx = linhaGol(lado) + sentido(lado) * MARCA_PEN;
        const l = Math.hypot(mx - x, CY - y);
        cobrar("ESCANTEIO", 1 - lado, x, y, (mx - x) / l, (CY - y) / l);
      } else {
        // tiro de meta: bola no bico da pequena área, na altura da trave
        const x = linhaGol(lado) + sentido(lado) * (AREA_G + 22), y = CY + (emCima ? -1 : 1) * GOL_MEIA;
        cobrar("TIRO DE META", lado, x, y, sentido(lado), 0);
      }
    }

    /* Bola parada: coloca a bola, o cobrador atrás dela e afasta os rivais. */
    function cobrar(tipo, time, bx, by, dx, dy) {
      estado = "preparo";
      cobranca = tipo.toLowerCase();
      pararTudo();
      const batedor = maisPerto(time, bx, by);
      cobrador = batedor;
      if (batedor) {
        // o cobrador fica EXATAMENTE atrás da bola, na linha da mira. Sem
        // espaço atrás (canto, linha do gol), bola e cobrador entram juntos
        const folga = cobranca === "falta" ? 22 : 6;
        const r = RAIO_BOTAO;
        let ax = bx - dx * (r + RAIO_BOLA + folga), ay = by - dy * (r + RAIO_BOLA + folga);
        const mx = r + 4, my = r + 2;
        const ddx = clamp(ax, CAMPO.x0 + mx, CAMPO.x1 - mx) - ax, ddy = clamp(ay, CAMPO.y0 + my, CAMPO.y1 - my) - ay;
        ax += ddx; ay += ddy; bx += ddx; by += ddy;
        batedor.x = ax; batedor.y = ay; batedor.suave = 0.7;
      }
      bola.x = bx; bola.y = by; bola.suave = 0.6;
      // rivais a ~90 px da bola (barreira); companheiros a ~63 px
      for (const t of [0, 1]) {
        const raioLivre = RAIO_BOTAO + (t !== time ? 58 : 32);
        for (const b of botoes[t]) {
          if (!b.ativo || b === batedor) continue;
          const ox = b.x - bx, oy = b.y - by, d = Math.hypot(ox, oy);
          if (d < raioLivre) {
            let nx, ny;
            if (d > 1) { nx = ox / d; ny = oy / d; } else { nx = -dy; ny = dx; }
            if (nx * -dx + ny * -dy > 0.6) {    // ninguém entre o cobrador e a bola
              const lado = Math.sign(nx * dy - ny * dx + 0.01);
              nx += -dy * lado; ny += dx * lado;
              const l = Math.hypot(nx, ny); nx /= l; ny /= l;
            }
            b.x = clamp(bx + nx * (raioLivre + 2), MURO.x0 + b.raio, MURO.x1 - b.raio);
            b.y = clamp(by + ny * (raioLivre + 2), MURO.y0 + b.raio, MURO.y1 - b.raio);
            b.suave = 0.7;
          }
        }
      }
      // lateral e escanteio: dois companheiros chegam perto para tabelar
      if ((cobranca === "lateral" || cobranca === "escanteio") && batedor) {
        const livres = botoes[time].filter((b) => b.ativo && b !== batedor);
        livres.sort((a, b) => Math.hypot(a.x - bx, a.y - by) - Math.hypot(b.x - bx, b.y - by));
        const rot = (a, d) => [bx + (dx * Math.cos(a) - dy * Math.sin(a)) * d, by + (dx * Math.sin(a) + dy * Math.cos(a)) * d];
        let alvos;
        if (cobranca === "escanteio") {
          const lado = Math.sign(dx * (CY - by) - dy * (CX - bx) + 0.01);
          alvos = [rot(0, 165), rot(0.75 * lado, 100)];
        } else alvos = [rot(-0.55, 120), rot(0.55, 150)];
        const m = RAIO_BOTAO + 12;
        for (let i = 0; i < Math.min(2, livres.length); i++) {
          livres[i].x = clamp(alvos[i][0], CAMPO.x0 + m, CAMPO.x1 - m);
          livres[i].y = clamp(alvos[i][1], CAMPO.y0 + m, CAMPO.y1 - m);
          livres[i].suave = 0.8;
        }
      }
      desencavalar(batedor);
      mostrarAviso(tipo, TIMES[time].nome, COR_BANNER[time], 1.3);
      depois(1.2, () => novaVez(time, false));
    }

    function cobrancaPenalti(time) {
      estado = "preparo";
      pararTudo();
      const def = 1 - time;
      const mx = linhaGol(def) + sentido(def) * MARCA_PEN;
      const dx = -sentido(def);             // da marca para o gol
      bola.x = mx; bola.y = CY; bola.suave = 0.6;
      const batedor = maisPerto(time, mx, CY);
      penaltiCobrador = batedor;
      if (batedor) {
        batedor.x = mx - dx * (RAIO_BOTAO + RAIO_BOLA + 42);
        batedor.y = CY;
        batedor.suave = 0.7;
      }
      // todo mundo para fora da área
      const borda = linhaGol(def) + sentido(def) * (AREA_P + 30);
      for (const t of [0, 1]) {
        for (const b of botoes[t]) {
          if (b.ativo && b !== batedor && naArea(b.x, b.y, def)) { b.x = borda; b.suave = 0.8; }
        }
      }
      goleiros[def].x = xGoleiro(def);
      goleiros[def].y = CY;
      desencavalar(batedor);
      cobranca = "penalti";
      api.som("apito");
      mostrarAviso("PÊNALTI!", `${TIMES[time].nome} vai cobrar`, "rgba(140,13,13,.85)", 1.8);
      depois(1.9, () => novaVez(time, false));
    }

    function tempoEsgotado() {
      estado = "evento";
      api.efeitos.texto("TEMPO!", api.W / 2, api.H / 2, { cor: VERMELHO, tamanho: 40 });
      api.som("erro");
      // o tempo acabou: a cobrança se perde
      cobranca = "";
      depois(0.8, () => passarVez(vez));
    }

    function gol(time) {
      estado = "evento";
      placar[time] += 1;
      // gol contra só quando o próprio time chutou para o seu gol
      const chutou = jogada.botao;
      let autor = "";
      if (chutou && chutou.time !== time) autor = "GOL CONTRA";
      else if (chutou && jogada.tocou) autor = `nº ${chutou.numero}`;
      else if (ultimoBotaoBola && ultimoBotaoBola.time === time && ultimoBotaoBola.tipo === BOTAO) autor = `nº ${ultimoBotaoBola.numero}`;
      api.som("strike");
      depois(0.5, () => api.som("combo"));
      mostrarAviso("GOOOOL!", `${TIMES[time].nome}  ${autor}`, COR_BANNER[time], 3.4, true);
      if (!api.reduzido) flash = { cor: TIMES[time].camisa, a: 0.55 };
      api.tremer(16);
      api.vibrar(160);
      torcidaPular(time, 1, 4.5);
      soltarConfete(time);
      soltarFogos(time);
      // os botões de quem fez o gol pulam de alegria
      for (const b of botoes[time]) if (b.ativo) { b.pulo = 0; b.puloAtraso = Math.random() * 0.1; }
      // quem marcou fica embalado
      embalo[time] = EMBALO_S;
      embalo[1 - time] = 0;
      atualizarPlacar(true);
      if (placar[time] >= GOLS_VITORIA || tempo <= 0) depois(4.0, fimDoTempo);
      else {
        depois(1.7, () => {
          api.efeitos.texto("EMBALADO!", api.W / 2, api.H * 0.72, { cor: LARANJA, tamanho: 30, vida: 1.2 });
          api.som("moeda");
        });
        depois(4.2, () => saidaDeBola(1 - time));
      }
    }

    function fimDoTempo() {
      if (estado === "fim") return;
      estado = "fim";
      mirando = null;
      ponteiro = null;
      carregando = false;
      cpu = null;
      dica = "";
      api.som("apito");
      depois(0.35, () => api.som("apito"));
      const venceu = placar[0] > placar[1], empate = placar[0] === placar[1];
      final = { t: 0, venceu, empate };
      aviso = null;
      if (venceu) {
        torcidaPular(0, 1, 5);
        soltarConfete(0);
        soltarFogos(0);
      } else if (!empate) torcidaPular(1, 1, 5);
      depois(venceu ? 3.4 : 2.8, encerrar);
    }

    function encerrar() {
      partidasJogadas += 1;
      const gols = placar[0];
      const venceu = placar[0] > placar[1], empate = placar[0] === placar[1];
      const bonus = venceu ? 300 : empate ? 100 : 0;
      const sobra = Math.ceil(tempo);
      const relampago = venceu && placar[0] >= GOLS_VITORIA && sobra > 0 ? sobra * 5 : 0;
      const pontos = gols * 100 + bonus + relampago;
      const partes = [`${gols} ${gols === 1 ? "gol" : "gols"} × 100`];
      if (venceu) partes.push("vitória +300");
      if (empate) partes.push("empate +100");
      if (relampago) partes.push(`${sobra} s de sobra +${relampago}`);
      api.terminar({
        pontos,
        titulo: venceu ? "Vitória do Brasil!" : empate ? "Empate!" : "A Argentina venceu",
        detalhe: `BRA ${placar[0]} x ${placar[1]} ARG · ${partes.join(" · ")}`,
      });
    }

    function atualizarPlacar(forcar) {
      const info = `BRA ${placar[0]} x ${placar[1]} ARG`;
      const s = Math.ceil(tempo);
      if (forcar || info !== placarMostrado) {
        placarMostrado = info;
        segundosMostrados = s;
        api.placar({ pontos: placar[0] * 100, tempo: s, info });
      } else if (s !== segundosMostrados) {
        segundosMostrados = s;
        api.placar({ tempo: s });
      }
    }

    /* ================================================================= CPU
       (ia.gd) Para cada botão e cada ideia de jogada (chute a gol, conduzir
       a bola, afastar do perigo) calcula onde o botão precisa bater na bola
       e com que força, descarta o que acertaria um botão antes da bola
       (falta!) e escolhe a melhor; depois erra um pouco, como gente. */
    function bloqueado(ax, ay, bx, by, r, ig1, ig2, ig3) {
      for (const c of corpos) {
        if (!c.ativo || c === ig1 || c === ig2 || c === ig3) continue;
        if (c.meio > 0) {
          if (distSegSeg(ax, ay, bx, by, c.x, c.y - c.meio, c.x, c.y + c.meio) < r + c.raio) return c;
          continue;
        }
        pontoNoSegmento(c.x, c.y, ax, ay, bx, by, P);
        if (Math.hypot(P.x - c.x, P.y - c.y) < r + c.raio) return c;
      }
      return null;
    }

    function decidir(time, goleiroY) {
      const restantes = TOQUES - toques;
      const vmax = vmaxDe(time);
      const adv = 1 - time;
      const gx = linhaGol(adv), sent = sentido(time);
      const goleiroAdv = goleiros[adv];
      const fixo = cobradorFixo();
      const penalti = cobranca === "penalti";
      const meus = botoes[time].filter((c) => c.ativo && (!fixo || c === fixo));
      const ideias = [];
      const distGol = Math.hypot(bola.x - gx, bola.y - CY);
      for (const fy of [-0.72, -0.4, 0, 0.4, 0.72]) {
        const ax = gx + sent * 20, ay = CY + fy * GOL_MEIA;
        const l = Math.hypot(ax - bola.x, ay - bola.y) || 1;
        ideias.push({ dx: (ax - bola.x) / l, dy: (ay - bola.y) / l, dist: l + 120, tipo: "chute", ax, ay });
      }
      if (restantes > 1 && !penalti) {
        for (const a of [0, 0.35, -0.35, 0.7, -0.7]) {
          for (const d of [150, 240]) {
            const dx = Math.cos(a) * sent, dy = Math.sin(a);
            ideias.push({ dx, dy, dist: d, tipo: "conduzir", ax: bola.x + dx * d, ay: bola.y + dy * d });
          }
        }
      }
      // bola perto do próprio gol: afastar para os lados/frente
      const perigo = naArea(bola.x, bola.y, time) || Math.abs(bola.x - linhaGol(time)) < 260;
      if (perigo) {
        for (const a of [0.6, -0.6, 0.3, -0.3]) {
          const dx = Math.cos(a) * sent, dy = Math.sin(a);
          ideias.push({ dx, dy, dist: 520, tipo: "afastar", ax: bola.x + dx * 520, ay: bola.y + dy * 520 });
        }
      }
      const rb = RAIO_BOTAO + RAIO_BOLA;
      const candidatos = [];
      for (const b of meus) {
        for (const ideia of ideias) {
          const m = mirar(b.x, b.y, bola.x, bola.y, ideia.dx, ideia.dy, rb);
          if (!m || m.cos < 0.2 || m.erro > 0.06) continue;
          const cx = b.x + m.ux * m.D, cy = b.y + m.uy * m.D;
          if (bloqueado(b.x, b.y, cx, cy, RAIO_BOTAO, b, bola, null)) continue;   // falta!
          if (ideia.tipo !== "chute" && !dentroDoCampo(ideia.ax, ideia.ay, -8)) continue;
          let vBola = velocidadeBola(ideia.dist);
          if (ideia.tipo === "chute") vBola = Math.max(vBola * 1.15, 700);
          const vContato = vBola / (GANHO_BOLA * m.cos);
          let v0 = Math.sqrt(vContato * vContato + 2 * ATRITO_BOTAO * m.D);
          let fraco = 0;
          if (v0 > vmax) { fraco = (v0 - vmax) / vmax; v0 = vmax; }
          let nota;
          if (ideia.tipo === "chute") {
            const livre = bloqueado(bola.x, bola.y, ideia.ax, ideia.ay, RAIO_BOLA, bola, b, goleiroY !== null ? goleiroAdv : null);
            nota = 70 - distGol * 0.06;
            if (livre) nota -= livre !== goleiroAdv ? 45 : 35;
            if (goleiroY !== null && Math.abs(ideia.ay - goleiroY) < 44) nota -= 40;
            if (restantes <= 1) nota += 18;
            nota -= fraco * 90;
          } else if (ideia.tipo === "conduzir") {
            nota = 28 + (ideia.ax - bola.x) * sent * 0.06;
            let perto = 999;
            for (const c of corpos) if (c.ativo && c.time === adv) perto = Math.min(perto, Math.hypot(c.x - ideia.ax, c.y - ideia.ay));
            nota += Math.min(perto, 160) * 0.12;
            nota -= fraco * 60;
          } else nota = 40 + (perigo ? 22 : 0) - fraco * 40;
          nota -= (1 - m.cos) * 25 + m.D * 0.02;
          candidatos.push({ botao: b, vx: m.ux * v0, vy: m.uy * v0, nota, tipo: ideia.tipo });
        }
      }
      if (!candidatos.length) return reposicionar(time, meus);
      candidatos.sort((a, b) => b.nota - a.nota);
      // às vezes a máquina pega a 2ª ou 3ª melhor ideia
      let idx = 0;
      if (DIFICULDADE === 0 && candidatos.length > 2 && Math.random() < 0.45) idx = 1 + Math.floor(Math.random() * 2);
      else if (DIFICULDADE === 1 && candidatos.length > 1 && Math.random() < 0.2) idx = 1;
      return errar(candidatos[idx], time);
    }

    /* Sem jogada boa: leva um botão para perto da bola (entre ela e o gol). */
    function reposicionar(time, meus) {
      let melhor = null, md = 1e9;
      for (const b of meus) {
        const d = Math.hypot(b.x - bola.x, b.y - bola.y);
        if (d < md) { md = d; melhor = b; }
      }
      if (!melhor) return null;
      const gx = linhaGol(time) - bola.x, gy = CY - bola.y, gl = Math.hypot(gx, gy) || 1;
      const ax = bola.x + (gx / gl) * 70, ay = bola.y + (gy / gl) * 70;
      let dx = ax - melhor.x, dy = ay - melhor.y, dist = Math.hypot(dx, dy);
      if (dist < 5) { dx = sentido(time); dy = 0; dist = 60; } else { dx /= dist; dy /= dist; }
      const v0 = clamp(Math.sqrt(2 * ATRITO_BOTAO * dist * 0.9), VMIN, VMAX * 0.7);
      return errar({ botao: melhor, vx: dx * v0, vy: dy * v0, nota: 0, tipo: "posicionar" }, time);
    }

    function errar(esc, time) {
      const erroAng = [0.075, 0.035, 0.014][DIFICULDADE];
      const erroV = [0.16, 0.08, 0.035][DIFICULDADE];
      const fator = PARAMS[time][embalo[time] > 0 ? 1 : 0].erroCpu * ERRO_MINI;
      const g = gauss() * erroAng * fator;
      const k = 1 + gauss() * erroV * fator;
      let vx = (esc.vx * Math.cos(g) - esc.vy * Math.sin(g)) * k;
      let vy = (esc.vx * Math.sin(g) + esc.vy * Math.cos(g)) * k;
      const v = Math.hypot(vx, vy), vmax = vmaxDe(time);
      if (v > vmax) { vx *= vmax / v; vy *= vmax / v; }
      esc.vx = vx;
      esc.vy = vy;
      return esc;
    }

    /* Jogada de reserva (instantânea): o botão mais perto bate na bola na
       direção do gol adversário, com força média. */
    function decisaoSimples() {
      let b = cobradorFixo();
      if (!b) b = listaEscolha(vez)[0];
      if (!b) return null;
      const gx = linhaGol(1 - vez) - bola.x, gy = CY - bola.y, gl = Math.hypot(gx, gy) || 1;
      const px = bola.x - (gx / gl) * (RAIO_BOLA + RAIO_BOTAO) * 0.6, py = bola.y - (gy / gl) * (RAIO_BOLA + RAIO_BOTAO) * 0.6;
      let dx = px - b.x, dy = py - b.y;
      const l = Math.hypot(dx, dy);
      if (l < 0.001) { dx = gx / gl; dy = gy / gl; } else { dx /= l; dy /= l; }
      const v = lerp(VMIN, vmaxDe(vez), 0.62);
      return { botao: b, vx: dx * v, vy: dy * v, tipo: "simples" };
    }

    /* Onde o goleiro balançando do pênalti está no instante "quando". */
    const goleiroPenaltiY = (quando) => CY + Math.sin(quando * (1.5 + DIFICULDADE * 0.35)) * (GOL_MEIA - 16) * 0.85;

    function cpuPensar(dt) {
      cpu.t += dt;
      if (!cpu.pensou) {
        cpu.pensou = true;
        // no pênalti a CPU mira onde o goleiro NÃO vai estar quando a bola chegar
        const gy = cobranca === "penalti" ? goleiroPenaltiY(relogio + Math.max(0, cpu.pensar - cpu.t) + 1.45) : null;
        cpu.decisao = decidir(vez, gy);
      }
      if (cpu.t < cpu.pensar) return;
      let d = cpu.decisao;
      if (!d || !d.botao.ativo) { d = decisaoSimples(); cpu.decisao = d; }
      if (!d) {
        cpu = null;
        estado = "evento";
        depois(0.3, () => passarVez(vez));
        return;
      }
      // mostra a jogada como um jogador: escolhe, gira a seta, enche a barra
      if (cpu.inicioMira < 0) {
        cpu.inicioMira = cpu.t;
        cpu.ang0 = Math.atan2(bola.y - d.botao.y, bola.x - d.botao.x);
        api.som("clique");
      }
      if (cpu.t - cpu.inicioMira >= 1.2) {
        const b = d.botao;
        cpu = null;
        chutar(b, d.vx, d.vy);
      }
    }

    /* ============================================================= GOLEIROS
       Na vez de jogar o goleiro "caixinha" se põe entre a bola e o gol;
       no pênalti ele balança (acerte o canto na hora certa!). O seu goleiro
       obedece ↑/↓ na vez da máquina. */
    function posicionarGoleiros(dt) {
      for (let t = 0; t < 2; t++) {
        const g = goleiros[t];
        const lim = GOL_MEIA - g.meio * 0.55;
        const antes = g.y;
        const vel = PARAMS[t][0].goleiroVel;
        const meuNaVezDoOutro = t !== vez && humano[t];
        let mov = 0;
        if (meuNaVezDoOutro) {
          if (teclas.cima) mov -= 1;
          if (teclas.baixo) mov += 1;
          if (mov !== 0) goleiroManual = true;
        }
        if (goleiroManual && meuNaVezDoOutro) {
          // soltou: ele fica onde foi deixado
          if (mov === 0) continue;
          g.y = clamp(g.y + mov * vel * 1.25 * dt, CY - lim, CY + lim);
        } else if (cobranca === "penalti" && t !== vez) {
          g.y = goleiroPenaltiY(relogio);
          continue;
        } else {
          const alvo = CY + clamp((bola.y - CY) * 0.5, -lim, lim);
          const passo = vel * dt;
          g.y = Math.abs(alvo - g.y) <= passo ? alvo : g.y + Math.sign(alvo - g.y) * passo;
        }
        // não entra por cima da bola nem de botões
        for (const c of corpos) {
          if (c === g || !c.ativo) continue;
          const qy = clamp(c.y, g.y - g.meio, g.y + g.meio);
          if (Math.hypot(c.x - g.x, c.y - qy) < g.raio + c.raio) { g.y = antes; break; }
        }
      }
    }

    /* ============================================================== EFEITOS */
    function mostrarAviso(txt, sub, cor, dur, grande = false) {
      aviso = { txt, sub, cor, dur, grande, t: 0 };
    }

    function torcidaPular(time, forca, dur) {
      torcida.alvo[time] = forca;
      torcida.vel = 2.6;
      torcida.calma = dur;
    }

    function soltarConfete(time) {
      confete = { resta: 2.5, time, acumulado: 0 };
    }

    function soltarFogos(time) {
      for (let k = 0; k < 6; k++) fogos.push({ t: 0.15 + k * 0.35, time, k });
    }

    function explodirFogo(f) {
      const x = f.time === 0 ? api.aleatorio(60, 600) : api.aleatorio(680, 1220);
      const y = api.aleatorio(20, 70);
      const n = api.reduzido ? 10 : 28;
      const tex = estrelas[f.time][f.k % 2];
      for (let i = 0; i < n; i++) {
        const p = particula();
        const g = Math.random() * TAU, v = 170 * (1 - 0.4 * Math.random());
        p.x = x; p.y = y; p.vx = Math.cos(g) * v; p.vy = Math.sin(g) * v;
        p.vida = p.total = 1.1; p.tam = 28 * (1 - 0.4 * Math.random()); p.img = tex; p.aditivo = true;
        p.grav = 60; p.amort = 60;
      }
      api.som("tiro");
    }

    function faisca(x, y) {
      const p = particula();
      p.x = x; p.y = y; p.vx = 0; p.vy = 0;
      p.vida = p.total = 0.25; p.tam = 26; p.cresce = 52; p.img = estrelaBranca; p.aditivo = true;
    }

    function atualizarEfeitos(dt) {
      if (aviso) {
        aviso.t += dt;
        if (aviso.t > aviso.dur + 0.3) aviso = null;
      }
      if (flash) {
        flash.a -= dt * 2.5;
        if (flash.a <= 0) flash = null;
      }
      if (final) final.t += dt;
      for (let l = 0; l < 2; l++) {
        if (rede[l] >= 0) { rede[l] += dt; if (rede[l] > 1.8) rede[l] = -1; }
      }
      // torcida: o lado que comemora pula alto, depois acalma
      if (torcida.calma > 0) {
        torcida.calma -= dt;
        if (torcida.calma <= 0) { torcida.alvo[0] = torcida.alvo[1] = 0.15; torcida.vel = 1; }
      }
      for (let i = 0; i < 2; i++) torcida.pulo[i] = lerp(torcida.pulo[i], torcida.alvo[i], Math.min(1, dt * 4));
      for (let i = 0; i < 2; i++) if (embalo[i] > 0) embalo[i] = Math.max(0, embalo[i] - dt);
      // confete: duas cores do time, caindo do alto da tela inteira
      if (confete) {
        confete.resta -= dt;
        confete.acumulado += dt * (api.reduzido ? 12 : 44);
        while (confete.acumulado >= 1) {
          confete.acumulado -= 1;
          const p = particula();
          const g = Math.PI / 2 + (Math.random() * 2 - 1) * 25 * GRAU, v = 160 * (1 - 0.6 * Math.random());
          p.x = api.aleatorio(-20, 1300); p.y = -20; p.vx = Math.cos(g) * v; p.vy = Math.sin(g) * v;
          p.vida = p.total = 3.2; p.img = confetes[confete.time][Math.random() < 0.5 ? 0 : 1];
          p.aditivo = false; p.grav = 160; p.confete = true;
          const s = 0.9 * (1 - 0.5 * Math.random()) * 1.4;
          p.larg = 16 * s; p.alt = 10 * s;
          p.giro = Math.random() * TAU; p.vgiro = 300 * GRAU * (Math.random() * 2 - 1);
        }
        if (confete.resta <= 0) confete = null;
      }
      for (let i = fogos.length - 1; i >= 0; i--) {
        fogos[i].t -= dt;
        if (fogos[i].t <= 0) { explodirFogo(fogos[i]); fogos.splice(i, 1); }
      }
      for (const p of parts) {
        if (!p.vivo) continue;
        p.vida -= dt;
        if (p.vida <= 0) { p.vivo = false; continue; }
        if (p.amort > 0) {
          const v = Math.hypot(p.vx, p.vy);
          if (v > 0) { const nv = Math.max(0, v - p.amort * dt); p.vx *= nv / v; p.vy *= nv / v; }
        }
        p.vy += p.grav * dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.giro += p.vgiro * dt;
      }
      // peças deslizando até a posição nova (cobrança posicionada) e pulando
      for (const c of corpos) {
        if (c.suave > 0) {
          c.suave -= dt;
          const k = Math.min(1, dt * 10);
          c.dx += (c.x - c.dx) * k;
          c.dy += (c.y - c.dy) * k;
        } else { c.dx = c.x; c.dy = c.y; }
        if (c.pulo >= 0) { c.pulo += dt; if (c.pulo > 1.8) c.pulo = -1; }
        if (c.sumir > 0 && !c.ativo) c.sumir = Math.max(0, c.sumir - dt * 2);
        if (c.cartao < 1) c.cartao = Math.min(1, c.cartao + dt / 0.45);
      }
      const vb = Math.hypot(bola.vx, bola.vy);
      if (vb > 1) bola.giro += ((vb * dt) / bola.raio) * Math.sign(bola.vx + 0.001);
      // rastro da bola rápida
      if (vb > 260 && estado === "movendo") {
        rastro.push(bola.x, bola.y);
        if (rastro.length > 24) rastro.splice(0, 2);
      } else if (rastro.length) rastro.splice(0, 2);
    }

    /* ============================================================ CONTROLES */
    function soltarChuteTeclado() {
      const f = valorBarra();
      const b = sel;
      carregando = false;
      if (!b) return;
      const v = velocidadeDaForca(vez, f);
      chutar(b, Math.cos(ang) * v, Math.sin(ang) * v);
    }

    /* Segurar ←/→ gira a mira cada vez mais rápido; a barra corre. */
    function teclado(dt) {
      if (!sel || mirando) return;
      const giro = (teclas.dir ? 1 : 0) - (teclas.esq ? 1 : 0);
      if (giro !== 0) {
        tGirar += dt;
        const vel = tGirar < 0.3 ? 28 * GRAU : Math.min(200, 28 + (tGirar - 0.3) * 320) * GRAU;
        ang += giro * vel * dt;
      } else tGirar = 0;
      if (carregando) {
        tCarga += dt;
        // ninguém segura o chute para sempre: chuta com a força do momento
        if (tCarga > 8) soltarChuteTeclado();
      }
    }

    function naMesa(x, y) { PT.x = x / K; PT.y = y / K; return PT; }

    const celularEmPe = () => typeof window !== "undefined" && window.innerHeight > window.innerWidth && window.innerWidth < 700;

    /* ============================================================== DESENHO */
    function desenharTorcida(ctx, dtv) {
      const im = torcidaPronta || img.torcida;
      if (!im) return;
      torcida.fase = (torcida.fase + dtv * 5.5 * torcida.vel) % TAU;
      ctx.save();
      if (!torcidaPronta) ctx.globalCompositeOperation = "lighter";
      // quatro grupos de torcedores, cada um no seu tempo de pulo; a metade
      // da esquerda torce pelo Brasil, a da direita pela Argentina
      for (let g = 0; g < 4; g++) {
        const onda = Math.max(0, Math.sin(torcida.fase + ((g + 0.5) / 4) * TAU));
        const dyC = -onda * torcida.pulo[0] * 5;
        const dyF = -onda * torcida.pulo[1] * 5;
        ctx.drawImage(im, 0, g * 80, 640, 78, 0, dyC, 640, 78);
        ctx.drawImage(im, 640, g * 80, 640, 78, 640, dyF, 640, 78);
        ctx.drawImage(im, g * 176, 320, 86, 634, 0, 78 + dyC, 86, 634);
        ctx.drawImage(im, g * 176 + 88, 320, 86, 634, 1194, 78 + dyF, 86, 634);
      }
      ctx.restore();
    }

    function desenharRedes(ctx) {
      const im = img.rede;
      if (!im) return;
      for (let l = 0; l < 2; l++) {
        let bal = 0;
        const u = rede[l];
        if (u >= 0) bal = Math.max(Math.exp(-u * 3) * Math.cos(u * 12), -0.2);
        const sx = 0.5 * (1 + 0.35 * bal);
        ctx.save();
        // estufa para fora do campo: a boca do gol fica no lugar
        if (l === 0) { ctx.translate(CAMPO.x0 + 4, CY - GOL_MEIA - 8); ctx.scale(-sx, 0.5); }
        else { ctx.translate(CAMPO.x1 - 4, CY - GOL_MEIA - 8); ctx.scale(sx, 0.5); }
        ctx.drawImage(im, 0, 0);
        ctx.restore();
      }
    }

    function escalaPulo(c) {
      if (c.pulo < 0) return 1;
      for (let k = 0; k < 3; k++) {
        const tk = c.pulo - (0.4 + k * 0.4 + c.puloAtraso);
        if (tk >= 0 && tk < 0.36) return 1 + 0.25 * Math.sin((tk / 0.36) * Math.PI);
      }
      return 1;
    }

    function desenharPecas(ctx) {
      const somb = img.sombra;
      // sombras primeiro: nenhuma sombra por cima de peça
      if (somb) {
        ctx.globalAlpha = 0.55;
        for (const c of corpos) {
          if (!c.ativo && c.sumir <= 0) continue;
          if (c.tipo === BOTAO) {
            const s = RAIO_BOTAO * 2 * 1.55;
            ctx.drawImage(somb, c.dx + 3 - s / 2, c.dy + 5 - s / 2, s, s);
          } else if (c.tipo === GOLEIRO) {
            const w = (GOLEIRO_RAIO + 2) * 2 * 1.4, h = (c.meio + GOLEIRO_RAIO + 2) * 2 * 1.25;
            ctx.drawImage(somb, c.dx + 3 - w / 2, c.dy + 5 - h / 2, w, h);
          } else {
            const s = RAIO_BOLA * 2.3 * 1.5;
            ctx.drawImage(somb, c.dx + 2 - s / 2, c.dy + 3 - s / 2, s, s);
          }
        }
        ctx.globalAlpha = 1;
      }
      // rastro da bola
      if (rastro.length >= 4) {
        ctx.lineCap = "round";
        ctx.lineWidth = 9;
        ctx.strokeStyle = "#fff";
        const n = rastro.length / 2;
        for (let i = 1; i < n; i++) {
          ctx.globalAlpha = (i / n) * 0.45;
          ctx.beginPath();
          ctx.moveTo(rastro[i * 2 - 2], rastro[i * 2 - 1]);
          ctx.lineTo(rastro[i * 2], rastro[i * 2 + 1]);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
      // goleiros caixinha
      for (let t = 0; t < 2; t++) {
        const g = goleiros[t], im = img[TIMES[t].goleiro];
        const w = (GOLEIRO_RAIO + 2) * 2, h = (g.meio + GOLEIRO_RAIO + 2) * 2;
        if (im) ctx.drawImage(im, g.dx - w / 2, g.dy - h / 2, w, h);
      }
      // botões
      const vezHumana = estado === "vez" && humano[vez];
      const fixo = estado === "vez" ? cobradorFixo() : null;
      const cpuSel = cpu && cpu.inicioMira >= 0 && cpu.decisao ? cpu.decisao.botao : null;
      for (let t = 0; t < 2; t++) {
        const im = img[TIMES[t].botao];
        for (const b of botoes[t]) {
          if (!b.ativo && b.sumir <= 0) continue;
          const d = RAIO_BOTAO * 2;
          const x = b.dx, y = b.dy;
          if (!b.ativo) ctx.globalAlpha = b.sumir;
          // embalado: brilho na cor do time pulsando
          if (embalo[t] > 0 && b.ativo && aura[t]) {
            ctx.save();
            ctx.globalCompositeOperation = "lighter";
            ctx.globalAlpha = 0.45 + Math.sin(anim * 7 + b.slot) * 0.2;
            const s = d * 2.6;
            ctx.drawImage(aura[t], x - s / 2, y - s / 2, s, s);
            ctx.restore();
          }
          // anel: a vez é sua (branco) ou o botão escolhido (amarelo)
          const escolhido = (vezHumana && (b === mirando || (modoTeclado && b === sel))) || b === cpuSel || (fixo && b === fixo);
          const destaque = vezHumana && t === vez && b.ativo && (!fixo || b === fixo);
          if ((escolhido || destaque) && img.anel) {
            const base = d * 1.9;
            const s = escolhido ? base * (1.08 + Math.sin(anim * 8) * 0.1) : base * (1 + Math.sin(anim * 5) * 0.05);
            ctx.save();
            ctx.globalAlpha = escolhido ? 1 : 0.55;
            ctx.drawImage(escolhido && anelAmarelo ? anelAmarelo : img.anel, x - s / 2, y - s / 2, s, s);
            ctx.restore();
          }
          const s = d * escalaPulo(b);
          if (im) ctx.drawImage(im, x - s / 2, y - s / 2, s, s);
          if (b.amarelos > 0) desenharCartao(ctx, b);
          ctx.globalAlpha = 1;
        }
      }
      // bola
      if (img.bola) {
        const s = RAIO_BOLA * 2.3;
        ctx.save();
        ctx.translate(bola.dx, bola.dy);
        ctx.rotate(bola.giro);
        ctx.drawImage(img.bola, -s / 2, -s / 2, s, s);
        ctx.restore();
      }
    }

    /* Cartão amarelo preso na borda do botão até o fim (cartao_tazo.gd). */
    function desenharCartao(ctx, b) {
      const r = RAIO_BOTAO;
      const k = b.cartao < 1 ? 1 + 1.4 * (1 - voltaAtras(b.cartao)) : 1;
      const h = r * 0.95, w = h * 0.7;
      ctx.save();
      ctx.translate(b.dx + r * 0.72, b.dy - r * 0.72);
      ctx.rotate(14 * GRAU);
      ctx.scale(k, k);
      ctx.fillStyle = "rgba(0,0,0,.35)";
      ctx.fillRect(-w / 2 + 2, -h / 2 + 2, w, h);
      ctx.fillStyle = "#ffd21f";
      ctx.strokeStyle = "#7a5a00";
      ctx.lineWidth = 1.5;
      retanguloRedondo(ctx, -w / 2, -h / 2, w, h, 3);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    /* GUIA DO PETELECO (mira.gd): pontilhado até onde o botão para, anel da
       força em volta do botão, seta, barra do manche e o elástico do dedo. */
    function desenharMira(ctx, x, y, dx, dy, f, v, barra, comDedo) {
      const r = RAIO_BOTAO;
      if (comDedo) {
        // o elástico do estilingue: do botão até o dedo
        ctx.save();
        ctx.lineCap = "round";
        ctx.strokeStyle = "rgba(0,0,0,.35)";
        ctx.lineWidth = 7;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(dedoX, dedoY); ctx.stroke();
        ctx.strokeStyle = "rgba(255,255,255,.75)";
        ctx.lineWidth = 3;
        ctx.setLineDash([8, 7]);
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(dedoX, dedoY); ctx.stroke();
        ctx.restore();
      }
      if (v > 0) {
        // pontilhado: até onde o botão para (sem contar choques)
        const dist = (v * v) / (2 * ATRITO_BOTAO);
        let d = r + 16;
        ctx.fillStyle = "#fff";
        for (let i = 0; d < dist && i < 60; i++) {
          const px = x + dx * d, py = y + dy * d;
          if (px < MURO.x0 || px > MURO.x1 || py < MURO.y0 || py > MURO.y1) break;
          ctx.globalAlpha = 0.85 * (1 - d / Math.max(dist, 1)) + 0.1;
          ctx.beginPath();
          ctx.arc(px, py, 3, 0, TAU);
          ctx.fill();
          d += 18;
        }
        ctx.globalAlpha = 1;
      }
      ctx.lineWidth = 7;
      ctx.strokeStyle = "rgba(0,0,0,.45)";
      ctx.beginPath();
      ctx.arc(x, y, r + 9, 0, TAU);
      ctx.stroke();
      const cor = corForca(f);
      if (f > 0.01) {
        ctx.lineWidth = 5;
        ctx.lineCap = "round";
        ctx.strokeStyle = cor;
        ctx.beginPath();
        ctx.arc(x, y, r + 9, -Math.PI / 2, -Math.PI / 2 + TAU * f);
        ctx.stroke();
      }
      if (v > 0) {
        const base = r + 6, ponta = r + 26 + 60 * Math.max(f, 0.25);
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(Math.atan2(dy, dx));
        ctx.lineCap = "round";
        ctx.strokeStyle = "rgba(0,0,0,.5)";
        ctx.lineWidth = 11;
        ctx.beginPath(); ctx.moveTo(base, 0); ctx.lineTo(ponta, 0); ctx.stroke();
        ctx.strokeStyle = cor;
        ctx.lineWidth = 6;
        ctx.beginPath(); ctx.moveTo(base, 0); ctx.lineTo(ponta, 0); ctx.stroke();
        ctx.fillStyle = cor;
        ctx.beginPath(); ctx.moveTo(ponta + 14, 0); ctx.lineTo(ponta - 4, 11); ctx.lineTo(ponta - 4, -11); ctx.closePath(); ctx.fill();
        ctx.restore();
      }
      if (barra) {
        // barra de força ao lado do botão, do lado oposto à seta
        const lado = dx <= 0 ? 1 : -1;
        const bx = x + lado * (r + 30), by0 = y + 38, alt = 76, larg = 14;
        ctx.fillStyle = "rgba(0,0,0,.7)";
        ctx.fillRect(bx - larg / 2 - 3, by0 - alt - 3, larg + 6, alt + 6);
        const fatias = 12, cheio = Math.ceil(f * fatias);
        for (let k = 0; k < fatias; k++) {
          ctx.globalAlpha = k >= cheio ? 0.18 : 1;
          ctx.fillStyle = corForca(k / (fatias - 1));
          ctx.fillRect(bx - larg / 2, by0 - (alt * (k + 1)) / fatias + 1, larg, alt / fatias - 1);
        }
        ctx.globalAlpha = 1;
        const ny = by0 - alt * f;
        ctx.fillStyle = "#fff";
        ctx.beginPath(); ctx.moveTo(bx - larg / 2 - 7, ny - 4); ctx.lineTo(bx - larg / 2 - 1, ny); ctx.lineTo(bx - larg / 2 - 7, ny + 4); ctx.fill();
        ctx.beginPath(); ctx.moveTo(bx + larg / 2 + 7, ny - 4); ctx.lineTo(bx + larg / 2 + 1, ny); ctx.lineTo(bx + larg / 2 + 7, ny + 4); ctx.fill();
      }
      if (comDedo) {
        const pulso = 0.5 + 0.2 * Math.sin(anim * 8);
        const g = ctx.createRadialGradient(dedoX, dedoY, 0, dedoX, dedoY, 18);
        g.addColorStop(0, `rgba(255,255,255,${pulso})`);
        g.addColorStop(1, "rgba(255,255,255,0)");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(dedoX, dedoY, 18, 0, TAU); ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,.95)";
        ctx.beginPath(); ctx.arc(dedoX, dedoY, 5, 0, TAU); ctx.fill();
      }
    }

    function desenharGuia(ctx) {
      if (estado !== "vez") return;
      if (humano[vez]) {
        if (mirando) {
          const r = forcaDoToque(mirando, dedoX, dedoY);
          if (r.dist < PUXAO_MIN) desenharMira(ctx, mirando.x, mirando.y, r.dx, r.dy, 0, 0, false, true);
          else desenharMira(ctx, mirando.x, mirando.y, r.dx, r.dy, r.f, r.v, false, true);
        } else if (modoTeclado && sel) {
          // sem carregar: só a direção (pontilhado de meia força)
          const f = carregando ? valorBarra() : 0;
          const v = carregando ? velocidadeDaForca(vez, f) : velocidadeDaForca(vez, 0.45);
          desenharMira(ctx, sel.x, sel.y, Math.cos(ang), Math.sin(ang), f, v, carregando, false);
        }
      } else if (cpu && cpu.inicioMira >= 0 && cpu.decisao) {
        // a máquina "pensa alto": gira a seta até a mira e enche a barra
        const d = cpu.decisao, b = d.botao;
        const k = cpu.t - cpu.inicioMira;
        const v = Math.hypot(d.vx, d.vy), vmax = vmaxDe(vez);
        const f = clamp(Math.pow(Math.max(v - VMIN, 0) / (vmax - VMIN), 1 / 1.1), 0, 1);
        const alvo = Math.atan2(d.vy, d.vx);
        const delta = ((((alvo - cpu.ang0 + Math.PI) % TAU) + TAU) % TAU) - Math.PI;
        const a = cpu.ang0 + delta * clamp(k / 0.4, 0, 1);
        const carga = clamp((k - 0.4) / 0.8, 0, 1) * f;
        const vel = k > 0.4 ? velocidadeDaForca(vez, Math.max(carga, 0.04)) : velocidadeDaForca(vez, 0.45);
        desenharMira(ctx, b.x, b.y, Math.cos(a), Math.sin(a), carga, vel, k > 0.4, false);
      }
    }

    function painel(ctx, x, y, w, h, r, fundo, borda) {
      retanguloRedondo(ctx, x, y, w, h, r);
      ctx.fillStyle = fundo;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = borda;
      ctx.stroke();
    }

    /* Placar de TV em cima, como na máquina: confronto no meio, caixa de
       cada time dos lados (vez, toques, relógio da vez, embalado). */
    function desenharHud(ctx) {
      painel(ctx, 448, 4, 384, 70, 14, "rgba(5,13,31,.92)", "rgba(255,255,255,.85)");
      for (let t = 0; t < 2; t++) {
        const band = img[TIMES[t].bandeira];
        if (band) ctx.drawImage(band, t === 0 ? 460 : 769, 12, 51, 34);
        api.texto(ctx, TIMES[t].sigla, t === 0 ? 550 : 730, 30, { tamanho: 23, cor: "#fff", peso: 900 });
        api.texto(ctx, String(placar[t]), t === 0 ? 607 : 673, 28, { tamanho: 40, cor: AMARELO, peso: 900, contorno: "rgba(0,0,0,.5)" });
      }
      api.texto(ctx, "x", 640, 28, { tamanho: 24, cor: "rgba(255,255,255,.8)", peso: 800 });
      const s = Math.max(0, Math.ceil(tempo));
      const relogioTxt = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
      api.texto(ctx, relogioTxt, 640, 59, { tamanho: 17, cor: s <= 10 && s > 0 ? "#ff8080" : "#cdf2ff", peso: 800 });

      for (let t = 0; t < 2; t++) {
        const x = t === 0 ? 10 : 940, w = 330, esq = t === 0;
        const minha = (estado === "vez" || estado === "movendo") && vez === t;
        ctx.save();
        ctx.globalAlpha = minha ? 1 : 0.6;
        painel(ctx, x, 6, w, 62, 14, "rgba(5,13,31,.88)", TIMES[t].camisa);
        const xt = esq ? x + 14 : x + w - 14;
        api.texto(ctx, TIMES[t].nome, xt, 21, { tamanho: 19, cor: "#fff", peso: 900, alinhar: esq ? "left" : "right" });
        if (embalo[t] > 0) {
          const pulso = 1 + Math.sin(anim * 6) * 0.06;
          api.texto(ctx, "EMBALADO!", esq ? x + w - 14 : x + 14, 21, { tamanho: 16 * pulso, cor: LARANJA, peso: 900, alinhar: esq ? "right" : "left" });
        }
        if (estado === "vez" && vez === t) {
          const txt = humano[t] ? "SUA VEZ!" : demo ? "JOGANDO..." : "MÁQUINA JOGANDO...";
          api.texto(ctx, txt, xt, 44, { tamanho: 17, cor: AMARELO, peso: 900, alinhar: esq ? "left" : "right" });
          // relógio da vez: a faixa encolhe (vermelha nos últimos 5 s)
          const k = clamp(relogioVez / RELOGIO_VEZ, 0, 1);
          ctx.fillStyle = relogioVez > 5 ? TIMES[t].camisa : VERMELHO;
          ctx.fillRect(x + 14, 59, 302 * k, 3);
        }
        if (minha && cobranca !== "penalti") {
          // bolinhas dos toques: cheia = toque já usado nesta vez
          for (let i = 0; i < TOQUES; i++) {
            const cx = esq ? x + w - 22 - i * 22 : x + 22 + i * 22;
            ctx.beginPath();
            ctx.arc(cx, 44, 7, 0, TAU);
            if (i < toques) { ctx.fillStyle = "#fff"; ctx.fill(); }
            else { ctx.lineWidth = 2.5; ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.stroke(); }
          }
        }
        ctx.restore();
      }
    }

    function desenharAviso(ctx) {
      if (!aviso) return;
      const t = aviso.t;
      let alfa = Math.min(1, t / 0.15);
      if (t > aviso.dur) alfa = Math.max(0, 1 - (t - aviso.dur) / 0.25);
      const sy = Math.max(0.001, voltaAtras(clamp(t / 0.25, 0, 1)));
      const st = 1.6 - 0.6 * voltaAtras(clamp(t / 0.4, 0, 1));
      ctx.save();
      ctx.globalAlpha = alfa;
      ctx.save();
      ctx.translate(640, 365);
      ctx.scale(1, sy);
      ctx.fillStyle = aviso.cor;
      ctx.fillRect(-640, -57, 1280, 114);
      ctx.fillStyle = "rgba(255,255,255,.35)";
      ctx.fillRect(-640, -57, 1280, 3);
      ctx.fillRect(-640, 54, 1280, 3);
      ctx.restore();
      ctx.translate(640, 352);
      ctx.scale(st, st);
      api.texto(ctx, aviso.txt, 0, 0, { tamanho: aviso.grande ? 104 : 72, cor: "#fff", peso: 900, contorno: "rgba(0,0,0,.6)" });
      ctx.restore();
      if (aviso.sub) {
        ctx.save();
        ctx.globalAlpha = alfa * 0.95;
        api.texto(ctx, aviso.sub, 640, 409, { tamanho: 22, cor: "#fff", peso: 800, contorno: "rgba(0,0,0,.5)" });
        ctx.restore();
      }
    }

    function desenharParticulas(ctx) {
      // normais primeiro (confete, poeira), depois as que brilham (somadas)
      for (let passada = 0; passada < 2; passada++) {
        const aditivo = passada === 1;
        if (aditivo) { ctx.save(); ctx.globalCompositeOperation = "lighter"; }
        for (const p of parts) {
          if (!p.vivo || p.aditivo !== aditivo || !p.img) continue;
          const k = p.vida / p.total;
          if (p.confete) {
            ctx.globalAlpha = Math.min(1, k * 4);
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.giro);
            ctx.scale(1, Math.abs(Math.cos(p.giro * 1.7)) * 0.8 + 0.2);   // vira no ar
            ctx.drawImage(p.img, -p.larg / 2, -p.alt / 2, p.larg, p.alt);
            ctx.restore();
          } else {
            ctx.globalAlpha = p.alfa * (p.cresce ? k : Math.min(1, k / 0.4));
            const s = p.tam + p.cresce * (1 - k);
            ctx.drawImage(p.img, p.x - s / 2, p.y - s / 2, s, s);
          }
        }
        ctx.globalAlpha = 1;
        if (aditivo) ctx.restore();
      }
    }

    /* Fim de jogo: a mesa escurece, o logo, o resultado e (na vitória) a
       taça subindo com a torcida em festa. */
    function desenharFinal(ctx) {
      const t = final.t;
      ctx.save();
      ctx.globalAlpha = Math.min(1, t / 0.4) * 0.62;
      ctx.fillStyle = "#030818";
      ctx.fillRect(0, 0, 1280, 720);
      ctx.restore();
      const entra = voltaAtras(clamp(t / 0.5, 0, 1));
      if (img.logo && entra > 0.01) {
        const w = 460 * entra, h = 171 * entra;
        ctx.drawImage(img.logo, 640 - w / 2, 118 - h / 2, w, h);
      }
      const titulo = final.venceu ? "VITÓRIA!" : final.empate ? "EMPATE!" : "FIM DE JOGO";
      ctx.save();
      ctx.globalAlpha = clamp((t - 0.2) / 0.3, 0, 1);
      ctx.translate(640, 268);
      const st = 1.5 - 0.5 * voltaAtras(clamp((t - 0.2) / 0.4, 0, 1));
      ctx.scale(st, st);
      api.texto(ctx, titulo, 0, 0, { tamanho: 78, cor: final.venceu ? AMARELO : "#fff", peso: 900, contorno: "rgba(0,0,0,.7)" });
      ctx.restore();
      ctx.save();
      ctx.globalAlpha = clamp((t - 0.45) / 0.3, 0, 1);
      for (let i = 0; i < 2; i++) {
        const band = img[TIMES[i].bandeira];
        if (band) ctx.drawImage(band, i === 0 ? 346 : 858, 327, 76, 51);
      }
      api.texto(ctx, `BRA  ${placar[0]}  x  ${placar[1]}  ARG`, 640, 353, { tamanho: 50, cor: "#fff", peso: 900, contorno: "rgba(0,0,0,.6)" });
      ctx.restore();
      if (final.venceu && img.trofeu) {
        const k = voltaAtras(clamp((t - 0.6) / 0.6, 0, 1));
        const y = lerp(760, 440, k);
        if (aura[0]) {
          ctx.save();
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = 0.55 + Math.sin(anim * 4) * 0.15;
          ctx.drawImage(aura[0], 640 - 170, y - 58, 340, 340);
          ctx.restore();
        }
        ctx.drawImage(img.trofeu, 640 - 80, y, 160, 224);
      }
    }

    /* ============================================================ A PARTIDA */
    function zerar() {
      estado = "pronto";
      vez = 0; toques = 0; tempo = DURACAO; relogioVez = RELOGIO_VEZ;
      relogio = 0; tEstado = 0; estadoAnt = "";
      placar[0] = placar[1] = 0;
      embalo[0] = embalo[1] = 0;
      jogada = null;
      cobranca = ""; cobrador = null; penaltiCobrador = null;
      ultimoToque = -1; ultimoBotaoBola = null;
      tJogada = 0; pararEm = -1;
      agenda = [];
      primeiroToque = true;
      goleiroManual = false;
      for (const k in somPronto) delete somPronto[k];
      sel = null; ang = 0; carregando = false; tCarga = 0; tGirar = 0;
      mirando = null; ponteiro = null;
      teclas.cima = teclas.baixo = teclas.esq = teclas.dir = false;
      cpu = null;
      aviso = null; flash = null; dica = ""; final = null;
      rede[0] = rede[1] = -1;
      torcida.pulo[0] = torcida.pulo[1] = 0.15;
      torcida.alvo[0] = torcida.alvo[1] = 0.15;
      torcida.vel = 1; torcida.calma = 0;
      rastro.length = 0;
      confete = null; fogos = [];
      for (const p of parts) p.vivo = false;
      for (const c of corpos) {
        c.vx = 0; c.vy = 0; c.ativo = true; c.amarelos = 0; c.faltas = 0;
        c.suave = 0; c.pulo = -1; c.sumir = 0; c.giro = 0; c.cartao = 1;
      }
      for (const t of [0, 1]) {
        for (const b of botoes[t]) posicaoFormacao(b);
        goleiros[t].x = xGoleiro(t);
        goleiros[t].y = CY;
      }
      bola.x = CX; bola.y = CY;
      for (const c of corpos) { c.dx = c.x; c.dy = c.y; }
      placarMostrado = "";
      segundosMostrados = -1;
    }

    return {
      iniciar() {
        zerar();
        // uma partida na casa do Brasil, a seguinte na da Argentina
        estadio = (partidasJogadas % 2 === 0 ? img.estadioBra : img.estadioArg) || img.estadioBra;
        atualizarPlacar(true);
      },

      atualizar(dt) {
        relogio += dt;
        if (estado === "pronto") {
          // espera o "VAI!" do console sumir para apitar a saída
          estado = "preparo";
          depois(0.55, () => saidaDeBola(0));
        }
        atualizarEfeitos(dt);
        if (estado === "vez" || estado === "movendo") tempo = Math.max(0, tempo - dt);
        if (estado === "vez") {
          posicionarGoleiros(dt);
          relogioVez -= dt;
          if (humano[vez]) teclado(dt);
          else if (cpu) cpuPensar(dt);
          if (estado === "vez") {
            const ocupado = !!mirando || carregando;
            if (relogioVez <= 0 && carregando && sel) soltarChuteTeclado();
            else if (relogioVez <= 0 && mirando) {
              // o tempo acabou com o dedo puxando: chuta com a força do momento
              const b = mirando, r = forcaDoToque(b, dedoX, dedoY);
              mirando = null; ponteiro = null;
              if (r.dist >= PUXAO_MIN) chutar(b, r.dx * r.v, r.dy * r.v); else tempoEsgotado();
            } else if (relogioVez <= 0 && !ocupado) tempoEsgotado();
            else if (tempo <= 0 && !ocupado) fimDoTempo();
          }
        } else if (estado === "movendo") {
          tJogada += dt;
          passoFisica(dt);
          verificarBola();
          let fim = tudoParado();
          if (pararEm > 0 && tJogada >= pararEm) fim = true;
          if (tJogada > 9) fim = true;
          if (fim) {
            pararTudo();
            estado = "evento";
            resolver();
          }
        }
        rodarAgenda();
        // vigia: nenhum estado de passagem fica parado para sempre
        if (estado !== estadoAnt) { estadoAnt = estado; tEstado = 0; } else tEstado += dt;
        if ((estado === "evento" || estado === "preparo") && tEstado > 3 && agenda.length === 0) {
          pararTudo();
          novaVez(1 - vez, false);
        }
        atualizarPlacar(false);
      },

      desenhar(ctx) {
        const agora = performance.now();
        const dtv = ultimoQuadro ? Math.min(0.05, (agora - ultimoQuadro) / 1000) : 0;
        ultimoQuadro = agora;
        anim += dtv;
        ctx.save();
        ctx.scale(K, K);
        if (estadio) ctx.drawImage(estadio, 0, 0, 1280, 720);
        else { ctx.fillStyle = "#1d6b34"; ctx.fillRect(0, 0, 1280, 720); }
        desenharTorcida(ctx, dtv);
        desenharPecas(ctx);
        desenharRedes(ctx);
        if (!final) desenharGuia(ctx);
        if (!final) desenharHud(ctx);
        if (!final) desenharAviso(ctx);
        if (final) desenharFinal(ctx);
        desenharParticulas(ctx);
        if (dica && estado === "vez" && !final) {
          // celular em pé: a mesa deitada fica miúda, então a dica cresce e
          // sugere girar o aparelho
          const emPe = celularEmPe();
          ctx.save();
          ctx.globalAlpha = 0.75 + Math.sin(anim * 4) * 0.25;
          if (emPe && primeiroToque) api.texto(ctx, "GIRE O CELULAR PARA JOGAR MAIOR", 640, 612, { tamanho: 32, cor: AMARELO, peso: 900, contorno: "rgba(0,0,0,.75)" });
          api.texto(ctx, dica, 640, emPe ? 656 : 662, { tamanho: emPe ? 34 : 24, cor: "#fff", peso: 900, contorno: "rgba(0,0,0,.7)" });
          ctx.restore();
        }
        if (flash) {
          ctx.globalAlpha = Math.max(0, flash.a);
          ctx.fillStyle = flash.cor;
          ctx.fillRect(0, 0, 1280, 720);
          ctx.globalAlpha = 1;
        }
        ctx.restore();
      },

      apertar(x, y, id) {
        if (ponteiro !== null || estado !== "vez" || !humano[vez]) return;
        const p = naMesa(x, y);
        let melhor = null, md = RAIO_BOTAO * TOQUE_ALCANCE;
        let soCobrador = false;
        for (const b of botoes[vez]) {
          if (!b.ativo) continue;
          const d = Math.hypot(b.x - p.x, b.y - p.y);
          if (!podeJogar(b)) { if (d < md) soCobrador = true; continue; }
          if (d < md) { md = d; melhor = b; }
        }
        if (!melhor) {
          if (soCobrador) api.efeitos.texto("QUEM COBRA É O DESTACADO", x, y - 30, { cor: "#fff", tamanho: 18, vida: 0.9 });
          return;
        }
        ponteiro = id === undefined ? 0 : id;
        mirando = melhor;
        sel = melhor;
        modoTeclado = false;
        carregando = false;
        dedoX = p.x; dedoY = p.y;
        api.som("clique");
      },

      mover(x, y, id) {
        if (!mirando || (id !== undefined && id !== ponteiro)) return;
        const p = naMesa(x, y);
        dedoX = p.x; dedoY = p.y;
      },

      soltar(x, y, id) {
        if (!mirando || (id !== undefined && id !== ponteiro)) return;
        const p = naMesa(x, y);
        dedoX = p.x; dedoY = p.y;
        const b = mirando;
        mirando = null;
        ponteiro = null;
        if (estado !== "vez") return;
        const r = forcaDoToque(b, dedoX, dedoY);
        if (r.dist < PUXAO_MIN) {
          // soltou em cima do botão: desistiu (ou só tocou sem puxar)
          if (primeiroToque) api.efeitos.texto("PUXE PARA TRÁS!", b.x * K, (b.y - 50) * K, { cor: "#fff", tamanho: 22, vida: 0.9 });
          return;
        }
        chutar(b, r.dx * r.v, r.dy * r.v);
      },

      tecla(codigo, apertada) {
        const cima = codigo === "ArrowUp" || codigo === "KeyW";
        const baixo = codigo === "ArrowDown" || codigo === "KeyS";
        const esq = codigo === "ArrowLeft" || codigo === "KeyA";
        const dir = codigo === "ArrowRight" || codigo === "KeyD";
        const chute = codigo === "Space" || codigo === "Enter" || codigo === "NumpadEnter";
        if (cima) teclas.cima = apertada;
        if (baixo) teclas.baixo = apertada;
        if (esq) teclas.esq = apertada;
        if (dir) teclas.dir = apertada;
        if (estado !== "vez" || !humano[vez] || mirando) return;
        if (apertada) {
          if (!modoTeclado && (cima || baixo || esq || dir || chute)) {
            // primeira tecla: mostra a mira no botão já escolhido
            modoTeclado = true;
            if (!sel) escolherInicial();
            if (chute && sel) { carregando = true; tCarga = 0; }
            return;
          }
          if (cima) trocarBotao(-1);
          else if (baixo) trocarBotao(1);
          else if (esq) { ang -= 1.5 * GRAU; tGirar = 0; }
          else if (dir) { ang += 1.5 * GRAU; tGirar = 0; }
          else if (chute && sel && !carregando) { carregando = true; tCarga = 0; }
        } else if (chute && carregando) soltarChuteTeclado();
      },

      destruir() {
        agenda = [];
        for (const p of parts) p.vivo = false;
      },
    };
  },
};
