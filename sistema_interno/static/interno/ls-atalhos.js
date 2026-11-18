/* ======================================================================
   ATALHOS NO TOPO (LEIA-ME-V10, seção 114)

   Um botão por função; o toque abre o painel dela e fecha os outros.
   Fecha com Esc, com toque fora e ao escolher uma tela. O painel que
   passaria da borda direita da janela encosta nela. O topo não é trocado
   pela navegação suave, então isto se liga uma vez só.
   ====================================================================== */
(function () {
  "use strict";

  function botoes() {
    return Array.prototype.slice.call(document.querySelectorAll(".ls-atalho-botao"));
  }

  function fechar(botao) {
    var painel = document.getElementById(botao.getAttribute("aria-controls"));
    botao.setAttribute("aria-expanded", "false");
    if (painel) { painel.hidden = true; painel.style.left = ""; }
  }

  function fecharTodos(exceto) {
    botoes().forEach(function (botao) { if (botao !== exceto) fechar(botao); });
  }

  function abrir(botao) {
    var painel = document.getElementById(botao.getAttribute("aria-controls"));
    if (!painel) return;
    fecharTodos(botao);
    botao.setAttribute("aria-expanded", "true");
    painel.hidden = false;
    painel.style.left = "";
    var caixa = painel.getBoundingClientRect();
    var sobra = caixa.right - (window.innerWidth - 12);
    if (sobra > 0) painel.style.left = (-sobra) + "px";
  }

  function ligar() {
    var raiz = document.getElementById("lsAtalhos");
    if (!raiz || raiz.dataset.ligado === "1") return;
    raiz.dataset.ligado = "1";
    raiz.addEventListener("click", function (evento) {
      var botao = evento.target.closest(".ls-atalho-botao");
      if (botao) {
        if (botao.getAttribute("aria-expanded") === "true") fechar(botao); else abrir(botao);
        return;
      }
      if (evento.target.closest(".ls-atalho-painel a")) fecharTodos(null);
    });
    document.addEventListener("click", function (evento) {
      if (!evento.target.closest("#lsAtalhos")) fecharTodos(null);
    });
    document.addEventListener("keydown", function (evento) {
      if (evento.key !== "Escape") return;
      var aberto = botoes().filter(function (b) { return b.getAttribute("aria-expanded") === "true"; })[0];
      if (aberto) { fechar(aberto); aberto.focus(); }
    });
    window.addEventListener("resize", function () { fecharTodos(null); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ligar);
  else ligar();
})();
