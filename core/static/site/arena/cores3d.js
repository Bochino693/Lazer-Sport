/* ======================================================================
   AS CORES DE UM OBJETO 3D (.glb) -- usado pela Arena 3D e pela página do
   brinquedo (o visor). Sem import nenhum.

   Quando o arquivo traz as VARIAÇÕES DE MATERIAL (a extensão
   KHR_materials_variants, que é como os programas de 3D gravam "a mesma
   máquina em várias cores"), cada cor é uma delas.

   Quando não traz, as cores são PALETAS MONTADAS (TEMAS, abaixo). Antes era
   o matiz girado do objeto inteiro: o azul virava amarelo, o verde virava
   roxo, e o brinquedão saía com combinações sem pé nem cabeça. Agora cada
   FAMÍLIA de cor do brinquedo (os verdes, os amarelos, os laranjas, os
   azuis, os vermelhos...) ganha a SUA cor na paleta -- o desenho continua
   com o mesmo contraste (o que era de cores diferentes continua diferente,
   o tom mais escuro continua mais escuro) -- e o que é neutro (branco,
   preto, cinza, a madeira, o texto e o contorno dos adesivos) fica como
   está. Nos adesivos (as texturas), a mesma conta pixel a pixel: a arte
   troca de cores sem perder os brancos, os pretos e as letras.
   ====================================================================== */

/** As famílias de cor, pelo matiz (graus). */
const FAMILIAS = [
  ["vermelho", 0, 14], ["laranja", 14, 38], ["amarelo", 38, 68], ["verde", 68, 165],
  ["ciano", 165, 198], ["azul", 198, 258], ["roxo", 258, 292], ["rosa", 292, 344], ["vermelho", 344, 361],
];

/**
 * As paletas. Cada uma diz a cor de cada FAMÍLIA do desenho original (o que era verde, o
 * que era azul...): a estrutura de um brinquedão costuma ser a família verde, e os painéis
 * as outras -- então cada tema troca a cara da estrutura e combina os painéis com ela.
 * Cores vivas, com contraste entre as famílias (o que era diferente continua diferente).
 */
export const TEMAS = [
  { chave: "original", nome: "Original" },
  {
    chave: "arco-iris", nome: "Arco-íris", // estrutura azul royal, painéis amarelo, vermelho e verde
    cores: { verde: "#1e5bff", azul: "#16b34a", amarelo: "#ffc400", laranja: "#ff2e4d", vermelho: "#ff7a00", ciano: "#06b6d4", roxo: "#7c3aed", rosa: "#ff3fa4" },
  },
  {
    chave: "oceano", nome: "Oceano", // azul profundo, turquesa, coral e areia
    cores: { verde: "#0a5cff", azul: "#00c2d1", amarelo: "#ffd23f", laranja: "#ff6b6b", vermelho: "#ff8c42", ciano: "#00b8a9", roxo: "#3a86ff", rosa: "#ff7aa2" },
  },
  {
    chave: "selva", nome: "Selva", // verde mata, amarelo sol, laranja e madeira
    cores: { verde: "#2b9348", azul: "#00838f", amarelo: "#fcbf49", laranja: "#f77f00", vermelho: "#d62828", ciano: "#2ec4b6", roxo: "#8f5e3b", rosa: "#e76f51" },
  },
  {
    chave: "doce", nome: "Doce", // estrutura rosa, lilás, azul bebê e amarelo
    cores: { verde: "#ff4f9a", azul: "#5aa9ff", amarelo: "#ffe156", laranja: "#a66bff", vermelho: "#ff9f68", ciano: "#5ce1e6", roxo: "#c084fc", rosa: "#ff7ad9" },
  },
  {
    chave: "esporte", nome: "Esporte", // grafite com vermelho, amarelo e azul marinho
    cores: { verde: "#2a2f3a", azul: "#0b3ea8", amarelo: "#ffd000", laranja: "#e8112d", vermelho: "#ff7b00", ciano: "#00bcd4", roxo: "#5b2a86", rosa: "#ff4d6d" },
  },
  {
    chave: "neon", nome: "Neon", // roxo elétrico com verde, rosa e ciano neon
    cores: { verde: "#7a2cff", azul: "#00e5ff", amarelo: "#d7ff1f", laranja: "#ff2bd6", vermelho: "#ff9e00", ciano: "#2ef2ff", roxo: "#b517ff", rosa: "#ff5ebc" },
  },
];

/** As peças que não se tingem nunca (telas, vidro, LEDs, a pista de madeira...). */
// (o piso do salão e as camas elásticas do espaço esportivo também: são do lugar, não do brinquedo)
const SEM_TINGIR = /^(monitor|tela_video|pista$|pista_|bola|bolsao|led|vidro|metal|espelho|colunas?$|cordas?$|piso-eva|base-plataforma|camas)/i;

/* ---------------------------------------------------------------- contas de cor (sRGB, 0..1) */
function hsl(r, g, b) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return [h * 60, s, l];
}
function rgbDeHsl(h, s, l) {
  h = ((h % 360) + 360) % 360 / 360;
  if (!s) return [l, l, l];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
  const canal = (t) => {
    t = (t + 1) % 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [canal(h + 1 / 3), canal(h), canal(h - 1 / 3)];
}
function hexParaRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}
/** A família de uma cor, ou null quando ela é neutra (fica como está). */
function familia(h, s, l) {
  if (s < 0.2 || l < 0.07 || l > 0.95) return null;
  // bege e madeira (laranja/amarelo apagado e claro): neutro
  if (h >= 14 && h < 60 && s < 0.5 && l > 0.55) return null;
  for (let i = 0; i < FAMILIAS.length; i++) if (h >= FAMILIAS[i][1] && h < FAMILIAS[i][2]) return FAMILIAS[i][0];
  return null;
}
/** Pré-calcula o alvo de cada família do tema (em HSL). */
function alvosDoTema(tema) {
  if (tema._alvos) return tema._alvos;
  const alvos = {};
  Object.keys(tema.cores).forEach((f) => { const c = hexParaRgb(tema.cores[f]); alvos[f] = hsl(c[0], c[1], c[2]); });
  return (tema._alvos = alvos);
}
/**
 * A cor no tema: a família vira a cor do tema, guardando o "mais claro / mais escuro"
 * de cada tom do desenho (o contorno escuro continua mais escuro que o tubo).
 */
function recolorir(r, g, b, alvos) {
  const [h, s, l] = hsl(r, g, b);
  const f = familia(h, s, l);
  if (!f || !alvos[f]) return null;
  const alvo = alvos[f];
  const luz = Math.min(0.9, Math.max(0.1, alvo[2] + (l - 0.5) * 0.55));
  const sat = Math.min(1, alvo[1] * (0.75 + 0.25 * Math.min(1, s / 0.6)));
  return rgbDeHsl(alvo[0], sat, luz);
}
/**
 * A cor na ARTE (adesivos, a logo): a mesma família do tema, mas cada pixel guarda o claro/escuro
 * do desenho (a letra, o contorno, o brilho continuam onde estavam) e NUNCA fica menos saturado do
 * que era. Com a conta das peças lisas (acima), que aproxima tudo da cor do tema, a letra perdia o
 * contorno e o brilho -- o "Strike Kids" ficava apagado no Doce, no Oceano, na Selva.
 */
function recolorirArte(r, g, b, alvos) {
  const [h, s, l] = hsl(r, g, b);
  const f = familia(h, s, l);
  if (!f || !alvos[f]) return null;
  const alvo = alvos[f];
  // cor de tema quase cinza (o grafite do Esporte): o escuro é a graça dela -- vale o claro/escuro
  // do tema, como nas peças lisas (com o desenho por cima); senão o grafite virava um cinza opaco
  if (alvo[1] < 0.3) return recolorir(r, g, b, alvos);
  const luz = Math.min(0.93, Math.max(0.05, l + (alvo[2] - 0.5) * 0.3));
  const sat = Math.min(1, Math.max(s, alvo[1] * 0.95));
  return rgbDeHsl(alvo[0], sat, luz);
}
/* o three.js guarda as cores dos materiais em linear; as contas acima são em sRGB */
const paraSrgb = (c) => (c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055);
const paraLinear = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));

/** As cores que o objeto oferece: as variações do arquivo ou as paletas montadas. */
export function coresDoObjeto(gltf) {
  const variantes = ((gltf.parser.json.extensions || {}).KHR_materials_variants || {}).variants || [];
  if (variantes.length) return variantes.map((v, i) => ({ nome: v.name || `Cor ${i + 1}`, variante: i }));
  return TEMAS.map((t) => ({ nome: t.nome, tema: t }));
}

/** A arte (textura) no tema, pixel a pixel: brancos, pretos e contornos ficam; as letras e o
 *  desenho trocam de cor guardando o claro/escuro e o brilho (recolorirArte). */
function arteNoTema(imagem, alvos) {
  const tela = document.createElement("canvas");
  tela.width = imagem.width;
  tela.height = imagem.height;
  const g = tela.getContext("2d");
  g.drawImage(imagem, 0, 0);
  const dados = g.getImageData(0, 0, tela.width, tela.height);
  const p = dados.data;
  // a mesma cor aparece muitas vezes numa arte: guarda o resultado de cada uma
  const lembrado = new Map();
  for (let i = 0; i < p.length; i += 4) {
    const chave = (p[i] << 16) | (p[i + 1] << 8) | p[i + 2];
    let novo = lembrado.get(chave);
    if (novo === undefined) {
      const c = recolorirArte(p[i] / 255, p[i + 1] / 255, p[i + 2] / 255, alvos);
      novo = c ? ((Math.round(c[0] * 255) << 16) | (Math.round(c[1] * 255) << 8) | Math.round(c[2] * 255)) : -1;
      if (lembrado.size < 200000) lembrado.set(chave, novo);
    }
    if (novo >= 0) { p[i] = (novo >> 16) & 255; p[i + 1] = (novo >> 8) & 255; p[i + 2] = novo & 255; }
  }
  g.putImageData(dados, 0, 0);
  return tela;
}

/** O material no tema (guardado: voltar a uma cor não refaz a conta). */
function materialNoTema(gltf, original, tema) {
  const guardados = gltf.userData.temas || (gltf.userData.temas = new Map());
  let porTema = guardados.get(original);
  if (!porTema) guardados.set(original, (porTema = {}));
  if (!porTema[tema.chave]) {
    const alvos = alvosDoTema(tema);
    const m = original.clone();
    if (m.map && m.map.image && m.map.image.width) {
      // A CÓPIA DA TEXTURA PRECISA DE UMA IMAGEM SÓ DELA. No three.js a textura clonada divide a
      // mesma "fonte" (Source) com a original, e `textura.image = ...` troca a imagem DA FONTE:
      // pintar a cópia pintava a original junto. Era o "não volta": o Original ficava com a arte
      // do último estilo, e cada estilo novo era pintado por cima do anterior -- as cores se
      // somavam até a letra do Strike Kids ficar apagada. Agora a arte pintada ganha uma fonte
      // nova, e a conta parte sempre da imagem de fábrica.
      const textura = m.map.clone();
      const Fonte = m.map.source && m.map.source.constructor;
      const arte = arteNoTema(original.map.image, alvos);
      if (Fonte) textura.source = new Fonte(arte); else textura.image = arte;
      textura.needsUpdate = true;
      m.map = textura;
    }
    if (m.color && !(m.map && m.color.r > 0.98 && m.color.g > 0.98 && m.color.b > 0.98)) {
      const c = recolorir(paraSrgb(m.color.r), paraSrgb(m.color.g), paraSrgb(m.color.b), alvos);
      if (c) { m.color = m.color.clone(); m.color.setRGB(paraLinear(c[0]), paraLinear(c[1]), paraLinear(c[2])); }
    }
    porTema[tema.chave] = m;
  }
  return porTema[tema.chave];
}

/** Veste o objeto na cor escolhida (uma das de `coresDoObjeto`). */
export async function aplicarCor(gltf, cor) {
  const parser = gltf.parser;
  const trocas = [];
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    if (!o.userData.materialOriginal) o.userData.materialOriginal = o.material;
    const original = o.userData.materialOriginal;
    if (cor.variante !== undefined) {
      const ligacao = parser.associations.get(o);
      const primitiva = ligacao && ligacao.meshes !== undefined
        ? parser.json.meshes[ligacao.meshes].primitives[ligacao.primitives]
        : null;
      const variantes = primitiva && primitiva.extensions && primitiva.extensions.KHR_materials_variants;
      const mapa = variantes && variantes.mappings.find((x) => x.variants.includes(cor.variante));
      if (mapa) trocas.push(parser.getDependency("material", mapa.material).then((m) => { o.material = m; }));
      else o.material = original;
      return;
    }
    const nome = (o.material && o.material.name) || o.name || "";
    const fixo = SEM_TINGIR.test(o.name) || SEM_TINGIR.test(nome);
    o.material = !cor.tema || !cor.tema.cores || fixo ? original : materialNoTema(gltf, original, cor.tema);
  });
  await Promise.all(trocas);
}

/**
 * O tema de UMA COR RAIZ (o "tema da montagem" do painel): cada família do desenho original
 * ganha uma cor tirada da raiz -- a estrutura (os verdes e os azuis) fica na própria cor, e
 * os painéis viram as vizinhas, a complementar e o destaque. `cores`: { familia: "#rrggbb" }.
 */
export function temaDeCores(chave, nome, cores) {
  return { chave, nome, cores };
}

/**
 * Veste QUALQUER objeto 3D (por exemplo a cópia de um .glb numa montagem) num tema. `originais`
 * (um WeakMap da malha para o material de fábrica) e `guarda` (um objeto qualquer) ficam com
 * quem chama: assim a cópia não leva o material original no userData (o three.js copia o
 * userData ao clonar e ao exportar). Sem tema, volta às cores de fábrica.
 */
export function vestirObjeto(objeto, tema, originais, guarda) {
  objeto.traverse((o) => {
    if (!o.isMesh) return;
    if (!originais.has(o)) originais.set(o, o.material);
    const original = originais.get(o);
    const nome = (original && original.name) || o.name || "";
    const fixo = SEM_TINGIR.test(o.name) || SEM_TINGIR.test(nome);
    o.material = !tema || !tema.cores || fixo ? original : materialNoTema(guarda, original, tema);
  });
}

/** As cores de destaque do próprio objeto (para a amostra do "Original"). */
function coresDoArquivo(gltf) {
  if (gltf.userData.coresDoArquivo) return gltf.userData.coresDoArquivo;
  const vistas = {};
  (gltf.parser.json.materials || []).forEach((m) => {
    const c = ((m.pbrMetallicRoughness || {}).baseColorFactor) || null;
    if (!c) return;
    const r = paraSrgb(c[0]), g = paraSrgb(c[1]), b = paraSrgb(c[2]);
    const [h, s, l] = hsl(r, g, b);
    const f = familia(h, s, l);
    if (f && !vistas[f]) vistas[f] = "#" + [r, g, b].map((x) => Math.round(x * 255).toString(16).padStart(2, "0")).join("");
  });
  return (gltf.userData.coresDoArquivo = Object.values(vistas).slice(0, 4));
}

/** A amostra para o botão: as cores principais do tema, numa roda. */
export function amostraDaCor(gltf, cor) {
  if (cor.variante !== undefined) return "";
  let cores = cor.tema && cor.tema.cores
    ? ["azul", "amarelo", "vermelho", "verde"].map((f) => cor.tema.cores[f])
    : coresDoArquivo(gltf);
  if (!cores.length) return "";
  if (cores.length === 1) cores = [cores[0], cores[0]];
  const passo = 360 / cores.length;
  return `conic-gradient(${cores.map((c, i) => `${c} ${Math.round(i * passo)}deg ${Math.round((i + 1) * passo)}deg`).join(", ")})`;
}
