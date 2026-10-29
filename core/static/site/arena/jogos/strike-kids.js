/* ======================================================================
   STRIKE KIDS 3D — a prévia do boliche infantil do Bob e da Mia.

   O jogo de verdade (Godot 4, versão 5.6, e a edição OpenGL ES 2.0) é todo
   em 3D: Bob e Mia arremessam na pista de madeira com neon, setas
   arco-íris e trilha de estrelas, para-choques de doce, o portal da
   máquina de pinos (arco de raios, letreiro STRIKE KIDS, cortina de
   estrelas), pinos com carinha e os 4 cenários sorteados (Parque de
   Diversões, Viagem ao Espaço, Fundo do Mar, Selva dos Dinos). Esta prévia
   refaz o jogo com o three.js, com as MESMAS peças e contas:

     * os modelos 3D saem do modelador da empresa (tools/modelos/*.py) e
       são simplificados e quantizados (strike-kids/modelos.bin + .json,
       cenario_<fase>, roupa_<fase>);
     * a pista usa a textura ASSADA da edição OpenGL ES 2.0
       (pista_pronta.png) e os shaders são os dela (luz por vértice, a
       mesma curva de tela do Godot 4: "tela" e "tela_g4");
     * personagem.gd e animacoes.gd: poses-chave com curva PCHIP, troca de
       animação por inércia, IK de duas juntas nas pernas com o pé travado
       no chão, rosto com expressões, piscar, olhar para a bola e rabinho
       que abana;
     * jogada.gd: as 5 jogadas dos sensores (Z X C V B) e a tabela de
       jogadas calibrada; a queda dos pinos é uma física leve feita aqui
       (os pinos batem na bola, uns nos outros, nas paredes e no fosso);
     * principal.gd, camera_cine.gd, placar.gd, hud.gd: o ritmo da partida
       (30% mais rápido que o tempo real), os planos de câmera, o replay do
       strike em câmera lenta, a máquina de pinos e as telas.

   A máquina de verdade tem 5 sensores: a criança rola a bola e o sensor
   que ela cruza decide a jogada. Aqui a pessoa ARRASTA a bola e solta: a
   direção do gesto escolhe o sensor (esquerda, meio-esquerda, centro,
   meio-direita, direita). As teclas Z X C V B são os 5 botões da placa
   Zero Delay; Espaço e Enter são o START.

   Contrato do console (site/arena/console.js): criar(api) devolve a
   partida. O 3D é desenhado num canvas WebGL próprio (fora da página) e
   copiado para o canvas 2D do console a cada quadro; o placar e os
   letreiros são desenhados por cima, em 2D.
   ====================================================================== */

const PASTA = new URL("./strike-kids/", import.meta.url);
const URL_THREE = new URL("../../../vendor/three/three.module.min.js", import.meta.url).href;

const LARGURA = 540;
const ALTURA = 960;
// a máquina é 1080 x 1920 (em pé): a unidade "u" do hud.gd vale meia
// unidade aqui (u = lado menor / 1080)
const U = LARGURA / 1080;
const TAU = Math.PI * 2;
const GRAU = Math.PI / 180;

// ------------------------------------------------------------------ medidas (scripts/mundo.gd)
const MEIA_LARGURA = 0.675;
const CANALETA = 0.25;
const Z_PINO1 = -10.5;
const ESPACO_PINOS = 0.38;
const FILEIRA = 0.329;
const Z_FIM_DECK = -11.95;
const Z_FUNDO = -13.7;
const N_BUMPERS = 10;
const Y_BOCA = 0.28;
const LARGURA_BOCA = 1.5;
const Y_CHAO_FOSSO = -0.14;
const N_TIRAS = 7;
const RETORNO = [2.35, 0, 5.2];
const ALTURA_PODIO = 0.152;
const BALAO_POS = [-1.75, 2.2, Z_PINO1 + 3.0];
// proporção da arte da marca Lazer & Sport (ui/marca/lazer_sport.png, 2560 x 1698)
const ASPECTO_MARCA = 1698 / 2560;

// ------------------------------------------------------------------ partida (principal.gd, Ajustes.gd)
const Z_INICIO = 3.15;
const X_MAO = 0.28;              // a mão direita fica 0,28 m à direita do corpo
const POS_PISTA = [0.0, 1.05, 2.2];
const ALVO_PISTA = [0.0, 0.18, Z_PINO1 + 0.6];
const PODIOS = [[-0.62, 0, 2.5], [0.62, 0, 2.5]];
const RODADAS = 3;               // padrão de fábrica: 3 rodadas por jogador
const TENTATIVAS = 3;            // e até 3 bolas por rodada
const DIFICULDADE = "facil";     // padrão de fábrica
const VELOCIDADE = 1.3;          // o jogo todo anda 30% mais rápido que o tempo real
const PASSO_FISICA = 1 / 240;    // passo da física (a bola a 8 m/s anda 3 cm por passo)
const PONTOS_PINO = 10;
const BONUS_STRIKE = 50;
const BONUS_SPARE = 20;
const TEMPO_ESCOLHA = 8.0;

// ------------------------------------------------------------------ cores do hud.gd
const COR_BOB = "#169BD5";
const COR_MIA = "#FF7A21";
const DESTAQUE = "#FFC21A";
const MARINHO = "#0B1F45";
const AZUL = "#1A4FA8";
const CREME = "#FFF6A8";

/* ----------------------------------------------------------------------
   OS 4 CENÁRIOS (scripts/temas.gd, valores da edição OpenGL ES 2.0, que
   foram medidos para estes mesmos shaders)
   ---------------------------------------------------------------------- */
const ORDEM_TEMAS = ["dinos", "parque", "espaco", "mar"];
const TEMAS = {
  parque: {
    ceu: ["#2F7FFF", "#6CBBFF", "#E4F4FF", "#8CD18C"],
    ambiente: [0.62, 0.7, 0.86], ambiente_forca: 0.68,
    neblina: [0.84, 0.92, 1.0], neblina_densidade: 0.0035,
    sol: [1.0, 0.95, 0.86], sol_forca: 0.9,
    fundo: ["#3A1C8C", "#7A3FD6"], halo: "#FFD6F4",
    portal: ["#FFC21A", "#E8384F"], gabinete: "#E8384F", coluna: "#1E62C8", neon: "#FF4FC8",
    parede: "#2A63C4", placa: "#2F63E0", divisoria: "#FFB627", faixa: "#E8384F",
    canaleta_modo: 0, canaleta: ["#FF6FAE", "#FFF3E2", "#FFD23F"],
    bumper: ["#FFFFFF", "#FF3B50"],
    chao: ["#6BCB5D", "#5BB54E", "#FFFFFF", "#FFE873"], chao_modo: 0,
  },
  espaco: {
    ceu: ["#040A26", "#0E2560", "#2C6AB8", "#14244E"],
    estrelas: 1.0, nebulosa: "#2FC8FF", cor_sol: "#CFE0FF", forca_sol: 0.35,
    ambiente: [0.6, 0.7, 1.0], ambiente_forca: 0.78,
    neblina: [0.14, 0.24, 0.5], neblina_densidade: 0.0045,
    sol: [0.9, 0.94, 1.0], sol_forca: 0.92,
    fundo: ["#0B1450", "#2A3FB0"], halo: "#9FE8FF",
    portal: ["#4FD8FF", "#3B2FA8"], gabinete: "#3B3FA8", coluna: "#6A3FD0", neon: "#4FE3FF",
    parede: "#3B4FC8", placa: "#5A3FD8", divisoria: "#4FD8FF", faixa: "#FF9F2E",
    canaleta_modo: 1, canaleta: ["#26357A", "#9FB4FF", "#4FE3FF"],
    bumper: ["#FFFFFF", "#3B8BFF"],
    chao: ["#9AA8C4", "#8494B3", "#C3CEE2", "#E2F5FF"], chao_modo: 1,
  },
  mar: {
    ceu: ["#0A4F86", "#1A94C0", "#86E6DE", "#E8D29A"],
    raios: 1.0, cor_sol: "#E6FFF8", forca_sol: 0.5,
    ambiente: [0.5, 0.82, 0.92], ambiente_forca: 0.72,
    neblina: [0.32, 0.72, 0.84], neblina_densidade: 0.0105,
    sol: [0.88, 1.0, 0.96], sol_forca: 0.86,
    fundo: ["#064A70", "#0FA0B8"], halo: "#C8FFF4",
    portal: ["#2EE6C8", "#FF7A5C"], gabinete: "#0E8C9C", coluna: "#FF7A5C", neon: "#5CFFD8",
    parede: "#18A6B8", placa: "#1A9BD0", divisoria: "#FF8A5C", faixa: "#2EC4B6",
    canaleta_modo: 2, canaleta: ["#0C86A6", "#56E0EA", "#E9FFFB"],
    bumper: ["#FFFFFF", "#FF7A5C"],
    chao: ["#F0C47C", "#E0AC62", "#FF9A86", "#7CD2E0"], chao_modo: 2,
  },
  dinos: {
    ceu: ["#3FA7E8", "#9BD8F0", "#FFE4AE", "#6BBF59"],
    cor_sol: "#FFE7B0",
    ambiente: [0.72, 0.72, 0.62], ambiente_forca: 0.68,
    neblina: [0.92, 0.9, 0.78], neblina_densidade: 0.0045,
    sol: [1.0, 0.93, 0.8], sol_forca: 0.92,
    fundo: ["#14501E", "#3E9A2E"], halo: "#FFF2A8",
    portal: ["#9BE04A", "#FF8A1E"], gabinete: "#8A5228", coluna: "#2E9A3E", neon: "#B6FF3B",
    parede: "#3E9A3A", placa: "#2FA046", divisoria: "#FF9F2E", faixa: "#8BD33F",
    canaleta_modo: 3, canaleta: ["#6DBB45", "#D4F58A", "#F2D27A"],
    bumper: ["#FFE65A", "#2E9A3E"],
    chao: ["#46A44E", "#57B948", "#FF9F33", "#FFE65A"], chao_modo: 3,
  },
};
// tamanho (m) de um ladrilho da textura de detalhes do chão, por modo
const LADRILHO_CHAO = [25.2, 22.4, 25.3, 25.0];
// a roupinha do Bob e da Mia em cada fase (tools/modelos/roupas.py)
const ROUPA_DO_TEMA = { mar: "pirata", dinos: "dino", espaco: "astronauta", parque: "parque" };
// luz de PALCO (pista, pinos, bola, bichinhos): branca e quente em todo
// cenário, com 20% da luz do cenário misturada (edição OpenGL ES 2.0)
const PALCO_SOL = [1.0, 0.96, 0.9];
const PALCO_SOL_FORCA = 1.05;
const PALCO_AMB = [0.66, 0.72, 0.86];
const PALCO_AMB_FORCA = 0.62;
const PALCO_TINTA = 0.2;
// direção PARA o sol (o DirectionalLight do Godot girado -52°, 28°)
const PARA_SOL = (() => {
  const x = Math.cos(52 * GRAU) * Math.sin(28 * GRAU);
  const y = Math.sin(52 * GRAU);
  const z = Math.cos(52 * GRAU) * Math.cos(28 * GRAU);
  return [x, y, z];
})();
// sol e lua com rostinho no céu: [imagem, onde fica visto da área de jogo, tamanho, tinta]
const ASTROS = {
  parque: ["sol", [9.8, 25.2, -59.4], 8.5, [1, 1, 1, 1]],
  dinos: ["sol", [9.8, 25.2, -59.4], 8.5, [1, 1, 1, 1]],
  mar: ["sol", [9.8, 25.2, -59.4], 8.0, [0.86, 1.0, 1.0, 0.82]],
  espaco: ["lua", [-1.1, 26.3, -59.7], 7.2, [1, 1, 1, 1]],
};
const ASTRO_REFERENCIA = [0.0, 1.2, 2.4];
const ASTRO_DISTANCIA = 140.0;
const CORES_LAMPADAS = ["#FFE14D", "#FF9F2E", "#4FD8FF", "#8DFF6A"];
const ARCO_IRIS = ["#FF4B5C", "#FF9F2E", "#FFE14D", "#5ED16A", "#4FC3F7", "#2E7BFF", "#FFFFFF"];

/* ----------------------------------------------------------------------
   UTILIDADES
   ---------------------------------------------------------------------- */
const lim = (v, a, b) => (v < a ? a : v > b ? b : v);
const mistura = (a, b, t) => a + (b - a) * t;
const suave = (a, b, x) => {
  const t = lim((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
const sinal = (v) => (v < 0 ? -1 : 1);
const aleat = (a, b) => a + Math.random() * (b - a);
const sortear = (lista) => lista[Math.floor(Math.random() * lista.length)];
const embaralhar = (lista) => {
  for (let i = lista.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [lista[i], lista[j]] = [lista[j], lista[i]];
  }
  return lista;
};
// TRANS_BACK + EASE_OUT do Godot: passa um pouco do ponto e volta
const voltaElastica = (t) => {
  const s = 1.70158;
  const u = t - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};
const voltaEntrando = (t) => {
  const s = 1.70158;
  return (s + 1) * t * t * t - s * t * t;
};
const senoIO = (t) => 0.5 - 0.5 * Math.cos(Math.PI * t);

/** "#RRGGBB" -> [r, g, b] em 0..1 (o valor cru, sem conversão de cor). */
function hex(h) {
  const n = parseInt(h.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/** sRGB -> linear (a conta do srgb_to_linear do Godot). */
function canalLinear(v) {
  return v < 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}
const linear = (c) => [canalLinear(c[0]), canalLinear(c[1]), canalLinear(c[2])];

/** Altura do terreno (a mesma fórmula do tools/modelos/modelos.py). */
const MORROS = [[-9, -20, 6, 2.2], [10, -26, 7, 2.6], [-14, -42, 9, 3.4], [15, -48, 10, 3.8], [0, -64, 16, 5.0],
  [-20, -10, 6, 1.8], [21, -8, 7, 2.2], [-26, -30, 9, 4.0], [27, -34, 10, 4.5], [-6, -52, 6, 2.0], [6, -58, 7, 2.4]];
function alturaTerreno(x, z) {
  let h = 0;
  for (const m of MORROS) h += m[3] * Math.exp(-((x - m[0]) ** 2 + (z - m[1]) ** 2) / (2 * m[2] * m[2]));
  let p = lim((Math.abs(x) - 3.2) / 4.0, 0, 1);
  p = p * p * (3 - 2 * p);
  return h * p + 0.06 * Math.sin(x * 0.7) * Math.sin(z * 0.55) * p - 0.02 - 0.22 * (1 - p);
}

/** Posição do pino n (numeração oficial: 1 na frente, 7..10 atrás). */
function posicaoDoPino(n) {
  let fileira = 0;
  let primeiro = 1;
  while (n >= primeiro + fileira + 1) {
    primeiro += fileira + 1;
    fileira += 1;
  }
  const k = n - primeiro;
  return [(k - fileira * 0.5) * ESPACO_PINOS, 0, Z_PINO1 - fileira * FILEIRA];
}

/* ----------------------------------------------------------------------
   SHADERS — os da edição OpenGL ES 2.0 (luz por vértice, cores e curva de
   tela iguais às do Godot 4). Escritos para o ShaderMaterial do three.js.
   ---------------------------------------------------------------------- */
const GLSL_COR = /* glsl */ `
// sRGB -> linear sem potência (polinômio, erro ~1%)
vec3 s2l(vec3 c) { return c * (c * (c * 0.305306011 + 0.682171111) + 0.012522878); }
// COR VIVA: realça as cores menos saturadas, um pouco mais de contraste
vec3 viva(vec3 c) {
  float lum = dot(c, vec3(0.299, 0.587, 0.114));
  float sat = max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b));
  c = mix(vec3(lum), c, 1.14 + 0.34 * (1.0 - sat));
  return clamp(c * 1.08 - 0.045, 0.0, 1.0);
}
// a curva de tela do Godot 4 ("filmic", branco 1,6, + sRGB)
vec3 tela(vec3 x) {
  x = max(x, vec3(0.0));
  return viva(min(sqrt(x) * (1.29 - 0.1 * x) / (1.0 + 0.25 * x), vec3(1.0)));
}
// a cor CRUA, como o shader do Godot 4 a entregava, até a tela
vec3 tela_g4(vec3 x) {
  x = clamp(x, 0.0, 1.25);
  return viva(x * (1.2094 - x * (0.015 + 0.25 * x)));
}
`;

// matriz do modelo (com a da cópia, nas malhas instanciadas)
const GLSL_MODELO = /* glsl */ `
mat4 matrizModelo() {
#ifdef USE_INSTANCING
  return modelMatrix * instanceMatrix;
#else
  return modelMatrix;
#endif
}
vec4 corVertice() {
#ifdef USE_COLOR_ALPHA
  return color;
#elif defined(USE_COLOR)
  return vec4(color, 1.0);
#else
  return vec4(1.0);
#endif
}
`;

const SH = {};

// TOON (peças da pista e da máquina): luz em duas faixas, borda clara,
// brilho especular de desenho — tudo por vértice
SH.toon = {
  vertex: GLSL_COR + GLSL_MODELO + /* glsl */ `
uniform vec3 tinta;
uniform float faixa;
uniform float luz_minima;
uniform float borda;
uniform vec3 cor_borda;
uniform float especular;
uniform float tamanho_especular;
uniform vec3 emissao;
uniform float flash;
uniform float brilho_luz;
uniform vec3 luz_dir;
uniform vec3 luz_cor;
uniform vec3 ambiente;
varying vec3 v_cor;
void main() {
  vec4 cor = corVertice();
  mat4 mm = matrizModelo();
  vec4 pm = mm * vec4(position, 1.0);
  vec3 base = s2l(s2l(cor.rgb)) * s2l(s2l(tinta));
  vec3 n = normalize(mat3(mm) * normal);
  float t = smoothstep(-faixa, faixa, dot(n, normalize(luz_dir)) - 0.02);
  vec3 l = luz_cor * max(t, luz_minima) + ambiente;
  vec4 pv = viewMatrix * pm;
  vec3 nv = normalize(mat3(viewMatrix) * n);
  vec3 v = normalize(-pv.xyz);
  float r1 = 1.0 - clamp(dot(nv, v), 0.0, 1.0);
  vec3 soma = s2l(s2l(cor_borda)) * borda * r1 * r1 * r1 * base + s2l(s2l(emissao)) + vec3(flash) * base;
  float brilho = 1.0 - clamp(abs(cor.a - 0.5) * 5.0, 0.0, 1.0);
  soma += base * brilho * brilho_luz;
  if (especular > 0.0) {
    vec3 lv = normalize(mat3(viewMatrix) * luz_dir);
    float s = smoothstep(tamanho_especular, tamanho_especular + 0.02, dot(nv, normalize(v + lv)));
    soma += luz_cor * s * especular;
  }
  v_cor = tela(base * l + soma);
  gl_Position = projectionMatrix * pv;
}`,
  fragment: /* glsl */ `
varying vec3 v_cor;
void main() { gl_FragColor = vec4(v_cor, 1.0); }`,
};

// TOON DOS PERSONAGENS E PINOS (toon_personagem): a mesma luz, por pixel
// (de perto o bichinho ocupa meia tela), o rosto projetado de frente
// (atlas de expressões) e a ESTAMPA da roupa desenhada aqui (estrela do
// Bob, bolinhas da Mia, listras de pirata), nítida em qualquer tamanho.
SH.personagem = {
  vertex: GLSL_COR + GLSL_MODELO + /* glsl */ `
uniform vec3 tinta;
uniform vec2 rosto_centro;
uniform vec2 rosto_tamanho;
uniform int estampa;
uniform vec3 estampa_base;
varying vec3 v_base;
varying vec3 v_n;
varying vec3 v_pv;
varying vec4 v_rosto;
varying vec3 v_local;
varying float v_brilho;
void main() {
  vec4 cor = corVertice();
  mat4 mm = matrizModelo();
  v_base = s2l(s2l(cor.rgb)) * s2l(s2l(tinta));
  v_n = normalize(mat3(mm) * normal);
  vec4 pv = viewMatrix * (mm * vec4(position, 1.0));
  v_pv = pv.xyz;
  vec2 uv = (position.xy - rosto_centro) / rosto_tamanho + 0.5;
  float tecido = 1.0 - smoothstep(0.05, 0.12, distance(s2l(cor.rgb), s2l(estampa_base)));
  if (estampa == 1) tecido *= smoothstep(0.15, 0.4, normal.z);
  v_rosto = vec4(uv.x, 1.0 - uv.y, smoothstep(0.75, 0.95, cor.a) * smoothstep(0.05, 0.3, normal.z), tecido);
  v_local = position;
  v_brilho = 1.0 - clamp(abs(cor.a - 0.5) * 5.0, 0.0, 1.0);
  gl_Position = projectionMatrix * pv;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform vec3 tinta;
uniform float faixa;
uniform float luz_minima;
uniform float borda;
uniform vec3 cor_borda;
uniform float especular;
uniform float tamanho_especular;
uniform vec3 emissao;
uniform float flash;
uniform float escuro;
uniform float brilho_luz;
uniform vec3 luz_dir;
uniform vec3 luz_cor;
uniform vec3 ambiente;
uniform bool usa_rosto;
uniform sampler2D rosto;
uniform vec2 rosto_grade;
uniform vec2 rosto_celula;
uniform int estampa;
uniform vec3 estampa_cor;
uniform vec2 estampa_centro;
uniform float estampa_raio;
uniform float estampa_dentro;
uniform float bolinhas_y0;
uniform float bolinhas_dy;
uniform int bolinhas_fileiras;
uniform int bolinhas_n0;
uniform float bolinhas_y_max;
varying vec3 v_base;
varying vec3 v_n;
varying vec3 v_pv;
varying vec4 v_rosto;
varying vec3 v_local;
varying float v_brilho;

float sd_estrela(vec2 p, float r, float vale) {
  const vec2 k1 = vec2(0.809016994375, -0.587785252292);
  const vec2 k2 = vec2(-0.809016994375, -0.587785252292);
  p.x = abs(p.x);
  p -= 2.0 * max(dot(k1, p), 0.0) * k1;
  p -= 2.0 * max(dot(k2, p), 0.0) * k2;
  p.x = abs(p.x);
  p.y -= r;
  vec2 ba = vale * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
  float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
  return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}
float cobre(float d) {
  float w = max(fwidth(d), 1e-6);
  return clamp(0.5 - d / w, 0.0, 1.0);
}
float sd_bolinhas(vec3 p) {
  float melhor = 1e3;
  float raio_h = max(length(p.xz), 1e-4);
  float ang = atan(p.x, p.z);
  for (int k = 0; k < 8; k++) {
    if (k >= bolinhas_fileiras) break;
    float fk = float(k);
    float y = bolinhas_y0 + fk * bolinhas_dy;
    float n = float(bolinhas_n0) - fk;
    float desloc = 0.5 * mod(fk, 2.0);
    float passo = 6.28318531 / n;
    float i = floor(ang / passo - desloc + 0.5);
    float d_ang = ang - (i + desloc) * passo;
    vec2 q = vec2(d_ang * raio_h, p.y - y);
    melhor = min(melhor, length(q) - estampa_raio);
  }
  return melhor;
}
void main() {
  vec3 base = v_base;
  if (usa_rosto && v_rosto.z > 0.01) {
    vec2 uv = v_rosto.xy;
    if (uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0) {
      vec4 f = texture2D(rosto, (clamp(uv, 0.004, 0.996) + rosto_celula) / rosto_grade);
      base = mix(base, f.rgb * f.rgb, f.a * v_rosto.z);
    }
  }
  if (estampa > 0 && v_rosto.w > 0.01) {
    float d = 1e3;
    float lado = 1.0;
    if (estampa == 1) {
      d = sd_estrela(v_local.xy - estampa_centro, estampa_raio, estampa_dentro) - estampa_raio * 0.06;
      lado = step(0.0, v_local.z);
    } else if (estampa == 2) {
      d = sd_bolinhas(v_local);
      lado = 1.0 - smoothstep(bolinhas_y_max - 0.01, bolinhas_y_max, v_local.y);
    } else {
      float y = v_local.y - bolinhas_y0;
      d = abs(y - bolinhas_dy * floor(y / bolinhas_dy + 0.5)) - estampa_raio;
      lado = (1.0 - smoothstep(bolinhas_y_max - 0.01, bolinhas_y_max, v_local.y)) * step(-estampa_raio, y);
    }
    float m = cobre(d) * v_rosto.w * lado;
    float filete = estampa == 1 ? cobre(abs(d + estampa_raio * 0.06) - estampa_raio * 0.06) * v_rosto.w * lado : 0.0;
    vec3 ec = estampa_cor * tinta;
    vec3 e2 = ec * ec;
    vec3 ce = e2 * e2;
    base = mix(base, ce, m);
    base = mix(base, ce * 0.72, filete * 0.6);
  }
  vec3 n = normalize(v_n);
  float t = smoothstep(-faixa, faixa, dot(n, normalize(luz_dir)) - 0.02);
  vec3 l = luz_cor * max(t, luz_minima) + ambiente;
  vec3 nv = normalize(mat3(viewMatrix) * n);
  vec3 v = normalize(-v_pv);
  float r1 = 1.0 - clamp(dot(nv, v), 0.0, 1.0);
  vec3 soma = s2l(s2l(cor_borda)) * borda * r1 * r1 * r1 * base + s2l(s2l(emissao)) + vec3(flash) * base;
  soma += base * v_brilho * brilho_luz;
  if (especular > 0.0) {
    vec3 lv = normalize(mat3(viewMatrix) * luz_dir);
    float s = smoothstep(tamanho_especular, tamanho_especular + 0.02, dot(nv, normalize(v + lv)));
    soma += luz_cor * s * especular;
  }
  gl_FragColor = vec4(tela((base * l + soma) * escuro), 1.0);
}`,
};

// CONTORNO (casca invertida): a malha inflada pela normal, desenhada só
// por dentro; a espessura acompanha a distância e um RECUO esconde o
// traço onde uma peça encosta em outra
SH.contorno = {
  vertex: GLSL_COR + GLSL_MODELO + /* glsl */ `
uniform float espessura;
uniform float recuo;
uniform vec3 cor_contorno;
uniform float usa_cor_vertice;
varying vec3 v_cor;
void main() {
  mat4 mv = viewMatrix * matrizModelo();
  vec4 pv = mv * vec4(position, 1.0);
  float d = clamp(-pv.z, 0.8, 9.0);
  vec4 p = mv * vec4(position + normal * espessura * d, 1.0);
  p.xyz += normalize(p.xyz) * recuo * d;
  gl_Position = projectionMatrix * p;
  v_cor = tela_g4(mix(s2l(cor_contorno), s2l(corVertice().rgb) * 0.28, usa_cor_vertice));
}`,
  fragment: /* glsl */ `
varying vec3 v_cor;
void main() { gl_FragColor = vec4(v_cor, 1.0); }`,
};

// TOON LEVE (decoração do cenário): as duas faixas (sol e sombra) por
// vértice, a passagem por pixel, e a neblina de cada cenário. A cor do
// vértice já vem em luz linear (raiz quadrada: aqui elevada ao quadrado).
SH.leve = {
  vertex: GLSL_COR + GLSL_MODELO + /* glsl */ `
uniform vec3 tinta;
uniform float faixa;
uniform float luz_minima;
uniform float borda;
uniform vec3 cor_borda;
uniform vec3 emissao;
uniform float brilho_luz;
uniform vec3 sol_dir;
uniform vec3 sol_cor;
uniform vec3 ambiente;
uniform vec3 neblina_cor;
uniform float neblina_densidade;
varying vec3 v_sol;
varying vec3 v_sombra;
varying float v_virada;
void main() {
  vec4 cor = corVertice();
  mat4 mm = matrizModelo();
  vec4 pm = mm * vec4(position, 1.0);
  vec3 base = cor.rgb * cor.rgb * tinta;
  vec3 n = normalize(mat3(mm) * normal);
  vec3 ate = cameraPosition - pm.xyz;
  vec3 v = normalize(ate);
  float neblina = 1.0 - exp(-neblina_densidade * length(ate));
  v_virada = (dot(n, sol_dir) - 0.02) * (0.5 / faixa) + 0.5;
  float rim = 1.0 - clamp(dot(n, v), 0.0, 1.0);
  float acesa = 1.0 - clamp(abs(cor.a - 0.5) * 5.0, 0.0, 1.0);
  vec3 resto = s2l(cor_borda) * borda * rim * rim * rim * base + s2l(emissao) + base * acesa * brilho_luz;
  v_sol = tela_g4(mix(base * (ambiente + sol_cor) + resto, neblina_cor, neblina));
  v_sombra = tela_g4(mix(base * (ambiente + sol_cor * luz_minima) + resto, neblina_cor, neblina));
  gl_Position = projectionMatrix * (viewMatrix * pm);
}`,
  fragment: /* glsl */ `
varying vec3 v_sol;
varying vec3 v_sombra;
varying float v_virada;
void main() { gl_FragColor = vec4(mix(v_sombra, v_sol, clamp(v_virada, 0.0, 1.0)), 1.0); }`,
};

// PISTA: a decoração fixa vem pronta na textura assada (pista_pronta);
// aqui só o que mexe: estrelas piscando, verniz, neon das bordas com as
// luzes correndo e o brilho que acompanha a bola
SH.pista = {
  vertex: /* glsl */ `
uniform float meia_largura;
uniform float z_inicio;
uniform float z_fim;
varying vec2 uv_p;
varying vec2 xd;
varying vec3 olhar;
void main() {
  vec4 pm = modelMatrix * vec4(position, 1.0);
  uv_p = vec2(pm.x / (meia_largura * 2.0) + 0.5, (pm.z - z_inicio) / (z_fim - z_inicio));
  xd = vec2(pm.x, -pm.z);
  olhar = cameraPosition - pm.xyz;
  gl_Position = projectionMatrix * viewMatrix * pm;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform sampler2D pista_pronta;
uniform float meia_largura;
uniform float z_pino1;
uniform float bola_z;
uniform float luz;
uniform float fase;
uniform float fase_lenta;
uniform vec3 cor_luz;
uniform vec3 cor_reflexo_a;
uniform vec3 cor_reflexo_b;
uniform vec3 luz_cena;
uniform vec3 cor_ceu;
uniform vec3 dir_sol;
uniform float verniz;
varying vec2 uv_p;
varying vec2 xd;
varying vec3 olhar;
void main() {
  vec4 t = texture2D(pista_pronta, uv_p);
  vec3 c = t.rgb * t.rgb * 1.6;
  float d = xd.y;
  float ax = abs(xd.x);
  float dp = -z_pino1;
  float chamado = 1.0 - luz;
  if (t.a > 0.004) {
    float k = clamp(floor((d - 2.3) / 1.35 + 0.5), 0.0, 5.0);
    float onda = step(0.72, fract(fase_lenta - k * 0.14));
    float acesa = mix(0.35, 1.0, max(onda * chamado, luz * 0.7));
    c *= 1.0 + t.a * ((0.75 + 0.6 * acesa) / 0.96 - 1.0);
  }
  c *= luz_cena * 0.84;
  float lum = dot(c, vec3(0.299, 0.587, 0.114));
  c = max(mix(vec3(lum), c, 1.3), vec3(0.0));
  vec3 v = normalize(olhar);
  float f1 = 1.0 - clamp(v.y, 0.0, 1.0);
  float f2 = f1 * f1;
  float fres = f2 * f2;
  c = mix(c, cor_ceu * cor_ceu * c * 2.2, fres * verniz * 0.35);
  if (d > dp - 6.0) {
    float fundo = smoothstep(dp - 6.0, dp + 0.5, d);
    vec3 portal = mix(cor_reflexo_b, cor_reflexo_a, 0.5 + 0.5 * sin(xd.x * 9.0));
    c += portal * portal * fres * fundo * 0.28;
  }
  vec3 refl = vec3(-v.x, v.y, -v.z);
  float b = max(dot(refl, dir_sol), 0.0);
  float b2 = b * b;
  float b4 = b2 * b2;
  float b16 = b4 * b4;
  b16 *= b16;
  c += vec3(1.0, 0.95, 0.85) * (b16 * b16 * b16 * verniz * 0.6);
  vec3 neon = cor_luz * cor_luz;
  float borda = smoothstep(meia_largura - 0.085, meia_largura - 0.015, ax);
  float espalha = exp(-(meia_largura - ax) * 9.0) * 0.3;
  float fr = fract(d * 1.1 - fase);
  float corre = smoothstep(0.42, 0.58, fr) * smoothstep(0.98, 0.84, fr);
  float onda_bola = 0.0;
  if (luz > 0.001) onda_bola = exp(-abs(d - bola_z) * 1.6);
  float forca = 0.75 + 0.45 * corre * chamado + luz * (corre * 0.6 + onda_bola * 1.4);
  vec3 e = neon * ((borda + espalha) * forca + onda_bola * luz * 0.18 * (1.0 - borda));
  gl_FragColor = vec4(tela(c + e), 1.0);
}`,
};

// PISO DA ÁREA DOS JOGADORES: madeira envernizada, pontinhos coloridos e
// a estrela "pise aqui"
SH.piso = {
  vertex: /* glsl */ `
varying vec3 pm;
varying vec3 olhar;
varying vec2 v_uv;
void main() {
  vec4 p = modelMatrix * vec4(position, 1.0);
  pm = p.xyz;
  olhar = cameraPosition - p.xyz;
  v_uv = uv;
  gl_Position = projectionMatrix * viewMatrix * p;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform sampler2D madeira;
uniform vec2 escala_uv;
uniform vec3 tom;
uniform vec3 luz_cena;
uniform vec3 cor_ceu;
uniform float verniz;
uniform float pulso;
varying vec3 pm;
varying vec3 olhar;
varying vec2 v_uv;
float cobre(float dist) { return clamp(0.5 - dist * 220.0, 0.0, 1.0); }
float sd_estrela(vec2 p, float r, float vale) {
  vec2 k1 = vec2(0.809016994375, -0.587785252292);
  vec2 k2 = vec2(-0.809016994375, -0.587785252292);
  p.x = abs(p.x);
  p -= 2.0 * max(dot(k1, p), 0.0) * k1;
  p -= 2.0 * max(dot(k2, p), 0.0) * k2;
  p.x = abs(p.x);
  p.y -= r;
  vec2 ba = vale * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
  float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
  return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}
vec3 adesivo(vec3 c, float dist, vec3 cor, float contorno) {
  c = mix(c, vec3(1.0), cobre(dist - contorno));
  return mix(c, cor, cobre(dist));
}
void main() {
  vec3 c = texture2D(madeira, v_uv * escala_uv).rgb * tom;
  if (abs(pm.z - 0.55) < 0.1 && abs(pm.x) < 0.62) {
    float ip = clamp(floor(pm.x / 0.17 + 0.5), -3.0, 3.0);
    float dd = length(vec2(pm.x - ip * 0.17, pm.z - 0.55)) - 0.032;
    vec3 cor = vec3(1.0, 0.23, 0.33);
    if (ip > -2.5) cor = vec3(1.0, 0.56, 0.13);
    if (ip > -1.5) cor = vec3(1.0, 0.85, 0.15);
    if (ip > -0.5) cor = vec3(0.35, 0.86, 0.33);
    if (ip > 0.5) cor = vec3(0.2, 0.8, 1.0);
    if (ip > 1.5) cor = vec3(0.27, 0.47, 1.0);
    if (ip > 2.5) cor = vec3(0.72, 0.38, 1.0);
    c = adesivo(c, dd, cor, 0.011);
  }
  if (abs(pm.z - 1.45) < 0.32 && abs(pm.x) < 0.32) {
    float de = sd_estrela(vec2(pm.x, 1.45 - pm.z), 0.2, 0.48) - 0.015;
    c += vec3(1.0, 0.85, 0.2) * exp(-max(de, 0.0) * 20.0) * (0.15 + 0.15 * pulso);
    c = adesivo(c, de, vec3(1.0, 0.82, 0.15), 0.02);
  }
  c *= luz_cena * 0.86;
  float lum = dot(c, vec3(0.299, 0.587, 0.114));
  c = max(mix(vec3(lum), c, 1.3), vec3(0.0));
  vec3 v = normalize(olhar);
  float f1 = 1.0 - clamp(v.y, 0.0, 1.0);
  float f2 = f1 * f1;
  gl_FragColor = vec4(tela_g4(mix(c, cor_ceu * c * 2.2, f2 * f2 * verniz * 0.5)), 1.0);
}`,
};

// CANALETA DE CADA CENÁRIO: doce listrado (Parque), metal de nave
// (Espaço), água com reflexos e bolhinhas (Mar), bambu (Selva)
SH.canaleta = {
  vertex: GLSL_COR + GLSL_MODELO + /* glsl */ `
uniform vec3 cor_a;
uniform vec3 cor_b;
uniform vec3 cor_c;
uniform vec3 luz_cena;
uniform float centro;
varying vec3 ta;
varying vec3 tb;
varying vec3 tc;
varying vec3 pos_c;
void main() {
  vec4 pw = modelMatrix * vec4(position, 1.0);
  pos_c = vec3(abs(pw.x) - centro, pw.z, smoothstep(-0.032, -0.012, pw.y));
  vec3 luz = corVertice().r * min(luz_cena, vec3(1.3));
  ta = tela_g4(cor_a * luz);
  tb = tela_g4(cor_b * luz);
  tc = tela_g4(cor_c * luz);
  gl_Position = projectionMatrix * viewMatrix * pw;
}`,
  fragment: /* glsl */ `
uniform int modo;
uniform float fase;
uniform float onda1;
uniform float onda2;
uniform float bolhas;
varying vec3 ta;
varying vec3 tb;
varying vec3 tc;
varying vec3 pos_c;
float pulso(float ux, float z, float largura) {
  float q = (fract(z * 0.8 + fase) - 0.5) * 9.0;
  return exp(-q * q) * (1.0 - smoothstep(largura * 0.4, largura, abs(ux)));
}
void main() {
  float ux = pos_c.x;
  float z = pos_c.y;
  float labio = pos_c.z;
  vec3 c;
  if (modo == 0) {
    float t = z * 2.4 + ux * 6.0;
    float m = clamp(0.5 - (abs(fract(t) - 0.5) - 0.25) * 40.0, 0.0, 1.0);
    c = mix(tb, ta, m);
    c += tc * pulso(ux, z, 0.06) * 0.9;
    c = mix(c, tc, labio);
  } else if (modo == 1) {
    float ds = abs(fract(z * 2.0 + 0.5) - 0.5) * 0.5;
    float emenda = 1.0 - smoothstep(0.004, 0.008, ds);
    float rebite = 1.0 - smoothstep(0.006, 0.01, length(vec2(abs(ux) - 0.1, ds - 0.06)));
    c = ta * (1.0 - 0.35 * emenda) + tb * 0.4 * rebite;
    float filete = 1.0 - smoothstep(0.004, 0.008, abs(ux));
    c += tc * (pulso(ux, z, 0.07) * 1.1 + filete * 0.45);
    c = mix(c, tc, labio);
  } else if (modo == 2) {
    float o = sin(z * 7.0 + sin(ux * 38.0 + onda1) * 1.3 + onda2);
    float reflexo = smoothstep(0.82, 0.92, o);
    c = mix(ta, tb, 0.25 + 0.35 * labio) + vec3(0.8, 0.95, 0.95) * reflexo * 0.3;
    vec2 bq = vec2(ux / 0.08, (z + bolhas) / 0.22);
    vec2 cel = floor(bq);
    float h = fract(cel.x * 0.618 + mod(cel.y, 16.0) * 0.7548 + cel.x * mod(cel.y, 16.0) * 0.137);
    vec2 cb = cel + vec2(0.25 + 0.5 * h, 0.2 + 0.6 * fract(h * 7.3));
    vec2 db = (bq - cb) * vec2(0.08, 0.22);
    float raio = 0.007 + 0.009 * fract(h * 13.1);
    float bolha = (1.0 - smoothstep(0.0015, 0.0035, abs(length(db) - raio))) * step(0.45, h);
    c = mix(c, vec3(0.92, 1.0, 1.0), bolha * 0.85);
    c = mix(c, tc, labio);
  } else {
    float dn = abs(fract(z / 0.42 + 0.5) - 0.5) * 0.42;
    float no = 1.0 - smoothstep(0.011, 0.016, dn);
    float anel = 1.0 - smoothstep(0.007, 0.012, abs(dn - 0.03));
    float fibra = 0.9 + 0.1 * sin(ux * 95.0 + sin(z * 2.7) * 0.6);
    c = ta * fibra;
    c = mix(c, tb, anel * 0.7);
    c = mix(c, ta * 0.45, no);
    c += vec3(0.55, 0.9, 0.25) * pulso(ux, z, 0.07) * 0.6;
    c = mix(c, tc, labio);
  }
  gl_FragColor = vec4(c, 1.0);
}`,
};

// DOCE LISTRADO (os para-choques): listras em espiral pela altura e pela
// volta do tubo, com a luz por vértice
SH.doce = {
  vertex: GLSL_COR + /* glsl */ `
uniform float faixa;
uniform float borda;
uniform vec3 luz_dir;
uniform vec3 luz_cor;
uniform vec3 ambiente;
varying vec4 v_sol;
varying vec4 v_sombra;
varying vec2 v_uv;
void main() {
  v_uv = uv;
  vec3 n = normalize(mat3(modelMatrix) * normal);
  float virada = (dot(n, normalize(luz_dir)) - 0.02) * (0.5 / faixa) + 0.5;
  vec4 pv = modelViewMatrix * vec4(position, 1.0);
  vec3 nv = normalize(mat3(viewMatrix) * n);
  vec3 v = normalize(-pv.xyz);
  float r1 = 1.0 - clamp(dot(nv, v), 0.0, 1.0);
  vec3 borda_v = vec3(r1 * r1 * r1 * borda) + ambiente;
  vec3 lv = normalize(mat3(viewMatrix) * luz_dir);
  v_sol = vec4(luz_cor + borda_v, virada);
  v_sombra = vec4(borda_v, dot(nv, normalize(v + lv)));
  gl_Position = projectionMatrix * pv;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform vec3 cor_a;
uniform vec3 cor_b;
uniform float listras_por_metro;
uniform float giro;
uniform float especular;
uniform vec3 luz_cor;
varying vec4 v_sol;
varying vec4 v_sombra;
varying vec2 v_uv;
void main() {
  float ang = -0.25 - v_uv.x;
  float s = fract(v_uv.y * listras_por_metro + ang * giro) - 0.5;
  float m = clamp(0.5 - (abs(s) - 0.25) * 30.0, 0.0, 1.0);
  vec3 base = mix(cor_a, cor_b, m);
  vec3 luz = mix(v_sombra.rgb, v_sol.rgb, clamp(v_sol.a, 0.0, 1.0));
  vec3 soma = luz_cor * (smoothstep(0.93, 0.95, v_sombra.a) * especular * 0.5);
  gl_FragColor = vec4(tela(base * base * luz + soma), 1.0);
}`,
};

// LÂMPADAS (malha instanciada): a cor de cada lâmpada e o número dela,
// que acende na corrida, todas piscando (strike) ou alternadas (spare)
SH.lampadas = {
  vertex: GLSL_COR + /* glsl */ `
attribute float numero;
uniform float fase;
uniform int modo;
uniform float intensidade;
varying vec3 v_cor;
void main() {
  float on;
  if (modo == 0) on = 0.25 + 0.75 * step(0.6, fract(numero * 0.25 - fase));
  else if (modo == 1) on = 0.3 + 0.7 * step(0.5, fract(fase * 2.0));
  else on = 0.25 + 0.75 * step(0.5, fract(numero * 0.5 + fase * 2.0));
  mat4 mv = modelViewMatrix * instanceMatrix;
  vec4 pv = mv * vec4(position, 1.0);
  vec3 nv = normalize(mat3(mv) * normal);
  float rim = clamp(dot(nv, normalize(-pv.xyz)), 0.0, 1.0);
  v_cor = tela_g4(instanceColor * (0.35 + rim * 0.65) * on * intensidade + vec3(0.12) * rim);
  gl_Position = projectionMatrix * pv;
}`,
  fragment: /* glsl */ `
varying vec3 v_cor;
void main() { gl_FragColor = vec4(v_cor, 1.0); }`,
};

// ARCO DO PORTAL: leque de raios alternando as duas cores do cenário
SH.raios = {
  vertex: GLSL_COR + GLSL_MODELO + /* glsl */ `
uniform vec3 cor_a;
uniform vec3 cor_b;
uniform float pulso;
varying vec3 v_cor;
void main() {
  vec4 cor = corVertice();
  float r = cor.g;
  vec3 c = mix(cor_b, cor_a, cor.r);
  c *= 1.12 - 0.35 * r;
  c += vec3(1.0, 0.95, 0.8) * (0.3 + 0.12 * pulso) * clamp(1.0 - r * 2.2, 0.0, 1.0);
  v_cor = tela_g4(c);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`,
  fragment: /* glsl */ `
varying vec3 v_cor;
void main() { gl_FragColor = vec4(v_cor, 1.0); }`,
};

// CORTINA ATRÁS DOS PINOS (fundo_estrelas): veludo nas cores do cenário,
// halo de luz atrás dos pinos, estrelinhas piscando e as pregas
SH.cortina = {
  vertex: /* glsl */ `
varying vec2 v_uv;
varying vec3 v_n;
void main() {
  v_uv = uv;
  v_n = normal;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform vec3 cor_a;
uniform vec3 cor_b;
uniform vec3 cor_halo;
uniform float fase;
varying vec2 v_uv;
varying vec3 v_n;
float h(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  vec2 UV = vec2(v_uv.x, 1.0 - v_uv.y);
  vec2 uv = UV * vec2(6.0, 3.0);
  vec3 a = s2l(cor_a);
  vec3 b = s2l(cor_b);
  vec3 hl = s2l(cor_halo);
  vec3 c = mix(b, a, UV.y);
  vec2 q = (UV - vec2(0.5, 0.82)) * vec2(1.25, 1.6);
  float halo = exp(-dot(q, q) * 4.0);
  c = mix(c, hl, halo * 0.55);
  float faixa = smoothstep(0.92, 1.0, sin(UV.x * 18.0 + fase * 6.2831) * 0.5 + 0.5);
  c += hl * faixa * 0.08;
  vec2 cel = floor(uv * 3.0);
  vec2 f = fract(uv * 3.0) - 0.5;
  float r = h(cel);
  if (r > 0.62) {
    float pis = 0.5 + 0.5 * sin(fase * 6.2831 * (0.5 + r) + r * 40.0);
    float est = max(0.0, 1.0 - length(f) * 7.0);
    float cruz = max(0.0, 1.0 - abs(f.x) * 30.0) * max(0.0, 1.0 - abs(f.y) * 4.0)
      + max(0.0, 1.0 - abs(f.y) * 30.0) * max(0.0, 1.0 - abs(f.x) * 4.0);
    c += vec3(1.0, 0.97, 0.9) * (est * 1.3 + cruz * 0.7) * pis * (1.0 - halo * 0.7);
  }
  float dobra = 0.72 + 0.45 * clamp(dot(normalize(v_n), normalize(vec3(0.75, 0.25, 0.6))), 0.0, 1.0);
  gl_FragColor = vec4(tela(c * dobra), 1.0);
}`,
};

// CÉU: uma esfera desenhada no INFINITO (só a direção conta), atrás de
// tudo: degradê, brilho do sol, estrelas e nebulosa (espaço) e raios de
// luz vindos de cima (fundo do mar)
SH.ceu = {
  vertex: /* glsl */ `
uniform float estrelas;
uniform float raios;
varying vec3 dir;
varying float nebulosa;
varying float raio_luz;
varying vec2 v_uv;
void main() {
  vec3 d = normalize(position);
  dir = d;
  v_uv = uv;
  vec3 v = mat3(viewMatrix) * d;
  gl_Position = projectionMatrix * vec4(v, 1.0);
  gl_Position.z = gl_Position.w * 0.99999;
  float n = sin(d.x * 3.1 + sin(d.z * 2.3) * 1.7) * sin(d.y * 4.2 + d.z * 1.3) + 0.5 * sin(d.x * 7.0 - d.z * 5.0);
  nebulosa = smoothstep(0.35, 1.2, n) * 0.22 * estrelas;
  float a = max(0.0, sin(d.x * 21.0 + d.z * 9.0) * 0.5 + 0.5);
  float b = max(0.0, sin(d.x * 13.0 - d.z * 15.0 + 1.7) * 0.5 + 0.5);
  float a2 = a * a;
  float a8 = a2 * a2;
  a8 *= a8;
  float b2 = b * b;
  float b4 = b2 * b2;
  raio_luz = (a8 * a2 + b4 * b4 * b4 * b2 * 0.7) * smoothstep(0.05, 0.7, d.y) * 0.35 * raios;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform vec3 cor_topo;
uniform vec3 cor_meio;
uniform vec3 cor_horizonte;
uniform vec3 cor_chao;
uniform vec3 dir_sol;
uniform vec3 cor_sol;
uniform float forca_sol;
uniform float estrelas;
uniform vec3 cor_nebulosa;
uniform float raios;
uniform sampler2D mapa_estrelas;
varying vec3 dir;
varying float nebulosa;
varying float raio_luz;
varying vec2 v_uv;
void main() {
  vec3 d = normalize(dir);
  float y = d.y;
  vec3 c;
  if (y > 0.0) {
    c = mix(cor_horizonte, cor_meio, smoothstep(0.0, 0.18, y));
    c = mix(c, cor_topo, smoothstep(0.18, 0.75, y));
  } else {
    c = mix(cor_horizonte, cor_chao, smoothstep(0.0, -0.08, y));
  }
  if (estrelas > 0.0 && y > -0.02) {
    c += cor_nebulosa * nebulosa;
    c += vec3(0.9, 0.92, 0.95) * texture2D(mapa_estrelas, v_uv).r * 2.2 * estrelas;
  }
  if (raios > 0.0 && y > 0.0) c += vec3(0.75, 1.0, 0.95) * raio_luz;
  float sol = max(dot(d, normalize(dir_sol)), 0.0);
  float s2 = sol * sol;
  float s4 = s2 * s2;
  float s8 = s4 * s4;
  c += cor_sol * (s8 * s4 * 0.25) * forca_sol;
  gl_FragColor = vec4(tela_g4(c), 1.0);
}`,
};

// CHÃO DOS CENÁRIOS: listras do gramado, crateras, ondinhas da areia,
// manchas da selva; florzinhas, crateras e conchinhas vêm da textura de
// detalhes (assada); luz e neblina por vértice
SH.terreno = {
  vertex: /* glsl */ `
uniform int modo;
uniform float faixa;
uniform float luz_minima;
uniform vec3 sol_dir;
uniform vec3 sol_cor;
uniform vec3 ambiente;
uniform float neblina_densidade;
uniform float detalhe_tile;
varying vec2 p;
varying vec2 uv_det;
varying vec3 luz;
varying float neblina;
varying float mancha;
void main() {
  vec4 pw = modelMatrix * vec4(position, 1.0);
  p = pw.xz;
  uv_det = p / detalhe_tile;
  vec3 n = normalize(mat3(modelMatrix) * normal);
  float t = smoothstep(-faixa, faixa, dot(n, sol_dir) - 0.02);
  float alt = clamp(pw.y / 4.0, 0.0, 1.0);
  luz = (ambiente + sol_cor * max(t, luz_minima)) * (1.0 + 0.23 * alt);
  neblina = 1.0 - exp(-neblina_densidade * length(cameraPosition - pw.xyz));
  if (modo == 2) mancha = sin(p.x * 1.6 + sin(p.y * 0.35) * 2.0) * 0.5 + 0.5;
  else if (modo == 3) mancha = sin(p.x * 0.45 + 1.3) * sin(p.y * 0.38) + 0.5 * sin(p.x * 1.1 - p.y * 0.9);
  else mancha = 0.0;
  gl_Position = projectionMatrix * viewMatrix * pw;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform int modo;
uniform vec3 lin_a;
uniform vec3 lin_b;
uniform vec3 lin_c;
uniform vec3 lin_d;
uniform vec3 terra;
uniform vec3 neblina_cor;
uniform sampler2D detalhe;
varying vec2 p;
varying vec2 uv_det;
varying vec3 luz;
varying float neblina;
varying float mancha;
void main() {
  vec3 c;
  if (modo == 0) {
    float s = fract((p.y + p.x * 0.15) / 4.4) - 0.5;
    c = mix(lin_a, lin_b, clamp(0.5 - (abs(s) - 0.25) * 30.0, 0.0, 1.0));
  } else if (modo == 1) {
    c = lin_a;
  } else if (modo == 2) {
    c = mix(lin_a, lin_b, smoothstep(0.35, 0.65, mancha));
  } else {
    c = mix(lin_b, lin_a, clamp(0.5 + mancha * 8.0, 0.0, 1.0));
    c = mix(c, lin_d * terra, clamp(0.5 - (1.05 - mancha) * 8.0, 0.0, 1.0));
  }
  vec3 w = texture2D(detalhe, uv_det).rgb;
  c += (lin_b - c) * w.r + (lin_c - c) * w.g + (lin_d - c) * w.b;
  gl_FragColor = vec4(tela_g4(mix(c * luz, neblina_cor, neblina)), 1.0);
}`,
};

// BOLA: textura do bichinho (patinhas do Bob, estrelas da Mia), luz em
// faixas, bolinha de reflexo do verniz e borda iluminada
SH.bola = {
  vertex: GLSL_COR + /* glsl */ `
uniform float faixa;
uniform float borda;
uniform vec3 cor_borda;
uniform float brilho;
uniform float aceso;
uniform vec3 luz_dir;
uniform vec3 luz_cor;
uniform vec3 ambiente;
varying vec3 luz;
varying vec3 soma;
varying float acesa;
varying vec2 v_uv;
void main() {
  vec3 n = normalize(mat3(modelMatrix) * normal);
  float t = smoothstep(-faixa, faixa, dot(n, normalize(luz_dir)));
  vec3 l = luz_cor * t + ambiente;
  vec4 pv = modelViewMatrix * vec4(position, 1.0);
  vec3 nv = normalize(mat3(viewMatrix) * n);
  vec3 v = normalize(-pv.xyz);
  float r1 = 1.0 - clamp(dot(nv, v), 0.0, 1.0);
  float rim = r1 * r1 * sqrt(r1);
  vec3 lv = normalize(mat3(viewMatrix) * luz_dir);
  float s = smoothstep(0.94, 0.975, dot(nv, normalize(v + lv)));
  luz = l;
  soma = s2l(cor_borda) * rim * borda + luz_cor * s * brilho * 0.6;
  acesa = 1.0 + aceso * 0.6;
  v_uv = uv;
  gl_Position = projectionMatrix * pv;
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform sampler2D textura;
varying vec3 luz;
varying vec3 soma;
varying float acesa;
varying vec2 v_uv;
void main() {
  vec3 c = texture2D(textura, v_uv).rgb;
  gl_FragColor = vec4(tela(c * c * luz * acesa + soma), 1.0);
}`,
};

// SOMBRA REDONDA (blob): embaixo da bola, dos pinos e dos bichinhos
SH.sombra = {
  vertex: GLSL_MODELO + /* glsl */ `
varying vec2 v_uv;
varying float v_a;
void main() {
  v_uv = uv;
  v_a = corVertice().a;
  gl_Position = projectionMatrix * viewMatrix * matrizModelo() * vec4(position, 1.0);
}`,
  fragment: /* glsl */ `
uniform sampler2D textura;
uniform float forca;
varying vec2 v_uv;
varying float v_a;
void main() {
  vec4 t = texture2D(textura, v_uv);
  float a = clamp(t.a * forca * v_a, 0.0, 1.0);
  gl_FragColor = vec4(t.rgb, 1.0 - pow(1.0 - a, 0.4545));
}`,
};

// SOL E LUA COM ROSTINHO: um quadradinho de frente para a câmera, NA
// DIREÇÃO do sol do céu e sempre à mesma distância (fica "no infinito");
// os raios giram e o rosto pisca pelo relógio
SH.astro = {
  vertex: /* glsl */ `
uniform vec3 direcao;
uniform float distancia;
uniform float tamanho;
varying vec2 v_uv;
void main() {
  v_uv = vec2(uv.x, 1.0 - uv.y);
  vec3 centro = cameraPosition + normalize(direcao) * distancia;
  mat4 iv = inverse(viewMatrix);
  vec3 p = centro + (iv[0].xyz * position.x + iv[1].xyz * position.y) * tamanho;
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
}`,
  fragment: GLSL_COR + /* glsl */ `
uniform sampler2D rosto;
uniform sampler2D raios;
uniform float usa_raios;
uniform float tempo;
uniform vec4 tinta;
varying vec2 v_uv;
void main() {
  vec4 fundo = vec4(0.0);
  if (usa_raios > 0.5) {
    float a = tempo * 0.02 * 6.2831853;
    vec2 q = v_uv - 0.5;
    q = vec2(q.x * cos(a) - q.y * sin(a), q.x * sin(a) + q.y * cos(a));
    fundo = texture2D(raios, q + 0.5);
  }
  float pisca = step(4.5 - 0.16, mod(tempo, 4.5));
  vec4 r = texture2D(rosto, vec2((clamp(v_uv.x, 0.002, 0.998) + pisca) * 0.5, v_uv.y));
  float a_saida = r.a + fundo.a * (1.0 - r.a);
  vec3 cor = r.rgb * r.a + fundo.rgb * fundo.a * (1.0 - r.a);
  cor = cor / max(a_saida, 1e-4) * tinta.rgb;
  gl_FragColor = vec4(tela(s2l(cor)), a_saida * tinta.a);
}`,
};

// LOGO DOS LETREIROS: a imagem sem luz, misturada pela transparência
SH.logo = {
  vertex: /* glsl */ `
varying vec2 v_uv;
void main() {
  v_uv = vec2(uv.x, 1.0 - uv.y);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`,
  fragment: /* glsl */ `
uniform sampler2D textura;
varying vec2 v_uv;
void main() {
  vec4 t = texture2D(textura, v_uv);
  if (t.a < 0.02) discard;
  gl_FragColor = t;
}`,
};

// PARTÍCULAS (estrelas, faíscas, fumaça, confete, bolhas): pontos com a
// textura girando e a cor de cada uma; somam luz ou misturam
SH.particula = {
  vertex: /* glsl */ `
attribute vec4 cor;
attribute vec2 tamgiro;
uniform float escala_tela;
uniform float tamanho_max;
varying vec4 v_cor;
varying float v_giro;
void main() {
  vec4 pv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * pv;
  // (o confete que passa rente à câmera não vira um borrão na tela toda)
  gl_PointSize = min(tamgiro.x * escala_tela / max(-pv.z, 0.05), tamanho_max);
  v_cor = cor;
  v_giro = tamgiro.y;
}`,
  fragment: /* glsl */ `
uniform sampler2D textura;
uniform float somar;
varying vec4 v_cor;
varying float v_giro;
void main() {
  vec2 q = gl_PointCoord - 0.5;
  float c = cos(v_giro);
  float s = sin(v_giro);
  q = vec2(c * q.x - s * q.y, s * q.x + c * q.y) + 0.5;
  vec4 t = texture2D(textura, q) * v_cor;
  if (somar > 0.5) gl_FragColor = vec4(t.rgb * t.a, 1.0);
  else {
    if (t.a < 0.01) discard;
    gl_FragColor = t;
  }
}`,
};

// RASTRO DE ARCO-ÍRIS da bola (fita no chão, soma luz)
SH.rastro = {
  vertex: /* glsl */ `
attribute vec4 cor;
varying vec4 v_cor;
void main() {
  v_cor = cor;
  gl_Position = projectionMatrix * viewMatrix * vec4(position, 1.0);
}`,
  fragment: /* glsl */ `
varying vec4 v_cor;
void main() { gl_FragColor = vec4(v_cor.rgb * v_cor.a, 1.0); }`,
};

/* ----------------------------------------------------------------------
   CARREGAMENTO: o three.js (só quando o jogo abre), os modelos, as
   texturas, as artes 2D e as fontes do jogo
   ---------------------------------------------------------------------- */
const TEXTURAS_3D = {
  pista: "pista.webp", madeira: "madeira.webp", estrelas_ceu: "estrelas_ceu.webp",
  chao_0: "chao_0.webp", chao_1: "chao_1.webp", chao_2: "chao_2.webp", chao_3: "chao_3.webp",
  rosto_bob: "rosto_bob.webp", rosto_mia: "rosto_mia.webp", rosto_pino: "rosto_pino.webp",
  bola_bob: "bola_bob.webp", bola_mia: "bola_mia.webp", sombra: "sombra.webp",
  estrela: "estrela.webp", faisca: "faisca.webp", fumaca: "fumaca.webp", confete: "confete.webp",
  bolha: "bolha.webp", ceu_sol: "ceu_sol.webp", ceu_lua: "ceu_lua.webp", ceu_raios: "ceu_raios.webp",
  marca: "marca.webp", logo: "logo.webp",
};
const ARTES_2D = {
  strike: "ui_strike.webp", spare: "ui_spare.webp", boa: "ui_boa.webp", uau: "ui_uau.webp",
  super: "ui_super.webp", quase: "ui_quase.webp", ops: "ui_ops.webp", pegando_fogo: "ui_pegando_fogo.webp",
  novo_recorde: "ui_novo_recorde.webp", cen_parque: "ui_cen_parque.webp", cen_espaco: "ui_cen_espaco.webp",
  cen_mar: "ui_cen_mar.webp", cen_dinos: "ui_cen_dinos.webp", fim_de_jogo: "ui_fim_de_jogo.webp",
  replay: "ui_replay.webp", retrato_bob: "ui_retrato_bob.webp", retrato_mia: "ui_retrato_mia.webp",
  retrato_bob_empolgado: "ui_retrato_bob_empolgado.webp", retrato_mia_empolgado: "ui_retrato_mia_empolgado.webp",
  estrela_placar: "ui_estrela_placar.webp", estrela_vazia: "ui_estrela_vazia.webp",
  estrela: "estrela.webp", logo: "logo.webp", bola_bob: "bola_bob.webp", bola_mia: "bola_mia.webp",
};
// artes que a tela de escolha e o placar já usam (o resto vem depois)
const ARTES_JA = new Set(["retrato_bob", "retrato_mia", "retrato_bob_empolgado", "retrato_mia_empolgado",
  "estrela_placar", "estrela_vazia", "estrela", "logo", "bola_bob", "bola_mia"]);
// largura original (px) das artes dos letreiros (ui/*.png do jogo)
const LARGURA_ARTE = {
  strike: 2108, spare: 1789, boa: 1228, uau: 1178, super: 1744, quase: 1640, ops: 1118,
  pegando_fogo: 1746, novo_recorde: 1700,
};
const FONTE = "'SK Fredoka', 'Fredoka', 'Poppins', system-ui, sans-serif";
const FONTE_TITULO = "'SK Titan', 'Titan One', 'Poppins', system-ui, sans-serif";

function urlDe(nome) {
  return new URL(nome, PASTA).href;
}

async function baixarBinario(nome) {
  const r = await fetch(urlDe(nome));
  if (!r.ok) throw new Error("não baixou " + nome);
  return r.arrayBuffer();
}

async function baixarJson(nome) {
  const r = await fetch(urlDe(nome));
  if (!r.ok) throw new Error("não baixou " + nome);
  return r.json();
}

function baixarImagem(nome) {
  return new Promise((resolver) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => resolver(img);
    img.onerror = () => resolver(null);
    img.src = urlDe(nome);
  });
}

async function carregarFontes() {
  if (typeof FontFace === "undefined" || !document.fonts) return;
  const pares = [["SK Fredoka", "fredoka_700.ttf", "700"], ["SK Titan", "titan_one.ttf", "400"]];
  await Promise.all(pares.map(async ([familia, arquivo, peso]) => {
    try {
      const f = new FontFace(familia, `url(${urlDe(arquivo)})`, { weight: peso });
      await f.load();
      document.fonts.add(f);
    } catch (erro) { /* sem a fonte do jogo: fica a do sistema */ }
  }));
}

/** Pacote de malhas (strike-kids/<nome>.bin + .json), como o
 *  tools/construir.py grava: posição em 16 bits na caixa da peça,
 *  normal em octaedro 2 x 8 bits, cor RGBA 8 bits e índices em 16 bits —
 *  cada um como diferença para o anterior (o arquivo comprime melhor). */
async function carregarPacote(THREE, nome) {
  const [info, buf] = await Promise.all([baixarJson(nome + ".json"), baixarBinario(nome + ".bin")]);
  const u8 = new Uint8Array(buf);
  const malhas = {};
  for (const m of info.malhas) malhas[m.nome] = decodificarMalha(THREE, u8, m);
  return { info, malhas };
}

function lerZigue16(u8, o, n, saida, passo, desloc, depois) {
  let acc = 0;
  for (let j = 0; j < n; j++) {
    const z = u8[o + j] | (u8[o + n + j] << 8);
    acc = (acc + ((z >>> 1) ^ -(z & 1))) & 0xffff;
    saida[j * passo + desloc] = depois ? depois(acc) : acc;
  }
}

function decodificarMalha(THREE, u8, m) {
  const nv = m.nv;
  const ni = m.ni;
  let o = m.o;
  const pos = new Float32Array(nv * 3);
  for (let k = 0; k < 3; k++) {
    const mn = m.min[k];
    const esc = m.esc[k] / 65535;
    lerZigue16(u8, o, nv, pos, 3, k, (q) => mn + q * esc);
    o += nv * 2;
  }
  const nor = new Float32Array(nv * 3);
  let ax = 0;
  let ay = 0;
  for (let j = 0; j < nv; j++) {
    ax = (ax + u8[o + j]) & 255;
    ay = (ay + u8[o + nv + j]) & 255;
    let x = ((ax << 24) >> 24) / 127;
    let y = ((ay << 24) >> 24) / 127;
    const z = 1 - Math.abs(x) - Math.abs(y);
    if (z < 0) {
      const xx = (1 - Math.abs(y)) * (x >= 0 ? 1 : -1);
      const yy = (1 - Math.abs(x)) * (y >= 0 ? 1 : -1);
      x = xx;
      y = yy;
    }
    const l = Math.hypot(x, y, z) || 1;
    nor[j * 3] = x / l;
    nor[j * 3 + 1] = y / l;
    nor[j * 3 + 2] = z / l;
  }
  o += nv * 2;
  const cor = new Uint8Array(nv * 4);
  for (let k = 0; k < 4; k++) {
    let acc = 0;
    for (let j = 0; j < nv; j++) {
      acc = (acc + u8[o + j]) & 255;
      cor[j * 4 + k] = acc;
    }
    o += nv;
  }
  const idx = new Uint16Array(ni);
  lerZigue16(u8, o, ni, idx, 1, 0, null);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  g.setAttribute("color", new THREE.BufferAttribute(cor, 4, true));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  g.computeBoundingSphere();
  return g;
}

/* ----------------------------------------------------------------------
   PEÇAS FEITAS NO CÓDIGO (scripts/perfis.gd e mundo.gd): perfis puxados
   ao longo de Z, caixas, tubos de doce, leque de raios, cortina
   ---------------------------------------------------------------------- */
const Perfis = {
  /** Retângulo de cantos arredondados (contorno anti-horário). */
  retangulo(largura, altura, raio, cx = 0, cy = 0, segs = 10) {
    const r = Math.min(raio, Math.min(largura, altura) * 0.5);
    const hw = largura * 0.5 - r;
    const hh = altura * 0.5 - r;
    const p = [];
    const cantos = [[hw, -hh], [hw, hh], [-hw, hh], [-hw, -hh]];
    for (let k = 0; k < 4; k++) {
      const a0 = -Math.PI * 0.5 + k * Math.PI * 0.5;
      for (let i = 0; i <= segs; i++) {
        const a = a0 + Math.PI * 0.5 * i / segs;
        p.push([cx + cantos[k][0] + Math.cos(a) * r, cy + cantos[k][1] + Math.sin(a) * r]);
      }
    }
    return p;
  },

  /** Canaleta em meia-cana: calha de raio r com os lábios no nível da pista. */
  canaleta(r, borda = 0.018, fundo = 0.05, segs = 56) {
    const p = [];
    const yc = -borda;
    const xe = r + 2 * borda;
    p.push([xe, yc - r - fundo]);
    for (let i = 0; i <= 16; i++) {
      const a = Math.PI * i / 16;
      p.push([r + borda + Math.cos(a) * borda, yc + Math.sin(a) * borda]);
    }
    for (let i = 1; i < segs; i++) {
      const a = -Math.PI * i / segs;
      p.push([Math.cos(a) * r, yc + Math.sin(a) * r]);
    }
    for (let i = 0; i <= 16; i++) {
      const a = Math.PI * i / 16;
      p.push([-r - borda + Math.cos(a) * borda, yc + Math.sin(a) * borda]);
    }
    p.push([-xe, yc - r - fundo]);
    return p;
  },

  /** Contorno do arco do portal: base reta, laterais e meia-elipse. */
  arco(r, y0, yc, alto) {
    const p = [[r, y0]];
    for (let i = 0; i <= 48; i++) {
      const a = Math.PI * i / 48;
      p.push([Math.cos(a) * r, yc + Math.sin(a) * alto]);
    }
    p.push([-r, y0]);
    return p;
  },
};

/** Puxa o contorno de z0 até z1: normais suaves nas curvas, quina viva
 *  acima de `quina` graus, tampas nas pontas. sombreado = [y_baixo,
 *  y_alto, brilho_baixo, brilho_alto] vira a cor do vértice. */
function extrudar(THREE, perfil, z0, z1, { tampa0 = true, tampa1 = true, quina = 50, sombreado = null } = {}) {
  const n = perfil.length;
  const pos = [];
  const nor = [];
  const cor = [];
  const brilho = (y) => {
    if (!sombreado) return 1;
    const t = lim((y - sombreado[0]) / Math.max(sombreado[1] - sombreado[0], 1e-4), 0, 1);
    return mistura(sombreado[2], sombreado[3], t * t * (3 - 2 * t));
  };
  const na = [];
  for (let i = 0; i < n; i++) {
    const a = perfil[i];
    const b = perfil[(i + 1) % n];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l = Math.hypot(dx, dy) || 1;
    na.push([dy / l, -dx / l]);
  }
  const limite = Math.cos(quina * GRAU);
  const juntar = (u, v) => {
    const x = u[0] + v[0];
    const y = u[1] + v[1];
    const l = Math.hypot(x, y) || 1;
    return [x / l, y / l];
  };
  const pt = (x, y, z, nx, ny, nz) => {
    pos.push(x, y, z);
    nor.push(nx, ny, nz);
    const b = brilho(y);
    cor.push(b, b, b, 1);
  };
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const a = perfil[i];
    const b = perfil[j];
    const ant = na[(i - 1 + n) % n];
    const prox = na[j];
    const nA = (na[i][0] * ant[0] + na[i][1] * ant[1]) < limite ? na[i] : juntar(na[i], ant);
    const nB = (na[i][0] * prox[0] + na[i][1] * prox[1]) < limite ? na[i] : juntar(na[i], prox);
    // frente para fora (anti-horário visto de fora): A, B, C e A, C, D
    pt(a[0], a[1], z0, nA[0], nA[1], 0);
    pt(b[0], b[1], z0, nB[0], nB[1], 0);
    pt(b[0], b[1], z1, nB[0], nB[1], 0);
    pt(a[0], a[1], z0, nA[0], nA[1], 0);
    pt(b[0], b[1], z1, nB[0], nB[1], 0);
    pt(a[0], a[1], z1, nA[0], nA[1], 0);
  }
  if (tampa0 || tampa1) {
    const contorno = perfil.map((p) => new THREE.Vector2(p[0], p[1]));
    const tris = THREE.ShapeUtils.triangulateShape(contorno, []);
    for (const t of tris) {
      const p0 = perfil[t[0]];
      const p1 = perfil[t[1]];
      const p2 = perfil[t[2]];
      const anti = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]) > 0;
      if (tampa1) {
        for (const q of (anti ? [p0, p1, p2] : [p0, p2, p1])) pt(q[0], q[1], z1, 0, 0, 1);
      }
      if (tampa0) {
        for (const q of (anti ? [p0, p2, p1] : [p0, p1, p2])) pt(q[0], q[1], z0, 0, 0, -1);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(cor, 4));
  g.computeBoundingSphere();
  return g;
}

/** Cor branca (RGBA) em cada vértice: o toon usa a cor do vértice x tinta. */
function comCor(THREE, g, rgba = [1, 1, 1, 1]) {
  const n = g.attributes.position.count;
  const c = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) c.set(rgba, i * 4);
  g.setAttribute("color", new THREE.BufferAttribute(c, 4));
  return g;
}

/** TUBO DE DOCE (para-choque): em pé no eixo Y, de y0 até y1, pontas em
 *  meia esfera; UV.x dá a volta e UV.y é a altura para as listras, contada
 *  do começo de cada trecho de até 2 m (Mundo._tubo_doce). */
function tuboDoce(THREE, raio, y0, y1, gomos, passo, aneisPonta) {
  const perfil = [];
  const yc1 = y1 - raio;
  const yc0 = y0 + raio;
  for (let k = 0; k <= aneisPonta; k++) {
    const f = Math.PI * 0.5 * (1 - k / aneisPonta);
    perfil.push([yc1 + raio * Math.sin(f), raio * Math.cos(f), Math.sin(f)]);
  }
  const nReta = Math.max(1, Math.ceil((yc1 - yc0) / passo));
  for (let k = 1; k < nReta; k++) perfil.push([mistura(yc1, yc0, k / nReta), raio, 0]);
  for (let k = 0; k <= aneisPonta; k++) {
    const f = -Math.PI * 0.5 * k / aneisPonta;
    perfil.push([yc0 + raio * Math.sin(f), raio * Math.cos(f), Math.sin(f)]);
  }
  const pos = [];
  const nor = [];
  const uv = [];
  const idx = [];
  let comeco = Math.ceil(y1 * 4) / 4;
  let nAneis = 0;
  const anel = (a, inicio) => {
    const nr = Math.sqrt(Math.max(1 - a[2] * a[2], 0));
    for (let j = 0; j <= gomos; j++) {
      const u = j / gomos;
      const ang = -Math.PI * 0.5 - TAU * u;
      nor.push(Math.cos(ang) * nr, a[2], Math.sin(ang) * nr);
      uv.push(u, a[0] - inicio);
      pos.push(Math.cos(ang) * a[1], a[0], Math.sin(ang) * a[1]);
    }
  };
  for (let i = 0; i < perfil.length; i++) {
    const y = perfil[i][0];
    if (i > 0 && comeco - y > 2.0) {
      comeco = Math.ceil(perfil[i - 1][0] * 4) / 4;
      anel(perfil[i - 1], comeco);
      nAneis++;
    }
    anel(perfil[i], comeco);
    nAneis++;
    if (nAneis < 2) continue;
    const antes = (nAneis - 2) * (gomos + 1);
    const este = (nAneis - 1) * (gomos + 1);
    for (let j = 0; j < gomos; j++) {
      // (anti-horário visto de fora)
      idx.push(antes + j, este + j, antes + j + 1);
      idx.push(antes + j + 1, este + j, este + j + 1);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/** Leque de raios do arco: do meio da base até o contorno do arco;
 *  COLOR.r = qual das 2 cores, COLOR.g = 0 no centro, 1 na borda. */
function lequeRaios(THREE, r, y0, yc, alto, setores, z) {
  const borda = (ang) => {
    const dx = Math.cos(ang);
    const dy = Math.sin(ang);
    if (Math.abs(dx) > 1e-4) {
      const tLado = r / Math.abs(dx);
      const yLado = y0 + tLado * dy;
      if (yLado <= yc) return [tLado * dx, yLado];
    }
    const a = (dx * dx) / (r * r) + (dy * dy) / (alto * alto);
    const b = 2 * (y0 - yc) * dy / (alto * alto);
    const c = (y0 - yc) * (y0 - yc) / (alto * alto) - 1;
    const t = (-b + Math.sqrt(Math.max(b * b - 4 * a * c, 0))) / (2 * a);
    return [t * dx, y0 + t * dy];
  };
  const pos = [];
  const cor = [];
  const nor = [];
  const sub = 4;
  for (let k = 0; k < setores; k++) {
    const qual = k % 2;
    for (let j = 0; j < sub; j++) {
      const a0 = Math.PI * (k + j / sub) / setores;
      const a1 = Math.PI * (k + (j + 1) / sub) / setores;
      const p0 = borda(a0);
      const p1 = borda(a1);
      // anti-horário visto de +Z: centro, p0, p1
      pos.push(0, y0, z, p0[0], p0[1], z, p1[0], p1[1], z);
      cor.push(qual, 0, 0, 1, qual, 1, 0, 1, qual, 1, 0, 1);
      nor.push(0, 0, 1, 0, 0, 1, 0, 0, 1);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(cor, 4));
  return g;
}

/** Cortina pregueada (plano XY com dobras em Z), UV 0..1. */
function cortinaPregueada(THREE, largura, altura, dobras, fundura, colunas = 160) {
  const k = TAU * dobras / largura;
  const pos = [];
  const nor = [];
  const uv = [];
  for (let i = 0; i <= colunas; i++) {
    const u = i / colunas;
    const x = (u - 0.5) * largura;
    const z = Math.sin(x * k) * fundura * 0.5;
    const dz = Math.cos(x * k) * fundura * 0.5 * k;
    const l = Math.hypot(dz, 1);
    for (let j = 0; j < 2; j++) {
      pos.push(x, (j - 0.5) * altura, z);
      nor.push(-dz / l, 0, 1 / l);
      uv.push(u, 1 - j);
    }
  }
  const idx = [];
  for (let i = 0; i < colunas; i++) {
    const a = i * 2;
    idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/** O TERRENO com morros (a mesma grade e a mesma fórmula do
 *  tools/modelos/modelos.py, com o furo do poço do alçapão). */
function malhaTerreno(THREE) {
  const FURO_X = [-0.95, 0.95];
  const FURO_Z = [-13.66, -11.98];
  const grade = (a, b, n, extras) => {
    const v = [];
    for (let i = 0; i < n; i++) v.push(a + (b - a) * i / (n - 1));
    for (const e of extras) v.push(e);
    v.sort((p, q) => p - q);
    return v.filter((x, i) => i === 0 || Math.abs(x - v[i - 1]) > 1e-9);
  };
  const xs = grade(-34, 34, 90, FURO_X);
  const zs = grade(-70, 18, 110, FURO_Z);
  const nx = xs.length;
  const nz = zs.length;
  const pos = new Float32Array(nx * nz * 3);
  const H = new Float32Array(nx * nz);
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < nz; j++) {
      const k = i * nz + j;
      H[k] = alturaTerreno(xs[i], zs[j]);
      pos[k * 3] = xs[i];
      pos[k * 3 + 1] = H[k];
      pos[k * 3 + 2] = zs[j];
    }
  }
  const nor = new Float32Array(nx * nz * 3);
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < nz; j++) {
      const i0 = Math.max(i - 1, 0);
      const i1 = Math.min(i + 1, nx - 1);
      const j0 = Math.max(j - 1, 0);
      const j1 = Math.min(j + 1, nz - 1);
      const dx = (H[i1 * nz + j] - H[i0 * nz + j]) / (xs[i1] - xs[i0]);
      const dz = (H[i * nz + j1] - H[i * nz + j0]) / (zs[j1] - zs[j0]);
      const l = Math.hypot(dx, 1, dz);
      const k = (i * nz + j) * 3;
      nor[k] = -dx / l;
      nor[k + 1] = 1 / l;
      nor[k + 2] = -dz / l;
    }
  }
  const idx = [];
  for (let i = 0; i < nx - 1; i++) {
    for (let j = 0; j < nz - 1; j++) {
      const furo = xs[i] >= FURO_X[0] - 1e-6 && xs[i + 1] <= FURO_X[1] + 1e-6 &&
        zs[j] >= FURO_Z[0] - 1e-6 && zs[j + 1] <= FURO_Z[1] + 1e-6;
      if (furo) continue;
      const a = i * nz + j;
      const b = (i + 1) * nz + j;
      const c = (i + 1) * nz + j + 1;
      const d = i * nz + j + 1;
      // normal para cima (anti-horário visto de cima)
      idx.push(a, c, b, a, d, c);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  g.setIndex(idx);
  g.computeBoundingSphere();
  return g;
}

/* ----------------------------------------------------------------------
   MATERIAIS (scripts/materiais.gd): a luz de PALCO (pista, pinos, bola,
   bichinhos) e a luz do CENÁRIO (chão e decoração) são uniformes
   compartilhados — trocar de cenário muda todos de uma vez.
   ---------------------------------------------------------------------- */
class Materiais {
  constructor(THREE, tex) {
    this.T = THREE;
    this.tex = tex;
    const v3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);
    this.v3 = v3;
    this.palco = {
      luz_dir: { value: v3(PARA_SOL).normalize() },
      luz_cor: { value: v3([1.05, 0.935, 0.745]) },
      ambiente: { value: v3([0.212, 0.278, 0.439]) },
    };
    this.cena = {
      sol_dir: { value: v3(PARA_SOL).normalize() },
      sol_cor: { value: v3([1, 1, 1]) },
      ambiente: { value: v3([0.4, 0.4, 0.4]) },
      neblina_cor: { value: v3([0.7, 0.8, 0.95]) },
      neblina_densidade: { value: 0.0 },
    };
    this.lista = [];
  }

  _novo(sh, uniforms, extra = {}) {
    const m = new this.T.ShaderMaterial({
      uniforms,
      vertexShader: sh.vertex,
      fragmentShader: sh.fragment,
      ...extra,
    });
    this.lista.push(m);
    return m;
  }

  cor(c) {
    return this.v3(typeof c === "string" ? hex(c) : c);
  }

  /** Toon das peças montadas (cor_toon): tinta + parâmetros. */
  toon(tinta = "#FFFFFF", p = {}) {
    return this._novo(SH.toon, {
      ...this.palco,
      tinta: { value: this.cor(tinta) },
      faixa: { value: p.faixa ?? 0.06 },
      luz_minima: { value: p.luz_minima ?? 0.0 },
      borda: { value: p.borda ?? 0.35 },
      cor_borda: { value: this.cor(p.cor_borda ?? [1.0, 0.95, 0.9]) },
      especular: { value: p.especular ?? 0.0 },
      tamanho_especular: { value: p.tamanho_especular ?? 0.92 },
      emissao: { value: this.cor(p.emissao ?? [0, 0, 0]) },
      flash: { value: 0 },
      brilho_luz: { value: p.brilho_luz ?? 1.4 },
    }, { vertexColors: true });
  }

  /** Toon dos personagens e pinos (rosto, estampa), luz por pixel. */
  personagem(p = {}) {
    return this._novo(SH.personagem, {
      ...this.palco,
      tinta: { value: this.cor(p.tinta ?? "#FFFFFF") },
      faixa: { value: p.faixa ?? 0.06 },
      luz_minima: { value: p.luz_minima ?? 0.0 },
      borda: { value: p.borda ?? 0.35 },
      cor_borda: { value: this.cor(p.cor_borda ?? [1.0, 0.95, 0.9]) },
      especular: { value: p.especular ?? 0.0 },
      tamanho_especular: { value: p.tamanho_especular ?? 0.92 },
      emissao: { value: this.cor(p.emissao ?? [0, 0, 0]) },
      flash: { value: 0 },
      escuro: { value: 1 },
      brilho_luz: { value: p.brilho_luz ?? 1.4 },
      usa_rosto: { value: !!p.rosto },
      rosto: { value: p.rosto ?? null },
      rosto_centro: { value: new this.T.Vector2(...(p.rosto_centro ?? [0, 0.235])) },
      rosto_tamanho: { value: new this.T.Vector2(...(p.rosto_tamanho ?? [0.46, 0.4])) },
      rosto_grade: { value: new this.T.Vector2(...(p.rosto_grade ?? [4, 2])) },
      rosto_celula: { value: new this.T.Vector2(0, 0) },
      estampa: { value: 0 },
      estampa_base: { value: this.cor([1, 1, 1]) },
      estampa_cor: { value: this.cor([1, 0.85, 0.2]) },
      estampa_centro: { value: new this.T.Vector2(0, 0.1) },
      estampa_raio: { value: 0.06 },
      estampa_dentro: { value: 0.5 },
      bolinhas_y0: { value: -0.05 },
      bolinhas_dy: { value: 0.05 },
      bolinhas_fileiras: { value: 3 },
      bolinhas_n0: { value: 12 },
      bolinhas_y_max: { value: 0.08 },
    }, { vertexColors: true });
  }

  /** Casca do contorno (desenhada por dentro). */
  contorno(espessura = 0.0035, p = {}) {
    return this._novo(SH.contorno, {
      espessura: { value: espessura },
      recuo: { value: p.recuo ?? 0.015 },
      cor_contorno: { value: this.cor(p.cor ?? [0.17, 0.10, 0.27]) },
      usa_cor_vertice: { value: p.usa_cor_vertice ?? 0.55 },
    }, { vertexColors: true, side: this.T.BackSide });
  }

  /** Toon leve da decoração (luz e neblina do cenário). */
  leve(tintaLinear = [1, 1, 1], p = {}) {
    return this._novo(SH.leve, {
      ...this.cena,
      tinta: { value: this.v3(tintaLinear) },
      faixa: { value: p.faixa ?? 0.1 },
      luz_minima: { value: p.luz_minima ?? 0.0 },
      borda: { value: p.borda ?? 0.3 },
      cor_borda: { value: this.cor(p.cor_borda ?? [1.0, 0.95, 0.9]) },
      emissao: { value: this.cor(p.emissao ?? [0, 0, 0]) },
      brilho_luz: { value: p.brilho_luz ?? 1.4 },
    }, { vertexColors: true });
  }

  sombra(forca = 0.55) {
    return this._novo(SH.sombra, {
      textura: { value: this.tex.sombra },
      forca: { value: forca },
    }, { transparent: true, depthWrite: false, vertexColors: true, side: this.T.DoubleSide });
  }

  /** A luz de palco e a do cenário de um tema (Mundo.aplicar_tema). */
  definirLuz(c) {
    const amb = linear(c.ambiente).map((v) => v * c.ambiente_forca);
    const ambP = linear(PALCO_AMB).map((v, i) => mistura(v * PALCO_AMB_FORCA, amb[i], PALCO_TINTA));
    const solC = linear(c.sol).map((v) => v * c.sol_forca);
    const solP = linear(PALCO_SOL).map((v, i) => mistura(v * PALCO_SOL_FORCA, solC[i], PALCO_TINTA));
    this.palco.luz_cor.value.set(solP[0], solP[1], solP[2]);
    this.palco.ambiente.value.set(ambP[0], ambP[1], ambP[2]);
    this.cena.sol_cor.value.set(solC[0], solC[1], solC[2]);
    this.cena.ambiente.value.set(amb[0], amb[1], amb[2]);
    const nb = linear(c.neblina);
    this.cena.neblina_cor.value.set(nb[0], nb[1], nb[2]);
    this.cena.neblina_densidade.value = c.neblina_densidade;
    const sobe = Math.max(PARA_SOL[1], 0);
    return [ambP[0] + solP[0] * sobe, ambP[1] + solP[1] * sobe, ambP[2] + solP[2] * sobe];
  }

  liberar() {
    for (const m of this.lista) m.dispose();
    this.lista.length = 0;
  }
}

/* ----------------------------------------------------------------------
   O MUNDO (scripts/mundo.gd): céu, sol, terreno, a pista (madeira,
   canaletas, para-choques), o fundo dos pinos (cortina de estrelas,
   letreiro com lâmpadas, arco de raios, caçapa das bolas), a área dos
   jogadores e os pódios. Cada cenário pinta tudo com as suas cores.
   ---------------------------------------------------------------------- */
class Mundo {
  constructor(THREE, mats, tex) {
    this.T = THREE;
    this.mats = mats;
    this.tex = tex;
    this.raiz = new THREE.Group();
    this.tema = "";
    this.t = 0;
    this.luz = 0;
    this.luzAlvo = 0;
    this.bolaZ = 100;
    this.bolaPos = null;
    this.geometrias = [];
    this.aberturaTiras = new Float32Array(N_TIRAS);
    this.podioDestaque = -1;
    this._ceu();
    this._terreno();
    this._pista();
    this._fundoDosPinos();
    this._colunas();
    this._areaDosJogadores();
    this._podios();
  }

  _g(g) {
    this.geometrias.push(g);
    return g;
  }

  _malha(geo, mat, pos = null, pai = this.raiz) {
    const m = new this.T.Mesh(this._g(geo), mat);
    if (pos) m.position.set(pos[0], pos[1], pos[2]);
    m.matrixAutoUpdate = false;
    m.updateMatrix();
    pai.add(m);
    return m;
  }

  caixa(tam, pos, mat, pai = this.raiz) {
    const g = comCor(this.T, new this.T.BoxGeometry(tam[0], tam[1], tam[2]));
    return this._malha(g, mat, pos, pai);
  }

  peca(perfil, z0, z1, mat, pai = this.raiz, opcoes = {}) {
    return this._malha(extrudar(this.T, perfil, z0, z1, opcoes), mat, null, pai);
  }

  // ---------------------------------------------------------------- céu e sol
  _ceu() {
    const T = this.T;
    this.matCeu = this.mats._novo(SH.ceu, {
      cor_topo: { value: new T.Vector3() }, cor_meio: { value: new T.Vector3() },
      cor_horizonte: { value: new T.Vector3() }, cor_chao: { value: new T.Vector3() },
      dir_sol: { value: new T.Vector3(0.146, 0.358, -0.922) }, cor_sol: { value: new T.Vector3(1, 0.95, 0.75) },
      forca_sol: { value: 1 }, estrelas: { value: 0 }, cor_nebulosa: { value: new T.Vector3(0.9, 0.4, 1) },
      raios: { value: 0 }, mapa_estrelas: { value: this.tex.estrelas_ceu },
    }, { depthWrite: false, side: T.BackSide });
    const ceu = new T.Mesh(this._g(new T.SphereGeometry(1, 48, 24)), this.matCeu);
    ceu.frustumCulled = false;
    ceu.renderOrder = -100;
    this.raiz.add(ceu);
    this.matAstro = this.mats._novo(SH.astro, {
      direcao: { value: new T.Vector3(0.146, 0.358, -0.922) }, distancia: { value: ASTRO_DISTANCIA },
      tamanho: { value: 17.8 }, rosto: { value: this.tex.ceu_sol }, raios: { value: this.tex.ceu_raios },
      usa_raios: { value: 1 }, tempo: { value: 0 }, tinta: { value: new T.Vector4(1, 1, 1, 1) },
    }, { transparent: true, depthWrite: false, side: T.DoubleSide });
    const astro = new T.Mesh(this._g(new T.PlaneGeometry(1, 1)), this.matAstro);
    astro.frustumCulled = false;
    astro.renderOrder = -99;
    this.raiz.add(astro);
  }

  _mostrarAstro(nome) {
    const a = ASTROS[nome] || ASTROS.parque;
    const rel = [a[1][0] - ASTRO_REFERENCIA[0], a[1][1] - ASTRO_REFERENCIA[1], a[1][2] - ASTRO_REFERENCIA[2]];
    const l = Math.hypot(rel[0], rel[1], rel[2]);
    const u = this.matAstro.uniforms;
    const sol = a[0] === "sol";
    u.rosto.value = sol ? this.tex.ceu_sol : this.tex.ceu_lua;
    u.usa_raios.value = sol ? 1 : 0;
    u.tinta.value.set(a[3][0], a[3][1], a[3][2], a[3][3]);
    u.direcao.value.set(rel[0] / l, rel[1] / l, rel[2] / l);
    u.tamanho.value = a[2] * ASTRO_DISTANCIA / l;
    this.matCeu.uniforms.dir_sol.value.copy(u.direcao.value);
  }

  // ---------------------------------------------------------------- terreno
  _terreno() {
    const T = this.T;
    this.matTerreno = this.mats._novo(SH.terreno, {
      ...this.mats.cena,
      modo: { value: 0 }, faixa: { value: 0.25 }, luz_minima: { value: 0 },
      lin_a: { value: new T.Vector3() }, lin_b: { value: new T.Vector3() },
      lin_c: { value: new T.Vector3() }, lin_d: { value: new T.Vector3() },
      terra: { value: new T.Vector3(0.45, 0.32, 0.17) },
      detalhe: { value: this.tex.chao_0 }, detalhe_tile: { value: 25 },
    });
    this._malha(malhaTerreno(T), this.matTerreno);
  }

  // ---------------------------------------------------------------- pista
  _pista() {
    const T = this.T;
    const m = this.mats;
    this.matPista = m._novo(SH.pista, {
      pista_pronta: { value: this.tex.pista }, meia_largura: { value: MEIA_LARGURA },
      z_pino1: { value: Z_PINO1 }, z_inicio: { value: 0.1 }, z_fim: { value: Z_FIM_DECK },
      bola_z: { value: 100 }, luz: { value: 0 }, fase: { value: 0 }, fase_lenta: { value: 0 },
      cor_luz: { value: new T.Vector3(0.35, 0.85, 1) }, cor_reflexo_a: { value: new T.Vector3(1, 0.76, 0.1) },
      cor_reflexo_b: { value: new T.Vector3(0.91, 0.22, 0.31) }, luz_cena: { value: new T.Vector3(1.2, 1.2, 1.22) },
      cor_ceu: { value: new T.Vector3(0.85, 0.93, 1) }, dir_sol: { value: m.v3(PARA_SOL).normalize() },
      verniz: { value: 0.24 },
    });
    const comp = 0.1 - Z_FIM_DECK;
    const deck = new T.PlaneGeometry(MEIA_LARGURA * 2, comp);
    deck.rotateX(-Math.PI / 2);
    this._malha(deck, this.matPista, [0, 0, 0.1 - comp / 2]);
    // área de aproximação (onde o bichinho corre): madeira leve
    this.matPiso = m._novo(SH.piso, {
      madeira: { value: this.tex.madeira }, escala_uv: { value: new T.Vector2(4.2, 3.2) },
      tom: { value: new T.Vector3(0.86, 0.69, 0.52) }, luz_cena: { value: new T.Vector3(1.2, 1.2, 1.22) },
      cor_ceu: { value: new T.Vector3(0.85, 0.93, 1) }, verniz: { value: 0.15 }, pulso: { value: 0 },
    });
    const piso = new T.PlaneGeometry(6.6, 6.2);
    piso.rotateX(-Math.PI / 2);
    this._malha(piso, this.matPiso, [0, -0.001, 3.2]);
    this.matFaixa = m.toon("#FF9F2E");
    for (const s of [-1, 1]) this.caixa([0.12, 0.04, 6.2], [s * 3.3, 0, 3.2], this.matFaixa);
    // canaletas: meia-cana de verdade, mais escura no fundo da calha
    this.matCanaleta = m._novo(SH.canaleta, {
      cor_a: { value: new T.Vector3() }, cor_b: { value: new T.Vector3() }, cor_c: { value: new T.Vector3() },
      luz_cena: { value: new T.Vector3(1.2, 1.2, 1.22) }, centro: { value: MEIA_LARGURA + CANALETA / 2 },
      modo: { value: 0 }, fase: { value: 0 }, onda1: { value: 0 }, onda2: { value: 0 }, bolhas: { value: 0 },
    }, { vertexColors: true });
    const geoCanaleta = extrudar(T, Perfis.canaleta(CANALETA / 2), Z_FIM_DECK, 0.1, { sombreado: [-0.15, -0.005, 0.5, 1.05] });
    this.matDivisoria = m.toon("#FFB627", { borda: 0.25, especular: 0.4 });
    const matLuzDiv = m.toon("#FFFFFF", { emissao: [0.35, 0.85, 1.0], borda: 0 });
    const geoCap = extrudar(T, Perfis.retangulo(0.32, 0.34, 0.06, 0, -0.07), Z_PINO1 + 0.2, 0.1);
    for (const s of [-1, 1]) {
      const c = this._malha(geoCanaleta, this.matCanaleta, [s * (MEIA_LARGURA + CANALETA / 2), 0, 0]);
      c.name = "canaleta";
      const xc = s * (MEIA_LARGURA + CANALETA + 0.036 + 0.16);
      this._malha(geoCap, this.matDivisoria, [xc, 0, 0]);
      this.caixa([0.05, 0.012, -Z_PINO1 - 0.3], [xc, 0.104, (Z_PINO1 + 0.2) / 2 + 0.05], matLuzDiv);
    }
    // para-choques listrados de doce: um tubo de cada lado
    this.matBumper = m._novo(SH.doce, {
      ...m.palco, cor_a: { value: new T.Vector3(1, 1, 1) }, cor_b: { value: new T.Vector3(1, 0.23, 0.31) },
      listras_por_metro: { value: 4 }, giro: { value: 1 }, faixa: { value: 0.08 }, borda: { value: 0.35 },
      especular: { value: 0.5 },
    });
    const contornoB = m.contorno(0.003, { usa_cor_vertice: 0 });
    const tubo = tuboDoce(T, 0.07, -0.6 - (N_BUMPERS - 1) * 0.96 - 0.57, -0.6 + 0.57, 24, 0.4, 6);
    comCor(T, tubo);
    this.bumpers = new T.Group();
    this.raiz.add(this.bumpers);
    for (const s of [-1, 1]) {
      for (const mat of [this.matBumper, contornoB]) {
        const b = new T.Mesh(this._g(tubo), mat);
        b.rotation.x = Math.PI / 2;
        b.position.set(s * 0.735, 0.1, 0);
        b.updateMatrix();
        b.matrixAutoUpdate = false;
        this.bumpers.add(b);
      }
    }
  }

  // ---------------------------------------------------------------- fundo dos pinos
  _fundoDosPinos() {
    const T = this.T;
    const m = this.mats;
    const fosso = m.toon("#16336E", { borda: 0.3 });
    this.matParede = m.toon("#2A63C4", { borda: 0.3, especular: 0.25 });
    this.matFriso = m.toon("#FFB627", { borda: 0.25, especular: 0.5 });
    this.matGabinete = m.toon("#E8384F", { borda: 0.35, especular: 0.12, luz_minima: 0.3 });
    const zFrente = Z_PINO1 + 0.9;
    for (const s of [-1, 1]) {
      const x = s * (MEIA_LARGURA + CANALETA + 0.09);
      this.peca(Perfis.retangulo(0.12, 1.0, 0.05, x, 0.35), Z_FUNDO, zFrente, this.matParede);
      this.peca(Perfis.retangulo(0.17, 0.07, 0.034, x, 0.875), Z_FUNDO, zFrente + 0.02, this.matFriso);
    }
    // chão do fosso, atrás da pista (mais baixo que ela)
    this.caixa([2.0, 0.2, Z_FIM_DECK - Z_FUNDO], [0, Y_CHAO_FOSSO - 0.1, (Z_FIM_DECK + Z_FUNDO) / 2], fosso);
    this._cacapa();
    // cortina pregueada (estrelinhas + halo atrás dos pinos) em cima da boca
    this.matCortina = m._novo(SH.cortina, {
      cor_a: { value: new T.Vector3() }, cor_b: { value: new T.Vector3() }, cor_halo: { value: new T.Vector3() },
      fase: { value: 0 },
    });
    this._malha(cortinaPregueada(T, 2.2, 1.95, 11, 0.07), this.matCortina, [0, Y_BOCA + 0.08 + 0.975, Z_FUNDO + 0.04]);
    // teto escuro do fosso
    this.caixa([2.3, 0.1, -Z_FUNDO + Z_PINO1 + 0.7], [0, 2.12, (Z_PINO1 + 0.7 + Z_FUNDO) / 2], m.toon("#0B1B3A", { borda: 0 }));
    // gabinete por fora: laterais, teto e fundo (esconde a máquina)
    const zTras = Z_FUNDO - 0.95;
    const zMasc = Z_PINO1 + 0.68;
    for (const s of [-1, 1]) this.peca(Perfis.retangulo(0.34, 3.7, 0.12, s * 1.23, 1.55), zTras + 0.3, zMasc, this.matGabinete);
    this.peca(Perfis.retangulo(2.8, 0.32, 0.1, 0, 3.24), zTras + 0.3, zMasc, this.matGabinete);
    this.peca(Perfis.retangulo(2.9, 3.75, 0.22, 0, 1.53), zTras, zTras + 0.35, this.matGabinete);
    this.peca(Perfis.retangulo(2.96, 0.09, 0.04, 0, 3.42), zTras - 0.03, zMasc, this.matFriso);
    // letreiro (iluminado por dentro) com o logo e lâmpadas
    this.matPlaca = m.toon("#1E3FA0", { borda: 0.15, luz_minima: 1.0 });
    this.peca(Perfis.retangulo(2.7, 0.95, 0.07, 0, 1.85), Z_PINO1 + 0.68, Z_PINO1 + 0.82, this.matPlaca);
    this.peca(Perfis.retangulo(2.8, 1.05, 0.09, 0, 1.85), Z_PINO1 + 0.66, Z_PINO1 + 0.78, this.matFriso);
    this.matLogo = m._novo(SH.logo, { textura: { value: this.tex.logo } }, { transparent: true });
    const asp = 1024 / 416;
    const lw = Math.min(2.5, 0.86 * asp);
    this._malha(new T.PlaneGeometry(lw, lw / asp), this.matLogo, [0, 1.86, Z_PINO1 + 0.83]);
    // ARCO em cima do letreiro: leque de raios nas cores do cenário
    this.matPortal = m._novo(SH.raios, {
      cor_a: { value: new T.Vector3(1, 0.76, 0.1) }, cor_b: { value: new T.Vector3(0.91, 0.22, 0.31) },
      pulso: { value: 0 },
    }, { vertexColors: true });
    this.peca(Perfis.arco(1.42, 2.22, 2.45, 0.86), Z_PINO1 + 0.69, Z_PINO1 + 0.79, m.toon("#2A1E3A", { borda: 0.2 }));
    this._malha(lequeRaios(T, 1.42, 2.22, 2.45, 0.86, 22, Z_PINO1 + 0.792), this.matPortal);
    this.peca(Perfis.arco(1.52, 2.2, 2.45, 0.96), Z_PINO1 + 0.66, Z_PINO1 + 0.76, this.matFriso);
    // lâmpadas: contorno do letreiro e do arco
    const pontos = [];
    const zc = Z_PINO1 + 0.83;
    for (let i = 0; i < 26; i++) pontos.push([-1.3 + i * 0.104, 1.41, zc]);
    for (let i = 0; i < 9; i++) {
      pontos.push([-1.33, 1.41 + i * 0.11, zc]);
      pontos.push([1.33, 1.41 + i * 0.11, zc]);
    }
    for (let i = 0; i < 31; i++) {
      const a = Math.PI * i / 30;
      pontos.push([Math.cos(a) * 1.47, 2.45 + Math.sin(a) * 0.91, zc - 0.02]);
    }
    this.matLampadas = m._novo(SH.lampadas, { fase: { value: 0 }, modo: { value: 0 }, intensidade: { value: 1.6 } });
    this.raiz.add(this.lampadasEm(pontos));
  }

  /** Fileira de lâmpadas (uma malha instanciada) com o material comum. */
  lampadasEm(pontos, fase0 = 0) {
    const T = this.T;
    // cada fileira tem a sua esfera (8 x 4 gomos): o número de cada lâmpada
    // (a ordem do pisca) é um atributo da cópia
    const g = this._g(new T.SphereGeometry(0.07, 8, 4));
    const mm = new T.InstancedMesh(g, this.matLampadas, pontos.length);
    const mat = new T.Matrix4();
    const cor = new T.Color();
    const numero = new Float32Array(pontos.length);
    for (let i = 0; i < pontos.length; i++) {
      mat.makeScale(0.75, 0.75, 0.75).setPosition(pontos[i][0], pontos[i][1], pontos[i][2]);
      mm.setMatrixAt(i, mat);
      const c = hex(CORES_LAMPADAS[i % CORES_LAMPADAS.length]);
      cor.setRGB(c[0], c[1], c[2], T.LinearSRGBColorSpace);
      mm.setColorAt(i, cor);
      numero[i] = i + fase0;
    }
    g.setAttribute("numero", new T.InstancedBufferAttribute(numero, 1));
    mm.frustumCulled = false;
    return mm;
  }

  // ---------------------------------------------------------------- caçapa das bolas
  _cacapa() {
    const T = this.T;
    const m = this.mats;
    const escuro = m.toon("#05070D", { borda: 0, luz_minima: 1 });
    const borracha = m.toon("#20263A", { borda: 0.3, luz_minima: 0.35 });
    const meia = LARGURA_BOCA / 2;
    const alto = Y_BOCA - Y_CHAO_FOSSO;
    const fundo = 1.0;
    this.caixa([LARGURA_BOCA + 0.2, 0.2, fundo], [0, Y_CHAO_FOSSO - 0.1, Z_FUNDO - fundo / 2], escuro);
    for (const s of [-1, 1]) this.caixa([0.1, alto + 0.1, fundo], [s * (meia + 0.05), Y_CHAO_FOSSO + alto / 2, Z_FUNDO - fundo / 2], escuro);
    this.caixa([LARGURA_BOCA + 0.2, 0.1, fundo], [0, Y_BOCA + 0.05, Z_FUNDO - fundo / 2], escuro);
    this.caixa([LARGURA_BOCA + 0.2, alto + 0.2, 0.1], [0, Y_CHAO_FOSSO + alto / 2, Z_FUNDO - fundo - 0.05], escuro);
    for (const s of [-1, 1]) {
      const x0 = meia + 0.06;
      const x1 = MEIA_LARGURA + CANALETA + 0.06;
      this.caixa([x1 - x0, alto + 0.14, 0.12], [s * (x0 + x1) / 2, Y_CHAO_FOSSO + (alto + 0.14) / 2 - 0.07, Z_FUNDO - 0.02], borracha);
    }
    this.peca(Perfis.retangulo(LARGURA_BOCA + 0.26, 0.12, 0.05, 0, Y_BOCA + 0.06), Z_FUNDO - 0.04, Z_FUNDO + 0.1, this.matFriso);
    for (const s of [-1, 1]) {
      this.peca(Perfis.retangulo(0.13, alto + 0.12, 0.05, s * (meia + 0.065), Y_CHAO_FOSSO + (alto + 0.12) / 2 - 0.02),
        Z_FUNDO - 0.04, Z_FUNDO + 0.1, this.matFriso);
    }
    this.matBocaLuz = m.toon("#FFFFFF", { emissao: [0.6, 0.9, 1.0], borda: 0 });
    this.caixa([LARGURA_BOCA, 0.025, 0.02], [0, Y_BOCA + 0.005, Z_FUNDO + 0.105], this.matBocaLuz);
    // cortina de tiras de borracha: abrem (giram para dentro) quando a bola passa
    const larg = LARGURA_BOCA / N_TIRAS - 0.012;
    const tira = comCor(T, new T.BoxGeometry(larg, alto - 0.03, 0.012));
    tira.translate(0, -(alto - 0.03) / 2, 0);
    this.tiras = new T.InstancedMesh(this._g(tira), m.toon("#151A28", { borda: 0.25, luz_minima: 0.3 }), N_TIRAS);
    this.tiras.frustumCulled = false;
    this.raiz.add(this.tiras);
    this._mexerTiras(0);
  }

  _mexerTiras(dt) {
    const T = this.T;
    if (!this._mt) this._mt = new T.Matrix4();
    const meia = LARGURA_BOCA / 2;
    const pb = this.bolaPos;
    let mexeu = dt <= 0;
    for (let i = 0; i < N_TIRAS; i++) {
      const x = -meia + LARGURA_BOCA * (i + 0.5) / N_TIRAS;
      let alvo = 0;
      if (pb && Math.abs(pb.z - Z_FUNDO) < 0.8 && Math.abs(pb.x - x) < 0.3 && pb.y < Y_BOCA) alvo = 1.25;
      const a = this.aberturaTiras[i];
      const vel = alvo > a ? 14 : 2.2;
      const novo = a < alvo ? Math.min(alvo, a + dt * vel) : Math.max(alvo, a - dt * vel);
      if (novo !== a || mexeu) {
        this.aberturaTiras[i] = novo;
        this._mt.makeRotationX(-novo).setPosition(x, Y_BOCA - 0.015, Z_FUNDO + 0.03);
        this.tiras.setMatrixAt(i, this._mt);
        mexeu = true;
      }
    }
    if (mexeu) this.tiras.instanceMatrix.needsUpdate = true;
  }

  // ---------------------------------------------------------------- colunas
  _colunas() {
    const zc = Z_PINO1 + 0.75;
    const pontos = [];
    this.matColuna = this.mats.toon("#1E62C8", { borda: 0.35, especular: 0.3 });
    for (const s of [-1, 1]) {
      const x = s * 1.93;
      this.peca(Perfis.retangulo(1.16, 3.0, 0.14, x, 1.15), zc - 0.07, zc + 0.07, this.matColuna);
      this.peca(Perfis.retangulo(1.26, 0.12, 0.05, x, 2.7), zc - 0.09, zc + 0.09, this.matFriso);
      for (let i = 0; i < 23; i++) {
        pontos.push([x - s * 0.5, 0.2 + i * 0.1, zc + 0.08]);
        pontos.push([x + s * 0.5, 0.2 + i * 0.1, zc + 0.08]);
      }
    }
    this.raiz.add(this.lampadasEm(pontos, 50));
  }

  // ---------------------------------------------------------------- área dos jogadores
  _areaDosJogadores() {
    const T = this.T;
    const m = this.mats;
    const zParede = 7.7;
    const marinho = m.toon("#123A7A", { borda: 0.3, especular: 0.2 });
    const azul = m.toon("#1E62C8", { borda: 0.3 });
    const vermelho = m.toon("#E8384F", { borda: 0.3, especular: 0.3 });
    const tapete = m.toon("#1B3E86", { borda: 0.15 });
    this.caixa([9.6, 0.06, zParede - 6.3], [0, -0.03, (6.3 + zParede) / 2], tapete);
    this.caixa([6.6, 0.065, 0.07], [0, -0.03, 6.33], this.matFriso);
    this.peca(Perfis.retangulo(9.6, 1.1, 0.12, 0, 0.55), zParede, zParede + 0.3, this.matGabinete);
    this.peca(Perfis.retangulo(9.7, 0.1, 0.05, 0, 1.12), zParede - 0.03, zParede + 0.33, this.matFriso);
    for (const s of [-1, 1]) this.peca(Perfis.retangulo(0.16, 3.0, 0.07, s * 1.9, 1.5), zParede - 0.2, zParede - 0.04, this.matColuna);
    this.peca(Perfis.retangulo(4.0, 1.75, 0.16, 0, 2.55), zParede - 0.18, zParede - 0.06, this.matPlaca);
    const lw = 3.0;
    const logo = this._malha(new T.PlaneGeometry(lw, lw * 416 / 1024), this.matLogo, null);
    logo.rotation.y = Math.PI;
    logo.position.set(0, 2.55, zParede - 0.2);
    logo.updateMatrix();
    const pontos = [];
    for (let i = 0; i < 30; i++) {
      const x = -1.85 + i * (3.7 / 29);
      pontos.push([x, 3.35, zParede - 0.21]);
      pontos.push([x, 1.75, zParede - 0.21]);
    }
    this.raiz.add(this.lampadasEm(pontos, 200));
    // sofás vermelhos encostados na mureta
    for (const s of [-1, 1]) {
      const sofa = new T.Group();
      sofa.position.set(s * 3.4, 0, zParede - 0.42);
      sofa.rotation.y = Math.PI / 2;
      this.raiz.add(sofa);
      this.peca(Perfis.retangulo(0.66, 0.42, 0.12, 0, 0.21), -1.1, 1.1, vermelho, sofa);
      this.peca(Perfis.retangulo(0.2, 0.86, 0.09, -0.27, 0.43), -1.1, 1.1, vermelho, sofa);
      for (const z of [-1.2, 1.2]) this.peca(Perfis.retangulo(0.66, 0.6, 0.1, 0, 0.3), z - 0.12, z + 0.12, marinho, sofa);
    }
    // retorno de bolas (do lado direito)
    const ret = new T.Group();
    ret.position.set(RETORNO[0], RETORNO[1], RETORNO[2]);
    this.raiz.add(ret);
    this.peca(Perfis.retangulo(0.56, 0.5, 0.1, 0, 0.25), -0.8, 0.8, marinho, ret);
    this.peca(Perfis.retangulo(0.6, 0.5, 0.24, 0, 0.62), 0.25, 0.8, azul, ret);
    this.peca(Perfis.retangulo(0.5, 0.06, 0.03, 0, 0.53), -0.78, 0.3, this.matFriso, ret);
    const geoBola = comCor(T, new T.SphereGeometry(0.13, 24, 12));
    ["#169BD5", "#FF7A21", "#2DBE4E"].forEach((c, i) => {
      this._malha(geoBola, m.toon(c, { borda: 0.4, especular: 0.8 }), [0, 0.69, -0.62 + i * 0.29], ret);
    });
  }

  // ---------------------------------------------------------------- pódios
  _podios() {
    const T = this.T;
    const m = this.mats;
    this.podios = [];
    this.matsPodio = [];
    const geoBase = comCor(T, new T.CylinderGeometry(0.4, 0.45, 0.14, 48, 1));
    const geoTampa = comCor(T, new T.CylinderGeometry(0.37, 0.37, 0.012, 48, 1));
    const geoAro = comCor(T, new T.TorusGeometry(0.3875, 0.0175, 10, 64).rotateX(Math.PI / 2));
    for (let i = 0; i < 2; i++) {
      const g = new T.Group();
      g.visible = false;
      this.raiz.add(g);
      const base = new T.Mesh(this._g(geoBase), m.toon(i === 0 ? COR_BOB : COR_MIA, { borda: 0.35 }));
      base.position.y = 0.07;
      g.add(base);
      const tampa = new T.Mesh(this._g(geoTampa), m.toon("#F4F8FF", { borda: 0.2 }));
      tampa.position.y = 0.146;
      g.add(tampa);
      const ma = m.toon("#FFD43B", { borda: 0, emissao: [0, 0, 0] });
      const aro = new T.Mesh(this._g(geoAro), ma);
      aro.position.y = 0.142;
      g.add(aro);
      this.podios.push(g);
      this.matsPodio.push(ma);
    }
    this.podioEscala = [1, 1];
  }

  /** Liga/desliga os pódios e acende o do escolhido. */
  mostrarPodios(ligar, destaque = -1) {
    for (let i = 0; i < 2; i++) {
      const g = this.podios[i];
      if (ligar && !g.visible) this.podioEscala[i] = 0;
      g.visible = ligar;
      g.position.set(PODIOS[i][0], PODIOS[i][1], PODIOS[i][2]);
    }
    this.podioDestaque = destaque;
  }

  definirProtecao(ligada) {
    this.bumpers.visible = ligada;
  }

  acenderPista(ligar) {
    this.luzAlvo = ligar ? 1 : 0;
  }

  /** Modo das lâmpadas: 0 corrida, 1 piscando todas (strike!), 2 alternado. */
  lampadas(modo) {
    this.matLampadas.uniforms.modo.value = modo;
  }

  // ---------------------------------------------------------------- tema
  aplicarTema(nome) {
    const c = TEMAS[nome] || TEMAS.parque;
    this.tema = nome;
    const u = this.matCeu.uniforms;
    u.cor_topo.value.set(...hex(c.ceu[0]));
    u.cor_meio.value.set(...hex(c.ceu[1]));
    u.cor_horizonte.value.set(...hex(c.ceu[2]));
    u.cor_chao.value.set(...hex(c.ceu[3]));
    u.cor_sol.value.set(...hex(c.cor_sol || "#FFF2BF"));
    u.forca_sol.value = c.forca_sol ?? 1.0;
    u.estrelas.value = c.estrelas ?? 0;
    u.cor_nebulosa.value.set(...hex(c.nebulosa || "#E666FF"));
    u.raios.value = c.raios ?? 0;
    this.corFundo = hex(c.ceu[2]);
    const luzCena = this.mats.definirLuz(c);
    const luzTela = linear(luzCena);
    this.matPista.uniforms.luz_cena.value.set(...luzTela);
    this.matPiso.uniforms.luz_cena.value.set(...luzCena);
    const ceu1 = hex(c.ceu[1]);
    const ceu2 = hex(c.ceu[2]);
    const corCeu = [0, 1, 2].map((i) => mistura(ceu1[i], ceu2[i], 0.55));
    this.matPista.uniforms.cor_ceu.value.set(...corCeu);
    this.matPiso.uniforms.cor_ceu.value.set(...corCeu);
    this.matCortina.uniforms.cor_a.value.set(...hex(c.fundo[0]));
    this.matCortina.uniforms.cor_b.value.set(...hex(c.fundo[1]));
    this.matCortina.uniforms.cor_halo.value.set(...hex(c.halo));
    this.matBocaLuz.uniforms.emissao.value.set(...hex(c.halo).map((v) => v * 0.9));
    this.matPlaca.uniforms.tinta.value.set(...hex(c.placa));
    this.matPista.uniforms.cor_luz.value.set(...hex(c.neon));
    this.matPista.uniforms.cor_reflexo_a.value.set(...hex(c.portal[0]));
    this.matPista.uniforms.cor_reflexo_b.value.set(...hex(c.portal[1]));
    this.matPortal.uniforms.cor_a.value.set(...hex(c.portal[0]));
    this.matPortal.uniforms.cor_b.value.set(...hex(c.portal[1]));
    this.matGabinete.uniforms.tinta.value.set(...hex(c.gabinete));
    this.matColuna.uniforms.tinta.value.set(...hex(c.coluna));
    this.matParede.uniforms.tinta.value.set(...hex(c.parede));
    this.matDivisoria.uniforms.tinta.value.set(...hex(c.divisoria));
    this.matFaixa.uniforms.tinta.value.set(...hex(c.faixa));
    const cu = this.matCanaleta.uniforms;
    cu.modo.value = c.canaleta_modo;
    cu.cor_a.value.set(...hex(c.canaleta[0]));
    cu.cor_b.value.set(...hex(c.canaleta[1]));
    cu.cor_c.value.set(...hex(c.canaleta[2]));
    cu.luz_cena.value.set(...luzCena);
    this.matBumper.uniforms.cor_a.value.set(...hex(c.bumper[0]));
    this.matBumper.uniforms.cor_b.value.set(...hex(c.bumper[1]));
    const tu = this.matTerreno.uniforms;
    tu.modo.value = c.chao_modo;
    tu.detalhe.value = this.tex["chao_" + c.chao_modo];
    tu.detalhe_tile.value = LADRILHO_CHAO[c.chao_modo];
    ["lin_a", "lin_b", "lin_c", "lin_d"].forEach((k, i) => tu[k].value.set(...linear(hex(c.chao[i]))));
    this._mostrarAstro(nome);
  }

  // ---------------------------------------------------------------- animação
  atualizar(dt) {
    this.t = (this.t + dt) % 3600;
    const t = this.t;
    this.luz = this.luz < this.luzAlvo ? Math.min(this.luzAlvo, this.luz + dt * 2.5) : Math.max(this.luzAlvo, this.luz - dt * 2.5);
    const p = this.matPista.uniforms;
    p.luz.value = this.luz;
    p.fase.value = (t * 2.2) % 1;
    p.fase_lenta.value = (t * 0.75) % 1;
    p.bola_z.value = this.bolaZ;
    this.matPiso.uniforms.pulso.value = 0.5 + 0.5 * Math.sin(t * 3.1);
    this.matLampadas.uniforms.fase.value = (t * 0.9) % 100;
    this.matCortina.uniforms.fase.value = (t * 0.4) % 100;
    this.matPortal.uniforms.pulso.value = Math.sin(t * 2.2);
    this.matAstro.uniforms.tempo.value = t;
    const cu = this.matCanaleta.uniforms;
    cu.fase.value = (t * 0.9) % 1;
    cu.onda1.value = (t * 1.3) % TAU;
    cu.onda2.value = (t * 0.9) % TAU;
    cu.bolhas.value = (t * 0.35) % 3.52;
    this._mexerTiras(dt);
    for (let i = 0; i < 2; i++) {
      const g = this.podios[i];
      if (!g.visible) continue;
      this.podioEscala[i] = Math.min(1, this.podioEscala[i] + dt / 0.35);
      const e = mistura(0.2, 1, voltaElastica(this.podioEscala[i]));
      g.scale.set(1, e, 1);
      const on = i === this.podioDestaque ? 0.75 + 0.25 * Math.sin(t * 6) : 0;
      this.matsPodio[i].uniforms.emissao.value.set(on * 1.6, on * 0.75 * 1.6, on * 0.15 * 1.6);
    }
  }

  liberar() {
    for (const g of this.geometrias) g.dispose();
    this.geometrias.length = 0;
  }
}

/* ----------------------------------------------------------------------
   PARTÍCULAS (scripts/efeitos.gd e as CPUParticles3D do jogo): estrelas,
   faíscas, poeira, confete, bolhas, fumaça e fogos. Cada textura é UM
   desenho (pontos com tamanho, cor e giro); a conta é feita aqui, sem
   criar nada novo a cada quadro (o estoque de cada tipo é fixo).
   ---------------------------------------------------------------------- */
const CURVAS = {
  constante: (u) => 1,
  some: (u) => 1 - u,
  estrela: (u) => (u < 0.75 ? 1 : 1 - (u - 0.75) / 0.25),
  poeira: (u) => (u < 0.3 ? mistura(0.4, 1.0, u / 0.3) : mistura(1.0, 1.3, (u - 0.3) / 0.7)),
  chama: (u) => (u < 0.3 ? mistura(0.6, 1.0, u / 0.3) : 1 - (u - 0.3) / 0.7),
  vulcao: (u) => mistura(0.4, 1.6, u),
};
const LISTA_CURVAS = Object.keys(CURVAS);

class Particulas {
  constructor(THREE, tex) {
    this.T = THREE;
    this.tipos = {};
    this.raiz = new THREE.Group();
    const tipos = [
      ["estrela", tex.estrela, false, 700],
      ["faisca", tex.faisca, true, 700],
      ["fumaca", tex.fumaca, false, 260],
      ["fogo", tex.fumaca, true, 140],
      ["confete", tex.confete, false, 500],
      ["bolha", tex.bolha, false, 160],
    ];
    this.escala = { value: 800 };
    // maior ponto na tela (px do 3D): 9% da altura
    this.tamanhoMax = { value: 90 };
    for (const [nome, textura, somar, n] of tipos) {
      const g = new THREE.BufferGeometry();
      const pos = new Float32Array(n * 3);
      const cor = new Float32Array(n * 4);
      const tg = new Float32Array(n * 2);
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
      g.setAttribute("cor", new THREE.BufferAttribute(cor, 4).setUsage(THREE.DynamicDrawUsage));
      g.setAttribute("tamgiro", new THREE.BufferAttribute(tg, 2).setUsage(THREE.DynamicDrawUsage));
      g.setDrawRange(0, 0);
      const m = new THREE.ShaderMaterial({
        uniforms: { textura: { value: textura }, somar: { value: somar ? 1 : 0 }, escala_tela: this.escala, tamanho_max: this.tamanhoMax },
        vertexShader: SH.particula.vertex,
        fragmentShader: SH.particula.fragment,
        transparent: true,
        depthWrite: false,
        blending: somar ? THREE.AdditiveBlending : THREE.NormalBlending,
      });
      const pontos = new THREE.Points(g, m);
      pontos.frustumCulled = false;
      pontos.renderOrder = 10;
      this.raiz.add(pontos);
      this.tipos[nome] = {
        n, ativos: 0, g, m, pos, cor, tg,
        vel: new Float32Array(n * 3), grav: new Float32Array(n * 3), amort: new Float32Array(n),
        vida: new Float32Array(n), total: new Float32Array(n), tam: new Float32Array(n),
        curva: new Uint8Array(n), cor0: new Float32Array(n * 4), cor1: new Float32Array(n * 4),
        giro: new Float32Array(n), vgiro: new Float32Array(n),
      };
    }
    this.ritmo = 1;
  }

  /** Uma partícula nova (some a mais velha se o estoque acabou). */
  _nova(tipo, p, v, o) {
    const t = this.tipos[tipo];
    let i = t.ativos;
    if (i >= t.n) {
      i = Math.floor(Math.random() * t.n);
    } else {
      t.ativos++;
    }
    t.pos[i * 3] = p[0];
    t.pos[i * 3 + 1] = p[1];
    t.pos[i * 3 + 2] = p[2];
    t.vel[i * 3] = v[0];
    t.vel[i * 3 + 1] = v[1];
    t.vel[i * 3 + 2] = v[2];
    const g = o.grav || [0, 0, 0];
    t.grav[i * 3] = g[0];
    t.grav[i * 3 + 1] = g[1];
    t.grav[i * 3 + 2] = g[2];
    t.amort[i] = o.amort || 0;
    t.total[i] = o.vida;
    t.vida[i] = o.vida;
    t.tam[i] = o.tam;
    t.curva[i] = LISTA_CURVAS.indexOf(o.curva || "constante");
    const c0 = o.cor || [1, 1, 1, 1];
    const c1 = o.cor_fim || c0;
    for (let k = 0; k < 4; k++) {
      t.cor0[i * 4 + k] = c0[k] ?? 1;
      t.cor1[i * 4 + k] = c1[k] ?? 1;
    }
    t.giro[i] = o.giro ?? Math.random() * TAU;
    t.vgiro[i] = o.vgiro ?? 0;
  }

  /** Direção sorteada num cone em volta de `dir` (graus). */
  _direcao(dir, espalha, saida) {
    const a = espalha * GRAU * Math.sqrt(Math.random());
    const b = Math.random() * TAU;
    const T = this.T;
    if (!this._v) {
      this._v = new T.Vector3();
      this._u = new T.Vector3();
      this._w = new T.Vector3();
    }
    const d = this._v.set(dir[0], dir[1], dir[2]).normalize();
    const u = Math.abs(d.y) < 0.9 ? this._u.set(0, 1, 0) : this._u.set(1, 0, 0);
    u.cross(d).normalize();
    const w = this._w.copy(d).cross(u);
    const s = Math.sin(a);
    saida[0] = d.x * Math.cos(a) + (u.x * Math.cos(b) + w.x * Math.sin(b)) * s;
    saida[1] = d.y * Math.cos(a) + (u.y * Math.cos(b) + w.y * Math.sin(b)) * s;
    saida[2] = d.z * Math.cos(a) + (u.z * Math.cos(b) + w.z * Math.sin(b)) * s;
    return saida;
  }

  _arco() {
    const c = hex(sortear(ARCO_IRIS));
    return [c[0], c[1], c[2], 1];
  }

  /** Explosão de estrelas coloridas (strike, spare) + faíscas. */
  estrelas(pos, qtd = 30, forca = 1) {
    const d = [0, 0, 0];
    for (let i = 0; i < qtd; i++) {
      this._direcao([0, 1, 0], 80, d);
      const v = aleat(2.5, 5.0) * forca;
      this._nova("estrela", pos, [d[0] * v, d[1] * v, d[2] * v], {
        vida: 1.3 * aleat(0.85, 1), tam: 0.16 * aleat(0.6, 1.3), curva: "estrela", grav: [0, -6, 0],
        cor: this._arco(), vgiro: aleat(-7, 7),
      });
    }
    for (let i = 0; i < 20; i++) {
      this._direcao([0, 1, 0], 180, d);
      const v = aleat(1.5, 3.5);
      this._nova("faisca", pos, [d[0] * v, d[1] * v, d[2] * v], {
        vida: 0.6, tam: 0.22, curva: "some", amort: 4, cor: [1, 0.95, 0.7, 1],
      });
    }
  }

  /** Poeirinha no chão (impacto da bola nos pinos). */
  poeira(pos, forca = 1) {
    const d = [0, 0, 0];
    const n = Math.floor(10 * forca) + 4;
    for (let i = 0; i < n; i++) {
      this._direcao([0, 1, 0], 85, d);
      const v = aleat(0.4, 1.4 * forca);
      this._nova("fumaca", pos, [d[0] * v, d[1] * v, d[2] * v], {
        vida: 0.8, tam: 0.35 * aleat(0.6, 1.2), curva: "poeira", grav: [0, 0.3, 0], amort: 2,
        cor: [1, 1, 1, 0.85], cor_fim: [1, 0.95, 1, 0],
      });
    }
  }

  /** Chuva de confete (posição e largura da área). */
  confete(pos, largura = 3, qtd = 120) {
    const d = [0, 0, 0];
    for (let i = 0; i < qtd; i++) {
      const p = [pos[0] + aleat(-largura, largura), pos[1] + aleat(-0.2, 0.2), pos[2] + aleat(-largura * 0.5, largura * 0.5)];
      this._direcao([0, 1, 0], 60, d);
      const v = aleat(1.5, 4.0);
      this._nova("confete", p, [d[0] * v, d[1] * v, d[2] * v], {
        vida: 3.2 * aleat(0.7, 1), tam: 0.07 * aleat(0.8, 1.4), grav: [0, -2.2, 0], amort: 1.2,
        cor: this._arco(), vgiro: aleat(-12, 12),
      });
    }
  }

  /** Fogos de artifício: um estouro. */
  fogo(pos) {
    const c = this._arco();
    const d = [0, 0, 0];
    for (let i = 0; i < 46; i++) {
      this._direcao([0, 1, 0], 180, d);
      const v = aleat(3.0, 3.6);
      this._nova("faisca", pos, [d[0] * v, d[1] * v, d[2] * v], {
        vida: 1.4, tam: 0.18, curva: "some", grav: [0, -2, 0], amort: 1.4, cor: c,
      });
    }
  }

  /** Brilhinhos de arco-íris em volta da bola rolando (ou chamas na bola de fogo). */
  brilhoBola(pos, raio, fogo) {
    const d = [0, 0, 0];
    this._direcao([0, 1, 0], 70, d);
    const p = [pos[0] + aleat(-raio, raio), pos[1] + aleat(-raio, raio), pos[2] + aleat(-raio, raio)];
    const v = aleat(0.3, 0.9);
    const cor = fogo ? hex(sortear(["#FFF3B0", "#FFD43B", "#FF9F2E", "#FF5A1E"])).concat(1) : this._arco();
    this._nova("faisca", p, [d[0] * v, d[1] * v, d[2] * v], {
      vida: 0.7, tam: 0.09 * aleat(0.5, 1), curva: "some", grav: [0, -0.6, 0], cor,
    });
  }

  chama(pos, raio) {
    const d = [0, 0, 0];
    this._direcao([0, 1, 0], 25, d);
    const p = [pos[0] + aleat(-raio, raio) * 0.8, pos[1] + aleat(-raio, raio) * 0.8, pos[2] + aleat(-raio, raio) * 0.8];
    const v = aleat(0.6, 1.4);
    this._nova("fogo", p, [d[0] * v, d[1] * v, d[2] * v], {
      vida: 0.45, tam: 0.2 * aleat(0.7, 1.3), curva: "chama", grav: [0, 1.5, 0],
      cor: [1, 0.85, 0.4, 1], cor_fim: [0.9, 0.15, 0.05, 0],
    });
  }

  /** Estrelinhas subindo em volta do bichinho (comemorações). */
  festa(pos) {
    const a = Math.random() * TAU;
    const r = aleat(0.25, 0.42);
    const d = [0, 0, 0];
    this._direcao([0, 1, 0], 25, d);
    const v = aleat(1.0, 2.2);
    this._nova("estrela", [pos[0] + Math.cos(a) * r, pos[1] + 0.25 + aleat(-0.05, 0.05), pos[2] + Math.sin(a) * r],
      [d[0] * v, d[1] * v, d[2] * v], {
        vida: 0.9, tam: 0.09 * aleat(0.6, 1.2), curva: "some", grav: [0, -1.5, 0], cor: this._arco(),
        vgiro: aleat(-5, 5),
      });
  }

  bolha(pos) {
    const d = [0, 0, 0];
    this._direcao([0, 1, 0], 12, d);
    const v = aleat(0.5, 0.9);
    const r = 0.25 * Math.cbrt(Math.random());
    const a = Math.random() * TAU;
    this._nova("bolha", [pos[0] + Math.cos(a) * r, pos[1], pos[2] + Math.sin(a) * r], [d[0] * v, d[1] * v, d[2] * v], {
      vida: 4, tam: 0.16 * aleat(0.4, 1.4), grav: [0, 0.25, 0], cor: [0.85, 1, 1, 0.85], cor_fim: [0.85, 1, 1, 0.0], giro: 0,
    });
  }

  fumacaVulcao(pos) {
    const d = [0, 0, 0];
    this._direcao([0.25, 1, 0], 18, d);
    const v = aleat(0.8, 1.3);
    this._nova("fumaca", pos, [d[0] * v, d[1] * v, d[2] * v], {
      vida: 5, tam: 2.4 * aleat(0.8, 1.6), curva: "vulcao", grav: [0.15, 0.15, 0],
      cor: [0.95, 0.9, 0.95, 0.85], cor_fim: [0.85, 0.85, 0.95, 0],
    });
  }

  cadente(pos) {
    const p = [pos[0] + aleat(-14, 14), pos[1] + aleat(-3, 3), pos[2] + aleat(-8, 8)];
    const d = [0, 0, 0];
    this._direcao([1, -0.35, 0], 5, d);
    const v = aleat(14, 18);
    this._nova("faisca", p, [d[0] * v, d[1] * v, d[2] * v], { vida: 1.6, tam: 0.6, curva: "some", cor: [1, 0.95, 0.8, 1] });
  }

  limpar() {
    for (const t of Object.values(this.tipos)) {
      t.ativos = 0;
      t.g.setDrawRange(0, 0);
    }
  }

  atualizar(dt, alturaTelaPx, fovGraus) {
    this.escala.value = alturaTelaPx / (2 * Math.tan(fovGraus * GRAU * 0.5));
    this.tamanhoMax.value = alturaTelaPx * 0.09;
    for (const t of Object.values(this.tipos)) {
      let i = 0;
      while (i < t.ativos) {
        t.vida[i] -= dt;
        if (t.vida[i] <= 0) {
          // tira trocando com a última viva
          const j = t.ativos - 1;
          if (j !== i) {
            for (let k = 0; k < 3; k++) {
              t.pos[i * 3 + k] = t.pos[j * 3 + k];
              t.vel[i * 3 + k] = t.vel[j * 3 + k];
              t.grav[i * 3 + k] = t.grav[j * 3 + k];
            }
            for (let k = 0; k < 4; k++) {
              t.cor0[i * 4 + k] = t.cor0[j * 4 + k];
              t.cor1[i * 4 + k] = t.cor1[j * 4 + k];
            }
            t.amort[i] = t.amort[j];
            t.vida[i] = t.vida[j];
            t.total[i] = t.total[j];
            t.tam[i] = t.tam[j];
            t.curva[i] = t.curva[j];
            t.giro[i] = t.giro[j];
            t.vgiro[i] = t.vgiro[j];
          }
          t.ativos--;
          continue;
        }
        const am = Math.max(0, 1 - t.amort[i] * dt);
        for (let k = 0; k < 3; k++) {
          t.vel[i * 3 + k] = (t.vel[i * 3 + k] + t.grav[i * 3 + k] * dt) * am;
          t.pos[i * 3 + k] += t.vel[i * 3 + k] * dt;
        }
        const u = 1 - t.vida[i] / t.total[i];
        for (let k = 0; k < 4; k++) t.cor[i * 4 + k] = mistura(t.cor0[i * 4 + k], t.cor1[i * 4 + k], u);
        t.giro[i] += t.vgiro[i] * dt;
        t.tg[i * 2] = t.tam[i] * CURVAS[LISTA_CURVAS[t.curva[i]]](u);
        t.tg[i * 2 + 1] = t.giro[i];
        i++;
      }
      t.g.setDrawRange(0, t.ativos);
      if (t.ativos > 0) {
        t.g.attributes.position.needsUpdate = true;
        t.g.attributes.cor.needsUpdate = true;
        t.g.attributes.tamgiro.needsUpdate = true;
      }
    }
  }

  liberar() {
    for (const t of Object.values(this.tipos)) {
      t.g.dispose();
      t.m.dispose();
    }
  }
}

/* ----------------------------------------------------------------------
   OS CENÁRIOS (scripts/temas.gd): a decoração de cada fase vem num pacote
   próprio (strike-kids/cenario_<fase>), baixado só quando a fase aparece.
   As peças paradas viram UMA malha (como o Lote.juntar do jogo); as que
   se mexem (roda-gigante, carrossel, nuvens, balões, peixes, águas-vivas,
   tartarugas, pterossauros, dinos, disco voador...) têm a animação do
   temas.gd.
   ---------------------------------------------------------------------- */
class Cenarios {
  constructor(THREE, mats, mundo, particulas) {
    this.T = THREE;
    this.mats = mats;
    this.mundo = mundo;
    this.particulas = particulas;
    this.grupos = {};
    this.pedidos = {};
    this.itens = {};
    this.emissores = {};
    this.atual = "";
    this.t = 0;
    this.geometrias = [];
    this.matsTinta = {};
    this.marcas = {};
    this._q = new THREE.Quaternion();
    this._q2 = new THREE.Quaternion();
    this._eixoZ = new THREE.Vector3(0, 0, 1);
    this._eixoY = new THREE.Vector3(0, 1, 0);
  }

  /** Começa a baixar a decoração de uma fase (devolve a promessa). */
  pedir(nome) {
    if (!this.pedidos[nome]) {
      this.pedidos[nome] = carregarPacote(this.T, "cenario_" + nome)
        .then((pac) => this._montar(nome, pac))
        .catch((erro) => {
          console.warn("Strike Kids: cenário não carregou", nome, erro);
          this.grupos[nome] = new this.T.Group();
          this.itens[nome] = [];
          this.emissores[nome] = [];
          this.mundo.raiz.add(this.grupos[nome]);
        });
    }
    return this.pedidos[nome];
  }

  pronto(nome) {
    return !!this.grupos[nome];
  }

  _matTinta(tinta, extra = null) {
    const chave = (tinta || "#FFFFFF") + (extra ? JSON.stringify(extra) : "");
    if (!this.matsTinta[chave]) {
      const lin = linear(hex(tinta || "#FFFFFF"));
      this.matsTinta[chave] = this.mats.leve(lin, extra || {});
    }
    return this.matsTinta[chave];
  }

  _matriz(item, alvo) {
    const T = this.T;
    const e = new T.Euler(item.r[0], item.r[1], item.r[2], "YXZ");
    alvo.compose(new T.Vector3(item.p[0], item.p[1], item.p[2]), new T.Quaternion().setFromEuler(e),
      new T.Vector3(item.e, item.e, item.e));
    return alvo;
  }

  _montar(nome, pac) {
    // (chegou depois de o jogo fechar: nada a montar)
    if (this.liberado) return;
    const T = this.T;
    const grupo = new T.Group();
    grupo.visible = false;
    this.mundo.raiz.add(grupo);
    for (const g of Object.values(pac.malhas)) this.geometrias.push(g);
    const info = pac.info;
    // 1) as paradas numa malha só (a tinta de cada cópia vai para a cor)
    let nv = 0;
    let ni = 0;
    for (const it of info.paradas) {
      const g = pac.malhas[it.m];
      if (!g) continue;
      nv += g.attributes.position.count;
      ni += g.index.count;
    }
    if (nv > 0) {
      const pos = new Float32Array(nv * 3);
      const nor = new Float32Array(nv * 3);
      const cor = new Uint8Array(nv * 4);
      const idx = nv > 65535 ? new Uint32Array(ni) : new Uint16Array(ni);
      const m4 = new T.Matrix4();
      const m3 = new T.Matrix3();
      const v = new T.Vector3();
      let ov = 0;
      let oi = 0;
      for (const it of info.paradas) {
        const g = pac.malhas[it.m];
        if (!g) continue;
        this._matriz(it, m4);
        m3.getNormalMatrix(m4);
        const p = g.attributes.position.array;
        const n = g.attributes.normal.array;
        const c = g.attributes.color.array;
        const k = g.attributes.position.count;
        const tin = it.t ? linear(hex(it.t)).map(Math.sqrt) : [1, 1, 1];
        for (let j = 0; j < k; j++) {
          v.set(p[j * 3], p[j * 3 + 1], p[j * 3 + 2]).applyMatrix4(m4);
          pos[(ov + j) * 3] = v.x;
          pos[(ov + j) * 3 + 1] = v.y;
          pos[(ov + j) * 3 + 2] = v.z;
          v.set(n[j * 3], n[j * 3 + 1], n[j * 3 + 2]).applyMatrix3(m3).normalize();
          nor[(ov + j) * 3] = v.x;
          nor[(ov + j) * 3 + 1] = v.y;
          nor[(ov + j) * 3 + 2] = v.z;
          cor[(ov + j) * 4] = Math.round(c[j * 4] * tin[0]);
          cor[(ov + j) * 4 + 1] = Math.round(c[j * 4 + 1] * tin[1]);
          cor[(ov + j) * 4 + 2] = Math.round(c[j * 4 + 2] * tin[2]);
          cor[(ov + j) * 4 + 3] = c[j * 4 + 3];
        }
        const ix = g.index.array;
        for (let j = 0; j < ix.length; j++) idx[oi + j] = ix[j] + ov;
        ov += k;
        oi += ix.length;
      }
      const geo = new T.BufferGeometry();
      geo.setAttribute("position", new T.BufferAttribute(pos, 3));
      geo.setAttribute("normal", new T.BufferAttribute(nor, 3));
      geo.setAttribute("color", new T.BufferAttribute(cor, 4, true));
      geo.setIndex(new T.BufferAttribute(idx, 1));
      geo.computeBoundingSphere();
      this.geometrias.push(geo);
      const malha = new T.Mesh(geo, this._matTinta("#FFFFFF"));
      malha.matrixAutoUpdate = false;
      grupo.add(malha);
    }
    // 2) as que se mexem
    const itens = [];
    for (const it of info.animadas) {
      const a = it.a;
      const extra = it.m === "nuvem" ? { borda: 0.6, luz_minima: 0.5, cor_borda: [0.9, 0.96, 1] }
        : it.m === "balao" ? { borda: 0.6 } : null;
      const malha = new T.Mesh(pac.malhas[it.m], this._matTinta(it.t, extra));
      malha.rotation.order = "YXZ";
      malha.position.set(it.p[0], it.p[1], it.p[2]);
      malha.rotation.set(it.r[0], it.r[1], it.r[2]);
      malha.scale.setScalar(it.e);
      const item = { tipo: a.tipo, no: malha, a, base: malha.position.clone(), giro: it.r[1], rot: malha.rotation.clone(), escala: it.e };
      if (a.tipo === "roda") {
        // a roda gira em volta do eixo; as cabines ficam sempre de pé
        const rg = new T.Group();
        rg.position.copy(malha.position);
        rg.rotation.y = it.r[1];
        const eixo = new T.Group();
        eixo.position.y = a.eixo;
        rg.add(eixo);
        malha.position.set(0, 0, 0);
        malha.rotation.set(0, 0, 0);
        eixo.add(malha);
        item.cabines = a.cabines.map((tinta) => {
          const c = new T.Mesh(pac.malhas.cabine, this._matTinta(tinta));
          c.rotation.order = "YXZ";
          eixo.add(c);
          return c;
        });
        grupo.add(rg);
      } else {
        grupo.add(malha);
      }
      if (a.fio) {
        // o fio do balão
        const fio = new T.Mesh(this._fio(), this._matTinta("#FFFFFF", { borda: 0 }));
        fio.position.y = -0.45;
        malha.add(fio);
      }
      itens.push(item);
    }
    for (const l of info.lampadas) grupo.add(this.mundo.lampadasEm(l.pontos, l.fase0));
    this.grupos[nome] = grupo;
    this.itens[nome] = itens;
    this.emissores[nome] = info.particulas.map((p) => ({ ...p, acumulo: Math.random() }));
    this.marcas[nome] = this._marca(nome, grupo, pac);
    if (this.atual === nome) grupo.visible = true;
    if (this.aoMontar) this.aoMontar(grupo);
  }

  /* O SÍMBOLO DA LAZER & SPORT EM TODO CENÁRIO (mundo.gd), sutil,
     flutuando ao lado da pista, cada um do jeito do cenário: o balãozinho
     (Parque), o planetinha com anel (Espaço), a bolha (Fundo do Mar) e o
     pterossauro segurando a plaquinha (Selva dos Dinos). */
  _marca(nome, grupo, pac) {
    const T = this.T;
    const m = this.mats;
    const no = new T.Group();
    no.position.set(BALAO_POS[0], BALAO_POS[1], BALAO_POS[2]);
    no.rotation.order = "YXZ";
    grupo.add(no);
    const marca = { no, escala: 1, ptero: null, bolhinhas: [] };
    const geo = (g) => {
      comCor(T, g);
      this.geometrias.push(g);
      return g;
    };
    const esfera = (gomos = 24) => geo(new T.SphereGeometry(1, gomos, gomos / 2));
    const contorno = this._contornoMarca || (this._contornoMarca = m.contorno(0.004));
    const peca = (g, mat, pos = [0, 0, 0], comContorno = true) => {
      const mi = new T.Mesh(g, mat);
      mi.position.set(pos[0], pos[1], pos[2]);
      mi.rotation.order = "YXZ";
      if (comContorno) mi.add(new T.Mesh(g, contorno));
      no.add(mi);
      return mi;
    };
    // material com a logo (sem fundo) estampada na frente da peça (+Z):
    // largura da logo nas medidas da malha; esticarY = a escala Y da peça
    const matLogo = (tinta, largura, centro = [0, 0], esticarY = 1, extra = {}) => m.personagem({
      rosto: m.tex.marca, rosto_grade: [1, 1], rosto_centro: centro,
      rosto_tamanho: [largura, largura * ASPECTO_MARCA / esticarY],
      borda: 0.4, faixa: 0.12, luz_minima: 0.38, especular: 0.3, tamanho_especular: 0.985, tinta, ...extra,
    });
    const corToon = (tinta, extra) => m.toon(tinta, { borda: 0.3, ...extra });
    if (nome === "parque") {
      marca.escala = 0.3;
      const mat = matLogo("#E8384F", 1.32, [0, 0.06], 1.12);
      const corpo = peca(esfera(), mat);
      corpo.scale.set(1, 1.12, 1);
      peca(geo(new T.CylinderGeometry(0.025, 0.09, 0.14, 12)), mat, [0, -1.17, 0]);
      peca(geo(new T.CylinderGeometry(0.012, 0.012, 4.2, 6)), corToon("#FFFFFF", { borda: 0, luz_minima: 0.6 }), [0, -1.24 - 2.1, 0], false);
    } else if (nome === "espaco") {
      marca.escala = 0.27;
      peca(esfera(), matLogo("#7B61FF", 1.3, [0, 0], 1, { borda: 0.7, cor_borda: "#9FE8FF" }));
      // o anel passa por baixo da logo (inclinado para a frente); o toro do
      // Godot fica deitado (em volta de Y), o do three em pé
      const toro = new T.TorusGeometry((1.32 + 1.62) / 2, (1.62 - 1.32) / 2, 8, 48);
      toro.rotateX(Math.PI / 2);
      const anel = peca(geo(toro), corToon("#FFD43B", { borda: 0.5, luz_minima: 0.5 }));
      anel.rotation.set(32 * Math.PI / 180, 0, -12 * Math.PI / 180);
      anel.scale.set(1, 0.35, 1);
    } else if (nome === "mar") {
      marca.escala = 0.3;
      peca(esfera(), matLogo("#C9F4FF", 1.25, [0, 0], 1,
        { borda: 1.3, cor_borda: "#FFFFFF", luz_minima: 0.75, especular: 0.45, tamanho_especular: 0.985 }));
      const mb = corToon("#DDF8FF", { borda: 1.4, cor_borda: [1, 1, 1], luz_minima: 0.8 });
      const g = esfera(12);
      for (let i = 0; i < 4; i++) {
        const b = peca(g, mb, [0, 0, 0], false);
        b.scale.setScalar(0.12 + 0.05 * (i % 2));
        marca.bolhinhas.push(b);
      }
    } else {
      // Selva dos Dinos: o pterossauro batendo asas com a plaquinha
      peca(geo(new T.BoxGeometry(0.74, 0.52, 0.05)), corToon("#7A4A22", { borda: 0.25 }), [0, 0, -0.012]);
      peca(geo(new T.BoxGeometry(0.68, 0.46, 0.05)), matLogo("#FFE9C2", 0.62, [0, 0], 1, { borda: 0.2, especular: 0 }), [0, 0, 0], false);
      const mc = corToon("#5A3A1A", { borda: 0, luz_minima: 0.5 });
      const corda = geo(new T.CylinderGeometry(0.006, 0.006, 0.36, 5));
      for (const lado of [-1, 1]) peca(corda, mc, [lado * 0.17, 0.4, 0], false).rotation.z = lado * 0.45;
      if (pac.malhas.ptero) {
        const pt = peca(pac.malhas.ptero, this._matTinta("#FFFFFF", { borda: 0.3 }), [0, 0.66, 0.02], false);
        pt.scale.setScalar(0.62);
        marca.ptero = pt;
      }
    }
    no.scale.setScalar(marca.escala);
    return marca;
  }

  /** O símbolo flutua — sobe e desce, vai e volta e balança (_mexer_marca). */
  _mexerMarca(nome, t) {
    const mc = this.marcas[nome];
    if (!mc) return;
    const no = mc.no;
    no.position.set(BALAO_POS[0] + Math.sin(t * 0.31) * 0.18, BALAO_POS[1] + Math.sin(t * 0.8) * 0.14, BALAO_POS[2] + Math.sin(t * 0.23) * 0.1);
    if (nome === "espaco") {
      no.rotation.set(Math.sin(t * 0.4) * 0.06, Math.sin(t * 0.3) * 0.35, Math.sin(t * 0.5) * 0.05);
    } else if (nome === "mar") {
      const pulso = Math.sin(t * 2.0);
      no.rotation.set(0, Math.sin(t * 0.35) * 0.25, Math.sin(t * 0.6) * 0.06);
      no.scale.set((1 + pulso * 0.03) * mc.escala, (1 - pulso * 0.03) * mc.escala, (1 + pulso * 0.03) * mc.escala);
      for (let i = 0; i < mc.bolhinhas.length; i++) {
        // sobem em volta da bolha e recomeçam embaixo
        const f = ((t * 0.22 + i * 0.25) % 1 + 1) % 1;
        const a = i * 1.9 + t * 0.4;
        mc.bolhinhas[i].position.set(Math.cos(a) * 1.25, -1.0 + f * 3.4, Math.sin(a) * 0.5 + 0.3);
        mc.bolhinhas[i].visible = f < 0.92;
      }
    } else if (nome === "dinos") {
      no.rotation.set(Math.sin(t * 0.7) * 0.05, Math.sin(t * 0.4) * 0.22, Math.sin(t * 0.9) * 0.06);
      if (mc.ptero) {
        // bate asas: o corpo sobe e desce um tiquinho, inclinando
        mc.ptero.position.y = 0.66 + Math.sin(t * 5.0) * 0.025;
        mc.ptero.rotation.x = Math.sin(t * 5.0) * 0.08;
      }
    } else {
      no.rotation.set(Math.sin(t * 0.5) * 0.05, Math.sin(t * 0.45) * 0.3, Math.sin(t * 0.6) * 0.08);
    }
  }

  _fio() {
    if (!this._geoFio) {
      this._geoFio = comCor(this.T, new this.T.CylinderGeometry(0.004, 0.004, 0.9, 4, 1));
      this.geometrias.push(this._geoFio);
    }
    return this._geoFio;
  }

  mostrar(nome) {
    this.atual = nome;
    for (const k of Object.keys(this.grupos)) this.grupos[k].visible = k === nome;
  }

  atualizar(dt) {
    const nome = this.atual;
    if (!this.grupos[nome]) return;
    this.t = (this.t + dt) % 3600;
    const t = this.t;
    this._mexerMarca(nome, t);
    for (const it of this.itens[nome]) {
      const no = it.no;
      const a = it.a;
      switch (it.tipo) {
        case "girar":
          no.rotation.y += a.vel * dt;
          break;
        case "nuvem":
          no.position.x += a.vel * dt;
          if (no.position.x > 30) no.position.x = -30;
          break;
        case "boiar": {
          const f = a.fase;
          const v = a.vel;
          no.position.set(it.base.x + Math.sin(t * 0.5 * v + f) * a.amp[0], it.base.y + Math.sin(t * 0.9 * v + f * 2) * a.amp[1], it.base.z);
          if (a.balanco) no.rotation.z = Math.sin(t * 0.7 * v + f) * a.balanco;
          if (a.vira) no.rotation.y = a.olhar + Math.sin(t * 0.6 * v + f) * a.vira;
          break;
        }
        case "girar_proprio":
          if (!it.eixo) it.eixo = new this.T.Vector3(a.eixo[0], a.eixo[1], a.eixo[2]).normalize();
          no.rotateOnAxis(it.eixo, a.vel * dt);
          break;
        case "passeio": {
          const ang = t * a.vel;
          no.position.set(a.centro[0] + Math.sin(ang) * a.raio[0], a.centro[1] + Math.sin(2 * ang) * a.raio[1],
            a.centro[2] + Math.cos(ang) * a.raio[2]);
          it.ang = ((it.ang || 0) + a.girar * dt) % TAU;
          this._q.setFromAxisAngle(this._eixoZ, -Math.cos(ang) * 0.2);
          this._q2.setFromAxisAngle(this._eixoY, it.ang);
          no.quaternion.copy(this._q).multiply(this._q2);
          break;
        }
        case "roda": {
          no.rotation.z += a.vel * dt;
          const n = it.cabines.length;
          for (let i = 0; i < n; i++) {
            const ang = no.rotation.z + TAU * i / n;
            it.cabines[i].position.set(Math.cos(ang) * a.raio, Math.sin(ang) * a.raio, 0);
            it.cabines[i].rotation.z = Math.sin(t * 1.3 + i) * 0.06;
          }
          break;
        }
        case "alga":
          no.rotation.set(it.rot.x + Math.sin(t * 0.8 + a.fase) * 0.07, it.rot.y, it.rot.z + Math.sin(t * 1.1 + a.fase * 1.7) * 0.09);
          break;
        case "peixe": {
          const v = a.vel;
          const ang = t * v - a.fase * sinal(v);
          no.position.set(a.centro[0] + Math.cos(ang) * a.raio[0], a.centro[1] + Math.sin(t * 1.7 + a.nado) * 0.12,
            a.centro[2] + Math.sin(ang) * a.raio[1]);
          const dx = -Math.sin(ang) * a.raio[0] * sinal(v);
          const dz = Math.cos(ang) * a.raio[1] * sinal(v);
          no.rotation.y = Math.atan2(dx, dz) + Math.sin(t * 9 + a.nado) * 0.12;
          break;
        }
        case "agua_viva": {
          const p = Math.sin(t * 2.2 * a.vel + a.fase);
          no.position.y = it.base.y + Math.sin(t * 0.6 * a.vel + a.fase) * 0.5;
          no.scale.set((1 + p * 0.06) * it.escala, (1 - p * 0.08) * it.escala, (1 + p * 0.06) * it.escala);
          break;
        }
        case "atravessar":
          no.position.x += a.vel * dt;
          if (no.position.x > a.limite) no.position.x = -a.limite;
          else if (no.position.x < -a.limite) no.position.x = a.limite;
          no.position.y += Math.sin(t * 0.8) * 0.003;
          break;
        case "respirar":
          no.rotation.y = it.giro + Math.sin(t * 0.35 + a.fase) * 0.12;
          no.rotation.z = Math.sin(t * 0.9 + a.fase) * 0.025;
          break;
        case "voo": {
          const v = a.vel;
          const ang = t * v + a.fase;
          no.position.set(a.centro[0] + Math.cos(ang) * a.raio, a.centro[1] + Math.sin(t * 1.4 + a.fase) * 0.4,
            a.centro[2] + Math.sin(ang) * a.raio);
          no.rotation.set(0, Math.atan2(-Math.sin(ang) * sinal(v), Math.cos(ang) * sinal(v)), -sinal(v) * 0.35 + Math.sin(t * 3) * 0.05);
          break;
        }
        default:
          break;
      }
    }
    // partículas do cenário: bolhas subindo, fumaça do vulcão, estrelas cadentes
    if (this.particulas) {
      for (const e of this.emissores[nome]) {
        e.acumulo += dt;
        if (e.tipo === "bolhas" && e.acumulo > 0.4) {
          e.acumulo = 0;
          this.particulas.bolha(e.pos);
        } else if (e.tipo === "fumaca" && e.acumulo > 0.36) {
          e.acumulo = 0;
          this.particulas.fumacaVulcao(e.pos);
        } else if (e.tipo === "cadentes" && e.acumulo > 0.55) {
          e.acumulo = 0;
          this.particulas.cadente(e.pos);
        }
      }
    }
  }

  liberar() {
    this.liberado = true;
    for (const g of this.geometrias) g.dispose();
    this.geometrias.length = 0;
  }
}

/* ----------------------------------------------------------------------
   A BOLA (scripts/bola.gd): textura do bichinho, rastro de arco-íris no
   chão, brilhinhos, sombrinha; com 2 ou mais strikes seguidos vira BOLA
   DE FOGO.
   ---------------------------------------------------------------------- */
const RAIO_BOLA = 0.14;
const MASSA_BOLA = 6.5;
const FOGO = ["#FFF3B0", "#FFD43B", "#FF9F2E", "#FF5A1E", "#E0301E"];
const N_RASTRO = 28;

function criarMatBola(mats, tex, nome) {
  return mats._novo(SH.bola, {
    ...mats.palco,
    textura: { value: tex["bola_" + nome] }, faixa: { value: 0.08 }, borda: { value: 0.28 },
    cor_borda: { value: mats.cor([1.0, 0.95, 0.88]) }, brilho: { value: 1.6 }, aceso: { value: 0 },
  });
}

class Bola {
  constructor(THREE, mats, tex, particulas, raiz) {
    this.T = THREE;
    this.particulas = particulas;
    this.mats = { bob: criarMatBola(mats, tex, "bob"), mia: criarMatBola(mats, tex, "mia") };
    this.geo = comCor(THREE, new THREE.SphereGeometry(RAIO_BOLA, 32, 16));
    this.malha = new THREE.Mesh(this.geo, this.mats.bob);
    this.casca = new THREE.Mesh(this.geo, mats.contorno(0.0025, { usa_cor_vertice: 0 }));
    this.no = new THREE.Group();
    this.no.add(this.malha);
    this.no.add(this.casca);
    raiz.add(this.no);
    this.geoSombra = comCor(THREE, new THREE.PlaneGeometry(0.42, 0.42).rotateX(-Math.PI / 2));
    this.sombra = new THREE.Mesh(this.geoSombra, mats.sombra(0.6));
    this.sombra.renderOrder = 1;
    raiz.add(this.sombra);
    // rastro: fita no chão (2 vértices por ponto), soma luz
    const g = new THREE.BufferGeometry();
    this.rastroPos = new Float32Array(N_RASTRO * 2 * 3);
    this.rastroCor = new Float32Array(N_RASTRO * 2 * 4);
    g.setAttribute("position", new THREE.BufferAttribute(this.rastroPos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("cor", new THREE.BufferAttribute(this.rastroCor, 4).setUsage(THREE.DynamicDrawUsage));
    const idx = [];
    for (let i = 0; i < N_RASTRO - 1; i++) {
      const a = i * 2;
      idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
    g.setIndex(idx);
    g.setDrawRange(0, 0);
    this.geoRastro = g;
    const mr = new THREE.ShaderMaterial({
      vertexShader: SH.rastro.vertex, fragmentShader: SH.rastro.fragment, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    });
    this.matRastro = mr;
    this.rastro = new THREE.Mesh(g, mr);
    this.rastro.frustumCulled = false;
    this.rastro.renderOrder = 2;
    raiz.add(this.rastro);
    this.pontos = [];
    for (let i = 0; i < N_RASTRO; i++) this.pontos.push(new THREE.Vector3());
    this.nPontos = 0;
    this.arco = ["#FF4B5C", "#FF9F2E", "#FFE14D", "#5ED16A", "#4FC3F7", "#2E7BFF"].map(hex);
    this.fogoCores = FOGO.map(hex);
    this.fogoLigado = false;
    this.brilhos = false;
    this.acc = 0;
    this.accFogo = 0;
    this.pos = new THREE.Vector3(0, -5, 20);
    this.vel = new THREE.Vector3();
    this.giro = new THREE.Quaternion();
    this.curva = 0;
    this.rolando = false;
    this.emReplay = false;
    this.ritmo = 1;
    this.guardar();
  }

  vestir(nome) {
    this.malha.material = this.mats[nome] || this.mats.bob;
    this.nomeAtual = nome;
  }

  acender(v) {
    for (const m of Object.values(this.mats)) m.uniforms.aceso.value = v;
  }

  fogo(ligar) {
    this.fogoLigado = ligar;
  }

  lancar(origem, vel, efeito) {
    this.pos.copy(origem);
    this.vel.copy(vel);
    this.giro.identity();
    this.curva = efeito;
    this.rolando = true;
    this.emReplay = false;
    this.no.visible = true;
    this.nPontos = 0;
    this.brilhos = true;
    this.ritmo = 1;
  }

  guardar() {
    this.rolando = false;
    this.emReplay = false;
    this.no.visible = false;
    this.sombra.visible = false;
    this.pos.set(0, -5, 20);
    this.vel.set(0, 0, 0);
    this.nPontos = 0;
    this.geoRastro.setDrawRange(0, 0);
    this.brilhos = false;
  }

  get visivel() {
    return this.no.visible;
  }

  /** Mais um ponto do rastro (só na pista: na canaleta e no fosso some). */
  marcarRastro(p) {
    if (Math.abs(p.x) > MEIA_LARGURA - 0.03 || p.y - RAIO_BOLA < -0.03 || p.z < Z_FIM_DECK) {
      if (this.nPontos > 0) this.nPontos--;
      return;
    }
    const ultimo = this.pontos[N_RASTRO - 1];
    for (let i = N_RASTRO - 1; i > 0; i--) this.pontos[i] = this.pontos[i - 1];
    this.pontos[0] = ultimo;
    ultimo.set(p.x, Math.max(p.y - RAIO_BOLA, 0) + 0.012, p.z);
    this.nPontos = Math.min(this.nPontos + 1, N_RASTRO);
  }

  limparRastro() {
    this.nPontos = 0;
  }

  _desenharRastro() {
    const n = this.nPontos;
    if (n < 2) {
      this.geoRastro.setDrawRange(0, 0);
      return;
    }
    for (let i = 0; i < n; i++) {
      const p = this.pontos[i];
      const q = i < n - 1 ? this.pontos[i + 1] : this.pontos[i - 1];
      let dx = i < n - 1 ? p.x - q.x : q.x - p.x;
      let dz = i < n - 1 ? p.z - q.z : q.z - p.z;
      const l = Math.hypot(dx, dz);
      if (l < 0.0001) {
        dx = 0;
        dz = -1;
      } else {
        dx /= l;
        dz /= l;
      }
      // lado = direção x CIMA
      const lx = -dz;
      const lz = dx;
      const f = 1 - i / (n - 1);
      let w = RAIO_BOLA * (this.fogoLigado ? 1.2 : 0.95) * (0.35 + 0.65 * f);
      w = lim(Math.min(w, MEIA_LARGURA - Math.abs(p.x)), 0, w);
      let c;
      if (this.fogoLigado) {
        const u = i / (n - 1) * (this.fogoCores.length - 1);
        const k = Math.min(Math.floor(u), this.fogoCores.length - 2);
        const t = u - k;
        c = [0, 1, 2].map((j) => mistura(this.fogoCores[k][j], this.fogoCores[k + 1][j], t));
      } else {
        const u = ((i / 10) % 1) * (this.arco.length - 1);
        const k = Math.min(Math.floor(u), this.arco.length - 2);
        const t = u - k;
        c = [0, 1, 2].map((j) => mistura(this.arco[k][j], this.arco[k + 1][j], t));
      }
      const a = f * 0.75;
      for (let s = 0; s < 2; s++) {
        const o = (i * 2 + s) * 3;
        const sg = s === 0 ? 1 : -1;
        this.rastroPos[o] = p.x + lx * w * sg;
        this.rastroPos[o + 1] = p.y;
        this.rastroPos[o + 2] = p.z + lz * w * sg;
        const oc = (i * 2 + s) * 4;
        this.rastroCor[oc] = c[0];
        this.rastroCor[oc + 1] = c[1];
        this.rastroCor[oc + 2] = c[2];
        this.rastroCor[oc + 3] = a;
      }
    }
    this.geoRastro.attributes.position.needsUpdate = true;
    this.geoRastro.attributes.cor.needsUpdate = true;
    this.geoRastro.setDrawRange(0, (n - 1) * 6);
  }

  /** Põe a malha no lugar (física ou replay), sombra, rastro e brilhos. */
  atualizarVisual(dt, marcar) {
    if (!this.no.visible) {
      this.sombra.visible = false;
      this.geoRastro.setDrawRange(0, 0);
      return;
    }
    const g = this.pos;
    this.no.position.copy(g);
    this.no.quaternion.copy(this.giro);
    this.sombra.visible = true;
    this.sombra.position.set(g.x, Math.max(g.y - RAIO_BOLA, -0.3) + 0.008, g.z);
    let alt = lim(1 - (g.y - RAIO_BOLA) * 1.5, 0.3, 1);
    if (g.z > Z_FIM_DECK && g.z < 0.12) alt *= lim((MEIA_LARGURA - Math.abs(g.x)) / 0.2, 0, 1);
    this.sombra.scale.set(Math.max(alt, 0.001), 1, Math.max(alt, 0.001));
    if (marcar && this.rolando) this.marcarRastro(g);
    if ((this.rolando || this.emReplay) && g.z < Z_PINO1 + 0.4) this.brilhos = false;
    if (this.brilhos && this.particulas) {
      this.acc += dt * 57 * this.ritmo;
      while (this.acc > 1) {
        this.acc -= 1;
        this.particulas.brilhoBola([g.x, g.y, g.z], RAIO_BOLA, this.fogoLigado);
      }
      if (this.fogoLigado) {
        this.accFogo += dt * 100 * this.ritmo;
        while (this.accFogo > 1) {
          this.accFogo -= 1;
          this.particulas.chama([g.x, g.y, g.z], RAIO_BOLA);
        }
      }
    }
    this._desenharRastro();
  }

  liberar() {
    this.geo.dispose();
    this.geoSombra.dispose();
    this.geoRastro.dispose();
    this.matRastro.dispose();
  }
}

/* ----------------------------------------------------------------------
   OS 10 PINOS (scripts/pinos.gd, pino.gd) e a FÍSICA LEVE da queda.

   O jogo de verdade usa a física Jolt; aqui uma física pequena feita para
   esta pista: cada pino é um corpo rígido (massa 1,5 kg, centro de massa a
   17 cm da base, como o do jogo) com 5 esferas no perfil e o anel da base
   (fica em pé apoiado nela); a bola é uma esfera de 6,5 kg. Choques por
   impulsos sequenciais (com atrito e quique), contra a pista, a canaleta
   (meia-cana), os para-choques, as paredes da caçapa, o fosso e a barra
   varredora da máquina. A jogada vem da TABELA de jogadas calibrada do
   jogo: ela diz por onde a bola passa e quais pinos costumam cair; a
   física mostra a queda (e às vezes cai um a mais ou a menos, como no
   boliche de verdade).

   Numeração oficial (vista de quem joga):
            7   8   9   10
              4   5   6
                2   3
                  1
   ---------------------------------------------------------------------- */
const MASSA_PINO = 1.5;
const CM_PINO = 0.17;
const ESFERAS_PINO = [[0.07, 0.064], [0.15, 0.084], [0.24, 0.068], [0.325, 0.036], [0.425, 0.046]];
const N_ANEL = 8;
const RAIO_ANEL = 0.034;
const I_PINO = [0.022, 0.0035, 0.022];
const EXPR_PINO = ["normal", "piscando", "medo", "tonto", "feliz", "surpreso", "triste", "bravo"];
const GRAVIDADE = 9.8;
const PAREDE_X = MEIA_LARGURA + CANALETA + 0.09 - 0.06;
const PAREDE_TRAS = Z_FUNDO + 0.04;

class Corpo {
  constructor(THREE) {
    this.p = new THREE.Vector3();
    this.q = new THREE.Quaternion();
    this.v = new THREE.Vector3();
    this.w = new THREE.Vector3();
    this.dinamico = false;
    this.invM = 0;
    this.parado = 0;
  }
}

class Fisica {
  constructor(THREE) {
    this.T = THREE;
    const V = () => new THREE.Vector3();
    this.tmp = Array.from({ length: 16 }, V);
    this.contatos = [];
    for (let i = 0; i < 240; i++) {
      this.contatos.push({ a: null, b: null, p: V(), n: V(), prof: 0, ra: V(), rb: V(), acN: 0, acT1: 0, acT2: 0,
        t1: V(), t2: V(), kN: 0, kT1: 0, kT2: 0, alvo: 0, mu: 0.4 });
    }
    this.nContatos = 0;
    this.m3 = new THREE.Matrix3();
    this.barra = null;
  }

  /** I⁻¹ (do mundo) aplicado a um vetor, para o corpo b. */
  invI(b, x, saida) {
    if (!b || !b.dinamico || b.ehBola) return saida.set(0, 0, 0);
    // R · diag(1/I) · Rᵀ · x
    const qi = this._qi || (this._qi = new this.T.Quaternion());
    qi.copy(b.q).invert();
    saida.copy(x).applyQuaternion(qi);
    saida.set(saida.x / I_PINO[0], saida.y / I_PINO[1], saida.z / I_PINO[2]);
    return saida.applyQuaternion(b.q);
  }

  novoContato(a, b, ponto, normal, prof, mu) {
    if (this.nContatos >= this.contatos.length) return;
    const c = this.contatos[this.nContatos++];
    c.a = a;
    c.b = b;
    c.p.copy(ponto);
    c.n.copy(normal);
    c.prof = prof;
    c.mu = mu;
  }

  /** Contatos de uma esfera (centro c, raio r) com o mundo parado. */
  mundo(corpo, c, r, ehBola, protecao) {
    const tmp = this.tmp[10];
    const n = this.tmp[11];
    const ax = Math.abs(c.x);
    const muChao = ehBola ? 0.0 : 0.42;
    // pista (deck): plano y = 0
    if (ax <= MEIA_LARGURA && c.z >= Z_FIM_DECK && c.z <= 1.2) {
      if (c.y - r < 0) this.novoContato(corpo, null, tmp.set(c.x, 0, c.z), n.set(0, 1, 0), r - c.y, muChao);
    } else if (ax > MEIA_LARGURA && ax < MEIA_LARGURA + CANALETA + 0.05 && c.z >= Z_FIM_DECK && c.z <= 0.1) {
      // canaleta: meia-cana (eixo em x = ±0,8, y = -0,018, raio 0,125)
      const cx = sinal(c.x) * (MEIA_LARGURA + CANALETA / 2);
      const yc = -0.018;
      if (c.y < yc + 0.02) {
        const dx = c.x - cx;
        const dy = c.y - yc;
        const d = Math.hypot(dx, dy) || 1e-6;
        const rc = CANALETA / 2;
        if (d + r > rc) this.novoContato(corpo, null, tmp.set(cx + dx / d * rc, yc + dy / d * rc, c.z), n.set(-dx / d, -dy / d, 0), d + r - rc, 0.2);
      }
    }
    // fosso: chão mais baixo atrás da pista
    if (c.z < Z_FIM_DECK && ax < 1.0) {
      if (c.y - r < Y_CHAO_FOSSO) this.novoContato(corpo, null, tmp.set(c.x, Y_CHAO_FOSSO, c.z), n.set(0, 1, 0), Y_CHAO_FOSSO - (c.y - r), ehBola ? 0.0 : 0.9);
      // a beirada do fim da pista
      if (c.y < -0.005 && c.z > Z_FIM_DECK - r && ax < MEIA_LARGURA) {
        this.novoContato(corpo, null, tmp.set(c.x, c.y, Z_FIM_DECK), n.set(0, 0, -1), r - (Z_FIM_DECK - c.z), 0.3);
      }
    }
    // paredes laterais da caçapa (acolchoadas)
    if (c.z < Z_PINO1 + 0.9 && c.y < 0.95) {
      if (ax + r > PAREDE_X) this.novoContato(corpo, null, tmp.set(sinal(c.x) * PAREDE_X, c.y, c.z), n.set(-sinal(c.x), 0, 0), ax + r - PAREDE_X, 0.3);
    }
    // parede do fundo: a bola passa por baixo (a boca da caçapa)
    const passa = ehBola && ax < LARGURA_BOCA / 2 - r * 0.5 && c.y < Y_BOCA;
    if (!passa && c.z - r < PAREDE_TRAS && c.z > PAREDE_TRAS - 0.6) {
      this.novoContato(corpo, null, tmp.set(c.x, c.y, PAREDE_TRAS), n.set(0, 0, 1), PAREDE_TRAS - (c.z - r), 0.5);
    }
    // para-choques (cilindros listrados ao longo da pista)
    if (protecao && c.z < 0.0 && c.z > -9.84) {
      const bx = sinal(c.x) * 0.735;
      const dx = c.x - bx;
      const dy = c.y - 0.1;
      const d = Math.hypot(dx, dy) || 1e-6;
      if (d < r + 0.075) this.novoContato(corpo, null, tmp.set(bx + dx / d * 0.075, 0.1 + dy / d * 0.075, c.z), n.set(dx / d, dy / d, 0), r + 0.075 - d, 0.1);
    }
    // a barra varredora da máquina (quando desce)
    const b = this.barra;
    if (b && b.ativa && ax < MEIA_LARGURA + 0.15 && Math.abs(c.y - b.y) < 0.085 + r) {
      const frente = b.z - 0.035;
      if (c.z > frente - r && c.z < b.z + 0.035 + r) {
        this.novoContato(corpo, b.corpo, tmp.set(c.x, c.y, frente), n.set(0, 0, -1), c.z - (frente - r), 0.3);
      }
    }
  }

  /** Um passo: integra os corpos dinâmicos e resolve os choques. */
  passo(h, pinos, bola, protecao) {
    const T = this.T;
    const tmp = this.tmp;
    // 1) forças e integração
    const corpos = pinos.corpos;
    for (const b of corpos) {
      if (!b.dinamico) continue;
      b.v.y -= GRAVIDADE * h;
      b.v.multiplyScalar(Math.max(0, 1 - 0.05 * h));
      b.w.multiplyScalar(Math.max(0, 1 - 0.35 * h));
      b.p.addScaledVector(b.v, h);
      const w = b.w;
      const q = b.q;
      const dq = this._dq || (this._dq = new T.Quaternion());
      dq.set(w.x * h * 0.5, w.y * h * 0.5, w.z * h * 0.5, 0).multiply(q);
      q.set(q.x + dq.x, q.y + dq.y, q.z + dq.z, q.w + dq.w).normalize();
      if (b.ajuda) this._ajudaFirme(b, h);
    }
    if (bola.dinamico) {
      const b = bola;
      b.v.y -= GRAVIDADE * h;
      if (b.curva !== 0 && b.p.z > Z_PINO1 + 1.4 && b.p.y > -0.02) b.v.x += b.curva * h;
      if (b.p.z < Z_FIM_DECK && b.p.y < 0 && b.v.z > -1.6) {
        b.v.x += -b.p.x * 3 * h;
        b.v.z += -4 * h;
      }
      b.p.addScaledVector(b.v, h);
    }
    // 2) contatos
    this.nContatos = 0;
    const centro = tmp[0];
    const centro2 = tmp[1];
    const nrm = tmp[2];
    const ponto = tmp[3];
    for (let i = 0; i < corpos.length; i++) {
      const a = corpos[i];
      if (a.removido || a.preso) continue;
      if (a.dinamico) {
        // esferas e anel da base contra o mundo
        for (const e of ESFERAS_PINO) {
          pinos.pontoMundo(a, 0, e[0], 0, centro);
          this.mundo(a, centro, e[1], false, protecao);
        }
        for (let k = 0; k < N_ANEL; k++) {
          const ang = TAU * k / N_ANEL;
          pinos.pontoMundo(a, Math.cos(ang) * RAIO_ANEL, 0.0, Math.sin(ang) * RAIO_ANEL, centro);
          if (centro.y < 0.002 && Math.abs(centro.x) <= MEIA_LARGURA && centro.z >= Z_FIM_DECK) {
            this.novoContato(a, null, ponto.set(centro.x, 0, centro.z), nrm.set(0, 1, 0), -centro.y, 0.42);
          } else if (centro.z < Z_FIM_DECK && centro.y < Y_CHAO_FOSSO + 0.002 && Math.abs(centro.x) < 1.0) {
            this.novoContato(a, null, ponto.set(centro.x, Y_CHAO_FOSSO, centro.z), nrm.set(0, 1, 0), Y_CHAO_FOSSO - centro.y, 0.9);
          }
        }
      }
      // pino x pino
      for (let j = i + 1; j < corpos.length; j++) {
        const b = corpos[j];
        if (b.removido || b.preso) continue;
        if (!a.dinamico && !b.dinamico) continue;
        if (a.p.distanceToSquared(b.p) > 0.36) continue;
        for (const ea of ESFERAS_PINO) {
          pinos.pontoMundo(a, 0, ea[0], 0, centro);
          for (const eb of ESFERAS_PINO) {
            pinos.pontoMundo(b, 0, eb[0], 0, centro2);
            const d = centro.distanceTo(centro2);
            const soma = ea[1] + eb[1];
            if (d < soma && d > 1e-6) {
              nrm.copy(centro).sub(centro2).divideScalar(d);
              ponto.copy(centro2).addScaledVector(nrm, eb[1] - (soma - d) * 0.5);
              this._acordar(a, b);
              this.novoContato(a, b, ponto, nrm, soma - d, 0.38);
            }
          }
        }
      }
      // bola x pino
      if (bola.dinamico && a.p.distanceToSquared(bola.p) < 0.36) {
        for (const ea of ESFERAS_PINO) {
          pinos.pontoMundo(a, 0, ea[0], 0, centro);
          const d = centro.distanceTo(bola.p);
          const soma = ea[1] + RAIO_BOLA;
          if (d < soma && d > 1e-6) {
            nrm.copy(centro).sub(bola.p).divideScalar(d);
            ponto.copy(bola.p).addScaledVector(nrm, RAIO_BOLA - (soma - d) * 0.5);
            this._acordar(a, bola);
            if (pinos.aoBater) pinos.aoBater(a, bola.v.length());
            this.novoContato(a, bola, ponto, nrm, soma - d, 0.12);
          }
        }
      }
    }
    if (bola.dinamico) this.mundo(bola, bola.p, RAIO_BOLA, true, protecao);
    // 3) impulsos (velocidade) e correção de posição
    this._resolver(h);
  }

  /** Um corpo parado que leva um encontrão passa a se mexer. */
  _acordar(a, b) {
    if (!a.dinamico && b.dinamico) a.acordar();
    else if (!b.dinamico && a.dinamico && !b.ehBola) b.acordar();
  }

  /** Pino que NÃO deveria cair (a tabela diz que ele fica): se só balançou
   *  (menos de ~25°), uma mola o devolve de pé — o encontrão de raspão não
   *  derruba; um choque forte de verdade derruba assim mesmo. */
  _ajudaFirme(b, h) {
    const up = this.tmp[12].set(0, 1, 0).applyQuaternion(b.q);
    if (up.y < 0.9 || b.p.y > CM_PINO + 0.05) return;
    const eixo = this.tmp[13].set(up.z, 0, -up.x);
    const ang = Math.acos(lim(up.y, -1, 1));
    if (eixo.lengthSq() > 1e-10) eixo.normalize().multiplyScalar(-ang * 70 * h);
    b.w.add(eixo);
    b.w.multiplyScalar(Math.max(0, 1 - 6 * h));
    b.v.x *= Math.max(0, 1 - 4 * h);
    b.v.z *= Math.max(0, 1 - 4 * h);
  }

  _resolver(h) {
    const tmp = this.tmp;
    const n = this.nContatos;
    const rxn = tmp[4];
    const aux = tmp[5];
    const va = tmp[6];
    const vb = tmp[7];
    for (let i = 0; i < n; i++) {
      const c = this.contatos[i];
      const a = c.a;
      const b = c.b;
      c.ra.copy(c.p).sub(a.p);
      if (b) c.rb.copy(c.p).sub(b.p);
      const invA = a.dinamico ? a.invM : 0;
      const invB = b && b.dinamico ? b.invM : 0;
      // massa efetiva na normal
      let k = invA + invB;
      if (a.dinamico && !a.ehBola) {
        rxn.copy(c.ra).cross(c.n);
        this.invI(a, rxn, aux);
        k += aux.cross(c.ra).dot(c.n);
      }
      if (b && b.dinamico && !b.ehBola) {
        rxn.copy(c.rb).cross(c.n);
        this.invI(b, rxn, aux);
        k += aux.cross(c.rb).dot(c.n);
      }
      c.kN = k > 1e-9 ? 1 / k : 0;
      // velocidade relativa no ponto
      this._velPonto(a, c.ra, va);
      if (b) this._velPonto(b, c.rb, vb);
      else vb.set(0, 0, 0);
      const vn = va.sub(vb).dot(c.n);
      const quique = a.ehBola || (b && b.ehBola) ? 0.12 : 0.38;
      c.alvo = vn < -0.6 ? -quique * vn : 0;
      c.acN = 0;
      c.acT1 = 0;
      c.acT2 = 0;
      // tangentes
      c.t1.set(c.n.y, -c.n.x, 0);
      if (c.t1.lengthSq() < 0.01) c.t1.set(0, c.n.z, -c.n.y);
      c.t1.normalize();
      c.t2.copy(c.n).cross(c.t1);
    }
    for (let it = 0; it < 8; it++) {
      for (let i = 0; i < n; i++) {
        const c = this.contatos[i];
        if (c.kN === 0) continue;
        const a = c.a;
        const b = c.b;
        this._velPonto(a, c.ra, va);
        if (b) this._velPonto(b, c.rb, vb);
        else vb.set(0, 0, 0);
        va.sub(vb);
        const vn = va.dot(c.n);
        let jn = (c.alvo - vn) * c.kN;
        const novo = Math.max(c.acN + jn, 0);
        jn = novo - c.acN;
        c.acN = novo;
        this._impulso(c, c.n, jn);
        // atrito (duas direções)
        if (c.mu > 0) {
          for (const [t, chave] of [[c.t1, "acT1"], [c.t2, "acT2"]]) {
            this._velPonto(a, c.ra, va);
            if (b) this._velPonto(b, c.rb, vb);
            else vb.set(0, 0, 0);
            const vt = va.sub(vb).dot(t);
            let jt = -vt * c.kN;
            const maxT = c.mu * c.acN;
            const acum = lim(c[chave] + jt, -maxT, maxT);
            jt = acum - c[chave];
            c[chave] = acum;
            this._impulso(c, t, jt);
          }
        }
      }
    }
    // correção de posição (sem mexer na velocidade)
    for (let i = 0; i < n; i++) {
      const c = this.contatos[i];
      const a = c.a;
      const b = c.b;
      const invA = a.dinamico ? a.invM : 0;
      const invB = b && b.dinamico ? b.invM : 0;
      const soma = invA + invB;
      if (soma <= 0) continue;
      const corr = Math.max(c.prof - 0.002, 0) * 0.45 / soma;
      if (corr <= 0) continue;
      if (invA > 0) a.p.addScaledVector(c.n, corr * invA);
      if (invB > 0) b.p.addScaledVector(c.n, -corr * invB);
    }
  }

  _velPonto(b, r, saida) {
    if (!b.dinamico) return saida.set(0, 0, 0);
    saida.copy(b.w).cross(r).add(b.v);
    return saida;
  }

  _impulso(c, dir, j) {
    if (j === 0) return;
    const a = c.a;
    const b = c.b;
    const tmp = this.tmp;
    const imp = tmp[8].copy(dir).multiplyScalar(j);
    if (a.dinamico) {
      a.v.addScaledVector(imp, a.invM);
      if (!a.ehBola) {
        const tq = tmp[9].copy(c.ra).cross(imp);
        this.invI(a, tq, tq);
        a.w.add(tq);
      }
    }
    if (b && b.dinamico) {
      b.v.addScaledVector(imp, -b.invM);
      if (!b.ehBola) {
        const tq = tmp[9].copy(c.rb).cross(imp).negate();
        this.invI(b, tq, tq);
        b.w.add(tq);
      }
    }
  }
}

class Pinos {
  constructor(THREE, mats, tex, pacote, particulas, raiz) {
    this.T = THREE;
    this.particulas = particulas;
    this.raiz = new THREE.Group();
    raiz.add(this.raiz);
    const meta = pacote.info.pino;
    const geo = pacote.malhas.pino;
    // um material por carinha (normal, piscando, medo, tonto, feliz, ...)
    this.matsExpr = EXPR_PINO.map((nome, i) => {
      const m = mats.personagem({
        rosto: tex.rosto_pino, rosto_centro: meta.rosto.centro, rosto_tamanho: meta.rosto.tamanho, rosto_grade: [4, 2],
        borda: 0.4, cor_borda: [0.92, 0.96, 1.0],
      });
      m.uniforms.rosto_celula.value.set(i % 4, Math.floor(i / 4));
      return m;
    });
    this.contorno = mats.contorno(0.0026);
    this.corpos = [];
    this.pinos = [];
    for (let n = 1; n <= 10; n++) {
      const no = new THREE.Group();
      const malha = new THREE.Mesh(geo, this.matsExpr[0]);
      const casca = new THREE.Mesh(geo, this.contorno);
      const visual = new THREE.Group();
      visual.add(malha);
      visual.add(casca);
      no.add(visual);
      this.raiz.add(no);
      const c = new Corpo(THREE);
      c.numero = n;
      c.lugar = posicaoDoPino(n);
      c.invM = 1 / MASSA_PINO;
      c.removido = false;
      c.preso = false;
      c.no = no;
      c.visual = visual;
      c.malha = malha;
      c.expr = "normal";
      c.piscarEm = aleat(1, 4);
      c.piscando = 0;
      c.tonto = false;
      c.balanco = 0;
      c.pulo = null;
      c.bravo = null;
      c.acordar = () => {
        if (c.removido || c.preso || c.dinamico) return;
        c.dinamico = true;
        c.parado = 0;
      };
      this.corpos.push(c);
    }
    // sombrinhas (uma malha instanciada) e estrelinhas da tontura
    const gs = comCor(THREE, new THREE.PlaneGeometry(0.28, 0.28).rotateX(-Math.PI / 2));
    this.geoSombra = gs;
    this.sombras = new THREE.InstancedMesh(gs, mats.sombra(0.5), 10);
    this.sombras.frustumCulled = false;
    this.sombras.renderOrder = 1;
    raiz.add(this.sombras);
    const ge = new THREE.BufferGeometry();
    this.estrelasPos = new Float32Array(30 * 3);
    this.estrelasCor = new Float32Array(30 * 4);
    this.estrelasTg = new Float32Array(30 * 2);
    ge.setAttribute("position", new THREE.BufferAttribute(this.estrelasPos, 3).setUsage(THREE.DynamicDrawUsage));
    ge.setAttribute("cor", new THREE.BufferAttribute(this.estrelasCor, 4).setUsage(THREE.DynamicDrawUsage));
    ge.setAttribute("tamgiro", new THREE.BufferAttribute(this.estrelasTg, 2).setUsage(THREE.DynamicDrawUsage));
    ge.setDrawRange(0, 0);
    this.geoEstrelas = ge;
    this.matEstrelas = new THREE.ShaderMaterial({
      uniforms: { textura: { value: tex.estrela }, somar: { value: 0 }, escala_tela: particulas.escala, tamanho_max: particulas.tamanhoMax },
      vertexShader: SH.particula.vertex, fragmentShader: SH.particula.fragment, transparent: true, depthWrite: false,
    });
    const pe = new THREE.Points(ge, this.matEstrelas);
    pe.frustumCulled = false;
    pe.renderOrder = 11;
    raiz.add(pe);
    this.tempo = 0;
    this._m = new THREE.Matrix4();
    this._v = new THREE.Vector3();
    this._v2 = new THREE.Vector3();
    this._q = new THREE.Quaternion();
    this._qb = new THREE.Quaternion();
    this.repor();
  }

  /** Ponto do pino (coordenadas do modelo, base na origem) no mundo. */
  pontoMundo(c, x, y, z, saida) {
    return saida.set(x, y - CM_PINO, z).applyQuaternion(c.q).add(c.p);
  }

  repor() {
    for (const c of this.corpos) this.recolocar(c);
  }

  recolocar(c) {
    c.removido = false;
    c.preso = false;
    c.dinamico = false;
    c.ajuda = false;
    c.p.set(c.lugar[0], CM_PINO, c.lugar[2]);
    c.q.identity();
    c.v.set(0, 0, 0);
    c.w.set(0, 0, 0);
    c.no.visible = true;
    c.visual.scale.set(1, 1, 1);
    c.visual.position.set(0, 0, 0);
    c.visual.rotation.set(0, 0, 0);
    c.tonto = false;
    c.balanco = 0;
    c.pulo = null;
    c.bravo = null;
    this.expressao(c, "normal");
  }

  tirar(c) {
    c.removido = true;
    c.dinamico = false;
    c.no.visible = false;
    c.tonto = false;
  }

  expressao(c, nome) {
    c.expr = nome;
    this._celula(c, nome);
  }

  _celula(c, nome) {
    const i = Math.max(0, EXPR_PINO.indexOf(nome));
    c.malha.material = this.matsExpr[i];
  }

  pino(n) {
    return this.corpos[n - 1];
  }

  estaCaido(c) {
    if (c.removido) return true;
    const up = this._v.set(0, 1, 0).applyQuaternion(c.q);
    if (up.y < 0.74) return true;
    if (c.p.y - CM_PINO < -0.12) return true;
    if (Math.hypot(c.p.x - c.lugar[0], c.p.z - c.lugar[2]) > 0.75) return true;
    return false;
  }

  emPe() {
    const r = [];
    for (const c of this.corpos) if (!c.removido && !this.estaCaido(c)) r.push(c.numero);
    return r;
  }

  caidosDesde(antes) {
    const agora = this.emPe();
    return antes.filter((n) => !agora.includes(n));
  }

  /** Carinha de medo quando a bola se aproxima. */
  susto(bola) {
    for (const c of this.corpos) {
      if (c.removido || this.estaCaido(c)) continue;
      if (c.p.distanceTo(bola) < 3.2 && c.expr === "normal") this.expressao(c, "medo");
    }
  }

  reviver() {
    for (const c of this.corpos) {
      if (!c.removido) {
        this.expressao(c, "normal");
        c.tonto = false;
      }
    }
  }

  todosParados() {
    for (const c of this.corpos) {
      if (c.removido || !c.dinamico) continue;
      if (c.v.length() > 0.06 || c.w.length() > 0.25) return false;
    }
    return true;
  }

  /** Depois da jogada: os caídos ficam tontos ou bravinhos; os que ficaram
   *  de pé comemoram (alguns dão pulinhos). Devolve quantos vão pular. */
  reagir() {
    const dePe = [];
    for (const c of this.corpos) {
      if (c.removido) continue;
      if (this.estaCaido(c)) {
        if (Math.random() < 0.55) {
          this.expressao(c, "tonto");
          c.tonto = true;
        } else {
          this.expressao(c, "bravo");
          c.tonto = false;
          c.bravo = { t: -aleat(0.1, 0.5) };
        }
      } else {
        dePe.push(c);
      }
    }
    const chance = lim(0.3 + dePe.length * 0.06, 0.35, 0.85);
    embaralhar(dePe);
    let pulando = 0;
    dePe.forEach((c, i) => {
      let pulos = 0;
      if (Math.random() < chance) {
        pulos = 1 + (Math.random() < 0.45 ? 1 : 0);
        pulando++;
      }
      this.expressao(c, "feliz");
      if (pulos > 0) c.pulo = { t: -(0.1 + i * 0.07), pulos };
    });
    return pulando;
  }

  /** Para a comemoração e os pulinhos (o pino volta ao lugar de onde saiu). */
  pararFesta() {
    for (const c of this.corpos) {
      c.pulo = null;
      c.bravo = null;
      c.visual.scale.set(1, 1, 1);
      c.visual.position.set(0, 0, 0);
      c.visual.rotation.set(0, 0, 0);
    }
  }

  /** Foto de todos (replay): posição e giro de cada pino. */
  foto(saida, o) {
    for (const c of this.corpos) {
      saida[o++] = c.p.x;
      saida[o++] = c.p.y;
      saida[o++] = c.p.z;
      saida[o++] = c.q.x;
      saida[o++] = c.q.y;
      saida[o++] = c.q.z;
      saida[o++] = c.q.w;
    }
    return o;
  }

  aplicarFoto(a, oa, b, ob, u) {
    for (const c of this.corpos) {
      if (!c.removido) {
        c.p.set(mistura(a[oa], b[ob], u), mistura(a[oa + 1], b[ob + 1], u), mistura(a[oa + 2], b[ob + 2], u));
        this._q.set(a[oa + 3], a[oa + 4], a[oa + 5], a[oa + 6]);
        this._qb.set(b[ob + 3], b[ob + 4], b[ob + 5], b[ob + 6]);
        c.q.copy(this._q).slerp(this._qb, u);
      }
      oa += 7;
      ob += 7;
    }
  }

  /** Desenho: malha no lugar do corpo, piscar, sombras, tontura, festa. */
  atualizarVisual(dt) {
    this.tempo += dt;
    let ne = 0;
    for (let i = 0; i < this.corpos.length; i++) {
      const c = this.corpos[i];
      if (c.removido) {
        this._m.makeScale(0, 0, 0);
        this.sombras.setMatrixAt(i, this._m);
        continue;
      }
      // a base do pino (origem do modelo) = centro de massa - R·(0, 0,17, 0)
      this.pontoMundo(c, 0, 0, 0, this._v);
      c.no.position.copy(this._v);
      c.no.quaternion.copy(c.q);
      // piscar
      if (c.piscando > 0) {
        c.piscando -= dt;
        if (c.piscando <= 0) this._celula(c, c.expr);
      } else if (c.expr === "normal" || c.expr === "feliz") {
        c.piscarEm -= dt;
        if (c.piscarEm <= 0) {
          c.piscarEm = aleat(1.5, 4.5);
          c.piscando = 0.12;
          this._celula(c, "piscando");
        }
      }
      // pulinhos de comemoração (agacha, pula, amortece)
      if (c.pulo) {
        c.pulo.t += dt;
        const t = c.pulo.t;
        const ciclo = 0.08 + 0.07 + 0.17 + 0.06 + 0.1;
        if (t > 0) {
          const k = Math.floor(t / ciclo);
          if (k >= c.pulo.pulos) {
            c.pulo = null;
            c.visual.scale.set(1, 1, 1);
            c.visual.position.set(0, 0, 0);
          } else {
            const u = t - k * ciclo;
            const hmax = k === 0 ? 0.16 : 0.1;
            let sx = 1;
            let sy = 1;
            let y = 0;
            if (u < 0.08) {
              const f = u / 0.08;
              sx = mistura(1, 1.08, f);
              sy = mistura(1, 0.86, f);
            } else if (u < 0.15) {
              const f = (u - 0.08) / 0.07;
              sx = mistura(1.08, 0.94, f);
              sy = mistura(0.86, 1.1, f);
              y = hmax * (1 - (1 - f * 0.41) ** 2);
            } else if (u < 0.32) {
              const f = (u - 0.15) / 0.17;
              const subida = 0.41 + 0.59 * f;
              y = u < 0.25 ? hmax * (1 - (1 - Math.min(1, subida)) ** 2) : hmax * (1 - ((u - 0.25) / 0.17) ** 2);
              sx = mistura(0.94, 1, f);
              sy = mistura(1.1, 1, f);
            } else if (u < 0.38) {
              const f = (u - 0.32) / 0.06;
              sx = mistura(1, 1.07, f);
              sy = mistura(1, 0.9, f);
            } else {
              const f = (u - 0.38) / 0.1;
              sx = mistura(1.07, 1, f);
              sy = mistura(0.9, 1, f);
            }
            c.visual.scale.set(sx, sy, sx);
            c.visual.position.y = Math.max(0, y);
          }
        }
      }
      // tremidinha de raiva
      if (c.bravo) {
        c.bravo.t += dt;
        const t = c.bravo.t;
        if (t > 0 && t < 0.42) c.visual.rotation.x = Math.sin(t / 0.12 * TAU) * 0.09;
        else if (t >= 0.42) {
          c.visual.rotation.x = 0;
          c.bravo = null;
        }
      }
      // sombra: some quando o pino sai do chão; deitado fica comprida
      const up = this._v2.set(0, 1, 0).applyQuaternion(c.q);
      const g = this._v;
      const deitado = 1 - Math.abs(up.y);
      let f = g.y < -0.1 ? 0 : lim(1 - g.y * 2.2, 0, 1);
      const naPista = Math.abs(g.x) < MEIA_LARGURA && g.z > Z_FIM_DECK;
      if (naPista) {
        f *= lim((MEIA_LARGURA - Math.abs(g.x)) / 0.16, 0, 1);
        const giro = Math.atan2(up.x, up.z);
        const cx = g.x + up.x * 0.19 * deitado;
        const cz = g.z + up.z * 0.19 * deitado;
        this._q.setFromAxisAngle(this._v2.set(0, 1, 0), giro);
        this._m.compose(this._v2.set(cx, 0.004, cz), this._q, this._v.set(Math.max(f * (1 + deitado * 0.2), 0.001), 1, Math.max(f * (1 + deitado * 1.6), 0.001)));
      } else {
        this._m.makeScale(0, 0, 0);
      }
      this.sombras.setMatrixAt(i, this._m);
      // estrelinhas da tontura girando em volta da cabeça
      if (c.tonto && ne < 30) {
        this.pontoMundo(c, 0, 0.52, 0, this._v);
        for (let k = 0; k < 3; k++) {
          const a = TAU * k / 3 + this.tempo * 5;
          this.estrelasPos[ne * 3] = this._v.x + Math.cos(a) * 0.1;
          this.estrelasPos[ne * 3 + 1] = this._v.y;
          this.estrelasPos[ne * 3 + 2] = this._v.z + Math.sin(a) * 0.1;
          this.estrelasCor.set([1, 0.88, 0.3, 1], ne * 4);
          this.estrelasTg[ne * 2] = 0.07;
          this.estrelasTg[ne * 2 + 1] = 0;
          ne++;
        }
      }
    }
    this.sombras.instanceMatrix.needsUpdate = true;
    this.geoEstrelas.setDrawRange(0, ne);
    if (ne > 0) {
      this.geoEstrelas.attributes.position.needsUpdate = true;
      this.geoEstrelas.attributes.cor.needsUpdate = true;
      this.geoEstrelas.attributes.tamgiro.needsUpdate = true;
    }
  }

  liberar() {
    this.geoSombra.dispose();
    this.geoEstrelas.dispose();
    this.matEstrelas.dispose();
  }
}

/* ----------------------------------------------------------------------
   O RELÓGIO DAS SEQUÊNCIAS: esperas e animações de propriedades (como os
   tweens e o _esperar do principal.gd), andando no tempo do jogo. Cada
   sequência tem um número (seq): começar outra cancela as esperas antigas.
   ---------------------------------------------------------------------- */
const FACIL = {
  linear: (t) => t,
  seno: senoIO,
  quadSai: (t) => 1 - (1 - t) * (1 - t),
  quadEntra: (t) => t * t,
  volta: voltaElastica,
  voltaEntra: voltaEntrando,
};

class Relogio {
  constructor() {
    this.esperas = [];
    this.tweens = [];
  }

  /** Espera t segundos (de jogo). Resolve true, ou false se cancelada. */
  esperar(t, cancelada) {
    return new Promise((resolver) => this.esperas.push({ t, resolver, cancelada }));
  }

  /** Anima uma função de 0 a 1 em `dur` segundos. */
  animar(dur, passo, facil = FACIL.seno) {
    return new Promise((resolver) => {
      const tw = { t: 0, dur: Math.max(dur, 1e-4), passo, facil, resolver };
      passo(0);
      this.tweens.push(tw);
    });
  }

  /** Anima a propriedade `chave` de `obj` até `alvo`. */
  tween(obj, chave, alvo, dur, facil = FACIL.seno) {
    const de = obj[chave];
    return this.animar(dur, (u) => { obj[chave] = mistura(de, alvo, facil(u)); }, FACIL.linear);
  }

  limpar() {
    for (const e of this.esperas) e.resolver(false);
    for (const t of this.tweens) t.resolver(false);
    this.esperas = [];
    this.tweens = [];
  }

  atualizar(dt) {
    if (this.tweens.length) {
      const fim = [];
      for (const tw of this.tweens) {
        tw.t += dt;
        const u = Math.min(1, tw.t / tw.dur);
        tw.passo(tw.facil(u));
        if (u >= 1) fim.push(tw);
      }
      if (fim.length) {
        this.tweens = this.tweens.filter((t) => !fim.includes(t));
        for (const tw of fim) tw.resolver(true);
      }
    }
    if (this.esperas.length) {
      const prontas = [];
      for (const e of this.esperas) {
        if (e.cancelada && e.cancelada()) {
          prontas.push([e, false]);
          continue;
        }
        e.t -= dt;
        if (e.t <= 0) prontas.push([e, true]);
      }
      if (prontas.length) {
        const fora = new Set(prontas.map((p) => p[0]));
        this.esperas = this.esperas.filter((e) => !fora.has(e));
        for (const [e, ok] of prontas) e.resolver(ok);
      }
    }
  }
}

/* ----------------------------------------------------------------------
   A MÁQUINA DE PINOS (scripts/maquina.gd), como num boliche de verdade:
   a BARRA desce na frente dos pinos, varre os caídos para o fosso e sobe;
   a MESA desce, levanta os que ficaram em pé e devolve cada um no lugar;
   na rodada nova, desce já com os 10 pinos novinhos.
   ---------------------------------------------------------------------- */
const Y_REPOUSO = 1.85;
const Y_ENCAIXE = 0.575;
const Y_LEVANTA = 0.95;
const Y_BARRA_CIMA = 1.72;
const Y_BARRA_BAIXO = 0.085;

class Maquina {
  constructor(THREE, mats, pinos, fisica, relogio, raiz) {
    this.T = THREE;
    this.pinos = pinos;
    this.fisica = fisica;
    this.relogio = relogio;
    this.rapidez = 1.25;
    this.zMesa = Z_PINO1 - FILEIRA * 1.5;
    this.zBarra = Z_PINO1 + 0.5;
    this.geos = [];
    const g = (x) => {
      this.geos.push(x);
      return x;
    };
    const corMaquina = "#E4EAF4";
    const corEscura = "#ABB0B7";
    const corDetalhe = "#FFD23F";
    this.mesa = new THREE.Group();
    raiz.add(this.mesa);
    this.mesa.add(new THREE.Mesh(g(comCor(THREE, new THREE.BoxGeometry(1.28, 0.07, 1.32))), mats.toon(corMaquina, { borda: 0.3, especular: 0.6 })));
    const matCopo = mats.toon(corDetalhe, { borda: 0.3 });
    const geoCopo = g(comCor(THREE, new THREE.CylinderGeometry(0.075, 0.06, 0.12, 16)));
    for (let n = 1; n <= 10; n++) {
      const p = posicaoDoPino(n);
      const copo = new THREE.Mesh(geoCopo, matCopo);
      copo.position.set(p[0], -0.095, p[2] - this.zMesa);
      this.mesa.add(copo);
    }
    const matEscura = mats.toon(corEscura, { borda: 0.2 });
    const geoCol = g(comCor(THREE, new THREE.CylinderGeometry(0.03, 0.03, 1.4, 8)));
    for (const s of [-1, 1]) {
      const col = new THREE.Mesh(geoCol, matEscura);
      col.position.set(s * 0.55, 0.7, 0);
      this.mesa.add(col);
    }
    this.barra = new THREE.Group();
    raiz.add(this.barra);
    this.barra.add(new THREE.Mesh(g(comCor(THREE, new THREE.BoxGeometry(MEIA_LARGURA * 2 + 0.3, 0.17, 0.07))), mats.toon(corDetalhe, { borda: 0.3 })));
    const geoHaste = g(comCor(THREE, new THREE.BoxGeometry(0.05, 1.3, 0.05)));
    for (const s of [-1, 1]) {
      const h = new THREE.Mesh(geoHaste, matEscura);
      h.position.set(s * (MEIA_LARGURA + 0.12), 0.65, 0);
      this.barra.add(h);
    }
    // a barra empurra os pinos de verdade (colisão na física)
    this.fisica.barra = { ativa: false, y: Y_BARRA_CIMA, z: this.zBarra };
    this.carregando = [];
    this.centrar = 0;
    this.trabalhando = false;
    this.seq = 0;
    this.instantaneo();
  }

  _sync() {
    const b = this.fisica.barra;
    b.y = this.barra.position.y;
    b.z = this.barra.position.z;
    b.ativa = b.y < 0.6;
  }

  /** Os pinos presos na mesa acompanham a mesa. */
  atualizar() {
    this._sync();
    const mp = this.mesa.position;
    for (const it of this.carregando) {
      const c = it.pino;
      c.p.set(mp.x + mistura(it.de[0], it.para[0], this.centrar), mp.y + mistura(it.de[1], it.para[1], this.centrar) + CM_PINO,
        mp.z + mistura(it.de[2], it.para[2], this.centrar));
      c.q.identity();
    }
  }

  _tw(obj, chave, alvo, dur) {
    return this.relogio.tween(obj, chave, alvo, dur / this.rapidez, FACIL.seno);
  }

  /** Bola que não fechou a rodada: guarda os em pé, varre os caídos e
   *  devolve os em pé no lugar. */
  reposicionar() {
    return this._ciclo(true);
  }

  /** Rodada nova: varre tudo e desce os 10 pinos. */
  rackNovo() {
    return this._ciclo(false);
  }

  async _ciclo(manter) {
    const s = ++this.seq;
    const ok = (r) => r !== false && s === this.seq;
    this.trabalhando = true;
    this.pinos.pararFesta();
    for (const c of this.pinos.corpos) {
      c.dinamico = false;
      c.v.set(0, 0, 0);
      c.w.set(0, 0, 0);
    }
    // 1. a barra desce na frente (proteção)
    if (this.aoSom) this.aoSom("barra");
    if (!ok(await this._tw(this.barra.position, "y", Y_BARRA_BAIXO, 0.55))) return;
    // 2. a mesa desce e levanta os que ficaram em pé
    this.carregando = [];
    this.centrar = 0;
    if (manter) {
      const emPe = this.pinos.emPe();
      if (emPe.length) {
        if (this.aoSom) this.aoSom("mesa");
        if (!ok(await this._tw(this.mesa.position, "y", Y_ENCAIXE + 0.02, 0.7))) return;
        const mp = this.mesa.position;
        for (const n of emPe) {
          const c = this.pinos.pino(n);
          c.preso = true;
          this.carregando.push({ pino: c, de: [c.p.x - mp.x, -mp.y, c.p.z - mp.z], para: [c.lugar[0] - mp.x, -mp.y, c.lugar[2] - mp.z] });
        }
        const sobe = this._tw(this.mesa.position, "y", Y_LEVANTA, 0.45);
        this.relogio.tween(this, "centrar", 1, 0.45 / this.rapidez, FACIL.linear);
        if (!ok(await sobe)) return;
      }
    }
    // 3. varre os caídos para o fosso (a barra empurra de verdade)
    const levados = new Set(this.carregando.map((it) => it.pino));
    for (const c of this.pinos.corpos) if (!levados.has(c) && !c.removido) c.acordar();
    if (this.aoSom) this.aoSom("varrer");
    if (!ok(await this._tw(this.barra.position, "z", Z_FIM_DECK - 0.15, 0.7))) return;
    for (const c of this.pinos.corpos) if (!levados.has(c)) this.pinos.tirar(c);
    if (!ok(await this._tw(this.barra.position, "z", this.zBarra, 0.5))) return;
    // 4. a mesa devolve os em pé (ou traz os 10 novos)
    if (!manter) {
      this.mesa.position.y = Y_REPOUSO;
      this.centrar = 1;
      for (const c of this.pinos.corpos) {
        this.pinos.recolocar(c);
        c.preso = true;
        const off = [c.lugar[0], -Y_ENCAIXE, c.lugar[2] - this.zMesa];
        this.carregando.push({ pino: c, de: off, para: off });
      }
      this.atualizar();
    }
    if (this.carregando.length) {
      if (this.aoSom) this.aoSom("mesa");
      if (!ok(await this._tw(this.mesa.position, "y", Y_ENCAIXE, manter ? 0.75 : 0.85))) return;
      for (const it of this.carregando) this.pinos.recolocar(it.pino);
      this.carregando = [];
      if (this.aoSom) this.aoSom("pousar");
      if (!ok(await this._tw(this.mesa.position, "y", Y_REPOUSO, 0.6))) return;
    }
    // 5. a barra sobe
    if (this.aoSom) this.aoSom("barra");
    if (!ok(await this._tw(this.barra.position, "y", Y_BARRA_CIMA, 0.5))) return;
    this.trabalhando = false;
  }

  /** Sem animação (começo da partida). */
  instantaneo() {
    this.seq++;
    this.carregando = [];
    this.centrar = 0;
    this.mesa.position.set(0, Y_REPOUSO, this.zMesa);
    this.barra.position.set(0, Y_BARRA_CIMA, this.zBarra);
    this.pinos.repor();
    this.trabalhando = false;
    this._sync();
  }

  liberar() {
    for (const g of this.geos) g.dispose();
  }
}

/* ----------------------------------------------------------------------
   CÂMERA DE CINEMA (scripts/camera_cine.gd): planos com transição suave,
   seguir a bola, órbita, trilho (curva monótona), tremida e "soco" de
   zoom. Cada plano diz quanto quer ver na vertical E na horizontal; a
   abertura escolhida garante as duas (a tela aqui é em pé).
   ---------------------------------------------------------------------- */
class CameraCine {
  constructor(THREE) {
    this.T = THREE;
    this.camera = new THREE.PerspectiveCamera(50, LARGURA / ALTURA, 0.05, 160);
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    this.pos = V(0, 2, 6);
    this.alvo = V(0, 0, -8);
    this.posDest = V(0, 2, 6);
    this.alvoDest = V(0, 0, -8);
    this.fovV = 50;
    this.fovH = 40;
    this.fovVDest = 50;
    this.fovHDest = 40;
    this.rapidez = 3;
    this.seguindo = null;
    this.deslPos = V();
    this.deslAlvo = V();
    this.tremor = 0;
    this.tremorDur = 0;
    this.socoGraus = 0;
    this.orbita = null;
    this.trilhoPts = null;
    this._t = V();
    this._p = V();
  }

  _parar() {
    this.seguindo = null;
    this.orbita = null;
    this.trilhoPts = null;
  }

  /** Corte seco para um plano. */
  corte(pos, alvo, fovV = 50, fovH = 34) {
    this._parar();
    this.pos.set(pos[0], pos[1], pos[2]);
    this.alvo.set(alvo[0], alvo[1], alvo[2]);
    this.posDest.copy(this.pos);
    this.alvoDest.copy(this.alvo);
    this.fovV = this.fovVDest = fovV;
    this.fovH = this.fovHDest = fovH;
    this._aplicar(0);
  }

  /** Vai suavemente até o plano (rapidez: maior = chega mais rápido). */
  ir(pos, alvo, fovV = 50, fovH = 34, rapidez = 3) {
    this._parar();
    this.posDest.set(pos[0], pos[1], pos[2]);
    this.alvoDest.set(alvo[0], alvo[1], alvo[2]);
    this.fovVDest = fovV;
    this.fovHDest = fovH;
    this.rapidez = rapidez;
  }

  /** Segue um objeto (função que devolve a posição) mantendo o deslocamento. */
  seguir(fonte, deslPos, deslAlvo, fovV = 50, fovH = 34, rapidez = 5) {
    this.orbita = null;
    this.trilhoPts = null;
    this.seguindo = fonte;
    this.deslPos.set(deslPos[0], deslPos[1], deslPos[2]);
    this.deslAlvo.set(deslAlvo[0], deslAlvo[1], deslAlvo[2]);
    this.fovVDest = fovV;
    this.fovHDest = fovH;
    this.rapidez = rapidez;
  }

  orbitar(centro, raio, altura, vel = 0.15, fovV = 45, fovH = 40) {
    this._parar();
    this.orbita = { centro: centro.slice(), raio, altura, vel, ang: Math.atan2(this.pos.x - centro[0], this.pos.z - centro[2]) };
    this.fovVDest = fovV;
    this.fovHDest = fovH;
    this.rapidez = 1.5;
  }

  /** Trilho: lista de [pos, alvo, segundos]; curva suave que passa pelos
   *  pontos do meio sem frear (Fritsch-Carlson por eixo). */
  trilho(pontos, fovV = 45, fovH = 34) {
    this._parar();
    this.trilhoPts = pontos;
    this.trilhoT = 0;
    this.fovV = this.fovVDest = fovV;
    this.fovH = this.fovHDest = fovH;
    const tempos = [0];
    for (let i = 1; i < pontos.length; i++) tempos.push(tempos[i - 1] + Math.max(pontos[i][2], 0.001));
    this.trilhoTempos = tempos;
    const vel = (k) => {
      const n = pontos.length;
      const v = [];
      for (let i = 0; i < n; i++) v.push([0, 0, 0]);
      for (let i = 1; i < n - 1; i++) {
        const h0 = tempos[i] - tempos[i - 1];
        const h1 = tempos[i + 1] - tempos[i];
        for (let e = 0; e < 3; e++) {
          const d0 = (pontos[i][k][e] - pontos[i - 1][k][e]) / h0;
          const d1 = (pontos[i + 1][k][e] - pontos[i][k][e]) / h1;
          if (d0 * d1 > 0) {
            const w1 = 2 * h1 + h0;
            const w2 = h1 + 2 * h0;
            v[i][e] = (w1 + w2) / (w1 / d0 + w2 / d1);
          }
        }
      }
      return v;
    };
    this.trilhoVp = vel(0);
    this.trilhoVa = vel(1);
  }

  _noTrilho(t) {
    const P = this.trilhoPts;
    const tempos = this.trilhoTempos;
    const n = P.length;
    if (n === 1 || t >= tempos[n - 1]) {
      this.pos.set(...P[n - 1][0]);
      this.alvo.set(...P[n - 1][1]);
      return;
    }
    let i = 0;
    while (i < n - 2 && t > tempos[i + 1]) i++;
    const h = tempos[i + 1] - tempos[i];
    const u = lim((t - tempos[i]) / h, 0, 1);
    const u2 = u * u;
    const u3 = u2 * u;
    const a = 2 * u3 - 3 * u2 + 1;
    const b = (u3 - 2 * u2 + u) * h;
    const c = -2 * u3 + 3 * u2;
    const d = (u3 - u2) * h;
    for (let e = 0; e < 3; e++) {
      const vp = P[i][0][e] * a + this.trilhoVp[i][e] * b + P[i + 1][0][e] * c + this.trilhoVp[i + 1][e] * d;
      const va = P[i][1][e] * a + this.trilhoVa[i][e] * b + P[i + 1][1][e] * c + this.trilhoVa[i + 1][e] * d;
      this.pos.setComponent(e, vp);
      this.alvo.setComponent(e, va);
    }
  }

  tremer(forca, dur = 0.35) {
    // menos movimento (pedido da pessoa): a câmera não treme
    if (this.reduzido) return;
    this.tremor = Math.max(this.tremor, forca);
    this.tremorDur = Math.max(this.tremorDur, dur);
  }

  /** "Soco" de zoom: fecha a abertura de repente e volta. */
  soco(graus) {
    this.socoGraus = this.reduzido ? graus * 0.3 : graus;
  }

  atualizar(dt) {
    this._aplicar(dt);
  }

  _aplicar(dt) {
    if (this.trilhoPts) {
      this.trilhoT += dt;
      this._noTrilho(this.trilhoT);
      this.posDest.copy(this.pos);
      this.alvoDest.copy(this.alvo);
    } else if (this.orbita) {
      const o = this.orbita;
      o.ang += o.vel * dt;
      this.posDest.set(o.centro[0] + Math.sin(o.ang) * o.raio, o.centro[1] + o.altura, o.centro[2] + Math.cos(o.ang) * o.raio);
      this.alvoDest.set(o.centro[0], o.centro[1], o.centro[2]);
    } else if (this.seguindo) {
      const g = this.seguindo();
      this.posDest.copy(g).add(this.deslPos);
      this.alvoDest.copy(g).add(this.deslAlvo);
    }
    if (dt > 0 && !this.trilhoPts) {
      const k = 1 - Math.exp(-this.rapidez * dt);
      this.pos.lerp(this.posDest, k);
      this.alvo.lerp(this.alvoDest, k);
    }
    const kf = dt > 0 ? 1 - Math.exp(-3 * dt) : 1;
    this.fovV = mistura(this.fovV, this.fovVDest, kf);
    this.fovH = mistura(this.fovH, this.fovHDest, kf);
    this.socoGraus = Math.max(0, this.socoGraus - dt * 30);
    const tr = this._t.set(0, 0, 0);
    if (this.tremorDur > 0) {
      this.tremorDur -= dt;
      const f = this.tremor * lim(this.tremorDur * 3, 0, 1);
      tr.set(aleat(-1, 1) * f, aleat(-1, 1) * f, aleat(-1, 1) * f);
      if (this.tremorDur <= 0) this.tremor = 0;
    }
    const cam = this.camera;
    cam.position.copy(this.pos).add(tr);
    cam.lookAt(this._p.copy(this.alvo).addScaledVector(tr, 0.5));
    const aspecto = LARGURA / ALTURA;
    const vPelaH = 2 * Math.atan(Math.tan(this.fovH * GRAU * 0.5) / aspecto) / GRAU;
    const fov = lim(Math.max(this.fovV, vPelaH), 10, 110) - this.socoGraus;
    if (Math.abs(cam.fov - fov) > 1e-4) {
      cam.fov = fov;
      cam.updateProjectionMatrix();
    }
  }
}

/* ----------------------------------------------------------------------
   ANIMAÇÕES DOS BICHINHOS (scripts/animacoes.gd): poses-chave em graus, no
   espaço do personagem (ele olha para +Z). braco_*.x negativo levanta o
   braço para a frente; antebraco.x negativo dobra o cotovelo; coxa.x
   negativo leva a perna para a frente; canela.x positivo dobra o joelho;
   corpo.x positivo inclina para a frente; cabeca.x positivo olha para
   baixo. Extras: "altura" (sobe/desce o quadril), "quadril" (desloca o
   quadril), "frente" (anda para a frente — a corrida do arremesso), "giro"
   (gira o corpo inteiro) e "voo" (sobe o personagem todo). Nos clipes:
   "pulos" = arcos de gravidade e "ik" = "trava" (pés presos no chão),
   "chao" (só não afunda: corrida) ou "livre".
   ---------------------------------------------------------------------- */
const JUNTAS = ["corpo", "cabeca", "braco_e", "antebraco_e", "braco_d", "antebraco_d",
  "coxa_e", "canela_e", "pe_e", "coxa_d", "canela_d", "pe_d"];
const CANAIS_V = [...JUNTAS, "quadril"];
const ESCALARES = ["altura", "frente", "giro", "voo"];
const N_CANAIS = CANAIS_V.length * 3 + ESCALARES.length;
const I_ESCALAR = Object.fromEntries(ESCALARES.map((n, i) => [n, CANAIS_V.length * 3 + i]));
const I_CANAL = Object.fromEntries(CANAIS_V.map((n, i) => [n, i * 3]));
const EXPRESSOES = ["feliz", "piscando", "empolgado", "triste", "concentrado", "surpreso", "risada", "piscadinha"];
const PASSO_DUR = 0.22;
const PASSO_ALTURA = 0.045;
const DIST_PASSO = 0.13;
const TROCA_PE = 0.14;

const ANIMACOES = (() => {
  const V = (x, y, z) => [x, y, z];
  const p = (base, mud) => ({ ...base, ...mud });
  const PARADO = { braco_e: V(0, 0, 8), braco_d: V(0, 0, -8), antebraco_e: V(-12, 0, 0), antebraco_d: V(-12, 0, 0) };
  const PRONTO = {
    braco_d: V(-48, 0, -4), antebraco_d: V(-78, 0, 6), braco_e: V(-42, 0, 14), antebraco_e: V(-72, 0, -18),
    corpo: V(6, 0, 0), cabeca: V(4, 0, 0), coxa_e: V(-5, 0, 0), canela_e: V(10, 0, 0),
    coxa_d: V(-5, 0, 0), canela_d: V(10, 0, 0), altura: -0.012,
  };
  const A = {};
  A.parado = {
    dur: 4.0, loop: true,
    chaves: [
      [0.0, p(PARADO, { quadril: V(0.012, 0, 0), corpo: V(1, 0, -2), cabeca: V(0, 0, 3), altura: -0.006 })],
      [2.0, p(PARADO, { quadril: V(-0.012, 0, 0), corpo: V(2, 0, 2), cabeca: V(3, 0, -3), braco_e: V(4, 0, 11), braco_d: V(4, 0, -11), altura: -0.012 })],
      [4.0, p(PARADO, { quadril: V(0.012, 0, 0), corpo: V(1, 0, -2), cabeca: V(0, 0, 3), altura: -0.006 })],
    ],
  };
  A.pronto = { dur: 3.2, loop: true, chaves: [[0.0, PRONTO], [1.6, p(PRONTO, { altura: -0.008, corpo: V(7, 0, 0) })], [3.2, PRONTO]] };
  // o ARREMESSO: passada de 3 passos, empurra a bola, desce, vai lá atrás, desliza e solta
  const p1 = {
    braco_d: V(-40, 0, -6), antebraco_d: V(-25, 0, 0), braco_e: V(-30, 0, 20), antebraco_e: V(-30, 0, 0),
    coxa_d: V(-28, 0, 0), canela_d: V(10, 0, 0), coxa_e: V(14, 0, 0), canela_e: V(28, 0, 0), corpo: V(8, 0, 0), altura: -0.02, frente: 0.45,
  };
  const p2 = {
    braco_d: V(12, 0, -4), antebraco_d: V(-5, 0, 0), braco_e: V(-15, 0, 40), antebraco_e: V(-20, 0, 0),
    coxa_e: V(-30, 0, 0), canela_e: V(12, 0, 0), coxa_d: V(16, 0, 0), canela_d: V(32, 0, 0), corpo: V(12, 0, 0), altura: -0.03, frente: 1.05,
  };
  const p3 = {
    braco_d: V(78, 0, -4), antebraco_d: V(0, 0, 0), braco_e: V(-25, 0, 60), antebraco_e: V(-15, 0, 0),
    coxa_d: V(-32, 0, 0), canela_d: V(18, 0, 0), coxa_e: V(22, 0, 0), canela_e: V(40, 0, 0),
    corpo: V(24, 0, -4), cabeca: V(-16, 0, 0), altura: -0.06, frente: 1.7,
  };
  const p4 = {
    braco_d: V(-18, 0, -4), antebraco_d: V(-8, 0, 0), braco_e: V(-10, 0, 80), antebraco_e: V(-10, 0, 0),
    coxa_e: V(-58, 0, 0), canela_e: V(72, 0, 0), coxa_d: V(42, 0, 0), canela_d: V(12, 0, 0),
    corpo: V(32, 0, -6), cabeca: V(-30, 0, 0), altura: -0.19, frente: 2.35,
  };
  const p5 = p(p4, { braco_d: V(-128, 0, -8), antebraco_d: V(-25, 0, 0), braco_e: V(-5, 0, 82), corpo: V(26, 0, -4), cabeca: V(-24, 0, 0), altura: -0.17, frente: 2.5 });
  const p6 = p(p5, { braco_d: V(-112, 0, -10), antebraco_d: V(-35, 0, 0), frente: 2.55, cabeca: V(-20, 0, 0) });
  A.arremesso = {
    dur: 2.0, loop: false, ik: "chao",
    chaves: [[0.0, PRONTO], [0.28, p1], [0.55, p2], [0.8, p3], [1.02, p4], [1.3, p5], [2.0, p6]],
    eventos: [[0.28, "som", "passo"], [0.55, "som", "passo"], [0.8, "som", "passo"], [1.0, "soltar", null],
      [0.0, "expressao", "concentrado"], [1.0, "expressao", "surpreso"]],
  };
  A.assistindo = {
    dur: 1.6, loop: true, ik: "chao",
    chaves: [[0.0, p(p6, { frente: 0 })], [0.8, p(p6, { frente: 0, altura: -0.15, braco_d: V(-100, 0, -12) })], [1.6, p(p6, { frente: 0 })]],
  };
  // STRIKE: pulão com pirueta e festa!
  const agacha = p(PARADO, {
    altura: -0.1, corpo: V(16, 0, 0), cabeca: V(-6, 0, 0),
    braco_e: V(28, 0, 22), braco_d: V(28, 0, -22), antebraco_e: V(-20, 0, 0), antebraco_d: V(-20, 0, 0),
  });
  const voando = {
    braco_e: V(-162, 0, 26), braco_d: V(-162, 0, -26), antebraco_e: V(-10, 0, 0), antebraco_d: V(-10, 0, 0),
    coxa_e: V(-34, 0, 4), canela_e: V(70, 0, 0), coxa_d: V(-24, 0, -4), canela_d: V(78, 0, 0),
    pe_e: V(20, 0, 0), pe_d: V(24, 0, 0), corpo: V(-8, 0, 0), cabeca: V(-14, 0, 0),
  };
  const esticado = p(voando, {
    coxa_e: V(-6, 0, 0), canela_e: V(8, 0, 0), coxa_d: V(-6, 0, 0), canela_d: V(8, 0, 0),
    pe_e: V(30, 0, 0), pe_d: V(30, 0, 0), corpo: V(-4, 0, 0),
  });
  const aterrissa = p(agacha, { altura: -0.085, braco_e: V(-120, 0, 52), braco_d: V(-120, 0, -52) });
  const vibra1 = p(PARADO, {
    braco_d: V(-125, 0, -35), antebraco_d: V(-15, 0, 0), braco_e: V(-20, 0, 30),
    corpo: V(-4, 0, -6), altura: -0.03, quadril: V(0.015, 0, 0),
  });
  const vibra2 = p(vibra1, { braco_d: V(-155, 0, -35), antebraco_d: V(-5, 0, 0), altura: -0.005, quadril: V(-0.01, 0, 0) });
  const impulso = p(agacha, {
    altura: -0.05, corpo: V(8, 0, 0), braco_e: V(-70, 0, 20), braco_d: V(-70, 0, -20),
    antebraco_e: V(-25, 0, 0), antebraco_d: V(-25, 0, 0),
  });
  A.comemora_strike = {
    dur: 3.1, loop: false,
    pulos: [[0.3, 0.98, 0.52], [2.42, 2.74, 0.12]],
    chaves: [
      [0.0, PARADO], [0.2, agacha], [0.3, impulso],
      [0.42, p(esticado, { giro: 25 })], [0.56, p(voando, { giro: 125 })], [0.72, p(voando, { giro: 245 })],
      [0.92, p(esticado, { giro: 360 })], [1.06, p(aterrissa, { giro: 360 })],
      [1.3, p(vibra1, { giro: 360 })], [1.5, p(vibra2, { giro: 360 })], [1.7, p(vibra1, { giro: 360 })],
      [1.9, p(vibra2, { giro: 360 })], [2.1, p(vibra1, { giro: 360 })],
      [2.36, p(agacha, { giro: 360, altura: -0.06, braco_e: V(-110, 0, 30), braco_d: V(-110, 0, -30), antebraco_e: V(-20, 0, 0), antebraco_d: V(-20, 0, 0) })],
      [2.5, p(esticado, { giro: 360 })], [2.78, p(aterrissa, { giro: 360, altura: -0.05 })], [3.1, p(PARADO, { giro: 360 })],
    ],
    eventos: [[0.0, "expressao", "empolgado"], [0.3, "jatos", true], [0.3, "som", "jato"], [2.7, "jatos", false],
      [1.1, "expressao", "risada"], [1.0, "som", "passo"], [2.74, "som", "passo"]],
  };
  // feliz (spare, boa jogada): pulinho + palmas
  const palmaJunta = p(PARADO, {
    braco_e: V(-72, 0, -12), antebraco_e: V(-48, -20, -25), braco_d: V(-72, 0, 12), antebraco_d: V(-48, 20, 25), corpo: V(4, 0, 0),
  });
  const palmaAbre = p(palmaJunta, { braco_e: V(-70, 0, 14), braco_d: V(-70, 0, -14) });
  A.feliz = {
    depois: "parado", dur: 1.9, loop: false, pulos: [[0.22, 0.56, 0.2]],
    chaves: [
      [0.0, PARADO], [0.18, p(agacha, { altura: -0.07 })],
      [0.39, p(PARADO, { braco_e: V(-130, 0, 45), braco_d: V(-130, 0, -45), coxa_e: V(-20, 0, 0), canela_e: V(45, 0, 0), coxa_d: V(-20, 0, 0), canela_d: V(45, 0, 0) })],
      [0.62, p(PARADO, { altura: -0.05 })],
      [0.75, palmaJunta], [0.9, palmaAbre], [1.05, palmaJunta], [1.2, palmaAbre], [1.35, palmaJunta], [1.9, PARADO],
    ],
    eventos: [[0.0, "expressao", "feliz"], [0.75, "som", "palma"], [1.05, "som", "palma"], [1.35, "som", "palma"]],
  };
  // triste (errou): cabeça baixa, balança
  const baixa = p(PARADO, { cabeca: V(26, 0, 0), corpo: V(10, 0, 0), braco_e: V(6, 0, 3), braco_d: V(6, 0, -3), altura: -0.03 });
  A.triste = {
    depois: "parado", dur: 2.0, loop: false,
    chaves: [[0.0, PARADO], [0.3, baixa], [0.6, p(baixa, { cabeca: V(24, -22, 0) })], [0.9, p(baixa, { cabeca: V(24, 22, 0) })],
      [1.2, p(baixa, { cabeca: V(20, 0, 0) })], [1.5, baixa],
      [2.0, p(PARADO, { braco_e: V(-20, 0, 40), braco_d: V(-20, 0, -40), antebraco_e: V(-80, 0, 0), antebraco_d: V(-80, 0, 0) })]],
    eventos: [[0.0, "expressao", "triste"], [1.6, "expressao", "concentrado"]],
  };
  // torcida (o outro jogando)
  const t1 = p(PARADO, { braco_e: V(-155, 0, 28), antebraco_e: V(-30, 0, 0), braco_d: V(-110, 0, -40), antebraco_d: V(-70, 0, 0) });
  const t2 = p(PARADO, { braco_d: V(-155, 0, -28), antebraco_d: V(-30, 0, 0), braco_e: V(-110, 0, 40), antebraco_e: V(-70, 0, 0) });
  A.torcida = {
    dur: 2.4, loop: true,
    chaves: [[0.0, p(t1, { quadril: V(0.01, 0, 0) })], [0.6, p(t1, { quadril: V(0.012, 0, 0), altura: -0.006 })],
      [1.2, p(t2, { quadril: V(-0.01, 0, 0) })], [1.8, p(t2, { quadril: V(-0.012, 0, 0), altura: -0.006 })],
      [2.4, p(t1, { quadril: V(0.01, 0, 0) })]],
  };
  // festa (fim de jogo): braços para cima balançando
  const f1 = p(PARADO, {
    braco_e: V(-150, 0, 38), antebraco_e: V(-15, 0, 0), braco_d: V(-150, 0, -38), antebraco_d: V(-15, 0, 0),
    corpo: V(-3, 0, -5), cabeca: V(-6, 0, 6), quadril: V(0.015, 0, 0),
  });
  const f2 = p(f1, { corpo: V(-3, 0, 5), cabeca: V(-6, 0, -6), quadril: V(-0.015, 0, 0) });
  A.festa = { dur: 2.0, loop: true, chaves: [[0.0, f1], [1.0, f2], [2.0, f1]] };
  // dança: o quadril vai de um lado para o outro, joelhos no tempo forte
  const d1 = p(PARADO, {
    braco_e: V(-110, 0, 30), antebraco_e: V(-35, 0, 0), braco_d: V(-8, 0, -30), antebraco_d: V(-90, 0, 0),
    corpo: V(2, 10, 7), cabeca: V(0, -10, -8), quadril: V(0.035, 0, 0),
  });
  const d2 = p(PARADO, {
    braco_d: V(-110, 0, -30), antebraco_d: V(-35, 0, 0), braco_e: V(-8, 0, 30), antebraco_e: V(-90, 0, 0),
    corpo: V(2, -10, -7), cabeca: V(0, 10, 8), quadril: V(-0.035, 0, 0),
  });
  A.danca = {
    dur: 2.8, loop: true,
    chaves: [[0.0, d1], [0.4, p(d1, { altura: -0.018, quadril: V(0.025, 0, 0) })], [0.7, d1],
      [0.95, p(d1, { coxa_d: V(-22, 0, 0), canela_d: V(40, 0, 0), pe_d: V(12, 0, 0) })], [1.2, d1],
      [1.4, d2], [1.8, p(d2, { altura: -0.018, quadril: V(-0.025, 0, 0) })], [2.1, d2],
      [2.35, p(d2, { coxa_e: V(-22, 0, 0), canela_e: V(40, 0, 0), pe_e: V(12, 0, 0) })], [2.6, d2], [2.8, d1]],
  };
  const dc = A.danca.chaves.slice();
  for (const c of A.danca.chaves.slice(1)) dc.push([c[0] + 2.8, c[1]]);
  A.danca_curta = { dur: 5.6, loop: false, depois: "parado", chaves: dc };
  // acenar (oi!): o braço sobe pelo LADO da cabeça e a mão balança
  const a1 = p(PARADO, { braco_d: V(-150, 0, -38), antebraco_d: V(-10, 0, -30), cabeca: V(0, 0, 6), quadril: V(0.015, 0, 0), corpo: V(0, 0, -3) });
  const a2 = p(a1, { antebraco_d: V(-10, 0, 28), cabeca: V(0, 0, -4), quadril: V(0.008, 0, 0) });
  A.acenar = { dur: 1.2, loop: true, chaves: [[0.0, a1], [0.3, a2], [0.6, a1], [0.9, a2], [1.2, a1]] };
  A.acenar_uma = {
    dur: 2.6, loop: false, depois: "parado",
    chaves: [[0.0, PARADO], [0.35, a1], [0.65, a2], [0.95, a1], [1.25, a2], [1.55, a1], [1.85, a2], [2.6, PARADO]],
    eventos: [[0.0, "expressao", "feliz"]],
  };
  A.olhar_volta = {
    dur: 3.2, loop: false, depois: "parado",
    chaves: [[0.0, PARADO], [0.6, p(PARADO, { cabeca: V(4, 35, 4), corpo: V(0, 8, 0) })],
      [1.5, p(PARADO, { cabeca: V(4, 35, 4), corpo: V(0, 8, 0) })],
      [2.1, p(PARADO, { cabeca: V(2, -30, -4), corpo: V(0, -6, 0) })],
      [2.7, p(PARADO, { cabeca: V(2, -30, -4), corpo: V(0, -6, 0) })], [3.2, PARADO]],
  };
  // vitória: pulinhos de alegria, braços para cima
  const vBaixo = p(agacha, { altura: -0.08, braco_e: V(-150, 0, 40), braco_d: V(-150, 0, -40) });
  A.vitoria = {
    dur: 1.4, loop: false, depois: "festa", pulos: [[0.12, 0.58, 0.3], [0.82, 1.24, 0.24]],
    chaves: [[0.0, vBaixo], [0.12, esticado], [0.35, voando], [0.58, esticado], [0.7, vBaixo],
      [0.82, p(esticado, { corpo: V(-6, 0, 8) })], [1.03, p(voando, { corpo: V(-6, 0, 10) })], [1.24, esticado], [1.4, vBaixo]],
  };
  // escolhido (seleção do amigo)
  A.escolhido = {
    dur: 1.4, loop: false, pulos: [[0.2, 0.62, 0.26]],
    chaves: [[0.0, PARADO], [0.17, p(agacha, { altura: -0.07 })],
      [0.41, p(PARADO, { braco_d: V(-165, 0, -25), antebraco_d: V(-10, 0, 0), braco_e: V(10, 0, 30), coxa_e: V(-30, 0, 0), canela_e: V(55, 0, 0), coxa_d: V(-10, 0, 0), canela_d: V(25, 0, 0) })],
      [0.75, p(PARADO, { altura: -0.03, braco_d: V(-160, 0, -28) })],
      [1.4, p(PARADO, { braco_d: V(-150, 0, -30), antebraco_d: V(-40, 0, 0) })]],
    eventos: [[0.0, "expressao", "empolgado"], [1.2, "expressao", "piscadinha"]],
  };
  // quase (ficou 1 pino): mãos nas bochechas
  A.quase = {
    depois: "parado", dur: 1.7, loop: false,
    chaves: [[0.0, PARADO],
      [0.3, p(PARADO, { braco_e: V(-110, 0, 20), antebraco_e: V(-30, 0, 0), braco_d: V(-110, 0, -20), antebraco_d: V(-30, 0, 0), corpo: V(-6, 0, 0), cabeca: V(-10, 0, 0) })],
      [1.2, p(PARADO, { braco_e: V(-115, 0, 18), antebraco_e: V(-35, 0, 0), braco_d: V(-115, 0, -18), antebraco_d: V(-35, 0, 0), corpo: V(-4, 0, 0), cabeca: V(-6, 0, 4) })],
      [1.7, PARADO]],
    eventos: [[0.0, "expressao", "surpreso"]],
  };
  return A;
})();

/** Tangente monotônica (Fritsch-Carlson): zero nos picos e vales. */
function pchip(a, b, c, h0, h1) {
  h0 = Math.max(h0, 0.0001);
  h1 = Math.max(h1, 0.0001);
  const d0 = (b - a) / h0;
  const d1 = (c - b) / h1;
  if (d0 * d1 <= 0) return 0;
  const w1 = 2 * h1 + h0;
  const w2 = h1 + 2 * h0;
  return (w1 + w2) / (w1 / d0 + w2 / d1);
}

/** Prepara o clipe uma vez: tempos, valores de cada canal e tangentes PCHIP. */
function prepararClipe(clip) {
  if (clip._tempos) return clip;
  const n = clip.chaves.length;
  const tempos = new Float32Array(n);
  const valores = [];
  for (let i = 0; i < n; i++) {
    const [t, pose] = clip.chaves[i];
    tempos[i] = t;
    const v = new Float32Array(N_CANAIS);
    for (const [k, val] of Object.entries(pose)) {
      if (k in I_ESCALAR) v[I_ESCALAR[k]] = val;
      else if (k in I_CANAL) v.set(val, I_CANAL[k]);
    }
    valores.push(v);
  }
  const loop = !!clip.loop;
  const dur = clip.dur;
  const tang = [];
  for (let i = 0; i < n; i++) {
    const m = new Float32Array(N_CANAIS);
    let ant = -1;
    let prox = -1;
    let h0 = 0;
    let h1 = 0;
    if (i > 0) {
      ant = i - 1;
      h0 = tempos[i] - tempos[i - 1];
    } else if (loop && n > 2) {
      ant = n - 2;
      h0 = tempos[i] - (tempos[n - 2] - dur);
    }
    if (i < n - 1) {
      prox = i + 1;
      h1 = tempos[i + 1] - tempos[i];
    } else if (loop && n > 2) {
      prox = 1;
      h1 = tempos[1] + dur - tempos[i];
    }
    if (ant >= 0 && prox >= 0) {
      for (let k = 0; k < N_CANAIS; k++) m[k] = pchip(valores[ant][k], valores[i][k], valores[prox][k], h0, h1);
    }
    tang.push(m);
  }
  clip._tempos = tempos;
  clip._valores = valores;
  clip._tangentes = tang;
  return clip;
}

/** Altura extra dos pulos do clipe: arco de gravidade h = 4H·u·(1-u). */
function alturaPulo(clip, t) {
  let h = 0;
  for (const p of clip.pulos || []) {
    if (t > p[0] && t < p[1]) {
      const u = (t - p[0]) / (p[1] - p[0]);
      h += 4 * p[2] * u * (1 - u);
    }
  }
  return h;
}

/** A pose do clipe no instante t (Hermite cúbica com as tangentes PCHIP). */
function amostrarClipe(clip, t, saida) {
  const tempos = clip._tempos;
  const v = clip._valores;
  const m = clip._tangentes;
  const n = tempos.length;
  if (n === 1) {
    saida.set(v[0]);
  } else {
    let i = 0;
    while (i < n - 2 && t >= tempos[i + 1]) i++;
    const h = Math.max(tempos[i + 1] - tempos[i], 0.0001);
    const u = lim((t - tempos[i]) / h, 0, 1);
    const u2 = u * u;
    const u3 = u2 * u;
    const h00 = 2 * u3 - 3 * u2 + 1;
    const h10 = (u3 - 2 * u2 + u) * h;
    const h01 = -2 * u3 + 3 * u2;
    const h11 = (u3 - u2) * h;
    const a = v[i];
    const b = v[i + 1];
    const ma = m[i];
    const mb = m[i + 1];
    for (let k = 0; k < N_CANAIS; k++) saida[k] = a[k] * h00 + ma[k] * h10 + b[k] * h01 + mb[k] * h11;
  }
  const pulo = alturaPulo(clip, t);
  if (pulo > 0) saida[I_ESCALAR.voo] += pulo;
  return saida;
}

/** Transição por inércia de solavanco mínimo (polinômio de 5º grau):
 *  devolve [A, B, C, v0, x0, t1, sinal] ou null. */
function inerciaCoef(x0, v0, t1, vmax, limite, saida, o) {
  if (Math.abs(x0) < 0.00001 && Math.abs(v0) < 0.0001) {
    saida[o + 5] = -1;
    return;
  }
  const s = x0 >= 0 ? 1 : -1;
  const x = x0 * s;
  let v = v0 * s;
  let t = lim(Math.max(t1, 1.875 * x / vmax), t1, 0.7);
  if (v < 0 && -v * t > 2.5 * x) {
    t = Math.max(2.5 * x / -v, Math.min(t1, 0.12));
    v = Math.max(v, -2.5 * x / t);
  } else if (v > 0) {
    v = Math.min(v, Math.max(2 * x, limite / 0.185) / t);
  }
  saida[o] = -(3 * v * t + 6 * x) / Math.pow(t, 5);
  saida[o + 1] = (8 * v * t + 15 * x) / Math.pow(t, 4);
  saida[o + 2] = -(6 * v * t + 10 * x) / Math.pow(t, 3);
  saida[o + 3] = v;
  saida[o + 4] = x;
  saida[o + 5] = t;
  saida[o + 6] = s;
}

function inerciaValor(c, o, t) {
  if (c[o + 5] < 0 || t >= c[o + 5]) return 0;
  return c[o + 6] * ((((c[o] * t + c[o + 1]) * t + c[o + 2]) * t * t * t) + c[o + 3] * t + c[o + 4]);
}

/* ----------------------------------------------------------------------
   UM PERSONAGEM (scripts/personagem.gd): Bob, o cachorrinho, ou Mia, a
   gatinha. Modelo articulado (as juntas do modelador) + poses + rosto com
   expressões + piscar + olhar para a bola + rabinho que abana + bola na
   mão + sombrinhas de contato + IK das pernas (pé travado no chão).
   ---------------------------------------------------------------------- */
class Personagem {
  constructor(THREE, mats, tex, nome, pacote, particulas, raizMundo) {
    this.T = THREE;
    this.mats = mats;
    this.nome = nome;
    this.particulas = particulas;
    this.raiz = new THREE.Group();
    this.raiz.rotation.order = "YXZ";
    this.juntas = {};
    this.repouso = {};
    this.malhas = {};
    this.mats_ = [];
    this.roupa = "";
    this.aoSoltar = null;
    this.aoSom = null;
    const meta = pacote.info[nome].meta;
    const juntas = pacote.info[nome].juntas;
    this.meta = meta;
    const rosto = tex["rosto_" + nome];
    this.contorno = mats.contorno(0.0032);
    for (const j of juntas) {
      const no = new THREE.Group();
      no.name = j.nome;
      no.position.set(j.pivo[0], j.pivo[1], j.pivo[2]);
      no.rotation.order = "YXZ";
      (j.pai ? this.juntas[j.pai] : this.raiz).add(no);
      this.juntas[j.nome] = no;
      this.repouso[j.nome] = no.position.clone();
      const p = { borda: 0.22, cor_borda: [1.0, 0.92, 1.0], brilho_luz: 1.4, faixa: 0.15, luz_minima: 0.32 };
      if (j.nome === "cabeca") {
        p.rosto = rosto;
        p.rosto_centro = meta.rosto.centro;
        p.rosto_tamanho = meta.rosto.tamanho;
      }
      const m = mats.personagem(p);
      if (j.nome === "cabeca") this.matCabeca = m;
      if (j.nome === "corpo") this.matCorpo = m;
      this.mats_.push(m);
      const geo = pacote.malhas[nome + "/" + j.nome];
      const malha = new THREE.Mesh(geo, m);
      const casca = new THREE.Mesh(geo, this.contorno);
      no.add(malha);
      no.add(casca);
      this.malhas[j.nome] = [malha, casca];
    }
    this.estampaPadrao = meta.estampa;
    this._estampa(meta.estampa);
    this.rabo = this.juntas.rabo;
    // a bola na mão direita
    this.bolaMao = new THREE.Group();
    const geoBola = new THREE.SphereGeometry(RAIO_BOLA, 32, 16);
    this.geoBola = geoBola;
    this.matBolaMao = criarMatBola(mats, tex, nome);
    this.bolaMao.add(new THREE.Mesh(geoBola, this.matBolaMao));
    this.bolaMao.add(new THREE.Mesh(geoBola, mats.contorno(0.0025, { usa_cor_vertice: 0 })));
    comCor(THREE, geoBola);
    const mao = meta.mao_d || [-0.034, -0.15, 0.025];
    this.bolaMao.position.set(mao[0], mao[1] - 0.118, mao[2] + 0.028);
    this.bolaMao.visible = false;
    this.juntas.antebraco_d.add(this.bolaMao);
    // pernas: comprimentos e altura do tornozelo
    this.tornY = meta.tornozelo_y ?? 0.078;
    this.l1 = {};
    this.l2 = {};
    this.pes = {};
    for (const lado of ["e", "d"]) {
      this.l1[lado] = this.repouso["canela_" + lado].length();
      this.l2[lado] = this.repouso["pe_" + lado].length();
      this.pes[lado] = { preso: false, pos: new THREE.Vector3(), passo: -1, de: new THREE.Vector3(), ancora: null, pesoLin: 0 };
    }
    // sombras: a redonda do corpo e a de contato de cada pé
    const geoSombra = comCor(THREE, new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2));
    this.geoSombra = geoSombra;
    this.sombra = new THREE.Mesh(geoSombra, mats.sombra(0.38));
    this.sombra.renderOrder = 1;
    raizMundo.add(this.sombra);
    this.sombrasPe = {};
    const matPe = mats.sombra(0.62);
    for (const lado of ["e", "d"]) {
      const s = new THREE.Mesh(geoSombra, matPe);
      s.renderOrder = 1;
      raizMundo.add(s);
      this.sombrasPe[lado] = s;
    }
    raizMundo.add(this.raiz);
    // estado da animação
    this.pose = new Float32Array(N_CANAIS);
    this.poseAnt = new Float32Array(N_CANAIS);
    this.poseTem = false;
    this.dtAnt = 1 / 60;
    this.inercia = new Float32Array(N_CANAIS * 7);
    this.inerciaT = 0;
    this.inerciaDur = 0;
    this.temInercia = false;
    this._novo0 = new Float32Array(N_CANAIS);
    this._novo1 = new Float32Array(N_CANAIS);
    this._antes = new Float32Array(N_CANAIS);
    this._vel = new Float32Array(N_CANAIS);
    this.baseYaw = 0;
    this.base = new THREE.Vector3();
    this.chao = 0;
    this.descer = 0;
    this.expressaoAtual = "feliz";
    this.piscarEm = aleat(1, 3);
    this.piscando = 0;
    this.olharAlvo = null;
    this.olhar = [0, 0];
    this.olharV = [0, 0];
    this.faseResp = 0;
    this.faseRabo = 0;
    this.alegria = 0.5;
    this.alegriaSuave = 0.5;
    this.jatosLigados = false;
    this.ociosoLigado = false;
    this.ociosoT = 0;
    this.flash = 0;
    // vetores e quatérnios reaproveitados (nada novo a cada quadro)
    const V = () => new THREE.Vector3();
    this._v = [V(), V(), V(), V(), V(), V(), V(), V(), V(), V()];
    this._q = [new THREE.Quaternion(), new THREE.Quaternion(), new THREE.Quaternion(), new THREE.Quaternion()];
    this._e = new THREE.Euler(0, 0, 0, "YXZ");
    this._alvos = { e: V(), d: V() };
    this.tocar("parado");
    this.expressao("feliz");
  }

  _estampa(e) {
    const u = this.matCorpo.uniforms;
    // roupa inteira (astronauta, dino) vem com a estampa vazia: corpo liso
    if (!e || !e.tipo) {
      u.estampa.value = 0;
      return;
    }
    u.estampa_base.value.set(...hex(e.base));
    u.estampa_cor.value.set(...hex(e.cor));
    u.estampa_raio.value = e.raio;
    if (e.tipo === "estrela") {
      u.estampa.value = 1;
      u.estampa_centro.value.set(e.centro[0], e.centro[1]);
      u.estampa_dentro.value = e.dentro;
    } else if (e.tipo === "listras") {
      u.estampa.value = 3;
      u.bolinhas_y0.value = e.y0;
      u.bolinhas_dy.value = e.periodo;
      u.bolinhas_y_max.value = e.y_max;
    } else {
      u.estampa.value = 2;
      u.bolinhas_y0.value = e.y0;
      u.bolinhas_dy.value = e.dy;
      u.bolinhas_fileiras.value = e.fileiras;
      u.bolinhas_n0.value = e.n0;
      u.bolinhas_y_max.value = e.y_max;
    }
  }

  /** Veste a roupinha da fase (pacote roupa_<fase>) ou a de sempre (null). */
  vestir(pacoteRoupa, nomeRoupa) {
    const T = this.T;
    if ((nomeRoupa || "") === this.roupa) return;
    const info = pacoteRoupa ? pacoteRoupa.info[this.nome] : null;
    const malhas = pacoteRoupa ? pacoteRoupa.malhas : this.pacoteBase.malhas;
    const prefixo = this.nome + "/";
    for (const j of Object.keys(this.malhas)) {
      const geo = malhas[prefixo + j] || this.pacoteBase.malhas[prefixo + j];
      this.malhas[j][0].geometry = geo;
      this.malhas[j][1].geometry = geo;
    }
    this._estampa(info ? info.meta.estampa : this.estampaPadrao);
    const geoHelice = pacoteRoupa ? malhas[prefixo + "helice"] : null;
    if (geoHelice) {
      if (!this.helice) {
        this.helice = new T.Group();
        const m = this.mats.personagem({ borda: 0.22, faixa: 0.15, luz_minima: 0.32 });
        this.mats_.push(m);
        this.helice.add(new T.Mesh(geoHelice, m));
        this.helice.add(new T.Mesh(geoHelice, this.contorno));
        this.juntas.cabeca.add(this.helice);
      }
      const jh = info.juntas.find((j) => j.nome === "helice");
      this.helice.children[0].geometry = geoHelice;
      this.helice.children[1].geometry = geoHelice;
      this.helice.position.set(jh.pivo[0], jh.pivo[1], jh.pivo[2]);
      this.helice.visible = true;
    } else if (this.helice) {
      this.helice.visible = false;
    }
    this.roupa = nomeRoupa || "";
  }

  // ---------------------------------------------------------------- animação
  /** Troca a animação (mistura: segundos de transição por inércia). */
  tocar(nome, mistura = 0.22, reiniciar = false) {
    if (nome === this.nomeClipe && !reiniciar) return;
    const antes = this._antes;
    const vel = this._vel;
    antes.set(this.pose);
    for (let k = 0; k < N_CANAIS; k++) vel[k] = this.poseTem ? (this.pose[k] - this.poseAnt[k]) / Math.max(this.dtAnt, 0.001) : 0;
    this.clipe = prepararClipe(ANIMACOES[nome] || ANIMACOES.parado);
    this.nomeClipe = nome;
    this.modoIk = this.clipe.ik || "trava";
    this.t = 0;
    this.eventosFeitos = new Set();
    // o quanto ele andou/girou vira o novo ponto de partida
    this.base.set(this.raiz.position.x, this.base.y, this.raiz.position.z);
    this.baseYaw = this.raiz.rotation.y;
    antes[I_ESCALAR.frente] = 0;
    antes[I_ESCALAR.giro] = 0;
    this.inerciaT = 0;
    this.inerciaDur = Math.max(mistura, 0.001);
    this.temInercia = false;
    if (!this.poseTem) return;
    amostrarClipe(this.clipe, 0, this._novo0);
    amostrarClipe(this.clipe, 1 / 60, this._novo1);
    for (let k = 0; k < N_CANAIS; k++) {
      const x0 = antes[k] - this._novo0[k];
      const v0 = vel[k] - (this._novo1[k] - this._novo0[k]) * 60;
      let vmax = 420;
      let limite = 12;
      if (k === I_ESCALAR.giro) {
        limite = 10;
      } else if (k >= CANAIS_V.length * 3 || (k >= I_CANAL.quadril && k < I_CANAL.quadril + 3)) {
        vmax = 0.8;
        limite = 0.015;
      }
      inerciaCoef(x0, v0, this.inerciaDur, vmax, limite, this.inercia, k * 7);
      if (this.inercia[k * 7 + 5] >= 0) {
        this.temInercia = true;
        this.inerciaDur = Math.max(this.inerciaDur, this.inercia[k * 7 + 5]);
      }
    }
  }

  /** "À vontade" (atração, escolha, fim): parado respirando e, de vez em
   *  quando, acena, olha em volta ou dança um pouquinho. */
  ocioso(ligar) {
    this.ociosoLigado = ligar;
    this.ociosoT = aleat(1.5, 4.0);
    if (ligar) this.tocar("parado", 0.3);
  }

  atualizar(dt) {
    const clip = this.clipe;
    const dur = clip.dur;
    const tAntes = this.t;
    this.t += dt;
    const loop = !!clip.loop;
    let deuVolta = false;
    if (loop) {
      if (this.t >= dur) {
        this.t %= dur;
        deuVolta = true;
      }
    } else if (this.t >= dur) {
      this.t = dur;
      if (tAntes < dur && clip.depois) this._depois = clip.depois;
    }
    if (this.ociosoLigado && this.nomeClipe === "parado") {
      this.ociosoT -= dt;
      if (this.ociosoT <= 0) {
        this.ociosoT = aleat(4.0, 8.5);
        this.tocar(sortear(["acenar_uma", "olhar_volta", "danca_curta", "acenar_uma", "danca_curta"]), 0.35, true);
      }
    }
    this._eventos(tAntes, this.t, deuVolta);
    this.poseAnt.set(this.pose);
    amostrarClipe(this.clipe, this.t, this.pose);
    if (this.temInercia) {
      this.inerciaT += dt;
      if (this.inerciaT >= this.inerciaDur) {
        this.temInercia = false;
      } else {
        for (let k = 0; k < N_CANAIS; k++) this.pose[k] += inerciaValor(this.inercia, k * 7, this.inerciaT);
      }
    }
    if (!this.poseTem) {
      this.poseAnt.set(this.pose);
      this.poseTem = true;
    }
    this.dtAnt = dt;
    this._aplicar(dt);
    this._rosto(dt);
    if (this.helice && this.helice.visible) this.helice.rotation.y += dt * (7 + 9 * this.alegriaSuave);
    if (this.jatosLigados && this.particulas) {
      this._festaAcc = (this._festaAcc || 0) + dt * 40;
      const p = this.raiz.position;
      while (this._festaAcc > 1) {
        this._festaAcc -= 1;
        this.particulas.festa([p.x, this.chao, p.z]);
      }
    }
    if (this._depois) {
      const d = this._depois;
      this._depois = null;
      this.tocar(d, 0.35);
    }
  }

  _eventos(de, ate, deuVolta) {
    const evs = this.clipe.eventos;
    if (!evs) return;
    for (let i = 0; i < evs.length; i++) {
      const ev = evs[i];
      const t = ev[0];
      const passou = (t > de && t <= ate) || (de === 0 && t === 0 && !this.eventosFeitos.has(i)) || (deuVolta && (t > de || t <= ate));
      if (passou && !this.eventosFeitos.has(i)) {
        this.eventosFeitos.add(i);
        if (ev[1] === "soltar") {
          if (this.bolaMao.visible) {
            const p = this.bolaMao.getWorldPosition(this._v[9]);
            this.bolaMao.visible = false;
            if (this.aoSoltar) this.aoSoltar(p.clone());
          }
        } else if (ev[1] === "jatos") {
          this.jatos(!!ev[2]);
        } else if (ev[1] === "expressao") {
          this.expressao(ev[2]);
        } else if (ev[1] === "som" && this.aoSom) {
          this.aoSom(ev[2]);
        }
      }
    }
    if (deuVolta) this.eventosFeitos.clear();
  }

  _aplicar(dt) {
    const pose = this.pose;
    const e = this._e;
    const corpoX = pose[I_CANAL.corpo];
    this.faseResp = (this.faseResp + dt * 2.4) % TAU;
    const altura = pose[I_ESCALAR.altura] + Math.sin(this.faseResp) * 0.004;
    const voo = Math.max(pose[I_ESCALAR.voo], 0);
    const frente = pose[I_ESCALAR.frente];
    const giro = pose[I_ESCALAR.giro];
    for (const j of JUNTAS) {
      const no = this.juntas[j];
      const o = I_CANAL[j];
      let x = pose[o];
      let y = pose[o + 1];
      const z = pose[o + 2];
      if (j.startsWith("coxa")) x -= corpoX;
      if (j === "cabeca") {
        x += this.olhar[1];
        y += this.olhar[0];
      }
      e.set(x * GRAU, y * GRAU, z * GRAU, "YXZ");
      no.quaternion.setFromEuler(e);
    }
    const rc = this.repouso.corpo;
    const oq = I_CANAL.quadril;
    this.juntas.corpo.position.set(rc.x + pose[oq], rc.y + altura, rc.z + pose[oq + 2]);
    const fx = Math.sin(this.baseYaw) * frente;
    const fz = Math.cos(this.baseYaw) * frente;
    this.raiz.position.set(this.base.x + fx, this.base.y + voo, this.base.z + fz);
    this.raiz.rotation.set(0, this.baseYaw + giro * GRAU, 0);
    this.raiz.updateMatrixWorld(true);
    this._ikPernas(dt, voo);
    this._sombras(voo);
    this._olharPasso(dt);
    if (this.rabo) {
      this.alegriaSuave = mistura(this.alegriaSuave, this.alegria, 1 - Math.exp(-dt * 3));
      this.faseRabo = (this.faseRabo + dt * (7 + this.alegriaSuave * 9)) % (TAU * 2);
      this.rabo.rotation.set(Math.sin(this.faseRabo * 0.5) * 0.12, Math.sin(this.faseRabo) * (0.35 + this.alegriaSuave * 0.35), 0);
    }
  }

  /** Olha para a bola com uma mola amortecida (só o que está na frente). */
  _olharPasso(dt) {
    let ay = 0;
    let ap = 0;
    if (this.olharAlvo) {
      const local = this.juntas.corpo.worldToLocal(this._v[0].copy(this.olharAlvo));
      const horiz = Math.hypot(local.x, local.z);
      const frente = lim((local.z - 0.05) / 0.3, 0, 1) * lim(horiz / 0.35, 0, 1);
      if (frente > 0) {
        const yaw = Math.atan2(local.x, local.z) / GRAU;
        const pitch = -Math.atan2(local.y - 0.55, horiz) / GRAU;
        ay = lim(yaw, -55, 55) * frente;
        ap = lim(pitch, -25, 30) * frente;
      }
    }
    const w = 9;
    let resto = dt;
    while (resto > 0) {
      const h = Math.min(resto, 1 / 60);
      this.olharV[0] += ((ay - this.olhar[0]) * w * w - this.olharV[0] * 2 * w) * h;
      this.olharV[1] += ((ap - this.olhar[1]) * w * w - this.olharV[1] * 2 * w) * h;
      this.olhar[0] += this.olharV[0] * h;
      this.olhar[1] += this.olharV[1] * h;
      resto -= h;
    }
  }

  /** IK das pernas com pé travado no chão: cada pé tem um "peso" de apoio
   *  que vai de 0 (segue a animação) a 1 (preso no chão) aos poucos. */
  _ikPernas(dt, voo) {
    const ty = this.chao + this.tornY;
    let passando = this.pes.e.passo >= 0 || this.pes.d.passo >= 0;
    for (const lado of ["e", "d"]) {
      const st = this.pes[lado];
      const fk = this.juntas["pe_" + lado].getWorldPosition(this._v[1]);
      const alturaPe = fk.y - ty;
      const livre = this._v[2].set(fk.x, Math.max(fk.y, ty), fk.z);
      if (this.modoIk !== "trava" || voo > 0.01) {
        st.preso = false;
        st.passo = -1;
      } else if (st.passo >= 0) {
        st.passo = Math.min(1, st.passo + dt / PASSO_DUR);
        const u = st.passo;
        const e = u * u * u * (u * (u * 6 - 15) + 10);
        if (!st.ancora) st.ancora = new this.T.Vector3();
        st.ancora.set(mistura(st.de.x, fk.x, e), mistura(st.de.y, ty, e) + PASSO_ALTURA * Math.sin(Math.PI * u), mistura(st.de.z, fk.z, e));
        if (u >= 1) {
          st.passo = -1;
          st.preso = true;
          st.pos.set(fk.x, ty, fk.z);
          st.ancora.copy(st.pos);
        }
      } else if (st.preso) {
        const longe = Math.hypot(fk.x - st.pos.x, fk.z - st.pos.z);
        if (alturaPe > 0.05) {
          st.preso = false;
        } else if (longe > DIST_PASSO && !passando) {
          st.preso = false;
          st.passo = 0;
          st.de.copy(st.pos);
          passando = true;
        }
        if (!st.ancora) st.ancora = new this.T.Vector3();
        st.ancora.copy(st.pos);
      } else if (alturaPe < 0.02) {
        st.preso = true;
        st.pos.set(fk.x, ty, fk.z);
        if (!st.ancora) st.ancora = new this.T.Vector3();
        st.ancora.copy(st.pos);
      }
      const quer = st.preso || st.passo >= 0 ? 1 : 0;
      st.pesoLin = st.pesoLin < quer ? Math.min(quer, st.pesoLin + dt / TROCA_PE) : Math.max(quer, st.pesoLin - dt / TROCA_PE);
      const w = st.pesoLin * st.pesoLin * (3 - 2 * st.pesoLin);
      const alvo = this._alvos[lado];
      if (w > 0 && st.ancora) alvo.copy(livre).lerp(st.ancora, w);
      else alvo.copy(livre);
    }
    // o quadril desce (suave) se um pé apoiado não alcançaria o chão
    let descer = 0;
    for (const lado of ["e", "d"]) {
      const q = this.juntas["coxa_" + lado].getWorldPosition(this._v[3]);
      const alvo = this._alvos[lado];
      const lmax = (this.l1[lado] + this.l2[lado]) * 0.985;
      const dv = q.y - alvo.y;
      const dh = Math.hypot(q.x - alvo.x, q.z - alvo.z);
      if (dh < lmax) descer = Math.max(descer, dv - Math.sqrt(lmax * lmax - dh * dh));
    }
    descer = lim(descer, 0, 0.12);
    const rapidez = descer > this.descer ? 40 : 12;
    this.descer = mistura(this.descer, descer, 1 - Math.exp(-dt * rapidez));
    if (this.descer > 0.0005) {
      this.juntas.corpo.position.y -= this.descer;
      this.juntas.corpo.updateMatrixWorld(true);
    }
    for (const lado of ["e", "d"]) this._resolverPerna(lado, this._alvos[lado], this.pes[lado].pesoLin > 0.5);
  }

  _resolverPerna(lado, alvo, apoiado) {
    const coxa = this.juntas["coxa_" + lado];
    const canela = this.juntas["canela_" + lado];
    const pe = this.juntas["pe_" + lado];
    const l1 = this.l1[lado];
    const l2 = this.l2[lado];
    const Q = coxa.getWorldPosition(this._v[3]);
    const JFK = canela.getWorldPosition(this._v[4]);
    const V = this._v[5].copy(alvo).sub(Q);
    const d = lim(V.length(), Math.abs(l1 - l2) + 0.001, l1 + l2 - 0.0008);
    const DIR = this._v[6].copy(V).normalize();
    const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
    const h = Math.sqrt(Math.max(l1 * l1 - a * a, 0));
    const FRENTE = this._v[8].set(Math.sin(this.raiz.rotation.y), 0, Math.cos(this.raiz.rotation.y));
    const POLO = this._v[7].copy(JFK).sub(Q);
    POLO.addScaledVector(DIR, -POLO.dot(DIR)).addScaledVector(FRENTE, 0.02);
    POLO.addScaledVector(DIR, -POLO.dot(DIR));
    if (POLO.lengthSq() < 1e-8) POLO.copy(FRENTE);
    POLO.normalize();
    const J = this._v[9].copy(Q).addScaledVector(DIR, a).addScaledVector(POLO, h);
    const de1 = this._v[0].copy(JFK).sub(Q).normalize();
    const para1 = this._v[1].copy(J).sub(Q).normalize();
    if (de1.dot(para1) < 0.99999) {
      this._girarGlobal(coxa, this._q[0].setFromUnitVectors(de1, para1));
      coxa.updateMatrixWorld(true);
    }
    const agora = pe.getWorldPosition(this._v[0]);
    const de2 = this._v[1].copy(agora).sub(J).normalize();
    const para2 = this._v[2].copy(Q).addScaledVector(DIR, d).sub(J).normalize();
    if (de2.dot(para2) < 0.99999) {
      this._girarGlobal(canela, this._q[0].setFromUnitVectors(de2, para2));
      canela.updateMatrixWorld(true);
    }
    // pé de sola chata quando está no chão (ou perto dele)
    const peso = apoiado ? 1 : lim(1 - (alvo.y - this.chao - this.tornY) / 0.08, 0, 1);
    if (peso > 0) {
      const qCanela = canela.getWorldQuaternion(this._q[1]);
      const qPlano = this._q[2].setFromAxisAngle(this._v[0].set(0, 1, 0), this.raiz.rotation.y);
      qPlano.premultiply(qCanela.invert());
      pe.quaternion.slerp(qPlano, peso);
      pe.updateMatrixWorld(true);
    }
  }

  /** Gira uma junta por uma rotação dada no espaço do mundo. */
  _girarGlobal(no, q) {
    const pai = no.parent.getWorldQuaternion(this._q[3]);
    // local = pai⁻¹ · q · pai
    const local = this._q[2].copy(pai).invert().multiply(q).multiply(pai);
    no.quaternion.premultiply(local);
  }

  _sombras(voo) {
    const p = this.raiz.position;
    const esc = lim(1 - voo * 0.9, 0.35, 1) * 0.75;
    this.sombra.position.set(p.x, this.chao + 0.006, p.z);
    this.sombra.scale.set(esc, 1, esc);
    for (const lado of ["e", "d"]) {
      const s = this.sombrasPe[lado];
      const pe = this.juntas["pe_" + lado];
      const g = pe.getWorldPosition(this._v[0]);
      const fx = Math.sin(this.raiz.rotation.y) * 0.025;
      const fz = Math.cos(this.raiz.rotation.y) * 0.025;
      const alto = Math.max(0, g.y - this.chao - this.tornY);
      const e = lim(1 - alto / 0.25, 0.25, 1);
      s.position.set(g.x + fx, this.chao + 0.008, g.z + fz);
      s.rotation.set(0, this.raiz.rotation.y, 0);
      s.scale.set(0.17 * e, 1, 0.24 * e);
    }
  }

  // ---------------------------------------------------------------- rosto
  expressao(nome) {
    this.expressaoAtual = nome;
    this._celula(nome);
    this.alegria = { empolgado: 1.0, risada: 1.0, feliz: 0.7, piscadinha: 0.8, triste: 0.0, concentrado: 0.25, surpreso: 0.5 }[nome] ?? 0.5;
  }

  _celula(nome) {
    let i = EXPRESSOES.indexOf(nome);
    if (i < 0) i = 0;
    this.matCabeca.uniforms.rosto_celula.value.set(i % 4, Math.floor(i / 4));
  }

  _rosto(dt) {
    if (this.piscando > 0) {
      this.piscando -= dt;
      if (this.piscando <= 0) this._celula(this.expressaoAtual);
      return;
    }
    this.piscarEm -= dt;
    if (this.piscarEm <= 0) {
      this.piscarEm = aleat(2.0, 4.5);
      if (["feliz", "concentrado", "surpreso", "empolgado"].includes(this.expressaoAtual)) {
        this.piscando = 0.13;
        this._celula("piscando");
      }
    }
  }

  jatos(ligar) {
    this.jatosLigados = ligar;
  }

  segurarBola(sim) {
    this.bolaMao.visible = sim;
  }

  /** Coloca o personagem num lugar, olhando para `direcaoY` (graus). */
  posicionar(pos, direcaoY) {
    this.raiz.position.set(pos[0], pos[1], pos[2]);
    this.raiz.rotation.set(0, direcaoY * GRAU, 0);
    this.chao = pos[1];
    this.base.set(pos[0], pos[1], pos[2]);
    this.baseYaw = direcaoY * GRAU;
    for (const lado of ["e", "d"]) {
      const st = this.pes[lado];
      st.preso = false;
      st.passo = -1;
      st.pesoLin = 0;
    }
    this.descer = 0;
  }

  /** Brilho de destaque (personagem escolhido fica "aceso"). */
  destaque(valor) {
    for (const m of this.mats_) m.uniforms.flash.value = valor;
  }

  set visivel(v) {
    this.raiz.visible = v;
    this.sombra.visible = v;
    this.sombrasPe.e.visible = v;
    this.sombrasPe.d.visible = v;
  }

  get visivel() {
    return this.raiz.visible;
  }

  liberar() {
    this.geoBola.dispose();
    this.geoSombra.dispose();
  }
}

/* ----------------------------------------------------------------------
   O HUD (scripts/hud.gd): tudo o que é 2D por cima do 3D — placar, mapa
   dos pinos, o convite "ROLE A BOLA!", letreiros (STRIKE!...), a faixa
   "VEZ DO BOB!", o nome do cenário, o modo replay, a escolha do amigo e o
   fim de jogo. As placas com volume (Painel3D: degradê, verniz, lateral e
   contorno azul-marinho) são desenhadas uma vez e guardadas.
   ---------------------------------------------------------------------- */
function clarear(c, k) {
  return c.map((v) => v + (1 - v) * k);
}
function escurecer(c, k) {
  return c.map((v) => v * (1 - k));
}
function rgb(c, a = 1) {
  return `rgba(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)}, ${a})`;
}
function caminhoArredondado(ctx, x, y, w, h, r) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

class Hud {
  constructor(api, artes) {
    this.api = api;
    this.artes = artes;
    this.W = LARGURA;
    this.H = ALTURA;
    this.t = 0;
    this.cache = new Map();
    this.itens = [];
    this.flashCor = [1, 1, 1];
    this.flashA = 0;
    this.flashDur = 0.35;
    this.placarVisivel = false;
    this.cartao = { personagem: "bob", valor: 0, alvo: 0, pulo: 0 };
    this.rodadas = [];
    this.info = "";
    this.bolas = { total: TENTATIVAS, usadas: 0 };
    this.mapa = null;
    this.convite = false;
    this.sequenciaN = 0;
    this.sequenciaPulo = 0;
    this.replay = 0;
    this.replayAlvo = 0;
    this.selecao = null;
    this.fim = null;
    this.bolaArrasto = null;
  }

  /** Placa com volume (Painel3D), guardada pelo tamanho e pela cor. */
  painel(w, h, cor, raio, espessura, borda, brilho = 0.24) {
    const chave = [Math.round(w), Math.round(h), cor, raio, espessura, borda, brilho].join("|");
    let c = this.cache.get(chave);
    if (c) return c;
    const m = Math.max(6, raio * 0.9 + espessura) * U;
    const esc = 2;
    const cv = document.createElement("canvas");
    cv.width = Math.ceil((w + m * 2) * esc);
    cv.height = Math.ceil((h + m * 2) * esc);
    const ctx = cv.getContext("2d");
    ctx.scale(esc, esc);
    ctx.translate(m, m);
    const base = hex(cor);
    const r = raio * U;
    const b = borda * U;
    const e = espessura * U;
    // sombra macia embaixo
    ctx.save();
    ctx.shadowColor = "rgba(0, 8, 26, 0.45)";
    ctx.shadowBlur = m * 0.8;
    ctx.shadowOffsetY = m * 0.35;
    caminhoArredondado(ctx, 0, 0, w, h, r);
    ctx.fillStyle = MARINHO;
    ctx.fill();
    ctx.restore();
    // contorno + lateral (espessura, mais escura embaixo)
    caminhoArredondado(ctx, 0, 0, w, h, r);
    ctx.fillStyle = MARINHO;
    ctx.fill();
    const lado = escurecer(base, 0.52);
    caminhoArredondado(ctx, b, b, w - 2 * b, h - 2 * b, r - b);
    const gl = ctx.createLinearGradient(0, h - e - b, 0, h - b);
    gl.addColorStop(0, rgb(clarear(lado, 0.1)));
    gl.addColorStop(1, rgb(escurecer(lado, 0.25)));
    ctx.fillStyle = gl;
    ctx.fill();
    // frente: degradê + verniz + filete claro
    const altF = Math.max(h - b - e - b, 2 * (r - b));
    caminhoArredondado(ctx, b, b, w - 2 * b, altF, r - b);
    const gf = ctx.createLinearGradient(0, b, 0, b + altF);
    gf.addColorStop(0, rgb(clarear(base, 0.2)));
    gf.addColorStop(0.75, rgb(escurecer(base, 0.1)));
    gf.addColorStop(1, rgb(escurecer(base, 0.24)));
    ctx.fillStyle = gf;
    ctx.fill();
    ctx.save();
    ctx.clip();
    if (brilho > 0) {
      const vy = b + altF * 0.07;
      caminhoArredondado(ctx, b + r * 0.3 + b, vy, w - 2 * (b + r * 0.3 + b), altF * 0.38, r * 0.75);
      const gv = ctx.createLinearGradient(0, vy, 0, vy + altF * 0.38);
      gv.addColorStop(0, `rgba(255,255,255,${brilho})`);
      gv.addColorStop(1, `rgba(255,255,255,${brilho * 0.15})`);
      ctx.fillStyle = gv;
      ctx.fill();
    }
    ctx.restore();
    caminhoArredondado(ctx, b + b * 0.4 + 1, b + b * 0.4 + 1, w - 2 * (b + b * 0.4 + 1), altF - 2 * (b * 0.4 + 1), r - b * 1.4);
    ctx.strokeStyle = "rgba(255,255,255,0.5)";
    ctx.lineWidth = Math.max(1, b * 0.45);
    ctx.stroke();
    c = { cv, m };
    this.cache.set(chave, c);
    return c;
  }

  desenharPainel(ctx, x, y, w, h, cor, raio, espessura, borda, escala = 1, alfa = 1, realce = 0) {
    const p = this.painel(w, h, cor, raio, espessura, borda);
    ctx.save();
    ctx.globalAlpha *= alfa;
    ctx.translate(x + w / 2, y + h / 2);
    ctx.scale(escala, escala);
    if (realce > 0) {
      ctx.save();
      ctx.globalAlpha *= realce * 0.85;
      caminhoArredondado(ctx, -w / 2 - 8, -h / 2 - 8, w + 16, h + 16, raio * U + 8);
      ctx.fillStyle = "#FFD640";
      ctx.fill();
      ctx.restore();
    }
    ctx.drawImage(p.cv, -w / 2 - p.m, -h / 2 - p.m, w + 2 * p.m, h + 2 * p.m);
    ctx.restore();
  }

  /** Texto com contorno e sombrinha (LabelSettings do Godot). */
  texto(ctx, s, x, y, tam, cor = "#FFFFFF", contorno = 0, corContorno = MARINHO, titulo = false, alinhar = "center", sombra = true) {
    ctx.save();
    ctx.font = `${titulo ? 400 : 700} ${Math.round(tam)}px ${titulo ? FONTE_TITULO : FONTE}`;
    ctx.textAlign = alinhar;
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    if (sombra) {
      const off = Math.max(1, tam * 0.06);
      ctx.fillStyle = "rgba(0, 13, 38, 0.45)";
      if (contorno > 0) {
        ctx.strokeStyle = "rgba(0, 13, 38, 0.45)";
        ctx.lineWidth = contorno;
        ctx.strokeText(s, x, y + off);
      }
      ctx.fillText(s, x, y + off);
    }
    if (contorno > 0) {
      ctx.strokeStyle = corContorno;
      ctx.lineWidth = contorno;
      ctx.strokeText(s, x, y);
    }
    ctx.fillStyle = cor;
    ctx.fillText(s, x, y);
    ctx.restore();
  }

  larguraTexto(ctx, s, tam, titulo) {
    ctx.save();
    ctx.font = `${titulo ? 400 : 700} ${Math.round(tam)}px ${titulo ? FONTE_TITULO : FONTE}`;
    const w = ctx.measureText(s).width;
    ctx.restore();
    return w;
  }

  // ---------------------------------------------------------------- comandos (os mesmos nomes do hud.gd)
  flash(cor = "#FFFFFF", forca = 0.7, dur = 0.35) {
    // menos movimento: o clarão vira só um brilho leve
    if (this.api.reduzido) forca *= 0.3;
    this.flashCor = hex(cor);
    this.flashA = forca;
    this.flashDur = dur;
    this.flashForca = forca;
  }

  mostrarPlacar(sim) {
    this.placarVisivel = sim;
  }

  configurarPlacar(personagem) {
    this.cartao = { personagem, valor: 0, alvo: 0, pulo: 0 };
  }

  atualizarPlacar(placar) {
    const j = placar.jogadores[0];
    this.cartao.alvo = j.pontos;
    this.rodadas = j.rodadas.map((bolas, r) => {
      const soma = bolas.reduce((a, b) => a + b, 0);
      return { bolas: bolas.length, soma, atual: r === placar.rodadaAtual };
    });
    this.info = `RODADA ${placar.rodadaAtual + 1} de ${placar.rodadas}`;
    this.bolas = { total: placar.tentativas, usadas: placar.bolaAtual, cor: j.personagem === "bob" ? COR_BOB : COR_MIA };
  }

  mostrarMapa(emPe) {
    this.mapa = emPe.slice();
  }

  conviteLigado(sim) {
    this.convite = sim;
  }

  sequencia(n) {
    if (n >= 2 && n !== this.sequenciaN) this.sequenciaPulo = 1;
    this.sequenciaN = n;
  }

  modoReplay(sim) {
    this.replayAlvo = sim ? 1 : 0;
  }

  /** Letreiro grande no centro (STRIKE!, SPARE!...) + texto embaixo. */
  letreiro(nome, sub = "", dur = 1.7, altura = 0.38) {
    const img = this.artes[nome];
    if (!img) return;
    // a arte original foi feita em 1,6x (ESCALA_ARTE): a largura dela na tela
    const larg = Math.min(this.W * 0.9, (LARGURA_ARTE[nome] || img.naturalWidth) / 1.6 * U * 0.95);
    this.itens.push({ tipo: "letreiro", img, t: 0, dur, altura, larg, sub });
    this._estrelas2d(this.W / 2, this.H * altura, 26);
  }

  /** Texto grande simples (ex.: "INSIRA FICHA"). */
  textoGrande(texto, cor = CREME, dur = 1.4, altura = 0.38) {
    this.itens.push({ tipo: "texto", texto, cor, t: 0, dur, altura });
  }

  /** Nome do cenário (letreiro grande que entra girando e sai). */
  anunciarCenario(tema, dur = 2.2) {
    const img = this.artes["cen_" + tema];
    if (!img) return;
    this.itens.push({ tipo: "cenario", img, t: 0, dur });
  }

  /** Faixa "VEZ DO BOB!" atravessando a tela. */
  faixa(personagem, texto, sub = "") {
    this.itens.push({ tipo: "faixa", personagem, texto, sub, t: 0 });
  }

  /** "+120" voando até o placar. */
  pontosVoando(pontos) {
    this.itens.push({ tipo: "pontos", pontos, t: 0 });
  }

  _estrelas2d(x, y, n) {
    const cores = ["#FFE14D", "#7FE7FF", "#FF9F2E"];
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU;
      const r = Math.random() * 60 * U;
      const v = aleat(450, 900) * U;
      const dir = -Math.PI / 2 + aleat(-Math.PI, Math.PI);
      this.itens.push({
        tipo: "estrela", x: x + Math.cos(a) * r, y: y + Math.sin(a) * r, vx: Math.cos(dir) * v, vy: Math.sin(dir) * v,
        giro: Math.random() * TAU, vgiro: aleat(-6.3, 6.3), tam: aleat(0.12, 0.3) * U * 256, cor: sortear(cores), t: 0, dur: 1.0,
      });
    }
  }

  // ---------------------------------------------------------------- tempo
  atualizar(dt) {
    this.t += dt;
    if (this.flashA > 0) this.flashA = Math.max(0, this.flashA - dt * this.flashForca / this.flashDur);
    const c = this.cartao;
    if (c.valor < c.alvo) c.valor = Math.min(c.alvo, c.valor + dt * Math.max(60, (c.alvo - c.valor) * 3));
    c.pulo = Math.max(0, c.pulo - dt * 2.6);
    this.sequenciaPulo = Math.max(0, this.sequenciaPulo - dt * 3);
    this.replay = this.replay < this.replayAlvo ? Math.min(1, this.replay + dt / 0.35) : Math.max(0, this.replay - dt / 0.35);
    for (const it of this.itens) {
      it.t += dt;
      if (it.tipo === "estrela") {
        it.vy += 900 * U * dt;
        it.x += it.vx * dt;
        it.y += it.vy * dt;
        it.giro += it.vgiro * dt;
      }
    }
    // tira os que acabaram sem criar uma lista nova a cada quadro
    let n = 0;
    for (let i = 0; i < this.itens.length; i++) {
      const it = this.itens[i];
      if (this._itemVivo(it)) this.itens[n++] = it;
    }
    this.itens.length = n;
    // a bola de arrastar, depois de rolada, sobe pela tela e some
    const b = this.bolaArrasto;
    if (b && b.voando) {
      b.x += b.voando.vx * dt;
      b.y += b.voando.vy * dt;
      b.raio = Math.max(4, b.raio - 40 * dt);
      b.giro += dt * 9;
      b.alfa -= dt * 3.2;
      if (b.alfa <= 0) this.bolaArrasto = null;
    }
  }

  _itemVivo(it) {
    if (it.tipo === "letreiro") return it.t < 0.22 + 0.18 + it.dur * 0.5 + 0.3;
    if (it.tipo === "texto") return it.t < 0.35 + it.dur + 0.3;
    if (it.tipo === "cenario") return it.t < 0.55 + it.dur + 0.3;
    if (it.tipo === "faixa") return it.t < 0.38 + 1.25 + 0.3;
    if (it.tipo === "pontos") {
      if (it.t >= 1.05 && !it.chegou) {
        it.chegou = true;
        this.cartao.pulo = 1;
      }
      return it.t < 1.05;
    }
    return it.t < it.dur;
  }

  // ---------------------------------------------------------------- desenho
  desenhar(ctx, extra) {
    if (this.placarVisivel && this.replay < 0.5) this._placar(ctx);
    if (this.convite) this._convite(ctx);
    if (this.bolaArrasto) this._bolaArrasto(ctx, this.bolaArrasto);
    if (this.selecao) this._selecao(ctx, extra);
    if (this.replay > 0) this._replay(ctx);
    if (this.fim) this._fim(ctx);
    for (const it of this.itens) this._item(ctx, it);
    if (this.flashA > 0) {
      ctx.fillStyle = rgb(this.flashCor, this.flashA);
      ctx.fillRect(0, 0, this.W, this.H);
    }
  }

  _placar(ctx) {
    const margem = 26 * U;
    const alt = 200 * U;
    const larg = this.W * 0.62;
    const x = (this.W - larg) / 2;
    const y = margem + 40 * U;
    const c = this.cartao;
    const cor = c.personagem === "bob" ? COR_BOB : COR_MIA;
    const esc = 1 + Math.sin(Math.min(c.pulo, 1) * Math.PI) * 0.08;
    ctx.save();
    ctx.translate(x + larg / 2, y + alt / 2);
    ctx.scale(esc, esc);
    ctx.translate(-larg / 2, -alt / 2);
    this.desenharPainel(ctx, 0, 0, larg, alt, cor, 34, 12, 6);
    const av = this.artes["retrato_" + c.personagem];
    if (av) ctx.drawImage(av, -alt * 0.12, -alt * 0.32, alt * 1.15, alt * 1.15);
    this.texto(ctx, c.personagem.toUpperCase(), alt * 0.98, 10 * U + 27 * U, 42 * U, "#FFFFFF", 10 * U, MARINHO, false, "left");
    this.texto(ctx, String(Math.floor(c.valor)), alt * 0.98, 52 * U + 44 * U, 78 * U, CREME, 14 * U, MARINHO, true, "left");
    // as rodadas: célula clara (por jogar), branca (pontos), estrela (strike), azul (spare)
    const cel = 46 * U;
    let cx = alt * 0.98;
    const cy = alt - 64 * U;
    for (const r of this.rodadas) {
      let fundo = "rgba(255,255,255,0.22)";
      let txt = "";
      let estrela = false;
      if (r.bolas > 0) {
        fundo = "rgba(255,255,255,0.95)";
        txt = String(r.soma);
        if (r.soma >= 10 && r.bolas === 1) {
          fundo = "#FFD43B";
          txt = "";
          estrela = true;
        } else if (r.soma >= 10) {
          fundo = "#7FE7FF";
        }
      }
      caminhoArredondado(ctx, cx, cy, cel, cel, 23 * U);
      ctx.fillStyle = fundo;
      ctx.fill();
      if (r.atual) {
        ctx.lineWidth = 4 * U;
        ctx.strokeStyle = DESTAQUE;
        ctx.stroke();
      }
      if (txt) this.texto(ctx, txt, cx + cel / 2, cy + cel / 2 + 1, 26 * U, MARINHO, 0, MARINHO, false, "center", false);
      if (estrela && this.artes.estrela_placar) ctx.drawImage(this.artes.estrela_placar, cx, cy, cel, cel);
      cx += cel + 8 * U;
    }
    ctx.restore();
    const baseY = y + alt + 16 * U;
    this.texto(ctx, this.info, this.W / 2, baseY + 24 * U, 34 * U, "#FFFFFF", 9 * U);
    // as bolas da rodada
    const b = this.bolas;
    const tb = 34 * U;
    const gap = 14 * U;
    let bx = this.W / 2 - (b.total * tb + (b.total - 1) * gap) / 2;
    for (let k = 0; k < b.total; k++) {
      ctx.beginPath();
      ctx.arc(bx + tb / 2, baseY + 52 * U + tb / 2, tb / 2, 0, TAU);
      ctx.fillStyle = k < b.usadas ? "rgba(255,255,255,0.25)" : (b.cor || COR_BOB);
      ctx.fill();
      ctx.lineWidth = 3 * U;
      ctx.strokeStyle = "#FFFFFF";
      ctx.stroke();
      bx += tb + gap;
    }
    // mapa dos pinos (canto)
    if (this.mapa) {
      const ms = 190 * U;
      const mx = this.W - ms - margem;
      const my = baseY + 8 * U;
      this.desenharPainel(ctx, mx, my, ms, ms * 0.86, AZUL, 26, 8, 4);
      for (let n = 1; n <= 10; n++) {
        const p = posicaoDoPino(n);
        const r = 24 * U;
        const fx = p[0] / (ESPACO_PINOS * 1.5);
        const fy = (Z_PINO1 - p[2]) / (FILEIRA * 3);
        const px = mx + ms / 2 + fx * ms * 0.36;
        const py = my + ms * 0.86 * (0.78 - fy * 0.56);
        const dePe = this.mapa.includes(n);
        ctx.beginPath();
        ctx.arc(px, py, r / 2, 0, TAU);
        ctx.fillStyle = dePe ? "#FFFFFF" : "rgba(255,255,255,0.12)";
        ctx.fill();
        if (dePe) {
          ctx.lineWidth = 3 * U;
          ctx.strokeStyle = DESTAQUE;
          ctx.stroke();
        }
      }
    }
    if (this.sequenciaN >= 2) {
      const e = 1 + Math.sin(Math.min(this.sequenciaPulo, 1) * Math.PI) * 0.1;
      ctx.save();
      ctx.translate(this.W / 2, baseY + 128 * U);
      ctx.scale(e, e);
      this.texto(ctx, `${this.sequenciaN} STRIKES SEGUIDOS!`, 0, 0, 40 * U, CREME, 10 * U, "#7A1E00", true);
      ctx.restore();
    }
  }

  _convite(ctx) {
    const y = this.H - 330 * U;
    const e = 1 + Math.sin(this.t * 5) * 0.05;
    ctx.save();
    ctx.translate(this.W / 2, y + 60 * U);
    ctx.scale(e, e);
    this.texto(ctx, "ROLE A BOLA!", 0, 0, 84 * U, CREME, 20 * U, MARINHO, true);
    ctx.restore();
    ctx.save();
    ctx.globalAlpha = 0.6 + 0.4 * Math.abs(Math.sin(this.t * 2.6));
    this.texto(ctx, "mire no STRIKE!", this.W / 2, y + 112 * U + 32 * U, 44 * U, "#FFFFFF", 11 * U);
    ctx.restore();
  }

  /** A bola que a pessoa arrasta (a bola de verdade da máquina). */
  _bolaArrasto(ctx, b) {
    const img = this.artes["bola_" + b.personagem];
    const r = b.raio;
    ctx.save();
    ctx.globalAlpha = b.alfa;
    // sombrinha no chão
    ctx.fillStyle = "rgba(0, 10, 30, 0.35)";
    ctx.beginPath();
    ctx.ellipse(b.x, b.y + r * 0.92, r * 0.85, r * 0.22, 0, 0, TAU);
    ctx.fill();
    ctx.translate(b.x, b.y);
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, TAU);
    ctx.save();
    ctx.clip();
    if (img) {
      // a textura da bola (equirretangular): a metade da frente, girando
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      const giro = (b.giro / TAU) % 1;
      const sx = ((giro * w) % w + w) % w;
      const larg = w * 0.5;
      ctx.drawImage(img, sx, h * 0.1, Math.min(larg, w - sx), h * 0.8, -r, -r, 2 * r * Math.min(larg, w - sx) / larg, 2 * r);
      if (w - sx < larg) ctx.drawImage(img, 0, h * 0.1, larg - (w - sx), h * 0.8, -r + 2 * r * (w - sx) / larg, -r, 2 * r * (larg - (w - sx)) / larg, 2 * r);
    } else {
      ctx.fillStyle = b.personagem === "bob" ? "#E8384F" : "#FF8A2B";
      ctx.fillRect(-r, -r, 2 * r, 2 * r);
    }
    // volume: sombra embaixo, luz em cima e o reflexo do verniz
    if (!this._volumeBola || this._volumeBolaR !== r) {
      const g = ctx.createRadialGradient(-r * 0.35, -r * 0.4, r * 0.1, 0, 0, r * 1.05);
      g.addColorStop(0, "rgba(255,255,255,0.28)");
      g.addColorStop(0.55, "rgba(255,255,255,0)");
      g.addColorStop(1, "rgba(0,10,40,0.55)");
      this._volumeBola = g;
      this._volumeBolaR = r;
    }
    ctx.fillStyle = this._volumeBola;
    ctx.fillRect(-r, -r, 2 * r, 2 * r);
    ctx.restore();
    ctx.lineWidth = 3;
    ctx.strokeStyle = MARINHO;
    ctx.stroke();
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.beginPath();
    ctx.ellipse(-r * 0.38, -r * 0.45, r * 0.16, r * 0.1, -0.6, 0, TAU);
    ctx.fill();
    ctx.restore();
  }

  _item(ctx, it) {
    const W = this.W;
    const H = this.H;
    if (it.tipo === "letreiro") {
      const img = it.img;
      const larg = it.larg;
      const alt = larg * img.naturalHeight / img.naturalWidth;
      let esc;
      let rot;
      let dy = 0;
      let alfa = 1;
      const t = it.t;
      const t1 = 0.22;
      const t2 = t1 + 0.18;
      const t3 = t2 + it.dur * 0.5;
      if (t < t1) {
        const u = t / t1;
        esc = 1.18 * voltaElastica(u);
        rot = mistura(-12, 3, u) * GRAU;
      } else if (t < t2) {
        const u = senoIO((t - t1) / 0.18);
        esc = mistura(1.18, 1, u);
        rot = mistura(3, 0, u) * GRAU;
      } else if (t < t3) {
        esc = mistura(1, 1.05, senoIO((t - t2) / (t3 - t2)));
        rot = 0;
      } else {
        const u = Math.min(1, (t - t3) / 0.3);
        esc = 1.05;
        rot = 0;
        dy = -120 * U * voltaEntrando(u);
        alfa = 1 - u;
      }
      ctx.save();
      ctx.globalAlpha = Math.max(0, alfa);
      ctx.translate(W / 2, H * it.altura + dy);
      ctx.rotate(rot);
      ctx.scale(Math.max(esc, 0.001), Math.max(esc, 0.001));
      ctx.drawImage(img, -larg / 2, -alt / 2, larg, alt);
      ctx.restore();
      if (it.sub) {
        const ts = Math.max(0, t - 0.18);
        const e = ts < 0.3 ? voltaElastica(ts / 0.3) : 1;
        const fimSub = 0.18 + 0.3 + it.dur * 0.55;
        const a = t < fimSub ? 1 : Math.max(0, 1 - (t - fimSub) / 0.3);
        if (e > 0.001 && a > 0) {
          ctx.save();
          ctx.globalAlpha = a;
          ctx.translate(W / 2, H * it.altura + alt / 2 + 10 * U + 45 * U);
          ctx.scale(e, e);
          this.texto(ctx, it.sub, 0, 0, 58 * U, "#FFFFFF", 14 * U, MARINHO, true);
          ctx.restore();
        }
      }
    } else if (it.tipo === "texto") {
      const t = it.t;
      const e = t < 0.2 ? 1.12 * voltaElastica(t / 0.2) : t < 0.35 ? mistura(1.12, 1, (t - 0.2) / 0.15) : 1;
      const a = t < 0.35 + it.dur ? 1 : Math.max(0, 1 - (t - 0.35 - it.dur) / 0.3);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(W / 2, H * it.altura);
      ctx.scale(e, e);
      this.texto(ctx, it.texto, 0, 0, 110 * U, it.cor, 22 * U, MARINHO, true);
      ctx.restore();
    } else if (it.tipo === "cenario") {
      const img = it.img;
      const w = Math.min(W * 0.86, 900 * U);
      const h = w * img.naturalHeight / img.naturalWidth;
      const t = it.t;
      let esc;
      let rot = 0;
      let a = 1;
      if (t < 0.55) {
        const u = voltaElastica(t / 0.55);
        esc = u;
        rot = mistura(-0.5, 0, u);
      } else if (t < 0.55 + it.dur) {
        esc = 1;
      } else {
        const u = Math.min(1, (t - 0.55 - it.dur) / 0.3);
        esc = mistura(1, 1.25, u);
        a = 1 - u;
      }
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(W / 2, H * 0.3);
      ctx.rotate(rot);
      ctx.scale(Math.max(esc, 0.001), Math.max(esc, 0.001));
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
      ctx.restore();
    } else if (it.tipo === "faixa") {
      const h = 210 * U;
      const w = Math.min(W * 0.92, 980 * U);
      const y = H * 0.3;
      const t = it.t;
      let x;
      if (t < 0.38) x = mistura(-w - 50 * U, (W - w) / 2, voltaElastica(t / 0.38));
      else if (t < 0.38 + 1.25) x = (W - w) / 2;
      else x = mistura((W - w) / 2, W + 50 * U, voltaEntrando(Math.min(1, (t - 1.63) / 0.3)));
      const cor = it.personagem === "bob" ? COR_BOB : COR_MIA;
      this.desenharPainel(ctx, x, y, w, h, cor, 40, 14, 7);
      const av = this.artes["retrato_" + it.personagem];
      if (av) ctx.drawImage(av, x - h * 0.15, y - h * 0.35, h * 1.25, h * 1.25);
      const tx = x + h * 1.05 + (w - h * 1.1) / 2;
      const tam = (it.sub ? 58 : 70) * U;
      if (it.sub) {
        this.texto(ctx, it.texto, tx, y + h * 0.36, tam, "#FFFFFF", 16 * U, MARINHO, true);
        this.texto(ctx, it.sub, tx, y + h * 0.68, tam, "#FFFFFF", 16 * U, MARINHO, true);
      } else {
        this.texto(ctx, it.texto, tx, y + h * 0.5, tam, "#FFFFFF", 16 * U, MARINHO, true);
      }
    } else if (it.tipo === "pontos") {
      const t = it.t;
      const x0 = W / 2;
      const y0 = H * 0.5 + 60 * U;
      const xd = W / 2;
      const yd = 26 * U + 40 * U + 100 * U;
      let x = x0;
      let y = y0;
      let e = 1;
      if (t < 0.15) e = mistura(1, 1.2, t / 0.15);
      else if (t < 0.5) e = 1.2;
      else {
        const u = FACIL.quadEntra(Math.min(1, (t - 0.5) / 0.55));
        x = mistura(x0, xd, u);
        y = mistura(y0, yd, u);
        e = mistura(1.2, 0.5, u);
      }
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(e, e);
      this.texto(ctx, "+" + it.pontos, 0, 0, 84 * U, CREME, 18 * U, MARINHO, true);
      ctx.restore();
    } else if (it.tipo === "estrela") {
      const img = this._estrelaTingida(it.cor);
      if (!img) return;
      const a = Math.max(0, 1 - it.t / it.dur);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(it.x, it.y);
      ctx.rotate(it.giro);
      const s = it.tam;
      ctx.drawImage(img, -s / 2, -s / 2, s, s);
      ctx.restore();
    }
  }

  /** A estrelinha já pintada na cor (feita uma vez por cor, num canvas à
   *  parte: pintar "por cima" na tela tingiria o 3D atrás dela). */
  _estrelaTingida(cor) {
    const img = this.artes.estrela;
    if (!img) return null;
    this._estrelas = this._estrelas || {};
    let c = this._estrelas[cor];
    if (!c) {
      c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const g = c.getContext("2d");
      g.drawImage(img, 0, 0);
      g.globalCompositeOperation = "source-atop";
      g.globalAlpha = 0.55;
      g.fillStyle = cor;
      g.fillRect(0, 0, c.width, c.height);
      this._estrelas[cor] = c;
    }
    return c;
  }

  _replay(ctx) {
    const h = this.H * 0.1 * this.replay;
    ctx.fillStyle = "rgb(3, 8, 23)";
    ctx.fillRect(0, 0, this.W, h);
    ctx.fillRect(0, this.H - h, this.W, h);
    if (this.replayAlvo > 0 && this.artes.replay) {
      const w = 420 * U;
      const x = this.W - w - 40 * U;
      const y = this.H * 0.1 * 0.5 - w * 0.118;
      ctx.drawImage(this.artes.replay, x, y, w, w * 0.236);
      if ((this.t % 1) < 0.6) {
        ctx.fillStyle = "#FF2E4D";
        ctx.beginPath();
        ctx.arc(x - 50 * U + 17 * U, y + w * 0.118, 17 * U, 0, TAU);
        ctx.fill();
      }
    }
  }

  /** ESCOLHA SEU AMIGO: título, placas com os nomes embaixo dos pódios e a dica. */
  _selecao(ctx, extra) {
    const s = this.selecao;
    const W = this.W;
    const sw = Math.min(W * 0.9, 900 * U);
    const entra = Math.min(1, s.t / 0.3);
    const et = 1 + Math.sin(Math.min(entra, 1) * Math.PI) * 0.08;
    ctx.save();
    ctx.translate(W / 2, 112 * U + 65 * U);
    ctx.scale(et, et);
    this.desenharPainel(ctx, -sw / 2, -65 * U, sw, 130 * U, AZUL, 44, 14, 7);
    this.texto(ctx, "ESCOLHA SEU AMIGO!", 0, -6 * U, 74 * U, CREME, 16 * U, MARINHO, true);
    ctx.restore();
    const pes = extra && extra.pes;
    for (let i = 0; i < 2; i++) {
      const pw = 330 * U;
      const ph = 116 * U;
      const pe = pes ? pes[i] : [W * (i === 0 ? 0.27 : 0.73), this.H * 0.64];
      const x = lim(pe[0] - pw / 2, 12 * U, W - pw - 12 * U);
      const y = pe[1] + 30 * U;
      const alvo = i === s.destaque ? 1.12 : 0.9;
      s.escalas[i] = mistura(s.escalas[i], alvo, 0.25);
      const realce = i === s.destaque ? 0.7 + 0.3 * Math.sin(this.t * 6) : 0;
      this.desenharPainel(ctx, x, y, pw, ph, i === 0 ? COR_BOB : COR_MIA, 36, 14, 7, s.escalas[i], i === s.destaque ? 1 : 0.85, realce);
      ctx.save();
      ctx.translate(x + pw / 2, y + ph / 2 - 7 * U);
      ctx.scale(s.escalas[i], s.escalas[i]);
      this.texto(ctx, i === 0 ? "BOB" : "MIA", 0, 0, 70 * U, "#FFFFFF", 16 * U, MARINHO, true);
      ctx.restore();
    }
    const dw = Math.min(W * 0.9, 860 * U);
    const dh = 150 * U;
    const dy = this.H - dh - 60 * U;
    this.desenharPainel(ctx, (W - dw) / 2, dy, dw, dh, "#203A6E", 30, 8, 5, 1, 0.94);
    this.texto(ctx, "ROLE A BOLA PARA ESCOLHER SEU AMIGO", W / 2, dy + 40 * U, 32 * U, "#FFFFFF", 9 * U);
    this.texto(ctx, `bola no MEIO ou toque no amigo confirma   (${Math.max(0, Math.ceil(s.resta))})`, W / 2, dy + 92 * U, 32 * U, CREME, 9 * U);
  }

  /** FIM DE JOGO: o logo, o cartão do jogador (pontos contando, estrelas,
   *  lugar no dia) e a CLASSIFICAÇÃO DE HOJE. */
  _fim(ctx) {
    const f = this.fim;
    const W = this.W;
    const t = f.t;
    ctx.fillStyle = "rgba(4, 12, 40, 0.35)";
    ctx.fillRect(0, 0, W, this.H);
    const titulo = this.artes.fim_de_jogo;
    if (titulo) {
      const tw = Math.min(W * 0.42, 440 * U) * 1.25;
      const th = tw * 0.61;
      const e = voltaElastica(Math.min(1, t / 0.45));
      ctx.save();
      ctx.translate(W / 2, 40 * U + th / 2);
      ctx.scale(Math.max(e, 0.001), Math.max(e, 0.001));
      ctx.drawImage(titulo, -tw / 2, -th / 2, tw, th);
      ctx.restore();
    }
    const j = f.jogador;
    const cor = j.personagem === "bob" ? COR_BOB : COR_MIA;
    const w = 300 * U * 1.6;
    const d = Math.min(w * 0.5, 250 * U);
    const h = 472 * U;
    const x = (W - w) / 2;
    const y0 = 40 * U + Math.min(W * 0.42, 440 * U) * 1.25 * 0.61 + 6 * U + d * 0.42;
    const ue = Math.min(1, Math.max(0, t - 0.3) / 0.5);
    const y = mistura(y0 + 900 * U, y0, voltaElastica(ue));
    this.desenharPainel(ctx, x, y, w, h, cor, 44, 18, 8);
    const av = this.artes[(j.estrelas >= 2 ? "retrato_" + j.personagem + "_empolgado" : "retrato_" + j.personagem)] || this.artes["retrato_" + j.personagem];
    if (av) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(x + w / 2, y - d * 0.42 + d / 2, d / 2, 0, TAU);
      ctx.fillStyle = "#FFFFFF";
      ctx.fill();
      ctx.lineWidth = 6 * U;
      ctx.strokeStyle = MARINHO;
      ctx.stroke();
      ctx.clip();
      ctx.drawImage(av, x + w / 2 - d / 2, y - d * 0.42, d, d);
      ctx.restore();
    }
    const yy = y + d * 0.6;
    this.texto(ctx, j.personagem.toUpperCase(), x + w / 2, yy + 29 * U, 46 * U, "#FFFFFF", 10 * U, MARINHO, true);
    const pts = t < 0.8 ? 0 : Math.round(j.pontos * FACIL.quadSai(Math.min(1, (t - 0.8) / 1.4)));
    this.texto(ctx, String(pts), x + w / 2, yy + 44 * U + 50 * U, 96 * U, CREME, 20 * U, MARINHO, true);
    this.texto(ctx, "PONTOS", x + w / 2, yy + 136 * U + 17 * U, 30 * U, "#FFFFFF", 7 * U);
    for (let k = 0; k < 3; k++) {
      const img = this.artes[k < j.estrelas ? "estrela_placar" : "estrela_vazia"];
      const es = (k === 1 ? 64 : 54) * U * 1.3;
      const ek = voltaElastica(lim((t - 2.2 - k * 0.25) / 0.35, 0, 1));
      if (img && ek > 0.001) {
        ctx.save();
        ctx.translate(x + w / 2 + (k - 1) * 72 * U * 1.3, yy + 176 * U + es / 2 - (k === 1 ? 6 * U : 0) + 10 * U);
        ctx.scale(ek, ek);
        ctx.drawImage(img, -es / 2, -es / 2, es, es);
        ctx.restore();
      }
    }
    if (f.posicao > 0) {
      const fh = 58 * U;
      const fw = w * 0.88;
      const ef = voltaElastica(lim((t - 2.8) / 0.4, 0, 1));
      if (ef > 0.001) {
        const corM = { 1: "#FFC21A", 2: "#DCE6F2", 3: "#F0A25A" }[f.posicao] || AZUL;
        ctx.save();
        ctx.translate(x + w / 2, y + h - fh / 2 - 16 * U);
        ctx.scale(ef, ef);
        this.desenharPainel(ctx, -fw / 2, -fh / 2, fw, fh, corM, 28, 8, 5);
        const txt = f.posicao <= 3 ? `${f.posicao}º LUGAR HOJE!` : `${f.posicao}º LUGAR HOJE`;
        this.texto(ctx, txt, 0, -3 * U, 34 * U, f.posicao <= 3 ? MARINHO : "#FFFFFF", f.posicao <= 3 ? 0 : 7 * U, MARINHO, true);
        ctx.restore();
      }
    }
    // classificação de hoje (os 5 melhores, cada um com o mascote)
    const lista = f.classificacao;
    if (lista && lista.length) {
      const qy = y0 + h + 28 * U;
      const qw = W - 72 * U;
      const lh = 78 * U;
      const cab = 86 * U;
      const n = Math.min(5, lista.length);
      const qh = cab + 12 * U + n * (lh + 12 * U);
      const a = lim((t - 1.0) / 0.4, 0, 1);
      if (a > 0 && qy + qh < this.H - 10) {
        ctx.save();
        ctx.globalAlpha = a;
        this.desenharPainel(ctx, 36 * U, qy, qw, qh, "#0E2A5C", 40, 14, 7);
        this.texto(ctx, "CLASSIFICAÇÃO DE HOJE", W / 2, qy + cab / 2, 50 * U, CREME, 12 * U, MARINHO, true);
        for (let k = 0; k < n; k++) {
          const e = lista[k];
          const ly = qy + cab + 12 * U + k * (lh + 12 * U);
          const minha = e.agora;
          const al = lim((t - 1.2 - k * 0.12) / 0.25, 0, 1);
          ctx.save();
          ctx.globalAlpha = a * al;
          this.desenharPainel(ctx, 36 * U + 18 * U, ly, qw - 36 * U, lh, minha ? "#FFB627" : "#2A63C4", 26, 8, 4);
          const md = lh * 0.74;
          const corM = { 1: "#FFC21A", 2: "#DCE6F2", 3: "#F0A25A" }[k + 1] || AZUL;
          ctx.beginPath();
          ctx.arc(36 * U + 18 * U + 12 * U + md / 2, ly + lh / 2 - 3 * U, md / 2, 0, TAU);
          ctx.fillStyle = corM;
          ctx.fill();
          ctx.lineWidth = 4 * U;
          ctx.strokeStyle = MARINHO;
          ctx.stroke();
          this.texto(ctx, String(k + 1), 36 * U + 18 * U + 12 * U + md / 2, ly + lh / 2 - 3 * U, md * 0.55, k < 3 ? MARINHO : "#FFFFFF", k < 3 ? 0 : 6 * U, MARINHO, true, "center", false);
          const av2 = this.artes["retrato_" + e.personagem];
          const fd = lh * 0.92;
          if (av2) ctx.drawImage(av2, 36 * U + 18 * U + 24 * U + md, ly + (lh - fd) / 2 - 3 * U, fd, fd);
          const px = 36 * U + 18 * U + 24 * U + md + fd + 14 * U;
          if (minha) {
            this.texto(ctx, "VOCÊ!", px, ly + lh * 0.3, 34 * U, MARINHO, 0, MARINHO, true, "left", false);
            this.texto(ctx, `com ${e.personagem.toUpperCase()}  ·  ${e.hora}`, px, ly + lh * 0.68, 26 * U, MARINHO, 0, MARINHO, false, "left", false);
          } else {
            this.texto(ctx, `com ${e.personagem.toUpperCase()}  ·  ${e.hora}`, px, ly + lh / 2, 28 * U, "#FFFFFF", 7 * U, MARINHO, false, "left");
          }
          this.texto(ctx, String(e.pontos), 36 * U + qw - 30 * U, ly + lh / 2, lh * 0.55, minha ? MARINHO : CREME, minha ? 0 : 10 * U, MARINHO, true, "right", !minha);
          ctx.restore();
        }
        ctx.restore();
      }
    }
  }

  liberar() {
    this.cache.clear();
  }
}

/* ----------------------------------------------------------------------
   A PARTIDA (criada pelo console)
   ---------------------------------------------------------------------- */
async function carregarTudo(THREE, progresso) {
  const etapas = { total: 0, prontas: 0 };
  const passo = (p) => p.then((v) => {
    etapas.prontas++;
    progresso(etapas.prontas / etapas.total);
    return v;
  });
  const carregador = new THREE.TextureLoader();
  const texturas = {};
  const promessas = [];
  for (const [nome, arquivo] of Object.entries(TEXTURAS_3D)) {
    etapas.total++;
    promessas.push(passo(carregador.loadAsync(urlDe(arquivo)).then((t) => {
      t.flipY = false;
      t.colorSpace = THREE.NoColorSpace;
      if (nome === "pista" || nome.startsWith("chao") || nome === "madeira") {
        // só os pisos vistos de lado pedem filtro anisotrópico
        t.anisotropy = 4;
        t.wrapS = THREE.RepeatWrapping;
        t.wrapT = THREE.RepeatWrapping;
      }
      if (nome === "pista") t.wrapS = THREE.ClampToEdgeWrapping;
      if (nome.startsWith("bola")) t.wrapS = THREE.RepeatWrapping;
      texturas[nome] = t;
    })));
  }
  // as artes da escolha e do placar entram na espera; os letreiros (só
  // aparecem depois da 1ª jogada) baixam em segundo plano depois
  const artes = {};
  const depois = [];
  for (const [nome, arquivo] of Object.entries(ARTES_2D)) {
    if (!ARTES_JA.has(nome)) {
      depois.push([nome, arquivo]);
      continue;
    }
    etapas.total++;
    promessas.push(passo(baixarImagem(arquivo).then((img) => { artes[nome] = img; })));
  }
  etapas.total += 3;
  const [modelos] = await Promise.all([
    passo(carregarPacote(THREE, "modelos")),
    passo(baixarJson("tabela.json")).catch(() => null).then((t) => { artes._tabela = t; }),
    passo(carregarFontes()),
    ...promessas,
  ]);
  for (const [nome, arquivo] of depois) {
    baixarImagem(arquivo).then((img) => { artes[nome] = img; }).catch(() => {});
  }
  return { texturas, artes, modelos, tabela: artes._tabela };
}

export default {
  largura: LARGURA,
  altura: ALTURA,
  artes: {},
  criar(api) {
    return new Partida(api);
  },
};

/* ----------------------------------------------------------------------
   PONTUAÇÃO (scripts/placar.gd): cada pino = 10 pontos, STRIKE (os 10 na
   1ª bola) = +50, SPARE (completou os 10 depois) = +20.
   ---------------------------------------------------------------------- */
class Placar {
  comecar(personagens, rodadas, tentativas) {
    this.jogadores = personagens.map((p) => ({ personagem: p, rodadas: [], pontos: 0, strikes: 0, spares: 0, pinos: 0, seguidos: 0 }));
    this.rodadas = rodadas;
    this.tentativas = tentativas;
    this.jogadorAtual = 0;
    this.rodadaAtual = 0;
    this.bolaAtual = 0;
    this.pinosNaRodada = 0;
    for (const j of this.jogadores) for (let r = 0; r < rodadas; r++) j.rodadas.push([]);
  }

  atual() {
    return this.jogadores[this.jogadorAtual];
  }

  registrar(derrubados) {
    const j = this.atual();
    j.rodadas[this.rodadaAtual].push(derrubados);
    this.pinosNaRodada += derrubados;
    let tipo = "normal";
    let pontos = derrubados * PONTOS_PINO;
    if (derrubados === 0) tipo = "zero";
    if (this.pinosNaRodada >= 10) {
      if (this.bolaAtual === 0) {
        tipo = "strike";
        pontos += BONUS_STRIKE;
        j.strikes++;
      } else {
        tipo = "spare";
        pontos += BONUS_SPARE;
        j.spares++;
      }
    }
    j.pontos += pontos;
    j.pinos += derrubados;
    const fim = this.pinosNaRodada >= 10 || this.bolaAtual + 1 >= this.tentativas;
    if (tipo === "strike") j.seguidos++;
    else if (fim) j.seguidos = 0;
    return { tipo, pontos, fimRodada: fim };
  }

  avancar(fimRodada) {
    if (!fimRodada) {
      this.bolaAtual++;
      return "bola";
    }
    this.bolaAtual = 0;
    this.pinosNaRodada = 0;
    this.jogadorAtual++;
    if (this.jogadorAtual >= this.jogadores.length) {
      this.jogadorAtual = 0;
      this.rodadaAtual++;
    }
    if (this.rodadaAtual >= this.rodadas) {
      this.rodadaAtual = this.rodadas - 1;
      return "fim";
    }
    return "rodada";
  }

  maximo() {
    return this.rodadas * (10 * PONTOS_PINO + BONUS_STRIKE);
  }

  estrelas(i) {
    const f = this.jogadores[i].pontos / Math.max(this.maximo(), 1);
    if (f >= 0.62) return 3;
    if (f >= 0.38) return 2;
    return 1;
  }
}

/* ----------------------------------------------------------------------
   O PLANEJADOR DA JOGADA (scripts/jogada.gd): ele só escolhe a LINHA da
   bola; quem derruba os pinos é a física. A mira é sempre o STRIKE; o
   sensor diz por onde a bola passou (5 posições) e a dificuldade define o
   quanto ela erra o bolso. As linhas vêm da tabela de jogadas calibrada.
   ---------------------------------------------------------------------- */
const LINHA = { Z: -0.43, X: -0.21, C: 0.0, V: 0.21, B: 0.43 };
const TABELA_CHANCES = {
  facil: {
    C: { 10: 60, 9: 14, 8: 10, 7: 8, 6: 5, 5: 3 },
    X: { 10: 34, 9: 17, 8: 15, 7: 13, 6: 10, 5: 7, 4: 4 },
    Z: { 10: 14, 9: 12, 8: 14, 7: 15, 6: 14, 5: 12, 4: 10, 3: 6, 2: 3 },
  },
  normal: {
    C: { 10: 42, 9: 18, 8: 14, 7: 11, 6: 8, 5: 5, 4: 2 },
    X: { 10: 22, 9: 16, 8: 16, 7: 15, 6: 12, 5: 10, 4: 6, 3: 3 },
    Z: { 10: 7, 9: 9, 8: 12, 7: 14, 6: 15, 5: 14, 4: 12, 3: 9, 2: 6, 1: 2 },
  },
  dificil: {
    C: { 10: 28, 9: 18, 8: 16, 7: 14, 6: 10, 5: 8, 4: 6 },
    X: { 10: 12, 9: 13, 8: 15, 7: 16, 6: 15, 5: 12, 4: 9, 3: 8 },
    Z: { 10: 4, 9: 6, 8: 9, 7: 12, 6: 14, 5: 15, 4: 14, 3: 12, 2: 9, 1: 5 },
  },
};
const SPARE_CHANCES = { facil: [72, 45, 20], normal: [58, 32, 12], dificil: [42, 22, 7] };

function sortearPeso(tabela) {
  let total = 0;
  for (const k of Object.keys(tabela)) total += tabela[k];
  let r = Math.floor(Math.random() * Math.max(total, 1));
  for (const k of Object.keys(tabela)) {
    r -= tabela[k];
    if (r < 0) return Number(k);
  }
  return 0;
}

class Jogada {
  constructor(tabela) {
    this.grupos = {};
    // só para testes e para gravar vídeo: resultados desejados em sequência
    // (quantos pinos caem); vazio = sorteio normal (Jogada.forcar)
    this.forcar = [];
    if (!tabela) return;
    // cada linha olha também as vizinhas (2 cm para cada lado): só conta
    // como "linha de strike" a que derruba tudo mesmo errando um pouquinho
    for (const [zona, linhas] of Object.entries(tabela)) {
      const idx = new Map();
      const chave = (xt, v, e) => `${xt.toFixed(2)}|${v.toFixed(1)}|${e.toFixed(2)}`;
      for (const l of linhas) idx.set(chave(l[0], l[1], l[2]), l);
      this.grupos[zona] = linhas.map((l) => {
        const amostra = l[4].map((r) => r[0]);
        for (const dx of [-0.02, 0.02]) {
          const viz = idx.get(chave(Math.round((l[0] + dx) * 100) / 100, l[1], l[2]));
          if (viz) for (const r of viz[4]) amostra.push(r[0]);
        }
        return { xt: l[0], v: l[1], e: l[2], entrada: l[3], res: l[4], amostra };
      });
    }
  }

  planejar(zona, emPe, primeira, dificuldade, protecao) {
    const j = { zona, origemX: LINHA[zona] ?? 0, alvoX: 0, velocidade: 7.9, efeito: 0, esperado: -1, cair: null };
    const grupo = zona === "C" ? "C" : (zona === "X" || zona === "V" ? "X" : "Z");
    const dif = TABELA_CHANCES[dificuldade] ? dificuldade : "facil";
    let desejado = -1;
    if (this.forcar.length) desejado = lim(Math.round(this.forcar.shift()), 0, emPe.length);
    if (primeira && emPe.length === 10) {
      if (desejado < 0) desejado = sortearPeso(TABELA_CHANCES[dif][grupo]);
      if (this._daTabela(j, zona, desejado, protecao)) return j;
    }
    this._resto(j, emPe, dif, desejado, protecao);
    return j;
  }

  /** Pega na tabela uma linha da zona que costuma render `n` pinos. */
  _daTabela(j, zona, n, protecao) {
    const lista = this.grupos[zona];
    if (!lista || !lista.length) return false;
    let melhor = -1;
    let opcoes = [];
    for (const g of lista) {
      if (!protecao && (Math.abs(g.entrada) > 0.5 || Math.abs(g.xt) > 0.5)) continue;
      let nota = 0;
      for (const r of g.amostra) {
        const d = Math.abs(r - n);
        nota += d === 0 ? 1 : d === 1 ? 0.35 : 0;
      }
      nota /= g.amostra.length;
      if (nota > melhor + 0.001) {
        melhor = nota;
        opcoes = [g];
      } else if (Math.abs(nota - melhor) <= 0.001) {
        opcoes.push(g);
      }
    }
    if (!opcoes.length) return false;
    const g = sortear(opcoes);
    j.alvoX = g.xt;
    j.velocidade = g.v;
    j.efeito = g.e;
    j.esperado = n;
    // os pinos que caíram nessa linha na simulação (o mais perto de n)
    let res = g.res.filter((r) => r[0] === n);
    if (!res.length) res = g.res.slice().sort((a, b) => Math.abs(a[0] - n) - Math.abs(b[0] - n)).slice(0, 1);
    const mascara = sortear(res)[1];
    j.cair = [];
    for (let p = 1; p <= 10; p++) if (mascara & (1 << (p - 1))) j.cair.push(p);
    j.esperado = j.cair.length;
    return true;
  }

  /** Bolas seguintes: mira no pino da frente do que sobrou. */
  _resto(j, emPe, dif, desejado, protecao) {
    const linha = j.origemX;
    j.origemX = lim(linha, -0.45, 0.45);
    j.velocidade = aleat(8.0, 8.8);
    j.efeito = 0;
    if (!emPe.length) {
      j.alvoX = 0;
      return;
    }
    let cx = 0;
    let chave = emPe[0];
    let xmin = 9;
    let xmax = -9;
    for (const n of emPe) {
      const p = posicaoDoPino(n);
      cx += p[0];
      xmin = Math.min(xmin, p[0]);
      xmax = Math.max(xmax, p[0]);
      const pc = posicaoDoPino(chave);
      if (p[2] > pc[2] + 0.01 || (Math.abs(p[2] - pc[2]) < 0.01 && Math.abs(p[0]) < Math.abs(pc[0]))) chave = n;
    }
    cx /= emPe.length;
    const pk = posicaoDoPino(chave);
    const lado = sinal(cx - pk[0]);
    const mira = Math.abs(cx - pk[0]) > 0.03 ? pk[0] - lado * 0.07 : pk[0] + aleat(-0.03, 0.03);
    let dist = 0;
    if (linha < xmin) dist = xmin - linha;
    else if (linha > xmax) dist = linha - xmax;
    const chances = SPARE_CHANCES[dif];
    const chance = dist < 0.12 ? chances[0] : (dist < 0.32 ? chances[1] : chances[2]);
    let acertou = Math.random() * 100 < chance;
    if (desejado >= 0) acertou = desejado >= emPe.length;
    if (acertou) {
      j.alvoX = mira + aleat(-0.015, 0.015);
      j.esperado = emPe.length;
      j.cair = emPe.slice();
    } else {
      const fora = mira !== 0 ? sinal(mira) : (Math.random() < 0.5 ? 1 : -1);
      j.alvoX = mira + fora * (desejado === 0 ? 0.45 : aleat(0.1, 0.32));
      j.esperado = -1;
    }
    j.alvoX = lim(j.alvoX, protecao ? -0.58 : -0.62, protecao ? 0.58 : 0.62);
  }
}

/* ----------------------------------------------------------------------
   A PARTIDA (principal.gd): ESCOLHA DO AMIGO -> a vez (cenário novo com
   passeio de câmera, faixa "VEZ DO BOB!") -> PRONTO (a pista de frente,
   "ROLE A BOLA!") -> ARREMESSO (o bichinho corre e solta a bola na linha
   do sensor) -> ROLANDO (a câmera segue a bola e vai para os pinos) ->
   RESULTADO (letreiro, REPLAY do strike, reação do bichinho, máquina de
   pinos) -> ... -> FIM DE JOGO.
   ---------------------------------------------------------------------- */
const MESMA_BOLA = 1.2;
// a mesma chave do recorde do console (PREFIXO_RECORDE + slug do jogo)
const CHAVE_RECORDE = "ls-jogo-recorde:strike-kids";
// arrasto lento para cima maior que isto (px) também rola a bola
const ARRASTO_COMPRIDO = 140;
// resolução do 3D: até 1,5 pixel por ponto; cai de 0,25 em 0,25 (até
// PR_MINIMO) quando a média do quadro passa de QUADRO_LENTO segundos
const PR_MAXIMO = 1.5;
const PR_MINIMO = 0.8;
const QUADRO_LENTO = 1 / 40;
// o gesto é medido no relógio do navegador (os eventos chegam entre quadros)
const relogioDoGesto = () => (typeof performance !== "undefined" ? performance.now() : Date.now()) / 1000;
// jogada que chega com a pista ocupada fica guardada por este tempo (s)
const VALIDADE_PENDENTE = 10;
// a roupinha da fase pode chegar depois: o jogo espera no máximo isto (s)
const ESPERA_ROUPA = 3;
const REPLAY_VEL = 0.45;
const REPLAY_VEL_BATIDA = 0.27;
const REPLAY_ANTES = 0.8;
const REPLAY_DEPOIS = 1.6;
const QUADRO_GRAVACAO = 77;           // bola (7) + 10 pinos (7) por passo gravado
const MAX_GRAVACAO = 1400;

class Partida {
  constructor(api) {
    this.api = api;
    this.pronto = false;
    this.erro = null;
    this.progresso = 0;
    this.estado = "carregando";
    this.seq = 0;
    this.pular = false;
    this.relogio = new Relogio();
    this.placar = new Placar();
    this.ritmo = 1;
    this.lenta = null;
    this.acumulador = 0;
    this.comecarNoProximo = false;
    this.arrasto = null;
    this.ultimaJogada = -10;
    this.pendente = "";
    this.pendenteT = 0;
    this.tempoReal = 0;
    this.medicao = { soma: 0, n: 0 };
    this._extraHud = { pes: null };
    this.destruido = false;
    this.temasPartida = [];
    this.roupas = {};
    this.pedidosRoupa = {};
    this.ultimoSomPino = 0;
    this._carregar();
  }

  // ---------------------------------------------------------------- montagem
  async _carregar() {
    try {
      const THREE = await import(URL_THREE);
      if (this.destruido) return;
      this.T = THREE;
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2", { antialias: true, alpha: false, powerPreference: "high-performance", preserveDrawingBuffer: false });
      if (!gl) throw new Error("sem-webgl");
      this.renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: true });
      this.pr = Math.min(PR_MAXIMO, window.devicePixelRatio || 1);
      this.renderer.setPixelRatio(this.pr);
      this.renderer.setSize(LARGURA, ALTURA, false);
      this.renderer.autoClear = true;
      this.canvas3d = canvas;
      canvas.addEventListener("webglcontextlost", (e) => {
        e.preventDefault();
        this.erro = new Error("contexto");
      });
      const r = await carregarTudo(THREE, (p) => { this.progresso = p; });
      if (this.destruido) return;
      this.res = r;
      this.tex = r.texturas;
      this.artes = r.artes;
      this.mats = new Materiais(THREE, r.texturas);
      this.cena = new THREE.Scene();
      this.cena.matrixWorldAutoUpdate = true;
      this.mundo = new Mundo(THREE, this.mats, r.texturas);
      this.cena.add(this.mundo.raiz);
      this.particulas = new Particulas(THREE, r.texturas);
      this.cena.add(this.particulas.raiz);
      this.cenarios = new Cenarios(THREE, this.mats, this.mundo, this.particulas);
      this.fisica = new Fisica(THREE);
      this.pinos = new Pinos(THREE, this.mats, r.texturas, r.modelos, this.particulas, this.mundo.raiz);
      this.pinos.aoBater = (c, v) => this._batidaPino(v);
      this.bola = new Bola(THREE, this.mats, r.texturas, this.particulas, this.mundo.raiz);
      this.corpoBola = { p: this.bola.pos, v: this.bola.vel, w: new THREE.Vector3(), q: new THREE.Quaternion(), dinamico: false,
        invM: 1 / MASSA_BOLA, ehBola: true, curva: 0, removido: false, preso: false };
      this.maquina = new Maquina(THREE, this.mats, this.pinos, this.fisica, this.relogio, this.mundo.raiz);
      this.maquina.aoSom = (n) => { if (n === "pousar") this.api.som("quica"); };
      this.personagens = {};
      for (const nome of ["bob", "mia"]) {
        const p = new Personagem(THREE, this.mats, r.texturas, nome, r.modelos, this.particulas, this.mundo.raiz);
        p.pacoteBase = r.modelos;
        p.aoSoltar = (pos) => this._soltouBola(pos);
        p.aoSom = (s) => this._somPersonagem(s);
        this.personagens[nome] = p;
      }
      this.cam = new CameraCine(THREE);
      this.cam.reduzido = !!this.api.reduzido;
      this.hud = new Hud(this.api, r.artes);
      this.jogada = new Jogada(r.tabela);
      this.alvoReplay = new THREE.Vector3();
      this.gravacao = new Float32Array(MAX_GRAVACAO * QUADRO_GRAVACAO);
      this.gravTempos = new Float32Array(MAX_GRAVACAO);
      this.nGrav = 0;
      this._gravarPasso = 0;
      this._vt = new THREE.Vector3();
      this._qt = new THREE.Quaternion();
      this._eixoGiro = new THREE.Vector3();
      this._corFundo = new THREE.Color();
      // a primeira fase (Selva dos Dinos é sempre a primeira da atração)
      await this.cenarios.pedir("dinos");
      if (this.destruido) return;
      this.mundo.aplicarTema("dinos");
      this.cenarios.mostrar("dinos");
      this._atracao();
      // prepara os shaders antes da partida (nada de tranco na 1ª jogada),
      // e os de cada cenário quando ele chega
      this._compilar(this.cena);
      this.cenarios.aoMontar = (grupo) => { if (!this.destruido) this._compilar(grupo); };
      this.pronto = true;
      if (this.comecarNoProximo === "ja") this._escolherPersonagem();
    } catch (e) {
      console.warn("Strike Kids: o 3D não abriu", e);
      this.erro = e;
    }
  }

  /** Compila os shaders de tudo o que está debaixo de `raiz`, inclusive o
   *  que ainda está escondido (bola, rastro, faíscas, cenário novo): no
   *  celular, compilar no meio da jogada dá um tranco visível. */
  _compilar(raiz) {
    // (o compile do three passa também pelos escondidos)
    try {
      this.renderer.compile(raiz, this.cam.camera, this.cena);
    } catch (erro) { /* compila na hora de desenhar */ }
  }

  // ---------------------------------------------------------------- contrato do console
  iniciar() {
    // o console chama ao abrir (capa) e ao apertar JOGAR: a partida começa
    // no primeiro quadro andando (depois da contagem 3-2-1)
    this.comecarNoProximo = true;
    if (this.pronto) {
      this.novoSeq();
      this.relogio.limpar();
      this._atracao();
    }
  }

  atualizar(dtReal) {
    if (this.destruido) return;
    if (!this.pronto) {
      if (this.comecarNoProximo === true) this.comecarNoProximo = "ja";
      return;
    }
    if (this.comecarNoProximo) {
      this.comecarNoProximo = false;
      this._escolherPersonagem();
    }
    this.tempoReal += dtReal;
    this._medirQuadros(dtReal);
    this._passoLenta(dtReal);
    const dt = dtReal * VELOCIDADE * this.ritmo;
    this.relogio.atualizar(dt);
    this.maquina.atualizar();
    // a física (passo fixo de 1/240 s do tempo de jogo)
    if (this.estado !== "replay") {
      this.acumulador += dt;
      let n = 0;
      while (this.acumulador >= PASSO_FISICA && n < 24) {
        this.acumulador -= PASSO_FISICA;
        this._passoFisica(PASSO_FISICA);
        n++;
      }
      if (n >= 24) this.acumulador = 0;
    }
    if (this.estado === "rolando") this._rolando();
    if (this.estado === "replay") this._rodarReplay(dt);
    if (this.estado === "escolha") this._escolhaTempo(dtReal);
    if (this.estado === "fim") this._fimTempo(dtReal);
    for (const nome of ["bob", "mia"]) {
      const p = this.personagens[nome];
      if (p.olharAlvo && this.bola.visivel) p.olharAlvo = this.bola.pos;
      if (p.visivel) p.atualizar(dt);
    }
    this.pinos.atualizarVisual(dt);
    this.bola.atualizarVisual(dt, this.estado === "rolando");
    this.mundo.bolaPos = this.bola.visivel ? this.bola.pos : null;
    this.mundo.atualizar(dt);
    this.cenarios.atualizar(dt);
    this.cam.atualizar(dt);
    this.particulas.atualizar(dt, ALTURA * this.pr, this.cam.camera.fov);
    this.hud.atualizar(dt);
    if (this.hud.selecao) this.hud.selecao.t += dt;
  }

  /** RESOLUÇÃO QUE SE AJUSTA: se o aparelho não segura ~40 quadros por
   *  segundo (média de 1,5 s de jogo), o 3D perde um degrau de pixels —
   *  o jogo fica igual, só um pouco menos nítido. */
  _medirQuadros(dtReal) {
    const m = this.medicao;
    m.soma += dtReal;
    m.n += 1;
    if (m.n < 90) return;
    const media = m.soma / m.n;
    m.soma = 0;
    m.n = 0;
    if (media > QUADRO_LENTO && this.pr > PR_MINIMO) {
      this.pr = Math.max(PR_MINIMO, this.pr - 0.25);
      this.renderer.setPixelRatio(this.pr);
      this.renderer.setSize(LARGURA, ALTURA, false);
    }
  }

  desenhar(ctx) {
    if (this.destruido) return;
    if (this.erro) {
      this._desenharErro(ctx);
      return;
    }
    if (!this.pronto) {
      this._desenharCarregando(ctx);
      return;
    }
    // o 3D é desenhado no canvas próprio e copiado para a tela do console
    // no mesmo quadro (sem preserveDrawingBuffer: a cópia tem de ser já).
    // Atrás da capa e da tela de fim o console só pede 1 quadro em 4.
    const cor = this.mundo.corFundo;
    this._corFundo.setRGB(cor[0], cor[1], cor[2]);
    this.renderer.setClearColor(this._corFundo, 1);
    this.renderer.render(this.cena, this.cam.camera);
    ctx.drawImage(this.canvas3d, 0, 0, LARGURA, ALTURA);
    this._extraHud.pes = this.estado === "escolha" ? this._pesNaTela() : null;
    this.hud.desenhar(ctx, this._extraHud);
  }

  _desenharCarregando(ctx) {
    const g = ctx.createLinearGradient(0, 0, 0, ALTURA);
    g.addColorStop(0, "#1b5fc4");
    g.addColorStop(1, "#0b1f45");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, LARGURA, ALTURA);
    this.api.texto(ctx, "STRIKE KIDS", LARGURA / 2, ALTURA * 0.42, { tamanho: 54, cor: "#FFD43B", contorno: "#0B1F45", peso: 900 });
    this.api.texto(ctx, "Carregando o boliche do Bob e da Mia…", LARGURA / 2, ALTURA * 0.5, { tamanho: 20, cor: "#fff", peso: 700 });
    const w = 300;
    ctx.fillStyle = "rgba(255,255,255,0.18)";
    caminhoArredondado(ctx, (LARGURA - w) / 2, ALTURA * 0.56, w, 16, 8);
    ctx.fill();
    ctx.fillStyle = "#FFC21A";
    caminhoArredondado(ctx, (LARGURA - w) / 2, ALTURA * 0.56, Math.max(16, w * this.progresso), 16, 8);
    ctx.fill();
  }

  _desenharErro(ctx) {
    ctx.fillStyle = "#0b1f45";
    ctx.fillRect(0, 0, LARGURA, ALTURA);
    const semGl = this.erro && this.erro.message === "sem-webgl";
    this.api.texto(ctx, "STRIKE KIDS", LARGURA / 2, ALTURA * 0.4, { tamanho: 50, cor: "#FFD43B", contorno: "#0B1F45", peso: 900 });
    const linhas = semGl
      ? ["Este aparelho não abriu o 3D", "(o navegador está sem WebGL 2).", "Tente em outro navegador ou aparelho."]
      : ["Não foi possível abrir o jogo agora.", "Recarregue a página e tente de novo."];
    linhas.forEach((l, i) => this.api.texto(ctx, l, LARGURA / 2, ALTURA * 0.5 + i * 32, { tamanho: 20, cor: "#fff", peso: 700 }));
  }

  destruir() {
    this.destruido = true;
    this.relogio.limpar();
    if (!this.pronto) {
      if (this.renderer) {
        this.renderer.dispose();
        this.renderer.forceContextLoss();
      }
      return;
    }
    this.mundo.liberar();
    this.cenarios.liberar();
    this.particulas.liberar();
    this.pinos.liberar();
    this.bola.liberar();
    this.maquina.liberar();
    for (const p of Object.values(this.personagens)) p.liberar();
    for (const pac of [this.res.modelos, ...Object.values(this.roupas)]) {
      if (pac) for (const g of Object.values(pac.malhas)) g.dispose();
    }
    this.mats.liberar();
    for (const t of Object.values(this.tex)) t.dispose();
    this.hud.liberar();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }

  // ---------------------------------------------------------------- entrada
  apertar(x, y, id) {
    if (!this.pronto) return;
    const agora = relogioDoGesto();
    this.arrasto = { id, x0: x, y0: y, x, y, t0: agora, pontos: [[x, y, agora]] };
    if (this.estado === "pronto" && this.hud.bolaArrasto) {
      this.hud.bolaArrasto.segurando = true;
    }
  }

  mover(x, y, id) {
    const a = this.arrasto;
    if (!a || a.id !== id) return;
    a.x = x;
    a.y = y;
    a.pontos.push([x, y, relogioDoGesto()]);
    if (a.pontos.length > 12) a.pontos.shift();
    const b = this.hud.bolaArrasto;
    if (b && b.segurando) {
      b.x = lim(x, 40, LARGURA - 40);
      b.y = lim(y, ALTURA * 0.45, ALTURA - 30);
      b.giro += (x - (b.ux ?? x)) * 0.02;
      b.ux = x;
    }
  }

  soltar(x, y, id) {
    const a = this.arrasto;
    if (!a || a.id !== id) return;
    this.arrasto = null;
    const agora = relogioDoGesto();
    a.pontos.push([x, y, agora]);
    const dist = Math.hypot(x - a.x0, y - a.y0);
    const dur = agora - a.t0;
    // velocidade do gesto: do ponto de ~0,1 s antes até a soltura (o
    // pointerup costuma repetir a posição do último movimento)
    let k = a.pontos.length - 1;
    while (k > 0 && agora - a.pontos[k][2] < 0.1) k--;
    const p0 = a.pontos[k];
    const dtg = Math.max(agora - p0[2], 1 / 60);
    let vx = (x - p0[0]) / dtg;
    let vy = (y - p0[1]) / dtg;
    const b = this.hud.bolaArrasto;
    if (b) b.segurando = false;
    let zona = null;
    // empurrão devagar mas comprido para cima também rola (criança pequena):
    // vale a direção do arrasto inteiro
    const empurrou = !(vy < -220) && y - a.y0 < -ARRASTO_COMPRIDO && dur > 0;
    if (empurrou) {
      vx = (x - a.x0) / dur;
      vy = (y - a.y0) / dur;
    }
    if (dist > 28 && (vy < -220 || empurrou)) {
      // rolou: onde a bola cruza a linha dos sensores (a linha de falta na
      // tela), seguindo a direção do gesto na hora de soltar — para a frente
      // se ainda não chegou nela, para trás se já passou
      const yLinha = ALTURA * 0.8;
      const cruza = x + vx / -vy * (y - yLinha);
      const s = (cruza - LARGURA / 2) / (LARGURA * 0.42);
      zona = s < -0.6 ? "Z" : s < -0.2 ? "X" : s <= 0.2 ? "C" : s <= 0.6 ? "V" : "B";
      if (b && this.estado === "pronto") {
        b.voando = { vx: vx * 0.6, vy: Math.min(vy * 0.6, -600) };
      }
    } else if (dist < 14 && dur < 0.4) {
      // toque: as 5 faixas da tela valem como os 5 sensores (como na máquina)
      zona = ["Z", "X", "C", "V", "B"][lim(Math.floor(x / LARGURA * 5), 0, 4)];
      if (this.estado === "escolha") {
        // na escolha, tocar no bichinho escolhe ele
        const pes = this._pesNaTela();
        const i = Math.abs(x - pes[0][0]) < Math.abs(x - pes[1][0]) ? 0 : 1;
        this._marcarDestaque(i);
        this._confirmarPersonagem();
        return;
      }
    }
    if (zona) this._jogadaRecebida(zona);
  }

  tecla(codigo, apertada) {
    if (!apertada || !this.pronto) return;
    const mapa = { KeyZ: "Z", KeyX: "X", KeyC: "C", KeyV: "V", KeyB: "B", KeyA: "Z", KeyS: "X", KeyD: "C", KeyF: "V", KeyG: "B" };
    if (mapa[codigo]) {
      this._jogadaRecebida(mapa[codigo]);
    } else if (codigo === "Space" || codigo === "Enter" || codigo === "Digit1") {
      this._start();
    } else if (codigo === "ArrowLeft") {
      if (this.estado === "escolha") this._marcarDestaque(0);
    } else if (codigo === "ArrowRight") {
      if (this.estado === "escolha") this._marcarDestaque(1);
    }
  }

  _start() {
    if (this.estado === "escolha") this._confirmarPersonagem();
    else if (this.estado === "pronto") this._jogadaRecebida("C");
    else this.pular = true;
  }

  _jogadaRecebida(zona) {
    if (this.estado === "pronto") {
      this._arremessar(zona);
    } else if (this.estado === "escolha") {
      if (zona === "Z" || zona === "X") this._marcarDestaque(0);
      else if (zona === "V" || zona === "B") this._marcarDestaque(1);
      else this._confirmarPersonagem();
    } else if (["arremesso", "rolando", "resultado", "replay"].includes(this.estado)) {
      // a jogada no meio da animação encurta a espera e fica guardada para
      // quando a pista estiver pronta (como o sensor da máquina)
      if (this.tempoReal - this.ultimaJogada < MESMA_BOLA) return;
      this.pendente = zona;
      this.pendenteT = this.tempoReal;
      this.pular = true;
    }
  }

  // ---------------------------------------------------------------- sequências
  novoSeq() {
    this.seq++;
    this.pular = false;
    return this.seq;
  }

  /** Espera t segundos de jogo; um toque encurta (pulavel). */
  async esperar(t, s, pulavel = true) {
    let passou = 0;
    while (passou < t) {
      const ok = await this.relogio.esperar(Math.min(0.05, t - passou), () => s !== this.seq);
      if (!ok || s !== this.seq) return false;
      passou += 0.05;
      if (pulavel && this.pular) {
        this.pular = false;
        break;
      }
    }
    return s === this.seq;
  }

  _somPersonagem(nome) {
    if (nome === "palma") this.api.som("clique");
    else if (nome === "jato") this.api.som("combo");
  }

  _batidaPino(v) {
    if (v < 0.35 || this.estado === "replay") return;
    if (this.tempoReal - this.ultimoSomPino < 0.09) return;
    this.ultimoSomPino = this.tempoReal;
    this.api.som("batida");
  }

  // ---------------------------------------------------------------- atração (a capa do console)
  _atracao() {
    this.estado = "atracao";
    this.hud.fim = null;
    this.hud.selecao = null;
    this.hud.mostrarPlacar(false);
    this.hud.conviteLigado(false);
    this.hud.bolaArrasto = null;
    this.hud.itens = [];
    this.hud.replayAlvo = 0;
    this.hud.replay = 0;
    this.bola.guardar();
    this.corpoBola.dinamico = false;
    this.maquina.instantaneo();
    this.mundo.mostrarPodios(false);
    this._vestirTodos(null, "");
    const t = this.personagens.bob;
    const r = this.personagens.mia;
    t.visivel = true;
    r.visivel = true;
    t.posicionar([-0.6, 0, 1.6], 0);
    r.posicionar([0.6, 0, 1.6], 0);
    for (const p of [t, r]) {
      p.segurarBola(false);
      p.jatos(false);
      p.olharAlvo = null;
      p.destaque(0);
      p.expressao("feliz");
    }
    t.tocar("acenar", 0.01, true);
    r.tocar("parado", 0.01, true);
    // um quadro bem posto: os dois na frente da pista, como a tela inicial
    for (let i = 0; i < 40; i++) {
      t.atualizar(1 / 30);
      r.atualizar(1 / 30);
    }
    this.pinos.atualizarVisual(0);
    this.cam.corte([1.0, 1.55, 5.9], [0, 0.95, 1.6], 40, 46);
    this.mundo.atualizar(0.016);
  }

  // ---------------------------------------------------------------- escolha do amigo
  _escolherPersonagem() {
    this.estado = "escolha";
    this.novoSeq();
    this.hud.fim = null;
    this.escolhaT = TEMPO_ESCOLHA;
    this.destaqueSel = -1;
    this.hud.selecao = { t: 0, destaque: 0, escalas: [0.9, 0.9], resta: TEMPO_ESCOLHA };
    const t = this.personagens.bob;
    const r = this.personagens.mia;
    this.mundo.mostrarPodios(true, -1);
    t.posicionar([PODIOS[0][0], ALTURA_PODIO, PODIOS[0][2]], 0);
    r.posicionar([PODIOS[1][0], ALTURA_PODIO, PODIOS[1][2]], 0);
    t.ocioso(false);
    r.ocioso(false);
    t.tocar("acenar", 0.3, true);
    r.tocar("parado", 0.3, true);
    this.cam.ir([0, 1.05, 6.1], [0, 0.78, 2.5], 32, 52, 3.0);
    this._marcarDestaque(0);
    this.api.som("whoosh");
    // as fases já são sorteadas aqui: a roupinha da 1ª rodada vai baixando
    // enquanto a criança escolhe
    this._sortearTemas(RODADAS);
    this.cenarios.pedir(this.temasPartida[0]);
    this._pedirRoupa(this.temasPartida[0]);
  }

  _marcarDestaque(i) {
    if (this.estado !== "escolha") return;
    if (i !== this.destaqueSel) this.api.som("clique");
    this.destaqueSel = i;
    this.hud.selecao.destaque = i;
    const t = this.personagens.bob;
    const r = this.personagens.mia;
    t.tocar(i === 0 ? "acenar" : "parado", 0.25);
    r.tocar(i === 1 ? "acenar" : "parado", 0.25);
    t.destaque(i === 0 ? 0.12 : 0);
    r.destaque(i === 1 ? 0.12 : 0);
    this.mundo.mostrarPodios(true, i);
    this.escolhaT = Math.max(this.escolhaT, 3.0);
  }

  _escolhaTempo(dtReal) {
    this.escolhaT -= dtReal;
    this.hud.selecao.resta = this.escolhaT;
    if (this.escolhaT <= 0) this._confirmarPersonagem();
  }

  /** Frente de cada pódio na tela (as placas com os nomes ficam embaixo). */
  _pesNaTela() {
    const cam = this.cam.camera;
    cam.updateMatrixWorld();
    return PODIOS.map((p) => {
      const v = this._vt.set(p[0], p[1], p[2] + 0.45).project(cam);
      return [(v.x + 1) / 2 * LARGURA, (1 - v.y) / 2 * ALTURA];
    });
  }

  async _confirmarPersonagem() {
    if (this.estado !== "escolha") return;
    this.estado = "resultado";
    const s = this.novoSeq();
    const escolhido = this.destaqueSel === 1 ? "mia" : "bob";
    const outro = escolhido === "bob" ? "mia" : "bob";
    this.hud.selecao = null;
    this.api.som("moeda");
    this.personagens[escolhido].tocar("escolhido", 0.15, true);
    this.personagens[outro].tocar("feliz", 0.2, true);
    this.hud.flash("#FFFFFF", 0.4);
    const pe = this.personagens[escolhido].raiz.position;
    this.particulas.estrelas([pe.x, pe.y + 1.2, pe.z], 26);
    if (!(await this.esperar(1.5, s))) return;
    this.personagens.bob.destaque(0);
    this.personagens.mia.destaque(0);
    this._comecar(escolhido);
  }

  // ---------------------------------------------------------------- partida
  _comecar(escolhido) {
    this.placar.comecar([escolhido], RODADAS, TENTATIVAS);
    if (!this.temasPartida || !this.temasPartida.length) this._sortearTemas(RODADAS);
    this._pedirRoupa(this.temasPartida[0]);
    this.hud.configurarPlacar(escolhido);
    this.hud.atualizarPlacar(this.placar);
    this.hud.sequencia(0);
    this.api.placar({ pontos: 0, info: `Rodada 1 de ${RODADAS}` });
    this.mundo.mostrarPodios(false);
    this._vez(true);
  }

  /** FASES SORTEADAS: todas aparecem antes de alguma se repetir, e nunca
   *  a mesma duas rodadas seguidas. */
  _sortearTemas(n) {
    this.temasPartida = [];
    let antes = this.mundo.tema;
    const usados = new Set();
    for (let i = 0; i < Math.max(n, 1); i++) {
      let opcoes = ORDEM_TEMAS.filter((t) => t !== antes && !usados.has(t));
      if (!opcoes.length) {
        usados.clear();
        opcoes = ORDEM_TEMAS.filter((t) => t !== antes);
      }
      const t = sortear(opcoes);
      this.temasPartida.push(t);
      usados.add(t);
      antes = t;
    }
  }

  _temaDaRodada() {
    return this.temasPartida[lim(this.placar.rodadaAtual, 0, this.temasPartida.length - 1)] || this.mundo.tema;
  }

  /** A roupinha de uma fase começa a baixar (em segundo plano). */
  _pedirRoupa(tema) {
    if (!tema || this.pedidosRoupa[tema]) return this.pedidosRoupa[tema];
    this.pedidosRoupa[tema] = carregarPacote(this.T, "roupa_" + tema)
      .then((pac) => {
        this.roupas[tema] = pac;
        return pac;
      })
      .catch(() => null);
    return this.pedidosRoupa[tema];
  }

  _vestirTodos(pacote, nomeRoupa) {
    for (const p of Object.values(this.personagens)) p.vestir(pacote, nomeRoupa);
  }

  /** Começo da vez do jogador (ou da próxima bola dele). */
  async _vez(novaRodada) {
    this.estado = "resultado";
    const s = this.novoSeq();
    const ativo = this.placar.atual().personagem;
    const plateia = ativo === "bob" ? "mia" : "bob";
    this.ativo = ativo;
    this.plateia = plateia;
    const a = this.personagens[ativo];
    const p = this.personagens[plateia];
    a.visivel = true;
    p.visivel = true;
    a.jatos(false);
    p.jatos(false);
    a.destaque(0);
    p.destaque(0);
    a.ocioso(false);
    p.ocioso(false);
    a.posicionar([-X_MAO, 0, Z_INICIO], 180);
    a.segurarBola(true);
    a.tocar("pronto", 0.15, true);
    a.expressao("feliz");
    a.olharAlvo = null;
    const lado = ativo === "bob" ? 1 : -1;
    p.posicionar([lado * 1.85, 0, 1.0], 180 - lado * 38);
    p.tocar("torcida", 0.2, true);
    p.olharAlvo = null;
    this.hud.mostrarPlacar(true);
    this.hud.atualizarPlacar(this.placar);
    this.hud.mostrarMapa(this.pinos.emPe());
    const seguidos = this.placar.atual().seguidos;
    this.hud.sequencia(seguidos);
    this.bola.fogo(seguidos >= 2);
    const comeco = this.placar.rodadaAtual === 0 && this.placar.jogadorAtual === 0;
    if (novaRodada && (this._temaDaRodada() !== this.mundo.tema || comeco)) {
      // cenário novo: clarão, troca e um passeio de câmera pelo lugar
      const tema = this._temaDaRodada();
      // o cenário é necessário; a roupinha, se demorar, entra quando chegar
      const roupa = this._pedirRoupa(tema);
      await Promise.all([this.cenarios.pedir(tema), Promise.race([roupa, this.relogio.esperar(ESPERA_ROUPA, () => s !== this.seq)])]);
      if (s !== this.seq) return;
      if (!this.roupas[tema] && roupa) {
        roupa.then((pac) => {
          if (pac && this.mundo.tema === tema) this._vestirTodos(pac, ROUPA_DO_TEMA[tema]);
        });
      }
      this.hud.flash("#FFFFFF", 0.95, 0.6);
      this.mundo.aplicarTema(tema);
      this.cenarios.mostrar(tema);
      this._vestirTodos(this.roupas[tema] || null, this.roupas[tema] ? ROUPA_DO_TEMA[tema] : "");
      if (this.placar.rodadaAtual + 1 < this.temasPartida.length) {
        const prox = this.temasPartida[this.placar.rodadaAtual + 1];
        this.cenarios.pedir(prox);
        this._pedirRoupa(prox);
      }
      this.api.som("combo");
      this.api.som("whoosh");
      this.hud.anunciarCenario(tema, 1.7);
      // passeio que termina na PISTA DE FRENTE (a vista da espera)
      this.cam.trilho([
        [[-2.6, 4.6, Z_PINO1 + 1.0], [0, 2.2, Z_FUNDO - 3.0], 0.0],
        [[2.2, 3.4, -5.0], [0, 1.4, Z_FUNDO], 1.4],
        [POS_PISTA, ALVO_PISTA, 1.3],
      ], 34, 40);
      if (!(await this.esperar(2.9, s, false))) return;
    } else if (novaRodada) {
      this.cam.ir(POS_PISTA, ALVO_PISTA, 34, 40, 2.6);
    }
    if (novaRodada) {
      const artigo = ativo === "bob" ? "DO" : "DA";
      this.hud.faixa(ativo, `VEZ ${artigo} ${ativo.toUpperCase()}!`, `RODADA ${this.placar.rodadaAtual + 1}`);
      this.api.som("nota");
      if (!(await this.esperar(1.6, s, false))) return;
    }
    this._pronto();
  }

  /** Esperando a jogada: a PISTA DE FRENTE, como a criança vê da máquina. */
  _pronto() {
    this.estado = "pronto";
    this.novoSeq();
    this.cam.ir(POS_PISTA, ALVO_PISTA, 34, 40, 2.6);
    this.hud.conviteLigado(true);
    this.hud.bolaArrasto = { personagem: this.ativo, x: LARGURA / 2, y: ALTURA - 52, raio: 34, giro: 0, alfa: 1, segurando: false };
    this.personagens[this.ativo].expressao("concentrado");
    // jogada que chegou enquanto a pista não estava pronta
    if (this.pendente && this.tempoReal - this.pendenteT < VALIDADE_PENDENTE) {
      const z = this.pendente;
      const s = this.seq;
      this.relogio.esperar(0.35, () => s !== this.seq).then((ok) => {
        if (ok && s === this.seq && this.estado === "pronto") this._arremessar(z);
      });
    }
    this.pendente = "";
  }

  _arremessar(zona) {
    if (this.estado !== "pronto") return;
    if (this.tempoReal - this.ultimaJogada < MESMA_BOLA) return;
    this.ultimaJogada = this.tempoReal;
    this.novoSeq();
    this.estado = "arremesso";
    this.hud.conviteLigado(false);
    // a bola de arrastar que foi rolada termina o voo dela; a do toque some
    if (!(this.hud.bolaArrasto && this.hud.bolaArrasto.voando)) this.hud.bolaArrasto = null;
    this.emPeAntes = this.pinos.emPe();
    const primeira = this.placar.bolaAtual === 0;
    this.plano = this.jogada.planejar(zona, this.emPeAntes, primeira && this.emPeAntes.length === 10, DIFICULDADE, true);
    // os pinos que devem cair ganham o empurrão da física; os que ficam,
    // a mola que os mantém de pé quando só balançam
    const cair = this.plano.cair ? new Set(this.plano.cair) : null;
    for (const c of this.pinos.corpos) c.ajuda = !!(cair && !cair.has(c.numero) && !c.removido);
    const a = this.personagens[this.ativo];
    // passo para o lado: a bola sai na linha do sensor
    const xCorpo = lim(this.plano.origemX - X_MAO, -0.85, 0.55);
    this.relogio.tween(a.base, "x", xCorpo, 0.45, FACIL.seno);
    a.tocar("arremesso", 0.12, true);
    // corte seco da pista para o bichinho arremessando
    const ap = a.raiz.position;
    this.cam.corte([ap.x + 1.15, 2.05, ap.z + 3.3], [ap.x - 0.35, 0.05, ap.z - 7.0], 50, 40);
    this.cam.seguir(() => a.raiz.position, [1.15, 2.05, 3.3], [-0.35, 0.05, -7.0], 50, 40, 3.0);
    this.api.som("whoosh");
  }

  _soltouBola(pos) {
    if (this.estado !== "arremesso") return;
    const a = this.personagens[this.ativo];
    const j = this.plano;
    this.bola.vestir(this.ativo);
    // a bola segue a linha planejada: passa por origemX na linha de falta
    // (z = 0,35) e vai até alvoX nos pinos
    const z0 = Math.min(pos.z, 0.45);
    const u = (0.35 - z0) / (0.35 - Z_PINO1);
    const origem = this._vt.set(mistura(j.origemX, j.alvoX, u), RAIO_BOLA + 0.04, z0);
    const dx = j.alvoX - origem.x;
    const dz = Z_PINO1 - z0;
    const l = Math.hypot(dx, dz);
    const vel = new this.T.Vector3(dx / l * j.velocidade, 0, dz / l * j.velocidade);
    this.bola.lancar(origem, vel, j.efeito);
    this.corpoBola.dinamico = true;
    this.corpoBola.curva = j.efeito;
    this.estado = "rolando";
    this.tJogada = 0;
    this.tImpacto = -1;
    this.deckCam = false;
    this.camBaixa = false;
    this.nGrav = 0;
    this._gravarPasso = 0;
    this.gravando = true;
    this.forcados = new Set();
    this.mundo.acenderPista(true);
    a.olharAlvo = this.bola.pos;
    this.cam.seguir(() => this.bola.pos, [0.5, 2.1, 3.6], [0, 0.0, -5.0], 50, 40, 3.0);
    const s = this.seq;
    this.relogio.esperar(0.02).then(() => {
      if (s !== this.seq) return;
      a.tocar("assistindo", 0.25);
      this.personagens[this.plateia].tocar("torcida", 0.2);
      this.api.som("quica");
    });
  }

  // ---------------------------------------------------------------- física e jogada
  _passoFisica(h) {
    const bola = this.corpoBola;
    this.fisica.passo(h, this.pinos, bola, true);
    // pinos que pararam dormem (param de tremer)
    for (const c of this.pinos.corpos) {
      if (!c.dinamico) continue;
      if (c.v.lengthSq() < 0.0025 && c.w.lengthSq() < 0.04) {
        c.parado += h;
        if (c.parado > 0.4) {
          c.dinamico = false;
          c.v.set(0, 0, 0);
          c.w.set(0, 0, 0);
        }
      } else {
        c.parado = 0;
      }
    }
    if (bola.dinamico) {
      // giro da bola rolando (só o desenho)
      const v = bola.v;
      const vel = Math.hypot(v.x, v.z);
      if (vel > 1e-4) {
        this._eixoGiro.set(-v.z / vel, 0, v.x / vel);
        this._qt.setFromAxisAngle(this._eixoGiro, -vel / RAIO_BOLA * h);
        this.bola.giro.premultiply(this._qt);
      }
      // entrou no túnel da caçapa: some
      if (bola.p.z < Z_FUNDO - 0.35) {
        bola.dinamico = false;
        this.bola.rolando = false;
        this.bola.no.visible = false;
        this.bola.brilhos = false;
      }
    }
    if (this.estado === "rolando") {
      this.tJogada += h;
      this._forcarQuedas();
      this._gravarPasso += 1;
      if (this.gravando && this._gravarPasso % 2 === 0 && this.nGrav < MAX_GRAVACAO) this._gravar();
    }
  }

  /** Os pinos que a tabela manda cair e ainda estão de pé levam o
   *  "encontrão" do vizinho (para longe da bola, para trás). */
  _forcarQuedas() {
    if (this.tImpacto < 0 || !this.plano.cair) return;
    const dt = this.tJogada - this.tImpacto;
    const bx = this.bola.pos.x;
    for (const n of this.plano.cair) {
      const c = this.pinos.pino(n);
      if (c.removido || this.forcados.has(n)) continue;
      const fileira = Math.round((Z_PINO1 - c.lugar[2]) / FILEIRA);
      const prazo = (c.dinamico ? 1.1 : 0.32) + fileira * 0.12;
      if (dt < prazo) continue;
      if (this.pinos.estaCaido(c)) {
        this.forcados.add(n);
        continue;
      }
      this.forcados.add(n);
      c.acordar();
      const lado = Math.abs(c.lugar[0] - bx) < 0.05 ? (Math.random() < 0.5 ? -1 : 1) : sinal(c.lugar[0] - bx);
      const dx = lado * aleat(0.5, 0.9);
      const dz = -aleat(0.6, 1.0);
      const l = Math.hypot(dx, dz);
      c.v.set(dx / l * 1.3, 0.4, dz / l * 1.3);
      // gira para cair na direção do empurrão (eixo = cima x direção)
      c.w.set(dz / l * -8.5, aleat(-2, 2), dx / l * 8.5);
    }
  }

  _gravar() {
    const o = this.nGrav * QUADRO_GRAVACAO;
    const g = this.gravacao;
    const b = this.corpoBola;
    g[o] = b.p.x;
    g[o + 1] = b.p.y;
    g[o + 2] = b.p.z;
    const q = this.bola.giro;
    g[o + 3] = q.x;
    g[o + 4] = q.y;
    g[o + 5] = q.z;
    g[o + 6] = this.bola.no.visible ? q.w : q.w + 10;   // (+10 = bola escondida)
    this.pinos.foto(g, o + 7);
    this.gravTempos[this.nGrav] = this.tJogada;
    this.nGrav++;
  }

  _rolando() {
    const b = this.bola.pos;
    this.mundo.bolaZ = -b.z;
    for (const nome of ["bob", "mia"]) this.personagens[nome].olharAlvo = b;
    if (b.z < Z_PINO1 + 3.3) this.pinos.susto(b);
    // câmera: desce para perseguir a bola, depois vai para os pinos
    if (!this.camBaixa && b.z < -2.5) {
      this.camBaixa = true;
      this.cam.seguir(() => this.bola.pos, [0.0, 0.85, 2.5], [0, 0.05, -4.5], 52, 40, 2.8);
    }
    if (!this.deckCam && b.z < Z_PINO1 + 4.6) {
      this.deckCam = true;
      this.cam.ir([b.x * 0.25 + 0.32, 0.9, Z_PINO1 + 3.0], [0, 0.16, Z_PINO1 - 0.5], 38, 36, 3.2);
    }
    if (this.tImpacto < 0 && b.z < Z_PINO1 + 0.22 && Math.abs(b.x) < MEIA_LARGURA) this._impacto(b);
    let fim = false;
    if (this.tImpacto >= 0) {
      const dt = this.tJogada - this.tImpacto;
      fim = dt > 2.8 || (dt > 1.4 && this.pinos.todosParados());
    } else if (b.z < Z_FIM_DECK - 0.4 || b.y < -0.5) {
      fim = this.tJogada > 0.5;
    }
    if (this.tJogada > 7.5) fim = true;
    if (fim) this._finalizarJogada();
  }

  _impacto(b) {
    this.tImpacto = this.tJogada;
    const cheio = Math.abs(b.x) < 0.2 && this.emPeAntes.length >= 6;
    const forte = cheio ? 8 : 3;
    this.cam.tremer(0.03 + forte * 0.005, 0.4);
    this.cam.soco(cheio ? 3.5 : 1.8);
    this.particulas.poeira([b.x, 0.05, b.z], 1.0 + forte * 0.08);
    if (cheio) this.api.som("batida");
    if (this.plano.cair && this.plano.cair.length === 10) {
      this.mundo.lampadas(1);
      this._cameraLenta(0.4, 0.5);
    }
  }

  /** Câmera lenta que ENTRA e SAI suave (0,08 s descendo, segura, 0,3 s voltando). */
  _cameraLenta(escala, durReal) {
    this.lenta = { t: 0, escala, segura: Math.max(durReal / VELOCIDADE - 0.08, 0) };
  }

  _passoLenta(dtReal) {
    const l = this.lenta;
    if (!l) return;
    l.t += dtReal;
    if (l.t < 0.08) this.ritmo = mistura(1, l.escala, Math.sin(l.t / 0.08 * Math.PI / 2));
    else if (l.t < 0.08 + l.segura) this.ritmo = l.escala;
    else if (l.t < 0.08 + l.segura + 0.3) this.ritmo = mistura(l.escala, 1, 1 - Math.cos((l.t - 0.08 - l.segura) / 0.3 * Math.PI / 2));
    else {
      this.ritmo = 1;
      this.lenta = null;
    }
  }

  async _finalizarJogada() {
    this.estado = "resultado";
    const s = this.novoSeq();
    this.gravando = false;
    this.lenta = null;
    this.ritmo = 1;
    this.mundo.acenderPista(false);
    this.mundo.lampadas(0);
    const derrubados = this.pinos.caidosDesde(this.emPeAntes);
    const n = derrubados.length;
    const festaPinos = this.pinos.reagir();
    this.hud.mostrarMapa(this.pinos.emPe());
    const a = this.personagens[this.ativo];
    const p = this.personagens[this.plateia];
    a.olharAlvo = null;
    p.olharAlvo = null;
    const res = this.placar.registrar(n);
    this.hud.atualizarPlacar(this.placar);
    this.api.placar({ pontos: this.placar.atual().pontos, info: `Rodada ${this.placar.rodadaAtual + 1} de ${RODADAS}` });
    const tipo = res.tipo;
    const sobrou = this.pinos.emPe().length;
    const zp = [0, 0.6, Z_PINO1 - 0.4];
    if (tipo === "strike") {
      this.hud.flash(CREME, 0.75);
      this.hud.letreiro("strike", "", 1.9);
      this.api.som("strike");
      this.api.vibrar(60);
      this.mundo.lampadas(1);
      this.particulas.estrelas(zp, 40, 1.3);
      this.particulas.confete([0, 0.3, Z_PINO1 + 1.5], 1.6, 90);
    } else if (tipo === "spare") {
      this.hud.flash("#C9F7FF", 0.55);
      this.hud.letreiro("spare", "", 1.7);
      this.api.som("acerto");
      this.mundo.lampadas(2);
      this.particulas.estrelas(zp, 28);
    } else if (tipo === "zero") {
      this.hud.letreiro("ops", "", 1.5);
      this.api.som("erro");
    } else {
      let nome = "boa";
      if (n >= 7) nome = Math.random() < 0.5 ? "super" : "uau";
      else if (sobrou === 1) nome = "quase";
      this.hud.letreiro(nome, `${n} ${n === 1 ? "PINO" : "PINOS"}!`, 1.5);
      this.api.som("ponto");
      if (n >= 5) this.particulas.estrelas([0, 0.5, Z_PINO1 - 0.3], 16, 0.8);
    }
    if (res.pontos > 0) this.hud.pontosVoando(res.pontos);
    if (tipo === "strike") {
      const seguidos = this.placar.atual().seguidos;
      if (seguidos >= 2) {
        this.hud.sequencia(seguidos);
        this.relogio.esperar(1.0).then(() => {
          if (s === this.seq || this.estado === "replay") {
            this.hud.letreiro("pegando_fogo", `${seguidos} STRIKES SEGUIDOS!`, 1.6, 0.55);
            this.api.som("combo");
          }
        });
      }
    }
    // replay do strike
    if (tipo === "strike" && this.nGrav > 20) {
      if (!(await this.esperar(1.5, s, false))) return;
      await this._replay(s);
      if (s !== this.seq) return;
    } else if (!(await this.esperar(festaPinos > 0 ? 1.6 : 1.1, s))) {
      return;
    }
    // reação do bichinho (câmera bem de frente)
    const pa = a.raiz.position;
    if (tipo === "strike") this.cam.ir([pa.x + 0.45, 1.35, pa.z - 3.6], [pa.x, 1.2, pa.z], 44, 34, 3.0);
    else this.cam.ir([pa.x + 0.35, 0.9, pa.z - 2.3], [pa.x, 0.72, pa.z], 36, 30, 3.5);
    if (tipo === "strike") {
      a.tocar("comemora_strike", 0.15, true);
      p.tocar("feliz", 0.2, true);
      this.particulas.confete([pa.x, 2.0, pa.z - 0.6], 1.2, 70);
      this.api.som("vitoria");
    } else if (tipo === "spare") {
      a.tocar("feliz", 0.15, true);
      p.tocar("feliz", 0.2, true);
    } else if (tipo === "zero") {
      a.tocar("triste", 0.15, true);
      p.tocar("acenar", 0.2, true);
    } else {
      a.tocar(sobrou === 1 ? "quase" : "feliz", 0.15, true);
    }
    if (!(await this.esperar(tipo === "strike" ? 2.6 : 1.8, s))) return;
    const proximo = this.placar.avancar(res.fimRodada);
    this.bola.guardar();
    this.corpoBola.dinamico = false;
    if (proximo === "fim") {
      this._fimDeJogo();
      return;
    }
    // a máquina de pinos: barra varre os caídos, a mesa recoloca / rack novo
    this._planoMaquina();
    this.pinos.reviver();
    const trabalho = proximo === "bola" ? this.maquina.reposicionar() : this.maquina.rackNovo();
    await trabalho;
    if (s !== this.seq) return;
    this.hud.mostrarMapa(this.pinos.emPe());
    this._vez(proximo === "rodada");
  }

  /** Câmera de frente para os pinos, baixinha, para ver a máquina trabalhar. */
  _planoMaquina() {
    this.cam.corte([0.55, 0.62, Z_PINO1 + 2.5], [0, 0.5, Z_PINO1 - 0.45], 40, 40);
    this.cam.ir([-0.35, 0.72, Z_PINO1 + 2.2], [0, 0.5, Z_PINO1 - 0.45], 40, 40, 0.4);
  }

  // ---------------------------------------------------------------- replay
  /** REPLAY do strike: a MESMA jogada (cada passo gravado), em câmera lenta
   *  — colada na bola, corte de lado na batida e a explosão de pinos. */
  async _replay(s) {
    this.estado = "replay";
    this.hud.modoReplay(true);
    this.api.som("whoosh");
    this.pinos.pararFesta();
    this.pinos.reviver();
    const fim = this.gravTempos[this.nGrav - 1];
    this.replayInicio = Math.max(this.gravTempos[0], this.tImpacto - REPLAY_ANTES);
    this.replayFim = Math.min(this.tImpacto + REPLAY_DEPOIS, fim);
    this.replayT = this.replayInicio;
    this.replayRastro = Math.max(this.gravTempos[0], this.replayInicio - 27 / 60);
    this.bola.emReplay = true;
    this.bola.rolando = false;
    this.bola.limparRastro();
    this.bola.brilhos = true;
    this._mostrarQuadro(this.replayT);
    this.bola.acender(0.8);
    const alvo = this.alvoReplay;
    // 1) câmera rasante colada na bola
    this.cam.corte([alvo.x + 0.42, alvo.y + 0.16, alvo.z + 0.75], [alvo.x - 0.1, alvo.y + 0.08, alvo.z - 1.2], 40, 46);
    this.cam.seguir(() => this.alvoReplay, [0.42, 0.16, 0.75], [-0.1, 0.08, -1.2], 40, 46, 12.0);
    while (this.estado === "replay" && this.replayT < this.tImpacto - 0.12) {
      if (!(await this.relogio.esperar(0.001, () => s !== this.seq))) return;
    }
    // 2) no impacto: lateral, baixinho, bem lenta
    this.cam.corte([0.5, 0.32, Z_PINO1 + 1.1], [-0.05, 0.24, Z_PINO1 - 0.35], 40, 48);
    this.cam.orbitar([0, 0.24, Z_PINO1 - 0.4], 1.55, 0.1, -0.3, 40, 48);
    while (this.estado === "replay" && this.replayT < this.tImpacto) {
      if (!(await this.relogio.esperar(0.001, () => s !== this.seq))) return;
    }
    this.cam.tremer(0.02, 0.5);
    this.api.som("batida");
    while (this.estado === "replay" && this.replayT < this.tImpacto + 0.65) {
      if (!(await this.relogio.esperar(0.001, () => s !== this.seq))) return;
    }
    // 3) abre o plano: a explosão de pinos
    this.cam.ir([-0.2, 1.3, Z_PINO1 + 2.1], [0, 0.25, Z_PINO1 - 0.6], 44, 46, 1.6);
    while (this.estado === "replay") {
      if (!(await this.relogio.esperar(0.001, () => s !== this.seq))) return;
    }
    this.bola.acender(0);
    this.bola.emReplay = false;
    this.bola.brilhos = false;
    this.pinos.reagir();
    this.hud.modoReplay(false);
  }

  _rodarReplay(dt) {
    const pulando = this.pular;
    const vel = pulando ? 3.0 : mistura(REPLAY_VEL_BATIDA, REPLAY_VEL, suave(0.08, 0.75, Math.abs(this.replayT - this.tImpacto)));
    this.replayT = Math.min(this.replayT + dt / VELOCIDADE * VELOCIDADE * vel, this.replayFim);
    this.bola.ritmo = vel;
    // o rastro: pontos nos mesmos instantes da jogada de verdade
    while (this.replayRastro + 1 / 60 <= this.replayT) {
      this.replayRastro += 1 / 60;
      this._mostrarQuadro(this.replayRastro);
      if (this.bola.no.visible) {
        this.bola.rolando = true;
        this.bola.marcarRastro(this.bola.pos);
        this.bola.rolando = false;
      }
    }
    this._mostrarQuadro(this.replayT);
    if (this.replayT < this.tImpacto + 0.1) this.pinos.susto(this.bola.pos);
    if (this.replayT >= this.replayFim) {
      // termina exatamente como ficou de verdade
      this._mostrarQuadro(this.gravTempos[this.nGrav - 1]);
      this.estado = "resultado";
    }
  }

  /** Bola e pinos como estavam no instante t (entre dois passos gravados). */
  _mostrarQuadro(t) {
    const n = this.nGrav;
    let lo = 0;
    let hi = n - 1;
    while (lo < hi) {
      const m = (lo + hi + 1) >> 1;
      if (this.gravTempos[m] <= t) lo = m;
      else hi = m - 1;
    }
    const l1 = Math.min(lo + 1, n - 1);
    const t0 = this.gravTempos[lo];
    const t1 = this.gravTempos[l1];
    const u = t1 > t0 ? lim((t - t0) / (t1 - t0), 0, 1) : 0;
    const g = this.gravacao;
    const a = lo * QUADRO_GRAVACAO;
    const b = l1 * QUADRO_GRAVACAO;
    this.bola.pos.set(mistura(g[a], g[b], u), mistura(g[a + 1], g[b + 1], u), mistura(g[a + 2], g[b + 2], u));
    const escondida = g[a + 6] > 5;
    this.bola.no.visible = !escondida;
    this._qt.set(g[a + 3], g[a + 4], g[a + 5], escondida ? g[a + 6] - 10 : g[a + 6]);
    const qb = this._qb || (this._qb = new this.T.Quaternion());
    qb.set(g[b + 3], g[b + 4], g[b + 5], g[b + 6] > 5 ? g[b + 6] - 10 : g[b + 6]);
    this.bola.giro.copy(this._qt).slerp(qb, u);
    this.alvoReplay.copy(this.bola.pos);
    this.pinos.aplicarFoto(g, a + 7, g, b + 7, u);
  }

  // ---------------------------------------------------------------- fim de jogo
  _fimDeJogo() {
    this.estado = "fim";
    this.novoSeq();
    this.fimT = 0;
    this.hud.mostrarPlacar(false);
    this.hud.conviteLigado(false);
    this.api.som("fim");
    const j = this.placar.jogadores[0];
    const estrelas = this.placar.estrelas(0);
    const { posicao, lista } = this._classificacao(j);
    this.hud.fim = { t: 0, jogador: { personagem: j.personagem, pontos: j.pontos, estrelas }, posicao, classificacao: lista };
    // NOVO RECORDE: o melhor de sempre neste aparelho (na máquina, o da casa)
    if (this._novoRecorde(j.pontos)) {
      const s = this.seq;
      this.relogio.esperar(3.4, () => s !== this.seq).then((ok) => {
        if (!ok || this.estado !== "fim") return;
        this.hud.letreiro("novo_recorde", `${j.pontos} PONTOS`, 3.0, 0.42);
        this.api.som("vitoria");
      });
    }
    // os bichinhos no "pódio", com festa
    const t = this.personagens.bob;
    const r = this.personagens.mia;
    this.bola.guardar();
    for (const p of [t, r]) {
      p.segurarBola(false);
      p.olharAlvo = null;
      p.jatos(false);
    }
    this._vestirTodos(null, "");
    t.posicionar([-0.62, 0, 2.3], 0);
    r.posicionar([0.62, 0, 2.3], 0);
    t.ocioso(true);
    r.ocioso(true);
    const prot = this.personagens[j.personagem];
    if (estrelas >= 2) {
      prot.tocar("vitoria", 0.3, true);
      prot.jatos(true);
      prot.expressao("empolgado");
    }
    this.cam.ir([0, 1.35, 6.6], [0, 1.1, 2.3], 40, 44, 2.0);
    this.particulas.confete([0, 3.2, 2.3], 2.2, 160);
    for (let i = 0; i < 7; i++) {
      this.relogio.esperar(0.35 * i).then(() => {
        if (this.estado === "fim") this.particulas.fogo([aleat(-2.5, 2.5), 3.8 + aleat(-0.5, 1.5), -2.0 + aleat(-1, 1)]);
      });
    }
    this.terminado = false;
  }

  _fimTempo(dtReal) {
    this.fimT += dtReal;
    if (this.hud.fim) this.hud.fim.t = this.fimT * VELOCIDADE;
    if (this.fimT > 3.0 && this.personagens.bob.jatosLigados && this.fimT < 3.1) this.personagens[this.placar.jogadores[0].personagem].jatos(false);
    if (!this.terminado && this.fimT > 6.5) {
      this.terminado = true;
      const j = this.placar.jogadores[0];
      const e = this.placar.estrelas(0);
      this.api.terminar({
        pontos: j.pontos,
        titulo: e >= 3 ? "Parabéns!" : "Fim de jogo",
        detalhe: `${j.strikes} strike${j.strikes === 1 ? "" : "s"} · ${j.spares} spare${j.spares === 1 ? "" : "s"} · ${"★".repeat(e)}${"☆".repeat(3 - e)}`,
      });
    }
  }

  /** O recorde é o do console (ele grava ao terminar a partida): aqui só
   *  se compara com o de antes. A 1ª partida no aparelho não é recorde. */
  _novoRecorde(pontos) {
    let antes = 0;
    try {
      antes = Number(window.localStorage.getItem(CHAVE_RECORDE)) || 0;
    } catch (erro) { return false; }
    return antes > 0 && pontos > antes;
  }

  /** CLASSIFICAÇÃO DE HOJE (neste aparelho): os 5 melhores do dia. */
  _classificacao(j) {
    const hoje = new Date().toISOString().slice(0, 10);
    let dados = { dia: hoje, lista: [] };
    try {
      const salvo = JSON.parse(window.localStorage.getItem("ls-strike-kids-hoje") || "null");
      if (salvo && salvo.dia === hoje && Array.isArray(salvo.lista)) dados = salvo;
    } catch (erro) { /* sem armazenamento: só esta partida */ }
    const agora = new Date();
    const hora = `${String(agora.getHours()).padStart(2, "0")}:${String(agora.getMinutes()).padStart(2, "0")}`;
    const minha = { pontos: j.pontos, personagem: j.personagem, hora, id: Date.now() };
    dados.lista.push(minha);
    dados.lista.sort((a, b) => b.pontos - a.pontos);
    dados.lista = dados.lista.slice(0, 20);
    try {
      window.localStorage.setItem("ls-strike-kids-hoje", JSON.stringify(dados));
    } catch (erro) { /* aba anônima */ }
    const posicao = dados.lista.findIndex((e) => e.id === minha.id) + 1;
    const lista = dados.lista.slice(0, 5).map((e) => ({ ...e, agora: e.id === minha.id }));
    return { posicao, lista };
  }
}

