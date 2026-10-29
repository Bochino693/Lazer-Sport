/* ======================================================================
   CABEÇALHO: os grupos do menu, a lupa e o item da página atual.

   Os grupos abrem por toque/clique (e por teclado), e no computador
   também ao passar o mouse -- isso é só CSS. O clique é que precisa de
   script: no celular e no tablet não existe "passar por cima".
   ====================================================================== */
(function () {
  "use strict";

  var grupos = Array.prototype.slice.call(document.querySelectorAll("[data-topo-grupo]"));

  function fechar(excecao) {
    grupos.forEach(function (grupo) {
      if (grupo === excecao) return;
      grupo.classList.remove("aberto");
      var botao = grupo.querySelector("button");
      if (botao) botao.setAttribute("aria-expanded", "false");
    });
  }

  grupos.forEach(function (grupo) {
    var botao = grupo.querySelector("button");
    if (!botao) return;
    botao.addEventListener("click", function (evento) {
      evento.stopPropagation();
      var abrir = !grupo.classList.contains("aberto");
      fechar(grupo);
      grupo.classList.toggle("aberto", abrir);
      botao.setAttribute("aria-expanded", abrir ? "true" : "false");
    });
    // Escolher um item fecha o grupo (a página pode só rolar até a seção).
    grupo.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { fechar(); });
    });
  });

  document.addEventListener("click", function (evento) {
    if (!evento.target.closest("[data-topo-grupo]")) fechar();
  });

  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape") fechar();
  });

  // A lupa traz a busca para perto e já deixa o cursor no campo.
  var lupa = document.querySelector("[data-topo-busca]");
  var campo = document.querySelector("#busca input[name='q']");
  if (lupa && campo) {
    lupa.addEventListener("click", function (evento) {
      evento.preventDefault();
      var secao = document.getElementById("busca");
      secao.classList.add("em-foco");
      secao.scrollIntoView({ behavior: "smooth", block: "center" });
      window.setTimeout(function () { campo.focus({ preventScroll: true }); }, 250);
      window.setTimeout(function () { secao.classList.remove("em-foco"); }, 1600);
    });
  }

  // O item da página em que se está fica marcado (Arena, Loja...).
  var caminho = window.location.pathname;
  document.querySelectorAll(".ls-topo-nav a, .ls-barra-app a, #ls-mobile-nav a").forEach(function (link) {
    var destino;
    try { destino = new URL(link.href, window.location.href).pathname; } catch (erro) { return; }
    if (destino !== "/" && caminho.indexOf(destino) === 0) link.setAttribute("aria-current", "page");
  });

  // O topo encolhe um pouco depois de rolar: mais tela para o conteúdo.
  var topo = document.querySelector(".ls-topo");
  if (topo) {
    var agendado = false;
    window.addEventListener("scroll", function () {
      if (agendado) return;
      agendado = true;
      window.requestAnimationFrame(function () {
        agendado = false;
        topo.classList.toggle("ls-topo--compacto", window.scrollY > 60);
      });
    }, { passive: true });
  }
})();
