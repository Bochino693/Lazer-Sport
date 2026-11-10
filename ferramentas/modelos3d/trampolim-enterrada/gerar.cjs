// Gera o .glb e as fotos: abre o index.html (que roda o montar.js) num Chromium sem tela.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb] [fotos] [espuma]
// "espuma" monta a variante (a cama do meio é a piscina de cubos) e grava
// trampolim-enterrada-espuma.glb e as vistas dela (v-espuma-*.jpg).
// PORTA=8791 node gerar.cjs ...  se a 8790 estiver ocupada.
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const espuma = process.argv.includes("espuma");
  const nome = espuma ? "trampolim-enterrada-espuma" : "trampolim-enterrada";
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  await page.goto(`http://localhost:${process.env.PORTA || 8790}/index.html${espuma ? "?variante=espuma" : ""}`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 120000 });
  const info = await page.evaluate(() => ({ medidas: window.medidas, triangulos: window.triangulos, centro: window.centro, aro: window.aro }));
  console.log("medidas (L, A, P) em m:", info.medidas, "triângulos:", info.triangulos);
  console.log("deslocamento (x, chão, z) do .3ds em m, para o passeio (TE em core/static/site/arena/caminhos.js):", info.centro, "aro:", info.aro);
  const salvar = (arquivo, url) => fs.writeFileSync(arquivo, Buffer.from(url.split(",")[1], "base64"));
  // as vistas de conferência: de frente 3/4 (o lado da escada), de frente, de
  // cima, o lado da cesta, a pista vista de cima da escada e as costas
  const vistas = {
    frente34: [[6.2, 3.4, 7.4]], frente: [[0, 2.0, 10.5]], cima: [[0, 40, 0.2], [0, 0, 0], "#0b1a3a", 9, false],
    cesta: [[-6.4, 3.2, 5.6], [-1.6, 1.6, 0]], pista: [[5.4, 2.7, 0.3], [-2.4, 2.0, 0], "#0b1a3a", 50],
    costas: [[-4.5, 3.6, -8]],
  };
  for (const [vista, [p, alvo, fundo, fov, sombra]] of Object.entries(vistas)) {
    salvar(`v-${espuma ? "espuma-" : ""}${vista}.jpg`, await page.evaluate(([p, ...resto]) => window.ver(...p, ...resto), [p, alvo, fundo, fov, sombra]));
  }
  if (process.argv.includes("fotos")) {
    // as fotos do cadastro: fundo claro, como as do catálogo
    // (a planta de bem longe, com a lente fechada: quase sem perspectiva)
    const fotos = {
      frente: [[6.6, 3.5, 8.0]], lado_esquerdo: [[-7.6, 3.5, 8.0], [-0.6, 1.3, 0]], lado_direito: [[9.6, 3.3, 2.6]], planta: [[0, 40, 0.2], [0, 0, 0], 9, false],
    };
    for (const [foto, [p, alvo = [0, 1.35, 0], fov, sombra]] of Object.entries(fotos)) {
      salvar(`foto-${espuma ? "espuma-" : ""}${foto}.jpg`, await page.evaluate(([p, alvo, fov, sombra]) => window.ver(...p, alvo, "#f2f5fa", fov, sombra), [p, alvo, fov, sombra]));
    }
  }
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync(`${nome}.glb`, Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync(`${nome}.glb`).size, "bytes");
  }
  await browser.close();
})();
