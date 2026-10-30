/* ======================================================================
   QUADRO INICIAL DA HOME — vitrine que gira, painel que se atualiza.

   A vitrine troca de brinquedo sozinha a cada poucos segundos, mas para
   quando alguém está olhando (mouse em cima, foco do teclado, quadro fora
   da tela). Inclina com o mouse e desliza com o dedo no celular.

   NADA AQUI RODA A CADA QUADRO. O relógio da vitrine é a animação CSS da
   barrinha de progresso (o compositor anda com ela sozinho) e a troca de
   brinquedo vem no fim dela. Antes um laço de requestAnimationFrame
   reescrevia a barrinha em todo quadro -- e no celular cada quadro gasto
   ali era um quadro a menos para a rolagem.

   O painel chega pronto no HTML; aqui ele só (1) conta do zero até o
   número quando aparece na tela e (2) pergunta ao servidor a cada minuto
   se algo mudou -- e o número que mudar pisca verde.
   ====================================================================== */
(function () {
  "use strict";

  var quadro = document.querySelector("[data-quadro]");
  if (!quadro) return;

  var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------
     VITRINE
     --------------------------------------------------------------- */
  var vitrine = quadro.querySelector("[data-vitrine]");
  var palco = vitrine && vitrine.querySelector("[data-vitrine-palco]");
  var slides = palco ? Array.prototype.slice.call(palco.querySelectorAll("[data-slide]")) : [];
  var minis = vitrine ? Array.prototype.slice.call(vitrine.querySelectorAll("[data-ir]")) : [];
  var barra = vitrine && vitrine.querySelector("[data-vitrine-progresso]");
  var atual = 0;
  var volta = 0;

  // Reinicia a barrinha trocando o nome da animação (a / b): o navegador
  // recomeça sozinho, sem precisar medir a página para isso.
  function correr() {
    if (!barra || reduzido || slides.length < 2) return;
    volta = 1 - volta;
    barra.classList.toggle("correndo-a", volta === 0);
    barra.classList.toggle("correndo-b", volta === 1);
  }

  function parar(sim) {
    if (vitrine) vitrine.classList.toggle("ls-vitrine--parada", sim);
  }

  function mostrar(indice) {
    if (!slides.length) return;
    indice = (indice + slides.length) % slides.length;
    if (indice === atual) return;
    var anterior = slides[atual];
    anterior.classList.remove("ativo");
    anterior.classList.add("saindo");
    anterior.setAttribute("aria-hidden", "true");
    anterior.querySelectorAll("a").forEach(function (a) { a.tabIndex = -1; });
    window.setTimeout(function () { anterior.classList.remove("saindo"); }, 700);

    atual = indice;
    var novo = slides[atual];
    novo.classList.add("ativo");
    novo.removeAttribute("aria-hidden");
    novo.querySelectorAll("a").forEach(function (a) { a.tabIndex = 0; });
    // A imagem preguiçosa do próximo slide começa a descer antes da vez dele.
    var seguinte = slides[(atual + 1) % slides.length].querySelector("img");
    if (seguinte) seguinte.loading = "eager";

    minis.forEach(function (botao, i) {
      botao.classList.toggle("ativo", i === atual);
      botao.setAttribute("aria-pressed", i === atual ? "true" : "false");
    });
    correr();
  }

  if (slides.length > 1) {
    minis.forEach(function (botao) {
      botao.addEventListener("click", function () { mostrar(Number(botao.dataset.ir)); });
    });

    vitrine.addEventListener("mouseenter", function () { parar(true); });
    vitrine.addEventListener("mouseleave", function () { parar(false); });
    vitrine.addEventListener("focusin", function () { parar(true); });
    vitrine.addEventListener("focusout", function () { parar(false); });

    // Deslizar com o dedo troca de brinquedo.
    var inicioX = null;
    palco.addEventListener("pointerdown", function (e) { inicioX = e.clientX; });
    palco.addEventListener("pointerup", function (e) {
      if (inicioX === null) return;
      var dx = e.clientX - inicioX;
      inicioX = null;
      if (Math.abs(dx) > 40) mostrar(atual + (dx < 0 ? 1 : -1));
    });

    if (barra) barra.addEventListener("animationend", function () { mostrar(atual + 1); });
    correr();
  }

  // Inclinação 3D seguindo o mouse. Só com mouse: no celular o dedo que
  // passa pela vitrine está rolando a página, e cada movimento obrigava o
  // navegador a medir e redesenhar a vitrine no meio da rolagem.
  var temMouse = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (palco && !reduzido && temMouse) {
    palco.addEventListener("pointermove", function (e) {
      var r = palco.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5;
      var y = (e.clientY - r.top) / r.height - 0.5;
      palco.style.setProperty("--inc-y", (x * 14).toFixed(2) + "deg");
      palco.style.setProperty("--inc-x", (-y * 10).toFixed(2) + "deg");
      palco.style.setProperty("--reflexo", (x * 160).toFixed(0) + "%");
    });
    palco.addEventListener("pointerleave", function () {
      palco.style.setProperty("--inc-y", "0deg");
      palco.style.setProperty("--inc-x", "0deg");
      palco.style.setProperty("--reflexo", "-60%");
    });
  }

  /* ---------------------------------------------------------------
     PAINEL AO VIVO
     --------------------------------------------------------------- */
  var visivel = true;
  var numeros = Array.prototype.slice.call(quadro.querySelectorAll("[data-contar]"));
  // Um formatador por número de casas, criado uma vez: toLocaleString com
  // opções monta um formatador novo a cada chamada, e a contagem chama
  // dezenas de vezes por segundo.
  var formatadores = {};
  var formatar = function (valor, casas) {
    var f = formatadores[casas] || (formatadores[casas] = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }));
    return f.format(Number(valor));
  };

  function contar(el, ate) {
    var casas = Number(el.dataset.casas || 0);
    if (reduzido) {
      el.textContent = formatar(ate, casas);
      return;
    }
    var de = Number(el.dataset.mostrado || 0);
    var inicio = null;
    var duracao = 1200;
    var quadroDeConta = function (agora) {
      if (inicio === null) inicio = agora;
      var t = Math.min(1, (agora - inicio) / duracao);
      var suave = 1 - Math.pow(1 - t, 3);
      el.textContent = formatar(de + (ate - de) * suave, casas);
      if (t < 1) window.requestAnimationFrame(quadroDeConta);
    };
    el.dataset.mostrado = String(ate);
    window.requestAnimationFrame(quadroDeConta);
  }

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entradas, observador) {
      entradas.forEach(function (entrada) {
        if (!entrada.isIntersecting) return;
        numeros.forEach(function (el) {
          el.dataset.mostrado = "0";
          contar(el, Number(el.dataset.contar));
        });
        observador.disconnect();
      });
    }, { threshold: 0.2 }).observe(quadro.querySelector(".ls-painel"));

    new IntersectionObserver(function (entradas) {
      visivel = entradas.some(function (e) { return e.isIntersecting; });
      // fora da tela, as animações do quadro param de redesenhar
      quadro.classList.toggle("ls-quadro--fora", !visivel);
    }).observe(quadro);
  }

  var hora = quadro.querySelector("[data-painel-hora]");
  var atualizadoEm = null;

  function relogio() {
    if (!hora || !atualizadoEm) return;
    var segundos = Math.max(0, Math.round((Date.now() - atualizadoEm) / 1000));
    hora.textContent = segundos < 10 ? "atualizado agora" : segundos < 60
      ? "atualizado há " + segundos + " s"
      : "atualizado há " + Math.round(segundos / 60) + " min";
  }

  function aplicar(dados) {
    Object.keys(dados).forEach(function (chave) {
      var item = quadro.querySelector('[data-painel="' + chave + '"]');
      if (!item) return;
      var valor = dados[chave];
      var b = item.querySelector("[data-contar]");
      var esconder = valor === null || valor === undefined || (item.hasAttribute("data-so-positivo") && !(valor > 0));
      item.hidden = esconder;
      if (esconder || !b) return;
      if (Number(b.dataset.contar) !== Number(valor)) {
        b.dataset.contar = String(valor);
        contar(b, Number(valor));
        item.classList.remove("mudou");
        void item.offsetWidth;
        item.classList.add("mudou");
      }
    });
    atualizadoEm = dados.atualizado_em ? Date.parse(dados.atualizado_em) : Date.now();
    relogio();
  }

  var url = quadro.dataset.painelUrl;
  function buscar() {
    if (!url || document.hidden || !visivel) return;
    fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (dados) { if (dados) aplicar(dados); })
      .catch(function () { /* sem rede: o painel fica com os números da página */ });
  }

  buscar();
  window.setInterval(buscar, 60000);
  window.setInterval(relogio, 5000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) buscar(); });

  /* ---------------------------------------------------------------
     LETREIRO — a fila é duplicada para o laço não ter emenda
     --------------------------------------------------------------- */
  var trilho = quadro.querySelector("[data-letreiro]");
  if (trilho && !reduzido && trilho.children.length) {
    Array.prototype.slice.call(trilho.children).forEach(function (item) {
      var copia = item.cloneNode(true);
      copia.setAttribute("aria-hidden", "true");
      copia.tabIndex = -1;
      trilho.appendChild(copia);
    });
    var letreiro = trilho.parentElement;
    letreiro.style.setProperty("--duracao", Math.max(24, trilho.scrollWidth / 60) + "s");
    letreiro.classList.add("rolando");
  }
})();
