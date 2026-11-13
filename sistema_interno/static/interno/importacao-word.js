/* ======================================================================
   CONFERÊNCIA DA IMPORTAÇÃO (WORD OU PDF)

   O QUE ESTE ARQUIVO FAZ. Liga a tela de conferência: a chave "Criar o
   orçamento também" (o padrão é só o cliente), a chave "Aparecer no mapa
   do site", a busca de produto em cada item (a mesma do orçamento), a busca de
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
  var iniciado = false;

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

  /* --------------------------- o cliente primeiro; orçamento é opção */
  /* "Criar o orçamento também" é uma chave: desligada, é só o cliente. */
  var chaveOrcamento = document.getElementById("modoOrcamento");
  var caminho = chaveOrcamento && chaveOrcamento.checked ? "orcamento" : "cliente";
  function aplicarCaminho() {
    caminho = chaveOrcamento && chaveOrcamento.checked ? "orcamento" : "cliente";
    /* As partes do orçamento SOMEM no "só o cliente", mas não perdem o
       que já foi conferido: quem volta para "criar orçamento" acha tudo
       como deixou. O servidor ignora esses campos no "só o cliente". */
    form.querySelectorAll("[data-so-orcamento]").forEach(function (parte) {
      parte.hidden = caminho !== "orcamento";
    });
    document.querySelectorAll("[data-nota-modo], [data-rotulo-modo]").forEach(function (el) {
      el.hidden = (el.dataset.notaModo || el.dataset.rotuloModo) !== caminho;
    });
    if (typeof ajustarPaineis === "function" && iniciado) ajustarPaineis(true);
    atualizar();
  }
  if (chaveOrcamento) chaveOrcamento.addEventListener("change", aplicarCaminho);

  /* OUTRO ENDEREÇO DO DOCUMENTO: um toque troca o endereço inteiro. */
  form.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-endereco-alternativo]");
    if (!botao) return;
    var campos = {
      campoCep: botao.dataset.cep, campoEndereco: botao.dataset.rua, campoNumero: botao.dataset.numero,
      campoComplemento: botao.dataset.complemento, campoBairro: botao.dataset.bairro,
      campoCidade: botao.dataset.cidade, campoEstado: botao.dataset.uf
    };
    Object.keys(campos).forEach(function (id) {
      var campo = document.getElementById(id);
      if (!campo) return;
      if (window.Painel && Painel.valor) Painel.valor(id, campos[id] || "");
      else campo.value = campos[id] || "";
      campo.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });

  /* APARECER NO MAPA: sem endereço não há alfinete. A chave não trava
     nada (o cliente é cadastrado do mesmo jeito); o aviso só diz o que
     vai faltar para o alfinete aparecer. */
  var chaveMapa = document.getElementById("campoMapa");
  function avisarMapa() {
    var aviso = document.getElementById("avisoMapaSemEndereco");
    if (!aviso || !chaveMapa) return;
    var temLugar = !!(valorDe("campoCep") || valorDe("campoCidade"));
    aviso.hidden = !(chaveMapa.checked && !temLugar);
  }
  if (chaveMapa) chaveMapa.addEventListener("change", avisarMapa);
  ["campoCep", "campoCidade"].forEach(function (id) {
    var campo = document.getElementById(id);
    if (campo) campo.addEventListener("input", avisarMapa);
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
      "documento.data": "campoDataDocumento",
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

    /* A data do documento: o primeiro passo do modal. O orçamento guarda
       essa data (e conta dela a validade); o cliente sozinho não a exige. */
    var dataDocumento = valorDe("campoDataDocumento");
    if (dataDocumento && dataDocumento > dados.hoje) {
      falta("campoDataDocumento", "Data do documento", "a data do documento não pode ser depois de hoje");
    } else if (!dataDocumento && caminho !== "cliente") {
      falta("campoDataDocumento", "Data do documento", "diga de quando é o documento: a proposta guarda essa data");
    }
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
    /* O mesmo pedido já lançado para este cliente (o servidor achou). */
    var repetido = document.getElementById("criarMesmoAssim");
    if (repetido && !repetido.checked) {
      falta("criarMesmoAssim", "Orçamento repetido",
            "já existe um orçamento com os mesmos itens: abra o existente ou marque “Criar mesmo assim”");
    }
    var validade = valorDe("campoValidade");
    var notaValidade = document.getElementById("notaValidade");
    if (notaValidade) notaValidade.hidden = !!validade;
    /* Os dias da validade contam da data do documento quando ele é de
       antes de hoje (o contrato de 2016 vale até 2016 + 5 dias). */
    var dataDoc = valorDe("campoDataDocumento");
    var baseValidade = dataDoc && dataDoc < dados.hoje ? dataDoc : dados.hoje;
    if (validade && validade < baseValidade) {
      falta("campoValidade", "Validade", baseValidade < dados.hoje
        ? "a validade não pode ser anterior à data do documento"
        : "a validade não pode ser anterior a hoje");
    }

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
      if (!caixa || !caixa.checked) falta(alerta.id || "", titulo, "corrija o valor ou aceite com uma justificativa");
      else if (!texto || texto.value.trim().length < dados.justificativaMinima) {
        falta(alerta.id || "", titulo, "escreva por que o alerta pode ser aceito (pelo menos " + dados.justificativaMinima + " letras)");
      }
    });
    return lista_;
  }

  /* ------------------------------------------- a tela guiada */
  /* QUANTAS VERIFICAÇÕES HÁ, para o anel do progresso: o cliente (nome e
     um contato, e o vínculo quando é o cadastro que já existe) e, com o
     orçamento, cada item (produto, quantidade, unitário), o frete, a
     escolha do total, o repetido e cada alerta vermelho. */
  function verificacoes() {
    var total = 2 + (modoAtual === "existente" ? 1 : 0);
    if (caminho === "orcamento") {
      total += Math.max(cartoes().length, 1) * 3 + 1;
      if (document.getElementById("escolhaTotal")) total += 1;
      if (document.getElementById("criarMesmoAssim")) total += 1;
      total += form.querySelectorAll(".ls-imp-alerta.vermelho").length;
    }
    return total;
  }

  var reduzirMovimento = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var painelProgresso = document.getElementById("painelPendencias");
  var faltavaAntes = null;

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

    /* "Faltam 2: CPF/CNPJ · Frete", o anel, e -- sem falta nenhuma -- a
       ação verde no lugar, com um pulso só. */
    var total = Math.max(verificacoes(), lista_.length);
    var feito = Math.round(((total - lista_.length) / total) * 100);
    var anel = document.getElementById("anelFeito");
    if (anel) anel.setAttribute("stroke-dasharray", feito + " 100");
    document.getElementById("progressoPorcento").textContent = feito + "%";
    var rotulos = [];
    lista_.forEach(function (p) { if (rotulos.indexOf(p.rotulo) < 0) rotulos.push(p.rotulo); });
    document.getElementById("progressoTitulo").textContent = lista_.length
      ? "Faltam " + lista_.length : "Tudo pronto";
    document.getElementById("progressoLista").textContent = rotulos.slice(0, 3).join(" · ")
      + (rotulos.length > 3 ? " · e mais" : "");
    painelProgresso.classList.toggle("pronto", !lista_.length);
    if (!lista_.length && faltavaAntes && !reduzirMovimento) {
      painelProgresso.classList.remove("pulsar");
      void painelProgresso.offsetWidth;
      painelProgresso.classList.add("pulsar");
    }
    faltavaAntes = lista_.length > 0;
    ajustarPaineis(false, lista_);
  }

  /* OS PAINÉIS: cada um diz quantas faltas tem e o resumo de agora. Abrir
     sozinho só no começo e quando o caminho muda (ou para levar ao campo
     que falta); depois, quem abre e fecha é a pessoa. */
  function painelDe(elemento) {
    return elemento ? elemento.closest("[data-painel]") : null;
  }

  function texto(id) { return valorDe(id); }

  function resumoCliente() {
    var partes = [texto("campoNome") || "sem nome"];
    if (texto("campoEstabelecimento")) partes.push(texto("campoEstabelecimento"));
    var documento = texto("campoDocumento").replace(/\D/g, "");
    partes.push(documento ? (documento.length === 14 ? "CNPJ ✓" : "CPF ✓") : "sem CPF/CNPJ");
    if (texto("campoTelefone")) partes.push(texto("campoWhatsapp") === "sim" ? "WhatsApp ✓" : "Telefone ✓");
    if (texto("campoEmail")) partes.push("E-mail ✓");
    if (!texto("campoTelefone") && !texto("campoEmail")) partes.push("sem contato");
    return partes.join(" · ");
  }

  function resumoEndereco() {
    if (!texto("campoEndereco") && !texto("campoCidade") && !texto("campoCep")) {
      return "Sem endereço (opcional; sem ele não há alfinete no mapa)";
    }
    var rua = [texto("campoEndereco"), texto("campoNumero")].filter(Boolean).join(", ");
    var cidade = [texto("campoCidade"), texto("campoEstado")].filter(Boolean).join("/");
    var partes = [rua, texto("campoBairro"), cidade].filter(Boolean);
    if (texto("campoCep")) partes.push("CEP ✓");
    if (chaveMapa && chaveMapa.checked) partes.push("no mapa ✓");
    return partes.join(" · ");
  }

  function resumoCondicoes() {
    var validade = texto("campoValidade");
    var partes = [/^\d{4}-\d{2}-\d{2}$/.test(validade)
      ? "Validade " + validade.slice(8) + "/" + validade.slice(5, 7) + "/" + validade.slice(0, 4)
      : "Validade padrão"];
    [texto("campoPagamento"), texto("campoEnvio")].forEach(function (valor) { if (valor) partes.push(valor); });
    if (texto("campoPrazo")) partes.push("Prazo ✓");
    if (texto("campoObservacoes")) partes.push("Observações ✓");
    if (partes.length === 1) partes.push("pagamento e entrega em branco");
    return partes.join(" · ");
  }

  function resumos(conta) {
    var quantos = cartoes().length;
    return {
      cliente: resumoCliente(),
      endereco: resumoEndereco(),
      itens: quantos ? quantos + (quantos === 1 ? " item" : " itens") + " · " + moeda(conta.subtotal) : "Nenhum item",
      valores: [
        texto("campoFrete") ? "Frete R$ " + texto("campoFrete") : "Frete a preencher",
        "Total " + moeda(conta.final),
        texto("campoPagamento")
      ].filter(Boolean).join(" · ")
    };
  }

  function ajustarPaineis(abrir, lista_) {
    lista_ = lista_ || pendencias(contas());
    var faltas = {};
    lista_.forEach(function (p) {
      var alvo = p.alvo ? document.getElementById(p.alvo) : null;
      var painel = painelDe(alvo);
      if (alvo && !painel) return;
      var nome = painel ? painel.dataset.painel : "valores";
      faltas[nome] = (faltas[nome] || 0) + 1;
    });
    var textos = resumos(contas());
    form.querySelectorAll("[data-painel]").forEach(function (painel) {
      var nome = painel.dataset.painel;
      var quantas = faltas[nome] || 0;
      var estado = painel.querySelector("[data-estado]");
      if (estado) {
        estado.textContent = quantas ? "Falta " + quantas : "✓";
        estado.classList.toggle("falta", !!quantas);
      }
      var resumo = painel.querySelector("[data-resumo]");
      if (resumo && textos[nome] !== undefined) resumo.textContent = textos[nome];
      painel.classList.toggle("com-falta", !!quantas);
      if (abrir && !painel.hidden) {
        var baixa = !!painel.querySelector(".ls-imp-selo.baixa");
        painel.open = !!quantas || baixa;
      }
    });
    var condicoes = document.querySelector("[data-resumo-condicoes]");
    if (condicoes) condicoes.textContent = resumoCondicoes();
    if (abrir) {
      /* As dobras de dentro (as condições) abrem só se algo nelas faltar. */
      form.querySelectorAll("details.ls-imp-sub").forEach(function (dobra) {
        dobra.open = lista_.some(function (p) {
          var alvo = p.alvo ? document.getElementById(p.alvo) : null;
          return !!alvo && dobra.contains(alvo);
        });
      });
    }
  }

  /* PRÓXIMO CAMPO: abre o painel, rola até o campo, põe o foco e
     destaca, com a dica do que se espera. */
  var destacado = null;
  function limparDestaque() {
    if (!destacado) return;
    destacado.caixa.classList.remove("ls-imp-alvo");
    if (destacado.dica && destacado.dica.parentNode) destacado.dica.parentNode.removeChild(destacado.dica);
    destacado = null;
  }

  function destacar(alvo, motivo) {
    limparDestaque();
    var caixa = alvo.closest(".ls-imp-campo, .ls-imp-item-produto, .ls-imp-alerta, .ls-imp-repetido, .ls-imp-endereco, .ls-imp-secao") || alvo;
    caixa.classList.add("ls-imp-alvo");
    var dica = document.createElement("p");
    dica.className = "ls-imp-dica";
    dica.setAttribute("role", "status");
    var icone = document.createElement("i");
    icone.className = "bi bi-arrow-return-right";
    icone.setAttribute("aria-hidden", "true");
    dica.appendChild(icone);
    dica.appendChild(document.createTextNode(" " + motivo.charAt(0).toUpperCase() + motivo.slice(1) + "."));
    caixa.appendChild(dica);
    destacado = { caixa: caixa, dica: dica, alvo: alvo.id };
  }

  function irPara(pendencia) {
    var alvo = pendencia.alvo ? document.getElementById(pendencia.alvo) : null;
    if (!alvo || alvo.closest("[hidden]")) alvo = document.getElementById("blocoAlertas") || painelProgresso;
    /* Abre o painel e qualquer dobra de dentro em que o campo esteja. */
    for (var dobra = alvo.closest("details"); dobra; dobra = dobra.parentElement && dobra.parentElement.closest("details")) {
      if (!dobra.open) dobra.open = true;
    }
    alvo.scrollIntoView({ behavior: reduzirMovimento ? "auto" : "smooth", block: "center" });
    window.setTimeout(function () {
      var focavel = alvo.matches("input, select, textarea, button")
        ? alvo : alvo.querySelector("input:not([type=hidden]), select, textarea, button");
      if (focavel) { try { focavel.focus({ preventScroll: true }); } catch (e) { focavel.focus(); } }
      destacar(alvo, pendencia.motivo);
      guiando = focavel ? focavel.id : null;
    }, reduzirMovimento ? 0 : 320);
  }

  function proximoCampo() {
    var lista_ = pendencias(contas());
    desenharPendencias(lista_);
    if (!lista_.length) {
      limparDestaque();
      botaoCriar.focus();
      return;
    }
    irPara(lista_[0]);
  }
  document.getElementById("proximoCampo").addEventListener("click", proximoCampo);

  document.getElementById("listaPendencias").addEventListener("click", function (evento) {
    var link = evento.target.closest("a[data-alvo]");
    if (!link) return;
    evento.preventDefault();
    var lista_ = pendencias(contas());
    var achada = lista_.filter(function (p) { return p.alvo === link.dataset.alvo; })[0];
    irPara(achada || { alvo: link.dataset.alvo, motivo: link.textContent.split(" — ").slice(1).join(" — ") });
  });

  /* AVANÇAR SOZINHO, mas só quando a pessoa termina: Enter, ou saindo do
     campo para lugar nenhum -- nunca no meio da digitação, e nunca
     roubando o clique que ela deu em outro campo. */
  var guiando = null;
  form.addEventListener("focusin", function (evento) {
    var id = evento.target.id;
    if (!id) return;
    var faltando = pendencias(contas()).some(function (p) { return p.alvo === id; });
    if (faltando) guiando = id;
  });

  function aoTerminar(campo, levarFoco) {
    if (!guiando || campo.id !== guiando) return false;
    var lista_ = pendencias(contas());
    if (lista_.some(function (p) { return p.alvo === guiando; })) return false;
    guiando = null;
    limparDestaque();
    desenharPendencias(lista_);
    if (!levarFoco) return true;
    if (!lista_.length) botaoCriar.focus();
    else irPara(lista_[0]);
    return true;
  }

  form.addEventListener("keydown", function (evento) {
    if (evento.key !== "Enter") return;
    var campo = evento.target;
    if (!campo.matches("input") || /^(checkbox|radio|submit|button)$/.test(campo.type)) return;
    if (campo.closest("#clienteBuscaBox, [data-busca-item]")) return;
    // Enter não envia o formulário pela metade: leva ao próximo que falta.
    evento.preventDefault();
    if (!aoTerminar(campo, true)) {
      var lista_ = pendencias(contas());
      if (lista_.length) irPara(lista_[0]);
    }
  });

  form.addEventListener("focusout", function (evento) {
    var campo = evento.target;
    var destino = evento.relatedTarget;
    window.setTimeout(function () { aoTerminar(campo, !destino); }, 0);
  });

  form.addEventListener("change", function (evento) {
    // Caixa de "Conferi", "Criar mesmo assim", "Aceitar": resolvido o
    // destacado, segue para o próximo.
    var campo = evento.target;
    if (!destacado || !campo.matches("input[type=checkbox], input[type=radio], select")) return;
    if (!destacado.caixa.contains(campo)) return;
    window.setTimeout(function () {
      var lista_ = pendencias(contas());
      if (lista_.some(function (p) { return p.alvo === destacado.alvo; })) return;
      limparDestaque();
      desenharPendencias(lista_);
      if (lista_.length) irPara(lista_[0]); else botaoCriar.focus();
    }, 0);
  });

  /* ------------------------------------------ o modal da decisão */
  var decisao = document.getElementById("decisaoImportacao");
  var cartaoDecisao = decisao ? decisao.querySelector(".ls-imp-decisao-cartao") : null;
  var chaveDecidido = "ls-imp-decidido:" + window.location.pathname;
  var focoAntesDoModal = null;

  function focaveis() {
    return Array.prototype.slice.call(cartaoDecisao.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'
    )).filter(function (el) { return el.offsetParent !== null; });
  }

  /* PASSOS. Um de cada vez, com botões grandes: a data (só quando o
     documento não diz, ou diz uma data de agora), o cliente, e os itens com
     os dois caminhos. Cada passo mostra o que está certo numa linha e o que
     falta em destaque. */
  var passos = decisao ? Array.prototype.slice.call(decisao.querySelectorAll("[data-passo]")) : [];

  function irParaPasso(nome, comFoco) {
    var alvo = null;
    passos.forEach(function (passo) {
      var este = passo.dataset.passo === nome;
      passo.hidden = !este;
      if (este) alvo = passo;
    });
    if (!alvo) return;
    var chegou = false;
    decisao.querySelectorAll("[data-marca-passo]").forEach(function (marca) {
      var atual = marca.dataset.marcaPasso === nome;
      if (atual) chegou = true;
      marca.classList.toggle("atual", atual);
      marca.classList.toggle("feito", !chegou);
      if (atual) marca.setAttribute("aria-current", "step"); else marca.removeAttribute("aria-current");
    });
    if (comFoco) {
      var foco = nome === "itens"
        ? (alvo.querySelector(".recomendado .ls-imp-caminho-botao") || alvo.querySelector(".ls-imp-passo-titulo"))
        : nome === "data"
          ? (alvo.querySelector(".ls-imp-data-opcao.sugerida") || alvo.querySelector(".ls-imp-passo-titulo"))
          : alvo.querySelector(".ls-imp-passo-seguir") || alvo.querySelector(".ls-imp-passo-titulo");
      window.setTimeout(function () { if (foco) foco.focus(); }, reduzirMovimento ? 0 : 60);
    }
  }

  function primeiroPasso() {
    var visivel = passos.filter(function (passo) { return !passo.hidden; })[0];
    return (visivel || passos[0] || { dataset: {} }).dataset.passo;
  }

  function abrirDecisao() {
    if (!decisao) return;
    focoAntesDoModal = document.activeElement;
    decisao.hidden = false;
    document.documentElement.classList.add("ls-imp-modal-aberto");
    window.requestAnimationFrame(function () { decisao.classList.add("aberto"); });
    irParaPasso(primeiroPasso(), true);
  }

  function fecharDecisao(paraGuiada) {
    if (!decisao || decisao.hidden) return;
    decisao.classList.remove("aberto");
    cartaoDecisao.style.transform = "";
    document.documentElement.classList.remove("ls-imp-modal-aberto");
    try { window.sessionStorage.setItem(chaveDecidido, "1"); } catch (e) { /* sem armazenamento: tudo bem */ }
    window.setTimeout(function () { decisao.hidden = true; }, reduzirMovimento ? 0 : 200);
    if (paraGuiada) {
      ajustarPaineis(true);
      window.setTimeout(proximoCampo, reduzirMovimento ? 0 : 220);
    } else if (focoAntesDoModal && focoAntesDoModal.focus) {
      focoAntesDoModal.focus();
    }
  }

  function enviar() {
    var lista_ = pendencias(contas());
    desenharPendencias(lista_);
    if (lista_.length) { fecharDecisao(true); return; }
    fecharDecisao(false);
    if (form.requestSubmit) form.requestSubmit(botaoCriar);
    else botaoCriar.click();
  }

  if (decisao) {
    decisao.addEventListener("click", function (evento) {
      if (evento.target.closest("[data-fechar-decisao]")) { fecharDecisao(true); return; }
      var passo = evento.target.closest("[data-ir-passo]");
      if (passo) { irParaPasso(passo.dataset.irPasso, true); return; }
      var botao = evento.target.closest("[data-decidir]");
      if (!botao) return;
      if (chaveOrcamento) chaveOrcamento.checked = botao.dataset.decidir === "orcamento";
      aplicarCaminho();
      if (botao.dataset.acao === "criar") enviar();
      else fecharDecisao(true);
    });
    decisao.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") { evento.preventDefault(); fecharDecisao(true); return; }
      if (evento.key !== "Tab") return;
      var lista_ = focaveis();
      if (!lista_.length) return;
      var primeiro = lista_[0];
      var ultimo = lista_[lista_.length - 1];
      if (evento.shiftKey && document.activeElement === primeiro) { evento.preventDefault(); ultimo.focus(); }
      else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primeiro.focus(); }
    });
    /* A folha do celular desce com o dedo: puxada mais de 90 px, fecha e
       leva à tela guiada. */
    var alca = document.getElementById("decisaoAlca");
    var inicioY = null;
    if (alca) {
      alca.addEventListener("pointerdown", function (evento) {
        inicioY = evento.clientY;
        alca.setPointerCapture(evento.pointerId);
      });
      alca.addEventListener("pointermove", function (evento) {
        if (inicioY === null) return;
        var desceu = Math.max(0, evento.clientY - inicioY);
        cartaoDecisao.style.transform = "translateY(" + desceu + "px)";
      });
      alca.addEventListener("pointerup", function (evento) {
        if (inicioY === null) return;
        var desceu = evento.clientY - inicioY;
        inicioY = null;
        if (desceu > 90) fecharDecisao(true);
        else cartaoDecisao.style.transform = "";
      });
    }
  }
  document.querySelectorAll("[data-abrir-decisao]").forEach(function (botao) {
    botao.addEventListener("click", abrirDecisao);
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
      irPara(lista_[0]);
      return;
    }
    botaoCriar.disabled = true;
    if (window.Painel && Painel.ocupado) {
      Painel.ocupado(caminho === "cliente" ? "Cadastrando o cliente…" : "Criando o cliente e o orçamento…");
    }
  });

  aplicarModo();
  aplicarCaminho();
  avisarMapa();
  renumerar();
  iniciado = true;
  desenharPendencias(pendencias(contas()));
  /* A decisão abre logo depois da leitura -- uma vez por importação: ao
     recarregar a tela, a pessoa já decidiu. */
  var jaDecidiu = false;
  try { jaDecidiu = window.sessionStorage.getItem(chaveDecidido) === "1"; } catch (e) { jaDecidiu = false; }
  if (decisao && decisao.dataset.abrir === "1" && !jaDecidiu) abrirDecisao();
});
