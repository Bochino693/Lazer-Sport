// Monta as máquinas dos jogos da casa em three.js e exporta o .glb:
//   ?maquina=lazer-shot      o gabinete do Lazer Shot (tiro com pistola de luz)
//   ?maquina=boliche-virtual o Boliche Virtual (roda o Dragon Bowling)
// Metros, Y para cima, frente em +Z, o chão em y = 0 e o centro em x = 0.
// As peças que NÃO são adesivo levam o nome que o cores3d.js deixa como
// está nas cores (tela_video, led_*, metal_*, bola_*, pista, bolsao).
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";

const MAQUINA = new URLSearchParams(location.search).get("maquina") || "lazer-shot";
const raiz = new THREE.Group();
raiz.name = MAQUINA;

const carregador = new THREE.TextureLoader();
async function textura(arquivo) {
  const t = await carregador.loadAsync("arte/" + arquivo);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (/\.jpe?g$/.test(arquivo)) t.userData.mimeType = "image/jpeg";
  return t;
}
const material = (nome, opcoes) => new THREE.MeshStandardMaterial({ name: nome, roughness: 0.5, metalness: 0, ...opcoes });
function malha(nome, geometria, mat, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(geometria, mat);
  m.name = nome;
  m.position.set(x, y, z);
  raiz.add(m);
  return m;
}
const caixa = (nome, w, h, d, mat, x, y, z) => malha(nome, new THREE.BoxGeometry(w, h, d), mat, x, y, z);
function plano(nome, w, h, mat, x, y, z, giroY = 0, giroX = 0) {
  const m = malha(nome, new THREE.PlaneGeometry(w, h), mat, x, y, z);
  m.rotation.set(giroX, giroY, 0, "YXZ");
  return m;
}

/** A lateral da máquina: o perfil (z, y) extrudado na espessura, com a arte. */
function lateral(nome, perfil, espessura, mat, x, espelhar) {
  const forma = new THREE.Shape(perfil.map(([z, y]) => new THREE.Vector2(z, y)));
  const g = new THREE.ExtrudeGeometry(forma, { depth: espessura, bevelEnabled: false });
  // a arte cobre o perfil inteiro: u = fundo -> frente, v = chão -> topo
  const zs = perfil.map((p) => p[0]);
  const ys = perfil.map((p) => p[1]);
  const [z0, z1, y0, y1] = [Math.min(...zs), Math.max(...zs), Math.min(...ys), Math.max(...ys)];
  const pos = g.attributes.position;
  const uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) {
    let u = (pos.getX(i) - z0) / (z1 - z0);
    if (espelhar) u = 1 - u;
    uv.setXY(i, u, (pos.getY(i) - y0) / (y1 - y0));
  }
  const m = malha(nome, g, mat);
  // a forma é desenhada no plano XY: gira para o perfil ficar no plano ZY
  m.rotation.y = -Math.PI / 2;
  m.position.x = x + espessura;
  return m;
}

/** A tela do jogo: a imagem de uma partida, acesa (emissiva). */
function telaDoJogo(nome, mapa, w, h) {
  return material(nome, { color: "#000000", emissive: "#ffffff", emissiveMap: mapa, emissiveIntensity: 1, roughness: 0.25, metalness: 0.1 });
}

// ======================================================================
// LAZER SHOT: gabinete em pé, TV em pé (9:16), letreiro aceso, a pistola
// personalizada no apoio e a câmera da foto do jogador em cima.
// ======================================================================
async function lazerShot() {
  const [lat, frente, letreiro, tela] = await Promise.all([
    textura("ls_lateral.jpg"), textura("ls_frente.jpg"), textura("ls_letreiro_full.jpg"), textura("ls_tela.jpg"),
  ]);
  const W = 1.04; // entre as laterais
  const E = 0.03; // espessura da lateral
  const preto = material("gabinete", { color: "#121216", roughness: 0.35 });
  const vermelho = material("acabamento", { color: "#d1102a", roughness: 0.35 });
  const artLat = material("adesivo_lateral", { map: lat, roughness: 0.45 });
  const artFrente = material("adesivo_frente", { map: frente, roughness: 0.45 });

  // o perfil do lado: base, apoio da pistola, a tela quase em pé e o letreiro por cima
  const perfil = [[-0.45, 0], [0.32, 0], [0.32, 0.88], [0.5, 0.98], [0.46, 1.05], [0.08, 1.05], [0.04, 2.02], [0.2, 2.06], [0.2, 2.26], [-0.45, 2.26]];
  // olhando do lado direito a frente fica à esquerda: a arte é espelhada lá
  lateral("adesivo_lateral_dir", perfil, E, artLat, W / 2, true);
  lateral("adesivo_lateral_esq", perfil, E, artLat, -W / 2 - E, false);

  // o miolo: frente da base, apoio, painel da tela, letreiro, topo e costas
  plano("adesivo_frente_base", W, 0.88, artFrente, 0, 0.44, 0.32);
  const apoio = caixa("apoio", W, 0.04, 0.42, vermelho, 0, 0.995, 0.28);
  apoio.rotation.x = -0.12;
  caixa("apoio_topo", W, 0.03, 0.4, preto, 0, 1.04, 0.27);
  // a moldura da TV e a TV em pé
  const moldura = caixa("moldura", W, 0.98, 0.04, preto, 0, 1.535, 0.04);
  moldura.rotation.x = -0.04;
  const tv = plano("tela_video", 0.54, 0.96, telaDoJogo("tela_video", tela), 0, 1.535, 0.083, 0, -0.04);
  tv.renderOrder = 1;
  // as fitas de LED vermelhas dos dois lados da tela e embaixo do letreiro
  const led = material("led", { color: "#ff2a3f", emissive: "#ff1f36", emissiveIntensity: 2.2 });
  for (const lado of [-1, 1]) {
    const fita = caixa(`led_tela_${lado < 0 ? "esq" : "dir"}`, 0.018, 0.94, 0.012, led, lado * 0.36, 1.535, 0.075);
    fita.rotation.x = -0.04;
    // os alto-falantes no painel da tela
    const caixaSom = malha(`metal_som_${lado < 0 ? "esq" : "dir"}`, new THREE.CylinderGeometry(0.07, 0.07, 0.02, 32), material("metal_som", { color: "#1d1d22", roughness: 0.8 }), lado * 0.44, 1.2, 0.07);
    caixaSom.rotation.x = Math.PI / 2;
  }
  caixa("led_letreiro", W, 0.012, 0.012, led, 0, 2.055, 0.2);
  // o letreiro aceso
  const placa = material("led_letreiro_placa", { color: "#000000", emissive: "#ffffff", emissiveMap: letreiro, emissiveIntensity: 1.25, roughness: 0.3 });
  plano("led_letreiro_frente", W, 0.2, placa, 0, 2.16, 0.201);
  caixa("letreiro_baixo", W, 0.01, 0.16, preto, 0, 2.06, 0.12);
  caixa("topo", W, 0.02, 0.65, preto, 0, 2.25, -0.125);
  caixa("costas", W, 2.24, 0.02, preto, 0, 1.13, -0.44);
  caixa("rodape", W + 2 * E, 0.05, 0.78, vermelho, 0, 0.025, -0.065);

  // a câmera da foto do jogador, em cima do letreiro
  const metal = material("metal_camera", { color: "#202228", roughness: 0.4, metalness: 0.4 });
  caixa("metal_camera", 0.12, 0.05, 0.06, metal, 0, 2.29, 0.12);
  const lente = malha("metal_camera_lente", new THREE.CylinderGeometry(0.018, 0.018, 0.012, 24), material("vidro_lente", { color: "#0a1a3a", roughness: 0.1, metalness: 0.6 }), 0, 2.29, 0.155);
  lente.rotation.x = Math.PI / 2;

  // a pistola personalizada, deitada no apoio, com o cabo
  const arma = new THREE.Group();
  arma.name = "metal_arma";
  const corpoArma = material("metal_arma_corpo", { color: "#c8102e", roughness: 0.3, metalness: 0.2 });
  const pretoArma = material("metal_arma_preto", { color: "#151518", roughness: 0.5 });
  const pecaArma = (nome, g, m, x, y, z, rz = 0) => {
    const p = new THREE.Mesh(g, m);
    p.name = nome;
    p.position.set(x, y, z);
    p.rotation.z = rz;
    arma.add(p);
  };
  pecaArma("metal_arma_ferrolho", new THREE.BoxGeometry(0.2, 0.045, 0.04), corpoArma, 0, 0.06, 0);
  pecaArma("metal_arma_cano", new THREE.CylinderGeometry(0.012, 0.012, 0.06, 16), pretoArma, 0.125, 0.065, 0, Math.PI / 2);
  pecaArma("metal_arma_cabo", new THREE.BoxGeometry(0.045, 0.11, 0.036), pretoArma, -0.06, 0.0, 0, 0.32);
  pecaArma("metal_arma_gatilho", new THREE.BoxGeometry(0.01, 0.03, 0.01), pretoArma, -0.015, 0.025, 0);
  pecaArma("led_arma_mira", new THREE.SphereGeometry(0.008, 12, 8), led, 0.157, 0.065, 0);
  arma.rotation.set(Math.PI / 2, 0, 0.0);
  arma.rotation.order = "YXZ";
  arma.rotation.y = 0.35;
  arma.position.set(0.26, 1.075, 0.3);
  raiz.add(arma);
  const caminho = new THREE.CatmullRomCurve3([new THREE.Vector3(0.22, 1.07, 0.3), new THREE.Vector3(0.2, 1.08, 0.22), new THREE.Vector3(0.3, 1.075, 0.14), new THREE.Vector3(0.36, 1.06, 0.12)]);
  malha("metal_arma_fio", new THREE.TubeGeometry(caminho, 24, 0.006, 8, false), pretoArma);
}

// ======================================================================
// BOLICHE VIRTUAL: a pista com os trilhos de LED (a fita de 60 LEDs da
// placa), as bolas na frente com START e CRÉDITO, e no fundo a torre com
// a tela em pé do Dragon Bowling e o letreiro do dragão.
// ======================================================================
async function bolicheVirtual() {
  const [torre, trilho, letreiro, frente, pista, tela] = await Promise.all([
    textura("db_torre.jpg"), textura("db_trilho.jpg"), textura("db_letreiro.jpg"), textura("db_frente.jpg"), textura("db_pista.jpg"), textura("db_tela.jpg"),
  ]);
  const L = 0.8;
  const FRENTE = 1.6;
  const FUNDO = -1.6;
  const TORRE = -0.95; // onde a torre começa
  const azul = material("gabinete", { color: "#0c2a7a", roughness: 0.4 });
  const azulEsc = material("gabinete_escuro", { color: "#071640", roughness: 0.5 });
  const artTorre = material("adesivo_torre", { map: torre, roughness: 0.45 });
  const artTrilho = material("adesivo_trilho", { map: trilho, roughness: 0.45 });
  const artFrente = material("adesivo_frente", { map: frente, roughness: 0.45 });

  // a pista: sobe de leve da frente para o fundo
  const comprimento = FRENTE - 0.25 - TORRE;
  const subida = Math.atan2(0.12, comprimento);
  const meioZ = (FRENTE - 0.25 + TORRE) / 2;
  pista.wrapS = pista.wrapT = THREE.ClampToEdgeWrapping;
  const chao = caixa("pista", L - 0.16, 0.03, comprimento, material("pista", { map: pista, roughness: 0.35 }), 0, 0.34, meioZ);
  chao.rotation.x = subida;
  // a base da pista (o móvel)
  caixa("base_pista", L - 0.16, 0.32, comprimento, azulEsc, 0, 0.16, meioZ);
  // os trilhos dos lados, com o adesivo do dragão e a fita de LED em cima
  const led = material("led_trilho", { color: "#5fd0ff", emissive: "#2fa8ff", emissiveIntensity: 2 });
  for (const lado of [-1, 1]) {
    const x = lado * (L / 2 - 0.04);
    const mats = [artTrilho, artTrilho, azul, azul, azul, azul];
    caixa(`adesivo_trilho_${lado < 0 ? "esq" : "dir"}`, 0.08, 0.52, FRENTE - TORRE, mats, x, 0.26, (FRENTE + TORRE) / 2);
    caixa(`led_trilho_${lado < 0 ? "esq" : "dir"}`, 0.02, 0.012, FRENTE - TORRE - 0.1, led, x, 0.526, (FRENTE + TORRE) / 2);
  }
  // a frente, onde a pessoa joga: o painel com START e CRÉDITO e o bolsão das bolas
  caixa("adesivo_frente", L - 0.16, 0.34, 0.25, [azul, azul, azulEsc, azul, artFrente, azul], 0, 0.17, FRENTE - 0.125);
  caixa("bolsao", L - 0.3, 0.02, 0.18, material("bolsao", { color: "#03081c", roughness: 0.9 }), 0, 0.345, FRENTE - 0.12);
  const cores = ["#1f6fff", "#ff8a1c", "#1f6fff"];
  cores.forEach((cor, i) => {
    malha(`bola_${i}`, new THREE.SphereGeometry(0.075, 28, 18), material(`bola_${i}`, { color: cor, roughness: 0.18, metalness: 0.1 }), -0.16 + i * 0.16, 0.42, FRENTE - 0.12);
  });
  const botao = (nome, cor, x) => {
    const b = malha(nome, new THREE.CylinderGeometry(0.035, 0.035, 0.03, 24), material(nome, { color: cor, emissive: cor, emissiveIntensity: 0.6, roughness: 0.3 }), x, 0.535, FRENTE - 0.05);
    return b;
  };
  caixa("painel_botoes", 0.36, 0.04, 0.12, azulEsc, 0, 0.5, FRENTE - 0.05);
  botao("led_botao_start", "#22e07a", -0.08);
  botao("led_botao_credito", "#ffd23f", 0.08);

  // a torre do fundo: as laterais com o dragão, a tela em pé e o letreiro
  const fundoTorre = TORRE - FUNDO;
  const zTorre = (TORRE + FUNDO) / 2;
  caixa("torre", L, 1.95, fundoTorre, [artTorre, artTorre, azul, azul, azulEsc, azulEsc], 0, 0.975, zTorre);
  // a boca por onde a bola entra (os sensores ficam lá dentro)
  caixa("bolsao_boca", L - 0.2, 0.36, 0.02, material("bolsao_boca", { color: "#02040c", roughness: 0.9 }), 0, 0.6, TORRE + 0.011);
  caixa("led_boca", L - 0.18, 0.015, 0.015, led, 0, 0.79, TORRE + 0.02);
  // a TV em pé (9:16) com a partida
  caixa("moldura", 0.62, 1.06, 0.04, material("moldura", { color: "#0b0d14", roughness: 0.4 }), 0, 1.42, TORRE + 0.02);
  plano("tela_video", 0.54, 0.96, telaDoJogo("tela_video", tela), 0, 1.42, TORRE + 0.041);
  // o letreiro aceso, um pouco mais largo e saliente
  const placa = material("led_letreiro_placa", { color: "#000000", emissive: "#ffffff", emissiveMap: letreiro, emissiveIntensity: 1.1, roughness: 0.3 });
  caixa("letreiro", L + 0.04, 0.43, fundoTorre + 0.1, [artTorre, artTorre, azul, azulEsc, azul, azulEsc], 0, 1.95 + 0.215, zTorre + 0.05);
  plano("led_letreiro_frente", L + 0.04, 0.43, placa, 0, 1.95 + 0.215, zTorre + 0.05 + (fundoTorre + 0.1) / 2 + 0.001);
  caixa("led_letreiro_fita", L + 0.04, 0.015, 0.015, led, 0, 1.95, zTorre + 0.05 + (fundoTorre + 0.1) / 2);
}

// ---------- montar, medir e exportar ----------
if (MAQUINA === "boliche-virtual") await bolicheVirtual();
else await lazerShot();

const cena = new THREE.Scene();
cena.background = new THREE.Color("#f2f5fa");
cena.add(raiz);
cena.add(new THREE.HemisphereLight("#ffffff", "#9aa8bd", 1.6));
const sol = new THREE.DirectionalLight("#ffffff", 2.2);
sol.position.set(4, 9, 7);
cena.add(sol);
const contra = new THREE.DirectionalLight("#cfe0ff", 0.9);
contra.position.set(-6, 4, -8);
cena.add(contra);

const caixaTudo = new THREE.Box3().setFromObject(raiz);
const tamanho = caixaTudo.getSize(new THREE.Vector3());
window.medidas = [tamanho.x, tamanho.y, tamanho.z].map((v) => Math.round(v * 100) / 100);
let triangulos = 0;
raiz.traverse((o) => { if (o.isMesh) triangulos += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3; });
window.triangulos = triangulos;

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(960, 960);
renderer.setPixelRatio(1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.append(renderer.domElement);
const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 100);
const centro = caixaTudo.getCenter(new THREE.Vector3());
const raio = tamanho.length() / 2;
window.ver = (giro, inclinacao, perto = 1) => {
  const d = (raio / Math.sin((15 * Math.PI) / 180)) * 0.82 * perto;
  camera.position.set(centro.x + Math.sin(giro) * Math.cos(inclinacao) * d, centro.y + Math.sin(inclinacao) * d, centro.z + Math.cos(giro) * Math.cos(inclinacao) * d);
  camera.lookAt(centro);
  renderer.render(cena, camera);
  return renderer.domElement.toDataURL("image/jpeg", 0.92);
};
window.exportar = () => new Promise((pronto, falhou) => {
  new GLTFExporter().parse(raiz, (glb) => {
    const bytes = new Uint8Array(glb);
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    pronto(btoa(s));
  }, falhou, { binary: true, maxTextureSize: 1024 });
});
window.pronto = true;
