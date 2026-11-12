/* LISTA OU CARDS: as duas apresentações de toda lista do painel.

   Cada tela marca o contêiner da lista (`data-visao="lista"`, o padrão,
   vindo do servidor) e põe o seletor (`includes/lista_ou_cards.html`):
   dois rádios, "Lista" e "Cards". Este módulo só troca o atributo do
   contêiner; quem desenha cada modo é o CSS comum de interno_modern.css
   ("LISTA OU CARDS"), a partir das mesmas marcações nos mesmos itens --
   um item, duas apresentações. Por isso o que outra frente pendura no
   item (`data-detalhe-*`, ouvintes de clique) vale nos dois modos.

   A ESCOLHA É LEMBRADA POR TELA, NO APARELHO: `ls-visao:<chave>` no
   localStorage, com try/catch (navegador com armazenamento bloqueado
   levanta exceção, e a lista não pode deixar de abrir por isso).

   A TELA QUE CHEGA SEM RECARREGAR TAMBÉM PRECISA DA ESCOLHA. O arquivo é
   carregado uma vez, no corpo do painel, e reaplica a escolha:
     * na carga normal;
     * a cada `Painel.montarTela(raiz)` -- é o que roda quando a navegação
       suave troca a tela inteira OU só um trecho (`data-ls-parte`) da
       lista de orçamentos e de O.S.;
     * no evento `ls:tela`, por garantia.
   O clique é ouvido no documento, uma vez só: o seletor de uma tela que
   chegou depois continua funcionando sem pendurar nada de novo. */
(function (window, document) {
  "use strict";

  var PREFIXO = "ls-visao:";
  var MODOS = ["lista", "cards"];

  function ler(chave) {
    try {
      return window.localStorage.getItem(PREFIXO + chave);
    } catch (erro) {
      return null;
    }
  }

  function gravar(chave, valor) {
    try {
      window.localStorage.setItem(PREFIXO + chave, valor);
    } catch (erro) { /* sem armazenamento: vale só até sair da tela */ }
  }

  function aplicar(seletor, modo) {
    if (MODOS.indexOf(modo) < 0) modo = seletor.getAttribute("data-visao-padrao") || "lista";
    var alvo = document.getElementById(seletor.getAttribute("data-visao-alvo") || "");
    if (alvo && alvo.getAttribute("data-visao") !== modo) alvo.setAttribute("data-visao", modo);
    var radios = seletor.querySelectorAll('input[type="radio"]');
    for (var i = 0; i < radios.length; i += 1) radios[i].checked = radios[i].value === modo;
  }

  function montar(raiz) {
    var escopo = raiz && raiz.querySelectorAll ? raiz : document;
    var seletores = escopo.querySelectorAll("[data-visao-seletor]");
    for (var i = 0; i < seletores.length; i += 1) {
      aplicar(seletores[i], ler(seletores[i].getAttribute("data-visao-chave") || ""));
    }
    // A lista pode ter chegado num trecho sem o seletor dentro (ou ser o
    // próprio trecho trocado).
    var alvos = Array.prototype.slice.call(escopo.querySelectorAll("[data-visao]"));
    if (escopo !== document && escopo.hasAttribute && escopo.hasAttribute("data-visao")) alvos.push(escopo);
    for (var j = 0; j < alvos.length; j += 1) {
      var seletor = document.querySelector('[data-visao-seletor][data-visao-alvo="' + alvos[j].id + '"]');
      if (seletor) aplicar(seletor, ler(seletor.getAttribute("data-visao-chave") || ""));
    }
  }

  document.addEventListener("change", function (evento) {
    var radio = evento.target;
    if (!radio || !radio.matches || !radio.matches('[data-visao-seletor] input[type="radio"]')) return;
    var seletor = radio.closest("[data-visao-seletor]");
    aplicar(seletor, radio.value);
    gravar(seletor.getAttribute("data-visao-chave") || "", radio.value);
  });

  document.addEventListener("ls:tela", function () { montar(document); });

  window.LSVisao = { montar: montar, ler: ler };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { montar(document); });
  } else {
    montar(document);
  }
})(window, document);
