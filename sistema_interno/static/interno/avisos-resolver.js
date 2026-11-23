/* ======================================================================
   A FOLHA QUE RESOLVE O AVISO ALI MESMO (LEIA-ME-V10, seção 116)
   ----------------------------------------------------------------------
   O pedido: "melhore as notificações, deixe modais para solucionar
   problemas pequenos e afins". O sino dizia "Cadastros de clientes
   incompletos (19) -- toque para corrigir", e o toque levava à tela de
   Clientes, onde ainda era preciso achar cada um dos dezenove.

   Agora o aviso que tem conserto pequeno (`data-resolver` no item, no
   sino e no Início) abre uma FOLHA -- a mesma casca das folhas do
   ls-aviso: cartão no meio no computador, folha que sobe de baixo no
   celular, cores do sol, da lua e do eclipse. Dentro dela:

     clientes    cada cliente com SÓ o que falta (contato/WhatsApp,
                 CPF/CNPJ conferido pelo dígito, endereço que o CEP
                 preenche). Salva um por um, sem fechar; o completo sai
                 da lista e o contador cai na hora.
     propostas   em aberto, a vencer, vencidas e recusadas: reenviar no
                 WhatsApp, lembrar por e-mail, registrar a recusa, marcar
                 como expirada e abrir a proposta.
     aprovadas   o resumo, o PRAZO de entrega (vai para a Cláusula 3ª),
                 gerar o contrato, mandar o link de assinatura e abrir.
     pedidos     o botão do andamento da tela de Pedidos (a folha dele
                 é a do producao-etiquetas.js).
     estoque     o que está no mínimo, para a compra.

   O QUE ESTE ARQUIVO NÃO DECIDE. Nem a lista (vem de /avisos/resolver/,
   `resolver_avisos.py`, a mesma consulta do número) nem a permissão: cada
   botão aparece porque o servidor disse que a função pode, e cada
   gravação vai ao endereço que a tela de origem já usa, que confere de
   novo. Nada de `alert`/`confirm`: o "tem certeza?" é a folha do LSAviso.

   NAVEGAÇÃO SUAVE. O sino mora no topo, que a troca de tela não refaz;
   este arquivo carrega uma vez por aba e escuta por delegação no
   documento -- o item do Início, que chega a cada visita, funciona sem
   ninguém ligar nada de novo. Trocou de tela, a folha fecha; a tela
   recarregou no mesmo endereço (o andamento de um pedido chama
   `LSAtualizarTela`), a folha relê a lista.
   ====================================================================== */
(function (window, document) {
  "use strict";

  if (window.LSResolverAvisos) return;

  /* ------------------------------------------------------------ apoio */
  var contador = 0;
  var aberta = null;

  function csrf() {
    var campo = document.querySelector("[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function criar(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto != null && texto !== "") el.textContent = texto;
    return el;
  }

  function icone(nome) {
    var i = criar("i", "bi " + nome);
    i.setAttribute("aria-hidden", "true");
    return i;
  }

  function botao(classe, nomeIcone, rotulo) {
    var b = criar("button", classe);
    b.type = "button";
    if (nomeIcone) b.appendChild(icone(nomeIcone));
    b.appendChild(criar("span", "", rotulo));
    return b;
  }

  function plural(n, um, varios) {
    return n + " " + (n === 1 ? um : varios);
  }

  function semMovimento() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function noCelular() {
    return window.matchMedia && window.matchMedia("(max-width: 640px)").matches;
  }

  function toast(nivel, titulo, texto) {
    if (window.LSAviso) window.LSAviso.toast({ nivel: nivel, titulo: titulo, texto: texto || "" });
  }

  function confirmar(opcoes) {
    if (window.LSAviso && window.LSAviso.confirmar) return window.LSAviso.confirmar(opcoes);
    /* Sem a folha do LSAviso não há como perguntar direito: não faz. */
    return Promise.resolve(false);
  }

  function enderecoDaFolha(chave) {
    var modelo = document.body.getAttribute("data-resolver-url") || "";
    return modelo ? modelo.replace("CHAVE", encodeURIComponent(chave)) : "";
  }

  function lerResposta(resposta, padrao) {
    return resposta.json().catch(function () { return null; }).then(function (corpo) {
      if (!resposta.ok || !corpo || corpo.status !== "sucesso") {
        throw new Error((corpo && corpo.msg) || padrao);
      }
      return corpo;
    });
  }

  /* POST com o token e o cabeçalho do painel. Passa por `Painel.rede.post`
     quando ele existe: é quem acorda o servidor que dormiu enquanto a
     pessoa estava no WhatsApp, sem repetir a gravação. */
  function postar(url, campos) {
    var dados = campos instanceof FormData ? campos : new FormData();
    if (!(campos instanceof FormData)) {
      Object.keys(campos || {}).forEach(function (chave) { dados.append(chave, campos[chave]); });
    }
    if (!dados.get("csrfmiddlewaretoken")) dados.append("csrfmiddlewaretoken", csrf());
    var opcoes = {
      method: "POST",
      body: dados,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" }
    };
    var envio = window.Painel && window.Painel.rede && window.Painel.rede.post
      ? window.Painel.rede.post(url, opcoes)
      : fetch(url, opcoes);
    return envio.then(function (resposta) {
      return lerResposta(resposta, "Não foi possível gravar agora. Tente de novo.");
    }, function () {
      throw new Error("A conexão caiu antes de o servidor responder. Nada foi gravado: tente de novo.");
    });
  }

  function buscar(url) {
    return fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
    }).then(function (resposta) {
      return lerResposta(resposta, "Não foi possível abrir a lista agora.");
    });
  }

  /* Gravou: o sino e as bolinhas acompanham sem esperar o próximo pulso. */
  function avisarGravacao() {
    if (window.Painel && window.Painel.confirmarGravacao) window.Painel.confirmarGravacao();
  }

  /* O número do próprio aviso cai junto, no sino e no Início, antes de a
     resposta do servidor chegar. A resposta confirma (ou corrige). */
  function baixarNumeroDoAviso(chave, quantidade) {
    document.querySelectorAll('[data-aviso="' + chave + '"] .ls-aviso-quantidade').forEach(function (selo) {
      selo.textContent = String(Math.max(0, quantidade));
    });
  }

  function iniciais(nome) {
    var partes = String(nome || "?").trim().split(/\s+/).filter(Boolean);
    var letras = (partes[0] || "?").charAt(0) + (partes.length > 1 ? partes[partes.length - 1].charAt(0) : "");
    return letras.toUpperCase();
  }

  /* ------------------------------------------- CPF e CNPJ pelo dígito
     A mesma conta de validacoes.py (CPF e o CNPJ alfanumérico de 2026).
     O servidor confere de novo; aqui é para a pessoa saber ANTES de
     salvar que o número não fecha. */
  function digitoModulo11(valores, pesos) {
    var soma = 0;
    for (var i = 0; i < valores.length; i++) soma += valores[i] * pesos[i];
    var resto = soma % 11;
    return resto < 2 ? 0 : 11 - resto;
  }

  function conferirDocumento(texto) {
    var chave = String(texto || "").toUpperCase().replace(/[^0-9A-Z]/g, "");
    if (!chave) return { vazio: true };
    if (chave.length === 11 && /^\d+$/.test(chave)) {
      if (/^(\d)\1+$/.test(chave)) return { tipo: "CPF", valido: false };
      var base = chave.slice(0, 9).split("").map(Number);
      var d1 = digitoModulo11(base, [10, 9, 8, 7, 6, 5, 4, 3, 2]);
      var d2 = digitoModulo11(base.concat(d1), [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]);
      return { tipo: "CPF", valido: chave.slice(-2) === "" + d1 + d2 };
    }
    if (chave.length === 14 && /^[0-9A-Z]{12}\d{2}$/.test(chave)) {
      if (/^(.)\1+$/.test(chave)) return { tipo: "CNPJ", valido: false };
      var valores = chave.slice(0, 12).split("").map(function (c) { return c.charCodeAt(0) - 48; });
      var p1 = digitoModulo11(valores, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
      var p2 = digitoModulo11(valores.concat(p1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
      return { tipo: "CNPJ", valido: chave.slice(-2) === "" + p1 + p2 };
    }
    return { tipo: chave.length > 11 ? "CNPJ" : "CPF", incompleto: true, valido: false };
  }

  function telefoneValido(texto) {
    var numero = String(texto || "").replace(/\D/g, "");
    if (numero.indexOf("55") === 0 && (numero.length === 12 || numero.length === 13)) numero = numero.slice(2);
    return (numero.length === 10 || numero.length === 11) && numero.slice(0, 2) !== "00";
  }

  function emailValido(texto) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(texto || "").trim());
  }

  /* ----------------------------------------------- campos e chips
     Chip é rádio dentro de <label> (nunca lista suspensa): `.is-marcado` vem
     do JavaScript para o tablet sem `:has()`. */
  function campo(rotulo, nome, opcoes) {
    opcoes = opcoes || {};
    contador += 1;
    var id = "lsRes" + contador;
    var caixa = criar("div", "ls-res-campo" + (opcoes.largo ? " largo" : "") + (opcoes.curto ? " curto" : ""));
    var etiqueta = criar("label", "form-label" + (opcoes.rotuloOculto ? " visually-hidden" : ""), rotulo);
    etiqueta.htmlFor = id;
    var entrada = criar(opcoes.multilinha ? "textarea" : "input", "form-control");
    entrada.id = id;
    entrada.name = nome;
    if (!opcoes.multilinha) entrada.type = opcoes.tipo || "text";
    if (opcoes.multilinha) entrada.rows = opcoes.linhas || 2;
    if (opcoes.mascara) entrada.setAttribute("data-mascara", opcoes.mascara);
    if (opcoes.modo) entrada.inputMode = opcoes.modo;
    if (opcoes.limite) entrada.maxLength = opcoes.limite;
    if (opcoes.dica) entrada.placeholder = opcoes.dica;
    if (opcoes.valor) entrada.value = opcoes.valor;
    if (opcoes.completar) entrada.autocomplete = opcoes.completar;
    else entrada.autocomplete = "off";
    caixa.appendChild(etiqueta);
    caixa.appendChild(entrada);
    if (opcoes.nota) {
      var nota = criar("small", "ls-res-nota", opcoes.nota);
      nota.id = id + "Nota";
      entrada.setAttribute("aria-describedby", nota.id);
      caixa.appendChild(nota);
    }
    return { caixa: caixa, entrada: entrada, id: id };
  }

  function chips(nome, opcoes, legenda) {
    var grupo = criar("fieldset", "ls-res-chips");
    if (legenda) grupo.appendChild(criar("legend", "ls-res-legenda", legenda));
    opcoes.forEach(function (opcao) {
      var chip = criar("label", "ls-res-chip" + (opcao.classe ? " " + opcao.classe : ""));
      var radio = criar("input");
      radio.type = "radio";
      radio.name = nome;
      radio.value = opcao.valor;
      if (opcao.marcado) { radio.checked = true; chip.classList.add("is-marcado"); }
      chip.appendChild(radio);
      chip.appendChild(criar("span", "", opcao.rotulo));
      grupo.appendChild(chip);
    });
    grupo.addEventListener("change", function () {
      grupo.querySelectorAll(".ls-res-chip").forEach(function (chip) {
        var radio = chip.querySelector("input");
        chip.classList.toggle("is-marcado", Boolean(radio && radio.checked));
      });
    });
    return grupo;
  }

  function erroDaLinha(onde) {
    var erro = criar("p", "ls-res-erro");
    erro.setAttribute("role", "alert");
    erro.hidden = true;
    onde.appendChild(erro);
    return function (texto) {
      erro.textContent = texto || "";
      erro.hidden = !texto;
    };
  }

  function ocupar(b, rotulo) {
    b.disabled = true;
    b.setAttribute("aria-busy", "true");
    b.dataset.rotuloOriginal = b.innerHTML;
    b.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span></span>';
    b.lastChild.textContent = rotulo || "Salvando";
  }

  function liberar(b) {
    b.disabled = false;
    b.removeAttribute("aria-busy");
    if (b.dataset.rotuloOriginal) b.innerHTML = b.dataset.rotuloOriginal;
  }

  /* ==================================================================
     A FOLHA (o casco)
     ================================================================== */
  function fecharAberta(imediato) {
    if (aberta) aberta.fechar(imediato);
  }

  function abrir(chave, origem) {
    var endereco = enderecoDaFolha(chave);
    if (!endereco) return false;
    fecharAberta(true);
    if (window.LSFecharAvisos) window.LSFecharAvisos();

    contador += 1;
    var id = "lsFolhaResolver" + contador;
    var janela = criar("dialog", "ls-recado-folha ls-folha-resolver");
    janela.setAttribute("aria-labelledby", id + "Titulo");
    janela.dataset.chave = chave;
    var cartao = criar("div", "ls-recado-folha-cartao ls-folha-resolver-cartao");
    janela.appendChild(cartao);

    var topo = criar("header", "ls-res-topo");
    var alca = criar("span", "ls-recado-folha-alca");
    alca.setAttribute("aria-hidden", "true");
    topo.appendChild(alca);
    var linhaTopo = criar("div", "ls-res-topo-linha");
    var marca = criar("span", "ls-res-marca");
    var marcaIcone = icone((origem && origem.icone) || "bi-bell");
    marca.appendChild(marcaIcone);
    var textos = criar("div", "ls-res-textos");
    var titulo = criar("h2", "ls-recado-folha-titulo ls-res-titulo", (origem && origem.titulo) || "Avisos");
    titulo.id = id + "Titulo";
    var instrucao = criar("p", "ls-res-instrucao", "");
    textos.appendChild(titulo);
    textos.appendChild(instrucao);
    var placar = criar("span", "ls-res-placar");
    placar.setAttribute("aria-live", "polite");
    placar.hidden = true;
    var fecharX = botao("ls-res-fechar", "bi-x-lg", "");
    fecharX.setAttribute("aria-label", "Fechar");
    linhaTopo.appendChild(marca);
    linhaTopo.appendChild(textos);
    linhaTopo.appendChild(placar);
    linhaTopo.appendChild(fecharX);
    topo.appendChild(linhaTopo);
    cartao.appendChild(topo);

    var corpo = criar("div", "ls-res-corpo");
    cartao.appendChild(corpo);

    var rodape = criar("footer", "ls-res-rodape");
    var tela = criar("a", "ls-recado-botao ls-res-tela");
    tela.href = (origem && origem.url) || "#";
    tela.appendChild(icone("bi-box-arrow-up-right"));
    tela.appendChild(criar("span", "", "Abrir a tela"));
    var pronto = botao("ls-recado-botao ls-recado-botao--primario", "", "Fechar");
    rodape.appendChild(tela);
    rodape.appendChild(pronto);
    cartao.appendChild(rodape);

    var anterior = document.activeElement;
    var fechada = false;
    var enderecoDaTela = window.location.href;

    function fechar(imediato) {
      if (fechada) return;
      fechada = true;
      if (aberta && aberta.janela === janela) aberta = null;
      document.removeEventListener("ls:tela", aoTrocarDeTela);
      janela.classList.add("is-saindo");
      window.setTimeout(function () {
        try { if (janela.open) janela.close(); } catch (erro) { /* nada */ }
        /* Os toasts moram DENTRO da janela modal aberta (é o único jeito
           de ficarem por cima dela, ver ls-aviso.js): antes de a folha
           sair, a pilha volta para o corpo, senão iria junto. */
        var pilha = janela.querySelector(".ls-recados-pilha");
        if (pilha) document.body.appendChild(pilha);
        janela.remove();
        if (!document.querySelector(".ls-recado-folha")) {
          document.documentElement.classList.remove("ls-recado-travado");
        }
        if (anterior && anterior.isConnected && typeof anterior.focus === "function") {
          try { anterior.focus({ preventScroll: true }); } catch (erro) { /* nada */ }
        }
      }, imediato || semMovimento() ? 0 : 170);
    }

    /* Trocou de tela (o link "Abrir a tela" leva a navegação suave
       junto): a folha sai. Recarregou o MESMO endereço -- o andamento do
       pedido faz isso --: a folha continua e relê a lista. */
    function aoTrocarDeTela() {
      if (window.location.href !== enderecoDaTela) { fechar(true); return; }
      document.documentElement.classList.add("ls-recado-travado");
      carregar();
    }
    document.addEventListener("ls:tela", aoTrocarDeTela);

    fecharX.addEventListener("click", function () { fechar(); });
    pronto.addEventListener("click", function () { fechar(); });
    janela.addEventListener("cancel", function (evento) { evento.preventDefault(); fechar(); });
    janela.addEventListener("click", function (evento) {
      if (evento.target === janela) { fechar(); return; }
      /* Um link de dentro (abrir a tela, a proposta, o cartão) vai embora
         com a navegação suave; a folha não fica por cima da tela nova. */
      var link = evento.target.closest ? evento.target.closest("a[href]") : null;
      if (link && link.target !== "_blank" && !link.hasAttribute("download")) fechar(true);
    });
    /* A folha do andamento (outra folha por cima desta) solta a trava da
       página ao fechar; o primeiro toque aqui a põe de volta. */
    janela.addEventListener("pointerdown", function () {
      document.documentElement.classList.add("ls-recado-travado");
    });

    ligarArraste(topo, cartao, fechar);

    document.body.appendChild(janela);
    document.documentElement.classList.add("ls-recado-travado");
    if (typeof janela.showModal === "function") {
      janela.showModal();
    } else {
      janela.setAttribute("open", "");
      janela.classList.add("sem-camada");
    }
    fecharX.focus();

    var estado = {
      chave: chave,
      quantidade: 0,
      janela: janela,
      corpo: corpo,
      placar: placar,
      fechar: fechar,
    };

    function carregar() {
      corpo.setAttribute("aria-busy", "true");
      if (!corpo.childElementCount) corpo.appendChild(esqueleto());
      return buscar(endereco).then(function (dados) {
        if (fechada) return;
        titulo.textContent = dados.titulo || titulo.textContent;
        instrucao.textContent = dados.instrucao || "";
        if (dados.icone) marcaIcone.className = "bi " + dados.icone;
        if (dados.tela && dados.tela.url) {
          tela.href = dados.tela.url;
          tela.lastChild.textContent = dados.tela.rotulo || "Abrir a tela";
        }
        estado.dados = dados;
        estado.quantidade = Number(dados.quantidade) || 0;
        desenharCorpo(estado);
      }).catch(function (erro) {
        if (fechada) return;
        corpo.textContent = "";
        var falha = criar("div", "ls-res-vazio is-erro");
        falha.appendChild(icone("bi-wifi-off"));
        falha.appendChild(criar("strong", "", "Não deu para abrir a lista"));
        falha.appendChild(criar("p", "", erro.message));
        var denovo = botao("ls-res-botao", "bi-arrow-clockwise", "Tentar de novo");
        denovo.addEventListener("click", carregar);
        falha.appendChild(denovo);
        corpo.appendChild(falha);
      }).finally(function () {
        corpo.removeAttribute("aria-busy");
      });
    }
    estado.carregar = carregar;

    aberta = { janela: janela, fechar: fechar, chave: chave, estado: estado };
    carregar();
    return true;
  }

  /* No celular a folha desce com o dedo, como as do aparelho -- puxando
     pelo topo, para a lista continuar rolando por dentro. */
  function ligarArraste(alvo, cartao, fechar) {
    var inicio = null;
    alvo.addEventListener("pointerdown", function (evento) {
      if (!noCelular() || evento.button !== 0 || evento.target.closest("button, a, input, label")) return;
      inicio = { y: evento.clientY, id: evento.pointerId, dy: 0 };
    });
    alvo.addEventListener("pointermove", function (evento) {
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
    alvo.addEventListener("pointerup", soltar);
    alvo.addEventListener("pointercancel", soltar);
  }

  function esqueleto() {
    var caixa = criar("div", "ls-res-esqueleto");
    caixa.setAttribute("aria-label", "Carregando a lista");
    for (var i = 0; i < 3; i++) caixa.appendChild(criar("span", "ls-res-esqueleto-linha"));
    return caixa;
  }

  function pintarPlacar(estado) {
    var tipo = estado.dados && estado.dados.tipo;
    var n = estado.quantidade;
    estado.placar.hidden = false;
    estado.placar.textContent = "";
    estado.placar.appendChild(criar("strong", "", String(n)));
    var rotulo = {
      clientes: n === 1 ? "falta" : "faltam",
      propostas: n === 1 ? "proposta" : "propostas",
      pedidos: n === 1 ? "pedido" : "pedidos",
      estoque: n === 1 ? "item" : "itens"
    }[tipo] || "";
    estado.placar.appendChild(criar("small", "", rotulo));
    estado.placar.classList.toggle("is-zerado", n === 0);
    baixarNumeroDoAviso(estado.chave, n);
  }

  /* Uma linha resolvida: o número cai, a linha sai e, se a lista acabou
     mas ainda há mais do que coube nela, a próxima leva é buscada. */
  function resolvida(estado, item, texto) {
    estado.quantidade = Math.max(0, estado.quantidade - 1);
    pintarPlacar(estado);
    item.classList.add("is-resolvido");
    var selo = criar("p", "ls-res-feito");
    selo.appendChild(icone("bi-check2-circle"));
    selo.appendChild(criar("span", "", texto || "Resolvido"));
    item.appendChild(selo);
    window.setTimeout(function () {
      item.classList.add("is-saindo");
      window.setTimeout(function () {
        var lista = item.parentNode;
        var proximo = item.nextElementSibling;
        item.remove();
        if (lista && !lista.querySelector(".ls-res-item")) {
          if (estado.quantidade > 0) estado.carregar();
          else desenharVazio(estado);
        } else if (proximo && proximo._lsAbrir) {
          proximo._lsAbrir(true);
        }
      }, semMovimento() ? 0 : 260);
    }, semMovimento() ? 300 : 900);
    avisarGravacao();
  }

  function desenharVazio(estado) {
    estado.corpo.textContent = "";
    var vazio = criar("div", "ls-res-vazio");
    vazio.appendChild(icone("bi-check2-all"));
    vazio.appendChild(criar("strong", "", "Tudo resolvido por aqui"));
    vazio.appendChild(criar("p", "", "Nada mais esperando neste aviso. Pode fechar."));
    estado.corpo.appendChild(vazio);
    pintarPlacar(estado);
  }

  function desenharCorpo(estado) {
    var dados = estado.dados;
    var corpo = estado.corpo;
    corpo.textContent = "";
    pintarPlacar(estado);
    var itens = dados.itens || [];
    if (!itens.length) { desenharVazio(estado); return; }

    var lista = criar("ul", "ls-res-lista");
    corpo.appendChild(lista);
    var depois = [];
    var desenhar = {
      clientes: linhaDeCliente,
      propostas: linhaDeProposta,
      pedidos: linhaDePedido,
      estoque: linhaDeEstoque
    }[dados.tipo];
    itens.forEach(function (item) {
      if (desenhar) lista.appendChild(desenhar(item, estado, depois));
    });
    depois.forEach(function (fn) { fn(); });
    if (window.Painel && window.Painel.aplicarMascaras) window.Painel.aplicarMascaras(corpo);

    if (Number(dados.quantidade) > itens.length) {
      corpo.appendChild(criar("p", "ls-res-mais",
        "Mostrando " + itens.length + " de " + dados.quantidade
        + ". Resolva estes e a folha traz os próximos, ou abra a tela."));
    }

    /* Cadastro: o primeiro já abre, para quem veio completar começar a
       digitar sem mais um toque. */
    var primeiro = lista.querySelector(".ls-res-item");
    if (dados.tipo === "clientes" && primeiro && primeiro._lsAbrir) primeiro._lsAbrir(true);
  }

  /* ==================================================================
     CLIENTES: só o que falta, salvo um por um
     ================================================================== */
  var ROTULO_DA_FALTA = { contato: "Contato", documento: "CPF/CNPJ", endereco: "Endereço" };

  function linhaDeCliente(item, estado, depois) {
    var li = criar("li", "ls-res-item ls-res-cliente");
    li.dataset.id = item.id;

    var linha = criar("button", "ls-res-linha");
    linha.type = "button";
    linha.setAttribute("aria-expanded", "false");
    var avatar = criar("span", "ls-res-avatar", iniciais(item.nome));
    avatar.setAttribute("aria-hidden", "true");
    var nome = criar("span", "ls-res-nome");
    nome.appendChild(criar("strong", "", item.nome));
    nome.appendChild(criar("small", "", item.tipo + (item.com_proposta ? " · tem proposta viva" : "")));
    var faltas = criar("span", "ls-res-faltas");
    function pintarFaltas(lista) {
      faltas.textContent = "";
      lista.forEach(function (falta) {
        var selo = criar("span", "ls-res-falta", ROTULO_DA_FALTA[falta] || falta);
        if (falta === "documento" && item.documento_invalido) selo.textContent = "CPF/CNPJ inválido";
        faltas.appendChild(selo);
      });
    }
    pintarFaltas(item.faltas || []);
    linha.appendChild(avatar);
    linha.appendChild(nome);
    linha.appendChild(faltas);
    linha.appendChild(icone("bi-chevron-down ls-res-seta"));
    li.appendChild(linha);

    var form = criar("form", "ls-res-form");
    form.method = "post";
    form.noValidate = true;
    form.setAttribute("action", estado.dados.urls.salvar);
    form.hidden = true;
    contador += 1;
    form.id = "lsResForm" + contador;
    linha.setAttribute("aria-controls", form.id);
    [["csrfmiddlewaretoken", csrf()], ["action", "completar"], ["id", item.id]].forEach(function (par) {
      var oculto = criar("input");
      oculto.type = "hidden";
      oculto.name = par[0];
      oculto.value = par[1];
      form.appendChild(oculto);
    });

    var blocos = {};

    /* CONTATO: telefone (e se é WhatsApp) ou e-mail; um dos dois basta. */
    var contato = criar("fieldset", "ls-res-bloco");
    contato.appendChild(criar("legend", "ls-res-bloco-titulo")).appendChild(icone("bi-telephone"));
    contato.querySelector("legend").appendChild(document.createTextNode(" Contato"));
    var camposContato = criar("div", "ls-res-campos");
    var telefone = campo("Telefone / WhatsApp", "telefone", {
      mascara: "telefone", modo: "tel", limite: 24, dica: "(11) 99999-9999",
    });
    var email = campo("E-mail", "email", { tipo: "email", limite: 150, dica: "cliente@exemplo.com", modo: "email" });
    camposContato.appendChild(telefone.caixa);
    camposContato.appendChild(email.caixa);
    contato.appendChild(camposContato);
    /* Quem cai aqui não tem telefone nenhum: o número que chega agora é,
       quase sempre, o do WhatsApp -- a resposta comum já vem marcada. */
    contato.appendChild(chips("canal_telefone", [
      { valor: "whatsapp", rotulo: "Tem WhatsApp", marcado: item.canal !== "telefone" },
      { valor: "telefone", rotulo: "Só ligação", marcado: item.canal === "telefone" },
      { valor: "nao_confirmado", rotulo: "Ainda não sei" },
    ], "Este número tem WhatsApp?"));
    contato.appendChild(criar("small", "ls-res-nota", "Um dos dois basta para sair da lista."));
    blocos.contato = contato;

    /* CPF/CNPJ: conferido pelo dígito enquanto se digita. */
    var documento = criar("fieldset", "ls-res-bloco");
    documento.appendChild(criar("legend", "ls-res-bloco-titulo")).appendChild(icone("bi-person-vcard"));
    documento.querySelector("legend").appendChild(document.createTextNode(" CPF ou CNPJ"));
    var doc = campo(item.documento_invalido ? "Corrija o número guardado" : "CPF ou CNPJ", "documento", {
      mascara: "documento", modo: "text", limite: 20, rotuloOculto: !item.documento_invalido,
      dica: "CPF ou CNPJ, só os números", valor: item.documento || "", largo: true,
    });
    var docStatus = criar("small", "ls-res-conferencia", item.documento_invalido
      ? "Este número não fecha os dígitos verificadores." : "Conferido pelos dígitos antes de salvar.");
    if (item.documento_invalido) docStatus.classList.add("erro");
    doc.caixa.appendChild(docStatus);
    documento.appendChild(doc.caixa);
    function conferirDoc() {
      var resultado = conferirDocumento(doc.entrada.value);
      docStatus.classList.remove("erro", "sucesso");
      doc.entrada.classList.remove("is-invalid", "is-valid");
      if (resultado.vazio) { docStatus.textContent = "Conferido pelos dígitos antes de salvar."; return resultado; }
      if (resultado.incompleto) { docStatus.textContent = "Faltam números"; return resultado; }
      docStatus.textContent = resultado.valido
        ? resultado.tipo + " válido"
        : resultado.tipo + " com dígito errado: confira o número";
      docStatus.classList.add(resultado.valido ? "sucesso" : "erro");
      doc.entrada.classList.add(resultado.valido ? "is-valid" : "is-invalid");
      return resultado;
    }
    doc.entrada.addEventListener("input", conferirDoc);
    blocos.documento = documento;

    /* ENDEREÇO: o CEP preenche rua, bairro, cidade e UF. */
    var endereco = criar("fieldset", "ls-res-bloco");
    endereco.appendChild(criar("legend", "ls-res-bloco-titulo")).appendChild(icone("bi-geo-alt"));
    endereco.querySelector("legend").appendChild(document.createTextNode(" Endereço"));
    var camposEndereco = criar("div", "ls-res-campos ls-res-endereco");
    var cep = campo("CEP", "cep", { mascara: "cep", modo: "numeric", limite: 18, dica: "00000-000", curto: true });
    var cepStatus = criar("small", "ls-cep-status");
    contador += 1;
    cepStatus.id = "lsResCep" + contador;
    cep.caixa.appendChild(cepStatus);
    var rua = campo("Rua", "endereco", { limite: 120, largo: true });
    var numero = campo("Número", "numero", { limite: 10, curto: true });
    var complemento = campo("Complemento", "complemento", { limite: 60 });
    var bairro = campo("Bairro", "bairro", { limite: 50 });
    var cidade = campo("Cidade", "cidade", { limite: 60, largo: true });
    var uf = campo("UF", "estado", { limite: 20, curto: true });
    [cep, rua, numero, complemento, bairro, cidade, uf].forEach(function (c) { camposEndereco.appendChild(c.caixa); });
    endereco.appendChild(camposEndereco);
    var latitude = criar("input");
    latitude.type = "hidden"; latitude.name = "latitude"; contador += 1; latitude.id = "lsResLat" + contador;
    var longitude = criar("input");
    longitude.type = "hidden"; longitude.name = "longitude"; contador += 1; longitude.id = "lsResLon" + contador;
    endereco.appendChild(latitude);
    endereco.appendChild(longitude);
    endereco.appendChild(criar("small", "ls-res-nota", "Digite o CEP: rua, bairro, cidade e UF vêm sozinhos."));
    blocos.endereco = endereco;

    ["contato", "documento", "endereco"].forEach(function (parte) {
      blocos[parte].hidden = (item.faltas || []).indexOf(parte) === -1;
      form.appendChild(blocos[parte]);
    });

    var mostrarErro = erroDaLinha(form);
    var acoes = criar("div", "ls-res-acoes");
    if (item.ficha) {
      var ficha = criar("a", "ls-res-link");
      ficha.href = item.ficha;
      ficha.appendChild(icone("bi-pencil-square"));
      ficha.appendChild(criar("span", "", "Cadastro completo"));
      acoes.appendChild(ficha);
    }
    var salvar = criar("button", "ls-res-botao primario");
    salvar.type = "submit";
    salvar.appendChild(icone("bi-check2-circle"));
    salvar.appendChild(criar("span", "", "Salvar este cliente"));
    acoes.appendChild(salvar);
    form.appendChild(acoes);
    li.appendChild(form);

    depois.push(function () {
      if (window.Painel && window.Painel.ligarCep) {
        window.Painel.ligarCep({
          url: estado.dados.urls.cep,
          cep: cep.id,
          status: cepStatus.id,
          campos: { rua: rua.id, bairro: bairro.id, cidade: cidade.id, estado: uf.id },
          coordenadas: { latitude: latitude.id, longitude: longitude.id }
        });
      }
    });

    function abrirLinha(focar) {
      var lista = li.parentNode;
      if (lista) {
        lista.querySelectorAll(".ls-res-cliente.is-aberto").forEach(function (outro) {
          if (outro !== li && outro._lsFecharLinha) outro._lsFecharLinha();
        });
      }
      li.classList.add("is-aberto");
      form.hidden = false;
      linha.setAttribute("aria-expanded", "true");
      if (focar) {
        var primeiro = form.querySelector("fieldset:not([hidden]) input:not([type=hidden]):not([type=radio])");
        if (primeiro && !noCelular()) {
          try { primeiro.focus({ preventScroll: true }); } catch (e) { primeiro.focus(); }
        }
      }
      if (!focar) return;
      try { li.scrollIntoView({ block: "nearest", behavior: semMovimento() ? "auto" : "smooth" }); } catch (e) { /* nada */ }
    }
    function fecharLinha() {
      li.classList.remove("is-aberto");
      form.hidden = true;
      linha.setAttribute("aria-expanded", "false");
    }
    li._lsAbrir = abrirLinha;
    li._lsFecharLinha = fecharLinha;
    linha.addEventListener("click", function () {
      if (li.classList.contains("is-aberto")) fecharLinha();
      else abrirLinha(true);
    });

    /* O QUE SE CONFERE ANTES DE IR. O servidor confere tudo de novo; aqui
       é para a pessoa não esperar a rede só para saber que faltou o DDD. */
    function conferir() {
      var faltando = (li.dataset.faltas || (item.faltas || []).join("|")).split("|").filter(Boolean);
      var preencheu = false;
      if (faltando.indexOf("contato") !== -1) {
        var tel = telefone.entrada.value.trim();
        var mail = email.entrada.value.trim();
        if (tel && !telefoneValido(tel)) return [telefone.entrada, "Telefone incompleto: informe DDD e número."];
        if (mail && !emailValido(mail)) return [email.entrada, "E-mail inválido."];
        if (tel || mail) preencheu = true;
      }
      if (faltando.indexOf("documento") !== -1 && doc.entrada.value.trim()) {
        var resultado = conferirDoc();
        if (!resultado.valido) {
          return [doc.entrada, resultado.incompleto
            ? "O CPF tem 11 números e o CNPJ, 14."
            : resultado.tipo + " inválido: confira os dígitos."];
        }
        if (!item.documento || doc.entrada.value.trim() !== item.documento) preencheu = true;
      }
      if (faltando.indexOf("endereco") !== -1) {
        var algum = [cep, rua, numero, bairro, cidade, uf].some(function (c) { return c.entrada.value.trim(); });
        if (algum) {
          if (!rua.entrada.value.trim() || !cidade.entrada.value.trim()) {
            return [rua.entrada.value.trim() ? cidade.entrada : rua.entrada,
              "Para guardar o endereço, informe pelo menos a rua e a cidade (o CEP preenche)."];
          }
          preencheu = true;
        }
      }
      if (!preencheu) return [form.querySelector("fieldset:not([hidden]) input:not([type=hidden]):not([type=radio])"),
        "Preencha o que tiver agora; o resto pode vir depois."];
      return null;
    }

    form.addEventListener("submit", function (evento) {
      evento.preventDefault();
      evento.stopPropagation();
      mostrarErro("");
      var problema = conferir();
      if (problema) {
        mostrarErro(problema[1]);
        if (problema[0]) problema[0].focus();
        return;
      }
      var dados = new FormData(form);
      /* O bloco escondido não manda nada: um documento guardado que não
         estava em falta nunca é reescrito por esta folha. */
      Object.keys(blocos).forEach(function (parte) {
        if (!blocos[parte].hidden) return;
        blocos[parte].querySelectorAll("input[name]").forEach(function (entrada) { dados.delete(entrada.name); });
      });
      ocupar(salvar, "Salvando");
      postar(form.getAttribute("action"), dados).then(function (json) {
        var restante = json.faltas || [];
        if (!json.incompleto && !restante.length) {
          liberar(salvar);
          salvar.disabled = true;
          fecharLinha();
          linha.disabled = true;
          pintarFaltas([]);
          resolvida(estado, li, "Cadastro de " + item.nome + " completo");
          return;
        }
        /* Salvou uma parte: o que ficou pronto some, o resto continua. */
        liberar(salvar);
        li.dataset.faltas = restante.join("|");
        item.documento_invalido = false;
        pintarFaltas(restante);
        Object.keys(blocos).forEach(function (parte) {
          blocos[parte].hidden = restante.indexOf(parte) === -1;
        });
        toast("sucesso", "Salvo", "Ainda falta: " + restante.map(function (f) {
          return (ROTULO_DA_FALTA[f] || f).toLowerCase();
        }).join(", ") + ".");
        avisarGravacao();
      }).catch(function (erro) {
        liberar(salvar);
        mostrarErro(erro.message);
      });
    });

    return li;
  }

  /* ==================================================================
     PROPOSTAS: reenviar, lembrar, recusar, expirar, abrir
     ================================================================== */
  var MOTIVOS = ["Achou caro", "O prazo não serviu", "Comprou de outro", "Desistiu ou adiou"];

  function linhaDeProposta(item, estado) {
    var li = criar("li", "ls-res-item ls-res-proposta estado-" + item.estado);
    li.dataset.id = item.id;
    var acoes = item.acoes || {};
    var urls = estado.dados.urls || {};

    var cabeca = criar("div", "ls-res-cabeca");
    var numero = criar("span", "ls-res-numero", "#" + item.id);
    if (item.versao > 1) numero.appendChild(criar("small", "", "v" + item.versao));
    var nome = criar("div", "ls-res-nome");
    nome.appendChild(criar("strong", "", item.cliente));
    nome.appendChild(criar("small", "", [item.total, item.itens].filter(Boolean).join(" · ")));
    cabeca.appendChild(numero);
    cabeca.appendChild(nome);
    cabeca.appendChild(criar("span", "ls-res-estado " + item.estado, item.situacao));
    li.appendChild(cabeca);

    var meta = criar("p", "ls-res-meta");
    if (item.validade_texto) {
      var validade = criar("span", "ls-res-validade" + (item.vencida ? " vencida" : ""));
      validade.appendChild(icone(item.vencida ? "bi-calendar-x" : "bi-calendar-event"));
      validade.appendChild(criar("span", "", item.validade_texto + (item.validade ? " (" + item.validade + ")" : "")));
      meta.appendChild(validade);
    }
    if (item.resposta) {
      var resposta = criar("span", "ls-res-resposta");
      resposta.appendChild(icone("bi-chat-left-text"));
      resposta.appendChild(criar("span", "", item.resposta));
      meta.appendChild(resposta);
    } else if (item.enviada) {
      var envio = criar("span");
      envio.appendChild(icone("bi-send"));
      envio.appendChild(criar("span", "", item.enviada));
      meta.appendChild(envio);
    }
    li.appendChild(meta);

    if (item.motivo !== undefined) {
      var motivo = criar("blockquote", "ls-res-motivo");
      motivo.appendChild(criar("span", "ls-res-motivo-rotulo", "O que o cliente disse"));
      motivo.appendChild(criar("p", "", item.motivo || "Não escreveu o motivo. Vale ligar antes de refazer."));
      li.appendChild(motivo);
    }

    if (item.prazo || item.contrato) li.appendChild(blocoDaAprovada(item, estado, li));

    var mostrarErro = erroDaLinha(li);
    var barra = criar("div", "ls-res-acoes");

    if (acoes.whatsapp) {
      var whats = botao("ls-res-botao primario", "bi-whatsapp", acoes.whatsapp_rotulo || "Reenviar no WhatsApp");
      whats.addEventListener("click", function () { reenviar(item, whats, urls, mostrarErro); });
      barra.appendChild(whats);
    } else if (acoes.sem_whatsapp) {
      barra.appendChild(criar("span", "ls-res-dica", "Sem WhatsApp na proposta: abra para informar o número."));
    }
    if (acoes.email) {
      var mail = botao("ls-res-botao", "bi-envelope", "Lembrar por e-mail");
      mail.addEventListener("click", function () { lembrarPorEmail(item, mail, mostrarErro); });
      barra.appendChild(mail);
    }
    if (acoes.aprovar) {
      var aprovou = botao("ls-res-botao sucesso", "bi-hand-thumbs-up", "Cliente aprovou");
      aprovou.addEventListener("click", function () { aprovar(item, estado, li, urls, aprovou, mostrarErro); });
      barra.appendChild(aprovou);
    }
    var formRecusa = null;
    if (acoes.recusar) {
      var recusou = botao("ls-res-botao", "bi-hand-thumbs-down", "Cliente recusou");
      recusou.setAttribute("aria-expanded", "false");
      barra.appendChild(recusou);
      formRecusa = formularioDeRecusa(item, estado, li, urls, mostrarErro, recusou);
      recusou.addEventListener("click", function () {
        var abrirAgora = formRecusa.hidden;
        formRecusa.hidden = !abrirAgora;
        recusou.setAttribute("aria-expanded", String(abrirAgora));
        if (abrirAgora) formRecusa.querySelector("textarea").focus();
      });
    }
    if (acoes.expirar) {
      var expirou = botao("ls-res-botao", "bi-calendar-x", "Marcar como expirada");
      expirou.addEventListener("click", function () { expirar(item, estado, li, urls, expirou, mostrarErro); });
      barra.appendChild(expirou);
    }
    var abrirProposta = criar("a", "ls-res-link");
    abrirProposta.href = item.abrir;
    abrirProposta.appendChild(icone("bi-box-arrow-up-right"));
    abrirProposta.appendChild(criar("span", "", item.vencida || item.estado === "recusado"
      ? "Abrir para fazer a versão nova" : "Abrir a proposta"));
    barra.appendChild(abrirProposta);
    li.appendChild(barra);
    if (formRecusa) li.appendChild(formRecusa);
    return li;
  }

  /* REENVIAR: o "Enviar → WhatsApp" da lista de Orçamentos, o mesmo POST.
     A janela abre JÁ, no toque (fora do gesto o navegador bloqueia), e
     recebe a conversa quando o servidor devolve o link registrado. */
  function reenviar(item, b, urls, mostrarErro) {
    mostrarErro("");
    if (item.estado !== "rascunho") { abrirConversa(item, b, urls, mostrarErro); return; }
    /* No rascunho a pergunta vem antes: ele sai da gaveta e vira link. A
       conversa abre no toque do "sim", que também é gesto da pessoa. */
    confirmar({
      titulo: "Enviar a proposta #" + item.id + "?",
      texto: "Ela sai do rascunho e o cliente recebe o link para aprovar. Confira antes se itens e valores estão certos.",
      confirmar: "Enviar no WhatsApp",
      cancelar: "Ainda não",
      icone: "info"
    }).then(function (sim) {
      if (sim) abrirConversa(item, b, urls, mostrarErro);
    });
  }

  function abrirConversa(item, b, urls, mostrarErro) {
    var janela = window.open("", "_blank");
    ocupar(b, "Abrindo");
    postar(urls.orcamentos, { action: "enviar", id: item.id, canal: "whatsapp" }).then(function (json) {
      var destino = json.whatsapp_url || "";
      if (window.Painel && window.Painel.whatsapp && json.whatsapp && json.mensagem) {
        destino = window.Painel.whatsapp.web(json.whatsapp, json.mensagem) || destino;
      }
      if (janela && !janela.closed && destino) janela.location.href = destino;
      else if (destino) window.open(destino, "_blank");
      liberar(b);
      b.classList.add("feito");
      b.lastChild.textContent = "Enviado: confirme no WhatsApp";
      toast("sucesso", "Proposta #" + item.id, "A conversa abriu com a mensagem pronta. O envio ficou registrado.");
      avisarGravacao();
    }).catch(function (erro) {
      if (janela && !janela.closed) janela.close();
      liberar(b);
      mostrarErro(erro.message);
    });
  }

  function lembrarPorEmail(item, b, mostrarErro) {
    mostrarErro("");
    ocupar(b, "Enviando");
    postar("/orcamentos/" + encodeURIComponent(item.id) + "/lembrar/", {}).then(function (json) {
      liberar(b);
      b.disabled = true;
      b.classList.add("feito");
      b.lastChild.textContent = "Lembrete enviado";
      toast("sucesso", "Proposta #" + item.id, json.msg);
      avisarGravacao();
    }).catch(function (erro) {
      liberar(b);
      mostrarErro(erro.message);
    });
  }

  /* A RECUSA PEDE O MOTIVO, como na janela "Situação" da lista: é o que a
     versão seguinte vai corrigir. Os chips só adiantam a frase. */
  function formularioDeRecusa(item, estado, li, urls, mostrarErro, gatilho) {
    var form = criar("form", "ls-res-recusa");
    form.hidden = true;
    form.noValidate = true;
    var rapidos = chips("motivo_rapido_" + item.id, MOTIVOS.map(function (texto) {
      return { valor: texto, rotulo: texto };
    }), "Por que o cliente recusou?");
    form.appendChild(rapidos);
    var motivo = campo("Motivo (vai para a versão nova)", "motivo", {
      multilinha: true, linhas: 2, limite: 600, largo: true,
      dica: "O que o cliente falou: preço, prazo, escopo, comprou de outro…",
    });
    form.appendChild(motivo.caixa);
    rapidos.addEventListener("change", function (evento) {
      if (evento.target && evento.target.value) {
        motivo.entrada.value = evento.target.value;
        motivo.entrada.focus();
      }
    });
    var linha = criar("div", "ls-res-acoes");
    var cancelar = botao("ls-res-botao", "", "Cancelar");
    cancelar.addEventListener("click", function () {
      form.hidden = true;
      gatilho.setAttribute("aria-expanded", "false");
    });
    var registrar = criar("button", "ls-res-botao perigo");
    registrar.type = "submit";
    registrar.appendChild(icone("bi-hand-thumbs-down"));
    registrar.appendChild(criar("span", "", "Registrar a recusa"));
    linha.appendChild(cancelar);
    linha.appendChild(registrar);
    form.appendChild(linha);

    form.addEventListener("submit", function (evento) {
      evento.preventDefault();
      evento.stopPropagation();
      mostrarErro("");
      var texto = motivo.entrada.value.trim();
      if (!texto) {
        mostrarErro("Escreva por que o cliente recusou: é dele que a versão nova parte.");
        motivo.entrada.focus();
        return;
      }
      ocupar(registrar, "Registrando");
      postar(urls.orcamentos, { action: "status", id: item.id, status: "recusado", motivo: texto }).then(function () {
        form.hidden = true;
        li.querySelectorAll(".ls-res-acoes button").forEach(function (b) { b.disabled = true; });
        resolvida(estado, li, "Recusa registrada. Use “Nova proposta” na lista para a versão nova.");
      }).catch(function (erro) {
        liberar(registrar);
        mostrarErro(erro.message);
      });
    });
    return form;
  }

  /* APROVAÇÃO MANUAL (seção 121): o cliente disse sim por telefone, no
     WhatsApp ou no balcão. Um toque, uma pergunta clara, e a proposta vai
     para Aprovado com quem registrou e quando. O cartão não some: vira o
     próximo passo -- gerar o contrato para o cliente assinar. */
  function aprovar(item, estado, li, urls, b, mostrarErro) {
    mostrarErro("");
    confirmar({
      titulo: "O cliente aprovou a proposta #" + item.id + "?",
      texto: item.cliente + " · " + item.total + ". Registre quando ele aprovou por telefone, WhatsApp ou no balcão: a proposta vai para Aprovado, o prazo de produção começa a contar e o próximo passo é o contrato para ele assinar.",
      confirmar: "Sim, o cliente aprovou",
      cancelar: "Voltar",
      icone: "sucesso"
    }).then(function (sim) {
      if (!sim) return;
      ocupar(b, "Registrando");
      postar(urls.orcamentos, {
        action: "status", id: item.id, status: "aprovado",
        motivo: "Aprovada pelo cliente (registrada pela equipe)."
      }).then(function () {
        estado.quantidade = Math.max(0, estado.quantidade - 1);
        pintarPlacar(estado);
        li.classList.add("is-resolvido", "is-aprovado");
        var barraVelha = li.querySelector(".ls-res-acoes");
        if (barraVelha) barraVelha.remove();
        var formVelho = li.querySelector(".ls-res-recusa");
        if (formVelho) formVelho.remove();
        var passo = criar("div", "ls-res-proximo");
        var topo = criar("p", "ls-res-feito");
        topo.appendChild(icone("bi-check2-circle"));
        topo.appendChild(criar("span", "", "Aprovada agora. Próximo passo: o contrato para o cliente assinar."));
        passo.appendChild(topo);
        var acoes = criar("div", "ls-res-acoes");
        if (item.contrato_url) {
          var contrato = criar("a", "ls-res-botao primario");
          contrato.href = item.contrato_url;
          contrato.appendChild(icone("bi-pen"));
          contrato.appendChild(criar("span", "", "Gerar o contrato"));
          acoes.appendChild(contrato);
        }
        var ok = botao("ls-res-botao", "bi-check2", "Depois");
        ok.addEventListener("click", function () {
          li.classList.add("is-saindo");
          window.setTimeout(function () {
            var lista = li.parentNode;
            li.remove();
            if (lista && !lista.querySelector(".ls-res-item")) {
              if (estado.quantidade > 0) estado.carregar();
              else desenharVazio(estado);
            }
          }, semMovimento() ? 0 : 260);
        });
        acoes.appendChild(ok);
        passo.appendChild(acoes);
        li.appendChild(passo);
        toast("sucesso", "Proposta #" + item.id + " aprovada", "Registrada em seu nome. Gere o contrato para o cliente assinar.");
        avisarGravacao();
      }).catch(function (erro) {
        liberar(b);
        mostrarErro(erro.message);
      });
    });
  }

  function expirar(item, estado, li, urls, b, mostrarErro) {
    mostrarErro("");
    confirmar({
      titulo: "Marcar a proposta #" + item.id + " como expirada?",
      texto: "Ela sai da fila e não gera mais link. Para vender, o caminho é a versão nova com o preço de hoje.",
      confirmar: "Marcar como expirada",
      cancelar: "Voltar",
      icone: "alerta"
    }).then(function (sim) {
      if (!sim) return;
      ocupar(b, "Marcando");
      postar(urls.orcamentos, { action: "status", id: item.id, status: "expirado", motivo: "Expirada pela folha do sino." })
        .then(function () {
          li.querySelectorAll(".ls-res-acoes button").forEach(function (outro) { outro.disabled = true; });
          resolvida(estado, li, "Marcada como expirada");
        }).catch(function (erro) {
          liberar(b);
          mostrarErro(erro.message);
        });
    });
  }

  /* ------------------------------------------------- a aprovada
     O PRAZO é o de produção, em dias úteis depois da aprovação, que a
     Cláusula 3ª do contrato lê -- combinar a data é escrever este número
     antes de gerar o contrato. O CONTRATO é o do cartão de assinatura. */
  var PRAZOS_RAPIDOS = [10, 15, 20, 30, 45];

  function blocoDaAprovada(item, estado, li) {
    var caixa = criar("div", "ls-res-aprovada");
    var mostrarErro = null;

    if (item.prazo) {
      var prazo = item.prazo;
      var bloco = criar("section", "ls-res-passo");
      var cabeca = criar("div", "ls-res-passo-topo");
      cabeca.appendChild(criar("span", "ls-res-passo-numero", "1"));
      var textos = criar("div");
      textos.appendChild(criar("strong", "", "Prazo de entrega"));
      var nota = criar("small", "ls-res-nota", prazo.nota || "");
      textos.appendChild(nota);
      cabeca.appendChild(textos);
      bloco.appendChild(cabeca);

      var linha = criar("div", "ls-res-prazo");
      contador += 1;
      var idPrazo = "lsResPrazo" + contador;
      var entrada = criar("input", "form-control ls-res-prazo-dias");
      entrada.id = idPrazo;
      entrada.type = "number";
      entrada.inputMode = "numeric";
      entrada.min = "0";
      entrada.max = "250";
      entrada.step = "1";
      entrada.placeholder = "—";
      entrada.value = prazo.dias == null ? "" : String(prazo.dias);
      entrada.disabled = prazo.editavel === false;
      var rotulo = criar("label", "visually-hidden", "Prazo em dias úteis");
      rotulo.htmlFor = idPrazo;
      var unidade = criar("span", "ls-res-prazo-unidade", "dias úteis");
      var gravar = botao("ls-res-botao", "bi-check2", "Salvar prazo");
      gravar.disabled = prazo.editavel === false;
      linha.appendChild(rotulo);
      linha.appendChild(entrada);
      linha.appendChild(unidade);
      linha.appendChild(gravar);
      bloco.appendChild(linha);
      var rapidos = chips("prazo_rapido_" + item.id, PRAZOS_RAPIDOS.map(function (dias) {
        return { valor: String(dias), rotulo: dias + " dias", marcado: prazo.dias === dias };
      }), "");
      rapidos.classList.add("compactos");
      rapidos.addEventListener("change", function (evento) {
        if (evento.target && evento.target.value) { entrada.value = evento.target.value; salvarPrazo(); }
      });
      if (prazo.editavel !== false) bloco.appendChild(rapidos);
      var contratoNota = criar("small", "ls-res-nota ls-res-clausula", textoDaClausula(prazo));
      bloco.appendChild(contratoNota);
      caixa.appendChild(bloco);

      var salvarPrazo = function () {
        if (mostrarErro) mostrarErro("");
        var valor = entrada.value.trim();
        if (valor && !/^\d+$/.test(valor)) {
          if (mostrarErro) mostrarErro("Informe o prazo em dias úteis, só com números (ex.: 15).");
          entrada.focus();
          return;
        }
        ocupar(gravar, "Salvando");
        postar(prazo.url, { prazo: valor }).then(function (json) {
          liberar(gravar);
          var novo = json.prazo || {};
          prazo.dias = novo.dias;
          prazo.contrato = novo.dias == null ? prazo.contrato : novo.dias;
          nota.textContent = novo.nota || "";
          entrada.value = novo.dias == null ? "" : String(novo.dias);
          contratoNota.textContent = textoDaClausula(prazo);
          rapidos.querySelectorAll(".ls-res-chip").forEach(function (chip) {
            var radio = chip.querySelector("input");
            var igual = radio && novo.dias != null && radio.value === String(novo.dias);
            radio.checked = igual;
            chip.classList.toggle("is-marcado", igual);
          });
          bloco.classList.add("is-salvo");
          window.setTimeout(function () { bloco.classList.remove("is-salvo"); }, 1600);
          toast("sucesso", "Prazo combinado", json.msg);
          avisarGravacao();
        }).catch(function (erro) {
          liberar(gravar);
          if (mostrarErro) mostrarErro(erro.message);
        });
      };
      gravar.addEventListener("click", salvarPrazo);
      entrada.addEventListener("keydown", function (evento) {
        if (evento.key === "Enter") { evento.preventDefault(); salvarPrazo(); }
      });
    }

    if (item.contrato) caixa.appendChild(blocoDoContrato(item, estado, li));
    mostrarErro = erroDaLinha(caixa);
    caixa._lsErro = mostrarErro;
    return caixa;
  }

  function textoDaClausula(prazo) {
    if (prazo.dias == null) {
      return "Sem prazo combinado, o contrato sai com " + plural(prazo.contrato || 45, "dia útil", "dias úteis") + ".";
    }
    return "Vai para a Cláusula 3ª do contrato: " + (prazo.dias === 0 ? "pronta entrega" : plural(prazo.dias, "dia útil", "dias úteis")) + ".";
  }

  var TEXTO_DO_CONTRATO = {
    gerar: "Ainda não foi gerado.",
    aguardando: "Gerado: esperando o cliente assinar.",
    assinado: "Assinado.",
    suspenso: "Suspenso: a proposta mudou depois de o documento sair.",
    bloqueado: "Só sai com a proposta aprovada."
  };

  function blocoDoContrato(item, estado, li) {
    var contrato = item.contrato;
    var bloco = criar("section", "ls-res-passo");
    var cabeca = criar("div", "ls-res-passo-topo");
    cabeca.appendChild(criar("span", "ls-res-passo-numero", item.prazo ? "2" : "1"));
    var textos = criar("div");
    var papel = contrato.papel === "termo de compra" ? "Termo de compra"
      : contrato.papel === "ordem de serviço" ? "Ordem de serviço" : "Contrato";
    textos.appendChild(criar("strong", "", papel));
    var situacao = criar("small", "ls-res-nota");
    textos.appendChild(situacao);
    cabeca.appendChild(textos);
    bloco.appendChild(cabeca);
    var observacoes = criar("ul", "ls-res-observacoes");
    bloco.appendChild(observacoes);
    var barra = criar("div", "ls-res-acoes");
    bloco.appendChild(barra);

    function erro(texto) {
      var alvo = bloco.parentNode && bloco.parentNode._lsErro;
      if (alvo) alvo(texto);
      else if (texto) toast("erro", "Contrato", texto);
    }

    function pintar() {
      situacao.textContent = contrato.situacao === "assinado" && contrato.assinado_por
        ? "Assinado por " + contrato.assinado_por + "."
        : (TEXTO_DO_CONTRATO[contrato.situacao] || "");
      bloco.classList.toggle("is-feito", contrato.situacao === "assinado" || contrato.situacao === "aguardando");
      observacoes.textContent = "";
      (contrato.observacoes || []).forEach(function (texto) {
        var linha = criar("li");
        linha.appendChild(icone("bi-info-circle"));
        linha.appendChild(criar("span", "", texto));
        observacoes.appendChild(linha);
      });
      observacoes.hidden = !(contrato.observacoes || []).length;
      barra.textContent = "";
      if (contrato.situacao === "gerar") {
        var gerar = botao("ls-res-botao primario", "bi-file-earmark-text", "Gerar o " + papel.toLowerCase());
        gerar.addEventListener("click", function () { gerarContrato(gerar); });
        barra.appendChild(gerar);
      }
      if (contrato.situacao === "aguardando") {
        var whats = botao("ls-res-botao primario", "bi-whatsapp", "Mandar o link no WhatsApp");
        whats.addEventListener("click", function () { mandarLink(whats); });
        barra.appendChild(whats);
      }
      var cartao = criar("a", "ls-res-link");
      cartao.href = contrato.pagina;
      cartao.appendChild(icone(contrato.situacao === "assinado" ? "bi-file-earmark-check" : "bi-qr-code"));
      cartao.appendChild(criar("span", "", {
        assinado: "Ver o documento assinado",
        aguardando: "Abrir o cartão de assinatura (QR)"
      }[contrato.situacao] || "Abrir o cartão do contrato"));
      barra.appendChild(cartao);
    }

    function gerarContrato(b) {
      erro("");
      var prazo = item.prazo;
      var pergunta = prazo && prazo.dias == null
        ? confirmar({
          titulo: "Gerar sem prazo combinado?",
          texto: "A Cláusula 3ª sai com " + plural(prazo.contrato || 45, "dia útil", "dias úteis")
            + ". Se já combinou outra data com o cliente, salve o prazo antes.",
          confirmar: "Gerar assim mesmo",
          cancelar: "Combinar o prazo",
          icone: "alerta"
        })
        : Promise.resolve(true);
      pergunta.then(function (sim) {
        if (!sim) {
          var campoPrazo = li.querySelector(".ls-res-prazo-dias");
          if (campoPrazo) campoPrazo.focus();
          return;
        }
        ocupar(b, "Gerando");
        postar(contrato.gerar, { action: "gerar" }).then(function (json) {
          contrato.situacao = "aguardando";
          contrato.observacoes = [];
          pintar();
          toast("sucesso", papel + " gerado", json.msg);
          /* A parte da equipe está feita: a aprovada sai do número, mas a
             linha fica para mandar o link na sequência. */
          estado.quantidade = Math.max(0, estado.quantidade - 1);
          pintarPlacar(estado);
          avisarGravacao();
        }).catch(function (falha) {
          liberar(b);
          erro(falha.message);
        });
      });
    }

    function mandarLink(b) {
      erro("");
      var janela = window.open("", "_blank");
      ocupar(b, "Abrindo");
      // o diário de bordo do contrato (seção 109) anota o link como "WhatsApp"
      postar(contrato.link, { canal: "whatsapp" }).then(function (corpo) {
        var destino = corpo.whatsapp || corpo.whatsapp_sem_numero;
        if (!corpo.whatsapp) toast("info", "Sem WhatsApp na proposta", "Escolha a conversa do cliente no WhatsApp.");
        if (janela && !janela.closed) janela.location.href = destino;
        else window.location.href = destino;
        liberar(b);
        b.classList.add("feito");
        // o número vem do servidor (VALIDADE_DO_LINK, seção 117)
        b.lastChild.textContent = "Link enviado: vale " + Math.round((corpo.validade || 600) / 60) + " minutos";
      }).catch(function (falha) {
        if (janela && !janela.closed) janela.close();
        liberar(b);
        erro(falha.message);
      });
    }

    pintar();
    return bloco;
  }

  /* ==================================================================
     PEDIDOS: o botão do andamento da tela de Pedidos
     ================================================================== */
  function linhaDePedido(item) {
    var li = criar("li", "ls-res-item ls-res-pedido");
    li.dataset.id = item.id;
    var cabeca = criar("div", "ls-res-cabeca");
    cabeca.appendChild(criar("span", "ls-res-numero", "#" + item.id));
    var nome = criar("div", "ls-res-nome");
    nome.appendChild(criar("strong", "", item.cliente));
    nome.appendChild(criar("small", "", [item.total, item.itens].filter(Boolean).join(" · ")));
    cabeca.appendChild(nome);
    li.appendChild(cabeca);

    var meta = criar("p", "ls-res-meta");
    [["bi-calendar", item.criado ? "Feito em " + item.criado : ""],
     ["bi-truck", item.entrega], ["bi-geo-alt", item.cidade]].forEach(function (par) {
      if (!par[1]) return;
      var pedaco = criar("span");
      pedaco.appendChild(icone(par[0]));
      pedaco.appendChild(criar("span", "", par[1]));
      meta.appendChild(pedaco);
    });
    li.appendChild(meta);

    var barra = criar("div", "ls-res-acoes");
    var andamento = item.andamento || {};
    if ((andamento.opcoes || []).length) {
      var b = criar("button", "ls-andamento-botao");
      b.type = "button";
      b.dataset.andamentoUrl = andamento.url;
      b.dataset.andamentoOpcoes = JSON.stringify(andamento.opcoes);
      b.dataset.andamentoTitulo = andamento.titulo;
      b.dataset.andamentoRotulo = item.situacao;
      b.dataset.envioTransportadora = andamento.transportadora || "";
      b.dataset.envioCodigo = andamento.codigo || "";
      b.dataset.envioLink = andamento.link || "";
      b.setAttribute("aria-haspopup", "dialog");
      b.title = "Mudar o andamento do pedido";
      b.textContent = item.situacao;
      barra.appendChild(b);
    } else {
      barra.appendChild(criar("span", "ls-res-estado", item.situacao));
    }
    li.appendChild(barra);
    return li;
  }

  /* ==================================================================
     ESTOQUE: o que comprar
     ================================================================== */
  function linhaDeEstoque(item) {
    var li = criar("li", "ls-res-item ls-res-estoque" + (item.zerado ? " zerado" : ""));
    var cabeca = criar("div", "ls-res-cabeca");
    var nome = criar("div", "ls-res-nome");
    nome.appendChild(criar("strong", "", item.material));
    nome.appendChild(criar("small", "", [item.codigo, item.local, item.fornecedor].filter(Boolean).join(" · ")));
    cabeca.appendChild(nome);
    var saldo = criar("span", "ls-res-saldo");
    saldo.appendChild(criar("strong", "", String(item.quantidade)));
    saldo.appendChild(criar("small", "", "mínimo " + item.minimo + (item.unidade ? " " + item.unidade : "")));
    cabeca.appendChild(saldo);
    li.appendChild(cabeca);
    var barra = criar("span", "ls-res-barra");
    barra.setAttribute("aria-hidden", "true");
    var cheio = criar("span");
    var parte = item.minimo > 0 ? Math.max(0, Math.min(1, item.quantidade / item.minimo)) : 0;
    cheio.style.width = Math.round(parte * 100) + "%";
    barra.appendChild(cheio);
    li.appendChild(barra);
    return li;
  }

  /* ==================================================================
     O TOQUE NO AVISO
     Captura no documento: chega antes da navegação suave (que olha
     `defaultPrevented`) e vale para o item do sino e o do Início, que
     é redesenhado a cada estado novo. Toque com Ctrl/meio continua
     abrindo a tela numa aba nova -- o `href` do aviso é a tela.
     ================================================================== */
  document.addEventListener("click", function (evento) {
    var alvo = evento.target && evento.target.closest ? evento.target.closest("[data-resolver]") : null;
    if (!alvo) return;
    if (evento.defaultPrevented || evento.button !== 0) return;
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
    if (!enderecoDaFolha(alvo.getAttribute("data-resolver"))) return;
    evento.preventDefault();
    var titulo = alvo.querySelector(".ls-aviso-titulo");
    var marca = alvo.querySelector(".ls-aviso-icone .bi");
    abrir(alvo.getAttribute("data-resolver"), {
      url: alvo.getAttribute("href") || "",
      titulo: titulo ? titulo.firstChild && titulo.firstChild.textContent : "",
      icone: marca ? Array.prototype.filter.call(marca.classList, function (c) { return c.indexOf("bi-") === 0; })[0] : ""
    });
  }, true);

  window.LSResolverAvisos = {
    abrir: abrir,
    fechar: function () { fecharAberta(false); },
    aberta: function () { return aberta ? aberta.chave : null; },
    conferirDocumento: conferirDocumento
  };
})(window, document);
