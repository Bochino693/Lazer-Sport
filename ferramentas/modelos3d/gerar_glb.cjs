// Gera o .glb de uma máquina de adesivo (LEIA-ME V10, seção 88): abre o
// <modelo>/index.html (que roda o montar.js com o three.js do site,
// core/static/vendor/three) num Chromium sem tela, confere as medidas, grava as
// vistas de conferência (<modelo>/v-*.jpg, fora do repositório), exporta o .glb
// e passa o gltfpack (a malha quantizada; os nomes dos materiais e das malhas
// ficam). NÃO refaz as fotos do cadastro (as .webp da pasta do modelo no static).
//
//   npm install playwright gltfpack        (ou NODE_PATH apontando para eles)
//   node gerar_glb.cjs <modelo> [--arte <nome>] [--saida <arquivo.glb>]
//
//   node gerar_glb.cjs basquete-street-quadrinhos
//   node gerar_glb.cjs air-game-kids-alienigenas
//   node gerar_glb.cjs air-game-kids-alienigenas --arte astronautas --saida air-game-kids-astronautas.glb
//   node gerar_glb.cjs strike-kids
const { chromium } = require("playwright");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { execFileSync } = require("child_process");

const AQUI = __dirname;
const VENDOR = path.join(AQUI, "../../core/static/vendor/three");
const DESTINO = path.join(AQUI, "../../core/static/site/arena/modelos");
const args = process.argv.slice(2);
const modelo = args[0];
const opcao = (nome) => { const i = args.indexOf(nome); return i >= 0 ? args[i + 1] : null; };
const arte = opcao("--arte");
const saida = opcao("--saida") || `${modelo}.glb`;
if (!modelo || !fs.existsSync(path.join(AQUI, modelo, "montar.js"))) {
  console.error("uso: node gerar_glb.cjs <modelo> [--arte <nome>] [--saida <arquivo.glb>]");
  process.exit(1);
}

const TIPOS = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg" };
const servidor = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  const arquivo = url.startsWith("/vendor/three/") ? path.join(VENDOR, url.slice(14)) : path.join(AQUI, url);
  if (!arquivo.startsWith(AQUI) && !arquivo.startsWith(VENDOR)) { res.writeHead(403); res.end(); return; }
  fs.readFile(arquivo, (erro, dados) => {
    if (erro) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "Content-Type": TIPOS[path.extname(arquivo)] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(dados);
  });
});

(async () => {
  await new Promise((ok) => servidor.listen(0, "127.0.0.1", ok));
  const porta = servidor.address().port;
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();
  page.on("pageerror", (e) => console.log("erro na página:", e.message));
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") console.log("console:", m.text()); });
  page.on("requestfailed", (r) => console.log("falhou:", r.url()));
  page.on("response", (r) => { if (r.status() >= 400) console.log("http", r.status(), r.url()); });
  await page.goto(`http://127.0.0.1:${porta}/${modelo}/index.html${arte ? `?arte=${arte}` : ""}`);
  await page.waitForFunction(() => window.pronto, null, { timeout: 300000 });
  const info = await page.evaluate(() => ({ medidas: window.medidas, triangulos: window.triangulos, avisos: window.avisos || [], escala: window.escala, pecas: window.pecas }));
  console.log("medidas (L, A, P) em m:", info.medidas, "triângulos:", info.triangulos);
  if (info.escala) console.log("escala:", JSON.stringify(info.escala));
  for (const aviso of info.avisos) console.log("AVISO:", aviso);
  if (info.pecas && !arte) fs.writeFileSync(path.join(AQUI, modelo, "pecas.json"), JSON.stringify(info.pecas, null, 1) + "\n");
  const vistas = await page.evaluate(() => window.vistasDeConferencia || {});
  const prefixo = arte ? `v-${arte}-` : "v-";
  for (const [nome, [p, alvo, fov]] of Object.entries(vistas)) {
    const url = await page.evaluate(([p, alvo, fov]) => window.ver(...p, alvo, "#0b1a3a", fov), [p, alvo, fov]);
    fs.writeFileSync(path.join(AQUI, modelo, `${prefixo}${nome}.jpg`), Buffer.from(url.split(",")[1], "base64"));
  }
  const b64 = await page.evaluate(() => window.exportar());
  const cru = path.join(AQUI, modelo, saida);
  fs.writeFileSync(cru, Buffer.from(b64, "base64"));
  console.log("glb sem o gltfpack:", fs.statSync(cru).size, "bytes");
  await browser.close();
  servidor.close();
  // o gltfpack: posições quantizadas (KHR_mesh_quantization), os nomes ficam (-kn -km), as texturas como vieram
  const final = path.join(DESTINO, saida);
  let cli;
  try { cli = require.resolve("gltfpack/cli.js"); } catch { cli = null; }
  const comando = cli ? [process.execPath, [cli]] : ["npx", ["gltfpack"]];
  execFileSync(comando[0], [...comando[1], "-i", cru, "-o", final, "-kn", "-km", "-ke"], { stdio: "inherit" });
  console.log("glb:", final, fs.statSync(final).size, "bytes");
})();
