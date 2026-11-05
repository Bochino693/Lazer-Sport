/* ======================================================================
   LAZER & SPORT GAMES -- a biblioteca (/jogos/).

   O índice de todos os jogos vem da própria página (json_script
   "portal-jogos") e o desenho das estantes também ("portal-biblioteca"):
   trocar de estante, de gênero, de ordem ou buscar não vai ao servidor.
   O endereço acompanha (?estante=, ?genero=, ?ordem=, ?q=) e é o mesmo que
   o servidor responde sem JavaScript.

   O QUE É DO APARELHO. "Jogados recentemente" e "Já no aparelho" vêm do
   navegador de quem joga: a página de cada jogo anota quando ele foi
   aberto (ls-biblioteca-recentes) e o jogo guardado no aparelho mantém o
   índice dele (ls-jogos-guardados, jogo-guardado.js). Nada disso vai para
   o servidor.
   ====================================================================== */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-portal]");
  var bruto = document.getElementById("portal-jogos");
  var brutoBib = document.getElementById("portal-biblioteca");
  if (!raiz || !bruto) return;

  function lerJson(no, padrao) { try { return JSON.parse(no.textContent || "") || padrao; } catch (e) { return padrao; } }
  var jogos = lerJson(bruto, []);
  var bib = brutoBib ? lerJson(brutoBib, {}) : {};
  var ESTANTES = bib.estantes || [];
  var COLECOES = bib.colecoes || [];
  var POR_ESTANTE = bib.porEstante || 12;
  var CONTROLES = bib.controles || {};
  var DICAS = bib.dicas || {};
  var temaDe = {};
  ESTANTES.forEach(function (e) { temaDe[e.chave] = e; });
  var porSlug = {};
  jogos.forEach(function (j) { porSlug[j.slug] = j; });

  function semAcento(texto) {
    return (texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function lerLocal(chave) { try { return JSON.parse(localStorage.getItem(chave) || "{}") || {}; } catch (e) { return {}; } }
  function gravarLocal(chave, valor) { try { localStorage.setItem(chave, valor); } catch (e) { /* aba anônima */ } }

  /* ---------- o que é deste aparelho ---------- */
  var guardados = lerLocal("ls-jogos-guardados");
  var abertos = lerLocal("ls-biblioteca-recentes");
  var recentes = {};
  Object.keys(abertos).forEach(function (s) { recentes[s] = Number(abertos[s]) || 0; });
  Object.keys(guardados).forEach(function (s) { recentes[s] = Math.max(recentes[s] || 0, Number((guardados[s] || {}).usado) || 0); });
  var noAparelho = Object.keys(guardados).filter(function (s) { return porSlug[s] && ((guardados[s] || {}).bytes || 0) > 0; });
  var listaRecentes = Object.keys(recentes).filter(function (s) { return porSlug[s] && recentes[s] > 0; })
    .sort(function (a, b) { return recentes[b] - recentes[a]; });

  /* ---------- os elementos ---------- */
  var bibEl = raiz.querySelector("[data-bj]");
  var conteudo = raiz.querySelector("[data-bj-conteudo]");
  var titulo = raiz.querySelector("[data-bj-lista-titulo]");
  var sub = raiz.querySelector("[data-bj-lista-sub]");
  var barraTitulo = raiz.querySelector("[data-bj-barra-titulo]");
  var ordemEl = raiz.querySelector("[data-bj-ordem]");
  var limpar = raiz.querySelector("[data-bj-limpar]");
  var campo = raiz.querySelector("[data-portal-busca]");
  var formulario = raiz.querySelector("[data-portal-form]");
  var hero = raiz.querySelector("[data-portal-hero]");
  var barra = raiz.querySelector("[data-bj-barra]");
  if (!bibEl || !conteudo) return;

  function lerVista() { try { return localStorage.getItem("ls-biblioteca-vista") === "lista" ? "lista" : "capas"; } catch (e) { return "capas"; } }
  var params = new URLSearchParams(location.search);
  var estado = {
    filtro: params.get("estante") || "",
    genero: params.get("genero") || "",
    termo: params.get("q") || "",
    ordem: params.get("ordem") || "destaque",
    vista: lerVista(),
  };

  /* ---------- a capa (a mesma de partials/cartao_jogo.html) ---------- */
  function el(tag, classe, texto) {
    var n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texto !== undefined) n.textContent = texto;
    return n;
  }
  function icone(nome) {
    var i = el("i", (nome === "fa-html5" ? "fa-brands " : "fa-solid ") + nome);
    i.setAttribute("aria-hidden", "true");
    return i;
  }
  function capa(jogo) {
    var a = el("a", "bj-capa");
    a.href = jogo.url;
    a.dataset.bjJogo = jogo.slug;
    a.style.setProperty("--cor", jogo.cor || "#3fd0ff");
    a.style.setProperty("--tema", jogo.tema || "#3fd0ff");
    var arte = el("span", "bj-capa-arte");
    if (jogo.capa) {
      var fundo = el("img", "bj-capa-fundo");
      fundo.src = jogo.capa; fundo.alt = ""; fundo.loading = "lazy"; fundo.decoding = "async"; fundo.setAttribute("aria-hidden", "true");
      var img = el("img", "bj-capa-img");
      img.src = jogo.capa; img.alt = ""; img.loading = "lazy"; img.decoding = "async";
      arte.appendChild(fundo);
      arte.appendChild(img);
    } else {
      var sem = icone("fa-gamepad");
      sem.classList.add("bj-capa-sem");
      arte.appendChild(sem);
    }
    arte.appendChild(el("span", "bj-sigla", jogo.sigla || ""));
    var marcas = el("span", "bj-marcas");
    if (jogo.ranking) { var r = el("span", "bj-marca bj-marca--ranking"); r.title = "Com ranking"; r.appendChild(icone("fa-trophy")); marcas.appendChild(r); }
    if (jogo.novidade) marcas.appendChild(el("span", "bj-marca bj-marca--nova", "Novo"));
    if (noAparelho.indexOf(jogo.slug) >= 0) {
      var g = el("span", "bj-marca bj-marca--aparelho");
      g.title = "Já no aparelho: abre na hora";
      g.appendChild(icone("fa-download"));
      marcas.appendChild(g);
    }
    arte.appendChild(marcas);
    var play = el("span", "bj-capa-play");
    play.setAttribute("aria-hidden", "true");
    play.appendChild(icone("fa-play"));
    arte.appendChild(play);
    var texto = el("span", "bj-capa-texto");
    texto.appendChild(el("strong", "", jogo.titulo));
    var partes = [jogo.tipo === "nosso" ? "Lazer & Sport" : jogo.plataforma];
    if (jogo.categoria) partes.push(jogo.categoria);
    if (jogo.partidas) partes.push(jogo.partidas + " partida" + (jogo.partidas === 1 ? "" : "s"));
    texto.appendChild(el("small", "", partes.join(" · ")));
    arte.appendChild(texto);
    a.appendChild(arte);
    return a;
  }
  function grade(lista) {
    var g = el("div", "bj-grade");
    lista.forEach(function (j) { g.appendChild(capa(j)); });
    return g;
  }
  function faixa(tema, total, mais, filtroDoVerTodos) {
    var s = el("section", "bj-estante");
    s.dataset.estante = tema.chave;
    s.style.setProperty("--tema", tema.cor);
    var f = el("div", "bj-estante-faixa");
    var ic = el("span", "bj-estante-icone");
    ic.appendChild(icone(tema.icone));
    f.appendChild(ic);
    var nome = el("div", "bj-estante-nome");
    nome.appendChild(el("h3", "", tema.nome));
    nome.appendChild(el("p", "", tema.sub));
    f.appendChild(nome);
    f.appendChild(el("span", "bj-estante-total", total + " jogo" + (total === 1 ? "" : "s")));
    if (mais) {
      var link = el("a", "bj-estante-todos", "Ver todos ");
      link.href = "?estante=" + (filtroDoVerTodos || tema.chave) + "#biblioteca";
      link.dataset.bjFiltro = filtroDoVerTodos || tema.chave;
      link.appendChild(icone("fa-chevron-right"));
      f.appendChild(link);
    }
    s.appendChild(f);
    return s;
  }

  /* ---------- filtrar e ordenar (o mesmo que core/portal_jogos.py faz) ---------- */
  function ordenar(lista, ordem) {
    var copia = lista.slice();
    var porNome = function (a, b) { return semAcento(a.titulo).localeCompare(semAcento(b.titulo)); };
    if (ordem === "az") return copia.sort(porNome);
    if (ordem === "jogados") return copia.sort(function (a, b) { return (b.partidas - a.partidas) || porNome(a, b); });
    if (ordem === "novos") return copia.sort(function (a, b) { return (b.criado || "").localeCompare(a.criado || ""); });
    if (ordem === "recentes") return copia.sort(function (a, b) { return (recentes[b.slug] || 0) - (recentes[a.slug] || 0); });
    return copia.sort(function (a, b) {
      return ((a.tipo !== "nosso") - (b.tipo !== "nosso")) || ((!a.destaque) - (!b.destaque)) || (b.partidas - a.partidas) || (a.ordem - b.ordem);
    });
  }
  function daColecao(chave) {
    if (chave === "recentes") return listaRecentes.map(function (s) { return porSlug[s]; });
    if (chave === "aparelho") return noAparelho.map(function (s) { return porSlug[s]; });
    if (chave === "ranking") return jogos.filter(function (j) { return j.ranking; });
    if (chave === "mais-jogados") return jogos.filter(function (j) { return j.partidas > 0; });
    if (chave === "novidades") return jogos.filter(function (j) { return j.novidade; });
    return null;
  }
  function nomeDaColecao(chave) {
    var c = COLECOES.filter(function (x) { return x.chave === chave; })[0];
    return c ? c.nome : "";
  }

  function desenhar() {
    var termo = semAcento(estado.termo.trim());
    var filtro = estado.filtro, ordem = estado.ordem;
    var lista = null, nome = "", frase = "", cor = "";
    if (temaDe[filtro]) {
      lista = jogos.filter(function (j) { return (j.familias || []).indexOf(filtro) >= 0; });
      nome = temaDe[filtro].nome; frase = temaDe[filtro].sub; cor = temaDe[filtro].cor;
    } else if (filtro && filtro !== "todos" && daColecao(filtro)) {
      lista = daColecao(filtro);
      nome = nomeDaColecao(filtro);
      if (ordem === "destaque" && filtro === "mais-jogados") ordem = "jogados";
      if (ordem === "destaque" && filtro === "novidades") ordem = "novos";
      if (ordem === "destaque" && filtro === "recentes") ordem = "recentes";
    } else {
      filtro = "";
    }
    if (estado.genero) {
      lista = (lista || jogos).filter(function (j) { return j.categoria === estado.genero; });
      nome = nome ? nome + " · " + estado.genero : estado.genero;
    }
    if (termo) {
      lista = (lista || jogos).filter(function (j) {
        return termo.split(/\s+/).every(function (p) { return (j.busca || "").indexOf(p) >= 0; });
      });
      nome = "Resultados para “" + estado.termo.trim() + "”";
    }

    var pedacos = [];
    if (lista) {
      lista = ordenar(lista, ordem);
      if (lista.length) pedacos.push(grade(lista));
      else pedacos.push(el("p", "bj-vazio", "Nenhum jogo encontrado aqui ainda. Tente outra palavra ou toque em “Ver tudo”."));
      titulo.textContent = nome;
      sub.textContent = lista.length + " jogo" + (lista.length === 1 ? "" : "s") + (frase ? " · " + frase : "");
    } else {
      // as estantes, cada uma com o seu tema -- e, primeiro, o que a pessoa jogou por último
      if (listaRecentes.length) {
        var r = faixa({ chave: "recentes", nome: "Continue de onde parou", sub: "Os jogos que você abriu por último neste aparelho",
                        icone: "fa-clock-rotate-left", cor: "#3fd0ff" }, listaRecentes.length, listaRecentes.length > 6, "recentes");
        r.appendChild(grade(listaRecentes.slice(0, 6).map(function (s) { return porSlug[s]; })));
        pedacos.push(r);
      }
      ESTANTES.forEach(function (tema) {
        var daEstante = ordenar(jogos.filter(function (j) { return (j.familias || []).indexOf(tema.chave) >= 0; }), ordem);
        if (!daEstante.length) return;
        var s = faixa(tema, daEstante.length, daEstante.length > POR_ESTANTE);
        s.appendChild(grade(daEstante.slice(0, POR_ESTANTE)));
        pedacos.push(s);
      });
      titulo.textContent = "Todas as estantes";
      sub.textContent = "Organizadas por plataforma";
    }
    conteudo.replaceChildren.apply(conteudo, pedacos);
    conteudo.classList.toggle("bj-conteudo--lista", estado.vista === "lista");
    if (barraTitulo) { if (cor) barraTitulo.style.setProperty("--tema", cor); else barraTitulo.style.removeProperty("--tema"); }
    if (limpar) limpar.hidden = !lista;
    if (hero) hero.hidden = !!lista;
    if (ordemEl && ordemEl.value !== estado.ordem) ordemEl.value = estado.ordem;

    // a lateral mostra onde a pessoa está
    raiz.querySelectorAll(".bj-item[data-bj-filtro]").forEach(function (item) {
      var atual = item.dataset.bjFiltro === "todos" ? !lista : item.dataset.bjFiltro === filtro;
      if (atual) item.setAttribute("aria-current", "true"); else item.removeAttribute("aria-current");
    });
    raiz.querySelectorAll("[data-bj-genero]").forEach(function (item) {
      if (item.dataset.bjGenero === estado.genero) item.setAttribute("aria-current", "true"); else item.removeAttribute("aria-current");
    });

    try {
      var url = new URL(location.href);
      [["estante", filtro], ["genero", estado.genero], ["q", estado.termo.trim()], ["ordem", estado.ordem === "destaque" ? "" : estado.ordem]].forEach(function (par) {
        if (par[1]) url.searchParams.set(par[0], par[1]); else url.searchParams.delete(par[0]);
      });
      history.replaceState(null, "", url);
    } catch (e) { /* nada */ }
  }

  function irParaABiblioteca() {
    var topo = bibEl.getBoundingClientRect().top;
    if (topo < 0 || topo > window.innerHeight * 0.6) bibEl.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ---------- as coleções do aparelho na lateral ---------- */
  [["recentes", listaRecentes.length], ["aparelho", noAparelho.length]].forEach(function (par) {
    var item = raiz.querySelector('.bj-item[data-bj-filtro="' + par[0] + '"]');
    if (!item) return;
    item.hidden = !par[1];
    var conta = item.querySelector("[data-bj-conta]");
    if (conta) conta.textContent = par[1];
  });

  /* ---------- os cliques ---------- */
  raiz.addEventListener("click", function (e) {
    var alvo = e.target.closest("[data-bj-filtro], [data-bj-genero], [data-bj-limpar], [data-bj-jogo], [data-bj-vista]");
    if (!alvo || !raiz.contains(alvo)) return;
    if (alvo.hasAttribute("data-bj-vista")) {
      estado.vista = alvo.dataset.bjVista;
      gravarLocal("ls-biblioteca-vista", estado.vista);
      raiz.querySelectorAll("[data-bj-vista]").forEach(function (b) { b.setAttribute("aria-pressed", b === alvo ? "true" : "false"); });
      conteudo.classList.toggle("bj-conteudo--lista", estado.vista === "lista");
      return;
    }
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;  // abrir numa aba nova continua valendo
    e.preventDefault();
    if (alvo.hasAttribute("data-bj-jogo")) { abrirFicha(porSlug[alvo.dataset.bjJogo], alvo); return; }
    if (alvo.hasAttribute("data-bj-limpar")) {
      estado.filtro = ""; estado.genero = ""; estado.termo = "";
      if (campo) campo.value = "";
    } else if (alvo.hasAttribute("data-bj-genero")) {
      estado.genero = estado.genero === alvo.dataset.bjGenero ? "" : alvo.dataset.bjGenero;
    } else if (alvo.dataset.bjFiltro === "todos") {
      estado.filtro = ""; estado.genero = ""; estado.termo = "";
      if (campo) campo.value = "";
    } else {
      estado.filtro = alvo.dataset.bjFiltro;
    }
    desenhar();
    irParaABiblioteca();
  });
  if (ordemEl) ordemEl.addEventListener("change", function () { estado.ordem = ordemEl.value; desenhar(); });
  if (barra) barra.addEventListener("submit", function (e) { e.preventDefault(); desenhar(); });
  var vistas = raiz.querySelector("[data-bj-vistas]");
  if (vistas) {
    vistas.hidden = false;
    raiz.querySelectorAll("[data-bj-vista]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.bjVista === estado.vista ? "true" : "false"); });
  }

  /* ---------- a busca: na hora, dentro da biblioteca ---------- */
  var espera = 0;
  if (campo) {
    campo.addEventListener("input", function () {
      clearTimeout(espera);
      espera = setTimeout(function () { estado.termo = campo.value; desenhar(); }, 140);
    });
  }
  if (formulario) {
    formulario.addEventListener("submit", function (e) {
      e.preventDefault();
      estado.termo = campo ? campo.value : "";
      desenhar();
      irParaABiblioteca();
    });
  }

  /* ---------- a ficha do jogo ---------- */
  var ficha = document.querySelector("[data-bj-ficha]");
  var quemAbriu = null;
  function campoDaFicha(nome) { return ficha.querySelector("[data-bj-ficha-" + nome + "]"); }
  function dado(iconeNome, texto) {
    var li = el("li");
    li.appendChild(icone(iconeNome));
    li.appendChild(document.createTextNode(texto));
    return li;
  }
  function quandoFoi(ms) {
    var min = Math.round((Date.now() - ms) / 60000);
    if (min < 2) return "agora há pouco";
    if (min < 60) return "há " + min + " minutos";
    var h = Math.round(min / 60);
    if (h < 24) return "há " + h + " hora" + (h === 1 ? "" : "s");
    var d = Math.round(h / 24);
    return "há " + d + " dia" + (d === 1 ? "" : "s");
  }
  var tocar = false;
  try { tocar = window.matchMedia("(pointer: coarse)").matches; } catch (e) { tocar = false; }

  function dicaLinha(iconeNome, rotulo, texto) {
    var linha = el("div", "bj-dica");
    linha.appendChild(icone(iconeNome));
    var corpo = el("div");
    corpo.appendChild(el("strong", "", rotulo));
    corpo.appendChild(document.createTextNode(texto || ""));
    linha.appendChild(corpo);
    return linha;
  }
  /* O como jogar desenhado: no computador, as teclas de cada botão; no celular, onde fica cada um. */
  function comoJogar(jogo) {
    var caixa = el("div");
    var lista = CONTROLES[jogo.sistema] || [];
    if (lista.length) {
      var t = el("div", "bj-teclas");
      lista.forEach(function (c) {
        var tile = el("div", "bj-tecla");
        tile.appendChild(el("span", "", c.acao));
        var ks = el("div");
        if (tocar) ks.appendChild(el("small", "", c.celular));
        else c.teclas.forEach(function (k) { ks.appendChild(el("kbd", "", k)); });
        tile.appendChild(ks);
        t.appendChild(tile);
      });
      caixa.appendChild(t);
      caixa.appendChild(dicaLinha(tocar ? "fa-mobile-screen" : "fa-keyboard", tocar ? "No celular" : "No computador", tocar ? DICAS.celular : DICAS.pc));
      return caixa;
    }
    if (jogo.dicas && (jogo.dicas.pc || jogo.dicas.celular)) {
      if (jogo.dicas.pc) caixa.appendChild(dicaLinha("fa-keyboard", "No computador", jogo.dicas.pc));
      if (jogo.dicas.celular) caixa.appendChild(dicaLinha("fa-mobile-screen", "No celular", jogo.dicas.celular));
      return caixa;
    }
    if (jogo.como) { caixa.appendChild(dicaLinha("fa-hand-pointer", "Como jogar", jogo.como)); return caixa; }
    return null;
  }

  function abrirFicha(jogo, origem) {
    if (!jogo || !ficha) { if (origem && origem.href) location.href = origem.href; return; }
    quemAbriu = origem || null;
    var tema = temaDe[jogo.estante] || { nome: "", cor: jogo.tema };
    var caixa = ficha.querySelector(".bj-ficha-caixa");
    caixa.style.setProperty("--tema", jogo.tema || tema.cor);
    caixa.style.setProperty("--cor", jogo.cor || "#3fd0ff");
    var poster = campoDaFicha("poster"), imagem = campoDaFicha("capa");
    poster.hidden = !(jogo.poster || jogo.capa);
    if (!poster.hidden) poster.src = jogo.poster || jogo.capa;
    imagem.hidden = !jogo.capa;
    if (jogo.capa) imagem.src = jogo.capa;
    imagem.alt = jogo.titulo;
    campoDaFicha("sigla").textContent = jogo.sigla || "";
    campoDaFicha("estante").textContent = tema.nome || jogo.plataforma;
    campoDaFicha("titulo").textContent = jogo.titulo;
    campoDaFicha("chamada").textContent = jogo.chamada || "";
    campoDaFicha("desc").textContent = jogo.descricao || "";
    var dados = [];
    dados.push(dado("fa-gamepad", jogo.tipo === "nosso" && !jogo.sistema ? "Lazer & Sport" : jogo.plataforma));
    if (jogo.categoria) dados.push(dado("fa-tag", jogo.categoria));
    if (jogo.ranking) dados.push(dado("fa-trophy", "Com ranking"));
    if (jogo.campeao) dados.push(dado("fa-crown", "Campeão: " + jogo.campeao.nome + " · " + Number(jogo.campeao.pontos).toLocaleString("pt-BR") + " pts"));
    if (jogo.partidas) dados.push(dado("fa-fire", jogo.partidas.toLocaleString("pt-BR") + " partida" + (jogo.partidas === 1 ? "" : "s")));
    if (noAparelho.indexOf(jogo.slug) >= 0) dados.push(dado("fa-download", "Já no aparelho: abre na hora"));
    if (recentes[jogo.slug]) dados.push(dado("fa-clock-rotate-left", "Você jogou " + quandoFoi(recentes[jogo.slug])));
    campoDaFicha("dados").replaceChildren.apply(campoDaFicha("dados"), dados);
    var como = campoDaFicha("como"), comandos = comoJogar(jogo);
    como.hidden = !comandos;
    campoDaFicha("teclas").replaceChildren.apply(campoDaFicha("teclas"), comandos ? [comandos] : []);
    campoDaFicha("jogar").href = jogo.url;
    var mais = campoDaFicha("mais");
    mais.querySelector("span").textContent = "Mais de " + (tema.nome || "da estante");
    mais.onclick = function () {
      fecharFicha();
      estado.filtro = jogo.estante; estado.genero = ""; estado.termo = "";
      if (campo) campo.value = "";
      desenhar();
      irParaABiblioteca();
    };
    ficha.hidden = false;
    document.documentElement.style.overflow = "hidden";
    campoDaFicha("jogar").focus({ preventScroll: true });
  }
  function fecharFicha() {
    if (!ficha || ficha.hidden) return;
    ficha.hidden = true;
    document.documentElement.style.overflow = "";
    if (quemAbriu && document.contains(quemAbriu)) quemAbriu.focus({ preventScroll: true });
  }
  if (ficha) {
    ficha.addEventListener("click", function (e) { if (e.target.closest("[data-bj-fechar]")) fecharFicha(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") fecharFicha(); });
  }

  desenhar();

  /* ---------- o carrossel de destaques ---------- */
  if (hero) {
    var slides = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-slide]"));
    var pontos = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-pontos] button"));
    var atual = 0;
    var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var relogio = 0;
    var mostrar = function (i) {
      atual = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) {
        s.classList.toggle("pg-slide--ativo", k === atual);
        if (k === atual) s.removeAttribute("aria-hidden"); else s.setAttribute("aria-hidden", "true");
      });
      pontos.forEach(function (p, k) { if (k === atual) p.setAttribute("aria-current", "true"); else p.removeAttribute("aria-current"); });
    };
    var girar = function () {
      clearInterval(relogio);
      if (!reduzido && slides.length > 1) relogio = setInterval(function () { if (!hero.hidden) mostrar(atual + 1); }, 6500);
    };
    var antes = hero.querySelector("[data-portal-antes]");
    var depois = hero.querySelector("[data-portal-depois]");
    if (antes) antes.addEventListener("click", function () { mostrar(atual - 1); girar(); });
    if (depois) depois.addEventListener("click", function () { mostrar(atual + 1); girar(); });
    pontos.forEach(function (p, k) { p.addEventListener("click", function () { mostrar(k); girar(); }); });
    hero.addEventListener("mouseenter", function () { clearInterval(relogio); });
    hero.addEventListener("mouseleave", girar);
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
