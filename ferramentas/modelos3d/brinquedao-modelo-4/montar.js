// Monta o Brinquedão Modelo 4 (dois trechos em "Z": 12 m ao fundo e 9 m mais
// à frente e à direita, ligados por uma passagem) em three.js e exporta um .glb.
//
// De onde vem cada coisa:
//  - do .3ds da fábrica (estrutura.json, feito pelo extrair.py): TODOS os
//    tubos azuis, nas medidas do arquivo -- as colunas, as barras do piso do
//    andar de cima (2,55 m) e do corrimão de cima (3,51 m), os degraus da
//    escada da ponta esquerda (0,98 m e 2,18 m) e o piso do meio dela
//    (1,59 m), as barras de cima das quatro redes em V (3,27 m e 3,31 m), os
//    postes dos rolos (13,13 m), o quadro da piscina do tobogã (a borda a
//    0,43 m e o topo a 2,55 m) e o arco azul da entrada dela; e o disco solto
//    que marca o rolo amarelo em pé do trecho de 9 m;
//  - das imagens do projeto (o render em perspectiva, a vista de frente e a
//    planta): as cores e o resto -- os pisos amarelos (trecho de 12 m e a
//    passagem) e pink (trecho de 9 m), os de duas cores na diagonal da
//    escada, os painéis com o X, os rolos em pé, os pares de rolos deitados,
//    as redes amarelas em V, os sacos azuis, a pirâmide magenta, os rolos da
//    passagem, o tobogã espiral amarelo e magenta, as duas piscinas de
//    bolinhas, os escorregadores ondulados, a Área Baby com a placa em
//    nuvem, a escadinha verde e as telas de proteção.
// As máquinas de jogos e o carrinho que aparecem embaixo e ao lado nas
// imagens são do salão, não do brinquedão: não entram (nem o salão).
//
// Coordenadas de trabalho = as do .3ds: x ao longo do brinquedo (da esquerda
// para a direita de quem olha de frente), y para o FUNDO, z para cima, em
// milímetros. No fim tudo vira metros, Y para cima e a frente em +Z.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const E = await (await fetch("estrutura.json")).json();
const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------- a grade (as colunas do .3ds) ----------
// o trecho de 12 m (ao fundo): 12 módulos de ~0,97 m
const A = { x: [1050, 2020, 2980, 3940, 4910, 5890, 6850, 7820, 8780, 9760, 10720, 11690, 12650], y0: 6600, y1: 7600 };
// o trecho de 9 m (na frente, à direita); o 6º módulo tem 2 m
const B = { x: [11690, 12650, 13620, 14600, 15580, 16560, 18610, 19590], y0: 3900, y1: 4910 };
// a passagem entre os dois (no último módulo do trecho de 12 m)
const PASSAGEM = { x0: 11690, x1: 12650, y0: B.y1, y1: A.y0 };
// o quadro da piscina do tobogã (2 m × 2 m): borda a 0,43 m, topo a 2,55 m
const POCO = { x0: 18610, x1: 20560, y0: 2880, y1: 4910, borda: 430, topo: 2550 };
const ANDAR = 2550; // as barras do piso do andar de cima
const PISO = ANDAR + 45; // onde se pisa lá em cima (o piso por cima das barras)
const TETO = 3510; // o corrimão de cima
const MEIO = 1590; // o piso do meio da escada
const BASE = 200; // o piso de baixo da escada
const ESP = 70; // a espessura dos pisos
const yA = (A.y0 + A.y1) / 2;
const yB = (B.y0 + B.y1) / 2;

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map(); // nome -> { material, geometrias: [], extras }
function material(nome, opcoes, extras = {}) {
  if (!pecas.has(nome)) {
    pecas.set(nome, { material: new THREE.MeshStandardMaterial({ name: nome, roughness: 0.55, metalness: 0, ...opcoes }), geometrias: [], extras });
  }
  return nome;
}
function por(nome, geometria, matriz) {
  if (matriz) geometria.applyMatrix4(matriz);
  pecas.get(nome).geometrias.push(geometria);
}
// texturas desenhadas (vão dentro do .glb, em PNG; pequenas, que o .glb tem de ser leve)
function tela(w, h, pintar, repetir) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  pintar(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  if (repetir) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// as cores tiradas do render em perspectiva (o mais fiel) e da planta
const COR = {
  azul: "#0b46b4", // os tubos (o material do .3ds é #0147a9)
  amarelo: "#efe31c", magenta: "#e0189a", pink: "#e8256f", vermelho: "#e01c5c",
  azulEspuma: "#0a58d8", azulSaco: "#1676f2", azulNuvem: "#0a84f5", verde: "#5ccb0a",
  branco: "#f1f2f5", cinza: "#9aa0a8",
};
// o contorno da nuvem (o mesmo no desenho da placa e no corpo dela), em 0..w × 0..h
const BOLOTAS = [[0.2, 0.42, 0.17], [0.38, 0.26, 0.2], [0.6, 0.24, 0.2], [0.8, 0.4, 0.18], [0.84, 0.66, 0.17], [0.64, 0.78, 0.2], [0.4, 0.8, 0.2], [0.17, 0.68, 0.17], [0.5, 0.52, 0.3]];
function nuvem(g, w, h) {
  for (const [x, y, r] of BOLOTAS) { g.beginPath(); g.arc(x * w, y * h, r * h * 1.05, 0, PI * 2); g.fill(); }
}

const M = {
  tubos: material("tubos-azuis", { color: COR.azul, roughness: 0.35, metalness: 0.1 }),
  amarelo: material("amarelo", { color: COR.amarelo }),
  pink: material("piso-pink", { color: COR.pink, roughness: 0.6 }),
  magenta: material("magenta", { color: COR.magenta, roughness: 0.5 }),
  vermelho: material("rolo-vermelho", { color: COR.vermelho, roughness: 0.6 }),
  espuma: material("espuma-azul", { color: COR.azulEspuma, roughness: 0.7 }),
  saco: material("saco-azul", { color: COR.azulSaco, roughness: 0.6 }),
  verde: material("verde-limao", { color: COR.verde, roughness: 0.6 }),
  branco: material("branco", { color: COR.branco, roughness: 0.5 }),
  ferragem: material("ferragem", { color: "#3b3f46", roughness: 0.4, metalness: 0.4 }),
  tuboAmarelo: material("toboga-amarelo", { color: COR.amarelo, roughness: 0.25, side: THREE.DoubleSide }),
  tuboMagenta: material("toboga-magenta", { color: COR.magenta, roughness: 0.25, side: THREE.DoubleSide }),
  pista: material("escorregador-amarelo", { color: COR.amarelo, roughness: 0.3, side: THREE.DoubleSide }),
  bolinhas: material("bolinhas", { vertexColors: true, roughness: 0.35 }),
  eva: material("piso-eva", { vertexColors: true, roughness: 0.8 }),
};
// a rede amarela das passarelas em V (a chapa com os furos quadrados)
M.rede = material("rede-amarela", {
  side: THREE.DoubleSide, alphaTest: 0.5, roughness: 0.5,
  map: tela(64, 64, (g, w, h) => {
    g.fillStyle = COR.amarelo; g.fillRect(0, 0, w, h);
    g.clearRect(16, 16, 32, 32);
  }, true),
});
// a tela de proteção: clara, translúcida, com a trama da rede
M.tela = material("tela-protecao", {
  color: "#eef4fb", transparent: true, depthWrite: false, side: THREE.DoubleSide, roughness: 0.2,
  map: tela(32, 32, (g, w, h) => {
    g.fillStyle = "rgba(255,255,255,.06)"; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(255,255,255,.22)";
    g.fillRect(0, 0, w, 1); g.fillRect(0, 0, 1, h);
  }, true),
});
// o painel "X": branco, com o círculo magenta e o X amarelo
M.painelX = material("painel-x", {
  roughness: 0.6, side: THREE.DoubleSide,
  map: tela(256, 256, (g, w, h) => {
    g.fillStyle = "#eceef3"; g.fillRect(0, 0, w, h);
    g.strokeStyle = "#d9dce4"; g.lineWidth = 6; g.strokeRect(3, 3, w - 6, h - 6);
    g.fillStyle = COR.magenta; g.beginPath(); g.arc(w / 2, h / 2, 108, 0, PI * 2); g.fill();
    g.fillStyle = "#fbfbfd"; g.beginPath(); g.arc(w / 2, h / 2, 90, 0, PI * 2); g.fill();
    g.strokeStyle = "#f2e21a"; g.lineWidth = 34; g.lineCap = "round";
    g.beginPath(); g.moveTo(w / 2 - 50, h / 2 - 54); g.lineTo(w / 2 + 50, h / 2 + 54);
    g.moveTo(w / 2 + 50, h / 2 - 54); g.lineTo(w / 2 - 50, h / 2 + 54); g.stroke();
  }),
});
// a placa em nuvem da Área Baby: o texto amarelo, com a sombra azul-escura
M.placa = material("placa-area-baby", {
  roughness: 0.5, alphaTest: 0.5, side: THREE.DoubleSide,
  map: tela(512, 256, (g, w, h) => {
    g.clearRect(0, 0, w, h);
    g.fillStyle = COR.azulNuvem;
    nuvem(g, w, h);
    g.textAlign = "center"; g.textBaseline = "middle";
    const escrever = (txt, y, px) => {
      g.font = `900 ${px}px "Arial Rounded MT Bold", "Arial Black", Arial, sans-serif`;
      g.fillStyle = "#0b3c8c"; g.fillText(txt, w / 2 + 4, y + 5);
      g.fillStyle = "#f7e93a"; g.fillText(txt, w / 2, y);
    };
    escrever("Área", 92, 66);
    escrever("Baby", 168, 92);
  }),
});
// ---------- peças básicas (em mm) ----------
function cilindro(nome, a, b, r, lados = 12, tampa = true) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, !tampa);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, V(1, 1, 1)));
}
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  const g = new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0));
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
// um quadrilátero a-b-c-d (a textura repete a cada `passo` mm)
function quad(nome, a, b, c, d, passo = 0) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute([a, b, c, d].flatMap((p) => [p.x, p.y, p.z]), 3));
  const su = passo ? a.distanceTo(b) / passo : 1;
  const sv = passo ? a.distanceTo(d) / passo : 1;
  g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, su, 0, su, sv, 0, sv], 2));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  g.computeVertexNormals();
  por(nome, g);
}
// um painel em pé no plano x = cte ou y = cte
function painelX(nome, x, y0, y1, z0, z1, passo = 0) {
  quad(nome, V(x, y0, z0), V(x, y1, z0), V(x, y1, z1), V(x, y0, z1), passo);
}
function painelY(nome, y, x0, x1, z0, z1, passo = 0) {
  quad(nome, V(x0, y, z0), V(x1, y, z0), V(x1, y, z1), V(x0, y, z1), passo);
}
// uma forma plana (no plano XY) extrudada para cima, de z0 até z0 + altura
function laje(nome, pontos, z0, altura) {
  const forma = new THREE.Shape(pontos.map(([x, y]) => new THREE.Vector2(x, y)));
  por(nome, new THREE.ExtrudeGeometry(forma, { depth: altura, bevelEnabled: false }), new THREE.Matrix4().makeTranslation(0, 0, z0));
}
// bolinhas e placas de EVA coloridas: uma geometria só, com a cor em cada vértice
function coloridos(nome, itens, base) {
  const partes = itens.map(({ m, cor }) => {
    const g = base.clone();
    g.applyMatrix4(m);
    const c = new THREE.Color(cor);
    const cores = new Float32Array(g.attributes.position.count * 3);
    for (let i = 0; i < cores.length; i += 3) { cores[i] = c.r; cores[i + 1] = c.g; cores[i + 2] = c.b; }
    g.setAttribute("color", new THREE.Float32BufferAttribute(cores, 3));
    return g;
  });
  por(nome, mergeGeometries(partes, false));
}
let semente = 7;
const sorte = () => ((semente = (semente * 16807) % 2147483647) / 2147483647);
// uma camada de bolinhas num retângulo (a de cima; embaixo, um fundo da mesma
// cor); `emFilas`: as cores em fileiras de frente para trás, como no render
function bolinhas(x0, x1, y0, y1, zTopo, cores, passo = 150, emFilas = false) {
  const lista = [];
  for (let y = y0 + passo / 2; y < y1 - passo / 3; y += passo) {
    for (let x = x0 + passo / 2, fila = 0; x < x1 - passo / 3; x += passo, fila++) {
      const cor = emFilas ? cores[fila % cores.length] : cores[Math.floor(sorte() * cores.length)];
      lista.push({ m: new THREE.Matrix4().makeTranslation(x + (sorte() - 0.5) * 30, y + (sorte() - 0.5) * 30, zTopo - 40 + sorte() * 40), cor });
    }
  }
  coloridos(M.bolinhas, lista, new THREE.IcosahedronGeometry(passo * 0.52, 1));
}

/* ======================================================================
   1. A ESTRUTURA DO .3DS: as colunas e as barras azuis, como estão no arquivo
   ====================================================================== */
for (const [x, y, z0, z1] of E.colunas) {
  // (no .3ds as colunas do chão começam a 5 cm: a sapata; aqui vão ao chão)
  cilindro(M.tubos, V(x, y, z0 <= 60 ? 0 : z0), V(x, y, z1 + 10), 40, 10);
}
for (const [xa, ya, za, xb, yb, zb, r] of E.barras) cilindro(M.tubos, V(xa, ya, za), V(xb, yb, zb), r, 8);
// o arco da entrada da piscina do tobogã (as duas pernas e o meio-círculo)
const ARCO = (() => {
  const [x0, x1, y, z0, z1] = E.arco;
  const r = 40, xc = (x0 + x1) / 2, raio = (x1 - x0) / 2 - r, zc = z1 - r - raio;
  const pontos = [V(xc - raio, y, z0)];
  for (let i = 0; i <= 12; i++) {
    const a = PI - (i / 12) * PI;
    pontos.push(V(xc + raio * Math.cos(a), y, zc + raio * Math.sin(a)));
  }
  pontos.push(V(xc + raio, y, z0));
  por(M.tubos, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pontos, false, "catmullrom", 0.05), 32, r, 8, false));
  return { xc, raio, y };
})();

/* ======================================================================
   2. OS PISOS DO ANDAR DE CIMA: amarelos no trecho de 12 m e na passagem,
      pink no de 9 m (o 1º módulo dele, na quina, é amarelo), como na planta
   ====================================================================== */
const VS = [[A.x[2], A.x[4], A], [A.x[6], A.x[7], A], [A.x[10], A.x[11], A], [B.x[3], B.x[5], B]]; // as redes em V
const piso = (nome, x0, x1, y0, y1) => caixa(nome, x0, x1, y0, y1, PISO - ESP, PISO);
// trecho de 12 m: do 2º módulo ao último (o 1º é a escada), menos as redes em V
for (let i = 1; i < A.x.length - 1; i++) {
  if (VS.some(([a, b, t]) => t === A && A.x[i] >= a && A.x[i + 1] <= b)) continue;
  piso(M.amarelo, A.x[i], A.x[i + 1], A.y0, A.y1);
}
piso(M.amarelo, PASSAGEM.x0, PASSAGEM.x1, PASSAGEM.y0, PASSAGEM.y1);
piso(M.amarelo, B.x[0], B.x[1], B.y0, B.y1);
for (const [x0, x1] of [[B.x[1], B.x[3]], [B.x[5], B.x[7]]]) piso(M.pink, x0, x1, B.y0, B.y1);

/* ======================================================================
   3. A PONTA ESQUERDA: a escada (os degraus de tubo do .3ds, a 0,98 m e a
      2,18 m, com a espuma pink), o piso de baixo amarelo e os dois pisos de
      duas cores na diagonal: o pink no meio (1,59 m, metade do fundo) e o
      amarelo em cima (metade da frente) -- vistos de cima, os dois juntos
      formam o quadrado de duas cores da planta
   ====================================================================== */
{
  const [x0, x1] = [A.x[0], A.x[1]];
  caixa(M.amarelo, x0, x1, A.y0, A.y1, BASE - 40, BASE + 40);
  laje(M.pink, [[x0, A.y0], [x0, A.y1], [x1, A.y1]], MEIO - 30, ESP);
  laje(M.amarelo, [[x0, A.y0], [x1, A.y0], [x1, A.y1]], PISO - ESP, ESP);
  // a espuma dos degraus (os tubos do .3ds a 0,98 m e 2,18 m, no lado e no fundo)
  for (const [xa, ya, za, xb, yb, zb] of E.barras) {
    if (za !== zb || ![980, 2180].includes(za) || Math.max(xa, xb) > x1 + 10) continue;
    const dir = V(xb - xa, yb - ya, 0).normalize();
    cilindro(M.pink, V(xa, ya, za).addScaledVector(dir, 80), V(xb, yb, zb).addScaledVector(dir, -80), 55, 12);
  }
}

/* ======================================================================
   4. AS REDES AMARELAS EM V: das barras de cima (3,27 m no trecho de 12 m,
      3,31 m no de 9 m) até a faixa amarela do meio, por onde se engatinha
   ====================================================================== */
for (const [x0, x1, t] of VS) {
  const zAlto = t === A ? 3270 : 3310;
  const yc = (t.y0 + t.y1) / 2, meio0 = yc - 120, meio1 = yc + 120, zb = PISO - 20;
  quad(M.rede, V(x0 + 40, t.y0, zAlto), V(x1 - 40, t.y0, zAlto), V(x1 - 40, meio0, zb), V(x0 + 40, meio0, zb), 120);
  quad(M.rede, V(x0 + 40, meio1, zb), V(x1 - 40, meio1, zb), V(x1 - 40, t.y1, zAlto), V(x0 + 40, t.y1, zAlto), 120);
  caixa(M.amarelo, x0 + 40, x1 - 40, meio0, meio1, zb - 40, zb);
}

/* ======================================================================
   5. AS PEÇAS DO ANDAR DE CIMA
   ====================================================================== */
const ZM = (ANDAR + TETO) / 2;
// os painéis "X" na frente das cabeceiras dos módulos (como na vista de frente)
for (const [x0, x1, y] of [[A.x[0], A.x[1], A.y0], [A.x[4], A.x[5], A.y0], [A.x[8], A.x[9], A.y0], [B.x[0], B.x[1], B.y0]]) {
  painelY(M.painelX, y - 45, x0 + 45, x1 - 45, ANDAR + 45, TETO - 45);
}
// os rolos em pé (giram num eixo do piso ao teto): vermelhos no trecho de
// 12 m e o amarelo do trecho de 9 m, no disco que o .3ds deixou marcado
function roloEmPe(nome, x, y, r) {
  cilindro(M.ferragem, V(x, y, PISO), V(x, y, TETO - 20), 18, 6);
  cilindro(nome, V(x, y, 2720), V(x, y, 3420), r, 20);
}
for (const i of [1, 5, 9]) roloEmPe(M.vermelho, (A.x[i] + A.x[i + 1]) / 2, yA, 160);
roloEmPe(M.amarelo, E.marca[0], E.marca[1], 180);
// os pares de rolos deitados (de frente para trás): passa-se entre os dois
const ROLOS = { baixo: 2745, alto: 3330, r: 150 }; // a fresta do meio (29 cm) é por onde se passa
function parDeRolos(x, comPostes) {
  if (comPostes) for (const y of [B.y0, B.y1]) cilindro(M.tubos, V(x, y, ANDAR), V(x, y, TETO), 32, 8);
  for (const z of [ROLOS.baixo, ROLOS.alto]) {
    cilindro(M.ferragem, V(x, B.y0, z), V(x, B.y1, z), 16, 6);
    cilindro(M.amarelo, V(x, B.y0 + 70, z), V(x, B.y1 - 70, z), ROLOS.r, 20);
  }
}
parDeRolos(E.colunas.find(([x, y, z0]) => x > 13000 && x < 13300 && z0 > 2000)[0], false); // nos postes do .3ds
parDeRolos(17100, true); // no módulo de 2 m (os postes iguais aos do .3ds)
// os sacos azuis pendurados (o 1º módulo do trecho de 9 m e o de 2 m)
for (const x of [(B.x[0] + B.x[1]) / 2, 18050]) {
  cilindro(M.ferragem, V(x, B.y0, TETO - 15), V(x, B.y1, TETO - 15), 16, 6);
  cilindro(M.ferragem, V(x, yB, TETO - 15), V(x, yB, 3360), 10, 5);
  cilindro(M.saco, V(x, yB, 3360), V(x, yB, 2820), 160, 18);
}
// a pirâmide magenta (um prisma baixo, de frente para trás) no 8º módulo
{
  const xc = (A.x[7] + A.x[8]) / 2, meia = 160, alto = 300;
  const forma = new THREE.Shape([new THREE.Vector2(-meia, 0), new THREE.Vector2(meia, 0), new THREE.Vector2(0, alto)]);
  const g = new THREE.ExtrudeGeometry(forma, { depth: 740, bevelEnabled: false });
  // a forma no plano XZ (x -> x, y da forma -> z), a espessura ao longo de y
  por(M.magenta, g, new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(xc, yA + 370, PISO));
}
// os rolos magenta deitados na passagem: um baixo, um alto, um baixo
for (const [y, z] of [[6280, PISO + 165], [5760, 3260], [5280, PISO + 165]]) {
  cilindro(M.ferragem, V(PASSAGEM.x0, y, z), V(PASSAGEM.x1, y, z), 16, 6);
  cilindro(M.magenta, V(PASSAGEM.x0 + 90, y, z), V(PASSAGEM.x1 - 90, y, z), 165, 20);
}

/* ======================================================================
   6. O TOBOGÃ ESPIRAL: a boca fica no piso do último módulo do trecho de
      9 m e o tubo sai pela frente dele (pelo furo do painel magenta); desce
      quase duas voltas em torno da coluna da quina (19,59 m, como na planta)
      e sai na piscina de bolinhas, na frente, à esquerda. Amarelo na frente,
      magenta por trás, como no render. As mesmas medidas estão no passeio
      da Arena (toboganDoModelo4, em core/static/site/arena/caminhos.js).
   ====================================================================== */
const TOBOGA = { cx: 19590, cy: 3900, raio: 570, r: 290, a0: 180, a1: 880, zTopo: 2880, zFim: 640, boca: [19020, 4200], saida: [18880, 3250, 560] };
{
  const { cx, cy, raio, r, a0, a1, zTopo, zFim, boca: [bx, by], saida } = TOBOGA;
  const grau = PI / 180;
  const ponto = (a, z) => V(cx + raio * Math.cos(a * grau), cy + raio * Math.sin(a * grau), z);
  // a espiral e as cores: [ângulo final, material] (um meio-giro de cada)
  const trechos = [[360, M.tuboAmarelo], [540, M.tuboMagenta], [720, M.tuboAmarelo], [a1, M.tuboMagenta]];
  const z = (a) => zTopo - ((a - a0) / (a1 - a0)) * (zTopo - zFim);
  let inicio = a0;
  trechos.forEach(([fim, nome], k) => {
    const pontos = [];
    if (k === 0) pontos.push(V(bx, by, zTopo), V(bx, (by + cy) / 2 + 60, zTopo));
    for (let a = inicio; a <= fim + 0.01; a += 15) pontos.push(ponto(a, z(a)));
    if (k === trechos.length - 1) pontos.push(V(...saida));
    else pontos.push(ponto(fim + 4, z(fim + 4)));
    // cada meio-giro entra 4 graus no seguinte (sem fresta) com 8 mm a menos
    // de raio, um sim, um não: na emenda as duas paredes não brigam (do mesmo
    // raio, piscavam -- a faixa amarela e magenta riscando o túnel no passeio)
    por(nome, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pontos), pontos.length * 3, r - (k % 2) * 8, 16, false));
    inicio = fim;
  });
  // a boca: o aro amarelo no piso do módulo
  por(M.tuboAmarelo, new THREE.TorusGeometry(r + 15, 30, 8, 24), new THREE.Matrix4().compose(V(bx, by, zTopo), new THREE.Quaternion().setFromUnitVectors(V(0, 0, 1), V(0, -1, 0)), V(1, 1, 1)));
  // o painel magenta da frente do módulo, com o furo por onde o tubo passa
  const forma = new THREE.Shape();
  const [p0, p1] = [B.x[6] + 45, B.x[7] - 45];
  forma.moveTo(p0, ANDAR + 45); forma.lineTo(p1, ANDAR + 45); forma.lineTo(p1, TETO - 45); forma.lineTo(p0, TETO - 45); forma.lineTo(p0, ANDAR + 45);
  const furo = new THREE.Path();
  furo.absarc(bx, zTopo, r + 25, 0, PI * 2, true);
  forma.holes.push(furo);
  const placa = new THREE.ExtrudeGeometry(forma, { depth: 25, bevelEnabled: false, curveSegments: 20 });
  por(M.magenta, placa, new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(0, B.y0 - 50, 0));
}

/* ======================================================================
   7. A PISCINA DO TOBOGÃ: a mureta azul até a barra de 0,43 m, as bolinhas
      magenta e verde-limão em fileiras, a escadinha verde de dois degraus na
      frente, sob o arco azul do .3ds, e as telas do quadro
   ====================================================================== */
{
  const { x0, x1, y0, y1, borda } = POCO;
  const e = 60;
  caixa(M.espuma, x0, x1, y0 - e, y0 + e, 0, borda);
  caixa(M.espuma, x0, x1, y1 - e, y1 + e, 0, borda);
  caixa(M.espuma, x0 - e, x0 + e, y0, y1, 0, borda);
  caixa(M.espuma, x1 - e, x1 + e, y0, y1, 0, borda);
  caixa(M.magenta, x0 + e, x1 - e, y0 + e, y1 - e, 0, borda - 160);
  bolinhas(x0 + e, x1 - e, y0 + e, y1 - e, borda - 70, ["#e0189a", "#7ad31c"], 150, true);
  // a escadinha verde: dois degraus encostados na mureta, sob o arco
  const [d0, d1] = [ARCO.xc - 250, ARCO.xc + 250];
  caixa(M.verde, d0, d1, y0 - e - 190, y0 - e, 0, borda);
  caixa(M.verde, d0, d1, y0 - e - 380, y0 - e - 190, 0, borda / 2);
  // as telas: o fundo, os dois lados (a frente fica aberta, como no render)
  painelY(M.tela, y1 + 20, x0, x1, borda + 30, POCO.topo, 100);
  painelX(M.tela, x1 + 20, y0, y1, borda + 30, POCO.topo, 100);
  painelX(M.tela, x0 - 20, y0, B.y0, borda + 30, POCO.topo, 100);
}

/* ======================================================================
   8. A PISCINA DE BOLINHAS GRANDE (embaixo do trecho de 12 m, entre as
      colunas de 4,91 m e 8,79 m): passa por baixo do andar de cima, com a
      mureta azul na frente, a divisória amarela no meio, a parede branca no
      fundo com as duas testeiras magenta, e um escorregador ondulado
      amarelo de cada lado, com os arcos brancos e amarelos por cima
   ====================================================================== */
const PISCINA = { x0: 5680, x1: 8110, y0: 5870, y1: 8340, borda: 800 };
{
  const { x0, x1, y0, y1, borda } = PISCINA;
  const e = 50, xm = (x0 + x1) / 2;
  caixa(M.espuma, x0, x1, y0 - e, y0 + e, 0, borda);
  caixa(M.branco, x0 - e, x0 + e, y0, y1, 0, borda);
  caixa(M.branco, x1 - e, x1 + e, y0, y1, 0, borda);
  caixa(M.amarelo, xm - 30, xm + 30, y0, y1, 0, borda);
  caixa(M.espuma, x0, x1, y0, y1, 0, borda - 360);
  bolinhas(x0 + e, xm - 30, y0 + e, y1 - 40, borda - 200, ["#2c6fe0", "#3cc43a", "#f4f4f4", "#e02a2a", "#2fb5e8"], 160);
  bolinhas(xm + 30, x1 - e, y0 + e, y1 - 40, borda - 200, ["#2c6fe0", "#3cc43a", "#f4f4f4", "#e02a2a", "#2fb5e8"], 160);
  // a parede branca do fundo (até 1,9 m, da largura dos escorregadores) e as testeiras magenta
  caixa(M.branco, A.x[4] + 70, A.x[8] - 70, y1, y1 + 80, 0, 1900);
  for (const [a, b] of [[x0, xm], [xm, x1]]) {
    const forma = new THREE.Shape();
    forma.moveTo(a + 60, 0);
    forma.lineTo(b - 60, 0);
    forma.quadraticCurveTo((a + b) / 2, 520, a + 60, 0);
    por(M.magenta, new THREE.ExtrudeGeometry(forma, { depth: 60, bevelEnabled: false, curveSegments: 12 }), new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(0, y1 + 10, 1900));
  }
}
// os escorregadores ondulados: do alto do fundo (1,9 m) até a frente da piscina
function perfilEscorregador(t) {
  return 1900 - 1550 * t + 120 * Math.sin(t * PI * 3) * (1 - t) * (t < 0.92 ? 1 : 0);
}
const ESCORREGADORES = [[A.x[4] + 70, PISCINA.x0 - 60], [PISCINA.x1 + 60, A.x[8] - 70]];
for (const [x0, x1] of ESCORREGADORES) {
  const ya = PISCINA.y1 - 120, yb = PISCINA.y0 + 30, n = 30;
  const pista = [], ladoE = [], ladoD = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, y = ya + (yb - ya) * t, z = perfilEscorregador(t);
    pista.push([V(x0 + 40, y, z), V(x1 - 40, y, z)]);
    ladoE.push([V(x0 + 20, y, z - 60), V(x0 + 20, y, z + 260)]);
    ladoD.push([V(x1 - 20, y, z - 60), V(x1 - 20, y, z + 260)]);
  }
  const fita = (nome, pares) => {
    const pos = [], uv = [], idx = [];
    pares.forEach(([a, b], i) => {
      pos.push(a.x, a.y, a.z, b.x, b.y, b.z);
      uv.push(0, i / n, 1, i / n);
      if (i) idx.push(2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i - 2, 2 * i + 1, 2 * i);
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    por(nome, g);
  };
  fita(M.pista, pista);
  fita(M.branco, ladoE);
  fita(M.branco, ladoD);
  // as bordas amarelas de cima das laterais
  for (const lado of [ladoE, ladoD]) {
    por(M.amarelo, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(lado.map(([, b]) => b)), n, 22, 6, false));
  }
  // os arcos por cima da pista (brancos e amarelos, alternados)
  const xc = (x0 + x1) / 2, rArco = (x1 - x0) / 2 - 20;
  [0.12, 0.34, 0.56, 0.78].forEach((t, k) => {
    const y = ya + (yb - ya) * t, z = perfilEscorregador(t) + 260;
    const pontos = [];
    for (let i = 0; i <= 10; i++) {
      const a = PI - (i / 10) * PI;
      pontos.push(V(xc + rArco * Math.cos(a), y, z + rArco * 1.3 * Math.sin(a)));
    }
    por(k % 2 ? M.amarelo : M.branco, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pontos), 14, 22, 6, false));
  });
  // a torre branca de onde se sai (no fundo, atrás do andar de cima)
  caixa(M.branco, x0, x1, PISCINA.y1 - 120, PISCINA.y1, 0, 1900);
}

/* ======================================================================
   9. A ÁREA BABY (na frente do trecho de 9 m, como na planta): o cercadinho
      amarelo baixo, os blocos de espuma azuis nas pontas da frente, o piso
      de EVA colorido, a plataforma amarela, as bolinhas, e a placa em nuvem
      azul "Área Baby" em dois postes amarelos sobre a entrada
   ====================================================================== */
const BABY = { x0: 13700, x1: 16440, y0: 2880, y1: 3860, alto: 450 };
{
  const { x0, x1, y0, y1, alto } = BABY;
  const e = 150, frente = y0 + 360, xa = 14580, xb = 15560;
  // o cercadinho: o fundo e os lados amarelos; na frente, os blocos azuis
  caixa(M.amarelo, x0, x1, y1 - e, y1, 0, alto);
  caixa(M.amarelo, x0, x0 + e, frente, y1 - e, 0, alto);
  caixa(M.amarelo, x1 - e, x1, frente, y1 - e, 0, alto);
  caixa(M.espuma, x0, xa, y0, frente, 0, alto);
  caixa(M.espuma, xb, x1, y0, frente, 0, alto);
  // o degrau amarelo da entrada e a plataforma amarela do lado esquerdo
  caixa(M.amarelo, xa, xb, frente, frente + 160, 0, 160);
  caixa(M.amarelo, x0 + e, xa, frente, y1 - e, 0, 260);
  // o piso de EVA colorido: placas de ~47 cm dentro e as três da entrada
  const cores = ["#f2e21a", "#1f74e0", "#e0242a", "#3cc43a"];
  const placas = [];
  const placa = (px0, px1, py0, py1, cor) => placas.push({
    m: new THREE.Matrix4().compose(V((px0 + px1) / 2, (py0 + py1) / 2, 15), new THREE.Quaternion(), V(px1 - px0 - 6, py1 - py0 - 6, 1)), cor,
  });
  let k = 0;
  for (let x = xa; x < x1 - e - 10; x += 470) {
    for (let y = frente + 160; y < y1 - e - 10; y += 450) placa(x, Math.min(x + 470, x1 - e), y, Math.min(y + 450, y1 - e), cores[k++ % 4]);
  }
  const passo = (xb - xa) / 3;
  ["#3cc43a", "#1f74e0", "#e0242a"].forEach((cor, i) => placa(xa + i * passo, xa + (i + 1) * passo, y0, frente, cor));
  coloridos(M.eva, placas, new THREE.BoxGeometry(1, 1, 30));
  // as bolinhas no canto direito
  semente = 3;
  bolinhas(xb, x1 - e, frente + 180, y1 - e, 200, ["#e0189a", "#f2e21a", "#1f74e0", "#8a4fd8", "#3cc43a"], 140);
  // os postes amarelos e a placa em nuvem
  const yp = frente + 40;
  for (const x of [xa - 40, xb + 40]) caixa(M.amarelo, x - 45, x + 45, yp - 45, yp + 45, 0, 1750);
  // (a placa tem a proporção do desenho, 2 × 1: as bolotas do corpo caem nas do desenho)
  const [n0, n1, z0, z1] = [(xa + xb) / 2 - 700, (xa + xb) / 2 + 700, 1520, 2220];
  // o corpo da nuvem (azul) e a frente com o texto (o desenho tem o contorno da nuvem)
  for (const [u, v, r] of BOLOTAS) {
    const bolota = new THREE.Shape();
    bolota.absarc(n0 + u * (n1 - n0), z1 - v * (z1 - z0), r * (z1 - z0) * 1.03, 0, PI * 2, false);
    por(M.espuma, new THREE.ExtrudeGeometry(bolota, { depth: 50, bevelEnabled: false, curveSegments: 14 }), new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(0, yp - 10, 0));
  }
  painelY(M.placa, yp - 65, n0, n1, z0, z1);
}

/* ======================================================================
   10. AS TELAS DE PROTEÇÃO (claras e translúcidas) em volta do andar de cima
   ====================================================================== */
{
  const z0 = ANDAR + 40, z1 = TETO - 40, P = 100;
  // trecho de 12 m: o fundo inteiro; a frente menos os painéis X e a boca da passagem
  painelY(M.tela, A.y1 + 15, A.x[0], A.x[12], z0, z1, P);
  for (let i = 1; i < 11; i++) if (![4, 8].includes(i)) painelY(M.tela, A.y0 - 15, A.x[i], A.x[i + 1], z0, z1, P);
  painelX(M.tela, A.x[12] + 15, A.y0, A.y1, z0, z1, P);
  // a escada: o lado esquerdo e o fundo inteiros; na frente, entre o piso do meio e o X
  painelX(M.tela, A.x[0] - 15, A.y0, A.y1, BASE + 40, z1, P);
  painelY(M.tela, A.y1 + 15, A.x[0], A.x[1], BASE + 40, z0, P);
  painelY(M.tela, A.y0 - 15, A.x[0], A.x[1], MEIO + 40, z0, P);
  // a passagem: os dois lados
  painelX(M.tela, PASSAGEM.x0 - 15, PASSAGEM.y0, PASSAGEM.y1, z0, z1, P);
  painelX(M.tela, PASSAGEM.x1 + 15, PASSAGEM.y0, PASSAGEM.y1, z0, z1, P);
  // trecho de 9 m: a frente (menos o X e o painel do tobogã), o fundo (menos a passagem) e as pontas
  for (let i = 1; i < 6; i++) painelY(M.tela, B.y0 - 15, B.x[i], B.x[i + 1], z0, z1, P);
  painelY(M.tela, B.y1 + 15, B.x[1], B.x[7], z0, z1, P);
  painelX(M.tela, B.x[0] - 15, B.y0, B.y1, z0, z1, P);
  painelX(M.tela, B.x[7] + 15, B.y0, B.y1, z0, z1, P);
}

/* ======================================================================
   MONTAGEM FINAL: metros, Y para cima, a frente em +Z; centraliza e assenta
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "brinquedao-modelo-4";
cena.add(raiz);
// (x, y, z) do .3ds -> (x, z, -y) em metros: rotação própria (sem espelhar)
const virar = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1).multiply(new THREE.Matrix4().makeScale(0.001, 0.001, 0.001));
for (const [nome, { material: mat, geometrias, extras }] of pecas) {
  if (!geometrias.length) continue;
  const comCor = Boolean(mat.vertexColors);
  const prontas = geometrias.map((g) => {
    let h = g.index ? g.toNonIndexed() : g;
    if (!h.attributes.uv) h.setAttribute("uv", new THREE.Float32BufferAttribute(new Float32Array(h.attributes.position.count * 2), 2));
    if (!h.attributes.normal) h.computeVertexNormals();
    for (const k of Object.keys(h.attributes)) if (!["position", "normal", "uv", ...(comCor ? ["color"] : [])].includes(k)) h.deleteAttribute(k);
    h.clearGroups();
    return h;
  });
  let g = mergeGeometries(prontas, false);
  g.applyMatrix4(virar);
  g = mergeVertices(g, 1e-5);
  const malha = new THREE.Mesh(g, mat);
  malha.name = nome;
  Object.assign(malha.userData, extras);
  raiz.add(malha);
}
// assenta no chão e centraliza
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 100) / 100);
// o deslocamento que leva o .3ds (em metros, já virado) ao objeto: o passeio da Arena usa
window.centro = { x: +centro.x.toFixed(4), chao: +caixaTotal.min.y.toFixed(4), z: +centro.z.toFixed(4) };
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);

// prévia, para conferir de vários lados
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1600, 1000);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.append(renderer.domElement);
cena.add(new THREE.HemisphereLight("#ffffff", "#667788", 1.9));
const sol = new THREE.DirectionalLight("#ffffff", 1.7);
sol.position.set(6, 10, 9);
cena.add(sol);
const chao = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshStandardMaterial({ color: "#d9dadf" }));
chao.rotation.x = -PI / 2;
cena.add(chao);
const camera = new THREE.PerspectiveCamera(40, 1600 / 1000, 0.1, 300);
window.ver = (x, y, z, alvo = [0, 1.5, 0], fov = 40, fundo = "#0b1a3a") => {
  cena.background = new THREE.Color(fundo);
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.88);
};
// sem perspectiva: de cima, como a planta (o fundo do brinquedo para cima), ou de frente, como a vista da fábrica
window.verOrto = (lado = "cima", largura = 22, fundo = "#ffffff") => {
  cena.background = new THREE.Color(fundo);
  chao.visible = false;
  const alto = (largura * 1000) / 1600;
  const orto = new THREE.OrthographicCamera(-largura / 2, largura / 2, alto / 2, -alto / 2, 0.1, 100);
  if (lado === "cima") {
    orto.position.set(0, 30, 0);
    orto.up.set(0, 0, -1);
    orto.lookAt(0, 0, 0);
  } else {
    orto.position.set(0, 1.75, 40);
    orto.lookAt(0, 1.75, 0);
  }
  renderer.render(cena, orto);
  chao.visible = true;
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
window.exportar = async () => {
  const exp = new GLTFExporter();
  const glb = await exp.parseAsync(raiz, { binary: true });
  const bytes = new Uint8Array(glb);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
};
window.pronto = true;
