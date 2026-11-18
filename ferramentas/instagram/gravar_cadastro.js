// Uso: node ferramentas/instagram/gravar_cadastro.js  (saida: pasta grav2 ao lado deste arquivo)
// Precisa da copia local do site em http://127.0.0.1:8010 e do cookie do cliente de demonstracao em sessao.txt.
// Grava as telas do video "Black Friday + cadastro com 1 clique".
// Publicas (inicio, entrar, pagina da promocao): site no ar, so leitura, sem clicar no Google.
// Quantidade, carrinho e pagamento: copia local com cliente de demonstracao.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const OUT = path.join(__dirname, 'grav2');
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
      await p.screenshot({ path: path.join(dir, String(n).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 88 });
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
async function centro(p, sel) {
  return await p.evaluate(q => { const e = Array.from(document.querySelectorAll(q)).find(n => n.offsetParent); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }, sel);
}
async function centroTexto(p, tag, texto) {
  return await p.evaluate(([t, x]) => {
    const e = Array.from(document.querySelectorAll(t)).find(n => n.offsetParent && (n.innerText || '').indexOf(x) >= 0);
    if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];
  }, [tag, texto]);
}
async function topoDe(p, sel) {
  return await p.evaluate(q => { const e = document.querySelector(q); return e ? e.getBoundingClientRect().top + window.scrollY : null; }, sel);
}
async function aquecer(p) {
  const h = await p.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < Math.min(h, 9000); y += 700) { await p.evaluate(v => window.scrollTo(0, v), y); await p.waitForTimeout(200); }
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(700);
}

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  const b = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY, bypass: '127.0.0.1,localhost' } });

  // ---------- 1. inicio do site -> Entrar (site no ar)
  let c = await b.newContext(tela);
  let p = await c.newPage();
  await p.goto(SITE + '/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(3000);
  let s = seg('1_inicio');
  await s.parado(p, 1.0);
  const te = await p.evaluate(() => {
    const e = Array.from(document.querySelectorAll('a[href*="/login"], a[href*="/registrar"]')).find(n => n.offsetParent && n.getBoundingClientRect().top < 860 && n.getBoundingClientRect().top >= 0);
    if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, (e.innerText || '').trim().slice(0, 20)];
  });
  console.log('link de entrar na primeira tela:', te);
  if (te) s.toque(te[0], te[1]);
  await s.parado(p, 0.6);

  // ---------- 2. tela de entrar -> Continuar com Google (site no ar; o botao NAO e clicado)
  await p.goto(SITE + '/login/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(2500);
  const yg = await p.evaluate(() => {
    const e = Array.from(document.querySelectorAll('button')).find(n => n.offsetParent && (n.innerText || '').indexOf('Continuar com Google') >= 0);
    return e ? e.getBoundingClientRect().top + window.scrollY : 300;
  });
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, yg - 300));
  await p.waitForTimeout(500);
  s = seg('2_google');
  await s.parado(p, 1.2);
  const tg = await centroTexto(p, 'button', 'Continuar com Google');
  console.log('botao do Google em', tg);
  s.toque(tg[0], tg[1]);
  await s.parado(p, 1.4);

  // ---------- 3. pagina da promocao (site no ar)
  await p.goto(SITE + '/promocao/10', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(2500);
  await aquecer(p);
  s = seg('3_promocao');
  const arte = await topoDe(p, 'main img');
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, (arte || 200) - 120));
  await s.parado(p, 1.2);
  const yb = await topoDe(p, 'button.btn-comprar');
  await s.rolar(p, yb - 520, 1.5);
  await s.parado(p, 1.2);
  const t2 = await centro(p, 'button.btn-comprar');
  s.toque(t2[0], t2[1]);
  await s.parado(p, 0.5);
  await c.close();

  // ---------- 4 a 7. quantidade, carrinho e pagamento (copia local)
  c = await b.newContext(tela);
  await c.addCookies([{ name: 'sessionid', value: fs.readFileSync(path.join(__dirname, 'sessao.txt'), 'utf8').trim(), domain: '127.0.0.1', path: '/' }]);
  p = await c.newPage();
  await p.goto(LOCAL + '/promocao/1', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(2500);
  await p.evaluate(() => document.querySelector('button.btn-comprar').scrollIntoView({ block: 'center' }));
  await p.waitForTimeout(500);
  await p.click('button.btn-comprar');
  await p.waitForTimeout(2200);
  s = seg('4_quantidade');
  await s.parado(p, 1.3);
  const t4 = await p.evaluate(() => {
    const e = Array.from(document.querySelectorAll('button')).find(n => n.offsetParent && (n.innerText || '').indexOf('Comprar agora') >= 0 && !n.classList.contains('btn-comprar'));
    const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];
  });
  s.toque(t4[0], t4[1]);
  await s.parado(p, 0.5);
  await p.mouse.click(t4[0], t4[1]);
  await p.waitForTimeout(4500);
  console.log('apos comprar:', p.url());

  await p.evaluate(() => {
    const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
    const alvo = []; let n;
    while ((n = w.nextNode())) { if (n.nodeValue.indexOf('{#') >= 0 || n.nodeValue.indexOf('#}') >= 0 || n.nodeValue.indexOf('Abre na forma de entrega') >= 0) alvo.push(n); }
    alvo.forEach(t => { t.nodeValue = ''; });
  });
  await aquecer(p);
  s = seg('5_carrinho');
  const yc = await topoDe(p, '#cpfInput');
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, yc - 330));
  await p.waitForTimeout(400);
  await s.parado(p, 0.5);
  await p.fill('#cpfInput', '52998224725');
  await p.evaluate(() => document.activeElement && document.activeElement.blur());
  await p.waitForTimeout(900);
  await s.parado(p, 0.8);
  const yr = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('main *')).find(n => n.children.length === 0 && (n.innerText || '').trim().indexOf('Total no Pix') === 0); return e ? e.getBoundingClientRect().top + window.scrollY : null; });
  console.log('resumo (Total no Pix) em y =', yr);
  if (yr) { await s.rolar(p, yr - 420, 1.2); await s.parado(p, 1.3); }
  const tc = await centro(p, '#btnFinalizar');
  s.toque(tc[0], tc[1]);
  await s.parado(p, 0.5);
  await p.click('#btnFinalizar');
  await p.waitForTimeout(5000);
  console.log('apos continuar:', p.url());

  const limpar = async () => p.evaluate(() => {
    ['#payment-error', '#payment-live-status'].forEach(q => { const e = document.querySelector(q); if (e) e.style.display = 'none'; });
  });
  await limpar();
  const yt = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('main *')).find(n => (n.innerText || '').trim().indexOf('TOTAL A PAGAR') === 0); return e ? e.getBoundingClientRect().top + window.scrollY : 300; });
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, yt - 300));
  await p.waitForTimeout(500);
  s = seg('6_pix');
  await s.parado(p, 0.4);
  const tp = await centroTexto(p, 'main button', 'Pix') || [120, 330];
  s.toque(tp[0], tp[1]);
  await s.parado(p, 1.7);
  s = seg('7_credito');
  const tk = await centroTexto(p, 'main button', 'Crédito');
  await s.parado(p, 0.3);
  s.toque(tk[0], tk[1]);
  await s.parado(p, 0.3);
  await p.mouse.click(tk[0], tk[1]);
  await p.waitForTimeout(3500);
  await limpar();
  await p.evaluate(() => {
    const bt = document.querySelector('#card-tentar');
    if (!bt) return;
    let e = bt;
    while (e.parentElement && (e.parentElement.innerText || '').indexOf('Cartão de crédito') < 0) e = e.parentElement;
    e.style.display = 'none';
  });
  await p.waitForTimeout(300);
  await s.parado(p, 1.7);
  await c.close();
  await b.close();
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 1));
  console.log(Object.keys(meta).map(k => k + ':' + (meta[k].dur.reduce((a, b) => a + b, 0) / 30).toFixed(1) + 's/' + meta[k].toques.length + 't').join('  '));
})();
