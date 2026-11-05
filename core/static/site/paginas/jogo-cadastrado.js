/* ======================================================================
   A PÁGINA DE UM JOGO QUE A EQUIPE SUBIU (JogoCadastrado).

   O jogo só baixa quando a pessoa toca em "Jogar": aí nasce um quadro
   isolado (iframe com sandbox), que roda o jogo sem enxergar o resto do
   site -- não lê os cookies, o conteúdo da página nem o login. A tela
   cheia vale para o quadro inteiro.
   ====================================================================== */
(function () {
  "use strict";
  const palco = document.querySelector("[data-jogo]");
  if (!palco) return;
  const capa = palco.querySelector("[data-jogo-capa]");
  const botao = palco.querySelector("[data-jogo-jogar]");
  const telaCheia = palco.querySelector("[data-jogo-tela-cheia]");
  const src = palco.dataset.jogoSrc;
  if (!src || !botao) return;

  /* JOGO NA HORA (jogo-guardado.js). Enquanto a pessoa lê a página, o jogo já
     vai sendo guardado no aparelho; ao tocar em Jogar, o quadro abre o que está
     guardado. Jogo grande (disco de PS1) não começa sozinho -- seria gastar o
     plano de dados de quem só passou pela página: ele baixa no toque e fica
     guardado para a próxima vez. */
  const PREPARO_AUTOMATICO = 120 * 1048576;
  const aviso = palco.querySelector("[data-jogo-preparo]");
  const arquivosBruto = document.getElementById("jogoArquivos");
  let preparo = null;

  function mb(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(bytes >= 10485760 ? 0 : 1).replace(".", ",") + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }
  function avisar(texto) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = !texto;
  }

  /* O emulador e o núcleo do console, adiantados -- só na primeira vez: depois
     disso o próprio emulador guarda o núcleo no aparelho, e baixar de novo a
     cada visita seria gastar dados à toa. A versão do núcleo segue a do
     emulador: sem WebGL 2 ele usa a "legacy". */
  function preCarregarEmulador(info) {
    if (!info || !info.dados) return;
    const marca = "ls-emulador-" + (info.nucleo || "base");
    try { if (localStorage.getItem(marca)) return; } catch (e) { /* sem armazenamento: adianta mesmo assim */ }
    let webgl2 = false;
    try { webgl2 = !!document.createElement("canvas").getContext("webgl2"); } catch (e) { webgl2 = false; }
    const lista = ["loader.js", "emulator.min.js", "emulator.min.css"];
    if (info.nucleo) lista.push("cores/" + info.nucleo + (webgl2 ? "" : "-legacy") + "-wasm.data");
    lista.forEach(function (arquivo) {
      const link = document.createElement("link");
      link.rel = "prefetch";
      link.href = info.dados + arquivo;
      document.head.appendChild(link);
    });
    botao.addEventListener("click", function () {
      try { localStorage.setItem(marca, "1"); } catch (e) { /* nada */ }
    }, { once: true });
  }

  function prepararJogo() {
    const guardado = window.LSJogoGuardado;
    if (!arquivosBruto || !guardado || !guardado.disponivel) return;
    let preparoDoServidor;
    try { preparoDoServidor = JSON.parse(arquivosBruto.textContent || "{}"); } catch (e) { return; }
    const dados = preparoDoServidor.config || {};
    preCarregarEmulador(preparoDoServidor);
    const itens = dados.arquivos || [];
    if (!itens.length) return;
    const total = itens.reduce(function (t, i) { return t + i.tamanho; }, 0);
    guardado.quantoFalta(itens).then(function (falta) {
      if (!falta) { avisar("Já está no aparelho: abre na hora."); return; }
      const economia = navigator.connection && navigator.connection.saveData;
      if (falta > PREPARO_AUTOMATICO || economia) {
        avisar("Na primeira vez baixa " + mb(falta) + "; depois fica guardado e abre na hora.");
        return;
      }
      const controle = typeof AbortController !== "undefined" ? new AbortController() : null;
      preparo = controle;
      avisar("Preparando o jogo…");
      guardado.preparar(dados.jogo, itens, function (feito) {
        avisar("Preparando o jogo: " + Math.min(99, Math.floor(feito / total * 100)) + "%");
      }, controle && controle.signal).then(function (r) {
        preparo = null;
        avisar(r && r.guardado ? "Pronto: abre na hora." : "");
      }, function () { preparo = null; avisar(""); });
    });
  }
  if (arquivosBruto) {
    // depois que a página terminou de abrir, para não disputar a rede com ela
    const comecar = function () { setTimeout(prepararJogo, 400); };
    if (document.readyState === "complete") comecar(); else window.addEventListener("load", comecar, { once: true });
  }

  function jogar() {
    // o toque manda: o preparo para, e o quadro continua do que já foi guardado
    if (preparo) { preparo.abort(); preparo = null; }
    const quadro = document.createElement("iframe");
    quadro.className = "jc-quadro";
    quadro.src = src;
    quadro.title = palco.dataset.jogoTitulo || "Jogo";
    // o quadro roda o jogo, mas fica preso nele: sem acesso ao site.
    // "allow-same-origin" só para jogo de OUTRO endereço (Cloudinary, itch.io...):
    // ele guarda o progresso no próprio domínio. Um arquivo servido pelo
    // domínio do site, com scripts e mesma origem juntos, sairia da caixa.
    let deFora = false;
    let doEmulador = false;
    try {
      const alvo = new URL(src, location.href);
      deFora = alvo.origin !== location.origin;
      // o quadro do emulador é uma página do próprio site, só com o código
      // do emulador (nenhum .html enviado roda nela): pode ter a mesma
      // origem, para o jogo salvo ficar guardado no navegador
      doEmulador = palco.dataset.jogoEmulador === "1" && !deFora && /^\/jogos\/[a-z0-9-]+\/emulador\/$/.test(alvo.pathname);
    } catch (e) { deFora = false; }
    const permissoes = ["allow-scripts", "allow-pointer-lock", "allow-orientation-lock", "allow-fullscreen"];
    if (deFora || doEmulador) permissoes.push("allow-same-origin");
    quadro.setAttribute("sandbox", permissoes.join(" "));
    quadro.setAttribute("allow", "autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-write");
    quadro.setAttribute("referrerpolicy", "no-referrer");
    quadro.setAttribute("loading", "eager");
    if (capa) capa.remove();
    palco.insertBefore(quadro, telaCheia || null);
    palco.classList.add("jc-palco--jogando");
    if (telaCheia) telaCheia.hidden = false;
    quadro.focus();
  }

  botao.addEventListener("click", jogar);

  // em tela cheia no celular, deita (ou levanta) a tela conforme o jogo
  function girarTela() {
    const orientacao = screen.orientation;
    if (!orientacao || !orientacao.lock) return;
    const deitado = palco.classList.contains("jc-palco--paisagem") || palco.classList.contains("jc-palco--largo");
    const emPe = palco.classList.contains("jc-palco--retrato");
    if (!deitado && !emPe) return;
    orientacao.lock(deitado ? "landscape" : "portrait").catch(function () {});
  }

  if (telaCheia) {
    telaCheia.addEventListener("click", function () {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else if (palco.requestFullscreen) {
        palco.requestFullscreen().then(girarTela).catch(function () {});
      }
    });
    document.addEventListener("fullscreenchange", function () {
      const icone = telaCheia.querySelector("i");
      if (icone) icone.className = document.fullscreenElement ? "fa-solid fa-compress" : "fa-solid fa-expand";
    });
  }
})();
