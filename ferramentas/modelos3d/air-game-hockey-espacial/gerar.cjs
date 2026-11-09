// Gera o .glb, as fotos e o pecas.json: abre o index.html (que roda o montar.js) num Chromium sem tela.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb] [fotos]
//   npx gltfpack -i air-game-hockey-espacial.glb -o ../../../core/static/site/arena/modelos/air-game-hockey-espacial.glb -kn -km -ke
// Antes: python3 recortar_adesivos.py (as peças e o formas.json, da folha).
// Sempre: as vistas de conferência (v-*.jpg) e o pecas.json (o tamanho de
// cada adesivo no 3D e onde ele vai). "fotos" grava as foto-*.jpg (a vista
// inteira, para conferir) e as .webp do cadastro, já recortadas no objeto, na
// pasta do modelo no static.
// PORTA=8791 node gerar.cjs ...  se a 8790 estiver ocupada.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const NOME = "air-game-hockey-espacial";
const FOTOS = path.join(__dirname, `../../../core/static/site/arena/modelos/${NOME}`);
(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text()); });
  await page.goto(`http://localhost:${process.env.PORTA || 8790}/index.html`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 180000 });
  const info = await page.evaluate(() => ({ medidas: window.medidas, triangulos: window.triangulos, pecas: window.pecas, avisos: window.avisos, escala: window.escala }));
  console.log("medidas (L, A, P) em m:", info.medidas, "triângulos:", info.triangulos);
  console.log("a escala da folha e o que sai dela:", JSON.stringify(info.escala));
  for (const aviso of info.avisos) console.log("AVISO:", aviso);
  fs.writeFileSync(path.join(__dirname, "pecas.json"), JSON.stringify(info.pecas, null, 1) + "\n");
  const salvar = (arquivo, url) => fs.writeFileSync(arquivo, Buffer.from(url.split(",")[1], "base64"));
  // as vistas de conferência: [posição, alvo, abertura]
  const vistas = {
    frente34: [[2.2, 1.9, 3.0], [0, 0.6, 0], 34],
    esquerda: [[-3.6, 1.0, 0.2], [0, 0.55, 0], 34],
    direita: [[3.6, 1.0, -0.2], [0, 0.55, 0], 34],
    cabeceira: [[0.15, 1.1, 3.3], [0, 0.5, 0], 34],
    tras: [[-0.15, 1.1, -3.3], [0, 0.5, 0], 34],
    baixo: [[-2.2, 0.35, 1.2], [0, 0.4, 0], 40],
    perto: [[0.9, 1.45, 1.3], [0, 0.82, 0.1], 40],
  };
  for (const [nome, [p, alvo, fov]] of Object.entries(vistas)) {
    salvar(`v-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, "#0b1a3a", fov), [p, alvo, fov]));
  }
  salvar("v-cima.jpg", await page.evaluate(() => window.verCima(2.6)));
  if (process.argv.includes("fotos")) {
    // as fotos do cadastro: fundo claro, como as do catálogo; a de cima é sem perspectiva
    fs.mkdirSync(FOTOS, { recursive: true });
    const fotos = {
      frente: [[2.3, 1.85, 2.9], [0, 0.55, 0]],
      lado_esquerdo: [[-3.3, 1.35, 1.1], [0, 0.55, 0]],
      lado_direito: [[3.3, 1.35, -1.1], [0, 0.55, 0]],
      verso: [[-1.6, 1.7, -3.0], [0, 0.55, 0]],
    };
    for (const [nome, [p, alvo]] of Object.entries(fotos)) {
      salvar(`foto-${nome}.jpg`, await page.evaluate(([p, alvo]) => window.ver(...p, alvo, "#f2f5fa", 34), [p, alvo]));
      salvar(path.join(FOTOS, `${nome}.webp`), await page.evaluate(() => window.recortar()));
    }
    salvar("foto-tampo.jpg", await page.evaluate(() => window.verCima(2.6, "#f2f5fa")));
    salvar(path.join(FOTOS, "tampo.webp"), await page.evaluate(() => window.recortar(0.04)));
    console.log("fotos em", FOTOS);
  }
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync(`${NOME}.glb`, Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync(`${NOME}.glb`).size, "bytes");
  }
  await browser.close();
})();
