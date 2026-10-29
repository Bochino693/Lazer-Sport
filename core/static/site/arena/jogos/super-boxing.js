/* ======================================================================
   SUPER BOXING — a máquina de força de soco, em miniatura.

   Na máquina de verdade o saco desce, a pessoa bate, o sensor de feixe
   mede a velocidade do golpe e o jogo transforma isso numa nota de 0 a
   9999, com oito níveis de espetáculo (IMPACTO LEVE ... SOCO PERFEITO).
   Aqui não há sensor: quem faz o papel do braço é o MEDIDOR REDONDO do
   jogo original (o aro com os 40 gomos). Ele enche e esvazia sem parar,
   e o toque na hora certa vira a força do soco — a zona vermelha, no fim
   do arco, é onde mora o NOCAUTE.

   O que veio do jogo original (super-boxing-android7):
     - a escala 0..9999 e os OITO NÍVEIS com nome, cor, tremor, clarão,
       ondas, faíscas, brasas, raios, chuva, rachaduras e hit-stop
       (scripts/fx/score_tier.gd);
     - a variação da nota: o sino de ±13%, o "dia bom / dia ruim", a
       PAREDE DOS 8000 e os dígitos que nunca repetem
       (scripts/score_curve.gd);
     - o anel que enche pela RAIZ da nota (um soco comum não pode acender
       só a pontinha) e a contagem de 1,1 s que cresce e dá um tranco;
     - A NOTA DA RODADA É O MELHOR SOCO, e não a soma (main.gd:
       SOCOS_POR_RODADA). Lá são dois socos; a miniatura dá três;
     - as frases do locutor por nível, as provocações da espera, o
       "MAIS FORTE! / ESSE NÃO PONTUOU" (scripts/arena/frases.gd);
     - FIGHT!, NEVER GIVE UP! e FIGHT TILL THE END (assets/tema).
   ====================================================================== */

const LARGURA = 540;
const ALTURA = 960;

/* As artes saem prontas em 2x da tela lógica: o console desenha com até
   o dobro de pixels em telas densas, e uma camada pré-desenhada em 1x
   ficaria borrada justamente onde mais se olha. */
const NITIDEZ = 2;

/* ----------------------------------------------------------------------
   A ESCALA E OS NÍVEIS (cópia de ScoreTier / GameDef)
   As quantidades de efeito são as do original, pensadas para 1080x1920;
   a miniatura divide na hora de usar (ver `golpe`).
   ---------------------------------------------------------------------- */
const SCORE_MAX = 9999;
const NIVEIS = [
  { id: "LEVE", max: 1799, nome: "IMPACTO LEVE", cor: "#8697b4", tremor: 4, clarao: 0.10, hitstop: 0, zoom: 1.0, ondas: 1, ondaRaio: 380, faiscas: 14, brasas: 0, raios: 0, estilhacos: 10, chuva: 0, poeira: 10, rachaduras: false, tunel: false, palco: false, festa: 0 },
  { id: "BOM", max: 3999, nome: "BOM GOLPE", cor: "#ff4d5e", tremor: 9, clarao: 0.22, hitstop: 0, zoom: 1.0, ondas: 2, ondaRaio: 520, faiscas: 26, brasas: 22, raios: 0, estilhacos: 0, chuva: 0, poeira: 8, rachaduras: false, tunel: false, palco: false, festa: 0 },
  { id: "FORTE", max: 6499, nome: "GOLPE FORTE", cor: "#ffb31f", tremor: 16, clarao: 0.38, hitstop: 0, zoom: 1.0, ondas: 2, ondaRaio: 700, faiscas: 34, brasas: 60, raios: 4, estilhacos: 0, chuva: 0, poeira: 0, rachaduras: false, tunel: false, palco: false, festa: 0 },
  { id: "EXPLOSIVO", max: 7999, nome: "EXPLOSIVO", cor: "#fff2d0", tremor: 22, clarao: 0.62, hitstop: 0, zoom: 1.0, ondas: 2, ondaRaio: 860, faiscas: 46, brasas: 90, raios: 8, estilhacos: 0, chuva: 0, poeira: 0, rachaduras: true, tunel: false, palco: false, festa: 0 },
  { id: "NOCAUTE", max: 8999, nome: "NOCAUTE", cor: "#ff6a12", tremor: 30, clarao: 0.72, hitstop: 0.095, zoom: 1.07, ondas: 3, ondaRaio: 980, faiscas: 54, brasas: 110, raios: 12, estilhacos: 0, chuva: 30, poeira: 0, rachaduras: true, tunel: false, palco: false, festa: 1.15 },
  { id: "PESO", max: 9699, nome: "PESO-PESADO", cor: "#ff2d45", tremor: 36, clarao: 0.80, hitstop: 0.110, zoom: 1.10, ondas: 3, ondaRaio: 1100, faiscas: 64, brasas: 150, raios: 18, estilhacos: 0, chuva: 55, poeira: 0, rachaduras: true, tunel: true, palco: false, festa: 0.90 },
  { id: "LENDARIO", max: 9998, nome: "LENDÁRIO", cor: "#ffd200", tremor: 40, clarao: 0.88, hitstop: 0.110, zoom: 1.12, ondas: 4, ondaRaio: 1240, faiscas: 80, brasas: 190, raios: 26, estilhacos: 0, chuva: 80, poeira: 0, rachaduras: true, tunel: true, palco: true, festa: 0.70 },
  { id: "PERFEITO", max: 9999, nome: "SOCO PERFEITO", cor: "#ffffff", tremor: 46, clarao: 1.00, hitstop: 0.360, zoom: 1.18, ondas: 5, ondaRaio: 1400, faiscas: 110, brasas: 260, raios: 40, estilhacos: 0, chuva: 120, poeira: 0, rachaduras: true, tunel: true, palco: true, festa: 0.55 },
];

function indiceDoNivel(pontos) {
  const p = Math.max(0, Math.min(SCORE_MAX, pontos));
  for (let i = 0; i < NIVEIS.length; i++) if (p <= NIVEIS[i].max) return i;
  return NIVEIS.length - 1;
}

/* As três faixas grossas (GameDef.Faixa): fraca, média e forte. São as
   cores da moldura e do medidor — e a zona vermelha do medidor é a FORTE. */
const COR_FAIXA = ["#8697b4", "#ffd014", "#ff2a6d"];
function faixaDe(pontos) {
  const i = indiceDoNivel(pontos);
  return i >= 4 ? 2 : i >= 2 ? 1 : 0;
}

/* O anel enche pela RAIZ da nota (main.gd, _draw_score_hero): na escala
   reta um soco comum acendia só a pontinha e parecia fraco. Então a
   posição do ponteiro f vale f² da escala, e as fronteiras das faixas no
   arco são as raízes das notas em que elas começam. */
const ZONA_MEDIA = Math.sqrt(4000 / SCORE_MAX); // ~0,63
const ZONA_FORTE = Math.sqrt(8000 / SCORE_MAX); // ~0,89 — daqui pra cima é NOCAUTE
/* Abaixo disto "não é soco" (a velocidade mínima do original). */
const FORCA_MINIMA = 0.12;

/* ----------------------------------------------------------------------
   AS FRASES (scripts/arena/frases.gd)
   ---------------------------------------------------------------------- */
const GOLPES = {
  LEVE: ["ELE NEM PISCOU!", "ISSO FOI UM CUMPRIMENTO", "AINDA ESTÁ AQUECENDO?", "A GUARDA NEM ABRIU"],
  BOM: ["AGORA SIM!", "ELE SENTIU ESSE!", "BOA PEGADA, CAMPEÃO", "O GINÁSIO ACORDOU"],
  FORTE: ["A GUARDA ABRIU!", "ELE CAMBALEOU!", "QUE ESTRONDO!", "ISSO VAI DOER AMANHÃ"],
  EXPLOSIVO: ["O PROTETOR VOOU!", "ISSO FOI UM TIRO!", "A PLATEIA LEVANTOU!", "ELE VIU ESTRELAS!"],
  NOCAUTE: ["DIRETO NO QUEIXO!", "APAGOU AS LUZES!", "ELE NÃO VIU ESSE!", "BOA NOITE, LUTADOR"],
  PESO: ["ISSO NÃO FOI SOCO, FOI TROVÃO", "A LONA PEDIU ARREGO!", "O RINGUE INTEIRO OUVIU", "PESO-PESADO DE VERDADE!"],
  LENDARIO: ["ISSO VAI PARA O MURAL!", "NINGUÉM ACREDITOU NO QUE VIU", "LENDA DA CASA!", "A ARENA NUNCA MAIS SERÁ A MESMA"],
  PERFEITO: ["PERFEIÇÃO ABSOLUTA!", "A MÁQUINA PEDIU DESCULPAS", "NÃO EXISTE NADA DEPOIS DISSO", "O SOCO PERFEITO ACONTECEU AQUI"],
};
const ESPERA = ["ELE ESTÁ TE ESPERANDO…", "MIRE NO QUEIXO", "MOSTRE O QUE VOCÊ TEM", "A ARENA É SUA", "SEM MEDO. ELE AGUENTA"];
const CHAMADAS = ["SOQUE AGORA!", "AGORA O SEGUNDO!", "AGORA O TERCEIRO!"];

/* ----------------------------------------------------------------------
   A NOTA DE UM SOCO (scripts/score_curve.gd → variar)

   O soco de verdade nunca dá o mesmo número duas vezes: em cima do valor
   "de tabela" entram um sino largo (±13%), o dia bom / dia ruim (18% das
   vezes, de 6 a 16% para cima ou para baixo), a parede dos 8000 (acima
   dela cada ponto custa mais que o anterior) e um tremido nos dígitos,
   desviando de número redondo e das últimas notas.
   ---------------------------------------------------------------------- */
const LIMIAR_DIFICIL = 8000;
const FAIXA_ALTA = 1998;
const ESCALA_ALTA = 1650;
/* No original o 9999 sai 1 vez em 1000 golpes que já encostaram no teto.
   Numa partida de três socos isso nunca aconteceria: aqui é 1 em 30,
   e continua valendo só para quem cravou o ponteiro no topo do arco. */
const CHANCE_PERFEITA = 30;
const recentes = []; // vive entre partidas, como a memória de notas da máquina

function sorteio(a, b) { return a + Math.random() * (b - a); }
function sorteioInteiro(a, b) { return Math.floor(a + Math.random() * (b - a + 1)); }
function limitar(v, a, b) { return v < a ? a : v > b ? b : v; }

function paredeDos8000(nota, sorte) {
  if (nota <= LIMIAR_DIFICIL) return nota;
  const excesso = (nota - LIMIAR_DIFICIL) * limitar(sorte, 0, 1);
  return LIMIAR_DIFICIL + FAIXA_ALTA * (1 - Math.exp(-excesso / ESCALA_ALTA));
}

function notaDoSoco(tabela) {
  if (tabela >= SCORE_MAX && sorteioInteiro(1, CHANCE_PERFEITA) === 1) return SCORE_MAX;
  const base = Math.min(tabela, SCORE_MAX);
  const sino = (Math.random() + Math.random() + Math.random()) / 1.5 - 1;
  let fator = 1 + sino * 0.13;
  if (Math.random() < 0.18) {
    const embalo = sorteio(0.06, 0.16);
    fator += Math.random() < 0.5 ? embalo : -embalo;
  }
  const nota = paredeDos8000(base * Math.max(fator, 0.5), sorteio(0.55, 1));
  let final = limitar(Math.round(nota) + sorteioInteiro(-27, 27), 1, SCORE_MAX - 1);
  let tentativas = 0;
  while ((final % 100 === 0 || recentes.includes(final)) && tentativas < 12) {
    const passo = sorteioInteiro(3, 41);
    final = limitar(final + (Math.random() < 0.5 ? passo : -passo), 1, SCORE_MAX - 1);
    tentativas++;
  }
  recentes.push(final);
  if (recentes.length > 16) recentes.shift();
  return final;
}

/* ----------------------------------------------------------------------
   TEMPOS (game_def.gd e main.gd)
   ---------------------------------------------------------------------- */
const SOCOS = 3;
const VOO_DA_LUVA = 0.13;            // da guarda até o saco
const VOLTA_DA_LUVA = 0.26;
const IMPACTO_DURACAO = 0.26;        // "LENDO SENSOR": flash + onda de choque
const CONTAGEM_DURACAO = 1.1;        // o número sobe crescendo
const MEDIDOR_POP_S = 0.42;          // o tranco do fim da contagem
const ESPERA_PARA_O_PROXIMO_SOCO = 1.9;
const MAIS_FORTE_S = 1.2;
const SUBIDA_DO_SACO = 1.1;
/* Quanto dura uma ida e volta do ponteiro, por soco: cada soco cobra
   um pouco mais de reflexo que o anterior. */
const PERIODOS = [1.5, 1.22, 1.0];

const FESTA = ["#ff26a8", "#ffd014", "#fff9ef", "#46dcff", "#8a3cff", "#ff6a2a"];
const AMBAR = "#ffd014";
const OURO_TARJA = "#ffdc27";
const CREME = "#f6fbff";
const TINTA_LEVE = "#a197d6";

/* Onde as coisas ficam na tela (a metade das medidas de 1080x1920). */
const PIVO = { x: 270, y: -6 };          // onde a corrente do saco prende na treliça
const SACO_ALVO = 336;                   // distância do pivô até o alvo pintado no saco
const MEDIDOR = { x: 270, y: 734, r: 80 };
const MEDIDOR_INICIO = Math.PI * 0.75;
const MEDIDOR_VOLTA = Math.PI * 1.5;
const MEDIDOR_GOMOS = 40;
const CHAMADA_Y = 853;
const FRASE_Y = 879;
const CARTOES_Y = 897;
const CARTOES_ALTURA = 50;
const TARJA = 8;
/* Os pontos do céu onde os fogos estouram (impact_director.gd, CEU). */
const CEU = [[105, 215], [435, 165], [205, 125], [465, 280], [75, 150], [340, 200], [270, 105]];

/* ----------------------------------------------------------------------
   AJUDANTES DE DESENHO
   ---------------------------------------------------------------------- */
function novaTela(largura, altura) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(largura * NITIDEZ));
  c.height = Math.max(1, Math.round(altura * NITIDEZ));
  const g = c.getContext("2d");
  g.scale(NITIDEZ, NITIDEZ);
  return { c, g };
}

function retanguloRedondo(g, x, y, w, h, r) {
  const raio = Math.min(r, w / 2, h / 2);
  g.beginPath();
  g.moveTo(x + raio, y);
  g.arcTo(x + w, y, x + w, y + h, raio);
  g.arcTo(x + w, y + h, x, y + h, raio);
  g.arcTo(x, y + h, x, y, raio);
  g.arcTo(x, y, x + w, y, raio);
  g.closePath();
}

function misturar(a, b, t) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const canal = (d) => {
    const ca = (pa >> d) & 255;
    const cb = (pb >> d) & 255;
    return Math.round(ca + (cb - ca) * t);
  };
  return "#" + ((1 << 24) | (canal(16) << 16) | (canal(8) << 8) | canal(0)).toString(16).slice(1);
}

/* As peças brancas do original (aro, giros, luva) são MÁSCARAS: o Godot
   as tinge na hora. Aqui a tinta é feita uma vez por cor e guardada. */
function criarTingidor() {
  const guardadas = new Map();
  /* `multiplicar` é o "modulate" do Godot de verdade: o branco vira a cor
     e o escuro continua escuro (é o que a tarja zebrada precisa). Sem ele
     a peça inteira vira a cor, que é o certo para as máscaras. */
  return (img, cor, multiplicar = false) => {
    if (!img) return null;
    const chave = img.src + "|" + cor + (multiplicar ? "|x" : "");
    let pronta = guardadas.get(chave);
    if (!pronta) {
      pronta = document.createElement("canvas");
      pronta.width = img.naturalWidth || img.width;
      pronta.height = img.naturalHeight || img.height;
      const g = pronta.getContext("2d");
      g.drawImage(img, 0, 0);
      g.globalCompositeOperation = multiplicar ? "multiply" : "source-in";
      g.fillStyle = cor;
      g.fillRect(0, 0, pronta.width, pronta.height);
      if (multiplicar) {
        g.globalCompositeOperation = "destination-in";
        g.drawImage(img, 0, 0);
      }
      guardadas.set(chave, pronta);
    }
    return pronta;
  };
}

function suavizar(t) { const u = 1 - limitar(t, 0, 1); return 1 - u * u * u; }
/* Passa do ponto e volta (arcade_stage.gd, _passar_do_ponto). */
function passarDoPonto(t, forca = 1.9) { const p = limitar(t, 0, 1) - 1; return p * p * ((forca + 1) * p + forca) + 1; }

/* ======================================================================
   O JOGO
   ====================================================================== */
export default {
  largura: LARGURA,
  altura: ALTURA,
  artes: {
    fundo: "super-boxing/fundo.webp",
    lona: "super-boxing/lona.webp",
    telao: "super-boxing/telao.webp",
    teto: "super-boxing/teto.webp",
    torcidaCima: "super-boxing/torcida_cima.webp",
    torcidaBaixo: "super-boxing/torcida_baixo.webp",
    faixa: "super-boxing/faixa_lateral.webp",
    saia: "super-boxing/saia.webp",
    facho: "super-boxing/facho.webp",
    brilho: "super-boxing/brilho.webp",
    zebra: "super-boxing/tarja_zebra.webp",
    tema: "super-boxing/fundo_tema.webp",
    fight: "super-boxing/fight.webp",
    never: "super-boxing/never_give_up.webp",
    ateOFim: "super-boxing/ate_o_fim.webp",
    aro: "super-boxing/medidor_aro.webp",
    giroFora: "super-boxing/medidor_giro_fora.webp",
    giroDentro: "super-boxing/medidor_giro_dentro.webp",
    luvaCorpo: "super-boxing/luva_corpo.webp",
    luvaBrilho: "super-boxing/luva_brilho.webp",
    cartaoGiro: "super-boxing/cartao_giro.webp",
  },

  criar(api) {
    const img = api.img;
    const tingir = criarTingidor();

    /* ------------------------------------------------------------------
       AS CAMADAS QUE NÃO SE MEXEM, desenhadas uma vez só.
       É a mesma lição do original (background_estatico): o ginásio é o
       mesmo de um quadro para o outro, e repintá-lo peça a peça a cada
       quadro é trabalho jogado fora.
       ------------------------------------------------------------------ */
    const camadaFundo = montarFundo();
    const camadaRingue = montarRingue();
    const camadaRodape = montarRodape();
    const spriteSaco = montarSaco();
    const spriteLuva = montarLuva();

    function montarFundo() {
      const { c, g } = novaTela(LARGURA, 640);
      g.fillStyle = "#07051a";
      g.fillRect(0, 0, LARGURA, 640);
      // a parede do ginásio: faixa de LED com o letreiro e a torcida ao fundo
      if (img.fundo) g.drawImage(img.fundo, -80, -24, 700, 700);
      // a treliça com os refletores, sumindo para dentro da parede
      if (img.teto) {
        const t = novaTela(LARGURA, 150);
        t.g.drawImage(img.teto, 0, -10, LARGURA, 150);
        t.g.setTransform(1, 0, 0, 1, 0, 0);
        t.g.globalCompositeOperation = "destination-in";
        const m = t.g.createLinearGradient(0, 0, 0, t.c.height);
        m.addColorStop(0, "rgba(0,0,0,1)");
        m.addColorStop(0.55, "rgba(0,0,0,.85)");
        m.addColorStop(1, "rgba(0,0,0,0)");
        t.g.fillStyle = m;
        t.g.fillRect(0, 0, t.c.width, t.c.height);
        g.drawImage(t.c, 0, 0, LARGURA, 150);
      }
      // a névoa roxa que a luz faz no meio do ginásio
      const nevoa = g.createRadialGradient(270, 330, 20, 270, 330, 330);
      nevoa.addColorStop(0, "rgba(138,60,255,.22)");
      nevoa.addColorStop(1, "rgba(138,60,255,0)");
      g.fillStyle = nevoa;
      g.fillRect(0, 0, LARGURA, 640);
      return c;
    }

    function montarRingue() {
      const { c, g } = novaTela(LARGURA, 660);
      // a luz do ginásio cai de cima: a torcida mais perto do escuro (vai
      // aqui, e não na torcida, porque esta camada é desenhada por cima dela)
      const sombra = g.createLinearGradient(0, 300, 0, 470);
      sombra.addColorStop(0, "rgba(7,5,26,0)");
      sombra.addColorStop(1, "rgba(7,5,26,.75)");
      g.fillStyle = sombra;
      g.fillRect(0, 300, LARGURA, 170);
      // AS FAIXAS DOS LADOS (faixa_lateral), penduradas na frente da torcida
      if (img.faixa) {
        g.save();
        g.shadowColor = "rgba(0,0,0,.55)";
        g.shadowBlur = 12;
        g.drawImage(img.faixa, 12, 176, 86, 172);
        g.translate(LARGURA - 12, 0);
        g.scale(-1, 1);
        g.drawImage(img.faixa, 0, 176, 86, 172);
        g.restore();
      }
      // A LONA EM PERSPECTIVA: uma linha da imagem por linha da tela, com a
      // profundidade corrigida (1/largura) — o logo no meio do ringue não
      // pode esticar por igual de perto e de longe.
      const longe = { y: 462, x0: 112, x1: 428 };
      const perto = { y: 604, x0: -70, x1: 610 };
      if (img.lona) {
        const passos = (perto.y - longe.y) * NITIDEZ;
        const w0 = longe.x1 - longe.x0;
        const w1 = perto.x1 - perto.x0;
        const lado = img.lona.naturalHeight || 512;
        const largo = img.lona.naturalWidth || 512;
        for (let i = 0; i < passos; i++) {
          const t = i / (passos - 1);
          const largura = w0 + (w1 - w0) * t;
          const v = (1 / w0 - 1 / largura) / (1 / w0 - 1 / w1);
          const x = longe.x0 + (perto.x0 - longe.x0) * t;
          const y = longe.y + (perto.y - longe.y) * t;
          g.drawImage(img.lona, 0, Math.min(lado - 1, v * lado), largo, 1, x, y, largura, 1 / NITIDEZ + 0.6);
        }
        // a luz de cima caindo no meio da lona
        const luz = g.createRadialGradient(270, 540, 10, 270, 540, 260);
        luz.addColorStop(0, "rgba(255,240,220,.16)");
        luz.addColorStop(1, "rgba(255,240,220,0)");
        g.fillStyle = luz;
        g.beginPath();
        g.moveTo(longe.x0, longe.y); g.lineTo(longe.x1, longe.y); g.lineTo(perto.x1, perto.y); g.lineTo(perto.x0, perto.y);
        g.closePath();
        g.fill();
      }
      // A SAIA do ringue, de frente para a câmera
      if (img.saia) {
        const altura = 46;
        const largura = altura * 8;
        for (let x = -60; x < LARGURA; x += largura) g.drawImage(img.saia, x, perto.y, largura, altura);
        const sombra = g.createLinearGradient(0, perto.y, 0, perto.y + altura);
        sombra.addColorStop(0, "rgba(0,0,0,.05)");
        sombra.addColorStop(1, "rgba(0,0,0,.45)");
        g.fillStyle = sombra;
        g.fillRect(0, perto.y, LARGURA, altura);
      }
      g.fillStyle = "rgba(255,255,255,.25)";
      g.fillRect(0, perto.y - 1, LARGURA, 2);
      // OS POSTES DO FUNDO, com os protetores (azul de um lado, vermelho do outro)
      const postes = [[longe.x0, "#3a5bff"], [longe.x1, "#e63950"]];
      for (const [x, cor] of postes) {
        g.fillStyle = "#1a1230";
        g.fillRect(x - 4, longe.y - 82, 8, 84);
        g.fillStyle = cor;
        retanguloRedondo(g, x - 6, longe.y - 80, 12, 74, 5);
        g.fill();
        g.fillStyle = "rgba(255,255,255,.3)";
        g.fillRect(x - 3, longe.y - 76, 2, 66);
      }
      // AS CORDAS: vermelha, branca e azul (as três alturas de ALTURAS_DAS_CORDAS)
      const cores = ["#e63950", "#f4f2ff", "#3a5bff"];
      const alturas = [22, 44, 66];
      g.lineCap = "round";
      for (let k = 0; k < 3; k++) {
        const h = alturas[k];
        g.strokeStyle = cores[k];
        g.lineWidth = 2.4;
        // a do fundo, de poste a poste
        g.beginPath();
        g.moveTo(longe.x0, longe.y - h);
        g.quadraticCurveTo(270, longe.y - h + 3, longe.x1, longe.y - h);
        g.stroke();
        // as dos lados, vindo para perto (ficam mais grossas e mais altas)
        g.lineWidth = 3.6;
        g.beginPath();
        g.moveTo(longe.x0, longe.y - h);
        g.lineTo(perto.x0 + 40, perto.y - h * 2.3);
        g.moveTo(longe.x1, longe.y - h);
        g.lineTo(perto.x1 - 40, perto.y - h * 2.3);
        g.stroke();
      }
      // as duas cordas da frente, baixas, por cima da lona
      for (let k = 0; k < 2; k++) {
        const y = perto.y - 22 - k * 30;
        g.strokeStyle = "rgba(0,0,0,.35)";
        g.lineWidth = 7;
        g.beginPath(); g.moveTo(-10, y + 3); g.quadraticCurveTo(270, y + 12, LARGURA + 10, y + 3); g.stroke();
        g.strokeStyle = cores[k];
        g.lineWidth = 5;
        g.beginPath(); g.moveTo(-10, y); g.quadraticCurveTo(270, y + 9, LARGURA + 10, y); g.stroke();
        g.strokeStyle = "rgba(255,255,255,.35)";
        g.lineWidth = 1.4;
        g.beginPath(); g.moveTo(-10, y - 1.5); g.quadraticCurveTo(270, y + 7.5, LARGURA + 10, y - 1.5); g.stroke();
      }
      return c;
    }

    /* O rodapé: o escuro que sobe por cima do ringue para os textos
       grandes (RODAPE_ESCURO do original) e, por baixo, a arte do
       gabinete — os raios roxos e magenta. */
    function montarRodape() {
      const topo = 520;
      const altura = ALTURA - topo;
      const { c, g } = novaTela(LARGURA, altura);
      const escuro = g.createLinearGradient(0, 0, 0, 170);
      escuro.addColorStop(0, "rgba(8,3,22,0)");
      escuro.addColorStop(1, "rgba(8,3,22,.94)");
      g.fillStyle = escuro;
      g.fillRect(0, 0, LARGURA, 170);
      g.fillStyle = "rgba(8,3,22,.94)";
      g.fillRect(0, 170, LARGURA, altura - 170);
      if (img.tema) {
        const t = novaTela(LARGURA, altura);
        t.g.drawImage(img.tema, 0, topo, LARGURA, altura, 0, 0, LARGURA, altura);
        t.g.setTransform(1, 0, 0, 1, 0, 0);
        t.g.globalCompositeOperation = "destination-in";
        const m = t.g.createLinearGradient(0, 0, 0, 220 * NITIDEZ);
        m.addColorStop(0, "rgba(0,0,0,0)");
        m.addColorStop(1, "rgba(0,0,0,.42)");
        t.g.fillStyle = m;
        t.g.fillRect(0, 0, t.c.width, t.c.height);
        g.drawImage(t.c, 0, 0, LARGURA, altura);
      }
      return { c, topo };
    }

    /* O SACO, desenhado à mão nas cores do original (Paleta.SACO_*): vinil
       vermelho vivo, couro nas pontas, o alvo da marca no meio. A corrente
       vai junto no desenho porque o conjunto todo gira no pivô. */
    function montarSaco() {
      const L = 160;
      const A = 480;
      const { c, g } = novaTela(L, A);
      const cx = L / 2;
      // a corrente
      for (let i = 0; i * 11 < 186; i++) {
        const y = i * 11;
        g.strokeStyle = i % 2 ? "#8a8598" : "#c9c4d8";
        g.lineWidth = 2.6;
        g.beginPath();
        g.ellipse(cx, y + 6, i % 2 ? 2.2 : 4.4, 6, 0, 0, Math.PI * 2);
        g.stroke();
      }
      g.strokeStyle = "#c9c4d8";
      g.lineWidth = 3;
      g.beginPath(); g.arc(cx, 192, 7, 0, Math.PI * 2); g.stroke();
      // as quatro alças de couro, do anel até a tampa
      g.strokeStyle = "#3a2030";
      g.lineWidth = 4;
      for (const x of [18, 56, 104, 142]) {
        g.beginPath(); g.moveTo(cx, 197); g.lineTo(x, 222); g.stroke();
      }
      // o corpo (um cilindro: sombra nas bordas, brilho perto da esquerda)
      const x0 = 10, y0 = 220, w = 140, h = 252;
      const corpo = g.createLinearGradient(x0, 0, x0 + w, 0);
      corpo.addColorStop(0, "#6d1426");
      corpo.addColorStop(0.18, "#c42a42");
      corpo.addColorStop(0.36, "#ff6f82");
      corpo.addColorStop(0.5, "#e63950");
      corpo.addColorStop(0.82, "#a3203a");
      corpo.addColorStop(1, "#56101f");
      retanguloRedondo(g, x0, y0, w, h, 26);
      g.fillStyle = corpo;
      g.fill();
      // as pontas de couro
      const couro = g.createLinearGradient(x0, 0, x0 + w, 0);
      couro.addColorStop(0, "#3d1f2a");
      couro.addColorStop(0.35, "#8a5262");
      couro.addColorStop(1, "#2e1620");
      g.save();
      retanguloRedondo(g, x0, y0, w, h, 26);
      g.clip();
      g.fillStyle = couro;
      g.fillRect(x0, y0, w, 30);
      g.fillRect(x0, y0 + h - 30, w, 30);
      // costuras
      g.strokeStyle = "rgba(255,230,235,.55)";
      g.lineWidth = 1.2;
      g.setLineDash([4, 4]);
      for (const y of [y0 + 33, y0 + h - 33, y0 + 90, y0 + 168]) {
        g.beginPath(); g.moveTo(x0, y); g.lineTo(x0 + w, y); g.stroke();
      }
      g.setLineDash([]);
      // o brilho do vinil
      g.fillStyle = "rgba(255,255,255,.22)";
      g.fillRect(x0 + 38, y0 + 34, 9, h - 68);
      g.fillStyle = "rgba(255,255,255,.10)";
      g.fillRect(x0 + 50, y0 + 34, 4, h - 68);
      g.restore();
      // o alvo pintado (o mesmo da marca): é para ele que a luva vai
      const ay = SACO_ALVO + PIVO.y;
      const aneis = [[30, "#fff4f6"], [23, "#e63950"], [15, "#fff4f6"], [7, "#e63950"]];
      for (const [r, cor] of aneis) {
        g.fillStyle = cor;
        g.beginPath(); g.ellipse(cx + 4, ay, r * 0.92, r, 0, 0, Math.PI * 2); g.fill();
      }
      // o contorno
      retanguloRedondo(g, x0, y0, w, h, 26);
      g.strokeStyle = "#53202f";
      g.lineWidth = 3;
      g.stroke();
      return { c, largura: L, altura: A, cx };
    }

    /* A LUVA QUE VOA: vista por trás, como quem está dando o soco a vê —
       o punho grande em cima, o dedão do lado e o cano branco perto da
       câmera. É a forma do ícone do original (Icones.luva: punho, dedão,
       palma e cano), só que com volume. */
    function montarLuva() {
      const L = 220;
      const A = 250;
      const { c, g } = novaTela(L, A);
      const contorno = "#3b0d18";
      // o cano
      const pano = g.createLinearGradient(56, 0, 168, 0);
      pano.addColorStop(0, "#b9b6c8");
      pano.addColorStop(0.4, "#ffffff");
      pano.addColorStop(1, "#a9a6ba");
      retanguloRedondo(g, 58, 160, 108, 84, 20);
      g.fillStyle = pano;
      g.fill();
      g.lineWidth = 4;
      g.strokeStyle = contorno;
      g.stroke();
      g.fillStyle = "#e63950";
      g.fillRect(60, 192, 104, 16);
      g.fillStyle = "rgba(0,0,0,.18)";
      g.fillRect(60, 206, 104, 3);
      // o vermelho da luva
      const vermelho = g.createRadialGradient(84, 62, 8, 110, 104, 128);
      vermelho.addColorStop(0, "#ff96a2");
      vermelho.addColorStop(0.3, "#f0253f");
      vermelho.addColorStop(0.75, "#b5132b");
      vermelho.addColorStop(1, "#6e0a18");
      // o dedão
      g.save();
      g.translate(44, 122);
      g.rotate(-0.38);
      g.beginPath(); g.ellipse(0, 0, 28, 48, 0, 0, Math.PI * 2);
      g.fillStyle = vermelho; g.fill();
      g.strokeStyle = contorno; g.stroke();
      g.restore();
      // a palma que liga o punho ao cano
      retanguloRedondo(g, 54, 100, 116, 76, 26);
      g.fillStyle = vermelho; g.fill();
      g.strokeStyle = contorno; g.stroke();
      // o punho
      g.beginPath(); g.ellipse(114, 90, 80, 78, 0, 0, Math.PI * 2);
      g.fillStyle = vermelho; g.fill();
      g.strokeStyle = contorno; g.stroke();
      // a dobra dos dedos e a costura do dedão
      g.strokeStyle = "rgba(70,0,16,.55)";
      g.lineWidth = 3;
      g.beginPath(); g.ellipse(118, 66, 58, 30, 0, Math.PI * 0.08, Math.PI * 0.92); g.stroke();
      g.beginPath(); g.moveTo(66, 108); g.quadraticCurveTo(58, 140, 72, 170); g.stroke();
      // os brilhos
      g.fillStyle = "rgba(255,255,255,.55)";
      g.beginPath(); g.ellipse(84, 50, 26, 13, -0.55, 0, Math.PI * 2); g.fill();
      g.fillStyle = "rgba(255,255,255,.25)";
      g.beginPath(); g.ellipse(150, 120, 9, 22, 0.3, 0, Math.PI * 2); g.fill();
      return { c, largura: L, altura: A, centro: { x: 112, y: 92 } };
    }

    /* ------------------------------------------------------------------
       ESTADO
       ------------------------------------------------------------------ */
    let estado = "armado";   // armado | voo | medindo | contando | veredito | maisForte | subindo | fim
    let tEstado = 0;
    let relogio = 0;
    let socos = [];          // as notas, na ordem
    let fase = 0;            // o ponteiro: fase da ida e volta
    let forca = 0;           // a posição do ponteiro (0..1) no arco
    let forcaTravada = 0;    // onde o toque pegou
    let notaAtual = 0;
    let nivelAtual = NIVEIS[0];
    let mostrado = 0;        // o número que está subindo na contagem
    let vereditoT = -1;      // há quanto tempo o veredito abriu
    let fraseAtual = "";
    let semente = 0;
    let terminou = false;
    let tique = 0;
    let proximaFesta = 0;
    let indiceCeu = 0;
    let mao = 1;             // 1 = direita, -1 = esquerda (alterna a cada soco)
    // o saco: balanço de lado (ângulo) e recuo (para longe da câmera)
    let anguloSaco = 0, velAngulo = 0, recuo = 0, velRecuo = 0, amasso = 0, alturaSaco = 0;
    // a luva
    let luvaT = -1;
    let luvaDe = { x: 0, y: 0 }, luvaPara = { x: 0, y: 0 };
    // efeitos de tela
    let clarao = 0, zoom = 1, hitstop = 0, brilhoGolpe = 0, pulo = 0;
    let torcidaEmPe = 0;
    let ondas = [], raios = [], confetes = [], rachaduras = null, estrelao = null, tunel = null;
    let faixas = [];         // FIGHT! / NEVER GIVE UP! / FIGHT TILL THE END
    let telaoNumero = -1;    // o telão mostra o número enquanto ele vale
    let telaoCor = CREME;

    function iniciar() {
      estado = "armado";
      tEstado = 0;
      relogio = 0;
      socos = [];
      fase = 0;
      forca = 0;
      forcaTravada = 0;
      notaAtual = 0;
      nivelAtual = NIVEIS[0];
      mostrado = 0;
      vereditoT = -1;
      fraseAtual = "";
      semente = sorteioInteiro(0, 50);
      terminou = false;
      tique = 0;
      proximaFesta = 0;
      mao = 1;
      anguloSaco = 0; velAngulo = 0; recuo = 0; velRecuo = 0; amasso = 0; alturaSaco = 0;
      luvaT = -1;
      clarao = 0; zoom = 1; hitstop = 0; brilhoGolpe = 0; pulo = 0; torcidaEmPe = 0;
      ondas = []; raios = []; confetes = []; rachaduras = null; estrelao = null; tunel = null;
      faixas = [];
      telaoNumero = -1;
      // A entrada da luta, como no gabinete: FIGHT! bate, NEVER GIVE UP! desliza.
      // (Depois do "VAI!" do console, que ocupa o meio da tela no começo.)
      faixas.push({ img: img.fight, x: 270, y: 318, largura: 400, t: 0, dur: 1.6, tipo: "bate", atraso: 0.55 });
      faixas.push({ img: img.never, x: 270, y: 404, largura: 330, t: 0, dur: 1.3, tipo: "desliza", atraso: 0.9 });
      api.placar({ pontos: 0, tempo: null, info: `SOCO 1/${SOCOS}` });
    }

    /* ------------------------------------------------------------------
       O SOCO
       ------------------------------------------------------------------ */
    function alvoNaTela() {
      // o alvo pintado, girando junto com o saco e recuando com ele
      const escala = 1 - 0.16 * recuo;
      const d = SACO_ALVO * escala;
      return {
        x: PIVO.x - Math.sin(anguloSaco) * d,
        y: PIVO.y - alturaSaco - recuo * 26 + Math.cos(anguloSaco) * d,
      };
    }

    function socar() {
      if (estado !== "armado" || terminou) return;
      forcaTravada = forca;
      estado = "voo";
      tEstado = 0;
      luvaT = 0;
      const alvo = alvoNaTela();
      luvaDe = { x: 270 + mao * 150, y: 1090 };
      luvaPara = { x: alvo.x + mao * 6, y: alvo.y + 26 };
      api.som("whoosh");
      // os cartazes saem da frente: o soco é que é o espetáculo agora
      for (const f of faixas) f.dur = Math.min(f.dur, Math.max(0, f.t - f.atraso) + 0.25);
    }

    function impacto() {
      const alvo = alvoNaTela();
      if (forcaTravada < FORCA_MINIMA) {
        // "abaixo disto não é soco": a máquina não conta e pede mais
        estado = "maisForte";
        tEstado = 0;
        velRecuo += 1.2;
        velAngulo += mao * 0.12;
        api.som("batida");
        api.som("erro");
        api.tremer(3);
        api.efeitos.explosao(alvo.x, alvo.y, { cor: ["#8697b4", "#ffffff"], n: 8, velocidade: 160, tamanho: 3 });
        return;
      }
      const tabela = forcaTravada >= 0.985 ? SCORE_MAX : Math.round(forcaTravada * forcaTravada * SCORE_MAX);
      notaAtual = notaDoSoco(tabela);
      // A ZONA VERMELHA É PROMESSA: aqui o ponteiro faz o papel do braço, e
      // quem acertou o vermelho não pode ler "EXPLOSIVO" por azar do sino.
      // A variação continua valendo, só que da parede dos 8000 para cima.
      if (forcaTravada >= ZONA_FORTE && notaAtual < LIMIAR_DIFICIL) {
        notaAtual = LIMIAR_DIFICIL + sorteioInteiro(12, 380);
        if (notaAtual % 100 === 0) notaAtual += 7;
      }
      nivelAtual = NIVEIS[indiceDoNivel(notaAtual)];
      golpe(alvo, nivelAtual, indiceDoNivel(notaAtual));
      estado = "medindo";
      tEstado = 0;
      mostrado = 0;
      telaoNumero = 0;
      telaoCor = AMBAR;
    }

    /* O ESPETÁCULO DO SOCO, por nível (fx/impact_director.gd → golpe).
       As quantidades do original são para uma tela de 1080 de largura;
       aqui a tela tem a metade, e o canvas paga cada partícula. */
    function golpe(alvo, nivel, indice) {
      const n = (q, div) => Math.ceil(q / div);
      const potencia = indice / (NIVEIS.length - 1);
      for (let i = 0; i < nivel.ondas; i++) {
        ondas.push({
          x: alvo.x, y: alvo.y,
          r0: 20 + i * 35,
          r1: nivel.ondaRaio * 0.5 * (1 + i * 0.22),
          cor: [CREME, nivel.cor, AMBAR][i % 3],
          alfa: 0.66 - i * 0.1,
          largura: 9 - i * 1.4,
          t: -i * 0.09,
          dur: 0.55 + i * 0.22,
        });
      }
      api.efeitos.explosao(alvo.x, alvo.y, {
        cor: [nivel.cor, "#ffffff", AMBAR], n: n(nivel.faiscas, 1.6), velocidade: 300 + nivel.tremor * 11, tamanho: 3.4, gravidade: 380, vida: 0.7,
      });
      if (nivel.brasas) {
        api.efeitos.explosao(alvo.x, alvo.y, { cor: FESTA, n: n(nivel.brasas, 3.2), velocidade: 380 + nivel.tremor * 9, tamanho: 2.6, gravidade: 520, vida: 1.1 });
      }
      if (nivel.estilhacos) api.efeitos.explosao(alvo.x, alvo.y, { cor: "#6b7b98", n: n(nivel.estilhacos, 1.5), velocidade: 220, tamanho: 3, gravidade: 700 });
      if (nivel.poeira) api.efeitos.explosao(alvo.x, alvo.y + 110, { cor: "rgba(140,150,190,.55)", n: n(nivel.poeira, 1.5), velocidade: 90, tamanho: 6, gravidade: -40, vida: 1.1 });
      if (nivel.raios && !api.reduzido) {
        const quantos = n(nivel.raios, 2);
        for (let i = 0; i < quantos; i++) raios.push(novoRaio(alvo, 110 + nivel.tremor * 4));
      }
      if (nivel.chuva) {
        const quantos = api.reduzido ? n(nivel.chuva, 6) : n(nivel.chuva, 1.6);
        for (let i = 0; i < quantos; i++) confetes.push(novoConfete(-sorteio(10, 420)));
      }
      if (nivel.rachaduras) rachaduras = novasRachaduras(alvo, nivel);
      if (nivel.tunel && !api.reduzido) tunel = { t: 0, dur: 0.55, cor: nivel.cor, x: alvo.x, y: alvo.y };
      estrelao = { t: 0, dur: 0.4, cor: nivel.cor, x: alvo.x, y: alvo.y, forca: 0.5 + potencia * 0.8, giro: sorteio(0, Math.PI) };
      clarao = Math.max(clarao, nivel.clarao);
      hitstop = nivel.hitstop;
      if (!api.reduzido) zoom = nivel.zoom;
      brilhoGolpe = 1;
      // o saco: recua e balança na proporção do golpe
      velRecuo += 2.2 + potencia * 5.5;
      velAngulo += mao * (0.25 + potencia * 0.75) * sorteio(0.7, 1.1);
      amasso = 1;
      // a torcida levanta nos golpes de verdade
      if (indice >= 2) { torcidaEmPe = 1; pulo = 1; }
      api.tremer(nivel.tremor * 0.55);
      api.vibrar(18 + indice * 14);
      api.som("soco");
      if (indice >= 2) api.som("batida");
      if (indice >= 4) api.som("strike");
    }

    function novoRaio(centro, alcance) {
      const pontos = [centro.x, centro.y];
      const angulo = sorteio(0, Math.PI * 2);
      const passos = 6;
      const comprimento = sorteio(alcance * 0.55, alcance);
      for (let i = 1; i <= passos; i++) {
        const d = (comprimento * i) / passos;
        const desvio = sorteio(-0.32, 0.32);
        pontos.push(centro.x + Math.cos(angulo + desvio) * d, centro.y + Math.sin(angulo + desvio) * d);
      }
      return { pontos, t: 0, dur: sorteio(0.18, 0.32) };
    }

    function novoConfete(y) {
      return {
        x: sorteio(10, LARGURA - 10), y,
        vy: sorteio(110, 230), vx: sorteio(-30, 30),
        rot: sorteio(0, Math.PI), vr: sorteio(-7, 7),
        balanco: sorteio(0, 6), cor: FESTA[sorteioInteiro(0, FESTA.length - 1)],
        w: sorteio(5, 9), h: sorteio(8, 13),
      };
    }

    /* AS RACHADURAS NO VIDRO (EXPLOSIVO para cima): linhas que saem do
       ponto do soco e se dividem — a tela "trincou". */
    function novasRachaduras(centro, nivel) {
      const linhas = [];
      const quantas = 5 + Math.round(nivel.tremor / 8);
      for (let i = 0; i < quantas; i++) {
        let angulo = (i / quantas) * Math.PI * 2 + sorteio(-0.25, 0.25);
        let x = centro.x, y = centro.y;
        const pontos = [x, y];
        const passos = sorteioInteiro(4, 7);
        for (let p = 0; p < passos; p++) {
          const passo = sorteio(18, 42);
          angulo += sorteio(-0.45, 0.45);
          x += Math.cos(angulo) * passo;
          y += Math.sin(angulo) * passo;
          pontos.push(x, y);
          if (p === 2 && Math.random() < 0.7) {
            const a2 = angulo + (Math.random() < 0.5 ? 0.7 : -0.7);
            linhas.push([x, y, x + Math.cos(a2) * sorteio(20, 45), y + Math.sin(a2) * sorteio(20, 45)]);
          }
        }
        linhas.push(pontos);
      }
      return { linhas, t: 0, dur: 1.7 };
    }

    function abrirVeredito() {
      estado = "veredito";
      tEstado = 0;
      vereditoT = 0;
      mostrado = notaAtual;
      socos.push(notaAtual);
      const indice = indiceDoNivel(notaAtual);
      fraseAtual = GOLPES[nivelAtual.id][(semente + socos.length) % 4];
      telaoNumero = notaAtual;
      telaoCor = COR_FAIXA[faixaDe(notaAtual)];
      proximaFesta = 0.35;
      const melhor = Math.max(...socos);
      api.placar({ pontos: melhor, info: socos.length < SOCOS ? `SOCO ${socos.length + 1}/${SOCOS}` : "MELHOR SOCO" });
      api.som(indice >= 2 ? "combo" : indice >= 1 ? "acerto" : "nota");
      // NEVER GIVE UP! quando o soco foi fraco e ainda há chance
      if (indice === 0 && socos.length < SOCOS) {
        faixas.push({ img: img.never, x: 270, y: 300, largura: 330, t: 0, dur: 1.5, tipo: "bate", atraso: 0.3 });
      }
    }

    function proximoSoco() {
      estado = "armado";
      tEstado = 0;
      fase = 0;
      forca = 0;
      vereditoT = -1;
      telaoNumero = -1;
      mao = -mao;
      torcidaEmPe = 0;
      // O ÚLTIMO SOCO tem cartaz próprio: FIGHT TILL THE END
      if (socos.length === SOCOS - 1) {
        faixas.push({ img: img.ateOFim, x: 270, y: 318, largura: 380, t: 0, dur: 1.5, tipo: "desliza", atraso: 0 });
      }
    }

    function encerrar() {
      if (terminou) return;
      terminou = true;
      const melhor = Math.max(...socos);
      const lista = socos.map((p) => p.toLocaleString("pt-BR")).join(" · ");
      api.terminar({
        pontos: melhor,
        titulo: NIVEIS[indiceDoNivel(melhor)].nome,
        detalhe: `Seus socos: ${lista}. Vale o melhor.`,
      });
    }

    /* ------------------------------------------------------------------
       O RELÓGIO
       ------------------------------------------------------------------ */
    function atualizar(dt) {
      relogio += dt;

      // efeitos que andam mesmo no hit-stop (são a "foto" do golpe)
      clarao = Math.max(0, clarao - dt * 2.6);
      brilhoGolpe = Math.max(0, brilhoGolpe - dt * 1.6);
      for (const f of faixas) f.t += dt;
      faixas = faixas.filter((f) => f.t < f.dur + f.atraso);

      if (hitstop > 0) { hitstop -= dt; return; }

      zoom += (1 - zoom) * Math.min(1, dt * 5);
      pulo = Math.max(0, pulo - dt * 1.4);
      amasso = Math.max(0, amasso - dt * 7);

      // o saco: duas molas amortecidas, uma de lado e uma de recuo
      velAngulo += (-anguloSaco * 9 - velAngulo * 1.6) * dt;
      anguloSaco += velAngulo * dt;
      velRecuo += (-recuo * 26 - velRecuo * 3.2) * dt;
      recuo += velRecuo * dt;
      recuo = limitar(recuo, -0.4, 1.6);

      for (const o of ondas) o.t += dt;
      ondas = ondas.filter((o) => o.t < o.dur);
      for (const r of raios) r.t += dt;
      raios = raios.filter((r) => r.t < r.dur);
      for (const c of confetes) {
        c.y += c.vy * dt;
        c.x += (c.vx + Math.sin(relogio * 3 + c.balanco) * 40) * dt;
        c.rot += c.vr * dt;
      }
      confetes = confetes.filter((c) => c.y < ALTURA + 20);
      if (rachaduras) { rachaduras.t += dt; if (rachaduras.t > rachaduras.dur) rachaduras = null; }
      if (estrelao) { estrelao.t += dt; if (estrelao.t > estrelao.dur) estrelao = null; }
      if (tunel) { tunel.t += dt; if (tunel.t > tunel.dur) tunel = null; }

      tEstado += dt;
      if (luvaT >= 0) luvaT += dt;

      switch (estado) {
        case "armado": {
          // O PONTEIRO: enche e esvazia, uma ida e volta por período
          fase += dt / PERIODOS[Math.min(socos.length, PERIODOS.length - 1)];
          const p = fase % 1;
          forca = 1 - Math.abs(1 - p * 2);
          break;
        }
        case "voo":
          if (tEstado >= VOO_DA_LUVA) impacto();
          break;
        case "maisForte":
          if (tEstado >= MAIS_FORTE_S) { estado = "armado"; tEstado = 0; fase = 0; }
          break;
        case "medindo":
          if (tEstado >= IMPACTO_DURACAO) { estado = "contando"; tEstado = 0; tique = 0; }
          break;
        case "contando": {
          const p = limitar(tEstado / CONTAGEM_DURACAO, 0, 1);
          mostrado = Math.round(notaAtual * (1 - Math.pow(1 - p, 2.2)));
          telaoNumero = mostrado;
          telaoCor = misturar(AMBAR, COR_FAIXA[faixaDe(notaAtual)], p * 0.82);
          // os tiques da contagem, cada vez mais juntos
          const marca = Math.floor(Math.pow(p, 0.7) * 9);
          if (marca > tique) { tique = marca; api.som("clique"); }
          if (tEstado >= CONTAGEM_DURACAO) abrirVeredito();
          break;
        }
        case "veredito": {
          vereditoT += dt;
          // os fogos de quem passou do NOCAUTE
          if (nivelAtual.festa > 0) {
            proximaFesta -= dt;
            if (proximaFesta <= 0) {
              proximaFesta = nivelAtual.festa;
              const [cx, cy] = CEU[indiceCeu++ % CEU.length];
              const x = cx + sorteio(-20, 20), y = cy + sorteio(-15, 15);
              ondas.push({ x, y, r0: 3, r1: sorteio(100, 160), cor: CREME, alfa: 0.55, largura: 3.5, t: 0, dur: 0.85 });
              ondas.push({ x, y, r0: 2, r1: sorteio(75, 130), cor: nivelAtual.cor, alfa: 0.45, largura: 2.5, t: 0, dur: 1.05 });
              api.efeitos.explosao(x, y, { cor: FESTA, n: 12 + Math.round(nivelAtual.raios / 3), velocidade: 220, tamanho: 2.6, gravidade: 160, vida: 1.3 });
              api.som("tiro");
            }
          }
          if (tEstado >= ESPERA_PARA_O_PROXIMO_SOCO + MEDIDOR_POP_S) {
            if (socos.length >= SOCOS) { estado = "subindo"; tEstado = 0; api.som("whoosh"); }
            else proximoSoco();
          }
          break;
        }
        case "subindo":
          // O SACO SOBE no fim da rodada, como na máquina
          vereditoT += dt;
          alturaSaco = 560 * Math.pow(limitar(tEstado / SUBIDA_DO_SACO, 0, 1), 2);
          if (tEstado >= SUBIDA_DO_SACO) { estado = "fim"; encerrar(); }
          break;
        default:
          break;
      }
    }

    /* ------------------------------------------------------------------
       O DESENHO
       ------------------------------------------------------------------ */
    function desenhar(ctx) {
      const alvo = alvoNaTela();
      const t = relogio;

      // O MUNDO, com o zoom do golpe em volta do ponto do soco
      ctx.save();
      if (zoom > 1.001) {
        ctx.translate(alvo.x, alvo.y);
        ctx.scale(zoom, zoom);
        ctx.translate(-alvo.x, -alvo.y);
      }
      ctx.drawImage(camadaFundo, 0, 0, LARGURA, 640);
      desenharFachos(ctx, t);
      desenharTorcida(ctx, t);
      ctx.drawImage(camadaRingue, 0, 0, LARGURA, 660);
      desenharSaco(ctx);
      desenharTelao(ctx);
      desenharTunel(ctx);
      desenharOndas(ctx);
      desenharRaios(ctx);
      desenharEstrelao(ctx);
      ctx.restore();

      desenharFaixas(ctx);

      // O RODAPÉ: o medidor, a chamada e os cartões dos socos
      ctx.drawImage(camadaRodape.c, 0, camadaRodape.topo, LARGURA, ALTURA - camadaRodape.topo);
      desenharMedidor(ctx, t);
      desenharChamada(ctx, t);
      desenharCartoes(ctx, t);

      // a luva vem da câmera: passa por cima de tudo, até do rodapé
      desenharLuva(ctx);
      desenharRachaduras(ctx);
      desenharConfetes(ctx);
      if (clarao > 0.01) {
        ctx.fillStyle = `rgba(255,250,240,${(clarao * 0.85).toFixed(3)})`;
        ctx.fillRect(0, 0, LARGURA, ALTURA);
      }
      desenharTarjas(ctx);
    }

    function desenharFachos(ctx, t) {
      if (!img.facho) return;
      // os fachos de luz até a lona: respiram com a torcida e acendem no golpe
      const fontes = [[40, "#ff26a8"], [150, "#ffffff"], [270, "#46dcff"], [390, "#ffffff"], [500, "#ff26a8"]];
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      for (let i = 0; i < fontes.length; i++) {
        const [x, cor] = fontes[i];
        const respira = 0.10 + 0.05 * Math.sin(t * 1.3 + i * 1.7);
        ctx.globalAlpha = Math.min(0.6, respira + brilhoGolpe * 0.32);
        const alvoX = 270 + (x - 270) * 0.35;
        const angulo = Math.atan2(alvoX - x, 470);
        ctx.save();
        ctx.translate(x, 20);
        ctx.rotate(-angulo);
        ctx.drawImage(tingir(img.facho, cor), -42, 0, 84, 500);
        ctx.restore();
      }
      // o brilho dos refletores da treliça
      if (img.brilho) {
        for (let i = 0; i < 7; i++) {
          const x = 30 + i * 80;
          ctx.globalAlpha = Math.min(1, 0.35 + 0.35 * Math.max(0, Math.sin(t * 2.1 + i * 2.3)) + brilhoGolpe * 0.3);
          const lado = 26 + 6 * Math.sin(t * 3 + i);
          ctx.drawImage(img.brilho, x - lado / 2, 18 + (i % 2) * 22 - lado / 2, lado, lado);
        }
      }
      ctx.restore();
    }

    function desenharTorcida(ctx, t) {
      // de braços baixados respirando; de braços para cima e pulando no golpe
      const emPe = torcidaEmPe > 0 && img.torcidaCima;
      const im = emPe ? img.torcidaCima : img.torcidaBaixo;
      if (!im) return;
      const salto = emPe ? Math.abs(Math.sin(t * 9)) * 7 * (0.35 + pulo) : Math.sin(t * 1.7) * 1.2;
      ctx.save();
      ctx.globalAlpha = 0.92;
      ctx.drawImage(im, -6, 252 - salto, LARGURA + 12, 136);
      ctx.restore();
      // (a sombra que cai sobre a torcida já vem pintada na camada do ringue)
    }

    function desenharSaco(ctx) {
      const s = spriteSaco;
      const escala = 1 - 0.16 * recuo;
      const y0 = PIVO.y - alturaSaco - recuo * 26;
      // a sombra na lona
      if (alturaSaco < 200) {
        ctx.save();
        ctx.globalAlpha = 0.38 * (1 - alturaSaco / 200);
        ctx.fillStyle = "#000";
        ctx.beginPath();
        ctx.ellipse(270 - Math.sin(anguloSaco) * 360, 532, 74 * escala, 13 * escala, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      ctx.save();
      ctx.translate(PIVO.x, y0);
      ctx.rotate(anguloSaco);
      ctx.scale(escala * (1 + amasso * 0.06), escala * (1 - amasso * 0.03));
      ctx.drawImage(s.c, -s.cx, 0, s.largura, s.altura);
      // o saco se acende na cor do golpe por um instante
      if (brilhoGolpe > 0.02 && estado !== "armado") {
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = brilhoGolpe * 0.35;
        ctx.fillStyle = nivelAtual.cor;
        retanguloRedondo(ctx, -s.cx + 10, 220, 140, 252, 26);
        ctx.fill();
      }
      ctx.restore();
    }

    function desenharTelao(ctx) {
      // o telão pendurado na treliça, por cima da corrente do saco
      const x = 132, y = 30, w = 276, h = 142;
      ctx.strokeStyle = "#2a2140";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x + 40, 0); ctx.lineTo(x + 40, y);
      ctx.moveTo(x + w - 40, 0); ctx.lineTo(x + w - 40, y);
      ctx.stroke();
      ctx.fillStyle = "#0d0820";
      retanguloRedondo(ctx, x - 7, y - 7, w + 14, h + 14, 9);
      ctx.fill();
      ctx.strokeStyle = telaoNumero >= 0 ? misturar("#ff26a8", telaoCor, 0.7) : "#ff26a8";
      ctx.lineWidth = 2;
      ctx.stroke();
      if (telaoNumero < 0) {
        if (img.telao) ctx.drawImage(img.telao, x, y, w, h);
      } else {
        // O NÚMERO NO TELÃO, como na máquina: sobe crescendo e fica
        const fundo = ctx.createLinearGradient(0, y, 0, y + h);
        fundo.addColorStop(0, "#1a0d3a");
        fundo.addColorStop(1, "#08041a");
        ctx.fillStyle = fundo;
        ctx.fillRect(x, y, w, h);
        const medindo = estado === "medindo";
        const texto = medindo ? "- - - -" : String(telaoNumero).padStart(4, "0");
        let escala = 1;
        if (estado === "contando") escala = 0.7 + 0.3 * limitar(tEstado / CONTAGEM_DURACAO, 0, 1);
        if (vereditoT >= 0 && vereditoT < MEDIDOR_POP_S) escala += 0.16 * Math.sin(Math.PI * vereditoT / MEDIDOR_POP_S);
        api.texto(ctx, "FORÇA DO SOCO", x + w / 2, y + 20, { tamanho: 13, cor: "#d9d1ff", peso: 800 });
        ctx.save();
        ctx.translate(x + w / 2, y + 78);
        ctx.scale(escala, escala);
        api.texto(ctx, texto, 0, 0, { tamanho: 68, cor: medindo ? AMBAR : telaoCor, peso: 900, contorno: "#0e0624", sombra: telaoCor });
        ctx.restore();
        api.texto(ctx, vereditoT >= 0 ? "PONTOS" : medindo ? "LENDO SENSOR" : "CONTANDO", x + w / 2, y + h - 15, { tamanho: 12, cor: "#a197d6", peso: 800 });
        // as linhas do painel de LED
        ctx.fillStyle = "rgba(0,0,0,.22)";
        for (let ly = y + 2; ly < y + h; ly += 4) ctx.fillRect(x, ly, w, 1.5);
      }
      // o reflexo do vidro
      ctx.fillStyle = "rgba(255,255,255,.06)";
      ctx.beginPath();
      ctx.moveTo(x, y); ctx.lineTo(x + w * 0.45, y); ctx.lineTo(x + w * 0.25, y + h); ctx.lineTo(x, y + h);
      ctx.closePath();
      ctx.fill();
    }

    function desenharLuva(ctx) {
      if (luvaT < 0) return;
      const s = spriteLuva;
      // a ida: acelera até o saco (o soco), o rastro fica para trás
      const ida = VOO_DA_LUVA;
      const espera = 0.06;
      let p, alfa = 1;
      if (luvaT < ida) p = Math.pow(luvaT / ida, 1.7);
      else if (luvaT < ida + espera) p = 1;
      else {
        // a volta: recolhe devagar e some antes de voltar a encher a tela
        const v = (luvaT - ida - espera) / VOLTA_DA_LUVA;
        if (v >= 1) { luvaT = -1; return; }
        p = 1 - v * v * 0.6;
        alfa = 1 - v;
      }
      const posicao = (q) => ({
        x: luvaDe.x + (luvaPara.x - luvaDe.x) * q,
        y: luvaDe.y + (luvaPara.y - luvaDe.y) * q,
        escala: 2.5 + (0.92 - 2.5) * q,
      });
      const desenharEm = (q, a) => {
        const pos = posicao(q);
        ctx.save();
        ctx.globalAlpha = a;
        ctx.translate(pos.x, pos.y);
        // a luva da mão esquerda é a direita espelhada
        ctx.scale(pos.escala * -mao, pos.escala);
        ctx.rotate(-0.18 * (1 - q));
        ctx.drawImage(s.c, -s.centro.x, -s.centro.y, s.largura, s.altura);
        ctx.restore();
      };
      if (luvaT < ida) {
        // o vento e o rastro
        const atual = posicao(p);
        ctx.save();
        ctx.strokeStyle = "rgba(255,255,255,.35)";
        ctx.lineWidth = 3;
        for (let i = 0; i < 4; i++) {
          const dx = (i - 1.5) * 34 * atual.escala;
          ctx.beginPath();
          ctx.moveTo(atual.x + dx, atual.y + 70 * atual.escala);
          ctx.lineTo(atual.x + dx * 1.3, atual.y + 190 * atual.escala);
          ctx.stroke();
        }
        ctx.restore();
        for (let k = 3; k >= 1; k--) {
          const q = Math.pow(Math.max(0, luvaT - k * 0.022) / ida, 1.7);
          desenharEm(q, 0.1 * (4 - k));
        }
      }
      desenharEm(p, alfa);
    }

    function desenharOndas(ctx) {
      ctx.save();
      for (const o of ondas) {
        if (o.t < 0) continue;
        const p = o.t / o.dur;
        const e = 1 - Math.pow(1 - p, 2.2);
        ctx.globalAlpha = Math.max(0, o.alfa * (1 - p));
        ctx.strokeStyle = o.cor;
        ctx.lineWidth = Math.max(1, o.largura * (1 - p * 0.6));
        ctx.beginPath();
        ctx.arc(o.x, o.y, o.r0 + (o.r1 - o.r0) * e, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    }

    function desenharRaios(ctx) {
      if (!raios.length) return;
      ctx.save();
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      for (const r of raios) {
        const a = 1 - r.t / r.dur;
        for (const [cor, largura] of [[AMBAR, 5], ["#ffffff", 1.8]]) {
          ctx.globalAlpha = a;
          ctx.strokeStyle = cor;
          ctx.lineWidth = largura;
          ctx.beginPath();
          ctx.moveTo(r.pontos[0], r.pontos[1]);
          for (let i = 2; i < r.pontos.length; i += 2) ctx.lineTo(r.pontos[i], r.pontos[i + 1]);
          ctx.stroke();
        }
      }
      ctx.restore();
    }

    /* O ESTRELÃO DA PANCADA (impact_director.gd): a estrela de quadrinho
       que abre no ponto do soco, branca com a borda na cor do nível. */
    function desenharEstrelao(ctx) {
      if (!estrelao) return;
      const p = estrelao.t / estrelao.dur;
      const some = Math.pow(1 - p, 1.6);
      const raio = (36 + 70 * suavizar(p * 1.6)) * estrelao.forca;
      const pontas = 14;
      ctx.save();
      ctx.translate(estrelao.x, estrelao.y);
      ctx.rotate(estrelao.giro);
      ctx.globalAlpha = some;
      ctx.beginPath();
      for (let i = 0; i < pontas * 2; i++) {
        const r = i % 2 ? raio * 0.48 : raio * (i % 4 ? 0.92 : 1.12);
        const a = (i / (pontas * 2)) * Math.PI * 2;
        ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
      }
      ctx.closePath();
      ctx.fillStyle = "#fffdf2";
      ctx.fill();
      ctx.lineWidth = 5;
      ctx.strokeStyle = estrelao.cor === "#ffffff" ? AMBAR : estrelao.cor;
      ctx.stroke();
      ctx.restore();
    }

    /* O TÚNEL DE LUZ (PESO-PESADO para cima): riscos que convergem para
       o ponto do soco, a tela inteira puxando o olho para ele. */
    function desenharTunel(ctx) {
      if (!tunel) return;
      const p = tunel.t / tunel.dur;
      ctx.save();
      ctx.globalAlpha = 0.55 * (1 - p);
      ctx.strokeStyle = tunel.cor;
      ctx.lineWidth = 3;
      ctx.beginPath();
      for (let i = 0; i < 28; i++) {
        const a = (i / 28) * Math.PI * 2 + i * 0.37;
        const r0 = 620 - 300 * p - (i % 3) * 40;
        const r1 = r0 - 120;
        ctx.moveTo(tunel.x + Math.cos(a) * r0, tunel.y + Math.sin(a) * r0);
        ctx.lineTo(tunel.x + Math.cos(a) * r1, tunel.y + Math.sin(a) * r1);
      }
      ctx.stroke();
      ctx.restore();
    }

    function desenharRachaduras(ctx) {
      if (!rachaduras) return;
      const p = rachaduras.t / rachaduras.dur;
      const a = p < 0.7 ? 1 : 1 - (p - 0.7) / 0.3;
      ctx.save();
      ctx.lineJoin = "round";
      for (const [cor, largura, alfa] of [["#000000", 4, 0.35], ["#ffffff", 1.6, 0.9]]) {
        ctx.globalAlpha = a * alfa;
        ctx.strokeStyle = cor;
        ctx.lineWidth = largura;
        ctx.beginPath();
        for (const l of rachaduras.linhas) {
          ctx.moveTo(l[0], l[1]);
          for (let i = 2; i < l.length; i += 2) ctx.lineTo(l[i], l[i + 1]);
        }
        ctx.stroke();
      }
      ctx.restore();
    }

    function desenharConfetes(ctx) {
      for (const c of confetes) {
        ctx.save();
        ctx.translate(c.x, c.y);
        ctx.rotate(c.rot);
        ctx.fillStyle = c.cor;
        ctx.fillRect(-c.w / 2, -c.h / 2, c.w, c.h * Math.abs(Math.cos(c.rot * 1.3)) + 1);
        ctx.restore();
      }
    }

    /* Os cartazes FIGHT! / NEVER GIVE UP! / FIGHT TILL THE END: um bate
       (entra grande e assenta, passando do ponto), o outro desliza. */
    function desenharFaixas(ctx) {
      for (const f of faixas) {
        if (!f.img) continue;
        const t = f.t - f.atraso;
        if (t < 0) continue;
        const altura = f.largura * (f.img.naturalHeight / f.img.naturalWidth);
        let escala = 1, dx = 0, alfa = 1;
        if (f.tipo === "bate") {
          const e = limitar(t / 0.24, 0, 1);
          escala = 2.1 - 1.1 * passarDoPonto(e, 2.4);
          alfa = Math.min(1, t / 0.08);
          if (e >= 0.5 && !f.tocou) { f.tocou = true; api.som("batida"); api.tremer(6); }
        } else {
          dx = (1 - passarDoPonto(limitar(t / 0.32, 0, 1), 1.6)) * 420;
          alfa = Math.min(1, t / 0.1);
          if (!f.tocou) { f.tocou = true; api.som("whoosh"); }
        }
        const resta = f.dur - t;
        if (resta < 0.3) alfa *= Math.max(0, resta / 0.3);
        const bate = 1 + 0.025 * Math.max(0, Math.sin(t * 6.8));
        ctx.save();
        ctx.globalAlpha = alfa;
        ctx.translate(f.x + dx, f.y);
        ctx.scale(escala * bate, escala * bate);
        ctx.drawImage(f.img, -f.largura / 2, -altura / 2, f.largura, altura);
        ctx.restore();
      }
    }

    /* O MOSTRADOR DE IMPACTO REDONDO (main.gd, _medidor_do_impacto):
       arco de 270° fechado embaixo, 40 gomos, o aro do original por fora.
       Na espera do soco ele é o ponteiro de força; depois do golpe ele
       vira o placar que conta a nota. */
    const direcoes = [];
    for (let g = 0; g < MEDIDOR_GOMOS; g++) {
      const f = (g + 0.5) / MEDIDOR_GOMOS;
      const a = MEDIDOR_INICIO + MEDIDOR_VOLTA * f;
      direcoes.push([Math.cos(a), Math.sin(a), f]);
    }

    function corDaZona(f) {
      return f >= ZONA_FORTE ? COR_FAIXA[2] : f >= ZONA_MEDIA ? COR_FAIXA[1] : COR_FAIXA[0];
    }

    function desenharMedidor(ctx, t) {
      const { x: cx, y: cy, r } = MEDIDOR;
      const armado = estado === "armado" || estado === "voo" || estado === "maisForte";
      const lendo = estado === "medindo";
      const fracaoNota = Math.sqrt(limitar(mostrado / SCORE_MAX, 0, 1));
      const fracao = armado || lendo ? (estado === "armado" ? forca : forcaTravada) : fracaoNota;
      let cor;
      if (armado || lendo) cor = corDaZona(fracao);
      else if (vereditoT >= 0) cor = COR_FAIXA[faixaDe(notaAtual)];
      else cor = misturar(AMBAR, COR_FAIXA[faixaDe(notaAtual)], limitar(tEstado / CONTAGEM_DURACAO, 0, 1) * 0.82);
      const naZonaVermelha = estado === "armado" && forca >= ZONA_FORTE;
      const pop = vereditoT >= 0 && vereditoT < MEDIDOR_POP_S ? Math.sin(Math.PI * vereditoT / MEDIDOR_POP_S) : 0;

      ctx.save();
      // o halo na cor, maior no tranco (e aceso na zona vermelha)
      const raioHalo = r + 34 + 14 * pop;
      const halo = ctx.createRadialGradient(cx, cy, r * 0.6, cx, cy, raioHalo);
      halo.addColorStop(0, cor);
      halo.addColorStop(1, "rgba(0,0,0,0)");
      ctx.globalAlpha = 0.16 + 0.2 * pop + (naZonaVermelha ? 0.22 : 0);
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(cx, cy, raioHalo, 0, Math.PI * 2); ctx.fill();
      // o vidro escuro com a luz da cor por dentro
      ctx.globalAlpha = 0.92;
      ctx.fillStyle = "#0b0616";
      ctx.beginPath(); ctx.arc(cx, cy, r + 8, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 0.08 + 0.12 * fracao;
      ctx.fillStyle = cor;
      ctx.beginPath(); ctx.arc(cx, cy, r - 22, 0, Math.PI * 2); ctx.fill();
      // o aro (a peça do original, tingida)
      if (img.aro) {
        ctx.globalAlpha = 0.65;
        const lado = 348 * (r / 158) * 1.02;
        ctx.drawImage(tingir(img.aro, cor), cx - lado / 2, cy - lado / 2, lado, lado);
      }
      ctx.restore();

      // OS GOMOS
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineWidth = 4.4;
      const varredura = (t * 1.4) % 1;
      for (let g = 0; g < MEDIDOR_GOMOS; g++) {
        const [dx, dy, f] = direcoes[g];
        let tinta, comprimento = 9, alfa;
        if (lendo) {
          const atras = (((varredura - f) % 1) + 1) % 1;
          if (atras < 0.22) { tinta = AMBAR; alfa = 0.95 - atras * 3.8; comprimento = 11; }
          else { tinta = "#2a1b43"; alfa = 1; }
        } else if (armado) {
          // na espera, cada gomo mostra a zona dele: dá para ver onde é o vermelho
          const zona = corDaZona(f);
          if (f <= fracao) {
            const ponta = limitar(1 - (fracao - f) * 9, 0, 1);
            tinta = misturar(zona, "#ffffff", 0.45 * ponta);
            alfa = 1;
            comprimento = 9 + 4 * ponta;
          } else { tinta = zona; alfa = f >= ZONA_FORTE ? 0.42 : 0.2; }
        } else if (f <= fracao) {
          const ponta = limitar(1 - (fracao - f) * 9, 0, 1);
          tinta = misturar(cor, "#ffffff", 0.45 * ponta);
          alfa = 1;
          comprimento = 9 + 4 * ponta;
        } else { tinta = "#2a1b43"; alfa = 1; }
        ctx.globalAlpha = alfa;
        ctx.strokeStyle = tinta;
        const base = r - 15;
        ctx.beginPath();
        ctx.moveTo(cx + dx * base, cy + dy * base);
        ctx.lineTo(cx + dx * (base + comprimento), cy + dy * (base + comprimento));
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      // o arco contínuo da força, com a ponta brilhando
      if (!lendo && fracao > 0.001) {
        const fim = MEDIDOR_INICIO + MEDIDOR_VOLTA * fracao;
        ctx.strokeStyle = cor;
        ctx.globalAlpha = 0.3;
        ctx.lineWidth = 8;
        ctx.beginPath(); ctx.arc(cx, cy, r + 1, MEDIDOR_INICIO, fim); ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(cx, cy, r + 1, MEDIDOR_INICIO, fim); ctx.stroke();
        const px = cx + Math.cos(fim) * (r + 1);
        const py = cy + Math.sin(fim) * (r + 1);
        ctx.fillStyle = cor;
        ctx.globalAlpha = 0.4;
        ctx.beginPath(); ctx.arc(px, py, 9, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 1;
        ctx.fillStyle = "#ffffff";
        ctx.beginPath(); ctx.arc(px, py, 4.6, 0, Math.PI * 2); ctx.fill();
      }
      // a onda que sai do anel no tranco final
      if (pop > 0) {
        ctx.globalAlpha = 0.55 * pop;
        ctx.strokeStyle = cor;
        ctx.lineWidth = 1.5 + 4 * pop;
        ctx.beginPath(); ctx.arc(cx, cy, r + 10 + 50 * (1 - pop * pop), 0, Math.PI * 2); ctx.stroke();
      }
      ctx.restore();

      // os arcos que giram enquanto o "sensor" lê
      if (lendo && img.giroFora && img.giroDentro) {
        const lado = 330 * (r / 158);
        const lado2 = 244 * (r / 158);
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(t * 3.4);
        ctx.drawImage(tingir(img.giroFora, AMBAR), -lado / 2, -lado / 2, lado, lado);
        ctx.rotate(-t * 3.4 * 1.7);
        ctx.globalAlpha = 0.5;
        ctx.drawImage(tingir(img.giroDentro, AMBAR), -lado2 / 2, -lado2 / 2, lado2, lado2);
        ctx.restore();
      }

      // O MIOLO: a luva chamando o soco, ou o número subindo
      let rotulo;
      if (armado) {
        const pulso = 0.62 + 0.38 * Math.sin(t * 4.4);
        const corLuva = naZonaVermelha ? COR_FAIXA[2] : AMBAR;
        if (img.luvaCorpo && img.luvaBrilho) {
          const lado = 64 + 6 * pulso + (naZonaVermelha ? 8 : 0);
          ctx.save();
          ctx.globalAlpha = estado === "armado" ? 0.55 + 0.45 * pulso : 0.4;
          ctx.drawImage(tingir(img.luvaCorpo, corLuva), cx - lado / 2, cy - 6 - lado / 2, lado, lado);
          ctx.drawImage(img.luvaBrilho, cx - lado / 2, cy - 6 - lado / 2, lado, lado);
          ctx.restore();
        }
        rotulo = naZonaVermelha ? "AGORA!" : "FORÇA";
      } else {
        let escala = 1;
        if (estado === "contando") escala = 0.55 + 0.45 * suavizar(tEstado / CONTAGEM_DURACAO);
        escala += 0.24 * pop;
        const texto = lendo ? "- - -" : String(mostrado);
        ctx.save();
        ctx.translate(cx, cy - 4);
        ctx.scale(escala, escala);
        api.texto(ctx, texto, 0, 0, {
          tamanho: texto.length <= 3 ? 50 : 42, cor: lendo ? AMBAR : "#ffffff", peso: 900, contorno: "#0e0624", sombra: cor,
        });
        ctx.restore();
        rotulo = lendo ? "LENDO SENSOR" : vereditoT >= 0 ? "PONTOS" : "CONTANDO";
      }
      api.texto(ctx, rotulo, cx, cy + r * 0.66, { tamanho: 11.5, cor: misturar(cor, "#ffffff", 0.25), peso: 800 });
    }

    function desenharChamada(ctx, t) {
      if (estado === "maisForte") {
        // "MAIS FORTE!" tremendo, e o porquê embaixo
        const treme = Math.sin(t * 60) * 4 * limitar(1 - tEstado / 0.5, 0, 1);
        api.texto(ctx, "MAIS FORTE!", 270 + treme, CHAMADA_Y, { tamanho: 38, cor: AMBAR, peso: 900, contorno: "#0e0624" });
        api.texto(ctx, "ESSE NÃO PONTUOU  •  BATA DE NOVO", 270, FRASE_Y, { tamanho: 14, cor: "#ffffff", peso: 800 });
        return;
      }
      if (estado === "veredito" || estado === "subindo" || estado === "fim") {
        // A FAIXA ESCURA DO VEREDITO: o nome do nível na cor dele, sobre
        // um fundo que dá contraste a qualquer cor
        const abre = limitar(vereditoT / 0.25, 0, 1);
        const cor = nivelAtual.cor;
        const topo = CHAMADA_Y - 28, base = FRASE_Y + 13;
        ctx.save();
        ctx.globalAlpha = abre;
        ctx.fillStyle = "rgba(12,6,21,.82)";
        ctx.beginPath();
        ctx.moveTo(0, topo + 9); ctx.lineTo(LARGURA, topo - 9); ctx.lineTo(LARGURA, base - 9); ctx.lineTo(0, base + 9);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = cor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, topo + 9); ctx.lineTo(LARGURA, topo - 9);
        ctx.moveTo(0, base + 9); ctx.lineTo(LARGURA, base - 9);
        ctx.stroke();
        const entra = passarDoPonto(limitar(vereditoT / 0.3, 0, 1), 2);
        ctx.translate(270, CHAMADA_Y);
        ctx.scale(0.6 + 0.4 * entra, 0.6 + 0.4 * entra);
        api.texto(ctx, nivelAtual.nome, 0, 0, { tamanho: 38, cor: cor === "#ffffff" ? "#fffbe6" : cor, peso: 900, contorno: "#0e0624", sombra: cor });
        ctx.restore();
        ctx.save();
        ctx.globalAlpha = limitar((vereditoT - 0.15) / 0.25, 0, 1);
        api.texto(ctx, fraseAtual, 270, FRASE_Y + 2, { tamanho: 15, cor: AMBAR, peso: 800 });
        ctx.restore();
        return;
      }
      if (estado === "armado" || estado === "voo") {
        const piscada = 0.78 + 0.22 * Math.sin(t * 4.4);
        ctx.save();
        ctx.globalAlpha = piscada;
        api.texto(ctx, CHAMADAS[Math.min(socos.length, CHAMADAS.length - 1)], 270, CHAMADA_Y, { tamanho: 36, cor: "#ffffff", peso: 900, contorno: "#0e0624" });
        ctx.restore();
        api.texto(ctx, ESPERA[(semente + socos.length) % ESPERA.length], 270, FRASE_Y, { tamanho: 15, cor: AMBAR, peso: 800 });
        return;
      }
      // medindo / contando: a pessoa olha para o número; aqui só o apoio
      api.texto(ctx, estado === "medindo" ? "LENDO O SOCO…" : "CONTANDO…", 270, CHAMADA_Y, { tamanho: 24, cor: "#d9d1ff", peso: 900 });
    }

    /* OS TRÊS SOCOS, LADO A LADO (main.gd, _draw_cartoes_dos_socos):
       vazio, à espera (borda âmbar pulsando) ou feito (anel na cor do
       nível). No fim, o que deu a nota da rodada ganha MELHOR. */
    function desenharCartoes(ctx, t) {
      const vao = 8;
      const x0 = 16;
      const largura = (LARGURA - x0 * 2 - vao * (SOCOS - 1)) / SOCOS;
      const h = CARTOES_ALTURA;
      const fimDaRodada = socos.length >= SOCOS;
      let melhorI = -1, melhorP = -1;
      for (let i = 0; i < socos.length; i++) if (socos[i] > melhorP) { melhorP = socos[i]; melhorI = i; }
      for (let i = 0; i < SOCOS; i++) {
        const x = x0 + i * (largura + vao);
        let y = CARTOES_Y;
        const feito = i < socos.length;
        const esperando = !feito && i === socos.length && (estado === "armado" || estado === "voo" || estado === "maisForte");
        const ehMelhor = fimDaRodada && feito && i === melhorI;
        const pontos = feito ? socos[i] : 0;
        const corNivel = feito ? COR_FAIXA[faixaDe(pontos)] : TINTA_LEVE;
        let cor = TINTA_LEVE;
        if (ehMelhor) cor = corNivel;
        else if (feito) cor = misturar(corNivel, "#d9d1ff", 0.35);
        else if (esperando) cor = AMBAR;
        // a chegada do cartão: sobe de baixo, passa do ponto e assenta
        const novo = feito && i === socos.length - 1 && estado === "veredito";
        let crescer = 0, clarao2 = 0;
        if (novo && vereditoT < 0.5) {
          const e = vereditoT / 0.5;
          y += (1 - passarDoPonto(e)) * 40;
          crescer = (1 - e) * 6;
          clarao2 = Math.pow(1 - limitar(vereditoT / 0.26, 0, 1), 2);
        }
        const pulso = esperando ? 0.62 + 0.38 * Math.sin(t * 4.4) : 1;
        const bx = x - crescer, by = y - crescer, bw = largura + crescer * 2, bh = h + crescer * 2;
        ctx.save();
        if (ehMelhor || esperando) {
          ctx.globalAlpha = (ehMelhor ? 0.3 : 0.2) * pulso;
          ctx.fillStyle = cor;
          retanguloRedondo(ctx, bx - 4, by - 4, bw + 8, bh + 8, bh / 2 + 4);
          ctx.fill();
        }
        ctx.globalAlpha = 0.88;
        ctx.fillStyle = "#0b0616";
        retanguloRedondo(ctx, bx, by, bw, bh, bh / 2);
        ctx.fill();
        if (clarao2 > 0) {
          ctx.globalAlpha = 0.4 * clarao2;
          ctx.fillStyle = "#ffffff";
          ctx.fill();
        }
        ctx.globalAlpha = (ehMelhor ? 0.95 : 0.65) * pulso;
        ctx.strokeStyle = cor;
        ctx.lineWidth = ehMelhor ? 2.6 : 1.6;
        ctx.stroke();
        ctx.globalAlpha = 1;
        // o anel à esquerda: enche até a força do soco, na cor do nível
        const ax = bx + bh / 2, ay = by + bh / 2, ar = bh / 2 - 9;
        ctx.lineWidth = 5;
        ctx.strokeStyle = "#2a1b43";
        ctx.beginPath(); ctx.arc(ax, ay, ar, 0, Math.PI * 2); ctx.stroke();
        const esq = ax + ar + 12;
        if (feito) {
          let subida = 1;
          if (novo && vereditoT < 0.6) subida = 1 - Math.pow(1 - vereditoT / 0.6, 3);
          const fracao = Math.sqrt(pontos / SCORE_MAX) * subida;
          ctx.strokeStyle = corNivel;
          ctx.beginPath(); ctx.arc(ax, ay, ar, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(fracao, 0.001)); ctx.stroke();
          api.texto(ctx, `SOCO ${i + 1}`, esq, by + 15, { tamanho: 10.5, cor: misturar(cor, "#ffffff", 0.3), alinhar: "left", peso: 800 });
          const valor = Math.round(pontos * subida).toLocaleString("pt-BR");
          api.texto(ctx, valor, esq, by + 34, { tamanho: 19, cor: ehMelhor ? misturar(corNivel, "#ffffff", 0.4) : "#ffffff", alinhar: "left", peso: 900 });
        } else if (esperando) {
          if (img.cartaoGiro) {
            ctx.save();
            ctx.translate(ax, ay);
            ctx.rotate(t * 3);
            ctx.globalAlpha = pulso;
            const lado = (ar + 3) * 2 * (136 / 120);
            ctx.drawImage(tingir(img.cartaoGiro, AMBAR), -lado / 2, -lado / 2, lado, lado);
            ctx.restore();
          }
          if (img.luvaCorpo) {
            const lado = 22 + 2 * pulso;
            ctx.save();
            ctx.globalAlpha = pulso;
            ctx.drawImage(tingir(img.luvaCorpo, AMBAR), ax - lado / 2, ay - lado / 2, lado, lado);
            ctx.restore();
          }
          api.texto(ctx, `SOCO ${i + 1}`, esq, by + 15, { tamanho: 10.5, cor: misturar(AMBAR, "#ffffff", 0.3), alinhar: "left", peso: 800 });
          ctx.save();
          ctx.globalAlpha = pulso;
          api.texto(ctx, "SOQUE!", esq, by + 34, { tamanho: 19, cor: AMBAR, alinhar: "left", peso: 900 });
          ctx.restore();
        } else {
          api.texto(ctx, "–", ax, ay - 1, { tamanho: 18, cor: "rgba(161,151,214,.55)", peso: 900 });
          api.texto(ctx, `SOCO ${i + 1}`, esq, by + 15, { tamanho: 10.5, cor: "rgba(161,151,214,.8)", alinhar: "left", peso: 800 });
          api.texto(ctx, "ESPERA", esq, by + 34, { tamanho: 13, cor: "rgba(161,151,214,.6)", alinhar: "left", peso: 800 });
        }
        if (ehMelhor) {
          ctx.fillStyle = AMBAR;
          retanguloRedondo(ctx, bx + bw - 64, by - 9, 58, 17, 8.5);
          ctx.fill();
          api.texto(ctx, "★ MELHOR", bx + bw - 35, by - 0.5, { tamanho: 9.5, cor: "#100818", peso: 900 });
        }
        ctx.restore();
      }
    }

    /* AS TARJAS ZEBRADAS nas bordas, como as de uma transmissão, com o fio
       de luz na cor do golpe por dentro (quadro.gd, tarjas). Ficam sempre
       por cima, nítidas, e nunca são cobertas pelo clarão. */
    function desenharTarjas(ctx) {
      const brilho = brilhoGolpe;
      const corGolpe = estado === "armado" ? AMBAR : nivelAtual.cor;
      // a cor arredondada em poucos degraus: cada tom novo é uma tinta guardada
      const degrau = Math.round(brilho * 4) / 4;
      const amarelo = degrau > 0 ? misturar(OURO_TARJA, misturar(corGolpe, "#ffffff", 0.35), degrau * 0.45) : OURO_TARJA;
      const zebra = img.zebra ? tingir(img.zebra, amarelo, true) : null;
      if (zebra) {
        ctx.drawImage(zebra, 0, 0, zebra.width, zebra.height, 0, 0, LARGURA, TARJA);
        ctx.drawImage(zebra, 0, 0, zebra.width, zebra.height, 0, ALTURA - TARJA, LARGURA, TARJA);
        for (const lado of [TARJA, LARGURA]) {
          ctx.save();
          ctx.translate(lado, 0);
          ctx.rotate(Math.PI / 2);
          ctx.drawImage(zebra, 0, 0, zebra.width, zebra.height, 0, 0, ALTURA, TARJA);
          ctx.restore();
        }
      }
      const g = 1.5 + brilho * 2;
      ctx.save();
      ctx.globalAlpha = 0.55 + brilho * 0.45;
      ctx.strokeStyle = corGolpe;
      ctx.lineWidth = g;
      ctx.strokeRect(TARJA + g / 2, TARJA + g / 2, LARGURA - TARJA * 2 - g, ALTURA - TARJA * 2 - g);
      ctx.restore();
    }

    return {
      iniciar,
      atualizar,
      desenhar,
      apertar() { socar(); },
      tecla(codigo, apertada) {
        if (apertada && (codigo === "Space" || codigo === "Enter" || codigo === "ArrowUp" || codigo === "KeyF")) socar();
      },
      destruir() {
        ondas = []; raios = []; confetes = []; faixas = [];
      },
    };
  },
};
