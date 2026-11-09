// Monta o Air Game Hockey Espacial em three.js e exporta um .glb.
//
// É a MESMA máquina do Air Game Hockey (a mesa de air hockey de 1,00 m de
// altura, 1,10 m de largura e 2,10 m de comprimento), só com os adesivos
// novos, do espaço: o logotipo HOCKEY KIDS, alienígenas astronautas, discos
// voadores, planetas, estrelas e o chão lunar laranja.
//
// A arte NÃO é desenhada aqui: cada adesivo é um arquivo da pasta adesivos/
// (adesivos/<peça>.png, recortado da folha de adesivos da fábrica pelo
// recortar_adesivos.py; enquanto a folha não chega, a arte provisória do
// desenhar_provisorios.py). Este arquivo faz a mesa e põe cada adesivo na sua
// face, na posição certa; a peça recortada (as laterais compridas) leva a
// imagem inteira e o contorno da peça corta o que sobra.
//
// As peças (cada uma vista DE FORA, em pé, como na folha):
//   tampo               o tampo inteiro, deitado: 2100 x 1064 mm; a cabeceira
//                       de trás (a da lateral esquerda 2) à esquerda da
//                       imagem e a da frente (lateral direita 2) à direita; o
//                       alto da imagem é o lado direito da mesa
//   lateral-esquerda    a lateral comprida da esquerda (de quem joga na
//   lateral-direita     frente): 2100 x 1000 mm, recortada (o alto sobe nas
//                       duas pontas e afunda um pouco no meio; embaixo, o vão
//                       entre os dois pés largos)
//   lateral-esquerda-2  as cabeceiras (as pontas curtas): 1064 x 795 mm,
//   lateral-direita-2   retângulos; a esquerda 2 é a de trás, a direita 2 a da frente
// O tamanho de cada peça e o contorno vão para o pecas.json (o gerar.cjs
// grava): é ele que o recortar_adesivos.py e o desenhar_provisorios.py leem.
//
// Coordenadas: as do three.js, em milímetros: x na largura (da esquerda para a
// direita de quem joga na frente), y para cima, z no comprimento (a frente da
// mesa, a cabeceira da lateral direita 2, em +z). No fim tudo vira metros,
// centralizado e no chão.
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------- as medidas (mm) ----------
const COMP = 2100; // o comprimento (z)
const LARG = 1100; // a largura (x)
const ALT = 1000; // a altura: a ponta das laterais
const ESP = 18; // o MDF das laterais e das cabeceiras
const XF = LARG / 2; // 550: a face de fora das laterais compridas
const XD = XF - ESP; // 532: a face de dentro
const ZF = COMP / 2; // 1050: a face de fora das cabeceiras
const ZD = ZF - ESP; // 1032
const TAMPO = 820; // a superfície de jogo
const TAMPO_ESP = 25;
const CABECEIRA = TAMPO - TAMPO_ESP; // 795: o alto das cabeceiras, embaixo do tampo
// a borda (as réguas em volta do campo): de lado e, nas cabeceiras, mais
// larga, com a boca do gol no meio
const BORDA = { altura: 40, lado: 35, cabeceira: 80, gol: 300, fundoGol: 15 };
// o desenho das laterais compridas: o alto sobe nas pontas (até a altura da
// mesa) e afunda no meio; embaixo, os dois pés largos e o vão entre eles
const LATERAL = { meio: 885, ponta: ALT, pe: 300, vao: 470, raioVao: 110, raioPonta: 60 };
// a resolução máxima de cada adesivo dentro do .glb (o lado maior, em px)
const RESOLUCAO = { tampo: 1024, "lateral-esquerda": 1024, "lateral-direita": 1024, "lateral-esquerda-2": 512, "lateral-direita-2": 512 };
const QUALIDADE_JPEG = 0.82;

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
  azul: "#1d4f8f", // a pintura da mesa (e o azul de baixo das cabeceiras)
  borda: "#2457b8", // as réguas da borda
  boca: "#0d1420", // a boca do gol
  soprador: "#3a3f48",
  grade: "#15181d",
  vermelho: "#e2232a",
  verde: "#2fbf4a",
  disco: "#ffcf1f",
  branco: "#f4f6f9",
};
const M = {
  pintura: material("pintura-azul", { color: COR.azul, roughness: 0.55 }),
  borda: material("borda", { color: COR.borda, roughness: 0.35 }),
  boca: material("boca-do-gol", { color: COR.boca, roughness: 0.9 }),
  soprador: material("soprador", { color: COR.soprador, roughness: 0.6, metalness: 0.3 }),
  grade: material("grade-do-soprador", { color: COR.grade, roughness: 0.8 }),
  rebatedorVermelho: material("rebatedor-vermelho", { color: COR.vermelho, roughness: 0.3 }),
  rebatedorVerde: material("rebatedor-verde", { color: COR.verde, roughness: 0.3 }),
  disco: material("disco", { color: COR.disco, roughness: 0.3 }),
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
async function adesivo(peca, mm, onde, contorno = null) {
  const arquivo = `adesivos/${peca}.png`;
  PECAS[peca] = { arquivo, mm: mm.map((v) => Math.round(v)), onde, ...(contorno ? { contorno } : {}) };
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
// o adesivo fica 1 mm fora da madeira: a medida de fora é a do adesivo
const PELE = 1;
// uma placa: o contorno extrudado para DENTRO (a espessura), na pintura
function placa(nome, pontos, b, espessura) {
  const g = new THREE.ExtrudeGeometry(forma(pontos), { depth: espessura, bevelEnabled: false });
  g.translate(0, 0, -espessura - PELE);
  por(nome, g, b.matriz());
}
// o adesivo da face de fora: o contorno (ou o retângulo) da peça; a imagem
// cobre o retângulo `ret` [a0, b0, a1, b1] e o contorno corta o resto
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
// o contorno no pecas.json: em frações da imagem (0 a 1), a partir do canto de cima à esquerda
const contornoDaImagem = (pontos, ret) => pontos.map(([a, b]) => [
  +((a - ret[0]) / (ret[2] - ret[0])).toFixed(4), +(1 - (b - ret[1]) / (ret[3] - ret[1])).toFixed(4),
]);

/* ======================================================================
   1. AS LATERAIS COMPRIDAS: o contorno recortado (os pés e a onda de cima)
   ====================================================================== */
// no plano da lateral, vista de fora: a = ao longo da mesa (de -1050 a 1050),
// b = a altura. O desenho é simétrico: serve para os dois lados.
const CONTORNO_LATERAL = (() => {
  const { meio, ponta, pe, vao, raioVao, raioPonta } = LATERAL;
  const zp = ZF - pe; // onde acaba cada pé
  const pts = [];
  const arco = (cx, cy, r, a0, a1, n = 10) => {
    for (let i = 0; i <= n; i++) {
      const a = a0 + ((a1 - a0) * i) / n;
      pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
    }
  };
  // o alto: plano no meio, subindo para as pontas (smoothstep a partir de 30% da metade)
  const topo = (a) => {
    const u = Math.min(1, Math.max(0, (Math.abs(a) / ZF - 0.3) / 0.7));
    return meio + (ponta - meio) * u * u * (3 - 2 * u);
  };
  // o pé de trás, o vão (as quinas de cima arredondadas) e o pé da frente
  pts.push([-ZF, 0], [-zp, 0]);
  arco(-zp + raioVao, vao - raioVao, raioVao, PI, PI / 2);
  arco(zp - raioVao, vao - raioVao, raioVao, PI / 2, 0);
  pts.push([zp, 0], [ZF, 0]);
  // a ponta da frente arredondada e a onda de cima, da frente para trás
  arco(ZF - raioPonta, ponta - raioPonta, raioPonta, 0, PI / 2, 8);
  for (let i = 1; i < 48; i++) {
    const a = ZF - raioPonta - ((2 * (ZF - raioPonta)) * i) / 48;
    pts.push([a, topo(a)]);
  }
  arco(-ZF + raioPonta, ponta - raioPonta, raioPonta, PI / 2, PI, 8);
  return pts;
})();
const RET_LATERAL = [-ZF, 0, ZF, ALT];
const LADOS = {
  esquerda: base(V(-XF, 0, 0), V(0, 0, 1), V(0, 1, 0)), // de fora (-x): a frente fica à direita
  direita: base(V(XF, 0, 0), V(0, 0, -1), V(0, 1, 0)), // de fora (+x): a frente fica à esquerda
};
for (const [lado, b] of Object.entries(LADOS)) {
  placa(M.pintura, CONTORNO_LATERAL, b, ESP);
  const m = await adesivo(`lateral-${lado}`, [COMP, ALT], `a lateral comprida da ${lado}, vista de fora`, contornoDaImagem(CONTORNO_LATERAL, RET_LATERAL));
  colar(m, CONTORNO_LATERAL, b, RET_LATERAL);
}

/* ======================================================================
   2. AS CABECEIRAS (as pontas curtas): retângulos até o tampo
   ====================================================================== */
// a de trás é a "lateral esquerda 2" (à esquerda do tampo, na folha); a da frente, a "direita 2"
const CABECEIRAS = {
  "lateral-esquerda-2": { z: -ZF, b: base(V(XD, 0, -ZF), V(-1, 0, 0), V(0, 1, 0)), onde: "a cabeceira de trás (a ponta curta à esquerda do tampo), vista de fora" },
  "lateral-direita-2": { z: ZF, b: base(V(-XD, 0, ZF), V(1, 0, 0), V(0, 1, 0)), onde: "a cabeceira da frente (a ponta curta à direita do tampo), vista de fora" },
};
for (const [peca, { z, b, onde }] of Object.entries(CABECEIRAS)) {
  caixa(M.pintura, -XD, XD, 0, CABECEIRA, z - Math.sign(z) * (ESP + PELE), z - Math.sign(z) * PELE);
  const m = await adesivo(peca, [2 * XD, CABECEIRA], onde);
  colar(m, retangulo(0, 0, 2 * XD, CABECEIRA), b, [0, 0, 2 * XD, CABECEIRA]);
}

/* ======================================================================
   3. O TAMPO: a prancha com o adesivo, a borda em volta e as bocas do gol
   ====================================================================== */
caixa(M.pintura, -XD, XD, CABECEIRA, TAMPO - PELE, -ZF, ZF);
{
  // de cima, com a frente (+z) à direita: o alto da imagem é o lado direito (+x)
  const b = base(V(0, TAMPO, -ZF), V(0, 0, 1), V(1, 0, 0));
  const m = await adesivo("tampo", [COMP, 2 * XD], "o tampo inteiro, de cima: a cabeceira de trás à esquerda, o lado direito da mesa no alto");
  colar(m, retangulo(0, -XD, COMP, XD), b, [0, -XD, COMP, XD]);
}
// a caixa de ar embaixo do tampo e o soprador (aparecem pelo vão das laterais)
caixa(M.pintura, -XD, XD, 650, CABECEIRA, -ZD, ZD);
caixa(M.soprador, -240, 240, 540, 650, -280, 280);
cilindro(M.grade, 0, 530, 540, 0, 150, 40);
{
  const { altura, lado, cabeceira, gol, fundoGol } = BORDA;
  const y1 = TAMPO + altura;
  // as réguas compridas, de ponta a ponta
  caixa(M.borda, -XD, -XD + lado, TAMPO, y1, -ZF, ZF);
  caixa(M.borda, XD - lado, XD, TAMPO, y1, -ZF, ZF);
  for (const s of [-1, 1]) {
    const zFora = s * ZF;
    const zDentro = s * (ZF - cabeceira);
    // a régua da cabeceira, com o vão do gol no meio
    caixa(M.borda, -XD + lado, -gol / 2, TAMPO, y1, zDentro, zFora);
    caixa(M.borda, gol / 2, XD - lado, TAMPO, y1, zDentro, zFora);
    // o gol: o fundo da boca (a parede de fora) e a boca escura, onde o disco cai
    caixa(M.borda, -gol / 2, gol / 2, TAMPO, y1, zFora - s * fundoGol, zFora);
    caixa(M.boca, -gol / 2, gol / 2, TAMPO, TAMPO + 1.5, zDentro, zFora - s * fundoGol);
  }
}

/* ======================================================================
   4. OS REBATEDORES E O DISCO, em cima do campo
   ====================================================================== */
function rebatedor(nome, z) {
  const perfil = [ // o meio perfil, girado em volta do eixo: a base larga, o pescoço e a pega
    [0, 0], [48, 0], [50, 3], [50, 14], [44, 20], [24, 24], [19, 30], [18, 58], [22, 64], [24, 72], [21, 80], [12, 85], [0, 86],
  ].map(([r, y]) => new THREE.Vector2(r, y));
  por(nome, new THREE.LatheGeometry(perfil, 40), new THREE.Matrix4().makeTranslation(0, TAMPO + 0.5, z));
}
rebatedor(M.rebatedorVermelho, ZF - 430);
rebatedor(M.rebatedorVerde, -ZF + 430);
cilindro(M.disco, -140, TAMPO + 0.5, TAMPO + 6.5, 180, 31, 32);

/* ======================================================================
   MONTAGEM FINAL: metros, junta por material, centraliza e assenta no chão
   ====================================================================== */
const cena = new THREE.Scene();
const raiz = new THREE.Group();
raiz.name = "air-game-hockey-espacial";
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
