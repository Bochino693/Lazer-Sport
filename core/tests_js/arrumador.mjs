// O arrumador do "Monte seu projeto" (core/static/site/projeto3d/arrumador.js), conferido de fora:
// node core/tests_js/arrumador.mjs <catalogo.json>  -- o catálogo vem do Django (core/projeto3d.catalogo).
// Sai com código 1 e a lista dos problemas quando algo não confere.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const ESTATICO = path.join(AQUI, "..", "static");
const { arrumar, espacoParaTudo, REGRAS } = await import(pathToFileURL(path.join(ESTATICO, "site/projeto3d/arrumador.js")));
const catalogo = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const problemas = [];
const confere = (cond, msg) => { if (!cond) problemas.push(msg); };
const id = (nome) => (catalogo.itens.find((i) => i.nome === nome) || {}).id;
const cruza = (a, b) => a.x0 < b.x1 - 1e-6 && b.x0 < a.x1 - 1e-6 && a.z0 < b.z1 - 1e-6 && b.z0 < a.z1 - 1e-6;

function geometria(r, rotulo) {
  const s = r.sala;
  r.itens.forEach((i, n) => {
    confere(i.zona.x0 >= s.x0 - 1e-6 && i.zona.x1 <= s.x1 + 1e-6 && i.zona.z0 >= s.z0 - 1e-6 && i.zona.z1 <= s.z1 + 1e-6, `${rotulo}: ${i.nome} sai da sala`);
    confere(!cruza(i.zona, r.hall), `${rotulo}: ${i.nome} em cima da entrada`);
    r.itens.slice(n + 1).forEach((o) => confere(!cruza(i.zona, o.zona), `${rotulo}: ${i.nome} e ${o.nome} se sobrepõem`));
    confere(i.corpo.x0 >= i.zona.x0 - 1e-6 && i.corpo.x1 <= i.zona.x1 + 1e-6, `${rotulo}: o corpo de ${i.nome} sai da zona`);
  });
  // da entrada até cada coisa: algum centro alcançado encosta na zona (a meio corredor)
  const p = r.passagem;
  const chega = (zona) => {
    const m = p.meio + p.g * 1.6;
    for (let k = 0; k < p.nz; k++) for (let i = 0; i < p.nx; i++) {
      if (!p.alcance[k * p.nx + i]) continue;
      const x = p.x0 + (i + 0.5) * p.g, z = p.z0 + (k + 0.5) * p.g;
      if (x >= zona.x0 - m && x <= zona.x1 + m && z >= zona.z0 - m && z <= zona.z1 + m) return true;
    }
    return false;
  };
  r.itens.forEach((i) => confere(chega(i.zona), `${rotulo}: sem passagem até ${i.nome}`));
}

const maquinas = catalogo.itens.filter((i) => i.tipo === "maquina");
const todas = (q) => maquinas.slice(0, 6).map((m) => ({ id: m.id, qtd: q }));

// 1. um espaço médio, com tudo: cabe sem sobrepor, dentro da sala, longe da entrada e com passagem
const medio = arrumar({ largura: 20, comprimento: 15, pe_direito: 4 },
  { principal: { tipo: "area", area: "esportivo" }, areas: ["baby"], itens: todas(1), semente: 3 }, catalogo);
geometria(medio, "20x15");
confere(medio.itens.some((i) => i.principal && i.area), "20x15: o principal sob medida ficou de fora");
confere(medio.recusados.length === 0, "20x15: algo ficou de fora: " + JSON.stringify(medio.recusados.map((r) => r.nome + ": " + r.motivo)));
const principal = medio.itens.find((i) => i.principal);
confere(principal && principal.w * principal.d > catalogo.areas.esportivo.min[0] * catalogo.areas.esportivo.min[1] * 1.5, "20x15: o principal não cresceu no que sobrou");
// as máquinas de parede ficam de costas para a parede (a 10 cm)
for (const i of medio.itens.filter((x) => x.parede !== null && x.tipo === "maquina")) {
  const s = medio.sala;
  const folga = { 0: i.corpo.z0 - s.z0, 180: s.z1 - i.corpo.z1, 90: i.corpo.x0 - s.x0, 270: s.x1 - i.corpo.x1 }[i.parede];
  confere(Math.abs(folga - REGRAS.parede) < 0.02, `20x15: ${i.nome} não está encostada na parede (${folga})`);
}

// 2. a mesma escolha e a mesma semente dão a mesma planta (o painel refaz o 3D do cliente)
const deNovo = arrumar({ largura: 20, comprimento: 15, pe_direito: 4 },
  { principal: { tipo: "area", area: "esportivo" }, areas: ["baby"], itens: todas(1), semente: 3 }, catalogo);
confere(JSON.stringify(deNovo.itens) === JSON.stringify(medio.itens), "a mesma semente deu outra planta");

// 3. espaço pequeno demais: o que não cabe fica de fora COM o motivo, e o resto continua certo
const pequeno = arrumar({ largura: 6, comprimento: 5, pe_direito: 2.5 },
  { principal: { tipo: "area", area: "trampolim" }, areas: ["brinquedao"], itens: todas(3), semente: 1 }, catalogo);
geometria(pequeno, "6x5");
const trampolim = pequeno.recusados.find((r) => r.principal);
confere(trampolim && trampolim.codigo === "altura" && /pé-direito/.test(trampolim.motivo), "6x5: o trampolim com pé-direito de 2,5 m devia ficar de fora pela altura");
confere(pequeno.recusados.every((r) => r.motivo && r.motivo.length > 10), "6x5: recusa sem motivo");
const sugestao = espacoParaTudo({ largura: 6, comprimento: 5, pe_direito: 2.5 },
  { principal: null, areas: ["brinquedao"], itens: todas(3), semente: 1 }, catalogo);
confere(!sugestao || (sugestao.largura >= 6 && sugestao.comprimento >= 5), "6x5: a sugestão de espaço é menor que o espaço");

// 4. o espaço pronto de 39 x 23 m não entra num galpão de 20 x 15: fica de fora pelo tamanho
const pronto = catalogo.itens.find((i) => i.tipo === "grande" && i.medidas[1] > 30);
if (pronto) {
  const r = arrumar({ largura: 20, comprimento: 15, pe_direito: 6 }, { principal: { tipo: "item", id: pronto.id }, areas: [], itens: [], semente: 1 }, catalogo);
  confere(r.recusados.some((x) => x.principal && x.codigo === "tamanho"), "o espaço de 39 m devia ficar de fora num lugar de 20 m");
  const grande = arrumar({ largura: 45, comprimento: 30, pe_direito: 6 }, { principal: { tipo: "item", id: pronto.id }, areas: [], itens: [], semente: 1 }, catalogo);
  confere(grande.itens.some((x) => x.principal), "o espaço de 39 m devia caber num lugar de 45 x 30 m");
  geometria(grande, "45x30");
}

// 5. só máquinas: todas nas paredes, e as iguais lado a lado
const fliper = arrumar({ largura: 12, comprimento: 10, pe_direito: 3.5 }, { principal: null, areas: [], itens: [{ id: maquinas[0].id, qtd: 4 }], semente: 1 }, catalogo);
geometria(fliper, "12x10");
confere(fliper.itens.length === 4, "12x10: as 4 máquinas iguais deviam caber");

// 6. o projetista do painel desenha toda peça que as áreas sob medida pedem (montar3d-pecas.js)
const T = await import(pathToFileURL(path.join(ESTATICO, "vendor/three/three.module.min.js")));
const utilidades = await import(pathToFileURL(path.join(ESTATICO, "vendor/three/BufferGeometryUtils.js")));
const pecas = await import(pathToFileURL(path.join(AQUI, "..", "..", "sistema_interno/static/interno/montar3d-pecas.js")));
const gerador = await import(pathToFileURL(path.join(AQUI, "..", "..", "sistema_interno/static/interno/montar3d-gerador.js")));
const base = pecas.desenhosBase(T, utilidades);
const desenhos = Object.assign({}, base.desenhos, pecas.desenhosExtra(T, base.ferramentas));
for (const tipo of Object.keys(catalogo.areas)) {
  for (const estilo of ["colorido", "neon", "selva"]) {
    const ideia = gerador.gerar(tipo, { largura: catalogo.areas[tipo].ideal[0], profundidade: catalogo.areas[tipo].ideal[1], altura: 5 }, "#2563eb", 2, { estilo });
    for (const p of ideia.pecas) confere(typeof desenhos[p.tipo] === "function", `a área ${tipo} (${estilo}) pede a peça ${p.tipo}, que não tem desenho`);
  }
}
confere(typeof desenhos.coluna(pecas.CATALOGO_BASE.coluna.d, "#2563eb")[0].geometry === "object", "a coluna não se desenha");

if (problemas.length) {
  console.log([...new Set(problemas)].join("\n"));
  process.exit(1);
}
console.log("arrumador ok");
