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
// o acabamento de render (three r169, ferramentas/categorias/vendor/): a luz de ambiente
// PBR da sala (RoomEnvironment) e a oclusão de ambiente (GTAO) no pós-processamento
import { RoomEnvironment } from "./vendor/environments/RoomEnvironment.js";
import { EffectComposer } from "./vendor/postprocessing/EffectComposer.js";
import { RenderPass } from "./vendor/postprocessing/RenderPass.js";
import { GTAOPass } from "./vendor/postprocessing/GTAOPass.js";
import { OutputPass } from "./vendor/postprocessing/OutputPass.js";

// o tamanho do render: 4:3 nas categorias (o card da home), quadrado nas capas dos produtos
// (o card de produto e a galeria): `formato` troca antes de cada foto. O render é o DOBRO da
// foto final (supersampling): 3200 x 2400 para 1600 x 1200, 3200 x 3200 para 1600 x 1600;
// o compor.py reduz com o filtro Lanczos (sem serrilhado nas bordas e nas texturas)
let LARGURA = 3200, ALTURA = 2400;
const GRAU = Math.PI / 180;

const renderer = new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(LARGURA, ALTURA);
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = T.SRGBColorSpace;
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = T.PCFSoftShadowMap; // a sombra macia, com o mapa grande (abaixo)
document.body.append(renderer.domElement);

/* ---------------------------------------------------------------- a luz */
const cena = new T.Scene();
// a luz de ambiente PBR: a sala de estúdio do three (RoomEnvironment), pré-filtrada (PMREM):
// dá o reflexo suave no que é liso e a luz difusa que vem de todo lado
{
  const pmrem = new T.PMREMGenerator(renderer);
  cena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  cena.environmentIntensity = 0.55;
}
const hemi = new T.HemisphereLight("#ffffff", "#a3adbd", 1.25);
cena.add(hemi);
const sol = new T.DirectionalLight("#fff3e0", 2.4);
sol.castShadow = true;
sol.shadow.mapSize.set(8192, 8192);
sol.shadow.bias = -0.00025;
sol.shadow.normalBias = 0.015;
cena.add(sol, sol.target);
const preenche = new T.DirectionalLight("#e8f0ff", 0.7);
cena.add(preenche, preenche.target);
const contra = new T.DirectionalLight("#ffffff", 0.9);
cena.add(contra, contra.target);
// as luzes coloridas do lugar (as da game zone), trocadas a cada cena
const coloridas = [new T.PointLight("#ffffff", 0, 0, 2), new T.PointLight("#ffffff", 0, 0, 2)];
// A LUZ DE ESTÚDIO das fotos de produto (as capas, as capas do catálogo, as vistas da galeria):
// como numa foto comercial -- a principal macia de 3/4 pela frente, o preenchimento do outro
// lado, o recorte por trás (separa a máquina do fundo); o produto é a parte mais clara da foto
// e o lugar fica mais escuro (os spots caem com a distância)
const principal = new T.SpotLight("#fff6ea", 0, 0, 0.5, 0.7, 2);
principal.castShadow = true;
principal.shadow.mapSize.set(4096, 4096);
principal.shadow.bias = -0.0002;
principal.shadow.normalBias = 0.02;
const preenchimento = new T.SpotLight("#eef3ff", 0, 0, 0.7, 0.9, 2);
const recorte = new T.SpotLight("#ffffff", 0, 0, 0.6, 0.8, 2);
for (const luzEstudio of [principal, preenchimento, recorte]) cena.add(luzEstudio, luzEstudio.target);
coloridas.forEach((l) => cena.add(l));
const camera = new T.PerspectiveCamera(28, LARGURA / ALTURA, 0.05, 600);

// o pós-processamento: a cena (num alvo de cor em ponto flutuante), a oclusão de ambiente
// (GTAO: o escuro macio nos cantos, embaixo das máquinas e onde uma peça encosta na outra)
// e a saída com o tone mapping ACES. O GTAO não vê o que é recorte de foto nem o que é
// transparente (a sombra de contato, o vidro, o sol no chão): eles têm sombra própria.
const composer = new EffectComposer(renderer);
composer.setPixelRatio(1);
composer.setSize(LARGURA, ALTURA);
composer.addPass(new RenderPass(cena, camera));
const gtao = new GTAOPass(cena, camera, LARGURA, ALTURA);
gtao.overrideVisibility = function () {
  this.scene.traverse((o) => {
    this._visibilityCache.set(o, o.visible);
    if (o.isPoints || o.isLine) o.visible = false;
    else if (o.isMesh && (o.userData.recorte || (o.material && o.material.transparent && !o.material.depthWrite))) o.visible = false;
  });
};
composer.addPass(gtao);
composer.addPass(new OutputPass());

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
  "air-game-kids-alienigenas": "Air Game Kids Alienígenas", "basquete-street-quadrinhos": "Basquete Home Quadrinhos",
  "air-game-kids-astronautas": "Air Game Kids (Astronautas)",
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

// a placa do logo do showroom (ferramentas/categorias/placa.py, do logo oficial do repositório)
const placaDoLogo = await leitorTextura.loadAsync("showroom/placa-lazer-sport.png");
placaDoLogo.colorSpace = T.SRGBColorSpace;
placaDoLogo.anisotropy = 16;
const LUGARES = criarLugares(T, P, { maquina: maquinaPronta, crianca, peca: pecaPronta, placa: placaDoLogo });

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
  // Brinquedão: o Brinquedão Modelo 2 e, ao lado (sem encostar), o Modelo 5 (3D); ao fundo, o Modelo 1 (foto), no buffet
  brinquedao: {
    maquinas: async () => grupo(
      await glb("brinquedao-modelo-2"),
      await glb("brinquedao-modelo-5", { x: 8.9, z: 0.2, r: -18 }),
    ),
    vida: () => grupo(
      crianca(6, "olhando", { x: -7.4, z: 0.9, r: 55 }),
    ),
    naTela: naFrente([[-0.7, -0.86, 0, "correndo", 50], [0.42, -0.9, 4, "comemorando", -15], [0.78, -0.82, 1, "apontando", -40]]),
    lugar: "buffet", lente: 40, giro: 30, altura: 12, ocupa: 0.8,
    lugarOp: { fundo: [] },
  },
  // Área Ninja: o Brinquedão Ninja (3D), o único item da categoria, num galpão de parque
  "area-ninja": {
    maquinas: async () => glb("brinquedao-ninja"),
    vida: () => grupo(
      crianca(5, "olhando", { x: 8.5, z: 1.2, r: -50 }),
    ),
    naTela: naFrente([[-0.62, -0.86, 4, "correndo", -40], [0.66, -0.88, 2, "comemorando", -30]]),
    lugar: "galpao", lente: 40, giro: -45, altura: 14,
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
  // Trampolins: o Trampolim de Enterrada (3D) e, afastado, o Brinquedão Modelo 1 (foto), num galpão de parque
  trampolins: {
    maquinas: async () => grupo(
      await glb("trampolim-enterrada-espuma"),
      await maquina("brinquedao-modelo-1", { x: -8.6, z: -1.4, r: 10 }),
    ),
    vida: () => grupo(
      crianca(2, "pulando", { x: 1.6, y: 0.75, z: 0.0, r: -10, escala: 0.9 }),
      crianca(5, "pulando", { x: -1.4, y: 0.65, z: 0.1, r: 20, escala: 0.9 }),
    ),
    naTela: naFrente([[0.64, -0.86, 0, "comemorando", -30], [-0.2, -0.9, 6, "correndo", 50]]),
    lugar: "galpao", lente: 40, giro: 30, altura: 14,
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
  // Espaço Kids Play: o Brinquedão Modelo 3 (3D) e, do lado (sem tapar a frente dele), o Air Game Kids
  // Alienígenas (3D) e o Sonic Kids (foto), na game zone (o shopping saía claro demais: "brancão")
  "espaco-kids-play": {
    maquinas: async () => grupo(
      await glb("brinquedao-modelo-3", { r: 0 }),
      await glb("air-game-kids-alienigenas", { x: 6.7, z: 1.4, r: -20 }),
      await maquina("sonic-kids", { x: 7.9, z: -0.3, r: -10 }),
    ),
    vida: () => grupo(
      crianca(3, "jogando", { x: 6.95, z: 0.55, r: -20 }),
    ),
    naTela: naFrente([[-0.7, -0.86, 4, "comemorando", 20], [0.1, -0.9, 0, "correndo", -70], [0.66, -0.88, 2, "andando", 160]]),
    lugar: "gamezone", lente: 40, giro: 22, altura: 12,
  },
  // Boliche Virtual: o Boliche Virtual (foto) e o Strike Kids (3D), lado a lado, com os pinos e as bolas, na game zone
  "boliche-virtual": {
    maquinas: async () => grupo(
      await maquina("boliche-virtual", { x: -1.0, z: 0, r: 4 }),
      await glb("strike-kids", { x: 1.2, z: -0.3, r: -12 }),
      pinos(0.15, 1.5, 3, 0.17, -8, 1.6),
      colocar(P.bolaBoliche("#7c3aed", 0.17), { x: -0.55, z: 1.65 }),
      colocar(P.bolaBoliche("#2563eb", 0.15), { x: 0.9, z: 1.75 }),
    ),
    naTela: naFrente([[-0.85, -0.8, 1, "apontando", 40], [0.86, -0.82, 5, "comemorando", -30]]),
    lugar: "gamezone", lente: 40, giro: 14, altura: 10, ocupa: 0.66,
    lugarOp: { fundo: [] },
  },
  // Eletrônicos: o Basquete Home Quadrinhos, o Strike Kids e o Air Game Kids Alienígenas (3D) e o Mundo Zumbi (foto),
  // em fila e com espaço entre eles (o Air Game à direita, na frente de nenhum)
  eletronicos: {
    maquinas: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -2.1, z: -0.5, r: 12 }),
      await glb("strike-kids", { x: -0.25, z: -0.5, r: 0 }),
      await maquina("mundo-zumbi", { x: 1.25, z: -0.4, r: -6 }),
      await glb("air-game-kids-alienigenas", { x: 3.0, z: 0.6, r: -14 }),
    ),
    vida: () => grupo(
      crianca(2, "jogando", { x: 3.05, z: -0.4, r: -14 }),
    ),
    naTela: naFrente([[-0.86, -0.82, 6, "comemorando", 30]]),
    lugar: "showroom", lente: 40, giro: 12, altura: 10, ocupa: 0.72,
    lugarOp: { fundo: [], cenario: "fliperama", deslocar: -1.5 },
  },
  // Fliperama: o Multi Jogos Retro, o Gabinete Games, o Pinball 40 Polegadas e o Subway Surfers (fotos), em fila, de frente
  fliperama: {
    maquinas: async () => grupo(
      await maquina("multi-jogos-retro", { x: -2.3, z: 0, r: 0 }),
      await maquina("gabinete-games", { x: -0.75, z: -0.1, r: 0 }),
      await maquina("pinball-40", { x: 0.85, z: 0, r: 0 }),
      await maquina("subway-surfers", { x: 2.3, z: -0.05, r: 0 }),
    ),
    naTela: naFrente([[-0.86, -0.8, 3, "apontando", 30], [0.86, -0.82, 0, "comemorando", -30]]),
    lugar: "showroom", lente: 40, giro: 6, altura: 8, ocupa: 0.66,
    lugarOp: { fundo: [], cenario: "logo" },
  },
  // Simuladores: o Simulador Mario Kart, o Top Racer e o Porsche Simulador (fotos), em fila, de frente, no shopping
  simuladores: {
    maquinas: async () => grupo(
      await maquina("simulador-mario-kart", { x: -2.4, z: 0, r: 0 }),
      await maquina("top-racer", { x: -0.2, z: -0.2, r: 0 }),
      await maquina("porsche-simulador", { x: 1.8, z: 0.1, r: 0 }),
    ),
    naTela: naFrente([[-0.8, -0.84, 4, "olhando", 30], [0.82, -0.86, 1, "apontando", -40]]),
    lugar: "shopping", lente: 40, giro: 6, altura: 8, ocupa: 0.76,
    lugarOp: { atras: 2.4, fundo: [] },
  },
  // Mecânicos: o Carrossel Sorvetinho, o Labamba e a Mini Roda Sorvete (fotos), em fila, de frente, na praça
  mecanicos: {
    maquinas: async () => grupo(
      await maquina("carrossel-sorvetinho", { x: -3.2, z: 0.2, r: 0 }),
      await maquina("labamba", { x: -0.4, z: -0.3, r: 0 }),
      await maquina("mini-roda-sorvete", { x: 2.9, z: 0.1, r: 0 }),
    ),
    naTela: naFrente([[-0.78, -0.84, 0, "correndo", 60], [0.0, -0.9, 3, "comemorando", -10], [0.8, -0.84, 5, "andando", 80]]),
    lugar: "praca", lente: 40, giro: 6, altura: 9, ocupa: 0.8,
    lugarOp: { fundo: [] },
  },
  // Jogos de Mesa: o Air Game Kids Alienígenas (3D), o Pac Man, o Pebolim Eletrônico e o Matrix (fotos), em fila, no salão
  "jogos-de-mesa": {
    maquinas: async () => grupo(
      await glb("air-game-kids-alienigenas", { x: -2.6, z: 0.2, r: 16 }),
      await maquina("pac-man", { x: -0.9, z: -0.2, r: 0 }),
      await maquina("matrix", { x: 0.55, z: -0.2, r: 0 }),
      await maquina("pebolim-eletronico", { x: 2.4, z: -0.1, r: 0 }),
    ),
    vida: () => grupo(
      crianca(2, "jogando", { x: -2.6, z: -0.8, r: -26 }),
    ),
    naTela: naFrente([[0.82, -0.84, 6, "comemorando", -30]]),
    lugar: "salao", lente: 40, giro: 10, altura: 12,
  },
  // Competitivos: o Basquete Home Quadrinhos (3D) e o Basquete Street (foto) lado a lado, e o Air Game Premium (foto)
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
    lugarOp: { fundo: [] },
  },
  // Famosos: o Basquete Home Quadrinhos (3D), o Sonic Dash, o Homem Aranha e o Pac Man (fotos) no palco do shopping
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
      crianca(1, "comemorando", { x: -3.05, z: 0.6, r: 30 }),
      crianca(4, "apontando", { x: 3.05, z: -0.2, r: -40 }),
    ),
    lugar: "shopping", lente: 40, giro: 14, altura: 13, ocupa: 0.7,
    lugarOp: { confete: true, fundo: [] },
  },
  // Esportivos: o Basquete Home Quadrinhos (3D), o Show de Bola e o Basquete Home (fotos), em fila, na quadra
  esportivos: {
    maquinas: async () => grupo(
      await glb("basquete-street-quadrinhos", { x: -2.1, z: -0.3, r: 14 }),
      await maquina("show-de-bola", { x: 0.15, z: -0.5, r: 0 }),
      await maquina("basquete-home", { x: 2.3, z: -0.1, r: 0 }),
      colocar(P.bolaFutebol(0.2), { x: 0.9, z: 1.3 }),
      colocar(P.bolaBasquete(0.21), { x: -0.6, z: 1.45 }),
    ),
    naTela: naFrente([[0.82, -0.84, 0, "correndo", -60], [-0.82, -0.82, 3, "comemorando", 30]]),
    lugar: "quadra", lente: 40, giro: 10, altura: 11,
  },
  // Kids: o Sonic Kids, o Minions Kids, a Pantera Cor de Rosa Kids e o Homem Aranha Kids (fotos), em fila, e o Air Game
  // Kids Alienígenas (3D) à direita, no buffet (a mesa de doces fica encostada na parede do lado, longe das máquinas)
  kids: {
    maquinas: async () => grupo(
      await maquina("sonic-kids", { x: -1.7, z: -0.3, r: 0 }),
      await maquina("minions-kids", { x: -0.6, z: -0.35, r: 0 }),
      await maquina("pantera-kids", { x: 0.5, z: -0.35, r: 0 }),
      await maquina("homem-aranha-kids", { x: 1.6, z: -0.3, r: 0 }),
      await glb("air-game-kids-alienigenas", { x: 3.3, z: 0.7, r: -12 }),
    ),
    vida: () => grupo(
      crianca(5, "jogando", { x: 3.35, z: -0.3, r: -12, escala: 0.92 }),
    ),
    naTela: naFrente([[-0.8, -0.84, 3, "correndo", 50], [0.15, -0.9, 6, "comemorando", -20]]),
    lugar: "buffet", lente: 40, giro: 10, altura: 12,
    lugarOp: { parede: "#93c5fd", fundo: ["bob-esponja-kids"], lado: 2.8, painel: false },
  },
  // Casinhas Cenográficas (a categoria nova da Black Friday, seção 78): a Cozinha Infantil, a Oficina de
  // Engenharia e o Salão de Beleza (fotos, tiradas do fundo de neon vermelho do cartaz), lado a lado, na
  // brinquedoteca -- o lugar do faz de conta --, com a criançada
  "casinhas-cenograficas": {
    maquinas: async () => grupo(
      await maquina("cozinha-infantil", { x: -1.72, z: 0.15, r: 8 }),
      await maquina("oficina-de-engenharia", { x: 0, z: -0.15, r: 0 }),
      await maquina("salao-de-beleza", { x: 1.72, z: 0.15, r: -8 }),
    ),
    // (as crianças no chão livre da frente, pelo lugar na tela: inteiras na foto, nenhuma cortada na borda)
    naTela: naFrente([[-0.62, -0.86, 4, "comemorando", 30], [0.1, -0.9, 0, "correndo", -60], [0.66, -0.86, 1, "apontando", -40]]),
    lugar: "brinquedoteca", lente: 40, giro: 8, altura: 8, ocupa: 0.84,
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
   `imagem_brinquedo`) e a primeira da galeria. O cliente mostrou o nível que
   quer: as imagens da fábrica do Brinquedão Modelo 5 no salão (a parede com
   o mural pintado, o piso de madeira com o reflexo suave, o teto claro, a
   luz difusa, o produto grande e nítido) -- e "nas fotos individuais não
   coloque as crianças". Então a capa é o produto SOZINHO, inteiro, grande e
   nítido, sem gente e sem outra máquina, no SHOWROOM DA LAZER & SPORT (lugares.js,
   `showroom`: o padrão de todas as fotos de produto, o da foto de verdade do
   Boliche Virtual), com a luz de estúdio; o Espaço Esportivo Modelo 1 (39 x 23 m),
   do alto, no galpão. QUADRADA: o card de produto é quadrado (ls-tema.css, `.card-mini
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
  // o Brinquedão Modelo 2 (o da selva)
  "brinquedao-modelo-2": {
    maquinas: async () => glb("brinquedao-modelo-2"),
    lugar: "showroom", lente: 40, giro: 36, altura: 6, lugarOp: { cenario: "plantas", semente: 81 },
  },
  // o Brinquedão Modelo 3 (a lojinha e o fliperama na frente)
  "brinquedao-modelo-3": {
    maquinas: async () => glb("brinquedao-modelo-3"),
    lugar: "showroom", lente: 40, giro: 32, altura: 6, lugarOp: { cenario: "fliperama", deslocar: -2.0, semente: 83 },
  },
  // o Brinquedão Ninja, visto pela ponta da entrada (a câmera pela esquerda)
  "brinquedao-ninja": {
    maquinas: async () => glb("brinquedao-ninja"),
    lugar: "showroom", lente: 40, giro: -38, altura: 6, lugarOp: { cenario: "plantas", deslocar: 1.5, semente: 85 },
  },
  // o Espaço Esportivo Modelo 1, do alto (o salão inteiro: as quadras, as camas, o circuito), no galpão
  "espaco-esportivo-modelo-1": {
    maquinas: async () => glb("espaco-esportivo-modelo-1"),
    lugar: "galpao", lente: 40, giro: 26, altura: 30, ocupa: 0.86, desce: 0.02,
  },
  // o Trampolim de Enterrada
  "trampolim-enterrada": {
    maquinas: async () => glb("trampolim-enterrada"),
    lugar: "showroom", lente: 40, giro: 30, altura: 7, lugarOp: { cenario: "logo", semente: 87 },
  },
  // o Strike Kids, quase de frente (a pista, a tela e a testeira)
  "strike-kids": {
    maquinas: async () => glb("strike-kids"),
    lugar: "showroom", lente: 40, giro: 30, altura: 6, ocupa: 0.82,
    lugarOp: { cenario: "vitrine", semente: 89 },
  },
  // o Air Game Kids Alienígenas, um tanto de cima (o tampo e a lateral)
  "air-game-kids-alienigenas": {
    maquinas: async () => glb("air-game-kids-alienigenas"),
    lugar: "showroom", lente: 40, giro: 30, altura: 16, ocupa: 0.78,
    lugarOp: { cenario: "plantas", deslocar: 0.6, semente: 91 },
  },
  // o Basquete Home Quadrinhos, de 3/4 (o console, a rampa e a lateral)
  "basquete-street-quadrinhos": {
    maquinas: async () => glb("basquete-street-quadrinhos"),
    lugar: "showroom", lente: 40, giro: 26, altura: 6, ocupa: 0.82,
    lugarOp: { cenario: "vitrine", deslocar: -1.0, semente: 93 },
  },
};

/* ---------------------------------------------------------------- as capas do catálogo
   O cliente, sobre as capas dos produtos do catálogo que são a foto da máquina no
   fundo branco: "você deve criar o fundo para todos que tem fundo branco, tirando
   sempre o zoom e mostrando todo o brinquedo, com fundos originais, com vida e com
   os estabelecimentos coerentes, não com cara muito de IA, parecendo mais bonito e
   vivo, é para vender!!!". Então cada uma vira uma FOTO no lugar onde a máquina fica
   de verdade: o SHOWROOM DA LAZER & SPORT, o padrão das fotos de produto (a foto
   de verdade do Boliche Virtual no catálogo: o painel preto com a placa do logo, o
   canteiro, os perfis de LED, o porcelanato que reflete) --, QUADRADA (1600 x 1600, o
   card) e com a máquina INTEIRA e grande, com folga em volta. Sem gente (são fotos
   individuais). A luz é a de estúdio (a principal de 3/4, o preenchimento, o recorte)
   e o tone mapping é o neutro: a arte sai viva, como na foto do produto.
   A máquina é a FOTO DO CATÁLOGO recortada (recortar.py --alta, maquinas-alta/), em
   pé no chão, de frente para a câmera; a câmera fica na altura e no lado da foto
   (a maioria é de 3/4, na altura dos olhos: `giro` é o lado que a foto mostra, `altura`
   o quanto ela é de cima), e o lugar gira com ela -- as linhas do chão e das paredes
   casam com as da máquina. O recorte recebe a luz do lugar (um tanto: a cor dele casa
   com a da sala), a sombra de contato embaixo e a sombra projetada macia; no piso que
   brilha, o reflexo suave. O compor.py desfoca o fundo (a profundidade de campo) e põe
   um grão bem leve.
   As variações (o que fica atrás, o quanto o nicho anda, o lado da câmera) não deixam as fotos iguais. */
// o showroom em cada capa: o que fica atrás do produto (o logo ao lado, o canteiro, a parede de
// fliperama, a vitrine) e o quanto o nicho anda, para não repetir a mesma foto
const v = (cenario, deslocar = 0, semente = 19, extra = {}) => ({ lugar: "showroom", lugarOp: Object.assign({ cenario, deslocar: cenario === "logo" ? 0 : deslocar, semente }, extra) });
const CATALOGO = {
  // fliperama, simulador, basquete
  "mundo-zumbi": { ...v("logo", 0.2, 3), giro: -24, altura: 8 },
  "simulador-mario-kart": { ...v("fliperama", -1.0, 5), giro: -24, altura: 8 },
  "basquete-street": { ...v("vitrine", 1.2, 7), giro: 24, altura: 7 },
  "basquete-home": { ...v("logo", -0.3, 9), giro: 20, altura: 8 },
  "show-de-bola": { ...v("plantas", 1.4, 11), giro: -24, altura: 9 },
  "multi-jogos-retro": { ...v("fliperama", 1.6, 13), giro: 22, altura: 7 },
  "gabinete-games": { ...v("logo", 0.4, 15), giro: 22, altura: 8 },
  "pinball-32": { ...v("vitrine", -1.5, 17), giro: -24, altura: 12 },
  "pinball-40": { ...v("plantas", -1.2, 19), giro: 24, altura: 12 },
  "homem-aranha": { ...v("fliperama", 0.8, 21), giro: -22, altura: 7 },
  "sonic-dash": { ...v("logo", 0, 23), giro: 22, altura: 7 },
  "subway-surfers": { ...v("vitrine", 0.6, 25), giro: 22, altura: 7 },
  "flappy-bird": { ...v("plantas", 1.8, 27), giro: 22, altura: 7 },
  "speed-turbo": { ...v("logo", 0.5, 29), giro: -22, altura: 7 },
  "nervo-teste": { ...v("logo", 0.9, 31), giro: 8, altura: 6 },
  "lazer-shot": { ...v("fliperama", -0.6, 33), giro: 6, altura: 6 },
  "top-racer": { ...v("vitrine", -0.8, 35), giro: 22, altura: 8 },
  "matrix-one-piece": { ...v("plantas", -1.6, 37), giro: 6, altura: 6 },
  // os kids
  "homem-aranha-kids": { ...v("logo", -0.4, 39), giro: -12, altura: 7 },
  "tomb-raider-kids": { ...v("plantas", 1.0, 41), giro: -8, altura: 7 },
  "corrida-dos-minions": { ...v("fliperama", 1.2, 43), giro: 22, altura: 9 },
  "pega-toupeira": { ...v("logo", 0.6, 45), giro: 10, altura: 10 },
  "pantera-kids": { ...v("vitrine", -0.4, 47), giro: 8, altura: 7 },
  "sonic-kids": { ...v("logo", -0.8, 49), giro: -8, altura: 7 },
  "minions-kids": { ...v("plantas", -0.9, 51), giro: 8, altura: 7 },
  "bob-esponja-kids": { ...v("fliperama", -1.4, 53), giro: -6, altura: 7 },
  "air-game-kids": { ...v("plantas", 0.4, 55), giro: 4, altura: 16 },
  "brinquedao-modelo-1": { ...v("logo", -1.0, 57), giro: -12, altura: 10, ocupa: 0.86 },
  // os jogos de mesa
  "air-game-premium": { ...v("plantas", 0.8, 59), giro: 22, altura: 22 },
  "air-game-home": { ...v("logo", 0.3, 61), giro: 20, altura: 22 },
  "pebolim-eletronico": { ...v("vitrine", 0.5, 63), giro: 18, altura: 18 },
  "pac-man": { ...v("plantas", -0.7, 65), giro: 24, altura: 22 },
  "matrix": { ...v("logo", -0.5, 67), giro: 24, altura: 24 },
  "multi-jogos": { ...v("fliperama", 0.3, 69), giro: -22, altura: 12 },
  // os mecânicos e os carrinhos
  "labamba": { ...v("vitrine", -1.0, 71), giro: -24, altura: 22 },
  "carrossel-sorvetinho": { ...v("plantas", 0.6, 73), giro: 10, altura: 14 },
  "mini-roda-sorvete": { ...v("logo", 0.8, 75), giro: 15, altura: 16 },
  "sonic-racing": { ...v("fliperama", -0.9, 77), giro: 22, altura: 10 },
  "porsche-simulador": { ...v("vitrine", 1.4, 79), giro: 24, altura: 10 },
  // os da Black Friday (seção 78): a máquina tirada do fundo de neon vermelho do cartaz ou da foto
  // panorâmica (recortar_vermelho.py), cada uma num canto do showroom e do lado que a foto mostra
  "basquete-duplo": { ...v("fliperama", 0.6, 95), giro: -20, altura: 8 },
  "basquete-kids": { ...v("vitrine", -0.5, 97), giro: -18, altura: 10 },
  "cozinha-infantil": { ...v("plantas", 1.0, 99), giro: -14, altura: 9 },
  "oficina-de-engenharia": { ...v("logo", 0, 101), giro: -14, altura: 9 },
  "salao-de-beleza": { ...v("fliperama", -1.3, 103), giro: -14, altura: 9 },
  "air-rock": { ...v("plantas", 0.6, 105), giro: -24, altura: 24 },
  "kid-play": { ...v("vitrine", 0.8, 107), giro: 10, altura: 14, ocupa: 0.86 },
};

// os recortes em alta (maquinas-alta/<chave>.webp), carregados quando a capa pede
const altas = new Map();
async function carregarAlta(chave) {
  if (altas.has(chave)) return;
  const t = await leitorTextura.loadAsync(`maquinas-alta/${chave}.webp`);
  t.colorSpace = T.SRGBColorSpace;
  t.anisotropy = 16;
  altas.set(chave, t);
}
const matContatoForte = new T.MeshBasicMaterial({ map: texturaContato, transparent: true, depthWrite: false, toneMapped: false, opacity: 1 });

/** A máquina do catálogo em foto, em alta, de pé no chão e de frente para a câmera (as capas do catálogo). */
function maquinaAlta(chave) {
  const t = altas.get(chave);
  const ficha = FICHA[chave];
  const a = ficha.altura;
  const l = (a * t.image.width) / t.image.height;
  // a cor da foto, com um tanto da luz do lugar (casa com a sala sem perder a foto)
  const mat = new T.MeshStandardMaterial({
    map: t, emissiveMap: t, emissive: "#ffffff", emissiveIntensity: 0.3, alphaTest: 0.5,
    roughness: 0.85, metalness: 0, side: T.DoubleSide, envMapIntensity: 0.25,
  });
  const plano = new T.Mesh(new T.PlaneGeometry(l, a), mat);
  plano.position.y = a / 2;
  plano.castShadow = true;
  plano.customDepthMaterial = new T.MeshDepthMaterial({ depthPacking: T.RGBADepthPacking, map: t, alphaTest: 0.5 });
  plano.userData.recorte = t;
  const g = new T.Group();
  g.add(plano);
  // a sombra de contato: a justa e escura bem embaixo, e a larga e macia em volta
  for (const [largura, fundo, z, material] of [[l * 0.92, Math.max(0.22, l * 0.22), -l * 0.06, matContatoForte], [l * 1.35, Math.max(0.5, l * 0.7), -l * 0.22, matContato]]) {
    const contato = new T.Mesh(new T.PlaneGeometry(largura, fundo), material);
    contato.rotation.x = -Math.PI / 2;
    contato.position.set(0, 0.004, z);
    contato.userData.sombraContato = true;
    g.add(contato);
  }
  g.rotation.y = giroDaCena * GRAU;
  g.userData.maquina = ficha.nome;
  return g;
}

/* ---------------------------------------------------------------- as vistas da galeria dos nossos 3D
   O cliente: "faça padrão para todas as imagens 2D". As fotos da galeria que saem dos
   nossos .glb (frente, lados, verso, tampo, jogador...) eram o objeto num fundo claro;
   agora são fotos no showroom, como as capas: a mesma luz de estúdio e o mesmo piso, cada
   vista do lado dela (a câmera das ferramentas de cada modelo, ferramentas/modelos3d/
   <modelo>/gerar.cjs, vira o giro e a altura daqui), o objeto inteiro e sem gente. O
   compor.py grava por cima do mesmo arquivo (core/static/site/arena/modelos/<chave>/
   <vista>.webp), no mesmo tamanho: o cadastro (CADASTROS) e a Arena não mudam. Ficam
   como estão: as fotos de verdade, as imagens da fábrica (os Brinquedões Modelo 2, 4, 5 e
   Ninja têm as da fábrica), as plantas (o desenho de cima) e as cores do Strike Kids. */
const vista = (pos, alvo, extra = {}) => {
  const d = [pos[0] - alvo[0], pos[1] - alvo[1], pos[2] - alvo[2]];
  const giro = Math.atan2(d[0], d[2]) / GRAU, altura = Math.atan2(d[1], Math.hypot(d[0], d[2])) / GRAU;
  return Object.assign({ giro: Math.round(giro * 10) / 10, altura: Math.round(altura * 10) / 10 }, extra);
};
const VISTAS = {
  // o Air Game Kids dos Astronautas (LEIA-ME 72: o adesivo padrão), o mesmo móvel e as mesmas vistas do Alienígenas
  "air-game-kids-astronautas": {
    tamanho: [1600, 1000], cenario: ["logo", "plantas", "vitrine", "fliperama", "plantas"],
    vistas: {
      frente: vista([2.3, 1.85, 2.9], [0, 0.55, 0]),
      // a mesa é simétrica: o lado esquerdo do outro lado era o direito de novo, e o verso,
      // a frente; agora o esquerdo é em 3/4, baixo, na altura das crianças, e o verso, a cabeceira
      lado_esquerdo: vista([-1.9, 0.62, 2.0], [0, 0.45, 0]),
      lado_direito: vista([3.3, 1.35, -1.1], [0, 0.55, 0]),
      verso: vista([0, 1.2, 3.3], [0, 0.5, 0]),
      tampo: { giro: 0, altura: 62 },
    },
  },
  "air-game-kids-alienigenas": {
    tamanho: [1600, 1000], cenario: ["logo", "plantas", "vitrine", "fliperama", "plantas"],
    vistas: {
      frente: vista([2.3, 1.85, 2.9], [0, 0.55, 0]),
      // a mesa é simétrica: o lado esquerdo do outro lado era o direito de novo, e o verso,
      // a frente; agora o esquerdo é em 3/4, baixo, na altura das crianças, e o verso, a cabeceira
      lado_esquerdo: vista([-1.9, 0.62, 2.0], [0, 0.45, 0]),
      lado_direito: vista([3.3, 1.35, -1.1], [0, 0.55, 0]),
      verso: vista([0, 1.2, 3.3], [0, 0.5, 0]),
      tampo: { giro: 0, altura: 62 },
    },
  },
  "basquete-street-quadrinhos": {
    tamanho: [1600, 1000], cenario: ["logo", "plantas", "vitrine", "fliperama", "logo"],
    vistas: {
      frente: vista([3.7, 2.5, 4.9], [0, 1.25, 0]),
      lado_esquerdo: vista([-6.0, 1.7, 1.6], [0, 1.3, 0]),
      // o direito de longe era o esquerdo espelhado (a mesma arte dos dois lados): agora de perto e baixo, com o console
      lado_direito: vista([3.0, 1.0, 2.6], [0, 1.0, 0.3]),
      verso: vista([-3.4, 2.4, -5.4], [0, 1.3, 0]),
      jogador: vista([0.4, 2.1, 6.2], [0, 1.3, -0.4]),
    },
  },
  // o Brinquedão Modelo 2: os lados vinham da folha da fábrica, de fundo branco (o recorte para artes); estes são do 3D
  "brinquedao-modelo-2": {
    tamanho: [1600, 1000], cenario: ["plantas", "logo"],
    vistas: {
      lado_esquerdo_3d: { giro: -42, altura: 8 },
      lado_direito_3d: { giro: 78, altura: 10 },
    },
  },
  "brinquedao-modelo-3": {
    tamanho: [1600, 1000], cenario: ["plantas", "logo", "fliperama"],
    vistas: {
      frente: vista([7.8, 4.4, 11.2], [0.4, 1.5, 0]),
      lado_esquerdo: vista([-11, 4.2, 7.2], [-0.8, 1.5, 0]),
      lado_direito: vista([11.6, 4.0, 4.4], [1.2, 1.4, 0]),
    },
  },
  "brinquedao-modelo-5": {
    tamanho: [1600, 1000], cenario: ["plantas", "logo", "fliperama", "vitrine"],
    vistas: {
      frente: vista([1.2, 1.9, 7.6], [0.05, 0.95, 0]),
      lado_esquerdo: vista([-6.4, 2.3, 4.4], [-0.2, 0.9, 0]),
      lado_direito: vista([6.6, 2.3, 3.6], [0.3, 0.9, 0]),
      perspectiva_3d: { giro: 42, altura: 24 },
    },
  },
  "espaco-esportivo-modelo-1": {
    tamanho: [1600, 1000], lugar: "galpao",
    vistas: {
      frente: vista([0, 25, 52], [0, 0, 0]),
      lado_direito: vista([39, 22, 35], [0, 0, 0]),
      lado_esquerdo: vista([-39, 22, 35], [0, 0, 0]),
    },
  },
  "strike-kids": {
    tamanho: [1080, 1080], cenario: ["logo", "plantas", "vitrine", "fliperama", "logo", "plantas"],
    vistas: {
      frente: { giro: 0, altura: 14 },
      lado_direito: { giro: 90, altura: 10 },
      lado_esquerdo: { giro: -90, altura: 10 },
      verso: { giro: 180, altura: 12 },
      tres_quartos_esquerda: { giro: -40, altura: 12 },
      de_cima: { giro: 20, altura: 48 },
    },
  },
  "trampolim-enterrada": {
    tamanho: [1600, 1000], cenario: ["logo", "plantas", "vitrine", "fliperama"],
    vistas: {
      frente: vista([6.6, 3.5, 8.0], [0, 1.3, 0]),
      lado_esquerdo: vista([-7.6, 3.5, 8.0], [-0.6, 1.3, 0]),
      lado_direito: vista([9.6, 3.3, 2.6], [0, 1.3, 0]),
      espuma: vista([6.6, 3.5, 8.0], [0, 1.3, 0], { glb: "trampolim-enterrada-espuma" }),
    },
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
  composer.setSize(LARGURA, ALTURA);
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
window.PRODUTOS = Object.keys(CATALOGO).map((chave) => "produto:" + chave);
window.VISTAS = Object.entries(VISTAS).flatMap(([chave, m]) => Object.keys(m.vistas).map((nome) => `vista:${chave}:${nome}`));
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
  // "criancas": as crianças de pessoas.js lado a lado, em todas as poses (para conferir)
  if (chave === "criancas") {
    c = { maquinas: async () => grupo(...["parada", "correndo", "andando", "pulando", "comemorando", "jogando", "apontando", "olhando"].map((pose, i) =>
      crianca(i, pose, { x: (i - 3.5) * 0.62, r: i % 2 ? 20 : -15 }))), giro: 0, altura: 6, lente: 30 };
  }
  if (chave.startsWith("area:")) {
    const [, tipo, cor, semente, medidas, porte, estilo] = chave.split(":");
    const [largura, profundidade, altura] = medidas.split("x").map(Number);
    c = { maquinas: () => area(tipo, { largura, profundidade, altura }, "#" + cor, Number(semente), { porte, estilo }), giro: 30, altura: 30, lente: 26 };
  }
  // "produto:<chave>", a capa do catálogo (a foto da máquina no lugar dela: quadrada, sem gente)
  if (chave.startsWith("produto:") && CATALOGO[chave.slice(8)]) {
    const qual = chave.slice(8);
    c = Object.assign({ quadrado: true, ocupa: 0.8, desce: 0.05, rampa: 2.2, lente: 38 }, CATALOGO[qual], {
      maquinas: async () => {
        await carregarAlta(qual);
        return maquinaAlta(qual);
      },
    });
  }
  // "vista:<chave>:<nome>", uma foto da galeria de um 3D nosso (no showroom, do lado da vista)
  if (chave.startsWith("vista:")) {
    const [, qual, nome] = chave.split(":");
    const modelo = VISTAS[qual], v = modelo && modelo.vistas[nome];
    if (v) {
      const k = Object.keys(modelo.vistas).indexOf(nome);
      const lugar = modelo.lugar || "showroom";
      // a vista de trás (ou quase): quem gira é o objeto, e não a câmera -- a câmera atrás
      // dele ficaria atrás da parede do fundo do lugar
      const virar = Math.abs(v.giro) > 95;
      const giro = virar ? v.giro - Math.sign(v.giro) * 180 : v.giro;
      c = Object.assign({ lugar, lente: 36, ocupa: 0.8, desce: 0.04, rampa: 3, formato: modelo.tamanho }, v, {
        giro,
        lugarOp: lugar === "showroom" ? { cenario: (modelo.cenario || ["logo"])[k % (modelo.cenario || ["logo"]).length], semente: 101 + k } : {},
        maquinas: async () => glb(v.glb || qual, { r: virar ? 180 : 0 }),
      });
    }
  }
  // "capa:<chave>", a capa do produto (quadrada, o produto grande)
  if (chave.startsWith("capa:")) c = CAPAS[chave.slice(5)] && Object.assign({ quadrado: true, ocupa: 0.86, desce: 0.04 }, CAPAS[chave.slice(5)]);
  c = Object.assign({}, c, ajustes);
  if (!c.maquinas) throw new Error("cena desconhecida: " + chave);
  // `previa`: a metade do tamanho (para acertar o ângulo depressa)
  // (a vista da galeria: o tamanho do arquivo de antes, no dobro -- até 3200 de largura)
  const [largura, altura] = c.formato
    ? [Math.min(3200, c.formato[0] * 2), Math.round((Math.min(3200, c.formato[0] * 2) * c.formato[1]) / c.formato[0])]
    : c.quadrado ? [3200, 3200] : [3200, 2400];
  formato(c.previa ? largura / 2 : largura, c.previa ? altura / 2 : altura);
  if (atual) cena.remove(atual);
  if (atualLugar) cena.remove(atualLugar);
  giroDaCena = c.giro;
  const op = c.lugarOp || {};
  await carregarFotos([...(Array.isArray(op.fundo) ? op.fundo : []), ...(op.vizinhas || [])]);
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
  // o enquadramento, pelas máquinas sozinhas (antes do lugar: ele precisa saber onde a câmera
  // fica -- o teto do salão, por exemplo, tem de ficar acima dela, para a foto ser de dentro)
  const ocupa = c.ocupa ?? (c.lugar ? 0.76 : 0.86), desce = c.desce ?? (c.lugar ? 0.1 : 0);
  const quadro = enquadrar(caixa, c.giro, c.altura, c.lente, ocupa, desce);
  if (c.lugar) acertarPelaSilhueta(quadro, atual, null, ocupa, desce);
  // a foto de produto: o tone mapping neutro (o ACES desbota e escurece as cores fortes da arte)
  // e a luz de estúdio na medida do produto, a partir do lado da câmera
  const estudio = c.estudio ?? (chave.startsWith("produto:") || chave.startsWith("capa:") || chave.startsWith("vista:"));
  // (as categorias também: o neutro mantém as cores das máquinas fiéis às fotos)
  renderer.toneMapping = T.NeutralToneMapping;
  const raioDoProduto = caixa.getBoundingSphere(new T.Sphere()).radius;
  for (const [luzEstudio, giroDaLuz, alturaDaLuz, forca] of [[principal, 38, 38, 1], [preenchimento, -55, 18, 0.32], [recorte, 165, 50, 0.9]]) {
    if (!estudio) {
      luzEstudio.intensity = 0;
      continue;
    }
    const a = (c.giro + (c.giro >= 0 ? giroDaLuz : -giroDaLuz)) * GRAU, e = alturaDaLuz * GRAU;
    const d = Math.max(3.5, raioDoProduto * 3.2);
    luzEstudio.position.set(centro.x + Math.sin(a) * Math.cos(e) * d, centro.y + Math.sin(e) * d, centro.z + Math.cos(a) * Math.cos(e) * d);
    luzEstudio.target.position.copy(centro);
    luzEstudio.angle = Math.min(1.2, Math.atan((raioDoProduto * 1.6) / d) + 0.15);
    // (os nossos .glb pedem mais luz que as fotos do catálogo, que já vêm iluminadas: a arte sai viva)
    luzEstudio.intensity = forca * (c.luzEstudio ?? (chave.startsWith("produto:") ? 3.2 : 4.8)) * d * d;
    luzEstudio.shadow.camera.near = 0.5;
    luzEstudio.shadow.camera.far = d * 3;
  }
  // o lugar em volta (e a luz dele) e a vida (as crianças, o que está no ar)
  const lugar = c.lugar ? LUGARES[c.lugar](caixa, c.giro, Object.assign({ alturaDaCamera: camera.position.y }, op)) : null;
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
  if (estudio) {
    // o sol vira só a luz geral do lugar (a do produto é a de estúdio), e o lugar fica mais escuro que ele
    sol.intensity = (l.sol ?? 2.4) * 0.35;
    hemi.intensity = (l.hemi ?? 1.25) * 0.6;
  }
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
  // o que fica na frente, desfocado (nos cantos de baixo), e o reflexo das máquinas no piso
  // (a coisa desfocada na frente, cortada no canto da foto, saiu: "nada cortado de um jeito estranho na borda")
  if (lugar && lugar.frente && c.frente === true) atualLugar.add(lugar.frente(chaoNaTela, camera));
  // as crianças da frente (as capas): no chão livre da foto, já enquadrada
  if (lugar && c.naTela) atualLugar.add(c.naTela(chaoNaTela));
  if (lugar && lugar.reflexo) {
    const espelho = atual.clone(true);
    // (o clone copia o userData em JSON: a textura do recorte volta a ser a de verdade)
    const originais = [];
    atual.traverse((o) => originais.push(o));
    let k = 0;
    espelho.traverse((o) => {
      const original = originais[k++];
      if (original && original.userData.recorte) o.userData.recorte = original.userData.recorte;
      o.castShadow = false;
      if (o.userData.sombraContato) o.visible = false;
    });
    espelho.scale.y = -1;
    atualLugar.add(espelho);
  }
  if (lugar) {
    // a oclusão de ambiente na medida da cena (um raio de ~5% do tamanho das máquinas)
    const raio = Math.min(1.0, Math.max(0.03, maior * 0.05)) * (c.ao ?? 1);
    gtao.updateGtaoMaterial({ radius: raio, thickness: raio, distanceExponent: 1.2, scale: 1.1, samples: 16, screenSpaceRadius: false });
    gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16 });
    gtao.blendIntensity = c.aoForca ?? 0.9;
    composer.render();
  } else {
    renderer.render(cena, camera);
  }
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
