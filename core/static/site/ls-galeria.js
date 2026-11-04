/* ======================================================================
   GALERIA — a janela de fotos de eventos, projetos e produtos.

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

   A JANELA DE UMA FOTO POR VEZ (a página do produto e a da peça). Se a
   janela tem `.ls-galeria-slide`, o módulo vira um visor: mostra um
   slide de cada vez, passa com as setas (`data-ls-galeria-anterior` e
   `data-ls-galeria-proxima`), com as teclas ← e →, com o dedo no
   celular, e conta "2 / 5" em `data-ls-galeria-contador`. Miniaturas
   dentro da janela levam `data-ls-galeria-ir="<índice>"`. O gatilho pode
   dizer em que foto abrir com `data-ls-galeria-indice`. A cada troca a
   janela dispara o evento `ls-galeria:mudou` com `{indice, total}`, e a
   página usa isso para deixar o carrossel de fora na mesma foto.
   Elementos com `data-ls-galeria-fundo` fecham a janela quando o clique
   cai neles diretamente (o palco em volta da foto).
   ====================================================================== */
(function (janela, documento) {
  "use strict";

  var aberta = null;
  var origem = null;
  /* o começo de um arraste no palco; `null` quando não há arraste */
  var arraste = null;
  /* um arraste que passou de foto não pode virar um clique no fundo
     (que fecharia a janela): o clique que vem logo depois é engolido */
  var engolirClique = false;

  var FOCAVEIS =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),'
    + ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function slidesDe(caixa) {
    return caixa ? caixa.querySelectorAll(".ls-galeria-slide") : [];
  }

  function indiceAtual(caixa) {
    return Number.parseInt(caixa.dataset.lsGaleriaAtual || "0", 10) || 0;
  }

  /* Mostra o slide `indice` (dá a volta nas pontas), atualiza o contador,
     a legenda e as miniaturas, e já manda baixar as fotos vizinhas para a
     próxima troca não mostrar um vazio. */
  function mostrarSlide(caixa, indice) {
    var slides = slidesDe(caixa);
    var total = slides.length;
    if (!total) return;

    indice = ((indice % total) + total) % total;
    caixa.dataset.lsGaleriaAtual = String(indice);

    Array.prototype.forEach.call(slides, function (slide, posicao) {
      var ativo = posicao === indice;
      slide.hidden = !ativo;
      slide.classList.toggle("ativo", ativo);
      var vizinho = posicao === (indice + 1) % total || posicao === (indice + total - 1) % total;
      if (ativo || vizinho) {
        var foto = slide.querySelector("img");
        if (foto && foto.loading === "lazy") foto.loading = "eager";
      }
    });

    var contador = caixa.querySelector("[data-ls-galeria-contador]");
    if (contador) contador.textContent = (indice + 1) + " / " + total;

    var legenda = caixa.querySelector("[data-ls-galeria-legenda]");
    if (legenda) {
      var ativa = slides[indice].querySelector("img");
      var texto = slides[indice].dataset.legenda || (ativa && ativa.alt) || "";
      legenda.textContent = texto;
      legenda.hidden = !texto;
    }

    Array.prototype.forEach.call(caixa.querySelectorAll("[data-ls-galeria-ir]"), function (botao) {
      var ativa = Number.parseInt(botao.dataset.lsGaleriaIr, 10) === indice;
      botao.classList.toggle("ativa", ativa);
      botao.setAttribute("aria-current", ativa ? "true" : "false");
      if (ativa && botao.scrollIntoView) {
        botao.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    });

    caixa.dispatchEvent(new CustomEvent("ls-galeria:mudou", {
      bubbles: true,
      detail: { indice: indice, total: total }
    }));
  }

  function passar(passo) {
    if (!aberta || !slidesDe(aberta).length) return;
    mostrarSlide(aberta, indiceAtual(aberta) + passo);
  }

  function abrir(id, gatilho, indice) {
    var caixa = documento.getElementById(id);
    if (!caixa || aberta === caixa) return;

    if (aberta) fechar();

    aberta = caixa;
    origem = gatilho || documento.activeElement;

    if (slidesDe(caixa).length) {
      if (indice === undefined && gatilho && gatilho.dataset && gatilho.dataset.lsGaleriaIndice !== undefined) {
        indice = Number.parseInt(gatilho.dataset.lsGaleriaIndice, 10);
      }
      mostrarSlide(caixa, Number.isFinite(indice) ? indice : indiceAtual(caixa));
    }

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
    arraste = null;

    caixa.classList.remove("aberta");
    caixa.hidden = true;
    documento.body.classList.remove("ls-galeria-travada");

    if (origem && origem.isConnected) origem.focus();
    origem = null;
  }

  /* Delegação no documento: os cartões podem ser reordenados ou trocados
     por filtro sem que nenhum ouvinte precise ser religado. */
  documento.addEventListener("click", function (evento) {
    if (engolirClique) {
      engolirClique = false;
      evento.preventDefault();
      return;
    }

    var fechamento = evento.target.closest("[data-ls-galeria-fechar]");
    if (fechamento) {
      evento.preventDefault();
      fechar();
      return;
    }

    if (aberta) {
      if (evento.target.closest("[data-ls-galeria-proxima]")) {
        evento.preventDefault();
        passar(1);
        return;
      }
      if (evento.target.closest("[data-ls-galeria-anterior]")) {
        evento.preventDefault();
        passar(-1);
        return;
      }
      var ir = evento.target.closest("[data-ls-galeria-ir]");
      if (ir) {
        evento.preventDefault();
        mostrarSlide(aberta, Number.parseInt(ir.dataset.lsGaleriaIr, 10) || 0);
        return;
      }
    }

    /* Clique no fundo escuro -- e só nele. `closest` acharia a janela a
       partir de qualquer coisa dentro dela, inclusive de uma foto. */
    if (aberta && (evento.target === aberta || evento.target.hasAttribute("data-ls-galeria-fundo"))) {
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

    if (aberta && slidesDe(aberta).length) {
      if (evento.key === "ArrowRight") { evento.preventDefault(); passar(1); return; }
      if (evento.key === "ArrowLeft") { evento.preventDefault(); passar(-1); return; }
      if (evento.key === "Home") { evento.preventDefault(); mostrarSlide(aberta, 0); return; }
      if (evento.key === "End") { evento.preventDefault(); mostrarSlide(aberta, -1); return; }
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

  /* O dedo no palco: arrastar de lado passa a foto (ou volta). Mouse não
     arrasta -- com ele há as setas, e o arraste atrapalharia o clique. */
  documento.addEventListener("pointerdown", function (evento) {
    if (!aberta || evento.pointerType === "mouse") return;
    if (!evento.target.closest(".ls-galeria-palco")) return;
    if (evento.target.closest("button, a[href]")) return;
    arraste = { x: evento.clientX, y: evento.clientY };
  }, { passive: true });

  documento.addEventListener("pointerup", function (evento) {
    if (!arraste || !aberta) { arraste = null; return; }
    var dx = evento.clientX - arraste.x;
    var dy = evento.clientY - arraste.y;
    arraste = null;
    if (Math.abs(dx) > 36 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      passar(dx < 0 ? 1 : -1);
      /* o `click` que o navegador dispara logo depois do dedo sair cairia
         no fundo e fecharia a janela; só este próximo clique é engolido */
      engolirClique = true;
      janela.setTimeout(function () { engolirClique = false; }, 0);
    }
  }, { passive: true });

  documento.addEventListener("pointercancel", function () { arraste = null; }, { passive: true });

  janela.LSGaleria = {
    abrir: abrir,
    fechar: fechar,
    proxima: function () { passar(1); },
    anterior: function () { passar(-1); },
    ir: function (indice) { if (aberta) mostrarSlide(aberta, indice); }
  };
})(window, document);
