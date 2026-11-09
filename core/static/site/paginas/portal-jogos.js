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
  // os jogos com um ponto guardado ("Continuar de onde parou", jogo-progresso.js)
  var comPonto = {};
  (function () {
    var indice = lerLocal("ls-progresso-indice");
    Object.keys(indice).forEach(function (chave) {
      var jogo = (indice[chave] || {}).jogo || chave.split("|")[0];
      if (porSlug[jogo]) comPonto[jogo] = Math.max(comPonto[jogo] || 0, Number(indice[chave].quando) || 0);
    });
  })();
  var listaRecentes = Object.keys(recentes).filter(function (s) { return porSlug[s] && recentes[s] > 0; })
    .sort(function (a, b) { return recentes[b] - recentes[a]; });

  /* ---------- quem está jogando agora (presenca-jogos.js) ----------
     A conta vem na resposta de cada batida da aba (o evento "ls-presenca"); antes da primeira, vale a
     que veio na página. Quem está olhando a biblioteca não está jogando: se o jogo aberto no app for um
     deles, a conta dele desconta este aparelho. */
  var vivo = { online: 0, jogando: {}, meu: "" };
  jogos.forEach(function (j) { if (j.jogando) vivo.jogando[j.slug] = j.jogando; });
  function jogandoAgora(slug) {
    var n = Number(vivo.jogando[slug]) || 0;
    return Math.max(0, n - (vivo.meu === slug ? 1 : 0));
  }
  function textoJogando(n) { return n + " jogando agora"; }
  // o "N jogando" no canto de baixo da capa de um cartão (some com ninguém)
  function pintarVivo(arte, n) {
    var selo = arte.querySelector(".bj-vivo");
    if (!n) { if (selo) selo.remove(); return; }
    if (!selo) {
      selo = el("span", "bj-vivo");
      var ponto = el("i", "pg-vivo-ponto");
      ponto.setAttribute("aria-hidden", "true");
      selo.appendChild(ponto);
      selo.appendChild(document.createTextNode(""));
      arte.insertBefore(selo, arte.firstChild);
    }
    selo.lastChild.nodeValue = n + " jogando";
  }

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
  var generoEl = raiz.querySelector("[data-bj-genero-escolha]");
  var pulso = raiz.querySelector("[data-pg-pulso]");
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

  /* ---------- o cartão (o mesmo de partials/cartao_jogo.html) ---------- */
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
  // não pode se chamar "pontos": o carrossel, mais abaixo, tem um "var pontos" que sobe para esta função toda e a apagaria
  function emPontos(n) { return Number(n || 0).toLocaleString("pt-BR"); }
  // a arte de reserva de quem não tem capa: o gradiente da cor do jogo, o ícone do console e o nome
  function reserva(jogo) {
    var r = el("span", "bj-capa-reserva");
    r.setAttribute("aria-hidden", "true");
    r.appendChild(icone((temaDe[jogo.estante] || {}).icone || "fa-gamepad"));
    r.appendChild(el("b", "", jogo.titulo));
    return r;
  }
  function capa(jogo) {
    var cartao = el("article", "bj-capa");
    cartao.dataset.portalCartao = jogo.slug;
    cartao.style.setProperty("--cor", jogo.cor || "#3fd0ff");
    cartao.style.setProperty("--tema", jogo.tema || "#3fd0ff");
    // o cartão inteiro leva à ficha (os cliques, mais abaixo); sem JavaScript, à página do jogo
    var a = el("a", "bj-capa-link");
    a.href = jogo.url;
    a.dataset.bjJogo = jogo.slug;
    var arte = el("span", "bj-capa-arte");
    if (jogo.capa) {
      var fundo = el("img", "bj-capa-fundo");
      fundo.src = jogo.capa; fundo.alt = ""; fundo.loading = "lazy"; fundo.decoding = "async"; fundo.setAttribute("aria-hidden", "true");
      var img = el("img", "bj-capa-img");
      img.src = jogo.capa; img.alt = ""; img.loading = "lazy"; img.decoding = "async"; img.width = 320; img.height = 320;
      arte.appendChild(fundo);
      arte.appendChild(img);
    } else {
      arte.appendChild(reserva(jogo));
    }
    pintarVivo(arte, jogandoAgora(jogo.slug));
    a.appendChild(arte);
    var texto = el("span", "bj-capa-texto");
    texto.appendChild(el("strong", "", jogo.titulo));
    if (comPonto[jogo.slug]) {
      // tem um ponto guardado neste aparelho: o jogo continua de onde a pessoa parou
      var ponto = el("small", "bj-capa-ponto");
      ponto.appendChild(icone("fa-clock-rotate-left"));
      ponto.appendChild(document.createTextNode(" Ponto guardado"));
      texto.appendChild(ponto);
    } else {
      // o console já está no selo da capa: aqui vão o gênero e as partidas
      var partes = [jogo.categoria || (jogo.tipo === "nosso" ? "Lazer & Sport" : jogo.plataforma)];
      if (jogo.partidas) partes.push(jogo.partidas + " partida" + (jogo.partidas === 1 ? "" : "s"));
      texto.appendChild(el("small", "", partes.join(" · ")));
    }
    a.appendChild(texto);
    // os selos vêm depois do nome no código (o leitor de tela diz o nome primeiro); na tela, sobre a capa
    var selos = el("span", "bj-capa-selos");
    selos.appendChild(el("span", "bj-sigla", jogo.sigla || ""));
    var marcas = el("span", "bj-marcas");
    if (jogo.novidade) marcas.appendChild(el("span", "bj-marca bj-marca--nova", "Novo"));
    if (jogo.ranking) {
      var r = el("span", "bj-marca bj-marca--ranking");
      r.appendChild(icone("fa-trophy"));
      if (jogo.campeao) {
        r.title = "Com ranking · recorde de " + jogo.campeao.nome + ": " + emPontos(jogo.campeao.pontos) + " pts";
        r.appendChild(el("span", "bj-oculto", "Recorde:"));
        r.appendChild(document.createTextNode(" " + emPontos(jogo.campeao.pontos)));
      } else {
        r.title = "Com ranking";
        r.appendChild(el("span", "bj-oculto", "Com ranking"));
      }
      marcas.appendChild(r);
    }
    if (noAparelho.indexOf(jogo.slug) >= 0) {
      var g = el("span", "bj-marca bj-marca--aparelho");
      g.title = "Já no aparelho: abre na hora";
      g.appendChild(icone("fa-download"));
      g.appendChild(el("span", "bj-oculto", "Já no aparelho"));
      marcas.appendChild(g);
    }
    selos.appendChild(marcas);
    a.appendChild(selos);
    cartao.appendChild(a);
    // o Jogar por cima da capa: abre o jogo direto, dentro do app (o clique do [data-app-jogo], no fim)
    var continuar = !!comPonto[jogo.slug];
    var acoes = el("span", "bj-capa-acoes");
    var jogar = el("a", "bj-capa-jogar");
    jogar.href = jogo.url;
    jogar.dataset.appJogo = jogo.slug;
    jogar.setAttribute("aria-label", (continuar ? "Continuar " : "Jogar ") + jogo.titulo);
    jogar.appendChild(icone("fa-play"));
    jogar.appendChild(el("span", "", continuar ? "Continuar" : "Jogar"));
    acoes.appendChild(jogar);
    cartao.appendChild(acoes);
    return cartao;
  }
  // fila: nas estantes, a grade vira uma fila que rola de lado no celular (portal-jogos.css)
  function grade(lista, fila) {
    var g = el("div", "bj-grade" + (fila ? " bj-grade--fila" : ""));
    lista.forEach(function (j) { g.appendChild(capa(j)); });
    return g;
  }
  function faixa(tema, total, mais, filtroDoVerTodos) {
    var s = el("section", "bj-estante");
    s.dataset.estante = tema.chave;
    s.style.setProperty("--tema", tema.cor);
    s.setAttribute("aria-labelledby", "estante-" + tema.chave);
    var f = el("div", "bj-estante-faixa");
    var ic = el("span", "bj-estante-icone");
    ic.setAttribute("aria-hidden", "true");
    ic.appendChild(icone(tema.icone));
    f.appendChild(ic);
    var nome = el("div", "bj-estante-nome");
    var h = el("h3", "", tema.nome);
    h.id = "estante-" + tema.chave;
    nome.appendChild(h);
    nome.appendChild(el("p", "", tema.sub));
    f.appendChild(nome);
    f.appendChild(el("span", "bj-estante-total", total + " jogo" + (total === 1 ? "" : "s")));
    if (mais) {
      var link = el("a", "bj-estante-todos", "Ver todos ");
      link.href = "?estante=" + (filtroDoVerTodos || tema.chave) + "#biblioteca";
      link.setAttribute("aria-label", "Ver todos os jogos de " + tema.nome);
      link.dataset.bjFiltro = filtroDoVerTodos || tema.chave;
      link.appendChild(icone("fa-chevron-right"));
      f.appendChild(link);
    }
    s.appendChild(f);
    return s;
  }

  // nada achado: o mesmo aviso do servidor, com o atalho para a biblioteca inteira
  function vazio() {
    var p = el("p", "bj-vazio");
    p.appendChild(icone("fa-magnifying-glass"));
    p.appendChild(document.createTextNode(" Nenhum jogo encontrado aqui ainda. Tente outra palavra ou "));
    var tudo = el("a", "", "veja a biblioteca inteira");
    tudo.href = location.pathname + "#biblioteca";
    tudo.setAttribute("data-bj-limpar", "");
    p.appendChild(tudo);
    p.appendChild(document.createTextNode("."));
    return p;
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
      else pedacos.push(vazio());
      titulo.textContent = nome;
      sub.textContent = lista.length + " jogo" + (lista.length === 1 ? "" : "s") + (frase ? " · " + frase : "");
    } else {
      // as estantes, cada uma com o seu tema -- e, primeiro, o que a pessoa jogou por último
      if (listaRecentes.length) {
        var r = faixa({ chave: "recentes", nome: "Continue de onde parou", sub: "Os jogos que você abriu por último neste aparelho",
                        icone: "fa-clock-rotate-left", cor: "#3fd0ff" }, listaRecentes.length, listaRecentes.length > 6, "recentes");
        r.appendChild(grade(listaRecentes.slice(0, 6).map(function (s) { return porSlug[s]; }), true));
        pedacos.push(r);
      }
      ESTANTES.forEach(function (tema) {
        var daEstante = ordenar(jogos.filter(function (j) { return (j.familias || []).indexOf(tema.chave) >= 0; }), ordem);
        if (!daEstante.length) return;
        var s = faixa(tema, daEstante.length, daEstante.length > POR_ESTANTE);
        s.appendChild(grade(daEstante.slice(0, POR_ESTANTE), true));
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
    if (pulso) pulso.hidden = !!lista;
    if (ordemEl && ordemEl.value !== estado.ordem) ordemEl.value = estado.ordem;
    if (generoEl && generoEl.value !== estado.genero) generoEl.value = estado.genero;

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

  // no tablet e no celular a lateral é uma fila que rola de lado: o botão escolhido vem para o meio dela
  // (só a fila rola; a página fica onde está)
  function mostrarEscolhido() {
    var fila = raiz.querySelector("[data-bj-lado]");
    var escolhido = fila && fila.querySelector('.bj-item[aria-current="true"]:not([hidden])');
    if (!escolhido || fila.scrollWidth <= fila.clientWidth + 1) return;
    var f = fila.getBoundingClientRect(), b = escolhido.getBoundingClientRect();
    fila.scrollLeft += (b.left - f.left) - (f.width - b.width) / 2;
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
    mostrarEscolhido();
    irParaABiblioteca();
  });
  if (ordemEl) ordemEl.addEventListener("change", function () { estado.ordem = ordemEl.value; desenhar(); });
  // o gênero da barra (tablet e celular): o mesmo filtro dos gêneros da lateral
  if (generoEl) generoEl.addEventListener("change", function () { estado.genero = generoEl.value; desenhar(); });
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
        // o que o botão FAZ: o que a equipe disse para este jogo, ou o costume do console
        var faz = (jogo.acoes && jogo.acoes[c.acao]) || c.funcao;
        var icone = (jogo.acoes && jogo.acoes[c.acao]) ? (jogo.icones || {})[c.acao] : c.icone;
        if (faz) {
          var linhaFaz = el("em", "bj-tecla-faz");
          if (icone) {
            var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("class", "bj-ico");
            svg.setAttribute("aria-hidden", "true");
            var uso = document.createElementNS("http://www.w3.org/2000/svg", "use");
            uso.setAttribute("href", "#a-" + icone);
            svg.appendChild(uso);
            linhaFaz.appendChild(svg);
          }
          linhaFaz.appendChild(document.createTextNode(faz));
          tile.appendChild(linhaFaz);
        }
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
    // atrás da capa: a cena do jogo da casa (capas/topo/), nítida; nos outros, o pôster
    var cena = jogo.topo_estreito || "";
    poster.hidden = !(cena || jogo.poster || jogo.capa);
    poster.classList.toggle("is-cena", !!cena);
    if (!poster.hidden) poster.src = cena || jogo.poster || jogo.capa;
    imagem.hidden = !jogo.capa;
    if (jogo.capa) imagem.src = jogo.capa;
    imagem.alt = jogo.titulo;
    var semCapa = campoDaFicha("reserva");
    if (semCapa) {
      semCapa.hidden = !!jogo.capa;
      semCapa.replaceChildren(icone((temaDe[jogo.estante] || {}).icone || "fa-gamepad"), el("b", "", jogo.titulo));
    }
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
    if (jogandoAgora(jogo.slug)) {
      var agora = el("li", "bj-ficha-vivo");
      var ponto = el("i", "pg-vivo-ponto");
      ponto.setAttribute("aria-hidden", "true");
      agora.appendChild(ponto);
      agora.appendChild(document.createTextNode(textoJogando(jogandoAgora(jogo.slug))));
      dados.push(agora);
    }
    if (jogo.partidas) dados.push(dado("fa-fire", jogo.partidas.toLocaleString("pt-BR") + " partida" + (jogo.partidas === 1 ? "" : "s")));
    if (noAparelho.indexOf(jogo.slug) >= 0) dados.push(dado("fa-download", "Já no aparelho: abre na hora"));
    if (recentes[jogo.slug]) dados.push(dado("fa-clock-rotate-left", "Você jogou " + quandoFoi(recentes[jogo.slug])));
    if (comPonto[jogo.slug]) dados.push(dado("fa-play", "Ponto guardado: continua de onde você parou"));
    campoDaFicha("dados").replaceChildren.apply(campoDaFicha("dados"), dados);
    var como = campoDaFicha("como"), comandos = comoJogar(jogo);
    como.hidden = !comandos;
    campoDaFicha("teclas").replaceChildren.apply(campoDaFicha("teclas"), comandos ? [comandos] : []);
    campoDaFicha("jogar").href = jogo.url;
    var textoJogar = campoDaFicha("jogar").querySelector("[data-bj-ficha-jogar-texto]");
    if (textoJogar) textoJogar.textContent = comPonto[jogo.slug] ? "Continuar" : "Jogar agora";
    // no app, o jogo abre ali mesmo (a tela cheia não fecha)
    campoDaFicha("jogar").onclick = function (e) {
      if (window.LSApp && window.LSApp.abrir(jogo, e)) { e.preventDefault(); fecharFicha(); }
    };
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
  mostrarEscolhido();

  /* ---------- o Jogar da vitrine: no app, o jogo abre ali mesmo ---------- */
  raiz.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest("[data-app-jogo]");
    if (!link || !window.LSApp) return;
    if (window.LSApp.abrir(porSlug[link.dataset.appJogo], e)) e.preventDefault();
  });

  /* ---------- o carrossel de destaques ---------- */
  if (hero) {
    var slides = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-slide]"));
    var pontos = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-pontos] button"));
    var atual = 0;
    var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var relogio = 0;
    // o carrossel só trabalha quando está na tela
    var naTela = true;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entradas) {
        naTela = entradas[0].isIntersecting;
        hero.classList.toggle("is-parado", !naTela);
      }, { threshold: 0.15 }).observe(hero);
    }
    document.addEventListener("visibilitychange", function () { hero.classList.toggle("is-parado", document.hidden || !naTela); });
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
      if (!reduzido && slides.length > 1) relogio = setInterval(function () {
        // parado fora da tela, com a aba escondida ou com um jogo aberto por cima
        if (!hero.hidden && naTela && !document.hidden && !document.body.classList.contains("app-jogando")) mostrar(atual + 1);
      }, 6500);
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

  /* ---------- os números ao vivo: gente online, quem joga cada jogo, o "Em alta agora" ----------
     Tudo some com elegância: o selo da barra só aparece com mais alguém além de quem olha (2 ou mais),
     e o "jogando agora" só com alguém jogando. */
  var seloOnline = raiz.querySelector("[data-pg-online]");
  var emAlta = raiz.querySelector("[data-pg-alta]");
  function pintarNumeros() {
    if (seloOnline) {
      seloOnline.hidden = vivo.online < 2;
      seloOnline.querySelector("[data-pg-online-n]").textContent = emPontos(vivo.online);
      seloOnline.setAttribute("aria-label", emPontos(vivo.online) + " pessoas online agora");
    }
    // o destaque de cada jogo
    raiz.querySelectorAll("[data-pg-jogando]").forEach(function (item) {
      var n = jogandoAgora(item.dataset.pgJogando);
      item.hidden = !n;
      if (n) item.querySelector("[data-pg-jogando-texto]").textContent = textoJogando(n);
    });
    // as capas da biblioteca
    raiz.querySelectorAll("[data-portal-cartao]").forEach(function (cartao) {
      var arte = cartao.querySelector(".bj-capa-arte");
      if (arte) pintarVivo(arte, jogandoAgora(cartao.dataset.portalCartao));
    });
    // o jogo com mais gente agora (empate: o que vem antes na biblioteca)
    if (emAlta) {
      var melhor = null;
      jogos.forEach(function (j) {
        var n = jogandoAgora(j.slug);
        if (n && (!melhor || n > melhor.n)) melhor = { jogo: j, n: n };
      });
      emAlta.hidden = !melhor;
      if (melhor) {
        emAlta.href = melhor.jogo.url;
        emAlta.dataset.appJogo = melhor.jogo.slug;
        emAlta.querySelector("[data-pg-alta-nome]").textContent = melhor.jogo.titulo;
        emAlta.querySelector("[data-pg-alta-n]").textContent = melhor.n + " jogando";
      }
    }
  }
  if (seloOnline) vivo.online = Number(seloOnline.querySelector("[data-pg-online-n]").textContent) || 0;
  document.addEventListener("ls-presenca", function (e) {
    var d = e.detail || {};
    vivo = { online: Number(d.online) || 0, jogando: d.jogando || {}, meu: d.meu || "" };
    pintarNumeros();
  });
  if (window.LSPresenca && window.LSPresenca.ultimo) {
    var u = window.LSPresenca.ultimo;
    vivo = { online: Number(u.online) || 0, jogando: u.jogando || {}, meu: u.meu || "" };
    pintarNumeros();
  }

  /* ---------- o "Continuar" do pulso: o último jogo aberto neste aparelho ---------- */
  var continuar = raiz.querySelector("[data-pg-continuar]");
  if (continuar && listaRecentes.length) {
    var ultimo = porSlug[listaRecentes[0]];
    continuar.hidden = false;
    continuar.href = ultimo.url;
    continuar.dataset.appJogo = ultimo.slug;
    continuar.querySelector("[data-pg-continuar-nome]").textContent = ultimo.titulo;
    continuar.title = "Você jogou " + quandoFoi(recentes[ultimo.slug]);
  }

  /* ---------- as artes do destaque ----------
     Os jogos da casa têm a cena do jogo (capas/topo/); os outros ganham aqui um MURAL da capa: a capa
     repetida em ladrilhos inclinados, com a cor do jogo, uma luz, a vinheta, um grão bem leve e o escuro
     do lado do texto (à esquerda no computador; embaixo no tablet em pé e no celular, onde o texto fica
     embaixo). Sem capa, só a cor do jogo. Nada de foto desfocada esticada.
     LEVE: só o destaque da vez e os vizinhos baixam a arte (data-src) e pintam o mural; o mural é
     desenhado uma vez no tamanho da tela (até 1600 px de largura) e refeito só se o destaque mudar
     de tamanho de verdade. */
  if (hero) (function () {
    var lista = Array.prototype.slice.call(hero.querySelectorAll("[data-portal-slide]"));
    if (!lista.length) return;
    var grao = null;

    function corDe(hexa) {
      var m = /^#?([0-9a-f]{6})$/i.exec((hexa || "").trim());
      var n = m ? parseInt(m[1], 16) : 0x3fd0ff;
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    function rgba(c, a) { return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")"; }
    function misturar(c, d, t) { return [0, 1, 2].map(function (i) { return Math.round(c[i] * (1 - t) + d[i] * t); }); }
    // o grão: um ladrilho de ruído feito uma vez só, repetido por cima de tudo
    function padraoDeGrao(g) {
      if (!grao) {
        grao = document.createElement("canvas");
        grao.width = grao.height = 96;
        var gg = grao.getContext("2d"), dados = gg.createImageData(96, 96);
        for (var i = 0; i < dados.data.length; i += 4) {
          var v = Math.random() * 255;
          dados.data[i] = dados.data[i + 1] = dados.data[i + 2] = v;
          dados.data[i + 3] = 14;
        }
        gg.putImageData(dados, 0, 0);
      }
      return g.createPattern(grao, "repeat");
    }
    function ladrilho(g, img, x, y, lado, raio) {
      g.save();
      g.beginPath();
      if (g.roundRect) g.roundRect(x, y, lado, lado, raio); else g.rect(x, y, lado, lado);
      g.clip();
      var escala = Math.max(lado / img.naturalWidth, lado / img.naturalHeight);
      var l = img.naturalWidth * escala, a = img.naturalHeight * escala;
      g.drawImage(img, x + (lado - l) / 2, y + (lado - a) / 2, l, a);
      g.restore();
    }
    function desenharMural(tela, W, H, cor, img) {
      var g = tela.getContext("2d");
      if (!g) return;
      var largo = W / H > 1.2;
      var escuro = [4, 7, 15];
      // a base: a cor do jogo, bem escura
      g.globalCompositeOperation = "source-over";
      g.globalAlpha = 1;
      var base = g.createLinearGradient(0, 0, W, H);
      base.addColorStop(0, rgba(misturar(cor, escuro, 0.9), 1));
      base.addColorStop(1, rgba(misturar(cor, escuro, 0.72), 1));
      g.fillStyle = base;
      g.fillRect(0, 0, W, H);
      // o centro da luz: do lado da arte (à direita no largo, em cima no estreito)
      var cx = largo ? W * 0.68 : W * 0.58, cy = largo ? H * 0.45 : H * 0.3;
      if (img && img.naturalWidth) {
        var lado = largo ? H * 0.46 : W * 0.4;
        var passo = lado * 1.09, raio = lado * 0.07, angulo = -0.22;
        var cos = Math.cos(angulo), sen = Math.sin(angulo), alcance = Math.hypot(W, H) * 0.62;
        var n = Math.ceil(Math.hypot(W, H) / passo / 2) + 2;
        g.save();
        g.translate(cx, cy);
        g.rotate(angulo);
        for (var lin = -n; lin <= n; lin++) {
          for (var col = -n; col <= n; col++) {
            // as fileiras desencontradas, como um mural de cartazes
            var x = (col + (lin % 2 ? 0.5 : 0)) * passo, y = lin * passo;
            var px = cx + x * cos - y * sen, py = cy + x * sen + y * cos;
            if (px < -lado || px > W + lado || py < -lado || py > H + lado) continue;
            // os ladrilhos perto da luz acesos; os de longe somem no escuro
            var perto = Math.max(0, 1 - Math.hypot(x, y) / (alcance * 1.25));
            g.globalAlpha = 0.2 + 0.78 * perto * Math.sqrt(perto);
            ladrilho(g, img, x - lado / 2, y - lado / 2, lado, raio);
          }
        }
        g.restore();
        g.globalAlpha = 1;
        // a cor do jogo amarra as capas num desenho só
        g.globalCompositeOperation = "soft-light";
        g.fillStyle = rgba(cor, 0.45);
        g.fillRect(0, 0, W, H);
      }
      // a luz na cor do jogo, somada por cima
      g.globalCompositeOperation = "screen";
      var luz = g.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W, H) * 0.55);
      luz.addColorStop(0, rgba(cor, 0.42));
      luz.addColorStop(0.45, rgba(cor, 0.12));
      luz.addColorStop(1, rgba(cor, 0));
      g.fillStyle = luz;
      g.fillRect(0, 0, W, H);
      // riscos de luz em diagonal, bem leves
      g.lineCap = "round";
      [[0.5, 0.012, 0.16], [0.6, 0.004, 0.3], [0.74, 0.02, 0.1], [0.88, 0.005, 0.24]].forEach(function (r) {
        g.strokeStyle = rgba(misturar(cor, [255, 255, 255], 0.35), r[2]);
        g.lineWidth = Math.max(1, W * r[1]);
        g.beginPath();
        g.moveTo(W * r[0], H * 1.05);
        g.lineTo(W * r[0] + H * 0.55, -H * 0.05);
        g.stroke();
      });
      // a vinheta e o escuro do lado do texto
      g.globalCompositeOperation = "source-over";
      var vinheta = g.createRadialGradient(cx, cy, Math.min(W, H) * 0.25, cx, cy, Math.hypot(W, H) * 0.75);
      vinheta.addColorStop(0, rgba(escuro, 0));
      vinheta.addColorStop(1, rgba(escuro, 0.72));
      g.fillStyle = vinheta;
      g.fillRect(0, 0, W, H);
      var lado2 = largo ? g.createLinearGradient(0, 0, W, 0) : g.createLinearGradient(0, H, 0, 0);
      lado2.addColorStop(0, rgba(escuro, 0.94));
      lado2.addColorStop(largo ? 0.32 : 0.36, rgba(escuro, 0.72));
      lado2.addColorStop(largo ? 0.62 : 0.72, rgba(escuro, 0));
      g.fillStyle = lado2;
      g.fillRect(0, 0, W, H);
      if (largo) {
        var chao = g.createLinearGradient(0, H, 0, H * 0.5);
        chao.addColorStop(0, rgba(escuro, 0.6));
        chao.addColorStop(1, rgba(escuro, 0));
        g.fillStyle = chao;
        g.fillRect(0, 0, W, H);
      }
      // o grão por cima de tudo (some o degrau dos gradientes)
      var padrao = padraoDeGrao(g);
      if (padrao) { g.fillStyle = padrao; g.fillRect(0, 0, W, H); }
    }

    var capas = {};  // a mesma capa serve a vários desenhos
    function carregarCapa(url) {
      if (!url) return Promise.resolve(null);
      if (!capas[url]) capas[url] = new Promise(function (ok) {
        var img = new Image();
        img.decoding = "async";
        img.onload = function () { ok(img); };
        img.onerror = function () { ok(null); };
        img.src = url;
      });
      return capas[url];
    }
    function pintarMural(caixa) {
      var largura = caixa.clientWidth, altura = caixa.clientHeight;
      if (!largura || !altura) return;
      var densidade = Math.min(1.5, window.devicePixelRatio || 1);
      var W = Math.min(1600, Math.round(largura * densidade)), H = Math.round(W * altura / largura);
      var tamanho = W + "x" + H;
      if (caixa.dataset.pgPintado === tamanho) return;
      caixa.dataset.pgPintado = tamanho;
      var cor = corDe(getComputedStyle(caixa.closest("[data-portal-slide]")).getPropertyValue("--cor"));
      carregarCapa(caixa.dataset.pgMural).then(function (img) {
        if (caixa.dataset.pgPintado !== tamanho) return;  // a tela mudou no caminho: outro desenho vem aí
        var tela = document.createElement("canvas");
        tela.width = W; tela.height = H;
        try { desenharMural(tela, W, H, cor, img); } catch (e) { return; }
        caixa.replaceChildren(tela);
        caixa.classList.add("is-pronto");
      });
    }
    // a arte de um destaque: troca o data-src pelo src (a cena) ou pinta o mural
    function acordar(slide) {
      if (!slide) return;
      slide.querySelectorAll("source[data-srcset]").forEach(function (fonte) {
        fonte.srcset = fonte.dataset.srcset;
        fonte.removeAttribute("data-srcset");
      });
      slide.querySelectorAll("img[data-src]").forEach(function (img) {
        img.src = img.dataset.src;
        img.removeAttribute("data-src");
      });
      var mural = slide.querySelector("[data-pg-mural]");
      if (mural) pintarMural(mural);
    }
    // o da vez e os dois vizinhos (o próximo a entrar e o de antes, se a pessoa voltar)
    function emVolta(slide) {
      var i = lista.indexOf(slide);
      acordar(slide);
      acordar(lista[(i + 1) % lista.length]);
      acordar(lista[(i - 1 + lista.length) % lista.length]);
    }
    function daVez() { return lista.filter(function (s) { return s.classList.contains("pg-slide--ativo"); })[0] || lista[0]; }
    acordar(daVez());
    // os vizinhos esperam a página terminar de abrir (não disputam com a primeira arte)
    var depois = function () { setTimeout(function () { emVolta(daVez()); }, 600); };
    if (document.readyState === "complete") depois(); else window.addEventListener("load", depois, { once: true });
    if ("MutationObserver" in window) {
      var vigia = new MutationObserver(function (mudancas) {
        mudancas.forEach(function (m) { if (m.target.classList.contains("pg-slide--ativo")) emVolta(m.target); });
      });
      lista.forEach(function (s) { vigia.observe(s, { attributes: true, attributeFilter: ["class"] }); });
    }
    // mudou o tamanho do destaque (girou o celular, mudou a janela): os murais já pintados são refeitos
    if ("ResizeObserver" in window) {
      var espera = 0;
      new ResizeObserver(function () {
        clearTimeout(espera);
        espera = setTimeout(function () {
          hero.querySelectorAll("[data-pg-mural][data-pg-pintado]").forEach(pintarMural);
          // o destaque estava escondido (a página abriu numa busca) e voltou: o da vez ganha a arte
          acordar(daVez());
        }, 250);
      }).observe(hero);
    }
  })();
})();
