// Monta o Basquete Home Quadrinhos em three.js e exporta um .glb.
//
// O basquete de arcade com os adesivos em quadrinhos. TUDO o que é adesivo sai
// da folha da fábrica (folha-adesivos.webp, a 26567-2): a arte de cada peça
// (adesivos/<peça>.png) e o desenho dela (formas.json: o tamanho em px, nas
// peças recortadas o CONTORNO de verdade e, nas laterais de fora, os FUROS da
// bola vazada), que o recortar_adesivos.py tira da folha. Nada da arte é
// redesenhado: cada imagem vai inteira na sua face.
//
// O GABINETE é o da folha, que é o do Basquete Home do catálogo (a mesma
// família de arte, em azul: ferramentas/categorias/maquinas/basquete-home.webp)
// no tamanho do Basquete Street (2,70 x 1,00 x 2,40 m, o cadastro): as
// laterais de chapa com o contorno da folha (a parte alta atrás, a curva e a
// diagonal, a parte baixa do console), a testeira em cima, o fundo da cesta
// com o placar, o teto interno e o console da frente. Do Basquete Street
// (a foto do catálogo) vêm as peças de máquina de ponto comercial que a folha
// não desenha: o moedeiro na frente, o neon nas bordas, os pés niveladores,
// e a estrutura de tubo preto atrás.
//
// O que a cliente apontou na primeira versão (e que mudou aqui):
//  - a bola grande das laterais de fora é VAZADA: os gomos brancos da folha
//    são furos de verdade na chapa (atravessam a lateral, com a parede de
//    dentro), abertos, sem grade: por eles se vê o lado de dentro;
//  - a PRANCHA (a chapa que devolve a bola) não fica no fundo: é a rampa,
//    inclinada, do pé do fundo da cesta até o console; a bola desce e para
//    na chapa de parada, logo atrás da tampa do console, ao alcance de quem
//    joga (as bolas ficam ali, como na máquina);
//  - nada de "madeiras quadradas": sem a caixa preta em cima do teto, sem os
//    tacos pretos atrás das laterais; as costas são a estrutura de tubo e uma
//    chapa recuada.
//
// A folha é desenhada em ESCALA: a testeira, a frente, a prancha, o fundo e o
// teto têm a mesma largura (182 px = 1,00 m) e a lateral de fora mais a
// testeira (e os pés) dão os 2,70 m.
//
// EM ALTA DEFINIÇÃO (LEIA-ME V10, seção 91; o que as três máquinas de adesivo
// dividem está em ../comum3d.js): os adesivos ampliados 4x com nitidez
// (adesivos-hd/, ../ampliar_adesivos.py), em vinil laminado brilhante (o verniz:
// KHR_materials_clearcoat); as laterais em MDF de 25 mm com a borda arredondada
// (o adesivo do tamanho da face plana); o preto acetinado, o metal cromado, o
// neon e o placar acesos (emissiveStrength). Os nomes dos materiais (e das
// malhas) são os de antes: quem importa no Blender acha cada peça pelo nome.
//
// Coordenadas: as do three.js, em milímetros: x na largura (da esquerda para a
// direita de quem joga), y para cima, z no comprimento (a frente, o jogador,
// em +z). No fim tudo vira metros, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "/vendor/three/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "/vendor/three/BufferGeometryUtils.js";
import * as C from "../comum3d.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const FORMAS = await (await fetch(`formas.json?v=${Date.now()}`)).json();

// uma peça da folha em mm, na escala `s`: o contorno de verdade (ou o retângulo
// da peça), com o canto de baixo à esquerda em (0, 0), o retângulo da imagem
// (o contorno fica 1 px para dentro da arte: no 3D não aparece o branco da
// folha) e os furos (os vazados), no mesmo sistema
function emMm(nome, s) {
  const { px: [w, h], contorno, furos = [] } = FORMAS[nome];
  const mm = ([u, v]) => [u * w * s, (1 - v) * h * s];
  const pts = (contorno || [[0, 0], [1, 0], [1, 1], [0, 1]]).map(mm);
  const a0 = Math.min(...pts.map((p) => p[0]));
  const b0 = Math.min(...pts.map((p) => p[1]));
  const largura = Math.max(...pts.map((p) => p[0])) - a0;
  const altura = Math.max(...pts.map((p) => p[1])) - b0;
  const mover = ([a, b]) => [a - a0, b - b0];
  return {
    pontos: pts.map(mover), ret: [-a0, -b0, w * s - a0, h * s - b0], largura, altura,
    furos: furos.map((f) => f.map(mm).map(mover)),
  };
}
// a altura do contorno numa abscissa: o maior b das arestas que cruzam a
const altoEm = (pontos, a) => {
  let alto = -Infinity;
  for (let i = 0; i < pontos.length; i++) {
    const [a0, b0] = pontos[i];
    const [a1, b1] = pontos[(i + 1) % pontos.length];
    if ((a0 <= a && a <= a1) || (a1 <= a && a <= a0)) alto = Math.max(alto, a1 === a0 ? Math.max(b0, b1) : b0 + ((a - a0) * (b1 - b0)) / (a1 - a0));
  }
  return alto;
};
// Ramer-Douglas-Peucker numa linha aberta (o neon segue o contorno sem os degraus dos pixels)
function simplificar(pontos, tol) {
  if (pontos.length < 3) return pontos;
  const [a, b] = [pontos[0], pontos[pontos.length - 1]];
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const L = Math.hypot(dx, dy) || 1e-9;
  let pior = 0, k = 0;
  for (let i = 1; i < pontos.length - 1; i++) {
    const d = Math.abs(dy * (pontos[i][0] - a[0]) - dx * (pontos[i][1] - a[1])) / L;
    if (d > pior) { pior = d; k = i; }
  }
  if (pior <= tol) return [a, b];
  return simplificar(pontos.slice(0, k + 1), tol).slice(0, -1).concat(simplificar(pontos.slice(k), tol));
}

// ---------- as medidas (mm) ----------
const ALT = 2700; // a altura, no alto da testeira
const PE = 25; // os pés niveladores: a chapa começa 25 mm acima do chão
const XF = 500; // a face de fora (o adesivo): 1,00 m de largura
const D = 2400; // a profundidade (as costas da estrutura até a frente do console)
const ZB = -D / 2; // as costas
const ZF = D / 2; // a frente (o adesivo da Frente)
const ESP = 18; // a chapa (MDF)
const ESP_LAT = 25; // as laterais: MDF de 25 mm (a máquina firme, sem cara de papelão)
const RAIO_LAT = 3; // a borda arredondada das laterais (pequena: os gomos da bola vazada são finos)
const PELE = 1; // o adesivo fica 1 mm fora da madeira
const XM = XF - PELE - ESP_LAT; // 474: a face de dentro das laterais
const XI = XM - PELE; // 473: o adesivo de dentro (a pista tem 946 mm)
const PISTA = 2 * XI;
const TUBO = 40; // o tubo preto da estrutura de trás (40 x 40)
const Z_COSTAS = ZB + TUBO; // a chapa das costas, na frente dos tubos

// a testeira: a frente dela é a largura da máquina (a escala de cima)
const S_T = 2 * XF / emMm("testeira-frente", 1).largura;
const T_FRENTE = emMm("testeira-frente", S_T);
const H_T = T_FRENTE.altura; // ~275
// o hexágono da testeira sai do contorno da frente dela: os lados retos embaixo,
// os chanfros e o teto; a profundidade, do teto da testeira
const T = (() => {
  const p = T_FRENTE.pontos;
  const W = T_FRENTE.largura;
  const lado = Math.max(...p.filter(([a]) => a < 0.012 * W).map(([, b]) => b)); // o alto do lado reto
  const cima = p.filter(([, b]) => b > H_T - 0.04 * H_T).map(([a]) => a); // o teto
  const cx = (Math.min(...cima) + (W - Math.max(...cima))) / 2;
  return { lado, chanfro: [cx, H_T - lado], topo: W - 2 * cx, fundo: FORMAS["testeira-teto"].px[1] * S_T };
})();
const TOPO = ALT - H_T; // o alto das laterais (embaixo da testeira)

// as laterais de fora: o contorno de cada uma, dos pés até a testeira
const S_E = (TOPO - PE) / emMm("lateral-externa-esquerda", 1).altura; // ~5,38 mm por px
const EXT = { esquerda: emMm("lateral-externa-esquerda", S_E), direita: emMm("lateral-externa-direita", S_E) };
const D_E = EXT.esquerda.largura; // ~2280: a lateral de fora vai da frente até 12 cm das costas
const Z_EXT = ZF - D_E; // onde ela começa (o fundo dela)
const ZT0 = Z_EXT; // a testeira, em cima da parte alta da lateral de fora
const ZT1 = Z_EXT + T.fundo;
// o alto da chapa da lateral num z (a de fora; atrás dela, a chapa vai até o alto)
const chapaEm = (z) => (z < Z_EXT + 1 ? TOPO : PE + altoEm(EXT.esquerda.pontos, z - Z_EXT));

// as laterais de dentro: o L entre a placa da frente do console e a chapa das costas
const L_DENTRO = (ZF - PELE - ESP) - (Z_COSTAS + ESP);
const S_I = L_DENTRO / emMm("lateral-interna-esquerda", 1).largura;
const INT = { esquerda: emMm("lateral-interna-esquerda", S_I), direita: emMm("lateral-interna-direita", S_I) };

// as peças da pista, na largura dela
const PRANCHA = emMm("prancha", PISTA / FORMAS.prancha.px[0]);
const FUNDO = emMm("fundo-cesta", PISTA / FORMAS["fundo-cesta"].px[0]);
const TETO_INT = emMm("teto-interno", PISTA / FORMAS["teto-interno"].px[0]);

// a frente do console: a Frente dobra em três faixas (as linhas da folha)
const FRENTE = emMm("frente", 2 * XF / FORMAS.frente.px[0]);
const [D1, D2] = FORMAS.frente.dobras; // de cima: a faixa de cima, a do meio e a de baixo
const FAIXA = { cima: D1 * FRENTE.altura, meio: (D2 - D1) * FRENTE.altura, baixo: (1 - D2) * FRENTE.altura };
// o chanfro da frente, tirado do contorno da lateral de fora (de fora, na esquerda, a frente fica à direita)
const CONSOLE = (() => {
  const p = EXT.esquerda.pontos;
  const quina = altoEm(p, D_E - 1); // o alto da face de pé da frente
  const baixa = altoEm(p, D_E - 400); // o alto da parte baixa
  let recuo = 1;
  while (recuo < 600 && altoEm(p, D_E - recuo) < baixa - 3) recuo += 1;
  const ang = Math.atan2(baixa - quina, recuo); // a inclinação do chanfro
  const zInclinada = ZF - FAIXA.meio * Math.cos(ang); // onde acaba a face inclinada
  const yCima = PE + FAIXA.baixo + FAIXA.meio * Math.sin(ang); // a altura da tampa (a faixa de cima, deitada)
  // onde a parte baixa da lateral acaba (começa a diagonal): o fim da boca das bolas
  let fim = 400;
  while (fim < D_E && altoEm(p, D_E - fim) < baixa + 3) fim += 1;
  return { ang, baixa: PE + baixa, zInclinada, yCima, zFimCima: zInclinada - FAIXA.cima, zBoca: ZF - fim };
})();
// as paredes de dentro: a parte baixa delas encontra a parte baixa da lateral de fora
const PISO_L = CONSOLE.baixa - altoEm(INT.esquerda.pontos, 0.15 * INT.esquerda.largura); // de dentro, na esquerda, a frente é a = 0
const TETO = TOPO - ESP - PELE; // o adesivo do teto interno (a placa do teto encosta embaixo da testeira)
const Z_FUNDO = Z_COSTAS + ESP + PELE; // o adesivo do fundo da cesta
const Y_FUNDO = TETO - FUNDO.altura; // o pé do fundo da cesta
// a PRANCHA: a rampa que devolve a bola. Atrás, ela encosta no fundo logo
// abaixo do BOOM! (as nuvens dele vão até 72% da altura do fundo); na frente,
// passa embaixo da tampa do console, que segura a bola: a 13 cm da tampa, a
// bola (24 cm) não passa e para na chapa de parada, ao alcance de quem joga
const BOLA = 105; // o raio das bolas
const RAMPA = (() => {
  const yAtras = TETO - 0.74 * FUNDO.altura;
  const yParada = CONSOLE.yCima - ESP - PELE - 130;
  const ang = Math.atan2(yAtras - yParada, CONSOLE.zFimCima - Z_FUNDO);
  const y = (z) => yParada + (CONSOLE.zFimCima - z) * Math.tan(ang); // a altura da rampa num z
  const zFrente = Z_FUNDO + PRANCHA.altura * Math.cos(ang); // a ponta da frente da prancha (embaixo da tampa)
  return { ang, yAtras, yParada, y, zFrente };
})();
// a cesta: embaixo do placar (a janela branca do fundo, de 11% a 19% da altura, de cima)
const JANELA = { u0: 0.648, u1: 0.868, v0: 0.109, v1: 0.193 }; // a janela do placar no fundo-cesta.png
const ARO = { y: TETO - 0.27 * FUNDO.altura, raio: 150 };
// o botão Start: a marca tracejada na faixa de cima da Frente (frações da imagem, de cima)
const START = { u0: 0.79, u1: 0.97, v0: 0.044, v1: 0.1 };
// a porta do moedeiro: na face de pé, à esquerda do POW! (onde a arte é só faixa colorida)
const PORTA = { x0: -XF + 30, x1: -XF + 230, y0: PE + 110, y1: PE + 490 };
// a resolução máxima de cada adesivo dentro do .glb (o lado maior, em px): a peça
// HD inteira (4x a folha) até 2048 px; as pequenas da testeira, até 512
const RESOLUCAO = {
  "lateral-externa-esquerda": 2048, "lateral-externa-direita": 2048, "lateral-interna-esquerda": 2048, "lateral-interna-direita": 2048,
  prancha: 2048, "fundo-cesta": 1280, "teto-interno": 768, frente: 1024, "testeira-frente": 768, "testeira-fundo": 512,
  "testeira-teto": 512, "testeira-superior-esquerda": 512, "testeira-superior-direita": 512,
  "testeira-lateral-esquerda": 512, "testeira-lateral-direita": 512,
};

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map(); // nome -> { material, geometrias: [] }
function material(nome, opcoes) {
  // `opcoes` é o material pronto (os do comum3d.js) ou as opções de um MeshStandardMaterial
  if (!pecas.has(nome)) {
    const m = opcoes && opcoes.isMaterial ? opcoes : new THREE.MeshStandardMaterial({ name: nome, roughness: 0.6, metalness: 0, ...opcoes });
    m.name = nome;
    pecas.set(nome, { material: m, geometrias: [] });
  }
  return nome;
}
function por(nome, geometria, matriz) {
  if (matriz) geometria.applyMatrix4(matriz);
  pecas.get(nome).geometrias.push(geometria);
}
function tela(w, h, pintar) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  pintar(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
// a rede da cesta: a malha branca em losangos (o resto é transparente)
const texRede = tela(64, 64, (g, w, h) => {
  g.clearRect(0, 0, w, h);
  g.strokeStyle = "#ffffff";
  g.lineWidth = 7;
  for (let k = -w; k <= 2 * w; k += w / 2) {
    g.beginPath(); g.moveTo(k, 0); g.lineTo(k + h, h); g.stroke();
    g.beginPath(); g.moveTo(k, h); g.lineTo(k + h, 0); g.stroke();
  }
});
// a bola de basquete: laranja com os gomos pretos
const texBola = tela(128, 64, (g, w, h) => {
  g.fillStyle = "#e8711f";
  g.fillRect(0, 0, w, h);
  g.strokeStyle = "#1c1209";
  g.lineWidth = 3;
  for (const x of [0, w / 4, w / 2, (3 * w) / 4]) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
  g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w, h / 2); g.stroke();
});
texBola.wrapT = THREE.ClampToEdgeWrapping;
// o placar: o visor preto com os dois dígitos vermelhos (o 88 apagado por baixo)
const texPlacar = tela(256, 128, (g, w, h) => {
  g.fillStyle = "#0a0a0c";
  g.fillRect(0, 0, w, h);
  const digito = (x0, cor, segs) => {
    g.fillStyle = cor;
    const [L, E, y0] = [42, 11, 10];
    const P = { a: [x0 + E, y0, L, E], b: [x0 + L + E, y0 + E, E, L], c: [x0 + L + E, y0 + 2 * E + L, E, L], d: [x0 + E, y0 + 2 * L + 2 * E, L, E],
      e: [x0, y0 + 2 * E + L, E, L], f: [x0, y0 + E, E, L], g: [x0 + E, y0 + L + E, L, E] };
    for (const s of segs) g.fillRect(...P[s]);
  };
  for (const x of [58, 138]) { digito(x, "#3a0d0d", "abcdefg"); digito(x, "#ff2a2a", "abcdef"); }
});
texPlacar.wrapS = texPlacar.wrapT = THREE.ClampToEdgeWrapping;

const M = {
  preto: material("mdf-preto", C.acetinado("mdf-preto", "#2b2c30")), // o preto dos adesivos (#333), acetinado
  estrutura: material("estrutura-tubo-preto", { color: "#17181b", roughness: 0.35, metalness: 0.7 }),
  pes: material("pes-niveladores", { color: "#111214", roughness: 0.7 }),
  parada: material("chapa-de-parada", C.cromo("chapa-de-parada", "#b8bfc8", { roughness: 0.22 })),
  aro: material("aro", new THREE.MeshPhysicalMaterial({ color: "#ff4a12", roughness: 0.3, metalness: 0.35, clearcoat: 1, clearcoatRoughness: 0.08 })),
  suporte: material("suporte-da-cesta", C.cromo("suporte-da-cesta")),
  redeCesta: material("rede-da-cesta", { color: "#ffffff", map: texRede, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.8 }),
  bolas: material("bolas", new THREE.MeshPhysicalMaterial({ map: texBola, roughness: 0.55, clearcoat: 0.35, clearcoatRoughness: 0.4 })),
  neon: material("neon-roxo", C.aceso("neon-roxo", "#9a45ff", 2.6)),
  placar: material("placar", { color: "#000000", map: texPlacar, emissive: "#ffffff", emissiveMap: texPlacar, emissiveIntensity: 1.6, roughness: 0.2 }),
  moldura: material("moldura-do-placar", C.acetinado("moldura-do-placar", "#101113", { roughness: 0.25, clearcoat: 0.8 })),
  porta: material("porta-do-moedeiro", { color: "#16171a", roughness: 0.4, metalness: 0.5 }),
  moedeiro: material("moedeiro", C.cromo("moedeiro")),
  start: material("botao-start", new THREE.MeshPhysicalMaterial({ color: "#ffd21f", emissive: "#ffb800", emissiveIntensity: 1.4, roughness: 0.25, clearcoat: 1 })),
};

// ---------- os adesivos: a imagem da peça, inteira, na sua face ----------
const PECAS = {}; // o que vai para o pecas.json (o tamanho de cada peça no 3D)
const avisos = [];
function imagem(arquivo) {
  return new Promise((ok, falha) => {
    const i = new Image();
    i.onload = () => ok(i);
    i.onerror = () => falha(new Error(arquivo));
    i.src = arquivo;
  });
}
// o material de um adesivo: a imagem da peça, ampliada com suavização até a
// RESOLUCAO (a folha tem pouca resolução) e com a proporção dela; `mm` é o
// retângulo da imagem no 3D (avisa se a proporção não bate)
async function adesivo(peca, mm, onde, { brilho = 0 } = {}) {
  const [w, h] = FORMAS[peca].px;
  const { textura: t, w: tw, h: th, hd } = await C.arte("", peca, { lado: RESOLUCAO[peca] || 512, px: [w, h], avisos });
  PECAS[peca] = {
    arquivo: hd ? `adesivos-hd/${peca}.webp` : `adesivos/${peca}.png`, px_no_glb: [tw, th], mm: mm.map((v) => Math.round(v)), onde,
    ...(FORMAS[peca].contorno ? { contorno: true } : {}), ...(FORMAS[peca].furos ? { furos: FORMAS[peca].furos.length } : {}),
  };
  const proporcao = w / h / (mm[0] / mm[1]);
  if (Math.abs(proporcao - 1) > 0.03) avisos.push(`${peca}: a face tem outra proporção que a peça (${(100 * (proporcao - 1)).toFixed(1)}%)`);
  // a testeira é acesa (o letreiro com a luz por trás)
  const luz = brilho ? { emissive: "#ffffff", emissiveMap: t, emissiveIntensity: brilho } : {};
  return material(`adesivo-${peca}`, C.vinil(`adesivo-${peca}`, t, luz));
}

// ---------- peças básicas (em mm) ----------
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  por(nome, new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0)),
    new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function cilindro(nome, a, b, r, lados = 16) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, false);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, V(1, 1, 1)));
}
// um tubo (o neon) por uma linha de pontos 3D
function tubo(nome, pontos, r, lados = 6) {
  const caminho = new THREE.CurvePath();
  for (let i = 0; i < pontos.length - 1; i++) caminho.add(new THREE.LineCurve3(pontos[i], pontos[i + 1]));
  por(nome, new THREE.TubeGeometry(caminho, Math.max(1, pontos.length - 1), r, lados, false));
}
// uma forma (pontos [a, b] no plano de uma face), no sentido anti-horário, com furos
function forma(pontos, furos = []) {
  const p = pontos.map(([a, b]) => new THREE.Vector2(a, b));
  if (THREE.ShapeUtils.isClockWise(p)) p.reverse();
  const s = new THREE.Shape(p);
  for (const f of furos) {
    const q = f.map(([a, b]) => new THREE.Vector2(a, b));
    if (!THREE.ShapeUtils.isClockWise(q)) q.reverse();
    s.holes.push(new THREE.Path(q));
  }
  return s;
}
// a base de uma face: a origem (na superfície do adesivo) e os eixos de quem
// olha DE FORA (U para a direita, W para cima); a normal (U x W) aponta para fora
function base(origem, U, W) {
  const N = new THREE.Vector3().crossVectors(U, W).normalize();
  return { origem, U, W, N, matriz: () => new THREE.Matrix4().makeBasis(U, W, N).setPosition(origem),
    ponto: (a, b, n = 0) => origem.clone().addScaledVector(U, a).addScaledVector(W, b).addScaledVector(N, n) };
}
// uma placa: o contorno extrudado para DENTRO (a espessura), atrás do adesivo
function placa(nome, pontos, b, espessura, furos = []) {
  const g = new THREE.ExtrudeGeometry(forma(pontos, furos), { depth: espessura, bevelEnabled: false, curveSegments: 1 });
  g.translate(0, 0, -espessura - PELE);
  por(nome, g, b.matriz());
}
// o adesivo de uma face: o contorno da peça; a imagem cobre o retângulo `ret`
// [a0, b0, a1, b1] (o da peça inteira, ou a faixa dela entre v0 e v1) e o contorno corta o resto
function colar(nome, pontos, b, ret, v0 = 0, v1 = 1, furos = []) {
  const g = new THREE.ShapeGeometry(forma(pontos, furos), 1);
  const pos = g.attributes.position;
  const uv = g.attributes.uv;
  for (let i = 0; i < pos.count; i++) {
    uv.setXY(i, (pos.getX(i) - ret[0]) / (ret[2] - ret[0]), v0 + ((v1 - v0) * (pos.getY(i) - ret[1])) / (ret[3] - ret[1]));
  }
  por(nome, g, b.matriz());
}
const retangulo = (a0, b0, a1, b1) => [[a0, b0], [a1, b0], [a1, b1], [a0, b1]];
// um retângulo colado (a peça inteira) na face
async function retanguloColado(peca, b, largura, altura, onde, opcoes = {}) {
  const m = await adesivo(peca, [largura, altura], onde, opcoes);
  colar(m, retangulo(0, 0, largura, altura), b, [0, 0, largura, altura]);
}

/* ======================================================================
   1. AS LATERAIS: uma chapa de cada lado, com o contorno da lateral de fora
   (e, atrás dela, até as costas); por fora o adesivo de fora, por dentro o
   L de dentro (até onde a chapa vai). Os gomos brancos da bola são FUROS:
   atravessam a chapa e os dois adesivos, abertos (sem grade).
   ====================================================================== */
for (const s of [-1, 1]) {
  const lado = s < 0 ? "esquerda" : "direita";
  // de fora: na esquerda (-x), a frente fica à direita da imagem; na direita, à esquerda
  const fora = s < 0 ? base(V(-XF, PE, Z_EXT), V(0, 0, 1), V(0, 1, 0)) : base(V(XF, PE, ZF), V(0, 0, -1), V(0, 1, 0));
  const zDeFora = s < 0 ? (a) => Z_EXT + a : (a) => ZF - a;
  const aDeFora = s < 0 ? (z) => z - Z_EXT : (z) => ZF - z;
  const ext = EXT[lado];
  // a chapa: o contorno da lateral de fora, com o pé de trás levado até as costas
  const aCostas = aDeFora(ZB);
  const atras = s < 0 ? Math.min(...ext.pontos.map(([a]) => a)) : Math.max(...ext.pontos.map(([a]) => a));
  const ptsChapa = ext.pontos.map(([a, b]) => [Math.abs(a - atras) < 2 ? aCostas : a, b]);
  // (a chapa, embaixo do adesivo, com o contorno e os furos simplificados: menos triângulos, a mesma forma)
  const fechado = (f) => {
    // o polígono fechado: partido no ponto mais longe do primeiro, cada metade simplificada
    const d = (q) => Math.hypot(q[0] - f[0][0], q[1] - f[0][1]);
    const longe = f.reduce((m, q, k) => (d(q) > d(f[m]) ? k : m), 0);
    return [...simplificar(f.slice(0, longe + 1), 4).slice(0, -1), ...simplificar([...f.slice(longe), f[0]], 4).slice(0, -1)];
  };
  // os furos (os gomos vazados, abertos: sem grade): o contorno dos pixels
  // suavizado (Chaikin, três vezes) e enxugado, o MESMO no adesivo de fora, na
  // chapa e no L de dentro, para a borda do furo sair limpa; a parede do furo,
  // na espessura da chapa, é a chapa preta (o preto do adesivo)
  const suavizar = (f) => {
    let q = f;
    for (let k = 0; k < 3; k++) {
      q = q.flatMap((p, i) => {
        const r = q[(i + 1) % q.length];
        return [[0.75 * p[0] + 0.25 * r[0], 0.75 * p[1] + 0.25 * r[1]], [0.25 * p[0] + 0.75 * r[0], 0.25 * p[1] + 0.75 * r[1]]];
      });
    }
    const d = (p) => Math.hypot(p[0] - q[0][0], p[1] - q[0][1]);
    const longe = q.reduce((m, p, k) => (d(p) > d(q[m]) ? k : m), 0);
    return [...simplificar(q.slice(0, longe + 1), 1.5).slice(0, -1), ...simplificar([...q.slice(longe), q[0]], 1.5).slice(0, -1)];
  };
  const furos = ext.furos.map(suavizar);
  // a chapa de 25 mm com a borda arredondada (nos furos também); o adesivo, do
  // tamanho da face plana (o contorno e os furos afastados do raio da borda)
  por(M.preto, C.placaArredondada(fechado(ptsChapa), ESP_LAT, RAIO_LAT, furos), fora.matriz());
  const mExt = await adesivo(`lateral-externa-${lado}`, [ext.ret[2] - ext.ret[0], ext.ret[3] - ext.ret[1]],
    `o lado de fora da ${lado}, com o contorno da folha e a bola vazada (vista de fora)`);
  colar(mExt, C.recuar(fechado(ext.pontos.map((p) => p.slice())), RAIO_LAT + 0.5), fora, ext.ret, 0, 1, furos.map((f) => C.recuar(f, -(RAIO_LAT + 0.5))));
  // de dentro (de quem está na pista): na esquerda, a frente fica à esquerda da imagem
  const dentro = s < 0
    ? base(V(-XI, PISO_L, ZF - PELE - ESP), V(0, 0, -1), V(0, 1, 0))
    : base(V(XI, PISO_L, Z_COSTAS + ESP), V(0, 0, 1), V(0, 1, 0));
  const zDe = s < 0 ? (a) => ZF - PELE - ESP - a : (a) => Z_COSTAS + ESP + a;
  const aDe = s < 0 ? (z) => ZF - PELE - ESP - z : (z) => z - Z_COSTAS - ESP;
  const int = INT[lado];
  // o L de dentro só vai até onde a chapa vai (o que passaria do contorno da
  // lateral de fora, no alto da frente da parte alta, fica cortado): por cima,
  // o menor entre o L e a chapa, ponto a ponto
  const cortes = new Set();
  for (const [a] of int.pontos) for (const d of [-0.05, 0.05]) cortes.add(Math.min(int.largura, Math.max(0, a + d)));
  for (const [a] of ext.pontos) cortes.add(aDe(zDeFora(a)));
  const as = [...cortes].filter((a) => a >= 0 && a <= int.largura).sort((p, q) => p - q);
  let topo = as.map((a) => [a, Math.min(altoEm(int.pontos, a), chapaEm(zDe(a)) - PISO_L)]).reverse(); // de trás para a frente
  // os furos da bola, no plano de dentro: o que fica todo dentro do L é furo; o
  // que passa do alto do L (a bola sobe acima da parede de dentro) vira um
  // recorte na borda de cima dele; o que fica todo acima, só na chapa
  const furosInt = [];
  for (const furo of furos.map((f) => f.map(([a, b]) => [aDe(zDeFora(a)), b + PE - PISO_L]))) {
    const alto = ([a, b]) => b > altoEm(topo, a) - 0.5;
    const acima = furo.map(alto);
    if (acima.every(Boolean)) continue;
    if (!acima.some(Boolean)) { furosInt.push(furo); continue; }
    const H = int.altura; // a bola fica na parte alta, de borda reta
    const cruz = [];
    for (let i = 0; i < furo.length; i++) {
      const [pa, pb] = furo[i];
      const [qa, qb] = furo[(i + 1) % furo.length];
      if ((pb > H) !== (qb > H)) cruz.push({ i, ponto: [pa + ((H - pb) / (qb - pb)) * (qa - pa), H], desce: pb > H });
    }
    if (cruz.length !== 2) { avisos.push(`lateral-interna-${lado}: um furo cruza a borda ${cruz.length} vezes (ficou só na chapa)`); continue; }
    const [c1, c2] = cruz[0].desce ? cruz : [cruz[1], cruz[0]];
    let arco = [c1.ponto];
    for (let k = (c1.i + 1) % furo.length; ; k = (k + 1) % furo.length) {
      arco.push(furo[k]);
      if (k === c2.i) break;
    }
    arco.push(c2.ponto);
    if (arco[0][0] < arco[arco.length - 1][0]) arco = arco.reverse();
    const [aHi, aLo] = [arco[0][0], arco[arco.length - 1][0]];
    topo = [...topo.filter(([a]) => a > aHi), ...arco, ...topo.filter(([a]) => a < aLo)];
  }
  const ptsInt = [[as[0], 0], [as[as.length - 1], 0], ...topo];
  const mInt = await adesivo(`lateral-interna-${lado}`, [int.ret[2] - int.ret[0], int.ret[3] - int.ret[1]],
    `o lado de dentro da ${lado}, em L, vista da pista (até onde a chapa vai; a bola vazada atravessa)`);
  // (do tamanho da face plana de dentro: o raio da borda da chapa fica de fora)
  colar(mInt, C.recuar(C.limpar(ptsInt), RAIO_LAT + 0.5), dentro, int.ret, 0, 1,
    furosInt.map((f) => C.recuar(f, -(RAIO_LAT + 0.5))));
  // o neon da borda: pelo contorno de cima da lateral, da quina da frente do console até as costas da testeira
  {
    const p = ext.pontos;
    const alto = (k) => p[k][1] > 0.25 * ext.altura;
    let ini = p.findIndex((_, k) => alto(k) && !alto((k - 1 + p.length) % p.length));
    const trecho = [];
    for (let k = ini; alto(k) && trecho.length < p.length; k = (k + 1) % p.length) trecho.push(p[k]);
    // a quina de baixo da face de pé do console fica de fora: o neon começa no alto dela
    // do alto do chanfro do console (a borda da tampa tem o seu) até a frente da testeira (embaixo dela, não)
    const linha = simplificar(trecho, 8).filter(([a]) => zDeFora(a) > ZT1 + 4 && zDeFora(a) < CONSOLE.zInclinada - 5);
    // por fora da chapa, rente à borda: a normal para fora do contorno (o contorno anda no sentido dos pontos)
    const area = p.reduce((s2, [a, b], k) => s2 + a * p[(k + 1) % p.length][1] - p[(k + 1) % p.length][0] * b, 0);
    const r = 11;
    const pts3 = linha.map(([a, b], k) => {
      const [pa, pb] = linha[Math.max(0, k - 1)];
      const [qa, qb] = linha[Math.min(linha.length - 1, k + 1)];
      let na = qb - pb, nb = -(qa - pa);
      if (area < 0) { na = -na; nb = -nb; }
      const L = Math.hypot(na, nb) || 1;
      return fora.ponto(a + (na / L) * (r + 1), b + (nb / L) * (r + 1), -PELE - ESP_LAT / 2);
    });
    tubo(M.neon, pts3, r);
  }
}

/* ======================================================================
   2. AS COSTAS: a estrutura de tubo preto (os dois montantes, as travessas de
   cima e de baixo) e a chapa das costas, recuada, com o fundo da cesta na frente
   ====================================================================== */
for (const s of [-1, 1]) caixa(M.estrutura, s * (XM - TUBO), s * XM, PE, TOPO, ZB, ZB + TUBO);
caixa(M.estrutura, -XM + TUBO, XM - TUBO, TOPO - TUBO, TOPO, ZB, ZB + TUBO);
caixa(M.estrutura, -XM + TUBO, XM - TUBO, PE, PE + TUBO, ZB, ZB + TUBO);
caixa(M.estrutura, -XM + TUBO, XM - TUBO, PE + 1100, PE + 1100 + TUBO, ZB, ZB + TUBO);
caixa(M.preto, -XM, XM, PE, TOPO, Z_COSTAS, Z_COSTAS + ESP);
await retanguloColado("fundo-cesta", base(V(-XI, Y_FUNDO, Z_FUNDO), V(1, 0, 0), V(0, 1, 0)), PISTA, FUNDO.altura,
  "o painel do fundo, atrás da cesta, do teto até a rampa (o placar no alto)");
// o placar na janela branca do fundo: a moldura preta e o visor com os dígitos
{
  const x0 = -XI + JANELA.u0 * PISTA, x1 = -XI + JANELA.u1 * PISTA;
  const y1 = TETO - JANELA.v0 * FUNDO.altura, y0 = TETO - JANELA.v1 * FUNDO.altura;
  caixa(M.moldura, x0 - 8, x1 + 8, y0 - 8, y1 + 8, Z_FUNDO, Z_FUNDO + 30);
  const g = new THREE.PlaneGeometry(x1 - x0, y1 - y0);
  por(M.placar, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, Z_FUNDO + 31));
}
// o teto interno, visto de baixo por quem joga: a frente no alto da imagem; a placa dele encosta na testeira
caixa(M.preto, -XM, XM, TETO + PELE, TOPO, Z_COSTAS + ESP, Z_FUNDO + TETO_INT.altura);
await retanguloColado("teto-interno", base(V(-XI, TETO, Z_FUNDO), V(1, 0, 0), V(0, 0, 1)), PISTA, TETO_INT.altura,
  "o teto da parte alta, visto de baixo (a frente no alto da imagem)");

/* ======================================================================
   3. A TESTEIRA: o hexágono da folha, em cima da parte alta das laterais
   ====================================================================== */
{
  const [cx, cy] = T.chanfro;
  const hexagono = [[-XF, TOPO], [XF, TOPO], [XF, TOPO + T.lado], [XF - cx, ALT], [-XF + cx, ALT], [-XF, TOPO + T.lado]];
  // o corpo, 1 mm para dentro de cada face (os adesivos ficam na medida de fora)
  const corpo = hexagono.map(([x, y]) => [x * (1 - 2 * PELE / (2 * XF)), TOPO + (y - TOPO) * (1 - PELE / H_T)]);
  const g = new THREE.ExtrudeGeometry(forma(corpo), { depth: ZT1 - ZT0 - 2 * PELE, bevelEnabled: false });
  por(M.preto, g, new THREE.Matrix4().makeTranslation(0, 0, ZT0 + PELE));
  // a frente (o contorno da folha) e o fundo
  const mFrente = await adesivo("testeira-frente", [T_FRENTE.ret[2] - T_FRENTE.ret[0], T_FRENTE.ret[3] - T_FRENTE.ret[1]],
    "a frente da testeira (o letreiro, aceso), com o contorno da folha", { brilho: 0.3 });
  colar(mFrente, T_FRENTE.pontos, base(V(-XF, TOPO, ZT1), V(1, 0, 0), V(0, 1, 0)), T_FRENTE.ret);
  const fundo = emMm("testeira-fundo", S_T);
  const desloca = (2 * XF - fundo.largura) / 2;
  const ptsFundo = fundo.pontos.map(([a, b]) => [a + desloca, b]);
  const retFundo = [fundo.ret[0] + desloca, fundo.ret[1], fundo.ret[2] + desloca, fundo.ret[3]];
  const mFundo = await adesivo("testeira-fundo", [retFundo[2] - retFundo[0], retFundo[3] - retFundo[1]], "o fundo da testeira, visto de trás");
  colar(mFundo, ptsFundo, base(V(XF, TOPO, ZT0), V(-1, 0, 0), V(0, 1, 0)), retFundo);
  // o teto (visto de cima, a frente embaixo da imagem)
  await retanguloColado("testeira-teto", base(V(-XF + cx, ALT, ZT1), V(1, 0, 0), V(0, 0, -1)), 2 * XF - 2 * cx, ZT1 - ZT0,
    "o alto da testeira, visto de cima (a frente embaixo da imagem)");
  // os chanfros: a ponta da frente da peça (endireitada) vai na frente; o lado de cima, no teto
  const chanfro = Math.hypot(cx, cy);
  await retanguloColado("testeira-superior-esquerda", base(V(-XF, TOPO + T.lado, ZT0), V(0, 0, 1), V(cx / chanfro, cy / chanfro, 0)),
    ZT1 - ZT0, chanfro, "o chanfro da esquerda da testeira (a frente à direita, o teto em cima)");
  await retanguloColado("testeira-superior-direita", base(V(XF, TOPO + T.lado, ZT1), V(0, 0, -1), V(-cx / chanfro, cy / chanfro, 0)),
    ZT1 - ZT0, chanfro, "o chanfro da direita da testeira (a frente à esquerda, o teto em cima)");
  // os lados retos, embaixo dos chanfros
  await retanguloColado("testeira-lateral-esquerda", base(V(-XF, TOPO, ZT0), V(0, 0, 1), V(0, 1, 0)), ZT1 - ZT0, T.lado,
    "o lado reto da esquerda da testeira, visto de fora");
  await retanguloColado("testeira-lateral-direita", base(V(XF, TOPO, ZT1), V(0, 0, -1), V(0, 1, 0)), ZT1 - ZT0, T.lado,
    "o lado reto da direita da testeira, visto de fora");
}

/* ======================================================================
   4. A CESTA: o suporte, o aro e a rede, no fundo, embaixo do placar
   ====================================================================== */
{
  const { y, raio } = ARO;
  const z = Z_FUNDO + 12 + 40 + raio;
  caixa(M.suporte, -130, 130, y - 150, y + 30, Z_FUNDO, Z_FUNDO + 12); // a chapa no fundo
  for (const lado of [-1, 1]) {
    const a = 0.8; // os braços pegam o aro a ±46° da parte de trás
    cilindro(M.suporte, V(lado * 100, y, Z_FUNDO + 12), V(lado * raio * Math.sin(a), y, z - raio * Math.cos(a)), 9, 8);
  }
  cilindro(M.suporte, V(0, y - 130, Z_FUNDO + 12), V(0, y, z - raio), 9, 8);
  const aro = new THREE.TorusGeometry(raio, 10, 10, 48);
  aro.rotateX(PI / 2);
  por(M.aro, aro, new THREE.Matrix4().makeTranslation(0, y, z));
  const rede = new THREE.CylinderGeometry(raio - 5, raio * 0.62, 280, 32, 1, true);
  const uv = rede.attributes.uv;
  for (let k = 0; k < uv.count; k++) uv.setXY(k, uv.getX(k) * 8, uv.getY(k) * 1.6);
  por(M.redeCesta, rede, new THREE.Matrix4().makeTranslation(0, y - 140, z));
}

/* ======================================================================
   5. A RAMPA (a prancha com a quadra, a cesta no alto da imagem), a chapa
   de parada embaixo da tampa do console e as bolas
   ====================================================================== */
{
  const { ang, y, zFrente } = RAMPA;
  const sobe = V(0, Math.sin(ang), -Math.cos(ang)); // da frente para o fundo, subindo
  const b = base(V(-XI, y(zFrente), zFrente), V(1, 0, 0), sobe);
  placa(M.preto, retangulo(0, 0, PISTA, PRANCHA.altura), b, ESP);
  await retanguloColado("prancha", b, PISTA, PRANCHA.altura,
    "a rampa que devolve a bola, vista de cima por quem joga (a cesta no alto da imagem); a ponta da frente passa embaixo da tampa do console");
  // a chapa de parada: de pé, da rampa até a tampa, logo atrás da faixa de cima da Frente
  const zP = CONSOLE.zFimCima;
  caixa(M.parada, -XI, XI, y(zP) - 10, CONSOLE.yCima - PELE - ESP, zP, zP + 3);
  // as bolas: quatro paradas na chapa e duas descendo a rampa
  const N = V(0, Math.cos(ang), Math.sin(ang)); // a normal da rampa
  // a bola com o centro em z, apoiada na rampa
  const bola = (x, zc) => {
    const zr = zc - N.z * (BOLA + 1);
    const c = V(x, y(zr), zr).addScaledVector(N, BOLA + 1);
    por(M.bolas, new THREE.SphereGeometry(BOLA, 14, 10), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
  };
  for (const x of [-354, -118, 118, 354]) bola(x, zP - BOLA - 2);
  bola(-160, -150);
  bola(200, 220);
}

/* ======================================================================
   6. O CONSOLE DA FRENTE: as três faces, cada uma com a sua faixa da Frente
   (o POW! de pé, o BASKETBALL inclinado, a tampa com o botão Start), a
   porta do moedeiro e o neon
   ====================================================================== */
{
  const { ang, zInclinada, yCima, zFimCima } = CONSOLE;
  const largura = 2 * XF;
  const W = FRENTE.largura;
  // as placas: a de pé, a inclinada e a de cima (1 mm atrás de cada adesivo)
  caixa(M.preto, -XM, XM, PE, PE + FAIXA.baixo, ZF - PELE - ESP, ZF - PELE);
  {
    const g = new THREE.BoxGeometry(2 * XM, FAIXA.meio, ESP);
    const sobe = V(0, Math.sin(ang), -Math.cos(ang));
    const normal = V(0, Math.cos(ang), Math.sin(ang));
    const meio = V(0, PE + FAIXA.baixo, ZF).addScaledVector(sobe, FAIXA.meio / 2).addScaledVector(normal, -PELE - ESP / 2);
    por(M.preto, g, new THREE.Matrix4().makeBasis(V(1, 0, 0), sobe, normal).setPosition(meio));
  }
  caixa(M.preto, -XM, XM, yCima - PELE - ESP, yCima - PELE, zFimCima, zInclinada);
  const m = await adesivo("frente", [W, FRENTE.altura], "a frente do console, dobrada em três: a faixa de baixo de pé, a do meio inclinada e a de cima deitada (a tampa, com o Start)");
  // a imagem: a faixa de cima (v de 1-D1 a 1), a do meio, a de baixo (v de 0 a 1-D2)
  colar(m, retangulo(0, 0, largura, FAIXA.baixo), base(V(-XF, PE, ZF), V(1, 0, 0), V(0, 1, 0)), [0, 0, largura, FAIXA.baixo], 0, 1 - D2);
  colar(m, retangulo(0, 0, largura, FAIXA.meio), base(V(-XF, PE + FAIXA.baixo, ZF), V(1, 0, 0), V(0, Math.sin(ang), -Math.cos(ang))),
    [0, 0, largura, FAIXA.meio], 1 - D2, 1 - D1);
  colar(m, retangulo(0, 0, largura, FAIXA.cima), base(V(-XF, yCima, zInclinada), V(1, 0, 0), V(0, 0, -1)),
    [0, 0, largura, FAIXA.cima], 1 - D1, 1);
  // o botão Start, na marca tracejada da tampa
  {
    const x0 = -XF + START.u0 * largura + 12, x1 = -XF + START.u1 * largura - 12;
    const b0 = ((D1 - START.v1) / D1) * FAIXA.cima + 6, b1 = ((D1 - START.v0) / D1) * FAIXA.cima - 6;
    const g = new THREE.CapsuleGeometry((b1 - b0) / 2, x1 - x0 - (b1 - b0), 3, 12);
    g.rotateZ(PI / 2);
    g.scale(1, 1, 0.25);
    g.rotateX(PI / 2);
    por(M.start, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, yCima + 4, zInclinada - (b0 + b1) / 2));
  }
  // a porta do moedeiro: a porta preta, o moedeiro cromado (com a fenda) e a fechadura
  {
    // (rentes à face: a máquina fica nos 2,40 m)
    const { x0, x1, y0, y1 } = PORTA;
    caixa(M.porta, x0, x1, y0, y1, ZF, ZF + 1.5);
    const xm = (x0 + x1) / 2;
    caixa(M.moedeiro, xm - 38, xm + 38, y0 + 170, y0 + 300, ZF + 1.5, ZF + 3.5);
    caixa(M.porta, xm - 3, xm + 3, y0 + 245, y0 + 285, ZF + 3.5, ZF + 4); // a fenda da moeda
    caixa(M.porta, xm - 22, xm + 22, y0 + 190, y0 + 205, ZF + 3.5, ZF + 4); // o retorno da moeda
    cilindro(M.moedeiro, V(x1 - 35, y0 + 120, ZF + 1.5), V(x1 - 35, y0 + 120, ZF + 4), 12, 16); // a fechadura
  }
  // o neon: a borda da tampa, na quina com o chanfro, e a luz do pé, embaixo da
  // frente e dos lados do console (dentro da medida: a máquina fica nos 1,00 x 2,40 m)
  const r = 9;
  tubo(M.neon, [V(-XF + r, yCima + r, zInclinada), V(XF - r, yCima + r, zInclinada)], r);
  tubo(M.neon, [V(-XF + 12, PE / 2, CONSOLE.zBoca), V(-XF + 12, PE / 2, ZF - 12), V(XF - 12, PE / 2, ZF - 12), V(XF - 12, PE / 2, CONSOLE.zBoca)], 8);
}

/* ======================================================================
   7. OS PÉS NIVELADORES: embaixo das chapas das laterais e da frente
   ====================================================================== */
for (const s of [-1, 1]) {
  for (const z of [ZF - 70, 0, ZB + 70]) {
    cilindro(M.pes, V(s * (XF - 30), 0, z), V(s * (XF - 30), 8, z), 32, 12); // a sapata
    cilindro(M.estrutura, V(s * (XF - 30), 8, z), V(s * (XF - 30), PE + 1, z), 9, 8); // a rosca
  }
}

/* ======================================================================
   MONTAGEM FINAL: metros, junta por material, centraliza e assenta no chão
   ====================================================================== */
const raiz = C.montarFinal(pecas, "basquete-street-quadrinhos", { mergeGeometries, mergeVertices });
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 1000) / 1000);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
window.pecas = PECAS;
window.avisos = avisos;
window.escala = {
  testeira_mm_por_px: +S_T.toFixed(3), laterais_de_fora: +S_E.toFixed(3), laterais_de_dentro: +S_I.toFixed(3),
  lateral_de_fora_comprimento: Math.round(D_E), paredes_de_dentro: [Math.round(PISO_L), Math.round(PISO_L + INT.esquerda.altura)],
  teto: Math.round(TETO), fundo_da_cesta: [Math.round(Y_FUNDO), Math.round(TETO)],
  rampa: { graus: +(RAMPA.ang * 180 / PI).toFixed(1), na_parada: Math.round(RAMPA.yParada), atras: Math.round(RAMPA.yAtras),
    embaixo_da_tampa_mm: Math.round(RAMPA.zFrente - CONSOLE.zFimCima) },
  console: { chanfro_graus: +(CONSOLE.ang * 180 / PI).toFixed(1), tampa: Math.round(CONSOLE.yCima), boca_mm: Math.round(CONSOLE.zFimCima - CONSOLE.zBoca) },
  aro: Math.round(ARO.y), furos: Object.fromEntries(Object.entries(EXT).map(([k, e]) => [k, e.furos.length])),
};

// ---------- as vistas de conferência (gerar_glb.cjs: v-*.jpg) e a exportação ----------
C.vistas(raiz);
window.vistasDeConferencia = {
  frente34: [[3.6, 2.6, 4.6], [0, 1.25, 0], 34],
  esquerda: [[-6.2, 1.5, 0.1], [0, 1.3, 0], 34],
  direita: [[6.2, 1.5, -0.1], [0, 1.3, 0], 34],
  frente: [[0, 1.6, 6.4], [0, 1.3, 0], 34],
  costas: [[-3.0, 2.4, -5.2], [0, 1.3, 0], 34],
  jogador: [[0, 1.55, 2.25], [0, 1.6, -1.0], 55],
  bola: [[-2.0, 1.9, 0.4], [-0.5, 1.7, -0.5], 34],
};
window.exportar = () => C.exportar(raiz, GLTFExporter);
window.pronto = true;
