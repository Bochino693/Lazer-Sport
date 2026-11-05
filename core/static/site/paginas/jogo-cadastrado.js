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

  function jogar() {
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
