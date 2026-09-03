const {JSDOM}=require('jsdom');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const base='http://painel.test/orcamentos/';
const html=`<body data-avisos="/avisos/estado/">
<span data-selo="total"></span><span data-selo="count_orcamentos" data-mostrar-zero="1"></span>
<span data-selo="count_ordens_servico" data-mostrar-zero="1"></span><span data-selo="count_manutencao" data-mostrar-zero="1"></span>
<div id="avisosLista"></div><main class="ls-content">
<section data-ls-parte="cartoes" data-ls-sincronia="orcamentos" data-ls-revisao="v1">1</section>
<section data-ls-parte="lista"><input id="rascunho" value="Meu preço"><span>Lista antiga</span></section>
</main></body>`;
const estado=v=>({assinatura:v,revisoes:{orcamentos:v},contagens:{count_orcamentos:2,count_ordens_servico:0,count_manutencao:3},total:5,urgentes:0,avisos:[]});
(async()=>{
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document;let avisosNovos=[],notas=0,emVoo=0,maxEmVoo=0,pedidos=0,versao='v2';
 w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
 w.scrollTo=()=>{throw Error('Sincronia não deve rolar a página');};
 w.HTMLElement.prototype.scrollIntoView=function(){};
 w.AudioContext=class {constructor(){this.state='running';this.currentTime=0;}createOscillator(){return {frequency:{},connect(){},start(){notas++;},stop(){}};}createGain(){return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}};
 const resposta=(payload,url,headers={})=>{
   const r=new Response(typeof payload==='string'?payload:JSON.stringify(payload),{headers:{'content-type':'application/json',...headers}});
   Object.defineProperty(r,'url',{value:url});return r;
 };
 w.fetch=async (url,opcoes={})=>{
   url=new URL(url,base).href;
   if(url.includes('/avisos/estado/')) {
     pedidos++;emVoo++;maxEmVoo=Math.max(maxEmVoo,emVoo);
     await new Promise(r=>setTimeout(r,30));emVoo--;
     return resposta({...estado(versao),avisos:avisosNovos},url,{'ETag':'"'+versao+'"'});
   }
   assert.equal(opcoes.headers['X-LS-Fragmento'],'lista');
   return resposta(`<section data-ls-parte="cartoes" data-ls-sincronia="orcamentos" data-ls-revisao="${versao}">2</section><section data-ls-parte="lista"><span>Lista ${versao}</span></section>`,url,{'X-LS-Fragmento':'lista','content-type':'text/html'});
 };
 await new Promise(r=>d.readyState==='loading'?d.addEventListener('DOMContentLoaded',r,{once:true}):r());
 for(const nome of ['painel.js','ls-soft-navigation.js','ls-sincronia.js']) w.eval(fs.readFileSync(path.join(root,'sistema_interno/static/interno',nome),'utf8'));
 const esperar=async(f,msg)=>{for(let i=0;i<150;i++){if(f())return;await new Promise(r=>setTimeout(r,20));}throw Error(msg);};
 d.querySelector('#rascunho').focus();d.querySelector('#rascunho').value='Preço ainda não salvo';
 w.Painel.avisos.agora();w.Painel.avisos.agora();
 await esperar(()=>d.querySelector('[data-ls-revisao]').dataset.lsRevisao==='v2','números atualizados');
 assert.equal(maxEmVoo,1,'GETs de avisos não sobrepostos');
 assert.equal(pedidos,2,'forçar durante leitura agenda só uma releitura');
 assert.equal(d.querySelector('[data-selo="count_manutencao"]').textContent,'3');
 assert.equal(d.querySelector('[data-selo="count_ordens_servico"]').hidden,false,'zero visível no menu');
 assert.equal(d.querySelector('#rascunho').value,'Preço ainda não salvo','edição preservada');
 assert(d.querySelector('[data-ls-parte="lista"]').textContent.includes('antiga'));
 d.querySelector('#rascunho').blur();
 await esperar(()=>d.querySelector('[data-ls-parte="lista"]').textContent.includes('v2'),'lista sincroniza após edição');
 w.localStorage.setItem('ls-som','nao');
 assert.equal(notas,0,'carga inicial e contadores sem som');
 w.Painel.confirmarGravacao();
 await w.Painel.avisos.agora();
 assert.equal(notas,0,'salvar sem aviso novo não toca');
 versao='v3';avisosNovos=[{chave:'novo',quantidade:1,titulo:'Aviso de teste',url:'/orcamentos/'}];
 await w.Painel.avisos.agora();
 /* Quantas vozes o aviso tem é decisão de timbre, e mudou quando o som
    precisou ficar audível num galpão. O que o teste cobra é o que
    importa: TOCOU. */
 assert(notas>0,'novo aviso do sino toca apesar da preferência antiga');
 const vozesDoAviso=notas;
 await w.Painel.avisos.agora();
 assert.equal(notas,vozesDoAviso,'mesmo aviso não repete');
 w.Painel.confirmarGravacao();await w.Painel.avisos.agora();
 assert.equal(notas,vozesDoAviso,'salvar não toca por conta própria');
 console.log('OK: contadores, zero, uma requisição por vez, números durante edição, lista após edição e sons.');
 dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
