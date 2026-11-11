// Monta o Air Game Kids Alienígenas em three.js e exporta um .glb.
//
// A mesa de air hockey infantil do Air Game Kids (0,90 m x 0,86 m x 1,50 m),
// com os adesivos dos alienígenas (o HOCKEY KIDS, os alienígenas astronautas,
// o disco voador, os planetas e o chão lunar laranja). TUDO sai da folha de
// adesivos da fábrica (folha-adesivos.webp, a 26567-1): a arte de cada peça
// (adesivos/<peça>.png) e o desenho dela (formas.json: o tamanho em px e, nas
// laterais, o CONTORNO de verdade), que o recortar_adesivos.py tira da folha.
// Nada da arte é redesenhado: cada imagem vai inteira na sua face, e a face
// tem a forma e a proporção da peça.
//
// A folha é desenhada em ESCALA (as peças encaixam umas nas outras: as
// laterais são 33 px mais compridas que o tampo, a cabeceira 7 px mais larga):
// uma escala só (mm por px da folha) dá a mesa inteira. Ela sai da altura do
// Air Game Kids, 0,90 m (com a fita de LED), que é a das laterais (o alto da
// corcova do meio). Daí: 1,51 m de comprimento (o 1,50 m do Air Game Kids), o
// tampo de 1,40 m x 0,80 m, o campo a 0,75 m do chão e 0,83 m de largura (os
// 0,86 m do catálogo contam a borda).
//
// As peças (cada uma vista DE FORA, em pé, como na folha):
//   tampo               o tampo, deitado: a cabeceira do "Jogador 02" (a de
//                       trás) à esquerda da imagem, a do "Jogador 01" (a da
//                       frente) à direita; o alto da imagem é o lado direito
//   lateral-esquerda    as laterais compridas, com o contorno recortado da folha
//   lateral-direita     (a corcova em cima, os dois pés embaixo)
//   lateral-esquerda-2  a cabeceira de trás (a da esquerda do tampo, na folha)
//   lateral-direita-2   a cabeceira da frente
//
// Conferido com a foto do Air Game Kids do catálogo (lazersport.com.br/brinquedo/40):
// a forma das laterais, os pés (os da própria lateral), o tampo entre elas e,
// o que a folha não desenha e a mesa tem: a fita de LED colorida na borda das
// laterais (o contorno inteiro, menos onde pisa no chão), a régua preta das
// pontas e a borda preta dos lados, em cima do tampo, e o placar branco no
// alto da corcova, por dentro da lateral direita.
//
// Coordenadas: as do three.js, em milímetros: x na largura (da esquerda para a
// direita de quem joga na frente), y para cima, z no comprimento (a frente, a
// cabeceira do Jogador 01, em +z). No fim tudo vira metros, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const FORMAS = await (await fetch(`formas.json?v=${Date.now()}`)).json();

// ---------- a escala da folha e as medidas (mm) ----------
const LED = 6; // a fita de LED na borda das laterais (mm para fora do contorno)
const ALT = 900 - LED; // a altura do Air Game Kids (0,90 m): o alto das laterais, mais a fita de LED
const ESP = 18; // o MDF das cabeceiras e do tampo
const PELE = 1; // o adesivo fica 1 mm fora da madeira
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
// a escala: as laterais (o contorno) têm a altura da mesa
const S = ALT / emMm("lateral-direita", 1).altura; // mm por px da folha (~3,06)
const LATERAIS = { esquerda: emMm("lateral-esquerda", S), direita: emMm("lateral-direita", S) };
const TAMPO = emMm("tampo", S); // ~1411 x 808
// as laterais: a cabeceira é 7 px mais larga que o tampo (3,5 px de cada lado, ~11 mm)
const ESP_LAT = Math.round(((FORMAS["lateral-esquerda-2"].px[0] - FORMAS.tampo.px[1]) / 2) * S);
const XD = TAMPO.altura / 2; // a face de dentro das laterais: o tampo vai de uma à outra
const XF = XD + ESP_LAT + PELE; // o adesivo de fora das laterais
const ZT = TAMPO.largura / 2; // as pontas do tampo
// a cabeceira fica entre as laterais (as laterais passam dela): na largura do tampo,
// com a proporção da peça. Na folha ela vem com uma faixa azul lisa embaixo da arte
// (o recorte a tira: faixa_lisa_px); essa tábua não existe na mesa: a cabeceira é só
// a faixa da arte, logo abaixo do tampo, e embaixo dela a mesa é aberta entre os pés
// das laterais. A peça inteira da folha (com a faixa), em escala, dá a altura do campo.
const [CW, CH] = FORMAS["lateral-esquerda-2"].px;
const CAMPO = (2 * XD * (CH + (FORMAS["lateral-esquerda-2"].faixa_lisa_px || 0))) / CW; // a superfície de jogo
const alturaDaCabeceira = (peca) => (2 * XD * FORMAS[peca].px[1]) / FORMAS[peca].px[0]; // só a arte
const ZC = ZT + ESP + PELE; // o adesivo das cabeceiras
const BORDA = { altura: 27, largura: 20, gol: 200 }; // a régua das pontas, com o gol no meio (preta, como na mesa)
const BORDA_LADO = { altura: 22, largura: 14 }; // a borda preta dos lados, em cima do tampo, encostada nas laterais
// a resolução máxima de cada adesivo dentro do .glb (o lado maior, em px; a folha tem ~1/3)
const RESOLUCAO = { tampo: 1024, "lateral-esquerda": 1024, "lateral-direita": 1024, "lateral-esquerda-2": 640, "lateral-direita-2": 640 };
const QUALIDADE_JPEG = 0.85;

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

const COR = {
  azul: "#1d4f8f", // a pintura da mesa (a madeira atrás dos adesivos)
  borda: "#141519", // a régua das pontas e a borda dos lados (pretas, como na foto da mesa)
  boca: "#0d1420",
  soprador: "#3a3f48",
  grade: "#15181d",
  vermelho: "#e2232a",
  verde: "#2fbf4a",
  disco: "#151515",
};
const M = {
  pintura: material("pintura-azul", { color: COR.azul, roughness: 0.55 }),
  borda: material("borda", { color: COR.borda, roughness: 0.35 }),
  boca: material("boca-do-gol", { color: COR.boca, roughness: 0.9 }),
  soprador: material("soprador", { color: COR.soprador, roughness: 0.6, metalness: 0.3 }),
  grade: material("grade-do-soprador", { color: COR.grade, roughness: 0.8 }),
  rebatedorVermelho: material("rebatedor-vermelho", { color: COR.vermelho, roughness: 0.3 }),
  rebatedorVerde: material("rebatedor-verde", { color: COR.verde, roughness: 0.3 }),
  disco: material("disco", { color: COR.disco, roughness: 0.35 }),
  // a fita de LED da borda das laterais: as cores correndo pelo contorno (a da mesa é RGB)
  led: material("fita-de-led", (() => {
    const c = document.createElement("canvas");
    c.width = 256; c.height = 4;
    const g = c.getContext("2d");
    const grad = g.createLinearGradient(0, 0, 256, 0);
    ["#ff3fd8", "#9b4dff", "#3d6bff", "#29d3ff", "#3dff8a", "#d6ff3d", "#ff9f2e", "#ff3fd8"].forEach((cor, i, l) => grad.addColorStop(i / (l.length - 1), cor));
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 4);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return { color: "#ffffff", map: t, emissive: "#ffffff", emissiveMap: t, emissiveIntensity: 2.4, roughness: 0.3, side: THREE.DoubleSide };
  })()),
  placar: material("placar", { color: "#f4f5f7", roughness: 0.4 }),
  digitos: material("digitos-do-placar", { color: "#ff3030", emissive: "#ff1a1a", emissiveIntensity: 1.2, roughness: 0.4 }),
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
async function adesivo(peca, mm, onde) {
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
  if (Math.abs(proporcao - 1) > 0.01) avisos.push(`${peca}: a face tem outra proporção que a peça (${(100 * (proporcao - 1)).toFixed(1)}%)`);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  t.userData.mimeType = "image/jpeg"; // no .glb, em JPEG (como os adesivos do Strike Kids)
  return material(`adesivo-${peca}`, { map: t, roughness: 0.5 });
}

// ---------- peças básicas (em mm) ----------
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  por(nome, new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0)),
    new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function cilindro(nome, x, y0, y1, z, r, lados = 32) {
  por(nome, new THREE.CylinderGeometry(r, r, y1 - y0, lados), new THREE.Matrix4().makeTranslation(x, (y0 + y1) / 2, z));
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
// [a0, b0, a1, b1] (o da peça inteira) e o contorno corta o resto
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

/* ======================================================================
   1. AS LATERAIS COMPRIDAS: o contorno de verdade de cada uma (a da folha)
   ====================================================================== */
const LADOS = {
  esquerda: base(V(-XF, 0, 0), V(0, 0, 1), V(0, 1, 0)), // de fora (-x): a frente fica à direita
  direita: base(V(XF, 0, 0), V(0, 0, -1), V(0, 1, 0)), // de fora (+x): a frente fica à esquerda
};
for (const [lado, b] of Object.entries(LADOS)) {
  const { pontos, ret, largura } = LATERAIS[lado];
  // centralizada no comprimento: a vai de -largura/2 a largura/2
  const pts = pontos.map(([a, y]) => [a - largura / 2, y]);
  const pts0 = pts;
  const r = [ret[0] - largura / 2, ret[1], ret[2] - largura / 2, ret[3]];
  {
    // a placa (embaixo do adesivo): o contorno sem os degraus dos pixels (o adesivo fica com o de verdade)
    const r = (linha, tol) => {
      if (linha.length < 3) return linha;
      const [a, z] = [linha[0], linha[linha.length - 1]];
      const [dx, dy] = [z[0] - a[0], z[1] - a[1]];
      const L = Math.hypot(dx, dy) || 1e-9;
      let pior = 0, k = 0;
      for (let i = 1; i < linha.length - 1; i++) {
        const d = Math.abs(dy * (linha[i][0] - a[0]) - dx * (linha[i][1] - a[1])) / L;
        if (d > pior) { pior = d; k = i; }
      }
      return pior <= tol ? [a, z] : r(linha.slice(0, k + 1), tol).slice(0, -1).concat(r(linha.slice(k), tol));
    };
    const d = (q) => Math.hypot(q[0] - pts[0][0], q[1] - pts[0][1]);
    const longe = pts.reduce((m, q, k) => (d(q) > d(pts[m]) ? k : m), 0);
    placa(M.pintura, [...r(pts.slice(0, longe + 1), 2).slice(0, -1), ...r([...pts.slice(longe), pts[0]], 2).slice(0, -1)], b, ESP_LAT);
  }
  const m = await adesivo(`lateral-${lado}`, [r[2] - r[0], r[3] - r[1]], `a lateral comprida da ${lado}, vista de fora (o contorno da folha)`);
  colar(m, pts, b, r);
  // a fita de LED: na face da borda (a espessura da lateral), pelo contorno
  // inteiro (sem os degraus dos pixels), menos o pé que pisa no chão; a mesa
  // fica na medida (a altura conta a fita)
  {
    const simplificar = (linha, tol) => {
      if (linha.length < 3) return linha;
      const [a, z] = [linha[0], linha[linha.length - 1]];
      const [dx, dy] = [z[0] - a[0], z[1] - a[1]];
      const L = Math.hypot(dx, dy) || 1e-9;
      let pior = 0, k = 0;
      for (let i = 1; i < linha.length - 1; i++) {
        const d = Math.abs(dy * (linha[i][0] - a[0]) - dx * (linha[i][1] - a[1])) / L;
        if (d > pior) { pior = d; k = i; }
      }
      return pior <= tol ? [a, z] : simplificar(linha.slice(0, k + 1), tol).slice(0, -1).concat(simplificar(linha.slice(k), tol));
    };
    // o polígono fechado: partido no ponto mais longe do primeiro, cada metade simplificada
    const longe = pts0.reduce((m, q, k) => (Math.hypot(q[0] - pts0[0][0], q[1] - pts0[0][1]) > Math.hypot(pts0[m][0] - pts0[0][0], pts0[m][1] - pts0[0][1]) ? k : m), 0);
    const pts = [...simplificar(pts0.slice(0, longe + 1), 3.5).slice(0, -1), ...simplificar([...pts0.slice(longe), pts0[0]], 3.5).slice(0, -1)];
    const n = pts.length;
    const area = pts.reduce((s, [a, y], k) => s + a * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * y, 0);
    const comp = pts.map(([a, y], k) => Math.hypot(pts[(k + 1) % n][0] - a, pts[(k + 1) % n][1] - y));
    const total = comp.reduce((s, c) => s + c, 0);
    const pos = [], uv = [], idx = [];
    let feito = 0;
    for (let k = 0; k < n; k++) {
      const [a0, y0] = pts[k];
      const [a1, y1] = pts[(k + 1) % n];
      const u0 = feito / total;
      feito += comp[k];
      if (Math.max(y0, y1) < 8) continue; // o pé no chão
      // a fita de LED, LED mm para fora da borda (a normal para fora do contorno),
      // na espessura da lateral
      let na = y1 - y0, nb = -(a1 - a0);
      if (area < 0) { na = -na; nb = -nb; }
      const L = Math.hypot(na, nb) || 1;
      const ponto = (a, y, fora, d) => b.origem.clone()
        .addScaledVector(b.U, a + (na / L) * fora).addScaledVector(b.W, Math.max(0.5, y + (nb / L) * fora)).addScaledVector(b.N, d);
      const [dFora, dDentro] = [-0.2, -PELE - ESP_LAT + 0.2];
      const u1 = feito / total;
      for (const [f0, d0, f1, d1] of [[LED, dFora, LED, dDentro]]) { // a face de fora da fita (a que acende)
        const i0 = pos.length / 3;
        for (const [a, y, u] of [[a0, y0, u0], [a1, y1, u1]]) {
          for (const [f, d] of [[f0, d0], [f1, d1]]) {
            const q = ponto(a, y, f, d);
            pos.push(q.x, q.y, q.z);
            uv.push(u, 0.5);
          }
        }
        idx.push(i0, i0 + 1, i0 + 2, i0 + 1, i0 + 3, i0 + 2);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    por(M.led, g);
  }
}

/* ======================================================================
   2. AS CABECEIRAS: entre as laterais, a faixa da arte logo abaixo do campo
      (embaixo, a mesa é aberta: nada de tábua até o chão)
   ====================================================================== */
// a de trás é a "lateral esquerda 2" (à esquerda do tampo, na folha); a da frente, a "direita 2"
const CABECEIRAS = {
  "lateral-esquerda-2": { z: -ZC, b: base(V(XD, 0, -ZC), V(-1, 0, 0), V(0, 1, 0)), onde: "a cabeceira de trás (a do Jogador 02), vista de fora" },
  "lateral-direita-2": { z: ZC, b: base(V(-XD, 0, ZC), V(1, 0, 0), V(0, 1, 0)), onde: "a cabeceira da frente (a do Jogador 01), vista de fora" },
};
for (const [peca, { z, b, onde }] of Object.entries(CABECEIRAS)) {
  const baixo = CAMPO - alturaDaCabeceira(peca);
  caixa(M.pintura, -XD, XD, baixo, CAMPO - PELE, z - Math.sign(z) * (ESP + PELE), z - Math.sign(z) * PELE);
  const m = await adesivo(peca, [2 * XD, CAMPO - baixo], onde);
  colar(m, retangulo(0, baixo, 2 * XD, CAMPO), b, [0, baixo, 2 * XD, CAMPO]);
}

/* ======================================================================
   3. O TAMPO: a prancha com o adesivo, a régua das pontas e as bocas do gol
   ====================================================================== */
caixa(M.pintura, -XD, XD, CAMPO - 25, CAMPO - PELE, -ZT, ZT);
{
  // de cima, com a frente (+z) à direita: o alto da imagem é o lado direito (+x)
  const b = base(V(0, CAMPO, -ZT), V(0, 0, 1), V(1, 0, 0));
  const m = await adesivo("tampo", [2 * ZT, 2 * XD], "o tampo, de cima: a cabeceira do Jogador 02 (a de trás) à esquerda, o lado direito da mesa no alto");
  colar(m, retangulo(0, -XD, 2 * ZT, XD), b, [0, -XD, 2 * ZT, XD]);
}
// a caixa de ar embaixo do tampo e o soprador
caixa(M.pintura, -XD, XD, CAMPO - 170, CAMPO - 25, -ZT, ZT);
caixa(M.soprador, -200, 200, CAMPO - 270, CAMPO - 170, -240, 240);
cilindro(M.grade, 0, CAMPO - 280, CAMPO - 270, 0, 130, 40);
{
  // a régua de cada ponta, sobre a beira de fora da moldura (o "Jogador" fica
  // mais para dentro), com o vão do gol no meio e a boca escura
  const { altura, largura, gol } = BORDA;
  for (const s of [-1, 1]) {
    const zFora = s * ZT;
    const zDentro = s * (ZT - largura);
    caixa(M.borda, -XD, -gol / 2, CAMPO, CAMPO + altura, zDentro, zFora);
    caixa(M.borda, gol / 2, XD, CAMPO, CAMPO + altura, zDentro, zFora);
    caixa(M.boca, -gol / 2, gol / 2, CAMPO, CAMPO + 1.5, zDentro, zFora);
  }
  // a borda dos lados: encostada nas laterais, de ponta a ponta, entre as réguas
  for (const s of [-1, 1]) {
    caixa(M.borda, s * (XD - BORDA_LADO.largura), s * XD, CAMPO, CAMPO + BORDA_LADO.altura, -ZT + largura, ZT - largura);
  }
}
// o placar: a caixinha branca no alto da corcova, por dentro da lateral direita, com os dois pontos acesos
{
  const alto = ALT - 30; // logo abaixo do alto da corcova
  caixa(M.placar, XD - 36, XD, alto - 60, alto, -70, 70);
  for (const z of [-38, 8]) caixa(M.digitos, XD - 37, XD - 36, alto - 45, alto - 15, z, z + 30);
}

/* ======================================================================
   4. OS REBATEDORES E O DISCO, em cima do campo
   ====================================================================== */
function rebatedor(nome, z) {
  const perfil = [ // o meio perfil, girado em volta do eixo: a base larga, o pescoço e a pega
    [0, 0], [43, 0], [45, 3], [45, 13], [40, 18], [22, 22], [17, 27], [16, 52], [20, 58], [22, 65], [19, 72], [11, 77], [0, 78],
  ].map(([r, y]) => new THREE.Vector2(r * 0.9, y * 0.9)); // os da mesa infantil
  por(nome, new THREE.LatheGeometry(perfil, 40), new THREE.Matrix4().makeTranslation(0, CAMPO + 0.5, z));
}
rebatedor(M.rebatedorVermelho, ZT - 270);
rebatedor(M.rebatedorVerde, -ZT + 270);
cilindro(M.disco, -100, CAMPO + 0.5, CAMPO + 5.5, 125, 25, 32);

/* ======================================================================
   MONTAGEM FINAL: metros, junta por material, centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "air-game-kids-alienigenas";
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
  const malha = new THREE.Mesh(g, mat);
  malha.name = nome;
  raiz.add(malha);
}
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 1000) / 1000);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
window.pecas = PECAS;
window.avisos = avisos;
window.escala = { mm_por_px: +S.toFixed(4), campo: Math.round(CAMPO), tampo: [Math.round(2 * ZT), Math.round(2 * XD)] };

// ---------- vistas para conferir e as fotos do cadastro ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1600, 1000);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.append(renderer.domElement);
cena.add(new THREE.HemisphereLight("#ffffff", "#8b95a5", 1.7));
const sol = new THREE.DirectionalLight("#ffffff", 2.0);
sol.position.set(3, 8, 5);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 1, far: 30 });
sol.shadow.bias = -0.0004;
cena.add(sol);
raiz.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
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
window.ver = (x, y, z, alvo = [0, 0.6, 0], fundo = "#0b1a3a", fov = 34, sombra = true) => {
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
// de cima, sem perspectiva (a frente para baixo, como quem joga na frente vê)
window.verCima = (largura = 3, fundo = "#0b1a3a") => {
  cena.background = new THREE.Color(fundo);
  piso.visible = fundo === "#0b1a3a";
  chao.visible = false;
  const alto = (largura * 1000) / 1600;
  const orto = new THREE.OrthographicCamera(-largura / 2, largura / 2, alto / 2, -alto / 2, 0.1, 100);
  orto.position.set(0, 20, 0);
  orto.up.set(1, 0, 0); // o comprimento na horizontal: a frente à direita
  orto.lookAt(0, 0, 0);
  renderer.render(cena, orto);
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
  // qualidade (a do Chromium é 0,92); aqui ela fica na QUALIDADE_JPEG
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
