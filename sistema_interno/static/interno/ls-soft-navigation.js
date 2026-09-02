/* Navegação suave e cache curto do painel interno.
 *
 * O HTML recente fica somente no sessionStorage: acelera voltar entre telas
 * no mesmo turno sem deixar dados de um usuário disponíveis após fechar a aba.
 */
(function (window, document) {
  "use strict";

  var PREFIXO = "ls:nav:v2:";
  var INDICE = PREFIXO + "index";
  var LIMITE = 7;
  var TTL_TELA = 90000;
  var TTL_FILTRO = 30000;
  var emVoo = new Map();
  var navegacao = 0;
  var prefetchTimer = null;
  var prefetchsExecutados = 0;
  var LIMITE_PREFETCH = 6;
  /* UMA SONDAGEM CURTA, DEPOIS UMA ESPERA LONGA -- E SÓ.

     Eram quatro tentativas de doze segundos: até 52 segundos por tela,
     quase todos em silêncio. Pior que o tempo era o formato. Repetir
     tentativas curtas contra uma instância que está ACORDANDO é o pior
     dos mundos: cada `abort` joga fora o pedido que já estava na fila do
     servidor e recomeça do zero, e a instância que ia responder no
     segundo 40 nunca chega a responder.

     Duas tentativas, com propósitos diferentes:

       1ª, 8 segundos -- a sondagem. Cobre lentidão normal de rede. Se
          falhar, o servidor não está só lento: está fora ou subindo.
       2ª, 50 segundos -- a espera. É a faixa em que uma instância
          suspensa volta. UM pedido, aberto, que é atendido no instante
          em que o processo sobe.

     O teto passou de 52 para 58 segundos, mas o que importa é que agora
     ele TERMINA com a tela carregada em vez de terminar em desistência.
     E a tarja diz o que está acontecendo desde o primeiro segundo. */
  var TIMEOUT_REDE = 8000;
  var TIMEOUT_REDE_DESPERTAR = 50000;
  var MAX_TENTATIVAS_REDE = 2;
  var ATRASOS_REDE = [0, 400];

  function urlSegura(valor) {
    try {
      var url = new URL(valor, window.location.href);
      return url.origin === window.location.origin ? url : null;
    } catch (erro) {
      return null;
    }
  }

  function chave(url) {
    return PREFIXO + url.href;
  }

  function lerIndice() {
    try {
      var bruto = window.sessionStorage.getItem(INDICE);
      var itens = bruto ? JSON.parse(bruto) : [];
      return Array.isArray(itens) ? itens : [];
    } catch (erro) {
      return [];
    }
  }

  function gravarIndice(itens) {
    try {
      window.sessionStorage.setItem(INDICE, JSON.stringify(itens.slice(0, LIMITE)));
    } catch (erro) {}
  }

  function removerChave(item) {
    try { window.sessionStorage.removeItem(item); } catch (erro) {}
  }

  function guardar(url, html) {
    if (!html || html.length > 850000) return;
    var item = chave(url);
    try {
      window.sessionStorage.setItem(item, JSON.stringify({
        em: Date.now(),
        html: html
      }));
      var indice = lerIndice().filter(function (existente) {
        return existente !== item;
      });
      indice.unshift(item);
      indice.slice(LIMITE).forEach(removerChave);
      gravarIndice(indice);
    } catch (erro) {
      lerIndice().slice(3).forEach(removerChave);
    }
  }

  function ttl(url) {
    return url.pathname === window.location.pathname && url.search
      ? TTL_FILTRO
      : TTL_TELA;
  }

  function recuperar(url) {
    try {
      var bruto = window.sessionStorage.getItem(chave(url));
      var salvo = bruto ? JSON.parse(bruto) : null;
      if (!salvo || !salvo.html || Date.now() - salvo.em > ttl(url)) {
        removerChave(chave(url));
        return null;
      }
      return salvo.html;
    } catch (erro) {
      return null;
    }
  }

  function limpar() {
    lerIndice().forEach(removerChave);
    removerChave(INDICE);
  }

  function esperar(ms) {
    return new Promise(function (resolver) { window.setTimeout(resolver, ms); });
  }

  function podeTentarNovamente(status) {
    return status === 408 || status === 429 || status === 500
      || status === 502 || status === 503 || status === 504;
  }

  function atrasoDaTentativa(tentativa, resposta) {
    var cabecalho = resposta && resposta.headers
      ? Number(resposta.headers.get("retry-after"))
      : 0;
    if (cabecalho > 0 && cabecalho <= 10) return cabecalho * 1000;
    return ATRASOS_REDE[Math.min(tentativa + 1, ATRASOS_REDE.length - 1)];
  }

  /* BUSCA DE FUNDO NÃO FALA COM A TELA.

     Este era o defeito: a antecipação (o `prefetch` que dispara quando o
     dedo encosta num link) usava o MESMO caminho da navegação de
     verdade. Se ela demorasse -- e ela demora, porque é justamente a
     tela que ainda não está em lugar nenhum --, a segunda tentativa
     chamava `escalarLoader` e a tarja "Servidor acordando…" nascia por
     cima de uma tela que já estava carregada e funcionando.

     Pior: como ninguém navegou, ninguém chamava `esconderLoader`. A
     tarja ficava lá, contando segundos, para sempre. Foi o que a fábrica
     viu marcando 351 segundos sobre uma tela pronta.

     Agora quem pede de fundo pede em silêncio. A tarja pertence à
     navegação que a pessoa realmente iniciou. */
  function requisitar(url, tentativa, silencioso) {
    var controlador = "AbortController" in window ? new AbortController() : null;
    /* A primeira é sondagem; da segunda em diante é espera de despertar. */
    var prazo = tentativa === 0 ? TIMEOUT_REDE : TIMEOUT_REDE_DESPERTAR;
    var timer = controlador ? window.setTimeout(function () { controlador.abort(); }, prazo) : null;
    if (tentativa > 0 && !silencioso) escalarLoader(tentativa);

    return window.fetch(url.href, {
      method: "GET",
      credentials: "same-origin",
      headers: { "X-Requested-With": "LS-Soft-Navigation" },
      cache: "default",
      signal: controlador ? controlador.signal : undefined
    }).then(function (resposta) {
      if (
        tentativa < MAX_TENTATIVAS_REDE - 1
        && podeTentarNovamente(resposta.status)
      ) {
        return esperar(atrasoDaTentativa(tentativa, resposta)).then(function () {
          return requisitar(url, tentativa + 1, silencioso);
        });
      }

      var tipo = resposta.headers.get("content-type") || "";
      if (!resposta.ok || tipo.indexOf("text/html") === -1) {
        var erro = new Error("Resposta incompatível com navegação suave.");
        erro.status = resposta.status;
        throw erro;
      }

      var finalUrl = urlSegura(resposta.url);
      if (!finalUrl) throw new Error("A navegação saiu do painel.");

      /* A resposta acabou de atravessar Django e banco. O próximo POST
         não precisa esperar outro GET em /pronto/ para provar a mesma
         conexão. */
      if (window.Painel && window.Painel.rede) {
        window.Painel.rede.marcarSucesso();
      }

      var controleCache = (resposta.headers.get("cache-control") || "").toLowerCase();
      var cachePermitido = controleCache.indexOf("no-store") === -1
        && resposta.headers.get("x-ls-no-store") !== "1";
      return resposta.text().then(function (html) {
        if (cachePermitido && finalUrl.pathname.indexOf("/login/inner/") === -1) {
          guardar(finalUrl, html);
          if (
            finalUrl.href !== url.href
            && finalUrl.searchParams.get("recuperado") !== "pagina"
          ) guardar(url, html);
        }
        return { html: html, url: finalUrl };
      });
    }).catch(function (erro) {
      if (
        tentativa < MAX_TENTATIVAS_REDE - 1
        && !erro.lsTentativaFinal
        && (!erro.status || podeTentarNovamente(erro.status))
      ) {
        return esperar(atrasoDaTentativa(tentativa)).then(function () {
          return requisitar(url, tentativa + 1, silencioso);
        });
      }
      erro.lsTentativaFinal = true;
      erro.lsTransitorio = !erro.status || podeTentarNovamente(erro.status);
      throw erro;
    }).finally(function () {
      if (timer) window.clearTimeout(timer);
    });
  }

  function buscar(url, silencioso) {
    var id = url.href;
    if (emVoo.has(id)) return emVoo.get(id);

    var pedido = requisitar(url, 0, silencioso).finally(function () {
      emVoo.delete(id);
    });

    emVoo.set(id, pedido);
    return pedido;
  }

  /* ======================================================================
     A BARRA DE CARREGAMENTO SÓ APARECE SE HOUVER ESPERA DE VERDADE.

     Ela aparecia a cada clique. Como a troca de tela normalmente termina
     em pouco mais de cem milissegundos, o que se via era um risco
     atravessando o topo e sumindo -- e é isso que dá a sensação de
     "carregando" numa troca que, para o usuário, deveria ser só a tela
     nova aparecendo.

     Diferente de uma navegação de verdade, aqui NADA se perde enquanto a
     espera dura: a tela anterior continua inteira e clicável. Uma barra
     que informa o que ninguém está esperando é ruído.

     Então ela é agendada, não mostrada. Se a tela nova chegar antes do
     prazo -- que é o caso comum, e sempre o caso quando a página já está
     no cache da aba --, o agendamento é cancelado e ninguém vê nada. Se
     demorar, aí sim a barra entra, porque aí sim há uma espera.
     ====================================================================== */
  var ESPERA_ATE_AVISAR = 400;
  var loaderAgendado = null;
  var loaderMensagem = "";

  /* Passado este prazo a troca deixou de ser instantânea e virou espera.
     Aí não basta a barra fina de 3px no topo: no celular ela some no
     recorte da tela, e quem está olhando conclui que o toque não pegou.
     A tarja diz, em palavras, o que está acontecendo. */
  var ESPERA_ATE_EXPLICAR = 1400;
  var explicarAgendado = null;

  function mostrarLoader(mensagem) {
    cancelarLoader();
    loaderMensagem = mensagem || "Carregando…";
    loaderAgendado = window.setTimeout(function () {
      loaderAgendado = null;
      if (window.LSLoader && window.LSLoader.show) {
        window.LSLoader.show(loaderMensagem);
      }
    }, ESPERA_ATE_AVISAR);

    explicarAgendado = window.setTimeout(function () {
      explicarAgendado = null;
      if (window.Painel && window.Painel.ocupado) {
        window.Painel.ocupado(loaderMensagem);
      }
    }, ESPERA_ATE_EXPLICAR);
  }

  /* A partir da segunda tentativa a espera tem nome: não é lentidão da
     tela, é o servidor voltando. Dizer isso evita o toque repetido, que
     só põe mais uma requisição na fila de um servidor que já está lento. */
  function escalarLoader(tentativa) {
    /* A primeira sondagem falhou: isso não é rede lenta, é servidor
       subindo. Dizer quanto isso costuma levar é o que impede o toque
       repetido -- que cancela o pedido em curso e recomeça a conta. */
    loaderMensagem = tentativa >= 2
      ? "O servidor está demorando. Ainda tentando…"
      : "Servidor acordando (até 1 minuto na primeira vez)…";
    if (window.LSLoader && window.LSLoader.show) window.LSLoader.show(loaderMensagem);
    if (window.Painel && window.Painel.ocupado) window.Painel.ocupado(loaderMensagem);
  }

  function cancelarLoader() {
    if (loaderAgendado) {
      window.clearTimeout(loaderAgendado);
      loaderAgendado = null;
    }
    if (explicarAgendado) {
      window.clearTimeout(explicarAgendado);
      explicarAgendado = null;
    }
  }

  function esconderLoader() {
    cancelarLoader();
    if (window.LSLoader && window.LSLoader.hide) window.LSLoader.hide();
    /* A tarja explicativa sai junto: ela existe por causa da espera, e a
       espera acabou. */
    if (window.Painel && window.Painel.pronto) window.Painel.pronto();
  }

  var recuperacaoTimer = null;

  function esconderRecuperacao() {
    if (recuperacaoTimer) window.clearTimeout(recuperacaoTimer);
    recuperacaoTimer = null;
    var aviso = document.getElementById("lsNavRecovery");
    if (aviso) aviso.remove();
  }

  function mostrarRecuperacao(url, modoHistorico) {
    esconderLoader();
    esconderRecuperacao();

    var aviso = document.createElement("div");
    aviso.id = "lsNavRecovery";
    aviso.className = "ls-nav-recovery";
    aviso.setAttribute("role", "status");
    aviso.innerHTML =
      '<span class="ls-nav-recovery-icon"><i class="bi bi-arrow-repeat"></i></span>' +
      '<span class="ls-nav-recovery-copy"><strong>Servidor retomando</strong>' +
      '<small>A tela atual continua segura. Tentaremos novamente sem abrir uma página 502.</small></span>' +
      '<button type="button" class="btn btn-sm btn-warning">Tentar agora</button>';
    document.body.appendChild(aviso);

    aviso.querySelector("button").addEventListener("click", function () {
      navegar(url, modoHistorico || "push");
    });

    /* Uma instância adormecida costuma voltar sozinha. A tentativa
       automática só acontece com a aba visível e rede disponível; sem
       isso o aviso permanece, sem martelar o servidor. */
    recuperacaoTimer = window.setTimeout(function () {
      recuperacaoTimer = null;
      if (document.visibilityState !== "visible" || navigator.onLine === false) return;
      navegar(url, modoHistorico || "push");
    }, 3500);
  }

  function fecharMenuMovel() {
    if (typeof window.LSFecharMenuTablet === "function") {
      window.LSFecharMenuTablet();
      return;
    }
    var sidebar = document.getElementById("sidebarMenu");
    var overlay = document.getElementById("sidebarOverlay");
    var toggle = document.getElementById("menuToggle");
    if (sidebar) sidebar.classList.remove("open");
    if (overlay) overlay.classList.remove("open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    document.body.classList.remove("menu-open");
  }

  /* ======================================================================
     A TROCA DE TELA

     ANTES ERA `document.write`, E ERA A ORIGEM DOS DOIS DEFEITOS QUE MAIS
     APARECIAM NO TABLET.

     `document.open()` + `document.write()` joga fora o documento inteiro e
     manda o navegador analisar tudo de novo -- inclusive o `<head>`. As
     folhas de estilo voltam para a fila de download e a fonte dos ícones
     junto. Existe, então, uma janela de tempo em que o HTML novo já está
     na tela e o CSS ainda não chegou:

       * o logotipo aparece no tamanho original do arquivo, ocupando a
         tela ("a imagem gigante");
       * `<i class="bi bi-send">` cai na fonte do sistema, e o ponto de
         código da Bootstrap Icons (\f6c0, área de uso privado) vira o que
         quer que o aparelho tenha ali -- em vários Android, um emoji
         antigo. É o coelho no botão de enviar.

     Nada disso era aleatório: era sempre a mesma janela, e ela abre por
     mais tempo quanto pior estiver a rede -- que é a condição normal do
     galpão.

     AGORA SE TROCA SÓ O QUE MUDA. O cabeçalho, o menu e a barra de cima
     continuam os mesmos nós, com os mesmos ouvintes e o mesmo CSS já
     aplicado; troca-se o conteúdo da tela, o título, a classe do corpo e
     os destaques do menu. O CSS da tela nova é carregado ANTES da troca,
     nunca depois: se ele não chegar, a tela velha continua inteira e o
     aviso de conexão aparece. Não existe mais o instante sem estilo.
     ====================================================================== */
  var FOLHA_BASE = "lsFolhaBase";
  var CAIXA_SCRIPTS = "lsTelaScripts";
  var TEMPO_FOLHA = 6000;

  function nucleo(doc) {
    return doc.querySelector(".ls-content");
  }

  function esperarFolha(link) {
    return new Promise(function (resolver) {
      var pronto = false;
      function terminar() {
        if (pronto) return;
        pronto = true;
        resolver();
      }
      link.addEventListener("load", terminar);
      /* Erro também resolve: uma folha a menos deixa a tela feia, e
         travar a navegação por causa dela deixaria a tela ausente. */
      link.addEventListener("error", terminar);
      window.setTimeout(terminar, TEMPO_FOLHA);
    });
  }

  /* As folhas da tela nova entram no MESMO ponto do `<head>` em que o
     servidor as escreveu: antes da folha do painel, que precisa continuar
     tendo a última palavra. Anexar no fim inverteria a cascata e a tela
     abriria com a cor errada. */
  function garantirFolhas(novoDoc) {
    var ancora = document.getElementById(FOLHA_BASE);
    var cabeca = document.head;
    var espera = [];

    /* O QUE A TELA NOVA PEDE, E SÓ ISSO.

       As folhas do painel (as do `base_inner`) ficam para sempre: são as
       mesmas em toda tela. As de TELA vêm marcadas com `data-ls-tela`, e
       essas entram e saem junto com a tela que as pediu.

       Sem a saída, a folha do catálogo do site entrava na primeira tela
       de /site/ e continuava valendo em cima da lista de orçamentos e da
       produção pelo resto da sessão -- a tela certa, com as regras de
       outra. É uma das caras de "o CSS bugou quando troquei de tela".

       A comparação é entre endereços JÁ RESOLVIDOS, e isso importa: no
       HTML o atributo é relativo ("/static/..."), enquanto a propriedade
       `.href` devolve o absoluto. Comparar um com o outro nunca casa --
       e a cada troca o painel reanexava as MESMAS folhas, dobrando a
       lista do `<head>`. */
    var pedidas = {};
    novoDoc.head.querySelectorAll('link[rel="stylesheet"]').forEach(function (folha) {
      if (folha.href) pedidas[folha.href] = true;
    });

    cabeca.querySelectorAll('link[rel="stylesheet"][data-ls-tela]').forEach(function (folha) {
      if (!pedidas[folha.href]) folha.remove();
    });

    var jaTem = {};
    cabeca.querySelectorAll('link[rel="stylesheet"]').forEach(function (folha) {
      if (folha.href) jaTem[folha.href] = true;
    });

    novoDoc.head.querySelectorAll('link[rel="stylesheet"]').forEach(function (folha) {
      var href = folha.href;
      if (!href || jaTem[href]) return;
      jaTem[href] = true;

      var copia = document.createElement("link");
      copia.rel = "stylesheet";
      copia.href = href;
      copia.setAttribute("data-ls-tela", "1");
      espera.push(esperarFolha(copia));
      cabeca.insertBefore(copia, ancora || null);
    });

    /* O `<style>` de tela (o bloco extra_css) é sempre da tela que está
       saindo: some com ela e volta escrito pela que chega. */
    cabeca.querySelectorAll("style[data-ls-tela]").forEach(function (velho) {
      velho.remove();
    });
    novoDoc.head.querySelectorAll("style:not([data-ls-base])").forEach(function (estilo) {
      var copia = document.createElement("style");
      copia.textContent = estilo.textContent;
      copia.setAttribute("data-ls-tela", "1");
      cabeca.insertBefore(copia, ancora || null);
    });

    return espera.length ? Promise.all(espera) : Promise.resolve();
  }

  /* O menu é o mesmo nó do início ao fim da sessão -- é o que evita o
     piscar da lateral a cada clique. O que muda é qual item está aceso e
     quantos itens cada bolinha conta; isso vem copiado da tela nova, que
     o servidor acabou de desenhar com os números de agora. */
  function sincronizarMenu(novoDoc) {
    [".ls-nav-item", ".ls-aba"].forEach(function (seletor) {
      var atuais = document.querySelectorAll(seletor);
      var novos = novoDoc.querySelectorAll(seletor);
      if (atuais.length !== novos.length) return;  /* Permissão mudou: deixa como está. */
      atuais.forEach(function (item, indice) {
        item.className = novos[indice].className;
        var marca = novos[indice].getAttribute("aria-current");
        if (marca) item.setAttribute("aria-current", marca);
        else item.removeAttribute("aria-current");
      });
    });

    document.querySelectorAll("[data-selo]").forEach(function (selo) {
      var origem = novoDoc.querySelector(
        '[data-selo="' + selo.getAttribute("data-selo") + '"]'
      );
      if (!origem) return;
      selo.textContent = origem.textContent;
      selo.hidden = origem.hidden;
    });
  }

  /* Script trocado por innerHTML não roda: o navegador ignora `<script>`
     inserido como texto. Cada um é recriado como elemento novo para que o
     navegador o execute -- é isto que faz a tela que chega ganhar o seu
     JavaScript, papel que antes era do `document.write`. */
  function trocarScripts(novoDoc) {
    var caixa = document.getElementById(CAIXA_SCRIPTS);
    var nova = novoDoc.getElementById(CAIXA_SCRIPTS);
    if (!caixa) return;

    caixa.textContent = "";
    if (!nova) return;

    nova.querySelectorAll("script").forEach(function (original) {
      var copia = document.createElement("script");
      for (var i = 0; i < original.attributes.length; i += 1) {
        var atributo = original.attributes[i];
        copia.setAttribute(atributo.name, atributo.value);
      }
      copia.textContent = original.textContent;
      caixa.appendChild(copia);
    });

    /* Os dados de tela viajam em <script type="application/json">, que
       não executa nada: entram junto porque o script da tela os lê pelo
       id logo em seguida. */
  }

  function aplicarTela(novoDoc, url, modoHistorico, versao) {
    /* Uma troca antiga nunca pode ganhar de um clique mais novo. A folha
       pode ter demorado a carregar ou a View Transition pode ter adiado o
       callback; em ambos os casos, só a navegação mais recente escreve. */
    if (versao !== navegacao) return false;
    var destino = nucleo(novoDoc);
    var atual = nucleo(document);
    if (!destino || !atual) return false;

    if (window.Painel && window.Painel.prepararNavegacao) {
      window.Painel.prepararNavegacao();
    }

    if (modoHistorico === "push") {
      window.history.pushState({ lsSoftNavigation: true }, "", url.href);
    } else if (modoHistorico === "replace") {
      window.history.replaceState({ lsSoftNavigation: true }, "", url.href);
    }

    document.title = novoDoc.title || document.title;

    /* A classe do corpo é o que diz ao CSS qual tela está aberta
       (ls-orcamentos-body, ls-os-body...). Sem copiar, a tela nova abria
       com as regras de largura da tela anterior -- tabela espremida,
       botão fora do lugar. `modal-open` fica de fora: quem cuida dela é
       `prepararNavegacao`, que acabou de rodar. */
    var classeAberta = document.body.classList.contains("modal-open");
    document.body.className = novoDoc.body.className;
    if (classeAberta) document.body.classList.add("modal-open");

    var titulo = document.querySelector(".ls-topbar-copy strong");
    var tituloNovo = novoDoc.querySelector(".ls-topbar-copy strong");
    if (titulo && tituloNovo) titulo.textContent = tituloNovo.textContent;

    atual.replaceWith(document.importNode(destino, true));
    sincronizarMenu(novoDoc);
    fecharMenuMovel();

    /* A ORDEM AQUI COPIA A DE UMA ABERTURA NORMAL: primeiro o painel
       monta a tela (máscara, textarea, ações de tabela), depois roda o
       script da tela. Numa página carregada do zero é isso que acontece,
       porque `painel.js` vem antes do bloco de scripts no corpo. Trocar
       a ordem aqui faria a mesma tela se comportar de um jeito ao abrir
       direto e de outro ao chegar pelo menu -- a pior espécie de defeito,
       porque não se reproduz quando se vai procurar. */
    if (window.Painel && window.Painel.montarTela) {
      window.Painel.montarTela(document);
    }
    trocarScripts(novoDoc);

    /* Tela nova começa do começo. Sem isto, quem estava no rodapé de uma
       lista longa abria a próxima tela no meio dela. */
    window.scrollTo(0, 0);

    /* Quem navega pelo teclado ou por leitor de tela precisa saber que a
       página mudou: sem mover o foco, o leitor continua anunciando a tela
       anterior e o Tab volta do começo do menu. */
    var conteudo = nucleo(document);
    if (conteudo) {
      conteudo.setAttribute("tabindex", "-1");
      conteudo.focus({ preventScroll: true });
    }

    esconderLoader();
    return true;
  }

  function trocarDocumento(html, url, modoHistorico, versao) {
    if (versao !== navegacao) return;
    var novoDoc;
    try {
      novoDoc = new DOMParser().parseFromString(html, "text/html");
    } catch (erro) {
      novoDoc = null;
    }

    /* Fora do contrato do painel -- login, sessão encerrada, tela de
       recuperação -- a navegação de verdade é a resposta certa: essas
       páginas têm cabeçalho próprio e não cabem dentro desta. */
    if (!novoDoc || !nucleo(novoDoc) || !nucleo(document)) {
      window.location.assign(url.href);
      return;
    }

    /* O CSS ANTES DO HTML. Enquanto a folha da tela nova não chegou, o
       que está na tela é a tela ANTERIOR, inteira e estilizada -- e não
       um esqueleto sem estilo. */
    garantirFolhas(novoDoc).then(function () {
      if (versao !== navegacao) return;
      if (!trocarComTransicao(novoDoc, url, modoHistorico, versao)) {
        window.location.assign(url.href);
      }
    }).catch(function () {
      if (versao === navegacao) window.location.assign(url.href);
    });
  }

  /* ======================================================================
     A TROCA NÃO PODE PARECER UM SOBRESSALTO

     Substituir a área de conteúdo é instantâneo, e instantâneo demais tem
     um problema próprio: a tela pisca de um assunto para outro sem nada
     que ligue os dois, e o olho registra isso como falha, não como
     navegação. Havia uma animação de entrada para suavizar, mas ela era
     do tempo do `document.write`: nascia com o conteúdo em 45% de
     opacidade, ou seja, mostrava a tela nova CHEGANDO -- exatamente o que
     não se quer ver.

     `startViewTransition` resolve pelo caminho certo: o navegador
     fotografa a tela antes, deixa a troca acontecer sem nada na tela, e
     faz a passagem entre as duas fotos. Quem olha vê uma tela virar a
     outra, e em momento nenhum vê o meio do caminho.

     Onde a API não existe (Safari mais antigo, Firefox), a troca é
     direta -- que é o comportamento de antes e continua correto. Nada
     aqui é obrigatório para a tela funcionar; é só a diferença entre
     trocar e trocar bem.
     ====================================================================== */
  function trocarComTransicao(novoDoc, url, modoHistorico, versao) {
    if (versao !== navegacao) return true;
    if (
      !document.startViewTransition
      || window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return aplicarTela(novoDoc, url, modoHistorico, versao);
    }

    /* O retorno do callback é assíncrono -- ele roda depois de o
       navegador fotografar a tela --, então a falha é tratada lá dentro,
       e não pelo valor devolvido aqui. Na prática ela não acontece:
       `trocarDocumento` já conferiu que as duas telas existem antes de
       chegar aqui. O caminho fica escrito mesmo assim, porque o dia em
       que acontecer a tela não pode simplesmente ficar parada. */
    try {
      document.startViewTransition(function () {
        if (versao !== navegacao) return;
        if (!aplicarTela(novoDoc, url, modoHistorico, versao)) {
          window.location.assign(url.href);
        }
      });
    } catch (erro) {
      return aplicarTela(novoDoc, url, modoHistorico, versao);
    }
    return true;
  }

  /* DEVOLVE PROMESSA.

     Quem chama `LSAtualizarTela` depois de gravar precisa saber quando a
     lista nova está de fato na tela, para só então tirar a tarja de
     "atualizando". Antes esta função não devolvia nada e a tarja tinha
     de sair no chute, por tempo. */
  function navegar(url, modoHistorico) {
    var alvo = urlSegura(url);
    if (!alvo) {
      window.location.assign(String(url));
      return Promise.resolve();
    }

    var minhaNavegacao = ++navegacao;
    esconderRecuperacao();
    /* A gaveta nunca acompanha a pessoa para a tela seguinte. Fechá-la
       já no toque também deixa o conteúdo anterior disponível durante
       os poucos milissegundos em que a próxima tela está chegando. */
    fecharMenuMovel();
    mostrarLoader("Carregando " + (alvo.pathname === window.location.pathname ? "resultados…" : "a tela…"));

    var cache = recuperar(alvo);
    if (cache) {
      trocarDocumento(cache, alvo, modoHistorico || "push", minhaNavegacao);
      return Promise.resolve();
    }

    return buscar(alvo).then(function (resultado) {
      if (minhaNavegacao !== navegacao) return;
      trocarDocumento(
        resultado.html, resultado.url, modoHistorico || "push", minhaNavegacao
      );
    }).catch(function (erro) {
      if (minhaNavegacao !== navegacao) return;
      /* Em falha transitória, navegar a página inteira entregaria o
         operador diretamente ao 502 do proxy e apagaria a tela boa que
         ainda está aberta. Mantemos o painel e continuamos tentando.
         Respostas definitivas (login, permissão, rota inválida) seguem
         pela navegação normal, pois exigem outro documento. */
      if (erro && erro.lsTransitorio) {
        mostrarRecuperacao(alvo, modoHistorico || "push");
        return;
      }
      esconderLoader();
      window.location.assign(alvo.href);
    });
  }

  /* POST confirmado não precisa recarregar cabeçalho, menu, fontes e
     scripts globais. Limpa o HTML antigo do cache e busca somente o miolo
     atual, preservando a recuperação de conexão da navegação suave. */
  window.LSAtualizarTela = function () {
    limpar();
    return navegar(window.location.href, "replace");
  };

  function linkNavegavel(link, evento) {
    if (!link || evento.defaultPrevented) return null;
    if (evento.type === "click" && evento.button !== 0) return null;
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return null;
    if (link.hasAttribute("download") || link.target === "_blank") return null;
    if (link.dataset.noSoftNav === "true" || link.dataset.bsToggle) return null;

    var href = link.getAttribute("href") || "";
    if (!href || href.charAt(0) === "#" || /^(mailto:|tel:|javascript:|whatsapp:|blob:|data:)/i.test(href)) {
      return null;
    }

    var url = urlSegura(link.href);
    if (!url) return null;
    if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) {
      return null;
    }
    return url;
  }

  document.addEventListener("click", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    var url = linkNavegavel(link, evento);
    if (!url) return;
    evento.preventDefault();
    navegar(url, "push");
  });

  document.addEventListener("submit", function (evento) {
    var form = evento.target;
    if (!form || !form.matches("form")) return;

    var metodo = (form.method || "get").toLowerCase();
    if (metodo !== "get") {
      limpar();
      return;
    }
    if (evento.defaultPrevented || form.dataset.noSoftNav === "true") return;

    var url = urlSegura(form.action || window.location.href);
    if (!url) return;
    url.search = new URLSearchParams(new FormData(form)).toString();

    evento.preventDefault();
    navegar(url, "push");
  });

  /* ======================================================================
     BUSCAR A TELA ANTES DE ALGUÉM PEDIR

     A troca só é imperceptível quando não há nada a esperar no momento do
     clique. Buscar a tela enquanto o dedo ainda está a caminho é o que
     transforma "clicou e carregou" em "clicou e apareceu".

     A cota era de DUAS buscas por aba, para a sessão inteira. Depois da
     segunda, todo clique voltava a esperar a rede -- e como o painel fica
     aberto o dia todo na bancada, isso significa que a antecipação valia
     nos dois primeiros cliques da manhã e em mais nenhum. Agora a cota se
     renova por minuto: protege de disparar dezenas de pedidos quando
     alguém passa o dedo pelo menu, sem desligar a antecipação para o
     resto do dia.

     Dois momentos disparam, e são diferentes de propósito:

       * PASSAR POR CIMA espera 90ms. O dedo cruzando o menu passa por
         cinco itens; a intenção só existe quando ele para em um.
       * ENCOSTAR (`pointerdown`) dispara na hora. Entre encostar e
         soltar existem uns 100ms de graça no toque, e é neles que a tela
         chega -- é o que faz a navegação parecer instantânea no tablet.
     ====================================================================== */
  var JANELA_DA_COTA = 60000;
  var cotaAberta = 0;

  function podeAntecipar() {
    if (document.querySelector(".modal.show")) return false;
    if (document.visibilityState !== "visible") return false;

    var conexao = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conexao && (conexao.saveData || /(^|-)2g$/.test(conexao.effectiveType || ""))) {
      /* Economia de dados ou 2G: quem está nessa condição paga por
         megabyte ou espera por ele. Buscar o que talvez não seja aberto
         é justamente o que não se deve fazer. */
      return false;
    }

    var agora = Date.now();
    if (agora - cotaAberta > JANELA_DA_COTA) {
      cotaAberta = agora;
      prefetchsExecutados = 0;
    }
    return prefetchsExecutados < LIMITE_PREFETCH;
  }

  function anteciparTela(url) {
    if (!url || recuperar(url) || emVoo.has(url.href)) return;
    prefetchsExecutados += 1;
    /* `true`: de fundo, e portanto mudo. Ver `requisitar`. */
    buscar(url, true).catch(function () {});
  }

  function agendarPrefetch(link, evento, atraso) {
    if (!podeAntecipar()) return;
    var url = linkNavegavel(link, evento);
    if (!url || recuperar(url) || emVoo.has(url.href)) return;

    window.clearTimeout(prefetchTimer);
    if (!atraso) {
      anteciparTela(url);
      return;
    }
    prefetchTimer = window.setTimeout(function () {
      anteciparTela(url);
    }, atraso);
  }

  document.addEventListener("pointerover", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    if (link) agendarPrefetch(link, evento, 90);
  });

  /* Encostar já é intenção: aqui não se espera. */
  document.addEventListener("pointerdown", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    if (link) agendarPrefetch(link, evento, 0);
  }, { passive: true });

  document.addEventListener("focusin", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    if (link) agendarPrefetch(link, evento, 90);
  });

  window.addEventListener("popstate", function () {
    navegar(window.location.href, "none");
  });

  window.LSNavigation = {
    clear: limpar,
    go: function (url) { navegar(url, "push"); },
    /* Atualiza somente o conteúdo. Filtros instantâneos não precisam
       transformar cada escolha em outra URL visível ou outra etapa do
       botão Voltar. */
    silent: function (url) { navegar(url, "none"); }
  };
})(window, document);
