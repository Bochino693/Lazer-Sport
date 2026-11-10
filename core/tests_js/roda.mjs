// A RODA DA ARENA 3D (core/static/site/arena/roda.js), conferida com as máquinas de verdade:
//   node core/tests_js/roda.mjs <maquinas.json>   -- o "arena_dados.maquinas" da página (core/views_arena.py)
// * UM DE CADA POR VEZ: brinquedão, área ninja, área baby e área esportiva têm UM lugar cada na roda,
//   e todos os modelos da categoria ficam nele (os brinquedões 2, 3 e 4 na mesma vaga);
// * quem chega depois numa categoria (outro brinquedão, outra área ninja) entra na vaga dela sozinho,
//   pelo nome e pelas categorias, sem mudar a roda de lugar (a vaga já tem o tamanho do maior);
// * NADA COLADO: entre dois estandes (a plataforma ou o pedestal, com a placa do nome) há sempre de
//   2,5 a 4 m de chão livre, e ninguém entra no círculo do meio (o símbolo da marca).
// Sai com código 1 e a lista dos problemas quando algo não confere.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const R = await import(pathToFileURL(path.join(AQUI, "..", "static", "site", "arena", "roda.js")));
const maquinas = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const problemas = [];
const confere = (cond, msg) => { if (!cond) problemas.push(msg); };

const medidas = (d) => {
  const m = (d.medidas_modelo || []).length === 3 ? d.medidas_modelo : d.medidas || [];
  return { largura: Number(m[1]) || 1, fundo: Number(m[2]) || 1 };
};
// a área baby que a arena monta com o projetista (sem uma no cadastro)
const BABY = { id: "area-baby", nome: "Área Baby", grupo: "brinquedoes", categorias: ["Área baby"], medidas: [2.3, 9, 6] };
const itensDe = (lista) => lista.map((d) => ({ dados: d, ...medidas(d) }));
const comBaby = [...maquinas, BABY];

/* ---------- um de cada por vez ---------- */
const { lugares, vagas } = R.montarVagas(itensDe(comBaby));
const porVaga = {};
lugares.forEach((l) => { if (l.vaga) porVaga[l.vaga.id] = (porVaga[l.vaga.id] || 0) + 1; });
for (const id of ["brinquedao", "ninja", "baby", "esportiva"]) {
  confere(porVaga[id] === 1, `a vaga "${id}" aparece ${porVaga[id] || 0} vez(es) na roda (deve ser 1)`);
}
const nomes = (id) => (vagas[id] ? vagas[id].membros.map((m) => m.dados.nome) : []);
for (const nome of ["Brinquedão Modelo 2", "Brinquedão Modelo 3", "Brinquedão Modelo 4"]) {
  confere(nomes("brinquedao").includes(nome), `${nome} fora da vaga do brinquedão (${nomes("brinquedao")})`);
}
confere(nomes("ninja").includes("Brinquedão Ninja"), `o Brinquedão Ninja fora da área ninja (${nomes("ninja")})`);
confere(nomes("esportiva").includes("Espaço Esportivo Modelo 1"), `o Espaço Esportivo fora da área esportiva (${nomes("esportiva")})`);
for (const fixo of ["Strike Kids", "Trampolim de Enterrada"]) {
  confere(lugares.some((l) => l.fixo && l.fixo.dados.nome === fixo), `${fixo} deveria ficar sempre na roda`);
}
// a vaga tem o tamanho do maior modelo dela
const b = vagas.brinquedao;
if (b) {
  confere(b.largura === Math.max(...b.membros.map((m) => m.largura)) && b.fundo === Math.max(...b.membros.map((m) => m.fundo)), "a vaga do brinquedão não tem o tamanho do maior");
}

/* ---------- quem chega depois entra na vaga da categoria ---------- */
const novos = [
  { id: 901, nome: "Brinquedão Selva", grupo: "brinquedoes", categorias: ["Brinquedões"], medidas_modelo: [3.4, 9, 3] },
  { id: 902, nome: "Área Ninja Kids", grupo: "brinquedoes", categorias: ["Brinquedões"], medidas_modelo: [3, 12, 2.3] },
  { id: 903, nome: "Espaço Baby Colorido", grupo: "brinquedoes", categorias: ["Área baby"], medidas_modelo: [2, 6, 4] },
];
const depois = R.montarVagas(itensDe([...comBaby, ...novos]));
confere(depois.lugares.length === lugares.length, `os modelos novos mudaram o número de lugares da roda (${lugares.length} -> ${depois.lugares.length})`);
confere(depois.vagas.brinquedao.membros.some((m) => m.dados.nome === "Brinquedão Selva"), "o Brinquedão Selva não entrou na vaga do brinquedão");
confere(depois.vagas.ninja.membros.some((m) => m.dados.nome === "Área Ninja Kids"), "a Área Ninja Kids não entrou na vaga da área ninja");
confere(depois.vagas.baby.membros.some((m) => m.dados.nome === "Espaço Baby Colorido"), "o Espaço Baby não entrou na vaga da área baby");
// (menores que o maior da vaga: a roda fica onde estava)
const antesDaRoda = R.arrumarRoda(lugares);
const depoisDaRoda = R.arrumarRoda(depois.lugares);
confere(Math.abs(antesDaRoda.raio - depoisDaRoda.raio) < 1e-6, "um modelo novo menor que o maior da vaga mexeu na roda");

/* ---------- nada colado ---------- */
const t0 = Date.now();
const roda = R.arrumarRoda(lugares);
const ms = Date.now() - t0;
confere(ms < 3000, `a conta da roda demorou ${ms} ms`);
const it = roda.itens;
for (let i = 0; i < it.length; i++) {
  for (let j = i + 1; j < it.length; j++) {
    const d = R.distancia(it[i].mundo, it[j].mundo);
    confere(d >= 2.5 - 1e-6, `os lugares ${i} e ${j} ficam a ${d.toFixed(2)} m (menos de 2,5 m de chão livre)`);
  }
  const vizinho = R.distancia(it[i].mundo, it[(i + 1) % it.length].mundo);
  confere(vizinho <= 4.0, `entre o lugar ${i} e o próximo sobram ${vizinho.toFixed(2)} m (o espaço não ficou repartido)`);
}
confere(roda.dentro >= 8.5 - 1e-6, `um estande entra no círculo do meio (${roda.dentro.toFixed(2)} m do centro)`);
confere(roda.beira > roda.raio, "a cerca de pilares não cobre a roda");
// o Espaço Esportivo fica do lado oposto à entrada (0,5 rad)
const iEsportiva = lugares.findIndex((l) => l.vaga && l.vaga.id === "esportiva");
if (iEsportiva >= 0) {
  const a = it[iEsportiva].a;
  const oposto = Math.abs(Math.atan2(Math.sin(a - (0.5 + Math.PI)), Math.cos(a - (0.5 + Math.PI))));
  confere(oposto < 0.05, `a área esportiva não ficou do lado oposto à entrada (${oposto.toFixed(2)} rad)`);
}

if (problemas.length) {
  console.log(problemas.join("\n"));
  process.exit(1);
}
console.log(`ok: ${lugares.length} lugares na roda (raio ${roda.raio.toFixed(1)} m, cerca a ${roda.beira.toFixed(1)} m), ${Object.keys(vagas).length} vagas que se revezam, a conta em ${ms} ms`);
