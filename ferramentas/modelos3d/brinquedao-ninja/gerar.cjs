// Gera o .glb: abre o index.html (que roda o montar.js) num Chromium sem tela,
// salva as vistas de conferência (v-*.jpg) e o brinquedao-ninja.glb.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb] [fotos]
//   npx gltfpack -i brinquedao-ninja.glb -o ../../../core/static/site/arena/modelos/brinquedao-ninja.glb -kn -km -ke
// A porta muda com PORTA=8791 (se a 8790 estiver ocupada).
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 867 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text()); });
  await page.goto(`http://localhost:${process.env.PORTA || 8790}/index.html`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 180000 });
  console.log("medidas (L, A, P) em m:", await page.evaluate(() => window.medidas), "triângulos:", await page.evaluate(() => window.triangulos));
  console.log("centro (o .3ds em metros -> o objeto):", await page.evaluate(() => window.centro));
  const salvar = (nome, url) => fs.writeFileSync(nome, Buffer.from(url.split(",")[1], "base64"));
  // "projeto" é o ponto de vista da imagem da fábrica, achado pelas colunas do
  // .3ds e onde elas caem na imagem (erro de ~5 px): olho a 1,43 m, a 2,9 m da
  // frente da faixa, virado 21° para a direita, lente de 40° (na vertical)
  const c = await page.evaluate(() => window.centro);
  const do3ds = (x, y, z) => [x / 1000 - c.x, z / 1000 - c.chao, -y / 1000 - c.z];
  const psi = (20.9 * Math.PI) / 180, phi = (2.1 * Math.PI) / 180;
  const olho = [2696, -2865, 1428];
  const alvoProjeto = olho.map((v, i) => v + 5000 * [Math.sin(psi) * Math.cos(phi), Math.cos(psi) * Math.cos(phi), Math.sin(phi)][i]);
  // [posição da câmera, alvo, abertura vertical]
  const vistas = {
    projeto: [do3ds(...olho), do3ds(...alvoProjeto), 39.9],
    frente: [[0, 2.2, 15.5], [0, 1.5, 0], 50],
    esq34: [[-11, 5, 9], [-1, 1.4, 0], 45],
    dir34: [[10, 5, 9.5], [1.5, 1.2, 0], 45],
    costas: [[1, 4, -15], [0, 1.5, 0], 50],
    dentro: [[-4.3, 2.85, -0.73], [2, 2.75, -0.73], 70],
  };
  for (const [nome, [p, alvo, fov]] of Object.entries(vistas)) {
    salvar(`v-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, fov), [p, alvo, fov]));
  }
  salvar("v-cima.jpg", await page.evaluate(() => window.verCima()));
  if (process.argv.includes("fotos")) {
    // as fotos do cadastro: fundo claro, como as do catálogo
    const fotos = { frente: [[-6.5, 3.6, 13], [0.3, 1.3, 0], 50], lado_direito: [[11, 4.5, 8.5], [1.5, 1.2, 0], 45], lado_esquerdo: [[-11, 4.5, 8.5], [-1.5, 1.2, 0], 45] };
    for (const [nome, [p, alvo, fov]] of Object.entries(fotos)) {
      salvar(`foto-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, fov, "#f2f5fa"), [p, alvo, fov]));
    }
  }
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync("brinquedao-ninja.glb", Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync("brinquedao-ninja.glb").size, "bytes");
  }
  await browser.close();
})();
