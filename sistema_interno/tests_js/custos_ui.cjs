const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '..', 'templates');
(async () => {
  const material = fs.readFileSync(path.join(root, 'material_inner.html'), 'utf8');
  const modal = material.slice(material.indexOf('<div class="modal fade" id="modalCodigos"'), material.indexOf('<div class="modal fade" id="modalMaterial"'));
  const dom = new JSDOM(`<button id="preverCodigos">Prévia</button>${modal}`, {runScripts:'outside-only', url:'https://interno.test/'});
  const w = dom.window, d = w.document;
  let abriu = false, ligou = false;
  w.Painel = {
    erro:()=>{}, aviso:mensagem=>{throw new Error(mensagem)},
    enviar:async (form, extras)=>{
      assert.equal(extras.action, 'prever_codigos');
      return {status:'sucesso', alteracoes:[{nome:'<img src=x>', anterior:'0001', novo:'ard-0001'}]};
    },
    abrir:id=>{assert.equal(id, 'modalCodigos'); abriu=true},
    ligar:opcoes=>{assert.equal(opcoes.form, 'formCodigos'); ligou=true}
  };
  const inicio = material.indexOf('  document.getElementById("preverCodigos").addEventListener');
  w.eval(material.slice(inicio, material.indexOf('  var fotoMaterial =', inicio)));
  d.getElementById('preverCodigos').click();
  assert.equal(d.getElementById('preverCodigos').disabled, true);
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(abriu && ligou);
  assert.equal(d.getElementById('preverCodigos').disabled, false);
  assert.equal(d.querySelector('#codigosPrevia td').textContent, '<img src=x>');
  assert.equal(d.querySelector('#codigosPrevia img'), null);
  dom.window.close();

  const estoque = fs.readFileSync(path.join(root, 'estoque_inner.html'), 'utf8');
  const mov = new JSDOM('<select id="movimentoTipo"><option>entrada</option><option>saida</option><option>ajuste</option></select><input id="movimentoValor"><input id="movimentoFornecedor"><input id="movimentoDataCompra"><input id="movimentoMotivo"><div id="movimentoAjuda"></div>', {runScripts:'outside-only'});
  const start = estoque.indexOf('  document.getElementById("movimentoTipo").addEventListener');
  mov.window.eval(estoque.slice(start, estoque.indexOf('  Painel.ligar(', start)));
  const tipo = mov.window.document.getElementById('movimentoTipo');
  for (const valor of ['entrada', 'saida', 'ajuste', 'entrada']) {
    tipo.value = valor; tipo.dispatchEvent(new mov.window.Event('change'));
    const preco = mov.window.document.getElementById('movimentoValor');
    assert.equal(preco.required, valor === 'entrada');
    assert.equal(preco.disabled, valor !== 'entrada');
    assert.equal(mov.window.document.getElementById('movimentoMotivo').required, valor === 'ajuste');
  }
  mov.window.close();
  console.log('OK: prévia segura de códigos e campos contextuais de compras/saídas/ajustes.');
})().catch(erro=>{console.error(erro); process.exit(1)});
