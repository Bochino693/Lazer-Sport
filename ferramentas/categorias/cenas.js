/* ======================================================================
   AS FOTOS DAS CATEGORIAS: uma cena 3D por categoria, feita com o que é
   da fábrica -- os objetos 3D (.glb) das máquinas e dos brinquedões, as
   áreas do projetista do painel (montar3d-gerador.js e montar3d-pecas.js,
   o mesmo código do "Monte seu espaço") e, para as máquinas que ainda não
   têm .glb, as peças de pecas.js.

   O gerar.cjs abre esta página num Chromium sem tela e chama
   `renderizar(chave)` para cada categoria: a cena sai com o fundo
   transparente (só o objeto e a sombra no chão), e o compor.py põe o fundo
   claro e faz o corte 4:3 do card.
   ====================================================================== */

import * as T from "three";
import { GLTFLoader } from "../../core/static/vendor/three/GLTFLoader.js";
import * as utilidades from "../../core/static/vendor/three/BufferGeometryUtils.js";
import * as pecasDoPainel from "../../sistema_interno/static/interno/montar3d-pecas.js";
import * as gerador from "../../sistema_interno/static/interno/montar3d-gerador.js";
import { criarPecas } from "./pecas.js";

const LARGURA = 2400, ALTURA = 1800;
const GRAU = Math.PI / 180;

const renderer = new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(LARGURA, ALTURA);
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = T.SRGBColorSpace;
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = T.VSMShadowMap; // a sombra macia de estúdio (com o raio abaixo)
document.body.append(renderer.domElement);

/* ---------------------------------------------------------------- a luz do estúdio */
const cena = new T.Scene();
// o reflexo: uma sala clara com três painéis de luz (dá brilho ao que é liso)
{
  const sala = new T.Scene();
  const parede = new T.Mesh(new T.BoxGeometry(30, 14, 30), new T.MeshBasicMaterial({ color: "#c9d3e2", side: T.BackSide }));
  parede.position.y = 5;
  sala.add(parede);
  for (const [x, y, z, l, a, forca] of [[0, 11.9, 0, 14, 10, 5], [-14.9, 5, 3, 0.1, 6, 3], [14.9, 6, -3, 0.1, 8, 2.2]]) {
    const painel = new T.Mesh(new T.BoxGeometry(l || 0.1, l ? 0.1 : a, l ? a : 10), new T.MeshBasicMaterial({ color: new T.Color(forca, forca, forca) }));
    painel.position.set(x, y, z);
    sala.add(painel);
  }
  const pmrem = new T.PMREMGenerator(renderer);
  cena.environment = pmrem.fromScene(sala, 0.04).texture;
  cena.environmentIntensity = 0.55;
}
cena.add(new T.HemisphereLight("#ffffff", "#a3adbd", 1.25));
const sol = new T.DirectionalLight("#fff8ef", 2.4);
sol.castShadow = true;
sol.shadow.mapSize.set(4096, 4096);
sol.shadow.bias = -0.0004;
sol.shadow.radius = 14;
sol.shadow.blurSamples = 24;
cena.add(sol, sol.target);
const preenche = new T.DirectionalLight("#e8f0ff", 0.7);
cena.add(preenche, preenche.target);
const contra = new T.DirectionalLight("#ffffff", 0.9);
cena.add(contra, contra.target);
// o chão: só a sombra (o fundo é do compor.py)
const chao = new T.Mesh(new T.PlaneGeometry(400, 400), new T.ShadowMaterial({ opacity: 0.26 }));
chao.rotation.x = -Math.PI / 2;
chao.receiveShadow = true;
cena.add(chao);
const camera = new T.PerspectiveCamera(28, LARGURA / ALTURA, 0.05, 500);

/* ---------------------------------------------------------------- as peças */
const P = criarPecas(T);
const base = pecasDoPainel.desenhosBase(T, utilidades);
const DESENHOS = Object.assign(base.desenhos, pecasDoPainel.desenhosExtra(T, base.ferramentas));
const PADROES = Object.assign({}, pecasDoPainel.CATALOGO_BASE, pecasDoPainel.CATALOGO_EXTRA);
const leitor = new GLTFLoader();
const glbs = new Map();

/** O objeto 3D da fábrica (core/static/site/arena/modelos/<nome>.glb), no chão e no meio. */
async function glb(nome, { x = 0, y = 0, z = 0, r = 0, escala = 1 } = {}) {
  const url = `../../core/static/site/arena/modelos/${nome}.glb`;
  if (!glbs.has(url)) glbs.set(url, leitor.loadAsync(url));
  const objeto = (await glbs.get(url)).scene.clone(true);
  objeto.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  const caixa = new T.Box3().setFromObject(objeto);
  objeto.position.set(-(caixa.min.x + caixa.max.x) / 2, -caixa.min.y, -(caixa.min.z + caixa.max.z) / 2);
  return colocar(objeto, { x, y, z, r, escala });
}

/** Uma área do projetista do painel (o mesmo do "Monte seu espaço"), pela medida e pela cor. */
function area(tipo, medidas, cor, semente, opcoes = {}) {
  const ideia = gerador.gerar(tipo, medidas, cor, semente, opcoes);
  const g = new T.Group();
  for (const peca of ideia.pecas) {
    const desenho = DESENHOS[peca.tipo];
    if (!desenho) continue;
    const d = Object.assign({}, (PADROES[peca.tipo] || {}).d || {}, peca.d || {});
    const pg = new T.Group();
    desenho(d, peca.cor, { cor2: peca.cor2 }).forEach((m) => pg.add(m));
    pg.position.fromArray(peca.p || [0, 0, 0]);
    pg.rotation.y = ((peca.r || 0) * Math.PI) / 180;
    g.add(pg);
  }
  P.sombra(g);
  return g;
}

/** Uma peça do projetista do painel (montar3d-pecas.js), avulsa: para as cenas montadas à mão. */
function peca(tipo, p, d = {}, cor, opcoes = {}, r = 0) {
  const dd = Object.assign({}, (PADROES[tipo] || {}).d || {}, d);
  const g = new T.Group();
  DESENHOS[tipo](dd, cor || PADROES[tipo].cor, opcoes).forEach((m) => g.add(m));
  g.position.fromArray(p);
  g.rotation.y = r * GRAU;
  return P.sombra(g);
}

function colocar(objeto, { x = 0, y = 0, z = 0, r = 0, escala = 1 } = {}) {
  const g = new T.Group();
  g.add(objeto);
  g.position.set(x, y, z);
  g.rotation.y = r * GRAU;
  g.scale.setScalar(escala);
  return g;
}

function grupo(...itens) {
  const g = new T.Group();
  itens.forEach((i) => g.add(i));
  return g;
}

/** Os pinos de boliche em triângulo (a ponta para +z), a partir de (x, z). */
function pinos(x, z, fileiras = 3, passo = 0.16, r = 0, escala = 1) {
  const g = new T.Group();
  for (let f = 0; f < fileiras; f++) {
    for (let i = 0; i <= f; i++) g.add(colocar(P.pino(), { x: (i - f / 2) * passo, z: -f * passo * 0.88 }));
  }
  return colocar(g, { x, z, r, escala });
}

/* ---------------------------------------------------------------- as cenas
   Cada uma: { montar: async () => grupo, giro, altura, lente } -- o giro é o
   ângulo da câmera em volta (0 = de frente, positivo = pela direita), a
   altura é o ângulo de cima para baixo e a lente o campo de visão. */
const CENAS = {
  // o Brinquedão Modelo 2 (o de selva: as casinhas, a torre e os escorregadores), em 3/4
  brinquedao: {
    montar: () => glb("brinquedao-modelo-2"),
    giro: 45, altura: 20, lente: 26,
  },
  // o Brinquedão Ninja visto pelo lado das camas elásticas: o andar dos obstáculos
  "area-ninja": {
    montar: () => glb("brinquedao-ninja"),
    giro: -55, altura: 22, lente: 26,
  },
  // a área baby, com as peças do projetista arrumadas à mão (a frente aberta, para ver
  // tudo): piso de EVA, cerca baixa, a piscina rasa com o escorregador, os blocos de
  // espuma, o túnel, a casinha e o painel ábaco
  "area-baby": {
    montar: async () => grupo(
      peca("piso_eva", [0, 0, 0], { largura: 5.0, profundidade: 3.8 }, "#f9a8d4", { cor2: "#86efac" }),
      peca("cerca", [0, 0, -1.8], { comprimento: 4.8, altura: 0.6 }, "#f472b6"),
      peca("cerca", [-2.4, 0, -0.05], { comprimento: 3.5, altura: 0.6 }, "#f472b6", {}, 90),
      peca("cerca", [2.4, 0, -0.05], { comprimento: 3.5, altura: 0.6 }, "#f472b6", {}, 90),
      peca("abaco", [2.25, 0.05, -0.7], { largura: 0.9, altura: 0.55 }, "#8b5cf6", {}, -90),
      peca("piscina", [-1.45, 0, -0.85], { largura: 1.6, profundidade: 1.6, altura: 0.4 }, "#38bdf8"),
      peca("plataforma", [0.3, 0.4, -1.05], { largura: 1.1, profundidade: 1.1, espessura: 0.08 }, "#facc15"),
      ...[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([dx, dz]) => peca("coluna", [0.3 + dx * 0.5, 0, -1.05 + dz * 0.5], { altura: 1.0, diametro: 0.06 }, "#a855f7")),
      peca("escorregador", [-0.7, 0, -1.05], { comprimento: 0.9, altura: 0.4, largura: 0.5 }, "#22c55e", {}, 180),
      peca("degraus_espuma", [1.25, 0, -1.05], { largura: 0.8, altura: 0.4, degraus: 2 }, "#f97316", {}, 180),
      peca("casinha", [1.65, 0, 0.55], { largura: 1.1, profundidade: 1.1, altura: 1.35 }, "#ec4899"),
      peca("blocos_espuma", [0.05, 0, 0.75], { largura: 1.7, profundidade: 1.1 }, "#facc15"),
      peca("tunel", [-1.55, 0, 0.75], { comprimento: 1.2, diametro: 0.6 }, "#a78bfa", {}, 90),
    ),
    giro: 18, altura: 30, lente: 26,
  },
  // o trampolim park do projetista (as camas em grade, a piscina de espuma) e o Trampolim de Enterrada
  trampolins: {
    montar: async () => grupo(
      area("trampolim", { largura: 14, profundidade: 9, altura: 5 }, "#2563eb", 2, { porte: "medio" }),
    ),
    giro: 30, altura: 34, lente: 26,
  },
  // o Espaço Esportivo Modelo 1, de cima em 3/4
  "espaco-esportivo-kids": {
    montar: () => glb("espaco-esportivo-modelo-1"),
    giro: 30, altura: 38, lente: 24,
  },
  // o espaço kids play: o brinquedão colorido do projetista, com o Air Game Kids e o Strike Kids na frente
  "espaco-kids-play": {
    montar: async () => grupo(
      area("brinquedao", { largura: 6.5, profundidade: 3.2, altura: 3.4 }, "#2563eb", 3, { estilo: "colorido" }),
      await glb("air-game-kids-alienigenas", { x: -1.3, z: 3.0, r: 20 }),
      await glb("strike-kids", { x: 1.8, z: 2.7, r: -18 }),
    ),
    giro: 22, altura: 22, lente: 26,
  },
  // o boliche: a máquina de boliche da fábrica (o Strike Kids), os pinos e as bolas (maiores
  // que os de verdade: na foto pequena, é o que diz "boliche")
  "boliche-virtual": {
    montar: async () => grupo(
      await glb("strike-kids", { r: -18 }),
      pinos(1.15, 0.55, 3, 0.17, -12, 1.9),
      colocar(P.bolaBoliche("#7c3aed", 0.19), { x: 0.42, z: 1.05 }),
      colocar(P.bolaBoliche("#2563eb", 0.17), { x: 1.55, z: 1.35 }),
    ),
    giro: 22, altura: 16, lente: 26,
  },
  // as eletrônicas: o basquete, o boliche, o hockey e o fliperama
  eletronicos: {
    montar: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -1.25, z: -0.5, r: 16 }),
      await glb("strike-kids", { x: 0.1, z: -0.45, r: 0 }),
      colocar(P.gabinete({ cor: "#1d4ed8", arte: "espaco" }), { x: 1.2, z: -0.3, r: -14 }),
      await glb("air-game-kids-alienigenas", { x: 0.0, z: 1.35, r: 10 }),
    ),
    giro: 14, altura: 16, lente: 26,
  },
  // os fliperamas: três gabinetes acesos e o pinball
  fliperama: {
    montar: async () => grupo(
      colocar(P.gabinete({ cor: "#1d4ed8", cores: ["#1d4ed8", "#facc15", "#ef4444", "#22d3ee"], arte: "espaco", letreiro: ["#7c3aed", "#ec4899"] }), { x: -1.0, z: 0, r: 14 }),
      colocar(P.gabinete({ cor: "#be123c", cores: ["#be123c", "#fde047", "#fb923c", "#f472b6"], arte: "blocos", letreiro: ["#f59e0b", "#ef4444"] }), { x: 0.0, z: -0.1, r: 0 }),
      colocar(P.gabinete({ cor: "#047857", cores: ["#047857", "#a3e635", "#22d3ee", "#facc15"], arte: "ritmo", letreiro: ["#06b6d4", "#22c55e"] }), { x: 1.0, z: 0, r: -14 }),
    ),
    giro: 12, altura: 12, lente: 24,
  },
  // os simuladores: dois de corrida e o de tiro
  simuladores: {
    montar: async () => grupo(
      colocar(P.simulador({ cor: "#dc2626", arte: "corrida", letreiro: ["#dc2626", "#f97316"] }), { x: -0.6, z: 0, r: 0 }),
      colocar(P.simulador({ cor: "#2563eb", arte: "corrida", letreiro: ["#2563eb", "#22d3ee"] }), { x: 0.6, z: 0, r: 0 }),
    ),
    giro: 48, altura: 20, lente: 26,
  },
  // os mecânicos: o carrossel e a mini roda, com as cores de sorvete
  mecanicos: {
    montar: async () => grupo(
      colocar(P.carrossel(), { x: -0.9, z: 0.3 }),
      colocar(P.rodaGigante(), { x: 1.55, z: -0.5, r: -20 }),
    ),
    giro: 14, altura: 16, lente: 26,
  },
  // os jogos de mesa: o hockey, o pebolim e a mesa de fliperama
  "jogos-de-mesa": {
    montar: async () => grupo(
      await glb("air-game-kids-alienigenas", { x: -1.0, z: 0.15, r: 22 }),
      colocar(P.mesaArcade({ cor: "#7c3aed", arte: "blocos" }), { x: 0.05, z: -0.85 }),
      colocar(P.pebolim(), { x: 1.05, z: 0.2, r: -10 }),
    ),
    giro: 20, altura: 30, lente: 26,
  },
  // os competitivos: dois basquetes lado a lado (um contra o outro) e o hockey
  competitivos: {
    montar: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -0.62, z: 0, r: 0 }),
      await glb("basquete-street-quadrinhos", { x: 0.62, z: 0, r: 0 }),
      await glb("air-game-kids-alienigenas", { x: 1.9, z: 2.2, r: -30 }),
    ),
    giro: 26, altura: 14, lente: 26,
  },
  // os famosos: as máquinas mais pedidas num palco, com as estrelas douradas
  famosos: {
    montar: async () => {
      const palco = new T.Group();
      P.cilindro(palco, 2.5, 0.16, P.mat("#312e81", { roughness: 0.75, metalness: 0 }), 0, 0, 0, 72);
      // a faixa dourada em volta do palco
      P.cilindro(palco, 2.53, 0.06, P.mat("#fbbf24", { metalness: 0.6, roughness: 0.35 }), 0, 0.05, 0, 72);
      return grupo(
        P.sombra(palco),
        await glb("basquete-street-quadrinhos", { x: -1.0, z: -0.45, y: 0.16, r: 12 }),
        colocar(P.gabinete({ cor: "#7c3aed", cores: ["#7c3aed", "#fbbf24", "#f472b6", "#22d3ee"], arte: "espaco", letreiro: ["#f59e0b", "#ec4899"] }), { x: 0.6, y: 0.16, z: -0.6, r: -8 }),
        await glb("air-game-kids-alienigenas", { x: 0.15, y: 0.16, z: 1.05, r: 10 }),
        colocar(P.estrela(0.42), { x: 1.75, y: 0.18 + 0.42, z: 0.75, r: -24 }),
        colocar(P.estrela(0.3), { x: -1.95, y: 0.18 + 0.3, z: 0.95, r: 24 }),
        colocar(P.estrela(0.36), { x: -0.15, y: 2.75, z: -1.0, r: 0 }),
      );
    },
    giro: 14, altura: 16, lente: 26,
  },
  // os esportivos: o basquete, o gol de LED e as bolas
  esportivos: {
    montar: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -1.25, z: -0.2, r: 22 }),
      colocar(P.golLed(), { x: 1.35, z: -0.5, r: -16 }),
      colocar(P.bolaFutebol(0.2), { x: 0.85, z: 0.85 }),
      colocar(P.bolaBasquete(0.21), { x: -0.2, z: 1.0 }),
    ),
    giro: 16, altura: 16, lente: 26,
  },
  // os kids: o Strike Kids, o Air Game Kids e dois fliperamas baixinhos
  kids: {
    montar: async () => grupo(
      await glb("strike-kids", { x: -1.3, z: -0.5, r: 16 }),
      colocar(P.gabinete({ cor: "#f472b6", cores: ["#f9a8d4", "#a7f3d0", "#fde68a", "#bfdbfe"], arte: "ritmo", letreiro: ["#fb7185", "#fde047"], kids: true, largura: 0.62 }), { x: 0.5, z: -0.55, r: -6 }),
      colocar(P.gabinete({ cor: "#14b8a6", cores: ["#5eead4", "#fde68a", "#f9a8d4", "#c4b5fd"], arte: "espaco", letreiro: ["#22d3ee", "#a78bfa"], kids: true, largura: 0.62 }), { x: 1.3, z: -0.3, r: -18 }),
      await glb("air-game-kids-alienigenas", { x: -0.25, z: 1.25, r: 10 }),
    ),
    giro: 12, altura: 18, lente: 26,
  },
};

/* ---------------------------------------------------------------- o enquadramento */
function cantos(caixa) {
  const { min, max } = caixa;
  const lista = [];
  for (const x of [min.x, max.x]) for (const y of [min.y, max.y]) for (const z of [min.z, max.z]) lista.push(new T.Vector3(x, y, z));
  return lista;
}

/** Põe a câmera no giro e na altura pedidos, com o objeto inteiro na tela (o corte fino é do compor.py). */
function enquadrar(caixa, giro, altura, lente) {
  camera.fov = lente;
  camera.updateProjectionMatrix();
  const dir = new T.Vector3(Math.sin(giro * GRAU) * Math.cos(altura * GRAU), Math.sin(altura * GRAU), Math.cos(giro * GRAU) * Math.cos(altura * GRAU));
  const alvo = caixa.getCenter(new T.Vector3());
  let dist = caixa.getBoundingSphere(new T.Sphere()).radius / Math.sin((lente / 2) * GRAU);
  const pontos = cantos(caixa);
  for (let i = 0; i < 8; i++) {
    camera.position.copy(alvo).addScaledVector(dir, dist);
    camera.lookAt(alvo);
    camera.updateMatrixWorld();
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const p of pontos) {
      const v = p.clone().project(camera);
      x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
    }
    // o meio do que aparece vai para o meio da tela, e o maior lado ocupa 86%
    const meia = Math.tan((lente / 2) * GRAU) * dist;
    const direita = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const cima = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    alvo.addScaledVector(direita, ((x0 + x1) / 2) * meia * camera.aspect).addScaledVector(cima, ((y0 + y1) / 2) * meia);
    dist *= Math.max((x1 - x0) / 2, (y1 - y0) / 2) / 0.86;
  }
  camera.position.copy(alvo).addScaledVector(dir, dist);
  camera.lookAt(alvo);
}

let atual = null;
window.CENAS = Object.keys(CENAS);

/** A foto da categoria `chave`: PNG com o fundo transparente (o objeto e a sombra). */
window.renderizar = async (chave, ajustes = {}) => {
  // "glb:<nome>" mostra um objeto 3D sozinho (para escolher o ângulo de uma cena nova)
  // "area:<tipo>:<cor>:<semente>:<largura>x<fundo>x<altura>:<porte>:<estilo>", uma área do projetista
  let c = CENAS[chave];
  if (chave.startsWith("glb:")) c = { montar: () => glb(chave.slice(4)), giro: 30, altura: 20, lente: 26 };
  if (chave.startsWith("area:")) {
    const [, tipo, cor, semente, medidas, porte, estilo] = chave.split(":");
    const [largura, profundidade, altura] = medidas.split("x").map(Number);
    c = { montar: () => area(tipo, { largura, profundidade, altura }, "#" + cor, Number(semente), { porte, estilo }), giro: 30, altura: 30, lente: 26 };
  }
  c = Object.assign({}, c, ajustes);
  if (!c.montar) throw new Error("cena desconhecida: " + chave);
  if (atual) cena.remove(atual);
  atual = await c.montar();
  cena.add(atual);
  atual.updateMatrixWorld(true);
  const caixa = new T.Box3().setFromObject(atual);
  const centro = caixa.getCenter(new T.Vector3());
  const tamanho = caixa.getSize(new T.Vector3());
  const maior = Math.max(tamanho.x, tamanho.z, tamanho.y);
  // o sol pela frente e pela direita, alto: a sombra cai para trás e para a esquerda
  sol.position.set(centro.x + maior * 0.55, centro.y + maior * 1.6 + 4, centro.z + maior * 0.9);
  sol.target.position.copy(centro);
  Object.assign(sol.shadow.camera, { left: -maior * 1.2, right: maior * 1.2, top: maior * 1.2, bottom: -maior * 1.2, near: 0.5, far: maior * 6 + 20 });
  sol.shadow.camera.updateProjectionMatrix();
  preenche.position.set(centro.x - maior, centro.y + maior * 0.5, centro.z + maior * 0.6);
  preenche.target.position.copy(centro);
  contra.position.set(centro.x - maior * 0.3, centro.y + maior, centro.z - maior * 1.2);
  contra.target.position.copy(centro);
  enquadrar(caixa, c.giro, c.altura, c.lente);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/png");
};
window.pronto = true;
