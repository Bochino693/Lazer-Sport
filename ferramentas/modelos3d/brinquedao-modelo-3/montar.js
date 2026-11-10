// Monta o Brinquedão Modelo 3 (o brinquedão em L: 10 m × 5,20 m, altura de
// 3,75 m) em three.js e exporta um .glb.
//
// Aqui não há .3ds da fábrica: tudo sai das três imagens do projeto que o
// cliente mandou (a vista de frente, a planta e a perspectiva).
//  - da planta: o L -- a barra de 10 m × 2 m encostada no fundo e a perna de
//    1 m de largura que sai da ponta esquerda e avança 3,20 m na frente --,
//    os módulos de 1 m (10 colunas × 2 fileiras na barra) e o piso de cada
//    módulo do 2º andar; a torre da ponta da perna com o piso de duas cores
//    na diagonal, a passarela de rede quadriculada e, na ponta direita, o
//    topo do tobogã e a piscina de bolinhas -- DENTRO da barra: os últimos
//    2 m dela, nos 2 m de fundo, com só o piso amarelo de trás em cima. Vista
//    de cima, o objeto é exatamente o L (só a escadinha sai 35 cm na frente);
//  - da vista de frente: as alturas (o piso do 2º andar a 1,90 m, 1,85 m de
//    pé-direito em cima, 3,75 m no total), as três barraquinhas com o toldo
//    listrado, o fliperama em cubo e a mesa de fliperama embaixo; em cima,
//    as cunhas de espuma sob o painel magenta, a bola-pêndulo, os sacos de
//    pancada, o balanço e o saco azul do módulo amarelo; no alto da ponta
//    direita, o painel da janela redonda, e embaixo o tobogã em espiral de
//    tubo fechado, em gomos coloridos, dentro da piscina de bolinhas, com a
//    escadinha amarela colada na frente dela;
//  - da perspectiva: a escada da torre em zigue-zague (as plataformas
//    amarelas e azuis, os degraus brancos), as redes em onda acima dela e a
//    passarela a ~1,9 m ligando a torre à barra.
// As figuras de filme e de jogo das imagens NÃO entram: a arte das máquinas e
// das barraquinhas é genérica (estrelas, planetas, disco voador, pixels).
//
// Coordenadas de trabalho (as mesmas dos .3ds dos outros brinquedões): x ao
// longo da barra (da esquerda para a direita de quem olha de frente), y para
// o FUNDO (y = 0 é a ponta da perna), z para cima, em milímetros. No fim tudo
// vira metros, Y para cima e a frente em +Z, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
let semente = 7;
const sorte = () => ((semente = (semente * 16807) % 2147483647) / 2147483647);

// ---------- as medidas (mm) ----------
const L = 10000; // a barra: 10 módulos de 1 m
const FUNDO = 5200; // o fundo do L
const BARRA = 3200; // a frente da barra (de 0 a 3200 é a perna)
const MEIO = 4200; // entre a fileira da frente e a de trás da barra
const PERNA = 1000; // a largura da perna
const TORRE = 1000; // a torre: o primeiro metro da perna, na ponta
const ANDAR = 1900; // o piso do 2º andar
const TOPO = 3750; // a altura total
const RT = 30; // o raio dos tubos das colunas
const TAMPA = 36; // a tampa arredondada; as colunas de fora ficam para dentro dela (o objeto mede 10 m cravados)
const ZT = TOPO - 50; // as travessas de cima
const ZP = ANDAR - 125; // as travessas embaixo do piso do 2º andar (a faixa branca sob cada piso)
// as linhas de colunas: ao longo da barra (11), as três da barra e as da perna
const XB = Array.from({ length: 11 }, (_, i) => Math.min(L - TAMPA, Math.max(TAMPA, i * 1000)));
const YB = [BARRA, MEIO, FUNDO - TAMPA];
const XP = [TAMPA, PERNA];
const YP = [TAMPA, TORRE, 2100];
const FRENTE = [BARRA, MEIO]; // a fileira da frente da barra (y)
const TRAS = [MEIO, FUNDO]; // a de trás

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map(); // nome -> { material, geometrias: [], extras }
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
// texturas desenhadas (vão dentro do .glb, em PNG; pequenas, que o .glb tem de ser leve)
function tela(w, h, pintar, repetir = true) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  pintar(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  if (repetir) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// a paleta das imagens do projeto
const COR = {
  branco: "#f3f5f8", travessa: "#e2e6ec", azul: "#5b6cff", lilas: "#a58cff", magenta: "#ff1fc2",
  amarelo: "#ffe600", laranja: "#ff9a1a", verdeLimao: "#9be22d", azulClaro: "#36aaff", azulBebe: "#9edcff",
  rosa: "#ff79cd", vermelho: "#ee2b36", bordo: "#7d1430", roxo: "#6c2bd9", preto: "#17181d",
  creme: "#fff3dc", pao: "#c88a3e", fundoPiscina: "#2b3fae",
};

// a rede colorida: a malha branca (o material dá a cor), o resto transparente
const texRede = tela(64, 64, (g, w, h) => {
  g.clearRect(0, 0, w, h);
  g.fillStyle = "#ffffff";
  for (const k of [0, 32]) {
    g.fillRect(k - 5, 0, 10, h);
    g.fillRect(0, k - 5, w, 10);
  }
  g.fillRect(w - 5, 0, 5, h);
  g.fillRect(0, h - 5, w, 5);
});
// a rede da passarela: quadriculada, os quadros azuis e amarelo-limão
// alternados (a planta a pinta azul e amarela; a perspectiva, verde e azul)
const texXadrez = tela(64, 64, (g, w, h) => {
  g.clearRect(0, 0, w, h);
  g.lineWidth = 10;
  for (let i = 0; i < 2; i++) {
    for (let j = 0; j < 2; j++) {
      g.strokeStyle = (i + j) % 2 ? "#cdef1c" : COR.azul;
      g.strokeRect(i * 32 + 5, j * 32 + 5, 22, 22);
    }
  }
});
// o toldo listrado bordô e branco (uma volta da textura = 4 listras)
const listras = (g, h) => {
  for (let i = 0; i < 4; i++) {
    g.fillStyle = i % 2 ? "#f7eef1" : COR.bordo;
    g.fillRect(i * 16, 0, 16, h);
  }
};
const texToldo = tela(64, 16, (g, w, h) => listras(g, h));
// o babado do toldo: as listras com a beira em meia-lua (o resto transparente)
const texBabado = tela(64, 32, (g) => {
  g.clearRect(0, 0, 64, 32);
  listras(g, 16);
  for (let i = 0; i < 4; i++) {
    g.fillStyle = i % 2 ? "#f7eef1" : COR.bordo;
    g.beginPath();
    g.arc(i * 16 + 8, 16, 8, 0, PI);
    g.fill();
  }
});
// a parede amarela de tijolinho da padaria
const texTijolo = tela(128, 128, (g, w, h) => {
  g.fillStyle = "#e0ae17";
  g.fillRect(0, 0, w, h);
  for (let l = 0; l < 4; l++) {
    for (let c = -1; c < 3; c++) {
      const x = c * 64 + (l % 2 ? 32 : 0);
      g.fillStyle = (l + c + 4) % 3 ? "#ffd84a" : "#ffcd2e";
      g.fillRect(x + 3, l * 32 + 3, 58, 26);
    }
  }
});
// a arte espacial do fliperama em cubo: estrelas, o planeta com anel e o
// disco voador (genérica: nada de personagem)
const texArte = tela(256, 256, (g, w, h) => {
  const fundo = g.createLinearGradient(0, 0, 0, h);
  fundo.addColorStop(0, "#22074f");
  fundo.addColorStop(1, "#7a35e0");
  g.fillStyle = fundo;
  g.fillRect(0, 0, w, h);
  for (let i = 0; i < 70; i++) {
    g.fillStyle = `rgba(255,255,255,${(0.45 + sorte() * 0.55).toFixed(2)})`;
    g.beginPath();
    g.arc(sorte() * w, sorte() * h, sorte() < 0.15 ? 2.4 : 1.2, 0, PI * 2);
    g.fill();
  }
  g.fillStyle = COR.laranja;
  g.beginPath(); g.arc(70, 72, 34, 0, PI * 2); g.fill();
  g.strokeStyle = COR.amarelo; g.lineWidth = 6;
  g.beginPath(); g.ellipse(70, 72, 60, 14, -0.35, 0, PI * 2); g.stroke();
  g.fillStyle = COR.magenta;
  g.beginPath(); g.arc(212, 48, 15, 0, PI * 2); g.fill();
  // o facho de luz, a cúpula, o disco e as luzinhas
  g.fillStyle = "rgba(155,226,45,.38)";
  g.beginPath(); g.moveTo(170, 168); g.lineTo(124, 252); g.lineTo(216, 252); g.closePath(); g.fill();
  g.fillStyle = "#7fe8ff";
  g.beginPath(); g.ellipse(170, 152, 26, 22, 0, PI, PI * 2); g.fill();
  g.fillStyle = "#c9ced6";
  g.beginPath(); g.ellipse(170, 160, 60, 16, 0, 0, PI * 2); g.fill();
  g.fillStyle = COR.amarelo;
  for (const dx of [-38, -13, 13, 38]) { g.beginPath(); g.arc(170 + dx, 162, 4, 0, PI * 2); g.fill(); }
}, false);
// a tela dos fliperamas: um quebra-blocos de pixels (genérico)
const texJogo = tela(128, 96, (g, w, h) => {
  g.fillStyle = "#05060f";
  g.fillRect(0, 0, w, h);
  const cores = [COR.magenta, COR.amarelo, COR.laranja, COR.azulClaro, COR.verdeLimao];
  for (let l = 0; l < 4; l++) for (let c = 0; c < 10; c++) { g.fillStyle = cores[(l + c) % 5]; g.fillRect(6 + c * 12, 10 + l * 7, 10, 5); }
  g.fillStyle = "#ffffff";
  g.fillRect(52, 84, 24, 4);
  g.fillRect(72, 60, 4, 4);
  for (let i = 0; i < 14; i++) { g.fillStyle = "rgba(255,255,255,.5)"; g.fillRect(Math.floor(sorte() * w), 44 + Math.floor(sorte() * 34), 2, 2); }
}, false);

const M = {
  estrutura: material("estrutura-branca", { color: COR.branco, roughness: 0.35 }),
  travessas: material("travessas", { color: COR.travessa, roughness: 0.4 }),
  espuma: material("espuma-branca", { color: "#fafbfd", roughness: 0.75 }),
  azul: material("azul", { color: COR.azul }),
  magenta: material("magenta", { color: COR.magenta }),
  amarelo: material("amarelo", { color: COR.amarelo }),
  laranja: material("laranja", { color: COR.laranja }),
  azulClaro: material("azul-claro", { color: COR.azulClaro }),
  verde: material("verde-limao", { color: COR.verdeLimao }),
  vermelho: material("vermelho", { color: COR.vermelho }),
  rosa: material("rosa", { color: COR.rosa }),
  lilas: material("lilas", { color: COR.lilas }),
  azulBebe: material("azul-bebe", { color: COR.azulBebe }),
  roxo: material("roxo", { color: COR.roxo }),
  preto: material("preto", { color: COR.preto, roughness: 0.4 }),
  creme: material("tampo-creme", { color: COR.creme, roughness: 0.5 }),
  pao: material("paes", { color: COR.pao, roughness: 0.8 }),
  cordas: material("cordas", { color: "#c9ced6", roughness: 0.85 }),
  ferragem: material("ferragem", { color: "#8d949e", roughness: 0.4, metalness: 0.5 }),
  fundoPiscina: material("fundo-da-piscina", { color: COR.fundoPiscina, roughness: 0.7 }),
  bolinhas: material("bolinhas", { vertexColors: true, roughness: 0.35 }),
  premios: material("premios", { vertexColors: true, roughness: 0.6 }),
  vidro: material("vidro", { color: "#d8ecff", transparent: true, opacity: 0.22, depthWrite: false, roughness: 0.05, side: THREE.DoubleSide }),
  redeAzul: material("rede-azul", { color: COR.azul, map: texRede, alphaTest: 0.5, side: THREE.DoubleSide }),
  redeAmarela: material("rede-amarela", { color: COR.amarelo, map: texRede, alphaTest: 0.5, side: THREE.DoubleSide }),
  passarela: material("rede-da-passarela", { map: texXadrez, alphaTest: 0.5, side: THREE.DoubleSide }),
  toldo: material("toldo-listrado", { map: texToldo, roughness: 0.7, side: THREE.DoubleSide }),
  babado: material("babado-do-toldo", { map: texBabado, alphaTest: 0.5, roughness: 0.7, side: THREE.DoubleSide }),
  tijolo: material("tijolinho-amarelo", { map: texTijolo, roughness: 0.8 }),
  arte: material("arte-espacial", { map: texArte, roughness: 0.5 }),
  jogo: material("tela-do-jogo", { map: texJogo, emissive: "#ffffff", emissiveMap: texJogo, emissiveIntensity: 0.85, roughness: 0.3 }),
  // os gomos do tobogã: por dentro também (o passeio desce por dentro dele)
  gomos: ["azul", "magenta", "amarelo", "laranja"].map((c) => material(`toboga-${c}`, { color: COR[c], roughness: 0.3, side: THREE.DoubleSide })),
};
// a tela de proteção: clara, translúcida, com a trama da rede (como a dos outros brinquedões)
M.tela = material("tela-protecao", {
  color: "#e9f6ff", transparent: true, depthWrite: false, side: THREE.DoubleSide, roughness: 0.2,
  map: tela(32, 32, (g, w, h) => {
    g.fillStyle = "rgba(255,255,255,.07)"; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(255,255,255,.2)";
    g.fillRect(0, 0, w, 1); g.fillRect(0, 0, 1, h);
  }),
});

// ---------- peças básicas (em mm) ----------
// as coordenadas do mundo viram a coordenada da textura (a textura repete a
// cada `passo` mm e continua de uma caixa para a outra: os tijolinhos)
function uvPlano(g, passo) {
  const p = g.attributes.position;
  const n = g.attributes.normal;
  const uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i)), az = Math.abs(n.getZ(i));
    if (ax >= ay && ax >= az) uv.setXY(i, p.getY(i) / passo, p.getZ(i) / passo);
    else if (ay >= az) uv.setXY(i, p.getX(i) / passo, p.getZ(i) / passo);
    else uv.setXY(i, p.getX(i) / passo, p.getY(i) / passo);
  }
}
function caixa(nome, x0, x1, y0, y1, z0, z1, passo = 0) {
  const g = new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0));
  g.applyMatrix4(new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
  if (passo) uvPlano(g, passo);
  por(nome, g);
}
// espuma: a caixa com as quinas arredondadas (mureta, degraus, painéis)
function almofada(nome, x0, x1, y0, y1, z0, z1, raio = 35) {
  const g = new RoundedBoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0), 2, raio);
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function cilindro(nome, a, b, r, lados = 12, aberto = false) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, aberto);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, V(1, 1, 1)));
}
function esfera(nome, c, r, w = 14, h = 8) {
  por(nome, new THREE.SphereGeometry(r, w, h), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
}
// um quadrilátero a-b-c-d; `passo` (mm) faz a textura repetir: um número
// para os dois lados, ou [ao longo de a-b, ao longo de a-d] (0 = uma vez)
function quad(nome, a, b, c, d, passo = 0) {
  const [pu, pv] = Array.isArray(passo) ? passo : [passo, passo];
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute([a, b, c, d].flatMap((p) => [p.x, p.y, p.z]), 3));
  const su = pu ? a.distanceTo(b) / pu : 1;
  const sv = pv ? a.distanceTo(d) / pv : 1;
  g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, su, 0, su, sv, 0, sv], 2));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  g.computeVertexNormals();
  por(nome, g);
}
// um painel em pé no plano x = cte ou y = cte (o de y = cte olha para a frente)
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
// uma forma desenhada de frente (no plano XZ: x -> x, y da forma -> z),
// com a espessura para o fundo, de y0 a y0 + espessura
const DE_FRENTE = () => new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0));
function perfil(nome, pontos, y0, espessura) {
  const forma = new THREE.Shape(pontos.map(([x, z]) => new THREE.Vector2(x, z)));
  por(nome, new THREE.ExtrudeGeometry(forma, { depth: espessura, bevelEnabled: false }), DE_FRENTE().setPosition(0, y0 + espessura, 0));
}
// bolinhas e prêmios coloridos: uma geometria só, com a cor em cada vértice
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
function travessa(xa, ya, xb, yb, z, r = 24) {
  cilindro(M.travessas, V(xa, ya, z), V(xb, yb, z), r, 8, true);
}
// pendurado: a travessa de cima (ao longo de y, de uma fileira à outra), a corda e a peça
function pendurar(x, y, zPeca, yTravessa = FRENTE) {
  cilindro(M.ferragem, V(x, yTravessa[0], ZT), V(x, Math.min(yTravessa[1], FUNDO - TAMPA), ZT), 16, 6, true);
  cilindro(M.cordas, V(x, y, ZT), V(x, y, zPeca), 12, 6, true);
}

/* ======================================================================
   1. A ESTRUTURA: as colunas e as travessas brancas, nos módulos de 1 m
   ====================================================================== */
const colunas = [];
for (const x of XB) for (const y of YB) colunas.push([x, y]);
for (const x of XP) for (const y of YP) colunas.push([x, y]);
for (const [x, y] of colunas) {
  cilindro(M.estrutura, V(x, y, 0), V(x, y, TOPO - TAMPA), RT, 10, true);
  esfera(M.estrutura, V(x, y, TOPO - TAMPA), TAMPA, 10, 6); // a tampa arredondada
}
// Embaixo do piso, no vão do tobogã (a frente dos módulos 9 e 10 e o fundo do
// 10º não têm piso), as duas travessas que cruzariam a espiral não existem:
// a do meio no 10º e a da coluna do meio da piscina para a frente.
const noVaoDoTobogan = (xa, ya, xb, yb, z) => z === ZP && ((ya === MEIO && yb === MEIO && xa >= 9000) || (xa === 9000 && xb === 9000 && ya === BARRA));
for (const z of [ZT, ZP]) {
  for (const y of YB) for (let i = 0; i < 10; i++) if (!noVaoDoTobogan(XB[i], y, XB[i + 1], y, z)) travessa(XB[i], y, XB[i + 1], y, z);
  for (const x of XB) {
    if (!noVaoDoTobogan(x, YB[0], x, YB[1], z)) travessa(x, YB[0], x, YB[1], z);
    travessa(x, YB[1], x, YB[2], z);
  }
  for (const x of XP) { travessa(x, YP[0], x, YP[1], z); travessa(x, YP[1], x, YP[2], z); travessa(x, YP[2], x, BARRA, z); }
  for (const y of YP) travessa(XP[0], y, XP[1], y, z);
}
// rente ao chão, só no fundo e nas pontas da barra (a frente fica livre para entrar nas barraquinhas)
travessa(XB[0], YB[2], XB[10], YB[2], 80);
for (const x of [XB[0], XB[10]]) travessa(x, YB[0], x, YB[2], 80);

/* ======================================================================
   2. A TORRE E A PASSARELA (a perna do L): por ela se entra
   ====================================================================== */
// A torre de 1 m × 1 m sobe em zigue-zague: quatro plataformas em triângulo,
// alternando as duas metades da diagonal -- amarela, azul, azul, amarela, de
// baixo para cima. De cima se vê o piso de duas cores na diagonal (a azul de
// 1,40 m e a amarela de 1,90 m), como na planta; de frente, as bordas e os
// dois blocos de baixo são os degraus brancos da vista de frente.
const FRENTE_DIR = [[0, 0], [PERNA, 0], [PERNA, TORRE]]; // a metade da frente (e da direita)
const FUNDO_ESQ = [[0, 0], [0, TORRE], [PERNA, TORRE]]; // a de trás (encosta na passarela)
const PLATAFORMAS = [[FRENTE_DIR, 450, M.amarelo], [FUNDO_ESQ, 900, M.azul], [FRENTE_DIR, 1400, M.azul], [FUNDO_ESQ, ANDAR, M.amarelo]];
PLATAFORMAS.forEach(([metade, z, cor], i) => {
  const base = i < 2 ? 0 : z - 110; // as duas de baixo são blocos de espuma até o chão
  laje(M.espuma, metade, base, z - 45 - base);
  laje(cor, metade, z - 45, 45);
});
// o que segura a plataforma de 1,40 m (na frente e no lado direito da torre)
travessa(XP[0], YP[0], XP[1], YP[0], 1265, 22);
travessa(XP[1], YP[0], XP[1], YP[1], 1265, 22);
// As redes em onda acima da escada: três faixas (azul, amarela, azul) com as
// beiras em onda, encaixadas em zigue-zague, cada uma curvada para dentro
// como uma rampa de rede -- na frente e nos dois lados da torre.
function ondas(origem, eixo, comprimento, paraDentro) {
  const A = 110, B = 75, faixas = 3;
  const z0 = ANDAR + 50 + A, z1 = ZT - A;
  const beira = (j, u) => z0 + ((z1 - z0) * j) / faixas + A * Math.sin(3 * PI * u + j * PI);
  for (let k = 0; k < faixas; k++) {
    const nu = 18, nv = 5, pos = [], uv = [], idx = [];
    for (let i = 0; i <= nu; i++) {
      for (let j = 0; j <= nv; j++) {
        const u = i / nu, v = j / nv;
        const z = beira(k, u) + (beira(k + 1, u) - beira(k, u)) * v;
        const p = origem.clone().addScaledVector(eixo, u * comprimento).addScaledVector(paraDentro, B * Math.sin(PI * v)).setZ(z);
        pos.push(p.x, p.y, p.z);
        uv.push((u * comprimento) / 130, z / 130);
      }
    }
    for (let i = 0; i < nu; i++) {
      for (let j = 0; j < nv; j++) {
        const a = i * (nv + 1) + j, b = a + nv + 1;
        idx.push(a, b, b + 1, a, b + 1, a + 1);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    por(k % 2 ? M.redeAmarela : M.redeAzul, g);
  }
}
ondas(V(TAMPA, TAMPA + 45, 0), V(1, 0, 0), PERNA - TAMPA, V(0, 1, 0)); // a frente
ondas(V(TAMPA + 45, TAMPA, 0), V(0, 1, 0), TORRE - TAMPA, V(1, 0, 0)); // o lado esquerdo
ondas(V(PERNA - 45, TAMPA, 0), V(0, 1, 0), TORRE - TAMPA, V(-1, 0, 0)); // o lado direito
// embaixo, a torre tem tela nos lados e, na frente, acima da entrada (a
// criança sobe pela frente, no bloco amarelo)
painelX(M.tela, TAMPA - 20, TAMPA, TORRE, 120, ANDAR, 100);
painelX(M.tela, PERNA + 20, TAMPA, TORRE, 120, ANDAR, 100);
painelY(M.tela, TAMPA - 20, TAMPA, PERNA, 1000, ANDAR, 100);
// A passarela de rede (a ~1,90 m, da torre até a barra): a rede quadriculada
// azul e amarela segue para dentro do 1º módulo da frente da barra (o começo
// da perna, na planta); as beiras dela e as telas dos dois lados
quad(M.passarela, V(0, TORRE, ANDAR - 10), V(PERNA, TORRE, ANDAR - 10), V(PERNA, MEIO, ANDAR - 10), V(0, MEIO, ANDAR - 10), 200);
for (const x of XP) travessa(x, TORRE, x, MEIO, ANDAR - 20, 18);
painelX(M.tela, TAMPA - 20, TORRE, BARRA, ANDAR, ZT - 20, 100);
painelX(M.tela, PERNA + 20, TORRE, BARRA, ANDAR, ZT - 20, 100);

/* ======================================================================
   3. OS PISOS DO 2º ANDAR (1,90 m), módulo por módulo, como na planta
   ====================================================================== */
const piso = (cor, x0, x1, [y0, y1]) => caixa(cor, x0, x1, y0, y1, ANDAR - 100, ANDAR);
const diagonal = (corA, corB, x0, x1, [y0, y1]) => {
  laje(corA, [[x0, y0], [x1, y0], [x1, y1]], ANDAR - 100, 100);
  laje(corB, [[x0, y0], [x0, y1], [x1, y1]], ANDAR - 100, 100);
};
// a fileira de trás: magenta/laranja, a base das ondas (2 a 4), a rede (5 a
// 7, abaixo), o módulo dos sacos e o amarelo de onde sai a boca do tobogã
// (8 a 9 m). Nos últimos 2 m da barra, só este tem piso: o resto é o vão
// do tobogã, que desce em espiral dentro da piscina de bolinhas.
diagonal(M.magenta, M.laranja, 0, 1000, TRAS);
piso(M.azul, 1000, 4000, TRAS);
piso(M.azul, 7000, 8000, TRAS);
piso(M.amarelo, 8000, 9000, TRAS);
// a fileira da frente: o 1º é a rede da passarela; magenta, a base azul das
// cunhas (3 a 7) e magenta (o balanço); no 9º e no 10º, o vão do tobogã
piso(M.magenta, 1000, 2000, FRENTE);
piso(M.azul, 2000, 7000, FRENTE);
piso(M.magenta, 7000, 8000, FRENTE);
// os módulos 5 a 7 de trás: piso de rede azul quadriculada, com as beiras
quad(M.redeAzul, V(4000, MEIO, ANDAR - 10), V(7000, MEIO, ANDAR - 10), V(7000, FUNDO, ANDAR - 10), V(4000, FUNDO, ANDAR - 10), 130);
travessa(4000, MEIO, 7000, MEIO, ANDAR - 20, 18);
travessa(4000, FUNDO - TAMPA, 7000, FUNDO - TAMPA, ANDAR - 20, 18);
for (const x of [4000, 5000, 6000, 7000]) travessa(x, MEIO, x, FUNDO - TAMPA, ANDAR - 20, 18);

/* ======================================================================
   4. OS OBSTÁCULOS DO 2º ANDAR
   ====================================================================== */
// as ondas da fileira de trás (2 a 4): rolos de espuma deitados de frente
// para o fundo, em listras laranja, amarela e magenta (como na planta)
{
  const cores = [M.laranja, M.amarelo, M.magenta];
  const y0 = MEIO + 40, y1 = FUNDO - TAMPA - 40;
  for (let k = 0; k < 9; k++) {
    const x = 1000 + (k + 0.5) * (3000 / 9);
    // a meia volta de cima (o eixo do cilindro é o y)
    const g = new THREE.CylinderGeometry(150, 150, y1 - y0, 16, 1, false, -PI / 2, PI);
    por(cores[k % 3], g, new THREE.Matrix4().makeTranslation(x, (y0 + y1) / 2, ANDAR));
  }
}
// O corredor de obstáculos da frente (3 a 7): as cunhas de espuma laranja,
// amarela e azul sobre a base azul, de frente para quem olha (o triângulo é
// o que se vê na vista de frente), e a passagem magenta no meio.
const CUNHAS = [2230, 2640, 3050, 3460, 3870, 4930, 5340, 5750, 6160, 6570];
const ALTURA_CUNHA = 300;
CUNHAS.forEach((c, i) => {
  perfil([M.laranja, M.amarelo, M.azulClaro][i % 3], [[c - 200, ANDAR], [c + 200, ANDAR], [c, ANDAR + ALTURA_CUNHA]], BARRA + 40, MEIO - BARRA - 80);
});
caixa(M.magenta, 4300, 4700, BARRA + 40, MEIO - 40, ANDAR, ANDAR + 40);
// a bola amarela grande, pendurada por uma corda no meio (o 6º módulo de trás)
const BOLA = { x: 5500, y: (MEIO + FUNDO) / 2, z: 2650, r: 300 };
pendurar(BOLA.x, BOLA.y, BOLA.z + BOLA.r, TRAS);
esfera(M.amarelo, V(BOLA.x, BOLA.y, BOLA.z), BOLA.r, 20, 14);
// os cinco sacos de pancada do 8º de trás (azul, vermelho, amarelo, rosa,
// azul), em zigue-zague: de frente, os cinco aparecem lado a lado. Entre a
// fileira da frente e a de trás fica o corredor de ~25 cm por onde o passeio
// passa (o amarelo 4 cm para a frente, o vermelho e o rosa 4 e 2 cm para
// trás: antes, a câmera roçava o amarelo)
const SACOS = [[7160, 4420, M.azul], [7330, 5000, M.vermelho], [7500, 4520, M.amarelo], [7670, 5000, M.rosa], [7840, 4430, M.azul]];
function saco(x, y, cor) {
  pendurar(x, y, 3150, TRAS);
  cilindro(cor, V(x, y, 3150), V(x, y, 2250), 120, 16);
  cilindro(M.ferragem, V(x, y, 3150), V(x, y, 3175), 60, 10); // a argola de cima
}
for (const [x, y, cor] of SACOS) saco(x, y, cor);
// o balanço do 8º da frente: a corda vermelha e a azul e o assento
{
  const x = 7500;
  cilindro(M.ferragem, V(x, BARRA, ZT), V(x, MEIO, ZT), 16, 6, true);
  cilindro(M.vermelho, V(x, 3500, ZT), V(x, 3500, 2400), 14, 6, true);
  cilindro(M.azul, V(x, 3900, ZT), V(x, 3900, 2400), 14, 6, true);
  almofada(M.amarelo, x - 110, x + 110, 3440, 3960, 2350, 2410, 18);
}
// o módulo amarelo da boca do tobogã: os dois sacos azuis (um atrás do
// outro: de frente parece um; de cima, as duas bolinhas azuis da planta)
saco(8400, 4450, M.azul);
saco(8400, 4950, M.azul);

/* ======================================================================
   5. AS TELAS DE PROTEÇÃO EM VOLTA DO 2º ANDAR E O PAINEL MAGENTA
   ====================================================================== */
{
  const zt = ZT - 20;
  painelY(M.tela, FUNDO - 10, 0, L, ANDAR, zt, 100); // o fundo
  painelX(M.tela, 10, BARRA, FUNDO, ANDAR, zt, 100); // a ponta esquerda
  painelX(M.tela, L - 10, BARRA, FUNDO, ANDAR, zt, 100); // a ponta direita
  // a frente: do 2º ao 9º módulo (o 1º é a passarela; o 10º, o painel da janela)
  painelY(M.tela, BARRA - 25, 1000, 8000, ANDAR, 3400, 100);
  painelY(M.tela, BARRA - 25, 8000, 9000, ANDAR, zt, 100);
  painelY(M.tela, BARRA - 25, 9000, L, ANDAR, 2500, 100); // embaixo do painel da janela
  // em volta do vão do tobogã: na beira do balanço e na frente do piso amarelo
  painelX(M.tela, 8000, BARRA, MEIO, ANDAR, zt, 100);
  painelY(M.tela, MEIO, 8000, 9000, ANDAR, zt, 100);
}
// o painel magenta comprido, no alto da frente, sobre os obstáculos
almofada(M.magenta, 1000, 8000, BARRA - 90, BARRA - 35, 3400, ZT + 10, 22);

/* ======================================================================
   6. EMBAIXO: as três barraquinhas de faz-de-conta, com o toldo listrado
   ====================================================================== */
// Cada uma ocupa um módulo e meio da fileira da frente: o balcão, a vitrine
// aberta, a testeira e o toldo. As colunas da frente passam diante delas (a
// fachada fica 6 cm para trás) e o toldo tem um vão em cada coluna.
const FACHADA = BARRA + 60;
const FIM_LOJA = MEIO - 50;
function toldo(xa, xb) {
  const cortes = XB.filter((c) => c > xa - 60 && c < xb + 60);
  let ini = xa;
  for (const c of [...cortes, Infinity]) {
    const fim = Math.min(xb, c - 45);
    if (fim - ini > 40) {
      quad(M.toldo, V(ini, BARRA - 115, 1450), V(fim, BARRA - 115, 1450), V(fim, FACHADA + 2, 1660), V(ini, FACHADA + 2, 1660), [400, 0]);
      painelY(M.babado, BARRA - 115, ini, fim, 1330, 1450, [400, 0]);
    }
    ini = Math.max(ini, c + 45);
    if (ini >= xb) break;
  }
}
function barraquinha(x0, x1, cor, passo = 0) {
  caixa(cor, x0, x1, FACHADA, FACHADA + 160, 0, 760, passo); // o balcão
  caixa(M.creme, x0, x1, BARRA + 38, FACHADA + 180, 760, 800); // o tampo
  caixa(cor, x0, x1, FACHADA, FACHADA + 40, 1400, ZP - 30, passo); // a testeira
  caixa(cor, x0, x0 + 40, FACHADA, FIM_LOJA, 0, ZP - 30, passo); // os lados
  caixa(cor, x1 - 40, x1, FACHADA, FIM_LOJA, 0, ZP - 30, passo);
  toldo(x0 + 10, x1 - 10);
}
// a 1ª, lilás, com a máquina de prêmios: a vitrine de vidro com os bonecos e a garra
barraquinha(1000, 2500, M.lilas);
{
  const x0 = 1150, x1 = 1850, y0 = 3480, y1 = 4040;
  caixa(M.magenta, x0, x1, y0, y1, 0, 790); // o gabinete
  caixa(M.vidro, x0, x1, y0, y1, 790, 1420); // a vitrine
  for (const [x, y] of [[x0, y0], [x1, y0], [x0, y1], [x1, y1]]) cilindro(M.estrutura, V(x, y, 790), V(x, y, 1420), 14, 6, true);
  caixa(M.magenta, x0 - 20, x1 + 20, y0 - 20, y1 + 20, 1420, 1560); // o letreiro de cima
  // os bonecos (bichinhos genéricos: bolas e cubos coloridos, amontoados)
  const cores = [COR.amarelo, COR.rosa, COR.azulClaro, COR.verdeLimao, COR.laranja, "#ffffff"];
  const bolas = [], cubos = [];
  for (let i = 0; i < 16; i++) {
    const x = x0 + 70 + sorte() * (x1 - x0 - 140), y = y0 + 70 + sorte() * (y1 - y0 - 140);
    const z = 790 + 55 + (i > 9 ? 70 : 0) + sorte() * 20;
    const item = { cor: cores[i % cores.length] };
    if (i % 3) bolas.push({ ...item, m: new THREE.Matrix4().makeTranslation(x, y, z) });
    else cubos.push({ ...item, m: new THREE.Matrix4().compose(V(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(0.3, 0.2, sorte() * PI)), V(1, 1, 1)) });
  }
  coloridos(M.premios, bolas, new THREE.IcosahedronGeometry(55, 1));
  coloridos(M.premios, cubos, new THREE.BoxGeometry(90, 90, 90));
  // a garra: o carrinho no alto, o cabo e as três pontas
  const g = V(1520, 3760, 1300);
  caixa(M.ferragem, g.x - 50, g.x + 50, g.y - 50, g.y + 50, 1380, 1410);
  cilindro(M.ferragem, V(g.x, g.y, 1380), g, 6, 6, true);
  for (let k = 0; k < 3; k++) {
    const a = (k * 2 * PI) / 3;
    cilindro(M.ferragem, g, V(g.x + 55 * Math.cos(a), g.y + 55 * Math.sin(a), g.z - 70), 8, 6);
  }
}
// a 2ª, de tijolinho amarelo: a padaria, com a prateleira de pães e o caixa
barraquinha(2500, 4000, M.tijolo, 400);
{
  const x0 = 2620, x1 = 3880, y0 = 3920, y1 = 4100;
  caixa(M.estrutura, x0, x0 + 30, y0, y1, 0, 1600);
  caixa(M.estrutura, x1 - 30, x1, y0, y1, 0, 1600);
  for (const z of [880, 1160, 1440]) {
    caixa(M.estrutura, x0, x1, y0, y1, z - 25, z);
    for (let x = x0 + 120; x < x1 - 80; x += 190) {
      const g = new THREE.SphereGeometry(1, 10, 6);
      por(M.pao, g, new THREE.Matrix4().compose(V(x + (sorte() - 0.5) * 30, (y0 + y1) / 2, z + 40), new THREE.Quaternion().setFromAxisAngle(V(0, 0, 1), (sorte() - 0.5) * 0.5), V(85, 55, 42)));
    }
  }
  caixa(M.preto, 3500, 3720, 3330, 3480, 800, 930); // o caixa registradora
  caixa(M.creme, 3520, 3700, 3330, 3360, 930, 1010);
  for (let x = 2700; x < 3300; x += 180) {
    // os pães no balcão
    por(M.pao, new THREE.SphereGeometry(1, 10, 6), new THREE.Matrix4().compose(V(x, 3360, 850), new THREE.Quaternion(), V(80, 50, 40)));
  }
}
// a 3ª, azul-clara: a cortina rosa, a prateleira e a cozinha de brinquedo (o fogão azul)
barraquinha(4000, 5500, M.azulBebe);
{
  // as duas bandas da cortina, franzidas, e a sanefa em cima
  const cortina = (x0, x1) => {
    const g = new THREE.PlaneGeometry(x1 - x0, 600, 14, 1);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) p.setZ(i, 25 * Math.sin((p.getX(i) / (x1 - x0)) * PI * 7));
    g.computeVertexNormals();
    // o plano XY vira o plano XZ, de frente
    por(M.rosa, g, DE_FRENTE().setPosition((x0 + x1) / 2, FACHADA + 30, 1100));
  };
  cortina(4050, 4300);
  cortina(5200, 5450);
  caixa(M.rosa, 4040, 5460, FACHADA + 10, FACHADA + 40, 1300, 1400);
  // a prateleira na parede da direita, com potes e latinhas
  caixa(M.estrutura, 5250, 5460, 3500, 4100, 1080, 1110);
  [COR.amarelo, COR.vermelho, COR.verdeLimao, COR.laranja].forEach((c, i) => {
    const nome = { [COR.amarelo]: M.amarelo, [COR.vermelho]: M.vermelho, [COR.verdeLimao]: M.verde, [COR.laranja]: M.laranja }[c];
    cilindro(nome, V(5350, 3580 + i * 140, 1110), V(5350, 3580 + i * 140, 1220 + (i % 2) * 50), 45, 12);
  });
  // o fogão azul: as quatro bocas, o forno com o vidro escuro e os botões
  const [x0, x1, y0, y1] = [4420, 4940, 3720, 4060];
  almofada(M.azul, x0, x1, y0, y1, 0, 600, 20);
  for (const [dx, dy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    cilindro(M.preto, V((x0 + x1) / 2 + dx * 120, (y0 + y1) / 2 + dy * 85, 600), V((x0 + x1) / 2 + dx * 120, (y0 + y1) / 2 + dy * 85, 615), 62, 16);
  }
  caixa(M.preto, x0 + 70, x1 - 70, y0 - 8, y0, 120, 430);
  for (let k = 0; k < 4; k++) cilindro(M.estrutura, V(x0 + 90 + k * 113, y0, 520), V(x0 + 90 + k * 113, y0 - 25, 520), 18, 8);
  almofada(M.azul, x0, x1, y1 - 30, y1, 600, 900, 12); // o espelho do fogão
}

/* ======================================================================
   7. EMBAIXO: o fliperama em cubo e a mesa de fliperama
   ====================================================================== */
// o gabinete roxo em forma de cubo, com a arte espacial dos lados, o painel
// de comando (alavanca e botões) e a tela
{
  const [x0, x1, y0, y1] = [5600, 6400, 3420, 4110];
  caixa(M.arte, x0, x1, y0, y1, 0, 760); // a base
  caixa(M.arte, x0, x1, y0, y1, 860, 1640); // o cubo de cima
  caixa(M.roxo, x0 - 10, x1 + 10, y0 - 10, y1 + 10, 1640, 1680); // o friso do alto
  // o painel de comando, saindo para quem joga
  caixa(M.preto, x0 + 10, x1 - 10, 3290, y0, 760, 860);
  cilindro(M.ferragem, V(5800, 3360, 860), V(5800, 3360, 960), 10, 6);
  esfera(M.vermelho, V(5800, 3360, 975), 32, 12, 8);
  [M.amarelo, M.azulClaro, M.magenta, M.verde].forEach((cor, k) => cilindro(cor, V(5960 + k * 85, 3360, 860), V(5960 + k * 85, 3360, 885), 26, 12));
  // a tela, um pouco para dentro do cubo
  painelY(M.preto, y0 - 4, x0 + 50, x1 - 50, 930, 1500);
  painelY(M.jogo, y0 - 6, x0 + 80, x1 - 80, 970, 1460);
}
// a mesa de fliperama (cocktail): preta, com a tela em cima e os comandos nas pontas
{
  const [x0, x1, y0, y1] = [6660, 7340, 3470, 4010];
  caixa(M.preto, x0, x1, y0, y1, 80, 700);
  caixa(M.preto, x0 + 60, x1 - 60, y0 + 60, y1 - 60, 0, 80); // o pé
  quad(M.jogo, V(x0 + 90, y0 + 70, 702), V(x1 - 90, y0 + 70, 702), V(x1 - 90, y1 - 70, 702), V(x0 + 90, y1 - 70, 702));
  for (const x of [x0 - 70, x1]) {
    caixa(M.preto, x, x + 70, y0 + 80, y1 - 80, 560, 680);
    const xc = x + 35;
    cilindro(M.ferragem, V(xc, 3640, 680), V(xc, 3640, 760), 8, 6);
    esfera(x < x0 ? M.azulClaro : M.vermelho, V(xc, 3640, 770), 26, 10, 6);
    cilindro(M.amarelo, V(xc, 3820, 680), V(xc, 3820, 700), 20, 10);
  }
}

/* ======================================================================
   8. A PONTA DIREITA (os últimos 2 m da barra): o painel da janela
      redonda, o tobogã em espiral dentro da piscina de bolinhas e a escadinha
   ====================================================================== */
// o painel amarelo da frente do 10º módulo, em cima, com o quadro laranja e
// a janela redonda (o círculo preto vazado)
{
  const x0 = 9040, x1 = 9924, z0 = 2500, z1 = ZT - 10, cx = (x0 + x1) / 2, cz = 3100, r = 330;
  const forma = new THREE.Shape();
  forma.moveTo(x0, z0); forma.lineTo(x1, z0); forma.lineTo(x1, z1); forma.lineTo(x0, z1); forma.lineTo(x0, z0);
  const furo = new THREE.Path();
  furo.absarc(cx, cz, r, 0, PI * 2, true);
  forma.holes.push(furo);
  por(M.amarelo, new THREE.ExtrudeGeometry(forma, { depth: 40, bevelEnabled: false, curveSegments: 28 }), DE_FRENTE().setPosition(0, BARRA - 35, 0));
  // o quadro laranja em volta do painel e o aro laranja da janela
  for (const [a, b, c, d] of [[x0, x1, z0, z0 + 60], [x0, x1, z1 - 60, z1], [x0, x0 + 60, z0, z1], [x1 - 60, x1, z0, z1]]) caixa(M.laranja, a, b, BARRA - 85, BARRA - 75, c, d);
  por(M.laranja, new THREE.RingGeometry(r + 40, r + 100, 36, 1), DE_FRENTE().setPosition(cx, BARRA - 77, cz));
  por(M.preto, new THREE.TorusGeometry(r + 18, 26, 8, 36), DE_FRENTE().setPosition(cx, BARRA - 80, cz));
}
// O tobogã: sai do piso amarelo de trás (8 a 9 m), pela beira da direita,
// e desce em espiral DENTRO da piscina de bolinhas -- os últimos 2 m da barra,
// nos 2 m de fundo inteiros --, em volta da coluna do meio, que é o poste
// dele: 2,25 voltas mais a boca (≈ 2,5 voltas de frente), em gomos azul,
// magenta, amarelo e laranja. A primeira volta é mais inclinada: quando a
// espiral passa por baixo do piso amarelo (uns 2/3 de volta depois da boca),
// o tubo já desceu o bastante para não bater nele. As mesmas medidas estão
// no passeio da Arena (toboganDoModelo3, em arena3d.js).
const TOBOGA = {
  cx: 9000, cy: MEIO, raio: 520, r: 250, a0: 90, voltas: 2.25,
  zTopo: 2160, quebra: 0.67, zQuebra: 1480, zFim: 550,
  entrada: [[8650, 4720, 2165], [8850, 4720, 2163]],
  saida: [[9560, 3800, 510], [9600, 3580, 480]],
};
// a altura do centro do tubo depois de `u` voltas: mais inclinada até a quebra
function alturaDoTobogan(u) {
  const { voltas, zTopo, quebra, zQuebra, zFim } = TOBOGA;
  return u <= quebra ? zTopo - ((zTopo - zQuebra) * u) / quebra : zQuebra - ((zQuebra - zFim) * (u - quebra)) / (voltas - quebra);
}
{
  const { cx, cy, raio, r, a0, voltas, entrada, saida } = TOBOGA;
  const pontos = entrada.map(([x, y, z]) => V(x, y, z));
  const passos = Math.round(voltas * 32);
  for (let i = 0; i <= passos; i++) {
    const u = (i / passos) * voltas;
    const a = ((a0 - u * 360) * PI) / 180; // de cima, no sentido do relógio
    pontos.push(V(cx + raio * Math.cos(a), cy + raio * Math.sin(a), alturaDoTobogan(u)));
  }
  pontos.push(...saida.map(([x, y, z]) => V(x, y, z)));
  const curva = new THREE.CatmullRomCurve3(pontos);
  const gomos = 14;
  for (let k = 0; k < gomos; k++) {
    const u0 = k / gomos, u1 = Math.min(1, (k + 1) / gomos + 0.003);
    const sub = new THREE.CatmullRomCurve3(Array.from({ length: 12 }, (_, j) => curva.getPointAt(u0 + (u1 - u0) * (j / 11))));
    // um gomo sim, um não, 8 mm mais fino (mais que o canto do polígono do tubo): na emenda (0,3% de sobra) as paredes não brigam nem se cruzam em dentes
    por(M.gomos[k % 4], new THREE.TubeGeometry(sub, 14, r - (k % 2) * 8, 16, false));
    // a junta branca no começo de cada gomo (o primeiro é a boca): POR FORA do
    // tubo (o anel de 16 mm encosta na parede de fora; com o raio r + 6, ele
    // entrava 1 cm no tubo e, no passeio, era um aro branco cruzando o túnel)
    const p = curva.getPointAt(u0), d = curva.getTangentAt(u0);
    por(M.estrutura, new THREE.TorusGeometry(r + 18, 16, 5, 22), new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromUnitVectors(V(0, 0, 1), d), V(1, 1, 1)));
  }
  const fim = curva.getPointAt(1), dFim = curva.getTangentAt(1);
  por(M.estrutura, new THREE.TorusGeometry(r + 18, 16, 5, 22), new THREE.Matrix4().compose(fim, new THREE.Quaternion().setFromUnitVectors(V(0, 0, 1), dFim), V(1, 1, 1)));
}
// a piscina de bolinhas (2 m × 2 m) embaixo dos últimos 2 m da barra: a
// mureta azul acolchoada, o fundo e a camada de cima das bolinhas (a coluna
// do meio, o poste do tobogã, passa por ela)
const PISCINA = { x0: 8000, x1: L, y0: BARRA, y1: FUNDO, alto: 450, borda: 120 };
{
  const { x0, x1, y0, y1, alto, borda } = PISCINA;
  almofada(M.azul, x0, x1, y0, y0 + borda, 0, alto, 40);
  almofada(M.azul, x0, x1, y1 - borda, y1, 0, alto, 40);
  almofada(M.azul, x0, x0 + borda, y0, y1, 0, alto, 40);
  almofada(M.azul, x1 - borda, x1, y0, y1, 0, alto, 40);
  caixa(M.fundoPiscina, x0 + borda, x1 - borda, y0 + borda, y1 - borda, 0, 230);
  const cores = ["#3f6dff", "#ffd60a", "#ef2b2b", "#ff6fc8"];
  const bolas = [];
  for (let x = x0 + borda + 85; x < x1 - borda - 60; x += 165) {
    for (let y = y0 + borda + 85; y < y1 - borda - 60; y += 165) {
      if (Math.hypot(x - TOBOGA.cx, y - TOBOGA.cy) < 110) continue; // a coluna do meio
      bolas.push({ m: new THREE.Matrix4().makeTranslation(x + (sorte() - 0.5) * 50, y + (sorte() - 0.5) * 50, 285 + sorte() * 50), cor: cores[Math.floor(sorte() * cores.length)] });
    }
  }
  coloridos(M.bolinhas, bolas, new THREE.IcosahedronGeometry(80, 1));
}
// a escadinha amarela de espuma, de 2 degraus, colada na frente da piscina
// (perto da ponta direita): é a única coisa que sai da frente da barra (35 cm)
const ESCADINHA = { x0: 9300, x1: 9800, y0: BARRA - 350 };
almofada(M.amarelo, ESCADINHA.x0, ESCADINHA.x1, ESCADINHA.y0, BARRA - 160, 0, 225, 35);
almofada(M.amarelo, ESCADINHA.x0, ESCADINHA.x1, BARRA - 170, BARRA, 0, PISCINA.alto, 35);

/* ======================================================================
   MONTAGEM FINAL: metros, Y para cima, a frente em +Z; junta por material,
   centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "brinquedao-modelo-3";
cena.add(raiz);
// (x, y, z) de trabalho -> (x, z, -y) em metros: rotação própria (sem espelhar)
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
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 100) / 100);
// o deslocamento que leva as coordenadas de trabalho (em metros, já viradas)
// ao objeto: o passeio da Arena usa (M3, em arena3d.js)
window.centro = { x: +centro.x.toFixed(4), chao: +caixaTotal.min.y.toFixed(4), z: +centro.z.toFixed(4) };
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
// um ponto de trabalho (mm) no objeto final, para as câmeras do gerar.cjs
window.noObjeto = (x, y, z) => [x / 1000 - centro.x, z / 1000 - caixaTotal.min.y, -y / 1000 - centro.z];

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
sol.position.set(4, 12, 8);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8, near: 1, far: 40 });
sol.shadow.bias = -0.0004;
cena.add(sol);
// as telas translúcidas e o vidro não fazem sombra (a sombra delas seria cheia)
raiz.traverse((o) => { if (o.isMesh) { o.castShadow = !o.material.transparent; o.receiveShadow = true; } });
// o chão só das vistas (não vai para o .glb): recebe a sombra
const chao = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.ShadowMaterial({ opacity: 0.2 }));
chao.rotation.x = -PI / 2;
chao.receiveShadow = true;
cena.add(chao);
const piso2 = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: "#3d4a5c", roughness: 1 }));
piso2.rotation.x = -PI / 2;
piso2.position.y = -0.002;
cena.add(piso2);
const camera = new THREE.PerspectiveCamera(34, 1600 / 1000, 0.05, 200);
window.ver = (x, y, z, alvo = [0, 1.6, 0], fundo = "#0b1a3a", fov = 34, sombra = true) => {
  cena.background = new THREE.Color(fundo);
  piso2.visible = fundo === "#0b1a3a"; // no fundo claro das fotos, só a sombra
  chao.visible = sombra;
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
// de cima, sem perspectiva, como a planta (o fundo do brinquedo para cima)
window.verCima = (largura = 12, fundo = "#0b1a3a") => {
  cena.background = new THREE.Color(fundo);
  piso2.visible = fundo === "#0b1a3a";
  chao.visible = false;
  // como a planta: sem as sombras compridas das colunas sobre os pisos
  renderer.shadowMap.enabled = false;
  cena.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
  const alto = (largura * 1000) / 1600;
  const orto = new THREE.OrthographicCamera(-largura / 2, largura / 2, alto / 2, -alto / 2, 0.1, 100);
  orto.position.set(0, 30, 0);
  orto.up.set(0, 0, -1);
  orto.lookAt(0, 0, 0);
  renderer.render(cena, orto);
  renderer.shadowMap.enabled = true;
  cena.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
// a foto do cadastro: a última vista recortada no objeto (com uma margem),
// em 16:10, 1600 × 1000, em .webp (como as dos outros objetos)
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
  const exp = new GLTFExporter();
  const glb = await exp.parseAsync(raiz, { binary: true });
  const bytes = new Uint8Array(glb);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
};
window.pronto = true;
