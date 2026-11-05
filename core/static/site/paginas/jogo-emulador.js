/* ======================================================================
   O QUADRO DO EMULADOR: liga o EmulatorJS do próprio site a este jogo.

   A configuração vem do servidor (core/views_jogos.config_do_emulador):
   o núcleo do console e TODOS os arquivos do jogo -- o que o emulador
   abre (o .cue, o .m3u, a ROM) e os que vão ao lado na pasta virtual dele
   (as faixas .bin, os outros discos, a BIOS) --, cada um com o nome exato
   que o índice pede e com a lista de partes de onde baixar.

   POR QUE ESTE ARQUIVO BAIXA TUDO, E NÃO O EMULADOR.
   1. Arquivo grande fica guardado em PEDAÇOS (o Cloudinary aceita até 10
      MB por arquivo): aqui os pedaços são baixados e juntados, na ordem,
      num bloco só -- o emulador recebe o .bin inteiro.
   2. O EmulatorJS 4.2.3 grava os "arquivos externos" que ele mesmo baixa
      num formato que a pasta virtual recusa (ArrayBuffer em vez de
      Uint8Array): o arquivo fica criado e VAZIO, sem erro na tela.
      Entregando os bytes prontos, ele grava certo.
   3. Quem joga vê o progresso: um disco de PS1 tem centenas de MB.
   ====================================================================== */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var bruto = document.getElementById("emuladorConfig");
  if (!bruto) return;
  var config = JSON.parse(bruto.textContent || "{}");
  if (!config.core || !(config.arquivos || []).length) return;

  function mb(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(bytes >= 10485760 ? 0 : 1).replace(".", ",") + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  var aviso = document.createElement("div");
  aviso.className = "emu-aviso";
  aviso.setAttribute("role", "status");
  var texto = document.createElement("p");
  var barra = document.createElement("div");
  barra.className = "emu-barra";
  barra.appendChild(document.createElement("span"));
  aviso.appendChild(texto);
  aviso.appendChild(barra);
  function mostrar(mensagem, pct) {
    texto.textContent = mensagem;
    barra.hidden = typeof pct !== "number";
    if (!barra.hidden) barra.firstChild.style.width = Math.max(0, Math.min(100, pct)) + "%";
  }

  function baixarParte(url, aoProgresso) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", url);
      xhr.responseType = "arraybuffer";
      xhr.addEventListener("progress", function (e) { aoProgresso(e.loaded); });
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300 && xhr.response) resolve(new Uint8Array(xhr.response));
        else reject(new Error("erro " + xhr.status));
      };
      xhr.onerror = function () { reject(new Error("sem conexão com o armazenamento")); };
      xhr.send();
    });
  }

  /* Um arquivo: as partes, na ordem, num bloco só do tamanho certo. */
  function baixarArquivo(item, aoProgresso) {
    var bloco = new Uint8Array(item.tamanho);
    var posicao = 0;
    return item.partes.reduce(function (promessa, url, i) {
      return promessa.then(function () {
        return baixarParte(url, function (agora) { aoProgresso(posicao + agora); }).then(function (dados) {
          if (posicao + dados.length > bloco.length) throw new Error("tamanho diferente do esperado");
          bloco.set(dados, posicao);
          posicao += dados.length;
        }, function (erro) {
          throw new Error(item.nome + (item.partes.length > 1 ? " (pedaço " + (i + 1) + " de " + item.partes.length + ")" : "") + ": " + erro.message);
        });
      });
    }, Promise.resolve()).then(function () {
      if (posicao !== bloco.length) throw new Error(item.nome + ": chegou incompleto");
      return bloco;
    });
  }

  function baixarTudo(itens) {
    var total = itens.reduce(function (t, i) { return t + i.tamanho; }, 0);
    var feitos = 0;
    var grande = total > 300 * 1048576 ? " — jogo grande: no celular pode não abrir" : "";
    var bytes = {};
    return itens.reduce(function (promessa, item) {
      return promessa.then(function () {
        return baixarArquivo(item, function (agora) {
          mostrar("Baixando o jogo: " + mb(feitos + agora) + " de " + mb(total) + grande, total ? (feitos + agora) / total * 100 : 0);
        }).then(function (dados) {
          feitos += item.tamanho;
          bytes[item.caminho] = dados;
        });
      });
    }, Promise.resolve()).then(function () { return bytes; });
  }

  function ligarEmulador(jogo, externos) {
    window.EJS_player = "#jogo";
    window.EJS_core = config.core;
    // o jogo vai como bytes; o nome (com a extensão certa) diz ao emulador o que é
    window.EJS_gameUrl = jogo;
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
      // o emulador já copiou tudo para a pasta dele: solta as cópias daqui (memória)
      Object.keys(externos).forEach(function (chave) { delete externos[chave]; });
      window.EJS_gameUrl = null;
    };
    var loader = document.createElement("script");
    loader.src = config.dados + "loader.js";
    document.body.appendChild(loader);
  }

  document.body.appendChild(aviso);
  mostrar("Baixando o jogo…", 0);
  baixarTudo(config.arquivos).then(function (bytes) {
    var principal = config.arquivos.filter(function (a) { return a.principal; })[0];
    var jogo = bytes[principal.caminho];
    delete bytes[principal.caminho];
    aviso.remove();
    ligarEmulador(jogo, bytes);
  }, function (erro) {
    mostrar("Não deu para baixar o jogo — " + erro.message + ". Recarregue a página para tentar de novo.");
  });
})();
