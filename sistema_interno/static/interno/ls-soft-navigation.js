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

  function trocarDocumento(html, url, modoHistorico) {
    try {
      window.sessionStorage.setItem(ENTRADA, "1");
    } catch (erro) {}

    if (modoHistorico === "push") {
      window.history.pushState({ lsSoftNavigation: true }, "", url.href);
    } else if (modoHistorico === "replace") {
      window.history.replaceState({ lsSoftNavigation: true }, "", url.href);
    }

    if (window.Painel && window.Painel.prepararNavegacao) {
      window.Painel.prepararNavegacao();
    }
    document.open();
    document.write(html);
    document.close();
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
