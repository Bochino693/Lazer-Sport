/* ======================================================================
   SUPER BOXING — a máquina de força de soco, em miniatura.

   Na máquina de verdade o saco desce, a pessoa bate, o sensor de feixe
   mede a velocidade do golpe e o jogo transforma isso numa nota de 0 a
   9999, com oito níveis de espetáculo (IMPACTO LEVE ... SOCO PERFEITO).
   E na tela, quem leva o soco é um BOXEADOR 3D num ringue 3D: ele recua
   na medida do golpe, desdenha do soco fraco, vai para as cordas, cai na
   lona — e quem demora para bater leva um soco dele na câmera.

   Aqui não há sensor: quem faz o papel do braço é o MEDIDOR REDONDO do
   jogo original (o aro com os 40 gomos). Ele enche e esvazia sem parar,
   e o toque na hora certa vira a força do soco — a zona vermelha, no fim
   do arco, é onde mora o NOCAUTE.

   O que veio do jogo original (super-boxing-android7):
     - A ARENA 3D INTEIRA (scripts/arena/arena3d.gd): ringue, cordas que
       esticam, postes, treliça com refletores e fachos, torcida animada,
       telão de LED, poeira na luz, a câmera de transmissão (enquadramento,
       arco lento, soco de câmera, nocaute, jogador no chão) e as luzes;
     - O BOXEADOR (scripts/arena/lutador.gd + lutador_boxeador.gd e o
       assets/lutador3d/boxeador_tvbox.glb): a coreografia em código,
       quadro a quadro — guarda, combos no ar, reações pela força (nem
       sentiu, cordas, cambaleio, nocaute e levantar), o soco na câmera, as
       festas do fim (zonzo, comemoração, deboche) e as expressões do
       rosto; pés plantados, IK de dois ossos e molas;
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
     - o painel de luta por cima do 3D (scripts/arena/quadro.gd): as duas
       vidas, o round, o mostrador do impacto à esquerda, os cartões dos
       socos e os textos no rodapé escuro, nas posições da tela da máquina;
     - o fim da rodada (main.gd, _fechar_desfecho): batido forte, ele fica
       zonzo; fraco, ele vem para cima, nocauteia a câmera ("K.O.") e
       comemora por cima de quem está no chão;
     - as frases do locutor por nível, as provocações da espera, o
       "MAIS FORTE! / ESSE NÃO PONTUOU" (scripts/arena/frases.gd);
     - FIGHT!, NEVER GIVE UP! e FIGHT TILL THE END (assets/tema).

   SEM WEBGL (ou se o 3D não carregar), a partida continua inteira: no
   lugar da arena entra o ginásio 2D com o saco de pancada.
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
/* Quando o lutador vai à lona, a frase é uma só e é grande. */
const FRASES_NOCAUTE = ["NOCAUTE!", "ELE FOI À LONA!", "CONTA ATÉ DEZ!"];
/* O soco bom que não derruba manda ele para as cordas (main.gd). */
const FRASES_CORDAS = ["FOI PARAR NAS CORDAS!", "AS CORDAS SEGURARAM ELE!", "SENTIU! FOI PRAS CORDAS!"];
/* Quando quem bateu perdeu: o lutador tira onda e a frase acompanha. */
const FRASES_DERROTA = [
  "ELE ESTÁ RINDO DE VOCÊ!", "A TORCIDA VAIOU • REVANCHE?", "FOI SÓ ISSO? ELE QUER MAIS",
  "ELE DANÇOU NA SUA FRENTE", "VAIA GERAL • BATA MAIS FORTE",
];
/* O estado do adversário, lido do medidor de dano (o texto da vida dele). */
const DANOS = [[0.001, "INTEIRO"], [0.25, "MARCADO"], [0.55, "ABALADO"], [0.85, "CAMBALEANDO"], [1.01, "POR UM FIO"]];
function estadoDoDano(dano) {
  for (const [ate, texto] of DANOS) if (dano <= ate) return texto;
  return DANOS[DANOS.length - 1][1];
}

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
const VOO_DA_LUVA = 0.13;            // da guarda até o rosto dele
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
/* QUEM DEMORA LEVA (main.gd): o lutador vem e soca a câmera em 4–5,5 s,
   depois a cada 5–7 s; depois de um soco fraco ele vem confiante (mais
   cedo); depois de um que doeu, mais tarde. Cada soco dele tira um quarto
   da vida de quem joga — zerou, é nocaute. */
const SOCO_NA_TELA_PRIMEIRO = [4.0, 5.5];
const SOCO_NA_TELA_DEPOIS = [5.0, 7.0];
const SOCO_NA_TELA_CONFIANTE = [2.3, 3.2];
const DANO_DO_SOCO_NA_TELA = 0.25;
/* O NOCAUTE NO JOGADOR: o "K.O." na tela, a paciência com a reação dele e
   a festa à vista antes do fim. */
const KO_DURACAO = 3.2;
const KO_PACIENCIA = 3.0;
const FESTA_DEPOIS_DO_KO = 1.6;
/* Quanto a arena fica no ar depois do último veredito: a festa de quem
   ganhou e, sobretudo, o deboche de quem perdeu precisam de tempo. */
const ESPERA_DO_FIM_FESTA = 3.8;
const ESPERA_DO_FIM_DEBOCHE = 7.6;
/* A nota que decide a luta (main.gd, _fechar_desfecho). */
const NOTA_DA_VITORIA = 6500;
const NOTA_DO_EMPATE = 4000;

const FESTA = ["#ff26a8", "#ffd014", "#fff9ef", "#46dcff", "#8a3cff", "#ff6a2a"];
const AMBAR = "#ffd014";
const OURO_TARJA = "#ffdc27";
const CREME = "#f6fbff";
const TINTA_LEVE = "#a197d6";
const VERDE = "#32f2a0";
const VERMELHO = "#ff2a6d";

/* ONDE AS COISAS FICAM NA TELA: a metade das medidas da tela de luta da
   máquina (1080 x 1920), que é a mesma proporção desta. */
/* O ponto do soco dos efeitos de tela (main.gd, ALVO_DO_SOCO 540, 900). */
const ALVO = { x: 270, y: 450 };
/* O mostrador do impacto, redondo, à esquerda sobre a torcida (main.gd,
   MEDIDOR_CENTRO 196, 640 e raio 158): o meio da tela é do lutador. */
const MEDIDOR = { x: 98, y: 320, r: 79 };
const MEDIDOR_INICIO = Math.PI * 0.75;
const MEDIDOR_VOLTA = Math.PI * 1.5;
const MEDIDOR_GOMOS = 40;
/* Os textos do rodapé (a chamada e a frase) e a faixa escura do veredito
   (VEREDITO_TOPO 1668, VEREDITO_BASE 1830). */
const CHAMADA_Y = 853;
const FRASE_Y = 893;
const VEREDITO_TOPO = 834;
const VEREDITO_BASE = 915;
/* Os cartões dos socos, sobre a frente do ringue (ArenaQuadro.PAINEIS_Y). */
const CARTOES_Y = 751;
const CARTOES_ALTURA = 50;
const TARJA = 8;
/* O degradê escuro que sobe do pé da tela para os textos (RODAPE_ESCURO). */
const RODAPE_ESCURO = 210;
/* O painel de luta no alto: a faixa escura e as duas vidas, a do JOGADOR
   à esquerda e a do ADVERSÁRIO à direita, espelhada (ArenaQuadro). */
const FAIXA_DO_ALTO = 128;
const VIDA_JOGADOR = { x: 20, y: 89, w: 231, h: 22 };
const VIDA_ADVERSARIO = { x: 289, y: 89, w: 231, h: 22 };
const INCLINA = 13;
const OURO = "#ffdc27";
const OURO_ESC = "#8a6a10";
const ESCURO = "#110a1e";
/* O logo do jogo no alto, entre "VOCÊ" e "ADVERSÁRIO", e a marca da casa
   à direita, logo abaixo da vida do adversário. */
const LOGO_DO_ALTO = { x: 270, y: 44, largura: 145 };
const MARCA = { x: 520, y: 136, altura: 100 };
/* O ginásio 2D de reserva (sem WebGL): onde a corrente do saco prende
   na treliça e a distância até o alvo pintado nele. */
const PIVO = { x: 270, y: -6 };
const SACO_ALVO = 336;
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

/* Uma cor hex com transparência, para o canvas. */
function comAlfa(hex, a) {
  const p = parseInt(hex.slice(1), 16);
  return `rgba(${(p >> 16) & 255},${(p >> 8) & 255},${p & 255},${limitar(a, 0, 1).toFixed(3)})`;
}

/* Color.lightened / darkened do Godot. */
function clarear(hex, quanto) { return misturar(hex, "#ffffff", quanto); }
function escurecer(hex, quanto) { return misturar(hex, "#000000", quanto); }

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
   O MUNDO 3D — o ringue e o boxeador do jogo de verdade.

   Na máquina, a arena é um mundo 3D (scripts/arena/arena3d.gd) com um
   boxeador de esqueleto animado EM CÓDIGO, quadro a quadro
   (scripts/arena/lutador.gd + lutador_boxeador.gd). Aqui é o mesmo mundo,
   no three.js: as mesmas medidas, a mesma câmera, as mesmas luzes, o mesmo
   modelo (assets/lutador3d/boxeador_tvbox.glb) e a mesma coreografia —
   cada constante abaixo tem o nome e o valor da de lá.

   O ESPAÇO DE COR É O DA TV BOX. O jogo roda no OpenGL ES 2.0 do Godot 3,
   que faz a luz em cima das cores como elas são (sem passar por linear):
   aqui também. As texturas entram sem conversão (`NoColorSpace`), as cores
   são dadas "cruas" (`cru`) e a imagem sai sem conversão
   (`LinearSRGBColorSpace`). A luz do three.js divide o difuso por π e a do
   Godot não: as energias de lá entram multiplicadas por π (`ENERGIA`).

   O three.js chega devagar (import dinâmico): até ele chegar, `THREE` é
   nulo e nada daqui é chamado.
   ====================================================================== */

let THREE = null;

const TAU = Math.PI * 2;
/* Uma energia de luz do Godot em intensidade do three.js (ver acima). */
const ENERGIA = Math.PI;

function lerp(a, b, t) { return a + (b - a) * t; }
function fposmod(a, b) { const r = a % b; return r < 0 ? r + b : r; }
function moverAte(a, b, passo) { return Math.abs(b - a) <= passo ? b : a + Math.sign(b - a) * passo; }
/* O `ease` do Godot: c > 1 sai devagar, 0 < c < 1 chega devagar, c < 0 os dois. */
function ease(x, c) {
  const p = limitar(x, 0, 1);
  if (c > 0) return c < 1 ? 1 - Math.pow(1 - p, 1 / c) : Math.pow(p, c);
  if (c < 0) return p < 0.5 ? Math.pow(p * 2, -c) * 0.5 : (1 - Math.pow(1 - (p - 0.5) * 2, -c)) * 0.5 + 0.5;
  return 0;
}
/* Uma cor do jogo (hex) do jeito que ela é, sem conversão (ver acima). */
function cru(hex) { return new THREE.Color().setHex(hex, THREE.LinearSRGBColorSpace); }

/* ----------------------------------------------------------------------
   A BASE (matriz 3x3 de giro), como o `Basis` do Godot 3.

   O boxeador é todo escrito com ela: `Basis(euler)` é Y·X·Z (o `set_euler`
   do Godot 3), `Basis(eixo, ângulo)` é o giro de Rodrigues e
   `Basis(x, y, z)` monta pelas colunas. Guardada em linhas (m[l*3+c]) e
   reaproveitada: nenhum quadro cria matriz nova.
   ---------------------------------------------------------------------- */
class Base3 {
  constructor() { this.m = [1, 0, 0, 0, 1, 0, 0, 0, 1]; }

  identidade() {
    const m = this.m;
    m[0] = 1; m[1] = 0; m[2] = 0; m[3] = 0; m[4] = 1; m[5] = 0; m[6] = 0; m[7] = 0; m[8] = 1;
    return this;
  }

  copiar(b) { const m = this.m, o = b.m; for (let i = 0; i < 9; i++) m[i] = o[i]; return this; }

  /* Basis(Vector3(x, y, z)) do Godot 3: Y · X · Z. */
  euler(x, y, z) {
    const cx = Math.cos(x), sx = Math.sin(x), cy = Math.cos(y), sy = Math.sin(y), cz = Math.cos(z), sz = Math.sin(z);
    const m = this.m;
    m[0] = cy * cz + sy * sx * sz; m[1] = -cy * sz + sy * sx * cz; m[2] = sy * cx;
    m[3] = cx * sz; m[4] = cx * cz; m[5] = -sx;
    m[6] = -sy * cz + cy * sx * sz; m[7] = sy * sz + cy * sx * cz; m[8] = cy * cx;
    return this;
  }

  eulerV(v) { return this.euler(v.x, v.y, v.z); }

  /* Basis(eixo, ângulo), com o eixo já normalizado. */
  eixo(ax, ay, az, ang) {
    const m = this.m;
    const c = Math.cos(ang), s = Math.sin(ang), t = 1 - c;
    m[0] = ax * ax + c * (1 - ax * ax); m[4] = ay * ay + c * (1 - ay * ay); m[8] = az * az + c * (1 - az * az);
    m[1] = ax * ay * t - az * s; m[3] = ax * ay * t + az * s;
    m[2] = ax * az * t + ay * s; m[6] = ax * az * t - ay * s;
    m[5] = ay * az * t - ax * s; m[7] = ay * az * t + ax * s;
    return this;
  }

  colunas(x, y, z) {
    const m = this.m;
    m[0] = x.x; m[3] = x.y; m[6] = x.z;
    m[1] = y.x; m[4] = y.y; m[7] = y.z;
    m[2] = z.x; m[5] = z.y; m[8] = z.z;
    return this;
  }

  /* this = a · b (a e b podem ser a própria base). */
  multiplicar(a, b) {
    const A = a.m, B = b.m, m = this.m;
    const r0 = A[0] * B[0] + A[1] * B[3] + A[2] * B[6];
    const r1 = A[0] * B[1] + A[1] * B[4] + A[2] * B[7];
    const r2 = A[0] * B[2] + A[1] * B[5] + A[2] * B[8];
    const r3 = A[3] * B[0] + A[4] * B[3] + A[5] * B[6];
    const r4 = A[3] * B[1] + A[4] * B[4] + A[5] * B[7];
    const r5 = A[3] * B[2] + A[4] * B[5] + A[5] * B[8];
    const r6 = A[6] * B[0] + A[7] * B[3] + A[8] * B[6];
    const r7 = A[6] * B[1] + A[7] * B[4] + A[8] * B[7];
    const r8 = A[6] * B[2] + A[7] * B[5] + A[8] * B[8];
    m[0] = r0; m[1] = r1; m[2] = r2; m[3] = r3; m[4] = r4; m[5] = r5; m[6] = r6; m[7] = r7; m[8] = r8;
    return this;
  }

  /* this = aᵀ · b — o "a.inverse() * b" de uma base de giro. */
  transpostaVezes(a, b) {
    const A = a.m, B = b.m, m = this.m;
    const r0 = A[0] * B[0] + A[3] * B[3] + A[6] * B[6];
    const r1 = A[0] * B[1] + A[3] * B[4] + A[6] * B[7];
    const r2 = A[0] * B[2] + A[3] * B[5] + A[6] * B[8];
    const r3 = A[1] * B[0] + A[4] * B[3] + A[7] * B[6];
    const r4 = A[1] * B[1] + A[4] * B[4] + A[7] * B[7];
    const r5 = A[1] * B[2] + A[4] * B[5] + A[7] * B[8];
    const r6 = A[2] * B[0] + A[5] * B[3] + A[8] * B[6];
    const r7 = A[2] * B[1] + A[5] * B[4] + A[8] * B[7];
    const r8 = A[2] * B[2] + A[5] * B[5] + A[8] * B[8];
    m[0] = r0; m[1] = r1; m[2] = r2; m[3] = r3; m[4] = r4; m[5] = r5; m[6] = r6; m[7] = r7; m[8] = r8;
    return this;
  }

  transpor() {
    const m = this.m;
    let t = m[1]; m[1] = m[3]; m[3] = t;
    t = m[2]; m[2] = m[6]; m[6] = t;
    t = m[5]; m[5] = m[7]; m[7] = t;
    return this;
  }

  /* out = this · v (out pode ser v). */
  aplicar(v, out) {
    const m = this.m, x = v.x, y = v.y, z = v.z;
    out.x = m[0] * x + m[1] * y + m[2] * z;
    out.y = m[3] * x + m[4] * y + m[5] * z;
    out.z = m[6] * x + m[7] * y + m[8] * z;
    return out;
  }

  /* out = thisᵀ · v: o caminho inverso de uma base de giro. */
  aplicarInversa(v, out) {
    const m = this.m, x = v.x, y = v.y, z = v.z;
    out.x = m[0] * x + m[3] * y + m[6] * z;
    out.y = m[1] * x + m[4] * y + m[7] * z;
    out.z = m[2] * x + m[5] * y + m[8] * z;
    return out;
  }

  /* O giro como quaternion (o `get_rotation_quat` de uma base de giro). */
  quaternion(q) {
    const m = this.m;
    const m11 = m[0], m12 = m[1], m13 = m[2], m21 = m[3], m22 = m[4], m23 = m[5], m31 = m[6], m32 = m[7], m33 = m[8];
    const traco = m11 + m22 + m33;
    let s;
    if (traco > 0) {
      s = 0.5 / Math.sqrt(traco + 1);
      q.set((m32 - m23) * s, (m13 - m31) * s, (m21 - m12) * s, 0.25 / s);
    } else if (m11 > m22 && m11 > m33) {
      s = 2 * Math.sqrt(1 + m11 - m22 - m33);
      q.set(0.25 * s, (m12 + m21) / s, (m13 + m31) / s, (m32 - m23) / s);
    } else if (m22 > m33) {
      s = 2 * Math.sqrt(1 + m22 - m11 - m33);
      q.set((m12 + m21) / s, 0.25 * s, (m23 + m32) / s, (m13 - m31) / s);
    } else {
      s = 2 * Math.sqrt(1 + m33 - m11 - m22);
      q.set((m13 + m31) / s, (m23 + m32) / s, 0.25 * s, (m21 - m12) / s);
    }
    return q.normalize();
  }
}

/* ======================================================================
   O ADVERSÁRIO — a lógica (lutador.gd) e o corpo (lutador_boxeador.gd).

   A ANIMAÇÃO NÃO É GRAVADA, como lá. Cada quadro:
     1. a COREOGRAFIA diz onde cada coisa quer estar (bacia, tronco,
        cabeça, as duas luvas: guarda, jab, direto, gancho, cruzado de
        baixo, festa, deboche, soco na câmera);
     2. OS PÉS SÃO PLANTADOS e só saem do chão num passo de verdade;
     3. IK DE DOIS OSSOS nas pernas e nos braços;
     4. MOLAS para o que é reação (cabeça, tronco, guarda, joelhos).
   ====================================================================== */

/* lutador.gd */
const ALTURA_DA_FIGURA = 1.80;
const DANO_POR_GOLPE = 0.62;
const DANO_MINIMO = 0.02;
const TEMPO_NA_LONA = 1.10;
const TEMPO_LEVANTAR = 2.0;
const PAPEIS = [
  "idle", "guard", "taunt_weak", "hit_light", "hit_medium", "hit_heavy",
  "stagger", "knockout", "get_up", "celebra", "deboche", "tonto", "soco_tela", "cordas",
];
const PAPEIS_CONTINUOS = ["idle", "guard"];
/* As festas de fim de rodada: duram até a rodada acabar. */
const PAPEIS_DE_FESTA = ["celebra", "deboche", "tonto"];
const DURACAO = { taunt_weak: 1.20, stagger: 1.30, hit_heavy: 0.95, hit_medium: 0.70, hit_light: 0.46, cordas: 2.0 };
/* Abaixo disto o adversário desdenha; acima, a força escolhe a reação. */
const LIMITE_DO_DESDEM = 2500;

function reacaoParaForca(forca) {
  const f = limitar(forca, 0, 1);
  if (f >= 0.82) return "stagger";
  if (f >= 0.62) return "hit_heavy";
  if (f >= 0.38) return "hit_medium";
  if (f >= 0.18) return "hit_light";
  return "taunt_weak";
}

/* O SOCO BOM QUE NÃO DERRUBA manda o adversário para as cordas. */
function reacaoParaPontos(pontos, forca) {
  if (pontos >= 0 && pontos < LIMITE_DO_DESDEM) return "taunt_weak";
  const reacao = reacaoParaForca(forca);
  if (reacao === "hit_medium" || reacao === "hit_heavy") return "cordas";
  return reacao === "taunt_weak" ? "hit_light" : reacao;
}

/* lutador_boxeador.gd — base de luta em metros do modelo: pé esquerdo à
   frente (guarda ortodoxa), direito atrás. */
const PE_FRENTE = [0.15, 0.15];
const PE_TRAS = [-0.17, -0.17];
const GIRO_DA_BASE = -0.34;
const LIMIAR_DO_PASSO = 0.055;
const TEMPO_DO_PASSO = 0.22;
const ALTURA_DO_PASSO = 0.055;
const CALCANHAR_MAX = 0.60;
const QUEDA_ANGULO = 1.50;
const RAIO_DA_LUVA = 0.075;
const RAIO_DA_BACIA = 0.10;
const RAIO_DAS_COSTAS = 0.11;
const RAIO_DA_CABECA = 0.10;
const COLUNA = ["Spine", "Spine1", "Spine2"];
const COLUNA_PESO = [0.3, 0.35, 0.35];
/* A coluna em onda: a lombar acompanha quase na hora, o peito por último. */
const VERTEBRA_FREQ = [24.0, 17.0, 13.0];
const VERTEBRA_AMORTECE = [0.95, 0.72, 0.62];
const VERTEBRA_RESPIRA = [-0.3, 0.4, 1.0];
const GOLPES_DELE = {
  jab: { dur: 0.30, pico: 0.36 },
  direto: { dur: 0.40, pico: 0.40 },
  gancho: { dur: 0.46, pico: 0.42 },
  upper: { dur: 0.46, pico: 0.44 },
};
const COMBOS = [
  [["jab", 0]],
  [["jab", 0], ["jab", 0], ["direto", 1]],
  [["jab", 0], ["direto", 1]],
  [["jab", 0], ["direto", 1], ["gancho", 0]],
  [["direto", 1], ["gancho", 0], ["direto", 1]],
  [["jab", 0], ["upper", 1], ["gancho", 0]],
  [["gancho", 0], ["direto", 1]],
  [["jab", 0], ["jab", 0]],
];
const MESCLA_EXPR = 7.0;
const EXPRESSOES = ["deboche", "dor", "grito", "apagado"];
/* Até onde, a partir do centro, a lona está livre das cordas (m). */
const RINGUE_LIVRE = 1.40;
const CORDAS_Z = 1.22;
/* O corpo anda em fatias de até 1/20 s, 40% mais rápido que o relógio
   (o boxeador parecia em câmera lenta na tela da máquina). */
const SUBPASSO = 1 / 20;
const VELOCIDADE = 1.4;
const PASSO_MAXIMO = 0.25;
/* O levantar em quatro tempos: deitado → senta → encolhe → agacha → de pé. */
const LEVANTAR_TEMPOS = [0.0, 0.24, 0.50, 0.76, 1.0];
const LEVANTAR_TOMBO = [0.0, -0.30, 0.22, 0.52, 0.0];
/* As texturas por material: [pintura, relevo] (o .glb não aponta para elas). */
const TEXTURAS_DO_CORPO = {
  Pele: ["pele", "relevo"],
  Roupa: ["calcao", null],
  Cinturao: ["cinturao", null],
  Placa: ["placa", null],
};

function ladoS(k) { return k === 0 ? 1 : -1; }

/* Os nomes dos ossos que a pose comanda (o resto segue o pai). */
const OSSOS_DO_LADO = {
  Shoulder: ["LeftShoulder", "RightShoulder"],
  Arm: ["LeftArm", "RightArm"],
  ForeArm: ["LeftForeArm", "RightForeArm"],
  Hand: ["LeftHand", "RightHand"],
  UpLeg: ["LeftUpLeg", "RightUpLeg"],
  Leg: ["LeftLeg", "RightLeg"],
  Foot: ["LeftFoot", "RightFoot"],
  ToeBase: ["LeftToeBase", "RightToeBase"],
  Toe_End: ["LeftToe_End", "RightToe_End"],
};

function filhoDoOsso(osso) {
  if (osso.endsWith("ForeArm")) return osso.replace("ForeArm", "Hand");
  if (osso.endsWith("Arm")) return osso.replace("Arm", "ForeArm");
  if (osso.endsWith("Hand")) return osso + "Middle1";
  if (osso.endsWith("UpLeg")) return osso.replace("UpLeg", "Leg");
  if (osso.endsWith("Leg")) return osso.replace("Leg", "Foot");
  if (osso.endsWith("Foot")) return osso.replace("Foot", "ToeBase");
  if (osso.endsWith("ToeBase")) return osso.replace("ToeBase", "Toe_End");
  return osso;
}

/* Rascunhos das contas: reaproveitados, nada nasce a cada quadro. */
let RASCUNHO = null;
function rascunho() {
  if (!RASCUNHO) {
    const V = () => new THREE.Vector3();
    RASCUNHO = {
      x: V(), y: V(), z: V(), b1: new Base3(), b2: new Base3(), eixo: V(),
      ikV: V(), ikDir: V(), ikDobra: V(),
    };
  }
  return RASCUNHO;
}

/* Basis(x, y, x × y) com y ortogonalizado: o "referencial" de um osso. */
function ortonormal(d, s, out) {
  const r = rascunho();
  const x = r.x.copy(d).normalize();
  const y = r.y.copy(s).addScaledVector(x, -s.dot(x));
  if (y.length() < 0.0001) {
    if (Math.abs(x.x) < 0.9) y.set(1, 0, 0); else y.set(0, 1, 0);
    y.crossVectors(x, y);
  }
  y.normalize();
  const z = r.z.crossVectors(x, y);
  return out.colunas(x, y, z);
}

/* IK de dois ossos: escreve a junta, a ponta e a direção da dobra. */
function ik(raiz, alvo, l1, l2, polo, junta, ponta, dobra) {
  const r = rascunho();
  const v = r.ikV.subVectors(alvo, raiz);
  const tam = v.length();
  const d = limitar(tam, Math.abs(l1 - l2) + 0.001, (l1 + l2) * 0.9995);
  const dir = r.ikDir;
  if (tam > 0.0001) dir.copy(v).divideScalar(tam); else dir.set(0, -1, 0);
  ponta.copy(raiz).addScaledVector(dir, d);
  const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(l1 * l1 - a * a, 0));
  dobra.copy(polo).addScaledVector(dir, -polo.dot(dir));
  if (dobra.length() < 0.0001) dobra.crossVectors(dir, r.eixo.set(1, 0, 0));
  dobra.normalize();
  junta.copy(raiz).addScaledVector(dir, a).addScaledVector(dobra, h);
}

/* O `slerp3` do jogo (Compat.slerp3): gira `de` em direção a `para`. */
function slerp3(de, para, peso, out) {
  const r = rascunho();
  const eixo = r.eixo.crossVectors(de, para);
  if (eixo.lengthSq() < 0.0000001) return out.copy(de).lerp(para, peso);
  const angulo = Math.atan2(eixo.length(), de.dot(para));
  eixo.normalize();
  return out.copy(de).applyAxisAngle(eixo, angulo * peso);
}

class Boxeador {
  /* `cena` é o gltf.scene do boxeador; `texturas` as pinturas já prontas. */
  constructor(cena, texturas) {
    const V = () => new THREE.Vector3();
    const V2 = () => new THREE.Vector2();
    this.no = new THREE.Group();          // o Lutador3D (o nó na arena)
    this.no.name = "Lutador";
    this.modelo = cena;
    this.no.add(cena);
    this.pronto = false;

    /* ---- lutador.gd */
    this.relogio = 0;
    this.papel = "";
    this.tempoNoPapel = 0;
    this.tempoReacao = 0;
    this.recuo = 0;
    this.forcaDoRecuo = 0;
    this.lado = 1;
    this.tempoNaLona = 0;
    this.levantando = false;
    this.caindo = false;
    this.clarao = 0;
    this.queda = 0;
    this.dano = 0;
    this.emGuarda = false;
    this.ficaNoChao = false;
    this.vaiComemorar = false;
    this.festa = "celebra";
    this.comemoraDepoisDoSoco = false;
    this.pontoDaCamera = new THREE.Vector3(0, 1.4, 3.0);

    /* ---- o corpo */
    this.bacia = V(); this.baciaRot = V(); this.tronco = V(); this.cabeca = V();
    this.mao = [V(), V()]; this.maoDir = [V(), V()]; this.polegar = [V(), V()]; this.cotovelo = [V(), V()];
    this.ombro = [V2(), V2()];
    this.aBacia = V(); this.aBaciaRot = V(); this.aTronco = V(); this.aCabeca = V();
    this.aMao = [V(), V()]; this.aMaoDir = [V(), V()]; this.aPolegar = [V(), V()]; this.aCotovelo = [V(), V()];
    this.aOmbro = [V2(), V2()];
    this.aCalcanhar = [0, 0];
    this.aExpr = { deboche: 0, dor: 0, grito: 0, apagado: 0 };
    this.rapidez = 18;
    this.dt = 1 / 60;
    this.centro = V2(); this.centroAlvo = V2(); this.centroVel = V2();
    this.pe = [V(), V()]; this.peGiro = [0, 0]; this.passoT = [-1, -1];
    this.passoDe = [V(), V()]; this.passoPara = [V(), V()];
    this.passoGiroDe = [0, 0]; this.passoGiroPara = [0, 0];
    this.calcanhar = [0, 0];
    this.vertebra = [V(), V(), V()]; this.vertebraV = [V(), V(), V()];
    this.respiro = 0;
    this.molaCab = V(); this.molaCabV = V(); this.molaTronco = V(); this.molaTroncoV = V();
    this.guardaAberta = 0; this.guardaAbertaV = 0;
    this.joelho = 0; this.joelhoV = 0;
    this.tonto = 0;
    this.fila = [];
    this.proximoCombo = 2.5;
    this.vagarEm = 1.5;
    this.telaOk = false;
    this.telaBateu = false;
    this.dolly = 0;
    this.quedaVis = 0;
    this.ameaca = 0;
    this.cordasDevolveu = false;
    this.montarPose = true;
    this.dtDoQuadro = 0;
    this.claraoPintado = -1;
    /* saídas de `resolver` */
    this.rPe = [V(), V()]; this.rTomba = [0, 0]; this.rMao = [V(), V()]; this.rCot = [V(), V()];
    this.rBacia = V(); this.rRot = new Base3();
    this.deitadoBacia = V(); this.deitadoAng = 0;
    this.levOk = false; this.levBacia = V(); this.levAng = 0; this.levPe = [V(), V()];
    /* as poses-chave do levantar e o trecho em que ele está, guardados */
    this.chavesBacia = [V(), V(), V(), V(), V()];
    this.chavesMao = [V(), V(), V(), V(), V()];
    this.chavesCot = [V(), V(), V(), V(), V()];
    this.trechoAtual = [0, 0];
    /* rascunhos próprios do quadro */
    this.t = { a: V(), b: V(), c: V(), d: V(), e: V(), f: V(), g: V(), h: V(), j: V(), k: V(), l: V(), m: V(),
      n: V(), o: V(), p: V(), q: V(), base1: new Base3(), base2: new Base3(), base3: new Base3() };

    this.malhas = [];
    this.matsPadrao = [];
    this.pele = null;
    this.matPele = null;
    this.expr = {};
    this.exprValor = {};
    this.montar(texturas);
  }

  /* ===================================================================
     MONTAGEM
     =================================================================== */
  montar(texturas) {
    let pele = null;
    const malhas = [];
    this.modelo.traverse((o) => {
      if (o.isSkinnedMesh) malhas.push(o);
    });
    if (!malhas.length) return;
    const esqueleto = malhas[0].skeleton;
    this.ossos = esqueleto.bones;
    /* Os nomes curtos ("Hips", "LeftArm"…): o three.js tira o ":" do
       "mixamorig:Hips"; o prefixo sai dos dois jeitos. */
    this.i = {};
    this.nomes = [];
    this.pais = [];
    for (let k = 0; k < this.ossos.length; k++) {
      const curto = this.ossos[k].name.replace(/^mixamorig[:_]?/i, "");
      this.i[curto] = k;
      this.nomes.push(curto);
    }
    for (let k = 0; k < this.ossos.length; k++) {
      const pai = this.ossos[k].parent;
      this.pais.push(pai && pai.isBone ? this.ossos.indexOf(pai) : -1);
    }
    for (const n of ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftArm", "LeftForeArm",
      "LeftHand", "LeftHandMiddle1", "LeftHandThumb1", "LeftUpLeg", "LeftLeg", "LeftFoot",
      "LeftToeBase", "LeftToe_End", "RightArm", "RightFoot", "HeadTop_End"]) {
      if (this.i[n] === undefined) return;
    }
    /* O repouso: no .glb cada osso só tem posição (nenhum giro), então o
       repouso global é a soma das posições até a raiz. */
    this.R = {};
    this.repousoOrigem = [];
    const global = [];
    for (let k = 0; k < this.ossos.length; k++) {
      const local = this.ossos[k].position.clone();
      this.repousoOrigem.push(local.clone());
      const p = this.pais[k];
      global.push(p >= 0 ? global[p].clone().add(local) : local.clone());
      this.R[this.nomes[k]] = global[k];
    }
    const R = this.R;
    /* O eixo secundário de repouso de cada osso de membro (a torção). */
    this.secundario = {};
    for (const s of ["Left", "Right"]) {
      const polegar = R[s + "HandThumb1"].clone().sub(R[s + "Hand"]);
      this.secundario[s + "Arm"] = new THREE.Vector3(0, 0, -1);
      this.secundario[s + "ForeArm"] = polegar;
      this.secundario[s + "Hand"] = polegar;
      this.secundario[s + "UpLeg"] = new THREE.Vector3(0, 0, 1);
      this.secundario[s + "Leg"] = new THREE.Vector3(0, 0, 1);
      this.secundario[s + "Foot"] = new THREE.Vector3(0, 1, 0);
      this.secundario[s + "ToeBase"] = new THREE.Vector3(0, 1, 0);
    }
    const topo = R.HeadTop_End.y;
    this.modelo.scale.setScalar(ALTURA_DA_FIGURA / Math.max(topo, 0.1));
    this.lBraco = R.LeftForeArm.distanceTo(R.LeftArm);
    this.lAnte = R.LeftHand.distanceTo(R.LeftForeArm);
    this.lCoxa = R.LeftLeg.distanceTo(R.LeftUpLeg);
    this.lCanela = R.LeftFoot.distanceTo(R.LeftLeg);
    this.h0 = R.Hips.y;
    this.tornozelo = R.LeftFoot.y;
    const dp = R.LeftToeBase.clone().sub(R.LeftFoot);
    this.descePe = Math.atan2(-dp.y, Math.hypot(dp.x, dp.z));
    const dd = R.LeftToe_End.clone().sub(R.LeftToeBase);
    this.desceDedo = Math.atan2(-dd.y, Math.hypot(dd.x, dd.z));
    this.peL = dp.length();
    this.solaPlanta = R.LeftToeBase.y;
    this.solaPonta = R.LeftToe_End.y;
    /* O calcanhar: logo abaixo do tornozelo, um pouco para trás. */
    this.calcanharOfs = new THREE.Vector3(0, -this.tornozelo, -0.035);
    this.prepararOssos();

    /* AS PEÇAS DO CORPO E OS MATERIAIS, com as mesmas regras do jogo:
       pele suada com relevo; cascas finas (calção, cinturão, friso, placa)
       com as duas faces; luvas de couro mais foscas e um pouco mais
       escuras; e a PEÇA DO AVESSO (a luva e a bota esquerdas vieram com os
       triângulos na ordem contrária) desenhando a face de dentro. Os
       materiais são feitos por [material, casca, avesso], na ordem das
       peças — como lá, onde a luva direita acaba com o material dos dentes. */
    const feitos = new Map();
    for (const mi of malhas) {
      mi.frustumCulled = false;
      mi.castShadow = false;
      mi.receiveShadow = false;
      this.malhas.push(mi);
      if (mi.name === "Pele") pele = mi;
    }
    if (pele) {
      this.pele = pele;
      const dic = pele.morphTargetDictionary || {};
      for (const nome of Object.keys(dic)) {
        this.expr[nome] = dic[nome];
        this.exprValor[nome] = 0;
      }
      const m = this.materialDoCorpo(pele.material, texturas, 0.44, 0.22, false);
      m.normalScale.set(1, 1);
      pele.material = m;
      this.matPele = m;
      this.matsPadrao.push(m);
    }
    for (const mi of this.malhas) {
      if (mi === pele) continue;
      const base = mi.material;
      const casca = ["Calcao", "Cinturao", "Friso", "Placa"].includes(mi.name);
      const avesso = Boxeador.doAvesso(mi.geometry);
      /* Lá a peça do avesso ganha `cull_front` (a face de fora aparece, com
         a luz certa). No three.js o lado de trás também vira a normal, e a
         luz sairia do avesso: aqui é a ordem dos triângulos que é
         desvirada, uma vez, na montagem. */
      if (avesso && !casca) Boxeador.desvirar(mi.geometry);
      const chave = base.name + "|" + casca + "|" + avesso;
      if (!feitos.has(chave)) {
        const luva = mi.name.startsWith("Luva");
        const novo = this.materialDoCorpo(base, texturas, luva ? Math.max(base.roughness, 0.42) : base.roughness,
          luva ? 0.10 : 0.18, casca);
        if (luva) novo.color.setRGB(0.72, 0.72, 0.72);
        novo.vertexColors = !!mi.geometry.attributes.color;
        feitos.set(chave, novo);
        this.matsPadrao.push(novo);
      }
      mi.material = feitos.get(chave);
    }
    this.pronto = true;
    this.reiniciarCorpo();
    this.tocar("idle");
  }

  /* Um material do corpo: a pintura e o relevo de TEXTURAS_DO_CORPO, o
     recorte de luz discreto e a emissão (o clarão do golpe) já ligada. */
  materialDoCorpo(base, texturas, aspereza, recorte, doisLados) {
    const nomes = TEXTURAS_DO_CORPO[base.name];
    const m = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: aspereza,
      metalness: base.metalness || 0,
      side: doisLados ? THREE.DoubleSide : THREE.FrontSide,
      emissive: 0x000000,
    });
    m.name = base.name;
    if (nomes) {
      if (nomes[0] && texturas[nomes[0]]) m.map = texturas[nomes[0]];
      if (nomes[1] && texturas[nomes[1]]) m.normalMap = texturas[nomes[1]];
    }
    instalarRecorte(m, recorte, 0.55);
    return m;
  }

  /* PEÇA DO AVESSO: a normal de cada triângulo contra a ordem dos
     vértices; quase todos ao contrário = a peça veio do avesso. */
  static doAvesso(geo) {
    const pos = geo.attributes.position, nor = geo.attributes.normal, idx = geo.index;
    if (!pos || !nor || !idx || idx.count < 3) return false;
    let avesso = 0, certo = 0;
    const passo = Math.max(3, Math.floor(idx.count / 3 / 200) * 3);
    const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), n = new THREE.Vector3(), t = new THREE.Vector3();
    for (let i = 0; i + 2 < idx.count; i += passo) {
      const i0 = idx.getX(i), i1 = idx.getX(i + 1), i2 = idx.getX(i + 2);
      a.fromBufferAttribute(pos, i0); b.fromBufferAttribute(pos, i1).sub(a); c.fromBufferAttribute(pos, i2).sub(a);
      n.fromBufferAttribute(nor, i0).add(t.fromBufferAttribute(nor, i1)).add(t.fromBufferAttribute(nor, i2));
      if (b.cross(c).dot(n) < 0) avesso++; else certo++;
    }
    return avesso > certo * 4;
  }

  static desvirar(geo) {
    const idx = geo.index;
    for (let i = 0; i + 2 < idx.count; i += 3) {
      const b = idx.getX(i + 1);
      idx.setX(i + 1, idx.getX(i + 2));
      idx.setX(i + 2, b);
    }
    idx.needsUpdate = true;
  }

  prepararOssos() {
    const comandados = ["Hips", "Neck", "Head", ...COLUNA];
    for (const lista of ["Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase"]) {
      comandados.push(...OSSOS_DO_LADO[lista]);
    }
    this.comandado = this.nomes.map((n) => comandados.includes(n));
    this.repousoT = [];
    for (let k = 0; k < this.nomes.length; k++) this.repousoT.push(null);
    for (const osso of comandados) {
      const filho = filhoDoOsso(osso);
      if (filho === osso || !this.R[filho]) continue;
      const dR = this.R[filho].clone().sub(this.R[osso]).normalize();
      const sR = this.secundario[osso] || new THREE.Vector3(0, 0, 1);
      this.repousoT[this.i[osso]] = ortonormal(dR, sR, new Base3()).transpor();
    }
    /* índices prontos dos ossos de cada lado */
    const ix = (n) => this.i[n];
    this.k = {};
    for (const [nome, lista] of Object.entries(OSSOS_DO_LADO)) this.k[nome] = lista.map(ix);
    this.k.Hips = ix("Hips"); this.k.Neck = ix("Neck"); this.k.Head = ix("Head");
    this.k.coluna = COLUNA.map(ix);
    this.k.Spine2 = ix("Spine2");
    this.G = this.nomes.map(() => new Base3());
    this.O = this.nomes.map(() => new THREE.Vector3());
    this.gravouFixos = false;
  }

  basePe(k, out) {
    const b = k === 0 ? PE_FRENTE : PE_TRAS;
    return out.set(this.centro.x + b[0], this.centro.y + b[1]);
  }

  giroDoPe(k) { return k === 0 ? -0.10 : -0.38; }

  reiniciarCorpo() {
    this.centro.set(0, 0);
    this.centroAlvo.set(0, 0);
    this.centroVel.set(0, 0);
    const b = new THREE.Vector2();
    for (let k = 0; k < 2; k++) {
      this.basePe(k, b);
      this.pe[k].set(b.x, this.tornozelo, b.y);
      this.peGiro[k] = this.giroDoPe(k);
      this.passoT[k] = -1;
      this.calcanhar[k] = 0;
    }
    this.bacia.set(0, this.h0 - 0.05, 0);
    this.baciaRot.set(0, GIRO_DA_BASE, 0);
    this.tronco.set(0, 0, 0);
    this.cabeca.set(0, 0, 0);
    this.molaCab.set(0, 0, 0); this.molaCabV.set(0, 0, 0);
    this.molaTronco.set(0, 0, 0); this.molaTroncoV.set(0, 0, 0);
    for (let i = 0; i < 3; i++) { this.vertebra[i].set(0, 0, 0); this.vertebraV[i].set(0, 0, 0); }
    this.guardaAberta = 0; this.guardaAbertaV = 0;
    this.joelho = 0; this.joelhoV = 0;
    this.tonto = 0;
    this.fila.length = 0;
    this.quedaVis = 0;
    this.dolly = 0;
    this.telaOk = false;
    this.telaBateu = false;
    this.levOk = false;
    for (let k = 0; k < 2; k++) {
      this.noTronco(this.guardaLocal(k, 1, this.t.a), this.mao[k]);
      this.maoDir[k].set(0, 0.8, 0.6).normalize();
      this.polegar[k].set(0, 0.4, -1).normalize();
      this.cotovelo[k].set(0.3 * ladoS(k), -1, -0.3).normalize();
    }
  }

  /* ===================================================================
     A LÓGICA DO COMBATE (lutador.gd)
     =================================================================== */
  preparar() {
    this.dano = 0;
    this.queda = 0;
    this.caindo = false;
    this.levantando = false;
    this.recuo = 0;
    this.tempoReacao = 0;
    this.tempoNaLona = 0;
    this.clarao = 0;
    this.emGuarda = false;
    this.ficaNoChao = false;
    this.vaiComemorar = false;
    this.comemoraDepoisDoSoco = false;
    this.festa = "celebra";
    this.papel = "";
    this.tocar("idle");
    if (!this.pronto) return;
    this.reiniciarCorpo();
    for (const nome of Object.keys(this.exprValor)) {
      this.exprValor[nome] = 0;
      if (this.pele) this.pele.morphTargetInfluences[this.expr[nome]] = 0;
    }
    this.pintar();
  }

  guardar(ativo) {
    this.emGuarda = ativo;
    // Nocauteado no fim fica na lona; comemorando, não volta à guarda.
    if (this.caindo || this.ficaNoChao || PAPEIS_DE_FESTA.includes(this.papel)) return;
    this.tocar(ativo ? "guard" : "idle");
  }

  bater(forca, derruba = false, pontos = -1, ultimo = false) {
    const f = limitar(forca, 0, 1);
    this.recuo = 1;
    this.forcaDoRecuo = f;
    this.lado *= -1;
    this.clarao = 1;
    const antes = this.dano;
    if (f > DANO_MINIMO) this.dano = limitar(this.dano + f * DANO_POR_GOLPE, 0, 1);
    const nocaute = !this.caindo && (derruba || (this.dano >= 1 && antes < 1));
    let papel = "";
    let desdenhou = false;
    if (nocaute) {
      papel = "knockout";
      this.caindo = true;
      this.levantando = false;
      this.tempoNaLona = 0;
      this.tempoReacao = TEMPO_NA_LONA + TEMPO_LEVANTAR;
      this.ficaNoChao = ultimo;
      this.tocar("knockout");
    } else if (!this.caindo) {
      papel = reacaoParaPontos(pontos, f);
      // NO ÚLTIMO SOCO ELE NÃO DESDENHA: sente o golpe fraco e o que vem
      // em seguida é o soco final.
      if (ultimo && papel === "taunt_weak") papel = "hit_light";
      desdenhou = papel === "taunt_weak" && pontos >= 0 && pontos < LIMITE_DO_DESDEM;
      this.tempoReacao = DURACAO[papel] !== undefined ? DURACAO[papel] : 0.8;
      this.vaiComemorar = false;
      this.tocar(papel);
    }
    const resposta = { nocaute, dano: this.dano, reacao: papel, desdenhou };
    if (!this.pronto) return resposta;
    /* o corpo (lutador_boxeador.gd) */
    this.fila.length = 0;
    this.telaOk = false;
    if (papel === "taunt_weak") {
      // Nem sentiu: o queixo mal mexe.
      this.molaCabV.x += -1.2;
      this.molaCabV.y += 0.8 * this.lado;
      this.tempoReacao = 2.3;
      return resposta;
    }
    // O soco vem da câmera: a cabeça vai para trás e para o lado, o tronco
    // recua, a guarda abre e o corpo é empurrado — os pés dão passos.
    const forte = 0.35 + f * 0.9;
    this.molaCabV.x += -9.5 * forte; this.molaCabV.y += this.lado * 5.5 * forte; this.molaCabV.z += this.lado * 4.0 * forte;
    this.molaTroncoV.x += -4.5 * forte; this.molaTroncoV.y += this.lado * 2.2 * forte; this.molaTroncoV.z += this.lado * 1.6 * forte;
    this.guardaAbertaV += 7.0 * forte;
    this.joelhoV += 3.5 * forte;
    this.centroVel.x += this.lado * 0.35 * f;
    this.centroVel.y += -(0.55 + 1.35 * f);
    if (papel === "stagger" || nocaute) this.tonto = 1.6;
    return resposta;
  }

  /* O FIM DA RODADA: "derrota", "vitoria", "nocaute" ou "empate". */
  fimDeRodada(desfecho) {
    this.comemoraDepoisDoSoco = false;
    if (desfecho === "vitoria" || desfecho === "nocaute") {
      // PERDEU A LUTA, NÃO COMEMORA: zonzo, cabeça baixa.
      this.festa = "tonto";
      this.vaiComemorar = true;
      if (PAPEIS_DE_FESTA.includes(this.papel)) this.tocar(this.festa);
    } else {
      // GANHOU: primeiro o nocaute na câmera, só depois a festa.
      this.festa = desfecho === "derrota" ? "deboche" : "celebra";
      this.vaiComemorar = false;
      this.comemoraDepoisDoSoco = true;
      if (PAPEIS_DE_FESTA.includes(this.papel)) this.tocar("guard");
    }
  }

  venceu(festa = "") {
    this.comemoraDepoisDoSoco = false;
    if (festa) this.festa = festa;
    this.vaiComemorar = true;
    if (PAPEIS_DE_FESTA.includes(this.papel)) this.tocar(this.festa);
  }

  /* QUEM DEMORA LEVA: avança, arma e solta o direto na câmera. */
  socoNaTela() {
    if (!this.pronto || this.caindo || PAPEIS_DE_FESTA.includes(this.papel)) return false;
    if (this.papel !== "guard" && this.papel !== "idle") return false;
    this.fila.length = 0;
    this.telaOk = true;
    this.telaBateu = false;
    this.tempoReacao = 2.9;
    this.tocar("soco_tela");
    return true;
  }

  /* O SOCO FINAL de quem venceu a luta (o jogador perdeu). */
  socoFinal() {
    if (!this.pronto || this.caindo) return false;
    // Ainda sentindo o soco do jogador: termina a reação e só então vem.
    if (DURACAO[this.papel] !== undefined && this.tempoReacao > 0) return false;
    if (this.comemoraDepoisDoSoco) {
      this.comemoraDepoisDoSoco = false;
      this.vaiComemorar = true;
    }
    this.fila.length = 0;
    this.telaOk = true;
    this.telaBateu = false;
    this.tempoReacao = 2.4;
    this.papel = "";
    this.tocar("soco_tela");
    return true;
  }

  /* Verdadeiro UMA vez, no quadro em que a luva encosta na câmera. */
  telaAtingida() {
    if (this.telaBateu) { this.telaBateu = false; return true; }
    return false;
  }

  cameraExtra(out) { return out.set(this.dolly, this.dolly * 0.08); }

  deslocamento(out) {
    const s = this.modelo.scale.x;
    return out.set(this.centro.x * s, 0, this.centro.y * s);
  }

  /* Quanto o corpo empurra as cordas de trás (0–1). */
  pressaoNasCordas() {
    if (this.papel !== "cordas") return 0;
    return limitar((-this.centro.y - (CORDAS_Z - 0.18)) / 0.18, 0, 1);
  }

  tocar(papel) {
    if (!PAPEIS.includes(papel)) papel = "idle";
    if (this.papel === papel) return;
    this.papel = papel;
    this.tempoNoPapel = 0;
  }

  /* O QUADRO: fatias de até 1/20 s, 40% mais rápidas que o relógio; a pose
     é montada só na última. */
  atualizar(delta) {
    if (!this.pronto) return;
    let resto = limitar(delta, 0, PASSO_MAXIMO) * VELOCIDADE;
    this.dtDoQuadro = resto;
    for (;;) {
      const d = Math.min(resto, SUBPASSO);
      this.dt = d;
      resto -= d;
      this.montarPose = resto <= 0.0005;
      this.passoDaLogica(d);
      if (this.montarPose) break;
    }
    this.montarPose = true;
  }

  /* `Lutador3D.atualizar` (lutador.gd). */
  passoDaLogica(delta) {
    this.relogio += delta;
    this.tempoNoPapel += delta;
    this.recuo = Math.max(0, this.recuo - delta * 2.1);
    this.clarao = Math.max(0, this.clarao - delta * 3.4);
    this.tempoReacao = Math.max(0, this.tempoReacao - delta);
    const festa = PAPEIS_DE_FESTA.includes(this.papel);
    if (this.caindo) {
      this.tempoNaLona += delta;
      this.queda = Math.min(1, this.queda + delta * 2.8);
      if (!this.ficaNoChao && this.tempoNaLona >= TEMPO_NA_LONA && !this.levantando) {
        this.levantando = true;
        this.tocar("get_up");
      }
      if (this.levantando) this.queda = Math.max(0, 1 - (this.tempoNaLona - TEMPO_NA_LONA) / TEMPO_LEVANTAR);
      if (!this.ficaNoChao && this.tempoNaLona >= TEMPO_NA_LONA + TEMPO_LEVANTAR) {
        this.caindo = false;
        this.levantando = false;
        this.queda = 0;
        this.dano = Math.min(this.dano, 0.72);
        this.tocar(this.emGuarda ? "guard" : "idle");
      }
    } else if (this.tempoReacao <= 0 && this.vaiComemorar && !festa) {
      // Aguentou a rodada (ou ganhou): a festa.
      this.tocar(this.festa);
    } else if (this.tempoReacao <= 0 && !PAPEIS_CONTINUOS.includes(this.papel) && !festa) {
      this.tocar(this.emGuarda ? "guard" : "idle");
    }
    this.moverOCorpo();
    this.pintar();
  }

  acenderClarao(valor) { this.clarao = Math.max(this.clarao, limitar(valor, 0, 1)); }

  /* ===================================================================
     O CORPO (lutador_boxeador.gd)
     =================================================================== */
  moverOCorpo() {
    const dt = this.dt;
    if (this.papel !== "soco_tela") this.dolly = lerp(this.dolly, 0, 1 - Math.exp(-dt * 5));
    this.molas(dt);
    this.coreografia(dt);
    this.suavizar(dt);
    this.andar(dt);
    this.raiz();
    if (!this.montarPose) return;
    this.resolver();
    this.rosto(this.dtDoQuadro);
  }

  molas(dt) {
    // Mola amortecida: vai, passa um pouco e volta.
    const k = 95, c = 11;
    this.molaCabV.x += (-this.molaCab.x * k - this.molaCabV.x * c) * dt;
    this.molaCabV.y += (-this.molaCab.y * k - this.molaCabV.y * c) * dt;
    this.molaCabV.z += (-this.molaCab.z * k - this.molaCabV.z * c) * dt;
    this.molaCab.addScaledVector(this.molaCabV, dt);
    this.molaTroncoV.x += (-this.molaTronco.x * 70 - this.molaTroncoV.x * 10) * dt;
    this.molaTroncoV.y += (-this.molaTronco.y * 70 - this.molaTroncoV.y * 10) * dt;
    this.molaTroncoV.z += (-this.molaTronco.z * 70 - this.molaTroncoV.z * 10) * dt;
    this.molaTronco.addScaledVector(this.molaTroncoV, dt);
    this.guardaAbertaV += (-this.guardaAberta * 40 - this.guardaAbertaV * 9) * dt;
    this.guardaAberta = limitar(this.guardaAberta + this.guardaAbertaV * dt, -0.2, 1.3);
    this.joelhoV += (-this.joelho * 45 - this.joelhoV * 8) * dt;
    this.joelho = limitar(this.joelho + this.joelhoV * dt, -0.3, 1.2);
    this.tonto = Math.max(0, this.tonto - dt);
  }

  /* ---------------------------------------------------------- coreografia */
  coreografia(dt) {
    const t = this.relogio;
    const tp = this.tempoNoPapel;
    const ex = this.aExpr;
    ex.deboche = 0; ex.dor = 0; ex.grito = 0; ex.apagado = 0;
    this.rapidez = 16;
    for (let k = 0; k < 2; k++) { this.aCalcanhar[k] = 0; this.aOmbro[k].set(0, 0); }
    this.aBaciaRot.set(0, GIRO_DA_BASE, 0);
    this.aTronco.set(0.10, 0, 0);
    this.aCabeca.set(0.10, 0, 0);
    let guarda = 1;

    // ---- a ginga: quique na ponta dos pés, peso indo e vindo.
    const compasso = this.papel === "guard" ? 1.9 : 1.35;
    const fase = t * TAU * compasso * 0.5;
    const quique = 0.5 - 0.5 * Math.cos(fase * 2);
    const balanco = Math.sin(fase);
    let ginga = 1, agacha = 0.075;
    if (this.papel === "idle") { agacha = 0.045; guarda = 0.55; ginga = 0.7; }
    this.aBacia.set(balanco * 0.018 * ginga, this.h0 - agacha - quique * 0.022 * ginga, 0);
    this.aBaciaRot.z = balanco * 0.035 * ginga;
    this.aTronco.z = -balanco * 0.03 * ginga;
    this.aTronco.x += quique * 0.02;
    for (let k = 0; k < 2; k++) this.aCalcanhar[k] = quique * 0.35 * ginga;
    // respiração: no peito, um pouco mais funda depois de apanhar
    this.respiro = Math.sin(t * 2.4) * (0.014 + 0.012 * limitar(this.tonto, 0, 1));
    this.aOmbro[0].x = Math.sin(t * 2.4) * 0.02;
    this.aOmbro[1].x = Math.sin(t * 2.4) * 0.02;

    // ---- andar pelo ringue: um ponto novo de tempos em tempos.
    this.vagarEm -= dt;
    if (this.vagarEm <= 0 && (this.papel === "guard" || this.papel === "idle")) {
      this.vagarEm = sorteio(1.2, 2.8);
      this.centroAlvo.set(sorteio(-0.16, 0.16), sorteio(-0.12, 0.10));
    }

    // ---- as luvas na guarda (no espaço do tronco)
    for (let k = 0; k < 2; k++) {
      const s = ladoS(k);
      this.guardaLocal(k, guarda, this.aMao[k]);
      this.aMaoDir[k].set(0.12 * -s, 0.82, 0.55).normalize();
      this.aPolegar[k].set(-0.35 * s, 0.35, -0.85).normalize();
      this.aCotovelo[k].set(0.35 * s, -1.0, -0.15).normalize();
    }

    switch (this.papel) {
      case "guard":
        this.combosNoAr(dt);
        break;
      case "idle": {
        // Solto, antes da luta: ombros girando, luvas batendo.
        if (t % 7 < 1.2) {
          const g = Math.sin((t % 7) / 1.2 * Math.PI);
          this.aOmbro[0].x += g * 0.12;
          this.aOmbro[1].x += g * 0.12;
          this.aCabeca.z += Math.sin(t * 5) * 0.18 * g;
        }
        if ((t + 3) % 6 < 0.5) {
          const g2 = Math.sin(((t + 3) % 6) / 0.5 * Math.PI);
          this.aMao[0].x += -0.07 * g2; this.aMao[0].z += 0.05 * g2;
          this.aMao[1].x += 0.07 * g2; this.aMao[1].z += 0.05 * g2;
        }
        break;
      }
      case "taunt_weak":
        this.nemSentiu(tp);
        break;
      case "hit_light":
      case "hit_medium":
      case "hit_heavy":
        ex.dor = tp < 0.7 ? 1 : 0.4;
        this.rapidez = 12;
        break;
      case "stagger":
        ex.dor = 1;
        this.rapidez = 9;
        break;
      case "celebra":
        this.celebrar(tp);
        break;
      case "deboche":
        this.debochar(tp);
        break;
      case "tonto":
        this.zonzo(tp);
        break;
      case "soco_tela":
        this.socarATela(tp);
        break;
      case "cordas":
        this.nasCordas(tp);
        break;
      case "knockout":
        // Apagou: os joelhos cedem, a cabeça vai para trás e a guarda cai.
        ex.apagado = 1;
        this.aBacia.y -= 0.10;
        this.aTronco.x -= 0.15;
        this.aCabeca.x -= 0.35;
        for (let k = 0; k < 2; k++) this.guardaLocal(k, 0.15, this.aMao[k]);
        this.rapidez = 14;
        break;
      case "get_up": {
        const g = this.levantarG();
        ex.apagado = 0.4 * (1 - g);
        ex.dor = 0.8;
        this.aTronco.x += 0.30 * Math.sin(g * Math.PI);
        this.aCabeca.x += 0.12 * Math.sin(g * Math.PI);
        break;
      }
      default:
        break;
    }

    this.golpesEmAndamento(dt);

    // ---- cambaleio: o corpo procura o equilíbrio em passos tortos.
    if (this.tonto > 0) {
      const w = limitar(this.tonto, 0, 1);
      this.centroAlvo.x += Math.sin(t * 3.3) * 0.10 * w * dt * 4;
      this.centroAlvo.y += Math.sin(t * 2.1) * 0.06 * w * dt * 4;
      this.aBaciaRot.z += Math.sin(t * 4.1) * 0.10 * w;
      this.aTronco.z += Math.sin(t * 3.2 + 1) * 0.12 * w;
      this.aCabeca.x += Math.sin(t * 2.7) * 0.15 * w;
      this.aCabeca.y += Math.sin(t * 1.9) * 0.2 * w;
      this.aCabeca.z += Math.sin(t * 3.1) * 0.2 * w;
      for (let k = 0; k < 2; k++) { this.aMao[k].y += -0.16 * w; this.aMao[k].z += -0.02 * w; }
      ex.dor = Math.max(ex.dor, w);
    }

    // ---- reações por cima de tudo (molas)
    const abre = limitar(this.guardaAberta, 0, 1.2);
    for (let k = 0; k < 2; k++) {
      this.aMao[k].x += 0.10 * ladoS(k) * abre;
      this.aMao[k].y += -0.18 * abre;
      this.aMao[k].z += -0.10 * abre;
    }
    this.aBacia.y -= limitar(this.joelho, -0.2, 1.0) * 0.09;

    // ---- a cabeça olha para quem joga (compensa o giro da base)
    this.aCabeca.y += -(this.aBaciaRot.y + this.aTronco.y) * 0.75;

    // ---- o deslocamento do corpo: empurrão do golpe + vontade de andar
    const antesX = this.centro.x, antesY = this.centro.y;
    this.centroVel.multiplyScalar(Math.exp(-dt * 3.2));
    this.centro.x += (this.centroVel.x + (this.centroAlvo.x - this.centro.x) * 2.2) * dt;
    this.centro.y += (this.centroVel.y + (this.centroAlvo.y - this.centro.y) * 2.2) * dt;
    this.centro.x = limitar(this.centro.x, -0.55, 0.55);
    // Nas cordas ele pode chegar até elas; fora disso, fica no miolo.
    this.centro.y = limitar(this.centro.y, this.papel === "cordas" ? -CORDAS_Z : -0.95, 1.05);
    // NA QUEDA, OS PÉS ESCORREGAM PARA A FRENTE: o corpo inteiro deita
    // dentro da lona (e não com a cabeça para fora das cordas).
    if (this.quedaVis > 0 && this.papel !== "get_up") {
      const livre = (ALTURA_DA_FIGURA * 1.02 - RINGUE_LIVRE) / Math.max(this.modelo.scale.x, 0.01);
      const junto = limitar(this.quedaVis * 1.6, 0, 1);
      this.centro.y = Math.max(this.centro.y, lerp(this.centro.y, livre, junto));
      this.centro.x = lerp(this.centro.x, limitar(this.centro.x, -0.35, 0.35), junto);
      this.centroVel.y = Math.max(this.centroVel.y, 0);
    }
    // Caindo, os pés não dão passo: deslizam junto com o corpo.
    if ((this.caindo || this.queda > 0.01) && this.papel !== "get_up") {
      const ax = this.centro.x - antesX, az = this.centro.y - antesY;
      for (let k = 0; k < 2; k++) { this.pe[k].x += ax; this.pe[k].z += az; }
    }
    this.aBacia.x += this.centro.x;
    this.aBacia.z += this.centro.y;
  }

  /* Onde a luva fica na guarda, a partir do tronco. */
  guardaLocal(k, fechada, out) {
    const s = ladoS(k);
    const f = limitar(fechada, 0, 1);
    let ax, ay, az;
    if (k === 0) { ax = 0.115 * s; ay = -0.035; az = 0.29; } else { ax = -0.10; ay = -0.055; az = 0.22; }
    const bx = 0.17 * s, by = -0.20, bz = 0.12;
    return out.set(bx + (ax - bx) * f, by + (ay - by) * f, bz + (az - bz) * f);
  }

  combosNoAr(dt) {
    this.proximoCombo -= dt;
    if (this.proximoCombo <= 0 && this.fila.length === 0) {
      this.proximoCombo = sorteio(1.6, 3.6);
      const combo = COMBOS[sorteioInteiro(0, COMBOS.length - 1)];
      let atraso = 0;
      for (const g of combo) {
        this.fila.push({ tipo: g[0], lado: g[1], t: -atraso });
        atraso += GOLPES_DELE[g[0]].dur * sorteio(0.62, 0.8);
      }
    }
  }

  /* O SOCO DELE VINDO NA CÂMERA: a arena faz a câmera recuar com ele. */
  golpesEmAndamento(dt) {
    this.ameaca = 0;
    if (!this.fila.length) return;
    let vivos = 0;
    for (let n = 0; n < this.fila.length; n++) {
      const g = this.fila[n];
      g.t += dt;
      const receita = GOLPES_DELE[g.tipo];
      const tt = g.t / receita.dur;
      if (tt > 1) continue;
      this.fila[vivos++] = g;
      if (tt < 0) continue;
      this.aplicarGolpe(g.tipo, g.lado, tt, receita.pico);
      if (g.tipo === "jab" || g.tipo === "direto") {
        this.ameaca = Math.max(this.ameaca, Math.max(Boxeador.envelope(tt, receita.pico), 0) * (g.tipo === "direto" ? 1 : 0.7));
      }
    }
    this.fila.length = vivos;
  }

  /* Envelope de um golpe: recolhe um pouco, estica rápido, segura e volta. */
  static envelope(tt, pico) {
    if (tt < 0.12) return -0.12 * Math.sin(tt / 0.12 * Math.PI * 0.5);
    if (tt < pico) {
      const u = (tt - 0.12) / (pico - 0.12);
      return -0.12 + 1.12 * (1 - Math.pow(1 - u, 3));
    }
    if (tt < pico + 0.08) return 1;
    const v = (tt - pico - 0.08) / (1 - pico - 0.08);
    return 1 - v * v * (3 - 2 * v);
  }

  aplicarGolpe(tipo, k, tt, pico) {
    const T = this.t;
    const e = Boxeador.envelope(tt, pico);
    const ep = Math.max(e, 0);
    const s = ladoS(k);
    this.rapidez = Math.max(this.rapidez, 34);
    const ombro = T.a.copy(this.R[OSSOS_DO_LADO.Arm[k]]);
    ombro.x += this.bacia.x; ombro.y += this.bacia.y - this.h0; ombro.z += this.bacia.z;
    const alcance = (this.lBraco + this.lAnte) * 0.97;
    if (tipo === "jab" || tipo === "direto") {
      const d = T.b.set(-0.03 * s + this.centro.x, 1.47, 1.2 + this.centro.y).sub(ombro).normalize();
      const fim = this.doMundo(T.c.copy(ombro).addScaledVector(d, alcance), T.c);
      this.aMao[k].lerp(fim, ep);
      this.aMaoDir[k].lerp(d, ep).normalize();
      this.aPolegar[k].lerp(T.d.set(-s, 0.25, 0).normalize(), ep).normalize();
      this.aCotovelo[k].lerp(T.d.set(0.8 * s, -0.5, 0).normalize(), ep).normalize();
      this.aOmbro[k].x += 0.10 * ep;
      this.aOmbro[k].y += 0.18 * ep;
      if (tipo === "direto") {
        // O direto vem do chão: gira bacia e tronco, o calcanhar de trás sobe.
        this.aBaciaRot.y += 0.55 * e;
        this.aTronco.y += 0.35 * e;
        this.aCalcanhar[1] = Math.max(this.aCalcanhar[1], ep);
        this.aBacia.z += 0.04 * ep;
      } else {
        this.aTronco.y += -0.14 * e;
        this.aBacia.z += 0.02 * ep;
      }
      this.aCabeca.z += 0.06 * s * ep;
    } else if (tipo === "gancho") {
      const mira = this.doMundo(T.b.set(-0.28 * s, 0.02, 0.36).add(ombro), T.b);
      this.aMao[k].lerp(mira, ep);
      this.aMaoDir[k].lerp(T.d.set(-s, 0.1, 0.35).normalize(), ep).normalize();
      this.aPolegar[k].lerp(T.d.set(0, 1, 0), ep).normalize();
      this.aCotovelo[k].lerp(T.d.set(s, 0.35, -0.2).normalize(), ep).normalize();
      this.aTronco.y += (k === 0 ? -0.55 : 0.55) * e;
      this.aBaciaRot.y += (k === 0 ? -0.30 : 0.30) * e;
      this.aCalcanhar[k] = Math.max(this.aCalcanhar[k], ep * 0.8);
    } else if (tipo === "upper") {
      const baixo = T.b.set(-0.05 * s, -0.30, 0.22).add(ombro);
      const alto = T.c.set(-0.10 * s, 0.14, 0.36).add(ombro);
      const alvo = this.doMundo(baixo.lerp(alto, limitar(e, 0, 1)), T.b);
      this.aMao[k].lerp(alvo, limitar(Math.abs(e) * 1.5, 0, 1));
      this.aMaoDir[k].lerp(T.d.set(0, 1, 0.25).normalize(), ep).normalize();
      this.aPolegar[k].lerp(T.d.set(0, 0.2, -1).normalize(), ep).normalize();
      this.aCotovelo[k].lerp(T.d.set(0.2 * s, -1, 0.1).normalize(), ep).normalize();
      this.aBacia.y -= 0.05 * Math.sin(limitar(tt / pico, 0, 1) * Math.PI * 0.5) * (1 - ep) + 0.02 * ep;
      this.aTronco.y += (k === 1 ? 0.40 : -0.40) * e;
      this.aTronco.x += -0.10 * ep;
    }
    this.aExpr.grito = Math.max(this.aExpr.grito, ep * 0.35);
  }

  /* NAS CORDAS. 0–0,45 s vai de costas até elas; 0,45–1,05 s encosta,
     braços por cima da corda, as cordas cedem; depois elas o devolvem. */
  nasCordas(tp) {
    const T = this.t;
    const vai = limitar(tp / 0.45, 0, 1);
    const apoio = limitar((tp - 0.30) / 0.25, 0, 1) * (1 - limitar((tp - 1.05) / 0.35, 0, 1));
    if (tp < 1.05) {
      this.cordasDevolveu = false;
      this.centroAlvo.set(this.centro.x * 0.6, lerp(this.centro.y, -CORDAS_Z, ease(vai, 0.5)));
      this.vagarEm = 2.0;
    } else if (!this.cordasDevolveu) {
      // o estilingue das cordas
      this.cordasDevolveu = true;
      this.centroVel.y += 2.1;
      this.centroAlvo.set(sorteio(-0.08, 0.08), 0.02);
    }
    this.aTronco.x -= 0.34 * apoio;
    this.aCabeca.x -= 0.22 * apoio;
    this.aBacia.y -= 0.03 * apoio;
    for (let k = 0; k < 2; k++) {
      const sl = ladoS(k);
      this.aMao[k].lerp(T.a.set(0.46 * sl, -0.04, -0.20), apoio);
      this.aMaoDir[k].lerp(T.a.set(sl, -0.2, -0.3).normalize(), apoio).normalize();
      this.aCotovelo[k].lerp(T.a.set(sl, -0.5, -0.3).normalize(), apoio).normalize();
    }
    this.aExpr.dor = tp < 1.2 ? 1 : 0.5;
    this.rapidez = 10;
  }

  nemSentiu(tp) {
    // Nem sentiu. Balança a cabeça, sorri de lado e chama com a luva.
    this.aExpr.deboche = limitar(tp * 3, 0, 1);
    if (tp > 0.25 && tp < 1.1) {
      const u = (tp - 0.25) / 0.85;
      this.aCabeca.y += Math.sin(u * TAU * 2) * 0.28 * Math.sin(u * Math.PI);
    }
    if (tp > 1.0) {
      const u2 = ((tp - 1.0) % 0.65) / 0.65;
      const chama = Math.sin(u2 * Math.PI);
      // a luva da frente sai e volta, "vem"
      this.aMao[0].x += 0.04 * chama; this.aMao[0].y += 0.02 * chama; this.aMao[0].z += 0.14 * chama;
      this.aMaoDir[0].set(0, 0.3 + 0.7 * chama, 0.9 - 0.6 * chama).normalize();
      this.aCabeca.x -= 0.10;
      this.aCabeca.z += 0.12;
    }
  }

  celebrar(tp) {
    // Aguentou: braços para o alto, pula com a torcida.
    const T = this.t;
    const entra = limitar(tp * 3, 0, 1);
    const pulo = Math.abs(Math.sin(this.relogio * TAU * 1.1));
    this.aBacia.y += pulo * 0.035 * entra;
    for (let k = 0; k < 2; k++) {
      const s = ladoS(k);
      this.aMao[k].lerp(T.a.set(0.28 * s, 0.42 + 0.05 * Math.sin(this.relogio * 6 + k), 0.06), entra);
      this.aMaoDir[k].lerp(T.a.set(0.1 * s, 1, 0.1).normalize(), entra).normalize();
      this.aCotovelo[k].lerp(T.a.set(s, 0.1, -0.2).normalize(), entra).normalize();
      this.aCalcanhar[k] = Math.max(this.aCalcanhar[k], pulo * entra);
    }
    this.aCabeca.x -= 0.25 * entra;
    this.aExpr.grito = entra * (0.6 + 0.4 * Math.sin(this.relogio * 3));
  }

  /* A FESTA LONGA DE QUEM GANHOU DO JOGADOR: oito segundos em cinco atos,
     em laço — vitória, "Ali shuffle", aponta e ri, "bate aqui", bíceps. */
  debochar(tp) {
    const T = this.t;
    const ato = tp % 8;
    const entra = limitar(tp * 3, 0, 1);
    this.aBaciaRot.y *= 0.4;
    if (ato < 1.5) { this.celebrar(ato + 0.4); return; }
    if (ato < 3.4) {
      const u = ato - 1.5;
      const troca = Math.sin(u * TAU * 3.2);
      this.centroAlvo.set(troca * 0.03, 0);
      for (let k = 0; k < 2; k++) {
        const s = ladoS(k);
        this.aMao[k].lerp(T.a.set(0.20 * s, -0.12 + 0.05 * troca * s, 0.16), entra);
        this.aCalcanhar[k] = 0.6;
      }
      this.aBacia.y += Math.abs(troca) * 0.02;
      this.aCabeca.y += Math.sin(u * 5) * 0.18;
      this.aExpr.deboche = 1;
      return;
    }
    if (ato < 5.0) {
      // Aponta para quem jogou e ri.
      const u2 = limitar((ato - 3.4) * 4, 0, 1);
      const ombro = T.a.copy(this.R.LeftArm);
      ombro.x += this.bacia.x; ombro.y += this.bacia.y - this.h0; ombro.z += this.bacia.z;
      const d = T.b.set(this.centro.x, 1.5, 2.0).sub(ombro).normalize();
      const mira = this.doMundo(T.c.copy(ombro).addScaledVector(d, (this.lBraco + this.lAnte) * 0.95), T.c);
      this.aMao[0].lerp(mira, u2);
      this.aMaoDir[0].lerp(d, u2).normalize();
      this.aCotovelo[0].set(0.7, -0.6, 0).normalize();
      const ri = 0.5 + 0.5 * Math.sin(this.relogio * 18);
      this.aTronco.x += -0.12 - 0.04 * ri;
      this.aCabeca.x += -0.28 - 0.05 * ri;
      this.aMao[1].lerp(T.d.set(-0.05, -0.12, 0.14), u2);
      this.aExpr.grito = 0.5 + 0.35 * ri;
      this.aExpr.deboche = 0.6;
      return;
    }
    if (ato < 6.5) {
      // "Bate aqui": a luva bate duas vezes no próprio queixo.
      const u3 = ato - 5.0;
      const bate = Math.abs(Math.sin(u3 * TAU * 1.4));
      this.aMao[0].lerp(T.a.set(0.02, 0.10 + 0.03 * bate, 0.12 + 0.05 * bate), 0.9);
      this.aMaoDir[0].set(-0.3, 0.9, 0.2).normalize();
      this.aCabeca.x -= 0.18;
      this.aCabeca.z += 0.10;
      this.aExpr.deboche = 1;
      return;
    }
    // Mostra os bíceps, gritando.
    const u4 = limitar((ato - 6.5) * 4, 0, 1);
    for (let k = 0; k < 2; k++) {
      const s = ladoS(k);
      this.aMao[k].lerp(T.a.set(0.36 * s, 0.24, 0.04), u4);
      this.aMaoDir[k].lerp(T.a.set(-0.6 * s, 0.8, 0).normalize(), u4).normalize();
      this.aCotovelo[k].set(s, -0.15, -0.2).normalize();
    }
    this.aTronco.x += 0.12 * u4;
    this.aExpr.grito = u4;
  }

  zonzo(tp) {
    // Levou bonito e ficou de pé: zonzo, balança a cabeça, respeita.
    this.tonto = Math.max(this.tonto, 0.8);
    const u = limitar(tp * 2, 0, 1);
    this.aExpr.dor = 0.7;
    for (let k = 0; k < 2; k++) this.aMao[k].lerp(this.guardaLocal(k, 0.35, this.t.a), u);
    if (tp > 2.0) {
      this.aCabeca.y += Math.sin(tp * 7) * 0.12;
      this.aCabeca.x += 0.12;
    }
  }

  /* QUEM DEMORA LEVA. Avança, arma, e solta o direto na câmera. */
  socarATela(tp) {
    const T = this.t;
    if (tp < 0.75) { this.centroAlvo.set(0.02, 0.95); this.aExpr.deboche = 0.6; }
    else if (tp < 1.55) this.centroAlvo.set(0.02, 0.95);
    else this.centroAlvo.set(0, 0);
    const arma = limitar((tp - 0.72) / 0.28, 0, 1) * (1 - limitar((tp - 1.0) / 0.06, 0, 1));
    const solta = limitar((tp - 1.0) / 0.10, 0, 1);
    const volta = limitar((tp - 1.25) / 0.45, 0, 1);
    const e = solta * (1 - volta * volta * (3 - 2 * volta));
    // arma: recolhe o direito e gira o corpo para trás
    this.aTronco.y += -0.35 * arma + 0.55 * e;
    this.aBaciaRot.y += -0.2 * arma + 0.6 * e;
    this.aCalcanhar[1] = Math.max(this.aCalcanhar[1], e);
    this.aMao[1].x += -0.04 * arma;
    this.aMao[1].z += -0.06 * arma;
    if (e > 0) {
      this.rapidez = 40;
      const cam = this.cameraNoEsqueleto(T.a);
      const ombro = T.b.copy(this.R.RightArm);
      ombro.x += this.bacia.x; ombro.y += this.bacia.y - this.h0; ombro.z += this.bacia.z;
      const d = T.c.copy(cam).sub(ombro).normalize();
      const fim = this.doMundo(T.d.copy(ombro).addScaledVector(d, this.lBraco + this.lAnte), T.d);
      this.aMao[1].lerp(fim, e);
      this.aMaoDir[1].lerp(d, e).normalize();
      this.aPolegar[1].lerp(T.e.set(1, 0.3, 0).normalize(), e).normalize();
      this.aCotovelo[1].set(-0.8, -0.5, 0).normalize();
      this.aOmbro[1].x += 0.12 * e;
      this.aOmbro[1].y += 0.28 * e;
      this.aBacia.z += 0.06 * e;
    }
    if (this.telaOk && tp >= 1.09) {
      this.telaOk = false;
      this.telaBateu = true;
    }
    this.aExpr.grito = Math.max(solta * (1 - volta), this.aExpr.grito);
    if (tp > 1.6) this.aExpr.deboche = 1;
    // a câmera vem ao encontro do soco e depois volta
    let alvoDolly = 0;
    if (tp > 0.4 && tp < 1.7) alvoDolly = 0.72 * limitar((tp - 0.4) / 0.6, 0, 1);
    this.dolly = lerp(this.dolly, alvoDolly, 1 - Math.exp(-this.dt * 6));
  }

  /* A câmera no espaço do esqueleto (o nó do lutador e a escala do modelo). */
  cameraNoEsqueleto(out) {
    const s = this.modelo.scale.x;
    return out.copy(this.pontoDaCamera).sub(this.no.position).divideScalar(s);
  }

  /* ---------------------------------------------------- suavização e passos */
  suavizar(dt) {
    const T = this.t;
    const a = 1 - Math.exp(-dt * this.rapidez);
    const lento = 1 - Math.exp(-dt * 10);
    this.bacia.lerp(this.aBacia, a);
    this.baciaRot.lerp(this.aBaciaRot, lento);
    this.tronco.lerp(this.aTronco, a);
    this.cabeca.lerp(this.aCabeca, lento);
    // A coluna em onda: mola resolvida de forma implícita (estável).
    const alvo = T.a.copy(this.tronco).add(this.molaTronco);
    for (let i = 0; i < 3; i++) {
      const w = VERTEBRA_FREQ[i];
      const kk = w * w;
      const cc = 2 * VERTEBRA_AMORTECE[i] * w;
      const div = 1 + cc * dt + kk * dt * dt;
      const v = this.vertebraV[i];
      v.x = (v.x + (alvo.x - this.vertebra[i].x) * kk * dt) / div;
      v.y = (v.y + (alvo.y - this.vertebra[i].y) * kk * dt) / div;
      v.z = (v.z + (alvo.z - this.vertebra[i].z) * kk * dt) / div;
      this.vertebra[i].addScaledVector(v, dt);
    }
    for (let k = 0; k < 2; k++) {
      // As luvas da guarda são guardadas relativas ao centro do corpo.
      this.mao[k].lerp(this.noTronco(this.aMao[k], T.b), a);
      slerp3(this.maoDir[k], T.c.copy(this.aMaoDir[k]).normalize(), a, this.maoDir[k]).normalize();
      slerp3(this.polegar[k], T.c.copy(this.aPolegar[k]).normalize(), a, this.polegar[k]).normalize();
      this.cotovelo[k].lerp(this.aCotovelo[k], a).normalize();
      this.ombro[k].lerp(this.aOmbro[k], a);
      this.calcanhar[k] = lerp(this.calcanhar[k], this.aCalcanhar[k], a);
    }
  }

  peitoGiro(out) {
    return out.euler(this.baciaRot.x + this.tronco.x * 0.7, this.baciaRot.y + this.tronco.y, this.baciaRot.z + this.tronco.z);
  }

  peitoBase(out) {
    return out.set(this.bacia.x, this.R.Spine2.y + (this.bacia.y - this.h0), this.bacia.z);
  }

  /* Um ponto da guarda (medido a partir do peito) levado para o mundo. */
  noTronco(p, out) {
    const giro = this.peitoGiro(this.t.base3);
    const base = this.peitoBase(this.t.p);
    giro.aplicar(p, out);
    return out.add(base);
  }

  /* O caminho inverso: um ponto do mundo no espaço da guarda. */
  doMundo(p, out) {
    const giro = this.peitoGiro(this.t.base3);
    const base = this.peitoBase(this.t.p);
    out.copy(p).sub(base);
    return giro.aplicarInversa(out, out);
  }

  andar(dt) {
    if (this.caindo || this.queda > 0.01) return;
    const b = this.t.q;
    // Um pé de cada vez: o que está mais longe de onde devia estar.
    let pior = -1;
    let maior = LIMIAR_DO_PASSO;
    for (let k = 0; k < 2; k++) {
      if (this.passoT[k] >= 0) continue;
      const base = this.basePe(k, rascunhoV2());
      const d = Math.hypot(this.pe[k].x - base.x, this.pe[k].z - base.y);
      const giroErr = Math.abs(this.peGiro[k] - this.giroDoPe(k));
      if (d > maior || giroErr > 0.5) { maior = d; pior = k; }
    }
    const algumAndando = this.passoT[0] >= 0 || this.passoT[1] >= 0;
    if (pior >= 0 && !algumAndando) {
      const alvo = this.basePe(pior, rascunhoV2());
      // passo um pouco além, para o corpo ter para onde ir
      const sx = (alvo.x - this.pe[pior].x) * 0.15, sz = (alvo.y - this.pe[pior].z) * 0.15;
      this.passoT[pior] = 0;
      this.passoDe[pior].copy(this.pe[pior]);
      this.passoPara[pior].set(alvo.x + sx, this.tornozelo, alvo.y + sz);
      this.passoGiroDe[pior] = this.peGiro[pior];
      this.passoGiroPara[pior] = this.giroDoPe(pior);
    }
    const pressa = 1 + limitar(this.centroVel.length() * 1.2, 0, 1.2);
    for (let k = 0; k < 2; k++) {
      if (this.passoT[k] < 0) continue;
      this.passoT[k] += dt * pressa / TEMPO_DO_PASSO;
      const u = limitar(this.passoT[k], 0, 1);
      const liso = u * u * (3 - 2 * u);
      b.copy(this.passoDe[k]).lerp(this.passoPara[k], liso);
      b.y = this.tornozelo + Math.sin(u * Math.PI) * ALTURA_DO_PASSO;
      this.pe[k].copy(b);
      this.peGiro[k] = lerp(this.passoGiroDe[k], this.passoGiroPara[k], liso);
      if (this.passoT[k] >= 1) {
        this.passoT[k] = -1;
        this.pe[k].y = this.tornozelo;
      }
    }
  }

  /* ------------------------------------------------------------ a pose */
  /* DA COREOGRAFIA ATÉ CADA OSSO, uma vez por quadro. */
  resolver() {
    const G = this.G, O = this.O, R = this.R, K = this.k, T = this.t;
    const rotBacia = T.base1.eulerV(this.baciaRot);
    const bacia = T.a.copy(this.bacia);
    let deita = 0;
    const levantando = this.papel === "get_up" && this.levOk;
    for (let k = 0; k < 2; k++) {
      this.peComCalcanhar(k, this.rPe[k]);
      this.rTomba[k] = 0;
      this.rMao[k].copy(this.mao[k]);
      this.rCot[k].copy(this.cotovelo[k]);
    }
    if (levantando) {
      deita = this.poseLevantando();
      bacia.copy(this.rBacia);
      rotBacia.copiar(this.rRot);
    } else if (this.quedaVis > 0.001) {
      // A QUEDA É O CORPO TODO GIRANDO PARA TRÁS EM VOLTA DOS PÉS — o giro
      // vai nos alvos (bacia, luvas, cotovelos), e os pés ficam no chão.
      const q = this.quedaVis;
      const cai = ease(q, 2.2);
      const quique = Math.sin(limitar((q - 0.86) / 0.14, 0, 1) * Math.PI) * 0.06;
      const ang = -QUEDA_ANGULO * cai + quique;
      const piv = T.b.set((this.pe[0].x + this.pe[1].x) * 0.5, this.tornozelo, (this.pe[0].z + this.pe[1].z) * 0.5);
      const giro = T.base2.eixo(1, 0, 0, ang);
      giro.aplicar(bacia.sub(piv), bacia).add(piv);
      rotBacia.multiplicar(giro, rotBacia);
      for (let k = 0; k < 2; k++) {
        giro.aplicar(this.rMao[k].copy(this.mao[k]).sub(piv), this.rMao[k]).add(piv);
        giro.aplicar(this.cotovelo[k], this.rCot[k]);
        this.rTomba[k] = ang;
      }
      deita = limitar(q * 2.5, 0, 1);
      this.deitadoBacia.copy(bacia);
      this.deitadoAng = ang;
    } else {
      // ---- a bacia desce se alguma perna não alcança o chão.
      let falta = 0;
      for (let k = 0; k < 2; k++) {
        const quadril = rotBacia.aplicar(T.c.copy(R[OSSOS_DO_LADO.UpLeg[k]]).sub(R.Hips), T.c).add(bacia);
        const pe = this.rPe[k];
        const h = Math.hypot(quadril.x - pe.x, quadril.z - pe.z);
        const alcance = (this.lCoxa + this.lCanela) * 0.985;
        const alto = pe.y + Math.sqrt(Math.max(alcance * alcance - h * h, 0));
        falta = Math.max(falta, quadril.y - alto);
      }
      bacia.y -= falta;
    }
    G[K.Hips].copiar(rotBacia);
    O[K.Hips].copy(bacia);
    // ---- coluna
    let pai = K.Hips;
    let paiNome = "Hips";
    for (let i = 0; i < 3; i++) {
      const n = K.coluna[i];
      const nome = COLUNA[i];
      const v = this.vertebra[i];
      const q = T.base2.euler(v.x * COLUNA_PESO[i] + this.respiro * VERTEBRA_RESPIRA[i], v.y * COLUNA_PESO[i], v.z * COLUNA_PESO[i]);
      G[pai].aplicar(T.c.copy(R[nome]).sub(R[paiNome]), O[n]).add(O[pai]);
      G[n].multiplicar(G[pai], q);
      pai = n;
      paiNome = nome;
    }
    const cab = T.d.copy(this.cabeca).add(this.molaCab);
    const sp2 = K.Spine2;
    G[sp2].aplicar(T.c.copy(R.Neck).sub(R.Spine2), O[K.Neck]).add(O[sp2]);
    G[K.Neck].multiplicar(G[sp2], T.base2.euler(cab.x * 0.4, cab.y * 0.4, cab.z * 0.4));
    G[K.Neck].aplicar(T.c.copy(R.Head).sub(R.Neck), O[K.Head]).add(O[K.Neck]);
    G[K.Head].multiplicar(G[K.Neck], T.base2.euler(cab.x * 0.6, cab.y * 0.6, cab.z * 0.6));
    // ---- braços
    const junta = T.e, ponta = T.f, dobra = T.g;
    for (let k = 0; k < 2; k++) {
      const sg = ladoS(k);
      const iOmbro = K.Shoulder[k], iBraco = K.Arm[k], iAnte = K.ForeArm[k], iMao = K.Hand[k];
      const nOmbro = OSSOS_DO_LADO.Shoulder[k], nBraco = OSSOS_DO_LADO.Arm[k];
      const cl = G[iOmbro].multiplicar(G[sp2], T.base2.euler(0, -this.ombro[k].y * sg * 0.6, this.ombro[k].x * sg));
      G[sp2].aplicar(T.c.copy(R[nOmbro]).sub(R.Spine2), O[iOmbro]).add(O[sp2]);
      const raiz = cl.aplicar(T.h.copy(R[nBraco]).sub(R[nOmbro]), T.h).add(O[iOmbro]);
      const mao = T.j.copy(this.rMao[k]);
      let polo = this.rCot[k];
      if (levantando) {
        this.maoLevantando(k, mao);
        polo = this.rCot[k];
      } else if (deita > 0) {
        mao.lerp(this.maoDeitado(k, T.k), deita);
      }
      // A luva nunca entra na lona.
      mao.y = Math.max(mao.y, RAIO_DA_LUVA);
      ik(raiz, mao, this.lBraco, this.lAnte, polo, junta, ponta, dobra);
      this.girar(iBraco, T.l.subVectors(junta, raiz), dobra, G[iBraco]);
      O[iBraco].copy(raiz);
      const pol = this.polegar[k];
      this.girar(iAnte, T.l.subVectors(ponta, junta), pol, G[iAnte]);
      O[iAnte].copy(junta);
      // PUNHO RETO, como de boxeador: a luva segue o antebraço, só com
      // uma pitada da direção pedida.
      const ante = T.l.subVectors(ponta, junta).normalize();
      const dirMao = slerp3(ante, T.m.copy(this.maoDir[k]).normalize(), 0.12, T.n).normalize();
      this.girar(iMao, dirMao, pol, G[iMao]);
      O[iMao].copy(ponta);
    }
    // ---- pernas
    for (let k = 0; k < 2; k++) {
      const iCoxa = K.UpLeg[k], iPerna = K.Leg[k], iPe = K.Foot[k], iDedo = K.ToeBase[k];
      const nCoxa = OSSOS_DO_LADO.UpLeg[k];
      const raiz = rotBacia.aplicar(T.h.copy(R[nCoxa]).sub(R.Hips), T.h).add(bacia);
      const pe = this.rPe[k];
      const frentePe = T.j.set(Math.sin(this.peGiro[k]), 0, Math.cos(this.peGiro[k]));
      const cimaPe = T.k.set(0, 1, 0);
      const tomba = this.rTomba[k];
      if (Math.abs(tomba) > 0.0001) {
        // deitado, o pé acompanha a perna: dedos para cima
        const gp = T.base2.eixo(1, 0, 0, tomba);
        gp.aplicar(frentePe, frentePe);
        gp.aplicar(cimaPe, cimaPe);
      }
      // O JOELHO SOBRE A PONTA DO PÉ (um resto de abertura para fora).
      const polo = T.l.copy(frentePe);
      polo.x += 0.12 * ladoS(k);
      polo.normalize();
      ik(raiz, pe, this.lCoxa, this.lCanela, polo, junta, ponta, dobra);
      this.girar(iCoxa, T.m.subVectors(junta, raiz), dobra, G[iCoxa]);
      O[iCoxa].copy(raiz);
      this.girar(iPerna, T.m.subVectors(ponta, junta), dobra, G[iPerna]);
      O[iPerna].copy(junta);
      // O CALCANHAR SOBE GIRANDO NA PLANTA DO PÉ.
      const inc = this.incDoCalcanhar(k) * (1 - deita);
      const ci = Math.cos(inc), si = Math.sin(inc);
      const frente = T.m.copy(frentePe).multiplyScalar(ci).addScaledVector(cimaPe, -si);
      const cima = T.n.copy(cimaPe).multiplyScalar(ci).addScaledVector(frentePe, si);
      const dirPe = T.o.copy(frente).multiplyScalar(Math.cos(this.descePe)).addScaledVector(cima, -Math.sin(this.descePe));
      this.girar(iPe, dirPe, cima, G[iPe]);
      O[iPe].copy(ponta);
      // E OS DEDOS FICAM DEITADOS NA LONA.
      const dirDedo = T.o.copy(frentePe).multiplyScalar(Math.cos(this.desceDedo)).addScaledVector(cimaPe, -Math.sin(this.desceDedo));
      this.girar(iDedo, dirDedo, cimaPe, G[iDedo]);
      G[iPe].aplicar(T.c.copy(R[OSSOS_DO_LADO.ToeBase[k]]).sub(R[OSSOS_DO_LADO.Foot[k]]), O[iDedo]).add(ponta);
    }
    // ---- NADA ATRAVESSA A LONA: mede sola, calcanhar (e, deitado, bacia,
    // costas e cabeça) e sobe o corpo se algum passou.
    let fundo = Infinity;
    for (let k = 0; k < 2; k++) {
      const iPe = K.Foot[k], iDedo = K.ToeBase[k];
      const pontaDedo = G[iDedo].aplicar(T.c.copy(R[OSSOS_DO_LADO.Toe_End[k]]).sub(R[OSSOS_DO_LADO.ToeBase[k]]), T.c).add(O[iDedo]);
      fundo = Math.min(fundo, pontaDedo.y - this.solaPonta);
      fundo = Math.min(fundo, O[iDedo].y - this.solaPlanta);
      const calc = G[iPe].aplicar(this.calcanharOfs, T.c).add(O[iPe]);
      fundo = Math.min(fundo, calc.y);
    }
    if (deita > 0 || levantando) {
      fundo = Math.min(fundo, bacia.y - RAIO_DA_BACIA);
      fundo = Math.min(fundo, O[sp2].y - RAIO_DAS_COSTAS);
      const topo = G[K.Head].aplicar(T.c.copy(R.HeadTop_End).sub(R.Head).multiplyScalar(0.5), T.c).add(O[K.Head]);
      fundo = Math.min(fundo, topo.y - RAIO_DA_CABECA);
    }
    if (fundo < 0) bacia.y -= fundo;
    // ---- grava no esqueleto (giro local de cada osso; a posição é a de
    // repouso, menos a bacia, que é a do quadro)
    const local = T.base2;
    for (let k = 0; k < this.ossos.length; k++) {
      const p = this.pais[k];
      const osso = this.ossos[k];
      if (!this.comandado[k]) {
        if (p >= 0) G[k].copiar(G[p]); else G[k].identidade();
        if (!this.gravouFixos) {
          osso.quaternion.identity();
          osso.position.copy(this.repousoOrigem[k]);
        }
        continue;
      }
      if (p >= 0) local.transpostaVezes(G[p], G[k]); else local.copiar(G[k]);
      local.quaternion(osso.quaternion);
      osso.position.copy(k === K.Hips ? bacia : this.repousoOrigem[k]);
    }
    this.gravouFixos = true;
  }

  /* Base global de um osso: leva a direção de repouso para `dir` e o eixo
     secundário de repouso para `sec`. */
  girar(indice, dir, sec, out) {
    const r = rascunho();
    ortonormal(dir, sec, r.b1);
    const repouso = this.repousoT[indice];
    return repouso ? out.multiplicar(r.b1, repouso) : out.copiar(r.b1);
  }

  incDoCalcanhar(k) { return CALCANHAR_MAX * limitar(this.calcanhar[k], 0, 1); }

  /* Onde o TORNOZELO fica com o calcanhar levantado: o pé gira em volta
     da planta, que continua no chão. */
  peComCalcanhar(k, out) {
    const p = this.pe[k];
    const inc = this.incDoCalcanhar(k);
    out.copy(p);
    if (inc <= 0.0001) return out;
    const fx = Math.sin(this.peGiro[k]), fz = Math.cos(this.peGiro[k]);
    const a = this.peL * Math.cos(this.descePe), b = this.peL * Math.sin(this.descePe);
    const c = this.peL * Math.cos(this.descePe + inc), d = this.peL * Math.sin(this.descePe + inc);
    out.x += fx * (a - c);
    out.z += fz * (a - c);
    out.y += -b + d;
    return out;
  }

  maoDeitado(k, out) {
    const s = ladoS(k);
    const sp2 = this.k.Spine2;
    this.G[sp2].aplicar(out.set(0.50 * s, 0.10, -0.12), out);
    return out.add(this.O[sp2]);
  }

  /* ------------------------------------------------------------ levantar */
  levantarG() { return limitar(this.tempoNoPapel / TEMPO_LEVANTAR, 0, 1); }

  /* Em que trecho do levantar estamos: [índice do trecho, fração suave]. */
  trecho(g) {
    const out = this.trechoAtual;
    for (let i = 1; i < LEVANTAR_TEMPOS.length; i++) {
      const t1 = LEVANTAR_TEMPOS[i];
      if (g <= t1 || i === LEVANTAR_TEMPOS.length - 1) {
        const t0 = LEVANTAR_TEMPOS[i - 1];
        const u = limitar((g - t0) / Math.max(t1 - t0, 0.001), 0, 1);
        out[0] = i - 1;
        out[1] = u * u * (3 - 2 * u);
        return out;
      }
    }
    out[0] = 3;
    out[1] = 1;
    return out;
  }

  /* Fotografa a pose de deitado e escolhe onde ele vai ficar de pé. */
  comecarALevantar() {
    this.levOk = true;
    this.levBacia.copy(this.deitadoBacia);
    this.levAng = this.deitadoAng;
    for (let k = 0; k < 2; k++) this.levPe[k].copy(this.pe[k]);
    // De pé ele fica um passo atrás de onde estavam os pés.
    const mx = (this.pe[0].x + this.pe[1].x) * 0.5, mz = (this.pe[0].z + this.pe[1].z) * 0.5;
    this.centro.set(mx - (PE_FRENTE[0] + PE_TRAS[0]) * 0.5, mz - 0.40 - (PE_FRENTE[1] + PE_TRAS[1]) * 0.5);
    this.centroAlvo.copy(this.centro);
    this.centroVel.set(0, 0);
  }

  /* A pose do levantar: escreve bacia, giro e pés; devolve quanto os
     braços ainda estão "deitados". */
  poseLevantando() {
    const g = this.levantarG();
    const [i, u] = this.trecho(g);
    const c = this.centro;
    const chaves = this.chavesBacia;
    chaves[0].copy(this.levBacia);
    chaves[1].copy(this.levBacia).y += 0.02;
    chaves[2].set(c.x, 0.16, c.y - 0.34);
    chaves[3].set(c.x, 0.47, c.y - 0.04);
    chaves[4].copy(this.bacia);
    this.rBacia.copy(chaves[i]).lerp(chaves[i + 1], u);
    const tombo = lerp(i === 0 ? this.levAng : LEVANTAR_TOMBO[i], LEVANTAR_TOMBO[i + 1], u);
    const b = this.t.base3;
    this.rRot.eixo(1, 0, 0, tombo).multiplicar(this.rRot, b.euler(this.baciaRot.x * (i >= 3 ? 1 : 0) * u, this.baciaRot.y, this.baciaRot.z));
    // Os pés: até sentar ficam onde caíram (dedos para cima); depois vêm
    // por baixo do corpo e plantam na base da guarda.
    const base = rascunhoV2();
    for (let k = 0; k < 2; k++) {
      this.basePe(k, base);
      if (i <= 0) {
        this.rPe[k].copy(this.levPe[k]);
        this.rTomba[k] = this.levAng;
      } else if (i === 1) {
        this.rPe[k].copy(this.levPe[k]).lerp(this.t.q.set(base.x, this.tornozelo, base.y), u);
        this.rPe[k].y += Math.sin(u * Math.PI) * 0.05;
        this.rTomba[k] = lerp(this.levAng, 0, u);
      } else {
        this.rPe[k].set(base.x, this.tornozelo, base.y);
        this.pe[k].copy(this.rPe[k]);
        this.peGiro[k] = this.giroDoPe(k);
        this.passoT[k] = -1;
      }
    }
    return 1 - limitar(g / LEVANTAR_TEMPOS[1], 0, 1);
  }

  /* As luvas no levantar: largadas → apoiadas atrás → nos joelhos → guarda. */
  maoLevantando(k, out) {
    const [i, u] = this.trecho(this.levantarG());
    const s = ladoS(k);
    const b = this.O[this.k.Hips];
    const giro = this.t.base3.eixo(0, 1, 0, this.baciaRot.y);
    const chaves = this.chavesMao;
    this.maoDeitado(k, chaves[0]);
    giro.aplicar(chaves[1].set(0.26 * s, 0, -0.20), chaves[1]);
    chaves[1].x += b.x; chaves[1].y += RAIO_DA_LUVA; chaves[1].z += b.z;
    giro.aplicar(chaves[2].set(0.17 * s, 0.26, 0.30), chaves[2]).add(b);
    giro.aplicar(chaves[3].set(0.15 * s, 0.02, 0.24), chaves[3]).add(b);
    chaves[4].copy(this.mao[k]);
    const cotovelos = this.chavesCot;
    cotovelos[0].copy(this.cotovelo[k]);
    cotovelos[1].set(0.6 * s, -0.2, -0.7).normalize();
    cotovelos[2].set(0.7 * s, -0.5, -0.2).normalize();
    cotovelos[3].set(0.7 * s, -0.4, -0.3).normalize();
    cotovelos[4].copy(this.cotovelo[k]);
    this.rCot[k].copy(cotovelos[i]).lerp(cotovelos[i + 1], u).normalize();
    return out.copy(chaves[i]).lerp(chaves[i + 1], u);
  }

  /* ------------------------------------------------------ rosto e tinta */
  rosto(dt) {
    if (!this.pele) return;
    const a = 1 - Math.exp(-dt * MESCLA_EXPR);
    const pesos = this.pele.morphTargetInfluences;
    for (const nome of EXPRESSOES) {
      const indice = this.expr[nome];
      if (indice === undefined) continue;
      const alvo = limitar(this.aExpr[nome] || 0, 0, 1);
      const antes = this.exprValor[nome];
      let v = lerp(antes, alvo, a);
      if (v < 0.002 && alvo <= 0) v = 0;
      if (Math.abs(v - antes) > 0.0005 || (v === 0 && antes !== 0)) {
        this.exprValor[nome] = v;
        pesos[indice] = v;
      }
    }
  }

  /* A QUEDA: quanto do tombo já aconteceu (o giro vai nos alvos). */
  raiz() {
    const alvo = limitar(this.queda, 0, 1);
    if (alvo > this.quedaVis) this.quedaVis = Math.min(alvo, this.quedaVis + this.dt * 2.4);
    else this.quedaVis = alvo;
    if (this.papel === "get_up" && !this.levOk && this.caindo) this.comecarALevantar();
    else if (this.papel !== "get_up" && this.levOk) this.levOk = false;
  }

  pintar() {
    if (!this.pronto || !this.montarPose) return;
    // O clarão do golpe é um calor na pele, não um lençol branco.
    const brilho = limitar(this.clarao, 0, 1) * 0.28;
    if (Math.abs(brilho - this.claraoPintado) > 0.004 || (brilho === 0 && this.claraoPintado !== 0)) {
      this.claraoPintado = brilho;
      for (const m of this.matsPadrao) m.emissive.setRGB(1.0 * brilho, 0.62 * brilho, 0.45 * brilho);
    }
    if (this.matPele) {
      // O estrago aparece: a pele fica mais vermelha com o dano.
      const d = limitar(this.dano, 0, 1);
      this.matPele.color.setRGB(1.0, 1.0 - 0.10 * d, 1.0 - 0.14 * d);
    }
  }

  destruir() {
    const texturas = new Set();
    for (const m of this.matsPadrao) {
      if (m.map) texturas.add(m.map);
      if (m.normalMap) texturas.add(m.normalMap);
      m.dispose();
    }
    for (const t of texturas) t.dispose();
    for (const mi of this.malhas) mi.geometry.dispose();
    if (this.malhas[0] && this.malhas[0].skeleton) this.malhas[0].skeleton.dispose();
  }
}

let RASCUNHO_V2 = null;
function rascunhoV2() {
  if (!RASCUNHO_V2) RASCUNHO_V2 = new THREE.Vector2();
  return RASCUNHO_V2;
}

/* O RECORTE DE LUZ do material do Godot (`rim`): uma borda clara na
   silhueta, que descola o corpo do fundo. Mesma conta de lá — a força cai
   com a aspereza e o tom mistura o branco com a cor da peça —, somada à
   luz da lâmpada principal. */
function instalarRecorte(material, recorte, tom) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uRecorte = { value: recorte };
    shader.uniforms.uRecorteTom = { value: tom };
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform float uRecorte;\nuniform float uRecorteTom;")
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
#if NUM_DIR_LIGHTS > 0
{
  float nvRecorte = max(0.0, dot(geometryNormal, geometryViewDir));
  float luzRecorte = pow(1.0 - nvRecorte, max(0.0, (1.0 - roughnessFactor) * 16.0));
  reflectedLight.directDiffuse += luzRecorte * uRecorte * mix(vec3(1.0), diffuseColor.rgb, uRecorteTom) * directionalLights[0].color * RECIPROCAL_PI;
}
#endif`);
  };
  material.customProgramCacheKey = () => "recorte";
}
/* ======================================================================
   A ARENA — scripts/arena/arena3d.gd (e particulas3d.gd)

   Build 119: a arena ocupa a TELA INTEIRA (1080 x 1920 lá, 540 x 960
   aqui — a mesma proporção). Fundo, lona e luzes são texturas prontas em
   materiais sem luz; cordas, postes e o lutador recebem luz de verdade.
   ====================================================================== */

/* A tela lógica do jogo e o quadro em que o enquadramento foi acertado
   (ArenaQuadro.QUADRO_DO_LUTADOR: 1080 x 1540, a 116 px do alto). */
const TELA_LOGICA_Y = 1920;
const QUADRO_DO_LUTADOR_Y = 116;
const QUADRO_DO_LUTADOR_ALTURA = 1540;
/* A força da luz principal (a do refletor de cima). */
const LUZ_CHAVE = 1.75;
/* Quanto da altura da janela o lutador em pé ocupa, quanto a câmera fica
   acima da mira e a abertura vertical da lente no quadro de 1540 px. */
const OCUPACAO_DO_LUTADOR = 0.54;
const CAMERA_ACIMA_DA_MIRA = 0.26;
const CAMPO_DE_VISAO = 50.0;
/* O ringue (metros): a meia largura põe os postes de trás nas bordas. */
const MEIO_RINGUE = 1.6;
const ALTURAS_DAS_CORDAS = [0.42, 0.82, 1.22];
const PISO_DO_LUTADOR = 0.004;
const COR_FUNDO_3D = 0x07051a;
/* A torcida: folga em cima de cada fileira (para quem pula) e onde começa
   o encosto parado; as quatro velocidades de cada movimento (voltas/s). */
const FOLGA_DA_TORCIDA = 0.12;
const ASSENTO_DA_TORCIDA = 0.80;
const RITMO_RESPIRA = [0.25, 0.32, 0.40, 0.48];
const RITMO_PULO = [0.50, 0.65, 0.80, 0.95];
const RITMO_BALANCO = [0.17, 0.22, 0.27, 0.33];
const RITMO_BRACO = [0.38, 0.48, 0.58, 0.70];
/* A câmera de transmissão: a mola que ela persegue, o arco lento na
   espera e o "soco de câmera" (o campo de visão fecha e volta). */
const CAMERA_MOLA = 7.5;
const ARCO = 0.11;
const ZOOM_DO_SOCO = 0.10;
/* As partículas da placa de vídeo: vida das estrelas do soco e da poeira
   da lona, e a fração do perfil da TV Box (Perfil.PARTICULAS_3D). */
const IMPACTO_VIDA = 0.75;
const POEIRA_VIDA = 1.35;
const PARTICULAS_3D = 0.5;
/* A poça de luz quente que o refletor faz na lona, em volta do lutador. */
const COR_DO_FOCO = [0.62, 0.46, 0.34];

/* A TELA INTEIRA COM O MESMO LUTADOR: a imagem cresceu de 1540 para 1920
   px de altura sem mudar a largura — a lente abre na vertical na mesma
   proporção e a câmera inclina um pouco para baixo. */
function campoDaTela() {
  const meia = Math.tan((CAMPO_DE_VISAO * Math.PI / 180) * 0.5);
  return (2 * Math.atan(meia * TELA_LOGICA_Y / QUADRO_DO_LUTADOR_ALTURA)) * 180 / Math.PI;
}

function inclinacaoDaTela() {
  const focal = QUADRO_DO_LUTADOR_ALTURA * 0.5 / Math.tan((CAMPO_DE_VISAO * Math.PI / 180) * 0.5);
  const abaixo = TELA_LOGICA_Y * 0.5 - (QUADRO_DO_LUTADOR_Y + QUADRO_DO_LUTADOR_ALTURA * 0.5);
  return Math.atan(abaixo / focal);
}

/* ---------------------------------------------------------------------
   OS SHADERS DA ARENA, os mesmos de lá (GLSL do Godot passado a limpo).
   O UV do Godot tem o y para baixo: os vértices entregam `vUv` já assim.
   --------------------------------------------------------------------- */
const VERTICE_UV = `
varying vec2 vUv;
void main() {
  vUv = vec2(uv.x, 1.0 - uv.y);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

/* A TORCIDA (SHADER_TORCIDA_SEGURA): cada coluna é uma pessoa que
   respira, balança, pula e levanta os braços em onda; o encosto da
   arquibancada fica parado; os fachos rosa e azul acendem quem está neles. */
const PIXEL_TORCIDA = `
uniform sampler2D baixo;
uniform sampler2D cima;
uniform float agito;
uniform float acende;
uniform float colunas;
uniform float v0;
uniform float v1;
uniform float semente;
uniform float folga;
uniform float assento;
uniform vec4 f_respira;
uniform vec4 f_pulo;
uniform vec4 f_balanco;
uniform vec4 f_braco;
uniform float f_ola;
uniform float tique;
uniform vec2 fachos;
uniform float fachos_forca;
varying vec2 vUv;
vec4 escolhe(float r) {
  float a = step(0.25, r);
  float b = step(0.50, r);
  float c = step(0.75, r);
  return vec4(1.0 - a, a - b, b - c, c);
}
void main() {
  vec2 UV = vUv;
  float col = floor(UV.x * colunas);
  float r = fract(sin(col * 0.731 + semente * 1.37) * 47.53);
  float r2 = fract(sin(col * 1.279 + semente * 0.71) * 31.17);
  float vida = 0.60 + agito * 0.40;
  float respira = sin(6.2831 * (dot(f_respira, escolhe(r2)) + r)) * 0.012 * vida;
  float pulo = max(0.0, sin(6.2831 * (dot(f_pulo, escolhe(r)) + r)));
  pulo *= step(0.35 - agito * 0.3, r2) * (0.03 + 0.07 * agito);
  float balanco = sin(6.2831 * (dot(f_balanco, escolhe(fract(r * 3.7))) + r * 1.43)) * 0.035 * vida;
  float dentro = fract(UV.x * colunas);
  float yb = UV.y * (1.0 + folga) - folga;
  float parado = step(assento, yb);
  float anda = smoothstep(0.0, 0.08, dentro) * (1.0 - smoothstep(0.92, 1.0, dentro)) * (1.0 - parado);
  float x = clamp(dentro + balanco * anda, 0.0, 1.0);
  float y = mix(min(yb + (respira + pulo) * anda, assento - 0.004), yb, parado);
  vec2 uv = vec2((col + x) / colunas, mix(v0, v1, clamp(y, 0.004, 0.996)));
  vec4 a = texture2D(baixo, uv);
  vec4 b = texture2D(cima, uv);
  float ola = 0.5 + 0.5 * sin(UV.x * 7.0 - 6.2831 * f_ola + semente);
  float braco = 0.5 + 0.5 * sin(6.2831 * (dot(f_braco, escolhe(r2)) + r * 1.91));
  float mao = step(0.55, braco * (0.35 + 0.65 * ola) + agito * 0.5) * step(0.25 - agito * 0.2, r);
  vec4 c = mix(a, b, mao);
  c.a *= step(0.0, y);
  float celular = step(0.985, fract(sin(col * 1.2989 + fract((tique + floor(r * 7.0)) * 0.137) * 37.0 + semente) * 53.71)) * c.a;
  vec2 celula = vec2(x - 0.5, (y - 0.30) * 5.0);
  celular *= (1.0 - smoothstep(0.04, 0.12, length(celula))) * (1.0 - parado);
  float l1 = 1.0 - smoothstep(0.0, 0.09, abs(UV.x - fachos.x));
  float l2 = 1.0 - smoothstep(0.0, 0.09, abs(UV.x - fachos.y));
  vec3 luz = (vec3(1.0, 0.42, 0.85) * l1 + vec3(0.42, 0.85, 1.0) * l2) * fachos_forca;
  gl_FragColor = vec4(c.rgb * (acende * (1.0 + agito * 0.35) + luz) + vec3(0.9, 0.95, 1.0) * celular * 1.2,
    c.a * (0.86 + 0.14 * agito));
}`;

/* A PAREDE DO GINÁSIO (SHADER_FUNDO): o telão de LED rola devagar e
   pisca com a festa; os mesmos dois fachos passam por ela. */
const PIXEL_FUNDO = `
uniform sampler2D tex;
uniform float tempo;
uniform float acende;
uniform float agito;
uniform float rolagem;
uniform vec2 fachos;
uniform float fachos_forca;
varying vec2 vUv;
void main() {
  vec2 uv = vUv;
  float faixa = step(0.155, uv.y) * step(uv.y, 0.265);
  uv.x = fract(uv.x + faixa * rolagem);
  vec3 c = texture2D(tex, uv).rgb;
  float pisca = 1.0 + faixa * agito * 0.35 * sin(tempo * 9.0);
  float l1 = 1.0 - smoothstep(0.0, 0.07, abs(vUv.x - fachos.x));
  float l2 = 1.0 - smoothstep(0.0, 0.07, abs(vUv.x - fachos.y));
  vec3 luz = (vec3(1.0, 0.42, 0.85) * l1 + vec3(0.42, 0.85, 1.0) * l2) * fachos_forca * 0.7;
  gl_FragColor = vec4(c * (acende * pisca + luz), 1.0);
}`;

/* A SAIA DO RINGUE (SHADER_SAIA): o letreiro de LED rola devagar. */
const PIXEL_SAIA = `
uniform sampler2D tex;
uniform float acende;
uniform float rolagem;
varying vec2 vUv;
void main() {
  vec2 uv = vec2(fract(vUv.x * 1.6 + rolagem), vUv.y);
  gl_FragColor = vec4(texture2D(tex, uv).rgb * acende, 1.0);
}`;

/* A TRELIÇA de alumínio, vazada no próprio material (SHADER_TRELICA). */
const PIXEL_TRELICA = `
uniform vec3 cor;
uniform float gomos;
varying vec2 vUv;
void main() {
  float u = fract(vUv.x * gomos);
  float v = vUv.y;
  float tubo = step(v, 0.14) + step(0.86, v);
  float d1 = abs(v - u);
  float d2 = abs(v - (1.0 - u));
  float zig = step(min(d1, d2), 0.07);
  float coluna = step(u, 0.05);
  if (clamp(tubo + zig + coluna, 0.0, 1.0) < 0.5) discard;
  gl_FragColor = vec4(cor * (1.25 - 0.5 * v), 1.0);
}`;

/* OS FACHOS DOS REFLETORES (SHADER_FACHO): a conta toda no vértice —
   mais forte perto da lâmpada, some na borda e no chão. */
const VERTICE_FACHO = `
uniform float vivo;
uniform float relogio;
attribute vec4 aCor;
attribute vec2 aCone;
varying vec4 vCor;
void main() {
  float t = aCone.x;
  float i = aCone.y;
  vec4 p4 = modelViewMatrix * vec4(position, 1.0);
  vec3 n = normalize((modelViewMatrix * vec4(normal, 0.0)).xyz);
  float meio = pow(abs(dot(n, normalize(-p4.xyz))), 1.7);
  float onda = 0.92 + 0.08 * sin(relogio * (0.7 + 0.13 * i) + i);
  float a = aCor.a * vivo * onda * meio * (0.18 + 0.82 * t * t) * smoothstep(0.0, 0.22, t) * 2.0;
  vCor = vec4(aCor.rgb, clamp(a, 0.0, 1.0));
  gl_Position = projectionMatrix * p4;
}`;
const PIXEL_COR = `
varying vec4 vCor;
void main() { gl_FragColor = vCor; }`;

/* AS PARTÍCULAS DA PLACA DE VÍDEO (particulas3d.gd): cada efeito é uma
   malha só, com sorteios nos vértices, e o vértice calcula onde cada
   partícula está a partir do tempo (e a vira para a câmera). */
const VERTICE_PARTICULAS = `
uniform float tempo;
uniform float semente;
uniform float quantos;
uniform float vida;
uniform float vida_aleatoria;
uniform vec3 dir_base;
uniform vec3 eixo_u;
uniform vec3 eixo_v;
uniform float abertura;
uniform float vel_max;
uniform float vel_min;
uniform float amort;
uniform vec3 grav;
uniform float esfera;
uniform vec3 caixa;
uniform float tam;
uniform float esc_min;
uniform float esc_max;
uniform vec4 cor_ini;
uniform vec4 cor_fim;
uniform float continuo;
uniform float flashes;
uniform float relogio;
uniform float festa;
attribute vec4 aSorteio;
attribute vec2 aUv2;
varying vec4 vCor;
varying vec2 vUv;
void main() {
  vec2 canto = uv;
  vec3 s = position;
  vec3 centro;
  float esc;
  vec4 cor;
  if (flashes > 0.5) {
    centro = s;
    float fase = aUv2.x;
    float base = max(0.0, sin(relogio * 1.7 + fase) - 0.93) * 12.0;
    float ag = festa * max(0.0, sin(fase * 3.1 + relogio * 22.0));
    float a = clamp(base + ag, 0.0, 1.0);
    cor = vec4(a, a * 0.97, a * 0.92, a);
    esc = 1.0;
  } else {
    float s_a = fract(s.x + semente);
    float s_b = fract(s.y + semente * 1.6180);
    float s_v = fract(s.z + semente * 2.4142);
    float s_vida = fract(aSorteio.r + semente * 3.3028);
    float s_tam = fract(aSorteio.g + semente * 4.2361);
    float s_px = fract(aSorteio.b + semente * 5.1231);
    float s_py = fract(aSorteio.a + semente * 6.0827);
    float s_pz = fract(aUv2.x + semente * 7.0711);
    float indice = aUv2.y;
    float t = tempo;
    float vida_p = vida * (1.0 - vida_aleatoria * s_vida);
    float aparece = step(indice, quantos - 0.0001);
    if (continuo > 0.5) {
      float fase = s_vida * vida;
      float total = tempo + vida - fase;
      float volta = floor(total / vida);
      t = total - volta * vida;
      s_px = fract(s_px + volta * 0.7549);
      s_py = fract(s_py + volta * 0.5698);
      s_pz = fract(s_pz + volta * 0.6180);
      s_a = fract(s_a + volta * 0.4142);
      vida_p = vida;
    }
    aparece *= step(t, vida_p);
    float x = clamp(t / vida_p, 0.0, 1.0);
    float th = s_a * abertura;
    float ph = s_b * 6.2832;
    vec3 dir = dir_base * cos(th) + (eixo_u * cos(ph) + eixo_v * sin(ph)) * sin(th);
    float v0 = vel_max * mix(vel_min, 1.0, s_v);
    float d = amort * mix(0.5, 1.0, s_tam);
    float tr = t;
    if (d > 0.0) tr = min(t, v0 / d);
    float dist = v0 * tr - 0.5 * d * tr * tr;
    vec3 origem = (vec3(s_px, s_py, s_pz) * 2.0 - 1.0) * caixa;
    vec3 n = normalize(vec3(s_px, s_py, s_pz) * 2.0 - 1.0 + vec3(0.0001));
    origem += n * esfera * s_v;
    centro = origem + dir * dist + 0.5 * grav * t * t;
    esc = mix(esc_min, esc_max, s_tam) * aparece;
    cor = mix(cor_ini, cor_fim, x);
    cor.a *= aparece;
  }
  vec4 vista = modelViewMatrix * vec4(centro, 1.0);
  vista.xy += (canto - 0.5) * tam * esc;
  gl_Position = projectionMatrix * vista;
  vCor = cor;
  vUv = uv;
}`;
const PIXEL_PARTICULAS = `
uniform sampler2D textura;
varying vec4 vCor;
varying vec2 vUv;
void main() {
  vec4 t = texture2D(textura, vUv);
  gl_FragColor = vec4(t.rgb * vCor.rgb, t.a * vCor.a);
}`;

/* ---------------------------------------------------------------------
   VÁRIAS PEÇAS, UMA MALHA (Arena3D._juntar): peças que dividem o material
   viram uma malha só, já no lugar, com a cor de cada uma nos vértices.
   `pecas`: [{ geo, matriz, cor: [r, g, b, a], cone: [meia altura, número] }]
   --------------------------------------------------------------------- */
function juntar(pecas) {
  let total = 0, totalIdx = 0;
  const comCor = pecas.some((p) => p.cor);
  const comCone = pecas.some((p) => p.cone);
  for (const p of pecas) {
    total += p.geo.attributes.position.count;
    totalIdx += p.geo.index ? p.geo.index.count : p.geo.attributes.position.count;
  }
  const pos = new Float32Array(total * 3);
  const nor = new Float32Array(total * 3);
  const uv = new Float32Array(total * 2);
  const cor = comCor ? new Float32Array(total * 4) : null;
  const cone = comCone ? new Float32Array(total * 2) : null;
  const idx = total > 65535 ? new Uint32Array(totalIdx) : new Uint16Array(totalIdx);
  const v = new THREE.Vector3();
  const nm = new THREE.Matrix3();
  let base = 0, bi = 0;
  for (const p of pecas) {
    const g = p.geo;
    const P = g.attributes.position, N = g.attributes.normal, U = g.attributes.uv;
    nm.getNormalMatrix(p.matriz);
    for (let k = 0; k < P.count; k++) {
      v.fromBufferAttribute(P, k);
      const yLocal = v.y;
      v.applyMatrix4(p.matriz);
      pos[(base + k) * 3] = v.x; pos[(base + k) * 3 + 1] = v.y; pos[(base + k) * 3 + 2] = v.z;
      v.fromBufferAttribute(N, k).applyMatrix3(nm).normalize();
      nor[(base + k) * 3] = v.x; nor[(base + k) * 3 + 1] = v.y; nor[(base + k) * 3 + 2] = v.z;
      if (U) { uv[(base + k) * 2] = U.getX(k); uv[(base + k) * 2 + 1] = U.getY(k); }
      if (cor) {
        const c = p.cor || [1, 1, 1, 1];
        cor.set(c, (base + k) * 4);
      }
      if (cone) {
        const cn = p.cone || [1, 0];
        cone[(base + k) * 2] = limitar(yLocal / cn[0] * 0.5 + 0.5, 0, 1);
        cone[(base + k) * 2 + 1] = cn[1];
      }
    }
    if (g.index) for (let i = 0; i < g.index.count; i++) idx[bi++] = base + g.index.getX(i);
    else for (let i = 0; i < P.count; i++) idx[bi++] = base + i;
    base += P.count;
    g.dispose();
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  if (cor) geo.setAttribute("aCor", new THREE.BufferAttribute(cor, 4));
  if (cone) geo.setAttribute("aCone", new THREE.BufferAttribute(cone, 2));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.computeBoundingSphere();
  return geo;
}

/* Um giro cujo eixo Y aponta de `alvo` para `de` (Arena3D._giro_para). */
function giroPara(de, alvo) {
  const y = new THREE.Vector3().subVectors(de, alvo).normalize();
  const ref = Math.abs(y.z) < 0.95 ? new THREE.Vector3(0, 0, -1) : new THREE.Vector3(1, 0, 0);
  const x = new THREE.Vector3().crossVectors(ref, y).normalize();
  const z = new THREE.Vector3().crossVectors(x, y).normalize();
  return new THREE.Matrix4().makeBasis(x, y, z);
}

function matriz(posicao, giro = null) {
  const m = giro ? giro.clone() : new THREE.Matrix4();
  m.setPosition(posicao);
  return m;
}

/* A cor de uma peça para `juntar`, crua, com o alfa. */
function corDaPeca(hex, alfa = 1) {
  const c = cru(hex);
  return [c.r, c.g, c.b, alfa];
}

/* Color.lightened do Godot. */
function clareada(hex, quanto) {
  const c = cru(hex);
  return [c.r + (1 - c.r) * quanto, c.g + (1 - c.g) * quanto, c.b + (1 - c.b) * quanto, 1];
}

/* Mancha redonda e macia (branco no centro, some na borda): a sombra de
   contato, o foco da lona e a poeira. Pintada pixel a pixel uma vez. */
function manchaRedonda() {
  const lado = 128;
  const dados = new Uint8Array(lado * lado * 4);
  for (let y = 0; y < lado; y++) {
    for (let x = 0; x < lado; x++) {
      const d = Math.hypot(x + 0.5 - lado * 0.5, y + 0.5 - lado * 0.5) / (lado * 0.5);
      let a = 0;
      if (d < 0.45) a = lerp(1, 0.55, d / 0.45);
      else if (d < 1) a = lerp(0.55, 0, (d - 0.45) / 0.55);
      const i = (y * lado + x) * 4;
      dados[i] = 255; dados[i + 1] = 255; dados[i + 2] = 255; dados[i + 3] = Math.round(a * 255);
    }
  }
  const t = new THREE.DataTexture(dados, lado, lado, THREE.RGBAFormat);
  t.colorSpace = THREE.NoColorSpace;
  t.magFilter = THREE.LinearFilter;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.generateMipmaps = true;
  t.needsUpdate = true;
  return t;
}

/* ---------------------------------------------------------------------
   PARTÍCULAS (particulas3d.gd): explosão (`disparar`), contínuo (a poeira
   no ar) e flashes da plateia (pontos fixos que piscam).
   --------------------------------------------------------------------- */
class Particulas3D {
  constructor(textura, soma) {
    this.tempo = 0;
    this.ativo = false;
    this.dura = 1;
    this.continuo = false;
    this.vida = 1;
    this.uniforms = {
      textura: { value: textura }, tempo: { value: 0 }, semente: { value: 0 }, quantos: { value: 1 },
      vida: { value: 1 }, vida_aleatoria: { value: 0 }, dir_base: { value: new THREE.Vector3(0, 1, 0) },
      eixo_u: { value: new THREE.Vector3(1, 0, 0) }, eixo_v: { value: new THREE.Vector3(0, 0, 1) },
      abertura: { value: Math.PI }, vel_max: { value: 1 }, vel_min: { value: 0.3 }, amort: { value: 0 },
      grav: { value: new THREE.Vector3() }, esfera: { value: 0 }, caixa: { value: new THREE.Vector3() },
      tam: { value: 0.1 }, esc_min: { value: 1 }, esc_max: { value: 1 },
      cor_ini: { value: new THREE.Vector4(1, 1, 1, 1) }, cor_fim: { value: new THREE.Vector4(1, 1, 1, 0) },
      continuo: { value: 0 }, flashes: { value: 0 }, relogio: { value: 0 }, festa: { value: 0 },
    };
    this.material = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: VERTICE_PARTICULAS,
      fragmentShader: PIXEL_PARTICULAS,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: soma ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
  }

  static malha(posicoes, sorteios, uv2) {
    const n = posicoes.length / 3;
    const pos = new Float32Array(n * 12), sort = new Float32Array(n * 16), u2 = new Float32Array(n * 8), uv = new Float32Array(n * 8);
    const idx = new Uint16Array(n * 6);
    const cantos = [0, 1, 1, 1, 1, 0, 0, 0];
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < 4; j++) {
        const v = i * 4 + j;
        pos.set([posicoes[i * 3], posicoes[i * 3 + 1], posicoes[i * 3 + 2]], v * 3);
        sort.set([sorteios[i * 4], sorteios[i * 4 + 1], sorteios[i * 4 + 2], sorteios[i * 4 + 3]], v * 4);
        u2.set([uv2[i * 2], uv2[i * 2 + 1]], v * 2);
        uv.set([cantos[j * 2], cantos[j * 2 + 1]], v * 2);
      }
      const b = i * 4;
      idx.set([b, b + 1, b + 2, b, b + 2, b + 3], i * 6);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("aSorteio", new THREE.BufferAttribute(sort, 4));
    geo.setAttribute("aUv2", new THREE.BufferAttribute(u2, 2));
    geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 40);
    return geo;
  }

  /* `n` partículas com sorteios fixos e a receita do efeito. */
  preparar(n, config) {
    const posicoes = [], sorteios = [], uv2 = [];
    for (let i = 0; i < n; i++) {
      posicoes.push(Math.random(), Math.random(), Math.random());
      sorteios.push(Math.random(), Math.random(), Math.random(), Math.random());
      uv2.push(Math.random(), (i + 0.5) / n);
    }
    this.malha = new THREE.Mesh(Particulas3D.malha(posicoes, sorteios, uv2), this.material);
    this.malha.frustumCulled = false;
    this.malha.visible = false;
    for (const [k, v] of Object.entries(config)) {
      const u = this.uniforms[k];
      if (!u) continue;
      if (u.value && u.value.copy) u.value.copy(v); else u.value = v;
    }
    this.vida = config.vida || 1;
    return this.malha;
  }

  /* Os flashes: um quadrado por posição, cada um com a sua fase. */
  prepararFlashes(posicoes, fases, tamanho) {
    const pos = [], sort = [], uv2 = [];
    for (let i = 0; i < posicoes.length; i++) {
      pos.push(posicoes[i].x, posicoes[i].y, posicoes[i].z);
      sort.push(1, 1, 1, 1);
      uv2.push(fases[i], 0);
    }
    this.malha = new THREE.Mesh(Particulas3D.malha(pos, sort, uv2), this.material);
    this.malha.frustumCulled = false;
    this.uniforms.flashes.value = 1;
    this.uniforms.tam.value = tamanho;
    return this.malha;
  }

  piscar(relogio, festa) {
    this.uniforms.relogio.value = relogio % 3600;
    this.uniforms.festa.value = festa;
  }

  /* Solta as partículas (`quantos` de 0 a 1 é a parte que sai). */
  disparar(quantos, dura, continuo = false) {
    this.tempo = 0;
    this.dura = dura;
    this.continuo = continuo;
    this.uniforms.tempo.value = 0;
    this.uniforms.semente.value = Math.random() * 61;
    this.uniforms.quantos.value = limitar(quantos, 0, 1);
    this.uniforms.continuo.value = continuo ? 1 : 0;
    this.ativo = true;
    this.malha.visible = true;
  }

  avancar(delta) {
    if (!this.ativo) return;
    this.tempo += delta;
    if (!this.continuo && this.tempo > this.dura) {
      this.ativo = false;
      this.malha.visible = false;
      return;
    }
    if (this.continuo && this.tempo > 600) this.tempo -= Math.floor(500 / this.vida) * this.vida;
    this.uniforms.tempo.value = this.tempo;
  }
}

/* A direção do cone em três vetores (o eixo e dois perpendiculares). */
function cone(direcao, aberturaGraus, config) {
  const d = direcao.clone().normalize();
  const ref = Math.abs(d.y) < 0.95 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
  const u = new THREE.Vector3().crossVectors(d, ref).normalize();
  const v = new THREE.Vector3().crossVectors(d, u).normalize();
  return { dir_base: d, eixo_u: u, eixo_v: v, abertura: aberturaGraus * Math.PI / 180, ...config };
}

/* ======================================================================
   O MUNDO
   ====================================================================== */
class Arena3D {
  /* `imagens`: as artes da arena já carregadas; `lutador`: o Boxeador. */
  constructor(imagens, lutador, reduzido) {
    this.reduzido = reduzido;
    this.texturas = [];
    this.cena = new THREE.Scene();
    this.cena.background = cru(COR_FUNDO_3D);
    this.lutador = null;
    this.relogio = 0;
    this.passo = 0;
    this.tremor = 0;
    this.clarao = 0;
    this.empurrao = 0;
    this.publico = 0;
    this.agito = 0;
    this.agitoAlvo = 0;
    this.agitoAte = 0;
    this.zoom = 0;
    this.zoomEnv = 0;
    this.koT = 0;
    this.fovBase = 0;
    this.chao = 0;
    this.chaoAlvo = 0;
    this.cambT = -1;
    this.cambDur = 1.6;
    this.camb = [];
    this.cordasPos = 0;
    this.cordasVel = 0;
    this.fasePulo = [0.0, 0.31, 0.62, 0.87];
    this.relogioDaTorcida = -1;
    this.acendePintado = -1;
    this.agitoPintado = -1;
    this.camPosOk = false;
    this.camPos = new THREE.Vector3();
    this.camMira = new THREE.Vector3();
    this.v = { pos: new THREE.Vector3(), mira: new THREE.Vector3(), sacode: new THREE.Vector3(), balanco: new THREE.Vector3(),
      extra: new THREE.Vector2(), desloc: new THREE.Vector3(), longe: new THREE.Vector3(), alvo: new THREE.Vector3() };
    this.inclinacao = inclinacaoDaTela();
    this.mancha = manchaRedonda();
    this.texturas.push(this.mancha);
    this.img = imagens;
    this.montarMundo();
    if (lutador && lutador.pronto) {
      this.lutador = lutador;
      lutador.no.position.y = PISO_DO_LUTADOR;
      this.cena.add(lutador.no);
    }
    this.montarFoco();
    this.montarSombra();
  }

  /* Uma arte já carregada como textura (sem conversão de cor). */
  textura(nome, { repetir = false, shader = false } = {}) {
    const img = this.img[nome];
    if (!img) return null;
    const t = new THREE.Texture(img);
    t.colorSpace = THREE.NoColorSpace;
    t.wrapS = repetir ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
    t.wrapT = THREE.ClampToEdgeWrapping;
    if (shader) {
      // nos shaders o UV é o do Godot (y para baixo) e a conta da torcida
      // e do letreiro corta a imagem em colunas: sem mipmap, sem costura
      t.flipY = false;
      t.generateMipmaps = false;
      t.minFilter = THREE.LinearFilter;
    } else {
      t.anisotropy = 4;
    }
    t.needsUpdate = true;
    this.texturas.push(t);
    return t;
  }

  peca(geo, material, onde = null, giro = null) {
    const mi = new THREE.Mesh(geo, material);
    if (onde) mi.position.copy(onde);
    if (giro) mi.rotation.set(giro.x, giro.y, giro.z, "YXZ");
    this.cena.add(mi);
    return mi;
  }

  /* Material sem luz com textura (e o aditivo dos fachos). */
  materialPlano(textura, aditivo = false) {
    const m = new THREE.MeshBasicMaterial({ map: textura, color: 0xffffff });
    if (aditivo) {
      m.transparent = true;
      m.blending = THREE.AdditiveBlending;
      m.depthWrite = false;
      m.side = THREE.DoubleSide;
    }
    return m;
  }

  /* Material com luz de verdade (e um brilho próprio, se pedido). */
  materialSolido(hex, aspereza = 0.5, brilho = 0) {
    const m = new THREE.MeshStandardMaterial({ roughness: aspereza, metalness: 0 });
    m.color.copy(cru(hex));
    if (brilho > 0) {
      m.emissive.copy(cru(hex));
      m.emissiveIntensity = brilho;
    }
    return m;
  }

  materialShader(vertexShader, fragmentShader, uniforms, extra = {}) {
    return new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, ...extra });
  }

  /* ----------------------------------------------------------- montagem */
  montarMundo() {
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    // a luz ambiente fraca e a principal mais de lado (build 123): com a luz
    // quase de frente o volume do corpo achatava
    this.cena.add(new THREE.AmbientLight(cru(0x39456a), 0.46 * ENERGIA));
    this.camera = new THREE.PerspectiveCamera(campoDaTela(), 540 / 960, 0.10, 30.0);
    this.calcularEnquadramento();
    this.camera.position.set(0, this.alturaDaCamera, this.distancia);
    this.camera.lookAt(0, this.alturaDaMira, 0);
    this.camera.rotateX(-this.inclinacao);
    this.cena.add(this.camera);

    this.luzChave = new THREE.DirectionalLight(cru(0xfff1d8), LUZ_CHAVE * ENERGIA);
    // DirectionalLight do Godot com giro (-46°, 42°, 0): ilumina para o
    // seu -Z. Aqui a luz fica atrás disso, mirando a origem.
    const dir = new THREE.Vector3(0, 0, -1).applyEuler(new THREE.Euler(-46 * Math.PI / 180, 42 * Math.PI / 180, 0, "YXZ"));
    this.luzChave.position.copy(dir).multiplyScalar(-10);
    this.luzChave.target.position.set(0, 0, 0);
    this.cena.add(this.luzChave);
    this.cena.add(this.luzChave.target);
    // (As luzes de recorte rosa e azul ficam de fora na TV Box:
    // Perfil.LUZES_DE_RECORTE = false.)

    this.montarFundo(V);
    this.montarRingue(V);
    this.montarFachos(V);
    this.montarFlashes(V);
    this.montarParticulas(V);
    this.montarGinasio(V);
    this.montarTeto(V);
  }

  calcularEnquadramento() {
    const figura = ALTURA_DA_FIGURA;
    const janela = figura / OCUPACAO_DO_LUTADOR;
    const meia = (CAMPO_DE_VISAO * Math.PI / 180) * 0.5;
    this.distancia = janela / (2 * Math.tan(meia));
    const base = PISO_DO_LUTADOR - (janela - figura) * 0.5;
    const inclinacao = Math.atan(CAMERA_ACIMA_DA_MIRA / this.distancia);
    this.alturaDaCamera = base + this.distancia * Math.tan(inclinacao + meia);
    this.alturaDaMira = this.alturaDaCamera - CAMERA_ACIMA_DA_MIRA;
  }

  montarFundo(V) {
    // A plateia pintada: um plano grande bem atrás do ringue.
    this.uFundo = {
      tex: { value: this.textura("fundo", { repetir: true, shader: true }) }, tempo: { value: 0 }, acende: { value: 1 },
      agito: { value: 0 }, rolagem: { value: 0 }, fachos: { value: new THREE.Vector2(-1, -1) }, fachos_forca: { value: 0 },
    };
    this.peca(new THREE.PlaneGeometry(10.4, 7.8), this.materialShader(VERTICE_UV, PIXEL_FUNDO, this.uFundo), V(0, 1.9, -4.8));
    // A GENTE da plateia: TRÊS FILEIRAS, cada uma no seu plano (a de trás
    // mais alta e mais longe), colunas e faixas iguais às de gerar_torcida.
    this.matsTorcida = [];
    this.gente = new THREE.Group();
    this.cena.add(this.gente);
    const baixo = this.textura("torcidaBaixo", { shader: true });
    const cima = this.textura("torcidaCima", { shader: true });
    if (baixo && cima) {
      const fileiras = [
        [52, 0, 150, V(0, 0.60, -4.45)],
        [40, 150, 320, V(0, 0.20, -4.32)],
        [30, 320, 512, V(0, -0.24, -4.20)],
      ];
      fileiras.forEach((fl, k) => {
        const mat = this.materialTorcida(baixo, cima, fl[0], fl[1] / 512, fl[2] / 512, k * 3.3);
        const altura = 2.5 * (fl[2] - fl[1]) / 512;
        // a folga de cima para quem pula: o pé da fileira fica onde estava
        const onde = fl[3].clone().add(V(0, altura * FOLGA_DA_TORCIDA * 0.5, 0));
        const mi = new THREE.Mesh(new THREE.PlaneGeometry(10, altura * (1 + FOLGA_DA_TORCIDA)), mat);
        mi.position.copy(onde);
        this.gente.add(mi);
      });
    }
    // O chão do ginásio entre o ringue e a plateia: escuro.
    const chao = new THREE.PlaneGeometry(14, 12);
    chao.rotateX(-Math.PI / 2);
    this.peca(chao, this.materialSolido(0x0b0810, 0.9), V(0, -0.62, -0.6));
  }

  materialTorcida(baixo, cima, colunas, v0, v1, semente) {
    const u = {
      baixo: { value: baixo }, cima: { value: cima }, agito: { value: 0 }, acende: { value: 1 },
      colunas: { value: colunas }, v0: { value: v0 }, v1: { value: v1 }, semente: { value: semente },
      folga: { value: FOLGA_DA_TORCIDA }, assento: { value: ASSENTO_DA_TORCIDA },
      f_respira: { value: new THREE.Vector4() }, f_pulo: { value: new THREE.Vector4() },
      f_balanco: { value: new THREE.Vector4() }, f_braco: { value: new THREE.Vector4() },
      f_ola: { value: 0 }, tique: { value: 0 }, fachos: { value: new THREE.Vector2(-1, -1) }, fachos_forca: { value: 0 },
    };
    const mat = this.materialShader(VERTICE_UV, PIXEL_TORCIDA, u, { transparent: true, depthWrite: false, side: THREE.DoubleSide });
    this.matsTorcida.push(mat);
    return mat;
  }

  montarRingue(V) {
    const m = MEIO_RINGUE;
    this.matLona = this.materialPlano(this.textura("lona"));
    const lona = new THREE.PlaneGeometry(m * 2, m * 2);
    lona.rotateX(-Math.PI / 2);
    this.peca(lona, this.matLona, V(0, 0, 0));
    // A borda do tablado: 3 cm abaixo da lona (sem "briga" de profundidade).
    this.peca(new THREE.BoxGeometry(m * 2 + 0.12, 0.6, m * 2 + 0.12), this.materialSolido(0x120a12, 0.8), V(0, -0.33, 0));
    // A SAIA DO RINGUE: o letreiro de LED na frente do tablado.
    const saia = this.textura("saia", { repetir: true, shader: true });
    if (saia) {
      this.uSaia = { tex: { value: saia }, acende: { value: 1 }, rolagem: { value: 0 } };
      this.peca(new THREE.PlaneGeometry(m * 2 + 0.12, 0.60), this.materialShader(VERTICE_UV, PIXEL_SAIA, this.uSaia), V(0, -0.31, m + 0.062));
    }
    // Postes de trás, REDONDOS DE VERDADE, com o protetor (vermelho à
    // esquerda, azul à direita).
    const metal = this.materialSolido(0x9aa3b5, 0.28);
    metal.metalness = 0.8;
    const poste = () => new THREE.CylinderGeometry(0.055, 0.055, 1.5, 24, 1);
    this.peca(juntar([
      { geo: poste(), matriz: matriz(V(-m, 0.75, -m)) },
      { geo: poste(), matriz: matriz(V(m, 0.75, -m)) },
    ]), metal);
    for (const lado of [-1, 1]) {
      const cor = lado < 0 ? 0xd3162f : 0x1f4fd1;
      this.peca(new THREE.CylinderGeometry(0.10, 0.10, 1.02, 28, 1), this.materialSolido(cor, 0.45, 0.12), V(lado * m, 0.86, -m));
    }
    // AS CORDAS: tubos redondos, só as de trás e as laterais. As de trás
    // ESTICAM DE VERDADE (cedem no meio e voltam com balanço de mola).
    const cores = [0xffd014, 0xff2ab0, 0x46dcff];
    const brilhos = [0.12, 0.22, 0.12];
    this.matCordas = [];
    for (let i = 0; i < ALTURAS_DAS_CORDAS.length; i++) {
      const y = ALTURAS_DAS_CORDAS[i];
      const mat = this.materialSolido(cores[i], 0.35, brilhos[i]);
      const u = { empurra: { value: 0 }, sobe: { value: 0 }, meia: { value: m } };
      mat.onBeforeCompile = (shader) => {
        Object.assign(shader.uniforms, u);
        shader.vertexShader = shader.vertexShader
          .replace("#include <common>", "#include <common>\nuniform float empurra;\nuniform float sobe;\nuniform float meia;")
          .replace("#include <begin_vertex>", `#include <begin_vertex>
  float tCorda = clamp(abs(transformed.y) / meia, 0.0, 1.0);
  float curvaCorda = 1.0 - tCorda * tCorda;
  transformed.z -= empurra * curvaCorda;
  transformed.x += sobe * curvaCorda;`);
      };
      mat.customProgramCacheKey = () => "corda";
      this.matCordas.push(u);
      const fundo = this.peca(new THREE.CylinderGeometry(0.024, 0.024, m * 2, 12, 25), mat, V(0, y, -m));
      fundo.rotation.z = Math.PI * 0.5;
      // as duas laterais da mesma cor numa malha só
      const deitada = new THREE.Matrix4().makeRotationX(Math.PI * 0.5);
      this.peca(juntar([
        { geo: new THREE.CylinderGeometry(0.024, 0.024, m * 2, 12, 2), matriz: matriz(V(-m, y, 0), deitada) },
        { geo: new THREE.CylinderGeometry(0.024, 0.024, m * 2, 12, 2), matriz: matriz(V(m, y, 0), deitada) },
      ]), this.materialSolido(cores[i], 0.35, brilhos[i]));
    }
  }

  montarFachos(V) {
    // Fachos de refletor varrendo a plateia, aditivos e baratos.
    const textura = this.textura("facho");
    this.fachos = [];
    if (!textura) return;
    [0xff3ab4, 0xb58cff, 0x48d6ff].forEach((cor, i) => {
      const mat = this.materialPlano(textura, true);
      mat.color.copy(cru(cor));
      this.fachos.push(this.peca(new THREE.PlaneGeometry(1.5, 6.0), mat, V(-2.4 + 2.4 * i, 3.2, -4.3)));
    });
  }

  montarFlashes() {
    // Flashes de câmera na plateia: estrela com halo, uma malha só.
    const brilho = this.textura("brilho");
    if (!brilho) return;
    const posicoes = [], fases = [];
    for (let i = 0; i < 16; i++) {
      posicoes.push(new THREE.Vector3(sorteio(-3.6, 3.6), sorteio(0.2, 2.6), sorteio(-4.6, -4.3)));
      fases.push(Math.random() * TAU);
    }
    this.flashes = new Particulas3D(brilho, true);
    this.cena.add(this.flashes.prepararFlashes(posicoes, fases, 0.42));
  }

  /* AS ESTRELAS DO SOCO E A POEIRA DA LONA. */
  montarParticulas(V) {
    const brilho = this.textura("brilho");
    if (brilho) {
      this.impacto = new Particulas3D(brilho, true);
      const corIni = new THREE.Vector4(...corDaPeca(0xffe7a8));
      const corFim = new THREE.Vector4(corIni.x * 1, corIni.y * 0.5, corIni.z * 0.2, 0);
      const malha = this.impacto.preparar(Math.round(96 * PARTICULAS_3D), cone(V(0, 0.2, 1), 80, {
        vida: IMPACTO_VIDA, vel_max: 6.8, vel_min: 2.4 / 6.8, amort: 3.0, grav: V(0, -5.5, 0), esfera: 0.14, tam: 0.13,
        esc_min: 1, esc_max: 1, cor_ini: corIni, cor_fim: corFim,
      }));
      malha.position.set(0, 1.34, 0.36);
      this.cena.add(malha);
    }
    this.poeira = new Particulas3D(this.mancha, false);
    const corPo = new THREE.Vector4(0.62, 0.68, 0.85, 0.30);
    const malhaPo = this.poeira.preparar(Math.round(36 * PARTICULAS_3D), cone(V(0, 1, 0), 65, {
      vida: POEIRA_VIDA, vel_max: 1.3, vel_min: 0.45 / 1.3, amort: 0, grav: V(0, -0.6, 0), caixa: V(0.7, 0.04, 0.38), tam: 0.34,
      esc_min: 1.22, esc_max: 1.6, cor_ini: corPo, cor_fim: new THREE.Vector4(corPo.x, corPo.y, corPo.z, 0),
    }));
    malhaPo.position.set(0, 0.08, -0.35);
    this.cena.add(malhaPo);
  }

  /* O FOCO DO RINGUE: a poça de luz quente na lona, em volta do lutador. */
  montarFoco() {
    const geo = new THREE.PlaneGeometry(3.0, 2.0);
    geo.rotateX(-Math.PI / 2);
    this.matFoco = this.materialPlano(this.mancha, true);
    this.matFoco.color.setRGB(COR_DO_FOCO[0] * 0.9, COR_DO_FOCO[1] * 0.9, COR_DO_FOCO[2] * 0.9);
    this.foco = this.peca(geo, this.matFoco, new THREE.Vector3(0, 0.015, 0));
    // antes da sombra: a sombra escurece por cima da luz
    this.foco.renderOrder = 1;
  }

  montarSombra() {
    const geo = new THREE.PlaneGeometry(1.0, 0.52);
    geo.rotateX(-Math.PI / 2);
    this.matSombra = new THREE.MeshBasicMaterial({ map: this.mancha, transparent: true, depthWrite: false, opacity: 0.9 });
    this.matSombra.color.setRGB(0, 0, 0.02);
    this.sombra = this.peca(geo, this.matSombra, new THREE.Vector3(0, 0.015, 0));
    this.sombra.renderOrder = 2;
  }

  /* O GINÁSIO EM VOLTA DO RINGUE (build 208): a treliça com os
     refletores e os fachos, as faixas dos lados, os protetores das cordas,
     as luzes dos postes e a poeira dançando na luz. */
  montarGinasio(V) {
    const trelica = this.materialShader(VERTICE_UV, PIXEL_TRELICA,
      { cor: { value: new THREE.Vector3(0.30, 0.31, 0.38) }, gomos: { value: 14 } }, { side: THREE.DoubleSide });
    const deitada = new THREE.Matrix4().makeRotationX(-Math.PI * 0.5);
    this.peca(juntar([
      { geo: new THREE.PlaneGeometry(5.4, 0.30), matriz: matriz(V(0, 3.30, -3.0)) },
      { geo: new THREE.PlaneGeometry(5.4, 0.30), matriz: matriz(V(0, 3.86, -3.62)) },
      { geo: new THREE.PlaneGeometry(5.4, 0.62), matriz: matriz(V(0, 3.15, -3.31), deitada) },
    ]), trelica);
    // OS REFLETORES pendurados na treliça, e os fachos até o ringue
    const cores = [0xfff1d8, 0xff4fb8, 0xfff1d8, 0x6fe2ff, 0xfff1d8, 0xff4fb8, 0xfff1d8];
    const carcacas = [], lampadas = [], cones = [];
    for (let i = 0; i < 7; i++) {
      const x = -2.25 + 0.75 * i;
      const onde = V(x, 3.02, -2.92);
      const alvo = V(x * 0.32, 0, -0.35 + 0.15 * Math.abs(x));
      const giro = giroPara(onde, alvo);
      const eixoY = new THREE.Vector3().setFromMatrixColumn(giro, 1);
      carcacas.push({ geo: new THREE.CylinderGeometry(0.055, 0.075, 0.20, 14, 1), matriz: matriz(onde, giro) });
      lampadas.push({ geo: new THREE.CylinderGeometry(0.062, 0.062, 0.02, 14, 1),
        matriz: matriz(onde.clone().addScaledVector(eixoY, -0.105), giro), cor: corDaPeca(cores[i]) });
      if (i >= 1 && i <= 5) {
        cones.push(this.facho(onde.clone().addScaledVector(eixoY, -0.11), alvo, cores[i], cores[i] === 0xfff1d8 ? 0.30 : 0.22, cones.length));
      }
    }
    this.peca(juntar(carcacas), new THREE.MeshBasicMaterial({ color: cru(0x2a2b36) }));
    this.uFachos = { vivo: { value: 1 }, relogio: { value: 0 } };
    this.cones = this.peca(juntar(cones), this.materialShader(VERTICE_FACHO, PIXEL_COR, this.uFachos, {
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide,
    }));
    // AS FAIXAS DOS LADOS, penduradas da treliça
    const faixa = this.textura("faixa");
    if (faixa) {
      const pecas = [];
      for (const lado of [-1, 1]) {
        pecas.push({ geo: new THREE.PlaneGeometry(0.56, 1.54), matriz: matriz(V(lado * 2.30, 2.62, -3.95), new THREE.Matrix4().makeRotationY(-lado * 0.30)) });
      }
      this.peca(juntar(pecas), this.materialPlano(faixa));
    }
    // OS PROTETORES DAS CORDAS nos postes de trás e a luz no alto de cada poste.
    for (const lado of [-1, 1]) {
      const cor = lado < 0 ? 0xd3162f : 0x1f4fd1;
      const centro = V(lado * MEIO_RINGUE, 0, -MEIO_RINGUE);
      const paraDentro = centro.clone().negate().normalize();
      const giro = new THREE.Matrix4().makeRotationFromQuaternion(new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), paraDentro));
      const pads = ALTURAS_DAS_CORDAS.map((y) => ({
        geo: new THREE.CapsuleGeometry(0.062, 0.26 - 2 * 0.062, 4, 12),
        matriz: matriz(centro.clone().add(V(0, y, 0)).addScaledVector(paraDentro, 0.09), giro),
      }));
      this.peca(juntar(pads), this.materialSolido(cor, 0.35, 0.18));
      lampadas.push({ geo: new THREE.CylinderGeometry(0.07, 0.07, 0.05, 20, 1), matriz: matriz(centro.clone().add(V(0, 1.52, 0))), cor: clareada(cor, 0.4) });
    }
    this.matLampadas = new THREE.ShaderMaterial({
      uniforms: { acesa: { value: 1 } },
      vertexShader: "attribute vec4 aCor; varying vec4 vCor; void main() { vCor = aCor; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: "uniform float acesa; varying vec4 vCor; void main() { gl_FragColor = vec4(vCor.rgb * acesa, 1.0); }",
    });
    this.peca(juntar(lampadas), this.matLampadas);
    // A POEIRA DANÇANDO NA LUZ (bem pouca, devagar).
    this.poeiraNoAr = new Particulas3D(this.mancha, true);
    const grao = new THREE.Vector4(1.0, 0.92, 0.8, 0.35);
    const malha = this.poeiraNoAr.preparar(Math.round(48 * PARTICULAS_3D), cone(V(0.2, 1, 0), 180, {
      vida: 9.0, vel_max: 0.08, vel_min: 0.25, amort: 0, grav: V(0, -0.01, 0), caixa: V(2.0, 1.3, 1.6), tam: 0.035,
      esc_min: 1.14, esc_max: 1.4, cor_ini: grao, cor_fim: grao,
    }));
    malha.position.set(0, 2.1, -1.2);
    this.cena.add(malha);
    this.poeiraNoAr.disparar(1, 9, true);
  }

  /* Um facho de luz de `de` até `alvo`, pronto para `juntar`. */
  facho(de, alvo, hex, forca, numero) {
    const comprimento = de.distanceTo(alvo);
    const c = cru(hex);
    return {
      geo: new THREE.CylinderGeometry(0.07, 0.42 + comprimento * 0.10, comprimento, 16, 6),
      matriz: matriz(de.clone().add(alvo).multiplyScalar(0.5), giroPara(de, alvo)),
      cor: [c.r, c.g, c.b, forca],
      cone: [comprimento * 0.5, numero],
    };
  }

  /* O TETO DA DERROTA: só quando o jogador vai à lona e a câmera olha para
     cima — a arquibancada de cima, o teto com as lâmpadas, o telão e três
     fachos. Na luta normal nada disso é desenhado. */
  montarTeto(V) {
    this.teto = new THREE.Group();
    this.teto.visible = false;
    this.cena.add(this.teto);
    this.matsTeto = [];
    const no = (mi) => { this.cena.remove(mi); this.teto.add(mi); return mi; };
    const tetoMat = this.materialPlano(this.textura("teto"));
    this.matsTeto.push(tetoMat);
    no(this.peca(new THREE.PlaneGeometry(18.0, 7.0), tetoMat, V(0, 8.6, -4.6), V(62 * Math.PI / 180, 0, 0)));
    if (this.matsTorcida.length > 1) {
      // a mesma plateia da fileira do meio, com outra semente
      const u = this.matsTorcida[1].uniforms;
      const gente = this.materialTorcida(u.baixo.value, u.cima.value, 40, 150 / 512, 320 / 512, 7.7);
      no(this.peca(new THREE.PlaneGeometry(17.0, 2.9), gente, V(0, 6.0, -5.7), V(24 * Math.PI / 180, 0, 0)));
    }
    const giro = 14 * Math.PI / 180;
    no(this.peca(new THREE.BoxGeometry(2.15, 1.25, 0.9), this.materialSolido(0x120c1c, 0.6), V(0, 4.35, -2.7), V(giro, 0, 0)));
    const telaoMat = this.materialPlano(this.textura("telao"));
    this.matsTeto.push(telaoMat);
    const frente = V(0, 0, 0.452).applyAxisAngle(V(1, 0, 0), giro);
    no(this.peca(new THREE.PlaneGeometry(1.95, 1.08), telaoMat, V(0, 4.35, -2.7).add(frente), V(giro, 0, 0)));
    const facho = this.textura("facho");
    if (facho) {
      const mat = this.materialPlano(facho, true);
      mat.color.setRGB(0.55, 0.42, 0.75);
      no(this.peca(juntar([
        { geo: new THREE.PlaneGeometry(1.1, 5.2), matriz: matriz(V(-1.9, 4.4, -3.3), new THREE.Matrix4().makeRotationZ(-0.20)) },
        { geo: new THREE.PlaneGeometry(1.1, 5.2), matriz: matriz(V(0, 5.6, -3.9)) },
        { geo: new THREE.PlaneGeometry(1.1, 5.2), matriz: matriz(V(1.9, 4.4, -3.3), new THREE.Matrix4().makeRotationZ(0.20)) },
      ]), mat));
    }
  }

  mostrarTeto(sim) {
    if (this.teto.visible !== sim) this.teto.visible = sim;
    if (sim) {
      // as lâmpadas e o telão respiram (só a cor do material)
      const luz = 0.88 + 0.12 * Math.sin(this.relogio * 1.8);
      for (const m of this.matsTeto) m.color.setRGB(luz, luz, luz);
    }
  }

  /* ---------------------------------------------------------- interface */
  golpe(forca, derruba = false, pontos = -1, ultimo = false) {
    this.zoom = Math.max(this.zoom, limitar(0.35 + forca * 0.75, 0, 1));
    this.tremor = limitar(0.35 + forca, 0, 1.35);
    this.clarao = limitar(0.4 + forca * 0.6, 0, 1);
    this.empurrao = forca;
    // O SOCO ESTICA AS CORDAS DE TRÁS: mais forte, mais longe (e voltam).
    this.cordasVel += 2.5 + limitar(forca, 0, 1.2) * 6.5;
    this.publico = Math.max(this.publico, limitar(0.08 + forca * (derruba ? 1.15 : 0.85), 0, 1));
    if (this.impacto) this.impacto.disparar(limitar(lerp(0.22, 1.0, forca), 0.05, 1), IMPACTO_VIDA + 0.05);
    if (derruba && this.poeira) this.poeira.disparar(1, POEIRA_VIDA + 0.05);
    if (!this.lutador) return { nocaute: false, dano: 0, reacao: "", desdenhou: false };
    const resposta = this.lutador.bater(forca, derruba, pontos, ultimo);
    if (resposta.desdenhou) {
      this.publico = Math.max(this.publico, 0.66);
      this.clarao = Math.max(this.clarao, 0.28);
    }
    return resposta;
  }

  /* O CAMBALEIO do soco na tela: a câmera balança e rola, e o balanço
     morre em `segundos`. Frequências e fases sorteadas: nunca igual. */
  cambalear(segundos) {
    this.cambT = 0;
    this.cambDur = Math.max(segundos, 0.3);
    this.camb = [
      sorteio(2.6, 4.6), Math.random() * TAU, sorteio(0.05, 0.09),
      sorteio(2.0, 3.8), Math.random() * TAU, sorteio(0.03, 0.06),
      sorteio(1.6, 3.0), Math.random() * TAU, sorteio(0.05, 0.10),
    ];
    this.tremor = Math.max(this.tremor, 0.9);
    this.clarao = Math.max(this.clarao, 0.35);
  }

  /* A TORCIDA REAGE: `intensidade` 0..1 por `segundos`, depois acalma. */
  agitar(intensidade, segundos = 4.0) {
    this.agitoAlvo = Math.max(this.agitoAlvo, limitar(intensidade, 0, 1));
    this.agitoAte = Math.max(this.agitoAte, this.relogio + segundos);
  }

  venceu(festa = "") { if (this.lutador) this.lutador.venceu(festa); }
  fimDeRodada(desfecho) { if (this.lutador) this.lutador.fimDeRodada(desfecho); }
  socoNaTela() { return !!this.lutador && this.lutador.socoNaTela(); }
  nocauteNoJogador() { return !!this.lutador && this.lutador.socoFinal(); }
  telaAtingida() { return !!this.lutador && this.lutador.telaAtingida(); }
  guardar(ativo) { if (this.lutador) this.lutador.guardar(ativo); }
  dano() { return this.lutador ? this.lutador.dano : 0; }
  naLona() { return !!this.lutador && this.lutador.queda > 0.35; }
  jogadorNoChao(sim) { this.chaoAlvo = sim ? 1 : 0; }

  preparar() {
    this.camPosOk = false;
    this.chao = 0;
    this.chaoAlvo = 0;
    this.mostrarTeto(false);
    this.agitoAlvo = 0;
    this.agitoAte = 0;
    if (this.lutador) this.lutador.preparar();
    this.tremor = 0;
    this.clarao = 0;
    this.publico = 0;
    this.cambT = -1;
  }

  avancar(delta) {
    this.relogio += delta;
    this.passo = delta;
    this.tremor = Math.max(0, this.tremor - delta * 2.2);
    this.clarao = Math.max(0, this.clarao - delta * 2.4);
    this.empurrao = Math.max(0, this.empurrao - delta * 1.6);
    this.publico = Math.max(0, this.publico - delta * 0.72);
    if (this.cambT >= 0) {
      this.cambT += delta;
      if (this.cambT > this.cambDur) this.cambT = -1;
    }
    if (this.relogio > this.agitoAte) this.agitoAlvo = Math.max(0, this.agitoAlvo - delta * 0.35);
    this.agito = lerp(this.agito, Math.max(this.agitoAlvo, this.publico * 0.6), 1 - Math.exp(-delta * 4));
    if (this.lutador) {
      this.lutador.pontoDaCamera.copy(this.camera.position);
      this.lutador.atualizar(delta);
    }
    this.mexerCordas(delta);
    this.sombraDeContato();
    this.atualizarCamera(delta);
    this.luzes();
    this.piscar();
  }

  /* AS CORDAS DE TRÁS CEDEM quando o lutador cai nelas e a cada soco. */
  mexerCordas(delta) {
    const alvo = this.lutador ? this.lutador.pressaoNasCordas() : 0;
    if (alvo <= 0 && Math.abs(this.cordasPos) < 0.001 && Math.abs(this.cordasVel) < 0.001) return;
    const d = Math.min(delta, 0.05);
    this.cordasVel += (alvo - this.cordasPos) * 140 * d;
    this.cordasVel *= Math.exp(-7 * d);
    this.cordasPos += this.cordasVel * d;
    const pesos = [0.55, 1.0, 0.75];
    for (let i = 0; i < this.matCordas.length; i++) {
      const peso = pesos[Math.min(i, 2)];
      this.matCordas[i].empurra.value = 0.55 * this.cordasPos * peso;
      this.matCordas[i].sobe.value = 0.24 * this.cordasVel / 11.8 * peso * (i % 2 === 0 ? 1 : -0.8);
    }
    if (alvo > 0.6) this.publico = Math.max(this.publico, 0.4);
  }

  sombraDeContato() {
    if (!this.lutador) return;
    const desloc = this.lutador.deslocamento(this.v.desloc);
    const caido = limitar(this.lutador.queda, 0, 1);
    this.sombra.position.set(desloc.x, 0.015, desloc.z * 0.6);
    this.sombra.scale.set(lerp(1, 1.5, caido), 1, lerp(1, 1.3, caido));
    this.matSombra.opacity = lerp(0.9, 0.6, caido);
    this.foco.position.set(desloc.x * 0.7, 0.015, desloc.z * 0.5);
    const f = 0.9 + this.clarao * 0.4;
    this.matFoco.color.setRGB(COR_DO_FOCO[0] * f, COR_DO_FOCO[1] * f, COR_DO_FOCO[2] * f);
  }

  /* A CÂMERA ANDA, NÃO PULA: empurrão do golpe, queda, soco na tela e o
     passeio lento viram um ALVO, perseguido por uma mola. O tremor fica de
     fora da mola (ele é para ser seco). */
  atualizarCamera(delta) {
    const cam = this.camera;
    const { pos, mira, sacode, balanco, extra, longe } = this.v;
    if (this.fovBase <= 0) this.fovBase = cam.fov;
    this.zoom = Math.max(0, this.zoom - delta * 1.8);
    // sobe rápido, desce devagar
    this.zoomEnv = lerp(this.zoomEnv, this.zoom, 1 - Math.exp(-(this.zoom > this.zoomEnv ? 22 : 5) * Math.min(delta, 0.05)));
    const fov = this.fovBase * (1 - ZOOM_DO_SOCO * this.zoomEnv);
    if (Math.abs(fov - cam.fov) > 1e-5) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }
    sacode.set(0, 0, 0);
    if (this.tremor > 0.02 && !this.reduzido) {
      sacode.set(sorteio(-1, 1), sorteio(-1, 1), sorteio(-0.4, 0.4)).multiplyScalar(this.tremor * 0.05);
    }
    if (this.lutador) this.lutador.cameraExtra(extra); else extra.set(0, 0);
    const ameaca = this.lutador ? this.lutador.ameaca : 0;
    const livre = 1 - limitar(extra.x * 1.5, 0, 1);
    const arco = Math.sin(this.relogio * 0.23) * ARCO * livre;
    const dolly = Math.sin(this.relogio * 0.17 + 1.3) * 0.10 * livre;
    const dist = this.distancia - this.empurrao * 0.30 - extra.x - dolly + ameaca * 0.07;
    pos.set(Math.sin(arco) * dist, this.alturaDaCamera + Math.sin(this.relogio * 0.21) * 0.05 - extra.y + ameaca * 0.015, Math.cos(arco) * dist);
    mira.set(0, this.alturaDaMira + this.empurrao * 0.06, 0);
    // NO SOCO NA TELA A CÂMERA OLHA NO ROSTO.
    const perto = limitar(extra.x / 0.72, 0, 1);
    if (perto > 0.001) {
      const rosto = ALTURA_DA_FIGURA * 0.90;
      const k = perto * perto * (3 - 2 * perto);
      pos.y = lerp(pos.y, rosto + 0.03, k);
      mira.y = lerp(mira.y, rosto - 0.04, k);
    }
    const caido = this.lutador ? this.lutador.queda : 0;
    if (caido > 0.001) {
      // No nocaute a câmera afasta e desce, e gira devagar em volta do corpo.
      const t = ease(caido, 0.5);
      this.koT = caido > 0.5 ? this.koT + delta : Math.max(0, this.koT - delta * 2);
      const giro = Math.min(this.koT * 0.14, 0.42) * t;
      longe.set(0, this.alturaDaCamera * 0.54, this.distancia * 1.07).applyAxisAngle(this.v.alvo.set(0, 1, 0), giro);
      pos.lerp(longe, t);
      mira.lerp(this.v.alvo.set(0, this.alturaDaMira * 0.58, 0), t);
    } else {
      this.koT = 0;
    }
    let rolo = 0;
    // O JOGADOR NO CHÃO: a câmera cai até a lona, meio de lado, olhando o
    // lutador de baixo — quem perdeu vê o ginásio do chão.
    this.chao = moverAte(this.chao, this.chaoAlvo, delta * (this.chaoAlvo > this.chao ? 2.4 : 1.2));
    this.mostrarTeto(this.chao > 0.02);
    if (this.chao > 0.001) {
      const t = this.chao * this.chao * (3 - 2 * this.chao);
      const quique = Math.sin(limitar(this.chao, 0, 1) * Math.PI) * 0.05 * (this.chaoAlvo > 0.5 ? 1 : 0);
      pos.lerp(longe.set(0.42, 0.14 + quique, this.distancia * 0.74), t);
      mira.lerp(this.v.alvo.set(-0.05, ALTURA_DA_FIGURA * 0.78, 0), t);
      rolo += 0.30 * t;
    }
    balanco.set(0, 0, 0);
    if (this.cambT >= 0 && this.camb.length >= 9 && !this.reduzido) {
      const t = this.cambT;
      const some = Math.pow(1 - limitar(t / this.cambDur, 0, 1), 1.6);
      const c = this.camb;
      sacode.x += Math.sin(t * c[0] * TAU * 0.5 + c[1]) * c[2] * some;
      sacode.y += Math.sin(t * c[3] * TAU * 0.5 + c[4]) * c[5] * some;
      balanco.x = Math.sin(t * c[3] * TAU * 0.4 + c[1]) * c[2] * 0.6 * some;
      rolo = Math.sin(t * c[6] * TAU * 0.5 + c[7]) * c[8] * some;
    }
    if (!this.camPosOk || delta <= 0) {
      this.camPos.copy(pos);
      this.camMira.copy(mira);
      this.camPosOk = true;
    } else {
      const k = 1 - Math.exp(-CAMERA_MOLA * Math.min(delta, 0.05));
      this.camPos.lerp(pos, k);
      this.camMira.lerp(mira, k);
    }
    cam.position.copy(this.camPos).add(sacode);
    cam.lookAt(this.v.alvo.copy(this.camMira).add(balanco));
    cam.rotateX(-this.inclinacao);
    if (Math.abs(rolo) > 0.0001) cam.rotateZ(-rolo);
    cam.updateMatrixWorld();
  }

  luzes() {
    if (this.lutador) this.lutador.acenderClarao(this.clarao);
    this.luzChave.intensity = (LUZ_CHAVE + this.clarao * 1.0) * ENERGIA;
    // Materiais sem luz acendem pelo albedo: o salão inteiro pisca junto.
    const acende = 1 + this.clarao * 0.55;
    this.uFundo.acende.value = acende;
    this.uFundo.tempo.value = fposmod(this.relogio, TAU * 10);
    this.uFundo.rolagem.value = fposmod(this.relogio * 0.018, 1);
    this.uFundo.agito.value = this.agito;
    this.fasesDaTorcida();
    if (Math.abs(acende - this.acendePintado) > 0.002 || Math.abs(this.agito - this.agitoPintado) > 0.002) {
      this.acendePintado = acende;
      this.agitoPintado = this.agito;
      for (const mat of this.matsTorcida) {
        mat.uniforms.acende.value = acende;
        mat.uniforms.agito.value = this.agito;
      }
    }
    this.matLona.color.setRGB(acende, acende, acende);
    this.animarGinasio();
    if (this.uSaia) {
      this.uSaia.rolagem.value = fposmod(this.relogio * 0.05, 1);
      this.uSaia.acende.value = acende;
    }
    for (let i = 0; i < this.fachos.length; i++) {
      const f = this.fachos[i];
      f.rotation.z = Math.sin(this.relogio * (0.35 + 0.1 * i) + i * 2.1) * 0.35
        + Math.sin(this.relogio * 2.6 + i) * 0.25 * this.agito;
      f.material.opacity = Math.min(1, 0.20 + this.publico * 0.35 + this.clarao * 0.25 + this.agito * 0.25);
    }
  }

  /* O RITMO DA TORCIDA, pronto: cada movimento em quatro velocidades,
     como fração da volta; o pulo acelera com o agito sem tranco. */
  fasesDaTorcida() {
    const dt = this.relogioDaTorcida < 0 ? 0 : limitar(this.relogio - this.relogioDaTorcida, 0, 0.25);
    this.relogioDaTorcida = this.relogio;
    for (let k = 0; k < 4; k++) this.fasePulo[k] = fposmod(this.fasePulo[k] + dt * (RITMO_PULO[k] + this.agito * 0.48), 1);
    const r = this.relogio;
    const ola = fposmod(r * 1.7 / TAU, 1);
    const tique = fposmod(Math.floor(r * 2.2), 64);
    // OS DOIS FACHOS vão e vêm pela plateia em ritmos diferentes.
    const fx = lerp(-0.12, 1.12, 0.5 + 0.5 * Math.sin(r * 0.37));
    const fy = lerp(-0.12, 1.12, 0.5 + 0.5 * Math.sin(r * 0.29 + 2.1));
    const forca = 0.45 + this.agito * 0.5 + this.clarao * 0.9;
    this.uFundo.fachos.value.set(fx, fy);
    this.uFundo.fachos_forca.value = forca;
    for (const mat of this.matsTorcida) {
      const u = mat.uniforms;
      u.fachos.value.set(fx, fy);
      u.fachos_forca.value = forca;
      this.quatroFases(RITMO_RESPIRA, u.f_respira.value);
      u.f_pulo.value.set(this.fasePulo[0], this.fasePulo[1], this.fasePulo[2], this.fasePulo[3]);
      this.quatroFases(RITMO_BALANCO, u.f_balanco.value);
      this.quatroFases(RITMO_BRACO, u.f_braco.value);
      u.f_ola.value = ola;
      u.tique.value = tique;
    }
  }

  /* Um movimento nas suas quatro velocidades, como fração da volta. */
  quatroFases(ritmo, out) {
    const r = this.relogio;
    return out.set(fposmod(r * ritmo[0], 1), fposmod(r * ritmo[1], 1), fposmod(r * ritmo[2], 1), fposmod(r * ritmo[3], 1));
  }

  /* Os refletores respiram com a torcida e acendem no golpe. */
  animarGinasio() {
    this.uFachos.vivo.value = 1 + this.clarao * 1.6 + this.agito * 0.35 + this.publico * 0.4;
    this.uFachos.relogio.value = fposmod(this.relogio, TAU * 100);
    this.matLampadas.uniforms.acesa.value = limitar(0.80 + this.clarao * 0.6 + 0.08 * Math.sin(this.relogio * 2), 0, 1.6);
  }

  piscar() {
    if (this.flashes) this.flashes.piscar(this.relogio, this.clarao + this.publico * 0.6 + this.agito * 0.5);
    if (this.impacto) this.impacto.avancar(this.passo);
    this.poeira.avancar(this.passo);
    this.poeiraNoAr.avancar(this.passo);
  }

  /* Um ponto do mundo na tela lógica (540 x 960). */
  projetar(x, y, z, out) {
    const v = this.v.alvo.set(x, y, z).project(this.camera);
    out.x = (v.x + 1) * 0.5 * 540;
    out.y = (1 - v.y) * 0.5 * 960;
    return out;
  }

  /* OS ENFEITES DO DEGRAU (Arena3D._enfeites_visiveis): os fachos, os cones
     de luz e os flashes da plateia são transparentes e cobrem boa parte da
     tela — são a primeira coisa a sair quando a máquina aperta. */
  enfeites(sim) {
    for (const f of this.fachos) f.visible = sim;
    if (this.cones) this.cones.visible = sim;
    if (this.flashes) this.flashes.malha.visible = sim;
  }

  /* Onde está o rosto dele na tela (a base da cabeça, o queixo): é para
     lá que a luva de quem joga vai. */
  cabecaNaTela(out) {
    if (!this.lutador) return this.projetar(0, ALTURA_DA_FIGURA * 0.86, 0, out);
    const osso = this.lutador.ossos[this.lutador.k.Head];
    osso.getWorldPosition(this.v.desloc);
    return this.projetar(this.v.desloc.x, this.v.desloc.y, this.v.desloc.z, out);
  }

  /* Tudo visível uma vez para o three.js compilar os shaders agora, e não
     no primeiro soco (o `aquecer` da arena). */
  aquecer(renderizador) {
    const escondidos = [];
    this.cena.traverse((o) => { if (!o.visible) { escondidos.push(o); o.visible = true; } });
    try { renderizador.compile(this.cena, this.camera); } catch (erro) { /* compila no primeiro quadro */ }
    for (const o of escondidos) o.visible = false;
  }

  destruir() {
    this.cena.traverse((o) => {
      if (o.isMesh && !o.isSkinnedMesh) {
        o.geometry.dispose();
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of mats) m.dispose();
      }
    });
    for (const t of this.texturas) t.dispose();
    if (this.lutador) this.lutador.destruir();
  }
}

/* ======================================================================
   O CARREGAMENTO DO 3D

   O three.js e o boxeador chegam DEPOIS que o jogo abre (import dinâmico
   e um .glb de ~1 MB): até lá a tela mostra o ringue sendo montado, e o
   resto da partida já funciona. O three.js é importado sempre pelo mesmo
   endereço — o GLTFLoader importa "./three.module.min.js" da mesma pasta,
   e assim os dois falam com a mesma cópia do motor.
   ====================================================================== */
const URL_THREE = "../../../vendor/three/three.module.min.js";
const URL_GLTF = "../../../vendor/three/GLTFLoader.js";
/* A nitidez da arena: até 1,5 pixel do 3D por ponto da tela lógica (o
   celular médio não aguenta desenhar o ginásio inteiro no dobro). */
const NITIDEZ_3D_MAXIMA = 1.5;
/* OS DEGRAUS DO GRÁFICO (Arena3D.DEGRAUS): cada degrau tira UMA coisa, a
   que menos se vê primeiro — 0 tudo; 1 sem os fachos e os flashes; 2 e 3
   o 3D com menos pixels. O vigia mede o quadro de verdade e só desce
   (subir de novo faria a imagem piscar entre dois tamanhos). */
const ESCALA_DO_DEGRAU = [1.0, 1.0, 0.85, 0.7];
/* Quantos quadros o vigia mede de cada vez, e a média que já é lenta
   demais: abaixo de 40 quadros por segundo. */
const QUADROS_DO_VIGIA = 120;
const QUADRO_LENTO = 1 / 40;
const MODELO_DO_BOXEADOR = "super-boxing/boxeador.glb";
/* As pinturas do corpo (lutador_boxeador.gd, TEXTURAS), em WebP. */
const TEXTURAS_DO_BOXEADOR = {
  pele: "super-boxing/boxeador_pele.webp",
  relevo: "super-boxing/boxeador_relevo.webp",
  calcao: "super-boxing/boxeador_calcao.webp",
  cinturao: "super-boxing/boxeador_0.webp",
  placa: "super-boxing/boxeador_1.webp",
};
/* O tamanho da luva que voa quando ela chega no rosto dele: o boxeador
   está a uns três metros e meio da câmera, e a luva chega do tamanho de
   uma cabeça (no saco de reserva ela chega maior: o saco é largo). */
const LUVA_NO_ROSTO = 0.42;
const LUVA_NO_SACO = 0.92;

/* Quantas partidas este aparelho já jogou (a frase da derrota varia). */
let partidas = 0;

/* O navegador desenha 3D? Pergunta a um canvas de rascunho, que é
   devolvido na hora (sem isso o three.js reclamaria no console). */
function temWebGL() {
  try {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2") || c.getContext("webgl");
    if (!gl) return false;
    const perder = gl.getExtension("WEBGL_lose_context");
    if (perder) perder.loseContext();
    return true;
  } catch (erro) {
    return false;
  }
}

/* Desfaz uma cena carregada que não vai ser usada. */
function descartarCena(raiz) {
  raiz.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
  });
}

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
    fight: "super-boxing/fight.webp",
    never: "super-boxing/never_give_up.webp",
    ateOFim: "super-boxing/ate_o_fim.webp",
    aro: "super-boxing/medidor_aro.webp",
    giroFora: "super-boxing/medidor_giro_fora.webp",
    giroDentro: "super-boxing/medidor_giro_dentro.webp",
    luvaCorpo: "super-boxing/luva_corpo.webp",
    luvaBrilho: "super-boxing/luva_brilho.webp",
    cartaoGiro: "super-boxing/cartao_giro.webp",
    logo: "super-boxing/logo.webp",
    marca: "super-boxing/marca.webp",
  },

  criar(api) {
    const img = api.img;
    const tingir = criarTingidor();

    /* ------------------------------------------------------------------
       O MUNDO 3D: "carregando" → "pronto" (ou "falhou", e aí o ginásio 2D
       com o saco entra no lugar). A imagem é desenhada num canvas WebGL
       próprio, fora da página, e colada por baixo do painel 2D.
       ------------------------------------------------------------------ */
    const mundo = {
      estado: "carregando", arena: null, renderizador: null, tela: null, largura: 0, altura: 0, relogio: 0, avancou: false,
      degrau: 0, quadros: 0, somaDosQuadros: 0,
    };
    let destruido = false;
    const pontoNaTela = { x: 0, y: 0 };
    let degradeDoRodape = null;
    carregarMundo3D();

    function arena3d() { return mundo.estado === "pronto" ? mundo.arena : null; }

    async function carregarMundo3D() {
      // sem WebGL nem adianta baixar o motor: o ginásio 2D entra direto
      if (!temWebGL()) { perderMundo3D(); return; }
      let renderizador = null, lutador = null, arena = null, cena = null;
      try {
        const [tres, carregador] = await Promise.all([
          import(new URL(URL_THREE, import.meta.url).href),
          import(new URL(URL_GLTF, import.meta.url).href),
        ]);
        if (destruido) return;
        THREE = tres;
        const tela = document.createElement("canvas");
        renderizador = new THREE.WebGLRenderer({ canvas: tela, antialias: true, alpha: false, stencil: false, powerPreference: "high-performance" });
        // ver O ESPAÇO DE COR É O DA TV BOX, no começo do mundo 3D
        renderizador.outputColorSpace = THREE.LinearSRGBColorSpace;
        renderizador.setPixelRatio(1);
        renderizador.setSize(LARGURA, ALTURA, false);
        tela.addEventListener("webglcontextlost", () => { if (!destruido) perderMundo3D(); });
        const endereco = (arquivo) => new URL(arquivo, import.meta.url).href;
        const anisotropia = Math.min(4, renderizador.capabilities.getMaxAnisotropy());
        const carregarTextura = (arquivo) => new THREE.TextureLoader().loadAsync(endereco(arquivo)).then((t) => {
          t.flipY = false; // as UVs do glTF
          t.colorSpace = THREE.NoColorSpace;
          t.anisotropy = anisotropia;
          return t;
        }).catch(() => null);
        const nomes = Object.keys(TEXTURAS_DO_BOXEADOR);
        const [gltf, ...pinturas] = await Promise.all([
          new carregador.GLTFLoader().loadAsync(endereco(MODELO_DO_BOXEADOR)),
          ...nomes.map((n) => carregarTextura(TEXTURAS_DO_BOXEADOR[n])),
        ]);
        cena = gltf.scene;
        const texturas = {};
        nomes.forEach((n, i) => { texturas[n] = pinturas[i]; });
        if (destruido) {
          for (const t of pinturas) if (t) t.dispose();
          descartarCena(cena);
          renderizador.dispose();
          return;
        }
        lutador = new Boxeador(cena, texturas);
        if (!lutador.pronto) throw new Error("o boxeador veio sem esqueleto");
        arena = new Arena3D(img, lutador, api.reduzido);
        arena.aquecer(renderizador);
        mundo.renderizador = renderizador;
        mundo.tela = tela;
        mundo.arena = arena;
        mundo.relogio = performance.now();
        mundo.estado = "pronto";
        arenaChegou();
      } catch (erro) {
        if (destruido) return;
        console.warn("Super Boxing: a arena 3D não carregou; a partida segue com o ginásio 2D.", erro);
        try {
          if (arena) arena.destruir();
          else if (cena) descartarCena(cena);
          if (renderizador) { renderizador.dispose(); renderizador.forceContextLoss(); }
        } catch (e) { /* já era */ }
        perderMundo3D();
      }
    }

    function perderMundo3D() {
      mundo.estado = "falhou";
      mundo.arena = null;
      mundo.renderizador = null;
      mundo.tela = null;
    }

    /* O 3D chegou com a partida já andando: o lutador entra no estado dela. */
    function arenaChegou() {
      const a = mundo.arena;
      a.preparar();
      if (lutaComecou && !terminou && (estado === "armado" || estado === "voo" || estado === "maisForte")) {
        a.guardar(true);
        a.agitar(0.35, 2.5);
      }
    }

    /* ------------------------------------------------------------------
       O GINÁSIO 2D DE RESERVA (sem WebGL): as camadas que não se mexem,
       desenhadas uma vez só — e só se o 3D não vier.
       ------------------------------------------------------------------ */
    let reserva = null;
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
      // a luz do ginásio cai de cima: a torcida mais perto do escuro
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
      // profundidade corrigida (1/largura).
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
        const sombraSaia = g.createLinearGradient(0, perto.y, 0, perto.y + altura);
        sombraSaia.addColorStop(0, "rgba(0,0,0,.05)");
        sombraSaia.addColorStop(1, "rgba(0,0,0,.45)");
        g.fillStyle = sombraSaia;
        g.fillRect(0, perto.y, LARGURA, altura);
      }
      g.fillStyle = "rgba(255,255,255,.25)";
      g.fillRect(0, perto.y - 1, LARGURA, 2);
      // OS POSTES DO FUNDO, com os protetores
      const postes = [[longe.x0, "#d3162f"], [longe.x1, "#1f4fd1"]];
      for (const [x, cor] of postes) {
        g.fillStyle = "#1a1230";
        g.fillRect(x - 4, longe.y - 82, 8, 84);
        g.fillStyle = cor;
        retanguloRedondo(g, x - 6, longe.y - 80, 12, 74, 5);
        g.fill();
        g.fillStyle = "rgba(255,255,255,.3)";
        g.fillRect(x - 3, longe.y - 76, 2, 66);
      }
      // AS CORDAS nas cores de ALTURAS_DAS_CORDAS
      const cores = ["#ffd014", "#ff2ab0", "#46dcff"];
      const alturas = [22, 44, 66];
      g.lineCap = "round";
      for (let k = 0; k < 3; k++) {
        const h = alturas[k];
        g.strokeStyle = cores[k];
        g.lineWidth = 2.4;
        g.beginPath();
        g.moveTo(longe.x0, longe.y - h);
        g.quadraticCurveTo(270, longe.y - h + 3, longe.x1, longe.y - h);
        g.stroke();
        g.lineWidth = 3.6;
        g.beginPath();
        g.moveTo(longe.x0, longe.y - h);
        g.lineTo(perto.x0 + 40, perto.y - h * 2.3);
        g.moveTo(longe.x1, longe.y - h);
        g.lineTo(perto.x1 - 40, perto.y - h * 2.3);
        g.stroke();
      }
      return c;
    }

    /* O SACO, desenhado à mão nas cores do original (Paleta.SACO_*). */
    function montarSaco() {
      const L = 160;
      const A = 480;
      const { c, g } = novaTela(L, A);
      const cx = L / 2;
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
      g.strokeStyle = "#3a2030";
      g.lineWidth = 4;
      for (const x of [18, 56, 104, 142]) {
        g.beginPath(); g.moveTo(cx, 197); g.lineTo(x, 222); g.stroke();
      }
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
      g.strokeStyle = "rgba(255,230,235,.55)";
      g.lineWidth = 1.2;
      g.setLineDash([4, 4]);
      for (const y of [y0 + 33, y0 + h - 33, y0 + 90, y0 + 168]) {
        g.beginPath(); g.moveTo(x0, y); g.lineTo(x0 + w, y); g.stroke();
      }
      g.setLineDash([]);
      g.fillStyle = "rgba(255,255,255,.22)";
      g.fillRect(x0 + 38, y0 + 34, 9, h - 68);
      g.fillStyle = "rgba(255,255,255,.10)";
      g.fillRect(x0 + 50, y0 + 34, 4, h - 68);
      g.restore();
      const ay = SACO_ALVO + PIVO.y;
      const aneis = [[30, "#fff4f6"], [23, "#e63950"], [15, "#fff4f6"], [7, "#e63950"]];
      for (const [r, cor] of aneis) {
        g.fillStyle = cor;
        g.beginPath(); g.ellipse(cx + 4, ay, r * 0.92, r, 0, 0, Math.PI * 2); g.fill();
      }
      retanguloRedondo(g, x0, y0, w, h, 26);
      g.strokeStyle = "#53202f";
      g.lineWidth = 3;
      g.stroke();
      return { c, largura: L, altura: A, cx };
    }

    /* A LUVA QUE VOA: vista por trás, como quem está dando o soco a vê —
       o punho grande em cima, o dedão do lado e o cano branco perto da
       câmera (a forma do ícone do original, Icones.luva, com volume). */
    function montarLuva() {
      const L = 220;
      const A = 250;
      const { c, g } = novaTela(L, A);
      const contorno = "#3b0d18";
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
      const vermelho = g.createRadialGradient(84, 62, 8, 110, 104, 128);
      vermelho.addColorStop(0, "#ff96a2");
      vermelho.addColorStop(0.3, "#f0253f");
      vermelho.addColorStop(0.75, "#b5132b");
      vermelho.addColorStop(1, "#6e0a18");
      g.save();
      g.translate(44, 122);
      g.rotate(-0.38);
      g.beginPath(); g.ellipse(0, 0, 28, 48, 0, 0, Math.PI * 2);
      g.fillStyle = vermelho; g.fill();
      g.strokeStyle = contorno; g.stroke();
      g.restore();
      retanguloRedondo(g, 54, 100, 116, 76, 26);
      g.fillStyle = vermelho; g.fill();
      g.strokeStyle = contorno; g.stroke();
      g.beginPath(); g.ellipse(114, 90, 80, 78, 0, 0, Math.PI * 2);
      g.fillStyle = vermelho; g.fill();
      g.strokeStyle = contorno; g.stroke();
      g.strokeStyle = "rgba(70,0,16,.55)";
      g.lineWidth = 3;
      g.beginPath(); g.ellipse(118, 66, 58, 30, 0, Math.PI * 0.08, Math.PI * 0.92); g.stroke();
      g.beginPath(); g.moveTo(66, 108); g.quadraticCurveTo(58, 140, 72, 170); g.stroke();
      g.fillStyle = "rgba(255,255,255,.55)";
      g.beginPath(); g.ellipse(84, 50, 26, 13, -0.55, 0, Math.PI * 2); g.fill();
      g.fillStyle = "rgba(255,255,255,.25)";
      g.beginPath(); g.ellipse(150, 120, 9, 22, 0.3, 0, Math.PI * 2); g.fill();
      return { c, largura: L, altura: A, centro: { x: 112, y: 92 } };
    }

    /* ------------------------------------------------------------------
       ESTADO
       ------------------------------------------------------------------ */
    // armado | voo | medindo | contando | veredito | maisForte |
    // desfecho (o fim da luta na arena) | nocauteado | subindo (saco) | fim
    let estado = "armado";
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
    let lutaComecou = false;
    // o saco de reserva: balanço de lado (ângulo) e recuo
    let anguloSaco = 0, velAngulo = 0, recuo = 0, velRecuo = 0, amasso = 0, alturaSaco = 0;
    // a luva
    let luvaT = -1;
    let luvaDe = { x: 0, y: 0 }, luvaPara = { x: 0, y: 0 }, luvaFinal = LUVA_NO_ROSTO;
    // efeitos de tela
    let clarao = 0, zoom = 1, hitstop = 0, brilhoGolpe = 0, pulo = 0;
    let tremorTela = 0;      // o tremor do golpe, só na imagem da arena (px de 1080)
    let torcidaEmPe = 0;
    let ondas = [], raios = [], confetes = [], rachaduras = null, estrelao = null, tunel = null;
    let faixas = [];         // FIGHT! / NEVER GIVE UP! / FIGHT TILL THE END
    // a luta (main.gd): as vidas, o desfecho e o nocaute no jogador
    let vidaJogador = 1, vidaJogadorFantasma = 1, vidaFantasma = 1;
    let jogadorNocauteado = false;
    let desfecho = "";
    let nocauteNaRodada = false;
    let koEm = -1, koACaminho = -1, koT = -1, koFim = -1, koPaciencia = 0, fimPorNocaute = -1;
    let ultimaReacao = "";
    let socoNaTelaEm = 5;
    let cambaleioT = -1, cambaleioDur = 1.6;
    let rachaduraTela = [], rachaduraTelaT = -1;

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
      lutaComecou = false;
      anguloSaco = 0; velAngulo = 0; recuo = 0; velRecuo = 0; amasso = 0; alturaSaco = 0;
      luvaT = -1;
      clarao = 0; zoom = 1; hitstop = 0; brilhoGolpe = 0; pulo = 0; torcidaEmPe = 0; tremorTela = 0;
      ondas = []; raios = []; confetes = []; rachaduras = null; estrelao = null; tunel = null;
      faixas = [];
      vidaJogador = 1; vidaJogadorFantasma = 1; vidaFantasma = 1;
      jogadorNocauteado = false;
      desfecho = "";
      nocauteNaRodada = false;
      koEm = -1; koACaminho = -1; koT = -1; koFim = -1; koPaciencia = 0; fimPorNocaute = -1;
      ultimaReacao = "";
      socoNaTelaEm = tempoDoAtaque();
      cambaleioT = -1;
      rachaduraTela = []; rachaduraTelaT = -1;
      partidas++;
      const a = arena3d();
      if (a) a.preparar();
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
      // o alvo pintado no saco de reserva, girando e recuando com ele
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
      const a = arena3d();
      if (a) {
        // a luva vai no queixo dele, onde ele estiver agora
        a.cabecaNaTela(pontoNaTela);
        luvaPara = { x: pontoNaTela.x + mao * 6, y: pontoNaTela.y + 12 };
        luvaFinal = LUVA_NO_ROSTO;
      } else {
        const alvo = alvoNaTela();
        luvaPara = { x: alvo.x + mao * 6, y: alvo.y + 26 };
        luvaFinal = LUVA_NO_SACO;
      }
      luvaDe = { x: 270 + mao * 150, y: 1090 };
      api.som("whoosh");
      // os cartazes saem da frente: o soco é que é o espetáculo agora
      for (const f of faixas) f.dur = Math.min(f.dur, Math.max(0, f.t - f.atraso) + 0.25);
    }

    function impacto() {
      const a = arena3d();
      const alvo = a ? ALVO : alvoNaTela();
      if (forcaTravada < FORCA_MINIMA) {
        // "abaixo disto não é soco": a máquina não conta e pede mais (lá a
        // placa recusa o golpe e o lutador nem fica sabendo)
        estado = "maisForte";
        tEstado = 0;
        velRecuo += 1.2;
        velAngulo += mao * 0.12;
        api.som("batida");
        api.som("erro");
        if (!a) api.tremer(3);
        api.efeitos.explosao(luvaPara.x, luvaPara.y, { cor: ["#8697b4", "#ffffff"], n: 8, velocidade: 160, tamanho: 3 });
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
      const indice = indiceDoNivel(notaAtual);
      nivelAtual = NIVEIS[indice];
      golpe(alvo, nivelAtual, indice);
      fraseAtual = GOLPES[nivelAtual.id][(semente + socos.length + 1) % 4];
      if (a) {
        // O SOCO ATRAVESSA A TELA E ACERTA ALGUÉM (main.gd, _registrar_impacto).
        // A arena recebe a posição do ponteiro — o papel da velocidade real
        // dentro da faixa do sensor — e o nível decide quem derruba: os que
        // têm hit-stop na tabela (NOCAUTE para cima).
        a.guardar(false);
        const derruba = nivelAtual.hitstop > 0;
        const ultimo = socos.length + 1 >= SOCOS;
        const reacao = a.golpe(forcaTravada, derruba, notaAtual, ultimo);
        ultimaReacao = reacao.nocaute ? "knockout" : reacao.reacao;
        if (reacao.nocaute) nocauteNaRodada = true;
        if (reacao.reacao === "cordas") fraseAtual = FRASES_CORDAS[(socos.length + 1) % 3];
        if (reacao.desdenhou) {
          // no meio da luta a torcida está do lado de quem bate
          fraseAtual = "ELE NEM SENTIU • TENTE MAIS FORTE";
          if (!ultimo) a.agitar(0.4, 2.5);
        }
        if (ultimo) fecharDesfecho();
        if (reacao.nocaute) fraseAtual = FRASES_NOCAUTE[(socos.length + 1) % 3];
      }
      estado = "medindo";
      tEstado = 0;
      mostrado = 0;
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
      // o saco de reserva: recua e balança na proporção do golpe
      velRecuo += 2.2 + potencia * 5.5;
      velAngulo += mao * (0.25 + potencia * 0.75) * sorteio(0.7, 1.1);
      amasso = 1;
      if (indice >= 2) { torcidaEmPe = 1; pulo = 1; }
      // O TREMOR DO GOLPE: na arena ele mora só DENTRO da imagem 3D (o
      // painel não treme); no ginásio de reserva, a tela inteira.
      if (arena3d()) tremorTela = Math.max(tremorTela, nivel.tremor);
      else api.tremer(nivel.tremor * 0.55);
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
      proximaFesta = 0.35;
      const melhor = Math.max(...socos);
      api.placar({ pontos: melhor, info: socos.length < SOCOS ? `SOCO ${socos.length + 1}/${SOCOS}` : "MELHOR SOCO" });
      api.som(indice >= 2 ? "combo" : indice >= 1 ? "acerto" : "nota");
      // NEVER GIVE UP! quando o soco foi fraco e ainda há chance
      if (indice === 0 && socos.length < SOCOS) {
        faixas.push({ img: img.never, x: 270, y: 300, largura: 330, t: 0, dur: 1.5, tipo: "bate", atraso: 0.3 });
      }
    }

    /* O PRÓXIMO SOCO: a máquina rearma, o lutador volta à guarda e a
       torcida chama o golpe (main.gd, _armar_proximo_soco). */
    function proximoSoco() {
      estado = "armado";
      tEstado = 0;
      fase = 0;
      forca = 0;
      vereditoT = -1;
      mao = -mao;
      torcidaEmPe = 0;
      const a = arena3d();
      if (a) {
        a.guardar(true);
        a.agitar(0.35, 2.5);
      }
      socoNaTelaEm = tempoDoAtaque();
      // O ÚLTIMO SOCO tem cartaz próprio: FIGHT TILL THE END
      if (socos.length === SOCOS - 1) {
        faixas.push({ img: img.ateOFim, x: 270, y: 318, largura: 380, t: 0, dur: 1.5, tipo: "desliza", atraso: 0 });
      }
    }

    /* QUANDO O LUTADOR VEM PARA CIMA: depois de um soco fraco ele vem logo,
       confiante; depois de um que doeu, demora mais (main.gd). */
    function tempoDoAtaque() {
      if (ultimaReacao === "taunt_weak") return sorteio(SOCO_NA_TELA_CONFIANTE[0], SOCO_NA_TELA_CONFIANTE[1]);
      const base = sorteio(SOCO_NA_TELA_PRIMEIRO[0], SOCO_NA_TELA_PRIMEIRO[1]);
      const a = arena3d();
      if (!ultimaReacao || !a) return base;
      return base + limitar(a.dano(), 0, 1) * 1.5;
    }

    /* O FIM DA RODADA NA ARENA: quem ganhou, e como a torcida reage.
       Batido forte (melhor soco de 6500 para cima, ou nocaute), ele fica
       zonzo e o ginásio pega fogo. Fraco, ele ganhou a luta — e isso tem
       de ser VISTO, nesta ordem: volta à guarda, vem para cima, acerta a
       câmera ("K.O.") e SÓ ENTÃO comemora. */
    function fecharDesfecho() {
      const a = arena3d();
      if (!a) return;
      const melhor = Math.max(notaAtual, ...socos);
      if (nocauteNaRodada) desfecho = "nocaute";
      else if (melhor >= NOTA_DA_VITORIA) desfecho = "vitoria";
      else if (melhor < NOTA_DO_EMPATE) desfecho = "derrota";
      else desfecho = "empate";
      a.fimDeRodada(desfecho);
      if (desfecho === "nocaute" || desfecho === "vitoria") {
        a.agitar(1.0, 7.5);
        return;
      }
      // O SOCO FINAL
      koEm = 0.9;
      koPaciencia = 0;
      if (desfecho === "empate") {
        fraseAtual = "ELE AGUENTOU… E AGORA VEM PRA CIMA!";
        a.agitar(0.45, 4.0);
      } else {
        fraseAtual = "ELE NÃO CAIU… E AGORA VEM PRA CIMA!";
      }
    }

    function esperaDoFim() {
      if (desfecho === "derrota" || desfecho === "empate") return ESPERA_DO_FIM_DEBOCHE;
      return ESPERA_DO_FIM_FESTA;
    }

    /* O NOCAUTE NO JOGADOR AINDA ESTÁ EM CENA: a luva a caminho, o "K.O."
       ou a festa de quem ganhou logo depois. Nada corta isso. */
    function nocauteEmCena() {
      return koEm >= 0 || koACaminho >= 0 || koT >= 0 || (koFim >= 0 && koFim < FESTA_DEPOIS_DO_KO);
    }

    /* A CONTAGEM DO NOCAUTE NO JOGADOR (main.gd, _passo_do_ko). */
    function passoDoKo(dt) {
      if (koEm >= 0) {
        koEm -= dt;
        if (koEm < 0) {
          const a = arena3d();
          if (a && a.nocauteNoJogador()) koACaminho = 2.2;     // espera a luva chegar
          else if (a && koPaciencia < KO_PACIENCIA) {
            // ainda reagindo ao soco (nas cordas, sentindo): ele termina e vem
            koPaciencia += 0.25;
            koEm = 0.25;
          } else levarKo();
        }
      }
      if (koACaminho >= 0) {
        koACaminho -= dt;
        if (koACaminho < 0) levarKo();
      }
      if (koT >= 0) {
        koT += dt;
        if (koT > KO_DURACAO) { koT = -1; koFim = 0; }
      } else if (koFim >= 0) {
        koFim += dt;
      }
    }

    /* A VIDA DO JOGADOR ACABOU: o lutador vem para o soco final. */
    function nocauteDoJogador() {
      if (jogadorNocauteado) return;
      jogadorNocauteado = true;
      vidaJogador = 0;
      desfecho = "derrota";
      fraseAtual = "VOCÊ DEMOROU… E ELE NÃO PERDOOU!";
      estado = "nocauteado";
      tEstado = 0;
      koEm = 0.15;
      // luva a caminho (até 2,2 s) + "K.O." + a queda assentando
      fimPorNocaute = 0.15 + 2.2 + KO_DURACAO + 0.6;
    }

    /* O jogador levou o nocaute: vidro estourado, tela vermelha, "K.O." —
       a câmera vai ao chão e SÓ AGORA quem ganhou comemora. */
    function levarKo() {
      koACaminho = -1;
      if (koT >= 0) return;
      levarSocoNaTela();
      vidaJogador = 0;
      api.som("strike");
      api.som("erro");
      tremorTela = Math.max(tremorTela, 40);
      clarao = Math.max(clarao, 0.30);
      koT = 0;
      if (!jogadorNocauteado) fraseAtual = FRASES_DERROTA[partidas % FRASES_DERROTA.length];
      const a = arena3d();
      if (a) {
        a.agitar(0.55, 7.0);
        a.jogadorNoChao(true);
        a.venceu(desfecho === "empate" ? "celebra" : "deboche");
      }
    }

    /* A LUVA DELE ACERTOU O VIDRO: som, tranco, rachadura e o cambaleio
       sorteado. Na espera, cada soco dele tira vida de quem demora. */
    function levarSocoNaTela() {
      if ((estado === "armado" || estado === "maisForte") && !jogadorNocauteado) {
        vidaJogador = Math.max(0, vidaJogador - DANO_DO_SOCO_NA_TELA);
        if (vidaJogador <= 0) nocauteDoJogador();
      }
      api.som("soco");
      api.som("batida");
      api.vibrar(80);
      tremorTela = Math.max(tremorTela, sorteio(24, 36));
      clarao = Math.max(clarao, 0.14);
      const cx = 270 + sorteio(-80, 80);
      const cy = 480 + sorteio(-100, 60);
      api.efeitos.explosao(cx, cy, { cor: [CREME, "#ffffff"], n: 14, velocidade: 550, tamanho: 3, gravidade: 300, vida: 0.6 });
      ondas.push({ x: cx, y: cy, r0: 20, r1: 260, cor: CREME, alfa: 0.6, largura: 5, t: 0, dur: 0.45 });
      montarRachaduraTela(cx, cy);
      // O CAMBALEIO É DA CÂMERA DA ARENA, e é liso: um balanço que morre
      // devagar, sorteado a cada vez.
      cambaleioT = 0;
      cambaleioDur = sorteio(1.3, 2.0);
      const a = arena3d();
      if (a) a.cambalear(cambaleioDur);
    }

    /* A rachadura do soco dele: galhos quebrados saindo do ponto, e o anel
       quebrado em volta (main.gd, _montar_rachadura). */
    function montarRachaduraTela(cx, cy) {
      rachaduraTela = [];
      rachaduraTelaT = 0;
      const dentro = (v, max) => limitar(v, 3, max - 3);
      const galhos = sorteioInteiro(6, 9);
      for (let i = 0; i < galhos; i++) {
        let ang = (i / galhos) * Math.PI * 2 + sorteio(-0.3, 0.3);
        let x = cx, y = cy;
        const linha = [x, y];
        const passos = sorteioInteiro(3, 6);
        for (let k = 0; k < passos; k++) {
          ang += sorteio(-0.45, 0.45);
          const passo = sorteio(20, 55);
          x = dentro(x + Math.cos(ang) * passo, LARGURA);
          y = dentro(y + Math.sin(ang) * passo, ALTURA);
          linha.push(x, y);
          if (Math.random() < 0.3) {
            const a2 = ang + sorteio(0.6, 1.2) * (Math.random() < 0.5 ? 1 : -1);
            const d2 = sorteio(15, 35);
            rachaduraTela.push([x, y, dentro(x + Math.cos(a2) * d2, LARGURA), dentro(y + Math.sin(a2) * d2, ALTURA)]);
          }
        }
        rachaduraTela.push(linha);
      }
      const anel = [];
      const raio = sorteio(17, 26);
      for (let k = 0; k < 13; k++) {
        const a = (k / 12) * Math.PI * 2;
        const r = raio * sorteio(0.8, 1.2);
        anel.push(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      }
      rachaduraTela.push(anel);
    }

    function encerrar() {
      if (terminou) return;
      terminou = true;
      const melhor = socos.length ? Math.max(...socos) : 0;
      const lista = socos.map((p) => p.toLocaleString("pt-BR")).join(" · ");
      let detalhe = socos.length ? `Seus socos: ${lista}. Vale o melhor.` : "Nenhum soco contado.";
      if (jogadorNocauteado) detalhe += " Você demorou e foi nocauteado.";
      api.terminar({
        pontos: melhor,
        titulo: jogadorNocauteado ? "VOCÊ PERDEU" : NIVEIS[indiceDoNivel(melhor)].nome,
        detalhe,
      });
    }

    /* ------------------------------------------------------------------
       O RELÓGIO
       ------------------------------------------------------------------ */
    function atualizar(dt) {
      relogio += dt;
      const a = arena3d();
      if (!lutaComecou) {
        // o "VAI!" do console: ele levanta a guarda e a torcida chama
        lutaComecou = true;
        if (a) { a.guardar(true); a.agitar(0.35, 2.5); }
      }
      // A ARENA ANDA NO RELÓGIO DO JOGO — inclusive no hit-stop, como lá.
      if (a) {
        a.avancar(dt);
        mundo.avancou = true;
        if (a.telaAtingida()) {
          // o nocaute vem primeiro: a luva final também chega na espera
          if (koACaminho >= 0) levarKo();
          else if (estado === "armado" || estado === "maisForte") levarSocoNaTela();
        }
      }
      passoDoKo(dt);
      passoDasVidas(dt);
      if (cambaleioT >= 0) { cambaleioT += dt; if (cambaleioT > cambaleioDur) cambaleioT = -1; }
      if (rachaduraTelaT >= 0) { rachaduraTelaT += dt; if (rachaduraTelaT > 1.4) rachaduraTelaT = -1; }
      tremorTela = Math.max(0, tremorTela - dt * 26);

      // efeitos que andam mesmo no hit-stop (são a "foto" do golpe)
      clarao = Math.max(0, clarao - dt * 2.6);
      brilhoGolpe = Math.max(0, brilhoGolpe - dt * 1.6);
      for (const f of faixas) f.t += dt;
      faixas = faixas.filter((f) => f.t < f.dur + f.atraso);

      if (hitstop > 0) { hitstop -= dt; return; }

      zoom += (1 - zoom) * Math.min(1, dt * 5);
      pulo = Math.max(0, pulo - dt * 1.4);
      amasso = Math.max(0, amasso - dt * 7);

      // o saco de reserva: duas molas amortecidas, uma de lado e uma de recuo
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
          esperarSoco(dt);
          break;
        }
        case "voo":
          if (tEstado >= VOO_DA_LUVA) impacto();
          break;
        case "maisForte":
          esperarSoco(dt);
          if (estado === "maisForte" && tEstado >= MAIS_FORTE_S) { estado = "armado"; tEstado = 0; fase = 0; }
          break;
        case "medindo":
          if (tEstado >= IMPACTO_DURACAO) { estado = "contando"; tEstado = 0; tique = 0; }
          break;
        case "contando": {
          const p = limitar(tEstado / CONTAGEM_DURACAO, 0, 1);
          mostrado = Math.round(notaAtual * (1 - Math.pow(1 - p, 2.2)));
          // os tiques da contagem, cada vez mais juntos
          const marca = Math.floor(Math.pow(p, 0.7) * 9);
          if (marca > tique) { tique = marca; api.som("clique"); }
          if (tEstado >= CONTAGEM_DURACAO) abrirVeredito();
          break;
        }
        case "veredito": {
          vereditoT += dt;
          fogos(dt);
          if (tEstado >= ESPERA_PARA_O_PROXIMO_SOCO + MEDIDOR_POP_S) {
            if (socos.length < SOCOS) proximoSoco();
            else if (a) { estado = "desfecho"; tEstado = 0; }
            else { estado = "subindo"; tEstado = 0; api.som("whoosh"); }
          }
          break;
        }
        case "desfecho":
          // a arena fica no ar: a festa de quem ganhou ou o K.O. e o deboche
          vereditoT += dt;
          fogos(dt);
          if (vereditoT >= esperaDoFim() && !nocauteEmCena()) { estado = "fim"; encerrar(); }
          break;
        case "nocauteado":
          if (fimPorNocaute >= 0) {
            fimPorNocaute -= dt;
            if (fimPorNocaute < 0) { fimPorNocaute = -1; estado = "fim"; encerrar(); }
          }
          break;
        case "subindo":
          // O SACO SOBE no fim da rodada, como na máquina (ginásio de reserva)
          vereditoT += dt;
          alturaSaco = 560 * Math.pow(limitar(tEstado / SUBIDA_DO_SACO, 0, 1), 2);
          if (tEstado >= SUBIDA_DO_SACO) { estado = "fim"; encerrar(); }
          break;
        default:
          break;
      }
    }

    /* QUEM DEMORA LEVA: de tempos em tempos o lutador avança e soca a
       câmera — é o jeito de a máquina dizer "vai, bate logo". */
    function esperarSoco(dt) {
      const a = arena3d();
      if (!a || jogadorNocauteado) return;
      socoNaTelaEm -= dt;
      if (socoNaTelaEm <= 0) {
        if (a.socoNaTela()) socoNaTelaEm = sorteio(SOCO_NA_TELA_DEPOIS[0], SOCO_NA_TELA_DEPOIS[1]);
        else socoNaTelaEm = 1.0;
      }
    }

    /* Os fogos de quem passou do NOCAUTE. */
    function fogos(dt) {
      if (nivelAtual.festa <= 0) return;
      proximaFesta -= dt;
      if (proximaFesta > 0) return;
      proximaFesta = nivelAtual.festa;
      const [cx, cy] = CEU[indiceCeu++ % CEU.length];
      const x = cx + sorteio(-20, 20), y = cy + sorteio(-15, 15);
      ondas.push({ x, y, r0: 3, r1: sorteio(100, 160), cor: CREME, alfa: 0.55, largura: 3.5, t: 0, dur: 0.85 });
      ondas.push({ x, y, r0: 2, r1: sorteio(75, 130), cor: nivelAtual.cor, alfa: 0.45, largura: 2.5, t: 0, dur: 1.05 });
      api.efeitos.explosao(x, y, { cor: FESTA, n: 12 + Math.round(nivelAtual.raios / 3), velocidade: 220, tamanho: 2.6, gravidade: 160, vida: 1.3 });
      api.som("tiro");
    }

    /* As barras de vida: a real cai na hora; o rastro branco desce devagar
       atrás dela, mostrando o tamanho do estrago. */
    function passoDasVidas(dt) {
      const a = arena3d();
      const vidaReal = 1 - limitar(a ? a.dano() : 0, 0, 1);
      if (vidaReal > vidaFantasma) vidaFantasma = vidaReal;
      vidaFantasma = moverAte(vidaFantasma, vidaReal, dt * 0.45);
      if (vidaJogador > vidaJogadorFantasma) vidaJogadorFantasma = vidaJogador;
      vidaJogadorFantasma = moverAte(vidaJogadorFantasma, vidaJogador, dt * 0.45);
    }

    /* ------------------------------------------------------------------
       O DESENHO
       ------------------------------------------------------------------ */
    function desenhar(ctx) {
      const t = relogio;
      if (mundo.estado === "pronto") desenharMundo3D(ctx);
      else if (mundo.estado === "falhou") desenharReserva(ctx, t);
      else desenharCarregando(ctx);

      desenharTunel(ctx);
      desenharOndas(ctx);
      desenharRaios(ctx);
      desenharEstrelao(ctx);

      // O RODAPÉ ESCURECE para os textos grandes, por cima do 3D
      desenharRodape(ctx);
      if (mundo.estado !== "falhou") desenharPainelDoAlto(ctx, t);
      desenharMarca(ctx);
      desenharFaixas(ctx);

      desenharMedidor(ctx, t);
      desenharChamada(ctx, t);
      desenharCartoes(ctx, t);

      // a luva vem da câmera: passa por cima de tudo, até do rodapé
      desenharLuva(ctx);
      desenharRachaduras(ctx);
      desenharConfetes(ctx);
      desenharSocoNaTela(ctx);
      desenharKo(ctx);
      if (clarao > 0.01) {
        ctx.fillStyle = `rgba(255,250,240,${(clarao * 0.85).toFixed(3)})`;
        ctx.fillRect(0, 0, LARGURA, ALTURA);
      }
      desenharTarjas(ctx);
      desenharLogoDoAlto(ctx);
    }

    /* A ARENA NA TELA. O 3D é desenhado no seu canvas e colado aqui; o
       TREMOR E O ZOOM DO GOLPE moram só dentro da imagem (ArenaQuadro.imagem):
       letreiros, placar e cartões ficam parados. */
    function desenharMundo3D(ctx) {
      const a = mundo.arena;
      const r = mundo.renderizador;
      const agora = performance.now();
      // fora da partida (capa, contagem, fim) o lutador continua vivo
      if (!mundo.avancou && mundo.relogio > 0) a.avancar(Math.min(0.1, Math.max(0, (agora - mundo.relogio) / 1000)));
      mundo.avancou = false;
      vigiar((agora - mundo.relogio) / 1000);
      mundo.relogio = agora;
      const razao = limitar(ctx.canvas.width / LARGURA, 1, NITIDEZ_3D_MAXIMA) * ESCALA_DO_DEGRAU[mundo.degrau];
      const w = Math.round(LARGURA * razao);
      const h = Math.round(ALTURA * razao);
      if (w !== mundo.largura || h !== mundo.altura) {
        r.setSize(w, h, false);
        mundo.largura = w;
        mundo.altura = h;
      }
      r.render(a.cena, a.camera);
      let dx = 0, dy = 0;
      if (tremorTela > 0.1 && !api.reduzido) {
        const tr = Math.min(tremorTela * 0.6, 22) * 0.5;
        dx = sorteio(-tr, tr);
        dy = sorteio(-tr, tr);
      }
      const z0 = api.reduzido ? 1 : zoom;
      if (dx === 0 && dy === 0 && z0 <= 1.0001) {
        ctx.drawImage(mundo.tela, 0, 0, w, h, 0, 0, LARGURA, ALTURA);
        return;
      }
      const folga = 1 + 2 * Math.max(Math.abs(dx) / LARGURA, Math.abs(dy) / ALTURA) + 0.002;
      const z = Math.max(z0, folga);
      const fw = w / z, fh = h / z, px = w / LARGURA;
      const ix = limitar((w - fw) * 0.5 - (dx * px) / z, 0, w - fw);
      const iy = limitar((h - fh) * 0.5 - (dy * px) / z, 0, h - fh);
      ctx.drawImage(mundo.tela, ix, iy, fw, fh, 0, 0, LARGURA, ALTURA);
    }

    /* O VIGIA DE DESEMPENHO: a média do quadro de verdade, de tempos em
       tempos; lenta, a arena desce um degrau. Um quadro de mais de um
       quarto de segundo é a aba que voltou, não lentidão — não conta. */
    function vigiar(passoReal) {
      if (!(passoReal > 0) || passoReal > 0.25) return;
      mundo.quadros++;
      mundo.somaDosQuadros += passoReal;
      if (mundo.quadros < QUADROS_DO_VIGIA) return;
      const media = mundo.somaDosQuadros / mundo.quadros;
      mundo.quadros = 0;
      mundo.somaDosQuadros = 0;
      if (media > QUADRO_LENTO && mundo.degrau < ESCALA_DO_DEGRAU.length - 1) {
        mundo.degrau++;
        if (mundo.degrau >= 1) mundo.arena.enfeites(false);
      }
    }

    /* Enquanto o three.js e o boxeador chegam: o ginásio escuro e um anel
       que gira (girando, prova que o programa está vivo). */
    function desenharCarregando(ctx) {
      ctx.fillStyle = "#07051a";
      ctx.fillRect(0, 0, LARGURA, ALTURA);
      const nevoa = ctx.createRadialGradient(270, 420, 20, 270, 420, 360);
      nevoa.addColorStop(0, "rgba(138,60,255,.20)");
      nevoa.addColorStop(1, "rgba(138,60,255,0)");
      ctx.fillStyle = nevoa;
      ctx.fillRect(0, 0, LARGURA, ALTURA);
      const giro = performance.now() / 1000 * 3.4;
      ctx.save();
      ctx.lineCap = "round";
      ctx.lineWidth = 5;
      ctx.strokeStyle = comAlfa(AMBAR, 0.16);
      ctx.beginPath(); ctx.arc(270, 430, 28, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = AMBAR;
      ctx.beginPath(); ctx.arc(270, 430, 28, giro, giro + 1.5); ctx.stroke();
      ctx.lineWidth = 4;
      ctx.strokeStyle = comAlfa(AMBAR, 0.55);
      ctx.beginPath(); ctx.arc(270, 430, 17, -giro * 0.7, -giro * 0.7 + 0.9); ctx.stroke();
      ctx.restore();
      api.texto(ctx, "MONTANDO O RINGUE…", 270, 490, { tamanho: 15, cor: TINTA_LEVE, peso: 800 });
    }

    /* O GINÁSIO 2D DE RESERVA, com o zoom do golpe em volta do saco. */
    function desenharReserva(ctx, t) {
      if (!reserva) reserva = { fundo: montarFundo(), ringue: montarRingue(), saco: montarSaco() };
      const alvo = alvoNaTela();
      ctx.save();
      if (zoom > 1.001) {
        ctx.translate(alvo.x, alvo.y);
        ctx.scale(zoom, zoom);
        ctx.translate(-alvo.x, -alvo.y);
      }
      ctx.drawImage(reserva.fundo, 0, 0, LARGURA, 640);
      ctx.fillStyle = "#07051a";
      ctx.fillRect(0, 640, LARGURA, ALTURA - 640);
      desenharFachos(ctx, t);
      desenharTorcida(ctx, t);
      ctx.drawImage(reserva.ringue, 0, 0, LARGURA, 660);
      desenharSaco(ctx);
      ctx.restore();
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
    }

    function desenharSaco(ctx) {
      const s = reserva.saco;
      const escala = 1 - 0.16 * recuo;
      const y0 = PIVO.y - alturaSaco - recuo * 26;
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
      if (brilhoGolpe > 0.02 && estado !== "armado") {
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = brilhoGolpe * 0.35;
        ctx.fillStyle = nivelAtual.cor;
        retanguloRedondo(ctx, -s.cx + 10, 220, 140, 252, 26);
        ctx.fill();
      }
      ctx.restore();
    }

    /* O RODAPÉ ESCURO (main.gd, RODAPE_ESCURO): um degradê só. */
    function desenharRodape(ctx) {
      if (!degradeDoRodape) {
        degradeDoRodape = ctx.createLinearGradient(0, ALTURA - RODAPE_ESCURO, 0, ALTURA);
        degradeDoRodape.addColorStop(0, "rgba(8,3,20,0)");
        degradeDoRodape.addColorStop(1, "rgba(8,3,20,.86)");
      }
      ctx.fillStyle = degradeDoRodape;
      ctx.fillRect(0, ALTURA - RODAPE_ESCURO, LARGURA, RODAPE_ESCURO);
    }

    /* O PAINEL DE LUTA DENTRO DO QUADRO: faixa escura no alto, a vida do
       JOGADOR à esquerda (o tempo dele) e a do ADVERSÁRIO à direita,
       espelhada, de frente uma para a outra; o round no meio. */
    function desenharPainelDoAlto(ctx, t) {
      ctx.fillStyle = "rgba(5,0,15,.55)";
      ctx.fillRect(0, 0, LARGURA, FAIXA_DO_ALTO);
      ctx.fillStyle = "rgba(5,0,15,.25)";
      ctx.fillRect(0, FAIXA_DO_ALTO, LARGURA, 9);
      const a = arena3d();
      const dano = a ? a.dano() : 0;
      // NA LONA, A PERCENTAGEM NÃO É MAIS A NOTÍCIA
      const estadoDele = a && a.naLona() ? "NA LONA" : estadoDoDano(dano);
      desenharVida(ctx, vidaJogador, vidaJogadorFantasma, t, jogadorNocauteado ? "VOCÊ  •  NOCAUTEADO" : "VOCÊ", VIDA_JOGADOR, false, "#3ec8ff");
      desenharVida(ctx, 1 - limitar(dano, 0, 1), vidaFantasma, t, "ADVERSÁRIO  •  " + estadoDele, VIDA_ADVERSARIO, true, null);
      api.texto(ctx, "R" + Math.min(socos.length + 1, SOCOS), 270, 107, { tamanho: 18, cor: AMBAR, peso: 900, base: "alphabetic" });
    }

    /* Uma faixa inclinada da barra de vida (ArenaQuadro._faixa). */
    function faixaDaVida(ctx, x0, x1, y0, y1, c0, c1, inc) {
      if (x1 - x0 < 0.5) return;
      const d = (inc * (y1 - y0)) / VIDA_ADVERSARIO.h;
      const g = ctx.createLinearGradient(x0, 0, x1, 0);
      g.addColorStop(0, c0);
      g.addColorStop(1, c1);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.moveTo(x0 + d, y0);
      ctx.lineTo(x1 + d, y0);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x0, y1);
      ctx.closePath();
      ctx.fill();
    }

    function trechoDaVida(espelho, x0, larg, a, b) {
      return espelho ? [x0 + larg * (1 - b), x0 + larg * (1 - a)] : [x0 + larg * a, x0 + larg * b];
    }

    /* A BARRA DE VIDA, a leitura de jogo de luta (ArenaQuadro.vida): moldura
       de ouro, o rastro do golpe, o vidro na metade de cima e o reflexo
       correndo. `espelho` enche da direita para a esquerda. */
    function desenharVida(ctx, vida, fantasma, t, rotulo, r, espelho, corBase) {
      const v = limitar(vida, 0, 1);
      const f = limitar(Math.max(fantasma, v), 0, 1);
      const inc = espelho ? -INCLINA : INCLINA;
      const larg = r.w - INCLINA;
      const x0 = r.x + (espelho ? INCLINA : 0);
      const y0 = r.y;
      const y1 = r.y + r.h;
      faixaDaVida(ctx, x0 - 5, x0 + larg + 5, y0 - 3.5, y1 + 3.5, "rgba(0,0,0,.55)", "rgba(0,0,0,.55)", inc);
      faixaDaVida(ctx, x0 - 3, x0 + larg + 3, y0 - 2, y1 + 2, OURO_ESC, OURO, inc);
      faixaDaVida(ctx, x0, x0 + larg, y0, y1, "#0c0615", "#1c1030", inc);
      if (f > v) {
        const [ra, rb] = trechoDaVida(espelho, x0, larg, v, f);
        faixaDaVida(ctx, ra, rb, y0, y1, "#ff3baa", "rgba(255,255,255,.9)", inc);
      }
      let cor = misturar(VERDE, AMBAR, limitar((1 - v) / 0.5, 0, 1));
      cor = misturar(cor, VERMELHO, limitar((0.5 - v) / 0.35, 0, 1));
      if (corBase) cor = misturar(corBase, VERMELHO, limitar((0.45 - v) / 0.35, 0, 1));
      if (v < 0.25) cor = misturar(cor, "#ffffff", 0.30 * (0.5 + 0.5 * Math.sin(t * 12)));
      const [ca, cb] = trechoDaVida(espelho, x0, larg, 0, v);
      const c0 = escurecer(cor, 0.35);
      const c1 = clarear(cor, 0.15);
      faixaDaVida(ctx, ca, cb, y0, y1, espelho ? c1 : c0, espelho ? c0 : c1, inc);
      faixaDaVida(ctx, ca, cb, y0, y0 + r.h * 0.42, "rgba(255,255,255,.22)", "rgba(255,255,255,.10)", inc);
      const brilho = ((t * 0.45) % 1.6) - 0.3;
      if (brilho > 0 && brilho < v) {
        const [ba, bb] = trechoDaVida(espelho, x0, larg, brilho, Math.min(brilho + 35 / larg, v));
        faixaDaVida(ctx, ba, bb, y0, y1, "rgba(255,255,255,0)", "rgba(255,255,255,.35)", inc);
      }
      // o rótulo em cima, do lado de fora; o número embaixo, do lado de dentro
      api.texto(ctx, rotulo, espelho ? r.x + r.w : r.x, y0 - 7, {
        tamanho: 13, cor: "#ffffff", alinhar: espelho ? "right" : "left", peso: 800, contorno: ESCURO, base: "alphabetic",
      });
      api.texto(ctx, Math.round(v * 100) + "%", espelho ? r.x : r.x + r.w, y1 + 17, {
        tamanho: 14, cor: clarear(cor, 0.2), alinhar: espelho ? "left" : "right", peso: 900, contorno: ESCURO, base: "alphabetic",
      });
    }

    /* A MARCA DA CASA, no alto à direita, logo abaixo da vida dele. */
    function desenharMarca(ctx) {
      const m = img.marca;
      if (!m || !m.naturalHeight) return;
      const h = MARCA.altura;
      const w = Math.round(h * m.naturalWidth / m.naturalHeight);
      ctx.drawImage(m, MARCA.x - w, MARCA.y, w, h);
    }

    /* O LOGO DO JOGO NO ALTO, por cima da tarja, entre as duas vidas. */
    function desenharLogoDoAlto(ctx) {
      const l = img.logo;
      if (!l || !l.naturalWidth) return;
      const w = LOGO_DO_ALTO.largura;
      const h = w * l.naturalHeight / l.naturalWidth;
      ctx.drawImage(l, LOGO_DO_ALTO.x - w / 2, LOGO_DO_ALTO.y - h / 2, w, h);
    }

    function desenharLuva(ctx) {
      if (luvaT < 0) return;
      const s = spriteLuva;
      // a ida: acelera até o rosto dele (o soco), o rastro fica para trás
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
        escala: 2.5 + (luvaFinal - 2.5) * q,
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

    /* O SOCO DELE NA TELA: o vidro racha e a vista escurece nas bordas,
       avermelhada, e volta (main.gd, _draw_soco_na_tela). */
    function desenharSocoNaTela(ctx) {
      if (rachaduraTelaT >= 0 && rachaduraTela.length) {
        const a = 1 - limitar((rachaduraTelaT - 0.5) / 0.9, 0, 1);
        ctx.save();
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        for (const [cor, largura] of [[`rgba(0,0,0,${(0.35 * a).toFixed(3)})`, 3], [`rgba(255,250,242,${(0.85 * a).toFixed(3)})`, 1.25]]) {
          ctx.strokeStyle = cor;
          ctx.lineWidth = largura;
          ctx.beginPath();
          for (const l of rachaduraTela) {
            ctx.moveTo(l[0], l[1]);
            for (let i = 2; i < l.length; i += 2) ctx.lineTo(l[i], l[i + 1]);
          }
          ctx.stroke();
        }
        ctx.restore();
      }
      if (cambaleioT >= 0) {
        const v = Math.pow(1 - limitar(cambaleioT / cambaleioDur, 0, 1), 2) * 0.5;
        const borda = 55;
        ctx.fillStyle = `rgba(89,0,20,${v.toFixed(3)})`;
        ctx.fillRect(0, 0, LARGURA, borda);
        ctx.fillRect(0, ALTURA - borda, LARGURA, borda);
        ctx.fillRect(0, borda, borda, ALTURA - borda * 2);
        ctx.fillRect(LARGURA - borda, borda, borda, ALTURA - borda * 2);
      }
    }

    /* O "K.O." NA TELA: pisca em vermelho, cresce num tranco e assenta;
       embaixo, quem levou (main.gd, _draw_ko). */
    function desenharKo(ctx) {
      if (koT < 0) return;
      const entra = limitar(koT / 0.18, 0, 1);
      const sai = 1 - limitar((koT - (KO_DURACAO - 0.5)) / 0.5, 0, 1);
      const a = entra * sai;
      const pisca = 0.5 + 0.5 * Math.sin(koT * 18) * Math.exp(-koT * 1.5);
      ctx.fillStyle = `rgba(140,0,15,${((0.30 + 0.20 * pisca) * a).toFixed(3)})`;
      ctx.fillRect(0, 0, LARGURA, ALTURA);
      const tranco = 1 + 0.45 * Math.exp(-koT * 9) * Math.cos(koT * 30);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(270, 460);
      ctx.scale(tranco, tranco);
      api.texto(ctx, "K.O.", 0, 30, { tamanho: 115, cor: "#ff2e47", peso: 900, contorno: "#0e0624", sombra: "#ff2e47", base: "alphabetic" });
      ctx.restore();
      ctx.save();
      ctx.globalAlpha = a;
      api.texto(ctx, "VOCÊ FOI NOCAUTEADO", 270, 545, { tamanho: 29, cor: "#ffffff", peso: 900, contorno: "#0e0624", base: "alphabetic" });
      ctx.restore();
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
       arco de 270° fechado embaixo, 40 gomos, o aro do original por fora,
       no canto esquerdo sobre a torcida. Na espera do soco ele é o
       ponteiro de força; depois do golpe ele vira o placar que conta a nota. */
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
      // NOCAUTEADO NA ESPERA: o mostrador diz o que aconteceu
      const caiu = estado === "nocauteado" || (jogadorNocauteado && estado === "fim");
      const melhor = socos.length ? Math.max(...socos) : 0;
      const fracaoNota = Math.sqrt(limitar((caiu ? melhor : mostrado) / SCORE_MAX, 0, 1));
      const fracao = armado || lendo ? (estado === "armado" ? forca : forcaTravada) : fracaoNota;
      let cor;
      if (caiu) cor = socos.length ? COR_FAIXA[faixaDe(melhor)] : VERMELHO;
      else if (armado || lendo) cor = corDaZona(fracao);
      else if (vereditoT >= 0) cor = COR_FAIXA[faixaDe(notaAtual)];
      else cor = misturar(AMBAR, COR_FAIXA[faixaDe(notaAtual)], limitar(tEstado / CONTAGEM_DURACAO, 0, 1) * 0.82);
      const naZonaVermelha = estado === "armado" && forca >= ZONA_FORTE;
      const pop = !caiu && vereditoT >= 0 && vereditoT < MEDIDOR_POP_S ? Math.sin(Math.PI * vereditoT / MEDIDOR_POP_S) : 0;

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
      } else if (caiu && !socos.length) {
        // nocauteado sem socar: nada de placar "0" (lia como soco fraco)
        api.texto(ctx, "K.O.", cx, cy - 4, { tamanho: 40, cor: "#ffffff", peso: 900, contorno: "#0e0624", sombra: cor });
        rotulo = "NENHUM SOCO";
      } else {
        let escala = 1;
        if (estado === "contando") escala = 0.55 + 0.45 * suavizar(tEstado / CONTAGEM_DURACAO);
        escala += 0.24 * pop;
        const texto = lendo ? "- - -" : String(caiu ? melhor : mostrado);
        ctx.save();
        ctx.translate(cx, cy - 4);
        ctx.scale(escala, escala);
        api.texto(ctx, texto, 0, 0, {
          tamanho: texto.length <= 3 ? 50 : 42, cor: lendo ? AMBAR : "#ffffff", peso: 900, contorno: "#0e0624", sombra: cor,
        });
        ctx.restore();
        rotulo = caiu ? "MELHOR SOCO" : lendo ? "LENDO SENSOR" : vereditoT >= 0 ? "PONTOS" : "CONTANDO";
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
      if (estado === "nocauteado" || (jogadorNocauteado && estado === "fim")) {
        api.texto(ctx, "VOCÊ CAIU!", 270, CHAMADA_Y, { tamanho: 40, cor: VERMELHO, peso: 900, contorno: "#0e0624" });
        api.texto(ctx, "A VIDA ACABOU  •  ELE NÃO ESPEROU", 270, FRASE_Y, { tamanho: 14, cor: "#ffffff", peso: 800 });
        return;
      }
      if (estado === "veredito" || estado === "subindo" || estado === "desfecho" || estado === "fim") {
        // A FAIXA ESCURA DO VEREDITO: o nome do nível na cor dele, sobre
        // um fundo que dá contraste a qualquer cor
        const abre = limitar(vereditoT / 0.25, 0, 1);
        const cor = nivelAtual.cor;
        const topo = VEREDITO_TOPO, base = VEREDITO_BASE;
        ctx.save();
        ctx.globalAlpha = abre;
        ctx.fillStyle = "rgba(12,6,21,.80)";
        ctx.beginPath();
        ctx.moveTo(0, topo + 9); ctx.lineTo(LARGURA, topo - 9); ctx.lineTo(LARGURA, base - 9); ctx.lineTo(0, base + 9);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = cor;
        ctx.lineWidth = 1.5;
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
        api.texto(ctx, fraseAtual, 270, FRASE_Y, { tamanho: 15, cor: AMBAR, peso: 800 });
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
        ctx.globalAlpha = 0.86;
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
        destruido = true;
        ondas = []; raios = []; confetes = []; faixas = [];
        try {
          if (mundo.arena) mundo.arena.destruir();
          if (mundo.renderizador) {
            mundo.renderizador.dispose();
            mundo.renderizador.forceContextLoss();
          }
        } catch (erro) { /* o contexto já tinha ido embora */ }
        mundo.arena = null;
        mundo.renderizador = null;
        mundo.tela = null;
        mundo.estado = "falhou";
      },
    };
  },
};
