// Filma um jogo da copia local QUADRO A QUADRO: o relogio da pagina e controlado, cada quadro
// avanca 1/30 s e a tela do jogo e fotografada, entao o take sai liso mesmo com a maquina lenta.
// Uso: node filmar_jogo.js <slug> <segundos> [largura_da_janela]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const slug = process.argv[2];
const SEG = parseFloat(process.argv[3] || '16');
const VW = parseInt(process.argv[4] || '760', 10);
const VH = Math.round(VW * 2.15);
const D = path.join(__dirname, 'jg', 'filme_' + slug);

(async () => {
  fs.rmSync(D, { recursive: true, force: true });
  fs.mkdirSync(D, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'] });
  const c = await b.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1, isMobile: true, hasTouch: true, locale: 'pt-BR' });
  await c.addCookies([{ name: 'sessionid', value: fs.readFileSync(path.join(__dirname, 'sessao.txt'), 'utf8').trim(), domain: '127.0.0.1', path: '/' }]);
  const p = await c.newPage();
  await p.clock.install();
  // um desenho por quadro do video (o relogio falso chamaria o jogo duas vezes a cada 33 ms)
  await p.addInitScript(() => { const o = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = cb => o(() => o(cb)); });
  await p.goto('http://127.0.0.1:8010/jogos/' + slug + '/', { waitUntil: 'domcontentloaded' });
  const andar = async (ms, passo) => { for (let t = 0; t < ms; t += passo) { await p.clock.runFor(passo); await p.waitForTimeout(20); } };
  await andar(4000, 100);
  const achar = () => p.evaluate(() => { const e = Array.from(document.querySelectorAll('button')).find(n => n.offsetParent && (n.innerText || '').trim().indexOf('Jogar') === 0); if (!e) return null; e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  let jogar = await achar();
  if (!jogar) { console.log(slug, 'SEM BOTAO JOGAR'); await b.close(); return; }
  await andar(300, 100);
  jogar = await achar();
  // leva o topo da tela do jogo para o topo da janela, para o jogo caber inteiro na foto
  await p.evaluate(() => { const e = Array.from(document.querySelectorAll('canvas')).find(n => n.offsetParent); window.scrollBy(0, e.getBoundingClientRect().top - 6); });
  await andar(200, 100);
  jogar = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('button')).find(n => n.offsetParent && (n.innerText || '').trim().indexOf('Jogar') === 0); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  const cv = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('canvas')).find(n => n.offsetParent); const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; });
  const clip = { x: Math.max(0, cv[0]), y: Math.max(0, cv[1]), width: Math.min(VW - Math.max(0, cv[0]), cv[2]), height: Math.min(VH - Math.max(0, cv[1]), cv[3] - Math.max(0, -cv[1])) };
  console.log(slug, 'tela do jogo', cv.map(Math.round).join(','), 'janela', VW + 'x' + VH, 'jogar', jogar.map(Math.round).join(','));
  await p.mouse.click(jogar[0], jogar[1]);
  const cdp = await c.newCDPSession(p);
  let rnd = parseInt(process.argv[5] || '11', 10);
  const r = () => { rnd = (rnd * 16807) % 2147483647; return rnd / 2147483647; };
  const N = Math.round(SEG * 30);
  let gesto = null, proximo = 20, n = 0;
  const t0 = Date.now();
  for (let f = 0; f < N; f++) {
    if (f === 12) await p.mouse.click(cv[0] + cv[2] / 2, cv[1] + cv[3] * 0.5);   // pula a abertura
    if (!gesto && f >= proximo) {
      const x = cv[0] + cv[2] * (0.28 + 0.44 * r());
      if (n % 3 !== 2) gesto = { k: 0, x, y0: cv[1] + cv[3] * 0.84, y1: cv[1] + cv[3] * (0.28 + 0.18 * r()), dx: (r() - 0.5) * cv[2] * 0.22 };
      else { await p.mouse.click(x, cv[1] + cv[3] * (0.32 + 0.45 * r())); proximo = f + 14 + Math.floor(r() * 10); }
      n++;
    }
    if (gesto) {
      const g = gesto, k = g.k;
      if (k === 0) { await p.mouse.move(g.x, g.y0); await p.mouse.down(); }
      else if (k <= 5) await p.mouse.move(g.x + g.dx * k / 5, g.y0 + (g.y1 - g.y0) * k / 5);
      else { await p.mouse.up(); gesto = null; proximo = f + 22 + Math.floor(r() * 16); }
      if (gesto) g.k++;
    }
    await p.clock.runFor(33);
    const foto = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 86, clip: { x: clip.x, y: clip.y, width: clip.width, height: clip.height, scale: 1 }, optimizeForSpeed: true });
    fs.writeFileSync(path.join(D, String(f).padStart(4, '0') + '.jpg'), Buffer.from(foto.data, 'base64'));
  }
  fs.writeFileSync(path.join(D, 'info.json'), JSON.stringify({ slug, quadros: N, largura: Math.round(clip.width), altura: Math.round(clip.height) }));
  console.log(slug, N + ' quadros', Math.round(clip.width) + 'x' + Math.round(clip.height), 'em', ((Date.now() - t0) / 1000).toFixed(0) + 's');
  await b.close();
})();
