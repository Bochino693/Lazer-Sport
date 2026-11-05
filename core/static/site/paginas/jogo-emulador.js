/* ======================================================================
   O QUADRO DO EMULADOR: liga o EmulatorJS do próprio site a este jogo.

   A configuração vem do servidor (core/views_jogos.config_do_emulador):
   o núcleo do console, o arquivo que o emulador abre (o .cue, o .m3u, a
   ROM) e os que vão ao lado na pasta virtual dele -- as faixas .bin, os
   outros discos, a BIOS -- cada um com o nome exato que o índice pede.

   POR QUE ESTE ARQUIVO BAIXA AS FAIXAS, E NÃO O EMULADOR. O EmulatorJS
   4.2.3 grava cada "arquivo externo" baixado num formato que a pasta
   virtual dele recusa (ArrayBuffer em vez de Uint8Array): o arquivo fica
   criado e VAZIO, sem erro na tela -- o .cue achava as faixas, mas cada
   uma com 0 byte. Entregando os bytes já baixados (Uint8Array), ele grava
   certo. E de quebra a pessoa vê o progresso: um disco de PS1 tem
   centenas de MB, e sem isso a tela ficava parada sem dizer nada.
   ====================================================================== */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var bruto = document.getElementById("emuladorConfig");
  if (!bruto) return;
  var config = JSON.parse(bruto.textContent || "{}");
  if (!config.core || !config.jogo) return;
  var palco = document.getElementById("jogo");

  function mb(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(bytes >= 10485760 ? 0 : 1).replace(".", ",") + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  var aviso = document.createElement("div");
  aviso.className = "emu-aviso";
  aviso.setAttribute("role", "status");
  var barra = document.createElement("div");
  barra.className = "emu-barra";
  barra.innerHTML = "<span></span>";
  function mostrar(texto, pct) {
    aviso.textContent = texto;
    if (typeof pct === "number") {
      barra.firstChild.style.width = Math.max(0, Math.min(100, pct)) + "%";
      aviso.appendChild(barra);
    }
  }

  function baixar(item, aoProgresso) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", item.url);
      xhr.responseType = "arraybuffer";
      xhr.addEventListener("progress", function (e) { aoProgresso(e.loaded); });
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300 && xhr.response) resolve(new Uint8Array(xhr.response));
        else reject(new Error(item.nome + " (erro " + xhr.status + ")"));
      };
      xhr.onerror = function () { reject(new Error(item.nome + " (sem conexão com o armazenamento)")); };
      xhr.send();
    });
  }

  function baixarTudo(itens) {
    var total = itens.reduce(function (t, i) { return t + (i.tamanho || 0); }, 0);
    var feitos = 0;
    var grande = total > 300 * 1048576 ? " — jogo grande: no celular pode não abrir" : "";
    var bytes = {};
    return itens.reduce(function (promessa, item) {
      return promessa.then(function () {
        return baixar(item, function (agora) {
          mostrar("Baixando o jogo: " + mb(feitos + agora) + " de " + mb(total) + grande, total ? (feitos + agora) / total * 100 : 0);
        }).then(function (dados) {
          feitos += item.tamanho || dados.length;
          bytes[item.caminho] = dados;
        });
      });
    }, Promise.resolve()).then(function () { return bytes; });
  }

  function ligarEmulador(externos) {
    window.EJS_player = "#jogo";
    window.EJS_core = config.core;
    window.EJS_gameUrl = config.jogo;
    window.EJS_gameName = config.nome;
    window.EJS_externalFiles = externos;
    window.EJS_pathtodata = config.dados;
    window.EJS_language = "pt-BR";
    window.EJS_color = config.cor || "#ff3df2";
    // quem abriu o quadro já tocou em "Jogar": o jogo começa sem outro toque
    window.EJS_startOnLoaded = true;
    // fora da barra: trapaça, jogo em rede (não há servidor), "sair do jogo"
    // (deixaria o quadro preto) e o gerenciador de cache
    window.EJS_Buttons = { cheat: false, netplay: false, exitEmulation: false, cacheManager: false };
    window.EJS_onGameStart = function () {
      // o emulador já copiou as faixas para a pasta dele: solta a cópia daqui (memória)
      Object.keys(externos).forEach(function (chave) { delete externos[chave]; });
    };
    var loader = document.createElement("script");
    loader.src = config.dados + "loader.js";
    document.body.appendChild(loader);
  }

  var itens = config.externos || [];
  if (!itens.length) {
    ligarEmulador({});
    return;
  }
  document.body.appendChild(aviso);
  mostrar("Baixando o jogo…", 0);
  baixarTudo(itens).then(function (bytes) {
    aviso.remove();
    ligarEmulador(bytes);
  }, function (erro) {
    mostrar("Não deu para baixar " + erro.message + ". Recarregue a página para tentar de novo.");
    if (palco) palco.setAttribute("aria-busy", "false");
  });
})();
