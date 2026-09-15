/* ======================================================================
   RASCUNHOS — o que estava sendo montado não se perde ao fechar a janela.

   O DEFEITO QUE ISTO RESOLVE. Montar um orçamento é um trabalho de
   minutos: cliente, seis itens, desconto combinado no telefone,
   observação de entrega. Até aqui, um toque fora da janela apagava tudo
   -- o `backdrop` do Bootstrap fecha o modal, o `form.reset()` da
   próxima abertura limpa os campos, e não havia onde procurar o que
   tinha sido digitado. Pior: no celular, sair do painel por um instante
   (abrir a galeria para conferir uma foto, atender uma ligação) põe a
   aba em segundo plano, e a volta encontrava a janela fechada e a
   gravação falhando contra um servidor que tinha adormecido.

   A PROTEÇÃO TEM DUAS CAMADAS, e as duas são necessárias:

     1. A janela não fecha mais por clique fora (`data-bs-backdrop`
        estático nos modais de montagem). O toque errado passou a não
        custar nada.

     2. Quando a janela fecha DE VERDADE -- no X, no Esc, na navegação
        para outra tela --, o que estava dentro dela é guardado e vira um
        botão flutuante na lateral direita. Um botão por rascunho: se
        houver um orçamento e uma O.S. pela metade, há dois botões. Tocar
        no botão reabre a janela exatamente como ela estava, inclusive de
        outra tela do painel -- daí ele navegar antes de reabrir.

   O QUE NÃO VIRA RASCUNHO. Abrir e fechar sem mexer em nada. O módulo
   fotografa a janela no instante em que ela abre (`show.bs.modal`, que
   é síncrono e acontece depois de a tela ter preenchido os campos) e só
   guarda o que ficou DIFERENTE dessa fotografia. Sem isso, cada espiada
   numa proposta antiga deixaria um botão flutuante para trás.

   ONDE FICA GUARDADO. `sessionStorage`, pela mesma razão que o cache de
   telas (ver `ls-soft-navigation.js`): sobrevive ao recarregamento, à
   troca de tela e ao aplicativo ir para segundo plano, mas não deixa
   dado de cliente no aparelho depois que a aba fecha. Rascunho é
   trabalho em andamento, não arquivo.

   COMO UMA TELA SE INSCREVE:

     LSRascunhos.registrar({
       tipo: "orcamento",              // uma chave por espécie
       modal: "modalOrcamento",        // id da janela
       form: "formOrcamento",          // some sozinho quando grava
       rotulo: "Orçamento",
       icone: "bi-file-earmark-text",
       coletar: function () { return {...} },   // estado serializável
       aplicar: function (dados) { ... },       // devolve o estado à tela
       resumo: function (dados) { return "Maria · 3 itens" },
       alvo: function (dados) { return dados.id || "novo" }
     });

   `coletar` e `aplicar` são da tela porque só ela sabe montar as próprias
   linhas -- o módulo não conhece orçamento nem ordem de serviço.
   ====================================================================== */
(function (janela, documento) {
  "use strict";

  var PREFIXO = "ls:rascunho:v1:";
  var PEDIDO = "ls:rascunho:abrir";
  var LIMITE = 4;
  var ESPERA_AUTO = 700;

  var registros = Object.create(null);
  var caixa = null;
  var relogioAuto = null;

  /* ------------------------------------------------------------------
     Armazenamento

     Modo privado de alguns navegadores lança ao escrever, e a cota pode
     estourar num rascunho grande. Nenhum dos dois pode derrubar a tela:
     sem armazenamento o painel continua funcionando exatamente como
     antes deste módulo existir.
     ------------------------------------------------------------------ */
  function cofre() {
    try {
      return janela.sessionStorage;
    } catch (erro) {
      return null;
    }
  }

  function chaveDe(tipo, alvo) {
    return PREFIXO + tipo + ":" + (alvo || "novo");
  }

  function ler(id) {
    var deposito = cofre();
    if (!deposito) return null;
    try {
      var bruto = deposito.getItem(id);
      var salvo = bruto ? JSON.parse(bruto) : null;
      return salvo && salvo.tipo && salvo.dados ? salvo : null;
    } catch (erro) {
      return null;
    }
  }

  function apagar(id) {
    var deposito = cofre();
    if (!deposito) return;
    try { deposito.removeItem(id); } catch (erro) {}
  }

  function listar() {
    var deposito = cofre();
    if (!deposito) return [];
    var achados = [];
    try {
      for (var i = 0; i < deposito.length; i += 1) {
        var id = deposito.key(i);
        if (!id || id.indexOf(PREFIXO) !== 0) continue;
        var salvo = ler(id);
        if (salvo) achados.push(salvo);
      }
    } catch (erro) {
      return achados;
    }
    /* O mais recente no alto: é ele que a pessoa acabou de deixar. */
    achados.sort(function (a, b) { return (b.em || 0) - (a.em || 0); });
    return achados;
  }

  function gravar(salvo) {
    var deposito = cofre();
    if (!deposito) return;
    try {
      deposito.setItem(salvo.id, JSON.stringify(salvo));
    } catch (erro) {
      /* Cota cheia: o rascunho mais antigo cede o lugar ao novo. */
      var antigos = listar();
      if (antigos.length) apagar(antigos[antigos.length - 1].id);
      try { deposito.setItem(salvo.id, JSON.stringify(salvo)); } catch (e) { return; }
    }
    listar().slice(LIMITE).forEach(function (velho) { apagar(velho.id); });
  }

  /* ------------------------------------------------------------------
     Os botões flutuantes

     Moram no `<body>`, e não dentro do conteúdo: a troca suave de tela
     substitui `.ls-content` inteiro, e um botão que vive lá dentro
     desapareceria justamente quando é mais útil -- depois de sair da
     tela de orçamentos com uma proposta pela metade.
     ------------------------------------------------------------------ */
  function montarCaixa() {
    if (caixa && caixa.isConnected) return caixa;
    caixa = documento.getElementById("lsRascunhos");
    if (!caixa) {
      caixa = documento.createElement("div");
      caixa.id = "lsRascunhos";
      caixa.className = "ls-rascunhos";
      caixa.setAttribute("aria-live", "polite");
      documento.body.appendChild(caixa);
    }
    return caixa;
  }

  function botaoDe(salvo) {
    var linha = documento.createElement("div");
    linha.className = "ls-rascunho";

    var abrir = documento.createElement("button");
    abrir.type = "button";
    abrir.className = "ls-rascunho-abrir";
    abrir.title = "Retomar " + (salvo.rotulo || "rascunho");

    var icone = documento.createElement("i");
    icone.className = "bi " + (salvo.icone || "bi-pencil-square");
    icone.setAttribute("aria-hidden", "true");
    abrir.appendChild(icone);

    var texto = documento.createElement("span");
    texto.className = "ls-rascunho-texto";
    var titulo = documento.createElement("strong");
    titulo.textContent = (salvo.rotulo || "Rascunho") + " em rascunho";
    texto.appendChild(titulo);
    var detalhe = documento.createElement("small");
    /* `textContent`: o resumo vem de campo digitado por gente. */
    detalhe.textContent = salvo.resumo || "Toque para continuar";
    texto.appendChild(detalhe);
    abrir.appendChild(texto);

    abrir.addEventListener("click", function () { retomar(salvo); });
    linha.appendChild(abrir);

    var descartar = documento.createElement("button");
    descartar.type = "button";
    descartar.className = "ls-rascunho-descartar";
    descartar.setAttribute("aria-label", "Descartar este rascunho");
    descartar.title = "Descartar este rascunho";
    descartar.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
    descartar.addEventListener("click", function () {
      apagar(salvo.id);
      desenhar();
      if (janela.Painel && janela.Painel.aviso) {
        janela.Painel.aviso("Rascunho descartado.", "ok");
      }
    });
    linha.appendChild(descartar);

    return linha;
  }

  /* A ASSINATURA DO QUE ESTÁ DESENHADO.

     Com a janela aberta o rascunho é regravado a cada pausa na digitação,
     e cada regravação chamava esta função. Redesenhar botões idênticos
     dezenas de vezes por minuto não muda um pixel (eles estão escondidos
     atrás da janela), mas custa DOM novo e faz o `aria-live` anunciar a
     mesma coisa repetidamente a quem usa leitor de tela. Só se redesenha
     quando a lista realmente mudou. */
  var desenhado = null;

  function desenhar() {
    var alvo = montarCaixa();
    var pendentes = listar();
    /* O horário fica de FORA da assinatura de propósito: ele muda a cada
       gravação automática e sozinho faria o desenho acontecer sempre,
       que é exatamente o que esta conta existe para evitar. O que se
       compara é o que aparece: quais rascunhos, e o que cada um diz. */
    var assinatura = pendentes.map(function (salvo) {
      return salvo.id + "#" + (salvo.resumo || "");
    }).join("|");

    if (assinatura === desenhado && alvo.childElementCount === pendentes.length) return;
    desenhado = assinatura;

    alvo.textContent = "";
    alvo.hidden = !pendentes.length;
    pendentes.forEach(function (salvo) { alvo.appendChild(botaoDe(salvo)); });
  }

  /* ------------------------------------------------------------------
     Retomar

     Se a tela do rascunho é esta, a janela reabre na hora.

     Se não é, o pedido fica ANOTADO no depósito antes de sair daqui. A
     troca entre telas do painel é navegação de documento (ver
     `data-ls-navigation` em `base_inner.html`), ou seja, esta página
     deixa de existir e nenhuma variável atravessa -- o bilhete no
     `sessionStorage`, sim. Quem se inscreve na tela de destino lê o
     bilhete em `atenderPedido` e abre a janela sozinho.
     ------------------------------------------------------------------ */
  function retomar(salvo) {
    var registro = registros[salvo.tipo];
    if (registro) {
      restaurar(registro, salvo);
      return;
    }

    var deposito = cofre();
    try { if (deposito) deposito.setItem(PEDIDO, salvo.id); } catch (erro) {}

    if (!salvo.tela) return;
    if (janela.LSNavigation && janela.LSNavigation.go) janela.LSNavigation.go(salvo.tela);
    else janela.location.assign(salvo.tela);
  }

  function restaurar(registro, salvo) {
    if (typeof registro.aplicar !== "function") return;
    try {
      registro.aplicar(salvo.dados);
    } catch (erro) {
      /* Rascunho de uma versão anterior da tela: melhor perder o
         rascunho do que deixar a janela num estado impossível. */
      apagar(salvo.id);
      desenhar();
      return;
    }
    /* A JANELA PASSA A SEGURAR UM RASCUNHO RETOMADO.

       Sem esta marca, fechar logo depois de retomar podia APAGAR o
       rascunho: a comparação com a janela recém-aberta é o que decide se
       há algo a guardar, e ela depende de o `show` ter fotografado a
       janela limpa ANTES de o rascunho entrar. Normalmente é o que
       acontece -- mas quando o Bootstrap adia a abertura (uma janela
       ainda fechando), a fotografia sai depois, já com o rascunho
       dentro, e "nada mudou" viraria "não há o que guardar".

       Retomar nunca pode ser um caminho para perder. Enquanto a janela
       estiver segurando um rascunho retomado, fechar guarda -- ponto. A
       marca sai na próxima abertura limpa. */
    registro._restaurado = true;

    if (janela.Painel && janela.Painel.aviso) {
      janela.Painel.aviso("Rascunho retomado.", "ok");
    }
  }

  function atenderPedido(registro) {
    var deposito = cofre();
    if (!deposito) return;
    var id = null;
    try { id = deposito.getItem(PEDIDO); } catch (erro) { return; }
    if (!id) return;

    var salvo = ler(id);
    if (!salvo || salvo.tipo !== registro.tipo) return;
    try { deposito.removeItem(PEDIDO); } catch (erro) {}
    restaurar(registro, salvo);
  }

  /* ------------------------------------------------------------------
     Fotografar e guardar
     ------------------------------------------------------------------ */
  function fotografar(registro) {
    if (typeof registro.coletar !== "function") return null;
    try {
      return registro.coletar();
    } catch (erro) {
      return null;
    }
  }

  function texto(registro, dados) {
    if (typeof registro.resumo !== "function") return "";
    try {
      return String(registro.resumo(dados) || "");
    } catch (erro) {
      return "";
    }
  }

  function alvoDe(registro, dados) {
    if (typeof registro.alvo !== "function") return "novo";
    try {
      return String(registro.alvo(dados) || "novo");
    } catch (erro) {
      return "novo";
    }
  }

  function guardar(registro) {
    if (!registro || !registro.elemento) return;

    /* Janela escondida para o cadastro-filho (novo cliente, nova peça)
       não fechou: ela volta em seguida com tudo dentro. Ver
       `Painel.abrirFilho`. */
    if (registro.elemento.dataset.lsPausado) return;

    /* ACABOU DE GRAVAR: a janela fechou porque o trabalho terminou.

       A marca vale até a próxima ABERTURA, e não até a próxima chamada.
       Gravar dispara duas passagens por aqui em sequência -- a da troca
       de tela, que acontece antes, e a do `hidden` da janela, que chega
       depois --, e uma marca de uso único deixaria a segunda recriar o
       rascunho do que acabou de ser salvo. Quem a apaga é o `show`. */
    if (registro._gravado) return;

    var dados = fotografar(registro);
    var id = chaveDe(registro.tipo, alvoDe(registro, dados));

    if (!dados || (!registro._restaurado && JSON.stringify(dados) === registro._limpo)) {
      apagar(id);
      desenhar();
      return;
    }

    gravar({
      id: id,
      tipo: registro.tipo,
      alvo: alvoDe(registro, dados),
      rotulo: registro.rotulo || "Rascunho",
      icone: registro.icone || "bi-pencil-square",
      tela: registro.tela,
      em: Date.now(),
      resumo: texto(registro, dados),
      dados: dados
    });
    desenhar();
  }

  function guardarAbertos() {
    Object.keys(registros).forEach(function (tipo) {
      var registro = registros[tipo];
      if (registro.elemento && registro.elemento.classList.contains("show")) {
        guardar(registro);
      }
    });
  }

  /* Enquanto a janela está aberta o rascunho é atualizado em silêncio.
     É o que sobrevive ao aplicativo ir para segundo plano sem aviso --
     abrir a galeria, atender o telefone, o sistema recolher a aba. */
  function agendarAuto() {
    if (relogioAuto) janela.clearTimeout(relogioAuto);
    relogioAuto = janela.setTimeout(function () {
      relogioAuto = null;
      guardarAbertos();
    }, ESPERA_AUTO);
  }

  documento.addEventListener("visibilitychange", function () {
    if (documento.visibilityState === "hidden") guardarAbertos();
  });
  janela.addEventListener("pagehide", guardarAbertos);

  /* ------------------------------------------------------------------
     API
     ------------------------------------------------------------------ */
  janela.LSRascunhos = {
    registrar: function (config) {
      if (!config || !config.tipo || !config.modal) return;
      var elemento = documento.getElementById(config.modal);
      if (!elemento) return;

      var registro = {
        tipo: config.tipo,
        elemento: elemento,
        rotulo: config.rotulo,
        icone: config.icone,
        tela: config.tela || janela.location.pathname,
        coletar: config.coletar,
        aplicar: config.aplicar,
        resumo: config.resumo,
        alvo: config.alvo,
        _limpo: null,
        _gravado: false,
        _restaurado: false
      };
      registros[config.tipo] = registro;

      /* `show`, e não `shown`: ele é disparado dentro do próprio
         `show()`, ou seja, no mesmo instante em que a tela terminou de
         preencher os campos e antes de qualquer rascunho ser reposto por
         cima. É essa a fotografia do "nada foi mexido". */
      elemento.addEventListener("show.bs.modal", function () {
        if (elemento.dataset.lsPausado) return;
        registro._gravado = false;
        registro._restaurado = false;
        registro._limpo = JSON.stringify(fotografar(registro));
      });

      /* A tela pode abrir a janela ANTES de se inscrever -- é o que
         acontece com `?editar=` e `?novo=1`, atendidos no alto do script.
         Sem esta linha o `show` já teria passado, a fotografia do "nada
         foi mexido" não existiria, e abrir e fechar sem tocar em nada
         deixaria um botão flutuante para trás. */
      if (elemento.classList.contains("show")
          || elemento.dataset.lsModalEstado === "show"
          || elemento.dataset.lsModalEstado === "shown") {
        registro._limpo = JSON.stringify(fotografar(registro));
      }

      elemento.addEventListener("hidden.bs.modal", function () {
        guardar(registro);
      });

      elemento.addEventListener("input", agendarAuto);
      elemento.addEventListener("change", agendarAuto);

      if (config.form) {
        var form = documento.getElementById(config.form);
        if (form) {
          form.addEventListener("ls:gravado", function () {
            registro._gravado = true;
            /* A chave é calculada COM A JANELA AINDA COMO ESTAVA: numa
               proposta nova o campo de id continua vazio neste instante,
               então o alvo é "novo" -- o mesmo com que ela foi guardada.
               Apagar "novo" por precaução, além deste, jogaria fora o
               rascunho de OUTRA proposta nova que estivesse pendurada. */
            apagar(chaveDe(registro.tipo, alvoDe(registro, fotografar(registro))));
            desenhar();
          });
        }
      }

      desenhar();
      atenderPedido(registro);
    },

    /* Chamado por `Painel.prepararNavegacao`, imediatamente antes de a
       tela ser trocada: é a última chance de guardar uma janela aberta,
       porque a troca descarta os modais sem disparar `hidden`. */
    aoSairDaTela: function () {
      if (relogioAuto) { janela.clearTimeout(relogioAuto); relogioAuto = null; }
      guardarAbertos();
      registros = Object.create(null);
      desenhar();
    },

    /* Para quem grava fora do caminho do `Painel.ligar`. */
    concluir: function (tipo) {
      listar().forEach(function (salvo) {
        if (salvo.tipo === tipo) apagar(salvo.id);
      });
      desenhar();
    },

    pendentes: listar,
    redesenhar: desenhar
  };

  if (documento.readyState === "loading") {
    documento.addEventListener("DOMContentLoaded", desenhar);
  } else {
    desenhar();
  }
})(window, document);
