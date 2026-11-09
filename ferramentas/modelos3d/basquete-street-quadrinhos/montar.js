// Monta o Basquete Street Quadrinhos em three.js e exporta um .glb.
//
// É a MESMA máquina do Basquete Street (o basquete de arcade de 2,70 m de
// altura, 1,00 m de largura e 2,40 m de comprimento), só com os adesivos
// novos, em quadrinhos: fundo preto, faixas arredondadas amarelas, laranja,
// vermelhas e rosa, os balões "POW!", "BOOM!" e "WOW!", o letreiro BASKETBALL,
// duas crianças jogando, a bola grande nas laterais de fora e a quadra com as
// linhas vermelhas na prancha.
//
// A arte NÃO é desenhada aqui: cada adesivo é um arquivo da pasta adesivos/
// (adesivos/<peça>.png, recortado da folha de adesivos da fábrica pelo
// recortar_adesivos.py; enquanto a folha não chega, a arte provisória do
// desenhar_provisorios.py). Este arquivo faz a máquina e põe cada adesivo na
// sua face; a peça recortada (as laterais) leva a imagem inteira e o contorno
// da peça corta o que sobra.
//
// A máquina, de trás para a frente (o jogador fica na frente, em +z):
//  - atrás, a parte ALTA: as laterais sobem até a testeira; dentro, o fundo
//    da cesta (o painel preto alto com o "BOOM!" e o placar), a cesta com a
//    rede e o teto interno; em cima, a testeira com o BASKETBALL;
//  - a quina de cima da parte alta desce em curva, na diagonal, até a parte
//    BAIXA (cerca de 1/3 da altura), que vai até a frente; em cima dela, o
//    corrimão com a faixa BASKETBALL, o poste da frente e a rede de proteção;
//  - entre as laterais, a prancha (a rampa preta com a quadra vermelha):
//    alta embaixo da cesta e descendo até a frente, por onde as bolas voltam;
//  - na frente, o console das bolas (a "Frente": BASKETBALL e POW!, e os
//    lados com o POW!), com as bolas na bandeja.
//
// As peças (cada uma vista DE FORA, ou de quem está dentro da pista, em pé):
//   lateral-externa-esquerda / -direita   o lado de fora, recortado no contorno
//   lateral-interna-esquerda / -direita   o lado de dentro, em L (alto atrás, baixo na frente)
//   prancha        a rampa, vista de quem joga (a cesta no alto da imagem)
//   fundo-cesta    o painel do fundo, atrás da cesta
//   teto-interno   o teto da parte alta, visto de baixo (a frente no alto da imagem)
//   testeira-frente, testeira-teto, testeira-lado   a testeira (o lado serve aos dois)
//   frente         a frente do console; frente-lateral, os lados dele (os dois)
//   faixa-rampa    a faixa do corrimão, em cima da parte baixa (os dois lados)
//   poste          a faixa do poste da frente, por fora (os dois)
// O tamanho de cada peça e o contorno vão para o pecas.json (o gerar.cjs grava).
//
// Coordenadas: as do three.js, em milímetros: x na largura (da esquerda para a
// direita de quem joga), y para cima, z no comprimento (a frente, o jogador,
// em +z). No fim tudo vira metros, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------- as medidas (mm) ----------
const ALT = 2700; // a altura, no alto da testeira
const XF = 500; // a face de fora (o adesivo): 1,00 m de largura
const ZT = -1200; // as costas
const ZF = 1200; // a frente do console: 2,40 m de comprimento
const ESP = 18; // o MDF
const PELE = 1; // o adesivo fica 1 mm fora da madeira (a medida de fora é a do adesivo)
const XM = XF - PELE - ESP; // 481: a face de dentro das laterais
const XI = XM - PELE; // 480: o adesivo de dentro (a pista vai de -480 a 480)
const ALTO = 2400; // o alto da parte alta (embaixo da testeira)
const TETO = ALTO - ESP - PELE; // 2381: o adesivo do teto interno
const Z_ALTO = -500; // a frente da parte alta (o teto interno vai até aqui)
const Z_FUNDO = ZT + ESP + PELE; // -1181: o adesivo do fundo da cesta
const TESTEIRA = { z0: -900, z1: -470 }; // a testeira, em cima da parte alta (sai 3 cm na frente)
const CONSOLE = { z0: 950, alto: 900, bandeja: 760 }; // o console das bolas, na frente
// a prancha: da frente (na beira do console) até o fundo, subindo
const RAMPA = { zFrente: CONSOLE.z0, yFrente: 780, inclinacao: 0.108 };
const rampa = (z) => RAMPA.yFrente + (RAMPA.zFrente - z) * RAMPA.inclinacao;
const PAREDE = 180; // a parte baixa sobe 18 cm acima da prancha, paralela a ela
const baixo = (z) => rampa(z) + PAREDE;
const CORRIMAO = { altura: 90, largura: 45 }; // o corrimão em cima da parte baixa
// a diagonal: a quina da parte alta (C1) e o encontro com a parte baixa (C2), com as curvas
const C1 = [-330, ALTO];
const C2 = [320, baixo(320)];
const CURVA = { alto: 170, baixo: 160 };
const POSTE = { z0: 890, z1: CONSOLE.z0, largura: 40, topo: 2016 }; // o poste da frente, que segura a rede
const REDE = 2000; // o alto da rede de proteção
const ARO = { y: 1950, raio: 150, z: Z_FUNDO + 30 + 150 + 12 }; // a cesta: o aro, na frente do fundo
const BOLA = 92; // o raio das bolas
// a resolução máxima de cada adesivo dentro do .glb (o lado maior, em px)
// (são 14 peças: somadas, as imagens ficam em ~0,5 MB; o .glb inteiro, abaixo de 800 KB)
const RESOLUCAO = {
  "lateral-externa-esquerda": 768, "lateral-externa-direita": 768, "lateral-interna-esquerda": 640, "lateral-interna-direita": 640,
  prancha: 768, "fundo-cesta": 576, "teto-interno": 384, frente: 576, "frente-lateral": 384,
  "testeira-frente": 896, "testeira-teto": 320, "testeira-lado": 256, "faixa-rampa": 512, poste: 320,
};
const QUALIDADE_JPEG = 0.74;

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
// a rede de proteção e a da cesta: a malha em losangos (o resto é transparente)
const malha = (cor, grossura) => tela(64, 64, (g, w, h) => {
  g.clearRect(0, 0, w, h);
  g.strokeStyle = cor;
  g.lineWidth = grossura;
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
  preto: material("mdf-preto", { color: "#141416", roughness: 0.55 }),
  borda: material("perfil-preto", { color: "#1f2024", roughness: 0.4, metalness: 0.3 }),
  aro: material("aro", { color: "#ef4b1f", roughness: 0.4, metalness: 0.45 }),
  suporte: material("suporte-da-cesta", { color: "#c9ced6", roughness: 0.35, metalness: 0.6 }),
  redeCesta: material("rede-da-cesta", { color: "#ffffff", map: malha("#ffffff", 7), alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.8 }),
  redeProtecao: material("rede-de-protecao", { color: "#ffffff", map: malha("#26272b", 3), alphaTest: 0.4, side: THREE.DoubleSide, roughness: 0.9 }),
  bolas: material("bolas", { map: texBola, roughness: 0.75 }),
};

// ---------- os adesivos: um arquivo por peça ----------
const PECAS = {}; // o que vai para o pecas.json
const avisos = [];
function imagem(arquivo) {
  return new Promise((ok, falha) => {
    const i = new Image();
    i.onload = () => ok(i);
    i.onerror = () => falha(new Error(arquivo));
    i.src = arquivo;
  });
}
// o material de um adesivo: a imagem da peça, esticada no tamanho dela (mm) e
// reduzida para caber no .glb; sem o arquivo, uma cor lisa (e o aviso)
async function adesivo(peca, mm, onde, { contorno = null, brilho = 0 } = {}) {
  const arquivo = `adesivos/${peca}.png`;
  if (!PECAS[peca]) PECAS[peca] = { arquivo, mm: mm.map((v) => Math.round(v)), onde, ...(contorno ? { contorno } : {}) };
  const nome = `adesivo-${peca}`;
  if (pecas.has(nome)) return nome; // a mesma peça nos dois lados: um material só
  const escala = (RESOLUCAO[peca] || 512) / Math.max(...mm);
  const c = document.createElement("canvas");
  c.width = Math.max(8, Math.round(mm[0] * escala));
  c.height = Math.max(8, Math.round(mm[1] * escala));
  const g = c.getContext("2d");
  try {
    const i = await imagem(`${arquivo}?v=${Date.now()}`);
    g.imageSmoothingQuality = "high";
    g.drawImage(i, 0, 0, c.width, c.height);
    const proporcao = i.width / i.height / (mm[0] / mm[1]);
    if (Math.abs(proporcao - 1) > 0.04) avisos.push(`${arquivo}: a imagem tem ${i.width} x ${i.height} px, fora da proporção da peça (${PECAS[peca].mm.join(" x ")} mm); foi esticada`);
  } catch {
    g.fillStyle = "#8a93a3";
    g.fillRect(0, 0, c.width, c.height);
    avisos.push(`${arquivo} não existe: a peça ficou cinza`);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  t.userData.mimeType = "image/jpeg"; // no .glb, em JPEG (como os adesivos do Strike Kids)
  // a testeira é acesa (o letreiro com a luz por trás)
  const luz = brilho ? { emissive: "#ffffff", emissiveMap: t, emissiveIntensity: brilho } : {};
  return material(nome, { map: t, roughness: 0.5, ...luz });
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
// o adesivo de uma face: o contorno (ou o retângulo) da peça; a imagem cobre
// o retângulo `ret` [a0, b0, a1, b1] e o contorno corta o resto
function colar(nome, pontos, b, ret) {
  const g = new THREE.ShapeGeometry(forma(pontos));
  const pos = g.attributes.position;
  const uv = g.attributes.uv;
  for (let i = 0; i < pos.count; i++) {
    uv.setXY(i, (pos.getX(i) - ret[0]) / (ret[2] - ret[0]), (pos.getY(i) - ret[1]) / (ret[3] - ret[1]));
  }
  por(nome, g, b.matriz());
}
const retangulo = (a0, b0, a1, b1) => [[a0, b0], [a1, b0], [a1, b1], [a0, b1]];
const ret = (pontos) => [Math.min(...pontos.map((p) => p[0])), Math.min(...pontos.map((p) => p[1])), Math.max(...pontos.map((p) => p[0])), Math.max(...pontos.map((p) => p[1]))];
// o contorno no pecas.json: em frações da imagem (0 a 1), a partir do canto de cima à esquerda
const contornoDaImagem = (pontos, r) => pontos.map(([a, b]) => [
  +((a - r[0]) / (r[2] - r[0])).toFixed(4), +(1 - (b - r[1]) / (r[3] - r[1])).toFixed(4),
]);
// um retângulo colado (a peça inteira), com a placa atrás, quando houver
async function retanguloColado(peca, b, largura, altura, onde, opcoes = {}) {
  const m = await adesivo(peca, [largura, altura], onde, opcoes);
  colar(m, retangulo(0, 0, largura, altura), b, [0, 0, largura, altura]);
}
// os dois lados: "esquerda" em -x (visto de fora, a frente fica à direita) e "direita" em +x
const LADOS = { esquerda: -1, direita: 1 };
// a base de um plano de pé no lado `s` (-1 ou 1), na altura x = s * x: de fora
// (normal para fora) ou de dentro (normal para a pista)
const deLado = (s, x, deFora = true) => {
  const U = deFora === (s < 0) ? V(0, 0, 1) : V(0, 0, -1);
  return { b: base(V(s * x, 0, 0), U, V(0, 1, 0)), a: (z) => (U.z > 0 ? z : -z) };
};

/* ======================================================================
   1. AS LATERAIS: o contorno (a parte alta, a diagonal em curva e a parte
   baixa), o adesivo de fora e o de dentro (em L)
   ====================================================================== */
// o contorno de fora, no plano (z, y): das costas até a frente do console
const CONTORNO = (() => {
  const pts = [[ZT, 0], [CONSOLE.z0, 0], [CONSOLE.z0, baixo(CONSOLE.z0)]];
  const d = new THREE.Vector2(C2[0] - C1[0], C2[1] - C1[1]).normalize(); // a diagonal, descendo para a frente
  const e = new THREE.Vector2(CONSOLE.z0 - C2[0], baixo(CONSOLE.z0) - C2[1]).normalize(); // a parte baixa, para a frente
  const curva = (p0, p1, p2, n = 12) => {
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      pts.push([(1 - t) ** 2 * p0[0] + 2 * t * (1 - t) * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * t * (1 - t) * p1[1] + t * t * p2[1]]);
    }
  };
  // da frente para trás: a parte baixa, a curva de baixo, a diagonal, a curva de cima e o alto
  curva([C2[0] + CURVA.baixo * e.x, C2[1] + CURVA.baixo * e.y], C2, [C2[0] - CURVA.baixo * d.x, C2[1] - CURVA.baixo * d.y]);
  curva([C1[0] + CURVA.alto * d.x, C1[1] + CURVA.alto * d.y], C1, [C1[0] - CURVA.alto, C1[1]], 16);
  pts.push([ZT, ALTO]);
  return pts;
})();
// onde a diagonal passa numa altura (para a rede)
const naDiagonal = (y) => C1[0] + ((C1[1] - y) * (C2[0] - C1[0])) / (C1[1] - C2[1]);
// o L de dentro: da prancha para cima; alto atrás (até o teto), baixo na frente (até o corrimão)
const L_DENTRO = [
  [CONSOLE.z0, rampa(CONSOLE.z0)], [CONSOLE.z0, baixo(CONSOLE.z0)], [Z_ALTO, baixo(Z_ALTO)],
  [Z_ALTO, TETO], [Z_FUNDO, TETO], [Z_FUNDO, rampa(Z_FUNDO)],
];
for (const [lado, s] of Object.entries(LADOS)) {
  // de fora
  const fora = deLado(s, XF, true);
  const pts = CONTORNO.map(([z, y]) => [fora.a(z), y]);
  placa(M.preto, pts, fora.b, ESP);
  const r = ret(pts);
  const m = await adesivo(`lateral-externa-${lado}`, [r[2] - r[0], r[3] - r[1]], `o lado de fora da ${lado} (vista de fora, recortada no contorno)`, { contorno: contornoDaImagem(pts, r) });
  colar(m, pts, fora.b, r);
  // de dentro (de quem está na pista)
  const dentro = deLado(s, XI, false);
  const ptsL = L_DENTRO.map(([z, y]) => [dentro.a(z), y]);
  const rL = ret(ptsL);
  const mL = await adesivo(`lateral-interna-${lado}`, [rL[2] - rL[0], rL[3] - rL[1]], `o lado de dentro da ${lado}, em L (visto da pista)`, { contorno: contornoDaImagem(ptsL, rL) });
  colar(mL, ptsL, dentro.b, rL);
}

/* ======================================================================
   2. A PARTE ALTA: as costas, o fundo da cesta, o teto interno e a testeira
   ====================================================================== */
caixa(M.preto, -XM, XM, 0, ALTO, ZT, ZT + ESP); // as costas
caixa(M.preto, -XM, XM, ALTO - ESP, ALTO, ZT, Z_ALTO); // o tampo de cima (o teto)
await retanguloColado("fundo-cesta", base(V(-XI, rampa(Z_FUNDO), Z_FUNDO), V(1, 0, 0), V(0, 1, 0)), 2 * XI, TETO - rampa(Z_FUNDO),
  "o painel do fundo, atrás da cesta (da prancha até o teto)");
// o teto, visto de baixo por quem joga: a frente no alto da imagem
await retanguloColado("teto-interno", base(V(-XI, TETO, Z_FUNDO), V(1, 0, 0), V(0, 0, 1)), 2 * XI, Z_ALTO - Z_FUNDO,
  "o teto da parte alta, visto de baixo (a frente no alto da imagem)");
{
  const { z0, z1 } = TESTEIRA;
  caixa(M.preto, -XF + PELE, XF - PELE, ALTO, ALT - PELE, z0 + PELE, z1 - PELE);
  await retanguloColado("testeira-frente", base(V(-XF, ALTO, z1), V(1, 0, 0), V(0, 1, 0)), 2 * XF, ALT - ALTO,
    "a frente da testeira (o letreiro, aceso)", { brilho: 0.35 });
  await retanguloColado("testeira-teto", base(V(-XF, ALT, z1), V(1, 0, 0), V(0, 0, -1)), 2 * XF, z1 - z0,
    "o alto da testeira, visto de cima (a frente embaixo da imagem)");
  for (const s of Object.values(LADOS)) {
    const b = s < 0 ? base(V(-XF, ALTO, z0), V(0, 0, 1), V(0, 1, 0)) : base(V(XF, ALTO, z1), V(0, 0, -1), V(0, 1, 0));
    await retanguloColado("testeira-lado", b, z1 - z0, ALT - ALTO, "os dois lados da testeira (a mesma peça), vistos de fora");
  }
}

/* ======================================================================
   3. A CESTA: o suporte, o aro e a rede
   ====================================================================== */
{
  const { y, raio, z } = ARO;
  caixa(M.suporte, -150, 150, y - 170, y + 30, Z_FUNDO, Z_FUNDO + 12); // a chapa no fundo
  for (const lado of [-1, 1]) {
    const a = 0.8; // os braços pegam o aro a ±46° da parte de trás
    cilindro(M.suporte, V(lado * 110, y, Z_FUNDO + 12), V(lado * raio * Math.sin(a), y, z - raio * Math.cos(a)), 9, 8);
  }
  cilindro(M.suporte, V(0, y - 150, Z_FUNDO + 12), V(0, y, z - raio), 9, 8);
  const aro = new THREE.TorusGeometry(raio, 10, 10, 48);
  aro.rotateX(PI / 2);
  por(M.aro, aro, new THREE.Matrix4().makeTranslation(0, y, z));
  const rede = new THREE.CylinderGeometry(raio - 5, raio * 0.62, 280, 32, 1, true);
  const uv = rede.attributes.uv;
  for (let k = 0; k < uv.count; k++) uv.setXY(k, uv.getX(k) * 8, uv.getY(k) * 1.6);
  por(M.redeCesta, rede, new THREE.Matrix4().makeTranslation(0, y - 140, z));
}

/* ======================================================================
   4. A PRANCHA: a rampa entre as laterais, da cesta até o console
   ====================================================================== */
{
  const comprimento = Math.hypot(RAMPA.zFrente - Z_FUNDO, rampa(Z_FUNDO) - rampa(RAMPA.zFrente));
  const sobe = new THREE.Vector3(0, rampa(Z_FUNDO) - rampa(RAMPA.zFrente), Z_FUNDO - RAMPA.zFrente).normalize(); // para a cesta
  const b = base(V(-XI, rampa(RAMPA.zFrente), RAMPA.zFrente), V(1, 0, 0), sobe);
  placa(M.preto, retangulo(0, 0, 2 * XI, comprimento), b, ESP);
  await retanguloColado("prancha", b, 2 * XI, comprimento, "a rampa, vista de quem joga (a cesta no alto da imagem)");
  // duas bolas voltando pela rampa
  for (const [x, t] of [[-180, 0.32], [210, 0.55]]) {
    const p = b.origem.clone().addScaledVector(b.U, XI + x).addScaledVector(sobe, comprimento * t).addScaledVector(b.N, BOLA);
    por(M.bolas, new THREE.SphereGeometry(BOLA, 16, 12), new THREE.Matrix4().makeTranslation(p.x, p.y, p.z));
  }
}

/* ======================================================================
   5. A PARTE BAIXA: o corrimão com a faixa, o poste e a rede de proteção
   ====================================================================== */
{
  const fimDaReta = C2[0] + CURVA.baixo * (CONSOLE.z0 - C2[0]) / Math.hypot(CONSOLE.z0 - C2[0], baixo(CONSOLE.z0) - C2[1]);
  const inicio = V(0, baixo(CONSOLE.z0), CONSOLE.z0); // a ponta da frente, em cima da parte baixa
  const fim = V(0, baixo(fimDaReta), fimDaReta);
  const ao = new THREE.Vector3().subVectors(fim, inicio); // da frente para trás, subindo
  const comprimento = ao.length();
  ao.normalize();
  const cima = V(0, ao.z, -ao.y).multiplyScalar(-1); // perpendicular, para cima
  if (cima.y < 0) cima.negate();
  const { altura, largura } = CORRIMAO;
  for (const [lado, s] of Object.entries(LADOS)) {
    // o corrimão: de x = s*500 para dentro, em cima da parte baixa
    const centro = inicio.clone().add(fim).multiplyScalar(0.5).addScaledVector(cima, altura / 2);
    centro.x = s * (XF - PELE - largura / 2);
    const g = new THREE.BoxGeometry(largura, altura, comprimento);
    const giro = new THREE.Matrix4().makeBasis(V(1, 0, 0), cima, ao.clone().negate());
    por(M.borda, g, giro.setPosition(centro));
    // a faixa do corrimão, por fora: de fora, a frente fica à direita no lado esquerdo
    const U = s < 0 ? ao.clone().negate() : ao.clone();
    const pontaEsquerda = s < 0 ? fim : inicio;
    const b = base(V(s * XF, pontaEsquerda.y, pontaEsquerda.z), U, cima);
    await retanguloColado("faixa-rampa", b, comprimento, altura, "a faixa do corrimão, em cima da parte baixa, vista de fora (os dois lados)");
    // o poste da frente, em cima do corrimão, e a faixa dele por fora
    const pe = baixo(POSTE.z0) + altura; // o alto do corrimão, no poste
    caixa(M.borda, s * (XF - PELE), s * (XF - PELE - POSTE.largura), pe - 20, POSTE.topo, POSTE.z0, POSTE.z1);
    const bp = s < 0 ? base(V(-XF, pe, POSTE.z0), V(0, 0, 1), V(0, 1, 0)) : base(V(XF, pe, POSTE.z1), V(0, 0, -1), V(0, 1, 0));
    await retanguloColado("poste", bp, POSTE.z1 - POSTE.z0, POSTE.topo - pe, "a faixa do poste da frente, do corrimão para cima, vista de fora (os dois lados)");
    // a rede: do corrimão até o alto, entre o poste e a diagonal (a ponta de
    // trás fica dentro da lateral); e o tubo de cima, do poste até a diagonal
    const xr = s * (XF - PELE - ESP / 2);
    const pRede = [
      [POSTE.z0 + 20, baixo(POSTE.z0) + altura - 25], [POSTE.z0 + 20, REDE], [naDiagonal(REDE) - 40, REDE],
      [C2[0] - 60, C2[1] - 40], [fimDaReta + 10, baixo(fimDaReta) + altura - 25],
    ];
    const gRede = new THREE.ShapeGeometry(forma(pRede));
    const uv = gRede.attributes.uv;
    const pos = gRede.attributes.position;
    for (let k = 0; k < uv.count; k++) uv.setXY(k, pos.getX(k) / 70, pos.getY(k) / 70); // um losango a cada 7 cm
    por(M.redeProtecao, gRede, new THREE.Matrix4().makeBasis(V(0, 0, 1), V(0, 1, 0), V(-1, 0, 0)).setPosition(xr, 0, 0));
    const xt = s * (XF - PELE - 14); // o tubo, rente à face de fora
    cilindro(M.borda, V(xt, REDE, POSTE.z1 - 10), V(xt, REDE, naDiagonal(REDE) - 15), 14, 12);
  }
}

/* ======================================================================
   6. O CONSOLE DA FRENTE: a caixa das bolas, a bandeja e as bolas
   ====================================================================== */
{
  const { z0, alto, bandeja } = CONSOLE;
  caixa(M.preto, -XF + PELE, XF - PELE, 0, alto, ZF - PELE - ESP, ZF - PELE); // a frente
  for (const s of Object.values(LADOS)) caixa(M.preto, s * (XF - PELE), s * (XF - PELE - ESP), 0, alto, z0, ZF - PELE);
  caixa(M.preto, -XM, XM, bandeja - ESP, bandeja, z0, ZF - PELE - ESP); // o fundo da bandeja
  caixa(M.borda, -XM, XM, alto - 10, alto + 12, ZF - PELE - ESP - 6, ZF - PELE + 0.5); // o friso da beira
  await retanguloColado("frente", base(V(-XF, 0, ZF), V(1, 0, 0), V(0, 1, 0)), 2 * XF, alto, "a frente do console (o lado de quem joga)");
  for (const s of Object.values(LADOS)) {
    const b = s < 0 ? base(V(-XF, 0, z0), V(0, 0, 1), V(0, 1, 0)) : base(V(XF, 0, ZF), V(0, 0, -1), V(0, 1, 0));
    await retanguloColado("frente-lateral", b, ZF - z0, alto, "os dois lados do console, vistos de fora (a mesma peça)");
  }
  // as bolas na bandeja
  for (const x of [-290, -95, 100, 295]) {
    por(M.bolas, new THREE.SphereGeometry(BOLA, 16, 12), new THREE.Matrix4().makeTranslation(x, bandeja + BOLA, (z0 + ZF) / 2 - 15));
  }
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
// as redes não fazem sombra cheia
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
  // texturas desenhadas aqui (as redes, a bola) seguem em PNG.
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
