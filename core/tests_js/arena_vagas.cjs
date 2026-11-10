// A ARENA 3D DE VERDADE, num Chromium sem tela (Playwright): um de cada categoria
// carregado, a troca na vaga descarta o de antes, e nenhum raio por quadro.
//   node core/tests_js/arena_vagas.cjs <endereço da /arena/>
// Sai com 1 e a lista dos problemas. (core/tests_arena.py, ArenaNoNavegadorTests, roda este.)
const { chromium } = require("playwright");

(async () => {
  const url = process.argv[2];
  const problemas = [];
  const confere = (cond, msg) => { if (!cond) problemas.push(msg); };
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    const page = await (await browser.newContext({ viewport: { width: 900, height: 640 } })).newPage();
    const erros = [];
    page.on("pageerror", (e) => erros.push(e.message));
    await page.goto(url.includes("?") ? url : `${url}?qualidade=baixa`, { waitUntil: "domcontentloaded" });
    await page.locator("[data-arena-palco]").scrollIntoViewIfNeeded();
    await page.waitForFunction(() => window.lsArena && window.lsArena.roda.length && window.lsArena.roda.every((m) => m.montada), null, { timeout: 240000 });
    const porVaga = () => page.evaluate(() => {
      const a = window.lsArena;
      const saida = {};
      Object.values(a.vagas).forEach((v) => { saida[v.id] = v.maquinas.filter((m) => m.gltf || m.carregando).map((m) => m.dados.nome); });
      return saida;
    });
    const inicio = await porVaga();
    Object.entries(inicio).forEach(([id, carregados]) => confere(carregados.length <= 1, `na abertura, a vaga ${id} tem ${carregados.length} modelos carregados: ${carregados}`));
    const vaga = await page.evaluate(() => {
      const a = window.lsArena;
      const v = Object.values(a.vagas).find((x) => x.maquinas.length > 1);
      if (!v) return null;
      a.selecionar(a.naVaga[v.id]);
      return { id: v.id, antes: a.naVaga[v.id].dados.nome };
    });
    if (vaga) {
      await page.click('[data-arena-troca] [data-troca-passo="1"]');
      await page.waitForFunction((id) => window.lsArena.naVaga[id].montada, vaga.id, { timeout: 240000 });
      const depois = await page.evaluate((v) => {
        const a = window.lsArena;
        const velha = a.vagas[v.id].maquinas.find((m) => m.dados.nome === v.antes);
        return { agora: a.naVaga[v.id].dados.nome, velhaDescartada: !velha.gltf && !velha.montada && !velha.grupo.visible, naRoda: a.roda.includes(a.naVaga[v.id]) };
      }, vaga);
      confere(depois.agora !== vaga.antes, `a seta do trocador não trocou o modelo da vaga ${vaga.id}`);
      confere(depois.velhaDescartada, `o ${vaga.antes} não foi descartado depois da troca`);
      confere(depois.naRoda, "o modelo novo não entrou no lugar da roda");
      const agora = await porVaga();
      Object.entries(agora).forEach(([id, carregados]) => confere(carregados.length <= 1, `depois da troca, a vaga ${id} tem ${carregados.length} modelos carregados: ${carregados}`));
    } else {
      problemas.push("nenhuma vaga com mais de um modelo (os brinquedões 2, 3 e 4 deviam se revezar)");
    }
    // nenhum raio por quadro: na arena e no passeio
    const raios = await page.evaluate(() => {
      const a = window.lsArena;
      const R = a.T.Raycaster.prototype;
      let n = 0;
      const originais = {};
      for (const nome of ["intersectObject", "intersectObjects"]) {
        originais[nome] = R[nome];
        R[nome] = function (...args) { n++; return originais[nome].apply(this, args); };
      }
      a.visivel = false;
      for (let i = 0; i < 15; i++) a.quadro(1 / 60);
      const naArena = n;
      a.selecionar(a.roda.find((m) => m.grande));
      a.entrarPasseio();
      n = 0;
      for (let i = 0; i < 15; i++) a.quadro(1 / 60);
      const noPasseio = n;
      for (const nome of Object.keys(originais)) R[nome] = originais[nome];
      return { naArena, noPasseio };
    });
    confere(raios.naArena === 0, `${raios.naArena} raios em 15 quadros da arena`);
    confere(raios.noPasseio === 0, `${raios.noPasseio} raios em 15 quadros do passeio`);
    confere(!erros.length, `erros na página: ${erros.slice(0, 3).join(" | ")}`);
  } finally {
    await browser.close();
  }
  if (problemas.length) {
    console.log(problemas.join("\n"));
    process.exit(1);
  }
  console.log("ok: um modelo carregado por categoria, a troca descarta o de antes, nenhum raio por quadro");
})().catch((erro) => {
  console.log(String(erro && erro.stack || erro));
  process.exit(1);
});
