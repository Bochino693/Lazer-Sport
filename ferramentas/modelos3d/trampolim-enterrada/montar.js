// Monta o Trampolim de Enterrada em three.js e exporta um .glb.
//
// De onde vem cada coisa:
//  - do trampolim.3ds da fábrica (o estrutura.json, feito pelo extrair.py):
//    as quatro colunas, o quadro de tubos de cima (a 2,93 m), a base de aço
//    (1,0 m de altura e 2 m de fundo) com os três módulos das camas e a linha
//    da parede inclinada. O .3ds é só a estrutura de aço, em mm;
//  - das imagens do projeto (6 m x 2 m, altura de 3,25 m; "projeto meramente
//    ilustrativo"): as cores, o caixote escuro que cobre a base, a lona das
//    camas com a moldura e as divisórias amarelas, o estofado da parede com a
//    moldura amarela, a cesta (aro e rede) e a escada de espuma de três
//    degraus no canto da cabeceira oposta à cesta (no .3ds não há escada).
//
// Coordenadas de trabalho = as do .3ds: x ao longo (a parede da cesta em
// x = 0), y para o fundo (y = 0 é a frente), z para cima, milímetros. No fim
// tudo vira metros, Y para cima e a frente em +Z: de frente, a cesta fica à
// esquerda e a escada no canto da direita, na frente.
//
// index.html?variante=espuma: a cama do meio vira uma piscina de cubos de
// espuma (amarelos e cinza-escuros, alternados), como na variante do projeto.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const E = await (await fetch("estrutura.json")).json();
const ESPUMA = new URLSearchParams(location.search).get("variante") === "espuma";
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const PI = Math.PI;

// ---------- as medidas (mm) ----------
const Q = E.quadro; // o retângulo do quadro de cima (linha de centro dos tubos)
const BASE = E.base.z; // 1000: o alto da base de aço, onde ficam as camas
const Y0 = E.base.y0; // a plataforma vai de y0 a y1: os 2 m de fundo do projeto
const Y1 = E.base.y1;
const YC = (Y0 + Y1) / 2;
const P = E.parede;
const [M1, M2, M3] = E.modulos;
// as divisas das camas: o pé da parede, o meio da folga de ~4 cm entre um
// módulo e o outro (a divisória amarela cobre a folga) e o fim da base
const DIVISAS = [P.x_baixo, (M1[1] + M2[0]) / 2, (M2[1] + M3[0]) / 2, M3[1]];
const ESTOFADO = 110; // a espessura dos estofados amarelos, sobre a base
const BORDA = 200; // a largura da moldura amarela de cada cama
const LONA = BASE + 15; // a lona fica na altura do quadro de aço (as molas ficam sob os estofados)
const TOPO = BASE + ESTOFADO;
// a escada: 50 cm depois do fim da estrutura (as colunas), encostada no canto
// da frente; o degrau de cima encosta no caixote. Começa depois da coluna do canto.
const ESCADA = { x0: M3[1], x1: E.caixa[1] + 500, y0: Y0 + 31, y1: Y0 + 931 };

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

const COR = {
  amarelo: "#f6c419",
  caixote: "#232529", // "cinza-escuro, quase preto"
  friso: "#34373d",
  coluna: "#43464b",
  estofadoCinza: "#3b3e45",
  aro: "#ef4b1f",
};
// a lona: grafite, com a trama da fita de polipropileno (uma volta da textura = 25 cm)
const texLona = tela(128, 128, (g, w, h) => {
  g.fillStyle = "#33373e";
  g.fillRect(0, 0, w, h);
  for (let i = 0; i < w; i += 8) {
    g.fillStyle = (i / 8) % 2 ? "rgba(255,255,255,.035)" : "rgba(0,0,0,.12)";
    g.fillRect(i, 0, 4, h);
    g.fillRect(0, i, w, 4);
  }
});
// a rede da cesta: a malha branca em losangos (o resto é transparente)
const texRede = tela(128, 128, (g, w, h) => {
  g.clearRect(0, 0, w, h);
  g.strokeStyle = "#ffffff";
  g.lineWidth = 9;
  for (let k = -w; k <= 2 * w; k += w / 2) {
    g.beginPath(); g.moveTo(k, 0); g.lineTo(k + h, h); g.stroke();
    g.beginPath(); g.moveTo(k, h); g.lineTo(k + h, 0); g.stroke();
  }
});
const M = {
  colunas: material("colunas", { color: COR.coluna, roughness: 0.45, metalness: 0.35 }),
  quadro: material("quadro-amarelo", { color: COR.amarelo, roughness: 0.32, metalness: 0.2 }),
  caixote: material("caixote", { color: COR.caixote, roughness: 0.85 }),
  friso: material("frisos-do-caixote", { color: COR.friso, roughness: 0.7 }),
  amarelo: material("estofados-amarelos", { color: COR.amarelo, roughness: 0.7 }),
  cinza: material("estofado-cinza", { color: COR.estofadoCinza, roughness: 0.75 }),
  lona: material("camas", { map: texLona, roughness: 0.9 }, { lona: true }), // no passeio, quica
  aro: material("aro", { color: COR.aro, roughness: 0.4, metalness: 0.45 }),
  rede: material("rede", { color: "#ffffff", map: texRede, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.8 }),
  cubos: material("cubos-de-espuma", { vertexColors: true, roughness: 0.85 }),
};

// ---------- peças básicas (em mm) ----------
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  por(nome, new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0)),
    new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
// espuma: a caixa com as quinas arredondadas (estofados, degraus)
function almofada(nome, x0, x1, y0, y1, z0, z1, raio = 35) {
  const g = new RoundedBoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0), 2, raio);
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function cilindro(nome, a, b, r, lados = 16) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, false);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, V(1, 1, 1)));
}
function esfera(nome, c, r) {
  por(nome, new THREE.SphereGeometry(r, 16, 10), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
}

/* ======================================================================
   1. A ESTRUTURA DO .3DS: colunas e o quadro amarelo de cima
   ====================================================================== */
// O quadro faz a volta com cotovelos arredondados; cada coluna sobe até o
// meio do cotovelo do seu canto (no .3ds, o tubo de pé fica no canto e os de
// cima se cruzam por cima dele; aqui a junta fica limpa, 2,6 cm para dentro).
{
  const RC = 90; // o raio da curva do cotovelo
  const r = Q.raio;
  const z = Q.z;
  // os tubos retos, entre os cotovelos
  cilindro(M.quadro, V(Q.x0 + RC, Q.y0, z), V(Q.x1 - RC, Q.y0, z), r, 18);
  cilindro(M.quadro, V(Q.x0 + RC, Q.y1, z), V(Q.x1 - RC, Q.y1, z), r, 18);
  cilindro(M.quadro, V(Q.x0, Q.y0 + RC, z), V(Q.x0, Q.y1 - RC, z), r, 18);
  cilindro(M.quadro, V(Q.x1, Q.y0 + RC, z), V(Q.x1, Q.y1 - RC, z), r, 18);
  // os cotovelos: um quarto de toro em cada canto (o toro do three fica no
  // plano XY, que aqui é o plano deitado)
  const cantos = [
    [Q.x0, Q.y0, 1, 1, PI], [Q.x1, Q.y0, -1, 1, 1.5 * PI],
    [Q.x1, Q.y1, -1, -1, 0], [Q.x0, Q.y1, 1, -1, 0.5 * PI],
  ];
  const meio = RC * (1 - Math.SQRT1_2); // do canto ao meio do cotovelo, em x e em y
  for (const [x, y, sx, sy, giro] of cantos) {
    const g = new THREE.TorusGeometry(RC, r, 12, 10, PI / 2);
    g.rotateZ(giro);
    por(M.quadro, g, new THREE.Matrix4().makeTranslation(x + sx * RC, y + sy * RC, z));
    const cx = x + sx * meio;
    const cy = y + sy * meio;
    const coluna = E.colunas.reduce((a, c) => (Math.hypot(c[0] - x, c[1] - y) < Math.hypot(a[0] - x, a[1] - y) ? c : a));
    cilindro(M.colunas, V(cx, cy, 0), V(cx, cy, z), coluna[4], 16);
    esfera(M.quadro, V(cx, cy, z), r + 4); // a junta da coluna com o cotovelo
    caixa(M.colunas, cx - 85, cx + 85, cy - 85, cy + 85, 0, 10); // a sapata no chão
  }
}

/* ======================================================================
   2. A BASE: o caixote escuro sobre a armação de aço (1,0 m)
   ====================================================================== */
caixa(M.caixote, P.x_atras, M3[1], Y0, Y1, 0, BASE);
// os frisos das juntas dos painéis, na frente e atrás: nas divisas das camas e nas pontas
for (const x of [P.x_atras + 30, ...DIVISAS.slice(0, 3), M3[1] - 30]) {
  caixa(M.friso, x - 30, x + 30, Y0 - 12, Y0, 0, BASE);
  caixa(M.friso, x - 30, x + 30, Y1, Y1 + 12, 0, BASE);
}
// o rodapé, rente ao chão
caixa(M.friso, P.x_atras, M3[1], Y0 - 12, Y0, 0, 70);
caixa(M.friso, P.x_atras, M3[1], Y1, Y1 + 12, 0, 70);
// nas duas cabeceiras: as juntas de pé (nas costas da parede, até o alto dela)
// e, atrás da parede, a junta da base com o painel de cima
for (const y of [Y0 + 30, YC, Y1 - 30]) {
  caixa(M.friso, P.x_atras - 12, P.x_atras, y - 30, y + 30, 0, P.z_alto);
  caixa(M.friso, M3[1], M3[1] + 12, y - 30, y + 30, 0, BASE);
}
caixa(M.friso, P.x_atras - 12, P.x_atras, Y0, Y1, BASE - 30, BASE + 30);

/* ======================================================================
   3. AS CAMAS: lona grafite, moldura amarela larga e as divisórias
   ====================================================================== */
for (let i = 0; i < 3; i++) {
  const a = DIVISAS[i];
  const b = DIVISAS[i + 1];
  // as laterais compridas (frente e fundo) de cada cama
  almofada(M.amarelo, a, b, Y0, Y0 + BORDA, BASE, TOPO);
  almofada(M.amarelo, a, b, Y1 - BORDA, Y1, BASE, TOPO);
  // a cabeceira de cada lado: no pé da parede e no fim, uma; entre duas
  // camas, a divisória (uma almofada só, por cima da folga dos módulos)
  const ini = i === 0 ? [a, a + BORDA] : [a - BORDA, a + BORDA];
  almofada(M.amarelo, ini[0], ini[1], Y0 + BORDA, Y1 - BORDA, BASE, TOPO);
  if (i === 2) almofada(M.amarelo, b - BORDA, b, Y0 + BORDA, Y1 - BORDA, BASE, TOPO);
  const x0 = a + BORDA;
  const x1 = b - BORDA;
  if (ESPUMA && i === 1) continue; // a piscina de espuma (abaixo)
  // a lona: a textura repete a cada 25 cm
  const g = new THREE.PlaneGeometry(x1 - x0, Y1 - Y0 - 2 * BORDA);
  const uv = g.attributes.uv;
  for (let k = 0; k < uv.count; k++) uv.setXY(k, (uv.getX(k) * (x1 - x0)) / 250, (uv.getY(k) * (Y1 - Y0 - 2 * BORDA)) / 250);
  por(M.lona, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, YC, LONA));
}

// a variante: a cama do meio é uma piscina de cubos de espuma, amarelos e
// cinza-escuros alternados, com a superfície um pouco abaixo dos estofados
if (ESPUMA) {
  const x0 = DIVISAS[1] + BORDA;
  const x1 = DIVISAS[2] - BORDA;
  const lado = 175;
  const nx = Math.round((x1 - x0) / lado);
  const ny = Math.round((Y1 - Y0 - 2 * BORDA) / lado);
  const px = (x1 - x0) / nx;
  const py = (Y1 - Y0 - 2 * BORDA) / ny;
  let semente = 11;
  const sorte = () => ((semente = (semente * 16807) % 2147483647) / 2147483647);
  // o amarelo da espuma é mais claro que o dos estofados: de longe, os cubos
  // não se confundem com a moldura
  const amarelo = new THREE.Color("#fbd94e");
  const cinza = new THREE.Color("#3a3d44");
  const partes = [];
  // uma camada cheia, rente aos estofados, e alguns cubos soltos por cima (o
  // monte da piscina); a de baixo ficaria dentro do caixote, sem aparecer
  for (let camada = 0; camada < 2; camada++) {
    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        if (camada && sorte() > 0.3) continue;
        const g = new THREE.BoxGeometry(lado - 8, lado - 8, lado - 8);
        const q = new THREE.Quaternion().setFromEuler(new THREE.Euler((sorte() - 0.5) * 0.35, (sorte() - 0.5) * 0.35, (sorte() - 0.5) * 0.6));
        const z = TOPO - 95 - lado / 2 + camada * (lado - 50) + (sorte() - 0.5) * 40;
        g.applyMatrix4(new THREE.Matrix4().compose(V(x0 + (i + 0.5 + camada * (sorte() - 0.5) * 0.5) * px, Y0 + BORDA + (j + 0.5) * py, z), q, V(1, 1, 1)));
        const c = (i + j + camada) % 2 ? cinza : amarelo;
        const cores = new Float32Array(g.attributes.position.count * 3);
        for (let k = 0; k < cores.length; k += 3) { cores[k] = c.r; cores[k + 1] = c.g; cores[k + 2] = c.b; }
        g.setAttribute("color", new THREE.Float32BufferAttribute(cores, 3));
        partes.push(g);
      }
    }
  }
  por(M.cubos, mergeGeometries(partes, false));
}

/* ======================================================================
   4. A PAREDE INCLINADA: a armação (a linha do .3ds), o estofado cinza
   com a moldura amarela e a cesta
   ====================================================================== */
// a linha da parede: do pé (na beira da cama, na altura da base) até o alto,
// junto da cabeceira; o estofado vai por cima dela, virado para as camas
const PE = V(P.x_baixo, YC, BASE);
const ALTO = V(P.x_alto, YC, P.z_alto);
const SUBIDA = new THREE.Vector3().subVectors(ALTO, PE);
const COMPRIMENTO = SUBIDA.length();
const U = SUBIDA.clone().normalize(); // para cima, ao longo da parede
const N = V(U.z, 0, -U.x); // a normal do estofado: para as camas e um pouco para cima
const LARGURA = Y1 - Y0;
const ESP_PAREDE = 120; // a espessura do estofado da parede
const MOLDURA = 150;
// uma placa na base da parede: centro em s (ao longo), t (para fora), tamanho (espessura, largura, comprimento)
function placaNaParede(nome, s, t, espessura, largura, comprimento, arredondada = true) {
  const g = arredondada
    ? new RoundedBoxGeometry(espessura, largura, comprimento, 2, 30)
    : new THREE.BoxGeometry(espessura, largura, comprimento);
  const m = new THREE.Matrix4().makeBasis(N, V(0, 1, 0), U);
  m.setPosition(PE.clone().addScaledVector(U, s).addScaledVector(N, t));
  por(nome, g, m);
}
// a armação por baixo, fechada com painéis escuros: o perfil da parede (as
// costas de pé, no x dos montantes do .3ds, e a frente inclinada) extrudado de
// um lado ao outro
{
  const perfil = new THREE.Shape();
  perfil.moveTo(P.x_atras, BASE);
  perfil.lineTo(P.x_baixo, BASE);
  perfil.lineTo(P.x_alto, P.z_alto);
  perfil.lineTo(P.x_atras, P.z_alto);
  perfil.lineTo(P.x_atras, BASE);
  const g = new THREE.ExtrudeGeometry(perfil, { depth: LARGURA, bevelEnabled: false });
  // a forma fica no plano XY; vira o plano XZ (x -> x, y -> z), extrudada para -y
  por(M.caixote, g, new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(0, Y1, 0));
}
// o estofado: a moldura amarela (a placa inteira) e o campo cinza, um pouco
// mais alto, por dentro dela; nos lados a moldura desce do alto até o piso das camas
placaNaParede(M.amarelo, COMPRIMENTO / 2, ESP_PAREDE / 2, ESP_PAREDE, LARGURA, COMPRIMENTO);
{
  const baixo = 230; // o pé do campo cinza (a almofada do pé da parede cobre o começo)
  const comprimento = COMPRIMENTO - baixo - MOLDURA;
  placaNaParede(M.cinza, baixo + comprimento / 2, (ESP_PAREDE + 18) / 2, ESP_PAREDE + 18, LARGURA - 2 * MOLDURA, comprimento);
}

// a cesta: perto do alto da parede, no meio; aro laranja com a rede branca
const CESTA = (() => {
  const altura = 2450; // o aro, do chão
  const raio = 225; // o aro oficial (45 cm por dentro)
  // onde a frente do campo cinza passa nessa altura
  const t = ESP_PAREDE + 18;
  const s = (altura - PE.z - N.z * t) / U.z;
  const frente = PE.clone().addScaledVector(U, s).addScaledVector(N, t);
  const centro = V(frente.x + 70 + raio, YC, altura);
  return { altura, raio, s, t, frente, centro };
})();
{
  const { altura, raio, s, t, frente, centro } = CESTA;
  // a chapa de fixação na parede e os braços até o aro
  placaNaParede(M.aro, s - 50, t + 12, 24, 300, 230, false);
  for (const lado of [-1, 1]) {
    const a = 0.75; // os braços pegam o aro a ±43° da parte de trás
    cilindro(M.aro, V(frente.x + 8, YC + lado * 120, altura), V(centro.x - raio * Math.cos(a), YC + lado * raio * Math.sin(a), altura), 13, 8);
  }
  cilindro(M.aro, V(frente.x + 8 - (150 * U.x) / U.z, YC, altura - 150), V(centro.x - raio, YC, altura), 13, 8);
  // o aro (o toro já fica deitado: plano XY)
  por(M.aro, new THREE.TorusGeometry(raio, 16, 10, 48), new THREE.Matrix4().makeTranslation(centro.x, centro.y, altura));
  // a rede: um tronco de cone aberto, mais estreito embaixo (a malha repete 8 vezes na volta)
  const rede = new THREE.CylinderGeometry(raio - 6, raio * 0.62, 420, 32, 1, true);
  rede.rotateX(PI / 2); // o eixo do cilindro (y) vira o z, de pé
  const uv = rede.attributes.uv;
  for (let k = 0; k < uv.count; k++) uv.setXY(k, uv.getX(k) * 8, uv.getY(k) * 2);
  por(M.rede, rede, new THREE.Matrix4().makeTranslation(centro.x, centro.y, altura - 210));
}

/* ======================================================================
   5. A ESCADA: bloco cinza-escuro de espuma com três degraus, cada um com
   o tampo amarelo; o de cima encosta no caixote
   ====================================================================== */
{
  const { x0, x1, y0, y1 } = ESCADA;
  const passo = (x1 - x0) / 3;
  for (let d = 1; d <= 3; d++) {
    const alto = (d * TOPO) / 4; // degraus iguais, até o alto dos estofados
    const a = x1 - d * passo;
    const b = x1 - (d - 1) * passo;
    almofada(M.cinza, d === 3 ? x0 : a, b, y0, y1, 0, alto - 55, 30);
    almofada(M.amarelo, d === 3 ? x0 : a, b, y0, y1, alto - 60, alto, 25);
  }
}

/* ======================================================================
   MONTAGEM FINAL: metros, Y para cima, frente em +Z; junta por material,
   centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = ESPUMA ? "trampolim-enterrada-espuma" : "trampolim-enterrada";
cena.add(raiz);
// (x, y, z) do .3ds -> (x, z, -y) em metros: rotação própria (sem espelhar)
const virar = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1).premultiply(new THREE.Matrix4().makeScale(0.001, 0.001, 0.001));
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
// assenta no chão e centraliza; o deslocamento vai para o passeio da Arena
// (TE, em arena3d.js: lá os pontos do caminho são escritos em mm do .3ds)
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.centro = [centro.x, caixaTotal.min.y, centro.z].map((v) => Math.round(v * 10000) / 10000);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 100) / 100);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
// o aro, no objeto final (para a câmera "dentro" e para conferir o passeio)
window.aro = [CESTA.centro.x / 1000 - centro.x, CESTA.altura / 1000 - caixaTotal.min.y, -CESTA.centro.y / 1000 - centro.z].map((v) => Math.round(v * 1000) / 1000);

// ---------- vistas para conferir e as fotos do cadastro ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1600, 1000);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.append(renderer.domElement);
cena.add(new THREE.HemisphereLight("#ffffff", "#8b95a5", 1.6));
const sol = new THREE.DirectionalLight("#ffffff", 2.1);
sol.position.set(5, 12, 7);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 1, far: 40 });
sol.shadow.bias = -0.0004;
cena.add(sol);
raiz.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
// o chão só das vistas (não vai para o .glb): recebe a sombra
const chao = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: 0.22 }));
chao.rotation.x = -PI / 2;
chao.receiveShadow = true;
cena.add(chao);
const piso = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshStandardMaterial({ color: "#3d4a5c", roughness: 1 }));
piso.rotation.x = -PI / 2;
piso.position.y = -0.002;
cena.add(piso);
const camera = new THREE.PerspectiveCamera(34, 1600 / 1000, 0.05, 200);
window.ver = (x, y, z, alvo = [0, 1.3, 0], fundo = "#0b1a3a", fov = 34, sombra = true) => {
  cena.background = new THREE.Color(fundo);
  piso.visible = fundo === "#0b1a3a"; // no fundo claro das fotos, só a sombra
  chao.visible = sombra; // vista de cima: sem a sombra inclinada do sol
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
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
