// As fotos das categorias: abre o index.html (que roda o cenas.js) num Chromium
// sem tela e grava, para cada categoria, a foto no lugar (render/<chave>.png),
// a máscara dos brinquedos (<chave>-mascara.png) e o peso do desfoque
// (<chave>-peso.png). Depois o compor.py desfoca o lugar e grava o .webp:
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
  const lista = {};
  for (const pedido of chaves) {
    const inicio = Date.now();
    const [chave, angulo] = pedido.split("@");
    const [giro, altura, lente] = (angulo || "").split(",").map(Number);
    const ajustes = angulo ? { giro, altura, lente: lente || 26 } : {};
    // a foto, a máscara dos brinquedos e o peso do desfoque (as duas últimas só com lugar)
    const imagens = await page.evaluate(([c, a]) => window.renderizar(c, a), [chave, ajustes]);
    const nome = pedido.replace(":", "_");
    for (const [tipo, url] of Object.entries(imagens)) {
      const sufixo = tipo === "cor" ? "" : `-${tipo}`;
      fs.writeFileSync(path.join(SAIDA, `${nome}${sufixo}.png`), Buffer.from(url.split(",")[1], "base64"));
    }
    const maquinas = await page.evaluate((c) => (window.MAQUINAS_DAS_CENAS || {})[c] || [], chave);
    console.log(`${pedido}: ${((Date.now() - inicio) / 1000).toFixed(1)} s -- ${maquinas.join(", ")}`);
    lista[chave] = maquinas;
  }
  // as máquinas de cada foto (o LEIA-ME e os testes conferem: só itens do catálogo)
  fs.writeFileSync(path.join(SAIDA, "maquinas-das-fotos.json"), JSON.stringify(lista, null, 1));
  await browser.close();
  servidor.close();
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
