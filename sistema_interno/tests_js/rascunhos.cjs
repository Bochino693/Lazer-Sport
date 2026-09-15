/* O rascunho das janelas de montagem, exercitado no DOM de verdade.

   O painel troca de TELA com navegação de documento
   (`data-ls-navigation="document"` em `base_inner.html`); a troca suave
   atende os filtros da mesma tela. Por isso o que faz o botão flutuante
   atravessar a tela não é o cache da navegação: é o `sessionStorage`, e
   é assim que este teste encena a travessia -- uma janela por tela, com
   o depósito da anterior reposto, exatamente como o navegador faria.

   O que se prova, na ordem em que a pessoa faz:
     1. a janela de montagem não fecha por clique fora;
     2. abrir e fechar sem mexer em nada NÃO deixa rascunho;
     3. fechar com coisa digitada deixa um botão flutuante;
     4. o botão devolve tudo o que estava na janela;
     5. gravar apaga o rascunho -- e só o dele;
     6. na tela de O.S., o rascunho do orçamento continua à vista, e a
        O.S. pendurada soma um SEGUNDO botão;
     7. tocar no botão de outra tela deixa o pedido anotado, e a tela de
        destino reabre a janela sozinha, inteira. */
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:8765';
const root=require('node:path').resolve(__dirname,'../..');
const MODULOS=['vendor/bootstrap.bundle.min.js','ls-busca.js','painel.js','ls-rascunhos.js','ls-filtro-local.js','ls-soft-navigation.js'];
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));

function abrirTela(caminho, deposito){
 /* Tocar no rascunho de outra tela manda o navegador para lá de verdade,
    e o jsdom não navega: o aviso dele é esperado e não é falha. */
 const console_=new VirtualConsole();
 console_.on('jsdomError',()=>{});
 ['error','warn','info','log'].forEach(nivel=>console_.on(nivel,(...a)=>console[nivel](...a)));
 const dom=new JSDOM(fixture[caminho],{url:base+caminho,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:console_});
 const w=dom.window,d=w.document;
 w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
 w.scrollTo=()=>{}; w.HTMLElement.prototype.scrollIntoView=function(){};
 w.fetch=async (url,opt={})=>{
   const dest=new URL(url,w.location.href);
   if(opt.method==='POST'&&w.__falharPost) throw new TypeError('Failed to fetch');
   const payload=opt.method==='POST'
     ? {status:'sucesso',msg:'Salvo',id:77}
     : {status:'sucesso',resultados:[],itens:[],opcoes:[],avisos:[]};
   const resposta=new Response(JSON.stringify(payload),{headers:{'content-type':'application/json'}});
   Object.defineProperty(resposta,'url',{value:dest.href});return resposta;
 };
 w.LSTela={pronto:fn=>fn()};
 /* O depósito da tela anterior: é ele, e não a memória da página, que
    carrega o rascunho de uma tela para a outra. */
 Object.keys(deposito||{}).forEach(chave=>w.sessionStorage.setItem(chave,deposito[chave]));
 for(const f of MODULOS) w.eval(fs.readFileSync(root+'/sistema_interno/static/interno/'+f,'utf8'));
 for(const script of d.querySelectorAll('#lsTelaScripts script:not([src])'))
   if(script.type!=='application/json') w.eval(script.textContent);
 return dom;
}

function copiarDeposito(w){
 const copia={};
 for(let i=0;i<w.sessionStorage.length;i+=1){
   const chave=w.sessionStorage.key(i);
   if(chave.indexOf('ls:rascunho:')===0) copia[chave]=w.sessionStorage.getItem(chave);
 }
 return copia;
}

const pausa=ms=>new Promise(r=>setTimeout(r,ms));
async function espera(f,msg){for(let i=0;i<150;i++){if(f())return;await pausa(20);}throw Error(msg);}

(async()=>{
 /* ================= TELA 1: orçamentos ================= */
 let dom=abrirTela('/orcamentos/',null);
 let w=dom.window,d=w.document;
 const fabs=()=>Array.from(d.querySelectorAll('#lsRascunhos .ls-rascunho'));
 const fechar=async id=>{w.Painel.fechar(id);await espera(()=>!d.querySelector('#'+id+'.show'),'fechou '+id);await pausa(80);};

 /* 1. clicar fora não fecha mais */
 assert.equal(d.getElementById('modalOrcamento').getAttribute('data-bs-backdrop'),'static','janela protegida do clique fora');

 /* 2. abrir e fechar sem tocar em nada não deixa rascunho */
 d.getElementById('novoOrcamento').click();
 await espera(()=>d.querySelector('#modalOrcamento.show'),'janela abriu');
 await fechar('modalOrcamento');
 assert.equal(fabs().length,0,'janela intocada não vira rascunho');

 /* 3. fechar com coisa digitada deixa o botão */
 d.getElementById('novoOrcamento').click();
 await espera(()=>d.querySelector('#modalOrcamento.show'),'janela abriu de novo');
 d.getElementById('orcamentoNome').value='Buffet Arco-Íris';
 d.querySelector('#itensCorpo .ls-item-descricao').value='Cama elástica 3m';
 d.querySelector('#itensCorpo .ls-item-valor').value='450,00';
 d.getElementById('orcamentoObs').value='Entregar na véspera';
 await fechar('modalOrcamento');
 assert.equal(fabs().length,1,'um rascunho, um botão');
 assert.match(fabs()[0].textContent,/Orçamento em rascunho/);
 assert.match(fabs()[0].textContent,/Buffet Arco-Íris/,'o botão diz de quem é');

 /* 4. o botão devolve a janela inteira */
 fabs()[0].querySelector('.ls-rascunho-abrir').click();
 await espera(()=>d.querySelector('#modalOrcamento.show'),'rascunho reabriu');
 assert.equal(d.getElementById('orcamentoNome').value,'Buffet Arco-Íris');
 assert.equal(d.getElementById('orcamentoObs').value,'Entregar na véspera');
 assert.equal(d.querySelector('#itensCorpo .ls-item-descricao').value,'Cama elástica 3m');
 assert.equal(d.querySelector('#itensCorpo .ls-item-valor').value,'450,00');

 /* Retomar e fechar sem mexer continua guardando: retomar não é perder. */
 await fechar('modalOrcamento');
 assert.equal(fabs().length,1,'rascunho retomado e fechado continua guardado');

 /* GRAVAR UMA PROPOSTA NÃO APAGA O RASCUNHO DE OUTRA.
    A proposta da lista tem id; o rascunho pendurado é de uma proposta
    NOVA, ainda sem id. São chaves diferentes e precisam continuar
    sendo tratadas como duas coisas diferentes. */
 const paraEditar=d.querySelector('[data-editar]');
 assert(paraEditar,'a lista tem uma proposta para editar');
 paraEditar.click();
 await espera(()=>d.querySelector('#modalOrcamento.show'),'proposta da lista abriu');
 d.getElementById('orcamentoObs').value='Conferido no balcão';
 d.getElementById('formOrcamento').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await pausa(700);
 assert.equal(fabs().length,1,'o rascunho da proposta nova continua pendurado');
 assert.match(fabs()[0].textContent,/Buffet Arco-Íris/,'e continua sendo o dele');

 const daPrimeiraTela=copiarDeposito(w);
 assert.equal(Object.keys(daPrimeiraTela).length,1,'um rascunho no depósito');
 dom.window.close();

 /* ================= TELA 2: ordens de serviço ================= */
 dom=abrirTela('/ordens-servico/',daPrimeiraTela);
 w=dom.window;d=w.document;
 const fabsOS=()=>Array.from(d.querySelectorAll('#lsRascunhos .ls-rascunho'));

 /* 6. o rascunho do orçamento continua à vista em outra tela */
 assert.equal(fabsOS().length,1,'o rascunho do orçamento atravessou a troca de tela');
 assert.equal(d.getElementById('modalOS').getAttribute('data-bs-backdrop'),'static','janela da O.S. protegida');
 assert.equal(
   d.querySelector('#modalOS .modal-body [data-fechar-filho-os]')||
   d.getElementById('modalPecaOS').getAttribute('data-bs-backdrop'),null,
   'camada filha da O.S. não usa backdrop do Bootstrap');

 d.getElementById('novaOS').click();
 await espera(()=>d.querySelector('#modalOS.show'),'janela da O.S. abriu');
 d.getElementById('osNome').value='Condomínio Vila Nova';
 d.getElementById('osDefeito').value='Motor do inflável falhando';
 w.Painel.fechar('modalOS');
 await espera(()=>!d.querySelector('#modalOS.show'),'O.S. fechou');
 await pausa(80);
 assert.equal(fabsOS().length,2,'orçamento e O.S. pendurados são dois botões');
 assert.deepEqual(
   fabsOS().map(f=>f.querySelector('strong').textContent).sort(),
   ['Ordem de serviço em rascunho','Orçamento em rascunho']);

 /* 7. tocar no botão de outra tela deixa o pedido anotado */
 fabsOS().find(f=>/Orçamento/.test(f.textContent)).querySelector('.ls-rascunho-abrir').click();
 const pedido=w.sessionStorage.getItem('ls:rascunho:abrir');
 assert(pedido&&pedido.indexOf('orcamento')>0,'o pedido de retomada ficou anotado');

 const dasDuasTelas=copiarDeposito(w);
 dasDuasTelas['ls:rascunho:abrir']=pedido;
 dom.window.close();

 /* ============ TELA 3: de volta aos orçamentos, pelo botão ============ */
 dom=abrirTela('/orcamentos/',dasDuasTelas);
 w=dom.window;d=w.document;
 const fabsFim=()=>Array.from(d.querySelectorAll('#lsRascunhos .ls-rascunho'));
 await espera(()=>d.querySelector('#modalOrcamento.show'),'a tela de destino reabriu a janela sozinha');
 assert.equal(d.getElementById('orcamentoNome').value,'Buffet Arco-Íris');
 assert.equal(d.querySelector('#itensCorpo .ls-item-valor').value,'450,00');
 assert.equal(w.sessionStorage.getItem('ls:rascunho:abrir'),null,'pedido atendido sai do depósito');

 /* A REDE CAINDO NO MEIO NÃO PODE ASSUSTAR NEM APAGAR NADA. */
 w.__falharPost=true;
 d.getElementById('formOrcamento').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await espera(()=>!d.getElementById('orcamentoErro').classList.contains('d-none'),'o erro apareceu');
 const recado=d.getElementById('orcamentoErro').textContent;
 assert.match(recado,/conexão caiu/i,'o recado diz o que houve');
 assert.match(recado,/Nada foi perdido/i,'e diz que nada foi perdido');
 assert(!/Failed to fetch/.test(recado),'nada de mensagem crua do navegador');
 assert.equal(d.querySelector('#modalOrcamento.show')!==null,true,'a janela continua aberta com tudo dentro');
 assert.equal(d.getElementById('orcamentoNome').value,'Buffet Arco-Íris');
 w.__falharPost=false;

 /* 5. gravar apaga o rascunho -- e só o dele */
 d.getElementById('formOrcamento').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await espera(()=>!fabsFim().some(f=>/Orçamento em rascunho/.test(f.textContent)),'gravou e o rascunho saiu');
 assert.equal(fabsFim().length,1,'o rascunho da O.S. continua lá');

 /* GRAVAR PASSA PELO GUARDADOR DUAS VEZES, e esta é a sequência real:
    o aviso de gravação, a troca de tela que vem logo atrás (e que
    precisa guardar janelas ainda abertas) e, por último, o `hidden` da
    janela que está se fechando. Nenhuma das duas últimas pode recriar o
    rascunho do que acabou de ser salvo. */
 d.getElementById('novoOrcamento').click();
 await espera(()=>d.querySelector('#modalOrcamento.show'),'janela abriu para a segunda gravação');
 d.getElementById('orcamentoNome').value='Escola Girassol';
 d.querySelector('#itensCorpo .ls-item-descricao').value='Tobogã inflável';
 d.querySelector('#itensCorpo .ls-item-valor').value='300,00';
 d.getElementById('formOrcamento').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await espera(()=>d.getElementById('modalOrcamento').dataset.lsModalEstado==='hide','gravação mandou fechar');
 w.Painel.prepararNavegacao();
 await pausa(700);
 assert.equal(fabsFim().length,1,'gravar não ressuscita o rascunho do que foi salvo');

 /* Descartar é explícito, e funciona. */
 fabsFim()[0].querySelector('.ls-rascunho-descartar').click();
 assert.equal(fabsFim().length,0,'descartado');

 console.log(JSON.stringify({ok:true,checks:[
   'clique fora não fecha','janela intocada não vira rascunho','fechar guarda e mostra o botão',
   'o botão devolve a janela inteira','gravar uma proposta não apaga o rascunho de outra','o rascunho atravessa a troca de tela',
   'orçamento e O.S. são dois botões','o pedido de outra tela reabre a janela',
   'falha de rede explica e não apaga nada','gravar apaga só o rascunho gravado','gravar não ressuscita o rascunho','descartar funciona'
 ]}));
 dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
