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
  const portes = catalogo.areas[tipo].portes || [];
  const medidas = portes.length ? portes.map((p) => [p.chave, p.ideal]) : [["", catalogo.areas[tipo].ideal]];
  for (const [porte, ideal] of medidas) {
    for (const estilo of ["colorido", "neon", "selva"]) {
      const ideia = gerador.gerar(tipo, { largura: ideal[0], profundidade: ideal[1], altura: 6 }, "#2563eb", 2, { estilo, porte });
      for (const p of ideia.pecas) confere(typeof desenhos[p.tipo] === "function", `a área ${tipo} (${porte} ${estilo}) pede a peça ${p.tipo}, que não tem desenho`);
      if (porte) confere(ideia.porte === porte, `${tipo}: pediu o porte ${porte} na medida ideal dele e saiu ${ideia.porte}`);
    }
  }
}
// os portes do servidor (core/projeto3d.py) e os do gerador são os mesmos
for (const [tipo, lista] of Object.entries(gerador.PORTES)) {
  const doServidor = (catalogo.areas[tipo] || {}).portes || [];
  confere(JSON.stringify(lista.map((p) => [p.chave, p.min, p.componentes])) === JSON.stringify(doServidor.map((p) => [p.chave, p.min, p.componentes])),
    `os portes de ${tipo} no gerador e no core/projeto3d.py não batem`);
}
// o trampolim park grande tem o que um park de verdade tem (como o do Espaço Esportivo Modelo 1)
const grande = gerador.gerar("trampolim", { largura: 20, profundidade: 13, altura: 6 }, "#2563eb", 1, {});
const tipos = new Set(grande.pecas.map((p) => p.tipo));
for (const t of ["cama", "espuma", "cama_inclinada", "cesta_parede", "painel", "escalada", "cerca", "degraus_espuma"]) confere(tipos.has(t), `o trampolim park grande sem ${t}`);
// a ÚNICA cesta do park é a da enterrada (a rampa com a cesta presa na parede): nada de tabela em poste
const semPoste = (ideia) => !ideia.pecas.some((p) => p.tipo === "tabela" || p.tipo === "swish");
confere(semPoste(grande), "o trampolim park tem cesta em poste");
const rampas = (ideia) => ideia.pecas.filter((p) => p.tipo === "cama_inclinada").length;
const cestas = (ideia) => ideia.pecas.filter((p) => p.tipo === "cesta_parede");
confere(rampas(grande) === 5 && cestas(grande).length === 5, `o grande com ${rampas(grande)} rampas e ${cestas(grande).length} cestas (pede 5 e 5)`);
confere(cestas(grande).every((c) => c.d.tela === 1), "a cesta da enterrada sem a tela do Swish Arena");
// cada cesta fica em cima da rampa dela (o mesmo x, na parede atrás)
for (const c of cestas(grande)) {
  const r = grande.pecas.find((p) => p.tipo === "cama_inclinada" && Math.abs(p.p[0] - c.p[0]) < 1e-6);
  confere(r && c.p[2] < r.p[2], "uma cesta da enterrada não está na parede em cima da rampa");
}
const compacto = gerador.gerar("trampolim", { largura: 6, profundidade: 6, altura: 5 }, "#2563eb", 1, {});
confere(semPoste(compacto) && rampas(compacto) >= 1 && rampas(compacto) === cestas(compacto).length, "o compacto sem a rampa com a cesta");
const compactoBaixo = gerador.gerar("trampolim", { largura: 6, profundidade: 6, altura: 3.4 }, "#2563eb", 1, {});
confere(!rampas(compactoBaixo) && !cestas(compactoBaixo).length, "a enterrada pede pé-direito de 3,60 m");
const semEnterrada = gerador.gerar("trampolim", { largura: 20, profundidade: 13, altura: 6 }, "#2563eb", 1, { sem: ["enterrada"] });
confere(!rampas(semEnterrada) && !cestas(semEnterrada).length && semPoste(semEnterrada), "tirar as enterradas não tirou as rampas e as cestas");
// a Swish liga e desliga: sem ela, a cesta da enterrada leva a tabela comum (e continua na parede)
const semSwish = gerador.gerar("trampolim", { largura: 20, profundidade: 13, altura: 6 }, "#2563eb", 1, { sem: ["swish"] });
confere(cestas(semSwish).length === 5 && cestas(semSwish).every((c) => c.d.tela === 0) && semPoste(semSwish), "sem a Swish, a cesta não virou a tabela comum na parede");
// o porte vai pela área de verdade: 13,5 × 5,5 m (74 m²) é médio, com as enterradas
confere(gerador.porteQueCabe("trampolim", 13.5, 5.5).chave === "medio", "13,5 × 5,5 m de trampolim park não deu o porte médio");
const faixa = gerador.gerar("trampolim", { largura: 13.5, profundidade: 5.5, altura: 6 }, "#2563eb", 1, {});
for (const t of ["cama_inclinada", "cesta_parede", "espuma"]) confere(faixa.pecas.some((p) => p.tipo === t), `o trampolim park de 13,5 × 5,5 × 6 m sem ${t}`);
const esportivoGrande = gerador.gerar("esportivo", { largura: 36, profundidade: 22, altura: 6 }, "#2563eb", 1, {});
confere(esportivoGrande.pecas.filter((p) => p.tipo === "quadra").length === 2 && esportivoGrande.pecas.some((p) => p.tipo === "espuma")
  && esportivoGrande.pecas.some((p) => p.tipo === "cesta_parede"), "o espaço esportivo grande leva as duas quadras e o trampolim park com as enterradas");
// a área ninja enche a área: raias em zigue-zague, mais obstáculos quanto maior, a escalada e a parede curva na grande
const obstaculos = (ideia) => ideia.pecas.filter((p) => ["degraus", "trave", "rolos", "argolas", "macaco", "corda", "tunel"].includes(p.tipo)).length;
const ninjaMedia = gerador.gerar("ninja", { largura: 13, profundidade: 5, altura: 5 }, "#2563eb", 1, {});
const ninjaGrande = gerador.gerar("ninja", { largura: 24, profundidade: 11, altura: 5 }, "#2563eb", 1, {});
confere(ninjaMedia.porte === "medio" && obstaculos(ninjaMedia) >= 5, `a área ninja média de 13 × 5 m com ${obstaculos(ninjaMedia)} obstáculos`);
confere(ninjaGrande.porte === "grande" && obstaculos(ninjaGrande) >= 14, `a área ninja grande de 24 × 11 m com ${obstaculos(ninjaGrande)} obstáculos`);
for (const t of ["escalada", "parede_curva", "piso_eva", "degraus_espuma"]) confere(ninjaGrande.pecas.some((p) => p.tipo === t), `a área ninja grande sem ${t}`);
// a área baby que é o espaço inteiro vira um parque baby (estações repetidas, com variedade)
const babyGrande = gerador.gerar("baby", { largura: 14, profundidade: 10, altura: 3 }, "#2563eb", 1, {});
for (const t of ["piscina", "piscina_redonda", "casinha", "tunel", "blocos_espuma", "pendulos", "rampa", "escorregador", "arco"]) {
  confere(babyGrande.pecas.some((p) => p.tipo === t), `o parque baby de 14 × 10 m sem ${t}`);
}
const babyPequena = gerador.gerar("baby", { largura: 3.5, profundidade: 3.2, altura: 3 }, "#2563eb", 1, {});
const dentro = (ideia, W, D) => ideia.pecas.every((p) => Math.abs(p.p[0]) <= W / 2 + 0.05 && Math.abs(p.p[2]) <= D / 2 + 0.05);
confere(dentro(babyPequena, 3.5, 3.2) && dentro(babyGrande, 14, 10), "uma peça da área baby saiu da área");
confere(dentro(ninjaGrande, 24, 11) && dentro(ninjaMedia, 13, 5), "uma peça da área ninja saiu da área");

confere(typeof desenhos.coluna(pecas.CATALOGO_BASE.coluna.d, "#2563eb")[0].geometry === "object", "a coluna não se desenha");

if (problemas.length) {
  console.log([...new Set(problemas)].join("\n"));
  process.exit(1);
}
console.log("arrumador ok");
