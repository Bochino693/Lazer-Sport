(function () {
  "use strict";
  var modal = document.getElementById("lsCampaignModal");
  if (!modal) return;
  var form = document.getElementById("lsCampaignForm");
  var tipo = document.getElementById("lsCampaignType");
  var objeto = document.getElementById("lsCampaignObject");
  var segmento = document.getElementById("lsCampaignSegment");
  var assunto = document.getElementById("lsCampaignSubject");
  var mensagem = document.getElementById("lsCampaignMessage");
  var caracteres = document.getElementById("lsCampaignCharacters");
  var feedback = document.getElementById("lsCampaignFeedback");
  var botao = document.getElementById("lsCampaignSubmit");
  var contagemEmail = document.getElementById("lsCampaignEmailCount");
  var contagemWhatsapp = document.getElementById("lsCampaignWhatsappCount");
  var contagemIgnorados = document.getElementById("lsCampaignIgnoredCount");
  var tituloPrevia = document.getElementById("lsCampaignPreviewTitle");
  var textoPrevia = document.getElementById("lsCampaignPreviewText");
  var requisicaoAtual = null;
  var temporizador = null;
  var ultimoFoco = null;

  function canais() {
    return {
      email: form.querySelector('[name="email"]').checked ? "1" : "0",
      whatsapp: form.querySelector('[name="whatsapp"]').checked ? "1" : "0"
    };
  }
  function mensagemFeedback(texto, sucesso) {
    feedback.hidden = !texto;
    feedback.textContent = texto || "";
    feedback.classList.toggle("is-success", Boolean(sucesso));
  }
  function abrir(disparador) {
    ultimoFoco = disparador;
    form.reset();
    tipo.value = disparador.dataset.campanhaTipo || "";
    objeto.value = disparador.dataset.campanhaObjeto || "";
    assunto.value = disparador.dataset.campanhaTitulo || "";
    mensagem.value = "";
    caracteres.textContent = "0";
    botao.disabled = false;
    botao.type = "submit";
    botao.onclick = null;
    botao.classList.remove("is-complete");
    botao.innerHTML = '<i class="bi bi-send-fill"></i><span>Criar fila de envios</span>';
    mensagemFeedback("");
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("ls-campaign-open");
    preparar(true);
    window.setTimeout(function () { segmento.focus(); }, 120);
  }
  function fechar() {
    if (requisicaoAtual) requisicaoAtual.abort();
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("ls-campaign-open");
    if (ultimoFoco) ultimoFoco.focus({ preventScroll: true });
  }
  function preparar(preencherTexto) {
    if (!tipo.value || !objeto.value) return;
    if (requisicaoAtual) requisicaoAtual.abort();
    requisicaoAtual = new AbortController();
    var escolhidos = canais();
    var params = new URLSearchParams({
      tipo: tipo.value, objeto: objeto.value, segmento: segmento.value,
      email: escolhidos.email, whatsapp: escolhidos.whatsapp
    });
    tituloPrevia.textContent = "Conferindo os contatos…";
    fetch(modal.dataset.prepararUrl + "?" + params.toString(), {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      signal: requisicaoAtual.signal
    }).then(function (resposta) {
      return resposta.json().then(function (json) { return { ok: resposta.ok, json: json }; });
    }).then(function (resultado) {
      var json = resultado.json;
      if (!resultado.ok || json.status !== "sucesso") throw new Error(json.msg || "Não foi possível preparar a campanha.");
      if (preencherTexto || !assunto.value.trim()) assunto.value = json.titulo;
      if (preencherTexto || !mensagem.value.trim()) mensagem.value = json.mensagem;
      caracteres.textContent = String(mensagem.value.length);
      contagemEmail.textContent = json.email;
      contagemWhatsapp.textContent = json.whatsapp;
      contagemIgnorados.textContent = json.ignorados;
      tituloPrevia.textContent = json.total + " entrega" + (json.total === 1 ? " preparada" : "s preparadas");
      textoPrevia.textContent = "Contatos repetidos são unidos. Cadastros inválidos não entram na fila.";
      mensagemFeedback("");
    }).catch(function (erro) {
      if (erro.name === "AbortError") return;
      contagemEmail.textContent = contagemWhatsapp.textContent = contagemIgnorados.textContent = "—";
      tituloPrevia.textContent = "Revise esta divulgação";
      textoPrevia.textContent = erro.message;
      mensagemFeedback(erro.message, false);
    });
  }
  function agendarPrevia() {
    window.clearTimeout(temporizador);
    temporizador = window.setTimeout(function () { preparar(false); }, 180);
  }

  document.addEventListener("click", function (evento) {
    var disparador = evento.target.closest("[data-campanha-tipo][data-campanha-objeto]");
    if (disparador) { evento.preventDefault(); abrir(disparador); return; }
    if (evento.target.closest("[data-campanha-fechar]")) fechar();
  });
  document.addEventListener("keydown", function (evento) {
    if (!modal.classList.contains("is-open")) return;
    if (evento.key === "Escape") { fechar(); return; }
    if (evento.key !== "Tab") return;
    var focaveis = Array.prototype.slice.call(modal.querySelectorAll(
      'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])'
    )).filter(function (item) { return item.offsetParent !== null; });
    if (!focaveis.length) return;
    var primeiro = focaveis[0];
    var ultimo = focaveis[focaveis.length - 1];
    if (evento.shiftKey && document.activeElement === primeiro) {
      evento.preventDefault(); ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault(); primeiro.focus();
    }
  });
  segmento.addEventListener("change", agendarPrevia);
  form.querySelectorAll('[name="email"],[name="whatsapp"]').forEach(function (campo) {
    campo.addEventListener("change", agendarPrevia);
  });
  mensagem.addEventListener("input", function () { caracteres.textContent = String(mensagem.value.length); });

  form.addEventListener("submit", function (evento) {
    evento.preventDefault();
    var escolhidos = canais();
    if (escolhidos.email === "0" && escolhidos.whatsapp === "0") {
      mensagemFeedback("Escolha pelo menos um canal.", false);
      return;
    }
    botao.disabled = true;
    botao.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span>Criando fila…</span>';
    fetch(modal.dataset.criarUrl, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" }
    }).then(function (resposta) {
      return resposta.json().then(function (json) { return { ok: resposta.ok, json: json }; });
    }).then(function (resultado) {
      if (!resultado.ok || resultado.json.status !== "sucesso") throw new Error(resultado.json.msg || "Não foi possível criar a campanha.");
      mensagemFeedback(resultado.json.msg, true);
      botao.disabled = false;
      botao.classList.add("is-complete");
      botao.innerHTML = '<i class="bi bi-arrow-right-circle-fill"></i><span>Acompanhar campanha</span>';
      botao.type = "button";
      botao.onclick = function () { window.location.assign(resultado.json.detalhe); };
    }).catch(function (erro) {
      mensagemFeedback(erro.message, false);
      botao.disabled = false;
      botao.innerHTML = '<i class="bi bi-send-fill"></i><span>Tentar novamente</span>';
    });
  });
})();
