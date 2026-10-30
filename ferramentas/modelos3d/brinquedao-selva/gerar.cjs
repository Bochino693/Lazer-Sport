// Gera o .glb: abre o index.html (que roda o montar.js) num Chromium sem tela,
// salva vistas de conferência (v-*.jpg) e o brinquedao-selva-11m.glb.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs glb
//   npx gltfpack -i brinquedao-selva-11m.glb -o ../../../core/static/site/arena/modelos/brinquedao-selva-11m.glb -kn -km
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1200, height: 700 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  await page.goto("http://localhost:8790/index.html");
  await page.waitForFunction(() => window.pronto, null, { timeout: 120000 });
  console.log("medidas (L, A, P) em m:", await page.evaluate(() => window.medidas), "triângulos:", await page.evaluate(() => window.triangulos));
  const vistas = { frente: [0, 3, 14], esq34: [-9, 5, 10], dir34: [9, 5, 10], costas: [0, 4, -14], cima: [0, 16, 3], baixo: [3, 0.4, 7] };
  for (const [nome, p] of Object.entries(vistas)) {
    const url = await page.evaluate((p) => window.ver(...p), p);
    fs.writeFileSync(`v-${nome}.jpg`, Buffer.from(url.split(",")[1], "base64"));
  }
  if (process.argv[2] === "glb") {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync("brinquedao-selva-11m.glb", Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync("brinquedao-selva-11m.glb").size, "bytes");
  }
  await browser.close();
})();
