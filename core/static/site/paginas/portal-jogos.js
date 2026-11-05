/* ======================================================================
   LAZER & SPORT GAMES -- o portal: busca na hora, filtros, carrossel.

   O índice de busca vem da própria página (json_script "portal-jogos"):
   a cada letra a lista filtra sem ir ao servidor. Sem JavaScript, a busca
   é o formulário de sempre (?q=) e o servidor responde a mesma coisa.
   ====================================================================== */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-portal]");
  var bruto = document.getElementById("portal-jogos");
  if (!raiz || !bruto) return;
  var jogos = [];
  try { jogos = JSON.parse(bruto.textContent || "[]"); } catch (e) { jogos = []; }

  var campo = raiz.querySelector("[data-portal-busca]");
  var formulario = raiz.querySelector("[data-portal-form]");
  var resultados = raiz.querySelector("[data-portal-resultados]");
  var grade = raiz.querySelector("[data-portal-grade]");
  var vazio = raiz.querySelector("[data-portal-vazio]");
  var titulo = raiz.querySelector("[data-portal-resultados-titulo]");
  var vitrine = raiz.querySelector("[data-portal-vitrine]");
  var filtros = Array.prototype.slice.call(raiz.querySelectorAll("[data-filtro]"));
  var filtroAtual = "";

  function semAcento(texto) {
    return (texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function cartao(jogo) {
    var a = document.createElement("a");
    a.className = "pg-cartao";
    a.href = jogo.url;
    a.style.setProperty("--cor", jogo.cor || "#3fd0ff");
    var arte = document.createElement("span");
    arte.className = "pg-cartao-arte";
    if (jogo.capa) {
      var img = document.createElement("img");
      img.src = jogo.capa; img.alt = ""; img.loading = "lazy"; img.decoding = "async";
      arte.appendChild(img);
    } else {
      arte.insertAdjacentHTML("beforeend", '<i class="fa-solid fa-gamepad" aria-hidden="true"></i>');
    }
    var play = document.createElement("span");
    play.className = "pg-cartao-play"; play.setAttribute("aria-hidden", "true");
    play.innerHTML = '<i class="fa-solid fa-play"></i>';
    arte.appendChild(play);
    a.appendChild(arte);
    var selos = document.createElement("span");
    selos.className = "pg-selos";
    if (jogo.tipo === "nosso") selos.insertAdjacentHTML("beforeend", '<span class="pg-selo pg-selo--nosso">Lazer &amp; Sport</span>');
    if (jogo.ranking) selos.insertAdjacentHTML("beforeend", '<span class="pg-selo pg-selo--ranking"><i class="fa-solid fa-trophy" aria-hidden="true"></i> Ranking</span>');
    a.appendChild(selos);
    var texto = document.createElement("span");
    texto.className = "pg-cartao-texto";
    var nome = document.createElement("strong");
    nome.textContent = jogo.titulo;
    var sub = document.createElement("small");
    sub.textContent = jogo.plataforma + (jogo.categoria ? " · " + jogo.categoria : "");
    texto.appendChild(nome); texto.appendChild(sub);
    a.appendChild(texto);
    return a;
  }

  function passa(jogo, termo) {
    if (filtroAtual) {
      var partes = filtroAtual.split(":");
      if (partes[0] === "familia" && (jogo.familias || []).indexOf(partes[1]) < 0) return false;
      if (partes[0] === "categoria" && jogo.categoria !== partes[1]) return false;
    }
    if (!termo) return true;
    return termo.split(/\s+/).every(function (p) { return jogo.busca.indexOf(p) >= 0; });
  }

  function atualizar() {
    var termo = semAcento(campo ? campo.value.trim() : "");
    var ativo = !!(termo || filtroAtual);
    resultados.hidden = !ativo;
    vitrine.hidden = ativo;
    if (!ativo) return;
    var lista = jogos.filter(function (j) { return passa(j, termo); });
    grade.replaceChildren.apply(grade, lista.map(cartao));
    vazio.hidden = lista.length > 0;
    var rotulo = filtros.filter(function (f) { return f.dataset.filtro === filtroAtual; })[0];
    titulo.textContent = termo ? "Resultados para “" + campo.value.trim() + "”" : (rotulo ? rotulo.textContent : "Jogos");
    try {
      var url = new URL(location.href);
      if (campo.value.trim()) url.searchParams.set("q", campo.value.trim()); else url.searchParams.delete("q");
      history.replaceState(null, "", url);
    } catch (e) { /* nada */ }
  }

  var espera = 0;
  if (campo) {
    campo.addEventListener("input", function () { clearTimeout(espera); espera = setTimeout(atualizar, 120); });
  }
  if (formulario) {
    formulario.addEventListener("submit", function (e) { e.preventDefault(); atualizar(); });
  }
  filtros.forEach(function (botao) {
    botao.addEventListener("click", function () {
      filtroAtual = botao.dataset.filtro;
      filtros.forEach(function (f) { f.setAttribute("aria-pressed", f === botao ? "true" : "false"); });
      atualizar();
    });
  });
  var limpar = raiz.querySelector("[data-portal-limpar]");
  if (limpar) {
    limpar.addEventListener("click", function () {
      if (campo) campo.value = "";
      filtroAtual = "";
      filtros.forEach(function (f, i) { f.setAttribute("aria-pressed", i === 0 ? "true" : "false"); });
      atualizar();
    });
  }

  /* ---------- as faixas: setas que rolam de lado ---------- */
  raiz.querySelectorAll("[data-portal-rolar]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var trilho = botao.closest(".pg-faixa").querySelector("[data-portal-trilho]");
      trilho.scrollBy({ left: Number(botao.dataset.portalRolar) * trilho.clientWidth * 0.85, behavior: "smooth" });
    });
  });

  /* ---------- o carrossel de destaques ---------- */
  var hero = raiz.querySelector("[data-portal-hero]");
  if (hero) {
    var slides = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-slide]"));
    var pontos = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-pontos] button"));
    var atual = 0;
    var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var relogio = 0;
    function mostrar(i) {
      atual = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) {
        s.classList.toggle("pg-slide--ativo", k === atual);
        if (k === atual) s.removeAttribute("aria-hidden"); else s.setAttribute("aria-hidden", "true");
      });
      pontos.forEach(function (p, k) { if (k === atual) p.setAttribute("aria-current", "true"); else p.removeAttribute("aria-current"); });
    }
    function girar() {
      clearInterval(relogio);
      if (!reduzido && slides.length > 1) relogio = setInterval(function () { mostrar(atual + 1); }, 6500);
    }
    var antes = hero.querySelector("[data-portal-antes]");
    var depois = hero.querySelector("[data-portal-depois]");
    if (antes) antes.addEventListener("click", function () { mostrar(atual - 1); girar(); });
    if (depois) depois.addEventListener("click", function () { mostrar(atual + 1); girar(); });
    pontos.forEach(function (p, k) { p.addEventListener("click", function () { mostrar(k); girar(); }); });
    hero.addEventListener("mouseenter", function () { clearInterval(relogio); });
    hero.addEventListener("mouseleave", girar);
    // arrastar o dedo de lado troca o destaque
    var inicioX = null;
    hero.addEventListener("touchstart", function (e) { inicioX = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener("touchend", function (e) {
      if (inicioX === null) return;
      var dx = e.changedTouches[0].clientX - inicioX;
      inicioX = null;
      if (Math.abs(dx) > 40) { mostrar(atual + (dx < 0 ? 1 : -1)); girar(); }
    });
    document.addEventListener("visibilitychange", function () { if (document.hidden) clearInterval(relogio); else girar(); });
    girar();
  }
})();
