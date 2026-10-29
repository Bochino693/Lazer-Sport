/* ======================================================================
   ELEMENTAL BEASTS — miniatura da Arena Elemental.

   O jogo de verdade (projeto Godot "beta-13", Lazer Beasts: Elemental
   Arena) é um duelo por turnos de Beasts de oito elementos. Esta
   miniatura é um duelo rápido 3 contra 3 contra a máquina, com as regras
   copiadas do original:

   - criaturas, golpes, poder, recarga e classes de peso vêm de
     data/creatures.json e data/moves.json (nove Beasts, uma ou duas por
     elemento, para não pesar a página);
   - a tabela de tipos é a de data/elements.json: vantagem ×1,45,
     resistência ×0,68, mesmo tipo ×0,82 — e Luz/Escuridão são rivais
     recíprocos ("CHOQUE DE RIVAIS!");
   - o dano é a fórmula de MoveDB.damage_preview (ataque/defesa ^0,62,
     resistência, tipo e peso) com a mesma variação de ±2;
   - recarga por golpe ajustada pela classe de peso, escudo de 1–3
     rodadas que corta 52% do dano, troca de Beast gastando a vez;
   - a CPU pensa como a do battle.gd: maior dano menos recarga, bônus se
     nocauteia, às vezes ergue escudo ou troca quando está com pouca vida;
   - pontos: dano causado (pesado vale dobrado), +250 por nocaute e +1000
     pela vitória — os mesmos de GameState.scores.

   A vida é um terço da do gabinete (mesma proporção entre as Beasts), para
   a luta caber em um ou dois minutos.
   ====================================================================== */

const LARGURA = 540;
const ALTURA = 960;
const ESCALA_VIDA = 0.34;

/* ---------- data/elements.json ---------- */
const ELEMENTOS = [
  { nome: "Luz", cor: "#ffe477", vence: ["Escuridão", "Natureza"] },
  { nome: "Escuridão", cor: "#a856ff", vence: ["Luz", "Vento"] },
  { nome: "Fogo", cor: "#ff5733", vence: ["Luz", "Natureza"] },
  { nome: "Choque", cor: "#ffdb32", vence: ["Água", "Vento"] },
  { nome: "Terra", cor: "#c58b52", vence: ["Choque", "Fogo"] },
  { nome: "Água", cor: "#27bcff", vence: ["Fogo", "Terra"] },
  { nome: "Natureza", cor: "#50d35a", vence: ["Terra", "Água"] },
  { nome: "Vento", cor: "#9cf4e8", vence: ["Natureza", "Luz"] },
];
const ELEMENTO = Object.fromEntries(ELEMENTOS.map((e, i) => [e.nome, { ...e, i }]));
const VANTAGEM = 1.45;
const RESISTENCIA = 0.68;
const MESMO_TIPO = 0.82;

/* ---------- move_db.gd: perfis de peso e escudo ---------- */
const PESO = {
  "Ultra Leve": { recarga: 0.7, vida: 0, dano: 1.08 },
  Leve: { recarga: 0.82, vida: 8, dano: 1.05 },
  "Médio": { recarga: 1, vida: 16, dano: 1 },
  Pesado: { recarga: 1.16, vida: 22, dano: 0.96 },
  Colossal: { recarga: 1.3, vida: 24, dano: 0.92 },
};
const ESCUDO_FATOR = 0.48;
const ESCUDO_RECARGA = 4;

/* ---------- data/creatures.json (9 das 30) ----------
   golpes: o primeiro (rápido), o pesado e o de cobertura (outro elemento,
   contra a fraqueza) — a mesma espinha dos cinco golpes do original. */
const BEASTS = [
  { id: "helionce", nome: "HELIONCE", titulo: "Leão do Zênite", tipo: "Luz", ataque: 85, defesa: 86, resistencia: 86, velocidade: 69, peso: 168, classe: "Pesado", golpes: ["luz_02_lanca_solar", "luz_10_julgamento_prismatico", "choque_05_campo_de_inducao"] },
  { id: "impavor", nome: "IMPAVOR", titulo: "Diabrete do Eclipse", tipo: "Escuridão", ataque: 94, defesa: 75, resistencia: 76, velocidade: 93, peso: 22, classe: "Leve", golpes: ["escuridao_01_garra_sombria", "escuridao_09_boca_do_abismo", "fogo_05_arco_de_cinza"] },
  { id: "pyrocondor", nome: "PYROCONDOR", titulo: "Condor da Coroa Ígnea", tipo: "Fogo", ataque: 86, defesa: 80, resistencia: 84, velocidade: 84, peso: 88, classe: "Médio", golpes: ["fogo_02_chicote_de_fagulha", "fogo_10_coroa_da_caldeira", "escuridao_05_eclipse_breve"] },
  { id: "vulcora", nome: "VULCORA", titulo: "Tartaruga-Caldeira", tipo: "Fogo", ataque: 82, defesa: 91, resistencia: 90, velocidade: 50, peso: 510, classe: "Colossal", golpes: ["fogo_02_chicote_de_fagulha", "fogo_10_coroa_da_caldeira", "choque_05_campo_de_inducao"] },
  { id: "voltalho", nome: "VOLTALHO", titulo: "Saltador Voltaico", tipo: "Choque", ataque: 90, defesa: 78, resistencia: 78, velocidade: 91, peso: 18, classe: "Leve", golpes: ["choque_01_pulso_estatico", "choque_09_impacto_tesla", "agua_05_espuma_vital"] },
  { id: "geodrilo", nome: "GEODRILO", titulo: "Crocodilo Geodo", tipo: "Terra", ataque: 86, defesa: 92, resistencia: 90, velocidade: 47, peso: 460, classe: "Colossal", golpes: ["terra_02_garra_de_arenito", "terra_10_despertar_fossil", "fogo_05_arco_de_cinza"] },
  { id: "crustarka", nome: "CRUSTARKA", titulo: "Lutador Recifal", tipo: "Água", ataque: 88, defesa: 84, resistencia: 82, velocidade: 82, peso: 82, classe: "Médio", golpes: ["agua_02_chicote_de_mare", "agua_10_trono_das_aguas", "terra_05_casulo_mineral"] },
  { id: "arborion", nome: "ARBORION", titulo: "Colosso do Bosque", tipo: "Natureza", ataque: 85, defesa: 93, resistencia: 90, velocidade: 46, peso: 680, classe: "Colossal", golpes: ["natureza_02_polen_vivo", "natureza_10_colapso_micelio", "vento_05_passo_nuvem"] },
  { id: "tempestral", nome: "TEMPESTRAL", titulo: "Serpente dos Quatro Ventos", tipo: "Vento", ataque: 87, defesa: 83, resistencia: 82, velocidade: 84, peso: 160, classe: "Médio", golpes: ["vento_02_pena_lamina", "vento_10_quatro_ventos", "terra_05_casulo_mineral"] },
];

/* ---------- data/moves.json (icone = posição no atlas golpes.webp) ---------- */
const GOLPES = {
  luz_02_lanca_solar: { nome: "Lança Solar", elemento: "Luz", papel: "rápido", poder: 26, recarga: 0.8, icone: 0 },
  luz_10_julgamento_prismatico: { nome: "Julgamento Prismático", elemento: "Luz", papel: "pesado", poder: 48, recarga: 3.85, icone: 1 },
  choque_05_campo_de_inducao: { nome: "Campo de Indução", elemento: "Choque", papel: "técnico", poder: 33, recarga: 1.55, icone: 2 },
  escuridao_01_garra_sombria: { nome: "Garra Sombria", elemento: "Escuridão", papel: "rápido", poder: 23, recarga: 0.55, icone: 3 },
  escuridao_09_boca_do_abismo: { nome: "Boca do Abismo", elemento: "Escuridão", papel: "pesado", poder: 45, recarga: 3.4, icone: 4 },
  fogo_05_arco_de_cinza: { nome: "Arco de Cinza", elemento: "Fogo", papel: "técnico", poder: 33, recarga: 1.55, icone: 5 },
  fogo_02_chicote_de_fagulha: { nome: "Chicote de Fagulha", elemento: "Fogo", papel: "rápido", poder: 26, recarga: 0.8, icone: 6 },
  fogo_10_coroa_da_caldeira: { nome: "Coroa da Caldeira", elemento: "Fogo", papel: "pesado", poder: 48, recarga: 3.85, icone: 7 },
  escuridao_05_eclipse_breve: { nome: "Eclipse Breve", elemento: "Escuridão", papel: "técnico", poder: 33, recarga: 1.55, icone: 8 },
  choque_01_pulso_estatico: { nome: "Pulso Estático", elemento: "Choque", papel: "rápido", poder: 23, recarga: 0.55, icone: 9 },
  choque_09_impacto_tesla: { nome: "Impacto Tesla", elemento: "Choque", papel: "pesado", poder: 45, recarga: 3.4, icone: 10 },
  agua_05_espuma_vital: { nome: "Espuma Vital", elemento: "Água", papel: "técnico", poder: 33, recarga: 1.55, icone: 11 },
  terra_02_garra_de_arenito: { nome: "Garra de Arenito", elemento: "Terra", papel: "rápido", poder: 26, recarga: 0.8, icone: 12 },
  terra_10_despertar_fossil: { nome: "Despertar Fóssil", elemento: "Terra", papel: "pesado", poder: 48, recarga: 3.85, icone: 13 },
  agua_02_chicote_de_mare: { nome: "Chicote de Maré", elemento: "Água", papel: "rápido", poder: 26, recarga: 0.8, icone: 14 },
  agua_10_trono_das_aguas: { nome: "Trono das Águas", elemento: "Água", papel: "pesado", poder: 48, recarga: 3.85, icone: 15 },
  terra_05_casulo_mineral: { nome: "Casulo Mineral", elemento: "Terra", papel: "técnico", poder: 33, recarga: 1.55, icone: 16 },
  natureza_02_polen_vivo: { nome: "Pólen Vivo", elemento: "Natureza", papel: "rápido", poder: 26, recarga: 0.8, icone: 17 },
  natureza_10_colapso_micelio: { nome: "Colapso Micélio", elemento: "Natureza", papel: "pesado", poder: 48, recarga: 3.85, icone: 18 },
  vento_05_passo_nuvem: { nome: "Passo Nuvem", elemento: "Vento", papel: "técnico", poder: 33, recarga: 1.55, icone: 19 },
  vento_02_pena_lamina: { nome: "Pena Lâmina", elemento: "Vento", papel: "rápido", poder: 26, recarga: 0.8, icone: 20 },
  vento_10_quatro_ventos: { nome: "Quatro Ventos", elemento: "Vento", papel: "pesado", poder: 48, recarga: 3.85, icone: 21 },
};

/* ---------- regras (creature_db.gd / move_db.gd) ---------- */
function rivais(a, b) {
  return a !== b && ELEMENTO[a].vence.includes(b) && ELEMENTO[b].vence.includes(a);
}

// A vantagem é conferida ANTES da resistência: num par recíproco os dois
// lados caem nela, que é o comportamento desejado para Luz/Escuridão.
function multiplicador(ataque, defesa) {
  if (ataque === defesa) return MESMO_TIPO;
  if (ELEMENTO[ataque].vence.includes(defesa)) return VANTAGEM;
  if (ELEMENTO[defesa].vence.includes(ataque)) return RESISTENCIA;
  return 1;
}

function textoEfeito(m, ataque, defesa) {
  if (m >= 1.4) return rivais(ataque, defesa) ? "CHOQUE DE RIVAIS!" : "SUPER EFETIVO!";
  if (m <= 0.7) return "RESISTIU AO TIPO";
  if (m < 0.9) return "MESMO TIPO: DANO REDUZIDO";
  return "ACERTO LIMPO";
}

function vidaMaxima(b) {
  return Math.round((145 + b.resistencia * 1.55 + PESO[b.classe].vida) * ESCALA_VIDA);
}

function previsaoDano(atacante, defensor, golpe) {
  const razao = Math.pow(atacante.ataque / Math.max(42, defensor.defesa), 0.62);
  const resistencia = 1 - Math.min(0.17, Math.max(0.06, defensor.resistencia / 590));
  const tipo = multiplicador(golpe.elemento, defensor.tipo);
  return Math.max(6, Math.round(golpe.poder * razao * resistencia * tipo * PESO[atacante.classe].dano));
}

function recargaEfetiva(golpe, b) {
  return Math.round(Math.max(0.35, golpe.recarga * PESO[b.classe].recarga) * 20) / 20;
}

function duracaoEscudo(b) {
  if (b.resistencia >= 78) return 3;
  if (b.resistencia >= 52) return 2;
  return 1;
}

const fmtMult = (m) => "x" + String(m).replace(".", ",");

/* ---------- tela (bandas do retrato 720x1280 do battle.gd, × 0,75) ---------- */
const HUD_CPU = { x: 12, y: 46, w: 516, h: 58 };
const HUD_EU = { x: 12, y: 654, w: 516, h: 62 };
const MSG_Y = 736;
const BOTOES = [
  { x: 12, y: 760, w: 252, h: 92 },
  { x: 276, y: 760, w: 252, h: 92 },
  { x: 12, y: 860, w: 252, h: 92 },
  { x: 276, y: 860, w: 252, h: 92 },
];
// âncora = chão sob os pés; o jogador fica perto (de costas), a CPU longe
const POS = [{ x: 205, y: 650, tam: 330 }, { x: 345, y: 432, tam: 236 }];
const QUADRO = 160; // célula do atlas de combate
const CARTA = { w: 152, h: 228, y: 530 };

export default {
  largura: LARGURA,
  altura: ALTURA,
  artes: {
    arena: "elemental-beasts/arena.webp",
    tipos: "elemental-beasts/tipos.webp",
    golpes: "elemental-beasts/golpes.webp",
    escudo: "elemental-beasts/escudo.svg",
    trocar: "elemental-beasts/trocar.svg",
    ...Object.fromEntries(BEASTS.flatMap((b) => [
      [b.id, `elemental-beasts/${b.id}.webp`],
      [b.id + "_carta", `elemental-beasts/${b.id}-carta.webp`],
    ])),
  },

  criar(api) {
    const img = api.img;
    const FONTE = "Poppins, Manrope, system-ui, sans-serif";

    /* ---------- brilhos pré-desenhados por elemento (+ ciano do escudo) ---------- */
    const CORES_BRILHO = [...ELEMENTOS.map((e) => e.cor), "#59d7ff", "#ffffff"];
    const CIANO = 8;
    const BRANCO = 9;
    const BRILHOS = CORES_BRILHO.map((cor) => {
      const c = document.createElement("canvas");
      c.width = c.height = 64;
      const x = c.getContext("2d");
      const n = parseInt(cor.slice(1), 16);
      const rgb = `${n >> 16},${(n >> 8) & 255},${n & 255}`;
      const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
      g.addColorStop(0, `rgba(${rgb},1)`);
      g.addColorStop(0.4, `rgba(${rgb},0.4)`);
      g.addColorStop(1, `rgba(${rgb},0)`);
      x.fillStyle = g;
      x.fillRect(0, 0, 64, 64);
      return c;
    });

    function brilho(ctx, i, x, y, rx, ry, alfa) {
      if (alfa <= 0.01) return;
      ctx.globalAlpha = Math.min(1, alfa);
      ctx.drawImage(BRILHOS[i], x - rx, y - ry, rx * 2, ry * 2);
    }

    /* ---------- estado ---------- */
    let chamadasIniciar = 0;
    let fase = "capa"; // capa → pronto → abertura → escolha ⇄ vez/acao → fim
    let tempo = 0;
    let relogio = 0;
    let times = [[], []];
    const ativo = [0, 0];
    let vez = 0;
    let rodada = 0;
    let pontos = 0;
    let nocautes = 0;
    let mensagem = "";
    let tempoMensagem = 0;
    let motivoEscolha = "inicio";
    let foco = 0;
    let focoCarta = 0;
    let agenda = [];
    let projetil = null;
    let cartaVoando = null;
    let anel = [];
    let vencedor = -1;
    let placarInfo = "";

    function esperar(segundos, fn) {
      agenda.push({ quando: tempo + segundos, fn });
    }

    function dizer(texto) {
      mensagem = texto;
      tempoMensagem = tempo;
    }

    function lutador(lado) {
      return times[lado][ativo[lado]];
    }

    function novoLutador(b, lado) {
      const vida = vidaMaxima(b);
      return {
        b, lado, vida, vidaMax: vida, vidaMostrada: vida, vidaRastro: vida,
        recargas: {}, escudo: false, escudoTurnos: 0, escudoRecarga: 0, ko: false,
        // visual
        pose: 0, anim: "", animIni: 0, animDur: 1, flash: 0, entrou: false,
      };
    }

    function animar(l, nome, dur) {
      l.anim = nome;
      l.animIni = tempo;
      l.animDur = dur;
    }

    function proximoVivo(lado) {
      const time = times[lado];
      for (let passo = 1; passo <= time.length; passo++) {
        const i = (ativo[lado] + passo) % time.length;
        if (!time[i].ko) return i;
      }
      return -1;
    }

    function vivos(lado) {
      return times[lado].filter((l) => !l.ko).length;
    }

    function podeUsar(l, id) {
      return (l.recargas[id] || 0) <= 0.001;
    }

    function turnosRecarga(l, id) {
      return Math.max(0, Math.ceil((l.recargas[id] || 0) - 0.001));
    }

    function podeEscudo(l) {
      return !l.escudo && l.escudoRecarga <= 0;
    }

    function atualizarPlacar() {
      api.placar({ pontos });
      const info = rodada > 0 ? `RODADA ${rodada}` : "";
      if (info !== placarInfo) { placarInfo = info; api.placar({ info }); }
    }

    /* ======================================================================
       FLUXO DA BATALHA
       ====================================================================== */
    function sortearTimes() {
      const baralho = BEASTS.slice();
      for (let i = baralho.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [baralho[i], baralho[j]] = [baralho[j], baralho[i]];
      }
      // três elementos diferentes em cada mão: escolher a carta certa precisa
      // ser uma escolha de verdade
      const tirar = () => {
        const mao = [];
        for (let i = 0; i < baralho.length && mao.length < 3; i++) {
          if (!mao.some((b) => b.tipo === baralho[i].tipo)) mao.push(baralho.splice(i--, 1)[0]);
        }
        while (mao.length < 3) mao.push(baralho.shift());
        return mao;
      };
      times = [tirar().map((b) => novoLutador(b, 0)), tirar().map((b) => novoLutador(b, 1))];
      ativo[0] = 0;
      ativo[1] = 0;
    }

    function entrar(lado, i) {
      ativo[lado] = i;
      const l = lutador(lado);
      l.entrou = true;
      l.pose = 0;
      animar(l, "entra", 0.55);
      const p = POS[lado];
      anel.push({ x: p.x, y: p.y, cor: ELEMENTO[l.b.tipo].i, ini: tempo, dur: 0.7, raio: p.tam * 0.55 });
      api.efeitos.explosao(p.x, p.y - p.tam * 0.3, { cor: [ELEMENTO[l.b.tipo].cor, "#ffffff"], n: 22, velocidade: 260, tamanho: 4, gravidade: 200, vida: 0.7 });
      api.som("acerto");
    }

    function abrirPartida() {
      dizer("AS BEASTS ENTRAM NA ARENA");
      esperar(0.45, () => {
        entrar(1, 0);
        dizer(`A CPU ENVIOU ${lutador(1).b.nome}`);
      });
      esperar(1.35, () => abrirEscolha("inicio"));
    }

    function abrirEscolha(motivo) {
      motivoEscolha = motivo;
      fase = "escolha";
      focoCarta = times[0].findIndex((l) => !l.ko);
      dizer(motivo === "inicio" ? "ESCOLHA QUEM ENTRA NA ARENA" : "ESCOLHA A PRÓXIMA BEAST");
    }

    function escolherCarta(i) {
      if (fase !== "escolha") return;
      const l = times[0][i];
      if (!l || l.ko) { api.som("erro"); return; }
      fase = "acao";
      cartaVoando = { i, ini: tempo, ...posCarta(i, contarCartas()) };
      api.som("whoosh");
      esperar(0.38, () => {
        cartaVoando = null;
        entrar(0, i);
        dizer(`${l.b.nome} ENTRA NA ARENA`);
      });
      esperar(1.15, () => {
        if (motivoEscolha === "inicio") {
          // "COMEÇA X • MAIOR VELOCIDADE" (empate fica com o jogador)
          vez = lutador(0).b.velocidade >= lutador(1).b.velocidade ? 0 : 1;
          dizer(`COMEÇA ${lutador(vez).b.nome} • MAIOR VELOCIDADE`);
          esperar(1.1, iniciarVez);
        } else {
          // depois de um nocaute quem perdeu a Beast age primeiro (battle.gd)
          vez = 0;
          iniciarVez();
        }
      });
    }

    function iniciarVez() {
      if (fase === "fim") return;
      rodada++;
      atualizarPlacar();
      const l = lutador(vez);
      // MoveDB.reduce_cooldowns e begin_fighter_turn
      for (const id of Object.keys(l.recargas)) l.recargas[id] = Math.max(0, l.recargas[id] - 1);
      if (l.escudo) {
        l.escudoTurnos--;
        if (l.escudoTurnos <= 0) {
          l.escudo = false;
          l.escudoRecarga = ESCUDO_RECARGA;
        }
      } else if (l.escudoRecarga > 0) {
        l.escudoRecarga--;
      }
      if (vez === 0) {
        if (!temAcao(l)) {
          fase = "acao";
          dizer("REAGRUPANDO • RECARGAS AVANÇAM");
          esperar(0.9, () => terminarAcao(0));
          return;
        }
        fase = "vez";
        foco = l.b.golpes.findIndex((id) => podeUsar(l, id));
        if (foco < 0) foco = 3;
        dizer(`SUA VEZ • ${l.b.nome}`);
      } else {
        fase = "acao";
        dizer("CPU CALCULANDO PESO, TIPO E RECARGA...");
        esperar(0.62, () => executar(1, escolhaCpu()));
      }
    }

    function temAcao(l) {
      return l.b.golpes.some((id) => podeUsar(l, id)) || podeEscudo(l) || proximoVivo(l.lado) >= 0;
    }

    // _escolha_da_cpu do battle.gd
    function escolhaCpu() {
      const cpu = lutador(1);
      const rival = lutador(0);
      const reserva = proximoVivo(1);
      if (cpu.vida / cpu.vidaMax < 0.24 && reserva >= 0 && Math.random() < 0.34) return { tipo: "trocar", para: reserva };
      if (Math.random() < 0.1 && podeEscudo(cpu)) return { tipo: "escudo" };
      let melhor = -1;
      let nota = -Infinity;
      cpu.b.golpes.forEach((id, i) => {
        if (!podeUsar(cpu, id)) return;
        const g = GOLPES[id];
        const dano = previsaoDano(cpu.b, rival.b, g);
        const n = dano - recargaEfetiva(g, cpu.b) * 1.7 + (dano >= rival.vida ? 14 : 0) + api.aleatorio(-1.8, 1.8);
        if (n > nota) { nota = n; melhor = i; }
      });
      if (melhor >= 0) return { tipo: "golpe", indice: melhor };
      if (podeEscudo(cpu)) return { tipo: "escudo" };
      if (reserva >= 0) return { tipo: "trocar", para: reserva };
      return { tipo: "esperar" };
    }

    function executar(lado, acao) {
      fase = "acao";
      if (acao.tipo === "golpe") atacar(lado, acao.indice);
      else if (acao.tipo === "escudo") defender(lado);
      else if (acao.tipo === "trocar") trocar(lado, acao.para);
      else {
        dizer("REAGRUPANDO • RECARGAS AVANÇAM");
        esperar(0.8, () => terminarAcao(lado));
      }
    }

    function terminarAcao(lado) {
      if (fase === "fim") return;
      vez = 1 - lado;
      iniciarVez();
    }

    function atacar(lado, indice) {
      const atk = lutador(lado);
      const alvo = 1 - lado;
      const def = lutador(alvo);
      const id = atk.b.golpes[indice];
      const golpe = GOLPES[id];
      const mult = multiplicador(golpe.elemento, def.b.tipo);
      let dano = Math.max(5, previsaoDano(atk.b, def.b, golpe) + api.inteiro(-2, 2));
      const protegido = def.escudo;
      if (protegido) dano = Math.max(4, Math.round(dano * ESCUDO_FATOR));
      atk.recargas[id] = recargaEfetiva(golpe, atk.b);
      const pesado = golpe.papel === "pesado";
      const cor = ELEMENTO[golpe.elemento];
      dizer(`${atk.b.nome} USA ${golpe.nome.toUpperCase()}`);

      // o pesado carrega antes; o efeito e o dano saem só no impacto
      const carga = pesado ? 0.6 : 0;
      if (pesado) { animar(atk, "carga", carga); api.som("moeda"); }
      esperar(carga, () => {
        animar(atk, "golpe", 0.6);
        api.som("whoosh");
        const de = POS[lado];
        const para = POS[alvo];
        projetil = {
          x0: de.x + (lado === 0 ? 30 : -20), y0: de.y - de.tam * 0.5,
          x1: para.x, y1: para.y - para.tam * 0.42,
          ini: tempo, dur: pesado ? 0.5 : 0.42, icone: golpe.icone, cor: cor.i, pesado,
        };
      });
      const impacto = carga + (pesado ? 0.5 : 0.42);
      esperar(impacto, () => {
        projetil = null;
        def.vida = Math.max(0, def.vida - dano);
        def.flash = 1;
        def.pose = 2;
        animar(def, "dano", 0.55);
        const p = POS[alvo];
        const cx = p.x;
        const cy = p.y - p.tam * 0.42;
        anel.push({ x: cx, y: cy, cor: cor.i, ini: tempo, dur: pesado ? 0.7 : 0.5, raio: p.tam * (pesado ? 0.75 : 0.5) });
        api.efeitos.explosao(cx, cy, {
          cor: [cor.cor, "#ffffff", cor.cor], n: pesado ? 42 : 24, velocidade: pesado ? 420 : 300,
          tamanho: pesado ? 6 : 4.5, gravidade: 380, vida: 0.8,
        });
        api.tremer(pesado ? 12 : 6);
        api.vibrar(pesado ? 60 : 25);
        api.som(pesado ? "soco" : "batida");
        if (mult >= 1.4) window.setTimeout(() => api.som("combo"), 120);
        else if (mult <= 0.7) window.setTimeout(() => api.som("quica"), 120);
        api.efeitos.texto(`-${dano}`, cx, cy - 30, { cor: cor.cor, tamanho: pesado ? 58 : 46, vida: 1.1 });
        const extra = protegido ? " • ESCUDO -52%" : "";
        api.efeitos.texto(textoEfeito(mult, golpe.elemento, def.b.tipo) + extra, cx, cy + 18, {
          cor: mult >= 1.4 ? "#7dffb0" : mult < 0.9 ? "#ffb36b" : "#ffffff", tamanho: 21, vida: 1.4,
        });
        if (lado === 0) {
          pontos += dano * (pesado ? 2 : 1);
          atualizarPlacar();
        }
      });
      esperar(impacto + 0.8, () => {
        if (def.vida <= 0) nocaute(alvo, lado);
        else terminarAcao(lado);
      });
    }

    function defender(lado) {
      const l = lutador(lado);
      const turnos = duracaoEscudo(l.b);
      l.escudo = true;
      l.escudoTurnos = turnos;
      l.escudoRecarga = 0;
      animar(l, "escudo", 0.6);
      dizer(`${l.b.nome} ERGUEU ESCUDO POR ${turnos} RODADA${turnos > 1 ? "S" : ""}`);
      api.som("ponto");
      const p = POS[lado];
      anel.push({ x: p.x, y: p.y - p.tam * 0.4, cor: CIANO, ini: tempo, dur: 0.6, raio: p.tam * 0.5 });
      esperar(0.85, () => terminarAcao(lado));
    }

    function trocar(lado, para) {
      const l = lutador(lado);
      if (l.escudo) {
        // trocar cancela o escudo e já põe a recarga dele para correr
        l.escudo = false;
        l.escudoTurnos = 0;
        l.escudoRecarga = ESCUDO_RECARGA;
      }
      animar(l, "sai", 0.35);
      api.som("whoosh");
      esperar(0.38, () => {
        l.entrou = false;
        entrar(lado, para);
        dizer(`${lutador(lado).b.nome} ENTRA NA ARENA`);
      });
      esperar(1.2, () => terminarAcao(lado));
    }

    function nocaute(derrotado, atacante) {
      const l = lutador(derrotado);
      l.ko = true;
      if (atacante === 0) {
        pontos += 250;
        nocautes++;
        atualizarPlacar();
      }
      dizer(`${l.b.nome} FORA DE COMBATE!`);
      api.som("strike");
      api.tremer(10);
      animar(l, "ko", 1);
      const p = POS[derrotado];
      api.efeitos.explosao(p.x, p.y - p.tam * 0.3, { cor: [ELEMENTO[l.b.tipo].cor, "#ffffff", "#333344"], n: 36, velocidade: 300, tamanho: 5, gravidade: 500, vida: 1 });
      esperar(1.15, () => {
        l.entrou = false;
        const prox = proximoVivo(derrotado);
        if (prox < 0) { encerrar(1 - derrotado); return; }
        if (derrotado === 0) { abrirEscolha("nocaute"); return; }
        entrar(1, prox);
        dizer(`${lutador(1).b.nome} ASSUME O DUELO`);
        esperar(1, () => { vez = 1; iniciarVez(); });
      });
    }

    function encerrar(ganhador) {
      fase = "fim";
      vencedor = ganhador;
      if (ganhador === 0) pontos += 1000;
      atualizarPlacar();
      const l = lutador(ganhador);
      animar(l, "comemora", 1.6);
      dizer(ganhador === 0 ? "VOCÊ VENCEU A BATALHA!" : "A CPU VENCEU A BATALHA!");
      api.efeitos.texto(ganhador === 0 ? "VITÓRIA!" : "DERROTA", LARGURA / 2, 300, {
        cor: ganhador === 0 ? "#ffd700" : "#ff5468", tamanho: 64, vida: 1.6,
      });
      esperar(1.7, () => {
        const de = vivos(0);
        api.terminar({
          pontos,
          titulo: ganhador === 0 ? "VITÓRIA!" : "DERROTA",
          detalhe: ganhador === 0
            ? `Você venceu em ${rodada} rodadas, com ${de} Beast${de > 1 ? "s" : ""} de pé · ${nocautes} nocautes`
            : `A CPU venceu na rodada ${rodada} · você nocauteou ${nocautes} de 3`,
        });
      });
    }

    /* ---------- entrada da pessoa ---------- */
    function contarCartas() {
      return times[0].length;
    }

    function posCarta(i, n) {
      const vao = 16;
      const total = n * CARTA.w + (n - 1) * vao;
      return { x: (LARGURA - total) / 2 + i * (CARTA.w + vao), y: CARTA.y, w: CARTA.w, h: CARTA.h };
    }

    function reservaDaVez() {
      // as duas outras Beasts do time, na ordem, para os retratos do HUD
      const r = [];
      for (let i = 0; i < times[0].length; i++) if (i !== ativo[0]) r.push(i);
      return r;
    }

    function posReserva(k) {
      return { x: HUD_EU.x + HUD_EU.w - 36 - (1 - k) * 58, y: HUD_EU.y + HUD_EU.h / 2 + 2, r: 24 };
    }

    function acionarBotao(i) {
      if (fase !== "vez") return;
      const l = lutador(0);
      if (i < 3) {
        const id = l.b.golpes[i];
        if (!podeUsar(l, id)) {
          dizer(`GOLPE EM RECARGA • AGUARDE ${turnosRecarga(l, id)} TURNO(S)`);
          api.som("erro");
          return;
        }
        api.som("clique");
        executar(0, { tipo: "golpe", indice: i });
      } else {
        if (!podeEscudo(l)) {
          dizer(l.escudo ? "O ESCUDO JÁ ESTÁ ERGUIDO" : `ESCUDO INDISPONÍVEL • RECARGA ${l.escudoRecarga}`);
          api.som("erro");
          return;
        }
        executar(0, { tipo: "escudo" });
      }
    }

    function pedirTroca(k) {
      if (fase !== "vez") return;
      const i = reservaDaVez()[k];
      if (i === undefined) return;
      if (times[0][i].ko) { dizer("ESSA BEAST ESTÁ FORA DE COMBATE"); api.som("erro"); return; }
      api.som("clique");
      executar(0, { tipo: "trocar", para: i });
    }

    /* ======================================================================
       DESENHO
       ====================================================================== */
    function retanguloRedondo(ctx, x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }

    // encolhe a fonte até o texto caber (nomes de golpe são compridos)
    const medidas = new Map();
    function tamanhoQueCabe(ctx, texto, largura, tamanho, peso) {
      const chave = texto + "|" + largura + "|" + tamanho;
      if (medidas.has(chave)) return medidas.get(chave);
      let t = tamanho;
      ctx.save();
      for (; t > 10; t--) {
        ctx.font = `${peso} ${t}px ${FONTE}`;
        if (ctx.measureText(texto).width <= largura) break;
      }
      ctx.restore();
      medidas.set(chave, t);
      return t;
    }

    function iconeTipo(ctx, tipo, x, y, tam) {
      if (!img.tipos) return;
      ctx.drawImage(img.tipos, ELEMENTO[tipo].i * 72, 0, 72, 72, x, y, tam, tam);
    }

    function iconeGolpe(ctx, i, x, y, tam) {
      if (!img.golpes) return;
      ctx.drawImage(img.golpes, (i % 6) * 80, Math.floor(i / 6) * 80, 80, 80, x, y, tam, tam);
    }

    function desenharFundo(ctx) {
      if (img.arena) ctx.drawImage(img.arena, 0, 0, LARGURA, ALTURA);
      else { ctx.fillStyle = "#08102a"; ctx.fillRect(0, 0, LARGURA, ALTURA); }
      // faixa de baixo escurece para os botões lerem bem
      const g = ctx.createLinearGradient(0, 600, 0, ALTURA);
      g.addColorStop(0, "rgba(2,5,16,0)");
      g.addColorStop(0.25, "rgba(2,5,16,0.82)");
      g.addColorStop(1, "rgba(2,5,16,0.96)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 600, LARGURA, ALTURA - 600);
      const t = ctx.createLinearGradient(0, 0, 0, 120);
      t.addColorStop(0, "rgba(2,5,16,0.85)");
      t.addColorStop(1, "rgba(2,5,16,0)");
      ctx.fillStyle = t;
      ctx.fillRect(0, 0, LARGURA, 120);
    }

    function desenharBeast(ctx, l) {
      if (!l.entrou && l.anim !== "ko") return;
      const p = POS[l.lado];
      const el = ELEMENTO[l.b.tipo];
      const k = Math.min(1, (tempo - l.animIni) / l.animDur);
      const animando = k < 1;
      let dx = 0;
      let dy = 0;
      let escala = 1;
      let alfa = 1;
      let pose = l.pose;
      // direção do ataque: o jogador avança para cima/direita, a CPU desce
      const ax = l.lado === 0 ? 1 : -1;
      const ay = l.lado === 0 ? -0.7 : 0.7;
      if (animando) {
        if (l.anim === "entra") {
          escala = k < 0.7 ? 0.3 + (k / 0.7) * 0.8 : 1.1 - ((k - 0.7) / 0.3) * 0.1;
          alfa = Math.min(1, k * 2.5);
        } else if (l.anim === "golpe") {
          pose = 1;
          const s = Math.sin(Math.PI * Math.min(1, k * 1.4));
          dx = ax * s * 46;
          dy = ay * s * 46;
        } else if (l.anim === "carga") {
          escala = 1 + k * 0.06;
          dx = (Math.random() - 0.5) * 4 * k;
        } else if (l.anim === "dano") {
          pose = 2;
          dx = -ax * (1 - k) * 22 + (Math.random() - 0.5) * 8 * (1 - k);
          dy = -ay * (1 - k) * 14;
        } else if (l.anim === "ko") {
          pose = 2;
          dy = k * 50;
          alfa = 1 - k;
          escala = 1 - k * 0.15;
        } else if (l.anim === "sai") {
          alfa = 1 - k;
          escala = 1 - k * 0.5;
        } else if (l.anim === "comemora") {
          dy = -Math.abs(Math.sin(k * Math.PI * 4)) * 26 * (1 - k * 0.5);
          pose = k % 0.25 < 0.12 ? 1 : 0;
        } else if (l.anim === "escudo") {
          escala = 1 + Math.sin(Math.PI * k) * 0.05;
        }
      } else if (l.anim === "ko") {
        return;
      } else {
        pose = 0;
      }
      if (!animando && l.anim === "dano") l.pose = 0;
      if (!animando && l.anim === "sai") return;

      const tam = p.tam * escala;
      // respiração parada: o peito sobe e desce de leve
      const resp = 1 + Math.sin(relogio * 2.4 + l.lado) * 0.018;
      const x = p.x + dx;
      const y = p.y + dy;

      // sombra e aura do elemento aos pés
      ctx.globalAlpha = 0.45 * alfa;
      ctx.fillStyle = "#000000";
      ctx.beginPath();
      ctx.ellipse(p.x, p.y - 4, p.tam * 0.34, p.tam * 0.07, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalCompositeOperation = "lighter";
      const pulso = 0.5 + 0.5 * Math.sin(relogio * 3 + l.lado * 2);
      brilho(ctx, el.i, p.x, p.y - 6, p.tam * 0.42, p.tam * 0.1, (0.35 + pulso * 0.2) * alfa);
      if (l.anim === "carga" && animando) brilho(ctx, el.i, x, y - tam * 0.45, tam * 0.5 * (0.5 + k), tam * 0.5 * (0.5 + k), 0.75 * k);
      ctx.globalCompositeOperation = "source-over";

      const folha = img[l.b.id];
      if (folha) {
        const sx = pose * QUADRO;
        const sy = l.lado === 0 ? 0 : QUADRO;
        const w = tam / resp;
        const h = tam * resp;
        ctx.globalAlpha = alfa;
        ctx.drawImage(folha, sx, sy, QUADRO, QUADRO, x - w / 2, y - h * 0.96, w, h);
        if (l.flash > 0.02) {
          // clarão do golpe recebido: a própria figura somada por cima
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = l.flash * 0.75;
          ctx.drawImage(folha, sx, sy, QUADRO, QUADRO, x - w / 2, y - h * 0.96, w, h);
          ctx.globalCompositeOperation = "source-over";
        }
      }
      ctx.globalAlpha = 1;

      if (l.escudo && l.anim !== "ko") {
        // cúpula do escudo (#59d7ff, a cor do guard.svg)
        const cx = p.x;
        const cy = p.y - p.tam * 0.42;
        const rx = p.tam * 0.46;
        const ry = p.tam * 0.5;
        ctx.globalCompositeOperation = "lighter";
        brilho(ctx, CIANO, cx, cy, rx * 1.1, ry * 1.1, 0.22 + pulso * 0.08);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 0.75;
        ctx.strokeStyle = "#59d7ff";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 0.35;
        ctx.lineWidth = 2;
        for (let i = 0; i < 3; i++) {
          const a = relogio * 1.6 + i * 2.1;
          ctx.beginPath();
          ctx.ellipse(cx, cy, rx * 0.92, ry * 0.92, 0, a, a + 0.7);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
    }

    function desenharProjetil(ctx) {
      if (!projetil) return;
      const pr = projetil;
      const k = Math.min(1, (tempo - pr.ini) / pr.dur);
      const ponto = (u) => {
        // arco: sobe um pouco no meio do caminho
        const x = pr.x0 + (pr.x1 - pr.x0) * u;
        const y = pr.y0 + (pr.y1 - pr.y0) * u - Math.sin(Math.PI * u) * 70;
        return [x, y];
      };
      ctx.globalCompositeOperation = "lighter";
      for (let i = 6; i >= 1; i--) {
        const u = Math.max(0, k - i * 0.05);
        const [x, y] = ponto(u);
        const r = (pr.pesado ? 34 : 24) * (1 - i / 8);
        brilho(ctx, pr.cor, x, y, r, r, 0.5 * (1 - i / 7));
      }
      const [x, y] = ponto(k);
      const tam = pr.pesado ? 84 : 64;
      brilho(ctx, pr.cor, x, y, tam, tam, 0.85);
      brilho(ctx, BRANCO, x, y, tam * 0.45, tam * 0.45, 0.6);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.sin(k * Math.PI * 3) * 0.25);
      iconeGolpe(ctx, pr.icone, -tam / 2, -tam / 2, tam);
      ctx.restore();
    }

    function desenharAneis(ctx) {
      for (let i = anel.length - 1; i >= 0; i--) {
        const a = anel[i];
        const k = (tempo - a.ini) / a.dur;
        if (k >= 1) { anel.splice(i, 1); continue; }
        const r = a.raio * (0.25 + k * 0.9);
        ctx.globalCompositeOperation = "lighter";
        brilho(ctx, a.cor, a.x, a.y, r * 1.2, r * 0.5, (1 - k) * 0.7);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 1 - k;
        ctx.strokeStyle = CORES_BRILHO[a.cor];
        ctx.lineWidth = 4 * (1 - k) + 1;
        ctx.beginPath();
        ctx.ellipse(a.x, a.y, r, r * 0.42, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }

    function barraVida(ctx, l, x, y, w, h) {
      ctx.fillStyle = "rgba(255,255,255,0.1)";
      retanguloRedondo(ctx, x, y, w, h, h / 2);
      ctx.fill();
      const fr = Math.max(0, l.vidaMostrada / l.vidaMax);
      const rastro = Math.max(0, l.vidaRastro / l.vidaMax);
      if (rastro > fr) {
        ctx.fillStyle = "rgba(255,255,255,0.75)";
        retanguloRedondo(ctx, x, y, Math.max(h, w * rastro), h, h / 2);
        ctx.fill();
      }
      if (fr > 0) {
        ctx.fillStyle = fr > 0.5 ? "#3dff9a" : fr > 0.25 ? "#ffd23d" : "#ff4d5e";
        retanguloRedondo(ctx, x, y, Math.max(h, w * fr), h, h / 2);
        ctx.fill();
      }
    }

    function desenharHudLutador(ctx, lado) {
      const caixa = lado === 0 ? HUD_EU : HUD_CPU;
      const l = lutador(lado);
      const el = ELEMENTO[l.b.tipo];
      ctx.fillStyle = "rgba(4,8,22,0.86)";
      retanguloRedondo(ctx, caixa.x, caixa.y, caixa.w, caixa.h, 14);
      ctx.fill();
      ctx.strokeStyle = lado === 0 ? "#6ef8ff" : "#ff55c6"; // COR_P1 / COR_P2 do battle.gd
      ctx.globalAlpha = 0.7;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.globalAlpha = 1;
      if (!l.entrou && fase !== "fim") {
        api.texto(ctx, lado === 0 ? "SUA BEAST" : "CPU", caixa.x + 18, caixa.y + caixa.h / 2, { tamanho: 16, peso: 800, alinhar: "left", cor: "rgba(255,255,255,0.5)" });
        return;
      }
      iconeTipo(ctx, l.b.tipo, caixa.x + 8, caixa.y + 7, caixa.h - 14);
      const nx = caixa.x + caixa.h + 2;
      api.texto(ctx, l.b.nome, nx, caixa.y + 17, { tamanho: 18, peso: 900, alinhar: "left", cor: "#ffffff" });
      api.texto(ctx, `${l.b.tipo.toUpperCase()} • ${l.b.classe.toUpperCase()} • ${String(l.b.peso).replace(".", ",")} kg`, nx + 132, caixa.y + 17, {
        tamanho: 11, peso: 800, alinhar: "left", cor: el.cor,
      });
      const bw = lado === 0 ? 250 : 330;
      barraVida(ctx, l, nx, caixa.y + 33, bw, 12);
      api.texto(ctx, `${Math.ceil(l.vidaMostrada)}/${l.vidaMax}`, nx + bw + 8, caixa.y + 40, { tamanho: 13, peso: 800, alinhar: "left", cor: "#ffffff" });
      if (l.escudo) {
        api.texto(ctx, `ESCUDO ${l.escudoTurnos}`, nx + bw - 4, caixa.y + 17, { tamanho: 11, peso: 900, alinhar: "right", cor: "#59d7ff" });
      }
      if (lado === 0) {
        // reserva: tocar no retrato troca de Beast (gasta a vez)
        const r = reservaDaVez();
        const podeTrocar = fase === "vez";
        r.forEach((i, k) => {
          const pos = posReserva(k);
          const m = times[0][i];
          ctx.save();
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, pos.r, 0, Math.PI * 2);
          ctx.fillStyle = "#0a1431";
          ctx.fill();
          ctx.clip();
          if (img[m.b.id]) {
            ctx.globalAlpha = m.ko ? 0.3 : 1;
            ctx.drawImage(img[m.b.id], 22, QUADRO + 18, 116, 116, pos.x - pos.r * 1.15, pos.y - pos.r * 1.05, pos.r * 2.3, pos.r * 2.3);
          }
          ctx.restore();
          ctx.globalAlpha = 1;
          ctx.strokeStyle = m.ko ? "#555b70" : podeTrocar ? "#59e98b" : ELEMENTO[m.b.tipo].cor;
          ctx.lineWidth = podeTrocar && !m.ko ? 3 : 2;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, pos.r, 0, Math.PI * 2);
          ctx.stroke();
          if (m.ko) {
            ctx.strokeStyle = "#ff4d5e";
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(pos.x - 10, pos.y - 10); ctx.lineTo(pos.x + 10, pos.y + 10);
            ctx.moveTo(pos.x + 10, pos.y - 10); ctx.lineTo(pos.x - 10, pos.y + 10);
            ctx.stroke();
          }
        });
        if (r.some((i) => !times[0][i].ko)) {
          const pos = posReserva(0);
          if (img.trocar && podeTrocar) ctx.drawImage(img.trocar, pos.x - 46, pos.y - 11, 22, 22);
        }
      }
    }

    function desenharTopo(ctx) {
      // VOCÊ ● ● ●   RODADA n   ● ● ● CPU
      api.texto(ctx, "VOCÊ", 16, 24, { tamanho: 15, peso: 900, alinhar: "left", cor: "#6ef8ff" });
      api.texto(ctx, "CPU", LARGURA - 16, 24, { tamanho: 15, peso: 900, alinhar: "right", cor: "#ff55c6" });
      for (let lado = 0; lado < 2; lado++) {
        times[lado].forEach((l, i) => {
          const x = lado === 0 ? 74 + i * 22 : LARGURA - 74 - i * 22;
          ctx.fillStyle = l.ko ? "#2a2f44" : ELEMENTO[l.b.tipo].cor;
          ctx.beginPath();
          ctx.arc(x, 24, 7, 0, Math.PI * 2);
          ctx.fill();
          if (lado === 1 && !l.entrou && !l.ko) {
            // a CPU não mostra a mão: só quem já entrou tem cor
            ctx.fillStyle = "#3b415c";
            ctx.beginPath();
            ctx.arc(x, 24, 7, 0, Math.PI * 2);
            ctx.fill();
          }
        });
      }
      if (rodada > 0) api.texto(ctx, `RODADA ${rodada}`, LARGURA / 2, 24, { tamanho: 14, peso: 800, cor: "rgba(255,255,255,0.75)" });
    }

    function desenharMensagem(ctx) {
      if (!mensagem) return;
      const idade = tempo - tempoMensagem;
      const pop = idade < 0.15 ? 0.85 + (idade / 0.15) * 0.15 : 1;
      const tam = tamanhoQueCabe(ctx, mensagem, LARGURA - 40, 17, 900);
      api.texto(ctx, mensagem, LARGURA / 2, MSG_Y, { tamanho: tam * pop, peso: 900, cor: "#ffe477", contorno: "rgba(0,0,0,.7)" });
    }

    function desenharBotoes(ctx) {
      const l = lutador(0);
      const ativoAgora = fase === "vez";
      const inimigo = lutador(1);
      for (let i = 0; i < 4; i++) {
        const bt = BOTOES[i];
        const pronto = i < 3 ? podeUsar(l, l.b.golpes[i]) : podeEscudo(l);
        ctx.globalAlpha = ativoAgora ? 1 : 0.45;
        ctx.fillStyle = "rgba(8,14,34,0.94)";
        retanguloRedondo(ctx, bt.x, bt.y, bt.w, bt.h, 14);
        ctx.fill();
        let corBorda = "#59d7ff";
        if (i < 3) {
          const g = GOLPES[l.b.golpes[i]];
          corBorda = ELEMENTO[g.elemento].cor;
          iconeGolpe(ctx, g.icone, bt.x + 10, bt.y + 13, 66);
          const tam = tamanhoQueCabe(ctx, g.nome, bt.w - 96, 17, 900);
          api.texto(ctx, g.nome, bt.x + 86, bt.y + 26, { tamanho: tam, peso: 900, alinhar: "left", cor: "#ffffff" });
          const papel = g.papel === "pesado" ? "PESADO" : g.papel === "rápido" ? "RÁPIDO" : "COBERTURA";
          api.texto(ctx, `${papel} • PODER ${g.poder}`, bt.x + 86, bt.y + 49, { tamanho: 12, peso: 800, alinhar: "left", cor: ELEMENTO[g.elemento].cor });
          if (inimigo.entrou) {
            const m = multiplicador(g.elemento, inimigo.b.tipo);
            const rotulo = m >= 1.4 ? "SUPER EFETIVO" : m <= 0.7 ? "RESISTE" : m < 0.9 ? "MESMO TIPO" : "NEUTRO";
            const cor = m >= 1.4 ? "#7dffb0" : m <= 0.7 ? "#ff6b7d" : m < 0.9 ? "#ffb36b" : "rgba(255,255,255,0.6)";
            api.texto(ctx, `${fmtMult(m)} ${rotulo}`, bt.x + 86, bt.y + 72, { tamanho: 12, peso: 900, alinhar: "left", cor });
          }
        } else {
          if (img.escudo) ctx.drawImage(img.escudo, bt.x + 12, bt.y + 15, 62, 62);
          api.texto(ctx, "ESCUDO", bt.x + 86, bt.y + 26, { tamanho: 17, peso: 900, alinhar: "left", cor: "#ffffff" });
          api.texto(ctx, "DANO -52%", bt.x + 86, bt.y + 49, { tamanho: 12, peso: 800, alinhar: "left", cor: "#59d7ff" });
          api.texto(ctx, `${duracaoEscudo(l.b)} RODADA${duracaoEscudo(l.b) > 1 ? "S" : ""} • RECARGA ${ESCUDO_RECARGA}`, bt.x + 86, bt.y + 72, {
            tamanho: 12, peso: 900, alinhar: "left", cor: "rgba(255,255,255,0.6)",
          });
        }
        ctx.strokeStyle = corBorda;
        ctx.lineWidth = ativoAgora && foco === i ? 3.5 : 2;
        retanguloRedondo(ctx, bt.x, bt.y, bt.w, bt.h, 14);
        ctx.stroke();
        if (ativoAgora && foco === i) {
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = 0.18 + 0.12 * Math.sin(relogio * 6);
          ctx.fillStyle = corBorda;
          retanguloRedondo(ctx, bt.x, bt.y, bt.w, bt.h, 14);
          ctx.fill();
          ctx.globalCompositeOperation = "source-over";
        }
        // tecla de atalho no canto
        ctx.globalAlpha = ativoAgora ? 0.55 : 0.3;
        api.texto(ctx, String(i + 1), bt.x + bt.w - 14, bt.y + 16, { tamanho: 12, peso: 900, cor: "#ffffff" });
        if (!pronto) {
          ctx.globalAlpha = 1;
          ctx.fillStyle = "rgba(2,4,12,0.72)";
          retanguloRedondo(ctx, bt.x, bt.y, bt.w, bt.h, 14);
          ctx.fill();
          let txt;
          if (i < 3) {
            const n = turnosRecarga(l, l.b.golpes[i]);
            txt = `RECARGA ${n} TURNO${n > 1 ? "S" : ""}`;
          } else txt = l.escudo ? `ESCUDO ATIVO • ${l.escudoTurnos}` : `RECARGA ${l.escudoRecarga}`;
          api.texto(ctx, txt, bt.x + bt.w / 2, bt.y + bt.h / 2, { tamanho: 15, peso: 900, cor: "rgba(255,255,255,0.85)" });
        }
        ctx.globalAlpha = 1;
      }
    }

    function veredito(meu, deles) {
      const a = multiplicador(meu, deles);
      const d = multiplicador(deles, meu);
      if (a > d) return ["VANTAGEM", "#3dff9a"];
      if (a < d) return ["DESVANTAGEM", "#ff5468"];
      if (a >= 1.4) return ["RIVAIS", "#c58bff"];
      if (a < 0.9) return ["MESMO TIPO", "#ffb36b"];
      return ["NEUTRO", "#b8c4e0"];
    }

    function desenharCarta(ctx, l, x, y, w, h, destaque) {
      const arte = img[l.b.id + "_carta"];
      ctx.save();
      ctx.globalAlpha = l.ko ? 0.35 : 1;
      if (destaque) {
        ctx.globalCompositeOperation = "lighter";
        brilho(ctx, ELEMENTO[l.b.tipo].i, x + w / 2, y + h / 2, w * 0.85, h * 0.7, 0.55);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = l.ko ? 0.35 : 1;
      }
      retanguloRedondo(ctx, x, y, w, h, 12);
      ctx.clip();
      if (arte) ctx.drawImage(arte, x, y, w, h);
      else { ctx.fillStyle = ELEMENTO[l.b.tipo].cor; ctx.fillRect(x, y, w, h); }
      ctx.restore();
      ctx.strokeStyle = destaque ? "#ffffff" : "rgba(255,255,255,0.35)";
      ctx.lineWidth = destaque ? 3 : 1.5;
      retanguloRedondo(ctx, x, y, w, h, 12);
      ctx.stroke();
      if (l.ko) api.texto(ctx, "FORA", x + w / 2, y + h / 2, { tamanho: 28, peso: 900, cor: "#ff5468", contorno: "rgba(0,0,0,.8)" });
    }

    function desenharEscolha(ctx, interativo) {
      const g = ctx.createLinearGradient(0, 470, 0, 520);
      g.addColorStop(0, "rgba(2,5,16,0)");
      g.addColorStop(1, "rgba(2,5,16,0.9)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 470, LARGURA, 50);
      ctx.fillStyle = "rgba(2,5,16,0.9)";
      ctx.fillRect(0, 520, LARGURA, ALTURA - 520);
      const inimigo = lutador(1);
      const temInimigo = inimigo.entrou;
      api.texto(ctx, motivoEscolha === "inicio" ? "ESCOLHA SUA BEAST" : "ESCOLHA A PRÓXIMA", LARGURA / 2, 498, {
        tamanho: 26, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.6)",
      });
      const n = contarCartas();
      times[0].forEach((l, i) => {
        const c = posCarta(i, n);
        if (cartaVoando && cartaVoando.i === i) return;
        const sobe = interativo && focoCarta === i ? -10 : 0;
        desenharCarta(ctx, l, c.x, c.y + sobe, c.w, c.h, interativo && focoCarta === i && !l.ko);
        if (temInimigo && !l.ko) {
          const [rotulo, cor] = veredito(l.b.tipo, inimigo.b.tipo);
          ctx.fillStyle = "rgba(4,8,22,0.92)";
          retanguloRedondo(ctx, c.x + 6, c.y + c.h + 10, c.w - 12, 28, 14);
          ctx.fill();
          ctx.strokeStyle = cor;
          ctx.lineWidth = 2;
          ctx.stroke();
          api.texto(ctx, rotulo, c.x + c.w / 2, c.y + c.h + 25, { tamanho: 13, peso: 900, cor });
        }
        if (interativo && !l.ko) api.texto(ctx, String(i + 1), c.x + c.w - 14, c.y + 16 + sobe, { tamanho: 13, peso: 900, cor: "#ffffff", contorno: "rgba(0,0,0,.8)" });
      });
      if (temInimigo) {
        // a roda dos tipos resumida para o elemento da CPU
        const t = inimigo.b.tipo;
        const perde = ELEMENTOS.filter((e) => e.vence.includes(t)).map((e) => e.nome);
        api.texto(ctx, `${inimigo.b.nome} É ${t.toUpperCase()}`, LARGURA / 2, 818, { tamanho: 16, peso: 900, cor: ELEMENTO[t].cor });
        api.texto(ctx, `vence ${ELEMENTO[t].vence.join(" e ")} • perde para ${perde.join(" e ")}`, LARGURA / 2, 844, {
          tamanho: 14, peso: 700, cor: "rgba(255,255,255,0.8)",
        });
      }
      api.texto(ctx, interativo ? "Toque na carta para mandar a Beast para a arena" : "", LARGURA / 2, 900, {
        tamanho: 14, peso: 700, cor: "rgba(255,255,255,0.55)",
      });
    }

    function desenharCartaVoando(ctx) {
      if (!cartaVoando) return;
      const cv = cartaVoando;
      const k = Math.min(1, (tempo - cv.ini) / 0.38);
      const e = 1 - (1 - k) * (1 - k);
      const p = POS[0];
      const x = cv.x + (p.x - cv.w / 2 - cv.x) * e;
      const y = cv.y + (p.y - p.tam * 0.6 - cv.y) * e;
      const esc = 1 - e * 0.55;
      ctx.save();
      ctx.translate(x + cv.w / 2, y + cv.h / 2);
      ctx.rotate(e * 0.5);
      ctx.scale(esc, esc);
      desenharCarta(ctx, times[0][cv.i], -cv.w / 2, -cv.h / 2, cv.w, cv.h, true);
      ctx.restore();
    }

    function desenharCapa(ctx) {
      desenharFundo(ctx);
      // três cartas em leque, só como vitrine atrás da capa do console
      const mostra = ["helionce", "vulcora", "tempestral"];
      mostra.forEach((id, i) => {
        const arte = img[id + "_carta"];
        if (!arte) return;
        ctx.save();
        ctx.translate(LARGURA / 2 + (i - 1) * 120, 560 + Math.abs(i - 1) * 20);
        ctx.rotate((i - 1) * 0.22 + Math.sin(relogio * 1.2 + i) * 0.02);
        ctx.drawImage(arte, -95, -142, 190, 285);
        ctx.restore();
      });
      if (img.tipos) {
        for (let i = 0; i < 8; i++) {
          const a = relogio * 0.3 + (i / 8) * Math.PI * 2;
          ctx.globalAlpha = 0.85;
          iconeTipo(ctx, ELEMENTOS[i].nome, LARGURA / 2 + Math.cos(a) * 230 - 22, 300 + Math.sin(a) * 90 - 22, 44);
        }
        ctx.globalAlpha = 1;
      }
    }

    /* ======================================================================
       A PARTIDA (contrato do console)
       ====================================================================== */
    return {
      iniciar() {
        chamadasIniciar++;
        fase = chamadasIniciar === 1 ? "capa" : "pronto";
        tempo = 0;
        rodada = 0;
        pontos = 0;
        nocautes = 0;
        vez = 0;
        vencedor = -1;
        agenda = [];
        anel = [];
        projetil = null;
        cartaVoando = null;
        mensagem = "";
        motivoEscolha = "inicio";
        foco = 0;
        focoCarta = 0;
        placarInfo = "";
        sortearTimes();
        api.placar({ pontos: 0, tempo: null, info: "" });
      },

      atualizar(dt) {
        if (fase === "pronto") { fase = "abertura"; abrirPartida(); }
        tempo += dt;
        // agenda de passos da batalha (tudo anda no relógio do jogo, então a
        // pausa do console congela a luta no meio do golpe sem descasar nada)
        for (let i = 0; i < agenda.length; i++) {
          if (agenda[i].quando <= tempo) {
            const passo = agenda.splice(i--, 1)[0];
            passo.fn();
          }
        }
        for (let lado = 0; lado < 2; lado++) {
          for (const l of times[lado]) {
            l.flash = Math.max(0, l.flash - dt * 3.5);
            // a barra desce rápido e o rastro branco vem atrás
            l.vidaMostrada += (l.vida - l.vidaMostrada) * Math.min(1, dt * 9);
            if (Math.abs(l.vidaMostrada - l.vida) < 0.05) l.vidaMostrada = l.vida;
            if (l.vidaRastro > l.vidaMostrada) l.vidaRastro = Math.max(l.vidaMostrada, l.vidaRastro - dt * 40);
            else l.vidaRastro = l.vidaMostrada;
          }
        }
      },

      desenhar(ctx) {
        relogio = performance.now() / 1000;
        if (fase === "capa") { desenharCapa(ctx); return; }
        desenharFundo(ctx);
        desenharTopo(ctx);
        desenharAneis(ctx);
        // a CPU (mais longe) primeiro; quem está perto fica na frente
        desenharBeast(ctx, lutador(1));
        desenharBeast(ctx, lutador(0));
        desenharProjetil(ctx);
        desenharHudLutador(ctx, 1);
        const escolhendo = fase === "escolha" || fase === "pronto" || fase === "abertura" || (cartaVoando !== null);
        if (escolhendo) {
          desenharEscolha(ctx, fase === "escolha");
          desenharCartaVoando(ctx);
          if (fase !== "pronto") desenharMensagemTopo(ctx);
        } else {
          desenharHudLutador(ctx, 0);
          desenharMensagem(ctx);
          desenharBotoes(ctx);
        }
      },

      apertar(x, y) {
        if (fase === "escolha") {
          const n = contarCartas();
          for (let i = 0; i < n; i++) {
            const c = posCarta(i, n);
            if (x >= c.x && x <= c.x + c.w && y >= c.y - 12 && y <= c.y + c.h + 40) { escolherCarta(i); return; }
          }
          return;
        }
        if (fase !== "vez") return;
        for (let i = 0; i < 4; i++) {
          const b = BOTOES[i];
          if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) { foco = i; acionarBotao(i); return; }
        }
        const r = reservaDaVez();
        for (let k = 0; k < r.length; k++) {
          const p = posReserva(k);
          if (Math.hypot(x - p.x, y - p.y) <= p.r + 10) { pedirTroca(k); return; }
        }
      },

      tecla(codigo, apertada) {
        if (!apertada) return;
        const digito = /^(Digit|Numpad)([1-9])$/.exec(codigo);
        const n = digito ? Number(digito[2]) : 0;
        if (fase === "escolha") {
          const total = contarCartas();
          if (n >= 1 && n <= total) { escolherCarta(n - 1); return; }
          if (codigo === "ArrowLeft" || codigo === "KeyA" || codigo === "ArrowRight" || codigo === "KeyD") {
            const passo = codigo === "ArrowLeft" || codigo === "KeyA" ? -1 : 1;
            for (let k = 1; k <= total; k++) {
              const i = (focoCarta + passo * k + total * 3) % total;
              if (!times[0][i].ko) { focoCarta = i; api.som("clique"); break; }
            }
          } else if (codigo === "Enter" || codigo === "Space" || codigo === "NumpadEnter") {
            escolherCarta(focoCarta);
          }
          return;
        }
        if (fase !== "vez") return;
        if (n >= 1 && n <= 4) { foco = n - 1; acionarBotao(n - 1); return; }
        if (n === 5 || n === 6) { pedirTroca(n - 5); return; }
        if (codigo === "KeyT") { const r = reservaDaVez(); const k = r.findIndex((i) => !times[0][i].ko); if (k >= 0) pedirTroca(k); return; }
        const mov = { ArrowLeft: -1, KeyA: -1, ArrowRight: 1, KeyD: 1, ArrowUp: -2, KeyW: -2, ArrowDown: 2, KeyS: 2 }[codigo];
        if (mov) {
          foco = (foco + mov + 8) % 4;
          api.som("clique");
        } else if (codigo === "Enter" || codigo === "Space" || codigo === "NumpadEnter") {
          acionarBotao(foco);
        }
      },

      destruir() {
        agenda = [];
        fase = "fim";
      },
    };

    // enquanto a mão está aberta, a mensagem sobe para cima das cartas
    function desenharMensagemTopo(ctx) {
      if (!mensagem) return;
      const tam = tamanhoQueCabe(ctx, mensagem, LARGURA - 40, 16, 900);
      api.texto(ctx, mensagem, LARGURA / 2, 128, { tamanho: tam, peso: 900, cor: "#ffe477", contorno: "rgba(0,0,0,.75)" });
    }
  },
};
