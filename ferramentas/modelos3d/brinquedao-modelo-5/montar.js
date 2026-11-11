// Monta o Brinquedão Modelo 5 (o brinquedão de tubos cor de madeira em L:
// 3,70 m × 1 m de barra, altura de 2 m) em three.js e exporta um .glb.
//
// Não há .3ds da fábrica: tudo sai das quatro imagens do projeto que o
// cliente mandou (a planta cotada, a perspectiva sem fundo e as duas vistas
// do brinquedão num salão; os cavalinhos e a mesinha do salão não são do
// produto).
//  - da planta: o L -- a barra de 3,70 m × 1 m com os quatro módulos (1 m,
//    1 m, 0,70 m e 1 m) e, embaixo à esquerda, a perna com o escorregador
//    saindo para a frente --, a grade de tubos de cima (a travessa dos sacos
//    no meio do 3º módulo), o piso de cada módulo (azul; amarelo com a cunha
//    azul; amarelo com os dois sacos; laranja em dois triângulos), os quatro
//    rolos na frente dos módulos 2 e 3 e o comprimento do escorregador;
//  - da perspectiva (a câmera dela foi calibrada com os cantos da estrutura,
//    erro < 2 px: as medidas que a planta não dá saem dela): o piso a 1 m, o
//    telhado da perna (a frente dela a 1,42 m, os tubos inclinados subindo
//    até o alto da barra), a cunha azul do 2º módulo (0,38 m de altura, a
//    cumeeira no meio dela), os sacos (o da frente laranja, o de trás
//    amarelo), as alturas dos rolos e, no 4º módulo, o degrau triangular a
//    0,62 m (a metade de trás e da direita) embaixo do piso triangular de
//    1 m (a metade da frente e da esquerda), sobre o piso azul do térreo;
//  - das vistas do salão: o mesmo, de frente (os painéis de casinha, a
//    janela em arco, a fresta do painel estreito, os rolos até 0,2 m do
//    chão e a beira do degrau triangular a ~0,6 m).
//
// Coordenadas de trabalho (as mesmas dos outros brinquedões): x ao longo da
// barra (da esquerda para a direita de quem olha de frente), y para o FUNDO
// (y = 0 é a frente da barra; a perna e o escorregador ficam em y < 0), z
// para cima, em milímetros. No fim tudo vira metros, Y para cima e a frente
// em +Z, centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------- as medidas (mm) ----------
const L = 3700; // a barra: 1 m + 1 m + 0,70 m + 1 m
const FUNDO = 1000; // a profundidade da barra
const TOPO = 2000; // a altura total
const R = 40; // o raio dos tubos (8 cm, como na planta)
// os tubos de fora ficam para dentro: o objeto mede 3,70 m × 1 m × 2 m cravados
const ZT = TOPO - R; // os tubos de cima
const ZA = 1000; // os tubos do piso de cima
const ANDAR = ZA + R; // o piso de cima (rente ao alto dos tubos: onde se pisa)
const ZD = 600; // os tubos do degrau triangular do 4º módulo
const DEGRAU = ZD + R; // o degrau (0,64 m)
const ZC = 100; // o quadro rente ao chão do 4º módulo
const CHAO4 = ZC + R; // o piso azul do térreo do 4º módulo
// as linhas de colunas ao longo da barra: a ponta esquerda, os módulos e a ponta direita
const X0 = R, X1 = 1000, X2 = 2000, X3 = 2700, X4 = L - R;
const XP = 620; // o lado direito da perna (a perna vai de X0 a XP)
const XS = 2350; // a travessa dos sacos, no meio do 3º módulo
const YF = R, YT = FUNDO - R; // a frente e o fundo da barra
const YP = -820; // a frente da perna (0,86 m na frente da barra)
const ZP = 1420; // a frente da perna é mais baixa: o telhado sobe dela até o alto da barra
// o escorregador: no meio da perna, da beira do piso até 1,45 m na frente da barra
const XE = (X0 + XP) / 2;

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

// a paleta das imagens do projeto (a planta tem as cores sem sombra)
const COR = {
  madeira: "#7a3d1a", azul: "#1f76d2", amarelo: "#ffe600", laranja: "#ffaa00", cunha: "#1f6fd0",
  rosa: "#f69db3", azulBebe: "#8dbcef", branco: "#f6f6f3", sacoLaranja: "#f79a10", sacoAmarelo: "#f5dc20",
  roloRosa: "#f7a9bf", roloAmarelo: "#ffeb00", roloAzul: "#1f9ff5", roloLaranja: "#ffaa12",
  escorregador: "#ffe600", ferragem: "#8d949e", gancho: "#d9262e",
};

const M = {
  madeira: material("tubos-madeira", { color: COR.madeira, roughness: 0.5 }),
  azul: material("piso-azul", { color: COR.azul, roughness: 0.7 }),
  amarelo: material("piso-amarelo", { color: COR.amarelo, roughness: 0.7 }),
  laranja: material("piso-laranja", { color: COR.laranja, roughness: 0.7 }),
  cunha: material("cunha-azul", { color: COR.cunha, roughness: 0.65 }),
  rosa: material("painel-rosa", { color: COR.rosa, roughness: 0.55, side: THREE.DoubleSide }),
  azulBebe: material("painel-azul", { color: COR.azulBebe, roughness: 0.55, side: THREE.DoubleSide }),
  branco: material("branco", { color: COR.branco, roughness: 0.5 }),
  sacoLaranja: material("saco-laranja", { color: COR.sacoLaranja, roughness: 0.45 }),
  sacoAmarelo: material("saco-amarelo", { color: COR.sacoAmarelo, roughness: 0.45 }),
  rolos: [
    material("rolo-rosa", { color: COR.roloRosa, roughness: 0.5 }),
    material("rolo-amarelo", { color: COR.roloAmarelo, roughness: 0.5 }),
    material("rolo-azul", { color: COR.roloAzul, roughness: 0.5 }),
    material("rolo-laranja", { color: COR.roloLaranja, roughness: 0.5 }),
  ],
  escorregador: material("escorregador-amarelo", { color: COR.escorregador, roughness: 0.3, side: THREE.DoubleSide }),
  ferragem: material("ferragem", { color: COR.ferragem, roughness: 0.4, metalness: 0.5 }),
  gancho: material("ganchos-vermelhos", { color: COR.gancho, roughness: 0.45 }),
};

// ---------- peças básicas (em mm) ----------
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  const g = new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0));
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
// espuma: a caixa com as quinas arredondadas
function almofada(nome, x0, x1, y0, y1, z0, z1, raio = 12) {
  const g = new RoundedBoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0), 2, raio);
  por(nome, g, new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
function cilindro(nome, a, b, r, lados = 16, aberto = false) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const g = new THREE.CylinderGeometry(r, r, dir.length(), lados, 1, aberto);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), dir.clone().normalize());
  por(nome, g, new THREE.Matrix4().compose(a.clone().add(b).multiplyScalar(0.5), q, V(1, 1, 1)));
}
function esfera(nome, c, r, w = 16, h = 10) {
  por(nome, new THREE.SphereGeometry(r, w, h), new THREE.Matrix4().makeTranslation(c.x, c.y, c.z));
}
// uma forma plana (no plano XY) extrudada para cima, de z0 até z0 + altura
function laje(nome, pontos, z0, altura) {
  const forma = new THREE.Shape(pontos.map(([x, y]) => new THREE.Vector2(x, y)));
  por(nome, new THREE.ExtrudeGeometry(forma, { depth: altura, bevelEnabled: false }), new THREE.Matrix4().makeTranslation(0, 0, z0));
}
// uma forma desenhada de frente (no plano XZ: x -> x, y da forma -> z), com
// a espessura para o fundo, de y0 a y0 + espessura
const DE_FRENTE = () => new THREE.Matrix4().makeBasis(V(1, 0, 0), V(0, 0, 1), V(0, -1, 0));
function deFrente(nome, forma, y0, espessura, opcoes = {}) {
  por(nome, new THREE.ExtrudeGeometry(forma, { depth: espessura, bevelEnabled: false, curveSegments: 24, ...opcoes }), DE_FRENTE().setPosition(0, y0 + espessura, 0));
}
const formaDe = (pontos) => new THREE.Shape(pontos.map(([x, z]) => new THREE.Vector2(x, z)));

/* ======================================================================
   1. A ESTRUTURA: os tubos redondos cor de madeira, com os cantos
      arredondados (uma bola do mesmo raio em cada encontro)
   ====================================================================== */
const juntas = new Map();
function junta(p) {
  if (p.z <= 0) return; // no chão a coluna termina reta
  juntas.set(`${Math.round(p.x)},${Math.round(p.y)},${Math.round(p.z)}`, p);
}
function tubo(a, b) {
  cilindro(M.madeira, a, b, R, 18, true);
  junta(a);
  junta(b);
}
const T = (x0, y0, z0, x1, y1, z1) => tubo(V(x0, y0, z0), V(x1, y1, z1));
// as colunas inteiras, do chão ao alto (nas pontas, nos módulos 1/2 e 3/4)
for (const x of [X0, X1, X3, X4]) for (const y of [YF, YT]) T(x, y, 0, x, y, ZT);
// do piso para cima: entre o painel estreito e a perna e entre os módulos 2 e
// 3 (embaixo do piso de 1,70 m dos módulos 2 e 3 não há coluna: é por onde
// pendem os rolos)
for (const [x, y] of [[XP, YF], [X2, YF], [X2, YT]]) T(x, y, ZA, x, y, ZT);
// em cima: a grade de tubos. Na frente, só da perna para a direita (o
// telhado da perna sobe até o alto da barra, sem tubo entre os dois)
T(XP, YF, ZT, X4, YF, ZT);
T(X0, YT, ZT, X4, YT, ZT);
for (const x of [X0, X1, X2, XS, X3, X4]) T(x, YF, ZT, x, YT, ZT);
// o piso de cima: frente, fundo e as travessas em cada módulo
T(X0, YF, ZA, X4, YF, ZA);
T(X0, YT, ZA, X4, YT, ZA);
for (const x of [X0, X1, X2, X3, X4]) T(x, YF, ZA, x, YT, ZA);
// a perna: as duas colunas da frente (mais baixas), o tubo da frente e o
// telhado (os dois tubos que sobem até o alto da barra)
for (const x of [X0, XP]) {
  T(x, YP, 0, x, YP, ZP);
  T(x, YP, ZP, x, YF, ZT);
}
T(X0, YP, ZP, XP, YP, ZP);
// os dois tubos que seguram o escorregador, dos lados dele: do piso até as colunas da frente da perna
const ZTRILHO = 470;
for (const x of [X0, XP]) T(x, YF, ZA, x, YP, ZTRILHO);
// o 4º módulo: o quadro rente ao chão (o piso azul do térreo) e o do degrau
// triangular (no fundo e na ponta direita: a metade de trás e da direita)
T(X3, YF, ZC, X4, YF, ZC);
T(X3, YT, ZC, X4, YT, ZC);
T(X3, YF, ZC, X3, YT, ZC);
T(X4, YF, ZC, X4, YT, ZC);
T(X3, YT, ZD, X4, YT, ZD);
T(X4, YF, ZD, X4, YT, ZD);
// os cantos e os encontros arredondados
for (const p of juntas.values()) esfera(M.madeira, p, R + 0.5, 18, 12);

/* ======================================================================
   2. OS PISOS
   ====================================================================== */
// (as placas ficam entre os tubos, a face de cima rente ao alto deles)
const placa = (cor, x0, x1) => caixa(cor, x0, x1, YF, YT, ANDAR - 40, ANDAR);
placa(M.azul, X0, X1); // 1º módulo: azul
placa(M.amarelo, X1, X2); // 2º: amarelo, com a cunha azul
placa(M.amarelo, X2, X3); // 3º: amarelo, com os sacos
// 4º: dois triângulos laranja, como na planta (a linha da diagonal vai do
// fundo à esquerda até a frente à direita): o piso de 1 m na metade da frente
// e da esquerda (emenda no 3º) e o degrau de 0,64 m na de trás e da direita
laje(M.laranja, [[X3, YT], [X3, YF], [X4, YF]], ANDAR - 40, 40);
laje(M.laranja, [[X3, YT], [X4, YT], [X4, YF]], DEGRAU - 40, 40);
// e o piso azul do térreo do 4º módulo, sobre o quadro rente ao chão
caixa(M.azul, X3, X4, YF, YT, CHAO4 - 40, CHAO4);

/* ======================================================================
   3. A CUNHA AZUL DO 2º MÓDULO (a faixa azul da planta): uma lombada de
      espuma de 0,50 m de base e 0,38 m de altura, de frente para o fundo,
      com a cumeeira arredondada no meio (a linha clara da planta)
   ====================================================================== */
// (`alto` é o da ponta viva: a cumeeira redonda fica a ~0,38 m do piso)
const CUNHA = { x0: 1400, x1: 1900, alto: 435, y0: YF + 30, y1: YT - 30 };
{
  const { x0, x1, alto, y0, y1 } = CUNHA;
  const xc = (x0 + x1) / 2, rc = 55;
  // o perfil: a base no piso, as duas águas e a cumeeira redonda
  const meia = (x1 - x0) / 2;
  const ang = Math.atan2(alto, meia); // a inclinação das águas
  const forma = new THREE.Shape();
  forma.moveTo(x0, ANDAR);
  forma.lineTo(x1, ANDAR);
  // a água da direita até a tangente da cumeeira
  const zc = ANDAR + alto - rc / Math.cos(ang);
  forma.lineTo(xc + rc * Math.sin(ang), zc + rc * Math.cos(ang));
  forma.absarc(xc, zc, rc, PI / 2 - ang, PI / 2 + ang, false);
  forma.lineTo(x0, ANDAR);
  const bisel = 22;
  por(M.cunha, new THREE.ExtrudeGeometry(forma, { depth: y1 - y0 - 2 * bisel, bevelEnabled: true, bevelSize: 10, bevelThickness: bisel, bevelSegments: 3, curveSegments: 10 }),
    DE_FRENTE().setPosition(0, y1 - bisel, 0));
}

/* ======================================================================
   4. OS PAINÉIS DA FRENTE: as casinhas (rosa no 2º módulo, azul-clara no
      4º) com o telhado branco e a janela em arco, e o painel rosa estreito
      com a fresta de janela alta (no 1º módulo, ao lado da perna)
   ====================================================================== */
const PZ0 = ZA + R, PZ1 = ZT - R; // do tubo do piso ao tubo de cima
const PY = YF - 10, PESP = 20; // o painel no plano das colunas da frente
// a janela em arco: o vão (largura 0,46 m, de 1,19 m até o alto do arco, a 1,77 m)
const JANELA = { meia: 230, z0: 1190, zArco: 1540 };
function contornoJanela(path, xc, folga = 0, horario = false) {
  const { meia, z0, zArco } = JANELA;
  const m = meia + folga, b = z0 - folga;
  if (!horario) {
    path.moveTo(xc - m, b);
    path.lineTo(xc + m, b);
    path.lineTo(xc + m, zArco);
    path.absarc(xc, zArco, m, 0, PI, false);
    path.lineTo(xc - m, b);
  } else {
    path.moveTo(xc - m, b);
    path.lineTo(xc - m, zArco);
    path.absarc(xc, zArco, m, PI, 0, true);
    path.lineTo(xc + m, b);
    path.lineTo(xc - m, b);
  }
  return path;
}
function casinha(cor, xa, xb) {
  const xc = (xa + xb) / 2;
  // o painel com o vão da janela
  const painel = formaDe([[xa, PZ0], [xb, PZ0], [xb, PZ1], [xa, PZ1]]);
  painel.holes.push(contornoJanela(new THREE.Path(), xc, 0, true));
  deFrente(cor, painel, PY, PESP);
  // a moldura branca da janela (dos dois lados), o montante e a travessa
  const moldura = contornoJanela(new THREE.Shape(), xc, 32);
  moldura.holes.push(contornoJanela(new THREE.Path(), xc, 0, true));
  deFrente(M.branco, moldura, PY - 4, PESP + 8);
  const { meia, z0, zArco } = JANELA;
  caixa(M.branco, xc - 13, xc + 13, PY - 3, PY + PESP + 3, z0, zArco + meia);
  caixa(M.branco, xc - meia, xc + meia, PY - 3, PY + PESP + 3, 1440, 1466);
  // o telhado: a faixa branca em V invertido, do meio da altura dos lados até o alto
  const ze = 1590, za = PZ1 - 25, w = 46;
  const telhado = formaDe([
    [xa, ze], [xc, za], [xb, ze], [xb, ze - w * 1.35], [xc, za - w * 1.6], [xa, ze - w * 1.35],
  ]);
  deFrente(M.branco, telhado, PY - 4, 4);
}
casinha(M.rosa, X1 + R, X2 - R);
casinha(M.azulBebe, X3 + R, X4 - R);
// o painel rosa estreito (1º módulo, entre a perna e o 2º módulo), com a fresta alta
{
  const xa = XP + R, xb = X1 - R, xc = (xa + xb) / 2;
  const f = { meia: 70, z0: 1120, z1: 1840 };
  const painel = formaDe([[xa, PZ0], [xb, PZ0], [xb, PZ1], [xa, PZ1]]);
  painel.holes.push(new THREE.Path([[xc - f.meia, f.z0], [xc - f.meia, f.z1], [xc + f.meia, f.z1], [xc + f.meia, f.z0]].map(([x, z]) => new THREE.Vector2(x, z))));
  deFrente(M.rosa, painel, PY, PESP);
  const moldura = formaDe([[xc - f.meia - 26, f.z0 - 26], [xc + f.meia + 26, f.z0 - 26], [xc + f.meia + 26, f.z1 + 26], [xc - f.meia - 26, f.z1 + 26]]);
  moldura.holes.push(new THREE.Path([[xc - f.meia, f.z0], [xc - f.meia, f.z1], [xc + f.meia, f.z1], [xc + f.meia, f.z0]].map(([x, z]) => new THREE.Vector2(x, z))));
  deFrente(M.branco, moldura, PY - 4, PESP + 8);
}

/* ======================================================================
   5. OS SACOS DE PANCADA (no 3º módulo, pendurados na travessa do meio):
      o da frente laranja, o de trás amarelo, como na planta
   ====================================================================== */
const SACOS = [
  { y: 270, cor: M.sacoLaranja },
  { y: 740, cor: M.sacoAmarelo },
];
const SACO = { r: 110, z0: 1240, z1: 1740, ponta: 1850 };
for (const { y, cor } of SACOS) {
  const { r, z0, z1, ponta } = SACO;
  // o corpo, o fundo arredondado e o "ombro" em cone até a alça
  const perfilSaco = [];
  for (let i = 0; i <= 6; i++) {
    const a = (i / 6) * (PI / 2);
    perfilSaco.push(new THREE.Vector2(Math.sin(a) * r, z0 + 40 - Math.cos(a) * 40));
  }
  perfilSaco.push(new THREE.Vector2(r, z1), new THREE.Vector2(r * 0.42, ponta), new THREE.Vector2(0, ponta));
  const g = new THREE.LatheGeometry(perfilSaco, 24);
  g.rotateX(PI / 2); // o eixo do torno (y) vira o z
  por(cor, g, new THREE.Matrix4().makeTranslation(XS, y, 0));
  // a alça e o gancho vermelho preso embaixo da travessa
  const zg = ZT - R - 16;
  cilindro(M.ferragem, V(XS, y, ponta - 5), V(XS, y, zg - 16), 9, 8);
  por(M.gancho, new THREE.TorusGeometry(17, 6, 8, 18), new THREE.Matrix4().makeRotationX(PI / 2).setPosition(XS, y, zg));
}

/* ======================================================================
   6. OS ROLOS: quatro rolos de espuma em pé, rosa, amarelo, azul e
      laranja, pendurados na frente do piso dos módulos 2 e 3 até perto do
      chão (0,2 m), encostados embaixo do tubo da frente
   ====================================================================== */
const ROLOS = [1478, 1765, 2058, 2364];
const ROLO = { r: 70, y: YF - 20, z0: 200, z1: ZA - R + 6 };
ROLOS.forEach((x, k) => {
  const { r, y, z0, z1 } = ROLO;
  const g = new THREE.CapsuleGeometry(r, z1 - z0 - 2 * r, 6, 20);
  g.rotateX(PI / 2);
  por(M.rolos[k], g, new THREE.Matrix4().makeTranslation(x, y, (z0 + z1) / 2));
});

/* ======================================================================
   7. O ESCORREGADOR AMARELO: largo, de bordas arredondadas, sai da beira
      do piso do 1º módulo, desce pela perna (entre as duas colunas da
      frente) e termina 1,45 m na frente da barra, nas "orelhas" redondas
   ====================================================================== */
const ESC = {
  meiaCama: 200, // a cama: 0,40 m de largura por dentro (passa entre as colunas da perna com 1 cm de folga)
  parede: 40, // a espessura das paredes
  altoParede: 130, // a altura das paredes acima da cama
  fundo: 40, // a espessura da cama
  // o eixo da cama (y, z): a boca 4 cm abaixo do piso, presa no tubo da
  // frente, a descida (~40° no começo, ~32° depois: a beira das paredes da
  // perspectiva, medida pela câmera calibrada) e a saída quase plana a 0,17 m
  eixo: [[YF + 40, ANDAR - 36], [0, ANDAR - 62], [-150, 860], [-330, 690], [-680, 480], [-1020, 250], [-1170, 190], [-1290, 172], [-1410, 170]],
  orelha: { y: -1270, z: 225, r: 190, esp: 45 },
};
{
  const { meiaCama: bi, parede: tw, altoParede: hw, fundo: tb, eixo, orelha } = ESC;
  const bo = bi + tw;
  const curva = new THREE.CatmullRomCurve3(eixo.map(([y, z]) => V(XE, y, z)), false, "centripetal");
  const N = 72;
  const pts = curva.getSpacedPoints(N);
  // a seção em U (u: para o lado, v: para cima da cama), com a borda de
  // cima de cada parede arredondada (meia volta de raio = metade da parede)
  const secao = [];
  const arco = (cu, cv, r, a0, a1, n) => {
    for (let i = 0; i <= n; i++) {
      const a = a0 + ((a1 - a0) * i) / n;
      secao.push([cu + r * Math.cos(a), cv + r * Math.sin(a)]);
    }
  };
  secao.push([-bi, hw]);
  arco(-bi + 25, 25, 25, PI, 1.5 * PI, 3); // o canto de dentro, arredondado
  arco(bi - 25, 25, 25, 1.5 * PI, 2 * PI, 3);
  secao.push([bi, hw]);
  arco(bi + tw / 2, hw, tw / 2, PI, 0, 5); // a borda de cima da parede direita
  secao.push([bo, -tb + 15]);
  arco(bo - 15, -tb + 15, 15, 0, -PI / 2, 2);
  arco(-bo + 15, -tb + 15, 15, -PI / 2, -PI, 2);
  secao.push([-bo, hw]);
  arco(-bi - tw / 2, hw, tw / 2, PI, 0, 5); // a da parede esquerda
  // cada aresta da seção vira uma faixa ao longo do escorregador (as normais
  // lisas no comprimento e quebradas nos cantos)
  const B = V(1, 0, 0);
  const anel = pts.map((p, k) => {
    const t = curva.getTangentAt(k / N);
    const n = new THREE.Vector3().crossVectors(t, B).normalize(); // para cima da cama
    return secao.map(([u, v]) => p.clone().addScaledVector(B, u).addScaledVector(n, v));
  });
  for (let i = 0; i < secao.length - 1; i++) {
    const pos = [];
    for (let k = 0; k <= N; k++) pos.push(...anel[k][i].toArray(), ...anel[k][i + 1].toArray());
    const idx = [];
    for (let k = 0; k < N; k++) {
      const a = 2 * k, b = a + 1, c = a + 2, d = a + 3;
      idx.push(a, c, b, b, c, d);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setIndex(idx);
    g.computeVertexNormals();
    por(M.escorregador, g);
  }
  // as duas pontas fechadas (a seção, triangulada)
  const tris = THREE.ShapeUtils.triangulateShape(secao.map(([u, v]) => new THREE.Vector2(u, v)), []);
  for (const [k, inverter] of [[0, true], [N, false]]) {
    const pos = anel[k].flatMap((p) => p.toArray());
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setIndex(tris.flatMap(([a, b, c]) => (inverter ? [a, c, b] : [a, b, c])));
    g.computeVertexNormals();
    por(M.escorregador, g);
  }
  // as orelhas: os discos redondos dos dois lados da saída, rente ao chão
  for (const lado of [-1, 1]) {
    const x = XE + lado * (bo + orelha.esp / 2 - 6);
    const g = new THREE.CylinderGeometry(orelha.r, orelha.r, orelha.esp, 40, 1, false);
    g.rotateZ(PI / 2);
    por(M.escorregador, g, new THREE.Matrix4().makeTranslation(x, orelha.y, orelha.z));
    // a beira arredondada do disco
    const aro = new THREE.TorusGeometry(orelha.r, orelha.esp / 2, 8, 40);
    aro.rotateY(PI / 2);
    por(M.escorregador, aro, new THREE.Matrix4().makeTranslation(x, orelha.y, orelha.z));
  }
}

/* ======================================================================
   MONTAGEM FINAL: metros, Y para cima, a frente em +Z; junta por material,
   centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "brinquedao-modelo-5";
cena.add(raiz);
// (x, y, z) de trabalho -> (x, z, -y) em metros: rotação própria (sem espelhar)
const virar = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1).multiply(new THREE.Matrix4().makeScale(0.001, 0.001, 0.001));
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
const caixaTotal = new THREE.Box3().setFromObject(raiz);
const centro = caixaTotal.getCenter(new THREE.Vector3());
raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixaTotal.min.y, -centro.z));
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 100) / 100);
// o deslocamento que leva as coordenadas de trabalho (em metros, já viradas)
// ao objeto: o passeio da Arena usa (M5, em core/static/site/arena/caminhos.js)
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
sol.position.set(3, 8, 6);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 1, far: 30 });
sol.shadow.bias = -0.0004;
cena.add(sol);
raiz.traverse((o) => { if (o.isMesh) { o.castShadow = !o.material.transparent; o.receiveShadow = true; } });
// o chão só das vistas (não vai para o .glb): recebe a sombra
const chao = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: 0.2 }));
chao.rotation.x = -PI / 2;
chao.receiveShadow = true;
cena.add(chao);
const piso2 = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshStandardMaterial({ color: "#3d4a5c", roughness: 1 }));
piso2.rotation.x = -PI / 2;
piso2.position.y = -0.002;
cena.add(piso2);
const camera = new THREE.PerspectiveCamera(34, 1600 / 1000, 0.05, 200);
function tamanho(w, h) {
  if (renderer.domElement.width !== w || renderer.domElement.height !== h) renderer.setSize(w, h);
}
window.ver = (x, y, z, alvo = [0, 1, 0], fundo = "#0b1a3a", fov = 34, sombra = true) => {
  tamanho(1600, 1000);
  cena.background = new THREE.Color(fundo);
  piso2.visible = fundo === "#0b1a3a"; // no fundo claro das fotos, só a sombra
  chao.visible = sombra;
  camera.aspect = 1600 / 1000;
  camera.fov = fov;
  camera.updateProjectionMatrix();
  camera.position.set(x, y, z);
  camera.lookAt(...alvo);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
// sem perspectiva: de cima (como a planta, o fundo do brinquedo para cima) ou de frente
window.verOrto = (lado = "cima", largura = 5, fundo = "#0b1a3a") => {
  tamanho(1600, 1000);
  cena.background = new THREE.Color(fundo);
  piso2.visible = fundo === "#0b1a3a" && lado !== "cima";
  chao.visible = false;
  renderer.shadowMap.enabled = false;
  cena.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
  const alto = (largura * 1000) / 1600;
  const orto = new THREE.OrthographicCamera(-largura / 2, largura / 2, alto / 2, -alto / 2, 0.1, 100);
  if (lado === "cima") {
    orto.position.set(0, 30, 0);
    orto.up.set(0, 0, -1);
    orto.lookAt(0, 0, 0);
  } else {
    orto.position.set(0, 1, 30);
    orto.lookAt(0, 1, 0);
  }
  renderer.render(cena, orto);
  renderer.shadowMap.enabled = true;
  cena.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
  return renderer.domElement.toDataURL("image/jpeg", 0.9);
};
// Do ponto da perspectiva da fábrica: a câmera calibrada na imagem (a matriz
// 3 × 4 que leva um ponto de trabalho, em metros, ao pixel), decomposta no
// gerar.cjs em posição, eixos e lente. `cam`: { pos, eixos (x, y, z da
// câmera do three, em metros de trabalho), proj (16, coluna a coluna), w, h }
window.verProjeto = (cam, fundo = "#ffffff") => {
  tamanho(cam.w, cam.h);
  cena.background = new THREE.Color(fundo);
  piso2.visible = false;
  chao.visible = true;
  const paraObjeto = (p) => V(...window.noObjeto(p[0] * 1000, p[1] * 1000, p[2] * 1000));
  const origem = paraObjeto(cam.pos);
  const eixo = (e) => paraObjeto([cam.pos[0] + e[0], cam.pos[1] + e[1], cam.pos[2] + e[2]]).sub(origem);
  const proj = new THREE.PerspectiveCamera();
  proj.matrixAutoUpdate = false;
  proj.matrixWorld.makeBasis(eixo(cam.eixos[0]), eixo(cam.eixos[1]), eixo(cam.eixos[2])).setPosition(origem);
  proj.matrixWorldInverse.copy(proj.matrixWorld).invert();
  proj.projectionMatrix.fromArray(cam.proj);
  proj.projectionMatrixInverse.copy(proj.projectionMatrix).invert();
  renderer.render(cena, proj);
  const url = renderer.domElement.toDataURL("image/png");
  tamanho(1600, 1000);
  return url;
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
