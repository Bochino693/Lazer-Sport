// As ideias para o espaço (core/static/site/projeto3d/sugestoes.js), conferidas de fora:
// node core/tests_js/sugestoes.mjs <catalogo.json>  -- o catálogo vem do Django (core/projeto3d.catalogo).
// Sai com código 1 e a lista dos problemas quando algo não confere.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const ESTATICO = path.join(AQUI, "..", "static");
const RAIZ_INTERNO = path.join(AQUI, "..", "..", "sistema_interno", "static");
const { arrumar } = await import(pathToFileURL(path.join(ESTATICO, "site/projeto3d/arrumador.js")));
const gerador = await import(pathToFileURL(path.join(RAIZ_INTERNO, "interno/montar3d-gerador.js")));
const { sugerir } = await import(pathToFileURL(path.join(ESTATICO, "site/projeto3d/sugestoes.js")));
const catalogo = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const problemas = [];
const confere = (cond, msg) => { if (!cond) problemas.push(msg); };

for (const [W, D, H] of [[8, 6, 3], [10, 8, 3.5], [15, 9, 6], [20, 15, 6], [30, 20, 8]]) {
  const espaco = { largura: W, comprimento: D, pe_direito: H };
  const t = Date.now();
  const ideias = sugerir(espaco, catalogo, arrumar, gerador, { limite: 3 });
  const rotulo = `${W} × ${D} × ${H} m`;
  confere(Date.now() - t < 4000, `${rotulo}: as ideias demoraram ${Date.now() - t} ms`);
  confere(ideias.length >= 1, `${rotulo}: nenhuma ideia`);
  const principais = ideias.map((i) => (i.escolha.principal ? i.escolha.principal.area : "maquinas"));
  confere(new Set(principais).size === principais.length, `${rotulo}: duas ideias do mesmo modelo (${principais})`);
  for (const i of ideias) {
    confere(!i.resultado.recusados.length, `${rotulo}: a ideia "${i.titulo}" deixa coisa de fora`);
    // a ideia, arrumada de novo como o cliente vai ver, dá o mesmo (nada de fora)
    const outra = arrumar(espaco, { ...i.escolha, estilo: "colorido", cor: "#2563eb", semente: 1 }, catalogo);
    confere(!outra.recusados.length && outra.itens.length === i.resultado.itens.length, `${rotulo}: a ideia "${i.titulo}" não se repete`);
    confere(i.titulo && i.linhas.length >= 2, `${rotulo}: a ideia sem título ou sem descrição`);
    confere(i.resultado.numeros.ocupacao <= 92, `${rotulo}: a ideia "${i.titulo}" ocupa ${i.resultado.numeros.ocupacao}%`);
  }
  for (let k = 1; k < ideias.length; k++) confere(ideias[k - 1].nota >= ideias[k].nota, `${rotulo}: as ideias fora da ordem da nota`);
  // pé-direito alto e espaço que dá: a primeira ideia é uma atração de verdade (não só a área baby)
  if (H >= 5 && W * D >= 120) confere(principais[0] !== "baby" && principais[0] !== "maquinas", `${rotulo}: a melhor ideia foi ${principais[0]}`);
  // pé-direito baixo: nada que pede mais do que o espaço tem
  for (const i of ideias) {
    for (const it of i.resultado.itens.filter((x) => x.area)) {
      confere((catalogo.areas[it.area.tipo].pe_direito_minimo || 0) <= H + 1e-6, `${rotulo}: ${it.area.tipo} num pé-direito de ${H} m`);
    }
  }
}

if (problemas.length) {
  console.log([...new Set(problemas)].join("\n"));
  process.exit(1);
}
console.log("sugestões ok");
