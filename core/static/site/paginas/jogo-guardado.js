/* ======================================================================
   O JOGO GUARDADO NO APARELHO

   Um jogo de console são de poucos KB (um cartucho de NES) a centenas de
   MB (um disco de PS1). Baixar tudo a cada partida deixava a pessoa
   esperando sempre -- e gastava o plano de dados dela à toa.

   Aqui cada pedaço baixado fica guardado no próprio navegador (Cache
   Storage). Da segunda vez em diante o jogo abre do aparelho, na hora,
   mesmo com a internet ruim. A página do jogo (jogo-cadastrado.js) já
   começa a preparar o jogo enquanto a pessoa lê a página, e o quadro do
   emulador (jogo-emulador.js) só lê o que já está guardado.

   A CHAVE LEVA O TAMANHO. O endereço de um pedaço não muda quando a equipe
   troca o jogo no painel -- o índice (.cue) sai sempre do mesmo lugar --,
   mas a versão e o tamanho mudam: com eles na chave, o jogo novo nunca
   abre com um pedaço do velho.

   ESPAÇO. Antes de guardar, o navegador diz quanto cabe. Faltando, saem
   primeiro os jogos que a pessoa abriu há mais tempo; se ainda assim não
   couber, o jogo roda direto da internet, como antes, sem erro.
   ====================================================================== */
(function () {
  "use strict";
  var NOME = "ls-jogos-v1";
  var INDICE = "ls-jogos-guardados";
  var disponivel = typeof window.caches !== "undefined" && window.isSecureContext !== false;

  function chave(url, tamanho) {
    var u = new URL(url, location.href);
    u.searchParams.set("ls-tamanho", String(tamanho));
    return u.href;
  }

  function lerIndice() {
    try { return JSON.parse(localStorage.getItem(INDICE) || "{}") || {}; } catch (e) { return {}; }
  }
  function gravarIndice(indice) {
    try { localStorage.setItem(INDICE, JSON.stringify(indice)); } catch (e) { /* sem armazenamento: segue sem índice */ }
  }
  function marcarUso(jogo, chaves, bytes) {
    if (!jogo) return;
    var indice = lerIndice();
    var atual = indice[jogo] || { chaves: [], bytes: 0 };
    chaves.forEach(function (c) { if (atual.chaves.indexOf(c) < 0) atual.chaves.push(c); });
    atual.bytes = Math.max(atual.bytes || 0, bytes || 0);
    atual.usado = Date.now();
    indice[jogo] = atual;
    gravarIndice(indice);
  }

  function abrir() {
    if (!disponivel) return Promise.resolve(null);
    return caches.open(NOME).catch(function () { return null; });
  }

  function pedirPersistencia() {
    // o navegador pode apagar o que é "provisório" quando falta espaço; pedindo
    // para guardar de vez, o jogo continua no aparelho entre uma visita e outra
    try { if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {}); } catch (e) { /* nada */ }
  }

  function espacoLivre() {
    if (!navigator.storage || !navigator.storage.estimate) return Promise.resolve(Infinity);
    return navigator.storage.estimate().then(function (e) {
      return Math.max(0, (e.quota || 0) - (e.usage || 0));
    }, function () { return Infinity; });
  }

  /* Abre espaço para `bytes`, tirando os jogos usados há mais tempo (menos o atual). */
  function abrirEspaco(cache, bytes, jogoAtual) {
    return espacoLivre().then(function (livre) {
      var folga = bytes * 1.1 + 8 * 1048576;
      if (livre >= folga) return true;
      var indice = lerIndice();
      var outros = Object.keys(indice).filter(function (j) { return j !== jogoAtual; })
        .sort(function (a, b) { return (indice[a].usado || 0) - (indice[b].usado || 0); });
      if (!outros.length || !cache) return false;
      var sai = outros[0];
      return Promise.all((indice[sai].chaves || []).map(function (c) { return cache.delete(c); })).then(function () {
        delete indice[sai];
        gravarIndice(indice);
        return abrirEspaco(cache, bytes, jogoAtual);
      });
    });
  }

  function baixarParte(url, aoProgresso, sinal) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", url);
      xhr.responseType = "arraybuffer";
      xhr.addEventListener("progress", function (e) { if (aoProgresso) aoProgresso(e.loaded); });
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300 && xhr.response) resolve(new Uint8Array(xhr.response));
        else reject(new Error("erro " + xhr.status));
      };
      xhr.onerror = function () { reject(new Error("sem conexão com o armazenamento")); };
      xhr.onabort = function () { var e = new Error("cancelado"); e.cancelado = true; reject(e); };
      if (sinal) {
        if (sinal.aborted) { xhr.abort(); return; }
        sinal.addEventListener("abort", function () { xhr.abort(); });
      }
      xhr.send();
    });
  }

  function lerGuardada(cache, url, tamanho) {
    if (!cache) return Promise.resolve(null);
    return cache.match(chave(url, tamanho)).then(function (resposta) {
      if (!resposta) return null;
      return resposta.arrayBuffer().then(function (dados) {
        return dados.byteLength === tamanho ? new Uint8Array(dados) : null;
      });
    }).catch(function () { return null; });
  }

  function guardar(cache, url, tamanho, dados) {
    if (!cache) return Promise.resolve(false);
    var resposta = new Response(dados, { headers: { "Content-Type": "application/octet-stream" } });
    return cache.put(chave(url, tamanho), resposta).then(function () { return true; }, function () { return false; });
  }

  /* As partes de todos os arquivos, com o tamanho de cada uma. */
  function partesDe(itens) {
    var lista = [];
    itens.forEach(function (item) {
      item.partes.forEach(function (url, i) {
        lista.push({ url: url, tamanho: (item.tamanhos || [])[i] != null ? item.tamanhos[i] : item.tamanho });
      });
    });
    return lista;
  }

  /* Quantos bytes ainda faltam guardar (0 = o jogo abre na hora). */
  function quantoFalta(itens) {
    return abrir().then(function (cache) {
      if (!cache) return partesDe(itens).reduce(function (t, p) { return t + p.tamanho; }, 0);
      return Promise.all(partesDe(itens).map(function (p) {
        return cache.match(chave(p.url, p.tamanho)).then(function (r) { return r ? 0 : p.tamanho; }, function () { return p.tamanho; });
      })).then(function (faltas) { return faltas.reduce(function (t, f) { return t + f; }, 0); });
    });
  }

  /* Baixa e guarda o que falta, sem montar nada na memória (é o "preparar" da página). */
  function preparar(jogo, itens, aoProgresso, sinal) {
    pedirPersistencia();
    return abrir().then(function (cache) {
      if (!cache) return { guardado: false };
      var partes = partesDe(itens);
      var total = partes.reduce(function (t, p) { return t + p.tamanho; }, 0);
      var feitos = 0;
      return abrirEspaco(cache, total, jogo).then(function (cabe) {
        if (!cabe) return { guardado: false, semEspaco: true };
        return partes.reduce(function (promessa, parte) {
          return promessa.then(function () {
            var k = chave(parte.url, parte.tamanho);
            return cache.match(k).then(function (existe) {
              if (existe) { feitos += parte.tamanho; if (aoProgresso) aoProgresso(feitos, total); return; }
              return baixarParte(parte.url, function (agora) { if (aoProgresso) aoProgresso(feitos + agora, total); }, sinal)
                .then(function (dados) {
                  if (dados.length !== parte.tamanho) throw new Error("tamanho diferente do esperado");
                  return guardar(cache, parte.url, parte.tamanho, dados).then(function () {
                    feitos += parte.tamanho;
                    marcarUso(jogo, [k], total);
                  });
                });
            });
          });
        }, Promise.resolve()).then(function () {
          marcarUso(jogo, partes.map(function (p) { return chave(p.url, p.tamanho); }), total);
          return { guardado: true };
        });
      });
    });
  }

  /* Um arquivo inteiro, do aparelho quando já está guardado; senão baixa (e guarda). */
  function pegarArquivo(jogo, item, aoProgresso, cache, podeGuardar) {
    var bloco = new Uint8Array(item.tamanho);
    var posicao = 0;
    var doAparelho = true;
    return item.partes.reduce(function (promessa, url, i) {
      return promessa.then(function () {
        var tamanho = (item.tamanhos || [])[i] != null ? item.tamanhos[i] : item.tamanho;
        return lerGuardada(cache, url, tamanho).then(function (guardada) {
          if (guardada) return guardada;
          doAparelho = false;
          return baixarParte(url, function (agora) { aoProgresso(posicao + agora, false); }).then(function (dados) {
            if (podeGuardar && dados.length === tamanho) {
              return guardar(cache, url, tamanho, dados).then(function (ok) {
                if (ok) marcarUso(jogo, [chave(url, tamanho)], 0);
                return dados;
              });
            }
            return dados;
          });
        }).then(function (dados) {
          if (posicao + dados.length > bloco.length) throw new Error("tamanho diferente do esperado");
          bloco.set(dados, posicao);
          posicao += dados.length;
          aoProgresso(posicao, doAparelho);
        }, function (erro) {
          throw new Error(item.nome + (item.partes.length > 1 ? " (pedaço " + (i + 1) + " de " + item.partes.length + ")" : "") + ": " + erro.message);
        });
      });
    }, Promise.resolve()).then(function () {
      if (posicao !== bloco.length) throw new Error(item.nome + ": chegou incompleto");
      return { dados: bloco, doAparelho: doAparelho };
    });
  }

  /* Todos os arquivos do jogo, prontos para o emulador. */
  function pegarTudo(jogo, itens, aoProgresso) {
    pedirPersistencia();
    var total = itens.reduce(function (t, i) { return t + i.tamanho; }, 0);
    return abrir().then(function (cache) {
      return (cache ? abrirEspaco(cache, total, jogo) : Promise.resolve(false)).then(function (cabe) {
        var feitos = 0;
        var tudoDoAparelho = true;
        var bytes = {};
        return itens.reduce(function (promessa, item) {
          return promessa.then(function () {
            return pegarArquivo(jogo, item, function (agora, doAparelho) {
              aoProgresso(feitos + agora, total, doAparelho);
            }, cache, cabe).then(function (r) {
              feitos += item.tamanho;
              tudoDoAparelho = tudoDoAparelho && r.doAparelho;
              bytes[item.caminho] = r.dados;
            });
          });
        }, Promise.resolve()).then(function () {
          marcarUso(jogo, [], total);
          return { bytes: bytes, doAparelho: tudoDoAparelho };
        });
      });
    });
  }

  window.LSJogoGuardado = {
    disponivel: disponivel,
    quantoFalta: quantoFalta,
    preparar: preparar,
    pegarTudo: pegarTudo,
  };
})();
