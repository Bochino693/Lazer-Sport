/* ======================================================================
   AS CORES DE UM OBJETO 3D (.glb) -- usado pela Arena 3D e pela página do
   brinquedo (o visor). Sem import nenhum: o three.js chega como `T`.

   Quando o arquivo traz as VARIAÇÕES DE MATERIAL (a extensão
   KHR_materials_variants, que é como os programas de 3D gravam "a mesma
   máquina em várias cores"), cada cor é uma delas: o carregador do three.js
   lê o arquivo mas não troca as variações, então aqui se acha, para cada
   malha, o material daquela cor (a ligação malha -> primitiva do arquivo
   vem de `parser.associations`).

   Quando não traz (o Strike Kids: a cor é a própria adesivagem), as cores
   são a ARTE GIRADA NO CÍRCULO DAS CORES -- a mesma adesivagem em outro
   tom --, sem mexer no que não é adesivo: a tela, a pista de madeira, as
   bolas, o bolsão e os LEDs (pelo nome da peça no arquivo).
   ====================================================================== */

/** Os tons da adesivagem, em graus no círculo das cores (0 = a original). */
export const TONS_DA_ADESIVAGEM = [
  { nome: "Original", giro: 0 },
  { nome: "Azul", giro: 110 },
  { nome: "Roxo", giro: 160 },
  { nome: "Rosa", giro: 205 },
  { nome: "Vermelho", giro: 230 },
  { nome: "Laranja", giro: -95 },
];

/** As peças que não são adesivo: ficam como estão em todas as cores. */
const SEM_TINGIR = /^(monitor|tela_video|pista$|pista_|bola|bolsao|led|vidro|metal|espelho)/i;

/** As cores que o objeto oferece: as variações do arquivo ou os tons da adesivagem. */
export function coresDoObjeto(gltf) {
  const variantes = ((gltf.parser.json.extensions || {}).KHR_materials_variants || {}).variants || [];
  if (variantes.length) return variantes.map((v, i) => ({ nome: v.name || `Cor ${i + 1}`, variante: i }));
  return TONS_DA_ADESIVAGEM.map((t) => ({ nome: t.nome, giro: t.giro }));
}

/**
 * A imagem com o matiz girado, pixel a pixel (a mesma conta do
 * "hue-rotate" do CSS, que mantém o brilho): funciona em todo navegador,
 * inclusive nos que não têm o filtro do canvas.
 */
function girarMatiz(imagem, graus) {
  const tela = document.createElement("canvas");
  tela.width = imagem.width;
  tela.height = imagem.height;
  const g = tela.getContext("2d");
  g.drawImage(imagem, 0, 0);
  const dados = g.getImageData(0, 0, tela.width, tela.height);
  const p = dados.data;
  const a = (graus * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  const m = [
    0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
    0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.14, 0.072 - c * 0.072 - s * 0.283,
    0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072,
  ];
  for (let i = 0; i < p.length; i += 4) {
    const r = p[i];
    const v = p[i + 1];
    const b = p[i + 2];
    p[i] = m[0] * r + m[1] * v + m[2] * b;
    p[i + 1] = m[3] * r + m[4] * v + m[5] * b;
    p[i + 2] = m[6] * r + m[7] * v + m[8] * b;
  }
  g.putImageData(dados, 0, 0);
  return tela;
}

/** O material na cor girada (guardado: trocar de cor de novo não refaz a conta). */
function materialGirado(gltf, original, giro) {
  const guardados = gltf.userData.tons || (gltf.userData.tons = new Map());
  let porGiro = guardados.get(original);
  if (!porGiro) guardados.set(original, (porGiro = {}));
  if (!porGiro[giro]) {
    const m = original.clone();
    if (m.map && m.map.image && m.map.image.width) {
      const textura = m.map.clone();
      textura.image = girarMatiz(m.map.image, giro);
      textura.needsUpdate = true;
      m.map = textura;
    } else if (m.color) {
      const hsl = {};
      m.color = m.color.clone();
      m.color.getHSL(hsl);
      m.color.setHSL((((hsl.h + giro / 360) % 1) + 1) % 1, hsl.s, hsl.l);
    }
    porGiro[giro] = m;
  }
  return porGiro[giro];
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
    o.material = !cor.giro || SEM_TINGIR.test(o.name) ? original : materialGirado(gltf, original, cor.giro);
  });
  await Promise.all(trocas);
}

/** A amostra da cor para o botão: a cor média da arte, já no tom escolhido. */
export function amostraDaCor(gltf, cor) {
  if (cor.variante !== undefined) return "";
  const base = { r: 0.12, g: 0.62, b: 0.25 }; // o verde da adesivagem do Strike Kids
  const a = ((cor.giro || 0) * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  const r = (0.213 + c * 0.787 - s * 0.213) * base.r + (0.715 - c * 0.715 - s * 0.715) * base.g + (0.072 - c * 0.072 + s * 0.928) * base.b;
  const v = (0.213 - c * 0.213 + s * 0.143) * base.r + (0.715 + c * 0.285 + s * 0.14) * base.g + (0.072 - c * 0.072 - s * 0.283) * base.b;
  const b = (0.213 - c * 0.213 - s * 0.787) * base.r + (0.715 - c * 0.715 + s * 0.715) * base.g + (0.072 + c * 0.928 + s * 0.072) * base.b;
  const hex = (x) => Math.round(Math.min(1, Math.max(0, x)) * 255).toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(v)}${hex(b)}`;
}
