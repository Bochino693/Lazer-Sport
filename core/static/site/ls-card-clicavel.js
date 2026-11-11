/* ======================================================================
   O CARD INTEIRO ABRE O ITEM.

   Nos combos, nas promoções e nos cards da loja, tocar em qualquer lugar
   do card abre a página do item, como num produto comum: a foto, o nome,
   o preço, o espaço vazio. Os controles de dentro continuam sendo deles:
   o "Adicionar" põe no carrinho, a estrela favorita, os links vão aonde
   apontam. Quem marca o card com `data-card-link="<endereço>"` ganha isto.

   Ctrl/Cmd/Shift + clique e o botão do meio abrem em outra aba, como num
   link de verdade. Selecionar um pedaço do texto não abre nada, e o
   arraste do carrossel da home (o mouse que rolou a fila) também não: ele
   cancela o clique antes de chegar aqui.
   ====================================================================== */
(function () {
  "use strict";

  // o que é controle do próprio card: ali o clique é dele, não do card
  var CONTROLES = "a, button, input, select, textarea, label, summary, [role='button'], [data-card-ignorar]";

  function cardDoClique(evento) {
    var alvo = evento.target;
    if (!alvo || !alvo.closest) return null;
    var card = alvo.closest("[data-card-link]");
    if (!card) return null;
    var controle = alvo.closest(CONTROLES);
    if (controle && card.contains(controle)) return null;
    if (controle && controle.contains(card)) return null; // o card já está dentro de um link
    var selecao = window.getSelection ? window.getSelection() : null;
    if (selecao && String(selecao).trim() && card.contains(selecao.anchorNode)) return null;
    return card;
  }

  function abrirEmOutraAba(endereco) {
    var aba = window.open(endereco, "_blank", "noopener");
    if (aba) aba.opener = null;
  }

  document.addEventListener("click", function (evento) {
    if (evento.defaultPrevented || evento.button !== 0) return;
    var card = cardDoClique(evento);
    if (!card) return;
    var endereco = card.getAttribute("data-card-link");
    if (!endereco) return;
    if (evento.ctrlKey || evento.metaKey || evento.shiftKey) {
      abrirEmOutraAba(endereco);
      return;
    }
    window.location.assign(endereco);
  });

  document.addEventListener("auxclick", function (evento) {
    if (evento.button !== 1) return;
    var card = cardDoClique(evento);
    if (!card) return;
    evento.preventDefault();
    abrirEmOutraAba(card.getAttribute("data-card-link"));
  });
})();
