/* LISTA OU CARDS: as duas apresentações de toda lista do painel.

   Cada tela marca o contêiner da lista (`data-visao="lista"`, o padrão,
   vindo do servidor) e põe o seletor (`includes/lista_ou_cards.html`):
   dois rádios, "Lista" e "Cards". Este módulo troca o atributo do
   contêiner; quem desenha cada modo é o CSS comum de interno_modern.css
   ("LISTA OU CARDS"), a partir das mesmas marcações nos mesmos itens --
   um item, duas apresentações. Por isso o que outra frente pendura no
   item (`data-detalhe-*`, ouvintes de clique) vale nos dois modos.

   A única coisa que ele monta é a BARRA DE AÇÕES do cartão, para a lista
   que a pede (`data-visao-acoes="barra"`), e só quando ela entra em
   cards: ver "A BARRA DE AÇÕES DO CARTÃO", mais abaixo.

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

  /* ------------------------------------------------------------------
     A BARRA DE AÇÕES DO CARTÃO (`data-visao-acoes="barra"` no contêiner)

     O pedido: "nos cards, melhore as ações deixando estilo app, como um
     botão no card elegante e com bons ícones e texto". No cartão que sai
     de uma tabela, as ações eram um "⋮" sozinho no pé. Com a barra, as
     mais usadas viram botões com ícone e nome, de ponta a ponta do
     cartão, e "Mais" abre o resto numa folha de ações.

     NADA É CLONADO. As ações da linha já foram recolhidas pelo painel
     (`Painel.organizarAcoesTabelas`) no menu flutuante, com os seus
     ouvintes, formulários e CSRF. Cada botão da barra é um ATALHO: ao
     toque, aciona a ação de verdade (`acao.click()`), esteja ela onde
     estiver. E "Mais" é o próprio botão "⋮" do menu, vestido de botão
     da barra: abrir, fechar, Esc e devolver o foco continuam com o
     painel. A LISTA não muda: o que é da barra leva
     `data-visao-so="cards"`.

     QUAIS VÃO PARA A BARRA: as que a tela marcou com
     `data-acao-cartao="Nome curto"` (até três, na ordem de
     `data-acao-ordem`). Tela que não marcou nenhuma ganha as duas
     primeiras que não apagam nada. O resto fica em "Mais" -- e o que
     apaga fica sempre lá, depois de uma linha.

     A barra só é montada quando a lista entra em cards pela primeira
     vez: quem fica na lista não paga por ela.
     ------------------------------------------------------------------ */
  var NA_BARRA = 3;
  var PERIGOSA = ".btn-outline-danger,[data-excluir],[data-excluir-os],[data-acao-perigosa]";

  /* As ações de uma caixa (o menu flutuante, ou o grupo da célula quando a
     linha tem uma ação só): cada filho é a ação ou o <form> que a embrulha. */
  function acoesDe(caixa) {
    var lista = [];
    for (var i = 0; i < caixa.children.length; i += 1) {
      var no = caixa.children[i];
      // o cabeçalho do menu, o próprio "⋮" e a linha divisória não são ações
      if (no.classList.contains("ls-action-fab") || no.classList.contains("ls-action-fab-head") ||
          no.classList.contains("ls-folha-divisor")) continue;
      var acao = no.matches("a,button") ? no : no.querySelector("a,button");
      if (acao) lista.push({ no: no, acao: acao });
    }
    return lista;
  }

  function ordemDa(acao) {
    var ordem = parseInt(acao.getAttribute("data-acao-ordem"), 10);
    return isNaN(ordem) ? 99 : ordem;
  }

  function nomeDa(acao) {
    var rotulo = acao.querySelector(".ls-action-label");
    return (
      acao.getAttribute("data-acao-cartao") ||
      (rotulo && rotulo.textContent.trim()) ||
      acao.getAttribute("data-label") ||
      acao.getAttribute("title") ||
      (acao.textContent || "").trim() ||
      "Abrir"
    );
  }

  function atalho(acao, principal) {
    var link = acao.tagName === "A" && acao.getAttribute("href");
    var botao = document.createElement(link ? "a" : "button");
    if (link) {
      // Link de verdade: o botão do meio e "abrir em outra aba" continuam valendo.
      botao.setAttribute("href", link);
      if (acao.target) botao.target = acao.target;
      if (acao.rel) botao.rel = acao.rel;
    } else {
      botao.type = "button";
    }
    botao.className = "ls-cartao-acao" +
      (acao.matches(PERIGOSA) ? " ls-cartao-acao--perigo" : principal ? " ls-cartao-acao--principal" : "");
    var desenho = acao.querySelector('i[class*="bi-"]');
    var icone = document.createElement("i");
    icone.className = desenho ? desenho.className.replace(/\bm[se]-\d\b/g, "").trim() : "bi bi-arrow-right-circle";
    icone.setAttribute("aria-hidden", "true");
    var nome = document.createElement("span");
    nome.textContent = nomeDa(acao);
    botao.appendChild(icone);
    botao.appendChild(nome);
    if (acao.getAttribute("aria-label")) botao.setAttribute("aria-label", acao.getAttribute("aria-label"));
    if (acao.title) botao.title = acao.title;
    botao.addEventListener("click", function (evento) {
      evento.preventDefault();
      if (!acao.disabled) acao.click();
    });
    return botao;
  }

  /* As ações que a folha mostra, na ordem em que aparecem: o que apaga
     por último (é o CSS que o põe lá). */
  function visiveis(menu) {
    var itens = Array.prototype.filter.call(menu.querySelectorAll("a,button"), function (item) {
      return !item.disabled && item.offsetParent !== null;
    });
    function peso(item) { return item.closest(".ls-folha-perigo") ? 1 : 0; }
    return itens.sort(function (a, b) { return peso(a) - peso(b); });
  }

  function ehFolha(menu) {
    return menu.getAttribute("data-folha") === "1";
  }

  /* O "⋮" vira "Mais", e o menu dele ganha o que uma folha de ações tem:
     o nome do registro no topo, a linha antes do que apaga, o foco na
     primeira ação ao abrir e as setas só pelo que está à vista (o que já
     tem botão na barra fica escondido na folha). */
  function vestirMais(fab, menu, resto, linha) {
    var gatilho = fab.querySelector(".ls-action-fab-trigger");
    if (!gatilho) return;
    var pontos = gatilho.querySelector("i");
    if (pontos) pontos.setAttribute("data-visao-so", "lista");
    gatilho.insertAdjacentHTML(
      "beforeend",
      '<i class="bi bi-three-dots" aria-hidden="true" data-visao-so="cards"></i>' +
      '<span data-visao-so="cards">Mais</span>'
    );
    gatilho.setAttribute("aria-label", "Mais ações deste registro");
    gatilho.setAttribute("aria-haspopup", "menu");

    var cabeca = menu.querySelector(".ls-action-fab-head");
    var nome = linha && linha.getAttribute("data-visao-nome");
    if (cabeca && nome) {
      var titulo = document.createElement("strong");
      titulo.className = "ls-folha-nome";
      titulo.textContent = nome;
      cabeca.appendChild(titulo);
    }
    /* O que apaga vai para o fim da folha, depois de uma linha -- pela
       ordem do CSS (`order`), e não mexendo no menu: na lista ele continua
       na ordem em que a tela o escreveu. */
    var perigosas = resto.filter(function (item) { return item.acao.matches(PERIGOSA); });
    perigosas.forEach(function (item) { item.no.classList.add("ls-folha-perigo"); });
    if (perigosas.length && perigosas.length < resto.length) {
      var divisor = document.createElement("span");
      divisor.className = "ls-folha-divisor";
      divisor.setAttribute("role", "separator");
      menu.appendChild(divisor);
    }

    gatilho.addEventListener("click", function () {
      if (!ehFolha(menu) || !fab.classList.contains("is-open")) return;
      window.requestAnimationFrame(function () {
        var itens = visiveis(menu);
        if (itens.length) itens[0].focus({ preventScroll: true });
      });
    });
    /* Na captura, antes do ouvinte do painel: ele anda por todos os itens,
       inclusive os que a folha esconde, e o foco pararia num botão que
       não se vê. Tab fecha e devolve o foco a "Mais", como num menu. */
    menu.addEventListener("keydown", function (evento) {
      var tecla = evento.key;
      if (!ehFolha(menu) || ["ArrowDown", "ArrowUp", "Home", "End", "Tab"].indexOf(tecla) < 0) return;
      evento.preventDefault();
      evento.stopPropagation();
      if (tecla === "Tab") {
        if (fab._lsFechar) fab._lsFechar(true);
        return;
      }
      var itens = visiveis(menu);
      if (!itens.length) return;
      var atual = itens.indexOf(document.activeElement);
      var proximo = tecla === "Home" ? 0
        : tecla === "End" ? itens.length - 1
        : tecla === "ArrowDown" ? (atual + 1) % itens.length
        : (atual - 1 + itens.length) % itens.length;
      itens[proximo].focus();
    }, true);
  }

  function montarBarra(grupo) {
    // Só depois de o painel recolher as ações da linha; e uma vez só.
    if (grupo.getAttribute("data-barra") === "1" || grupo.getAttribute("data-ls-actions-ready") !== "1") return;
    grupo.setAttribute("data-barra", "1");
    var celula = grupo.parentNode;
    var fab = null;
    for (var i = 0; i < grupo.children.length; i += 1) {
      if (grupo.children[i].classList.contains("ls-action-fab")) fab = grupo.children[i];
    }
    var menu = fab && fab._lsMenu;
    var itens = acoesDe(menu || grupo);
    if (!itens.length) return;

    var principais = itens.filter(function (item) { return item.acao.hasAttribute("data-acao-cartao"); });
    if (!principais.length) {
      principais = itens.filter(function (item) { return !item.acao.matches(PERIGOSA); }).slice(0, 2);
    }
    // Linha de uma ação só não tem menu: ela vai para a barra, seja qual for.
    if (!menu) principais = itens.slice();
    principais.sort(function (a, b) { return ordemDa(a.acao) - ordemDa(b.acao); });
    principais = principais.slice(0, NA_BARRA);

    var barra = document.createElement("div");
    barra.className = "ls-cartao-acoes";
    barra.setAttribute("data-visao-so", "cards");
    principais.forEach(function (item, indice) {
      barra.appendChild(atalho(item.acao, indice === 0));
      item.no.setAttribute("data-na-barra", "1");
    });
    celula.insertBefore(barra, grupo);

    var naBarra = principais.length;
    if (fab && menu) {
      var resto = itens.filter(function (item) { return principais.indexOf(item) < 0; });
      if (resto.length) {
        vestirMais(fab, menu, resto, celula.closest("tr,[data-visao-item]"));
        naBarra += 1;
      } else {
        fab.setAttribute("data-sem-resto", "1");
      }
    }
    celula.setAttribute("data-barra-itens", String(naBarra));
  }

  function prepararAcoes(alvo, modo) {
    if (!alvo || alvo.getAttribute("data-visao-acoes") !== "barra") return;
    var emCards = modo === "cards";
    if (emCards) {
      // Idempotente: garante o menu de cada linha antes de tirar dele os atalhos.
      if (window.Painel && window.Painel.organizarAcoesTabelas) window.Painel.organizarAcoesTabelas(alvo);
      var grupos = alvo.querySelectorAll(".ls-row-actions");
      for (var i = 0; i < grupos.length; i += 1) montarBarra(grupos[i]);
      /* Com quatro botões o ícone sobe para cima do nome, senão não cabem.
         Vale para a lista inteira, e não cartão a cartão: uma fileira com
         uma barra de cada jeito parece defeito. */
      if (alvo.querySelector('[data-barra-itens="4"]')) alvo.setAttribute("data-barra-cheia", "1");
      else alvo.removeAttribute("data-barra-cheia");
    }
    // O menu mora no <body>: é por este atributo que ele sabe em que modo a lista está.
    var fabs = alvo.querySelectorAll(".ls-action-fab");
    for (var j = 0; j < fabs.length; j += 1) {
      var menu = fabs[j]._lsMenu;
      if (!menu) continue;
      if (emCards) menu.setAttribute("data-folha", "1");
      else menu.removeAttribute("data-folha");
    }
  }

  /* A logo do cartão que não carregou (arquivo apagado, rede fora): a
     imagem sai e ficam as iniciais, que estão por baixo dela. `error` não
     borbulha, por isso a escuta é na captura. */
  document.addEventListener("error", function (evento) {
    var imagem = evento.target;
    var quadro = imagem && imagem.tagName === "IMG" ? imagem.parentNode : null;
    if (quadro && quadro.getAttribute && quadro.getAttribute("data-v") === "avatar") imagem.remove();
  }, true);

  function aplicar(seletor, modo) {
    if (MODOS.indexOf(modo) < 0) modo = seletor.getAttribute("data-visao-padrao") || "lista";
    var alvo = document.getElementById(seletor.getAttribute("data-visao-alvo") || "");
    if (alvo && alvo.getAttribute("data-visao") !== modo) alvo.setAttribute("data-visao", modo);
    var radios = seletor.querySelectorAll('input[type="radio"]');
    for (var i = 0; i < radios.length; i += 1) radios[i].checked = radios[i].value === modo;
    prepararAcoes(alvo, modo);
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
