/* =========================================================================
   O PASSE DOS JOGOS (core/escudo_jogos.py): o endereço dos arquivos do jogo
   não vem na página. O navegador resolve a "prova de trabalho" do desafio
   que o site assinou -- achar o número que, junto com o sorteio, dá um
   SHA-256 começando com N bits zero -- e troca a resposta pela lista de onde
   baixar. Uma fração de segundo para quem joga; caro para robô em massa.

   A lista fica guardada no aparelho: sem internet, o jogo já guardado abre
   com ela (os arquivos o jogo-guardado.js já tem).

   window.LSPasse.pegar(passe, jogo, aoConferir) -> Promise de {nome: {partes, tamanhos}}
   window.LSPasse.juntar(itens, lista) -> os itens com as partes
   ========================================================================= */
(function () {
  "use strict";

  /* ---------------------------------------------------------------- SHA-256 (um bloco) */
  var K = new Int32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ]);
  var W = new Int32Array(64);
  /* Os primeiros 32 bits do SHA-256 de um texto ASCII curto (até 55 letras: um bloco só). */
  function sha256Inicio(texto) {
    var n = texto.length, i;
    for (i = 0; i < 16; i++) W[i] = 0;
    for (i = 0; i < n; i++) W[i >> 2] |= texto.charCodeAt(i) << (24 - (i & 3) * 8);
    W[n >> 2] |= 0x80 << (24 - (n & 3) * 8);
    W[15] = n * 8;
    for (i = 16; i < 64; i++) {
      var a15 = W[i - 15], a2 = W[i - 2];
      var s0 = ((a15 >>> 7) | (a15 << 25)) ^ ((a15 >>> 18) | (a15 << 14)) ^ (a15 >>> 3);
      var s1 = ((a2 >>> 17) | (a2 << 15)) ^ ((a2 >>> 19) | (a2 << 13)) ^ (a2 >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) | 0;
    }
    var a = 0x6a09e667, b = 0xbb67ae85 | 0, c = 0x3c6ef372, d = 0xa54ff53a | 0;
    var e = 0x510e527f, f = 0x9b05688c | 0, g = 0x1f83d9ab, h = 0x5be0cd19;
    for (i = 0; i < 64; i++) {
      var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      var t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[i] + W[i]) | 0;
      var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      var t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    return (a + 0x6a09e667) >>> 0;
  }

  /* A conta: em pedaços, devolvendo a vez ao navegador (a abertura continua animada). */
  var proximo = (function () {
    if (typeof MessageChannel === "undefined") return function (fn) { setTimeout(fn, 0); };
    var canal = new MessageChannel(), fila = [];
    canal.port1.onmessage = function () { var fn = fila.shift(); if (fn) fn(); };
    return function (fn) { fila.push(fn); canal.port2.postMessage(0); };
  })();
  function resolver(desafio, bits) {
    var sorteio = String(desafio).split(".")[1] || "";
    var prefixo = sorteio + ":";
    var corte = 32 - bits;
    return new Promise(function (ok) {
      var nonce = 0;
      (function rodada() {
        var fim = nonce + 25000;
        for (; nonce < fim; nonce++) {
          if ((sha256Inicio(prefixo + nonce) >>> corte) === 0) { ok(String(nonce)); return; }
        }
        proximo(rodada);
      })();
    });
  }

  /* ---------------------------------------------------------------- a lista guardada */
  function chave(jogo) { return "ls-passe-lista-" + jogo; }
  function lerLista(jogo) {
    try { var l = JSON.parse(localStorage.getItem(chave(jogo)) || "null"); return l && typeof l === "object" ? l : null; } catch (e) { return null; }
  }
  function gravarLista(jogo, lista) {
    try { localStorage.setItem(chave(jogo), JSON.stringify(lista)); } catch (e) { /* aba anônima ou sem espaço */ }
  }
  function juntar(itens, lista) {
    return itens.map(function (item) {
      var dela = lista[item.nome];
      if (!dela) throw new Error("faltou o endereço de " + item.nome);
      var novo = {};
      Object.keys(item).forEach(function (k) { novo[k] = item[k]; });
      novo.partes = dela.partes;
      novo.tamanhos = dela.tamanhos;
      return novo;
    });
  }

  function csrf() {
    var achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return achado ? decodeURIComponent(achado[1]) : "";
  }
  function erroDeRede() { var e = new Error("sem internet"); e.rede = true; return e; }

  function pedir(url, desafio, bits, nonce) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ desafio: desafio, nonce: nonce, sinais: { webdriver: navigator.webdriver === true } })
    }).catch(function () { throw erroDeRede(); }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (corpo) { return { status: r.status, corpo: corpo }; });
    });
  }

  /* O passe: resolve, pede; desafio vencido ou repetido -> o site manda outro e tenta de novo. */
  function pegar(passe, jogo, aoConferir) {
    var guardada = lerLista(jogo);
    if (!passe || !passe.url) return guardada ? Promise.resolve(guardada) : Promise.reject(new Error("sem passe"));
    if (navigator.onLine === false && guardada) return Promise.resolve(guardada);
    var tentativas = 0;
    function rodar(desafio, bits) {
      tentativas += 1;
      if (aoConferir) aoConferir();
      return resolver(desafio, bits).then(function (nonce) { return pedir(passe.url, desafio, bits, nonce); }).then(function (r) {
        if (r.status === 200 && r.corpo && Array.isArray(r.corpo.arquivos)) {
          var lista = {};
          r.corpo.arquivos.forEach(function (a) { lista[a.nome] = { partes: a.partes, tamanhos: a.tamanhos }; });
          gravarLista(jogo, lista);
          return lista;
        }
        if (r.status === 409 && r.corpo && r.corpo.desafio && tentativas < 4) return rodar(r.corpo.desafio, r.corpo.bits);
        var erro = new Error((r.corpo && r.corpo.erro) || "o site não liberou o jogo agora (" + r.status + ")");
        erro.recusado = true;
        throw erro;
      });
    }
    return rodar(passe.desafio, passe.bits).catch(function (erro) {
      // sem internet (ou o site fora do ar): o jogo já guardado abre com a lista do aparelho
      if (erro.rede && guardada) return guardada;
      throw erro;
    });
  }

  window.LSPasse = { pegar: pegar, juntar: juntar, lerLista: lerLista, _sha256Inicio: sha256Inicio };
})();
