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

   Em catálogos grandes, `carregar(termo)` pode devolver uma Promise com
   poucas opções do servidor. Nesse modo o componente espera 220 ms entre
   teclas, ignora resposta antiga e nunca precisa receber a tabela inteira.

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

    var rodape = null;
    if (config.criar) {
      rodape = document.createElement("button");
      rodape.type = "button";
      rodape.className = "ls-busca-criar";
      rodape.innerHTML =
        '<i class="bi bi-plus-circle"></i><span></span>';
      painel.appendChild(rodape);
    }
    /* Cadastrar é uma saída imediata quando a busca não encontra o que a
       pessoa quer. No rodapé ele ficava escondido depois de dezenas de
       clientes ou brinquedos; no topo aparece antes dos resultados. */
    painel.appendChild(lista);

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
      var visual = "";
      if (config.exibirImagem) {
        visual = opcao.imagem
          ? '<span class="ls-busca-item-foto"><img src="' + escaparAtributo(opcao.imagem) + '" alt="" loading="lazy"></span>'
          : '<span class="ls-busca-item-foto sem-foto"><i class="bi bi-box-seam"></i></span>';
      }
      item.innerHTML = visual + '<span class="ls-busca-item-corpo">' + corpo + "</span>";

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

    function escaparAtributo(texto) {
      return escapar(texto).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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

    var timerBusca = null;
    var geracaoBusca = 0;

    function mensagemBusca(texto) {
      lista.innerHTML = "";
      var aviso = document.createElement("p");
      aviso.className = "ls-busca-vazio";
      aviso.textContent = texto;
      lista.appendChild(aviso);
    }

    function carregarRemoto(filtro, imediato) {
      if (typeof config.carregar !== "function") {
        desenhar(filtro);
        return;
      }

      var termo = String(filtro || "").trim();
      var minimo = Number(config.minimoBusca || 0);
      if (termo && termo.length < minimo) {
        mensagemBusca("Digite mais " + (minimo - termo.length) + " caractere(s).");
        return;
      }

      if (timerBusca) janela.clearTimeout(timerBusca);
      var geracao = ++geracaoBusca;

      function executar() {
        mensagemBusca("Buscando itens…");
        Promise.resolve(config.carregar(termo))
          .then(function (novas) {
            if (geracao !== geracaoBusca) return;

            var anterior = escolhida;
            opcoes = indexar((novas || []).slice());
            if (anterior && !acharOpcao(anterior.valor)) {
              indexar([anterior]);
              opcoes.unshift(anterior);
            }
            escolher(guardado.value, false);
            if (!painel.hidden) {
              desenhar(termo);
              posicionar();
            }
          })
          .catch(function () {
            if (geracao !== geracaoBusca) return;
            mensagemBusca("Não consegui buscar agora. Tente novamente.");
          });
      }

      if (imediato) executar();
      else timerBusca = janela.setTimeout(executar, 220);
    }

    /* --------------------------------------------------- abrir/fechar

       O PAINEL SAI DE DENTRO DO FORMULÁRIO PARA ABRIR.

       Enquanto ele era filho do campo, quem o cortava era o contêiner de
       cima: o corpo do modal rola (`overflow:auto`) e a tabela de itens
       do orçamento rola de lado. O resultado era a lista aparecendo pela
       metade, escondida atrás da borda -- exatamente onde ela mais é
       usada.

       Aberto, o painel vai para o <body> em `position:fixed`, colado ao
       campo por coordenada. Fechado, volta para dentro do componente,
       para não sobrar nó solto quando a linha do orçamento é removida.
    */
    function posicionar() {
      var caixa = campo.getBoundingClientRect();
      var folga = 6;
      var espacoAbaixo = janela.innerHeight - caixa.bottom - folga;
      var espacoAcima = caixa.top - folga;
      var altura = Math.min(420, janela.innerHeight * 0.58);

      /* O painel acompanha o campo, mas nunca fica mais estreito que o
         necessário para ler o nome do produto: dentro da tabela do
         orçamento a coluna tem 30% da largura, e "Cama elástica 3m"
         quebrava em três linhas. Quando estica, ele desliza para caber
         na tela em vez de vazar pela direita. */
      var largura = Math.min(
        Math.max(caixa.width, 340),
        janela.innerWidth - 16
      );
      var esquerda = Math.min(
        Math.max(8, caixa.left),
        janela.innerWidth - largura - 8
      );

      painel.style.position = "fixed";
      painel.style.left = esquerda + "px";
      painel.style.width = largura + "px";

      /* Campo perto da base da tela abre para cima -- é o caso do último
         item da proposta, com o teclado do tablet ocupando o resto. */
      if (espacoAbaixo < 200 && espacoAcima > espacoAbaixo) {
        painel.style.top = "auto";
        painel.style.bottom = (janela.innerHeight - caixa.top + folga) + "px";
        painel.style.maxHeight = Math.min(altura, espacoAcima) + "px";
      } else {
        painel.style.bottom = "auto";
        painel.style.top = (caixa.bottom + folga) + "px";
        painel.style.maxHeight = Math.min(altura, espacoAbaixo) + "px";
      }
    }

    function abrir() {
      if (!painel.hidden) return;

      document.body.appendChild(painel);
      painel.hidden = false;
      raiz.classList.add("aberta");
      entrada.setAttribute("aria-expanded", "true");
      var filtro = entrada.value === rotuloEscolhido() ? "" : entrada.value;
      if (typeof config.carregar === "function") carregarRemoto(filtro, true);
      else desenhar(filtro);
      posicionar();

      /* `true` no terceiro argumento: a rolagem que interessa é a do
         modal e a da tabela, e nenhuma das duas borbulha até o document
         sem a fase de captura. */
      janela.addEventListener("scroll", posicionar, true);
      janela.addEventListener("resize", posicionar);
    }

    function fechar(restaurar) {
      if (painel.hidden) return;

      painel.hidden = true;
      raiz.classList.remove("aberta");
      entrada.setAttribute("aria-expanded", "false");
      marcado = -1;

      janela.removeEventListener("scroll", posicionar, true);
      janela.removeEventListener("resize", posicionar);
      painel.removeAttribute("style");
      raiz.appendChild(painel);

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
      if (typeof config.carregar === "function") carregarRemoto(entrada.value, false);
      else desenhar(entrada.value);
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
      /* O painel está no <body> enquanto aberto: sem esta linha, clicar
         numa opção contaria como "clique fora" e fecharia antes da
         escolha ser registrada. */
      if (painel.contains(evento.target)) return;
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
        var existente = acharOpcao(opcao && opcao.valor);
        if (existente) Object.assign(existente, opcao);
        else {
          indexar([opcao]);
          opcoes.push(opcao);
        }
        if (escolherAgora) escolher(opcao.valor);
      },
      focar: function () { entrada.focus(); },
      /* Chamado quando o dono do campo some da tela (linha do orçamento
         removida): fecha e leva o painel junto. */
      destruir: function () {
        if (timerBusca) janela.clearTimeout(timerBusca);
        geracaoBusca += 1;
        fechar(false);
        raiz.remove();
      }
    };
  }

  janela.LSBusca = { criar: criar, semAcento: semAcento };
})(window);
