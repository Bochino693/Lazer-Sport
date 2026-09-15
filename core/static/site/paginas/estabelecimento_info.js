/* Ordenação dos brinquedos de um parceiro, sem recarregar a tela.
 *
 * OS CHIPS SÃO LINKS, E CONTINUAM SENDO. Sem JavaScript -- ou antes de
 * ele chegar -- cada um leva a `?order=...` e o servidor devolve a lista
 * ordenada. O que este arquivo faz é ANTECIPAR esse resultado: reordena
 * os cartões que já estão na tela e reescreve o endereço, para o link
 * continuar podendo ser copiado e mandado para alguém.
 *
 * A ORDEM É A MESMA DOS DOIS LADOS, e isso não é detalhe. Antes o botão
 * "Menor preço" ordenava por avaliação dividida por preço -- uma fórmula
 * que não é "menor preço" nenhum -- enquanto o servidor, no mesmo
 * parâmetro, ordenava por valor crescente. O mesmo botão dava duas
 * listas diferentes conforme o JavaScript tivesse carregado ou não.
 */
(function (janela, documento) {
  "use strict";

  var lista = documento.getElementById("estb-lista");
  var barra = documento.getElementById("filter");
  if (!lista || !barra) return;

  function texto(cartao) {
    return (cartao.dataset.nome || "").toLocaleLowerCase("pt-BR");
  }

  function numero(valor, quandoVazio) {
    var convertido = parseFloat(valor);
    return isNaN(convertido) ? quandoVazio : convertido;
  }

  var ORDENS = {
    az: function (a, b) { return texto(a).localeCompare(texto(b), "pt-BR"); },
    za: function (a, b) { return texto(b).localeCompare(texto(a), "pt-BR"); },
    avaliacao: function (a, b) {
      return numero(b.dataset.avaliacao, 0) - numero(a.dataset.avaliacao, 0);
    },
    /* Sem preço cadastrado vai para o fim, e não para o começo: "menor
       preço" mostrando primeiro o que não tem preço seria uma lista que
       não responde ao que foi pedido. */
    custo: function (a, b) {
      return numero(a.dataset.custo, Infinity) - numero(b.dataset.custo, Infinity);
    }
  };

  function ordenar(chave) {
    var comparar = ORDENS[chave];
    if (!comparar) return;

    var cartoes = Array.prototype.slice.call(lista.children);
    cartoes.sort(comparar);

    /* Um fragmento só: mover 60 cartões um a um dentro do documento
       obriga o navegador a recalcular o desenho a cada passo. */
    var fragmento = documento.createDocumentFragment();
    cartoes.forEach(function (cartao) { fragmento.appendChild(cartao); });
    lista.appendChild(fragmento);

    barra.querySelectorAll("[data-ordem]").forEach(function (chip) {
      chip.setAttribute("aria-pressed", String(chip.dataset.ordem === chave));
    });
  }

  barra.addEventListener("click", function (evento) {
    var chip = evento.target.closest("[data-ordem]");
    if (!chip || !ORDENS[chip.dataset.ordem]) return;

    evento.preventDefault();
    ordenar(chip.dataset.ordem);

    /* `replaceState`: reordenar não é sair da página, e não merece uma
       parada a mais no botão Voltar. O endereço fica certo do mesmo
       jeito para quem copiar a barra. */
    try {
      var endereco = new URL(janela.location.href);
      endereco.searchParams.set("order", chip.dataset.ordem);
      endereco.hash = "filter";
      janela.history.replaceState(janela.history.state, "", endereco);
    } catch (erro) {}
  });
})(window, document);
