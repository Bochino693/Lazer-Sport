/* ======================================================================
   ANÁLISES E FICHAS DAS TELAS DE GESTÃO (LEIA-ME-V10, seção 76)

   Dois pedaços, um arquivo:
     * o painel "Desempenho" do topo de cada tela ([data-lsa-painel]);
     * o modal de detalhes ([data-lsa-ficha]) que abre ao tocar num objeto
       da lista ([data-detalhe-tipo][data-detalhe-id]) ou no atalho
       "Gráficos" que este arquivo põe em cada objeto.

   GRÁFICOS DESENHADOS AQUI, EM SVG. O painel não usa biblioteca nem CDN:
   uma linha com área para a série, a do período anterior em cinza, colunas
   por dia da semana e barras deitadas no ranking. Marcas finas (linha de
   2px, coluna de no máximo 24px com a ponta arredondada), grade de 1px, e
   a dica que acompanha o dedo ou o mouse -- e as setas do teclado.

   TEXTO DE FORA ENTRA COMO TEXTO. Nome de brinquedo, de cliente e de cupom
   vem do banco: tudo vai por textContent, nunca por innerHTML.

   Pode ser carregado mais de uma vez (a navegação suave reaproveita a
   tela): a segunda carga só procura painéis e itens novos.
   ====================================================================== */
(function (window, document) {
  "use strict";

  if (window.LSAnalises) {
    window.LSAnalises.montar(document);
    return;
  }

  var SVG = "http://www.w3.org/2000/svg";
  var NUM = new Intl.NumberFormat("pt-BR");
  var NUM1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  var COMPACTO = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  var REAIS = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  var REAIS0 = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  var REAIS_COMPACTO = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
  var TITULO_UNIDADE = { hora: "por hora", dia: "por dia", semana: "por semana", mes: "por mês" };
  var uid = 0;

  /* ------------------------------------------------------------------
     utilidades
     ------------------------------------------------------------------ */
  function el(tag, classe, texto) {
    var no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined && texto !== null) no.textContent = String(texto);
    return no;
  }

  function sv(tag, atributos) {
    var no = document.createElementNS(SVG, tag);
    Object.keys(atributos || {}).forEach(function (nome) {
      no.setAttribute(nome, atributos[nome]);
    });
    return no;
  }

  function icone(nome) {
    var i = el("i", "bi " + (nome || "bi-dot"));
    i.setAttribute("aria-hidden", "true");
    return i;
  }

  function lerPreferencia(chave, padrao) {
    try {
      var valor = window.localStorage.getItem("lsa:" + chave);
      return valor === null ? padrao : valor;
    } catch (erro) {
      return padrao;
    }
  }

  function gravarPreferencia(chave, valor) {
    try { window.localStorage.setItem("lsa:" + chave, valor); } catch (erro) { /* aba sem armazenamento */ }
  }

  function formatar(valor, formato, modo) {
    if (valor === null || valor === undefined || isNaN(valor)) return "—";
    var absoluto = Math.abs(valor);
    if (formato === "dinheiro") {
      if (modo === "eixo") return absoluto >= 1000 ? REAIS_COMPACTO.format(valor) : REAIS0.format(valor);
      if (modo === "curto" && absoluto >= 100000) return REAIS_COMPACTO.format(valor);
      if (modo === "curto" && absoluto >= 10000) return REAIS0.format(valor);
      return REAIS.format(valor);
    }
    if (modo === "eixo" && absoluto >= 10000) return COMPACTO.format(valor);
    if (modo === "curto" && absoluto >= 1000000) return COMPACTO.format(valor);
    return Number.isInteger(valor) ? NUM.format(valor) : NUM1.format(valor);
  }

  function hojeIso(deslocamento) {
    var data = new Date();
    data.setDate(data.getDate() + (deslocamento || 0));
    var mes = String(data.getMonth() + 1).padStart(2, "0");
    var dia = String(data.getDate()).padStart(2, "0");
    return data.getFullYear() + "-" + mes + "-" + dia;
  }

  function buscar(url, sinal) {
    return window.fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      signal: sinal
    }).then(function (resposta) {
      return resposta.json().catch(function () { return {}; }).then(function (dados) {
        if (!resposta.ok) {
          var erro = new Error(dados.erro || ("O servidor respondeu " + resposta.status + "."));
          erro.status = resposta.status;
          throw erro;
        }
        return dados;
      });
    });
  }

  /* Escala "redonda" do eixo: 0, 25, 50, 75, 100 -- nunca 0, 23, 46. */
  function escala(maximo, inteiro) {
    if (!(maximo > 0)) return { topo: inteiro ? 4 : 1, passo: inteiro ? 1 : 0.25 };
    var bruto = maximo / 4;
    var grandeza = Math.pow(10, Math.floor(Math.log10(bruto)));
    var normal = bruto / grandeza;
    var passo = (normal <= 1 ? 1 : normal <= 2 ? 2 : normal <= 2.5 ? 2.5 : normal <= 5 ? 5 : 10) * grandeza;
    if (inteiro) passo = Math.max(1, Math.ceil(passo));
    return { topo: passo * Math.ceil(maximo / passo), passo: passo };
  }

  function medirTexto(texto) {
    return String(texto).length * 6.4 + 4;
  }

  /* ------------------------------------------------------------------
     a dica (tooltip) de cada gráfico
     ------------------------------------------------------------------ */
  function Dica(tela) {
    this.tela = tela;
    this.no = el("div", "lsa-dica");
    this.no.setAttribute("role", "status");
    this.no.setAttribute("aria-live", "polite");
    tela.appendChild(this.no);
  }

  Dica.prototype.mostrar = function (titulo, linhas, x, y) {
    var no = this.no;
    no.textContent = "";
    no.appendChild(el("span", "lsa-dica-titulo", titulo));
    linhas.forEach(function (linha) {
      var item = el("div", "lsa-dica-linha");
      var chave = el("span", "lsa-chave" + (linha.anterior ? " is-anterior" : ""));
      chave.setAttribute("aria-hidden", "true");
      item.appendChild(chave);
      item.appendChild(el("strong", "", linha.valor));
      item.appendChild(el("span", "", linha.rotulo));
      no.appendChild(item);
    });
    var largura = this.tela.clientWidth;
    var caixa = no.getBoundingClientRect();
    var esquerda = x + 14;
    if (esquerda + caixa.width > largura) esquerda = Math.max(0, x - caixa.width - 14);
    var topo = Math.max(0, y - caixa.height - 10);
    no.style.left = esquerda + "px";
    no.style.top = topo + "px";
    no.classList.add("is-visivel");
  };

  Dica.prototype.esconder = function () {
    this.no.classList.remove("is-visivel");
  };

  /* ------------------------------------------------------------------
     linha + área: a série do período e a do período anterior
     ------------------------------------------------------------------ */
  function desenharLinha(tela, rotulos, metrica, unidade) {
    tela.textContent = "";
    var largura = Math.max(260, tela.clientWidth || 600);
    var altura = largura < 480 ? 196 : 236;
    var serie = metrica.serie || [];
    var anterior = metrica.serie_anterior || null;
    var n = serie.length;
    var inteiro = metrica.formato !== "dinheiro" && !metrica.razao;
    var valores = serie.concat(anterior || []).filter(function (v) { return v !== null && v !== undefined; });
    var esc = escala(Math.max.apply(null, valores.concat([0])), inteiro);
    var ticks = [];
    for (var t = 0; t <= esc.topo + 1e-9; t += esc.passo) ticks.push(t);
    var margemEsq = Math.max.apply(null, ticks.map(function (v) { return medirTexto(formatar(v, metrica.formato, "eixo")); })) + 6;
    var m = { esq: margemEsq, dir: 12, topo: 12, base: 26 };
    var lp = largura - m.esq - m.dir;
    var ap = altura - m.topo - m.base;
    var x = function (i) { return m.esq + (n <= 1 ? lp / 2 : (i * lp) / (n - 1)); };
    var y = function (v) { return m.topo + ap - (v / esc.topo) * ap; };

    uid += 1;
    var idDegrade = "lsaDegrade" + uid;
    var svg = sv("svg", { width: largura, height: altura, viewBox: "0 0 " + largura + " " + altura, role: "img", tabindex: "0" });
    var defs = sv("defs");
    var degrade = sv("linearGradient", { id: idDegrade, x1: "0", x2: "0", y1: "0", y2: "1" });
    [["0%", ".12"], ["100%", "0"]].forEach(function (par) {
      var parada = sv("stop", { offset: par[0] });
      parada.style.stopColor = "var(--lsa-serie)";
      parada.style.stopOpacity = par[1];
      degrade.appendChild(parada);
    });
    defs.appendChild(degrade);
    svg.appendChild(defs);

    ticks.forEach(function (valor) {
      var py = Math.round(y(valor)) + 0.5;
      svg.appendChild(sv("line", { x1: m.esq, x2: largura - m.dir, y1: py, y2: py, "class": valor === 0 ? "lsa-svg-base" : "lsa-svg-grade" }));
      var rotulo = sv("text", { x: m.esq - 8, y: py + 4, "text-anchor": "end", "class": "lsa-svg-texto" });
      rotulo.textContent = formatar(valor, metrica.formato, "eixo");
      svg.appendChild(rotulo);
    });

    var cabem = Math.max(2, Math.floor(lp / 58));
    var passo = Math.max(1, Math.ceil(n / cabem));
    rotulos.forEach(function (rotulo, i) {
      if ((n - 1 - i) % passo !== 0) return;
      var px = x(i);
      var ancora = "middle";
      if (px - m.esq < 18) ancora = "start";
      if (largura - m.dir - px < 18) ancora = "end";
      var texto = sv("text", { x: px, y: altura - 8, "text-anchor": ancora, "class": "lsa-svg-texto" });
      texto.textContent = rotulo.curto;
      svg.appendChild(texto);
    });

    function caminho(lista) {
      var partes = [];
      var aberto = false;
      lista.forEach(function (v, i) {
        if (v === null || v === undefined) { aberto = false; return; }
        partes.push((aberto ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1));
        aberto = true;
      });
      return partes.join(" ");
    }

    if (anterior) {
      svg.appendChild(sv("path", { d: caminho(anterior), "class": "lsa-svg-anterior" }));
    }

    var ultimo = -1;
    serie.forEach(function (v, i) { if (v !== null && v !== undefined) ultimo = i; });
    var primeiro = serie.findIndex(function (v) { return v !== null && v !== undefined; });
    if (ultimo >= 0 && serie.slice(primeiro, ultimo + 1).every(function (v) { return v !== null; })) {
      var area = caminho(serie) + " L" + x(ultimo).toFixed(1) + " " + y(0).toFixed(1) + " L" + x(primeiro).toFixed(1) + " " + y(0).toFixed(1) + " Z";
      var preenchida = sv("path", { d: area, fill: "url(#" + idDegrade + ")", stroke: "none" });
      svg.appendChild(preenchida);
    }
    svg.appendChild(sv("path", { d: caminho(serie), "class": "lsa-svg-serie" }));
    if (ultimo >= 0) {
      svg.appendChild(sv("circle", { cx: x(ultimo), cy: y(serie[ultimo]), r: 4, "class": "lsa-svg-ponto" }));
    }

    /* a mira: acha o balde mais perto do dedo, não exige acertar a linha de 2px */
    var mira = sv("line", { x1: 0, x2: 0, y1: m.topo, y2: m.topo + ap, "class": "lsa-svg-mira", visibility: "hidden" });
    var pontoAtual = sv("circle", { r: 5, "class": "lsa-svg-ponto", visibility: "hidden" });
    var pontoAnterior = sv("circle", { r: 4, "class": "lsa-svg-ponto-anterior", visibility: "hidden" });
    svg.appendChild(mira);
    svg.appendChild(pontoAnterior);
    svg.appendChild(pontoAtual);
    var alvo = sv("rect", { x: m.esq - 10, y: 0, width: lp + 20, height: altura, "class": "lsa-svg-alvo" });
    svg.appendChild(alvo);

    var total = metrica.total;
    svg.setAttribute("aria-label", metrica.rotulo + " " + (TITULO_UNIDADE[unidade] || "") + ": total " +
      formatar(total, metrica.formato) + (metrica.anterior !== null && metrica.anterior !== undefined ? ", período anterior " + formatar(metrica.anterior, metrica.formato) : "") +
      ". Use as setas para ler cada ponto; a tabela abaixo traz todos os valores.");
    tela.appendChild(svg);
    var dica = new Dica(tela);
    var indice = -1;

    function mostrar(i) {
      if (i < 0 || i >= n) return;
      indice = i;
      var px = x(i);
      mira.setAttribute("x1", px);
      mira.setAttribute("x2", px);
      mira.setAttribute("visibility", "visible");
      var linhas = [];
      var atual = serie[i];
      if (atual !== null && atual !== undefined) {
        pontoAtual.setAttribute("cx", px);
        pontoAtual.setAttribute("cy", y(atual));
        pontoAtual.setAttribute("visibility", "visible");
        linhas.push({ valor: formatar(atual, metrica.formato), rotulo: "este período" });
      } else {
        pontoAtual.setAttribute("visibility", "hidden");
        linhas.push({ valor: "—", rotulo: rotulos[i] && rotulos[i].futuro ? "ainda não chegou" : "este período" });
      }
      if (anterior && anterior[i] !== null && anterior[i] !== undefined) {
        pontoAnterior.setAttribute("cx", px);
        pontoAnterior.setAttribute("cy", y(anterior[i]));
        pontoAnterior.setAttribute("visibility", "visible");
        linhas.push({ valor: formatar(anterior[i], metrica.formato), rotulo: "período anterior", anterior: true });
      } else {
        pontoAnterior.setAttribute("visibility", "hidden");
      }
      var referencia = atual !== null && atual !== undefined ? y(atual) : m.topo + ap / 2;
      dica.mostrar(rotulos[i] ? rotulos[i].longo : "", linhas, px, referencia);
    }

    function esconder() {
      mira.setAttribute("visibility", "hidden");
      pontoAtual.setAttribute("visibility", "hidden");
      pontoAnterior.setAttribute("visibility", "hidden");
      dica.esconder();
    }

    function pelaPosicao(evento) {
      var caixa = svg.getBoundingClientRect();
      var px = (evento.clientX - caixa.left) * (largura / caixa.width);
      var i = n <= 1 ? 0 : Math.round(((px - m.esq) / lp) * (n - 1));
      mostrar(Math.max(0, Math.min(n - 1, i)));
    }

    alvo.addEventListener("pointermove", pelaPosicao);
    alvo.addEventListener("pointerdown", pelaPosicao);
    alvo.addEventListener("pointerleave", esconder);
    svg.addEventListener("keydown", function (evento) {
      if (evento.key === "ArrowRight" || evento.key === "ArrowLeft") {
        evento.preventDefault();
        var proximo = indice < 0 ? (ultimo >= 0 ? ultimo : n - 1) : indice + (evento.key === "ArrowRight" ? 1 : -1);
        mostrar(Math.max(0, Math.min(n - 1, proximo)));
      } else if (evento.key === "Home" || evento.key === "End") {
        evento.preventDefault();
        mostrar(evento.key === "Home" ? 0 : (ultimo >= 0 ? ultimo : n - 1));
      } else if (evento.key === "Escape") {
        esconder();
      }
    });
    svg.addEventListener("focus", function () { mostrar(indice >= 0 ? indice : (ultimo >= 0 ? ultimo : 0)); });
    svg.addEventListener("blur", esconder);
  }

  /* ------------------------------------------------------------------
     colunas: o dia da semana
     ------------------------------------------------------------------ */
  function desenharColunas(tela, nomes, valores, metrica) {
    tela.textContent = "";
    var largura = Math.max(240, tela.clientWidth || 400);
    var altura = 170;
    var inteiro = metrica.formato !== "dinheiro";
    var maior = Math.max.apply(null, valores.concat([0]));
    var esc = escala(maior, inteiro);
    var ticks = [];
    for (var t = 0; t <= esc.topo + 1e-9; t += esc.passo) ticks.push(t);
    var margemEsq = Math.max.apply(null, ticks.map(function (v) { return medirTexto(formatar(v, metrica.formato, "eixo")); })) + 6;
    var m = { esq: margemEsq, dir: 6, topo: 18, base: 24 };
    var lp = largura - m.esq - m.dir;
    var ap = altura - m.topo - m.base;
    var faixa = lp / valores.length;
    var grossura = Math.min(24, Math.max(10, faixa * 0.58));
    var y = function (v) { return m.topo + ap - (v / esc.topo) * ap; };
    var svg = sv("svg", { width: largura, height: altura, viewBox: "0 0 " + largura + " " + altura, role: "img", tabindex: "0" });

    ticks.forEach(function (valor) {
      var py = Math.round(y(valor)) + 0.5;
      svg.appendChild(sv("line", { x1: m.esq, x2: largura - m.dir, y1: py, y2: py, "class": valor === 0 ? "lsa-svg-base" : "lsa-svg-grade" }));
      var rotulo = sv("text", { x: m.esq - 8, y: py + 4, "text-anchor": "end", "class": "lsa-svg-texto" });
      rotulo.textContent = formatar(valor, metrica.formato, "eixo");
      svg.appendChild(rotulo);
    });

    var barras = [];
    var melhor = valores.indexOf(maior);
    valores.forEach(function (valor, i) {
      var cx = m.esq + faixa * i + faixa / 2;
      var topo = y(valor);
      var base = y(0);
      var alturaBarra = Math.max(0, base - topo);
      var raio = Math.min(4, alturaBarra, grossura / 2);
      var esq = cx - grossura / 2;
      var dir = cx + grossura / 2;
      var d = alturaBarra > 0
        ? "M" + esq + " " + base + " L" + esq + " " + (topo + raio) + " Q" + esq + " " + topo + " " + (esq + raio) + " " + topo +
          " L" + (dir - raio) + " " + topo + " Q" + dir + " " + topo + " " + dir + " " + (topo + raio) + " L" + dir + " " + base + " Z"
        : "M" + esq + " " + (base - 1) + " L" + dir + " " + (base - 1);
      var barra = sv("path", { d: d, "class": "lsa-svg-barra" });
      if (alturaBarra <= 0) { barra.setAttribute("stroke", "currentColor"); barra.style.stroke = "var(--lsa-grade)"; }
      svg.appendChild(barra);
      barras.push(barra);
      var nome = sv("text", { x: cx, y: altura - 7, "text-anchor": "middle", "class": "lsa-svg-texto" });
      nome.textContent = nomes[i].slice(0, 3);
      svg.appendChild(nome);
      if (i === melhor && maior > 0) {
        var valorTexto = sv("text", { x: cx, y: topo - 6, "text-anchor": "middle", "class": "lsa-svg-valor" });
        valorTexto.textContent = formatar(valor, metrica.formato, "curto");
        svg.appendChild(valorTexto);
      }
    });

    tela.appendChild(svg);
    var dica = new Dica(tela);
    var indice = -1;
    function mostrar(i) {
      indice = i;
      barras.forEach(function (barra, j) { barra.classList.toggle("is-apagada", j !== i); });
      var cx = m.esq + faixa * i + faixa / 2;
      dica.mostrar(nomes[i], [{ valor: formatar(valores[i], metrica.formato), rotulo: metrica.rotulo.toLowerCase() }], cx, y(valores[i]));
    }
    function esconder() {
      barras.forEach(function (barra) { barra.classList.remove("is-apagada"); });
      dica.esconder();
    }
    valores.forEach(function (valor, i) {
      var alvo = sv("rect", { x: m.esq + faixa * i, y: 0, width: faixa, height: altura, "class": "lsa-svg-alvo" });
      alvo.addEventListener("pointerenter", function () { mostrar(i); });
      alvo.addEventListener("pointerdown", function () { mostrar(i); });
      svg.appendChild(alvo);
    });
    svg.addEventListener("pointerleave", esconder);
    svg.addEventListener("keydown", function (evento) {
      if (evento.key === "ArrowRight" || evento.key === "ArrowLeft") {
        evento.preventDefault();
        var proximo = indice < 0 ? 0 : indice + (evento.key === "ArrowRight" ? 1 : -1);
        mostrar(Math.max(0, Math.min(valores.length - 1, proximo)));
      } else if (evento.key === "Escape") {
        esconder();
      }
    });
    svg.addEventListener("blur", esconder);
    svg.setAttribute("aria-label", metrica.rotulo + " por dia da semana. Melhor dia: " + nomes[melhor] + ", " + formatar(maior, metrica.formato) + ".");
    return melhor;
  }

  /* a faísca (sparkline) de cada indicador: cinza, o ponto de agora no acento */
  function faisca(metrica) {
    var serie = (metrica.serie || []).filter(function (v) { return v !== null && v !== undefined; });
    if (serie.length < 2) return null;
    var maior = Math.max.apply(null, serie.concat([0]));
    var menor = Math.min.apply(null, serie.concat([0]));
    var faixa = maior - menor || 1;
    var svg = sv("svg", { "class": "lsa-faisca", viewBox: "0 0 100 26", preserveAspectRatio: "none", "aria-hidden": "true", focusable: "false" });
    var pontos = serie.map(function (v, i) {
      return ((i / (serie.length - 1)) * 100).toFixed(2) + "," + (23 - ((v - menor) / faixa) * 20).toFixed(2);
    });
    var linha = sv("polyline", { points: pontos.join(" "), fill: "none", "stroke-width": "1.5", "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" });
    linha.style.stroke = "var(--lsa-anterior)";
    svg.appendChild(linha);
    return svg;
  }

  function classeDaVariacao(metrica) {
    if (metrica.direcao === "sobe" || metrica.direcao === "novo") {
      return metrica.subir_e_bom === true ? "is-bom" : (metrica.subir_e_bom === false ? "is-ruim" : "");
    }
    if (metrica.direcao === "desce") {
      return metrica.subir_e_bom === true ? "is-ruim" : (metrica.subir_e_bom === false ? "is-bom" : "");
    }
    return "";
  }

  function variacao(metrica) {
    var caixa = el("span", "lsa-variacao " + classeDaVariacao(metrica));
    var falado;
    if (metrica.sem_dados) {
      caixa.appendChild(icone("bi-hourglass"));
      caixa.appendChild(document.createTextNode("sem dados ainda"));
      return caixa;
    }
    if (metrica.direcao === "sem_base") {
      caixa.appendChild(icone("bi-info-circle"));
      caixa.appendChild(document.createTextNode("sem base anterior"));
      if (metrica.desde) caixa.appendChild(el("small", "", "· desde " + metrica.desde.split("-").reverse().slice(0, 2).join("/")));
      return caixa;
    }
    var anterior = formatar(metrica.anterior, metrica.formato, "curto");
    if (metrica.direcao === "novo") {
      caixa.appendChild(icone("bi-arrow-up-right"));
      caixa.appendChild(document.createTextNode("novo"));
      falado = "novo: não houve no período anterior";
    } else if (metrica.direcao === "igual") {
      caixa.appendChild(icone("bi-dash-lg"));
      caixa.appendChild(document.createTextNode("estável"));
      falado = "estável em relação ao período anterior";
    } else {
      var sobe = metrica.direcao === "sobe";
      caixa.appendChild(icone(sobe ? "bi-arrow-up-right" : "bi-arrow-down-right"));
      caixa.appendChild(document.createTextNode(NUM1.format(Math.abs(metrica.variacao)) + "%"));
      falado = (sobe ? "subiu " : "caiu ") + NUM1.format(Math.abs(metrica.variacao)) + "% em relação ao período anterior";
    }
    caixa.appendChild(el("small", "", "· antes " + anterior));
    caixa.setAttribute("aria-label", falado + ", que teve " + anterior);
    return caixa;
  }

  /* ------------------------------------------------------------------
     uma análise: período, indicadores, gráficos, ranking
     ------------------------------------------------------------------ */
  function Analise(raiz, opcoes) {
    this.raiz = raiz;
    this.opcoes = opcoes;
    this.corpo = raiz.querySelector("[data-lsa-corpo]");
    this.descricao = raiz.querySelector("[data-lsa-descricao]");
    this.destaques = raiz.querySelector("[data-lsa-destaques]");
    this.periodos = raiz.querySelector("[data-lsa-periodos]");
    this.dias = raiz.querySelector("[data-lsa-dias]");
    this.de = raiz.querySelector("[data-lsa-de]");
    this.ate = raiz.querySelector("[data-lsa-ate]");
    this.nome = "lsa-m-" + (uid += 1);
    this.metrica = null;
    this.dados = null;
    this.pedido = null;
    this.ligar();
    this.escolherPeriodo(opcoes.periodo || "mes", opcoes.de, opcoes.ate);
  }

  Analise.prototype.ligar = function () {
    var eu = this;
    if (this.periodos) {
      this.periodos.addEventListener("change", function (evento) {
        if (!evento.target.matches("input[type=radio]")) return;
        eu.escolherPeriodo(evento.target.value);
        if (eu.opcoes.aoMudarPeriodo) eu.opcoes.aoMudarPeriodo(eu.periodo);
      });
    }
    [this.de, this.ate].forEach(function (campo) {
      if (campo) campo.addEventListener("change", function () { eu.carregar(); });
    });
    if (window.ResizeObserver && this.corpo) {
      var largura = 0;
      var espera = null;
      this.observador = new window.ResizeObserver(function (entradas) {
        var nova = Math.round(entradas[0].contentRect.width);
        if (!nova || Math.abs(nova - largura) < 8) return;
        largura = nova;
        window.clearTimeout(espera);
        espera = window.setTimeout(function () { eu.desenharGraficos(); }, 120);
      });
      this.observador.observe(this.corpo);
    }
  };

  Analise.prototype.escolherPeriodo = function (periodo, de, ate) {
    this.periodo = periodo;
    if (this.periodos) {
      var radio = this.periodos.querySelector('input[value="' + periodo + '"]');
      if (radio) radio.checked = true;
    }
    if (this.dias) {
      this.dias.hidden = periodo !== "dias";
      if (periodo === "dias") {
        if (de) this.de.value = de;
        if (ate) this.ate.value = ate;
        if (!this.de.value) this.de.value = hojeIso(-29);
        if (!this.ate.value) this.ate.value = hojeIso(0);
        this.de.max = this.ate.max = hojeIso(0);
      }
    }
    this.carregar();
  };

  Analise.prototype.url = function () {
    var parametros = new URLSearchParams();
    parametros.set("periodo", this.periodo);
    if (this.periodo === "dias") {
      parametros.set("de", this.de.value);
      parametros.set("ate", this.ate.value);
    }
    if (this.opcoes.id) parametros.set("id", this.opcoes.id);
    return this.opcoes.url + "?" + parametros.toString();
  };

  Analise.prototype.carregar = function () {
    var eu = this;
    if (this.periodo === "dias" && (!this.de.value || !this.ate.value)) return;
    if (this.pedido) this.pedido.abort();
    this.pedido = window.AbortController ? new window.AbortController() : null;
    /* recarregar mantém o desenho anterior, apagado: sem pulo, sem esqueleto */
    if (this.dados) {
      this.corpo.classList.add("is-carregando");
    } else {
      this.corpo.textContent = "";
      var estado = el("div", "lsa-estado");
      var gira = el("span", "lsa-girando");
      gira.setAttribute("aria-hidden", "true");
      estado.appendChild(gira);
      estado.appendChild(el("span", "", "Carregando os números…"));
      this.corpo.appendChild(estado);
    }
    this.corpo.setAttribute("aria-busy", "true");
    buscar(this.url(), this.pedido && this.pedido.signal).then(function (dados) {
      eu.dados = dados;
      eu.desenhar();
    }).catch(function (erro) {
      if (erro && erro.name === "AbortError") return;
      eu.erro(erro && erro.message);
    }).then(function () {
      eu.corpo.classList.remove("is-carregando");
      eu.corpo.removeAttribute("aria-busy");
    });
  };

  Analise.prototype.erro = function (mensagem) {
    var eu = this;
    this.corpo.textContent = "";
    var caixa = el("div", "lsa-estado is-erro");
    caixa.appendChild(icone("bi-exclamation-triangle"));
    caixa.appendChild(el("span", "", (mensagem || "Não foi possível carregar os números.") + " "));
    var tentar = el("button", "lsa-tentar", "Tentar de novo");
    tentar.type = "button";
    tentar.addEventListener("click", function () { eu.carregar(); });
    caixa.appendChild(tentar);
    this.corpo.appendChild(caixa);
    if (this.descricao) this.descricao.textContent = "";
  };

  Analise.prototype.desenhar = function () {
    var dados = this.dados;
    var eu = this;
    if (this.descricao) this.descricao.textContent = dados.periodo.descricao;
    this.desenharDestaques(dados.destaques || []);
    var metricas = dados.metricas || [];
    if (!this.metrica || !metricas.some(function (m) { return m.codigo === eu.metrica; })) {
      var principal = metricas.find(function (m) { return m.codigo === dados.principal && !m.sem_dados; });
      var primeiraComDados = metricas.find(function (m) { return !m.sem_dados; });
      this.metrica = (principal || primeiraComDados || metricas[0] || {}).codigo;
    }

    this.corpo.textContent = "";
    var grade = el("div", "lsa-indicadores");
    grade.setAttribute("role", "radiogroup");
    grade.setAttribute("aria-label", "Escolha a métrica dos gráficos");
    metricas.forEach(function (metrica) {
      var rotulo = el("label", "lsa-indicador");
      var radio = el("input");
      radio.type = "radio";
      radio.name = eu.nome;
      radio.value = metrica.codigo;
      radio.checked = metrica.codigo === eu.metrica;
      if (metrica.ajuda) rotulo.title = metrica.ajuda;
      rotulo.appendChild(radio);
      var topo = el("span", "lsa-indicador-rotulo");
      topo.appendChild(icone(metrica.icone));
      topo.appendChild(el("span", "", metrica.rotulo));
      rotulo.appendChild(topo);
      var valor = metrica.sem_dados
        ? el("span", "lsa-indicador-valor is-vazio", "sem dados ainda")
        : el("span", "lsa-indicador-valor", formatar(metrica.total, metrica.formato, "curto"));
      rotulo.appendChild(valor);
      if (!metrica.sem_dados) rotulo.appendChild(variacao(metrica));
      var linha = !metrica.sem_dados && faisca(metrica);
      if (linha) rotulo.appendChild(linha);
      grade.appendChild(rotulo);
    });
    grade.addEventListener("change", function (evento) {
      if (!evento.target.matches("input[type=radio]")) return;
      eu.metrica = evento.target.value;
      eu.desenharGraficos();
    });
    this.corpo.appendChild(grade);

    if (metricas.length > 4) {
      var mais = el("label", "lsa-mais-rotulo");
      var marca = el("input", "lsa-oculto");
      marca.type = "checkbox";
      var texto = el("span", "", "Mais métricas (+" + (metricas.length - 4) + ")");
      mais.appendChild(marca);
      mais.appendChild(icone("bi-chevron-down"));
      mais.appendChild(texto);
      marca.addEventListener("change", function () {
        grade.classList.toggle("is-todos", marca.checked);
        texto.textContent = marca.checked ? "Menos métricas" : "Mais métricas (+" + (metricas.length - 4) + ")";
      });
      this.corpo.appendChild(mais);
    }

    this.graficos = el("div", "lsa-graficos");
    this.corpo.appendChild(this.graficos);
    this.desenharGraficos();

    if (dados.avisos && dados.avisos.length) {
      var avisos = el("ul", "lsa-avisos");
      dados.avisos.forEach(function (aviso) {
        var item = el("li");
        item.appendChild(icone("bi-info-circle"));
        item.appendChild(el("span", "", aviso));
        avisos.appendChild(item);
      });
      this.corpo.appendChild(avisos);
    }
  };

  Analise.prototype.desenharDestaques = function (lista) {
    if (!this.destaques) return;
    this.destaques.textContent = "";
    var eu = this;
    lista.forEach(function (destaque) {
      var item = el("span", "lsa-destaque" + (destaque.tom === "bom" ? " is-bom" : ""));
      if (destaque.codigo === "online" && destaque.valor > 0) {
        var ponto = el("span", "lsa-ponto-vivo");
        ponto.setAttribute("aria-hidden", "true");
        item.appendChild(ponto);
      } else {
        item.appendChild(icone(destaque.icone));
      }
      item.appendChild(el("strong", "", formatar(destaque.valor, "inteiro")));
      item.appendChild(el("span", "", destaque.rotulo));
      eu.destaques.appendChild(item);
    });
  };

  Analise.prototype.desenharGraficos = function () {
    var dados = this.dados;
    var grade = this.graficos;
    if (!dados || !grade) return;
    var eu = this;
    var metrica = (dados.metricas || []).find(function (m) { return m.codigo === eu.metrica; });
    grade.textContent = "";
    if (!metrica) return;
    var unidade = dados.periodo.unidade;
    var temSemana = !!(metrica.semana && !metrica.sem_dados);
    var temRanking = !!this.opcoes.ranking && metrica.tem_ranking !== false;
    grade.className = "lsa-graficos" + (temRanking ? "" : " sem-ranking") + (temSemana ? "" : " sem-semana");

    /* linha */
    var blocoLinha = el("section", "lsa-bloco lsa-bloco-linha");
    var topo = el("div", "lsa-bloco-topo");
    topo.appendChild(el("h3", "lsa-bloco-titulo", metrica.rotulo + " " + (TITULO_UNIDADE[unidade] || "")));
    var legenda = el("ul", "lsa-legenda");
    [["este período", ""], ["período anterior", " is-anterior"]].forEach(function (par, i) {
      if (i === 1 && !metrica.serie_anterior) return;
      var item = el("li");
      var chave = el("span", "lsa-chave" + par[1]);
      chave.setAttribute("aria-hidden", "true");
      item.appendChild(chave);
      item.appendChild(document.createTextNode(par[0]));
      legenda.appendChild(item);
    });
    topo.appendChild(legenda);
    blocoLinha.appendChild(topo);
    var telaLinha = el("div", "lsa-tela");
    blocoLinha.appendChild(telaLinha);
    grade.appendChild(blocoLinha);
    if (metrica.sem_dados) {
      var vazio = el("div", "lsa-sem-serie");
      vazio.appendChild(icone("bi-hourglass"));
      vazio.appendChild(el("span", "", "Sem dados ainda para " + metrica.rotulo.toLowerCase() + "."));
      telaLinha.appendChild(vazio);
    } else if (!metrica.serie) {
      var semSerie = el("div", "lsa-sem-serie");
      semSerie.appendChild(icone("bi-info-circle"));
      semSerie.appendChild(el("span", "", "Esta métrica conta pessoas distintas: hora a hora não existe. Total do período: " + formatar(metrica.total, metrica.formato) + "."));
      telaLinha.appendChild(semSerie);
    } else {
      desenharLinha(telaLinha, dados.rotulos, metrica, unidade);
      blocoLinha.appendChild(this.tabela(dados.rotulos, metrica));
    }

    /* colunas por dia da semana */
    if (temSemana) {
      var blocoSemana = el("section", "lsa-bloco lsa-bloco-semana");
      var topoSemana = el("div", "lsa-bloco-topo");
      topoSemana.appendChild(el("h3", "lsa-bloco-titulo", "Por dia da semana"));
      var sub = el("p", "lsa-bloco-sub");
      topoSemana.appendChild(sub);
      blocoSemana.appendChild(topoSemana);
      var telaSemana = el("div", "lsa-tela");
      blocoSemana.appendChild(telaSemana);
      grade.appendChild(blocoSemana);
      var melhor = desenharColunas(telaSemana, dados.dias_da_semana, metrica.semana, metrica);
      var maior = Math.max.apply(null, metrica.semana);
      sub.textContent = maior > 0 ? "melhor dia: " + dados.dias_da_semana[melhor] : "nada neste período";
    }

    /* ranking */
    if (temRanking) {
      var blocoRanking = el("section", "lsa-bloco lsa-bloco-ranking");
      var topoRanking = el("div", "lsa-bloco-topo");
      topoRanking.appendChild(el("h3", "lsa-bloco-titulo", "Quem mais rendeu"));
      topoRanking.appendChild(el("p", "lsa-bloco-sub", "em " + metrica.rotulo.toLowerCase()));
      blocoRanking.appendChild(topoRanking);
      var lista = metrica.ranking || [];
      if (!lista.length) {
        var nada = el("div", "lsa-sem-serie");
        nada.appendChild(icone(metrica.sem_dados ? "bi-hourglass" : "bi-trophy"));
        nada.appendChild(el("span", "", metrica.sem_dados ? "Sem dados ainda." : "Ninguém pontuou neste período."));
        blocoRanking.appendChild(nada);
      } else {
        var topoValor = lista[0].valor || 1;
        var ol = el("ol", "lsa-ranking");
        lista.forEach(function (item, i) {
          var li = el("li", "lsa-ranking-item");
          li.appendChild(el("span", "lsa-ranking-pos", i + 1));
          var nome = el("span", "lsa-ranking-nome");
          var tipoItem = item.tipo || dados.tipo;
          if (item.id !== null && item.id !== undefined && Ficha.temItem(tipoItem)) {
            var link = el("a", "", item.nome);
            link.href = "#";
            link.title = "Abrir " + item.nome;
            link.addEventListener("click", function (evento) {
              evento.preventDefault();
              Ficha.abrir(tipoItem, item.id, { aba: "graficos", periodo: eu.periodo, origem: link });
            });
            nome.appendChild(link);
          } else {
            nome.textContent = item.nome;
          }
          li.appendChild(nome);
          li.appendChild(el("span", "lsa-ranking-valor", formatar(item.valor, metrica.formato, "curto")));
          var trilho = el("span", "lsa-ranking-trilho");
          trilho.setAttribute("aria-hidden", "true");
          var barra = el("span", "lsa-ranking-barra");
          barra.style.width = Math.max(2, (item.valor / topoValor) * 100) + "%";
          trilho.appendChild(barra);
          li.appendChild(trilho);
          ol.appendChild(li);
        });
        blocoRanking.appendChild(ol);
      }
      grade.appendChild(blocoRanking);
    }
  };

  /* a tabela: o gêmeo acessível de todo gráfico */
  Analise.prototype.tabela = function (rotulos, metrica) {
    var detalhes = el("details", "lsa-tabela");
    var resumo = el("summary");
    resumo.appendChild(icone("bi-table"));
    resumo.appendChild(document.createTextNode("Ver os números em tabela"));
    detalhes.appendChild(resumo);
    var rolagem = el("div", "lsa-tabela-rolagem");
    var tabela = el("table");
    var cabeca = el("thead");
    var linha = el("tr");
    ["Quando", "Este período"].concat(metrica.serie_anterior ? ["Período anterior"] : []).forEach(function (texto) {
      var th = el("th", "", texto);
      th.scope = "col";
      linha.appendChild(th);
    });
    cabeca.appendChild(linha);
    tabela.appendChild(cabeca);
    var corpo = el("tbody");
    rotulos.forEach(function (rotulo, i) {
      if (rotulo.futuro) return;
      var tr = el("tr");
      tr.appendChild(el("td", "", rotulo.longo));
      tr.appendChild(el("td", "", formatar(metrica.serie[i], metrica.formato)));
      if (metrica.serie_anterior) tr.appendChild(el("td", "", formatar(metrica.serie_anterior[i], metrica.formato)));
      corpo.appendChild(tr);
    });
    tabela.appendChild(corpo);
    rolagem.appendChild(tabela);
    detalhes.appendChild(rolagem);
    return detalhes;
  };

  /* ------------------------------------------------------------------
     o painel do topo da tela
     ------------------------------------------------------------------ */
  var paineis = [];

  function montarPainel(raiz) {
    if (raiz.dataset.lsaPronto) return;
    raiz.dataset.lsaPronto = "1";
    var tipo = raiz.dataset.lsaTipo;
    var recolher = raiz.querySelector("[data-lsa-recolher]");
    var textoRecolher = raiz.querySelector("[data-lsa-recolher-texto]");
    var analise = null;

    function aplicarRecolhido(recolhido) {
      raiz.dataset.lsaRecolhido = recolhido ? "1" : "0";
      if (textoRecolher) textoRecolher.textContent = recolhido ? "Mostrar gráficos" : "Recolher";
      if (recolher) recolher.checked = recolhido;
      if (!recolhido && !analise) iniciar();
    }

    function iniciar() {
      analise = new Analise(raiz, {
        url: raiz.dataset.lsaUrl,
        periodo: lerPreferencia("periodo:" + tipo, "mes"),
        ranking: true,
        aoMudarPeriodo: function (periodo) { gravarPreferencia("periodo:" + tipo, periodo); }
      });
      paineis.push({ tipo: tipo, analise: analise });
    }

    if (recolher) {
      recolher.addEventListener("change", function () {
        aplicarRecolhido(recolher.checked);
        gravarPreferencia("recolhido:" + tipo, recolher.checked ? "1" : "0");
      });
    }
    aplicarRecolhido(lerPreferencia("recolhido:" + tipo, "0") === "1");
  }

  function periodoDaTela(tipo) {
    var achado = paineis.find(function (p) { return p.tipo === tipo; }) || paineis[0];
    if (achado) return { periodo: achado.analise.periodo, de: achado.analise.de && achado.analise.de.value, ate: achado.analise.ate && achado.analise.ate.value };
    return { periodo: lerPreferencia("periodo:" + tipo, "mes") };
  }

  /* ------------------------------------------------------------------
     a ficha (modal de detalhes)
     ------------------------------------------------------------------ */
  var Ficha = {
    dialogo: null,
    pilha: [],
    atual: null,
    pedido: null,
    analise: null,

    temItem: function (tipo) {
      return ["brinquedo", "peca", "promocao", "combo", "cupom", "evento", "projeto", "cliente", "pedido", "usuario", "jogo"].indexOf(tipo) !== -1;
    },

    preparar: function () {
      var dialogo = document.querySelector("[data-lsa-ficha]");
      if (!dialogo || dialogo === this.dialogo) return;
      this.dialogo = dialogo;
      var eu = this;
      dialogo.querySelector("[data-lsa-fechar]").addEventListener("click", function () { eu.fechar(); });
      dialogo.addEventListener("click", function (evento) {
        if (evento.target === dialogo) eu.fechar();  /* toque no fundo escuro */
      });
      dialogo.addEventListener("close", function () {
        if (eu.pedido) eu.pedido.abort();
        if (eu.origem && document.contains(eu.origem)) eu.origem.focus({ preventScroll: true });
      });
      dialogo.querySelector("[data-lsa-abas]").addEventListener("change", function (evento) {
        if (evento.target.matches("input[type=radio]")) eu.mostrarAba(evento.target.value);
      });
    },

    abrir: function (tipo, id, opcoes) {
      this.preparar();
      if (!this.dialogo) return;
      opcoes = opcoes || {};
      if (this.dialogo.open && this.atual && !opcoes.voltando) this.pilha.push(this.atual);
      if (!this.dialogo.open) {
        this.pilha = [];
        this.origem = opcoes.origem || document.activeElement;
      }
      this.atual = { tipo: tipo, id: id };
      this.periodo = opcoes.periodo ? { periodo: opcoes.periodo } : periodoDaTela(tipo);
      this.abaPedida = opcoes.aba || "resumo";
      this.ficha = null;
      this.graficosDe = null;
      this.estadoCarregando();
      if (!this.dialogo.open) {
        if (typeof this.dialogo.showModal === "function") this.dialogo.showModal();
        else this.dialogo.setAttribute("open", "");
      }
      this.carregar();
    },

    fechar: function () {
      if (!this.dialogo) return;
      if (typeof this.dialogo.close === "function") this.dialogo.close();
      else this.dialogo.removeAttribute("open");
    },

    url: function (tipo, id, sufixo) {
      var base = this.dialogo.dataset.lsaDetalheUrl.replace("TIPO", encodeURIComponent(tipo)).replace("987654321", encodeURIComponent(id));
      return base + (sufixo || "");
    },

    estadoCarregando: function () {
      var d = this.dialogo;
      d.querySelector("[data-lsa-ficha-titulo]").textContent = "Carregando…";
      d.querySelector("[data-lsa-ficha-sub]").textContent = "";
      d.querySelector("[data-lsa-ficha-selos]").textContent = "";
      d.querySelector("[data-lsa-ficha-olho]").textContent = "Detalhes";
      var capa = d.querySelector("[data-lsa-ficha-capa]");
      capa.textContent = "";
      capa.appendChild(icone("bi-hourglass-split"));
      var resumo = d.querySelector('[data-lsa-parte="resumo"]');
      resumo.textContent = "";
      var estado = el("div", "lsa-estado");
      var gira = el("span", "lsa-girando");
      gira.setAttribute("aria-hidden", "true");
      estado.appendChild(gira);
      estado.appendChild(el("span", "", "Buscando a ficha completa…"));
      resumo.appendChild(estado);
      d.querySelector('[data-lsa-parte="atividade"]').textContent = "";
      d.querySelector('[data-lsa-parte="graficos"] [data-lsa-corpo]').textContent = "";
    },

    carregar: function () {
      var eu = this;
      var atual = this.atual;
      if (this.pedido) this.pedido.abort();
      this.pedido = window.AbortController ? new window.AbortController() : null;
      buscar(this.url(atual.tipo, atual.id), this.pedido && this.pedido.signal).then(function (ficha) {
        if (eu.atual !== atual) return;
        eu.ficha = ficha;
        eu.desenhar(ficha);
      }).catch(function (erro) {
        if (erro && erro.name === "AbortError") return;
        eu.erro(erro && erro.message, erro && erro.status);
      });
    },

    erro: function (mensagem, status) {
      var eu = this;
      var d = this.dialogo;
      d.querySelector("[data-lsa-ficha-titulo]").textContent = status === 403 ? "Sem acesso" : "Não carregou";
      var resumo = d.querySelector('[data-lsa-parte="resumo"]');
      resumo.textContent = "";
      var caixa = el("div", "lsa-estado is-erro");
      caixa.appendChild(icone(status === 403 ? "bi-shield-lock" : "bi-exclamation-triangle"));
      caixa.appendChild(el("span", "", (mensagem || "Não foi possível buscar a ficha.") + " "));
      if (status !== 403 && status !== 404) {
        var tentar = el("button", "lsa-tentar", "Tentar de novo");
        tentar.type = "button";
        tentar.addEventListener("click", function () { eu.estadoCarregando(); eu.carregar(); });
        caixa.appendChild(tentar);
      }
      resumo.appendChild(caixa);
      this.mostrarAba("resumo");
    },

    desenhar: function (ficha) {
      var d = this.dialogo;
      var eu = this;
      d.querySelector("[data-lsa-ficha-olho]").textContent = ficha.tipo_rotulo || "Detalhes";
      d.querySelector("[data-lsa-ficha-titulo]").textContent = ficha.titulo || "";
      d.querySelector("[data-lsa-ficha-sub]").textContent = ficha.subtitulo || "";
      var capa = d.querySelector("[data-lsa-ficha-capa]");
      capa.textContent = "";
      if (ficha.imagem) {
        var img = el("img");
        img.alt = "";
        img.loading = "lazy";
        img.src = ficha.imagem;
        img.addEventListener("error", function () { capa.textContent = ""; capa.appendChild(icone(ficha.icone || "bi-card-text")); });
        capa.appendChild(img);
      } else {
        capa.appendChild(icone(ficha.icone || "bi-card-text"));
      }
      var selos = d.querySelector("[data-lsa-ficha-selos]");
      selos.textContent = "";
      if (this.pilha.length) {
        var voltar = el("button", "lsa-voltar");
        voltar.type = "button";
        voltar.appendChild(icone("bi-arrow-left"));
        voltar.appendChild(document.createTextNode(" Voltar"));
        voltar.addEventListener("click", function () {
          var anterior = eu.pilha.pop();
          if (anterior) eu.abrir(anterior.tipo, anterior.id, { voltando: true });
        });
        selos.appendChild(voltar);
      }
      (ficha.selos || []).forEach(function (s) {
        var item = el("span", "lsa-selo" + (s.tom && s.tom !== "neutro" ? " is-" + s.tom : ""));
        item.appendChild(icone(s.icone));
        item.appendChild(document.createTextNode(s.texto));
        selos.appendChild(item);
      });

      this.desenharResumo(ficha);
      this.desenharAtividade(ficha.atividade, false);
      var abaGraficos = d.querySelector("[data-lsa-aba-graficos]");
      abaGraficos.hidden = !ficha.tem_graficos;
      var aba = this.abaPedida === "graficos" && !ficha.tem_graficos ? "resumo" : this.abaPedida;
      var radio = d.querySelector('[data-lsa-abas] input[value="' + aba + '"]');
      if (radio) radio.checked = true;
      this.mostrarAba(aba);
    },

    mostrarAba: function (aba) {
      var d = this.dialogo;
      d.querySelectorAll("[data-lsa-parte]").forEach(function (parte) {
        parte.hidden = parte.dataset.lsaParte !== aba;
      });
      var radio = d.querySelector('[data-lsa-abas] input[value="' + aba + '"]');
      if (radio && !radio.checked) radio.checked = true;
      d.querySelector("[data-lsa-ficha-corpo]").scrollTop = 0;
      if (aba === "graficos" && this.ficha && this.graficosDe !== this.atual) {
        /* UMA análise para o modal inteiro, reapontada a cada objeto: criar
           outra a cada abertura deixaria ouvintes antigos no mesmo seletor
           de período, e uma troca de período carregaria dois objetos. */
        var atual = this.atual;
        this.graficosDe = atual;
        var opcoesAnalise = {
          url: d.dataset.lsaAnaliseUrl.replace("TIPO", encodeURIComponent(atual.tipo)),
          id: atual.id,
          periodo: this.periodo.periodo,
          de: this.periodo.de,
          ate: this.periodo.ate,
          ranking: false
        };
        if (!this.analise) {
          this.analise = new Analise(d.querySelector('[data-lsa-parte="graficos"]'), opcoesAnalise);
        } else {
          this.analise.opcoes = opcoesAnalise;
          this.analise.dados = null;
          this.analise.metrica = null;
          this.analise.escolherPeriodo(opcoesAnalise.periodo, opcoesAnalise.de, opcoesAnalise.ate);
        }
      }
    },

    desenharResumo: function (ficha) {
      var eu = this;
      var resumo = this.dialogo.querySelector('[data-lsa-parte="resumo"]');
      resumo.textContent = "";
      var grade = el("div", "lsa-secoes");
      (ficha.secoes || []).forEach(function (secao) {
        var caixa = el("section", "lsa-secao");
        var larga = (secao.fotos && secao.fotos.length > 4) || (secao.texto && secao.texto.length > 220) || (secao.lista && secao.lista.length > 4);
        if (larga) caixa.classList.add("is-larga");
        var titulo = el("h3", "lsa-secao-titulo");
        titulo.appendChild(icone(secao.icone || "bi-card-text"));
        titulo.appendChild(document.createTextNode(secao.titulo));
        caixa.appendChild(titulo);
        if (secao.campos) {
          var dl = el("dl", "lsa-campos");
          secao.campos.forEach(function (campo) {
            var linha = el("div", "lsa-campo" + (campo.tom === "bom" ? " is-bom" : ""));
            var dt = el("dt");
            if (campo.icone) dt.appendChild(icone(campo.icone));
            dt.appendChild(document.createTextNode(campo.rotulo));
            linha.appendChild(dt);
            linha.appendChild(el("dd", "", campo.valor));
            dl.appendChild(linha);
          });
          caixa.appendChild(dl);
        }
        if (secao.etiquetas) {
          var ul = el("ul", "lsa-etiquetas");
          secao.etiquetas.forEach(function (texto) { ul.appendChild(el("li", "", texto)); });
          caixa.appendChild(ul);
        }
        if (secao.fotos) {
          var fotos = el("div", "lsa-fotos");
          secao.fotos.forEach(function (url) {
            var a = el("a");
            a.href = url;
            a.target = "_blank";
            a.rel = "noopener";
            var img = el("img");
            img.alt = "";
            img.loading = "lazy";
            /* foto que não chega (armazenamento fora do ar) vira um ícone, não um quadrado quebrado */
            img.addEventListener("error", function () {
              a.textContent = "";
              a.classList.add("is-sem-foto");
              a.appendChild(icone("bi-image"));
            });
            img.src = url;
            a.appendChild(img);
            fotos.appendChild(a);
          });
          caixa.appendChild(fotos);
        }
        if (secao.lista) {
          var lista = el("ul", "lsa-lista");
          secao.lista.forEach(function (item) {
            var li = el("li");
            var forte = el("strong", "", item.titulo);
            if (item.detalhe && item.detalhe.id && eu.temItem(item.detalhe.tipo)) {
              var link = el("a");
              link.href = "#";
              link.appendChild(forte);
              link.addEventListener("click", function (evento) {
                evento.preventDefault();
                eu.abrir(item.detalhe.tipo, item.detalhe.id, {});
              });
              li.appendChild(link);
            } else {
              li.appendChild(forte);
            }
            if (item.texto) li.appendChild(el("span", "", item.texto));
            lista.appendChild(li);
          });
          caixa.appendChild(lista);
        }
        if (secao.texto) caixa.appendChild(el("p", "lsa-secao-texto", secao.texto));
        if (secao.detalhe && secao.detalhe.id) {
          var abrir = el("a", "lsa-links");
          abrir.href = "#";
          abrir.textContent = "Abrir a ficha";
          abrir.addEventListener("click", function (evento) {
            evento.preventDefault();
            eu.abrir(secao.detalhe.tipo, secao.detalhe.id, {});
          });
          caixa.appendChild(abrir);
        }
        grade.appendChild(caixa);
      });
      resumo.appendChild(grade);
      var links = (ficha.links || []).filter(function (l) { return l.url; });
      if (links.length) {
        var barra = el("div", "lsa-links");
        links.forEach(function (link) {
          var a = el("a");
          a.href = link.url;
          if (link.externo) { a.target = "_blank"; a.rel = "noopener"; }
          a.appendChild(icone("bi-box-arrow-up-right"));
          a.appendChild(document.createTextNode(link.rotulo));
          barra.appendChild(a);
        });
        resumo.appendChild(barra);
      }
    },

    desenharAtividade: function (atividade, acrescentar) {
      var eu = this;
      var parte = this.dialogo.querySelector('[data-lsa-parte="atividade"]');
      var lista = parte.querySelector(".lsa-linha-tempo");
      if (!acrescentar || !lista) {
        parte.textContent = "";
        lista = el("ol", "lsa-linha-tempo");
        parte.appendChild(lista);
      }
      var anterior = parte.querySelector(".lsa-mais-atividade");
      if (anterior) anterior.remove();
      var itens = (atividade && atividade.itens) || [];
      if (!acrescentar && !itens.length) {
        var vazio = el("div", "lsa-estado");
        vazio.appendChild(icone("bi-clock-history"));
        vazio.appendChild(el("span", "", "Nenhuma atividade registrada ainda."));
        parte.textContent = "";
        parte.appendChild(vazio);
        return;
      }
      itens.forEach(function (item) {
        var li = el("li", "lsa-evento" + (item.tom && item.tom !== "neutro" ? " is-" + item.tom : ""));
        var ic = el("span", "lsa-evento-icone");
        ic.appendChild(icone(item.icone));
        li.appendChild(ic);
        li.appendChild(el("span", "lsa-evento-titulo", item.titulo));
        var quando = el("time", "lsa-evento-quando", item.quando);
        quando.dateTime = item.momento;
        li.appendChild(quando);
        if (item.texto) li.appendChild(el("p", "lsa-evento-texto", item.texto));
        lista.appendChild(li);
      });
      if (atividade && atividade.tem_mais) {
        var caixa = el("div", "lsa-mais-atividade");
        var mais = el("button", "lsa-carregar-mais", "Ver mais atividade");
        mais.type = "button";
        mais.addEventListener("click", function () {
          mais.disabled = true;
          mais.textContent = "Carregando…";
          var atual = eu.atual;
          buscar(eu.url(atual.tipo, atual.id, "atividade/?pagina=" + (atividade.pagina + 1))).then(function (pagina) {
            if (eu.atual !== atual) return;
            eu.desenharAtividade(pagina, true);
          }).catch(function (erro) {
            mais.disabled = false;
            mais.textContent = "Não carregou. Tentar de novo";
            mais.title = (erro && erro.message) || "";
          });
        });
        caixa.appendChild(mais);
        parte.appendChild(caixa);
      }
    }
  };

  /* ------------------------------------------------------------------
     os objetos das listas: tocar abre a ficha; o atalho abre os gráficos
     ------------------------------------------------------------------ */
  var INTERATIVOS = "a,button,input,select,textarea,label,summary,[contenteditable],[data-lsa-ignorar],[role=button],[role=switch]";
  var SEM_GRAFICOS = { pedido: true };

  function lugarDoAtalho(item) {
    var marcado = item.querySelector("[data-detalhe-acoes]");
    if (marcado) return marcado;
    var acoes = item.querySelector(".actions,[class*='-actions'],[class*='-acoes'],.adm-actions");
    if (acoes) return acoes;
    if (item.tagName === "TR") {
      var celulas = item.querySelectorAll("td");
      if (celulas.length) {
        var caixa = el("div", "lsa-atalho-solto");
        celulas[celulas.length - 1].appendChild(caixa);
        return caixa;
      }
    }
    var solto = el("div", "lsa-atalho-solto");
    item.appendChild(solto);
    return solto;
  }

  function prepararItens(raiz) {
    if (!document.querySelector("[data-lsa-ficha]")) return;
    (raiz || document).querySelectorAll("[data-detalhe-tipo][data-detalhe-id]").forEach(function (item) {
      if (item.dataset.lsaPronto) return;
      item.dataset.lsaPronto = "1";
      var tipo = item.dataset.detalheTipo;
      if (!item.matches("a,button") && !item.hasAttribute("tabindex")) item.tabIndex = 0;
      item.setAttribute("aria-haspopup", "dialog");
      if (item.dataset.detalheAtalho === "nao") return;
      var atalho = el("button", "lsa-atalho");
      atalho.type = "button";
      var graficos = !SEM_GRAFICOS[tipo];
      atalho.appendChild(icone(graficos ? "bi-graph-up" : "bi-card-text"));
      atalho.appendChild(document.createTextNode(graficos ? " Gráficos" : " Detalhes"));
      atalho.title = graficos ? "Ver os gráficos deste item" : "Ver os detalhes";
      atalho.setAttribute("aria-haspopup", "dialog");
      atalho.dataset.lsaAtalho = graficos ? "graficos" : "resumo";
      lugarDoAtalho(item).appendChild(atalho);
    });
  }

  document.addEventListener("click", function (evento) {
    var atalho = evento.target.closest && evento.target.closest("[data-lsa-atalho]");
    if (atalho) {
      var dono = atalho.closest("[data-detalhe-tipo]");
      if (!dono) return;
      evento.preventDefault();
      evento.stopPropagation();
      Ficha.abrir(dono.dataset.detalheTipo, dono.dataset.detalheId, { aba: atalho.dataset.lsaAtalho, origem: atalho });
      return;
    }
    var item = evento.target.closest && evento.target.closest("[data-detalhe-tipo][data-detalhe-id]");
    if (!item || !item.dataset.lsaPronto) return;
    var interativo = evento.target.closest(INTERATIVOS);
    if (interativo && interativo !== item && item.contains(interativo)) return;
    if (window.getSelection && String(window.getSelection()).length > 2) return;  /* estava selecionando texto */
    Ficha.abrir(item.dataset.detalheTipo, item.dataset.detalheId, { aba: "resumo", origem: item });
  });

  document.addEventListener("keydown", function (evento) {
    if (evento.key !== "Enter" && evento.key !== " ") return;
    var item = evento.target;
    if (!item || !item.dataset || !item.dataset.detalheTipo || !item.dataset.lsaPronto) return;
    evento.preventDefault();
    Ficha.abrir(item.dataset.detalheTipo, item.dataset.detalheId, { aba: "resumo", origem: item });
  });

  function montar(raiz) {
    (raiz || document).querySelectorAll("[data-lsa-painel]").forEach(montarPainel);
    Ficha.preparar();
    prepararItens(raiz || document);
  }

  window.LSAnalises = { montar: montar, abrir: function (tipo, id, opcoes) { Ficha.abrir(tipo, id, opcoes); } };

  function iniciar() {
    montar(document);
    /* listas que se redesenham (busca local, paginação por JS) ganham o atalho também */
    if (window.MutationObserver) {
      var espera = null;
      new window.MutationObserver(function (mudancas) {
        var temItem = mudancas.some(function (mudanca) {
          return Array.prototype.some.call(mudanca.addedNodes, function (no) {
            return no.nodeType === 1 && (no.hasAttribute("data-detalhe-tipo") || (no.querySelector && no.querySelector("[data-detalhe-tipo]")));
          });
        });
        if (!temItem) return;
        window.clearTimeout(espera);
        espera = window.setTimeout(function () { prepararItens(document); }, 150);
      }).observe(document.body, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
  document.addEventListener("ls:tela", function () { paineis = []; montar(document); });
})(window, document);
