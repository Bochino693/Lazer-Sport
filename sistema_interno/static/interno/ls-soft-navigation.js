/* Navegação suave e cache curto do painel interno.
 *
 * O HTML recente fica somente no sessionStorage: acelera voltar entre telas
 * no mesmo turno sem deixar dados de um usuário disponíveis após fechar a aba.
 */
(function (window, document) {
  "use strict";

  var PREFIXO = "ls:nav:v2:";
  var INDICE = PREFIXO + "index";
  var ENTRADA = PREFIXO + "entrada";
  var LIMITE = 7;
  var TTL_TELA = 90000;
  var TTL_FILTRO = 30000;
  var emVoo = new Map();
  var navegacao = 0;
  var prefetchTimer = null;
  var prefetchsExecutados = 0;
  var LIMITE_PREFETCH = 2;
  var TIMEOUT_REDE = 12000;

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
    return status === 408 || status === 429 || status === 502 || status === 503 || status === 504;
  }

  function requisitar(url, tentativa) {
    var controlador = "AbortController" in window ? new AbortController() : null;
    var timer = controlador ? window.setTimeout(function () { controlador.abort(); }, TIMEOUT_REDE) : null;

    return window.fetch(url.href, {
      method: "GET",
      credentials: "same-origin",
      headers: { "X-Requested-With": "LS-Soft-Navigation" },
      cache: "default",
      signal: controlador ? controlador.signal : undefined
    }).then(function (resposta) {
      if (tentativa === 0 && podeTentarNovamente(resposta.status)) {
        return esperar(420).then(function () { return requisitar(url, 1); });
      }

      var tipo = resposta.headers.get("content-type") || "";
      if (!resposta.ok || tipo.indexOf("text/html") === -1) {
        var erro = new Error("Resposta incompatível com navegação suave.");
        erro.status = resposta.status;
        throw erro;
      }

      var finalUrl = urlSegura(resposta.url);
      if (!finalUrl) throw new Error("A navegação saiu do painel.");

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
        tentativa === 0
        && !erro.lsTentativaFinal
        && (!erro.status || podeTentarNovamente(erro.status))
      ) {
        return esperar(420).then(function () { return requisitar(url, 1); });
      }
      if (tentativa > 0) erro.lsTentativaFinal = true;
      throw erro;
    }).finally(function () {
      if (timer) window.clearTimeout(timer);
    });
  }

  function buscar(url) {
    var id = url.href;
    if (emVoo.has(id)) return emVoo.get(id);

    var pedido = requisitar(url, 0).finally(function () {
      emVoo.delete(id);
    });

    emVoo.set(id, pedido);
    return pedido;
  }

  function mostrarLoader(mensagem) {
    if (window.LSLoader && window.LSLoader.show) {
      window.LSLoader.show(mensagem || "Carregando…");
    }
  }

  function esconderLoader() {
    if (window.LSLoader && window.LSLoader.hide) window.LSLoader.hide();
  }

  function mostrarFalha(url) {
    esconderLoader();
    var anterior = document.getElementById("lsNavRecovery");
    if (anterior) anterior.remove();

    var painel = document.createElement("div");
    painel.id = "lsNavRecovery";
    painel.className = "ls-nav-recovery";
    painel.setAttribute("role", "alert");
    painel.innerHTML = (
      '<div><strong>A conexão oscilou</strong>' +
      '<span>A tela atual foi preservada e nada foi reenviado.</span></div>' +
      '<button type="button" data-retry> tentar novamente</button>' +
      '<button type="button" data-close aria-label="Fechar aviso">×</button>'
    );
    painel.querySelector("[data-retry]").addEventListener("click", function () {
      painel.remove();
      navegar(url, "push");
    });
    painel.querySelector("[data-close]").addEventListener("click", function () { painel.remove(); });
    document.body.appendChild(painel);
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

    /* A comparação é entre endereços JÁ RESOLVIDOS, e isso importa: no
       HTML o atributo é relativo ("/static/..."), enquanto a propriedade
       `.href` devolve o endereço absoluto. Procurar pelo atributo com o
       valor absoluto nunca casa -- e a cada troca de tela o painel
       reanexava as MESMAS quatro folhas, dobrando a lista do `<head>`. */
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

  function aplicarTela(novoDoc, url, modoHistorico) {
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

  function trocarDocumento(html, url, modoHistorico) {
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

    try {
      window.sessionStorage.setItem(ENTRADA, "1");
    } catch (erro) {}

    /* O CSS ANTES DO HTML. Enquanto a folha da tela nova não chegou, o
       que está na tela é a tela ANTERIOR, inteira e estilizada -- e não
       um esqueleto sem estilo. */
    garantirFolhas(novoDoc).then(function () {
      if (!aplicarTela(novoDoc, url, modoHistorico)) {
        window.location.assign(url.href);
      }
    }).catch(function () {
      window.location.assign(url.href);
    });
  }

  function navegar(url, modoHistorico) {
    var alvo = urlSegura(url);
    if (!alvo) {
      window.location.assign(String(url));
      return;
    }

    var minhaNavegacao = ++navegacao;
    mostrarLoader("Carregando " + (alvo.pathname === window.location.pathname ? "resultados…" : "a tela…"));

    var cache = recuperar(alvo);
    if (cache) {
      trocarDocumento(cache, alvo, modoHistorico || "push");
      return;
    }

    buscar(alvo).then(function (resultado) {
      if (minhaNavegacao !== navegacao) return;
      trocarDocumento(resultado.html, resultado.url, modoHistorico || "push");
    }).catch(function () {
      if (minhaNavegacao !== navegacao) return;
      mostrarFalha(alvo);
    });
  }

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

  function agendarPrefetch(link, evento) {
    if (document.querySelector(".modal.show")) return;
    if (document.visibilityState !== "visible" || prefetchsExecutados >= LIMITE_PREFETCH) return;
    var conexao = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conexao && (conexao.saveData || /(^|-)2g$/.test(conexao.effectiveType || ""))) return;
    var url = linkNavegavel(link, evento);
    if (!url || recuperar(url) || emVoo.has(url.href)) return;
    window.clearTimeout(prefetchTimer);
    prefetchTimer = window.setTimeout(function () {
      prefetchsExecutados += 1;
      buscar(url).catch(function () {});
    }, 360);
  }

  document.addEventListener("pointerover", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    if (link) agendarPrefetch(link, evento);
  });

  document.addEventListener("focusin", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    if (link) agendarPrefetch(link, evento);
  });

  window.addEventListener("popstate", function () {
    navegar(window.location.href, "none");
  });

  try {
    if (window.sessionStorage.getItem(ENTRADA) === "1") {
      window.sessionStorage.removeItem(ENTRADA);
      document.documentElement.classList.add("ls-soft-enter");
      window.setTimeout(function () {
        document.documentElement.classList.remove("ls-soft-enter");
      }, 320);
    }
  } catch (erro) {}

  window.LSNavigation = {
    clear: limpar,
    go: function (url) { navegar(url, "push"); }
  };
})(window, document);
