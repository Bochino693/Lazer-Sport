/* A barra de ações do cartão e a folha do "Mais" (ls-listas.js), no DOM.

   Roda o agrupador de ações do painel (painel.js) e o módulo da lista ou
   cards inteiro sobre uma tabela de mentira, e confere:
     * na LISTA nada é montado: quem não usa cards não paga pela barra;
     * em CARDS as ações marcadas viram botões, na ordem pedida, e acionam
       a ação de verdade -- nenhuma é clonada;
     * "Mais" é o próprio "⋮", com o nome, e a folha esconde o que já está
       na barra, separa o que apaga e leva o nome do registro;
     * a linha de uma ação só, a linha sem resto e a tela que não marcou
       nenhuma ação;
     * a escolha volta para a lista, e a logo que não carrega dá lugar às
       iniciais.
   O jsdom não calcula layout: o foco na folha e as setas são conferidos
   no navegador (ver LEIA-ME-V10.txt, seção 75). */
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');

const estaticos = path.join(__dirname, '../static/interno');
const painel = fs.readFileSync(path.join(estaticos, 'painel.js'), 'utf8');
const listas = fs.readFileSync(path.join(estaticos, 'ls-listas.js'), 'utf8');
const agrupador = painel.slice(
  painel.indexOf('  Painel.organizarAcoesTabelas ='),
  painel.indexOf('  global.Painel = Painel;')
);
assert.ok(agrupador.length > 1000, 'não achei Painel.organizarAcoesTabelas em painel.js');

function linha(id, nome, acoes) {
  return '<tr data-registro="' + id + '" data-visao-nome="' + nome + '"><td data-rotulo="Cliente">' + nome + '</td>' +
    '<td data-rotulo="Ações" class="ls-actions ls-commercial-actions"><div class="ls-row-actions">' + acoes + '</div></td></tr>';
}

function tabela(id, chave, linhas) {
  return '<div class="ls-visao" data-visao-seletor data-visao-alvo="' + id + '" data-visao-chave="' + chave + '">' +
    '<label><input type="radio" name="v-' + chave + '" value="lista" checked></label>' +
    '<label><input type="radio" name="v-' + chave + '" value="cards"></label></div>' +
    '<div class="ls-visao-alvo" id="' + id + '" data-visao="lista" data-visao-acoes="barra">' +
    '<table class="ls-visao-tabela"><tbody>' + linhas + '</tbody></table></div>';
}

const completa =
  '<a class="btn btn-outline-primary" href="/previa/7/" target="_blank" rel="noopener" data-acao-cartao="Prévia" title="Conferir"><i class="bi bi-eye me-1"></i><span class="ls-action-label">Prévia do documento</span></a>' +
  '<button type="button" class="btn" data-editar="7" data-acao-cartao data-acao-ordem="1" aria-label="Editar Buffet Alegria"><i class="bi bi-pencil"></i><span class="ls-action-label">Editar</span></button>' +
  '<button type="button" class="btn" data-situacao="7"><i class="bi bi-flag"></i><span class="ls-action-label">Situação</span></button>' +
  '<form method="post"><button type="submit" class="btn btn-outline-danger" data-excluir="7"><i class="bi bi-trash"></i><span class="ls-action-label">Excluir</span></button></form>';
const umaSo = '<button type="button" class="btn btn-outline-danger" data-excluir="8"><i class="bi bi-trash"></i><span class="ls-action-label">Excluir</span></button>';
const semResto =
  '<button type="button" class="btn" data-editar="9" data-acao-cartao="Editar"><i class="bi bi-pencil"></i></button>' +
  '<button type="button" class="btn" data-dossie="9" data-acao-cartao="Histórico"><i class="bi bi-clock-history"></i></button>';
const semMarca =
  '<button type="button" class="btn btn-outline-danger" data-excluir="3"><i class="bi bi-trash"></i><span class="ls-action-label">Excluir</span></button>' +
  '<button type="button" class="btn" data-ver="3"><i class="bi bi-eye"></i><span class="ls-action-label">Ver</span></button>' +
  '<button type="button" class="btn" data-editar="3"><i class="bi bi-pencil"></i><span class="ls-action-label">Editar</span></button>' +
  '<button type="button" class="btn" data-copiar="3"><i class="bi bi-copy"></i><span class="ls-action-label">Copiar</span></button>';

const dom = new JSDOM(
  '<main class="ls-content">' +
  tabela('lista', 'teste', linha(7, 'Buffet Alegria', completa) + linha(8, 'João', umaSo) + linha(9, 'Ana', semResto)) +
  tabela('outra', 'livre', linha(3, 'Sem marca', semMarca)) +
  // uma lista que NÃO pediu a barra
  '<div class="ls-visao" data-visao-seletor data-visao-alvo="quieta" data-visao-chave="quieta">' +
  '<label><input type="radio" name="v-quieta" value="lista" checked></label>' +
  '<label><input type="radio" name="v-quieta" value="cards"></label></div>' +
  '<div class="ls-visao-alvo" id="quieta" data-visao="lista"><table class="ls-visao-tabela"><tbody>' +
  linha(5, 'Quieta', completa.replace(/7/g, '5')) + '</tbody></table></div>' +
  '<span data-v="avatar"><span class="ls-perfil-iniciais">BA</span><img id="logo" src="/nao-existe.png" alt=""></span>' +
  '</main>',
  { runScripts: 'outside-only', url: 'http://interno.localhost/clientes/' }
);
const w = dom.window;
const d = w.document;
w.requestAnimationFrame = function (fn) { return setTimeout(fn, 0); };
w.eval('var global = window; var Painel = {};\n' + agrupador + '\nwindow.Painel = Painel;');
w.Painel.organizarAcoesTabelas(d);
w.eval(listas);

const alvo = d.getElementById('lista');
function escolher(chave, modo) {
  const radio = d.querySelector('[data-visao-chave="' + chave + '"] input[value="' + modo + '"]');
  radio.checked = true;
  radio.dispatchEvent(new w.Event('change', { bubbles: true }));
}

/* ---- na lista, nada é montado ---- */
assert.equal(alvo.getAttribute('data-visao'), 'lista');
assert.equal(d.querySelectorAll('.ls-cartao-acoes').length, 0, 'a barra não pode nascer na lista');
assert.equal(d.querySelectorAll('.ls-action-fab-menu[data-folha]').length, 0);

/* ---- em cards ---- */
let cliques = [];
d.addEventListener('click', function (evento) {
  const acao = evento.target.closest('[data-editar],[data-excluir],[data-situacao],[data-dossie],a[href^="/previa/"]');
  if (acao && !acao.classList.contains('ls-cartao-acao')) {
    cliques.push(acao.getAttribute('data-editar') ? 'editar' : acao.getAttribute('data-excluir') ? 'excluir'
      : acao.getAttribute('data-dossie') ? 'dossie' : acao.tagName === 'A' ? 'previa' : 'situacao');
    evento.preventDefault();
  }
});
escolher('teste', 'cards');
assert.equal(alvo.getAttribute('data-visao'), 'cards');
assert.equal(w.localStorage.getItem('ls-visao:teste'), 'cards');

const linhas = alvo.querySelectorAll('tbody tr');
const celula = linhas[0].querySelector('td.ls-actions');
const barra = celula.querySelector('.ls-cartao-acoes');
assert.ok(barra, 'a linha com ações ganha a barra');
assert.equal(barra.getAttribute('data-visao-so'), 'cards');
assert.equal(barra.nextElementSibling.className, 'ls-row-actions', 'a barra fica antes do grupo, fora dele');
const botoes = barra.querySelectorAll('.ls-cartao-acao');
// só as marcadas, e na ordem pedida: Editar (ordem 1) antes da Prévia (sem ordem)
assert.deepEqual(Array.from(botoes).map((b) => b.textContent), ['Editar', 'Prévia']);
assert.equal(botoes[0].tagName, 'BUTTON');
assert.equal(botoes[0].type, 'button');
assert.equal(botoes[0].getAttribute('aria-label'), 'Editar Buffet Alegria');
assert.ok(botoes[0].classList.contains('ls-cartao-acao--principal'), 'a primeira é a principal');
assert.equal(botoes[0].querySelector('i').className, 'bi bi-pencil');
// o link continua link (botão do meio, abrir em outra aba), com o nome curto e sem a margem do ícone
assert.equal(botoes[1].tagName, 'A');
assert.equal(botoes[1].getAttribute('href'), '/previa/7/');
assert.equal(botoes[1].target, '_blank');
assert.equal(botoes[1].rel, 'noopener');
assert.equal(botoes[1].title, 'Conferir');
assert.equal(botoes[1].querySelector('i').className, 'bi bi-eye');
assert.equal(celula.getAttribute('data-barra-itens'), '3', 'duas ações e o Mais');

// o atalho aciona a ação de verdade, uma vez
botoes[0].click();
botoes[1].click();
assert.deepEqual(cliques, ['editar', 'previa']);

// "Mais" é o próprio "⋮" do painel, com nome
const fab = celula.querySelector('.ls-action-fab');
const gatilho = fab.querySelector('.ls-action-fab-trigger');
assert.equal(gatilho.querySelector('span[data-visao-so="cards"]').textContent, 'Mais');
assert.equal(gatilho.querySelector('i.bi-three-dots-vertical').getAttribute('data-visao-so'), 'lista');
assert.ok(gatilho.querySelector('i.bi-three-dots[data-visao-so="cards"]'));
assert.equal(gatilho.getAttribute('aria-haspopup'), 'menu');
assert.equal(gatilho.getAttribute('aria-label'), 'Mais ações deste registro');

// a folha: o que está na barra não se repete, o que apaga vem depois da linha
const menu = fab._lsMenu;
assert.equal(menu.getAttribute('data-folha'), '1');
assert.equal(menu.parentNode, d.body, 'o menu continua no <body>');
assert.equal(menu.querySelector('.ls-folha-nome').textContent, 'Buffet Alegria');
const naBarra = Array.from(menu.querySelectorAll('[data-na-barra]')).map((n) => n.textContent.trim());
assert.deepEqual(naBarra, ['Prévia do documento', 'Editar']);
const divisor = menu.querySelector('.ls-folha-divisor');
assert.ok(divisor, 'falta a linha antes do que apaga');
assert.equal(divisor.getAttribute('role'), 'separator');
// o que apaga é marcado (o CSS o manda para o fim, depois da linha); o menu não é reordenado
const perigo = menu.querySelectorAll(':scope > .ls-folha-perigo');
assert.equal(perigo.length, 1);
assert.ok(perigo[0].matches('form') && perigo[0].querySelector('[data-excluir="7"]'));
assert.deepEqual(
  Array.from(menu.querySelectorAll('.ls-action-label')).map((n) => n.textContent),
  ['Prévia do documento', 'Editar', 'Situação', 'Excluir'],
  'a ordem do menu é a que a tela escreveu'
);
// nada foi clonado: cada ação existe uma vez só, e o formulário veio junto
assert.equal(d.querySelectorAll('[data-editar="7"]').length, 1);
assert.equal(d.querySelectorAll('[data-excluir="7"]').length, 1);
assert.equal(menu.querySelector('[data-excluir="7"]').closest('form').method, 'post');

// "Mais" abre e fecha a folha (o comportamento é o do painel)
gatilho.click();
assert.ok(fab.classList.contains('is-open'));
assert.equal(gatilho.getAttribute('aria-expanded'), 'true');
assert.equal(menu.hidden, false);
menu.querySelector('[data-excluir="7"]').click();
assert.deepEqual(cliques.slice(2), ['excluir']);
assert.ok(!fab.classList.contains('is-open'), 'escolher uma ação fecha a folha');

// folha que só tem o que apaga (ou só o que não apaga) não tem o que separar
assert.equal(linhas[2].querySelector('.ls-action-fab')._lsMenu.querySelectorAll('.ls-folha-divisor').length, 0);

/* ---- a linha de uma ação só: sem menu, ela vai para a barra seja qual for ---- */
const sozinha = linhas[1].querySelector('td.ls-actions');
assert.equal(sozinha.querySelector('.ls-action-fab'), null);
const unico = sozinha.querySelectorAll('.ls-cartao-acao');
assert.equal(unico.length, 1);
assert.equal(unico[0].textContent, 'Excluir');
assert.ok(unico[0].classList.contains('ls-cartao-acao--perigo'));
assert.equal(sozinha.getAttribute('data-barra-itens'), '1');
unico[0].click();
assert.equal(cliques[cliques.length - 1], 'excluir');

/* ---- todas na barra: não sobra nada para o "Mais" ---- */
const cheia = linhas[2].querySelector('td.ls-actions');
assert.deepEqual(Array.from(cheia.querySelectorAll('.ls-cartao-acao')).map((b) => b.textContent), ['Editar', 'Histórico']);
assert.equal(cheia.querySelector('.ls-action-fab').getAttribute('data-sem-resto'), '1');
assert.equal(cheia.getAttribute('data-barra-itens'), '2');
assert.equal(alvo.hasAttribute('data-barra-cheia'), false, 'três na barra cabem lado a lado');

/* ---- montar de novo não duplica (a tela é montada a cada navegação) ---- */
w.LSVisao.montar(d);
w.Painel.organizarAcoesTabelas(d);
w.LSVisao.montar(alvo);
assert.equal(alvo.querySelectorAll('.ls-cartao-acoes').length, 3);
assert.equal(celula.querySelectorAll('.ls-cartao-acao').length, 2);
assert.equal(gatilho.querySelectorAll('span').length, 1);
assert.equal(menu.querySelectorAll('.ls-folha-divisor').length, 1);

/* ---- a tela que não marcou nada: as duas primeiras que não apagam ---- */
escolher('livre', 'cards');
const livre = d.getElementById('outra').querySelector('td.ls-actions');
assert.deepEqual(Array.from(livre.querySelectorAll('.ls-cartao-acao')).map((b) => b.textContent), ['Ver', 'Editar']);
const folhaLivre = livre.querySelector('.ls-action-fab')._lsMenu;
// "Excluir" é a primeira do menu; na folha ela desce para depois de "Copiar", separada pela linha
assert.equal(folhaLivre.querySelectorAll('.ls-folha-divisor').length, 1);
assert.ok(folhaLivre.querySelector(':scope > .ls-folha-perigo[data-excluir="3"]'));
assert.equal(folhaLivre.querySelector('.ls-folha-nome').textContent, 'Sem marca');

/* ---- a lista que não pediu a barra fica como estava ---- */
escolher('quieta', 'cards');
const quieta = d.getElementById('quieta');
assert.equal(quieta.getAttribute('data-visao'), 'cards');
assert.equal(quieta.querySelectorAll('.ls-cartao-acoes').length, 0);
const fabQuieto = quieta.querySelector('.ls-action-fab');
assert.equal(fabQuieto._lsMenu.hasAttribute('data-folha'), false);
assert.equal(fabQuieto.querySelector('.ls-action-fab-trigger').textContent, '');
assert.equal(fabQuieto.querySelector('.ls-action-fab-trigger').getAttribute('aria-label'), 'Abrir ações deste registro');

/* ---- de volta à lista: o menu volta a ser o de sempre ---- */
escolher('teste', 'lista');
assert.equal(alvo.getAttribute('data-visao'), 'lista');
assert.equal(menu.hasAttribute('data-folha'), false);
assert.equal(w.localStorage.getItem('ls-visao:teste'), 'lista');

/* ---- quatro na barra: a lista inteira empilha ícone e nome ---- */
const quatro = d.createElement('tr');
quatro.innerHTML = '<td data-rotulo="Ações" class="ls-actions"><div class="ls-row-actions">' +
  ['Um', 'Dois', 'Três', 'Quatro'].map((nome) => '<button type="button" class="btn" data-acao-cartao="' + nome + '"><i class="bi bi-star"></i></button>').join('') +
  '<button type="button" class="btn" data-situacao="1"><i class="bi bi-flag"></i><span class="ls-action-label">Situação</span></button></div></td>';
alvo.querySelector('tbody').appendChild(quatro);
escolher('teste', 'cards');
// no máximo três marcadas na barra; com o "Mais", quatro botões
assert.deepEqual(Array.from(quatro.querySelectorAll('.ls-cartao-acao')).map((b) => b.textContent), ['Um', 'Dois', 'Três']);
assert.equal(quatro.querySelector('td').getAttribute('data-barra-itens'), '4');
assert.equal(alvo.getAttribute('data-barra-cheia'), '1');

/* ---- a logo que não carregou dá lugar às iniciais ---- */
const logo = d.getElementById('logo');
logo.dispatchEvent(new w.Event('error'));
assert.equal(d.getElementById('logo'), null);
assert.equal(d.querySelector('[data-v="avatar"]').textContent, 'BA');

w.close();
console.log('OK: barra só em cards, atalhos sem clone, Mais com folha, ação única, sem resto, sem marca, lista quieta, quatro botões e logo quebrada.');
