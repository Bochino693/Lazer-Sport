// As fotos das categorias: abre o index.html (que roda o cenas.js) num Chromium
// sem tela e grava, para cada categoria, o render com o fundo transparente em
// render/<chave>.png. Depois o compor.py põe o fundo e faz o corte 4:3:
//
//   node ferramentas/categorias/gerar.cjs                 (todas)
//   node ferramentas/categorias/gerar.cjs fliperama kids  (só estas)
//   python ferramentas/categorias/compor.py               (os .webp em core/static/site/categorias/)
//
// Precisa do Playwright com o Chromium (npm install playwright; npx playwright
// install chromium). O three.js e as peças vêm do próprio repositório: este
// script serve a raiz do projeto num endereço local (PORTA=8795 por padrão).
const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const RAIZ = path.resolve(__dirname, "..", "..");
const SAIDA = path.join(__dirname, "render");
const PORTA = Number(process.env.PORTA || 8795);
const TIPOS = { ".html": "text/html", ".js": "text/javascript", ".glb": "model/gltf-binary", ".webp": "image/webp", ".png": "image/png", ".json": "application/json" };

const servidor = http.createServer((req, res) => {
  const caminho = path.normalize(path.join(RAIZ, decodeURIComponent(req.url.split("?")[0])));
  if (!caminho.startsWith(RAIZ) || !fs.existsSync(caminho) || fs.statSync(caminho).isDirectory()) {
    res.writeHead(404);
    return res.end();
  }
  res.writeHead(200, { "Content-Type": TIPOS[path.extname(caminho)] || "application/octet-stream" });
  fs.createReadStream(caminho).pipe(res);
});

(async () => {
  await new Promise((ok) => servidor.listen(PORTA, "127.0.0.1", ok));
  fs.mkdirSync(SAIDA, { recursive: true });
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => m.type() === "error" && console.log("console:", m.text()));
  await page.goto(`http://127.0.0.1:${PORTA}/ferramentas/categorias/index.html`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 120000 });
  const pedidas = process.argv.slice(2);
  const chaves = pedidas.length ? pedidas : await page.evaluate(() => window.CENAS);
  // "chave@giro,altura,lente" experimenta outro ângulo (e grava com esse nome)
  for (const pedido of chaves) {
    const inicio = Date.now();
    const [chave, angulo] = pedido.split("@");
    const [giro, altura, lente] = (angulo || "").split(",").map(Number);
    const ajustes = angulo ? { giro, altura, lente: lente || 26 } : {};
    const url = await page.evaluate(([c, a]) => window.renderizar(c, a), [chave, ajustes]);
    fs.writeFileSync(path.join(SAIDA, `${pedido.replace(":", "_")}.png`), Buffer.from(url.split(",")[1], "base64"));
    console.log(`${pedido}: ${((Date.now() - inicio) / 1000).toFixed(1)} s`);
  }
  await browser.close();
  servidor.close();
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
