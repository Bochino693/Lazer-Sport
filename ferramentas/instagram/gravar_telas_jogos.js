// Grava as telas da area de jogos para o video: portal e biblioteca (site no ar, so leitura),
// aviso das 2 jogadas gratis, ranking e botao da maquina (copia local, ranking de demonstracao).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const OUT = path.join(__dirname, 'grav3');
const SITE = 'https://www.lazersport.com.br';
const LOCAL = 'http://127.0.0.1:8010';
const FPS = 30;
const tela = { viewport: { width: 412, height: 860 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, ignoreHTTPSErrors: true, locale: 'pt-BR' };
const meta = {};
function seg(nome) {
  const dir = path.join(OUT, nome);
  fs.mkdirSync(dir, { recursive: true });
  meta[nome] = { quadros: 0, dur: [], toques: [] };
  return {
    async foto(p, d) {
      const n = meta[nome].quadros++;
      meta[nome].dur.push(d);
      await p.screenshot({ path: path.join(dir, String(n).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 88, timeout: 120000 });
    },
    async parado(p, s) { for (let i = 0; i < Math.max(1, Math.round(s * FPS / 6)); i++) await this.foto(p, 6); },
    async rolar(p, ate, s) {
      const de = await p.evaluate(() => window.scrollY);
      const n = Math.round(s * FPS / 2);
      for (let i = 1; i <= n; i++) {
        const k = i / n; const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        await p.evaluate(v => window.scrollTo(0, v), de + (ate - de) * e);
        await this.foto(p, 2);
      }
    },
    toque(x, y) { meta[nome].toques.push({ t: meta[nome].dur.reduce((a, b) => a + b, 0), x, y }); },
  };
}
const topo = (p, sel) => p.evaluate(q => { const e = document.querySelector(q); return e ? e.getBoundingClientRect().top + window.scrollY : null; }, sel);
const centroTexto = (p, tag, texto) => p.evaluate(([t, x]) => {
  const e = Array.from(document.querySelectorAll(t)).find(n => n.offsetParent && (n.innerText || '').trim().indexOf(x) === 0);
  if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];
}, [tag, texto]);
async function aquecer(p, max) {
  const h = await p.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < Math.min(h, max); y += 700) { await p.evaluate(v => window.scrollTo(0, v), y); await p.waitForTimeout(250); }
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(600);
}

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  const b = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY, bypass: '127.0.0.1,localhost' } });

  // ---------- portal e biblioteca (site no ar)
  let c = await b.newContext(tela);
  let p = await c.newPage();
  await p.goto(SITE + '/jogos/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(3000);
  await aquecer(p, 7000);
  let s = seg('a_portal');
  await s.parado(p, 1.2);
  await s.rolar(p, 520, 1.2);
  await s.parado(p, 0.8);
  const yb = await topo(p, '#biblioteca');
  console.log('biblioteca em y =', yb);
  s = seg('b_classicos');
  const yps = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('h2,h3,h4')).find(n => (n.innerText || '').trim().indexOf('PlayStation') === 0); return e ? e.getBoundingClientRect().top + window.scrollY : null; });
  console.log('estante PlayStation em y =', yps);
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, (yps || yb || 900) - 150));
  await p.waitForTimeout(500);
  await s.parado(p, 1.0);
  await s.rolar(p, (yps || yb || 900) + 1500, 3.4);
  await s.parado(p, 0.8);
  await c.close();

  // ---------- aviso das 2 jogadas gratis (copia local, visitante sem conta)
  c = await b.newContext(tela);
  p = await c.newPage();
  await p.goto(LOCAL + '/jogos/strike-kids/', { waitUntil: 'domcontentloaded', timeout: 120000 });
  await p.waitForTimeout(4000);
  const tem = await p.evaluate(() => {
    const d = document.querySelector('[data-console-cadastro]');
    if (!d) return false;
    d.hidden = false; d.removeAttribute('hidden');
    const cv = document.querySelector('canvas');
    (cv || d).scrollIntoView({ block: 'center' });
    return true;
  });
  console.log('aviso das jogadas gratis:', tem);
  await p.waitForTimeout(600);
  s = seg('c_regra');
  await s.parado(p, 2.2);
  const tcr = await centroTexto(p, 'a', 'Criar conta grátis');
  console.log('botao criar conta em', tcr);
  if (tcr) s.toque(tcr[0], tcr[1]);
  await s.parado(p, 0.7);
  await c.close();

  // ---------- ranking e botao da maquina (copia local, cliente de demonstracao)
  c = await b.newContext(tela);
  await c.addCookies([{ name: 'sessionid', value: fs.readFileSync(path.join(__dirname, 'sessao.txt'), 'utf8').trim(), domain: '127.0.0.1', path: '/' }]);
  p = await c.newPage();
  await p.goto(LOCAL + '/jogos/strike-kids/', { waitUntil: 'domcontentloaded', timeout: 120000 });
  await p.waitForTimeout(4000);
  const yr = await topo(p, '.sim-ranking');
  console.log('ranking em y =', yr);
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, yr - 130));
  await p.waitForTimeout(700);
  s = seg('d_ranking');
  await s.parado(p, 1.8);
  const tg = await centroTexto(p, 'button', 'Geral');
  if (tg) { s.toque(tg[0], tg[1]); await s.parado(p, 0.4); await p.mouse.click(tg[0], tg[1]); await p.waitForTimeout(1200); }
  await s.parado(p, 2.2);
  s = seg('e_maquina');
  const ym = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('a')).find(n => n.offsetParent && (n.innerText || '').indexOf('Quero essa máquina') >= 0); return e ? e.getBoundingClientRect().top + window.scrollY : null; });
  console.log('botao da maquina em y =', ym);
  if (ym) {
    await p.evaluate(v => window.scrollTo(0, v), Math.max(0, ym - 520));
    await p.waitForTimeout(600);
    await s.parado(p, 1.2);
    const tm = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('a')).find(n => n.offsetParent && (n.innerText || '').indexOf('Quero essa máquina') >= 0); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    s.toque(tm[0], tm[1]);
    await s.parado(p, 0.8);
  }
  await c.close();
  await b.close();
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 1));
  console.log(Object.keys(meta).map(k => k + ':' + (meta[k].dur.reduce((a, b) => a + b, 0) / 30).toFixed(1) + 's/' + meta[k].toques.length + 't').join('  '));
})();
