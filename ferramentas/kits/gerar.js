// Gera as artes de capa dos kits eletrônicos (LEIA-ME-V10, seção 105).
//
//   NODE_PATH=<node_modules com playwright> node ferramentas/kits/gerar.js [pasta-de-saida]
//
// Abre ferramentas/kits/artes.html para cada kit, fotografa 1200x1200 em PNG
// e grava <pasta>/<chave>.png (padrão: a pasta do próprio script). A
// conversão para .webp (core/static/site/kits/) é feita à parte com o Pillow:
//   python ferramentas/kits/para_webp.py <pasta>
const path = require("path");
const { chromium } = require("playwright");

const KITS = ["kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot"];
const saida = path.resolve(process.argv[2] || __dirname);
const pagina = "file://" + path.join(__dirname, "artes.html");

(async () => {
  const navegador = await chromium.launch();
  const p = await navegador.newPage({ viewport: { width: 1200, height: 1200 }, deviceScaleFactor: 1 });
  for (const chave of KITS) {
    await p.goto(`${pagina}?kit=${chave}`, { waitUntil: "load" });
    await p.evaluate(() => window.PRONTO);
    await p.waitForTimeout(300);
    const arquivo = path.join(saida, `${chave}.png`);
    await p.locator("#arte").screenshot({ path: arquivo });
    console.log(arquivo);
  }
  await navegador.close();
})();
