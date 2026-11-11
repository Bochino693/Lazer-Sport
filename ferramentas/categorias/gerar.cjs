// As fotos das categorias: abre o index.html (que roda o cenas.js) num Chromium
// sem tela e grava, para cada categoria, a foto no lugar (render/<chave>.png),
// a máscara dos brinquedos (<chave>-mascara.png) e o peso do desfoque
// (<chave>-peso.png). Depois o compor.py desfoca o lugar e grava o .webp:
//
//   node ferramentas/categorias/gerar.cjs                 (todas)
//   node ferramentas/categorias/gerar.cjs fliperama kids  (só estas)
//   node ferramentas/categorias/gerar.cjs capas           (as capas dos produtos: "capa:<chave>")
//   node ferramentas/categorias/gerar.cjs capa:strike-kids (só esta capa)
//   python ferramentas/categorias/compor.py               (os .webp em core/static/site/categorias/
//                                                          e as capas em core/static/site/arena/modelos/<chave>/capa.webp)
//
// UM .GLB FOI REFEITO? Refaça só as fotos que usam ele (as das categorias e as
// capas), já com o .webp no lugar (--compor roda o compor.py no fim):
//
//   node ferramentas/categorias/gerar.cjs --glb basquete-street-quadrinhos --glb air-game-kids-alienigenas --compor
//
// PREVIA=1 renderiza na metade do tamanho (para acertar o ângulo depressa).
// PYTHON=<caminho> escolhe o Python do --compor (o padrão é "python3").
//
// Precisa do Playwright com o Chromium (npm install playwright; npx playwright
// install chromium). O three.js e as peças vêm do próprio repositório: este
// script serve a raiz do projeto num endereço local (PORTA=8795 por padrão).
const http = require("http");
const { execFileSync } = require("child_process");
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
  // os pedidos: as chaves, "capas", "--glb <nome>" (as cenas que usam aquele .glb) e "--compor"
  const argumentos = process.argv.slice(2);
  const compor = argumentos.includes("--compor");
  const pedidas = [];
  const glbs = [];
  for (let i = 0; i < argumentos.length; i++) {
    if (argumentos[i] === "--glb") glbs.push(argumentos[++i]);
    else if (argumentos[i] !== "--compor") pedidas.push(argumentos[i]);
  }
  const capas = await page.evaluate(() => window.CAPAS);
  const todas = await page.evaluate(() => window.TODAS);
  if (glbs.length) {
    const usam = await page.evaluate((nomes) => window.cenasComGlb(...nomes), glbs);
    console.log(`as fotos com ${glbs.join(", ")}: ${usam.join(", ") || "nenhuma"}`);
    pedidas.push(...usam);
  }
  const chaves = pedidas.length || glbs.length ? pedidas.flatMap((p) => (p === "capas" ? capas : [p])) : await page.evaluate(() => window.CENAS);
  // "chave@giro,altura,lente" experimenta outro ângulo (e grava com esse nome)
  const lista = {};
  for (const pedido of chaves) {
    const inicio = Date.now();
    const [chave, angulo] = pedido.split("@");
    const [giro, altura, lente] = (angulo || "").split(",").map(Number);
    const ajustes = angulo ? { giro, altura, lente: lente || 26 } : {};
    if (process.env.PREVIA) ajustes.previa = true;
    // a foto, a máscara dos brinquedos e o peso do desfoque (as duas últimas só com lugar)
    const imagens = await page.evaluate(([c, a]) => window.renderizar(c, a), [chave, ajustes]);
    const nome = pedido.replace(":", "_");
    for (const [tipo, url] of Object.entries(imagens)) {
      const sufixo = tipo === "cor" ? "" : `-${tipo}`;
      fs.writeFileSync(path.join(SAIDA, `${nome}${sufixo}.png`), Buffer.from(url.split(",")[1], "base64"));
    }
    const maquinas = await page.evaluate((c) => (window.MAQUINAS_DAS_CENAS || {})[c] || [], chave);
    console.log(`${pedido}: ${((Date.now() - inicio) / 1000).toFixed(1)} s -- ${maquinas.join(", ")}`);
    lista[pedido] = maquinas;
  }
  // as máquinas de cada foto (o LEIA-ME e os testes conferem: só itens da categoria no catálogo)
  // (as das capas, à parte: maquinas-das-capas.json, pela chave do produto)
  for (const [arquivo, prefixo] of [["maquinas-das-fotos.json", ""], ["maquinas-das-capas.json", "capa:"]]) {
    const arquivoLista = path.join(__dirname, arquivo);
    const antes = fs.existsSync(arquivoLista) ? JSON.parse(fs.readFileSync(arquivoLista, "utf8")) : {};
    let mudou = false;
    for (const [chave, maquinas] of Object.entries(lista)) {
      if (chave.includes("@")) continue;
      if (prefixo ? chave.startsWith(prefixo) : !chave.includes(":") && todas.includes(chave)) {
        antes[chave.slice(prefixo.length)] = maquinas;
        mudou = true;
      }
    }
    if (mudou) fs.writeFileSync(arquivoLista, JSON.stringify(antes, null, 1) + "\n");
  }
  await browser.close();
  servidor.close();
  // o .webp de cada uma (o lugar desfocado, os brinquedos nítidos): as categorias e as capas
  if (compor && chaves.length) {
    const nomes = chaves.filter((c) => !c.includes("@")).map((c) => c.replace(":", "_"));
    execFileSync(process.env.PYTHON || "python3", [path.join(__dirname, "compor.py"), ...nomes], { stdio: "inherit" });
  }
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
