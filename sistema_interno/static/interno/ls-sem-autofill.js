/* ======================================================================
   SEM "SALVAR ENDEREÇO?" (CONTA DO GOOGLE) NA ÁREA INTERNA

   O QUE APARECIA. Ao salvar um cliente, um orçamento, uma O.S. -- qualquer
   tela com nome, rua, CEP, cidade, telefone ou e-mail --, o Chrome (e o Edge)
   abria a janelinha dele: "Salvar endereço? ... Esse será salvo na sua conta
   <fulano>@gmail.com". Não é o site que mostra: é o PREENCHIMENTO AUTOMÁTICO
   do navegador, que lê o formulário enviado, monta um "endereço" com os
   dados do CLIENTE e oferece guardar na conta Google de quem está no
   computador. Um clique em "Salvar" levava dado de cliente para fora da
   empresa. Ele também guardava, calado, o que foi digitado em cada campo
   (o "histórico do campo") para sugerir depois.

   O QUE FUNCIONA DE VERDADE (medido no Chromium, em chrome://autofill-
   internals e no arquivo do perfil, com um formulário de cliente igual ao
   nosso -- ver LEIA-ME-V10, seção 135):
     autocomplete="off" ................ importa o endereço (o Chrome ignora)
     autocomplete com valor inventado .. importa o endereço E guarda o histórico
     autocomplete="transaction-amount" . NÃO importa; guarda o histórico
     role="presentation" ............... NÃO importa e NÃO guarda o histórico
   Com role="presentation" o navegador deixa o campo de fora do preenchimento
   automático inteiro (tipo UNKNOWN_TYPE). Para quem usa leitor de tela nada
   muda: a regra do ARIA manda ignorar esse papel em campo que recebe foco.

   O QUE ESTE ARQUIVO FAZ, em toda tela da área interna (base_inner.html:
   painel, gestão /adm e RH; rh/folha_base.html; e o /system/ do Django),
   inclusive no que entra na página depois (janelas, linhas novas, navegação
   sem recarregar) e no campo que um script mudar:
   - TODO campo de texto, caixa de texto e lista recebe role="presentation"
     (se já não tiver um papel próprio) e a segunda trava no autocomplete:
     "transaction-amount" nos navegadores do tipo Chrome/Edge, "off" nos
     outros (Firefox e Safari respeitam o "off");
   - todo <form> fica com autocomplete="off".
   Ficam como estão: os campos de senha e de login (current-password,
   new-password, username, one-time-code, webauthn) e o campo marcado com
   data-ls-autofill="livre".

   O SITE PÚBLICO NÃO CARREGA ESTE ARQUIVO: lá o cliente preenche e salva o
   PRÓPRIO endereço (cadastro, carrinho, checkout), e o navegador dele pode
   ajudar como sempre.
   ====================================================================== */
(function () {
  "use strict";
  var agente = navigator.userAgent || "";
  var tipoChrome = /Chrome|Chromium|CriOS|Edg|OPR|SamsungBrowser/.test(agente);
  var TRAVA = tipoChrome ? "transaction-amount" : "off";
  var LIVRES = /^(current-password|new-password|username|one-time-code|webauthn)$/;
  var NAO_SAO_TEXTO = /^(hidden|submit|button|reset|image|checkbox|radio|file|range|color|password)$/;

  function tratar(campo) {
    var marca = campo.tagName;
    if (marca !== "INPUT" && marca !== "TEXTAREA" && marca !== "SELECT") return;
    if (marca === "INPUT" && NAO_SAO_TEXTO.test((campo.getAttribute("type") || "text").toLowerCase())) return;
    if (campo.getAttribute("data-ls-autofill") === "livre") return;
    var atual = (campo.getAttribute("autocomplete") || "").trim().toLowerCase();
    if (LIVRES.test(atual)) return;
    // 1a trava: fora do preenchimento automático (não importa endereço, não guarda histórico)
    if (!campo.hasAttribute("role")) campo.setAttribute("role", "presentation");
    // 2a trava: um tipo que o navegador conhece e que não é dado pessoal
    if (atual !== TRAVA) campo.setAttribute("autocomplete", TRAVA);
  }

  function varrer(raiz) {
    if (!raiz || raiz.nodeType !== 1) return;
    if (raiz.tagName === "FORM") { if (raiz.getAttribute("autocomplete") !== "off") raiz.setAttribute("autocomplete", "off"); }
    else tratar(raiz);
    if (!raiz.querySelectorAll) return;
    var formularios = raiz.querySelectorAll("form");
    for (var f = 0; f < formularios.length; f++) {
      if (formularios[f].getAttribute("autocomplete") !== "off") formularios[f].setAttribute("autocomplete", "off");
    }
    var campos = raiz.querySelectorAll("input, textarea, select");
    for (var i = 0; i < campos.length; i++) tratar(campos[i]);
  }

  // o que entra na página depois (janelas, linhas novas, a navegação sem recarregar)
  var fila = [];
  var agendado = false;
  function esvaziar() {
    agendado = false;
    var nos = fila;
    fila = [];
    for (var i = 0; i < nos.length; i++) if (nos[i].isConnected) varrer(nos[i]);
  }
  function comecar() {
    varrer(document.documentElement);
    if (!window.MutationObserver) return;
    new MutationObserver(function (mudancas) {
      for (var m = 0; m < mudancas.length; m++) {
        var mudanca = mudancas[m];
        if (mudanca.type === "attributes") { fila.push(mudanca.target); continue; }
        for (var n = 0; n < mudanca.addedNodes.length; n++) if (mudanca.addedNodes[n].nodeType === 1) fila.push(mudanca.addedNodes[n]);
      }
      if (fila.length && !agendado) { agendado = true; (window.queueMicrotask || setTimeout)(esvaziar); }
    }).observe(document.documentElement, {
      childList: true, subtree: true,
      // um script que troca o autocomplete, o papel ou o tipo do campo: confere de novo
      attributes: true, attributeFilter: ["autocomplete", "role", "type"],
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", comecar);
  else comecar();
  // antes de enviar, uma última conferência (o navegador lê o formulário nesta hora)
  document.addEventListener("submit", function (e) { varrer(e.target); }, true);

  window.LSSemAutofill = { varrer: varrer, trava: TRAVA };
})();
