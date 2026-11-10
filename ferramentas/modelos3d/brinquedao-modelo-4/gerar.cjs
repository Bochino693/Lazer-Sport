// Gera o .glb: abre o index.html (que roda o montar.js) num Chromium sem tela,
// salva as vistas de conferência (v-*.jpg) e o brinquedao-modelo-4.glb.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb]
//   npx gltfpack -i brinquedao-modelo-4.glb -o ../../../core/static/site/arena/modelos/brinquedao-modelo-4.glb -kn -km -ke
// A porta muda com PORTA=8791 (se a 8790 estiver ocupada).
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text()); });
  await page.goto(`http://localhost:${process.env.PORTA || 8790}/index.html`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 180000 });
  console.log("medidas (L, A, P) em m:", await page.evaluate(() => window.medidas), "triângulos:", await page.evaluate(() => window.triangulos));
  console.log("centro (o .3ds em metros -> o objeto; M4 em core/static/site/arena/caminhos.js):", await page.evaluate(() => window.centro));
  const salvar = (nome, url) => fs.writeFileSync(nome, Buffer.from(url.split(",")[1], "base64"));
  const c = await page.evaluate(() => window.centro);
  // um ponto do .3ds (mm) no objeto (m)
  const do3ds = (x, y, z) => [x / 1000 - c.x, z / 1000 - c.chao, -y / 1000 - c.z];
  // [posição da câmera, alvo, abertura vertical]: "projeto" é de onde a
  // fábrica fez o render em perspectiva (da frente e da direita, perto do tobogã)
  const vistas = {
    projeto: [do3ds(21200, -1500, 1450), do3ds(12500, 5600, 1800), 70],
    esq34: [do3ds(-1500, -4500, 4200), do3ds(6500, 5500, 1500), 50],
    dir34: [do3ds(24500, -5500, 5000), do3ds(14500, 4500, 1300), 50],
    tras: [do3ds(10000, 20000, 6000), do3ds(10000, 5000, 1500), 55],
    dentro: [do3ds(2600, 7100, 3150), do3ds(9000, 7100, 3000), 75],
    baby: [do3ds(15100, -1500, 1500), do3ds(15100, 3600, 900), 55],
  };
  for (const [nome, [p, alvo, fov]] of Object.entries(vistas)) {
    salvar(`v-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, fov), [p, alvo, fov]));
  }
  // sem perspectiva, para comparar com a planta e com a vista de frente da fábrica
  salvar("v-cima.jpg", await page.evaluate(() => window.verOrto("cima", 22)));
  salvar("v-frente.jpg", await page.evaluate(() => window.verOrto("frente", 22)));
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync("brinquedao-modelo-4.glb", Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync("brinquedao-modelo-4.glb").size, "bytes");
  }
  await browser.close();
})();
