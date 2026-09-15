/* ======================================================================
   GALERIA — a janela de fotos de eventos e projetos.

   O DEFEITO QUE ISTO RESOLVE. A tela de Eventos tinha cartões com
   `data-modal`, janelas com `.evento-modal` e um X com `.modal-close` --
   e NENHUM script que ligasse os três. O código que fazia isso morava em
   `home.js`, carregado só na página inicial. Resultado: em /eventos/ os
   cartões não abriam nada. Clicar não dava erro, não dava aviso, não
   dava nada -- o pior tipo de defeito, porque parece decisão de projeto.
   A tela de Projetos tinha o seu próprio script, parecido mas não igual,
   escrito à mão dentro do HTML.

   Agora as duas usam este módulo, e ele faz o que aquelas versões não
   faziam:

     * abre pelo TECLADO, e não só pelo mouse (Enter e Espaço);
     * fecha no Esc, no X e no clique fora, nos três casos;
     * trava a rolagem do fundo enquanto está aberta -- sem isso, rolar
       a janela no celular rolava a página atrás dela;
     * devolve o foco ao cartão de origem ao fechar, senão quem navega
       por teclado volta para o começo da página;
     * mantém o foco dentro da janela enquanto ela está aberta.

   COMO USAR:

     <article class="..." data-ls-galeria="galeria-evento-3" tabindex="0"
              role="button" aria-haspopup="dialog"> … </article>

     <div class="ls-galeria" id="galeria-evento-3" role="dialog"
          aria-modal="true" aria-labelledby="titulo-3" hidden>
       <div class="ls-galeria-caixa">
         <button type="button" class="ls-galeria-fechar"
                 data-ls-galeria-fechar aria-label="Fechar">×</button>
         …
       </div>
     </div>
   ====================================================================== */
(function (janela, documento) {
  "use strict";

  var aberta = null;
  var origem = null;

  var FOCAVEIS =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),'
    + ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function abrir(id, gatilho) {
    var caixa = documento.getElementById(id);
    if (!caixa || aberta === caixa) return;

    if (aberta) fechar();

    aberta = caixa;
    origem = gatilho || documento.activeElement;

    caixa.hidden = false;
    /* A classe entra num quadro seguinte para a transição de opacidade
       ter de onde sair; posta junto com `hidden = false`, o navegador
       calcula os dois estados de uma vez e a janela aparece seca. */
    janela.requestAnimationFrame(function () { caixa.classList.add("aberta"); });

    documento.body.classList.add("ls-galeria-travada");

    var primeiro = caixa.querySelector(FOCAVEIS);
    if (primeiro) primeiro.focus();
  }

  function fechar() {
    if (!aberta) return;

    var caixa = aberta;
    aberta = null;

    caixa.classList.remove("aberta");
    caixa.hidden = true;
    documento.body.classList.remove("ls-galeria-travada");

    if (origem && origem.isConnected) origem.focus();
    origem = null;
  }

  /* Delegação no documento: os cartões podem ser reordenados ou trocados
     por filtro sem que nenhum ouvinte precise ser religado. */
  documento.addEventListener("click", function (evento) {
    var fechamento = evento.target.closest("[data-ls-galeria-fechar]");
    if (fechamento) {
      evento.preventDefault();
      fechar();
      return;
    }

    /* Clique no fundo escuro -- e só nele. `closest` acharia a janela a
       partir de qualquer coisa dentro dela, inclusive de uma foto. */
    if (aberta && evento.target === aberta) {
      fechar();
      return;
    }

    var gatilho = evento.target.closest("[data-ls-galeria]");
    if (!gatilho) return;
    /* Um link dentro do cartão continua sendo um link. */
    if (evento.target.closest("a[href]") && !gatilho.matches("a[href]")) return;

    evento.preventDefault();
    abrir(gatilho.dataset.lsGaleria, gatilho);
  });

  documento.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && aberta) {
      evento.preventDefault();
      fechar();
      return;
    }

    if (evento.key === "Tab" && aberta) {
      var focaveis = Array.prototype.filter.call(
        aberta.querySelectorAll(FOCAVEIS),
        function (elemento) { return elemento.offsetParent !== null; }
      );
      if (!focaveis.length) return;

      var primeiro = focaveis[0];
      var ultimo = focaveis[focaveis.length - 1];

      if (evento.shiftKey && documento.activeElement === primeiro) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && documento.activeElement === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      }
      return;
    }

    /* Abrir pelo teclado. O cartão é `role="button"`, e o que um botão
       promete é responder a Enter e a Espaço. */
    if (evento.key !== "Enter" && evento.key !== " ") return;
    var gatilho = evento.target.closest
      ? evento.target.closest("[data-ls-galeria]")
      : null;
    if (!gatilho || gatilho.matches("a[href]")) return;

    evento.preventDefault();
    abrir(gatilho.dataset.lsGaleria, gatilho);
  });

  janela.LSGaleria = { abrir: abrir, fechar: fechar };
})(window, document);
