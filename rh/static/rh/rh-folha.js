/* As folhas do RH: o botão "Salvar em PDF" abre a impressão do navegador
   (onde se escolhe "Salvar como PDF"); com ?imprimir=1 ela abre sozinha. */
(function () {
  "use strict";
  var botao = document.querySelector("[data-rh-imprimir]");
  if (!botao) return;
  botao.addEventListener("click", function () { window.print(); });
  if (botao.getAttribute("data-imprimir-ao-abrir") === "1") {
    window.addEventListener("load", function () { setTimeout(function () { window.print(); }, 350); });
  }
})();
