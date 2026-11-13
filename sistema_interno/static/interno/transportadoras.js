/* TRANSPORTADORAS (LEIA-ME-V10, seção 89) -- views_transportadoras.py.

   Três coisas, e nenhuma delas precisa recarregar a tela:

     * A BUSCA FILTRA NA HORA. Cada item traz o próprio texto já sem
       acento (`data-busca`, montado pelo servidor); digitar só esconde e
       mostra itens. O formulário continua GET, para quem estiver sem
       JavaScript.
     * "COPIAR CONTATO" põe nome, telefone, WhatsApp, e-mail, site e
       Instagram na área de transferência, para colar na conversa com o
       cliente. Navegador que não deixa copiar (HTTP, permissão negada)
       mostra o texto num aviso, para copiar à mão -- nunca alert().
     * GESTÃO cadastra e corrige na folha (o modal do painel, que sobe de
       baixo no celular) e desativa depois da folha de confirmação do
       LSAviso -- nunca confirm().

   O painel troca de tela sem recarregar (ls-soft-navigation.js): este
   arquivo roda de novo a cada visita. Os cliques usam `Painel.aoClicar`,
   que a navegação descarta junto com a tela. */
(function (window, document) {
  "use strict";

  function semAcento(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  /* As mesmas palavras que o servidor procura (transportadoras.termos_de_busca):
     sem acento e sem a última letra das longas -- "aéreo" acha "aérea". */
  function termosDe(busca) {
    return semAcento(busca).split(/\s+/).filter(Boolean).map(function (palavra) {
      return palavra.length > 4 ? palavra.slice(0, -1) : palavra;
    });
  }

  function aviso(opcoes) {
    if (window.LSAviso) window.LSAviso.toast(opcoes);
    else if (window.Painel) window.Painel.aviso(opcoes.texto || opcoes.titulo, opcoes.nivel === "erro" ? "erro" : "ok");
  }

  /* ---------------------------------------------------------- copiar */
  function copiarParaAreaDeTransferencia(texto) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(texto).then(
        function () { return true; },
        function () { return copiarPeloCampo(texto); }
      );
    }
    return Promise.resolve(copiarPeloCampo(texto));
  }

  function copiarPeloCampo(texto) {
    var campo = document.createElement("textarea");
    campo.value = texto;
    campo.setAttribute("readonly", "");
    campo.style.position = "fixed";
    campo.style.top = "-1000px";
    document.body.appendChild(campo);
    campo.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (erro) { ok = false; }
    campo.remove();
    return ok;
  }

  window.LSTela.pronto(function () {
    var tela = document.getElementById("tpTela");
    if (!tela || !window.Painel) return;
    var Painel = window.Painel;

    /* -------------------------------------------------------- busca */
    var campo = document.getElementById("tpBusca");
    var lista = document.getElementById("tpLista");
    var contagem = document.getElementById("tpContagem");
    var vazio = document.getElementById("tpVazio");
    var textoVazio = vazio ? vazio.querySelector("[data-tp-vazio-texto]") : null;
    var vazioOriginal = textoVazio ? textoVazio.textContent : "";

    function filtrar() {
      if (!campo || !lista) return;
      var termos = termosDe(campo.value);
      var visiveis = 0;
      lista.querySelectorAll("[data-tp-item]").forEach(function (item) {
        var texto = item.getAttribute("data-busca") || "";
        var ok = termos.every(function (termo) { return texto.indexOf(termo) !== -1; });
        item.hidden = !ok;
        if (ok) visiveis += 1;
      });
      lista.querySelectorAll("[data-tp-secao]").forEach(function (secao) {
        secao.hidden = !secao.querySelector("[data-tp-item]:not([hidden])");
      });
      if (contagem) {
        contagem.textContent = visiveis + (visiveis === 1 ? " transportadora" : " transportadoras");
      }
      if (vazio) {
        vazio.hidden = visiveis > 0;
        if (textoVazio) {
          textoVazio.textContent = termos.length
            ? "Nenhuma transportadora com “" + campo.value.trim() + "”. Tente outro estado ou outra palavra."
            : vazioOriginal;
        }
      }
    }

    if (campo) {
      campo.addEventListener("input", filtrar);
      var busca = campo.closest("form");
      if (busca) {
        busca.addEventListener("submit", function (evento) {
          evento.preventDefault();
          filtrar();
          campo.blur();
        });
      }
    }

    /* ------------------------------------------------ copiar contato */
    Painel.aoClicar("[data-tp-copiar]", function (botao) {
      var texto = botao.getAttribute("data-tp-copiar") || "";
      copiarParaAreaDeTransferencia(texto).then(function (copiou) {
        if (copiou) {
          aviso({ nivel: "sucesso", titulo: "Contato copiado", texto: "Cole na conversa com o cliente." });
        } else {
          aviso({ nivel: "alerta", titulo: "Copie à mão", texto: texto, duracao: 0 });
        }
      });
    });

    /* -------------------------------------------- gestão: a folha */
    var dadosEl = document.getElementById("tpDados");
    var form = document.getElementById("formTransportadora");
    if (!dadosEl || !form) return;

    var registros = [];
    try { registros = JSON.parse(dadosEl.textContent || "[]"); } catch (erro) { registros = []; }
    var porId = {};
    registros.forEach(function (registro) { porId[String(registro.id)] = registro; });

    var todoBrasil = document.getElementById("tpTodoBrasil");
    var regioes = document.getElementById("tpRegioes");
    var tipo = document.getElementById("tpTipo");
    var marcaHoje = document.getElementById("tpHoje");
    var hoje = marcaHoje ? marcaHoje.getAttribute("data-hoje") : "";
    var caixasUf = function () { return form.querySelectorAll('input[name="estados"]'); };

    function sincronizarBrasil() {
      var ligado = todoBrasil.checked;
      regioes.classList.toggle("is-desligado", ligado);
      caixasUf().forEach(function (caixa) { caixa.disabled = ligado; });
    }
    todoBrasil.addEventListener("change", sincronizarBrasil);

    tipo.addEventListener("change", function () {
      /* Nacional sem estado marcado é, quase sempre, "o Brasil inteiro". */
      var algum = Array.prototype.some.call(caixasUf(), function (c) { return c.checked; });
      if (tipo.value === "nacional" && !algum) {
        todoBrasil.checked = true;
        sincronizarBrasil();
      }
    });

    function preencher(registro) {
      form.reset();
      Painel.erro("tpErro", "");
      var r = registro || {};
      Painel.valor("tpId", r.id || "");
      Painel.valor("tpNome", r.nome || "");
      Painel.valor("tpFantasia", r.nome_fantasia || "");
      Painel.valor("tpTipo", r.tipo || "regional");
      Painel.valor("tpCidade", r.cidade_sede || "");
      Painel.valor("tpUfSede", r.uf_sede || "");
      Painel.valor("tpTelefone", r.telefone || "");
      Painel.valor("tpWhatsapp", r.whatsapp || "");
      Painel.valor("tpEmail", r.email || "");
      Painel.valor("tpInstagram", r.instagram || "");
      Painel.valor("tpSite", r.site || "");
      Painel.valor("tpObs", r.observacoes || "");
      Painel.valor("tpFonte", r.fonte_url || "");
      Painel.valor("tpFontesExtras", r.fontes_extras || "");
      Painel.valor("tpVerificado", r.verificado_em || (registro ? "" : hoje));
      Painel.valor("tpOrdem", r.ordem != null ? r.ordem : 100);
      todoBrasil.checked = Boolean(r.atende_todo_brasil);
      var marcadas = r.estados || [];
      caixasUf().forEach(function (caixa) { caixa.checked = marcadas.indexOf(caixa.value) !== -1; });
      sincronizarBrasil();
      document.getElementById("tpFormTitulo").textContent = registro
        ? "Corrigir " + (r.nome_fantasia || r.nome)
        : "Nova transportadora";
      Painel.abrir("modalTransportadora");
    }

    Painel.aoClicar("[data-tp-novo]", function () { preencher(null); });
    Painel.aoClicar("[data-tp-editar]", function (botao) {
      preencher(porId[botao.getAttribute("data-tp-editar")] || null);
    });

    /* O nome da região marca a região inteira (ou desmarca, se já estava). */
    Painel.aoClicar("[data-tp-regiao]", function (botao) {
      var caixas = botao.closest(".tp-form-regiao").querySelectorAll('input[name="estados"]');
      var todas = Array.prototype.every.call(caixas, function (c) { return c.checked; });
      caixas.forEach(function (c) { c.checked = !todas; });
    });

    Painel.ligar({
      form: "formTransportadora",
      erro: "tpErro",
      antes: function () {
        var algum = Array.prototype.some.call(caixasUf(), function (c) { return c.checked; });
        if (!todoBrasil.checked && !algum) {
          return "Marque os estados que ela atende, ou “Atende todo o Brasil”.";
        }
        return "";
      },
      mensagemPronta: function (json) { return json && json.msg; }
    });

    /* ------------------------------------- desativar e reativar */
    var formEstado = document.getElementById("formTpEstado");

    function mudarEstado(acao, id) {
      formEstado.querySelector('[name="action"]').value = acao;
      formEstado.querySelector('[name="id"]').value = id;
      Painel.ocupado("Salvando…");
      Painel.enviar(formEstado).then(function (json) {
        Painel.pronto();
        Painel.aviso(json.msg, "ok");
        if (typeof window.LSAtualizarTela === "function") window.LSAtualizarTela();
        else window.location.reload();
      }).catch(function (erro) {
        Painel.pronto();
        Painel.aviso(erro.message, "erro");
      });
    }

    Painel.aoClicar("[data-tp-desativar]", function (botao) {
      var nome = botao.getAttribute("data-nome") || "esta transportadora";
      window.LSAviso.confirmar({
        titulo: "Tirar " + nome + " das recomendações?",
        texto: "Ela some da lista da equipe, mas fica guardada em Desativadas, com a fonte, e pode voltar quando quiser.",
        confirmar: "Desativar",
        cancelar: "Manter",
        perigo: true
      }).then(function (sim) {
        if (sim) mudarEstado("desativar", botao.getAttribute("data-tp-desativar"));
      });
    });

    Painel.aoClicar("[data-tp-reativar]", function (botao) {
      mudarEstado("reativar", botao.getAttribute("data-tp-reativar"));
    });
  });
})(window, document);
