const fs = require('fs');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync('/workspace/scratch/2ff5a8e27f7d/repo/sistema_interno/static/interno/ls-soft-navigation.js','utf8');
(async () => {
  for (const documentMode of [true, false]) {
    const dom = new JSDOM(`<html ${documentMode ? 'data-ls-navigation="document"' : ''}><head></head><body><main class="ls-content">Inicial</main><div id="lsTelaScripts"></div></body></html>`, {url:'https://interno.test/estoque/',runScripts:'outside-only'});
    const w=dom.window;
    let calls=0;
    w.scrollTo=()=>{};
    w.fetch=async url=>{ calls++; return {ok:true,status:200,url,headers:{get:()=> 'text/html'},text:async()=>'<html><head></head><body><main class="ls-content">Filtrado</main><div id="lsTelaScripts"></div></body></html>'}; };
    w.eval(source);
    const paths=['/abrir-site/loja/','/accounts/login/','https://www.lazersport.com.br/loja/'];
    if(documentMode) paths.push('/aplicativo/avisos/','/materiais/');
    for(const href of paths) {
      const a=w.document.createElement('a'); a.href=href; a.textContent='Abrir'; w.document.body.append(a);
      let prevented;
      const listener=e=>{prevented=e.defaultPrevented;e.preventDefault();};
      w.document.addEventListener('click',listener);
      a.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true,button:0}));
      w.document.removeEventListener('click',listener);
      assert.equal(prevented,false,href+' deve usar navegação nativa');
    }
    assert.equal(calls,0,'não buscar links de outro módulo');
    await w.LSNavigation.go('/estoque/?busca=arduino');
    assert.equal(calls,1,'filtro permanece assíncrono');
    assert.equal(w.document.querySelector('.ls-content').textContent,'Filtrado');
    const aviso=w.document.createElement('div'); aviso.id='lsNavRecovery';w.document.body.append(aviso);
    w.dispatchEvent(new w.PageTransitionEvent('pageshow',{persisted:true}));
    assert.equal(w.document.getElementById('lsNavRecovery'),null,'retorno pelo histórico limpa aviso antigo');
    dom.window.close();
  }
  const painel=fs.readFileSync('/workspace/scratch/2ff5a8e27f7d/repo/sistema_interno/static/interno/painel.js','utf8');
  const pintar=new Function(painel.slice(painel.indexOf('  function pintarSelo('),painel.indexOf('  function desenharAvisos('))+';return pintarSelo;')();
  const badge={dataset:{mostrarZero:'1'},textContent:'…',hidden:false};
  for(const n of [4,0,12]){pintar(badge,n);assert.equal(badge.textContent,n);assert.equal(badge.hidden,false);}
  console.log('OK: navegação nativa, filtros assíncronos, histórico limpa aviso e contador exibe inclusive zero.');
})().catch(e=>{console.error(e);process.exit(1);});
