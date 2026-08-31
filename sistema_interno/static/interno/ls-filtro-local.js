/* FILTRAR SEM IR AO SERVIDOR.

   A busca das listas era um formulário GET: cada palavra digitada só
   valia depois de apertar a lupa, e aí a tela inteira recarregava --
   com o desenho, os modais e a rolagem voltando do zero. Procurar um
   cliente custava uma viagem de rede e um piscar de tela.

   A TÉCNICA AQUI NÃO É GUARDAR O DOM. O servidor manda, junto da
   página, um índice enxuto de TODOS os registros do filtro atual: só o
   número e um texto já sem acento, pronto para comparar. Digitar passa
   a ser uma varredura em memória sobre esse índice -- instantânea, sem
   rede, sem mexer na URL e sem perder o que estava aberto na tela.

   O índice cobre o filtro inteiro, e a página desenhada é só um pedaço
   dele. Então o módulo sabe uma coisa que a filtragem de DOM sozinha
   não saberia: quando o que a pessoa procura EXISTE mas está fora
   desta página. Nesse caso ele não mente dizendo "nada encontrado" --
   diz quantos há e oferece o botão que vai buscá-los. Essa é a única
   situação em que a rede é acionada.

   Nada aqui reescreve a tabela: as linhas apenas somem e voltam, então
   os botões de cada linha continuam sendo os mesmos nós, com os mesmos
   ouvintes que a tela já pendurou neles. */
(function () {
  "use strict";

  function semAcento(texto) {
    return (texto || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function plural(quantidade, singular, pluralizado) {
    return quantidade === 1 ? singular : (pluralizado || singular + "s");
  }

  function montar(caixa) {
    if (caixa.dataset.lsFiltroPronto === "1") return;
    caixa.dataset.lsFiltroPronto = "1";

    var campo = caixa.querySelector("input[name='q']");
    var formulario = caixa.closest("form") || caixa.querySelector("form");
    var corpo = document.querySelector(caixa.dataset.filtroAlvo || "");
    if (!campo || !corpo) return;

    var nome = caixa.dataset.filtroNome || "registro";
    var nomes = caixa.dataset.filtroNomePlural || (nome + "s");
    /* "1 proposta encontrado" e "Nenhum proposta" -- o recado saía
       torto porque o módulo é o mesmo para propostas, ordens e clientes.
       Cada tela diz o gênero da palavra que usa. */
    var feminino = (caixa.dataset.filtroGenero || "m") === "f";
    var nenhum = feminino ? "Nenhuma" : "Nenhum";

    function encontrados(quantidade) {
      return "encontrad" + (feminino ? "a" : "o") + (quantidade === 1 ? "" : "s");
    }

    var indice = [];
    var fonte = document.getElementById(caixa.dataset.filtroIndice || "");
    if (fonte) {
      try { indice = JSON.parse(fonte.textContent) || []; } catch (erro) { indice = []; }
    }

    var linhas = Array.prototype.filter.call(
      corpo.querySelectorAll("tr[data-registro]"),
      function (tr) { return true; }
    );
    var linhaVazia = corpo.querySelector("tr[data-lista-vazia]");

    /* O aviso do que ficou de fora e o contador vivem fora da tabela:
       dentro dela virariam uma linha que o filtro teria de esconder. */
    var recado = document.createElement("div");
    recado.className = "ls-filtro-recado";
    recado.hidden = true;
    corpo.closest("table").insertAdjacentElement("afterend", recado);

    function desenharRecado(achados, visiveis, termo) {
      if (!termo) { recado.hidden = true; return; }

      if (achados === 0) {
        recado.hidden = false;
        recado.className = "ls-filtro-recado vazio";
        recado.innerHTML =
          '<i class="bi bi-search" aria-hidden="true"></i><span>' + nenhum + " " +
          nome + " com <strong>" + termo.replace(/[<&]/g, "") + "</strong>.</span>";
        return;
      }

      var fora = achados - visiveis;
      if (fora > 0) {
        /* O QUE A FILTRAGEM LOCAL SOZINHA NÃO SABERIA DIZER. A lista vem
           por página; o índice, não. Sem isto a tela responderia "nada
           encontrado" sobre um registro que existe. */
        recado.hidden = false;
        recado.className = "ls-filtro-recado fora";
        recado.innerHTML =
          '<span><strong>' + fora + "</strong> " + plural(fora, nome, nomes) +
          " fora desta página também " + plural(fora, "combina", "combinam") +
          " com a busca.</span>";
        var botao = document.createElement("button");
        botao.type = "button";
        botao.className = "btn btn-sm btn-outline-primary";
        botao.innerHTML = '<i class="bi bi-download" aria-hidden="true"></i> Trazer todos';
        botao.addEventListener("click", function () {
          if (formulario) formulario.submit();
        });
        recado.appendChild(botao);
        return;
      }

      recado.hidden = false;
      recado.className = "ls-filtro-recado";
      recado.innerHTML =
        "<span><strong>" + visiveis + "</strong> " +
        plural(visiveis, nome, nomes) + " " + encontrados(visiveis) + ".</span>";
    }

    function filtrar() {
      var termo = semAcento(campo.value);

      if (!termo) {
        linhas.forEach(function (tr) { tr.hidden = false; });
        if (linhaVazia) linhaVazia.hidden = linhas.length > 0;
        desenharRecado(0, 0, "");
        return;
      }

      var achados = 0;
      var combinam = Object.create(null);
      indice.forEach(function (registro) {
        if (registro.t && registro.t.indexOf(termo) !== -1) {
          combinam[registro.i] = true;
          achados += 1;
        }
      });

      var visiveis = 0;
      linhas.forEach(function (tr) {
        var cabe = !!combinam[tr.dataset.registro];
        tr.hidden = !cabe;
        if (cabe) visiveis += 1;
      });

      /* A linha de "lista vazia" é do servidor e fala do filtro, não da
         busca digitada; quem responde pela busca é o recado abaixo. */
      if (linhaVazia) linhaVazia.hidden = true;
      desenharRecado(achados, visiveis, campo.value.trim());
    }

    campo.addEventListener("input", filtrar);
    campo.addEventListener("search", filtrar);

    if (formulario) {
      /* Sem isto, apertar Enter recarregaria a tela -- exatamente a
         viagem que este módulo existe para evitar. Quando faz falta ir
         ao servidor, quem pede é o botão do recado. */
      formulario.addEventListener("submit", function (evento) {
        if (!campo.value.trim()) return;
        evento.preventDefault();
        filtrar();
      });
    }

    if (campo.value.trim()) filtrar();
  }

  window.LSFiltroLocal = {
    ligar: function (raiz) {
      (raiz || document).querySelectorAll("[data-filtro-alvo]").forEach(montar);
    },
  };

  if (window.LSTela && window.LSTela.pronto) {
    window.LSTela.pronto(function () { window.LSFiltroLocal.ligar(); });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      window.LSFiltroLocal.ligar();
    });
  }
})();
