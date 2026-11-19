/* O AUTOMATIZADOR DA O.S. (LEIA-ME-V10, seção 122) -- views_importacao_os.py.

   A folha "Ler documentos" da tela de Ordens de Serviço:

     * a equipe escolhe (ou arrasta) um ou vários documentos; cada um vira
       uma linha "Na fila" e vai para o servidor UM DE CADA VEZ, num pedido
       próprio -- o lote de dez é uma fila de dez pedidos curtos, com o anel
       do progresso, e nunca um pedido de minutos;
     * a resposta desenha a linha: "O.S. criada" (com "Abrir a O.S."),
       "Falta completar" (os campos só do que falta, já preenchidos, e
       "Salvar e criar a O.S."), "Já importada" (com o caminho para a O.S.)
       ou "Não deu para ler" (com o motivo);
     * "Próximo campo" leva ao primeiro campo vazio das linhas que faltam;
     * ao fim do lote, o toast conta o que aconteceu e a lista de O.S. de
       trás se atualiza sozinha;
     * a janela da O.S. mostra "Lido do documento ..." com o anexo.

   Nada de alert()/confirm(): o recado é o toast do painel e o "Descartar"
   pergunta pela folha do LSAviso. O painel troca de tela sem recarregar:
   este arquivo roda de novo a cada visita e só liga o que está na tela. */
(function (window, document) {
  "use strict";

  var ICONES = { docx: "bi-file-earmark-word", pdf: "bi-file-earmark-pdf", txt: "bi-file-earmark-text" };
  var SELOS = {
    fila: "Na fila", lendo: "Lendo", criada: "O.S. criada", falta: "Falta completar",
    repetida: "Já importada", ilegivel: "Não deu para ler", descartado: "Descartado"
  };
  var PRAZO = 85000;
  var reduzir = Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  function el(tag, classe, texto) {
    var no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined && texto !== null) no.textContent = String(texto);
    return no;
  }

  function icone(nome) {
    var i = el("i", "bi " + nome);
    i.setAttribute("aria-hidden", "true");
    return i;
  }

  function formatoDoNome(nome) {
    var extensao = String(nome || "").split(".").pop().toLowerCase();
    return ICONES[extensao] ? extensao : "docx";
  }

  /* Com a folha aberta, a própria folha é o recado: o anel e o placar
     dizem o que aconteceu, e a linha fica verde, amarela ou vermelha. O
     toast por cima taparia o topo da folha (no celular, o título e o X).
     Ele só aparece com a folha fechada -- o lote seguiu lendo por trás --,
     ou quando é erro. */
  function toast(nivel, titulo, texto, sempre) {
    var folha = document.getElementById("osdocFolha");
    if (!sempre && folha && !folha.hidden) return;
    if (window.LSAviso && window.LSAviso.toast) window.LSAviso.toast({ nivel: nivel, titulo: titulo, texto: texto || "" });
  }

  function confirmar(opcoes) {
    if (window.LSAviso && typeof window.LSAviso.confirmar === "function") return window.LSAviso.confirmar(opcoes);
    return Promise.resolve(true);
  }

  function enviar(url, dados, csrf) {
    var controle = window.AbortController ? new window.AbortController() : null;
    var prazo = controle ? window.setTimeout(function () { controle.abort(); }, PRAZO) : null;
    return window.fetch(url, {
      method: "POST", body: dados, credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf },
      signal: controle ? controle.signal : undefined
    }).then(function (resposta) {
      return resposta.json().catch(function () { return null; }).then(function (json) {
        if (json) return json;
        if (resposta.status === 403) return { estado: "ilegivel", motivo: "Sua conta não pode criar O.S. por aqui." };
        return { estado: "ilegivel", motivo: "O servidor não respondeu direito (" + resposta.status + "). Envie de novo." };
      });
    }).catch(function () {
      return { estado: "ilegivel", motivo: "Sem resposta do servidor: este documento não foi lido. Envie de novo." };
    }).finally(function () { if (prazo) window.clearTimeout(prazo); });
  }

  /* ------------------------------------------------------------------
     A O.S. criada (ou a repetida) abre na própria tela: a linha dela já
     está na lista, ou a lista é filtrada nela e a janela abre depois. */
  function clicarNaOS(id) {
    var botao = document.querySelector('[data-editar-os="' + String(id) + '"]');
    if (botao) { botao.click(); return true; }
    return false;
  }

  /* CLIENTE NOVO PEDE A TELA INTEIRA. A janela da O.S. escolhe o cliente
     numa lista que veio com a tela; o cliente que a leitura acabou de
     cadastrar não está nela, e a janela abriria com o campo vazio -- e
     salvar ali desligaria a O.S. do cliente. Então, depois de um cadastro
     novo, a O.S. abre numa tela recarregada inteira (com a lista nova), e
     o `abrir_os` da URL abre a janela dela. */
  function abrirOS(os, folha) {
    var inteira = Boolean(folha && folha.clientesNovos);
    if (folha) { folha.clientesNovos = 0; folha.fechar(true); }
    if (!inteira && clicarNaOS(os.id)) return;
    if (window.LSNavigation && window.LSNavigation.go) {
      Promise.resolve(window.LSNavigation.go(os.link, { inteira: inteira })).then(function () {
        window.setTimeout(function () { if (!clicarNaOS(os.id)) window.location.href = os.link; }, 160);
      });
    } else {
      window.location.href = os.link;
    }
  }

  function limparParametro(nome) {
    try {
      var url = new URL(window.location.href);
      if (!url.searchParams.has(nome)) return;
      url.searchParams.delete(nome);
      window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    } catch (erro) { /* nada */ }
  }

  /* ====================================================================
     A FOLHA
     ==================================================================== */
  function Folha(raiz) {
    this.raiz = raiz;
    this.cartao = raiz.querySelector(".ls-osdoc-cartao");
    this.corpo = raiz.querySelector(".ls-osdoc-corpo");
    this.lista = raiz.querySelector("#osdocLista");
    this.secaoPendentes = raiz.querySelector("#osdocPendentes");
    this.listaPendentes = raiz.querySelector("#osdocListaPendentes");
    this.entrada = raiz.querySelector("#osdocArquivos");
    this.soltar = raiz.querySelector("#osdocSoltar");
    this.progresso = raiz.querySelector("#osdocProgresso");
    this.anel = raiz.querySelector("#osdocAnel");
    this.percentual = raiz.querySelector("#osdocPercentual");
    this.contagem = raiz.querySelector("#osdocContagem");
    this.placar = raiz.querySelector("#osdocPlacar");
    this.botaoProximo = raiz.querySelector("#osdocProximo");
    this.url = raiz.dataset.url;
    this.urlDocumento = raiz.dataset.urlDocumento;
    this.maximo = Number(raiz.dataset.tamanhoMaximo) || 10485760;
    this.fila = [];
    this.total = 0;
    this.feitos = 0;
    this.rodando = false;
    this.criadasNoLote = 0;
    this.clientesNovos = 0;
    this.placarLote = { criada: 0, falta: 0, repetida: 0, ilegivel: 0 };
    this.focoAntes = null;
    this.ligar();
  }

  Folha.prototype.csrf = function () {
    var campo = this.raiz.querySelector("[name=csrfmiddlewaretoken]") || document.querySelector("[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  };

  Folha.prototype.urlDo = function (id) {
    return this.urlDocumento.replace(/\/0\/$/, "/" + String(id) + "/");
  };

  Folha.prototype.ligar = function () {
    var folha = this;
    this.raiz.addEventListener("click", function (evento) {
      if (evento.target.closest("[data-osdoc-fechar]")) { folha.fechar(); return; }
    });
    this.raiz.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") { evento.preventDefault(); folha.fechar(); return; }
      if (evento.key !== "Tab") return;
      var focaveis = Array.prototype.filter.call(folha.cartao.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), textarea, [tabindex]:not([tabindex="-1"])'
      ), function (no) { return no.offsetParent !== null || no === folha.entrada; });
      if (!focaveis.length) return;
      var primeiro = focaveis[0];
      var ultimo = focaveis[focaveis.length - 1];
      if (evento.shiftKey && document.activeElement === primeiro) { evento.preventDefault(); ultimo.focus(); }
      else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primeiro.focus(); }
    });
    this.entrada.addEventListener("change", function () {
      if (folha.entrada.files && folha.entrada.files.length) folha.enfileirar(folha.entrada.files);
      folha.entrada.value = "";
    });
    ["dragenter", "dragover"].forEach(function (tipo) {
      folha.cartao.addEventListener(tipo, function (evento) {
        evento.preventDefault();
        folha.soltar.classList.add("arrastando");
      });
    });
    ["dragleave", "drop"].forEach(function (tipo) {
      folha.cartao.addEventListener(tipo, function (evento) {
        evento.preventDefault();
        if (tipo === "drop" || !folha.cartao.contains(evento.relatedTarget)) folha.soltar.classList.remove("arrastando");
      });
    });
    this.cartao.addEventListener("drop", function (evento) {
      var arquivos = evento.dataTransfer && evento.dataTransfer.files;
      if (arquivos && arquivos.length) folha.enfileirar(arquivos);
    });
    this.botaoProximo.addEventListener("click", function () { folha.proximoCampo(); });

    /* No celular a folha desce com o dedo, pela alça. */
    var alca = this.raiz.querySelector("#osdocAlca");
    var inicio = null;
    if (alca) {
      alca.addEventListener("pointerdown", function (evento) {
        inicio = evento.clientY;
        try { alca.setPointerCapture(evento.pointerId); } catch (erro) { /* nada */ }
      });
      alca.addEventListener("pointermove", function (evento) {
        if (inicio === null) return;
        folha.cartao.style.transform = "translateY(" + Math.max(0, evento.clientY - inicio) + "px)";
      });
      ["pointerup", "pointercancel"].forEach(function (tipo) {
        alca.addEventListener(tipo, function (evento) {
          if (inicio === null) return;
          var desceu = evento.clientY - inicio;
          inicio = null;
          folha.cartao.style.transform = "";
          if (desceu > 90) folha.fechar();
        });
      });
    }
  };

  Folha.prototype.abrir = function () {
    this.focoAntes = document.activeElement;
    this.raiz.hidden = false;
    document.documentElement.classList.add("ls-osdoc-aberta");
    var raiz = this.raiz;
    window.requestAnimationFrame(function () { raiz.classList.add("aberta"); });
    var cartao = this.cartao;
    window.setTimeout(function () { cartao.focus(); }, reduzir ? 0 : 60);
    this.carregarPendentes();
  };

  Folha.prototype.fechar = function (semAtualizar) {
    if (this.raiz.hidden) return;
    if (this.clientesNovos && !semAtualizar && typeof window.LSAtualizarTela === "function") {
      /* Ver `abrirOS`: com cliente novo, a tela vem inteira. */
      this.clientesNovos = 0;
      window.setTimeout(function () { window.LSAtualizarTela(); }, reduzir ? 0 : 220);
    }
    this.raiz.classList.remove("aberta");
    document.documentElement.classList.remove("ls-osdoc-aberta");
    var raiz = this.raiz;
    window.setTimeout(function () { raiz.hidden = true; }, reduzir ? 0 : 200);
    if (this.focoAntes && this.focoAntes.isConnected && this.focoAntes.focus) {
      try { this.focoAntes.focus({ preventScroll: true }); } catch (erro) { /* nada */ }
    }
  };

  Folha.prototype.carregarPendentes = function () {
    var folha = this;
    window.fetch(this.url + "?formato=json", {
      credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }, cache: "no-store"
    }).then(function (resposta) { return resposta.ok ? resposta.json() : null; }).then(function (json) {
      if (!json || !json.pendentes) return;
      var naLista = {};
      folha.lista.querySelectorAll("[data-documento]").forEach(function (linha) { naLista[linha.dataset.documento] = true; });
      folha.listaPendentes.textContent = "";
      json.pendentes.forEach(function (resposta) {
        if (naLista[String(resposta.documento)]) return;
        var linha = folha.novaLinha(resposta.arquivo);
        folha.listaPendentes.appendChild(linha);
        folha.desenhar(linha, resposta);
      });
      folha.secaoPendentes.hidden = !folha.listaPendentes.children.length;
      if (!folha.secaoPendentes.hidden) folha.raiz.classList.add("com-itens");
      folha.mostrarProximo();
    }).catch(function () { /* a lista de espera é ajuda, não trava a folha */ });
  };

  /* ------------------------------------------------------------ a fila */
  Folha.prototype.enfileirar = function (arquivos) {
    var folha = this;
    Array.prototype.forEach.call(arquivos, function (arquivo) {
      var linha = folha.novaLinha(arquivo.name);
      folha.lista.appendChild(linha);
      folha.desenhar(linha, { estado: "fila", arquivo: arquivo.name });
      folha.fila.push({ arquivo: arquivo, linha: linha });
      folha.total += 1;
    });
    this.progresso.hidden = false;
    this.progresso.classList.remove("so-espera");
    this.raiz.classList.add("com-itens");
    this.atualizarProgresso();
    if (!this.rodando) this.seguir();
  };

  Folha.prototype.seguir = function () {
    var folha = this;
    var trabalho = this.fila.shift();
    if (!trabalho) { this.terminar(); return; }
    this.rodando = true;
    this.soltar.classList.add("lendo");
    this.desenhar(trabalho.linha, { estado: "lendo", arquivo: trabalho.arquivo.name });
    this.atualizarProgresso(trabalho.arquivo.name);
    var feito;
    if (trabalho.arquivo.size > this.maximo) {
      feito = Promise.resolve({
        estado: "ilegivel", arquivo: trabalho.arquivo.name,
        motivo: "O arquivo passa de 10 MB. Salve uma cópia sem as fotos (ou com as fotos compactadas) e envie de novo."
      });
    } else {
      var dados = new window.FormData();
      dados.append("arquivo", trabalho.arquivo, trabalho.arquivo.name);
      dados.append("csrfmiddlewaretoken", this.csrf());
      feito = enviar(this.url, dados, this.csrf());
    }
    feito.then(function (resposta) {
      resposta.arquivo = resposta.arquivo || trabalho.arquivo.name;
      folha.desenhar(trabalho.linha, resposta);
      folha.contar(resposta.estado, 1);
      trabalho.linha.dataset.contada = "1";
      if (resposta.cliente && resposta.cliente.novo) folha.clientesNovos += 1;
      if (resposta.estado === "criada") folha.criadasNoLote += 1;
    }).finally(function () {
      folha.feitos += 1;
      folha.atualizarProgresso();
      folha.seguir();
    });
  };

  Folha.prototype.contar = function (estado, quanto) {
    if (Object.prototype.hasOwnProperty.call(this.placarLote, estado)) this.placarLote[estado] += quanto;
  };

  Folha.prototype.atualizarProgresso = function (lendo) {
    var total = Math.max(this.total, 1);
    var fracao = Math.min(1, this.feitos / total);
    var circunferencia = 2 * Math.PI * 20;
    this.anel.setAttribute("stroke-dasharray", (fracao * circunferencia).toFixed(1) + " " + circunferencia.toFixed(1));
    this.percentual.textContent = Math.round(fracao * 100) + "%";
    if (this.feitos < this.total) {
      this.contagem.textContent = "Lendo " + Math.min(this.feitos + 1, this.total) + " de " + this.total + (lendo ? " · " + lendo : "");
    } else {
      this.contagem.textContent = this.total === 1 ? "1 documento lido" : this.total + " documentos lidos";
    }
    var p = this.placarLote;
    var partes = [];
    if (p.criada) partes.push(p.criada + (p.criada === 1 ? " O.S. criada" : " O.S. criadas"));
    if (p.falta) partes.push(p.falta + " para completar");
    if (p.repetida) partes.push(p.repetida + (p.repetida === 1 ? " já importada" : " já importadas"));
    if (p.ilegivel) partes.push(p.ilegivel + " sem leitura");
    this.placar.textContent = partes.join(" · ");
    this.mostrarProximo();
  };

  Folha.prototype.terminar = function () {
    this.rodando = false;
    this.soltar.classList.remove("lendo");
    var p = this.placarLote;
    if (this.total) {
      var texto = [];
      if (p.criada) texto.push(p.criada + (p.criada === 1 ? " O.S. criada" : " O.S. criadas"));
      if (p.falta) texto.push(p.falta + " para completar aqui");
      if (p.repetida) texto.push(p.repetida + " já importada" + (p.repetida === 1 ? "" : "s"));
      if (p.ilegivel) texto.push(p.ilegivel + " sem leitura");
      toast(p.falta || p.ilegivel ? "alerta" : "sucesso", "Documentos lidos", texto.join(" · "));
    }
    if (this.criadasNoLote) this.atualizarLista();
    this.criadasNoLote = 0;
  };

  Folha.prototype.atualizarLista = function () {
    if (window.Painel && window.Painel.confirmarGravacao) window.Painel.confirmarGravacao();
    if (typeof window.LSAtualizarTela === "function") window.LSAtualizarTela({ partes: true });
  };

  Folha.prototype.mostrarProximo = function () {
    var faltando = this.raiz.querySelectorAll(".ls-osdoc-item.falta").length;
    this.botaoProximo.hidden = !faltando;
    if (!faltando && this.progresso.classList.contains("so-espera")) {
      this.progresso.hidden = true;
      return;
    }
    if (!faltando || (!this.progresso.hidden && !this.progresso.classList.contains("so-espera"))) return;
    this.progresso.hidden = false;
    this.progresso.classList.add("so-espera");
    this.contagem.textContent = faltando === 1 ? "1 documento espera completar" : faltando + " documentos esperam completar";
    this.placar.textContent = "";
  };

  Folha.prototype.proximoCampo = function () {
    var campos = this.raiz.querySelectorAll(".ls-osdoc-item.falta .ls-osdoc-falta");
    var alvo = null;
    var foco = null;
    Array.prototype.some.call(campos, function (falta) {
      var vazio = Array.prototype.filter.call(falta.querySelectorAll("input:not([type=hidden]), textarea"), function (campo) {
        return campo.offsetParent !== null && !campo.value.trim() && campo.dataset.opcional !== "1";
      })[0];
      var escolha = falta.querySelector("[name=cliente_escolha], [name=usar_total]");
      var semEscolha = Boolean(escolha && !escolha.value);
      if (vazio || semEscolha) {
        alvo = falta;
        foco = vazio || falta.querySelector(".ls-chip");
        return true;
      }
      return false;
    });
    if (!alvo) {
      var salvar = this.raiz.querySelector(".ls-osdoc-item.falta .ls-osdoc-salvar");
      if (salvar) { salvar.scrollIntoView({ block: "center", behavior: reduzir ? "auto" : "smooth" }); salvar.focus(); }
      return;
    }
    (foco || alvo).scrollIntoView({ block: "center", behavior: reduzir ? "auto" : "smooth" });
    alvo.classList.remove("alvo");
    void alvo.offsetWidth;
    alvo.classList.add("alvo");
    window.setTimeout(function () { if (foco) foco.focus({ preventScroll: true }); }, reduzir ? 0 : 280);
  };

  /* ------------------------------------------------------- as linhas */
  Folha.prototype.novaLinha = function (nome) {
    var linha = el("li", "ls-osdoc-item fila");
    linha.dataset.formato = formatoDoNome(nome);
    return linha;
  };

  Folha.prototype.desenhar = function (linha, r) {
    var folha = this;
    var estado = r.estado || "ilegivel";
    var anterior = linha.dataset.estado;
    linha.className = "ls-osdoc-item " + estado;
    linha.dataset.estado = estado;
    if (r.documento) linha.dataset.documento = String(r.documento);
    linha.textContent = "";

    var topo = el("div", "ls-osdoc-item-topo");
    var simbolo = el("span", "ls-osdoc-icone");
    simbolo.appendChild(icone(ICONES[r.formato || linha.dataset.formato] || ICONES.docx));
    topo.appendChild(simbolo);
    var titulo = el("div", "ls-osdoc-item-titulo");
    titulo.appendChild(el("strong", "", r.arquivo || "Documento"));
    var sub = "";
    if (r.os) sub = [r.os.numero, r.os.cliente, r.os.equipamento].filter(Boolean).join(" · ");
    else if (estado === "falta") sub = "Lido" + (r.enviado_em ? " em " + r.enviado_em : "") + ": complete o que falta para criar a O.S.";
    else if (estado === "lendo") sub = "Lendo o documento…";
    else if (estado === "fila") sub = "Esperando a vez";
    if (sub) titulo.appendChild(el("small", "", sub));
    topo.appendChild(titulo);
    var selo = el("span", "ls-osdoc-selo " + estado);
    if (estado === "lendo") selo.appendChild(el("span", "ls-osdoc-girando"));
    selo.appendChild(document.createTextNode(SELOS[estado] || SELOS.ilegivel));
    topo.appendChild(selo);
    linha.appendChild(topo);

    if (estado === "descartado") {
      linha.classList.add("saindo");
      window.setTimeout(function () {
        var lista = linha.parentNode;
        linha.remove();
        if (lista === folha.listaPendentes) folha.secaoPendentes.hidden = !folha.listaPendentes.children.length;
        folha.mostrarProximo();
      }, reduzir ? 0 : 450);
      return;
    }

    if (r.motivo && estado !== "falta") linha.appendChild(el("p", "ls-osdoc-motivo", r.motivo));
    if (r.resumo && r.resumo.length) {
      if (estado === "criada") {
        var dobra = el("details", "ls-osdoc-dobra");
        var resumoDobra = el("summary");
        resumoDobra.appendChild(document.createTextNode("O que foi lido (" + r.resumo.length + ")"));
        resumoDobra.appendChild(icone("bi-chevron-down"));
        dobra.appendChild(resumoDobra);
        dobra.appendChild(this.lido(r.resumo));
        dobra.open = !(window.matchMedia && window.matchMedia("(max-width: 760px)").matches);
        linha.appendChild(dobra);
      } else {
        linha.appendChild(this.lido(r.resumo));
      }
    }
    if (r.avisos && r.avisos.length) {
      var avisos = el("ul", "ls-osdoc-avisos");
      r.avisos.forEach(function (aviso) {
        var item = el("li");
        item.appendChild(icone("bi-exclamation-triangle"));
        item.appendChild(el("span", "", aviso));
        avisos.appendChild(item);
      });
      linha.appendChild(avisos);
    }
    if (estado === "falta") linha.appendChild(this.formulario(linha, r));
    if (r.os && (estado === "criada" || estado === "repetida")) {
      var acoes = el("div", "ls-osdoc-acoes");
      var abrir = el("button", "btn btn-sm " + (estado === "criada" ? "btn-success" : "btn-outline-primary"));
      abrir.type = "button";
      abrir.appendChild(icone("bi-box-arrow-up-right me-1"));
      abrir.appendChild(document.createTextNode(estado === "criada" ? "Abrir a O.S." : "Abrir a " + r.os.numero));
      abrir.addEventListener("click", function () { abrirOS(r.os, folha); });
      acoes.appendChild(abrir);
      var previa = el("a", "ls-osdoc-link", "Prévia");
      previa.href = r.os.previa;
      acoes.appendChild(previa);
      if (r.arquivo_url) {
        var original = el("a", "ls-osdoc-link", "Documento original");
        original.href = r.arquivo_url;
        original.target = "_blank";
        original.rel = "noopener";
        acoes.appendChild(original);
      }
      linha.appendChild(acoes);
    }
    if (anterior === "falta" && estado !== "falta") {
      if (linha.dataset.contada === "1") {
        this.contar("falta", -1);
        this.contar(estado, 1);
      }
      if (estado === "criada") this.atualizarLista();
      this.atualizarProgresso();
    }
  };

  Folha.prototype.lido = function (resumo) {
    var lista = el("ul", "ls-osdoc-lido");
    lista.setAttribute("aria-label", "O que foi lido");
    resumo.forEach(function (item) {
      var pilula = el("li");
      pilula.appendChild(el("b", "", item.rotulo));
      var valor = el("span", "", item.valor);
      valor.title = item.valor;
      pilula.appendChild(valor);
      if (item.como) pilula.appendChild(el("em", "", item.como));
      lista.appendChild(pilula);
    });
    return lista;
  };

  /* --------------------------------------- completar ali mesmo */
  function grupoDeChips(nome, opcoes, escolhido, aoEscolher) {
    var grupo = el("div", "ls-osdoc-chips");
    grupo.setAttribute("role", "group");
    var oculto = el("input");
    oculto.type = "hidden";
    oculto.name = nome;
    oculto.value = escolhido || "";
    grupo.appendChild(oculto);
    opcoes.forEach(function (opcao) {
      var chip = el("button", "ls-chip");
      chip.type = "button";
      chip.dataset.valor = opcao.valor;
      chip.setAttribute("aria-pressed", opcao.valor === escolhido ? "true" : "false");
      chip.appendChild(document.createTextNode(opcao.rotulo));
      if (opcao.detalhe) chip.appendChild(el("small", "", opcao.detalhe));
      chip.addEventListener("click", function () {
        oculto.value = opcao.valor;
        grupo.querySelectorAll(".ls-chip").forEach(function (outro) {
          outro.setAttribute("aria-pressed", outro === chip ? "true" : "false");
        });
        if (aoEscolher) aoEscolher(opcao.valor);
      });
      grupo.appendChild(chip);
    });
    return grupo;
  }

  function campoTexto(rotulo, nome, valor, opcoes) {
    opcoes = opcoes || {};
    var caixa = el("label");
    /* O campo único do bloco já tem o título em cima ("Equipamento ·
       o documento não diz..."): o rótulo fica só para o leitor de tela. */
    caixa.appendChild(opcoes.soLeitor ? el("span", "visually-hidden", rotulo) : document.createTextNode(rotulo));
    var campo = el(opcoes.longo ? "textarea" : "input", "form-control");
    if (!opcoes.longo) campo.type = opcoes.tipo || "text";
    if (opcoes.longo) campo.rows = 3;
    campo.name = nome;
    campo.value = valor || "";
    if (opcoes.mascara) campo.dataset.mascara = opcoes.mascara;
    if (opcoes.modo) campo.setAttribute("inputmode", opcoes.modo);
    if (opcoes.limite) campo.maxLength = opcoes.limite;
    if (opcoes.placeholder) campo.placeholder = opcoes.placeholder;
    if (opcoes.opcional) campo.dataset.opcional = "1";
    campo.autocomplete = "off";
    caixa.appendChild(campo);
    return caixa;
  }

  function cabecaDaFalta(falta, iconeNome) {
    var cabeca = el("p", "ls-osdoc-falta-rotulo");
    cabeca.appendChild(icone(iconeNome || "bi-exclamation-circle"));
    cabeca.appendChild(document.createTextNode(falta.rotulo));
    if (falta.motivo) cabeca.appendChild(el("span", "ls-osdoc-falta-motivo", "· " + falta.motivo));
    return cabeca;
  }

  Folha.prototype.formulario = function (linha, r) {
    var folha = this;
    var form = el("form", "ls-osdoc-form");
    form.noValidate = true;
    if (r.recado) form.appendChild(el("p", "ls-osdoc-motivo", r.recado));
    if (r.erros && r.erros.length) form.appendChild(el("p", "ls-osdoc-erros", r.erros.join(" ")));
    (r.faltas || []).forEach(function (falta) {
      var bloco = el("div", "ls-osdoc-falta");
      bloco.dataset.falta = falta.campo;
      if (falta.campo === "cliente") {
        bloco.appendChild(cabecaDaFalta(falta, "bi-person-exclamation"));
        var valores = falta.valores || {};
        var opcoes = (falta.candidatos || []).map(function (c) {
          return { valor: "id:" + c.id, rotulo: c.nome + " (#" + c.id + ")", detalhe: c.detalhe || "é este o cliente" };
        });
        opcoes.push({ valor: "novo", rotulo: opcoes.length ? "Outro cliente: cadastrar" : "Cadastrar o cliente", detalhe: "com nome e um contato" });
        if (falta.pode_sem_cadastro) opcoes.push({ valor: "sem_cadastro", rotulo: "Só o nome na O.S.", detalhe: "sem cadastrar" });
        var inicial = (falta.candidatos || []).length ? "" : "novo";
        var grade = el("div", "ls-osdoc-grade");
        grade.appendChild(campoTexto("Nome do cliente", "cliente_nome", valores.nome, { limite: 90 }));
        var tel = campoTexto("Telefone / WhatsApp", "cliente_telefone", valores.telefone, { mascara: "telefone", modo: "tel", limite: 24, opcional: true });
        var mail = campoTexto("E-mail", "cliente_email", valores.email, { tipo: "email", modo: "email", limite: 150, opcional: true });
        grade.appendChild(tel);
        grade.appendChild(mail);
        function mostrarGrade(valor) {
          grade.hidden = !(valor === "novo" || valor === "sem_cadastro");
          tel.hidden = mail.hidden = valor === "sem_cadastro";
        }
        bloco.appendChild(grupoDeChips("cliente_escolha", opcoes, inicial, mostrarGrade));
        bloco.appendChild(grade);
        mostrarGrade(inicial);
      } else if (falta.campo === "equipamento") {
        bloco.appendChild(cabecaDaFalta(falta, "bi-tools"));
        bloco.appendChild(campoTexto("Equipamento", "equipamento", falta.valor, { limite: 180, placeholder: "Ex.: Cama elástica 3 m", soLeitor: true }));
      } else if (falta.campo === "defeito_relatado" || falta.campo === "servico_executado") {
        bloco.appendChild(cabecaDaFalta(falta, falta.campo === "servico_executado" ? "bi-check2-square" : "bi-chat-left-text"));
        bloco.appendChild(campoTexto(falta.rotulo, falta.campo, falta.valor, {
          longo: true, limite: 4000, soLeitor: true,
          placeholder: falta.campo === "servico_executado" ? "O que foi trocado, ajustado ou substituído." : "O que o cliente contou, com as palavras dele."
        }));
      } else if (falta.campo === "valores") {
        bloco.appendChild(cabecaDaFalta(falta, "bi-cash-coin"));
        var itens = el("div", "ls-osdoc-itens");
        (falta.itens || []).forEach(function (item) {
          var fila = el("div", "ls-osdoc-linha" + (!item.valor_unitario || !item.quantidade || item.recusa ? " sem-valor" : ""));
          fila.dataset.item = "1";
          var nome = el("div", "ls-osdoc-linha-nome");
          nome.appendChild(el("strong", "", item.descricao));
          nome.appendChild(el("small", "", item.recusa || ({ peca: "Peça / material", servico: "Serviço", deslocamento: "Deslocamento", outro: "Outro" }[item.tipo] || "")));
          fila.appendChild(nome);
          fila.appendChild(campoTexto("Qtd", "qtd", item.quantidade, { modo: "numeric", limite: 8 }));
          fila.appendChild(campoTexto("Valor unit. (R$)", "valor", item.valor_unitario, { mascara: "moeda-valor", modo: "decimal", limite: 18 }));
          itens.appendChild(fila);
        });
        bloco.appendChild(itens);
        var ajustes = el("div", "ls-osdoc-grade");
        ajustes.appendChild(campoTexto("Frete (R$)", "frete", falta.frete, { mascara: "moeda-valor", modo: "decimal", opcional: true }));
        ajustes.appendChild(campoTexto("Desconto (R$)", "desconto", falta.desconto, { mascara: "moeda-valor", modo: "decimal", opcional: true }));
        bloco.appendChild(ajustes);
        if (falta.total_documento) {
          var total = el("p", "ls-osdoc-total");
          total.appendChild(document.createTextNode("Total escrito no documento: "));
          total.appendChild(el("b", "", falta.total_documento));
          bloco.appendChild(total);
          var escolhas = [];
          if (falta.diferenca) escolhas.push({ valor: "desconto", rotulo: "Aplicar desconto de " + falta.diferenca, detalhe: "fecha no total do documento" });
          if (falta.lancar_total) escolhas.push({ valor: "linha", rotulo: "Lançar " + falta.total_documento + " como serviço", detalhe: "uma linha só" });
          escolhas.push({ valor: "soma", rotulo: "Ficar com a soma das linhas", detalhe: "o total do documento não vale" });
          bloco.appendChild(grupoDeChips("usar_total", escolhas, ""));
        }
      } else {
        bloco.appendChild(cabecaDaFalta(falta));
      }
      form.appendChild(bloco);
    });

    var acoes = el("div", "ls-osdoc-acoes");
    var salvar = el("button", "btn btn-success ls-osdoc-salvar");
    salvar.type = "submit";
    salvar.appendChild(icone("bi-check2-circle me-1"));
    salvar.appendChild(document.createTextNode("Salvar e criar a O.S."));
    acoes.appendChild(salvar);
    var descartar = el("button", "ls-osdoc-link perigo", "Descartar");
    descartar.type = "button";
    descartar.addEventListener("click", function () { folha.descartar(linha, r); });
    acoes.appendChild(descartar);
    form.appendChild(acoes);

    form.addEventListener("submit", function (evento) {
      evento.preventDefault();
      folha.completar(linha, form, r);
    });
    /* Enter num campo de uma linha leva ao próximo campo vazio, e não
       cria a O.S. no meio da digitação. */
    form.addEventListener("keydown", function (evento) {
      if (evento.key !== "Enter" || evento.target.tagName !== "INPUT") return;
      evento.preventDefault();
      folha.proximoCampo();
    });
    if (window.Painel && window.Painel.aplicarMascaras) {
      window.setTimeout(function () { window.Painel.aplicarMascaras(form); }, 0);
    }
    return form;
  };

  Folha.prototype.completar = function (linha, form, r) {
    var folha = this;
    var dados = new window.FormData();
    dados.append("action", "completar");
    dados.append("csrfmiddlewaretoken", this.csrf());
    form.querySelectorAll(".ls-osdoc-falta").forEach(function (bloco) {
      var campo = bloco.dataset.falta;
      if (campo === "cliente") {
        ["cliente_escolha", "cliente_nome", "cliente_telefone", "cliente_email"].forEach(function (nome) {
          var entrada = bloco.querySelector("[name=" + nome + "]");
          if (entrada) dados.append(nome, entrada.value);
        });
      } else if (campo === "valores") {
        var linhas = [];
        bloco.querySelectorAll("[data-item]").forEach(function (fila) {
          linhas.push({
            quantidade: fila.querySelector("[name=qtd]").value,
            valor_unitario: fila.querySelector("[name=valor]").value
          });
        });
        dados.append("itens_valores", JSON.stringify(linhas));
        ["frete", "desconto"].forEach(function (nome) { dados.append(nome, bloco.querySelector("[name=" + nome + "]").value); });
        var uso = bloco.querySelector("[name=usar_total]");
        if (uso && uso.value === "soma") dados.append("ignorar_total", "1");
        else if (uso && uso.value) dados.append("usar_total", uso.value);
      } else {
        var entrada = bloco.querySelector("[name=" + campo + "]");
        if (entrada) dados.append(campo, entrada.value);
      }
    });
    var botao = form.querySelector(".ls-osdoc-salvar");
    botao.disabled = true;
    botao.textContent = "Criando a O.S.…";
    enviar(this.urlDo(r.documento), dados, this.csrf()).then(function (resposta) {
      if (resposta.estado === "sumiu") {
        toast("alerta", "Documento", resposta.motivo, true);
        folha.desenhar(linha, { estado: "descartado", arquivo: r.arquivo });
        return;
      }
      resposta.arquivo = resposta.arquivo || r.arquivo;
      if (resposta.cliente && resposta.cliente.novo) folha.clientesNovos += 1;
      folha.desenhar(linha, resposta);
      if (resposta.estado === "criada") toast("sucesso", resposta.os.numero + " criada", r.arquivo);
      else if (resposta.estado === "falta") {
        toast("alerta", "Ainda falta", (resposta.faltas || []).map(function (f) { return f.rotulo; }).join(", "));
        folha.proximoCampo();
      }
    });
  };

  Folha.prototype.descartar = function (linha, r) {
    var folha = this;
    confirmar({
      titulo: "Descartar este documento?",
      texto: "“" + r.arquivo + "” sai da lista e o arquivo é apagado. Nenhuma O.S. é criada.",
      confirmar: "Descartar", cancelar: "Manter", perigo: true
    }).then(function (sim) {
      if (!sim) return;
      var dados = new window.FormData();
      dados.append("action", "descartar");
      dados.append("csrfmiddlewaretoken", folha.csrf());
      enviar(folha.urlDo(r.documento), dados, folha.csrf()).then(function (resposta) {
        if (resposta.estado === "descartado" || resposta.estado === "sumiu") {
          if (linha.dataset.estado === "falta" && linha.dataset.contada === "1") folha.contar("falta", -1);
          folha.desenhar(linha, { estado: "descartado", arquivo: r.arquivo });
          folha.atualizarProgresso();
          toast("info", "Documento descartado", r.arquivo);
        } else {
          toast("erro", "Não descartado", resposta.motivo || "Tente de novo.", true);
        }
      });
    });
  };

  /* ====================================================================
     O ANEXO NA JANELA DA O.S.
     ==================================================================== */
  function mostrarAnexo(modal) {
    var raiz = document.getElementById("osdocFolha");
    var campoId = document.getElementById("osId");
    var corpo = modal.querySelector(".modal-body");
    if (!corpo) return;
    var faixa = corpo.querySelector(".ls-osdoc-anexo");
    if (faixa) faixa.remove();
    var id = campoId ? campoId.value : "";
    if (!id || !raiz || !raiz.dataset.urlAnexos) return;
    var url = raiz.dataset.urlAnexos.replace(/\/0\/documentos\/$/, "/" + id + "/documentos/") + "?formato=json";
    window.fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }, cache: "no-store" })
      .then(function (resposta) { return resposta.ok ? resposta.json() : null; })
      .then(function (json) {
        if (!json || !json.documentos || !json.documentos.length || document.getElementById("osId").value !== id) return;
        var anexo = el("div", "ls-osdoc-anexo");
        anexo.appendChild(icone("bi-paperclip"));
        anexo.appendChild(document.createTextNode("Lida do documento "));
        json.documentos.forEach(function (documento, posicao) {
          if (posicao) anexo.appendChild(document.createTextNode(" · "));
          anexo.appendChild(el("strong", "", documento.arquivo));
          var link = el("a", "", "Abrir");
          link.href = documento.url;
          link.target = "_blank";
          link.rel = "noopener";
          anexo.appendChild(document.createTextNode(" "));
          anexo.appendChild(link);
        });
        anexo.appendChild(el("span", "", "· enviado em " + json.documentos[0].enviado_em));
        var antiga = corpo.querySelector(".ls-osdoc-anexo");
        if (antiga) antiga.remove();
        corpo.insertBefore(anexo, corpo.firstChild);
      })
      .catch(function () { /* o anexo é informação a mais; a O.S. abre igual */ });
  }

  if (!window.__lsOsdocAnexo) {
    window.__lsOsdocAnexo = true;
    document.addEventListener("shown.bs.modal", function (evento) {
      if (evento.target && evento.target.id === "modalOS") mostrarAnexo(evento.target);
    });
  }

  /* ====================================================================
     LIGAR NA TELA
     ==================================================================== */
  function iniciar() {
    var raiz = document.getElementById("osdocFolha");
    if (raiz && !raiz._lsFolha) {
      raiz._lsFolha = new Folha(raiz);
      document.querySelectorAll("[data-osdoc-abrir]").forEach(function (botao) {
        botao.addEventListener("click", function () { raiz._lsFolha.abrir(); });
      });
    }
    var parametros = new URLSearchParams(window.location.search);
    if (raiz && parametros.get("importar") === "1") {
      raiz._lsFolha.abrir();
      limparParametro("importar");
    }
    var pedida = parametros.get("abrir_os");
    if (pedida && /^\d+$/.test(pedida)) {
      limparParametro("abrir_os");
      /* Depois do script da tela: é ele que liga o botão de editar. */
      window.setTimeout(function () { clicarNaOS(pedida); }, 120);
    }
  }

  if (window.LSTela && typeof window.LSTela.pronto === "function") window.LSTela.pronto(iniciar);
  else iniciar();
})(window, document);
