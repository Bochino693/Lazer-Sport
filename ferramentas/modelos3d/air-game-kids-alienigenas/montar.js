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
// tampo de 1,40 m x 0,80 m e o campo a 0,75 m do chão; com as laterais de MDF
// grosso, os 0,86 m de largura do catálogo.
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
// EM ALTA DEFINIÇÃO (LEIA-ME V10, seção 92; o que as máquinas de adesivo dividem
// está em ../comum3d.js): os adesivos ampliados 4x com nitidez (adesivos-hd/), em
// vinil laminado brilhante (KHR_materials_clearcoat); as laterais em MDF de 25 mm
// com a borda arredondada -- a mesa fica com os 0,86 m de largura do cadastro (a
// folha dava 0,83 m com as laterais finas de 11 mm) --, a fita de LED e o placar
// acesos (emissiveStrength). Os nomes dos materiais e das malhas são os de antes.
//
// OS DOIS ADESIVOS DO AIR GAME KIDS SAEM DAQUI, com o MESMO móvel (a mesma
// geometria, a mesma medida): ?arte=astronautas usa as artes de
// ../air-game-kids-astronautas/adesivos(-hd)/ e grava o air-game-kids-astronautas.glb
// (node ../gerar_glb.cjs air-game-kids-alienigenas --arte astronautas --saida air-game-kids-astronautas.glb).
//
// Coordenadas: as do three.js, em milímetros: x na largura (da esquerda para a
// direita de quem joga na frente), y para cima, z no comprimento (a frente, a
// cabeceira do Jogador 01, em +z). No fim tudo vira metros, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "/vendor/three/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "/vendor/three/BufferGeometryUtils.js";
import * as C from "../comum3d.js";

// a arte: a dos alienígenas (esta pasta) ou a dos astronautas (a pasta ao lado)
const ARTE = new URLSearchParams(location.search).get("arte") || "alienigenas";
const PASTA_DA_ARTE = ARTE === "astronautas" ? "../air-game-kids-astronautas/" : "";
// nos astronautas, as duas laterais são a mesma arte (a da foto, desentortada)
const ARQUIVO_DA_PECA = ARTE === "astronautas" ? { "lateral-direita": "lateral-esquerda" } : {};

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const FORMAS = await (await fetch(`formas.json?v=${Date.now()}`)).json();

// ---------- a escala da folha e as medidas (mm) ----------
const LED = 6; // a fita de LED na borda das laterais (mm para fora do contorno)
const ALT = 900 - LED; // a altura do Air Game Kids (0,90 m): o alto das laterais, mais a fita de LED
const ESP = 18; // o MDF das cabeceiras e do tampo
const PELE = 1; // o adesivo fica 1 mm fora da madeira
const RAIO = 6; // a borda arredondada das laterais
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
// as laterais: MDF grosso (na folha a cabeceira é só 7 px mais larga que o tampo, ~11 mm de
// cada lado, e a mesa ficava com 0,83 m); com as laterais de verdade (~28 mm), os 0,86 m do cadastro
const LARGURA = 860;
const ESP_LAT = Math.round(LARGURA / 2 - TAMPO.altura / 2 - PELE);
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
// a resolução máxima de cada adesivo dentro do .glb (o lado maior, em px: a peça HD inteira)
const RESOLUCAO = { tampo: 2048, "lateral-esquerda": 2048, "lateral-direita": 2048, "lateral-esquerda-2": 1280, "lateral-direita-2": 1280 };

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map(); // nome -> { material, geometrias: [] }
function material(nome, opcoes) {
  // `opcoes` é o material pronto (os do comum3d.js) ou as opções de um MeshPhysicalMaterial
  if (!pecas.has(nome)) {
    const m = opcoes && opcoes.isMaterial ? opcoes : new THREE.MeshPhysicalMaterial({ name: nome, roughness: 0.6, metalness: 0, ...opcoes });
    m.name = nome;
    pecas.set(nome, { material: m, geometrias: [] });
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
  // a pintura (laca) da madeira e as peças de plástico brilhante
  pintura: material("pintura-azul", { color: COR.azul, roughness: 0.4, clearcoat: 0.7, clearcoatRoughness: 0.15 }),
  borda: material("borda", { color: COR.borda, roughness: 0.3, clearcoat: 0.8, clearcoatRoughness: 0.1 }),
  boca: material("boca-do-gol", { color: COR.boca, roughness: 0.9 }),
  soprador: material("soprador", { color: COR.soprador, roughness: 0.45, metalness: 0.5 }),
  grade: material("grade-do-soprador", { color: COR.grade, roughness: 0.8 }),
  rebatedorVermelho: material("rebatedor-vermelho", { color: COR.vermelho, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.05 }),
  rebatedorVerde: material("rebatedor-verde", { color: COR.verde, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.05 }),
  disco: material("disco", { color: COR.disco, roughness: 0.3, clearcoat: 1 }),
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
    return new THREE.MeshStandardMaterial({ color: "#ffffff", map: t, emissive: "#ffffff", emissiveMap: t, emissiveIntensity: 2.8, roughness: 0.3, side: THREE.DoubleSide });
  })()),
  placar: material("placar", { color: "#f4f5f7", roughness: 0.3, clearcoat: 0.6 }),
  digitos: material("digitos-do-placar", C.aceso("digitos-do-placar", "#ff1a1a", 2.2)),
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
async function adesivo(peca, mm, onde, extra = {}) {
  const [w, h] = FORMAS[peca].px;
  const arquivo = ARQUIVO_DA_PECA[peca] || peca;
  const { textura: t, w: tw, h: th, hd } = await C.arte(PASTA_DA_ARTE, arquivo, { lado: RESOLUCAO[peca] || 1024, px: [w, h], avisos });
  PECAS[peca] = {
    arquivo: `${PASTA_DA_ARTE}${hd ? `adesivos-hd/${arquivo}.webp` : `adesivos/${arquivo}.png`}`, px_no_glb: [tw, th],
    mm: mm.map((v) => Math.round(v)), onde, ...(FORMAS[peca].contorno ? { contorno: true } : {}),
  };
  const proporcao = w / h / (mm[0] / mm[1]);
  if (Math.abs(proporcao - 1) > 0.01) avisos.push(`${peca}: a face tem outra proporção que a peça (${(100 * (proporcao - 1)).toFixed(1)}%)`);
  return material(`adesivo-${peca}`, C.vinil(`adesivo-${peca}`, t, extra));
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
  let adesivoDaLateral; // o contorno do adesivo: a face plana da chapa (o raio da borda fica de fora)
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
    const contorno = [...r(pts.slice(0, longe + 1), 1).slice(0, -1), ...r([...pts.slice(longe), pts[0]], 1).slice(0, -1)];
    por(M.pintura, C.placaArredondada(contorno, ESP_LAT, RAIO), b.matriz());
    adesivoDaLateral = C.recuar(C.limpar(contorno), RAIO + 0.5);
  }
  const m = await adesivo(`lateral-${lado}`, [r[2] - r[0], r[3] - r[1]], `a lateral comprida da ${lado}, vista de fora (o contorno da folha)`);
  colar(m, adesivoDaLateral, b, r);
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
      const [dFora, dDentro] = [-PELE - RAIO + 0.5, -PELE - ESP_LAT + RAIO - 0.5];
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
  const m = await adesivo("tampo", [2 * ZT, 2 * XD], "o tampo, de cima: a cabeceira do Jogador 02 (a de trás) à esquerda, o lado direito da mesa no alto",
    { roughness: 0.28, clearcoatRoughness: 0.03 });
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
const raiz = C.montarFinal(pecas, `air-game-kids-${ARTE}`, { mergeGeometries, mergeVertices });
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 1000) / 1000);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
window.pecas = PECAS;
window.avisos = avisos;
window.escala = { arte: ARTE, mm_por_px: +S.toFixed(4), campo: Math.round(CAMPO), tampo: [Math.round(2 * ZT), Math.round(2 * XD)], laterais_mm: ESP_LAT };

// ---------- as vistas de conferência (gerar_glb.cjs: v-*.jpg) e a exportação ----------
C.vistas(raiz);
window.vistasDeConferencia = {
  frente34: [[1.9, 1.5, 2.3], [0, 0.55, 0], 34],
  esquerda: [[-3.2, 0.9, 0.3], [0, 0.55, 0], 34],
  direita: [[3.2, 0.9, -0.3], [0, 0.55, 0], 34],
  cabeceira: [[0.4, 1.0, 3.4], [0, 0.5, 0], 34],
  tampo: [[0.01, 3.2, 0.6], [0, 0.6, 0], 34],
};
window.exportar = () => C.exportar(raiz, GLTFExporter);
window.pronto = true;
