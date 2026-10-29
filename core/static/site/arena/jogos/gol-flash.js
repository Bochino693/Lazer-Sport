/* ======================================================================
   GOL FLASH ARENA — "Acerte, marque e seja o craque", em miniatura.

   Na máquina de verdade o gol tem SETE ALVOS DE LUZ (os sensores A a G,
   cada um com um anel de LED). O jogo acende de 1 a 3 deles por vez, cada
   um numa cor sorteada entre amarelo, vermelho, verde e azul; a bola que
   entra num anel aceso é GOOOL!, o anel apaga e outro acende no lugar.
   Chutar num anel apagado é erro (o LED pisca vermelho). Cada jogador tem
   um tempo, e a torcida reage: canta a cada 10 gols, faz pressão quando o
   gol demora, comemora o combo e vaia quem termina com menos de 15.

   O que veio do jogo original (beta7/scripts/play.gd):
     - LEDS_TOTAL = 7, de 1 a 3 acesos (LEDS_ATIVOS_MIN/MAX), cores de
       CORES_ALVOS_RGB; o grupo se completa 0,08 s depois de um acerto;
     - ALVO_TIMEOUT: 15 s sem acerto troca o grupo inteiro;
     - COMBO: 4 gols ou mais em 6 s; a torcida canta a cada 10 gols;
       PRESSÃO depois de 9 s sem gol; vaia abaixo de 15 gols;
     - os textos: "MARQUE O MÁXIMO DE GOLS", "GOOOL!" com "+N", "TEMPO
       ESGOTADO", "PLAYER 1 FINALIZOU COM N GOLS", o painel do player com
       GOL e TEMPO e o fundo na cor (fundos/*.png).
   O que a miniatura acrescenta, porque a tela não tem sensor: cada anel
   aceso tem uma vida curta e APAGA sozinho, e o gol vale mais quanto mais
   rápido ele sai depois de o anel acender. O tempo é de 45 s (60 s na
   máquina).
   ====================================================================== */

const LARGURA = 960;
const ALTURA = 540;
const NITIDEZ = 2;

/* ----------------------------------------------------------------------
   REGRAS (play.gd)
   ---------------------------------------------------------------------- */
const TEMPO_DE_JOGO = 45;
const LEDS_TOTAL = 7;
const LEDS_ATIVOS_MIN = 1;
const LEDS_ATIVOS_MAX = 3;
const LETRAS = ["A", "B", "C", "D", "E", "F", "G"];
const COMPLETAR_DEPOIS = 0.08;       // o grupo se completa logo depois do acerto
const ALVO_TIMEOUT = 15;             // sem acerto por 15 s: troca o grupo
const COMBO_JANELA = 6;
const COMBO_MIN_GOLS = 4;            // "mais que 3" gols
const PONTOS_PARA_TORCIDA = 10;
const PRESSAO_JANELA = 9;
const GOLS_MINIMOS_SEM_VAIA = 15;

/* A vida de um anel aceso (a regra nova da miniatura): começa folgada e
   aperta conforme a partida anda. */
const VIDA_DO_ANEL_INICIO = 3.6;
const VIDA_DO_ANEL_FIM = 2.3;
const PONTOS_BASE = 100;
const PONTOS_RAPIDEZ = 100;          // o bônus inteiro, para quem chuta no instante em que acende

/* As cores dos alvos: amarelo, vermelho, verde e azul fortes (os RGB puros
   do original), com o "miolo" claro que um LED aceso tem. O azul puro some
   no escuro; o tom aqui é o que o anel de LED parece de verdade. */
const CORES = [
  { nome: "amarelo", cor: "#ffe600", luz: "#fff8b0" },
  { nome: "vermelho", cor: "#ff2626", luz: "#ffb6ae" },
  { nome: "verde", cor: "#22ff4a", luz: "#c2ffcc" },
  { nome: "azul", cor: "#2f6bff", luz: "#b4c8ff" },
];
const COR_PLAYER = "#1abfff";        // cores_players[0]: Color(0.1, 0.75, 1.0)
const OURO = "#ffd914";

/* ----------------------------------------------------------------------
   GEOMETRIA DA TELA
   Os sete alvos ficam num arco em volta da marca do pênalti, cada um a
   20° do vizinho: é a DIREÇÃO do chute que escolhe o anel, e no arco
   todos ficam à mesma distância da bola — nenhum é mais fácil que outro.
   ---------------------------------------------------------------------- */
const MARCA = { x: 480, y: 476 };
const BOLA_RAIO = 21;
const ARCO_RAIO = 280;
const PASSO_ANGULAR = (20 * Math.PI) / 180;
const ANEL_RAIO = 34;
const TOLERANCIA = (7.5 * Math.PI) / 180; // meia largura angular do anel
const LIMITE_DA_TRAVE = (68 * Math.PI) / 180;
const GOL = {
  frente: { x0: 168, x1: 792, topo: 116, chao: 406 },
  fundo: { x0: 198, x1: 762, topo: 136, chao: 392 },
};
const PAINEL_E = { x: 14, y: 430, w: 200, h: 96 };
const PAINEL_D = { x: 746, y: 430, w: 200, h: 96 };

function limitar(v, a, b) { return v < a ? a : v > b ? b : v; }
function sorteio(a, b) { return a + Math.random() * (b - a); }
function sorteioInteiro(a, b) { return Math.floor(a + Math.random() * (b - a + 1)); }
function voltaComPasso(t, forca = 1.7) { const p = limitar(t, 0, 1) - 1; return p * p * ((forca + 1) * p + forca) + 1; }

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

export default {
  largura: LARGURA,
  altura: ALTURA,
  artes: {
    estadio: "gol-flash/estadio.webp",
    amarelo: "gol-flash/amarelo.webp",
    vermelho: "gol-flash/vermelho.webp",
    verde: "gol-flash/verde.webp",
    azul: "gol-flash/azul.webp",
  },

  criar(api) {
    const img = api.img;

    /* ------------------------------------------------------------------
       OS ANÉIS: posição fixa no arco, estado de LED
       ------------------------------------------------------------------ */
    const aneis = [];
    for (let i = 0; i < LEDS_TOTAL; i++) {
      const angulo = (i - 3) * PASSO_ANGULAR;
      aneis.push({
        i,
        angulo,
        x: MARCA.x + Math.sin(angulo) * ARCO_RAIO,
        y: MARCA.y - Math.cos(angulo) * ARCO_RAIO,
        aceso: false, cor: 0, vida: 0, total: 1, reservado: false,
        acendeu: 0, flash: 0, erro: 0, apagando: 0,
      });
    }

    /* ------------------------------------------------------------------
       AS CAMADAS PRONTAS (desenhadas uma vez)
       ------------------------------------------------------------------ */
    const camadaFundo = montarFundo();
    const camadaTrave = montarTrave();
    const spritesAceso = CORES.map((c) => montarAnel(c.cor, c.luz));
    const spriteErro = montarAnel("#ff2020", "#ffd0d0");
    const spriteBola = montarBola();

    function montarFundo() {
      const { c, g } = novaTela(LARGURA, ALTURA);
      if (img.estadio) g.drawImage(img.estadio, 0, 0, LARGURA, ALTURA);
      else { g.fillStyle = "#061226"; g.fillRect(0, 0, LARGURA, ALTURA); }
      const { frente: f, fundo: b } = GOL;
      // O PAINEL DOS ALVOS: a "parede" do gol da máquina, escura, com a rede
      // por trás aparecendo de leve
      const painel = g.createLinearGradient(0, b.topo, 0, b.chao);
      painel.addColorStop(0, "rgba(6,14,32,.94)");
      painel.addColorStop(1, "rgba(3,8,20,.96)");
      g.fillStyle = painel;
      g.fillRect(b.x0, b.topo, b.x1 - b.x0, b.chao - b.topo);
      g.save();
      g.beginPath();
      g.rect(b.x0, b.topo, b.x1 - b.x0, b.chao - b.topo);
      g.clip();
      g.strokeStyle = "rgba(160,200,255,.07)";
      g.lineWidth = 1;
      g.beginPath();
      for (let x = b.x0 - 300; x < b.x1 + 300; x += 16) {
        g.moveTo(x, b.topo); g.lineTo(x + 260, b.chao);
        g.moveTo(x + 260, b.topo); g.lineTo(x, b.chao);
      }
      g.stroke();
      // a luz dos refletores lavando o alto do painel
      const luz = g.createRadialGradient(480, b.topo - 40, 20, 480, b.topo - 40, 420);
      luz.addColorStop(0, "rgba(90,170,255,.22)");
      luz.addColorStop(1, "rgba(90,170,255,0)");
      g.fillStyle = luz;
      g.fillRect(b.x0, b.topo, b.x1 - b.x0, b.chao - b.topo);
      g.restore();
      // AS REDES DOS LADOS E DO TETO, entre a trave da frente e o fundo
      const redes = [
        [[f.x0, f.topo], [b.x0, b.topo], [b.x0, b.chao], [f.x0, f.chao]],
        [[f.x1, f.topo], [b.x1, b.topo], [b.x1, b.chao], [f.x1, f.chao]],
        [[f.x0, f.topo], [f.x1, f.topo], [b.x1, b.topo], [b.x0, b.topo]],
      ];
      for (const r of redes) {
        g.save();
        g.beginPath();
        r.forEach(([x, y], k) => (k ? g.lineTo(x, y) : g.moveTo(x, y)));
        g.closePath();
        g.fillStyle = "rgba(4,10,24,.55)";
        g.fill();
        g.clip();
        g.strokeStyle = "rgba(220,235,255,.26)";
        g.lineWidth = 0.9;
        g.beginPath();
        for (let k = -600; k < 1600; k += 11) {
          g.moveTo(k, 0); g.lineTo(k + 540, 540);
          g.moveTo(k + 540, 0); g.lineTo(k, 540);
        }
        g.stroke();
        g.restore();
      }
      // a moldura do fundo do gol, fina
      g.strokeStyle = "rgba(200,220,255,.35)";
      g.lineWidth = 2;
      g.strokeRect(b.x0, b.topo, b.x1 - b.x0, b.chao - b.topo);
      // OS SETE ALVOS APAGADOS (o encaixe de cada sensor, com a letra dele)
      for (const a of aneis) desenharAnelApagado(g, a.x, a.y, LETRAS[a.i]);
      // a marca do pênalti e a sombra da bola
      g.fillStyle = "rgba(255,255,255,.75)";
      g.beginPath(); g.ellipse(MARCA.x, MARCA.y + BOLA_RAIO + 3, 9, 3, 0, 0, Math.PI * 2); g.fill();
      return c;
    }

    function desenharAnelApagado(g, x, y, letra) {
      const buraco = g.createRadialGradient(x, y - 4, 2, x, y, ANEL_RAIO - 6);
      buraco.addColorStop(0, "#0b1424");
      buraco.addColorStop(1, "#010309");
      g.fillStyle = buraco;
      g.beginPath(); g.arc(x, y, ANEL_RAIO - 5, 0, Math.PI * 2); g.fill();
      g.strokeStyle = "#1b2436";
      g.lineWidth = 8;
      g.beginPath(); g.arc(x, y, ANEL_RAIO - 3, 0, Math.PI * 2); g.stroke();
      g.strokeStyle = "rgba(150,170,200,.28)";
      g.lineWidth = 1.2;
      g.beginPath(); g.arc(x, y, ANEL_RAIO + 1.5, 0, Math.PI * 2); g.stroke();
      // os LEDs apagados do anel
      g.fillStyle = "#3a465c";
      for (let k = 0; k < 20; k++) {
        const a = (k / 20) * Math.PI * 2;
        g.beginPath(); g.arc(x + Math.cos(a) * (ANEL_RAIO - 3), y + Math.sin(a) * (ANEL_RAIO - 3), 1.3, 0, Math.PI * 2); g.fill();
      }
      g.fillStyle = "rgba(170,190,220,.45)";
      g.font = "800 12px Poppins, Manrope, system-ui, sans-serif";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(letra, x, y + ANEL_RAIO + 12);
    }

    function montarTrave() {
      const { c, g } = novaTela(LARGURA, ALTURA);
      const { frente: f } = GOL;
      // o brilho azul do estádio batendo na trave
      g.save();
      g.shadowColor = "rgba(120,200,255,.85)";
      g.shadowBlur = 14;
      g.strokeStyle = "#eef6ff";
      g.lineWidth = 11;
      g.lineJoin = "round";
      g.lineCap = "round";
      g.beginPath();
      g.moveTo(f.x0, f.chao); g.lineTo(f.x0, f.topo); g.lineTo(f.x1, f.topo); g.lineTo(f.x1, f.chao);
      g.stroke();
      g.restore();
      // o volume do tubo: sombra de um lado, brilho do outro
      g.strokeStyle = "rgba(120,140,170,.55)";
      g.lineWidth = 3;
      g.beginPath();
      g.moveTo(f.x0 + 3.5, f.chao); g.lineTo(f.x0 + 3.5, f.topo + 3.5); g.lineTo(f.x1 - 3.5, f.topo + 3.5); g.lineTo(f.x1 - 3.5, f.chao);
      g.stroke();
      g.strokeStyle = "rgba(255,255,255,.9)";
      g.lineWidth = 1.6;
      g.beginPath();
      g.moveTo(f.x0 - 3, f.chao); g.lineTo(f.x0 - 3, f.topo - 3); g.lineTo(f.x1 + 3, f.topo - 3); g.lineTo(f.x1 + 3, f.chao);
      g.stroke();
      // a sombra das traves no gramado
      g.fillStyle = "rgba(0,0,0,.35)";
      g.beginPath(); g.ellipse(f.x0, f.chao + 2, 14, 4, 0, 0, Math.PI * 2); g.fill();
      g.beginPath(); g.ellipse(f.x1, f.chao + 2, 14, 4, 0, 0, Math.PI * 2); g.fill();
      return c;
    }

    /* O ANEL DE LED ACESO: o brilho da cor, o tubo de luz e os pontinhos
       dos LEDs — o desenho dos alvos da arte oficial. */
    function montarAnel(cor, luz) {
      const lado = (ANEL_RAIO + 22) * 2;
      const { c, g } = novaTela(lado, lado);
      const m = lado / 2;
      const r = ANEL_RAIO - 3;
      // o halo largo da luz no painel escuro
      const halo = g.createRadialGradient(m, m, r - 10, m, m, r + 20);
      halo.addColorStop(0, cor + "00");
      halo.addColorStop(0.45, cor + "70");
      halo.addColorStop(1, cor + "00");
      g.fillStyle = halo;
      g.beginPath(); g.arc(m, m, r + 20, 0, Math.PI * 2); g.fill();
      g.save();
      g.shadowColor = cor;
      g.shadowBlur = 16;
      g.strokeStyle = cor;
      g.lineWidth = 10;
      g.beginPath(); g.arc(m, m, r, 0, Math.PI * 2); g.stroke();
      g.shadowBlur = 8;
      g.stroke();
      g.restore();
      // a luz dentro do buraco
      const dentro = g.createRadialGradient(m, m, 4, m, m, r);
      dentro.addColorStop(0, "rgba(0,0,0,0)");
      dentro.addColorStop(1, cor + "55");
      g.fillStyle = dentro;
      g.beginPath(); g.arc(m, m, r - 4, 0, Math.PI * 2); g.fill();
      g.strokeStyle = luz;
      g.lineWidth = 4.2;
      g.beginPath(); g.arc(m, m, r, 0, Math.PI * 2); g.stroke();
      g.fillStyle = "#ffffff";
      for (let k = 0; k < 20; k++) {
        const a = (k / 20) * Math.PI * 2;
        g.beginPath(); g.arc(m + Math.cos(a) * r, m + Math.sin(a) * r, 1.5, 0, Math.PI * 2); g.fill();
      }
      return { c, lado };
    }

    /* A BOLA: branca com os gomos pretos, sombreada como uma esfera. */
    function montarBola() {
      const R = 24;
      const { c, g } = novaTela(R * 2, R * 2);
      g.translate(R, R);
      const pele = g.createRadialGradient(-7, -8, 2, 0, 0, R);
      pele.addColorStop(0, "#ffffff");
      pele.addColorStop(0.55, "#e9edf3");
      pele.addColorStop(1, "#8d97a8");
      g.fillStyle = pele;
      g.beginPath(); g.arc(0, 0, R - 0.5, 0, Math.PI * 2); g.fill();
      g.save();
      g.beginPath(); g.arc(0, 0, R - 0.5, 0, Math.PI * 2); g.clip();
      const pentagono = (cx, cy, r, giro) => {
        g.beginPath();
        for (let k = 0; k < 5; k++) {
          const a = giro + (k / 5) * Math.PI * 2;
          g.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
        }
        g.closePath();
        g.fill();
      };
      // o gomo do meio e os cinco em volta, ligados pelas costuras
      g.fillStyle = "#161b26";
      pentagono(0, 0, 7.2, -Math.PI / 2);
      g.strokeStyle = "#4a5263";
      g.lineWidth = 1.3;
      for (let k = 0; k < 5; k++) {
        const a = -Math.PI / 2 + (k / 5) * Math.PI * 2;
        const b = a + Math.PI / 5;
        // costura do vértice do gomo do meio até a costura dos hexágonos
        g.beginPath();
        g.moveTo(Math.cos(a) * 7.2, Math.sin(a) * 7.2);
        g.lineTo(Math.cos(a) * 12.5, Math.sin(a) * 12.5);
        g.lineTo(Math.cos(b) * 15.5, Math.sin(b) * 15.5);
        g.lineTo(Math.cos(a + (Math.PI * 2) / 5) * 12.5, Math.sin(a + (Math.PI * 2) / 5) * 12.5);
        g.stroke();
        // o gomo preto de fora, entre duas costuras, cortado pela borda
        g.fillStyle = "#161b26";
        pentagono(Math.cos(b) * 21.5, Math.sin(b) * 21.5, 7.4, b);
      }
      g.restore();
      // o brilho e a borda
      g.fillStyle = "rgba(255,255,255,.55)";
      g.beginPath(); g.ellipse(-8, -10, 6, 3.5, -0.6, 0, Math.PI * 2); g.fill();
      g.strokeStyle = "rgba(20,30,50,.6)";
      g.lineWidth = 1;
      g.beginPath(); g.arc(0, 0, R - 0.5, 0, Math.PI * 2); g.stroke();
      return { c, R };
    }

    /* ------------------------------------------------------------------
       ESTADO
       ------------------------------------------------------------------ */
    let tempo = TEMPO_DE_JOGO;
    let relogio = 0;
    let pontos = 0;
    let gols = 0;
    let chutes = 0;
    let terminou = false;
    let fimT = -1;
    let qtdAlvo = 2;               // quantos anéis o grupo atual mantém acesos
    let ultimoAcerto = 0;          // para o ALVO_TIMEOUT
    let ultimaPressao = 0;
    let ultimoGol = 0;
    let golsRecentes = [];         // instantes dos gols (janela do combo)
    let comboAtivo = false;
    let acertosTorcida = 0;
    let completarEm = -1;
    let corPainel = -1, corPainelAntes = -1, trocaPainel = 1;
    let mira = 3;                  // a mira do teclado
    let miraVisivel = 0;
    let tempoMostrado = -1, pontosMostrados = -1, infoMostrada = null;
    // a bola
    let bola;                      // { estado, x, y, escala, giro, ... }
    let arrasto = null;            // { id, x0, y0, x, y, hist }
    let voo = null;                // { de, para, t, dur, alvo, resultado, curva }
    let restos = [];               // as bolas já chutadas terminando de entrar ou de quicar
    // efeitos
    let ondas = [], popups = [], avisos = [], confetes = [], ondulacao = null;
    let tremeTrave = 0;

    function novaBola(rolando) {
      bola = rolando
        ? { estado: "chegando", x: LARGURA + 40, y: MARCA.y, escala: 1, giro: 0, t: 0, alfa: 1 }
        : { estado: "pronta", x: MARCA.x, y: MARCA.y, escala: 1, giro: 0, t: 0, alfa: 1 };
    }

    function iniciar() {
      tempo = TEMPO_DE_JOGO;
      relogio = 0;
      pontos = 0;
      gols = 0;
      chutes = 0;
      terminou = false;
      fimT = -1;
      ultimoAcerto = 0;
      ultimaPressao = 0;
      ultimoGol = 0;
      golsRecentes = [];
      comboAtivo = false;
      acertosTorcida = 0;
      completarEm = -1;
      corPainel = -1; corPainelAntes = -1; trocaPainel = 1;
      mira = 3;
      miraVisivel = 0;
      tempoMostrado = -1; pontosMostrados = -1; infoMostrada = null;
      arrasto = null;
      voo = null;
      restos = [];
      ondas = []; popups = []; avisos = []; confetes = []; ondulacao = null;
      tremeTrave = 0;
      for (const a of aneis) Object.assign(a, { aceso: false, vida: 0, reservado: false, acendeu: 0, flash: 0, erro: 0, apagando: 0 });
      novaBola(false);
      // o primeiro grupo já aceso: a capa e a contagem mostram o gol "ligado"
      sortearNovoGrupo();
      // "VAI!" é do console; logo depois, o recado do original
      avisos.push({ texto: "MARQUE O MÁXIMO DE GOLS", sub: "", cor: "#ffffff", t: -0.7, dur: 1.8, tamanho: 40, x: LARGURA / 2, y: 66 });
      api.placar({ pontos: 0, tempo: TEMPO_DE_JOGO, info: "" });
    }

    /* ------------------------------------------------------------------
       OS LEDS (play.gd: _sortear_novo_grupo_de_fileiras / _completar)
       ------------------------------------------------------------------ */
    function vidaDoAnel() {
      const p = limitar(1 - tempo / TEMPO_DE_JOGO, 0, 1);
      return VIDA_DO_ANEL_INICIO + (VIDA_DO_ANEL_FIM - VIDA_DO_ANEL_INICIO) * p;
    }

    function acender(a) {
      a.aceso = true;
      a.cor = sorteioInteiro(0, CORES.length - 1);
      a.total = vidaDoAnel() * sorteio(0.9, 1.1);
      a.vida = a.total;
      a.reservado = false;
      a.acendeu = 0;
      a.apagando = 0;
    }

    function apagar(a, sumindo) {
      a.aceso = false;
      a.reservado = false;
      if (sumindo) a.apagando = 0.25;
    }

    function sortearLivre() {
      const livres = aneis.filter((a) => !a.aceso && a.apagando <= 0 && a.flash <= 0);
      if (!livres.length) return null;
      return livres[sorteioInteiro(0, livres.length - 1)];
    }

    function acesos() {
      let n = 0;
      for (const a of aneis) if (a.aceso) n++;
      return n;
    }

    function completarGrupo() {
      qtdAlvo = limitar(qtdAlvo, LEDS_ATIVOS_MIN, LEDS_ATIVOS_MAX);
      let guarda = 10;
      while (acesos() < qtdAlvo && guarda-- > 0) {
        const a = sortearLivre();
        if (!a) break;
        acender(a);
      }
    }

    function sortearNovoGrupo() {
      for (const a of aneis) if (a.aceso && !a.reservado) apagar(a, true);
      qtdAlvo = sorteioInteiro(LEDS_ATIVOS_MIN, LEDS_ATIVOS_MAX);
      completarGrupo();
    }

    /* ------------------------------------------------------------------
       O CHUTE
       ------------------------------------------------------------------ */
    function anelNaDirecao(angulo) {
      let melhor = null, menor = Infinity;
      for (const a of aneis) {
        const d = Math.abs(angulo - a.angulo);
        if (d < menor) { menor = d; melhor = a; }
      }
      return menor <= TOLERANCIA ? melhor : null;
    }

    function chutar(angulo, velocidade) {
      if (!bola || bola.estado !== "pronta" || terminou) return;
      chutes++;
      const alvo = anelNaDirecao(angulo);
      let resultado, para;
      if (alvo) {
        para = { x: alvo.x, y: alvo.y };
        if (alvo.aceso) {
          // O anel fica guardado para esta bola: se apagasse no meio do voo,
          // quem chutou no aceso perderia o gol por meio segundo de viagem.
          resultado = "gol";
          alvo.reservado = true;
        } else resultado = "apagado";
      } else if (Math.abs(angulo) <= LIMITE_DA_TRAVE) {
        resultado = "quase";
        para = { x: MARCA.x + Math.sin(angulo) * ARCO_RAIO, y: MARCA.y - Math.cos(angulo) * ARCO_RAIO };
      } else {
        resultado = "fora";
        const lado = Math.sign(angulo);
        para = { x: MARCA.x + lado * 360, y: GOL.frente.topo + 120 + sorteio(-40, 60) };
      }
      const restante = alvo && alvo.aceso ? limitar(alvo.vida / alvo.total, 0, 1) : 0;
      voo = {
        de: { x: bola.x, y: bola.y },
        para,
        t: 0,
        dur: limitar(0.56 - velocidade / 5200, 0.26, 0.56),
        alvo,
        resultado,
        restante,
        curva: sorteio(-14, 14),
      };
      bola.estado = "voando";
      miraVisivel = 0;
      api.som("batida");
      api.som("whoosh");
    }

    function chegou() {
      const { alvo, resultado, para } = voo;
      // A bola que chegou vira "resto" e termina a animação dela sozinha; a
      // próxima já vem rolando — esperar a velha quicar até o fim esfria o
      // ritmo de quem está chutando contra o relógio.
      const resto = { estado: resultado === "gol" ? "entrando" : "quicando", x: bola.x, y: bola.y, escala: bola.escala, giro: bola.giro, t: 0, alfa: 1 };
      restos.push(resto);
      novaBola(true);
      if (resultado === "gol") {
        marcarGol(alvo, voo.restante);
      } else {
        resto.de = { x: para.x, y: para.y };
        resto.vx = sorteio(-60, 60) + (resultado === "fora" ? Math.sign(para.x - MARCA.x) * 180 : 0);
        if (resultado === "apagado") {
          // o LED pisca vermelho e cresce (play.gd: _flash_led sem sucesso)
          alvo.erro = 0.35;
          aviso("ERROU!", "ESSE ANEL ESTAVA APAGADO", "#ff4646", 30, alvo.x, alvo.y - 52);
          api.som("erro");
        } else if (resultado === "quase") {
          aviso("QUASE!", "", "#ffffff", 30, para.x, para.y - 46);
          api.som("quica");
          tremeTrave = 0.25;
        } else {
          aviso("PRA FORA!", "", "#ffffff", 30, limitar(para.x, 120, 840), para.y - 40);
        }
      }
      voo = null;
    }

    function marcarGol(a, restante) {
      const agora = relogio;
      gols++;
      ultimoAcerto = agora;
      ultimoGol = agora;
      ultimaPressao = agora;
      golsRecentes.push(agora);
      golsRecentes = golsRecentes.filter((t) => agora - t <= COMBO_JANELA);
      const eraCombo = comboAtivo;
      comboAtivo = golsRecentes.length >= COMBO_MIN_GOLS;
      const multiplicador = comboAtivo ? 2 : 1;
      const valor = (PONTOS_BASE + Math.round(PONTOS_RAPIDEZ * restante)) * multiplicador;
      pontos += valor;
      const cor = CORES[a.cor];
      // o anel apaga com um clarão e o grupo se completa em seguida
      a.flash = 0.45;
      a.flashCor = a.cor;
      apagar(a, false);
      completarEm = COMPLETAR_DEPOIS;
      // o painel do player ganha o fundo da cor do anel
      if (corPainel !== a.cor) { corPainelAntes = corPainel; corPainel = a.cor; trocaPainel = 0; }
      // _explosao_gol: clarão, três ondas de choque e as faíscas
      for (let k = 0; k < 3; k++) {
        ondas.push({ x: a.x, y: a.y, r0: 14, r1: 70 + k * 18, cor: k === 1 ? "#ffffff" : cor.cor, t: -k * 0.07, dur: 0.55 + k * 0.12, largura: 5 });
      }
      api.efeitos.explosao(a.x, a.y, { cor: ["#ffd914", "#ff5940", cor.cor, "#ffffff", "#33e5ff"], n: 24, velocidade: 300, tamanho: 3.4, gravidade: 520, vida: 0.95 });
      ondulacao = { x: a.x, y: a.y, t: 0, cor: cor.cor };
      tremeTrave = 0.3;
      popups.push({ texto: "GOOOL!", sub: `+${valor}${multiplicador > 1 ? "  x2" : ""}`, cor: cor.cor, luz: cor.luz, x: a.x, y: a.y - 44, t: 0, giro: sorteio(-0.12, 0.12) });
      api.tremer(5);
      api.vibrar(25);
      api.som("acerto");
      api.som("ponto");
      if (comboAtivo && !eraCombo) {
        aviso("COMBO!", "GOLS VALEM EM DOBRO", OURO, 46);
        api.som("combo");
      }
      // A cada 10 gols a torcida canta (PONTOS_PARA_TORCIDA)
      acertosTorcida++;
      if (acertosTorcida >= PONTOS_PARA_TORCIDA) {
        acertosTorcida = 0;
        aviso(`${gols} GOLS!`, "A TORCIDA CANTA!", "#ffffff", 50);
        for (let k = 0; k < (api.reduzido ? 12 : 40); k++) confetes.push(novoConfete());
        api.som("strike");
      }
    }

    function novoConfete() {
      const paleta = ["#ffd914", "#ff5940", "#22ff4a", "#2f6bff", "#ffffff", "#33e5ff"];
      return {
        x: sorteio(0, LARGURA), y: sorteio(-260, -10), vy: sorteio(110, 200), vx: sorteio(-25, 25),
        rot: sorteio(0, 3), vr: sorteio(-7, 7), cor: paleta[sorteioInteiro(0, paleta.length - 1)],
        w: sorteio(5, 9), h: sorteio(8, 13), fase: sorteio(0, 6),
      };
    }

    function aviso(texto, sub, cor, tamanho = 40, x = LARGURA / 2, y = 66) {
      avisos.push({ texto, sub, cor, t: 0, dur: 1.15, tamanho, x, y });
    }

    function encerrar() {
      if (terminou) return;
      terminou = true;
      fimT = 0;
      for (const a of aneis) if (a.aceso && !a.reservado) apagar(a, true);
      api.som("apito");
      api.placar({ tempo: 0, info: `${gols} ${gols === 1 ? "GOL" : "GOLS"}` });
      infoMostrada = "fim";
      if (gols < GOLS_MINIMOS_SEM_VAIA) api.som("erro");
    }

    /* ------------------------------------------------------------------
       O RELÓGIO
       ------------------------------------------------------------------ */
    function atualizar(dt) {
      relogio += dt;
      if (relogio - dt <= 0) api.som("apito");

      if (!terminou) {
        tempo -= dt;
        if (tempo <= 0) { tempo = 0; encerrar(); }
      } else {
        fimT += dt;
        // o anúncio do fim fica um instante na tela antes do resultado
        if (fimT >= 1.9 && !voo && fimT < 99) {
          fimT = 99;
          const precisao = chutes ? Math.round((gols / chutes) * 100) : 0;
          const torcida = gols >= GOLS_MINIMOS_SEM_VAIA ? "A torcida aplaudiu de pé!" : `Abaixo de ${GOLS_MINIMOS_SEM_VAIA} gols a torcida vaia.`;
          api.terminar({
            pontos,
            titulo: gols >= GOLS_MINIMOS_SEM_VAIA ? `CAMPEÃO • ${gols} GOLS` : "TEMPO ESGOTADO",
            detalhe: `${gols} ${gols === 1 ? "gol" : "gols"} em ${chutes} ${chutes === 1 ? "chute" : "chutes"} (${precisao}% de acerto). ${torcida}`,
          });
        }
      }

      // OS ANÉIS: a vida de cada aceso, o clarão do gol, o pisca do erro
      for (const a of aneis) {
        a.acendeu += dt;
        if (a.flash > 0) a.flash -= dt;
        if (a.erro > 0) a.erro -= dt;
        if (a.apagando > 0) a.apagando -= dt;
        if (a.aceso && !a.reservado && !terminou) {
          a.vida -= dt;
          if (a.vida <= 0) {
            apagar(a, true);
            completarEm = completarEm < 0 ? 0.25 : completarEm;
          }
        }
      }
      if (completarEm >= 0 && !terminou) {
        completarEm -= dt;
        if (completarEm < 0) completarGrupo();
      }
      // 15 s sem acerto: troca o grupo inteiro (e a quantidade de acesos)
      if (!terminou && relogio - ultimoAcerto >= ALVO_TIMEOUT) {
        ultimoAcerto = relogio;
        sortearNovoGrupo();
      }
      // a torcida faz pressão quando o gol demora
      if (!terminou && relogio - ultimaPressao >= PRESSAO_JANELA) {
        ultimaPressao = relogio;
        aviso("A TORCIDA PEDE GOL!", "", OURO, 34, LARGURA / 2, 70);
      }
      // o combo acaba quando a janela de 6 s esvazia
      golsRecentes = golsRecentes.filter((t) => relogio - t <= COMBO_JANELA);
      if (comboAtivo && golsRecentes.length < COMBO_MIN_GOLS) comboAtivo = false;

      // A BOLA
      bola.t += dt;
      if (bola.estado === "chegando") {
        // a próxima bola vem rolando da direita até a marca
        const p = limitar(bola.t / 0.36, 0, 1);
        const e = 1 - Math.pow(1 - p, 3);
        bola.x = LARGURA + 40 + (MARCA.x - LARGURA - 40) * e;
        bola.giro = -(1 - e) * 9;
        if (p >= 1) { bola.estado = "pronta"; bola.x = MARCA.x; bola.y = MARCA.y; }
      } else if (bola.estado === "voando" && voo) {
        voo.t += dt;
        const p = limitar(voo.t / voo.dur, 0, 1);
        const e = 1 - Math.pow(1 - p, 1.6);
        const nx = -(voo.para.y - voo.de.y), ny = voo.para.x - voo.de.x;
        const n = Math.hypot(nx, ny) || 1;
        const curva = Math.sin(Math.PI * e) * voo.curva;
        bola.x = voo.de.x + (voo.para.x - voo.de.x) * e + (nx / n) * curva;
        bola.y = voo.de.y + (voo.para.y - voo.de.y) * e + (ny / n) * curva;
        bola.escala = 1 - 0.47 * e;
        bola.giro += dt * 22;
        if (p >= 1) chegou();
      }
      for (const r of restos) {
        r.t += dt;
        if (r.estado === "entrando") {
          // a bola some dentro do anel
          r.escala = Math.max(0, 0.53 * (1 - r.t / 0.14));
          if (r.t >= 0.14) r.fim = true;
        } else {
          // bateu e volta: cai até o gramado na frente do gol, quicando
          const p = limitar(r.t / 0.6, 0, 1);
          r.x = r.de.x + r.vx * r.t;
          const chao = GOL.frente.chao + 8;
          const queda = r.de.y + (chao - r.de.y) * Math.min(1, p * 1.6);
          r.y = queda - Math.abs(Math.sin(p * Math.PI * 2.2)) * 26 * (1 - p);
          r.escala = 0.53;
          r.giro += dt * 8;
          r.alfa = 1 - Math.max(0, (p - 0.55) / 0.45);
          if (p >= 1) r.fim = true;
        }
      }
      if (restos.length) restos = restos.filter((r) => !r.fim);

      // efeitos
      for (const o of ondas) o.t += dt;
      ondas = ondas.filter((o) => o.t < o.dur);
      for (const p of popups) p.t += dt;
      popups = popups.filter((p) => p.t < 1.15);
      for (const a of avisos) a.t += dt;
      avisos = avisos.filter((a) => a.t < a.dur);
      for (const c of confetes) {
        c.y += c.vy * dt;
        c.x += (c.vx + Math.sin(relogio * 3 + c.fase) * 35) * dt;
        c.rot += c.vr * dt;
      }
      confetes = confetes.filter((c) => c.y < ALTURA + 20);
      if (ondulacao) { ondulacao.t += dt; if (ondulacao.t > 0.7) ondulacao = null; }
      tremeTrave = Math.max(0, tremeTrave - dt);
      trocaPainel = Math.min(1, trocaPainel + dt * 3);
      miraVisivel = Math.max(0, miraVisivel - dt * 0.5);

      // o placar do console só é tocado quando o número muda
      const s = Math.ceil(tempo);
      if (s !== tempoMostrado) { tempoMostrado = s; api.placar({ tempo: Math.max(0, tempo) }); }
      if (pontos !== pontosMostrados) { pontosMostrados = pontos; api.placar({ pontos }); }
      if (!terminou) {
        const info = comboAtivo ? "x2 COMBO" : gols ? `${gols} ${gols === 1 ? "GOL" : "GOLS"}` : "";
        if (info !== infoMostrada) { infoMostrada = info; api.placar({ info }); }
      }
    }

    /* ------------------------------------------------------------------
       O DESENHO
       ------------------------------------------------------------------ */
    function desenhar(ctx) {
      const t = relogio;
      ctx.drawImage(camadaFundo, 0, 0, LARGURA, ALTURA);
      desenharOndulacao(ctx);
      desenharAneis(ctx, t);
      // a trave treme quando a bola bate (ou a rede estufa no gol)
      if (tremeTrave > 0) {
        const d = Math.sin(t * 70) * 2.2 * (tremeTrave / 0.3);
        ctx.drawImage(camadaTrave, d, 0, LARGURA, ALTURA);
      } else ctx.drawImage(camadaTrave, 0, 0, LARGURA, ALTURA);
      desenharOndas(ctx);
      desenharMira(ctx);
      desenharBola(ctx);
      desenharPainelPlayer(ctx, t);
      desenharPainelCombo(ctx, t);
      desenharPopups(ctx);
      desenharAvisos(ctx);
      desenharConfetes(ctx);
      if (terminou) desenharFim(ctx);
    }

    function desenharAneis(ctx, t) {
      for (const a of aneis) {
        const m = spritesAceso[0].lado / 2;
        if (a.aceso || a.apagando > 0) {
          const sprite = spritesAceso[a.cor];
          let escala = 1, alfa = 1;
          if (a.aceso) {
            // acende crescendo; perto de apagar, pisca
            const e = limitar(a.acendeu / 0.18, 0, 1);
            escala = 1.35 - 0.35 * voltaComPasso(e);
            alfa = Math.min(1, a.acendeu / 0.1);
            const resta = a.vida / a.total;
            if (!a.reservado && a.vida < 0.8) alfa *= 0.55 + 0.45 * (Math.sin(t * 28) > 0 ? 1 : 0);
            else escala += 0.03 * Math.sin(t * 6 + a.i);
            // o relógio do anel: o arco que vai fechando
            if (!a.reservado) {
              ctx.save();
              ctx.strokeStyle = CORES[a.cor].cor;
              ctx.globalAlpha = 0.85;
              ctx.lineWidth = 3;
              ctx.lineCap = "round";
              ctx.beginPath();
              ctx.arc(a.x, a.y, ANEL_RAIO + 8, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * limitar(resta, 0, 1));
              ctx.stroke();
              ctx.restore();
            }
          } else {
            const p = a.apagando / 0.25;
            alfa = p;
            escala = 0.85 + 0.15 * p;
          }
          ctx.save();
          ctx.globalAlpha = alfa;
          ctx.translate(a.x, a.y);
          ctx.scale(escala, escala);
          ctx.drawImage(sprite.c, -m, -m, sprite.lado, sprite.lado);
          ctx.restore();
        }
        if (a.flash > 0) {
          // o clarão do gol: o anel explode em branco e na cor
          const p = 1 - a.flash / 0.45;
          ctx.save();
          ctx.globalAlpha = 1 - p;
          ctx.translate(a.x, a.y);
          ctx.scale(1 + p * 0.6, 1 + p * 0.6);
          ctx.drawImage(spritesAceso[a.flashCor].c, -m, -m, spritesAceso[0].lado, spritesAceso[0].lado);
          ctx.fillStyle = "#ffffff";
          ctx.globalAlpha = (1 - p) * 0.8;
          ctx.beginPath(); ctx.arc(0, 0, ANEL_RAIO * 0.75 * (1 - p * 0.5), 0, Math.PI * 2); ctx.fill();
          ctx.restore();
        }
        if (a.erro > 0) {
          const p = 1 - a.erro / 0.35;
          ctx.save();
          ctx.globalAlpha = 1 - p;
          ctx.translate(a.x, a.y);
          const s = 1.3 - 0.3 * p;
          ctx.scale(s, s);
          ctx.drawImage(spriteErro.c, -m, -m, spriteErro.lado, spriteErro.lado);
          ctx.restore();
        }
      }
    }

    /* A rede estufando: anéis de luz que correm pelo painel a partir do
       anel que levou o gol. */
    function desenharOndulacao(ctx) {
      if (!ondulacao) return;
      const { x, y, t, cor } = ondulacao;
      const b = GOL.fundo;
      ctx.save();
      ctx.beginPath();
      ctx.rect(b.x0, b.topo, b.x1 - b.x0, b.chao - b.topo);
      ctx.clip();
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2;
      for (let k = 0; k < 3; k++) {
        const p = t / 0.7 - k * 0.12;
        if (p <= 0 || p >= 1) continue;
        ctx.globalAlpha = 0.35 * (1 - p);
        ctx.beginPath();
        ctx.arc(x, y, 40 + p * 260, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    }

    function desenharOndas(ctx) {
      ctx.save();
      for (const o of ondas) {
        if (o.t < 0) continue;
        const p = o.t / o.dur;
        const e = 1 - Math.pow(1 - p, 3);
        ctx.globalAlpha = 0.95 * (1 - e);
        ctx.strokeStyle = o.cor;
        ctx.lineWidth = Math.max(1, o.largura * (1 - p * 0.5));
        ctx.beginPath();
        ctx.arc(o.x, o.y, o.r0 + (o.r1 - o.r0) * e, 0, Math.PI * 2);
        ctx.stroke();
      }
      // o clarão central do gol
      for (const o of ondas) {
        if (o.t < 0 || o.cor !== "#ffffff") continue;
        const p = o.t / 0.3;
        if (p >= 1) continue;
        ctx.globalAlpha = 0.85 * (1 - p);
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(o.x, o.y, 12 + 20 * p, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }

    /* A MIRA: enquanto o dedo arrasta (ou as setas apontam), uma linha de
       pontinhos mostra a direção e o anel que ela pega. */
    function desenharMira(ctx) {
      let angulo = null, forca = 0;
      if (arrasto && bola.estado === "pronta") {
        const dx = arrasto.x - arrasto.x0, dy = arrasto.y - arrasto.y0;
        const d = Math.hypot(dx, dy);
        if (d > 14 && dy < -6) { angulo = Math.atan2(dx, -dy); forca = limitar(d / 90, 0.2, 1); }
      } else if (miraVisivel > 0 && bola.estado === "pronta") {
        angulo = aneis[mira].angulo;
        forca = Math.min(1, miraVisivel * 2);
      }
      if (angulo === null) return;
      const alvo = anelNaDirecao(angulo);
      const ox = bola.x, oy = bola.y;
      ctx.save();
      ctx.fillStyle = "#ffffff";
      for (let k = 1; k <= 9; k++) {
        const d = 40 + k * 23;
        const px = MARCA.x + Math.sin(angulo) * d + (ox - MARCA.x) * (1 - k / 10);
        const py = MARCA.y - Math.cos(angulo) * d + (oy - MARCA.y) * (1 - k / 10);
        ctx.globalAlpha = 0.55 * forca * (1 - k / 11);
        ctx.beginPath(); ctx.arc(px, py, 3.2 - k * 0.2, 0, Math.PI * 2); ctx.fill();
      }
      if (alvo) {
        ctx.globalAlpha = 0.75 * forca;
        ctx.strokeStyle = alvo.aceso ? CORES[alvo.cor].luz : "#ffffff";
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.beginPath(); ctx.arc(alvo.x, alvo.y, ANEL_RAIO + 14, 0, Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.restore();
    }

    function desenharUmaBola(ctx, b) {
      const { c, R } = spriteBola;
      const raio = BOLA_RAIO * b.escala;
      if (raio <= 0.3) return;
      ctx.save();
      ctx.globalAlpha = b.alfa;
      // a sombra no gramado: no chão quando parada, longe quando voa
      const sombraY = b.estado === "voando" || b.estado === "entrando"
        ? MARCA.y + BOLA_RAIO + 2 - (MARCA.y - b.y) * 0.35
        : b.y + raio + 2;
      ctx.fillStyle = "rgba(0,0,0,.35)";
      ctx.beginPath(); ctx.ellipse(b.x + 3, sombraY, raio * 1.05, raio * 0.32, 0, 0, Math.PI * 2); ctx.fill();
      ctx.translate(b.x, b.y);
      ctx.rotate(b.giro);
      const lado = (raio / (R - 0.5)) * R * 2;
      ctx.drawImage(c, -lado / 2, -lado / 2, lado, lado);
      ctx.restore();
    }

    function desenharBola(ctx) {
      for (const r of restos) desenharUmaBola(ctx, r);
      if (!bola) return;
      desenharUmaBola(ctx, bola);
      const raio = BOLA_RAIO * bola.escala;
      // o rastro de luz do chute
      if (bola.estado === "voando" && voo) {
        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        const dx = voo.de.x - bola.x, dy = voo.de.y - bola.y;
        const d = Math.hypot(dx, dy) || 1;
        const comprimento = Math.min(d, 90);
        const g = ctx.createLinearGradient(bola.x, bola.y, bola.x + (dx / d) * comprimento, bola.y + (dy / d) * comprimento);
        g.addColorStop(0, "rgba(255,230,120,.55)");
        g.addColorStop(1, "rgba(255,230,120,0)");
        ctx.strokeStyle = g;
        ctx.lineWidth = raio * 1.4;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(bola.x, bola.y);
        ctx.lineTo(bola.x + (dx / d) * comprimento, bola.y + (dy / d) * comprimento);
        ctx.stroke();
        ctx.restore();
      }
    }

    /* O PAINEL DO PLAYER (play.gd: _criar_painel_player): PLAYER 1, GOL
       grande, TEMPO, e o status. O fundo vira a cor do anel do último gol
       — as artes azul/verde/vermelho/amarelo dos cartões do original. */
    function desenharPainelPlayer(ctx, t) {
      const { x, y, w, h } = PAINEL_E;
      ctx.save();
      retanguloRedondo(ctx, x, y, w, h, 16);
      ctx.fillStyle = "rgba(2,6,14,.9)";
      ctx.fill();
      ctx.save();
      ctx.clip();
      const fundo = (i, a) => {
        const im = i >= 0 ? img[CORES[i].nome] : null;
        if (!im || a <= 0) return;
        ctx.globalAlpha = a;
        ctx.drawImage(im, x, y, w, h);
      };
      fundo(corPainelAntes, 1 - trocaPainel);
      fundo(corPainel, trocaPainel);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(2,6,14,.58)";
      ctx.fillRect(x, y, w, h);
      ctx.restore();
      const cor = corPainel >= 0 ? CORES[corPainel].cor : COR_PLAYER;
      ctx.strokeStyle = cor;
      ctx.globalAlpha = 0.7;
      ctx.lineWidth = 2;
      retanguloRedondo(ctx, x, y, w, h, 16);
      ctx.stroke();
      ctx.globalAlpha = 1;
      api.texto(ctx, "PLAYER 1", x + 14, y + 17, { tamanho: 15, cor: COR_PLAYER, alinhar: "left", peso: 900 });
      api.texto(ctx, terminou ? "FINALIZADO" : "JOGANDO AGORA", x + w - 12, y + 17, { tamanho: 10.5, cor: "rgba(200,215,230,.8)", alinhar: "right", peso: 800 });
      api.texto(ctx, "GOL", x + 52, y + 40, { tamanho: 12, cor: "#bfd6e6", peso: 800 });
      const pulo = popups.length ? Math.max(0, 1 - popups[popups.length - 1].t / 0.3) : 0;
      ctx.save();
      ctx.translate(x + 52, y + 68);
      ctx.scale(1 + pulo * 0.25, 1 + pulo * 0.25);
      api.texto(ctx, String(gols), 0, 0, { tamanho: 38, cor: "#ffffff", peso: 900, contorno: "rgba(0,0,0,.6)" });
      ctx.restore();
      api.texto(ctx, "TEMPO", x + 148, y + 40, { tamanho: 12, cor: "#a6b8c6", peso: 800 });
      const alerta = tempo <= 5 && !terminou && Math.sin(t * 12) > 0;
      api.texto(ctx, String(Math.max(0, Math.ceil(tempo))), x + 148, y + 68, { tamanho: 30, cor: alerta ? "#ff5a3c" : "#ffd914", peso: 900, contorno: "rgba(0,0,0,.6)" });
      ctx.restore();
    }

    /* O COMBO: quatro luzes que acendem com os gols da janela de 6 s; com
       as quatro acesas o gol vale dobrado. */
    function desenharPainelCombo(ctx, t) {
      const { x, y, w, h } = PAINEL_D;
      ctx.save();
      retanguloRedondo(ctx, x, y, w, h, 16);
      ctx.fillStyle = comboAtivo ? "rgba(40,30,0,.88)" : "rgba(2,6,14,.85)";
      ctx.fill();
      ctx.strokeStyle = comboAtivo ? OURO : "rgba(150,180,210,.35)";
      ctx.lineWidth = comboAtivo ? 2.5 : 1.5;
      ctx.stroke();
      api.texto(ctx, "COMBO", x + 14, y + 17, { tamanho: 15, cor: comboAtivo ? OURO : "#bfd6e6", alinhar: "left", peso: 900 });
      api.texto(ctx, "4 GOLS EM 6 s", x + w - 12, y + 17, { tamanho: 10.5, cor: "rgba(200,215,230,.75)", alinhar: "right", peso: 800 });
      const n = Math.min(COMBO_MIN_GOLS, golsRecentes.length);
      for (let k = 0; k < COMBO_MIN_GOLS; k++) {
        const cx = x + 30 + k * 30, cy = y + 58;
        const aceso = k < n;
        ctx.beginPath(); ctx.arc(cx, cy, 10, 0, Math.PI * 2);
        ctx.fillStyle = aceso ? OURO : "#1b2436";
        ctx.fill();
        if (aceso) {
          ctx.globalAlpha = 0.35;
          ctx.beginPath(); ctx.arc(cx, cy, 15, 0, Math.PI * 2); ctx.fill();
          ctx.globalAlpha = 1;
        }
      }
      const bate = comboAtivo ? 1 + 0.08 * Math.sin(t * 10) : 1;
      ctx.save();
      ctx.translate(x + w - 34, y + 58);
      ctx.scale(bate, bate);
      api.texto(ctx, "x2", 0, 0, { tamanho: 30, cor: comboAtivo ? OURO : "rgba(150,170,200,.35)", peso: 900, contorno: comboAtivo ? "rgba(0,0,0,.6)" : null });
      ctx.restore();
      api.texto(ctx, comboAtivo ? "GOL VALE EM DOBRO!" : "CHUTE RÁPIDO VALE MAIS", x + w / 2, y + h - 12, { tamanho: 10.5, cor: comboAtivo ? "#fff1a8" : "rgba(170,190,215,.7)", peso: 800 });
      ctx.restore();
    }

    /* "GOOOL!" e "+N" (play.gd: _mostrar_popup_ponto): nasce pequeno e
       torto, cresce passando do ponto, sobe e some. */
    function desenharPopups(ctx) {
      for (const p of popups) {
        const cresce = voltaComPasso(limitar(p.t / 0.16, 0, 1), 2.2);
        const escala = 0.5 + 0.85 * cresce;
        const giro = p.giro * (1 - limitar(p.t / 0.22, 0, 1));
        const sobe = p.t > 0.12 ? (1 - Math.pow(1 - limitar((p.t - 0.12) / 0.72, 0, 1), 2)) * 60 : 0;
        const alfa = p.t > 0.42 ? Math.max(0, 1 - (p.t - 0.42) / 0.42) : 1;
        const y = Math.max(60, p.y) - sobe;
        ctx.save();
        ctx.globalAlpha = alfa;
        ctx.translate(p.x, y);
        ctx.rotate(giro);
        ctx.scale(escala * 0.74, escala * 0.74);
        api.texto(ctx, p.texto, 0, 0, { tamanho: 58, cor: "#ffffff", peso: 900, contorno: "rgba(0,0,0,.55)", sombra: p.cor });
        ctx.restore();
        ctx.save();
        ctx.globalAlpha = alfa;
        const subEscala = 0.6 + 0.4 * voltaComPasso(limitar(p.t / 0.18, 0, 1));
        ctx.translate(p.x, y + 34);
        ctx.scale(subEscala, subEscala);
        api.texto(ctx, p.sub, 0, 0, { tamanho: 26, cor: p.luz, peso: 900, contorno: "rgba(0,0,0,.75)" });
        ctx.restore();
      }
    }

    function desenharAvisos(ctx) {
      for (const a of avisos) {
        if (a.t < 0) continue;
        const entra = voltaComPasso(limitar(a.t / 0.22, 0, 1), 2);
        const sai = a.t > a.dur - 0.25 ? Math.max(0, (a.dur - a.t) / 0.25) : 1;
        ctx.save();
        ctx.globalAlpha = sai;
        ctx.translate(a.x, a.y);
        ctx.scale(0.4 + 0.6 * entra, 0.4 + 0.6 * entra);
        api.texto(ctx, a.texto, 0, 0, { tamanho: a.tamanho, cor: a.cor, peso: 900, contorno: "rgba(0,0,0,.7)" });
        if (a.sub) api.texto(ctx, a.sub, 0, a.tamanho * 0.72, { tamanho: Math.max(13, a.tamanho * 0.36), cor: "#ffffff", peso: 800, contorno: "rgba(0,0,0,.7)" });
        ctx.restore();
      }
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

    /* TEMPO ESGOTADO (play.gd: _mostrar_aviso_turno), no cartão azul do
       PLAYER 1. */
    function desenharFim(ctx) {
      const e = voltaComPasso(limitar(fimT / 0.35, 0, 1), 1.6);
      const w = 520, h = 150;
      const x = (LARGURA - w) / 2, y = 150;
      ctx.save();
      ctx.fillStyle = `rgba(0,4,12,${(0.45 * limitar(fimT / 0.3, 0, 1)).toFixed(3)})`;
      ctx.fillRect(0, 0, LARGURA, ALTURA);
      ctx.translate(LARGURA / 2, y + h / 2);
      ctx.scale(0.6 + 0.4 * e, 0.6 + 0.4 * e);
      ctx.globalAlpha = limitar(fimT / 0.2, 0, 1);
      ctx.translate(-LARGURA / 2, -(y + h / 2));
      retanguloRedondo(ctx, x, y, w, h, 22);
      ctx.save();
      ctx.clip();
      if (img.azul) ctx.drawImage(img.azul, x, y, w, h);
      ctx.fillStyle = "rgba(0,8,30,.45)";
      ctx.fillRect(x, y, w, h);
      ctx.restore();
      ctx.strokeStyle = COR_PLAYER;
      ctx.lineWidth = 3;
      retanguloRedondo(ctx, x, y, w, h, 22);
      ctx.stroke();
      api.texto(ctx, "TEMPO ESGOTADO", LARGURA / 2, y + 58, { tamanho: 46, cor: "#ffffff", peso: 900, contorno: "rgba(0,0,0,.6)", sombra: COR_PLAYER });
      api.texto(ctx, `PLAYER 1 FINALIZOU COM ${gols} ${gols === 1 ? "GOL" : "GOLS"}`, LARGURA / 2, y + 108, { tamanho: 20, cor: "#ffd914", peso: 900, contorno: "rgba(0,0,0,.6)" });
      ctx.restore();
    }

    /* ------------------------------------------------------------------
       O TOQUE: arrasta a bola e solta na direção do anel
       ------------------------------------------------------------------ */
    function apertar(x, y, id) {
      if (terminou || arrasto) return;
      if (!bola || bola.estado !== "pronta") return;
      // pega a bola, ou qualquer ponto do gramado perto dela
      if (Math.hypot(x - bola.x, y - bola.y) > 150 && y < MARCA.y - 80) return;
      arrasto = { id, x0: x, y0: y, x, y, hist: [{ x, y, t: performance.now() }] };
    }

    function mover(x, y, id) {
      if (!arrasto || arrasto.id !== id) return;
      arrasto.x = x;
      arrasto.y = y;
      const agora = performance.now();
      arrasto.hist.push({ x, y, t: agora });
      if (arrasto.hist.length > 8) arrasto.hist.shift();
      // a bola acompanha o dedo, presa perto da marca
      if (bola.estado === "pronta") {
        const dx = x - arrasto.x0, dy = y - arrasto.y0;
        const d = Math.hypot(dx, dy) || 1;
        const k = Math.min(d, 46) / d;
        bola.x = MARCA.x + dx * k;
        bola.y = MARCA.y + dy * k;
      }
    }

    function soltar(x, y, id) {
      if (!arrasto || arrasto.id !== id) return;
      mover(x, y, id);
      const a = arrasto;
      arrasto = null;
      const dx = a.x - a.x0, dy = a.y - a.y0;
      const distancia = Math.hypot(dx, dy);
      if (bola.estado !== "pronta") return;
      if (distancia < 26 || dy > -10) {
        // não foi chute: a bola volta para a marca
        bola.x = MARCA.x;
        bola.y = MARCA.y;
        return;
      }
      // a velocidade do fim do gesto decide a força (a direção é o gesto todo)
      const ultimo = a.hist[a.hist.length - 1];
      let primeiro = a.hist[0];
      for (const p of a.hist) if (ultimo.t - p.t <= 110) { primeiro = p; break; }
      const dtGesto = Math.max(16, ultimo.t - primeiro.t) / 1000;
      const velocidade = Math.hypot(ultimo.x - primeiro.x, ultimo.y - primeiro.y) / dtGesto;
      chutar(Math.atan2(dx, -dy), velocidade);
    }

    function tecla(codigo, apertada) {
      if (!apertada || terminou) return;
      if (codigo === "ArrowLeft") { mira = Math.max(0, mira - 1); miraVisivel = 2; return; }
      if (codigo === "ArrowRight") { mira = Math.min(LEDS_TOTAL - 1, mira + 1); miraVisivel = 2; return; }
      if (codigo === "Space" || codigo === "Enter" || codigo === "ArrowUp") { chutar(aneis[mira].angulo, 1800); return; }
      // as letras dos sensores (A a G) e os números 1 a 7 chutam direto
      const letra = /^Key([A-G])$/.exec(codigo);
      const numero = /^(?:Digit|Numpad)([1-7])$/.exec(codigo);
      const i = letra ? LETRAS.indexOf(letra[1]) : numero ? Number(numero[1]) - 1 : -1;
      if (i >= 0) { mira = i; chutar(aneis[i].angulo, 1800); }
    }

    return {
      iniciar, atualizar, desenhar, apertar, mover, soltar, tecla,
      destruir() { ondas = []; popups = []; avisos = []; confetes = []; arrasto = null; },
    };
  },
};
