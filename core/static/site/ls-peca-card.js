/* ======================================================================
   O BOTÃO "ADICIONAR AO CARRINHO" DO CARTÃO DA PEÇA, fora da home.

   Na home ele já vem do home.js. Nas outras telas que mostram o cartão
   (partials/peca_card.html), este arquivo faz o mesmo: chama o carrinho
   do site (`adicionarAoCarrinho`, do base.html) e mostra no botão que
   está adicionando e que adicionou.
   ====================================================================== */
(function () {
  "use strict";
  if (typeof window.adicionarPecaAoCarrinho === "function") return;

  window.adicionarPecaAoCarrinho = function (evento, pecaId, botao) {
    evento.preventDefault();
    evento.stopPropagation();
    if (!botao || botao.dataset.loading === "true") return;
    if (typeof window.adicionarAoCarrinho !== "function") {
      if (typeof window.mostrarToast === "function") window.mostrarToast("Não foi possível abrir o carrinho agora.", true);
      return;
    }
    const original = botao.innerHTML;
    botao.dataset.loading = "true";
    botao.disabled = true;
    botao.classList.add("is-loading");
    botao.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i><span>Adicionando...</span>';
    // Desistiu na folha de quantidade, ou deu erro: o botão volta na hora.
    let adicionou = false;
    Promise.resolve(window.adicionarAoCarrinho("peca", pecaId))
      .then((resultado) => {
        if (!resultado || !resultado.sucesso) return;
        adicionou = true;
        botao.classList.remove("is-loading");
        botao.classList.add("is-added");
        botao.innerHTML = '<i class="fa-solid fa-check" aria-hidden="true"></i><span>Adicionado</span>';
      })
      .finally(() => {
        window.setTimeout(() => {
          botao.disabled = false;
          botao.dataset.loading = "false";
          botao.classList.remove("is-loading", "is-added");
          botao.innerHTML = original;
        }, adicionou ? 1200 : 0);
      });
  };
})();
