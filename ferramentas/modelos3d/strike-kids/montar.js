// Monta o Strike Kids (o boliche kids) em three.js e exporta um .glb (LEIA-ME V10, seção 92).
//
// A máquina de verdade, como nas fotos do cliente: um gabinete cheio e firme,
// as laterais de MDF grosso (25 mm) com as bordas arredondadas, que descem da
// coluna da tela numa curva só até a pista e terminam na frente com o canto
// redondo; a coluna com o monitor em pé (o jogo aceso na tela, a moldura preta,
// a caixinha branca da câmera em cima e o logotipo da Lazer & Sport embaixo);
// a testeira em forma de nuvem em cima da coluna, com o neon flex vermelho em
// volta do logotipo; a fita de LED de pontos coloridos por toda a borda de cima
// das laterais (e subindo pela frente da coluna); a pista de madeira brilhante
// com as setas; o bolsão das bolas na frente, à direita, com as duas bolas; a
// frente com o logotipo no neon azul, o botão vermelho e a Lazer & Sport.
//
// AS ARTES são as de verdade, as do .glb que a fábrica mandou (extrair_do_glb.py:
// adesivos/<peça>.png e o contorno de cada peça recortada, no formas.json),
// ampliadas 4x com nitidez (../ampliar_adesivos.py: adesivos-hd/). O caminho do
// neon é o contorno do logotipo em cada arte (contornos_neon.py).
//
// AS MEDIDAS são as do cadastro: 2,07 m de altura, 0,74 m de largura e 1,91 m de
// comprimento. As laterais têm o contorno e a proporção da arte delas (1,91 m x
// 1,65 m); a testeira, a da arte (0,70 x 0,49 m), presa na frente do alto da
// coluna (sem entrar nas laterais nem no teto: nada se cruza).
//
// Coordenadas em mm: x na largura (da esquerda para a direita de quem joga), y
// para cima, z no comprimento (o jogador, a frente, em +z; a tela em -z). No fim
// tudo vira metros, centralizado e no chão. Os nomes das malhas (e dos
// materiais, iguais) são os do .glb de antes, para as cores do site (cores3d.js:
// a tela, a pista, as bolas, o bolsão e os LEDs nunca se tingem) e para quem
// importa no Blender (o README tem a lista).
import * as THREE from "three";
import { GLTFExporter } from "/vendor/three/GLTFExporter.js";
import { mergeGeometries, mergeVertices } from "/vendor/three/BufferGeometryUtils.js";
import * as C from "../comum3d.js";

const PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const FORMAS = await (await fetch(`formas.json?v=${Date.now()}`)).json();
const PELE = C.PELE;
const avisos = [];
const limite = (v, a, b) => Math.min(b, Math.max(a, v));

// ---------- as medidas (mm) ----------
// As do cadastro são a máquina inteira, com o que sobressai: o neon das laterais
// (o tubo de 8 mm encostado no adesivo) e o botão vermelho da frente. O gabinete
// fica dentro delas.
const ALT = 2070; // o alto da testeira
const R_NEON = 5; // o tubo do neon flex (10 mm), encostado no adesivo
const NEON_FORA = R_NEON + 0.5; // o eixo do tubo, fora do adesivo
const BOTAO_FORA = 16; // o botão vermelho (o aro e a cúpula) sobressai da frente
const LARG = 740 - 2 * (NEON_FORA + R_NEON); // ~723: de um adesivo de fora das laterais ao outro
const COMP = 1910 - BOTAO_FORA; // 1894: da chapa das costas à frente
const XF = LARG / 2; // o adesivo de fora das laterais
const ESP_L = 25; // o MDF das laterais
const ESP = 18; // o MDF das outras peças
const RAIO = 8; // o raio das bordas fresadas
const XI = XF - PELE - ESP_L; // 344: a face de dentro das laterais
const XP = XI - 0.5; // as peças entre as laterais (meio milímetro de folga)
const ZT = -1910 / 2; // as costas
const ZF = ZT + COMP; // a frente (o botão vai até 1910)
const [LW, LH] = FORMAS["lateral-esquerda"].px;
const HL = (COMP * LH) / LW; // ~1648: a altura das laterais, na proporção da arte
// a frente (entre as laterais), na proporção da arte; o alto dela é o nível da pista
const [FW, FH] = FORMAS.frente.px;
const S_F = (2 * XP) / FW; // mm por px da arte da frente
const V_BAIXO_F = Math.max(...FORMAS.frente.contorno.map(([, v]) => v)); // o pé da peça na arte (~0,968)
const Y_FRENTE = 10; // a frente começa 10 mm acima do chão (os pés)
const PISTA_Y = Y_FRENTE + V_BAIXO_F * FH * S_F; // ~332: a pista, rente ao alto da frente
const Z_FRENTE_DENTRO = ZF - PELE - ESP_L; // a face de dentro da frente
// o bolsão: o recorte da arte da frente (a parte baixa, à direita) e o da pista
const U_BOLSAO = Math.max(...FORMAS.frente.contorno.filter(([, v]) => v > 0.3 && v < 0.55).map(([u]) => u)); // ~0,64: a parede do recorte
const V_BOLSAO = Math.min(...FORMAS.frente.contorno.filter(([u]) => u > 0.9).map(([, v]) => v)); // ~0,656
const X_BOLSAO = -XP + U_BOLSAO * 2 * XP; // ~96
const Y_BEIRA = Y_FRENTE + (V_BAIXO_F - V_BOLSAO) * FH * S_F; // ~114: a beira do bolsão
const Z_BOLSAO = 545; // o fundo do bolsão
const Y_PISO_BOLSAO = 40;
const R_BOLA = 85;
// a coluna: o painel da tela, inclinado como a frente das laterais (13,8°), e a placa embaixo dele
const INCL = Math.atan2(228, 930);
const PAINEL = { y0: 661, z0: -454, largura: 2 * XP };
PAINEL.comprimento = (PAINEL.largura * FORMAS["painel-tela"].px[1]) / FORMAS["painel-tela"].px[0]; // ~986
const SOBE = V(0, Math.cos(INCL), -Math.sin(INCL)); // ao longo do painel, para cima
PAINEL.topo = V(0, PAINEL.y0, PAINEL.z0).addScaledVector(SOBE, PAINEL.comprimento);
// o buraco do monitor na arte do painel (o retângulo escuro: 16:9 em pé)
const BURACO = { u0: 0.1733, u1: 0.8267, v0: 0.096, v1: 0.904 };
const TELA = { w: 405, h: 720 }; // a tela de ~32" em pé (9:16), dentro da moldura
// a testeira: a arte em 0,70 m de largura, o alto em 2,07 m; a parte de trás
// fica na frente da borda das laterais (nada se cruza)
const [TW, TH] = FORMAS.testeira.px;
const T_LARG = 700;
const T_ALT = (T_LARG * TH) / TW; // ~494
const T_ESP = 30;
const T_Y = ALT - T_ALT;

// ---------- materiais e o acúmulo de peças por material ----------
const pecas = new Map(); // nome -> { material, geometrias: [] }
function material(nome, criar) {
  if (!pecas.has(nome)) pecas.set(nome, { material: criar(nome), geometrias: [] });
  return nome;
}
function por(nome, geometria, matriz) {
  if (matriz) geometria.applyMatrix4(matriz);
  pecas.get(nome).geometrias.push(geometria);
}
// a base de uma face: a origem (na superfície do adesivo) e os eixos de quem olha
// DE FORA (U para a direita, W para cima); a normal (U x W) aponta para fora
function base(origem, U, W) {
  const N = new THREE.Vector3().crossVectors(U, W).normalize();
  return {
    origem, U, W, N, matriz: () => new THREE.Matrix4().makeBasis(U, W, N).setPosition(origem),
    ponto: (a, b, n = 0) => origem.clone().addScaledVector(U, a).addScaledVector(W, b).addScaledVector(N, n),
  };
}
function caixa(nome, x0, x1, y0, y1, z0, z1) {
  por(nome, new THREE.BoxGeometry(Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0)),
    new THREE.Matrix4().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
}
const retangulo = (a0, b0, a1, b1) => [[a0, b0], [a1, b0], [a1, b1], [a0, b1]];

const M = {
  mdf: material("estrutura_mdf", (n) => C.acetinado(n, "#15161a")),
  bolsao: material("bolsao", (n) => C.acetinado(n, "#1d2027", { roughness: 0.6, clearcoat: 0.1 })),
  moldura: material("moldura_monitor", (n) => C.acetinado(n, "#09090b", { roughness: 0.22, clearcoat: 0.9, clearcoatRoughness: 0.05 })),
  camera: material("camera_sensor", (n) => C.acetinado(n, "#f4f6f9", { roughness: 0.35, clearcoat: 0.6 })),
  lente: material("lente", (n) => C.acetinado(n, "#050608", { roughness: 0.08, clearcoat: 1, clearcoatRoughness: 0.02 })),
  aro: material("botao_aro", (n) => C.acetinado(n, "#0c0c0e", { roughness: 0.3 })),
  botao: material("botao_vermelho", (n) => new THREE.MeshPhysicalMaterial({
    name: n, color: "#e0101c", roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.04, emissive: "#ff1a24", emissiveIntensity: 0.35,
  })),
  // o neon flex: o silicone leitoso aceso (a cor dele mesmo de dia, e o brilho)
  neonVermelho: material("neon_vermelho", (n) => C.aceso(n, "#ff0a24", 1.8, { color: "#ff1a2e", roughness: 0.6 })),
  neonAzul: material("neon_azul", (n) => C.aceso(n, "#0a5cff", 2.2, { color: "#1f6bff", roughness: 0.6 })),
  ledFita: material("led_fita", (n) => C.acetinado(n, "#101114", { roughness: 0.5, clearcoat: 0 })),
  led: material("led_pontos", (n) => {
    const t = C.texturaArcoIris();
    return new THREE.MeshStandardMaterial({ name: n, color: "#ffffff", map: t, emissive: "#ffffff", emissiveMap: t, emissiveIntensity: 1.5, roughness: 0.5 });
  }),
};

// o lado maior de cada arte dentro do .glb (px): a HD inteira (4x a arte da fábrica), até 2048
const RESOLUCAO = {
  "lateral-esquerda": 2048, "lateral-direita": 2048, pista: 2048, "tela-do-jogo": 2048, "acabamento-esquerda": 2048,
  "acabamento-direita": 2048, "painel-tela": 1536, testeira: 1024, frente: 1024,
};

// um adesivo (vinil laminado) com a arte da peça
async function vinil(nomeMalha, peca, extra = {}) {
  const { textura } = await C.arte("", peca, { lado: RESOLUCAO[peca] || 1024, avisos });
  return material(nomeMalha, (n) => C.vinil(n, textura, extra));
}

/* ======================================================================
   1. AS LATERAIS: o contorno da arte, em MDF de 25 mm com a borda
   arredondada; o adesivo de fora do tamanho da face plana; por dentro, a
   faixa do acabamento (o arco escuro com as lâmpadas) acima da pista; o
   neon vermelho em volta do logotipo; a fita de LED pela borda de cima.
   ====================================================================== */
for (const lado of ["esquerda", "direita"]) {
  const s = lado === "esquerda" ? -1 : 1;
  // de fora: na esquerda (-x) as costas ficam à esquerda da arte; na direita, à direita
  const b = s < 0 ? base(V(-XF, 0, ZT), V(0, 0, 1), V(0, 1, 0)) : base(V(XF, 0, ZF), V(0, 0, -1), V(0, 1, 0));
  const f = FORMAS[`lateral-${lado}`];
  const doUv = ([u, v]) => [limite(u, 0, 1) * COMP, (1 - limite(v, 0, 1)) * HL];
  const contorno = f.contorno.map(doUv);
  const pts = C.limpar(contorno);
  por(M.mdf, C.placaArredondada(pts, ESP_L, RAIO), b.matriz());
  const m = await vinil(`lateral_${lado}_arte`, `lateral-${lado}`);
  por(m, C.adesivoPlano(C.recuar(pts, RAIO + 0.5), [0, 0, COMP, HL]), b.matriz());
  // o neon flex em volta do logotipo, 6 mm fora do adesivo
  if (f.neon) por(M.neonVermelho, C.tuboNeon(f.neon.map(doUv).map(([a, y]) => b.ponto(a, y, NEON_FORA)), R_NEON));
  // a fita de LED: a borda de cima inteira, do alto da frente até o alto das costas,
  // no meio da espessura da chapa, com os pontos virados para fora do contorno
  {
    const costas = s < 0 ? (u) => u < 0.03 : (u) => u > 0.97;
    let i0 = f.contorno.findIndex(([u, v]) => v < 0.7 && !costas(u));
    const trecho = [];
    for (let k = i0; trecho.length < f.contorno.length; k = (k + 1) % f.contorno.length) {
      trecho.push(contorno[k]);
      if (costas(f.contorno[k][0]) && f.contorno[k][1] < 0.03) break;
    }
    // a linha macia (Chaikin numa linha aberta): sem quinas na fita
    let linha = trecho;
    for (let k = 0; k < 2; k++) {
      linha = [linha[0], ...linha.slice(0, -1).flatMap((p, i) => {
        const r = linha[i + 1];
        return [[0.75 * p[0] + 0.25 * r[0], 0.75 * p[1] + 0.25 * r[1]], [0.25 * p[0] + 0.75 * r[0], 0.25 * p[1] + 0.75 * r[1]]];
      }), linha[linha.length - 1]];
    }
    const meio = -(PELE + ESP_L / 2);
    const caminho = linha.map(([a, y]) => b.ponto(a, y, meio));
    // o sentido do contorno no plano da face: para fora é tangente x N (anti-horário) ou o contrário
    const area = pts.reduce((acc, [a, y], k) => acc + a * pts[(k + 1) % pts.length][1] - pts[(k + 1) % pts.length][0] * y, 0);
    const sinal = area > 0 ? 1 : -1;
    const { pontos, fita } = C.pontosDeLed(caminho, (p, t) => t.clone().cross(b.N).multiplyScalar(sinal), { passo: 33, r: 5.5, largura: 10 });
    pontos.forEach((g) => por(M.led, g));
    fita.forEach((g) => por(M.ledFita, g));
  }
  // por dentro: a faixa do acabamento, da base da coluna até a frente, acima da pista
  {
    const L = Z_FRENTE_DENTRO - PAINEL.z0;
    const [AW, AH] = FORMAS[`acabamento-${lado}`].px;
    const H = (L * AH) / AW;
    // (como no .glb da fábrica: na esquerda a arte anda das costas para a frente; na direita, ao contrário)
    const bi = s < 0
      ? base(V(-XI + 0.5, PISTA_Y, Z_FRENTE_DENTRO), V(0, 0, -1), V(0, 1, 0))
      : base(V(XI - 0.5, PISTA_Y, PAINEL.z0), V(0, 0, 1), V(0, 1, 0));
    const ma = await vinil(s < 0 ? "acab_esq" : "acab_dir", `acabamento-${lado}`);
    por(ma, C.adesivoPlano(retangulo(0, 0, L, H), [L, 0, 0, H]), bi.matriz());
  }
}

/* ======================================================================
   2. A PISTA: a madeira com as setas (brilhante), com o recorte do bolsão na
   frente, à direita; o bolsão (o piso, a divisória e o fundo) e as duas bolas
   ====================================================================== */
{
  const L = Z_FRENTE_DENTRO - PAINEL.z0;
  const b = base(V(-XP, PISTA_Y, Z_FRENTE_DENTRO), V(1, 0, 0), V(0, 0, -1));
  const aB = X_BOLSAO + XP; // onde o bolsão começa, na largura
  const bB = Z_FRENTE_DENTRO - Z_BOLSAO; // até onde ele vai, no comprimento
  const pts = [[0, 0], [aB, 0], [aB, bB], [2 * XP, bB], [2 * XP, L], [0, L]];
  const laje = new THREE.ExtrudeGeometry(C.forma(pts), { depth: ESP_L, bevelEnabled: false });
  laje.translate(0, 0, -ESP_L - PELE);
  por(M.mdf, laje, b.matriz());
  const m = await vinil("pista", "pista", { roughness: 0.32, clearcoatRoughness: 0.04 });
  por(m, C.adesivoPlano(pts, [0, 0, 2 * XP, L]), b.matriz());
  // o bolsão
  const yTopo = PISTA_Y - ESP_L - PELE;
  caixa(M.bolsao, X_BOLSAO, XP, Y_PISO_BOLSAO - ESP, Y_PISO_BOLSAO, Z_BOLSAO, Z_FRENTE_DENTRO);
  caixa(M.bolsao, X_BOLSAO - ESP, X_BOLSAO, Y_PISO_BOLSAO - ESP, yTopo, Z_BOLSAO - ESP, Z_FRENTE_DENTRO);
  caixa(M.bolsao, X_BOLSAO, XP, Y_PISO_BOLSAO - ESP, yTopo, Z_BOLSAO - ESP, Z_BOLSAO);
  // as bolas de borracha (de gomos, como as de futebol): uma vermelha e preta, a outra colorida
  const gomos = (fundo, cores) => {
    const c = document.createElement("canvas");
    c.width = 512;
    c.height = 256;
    const g = c.getContext("2d");
    g.fillStyle = fundo;
    g.fillRect(0, 0, 512, 256);
    // os 12 pentágonos do icosaedro (latitude, longitude), deformados como no mapa
    const vertices = [[90, 0], [-90, 0]];
    for (let i = 0; i < 5; i++) { vertices.push([26.57, i * 72]); vertices.push([-26.57, i * 72 + 36]); }
    vertices.forEach(([lat, lon], i) => {
      const x = (lon / 360) * 512, y = ((90 - lat) / 180) * 256;
      const esticar = 1 / Math.max(0.25, Math.cos((lat * PI) / 180));
      g.fillStyle = cores[i % cores.length];
      for (const dx of [-512, 0, 512]) {
        g.beginPath();
        for (let k = 0; k < 5; k++) {
          const a = (k / 5) * 2 * PI - PI / 2;
          g.lineTo(x + dx + Math.cos(a) * 30 * esticar, y + Math.sin(a) * 30);
        }
        g.closePath();
        g.fill();
      }
    });
    g.strokeStyle = "rgba(0,0,0,.35)";
    g.lineWidth = 2;
    for (let y = 0; y <= 256; y += 64) { g.beginPath(); g.moveTo(0, y); g.lineTo(512, y); g.stroke(); }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.userData.mimeType = "image/jpeg";
    return t;
  };
  const bolas = [
    ["bola_0", gomos("#d8141e", ["#111111"]), 640],
    ["bola_1", gomos("#ffd21a", ["#e01820", "#1748d8", "#111111"]), 830],
  ];
  for (const [nome, textura, z] of bolas) {
    const mb = material(nome, (n) => new THREE.MeshPhysicalMaterial({ name: n, map: textura, roughness: 0.45, clearcoat: 0.6, clearcoatRoughness: 0.18 }));
    const g = new THREE.SphereGeometry(R_BOLA, 40, 24);
    g.rotateZ(z > 700 ? 0.6 : -0.4);
    por(mb, g, new THREE.Matrix4().makeTranslation((X_BOLSAO + XP) / 2, Y_PISO_BOLSAO + R_BOLA, z));
  }
}

/* ======================================================================
   3. A FRENTE: a arte (com o recorte do bolsão), em MDF de 25 mm com a borda
   arredondada; o neon azul em volta do logotipo e o botão vermelho
   ====================================================================== */
{
  const b = base(V(-XP, Y_FRENTE, ZF), V(1, 0, 0), V(0, 1, 0));
  const doUv = ([u, v]) => [limite(u, 0, 1) * 2 * XP, (V_BAIXO_F - v) * FH * S_F];
  const pts = C.limpar(FORMAS.frente.contorno.map(doUv));
  por(M.mdf, C.placaArredondada(pts, ESP_L, RAIO), b.matriz());
  const m = await vinil("frente_arte", "frente");
  por(m, C.adesivoPlano(C.recuar(pts, RAIO + 0.5), [0, (V_BAIXO_F - 1) * FH * S_F, 2 * XP, V_BAIXO_F * FH * S_F]), b.matriz());
  if (FORMAS.frente.neon) por(M.neonAzul, C.tuboNeon(FORMAS.frente.neon.map(doUv).map(([a, y]) => b.ponto(a, y, NEON_FORA)), R_NEON));
  // o botão vermelho: no círculo branco da arte, à esquerda do logotipo
  const [a, y] = doUv([0.104, 0.362]);
  const centro = b.ponto(a, y, 0);
  const aro = new THREE.CylinderGeometry(38, 40, 6, 40);
  aro.rotateX(PI / 2);
  por(M.aro, aro, new THREE.Matrix4().makeTranslation(centro.x, centro.y, centro.z + 3));
  const cupula = new THREE.SphereGeometry(30, 32, 12, 0, 2 * PI, 0, PI / 2);
  cupula.scale(1, (BOTAO_FORA - 6) / 30, 1);
  cupula.rotateX(PI / 2);
  por(M.botao, cupula, new THREE.Matrix4().makeTranslation(centro.x, centro.y, centro.z + 6));
}

/* ======================================================================
   4. A COLUNA: o painel da tela (a arte com o buraco do monitor), inclinado
   como a frente das laterais; o monitor em pé (a moldura preta e o jogo
   aceso), a câmera em cima; a placa embaixo do painel, o teto e as costas
   ====================================================================== */
{
  const { largura: W, comprimento: Lp } = PAINEL;
  const b = base(V(-XP, PAINEL.y0, PAINEL.z0), V(1, 0, 0), SOBE);
  const furo = [[BURACO.u0 * W, (1 - BURACO.v1) * Lp], [BURACO.u1 * W, (1 - BURACO.v1) * Lp], [BURACO.u1 * W, (1 - BURACO.v0) * Lp], [BURACO.u0 * W, (1 - BURACO.v0) * Lp]];
  const pts = retangulo(0, 0, W, Lp);
  por(M.mdf, C.placaArredondada(pts, ESP, 4, [furo.slice().reverse()]), b.matriz());
  const m = await vinil("painel_tela", "painel-tela");
  por(m, C.adesivoPlano(C.recuar(pts, 4.5), [0, 0, W, Lp], [C.recuar(furo, -4.5).slice().reverse()]), b.matriz());
  // o monitor: a moldura (preta, brilhante) do tamanho do buraco, 5 mm para dentro, e a tela acesa
  const [a0, b0, a1, b1] = [furo[0][0], furo[0][1], furo[2][0], furo[2][1]];
  const meio = b.ponto((a0 + a1) / 2, (b0 + b1) / 2, 0);
  const giro = new THREE.Matrix4().makeBasis(b.U, b.W, b.N);
  const moldura = new THREE.BoxGeometry(a1 - a0 - 3, b1 - b0 - 3, 60);
  moldura.translate(0, 0, -6 - 30);
  por(M.moldura, moldura, giro.clone().setPosition(meio));
  const { textura } = await C.arte("", "tela-do-jogo", { lado: RESOLUCAO["tela-do-jogo"], avisos });
  const mt = material("monitor", (n) => new THREE.MeshPhysicalMaterial({
    name: n, color: "#0b0c0e", emissive: "#ffffff", emissiveMap: textura, emissiveIntensity: 1.0,
    roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.03,
  }));
  const tela = new THREE.PlaneGeometry(TELA.w, TELA.h);
  tela.translate(0, 0, -5.4);
  por(mt, tela, giro.clone().setPosition(meio));
  // a câmera que tira a foto do jogador: a caixinha branca centrada em cima do monitor
  const cam = b.ponto(W / 2, b1 + 30, 0);
  const caixinha = new THREE.BoxGeometry(64, 40, 30);
  caixinha.translate(0, 0, 15);
  por(M.camera, caixinha, giro.clone().setPosition(cam));
  const lente = new THREE.CylinderGeometry(9, 9, 3, 24);
  lente.rotateX(PI / 2);
  lente.translate(0, 0, 31.5);
  por(M.lente, lente, giro.clone().setPosition(cam));
  // a placa embaixo do painel (o fim da pista), o teto e as costas, entre as laterais
  caixa(M.mdf, -XP, XP, PISTA_Y - ESP_L - PELE, PAINEL.y0, PAINEL.z0 - ESP, PAINEL.z0);
  const yTeto = PAINEL.topo.y + 2;
  caixa(M.mdf, -XP, XP, yTeto, yTeto + ESP, ZT + ESP, PAINEL.topo.z + 3);
  caixa(M.mdf, -XP, XP, Y_FRENTE, yTeto, ZT, ZT + ESP);
  // os dois suportes da testeira, em cima do teto, até as costas dela
  for (const x of [-250, 250]) caixa(M.mdf, x - 20, x + 20, yTeto + ESP, yTeto + ESP + 18, PAINEL.topo.z - 20, ZT_TESTEIRA() - T_ESP - PELE);
}
function ZT_TESTEIRA() {
  // a frente da testeira: a parte de trás dela fica 4 mm na frente da borda das laterais,
  // na altura do pé da testeira (onde a borda vem mais para a frente)
  const f = FORMAS["lateral-esquerda"].contorno;
  const v = 1 - T_Y / HL;
  let u = 0;
  for (let i = 0; i < f.length; i++) {
    const [ua, va] = f[i];
    const [ub, vb] = f[(i + 1) % f.length];
    if ((va - v) * (vb - v) <= 0 && va !== vb && ua < 0.5 && ub < 0.5) u = Math.max(u, ua + ((v - va) * (ub - ua)) / (vb - va));
  }
  return ZT + u * COMP + 4 + T_ESP + PELE;
}

/* ======================================================================
   5. A TESTEIRA: a nuvem da arte, em MDF de 30 mm com a borda arredondada,
   presa na frente do alto da coluna; o neon vermelho em volta do logotipo
   ====================================================================== */
{
  const z = ZT_TESTEIRA();
  const b = base(V(-T_LARG / 2, T_Y, z), V(1, 0, 0), V(0, 1, 0));
  const doUv = ([u, v]) => [limite(u, 0, 1) * T_LARG, (1 - limite(v, 0, 1)) * T_ALT];
  const pts = C.limpar(FORMAS.testeira.contorno.map(doUv));
  por(M.mdf, C.placaArredondada(pts, T_ESP, RAIO), b.matriz());
  const m = await vinil("testeira_arte", "testeira");
  por(m, C.adesivoPlano(C.recuar(pts, RAIO + 0.5), [0, 0, T_LARG, T_ALT]), b.matriz());
  // o neon da testeira é o que a própria arte marca (a linha fina vermelho-escura
  // impressa a ~4 cm da borda da nuvem, de um pé ao outro por cima): aqui, o
  // contorno da peça 40 mm para dentro, aberto embaixo
  const anel = C.recuar(pts, 40);
  const n = anel.length;
  const embaixo = anel.map(([, y]) => y < 45);
  const ini = anel.findIndex((_, k) => !embaixo[k] && embaixo[(k - 1 + n) % n]);
  const linha = [];
  for (let k = 0; k < n; k++) {
    const i = (ini + k) % n;
    if (embaixo[i]) break;
    linha.push(anel[i]);
  }
  por(M.neonVermelho, C.tuboNeon(linha.map(([a, y]) => b.ponto(a, y, NEON_FORA)), R_NEON, false));
}

/* ======================================================================
   MONTAGEM FINAL, as vistas de conferência e a exportação
   ====================================================================== */
const raiz = C.montarFinal(pecas, "strike-kids", { mergeGeometries, mergeVertices });
const final = new THREE.Box3().setFromObject(raiz);
window.medidas = final.getSize(new THREE.Vector3()).toArray().map((v) => Math.round(v * 1000) / 1000);
window.triangulos = raiz.children.reduce((s, m) => s + (m.geometry.index ? m.geometry.index.count / 3 : m.geometry.attributes.position.count / 3), 0);
window.avisos = avisos;
window.escala = {
  laterais_mm: [COMP, Math.round(HL)], pista: Math.round(PISTA_Y), beira_do_bolsao: Math.round(Y_BEIRA), bolsao_x: Math.round(X_BOLSAO),
  painel: { comprimento: Math.round(PAINEL.comprimento), topo: PAINEL.topo.toArray().map(Math.round) },
  testeira: { largura: T_LARG, altura: Math.round(T_ALT), pe: Math.round(T_Y), frente_z: Math.round(ZT_TESTEIRA()) },
};
C.vistas(raiz);
window.vistasDeConferencia = {
  frente34: [[2.4, 1.9, 3.4], [0, 1.0, 0], 34],
  esquerda: [[-4.6, 1.3, 0.1], [0, 1.0, 0], 34],
  direita: [[4.6, 1.3, -0.1], [0, 1.0, 0], 34],
  frente: [[0, 1.3, 4.8], [0, 1.0, 0], 34],
  costas: [[-2.2, 2.2, -3.8], [0, 1.0, 0], 34],
  jogador: [[0.1, 1.45, 1.9], [0, 0.9, -0.6], 50],
  bolsao: [[0.9, 0.9, 1.6], [0.2, 0.3, 0.75], 34],
  testeira: [[0.8, 2.1, 0.9], [0, 1.75, -0.6], 40],
};
window.exportar = () => C.exportar(raiz, GLTFExporter);
window.pronto = true;
