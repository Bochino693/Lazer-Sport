// Monta o Brinquedão Selva 11 m em three.js e exporta um .glb.
// Estrutura (colunas, barras, rede) = a do .3ds do cliente, em mm.
// Peças que o .3ds não tem (caixas, escorregadores, bolas, painéis, pisos)
// = modeladas a partir das imagens e da planta (11 m x 2 m x 3,5 m).
//
// Coordenadas de trabalho = as do .3ds: x ao longo do brinquedo, y para a
// FRENTE (+), z para cima, milímetros. No fim tudo vira metros, Y para cima
// e frente em +Z (a torre das bolas à esquerda de quem olha de frente).
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const E = await (await fetch("estrutura.json")).json();

// ---------- a grade ----------
const XS = [-10575, -9540, -8507, -7474, -6441, -5410, -3840, -2807, -237];
const FUNDO = -3690, FRENTE = -2620, FRENTE2 = -1566;
const Z1 = 1104, Z2 = 2074, ZTETO = 3044, TORRE = 3560, REDE = 1833;
const perto = (lista, v) => lista.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));

// ---------- materiais ----------
const pecas = new Map(); // nome -> { material, geometrias: [] }
function material(nome, opcoes) {
  if (!pecas.has(nome)) {
    pecas.set(nome, { material: new THREE.MeshStandardMaterial({ name: nome, roughness: 0.55, metalness: 0, ...opcoes }), geometrias: [] });
  }
  return nome;
}
const BEGE = material("colunas", { color: "#e8cdb0", roughness: 0.45 });
const VERDE = material("tubos-verdes", { color: "#1f9a3c", roughness: 0.4 });
const PISO = material("pisos", { color: "#27a844", roughness: 0.7 });
const AMARELO = material("amarelo", { color: "#f6c21c" });
const LARANJA = material("laranja", { color: "#f07f1c" });
const AZUL = material("azul", { color: "#1f55cf" });
const VERDE_ESC = material("contorno", { color: "#1d6b30" });
const AMARELO_ESC = material("tubo-amarelo", { color: "#f8c623", roughness: 0.35, side: THREE.DoubleSide });
const LARANJA_ESC = material("tubo-laranja", { color: "#ef7417", roughness: 0.35, side: THREE.DoubleSide });
const AZUL_ESC = material("escorregador-azul", { color: "#1d4bd0", roughness: 0.3, side: THREE.DoubleSide });
const CORDA = material("cordas", { color: "#d9b84a", roughness: 0.8 });

// texturas desenhadas (vão dentro do .glb, em PNG)
function tela(w, h, pintar) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  pintar(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const texPainel = tela(512, 512, (g, w, h) => {
  // painel temático: selva ao fundo, o círculo amarelo com o X verde
  const fundo = g.createLinearGradient(0, 0, 0, h);
  fundo.addColorStop(0, "#cfe8b5");
  fundo.addColorStop(1, "#9fcf7a");
  g.fillStyle = fundo;
  g.fillRect(0, 0, w, h);
  const folha = (x, y, s, a, cor) => {
    g.save(); g.translate(x, y); g.rotate(a); g.fillStyle = cor;
    g.beginPath(); g.ellipse(0, 0, s, s * 0.38, 0, 0, Math.PI * 2); g.fill();
    g.strokeStyle = "rgba(0,0,0,.18)"; g.lineWidth = 3; g.beginPath(); g.moveTo(-s, 0); g.lineTo(s, 0); g.stroke();
    g.restore();
  };
  const cores = ["#3e8e2f", "#58a83a", "#2f7a2a", "#6cbf45"];
  for (let i = 0; i < 26; i++) folha((i * 97) % w, ((i * 151) % h), 50 + (i % 4) * 14, (i * 0.7) % 3.1, cores[i % 4]);
  g.fillStyle = "#1d6b30"; g.beginPath(); g.arc(w / 2, h / 2, 190, 0, Math.PI * 2); g.fill();
  g.fillStyle = "#f6c21c"; g.beginPath(); g.arc(w / 2, h / 2, 165, 0, Math.PI * 2); g.fill();
  g.strokeStyle = "#1f9a3c"; g.lineWidth = 46; g.lineCap = "round";
  g.beginPath(); g.moveTo(w / 2 - 95, h / 2 - 95); g.lineTo(w / 2 + 95, h / 2 + 95);
  g.moveTo(w / 2 + 95, h / 2 - 95); g.lineTo(w / 2 - 95, h / 2 + 95); g.stroke();
});
const PAINEL = material("painel-x", { map: texPainel, roughness: 0.6 });
const texVidro = tela(256, 512, (g, w, h) => {
  // a tela de proteção (azul claro, translúcida), com a selva desenhada embaixo
  const fundo = g.createLinearGradient(0, 0, 0, h);
  fundo.addColorStop(0, "rgba(150, 215, 240, .55)");
  fundo.addColorStop(1, "rgba(210, 240, 250, .5)");
  g.fillStyle = fundo;
  g.fillRect(0, 0, w, h);
  g.fillStyle = "rgba(90, 160, 80, .45)";
  for (let i = 0; i < 9; i++) { g.beginPath(); g.ellipse((i * 61) % w, h - 30 - (i % 3) * 25, 55, 22, (i % 5) * 0.6, 0, Math.PI * 2); g.fill(); }
});
const VIDRO = material("tela-protecao", { map: texVidro, transparent: true, depthWrite: false, side: THREE.DoubleSide, roughness: 0.2 });
const texFuros = tela(256, 128, (g, w, h) => {
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, w, h);
  g.clearRect(0, 0, 0, 0);
  for (let x = 10; x < w; x += 32) for (let y = 10; y < h; y += 32) g.clearRect(x, y, 18, 18);
});
const FUROS = material("tubo-furado", { color: "#f07f1c", map: texFuros, alphaTest: 0.5, side: THREE.DoubleSide });

function por(nome, geometria, matriz) {
  if (matriz) geometria.applyMatrix4(matriz);
  pecas.get(nome).geometrias.push(geometria);
}

// ---------- peças básicas (em mm) ----------
const V = (x, y, z) => new THREE.Vector3(x, y, z);
function cilindro(nome, a, b, r, lados = 12) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, false);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, new THREE.Vector3(1, 1, 1)));
}
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  const g = new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0));
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function esfera(nome, c, r) {
  por(nome, new THREE.SphereGeometry(r, 24, 16), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
}
// um painel plano: retângulo no plano que passa por `centro`, com normal `n`
function painel(nome, centro, largura, altura, n, ladoU = V(1, 0, 0)) {
  const g = new THREE.PlaneGeometry(largura, altura);
  const nn = n.clone().normalize();
  const u = ladoU.clone().normalize();
  const v = new THREE.Vector3().crossVectors(nn, u);
  // a placa do three tem o lado U em +x, o V em +y e a normal em +z
  const m = new THREE.Matrix4().makeBasis(u, v, nn);
  m.setPosition(centro);
  por(nome, g, m);
}

// ---------- 1. ESTRUTURA DO .3DS ----------
const colunas = new Map();
for (const [x, y, z0, z1] of E.colunas) {
  const cx = perto(XS, x);
  const cy = perto([FUNDO, FRENTE, FRENTE2], y);
  const k = cx + ":" + cy;
  const atual = colunas.get(k) || [Infinity, -Infinity];
  colunas.set(k, [Math.min(atual[0], z0), Math.max(atual[1], z1)]);
}
for (const [k, [z0, z1]] of colunas) {
  const [x, y] = k.split(":").map(Number);
  cilindro(BEGE, V(x, y, z0), V(x, y, z1), 55, 14);
  esfera(VERDE, V(x, y, z1 + 10), 66); // a tampa verde de cada coluna
}
for (const [xa, ya, za, xb, yb, zb] of E.barras) {
  cilindro(VERDE, V(xa, ya, za), V(xb, yb, zb), 46, 10);
}
// a rede do andar das bolas (a grade verde do .3ds)
{
  const x0 = -2814, x1 = -297, y0 = -3697, y1 = -1539;
  for (let x = x0; x <= x1 + 1; x += (x1 - x0) / 14) cilindro(VERDE, V(x, y0, REDE), V(x, y1, REDE), 14, 6);
  for (let y = y0; y <= y1 + 1; y += (y1 - y0) / 12) cilindro(VERDE, V(x0, y, REDE), V(x1, y, REDE), 14, 6);
}

// ---------- 2. PISOS ----------
const ESP = 45;
caixa(PISO, XS[0], XS[7], FUNDO, FRENTE, Z2 - ESP, Z2); // andar de cima, de ponta a ponta
caixa(PISO, XS[0], XS[1], FRENTE, FRENTE2, Z2 - ESP, Z2); // a saída do tobogã
caixa(PISO, XS[0], XS[2], FUNDO, FRENTE, Z1 - ESP, Z1); // o andar do meio dos escorregadores
caixa(AMARELO, XS[6], XS[7], FUNDO, -3150, 1109 - ESP, 1109); // degraus de subida
caixa(AMARELO, XS[6], XS[7], -3150, FRENTE, 643 - ESP, 643);
caixa(AMARELO, XS[6], XS[7], FUNDO, FRENTE, 0, 135);

// ---------- 3. AS TRÊS CAIXAS COLORIDAS COM ARCO ----------
function caixaComArco(x0, x1, cor) {
  const y0 = FUNDO, y1 = -2120, alto = 1950, parede = 40;
  const w = x1 - x0;
  // frente com o arco vazado (porta)
  const forma = new THREE.Shape();
  forma.moveTo(0, 0); forma.lineTo(w, 0); forma.lineTo(w, alto); forma.lineTo(0, alto); forma.lineTo(0, 0);
  const larg = 820, altPorta = 1250, raio = larg / 2;
  const furo = new THREE.Path();
  furo.moveTo(w / 2 - raio, 0);
  furo.lineTo(w / 2 + raio, 0);
  furo.lineTo(w / 2 + raio, altPorta - raio);
  furo.absarc(w / 2, altPorta - raio, raio, 0, Math.PI, false);
  furo.lineTo(w / 2 - raio, 0);
  forma.holes.push(furo);
  const frente = new THREE.ExtrudeGeometry(forma, { depth: parede, bevelEnabled: false, curveSegments: 20 });
  // a forma fica em XY; vira o plano XZ da frente (y = y1)
  const m = new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(x0, y1, 0);
  por(cor, frente, m);
  // o contorno verde do arco
  const anel = new THREE.Shape();
  anel.moveTo(w / 2 - raio - 70, 0);
  anel.lineTo(w / 2 + raio + 70, 0);
  anel.lineTo(w / 2 + raio + 70, altPorta - raio);
  anel.absarc(w / 2, altPorta - raio, raio + 70, 0, Math.PI, false);
  anel.lineTo(w / 2 - raio - 70, 0);
  anel.holes.push(furo);
  const contorno = new THREE.ExtrudeGeometry(anel, { depth: 12, bevelEnabled: false, curveSegments: 20 });
  por(VERDE_ESC, contorno, new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0)).setPosition(x0, y1 + 12, 0));
  // laterais, fundo e tampo
  caixa(cor, x0, x0 + parede, y0, y1, 0, alto);
  caixa(cor, x1 - parede, x1, y0, y1, 0, alto);
  caixa(cor, x0, x1, y0, y0 + parede, 0, alto);
  caixa(cor, x0, x1, y0, y1, alto - parede, alto);
  // o chão laranja de dentro
  caixa(LARANJA, x0 + parede, x1 - parede, y0 + parede, y1, 0, 60);
}
const terco = (XS[6] - XS[2]) / 3;
caixaComArco(XS[2], XS[2] + terco, AMARELO);
caixaComArco(XS[2] + terco, XS[2] + 2 * terco, LARANJA);
caixaComArco(XS[2] + 2 * terco, XS[6], AZUL);

// ---------- 4. ESCORREGADOR DUPLO ONDULADO (azul) ----------
function faixa(nome, caminho, perfil, passos = 48) {
  // superfície varrida: em cada t, o perfil (pares [deslocamento lateral, altura]) no ponto do caminho
  const pos = [], uv = [], idx = [];
  for (let i = 0; i <= passos; i++) {
    const t = i / passos;
    const { p, lado } = caminho(t);
    perfil.forEach(([d, h], j) => {
      pos.push(p.x + lado.x * d, p.y + lado.y * d, p.z + h);
      uv.push(j / (perfil.length - 1), t);
    });
  }
  const n = perfil.length;
  for (let i = 0; i < passos; i++) {
    for (let j = 0; j < n - 1; j++) {
      const a = i * n + j, b = a + 1, c = a + n, d = c + 1;
      idx.push(a, c, b, b, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  por(nome, g);
}
{
  const xc = (XS[1] + XS[2]) / 2, ya = FRENTE, yb = FRENTE + 1750, za = Z1, zb = 260;
  faixa(AZUL_ESC, (t) => ({
    p: V(xc, ya + (yb - ya) * t, za + (zb - za) * t + 110 * Math.sin(t * Math.PI * 3) * (1 - t) - (t > 0.85 ? (t - 0.85) * 600 : 0)),
    lado: V(1, 0, 0),
  }), [[-470, 260], [-460, 0], [-260, -40], [-30, 0], [0, 90], [30, 0], [260, -40], [460, 0], [470, 260]], 60);
  caixa(AMARELO, xc - 480, xc + 480, yb - 150, yb + 380, 0, 120); // o colchão amarelo da chegada
}

// ---------- 5. TOBOGÃ EM ESPIRAL (laranja e amarelo) ----------
// Como na planta: o círculo do tobogã fica em volta da coluna da frente da
// ponta; ele sai da cabine laranja do andar de cima, dá a volta na coluna
// descendo e chega no colchão laranja, na frente.
{
  const cx = -10590, cy = -1500, raio = 650, r = 330;
  const grau = Math.PI / 180;
  const a0 = -50 * grau, a1 = 360 * grau, passos = 48;
  const p0 = V(cx + raio * Math.cos(a0), cy + raio * Math.sin(a0), Z2 + 330);
  const tangente = V(-Math.sin(a0), Math.cos(a0), 0);
  const pontos = [p0.clone().addScaledVector(tangente, -420)];
  for (let i = 0; i <= passos; i++) {
    const t = i / passos;
    const a = a0 + (a1 - a0) * t;
    pontos.push(V(cx + raio * Math.cos(a), cy + raio * Math.sin(a), Z2 + 330 - t * (Z2 + 330 - 430)));
  }
  const fim = pontos[pontos.length - 1];
  pontos.push(V(fim.x, fim.y + 380, 395), V(fim.x, fim.y + 700, 385));
  const curva = new THREE.CatmullRomCurve3(pontos);
  const parte = (t0, t1, nome) => {
    const sub = new THREE.CatmullRomCurve3(Array.from({ length: 40 }, (_, k) => curva.getPoint(t0 + (t1 - t0) * (k / 39))));
    por(nome, new THREE.TubeGeometry(sub, 90, r, 20, false));
  };
  parte(0, 0.52, LARANJA_ESC);
  parte(0.5, 1, AMARELO_ESC);
  const saida = curva.getPoint(1);
  caixa(LARANJA, saida.x - 430, saida.x + 430, saida.y + 60, saida.y + 660, 0, 120); // colchão da chegada
  // a cabine laranja de onde sai o tobogã
  painel(LARANJA, V(XS[0] - 25, (FRENTE + FRENTE2) / 2, (Z2 + ZTETO) / 2), FRENTE2 - FRENTE - 60, ZTETO - Z2 - 60, V(-1, 0, 0), V(0, -1, 0));
  painel(LARANJA, V((XS[0] + XS[1]) / 2, FRENTE2 + 25, (Z2 + ZTETO) / 2 + 150), XS[1] - XS[0] - 60, ZTETO - Z2 - 360, V(0, 1, 0), V(-1, 0, 0));
}

// ---------- 6. O ANDAR DE CIMA: rede de escalada, rolos, saco e painéis ----------
{
  // rede laranja inclinada (módulo sobre a caixa azul)
  const x0 = XS[5] + 80, x1 = XS[6] - 80;
  const a = V(0, FRENTE - 60, Z2 + 60), b = V(0, FUNDO + 250, Z2 + 620);
  for (let i = 0; i <= 10; i++) {
    const x = x0 + ((x1 - x0) * i) / 10;
    cilindro(LARANJA, V(x, a.y, a.z), V(x, b.y, b.z), 14, 6);
  }
  for (let i = 0; i <= 8; i++) {
    const t = i / 8;
    const p = a.clone().lerp(b, t);
    cilindro(LARANJA, V(x0, p.y, p.z), V(x1, p.y, p.z), 14, 6);
  }
}
// rolo amarelo pequeno (deitado) e o tubo laranja furado (para atravessar)
cilindro(AMARELO, V((XS[4] + XS[5]) / 2 - 300, -3000, Z2 + 140), V((XS[4] + XS[5]) / 2 + 300, -3000, Z2 + 140), 130, 20);
{
  const xc = (XS[3] + XS[4]) / 2;
  const g = new THREE.CylinderGeometry(430, 430, 900, 28, 1, true);
  por(FUROS, g, new THREE.Matrix4().compose(V(xc, -3150, Z2 + 440), new THREE.Quaternion().setFromAxisAngle(V(0, 1, 0), Math.PI / 2).multiply(new THREE.Quaternion().setFromAxisAngle(V(1, 0, 0), Math.PI / 2)), V(1, 1, 1)));
  const deitado = new THREE.Quaternion().setFromUnitVectors(V(0, 0, 1), V(1, 0, 0));
  for (const dx of [-450, 450]) {
    por(VERDE_ESC, new THREE.TorusGeometry(440, 30, 10, 36), new THREE.Matrix4().compose(V(xc + dx, -3150, Z2 + 440), deitado, V(1, 1, 1)));
  }
}
// saco amarelo pendurado
{
  const xc = (XS[2] + XS[3]) / 2;
  cilindro(CORDA, V(xc, -3150, ZTETO), V(xc, -3150, Z2 + 820), 10, 6);
  cilindro(AMARELO, V(xc, -3150, Z2 + 820), V(xc, -3150, Z2 + 220), 140, 20);
}
// painéis temáticos com o X
const X_FRENTE = V(0, 1, 0);
const DIREITA = V(-1, 0, 0); // a direita de quem olha de frente
painel(PAINEL, V((XS[6] + XS[7]) / 2, FRENTE + 30, (Z2 + ZTETO) / 2), XS[7] - XS[6] - 90, ZTETO - Z2 - 90, X_FRENTE, DIREITA);
painel(PAINEL, V((XS[6] + XS[7]) / 2, FRENTE + 30, (1109 + Z2) / 2), XS[7] - XS[6] - 90, Z2 - 1109 - 90, X_FRENTE, DIREITA);
painel(PAINEL, V((XS[1] + XS[2]) / 2, FRENTE + 30, (Z2 + ZTETO) / 2), XS[2] - XS[1] - 90, ZTETO - Z2 - 90, X_FRENTE, DIREITA);
painel(PAINEL, V(XS[1], (FRENTE + FRENTE2) / 2, (Z2 + ZTETO) / 2), FRENTE2 - FRENTE - 90, ZTETO - Z2 - 90, V(1, 0, 0), V(0, 1, 0));
painel(PAINEL, V((XS[0] + XS[1]) / 2, FUNDO + 30, (Z1 + Z2) / 2), XS[1] - XS[0] - 90, Z2 - Z1 - 90, X_FRENTE, DIREITA);

// ---------- 7. A TORRE DAS BOLAS ----------
for (const [x, y] of [[-2468, -2056], [-1318, -3085]]) {
  cilindro(CORDA, V(x, y, 3536), V(x, y, 2650), 12, 6);
  esfera(AMARELO, V(x, y, 2380), 290);
}

// ---------- 8. TELAS DE PROTEÇÃO (azul claro, translúcidas) ----------
painel(VIDRO, V((XS[0] + XS[7]) / 2, FUNDO - 20, (Z2 + ZTETO) / 2), XS[7] - XS[0], ZTETO - Z2, V(0, -1, 0), V(1, 0, 0));
painel(VIDRO, V((XS[7] + XS[8]) / 2, FUNDO - 20, TORRE / 2), XS[8] - XS[7], TORRE - 40, V(0, -1, 0), V(1, 0, 0));
painel(VIDRO, V(XS[8] + 20, (FUNDO + FRENTE2) / 2, TORRE / 2), FRENTE2 - FUNDO, TORRE - 40, V(1, 0, 0), V(0, 1, 0));
painel(VIDRO, V(XS[7], (FRENTE + FRENTE2) / 2, REDE / 2 + 80), FRENTE2 - FRENTE, REDE, V(-1, 0, 0), V(0, -1, 0));
painel(VIDRO, V(XS[0] - 20, (FUNDO + FRENTE) / 2, (Z2 + ZTETO) / 2), FRENTE - FUNDO, ZTETO - Z2, V(-1, 0, 0), V(0, -1, 0));

// ---------- montagem final: metros, Y para cima, frente em +Z ----------
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "brinquedao-selva-11m";
cena.add(raiz);
// (x, y, z) do .3ds -> (-x, z, y) em metros: rotação própria (sem espelhar)
const virar = new THREE.Matrix4().set(-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1).premultiply(new THREE.Matrix4().makeScale(0.001, 0.001, 0.001));
for (const [nome, { material: mat, geometrias }] of pecas) {
  if (!geometrias.length) continue;
  const prontas = geometrias.map((g) => {
    let h = g.index ? g.toNonIndexed() : g;
    if (!h.attributes.uv) h.setAttribute("uv", new THREE.Float32BufferAttribute(new Float32Array(h.attributes.position.count * 2), 2));
    if (!h.attributes.normal) h.computeVertexNormals();
    for (const k of Object.keys(h.attributes)) if (!["position", "normal", "uv"].includes(k)) h.deleteAttribute(k);
    h.clearGroups();
    return h;
  });
  let g = mergeGeometries(prontas, false);
  g.applyMatrix4(virar);
  g = mergeVertices(g, 1e-5);
  const malha = new THREE.Mesh(g, mat);
  malha.name = nome;
  raiz.add(malha);
}
// assenta no chão e centraliza
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 100) / 100);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);

// prévia, para conferir de vários lados
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(1200, 700);
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.append(renderer.domElement);
cena.background = new THREE.Color("#0b1a3a");
cena.add(new THREE.HemisphereLight("#ffffff", "#334466", 1.6));
const sol = new THREE.DirectionalLight("#ffffff", 2.2);
sol.position.set(6, 10, 8);
cena.add(sol);
const chao = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.MeshStandardMaterial({ color: "#3a7d3a" }));
chao.rotation.x = -Math.PI / 2;
cena.add(chao);
const camera = new THREE.PerspectiveCamera(40, 1200 / 700, 0.1, 200);
window.ver = (x, y, z) => {
  camera.position.set(x, y, z);
  camera.lookAt(0, 1.5, 0);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.85);
};
window.exportar = async () => {
  cena.remove(chao);
  const exp = new GLTFExporter();
  const glb = await exp.parseAsync(raiz, { binary: true });
  const bytes = new Uint8Array(glb);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
};
window.pronto = true;
