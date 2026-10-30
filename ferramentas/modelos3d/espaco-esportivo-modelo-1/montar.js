// Monta o Espaço Esportivo Modelo 1 em three.js e exporta um .glb.
//
// De onde vem cada coisa:
//  - do trampo.3ds da fábrica: as alturas e a estrutura do parque de
//    trampolins -- a plataforma a 0,85 m (a grade de aço das camas, em
//    módulos de ~2 m), os postes laranja e o quadro preto de cima a 3,65 m,
//    e as gaiolas pretas das piscinas de espuma a 2,6 m;
//  - da planta do parque (18 m x 16,5 m): a divisão das camas, as cores
//    dos acolchoados, as piscinas de espuma, as enterradas e a parede;
//  - da planta das quadras (altura 2,90 m): campo e quadra de basquete
//    (8 m + 7 m, por 4 + 4 m), as duas arenas de panna (5 m) e a pista
//    de 2 m x 14 m;
//  - das imagens do espaço completo: o piso azul, o circuito kids na
//    frente do parque, o tobogã com a piscina de bolinhas e os blocos.
//
// Metros, Y para cima, a frente em +Z. A origem fica no centro do piso.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const PI = Math.PI;

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map();
function material(nome, opcoes, extras = {}) {
  if (!pecas.has(nome)) {
    pecas.set(nome, { material: new THREE.MeshStandardMaterial({ name: nome, roughness: 0.6, metalness: 0, ...opcoes }), geometrias: [], extras });
  }
  return nome;
}
function por(nome, geometria, matriz) {
  if (matriz) geometria.applyMatrix4(matriz);
  pecas.get(nome).geometrias.push(geometria);
}
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

const COR = {
  amarelo: "#f6c419", laranja: "#f07a12", azul: "#1f6fd8", vermelho: "#e3262f", verdeLimao: "#a8d826",
  cama: "#33363c", base: "#3a3d43", cinza: "#55585f", preto: "#1b1d22", posteLaranja: "#e98a1c",
  pisoAzul: "#2c4687", madeira: "#d9a464", grama: "#3e8c3c", terra: "#7d5a4b", rosa: "#e0218a", verde: "#2fb34a",
};
const M = {
  base: material("base-plataforma", { color: COR.base, roughness: 0.8 }),
  cama: material("camas", { color: COR.cama, roughness: 0.9 }, { lona: true }), // no passeio, quica
  camaVerde: material("camas-enterrada", { color: "#2c4b47", roughness: 0.9 }, { lona: true }),
  amarelo: material("amarelo", { color: COR.amarelo }),
  laranja: material("laranja", { color: COR.laranja }),
  azul: material("azul", { color: COR.azul }),
  vermelho: material("vermelho", { color: COR.vermelho }),
  verdeLimao: material("verde-limao", { color: COR.verdeLimao }),
  posteLaranja: material("postes-laranja", { color: COR.posteLaranja, roughness: 0.4, metalness: 0.3 }),
  preto: material("estrutura-preta", { color: COR.preto, roughness: 0.5, metalness: 0.4 }),
  cinza: material("cinza", { color: COR.cinza, roughness: 0.8 }),
  pisoAzul: material("piso-eva", { color: COR.pisoAzul, roughness: 0.95 }),
  branco: material("branco", { color: "#f4f6fa", roughness: 0.5 }),
  aro: material("aro-laranja", { color: "#ff6a00", roughness: 0.4, metalness: 0.5 }),
  terra: material("piso-panna", { color: COR.terra, roughness: 0.95 }),
  bordaPanna: material("parede-panna", { color: "#2b2e33", roughness: 0.6 }),
  verdeBorda: material("borda-verde", { color: "#5fd36a", roughness: 0.5 }),
  vidro: material("tela-quadras", { color: "#20242c", transparent: true, opacity: 0.28, depthWrite: false, side: THREE.DoubleSide }),
  cubos: material("cubos-de-espuma", { vertexColors: true, roughness: 0.85 }),
  bolinhas: material("bolinhas", { vertexColors: true, roughness: 0.35 }),
  tuboAmarelo: material("tobogã-amarelo", { color: "#f8cf1d", roughness: 0.35, side: THREE.DoubleSide }),
  tuboLaranja: material("tobogã-laranja", { color: "#f07417", roughness: 0.35, side: THREE.DoubleSide }),
};

// grama com as linhas, madeira com as linhas, a pista quadriculada, o painel do X, as agarras
M.grama = material("grama", {
  roughness: 0.95,
  map: tela(512, 256, (g, w, h) => {
    g.fillStyle = COR.grama; g.fillRect(0, 0, w, h);
    for (let i = 0; i < w; i += 32) { g.fillStyle = i % 64 ? "rgba(255,255,255,.04)" : "rgba(0,0,0,.05)"; g.fillRect(i, 0, 32, h); }
    g.strokeStyle = "rgba(255,255,255,.9)"; g.lineWidth = 5;
    g.strokeRect(6, 6, w - 12, h - 12);
    g.beginPath(); g.moveTo(w / 2, 6); g.lineTo(w / 2, h - 6); g.stroke();
    g.beginPath(); g.arc(w / 2, h / 2, 34, 0, PI * 2); g.stroke();
    g.strokeRect(6, h / 2 - 50, 60, 100); g.strokeRect(w - 66, h / 2 - 50, 60, 100);
  }),
});
M.quadra = material("quadra-basquete", {
  roughness: 0.6,
  map: tela(512, 256, (g, w, h) => {
    g.fillStyle = COR.madeira; g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(120,70,30,.25)"; g.lineWidth = 1;
    for (let y = 0; y < h; y += 8) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
    g.fillStyle = "#2f66c9";
    g.fillRect(6, h / 2 - 40, 90, 80); g.fillRect(w - 96, h / 2 - 40, 90, 80);
    g.strokeStyle = "rgba(255,255,255,.95)"; g.lineWidth = 4;
    g.strokeRect(6, 6, w - 12, h - 12);
    g.beginPath(); g.moveTo(w / 2, 6); g.lineTo(w / 2, h - 6); g.stroke();
    g.beginPath(); g.arc(w / 2, h / 2, 30, 0, PI * 2); g.stroke();
    g.beginPath(); g.arc(6, h / 2, 110, -PI / 2, PI / 2); g.stroke();
    g.beginPath(); g.arc(w - 6, h / 2, 110, PI / 2, PI * 1.5); g.stroke();
  }),
});
M.pista = material("pista", {
  roughness: 0.95,
  map: tela(64, 512, (g, w, h) => {
    g.fillStyle = COR.grama; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(255,255,255,.85)"; g.fillRect(0, 0, 3, h); g.fillRect(w - 3, 0, 3, h);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { g.fillStyle = (i + j) % 2 ? "#111" : "#fff"; g.fillRect(i * 16, h - 64 + j * 16, 16, 16); }
  }),
});
M.painelX = material("painel-x", {
  roughness: 0.6,
  map: tela(256, 256, (g, w, h) => {
    g.fillStyle = "#e5262e"; g.fillRect(0, 0, w, h);
    g.fillStyle = "#f6c419"; g.fillRect(14, 14, w - 28, h - 28);
    g.fillStyle = "#1d6b30"; g.beginPath(); g.arc(w / 2, h / 2, 92, 0, PI * 2); g.fill();
    g.fillStyle = "#9be04a"; g.beginPath(); g.arc(w / 2, h / 2, 78, 0, PI * 2); g.fill();
    g.strokeStyle = "#e5262e"; g.lineWidth = 26; g.lineCap = "round";
    g.beginPath(); g.moveTo(w / 2 - 45, h / 2 - 45); g.lineTo(w / 2 + 45, h / 2 + 45); g.moveTo(w / 2 + 45, h / 2 - 45); g.lineTo(w / 2 - 45, h / 2 + 45); g.stroke();
  }),
});
M.escalada = material("parede-escalada", {
  roughness: 0.8,
  map: tela(512, 256, (g, w, h) => {
    g.fillStyle = "#3a3c42"; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 70; i++) {
      const x = (i * 97) % (w - 20) + 10; const y = (i * 53) % (h - 20) + 10;
      g.fillStyle = i % 2 ? "#e3262f" : "#f6d419";
      g.beginPath(); g.moveTo(x, y - 7); g.lineTo(x + 7, y + 6); g.lineTo(x - 7, y + 6); g.fill();
    }
  }),
});
M.poster = material("painel-chute-ao-gol", {
  roughness: 0.7,
  map: tela(512, 256, (g, w, h) => {
    const ceu = g.createLinearGradient(0, 0, 0, h); ceu.addColorStop(0, "#0b4fa8"); ceu.addColorStop(1, "#5cc7f2");
    g.fillStyle = ceu; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(255,255,255,.18)"; for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(80 + i * 80, 60 + (i % 2) * 40, 40, 0, PI * 2); g.fill(); }
    // o goleiro voando para a bola
    g.fillStyle = "#132743"; g.save(); g.translate(260, 140); g.rotate(-0.5);
    g.fillRect(-90, -18, 180, 36); g.beginPath(); g.arc(-105, 0, 22, 0, PI * 2); g.fill(); g.fillRect(70, -40, 18, 80); g.restore();
    g.fillStyle = "#fff"; g.beginPath(); g.arc(400, 70, 22, 0, PI * 2); g.fill();
  }),
});

// ---------- peças ----------
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  por(nome, new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0)),
    new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function cilindro(nome, a, b, r, lados = 10) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, false);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, V(1, 1, 1)));
}
function esfera(nome, c, r, seg = 16) {
  por(nome, new THREE.SphereGeometry(r, seg, Math.max(6, seg >> 1)), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
}
function placa(nome, centro, largura, altura, normal, ladoU) {
  const n = normal.clone().normalize();
  const u = ladoU.clone().normalize();
  const v = new THREE.Vector3().crossVectors(n, u);
  por(nome, new THREE.PlaneGeometry(largura, altura), new THREE.Matrix4().makeBasis(u, v, n).setPosition(centro));
}
// piso deitado com a textura (u ao longo de x, v ao longo de -z)
function piso(nome, x0, x1, z0, z1, y) {
  const g = new THREE.PlaneGeometry(x1 - x0, z1 - z0);
  g.rotateX(-PI / 2);
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, y, (z0 + z1) / 2));
}
// cubos e bolinhas coloridos: uma geometria só, com a cor em cada vértice
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
const CORES_ESPUMA = ["#e3262f", "#f6c419", "#1f6fd8", "#3dbb3a", "#e0218a", "#f07a12", "#9be04a"];

/* ======================================================================
   1. O PISO AZUL (EVA) DO ESPAÇO
   ====================================================================== */
const PISO = { x0: -19.5, x1: 19.5, z0: -11.5, z1: 11.5 };
caixa(M.pisoAzul, PISO.x0, PISO.x1, 0, 0.05, PISO.z0, PISO.z1);
// os blocos de proteção coloridos na borda da frente e do lado direito do parque
{
  const cores = [M.vermelho, M.azul, M.amarelo];
  let k = 0;
  for (let x = 0.2; x < PISO.x1 - 0.6; x += 1.25) caixa(cores[k++ % 3], x, x + 1.2, 0.05, 0.5, PISO.z1 - 0.45, PISO.z1);
  for (let z = -6; z < PISO.z1 - 0.6; z += 1.25) caixa(cores[k++ % 3], PISO.x1 - 0.45, PISO.x1, 0.05, 0.5, z, z + 1.2);
  // blocos soltos (rosa, verde, azul) perto da beira
  [[11.8, 10.2], [14.0, 10.2]].forEach(([x, z]) => {
    caixa(M.vermelho, x, x + 0.6, 0.05, 0.65, z - 0.3, z + 0.3);
    caixa(M.verdeLimao, x + 0.65, x + 1.25, 0.05, 0.65, z - 0.3, z + 0.3);
    caixa(M.azul, x + 1.3, x + 1.9, 0.05, 0.65, z - 0.3, z + 0.3);
  });
}

/* ======================================================================
   2. O PARQUE DE TRAMPOLINS (18 m x 16,5 m) -- a planta, em metros
   x da planta: da esquerda para a direita no desenho; y: de cima para
   baixo. No espaço o parque fica à direita, de costas para o fundo: o
   fim do desenho (as enterradas e a parede de escalada) é o fundo.
   ====================================================================== */
const ALTURA = 0.85; // a plataforma (a grade de aço do .3ds)
const ACOLCHOADO = 0.12;
const P = { X: (px) => 18.6 - px, Z: (py) => 5.3 - py }; // planta -> espaço
const W = (px0, px1) => [P.X(px1), P.X(px0)]; // intervalo em x (a planta é espelhada)
const D = (py0, py1) => [P.Z(py1), P.Z(py0)];

// os retângulos da planta: [px0, px1, py0, py1, cor do acolchoado, colunas, linhas, tipo]
const BLOCOS = [
  [7.9, 18, 0, 2, M.amarelo, 5, 1],
  [6, 8, 2, 6, M.amarelo, 1, 2],
  [6, 8, 6, 10, M.vermelho, 1, 2],
  [8, 12, 2, 6, M.azul, 2, 2],
  [8, 12, 6, 10, M.vermelho, 2, 2],
  [12, 18, 2, 6, M.amarelo, 3, 2],
  [12, 18, 6, 10, M.azul, 3, 1],
  [0, 12, 10, 14, M.laranja, 6, 2],
  [12, 18, 10, 11, M.cinza, 0, 0],
  [0, 2, 14, 16.5, M.amarelo, 1, 1],
];
// a base da plataforma (lados escuros) e os acolchoados com as camas
function bloco([px0, px1, py0, py1, cor, cols, rows]) {
  const [x0, x1] = W(px0, px1);
  const [z0, z1] = D(py0, py1);
  caixa(M.base, x0, x1, 0.05, ALTURA, z0, z1);
  caixa(cor, x0, x1, ALTURA, ALTURA + ACOLCHOADO, z0, z1);
  if (!cols) return;
  const borda = 0.32;
  const cw = (x1 - x0) / cols;
  const cd = (z1 - z0) / rows;
  for (let i = 0; i < cols; i++) {
    for (let j = 0; j < rows; j++) {
      caixa(M.cama, x0 + i * cw + borda, x0 + (i + 1) * cw - borda, ALTURA + ACOLCHOADO, ALTURA + ACOLCHOADO + 0.012, z0 + j * cd + borda, z0 + (j + 1) * cd - borda);
    }
  }
}
BLOCOS.forEach(bloco);
// o quadro laranja do meio do bloco amarelo de cima
{
  const [x0, x1] = W(14, 16);
  const [z0, z1] = D(2, 6);
  caixa(M.laranja, x0 + 0.02, x1 - 0.02, ALTURA + ACOLCHOADO, ALTURA + ACOLCHOADO + 0.008, z0 + 0.02, z0 + 0.3);
  caixa(M.laranja, x0 + 0.02, x1 - 0.02, ALTURA + ACOLCHOADO, ALTURA + ACOLCHOADO + 0.008, z1 - 0.3, z1 - 0.02);
}

// as seis piscinas de espuma com as gaiolas pretas por cima
{
  const coresQuadro = [M.vermelho, M.amarelo, M.azul];
  const cubos = [];
  for (let c = 0; c < 3; c++) {
    for (let r = 0; r < 2; r++) {
      const [x0, x1] = W(c * 2, c * 2 + 2);
      const [z0, z1] = D(2 + r * 4, 6 + r * 4);
      caixa(M.base, x0, x1, 0.05, ALTURA, z0, z1);
      // o quadro colorido em volta
      caixa(coresQuadro[c], x0, x1, ALTURA, ALTURA + ACOLCHOADO, z0, z0 + 0.25);
      caixa(coresQuadro[c], x0, x1, ALTURA, ALTURA + ACOLCHOADO, z1 - 0.25, z1);
      caixa(coresQuadro[c], x0, x0 + 0.25, ALTURA, ALTURA + ACOLCHOADO, z0, z1);
      caixa(coresQuadro[c], x1 - 0.25, x1, ALTURA, ALTURA + ACOLCHOADO, z0, z1);
      for (let x = x0 + 0.42; x < x1 - 0.3; x += 0.36) {
        for (let z = z0 + 0.42; z < z1 - 0.3; z += 0.36) {
          const q = new THREE.Quaternion().setFromEuler(new THREE.Euler((sorte() - 0.5) * 0.5, sorte() * PI, (sorte() - 0.5) * 0.5));
          cubos.push({ m: new THREE.Matrix4().compose(V(x, ALTURA + 0.02 + sorte() * 0.1, z), q, V(1, 1, 1)), cor: CORES_ESPUMA[Math.floor(sorte() * CORES_ESPUMA.length)] });
        }
      }
    }
  }
  // a piscina grande (com a parede de escalada atrás)
  const [gx0, gx1] = W(12, 18);
  const [gz0, gz1] = D(11, 16.5);
  caixa(M.base, gx0, gx1, 0.05, ALTURA, gz0, gz1);
  for (let x = gx0 + 0.25; x < gx1 - 0.2; x += 0.36) {
    for (let z = gz0 + 0.25; z < gz1 - 0.2; z += 0.36) {
      const q = new THREE.Quaternion().setFromEuler(new THREE.Euler((sorte() - 0.5) * 0.6, sorte() * PI, (sorte() - 0.5) * 0.6));
      cubos.push({ m: new THREE.Matrix4().compose(V(x, ALTURA + 0.05 + sorte() * 0.15, z), q, V(1, 1, 1)), cor: CORES_ESPUMA[Math.floor(sorte() * CORES_ESPUMA.length)] });
    }
  }
  coloridos(M.cubos, cubos, new THREE.BoxGeometry(0.32, 0.32, 0.32));

  // gaiolas: postes nos cantos das células (2 m x 4 m) e as barras de cima, a 2,6 m
  const topo = 2.6;
  const xs = [0, 2, 4, 6].map(P.X);
  const zs = [2, 6, 10].map(P.Z);
  xs.forEach((x) => zs.forEach((z) => cilindro(M.preto, V(x, ALTURA, z), V(x, topo, z), 0.045, 8)));
  xs.forEach((x) => cilindro(M.preto, V(x, topo, zs[0]), V(x, topo, zs[2]), 0.04, 8));
  zs.forEach((z) => cilindro(M.preto, V(xs[0], topo, z), V(xs[3], topo, z), 0.04, 8));
  // cordas e argolas coloridas penduradas (o percurso ninja sobre as piscinas)
  const coresCorda = [M.azul, M.vermelho, M.amarelo, M.verdeLimao];
  for (let c = 0; c < 3; c++) {
    for (let r = 0; r < 2; r++) {
      const [x0, x1] = W(c * 2, c * 2 + 2);
      const [z0, z1] = D(2 + r * 4, 6 + r * 4);
      for (let k = 0; k < 4; k++) {
        const x = x0 + 0.5 + ((k % 2) * (x1 - x0 - 1));
        const z = z0 + 0.8 + k * ((z1 - z0 - 1.6) / 3);
        cilindro(coresCorda[(c + k) % 4], V(x, topo, z), V(x, 1.45, z), 0.025, 6);
      }
    }
  }
}

// o varredor (o braço giratório) no meio do bloco vermelho
{
  const x = P.X(10);
  const z = P.Z(8);
  const y = ALTURA + ACOLCHOADO;
  cilindro(M.amarelo, V(x, y, z), V(x, y + 0.75, z), 0.2, 20);
  cilindro(M.amarelo, V(x - 1.9, y + 0.5, z), V(x + 1.9, y + 0.5, z), 0.1, 14);
  cilindro(M.laranja, V(x, y + 0.5, z - 1.9), V(x, y + 0.5, z + 1.9), 0.1, 14);
}

// as cinco enterradas (camas inclinadas até a parede com as cestas)
{
  const cores = [M.azul, M.laranja, M.verdeLimao, M.laranja, M.azul];
  const [, zFundo] = [0, P.Z(16.5)];
  const zIni = P.Z(14);
  for (let i = 0; i < 5; i++) {
    const [x0, x1] = W(2 + i * 2, 4 + i * 2);
    caixa(M.base, x0, x1, 0.05, ALTURA, zFundo, zIni);
    caixa(cores[i], x0, x1, ALTURA, ALTURA + ACOLCHOADO, zIni - 0.3, zIni);
    caixa(cores[i], x0, x0 + 0.28, ALTURA, ALTURA + ACOLCHOADO + 0.9, zFundo, zIni - 0.3);
    caixa(cores[i], x1 - 0.28, x1, ALTURA, ALTURA + ACOLCHOADO + 0.9, zFundo, zIni - 0.3);
    // a cama inclinada: sobe 1,6 m até a parede
    const comprimento = Math.hypot(zIni - 0.3 - zFundo, 1.6);
    const g = new THREE.BoxGeometry(x1 - x0 - 0.56, 0.03, comprimento);
    const m = new THREE.Matrix4().compose(
      V((x0 + x1) / 2, ALTURA + ACOLCHOADO + 0.8, (zFundo + zIni - 0.3) / 2),
      new THREE.Quaternion().setFromAxisAngle(V(1, 0, 0), Math.atan2(1.6, zIni - 0.3 - zFundo)),
      V(1, 1, 1),
    );
    por(M.camaVerde, g, m);
    // a cesta: tabela branca e o aro laranja
    const xc = (x0 + x1) / 2;
    caixa(M.branco, xc - 0.45, xc + 0.45, 2.75, 3.3, zFundo + 0.06, zFundo + 0.1);
    const aro = new THREE.TorusGeometry(0.2, 0.018, 8, 24);
    aro.rotateX(PI / 2);
    por(M.aro, aro, new THREE.Matrix4().makeTranslation(xc, 2.8, zFundo + 0.32));
  }
  // a parede do fundo das enterradas
  const [x0, x1] = W(2, 12);
  caixa(M.preto, x0, x1, ALTURA, 3.4, zFundo, zFundo + 0.06);
}

// a parede de escalada atrás da piscina grande
{
  const [x0, x1] = W(12, 18);
  const z = P.Z(16.5);
  caixa(M.base, x0, x1, ALTURA, 3.6, z, z + 0.08);
  placa(M.escalada, V((x0 + x1) / 2, (ALTURA + 3.6) / 2, z + 0.085), x1 - x0, 3.6 - ALTURA, V(0, 0, 1), V(1, 0, 0));
}

// escadas de subida (4 degraus até a plataforma); `subida` é o lado da plataforma
function escada(x0, x1, z0, z1, subida) {
  const n = 4;
  for (let k = 0; k < n; k++) {
    const h = ((k + 1) * ALTURA) / n;
    const t = k / n;
    if (subida === "-z") caixa(M.cinza, x0, x1, 0.05, h, z0, z1 - t * (z1 - z0));
    if (subida === "+x") caixa(M.cinza, x0 + t * (x1 - x0), x1, 0.05, h, z0, z1);
  }
}
escada(...W(6.1, 7.8), P.Z(2), P.Z(2) + 1.2, "-z"); // o acesso da frente, no recorte da planta
escada(P.X(18) - 1.2, P.X(18), ...D(8.6, 10), "+x"); // a do lado das quadras

// a estrutura do .3ds: postes laranja nos cantos e o quadro preto de cima, a 3,65 m
{
  const topo = 3.65;
  const contorno = [[0, 2], [7.9, 2], [7.9, 0], [18, 0], [18, 16.5], [0, 16.5]].map(([px, py]) => V(P.X(px), 0, P.Z(py)));
  for (let i = 0; i < contorno.length; i++) {
    const a = contorno[i];
    const b = contorno[(i + 1) % contorno.length];
    cilindro(M.posteLaranja, V(a.x, 0.05, a.z), V(a.x, topo, a.z), 0.05, 10);
    cilindro(M.preto, V(a.x, topo, a.z), V(b.x, topo, b.z), 0.045, 8);
    // postes intermediários nos lados longos
    const lados = Math.floor(a.distanceTo(b) / 6.5);
    for (let k = 1; k <= lados; k++) {
      const p = a.clone().lerp(b, k / (lados + 1));
      cilindro(M.posteLaranja, V(p.x, 0.05, p.z), V(p.x, topo, p.z), 0.05, 10);
    }
  }
}

/* ======================================================================
   3. O CIRCUITO KIDS, NA FRENTE DO PARQUE: pórticos laranja, deck
   vermelho em dois andares, obstáculos, redes amarelas, painéis do X,
   e na ponta o tobogã caindo na piscina de bolinhas
   ====================================================================== */
{
  const z0 = 6.3;
  const z1 = 8.4;
  const xs = [1.2, 4.2, 7.2, 10.2, 13.2, 16.2];
  const alto = 2.8;
  xs.forEach((x) => [z0, z1].forEach((z) => cilindro(M.posteLaranja, V(x, 0.05, z), V(x, alto, z), 0.05, 10)));
  // arcos laranja no alto dos pórticos
  xs.forEach((x, i) => {
    if (i % 2) return;
    const arco = new THREE.TorusGeometry((z1 - z0) / 2, 0.05, 8, 20, PI);
    arco.rotateY(PI / 2);
    por(M.posteLaranja, arco, new THREE.Matrix4().makeTranslation(x, alto, (z0 + z1) / 2));
  });
  // decks vermelhos (de baixo e de cima) e a viga de cima
  caixa(M.vermelho, xs[0], xs[5], 0.55, 0.65, z0, z1);
  caixa(M.vermelho, xs[0], xs[5], 1.75, 1.85, z0 + 0.5, z1 - 0.5);
  cilindro(M.posteLaranja, V(xs[0], alto, z0), V(xs[5], alto, z0), 0.04, 8);
  cilindro(M.posteLaranja, V(xs[0], alto, z1), V(xs[5], alto, z1), 0.04, 8);
  // obstáculos: pilares, cunhas e cones coloridos sobre os decks
  const coresObs = [M.verdeLimao, M.amarelo, M.azul, M.laranja];
  for (let k = 0; k < 14; k++) {
    const x = xs[0] + 0.6 + k * ((xs[5] - xs[0] - 1.2) / 13);
    const cor = coresObs[k % 4];
    if (k % 3 === 0) cilindro(cor, V(x, 0.65, 7.35), V(x, 1.15, 7.35), 0.16, 14);
    else if (k % 3 === 1) {
      const cunha = new THREE.CylinderGeometry(0.0, 0.35, 0.5, 3);
      por(cor, cunha, new THREE.Matrix4().makeTranslation(x, 2.1, 7.35));
    } else cilindro(cor, V(x, 1.85, 7.35), V(x, 2.35, 7.35), 0.12, 12);
  }
  // redes amarelas de escalada (grades inclinadas) entre alguns pórticos
  [[xs[1], xs[2]], [xs[3], xs[4]]].forEach(([xa, xb]) => {
    for (let i = 0; i <= 8; i++) {
      const x = xa + 0.1 + ((xb - xa - 0.2) * i) / 8;
      cilindro(M.amarelo, V(x, 0.65, z1 + 0.5), V(x, 1.8, z1 - 0.3), 0.015, 5);
    }
    for (let j = 0; j <= 5; j++) {
      const t = j / 5;
      const y = 0.65 + 1.15 * t;
      const z = z1 + 0.5 - 0.8 * t;
      cilindro(M.amarelo, V(xa + 0.1, y, z), V(xb - 0.1, y, z), 0.015, 5);
    }
  });
  // os painéis do X nas pontas
  [xs[0], xs[5]].forEach((x) => {
    placa(M.painelX, V(x, 1.6, z1 + 0.06), 1.0, 1.0, V(0, 0, 1), V(1, 0, 0));
    placa(M.painelX, V(x, 1.6, z0 - 0.06), 1.0, 1.0, V(0, 0, -1), V(-1, 0, 0));
  });
  // um banco vermelho na frente
  caixa(M.vermelho, 9, 11.5, 0.05, 0.5, 9.6, 10.1);

  // o tobogã em espiral e a piscina de bolinhas
  const cx = 17.8;
  const cz = 9.4;
  const pontos = [V(xs[5], 2.0, 7.35), V(17.2, 2.0, 7.9)];
  for (let i = 0; i <= 36; i++) {
    const t = i / 36;
    const a = -PI / 2 + t * PI * 3;
    pontos.push(V(cx + 0.75 * Math.cos(a), 1.95 - t * 1.25, cz + 0.75 * Math.sin(a)));
  }
  const curva = new THREE.CatmullRomCurve3(pontos);
  const parte = (t0, t1, nome) => {
    const sub = new THREE.CatmullRomCurve3(Array.from({ length: 30 }, (_, k) => curva.getPoint(t0 + (t1 - t0) * (k / 29))));
    por(nome, new THREE.TubeGeometry(sub, 70, 0.33, 18, false));
  };
  parte(0, 0.35, M.tuboAmarelo);
  parte(0.35, 0.68, M.tuboLaranja);
  parte(0.68, 1, M.tuboAmarelo);
  // a torre do tobogã
  [[16.7, 8.4], [16.7, 9.9], [18.95, 8.4], [18.95, 9.9]].forEach(([x, z]) => cilindro(M.preto, V(x, 0.05, z), V(x, 2.6, z), 0.04, 8));
  // a piscina de bolinhas
  const [bx0, bx1, bz0, bz1] = [16.6, 19.0, 9.9, 11.0];
  caixa(M.vermelho, bx0, bx1, 0.05, 0.6, bz1 - 0.1, bz1);
  caixa(M.amarelo, bx0, bx1, 0.05, 0.6, bz0, bz0 + 0.1);
  caixa(M.azul, bx0, bx0 + 0.1, 0.05, 0.6, bz0, bz1);
  caixa(M.azul, bx1 - 0.1, bx1, 0.05, 0.6, bz0, bz1);
  const bolas = [];
  for (let x = bx0 + 0.18; x < bx1 - 0.12; x += 0.17) {
    for (let z = bz0 + 0.18; z < bz1 - 0.12; z += 0.17) {
      bolas.push({ m: new THREE.Matrix4().makeTranslation(x + (sorte() - 0.5) * 0.04, 0.45 + sorte() * 0.08, z + (sorte() - 0.5) * 0.04), cor: CORES_ESPUMA[Math.floor(sorte() * 5)] });
    }
  }
  coloridos(M.bolinhas, bolas, new THREE.IcosahedronGeometry(0.085, 1));
}

/* ======================================================================
   4. A ÁREA DAS QUADRAS (altura 2,90 m): campo e basquete enjaulados,
   as duas arenas de panna e a pista de 14 m
   ====================================================================== */
{
  const alto = 2.9;
  const x0 = -17;
  const xMeio = -9;
  const x1 = -2;
  const zFundo = -11;
  const zMeio = -7;
  const zFrente = -3;
  // pisos: grama no fundo, quadra de madeira na frente (8 m + 7 m)
  piso(M.grama, x0, xMeio, zFundo, zMeio, 0.06);
  piso(M.grama, xMeio, x1, zFundo, zMeio, 0.06);
  piso(M.quadra, x0, xMeio, zMeio, zFrente, 0.06);
  piso(M.quadra, xMeio, x1, zMeio, zFrente, 0.06);
  // gols pequenos (no fundo de cada campinho) e a parede do chute ao gol
  const gol = (xc, z, sentido) => {
    const largura = 1.6;
    const altura = 1.0;
    cilindro(M.branco, V(xc - largura / 2, 0.06, z), V(xc - largura / 2, altura, z), 0.04, 8);
    cilindro(M.branco, V(xc + largura / 2, 0.06, z), V(xc + largura / 2, altura, z), 0.04, 8);
    cilindro(M.branco, V(xc - largura / 2, altura, z), V(xc + largura / 2, altura, z), 0.04, 8);
    placa(M.vidro, V(xc, altura / 2, z - sentido * 0.45), largura, altura, V(0, 0, sentido), V(sentido, 0, 0));
  };
  gol(-15, zFundo + 0.5, 1);
  gol(-11, zFundo + 0.5, 1);
  gol(-3.5, zFundo + 0.5, 1);
  caixa(M.preto, -8.7, -5.3, 0.06, 2.2, zFundo + 0.05, zFundo + 0.15);
  placa(M.poster, V(-7, 1.15, zFundo + 0.16), 3.4, 2.1, V(0, 0, 1), V(1, 0, 0));
  // cestas nas pontas das quadras de basquete
  const cesta = (x, sentido) => {
    const z = (zMeio + zFrente) / 2;
    cilindro(M.preto, V(x, 0.06, z), V(x, 2.6, z), 0.05, 8);
    caixa(M.branco, x + sentido * 0.08, x + sentido * 0.12, 2.3, 2.9, z - 0.5, z + 0.5);
    const aro = new THREE.TorusGeometry(0.2, 0.018, 8, 24);
    aro.rotateX(PI / 2);
    por(M.aro, aro, new THREE.Matrix4().makeTranslation(x + sentido * 0.35, 2.4, z));
  };
  cesta(x0 + 0.1, 1);
  cesta(xMeio - 0.1, -1);
  cesta(xMeio + 0.1, 1);
  cesta(x1 - 0.1, -1);
  // a gaiola: postes, barras de cima e a tela escura dos lados
  const xs = [x0, -13, xMeio, -5.5, x1];
  const zs = [zFundo, zMeio, zFrente];
  xs.forEach((x) => zs.forEach((z) => cilindro(M.preto, V(x, 0.05, z), V(x, alto, z), 0.04, 8)));
  xs.forEach((x) => cilindro(M.preto, V(x, alto, zFundo), V(x, alto, zFrente), 0.035, 6));
  zs.forEach((z) => cilindro(M.preto, V(x0, alto, z), V(x1, alto, z), 0.035, 6));
  placa(M.vidro, V((x0 + x1) / 2, alto / 2, zFundo), x1 - x0, alto, V(0, 0, 1), V(1, 0, 0));
  placa(M.vidro, V((x0 + x1) / 2, alto / 2, zFrente), x1 - x0, alto, V(0, 0, 1), V(1, 0, 0));
  placa(M.vidro, V(x0, alto / 2, (zFundo + zFrente) / 2), zFrente - zFundo, alto, V(1, 0, 0), V(0, 0, -1));
  placa(M.vidro, V(x1, alto / 2, (zFundo + zFrente) / 2), zFrente - zFundo, alto, V(1, 0, 0), V(0, 0, -1));
  placa(M.vidro, V((x0 + x1) / 2, alto / 2, zMeio), x1 - x0, alto, V(0, 0, 1), V(1, 0, 0));

  // as duas arenas de panna (5 m), com a bola
  [-12.5, -6.5].forEach((xc) => {
    const zc = 2.4;
    const chao = new THREE.CircleGeometry(2.5, 48);
    chao.rotateX(-PI / 2);
    por(M.terra, chao, new THREE.Matrix4().makeTranslation(xc, 0.07, zc));
    const parede = new THREE.CylinderGeometry(2.55, 2.55, 0.55, 64, 1, true);
    por(M.bordaPanna, parede, new THREE.Matrix4().makeTranslation(xc, 0.33, zc));
    const borda = new THREE.TorusGeometry(2.55, 0.05, 8, 64);
    borda.rotateX(PI / 2);
    por(M.verdeBorda, borda, new THREE.Matrix4().makeTranslation(xc, 0.6, zc));
    esfera(M.branco, V(xc + 0.4, 0.18, zc - 0.3), 0.11, 14);
  });

  // a pista de 2 m x 14 m, com a chegada quadriculada
  const pista = new THREE.PlaneGeometry(2, 14);
  pista.rotateX(-PI / 2);
  por(M.pista, pista, new THREE.Matrix4().makeTranslation(-18.4, 0.06, -4));
  caixa(M.preto, -18.8, -18.0, 0.05, 1.1, -11.2, -10.9); // o painel de largada
}

/* ======================================================================
   MONTAGEM FINAL: junta por material, centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "espaco-esportivo-modelo-1";
cena.add(raiz);
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
  g = mergeVertices(g, 1e-4);
  const malha = new THREE.Mesh(g, mat);
  malha.name = nome;
  Object.assign(malha.userData, extras);
  raiz.add(malha);
}
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 100) / 100);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);

// vistas para conferir e as fotos do cadastro
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1600, 1000);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.body.append(renderer.domElement);
cena.add(new THREE.HemisphereLight("#ffffff", "#8899aa", 1.7));
const sol = new THREE.DirectionalLight("#ffffff", 2.0);
sol.position.set(12, 30, 18);
cena.add(sol);
const camera = new THREE.PerspectiveCamera(32, 1600 / 1000, 0.1, 400);
window.ver = (x, y, z, alvo = [0, 0, 0], fundo = "#0b1a3a") => {
  cena.background = new THREE.Color(fundo);
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.88);
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
