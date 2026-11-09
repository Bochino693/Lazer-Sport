/* ======================================================================
   AS CENAS DOS JOGOS DA CASA, fotografadas jogando de verdade.

   As artes do destaque do portal (/jogos/) são cenas reais dos jogos:
   este programa abre cada jogo da casa no navegador (Playwright), joga
   uma partida -- o boliche rola a bola, o tiro acerta os alvos, o boxe
   soca -- e guarda o canvas do jogo, quadro a quadro, em PNG. Depois a
   gente escolhe os momentos bonitos e o gerar.py monta as artes
   (core/static/site/arena/capas/topo/gerar.py).

   Só durante a foto, e só no navegador desta ferramenta (nada muda no
   site):
     * o canvas sai em resolução alta (o console limita a 2x; aqui vai a
       ESCALA pedida), sem o vigia de desempenho baixar a nitidez;
     * os jogos 3D (Strike Kids, Super Boxing) rodam numa tela deitada:
       o motor refaz a câmera e a cena sai larga de verdade, em vez de um
       recorte da tela em pé;
     * a partida fica em window.__partida, para o roteiro mirar nos alvos.

   Como rodar (com o site no ar, por exemplo manage.py runserver 8000):

       node ferramentas/artes_do_topo/filmar.js http://127.0.0.1:8000 /tmp/quadros [slug...]

   Precisa do Playwright com o Chromium (npm i playwright; npx playwright
   install chromium). Sem placa de vídeo, o 3D sai pelo SwiftShader.
   ====================================================================== */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";

/* O roteiro de cada jogo: o tamanho da tela (largo: a tela lógica deitada, só nos 3D), a escala do
   canvas e o que fazer. j.quadro(nome) guarda o canvas; j.serie(nome, n, s) guarda n quadros, um a
   cada s segundos; j.tecla(codigo) aperta e solta; j.na(fn, ...) roda fn na página. */
const ROTEIROS = {
  "strike-kids": {
    largo: [1280, 720], escala: 2,
    async rodar(j) {
      await j.jogar();
      await j.esperar(2.5);
      await j.serie("parque", 3, 0.7);
      // a bola pelo meio confirma o amigo; depois, a apresentação da fase e a jogada pelo meio
      await j.tecla("KeyC");
      await j.serie("amigos", 4, 0.7);
      await j.esperar(3);
      await j.serie("fase", 4, 1);
      await j.tecla("KeyC");
      await j.serie("jogada", 16, 0.35);
      await j.esperar(2);
      await j.tecla("KeyC");
      await j.serie("jogada2", 12, 0.4);
    },
  },
  "super-boxing": {
    largo: [1280, 720], escala: 1.5,
    async rodar(j) {
      await j.jogar();
      await j.esperar(4);
      await j.serie("ringue", 2, 0.6);
      // no SwiftShader a contagem anda devagar: espera o "SOQUE AGORA" e soca três vezes
      await j.esperar(14);
      for (let soco = 0; soco < 3; soco++) {
        await j.tecla("Space");
        await j.serie(`soco${soco}`, 6, 0.2);
        await j.esperar(1.5);
      }
      await j.serie("fim", 6, 0.6);
    },
  },
  "dragon-bowling": {
    escala: 3,
    async rodar(j) {
      await j.jogar();
      await j.esperar(4.5);
      await j.quadro("pista");
      await j.tecla("Space");
      await j.serie("jogada", 16, 0.3);
      await j.esperar(2);
      await j.tecla("Space");
      await j.serie("jogada2", 10, 0.4);
    },
  },
  "lazer-shot": {
    escala: 3,
    async rodar(j) {
      await j.jogar();
      await j.esperar(1.5);
      await j.tecla(process.env.CENARIO || "Digit1");
      await j.esperar(2.5);
      await j.serie("missao", 1, 0.1);
      await j.tecla("Enter");
      await j.esperar(4.5);
      // mira nos alvos que estão na tela: o tiro de verdade, com a explosão de verdade
      for (let i = 0; i < 14; i++) {
        await j.na(() => {
          const p = window.__partida;
          const alvos = (p && p.cenario && p.cenario.alvos) || [];
          const a = alvos.find((x) => x.alfa > 0.8) || alvos[0];
          if (a && p.atirar) p.atirar(a.x, a.y);
        });
        await j.esperar(0.12);
        await j.quadro(`tiro${String(i).padStart(2, "0")}`);
        await j.esperar(0.35);
      }
    },
  },
  "slam-arena": {
    escala: 3,
    async rodar(j) {
      await j.jogar();
      await j.esperar(4.5);
      // forças diferentes até a cesta entrar (a primeira cesta liga a arena)
      const forcas = [[0.62, 12, 30], [0.55, 12, 28], [0.5, 10, 26], [0.6, 14, 34], [0.58, 12, 30], [0.56, 12, 30]];
      for (let i = 0; i < forcas.length; i++) {
        const [ate, passos, ms] = forcas[i];
        await j.arrastar(0.5, 0.86, 0.5, ate, passos, ms);
        await j.serie(`arremesso${i}`, 6, 0.28);
      }
    },
  },
  "swish-arena": {
    escala: 2, hash: "#jogar-swish-arena",
    async rodar(j) {
      await j.jogar();
      await j.esperar(4.5);
      for (let i = 0; i < 4; i++) {
        await j.arrastar(0.5, 0.92, 0.5, 0.3, 8, 16);
        await j.serie(`arremesso${i}`, 7, 0.25);
      }
    },
  },
  "gol-flash-arena": {
    escala: 2,
    async rodar(j) {
      await j.jogar();
      await j.esperar(4.5);
      await j.quadro("estadio");
      // chuta em cada anel, um atrás do outro: o que estiver aceso vira gol (o anel explode em luz)
      const aneis = ["KeyA", "KeyB", "KeyC", "KeyD", "KeyE", "KeyF", "KeyG"];
      for (let volta = 0; volta < 3; volta++) {
        for (const anel of aneis) {
          await j.tecla(anel);
          await j.esperar(0.18);
          await j.quadro(`chute${volta}-${anel.slice(3)}`);
        }
      }
    },
  },
  "craque-de-botao": {
    escala: 2,
    async rodar(j) {
      await j.jogar();
      await j.esperar(4);
      await j.quadro("campo");
      for (let i = 0; i < 3; i++) {
        // a primeira tecla mostra a mira; segurar o Espaço carrega a força
        await j.tecla("Space");
        await j.esperar(0.3);
        await j.p.keyboard.down("Space");
        await j.esperar(0.6);
        await j.p.keyboard.up("Space");
        await j.serie(`chute${i}`, 6, 0.25);
        await j.esperar(3);
      }
    },
  },
  "hit-music": {
    escala: 3,
    async rodar(j) {
      await j.jogar();
      await j.esperar(2);
      await j.tecla("Enter");
      await j.esperar(6);
      // toca as faixas no ritmo (as notas que chegam ao anel acendem)
      const faixas = ["KeyA", "KeyS", "KeyD", "KeyF", "KeyJ", "KeyK", "KeyL", "Semicolon"];
      for (let i = 0; i < 24; i++) {
        await j.tecla(faixas[i % faixas.length]);
        await j.tecla(faixas[(i * 3 + 2) % faixas.length]);
        if (i % 2 === 0) await j.quadro(`musica${String(i).padStart(2, "0")}`);
        await j.esperar(0.15);
      }
    },
  },
};

// só na foto: o canvas na resolução pedida, a cena deitada nos jogos 3D e a partida à mão do roteiro
function remendar(arquivo, texto, roteiro) {
  const trocas = [
    ["this.escalaMaxima = 2;", "this.escalaMaxima = (window.__CAPTURA || 2);"],
    ["const densidade = Math.min(2, window.devicePixelRatio || 1);", "const densidade = window.__CAPTURA ? 12 : Math.min(2, window.devicePixelRatio || 1);"],
    ["medirDesempenho(ms) {", "medirDesempenho(ms) { if (window.__CAPTURA) return;"],
    ["function vigiar(passoReal) {", "function vigiar(passoReal) { if (window.__CAPTURA) return;"],
    ["const PR_MAXIMO = 1.5;", "const PR_MAXIMO = (window.__CAPTURA || 1.5);"],
    ["const QUADRO_LENTO = 1 / 40;", "const QUADRO_LENTO = window.__CAPTURA ? 99 : 1 / 40;"],
    ["this.partida = jogo.criar(api);", "this.partida = jogo.criar(api); window.__partida = this.partida;"],
  ];
  if (roteiro.largo && arquivo === `${roteiro.slug}.js`) {
    trocas.push(["const LARGURA = 540;", `const LARGURA = ${roteiro.largo[0]};`], ["const ALTURA = 960;", `const ALTURA = ${roteiro.largo[1]};`]);
  }
  for (const [antes, depois] of trocas) texto = texto.split(antes).join(depois);
  return texto;
}

async function filmar(navegador, base, pasta, slug) {
  const roteiro = { ...ROTEIROS[slug], slug };
  const ctx = await navegador.newContext({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2, userAgent: UA });
  await ctx.addInitScript((escala) => {
    window.__CAPTURA = escala;
    Object.defineProperty(window, "devicePixelRatio", { get: () => escala });
  }, roteiro.escala);
  await ctx.route(/\/static\/site\/arena\/.*\.js/, async (rota) => {
    const resposta = await rota.fetch();
    const arquivo = path.basename(new URL(rota.request().url()).pathname);
    await rota.fulfill({ response: resposta, body: remendar(arquivo, await resposta.text(), roteiro),
                         headers: { ...resposta.headers(), "content-type": "application/javascript" } });
  });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.log(`  [${slug}] erro na página: ${e.message}`));
  await p.goto(`${base}/jogos/${slug}/${roteiro.hash || ""}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  const tela = p.locator("[data-console-tela]");
  const j = {
    p,
    esperar: (s) => p.waitForTimeout(s * 1000),
    na: (fn, ...args) => p.evaluate(fn, ...args),
    async jogar() {
      await p.locator("[data-console-acao='jogar']").first().click({ timeout: 15000 });
      // o console não passa tecla ao jogo com o foco num botão (quem navega pelo teclado não joga sem querer)
      await p.evaluate(() => document.activeElement && document.activeElement.blur && document.activeElement.blur());
    },
    async tecla(codigo) { await p.keyboard.press(codigo); },
    async quadro(nome) {
      const url = await p.evaluate(() => document.querySelector("[data-console-tela]").toDataURL("image/png"));
      fs.writeFileSync(path.join(pasta, `${slug}-${nome}.png`), Buffer.from(url.split(",")[1], "base64"));
    },
    async serie(nome, n, intervalo) {
      for (let i = 0; i < n; i++) {
        await j.quadro(`${nome}-${String(i).padStart(2, "0")}`);
        await j.esperar(intervalo);
      }
    },
    // x e y em frações da tela do jogo
    async arrastar(x0, y0, x1, y1, passos = 8, ms = 20) {
      const c = await tela.boundingBox();
      const ponto = (x, y) => [c.x + x * c.width, c.y + y * c.height];
      const [a0, b0] = ponto(x0, y0), [a1, b1] = ponto(x1, y1);
      await p.mouse.move(a0, b0);
      await p.mouse.down();
      for (let i = 1; i <= passos; i++) {
        await p.mouse.move(a0 + (a1 - a0) * i / passos, b0 + (b1 - b0) * i / passos);
        await p.waitForTimeout(ms);
      }
      await p.mouse.up();
    },
  };
  await roteiro.rodar(j);
  await ctx.close();
}

(async () => {
  const [base, pasta, ...pedidos] = process.argv.slice(2);
  if (!base || !pasta) {
    console.log("uso: node filmar.js <endereço do site> <pasta dos quadros> [slug...]");
    process.exit(2);
  }
  fs.mkdirSync(pasta, { recursive: true });
  // o 2D no processador (o canvas acelerado pelo SwiftShader leva minutos por quadro); o 3D no SwiftShader
  const navegador = await chromium.launch({
    args: ["--disable-blink-features=AutomationControlled", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
           "--disable-accelerated-2d-canvas", "--autoplay-policy=no-user-gesture-required", "--mute-audio"],
  });
  for (const slug of pedidos.length ? pedidos : Object.keys(ROTEIROS)) {
    if (!ROTEIROS[slug]) { console.log(`sem roteiro: ${slug}`); continue; }
    const inicio = Date.now();
    await filmar(navegador, base.replace(/\/$/, ""), pasta, slug);
    console.log(`${slug}: ${Math.round((Date.now() - inicio) / 1000)} s`);
  }
  await navegador.close();
})();
