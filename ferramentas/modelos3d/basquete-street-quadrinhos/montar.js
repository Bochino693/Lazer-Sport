// Monta o Basquete Street Quadrinhos em three.js e exporta um .glb.
//
// O basquete de arcade com os adesivos em quadrinhos. TUDO sai da folha de
// adesivos da fábrica (folha-adesivos.webp, a 26567-2): a arte de cada peça
// (adesivos/<peça>.png) e o desenho dela (formas.json: o tamanho em px e, nas
// peças recortadas, o CONTORNO de verdade), que o recortar_adesivos.py tira
// da folha. Nada da arte é redesenhado: cada imagem vai inteira na sua face, e
// a face tem a forma e a proporção da peça.
//
// A folha é desenhada em ESCALA: a testeira, a frente, a prancha, o fundo e o
// teto têm a mesma largura (182 px = 1,00 m) e a lateral de fora mais a
// testeira dão os 2,70 m de altura. Daí a máquina, de trás para a frente
// (o jogador fica em +z):
//  - a TESTEIRA em cima (a "frente testeira" é um hexágono: os lados retos
//    embaixo e os chanfros em cima): a frente com o BASKETBALL, o fundo, o
//    teto, os dois chanfros ("superior") e os dois lados retos, cada um a sua
//    peça; 1,00 m x 0,27 m, 0,58 m de fundo;
//  - as LATERAIS DE FORA com o contorno da folha: a parte alta atrás (até a
//    testeira), a curva e a diagonal até a parte baixa, e na frente o chanfro
//    do console; 2,30 m de comprido;
//  - as LATERAIS DE DENTRO em L (a parte alta atrás, a baixa na frente): na
//    mesma escala, 2,40 m -- a profundidade da máquina; elas vão do fundo até
//    a frente, e a parte alta delas, onde passa da diagonal da lateral de
//    fora, aparece por fora em preto (é a parede da pista);
//  - dentro: o FUNDO DA CESTA (com o placar e o BOOM!), o TETO INTERNO em
//    cima dele, a cesta e a PRANCHA com a quadra no chão da pista;
//  - na frente, o console: a FRENTE dobra em três faixas (as linhas da folha):
//    o POW! na face de pé, o BASKETBALL na face inclinada (o chanfro da
//    lateral) e a de cima, deitada, com a marca do botão.
// As três peças soltas ao lado da Lateral Externa Esquerda, na folha, são as
// três faixas da Frente desenhadas de lado (mesma arte): não são outros adesivos.
//
// Coordenadas: as do three.js, em milímetros: x na largura (da esquerda para a
// direita de quem joga), y para cima, z no comprimento (a frente, o jogador,
// em +z). No fim tudo vira metros, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const FORMAS = await (await fetch(`formas.json?v=${Date.now()}`)).json();

// uma peça da folha em mm, na escala `s`: o contorno de verdade (ou o retângulo
// da peça), com o canto de baixo à esquerda em (0, 0), e o retângulo da imagem
// (o contorno fica 1 px para dentro da arte: no 3D não aparece o branco da folha)
function emMm(nome, s) {
  const { px: [w, h], contorno } = FORMAS[nome];
  const pts = (contorno || [[0, 0], [1, 0], [1, 1], [0, 1]]).map(([u, v]) => [u * w * s, (1 - v) * h * s]);
  const a0 = Math.min(...pts.map((p) => p[0]));
  const b0 = Math.min(...pts.map((p) => p[1]));
  const largura = Math.max(...pts.map((p) => p[0])) - a0;
  const altura = Math.max(...pts.map((p) => p[1])) - b0;
  return { pontos: pts.map(([a, b]) => [a - a0, b - b0]), ret: [-a0, -b0, w * s - a0, h * s - b0], largura, altura };
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

// ---------- as medidas (mm) ----------
const ALT = 2700; // a altura, no alto da testeira
const XF = 500; // a face de fora (o adesivo): 1,00 m de largura
const D = 2400; // a profundidade: a das laterais de dentro (na escala da folha, 2,40 m)
const ZB = -D / 2; // as costas
const ZF = D / 2; // a frente (o adesivo da Frente)
const ESP = 18; // o MDF
const PELE = 1; // o adesivo fica 1 mm fora da madeira
const XM = XF - PELE - ESP; // 481: a face de dentro das laterais
const XI = XM - PELE; // 480: o adesivo de dentro (a pista tem 960 mm)
const PISTA = 2 * XI;

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
const ALTO = ALT - H_T; // o alto das laterais (embaixo da testeira)

// as laterais de fora: o contorno de cada uma, na altura até a testeira
const S_E = ALTO / emMm("lateral-externa-esquerda", 1).altura; // ~5,44 mm por px
const EXT = { esquerda: emMm("lateral-externa-esquerda", S_E), direita: emMm("lateral-externa-direita", S_E) };
const D_E = EXT.esquerda.largura; // ~2300: a lateral de fora vai da frente até 10 cm do fundo
const Z_EXT = ZF - D_E; // onde ela começa (o fundo dela)
const ZT0 = Z_EXT; // a testeira, em cima da parte alta da lateral de fora
const ZT1 = Z_EXT + T.fundo;

// as laterais de dentro: o L entre o fundo e a frente (a placa da frente do console)
const L_DENTRO = D - 2 * ESP - PELE;
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
  const yCima = FAIXA.baixo + FAIXA.meio * Math.sin(ang); // a altura da face de cima
  return { ang, baixa, zInclinada, yCima, zFimCima: zInclinada - FAIXA.cima };
})();
// a pista: o chão na altura em que a parte baixa da parede de dentro encontra a de fora
const PISO = CONSOLE.baixa - altoEm(INT.esquerda.pontos, 0.15 * INT.esquerda.largura); // de dentro, na esquerda, a frente é a = 0
// a quina da frente da parede de dentro (reta, na folha) fica embaixo da face
// inclinada do console: o que passaria dela é cortado (fica escondido no console)
const abaixoDoConsole = (z) => FAIXA.baixo + (ZF - z) * Math.tan(CONSOLE.ang) - ESP / Math.cos(CONSOLE.ang) - 2;
function cortarNoConsole(pontos, zDe) {
  // Sutherland-Hodgman contra o plano inclinado: fica o que está embaixo dele
  const dentro = ([a, b]) => b + PISO <= abaixoDoConsole(zDe(a));
  const saida = [];
  for (let i = 0; i < pontos.length; i++) {
    const p = pontos[i];
    const q = pontos[(i + 1) % pontos.length];
    if (dentro(p)) saida.push(p);
    if (dentro(p) !== dentro(q)) {
      let lo = 0, hi = 1; // o cruzamento, por bisseção (a linha é reta, mas o z depende do lado)
      for (let k = 0; k < 40; k++) {
        const t = (lo + hi) / 2;
        const m = [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
        if (dentro(m) === dentro(p)) lo = t; else hi = t;
      }
      saida.push([p[0] + (q[0] - p[0]) * lo, p[1] + (q[1] - p[1]) * lo]);
    }
  }
  return saida;
}
const TETO = PISO + INT.esquerda.altura; // o teto interno: no alto das paredes de dentro
const ARO = { y: TETO - 400, raio: 150 };
const BOLA = 92; // o raio das bolas
// a resolução máxima de cada adesivo dentro do .glb (o lado maior, em px; a folha tem ~1/2)
const RESOLUCAO = {
  "lateral-externa-esquerda": 1024, "lateral-externa-direita": 1024, "lateral-interna-esquerda": 896, "lateral-interna-direita": 896,
  prancha: 896, "fundo-cesta": 768, "teto-interno": 512, frente: 768, "testeira-frente": 768, "testeira-fundo": 256,
  "testeira-teto": 384, "testeira-superior-esquerda": 384, "testeira-superior-direita": 384,
  "testeira-lateral-esquerda": 384, "testeira-lateral-direita": 384,
};
const QUALIDADE_JPEG = 0.82;

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map(); // nome -> { material, geometrias: [] }
function material(nome, opcoes) {
  if (!pecas.has(nome)) {
    pecas.set(nome, { material: new THREE.MeshStandardMaterial({ name: nome, roughness: 0.6, metalness: 0, ...opcoes }), geometrias: [] });
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

const M = {
  preto: material("mdf-preto", { color: "#2b2c30", roughness: 0.55 }), // o preto dos adesivos (#333)
  aro: material("aro", { color: "#ef4b1f", roughness: 0.4, metalness: 0.45 }),
  suporte: material("suporte-da-cesta", { color: "#c9ced6", roughness: 0.35, metalness: 0.6 }),
  redeCesta: material("rede-da-cesta", { color: "#ffffff", map: texRede, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.8 }),
  bolas: material("bolas", { map: texBola, roughness: 0.75 }),
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
  const arquivo = `adesivos/${peca}.png`;
  PECAS[peca] = { arquivo, mm: mm.map((v) => Math.round(v)), onde, ...(FORMAS[peca].contorno ? { contorno: true } : {}) };
  const [w, h] = FORMAS[peca].px;
  const escala = (RESOLUCAO[peca] || 512) / Math.max(w, h);
  const c = document.createElement("canvas");
  c.width = Math.round(w * escala);
  c.height = Math.round(h * escala);
  const g = c.getContext("2d");
  try {
    const i = await imagem(`${arquivo}?v=${Date.now()}`);
    g.imageSmoothingQuality = "high";
    g.drawImage(i, 0, 0, c.width, c.height);
  } catch {
    g.fillStyle = "#8a93a3";
    g.fillRect(0, 0, c.width, c.height);
    avisos.push(`${arquivo} não existe: a peça ficou cinza`);
  }
  const proporcao = w / h / (mm[0] / mm[1]);
  if (Math.abs(proporcao - 1) > 0.03) avisos.push(`${peca}: a face tem outra proporção que a peça (${(100 * (proporcao - 1)).toFixed(1)}%)`);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  t.userData.mimeType = "image/jpeg"; // no .glb, em JPEG (como os adesivos do Strike Kids)
  // a testeira é acesa (o letreiro com a luz por trás)
  const luz = brilho ? { emissive: "#ffffff", emissiveMap: t, emissiveIntensity: brilho } : {};
  return material(`adesivo-${peca}`, { map: t, roughness: 0.5, ...luz });
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
// uma forma (pontos [a, b] no plano de uma face), no sentido anti-horário
function forma(pontos) {
  const p = pontos.map(([a, b]) => new THREE.Vector2(a, b));
  if (THREE.ShapeUtils.isClockWise(p)) p.reverse();
  return new THREE.Shape(p);
}
// a base de uma face: a origem (na superfície do adesivo) e os eixos de quem
// olha DE FORA (U para a direita, W para cima); a normal (U x W) aponta para fora
function base(origem, U, W) {
  const N = new THREE.Vector3().crossVectors(U, W).normalize();
  return { origem, U, W, N, matriz: () => new THREE.Matrix4().makeBasis(U, W, N).setPosition(origem) };
}
// uma placa: o contorno extrudado para DENTRO (a espessura), atrás do adesivo
function placa(nome, pontos, b, espessura) {
  const g = new THREE.ExtrudeGeometry(forma(pontos), { depth: espessura, bevelEnabled: false });
  g.translate(0, 0, -espessura - PELE);
  por(nome, g, b.matriz());
}
// o adesivo de uma face: o contorno da peça; a imagem cobre o retângulo `ret`
// [a0, b0, a1, b1] (o da peça inteira, ou a faixa dela entre v0 e v1) e o contorno corta o resto
function colar(nome, pontos, b, ret, v0 = 0, v1 = 1) {
  const g = new THREE.ShapeGeometry(forma(pontos));
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
   1. AS LATERAIS: a de fora (o contorno da folha) e a de dentro (o L), cada
   uma numa placa de 9 mm, uma encostada na outra
   ====================================================================== */
for (const s of [-1, 1]) {
  const lado = s < 0 ? "esquerda" : "direita";
  // de fora: na esquerda (-x), a frente fica à direita da imagem; na direita, à esquerda
  const fora = s < 0 ? base(V(-XF, 0, Z_EXT), V(0, 0, 1), V(0, 1, 0)) : base(V(XF, 0, ZF), V(0, 0, -1), V(0, 1, 0));
  const ext = EXT[lado];
  // na direita a imagem começa pela frente: o contorno dela já vem assim (a parte alta à direita)
  placa(M.preto, ext.pontos, fora, ESP / 2);
  const mExt = await adesivo(`lateral-externa-${lado}`, [ext.ret[2] - ext.ret[0], ext.ret[3] - ext.ret[1]],
    `o lado de fora da ${lado}, com o contorno da folha (vista de fora)`);
  colar(mExt, ext.pontos, fora, ext.ret);
  // de dentro (de quem está na pista): na esquerda, a frente fica à esquerda da imagem
  const dentro = s < 0
    ? base(V(-XI, PISO, ZF - PELE - ESP), V(0, 0, -1), V(0, 1, 0))
    : base(V(XI, PISO, ZB + ESP), V(0, 0, 1), V(0, 1, 0));
  const int = INT[lado];
  const zDe = s < 0 ? (a) => ZF - PELE - ESP - a : (a) => ZB + ESP + a;
  const ptsInt = cortarNoConsole(int.pontos, zDe);
  placa(M.preto, ptsInt, dentro, ESP / 2);
  const mInt = await adesivo(`lateral-interna-${lado}`, [int.ret[2] - int.ret[0], int.ret[3] - int.ret[1]],
    `o lado de dentro da ${lado}, em L, da prancha para cima (visto da pista; a quina da frente fica sob o console)`);
  colar(mInt, ptsInt, dentro, int.ret);
  // atrás da lateral de fora (os 10 cm do fundo), a lateral fecha em preto até o alto
  caixa(M.preto, s * XM, s * (XF - PELE), 0, ALTO, ZB, Z_EXT + 2);
}

/* ======================================================================
   2. A PARTE ALTA: as costas, o fundo da cesta, o teto interno, a caixa de
   cima e a testeira (o hexágono da folha)
   ====================================================================== */
caixa(M.preto, -XM, XM, 0, ALTO - ESP, ZB, ZB + ESP); // as costas
const Z_FUNDO = ZB + ESP + PELE; // o adesivo do fundo da cesta
await retanguloColado("fundo-cesta", base(V(-XI, TETO - FUNDO.altura, Z_FUNDO), V(1, 0, 0), V(0, 1, 0)), PISTA, FUNDO.altura,
  "o painel do fundo, atrás da cesta, até o teto interno (o placar no alto)");
// o teto interno, visto de baixo por quem joga: a frente no alto da imagem
caixa(M.preto, -XM, XM, TETO + PELE, TETO + PELE + ESP, ZB + ESP, Z_FUNDO + TETO_INT.altura);
await retanguloColado("teto-interno", base(V(-XI, TETO, Z_FUNDO), V(1, 0, 0), V(0, 0, 1)), PISTA, TETO_INT.altura,
  "o teto da parte alta, visto de baixo (a frente no alto da imagem)");
// a caixa de cima (do teto interno até o alto das laterais): a frente e o tampo
{
  const zFrente = Z_FUNDO + TETO_INT.altura;
  const alto = altoEm(EXT.esquerda.pontos, zFrente - Z_EXT);
  caixa(M.preto, -XM, XM, TETO + PELE, alto - 2, zFrente, zFrente + ESP);
  caixa(M.preto, -XM, XM, ALTO - ESP, ALTO, ZB, zFrente + ESP);
}
// a testeira: o hexágono (os lados retos embaixo, os chanfros, o teto) extrudado na profundidade
{
  const [cx, cy] = T.chanfro;
  const hexagono = [[-XF, ALTO], [XF, ALTO], [XF, ALTO + T.lado], [XF - cx, ALT], [-XF + cx, ALT], [-XF, ALTO + T.lado]];
  // o corpo, 1 mm para dentro de cada face (os adesivos ficam na medida de fora)
  const corpo = hexagono.map(([x, y]) => [x * (1 - 2 * PELE / (2 * XF)), ALTO + (y - ALTO) * (1 - PELE / H_T)]);
  const g = new THREE.ExtrudeGeometry(forma(corpo), { depth: ZT1 - ZT0 - 2 * PELE, bevelEnabled: false });
  por(M.preto, g, new THREE.Matrix4().makeTranslation(0, 0, ZT0 + PELE));
  // a frente (o contorno da folha) e o fundo
  const mFrente = await adesivo("testeira-frente", [T_FRENTE.ret[2] - T_FRENTE.ret[0], T_FRENTE.ret[3] - T_FRENTE.ret[1]],
    "a frente da testeira (o letreiro, aceso), com o contorno da folha", { brilho: 0.3 });
  colar(mFrente, T_FRENTE.pontos, base(V(-XF, ALTO, ZT1), V(1, 0, 0), V(0, 1, 0)), T_FRENTE.ret);
  const fundo = emMm("testeira-fundo", S_T);
  const desloca = (2 * XF - fundo.largura) / 2;
  const ptsFundo = fundo.pontos.map(([a, b]) => [a + desloca, b]);
  const retFundo = [fundo.ret[0] + desloca, fundo.ret[1], fundo.ret[2] + desloca, fundo.ret[3]];
  const mFundo = await adesivo("testeira-fundo", [retFundo[2] - retFundo[0], retFundo[3] - retFundo[1]], "o fundo da testeira, visto de trás");
  colar(mFundo, ptsFundo, base(V(XF, ALTO, ZT0), V(-1, 0, 0), V(0, 1, 0)), retFundo);
  // o teto (visto de cima, a frente embaixo da imagem)
  await retanguloColado("testeira-teto", base(V(-XF + cx, ALT, ZT1), V(1, 0, 0), V(0, 0, -1)), 2 * XF - 2 * cx, ZT1 - ZT0,
    "o alto da testeira, visto de cima (a frente embaixo da imagem)");
  // os chanfros: a ponta da frente da peça (endireitada) vai na frente; o lado de cima, no teto
  const chanfro = Math.hypot(cx, cy);
  await retanguloColado("testeira-superior-esquerda", base(V(-XF, ALTO + T.lado, ZT0), V(0, 0, 1), V(cx / chanfro, cy / chanfro, 0)),
    ZT1 - ZT0, chanfro, "o chanfro da esquerda da testeira (a frente à direita, o teto em cima)");
  await retanguloColado("testeira-superior-direita", base(V(XF, ALTO + T.lado, ZT1), V(0, 0, -1), V(-cx / chanfro, cy / chanfro, 0)),
    ZT1 - ZT0, chanfro, "o chanfro da direita da testeira (a frente à esquerda, o teto em cima)");
  // os lados retos, embaixo dos chanfros
  await retanguloColado("testeira-lateral-esquerda", base(V(-XF, ALTO, ZT0), V(0, 0, 1), V(0, 1, 0)), ZT1 - ZT0, T.lado,
    "o lado reto da esquerda da testeira, visto de fora");
  await retanguloColado("testeira-lateral-direita", base(V(XF, ALTO, ZT1), V(0, 0, -1), V(0, 1, 0)), ZT1 - ZT0, T.lado,
    "o lado reto da direita da testeira, visto de fora");
}

/* ======================================================================
   3. A CESTA: o suporte, o aro e a rede, no fundo
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
   4. A PISTA: o chão (a prancha com a quadra, a cesta no alto da imagem) e as bolas
   ====================================================================== */
caixa(M.preto, -XM, XM, PISO - PELE - ESP, PISO - PELE, ZB + ESP, ZF - PELE - ESP);
await retanguloColado("prancha", base(V(-XI, PISO, Z_FUNDO + PRANCHA.altura), V(1, 0, 0), V(0, 0, -1)), PISTA, PRANCHA.altura,
  "o chão da pista, visto de cima por quem joga (a cesta no alto da imagem)");
for (const x of [-300, -100, 100, 300]) {
  por(M.bolas, new THREE.SphereGeometry(BOLA, 16, 12), new THREE.Matrix4().makeTranslation(x, PISO + BOLA, CONSOLE.zFimCima - BOLA - 30));
}
for (const [x, z] of [[-150, -200], [220, 250]]) {
  por(M.bolas, new THREE.SphereGeometry(BOLA, 16, 12), new THREE.Matrix4().makeTranslation(x, PISO + BOLA, z));
}

/* ======================================================================
   5. O CONSOLE DA FRENTE: as três faces, cada uma com a sua faixa da Frente
   ====================================================================== */
{
  const { ang, zInclinada, yCima, zFimCima } = CONSOLE;
  const largura = 2 * XF;
  const W = FRENTE.largura;
  // as placas: a de pé, a inclinada e a de cima (1 mm atrás de cada adesivo)
  caixa(M.preto, -XM, XM, 0, FAIXA.baixo, ZF - PELE - ESP, ZF - PELE);
  {
    const g = new THREE.BoxGeometry(2 * XM, FAIXA.meio, ESP);
    const sobe = V(0, Math.sin(ang), -Math.cos(ang));
    const normal = V(0, Math.cos(ang), Math.sin(ang));
    const meio = V(0, FAIXA.baixo, ZF).addScaledVector(sobe, FAIXA.meio / 2).addScaledVector(normal, -PELE - ESP / 2);
    por(M.preto, g, new THREE.Matrix4().makeBasis(V(1, 0, 0), sobe, normal).setPosition(meio));
  }
  caixa(M.preto, -XM, XM, yCima - PELE - ESP, yCima - PELE, zFimCima, zInclinada);
  const m = await adesivo("frente", [W, FRENTE.altura], "a frente do console, dobrada em três: a faixa de baixo de pé, a do meio inclinada e a de cima deitada");
  // a imagem: a faixa de cima (v de 1-D1 a 1), a do meio, a de baixo (v de 0 a 1-D2)
  colar(m, retangulo(0, 0, largura, FAIXA.baixo), base(V(-XF, 0, ZF), V(1, 0, 0), V(0, 1, 0)), [0, 0, largura, FAIXA.baixo], 0, 1 - D2);
  colar(m, retangulo(0, 0, largura, FAIXA.meio), base(V(-XF, FAIXA.baixo, ZF), V(1, 0, 0), V(0, Math.sin(ang), -Math.cos(ang))),
    [0, 0, largura, FAIXA.meio], 1 - D2, 1 - D1);
  colar(m, retangulo(0, 0, largura, FAIXA.cima), base(V(-XF, yCima, zInclinada), V(1, 0, 0), V(0, 0, -1)),
    [0, 0, largura, FAIXA.cima], 1 - D1, 1);
}

/* ======================================================================
   MONTAGEM FINAL: metros, junta por material, centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "basquete-street-quadrinhos";
cena.add(raiz);
const mm = new THREE.Matrix4().makeScale(0.001, 0.001, 0.001);
for (const [nome, { material: mat, geometrias }] of pecas) {
  if (!geometrias.length) continue;
  const prontas = geometrias.map((g) => {
    const h = g.index ? g.toNonIndexed() : g;
    if (!h.attributes.uv) h.setAttribute("uv", new THREE.Float32BufferAttribute(new Float32Array(h.attributes.position.count * 2), 2));
    if (!h.attributes.normal) h.computeVertexNormals();
    for (const k of Object.keys(h.attributes)) if (!["position", "normal", "uv"].includes(k)) h.deleteAttribute(k);
    h.clearGroups();
    return h;
  });
  let g = mergeGeometries(prontas, false);
  g.applyMatrix4(mm);
  g = mergeVertices(g, 1e-6);
  const malhaFinal = new THREE.Mesh(g, mat);
  malhaFinal.name = nome;
  raiz.add(malhaFinal);
}
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 1000) / 1000);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
window.pecas = PECAS;
window.avisos = avisos;
window.escala = {
  testeira_mm_por_px: +S_T.toFixed(3), laterais_de_fora: +S_E.toFixed(3), laterais_de_dentro: +S_I.toFixed(3),
  lateral_de_fora_comprimento: Math.round(D_E), parede_de_dentro_alto: Math.round(TETO), piso_da_pista: Math.round(PISO),
  console: { chanfro_graus: +(CONSOLE.ang * 180 / PI).toFixed(1), alto: Math.round(CONSOLE.yCima) }, aro: Math.round(ARO.y),
};

// ---------- vistas para conferir e as fotos do cadastro ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1600, 1000);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.append(renderer.domElement);
cena.add(new THREE.HemisphereLight("#ffffff", "#8b95a5", 1.8));
const sol = new THREE.DirectionalLight("#ffffff", 2.0);
sol.position.set(4, 9, 6);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 1, far: 30 });
sol.shadow.bias = -0.0004;
cena.add(sol);
// a rede da cesta não faz sombra cheia
raiz.traverse((o) => { if (o.isMesh) { o.castShadow = !o.name.startsWith("rede"); o.receiveShadow = true; } });
// o chão só das vistas (não vai para o .glb): recebe a sombra
const chao = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.ShadowMaterial({ opacity: 0.2 }));
chao.rotation.x = -PI / 2;
chao.receiveShadow = true;
cena.add(chao);
const piso = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: "#3d4a5c", roughness: 1 }));
piso.rotation.x = -PI / 2;
piso.position.y = -0.002;
cena.add(piso);
const camera = new THREE.PerspectiveCamera(34, 1600 / 1000, 0.05, 100);
window.ver = (x, y, z, alvo = [0, 1.3, 0], fundo = "#0b1a3a", fov = 34, sombra = true) => {
  cena.background = new THREE.Color(fundo);
  piso.visible = fundo === "#0b1a3a"; // no fundo claro das fotos, só a sombra
  chao.visible = sombra;
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
// a foto do cadastro: a última vista recortada no objeto (com uma margem),
// em 16:10, 1600 x 1000, em .webp (como as dos outros objetos)
window.recortar = (margem = 0.05, qualidade = 0.86) => {
  const src = renderer.domElement;
  const W = src.width, H = src.height;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d");
  g.drawImage(src, 0, 0);
  const px = g.getImageData(0, 0, W, H).data;
  const [fr, fg, fb] = [px[0], px[1], px[2]]; // o fundo: a cor do canto
  let x0 = W, y0 = H, x1 = 0, y1 = 0;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      if (Math.abs(px[i] - fr) + Math.abs(px[i + 1] - fg) + Math.abs(px[i + 2] - fb) > 18) {
        if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
  }
  let w = (x1 - x0) * (1 + 2 * margem), h = (y1 - y0) * (1 + 2 * margem);
  if (w / h > 1.6) h = w / 1.6; else w = h * 1.6;
  w = Math.min(w, W); h = Math.min(h, H);
  const cx = Math.min(Math.max((x0 + x1) / 2, w / 2), W - w / 2), cy = Math.min(Math.max((y0 + y1) / 2, h / 2), H - h / 2);
  const saida = document.createElement("canvas");
  saida.width = 1600;
  saida.height = 1000;
  const s = saida.getContext("2d");
  s.fillStyle = `rgb(${fr},${fg},${fb})`;
  s.fillRect(0, 0, 1600, 1000);
  s.drawImage(src, cx - w / 2, cy - h / 2, w, h, 0, 0, 1600, 1000);
  return saida.toDataURL("image/webp", qualidade);
};
window.exportar = async () => {
  // os adesivos vão em JPEG: o exportador usa o toBlob do canvas, sem dizer a
  // qualidade (a do Chromium é 0,92); aqui ela fica na QUALIDADE_JPEG. As
  // texturas desenhadas aqui (a rede da cesta, a bola) seguem em PNG.
  const toBlob = HTMLCanvasElement.prototype.toBlob;
  HTMLCanvasElement.prototype.toBlob = function (feito, tipo, qualidade) {
    return toBlob.call(this, feito, tipo, tipo === "image/jpeg" ? QUALIDADE_JPEG : qualidade);
  };
  try {
    const glb = await new GLTFExporter().parseAsync(raiz, { binary: true });
    const bytes = new Uint8Array(glb);
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(s);
  } finally {
    HTMLCanvasElement.prototype.toBlob = toBlob;
  }
};
window.pronto = true;
