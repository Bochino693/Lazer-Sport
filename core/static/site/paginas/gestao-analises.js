/* ======================================================================
   ANÁLISES E FICHAS DAS TELAS DE GESTÃO (LEIA-ME-V10, seção 76 e o AJUSTE)

   Três pedaços, um arquivo:
     * o painel "Desempenho" do topo de cada tela ([data-lsa-painel]);
     * a faixa "Agora" da tela Usuários ([data-lsa-agora]): quem está
       online, quem passou nas últimas 24 h e os contadores que filtram a
       lista -- alimentada pelo relógio do interno/ls-presenca.js;
     * o modal de detalhes ([data-lsa-ficha]) que abre ao tocar num objeto
       da lista ([data-detalhe-tipo][data-detalhe-id]) ou no atalho
       "Gráficos" que este arquivo põe em cada objeto.

   O QUE O AJUSTE MUDOU NO PAINEL (o cliente: "não gostei muito desse
   design ... mais criativo e mais robusto com estilo app e com as
   informações coerentes"):
     * SEM PAREDE DE CAIXAS VAZIAS. Cartão só para a métrica que tem
       número; as que não tiveram nada no período nem no anterior viram UMA
       linha ("Ainda sem registro neste período: ..."), com o motivo de
       cada uma a um toque. O gráfico abre na primeira métrica que tem dado.
     * NENHUM GRÁFICO PEDINDO DESCULPA. Quem conta pessoas distintas sai em
       colunas (por dia, semana ou mês); em "Hoje", as contas ativas viram
       a linha do tempo "Quem esteve ativo hoje" (do primeiro ao último
       sinal de cada pessoa). Sem série e sem pessoas, o número em
       destaque -- nunca uma área vazia com um aviso dentro.
     * TEXTO QUE FECHA. A frase do período e a comparação vêm prontas do
       servidor; o cartão diz "antes: 4" (ou "ontem: 4"), "novo", "igual" --
       e nunca "estável · antes 0".

   GRÁFICOS DESENHADOS AQUI, EM SVG. O painel não usa biblioteca nem CDN:
   uma linha com área para a série, a do período anterior em cinza, colunas
   (por dia da semana e para pessoas distintas) e barras deitadas no
   ranking. Marcas finas (linha de 2px, coluna de no máximo 24px com a
   ponta arredondada e 2px de respiro), grade de 1px, e a dica que segue o
   dedo ou o mouse -- e as setas do teclado. Toda série tem a tabela.

   TEXTO DE FORA ENTRA COMO TEXTO. Nome de brinquedo, de cliente e de cupom
   vem do banco: tudo vai por textContent, nunca por HTML montado em texto.

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
  var NOME_UNIDADE = { hora: "hora", dia: "dia", semana: "semana", mes: "mês" };
  var CORES_DE_AVATAR = 5;
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

  function plural(quantidade, um, varios) {
    return quantidade === 1 ? um : varios;
  }

  /* As iniciais numa cor estável (a cor sai do número da conta, não da posição). */
  function avatar(iniciais, cor, classe) {
    var no = el("span", "lsa-avatar is-c" + ((Number(cor) || 0) % CORES_DE_AVATAR) + (classe ? " " + classe : ""), iniciais || "?");
    no.setAttribute("aria-hidden", "true");
    return no;
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

  function temValor(valor) {
    return valor !== null && valor !== undefined;
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
  function desenharLinha(tela, rotulos, metrica, unidade, nomes) {
    tela.textContent = "";
    var largura = Math.max(260, tela.clientWidth || 600);
    var altura = largura < 480 ? 204 : 252;
    var serie = metrica.serie || [];
    var anterior = metrica.serie_anterior || null;
    var n = serie.length;
    var inteiro = metrica.formato !== "dinheiro" && !metrica.razao;
    var valores = serie.concat(anterior || []).filter(temValor);
    var esc = escala(Math.max.apply(null, valores.concat([0])), inteiro);
    var ticks = [];
    for (var t = 0; t <= esc.topo + 1e-9; t += esc.passo) ticks.push(t);
    var margemEsq = Math.max.apply(null, ticks.map(function (v) { return medirTexto(formatar(v, metrica.formato, "eixo")); })) + 6;
    var m = { esq: margemEsq, dir: 12, topo: 14, base: 26 };
    var lp = largura - m.esq - m.dir;
    var ap = altura - m.topo - m.base;
    var x = function (i) { return m.esq + (n <= 1 ? lp / 2 : (i * lp) / (n - 1)); };
    var y = function (v) { return m.topo + ap - (v / esc.topo) * ap; };

    uid += 1;
    var idDegrade = "lsaDegrade" + uid;
    var svg = sv("svg", { width: largura, height: altura, viewBox: "0 0 " + largura + " " + altura, role: "img", tabindex: "0" });
    var defs = sv("defs");
    var degrade = sv("linearGradient", { id: idDegrade, x1: "0", x2: "0", y1: "0", y2: "1" });
    [["0%", ".16"], ["100%", "0"]].forEach(function (par) {
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
        if (!temValor(v)) { aberto = false; return; }
        partes.push((aberto ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1));
        aberto = true;
      });
      return partes.join(" ");
    }

    if (anterior) {
      svg.appendChild(sv("path", { d: caminho(anterior), "class": "lsa-svg-anterior" }));
    }

    var ultimo = -1;
    serie.forEach(function (v, i) { if (temValor(v)) ultimo = i; });
    var primeiro = serie.findIndex(temValor);
    if (ultimo >= 0 && serie.slice(primeiro, ultimo + 1).every(function (v) { return v !== null; })) {
      var area = caminho(serie) + " L" + x(ultimo).toFixed(1) + " " + y(0).toFixed(1) + " L" + x(primeiro).toFixed(1) + " " + y(0).toFixed(1) + " Z";
      svg.appendChild(sv("path", { d: area, fill: "url(#" + idDegrade + ")", stroke: "none" }));
    }
    svg.appendChild(sv("path", { d: caminho(serie), "class": "lsa-svg-serie" }));
    if (ultimo >= 0) {
      svg.appendChild(sv("circle", { cx: x(ultimo), cy: y(serie[ultimo]), r: 4.5, "class": "lsa-svg-ponto" }));
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
      formatar(total, metrica.formato) + (temValor(metrica.anterior) ? ", " + nomes.anterior + " " + formatar(metrica.anterior, metrica.formato) : "") +
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
      if (temValor(atual)) {
        pontoAtual.setAttribute("cx", px);
        pontoAtual.setAttribute("cy", y(atual));
        pontoAtual.setAttribute("visibility", "visible");
        linhas.push({ valor: formatar(atual, metrica.formato), rotulo: nomes.atual });
      } else {
        pontoAtual.setAttribute("visibility", "hidden");
        linhas.push({ valor: "—", rotulo: rotulos[i] && rotulos[i].futuro ? "ainda não chegou" : nomes.atual });
      }
      if (anterior && temValor(anterior[i])) {
        pontoAnterior.setAttribute("cx", px);
        pontoAnterior.setAttribute("cy", y(anterior[i]));
        pontoAnterior.setAttribute("visibility", "visible");
        linhas.push({ valor: formatar(anterior[i], metrica.formato), rotulo: nomes.anterior, anterior: true });
      } else {
        pontoAnterior.setAttribute("visibility", "hidden");
      }
      var referencia = temValor(atual) ? y(atual) : m.topo + ap / 2;
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
     colunas: o dia da semana, e a série de quem conta pessoas distintas
     (cada dia, semana ou mês é uma contagem à parte: não se liga uma à
     outra com uma linha)

     itens: [{curto, longo, valor}] -- valor null = balde que ainda não chegou
     ------------------------------------------------------------------ */
  function desenharColunas(tela, itens, metrica, opcoes) {
    opcoes = opcoes || {};
    tela.textContent = "";
    var n = itens.length;
    var largura = Math.max(240, tela.clientWidth || 400);
    var altura = opcoes.altura || 176;
    var inteiro = metrica.formato !== "dinheiro" && !opcoes.media;
    var valores = itens.map(function (item) { return temValor(item.valor) ? item.valor : 0; });
    var maior = Math.max.apply(null, valores.concat([0]));
    var esc = escala(maior, inteiro);
    var ticks = [];
    for (var t = 0; t <= esc.topo + 1e-9; t += esc.passo) ticks.push(t);
    var margemEsq = Math.max.apply(null, ticks.map(function (v) { return medirTexto(formatar(v, metrica.formato, "eixo")); })) + 6;
    var m = { esq: margemEsq, dir: 6, topo: 20, base: 24 };
    var lp = largura - m.esq - m.dir;
    var ap = altura - m.topo - m.base;
    var faixa = lp / n;
    /* no máximo 24px, e sempre 2px de respiro entre uma coluna e a vizinha */
    var grossura = Math.max(2, Math.min(24, faixa * 0.6, faixa - 2));
    var y = function (v) { return m.topo + ap - (v / esc.topo) * ap; };
    var svg = sv("svg", { width: largura, height: altura, viewBox: "0 0 " + largura + " " + altura, role: "img", tabindex: "0" });

    ticks.forEach(function (valor) {
      var py = Math.round(y(valor)) + 0.5;
      svg.appendChild(sv("line", { x1: m.esq, x2: largura - m.dir, y1: py, y2: py, "class": valor === 0 ? "lsa-svg-base" : "lsa-svg-grade" }));
      var rotulo = sv("text", { x: m.esq - 8, y: py + 4, "text-anchor": "end", "class": "lsa-svg-texto" });
      rotulo.textContent = formatar(valor, metrica.formato, "eixo");
      svg.appendChild(rotulo);
    });

    var cabem = Math.max(2, Math.floor(lp / (opcoes.larguraDoRotulo || 44)));
    var passo = Math.max(1, Math.ceil(n / cabem));
    var barras = [];
    var melhor = valores.indexOf(maior);
    itens.forEach(function (item, i) {
      var valor = valores[i];
      var cx = m.esq + faixa * i + faixa / 2;
      var topo = y(valor);
      var base = y(0);
      var alturaBarra = Math.max(0, base - topo);
      var raio = Math.min(4, alturaBarra, grossura / 2);
      var esq = cx - grossura / 2;
      var dir = cx + grossura / 2;
      var barra;
      if (alturaBarra > 0) {
        barra = sv("path", {
          d: "M" + esq + " " + base + " L" + esq + " " + (topo + raio) + " Q" + esq + " " + topo + " " + (esq + raio) + " " + topo +
            " L" + (dir - raio) + " " + topo + " Q" + dir + " " + topo + " " + dir + " " + (topo + raio) + " L" + dir + " " + base + " Z",
          "class": "lsa-svg-barra"
        });
      } else {
        /* zero é zero: um traço na base, e não uma coluna inventada */
        barra = sv("path", { d: "M" + esq + " " + (base - 1) + " L" + dir + " " + (base - 1), "class": "lsa-svg-barra-zero" });
      }
      if (!temValor(item.valor)) barra.setAttribute("visibility", "hidden");
      svg.appendChild(barra);
      barras.push(barra);
      if ((n - 1 - i) % passo === 0) {
        var nome = sv("text", { x: cx, y: altura - 7, "text-anchor": "middle", "class": "lsa-svg-texto" });
        nome.textContent = item.curto;
        svg.appendChild(nome);
      }
      if (i === melhor && maior > 0) {
        var valorTexto = sv("text", { x: cx, y: topo - 6, "text-anchor": "middle", "class": "lsa-svg-valor" });
        valorTexto.textContent = formatar(valor, metrica.formato, "curto");
        svg.appendChild(valorTexto);
      }
    });

    tela.appendChild(svg);
    var dica = new Dica(tela);
    var indice = -1;
    var rotuloDaDica = opcoes.rotuloDaDica || metrica.rotulo.toLowerCase();
    function mostrar(i) {
      indice = i;
      barras.forEach(function (barra, j) { barra.classList.toggle("is-apagada", j !== i); });
      var cx = m.esq + faixa * i + faixa / 2;
      var valor = itens[i].valor;
      dica.mostrar(itens[i].longo, [{
        valor: temValor(valor) ? formatar(valor, metrica.formato) : "—",
        rotulo: temValor(valor) ? rotuloDaDica : "ainda não chegou"
      }], cx, y(valores[i]));
    }
    function esconder() {
      barras.forEach(function (barra) { barra.classList.remove("is-apagada"); });
      dica.esconder();
    }
    itens.forEach(function (item, i) {
      var alvo = sv("rect", { x: m.esq + faixa * i, y: 0, width: faixa, height: altura, "class": "lsa-svg-alvo" });
      alvo.addEventListener("pointerenter", function () { mostrar(i); });
      alvo.addEventListener("pointerdown", function () { mostrar(i); });
      svg.appendChild(alvo);
    });
    svg.addEventListener("pointerleave", esconder);
    svg.addEventListener("keydown", function (evento) {
      if (evento.key === "ArrowRight" || evento.key === "ArrowLeft") {
        evento.preventDefault();
        var proximo = indice < 0 ? (melhor >= 0 ? melhor : 0) : indice + (evento.key === "ArrowRight" ? 1 : -1);
        mostrar(Math.max(0, Math.min(n - 1, proximo)));
      } else if (evento.key === "Escape") {
        esconder();
      }
    });
    svg.addEventListener("blur", esconder);
    svg.setAttribute("aria-label", (opcoes.titulo || metrica.rotulo) + ". " +
      (maior > 0 ? "Maior valor: " + itens[melhor].longo + ", " + formatar(maior, metrica.formato) + "." : "Sem movimento.") +
      " Use as setas para ler cada coluna.");
    return melhor;
  }

  /* ------------------------------------------------------------------
     "Quem esteve ativo hoje": uma faixa por pessoa, do primeiro ao último
     sinal do dia. É o que o banco guarda dos acessos (o dia, o primeiro e
     o último sinal de cada conta) -- a hora de cada acesso não é guardada, e por isso
     este desenho entra no lugar das colunas por hora.
     ------------------------------------------------------------------ */
  function desenharPresencas(tela, pessoas, agoraMinutos) {
    tela.textContent = "";
    var itens = (pessoas && pessoas.itens) || [];
    var VISIVEIS = 8;
    var comeco = Math.min.apply(null, itens.map(function (p) { return p.inicio; }));
    var fim = Math.max.apply(null, itens.map(function (p) { return p.fim; }).concat(temValor(agoraMinutos) ? [agoraMinutos] : []));
    /* o eixo começa na hora cheia antes do primeiro sinal e acaba na hora cheia depois do último */
    comeco = Math.max(0, Math.floor(comeco / 60) * 60);
    fim = Math.min(1440, Math.ceil((fim + 1) / 60) * 60);
    if (fim - comeco < 360) {
      comeco = Math.max(0, fim - 360);
      fim = Math.min(1440, comeco + 360);
    }
    var horas = (fim - comeco) / 60;
    var passo = horas <= 6 ? 1 : horas <= 12 ? 2 : horas <= 18 ? 3 : 4;
    var pct = function (minutos) { return ((Math.min(fim, Math.max(comeco, minutos)) - comeco) / (fim - comeco)) * 100; };

    var caixa = el("div", "lsa-dia");
    if (temValor(agoraMinutos) && agoraMinutos >= comeco && agoraMinutos <= fim) {
      caixa.style.setProperty("--lsa-dia-agora", pct(agoraMinutos) + "%");
      caixa.classList.add("tem-agora");
    }
    var eixo = el("div", "lsa-dia-eixo");
    eixo.setAttribute("aria-hidden", "true");
    var regua = el("span", "lsa-dia-regua");
    for (var h = comeco; h <= fim; h += passo * 60) {
      var marca = el("span", "", (h / 60) + "h");
      marca.style.left = pct(h) + "%";
      regua.appendChild(marca);
    }
    eixo.appendChild(regua);
    caixa.appendChild(eixo);

    var lista = el("ul", "lsa-dia-linhas");
    var dica = new Dica(tela);
    itens.forEach(function (pessoa, i) {
      var item = el("li", i >= VISIVEIS ? "is-extra" : "");
      var linha = el("div", "lsa-dia-linha");
      linha.dataset.detalheTipo = "usuario";
      linha.dataset.detalheId = pessoa.id;
      linha.dataset.detalheAtalho = "nao";
      linha.setAttribute("role", "button");
      linha.setAttribute("aria-label", pessoa.nome + ", " + pessoa.papel_rotulo + ": ativo das " + pessoa.de + " às " + pessoa.ate + ". Abrir a ficha");
      linha.appendChild(avatar(pessoa.iniciais, pessoa.cor, "is-pequeno"));
      var nome = el("span", "lsa-dia-nome", pessoa.nome);
      linha.appendChild(nome);
      var horario = el("span", "lsa-dia-horas", pessoa.de === pessoa.ate ? pessoa.de : pessoa.de + " – " + pessoa.ate);
      linha.appendChild(horario);
      var trilho = el("span", "lsa-dia-trilho");
      trilho.setAttribute("aria-hidden", "true");
      var faixa = el("span", "lsa-dia-faixa");
      var esquerda = pct(pessoa.inicio);
      faixa.style.left = esquerda + "%";
      faixa.style.width = Math.max(0, pct(pessoa.fim) - esquerda) + "%";
      trilho.appendChild(faixa);
      linha.appendChild(trilho);
      function mostrar() {
        var c = tela.getBoundingClientRect();
        var f = faixa.getBoundingClientRect();
        dica.mostrar(pessoa.nome + " · " + pessoa.papel_rotulo, [
          { valor: pessoa.de, rotulo: "primeiro sinal do dia" },
          { valor: pessoa.ate, rotulo: "último sinal" }
        ], f.left - c.left + f.width / 2, f.top - c.top);
      }
      linha.addEventListener("pointerenter", mostrar);
      linha.addEventListener("focus", mostrar);
      linha.addEventListener("pointerleave", function () { dica.esconder(); });
      linha.addEventListener("blur", function () { dica.esconder(); });
      item.appendChild(linha);
      lista.appendChild(item);
    });
    caixa.appendChild(lista);
    tela.appendChild(caixa);
    tela.appendChild(dica.no);
    prepararItens(tela);

    var escondidas = itens.length - VISIVEIS;
    var fora = Math.max(0, (pessoas.total || itens.length) - itens.length);
    if (escondidas > 0) {
      var mais = el("label", "lsa-mais-rotulo");
      var marca2 = el("input", "lsa-oculto");
      marca2.type = "checkbox";
      var texto = el("span", "", "Mostrar as " + itens.length + " contas");
      mais.appendChild(marca2);
      mais.appendChild(icone("bi-chevron-down"));
      mais.appendChild(texto);
      marca2.addEventListener("change", function () {
        caixa.classList.toggle("is-todas", marca2.checked);
        texto.textContent = marca2.checked ? "Mostrar só as " + VISIVEIS + " mais recentes" : "Mostrar as " + itens.length + " contas";
      });
      tela.appendChild(mais);
    }
    if (fora > 0) {
      tela.appendChild(el("p", "lsa-bloco-nota", "E mais " + NUM.format(fora) + " " + plural(fora, "conta", "contas") + ": a lista traz as " + itens.length + " vistas por último."));
    }
  }

  /* a faísca (sparkline) de cada indicador: cinza, o ponto de agora no acento */
  function faisca(metrica) {
    var serie = (metrica.serie || []).filter(temValor);
    if (serie.length < 2) return null;
    var maior = Math.max.apply(null, serie.concat([0]));
    var menor = Math.min.apply(null, serie.concat([0]));
    var faixa = maior - menor || 1;
    var altura = function (v) { return 23 - ((v - menor) / faixa) * 20; };
    var caixa = el("span", "lsa-faisca-caixa");
    caixa.setAttribute("aria-hidden", "true");
    var svg = sv("svg", { "class": "lsa-faisca", viewBox: "0 0 100 26", preserveAspectRatio: "none", focusable: "false" });
    var pontos = serie.map(function (v, i) {
      return ((i / (serie.length - 1)) * 100).toFixed(2) + "," + altura(v).toFixed(2);
    });
    var linha = sv("polyline", { points: pontos.join(" "), fill: "none", "stroke-width": "1.5", "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round", "stroke-linecap": "round" });
    linha.style.stroke = "var(--lsa-anterior)";
    svg.appendChild(linha);
    caixa.appendChild(svg);
    /* o ponto é HTML: num SVG esticado ele viraria um ovo */
    var ponto = el("span", "lsa-faisca-ponto");
    ponto.style.top = (altura(serie[serie.length - 1]) / 26) * 100 + "%";
    caixa.appendChild(ponto);
    return caixa;
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

  function diaMes(iso) {
    return iso ? iso.split("-").reverse().slice(0, 2).join("/") : "";
  }

  /* A pílula da variação ("▲ 47,8%") e, ao lado, o número de antes ("antes: 23").
     Devolve {pilula, antes}: o cartão põe cada um no seu lugar. */
  function variacao(metrica, periodo) {
    var pilula = el("span", "lsa-variacao " + classeDaVariacao(metrica));
    var antes = el("span", "lsa-antes");
    var nomeAnterior = (periodo && periodo.anterior_curto) || "antes";
    var falado;
    if (metrica.direcao === "sem_base") {
      pilula.appendChild(icone("bi-info-circle"));
      pilula.appendChild(document.createTextNode("sem comparação"));
      antes.textContent = metrica.desde ? "registrado desde " + diaMes(metrica.desde) : "";
      falado = "sem comparação: o registro começou" + (metrica.desde ? " em " + diaMes(metrica.desde) : " há pouco");
      pilula.title = "O registro começou" + (metrica.desde ? " em " + diaMes(metrica.desde) : " há pouco") + ": ainda não há período anterior inteiro para comparar.";
    } else {
      var anterior = formatar(metrica.anterior, metrica.formato, "curto");
      if (metrica.direcao === "novo") {
        pilula.appendChild(icone("bi-caret-up-fill"));
        pilula.appendChild(document.createTextNode("novo"));
        falado = "novo: não houve nada no período anterior";
        antes.textContent = nomeAnterior + ": nada";
      } else if (metrica.direcao === "igual") {
        pilula.appendChild(icone("bi-dash-lg"));
        pilula.appendChild(document.createTextNode("igual"));
        falado = "igual ao período anterior";
        antes.textContent = nomeAnterior + ": " + anterior;
      } else {
        var sobe = metrica.direcao === "sobe";
        pilula.appendChild(icone(sobe ? "bi-caret-up-fill" : "bi-caret-down-fill"));
        pilula.appendChild(document.createTextNode(NUM1.format(Math.abs(metrica.variacao)) + "%"));
        falado = (sobe ? "subiu " : "caiu ") + NUM1.format(Math.abs(metrica.variacao)) + "% em relação ao período anterior, que teve " + anterior;
        antes.textContent = nomeAnterior + ": " + anterior;
      }
    }
    pilula.setAttribute("aria-label", falado);
    return { pilula: pilula, antes: antes };
  }

  function nomesDasSeries(periodo) {
    if (periodo && periodo.anterior_curto === "ontem") return { atual: "hoje", anterior: "ontem" };
    if (periodo && periodo.anterior_curto === "dia anterior") return { atual: "este dia", anterior: "dia anterior" };
    return { atual: "este período", anterior: "período anterior" };
  }

  /* O AVISO GRANDE: o ícone num quadrado, o título, uma frase e (quando há o
     que fazer) um botão. É a mesma peça para o erro de carga, o período sem
     movimento, a ficha que não abriu e a atividade vazia -- nunca uma linha
     de texto solta no meio da tela. */
  function avisoGrande(opcoes) {
    var caixa = el("div", "lsa-aviso-grande" + (opcoes.erro ? " is-erro" : ""));
    caixa.setAttribute("role", opcoes.erro ? "alert" : "status");
    var selo = el("span", "lsa-aviso-icone");
    selo.appendChild(icone(opcoes.icone));
    caixa.appendChild(selo);
    caixa.appendChild(el("strong", "", opcoes.titulo));
    if (opcoes.texto) caixa.appendChild(el("p", "", opcoes.texto));
    if (opcoes.acao) {
      var botao = el("button", "lsa-tentar", opcoes.acao);
      botao.type = "button";
      botao.addEventListener("click", opcoes.aoTocar);
      caixa.appendChild(botao);
    }
    return caixa;
  }

  /* O recado que sobe e some (a "tarja" do painel): para o que não deu certo
     mas não tirou nada da tela. Fora do painel, não há tarja: fica o silêncio. */
  function recado(mensagem, tipo) {
    if (window.Painel && window.Painel.aviso) window.Painel.aviso(mensagem, tipo || "");
  }

  /* o esqueleto: as caixas no lugar dos indicadores e do gráfico enquanto os números não chegam */
  function esqueleto(texto) {
    var caixa = el("div", "lsa-esqueleto");
    caixa.setAttribute("role", "status");
    caixa.appendChild(el("span", "lsa-oculto", texto || "Carregando os números…"));
    var linha = el("div", "lsa-esqueleto-linha");
    linha.setAttribute("aria-hidden", "true");
    for (var i = 0; i < 4; i += 1) linha.appendChild(el("span"));
    caixa.appendChild(linha);
    var bloco = el("div", "lsa-esqueleto-bloco");
    bloco.setAttribute("aria-hidden", "true");
    caixa.appendChild(bloco);
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
        espera = window.setTimeout(function () { eu.arrumarIndicadores(); eu.desenharGraficos(); }, 120);
      });
      this.observador.observe(this.corpo);
    }
  };

  Analise.prototype.escolherPeriodo = function (periodo, de, ate) {
    this.periodo = periodo;
    if (this.periodos) {
      var radio = this.periodos.querySelector('input[value="' + periodo + '"]');
      if (radio) {
        radio.checked = true;
        /* no celular a régua de períodos rola de lado: o escolhido vem para a vista */
        var rotulo = radio.closest("label");
        if (rotulo && this.periodos.scrollWidth > this.periodos.clientWidth) {
          this.periodos.scrollLeft = Math.max(0, rotulo.offsetLeft - (this.periodos.clientWidth - rotulo.offsetWidth) / 2);
        }
      }
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
    /* recarregar mantém o desenho anterior, apagado: sem pulo. O esqueleto é só da primeira vez. */
    if (this.dados) {
      this.corpo.classList.add("is-carregando");
    } else {
      this.corpo.textContent = "";
      this.corpo.appendChild(esqueleto());
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
    if (this.dados) {
      /* Já havia números na tela: eles ficam (são os do período de antes), o
         período volta a ser o deles e um recado diz o que houve. Trocar um
         painel inteiro por um aviso de erro seria tirar da pessoa o que ela
         estava lendo. */
      var codigo = this.dados.periodo.codigo;
      this.periodo = codigo;
      var radio = this.periodos && this.periodos.querySelector('input[value="' + codigo + '"]');
      if (radio) radio.checked = true;
      if (this.dias) this.dias.hidden = codigo !== "dias";
      if (this.opcoes.aoMudarPeriodo) this.opcoes.aoMudarPeriodo(codigo);
      recado("Não deu para atualizar os números agora. Ficaram os de antes.", "erro");
      return;
    }
    this.corpo.textContent = "";
    this.corpo.appendChild(avisoGrande({
      erro: true,
      icone: "bi-wifi-off",
      titulo: "Os números não chegaram",
      texto: (mensagem || "Não foi possível falar com o servidor.") + " O resto da tela continua funcionando.",
      acao: "Tentar de novo",
      aoTocar: function () { eu.carregar(); }
    }));
    if (this.descricao) this.descricao.textContent = "";
  };

  Analise.prototype.escreverPeriodo = function (periodo) {
    if (!this.descricao) return;
    this.descricao.textContent = "";
    this.descricao.appendChild(el("strong", "", periodo.titulo || periodo.descricao));
    if (periodo.comparacao) this.descricao.appendChild(el("span", "", periodo.comparacao));
  };

  Analise.prototype.desenhar = function () {
    var dados = this.dados;
    var eu = this;
    this.escreverPeriodo(dados.periodo);
    var metricas = dados.metricas || [];
    var comDados = metricas.filter(function (m) { return !m.vazia; });
    var vazias = metricas.filter(function (m) { return m.vazia && !m.indisponivel; });
    /* a fonte que falhou no servidor: uma linha calma, e as outras métricas seguem */
    var foraDoAr = metricas.filter(function (m) { return m.indisponivel; });
    /* a métrica escolhida continua, se ainda tiver número; senão, a primeira que tem */
    if (!this.metrica || !comDados.some(function (m) { return m.codigo === eu.metrica; })) {
      var principal = comDados.find(function (m) { return m.codigo === dados.principal; });
      this.metrica = (principal || comDados[0] || {}).codigo || null;
    }

    this.corpo.textContent = "";
    this.graficos = null;
    this.abas = null;

    if (!comDados.length) {
      if (foraDoAr.length) this.corpo.appendChild(this.linhaDasIndisponiveis(foraDoAr));
      if (vazias.length || !foraDoAr.length) this.corpo.appendChild(this.semMovimento(dados, vazias));
      this.desenharAvisos(dados);
      manterAncora();
      return;
    }

    var grade = el("div", "lsa-indicadores" + (comDados.length < 3 ? " is-poucos" : ""));
    grade.setAttribute("role", "radiogroup");
    grade.setAttribute("aria-label", "Indicadores do período: escolha o que os gráficos mostram");
    comDados.forEach(function (metrica) {
      var rotulo = el("label", "lsa-indicador lsa-tom-" + (metrica.tom || "acento"));
      var radio = el("input");
      radio.type = "radio";
      radio.name = eu.nome;
      radio.value = metrica.codigo;
      radio.checked = metrica.codigo === eu.metrica;
      if (metrica.ajuda) rotulo.title = metrica.ajuda;
      rotulo.appendChild(radio);
      var partes = variacao(metrica, dados.periodo);
      var topo = el("span", "lsa-indicador-topo");
      var selo = el("span", "lsa-indicador-icone");
      selo.appendChild(icone(metrica.icone));
      topo.appendChild(selo);
      topo.appendChild(partes.pilula);
      rotulo.appendChild(topo);
      rotulo.appendChild(el("span", "lsa-indicador-rotulo", metrica.rotulo));
      rotulo.appendChild(el("span", "lsa-indicador-valor", formatar(metrica.total, metrica.formato, "curto")));
      rotulo.appendChild(partes.antes);
      var linha = faisca(metrica);
      rotulo.appendChild(linha || el("span", "lsa-faisca-caixa is-vazia"));
      grade.appendChild(rotulo);
    });
    grade.addEventListener("change", function (evento) {
      if (!evento.target.matches("input[type=radio]")) return;
      eu.escolherMetrica(evento.target.value);
    });
    this.indicadores = grade;
    this.corpo.appendChild(grade);
    this.arrumarIndicadores();

    if (foraDoAr.length) this.corpo.appendChild(this.linhaDasIndisponiveis(foraDoAr));
    if (vazias.length) this.corpo.appendChild(this.linhaDasVazias(vazias));

    this.graficos = el("div", "lsa-graficos");
    this.corpo.appendChild(this.graficos);
    this.desenharGraficos();
    this.desenharAvisos(dados);
    manterAncora();
  };

  /* Nove cartões numa grade de seis colunas deixam 6 + 3 e um buraco. Aqui as
     linhas saem equilibradas (5 + 4, 4 + 3, 4 + 4): o CSS reparte a largura
     por `--lsa-por-linha`. No celular isto não vale: os cartões passam de lado. */
  Analise.prototype.arrumarIndicadores = function () {
    var grade = this.indicadores;
    if (!grade || !document.contains(grade)) return;
    var quantos = grade.children.length;
    var cabem = Math.max(1, Math.floor((grade.clientWidth + 12) / (172 + 12)));
    var linhas = Math.ceil(quantos / cabem);
    grade.style.setProperty("--lsa-por-linha", Math.max(1, Math.ceil(quantos / linhas)));
  };

  /* A métrica do gráfico: os cartões e as abas do gráfico são dois caminhos para a mesma escolha. */
  Analise.prototype.escolherMetrica = function (codigo) {
    this.metrica = codigo;
    if (this.indicadores) {
      this.indicadores.querySelectorAll("input[type=radio]").forEach(function (radio) {
        radio.checked = radio.value === codigo;
      });
    }
    this.desenharGraficos();
  };

  /* UMA linha para tudo o que não teve número: sem parede de caixas vazias. */
  Analise.prototype.linhaDasVazias = function (vazias) {
    var detalhes = el("details", "lsa-vazias");
    var resumo = el("summary");
    resumo.appendChild(icone("bi-moon-stars"));
    var frase = el("span", "lsa-vazias-frase");
    frase.appendChild(document.createTextNode("Ainda sem registro neste período: "));
    frase.appendChild(el("strong", "", vazias.map(function (m) { return m.rotulo; }).join(" · ")));
    resumo.appendChild(frase);
    var porque = el("span", "lsa-vazias-porque", "por quê?");
    porque.appendChild(icone("bi-chevron-down"));
    resumo.appendChild(porque);
    detalhes.appendChild(resumo);
    var lista = el("ul", "lsa-vazias-lista");
    vazias.forEach(function (metrica) {
      var item = el("li");
      item.appendChild(icone(metrica.icone));
      item.appendChild(el("strong", "", metrica.rotulo));
      item.appendChild(el("span", "", metrica.motivo || "Sem movimento neste período."));
      lista.appendChild(item);
    });
    detalhes.appendChild(lista);
    return detalhes;
  };

  /* "Você não pode me gerar uma coisa gerando erros": a métrica cuja consulta
     falhou no servidor (o erro vai para o log de lá) não vira parede de erro.
     Uma linha diz quais não vieram, e que as outras estão certas. */
  Analise.prototype.linhaDasIndisponiveis = function (metricas) {
    var eu = this;
    var linha = el("div", "lsa-fora-do-ar");
    linha.setAttribute("role", "status");
    linha.appendChild(icone("bi-cloud-slash"));
    var frase = el("span", "lsa-vazias-frase");
    frase.appendChild(document.createTextNode("Não deu para carregar agora: "));
    frase.appendChild(el("strong", "", metricas.map(function (m) { return m.rotulo; }).join(" · ")));
    frase.appendChild(document.createTextNode(". Os outros números estão certos."));
    linha.appendChild(frase);
    var tentar = el("a", "lsa-fora-do-ar-tentar", "Tentar de novo");
    tentar.href = "#";
    tentar.addEventListener("click", function (evento) {
      evento.preventDefault();
      eu.carregar();
    });
    linha.appendChild(tentar);
    return linha;
  };

  Analise.prototype.semMovimento = function (dados, vazias) {
    var caixa = avisoGrande({
      icone: "bi-moon-stars",
      titulo: "Sem movimento no período",
      texto: "Nenhum indicador teve registro neste período nem no anterior. Escolha um período maior para ver o histórico."
    });
    if (vazias.length) {
      var lista = el("ul", "lsa-vazias-lista");
      vazias.forEach(function (metrica) {
        var item = el("li");
        item.appendChild(icone(metrica.icone));
        item.appendChild(el("strong", "", metrica.rotulo));
        item.appendChild(el("span", "", metrica.motivo || "Sem movimento neste período."));
        lista.appendChild(item);
      });
      caixa.appendChild(lista);
    }
    return caixa;
  };

  Analise.prototype.desenharAvisos = function (dados) {
    if (!dados.avisos || !dados.avisos.length) return;
    var notas = el("details", "lsa-notas");
    var resumo = el("summary");
    resumo.appendChild(icone("bi-info-circle"));
    resumo.appendChild(document.createTextNode("Como estes números são contados"));
    notas.appendChild(resumo);
    var lista = el("ul");
    dados.avisos.forEach(function (aviso) { lista.appendChild(el("li", "", aviso)); });
    notas.appendChild(lista);
    this.corpo.appendChild(notas);
  };

  /* Três números que resumem a série, acima do gráfico: o total, a média por balde e o pico. */
  Analise.prototype.resumoDaSerie = function (metrica, dados) {
    var unidade = dados.periodo.unidade;
    var itens = [{
      rotulo: dados.periodo.anterior_curto === "ontem" ? "Hoje até agora" : "No período",
      valor: formatar(metrica.total, metrica.formato, "curto")
    }];
    var serie = (metrica.serie || []);
    var passados = serie.filter(temValor);
    if (passados.length > 1) {
      if (!metrica.razao) {
        var soma = passados.reduce(function (a, b) { return a + b; }, 0);
        itens.push({ rotulo: "Média por " + NOME_UNIDADE[unidade], valor: formatar(Math.round((soma / passados.length) * 10) / 10, metrica.formato, "curto") });
      }
      var maior = Math.max.apply(null, passados);
      var onde = serie.indexOf(maior);
      if (maior > 0 && onde >= 0 && dados.rotulos[onde]) {
        var curto = dados.rotulos[onde].curto;
        var quando = unidade === "hora" ? "às " + curto : unidade === "semana" ? "semana de " + curto : "em " + curto;
        itens.push({ rotulo: "Pico", valor: formatar(maior, metrica.formato, "curto"), nota: quando });
      }
    }
    var caixa = el("dl", "lsa-resumo");
    itens.forEach(function (item) {
      var parte = el("div");
      parte.appendChild(el("dt", "", item.rotulo));
      var valor = el("dd", "", item.valor);
      if (item.nota) valor.appendChild(el("small", "", item.nota));
      parte.appendChild(valor);
      caixa.appendChild(parte);
    });
    return caixa;
  };

  /* Por dia da semana: a soma do servidor (métricas que se somam) ou, para
     pessoas distintas em períodos por dia, a MÉDIA de cada dia da semana. */
  function semanaDe(metrica, dados) {
    if (metrica.semana) return { valores: metrica.semana, media: false };
    if (!metrica.distinta || dados.periodo.unidade !== "dia" || !metrica.serie) return null;
    var somas = [0, 0, 0, 0, 0, 0, 0];
    var vezes = [0, 0, 0, 0, 0, 0, 0];
    metrica.serie.forEach(function (valor, i) {
      if (!temValor(valor) || !dados.rotulos[i]) return;
      var partes = dados.rotulos[i].chave.slice(0, 10).split("-");
      var dia = (new Date(Number(partes[0]), Number(partes[1]) - 1, Number(partes[2])).getDay() + 6) % 7;
      somas[dia] += valor;
      vezes[dia] += 1;
    });
    if (vezes.filter(function (v) { return v > 0; }).length < 7) return null;
    return { valores: somas.map(function (soma, i) { return Math.round((soma / vezes[i]) * 10) / 10; }), media: true };
  }

  Analise.prototype.desenharGraficos = function () {
    var dados = this.dados;
    var grade = this.graficos;
    if (!dados || !grade) return;
    var eu = this;
    var comDados = (dados.metricas || []).filter(function (m) { return !m.vazia; });
    var metrica = comDados.find(function (m) { return m.codigo === eu.metrica; });
    grade.textContent = "";
    if (!metrica) return;
    var unidade = dados.periodo.unidade;
    var nomes = nomesDasSeries(dados.periodo);
    var semana = semanaDe(metrica, dados);
    var temLista = !!(this.opcoes.ranking && metrica.lista && metrica.lista.itens && metrica.lista.itens.length);
    var temRanking = !!this.opcoes.ranking && (temLista || (metrica.tem_ranking !== false && (metrica.ranking || []).length > 0));
    grade.className = "lsa-graficos" + (temRanking ? "" : " sem-ranking") + (semana ? "" : " sem-semana");

    /* ---- o gráfico principal, com as abas de métrica ---- */
    var bloco = el("section", "lsa-bloco lsa-bloco-linha");
    if (comDados.length > 1) {
      var abas = el("div", "lsa-metricas");
      abas.setAttribute("role", "radiogroup");
      abas.setAttribute("aria-label", "Métrica do gráfico");
      comDados.forEach(function (m) {
        var rotulo = el("label", "lsa-metrica");
        var radio = el("input");
        radio.type = "radio";
        radio.name = eu.nome + "-aba";
        radio.value = m.codigo;
        radio.checked = m.codigo === metrica.codigo;
        rotulo.appendChild(radio);
        rotulo.appendChild(icone(m.icone));
        rotulo.appendChild(document.createTextNode(m.rotulo));
        abas.appendChild(rotulo);
      });
      abas.addEventListener("change", function (evento) {
        if (!evento.target.matches("input[type=radio]")) return;
        var foco = evento.target.value;
        eu.escolherMetrica(foco);
        /* o gráfico foi redesenhado: o foco volta para a aba escolhida */
        var nova = eu.graficos && eu.graficos.querySelector('.lsa-metricas input[value="' + foco + '"]');
        if (nova) nova.focus({ preventScroll: true });
      });
      bloco.appendChild(abas);
    }
    var topo = el("div", "lsa-bloco-topo");
    var telaLinha = el("div", "lsa-tela");
    var tabela = null;
    if (metrica.pessoas && metrica.pessoas.itens && metrica.pessoas.itens.length) {
      /* Hoje, contas ativas: quem são, do primeiro ao último sinal */
      var hoje = dados.periodo.anterior_curto === "ontem";
      var daConta = !!metrica.pessoas.da_conta;
      topo.appendChild(el("h3", "lsa-bloco-titulo", daConta
        ? (hoje ? "O dia de hoje" : "Aquele dia")
        : (hoje ? "Quem esteve ativo hoje" : "Quem esteve ativo no dia")));
      var total = metrica.pessoas.total || metrica.pessoas.itens.length;
      var agora = hoje && dados.gerado_em ? Number(dados.gerado_em.slice(11, 13)) * 60 + Number(dados.gerado_em.slice(14, 16)) : null;
      var legendaDia = el("ul", "lsa-legenda");
      [["is-faixa", "do primeiro ao último sinal"]].concat(agora === null ? [] : [["is-agora", "agora"]]).forEach(function (par) {
        var item = el("li");
        var chave = el("span", "lsa-chave " + par[0]);
        chave.setAttribute("aria-hidden", "true");
        item.appendChild(chave);
        item.appendChild(document.createTextNode(par[1]));
        legendaDia.appendChild(item);
      });
      topo.appendChild(legendaDia);
      bloco.appendChild(topo);
      var umaSo = metrica.pessoas.itens[0];
      bloco.appendChild(el("p", "lsa-bloco-sub lsa-bloco-conta", daConta
        ? (umaSo.de === umaSo.ate ? "Um sinal só, às " + umaSo.de + "." : "Entrou às " + umaSo.de + "; o último sinal foi às " + umaSo.ate + ".")
        : NUM.format(total) + " " + plural(total, "conta usou", "contas usaram") + " o site, o aplicativo ou o painel"));
      bloco.appendChild(telaLinha);
      grade.appendChild(bloco);
      desenharPresencas(telaLinha, metrica.pessoas, agora);
      tabela = this.tabelaDePessoas(metrica.pessoas);
    } else if (!metrica.serie) {
      /* sem série e sem pessoas: o número é o gráfico */
      topo.appendChild(el("h3", "lsa-bloco-titulo", metrica.rotulo));
      bloco.appendChild(topo);
      var heroi = el("div", "lsa-heroi");
      heroi.appendChild(el("strong", "", formatar(metrica.total, metrica.formato, "curto")));
      heroi.appendChild(el("span", "", metrica.rotulo.toLowerCase() + " · " + String(dados.periodo.titulo || "").toLowerCase()));
      var partes = variacao(metrica, dados.periodo);
      var linhaHeroi = el("span", "lsa-heroi-linha");
      linhaHeroi.appendChild(partes.pilula);
      linhaHeroi.appendChild(partes.antes);
      heroi.appendChild(linhaHeroi);
      bloco.appendChild(heroi);
      grade.appendChild(bloco);
    } else {
      var tituloDoGrafico = (metrica.titulos && metrica.titulos[unidade]) || (metrica.rotulo + " " + (TITULO_UNIDADE[unidade] || ""));
      topo.appendChild(el("h3", "lsa-bloco-titulo", tituloDoGrafico));
      if (metrica.forma !== "colunas" && metrica.serie_anterior) {
        var legenda = el("ul", "lsa-legenda");
        [[nomes.atual, ""], [nomes.anterior, " is-anterior"]].forEach(function (par) {
          var item = el("li");
          var chave = el("span", "lsa-chave" + par[1]);
          chave.setAttribute("aria-hidden", "true");
          item.appendChild(chave);
          item.appendChild(document.createTextNode(par[0]));
          legenda.appendChild(item);
        });
        topo.appendChild(legenda);
      } else if (metrica.distinta) {
        topo.appendChild(el("p", "lsa-bloco-sub", "pessoas diferentes em cada " + NOME_UNIDADE[unidade]));
      }
      bloco.appendChild(topo);
      bloco.appendChild(this.resumoDaSerie(metrica, dados));
      bloco.appendChild(telaLinha);
      grade.appendChild(bloco);
      if (metrica.forma === "colunas") {
        desenharColunas(telaLinha, dados.rotulos.map(function (rotulo, i) {
          return { curto: rotulo.curto, longo: rotulo.longo, valor: rotulo.futuro ? null : metrica.serie[i] };
        }), metrica, { altura: telaLinha.clientWidth < 480 ? 204 : 252, larguraDoRotulo: 58, titulo: tituloDoGrafico });
      } else {
        desenharLinha(telaLinha, dados.rotulos, metrica, unidade, nomes);
      }
      tabela = this.tabela(dados.rotulos, metrica, nomes);
    }
    if (tabela) bloco.appendChild(tabela);

    /* ---- por dia da semana ---- */
    if (semana) grade.appendChild(this.blocoDaSemana(semana, metrica, dados));

    /* ---- o ranking (ou a lista que entra no lugar dele) ---- */
    if (temRanking) grade.appendChild(temLista ? this.blocoDaLista(metrica.lista) : this.blocoDoRanking(metrica, dados));
  };

  /* Por dia da semana: sete barras deitadas, cada uma com o nome e o número
     (cabe de pé num cartão estreito ao lado do gráfico, e deitado no celular). */
  Analise.prototype.blocoDaSemana = function (semana, metrica, dados) {
    var bloco = el("section", "lsa-bloco lsa-bloco-semana");
    var topo = el("div", "lsa-bloco-topo");
    topo.appendChild(el("h3", "lsa-bloco-titulo", "Por dia da semana"));
    topo.appendChild(el("p", "lsa-bloco-sub", semana.media ? "média de cada dia" : "soma do período"));
    bloco.appendChild(topo);
    var valores = semana.valores;
    var nomes = dados.dias_da_semana;
    var maior = Math.max.apply(null, valores);
    var menor = Math.min.apply(null, valores);
    var melhores = [];
    var parados = [];
    valores.forEach(function (valor, i) {
      if (maior > 0 && valor === maior) melhores.push(nomes[i]);
      if (valor === menor) parados.push(nomes[i]);
    });
    var lista = el("ol", "lsa-semana");
    valores.forEach(function (valor, i) {
      var nome = nomes[i];
      var item = el("li", "lsa-semana-dia" + (maior > 0 && valor === maior && melhores.length <= 3 ? " is-melhor" : ""));
      item.setAttribute("aria-label", nome + ": " + formatar(valor, metrica.formato));
      var rotulo = el("span", "lsa-semana-nome", nome.slice(0, 3));
      rotulo.title = nome;
      rotulo.setAttribute("aria-hidden", "true");
      item.appendChild(rotulo);
      var trilho = el("span", "lsa-ranking-trilho");
      trilho.setAttribute("aria-hidden", "true");
      var barra = el("span", "lsa-ranking-barra");
      barra.style.width = (maior > 0 ? Math.max(valor > 0 ? 2 : 0, (valor / maior) * 100) : 0) + "%";
      if (!(valor > 0)) barra.style.minWidth = "0";
      trilho.appendChild(barra);
      item.appendChild(trilho);
      var numero = el("span", "lsa-semana-valor", formatar(valor, metrica.formato, "curto"));
      numero.setAttribute("aria-hidden", "true");
      item.appendChild(numero);
      lista.appendChild(item);
    });
    bloco.appendChild(lista);
    /* a frase de baixo só diz o que é verdade: com empate de muitos dias, não há "melhor dia" */
    function juntar(dias) {
      return dias.length === 1 ? dias[0] : dias.slice(0, -1).join(", ") + " e " + dias[dias.length - 1];
    }
    if (melhores.length && melhores.length <= 3) {
      var nota = el("p", "lsa-semana-nota");
      nota.appendChild(document.createTextNode(melhores.length === 1 ? "Melhor dia: " : "Melhores dias: "));
      nota.appendChild(el("strong", "", juntar(melhores)));
      if (menor < maior && parados.length === 1) {
        nota.appendChild(document.createTextNode(" · mais parado: "));
        nota.appendChild(el("strong", "", parados[0]));
      } else if (menor === 0 && parados.length > 1) {
        nota.appendChild(document.createTextNode(" · sem movimento em " + parados.length + " dias da semana"));
      }
      bloco.appendChild(nota);
    }
    return bloco;
  };

  function linkDaFicha(nome, tipo, id, opcoes) {
    if (id === null || id === undefined || !Ficha.temItem(tipo)) return document.createTextNode(nome);
    var link = el("a", "", nome);
    link.href = "#";
    link.title = "Abrir " + nome;
    link.addEventListener("click", function (evento) {
      evento.preventDefault();
      opcoes = opcoes || {};
      opcoes.origem = link;
      Ficha.abrir(tipo, id, opcoes);
    });
    return link;
  }

  Analise.prototype.blocoDoRanking = function (metrica, dados) {
    var eu = this;
    var bloco = el("section", "lsa-bloco lsa-bloco-ranking");
    var topo = el("div", "lsa-bloco-topo");
    topo.appendChild(el("h3", "lsa-bloco-titulo", dados.ranking_titulo || "Quem mais rendeu"));
    var unidade = metrica.ranking_unidade;
    topo.appendChild(el("p", "lsa-bloco-sub", unidade ? "por " + unidade[1] : "em " + metrica.rotulo.toLowerCase()));
    bloco.appendChild(topo);
    var lista = metrica.ranking || [];
    var topoValor = lista[0].valor || 1;
    var ol = el("ol", "lsa-ranking");
    lista.forEach(function (item, i) {
      var li = el("li", "lsa-ranking-item" + (item.avatar ? " tem-avatar" : ""));
      li.appendChild(el("span", "lsa-ranking-pos", i + 1));
      if (item.avatar) li.appendChild(avatar(item.avatar.iniciais, item.avatar.cor, "is-pequeno" + (item.online ? " is-online" : "")));
      var nome = el("span", "lsa-ranking-nome");
      var titulo = el("span");
      titulo.appendChild(linkDaFicha(item.nome, item.tipo || dados.tipo, item.id, { aba: "graficos", periodo: eu.periodo }));
      nome.appendChild(titulo);
      if (item.detalhe) nome.appendChild(el("small", item.online ? "is-online" : "", item.detalhe));
      li.appendChild(nome);
      var valor = unidade
        ? NUM.format(item.valor) + " " + plural(item.valor, unidade[0], unidade[1]).split(" ")[0]
        : formatar(item.valor, metrica.formato, "curto");
      li.appendChild(el("span", "lsa-ranking-valor", valor));
      var trilho = el("span", "lsa-ranking-trilho");
      trilho.setAttribute("aria-hidden", "true");
      var barra = el("span", "lsa-ranking-barra");
      barra.style.width = Math.max(2, (item.valor / topoValor) * 100) + "%";
      trilho.appendChild(barra);
      li.appendChild(trilho);
      ol.appendChild(li);
    });
    bloco.appendChild(ol);
    return bloco;
  };

  /* A lista que entra no lugar do ranking (os cadastros mais recentes, por exemplo). */
  Analise.prototype.blocoDaLista = function (lista) {
    var bloco = el("section", "lsa-bloco lsa-bloco-ranking");
    var topo = el("div", "lsa-bloco-topo");
    topo.appendChild(el("h3", "lsa-bloco-titulo", lista.titulo));
    if (lista.sub) topo.appendChild(el("p", "lsa-bloco-sub", lista.sub));
    bloco.appendChild(topo);
    var ul = el("ul", "lsa-recentes-lista");
    lista.itens.forEach(function (item) {
      var li = el("li");
      if (item.avatar) li.appendChild(avatar(item.avatar.iniciais, item.avatar.cor, "is-pequeno"));
      var nome = el("span", "lsa-ranking-nome");
      var titulo = el("span");
      titulo.appendChild(linkDaFicha(item.nome, item.tipo, item.id, {}));
      nome.appendChild(titulo);
      if (item.detalhe) nome.appendChild(el("small", "", item.detalhe));
      li.appendChild(nome);
      if (item.quando) li.appendChild(el("span", "lsa-recentes-quando", item.quando));
      ul.appendChild(li);
    });
    bloco.appendChild(ul);
    return bloco;
  };

  /* a tabela: o gêmeo acessível de todo gráfico */
  function caixaDaTabela(cabecalhos, linhas) {
    var detalhes = el("details", "lsa-tabela");
    var resumo = el("summary");
    resumo.appendChild(icone("bi-table"));
    resumo.appendChild(document.createTextNode("Ver os números em tabela"));
    detalhes.appendChild(resumo);
    var rolagem = el("div", "lsa-tabela-rolagem");
    var tabela = el("table");
    var cabeca = el("thead");
    var linha = el("tr");
    cabecalhos.forEach(function (texto) {
      var th = el("th", "", texto);
      th.scope = "col";
      linha.appendChild(th);
    });
    cabeca.appendChild(linha);
    tabela.appendChild(cabeca);
    var corpo = el("tbody");
    linhas.forEach(function (celulas) {
      var tr = el("tr");
      celulas.forEach(function (texto) { tr.appendChild(el("td", "", texto)); });
      corpo.appendChild(tr);
    });
    tabela.appendChild(corpo);
    rolagem.appendChild(tabela);
    detalhes.appendChild(rolagem);
    return detalhes;
  }

  Analise.prototype.tabela = function (rotulos, metrica, nomes) {
    var cabecalhos = ["Quando", nomes.atual.charAt(0).toUpperCase() + nomes.atual.slice(1)];
    if (metrica.serie_anterior) cabecalhos.push(nomes.anterior.charAt(0).toUpperCase() + nomes.anterior.slice(1));
    var linhas = [];
    rotulos.forEach(function (rotulo, i) {
      if (rotulo.futuro) return;
      var celulas = [rotulo.longo, formatar(metrica.serie[i], metrica.formato)];
      if (metrica.serie_anterior) celulas.push(formatar(metrica.serie_anterior[i], metrica.formato));
      linhas.push(celulas);
    });
    return caixaDaTabela(cabecalhos, linhas);
  };

  Analise.prototype.tabelaDePessoas = function (pessoas) {
    return caixaDaTabela(["Conta", "Papel", "Primeiro sinal", "Último sinal"], pessoas.itens.map(function (pessoa) {
      return [pessoa.nome, pessoa.papel_rotulo, pessoa.de, pessoa.ate];
    }));
  };

  /* ------------------------------------------------------------------
     AGORA: quem está online (tela Usuários)

     A faixa não pergunta nada ao servidor: assina o relógio do
     interno/ls-presenca.js, que traz as contas online, as vistas nas
     últimas 24 h e os contadores. Tocar numa pessoa abre a ficha dela;
     tocar num contador filtra a lista de contas da tela.

     O FILTRO É DO SERVIDOR (?presenca=hoje): a lista é paginada, 18 por
     página, e filtrar só as linhas que vieram deixaria de fora quem está
     na página 3. Cada contador é um LINK para a mesma tela com o filtro (a
     busca e o perfil escolhidos continuam valendo, e a página volta para a
     primeira), com a âncora da lista -- a navegação suave do painel troca
     a tela sem recarregar e a tela chega na lista, e não no topo.
     ------------------------------------------------------------------ */
  var FILTROS = [
    { codigo: "", rotulo: "Todas", icone: "bi-people", numero: "total" },
    { codigo: "online", rotulo: "Online", icone: "", numero: "online" },
    { codigo: "hoje", rotulo: "Ativos hoje", icone: "bi-sun", numero: "hoje" },
    { codigo: "semana", rotulo: "Em 7 dias", icone: "bi-calendar-week", numero: "semana" },
    { codigo: "mes", rotulo: "Em 30 dias", icone: "bi-calendar3", numero: "mes" },
    { codigo: "nunca", rotulo: "Nunca entraram", icone: "bi-person-dash", numero: "nunca" }
  ];

  /* O endereço da mesma tela com o contador escolhido (ou sem nenhum). */
  function enderecoDoFiltro(codigo) {
    var parametros = new URLSearchParams(window.location.search);
    parametros.delete("page");
    if (codigo) parametros.set("presenca", codigo);
    else parametros.delete("presenca");
    var consulta = parametros.toString();
    var lista = document.querySelector("[data-lsa-ancora]");
    return window.location.pathname + (consulta ? "?" + consulta : "") + (lista && lista.id ? "#" + lista.id : "");
  }

  function filtroDaTela() {
    var codigo = new URLSearchParams(window.location.search).get("presenca") || "";
    return FILTROS.some(function (f) { return f.codigo === codigo; }) ? codigo : "";
  }
  var ICONE_DE_ONDE = { painel: "bi-window-sidebar", site: "bi-globe2", app: "bi-phone" };
  var MAXIMO_DE_CARTOES = 12;

  function cartaoDaPessoa(pessoa, compacto) {
    var cartao = el("div", "lsa-pessoa" + (compacto ? " is-compacta" : "") + (pessoa.voce ? " is-voce" : ""));
    cartao.dataset.detalheTipo = "usuario";
    cartao.dataset.detalheId = pessoa.id;
    cartao.dataset.detalheAtalho = "nao";
    cartao.setAttribute("role", "button");
    var lugar = pessoa.onde_rotulo ? " no " + pessoa.onde_rotulo : "";
    cartao.setAttribute("aria-label", pessoa.nome + (pessoa.voce ? " (você)" : "") + ", " + pessoa.papel_rotulo +
      (pessoa.online ? ", online" + lugar + ", " + (pessoa.quando === "agora" ? "agora" : "último sinal " + pessoa.quando) : ", " + (pessoa.quando === "agora" ? "visto agora há pouco" : "visto " + pessoa.quando)) + ". Abrir a ficha");
    cartao.appendChild(avatar(pessoa.iniciais, pessoa.cor, (compacto ? "is-pequeno" : "") + (pessoa.online ? " is-online" : "")));
    var texto = el("span", "lsa-pessoa-texto");
    var nome = el("span", "lsa-pessoa-nome");
    nome.appendChild(el("span", "", pessoa.nome));
    if (pessoa.voce) nome.appendChild(el("span", "lsa-voce", "Você"));
    texto.appendChild(nome);
    var linha = el("span", "lsa-pessoa-linha");
    linha.appendChild(el("span", "lsa-papel is-" + pessoa.papel, pessoa.papel_rotulo));
    if (compacto) {
      linha.appendChild(document.createTextNode(pessoa.quando === "agora" ? "há instantes" : pessoa.quando));
    } else {
      if (pessoa.onde_rotulo) {
        var lugarNo = el("span", "lsa-pessoa-onde");
        lugarNo.appendChild(icone(ICONE_DE_ONDE[pessoa.onde] || "bi-geo"));
        lugarNo.appendChild(document.createTextNode(pessoa.onde_rotulo));
        linha.appendChild(lugarNo);
      }
      linha.appendChild(el("span", "lsa-pessoa-quando", pessoa.quando));
    }
    texto.appendChild(linha);
    cartao.appendChild(texto);
    return cartao;
  }

  function Agora(faixa) {
    this.faixa = faixa;
    this.titulo = faixa.querySelector("[data-lsa-agora-titulo]");
    this.relogio = faixa.querySelector("[data-lsa-agora-relogio]");
    this.corpo = faixa.querySelector("[data-lsa-agora-corpo]");
    this.assinatura = "";
    this.dados = null;
    var eu = this;
    if (!window.LSPresenca) {
      faixa.hidden = true;
      return;
    }
    window.LSPresenca.assinar(function (dados, erro) { eu.receber(dados, erro); }, { contas: true, no: faixa });
  }

  Agora.prototype.receber = function (dados, erro) {
    if (!dados) {
      /* a pergunta falhou: fica o último retrato, com o aviso de que é antigo */
      this.faixa.classList.add("is-sem-rede");
      if (this.dados) {
        this.relogio.textContent = "sem conexão · mostrando o retrato das " + this.dados.agora.slice(11, 16);
      } else {
        this.faixa.removeAttribute("aria-busy");
        this.titulo.textContent = "Quem está online";
        this.relogio.textContent = "";
        this.corpo.textContent = "";
        this.corpo.appendChild(avisoGrande({
          icone: "bi-wifi-off",
          titulo: "Não deu para ver quem está online",
          texto: "A faixa tenta de novo sozinha em instantes; o resto da tela continua funcionando.",
          acao: "Tentar agora",
          aoTocar: function () { if (window.LSPresenca) window.LSPresenca.atualizar(); }
        }));
      }
      return;
    }
    if (!dados.numeros) return;  /* resposta só da equipe (a pergunta das contas vem em seguida) */
    this.faixa.classList.remove("is-sem-rede");
    this.faixa.removeAttribute("aria-busy");
    this.dados = dados;
    var online = dados.numeros.online;
    this.titulo.textContent = NUM.format(online) + " online agora";
    this.relogio.textContent = "atualizado às " + dados.agora.slice(11, 16) + " · atualiza sozinho";
    /* só redesenha quando algo mudou: quem está com o dedo num cartão não o perde a cada 45 s */
    var assinatura = JSON.stringify([dados.online, dados.recentes, dados.numeros, dados.recentes_total]);
    if (assinatura !== this.assinatura) {
      this.assinatura = assinatura;
      this.desenhar(dados);
    }
    atualizarLinhas(dados);
  };

  Agora.prototype.desenhar = function (dados) {
    var eu = this;
    var foco = document.activeElement && this.corpo.contains(document.activeElement) ? document.activeElement : null;
    var focoId = foco && foco.dataset ? foco.dataset.detalheId : null;
    var focoFiltro = foco && foco.dataset && foco.dataset.lsaFiltro !== undefined ? foco.dataset.lsaFiltro : null;
    var escolhido = filtroDaTela();
    this.corpo.textContent = "";

    var online = dados.online || [];
    var cartoes = el("div", "lsa-pessoas");
    cartoes.setAttribute("role", "list");
    cartoes.setAttribute("aria-label", "Contas online agora");
    online.slice(0, MAXIMO_DE_CARTOES).forEach(function (pessoa) {
      var item = el("div", "lsa-pessoas-item");
      item.setAttribute("role", "listitem");
      item.appendChild(cartaoDaPessoa(pessoa, false));
      cartoes.appendChild(item);
    });
    var resto = Math.max(online.length, dados.numeros.online) - Math.min(online.length, MAXIMO_DE_CARTOES);
    if (resto > 0) {
      var mais = el("a", "lsa-pessoa-mais");
      mais.href = enderecoDoFiltro("online");
      mais.appendChild(el("strong", "", "+" + NUM.format(resto)));
      mais.appendChild(el("span", "", "ver na lista"));
      cartoes.appendChild(mais);
    }
    this.corpo.appendChild(cartoes);

    var bloco = el("div", "lsa-vistos");
    var titulo = el("h3", "lsa-vistos-titulo");
    titulo.appendChild(icone("bi-clock-history"));
    titulo.appendChild(document.createTextNode("Vistos por último"));
    titulo.appendChild(el("small", "", "nas últimas " + (dados.recentes_horas || 24) + " h"));
    bloco.appendChild(titulo);
    var recentes = dados.recentes || [];
    if (recentes.length) {
      var lista = el("div", "lsa-pessoas is-compacta");
      lista.setAttribute("role", "list");
      lista.setAttribute("aria-label", "Contas vistas nas últimas horas");
      recentes.forEach(function (pessoa) {
        var item = el("div", "lsa-pessoas-item");
        item.setAttribute("role", "listitem");
        item.appendChild(cartaoDaPessoa(pessoa, true));
        lista.appendChild(item);
      });
      var fora = (dados.recentes_total || recentes.length) - recentes.length;
      if (fora > 0) lista.appendChild(el("span", "lsa-pessoa-resto", "e mais " + NUM.format(fora)));
      bloco.appendChild(lista);
    } else {
      var ninguem = el("p", "lsa-vistos-vazio");
      ninguem.appendChild(icone("bi-moon-stars"));
      ninguem.appendChild(el("span", "", "Ninguém mais passou por aqui nas últimas " + (dados.recentes_horas || 24) + " horas."));
      bloco.appendChild(ninguem);
    }
    this.corpo.appendChild(bloco);

    /* os contadores: links (o filtro é do servidor), com o desenho das pílulas de período */
    var filtros = el("nav", "lsa-filtros");
    filtros.setAttribute("aria-label", "Filtrar a lista de contas");
    filtros.appendChild(el("span", "lsa-filtros-titulo", "Filtrar a lista de contas"));
    FILTROS.forEach(function (filtro) {
      var numero = dados.numeros[filtro.numero];
      var link = el("a", "lsa-filtro" + (filtro.codigo === "online" ? " is-vivo" : ""));
      link.href = enderecoDoFiltro(filtro.codigo);
      link.dataset.lsaFiltro = filtro.codigo;
      if (filtro.codigo === escolhido) link.setAttribute("aria-current", "true");
      if (filtro.codigo === "online") {
        var ponto = el("span", "lsa-ponto-vivo");
        ponto.setAttribute("aria-hidden", "true");
        link.appendChild(ponto);
      } else {
        link.appendChild(icone(filtro.icone));
      }
      link.appendChild(el("span", "", filtro.rotulo));
      if (temValor(numero)) link.appendChild(el("strong", "", NUM.format(numero)));
      filtros.appendChild(link);
    });
    this.corpo.appendChild(filtros);

    prepararItens(this.corpo);
    if (focoId) {
      var mesmo = this.corpo.querySelector('[data-detalhe-id="' + focoId + '"]');
      if (mesmo) mesmo.focus({ preventScroll: true });
    } else if (focoFiltro !== null) {
      var linkDeAntes = this.corpo.querySelector('[data-lsa-filtro="' + focoFiltro + '"]');
      if (linkDeAntes) linkDeAntes.focus({ preventScroll: true });
    }
    manterAncora();
  };

  /* O selo de cada linha da lista acompanha a faixa: quem entrou no ar com a
     tela aberta vira "Online agora"; quem saiu, "Visto há 6 min". */
  function seloDaLinha(linha, online, texto) {
    var selo = linha.querySelector("[data-lsa-selo]");
    if (!selo) return;
    selo.textContent = "";
    selo.className = "lsa-presenca" + (online ? " is-online" : "");
    if (online) {
      var ponto = el("span", "lsa-ponto-vivo");
      ponto.setAttribute("aria-hidden", "true");
      selo.appendChild(ponto);
      selo.title = "Deu sinal de vida nos últimos minutos";
    } else {
      selo.appendChild(icone("bi-clock-history"));
      selo.title = "A última vez em que a conta usou o site, o aplicativo ou o painel";
    }
    selo.appendChild(document.createTextNode(texto));
  }

  function atualizarLinhas(dados) {
    var online = {};
    (dados.online || []).forEach(function (pessoa) { online[pessoa.id] = pessoa; });
    var recentes = {};
    (dados.recentes || []).forEach(function (pessoa) { recentes[pessoa.id] = pessoa; });
    document.querySelectorAll("[data-presenca][data-detalhe-id]").forEach(function (linha) {
      var grupos = (linha.dataset.presenca || "").split(" ").filter(Boolean);
      var estava = grupos.indexOf("online") !== -1;
      var esta = !!online[linha.dataset.detalheId];
      if (esta === estava) return;
      if (esta) {
        grupos = ["online", "hoje", "semana", "mes"];
        seloDaLinha(linha, true, "Online agora");
      } else {
        grupos = grupos.filter(function (g) { return g !== "online"; });
        var pessoa = recentes[linha.dataset.detalheId];
        seloDaLinha(linha, false, "Visto " + (pessoa && pessoa.quando !== "agora" ? pessoa.quando : "há pouco"));
      }
      linha.dataset.presenca = grupos.join(" ");
    });
  }

  /* A ÂNCORA DA LISTA. Os contadores, o paginador e a busca levam
     "#usrContas": a tela deve chegar na lista, e não no topo. Numa carga
     normal o navegador cuida disso -- mas o painel de cima ainda vai crescer
     (os números chegam depois) e empurraria a lista para baixo. E na
     navegação suave do painel a tela nova sempre começa do topo e o endereço
     perde o "#" (ela usa o endereço da resposta). Por isso o toque num link
     com âncora fica anotado, e depois de cada desenho a âncora é mirada de
     novo, por uns segundos, até a pessoa mexer na tela. */
  var ancora = null;
  var ancoraPedida = null;

  function idDaAncora(endereco) {
    var corte = String(endereco || "").indexOf("#");
    var id = corte === -1 ? "" : String(endereco).slice(corte + 1);
    return /^[\w-]+$/.test(id) ? id : "";
  }

  function mirarAncora() {
    var pedida = ancoraPedida && Date.now() - ancoraPedida.em < 20000 ? ancoraPedida.id : "";
    ancoraPedida = null;
    var id = pedida || idDaAncora(window.location.hash);
    var alvo = id ? document.getElementById(id) : null;
    ancora = alvo && alvo.hasAttribute("data-lsa-ancora") ? { alvo: alvo, ate: Date.now() + 6000 } : null;
    if (ancora && pedida && window.history && window.history.replaceState && !window.location.hash) {
      /* a âncora volta para o endereço: recarregar a página cai no mesmo lugar */
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search + "#" + id);
    }
    manterAncora();
  }

  function manterAncora() {
    if (!ancora) return;
    if (Date.now() > ancora.ate || !document.contains(ancora.alvo)) { ancora = null; return; }
    ancora.alvo.scrollIntoView({ block: "start" });
  }

  function anotarAncora(endereco) {
    var id = idDaAncora(endereco);
    var alvo = id ? document.getElementById(id) : null;
    if (alvo && alvo.hasAttribute("data-lsa-ancora")) ancoraPedida = { id: id, em: Date.now() };
  }

  /* na captura: antes de a navegação suave pegar o clique */
  document.addEventListener("click", function (evento) {
    var link = evento.target.closest ? evento.target.closest("a[href]") : null;
    if (link) anotarAncora(link.getAttribute("href"));
  }, true);
  document.addEventListener("submit", function (evento) {
    if (evento.target && evento.target.getAttribute) anotarAncora(evento.target.getAttribute("action"));
  }, true);

  ["wheel", "touchmove", "keydown"].forEach(function (evento) {
    window.addEventListener(evento, function () { ancora = null; }, { passive: true });
  });

  function montarAgora(faixa) {
    if (faixa.dataset.lsaPronto) return;
    faixa.dataset.lsaPronto = "1";
    faixa.lsaAgora = new Agora(faixa);
  }

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
      resumo.appendChild(esqueleto("Buscando a ficha completa…"));
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
      var podeTentar = status !== 403 && status !== 404;
      resumo.appendChild(avisoGrande({
        erro: true,
        icone: status === 403 ? "bi-shield-lock" : (status === 404 ? "bi-search" : "bi-wifi-off"),
        titulo: status === 403 ? "Sua conta não abre esta ficha" : (status === 404 ? "Este item não existe mais" : "A ficha não abriu"),
        texto: mensagem || "Não foi possível buscar a ficha.",
        acao: podeTentar ? "Tentar de novo" : null,
        aoTocar: function () { eu.estadoCarregando(); eu.carregar(); }
      }));
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
      if (ficha.avatar) {
        capa.appendChild(avatar(ficha.avatar.iniciais, ficha.avatar.cor, "is-grande" + (ficha.presenca && ficha.presenca.online ? " is-online" : "")));
      } else if (ficha.imagem) {
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
        parte.textContent = "";
        parte.appendChild(avisoGrande({
          icone: "bi-clock-history",
          titulo: "Nada por aqui ainda",
          texto: "Quando houver movimento (pedidos, curtidas, acessos), ele aparece nesta linha do tempo, do mais novo para o mais antigo."
        }));
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
            mais.textContent = "Tentar de novo";
            recado((erro && erro.message) || "Não deu para buscar mais atividade agora.", "erro");
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
    raiz = raiz || document;
    raiz.querySelectorAll("[data-lsa-painel]").forEach(montarPainel);
    raiz.querySelectorAll("[data-lsa-agora]").forEach(montarAgora);
    Ficha.preparar();
    prepararItens(raiz);
  }

  window.LSAnalises = { montar: montar, abrir: function (tipo, id, opcoes) { Ficha.abrir(tipo, id, opcoes); } };

  function iniciar() {
    montar(document);
    mirarAncora();
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
  document.addEventListener("ls:tela", function () {
    paineis = [];
    montar(document);
    /* um instante depois: a navegação suave rola para o topo logo após este aviso */
    window.setTimeout(mirarAncora, 40);
  });
})(window, document);
