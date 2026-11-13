// O que as máquinas de adesivo (o Basquete Home Quadrinhos, o Air Game Kids e o
// Strike Kids) dividem para sair em ALTA DEFINIÇÃO (LEIA-ME V10, seção 92):
//
//  * os MATERIAIS como os da máquina de verdade (PBR do glTF): o adesivo é
//    vinil impresso e laminado brilhante (o verniz, KHR_materials_clearcoat),
//    a estrutura preta é acetinada, o cromo é metal, o neon e os LEDs acendem
//    (emissive com KHR_materials_emissive_strength);
//  * a PLACA DE MDF com as bordas arredondadas (o raio na quina, como a peça
//    fresada) e o adesivo do tamanho da face plana (ele não passa da quina);
//  * os adesivos na resolução útil: a peça ampliada 4x com nitidez
//    (../ampliar_adesivos.py, adesivos-hd/<peça>.webp), até 2048 px no lado
//    maior, em JPEG de qualidade 0,9 dentro do .glb (sRGB);
//  * a fita de LED de pontos, o neon flex (um tubo pelo caminho) e as vistas
//    de conferência com a luz de ambiente (RoomEnvironment), a mesma dos
//    visores do site.
//
// Coordenadas em milímetros (cada montar.js converte para metros no fim).
import * as THREE from "three";
import { RoomEnvironment } from "/vendor/three/RoomEnvironment.js";

export const PELE = 1; // o adesivo fica 1 mm fora da madeira
export const QUALIDADE_JPEG = 0.9;

/* ---------------------------------------------------------------- materiais */

/** O vinil laminado brilhante dos adesivos: a arte (sRGB) com o verniz por cima. */
export function vinil(nome, map, extra = {}) {
  return new THREE.MeshPhysicalMaterial({
    name: nome, map, color: "#ffffff", roughness: 0.42, metalness: 0,
    clearcoat: 1, clearcoatRoughness: 0.06, ...extra,
  });
}

/** O MDF preto acetinado (as bordas, o lado de dentro, a estrutura). */
export function acetinado(nome, cor = "#17181c", extra = {}) {
  return new THREE.MeshPhysicalMaterial({ name: nome, color: cor, roughness: 0.48, metalness: 0, clearcoat: 0.35, clearcoatRoughness: 0.32, ...extra });
}

/** O metal cromado (o moedeiro, o suporte da cesta, a chapa de parada). */
export function cromo(nome, cor = "#dfe3e8", extra = {}) {
  return new THREE.MeshStandardMaterial({ name: nome, color: cor, roughness: 0.14, metalness: 1, ...extra });
}

/** O que acende (o neon, o LED, a tela): a cor e a força da luz (emissiveStrength no .glb). */
export function aceso(nome, cor, forca = 2, extra = {}) {
  return new THREE.MeshStandardMaterial({ name: nome, color: "#000000", emissive: cor, emissiveIntensity: forca, roughness: 0.35, ...extra });
}

/* ---------------------------------------------------------------- texturas */

function imagem(src) {
  return new Promise((ok, falha) => {
    const i = new Image();
    i.onload = () => ok(i);
    i.onerror = () => falha(new Error(src));
    i.src = src;
  });
}

/**
 * A arte de uma peça: a versão HD (adesivos-hd/<peça>.webp) quando existe, senão a
 * da folha (adesivos/<peça>.png, ampliada com suavização); o lado maior até `lado`
 * px. Volta { textura, hd, w, h } (a textura em sRGB, com mipmaps, JPEG no .glb).
 */
export async function arte(pasta, peca, { lado = 2048, px = null, avisos = [] } = {}) {
  let fonte = null;
  let hd = true;
  try {
    fonte = await imagem(`${pasta}adesivos-hd/${peca}.webp?v=${Date.now()}`);
  } catch {
    hd = false;
    try {
      fonte = await imagem(`${pasta}adesivos/${peca}.png?v=${Date.now()}`);
    } catch {
      avisos.push(`${pasta}adesivos/${peca}.png não existe: a peça ficou cinza`);
    }
  }
  const [w0, h0] = fonte ? [fonte.naturalWidth, fonte.naturalHeight] : px || [256, 256];
  // com a HD (4x a folha, nítida), o lado pedido (2048 nas peças grandes: no máximo ~1,2x a
  // HD, sem perder a nitidez); sem ela, amplia com suavização até 2x a folha (como antes)
  const alvo = hd ? lado : Math.min(lado, 2 * Math.max(w0, h0));
  const k = alvo / Math.max(w0, h0);
  const c = document.createElement("canvas");
  c.width = Math.round(w0 * k);
  c.height = Math.round(h0 * k);
  const g = c.getContext("2d");
  if (fonte) {
    g.imageSmoothingQuality = "high";
    g.drawImage(fonte, 0, 0, c.width, c.height);
  } else {
    g.fillStyle = "#8a93a3";
    g.fillRect(0, 0, c.width, c.height);
  }
  if (!hd) avisos.push(`${peca}: sem a versão HD (rode ../ampliar_adesivos.py)`);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 16;
  t.userData.mimeType = "image/jpeg";
  return { textura: t, hd, w: c.width, h: c.height };
}

/* ---------------------------------------------------------------- formas */

/** O polígono no sentido anti-horário. */
export function antiHorario(pontos) {
  const p = pontos.map(([a, b]) => new THREE.Vector2(a, b));
  return THREE.ShapeUtils.isClockWise(p) ? pontos.slice().reverse() : pontos.slice();
}

/**
 * O polígono afastado `d` mm para DENTRO (d < 0: para fora), vértice a
 * vértice pela bissetriz (como o chanfro do ExtrudeGeometry): o adesivo do
 * tamanho da face plana de uma placa de borda arredondada.
 */
export function recuar(pontos, d) {
  const p = antiHorario(pontos);
  const n = p.length;
  return p.map(([x, y], i) => {
    const [xa, ya] = p[(i - 1 + n) % n];
    const [xb, yb] = p[(i + 1) % n];
    // as normais para dentro (à esquerda de cada aresta, no anti-horário)
    let [ux, uy] = [x - xa, y - ya];
    let L = Math.hypot(ux, uy) || 1;
    const n1 = [-uy / L, ux / L];
    [ux, uy] = [xb - x, yb - y];
    L = Math.hypot(ux, uy) || 1;
    const n2 = [-uy / L, ux / L];
    let [bx, by] = [n1[0] + n2[0], n1[1] + n2[1]];
    const Lb = Math.hypot(bx, by);
    if (Lb < 1e-6) return [x + n1[0] * d, y + n1[1] * d];
    [bx, by] = [bx / Lb, by / Lb];
    const cos = Math.max(0.35, bx * n1[0] + by * n1[1]);
    return [x + (bx * d) / cos, y + (by * d) / cos];
  });
}

/** Chaikin: o polígono fechado com as quinas arredondadas (`vezes` passadas). */
export function suavizar(pontos, vezes = 2) {
  let q = pontos;
  for (let k = 0; k < vezes; k++) {
    q = q.flatMap((p, i) => {
      const r = q[(i + 1) % q.length];
      return [[0.75 * p[0] + 0.25 * r[0], 0.75 * p[1] + 0.25 * r[1]], [0.25 * p[0] + 0.75 * r[0], 0.25 * p[1] + 0.75 * r[1]]];
    });
  }
  return q;
}

/** Tira os pontos a menos de `min` mm do anterior (o chanfro não faz bico em ponto repetido). */
export function limpar(pontos, min = 1.5) {
  const saida = [];
  for (const p of pontos) {
    const u = saida[saida.length - 1];
    if (!u || Math.hypot(p[0] - u[0], p[1] - u[1]) >= min) saida.push(p);
  }
  if (saida.length > 3 && Math.hypot(saida[0][0] - saida[saida.length - 1][0], saida[0][1] - saida[saida.length - 1][1]) < min) saida.pop();
  return saida;
}

export function forma(pontos, furos = []) {
  const s = new THREE.Shape(antiHorario(pontos).map(([a, b]) => new THREE.Vector2(a, b)));
  for (const f of furos) {
    const q = f.map(([a, b]) => new THREE.Vector2(a, b));
    if (!THREE.ShapeUtils.isClockWise(q)) q.reverse();
    s.holes.push(new THREE.Path(q));
  }
  return s;
}

/**
 * A placa de MDF de `espessura` mm com as bordas arredondadas (raio `raio`):
 * o contorno de fora é o dado (na metade da espessura) e as duas faces planas
 * ficam `raio` mm para dentro (onde vai o adesivo). A face da frente fica
 * PELE mm atrás do plano z = 0; a de trás, `espessura` atrás dela.
 */
export function placaArredondada(pontos, espessura, raio = 6, furos = []) {
  const r = Math.min(raio, espessura / 2 - 0.5);
  const g = new THREE.ExtrudeGeometry(forma(pontos, furos), {
    depth: espessura - 2 * r, bevelEnabled: true, bevelThickness: r, bevelSize: r, bevelOffset: -r, bevelSegments: 3, curveSegments: 4,
  });
  g.translate(0, 0, r - espessura - PELE);
  return g;
}

/** O adesivo plano: a forma; o uv pela posição dentro do retângulo `ret` [a0, b0, a1, b1] (a imagem inteira). */
export function adesivoPlano(pontos, ret, furos = [], v0 = 0, v1 = 1) {
  const g = new THREE.ShapeGeometry(forma(pontos, furos), 4);
  const pos = g.attributes.position;
  const uv = g.attributes.uv;
  for (let i = 0; i < pos.count; i++) {
    uv.setXY(i, (pos.getX(i) - ret[0]) / (ret[2] - ret[0]), v0 + ((v1 - v0) * (pos.getY(i) - ret[1])) / (ret[3] - ret[1]));
  }
  return g;
}

/* ---------------------------------------------------------------- luzes da máquina */

/** As cores do arco-íris da fita de LED (uma textura de 64 x 1: o uv de cada ponto escolhe a cor). */
export function texturaArcoIris() {
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 1;
  const g = c.getContext("2d");
  const cores = ["#ff2d55", "#ff8a00", "#ffe600", "#29ff5a", "#00e5ff", "#2f6bff", "#b44dff", "#ff2d55"];
  const grad = g.createLinearGradient(0, 0, 64, 0);
  cores.forEach((cor, i) => grad.addColorStop(i / (cores.length - 1), cor));
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 1);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  t.userData.mimeType = "image/png";
  return t;
}

/**
 * Os pontos de LED por um caminho 3D (mm): a cada `passo` mm, uma meia esfera de
 * raio `r` virada para `normal(t)` (a direção para fora do caminho), com o uv na
 * cor do arco-íris (a cor anda ao longo da fita). Volta { pontos, fita }.
 */
export function pontosDeLed(caminho, normal, { passo = 33, r = 4.5, largura = 10, ciclos = 3 } = {}) {
  const curva = new THREE.CurvePath();
  for (let i = 0; i < caminho.length - 1; i++) curva.add(new THREE.LineCurve3(caminho[i], caminho[i + 1]));
  const L = curva.getLength();
  const n = Math.max(2, Math.floor(L / passo));
  const pontos = [];
  const fita = [];
  const base = new THREE.SphereGeometry(r, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2);
  for (let k = 0; k <= n; k++) {
    const t = k / n;
    const p = curva.getPointAt(t);
    const tangente = curva.getTangentAt(t);
    const N = normal(p, tangente).normalize();
    const g = base.clone();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), N);
    g.applyMatrix4(new THREE.Matrix4().compose(p.clone().addScaledVector(N, 1.2), q, new THREE.Vector3(1, 1, 1)));
    const uv = g.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, ((t * ciclos) % 1) * 0.98 + 0.01, 0.5);
    pontos.push(g);
  }
  // a fita (a tira preta embaixo dos pontos): um quadrilátero por trecho
  const pos = [];
  for (let k = 0; k < n; k++) {
    const t0 = k / n, t1 = (k + 1) / n;
    const [p0, p1] = [curva.getPointAt(t0), curva.getPointAt(t1)];
    const [n0, n1] = [normal(p0, curva.getTangentAt(t0)).normalize(), normal(p1, curva.getTangentAt(t1)).normalize()];
    const [l0, l1] = [new THREE.Vector3().crossVectors(curva.getTangentAt(t0), n0).normalize(), new THREE.Vector3().crossVectors(curva.getTangentAt(t1), n1).normalize()];
    const v = (p, nn, l, s) => p.clone().addScaledVector(nn, 0.6).addScaledVector(l, (s * largura) / 2);
    const [a, b, c, d] = [v(p0, n0, l0, -1), v(p0, n0, l0, 1), v(p1, n1, l1, -1), v(p1, n1, l1, 1)];
    pos.push(...a.toArray(), ...c.toArray(), ...b.toArray(), ...b.toArray(), ...c.toArray(), ...d.toArray());
  }
  const gf = new THREE.BufferGeometry();
  gf.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  gf.computeVertexNormals();
  fita.push(gf);
  return { pontos, fita };
}

/** O neon flex: um tubo macio (Catmull-Rom) pelo caminho 3D (mm), fechado ou não. */
export function tuboNeon(pontos, r = 6, fechado = true) {
  const curva = new THREE.CatmullRomCurve3(pontos, fechado, "centripetal");
  const segmentos = Math.max(16, Math.round(curva.getLength() / 6));
  return new THREE.TubeGeometry(curva, segmentos, r, 8, fechado);
}

/* ---------------------------------------------------------------- montagem e vistas */

/**
 * Junta as geometrias de cada material numa malha (com o nome do material, que
 * fica estável para quem importa o .glb no Blender), passa para metros,
 * centraliza e assenta no chão. `pecas`: Map nome -> { material, geometrias }.
 */
export function montarFinal(pecas, nomeRaiz, { mergeGeometries, mergeVertices }) {
  const raiz = new THREE.Group();
  raiz.name = nomeRaiz;
  const mm = new THREE.Matrix4().makeScale(0.001, 0.001, 0.001);
  for (const [nome, { material: mat, geometrias, malha }] of pecas) {
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
    const m = new THREE.Mesh(g, mat);
    m.name = malha || nome;
    raiz.add(m);
  }
  const caixa = new THREE.Box3().setFromObject(raiz);
  const centro = caixa.getCenter(new THREE.Vector3());
  raiz.children.forEach((m) => m.geometry.translate(-centro.x, -caixa.min.y, -centro.z));
  return raiz;
}

/** As vistas de conferência: a luz de ambiente do site (RoomEnvironment), o chão com a sombra macia. */
export function vistas(raiz, { largura = 1200, altura = 800 } = {}) {
  const cena = new THREE.Scene();
  cena.add(raiz);
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(largura, altura);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  document.body.append(renderer.domElement);
  const pmrem = new THREE.PMREMGenerator(renderer);
  cena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  cena.environmentIntensity = 0.9;
  const sol = new THREE.DirectionalLight("#ffffff", 1.6);
  sol.position.set(3, 8, 5);
  sol.castShadow = true;
  sol.shadow.mapSize.set(1024, 1024);
  Object.assign(sol.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 1, far: 30 });
  sol.shadow.bias = -0.0004;
  sol.shadow.radius = 4;
  cena.add(sol);
  raiz.traverse((o) => { if (o.isMesh) { o.castShadow = !/rede|neon|led/.test(o.name); o.receiveShadow = true; } });
  const chao = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.ShadowMaterial({ opacity: 0.3 }));
  chao.rotation.x = -Math.PI / 2;
  chao.receiveShadow = true;
  cena.add(chao);
  const camera = new THREE.PerspectiveCamera(34, largura / altura, 0.05, 100);
  window.ver = (x, y, z, alvo = [0, 1, 0], fundo = "#0b1a3a", fov = 34) => {
    cena.background = new THREE.Color(fundo);
    camera.fov = fov;
    camera.updateProjectionMatrix();
    camera.position.set(x, y, z);
    camera.lookAt(...alvo);
    renderer.render(cena, camera);
    return renderer.domElement.toDataURL("image/jpeg", 0.92);
  };
  return { cena, renderer, camera };
}

/** O .glb (base64): os adesivos em JPEG na QUALIDADE_JPEG (o exportador usa o toBlob sem qualidade). */
export async function exportar(raiz, GLTFExporter, qualidade = QUALIDADE_JPEG) {
  const toBlob = HTMLCanvasElement.prototype.toBlob;
  HTMLCanvasElement.prototype.toBlob = function (feito, tipo, q) {
    return toBlob.call(this, feito, tipo, tipo === "image/jpeg" ? qualidade : q);
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
}
