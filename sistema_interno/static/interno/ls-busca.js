/* ======================================================================
   BUSCA — o campo de escolher coisa do painel interno.

   POR QUE EXISTE. Este painel é usado em tablet, no chão de fábrica, por
   quem não trabalha com computador o dia todo. O <select> do navegador
   resolve dez opções; com trezentos brinquedos ele vira uma lista sem
   fim, sem foto do que está escolhendo, e no tablet abre uma roleta que
   não aceita digitar. Quem monta orçamento na frente do cliente não pode
   depender disso.

   O QUE ESTE COMPONENTE FAZ DIFERENTE:
     * digita e filtra, sem acento e sem se importar com maiúscula --
       "cama elastica" acha "Cama Elástica";
     * mostra o preço (ou o código) embaixo do nome, então dá para
       conferir sem abrir outra tela;
     * separa por grupo (catálogo do site, produção...);
     * tem uma linha final "cadastrar na hora", porque o que falta no
       cadastro aparece justamente quando o cliente está esperando;
     * anda pelo teclado (setas, Enter, Esc) para quem usa no computador;
     * cada linha tem 48px de altura -- é o tamanho do dedo.

   COMO USAR:

     var campo = LSBusca.criar({
       nome: "cliente",
       valor: "12",
       placeholder: "Buscar cliente...",
       opcoes: [{valor:"12", rotulo:"Buffet Alegria", detalhe:"Buffet",
                 grupo:"Parceiros"}],
       aoEscolher: function (opcao) {},
       criar: {rotulo:"Cadastrar cliente", aoClicar: function (digitado) {}}
     });
     algumLugar.appendChild(campo.elemento);

   O componente não conhece o resto do painel: quem chama decide o que
   fazer ao escolher.
   ====================================================================== */
(function (janela) {
  "use strict";

  var LIMITE_VISIVEL = 60;   /* rolar mais que isso ninguém rola */
  var sequencia = 0;

  function semAcento(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function criar(config) {
    config = config || {};

    var opcoes = (config.opcoes || []).slice();
    var id = "ls-busca-" + (++sequencia);
    var escolhida = null;

    /* ---------------------------------------------------------- HTML */
    var raiz = document.createElement("div");
    raiz.className = "ls-busca" + (config.classe ? " " + config.classe : "");

    var guardado = document.createElement("input");
    guardado.type = "hidden";
    if (config.nome) guardado.name = config.nome;
    guardado.value = config.valor == null ? "" : String(config.valor);

    var campo = document.createElement("div");
    campo.className = "ls-busca-campo";

    var lupa = document.createElement("i");
    lupa.className = "bi bi-search ls-busca-lupa";
    lupa.setAttribute("aria-hidden", "true");

    var entrada = document.createElement("input");
    entrada.type = "text";
    entrada.className = "ls-busca-entrada";
    entrada.autocomplete = "off";
    entrada.placeholder = config.placeholder || "Buscar...";
    entrada.setAttribute("role", "combobox");
    entrada.setAttribute("aria-expanded", "false");
    entrada.setAttribute("aria-controls", id);
    entrada.setAttribute("aria-autocomplete", "list");
    if (config.rotuloAcessivel) {
      entrada.setAttribute("aria-label", config.rotuloAcessivel);
    }

    var limpar = document.createElement("button");
    limpar.type = "button";
    limpar.className = "ls-busca-limpar";
    limpar.innerHTML = '<i class="bi bi-x-lg"></i>';
    limpar.setAttribute("aria-label", "Limpar escolha");
    limpar.hidden = true;

    campo.appendChild(lupa);
    campo.appendChild(entrada);
    campo.appendChild(limpar);

    var painel = document.createElement("div");
    painel.className = "ls-busca-painel";
    painel.id = id;
    painel.setAttribute("role", "listbox");
    painel.hidden = true;

    var lista = document.createElement("div");
    lista.className = "ls-busca-lista";
    painel.appendChild(lista);

    var rodape = null;
    if (config.criar) {
      rodape = document.createElement("button");
      rodape.type = "button";
      rodape.className = "ls-busca-criar";
      rodape.innerHTML =
        '<i class="bi bi-plus-circle"></i><span></span>';
      painel.appendChild(rodape);
    }

    raiz.appendChild(guardado);
    raiz.appendChild(campo);
    raiz.appendChild(painel);

    /* ------------------------------------------------------- desenho */
    function acharOpcao(valor) {
      var alvo = String(valor == null ? "" : valor);
      for (var i = 0; i < opcoes.length; i++) {
        if (String(opcoes[i].valor) === alvo) return opcoes[i];
      }
      return null;
    }

    function linha(opcao, indice) {
      var item = document.createElement("button");
      item.type = "button";
      item.className = "ls-busca-item";
      item.setAttribute("role", "option");
      item.dataset.valor = String(opcao.valor);
      item.dataset.indice = String(indice);

      var corpo = '<span class="ls-busca-item-nome">' + escapar(opcao.rotulo) + "</span>";
      if (opcao.detalhe) {
        corpo += '<span class="ls-busca-item-detalhe">' + escapar(opcao.detalhe) + "</span>";
      }
      item.innerHTML = '<span class="ls-busca-item-corpo">' + corpo + "</span>";

      if (opcao.valorDireita) {
        item.innerHTML +=
          '<span class="ls-busca-item-direita">' + escapar(opcao.valorDireita) + "</span>";
      }

      if (String(opcao.valor) === guardado.value) {
        item.classList.add("escolhido");
        item.setAttribute("aria-selected", "true");
      }

      return item;
    }

    function escapar(texto) {
      var caixa = document.createElement("span");
      caixa.textContent = texto == null ? "" : String(texto);
      return caixa.innerHTML;
    }

    function desenhar(filtro) {
      lista.innerHTML = "";

      var termo = semAcento(filtro);
      var achados = [];

      for (var i = 0; i < opcoes.length; i++) {
        var opcao = opcoes[i];
        if (!termo || (opcao._busca || semAcento(
          opcao.rotulo + " " + (opcao.detalhe || "")
        )).indexOf(termo) >= 0) {
          achados.push(opcao);
        }
        if (achados.length > LIMITE_VISIVEL) break;
      }

      if (!achados.length) {
        var vazio = document.createElement("p");
        vazio.className = "ls-busca-vazio";
        vazio.textContent = filtro
          ? 'Nada encontrado para "' + filtro + '".'
          : "Nenhuma opção disponível.";
        lista.appendChild(vazio);
      } else {
        var grupoAtual = null;
        achados.forEach(function (opcao, indice) {
          if (opcao.grupo && opcao.grupo !== grupoAtual) {
            grupoAtual = opcao.grupo;
            var titulo = document.createElement("span");
            titulo.className = "ls-busca-grupo";
            titulo.textContent = grupoAtual;
            lista.appendChild(titulo);
          }
          lista.appendChild(linha(opcao, indice));
        });
      }

      if (rodape) {
        var rotulo = config.criar.rotulo || "Cadastrar";
        rodape.querySelector("span").textContent = filtro
          ? rotulo + ': "' + filtro + '"'
          : rotulo;
      }
    }

    /* --------------------------------------------------- abrir/fechar */
    function abrir() {
      if (!painel.hidden) return;
      painel.hidden = false;
      raiz.classList.add("aberta");
      entrada.setAttribute("aria-expanded", "true");
      desenhar(entrada.value === rotuloEscolhido() ? "" : entrada.value);

      /* No tablet o teclado sobe e come metade da tela: garantir que a
         lista fique visível evita o usuário digitar às cegas. */
      janela.setTimeout(function () {
        raiz.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }, 60);
    }

    function fechar(restaurar) {
      if (painel.hidden) return;
      painel.hidden = true;
      raiz.classList.remove("aberta");
      entrada.setAttribute("aria-expanded", "false");
      marcado = -1;

      /* Texto pela metade no campo faz o usuário achar que escolheu algo
         que não escolheu. Fechar devolve o rótulo do que está valendo. */
      if (restaurar !== false) entrada.value = rotuloEscolhido();
    }

    function rotuloEscolhido() {
      return escolhida ? escolhida.rotulo : "";
    }

    /* --------------------------------------------------- seleção */
    function escolher(valor, avisar) {
      var opcao = acharOpcao(valor);
      escolhida = opcao;
      guardado.value = opcao ? String(opcao.valor) : "";
      entrada.value = opcao ? opcao.rotulo : "";
      limpar.hidden = !opcao;
      raiz.classList.toggle("preenchida", !!opcao);

      if (avisar !== false && typeof config.aoEscolher === "function") {
        config.aoEscolher(opcao);
      }
    }

    var marcado = -1;

    function marcar(passo) {
      var itens = lista.querySelectorAll(".ls-busca-item");
      if (!itens.length) return;

      marcado += passo;
      if (marcado < 0) marcado = itens.length - 1;
      if (marcado >= itens.length) marcado = 0;

      itens.forEach(function (item, indice) {
        item.classList.toggle("marcado", indice === marcado);
      });
      itens[marcado].scrollIntoView({ block: "nearest" });
    }

    /* --------------------------------------------------- eventos */
    entrada.addEventListener("focus", abrir);
    entrada.addEventListener("click", abrir);

    entrada.addEventListener("input", function () {
      if (painel.hidden) abrir();
      marcado = -1;
      desenhar(entrada.value);
    });

    entrada.addEventListener("keydown", function (evento) {
      if (evento.key === "ArrowDown") {
        evento.preventDefault();
        if (painel.hidden) abrir();
        marcar(1);
        return;
      }
      if (evento.key === "ArrowUp") {
        evento.preventDefault();
        marcar(-1);
        return;
      }
      if (evento.key === "Enter") {
        var itens = lista.querySelectorAll(".ls-busca-item");
        if (!painel.hidden && itens.length) {
          evento.preventDefault();
          var alvo = itens[marcado >= 0 ? marcado : 0];
          escolher(alvo.dataset.valor);
          fechar();
        }
        return;
      }
      if (evento.key === "Escape") {
        if (!painel.hidden) {
          evento.stopPropagation();  /* não fecha o modal junto */
          fechar();
        }
      }
    });

    lista.addEventListener("click", function (evento) {
      var item = evento.target.closest(".ls-busca-item");
      if (!item) return;
      escolher(item.dataset.valor);
      fechar();
    });

    limpar.addEventListener("click", function () {
      escolher("");
      entrada.focus();
      desenhar("");
    });

    if (rodape) {
      rodape.addEventListener("click", function () {
        var digitado = entrada.value === rotuloEscolhido() ? "" : entrada.value;
        fechar();
        if (typeof config.criar.aoClicar === "function") {
          config.criar.aoClicar(digitado.trim());
        }
      });
    }

    document.addEventListener("click", function (evento) {
      if (raiz.contains(evento.target)) return;
      fechar();
    });

    /* --------------------------------------------------- índice */
    function indexar(lista_) {
      lista_.forEach(function (opcao) {
        opcao._busca = semAcento(opcao.rotulo + " " + (opcao.detalhe || ""));
      });
      return lista_;
    }

    indexar(opcoes);
    escolher(guardado.value, false);

    /* --------------------------------------------------- API */
    return {
      elemento: raiz,
      entrada: entrada,
      valor: function () { return guardado.value; },
      opcaoAtual: function () { return escolhida; },
      definirValor: function (valor, avisar) { escolher(valor, avisar); },
      definirOpcoes: function (novas) {
        opcoes = indexar((novas || []).slice());
        escolher(guardado.value, false);
        if (!painel.hidden) desenhar(entrada.value);
      },
      adicionarOpcao: function (opcao, escolherAgora) {
        indexar([opcao]);
        opcoes.push(opcao);
        if (escolherAgora) escolher(opcao.valor);
      },
      focar: function () { entrada.focus(); }
    };
  }

  janela.LSBusca = { criar: criar, semAcento: semAcento };
})(window);
