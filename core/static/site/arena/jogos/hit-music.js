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
   - A nota final é a da máquina (stage_v10.gd): soma da qualidade de cada
     acerto ÷ total de notas da fase. CLASSIFICADO com 70% ou mais.

   AS MÚSICAS SÃO AS DA MÁQUINA. Antes de jogar a pessoa escolhe entre
   CARMINE (a favorita do dono, primeira da lista) e PAPER MOON (o "soul"
   do catálogo da mesa), e ouve o áudio de verdade de cada uma. A fase
   não é composta à mão: é o chart_factory_v9.gd portado linha a linha,
   alimentado com os ajustes da música copiados do hit_music_songs.json e
   com o mesmo sorteador do Godot (PCG32 + randf do RandomPCG), na mesma
   ordem de sorteios. As notas saem iguais às que a mesa gera, no nível
   FÁCIL — o que a máquina deixa marcado ao abrir a música.

   O relógio do jogo é o do áudio: o tempo da música sai do
   AudioContext.currentTime (a máquina usa a posição do player do mesmo
   jeito), então nota e batida não descasam quando o quadro da tela
   engasga, e a pausa da aba congela as duas juntas.

   Sem capa nem vídeo das músicas (arte de terceiros): só os títulos e a
   interface do próprio jogo.
   ====================================================================== */

const LARGURA = 540;
const ALTURA = 960;

/* ---------- geometria (mesmas proporções do stage.gd em 1080x1920) ---------- */
const R = 258; // raio do campo: 98,5% da metade da largura útil
const CX = LARGURA / 2;
const CY = ALTURA - 12 - R; // o círculo encosta na margem de baixo
const R_ANEL = R * 0.905; // linha branca onde os tazos encaixam
const FAIXAS = 8;
const HUD = { x: 14, y: 12, w: LARGURA - 28, h: 178 };

/* ---------- partida (stage.gd / stage_v9.gd) ---------- */
const DIFICULDADE = "easy"; // a tela de dificuldade da máquina abre em FÁCIL
const DURACAO_CONTAGEM = 3.0; // COUNTDOWN_SECONDS: o 3-2-1 corre por cima da introdução
const CLASSIFICA = 70; // RESULT_PASS_PERCENT
const FIM_ANTECIPADO = 0.02; // a máquina encerra em song_time >= duração - 0,02

/* ---------- arrasto (constantes do stage.gd) ---------- */
const ESCALA_JANELA_ARRASTO = 2.1; // achar o começo do arrasto leva mais tempo
const FOLGA_ARRASTO = 0.45;
const ARRASTO_COMPLETO = 0.93;
const CORREDOR = R * 0.2; // folga de um dedo inteiro em volta do trilho (no celular, um pouco mais que os 0,165 da mesa)
const AVANCO_MAXIMO = 0.22; // o quanto uma amostra pode andar no trilho
const PASSO_AMOSTRA = 0.045; // SLIDE_SAMPLE_STEP_RATIO
const FOLGA_SOLTAR_HOLD = 0.12; // soltar o hold até 0,12 s antes do fim ainda vale

/* ---------- música: energia e volume (stage.gd) ---------- */
const VOLUME_MIN_DB = -16; // MUSIC_VOLUME_MIN_DB: energia vazia
const VOLUME_MAX_DB = -1; // MUSIC_VOLUME_MAX_DB: energia cheia
const SUAVIZACAO_VOLUME = 2.4; // MUSIC_VOLUME_SMOOTH_SPEED (por segundo)
const PENALIDADE_ERRO = 0.16; // MUSIC_ENERGY_MISS_PENALTY
const RECUPERACAO_ACERTO = 0.1; // MUSIC_ENERGY_HIT_RECOVERY
const VOLUME_MUSICA = 0.85; // nível da trilha na saída (os sons do console vêm por cima)

/* ---------- relógio do áudio ---------- */
const ANTECEDENCIA_INICIO = 0.12; // a fonte é agendada um instante à frente: começa exata
const SALTO_RELOGIO = 0.03; // diferença que denuncia pausa/retomada do áudio
const DERIVA_RELOGIO = 0.001; // s por segundo: deixa o relógio da tela seguir o do áudio
const LATENCIA_MAXIMA = 0.25; // teto da compensação da saída de som
const PAUSA_DO_CONSOLE = 0.35; // sem quadro por esse tempo = o console pausou o jogo
const VIGIA_MS = 250; // conferência do mudo, da latência e da pausa

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
// Contagem da máquina (COUNTDOWN_COLORS): 3 ciano, 2 vermelho, 1 amarelo.
const CORES_CONTAGEM = ["#00dbff", "#ff060e", "#ffb800"];

/* Rótulos do acerto. A máquina tem dois degraus dentro da janela (1,0 no
   perfect_window e 0,72 até o hit_window) e o acerto antecipado, que
   paga de 0,72 a 0,50. Cada degrau ganha o seu nome na tela. */
const JULGAMENTOS = [
  { nome: "PERFECT", cor: "#fff27a" },
  { nome: "GREAT", cor: "#3ff0ff" },
  { nome: "GOOD", cor: "#ff8ae8" },
  { nome: "MISS", cor: "#ff5468" },
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
// Escolha da música com os botões dos menus da mesa: A sobe, E (lane 4,
// a tecla J) desce e B (lane 1, a tecla S) confirma.
const TECLAS_SOBE = { ArrowUp: 1, ArrowLeft: 1, KeyA: 1 };
const TECLAS_DESCE = { ArrowDown: 1, ArrowRight: 1, KeyJ: 1 };
const TECLAS_CONFIRMA = { Enter: 1, NumpadEnter: 1, Space: 1, KeyS: 1 };

/* Silhuetas das setas do arrasto (quatro estilos, como no renderer):
   chevron cheio, dardo, duplo e pena. Pontos em múltiplos do tamanho. */
const FORMAS_SETA = [
  [[[1.05, 0], [-0.75, 0.88], [-0.35, 0], [-0.75, -0.88]]],
  [[[1.3, 0], [-0.9, 0.55], [-0.45, 0], [-0.9, -0.55]]],
  [[[1.05, 0], [0.05, 0.75], [0.35, 0], [0.05, -0.75]], [[0.15, 0], [-0.85, 0.75], [-0.55, 0], [-0.85, -0.75]]],
  [[[1.1, 0], [-0.6, 0.9], [-0.25, 0.1], [-1.1, 0.1], [-1.1, -0.1], [-0.25, -0.1], [-0.6, -0.9]]],
];

/* ======================================================================
   AS MÚSICAS — cópia dos campos de jogo de data/hit_music_songs.json
   (as chaves ficam em inglês, iguais às do catálogo da máquina, para a
   conferência ser direta). Ficaram de fora só os caminhos de cena,
   vídeo e capa, que o site não usa.
   ====================================================================== */
const MUSICAS = [
  {
    id: "carmine",
    nome: "CARMINE",
    arquivo: "hit-music/musicas/carmine.mp3",
    // O MP3 da mesa tem 3456 quadros de 1152 amostras a 44,1 kHz, sem
    // etiqueta Xing: é desse total que o AudioStreamMP3 do Godot tira a
    // duração que a fábrica recebe (e que corta o fim da fase).
    amostras: 3981312,
    taxa: 44100,
    universo: "laminas", // UNIVERSE_BY_SONG: carmine → blade_shards
    category: "ANIME",
    bpm: 174.0,
    chart_start: 4.2,
    seed: 1101,
    pattern: "shards",
    colors: { primary: "#F40730", secondary: "#FFFFFF", accent: "#FFD21A", dark: "#090208" },
    lane_pattern_easy: [0, 2, 4, 6, 1, 3, 5, 7, 2, 6, 0, 4],
    lane_pattern_hard: [0, 4, 1, 5, 2, 6, 3, 7, 0, 3, 6, 1, 4, 7, 2, 5],
    slides_easy: [
      { path: [7, 3], shape: "straight" },
      { path: [1, 5], shape: "arc_cw", curve: 0.52 },
      { path: [0, 4], shape: "cross" },
    ],
    slides_hard: [
      { path: [7, 2, 5], shape: "zigzag" },
      { path: [1, 6], shape: "cross" },
      { path: [0, 3], shape: "arc_ccw", curve: 0.72 },
      { path: [4, 7, 2], shape: "zigzag" },
    ],
    easy: {
      approach: 1.12, hit_window: 0.24, perfect_window: 0.09, step_beats: 2.0,
      slide_every: 9, hold_every: 13, double_every: 0, slide_beats: 4.0, hold_beats: 4.0,
      tap_scale: 1.08, star_scale: 1.08, hold_width: 1.1,
      background_intensity: 0.13, background_speed: 0.13, jitter: 0.02,
    },
    hard: {
      approach: 0.86, hit_window: 0.16, perfect_window: 0.065, step_beats: 1.0,
      slide_every: 7, hold_every: 11, double_every: 6, double_distance: 4, slide_beats: 3.0, hold_beats: 3.0,
      tap_scale: 0.98, star_scale: 1.0, hold_width: 0.96,
      background_intensity: 0.22, background_speed: 0.28, jitter: 0.03,
    },
  },
  {
    id: "soul",
    nome: "PAPER MOON",
    arquivo: "hit-music/musicas/soul.mp3",
    amostras: 3929472, // 3411 quadros × 1152
    taxa: 44100,
    universo: "favo", // UNIVERSE_BY_SONG: soul → moon_hive
    category: "ANIME",
    bpm: 152.0,
    chart_start: 4.0,
    seed: 7707,
    pattern: "hex",
    colors: { primary: "#FF263F", secondary: "#FFFFFF", accent: "#FFE300", dark: "#080204" },
    lane_pattern_easy: [0, 2, 5, 7, 4, 1, 3, 6, 0, 4, 2, 6],
    lane_pattern_hard: [0, 4, 2, 6, 1, 5, 3, 7, 0, 5, 2, 7, 4, 1, 6, 3],
    slides_easy: [
      { path: [0, 4], shape: "straight" },
      { path: [2, 6], shape: "v" },
      { path: [7, 3], shape: "arc_ccw", curve: 0.62 },
    ],
    slides_hard: [
      { path: [0, 4], shape: "cross" },
      { path: [7, 2, 5], shape: "zigzag" },
      { path: [1, 6], shape: "hook", curve: 0.8 },
      { path: [3, 0], shape: "arc_cw", curve: 0.78 },
    ],
    easy: {
      approach: 1.14, hit_window: 0.24, perfect_window: 0.09, step_beats: 2.0,
      slide_every: 9, hold_every: 12, double_every: 0, slide_beats: 4.0, hold_beats: 4.0,
      tap_scale: 1.08, star_scale: 1.08, hold_width: 1.1,
      background_intensity: 0.13, background_speed: 0.14, jitter: 0.015,
    },
    hard: {
      approach: 0.84, hit_window: 0.16, perfect_window: 0.063, step_beats: 0.75,
      slide_every: 6, hold_every: 9, double_every: 5, double_distance: 4, slide_beats: 3.0, hold_beats: 3.0,
      tap_scale: 0.96, star_scale: 1.0, hold_width: 0.95,
      background_intensity: 0.23, background_speed: 0.3, jitter: 0.02,
    },
  },
];

/* Duração que a máquina passa para a fábrica: AudioStreamMP3 calcula
   amostras ÷ (taxa × canais) em float de 32 bits. A conta é refeita
   aqui com a mesma precisão porque o fim da fase (duração − 2,2 s) cai
   a poucos milissegundos de uma batida na Paper Moon. */
function duracaoNaMaquina(musica) {
  return Math.fround(Math.fround(musica.amostras * 2) / Math.fround(musica.taxa * 2));
}

/* ======================================================================
   O SORTEADOR DO GODOT — RandomNumberGenerator (RandomPCG)

   PCG32 (pcg32_srandom_r / pcg32_random_r) com o incremento padrão do
   Godot, e o randf() de random_pcg.h: um sorteio dá o expoente (zeros à
   esquerda), outro a mantissa com o primeiro e o último bit ligados,
   convertida para float de 32 bits. Mesma semente e mesma ordem de
   chamadas = mesmos números que a máquina sorteia. BigInt só roda na
   montagem da fase (umas centenas de sorteios), nunca por quadro.
   ====================================================================== */
const PCG_MULT = 6364136223846793005n;
const PCG_INC = 1442695040888963407n; // PCG_DEFAULT_INC_64
const MASCARA_64 = (1n << 64n) - 1n;

function sorteadorGodot(sementeInicial) {
  let estado = 0n;
  const incremento = ((PCG_INC << 1n) | 1n) & MASCARA_64;
  function proximo() {
    const antigo = estado;
    estado = (antigo * PCG_MULT + incremento) & MASCARA_64;
    const misturado = Number((((antigo >> 18n) ^ antigo) >> 27n) & 0xffffffffn);
    const giro = Number(antigo >> 59n);
    return ((misturado >>> giro) | (misturado << ((32 - giro) & 31))) >>> 0;
  }
  proximo();
  estado = (estado + BigInt(sementeInicial)) & MASCARA_64;
  proximo();
  return {
    randf() {
      const expoente = proximo();
      if (expoente === 0) return 0;
      const mantissa = Math.fround((proximo() | 0x80000001) >>> 0);
      return mantissa * Math.pow(2, -32 - Math.clz32(expoente));
    },
  };
}

/* ======================================================================
   O RITMO DA MÚSICA — rhythm_profile.gd
   ====================================================================== */
const BATIDAS_POR_COMPASSO = 4;

function limitar(v, a, b) {
  return Math.min(b, Math.max(a, v));
}

// Dobra ou parte o BPM até ele cair entre 88 e 178 (musical_bpm).
function bpmMusical(bruto) {
  let v = Math.max(bruto, 1);
  for (let g = 0; v < 88 && g < 6; g++) v *= 2;
  for (let g = 0; v > 178 && g < 6; g++) v *= 0.5;
  return v;
}

/* Perfil da dificuldade: derivado do BPM e, por cima, o que o JSON da
   música trouxer (o JSON manda, como em RHYTHM.build). */
function perfilRitmo(musica, dificil) {
  const bpm = bpmMusical(Math.max(musica.bpm, 1));
  const batida = 60 / bpm;
  const janela = limitar(batida * (dificil ? 0.42 : 0.58), 0.15, 0.34);
  const perfil = {
    bpm,
    beat: batida,
    approach: dificil ? limitar(batida * 2.8, 0.66, 1.24) : limitar(batida * 3.4, 0.78, 1.58),
    hit_window: janela,
    perfect_window: limitar(janela * 0.38, 0.05, 0.13),
    grid_beats: dificil ? 0.5 : 1.0,
    bars_per_phrase: 4,
    slide_beats: dificil ? 4.0 : 5.0,
    hold_beats: dificil ? 3.5 : 4.5,
    double_distance: 4,
  };
  return Object.assign(perfil, dificil ? musica.hard : musica.easy);
}

/* ======================================================================
   A FASE — chart_factory_v9.gd, na mesma ordem de sorteios
   ====================================================================== */

// Arquétipos de frase (PHRASE_*).
const CORRIDA = 0;
const QUEBRA = 1;
const VIRADA = 2;
const PAR = 3;
const MISTO = 4;

// _on_subdivision: testa os dois lados do resto (3,9999 também é batida).
function naSubdivisao(batida, passo) {
  const resto = ((batida % passo) + passo) % passo;
  return resto < 0.0005 || resto > passo - 0.0005;
}

// _density_weight: "um a cada N" do JSON vira peso no sorteio da frase.
function pesoDensidade(cada, slotsPorFrase, reserva) {
  const n = Math.trunc(cada || 0);
  if (n <= 0) return reserva;
  return limitar(slotsPorFrase / n, 0.35, 1.6);
}

// _pick_archetype: sorteio ponderado; repetir o anterior paga 0,28.
function sortearArquetipo(sorteio, dificil, frase, anterior, pesoArrasto, pesoHold, pesoPar) {
  if (frase === 0) return CORRIDA; // a primeira frase é corrida limpa, sem sorteio
  const pesos = [1.4, pesoHold, pesoArrasto, pesoPar, dificil ? 0.55 : 0.38];
  if (anterior >= 0 && anterior < pesos.length) pesos[anterior] *= 0.28;
  let total = 0;
  for (let i = 0; i < pesos.length; i++) total += pesos[i];
  if (total <= 0) return CORRIDA;
  const rolagem = sorteio.randf() * total;
  let acumulado = 0;
  for (let i = 0; i < pesos.length; i++) {
    acumulado += pesos[i];
    if (rolagem <= acumulado) return i;
  }
  return CORRIDA;
}

/* _slot_is_active: o fácil só pisa nas batidas (1 e 3 sempre, 2 e 4 na
   corrida e às vezes nas outras frases); o difícil anda em colcheias. */
function slotAtivo(sorteio, dificil, arquetipo, batidaNoCompasso) {
  const naBatida = naSubdivisao(batidaNoCompasso, 1);
  const forte = naSubdivisao(batidaNoCompasso, 2);
  if (!dificil) {
    if (!naBatida) return false;
    if (forte) return true;
    if (arquetipo === CORRIDA) return true;
    return sorteio.randf() < 0.45;
  }
  if (naBatida) return true;
  if (arquetipo === CORRIDA) return sorteio.randf() < 0.62;
  if (arquetipo === PAR) return sorteio.randf() < 0.3;
  return sorteio.randf() < 0.42;
}

// is_equal_approx do Godot (CMP_EPSILON relativo, com piso).
function quaseIgual(a, b) {
  if (a === b) return true;
  const tolerancia = Math.max(0.00001 * Math.abs(a), 0.00001);
  return Math.abs(a - b) < tolerancia;
}

function montarFase(musica, dificuldade, duracao) {
  const dificil = dificuldade === "hard";
  const perfil = perfilRitmo(musica, dificil);
  const batida = Math.max(perfil.beat, 0.05);
  const compasso = batida * BATIDAS_POR_COMPASSO;
  const grade = Math.max(perfil.grid_beats, 0.25);
  const compassosPorFrase = Math.max(Math.trunc(perfil.bars_per_phrase), 1);
  const inicio = Math.max(musica.chart_start, 3.2);
  const fim = Math.max(inicio + compasso, duracao - 2.2);

  let faixas = dificil ? musica.lane_pattern_hard : musica.lane_pattern_easy;
  if (!faixas || !faixas.length) faixas = [0, 2, 4, 6, 1, 3, 5, 7];
  const arrastos = (dificil ? musica.slides_hard : musica.slides_easy) || [];

  // Semente separada por dificuldade, como na máquina.
  const sorteio = sorteadorGodot(Math.abs(Math.trunc(musica.seed)) * 7919 + (dificil ? 104729 : 15485863));

  const batidasArrasto = Math.max(perfil.slide_beats, 1);
  const batidasHold = Math.max(perfil.hold_beats, 1);
  // Par de mãos só com as lanes em lados opostos da mesa (3 a 5 de distância).
  const distanciaPar = limitar(Math.trunc(perfil.double_distance), 3, 5);

  const slotsPorFraseReal = (BATIDAS_POR_COMPASSO / grade) * compassosPorFrase;
  const pesoArrasto = pesoDensidade(perfil.slide_every, slotsPorFraseReal, 1.3);
  const pesoHold = pesoDensidade(perfil.hold_every, slotsPorFraseReal, 1.1);
  const pesoPar = dificil ? pesoDensidade(perfil.double_every, slotsPorFraseReal, 1.2) : 0;
  let anterior = -1;

  const notas = [];
  let indiceNota = 0;
  let indiceArrasto = 0;
  let frase = 0;

  // A grade é contada em slots inteiros, nunca somando segundos.
  const slotsCompasso = Math.max(Math.round(BATIDAS_POR_COMPASSO / grade), 1);
  const slotsFrase = slotsCompasso * compassosPorFrase;
  // Gesto longo bloqueia tudo até o fim dele mais um respiro, contado em
  // slot ABSOLUTO (vale também para a frase seguinte).
  const slotsRespiro = Math.max(Math.round((dificil ? 0.5 : 1.0) / grade), 1);
  let ocupadoAte = -1;

  for (;;) {
    const inicioFrase = inicio + compasso * (compassosPorFrase * frase);
    if (inicioFrase >= fim) break;

    const arquetipo = sortearArquetipo(sorteio, dificil, frase, anterior, pesoArrasto, pesoHold, pesoPar);
    anterior = arquetipo;

    // Jogada especial: último compasso da frase, batida 1 ou 3.
    const slotEspecial = slotsFrase - slotsCompasso + (sorteio.randf() < 0.6 ? 0 : Math.round(2 / grade));
    let especialFeito = false;

    let slot = 0;
    while (slot < slotsFrase) {
      const absoluto = frase * slotsFrase + slot;
      if (absoluto < ocupadoAte) { slot++; continue; }

      const batidasNaFrase = slot * grade;
      const t = inicioFrase + batida * batidasNaFrase;
      if (t >= fim) break;
      const batidaNoCompasso = ((batidasNaFrase % BATIDAS_POR_COMPASSO) + BATIDAS_POR_COMPASSO) % BATIDAS_POR_COMPASSO;

      if (!slotAtivo(sorteio, dificil, arquetipo, batidaNoCompasso)) { slot++; continue; }

      const faixa = ((Math.trunc(faixas[indiceNota % faixas.length]) % FAIXAS) + FAIXAS) % FAIXAS;
      const querEspecial = !especialFeito && slot >= slotEspecial;

      if (querEspecial && (arquetipo === VIRADA || arquetipo === MISTO) && arrastos.length) {
        const molde = arrastos[indiceArrasto % arrastos.length];
        if (molde.path && molde.path.length >= 2) {
          const nota = {
            tipo: SLIDE, t, fim: Math.min(t + batida * batidasArrasto, fim + batida),
            faixa: molde.path[0], cor: indiceNota % 3,
            caminho: molde.path.slice(), forma: molde.shape || "straight",
            curva: molde.curve === undefined ? 0.55 : molde.curve,
            estiloSeta: indiceArrasto % 4, estiloEstrela: (indiceArrasto * 3 + 1) % 4,
          };
          montarCaminho(nota);
          notas.push(nota);
          indiceArrasto++;
          indiceNota++;
          especialFeito = true;
          const slotsArrasto = Math.max(Math.ceil(batidasArrasto / grade), 1);
          ocupadoAte = absoluto + slotsArrasto + slotsRespiro;
          slot += slotsArrasto;
          continue;
        }
      }

      if (querEspecial && (arquetipo === QUEBRA || arquetipo === MISTO)) {
        notas.push({ tipo: HOLD, t, fim: Math.min(t + batida * batidasHold, fim + batida), faixa, cor: indiceNota % 3 });
        indiceNota++;
        especialFeito = true;
        const slotsHold = Math.max(Math.ceil(batidasHold / grade), 1);
        ocupadoAte = absoluto + slotsHold + slotsRespiro;
        slot += slotsHold;
        continue;
      }

      notas.push({ tipo: TAP, t, fim: t, faixa, cor: indiceNota % 3 });
      // Par de mãos: só na frase de par (só existe no difícil) e na batida forte.
      if (arquetipo === PAR && naSubdivisao(batidaNoCompasso, 2) && sorteio.randf() < 0.72) {
        notas.push({ tipo: TAP, t, fim: t, faixa: (faixa + distanciaPar) % FAIXAS, cor: (indiceNota + 1) % 3 });
      }
      indiceNota++;
      slot++;
    }
    frase++;
  }

  // Mesma ordem do sort_custom: tempo, e no mesmo instante a lane menor
  // (arrasto não tem "lane" no evento e conta como 0).
  notas.sort((a, b) => {
    if (quaseIgual(a.t, b.t)) return (a.tipo === SLIDE ? 0 : a.faixa) - (b.tipo === SLIDE ? 0 : b.faixa);
    return a.t < b.t ? -1 : 1;
  });
  return notas;
}

/* ======================================================================
   O TRILHO DO ARRASTO — path_builder.gd (formas e número de amostras)
   ====================================================================== */
function posicaoFaixa(faixa) {
  const a = -Math.PI / 2 + (Math.PI * 2 * faixa) / FAIXAS;
  return [CX + Math.cos(a) * R_ANEL, CY + Math.sin(a) * R_ANEL];
}

function polilinha(ancoras, passos) {
  const pts = [];
  for (let s = 0; s < ancoras.length - 1; s++) {
    const a = ancoras[s];
    const b = ancoras[s + 1];
    for (let i = 0; i < passos; i++) pts.push([a[0] + (b[0] - a[0]) * (i / passos), a[1] + (b[1] - a[1]) * (i / passos)]);
  }
  pts.push(ancoras[ancoras.length - 1]);
  return pts;
}

function quadratica(a, b, c, passos) {
  const pts = [];
  for (let i = 0; i <= passos; i++) {
    const t = i / passos;
    const u = 1 - t;
    pts.push([a[0] * u * u + b[0] * 2 * u * t + c[0] * t * t, a[1] * u * u + b[1] * 2 * u * t + c[1] * t * t]);
  }
  return pts;
}

function cubica(a, b, c, d, passos) {
  const pts = [];
  for (let i = 0; i <= passos; i++) {
    const t = i / passos;
    const u = 1 - t;
    pts.push([
      a[0] * u * u * u + b[0] * 3 * u * u * t + c[0] * 3 * u * t * t + d[0] * t * t * t,
      a[1] * u * u * u + b[1] * 3 * u * u * t + c[1] * 3 * u * t * t + d[1] * t * t * t,
    ]);
  }
  return pts;
}

// _arc_control: o arco estufa para fora do disco (curva negativa: para dentro).
function controleArco(a, b, curva) {
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2;
  let nx = -(b[1] - a[1]);
  let ny = b[0] - a[0];
  const l = Math.hypot(nx, ny) || 1;
  nx /= l; ny /= l;
  if (nx * (mx - CX) + ny * (my - CY) < 0) { nx = -nx; ny = -ny; }
  return [mx + nx * R * curva * 0.6, my + ny * R * curva * 0.6];
}

function montarCaminho(nota) {
  const faixas = nota.caminho;
  const ancoras = faixas.map(posicaoFaixa);
  const a = ancoras[0];
  const b = ancoras[ancoras.length - 1];
  const curva = limitar(nota.curva, -1, 1);
  let pts;
  if (nota.forma === "cross") {
    pts = polilinha([a, [CX, CY], b], 18);
  } else if (nota.forma === "v") {
    // vértice a 0,24 do raio, na direção do meio da corda (ou para cima)
    let dx = (a[0] + b[0]) / 2 - CX;
    let dy = (a[1] + b[1]) / 2 - CY;
    const l = Math.hypot(dx, dy);
    if (l > 0) { dx /= l; dy /= l; }
    if (dx * dx + dy * dy < 0.01) { dx = 0; dy = -1; }
    pts = polilinha([a, [CX + dx * R * 0.24, CY + dy * R * 0.24], b], 18);
  } else if (nota.forma === "arc_cw" || nota.forma === "arc_ccw") {
    const c = controleArco(a, b, nota.forma === "arc_cw" ? Math.abs(curva) : -Math.abs(curva));
    pts = quadratica(a, c, b, 42);
  } else if (nota.forma === "hook") {
    const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const px = -(b[1] - a[1]) / l;
    const py = (b[0] - a[0]) / l;
    const c1 = [a[0] + (CX - a[0]) * 0.6 + px * R * curva * 0.35, a[1] + (CY - a[1]) * 0.6 + py * R * curva * 0.35];
    const c2 = [b[0] + (CX - b[0]) * 0.42 - px * R * curva * 0.2, b[1] + (CY - b[1]) * 0.42 - py * R * curva * 0.2];
    pts = cubica(a, c1, c2, b, 48);
  } else if (nota.forma === "zigzag" || ancoras.length > 2) {
    pts = polilinha(ancoras, 14);
  } else {
    pts = polilinha([a, b], 42);
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
  // O progresso da mecânica é por índice de amostra (nearest_progress);
  // cada âncora (faixa) guarda o seu, para o teclado andar por elas.
  nota.ancoras = ancoras.map((p) => {
    let melhor = 0;
    let menor = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.hypot(nota.px[i] - p[0], nota.py[i] - p[1]);
      if (d < menor) { menor = d; melhor = i; }
    }
    return melhor / Math.max(n - 1, 1);
  });
}

/* ---------- cores das músicas ---------- */
function hexParaRgb(hex) {
  const v = parseInt(hex.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

function misturar(a, b, k) {
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
}

function textoRgb(c) {
  return `rgb(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])})`;
}

/* Tema de cada tela: a capa e a escolha usam o rosa/ciano da marca Hit
   Music; durante a música vale a paleta dela (colors do catálogo), como
   na mesa — borda do HUD, brilho do anel, poeira e cenário. */
const TEMA_PADRAO = {
  id: "hit", primaria: COR_TEMA, destaque: COR_TEMA2, meio: "#8a5cff", clara: "#ff8ae8", brilho: ROSA,
  fundo: ["#0d0326", "#070118", "#020007"], disco: ["#1c0a3d", "#0c0424", "#05010f"],
};
const RGB_BRILHOS = RGB.concat(MUSICAS.map((m) => hexParaRgb(m.colors.primary)));
const TEMAS = MUSICAS.map((m, k) => {
  const p = hexParaRgb(m.colors.primary);
  const d = hexParaRgb(m.colors.accent);
  const e = hexParaRgb(m.colors.dark);
  const branco = [255, 255, 255];
  return {
    id: m.id,
    primaria: m.colors.primary,
    destaque: m.colors.accent,
    meio: textoRgb(misturar(p, d, 0.5)),
    clara: textoRgb(misturar(p, branco, 0.45)),
    brilho: RGB.length + k,
    fundo: [textoRgb(misturar([0, 0, 0], p, 0.1)), textoRgb(misturar([0, 0, 0], p, 0.04)), "#020007"],
    disco: [textoRgb(misturar(e, p, 0.16)), textoRgb(misturar(e, p, 0.06)), textoRgb(e)],
    // lâminas do carmine: primária puxando para o destaque (slash % 3 × 0,34)
    laminas: [0, 0.34, 0.68].map((x) => textoRgb(misturar(p, d, x))),
    // placas do favo: primária clareando para a secundária (branco)
    placas: [0.12, 0.3, 0.48].map((x) => textoRgb(misturar(p, branco, x))),
  };
});

// Textos fixos de cada música, montados uma vez (nada de string nova por quadro).
const TEXTOS_MUSICA = MUSICAS.map((m, k) => ({
  faixa: `TRACK ${String(k + 1).padStart(2, "0")}`,
  andamento: `${m.bpm} BPM  •  FÁCIL`,
  nivel: `FÁCIL • ${m.bpm} BPM`,
}));

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
    const MARCAS = Array.from({ length: FAIXAS }, (_, i) => posicaoFaixa(i));
    const temMouse = !!(window.matchMedia && window.matchMedia("(hover: hover)").matches);
    const botaoSom = document.querySelector("[data-console-som]");

    /* ---------- brilhos pré-desenhados (um por cor) ----------
       Gradiente radial custa caro se for criado a cada quadro; um
       canvas pequeno pintado uma vez e esticado com drawImage sai de
       graça e dá o mesmo "neon". */
    const BRILHOS = RGB_BRILHOS.map(([r, g, b]) => {
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

    // Gradientes de cada tema, criados uma vez na primeira vez que aparecem.
    const gradientesPorTema = {};
    let gradientes = null;
    function prepararGradientes(ctx, tema) {
      gradientes = gradientesPorTema[tema.id];
      if (gradientes) return;
      const fundo = ctx.createLinearGradient(0, 0, 0, ALTURA);
      fundo.addColorStop(0, tema.fundo[0]);
      fundo.addColorStop(0.45, tema.fundo[1]);
      fundo.addColorStop(1, tema.fundo[2]);
      const disco = ctx.createRadialGradient(CX, CY, R * 0.1, CX, CY, R);
      disco.addColorStop(0, tema.disco[0]);
      disco.addColorStop(0.7, tema.disco[1]);
      disco.addColorStop(1, tema.disco[2]);
      const borda = ctx.createLinearGradient(HUD.x, 0, HUD.x + HUD.w, 0);
      borda.addColorStop(0, tema.primaria);
      borda.addColorStop(0.5, tema.meio);
      borda.addColorStop(1, tema.destaque);
      const barras = ctx.createLinearGradient(HUD.x, 0, HUD.x + HUD.w, 0);
      barras.addColorStop(0, tema.primaria);
      barras.addColorStop(0.5, tema.meio);
      barras.addColorStop(1, tema.destaque);
      gradientes = gradientesPorTema[tema.id] = { fundo, disco, borda, barras };
    }

    /* Favo da Paper Moon (moon_hive): as placas não mudam de lugar, então
       o centro e a profundidade de cada uma são calculados uma vez só. */
    const RAIO_UNIVERSO = R * 0.86; // UNIVERSE_INNER_RATIO: nada vaza do disco
    const CELULA = RAIO_UNIVERSO * 0.185;
    const FAVO = [];
    for (let coluna = -4; coluna <= 4; coluna++) {
      for (let linha = -4; linha <= 4; linha++) {
        const desvio = ((coluna % 2) + 2) % 2 === 1 ? CELULA * 0.866 : 0;
        const x = CX + coluna * CELULA * 1.5;
        const y = CY + linha * CELULA * 1.732 + desvio;
        const d = Math.hypot(x - CX, y - CY);
        if (d > RAIO_UNIVERSO - CELULA * 0.55) continue;
        FAVO.push({ x, y, profundidade: 1 - limitar(d / RAIO_UNIVERSO, 0, 1), fase: coluna * 0.8 + linha * 0.6 });
      }
    }

    /* ======================================================================
       SOM — a faixa de verdade num AudioContext só do jogo

       fonte → energia (volume que erra/acerta mexe) → analisador (barras
       do HUD) → saída (mudo do console) → alto-falante. O mudo zera só a
       saída: o contexto continua rodando porque ele é o relógio do jogo.
       ====================================================================== */
    const Contexto = window.AudioContext || window.webkitAudioContext;
    const audio = {
      ctx: null, saida: null, energia: null, analisador: null, dados: null,
      fonte: null, buffer: null, bufferId: null, duracao: 0,
      inicio: 0, latencia: 0, desvio: null, ligado: true,
      tocando: false, acabou: false, suspensoPorNos: false, travadoDesde: 0, ultimaRetomada: 0,
    };
    // Barras do HUD: 32 faixas de frequência em escala quase logarítmica.
    const BARRAS = 32;
    const espectro = new Float32Array(BARRAS);
    const BORDAS_BARRAS = new Uint8Array(BARRAS + 1);
    for (let i = 0; i <= BARRAS; i++) BORDAS_BARRAS[i] = Math.round(1 + 95 * Math.pow(i / BARRAS, 1.7)) + i;

    /* O console não expõe o mudo para o jogo. O botão dele, porém, diz o
       estado em aria-pressed (e o mesmo valor fica no localStorage); é o
       que a pessoa vê, então é a fonte certa para a trilha obedecer. */
    function somLigado() {
      if (botaoSom) return botaoSom.getAttribute("aria-pressed") !== "false";
      try { return window.localStorage.getItem("ls-jogos-som") !== "0"; } catch (erro) { return true; }
    }

    function retomarContexto() {
      const p = audio.ctx.resume();
      if (p && p.catch) p.catch(() => {});
    }

    // Só chamar a partir de um gesto (ou depois que a página já teve um):
    // é a regra dos navegadores para tocar som.
    function acordarAudio() {
      if (!Contexto) return;
      if (!audio.ctx) {
        try { audio.ctx = new Contexto(); } catch (erro) { audio.ctx = null; return; }
        const c = audio.ctx;
        audio.ligado = somLigado();
        audio.saida = c.createGain();
        audio.saida.gain.value = audio.ligado ? VOLUME_MUSICA : 0;
        audio.analisador = c.createAnalyser();
        audio.analisador.fftSize = 256;
        audio.analisador.smoothingTimeConstant = 0.72;
        audio.dados = new Uint8Array(audio.analisador.frequencyBinCount);
        audio.energia = c.createGain();
        audio.energia.gain.value = Math.pow(10, VOLUME_MAX_DB / 20);
        audio.energia.connect(audio.analisador);
        audio.analisador.connect(audio.saida);
        audio.saida.connect(c.destination);
        medirLatencia();
      }
      if (audio.ctx.state !== "running" && !document.hidden) {
        audio.suspensoPorNos = false;
        retomarContexto();
      }
    }

    // A máquina desconta a latência de saída da posição do player; aqui é
    // a mesma conta com o que o navegador informa (base + saída).
    function medirLatencia() {
      const c = audio.ctx;
      if (!c) return;
      audio.latencia = limitar((c.baseLatency || 0) + (c.outputLatency || 0), 0, LATENCIA_MAXIMA);
    }

    function aplicarMudo() {
      const ligado = somLigado();
      if (ligado === audio.ligado) return;
      audio.ligado = ligado;
      if (audio.saida) audio.saida.gain.setTargetAtTime(ligado ? VOLUME_MUSICA : 0, audio.ctx.currentTime, 0.03);
    }

    function atualizarVolume() {
      if (!audio.energia || !audio.tocando) return;
      // energia cheia = -1 dB, vazia = -16 dB, deslizando como o lerp por quadro do stage.gd
      const db = VOLUME_MIN_DB + (VOLUME_MAX_DB - VOLUME_MIN_DB) * energiaMusica;
      audio.energia.gain.setTargetAtTime(Math.pow(10, db / 20), audio.ctx.currentTime, 1 / SUAVIZACAO_VOLUME);
    }

    function pararFonte() {
      const f = audio.fonte;
      audio.fonte = null;
      audio.tocando = false;
      if (!f) return;
      f.onended = null;
      try { f.stop(); } catch (erro) { /* já parou */ }
      try { f.disconnect(); } catch (erro) { /* já solta */ }
    }

    function pausarAudio() {
      if (!audio.ctx || audio.ctx.state !== "running") return;
      audio.suspensoPorNos = true;
      const p = audio.ctx.suspend();
      if (p && p.catch) p.catch(() => {});
    }

    /* O RELÓGIO. O tempo da música é o currentTime do contexto menos o
       instante em que a fonte começou e menos a latência de saída. O
       currentTime anda aos saltos (um bloco de áudio por vez), então a
       diferença entre ele e o relógio da página é guardada pelo MAIOR
       valor visto — a leitura mais fresca de cada bloco — e o tempo de
       cada quadro (e de cada toque) sai dessa diferença, sem degraus.
       Contexto suspenso = tempo parado: a pausa congela música e fase. */
    function tempoMusica() {
      const c = audio.ctx;
      if (!audio.tocando || !c) return t;
      if (c.state !== "running") { audio.desvio = null; return t; }
      const agora = performance.now() / 1000;
      const d = c.currentTime - agora;
      if (audio.desvio === null || d > audio.desvio || d < audio.desvio - SALTO_RELOGIO) audio.desvio = d;
      const valor = agora + audio.desvio - audio.inicio - audio.latencia;
      return Math.min(audio.duracao, Math.max(t, valor));
    }

    /* ---------- carregar a música escolhida ---------- */
    const carga = { ficha: 0, indice: -1, estado: "", progresso: 0 };

    async function baixar(url, ficha) {
      const resposta = await fetch(url);
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const total = Number(resposta.headers.get("Content-Length")) || 0;
      if (!total || !resposta.body || !resposta.body.getReader) return resposta.arrayBuffer();
      const leitor = resposta.body.getReader();
      const pedacos = [];
      let recebido = 0;
      for (;;) {
        const { done, value } = await leitor.read();
        if (done) break;
        if (ficha !== carga.ficha) { leitor.cancel().catch(() => {}); return null; }
        pedacos.push(value);
        recebido += value.length;
        carga.progresso = Math.min(1, recebido / total);
      }
      const bytes = new Uint8Array(recebido);
      let pos = 0;
      for (const p of pedacos) { bytes.set(p, pos); pos += p.length; }
      return bytes.buffer;
    }

    function decodificar(bytes) {
      return new Promise((ok, falha) => {
        const p = audio.ctx.decodeAudioData(bytes, ok, falha);
        if (p && p.catch) p.catch(falha);
      });
    }

    // Baixa (só quando escolhida), decodifica e começa. Fica guardada só
    // a última música decodificada: 90 s de áudio aberto pesam ~35 MB.
    async function carregarMusica(indice) {
      const musica = MUSICAS[indice];
      const ficha = ++carga.ficha;
      carga.indice = indice;
      carga.estado = "baixando";
      carga.progresso = 0;
      fase = "carregando";
      try {
        if (audio.bufferId !== musica.id) {
          audio.buffer = null;
          audio.bufferId = null;
          const bytes = await baixar(new URL(musica.arquivo, import.meta.url), ficha);
          if (ficha !== carga.ficha || !bytes) return;
          carga.estado = "preparando";
          if (!audio.ctx) throw new Error("navegador sem Web Audio");
          const buffer = await decodificar(bytes);
          if (ficha !== carga.ficha) return;
          audio.buffer = buffer;
          audio.bufferId = musica.id;
        }
        if (ficha !== carga.ficha || fase !== "carregando") return;
        comecarMusica(indice);
      } catch (erro) {
        if (ficha !== carga.ficha) return;
        console.warn("Hit Music: a música não carregou", erro);
        carga.estado = "erro";
      }
    }

    function escolher(indice) {
      cursor = indice;
      acordarAudio(); // o toque na música é o gesto que libera o som
      if (fase === "carregando" && carga.indice === indice && carga.estado !== "erro") return;
      carregarMusica(indice);
    }

    /* ======================================================================
       ESTADO DA PARTIDA
       ====================================================================== */
    let chamadasIniciar = 0;
    let fase = "capa"; // capa → escolha → carregando → contagem → tocando → fim
    let cursor = 0; // a Carmine vem marcada
    let indiceMusica = -1;
    let musica = null;
    let tema = TEMA_PADRAO;
    const fases = []; // fase de cada música, montada na primeira vez que ela toca
    let NOTAS = [];
    let TOTAL_NOTAS = 0;
    let PRIMEIRA_NOTA = 0;
    let aproximacao = 1.12;
    let janelaAcerto = 0.24;
    let janelaPerfeito = 0.09;
    let batida = 60 / 174;
    let inicioFase = 4.2;
    let intensidadeUniverso = 0.3;
    let velocidadeUniverso = 0.13;

    let t = 0; // tempo da música (s), do relógio do áudio
    let relogio = 0; // relógio visual (anda até atrás da capa)
    let ultimoQuadro = 0;
    let combo = 0;
    let comboMax = 0;
    let somaQualidade = 0;
    let acertos = 0;
    let erros = 0;
    let precisaoMostrada = 0;
    let energiaMusica = 1;
    let energiaAcerto = 0;
    let proxNascer = 0;
    let primeiraViva = 0;
    let ultimoJulgamento = -1;
    let tempoJulgamento = -9;
    let comboPulo = 0;
    let tempoMostrado = -1;
    let pontosMostrados = -1;
    let classificado = false;
    let terminou = false;
    const flash = new Float32Array(FAIXAS);
    const corFlash = new Uint8Array(FAIXAS);
    const toque = new Float32Array(FAIXAS);
    const ponteiros = new Map();
    const teclasPresas = new Set();
    const setaFaixa = {};
    let setaPendente = null;

    // Textos do HUD só são remontados quando o valor muda.
    let textoPrecisao = "0,00%";
    let centesimosPrecisao = 0;
    let textoTempo = "0:00 / 0:00";
    let segundoTempo = -1;
    let textoCombo = "COMBO 0";
    let textoComboNumero = "0";
    let comboTexto = 0;

    /* Recorde de cada música neste aparelho (a mesa mostra o recorde por
       música no seletor). Conveniência local: sem armazenamento, fica 0. */
    const recordes = MUSICAS.map((m) => {
      try { return Number(window.localStorage.getItem("ls-hit-music-recorde:" + m.id)) || 0; } catch (erro) { return 0; }
    });
    const textosRecorde = recordes.map((v) => "RECORDE " + formatarPct(v));

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

    // _score_percent do stage_v10: sobre o total de notas da fase, então
    // começa em 0% e sobe a cada acerto.
    function precisao() {
      return TOTAL_NOTAS ? limitar((100 * somaQualidade) / TOTAL_NOTAS, 0, 100) : 0;
    }

    function formatarPct(v) {
      return v.toFixed(2).replace(".", ",") + "%";
    }

    function formatarTempo(s) {
      const v = Math.max(0, Math.round(s));
      return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, "0")}`;
    }

    // Os pontos do console são a nota da máquina em centésimos de ponto
    // percentual: 87,45% = 8.745. O recorde do console fica sendo a
    // melhor precisão, comparável entre as duas músicas.
    function atualizarPlacar() {
      const pontos = Math.round(precisao() * 100);
      if (pontos !== pontosMostrados) { pontosMostrados = pontos; api.placar({ pontos }); }
    }

    function zerarPartida() {
      t = 0;
      combo = 0; comboMax = 0; somaQualidade = 0; acertos = 0; erros = 0;
      precisaoMostrada = 0; energiaMusica = 1; energiaAcerto = 0;
      proxNascer = 0; primeiraViva = 0;
      ultimoJulgamento = -1; tempoJulgamento = -9; comboPulo = 0;
      tempoMostrado = -1; pontosMostrados = -1; classificado = false; terminou = false;
      centesimosPrecisao = -1; segundoTempo = -1; comboTexto = -1;
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
    }

    /* Prepara a música escolhida: a fase (gerada uma vez e guardada), o
       tempo de jogo do perfil dela e as cores. */
    function prepararMusica(indice) {
      indiceMusica = indice;
      musica = MUSICAS[indice];
      tema = TEMAS[indice];
      const perfil = perfilRitmo(musica, DIFICULDADE === "hard");
      aproximacao = Math.max(perfil.approach, 0.001);
      janelaAcerto = perfil.hit_window;
      janelaPerfeito = perfil.perfect_window;
      batida = perfil.beat;
      inicioFase = Math.max(musica.chart_start, 3.2);
      // _draw_universe reescala a intensidade do fundo para ter presença
      intensidadeUniverso = limitar(limitar(perfil.background_intensity, 0.06, 0.3) * 1.9 + 0.06, 0.14, 0.52);
      velocidadeUniverso = perfil.background_speed;
      if (!fases[indice]) fases[indice] = montarFase(musica, DIFICULDADE, duracaoNaMaquina(musica));
      NOTAS = fases[indice];
      TOTAL_NOTAS = NOTAS.length;
      PRIMEIRA_NOTA = TOTAL_NOTAS ? NOTAS[0].t : inicioFase;
      zerarPartida();
    }

    // A fonte começa no zero da faixa junto com a contagem, como o
    // _start_countdown da máquina; a primeira nota vem no chart_start.
    function comecarMusica(indice) {
      prepararMusica(indice);
      pararFonte();
      const c = audio.ctx;
      medirLatencia();
      const fonte = c.createBufferSource();
      fonte.buffer = audio.buffer;
      fonte.connect(audio.energia);
      const g = audio.energia.gain;
      g.cancelScheduledValues(c.currentTime);
      g.setValueAtTime(Math.pow(10, VOLUME_MAX_DB / 20), c.currentTime);
      audio.inicio = c.currentTime + ANTECEDENCIA_INICIO;
      audio.duracao = audio.buffer.duration;
      audio.desvio = null;
      audio.acabou = false;
      audio.travadoDesde = 0;
      fonte.onended = () => { if (audio.fonte === fonte) audio.acabou = true; };
      fonte.start(audio.inicio);
      audio.fonte = fonte;
      audio.tocando = true;
      fase = "contagem";
      api.placar({ pontos: 0, tempo: audio.duracao, info: "" });
      pontosMostrados = 0;
    }

    function terminarPartida() {
      if (terminou) return;
      terminou = true;
      fase = "fim";
      pararFonte();
      window.setTimeout(() => { if (fase === "fim" && audio.ctx) pausarAudio(); }, 700);
      const pct = precisao();
      precisaoMostrada = pct;
      classificado = pct >= CLASSIFICA;
      if (pct > recordes[indiceMusica]) {
        recordes[indiceMusica] = pct;
        textosRecorde[indiceMusica] = "RECORDE " + formatarPct(pct);
        try { window.localStorage.setItem("ls-hit-music-recorde:" + musica.id, String(pct)); } catch (erro) { /* aba anônima */ }
      }
      api.placar({ tempo: 0 });
      api.terminar({
        pontos: Math.round(pct * 100),
        titulo: classificado ? "CLASSIFICADO!" : "NÃO CLASSIFICADO",
        detalhe: `${musica.nome} · precisão ${formatarPct(pct)} · ${acertos} ${acertos === 1 ? "acerto" : "acertos"}`
          + ` · ${erros} ${erros === 1 ? "erro" : "erros"} · combo máx. ${comboMax}`
          + (classificado ? "" : " · mínimo 70%"),
      });
    }

    /* ---------- vigia: mudo, latência e pausa ----------
       O console só para de chamar atualizar() quando a aba some ou a
       máquina sai da tela; não avisa o jogo. Sem quadro por um instante
       com a música tocando = pausa: o contexto é suspenso e o relógio da
       música congela junto com a fase. A volta é no próximo atualizar(). */
    function vigiar() {
      aplicarMudo();
      if (!audio.ctx) return;
      medirLatencia();
      const parado = performance.now() - ultimoQuadro > PAUSA_DO_CONSOLE * 1000;
      if (audio.tocando && (document.hidden || parado)) pausarAudio();
    }
    const vigia = window.setInterval(vigiar, VIGIA_MS);

    function aoMudarVisibilidade() {
      if (document.hidden && audio.tocando) pausarAudio();
    }
    document.addEventListener("visibilitychange", aoMudarVisibilidade);

    /* ---------- posição das coisas no tempo (sem alocar: px/py/pang) ---------- */
    let px = 0;
    let py = 0;
    let pang = 0;

    function chegada(nota, tempo) {
      return Math.min(1, Math.max(0, (tempo - (nota.t - aproximacao)) / aproximacao));
    }
    // Sai rápido do centro e desacelera perto do anel (no original a curva
    // é mais fechada; aqui um pouco mais aberta para ler no celular).
    const suavizar = (p) => 1 - (1 - p) * (1 - p);

    function posicaoTap(nota, tempo) {
      const m = MARCAS[nota.faixa];
      const p = (tempo - (nota.t - aproximacao)) / aproximacao;
      // atrasado: o tazo passa do anel e some — é o MISS chegando
      const k = p <= 1 ? suavizar(Math.max(0, p)) : 1 + (p - 1) * 0.55;
      px = CX + (m[0] - CX) * k;
      py = CY + (m[1] - CY) * k;
    }

    // Ponto do trilho por fração do comprimento (point_at_cached): é onde
    // a estrela é desenhada.
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
       JULGAMENTO (stage.gd)
       ====================================================================== */
    // _timing_quality: 1,0 no perfect_window, 0,72 no hit_window e, antes
    // disso (a nota pode ser tocada assim que aparece), de 0,72 a 0,50.
    function qualidadeTempo(dif) {
      const a = Math.abs(dif);
      if (a <= janelaPerfeito) return 1;
      if (a <= janelaAcerto) return 0.72;
      return 0.72 + (0.5 - 0.72) * limitar((a - janelaAcerto) / aproximacao, 0, 1);
    }

    function rotuloTempo(dif) {
      const a = Math.abs(dif);
      if (a <= janelaPerfeito) return 0;
      if (a <= janelaAcerto) return 1;
      return 2;
    }

    function acertar(nota, q, rotulo, x, y) {
      nota.resolvida = true;
      nota.segurando = false;
      nota.ativa = false;
      combo++;
      comboMax = Math.max(comboMax, combo);
      somaQualidade += q;
      acertos++;
      energiaMusica = Math.min(1, energiaMusica + RECUPERACAO_ACERTO);
      energiaAcerto = Math.min(1, energiaAcerto + 0.3 + q * 0.3);
      ultimoJulgamento = rotulo;
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
        api.efeitos.texto(`COMBO ${combo}!`, CX, 392, { cor: tema.destaque, tamanho: 34, vida: 1 });
        api.tremer(5);
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
      erros++;
      energiaMusica = Math.max(0, energiaMusica - PENALIDADE_ERRO);
      ultimoJulgamento = 3;
      tempoJulgamento = t;
      atualizarVolume();
    }

    function concluirArrasto(nota) {
      pontoDoCaminho(nota, nota.desenho);
      acertar(nota, 1, 0, px, py);
      nota.finalizando = true;
    }

    /* ---------- entrada ---------- */
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
          if (tp > n.t + janelaAcerto * ESCALA_JANELA_ARRASTO) continue;
        } else {
          if (n.faixa !== faixa || n.segurando) continue;
          if (tp > n.t + janelaAcerto) continue;
        }
        const d = Math.abs(tp - n.t);
        if (d < menor) { menor = d; melhor = n; }
      }
      if (!melhor) return;

      const dif = tp - melhor.t;
      if (melhor.tipo === TAP) {
        posicaoTap(melhor, tp);
        acertar(melhor, qualidadeTempo(dif), rotuloTempo(dif), px, py);
      } else if (melhor.tipo === HOLD) {
        melhor.segurando = true;
        melhor.fonte = fonte;
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
          // hold completo vale 1,0, como no stage.gd
          if (tp >= n.fim - FOLGA_SOLTAR_HOLD) acertar(n, 1, 0, MARCAS[n.faixa][0], MARCAS[n.faixa][1]);
          else errar(n);
        } else if (n.tipo === SLIDE && n.ativa) {
          // Soltar no meio não é erro na hora: o trecho feito fica guardado
          // e dá para retomar enquanto a nota viver.
          n.ativa = false;
        }
      }
    }

    // nearest_progress do path_builder.gd: procura a amostra mais perto só
    // numa janela curta à frente do progresso atual (índice de amostra).
    let achadoProgresso = 0;
    let achadoDistancia = 0;
    function maisPerto(n, x, y, minimo) {
      const ultimo = n.px.length - 1;
      const de = limitar(Math.floor(limitar(minimo, 0, 1) * ultimo) - 2, 0, ultimo);
      const ate = limitar(de + Math.ceil(AVANCO_MAXIMO * ultimo) + 2, de, ultimo);
      let melhor = de;
      let menor = Infinity;
      for (let i = de; i <= ate; i++) {
        const dx = n.px[i] - x;
        const dy = n.py[i] - y;
        const d = dx * dx + dy * dy;
        if (d < menor) { menor = d; melhor = i; }
      }
      achadoProgresso = melhor / Math.max(ultimo, 1);
      achadoDistancia = Math.sqrt(menor);
    }

    // O trilho avança só pelo que o dedo realmente varreu: cada amostra
    // entre a posição anterior e a atual precisa cair dentro do corredor.
    function avancarArrasto(n, x, y) {
      const passo = Math.max(R * PASSO_AMOSTRA, 1);
      const dx = x - n.ux;
      const dy = y - n.uy;
      const k = Math.min(96, Math.max(1, Math.ceil(Math.hypot(dx, dy) / passo)));
      let prog = n.progresso;
      for (let s = 1; s <= k; s++) {
        maisPerto(n, n.ux + (dx * s) / k, n.uy + (dy * s) / k, prog);
        if (achadoDistancia > CORREDOR) break;
        if (achadoProgresso > prog) prog = achadoProgresso;
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

    /* ---------- a escolha da música ---------- */
    const CARTOES = [
      { x: 30, y: 214, w: 480, h: 150 },
      { x: 30, y: 382, w: 480, h: 150 },
    ];

    function cartaoEm(x, y) {
      for (let k = 0; k < CARTOES.length; k++) {
        const c = CARTOES[k];
        if (x >= c.x && x <= c.x + c.w && y >= c.y && y <= c.y + c.h) return k;
      }
      return -1;
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

    // Acrescenta um polígono regular ao caminho atual (sem beginPath, para
    // vários saírem num traço só).
    function subPoligono(ctx, x, y, raio, lados, rot) {
      for (let i = 0; i <= lados; i++) {
        const a = rot + (Math.PI * 2 * i) / lados;
        if (i === 0) ctx.moveTo(x + Math.cos(a) * raio, y + Math.sin(a) * raio);
        else ctx.lineTo(x + Math.cos(a) * raio, y + Math.sin(a) * raio);
      }
    }

    function poligono(ctx, x, y, raio, lados, rot) {
      ctx.beginPath();
      subPoligono(ctx, x, y, raio, lados, rot);
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
        ctx.fillStyle = i % 3 === 0 ? tema.primaria : i % 3 === 1 ? tema.destaque : "#ffffff";
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
        ctx.fillStyle = k ? tema.primaria : tema.destaque;
        for (let j = 0; j < 7; j++) {
          ctx.globalAlpha = (1 - j / 7) * 0.5 * Math.sin(Math.PI * p);
          ctx.fillRect(x - sentido * j * 6, y - j * 1.6, 2.4 - j * 0.25, 2.4 - j * 0.25);
        }
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    }

    // Pulso da batida preso na grade da fase: as notas caem em
    // chart_start + k batidas, e o pulso bate junto com elas.
    function batidaPulso() {
      const fasei = (((t - inicioFase) / batida) % 1 + 1) % 1;
      return Math.pow(1 - fasei, 3);
    }

    function comMusica() {
      return fase === "contagem" || fase === "tocando" || fase === "fim";
    }

    /* CARMINE — lâminas (blade_shards do playfield_renderer.gd): cortes
       diagonais atravessam o disco e deixam estilhaços para trás. */
    function desenharLaminas(ctx, tempo, pulso, reacao) {
      const forca = intensidadeUniverso;
      for (let s = 0; s < 5; s++) {
        const ang = -Math.PI * 0.3 + s * 0.38 + Math.sin(tempo * 0.14 + s * 1.3) * 0.05;
        const dx = Math.cos(ang);
        const dy = Math.sin(ang);
        const nx = -dy;
        const ny = dx;
        const fasei = (tempo * 0.055 + s * 0.21) % 1;
        const desloc = (fasei - 0.5) * RAIO_UNIVERSO * 1.72;
        const vao = Math.sqrt(Math.max(RAIO_UNIVERSO * RAIO_UNIVERSO - desloc * desloc, 0));
        if (vao <= 1) continue;
        const mx = CX + nx * desloc;
        const my = CY + ny * desloc;
        const esp = R * (0.016 + 0.009 * (s % 3)) * (1 + reacao * 0.85 + pulso * 0.25);
        const some = Math.sin(Math.PI * fasei);
        ctx.globalAlpha = forca * (0.46 + pulso * 0.16 + reacao * 0.34) * some;
        ctx.fillStyle = tema.laminas[s % 3];
        ctx.beginPath();
        ctx.moveTo(mx - dx * vao, my - dy * vao);
        ctx.lineTo(mx + nx * esp, my + ny * esp);
        ctx.lineTo(mx + dx * vao, my + dy * vao);
        ctx.lineTo(mx - nx * esp, my - ny * esp);
        ctx.closePath();
        ctx.fill();
        // fio de luz no meio da lâmina
        ctx.globalAlpha = forca * 0.28 * some;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(mx - dx * vao * 0.86, my - dy * vao * 0.86);
        ctx.lineTo(mx + dx * vao * 0.86, my + dy * vao * 0.86);
        ctx.stroke();
        // estilhaços saltando do corte
        ctx.globalAlpha = forca * (0.62 + reacao * 0.35) * some;
        ctx.strokeStyle = tema.destaque;
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let k = 0; k < 3; k++) {
          const ao = -0.52 + k * 0.52;
          const lado = k % 2 === 0 ? 1 : -1;
          const sx = mx + dx * vao * ao + nx * R * (0.03 + 0.012 * k) * lado;
          const sy = my + dy * vao * ao + ny * R * (0.03 + 0.012 * k) * lado;
          if (Math.hypot(sx - CX, sy - CY) > RAIO_UNIVERSO) continue;
          subPoligono(ctx, sx, sy, R * (0.026 + 0.009 * k), 3, ang + Math.PI * 0.5 + tempo * 0.55 * lado);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    /* PAPER MOON — favo e lua (moon_hive): placas hexagonais enchem o
       disco e uma lua crescente balança no alto. */
    function desenharFavo(ctx, tempo, pulso, reacao) {
      const forca = intensidadeUniverso;
      const respira = 0.9 + 0.08 * Math.sin(tempo * 1.25) + pulso * 0.05;
      const giro = Math.PI / 6 + tempo * velocidadeUniverso * 0.05;
      ctx.lineWidth = 1.5;
      for (let i = 0; i < FAVO.length; i++) {
        const c = FAVO[i];
        const onda = Math.sin(tempo * 1.05 + c.fase);
        ctx.globalAlpha = forca * (0.28 + c.profundidade * 0.42 + reacao * 0.24);
        ctx.strokeStyle = tema.placas[onda < -0.33 ? 0 : onda < 0.33 ? 1 : 2];
        poligono(ctx, c.x, c.y, CELULA * 0.52 * respira, 6, giro);
        ctx.stroke();
      }
      const lx = CX - RAIO_UNIVERSO * 0.24;
      const ly = CY - RAIO_UNIVERSO * 0.2;
      const raio = RAIO_UNIVERSO * 0.3;
      const balanco = Math.sin(tempo * 0.28) * 0.16;
      ctx.strokeStyle = tema.destaque;
      ctx.globalAlpha = forca * (0.62 + pulso * 0.14);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(lx, ly, raio, -Math.PI * 0.62 + balanco, Math.PI * 0.62 + balanco);
      ctx.stroke();
      ctx.globalAlpha = forca * 0.4;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(lx + raio * 0.42, ly, raio * 0.92, -Math.PI * 0.52 + balanco, Math.PI * 0.52 + balanco);
      ctx.stroke();
      ctx.globalAlpha = 1;
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

      const tocando = fase === "tocando";
      const pulso = tocando ? batidaPulso() : 0;
      if (comMusica() && musica) {
        // O universo da música (um único fundo, como na mesa).
        const reacao = energiaAcerto + Math.min(1, combo / 40) * 0.32;
        if (musica.universo === "laminas") desenharLaminas(ctx, relogio, pulso, reacao);
        else desenharFavo(ctx, relogio, pulso, reacao);
      } else if (img.roda) {
        // Na escolha, a arte da roda (abertura do jogo) bem apagada.
        ctx.save();
        ctx.beginPath();
        ctx.arc(CX, CY, R * 0.985, 0, Math.PI * 2);
        ctx.clip();
        ctx.globalAlpha = 0.13 + 0.03 * Math.sin(relogio * 2);
        const lado = R * 2.12;
        ctx.drawImage(img.roda, CX - lado / 2, CY - lado / 2, lado, lado);
        ctx.restore();
      }

      // onda da batida saindo do centro
      if (tocando && t >= inicioFase - batida) {
        const fasei = 1 - Math.cbrt(pulso);
        ctx.globalAlpha = (1 - fasei) * 0.22;
        ctx.strokeStyle = tema.primaria;
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
      ctx.strokeStyle = tema.primaria;
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
      ctx.strokeStyle = tema.primaria;
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
        brilho(ctx, mix > 0.05 ? corF : tema.brilho, mx, my, rm * (2.6 + pulsoF * 0.8 + fl * 1.6), 0.18 + pulsoF * 0.2 + mix * 0.6 + toque[f] * 0.35);
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
      const n = tocando ? Math.floor((t - inicioFase) / batida) : Math.floor(relogio / 0.4);
      const quadro = ((n % 8) + 8) % 8;
      const pulso = tocando ? batidaPulso() : 0.5 + 0.5 * Math.sin(relogio * 3);
      const tam = R * 0.36 * (1 + pulso * 0.06);
      ctx.globalCompositeOperation = "lighter";
      brilho(ctx, tema.brilho, CX, CY, tam * 1.1, 0.35 + pulso * 0.3);
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
      const p = (t - (nota.t - aproximacao)) / aproximacao;
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
      if (t < nota.t - aproximacao || t > nota.fim + 0.25) return;
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
      if (!ativa && t > nota.t - aproximacao * 0.7) {
        api.texto(ctx, "SEGURE", CX + (m[0] - CX) * 0.7, CY + (m[1] - CY) * 0.7 - 22, {
          tamanho: 15, peso: 900, cor: COR_CLARA[nota.cor], contorno: "rgba(0,0,0,.75)",
        });
      }
    }

    function desenharSlide(ctx, nota) {
      if (t < nota.t - aproximacao) return;
      if (nota.resolvida && !nota.finalizando) return;
      let aparece = 1;
      if (t < nota.t) {
        aparece = Math.min(1, Math.max(0, (t - (nota.t - aproximacao)) / (aproximacao * 0.55)));
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
      if (!nota.iniciada && t > nota.t - aproximacao * 0.7) {
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

    // Barras do HUD: o analisador ouve a música de verdade (antes do mudo,
    // então elas dançam até sem som). Fora da música, um ondular ocioso.
    function lerEspectro() {
      if (!audio.analisador || !audio.tocando) { espectro.fill(0); return; }
      audio.analisador.getByteFrequencyData(audio.dados);
      const dados = audio.dados;
      for (let i = 0; i < BARRAS; i++) {
        let maior = 0;
        const fim = Math.min(dados.length, Math.max(BORDAS_BARRAS[i] + 1, BORDAS_BARRAS[i + 1]));
        for (let k = BORDAS_BARRAS[i]; k < fim; k++) if (dados[k] > maior) maior = dados[k];
        espectro[i] = Math.pow(maior / 255, 1.6);
      }
    }

    function desenharEspectro(ctx, x, y, w, h) {
      ctx.fillStyle = "rgba(255,255,255,0.04)";
      ctx.fillRect(x, y, w, h);
      const passo = w / BARRAS;
      ctx.fillStyle = gradientes.barras;
      const energia = 0.45 + energiaMusica * 0.55;
      for (let i = 0; i < BARRAS; i++) {
        const ocioso = 0.06 + 0.04 * Math.sin(relogio * 2.2 + i * 0.7);
        const v = Math.min(1, Math.max(ocioso, espectro[i] * energia));
        const bh = Math.max(3, v * (h - 6));
        ctx.globalAlpha = 0.45 + v * 0.55;
        ctx.fillRect(x + i * passo + 1.5, y + h - bh - 3, passo - 3, bh);
      }
      ctx.globalAlpha = 1;
    }

    function desenharPainelHud(ctx) {
      const { x, y, w, h } = HUD;
      ctx.fillStyle = "rgba(10,4,30,0.9)";
      retanguloRedondo(ctx, x, y, w, h, 18);
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = gradientes.borda;
      ctx.stroke();
    }

    function desenharHud(ctx) {
      const { x, y, w, h } = HUD;
      desenharPainelHud(ctx);

      if (fase === "contagem") {
        // Como na mesa: na contagem o painel de cima mostra só o número,
        // na cor da vez (3 ciano, 2 vermelho, 1 amarelo).
        const numero = Math.max(1, Math.ceil(DURACAO_CONTAGEM - t));
        const fracao = DURACAO_CONTAGEM - t - (numero - 1);
        const escala = 1 + Math.max(0, fracao - 0.75) * 0.6;
        api.texto(ctx, String(numero), x + w / 2, y + h / 2 + 4, {
          tamanho: 104 * escala, peso: 900, cor: CORES_CONTAGEM[3 - numero], contorno: "rgba(0,0,0,.7)",
        });
        api.texto(ctx, musica.nome, x + 20, y + 26, { tamanho: 15, peso: 900, alinhar: "left", cor: tema.clara });
        return;
      }

      api.texto(ctx, musica.nome, x + 20, y + 30, { tamanho: 25, peso: 900, alinhar: "left", cor: "#ffffff" });
      api.texto(ctx, TEXTOS_MUSICA[indiceMusica].nivel, x + 20, y + 56, { tamanho: 14, peso: 800, alinhar: "left", cor: tema.clara });
      const centesimos = Math.round(precisaoMostrada * 100);
      if (centesimos !== centesimosPrecisao) { centesimosPrecisao = centesimos; textoPrecisao = formatarPct(centesimos / 100); }
      api.texto(ctx, textoPrecisao, x + w - 20, y + 31, { tamanho: 30, peso: 900, alinhar: "right", cor: tema.destaque });
      if (combo !== comboTexto) { comboTexto = combo; textoCombo = `COMBO ${combo}`; textoComboNumero = String(combo); }
      api.texto(ctx, textoCombo, x + w - 20, y + 57, { tamanho: 15, peso: 800, alinhar: "right", cor: "#ffffff" });

      // Espectro no lugar do vídeo da música (o retângulo central do HUD)
      desenharEspectro(ctx, x + 20, y + 72, w - 40, 62);

      // andamento da música, como a barra e o "0:42 / 1:30" da mesa
      const by = y + 152;
      const segundo = Math.round(t);
      if (segundo !== segundoTempo) { segundoTempo = segundo; textoTempo = `${formatarTempo(t)} / ${formatarTempo(audio.duracao)}`; }
      api.texto(ctx, textoTempo, x + w - 20, by, { tamanho: 13, peso: 800, alinhar: "right", cor: "rgba(255,255,255,0.75)" });
      const bw = w - 40 - 104;
      ctx.fillStyle = "rgba(255,255,255,0.12)";
      ctx.fillRect(x + 20, by - 3, bw, 6);
      ctx.fillStyle = tema.primaria;
      ctx.fillRect(x + 20, by - 3, bw * limitar(t / (audio.duracao || 1), 0, 1), 6);
    }

    function desenharMeio(ctx) {
      // faixa entre o HUD e o círculo: dica inicial, julgamento e combo
      if (fase === "contagem" || (fase === "tocando" && t < PRIMEIRA_NOTA - 0.9)) {
        ctx.globalAlpha = fase === "contagem" ? 1 : Math.min(1, (PRIMEIRA_NOTA - 0.9 - t) * 2);
        api.texto(ctx, "TOQUE NA FAIXA QUANDO", CX, 268, { tamanho: 24, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.6)" });
        api.texto(ctx, "O TAZO ENCAIXAR NO ANEL", CX, 300, { tamanho: 24, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.6)" });
        api.texto(ctx, temMouse ? "Teclas A S D F J K L Ç • segure as fitas • arraste as estrelas" : "Segure as fitas • arraste as estrelas", CX, 340, {
          tamanho: 15, peso: 700, cor: tema.clara,
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
      // a mesa mostra o combo a partir de 2 acertos seguidos
      if (combo >= 2) {
        api.texto(ctx, textoComboNumero, CX, 336, { tamanho: 56 + comboPulo * 10, peso: 900, cor: "#ffffff", contorno: tema.primaria });
        api.texto(ctx, "COMBO", CX, 378, { tamanho: 15, peso: 900, cor: tema.clara });
      }
    }

    /* Emblema de cada música no cartão, com o desenho do universo dela
       na mesa: lâminas para a Carmine, lua e favo para a Paper Moon. */
    function desenharEmblema(ctx, k, x, y, aceso) {
      const tm = TEMAS[k];
      ctx.globalAlpha = aceso ? 1 : 0.45;
      ctx.lineJoin = "round";
      if (MUSICAS[k].universo === "laminas") {
        for (let s = 0; s < 3; s++) {
          const ang = -0.75 + s * 0.38;
          const dx = Math.cos(ang);
          const dy = Math.sin(ang);
          const ox = x - dy * (s - 1) * 20;
          const oy = y + dx * (s - 1) * 20;
          ctx.fillStyle = tm.laminas[s];
          ctx.beginPath();
          ctx.moveTo(ox - dx * 34, oy - dy * 34);
          ctx.lineTo(ox - dy * 5, oy + dx * 5);
          ctx.lineTo(ox + dx * 34, oy + dy * 34);
          ctx.lineTo(ox + dy * 5, oy - dx * 5);
          ctx.closePath();
          ctx.fill();
        }
        ctx.strokeStyle = tm.destaque;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        subPoligono(ctx, x + 30, y - 26, 8, 3, relogio * 0.8);
        subPoligono(ctx, x - 32, y + 28, 6, 3, -relogio * 0.8);
        ctx.stroke();
      } else {
        ctx.strokeStyle = tm.placas[1];
        ctx.lineWidth = 2;
        ctx.beginPath();
        subPoligono(ctx, x + 16, y + 18, 13, 6, Math.PI / 6);
        subPoligono(ctx, x + 36, y + 6, 13, 6, Math.PI / 6);
        subPoligono(ctx, x + 36, y + 30, 13, 6, Math.PI / 6);
        ctx.stroke();
        ctx.strokeStyle = tm.destaque;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(x - 8, y - 6, 30, -Math.PI * 0.62, Math.PI * 0.62);
        ctx.stroke();
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(x + 5, y - 6, 27, -Math.PI * 0.52, Math.PI * 0.52);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // Cartão no estilo do seletor da mesa (selector_final.gd): fundo
    // escuro, barra de destaque grossa à esquerda quando marcado,
    // "TRACK 01", categoria, título grande, BPM, nível e recorde.
    function desenharCartao(ctx, k) {
      const c = CARTOES[k];
      const m = MUSICAS[k];
      const tm = TEMAS[k];
      const marcado = k === cursor;
      const carregando = fase === "carregando" && carga.indice === k;
      const pulso = 0.5 + 0.5 * Math.sin(relogio * 4);
      if (marcado) {
        // halo em traços largos e transparentes (sem shadowBlur)
        ctx.strokeStyle = tm.primaria;
        for (let i = 0; i < 3; i++) {
          ctx.globalAlpha = (0.08 + i * 0.06) * (0.75 + pulso * 0.25);
          ctx.lineWidth = 16 - i * 5;
          retanguloRedondo(ctx, c.x, c.y, c.w, c.h, 24);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = marcado ? "rgba(4,7,14,0.97)" : "rgba(1,3,6,0.86)";
      retanguloRedondo(ctx, c.x, c.y, c.w, c.h, 24);
      ctx.fill();
      ctx.lineWidth = marcado ? 3 : 1.5;
      ctx.strokeStyle = marcado ? tm.destaque : "rgba(244,7,48,0.28)";
      ctx.stroke();
      if (marcado) {
        ctx.fillStyle = tm.destaque;
        retanguloRedondo(ctx, c.x + 4, c.y + 18, 7, c.h - 36, 3.5);
        ctx.fill();
      }

      api.texto(ctx, TEXTOS_MUSICA[k].faixa, c.x + 30, c.y + 26, { tamanho: 13, peso: 800, alinhar: "left", cor: "#a3b8d6" });
      api.texto(ctx, m.category, c.x + c.w - 24, c.y + 26, { tamanho: 13, peso: 900, alinhar: "right", cor: tm.destaque });
      api.texto(ctx, m.nome, c.x + 30, c.y + 76, { tamanho: 46, peso: 900, alinhar: "left", cor: marcado ? "#ffffff" : "#94a6c2" });
      desenharEmblema(ctx, k, c.x + c.w - 76, c.y + 70, marcado);

      const by = c.y + c.h - 26;
      api.texto(ctx, TEXTOS_MUSICA[k].andamento, c.x + 30, by, { tamanho: 15, peso: 800, alinhar: "left", cor: tm.clara });
      if (carregando && carga.estado === "erro") {
        api.texto(ctx, "NÃO CARREGOU • TOQUE DE NOVO", c.x + c.w - 24, by, { tamanho: 14, peso: 900, alinhar: "right", cor: "#ff5468" });
      } else if (carregando) {
        const texto = carga.estado === "preparando" ? "PREPARANDO…" : `CARREGANDO ${Math.round(carga.progresso * 100)}%`;
        api.texto(ctx, texto, c.x + c.w - 52, by, { tamanho: 14, peso: 900, alinhar: "right", cor: "#ffffff" });
        // anel girando ao lado do texto
        ctx.strokeStyle = tm.destaque;
        ctx.lineWidth = 3;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.arc(c.x + c.w - 34, by, 9, relogio * 7, relogio * 7 + Math.PI * 1.4);
        ctx.stroke();
        ctx.lineCap = "butt";
        // barra do download no pé do cartão
        const largura = c.w - 60;
        ctx.fillStyle = "rgba(255,255,255,0.12)";
        ctx.fillRect(c.x + 30, c.y + c.h - 9, largura, 3);
        ctx.fillStyle = tm.destaque;
        ctx.fillRect(c.x + 30, c.y + c.h - 9, largura * (carga.estado === "preparando" ? 1 : carga.progresso), 3);
      } else {
        api.texto(ctx, textosRecorde[k], c.x + c.w - 24, by, { tamanho: 14, peso: 800, alinhar: "right", cor: "rgba(255,255,255,0.72)" });
      }
    }

    function desenharEscolha(ctx) {
      // o disco fica de cenário, apagado por baixo dos cartões
      ctx.fillStyle = "rgba(2,0,8,0.5)";
      ctx.fillRect(0, 0, LARGURA, ALTURA);

      desenharPainelHud(ctx);
      const { x, y, w } = HUD;
      api.texto(ctx, "ESCOLHA A MÚSICA", x + 20, y + 30, { tamanho: 25, peso: 900, alinhar: "left", cor: "#ffffff" });
      api.texto(ctx, "AS MÚSICAS DA MÁQUINA • NÍVEL FÁCIL", x + 20, y + 56, { tamanho: 14, peso: 800, alinhar: "left", cor: TEMA_PADRAO.clara });
      api.texto(ctx, `${MUSICAS.length} MÚSICAS`, x + w - 20, y + 31, { tamanho: 18, peso: 900, alinhar: "right", cor: COR_TEMA2 });
      desenharEspectro(ctx, x + 20, y + 72, w - 40, 62);
      api.texto(ctx, "HIT MUSIC", x + w / 2, y + 152, { tamanho: 14, peso: 900, cor: "rgba(255,255,255,0.6)" });

      for (let k = 0; k < CARTOES.length; k++) desenharCartao(ctx, k);

      const esperando = fase === "carregando" && carga.estado !== "erro";
      const aviso = esperando ? "A MÚSICA JÁ VAI COMEÇAR" : "TOQUE NA MÚSICA PARA JOGAR";
      ctx.globalAlpha = esperando ? 1 : 0.75 + 0.25 * Math.sin(relogio * 3.2);
      api.texto(ctx, aviso, CX, 572, { tamanho: 22, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.6)" });
      ctx.globalAlpha = 1;
      if (temMouse) {
        api.texto(ctx, "A / J ou setas escolhem • S ou ENTER confirma", CX, 604, { tamanho: 14, peso: 700, cor: TEMA_PADRAO.clara });
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
        pararFonte();
        carga.ficha++; // um download pela metade não começa mais nada
        carga.indice = -1;
        carga.estado = "";
        // a primeira chamada é a do console montando o jogo (atrás da capa);
        // as próximas são "Jogar" — e aí já houve um gesto da pessoa.
        fase = chamadasIniciar === 1 ? "capa" : "escolha";
        tema = TEMA_PADRAO;
        zerarPartida();
        if (fase === "escolha") {
          const ativacao = navigator.userActivation;
          if (!ativacao || ativacao.isActive || ativacao.hasBeenActive) acordarAudio();
        }
        api.placar({ pontos: 0, tempo: null, info: "" });
        pontosMostrados = 0;
      },

      atualizar(dt) {
        ultimoQuadro = performance.now();
        if (fase !== "contagem" && fase !== "tocando") return;

        const c = audio.ctx;
        if (c && c.state !== "running") {
          // Pausado por nós (aba/rolagem): o console voltou a rodar, então
          // a música volta. Travado por política de som: tenta de novo a
          // cada segundo e pede um toque na tela.
          if (audio.suspensoPorNos) {
            if (!document.hidden) { audio.suspensoPorNos = false; retomarContexto(); }
          } else {
            if (!audio.travadoDesde) audio.travadoDesde = ultimoQuadro;
            if (ultimoQuadro - audio.ultimaRetomada > 1000) { audio.ultimaRetomada = ultimoQuadro; retomarContexto(); }
          }
          return;
        }
        audio.travadoDesde = 0;
        if (audio.desvio !== null) audio.desvio -= dt * DERIVA_RELOGIO;
        t = tempoMusica();
        if (fase === "contagem" && t >= DURACAO_CONTAGEM) fase = "tocando";

        lerEspectro();
        if (precisaoMostrada !== precisao()) {
          // _display_score do stage_v10: a porcentagem desliza até o valor
          const alvo = precisao();
          precisaoMostrada += (alvo - precisaoMostrada) * 0.18;
          if (Math.abs(precisaoMostrada - alvo) < 0.005) precisaoMostrada = alvo;
        }

        if (fase === "tocando") {
          if (setaPendente && t - setaPendente.tempo > 0.05) descarregarSeta();

          while (proxNascer < TOTAL_NOTAS && NOTAS[proxNascer].t - aproximacao <= t) proxNascer++;

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
              if (t > n.t + janelaAcerto) errar(n);
            } else if (n.tipo === HOLD) {
              if (n.segurando) {
                if (t >= n.fim) acertar(n, 1, 0, MARCAS[n.faixa][0], MARCAS[n.faixa][1]);
              } else if (t > n.t + janelaAcerto) errar(n);
            } else if (n.iniciada) {
              if (t > n.fim + FOLGA_ARRASTO) errar(n);
            } else if (t > n.t + janelaAcerto * ESCALA_JANELA_ARRASTO) errar(n);
          }
          while (primeiraViva < proxNascer && NOTAS[primeiraViva].resolvida && !NOTAS[primeiraViva].finalizando) primeiraViva++;
        }

        for (let f = 0; f < FAIXAS; f++) {
          flash[f] = Math.max(0, flash[f] - dt * 3.1);
          toque[f] = Math.max(0, toque[f] - dt * 5);
        }
        energiaAcerto = Math.max(0, energiaAcerto - dt * 1.6);
        comboPulo = Math.max(0, comboPulo - dt * 6);

        const restante = Math.max(0, Math.ceil(audio.duracao - t));
        if (restante !== tempoMostrado) { tempoMostrado = restante; api.placar({ tempo: restante }); }

        // A partida acaba quando a música acaba (stage.gd: song_time >=
        // duração - 0,02, ou o "finished" do player).
        if (fase === "tocando" && (audio.acabou || t >= audio.duracao - FIM_ANTECIPADO)) terminarPartida();
      },

      desenhar(ctx) {
        relogio = performance.now() / 1000;
        if (fase === "capa") { desenharCapa(ctx); return; }
        prepararGradientes(ctx, tema);
        desenharFundo(ctx);
        desenharDisco(ctx);
        desenharAnel(ctx);
        desenharSelo(ctx);
        if (fase === "escolha" || fase === "carregando") { desenharEscolha(ctx); return; }

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
          api.texto(ctx, formatarPct(precisaoMostrada), CX, CY + 48, { tamanho: 30, peso: 900, cor: "#ffffff" });
        } else if (audio.travadoDesde && performance.now() - audio.travadoDesde > 600) {
          // o navegador segurou o som: um toque na tela libera
          ctx.fillStyle = "rgba(3,1,12,0.6)";
          ctx.fillRect(0, 0, LARGURA, ALTURA);
          api.texto(ctx, "TOQUE NA TELA", CX, CY - 16, { tamanho: 34, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.7)" });
          api.texto(ctx, "PARA LIGAR A MÚSICA", CX, CY + 22, { tamanho: 20, peso: 800, cor: tema.clara });
        }
      },

      apertar(x, y, id) {
        if (fase === "escolha" || fase === "carregando") {
          const k = cartaoEm(x, y);
          if (k >= 0) escolher(k);
          return;
        }
        if (fase !== "contagem" && fase !== "tocando") return;
        acordarAudio();
        if (fase !== "tocando") return;
        const tp = tempoMusica();
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
        soltarFonte(id, tempoMusica());
      },

      tecla(codigo, apertada) {
        if (fase === "escolha" || fase === "carregando") {
          if (!apertada) return;
          if (codigo in TECLAS_SOBE) cursor = (cursor + MUSICAS.length - 1) % MUSICAS.length;
          else if (codigo in TECLAS_DESCE) cursor = (cursor + 1) % MUSICAS.length;
          else if (codigo in TECLAS_CONFIRMA) escolher(cursor);
          return;
        }
        if (fase !== "tocando") return;
        const tp = tempoMusica();
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
        carga.ficha++;
        window.clearInterval(vigia);
        document.removeEventListener("visibilitychange", aoMudarVisibilidade);
        pararFonte();
        if (audio.ctx) {
          try { audio.ctx.close(); } catch (erro) { /* já fechado */ }
        }
        audio.ctx = null;
        audio.saida = null;
        audio.energia = null;
        audio.analisador = null;
        audio.buffer = null;
        audio.bufferId = null;
      },
    };
  },
};
