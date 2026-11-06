/* =========================================================================
   O PROGRESSO DOS JOGOS NO APARELHO: "Continuar de onde parou".

   O reprodutor (jogo-emulador.js) guarda aqui o ESTADO do jogo -- o ponto
   exato, como um "save" instantâneo -- quando a pessoa sai (fecha a aba,
   troca de app, aperta Voltar) e a cada minuto jogando. Na próxima vez, a
   abertura oferece "Continuar de onde parou".

   Fica no IndexedDB do aparelho (um estado por jogo; guarda os 8 jogos mais
   recentes, porque um estado de PlayStation tem uns 4 MB e o de Nintendo 64,
   uns 16 MB). O índice pequeno (jogo, quando, título) fica no localStorage,
   para a biblioteca saber na hora quem tem "Continuar".

   window.LSProgresso.ler(chave)          -> Promise de {estado, quando, imagem, titulo} ou null
   window.LSProgresso.gravar(chave, dados) -> Promise de true/false
   window.LSProgresso.apagar(chave)        -> Promise
   window.LSProgresso.indice()             -> {chave: {quando, titulo, jogo}} (na hora, sem esperar)
   ========================================================================= */
(function () {
  "use strict";
  var BANCO = "ls-jogos-progresso";
  var LOJA = "estados";
  var INDICE = "ls-progresso-indice";
  var MAXIMO = 8;
  var aberto = null;

  function abrir() {
    if (aberto) return aberto;
    aberto = new Promise(function (ok) {
      var pedido;
      try { pedido = window.indexedDB && window.indexedDB.open(BANCO, 1); } catch (e) { pedido = null; }
      if (!pedido) { ok(null); return; }
      pedido.onupgradeneeded = function () {
        if (!pedido.result.objectStoreNames.contains(LOJA)) pedido.result.createObjectStore(LOJA);
      };
      pedido.onsuccess = function () { ok(pedido.result); };
      pedido.onerror = function () { ok(null); };
      pedido.onblocked = function () { ok(null); };
    });
    return aberto;
  }

  function indice() {
    try { var i = JSON.parse(localStorage.getItem(INDICE) || "{}"); return i && typeof i === "object" ? i : {}; } catch (e) { return {}; }
  }
  function gravarIndice(i) {
    try { localStorage.setItem(INDICE, JSON.stringify(i)); } catch (e) { /* aba anônima */ }
  }

  function operar(modo, fazer) {
    return abrir().then(function (banco) {
      if (!banco) return null;
      return new Promise(function (ok) {
        var tx;
        try { tx = banco.transaction(LOJA, modo); } catch (e) { ok(null); return; }
        var resultado = null;
        var pedido = fazer(tx.objectStore(LOJA));
        if (pedido) pedido.onsuccess = function () { resultado = pedido.result; };
        tx.oncomplete = function () { ok(modo === "readonly" ? resultado : true); };
        tx.onerror = tx.onabort = function () { ok(modo === "readonly" ? null : false); };
      });
    });
  }

  function ler(chave) {
    return operar("readonly", function (loja) { return loja.get(chave); }).then(function (v) { return v || null; });
  }

  function apagar(chave) {
    var i = indice();
    delete i[chave];
    gravarIndice(i);
    return operar("readwrite", function (loja) { return loja.delete(chave); });
  }

  function gravar(chave, dados) {
    var valor = { estado: dados.estado, quando: dados.quando || Date.now(), imagem: dados.imagem || null, titulo: dados.titulo || "", jogo: dados.jogo || "" };
    return operar("readwrite", function (loja) { return loja.put(valor, chave); }).then(function (ok) {
      if (!ok) return false;
      var i = indice();
      i[chave] = { quando: valor.quando, titulo: valor.titulo, jogo: valor.jogo };
      // os mais antigos saem (o espaço do celular é de quem joga)
      var chaves = Object.keys(i).sort(function (a, b) { return (i[b].quando || 0) - (i[a].quando || 0); });
      var sobra = chaves.slice(MAXIMO);
      sobra.forEach(function (c) { delete i[c]; });
      gravarIndice(i);
      if (sobra.length) operar("readwrite", function (loja) { sobra.forEach(function (c) { loja.delete(c); }); return null; });
      return true;
    });
  }

  window.LSProgresso = { ler: ler, gravar: gravar, apagar: apagar, indice: indice };
})();
