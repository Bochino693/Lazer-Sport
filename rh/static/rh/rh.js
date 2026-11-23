/* RECURSOS HUMANOS -- o que as telas do RH fazem no navegador.

   O painel troca de tela sem recarregar (ls-soft-navigation.js): este
   arquivo roda de novo a cada visita, dentro de `LSTela.pronto`, e os
   cliques usam `Painel.aoClicar` (descartado junto com a tela). Nada de
   alert()/confirm(): recado é toast do LSAviso, confirmação é a folha dele
   (`data-ls-confirmar` nos formulários).

     * BATER O PONTO: o relógio na tela anda com a diferença para o relógio
       do SERVIDOR (só para mostrar -- a hora gravada é a de lá). O toque
       manda o tipo e, se a pessoa marcou, a localização do aparelho (com
       prazo curto: sem resposta em 8 s, vai sem). Volta o comprovante e o
       cartão do dia, já atualizado.
     * PEDIR AJUSTE: o tipo escolhido mostra só os campos dele.
     * FICHA: CPF e PIS conferidos pelos dígitos enquanto se digita; as
       especialidades só aparecem para a Engenharia de produção.
     * TAREFAS: o filtro dos chips de responsável e o "Sugerir pela etapa".
     * TERMO: o QR e o link de 10 minutos, renovados sozinhos. */
(function (window, document) {
  "use strict";

  function aviso(nivel, texto, titulo) {
    if (window.LSAviso) window.LSAviso.toast({ nivel: nivel, titulo: titulo, texto: texto });
  }

  function csrf(raiz) {
    var campo = (raiz || document).querySelector("[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  /* ------------------------------------------------------ o ponto */
  function ligarPonto() {
    var caixa = document.getElementById("rhPontoHoje");
    if (!caixa) return;
    var diferenca = (parseInt(caixa.getAttribute("data-agora"), 10) || Date.now()) - Date.now();

    function horaDoServidor() {
      var agora = new Date(Date.now() + diferenca);
      return agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "America/Sao_Paulo" });
    }
    var relogio = setInterval(function () {
      if (!document.body.contains(caixa)) { clearInterval(relogio); return; }
      var alvo = caixa.querySelector("[data-rh-hora]");
      if (alvo) alvo.textContent = horaDoServidor();
    }, 1000);

    var CHAVE = "rh-ponto-localizacao";
    function lembrarConsentimento() {
      var marcado = false;
      try { marcado = window.localStorage.getItem(CHAVE) === "1"; } catch (e) { /* sem armazenamento */ }
      var campo = caixa.querySelector("[data-rh-consentimento]");
      if (campo) {
        campo.checked = marcado;
        campo.addEventListener("change", function () {
          try { window.localStorage.setItem(CHAVE, campo.checked ? "1" : "0"); } catch (e) { /* idem */ }
        });
      }
    }
    lembrarConsentimento();

    function localizacao() {
      return new Promise(function (resolver) {
        if (!navigator.geolocation) { resolver(null); return; }
        var feito = false;
        var prazo = setTimeout(function () { if (!feito) { feito = true; resolver(null); } }, 8000);
        navigator.geolocation.getCurrentPosition(function (pos) {
          if (feito) return;
          feito = true; clearTimeout(prazo);
          resolver({ lat: pos.coords.latitude, lng: pos.coords.longitude, precisao: Math.round(pos.coords.accuracy || 0) });
        }, function () {
          if (feito) return;
          feito = true; clearTimeout(prazo); resolver(null);
        }, { enableHighAccuracy: true, timeout: 7000, maximumAge: 30000 });
      });
    }

    caixa.addEventListener("submit", function (evento) {
      var form = evento.target.closest("[data-rh-bater]");
      if (!form) return;
      evento.preventDefault();
      var botao = evento.submitter || form.querySelector("[data-rh-tipo]");
      var tipo = botao ? botao.getAttribute("data-rh-tipo") : "";
      var botoes = form.querySelectorAll("button");
      botoes.forEach(function (b) { b.disabled = true; });
      var consentiu = form.querySelector("[data-rh-consentimento]");
      var querLocal = consentiu && consentiu.checked;
      (querLocal ? localizacao() : Promise.resolve(null)).then(function (pos) {
        var dados = new FormData();
        dados.set("csrfmiddlewaretoken", csrf(form));
        dados.set("tipo", tipo);
        if (pos) {
          dados.set("localizacao", "1");
          dados.set("lat", String(pos.lat));
          dados.set("lng", String(pos.lng));
          dados.set("precisao", String(pos.precisao));
        }
        return fetch(form.getAttribute("action"), {
          method: "POST", body: dados, credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
        });
      }).then(function (resposta) {
        return resposta.json().then(function (json) { return { ok: resposta.ok, json: json }; });
      }).then(function (r) {
        if (!r.ok || !r.json || r.json.status !== "sucesso") {
          botoes.forEach(function (b) { b.disabled = false; });
          aviso("erro", (r.json && r.json.msg) || "Não foi possível registrar agora.", "Ponto não registrado");
          return;
        }
        caixa.innerHTML = r.json.html;
        var cartao = caixa.querySelector("[data-rh-comprovante]");
        if (cartao) {
          cartao.querySelector("[data-rh-comprovante-texto]").textContent = r.json.msg;
          cartao.querySelector("[data-rh-comprovante-codigo]").textContent = r.json.codigo + " · NSR " + r.json.nsr;
          cartao.querySelector("[data-rh-comprovante-link]").setAttribute("href", r.json.comprovante);
          cartao.hidden = false;
        }
        lembrarConsentimento();
        aviso("sucesso", r.json.msg + " Comprovante " + r.json.codigo + ".", "Ponto registrado");
        if (navigator.vibrate) { try { navigator.vibrate(60); } catch (e) { /* sem vibração */ } }
      }).catch(function () {
        botoes.forEach(function (b) { b.disabled = false; });
        aviso("erro", "A conexão caiu antes de o servidor responder. Confira a internet e toque de novo: se a marcação tiver entrado, o servidor avisa.", "Sem conexão");
      });
    });
  }

  /* ------------------------------------------------------ pedir ajuste */
  function ligarAjuste() {
    var form = document.querySelector("[data-rh-ajuste]");
    if (!form) return;
    var data = form.querySelector("[name=data]");
    var maximoOriginal = data ? data.getAttribute("max") : "";
    function mostrar() {
      var escolhido = (form.querySelector("[name=tipo]:checked") || {}).value || "incluir";
      form.querySelectorAll("[data-rh-so]").forEach(function (parte) {
        parte.hidden = parte.getAttribute("data-rh-so") !== escolhido;
      });
      if (data) {
        if (escolhido === "abono") data.removeAttribute("max");
        else if (maximoOriginal) data.setAttribute("max", maximoOriginal);
      }
      var hora = form.querySelector("[name=hora]");
      if (hora) hora.required = escolhido === "incluir";
    }
    form.addEventListener("change", function (evento) {
      if (evento.target.name === "tipo") mostrar();
    });
    mostrar();
  }

  /* ------------------------------------------------------ a ficha */
  function digitos(texto) { return String(texto || "").replace(/\D/g, ""); }
  function cpfValido(valor) {
    var n = digitos(valor);
    if (n.length !== 11 || /^(\d)\1+$/.test(n)) return false;
    function dv(base, peso) {
      var soma = 0;
      for (var i = 0; i < base.length; i += 1) soma += parseInt(base.charAt(i), 10) * (peso - i);
      var resto = soma % 11;
      return resto < 2 ? 0 : 11 - resto;
    }
    var d1 = dv(n.slice(0, 9), 10);
    var d2 = dv(n.slice(0, 9) + d1, 11);
    return n.slice(9) === "" + d1 + d2;
  }
  function pisValido(valor) {
    var n = digitos(valor);
    if (n.length !== 11 || /^(\d)\1+$/.test(n)) return false;
    var pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    var soma = 0;
    for (var i = 0; i < 10; i += 1) soma += parseInt(n.charAt(i), 10) * pesos[i];
    var resto = soma % 11;
    return parseInt(n.charAt(10), 10) === (resto < 2 ? 0 : 11 - resto);
  }
  function conferirCampo(campo, valido, mensagem) {
    if (!campo) return;
    var bloco = campo.closest(".rh-campo");
    function rodar() {
      var vazio = !digitos(campo.value);
      var ok = vazio || valido(campo.value);
      campo.setCustomValidity(ok ? "" : mensagem);
      if (bloco) bloco.classList.toggle("tem-erro", !ok && digitos(campo.value).length >= 11);
      var dica = bloco && bloco.querySelector("[data-rh-dica]");
      if (!dica && bloco) {
        dica = document.createElement("small");
        dica.className = "rh-erro";
        dica.setAttribute("data-rh-dica", "");
        bloco.appendChild(dica);
      }
      if (dica) dica.textContent = (!ok && digitos(campo.value).length >= 11) ? mensagem : "";
    }
    campo.addEventListener("input", rodar);
    campo.addEventListener("blur", rodar);
  }
  function ligarFicha() {
    var form = document.querySelector("[data-rh-form-colaborador]");
    if (!form) return;
    conferirCampo(form.querySelector("[name=cpf]"), cpfValido, "CPF inválido: confira os dígitos.");
    conferirCampo(form.querySelector("[name=pis]"), pisValido, "PIS/NIS inválido: confira os dígitos.");
    var especialidades = form.querySelector("[data-rh-especialidades]");
    function setor() {
      var escolhido = (form.querySelector("[name=setor]:checked") || {}).value;
      if (especialidades) especialidades.hidden = escolhido !== "producao";
    }
    form.addEventListener("change", function (evento) { if (evento.target.name === "setor") setor(); });
    setor();
    ["uf", "ctps_uf"].forEach(function (nome) {
      var campo = form.querySelector("[name=" + nome + "]");
      if (campo) campo.addEventListener("input", function () { campo.value = campo.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 2); });
    });
  }

  /* ------------------------------------------------------ tarefas */
  function semAcento(texto) {
    return String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function ligarTarefas() {
    document.querySelectorAll("[data-rh-filtrar-chips]").forEach(function (campo) {
      var alvo = document.querySelector(campo.getAttribute("data-rh-filtrar-chips"));
      if (!alvo) return;
      campo.addEventListener("input", function () {
        var termo = semAcento(campo.value.trim());
        alvo.querySelectorAll(".rh-chip[data-nome]").forEach(function (chip) {
          chip.hidden = termo && semAcento(chip.getAttribute("data-nome")).indexOf(termo) === -1 && !chip.querySelector("input:checked");
        });
      });
    });

    var form = document.querySelector("[data-rh-nova-tarefa]");
    if (!form) return;
    var botao = form.querySelector("[data-rh-sugerir]");
    var nota = form.querySelector("[data-rh-sugestao-nota]");
    if (!botao) return;
    botao.addEventListener("click", function () {
      var etapa = (form.querySelector("[name=etapa]") || {}).value || "";
      var setor = (form.querySelector("[name=setor]:checked") || {}).value || "";
      var url = form.getAttribute("data-sugerir") + "?etapa=" + encodeURIComponent(etapa) + "&setor=" + encodeURIComponent(setor);
      botao.disabled = true;
      fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (json) {
          botao.disabled = false;
          form.querySelectorAll(".rh-chip--sugerido").forEach(function (c) { c.classList.remove("rh-chip--sugerido"); });
          var pessoas = (json && json.pessoas) || [];
          if (!pessoas.length) {
            if (nota) nota.textContent = "Ninguém ativo no setor dessa etapa. Escolha à mão.";
            return;
          }
          pessoas.forEach(function (p, i) {
            var chip = form.querySelector('.rh-chip[data-id="' + p.id + '"]');
            if (!chip) return;
            chip.hidden = false;
            chip.classList.add("rh-chip--sugerido");
            if (i === 0) chip.querySelector("input").checked = true;
          });
          var primeiro = pessoas[0];
          if (nota) {
            nota.textContent = "Sugerido: " + primeiro.nome + (primeiro.especialista ? " (tem a especialidade da etapa)" : "") +
              " · " + primeiro.abertas + " tarefa(s) aberta(s). Os outros sugeridos estão marcados em verde.";
          }
        })
        .catch(function () {
          botao.disabled = false;
          aviso("erro", "Não foi possível buscar a sugestão agora.");
        });
    });
  }

  /* ------------------------------------------------------ termo: QR e link */
  function ligarQr() {
    var caixa = document.querySelector("[data-rh-termo-qr]");
    if (!caixa) return;
    var qr = caixa.querySelector("[data-rh-qr]");
    var relogio = caixa.querySelector("[data-rh-relogio-link]");
    var numero = caixa.querySelector("[data-rh-numero-link]");
    var texto = caixa.querySelector("[data-rh-link-texto]");
    var whatsapp = caixa.querySelector("[data-rh-whatsapp]");
    var linkAtual = "";
    var fim = 0;
    var diferenca = 0;
    var validade = 600;  // segundos; o servidor manda o número certo
    var renovando = false;

    function pedir() {
      if (renovando || !document.body.contains(caixa)) return;
      renovando = true;
      var dados = new FormData();
      dados.set("csrfmiddlewaretoken", csrf(caixa));
      dados.set("action", "link");
      fetch(caixa.getAttribute("data-acao"), {
        method: "POST", body: dados, credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
      }).then(function (r) { return r.json(); }).then(function (json) {
        renovando = false;
        if (!json || json.status !== "sucesso") {
          qr.innerHTML = "";
          aviso("erro", (json && json.msg) || "Não foi possível gerar o link.");
          return;
        }
        qr.innerHTML = json.qr;
        linkAtual = json.link;
        texto.textContent = json.link;
        numero.textContent = json.numero;
        whatsapp.setAttribute("href", json.whatsapp);
        diferenca = json.agora - Date.now();
        fim = json.expira_em;
        validade = json.validade || validade;
      }).catch(function () { renovando = false; });
    }

    var tique = setInterval(function () {
      if (!document.body.contains(caixa)) { clearInterval(tique); return; }
      if (!fim) return;
      var resta = Math.max(0, Math.round((fim - (Date.now() + diferenca)) / 1000));
      relogio.textContent = Math.floor(resta / 60) + ":" + ("0" + (resta % 60)).slice(-2);
      if (resta <= 5) pedir();
    }, 1000);

    caixa.querySelector("[data-rh-novo-link]").addEventListener("click", pedir);
    caixa.querySelector("[data-rh-copiar-link]").addEventListener("click", function () {
      if (!linkAtual) return;
      var feito = function () { aviso("sucesso", "Link copiado. Ele vale " + Math.round(validade / 60) + " minutos."); };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(linkAtual).then(feito, function () { aviso("info", linkAtual, "Copie o link"); });
      } else {
        aviso("info", linkAtual, "Copie o link");
      }
    });
    pedir();
  }

  /* ==================================================================
     ESTILO APP EM TODO O RH (LEIA-ME-V10, seções 123 e 125)

     * FORMULÁRIO DE FOLHA (data-rh-ligar): vai por fetch, pelo
       `Painel.ligar` do painel -- o campo que falta vira a JANELA "Confira
       o campo" com ele aceso; o erro do servidor, a janela com o título, o
       campo e o botão que resolve ("Importar mesmo assim", "Cadastrar
       colaborador"); o deu-certo, toast (ou a janela do resultado). A
       folha fecha e a tela se atualiza sozinha (ou vai para `ir`).
     * AÇÃO RÁPIDA (data-rh-rapido): a situação da tarefa -- o botão tocado
       vai junto, toast e a lista se atualiza.
     * O ARQUIVO (data-rh-soltar): arrastar e soltar, a lista dos escolhidos.
     * O FILTRO DE CHIPS (data-rh-filtro): mostra só quem tem a marca.
     * A VISTA (data-rh-vista): linha do tempo ou tabela, lembrada no aparelho.
     * A JORNADA DIA A DIA na ficha: liga e desliga a grade da semana.
     ================================================================== */
  var contador = 0;

  function irPara(url) {
    if (window.LSNavigation && typeof window.LSNavigation.go === "function") window.LSNavigation.go(url);
    else window.location.assign(url);
  }

  function atualizar() {
    if (typeof window.LSAtualizarTela === "function") window.LSAtualizarTela();
    else window.location.reload();
  }

  function depoisDeFechar(form, fazer) {
    var modal = form.closest(".modal");
    if (modal && modal.id && modal.classList.contains("show") && window.Painel) {
      var feito = false;
      var seguir = function () { if (!feito) { feito = true; fazer(); } };
      modal.dataset.lsTrocaTela = "1";
      modal.addEventListener("hidden.bs.modal", seguir, { once: true });
      window.Painel.fechar(modal.id);
      setTimeout(seguir, 900);
    } else {
      fazer();
    }
  }

  function acoesDoFormulario(form) {
    return {
      forcar_cnpj: function () {
        var campo = form.querySelector("[data-rh-forcar-cnpj]");
        if (!campo) return;
        campo.value = "1";
        if (typeof form.requestSubmit === "function") form.requestSubmit();
      },
      cadastrar: function () {
        var cartao = form.closest(".rh-cartao");
        var botao = cartao && cartao.querySelector('[data-bs-target^="#rhCadastro"]');
        if (botao) botao.click();
      },
      recarregar: atualizar
    };
  }

  function ligarFormularios() {
    if (!window.Painel || typeof window.Painel.ligar !== "function") return;
    document.querySelectorAll("form[data-rh-ligar]").forEach(function (form) {
      if (form.dataset.rhLigado) return;
      form.dataset.rhLigado = "1";
      if (!form.id) { contador += 1; form.id = "rhForm" + contador + "x" + Date.now().toString(36); }
      var caixa = form.querySelector("[data-rh-erro]");
      if (!caixa) {
        caixa = document.createElement("div");
        caixa.className = "visually-hidden";
        caixa.setAttribute("role", "alert");
        caixa.setAttribute("data-rh-erro", "");
        form.insertBefore(caixa, form.firstChild);
      }
      if (!caixa.id) caixa.id = form.id + "Erro";
      /* O nome do campo na janela "Confira o campo" é o do rótulo, sem o "*". */
      form.querySelectorAll("label[for]").forEach(function (rotulo) {
        var campo = document.getElementById(rotulo.getAttribute("for"));
        if (campo && !campo.getAttribute("data-rotulo")) {
          campo.setAttribute("data-rotulo", rotulo.textContent.replace(/\*/g, "").replace(/\s+/g, " ").trim());
        }
      });
      window.Painel.ligar({
        form: form.id,
        erro: caixa.id,
        rotuloCarregando: form.getAttribute("data-rh-carregando") || "Salvando…",
        acoes: acoesDoFormulario(form),
        mensagemPronta: function (json) { return json && json.janela ? null : ((json && json.msg) || "Salvo."); },
        depois: function (json) {
          var campo = form.querySelector("[data-rh-forcar-cnpj]");
          if (campo) campo.value = "0";
          depoisDeFechar(form, function () {
            if (json && json.ir) irPara(json.ir);
            else atualizar();
          });
        }
      });
    });
  }

  function ligarRapidos() {
    document.querySelectorAll("form[data-rh-rapido]").forEach(function (form) {
      if (form.dataset.rhLigado) return;
      form.dataset.rhLigado = "1";
      form.addEventListener("submit", function (evento) {
        evento.preventDefault();
        var botao = evento.submitter;
        var dados;
        try { dados = new FormData(form, botao); } catch (e) {
          dados = new FormData(form);
          if (botao && botao.name) dados.set(botao.name, botao.value);
        }
        form.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
        fetch(form.getAttribute("action"), {
          method: "POST", body: dados, credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
        }).then(function (r) {
          return r.json().catch(function () { return null; }).then(function (json) { return { ok: r.ok, json: json, status: r.status }; });
        }).then(function (r) {
          form.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
          if (!r.ok || !r.json || r.json.status !== "sucesso") {
            if (window.Painel) window.Painel.erro(null, (r.json && r.json.msg) || "Não foi possível agora.", { titulo: (r.json && r.json.titulo) || "Não deu certo", status: r.status });
            return;
          }
          aviso("sucesso", r.json.msg);
          atualizar();
        }).catch(function () {
          form.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
          if (window.Painel) window.Painel.erro(null, "A conexão caiu antes de o servidor responder. Confira a internet e tente de novo.", { rede: true });
        });
      });
    });
  }

  function tamanho(bytes) {
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1).replace(".", ",") + " MB";
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function ligarSoltar() {
    document.querySelectorAll("[data-rh-soltar]").forEach(function (zona) {
      if (zona.dataset.rhLigado) return;
      zona.dataset.rhLigado = "1";
      var campo = zona.querySelector("input[type=file]");
      var lista = zona.querySelector("[data-rh-soltar-lista]");
      var titulo = zona.querySelector("[data-rh-soltar-titulo]");
      var tituloOriginal = titulo ? titulo.textContent : "";
      if (!campo) return;
      function mostrar() {
        var arquivos = Array.prototype.slice.call(campo.files || []);
        if (lista) {
          lista.innerHTML = "";
          arquivos.forEach(function (arquivo) {
            var item = document.createElement("li");
            var nome = document.createElement("span");
            nome.textContent = arquivo.name;
            var peso = document.createElement("small");
            peso.textContent = tamanho(arquivo.size);
            item.appendChild(nome);
            item.appendChild(peso);
            lista.appendChild(item);
          });
        }
        zona.classList.toggle("escolhido", arquivos.length > 0);
        if (titulo) {
          titulo.textContent = arquivos.length > 1 ? arquivos.length + " arquivos escolhidos"
            : (arquivos.length ? "Arquivo escolhido" : tituloOriginal);
        }
      }
      campo.addEventListener("change", mostrar);
      ["dragenter", "dragover"].forEach(function (tipo) {
        zona.addEventListener(tipo, function (evento) { evento.preventDefault(); zona.classList.add("arrastando"); });
      });
      ["dragleave", "drop"].forEach(function (tipo) {
        zona.addEventListener(tipo, function () { zona.classList.remove("arrastando"); });
      });
      zona.addEventListener("drop", function (evento) {
        evento.preventDefault();
        if (!evento.dataTransfer || !evento.dataTransfer.files.length) return;
        try {
          var juntos = new DataTransfer();
          Array.prototype.forEach.call(evento.dataTransfer.files, function (f) {
            if (campo.multiple || !juntos.files.length) juntos.items.add(f);
          });
          campo.files = juntos.files;
        } catch (e) { campo.files = evento.dataTransfer.files; }
        campo.dispatchEvent(new Event("change", { bubbles: true }));
      });
      var modal = zona.closest(".modal");
      if (modal) modal.addEventListener("hidden.bs.modal", function () {
        if (modal.dataset.lsTrocaTela) return;
        try { campo.value = ""; } catch (e) { /* sem limpar */ }
        mostrar();
      });
    });
  }

  function ligarRecusa() {
    var form = document.getElementById("rhFormRecusa");
    if (!form || !window.Painel) return;
    window.Painel.aoClicar("[data-rh-recusar]", function (botao) {
      form.setAttribute("action", botao.getAttribute("data-rh-recusar"));
      var resumo = form.querySelector("[data-rh-recusa-resumo]");
      if (resumo) resumo.textContent = botao.getAttribute("data-rh-recusar-texto") || "";
      var motivo = form.querySelector("[name=resposta]");
      if (motivo) motivo.value = "";
      window.Painel.abrir("rhFolhaRecusa");
      setTimeout(function () { if (motivo) motivo.focus(); }, 350);
    });
  }

  function ligarFiltro() {
    document.querySelectorAll("[data-rh-filtro]").forEach(function (grupo) {
      if (grupo.dataset.rhLigado) return;
      grupo.dataset.rhLigado = "1";
      var alvo = document.querySelector(grupo.getAttribute("data-rh-filtro"));
      if (!alvo) return;
      var vazio = alvo.querySelector("[data-rh-filtro-vazio]");
      grupo.addEventListener("click", function (evento) {
        var chip = evento.target.closest("[data-rh-filtro-chave]");
        if (!chip) return;
        var chave = chip.getAttribute("data-rh-filtro-chave");
        grupo.querySelectorAll("[data-rh-filtro-chave]").forEach(function (c) {
          var ativo = c === chip;
          c.classList.toggle("is-ativo", ativo);
          c.setAttribute("aria-pressed", ativo ? "true" : "false");
        });
        var visiveis = 0;
        alvo.querySelectorAll("[data-rh-marcas]").forEach(function (item) {
          var marcas = " " + (item.getAttribute("data-rh-marcas") || "") + " ";
          var mostra = !chave || marcas.indexOf(" " + chave + " ") !== -1;
          item.hidden = !mostra;
          if (mostra) visiveis += 1;
        });
        if (vazio) vazio.hidden = visiveis > 0;
      });
    });
  }

  function ligarVista() {
    document.querySelectorAll("[data-rh-vista]").forEach(function (grupo) {
      if (grupo.dataset.rhLigado) return;
      grupo.dataset.rhLigado = "1";
      var chave = grupo.getAttribute("data-rh-vista-chave") || "rh-vista";
      var secao = grupo.closest("section") || document;
      function mostrar(valor) {
        secao.querySelectorAll("[data-rh-vista-painel]").forEach(function (painel) {
          painel.hidden = painel.getAttribute("data-rh-vista-painel") !== valor;
        });
      }
      var lembrada = "";
      try { lembrada = window.localStorage.getItem(chave) || ""; } catch (e) { /* sem armazenamento */ }
      var radio = lembrada && grupo.querySelector('input[value="' + lembrada.replace(/[^a-z]/g, "") + '"]');
      if (radio) radio.checked = true;
      var marcado = grupo.querySelector("input:checked");
      mostrar(marcado ? marcado.value : "linha");
      grupo.addEventListener("change", function (evento) {
        if (!evento.target.value) return;
        mostrar(evento.target.value);
        try { window.localStorage.setItem(chave, evento.target.value); } catch (e) { /* idem */ }
      });
    });
  }

  function ligarJornadaSemana() {
    var caixa = document.querySelector("[data-rh-jornada-por-dia]");
    if (!caixa) return;
    var simples = document.querySelector("[data-rh-jornada-simples]");
    var semana = document.querySelector("[data-rh-jornada-semana]");
    function mostrar() {
      if (simples) simples.hidden = caixa.checked;
      if (semana) semana.hidden = !caixa.checked;
      if (simples) simples.querySelectorAll("input").forEach(function (campo) {
        if (campo.type === "time" || campo.type === "number") campo.required = !caixa.checked;
      });
    }
    caixa.addEventListener("change", function () {
      if (caixa.checked && semana) {
        /* Primeira vez: a grade nasce com a jornada simples nos dias marcados. */
        var vazia = !Array.prototype.some.call(semana.querySelectorAll("input[type=time]"), function (c) { return c.value; });
        if (vazia && simples) {
          var inicio = (simples.querySelector("[name=jornada_inicio]") || {}).value || "";
          var fim = (simples.querySelector("[name=jornada_fim]") || {}).value || "";
          simples.querySelectorAll("[name=jornada_dias]:checked").forEach(function (dia) {
            var a = semana.querySelector('[name="js_' + dia.value + '_0"]');
            var b = semana.querySelector('[name="js_' + dia.value + '_1"]');
            if (a) a.value = inicio;
            if (b) b.value = fim;
          });
        }
      }
      mostrar();
    });
    mostrar();
  }

  window.LSTela.pronto(function () {
    if (!document.getElementById("rhTela")) return;
    ligarPonto();
    ligarAjuste();
    ligarFicha();
    ligarTarefas();
    ligarQr();
    ligarFormularios();
    ligarRapidos();
    ligarSoltar();
    ligarRecusa();
    ligarFiltro();
    ligarVista();
    ligarJornadaSemana();
  });
})(window, document);
