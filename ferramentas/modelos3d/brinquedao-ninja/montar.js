// Monta o Brinquedão Ninja (14 m: o brinquedão de 10 m e as duas camas
// elásticas de 2 m) em three.js e exporta um .glb.
//
// De onde vem cada coisa:
//  - do .3ds da fábrica (estrutura.json, feito pelo extrair.py): as colunas
//    rosa e as barras laranja, nas medidas do arquivo -- o andar de cima a
//    2,2 m, o corrimão de cima a 3,26 m, o quadro das camas e da piscina de
//    bolinhas a 0,3 m, as duas barras azuis de cima da rede em V e os
//    corrimãos rosa das entradas da frente;
//  - da imagem do projeto (vista de frente): as cores e as peças do andar de
//    cima (os cilindros pendurados, os postes com pegas, o rolo vazado rosa,
//    a rede em V verde-limão, os painéis com o X), as placas "ninja", o
//    tobogã em espiral rosa e verde-limão, a piscina de cubos com as cordas,
//    a viga azul da tirolesa, a estrela, os degraus verdes e as telas;
//  - da planta (10 m + 4 m por 2 m, altura 3,10 m): a ordem dos módulos, o
//    canto em L com os dois triângulos (azul e amarelo), a piscina de
//    bolinhas, as duas camas elásticas (a lona rosa com o círculo verde) e
//    os degraus verdes que saem na frente.
// O céu com nuvens do fundo da imagem é ilustrativo: no lugar dele, a tela
// de proteção, como no resto do brinquedo.
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
// x: o canto em L (480-1480), os módulos do andar de cima até 8360, o
// módulo vermelho (8360-10440) e as duas camas (10440-12520-14680)
const X = {
  canto0: 480, canto1: 1480, m1: 3000, poste: 3580, m2: 4520, m3: 5520, m4: 6320,
  pe: 7360, vermelho0: 8360, vermelho1: 9400, vermelho2: 10440, cama1: 12520, cama2: 14680,
};
const XS = Object.values(X);
const FRENTE = 1980, MEIO = 2965, FUNDO = 3960; // a frente do L, a frente da faixa de 1 m, o fundo
const YS = [FRENTE, MEIO, FUNDO];
const CENTRO_Y = (MEIO + FUNDO) / 2; // o meio da faixa de 1 m (o caminho do andar de cima)
const BASE = 130; // o quadro do chão da piscina de cubos
const CAMA = 300; // o quadro das camas elásticas e da piscina de bolinhas
const DEGRAU = 650, PATAMAR = 1222; // o canto em L: o degrau e o triângulo azul
const ANDAR = 2260; // o piso do andar de cima (as barras a 2,22 m)
const TETO = 3265; // o corrimão de cima
const ALTO = 3010; // as barras azuis da rede em V
const perto = (lista, v) => lista.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));

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

// as cores tiradas da imagem do projeto e da planta
const COR = {
  laranja: "#f8a515", magenta: "#e012c6", amarelo: "#f3e21b", ouro: "#f8c10e", azul: "#2f7fe8",
  azulViga: "#3f55c8", azulEscuro: "#1d3c9c", vermelho: "#e8231e", carmim: "#d4145a", rosaBloco: "#e3189c",
  lona: "#ea1fe0", verdeLimao: "#7fe41c", tambor: "#eb13ca", cilVermelho: "#e01455", cilMagenta: "#d10aae",
  cilAzul: "#1f6fe0", corda: "#a7adb4", cinzaEscuro: "#3b3f46",
};
const M = {
  colunas: material("colunas", { color: COR.magenta, roughness: 0.4 }),
  barras: material("barras-laranja", { color: COR.laranja, roughness: 0.4 }),
  azulBarra: material("barras-azuis", { color: "#4a6ef5", roughness: 0.4 }),
  amarelo: material("amarelo", { color: COR.amarelo }),
  ouro: material("amarelo-ouro", { color: COR.ouro }),
  azul: material("azul", { color: COR.azul }),
  vermelho: material("vermelho", { color: COR.vermelho }),
  carmim: material("acolchoado-carmim", { color: COR.carmim, roughness: 0.7 }),
  rosaBloco: material("bloco-rosa", { color: COR.rosaBloco, roughness: 0.7 }),
  verde: material("verde-limao", { color: COR.verdeLimao, roughness: 0.5 }),
  viga: material("viga-azul", { color: COR.azulViga, roughness: 0.45 }),
  azulEscuro: material("discos-azuis", { color: COR.azulEscuro, roughness: 0.5 }),
  cilVermelho: material("cilindro-vermelho", { color: COR.cilVermelho, roughness: 0.6 }),
  cilMagenta: material("cilindro-magenta", { color: COR.cilMagenta, roughness: 0.6 }),
  cilAzul: material("cilindro-azul", { color: COR.cilAzul, roughness: 0.6 }),
  corda: material("cordas", { color: COR.corda, roughness: 0.8 }),
  cinza: material("ferragem", { color: COR.cinzaEscuro, roughness: 0.4, metalness: 0.4 }),
  tuboRosa: material("tobogã-rosa", { color: COR.magenta, roughness: 0.3, side: THREE.DoubleSide }),
  tuboVerde: material("tobogã-verde", { color: COR.verdeLimao, roughness: 0.3, side: THREE.DoubleSide }),
  cubos: material("cubos-de-espuma", { vertexColors: true, roughness: 0.85 }),
  bolinhas: material("bolinhas", { vertexColors: true, roughness: 0.35 }),
};

// a rede verde-limão da passarela em V (a chapa com os furos quadrados)
M.rede = material("rede-verde", {
  side: THREE.DoubleSide, alphaTest: 0.5, roughness: 0.5,
  map: tela(64, 64, (g, w, h) => {
    g.fillStyle = COR.verdeLimao; g.fillRect(0, 0, w, h);
    g.clearRect(14, 14, 36, 36);
  }, true),
});
// o rolo vazado rosa (o mesmo desenho, em rosa)
M.tambor = material("rolo-vazado", {
  side: THREE.DoubleSide, alphaTest: 0.5, roughness: 0.45,
  map: tela(64, 64, (g, w, h) => {
    g.fillStyle = COR.tambor; g.fillRect(0, 0, w, h);
    g.clearRect(16, 18, 32, 28);
  }, true),
});
// a lona das camas elásticas: rosa, trançada (o losango da planta)
M.lona = material("lona-cama-elastica", {
  roughness: 0.9,
  map: tela(64, 64, (g, w, h) => {
    g.fillStyle = COR.lona; g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 3;
    g.beginPath();
    g.moveTo(0, h / 2); g.lineTo(w / 2, 0); g.lineTo(w, h / 2); g.lineTo(w / 2, h); g.closePath();
    g.stroke();
    g.fillStyle = "rgba(120,0,110,.35)";
    for (const [x, y] of [[0, 0], [w, 0], [0, h], [w, h], [w / 2, h / 2]]) { g.beginPath(); g.arc(x, y, 3, 0, PI * 2); g.fill(); }
  }, true),
}, { lona: true }); // no passeio da Arena, a cama é onde se pula
// a tela de proteção: clara, translúcida, com a trama da rede
M.tela = material("tela-protecao", {
  color: "#e9f6ff", transparent: true, depthWrite: false, side: THREE.DoubleSide, roughness: 0.2,
  map: tela(32, 32, (g, w, h) => {
    g.fillStyle = "rgba(255,255,255,.07)"; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(255,255,255,.2)";
    g.fillRect(0, 0, w, 1); g.fillRect(0, 0, 1, h);
  }, true),
});
M.telaVerde = material("tela-verde", { color: COR.verdeLimao, transparent: true, opacity: 0.45, depthWrite: false, side: THREE.DoubleSide, roughness: 0.3 });
// o painel com o X: fundo carmim, o aro azul, o disco amarelo e o X verde-limão
M.painelX = material("painel-x", {
  roughness: 0.6, side: THREE.DoubleSide,
  map: tela(256, 256, (g, w, h) => {
    g.fillStyle = "#c8155f"; g.fillRect(0, 0, w, h);
    g.fillStyle = "#2463d9"; g.beginPath(); g.arc(w / 2, h / 2, 104, 0, PI * 2); g.fill();
    g.fillStyle = "#f05a2a"; g.beginPath(); g.arc(w / 2, h / 2, 92, 0, PI * 2); g.fill();
    g.fillStyle = COR.amarelo; g.beginPath(); g.arc(w / 2, h / 2, 86, 0, PI * 2); g.fill();
    g.strokeStyle = COR.verdeLimao; g.lineWidth = 30; g.lineCap = "round";
    g.beginPath(); g.moveTo(w / 2 - 52, h / 2 - 52); g.lineTo(w / 2 + 52, h / 2 + 52);
    g.moveTo(w / 2 + 52, h / 2 - 52); g.lineTo(w / 2 - 52, h / 2 + 52); g.stroke();
  }),
});
// as placas "ninja": a amarela da frente e a rosa em pé do canto
const letreiro = (w, h, fundo, vertical) => tela(w, h, (g) => {
  g.fillStyle = fundo; g.fillRect(0, 0, w, h);
  g.textAlign = "center"; g.textBaseline = "middle";
  g.font = `900 ${vertical ? 104 : 120}px "Arial Rounded MT Bold", "Arial Black", Arial, sans-serif`;
  const escrever = (txt, x, y) => {
    g.fillStyle = "rgba(90,90,110,.55)"; g.fillText(txt, x + 5, y + 6);
    g.fillStyle = "#ffffff"; g.fillText(txt, x, y);
  };
  if (vertical) "ninja".split("").forEach((l, i) => escrever(l, w / 2, 62 + i * 98));
  else escrever("ninja", w / 2, h / 2 + 6);
});
M.placa = material("placa-ninja", { roughness: 0.6, map: letreiro(512, 160, "#f3e21b", false) });
M.placaRosa = material("placa-ninja-rosa", { roughness: 0.6, map: letreiro(128, 512, "#e012c6", true) });

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
function esfera(nome, c, r, w = 16, h = 10) {
  por(nome, new THREE.SphereGeometry(r, w, h), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
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
// um painel em pé no plano x = cte (normal ±x) ou y = cte (normal ±y)
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
let semente = 11;
const sorte = () => ((semente = (semente * 16807) % 2147483647) / 2147483647);

/* O TOBOGÃ (o tubo vem no item 5): sai do andar de cima (na metade direita
   do módulo vermelho, ao lado da coluna do meio), desce uma volta e meia em
   espiral na frente do módulo -- passando para fora da planta, como na
   imagem -- e entra na piscina de bolinhas. A espiral passa entre as colunas
   (8360 na frente e 9400 no meio) com folga de uns 4 cm: o lugar dela na
   imagem (pela câmera achada com as colunas) é esse. As mesmas medidas estão
   no passeio da Arena (toboganDoNinja, em core/static/site/arena/caminhos.js).
   Ele vem antes da estrutura porque a barra do .3ds que cruzava o tubo (a da
   frente, a 2,21 m, entre as colunas 8360 e 9400) é cortada onde ele passa. */
const TOBOGA = {
  cx: 9030, cy: 2290, raio: 400, r: 265, a0: 0, a1: -540, zTopo: ANDAR + 265, zFim: 640,
  boca: [9900, 3060], saida: [[8700, 2600, 580], [8760, 2850, 530]],
};
function curvaDoTobogan() {
  const { cx, cy, raio, a0, a1, zTopo, zFim, boca: [bx, by], saida } = TOBOGA;
  const grau = PI / 180;
  const pontos = [V(bx, by, zTopo + 5)];
  const passos = 60;
  for (let i = 0; i <= passos; i++) {
    const t = i / passos;
    const a = (a0 + (a1 - a0) * t) * grau;
    pontos.push(V(cx + raio * Math.cos(a), cy + raio * Math.sin(a), zTopo - (zTopo - zFim) * t));
  }
  pontos.push(...saida.map(([x, y, z]) => V(x, y, z)));
  return new THREE.CatmullRomCurve3(pontos);
}
// o eixo do tubo, a cada ~2 cm: para nenhuma barra passar por dentro dele
const EIXO_DO_TOBOGAN = curvaDoTobogan().getSpacedPoints(400);
/** Os pedaços da barra de a até b que ficam FORA do tubo do tobogã (com `folga` mm de sobra). */
function foraDoTobogan(a, b, folga) {
  const n = Math.max(2, Math.ceil(a.distanceTo(b) / 10));
  const fora = [];
  for (let i = 0; i <= n; i++) {
    const p = a.clone().lerp(b, i / n);
    fora.push(EIXO_DO_TOBOGAN.every((q) => q.distanceTo(p) > TOBOGA.r + folga));
  }
  const pedacos = [];
  let inicio = -1;
  for (let i = 0; i <= n + 1; i++) {
    if (i <= n && fora[i]) { if (inicio < 0) inicio = i; continue; }
    if (inicio >= 0 && i - 1 - inicio >= 6) pedacos.push([a.clone().lerp(b, inicio / n), a.clone().lerp(b, (i - 1) / n)]);
    inicio = -1;
  }
  return pedacos;
}

/* ======================================================================
   1. A ESTRUTURA DO .3DS: colunas rosa e barras laranja
   ====================================================================== */
const colunas = new Map();
for (const [x, y, z0, z1] of E.colunas) {
  const k = perto(XS, x) + ":" + perto(YS, y);
  const atual = colunas.get(k) || [Infinity, -Infinity];
  colunas.set(k, [Math.min(atual[0], z0), Math.max(atual[1], z1)]);
}
for (const [k, [z0, z1]] of colunas) {
  const [x, y] = k.split(":").map(Number);
  cilindro(M.colunas, V(x, y, z0), V(x, y, z1), 44, 14);
  esfera(M.colunas, V(x, y, z1), 52, 14, 8); // a tampa arredondada de cada coluna
}
{
  // o .3ds tem algumas barras repetidas (a mesma em dois pedaços): fica uma
  const vistas = new Set();
  for (const [xa, ya, za, xb, yb, zb] of E.barras) {
    const chave = [xa, ya, za, xb, yb, zb].map((v) => Math.round(v / 40)).join(":");
    if (vistas.has(chave)) continue;
    vistas.add(chave);
    // onde o tobogã passa, a barra acaba na parede dele (não atravessa o tubo)
    for (const [a, b] of foraDoTobogan(V(xa, ya, za), V(xb, yb, zb), 42 + 15)) cilindro(M.barras, a, b, 42, 10);
  }
}
// as barras azuis de cima da rede em V
for (const [xa, ya, za, xb, yb, zb] of E.barras_azuis) cilindro(M.azulBarra, V(xa, ya, za), V(xb, yb, zb), 40, 12);
// os corrimãos rosa das entradas da frente: sobe da borda e faz a curva para a direita
for (const [x0, x1, y, z0, z1] of E.corrimaos) {
  const r = 32, curva = 130;
  const xp = x0 + 45, zt = z1 - 45;
  const pontos = [V(xp, y, z0 + 10), V(xp, y, zt - curva)];
  for (let i = 1; i < 6; i++) {
    const a = PI - (i / 6) * (PI / 2);
    pontos.push(V(xp + curva + curva * Math.cos(a), y, zt - curva + curva * Math.sin(a)));
  }
  pontos.push(V(xp + curva, y, zt), V(x1 - 20, y, zt));
  por(M.colunas, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pontos, false, "catmullrom", 0.1), 24, r, 8, false));
}

/* ======================================================================
   2. O CANTO EM L (a entrada): degrau, o triângulo azul a 1,22 m, o
      triângulo amarelo a 2,26 m e, atrás, o piso azul do andar de cima
   ====================================================================== */
const ESP = 110; // a borda do piso, que na imagem aparece como a faixa amarela embaixo da barra
const [c0, c1] = [X.canto0, X.canto1];
// o triângulo azul da frente (em baixo) e o amarelo do fundo (em cima), como na planta
laje(M.azul, [[c0, FRENTE], [c1, FRENTE], [c0, MEIO]], PATAMAR - ESP, ESP);
laje(M.ouro, [[c1, FRENTE], [c1, MEIO], [c0, MEIO]], ANDAR - ESP, ESP);
caixa(M.azul, c0, c1, MEIO, FUNDO, ANDAR - ESP, ANDAR); // o piso azul do andar de cima, atrás
// os degraus acolchoados: do chão ao degrau, do triângulo azul ao amarelo
caixa(M.ouro, 1080, 1440, 2460, 2930, 0, DEGRAU);
caixa(M.ouro, 640, 930, 2160, 2440, PATAMAR, PATAMAR + 520);
// a placa "ninja" rosa, em pé, e o painel com o X, no lado direito do canto
quad(M.placaRosa, V(c1 + 50, 2060, 1500), V(c1 + 50, 2440, 1500), V(c1 + 50, 2440, 2160), V(c1 + 50, 2060, 2160));
painelX(M.painelX, c1 + 30, FRENTE + 50, MEIO - 50, ANDAR + 40, TETO - 40);

/* ======================================================================
   3. O ANDAR DE CIMA (2,26 m, teto baixo): pisos amarelos e as peças ninja
   ====================================================================== */
caixa(M.amarelo, c1, X.m4, MEIO, FUNDO, ANDAR - ESP, ANDAR);
caixa(M.vermelho, X.vermelho0, X.vermelho2, MEIO, FUNDO, ANDAR - ESP, ANDAR); // o módulo vermelho

// os três cilindros pendurados (vermelho e magenta na frente, o azul atrás)
{
  const pendurar = (nome, x, y, r, base) => {
    cilindro(M.cinza, V(x, MEIO, TETO - 10), V(x, FUNDO, TETO - 10), 16, 6); // a travessa de cima
    cilindro(M.corda, V(x, y, TETO - 10), V(x, y, 3150), 10, 6);
    cilindro(nome, V(x, y, 3150), V(x, y, 2440), r, 20);
    if (base) cilindro(base, V(x, y, 2470), V(x, y, 2440), r + 4, 20); // o fundo amarelo do magenta
  };
  // (o vão do meio, entre o vermelho e o azul, é por onde se passa empurrando)
  pendurar(M.cilVermelho, 1680, 3180, 190);
  pendurar(M.cilAzul, 1700, 3770, 165);
  pendurar(M.cilMagenta, 2200, 3200, 170, M.amarelo);
}
// os dois postes com as pegas (os do .3ds, a 3,58 m) e a barra rosa de cima
{
  const x = X.poste;
  cilindro(M.colunas, V(x, MEIO, 3200), V(x, FUNDO, 3200), 55, 12);
  const deLado = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), V(1, 0, 0));
  for (const [y, zs] of [[MEIO, [2520, 2960]], [FUNDO, [2740]]]) {
    for (const z of zs) por(M.barras, new THREE.CylinderGeometry(150, 150, 30, 24), new THREE.Matrix4().compose(V(x, y + (y === MEIO ? 60 : -60), z), deLado, V(1, 1, 1)));
  }
  for (const [y, z] of [[MEIO + 70, 2400], [MEIO + 70, 2830], [FUNDO - 70, 2560], [FUNDO - 70, 2980]]) {
    esfera(M.colunas, V(x - 95, y, z), 95);
    cilindro(M.colunas, V(x - 95, y, z), V(x, y, z), 32, 8);
  }
}
// o rolo vazado rosa (deitado ao longo do brinquedo) entre os painéis amarelos com o furo redondo
{
  const xa = X.m2 + 60, xb = X.m3 - 60, r = 420, zc = ANDAR + 450;
  const g = new THREE.CylinderGeometry(r, r, xb - xa, 28, 1, true);
  const uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 9, uv.getY(i) * 3.4);
  por(M.tambor, g, new THREE.Matrix4().compose(V((xa + xb) / 2, CENTRO_Y, zc), new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), V(1, 0, 0)), V(1, 1, 1)));
  const deitado = new THREE.Quaternion().setFromUnitVectors(V(0, 0, 1), V(1, 0, 0));
  for (const xp of [X.m2 + 35, X.m3 - 35]) {
    // o painel amarelo com o furo do tamanho do rolo
    const forma = new THREE.Shape();
    const meia = (FUNDO - MEIO) / 2 - 45, alto = TETO - ANDAR - 70;
    forma.moveTo(-meia, -450); forma.lineTo(meia, -450); forma.lineTo(meia, alto - 450); forma.lineTo(-meia, alto - 450); forma.lineTo(-meia, -450);
    const furo = new THREE.Path();
    furo.absarc(0, 0, r - 20, 0, PI * 2, true);
    forma.holes.push(furo);
    const placa = new THREE.ExtrudeGeometry(forma, { depth: 30, bevelEnabled: false, curveSegments: 24 });
    // a forma fica no plano YZ: x da forma -> y, y da forma -> z, a espessura ao longo de x
    por(M.amarelo, placa, new THREE.Matrix4().makeBasis(V(0, 1, 0), V(0, 0, 1), V(1, 0, 0)).setPosition(xp - 15, CENTRO_Y, zc));
    por(M.ouro, new THREE.TorusGeometry(r, 26, 8, 32), new THREE.Matrix4().compose(V(xp, CENTRO_Y, zc), deitado, V(1, 1, 1)));
  }
}
// a passarela de rede em V: das barras azuis (3 m) até a faixa verde do meio, onde se anda
{
  const x0 = X.m4 + 20, x1 = X.vermelho0 - 20;
  const [frente, fundo] = E.barras_azuis.map((b) => [b[1], b[2]]).sort((a, b) => a[0] - b[0]);
  const meio0 = CENTRO_Y - 110, meio1 = CENTRO_Y + 110, zb = ANDAR + 30;
  quad(M.rede, V(x0, frente[0], frente[1]), V(x1, frente[0], frente[1]), V(x1, meio0, zb), V(x0, meio0, zb), 110);
  quad(M.rede, V(x0, meio1, zb), V(x1, meio1, zb), V(x1, fundo[0], fundo[1]), V(x0, fundo[0], fundo[1]), 110);
  caixa(M.verde, x0, x1, meio0, meio1, zb - 30, zb);
  // as travessas de baixo, que seguram a faixa do meio
  for (let x = x0 + 250; x < x1; x += 500) cilindro(M.barras, V(x, MEIO, ANDAR - 40), V(x, FUNDO, ANDAR - 40), 30, 8);
}
// o cilindro magenta pendurado no módulo vermelho (o círculo rosa da planta)
cilindro(M.cinza, V(8870, MEIO, TETO - 10), V(8870, FUNDO, TETO - 10), 16, 6);
cilindro(M.corda, V(8870, 3520, TETO - 10), V(8870, 3520, 3150), 10, 6);
cilindro(M.cilMagenta, V(8870, 3520, 3150), V(8870, 3520, 2440), 140, 20);
// o painel com o X na frente da metade esquerda do módulo vermelho
painelY(M.painelX, MEIO - 30, X.vermelho0 + 50, X.vermelho1 - 50, ANDAR + 40, TETO - 40);

/* ======================================================================
   4. EMBAIXO: a piscina de cubos, as cordas, a tirolesa, a estrela, a saída
   ====================================================================== */
{
  // as bordas acolchoadas da piscina (a barra laranja do .3ds corre por cima)
  const x0 = c0, x1 = X.pe;
  caixa(M.carmim, x0, x1, MEIO - 30, MEIO + 30, 0, BASE + 40);
  caixa(M.carmim, x0, x1, FUNDO - 30, FUNDO + 30, 0, BASE + 40);
  caixa(M.carmim, x0 - 30, x0 + 30, MEIO, FUNDO, 0, BASE + 40);
  // os cubos de espuma: uma camada e alguns soltos por cima (na imagem eles
  // mal passam da borda)
  const cores = ["#7f86ee", "#9b46b5", "#f2b81e", "#e03fa6", "#5d6fe8"];
  const cubos = [];
  for (let camada = 0; camada < 2; camada++) {
    for (let x = x0 + 130 + camada * 90; x < x1 - 90; x += 205) {
      for (let y = MEIO + 130 + camada * 80; y < FUNDO - 90; y += 205) {
        if (camada && sorte() < 0.7) continue;
        const q = new THREE.Quaternion().setFromEuler(new THREE.Euler((sorte() - 0.5) * 0.9, (sorte() - 0.5) * 0.9, sorte() * PI));
        // (a primeira camada assenta no chão: um cubo girado não pode furar o piso)
        const z = 170 + camada * 165 + sorte() * 45;
        cubos.push({ m: new THREE.Matrix4().compose(V(x + (sorte() - 0.5) * 60, y + (sorte() - 0.5) * 60, z), q, V(1, 1, 1)), cor: cores[Math.floor(sorte() * cores.length)] });
      }
    }
  }
  coloridos(M.cubos, cubos, new THREE.BoxGeometry(190, 190, 190));
}
// as cordas com nós penduradas do andar de cima até a espuma
for (const x of [1640, 2240, 2840]) {
  for (const dx of [-55, 55]) {
    cilindro(M.corda, V(x + dx, MEIO + 90, ANDAR - ESP), V(x + dx, MEIO + 90, 260), 13, 6);
    for (let z = 420; z < ANDAR - 200; z += 330) cilindro(z % 660 < 330 ? M.barras : M.ouro, V(x + dx, MEIO + 90, z), V(x + dx, MEIO + 90, z + 80), 30, 8);
  }
}
// a viga azul da tirolesa, por baixo do andar de cima (presa nele), com o
// poste rosa de apoio na ponta direita, o carrinho e o pegador
const TIROLESA = { x0: X.m1, x1: 6880, y: CENTRO_Y, z0: 1780, z1: 2040 };
{
  const { x0, x1, y, z0, z1 } = TIROLESA;
  caixa(M.viga, x0, x1, y - 85, y + 85, z0, z1);
  for (const x of [x0 + 600, (x0 + x1) / 2, x1 - 300]) cilindro(M.cinza, V(x, y, z1), V(x, y, ANDAR - ESP), 22, 8);
  cilindro(M.colunas, V(x1 + 60, y, 0), V(x1 + 60, y, z1), 44, 14);
  const xc = 6700; // o carrinho fica na ponta da direita, perto do bloco de onde se sai
  caixa(M.cinza, xc - 110, xc + 110, y - 95, y + 95, z0 - 70, z0);
  cilindro(M.corda, V(xc, y, z0 - 70), V(xc, y, 1480), 14, 6);
  cilindro(M.cinza, V(xc, y - 200, 1480), V(xc, y + 200, 1480), 22, 8); // o pegador
}
// a estrela amarela na coluna da frente, e os dois discos azuis do fundo
{
  const forma = new THREE.Shape();
  for (let i = 0; i < 10; i++) {
    const a = PI / 2 + (i * PI) / 5, r = i % 2 ? 150 : 340;
    if (i) forma.lineTo(r * Math.cos(a), r * Math.sin(a)); else forma.moveTo(r * Math.cos(a), r * Math.sin(a));
  }
  const g = new THREE.ExtrudeGeometry(forma, { depth: 70, bevelEnabled: true, bevelThickness: 25, bevelSize: 25, bevelSegments: 2 });
  por(M.amarelo, g, new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(TIROLESA.x1 + 60, TIROLESA.y - 60, 1350));
  const deFrente = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), V(0, -1, 0));
  for (const [x, z] of [[3350, 1000], [4550, 1250]]) {
    por(M.azulEscuro, new THREE.CylinderGeometry(290, 290, 30, 28), new THREE.Matrix4().compose(V(x, FUNDO - 40, z), deFrente, V(1, 1, 1)));
  }
}
// a saída da piscina de cubos: o bloco rosa no fim dela e os degraus verdes na frente
caixa(M.rosaBloco, X.pe + 40, X.vermelho0 - 40, MEIO + 40, FUNDO - 40, 0, 450);
function degraus(xa, xb, y, alturas) {
  // degraus verde-limão saindo para a frente, com a ponta arredondada (como na planta)
  const fundoDegrau = 165;
  alturas.forEach((h, i) => {
    const sai = fundoDegrau * (alturas.length - i);
    const forma = new THREE.Shape();
    forma.moveTo(xa, y); forma.lineTo(xb, y); forma.lineTo(xb, y - sai + 60);
    forma.quadraticCurveTo((xa + xb) / 2, y - sai - 60, xa, y - sai + 60);
    forma.lineTo(xa, y);
    por(M.verde, new THREE.ExtrudeGeometry(forma, { depth: h, bevelEnabled: false, curveSegments: 10 }));
  });
}
degraus(7440, 8280, MEIO - 20, [150, 300]);
// a placa "ninja" amarela, pendurada embaixo do andar de cima, na frente
painelY(M.placa, MEIO - 50, X.pe + 40, X.vermelho0 - 40, 1790, 2150);

/* ======================================================================
   5. O MÓDULO VERMELHO: a piscina de bolinhas e o tobogã em espiral
   ====================================================================== */
{
  const x0 = X.vermelho0, x1 = X.vermelho2;
  // as bordas da piscina (até o quadro do .3ds, a 0,3 m)
  caixa(M.vermelho, x0, x1, FRENTE - 25, FRENTE + 25, 0, CAMA + 40);
  caixa(M.vermelho, x0, x1, FUNDO - 25, FUNDO + 25, 0, CAMA + 40);
  caixa(M.vermelho, x0 - 25, x0 + 25, FRENTE, FUNDO, 0, CAMA + 40);
  caixa(M.vermelho, x1 - 25, x1 + 25, FRENTE, FUNDO, 0, CAMA + 40);
  // as bolinhas: a camada de cima (o resto é o fundo colorido)
  caixa(M.vermelho, x0, x1, FRENTE, FUNDO, 0, 150);
  const cores = ["#e8231e", "#f4f4f4", "#5fd13a", "#2fb5e8", "#f6c419"];
  const bolas = [];
  for (let x = x0 + 95; x < x1 - 60; x += 172) {
    for (let y = FRENTE + 95; y < FUNDO - 60; y += 172) {
      bolas.push({ m: new THREE.Matrix4().makeTranslation(x + (sorte() - 0.5) * 50, y + (sorte() - 0.5) * 50, 200 + sorte() * 70), cor: cores[Math.floor(sorte() * cores.length)] });
    }
  }
  coloridos(M.bolinhas, bolas, new THREE.IcosahedronGeometry(88, 1));
  // a saída da frente: os degraus verdes sob o corrimão rosa
  degraus(9930, 10420, FRENTE - 20, [150, 300]);
}
{
  const { r, zTopo } = TOBOGA;
  const curva = curvaDoTobogan();
  // rosa e verde-limão alternados, um quarto de volta cada (como na imagem).
  // Cada pedaço entra 0,4% no seguinte (sem fresta) com 8 mm a menos de
  // raio, um sim, um não: na emenda as duas paredes não brigam (antes, do
  // mesmo raio, piscavam -- uma faixa riscando o túnel no passeio)
  const partes = 7;
  for (let k = 0; k < partes; k++) {
    const t0 = k / partes, t1 = (k + 1) / partes + 0.004;
    const sub = new THREE.CatmullRomCurve3(Array.from({ length: 16 }, (_, j) => curva.getPoint(Math.min(1, t0 + (t1 - t0) * (j / 15)))));
    por(k % 2 ? M.tuboRosa : M.tuboVerde, new THREE.TubeGeometry(sub, 18, r - (k % 2) * 8, 18, false));
  }
  // a boca do tobogã: o aro verde-limão na beira do piso e o capuz verde-limão
  // por cima de quem senta para descer (o pedaço verde mais alto da imagem)
  const boca = curva.getPoint(0), dirBoca = curva.getTangent(0);
  por(M.tuboVerde, new THREE.TorusGeometry(r + 36, 34, 8, 24), new THREE.Matrix4().compose(boca, new THREE.Quaternion().setFromUnitVectors(V(0, 0, 1), dirBoca), V(1, 1, 1)));
  const eixo = V(dirBoca.x, dirBoca.y, 0).normalize(), cima = V(0, 0, 1);
  const lado = new THREE.Vector3().crossVectors(eixo, cima);
  const capuz = new THREE.CylinderGeometry(r + 60, r + 60, 520, 18, 1, true, -PI / 2, PI);
  const centroCapuz = boca.clone().addScaledVector(eixo, -200).setZ(zTopo + 30);
  por(M.tuboVerde, capuz, new THREE.Matrix4().makeBasis(lado, eixo, cima).setPosition(centroCapuz));
}
// a tela verde-limão acima da boca do tobogã (como na imagem)
painelY(M.telaVerde, MEIO - 20, X.vermelho1 + 50, X.vermelho2 - 50, ANDAR + 600, TETO - 40, 100);

/* ======================================================================
   6. AS DUAS CAMAS ELÁSTICAS (2 m x 2 m): a lona rosa com o círculo verde,
      a proteção das molas, a saia acolchoada, as telas e os degraus
   ====================================================================== */
for (const [x0, x1] of [[X.vermelho2, X.cama1], [X.cama1, X.cama2]]) {
  const y0 = FRENTE, y1 = FUNDO;
  // a saia acolchoada, do chão ao quadro
  caixa(M.carmim, x0, x1, y0 - 20, y0 + 20, 0, CAMA - 20);
  caixa(M.carmim, x0, x1, y1 - 20, y1 + 20, 0, CAMA - 20);
  caixa(M.carmim, x1 - 20, x1 + 20, y0, y1, 0, CAMA - 20);
  // a proteção das molas (a borda acolchoada) e a lona
  const borda = 150;
  caixa(M.rosaBloco, x0 + 40, x1 - 40, y0 + 40, y0 + 40 + borda, CAMA - 30, CAMA + 40);
  caixa(M.rosaBloco, x0 + 40, x1 - 40, y1 - 40 - borda, y1 - 40, CAMA - 30, CAMA + 40);
  caixa(M.rosaBloco, x0 + 40, x0 + 40 + borda, y0 + 40, y1 - 40, CAMA - 30, CAMA + 40);
  caixa(M.rosaBloco, x1 - 40 - borda, x1 - 40, y0 + 40, y1 - 40, CAMA - 30, CAMA + 40);
  const z = CAMA + 15;
  quad(M.lona, V(x0 + 40 + borda, y0 + 40 + borda, z), V(x1 - 40 - borda, y0 + 40 + borda, z), V(x1 - 40 - borda, y1 - 40 - borda, z), V(x0 + 40 + borda, y1 - 40 - borda, z), 150);
  // o círculo verde no meio da lona
  const disco = new THREE.CircleGeometry(310, 28);
  por(M.verde, disco, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, z + 4));
  // as telas: o fundo, o lado e a frente (com a entrada na direita, sob o corrimão)
  const zt = 2180;
  painelY(M.tela, y1, x0, x1, CAMA + 40, zt, 100);
  painelX(M.tela, x1, y0, y1, CAMA + 40, zt, 100);
  if (x0 === X.vermelho2) painelX(M.tela, x0, y0, y1, CAMA + 40, zt, 100); // o lado da piscina de bolinhas
  painelY(M.tela, y0, x0, x1 - 520, CAMA + 40, zt, 100);
  painelY(M.tela, y0, x1 - 520, x1, 900, zt, 100);
  degraus(x1 - 510, x1 - 50, y0 - 20, [150, 300]);
}

/* ======================================================================
   7. AS TELAS DE PROTEÇÃO (claras e translúcidas; o céu da imagem é só fundo)
   ====================================================================== */
{
  const z0 = BASE + 60, zt = TETO - 40, zc = ANDAR - 60;
  // o fundo inteiro, do canto ao módulo vermelho
  painelY(M.tela, FUNDO + 20, c0, X.vermelho2, z0, zt, 100);
  // a frente da faixa: embaixo (a piscina de cubos) e em cima (exceto a rede em V, que é a frente ali)
  painelY(M.tela, MEIO - 15, c1, X.pe, z0, zc, 100);
  painelY(M.tela, MEIO - 15, c1, X.m4, ANDAR + 40, zt, 100);
  // o canto em L: a frente e o lado esquerdo (a entrada é pelo lado direito, embaixo)
  painelY(M.tela, FRENTE - 15, c0, c1, z0, zt, 100);
  painelX(M.tela, c0 - 15, FRENTE, FUNDO, z0, zt, 100);
  // o lado do módulo vermelho em cima (para as camas) e o lado do bloco de saída
  painelX(M.tela, X.vermelho2, MEIO, FUNDO, ANDAR + 40, zt, 100);
}

/* ======================================================================
   MONTAGEM FINAL: metros, Y para cima, a frente em +Z; centraliza e assenta
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "brinquedao-ninja";
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
renderer.setSize(1600, 867);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.append(renderer.domElement);
cena.add(new THREE.HemisphereLight("#ffffff", "#556677", 1.9));
const sol = new THREE.DirectionalLight("#ffffff", 1.9);
sol.position.set(-6, 10, 9);
cena.add(sol);
const chao = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: "#3d5a9a" }));
chao.rotation.x = -PI / 2;
cena.add(chao);
const camera = new THREE.PerspectiveCamera(40, 1600 / 867, 0.1, 200);
window.ver = (x, y, z, alvo = [0, 1.5, 0], fov = 40, fundo = "#0b1a3a") => {
  cena.background = new THREE.Color(fundo);
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.88);
};
// de cima, sem perspectiva, como a planta (o fundo do brinquedo para cima)
window.verCima = (largura = 15.6, fundo = "#ffffff") => {
  cena.background = new THREE.Color(fundo);
  chao.visible = false;
  const alto = (largura * 867) / 1600;
  const orto = new THREE.OrthographicCamera(-largura / 2, largura / 2, alto / 2, -alto / 2, 0.1, 100);
  orto.position.set(0, 30, 0);
  orto.up.set(0, 0, -1);
  orto.lookAt(0, 0, 0);
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
