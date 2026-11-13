/* ======================================================================
   O FUNIL NO PAINEL: PRAZO DE PRODUÇÃO, ETIQUETAS E ANDAMENTO
   LEIA-ME-V10, seção 89. O servidor é sistema_interno/views_funil.py.

   Três peças, todas por delegação no documento -- funcionam na tela que
   abre direto, na que chega pela navegação suave e no trecho da lista que
   o filtro troca, sem ninguém "ligar" nada de novo:

     [data-prazo-url]       o campo do prazo (dias úteis) na linha do
                            pedido, na janela do orçamento e na lista da
                            produção: grava sozinho ao sair do campo (ou no
                            Enter), sem recarregar, e mostra a previsão.
     [data-etiquetas-url]   o botão "Etiquetas": abre a folha de cópias --
                            cada máquina com "quantas cópias por máquina",
                            o total e quantas folhas A4 dá -- e o
                            "Imprimir" abre as folhas numa aba nova.
     [data-andamento-url]   o andamento do pedido do site (Financeiro e
                            Gestão): a folha com os passos; cancelar
                            pergunta antes, pela folha do LSAviso (nunca
                            a caixa cinza do navegador).

   As folhas são as do ls-aviso (as mesmas classes `ls-recado-folha*`):
   cartão no meio no computador, folha que sobe de baixo no celular, cores
   do sol, da lua e do eclipse.
   ====================================================================== */
(function (window, document) {
  "use strict";

  if (window.LSProducao) return;

  /* ------------------------------------------------------------ apoio */
  function csrf() {
    var campo = document.querySelector("[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function avisar(nivel, titulo, texto) {
    if (window.LSAviso) {
      window.LSAviso.toast({ nivel: nivel, titulo: titulo, texto: texto || "" });
    }
  }

  function erroDe(resposta, padrao) {
    return resposta.json().catch(function () { return {}; }).then(function (corpo) {
      throw new Error((corpo && corpo.msg) || padrao);
    });
  }

  function postar(url, campos) {
    var dados = new FormData();
    Object.keys(campos).forEach(function (chave) { dados.append(chave, campos[chave]); });
    dados.append("csrfmiddlewaretoken", csrf());
    return fetch(url, {
      method: "POST",
      body: dados,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" }
    }).then(function (resposta) {
      if (!resposta.ok) return erroDe(resposta, "Não foi possível gravar agora. Tente de novo.");
      return resposta.json();
    });
  }

  function buscar(url) {
    return fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
    }).then(function (resposta) {
      if (!resposta.ok) return erroDe(resposta, "Não foi possível abrir agora. Tente de novo.");
      return resposta.json();
    });
  }

  function criar(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto != null) el.textContent = texto;
    return el;
  }

  function icone(nome) {
    var i = criar("i", "bi " + nome);
    i.setAttribute("aria-hidden", "true");
    return i;
  }

  function plural(n, um, varios) {
    return n + " " + (n === 1 ? um : varios);
  }

  var contador = 0;

  /* ==================================================================
     1. O PRAZO DE PRODUÇÃO
     ================================================================== */

  /* O campo, montado por quem não tem HTML pronto (a janela do orçamento,
     a folha de etiquetas). O HTML do servidor é o mesmo desenho
     (includes/prazo_producao.html). */
  function campoPrazo(prazo, opcoes) {
    opcoes = opcoes || {};
    contador += 1;
    var id = "lsPrazo" + contador;
    var caixa = criar("div", "ls-prazo" + (opcoes.compacto ? " compacto" : ""));
    caixa.dataset.prazoUrl = prazo.url;
    var rotulo = criar("label", "ls-prazo-rotulo");
    rotulo.htmlFor = id;
    rotulo.appendChild(icone("bi-hourglass-split"));
    rotulo.appendChild(document.createTextNode(" Produção"));
    var campo = criar("span", "ls-prazo-campo");
    var entrada = criar("input");
    entrada.id = id;
    entrada.type = "number";
    entrada.inputMode = "numeric";
    entrada.min = "0";
    entrada.max = "250";
    entrada.step = "1";
    entrada.placeholder = "—";
    entrada.value = prazo.dias == null ? "" : String(prazo.dias);
    entrada.dataset.prazoValor = entrada.value;
    entrada.setAttribute("aria-describedby", id + "Nota");
    entrada.disabled = prazo.editavel === false;
    var unidade = criar("span", "ls-prazo-unidade", "dias úteis");
    unidade.setAttribute("aria-hidden", "true");
    campo.appendChild(entrada);
    campo.appendChild(unidade);
    var nota = criar("small", "ls-prazo-nota", prazo.nota || "");
    nota.id = id + "Nota";
    nota.dataset.prazoNota = "";
    caixa.appendChild(rotulo);
    caixa.appendChild(campo);
    caixa.appendChild(nota);
    return caixa;
  }

  function salvarPrazo(entrada) {
    var caixa = entrada.closest("[data-prazo-url]");
    if (!caixa) return;
    var valor = entrada.value.trim();
    var antes = entrada.dataset.prazoValor || "";
    if (valor === antes) return;
    caixa.classList.remove("is-salvo", "is-erro");
    caixa.classList.add("is-salvando");
    postar(caixa.dataset.prazoUrl, { prazo: valor }).then(function (corpo) {
      var prazo = corpo.prazo || {};
      var novo = prazo.dias == null ? "" : String(prazo.dias);
      entrada.value = novo;
      entrada.dataset.prazoValor = novo;
      var nota = caixa.querySelector("[data-prazo-nota]");
      if (nota) nota.textContent = prazo.nota || "";
      caixa.classList.remove("is-salvando");
      caixa.classList.add("is-salvo");
      window.setTimeout(function () { caixa.classList.remove("is-salvo"); }, 1600);
      avisar("sucesso", "Prazo salvo", corpo.msg);
      caixa.dispatchEvent(new CustomEvent("ls:prazo-salvo", { bubbles: true, detail: prazo }));
    }).catch(function (erro) {
      entrada.value = antes;
      caixa.classList.remove("is-salvando");
      caixa.classList.add("is-erro");
      avisar("erro", "Prazo não salvo", erro.message);
    });
  }

  document.addEventListener("change", function (evento) {
    var entrada = evento.target;
    if (entrada && entrada.matches && entrada.matches("[data-prazo-url] input")) salvarPrazo(entrada);
  });

  /* Enter grava (e não envia o formulário da janela em volta). */
  document.addEventListener("keydown", function (evento) {
    var entrada = evento.target;
    if (evento.key !== "Enter" || !entrada || !entrada.matches || !entrada.matches("[data-prazo-url] input")) return;
    evento.preventDefault();
    evento.stopPropagation();
    salvarPrazo(entrada);
  }, true);

  /* ==================================================================
     A FOLHA (o casco comum às duas folhas abaixo)
     ================================================================== */
  function semMovimento() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function noCelular() {
    return window.matchMedia && window.matchMedia("(max-width: 640px)").matches;
  }

  function abrirFolha(classe, montar) {
    contador += 1;
    var id = "lsFolhaProducao" + contador;
    var janela = criar("dialog", "ls-recado-folha ls-folha-producao " + (classe || ""));
    janela.setAttribute("aria-labelledby", id + "Titulo");
    var cartao = criar("form", "ls-recado-folha-cartao ls-folha-producao-cartao");
    cartao.method = "dialog";
    cartao.noValidate = true;
    var alca = criar("span", "ls-recado-folha-alca");
    alca.setAttribute("aria-hidden", "true");
    cartao.appendChild(alca);
    janela.appendChild(cartao);

    var anterior = document.activeElement;
    var fechada = false;

    function fechar() {
      if (fechada) return;
      fechada = true;
      janela.classList.add("is-saindo");
      window.setTimeout(function () {
        try { if (janela.open) janela.close(); } catch (erro) { /* nada */ }
        janela.remove();
        document.documentElement.classList.remove("ls-recado-travado");
        if (anterior && anterior.isConnected && typeof anterior.focus === "function") {
          try { anterior.focus({ preventScroll: true }); } catch (erro) { /* nada */ }
        }
      }, semMovimento() ? 0 : 170);
    }

    /* O envio desta folha é só dela: nem a navegação suave nem a barra de
       carregamento precisam saber. */
    cartao.addEventListener("submit", function (evento) {
      evento.preventDefault();
      evento.stopPropagation();
    });
    janela.addEventListener("cancel", function (evento) {
      evento.preventDefault();
      fechar();
    });
    janela.addEventListener("click", function (evento) {
      if (evento.target === janela) fechar();
    });

    /* No celular a folha desce com o dedo, como as do aparelho. */
    var inicio = null;
    cartao.addEventListener("pointerdown", function (evento) {
      if (!noCelular() || evento.button !== 0 || evento.target.closest("button, a, input, label, select, textarea")) return;
      if (cartao.scrollTop > 0) return;
      inicio = { y: evento.clientY, id: evento.pointerId, dy: 0 };
    });
    cartao.addEventListener("pointermove", function (evento) {
      if (!inicio || evento.pointerId !== inicio.id) return;
      inicio.dy = Math.max(0, evento.clientY - inicio.y);
      if (inicio.dy > 6) {
        cartao.classList.add("is-arrastando");
        cartao.style.transform = "translateY(" + inicio.dy + "px)";
      }
    });
    function soltar(evento) {
      if (!inicio || evento.pointerId !== inicio.id) return;
      var dy = inicio.dy;
      inicio = null;
      cartao.classList.remove("is-arrastando");
      cartao.style.transform = "";
      if (dy > 90) fechar();
    }
    cartao.addEventListener("pointerup", soltar);
    cartao.addEventListener("pointercancel", soltar);

    var foco = montar(cartao, fechar, id);

    document.body.appendChild(janela);
    document.documentElement.classList.add("ls-recado-travado");
    if (typeof janela.showModal === "function") {
      janela.showModal();
    } else {
      janela.setAttribute("open", "");
      janela.classList.add("sem-camada");
    }
    if (foco && typeof foco.focus === "function") foco.focus();
    return { janela: janela, fechar: fechar };
  }

  function cabecalho(cartao, id, nomeIcone, titulo, subtitulo) {
    var topo = criar("div", "ls-folha-producao-topo");
    var marca = criar("span", "ls-folha-producao-icone");
    marca.appendChild(icone(nomeIcone));
    var textos = criar("div", "ls-folha-producao-textos");
    var h = criar("h2", "ls-recado-folha-titulo", titulo);
    h.id = id + "Titulo";
    textos.appendChild(h);
    if (subtitulo) textos.appendChild(criar("p", "ls-folha-producao-sub", subtitulo));
    topo.appendChild(marca);
    topo.appendChild(textos);
    cartao.appendChild(topo);
  }

  /* ==================================================================
     2. A FOLHA DE CÓPIAS DAS ETIQUETAS
     ================================================================== */
  function folhaDeEtiquetas(ficha) {
    abrirFolha("ls-folha-etiquetas-maquinas", function (cartao, fechar, id) {
      cabecalho(cartao, id, "bi-upc-scan", "Imprimir etiquetas",
        ficha.titulo + (ficha.nome ? " · " + ficha.nome : ""));

      var botoes = criar("div", "ls-recado-folha-botoes");
      var cancelar = criar("button", "ls-recado-botao", ficha.pronta ? "Cancelar" : "Fechar");
      cancelar.type = "button";
      cancelar.addEventListener("click", fechar);

      /* O prazo também mora aqui: quem imprime a etiqueta é quem
         acabou de fabricar, e a data de "pronto" sai dele. */
      if (ficha.prazo) {
        var producao = criar("div", "ls-folha-producao-bloco");
        producao.appendChild(campoPrazo(ficha.prazo, { compacto: true }));
        cartao.appendChild(producao);
      }

      if (!ficha.pronta) {
        var aviso = criar("p", "ls-folha-producao-aviso");
        aviso.appendChild(icone("bi-info-circle"));
        aviso.appendChild(document.createTextNode(" " + (ficha.motivo || "Este registro ainda não imprime etiquetas.")));
        cartao.appendChild(aviso);
        botoes.appendChild(cancelar);
        cartao.appendChild(botoes);
        return cancelar;
      }

      /* O tamanho da etiqueta: os dois que a tela de Etiquetas já tinha. */
      var tamanhos = criar("fieldset", "ls-folha-producao-tamanhos");
      var legenda = criar("legend", "", "Tamanho da etiqueta");
      tamanhos.appendChild(legenda);
      var grade = criar("div", "ls-folha-producao-opcoes");
      ficha.tamanhos.forEach(function (tamanho) {
        var opcao = criar("label", "ls-folha-producao-opcao");
        var radio = criar("input");
        radio.type = "radio";
        radio.name = id + "Tamanho";
        radio.value = tamanho.valor;
        radio.checked = tamanho.valor === ficha.tamanho;
        radio.dataset.porFolha = tamanho.por_folha;
        var textos = criar("span");
        textos.appendChild(criar("strong", "", tamanho.rotulo));
        textos.appendChild(criar("small", "", tamanho.nota));
        opcao.appendChild(radio);
        opcao.appendChild(textos);
        grade.appendChild(opcao);
      });
      tamanhos.appendChild(grade);
      cartao.appendChild(tamanhos);

      /* As máquinas, cada uma com "quantas cópias por máquina". */
      var lista = criar("ul", "ls-folha-producao-maquinas");
      lista.setAttribute("aria-label", "Cópias por máquina");
      var entradas = [];
      ficha.maquinas.forEach(function (maquina) {
        var linha = criar("li", "ls-folha-producao-maquina");
        var nome = criar("div", "ls-folha-producao-maquina-nome");
        nome.appendChild(criar("strong", "", maquina.nome));
        var detalhe = criar("small", "", maquina.quantidade > 1 ? maquina.quantidade + " unidades" : "1 unidade");
        nome.appendChild(detalhe);
        var passo = criar("div", "ls-passo");
        var menos = criar("button", "ls-passo-botao");
        menos.type = "button";
        menos.setAttribute("aria-label", "Uma cópia a menos de " + maquina.nome);
        menos.appendChild(icone("bi-dash-lg"));
        var entrada = criar("input", "ls-passo-valor");
        entrada.type = "number";
        entrada.inputMode = "numeric";
        entrada.min = "0";
        entrada.max = String(ficha.copias_maximas);
        entrada.value = "1";
        entrada.setAttribute("aria-label", "Cópias por máquina de " + maquina.nome);
        entrada.dataset.maquina = maquina.id;
        entrada.dataset.quantidade = maquina.quantidade;
        var mais = criar("button", "ls-passo-botao");
        mais.type = "button";
        mais.setAttribute("aria-label", "Uma cópia a mais de " + maquina.nome);
        mais.appendChild(icone("bi-plus-lg"));
        passo.appendChild(menos);
        passo.appendChild(entrada);
        passo.appendChild(mais);
        var soma = criar("span", "ls-folha-producao-maquina-soma");
        soma.setAttribute("aria-live", "polite");
        linha.appendChild(nome);
        linha.appendChild(passo);
        linha.appendChild(soma);
        lista.appendChild(linha);
        entradas.push({ entrada: entrada, soma: soma, quantidade: maquina.quantidade });

        function mudar(delta) {
          var atual = parseInt(entrada.value, 10) || 0;
          entrada.value = String(Math.min(ficha.copias_maximas, Math.max(0, atual + delta)));
          contar();
        }
        menos.addEventListener("click", function () { mudar(-1); });
        mais.addEventListener("click", function () { mudar(1); });
        entrada.addEventListener("input", contar);
      });
      if (!ficha.maquinas.length) {
        lista.appendChild(criar("li", "ls-folha-producao-vazia", "Nenhuma máquina neste registro."));
      }
      cartao.appendChild(lista);

      var resumo = criar("p", "ls-folha-producao-resumo");
      resumo.setAttribute("aria-live", "polite");
      cartao.appendChild(resumo);

      var imprimir = criar("button", "ls-recado-botao ls-recado-botao--primario");
      imprimir.type = "submit";
      imprimir.appendChild(icone("bi-printer"));
      imprimir.appendChild(document.createTextNode(" Imprimir"));
      botoes.appendChild(cancelar);
      botoes.appendChild(imprimir);
      cartao.appendChild(botoes);

      function porFolha() {
        var marcado = cartao.querySelector("input[type=radio]:checked");
        return marcado ? parseInt(marcado.dataset.porFolha, 10) || 4 : 4;
      }

      function contar() {
        var total = 0;
        entradas.forEach(function (item) {
          var copias = Math.min(ficha.copias_maximas, Math.max(0, parseInt(item.entrada.value, 10) || 0));
          var linha = copias * item.quantidade;
          total += linha;
          item.soma.textContent = plural(linha, "etiqueta", "etiquetas");
        });
        var folhas = total ? Math.ceil(total / porFolha()) : 0;
        resumo.textContent = "";
        resumo.appendChild(icone("bi-file-earmark"));
        resumo.appendChild(document.createTextNode(" "));
        resumo.appendChild(criar("strong", "", plural(total, "etiqueta", "etiquetas")));
        resumo.appendChild(document.createTextNode(" em "));
        resumo.appendChild(criar("strong", "", plural(folhas, "folha A4", "folhas A4")));
        var demais = total > ficha.etiquetas_maximas;
        if (demais) {
          resumo.appendChild(document.createTextNode(" · máximo de " + ficha.etiquetas_maximas + " por vez"));
        }
        resumo.classList.toggle("is-alerta", demais || total === 0);
        imprimir.disabled = total === 0 || demais;
        return total;
      }
      cartao.addEventListener("change", function (evento) {
        if (evento.target.type === "radio") contar();
      });
      contar();

      cartao.addEventListener("submit", function () {
        if (!contar()) return;
        var partes = ["tamanho=" + encodeURIComponent(
          (cartao.querySelector("input[type=radio]:checked") || {}).value || ficha.tamanho
        )];
        entradas.forEach(function (item) {
          partes.push("c=" + encodeURIComponent(item.entrada.dataset.maquina + ":" + (parseInt(item.entrada.value, 10) || 0)));
        });
        partes.push("imprimir=1");
        var url = ficha.imprimir + "?" + partes.join("&");
        /* Numa aba nova: o painel fica onde estava. Com a aba bloqueada,
           abre aqui mesmo (o "Fechar" da página volta). */
        var aba = window.open(url, "_blank");
        if (!aba) window.location.href = url;
        fechar();
      });

      return entradas.length ? entradas[0].entrada : cancelar;
    });
  }

  function abrirEtiquetas(url, botao) {
    if (botao) botao.setAttribute("aria-busy", "true");
    return buscar(url).then(function (ficha) {
      folhaDeEtiquetas(ficha);
    }).catch(function (erro) {
      avisar("erro", "Etiquetas", erro.message);
    }).finally(function () {
      if (botao) botao.removeAttribute("aria-busy");
    });
  }

  /* ==================================================================
     3. O ANDAMENTO DO PEDIDO DO SITE
     ================================================================== */
  var DICA_DO_PASSO = {
    pago: "Volta ao começo (correção).",
    em_preparacao: "A fábrica começou a montar.",
    saiu_entrega: "Está a caminho do cliente.",
    finalizado: "Entregue. Fecha o pedido.",
    cancelado: "Tira a venda da receita. O estorno no Mercado Pago é feito lá."
  };

  function folhaDeAndamento(botao) {
    var opcoes = [];
    try { opcoes = JSON.parse(botao.dataset.andamentoOpcoes || "[]"); } catch (erro) { opcoes = []; }
    var url = botao.dataset.andamentoUrl;
    var titulo = botao.dataset.andamentoTitulo || "Andamento do pedido";
    var atual = botao.dataset.andamentoRotulo || "";

    abrirFolha("ls-folha-andamento", function (cartao, fechar, id) {
      cabecalho(cartao, id, "bi-signpost-split", titulo, atual ? "Agora: " + atual : "");
      var lista = criar("div", "ls-folha-andamento-opcoes");
      var primeiro = null;
      opcoes.forEach(function (opcao) {
        var item = criar("button", "ls-folha-andamento-opcao" + (opcao.valor === "cancelado" ? " perigo" : ""));
        item.type = "button";
        item.appendChild(icone(opcao.icone));
        var textos = criar("span");
        textos.appendChild(criar("strong", "", opcao.rotulo));
        textos.appendChild(criar("small", "", DICA_DO_PASSO[opcao.valor] || ""));
        item.appendChild(textos);
        item.addEventListener("click", function () {
          fechar();
          escolher(opcao);
        });
        lista.appendChild(item);
        if (!primeiro && opcao.valor !== "cancelado") primeiro = item;
      });
      if (!opcoes.length) {
        lista.appendChild(criar("p", "ls-folha-producao-aviso", "Este pedido não muda mais de situação pelo painel."));
      }
      cartao.appendChild(lista);
      var botoes = criar("div", "ls-recado-folha-botoes");
      var voltar = criar("button", "ls-recado-botao", "Fechar");
      voltar.type = "button";
      voltar.addEventListener("click", fechar);
      botoes.appendChild(voltar);
      cartao.appendChild(botoes);
      return primeiro || voltar;
    });

    function escolher(opcao) {
      var pergunta = Promise.resolve(true);
      if (opcao.valor === "cancelado" && window.LSAviso) {
        pergunta = window.LSAviso.confirmar({
          titulo: "Cancelar " + titulo.replace("Andamento do ", "o ") + "?",
          texto: "A venda dele sai da receita do Financeiro. Devolver o dinheiro ao cliente é no Mercado Pago.",
          confirmar: "Cancelar pedido",
          cancelar: "Voltar",
          perigo: true,
          icone: "alerta"
        });
      }
      pergunta.then(function (sim) {
        if (!sim) return;
        botao.setAttribute("aria-busy", "true");
        postar(url, { status: opcao.valor }).then(function (corpo) {
          avisar("sucesso", corpo.rotulo || "Pedido atualizado", corpo.msg);
          if (typeof window.LSAtualizarTela === "function") window.LSAtualizarTela();
          else window.location.reload();
        }).catch(function (erro) {
          avisar("erro", "O pedido não mudou", erro.message);
        }).finally(function () {
          botao.removeAttribute("aria-busy");
        });
      });
    }
  }

  /* ------------------------------------------------- os cliques */
  document.addEventListener("click", function (evento) {
    var alvo = evento.target.closest && evento.target.closest("[data-etiquetas-url], [data-andamento-url]");
    if (!alvo || alvo.disabled) return;
    var etiquetas = alvo.dataset.etiquetasUrl;
    var andamento = alvo.dataset.andamentoUrl;
    if (!etiquetas && !andamento) return;
    evento.preventDefault();
    evento.stopPropagation();
    if (etiquetas) abrirEtiquetas(etiquetas, alvo);
    else folhaDeAndamento(alvo);
  });

  window.LSProducao = {
    campoPrazo: campoPrazo,
    etiquetas: abrirEtiquetas
  };
})(window, document);
