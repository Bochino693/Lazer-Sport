// Gera as artes de capa dos kits eletrônicos (LEIA-ME-V10, seções 105 e 107).
//
//   NODE_PATH=<node_modules com playwright> node ferramentas/kits/gerar.js [pasta-de-saida]
//
// Serve o repositório por HTTP (módulos e texturas não carregam de file://),
// abre ferramentas/kits/artes.html para cada kit, renderiza a cena 3D em
// 2400 x 2400 (deviceScaleFactor 2: bordas lisas) e grava <pasta>/<chave>.png.
// A conversão para .webp 1200 x 1200 (core/static/site/kits/) é à parte:
//   python -I ferramentas/kits/para_webp.py <pasta>
const fs = require("fs");
const http = require("http");
const path = require("path");
const { chromium } = require("playwright");

const KITS = ["kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot"];
const RAIZ = path.resolve(__dirname, "..", "..");
const saida = path.resolve(process.argv[2] || __dirname);
const TIPOS = { ".html": "text/html", ".js": "text/javascript", ".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".woff2": "font/woff2", ".css": "text/css" };

const servidor = http.createServer((req, res) => {
  const caminho = path.normalize(path.join(RAIZ, decodeURIComponent(req.url.split("?")[0])));
  if (!caminho.startsWith(RAIZ) || !fs.existsSync(caminho) || fs.statSync(caminho).isDirectory()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { "Content-Type": TIPOS[path.extname(caminho)] || "application/octet-stream" });
  fs.createReadStream(caminho).pipe(res);
});

servidor.listen(0, "127.0.0.1", async () => {
  const porta = servidor.address().port;
  const navegador = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
  const p = await navegador.newPage({ viewport: { width: 1200, height: 1200 }, deviceScaleFactor: 2 });
  p.on("pageerror", (e) => console.error("erro na página:", e.message));
  for (const chave of KITS) {
    await p.goto(`http://127.0.0.1:${porta}/ferramentas/kits/artes.html?kit=${chave}`, { waitUntil: "load" });
    await p.evaluate(() => window.PRONTO);
    await p.waitForTimeout(400);
    const arquivo = path.join(saida, `${chave}.png`);
    await p.locator("#arte").screenshot({ path: arquivo });
    console.log(arquivo);
  }
  await navegador.close();
  servidor.close();
});
