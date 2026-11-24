/* ======================================================================
   SEM "SALVAR NA CONTA DO GOOGLE" NA ÁREA INTERNA

   O QUE APARECIA. Ao abrir uma tela com endereço, telefone ou e-mail de
   cliente, ou ao salvar um cadastro, o Chrome (e o Edge) mostrava a
   janelinha dele: "Salvar endereço?" / "Salvar na Conta do Google", além de
   oferecer os dados pessoais de quem está no computador para preencher o
   campo. Não é o site que mostra: é o PREENCHIMENTO AUTOMÁTICO do navegador,
   que reconhece os campos (nome, rua, CEP, cidade, telefone, e-mail,
   empresa, cartão) e quer guardá-los no perfil -- que pode estar ligado à
   conta Google pessoal do colaborador. Um clique em "Salvar" levava o dado
   de um cliente para fora da empresa.

   O QUE ESTE ARQUIVO FAZ, em toda tela que usa o base_inner.html (painel
   interno, gestão /adm e RH), inclusive no que entra na página depois
   (janelas, linhas novas, navegação sem recarregar):
   - todo campo de CONTATO / ENDEREÇO / DOCUMENTO / CARTÃO recebe
     autocomplete="ls-interno". O Chrome IGNORA autocomplete="off" nesses
     campos (decisão dele, desde 2014), mas respeita um valor que ele não
     conhece: o campo deixa de ser "endereço" para o navegador -- ele não
     oferece preencher e NÃO OFERECE SALVAR;
   - os outros campos de texto ficam com autocomplete="off" (o navegador
     não guarda nem sugere o que foi digitado antes naquele campo);
   - o formulário inteiro fica com autocomplete="off".
   Ficam como estão: os campos de senha e de login (current-password,
   new-password, username, one-time-code) e o campo marcado com
   data-ls-autofill="livre" (para um caso em que o preenchimento seja útil).

   GARANTIA TOTAL, POR COMPUTADOR: isto é um pedido ao navegador. Para
   proibir de vez nos computadores da empresa, desligue em cada Chrome
   (Configurações > Preenchimento automático e senhas > Endereços e mais >
   "Salvar e preencher endereços") ou aplique a política
   ferramentas/navegador/sem-salvar-no-google.reg (LEIA-ME-V10, seção 134).
   ====================================================================== */
(function () {
  "use strict";
  var NAO_CONHECIDO = "ls-interno";
  var LIVRES = /^(current-password|new-password|username|one-time-code|webauthn)$/;
  // valores de autocomplete que o navegador entende como dado pessoal
  var TIPOS_PESSOAIS = /(^|\s)(name|given-name|additional-name|family-name|nickname|honorific-prefix|honorific-suffix|organization|organization-title|street-address|address-line[123]|address-level[1234]|country|country-name|postal-code|tel|tel-[a-z-]+|email|bday|bday-[a-z]+|sex|url|photo|impp|cc-[a-z-]+|transaction-[a-z]+)$/;
  // palavras que o navegador usa para "adivinhar" o campo (pelo nome, rótulo e exemplo)
  var CONTATO = new RegExp([
    "endere", "logradouro", "\\brua\\b", "avenida", "bairro", "complemento", "\\bcep\\b", "cidade", "munic", "estado", "\\buf\\b",
    "pa[ií]s", "address", "street", "city", "\\bzip", "postal", "nome", "name", "sobrenome", "e-?mail", "telefone", "\\bfone",
    "celular", "whats", "phone", "\\btel\\b", "empresa", "raz[aã]o", "fantasia", "company", "organiza", "contato", "destinat",
    "respons[aá]vel", "cliente", "cpf", "cnpj", "\\brg\\b", "cart[aã]o", "\\bcard", "validade", "cvv", "cvc", "titular",
    "nascimento", "birth", "n[uú]mero", "\\bnum\\b", "refer[eê]ncia",
  ].join("|"), "i");
  var NAO_SAO_TEXTO = /^(hidden|submit|button|reset|image|checkbox|radio|file|range|color|password)$/;

  function rotulo(campo) {
    var partes = [campo.name, campo.id, campo.getAttribute("placeholder"), campo.getAttribute("aria-label"), campo.getAttribute("title")];
    try {
      if (campo.labels) for (var i = 0; i < campo.labels.length; i++) partes.push(campo.labels[i].textContent);
    } catch (e) { /* campo sem rótulo */ }
    // "rua_entrega", "telefone-2", "nomeCliente": separa as palavras como o navegador faz
    return partes.filter(Boolean).join(" ").replace(/[_\-.\[\]]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2").slice(0, 300);
  }

  function tratar(campo) {
    var marca = campo.tagName;
    if (marca !== "INPUT" && marca !== "TEXTAREA" && marca !== "SELECT") return;
    if (marca === "INPUT" && NAO_SAO_TEXTO.test((campo.getAttribute("type") || "text").toLowerCase())) return;
    if (campo.getAttribute("data-ls-autofill") === "livre") return;
    var atual = (campo.getAttribute("autocomplete") || "").trim().toLowerCase();
    if (LIVRES.test(atual) || atual === NAO_CONHECIDO) return;
    var pessoal = TIPOS_PESSOAIS.test(atual) || CONTATO.test(rotulo(campo));
    var certo = pessoal ? NAO_CONHECIDO : "off";
    if (atual !== certo) campo.setAttribute("autocomplete", certo);
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
      // um script que troca o nome, o exemplo ou o próprio autocomplete do campo: confere de novo
      attributes: true, attributeFilter: ["autocomplete", "name", "placeholder", "type"],
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", comecar);
  else comecar();
  // os campos que já estão na página antes do DOMContentLoaded (o navegador olha cedo)
  varrer(document.documentElement);

  window.LSSemAutofill = { varrer: varrer };
})();
