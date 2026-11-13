// Grava, quadro a quadro, as telas do passo a passo de compra para o tutorial.py.
//
// Uso:  node ferramentas/instagram/gravar_compra.js
// Saida: pasta "grav" ao lado deste arquivo (meta.json + um trecho por subpasta).
//
// Telas publicas (vitrine e pagina da promocao): site no ar, so leitura.
// Carrinho e pagamento: copia LOCAL do site em http://127.0.0.1:8010, com um cliente de
// demonstracao logado (cookie em sessao.txt ao lado deste arquivo), para nao criar conta nem
// pedido de verdade. A copia local nao tem as chaves do Mercado Pago, entao os avisos de erro
// da tela de pagamento sao escondidos e o QR do Pix / formulario do cartao nao aparecem.
// Ajuste o numero da promocao (10 no site, 1 na copia local) antes de gravar outra oferta.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const OUT = path.join(__dirname, 'grav');
const SITE = 'https://www.lazersport.com.br';
const LOCAL = 'http://127.0.0.1:8010';
const FPS = 30;
const tela = { viewport: { width: 412, height: 860 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, ignoreHTTPSErrors: true, locale: 'pt-BR' };
const meta = {};

function seg(nome) {
  const dir = path.join(OUT, nome);
  fs.mkdirSync(dir, { recursive: true });
  // dur[i] = por quantos quadros do video final (30 fps) a foto i fica na tela
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
    // t = instante do toque, em quadros do video final desde o inicio do trecho
    toque(x, y) { meta[nome].toques.push({ t: meta[nome].dur.reduce((a, b) => a + b, 0), x, y }); },
  };
}
// Cada foto vale um numero de quadros do video final; guardamos a lista para o compositor.
// Para simplificar: "parado" grava 1 foto a cada 6 quadros e "rolar" 1 a cada 2. O compositor
// recebe a duracao de cada foto em meta[nome].tempos.
function comTempos(s) {
  const base = s.foto.bind(s);
  let nome = null;
  return s;
}

async function centro(p, sel) {
  return await p.evaluate(q => { const e = document.querySelector(q); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }, sel);
}
async function centroTexto(p, tag, texto, exato) {
  return await p.evaluate(([t, x, ex]) => {
    const e = Array.from(document.querySelectorAll(t)).find(n => n.offsetParent && (ex ? (n.innerText || '').trim() === x : (n.innerText || '').indexOf(x) >= 0));
    if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];
  }, [tag, texto, !!exato]);
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

  // ---------- 1. vitrine (site no ar)
  let c = await b.newContext(tela);
  let p = await c.newPage();
  await p.goto(SITE + '/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(2500);
  await aquecer(p);
  const SEL = '#promocoes-section a[href*="/promocao/10"]';
  const alvoY = await p.evaluate(q => {
    const a = Array.from(document.querySelectorAll(q)).find(n => n.offsetParent) || Array.from(document.querySelectorAll('a[href*="/promocao/10"]')).filter(n => n.offsetParent).pop();
    if (!a) return null;
    a.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
    return window.scrollY;
  }, SEL);
  console.log('oferta na secao de promocoes, rolagem =', alvoY);
  await p.waitForTimeout(900);
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(500);
  let s = seg('1_vitrine');
  await s.parado(p, 0.5);
  await s.rolar(p, alvoY || 1500, 1.9);
  await s.parado(p, 1.2);
  const t1 = await p.evaluate(q => {
    const a = Array.from(document.querySelectorAll(q)).find(n => n.offsetParent) || Array.from(document.querySelectorAll('a[href*="/promocao/10"]')).filter(n => n.offsetParent).pop();
    if (!a) return null; const r = a.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];
  }, SEL);
  console.log('toque na oferta em', t1);
  if (t1) s.toque(Math.min(Math.max(t1[0], 40), 372), Math.min(Math.max(t1[1], 120), 700));
  await s.parado(p, 0.5);

  // ---------- 2. pagina da promocao (site no ar)
  await p.goto(SITE + '/promocao/10', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await p.waitForTimeout(2500);
  await aquecer(p);
  s = seg('2_promocao');
  const arte = await topoDe(p, 'main img');
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, (arte || 200) - 120));
  await s.parado(p, 1.3);
  const yb = await topoDe(p, 'button.btn-comprar');
  await s.rolar(p, yb - 520, 1.5);
  await s.parado(p, 1.1);
  const t2 = await centro(p, 'button.btn-comprar');
  s.toque(t2[0], t2[1]);
  await s.parado(p, 0.5);
  await c.close();

  // ---------- 3. entrar na conta (copia local)
  c = await b.newContext(tela);
  p = await c.newPage();
  await p.goto(LOCAL + '/login/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(2000);
  s = seg('3_entrar');
  const yl = await topoDe(p, 'input[name=username]');
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, yl - 330));
  await s.parado(p, 0.5);
  await p.type('input[name=username]', 'marina@email.com', { delay: 0 });
  await s.parado(p, 0.4);
  await p.type('input[type=password]', 'minhasenha', { delay: 0 });
  await p.evaluate(() => document.activeElement && document.activeElement.blur());
  await s.parado(p, 0.6);
  const t3 = await centroTexto(p, 'form button[type=submit]', 'Entrar');
  s.toque(t3[0], t3[1]);
  await s.parado(p, 0.5);
  await c.close();

  // ---------- 4 a 6. quantidade, carrinho e pagamento (copia local, cliente de demonstracao)
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
  await s.parado(p, 1.4);
  const t4 = await p.evaluate(() => {
    const e = Array.from(document.querySelectorAll('button')).find(n => n.offsetParent && (n.innerText || '').indexOf('Comprar agora') >= 0 && !n.classList.contains('btn-comprar'));
    const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2];
  });
  s.toque(t4[0], t4[1]);
  await s.parado(p, 0.5);
  await p.mouse.click(t4[0], t4[1]);
  await p.waitForTimeout(4500);
  console.log('apos comprar:', p.url());

  // carrinho
  await p.evaluate(() => {
    const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
    const alvo = []; let n;
    while ((n = w.nextNode())) { if (n.nodeValue.indexOf('{#') >= 0 || n.nodeValue.indexOf('#}') >= 0 || n.nodeValue.indexOf('Abre na forma de entrega') >= 0) alvo.push(n); }
    alvo.forEach(t => { t.nodeValue = ''; });
  });
  await aquecer(p);
  s = seg('5_carrinho');
  await s.parado(p, 1.0);
  const yc = await topoDe(p, '#cpfInput');
  await s.rolar(p, yc - 330, 1.0);
  await s.parado(p, 0.3);
  await p.fill('#cpfInput', '52998224725');
  await p.evaluate(() => document.activeElement && document.activeElement.blur());
  await p.waitForTimeout(900);
  await s.parado(p, 0.9);
  const tr0 = await centroTexto(p, 'main button', 'Retirar na loja');
  await s.rolar(p, (await p.evaluate(() => window.scrollY)) + Math.max(0, tr0[1] - 380), 0.8);
  const tr = await centroTexto(p, 'main button', 'Retirar na loja');
  s.toque(tr[0], tr[1]);
  await s.parado(p, 0.4);
  await p.mouse.click(tr[0], tr[1]);
  await p.waitForTimeout(2200);
  await s.parado(p, 1.0);
  const tc = await centro(p, '#btnFinalizar');
  s.toque(tc[0], tc[1]);
  await s.parado(p, 0.5);
  await p.click('#btnFinalizar');
  await p.waitForTimeout(5000);
  console.log('apos continuar:', p.url());

  // pagamento (sem as chaves do Mercado Pago na copia local: esconde os avisos de erro)
  const limpar = async () => p.evaluate(() => {
    ['#payment-error', '#payment-live-status'].forEach(q => { const e = document.querySelector(q); if (e) e.style.display = 'none'; });
  });
  await limpar();
  const yt = await p.evaluate(() => { const e = Array.from(document.querySelectorAll('main *')).find(n => (n.innerText || '').trim().indexOf('TOTAL A PAGAR') === 0); return e ? e.getBoundingClientRect().top + window.scrollY : 300; });
  await p.evaluate(v => window.scrollTo(0, v), Math.max(0, yt - 300));
  await p.waitForTimeout(500);
  s = seg('6_pix');
  await s.parado(p, 0.4);
  await p.screenshot({ path: path.join(OUT, 'debug_pag.jpg'), type: 'jpeg' }); const tp = await centroTexto(p, 'main button', 'Pix', false) || [120, 330];
  s.toque(tp[0], tp[1]);
  await s.parado(p, 1.8);
  s = seg('7_credito');
  const tk = await centroTexto(p, 'main button', 'Crédito', false);
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
  await s.parado(p, 1.8);
  await c.close();
  await b.close();
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 1));
  console.log(Object.keys(meta).map(k => k + ':' + meta[k].quadros + 'f/' + meta[k].toques.length + 't').join('  '));
})();
