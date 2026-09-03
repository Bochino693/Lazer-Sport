/* O SINO ANUNCIA O QUE ACONTECEU ENQUANTO A PESSOA NÃO ESTAVA.
 *
 * Com o painel aberto isso sempre funcionou: o número era 3, virou 4, o
 * sino balançou. O buraco era a CHEGADA -- sair com dez pendências e
 * voltar com onze não produzia nada, porque a aba nova não tinha contra
 * o que comparar e guardava "onze" como se sempre tivesse sido onze.
 *
 * Aqui cada cena monta um painel do zero, como um F5 de verdade, e cobra
 * o que a pessoa VÊ: o sino balança, balança mais forte na chegada, o
 * número está certo, e a memória volta para o servidor uma vez só.
 */
const {JSDOM} = require('jsdom');
const fs = require('fs'), path = require('path'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const base = 'http://painel.test/orcamentos/';
const html = `<body data-avisos="/avisos/estado/">
<input type="hidden" name="csrfmiddlewaretoken" value="tok">
<button id="avisosBotao" class="ls-avisos-botao"><i class="bi bi-bell"></i><span class="ls-avisos-selo" data-selo="total"></span></button>
<div id="avisosLista"></div><main class="ls-content"></main></body>`;

const fontes = ['painel.js', 'ls-soft-navigation.js', 'ls-sincronia.js'].map(
  nome => fs.readFileSync(path.join(root, 'sistema_interno/static/interno', nome), 'utf8'));

/* Um painel recém-aberto: `vistos` é a memória que o servidor tem desta
   conta, `quantidade` é o que está acontecendo agora. */
async function abrir(vistos, quantidade) {
  const dom = new JSDOM(html, {url: base, runScripts: 'outside-only', pretendToBeVisual: true});
  const w = dom.window, d = w.document;
  w.matchMedia = () => ({matches: false, addEventListener() {}, removeEventListener() {}});
  w.scrollTo = () => {};
  w.notas = 0; w.posts = [];
  w.AudioContext = class {
    constructor() { this.state = 'running'; this.currentTime = 0; }
    createOscillator() { return {frequency: {}, connect() {}, start() { w.notas += 1; }, stop() {}}; }
    createGain() { return {gain: {setValueAtTime() {}, exponentialRampToValueAtTime() {}}, connect() {}}; }
  };
  w.cena = {vistos, quantidade};
  w.fetch = async (url, opcoes = {}) => {
    if (opcoes.method === 'POST') {
      w.posts.push({acao: opcoes.body.get('acao'), vistos: opcoes.body.get('vistos')});
      return new Response('{}', {headers: {'content-type': 'application/json'}});
    }
    const q = w.cena.quantidade;
    return new Response(JSON.stringify({
      assinatura: 'estado-' + q, revisoes: {}, contagens: {},
      total: q, urgentes: 0, vistos: w.cena.vistos,
      avisos: [{chave: 'orcamentos_atividade', titulo: 'Nova movimentação',
                detalhe: 'Colega alterou o orçamento #12.', quantidade: q,
                url: '/orcamentos/', nivel: 'novidade', icone: 'bi-bell-fill', urgente: false}],
    }), {headers: {'content-type': 'application/json'}});
  };
  await new Promise(r => d.readyState === 'loading'
    ? d.addEventListener('DOMContentLoaded', r, {once: true}) : r());
  fontes.forEach(fonte => w.eval(fonte));
  await w.Painel.avisos.agora();
  return {dom, w, d, sino: d.getElementById('avisosBotao'),
          selo: d.querySelector('[data-selo="total"]')};
}

const dormir = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  /* 1. Nada mudou enquanto esteve fora: silêncio. */
  {
    const {dom, sino} = await abrir({orcamentos_atividade: 10}, 10);
    assert.equal(sino.classList.contains('chacoalha'), false,
      'voltar com o mesmo número não pode balançar o sino');
    dom.window.close();
  }

  /* 2. Saiu com dez, um colega mexeu, voltou com onze. */
  {
    const {dom, w, sino, selo} = await abrir({orcamentos_atividade: 10}, 11);
    assert.equal(sino.classList.contains('chacoalha'), true,
      'a movimentação feita com a pessoa fora tem de balançar o sino na chegada');
    assert.equal(sino.classList.contains('chegada'), true,
      'na chegada o sino bate três vezes, não uma');
    assert.equal(selo.textContent, '11', 'o número já chega atualizado');

    await dormir(2300);
    assert.equal(w.posts.length, 1, 'a memória volta ao servidor uma vez só');
    assert.equal(w.posts[0].acao, 'avisos_vistos');
    assert.equal(JSON.parse(w.posts[0].vistos).orcamentos_atividade, 11);

    /* E não se repete: o pulso seguinte encontra a memória já em dia. */
    sino.classList.remove('chacoalha');
    await w.Painel.avisos.agora();
    assert.equal(sino.classList.contains('chacoalha'), false,
      'anunciado uma vez, não se anuncia de novo a cada pulso');
    dom.window.close();
  }

  /* 3. O colega mexe com o painel JÁ aberto -- o caso que já funcionava,
        e que a memória nova não pode ter quebrado. */
  {
    const {dom, w, sino, selo} = await abrir({orcamentos_atividade: 11}, 11);
    w.notas = 0;
    w.cena.quantidade = 12;
    await w.Painel.avisos.agora();
    assert.equal(sino.classList.contains('chacoalha'), true,
      'com o painel aberto o sino continua balançando na hora');
    assert.equal(sino.classList.contains('chegada'), false,
      'quem está olhando não precisa das três batidas');
    assert(w.notas > 0, 'com o painel aberto o aviso também é ouvido');
    assert.equal(selo.textContent, '12');
    dom.window.close();
  }

  /* 4. Servidor sem o campo (implantação no meio do caminho): calado,
        como era antes -- e nunca doze avisos de uma vez. */
  {
    const {dom, w, sino} = await abrir(undefined, 7);
    assert.equal(sino.classList.contains('chacoalha'), false,
      'sem memória do servidor o sino se cala em vez de anunciar tudo');
    await dormir(2300);
    assert.equal(JSON.parse(w.posts[0].vistos).orcamentos_atividade, 7,
      'mas já grava a memória, para a próxima chegada valer');
    dom.window.close();
  }

  console.log('OK: chegada silenciosa, chegada com novidade, novidade ao vivo e servidor sem memória.');
})().catch(e => { console.error(e); process.exit(1); });
