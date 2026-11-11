/* ======================================================================
   AS FOTOS DAS CATEGORIAS: em cada uma, as MÁQUINAS DE VERDADE daquela
   categoria do site, dentro de um lugar de verdade, com vida.

   O cliente pediu: "não quero nenhuma máquina fake, você tem os itens nas
   categorias, é só pegar e posicionar, além de caprichar mais no fundo,
   está muito sem vida". Então:
     * toda máquina é um item real da categoria (core/categorias_capas.py,
       e a lista de cada foto em CENAS): o .glb nosso, quando existe, ou a
       FOTO DO CATÁLOGO recortada do fundo (recortar.py, maquinas/), em pé
       no chão -- um plano virado para a câmera, na altura de verdade, com a
       luz da cena, a sombra e a sombra de contato embaixo. Nada inventado,
       nem no fundo: as máquinas do fundo são outros itens da categoria;
     * o lugar (lugares.js: o buffet, o shopping, a game zone, o galpão do
       parque, a brinquedoteca, a praça, o salão de festas, a quadra) tem
       vida: as crianças brincando (as mesmas da Arena 3D, pessoas.js), os
       balões, o confete e as bolinhas no ar, as luzes acesas, o sol nas
       janelas, o reflexo no piso e as coisas na frente, desfocadas.

   O gerar.cjs abre esta página num Chromium sem tela e chama
   `renderizar(chave)` para cada categoria. Saem três imagens: a foto, a
   máscara das máquinas (o que é máquina e está à vista) e o peso do
   desfoque (o que está longe delas, pela profundidade). O compor.py
   desfoca o lugar, deixa as máquinas nítidas e acende o brilho das luzes.
   ====================================================================== */

import * as T from "three";
import { GLTFLoader } from "../../core/static/vendor/three/GLTFLoader.js";
import * as utilidades from "../../core/static/vendor/three/BufferGeometryUtils.js";
import * as pecasDoPainel from "../../sistema_interno/static/interno/montar3d-pecas.js";
import * as gerador from "../../sistema_interno/static/interno/montar3d-gerador.js";
import { criarPecas } from "./pecas.js";
import { criarLugares } from "./lugares.js";
import { criarPessoas } from "./pessoas.js";

// o tamanho do render: 4:3 nas categorias (o card da home), quadrado nas capas dos produtos
// (o card de produto e a galeria): `formato` troca antes de cada foto
let LARGURA = 2400, ALTURA = 1800;
const GRAU = Math.PI / 180;

const renderer = new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(LARGURA, ALTURA);
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = T.SRGBColorSpace;
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = T.VSMShadowMap; // a sombra macia (com o raio abaixo)
document.body.append(renderer.domElement);

/* ---------------------------------------------------------------- a luz */
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
const hemi = new T.HemisphereLight("#ffffff", "#a3adbd", 1.25);
cena.add(hemi);
const sol = new T.DirectionalLight("#fff3e0", 2.4);
sol.castShadow = true;
sol.shadow.mapSize.set(4096, 4096);
sol.shadow.bias = -0.0004;
sol.shadow.radius = 10;
sol.shadow.blurSamples = 20;
cena.add(sol, sol.target);
const preenche = new T.DirectionalLight("#e8f0ff", 0.7);
cena.add(preenche, preenche.target);
const contra = new T.DirectionalLight("#ffffff", 0.9);
cena.add(contra, contra.target);
// as luzes coloridas do lugar (as da game zone), trocadas a cada cena
const coloridas = [new T.PointLight("#ffffff", 0, 0, 2), new T.PointLight("#ffffff", 0, 0, 2)];
coloridas.forEach((l) => cena.add(l));
const camera = new T.PerspectiveCamera(28, LARGURA / ALTURA, 0.05, 600);

/* ---------------------------------------------------------------- as peças */
const P = criarPecas(T);
const pessoas = criarPessoas(T);
const base = pecasDoPainel.desenhosBase(T, utilidades);
const DESENHOS = Object.assign(base.desenhos, pecasDoPainel.desenhosExtra(T, base.ferramentas));
const PADROES = Object.assign({}, pecasDoPainel.CATALOGO_BASE, pecasDoPainel.CATALOGO_EXTRA);
const leitor = new GLTFLoader();
const glbs = new Map();

/** O produto do catálogo de cada objeto 3D nosso (o nome da máquina na lista da foto). */
const GLB_DO_PRODUTO = {
  "brinquedao-modelo-2": "Brinquedão Modelo 2", "brinquedao-modelo-3": "Brinquedão Modelo 3", "brinquedao-modelo-4": "Brinquedão Modelo 4",
  "brinquedao-modelo-5": "Brinquedão Modelo 5",
  "brinquedao-ninja": "Brinquedão Ninja", "espaco-esportivo-modelo-1": "Espaço Esportivo Modelo 1", "strike-kids": "Strike Kids",
  "air-game-kids-alienigenas": "Air Game Kids Alienígenas", "basquete-street-quadrinhos": "Basquete Street Quadrinhos",
  "trampolim-enterrada": "Trampolim de Enterrada", "trampolim-enterrada-espuma": "Trampolim de Enterrada",
};

// os objetos 3D que uma cena usa (`cenasComGlb` anota aqui)
let anotarGlb = null;

/** O objeto 3D da fábrica (core/static/site/arena/modelos/<nome>.glb), no chão e no meio. */
async function glb(nome, { x = 0, y = 0, z = 0, r = 0, escala = 1 } = {}) {
  if (anotarGlb) anotarGlb.add(nome);
  const url = `../../core/static/site/arena/modelos/${nome}.glb`;
  if (!glbs.has(url)) glbs.set(url, leitor.loadAsync(url));
  const objeto = (await glbs.get(url)).scene.clone(true);
  objeto.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  const caixa = new T.Box3().setFromObject(objeto, true);
  objeto.position.set(-(caixa.min.x + caixa.max.x) / 2, -caixa.min.y, -(caixa.min.z + caixa.max.z) / 2);
  const g = colocar(objeto, { x, y, z, r, escala });
  if (GLB_DO_PRODUTO[nome]) g.userData.maquina = GLB_DO_PRODUTO[nome] + " (3D)";
  return g;
}

/* ---------------------------------------------------------------- as máquinas em foto
   A foto do catálogo, recortada (maquinas/<chave>.webp), num plano de pé:
   a base no chão, a altura do cadastro (maquinas.json), virado para a
   câmera (o giro da cena) e, se a foto é de 3/4, um tanto mais (`r`). A luz
   da cena acende a foto como acende o resto; a sombra sai pelo recorte, e
   embaixo vai a sombra de contato (uma mancha macia). */
const FICHA = await (await fetch("maquinas/maquinas.json")).json();
const fotos = new Map();
const leitorTextura = new T.TextureLoader();
async function carregarFotos(chaves) {
  await Promise.all(chaves.filter((c) => !fotos.has(c)).map(async (c) => {
    const t = await leitorTextura.loadAsync(`maquinas/${c}.webp`);
    t.colorSpace = T.SRGBColorSpace;
    t.anisotropy = 8;
    fotos.set(c, t);
  }));
}
const texturaContato = (() => {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const r = g.createRadialGradient(64, 64, 4, 64, 64, 64);
  r.addColorStop(0, "rgba(0,0,0,.62)");
  r.addColorStop(0.55, "rgba(0,0,0,.3)");
  r.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = r;
  g.fillRect(0, 0, 128, 128);
  return new T.CanvasTexture(c);
})();
const matContato = new T.MeshBasicMaterial({ map: texturaContato, transparent: true, depthWrite: false, toneMapped: false });
let giroDaCena = 0;

/** A máquina `chave` em foto (as fotos já carregadas: `carregarFotos`). */
function maquinaPronta(chave, { x = 0, y = 0, z = 0, r = 0, escala = 1, altura } = {}) {
  const t = fotos.get(chave);
  if (!t) throw new Error("foto não carregada: " + chave);
  if (!FICHA[chave]) throw new Error("máquina sem ficha: " + chave);
  const a = (altura || FICHA[chave].altura) * escala;
  const l = (a * t.image.width) / t.image.height;
  const mat = new T.MeshStandardMaterial({ map: t, alphaTest: 0.5, roughness: 0.8, metalness: 0, side: T.DoubleSide, envMapIntensity: 0.35 });
  const plano = new T.Mesh(new T.PlaneGeometry(l, a), mat);
  plano.position.y = a / 2;
  plano.castShadow = true;
  plano.customDepthMaterial = new T.MeshDepthMaterial({ depthPacking: T.RGBADepthPacking, map: t, alphaTest: 0.5 });
  plano.userData.recorte = t;
  const contato = new T.Mesh(new T.PlaneGeometry(l * 1.1, Math.max(0.45, l * 0.42)), matContato);
  contato.rotation.x = -Math.PI / 2;
  contato.position.set(0, 0.004, -l * 0.08);
  contato.userData.sombraContato = true;
  const g = new T.Group();
  g.add(plano, contato);
  g.position.set(x, y, z);
  g.rotation.y = (giroDaCena + r) * GRAU;
  g.userData.maquina = FICHA[chave].nome;
  return g;
}
async function maquina(chave, opcoes) {
  await carregarFotos([chave]);
  return maquinaPronta(chave, opcoes);
}

/* ---------------------------------------------------------------- as peças de reposição
   O card "Peças e acessórios" da home: as peças DO CATÁLOGO (a página
   /pecas-reposicao/), cada uma a foto dela recortada (recortar.py --pecas,
   reposicao/<chave>.webp), em pé no balcão ou na prateleira, na altura de
   verdade (reposicao/pecas.json) -- como as máquinas em foto. */
const PECAS = await (await fetch("reposicao/pecas.json")).json();
await Promise.all(Object.keys(PECAS).map(async (c) => {
  const t = await leitorTextura.loadAsync(`reposicao/${c}.webp`);
  t.colorSpace = T.SRGBColorSpace;
  t.anisotropy = 8;
  fotos.set("peca:" + c, t);
}));

/** A peça `chave` em foto: `deita` inclina para trás (a peça que está deitada no balcão). */
function pecaPronta(chave, { x = 0, y = 0, z = 0, r = 0, escala = 1, deita = 0, semContato: sem = false } = {}) {
  const t = fotos.get("peca:" + chave);
  if (!t || !PECAS[chave]) throw new Error("peça sem foto ou sem ficha: " + chave);
  const a = PECAS[chave].altura * escala;
  const l = (a * t.image.width) / t.image.height;
  const mat = new T.MeshStandardMaterial({ map: t, alphaTest: 0.5, roughness: 0.55, metalness: 0, side: T.DoubleSide, envMapIntensity: 0.5 });
  const plano = new T.Mesh(new T.PlaneGeometry(l, a), mat);
  plano.position.y = a / 2;
  plano.castShadow = true;
  plano.customDepthMaterial = new T.MeshDepthMaterial({ depthPacking: T.RGBADepthPacking, map: t, alphaTest: 0.5 });
  plano.userData.recorte = t;
  const pe = new T.Group();
  pe.add(plano);
  pe.rotation.x = -deita * GRAU;
  const g = new T.Group();
  g.add(pe);
  if (!sem) {
    const contato = new T.Mesh(new T.PlaneGeometry(l * 1.05, Math.max(0.02, l * 0.4)), matContato);
    contato.rotation.x = -Math.PI / 2;
    contato.position.set(0, 0.002, -a * Math.sin(deita * GRAU) * 0.4);
    contato.userData.sombraContato = true;
    g.add(contato);
  }
  g.position.set(x, y, z);
  g.rotation.y = (giroDaCena + r) * GRAU;
  g.userData.maquina = PECAS[chave].nome + " (peça)";
  return g;
}

/** Uma criança (pessoas.js) em (x, z), virada `r` graus a partir da câmera (0 = de frente para ela). */
function crianca(i, pose, { x = 0, y = 0, z = 0, r = 0, escala = 1 } = {}) {
  const k = pessoas.crianca(i, pose, escala);
  const g = new T.Group();
  g.add(k);
  g.position.set(x, y + k.position.y, z);
  k.position.y = 0;
  g.rotation.y = (giroDaCena + r) * GRAU;
  return g;
}

const LUGARES = criarLugares(T, P, { maquina: maquinaPronta, crianca, peca: pecaPronta });

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

/** Bolinhas no ar (as da piscina de bolinhas, os cubos de espuma): `n` em volta de (x, y, z). */
function noAr(n, x, y, z, raio, tipo = "bola", semente = 1) {
  let s = semente * 9301 + 49297;
  const r = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  const g = new T.Group();
  const cores = ["#ef4444", "#facc15", "#22c55e", "#3b82f6", "#ec4899", "#f97316", "#a855f7"];
  for (let i = 0; i < n; i++) {
    const m = P.mat(cores[i % cores.length], { roughness: 0.35 });
    const o = tipo === "cubo" ? new T.Mesh(new T.BoxGeometry(0.22, 0.22, 0.22), m) : new T.Mesh(new T.SphereGeometry(0.06, 14, 10), m);
    o.position.set(x + (r() - 0.5) * raio * 2, y + r() * raio, z + (r() - 0.5) * raio);
    o.rotation.set(r() * 3, r() * 3, 0);
    o.castShadow = true;
    g.add(o);
  }
  return g;
}

/* ---------------------------------------------------------------- as cenas
   Cada uma: `maquinas` (async: as máquinas reais, o destaque), `vida` (as
   crianças e o que está no ar: vão com o lugar, desfocam com ele), o
   `lugar` e o `lugarOp` (as máquinas do fundo em `fundo`: outros itens da
   mesma categoria), e a câmera: `giro` (0 = de frente, positivo = pela
   direita), `altura` (o ângulo de cima), `lente` e `ocupa` (o tamanho das
   máquinas na foto). `manter`: a foto que fica como está (a Área Baby, que
   não tem produto no catálogo). */
const CENAS = {
  // Brinquedão: o Brinquedão Modelo 2 e o Modelo 5 (3D) e, atrás, o Brinquedão Modelo 1 (foto), num buffet
  brinquedao: {
    maquinas: async () => grupo(
      await glb("brinquedao-modelo-2"),
      await glb("brinquedao-modelo-5", { x: 8.3, z: 1.9, r: -28 }),
    ),
    vida: () => grupo(
      crianca(0, "correndo", { x: 2.6, z: 1.9, r: 40 }),
      crianca(1, "comemorando", { x: -2.4, z: 1.7, r: 10 }),
      crianca(2, "pulando", { x: 0.6, z: 2.1, r: -15 }),
      crianca(3, "andando", { x: -5.2, z: 1.2, r: 70, escala: 0.9 }),
      noAr(26, 4.0, 1.3, 2.0, 0.9, "bola", 3),
    ),
    lugar: "buffet", lente: 40, giro: 40, altura: 14, ocupa: 0.8,
    lugarOp: { fundo: ["brinquedao-modelo-1"] },
  },
  // Área Ninja: o Brinquedão Ninja (3D), o único item da categoria, num galpão de parque
  "area-ninja": {
    maquinas: async () => glb("brinquedao-ninja"),
    vida: () => grupo(
      crianca(4, "correndo", { x: -3.5, z: 2.0, r: -40 }),
      crianca(5, "comemorando", { x: 1.0, z: 2.2, r: -20 }),
      crianca(6, "apontando", { x: 4.8, z: 2.1, r: -60 }),
      crianca(1, "pulando", { x: 6.0, y: 0.45, z: 0.0, r: -30 }),
      noAr(18, -1.5, 0.5, 0.2, 1.0, "cubo", 5),
    ),
    lugar: "galpao", lente: 40, giro: -55, altura: 18,
  },
  // Área Baby: sem produto no catálogo -- a foto fica como está (as peças da área baby)
  "area-baby": {
    manter: true,
    maquinas: async () => grupo(
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
    lugar: "brinquedoteca", lente: 40, giro: 18, altura: 24,
  },
  // Trampolins: o Trampolim de Enterrada (3D) e o Brinquedão Modelo 1 (foto), num galpão de parque
  trampolins: {
    maquinas: async () => grupo(
      await glb("trampolim-enterrada-espuma"),
      await maquina("brinquedao-modelo-1", { x: -6.4, z: -1.6, r: 18 }),
    ),
    vida: () => grupo(
      crianca(2, "pulando", { x: 1.6, y: 1.25, z: 0.0, r: -10 }),
      crianca(5, "pulando", { x: -1.4, y: 1.45, z: 0.1, r: 20 }),
      crianca(0, "comemorando", { x: 2.4, z: 2.0, r: -30 }),
      crianca(6, "correndo", { x: -3.2, z: 2.2, r: 50 }),
      noAr(14, 0.0, 1.3, 0.0, 0.9, "cubo", 7),
    ),
    lugar: "galpao", lente: 40, giro: 34, altura: 18,
  },
  // Espaço Esportivo Kids: o Espaço Esportivo Modelo 1 (3D), de cima, com a criançada
  "espaco-esportivo-kids": {
    maquinas: async () => glb("espaco-esportivo-modelo-1"),
    vida: () => grupo(
      ...[[-8, 8, "correndo"], [-4, 9.5, "comemorando"], [2, 9, "correndo"], [6, 10, "andando"], [10, 7, "pulando"], [-12, 6, "andando"],
        [4, 2, "pulando"], [8, 1, "pulando"], [-6, -2, "correndo"], [13, -3, "comemorando"], [0, 12, "apontando"]].map(([x, z, pose], i) =>
        crianca(i, pose, { x, z, r: (i * 47) % 360, y: pose === "pulando" ? 0.9 : 0, escala: 1.15 })),
    ),
    lugar: "galpao", lente: 40, giro: 30, altura: 30,
  },
  // Espaço Kids Play: o Brinquedão Modelo 3 (3D) com o Air Game Kids Alienígenas (3D) e o Sonic Kids (foto), no shopping
  "espaco-kids-play": {
    maquinas: async () => grupo(
      await glb("brinquedao-modelo-3", { r: 0 }),
      await glb("air-game-kids-alienigenas", { x: -2.6, z: 3.9, r: 22 }),
      await maquina("sonic-kids", { x: 2.2, z: 3.6, r: -6 }),
    ),
    vida: () => grupo(
      crianca(3, "jogando", { x: -2.95, z: 3.05, r: 22 }),
      crianca(4, "comemorando", { x: -0.9, z: 4.6, r: 20 }),
      crianca(0, "correndo", { x: 4.6, z: 3.2, r: -70 }),
      crianca(2, "andando", { x: 0.4, z: 4.6, r: 160, escala: 0.95 }),
    ),
    lugar: "shopping", lente: 40, giro: 22, altura: 16,
    lugarOp: { confete: false },
  },
  // Boliche Virtual: o Boliche Virtual (foto) e o Strike Kids (3D), com os pinos e as bolas, na game zone
  "boliche-virtual": {
    maquinas: async () => grupo(
      await maquina("boliche-virtual", { x: -0.7, z: 0, r: 8 }),
      await glb("strike-kids", { x: 1.45, z: -0.3, r: -18 }),
      pinos(0.95, 1.45, 3, 0.17, -12, 1.6),
      colocar(P.bolaBoliche("#7c3aed", 0.17), { x: 0.2, z: 1.6 }),
      colocar(P.bolaBoliche("#2563eb", 0.15), { x: 1.75, z: 1.8 }),
    ),
    vida: () => grupo(
      crianca(1, "comemorando", { x: 2.55, z: 0.2, r: -30 }),
      crianca(5, "apontando", { x: -2.5, z: 0.6, r: 40 }),
    ),
    lugar: "gamezone", lente: 40, giro: 22, altura: 12,
    lugarOp: { fundo: [] },
  },
  // Eletrônicos: o Basquete Street Quadrinhos, o Strike Kids e o Air Game Kids Alienígenas (3D) e o Mundo Zumbi (foto)
  // (o basquete mais à esquerda: o Air Game na frente não tapa o console dele)
  eletronicos: {
    maquinas: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -1.8, z: -0.6, r: 16 }),
      await glb("strike-kids", { x: 0.05, z: -0.45, r: 0 }),
      await maquina("mundo-zumbi", { x: 1.35, z: -0.3, r: -8 }),
      await glb("air-game-kids-alienigenas", { x: -0.05, z: 1.4, r: 10 }),
    ),
    vida: () => grupo(
      crianca(2, "jogando", { x: -0.05, z: 0.45, r: 10 }),
      crianca(6, "comemorando", { x: 2.15, z: 0.4, r: -25 }),
    ),
    lugar: "gamezone", lente: 40, giro: 14, altura: 12,
    lugarOp: { fundo: ["subway-surfers", "homem-aranha", "sonic-dash", "flappy-bird", "pinball-32", "tomb-raider-kids", "corrida-dos-minions", "nervo-teste"] },
  },
  // Fliperama: o Multi Jogos Retro, o Gabinete Games, o Pinball 40 Polegadas e o Subway Surfers (fotos)
  fliperama: {
    maquinas: async () => grupo(
      await maquina("multi-jogos-retro", { x: -1.65, z: 0, r: 10 }),
      await maquina("gabinete-games", { x: -0.45, z: -0.15, r: 0 }),
      await maquina("pinball-40", { x: 0.75, z: -0.05, r: -4 }),
      await maquina("subway-surfers", { x: 1.85, z: 0.05, r: -10 }),
    ),
    vida: () => grupo(
      crianca(3, "apontando", { x: 0.15, z: -0.75, r: 20 }),
      crianca(0, "comemorando", { x: 2.95, z: -1.0, r: -30 }),
    ),
    lugar: "gamezone", lente: 40, giro: 16, altura: 10, ocupa: 0.74,
    lugarOp: { fundo: ["tomb-raider-kids", "corrida-dos-minions", "sonic-dash", "flappy-bird", "homem-aranha", "pinball-32", "minions-kids", "sonic-kids"] },
  },
  // Simuladores: o Simulador Mario Kart, o Porsche Simulador e o Top Racer (fotos), no shopping
  simuladores: {
    maquinas: async () => grupo(
      await maquina("simulador-mario-kart", { x: -1.7, z: 0, r: 4 }),
      await maquina("top-racer", { x: 0.2, z: -0.9, r: 0 }),
      await maquina("porsche-simulador", { x: 1.95, z: 0.3, r: -6 }),
    ),
    vida: () => grupo(
      crianca(4, "apontando", { x: 1.0, z: -1.5, r: -20 }),
      crianca(1, "andando", { x: -3.4, z: -0.6, r: 70 }),
    ),
    lugar: "shopping", lente: 40, giro: 24, altura: 10, ocupa: 0.78,
    lugarOp: { atras: 2.4, fundo: ["speed-turbo", "lazer-shot", "sonic-racing"] },
  },
  // Mecânicos: o Carrossel Sorvetinho, a Mini Roda Sorvete e o Labamba (fotos), na praça
  mecanicos: {
    maquinas: async () => grupo(
      await maquina("carrossel-sorvetinho", { x: -3.0, z: 0.4, r: 6 }),
      await maquina("labamba", { x: -0.45, z: -0.5, r: 0 }),
      await maquina("mini-roda-sorvete", { x: 2.75, z: 0.3, r: -6 }),
    ),
    vida: () => grupo(
      crianca(0, "correndo", { x: -1.6, z: 1.6, r: 60 }),
      crianca(3, "comemorando", { x: 0.75, z: 1.3, r: -10 }),
      crianca(5, "andando", { x: -4.7, z: 1.2, r: 80, escala: 1.05 }),
      crianca(6, "apontando", { x: 4.7, z: -0.4, r: -50 }),
    ),
    lugar: "praca", lente: 40, giro: 14, altura: 10, ocupa: 0.8,
    lugarOp: { fundo: ["sonic-racing"] },
  },
  // Jogos de Mesa: o Air Game Kids Alienígenas (3D), o Pac Man, o Matrix e o Pebolim Eletrônico (fotos), no salão
  "jogos-de-mesa": {
    maquinas: async () => grupo(
      await glb("air-game-kids-alienigenas", { x: -1.5, z: 0.4, r: 24 }),
      await maquina("pac-man", { x: 0.0, z: -0.6, r: 0 }),
      await maquina("pebolim-eletronico", { x: 1.7, z: -0.2, r: -8 }),
      await maquina("matrix", { x: 0.35, z: 1.2, r: -4 }),
    ),
    vida: () => grupo(
      crianca(2, "jogando", { x: -1.9, z: -0.45, r: 24 }),
      crianca(6, "comemorando", { x: 2.95, z: -0.6, r: -30 }),
    ),
    lugar: "salao", lente: 40, giro: 18, altura: 18,
  },
  // Competitivos: o Basquete Street Quadrinhos (3D) e o Basquete Street (foto) lado a lado, e o Air Game Premium (foto)
  // à direita -- nenhum na frente do outro (o basquete de hoje, com a rampa, aparece inteiro)
  competitivos: {
    maquinas: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -1.3, z: 0, r: 0 }),
      await maquina("basquete-street", { x: 0.6, z: -0.9, r: -4 }),
      await maquina("air-game-premium", { x: 2.85, z: 1.0, r: -8 }),
    ),
    vida: () => grupo(
      crianca(0, "comemorando", { x: -2.6, z: 0.6, r: 30 }),
      crianca(3, "jogando", { x: 4.0, z: 1.4, r: -60 }),
    ),
    lugar: "gamezone", lente: 40, giro: 22, altura: 11,
    lugarOp: { fundo: ["nervo-teste", "mundo-zumbi", "pega-toupeira", "multi-jogos-retro", "pinball-40", "sonic-dash", "homem-aranha"] },
  },
  // Famosos: o Basquete Street Quadrinhos (3D), o Sonic Dash, o Homem Aranha e o Pac Man (fotos) no palco do shopping
  famosos: {
    maquinas: async () => {
      const palco = new T.Group();
      P.cilindro(palco, 2.6, 0.16, P.mat("#312e81", { roughness: 0.75, metalness: 0 }), 0, 0, 0, 72);
      P.cilindro(palco, 2.63, 0.06, P.mat("#fbbf24", { metalness: 0.6, roughness: 0.35 }), 0, 0.05, 0, 72);
      return grupo(
        P.sombra(palco),
        await glb("basquete-street-quadrinhos", { x: -1.35, z: -0.55, y: 0.16, r: 14 }),
        await maquina("sonic-dash", { x: 0.05, y: 0.16, z: -0.95, r: 0 }),
        await maquina("homem-aranha", { x: 1.05, y: 0.16, z: -0.75, r: -8 }),
        await maquina("pac-man", { x: 1.75, y: 0.16, z: 1.0, r: -10 }),
        colocar(P.estrela(0.42), { x: 2.05, y: 0.18 + 0.42, z: 0.9, r: -24 }),
        colocar(P.estrela(0.3), { x: -2.1, y: 0.18 + 0.3, z: 1.05, r: 24 }),
      );
    },
    vida: () => grupo(
      crianca(1, "comemorando", { x: -2.9, z: 1.4, r: 30 }),
      crianca(4, "apontando", { x: 3.2, z: 0.4, r: -40 }),
      crianca(6, "andando", { x: -4.4, z: -0.2, r: 80, escala: 0.95 }),
    ),
    lugar: "shopping", lente: 40, giro: 14, altura: 13,
    lugarOp: { confete: true, fundo: ["flappy-bird", "corrida-dos-minions"] },
  },
  // Esportivos: o Basquete Street Quadrinhos (3D), o Show de Bola e o Basquete Home (fotos), na quadra
  esportivos: {
    maquinas: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -1.35, z: -0.2, r: 20 }),
      await maquina("show-de-bola", { x: 0.35, z: -0.45, r: 0 }),
      await maquina("basquete-home", { x: 1.75, z: 0.1, r: -10 }),
      colocar(P.bolaFutebol(0.2), { x: 0.9, z: 1.25 }),
      colocar(P.bolaBasquete(0.21), { x: -0.4, z: 1.35 }),
    ),
    vida: () => grupo(
      crianca(0, "correndo", { x: 2.85, z: 0.3, r: -60 }),
      crianca(3, "comemorando", { x: -2.6, z: 0.8, r: 30 }),
      colocar(P.bolaBasquete(0.12), { x: -2.35, y: 1.9, z: 0.6 }),
    ),
    lugar: "quadra", lente: 40, giro: 16, altura: 12,
  },
  // Kids: o Sonic Kids, o Minions Kids, a Pantera Cor de Rosa Kids e o Homem Aranha Kids (fotos) e o Air Game Kids Alienígenas (3D), no buffet
  kids: {
    maquinas: async () => grupo(
      await maquina("sonic-kids", { x: -1.55, z: -0.35, r: 12 }),
      await maquina("minions-kids", { x: -0.55, z: -0.6, r: 5 }),
      await maquina("pantera-kids", { x: 0.45, z: -0.6, r: -3 }),
      await maquina("homem-aranha-kids", { x: 1.42, z: -0.35, r: -10 }),
      await glb("air-game-kids-alienigenas", { x: -0.15, z: 1.15, r: 8 }),
    ),
    vida: () => grupo(
      crianca(5, "jogando", { x: -0.15, z: 0.2, r: 0, escala: 0.92 }),
      crianca(1, "comemorando", { x: 2.4, z: 0.3, r: -30, escala: 0.92 }),
      crianca(3, "correndo", { x: -2.7, z: 1.3, r: 50, escala: 0.9 }),
      noAr(12, 0, 2.3, -0.2, 1.6, "bola", 9),
    ),
    lugar: "buffet", lente: 40, giro: 12, altura: 12,
    lugarOp: { parede: "#93c5fd", fundo: ["bob-esponja-kids"] },
  },
};

// O card fixo "Peças e acessórios" da home (não é categoria: core/templates/home.html o
// mostra direto, de core/static/site/categorias/pecas-e-acessorios.webp): as peças de
// verdade do catálogo no balcão da loja, com o estoque atrás, desfocado, e a luz quente.
CENAS["pecas-e-acessorios"] = {
  maquinas: async () => grupo(
    pecaPronta("cabo-hdmi", { x: -0.21, z: -0.1, r: 8 }),
    pecaPronta("mini-caixa-de-som-frente", { x: 0.2, z: -0.09, r: -8 }),
    pecaPronta("boneco-pebolim-vermelho", { x: -0.035, z: -0.01, r: 6 }),
    pecaPronta("boneco-pebolim-amarelo", { x: 0.035, z: 0.0, r: -4 }),
    pecaPronta("mini-caixa-de-som", { x: 0.15, z: 0.07, r: -6 }),
    pecaPronta("maneta-air-game", { x: -0.15, z: 0.07, r: 6 }),
    pecaPronta("disco-air-game", { x: -0.04, z: 0.13, r: 2, deita: 40 }),
  ),
  lugar: "loja", lente: 32, giro: 6, altura: 8, ocupa: 0.74, desce: 0.34, rampa: 0.22,
};

/* ---------------------------------------------------------------- as capas dos produtos
   A CAPA de cada produto nosso em 3D: a foto que vai no card de produto (a
   `imagem_brinquedo`) e a primeira da galeria. O cliente: "as fotos nas
   categorias devem ficar full ali, sem as bordas brancas". Então a capa é
   uma cena cheia, como as fotos das categorias: o produto SOZINHO no
   destaque, inteiro, grande e nítido, num lugar que combina com ele, com
   a criançada em volta (sem tapar o produto) e a luz do lugar. Companhia,
   só máquina de verdade do catálogo, ao fundo e desfocada (`lugarOp.fundo`).
   QUADRADA: o card de produto é quadrado (ls-tema.css, `.card-mini
   .img-area`), e a galeria da página do produto também, no computador.
   As mesmas chaves de `core/cadastro_modelos.py` (CADASTROS): o compor.py
   grava em core/static/site/arena/modelos/<chave>/capa.webp. */
/** As crianças da frente, pelo lugar na TELA ([x, y] de -1 a 1, depois do enquadramento): no chão livre da foto. */
function naFrente(lista) {
  return (naTela) => grupo(...lista.map(([x, y, i, pose, r = 0, escala = 1]) => {
    const p = naTela(x, y);
    return p ? crianca(i, pose, { x: p.x, z: p.z, r, escala }) : new T.Group();
  }));
}

const CAPAS = {
  // o Brinquedão Modelo 2 (o da selva) no buffet, com a parede verde
  "brinquedao-modelo-2": {
    maquinas: async () => glb("brinquedao-modelo-2"),
    vida: () => grupo(
      crianca(1, "comemorando", { x: -6.6, z: 1.0, r: 20 }),
      crianca(5, "andando", { x: 7.4, z: -0.4, r: 80, escala: 0.95 }),
      noAr(16, -3.6, 2.2, 0.2, 0.8, "bola", 4),
    ),
    naTela: naFrente([[-0.7, -0.93, 3, "correndo", 60], [0.5, -0.96, 6, "comemorando", -20]]),
    lugar: "buffet", lente: 46, giro: 46, altura: 14, desce: 0,
    lugarOp: { parede: "#86efac" },
  },
  // o Brinquedão Modelo 3 (a lojinha e o fliperama na frente) na game zone, com o neon e as máquinas kids ao fundo
  "brinquedao-modelo-3": {
    maquinas: async () => glb("brinquedao-modelo-3"),
    vida: () => grupo(
      crianca(2, "apontando", { x: 6.6, z: 0.4, r: -70, escala: 0.95 }),
    ),
    naTela: naFrente([[-0.62, -0.92, 0, "correndo", 60], [0.7, -0.9, 4, "comemorando", -30]]),
    lugar: "gamezone", lente: 40, giro: 30, altura: 12, desce: 0.04,
    lugarOp: { fundo: ["sonic-kids", "minions-kids"] },
  },
  // o Brinquedão Ninja no galpão do parque, visto pela ponta das camas elásticas, com a criançada em volta
  "brinquedao-ninja": {
    maquinas: async () => glb("brinquedao-ninja"),
    vida: () => grupo(
      crianca(1, "comemorando", { x: -8.6, z: -0.6, r: -20, escala: 0.95 }),
      noAr(14, 2.0, 0.6, 0.0, 0.9, "cubo", 5),
    ),
    naTela: naFrente([[-0.66, -0.92, 4, "correndo", -40], [0.62, -0.9, 6, "apontando", -60]]),
    lugar: "galpao", lente: 48, giro: -56, altura: 13, desce: 0,
  },
  // o Espaço Esportivo Modelo 1, de cima, com a criançada nas quadras e nas camas
  "espaco-esportivo-modelo-1": {
    maquinas: async () => glb("espaco-esportivo-modelo-1"),
    vida: () => grupo(
      ...[[-8, 8, "correndo"], [-4, 9.5, "comemorando"], [2, 9, "correndo"], [6, 10, "andando"], [10, 7, "pulando"], [-12, 6, "andando"],
        [4, 2, "pulando"], [8, 1, "pulando"], [-6, -2, "correndo"], [13, -3, "comemorando"], [0, 12, "apontando"]].map(([x, z, pose], i) =>
        crianca(i, pose, { x, z, r: (i * 47) % 360, y: pose === "pulando" ? 0.9 : 0, escala: 1.15 })),
    ),
    lugar: "galpao", lente: 40, giro: 28, altura: 42, ocupa: 0.86, desce: 0.02,
  },
  // o Trampolim de Enterrada na quadra: dois pulando nas camas e um torcendo do lado
  "trampolim-enterrada": {
    maquinas: async () => glb("trampolim-enterrada"),
    vida: () => grupo(
      crianca(2, "pulando", { x: 1.2, y: 0.8, z: 0.1, r: -10, escala: 0.9 }),
      crianca(5, "pulando", { x: -1.5, y: 0.7, z: 0.2, r: 20, escala: 0.9 }),
      colocar(P.bolaBasquete(0.12), { x: 2.3, y: 2.3, z: 0.0 }),
    ),
    naTela: naFrente([[-0.7, -0.9, 3, "correndo", 50], [0.68, -0.92, 0, "comemorando", -30]]),
    lugar: "quadra", lente: 44, giro: 30, altura: 12, desce: 0.02,
  },
  // o Strike Kids na game zone: os pinos e a bola no chão, outras máquinas do catálogo ao fundo
  "strike-kids": {
    maquinas: async () => glb("strike-kids"),
    vida: () => grupo(
      crianca(1, "comemorando", { x: 0.8, z: -0.65, r: -30 }),
      pinos(-0.95, 0.75, 3, 0.17, -12, 1.25),
      colocar(P.bolaBoliche("#7c3aed", 0.15), { x: 1.6, z: 1.1 }),
    ),
    lugar: "gamezone", lente: 40, giro: 28, altura: 9, ocupa: 0.8,
    lugarOp: { atras: 2.6, fundo: ["boliche-virtual", "sonic-kids", "minions-kids", "pac-man"] },
  },
  // o Air Game Kids Alienígenas no buffet: um jogando do outro lado da mesa, um torcendo; as máquinas kids ao fundo
  "air-game-kids-alienigenas": {
    maquinas: async () => glb("air-game-kids-alienigenas"),
    vida: () => grupo(
      crianca(2, "jogando", { x: 0.05, z: -1.2, r: -34, escala: 0.9 }),
      crianca(6, "comemorando", { x: 1.3, z: -0.5, r: -40, escala: 0.85 }),
    ),
    lugar: "buffet", lente: 40, giro: 34, altura: 20, ocupa: 0.78, desce: 0.14, frente: false,
    lugarOp: { atras: 3.0, lado: 3.4, mesaX: -3.4, mesaZ: -2.6, parede: "#93c5fd", fundo: ["sonic-kids", "minions-kids", "pantera-kids", "homem-aranha-kids"] },
  },
  // o Basquete Street Quadrinhos na game zone: um torcendo do lado, outras máquinas do catálogo ao fundo
  "basquete-street-quadrinhos": {
    maquinas: async () => glb("basquete-street-quadrinhos"),
    vida: () => grupo(
      crianca(0, "comemorando", { x: 1.6, z: 0.4, r: -30 }),
      crianca(3, "apontando", { x: -1.0, z: 1.15, r: 40 }),
    ),
    lugar: "gamezone", lente: 40, giro: 28, altura: 10, ocupa: 0.8,
    lugarOp: { atras: 2.6, fundo: ["basquete-street", "nervo-teste", "pinball-40", "sonic-dash"] },
  },
};

/* ---------------------------------------------------------------- o enquadramento */
function cantos(caixa) {
  const { min, max } = caixa;
  const lista = [];
  for (const x of [min.x, max.x]) for (const y of [min.y, max.y]) for (const z of [min.z, max.z]) lista.push(new T.Vector3(x, y, z));
  return lista;
}

/**
 * Põe a câmera no giro e na altura pedidos, com as máquinas inteiras na foto:
 * o maior lado delas ocupa `ocupa` da metade da tela, e o meio delas fica
 * `desce` abaixo do meio (sobra lugar em cima, onde o card põe a etiqueta).
 */
function enquadrar(caixa, giro, altura, lente, ocupa = 0.74, desce = 0.08) {
  camera.fov = lente;
  camera.updateProjectionMatrix();
  const dir = new T.Vector3(Math.sin(giro * GRAU) * Math.cos(altura * GRAU), Math.sin(altura * GRAU), Math.cos(giro * GRAU) * Math.cos(altura * GRAU));
  const alvo = caixa.getCenter(new T.Vector3());
  let dist = caixa.getBoundingSphere(new T.Sphere()).radius / Math.sin((lente / 2) * GRAU);
  const pontos = cantos(caixa);
  for (let i = 0; i < 10; i++) {
    camera.position.copy(alvo).addScaledVector(dir, dist);
    camera.lookAt(alvo);
    camera.updateMatrixWorld();
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const p of pontos) {
      const v = p.clone().project(camera);
      x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
    }
    const meia = Math.tan((lente / 2) * GRAU) * dist;
    const direita = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const cima = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    alvo.addScaledVector(direita, ((x0 + x1) / 2) * meia * camera.aspect).addScaledVector(cima, ((y0 + y1) / 2 + desce) * meia);
    dist *= Math.max((x1 - x0) / 2, (y1 - y0) / 2) / ocupa;
  }
  camera.position.copy(alvo).addScaledVector(dir, dist);
  camera.lookAt(alvo);
  camera.updateMatrixWorld();
  return { alvo, dir, dist };
}

/** Troca o material de cada malha (o `escolher` diz qual) e devolve o que desfaz a troca. */
function trocarMateriais(raiz, escolher) {
  const trocas = [];
  raiz.traverse((o) => {
    if (o.isMesh) {
      const novo = escolher(o);
      if (novo) {
        trocas.push([o, o.material]);
        o.material = novo;
      }
    }
  });
  return () => trocas.forEach(([o, m]) => { o.material = m; });
}

/** Esconde o que é transparente e não escreve profundidade (o vidro, o sol no chão, a sombra de contato). */
function esconderTransparentes(raiz) {
  const escondidas = [];
  raiz.traverse((o) => {
    if (o.isMesh && o.visible && o.material && o.material.transparent && !o.material.depthWrite) {
      o.visible = false;
      escondidas.push(o);
    }
  });
  return () => escondidas.forEach((o) => { o.visible = true; });
}

/** Esconde as sombras de contato (o render das máquinas sozinhas não as conta). */
function semContato(raiz) {
  const escondidas = [];
  raiz.traverse((o) => {
    if (o.userData.sombraContato && o.visible) {
      o.visible = false;
      escondidas.push(o);
    }
  });
  return () => escondidas.forEach((o) => { o.visible = true; });
}

/**
 * O acerto fino pelo que se VÊ das máquinas (a silhueta, num render pequeno
 * só com elas), e não pela caixa: a caixa de um brinquedão em L sobra nos
 * cantos, e ele ficava pequeno e alto na foto.
 */
const alvoSilhueta = new T.WebGLRenderTarget(480, 360);
function acertarPelaSilhueta(quadro, maquinas, lugar, ocupa, desce) {
  const SL = alvoSilhueta.width, SA = alvoSilhueta.height;
  const { alvo, dir } = quadro;
  for (let volta = 0; volta < 3; volta++) {
    if (lugar) lugar.visible = false;
    const devolver = semContato(maquinas);
    const fundo = cena.background;
    cena.background = null;
    renderer.setRenderTarget(alvoSilhueta);
    renderer.setClearColor(0x000000, 0);
    renderer.clear();
    renderer.render(cena, camera);
    const px = new Uint8Array(SL * SA * 4);
    renderer.readRenderTargetPixels(alvoSilhueta, 0, 0, SL, SA, px);
    renderer.setRenderTarget(null);
    cena.background = fundo;
    devolver();
    if (lugar) lugar.visible = true;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let y = 0; y < SA; y++) {
      for (let x = 0; x < SL; x++) {
        if (px[(y * SL + x) * 4 + 3] > 40) {
          const nx = ((x + 0.5) / SL) * 2 - 1, ny = ((y + 0.5) / SA) * 2 - 1; // de baixo para cima, como o NDC
          x0 = Math.min(x0, nx); x1 = Math.max(x1, nx); y0 = Math.min(y0, ny); y1 = Math.max(y1, ny);
        }
      }
    }
    if (x0 === Infinity) return;
    const meia = Math.tan((camera.fov / 2) * GRAU) * quadro.dist;
    const direita = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const cima = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    alvo.addScaledVector(direita, ((x0 + x1) / 2) * meia * camera.aspect).addScaledVector(cima, ((y0 + y1) / 2 + desce) * meia);
    quadro.dist *= Math.max((x1 - x0) / 2, (y1 - y0) / 2) / ocupa;
    camera.position.copy(alvo).addScaledVector(dir, quadro.dist);
    camera.lookAt(alvo);
    camera.updateMatrixWorld();
  }
}

/** O ponto do chão que aparece em (x, y) da tela (NDC), para pôr as coisas da frente. */
function chaoNaTela(x, y) {
  const raio = new T.Raycaster();
  raio.setFromCamera(new T.Vector2(x, y), camera);
  const p = new T.Vector3();
  return raio.ray.intersectPlane(new T.Plane(new T.Vector3(0, 1, 0), 0), p) ? p : null;
}

/* ---------------------------------------------------------------- as três imagens */
// a profundidade em metros, em dois canais (16 bits): R + G/255, de 0 a `maximo`; com o
// recorte das fotos (o transparente não conta) e as crianças na pose (o esqueleto)
const vertProfundidade = `
#include <common>
#include <skinning_pars_vertex>
varying float vZ;
varying vec2 vUv;
void main() {
  vUv = uv;
  #include <skinbase_vertex>
  #include <begin_vertex>
  #include <skinning_vertex>
  #include <project_vertex>
  vZ = -mvPosition.z;
}`;
const fragProfundidade = `
uniform float maximo;
uniform sampler2D mapa;
uniform float comMapa;
varying float vZ;
varying vec2 vUv;
void main() {
  if (comMapa > 0.5 && texture2D(mapa, vUv).a < 0.5) discard;
  float d = clamp(vZ / maximo, 0.0, 1.0) * 255.0;
  gl_FragColor = vec4(floor(d) / 255.0, fract(d), 0.0, 1.0);
}`;
const materiaisDeProfundidade = new Map();
function matProfundidade(mapa) {
  const chave = mapa ? mapa.uuid : "-";
  if (!materiaisDeProfundidade.has(chave)) {
    materiaisDeProfundidade.set(chave, new T.ShaderMaterial({
      uniforms: { maximo: { value: 100 }, mapa: { value: mapa || null }, comMapa: { value: mapa ? 1 : 0 } },
      vertexShader: vertProfundidade, fragmentShader: fragProfundidade, side: T.DoubleSide,
    }));
  }
  return materiaisDeProfundidade.get(chave);
}
// só a profundidade (o lugar esconde o que está atrás dele, na máscara)
const soProfundidade = new T.MeshBasicMaterial({ colorWrite: false, side: T.DoubleSide });
const soProfundidadeRecorte = new Map();
function matSoProfundidade(o) {
  const t = o.userData.recorte;
  if (!t) return soProfundidade;
  if (!soProfundidadeRecorte.has(t.uuid)) soProfundidadeRecorte.set(t.uuid, new T.MeshBasicMaterial({ colorWrite: false, map: t, alphaTest: 0.5, side: T.DoubleSide }));
  return soProfundidadeRecorte.get(t.uuid);
}
const alvoProfundidade = new T.WebGLRenderTarget(LARGURA, ALTURA);

/** O tamanho da foto: 4:3 (as categorias) ou quadrada (as capas dos produtos). */
function formato(largura, altura) {
  if (largura === LARGURA && altura === ALTURA) return;
  LARGURA = largura;
  ALTURA = altura;
  renderer.setSize(LARGURA, ALTURA);
  camera.aspect = LARGURA / ALTURA;
  camera.updateProjectionMatrix();
  alvoProfundidade.setSize(LARGURA, ALTURA);
  alvoSilhueta.setSize(480, Math.round((480 * ALTURA) / LARGURA));
}

/** O quanto cada ponto da foto é desfocado (0 = nítido): longe das máquinas, mais. */
function pesoDoDesfoque(caixa, maximo, rampaDaCena) {
  const fundo = cena.background;
  cena.background = null;
  const devolver = trocarMateriais(cena, (o) => {
    // o que não escreve profundidade (a sombra de contato, o vidro) não conta
    if (o.material && o.material.transparent && !o.material.depthWrite) return null;
    const m = matProfundidade(o.userData.recorte);
    m.uniforms.maximo.value = maximo;
    return m;
  });
  const mostrar = esconderTransparentes(cena);
  renderer.setRenderTarget(alvoProfundidade);
  renderer.setClearColor(0xffffff, 1);
  renderer.clear();
  renderer.render(cena, camera);
  const px = new Uint8Array(LARGURA * ALTURA * 4);
  renderer.readRenderTargetPixels(alvoProfundidade, 0, 0, LARGURA, ALTURA, px);
  renderer.setRenderTarget(null);
  renderer.setClearColor(0x000000, 0);
  mostrar();
  devolver();
  cena.background = fundo;
  // a faixa de foco: do ponto mais perto ao mais longe das máquinas
  let perto = Infinity, longe = 0;
  for (const p of cantos(caixa)) {
    const z = -p.clone().applyMatrix4(camera.matrixWorldInverse).z;
    perto = Math.min(perto, z);
    longe = Math.max(longe, z);
  }
  // (`rampa` da cena: a cena de perto, a das peças, desfoca o fundo mais depressa)
  const rampa = rampaDaCena ?? Math.max(4, (longe + perto) * 0.55);
  const tela = document.createElement("canvas");
  tela.width = LARGURA;
  tela.height = ALTURA;
  const ctx = tela.getContext("2d");
  const img = ctx.createImageData(LARGURA, ALTURA);
  for (let y = 0; y < ALTURA; y++) {
    const origem = (ALTURA - 1 - y) * LARGURA * 4; // o alvo vem de baixo para cima
    for (let x = 0; x < LARGURA; x++) {
      const i = origem + x * 4;
      const d = ((px[i] + px[i + 1] / 255) / 255) * maximo;
      let w = 0;
      if (d > longe + 0.4) w = Math.min(1, (d - longe - 0.4) / rampa);
      else if (d < perto - 0.6) w = Math.min(1, (perto - 0.6 - d) / (rampa * 0.45));
      const v = Math.round(w * 255);
      const o = (y * LARGURA + x) * 4;
      img.data[o] = img.data[o + 1] = img.data[o + 2] = v;
      img.data[o + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return tela.toDataURL("image/png");
}

/** A máscara das máquinas: só elas, com o lugar escondendo o que fica atrás dele. */
function mascara(maquinas, lugar) {
  const fundo = cena.background;
  cena.background = null;
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.autoClear = false;
  maquinas.visible = false;
  const mostrar = esconderTransparentes(lugar);
  let devolver = trocarMateriais(lugar, matSoProfundidade);
  renderer.render(cena, camera);
  devolver();
  mostrar();
  maquinas.visible = true;
  lugar.visible = false;
  devolver = semContato(maquinas);
  renderer.render(cena, camera);
  devolver();
  lugar.visible = true;
  renderer.autoClear = true;
  cena.background = fundo;
  return renderer.domElement.toDataURL("image/png");
}

let atual = null, atualLugar = null;
window.CENAS = Object.keys(CENAS).filter((chave) => !CENAS[chave].manter);
window.TODAS = Object.keys(CENAS);
window.CAPAS = Object.keys(CAPAS).map((chave) => "capa:" + chave);
window.MAQUINAS_DAS_CENAS = {};

/**
 * A foto da categoria `chave`: { cor, mascara, peso } (PNGs em data URL).
 * Sem lugar ("glb:<nome>", "area:..."), sai como antes: fundo transparente.
 */
window.renderizar = async (chave, ajustes = {}) => {
  // "glb:<nome>" mostra um objeto 3D sozinho (para escolher o ângulo de uma cena nova)
  // "area:<tipo>:<cor>:<semente>:<largura>x<fundo>x<altura>:<porte>:<estilo>", uma área do projetista
  let c = CENAS[chave];
  if (chave.startsWith("glb:")) c = { maquinas: () => glb(chave.slice(4)), giro: 30, altura: 20, lente: 26 };
  if (chave.startsWith("area:")) {
    const [, tipo, cor, semente, medidas, porte, estilo] = chave.split(":");
    const [largura, profundidade, altura] = medidas.split("x").map(Number);
    c = { maquinas: () => area(tipo, { largura, profundidade, altura }, "#" + cor, Number(semente), { porte, estilo }), giro: 30, altura: 30, lente: 26 };
  }
  // "capa:<chave>", a capa do produto (quadrada, o produto grande)
  if (chave.startsWith("capa:")) c = CAPAS[chave.slice(5)] && Object.assign({ quadrado: true, ocupa: 0.84, desce: 0.06 }, CAPAS[chave.slice(5)]);
  c = Object.assign({}, c, ajustes);
  if (!c.maquinas) throw new Error("cena desconhecida: " + chave);
  // `previa`: a metade do tamanho (para acertar o ângulo depressa)
  const [largura, altura] = c.quadrado ? [2000, 2000] : [2400, 1800];
  formato(c.previa ? largura / 2 : largura, c.previa ? altura / 2 : altura);
  if (atual) cena.remove(atual);
  if (atualLugar) cena.remove(atualLugar);
  giroDaCena = c.giro;
  const op = c.lugarOp || {};
  await carregarFotos(op.fundo || []);
  atual = await c.maquinas();
  cena.add(atual);
  atual.updateMatrixWorld(true);
  // a lista das máquinas da foto (o resumo e os testes conferem que todas são do catálogo)
  const nomes = [];
  atual.traverse((o) => { if (o.userData.maquina) nomes.push(o.userData.maquina); });
  // a caixa justa (pelos vértices), sem as sombras de contato
  const devolverContato = semContato(atual);
  const caixa = new T.Box3().setFromObject(atual, true);
  devolverContato();
  const centro = caixa.getCenter(new T.Vector3());
  const tamanho = caixa.getSize(new T.Vector3());
  const maior = Math.max(tamanho.x, tamanho.z, tamanho.y);
  // o lugar em volta (e a luz dele) e a vida (as crianças, o que está no ar)
  const lugar = c.lugar ? LUGARES[c.lugar](caixa, c.giro, op) : null;
  const l = (lugar && lugar.luz) || {};
  atualLugar = lugar ? lugar.grupo : null;
  if (atualLugar) {
    if (c.vida) atualLugar.add(c.vida());
    cena.add(atualLugar);
    atualLugar.traverse((o) => { if (o.userData.maquina) nomes.push(o.userData.maquina + " (ao fundo)"); });
  }
  window.MAQUINAS_DAS_CENAS[chave] = nomes;
  cena.background = lugar ? new T.Color(lugar.fundo) : null;
  cena.fog = lugar && lugar.neblina ? new T.Fog(lugar.neblina[0], lugar.neblina[1], lugar.neblina[2]) : null;
  hemi.color.set(l.ceu || "#ffffff");
  hemi.groundColor.set(l.chao || "#a3adbd");
  hemi.intensity = l.hemi ?? 1.25;
  sol.intensity = l.sol ?? 2.4;
  cena.environmentIntensity = l.amb ?? 0.55;
  renderer.toneMappingExposure = l.exposicao ?? 1.0;
  coloridas.forEach((luzColorida, i) => {
    const [cor, lado] = (l.cores || [])[i] || ["#ffffff", 0];
    luzColorida.color.set(cor);
    luzColorida.intensity = lado ? 18 * Math.max(1, maior / 3) : 0;
    luzColorida.position.set(centro.x + lado * (tamanho.x / 2 + 1.2), 2.4, centro.z + tamanho.z * 0.2);
  });
  // o sol pela frente e pela direita, alto: a sombra cai para trás e para a esquerda
  sol.position.set(centro.x + maior * 0.55, centro.y + maior * 1.6 + 4, centro.z + maior * 0.9);
  sol.target.position.copy(centro);
  Object.assign(sol.shadow.camera, { left: -maior * 1.4, right: maior * 1.4, top: maior * 1.4, bottom: -maior * 1.4, near: 0.5, far: maior * 6 + 24 });
  sol.shadow.camera.updateProjectionMatrix();
  preenche.position.set(centro.x - maior, centro.y + maior * 0.5, centro.z + maior * 0.6);
  preenche.target.position.copy(centro);
  contra.position.set(centro.x - maior * 0.3, centro.y + maior, centro.z - maior * 1.2);
  contra.target.position.copy(centro);
  const ocupa = c.ocupa ?? (lugar ? 0.76 : 0.86), desce = c.desce ?? (lugar ? 0.1 : 0);
  const quadro = enquadrar(caixa, c.giro, c.altura, c.lente, ocupa, desce);
  if (lugar) acertarPelaSilhueta(quadro, atual, atualLugar, ocupa, desce);
  // o que fica na frente, desfocado (nos cantos de baixo), e o reflexo das máquinas no piso
  if (lugar && lugar.frente && c.frente !== false) atualLugar.add(lugar.frente(chaoNaTela, camera));
  // as crianças da frente (as capas): no chão livre da foto, já enquadrada
  if (lugar && c.naTela) atualLugar.add(c.naTela(chaoNaTela));
  if (lugar && lugar.reflexo) {
    const espelho = atual.clone(true);
    espelho.traverse((o) => {
      o.castShadow = false;
      if (o.userData.sombraContato) o.visible = false;
    });
    espelho.scale.y = -1;
    atualLugar.add(espelho);
  }
  renderer.render(cena, camera);
  const cor = renderer.domElement.toDataURL("image/png");
  if (!lugar) return { cor };
  const peso = pesoDoDesfoque(caixa, camera.position.distanceTo(centro) * 6 + 40, c.rampa);
  window.ultimaCaixa = [caixa.min.toArray(), caixa.max.toArray()].map((v) => v.map((n) => +n.toFixed(2)));
  return { cor, mascara: mascara(atual, atualLugar), peso };
};
/**
 * As cenas (as fotos das categorias e as capas dos produtos) que usam algum dos
 * objetos 3D `nomes`: quando um .glb é refeito, o gerar.cjs (--glb <nome>) refaz
 * só elas. Monta as máquinas de cada cena (sem renderizar) e vê quais .glb entraram.
 */
window.cenasComGlb = async (...nomes) => {
  const todas = [...window.CENAS.map((k) => [k, CENAS[k]]), ...Object.keys(CAPAS).map((k) => ["capa:" + k, CAPAS[k]])];
  const lista = [];
  try {
    for (const [chave, c] of todas) {
      anotarGlb = new Set();
      await c.maquinas();
      if (nomes.some((nome) => anotarGlb.has(nome))) lista.push(chave);
    }
  } finally {
    anotarGlb = null;
  }
  return lista;
};

/** As medidas de um objeto 3D nosso (largura, altura, fundo), para montar uma cena nova. */
window.medir = async (nome) => {
  const caixa = new T.Box3().setFromObject(await glb(nome), true);
  return caixa.getSize(new T.Vector3()).toArray().map((n) => +n.toFixed(2));
};
window.pronto = true;
