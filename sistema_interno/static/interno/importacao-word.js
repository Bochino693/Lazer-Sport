/* ======================================================================
   CONFERÊNCIA DA IMPORTAÇÃO (WORD OU PDF)

   O QUE ESTE ARQUIVO FAZ. Liga a tela de conferência: a escolha entre
   "Cadastrar cliente e criar orçamento" e "Só cadastrar o cliente", a
   busca de produto em cada item (a mesma do orçamento), a busca de
   cliente, os botões de leitura e de sugestão, as contas refeitas a cada
   tecla, a lista do que falta e o botão "Criar", que só acende com tudo
   completo.

   AS REGRAS SÃO AS DO SERVIDOR (importacao_word/formulario.py), repetidas
   aqui só para a pessoa ver na hora o que falta. Quem decide é o
   servidor: um envio que passasse por aqui com algo faltando volta com a
   mesma lista. Por isso as duas listas têm de dizer a mesma coisa -- e
   quando mudar uma regra lá, mude aqui.

   DINHEIRO EM CENTAVOS INTEIROS (BigInt). Somar 0,1 + 0,2 em ponto
   flutuante dá 0,30000000000000004; numa tela que existe para dizer "a
   conta bate", isso é inaceitável.
   ====================================================================== */
LSTela.pronto(function () {
  "use strict";

  var form = document.getElementById("formConferencia");
  if (!form) return;
  var dados = JSON.parse(document.getElementById("dadosConferencia").textContent || "{}");
  var lista = document.getElementById("listaItens");
  var ordem = document.getElementById("itensOrdem");
  var botaoCriar = document.getElementById("criarOrcamento");
  var buscas = {};
  var novos = 0;

  /* -------------------------------------------------------- números */
  /* A mesma leitura do servidor (deterministica.ler_dinheiro) e do campo
     de reais do painel (`moeda-valor`): "18000" e "18.000" são dezoito
     mil; "1234,5" é mil duzentos e trinta e quatro e cinquenta; "18.5" é
     dezoito e cinquenta; "R$ 1.234,56" colado de planilha também vale.
     A vírgula ou o ponto no fim ("18,") é digitação pela metade. */
  function centavos(texto) {
    var bruto = String(texto || "").replace(/R\$|\s/g, "").replace(/[.,]$/, "");
    if (!bruto) return null;
    var m;
    function junta(inteiros, casas) { return BigInt(inteiros + (casas + "00").slice(0, 2)); }
    if ((m = bruto.match(/^(\d{1,3}(?:\.\d{3})+|\d+),(\d{1,2})$/))) return junta(m[1].replace(/\./g, ""), m[2]);
    if (/^\d{1,3}(?:\.\d{3})+$/.test(bruto)) return BigInt(bruto.replace(/\./g, "") + "00");
    if (/^\d+$/.test(bruto)) return BigInt(bruto + "00");
    if ((m = bruto.match(/^(\d+)\.(\d{1,2})$/))) return junta(m[1], m[2]);
    if ((m = bruto.match(/^(\d{1,3}(?:,\d{3})+)\.(\d{1,2})$/))) return junta(m[1].replace(/,/g, ""), m[2]);
    return null;
  }

  function moeda(valor) {
    if (valor === null || valor === undefined) return "—";
    var negativo = valor < 0n;
    var absoluto = negativo ? -valor : valor;
    var texto = absoluto.toString().padStart(3, "0");
    var inteiros = texto.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (negativo ? "− " : "") + "R$ " + inteiros + "," + texto.slice(-2);
  }

  function quantidade(texto) {
    var bruto = String(texto || "").trim();
    if (!/^\d+$/.test(bruto)) return null;
    var numero = parseInt(bruto, 10);
    return numero >= 1 && numero <= 100000 ? numero : null;
  }

  /* -------------------------------------------- CPF, CNPJ, telefone */
  function digitoModulo11(valores, pesos) {
    var soma = 0;
    for (var i = 0; i < valores.length; i++) soma += valores[i] * pesos[i];
    var resto = soma % 11;
    return resto < 2 ? 0 : 11 - resto;
  }

  function documentoValido(texto) {
    var chave = String(texto || "").toUpperCase().replace(/[^0-9A-Z]/g, "");
    if (chave.length === 11 && /^\d+$/.test(chave)) {
      if (/^(\d)\1+$/.test(chave)) return false;
      var base = chave.slice(0, 9).split("").map(Number);
      var d1 = digitoModulo11(base, [10, 9, 8, 7, 6, 5, 4, 3, 2]);
      var d2 = digitoModulo11(base.concat(d1), [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]);
      return chave.slice(-2) === "" + d1 + d2;
    }
    if (chave.length === 14 && /^[0-9A-Z]{12}\d{2}$/.test(chave)) {
      if (/^(.)\1+$/.test(chave)) return false;
      var valores = chave.slice(0, 12).split("").map(function (c) { return c.charCodeAt(0) - 48; });
      var p1 = digitoModulo11(valores, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
      var p2 = digitoModulo11(valores.concat(p1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
      return chave.slice(-2) === "" + p1 + p2;
    }
    return false;
  }

  function telefoneValido(texto) {
    var numero = String(texto || "").replace(/\D/g, "");
    if (numero.indexOf("55") === 0 && (numero.length === 12 || numero.length === 13)) numero = numero.slice(2);
    return (numero.length === 10 || numero.length === 11) && numero.slice(0, 2) !== "00";
  }

  function emailValido(texto) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(texto || "").trim());
  }

  function valorDe(id) {
    var campo = document.getElementById(id);
    return campo ? String(campo.value || "").trim() : "";
  }

  function marcado(seletor) {
    var campo = form.querySelector(seletor);
    return !!(campo && campo.checked);
  }

  /* --------------------------------------------------------- fonte */
  /* O toque na fonte abre o documento lido na linha citada, para conferir
     com os próprios olhos o que está escrito lá. */
  document.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-fonte]");
    if (!botao) return;
    var linha = document.getElementById("linha-" + botao.dataset.fonte);
    var painel = document.getElementById("documentoLido");
    if (!linha || !painel) return;
    painel.open = true;
    linha.scrollIntoView({ block: "center", behavior: "smooth" });
    linha.classList.add("destaque");
    window.setTimeout(function () { linha.classList.remove("destaque"); }, 2600);
  });

  /* ---------------------------------------------- opção e sugestão */
  /* Nada se preenche sozinho: as leituras e as sugestões são botões. */
  form.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-preencher]");
    if (!botao) return;
    var alvo = document.getElementById(botao.dataset.preencher);
    if (!alvo) return;
    if (window.Painel && Painel.valor) Painel.valor(alvo.id, botao.dataset.valor);
    else alvo.value = botao.dataset.valor;
    alvo.dispatchEvent(new Event("input", { bubbles: true }));
    alvo.dispatchEvent(new Event("change", { bubbles: true }));
  });

  /* ------------------------------------- orçamento, ou só o cliente */
  var caminho = (form.querySelector('[name="modo"]:checked') || {}).value || "orcamento";
  function aplicarCaminho() {
    caminho = (form.querySelector('[name="modo"]:checked') || {}).value || "orcamento";
    /* As partes do orçamento SOMEM no "só o cliente", mas não perdem o
       que já foi conferido: quem volta para "criar orçamento" acha tudo
       como deixou. O servidor ignora esses campos no "só o cliente". */
    form.querySelectorAll("[data-so-orcamento]").forEach(function (parte) {
      parte.hidden = caminho !== "orcamento";
    });
    document.querySelectorAll("[data-nota-modo], [data-rotulo-modo]").forEach(function (el) {
      el.hidden = (el.dataset.notaModo || el.dataset.rotuloModo) !== caminho;
    });
    atualizar();
  }
  form.querySelectorAll('[name="modo"]').forEach(function (radio) {
    radio.addEventListener("change", aplicarCaminho);
  });

  /* ----------------------------------------------------- cliente */
  var modoAtual = (form.querySelector('[name="cliente_modo"]:checked') || {}).value || "novo";
  var clienteEscolhido = dados.cliente.opcao || null;
  function aplicarModo() {
    var anterior = modoAtual;
    modoAtual = (form.querySelector('[name="cliente_modo"]:checked') || {}).value || "novo";
    /* "Cadastrar novo" depois de olhar o cadastro: o nome volta a ser o
       do documento, e não o do cliente que estava escolhido. */
    if (anterior === "existente" && modoAtual === "novo" && clienteEscolhido
        && valorDe("campoNome") === clienteEscolhido.rotulo && dados.nomeDocumento) {
      document.getElementById("campoNome").value = dados.nomeDocumento;
    }
    form.querySelectorAll("[data-modo]").forEach(function (secao) {
      var ativa = secao.dataset.modo === modoAtual;
      secao.hidden = !ativa;
      /* Campo escondido não viaja no envio: o CPF digitado no cadastro
         novo não pode ir junto quando a escolha é o cliente cadastrado. */
      secao.querySelectorAll("input, select, textarea").forEach(function (campo) {
        if (campo.id === "clienteId") return;
        campo.disabled = !ativa;
      });
    });
    atualizar();
  }
  form.querySelectorAll('[name="cliente_modo"]').forEach(function (radio) {
    radio.addEventListener("change", aplicarModo);
  });

  var campoClienteId = document.getElementById("clienteId");
  function preencherContatoDoCadastro(opcao) {
    clienteEscolhido = opcao || null;
    if (!opcao) return;
    /* Escolha explícita na busca: o nome é o do cadastro, e o que estiver
       vazio aqui passa a ser o do cadastro -- como no formulário normal
       de orçamento. */
    if (opcao.rotulo) document.getElementById("campoNome").value = opcao.rotulo;
    if (!valorDe("campoDocumento") && opcao.documento) Painel.valor("campoDocumento", opcao.documento);
    if (!valorDe("campoTelefone") && (opcao.telefone || opcao.whatsapp)) {
      Painel.valor("campoTelefone", opcao.whatsapp || opcao.telefone);
      if (opcao.whatsapp) definirWhatsapp("sim", "Confirmado no cadastro do cliente.");
    }
    if (!valorDe("campoEmail") && opcao.email) Painel.valor("campoEmail", opcao.email);
  }

  /* TEM WHATSAPP? Vem respondido, e a pessoa só troca se precisar:
     celular de nove dígitos é sim, fixo é não. Enquanto ninguém mexeu na
     resposta, trocar o número refaz a sugestão. */
  var campoWhatsapp = document.getElementById("campoWhatsapp");
  var whatsappEscolhido = false;
  function definirWhatsapp(valor, nota) {
    campoWhatsapp.value = valor;
    var aviso = document.getElementById("notaWhatsapp");
    if (aviso) aviso.textContent = nota || "";
  }
  campoWhatsapp.addEventListener("change", function () {
    whatsappEscolhido = true;
    var aviso = document.getElementById("notaWhatsapp");
    if (aviso) aviso.textContent = "";
  });
  document.getElementById("campoTelefone").addEventListener("input", function () {
    if (whatsappEscolhido) return;
    var numero = valorDe("campoTelefone").replace(/\D/g, "");
    if (numero.indexOf("55") === 0 && numero.length > 11) numero = numero.slice(2);
    if (numero.length < 10) return;
    var celular = numero.length === 11 && numero.charAt(2) === "9";
    definirWhatsapp(celular ? "sim" : "nao",
      celular ? "Celular: em geral tem WhatsApp. Troque se não tiver." : "Telefone fixo. Troque se tiver WhatsApp.");
  });

  var caixaCliente = document.getElementById("clienteBuscaBox");
  var buscaCliente = null;
  if (caixaCliente && window.LSBusca) {
    buscaCliente = LSBusca.criar({
      opcoes: [],
      placeholder: "Buscar cliente cadastrado...",
      rotuloAcessivel: "Cliente cadastrado",
      minimoBusca: 2,
      carregar: function (termo) {
        return fetch(dados.buscaClientes + "?q=" + encodeURIComponent(termo || ""), {
          credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }
        }).then(function (r) { return r.json(); }).then(function (json) { return json.opcoes || []; });
      },
      aoEscolher: function (opcao) {
        campoClienteId.value = opcao ? opcao.valor : "";
        var confirmar = document.getElementById("clienteConfirmarBox");
        if (confirmar) confirmar.hidden = !(opcao && opcao.valor === dados.cliente.id && dados.cliente.confianca !== "alta");
        preencherContatoDoCadastro(opcao);
        atualizar();
      }
    });
    buscaCliente.entrada.id = "clienteBusca";
    caixaCliente.appendChild(buscaCliente.elemento);
    if (dados.cliente.opcao) {
      buscaCliente.adicionarOpcao(dados.cliente.opcao, false);
      if (campoClienteId.value) buscaCliente.definirValor(campoClienteId.value, false);
    }
  }
  form.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-cliente]");
    if (!botao || !buscaCliente) return;
    var radio = form.querySelector('[name="cliente_modo"][value="existente"]');
    radio.checked = true;
    aplicarModo();
    fetch(dados.buscaClientes + "?q=" + encodeURIComponent(botao.textContent.trim().split("\n")[0]), {
      credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }
    }).then(function (r) { return r.json(); }).then(function (json) {
      var opcao = (json.opcoes || []).filter(function (o) { return String(o.valor) === botao.dataset.cliente; })[0];
      if (opcao) {
        buscaCliente.adicionarOpcao(opcao, false);
        buscaCliente.definirValor(opcao.valor, true);
      }
    });
  });

  /* ------------------------------------------------------- itens */
  function buscarItens(termo) {
    return fetch(dados.buscaItens + "?q=" + encodeURIComponent(termo || ""), {
      credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }
    }).then(function (r) { return r.json(); }).then(function (json) {
      if (!json || json.status !== "sucesso") throw new Error("Não foi possível buscar os itens.");
      return json.opcoes || [];
    });
  }

  function infoDoItem(uid) {
    return (dados.itens || {})[uid] || { totalWord: "", sugerido: "", confianca: "baixa", opcao: null };
  }

  function ligarItem(cartao) {
    var uid = cartao.dataset.uid;
    var caixa = cartao.querySelector("[data-busca-item]");
    var guardado = document.getElementById("item-" + uid + "-produto");
    var descricao = document.getElementById("item-" + uid + "-descricao");
    var avulsa = cartao.querySelector("[data-avulsa]");
    var conferir = cartao.querySelector("[data-conferir-de]");
    var info = infoDoItem(uid);
    var nomeAnterior = info.opcao ? info.opcao.rotulo : "";

    var busca = LSBusca.criar({
      opcoes: [],
      placeholder: "Buscar brinquedo, peça ou produto...",
      rotuloAcessivel: "Produto do catálogo do item",
      classe: "ls-busca-item-orcamento",
      exibirImagem: true,
      minimoBusca: 2,
      carregar: buscarItens,
      aoEscolher: function (opcao) {
        guardado.value = opcao ? opcao.valor : "";
        if (opcao) {
          avulsa.checked = false;
          /* Uniformidade: a linha leva o nome do catálogo. Só não troca o
             que a pessoa já reescreveu à mão. */
          var atual = descricao.value.trim();
          if (!atual || atual === descricao.dataset.original || atual === nomeAnterior) {
            descricao.value = opcao.rotulo;
          }
          nomeAnterior = opcao.rotulo;
          mostrarPrecoDoCatalogo(cartao, uid, opcao);
        }
        if (conferir) {
          conferir.hidden = !(opcao && opcao.valor === info.sugerido && info.confianca === "media");
        }
        atualizar();
      }
    });
    busca.entrada.id = "item-" + uid + "-busca";
    caixa.appendChild(busca.elemento);
    if (info.opcao) busca.adicionarOpcao(info.opcao, false);
    if (guardado.value) busca.definirValor(guardado.value, false);
    buscas[uid] = busca;

    avulsa.addEventListener("change", function () {
      if (avulsa.checked) {
        busca.definirValor("", false);
        guardado.value = "";
        if (conferir) conferir.hidden = true;
      }
      atualizar();
    });

    cartao.querySelectorAll("[data-candidato]").forEach(function (botao) {
      botao.addEventListener("click", function () {
        buscarItens(botao.dataset.rotulo).then(function (opcoes) {
          var opcao = opcoes.filter(function (o) { return o.valor === botao.dataset.valor; })[0];
          if (!opcao) {
            opcao = { valor: botao.dataset.valor, rotulo: botao.dataset.rotulo, grupo: "", detalhe: "",
                      preco: botao.dataset.preco || "" };
          }
          busca.adicionarOpcao(opcao, false);
          busca.definirValor(opcao.valor, true);
        });
      });
    });

    if (window.Painel && Painel.aplicarMascaras) Painel.aplicarMascaras(cartao);
  }

  /* Preço do catálogo é sugestão, nunca valor escrito por cima do Word. */
  function mostrarPrecoDoCatalogo(cartao, uid, opcao) {
    var antiga = cartao.querySelector("[data-preco-catalogo]");
    if (antiga) antiga.remove();
    if (!opcao || !opcao.preco) return;
    var campo = document.getElementById("item-" + uid + "-valor_unitario");
    if (!campo || centavos(campo.value) === centavos(opcao.preco)) return;
    var linha = document.createElement("div");
    linha.className = "ls-imp-sugestao";
    linha.setAttribute("data-preco-catalogo", "1");
    var botao = document.createElement("button");
    botao.type = "button";
    botao.className = "ls-chip";
    botao.dataset.preencher = campo.id;
    botao.dataset.valor = opcao.preco;
    botao.innerHTML = '<i class="bi bi-tag" aria-hidden="true"></i> ';
    botao.appendChild(document.createTextNode("Preço do catálogo: R$ " + opcao.preco));
    var nota = document.createElement("small");
    nota.textContent = campo.value ? "o documento diz outro valor; confira antes de trocar" : "o documento não traz o unitário";
    linha.appendChild(botao);
    linha.appendChild(nota);
    campo.closest(".ls-imp-campo").appendChild(linha);
  }

  function cartoes() {
    return Array.prototype.slice.call(lista.querySelectorAll(".ls-imp-item"));
  }

  function renumerar() {
    var uids = [];
    cartoes().forEach(function (cartao, indice) {
      uids.push(cartao.dataset.uid);
      cartao.querySelectorAll("[data-posicao]").forEach(function (el) { el.textContent = indice + 1; });
    });
    ordem.value = uids.join(",");
  }

  document.getElementById("acrescentarItem").addEventListener("click", function () {
    novos += 1;
    var uid = "n" + novos;
    var modelo = document.getElementById("modeloItem").innerHTML
      .replace(/__uid__/g, uid).replace(/__posicao__/g, String(cartoes().length + 1));
    var caixa = document.createElement("div");
    caixa.innerHTML = modelo.trim();
    var cartao = caixa.firstElementChild;
    lista.appendChild(cartao);
    ligarItem(cartao);
    renumerar();
    atualizar();
    var primeiro = document.getElementById("item-" + uid + "-busca");
    if (primeiro) primeiro.focus();
  });

  lista.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-remover]");
    if (!botao) return;
    var cartao = botao.closest(".ls-imp-item");
    if (buscas[cartao.dataset.uid]) buscas[cartao.dataset.uid].destruir();
    delete buscas[cartao.dataset.uid];
    cartao.remove();
    renumerar();
    atualizar();
  });

  cartoes().forEach(ligarItem);

  /* ---------------------------------------------------- alertas */
  form.querySelectorAll("[data-aceite]").forEach(function (caixa) {
    caixa.addEventListener("change", function () {
      var texto = form.querySelector('[data-justificativa="' + caixa.dataset.aceite + '"]');
      if (texto) {
        texto.hidden = !caixa.checked;
        if (caixa.checked) texto.focus();
      }
      atualizar();
    });
  });

  function campoDoAlerta(chave) {
    /* "valores.frete" -> campoFrete; "itens.i2.valor_unitario" -> item-i2-valor_unitario */
    var mapa = {
      "valores.frete": "campoFrete", "valores.desconto": "campoDesconto",
      "condicoes.validade": "campoValidade", "cliente.documento": "campoDocumento",
      "cliente.telefone": "campoTelefone", "cliente.email": "campoEmail"
    };
    if (mapa[chave]) return document.getElementById(mapa[chave]);
    var partes = chave.split(".");
    if (partes[0] === "itens" && partes.length === 3) {
      return document.getElementById("item-" + partes[1] + "-" + partes[2]);
    }
    return null;
  }

  /* --------------------------------------------------- a conta */
  function contas() {
    var subtotal = 0n;
    var completos = true;
    var linhas = {};
    cartoes().forEach(function (cartao) {
      var uid = cartao.dataset.uid;
      var qtd = quantidade(valorDe("item-" + uid + "-quantidade"));
      var unit = centavos(valorDe("item-" + uid + "-valor_unitario"));
      var total = qtd !== null && unit !== null ? unit * BigInt(qtd) : null;
      linhas[uid] = { qtd: qtd, unit: unit, total: total };
      if (total === null) completos = false;
      else subtotal += total;
    });
    var frete = centavos(valorDe("campoFrete"));
    var desconto = centavos(valorDe("campoDesconto"));
    var total = subtotal + (frete || 0n) - (desconto || 0n);
    if (total < 0n) total = 0n;
    /* Com o valor final combinado, o total é o do documento e o desconto
       digitado não entra (o servidor grava zero). */
    var valorFinal = escolhaDoTotal() === "valor_final" ? centavos(dados.valorFinal) : null;
    return { linhas: linhas, subtotal: subtotal, frete: frete, desconto: desconto, total: total,
             completos: completos, valorFinal: valorFinal,
             final: valorFinal !== null ? valorFinal : total };
  }

  function escolhaDoTotal() {
    var marcada = form.querySelector('[name="total_escolha"]:checked');
    return marcada ? marcada.value : "";
  }

  function desenharContas(conta) {
    cartoes().forEach(function (cartao) {
      var uid = cartao.dataset.uid;
      var linha = conta.linhas[uid];
      var alvo = cartao.querySelector("[data-subtotal-de]");
      if (alvo) alvo.textContent = linha.total === null ? "—" : moeda(linha.total);
      var estado = cartao.querySelector("[data-conta-de]");
      var word = centavos(infoDoItem(uid).totalWord);
      if (!estado) return;
      if (word === null || linha.total === null) { estado.hidden = true; return; }
      var bate = linha.total === word;
      estado.hidden = false;
      estado.className = "ls-imp-conta-estado " + (bate ? "bate" : "nao-bate");
      estado.textContent = bate ? "Confere com o documento." : "Não bate com o documento (" + moeda(word) + ").";
    });
    document.getElementById("contaSubtotal").textContent = moeda(conta.subtotal);
    document.getElementById("contaFrete").textContent = moeda(conta.frete || 0n);
    document.getElementById("contaDesconto").textContent = moeda(conta.desconto || 0n);
    document.getElementById("contaTotal").textContent = moeda(conta.final);
    document.getElementById("contaTotalLateral").textContent = moeda(conta.final);
    var fixo = document.getElementById("totalFixo");
    if (!fixo) {
      fixo = document.createElement("small");
      fixo.id = "totalFixo";
      fixo.className = "ls-imp-fixo";
      document.getElementById("contaTotal").insertAdjacentElement("afterend", fixo);
    }
    fixo.hidden = conta.valorFinal === null;
    fixo.textContent = conta.valorFinal === null ? "" : "Valor final combinado (a soma dá " + moeda(conta.total) + ").";

    /* A escolha entre a soma e o total do documento só aparece quando os
       dois diferem -- e some (desmarcada) quando a pessoa acerta a conta. */
    /* O valor negociado ESCRITO no documento fica sempre à vista (é uma
       informação do documento, e não um erro de conta). */
    var escolha = document.getElementById("escolhaTotal");
    var word = centavos(dados.totalWord);
    var diferem = word !== null && conta.total !== word;
    if (escolha) {
      escolha.hidden = !(dados.valorFinalExplicito || diferem);
      if (escolha.hidden) {
        form.querySelectorAll('[name="total_escolha"]').forEach(function (r) { r.checked = false; });
      }
      var soma = document.getElementById("valorFinalSoma");
      if (soma) soma.textContent = moeda(conta.total);
      var justificativa = document.getElementById("justificativaSoma");
      if (justificativa) justificativa.hidden = !(escolhaDoTotal() === "soma" && (diferem || dados.valorFinalExplicito));
    }
  }

  /* O alerta vermelho está resolvido com o que está na tela agora? */
  function alertaResolvido(alerta, conta) {
    var tipo = alerta.dataset.tipo;
    var id = alerta.dataset.alerta;
    if (tipo === "linha") {
      var uid = id.split(":")[1];
      var linha = conta.linhas[uid];
      var word = centavos(infoDoItem(uid).totalWord);
      return !linha || (linha.total !== null && word !== null && linha.total === word);
    }
    if (tipo === "soma_subtotal") {
      var sub = centavos(dados.subtotalWord);
      return conta.completos && sub !== null && conta.subtotal === sub;
    }
    if (tipo === "soma_total") {
      var tot = centavos(dados.totalWord);
      /* O total escrito vira o valor final. (O negociado com rótulo
         próprio não apaga um total que não bate: esse pede a conta.) */
      if (escolhaDoTotal() === "valor_final" && tot !== null && !dados.valorFinalExplicito) return true;
      return conta.completos && tot !== null && conta.total === tot;
    }
    if (tipo === "documento_invalido") {
      return modoAtual === "existente" || !valorDe("campoDocumento") || documentoValido(valorDe("campoDocumento"));
    }
    if (tipo === "cliente_conflito") {
      return modoAtual !== dados.cliente.modo || (campoClienteId.value || "") !== (dados.cliente.id || "");
    }
    if (tipo === "divergencia" && !alerta.dataset.referencia) {
      var partes = alerta.dataset.campo.split(".");
      if (partes[0] === "itens" && !document.getElementById("item-" + partes[1])) return true;
      var campo = campoDoAlerta(alerta.dataset.campo);
      return !!(campo && String(campo.value || "").trim());
    }
    if (tipo === "divergencia" && alerta.dataset.campo.indexOf("itens.") === 0) {
      return !document.getElementById("item-" + alerta.dataset.campo.split(".")[1]);
    }
    return false;
  }

  /* --------------------------------------------- o que falta */
  /* AS MESMAS REGRAS DE formulario.validar. O que bloqueia é o que
     protege o dinheiro e o produto (e o cadastro do cliente); WhatsApp,
     forma de pagamento, de envio e prazo não seguram o "Criar". */
  function pendencias(conta) {
    var lista_ = [];
    function falta(alvo, rotulo, motivo) { lista_.push({ alvo: alvo, rotulo: rotulo, motivo: motivo }); }

    if (modoAtual === "existente") {
      if (!campoClienteId.value) falta("clienteBusca", "Cliente", "escolha o cliente cadastrado na busca (ou cadastre um novo)");
      else if (campoClienteId.value === dados.cliente.id && dados.cliente.confianca !== "alta"
               && !marcado("#clienteConfirmado")) {
        falta("clienteConfirmado", "Cliente", "confirme que é o cliente do documento");
      }
    }
    if (!valorDe("campoNome")) falta("campoNome", "Nome do cliente", "escreva o nome do cliente");
    if (valorDe("campoDocumento") && !documentoValido(valorDe("campoDocumento"))) {
      falta("campoDocumento", "CPF/CNPJ", "documento inválido: corrija pelo documento do cliente ou apague");
    }
    var algumEndereco = ["campoCep", "campoEndereco", "campoNumero", "campoComplemento", "campoBairro", "campoCidade", "campoEstado"]
      .some(function (id) { return !!valorDe(id); });
    if (algumEndereco && !(valorDe("campoEndereco") && valorDe("campoCidade"))) {
      falta("campoEndereco", "Endereço", "para guardar o endereço, informe pelo menos a rua e a cidade");
    }
    var telefone = valorDe("campoTelefone");
    var telefoneOk = !!telefone && telefoneValido(telefone);
    if (telefone && !telefoneOk) falta("campoTelefone", "Telefone/WhatsApp", "telefone incompleto: informe DDD e número");
    var email = valorDe("campoEmail");
    var emailOk = !!email && emailValido(email);
    if (email && !emailOk) falta("campoEmail", "E-mail", "e-mail inválido");
    var cadastroTemContato = modoAtual === "existente" && clienteEscolhido
      && String(clienteEscolhido.valor) === String(campoClienteId.value)
      && !!(clienteEscolhido.telefone || clienteEscolhido.email);
    if (!telefone && !email && !cadastroTemContato) {
      falta("campoTelefone", "Telefone ou e-mail", "informe ao menos um contato: telefone/WhatsApp ou e-mail");
    }
    if (caminho === "cliente") return lista_;

    var itens = cartoes();
    if (!itens.length) falta("acrescentarItem", "Itens", "o orçamento precisa de pelo menos um item (ou escolha “Só cadastrar o cliente”)");
    itens.forEach(function (cartao, indice) {
      var uid = cartao.dataset.uid;
      var rotulo = "Item " + (indice + 1);
      var info = infoDoItem(uid);
      var produto = valorDe("item-" + uid + "-produto");
      var avulsa = marcado('[name="item-' + uid + '-avulsa"]');
      if (!valorDe("item-" + uid + "-descricao")) falta("item-" + uid + "-descricao", rotulo, "escreva a descrição");
      if (!avulsa && !produto) falta("item-" + uid + "-busca", rotulo, "escolha o produto do catálogo ou marque “linha avulsa”");
      else if (!avulsa && produto === info.sugerido && info.confianca === "media"
               && !marcado('[name="item-' + uid + '-conferido"]')) {
        falta("item-" + uid + "-busca", rotulo, "confirme o produto sugerido ou escolha outro");
      }
      var linha = conta.linhas[uid];
      if (linha.qtd === null) falta("item-" + uid + "-quantidade", rotulo, "informe a quantidade (número inteiro maior que zero)");
      if (linha.unit === null) falta("item-" + uid + "-valor_unitario", rotulo, "informe o valor unitário");
    });

    if (!valorDe("campoFrete")) falta("campoFrete", "Frete", "informe o frete; se não houver, use “Sem frete (R$ 0,00)”");
    else if (conta.frete === null) falta("campoFrete", "Frete", "valor do frete ilegível");
    if (valorDe("campoDesconto") && conta.desconto === null) falta("campoDesconto", "Desconto", "valor do desconto ilegível");
    if (dados.descontoExigido && !valorDe("campoDesconto") && conta.valorFinal === null) {
      falta("campoDesconto", "Desconto", "o documento dá desconto em porcentagem: confirme o valor em reais");
    }
    if (conta.valorFinal === null && conta.desconto !== null && conta.desconto > conta.subtotal + (conta.frete || 0n)) {
      falta("campoDesconto", "Desconto", "o desconto é maior que o total");
    }
    var totalWord = centavos(dados.totalWord);
    if (document.getElementById("escolhaTotal") && totalWord !== null && conta.total !== totalWord) {
      var escolhida = escolhaDoTotal();
      var textoSoma = valorDe("justificativaSoma");
      if (!escolhida) {
        falta("escolhaTotal", "Qual total vale?", "o documento diz " + moeda(totalWord) + " e a soma dá " + moeda(conta.total) + ": escolha");
      } else if (escolhida === "soma" && textoSoma.length < dados.justificativaMinima) {
        falta("justificativaSoma", "Qual total vale?", "escreva por que fica a soma (pelo menos " + dados.justificativaMinima + " letras)");
      }
    }
    if (dados.valorFinalExplicito && escolhaDoTotal() === "soma" && !(totalWord !== null && conta.total !== totalWord)
        && valorDe("justificativaSoma").length < dados.justificativaMinima) {
      falta("justificativaSoma", "Qual total vale?",
            "escreva por que fica a soma das linhas, e não o valor negociado (pelo menos " + dados.justificativaMinima + " letras)");
    }
    var validade = valorDe("campoValidade");
    var notaValidade = document.getElementById("notaValidade");
    if (notaValidade) notaValidade.hidden = !!validade;
    if (validade && validade < dados.hoje) falta("campoValidade", "Validade", "a validade não pode ser anterior a hoje");

    form.querySelectorAll(".ls-imp-alerta.vermelho").forEach(function (alerta) {
      var resolvido = alertaResolvido(alerta, conta);
      alerta.classList.toggle("resolvido", resolvido);
      var aviso = alerta.querySelector(".ls-imp-alerta-resolvido");
      if (aviso) aviso.hidden = !resolvido;
      var aceite = alerta.querySelector(".ls-imp-aceite");
      if (aceite) aceite.hidden = resolvido;
      if (resolvido) return;
      var id = alerta.dataset.alerta;
      /* O total que não bate se resolve no quadro "Qual total vale?" --
         menos quando o valor escolhido é o negociado escrito à parte: aí
         o total errado continua pedindo conta ou justificativa. */
      if (id === "soma_total" && document.getElementById("escolhaTotal")
          && !(dados.valorFinalExplicito && escolhaDoTotal() === "valor_final")) return;
      var caixa = form.querySelector('[data-aceite="' + id + '"]');
      var texto = form.querySelector('[data-justificativa="' + id + '"]');
      var titulo = (alerta.querySelector("strong") || {}).textContent || "Alerta";
      if (!caixa || !caixa.checked) falta(caixa ? caixa.id || "" : "", titulo, "corrija o valor ou aceite com uma justificativa");
      else if (!texto || texto.value.trim().length < dados.justificativaMinima) {
        falta("", titulo, "escreva por que o alerta pode ser aceito (pelo menos " + dados.justificativaMinima + " letras)");
      }
    });
    return lista_;
  }

  function desenharPendencias(lista_) {
    var ol = document.getElementById("listaPendencias");
    ol.innerHTML = "";
    lista_.forEach(function (p) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + (p.alvo || "blocoAlertas");
      a.dataset.alvo = p.alvo || "";
      var forte = document.createElement("strong");
      forte.textContent = p.rotulo;
      a.appendChild(forte);
      a.appendChild(document.createTextNode(" — " + p.motivo));
      li.appendChild(a);
      ol.appendChild(li);
    });
    var contagem = document.getElementById("contagemPendencias");
    contagem.textContent = String(lista_.length);
    contagem.classList.toggle("zero", !lista_.length);
    document.getElementById("semPendencias").hidden = !!lista_.length;
    botaoCriar.disabled = !!lista_.length;
    var falta = document.getElementById("criarFalta");
    if (falta) {
      falta.hidden = !lista_.length;
      falta.querySelector("span").textContent = String(lista_.length);
    }
  }

  document.getElementById("listaPendencias").addEventListener("click", function (evento) {
    var link = evento.target.closest("a[data-alvo]");
    if (!link) return;
    var alvo = link.dataset.alvo ? document.getElementById(link.dataset.alvo) : null;
    if (!alvo) {
      evento.preventDefault();
      document.getElementById("blocoAlertas").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    evento.preventDefault();
    alvo.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(function () { try { alvo.focus({ preventScroll: true }); } catch (e) {} }, 350);
  });

  var agendado = null;
  function atualizar() {
    if (agendado) return;
    agendado = window.requestAnimationFrame(function () {
      agendado = null;
      var conta = contas();
      desenharContas(conta);
      desenharPendencias(pendencias(conta));
    });
  }

  form.addEventListener("input", atualizar);
  form.addEventListener("change", atualizar);
  form.addEventListener("submit", function (evento) {
    var lista_ = pendencias(contas());
    if (lista_.length) {
      evento.preventDefault();
      desenharPendencias(lista_);
      document.getElementById("painelPendencias").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    botaoCriar.disabled = true;
    if (window.Painel && Painel.ocupado) {
      Painel.ocupado(caminho === "cliente" ? "Cadastrando o cliente…" : "Criando o cliente e o orçamento…");
    }
  });

  aplicarModo();
  aplicarCaminho();
  renumerar();
});
