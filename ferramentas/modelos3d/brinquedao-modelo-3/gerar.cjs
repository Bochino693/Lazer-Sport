// Gera o .glb e as fotos: abre o index.html (que roda o montar.js) num Chromium sem tela.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb] [fotos]
//   npx gltfpack -i brinquedao-modelo-3.glb -o ../../../core/static/site/arena/modelos/brinquedao-modelo-3.glb -kn -km -ke
// "fotos" grava as foto-*.jpg (a vista inteira, para conferir) e as .webp do
// cadastro, já recortadas no objeto, na pasta do modelo no static.
// PORTA=8791 node gerar.cjs ...  se a 8790 estiver ocupada.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const FOTOS = path.join(__dirname, "../../../core/static/site/arena/modelos/brinquedao-modelo-3");
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text()); });
  await page.goto(`http://localhost:${process.env.PORTA || 8790}/index.html`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 180000 });
  const info = await page.evaluate(() => ({ medidas: window.medidas, triangulos: window.triangulos, centro: window.centro }));
  console.log("medidas (L, A, P) em m:", info.medidas, "triângulos:", info.triangulos);
  console.log("deslocamento (x, chão, z) das coordenadas de trabalho em m, para o passeio (M3 em core/static/site/arena/caminhos.js):", info.centro);
  const salvar = (arquivo, url) => fs.writeFileSync(arquivo, Buffer.from(url.split(",")[1], "base64"));
  // um ponto de trabalho (mm) no objeto final
  const P = (x, y, z) => page.evaluate(([x, y, z]) => window.noObjeto(x, y, z), [x, y, z]);
  // as vistas de conferência: [posição, alvo, abertura]
  const vistas = {
    frente: [[0, 2.0, 17.5], [0, 1.75, 0], 34],
    esq34: [[-10.5, 5.5, 11], [-0.5, 1.5, 0], 34],
    dir34: [[10.5, 5, 10.5], [1, 1.4, 0], 34],
    costas: [[1, 4.5, -15.5], [0, 1.6, 0], 34],
    // de perto: o tobogã e a piscina, a torre e o andar de cima por dentro
    toboga: [[7.4, 2.5, 3.4], await P(9000, 4200, 1150), 40],
    piscina: [[4.2, 4.6, 0.6], await P(9000, 4200, 600), 45],
    torre: [[-4.2, 3.0, 6.0], await P(500, 900, 1800), 40],
    andar: [[-0.5, 6.6, 4.2], await P(5000, 4300, 2100), 42],
    dentro: [await P(500, 3650, 2750), await P(6000, 3900, 2250), 72],
  };
  for (const [nome, [p, alvo, fov]] of Object.entries(vistas)) {
    salvar(`v-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, "#0b1a3a", fov), [p, alvo, fov]));
  }
  salvar("v-cima.jpg", await page.evaluate(() => window.verCima(12)));
  if (process.argv.includes("fotos")) {
    // as fotos do cadastro: fundo claro, como as do catálogo; a planta é a
    // vista de cima sem perspectiva
    fs.mkdirSync(FOTOS, { recursive: true });
    const fotos = {
      frente: [[7.8, 4.4, 11.2], [0.4, 1.5, 0]],
      lado_esquerdo: [[-11, 4.2, 7.2], [-0.8, 1.5, 0]],
      lado_direito: [[11.6, 4.0, 4.4], [1.2, 1.4, 0]],
    };
    for (const [nome, [p, alvo]] of Object.entries(fotos)) {
      salvar(`foto-${nome}.jpg`, await page.evaluate(([p, alvo]) => window.ver(...p, alvo, "#f2f5fa", 34), [p, alvo]));
      salvar(path.join(FOTOS, `${nome}.webp`), await page.evaluate(() => window.recortar()));
    }
    salvar("foto-planta.jpg", await page.evaluate(() => window.verCima(11.4, "#f2f5fa")));
    salvar(path.join(FOTOS, "planta.webp"), await page.evaluate(() => window.recortar(0.04)));
    console.log("fotos em", FOTOS);
  }
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync("brinquedao-modelo-3.glb", Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync("brinquedao-modelo-3.glb").size, "bytes");
  }
  await browser.close();
})();
