// Gera o .glb e as fotos: abre o index.html (que roda o montar.js) num Chromium sem tela.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb] [fotos]
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  await page.goto("http://localhost:8790/index.html");
  await page.waitForFunction(() => window.pronto, null, { timeout: 180000 });
  console.log("medidas (L, A, P) em m:", await page.evaluate(() => window.medidas), "triângulos:", await page.evaluate(() => window.triangulos));
  const salvar = (nome, url) => fs.writeFileSync(nome, Buffer.from(url.split(",")[1], "base64"));
  const vistas = { frente: [6, 22, 44], esq: [-38, 24, 30], dir: [40, 24, 30], cima: [0, 62, 6], costas: [-10, 22, -42], dentro: [9, 2.2, 1] };
  for (const [nome, p] of Object.entries(vistas)) {
    const alvo = nome === "dentro" ? [12, 1.2, -6] : [0, 0, 0];
    salvar(`v-${nome}.jpg`, await page.evaluate(([p, alvo]) => window.ver(...p, alvo), [p, alvo]));
  }
  if (process.argv.includes("fotos")) {
    // as fotos do cadastro: fundo claro, como as do catálogo
    const fotos = { "frente": [0, 25, 52], "lado_direito": [39, 22, 35], "lado_esquerdo": [-39, 22, 35], "planta": [0, 54, 0.5] };
    for (const [nome, p] of Object.entries(fotos)) salvar(`foto-${nome}.jpg`, await page.evaluate((p) => window.ver(...p, [0, 0, 0], "#f2f5fa"), p));
  }
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync("espaco-esportivo-modelo-1.glb", Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync("espaco-esportivo-modelo-1.glb").size, "bytes");
  }
  await browser.close();
})();
