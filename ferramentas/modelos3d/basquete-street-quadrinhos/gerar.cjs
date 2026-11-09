// Gera o .glb, as fotos e o pecas.json: abre o index.html (que roda o montar.js) num Chromium sem tela.
//   npm install three@0.169.0 playwright gltfpack
//   python3 -m http.server 8790 --bind 127.0.0.1   (nesta pasta, com o node_modules)
//   node gerar.cjs [glb] [fotos]
//   npx gltfpack -i basquete-street-quadrinhos.glb -o ../../../core/static/site/arena/modelos/basquete-street-quadrinhos.glb -kn -km -ke
// Antes: python3 recortar_adesivos.py (as peças e o formas.json, da folha).
// Sempre: as vistas de conferência (v-*.jpg) e o pecas.json (o tamanho de
// cada adesivo no 3D e onde ele vai). "fotos" grava as foto-*.jpg (a vista
// inteira, para conferir) e as .webp do cadastro, já recortadas no objeto, na
// pasta do modelo no static.
// PORTA=8791 node gerar.cjs ...  se a 8790 estiver ocupada.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const NOME = "basquete-street-quadrinhos";
const FOTOS = path.join(__dirname, `../../../core/static/site/arena/modelos/${NOME}`);
(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("404")) console.log("console:", m.text()); });
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
    frente34: [[3.6, 2.6, 4.6], [0, 1.25, 0], 34],
    esquerda: [[-6.2, 1.5, 0.1], [0, 1.3, 0], 34],
    direita: [[6.2, 1.5, -0.1], [0, 1.3, 0], 34],
    frente: [[0, 1.6, 6.4], [0, 1.3, 0], 34],
    costas: [[-3.0, 2.4, -5.2], [0, 1.3, 0], 34],
    jogador: [[0, 1.55, 2.25], [0, 1.6, -1.0], 55],
    cesta: [[0.5, 1.9, 0.3], [0, 1.95, -1.0], 60],
    alto: [[2.2, 4.6, 2.4], [0, 1.6, -0.2], 40],
  };
  for (const [nome, [p, alvo, fov]] of Object.entries(vistas)) {
    salvar(`v-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, "#0b1a3a", fov), [p, alvo, fov]));
  }
  if (process.argv.includes("fotos")) {
    // as fotos do cadastro: fundo claro, como as do catálogo
    fs.mkdirSync(FOTOS, { recursive: true });
    const fotos = {
      frente: [[3.7, 2.5, 4.9], [0, 1.25, 0], 34],
      lado_esquerdo: [[-6.0, 1.7, 1.6], [0, 1.3, 0], 34],
      lado_direito: [[6.0, 1.7, -1.6], [0, 1.3, 0], 34],
      verso: [[-3.4, 2.4, -5.4], [0, 1.3, 0], 34],
      jogador: [[0.4, 2.1, 6.2], [0, 1.3, -0.4], 36],
    };
    for (const [nome, [p, alvo, fov]] of Object.entries(fotos)) {
      salvar(`foto-${nome}.jpg`, await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, "#f2f5fa", fov), [p, alvo, fov]));
      salvar(path.join(FOTOS, `${nome}.webp`), await page.evaluate(() => window.recortar()));
    }
    console.log("fotos em", FOTOS);
  }
  if (process.argv.includes("glb")) {
    const b64 = await page.evaluate(() => window.exportar());
    fs.writeFileSync(`${NOME}.glb`, Buffer.from(b64, "base64"));
    console.log("glb:", fs.statSync(`${NOME}.glb`).size, "bytes");
  }
  await browser.close();
})();
