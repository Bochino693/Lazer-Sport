// node gerar.cjs <maquina> [glb]  -> vistas v-<maquina>-*.jpg e <maquina>.glb
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const maquina = process.argv[2];
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1000, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text()); });
  await page.goto(`http://localhost:8790/index.html?maquina=${maquina}`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 120000 });
  console.log(maquina, "medidas (L, A, P):", await page.evaluate(() => window.medidas), "triângulos:", await page.evaluate(() => window.triangulos));
  const vistas = { frente: [0, 0.12], dir34: [0.75, 0.22], esq34: [-0.75, 0.22], lado_direito: [Math.PI / 2, 0.1], lado_esquerdo: [-Math.PI / 2, 0.1], verso: [Math.PI, 0.12], cima: [0.5, 1.0] };
  for (const [nome, [g, i]] of Object.entries(vistas)) {
    const url = await page.evaluate(([g, i]) => window.ver(g, i), [g, i]);
    fs.writeFileSync(`v-${maquina}-${nome}.jpg`, Buffer.from(url.split(",")[1], "base64"));
  }
  if (process.argv[3] === "glb") {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync(`${maquina}.glb`, Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync(`${maquina}.glb`).size, "bytes");
  }
  await browser.close();
})();
