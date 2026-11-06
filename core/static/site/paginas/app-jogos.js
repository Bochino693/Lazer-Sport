/* ======================================================================
   O APP LAZER & SPORT GAMES (o launcher, /jogos/)

   A biblioteca de jogos é um app dentro do site:
   - abre com o carregamento da marca (uma vez por visita; sempre no app
     instalado), sem o cabeçalho e o rodapé do site (body.ls-modo-app);
   - O JOGO ABRE DENTRO DO APP, por cima da biblioteca, no mesmo documento:
     a tela cheia continua ligada ao tocar em Jogar (antes a página trocava e
     o navegador saía da tela cheia), e "Voltar" -- ou o botão voltar do
     celular -- traz de volta à biblioteca, ainda em tela cheia;
   - funciona sem internet: o service worker (/jogos/sw.js) guarda a
     biblioteca, as capas, o emulador e as páginas dos jogos já abertos (os
     arquivos do jogo ficam com o jogo-guardado.js), e o app pode ser
     instalado na tela de início.

     LSApp.abrir(jogo, evento) -> true quando o app cuidou (o link não segue)
     LSApp.fechar(), LSApp.telaCheia(), LSApp.emTelaCheia()
   ====================================================================== */
(function () {
  "use strict";
  var corpo = document.body;
  var raiz = document.documentElement;
  var $ = function (s) { return document.querySelector(s); };
  function consulta(q) { try { return window.matchMedia(q).matches; } catch (e) { return false; } }
  var celular = consulta("(pointer: coarse)");
  var instalado = consulta("(display-mode: standalone)") || consulta("(display-mode: fullscreen)") || navigator.standalone === true;

  /* ---------------------------------------------------------------- o carregamento */
  var abertura = $("[data-app-abertura]");
  if (abertura) {
    var barra = abertura.querySelector("[data-app-abertura-barra]");
    var texto = abertura.querySelector("[data-app-abertura-texto]");
    var inicio = performance.now();
    var MINIMO = 1100, MAXIMO = 2800;
    var imagens = Array.prototype.slice.call(document.querySelectorAll(".pg-vitrine img, .bj-grade img")).slice(0, 18);
    var progresso = function () {
      var prontas = imagens.filter(function (i) { return i.complete; }).length;
      var tempo = Math.min(1, (performance.now() - inicio) / MAXIMO);
      var parte = imagens.length ? prontas / imagens.length : 1;
      if (barra) barra.style.width = Math.round(Math.max(tempo, parte * 0.9) * 100) + "%";
      return parte;
    };
    var sair = function () {
      if (!abertura || abertura.classList.contains("is-saindo")) return;
      if (barra) barra.style.width = "100%";
      if (texto) texto.textContent = "Pronto!";
      abertura.classList.add("is-saindo");
      try { sessionStorage.setItem("ls-app-aberto", "1"); } catch (e) { /* aba anônima */ }
      setTimeout(function () { if (abertura) abertura.remove(); abertura = null; }, 520);
    };
    var olhar = function () {
      if (!abertura) return;
      var parte = progresso();
      var tempo = performance.now() - inicio;
      if ((parte >= 1 && tempo >= MINIMO) || tempo >= MAXIMO) sair();
      else requestAnimationFrame(olhar);
    };
    abertura.addEventListener("click", sair);
    requestAnimationFrame(olhar);
  }

  /* ---------------------------------------------------------------- tela cheia */
  function emTelaCheia() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
  var podeTelaCheia = !!(raiz.requestFullscreen || raiz.webkitRequestFullscreen);
  function pedirTelaCheia() {
    if (!podeTelaCheia || emTelaCheia()) return Promise.resolve();
    try {
      var pedido = raiz.requestFullscreen ? raiz.requestFullscreen({ navigationUI: "hide" }) : raiz.webkitRequestFullscreen();
      return Promise.resolve(pedido).catch(function () {});
    } catch (e) { return Promise.resolve(); }
  }
  function sairTelaCheia() {
    try {
      if (document.exitFullscreen) return document.exitFullscreen();
      if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
    } catch (e) { /* nada */ }
  }
  function deitar(emPe) {
    if (!celular || !screen.orientation || !screen.orientation.lock) return;
    screen.orientation.lock(emPe ? "portrait" : "landscape").catch(function () { /* o aparelho não deixa */ });
  }
  function soltarGiro() {
    try { if (screen.orientation && screen.orientation.unlock) screen.orientation.unlock(); } catch (e) { /* nada */ }
  }
  var botaoCheia = $("[data-app-tela-cheia]");
  function desenharBotaoCheia() {
    corpo.classList.toggle("app-tela-cheia", emTelaCheia());
    if (!botaoCheia) return;
    var nome = emTelaCheia() ? "Sair da tela cheia" : "Tela cheia";
    botaoCheia.querySelector("span").textContent = nome;
    botaoCheia.title = nome;
    botaoCheia.setAttribute("aria-label", nome);
    var i = botaoCheia.querySelector("i");
    if (i) i.className = emTelaCheia() ? "fa-solid fa-compress" : "fa-solid fa-expand";
  }
  if (botaoCheia) {
    if (!podeTelaCheia) botaoCheia.hidden = true;
    botaoCheia.addEventListener("click", function () { if (emTelaCheia()) sairTelaCheia(); else pedirTelaCheia(); });
  }
  document.addEventListener("fullscreenchange", desenharBotaoCheia);
  document.addEventListener("webkitfullscreenchange", desenharBotaoCheia);

  /* ---------------------------------------------------------------- o jogo dentro do app */
  var palco = $("[data-app-palco]");
  var botaoFechar = palco && palco.querySelector("[data-app-fechar]");
  var quadro = null;
  var aberto = null;
  // PSP e DOS precisam da página isolada (o núcleo de várias linhas): esses abrem na página deles
  var SO_NA_PAGINA = ["psp", "dos"];
  var URL_ABRIU = (palco && palco.dataset.appAbriu) || "";

  function csrf() {
    var achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return achado ? decodeURIComponent(achado[1]) : "";
  }
  /* A partida grátis de quem não tem conta (a mesma conta da página do jogo, /jogos/abriu/).
     Sem resposta rápida (rede ruim, sem internet), o jogo abre do mesmo jeito. */
  function perguntar(slug) {
    var livre = { liberado: true };
    if (!URL_ABRIU || !window.fetch || !navigator.onLine) return Promise.resolve(livre);
    var pedido = fetch(URL_ABRIU, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ jogo: slug }),
    }).then(function (r) { return r.ok ? r.json() : livre; }).catch(function () { return livre; });
    return Promise.race([pedido, new Promise(function (ok) { setTimeout(function () { ok(livre); }, 2500); })]);
  }
  function lembrar(slug) {
    try {
      var lista = JSON.parse(localStorage.getItem("ls-biblioteca-recentes") || "{}") || {};
      lista[slug] = Date.now();
      localStorage.setItem("ls-biblioteca-recentes", JSON.stringify(lista));
    } catch (e) { /* sem armazenamento */ }
  }

  function abrir(jogo, evento) {
    if (!palco || !jogo || !jogo.url) return false;
    var deConsole = !!jogo.sistema && jogo.tipo !== "nosso";
    if (deConsole && SO_NA_PAGINA.indexOf(jogo.sistema) !== -1) return false;
    if (evento && (evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button === 1)) return false; // nova aba: deixa
    // o toque em Jogar: no celular a tela cheia deitada já vem junto (o jogo abre lá dentro)
    if (celular) pedirTelaCheia().then(function () { deitar(jogo.sistema === "nds"); });
    var endereco = deConsole ? jogo.url.replace(/\/?$/, "/") + "emulador/?app=1" : jogo.url + (jogo.url.indexOf("?") === -1 ? "?" : "&") + "app=1";
    var seguir = function (resposta) {
      if (resposta && resposta.liberado === false) { location.href = jogo.url; return; } // o convite de cadastro
      lembrar(jogo.slug);
      mostrarJogo(jogo, endereco, deConsole);
    };
    if (deConsole) perguntar(jogo.slug).then(seguir); else seguir(null);
    return true;
  }

  function mostrarJogo(jogo, endereco, deConsole) {
    fecharQuadro();
    aberto = jogo;
    quadro = document.createElement("iframe");
    quadro.className = "app-jogo-quadro";
    quadro.title = jogo.titulo || "Jogo";
    quadro.src = endereco;
    quadro.setAttribute("allow", "fullscreen; gamepad; autoplay; screen-wake-lock; clipboard-write");
    quadro.setAttribute("allowfullscreen", "");
    palco.style.setProperty("--cor", jogo.cor || "#ff3df2");
    palco.insertBefore(quadro, palco.firstChild);
    // o reprodutor de console tem o Voltar dele; os outros jogos, o do app
    if (botaoFechar) botaoFechar.hidden = deConsole;
    palco.hidden = false;
    corpo.classList.add("app-jogando");
    try { history.pushState({ lsJogo: jogo.slug }, "", location.pathname + location.search + "#jogando"); } catch (e) { /* nada */ }
    quadro.addEventListener("load", function () { try { quadro.focus(); } catch (e) { /* nada */ } });
  }
  function fecharQuadro() {
    if (!quadro) return;
    var q = quadro;
    quadro = null;
    var tirar = function () { if (!q) return; q.src = "about:blank"; q.remove(); q = null; };
    // antes de fechar, o jogo guarda o ponto onde parou ("Continuar de onde parou")
    var salvar = null;
    try { salvar = q.contentWindow && q.contentWindow.LSJogoSalvar; } catch (e) { salvar = null; }
    if (typeof salvar !== "function") { tirar(); return; }
    setTimeout(tirar, 1500);
    try { Promise.resolve(salvar()).then(tirar, tirar); } catch (e) { tirar(); }
  }
  function fechar(daHistoria) {
    if (!aberto) return;
    aberto = null;
    fecharQuadro();
    palco.hidden = true;
    corpo.classList.remove("app-jogando");
    soltarGiro();
    if (!daHistoria && history.state && history.state.lsJogo) {
      try { history.back(); } catch (e) { /* nada */ }
    }
    var volta = document.querySelector("[data-bj-ficha]:not([hidden]) [data-bj-ficha-jogar]") || document.querySelector(".pg-marca");
    if (volta && volta.focus) volta.focus({ preventScroll: true });
  }
  // o botão voltar do celular (e do navegador) fecha o jogo, não sai do app
  window.addEventListener("popstate", function () { if (aberto) fechar(true); });
  if (botaoFechar) botaoFechar.addEventListener("click", function () { fechar(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && aberto && botaoFechar && !botaoFechar.hidden) fechar(false); });

  /* ---------------------------------------------------------------- instalar o app */
  var botaoInstalar = $("[data-app-instalar]");
  var pedidoDeInstalar = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    pedidoDeInstalar = e;
    if (botaoInstalar) botaoInstalar.hidden = false;
  });
  var iphone = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  if (botaoInstalar && iphone && !instalado) botaoInstalar.hidden = false;
  if (botaoInstalar) {
    botaoInstalar.addEventListener("click", function () {
      if (pedidoDeInstalar) {
        pedidoDeInstalar.prompt();
        pedidoDeInstalar.userChoice.then(function () { pedidoDeInstalar = null; botaoInstalar.hidden = true; });
      } else if (iphone) {
        avisar("No iPhone: toque em Compartilhar e em “Adicionar à Tela de Início”. O app abre em tela cheia, sem as barras.");
      }
    });
  }
  window.addEventListener("appinstalled", function () { if (botaoInstalar) botaoInstalar.hidden = true; });

  /* ---------------------------------------------------------------- sem internet */
  var avisoRede = $("[data-app-sem-rede]");
  function olharRede() { if (avisoRede) avisoRede.hidden = navigator.onLine !== false; }
  window.addEventListener("online", olharRede);
  window.addEventListener("offline", olharRede);
  olharRede();
  if ("serviceWorker" in navigator && palco && palco.dataset.appSw) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register(palco.dataset.appSw, { scope: "/jogos/" }).then(function () {
        return navigator.serviceWorker.ready;
      }).then(function (registro) {
        // o que esta página já baixou (o CSS e o JS do site, as capas) vai para o cofre do app
        var urls = performance.getEntriesByType("resource").map(function (e) { return e.name; })
          .concat(Array.prototype.map.call(document.images, function (i) { return i.currentSrc || i.src; }));
        if (registro.active) registro.active.postMessage({ tipo: "guardar", urls: urls });
      }).catch(function () { /* sem app offline: segue online */ });
    });
  }

  /* ---------------------------------------------------------------- a barra do app */
  // presa no alto (computador e tablet), ganha o vidro escuro ao rolar; a aba da seção
  // à vista fica acesa; "/" leva à busca; no celular, a aba Buscar abre a busca.
  var barraDoApp = $("[data-pg-barra]");
  var abas = Array.prototype.slice.call(document.querySelectorAll("[data-pg-aba]"));
  var secoes = { biblioteca: document.getElementById("biblioteca"), ranking: document.getElementById("ranking") };
  var campoBusca = $("[data-portal-busca]");
  var marcando = false;
  function presa() { return barraDoApp && getComputedStyle(barraDoApp).position === "sticky"; }
  function marcarBarra() {
    marcando = false;
    if (!barraDoApp) return;
    var altura = presa() ? barraDoApp.offsetHeight : 0;
    document.documentElement.style.setProperty("--pg-barra-altura", altura + "px");
    barraDoApp.classList.toggle("is-rolada", window.scrollY > 8);
    var linha = Math.max(altura + 40, window.innerHeight * 0.35);
    var atual = "inicio";
    if (secoes.biblioteca && secoes.biblioteca.getBoundingClientRect().top <= linha) atual = "biblioteca";
    if (secoes.ranking && secoes.ranking.getBoundingClientRect().top <= linha) atual = "ranking";
    // no fim da página, o ranking (a última seção) mesmo que não chegue à linha
    if (secoes.ranking && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) atual = "ranking";
    abas.forEach(function (a) {
      if (a.dataset.pgAba === atual) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
    });
  }
  function pedirMarca() { if (!marcando) { marcando = true; requestAnimationFrame(marcarBarra); } }
  window.addEventListener("scroll", pedirMarca, { passive: true });
  window.addEventListener("resize", pedirMarca);
  marcarBarra();
  abas.forEach(function (a) {
    a.addEventListener("click", function (e) {
      var alvo = a.dataset.pgAba === "inicio" ? null : secoes[a.dataset.pgAba];
      if (a.dataset.pgAba !== "inicio" && !alvo) return;
      e.preventDefault();
      var suave = !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
      if (alvo) alvo.scrollIntoView({ behavior: suave ? "smooth" : "auto", block: "start" });
      else window.scrollTo({ top: 0, behavior: suave ? "smooth" : "auto" });
      if (history.replaceState) history.replaceState(history.state, "", location.pathname + location.search + (alvo ? "#" + alvo.id : ""));
    });
  });
  function irParaBusca() {
    if (!campoBusca) return;
    window.scrollTo({ top: 0, behavior: "auto" });
    campoBusca.focus({ preventScroll: true });
    try { campoBusca.select(); } catch (e) { /* nada */ }
  }
  var abaBuscar = $("[data-pg-aba-buscar]");
  if (abaBuscar) abaBuscar.addEventListener("click", function (e) { e.preventDefault(); irParaBusca(); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey || aberto) return;
    var ali = document.activeElement;
    if (ali && (ali.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ali.tagName))) return;
    if (document.querySelector("[data-bj-ficha]:not([hidden])")) return;
    e.preventDefault();
    irParaBusca();
  });

  var tempoAviso = null;
  function avisar(mensagem) {
    var caixa = $("[data-app-aviso]");
    if (!caixa) return;
    caixa.textContent = mensagem;
    caixa.hidden = false;
    clearTimeout(tempoAviso);
    tempoAviso = setTimeout(function () { caixa.hidden = true; }, 6000);
  }

  window.LSApp = {
    abrir: abrir,
    fechar: function () { fechar(false); },
    telaCheia: function (emPe) {
      if (emTelaCheia()) { sairTelaCheia(); return Promise.resolve(false); }
      return pedirTelaCheia().then(function () { deitar(emPe); return true; });
    },
    pedirTelaCheia: function (emPe) { return pedirTelaCheia().then(function () { deitar(emPe); }); },
    emTelaCheia: emTelaCheia,
    podeTelaCheia: podeTelaCheia,
    documento: document,
  };
})();
