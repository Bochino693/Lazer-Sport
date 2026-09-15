/* ======================================================================
   ESTRELAS — a nota de um produto, desenhada igual em toda tela.

   POR QUE UM MÓDULO, E NÃO UM PEDAÇO DE SCRIPT EM CADA PÁGINA. Cada tela
   que mostrava avaliação trazia a sua própria versão: uma escrevia "★"
   como texto e recortava a metade com `overflow:hidden`, outra desenhava
   SVG. Duas notas iguais apareciam diferentes conforme a página -- e a
   que usava texto mudava de forma conforme a fonte do aparelho, porque
   "★" não é um desenho, é um caractere que cada sistema escreve do seu
   jeito.

   Aqui é SVG, que é o mesmo desenho em todo lugar, e a meia-estrela sai
   de um gradiente que corta exatamente no meio -- e não de um
   recorte por cima de outra estrela.

   COMO USAR, no HTML:

     <span class="ls-estrelas" data-nota="4.5"
           role="img" aria-label="4,5 de 5"></span>

   O módulo procura sozinho, na carga e a cada `ls:estrelas` disparado no
   documento -- que é o gancho para quem reordena ou troca a lista sem
   recarregar a página.
   ====================================================================== */
(function (janela, documento) {
  "use strict";

  var sequencia = 0;

  function paraNumero(valor) {
    var numero = parseFloat(String(valor == null ? "" : valor).replace(",", "."));
    return isNaN(numero) ? 0 : numero;
  }

  var CONTORNO =
    "M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896 "
    + "4.664 22.774l1.402-8.176L.132 9.21l8.2-1.192z";

  function cheia() {
    return '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
      + '<path d="' + CONTORNO + '"></path></svg>';
  }

  function vazia() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">'
      + '<path d="' + CONTORNO + '" stroke-width="1.35"></path></svg>';
  }

  function metade(identificador) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><defs>'
      + '<linearGradient id="' + identificador + '">'
      + '<stop offset="50%" stop-color="currentColor"></stop>'
      + '<stop offset="50%" stop-color="transparent"></stop>'
      + "</linearGradient></defs>"
      + '<path d="' + CONTORNO + '" fill="url(#' + identificador + ')"></path></svg>';
  }

  function desenhar(raiz) {
    var alvo = raiz && raiz.querySelectorAll ? raiz : documento;

    alvo.querySelectorAll(".ls-estrelas[data-nota]").forEach(function (caixa) {
      var nota = Math.max(0, Math.min(5, paraNumero(caixa.dataset.nota)));

      /* Redesenhar a mesma nota seria trocar o DOM por DOM igual --
         e, numa lista reordenada a cada clique de filtro, isso é
         trabalho repetido em dezenas de cartões. */
      if (caixa.dataset.lsDesenhada === String(nota)) return;
      caixa.dataset.lsDesenhada = String(nota);

      var partes = [];
      for (var posicao = 1; posicao <= 5; posicao += 1) {
        if (nota >= posicao) partes.push(cheia());
        else if (nota >= posicao - 0.5) partes.push(metade("ls-meia-" + (++sequencia)));
        else partes.push(vazia());
      }
      caixa.innerHTML = partes.join("");

      /* A nota também precisa ser LIDA, e não só vista. Quem não põe o
         rótulo no HTML recebe um aqui -- sem isto, um leitor de tela
         anuncia cinco desenhos sem nome. */
      if (!caixa.getAttribute("aria-label")) {
        caixa.setAttribute("role", "img");
        caixa.setAttribute(
          "aria-label",
          nota
            ? "Avaliação " + String(nota).replace(".", ",") + " de 5"
            : "Ainda sem avaliação"
        );
      }
    });
  }

  janela.LSEstrelas = { desenhar: desenhar };

  documento.addEventListener("ls:estrelas", function (evento) {
    desenhar(evento.detail && evento.detail.raiz);
  });

  if (documento.readyState === "loading") {
    documento.addEventListener("DOMContentLoaded", function () { desenhar(); });
  } else {
    desenhar();
  }
})(window, document);
