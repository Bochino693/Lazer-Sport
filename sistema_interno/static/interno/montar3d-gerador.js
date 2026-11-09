/* ======================================================================
   O PROJETISTA AUTOMÁTICO do "Montar em 3D": monta sozinho um brinquedão,
   um espaço esportivo kids, uma área ninja, um trampolim park ou um espaço
   baby nas medidas do lugar e na COR-TEMA escolhida. Não é um modelo de
   linguagem: são as regras do ramo, escritas aqui, com sorteio para cada
   ideia sair diferente ("Outra ideia" troca a semente).

   AS REGRAS (o que se vê nos playgrounds indoor de verdade -- as fábricas
   que o cliente mostrou: Nogueira, Brinquedão & Diversão, Kid Play; só o
   padrão do ramo, nenhum desenho copiado):
     * brinquedão: estrutura tubular de uma cor só, em módulos de ~1,05 m
       (1,25 m nos espaços largos); os catálogos vão de 2,65 a 5,30 m de
       comprimento e de 2,40 a 4,35 m de altura, com pisos a cada 0,80 m
       nos baixinhos, 0,85 m nos médios e 1,0 m nos altos (até 3 níveis);
       pisos de duas cores cortados na diagonal; rede de proteção de 1,0 m
       em todo lado de nível elevado que não dá para outro módulo, com
       janelas redondas na frente e painéis ábaco nos lados; o tobogã
       espiral (quase sempre de tubo fechado) ou o escorregador sai do nível
       mais alto, para fora, com a boca de frente para a torre; a piscina de
       bolinhas fica no chão, DEBAIXO do 2º nível; rolos de espuma entre
       dois pisos; bolas penduradas no alto; túnel de rede entre torres;
       colmeia de hexágonos empilhados do lado, com degraus de espuma na
       entrada; subida por degraus de espuma nos baixinhos; piso de EVA;
       telhado ou teto em arco nas torres quando o pé-direito deixa;
     * os ESTILOS: colorido (a paleta da cor raiz), neon (estrutura cinza,
       piso escuro e fitas de LED na cor raiz) e selva (estrutura de
       madeira, grama, teto em arco, tobogã aberto e piscina redonda);
     * O QUE A CASA FAZ ENSINA: o módulo e a distância entre os pisos mais
       usados nas montagens guardadas viram o padrão do projetista;
     * espaço esportivo kids: quadra com traves e tabelas na altura das
       crianças, tela de proteção, parede de escalada com colchão e camas
       elásticas na faixa que sobra;
     * área ninja: circuito em linha (ida e volta, se couber) -- degraus
       ninja, trave, argolas, barra de macaco, corda e a parede curva no
       fim --, tudo sobre colchões;
     * trampolim park (como o de dentro do Espaço Esportivo Modelo 1): camas
       em grade com o estofado colorido, piscina de espuma no fim, pista de
       enterrada, trampolim de parede, escalada sobre a espuma, queimada,
       tela em volta e escadinha -- mais coisas a cada PORTE (ver PORTES);
     * espaço baby (0 a 3 anos): tudo baixo -- piso de EVA, cerca de 0,6 m,
       portal, piscina rasa com plataforma de 0,4 m e escorregador, blocos
       de espuma, túnel, casinha, painéis ábaco, bolas penduradas e rampa.
   O espaço esportivo, o trampolim park e o baby têm PORTES (compacto, médio,
   grande) pelo tamanho; o cliente escolhe na página entre os que cabem.
   É um RASCUNHO para conversar com o cliente: o projeto final segue a
   norma de playgrounds (ABNT NBR 16071) e a engenharia da fábrica.
   ====================================================================== */

/* ---------------------------------------------------------------- cores */
function hexParaHsl(hex) {
  const n = parseInt(String(hex || "#2563eb").replace("#", "").padEnd(6, "0").slice(0, 6), 16);
  const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h *= 60;
  }
  return [h, s, l];
}
function hslParaHex(h, s, l) {
  h = ((h % 360) + 360) % 360;
  s = Math.min(1, Math.max(0, s));
  l = Math.min(1, Math.max(0, l));
  const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = l - c / 2;
  const [r, g, b] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return "#" + [r, g, b].map((v) => Math.round((v + m) * 255).toString(16).padStart(2, "0")).join("");
}

/**
 * A paleta de uma cor raiz: cada PAPEL das peças ganha a sua cor.
 *   estrutura  a própria cor (os tubos, as colunas)
 *   piso       a vizinha (as plataformas, a quadra)
 *   destaque   a complementar (tobogãs, painéis, túneis)
 *   acento     a de 60° (escadas, agarras, obstáculos)
 *   apoio      a raiz bem escura (redes, telas)
 *   protecao   a complementar clara (colchões, espuma)
 *   clara      a raiz clara (detalhes)
 * `varias`: as cores para alternar nas plataformas e painéis (o colorido das referências).
 */
export function paletaDaCor(hex, estilo) {
  const [h, s0, l0] = hexParaHsl(hex);
  const s = Math.max(0.6, s0), l = Math.min(0.56, Math.max(0.42, l0));
  const p = {
    estrutura: hslParaHex(h, s, l),
    piso: hslParaHex(h + 32, s, 0.55),
    destaque: hslParaHex(h + 180, Math.max(0.7, s), 0.52),
    acento: hslParaHex(h + 60, 0.9, 0.55),
    apoio: hslParaHex(h, 0.35, 0.16),
    protecao: hslParaHex(h + 180, 0.55, 0.72),
    clara: hslParaHex(h, 0.65, 0.76),
    led: hslParaHex(h, 1, 0.62),
    madeira: "#6b4f3a",
  };
  p.varias = [hslParaHex(h + 120, 0.8, 0.52), p.acento, p.destaque, hslParaHex(h + 300, 0.75, 0.6), p.piso, hslParaHex(h + 210, 0.8, 0.55)];
  p.chao = p.varias[0];
  p.chao2 = p.acento;
  if (estilo === "neon") {
    Object.assign(p, { estrutura: "#4b5563", apoio: "#0f172a", chao: "#1f2937", chao2: "#334155" });
  } else if (estilo === "selva") {
    Object.assign(p, { estrutura: "#6b4f3a", apoio: "#3b2f25", chao: "#4caf50", chao2: "#4caf50" });
  }
  return p;
}

/** Os estilos do projetista (e da cor-tema). */
export const ESTILOS = {
  colorido: { nome: "Colorido", amostra: "conic-gradient(#2563eb 0 25%, #facc15 0 50%, #ef4444 0 75%, #22c55e 0)" },
  neon: { nome: "Neon", amostra: "linear-gradient(135deg, #4b5563 45%, #3fd0ff 45% 65%, #d946ef 65%)" },
  selva: { nome: "Selva (madeira e grama)", amostra: "linear-gradient(135deg, #6b4f3a 50%, #4caf50 50%)" },
};

/** O tema do cores3d.js (as famílias do desenho original) feito da cor raiz: para os objetos .glb. */
export function familiasDaCor(hex) {
  const p = paletaDaCor(hex);
  return {
    verde: p.estrutura, azul: p.estrutura, amarelo: p.acento, laranja: p.destaque, vermelho: p.varias[3],
    ciano: p.piso, roxo: p.varias[5], rosa: p.varias[0],
  };
}

/** De que papel é cada peça (para a cor-tema). */
export const PAPEL = {
  coluna: "estrutura", barra: "estrutura", macaco: "estrutura", argolas: "estrutura", corda: "estrutura",
  trave: "estrutura", tabela: "estrutura", gol: "clara", cerca: "estrutura", escada: "acento", arco: "destaque",
  plataforma: "varias", piso_eva: "chao", quadra: "piso", painel: "varias", janela: "varias", abaco: "varias",
  escorregador: "destaque", toboga: "destaque", tunel: "varias", rolos: "varias", colmeia: "acento", pendulos: "varias",
  degraus: "acento", rede: "apoio", tunel_rede: "apoio", colchao: "protecao", espuma: "varias", cama: "estrutura",
  piscina: "destaque", piscina_redonda: "madeira", degraus_espuma: "varias", rampa: "acento", telhado: "destaque",
  teto_arco: "estrutura", led: "led", escalada: "acento", parede_curva: "acento",
};
export function corDoPapel(paleta, tipo, indice) {
  const papel = PAPEL[tipo] || "estrutura";
  if (papel === "varias") return paleta.varias[(indice || 0) % paleta.varias.length];
  return paleta[papel] || paleta.estrutura;
}

/* ---------------------------------------------------------------- os projetos */
export const PROJETOS = {
  brinquedao: {
    nome: "Brinquedão", sub: "playground indoor em torres", icone: "bi-bricks",
    medidas: { largura: 6.5, profundidade: 3.2, altura: 3.4 },
  },
  esportivo: {
    nome: "Espaço esportivo kids", sub: "quadra, escalada e camas", icone: "bi-dribbble",
    medidas: { largura: 18, profundidade: 10, altura: 5 },
  },
  ninja: {
    nome: "Área ninja", sub: "circuito de obstáculos", icone: "bi-lightning-charge-fill",
    medidas: { largura: 16, profundidade: 5, altura: 4 },
  },
  trampolim: {
    nome: "Trampolim park", sub: "camas, espuma e enterrada", icone: "bi-arrows-collapse-vertical",
    medidas: { largura: 14, profundidade: 9, altura: 5 },
  },
  baby: {
    nome: "Espaço baby", sub: "0 a 3 anos, tudo baixo", icone: "bi-balloon-heart-fill",
    medidas: { largura: 5, profundidade: 4, altura: 2.6 },
  },
};

function sorteio(semente) {
  let a = (semente >>> 0) || 1;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const arred = (v) => Math.round(v * 1000) / 1000;
const contar = (n, um, varios) => (n ? `${n} ${n > 1 ? varios : um}` : "");
const m2 = (v) => (Math.round(v * 100) / 100).toFixed(2).replace(".", ",");

class Projeto {
  constructor(paleta) {
    this.pecas = [];
    this.paleta = paleta;
    this.contagem = {};
    this.cores = {};
  }
  por(tipo, p, d, r = 0, cor, extra) {
    const indice = (this.cores[tipo] = (this.cores[tipo] || 0) + 1) - 1;
    this.pecas.push(Object.assign({ tipo, p: p.map(arred), r: arred(r), d, cor: cor || corDoPapel(this.paleta, tipo, indice) }, extra || {}));
    this.contagem[tipo] = (this.contagem[tipo] || 0) + 1;
  }
}

const NOMES = {
  coluna: ["coluna", "colunas"], barra: ["barra", "barras"], plataforma: ["plataforma", "plataformas"],
  rede: ["rede de proteção", "redes de proteção"], janela: ["painel com janela", "painéis com janela"],
  painel: ["painel", "painéis"], escorregador: ["escorregador", "escorregadores"], toboga: ["tobogã espiral", "tobogãs espirais"],
  tunel: ["túnel", "túneis"], tunel_rede: ["túnel de rede", "túneis de rede"], rolos: ["conjunto de rolos", "conjuntos de rolos"],
  colmeia: ["colmeia", "colmeias"], piscina: ["piscina de bolinhas", "piscinas de bolinhas"], cama: ["cama elástica", "camas elásticas"],
  escada: ["escada", "escadas"], telhado: ["telhado", "telhados"], piso_eva: ["piso de EVA", "pisos de EVA"],
  quadra: ["quadra", "quadras"], gol: ["trave", "traves"], tabela: ["tabela de basquete", "tabelas de basquete"],
  cerca: ["tela de proteção", "telas de proteção"], escalada: ["parede de escalada", "paredes de escalada"],
  colchao: ["colchão", "colchões"], degraus: ["conjunto de degraus ninja", "conjuntos de degraus ninja"], trave: ["trave de equilíbrio", "traves de equilíbrio"],
  argolas: ["conjunto de argolas", "conjuntos de argolas"], macaco: ["barra de macaco", "barras de macaco"], corda: ["corda", "cordas"],
  parede_curva: ["parede curva", "paredes curvas"], espuma: ["piscina de espuma", "piscinas de espuma"],
  rampa: ["rampa", "rampas"], degraus_espuma: ["escadinha de espuma", "escadinhas de espuma"], arco: ["portal", "portais"],
  abaco: ["painel ábaco", "painéis ábaco"], pendulos: ["conjunto de bolas penduradas", "conjuntos de bolas penduradas"],
  piscina_redonda: ["piscina redonda", "piscinas redondas"], teto_arco: ["teto em arco", "tetos em arco"], led: ["fita de LED", "fitas de LED"],
};
function resumoDe(contagem) {
  return Object.entries(contagem).map(([tipo, n]) => `${n} ${(NOMES[tipo] || [tipo, tipo])[n > 1 ? 1 : 0]}`);
}

/* ---------------------------------------------------------------- brinquedão */
function brinquedao(P, W, D, H, sorte, op) {
  const regras = [];
  const pal = P.paleta, estilo = op.estilo || "colorido";
  const aprendido = op.aprendido || {};
  // os pisos: a cada 0,80 m nos baixinhos (pé-direito até 3,2 m), 0,85 m nos médios e 1,0 m nos altos
  const nivelAprendido = Number(aprendido.nivel) >= 0.7 && Number(aprendido.nivel) <= 1.3 ? Number(aprendido.nivel) : 0;
  const L = nivelAprendido || (H >= 4.2 ? 1.0 : H >= 3.2 ? 0.85 : 0.8);
  const niveis = Math.max(1, Math.min(3, Math.floor((H - 0.95) / L)));
  const topo = niveis * L;
  // o módulo: ~1,05 m (o padrão das fábricas); 1,25 m nos espaços largos
  const moduloAprendido = Number(aprendido.modulo) >= 0.9 && Number(aprendido.modulo) <= 1.6 ? Number(aprendido.modulo) : 0;
  let m = moduloAprendido || (W >= 9 ? 1.25 : 1.05);
  // a saída: tobogã espiral com 2+ níveis (tubo fechado ou calha); escorregador com 1
  const espiral = niveis >= 2;
  const R = W < 6 ? 0.75 : m >= 1.2 ? 1.0 : 0.9; // nos espaços pequenos, a espiral é mais fechada
  const saida = espiral ? 2 * R + 0.45 : Math.min(W * 0.4, topo * 1.9 + 0.4);
  // a colmeia (hexágonos empilhados) do lado de fora, quando sobra largura
  let colmeia = espiral && W >= 6 ? 1.0 : 0;
  let nx = Math.floor((W - saida - colmeia) / m);
  if (nx < 2 && colmeia) { colmeia = 0; nx = Math.floor((W - saida) / m); }
  if (nx < 2) { nx = 2; m = Math.max(0.9, (W - saida) / 2); }
  const nz = Math.max(1, Math.min(4, Math.floor((D - 0.7) / m)));
  const usado = colmeia + nx * m + saida;
  const x0 = -usado / 2 + colmeia, z0 = -nz * m / 2;
  const fonte = moduloAprendido || nivelAprendido ? " (o que mais aparece nas montagens guardadas)" : "";
  regras.push(`Módulos de ${m2(m)} m (${nx} × ${nz}), ${niveis} ${niveis > 1 ? "níveis" : "nível"}: pisos a cada ${m2(L)} m${fonte}.`);

  // até onde vai cada módulo (t) e onde começa (b): a piscina fica DEBAIXO da estrutura, no chão
  const t = [], b = [];
  for (let i = 0; i < nx; i++) {
    t.push([]); b.push([]);
    for (let k = 0; k < nz; k++) {
      t[i][k] = i === nx - 1 ? niveis : Math.max(1, niveis - (sorte() < 0.4 ? 1 : 0));
      b[i][k] = 1;
    }
  }
  const piscinaI = Math.min(nx - 2, Math.floor(sorte() * Math.max(1, nx - 1)));
  const piscinaK = nz - 1;
  const redonda = estilo === "selva" && D - nz * m >= 2.2;
  let piscinaDebaixo = false;
  if (!redonda) {
    if (niveis >= 2) { b[piscinaI][piscinaK] = 2; t[piscinaI][piscinaK] = Math.max(2, t[piscinaI][piscinaK]); piscinaDebaixo = true; }
    else if (nx >= 3 || nz >= 2) t[piscinaI][piscinaK] = 0;
  }
  const kSaida = Math.floor(sorte() * nz);
  const cx = (i) => x0 + (i + 0.5) * m;
  const cz = (k) => z0 + (k + 0.5) * m;
  const tem = (i, k, n) => i >= 0 && k >= 0 && i < nx && k < nz && n >= b[i][k] && n <= t[i][k];
  const alto = (i, k) => (i < 0 || k < 0 || i >= nx || k >= nz ? 0 : t[i][k]);

  // o piso: EVA em xadrez (neon: escuro; selva: grama lisa)
  P.por("piso_eva", [0, 0, 0],
    { largura: arred(Math.min(W, usado + 0.6)), profundidade: arred(Math.min(D, nz * m + 1.4)) }, 0, pal.chao, { cor2: pal.chao2 });

  // as colunas, em cada nó, até 1,0 m acima do piso mais alto em volta
  for (let i = 0; i <= nx; i++) {
    for (let k = 0; k <= nz; k++) {
      const em = Math.max(alto(i - 1, k - 1), alto(i, k - 1), alto(i - 1, k), alto(i, k));
      if (em < 1) continue;
      P.por("coluna", [x0 + i * m, 0, z0 + k * m], { altura: arred(em * L + 1.0), diametro: 0.06 }, 0, pal.estrutura);
    }
  }
  // os pisos (de duas cores na diagonal, metade deles) e a proteção de cada nível
  let redes = 0, janelas = 0, abacos = 0, bicolores = 0;
  for (let i = 0; i < nx; i++) {
    for (let k = 0; k < nz; k++) {
      for (let n = b[i][k]; n <= t[i][k]; n++) {
        const cor = pal.varias[(i * 3 + k * 2 + n) % pal.varias.length];
        const extra = sorte() < 0.5 ? { cor2: pal.varias[(i * 3 + k * 2 + n + 2) % pal.varias.length] } : null;
        if (extra) bicolores++;
        P.por("plataforma", [cx(i), n * L - 0.05, cz(k)], { largura: arred(m - 0.04), profundidade: arred(m - 0.04), espessura: 0.05 }, 0, cor, extra);
        for (const [di, dk, giro] of [[1, 0, 90], [-1, 0, 90], [0, 1, 0], [0, -1, 0]]) {
          if (tem(i + di, k + dk, n)) continue; // dá para o módulo vizinho: aberto
          if (n === niveis && i === nx - 1 && k === kSaida && di === 1) continue; // a boca da saída
          const px = cx(i) + di * m / 2, pz = cz(k) + dk * m / 2;
          const frente = dk === 1 && k === nz - 1;
          const sorteio = sorte();
          if (frente && n <= 2 && sorteio < 0.4) {
            P.por("janela", [px, n * L, pz], { largura: arred(m - 0.06), altura: arred(Math.min(0.9, L)), espessura: 0.03 }, giro);
            janelas++;
          } else if (!frente && n === b[i][k] && sorteio < 0.3) {
            P.por("abaco", [px, n * L, pz], { largura: arred(m - 0.06), altura: arred(Math.min(0.9, L)) }, giro);
            abacos++;
          } else {
            P.por("rede", [px, n * L, pz], { largura: arred(m - 0.06), altura: 1.0 }, giro, pal.apoio, { cor2: pal.estrutura });
            redes++;
          }
        }
      }
    }
  }
  const protecao = [contar(redes, "rede de 1,0 m", "redes de 1,0 m"), contar(janelas, "painel com janela", "painéis com janela"), contar(abacos, "painel ábaco", "painéis ábaco")].filter(Boolean);
  regras.push(`Proteção em todo lado de nível elevado que não dá para outro módulo: ${protecao.join(", ").replace(/, ([^,]*)$/, " e $1")}.`);
  if (bicolores) regras.push(`${contar(bicolores, "piso", "pisos")} de duas cores na diagonal (o colorido dos brinquedões).`);

  // a saída: tobogã espiral do nível mais alto, para fora, com a boca de frente para a torre
  const xBorda = x0 + nx * m;
  if (espiral) {
    const lado = cz(kSaida) > 0 || nz === 1 ? 1 : -1;
    const fechado = estilo === "selva" ? 0 : sorte() < 0.65 ? 1 : 0;
    const voltas = Math.max(1, Math.round((topo / 1.9) * 4) / 4);
    P.por("toboga", [arred(xBorda + R + 0.35), 0, arred(cz(kSaida) - lado * R)],
      { altura: arred(topo), raio: R, voltas, fechado, espelhado: lado < 0 ? 1 : 0 });
    regras.push(`Tobogã espiral ${fechado ? "de tubo fechado" : "aberto (calha)"} saindo do nível de ${m2(topo)} m, ${m2(voltas)} volta${voltas > 1 ? "s" : ""}, com a área de chegada livre.`);
  } else {
    const comp = Math.min(saida - 0.3, Math.max(1.6, topo * 1.9));
    const fechado = sorte() < 0.4 ? 1 : 0;
    P.por("escorregador", [xBorda + comp / 2, 0, cz(kSaida)], { comprimento: arred(comp), altura: arred(topo), largura: 0.6, fechado });
    regras.push(`Escorregador ${fechado ? "de tubo " : ""}de ${m2(comp)} m saindo do nível de ${m2(topo)} m, para fora da estrutura.`);
  }
  // a subida: escadinha de espuma nos baixinhos, escada nos altos
  let iEscada = 0;
  while (iEscada < nx - 1 && !tem(iEscada, nz - 1, 1)) iEscada++;
  if (tem(iEscada, nz - 1, 1)) {
    if (L <= 0.85) {
      const n = 3;
      P.por("degraus_espuma", [cx(iEscada), 0, arred(z0 + nz * m + n * 0.15 + 0.02)], { largura: arred(Math.min(0.8, m - 0.2)), altura: arred(L), degraus: n }, 90);
      regras.push("Subida por degraus de espuma (os pequenos sobem engatinhando).");
    } else {
      P.por("escada", [cx(iEscada), 0, arred(z0 + nz * m + L * 0.375)], { altura: L, largura: 0.6, degraus: 4 }, -90);
    }
  }
  // túnel de rede entre dois módulos do mesmo nível
  const nTunel = Math.min(niveis, 2);
  for (let i = 0; i < nx - 1; i++) {
    const k = Math.floor(sorte() * nz);
    if (tem(i, k, nTunel) && tem(i + 1, k, nTunel)) {
      P.por("tunel_rede", [x0 + (i + 1) * m, nTunel * L, cz(k)], { comprimento: arred(m * 0.9), diametro: 0.62 });
      break;
    }
  }
  // rolos entre dois pisos (de passar no meio) e bolas penduradas no alto
  const usados = new Set();
  if (niveis >= 2) {
    for (let tentativa = 0; tentativa < 8; tentativa++) {
      const i = Math.floor(sorte() * nx), k = Math.floor(sorte() * nz);
      if (usados.has(i + "," + k) || !tem(i, k, 1) || !tem(i, k, 2)) continue;
      P.por("rolos", [cx(i), L, cz(k)], { altura: arred(L - 0.07), largura: arred(m * 0.85), quantidade: m >= 1.2 ? 4 : 3 }, sorte() < 0.5 ? 0 : 90);
      usados.add(i + "," + k);
      break;
    }
  }
  for (let tentativa = 0; tentativa < 8; tentativa++) {
    const i = Math.floor(sorte() * nx), k = Math.floor(sorte() * nz);
    if (usados.has(i + "," + k) || t[i][k] < 1) continue;
    P.por("pendulos", [cx(i), t[i][k] * L, cz(k)], { largura: arred(m * 0.85), altura: 0.95, quantidade: 3 }, sorte() < 0.5 ? 0 : 90);
    usados.add(i + "," + k);
    break;
  }
  // a piscina de bolinhas: debaixo da estrutura (ou redonda, na frente, no tema selva)
  if (redonda) {
    const r = Math.min(1.4, (D - nz * m) / 2 - 0.25, W * 0.18);
    P.por("piscina_redonda", [iEscada === nx - 1 ? cx(0) : cx(nx - 1), 0, arred(z0 + nz * m + r + 0.25)], { diametro: arred(r * 2), altura: 0.5 }, 0, pal.madeira);
    regras.push("Piscina redonda de bolinhas na frente, com borda de madeira.");
  } else {
    P.por("piscina", [cx(piscinaI), 0, cz(piscinaK)], { largura: arred(m - 0.08), profundidade: arred(m - 0.08), altura: 0.5 });
    if (piscinaDebaixo) regras.push("Piscina de bolinhas no chão, debaixo do 2º nível.");
  }
  // a colmeia do lado de fora, com a escadinha de espuma até o primeiro hexágono
  if (colmeia) {
    const kc = nz - 1;
    P.por("colmeia", [arred(x0 - colmeia / 2), 0, cz(kc)], { largura: 0.9, altura: arred(Math.min(topo + 0.1, 3 * 0.78 + 0.05)), profundidade: arred(Math.min(0.8, m - 0.2)) });
    if (D / 2 - (cz(kc) + 0.4) > 0.7) P.por("degraus_espuma", [arred(x0 - colmeia / 2), 0, arred(cz(kc) + 0.4 + 0.3)], { largura: 0.7, altura: 0.4, degraus: 2 }, 90);
    regras.push("Colmeia de hexágonos empilhados do lado, com degraus de espuma na entrada.");
  }
  // o teto das torres mais altas, se o pé-direito deixa: em arco (selva) ou pirâmide
  const sobra = H - (topo + 1.0);
  if (sobra >= 0.4) {
    const arco = estilo === "selva" || sorte() < 0.4;
    for (let k = 0; k < nz; k++) {
      if (t[nx - 1][k] !== niveis) continue;
      if (arco) P.por("teto_arco", [cx(nx - 1), topo + 1.0, cz(k)], { largura: m, profundidade: m, altura: arred(Math.min(0.55, sobra)) }, 0, pal.estrutura);
      else P.por("telhado", [cx(nx - 1), topo + 1.0, cz(k)], { largura: m, profundidade: m, altura: arred(Math.min(0.7, sobra)) });
    }
    regras.push(arco ? "Teto em arco nas torres mais altas." : "Telhado nas torres mais altas (o pé-direito deixa).");
  }
  // neon: a fita de LED no alto de cada lado de fora
  if (estilo === "neon") {
    let leds = 0;
    for (let i = 0; i < nx; i++) {
      for (let k = 0; k < nz; k++) {
        if (t[i][k] < 1) continue;
        const y = t[i][k] * L + 1.0 - 0.02;
        for (const [di, dk, giro] of [[1, 0, 90], [-1, 0, 90], [0, 1, 0], [0, -1, 0]]) {
          if (alto(i + di, k + dk) >= t[i][k]) continue;
          P.por("led", [arred(cx(i) + di * m / 2), arred(y), arred(cz(k) + dk * m / 2)], { comprimento: arred(m) }, giro, pal.led);
          leds++;
        }
      }
    }
    regras.push(`${leds} fitas de LED contornando o alto da estrutura (o tema neon).`);
  }
  return regras;
}

/* ---------------------------------------------------------------- os portes (as áreas pelo tamanho) */
/**
 * O que cada área leva conforme o tamanho -- os mesmos números de core/projeto3d.py
 * (a página do cliente mostra só os portes que cabem no espaço dele).
 *   trampolim park: compacto (camas e espuma), médio (+ pista de enterrada), grande (+ trampolim
 *     de parede, parede de escalada sobre a espuma e quadra de queimada);
 *   espaço esportivo kids: compacto (a quadra com escalada e camas), médio (a quadra + um
 *     trampolim park), grande (quadras de futebol e de basquete + trampolim park + circuito kids)
 *     -- como o Espaço Esportivo Modelo 1;
 *   área baby: compacta, média e grande (mais brinquedos baixos a cada porte).
 */
export const PORTES = {
  trampolim: [
    { chave: "compacto", min: [5.5, 5.5], area: 30, lado: 5.5, componentes: ["camas", "espuma", "parede_inclinada"] },
    { chave: "medio", min: [9, 7], area: 50, lado: 5, componentes: ["camas", "espuma", "enterrada", "parede_inclinada", "queimada"] },
    { chave: "grande", min: [14, 10], area: 120, lado: 8, componentes: ["camas", "espuma", "enterrada", "parede_inclinada", "escalada", "queimada"] },
  ],
  esportivo: [
    { chave: "compacto", min: [7, 5], area: 35, lado: 5, componentes: ["quadra", "escalada"] },
    { chave: "medio", min: [16, 10], area: 140, lado: 9, componentes: ["quadra", "trampolim_park", "escalada"] },
    { chave: "grande", min: [26, 16], area: 380, lado: 14, componentes: ["quadra_futebol", "quadra_basquete", "trampolim_park", "escalada", "circuito_kids"] },
  ],
  baby: [
    { chave: "compacto", min: [3, 3], area: 9, lado: 3, componentes: ["piscina", "escorregador", "blocos"] },
    { chave: "medio", min: [5, 4], area: 18, lado: 3.6, componentes: ["piscina", "escorregador", "blocos", "tunel", "paineis", "casinha"] },
    { chave: "grande", min: [7, 5], area: 32, lado: 4.4, componentes: ["piscina", "escorregador", "blocos", "tunel", "paineis", "casinha", "pendulos", "rampa", "torrinha"] },
  ],
  ninja: [
    { chave: "compacto", min: [7, 2.5], area: 17, lado: 2.5, componentes: ["degraus", "trave", "rolos", "argolas"] },
    { chave: "medio", min: [12, 4.5], area: 50, lado: 4.2, componentes: ["degraus", "trave", "rolos", "argolas", "macaco", "corda", "parede_curva"] },
    { chave: "grande", min: [18, 7], area: 120, lado: 6.5, componentes: ["degraus", "trave", "rolos", "argolas", "macaco", "corda", "parede_curva", "escalada"] },
  ],
};
/**
 * O porte cabe em W × D: o retângulo mínimo entra (de qualquer jeito) OU a área tem os m² e o lado
 * menor que ele pede -- o que entra dentro, quem decide é a geometria de cada montador.
 */
export function porteCabe(p, W, D) {
  const ret = Math.max(W, D) >= Math.max(...p.min) - 1e-6 && Math.min(W, D) >= Math.min(...p.min) - 1e-6;
  const porArea = p.area && W * D >= p.area - 1e-6 && Math.min(W, D) >= (p.lado || 0) - 1e-6;
  return ret || Boolean(porArea);
}
/** O maior porte da área que cabe em W × D (ou o menor, se nem ele cabe). */
export function porteQueCabe(tipo, W, D) {
  const lista = PORTES[tipo] || [];
  let melhor = lista[0] || null;
  for (const p of lista) if (porteCabe(p, W, D)) melhor = p;
  return melhor;
}
/** O porte pedido (ou o que cabe) e os componentes dele, menos os que o cliente tirou (`opcoes.sem`). */
function componentesDe(tipo, W, D, op) {
  const lista = PORTES[tipo] || [];
  const pedido = lista.find((p) => p.chave === op.porte && porteCabe(p, W, D));
  const porte = pedido || porteQueCabe(tipo, W, D);
  const sem = new Set(op.sem || []);
  return { porte: porte ? porte.chave : "", tem: new Set((porte ? porte.componentes : []).filter((c) => !sem.has(c))) };
}
/** As peças de uma parte do projeto, postas num retângulo com o meio em (cx, cz) e, se `girar`, giradas 90°. */
function regiao(P, cx, cz, girar = false) {
  return {
    paleta: P.paleta,
    por(tipo, p, d, r = 0, cor, extra) {
      const [x, y, z] = p;
      const q = girar ? [z, y, -x] : [x, y, z];
      P.por(tipo, [q[0] + cx, q[1], q[2] + cz], d, r + (girar ? 90 : 0), cor, extra);
    },
  };
}

/* ---------------------------------------------------------------- espaço esportivo kids */
/** Uma quadra com a tela em volta: de futebol (traves), de basquete (tabelas) ou multiuso (as duas). */
function quadraCom(P, qx, qz, qL, qP, H, tipo) {
  P.por("quadra", [qx, 0, qz], { largura: arred(qL), profundidade: arred(qP) });
  const textos = [];
  if (tipo !== "basquete") {
    const golL = qL >= 14 ? 3 : 2.4, golA = qL >= 14 ? 2 : 1.6;
    // a trave tem 0,8 m de fundo: o meio dela fica 0,45 m para dentro da linha de fundo
    P.por("gol", [qx - qL / 2 + 0.45, 0, qz], { largura: golL, altura: golA }, 90);
    P.por("gol", [qx + qL / 2 - 0.45, 0, qz], { largura: golL, altura: golA }, -90);
    textos.push(`traves de ${m2(golL)} m`);
  }
  if (tipo !== "futebol") {
    const aro = H >= 3.6 ? 2.6 : 2.3;
    if (tipo === "basquete") {
      P.por("tabela", [qx - qL / 2 + 0.7, 0, qz], { altura: aro }, 90);
      P.por("tabela", [qx + qL / 2 - 0.7, 0, qz], { altura: aro }, -90);
    } else {
      P.por("tabela", [qx - qL / 2 + 0.7, 0, qz - qP / 2 + 0.6], { altura: aro }, 90);
      P.por("tabela", [qx + qL / 2 - 0.7, 0, qz + qP / 2 - 0.6], { altura: aro }, -90);
    }
    textos.push(`tabelas com aro a ${m2(aro)} m (altura de criança)`);
  }
  const telaA = arred(Math.min(3, H - 0.4));
  P.por("cerca", [qx, 0, qz - qP / 2], { comprimento: arred(qL), altura: telaA });
  P.por("cerca", [qx, 0, qz + qP / 2], { comprimento: arred(qL), altura: telaA });
  P.por("cerca", [qx - qL / 2, 0, qz], { comprimento: arred(qP), altura: telaA }, 90);
  P.por("cerca", [qx + qL / 2, 0, qz], { comprimento: arred(qP), altura: telaA }, 90);
  const nome = tipo === "futebol" ? "Quadra de futebol" : tipo === "basquete" ? "Quadra de basquete" : "Quadra multiuso";
  return `${nome} de ${m2(qL)} × ${m2(qP)} m com ${textos.join(" e ")}, e tela de proteção.`;
}

/** O circuito kids: piscina de bolinhas com a torrezinha e o escorregador caindo nela. */
function circuitoKids(P, cx, cz, L, Pp) {
  const pis = Math.min(3, L - 1.4, Pp);
  P.por("piscina", [cx + (L - pis) / 2, 0, cz], { largura: arred(pis), profundidade: arred(pis), altura: 0.5 });
  const tx = cx - L / 2 + 0.7;
  P.por("plataforma", [tx, 1.5, cz], { largura: 1.2, profundidade: 1.2, espessura: 0.06 });
  for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) P.por("coluna", [tx + dx * 0.55, 0, cz + dz * 0.55], { altura: 2.5, diametro: 0.08 });
  P.por("telhado", [tx, 2.5, cz], { largura: 1.3, profundidade: 1.3, altura: 0.6 });
  P.por("escada", [tx, 0, cz + 1.0], { altura: 1.5, largura: 0.6, degraus: 5 }, -90);
  const comp = Math.max(1.2, cx + (L - pis) / 2 - (tx + 0.6));
  P.por("escorregador", [tx + 0.6 + comp / 2, 0, cz], { comprimento: arred(comp), altura: 1.5, largura: 0.6 });
  return `Circuito kids: torrezinha de 1,50 m com escorregador caindo na piscina de bolinhas de ${m2(pis)} × ${m2(pis)} m.`;
}

function esportivo(P, W, D, H, sorte, op) {
  const { porte, tem } = componentesDe("esportivo", W, D, op);
  const regras = [];
  if (porte === "compacto" || !tem.has("trampolim_park")) {
    // a quadra multiuso, e na faixa que sobra a escalada com o colchão e as camas
    const faixa = W >= 12 && tem.has("escalada") ? Math.min(5, W * 0.28) : 0;
    const qL = Math.max(6, W - faixa - 0.6), qP = Math.max(4, D - 0.6);
    const qx = -W / 2 + 0.3 + qL / 2;
    regras.push(quadraCom(P, qx, 0, qL, qP, H, tem.has("quadra_futebol") && !tem.has("quadra_basquete") ? "futebol" : "multi"));
    if (faixa) {
      const fx = W / 2 - faixa / 2;
      const esc = Math.min(H - 0.5, 4);
      P.por("escalada", [fx, 0, -D / 2 + 0.2], { largura: arred(Math.min(faixa - 0.4, 3)), altura: arred(esc) });
      P.por("colchao", [fx, 0, -D / 2 + 1.2], { largura: arred(Math.min(faixa - 0.4, 3)), profundidade: 1.6, espessura: 0.3 });
      const camas = Math.max(1, Math.min(3, Math.floor((D - 3) / 2.6)));
      for (let i = 0; i < camas; i++) {
        P.por("cama", [fx, 0, -D / 2 + 3.3 + i * 2.6], { largura: arred(Math.min(faixa - 0.6, 2.4)), profundidade: 2.3, altura: 0.6 });
      }
      regras.push(`Faixa de ${m2(faixa)} m: parede de escalada de ${m2(esc)} m com colchão de queda e ${camas} cama${camas > 1 ? "s" : ""} elástica${camas > 1 ? "s" : ""}.`);
    }
    return regras;
  }
  // como o Espaço Esportivo Modelo 1: as quadras de um lado, o trampolim park do outro
  const parkW = Math.max(9, Math.min(W - 7, W * (porte === "grande" ? 0.5 : 0.46)));
  const quadrasW = W - parkW;
  const qx = -W / 2 + quadrasW / 2;
  if (porte === "grande" && D >= 16 && tem.has("quadra_futebol") && tem.has("quadra_basquete")) {
    const qP = (D - 0.9) / 2;
    regras.push(quadraCom(P, qx, -D / 2 + 0.3 + qP / 2, quadrasW - 0.6, qP, H, "futebol"));
    regras.push(quadraCom(P, qx, D / 2 - 0.3 - qP / 2, quadrasW - 0.6, qP, H, "basquete"));
  } else {
    const tipo = tem.has("quadra_futebol") && !tem.has("quadra_basquete") ? "futebol" : tem.has("quadra_basquete") && !tem.has("quadra_futebol") ? "basquete" : "multi";
    regras.push(quadraCom(P, qx, 0, quadrasW - 0.6, D - 0.6, H, tipo));
  }
  // o circuito kids na frente do park (o lado da entrada)
  let parkD = D, parkZ = 0;
  if (tem.has("circuito_kids") && D >= 13) {
    const cD = 3.6;
    regras.push(circuitoKids(P, W / 2 - parkW / 2, D / 2 - cD / 2, Math.min(parkW - 0.6, 7), cD - 0.4));
    parkD = D - cD;
    parkZ = -cD / 2;
  }
  // o trampolim park, montado no pedaço dele (com o lado maior no x do gerador)
  const girar = parkD > parkW;
  const pw = girar ? parkD : parkW, pd = girar ? parkW : parkD;
  const comps = new Set(porte === "grande" ? PORTES.trampolim[2].componentes : PORTES.trampolim[1].componentes);
  if (!tem.has("escalada")) comps.delete("escalada");
  regras.push(...trampolimPark(regiao(P, W / 2 - parkW / 2, parkZ, girar), pw, pd, H, sorte, comps, porte === "grande" ? 4 : 2));
  return regras;
}

/* ---------------------------------------------------------------- área ninja */
/**
 * A área ninja: o circuito em RAIAS EM ZIGUE-ZAGUE que enchem a área (uma raia na compacta, duas na
 * média, até cinco na grande), cada uma com os obstáculos em fila sobre o piso macio -- os suspensos
 * (argolas, barra de macaco, corda) com colchão embaixo --, a largada com a escadinha na frente
 * (o lado da entrada) e a chegada na parede curva. Na grande, com pé-direito de 3,50 m, a parede de
 * escalada no fundo, com o colchão de queda. Área maior, mais raias e mais obstáculos (repetem na
 * ordem sorteada quando a lista acaba).
 */
function ninja(P, W, D, H, sorte, op) {
  const { porte, tem } = componentesDe("ninja", W, D, op);
  const regras = [];
  const alto = arred(Math.min(2.3, H - 0.6));
  P.por("piso_eva", [0, 0, 0], { largura: arred(W - 0.2), profundidade: arred(D - 0.2) }, 0, P.paleta.chao, { cor2: P.paleta.chao2 });
  // 1. o fundo: a parede de escalada (e, do lado, a parede curva da chegada)
  let zTopo = -D / 2 + 0.3;
  let curvaNoFundo = false;
  if (tem.has("escalada") && H >= 3.5 && D >= 6) {
    const ew = arred(Math.min(W - 1.2, Math.max(3, W * 0.4), 7)), ea = arred(Math.min(H - 0.5, 4));
    const ex = W / 2 - 0.6 - ew / 2;
    P.por("escalada", [ex, 0, -D / 2 + 0.15], { largura: ew, altura: ea });
    P.por("colchao", [ex, 0, -D / 2 + 1.0], { largura: ew, profundidade: 1.5, espessura: 0.3 });
    regras.push(`Parede de escalada de ${m2(ew)} m de largura e ${m2(ea)} m de altura no fundo, com colchão de queda.`);
    if (tem.has("parede_curva") && H >= 3 && W - ew - 1.2 >= 2.6) {
      P.por("parede_curva", [arred(-W / 2 + 0.6 + 1.1), 0, arred(-D / 2 + 0.9)], { largura: 2.0, altura: arred(Math.min(3, H - 0.6)) }, 0);
      curvaNoFundo = true;
      regras.push("A parede curva da chegada no fundo, ao lado da escalada.");
    }
    zTopo = -D / 2 + 1.9;
  }
  // 2. as raias: da frente (a largada, perto da entrada) para o fundo, uma indo e a outra voltando
  const zFrente = D / 2 - 0.6; // a fila da largada, na frente
  const passoRaia = 1.9;
  const teto = porte === "compacto" ? 1 : porte === "medio" ? 2 : 5;
  const n = Math.max(1, Math.min(teto, Math.floor((zFrente - zTopo) / passoRaia)));
  const passo = (zFrente - zTopo) / n;
  const raias = Array.from({ length: n }, (_, k) => arred(zFrente - passo * (k + 0.5)));
  const lista = [
    ["degraus", 3.5, { comprimento: 3.2, largura: 1.2 }, false],
    ["trave", 2.8, { comprimento: 2.5, altura: 0.45 }, false],
    ["rolos", 2.0, { altura: 1.0, largura: 1.6, quantidade: 4 }, false],
    ["argolas", 3.2, { comprimento: 3.0, altura: alto, quantidade: 4 }, true],
    ["macaco", 3.2, { comprimento: 3.0, altura: alto, largura: 0.6 }, true],
    ["corda", 1.8, { altura: arred(Math.min(3, H - 0.4)) }, true],
  ].filter(([tipo]) => tem.has(tipo));
  // o túnel de rastejar entra como respiro nas raias compridas
  if (W * n >= 24) lista.push(["tunel", 1.8, { comprimento: 1.5, diametro: 0.7 }, false]);
  for (let i = lista.length - 1; i > 0; i--) {
    const j = Math.floor(sorte() * (i + 1));
    [lista[i], lista[j]] = [lista[j], lista[i]];
  }
  const curvaNaRaia = tem.has("parede_curva") && H >= 3 && !curvaNoFundo;
  const usados = {};
  let total = 0, proximo = 0;
  raias.forEach((zc, k) => {
    const sentido = k % 2 === 0 ? 1 : -1; // a primeira vai para a direita
    let x = -W / 2 + 0.5;
    let fim = W / 2 - 0.5;
    if (k === 0) {
      // a largada: a escadinha de espuma
      P.por("degraus_espuma", [sentido > 0 ? arred(-W / 2 + 0.6) : arred(W / 2 - 0.6), 0, zc], { largura: 1.2, altura: 0.6, degraus: 2 }, sentido > 0 ? 90 : -90);
      x += 1.2;
    }
    if (k === n - 1 && curvaNaRaia) fim -= 2.6;
    let tentativas = 0;
    while (lista.length && tentativas < lista.length) {
      const [tipo, comp, d, colchao] = lista[proximo % lista.length];
      if (x + comp > fim + 1e-6) { proximo++; tentativas++; continue; } // não cabe: tenta o seguinte
      tentativas = 0;
      const meio = x + comp / 2;
      const xm = arred(sentido > 0 ? meio : -meio);
      if (colchao) P.por("colchao", [xm, 0, zc], { largura: arred(comp - 0.1), profundidade: 1.6, espessura: 0.2 });
      P.por(tipo, [xm, tipo === "rolos" ? 0.2 : 0, zc], d, tipo === "tunel" ? 90 : 0);
      usados[tipo] = (usados[tipo] || 0) + 1;
      total++;
      proximo++;
      x += comp + 0.4;
    }
    if (k === n - 1 && curvaNaRaia) {
      const xp = sentido > 0 ? W / 2 - 0.5 - 1.3 : -(W / 2 - 0.5 - 1.3);
      P.por("parede_curva", [arred(xp), 0, zc], { largura: 2.0, altura: arred(Math.min(3, H - 0.6)) }, sentido > 0 ? -90 : 90);
      regras.push("A parede curva fecha o circuito, de frente para quem vem correndo.");
    }
  });
  const nomes = {
    degraus: ["conjunto de degraus", "conjuntos de degraus"], trave: ["trave", "traves"], rolos: ["conjunto de rolos", "conjuntos de rolos"],
    argolas: ["conjunto de argolas", "conjuntos de argolas"], macaco: ["barra de macaco", "barras de macaco"], corda: ["corda", "cordas"], tunel: ["túnel", "túneis"],
  };
  const tipos = Object.entries(usados).map(([t, q]) => `${q} ${nomes[t][q > 1 ? 1 : 0]}`);
  regras.unshift(`${n === 1 ? "Uma raia" : `${n} raias em zigue-zague`} com ${total} obstáculos (${tipos.join(", ")}) sobre piso macio; os suspensos a ${m2(alto)} m, com colchão embaixo.`);
  regras.push("A largada na frente (a escadinha de espuma), do lado da entrada.");
  return regras;
}

/* ---------------------------------------------------------------- trampolim park */
/**
 * O trampolim park de verdade (o que fica dentro do Espaço Esportivo Modelo 1): as camas em grade
 * com o estofado colorido, a piscina de espuma no fim (com as camas de lançamento antes e, se o
 * pé-direito deixa, a parede de escalada por cima dela), a pista de enterrada (raias de três camas
 * com a tabela no fim), o trampolim de parede no fundo, a quadra de queimada, a tela em volta e a
 * escadinha na entrada. `tem`: os componentes; `raias`: quantas raias de enterrada no máximo.
 */
function trampolimPark(P, W, D, H, sorte, tem, raias = 2) {
  const regras = [];
  const m = 0.3, x0 = -W / 2 + m, x1 = W / 2 - m, z0 = -D / 2 + m, z1 = D / 2 - m;
  const alto = H >= 4.5;
  let nCamas = 0;
  const cores = P.paleta.varias;
  const cama = (x, z, l, p) => {
    P.por("cama", [arred(x), 0, arred(z)], { largura: arred(l - 0.04), profundidade: arred(p - 0.04), altura: 0.9 }, 0, cores[nCamas % cores.length]);
    nCamas++;
  };
  const grade = (xa, xb, za, zb, lado = 2.4) => {
    if (xb - xa < 1.4 || zb - za < 1.4) return;
    const nx = Math.max(1, Math.round((xb - xa) / lado)), nz = Math.max(1, Math.round((zb - za) / lado));
    const lx = (xb - xa) / nx, lz = (zb - za) / nz;
    for (let i = 0; i < nx; i++) for (let k = 0; k < nz; k++) cama(xa + (i + 0.5) * lx, za + (k + 0.5) * lz, lx, lz);
  };
  let xr = x1;
  // 1. a piscina de espuma no fim (direita), com a escalada por cima dela
  if (tem.has("espuma") && W >= 6.5) {
    const pw = Math.min(4.5, Math.max(2.0, W * 0.22));
    const pd = Math.min(z1 - z0, 8);
    P.por("espuma", [x1 - pw / 2, 0, z0 + pd / 2], { largura: arred(pw), profundidade: arred(pd), altura: 0.9 });
    regras.push(`Piscina de espuma de ${m2(pw)} × ${m2(pd)} m no fim, com as camas de lançamento antes dela.`);
    if (tem.has("escalada")) {
      if (alto) {
        const ew = Math.min(pd - 0.4, 4), ea = Math.min(H - 0.6, 4.5);
        P.por("escalada", [x1 + 0.1, 0, z0 + pd / 2], { largura: arred(ew), altura: arred(ea) }, -90);
        regras.push(`Parede de escalada de ${m2(ea)} m sobre a piscina de espuma (a queda é na espuma).`);
      } else {
        regras.push("A parede de escalada pede pé-direito de 4,50 m: ficou de fora.");
      }
    }
    if (pd < z1 - z0 - 1.4) grade(x1 - pw, x1, z0 + pd, z1);
    xr = x1 - pw;
  }
  // 2. a pista de enterrada (esquerda): raias de camas em linha com a tabela no fim
  let xl = x0;
  if (tem.has("enterrada") && xr - x0 >= 6) {
    const raiaP = 1.6, cl = 1.5;
    const n = Math.max(1, Math.min(raias, Math.floor((z1 - z0) / raiaP)));
    const camas = xr - x0 - 0.9 >= 3 * cl + 2.4 ? 3 : 2;
    for (let i = 0; i < n; i++) {
      const zc = z0 + raiaP * (i + 0.5);
      P.por("tabela", [x0 + 0.35, 0, zc], { altura: 2.9 }, 90);
      for (let k = 0; k < camas; k++) cama(x0 + 0.9 + cl * (k + 0.5), zc, cl, raiaP);
    }
    xl = x0 + 0.9 + camas * cl;
    // na frente das raias, mais camas livres
    grade(x0, xl, z0 + n * raiaP, z1);
    regras.push(`Pista de enterrada: ${n} raia${n > 1 ? "s" : ""} de ${camas} camas em linha com a tabela (aro a 2,90 m) no fim.`);
  }
  // 3. o trampolim de parede no fundo do meio
  let zb = z0;
  if (tem.has("parede_inclinada")) {
    if (alto && xr - xl >= 2) {
      const n = Math.max(1, Math.floor((xr - xl) / 2));
      const lw = (xr - xl) / n;
      for (let i = 0; i < n; i++) {
        P.por("cama_inclinada", [xl + (i + 0.5) * lw, 0, z0 + 0.8], { largura: arred(lw - 0.05), profundidade: 1.6, altura: 2.6, base: 0.9 }, 0, cores[(i + 2) % cores.length]);
      }
      zb = z0 + 1.6;
      regras.push(`${n} ${n > 1 ? "trampolins" : "trampolim"} de parede (camas inclinadas) no fundo.`);
    } else if (!alto) {
      regras.push("O trampolim de parede pede pé-direito de 4,50 m: ficou de fora.");
    }
  }
  // 4. a quadra de queimada na frente do meio (camas com a tela baixa em volta e a rede no meio)
  let zf = z1;
  if (tem.has("queimada") && xr - xl >= 6 && z1 - zb >= 7) {
    const qP = 4.4, qL = Math.min(xr - xl, 8.8);
    const qx = xl + qL / 2, qz = z1 - qP / 2;
    grade(xl, xl + qL, z1 - qP, z1, 2.2);
    P.por("cerca", [qx, 0.9, qz - qP / 2], { comprimento: arred(qL), altura: 1.2 });
    P.por("cerca", [qx, 0.9, qz], { comprimento: arred(qP), altura: 0.9 }, 90);
    grade(xl + qL, xr, z1 - qP, z1);
    zf = z1 - qP;
    regras.push(`Quadra de queimada de ${m2(qL)} × ${m2(qP)} m (camas com tela baixa e a rede no meio).`);
  }
  // 5. as camas livres no resto
  grade(xl, xr, zb, zf);
  regras.unshift(`${nCamas} camas elásticas com o estofado colorido em volta de cada uma (lona a 0,90 m).`);
  // 6. a tela em volta (com a entrada na frente) e a escadinha da entrada
  const telaA = arred(Math.min(2.2, H - 0.3));
  const vao = 1.4, ex = x0 + Math.min(W * 0.3, 3);
  P.por("cerca", [0, 0, -D / 2 + 0.15], { comprimento: arred(W - 0.3), altura: telaA });
  P.por("cerca", [-W / 2 + 0.15, 0, 0], { comprimento: arred(D - 0.3), altura: telaA }, 90);
  P.por("cerca", [W / 2 - 0.15, 0, 0], { comprimento: arred(D - 0.3), altura: telaA }, 90);
  const esqL = ex - vao / 2 - (-W / 2 + 0.15), dirL = W / 2 - 0.15 - (ex + vao / 2);
  if (esqL > 0.2) P.por("cerca", [-W / 2 + 0.15 + esqL / 2, 0, D / 2 - 0.15], { comprimento: arred(esqL), altura: telaA });
  if (dirL > 0.2) P.por("cerca", [W / 2 - 0.15 - dirL / 2, 0, D / 2 - 0.15], { comprimento: arred(dirL), altura: telaA });
  P.por("degraus_espuma", [ex, 0, D / 2 + 0.2], { largura: 1.2, altura: 0.9, degraus: 3 }, 90);
  regras.push(`Tela de ${m2(telaA)} m em volta, com a entrada na frente e a escadinha de espuma até as camas.`);
  return regras;
}

function trampolim(P, W, D, H, sorte, op) {
  const { porte, tem } = componentesDe("trampolim", W, D, op);
  return trampolimPark(P, W, D, H, sorte, tem, porte === "grande" ? 4 : 2);
}

/* ---------------------------------------------------------------- espaço baby */
/**
 * O espaço baby (0 a 3 anos), tudo baixo e macio: piso de EVA, cerca de 0,60 m com o portal e os
 * painéis ábaco nela; dentro, as ESTAÇÕES -- a piscina rasa com a plataforma de 0,40 m e o
 * escorregador caindo nela, a torrinha com escorregador, a casinha, os blocos de espuma, o túnel,
 * a rampa com degraus, as bolas penduradas -- postas em fileiras do fundo para a frente, com
 * passagem entre elas e a frente livre (a chegada pelo portal). Área grande (o espaço baby como
 * modelo do espaço) ganha mais estações: a piscina redonda, outro canto de blocos, outro túnel...
 */
function baby(P, W, D, H, sorte, op) {
  const { porte, tem } = componentesDe("baby", W, D, op);
  const regras = [];
  P.por("piso_eva", [0, 0, 0], { largura: arred(W - 0.2), profundidade: arred(D - 0.2) }, 0, P.paleta.chao, { cor2: P.paleta.chao2 });
  const c = 0.6;
  P.por("cerca", [0, 0, -D / 2 + 0.15], { comprimento: arred(W - 0.4), altura: c });
  P.por("cerca", [-W / 2 + 0.15, 0, 0], { comprimento: arred(D - 0.4), altura: c }, 90);
  P.por("cerca", [W / 2 - 0.15, 0, 0], { comprimento: arred(D - 0.4), altura: c }, 90);
  const vao = 1.4;
  const ladoFrente = (W - 0.4 - vao) / 2;
  P.por("cerca", [-W / 2 + 0.2 + ladoFrente / 2, 0, D / 2 - 0.15], { comprimento: arred(ladoFrente), altura: c });
  P.por("cerca", [W / 2 - 0.2 - ladoFrente / 2, 0, D / 2 - 0.15], { comprimento: arred(ladoFrente), altura: c });
  P.por("arco", [0, 0, D / 2 - 0.15], { largura: vao, altura: 2.0 });

  // o miolo onde vão as estações (a frente fica livre: a chegada pelo portal)
  const x0 = -W / 2 + 0.45, x1 = W / 2 - 0.45, z0 = -D / 2 + 0.45;
  const z1 = D / 2 - Math.max(0.7, Math.min(1.4, D * 0.22));
  const fundoUtil = z1 - z0, larguraUtil = x1 - x0;
  const cores = P.paleta.varias;
  const pis = arred(Math.max(1.4, Math.min(2.2, larguraUtil * 0.45, fundoUtil)));
  const montar = {
    piscina: (cx, cz, w) => {
      // a piscina rasa à esquerda e, se couber, a plataforma de 0,40 m com o escorregador caindo nela
      const px = cx - w / 2 + pis / 2;
      P.por("piscina", [arred(px), 0, arred(cz)], { largura: pis, profundidade: pis, altura: 0.4 });
      if (w > pis + 1.5) {
        const tx = arred(px + pis / 2 + 0.95), tz = arred(cz - pis / 2 + 0.6);
        P.por("plataforma", [tx, 0.4, tz], { largura: 1.1, profundidade: 1.1, espessura: 0.08 });
        for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) P.por("coluna", [tx + dx * 0.5, 0, tz + dz * 0.5], { altura: 1.0, diametro: 0.06 });
        P.por("escorregador", [arred(tx - 0.55 - 0.45), 0, tz], { comprimento: 0.9, altura: 0.4, largura: 0.5 }, 180);
        P.por("degraus_espuma", [arred(tx + 0.95), 0, tz], { largura: 0.8, altura: 0.4, degraus: 2 }, 180);
        return `piscina rasa de ${m2(pis)} × ${m2(pis)} m com a plataforma de 0,40 m e o escorregador caindo nela`;
      }
      return `piscina rasa de ${m2(pis)} × ${m2(pis)} m`;
    },
    torrinha: (cx, cz) => {
      // a torrinha de 0,60 m, com a escadinha de espuma de um lado e o escorregador do outro
      P.por("plataforma", [arred(cx), 0.6, arred(cz)], { largura: 1.0, profundidade: 1.0, espessura: 0.08 }, 0, cores[1 % cores.length]);
      for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) P.por("coluna", [arred(cx + dx * 0.45), 0, arred(cz + dz * 0.45)], { altura: 1.25, diametro: 0.06 });
      P.por("telhado", [arred(cx), 1.25, arred(cz)], { largura: 1.1, profundidade: 1.1, altura: 0.45 }, 0, cores[3 % cores.length]);
      P.por("degraus_espuma", [arred(cx - 0.95), 0, arred(cz)], { largura: 0.8, altura: 0.6, degraus: 3 });
      P.por("escorregador", [arred(cx + 0.5 + 0.6), 0, arred(cz)], { comprimento: 1.2, altura: 0.6, largura: 0.5 });
      return "torrinha de 0,60 m com escadinha e escorregador";
    },
    casinha: (cx, cz) => { P.por("casinha", [arred(cx), 0, arred(cz)], { largura: 1.2, profundidade: 1.2, altura: 1.4 }, 0, P.paleta.destaque); return "casinha"; },
    blocos: (cx, cz, w, d) => { P.por("blocos_espuma", [arred(cx), 0, arred(cz)], { largura: arred(w - 0.2), profundidade: arred(d - 0.2) }); return "blocos de espuma (cubos, cilindros, meia-lua, cunha e arco)"; },
    tunel: (cx, cz) => { P.por("tunel", [arred(cx), 0, arred(cz)], { comprimento: 1.2, diametro: 0.6 }); return "túnel"; },
    rampa: (cx, cz) => {
      P.por("rampa", [arred(cx + 0.5), 0, arred(cz)], { comprimento: 1.2, altura: 0.35, largura: 0.9 });
      P.por("degraus_espuma", [arred(cx - 0.75), 0, arred(cz)], { largura: 0.9, altura: 0.35, degraus: 2 });
      return "rampa e degraus de espuma";
    },
    pendulos: (cx, cz) => { P.por("pendulos", [arred(cx), 1.3, arred(cz)], { largura: 0.95, altura: 0.9, quantidade: 3 }); return "bolas penduradas"; },
    redonda: (cx, cz) => { P.por("piscina_redonda", [arred(cx), 0, arred(cz)], { diametro: 2.2, altura: 0.4 }); return "piscina redonda de 2,20 m"; },
  };
  // [chave, largura, fundo] na ordem de importância; a área grande repete (a segunda rodada)
  const primeira = [
    ["piscina", tem.has("escorregador") && larguraUtil >= pis + 2.2 ? pis + 2.0 : pis, pis],
    ["torrinha", 2.9, 1.4],
    ["casinha", 1.5, 1.5],
    ["blocos", Math.min(2.2, larguraUtil), Math.min(1.8, fundoUtil)],
    ["rampa", 2.2, 1.1],
    ["tunel", 1.5, 0.9],
    ["pendulos", 1.3, 1.0],
  ].filter(([k]) => (k === "piscina" ? tem.has("piscina") : k === "torrinha" ? tem.has("torrinha") : tem.has(k)));
  const segunda = porte === "grande" ? [["redonda", 2.4, 2.4], ["blocos", 2.2, 1.8], ["tunel", 1.5, 0.9], ["casinha", 1.5, 1.5], ["pendulos", 1.3, 1.0], ["rampa", 2.2, 1.1]] : [];
  const fila = [...primeira];
  // a área bem maior que o porte grande ganha a segunda rodada (e mais, se ainda sobrar muito)
  const rodadas = porte === "grande" ? Math.max(0, Math.floor((W * D) / 40) - 1) : 0;
  for (let r = 0; r < rodadas; r++) fila.push(...segunda.filter(([k]) => k !== "redonda" || r % 2 === 0));
  // fileiras do fundo para a frente, da esquerda para a direita, com passagem entre as estações
  const vaoX = 0.7, vaoZ = 0.8;
  let x = x0, z = z0, alturaFileira = 0;
  const feitos = [];
  const vezes = {};
  for (const [k, w, d] of fila) {
    if (w > larguraUtil + 1e-6) continue;
    if ((vezes[k] || 0) >= (k === "tunel" ? 3 : 2)) continue; // variedade: no máximo duas de cada (três túneis)
    if (x + w > x1 + 1e-6) { x = x0; z += alturaFileira + vaoZ; alturaFileira = 0; }
    if (z + d > z1 + 1e-6) continue; // não cabe nesta fileira nem nas próximas: a seguinte, menor, pode caber
    const texto = montar[k](x + w / 2, z + d / 2, w, d);
    vezes[k] = (vezes[k] || 0) + 1;
    feitos.push(texto);
    x += w + vaoX;
    alturaFileira = Math.max(alturaFileira, d);
  }
  // os painéis ábaco na cerca: um a cada 3 m das laterais
  if (tem.has("paineis")) {
    const n = Math.max(1, Math.floor((D - 1) / 3));
    for (let i = 0; i < n; i++) {
      const zp = arred(-D / 2 + (i + 0.5) * ((D - 1) / n) + 0.3);
      P.por("abaco", [W / 2 - 0.3, 0.05, zp], { largura: 0.9, altura: 0.55 }, -90);
      P.por("abaco", [-W / 2 + 0.3, 0.05, zp], { largura: 0.9, altura: 0.55 }, 90);
    }
    feitos.push(`${n * 2} painéis ábaco na cerca`);
  }
  const contagem = {};
  for (const t of feitos) contagem[t] = (contagem[t] || 0) + 1;
  const lista = Object.entries(contagem).map(([t, q]) => (q > 1 ? `${q}× ${t}` : t));
  regras.push(`${feitos.length} estações baixas e macias: ${lista.join("; ")}.`);
  regras.push("Piso de EVA no espaço todo, cerca de 0,60 m, o portal na entrada e a frente livre para chegar.");
  return regras;
}

const MONTADORES = { brinquedao, esportivo, ninja, trampolim, baby };

/**
 * Monta a ideia: { pecas: [...], resumo: ["12 colunas", ...], regras: [...], titulo }.
 * `medidas`: { largura, profundidade, altura } do espaço (m). `semente`: muda a ideia.
 * `opcoes`: { estilo: "colorido" | "neon" | "selva", aprendido: { modulo, nivel },
 *            porte: "compacto" | "medio" | "grande" (o maior que cabe, se vazio),
 *            sem: [componentes que o cliente tirou] } -- ver PORTES.
 */
export function gerar(tipo, medidas, cor, semente = 1, opcoes = {}) {
  if (!MONTADORES[tipo]) tipo = "brinquedao";
  const montar = MONTADORES[tipo];
  const W = Math.max(2.5, Math.min(60, Number(medidas.largura) || PROJETOS[tipo].medidas.largura));
  const D = Math.max(2, Math.min(40, Number(medidas.profundidade) || PROJETOS[tipo].medidas.profundidade));
  const H = Math.max(2, Math.min(12, Number(medidas.altura) || PROJETOS[tipo].medidas.altura));
  const estilo = ESTILOS[opcoes.estilo] ? opcoes.estilo : "colorido";
  const paleta = paletaDaCor(cor, estilo);
  const P = new Projeto(paleta);
  const regras = montar(P, W, D, H, sorteio(semente * 2654435761), {
    estilo, aprendido: opcoes.aprendido || {}, porte: opcoes.porte || "", sem: opcoes.sem || [],
  });
  const porte = PORTES[tipo] ? componentesDe(tipo, W, D, { porte: opcoes.porte }).porte : "";
  return {
    pecas: P.pecas,
    resumo: resumoDe(P.contagem),
    regras,
    porte,
    titulo: `${PROJETOS[tipo] ? PROJETOS[tipo].nome : "Projeto"} ${m2(W)} × ${m2(D)} m`,
  };
}
