/* A tela "Dados do contrato" (LEIA-ME-V10, seção 109).

   Duas coisas, e só:
     * a PRÉVIA: cada campo digitado aparece na hora no preâmbulo "como sai
       no contrato" (os <mark data-dc-previa> que o servidor já desenhou);
     * o SALVAR: pelo Painel.ligar, como as outras telas -- o erro volta no
       quadro do formulário, o recado sai num aviso e a tela se atualiza
       (a faixa "falta preencher" muda sozinha).

   O painel troca de tela sem recarregar (ls-soft-navigation.js): o script
   roda de novo a cada visita e só liga o que está na tela agora.
*/
(function () {
  "use strict";

  var form = document.getElementById("formDadosContrato");
  if (!form) return;

  /* ------------------------------------------------------------------
     A ASSINATURA DO REPRESENTANTE (LEIA-ME-V10, seção 152).
     Escolher a foto já pede a PRÉVIA ao servidor (que tira o papel e
     devolve só o traço; nada é gravado). "Salvar esta assinatura" manda a
     mesma foto de novo, agora para gravar. Remover pede confirmação na
     folha do LSAviso. Erro: toast do LSAviso e o botão da foto em destaque.
     ------------------------------------------------------------------ */
  function ligarRubrica() {
    var caixa = document.getElementById("dcRubrica");
    var formRubrica = document.getElementById("formRubrica");
    if (!caixa || !formRubrica) return;
    var arquivo = document.getElementById("dcRubricaArquivo");
    var escolher = document.getElementById("dcRubricaEscolher");
    var salvar = document.getElementById("dcRubricaSalvar");
    var cancelar = document.getElementById("dcRubricaCancelar");
    var remover = document.getElementById("dcRubricaRemover");
    var traco = document.getElementById("dcRubricaTraco");
    var situacao = document.getElementById("dcRubricaSituacao");
    var salva = traco && !traco.hidden ? traco.style.maskImage || traco.style.webkitMaskImage : "";
    var ocupado = false;

    function avisar(nivel, titulo, texto) {
      if (window.LSAviso && window.LSAviso.toast) window.LSAviso.toast({ nivel: nivel, titulo: titulo, texto: texto });
    }

    function desenhar(imagem) {
      if (!traco) return;
      var valor = imagem ? (imagem.indexOf("url(") === 0 ? imagem : "url(" + imagem + ")") : "";
      traco.hidden = !valor;
      traco.style.webkitMaskImage = valor;
      traco.style.maskImage = valor;
    }

    function dizer(icone, texto, classe) {
      situacao.className = "ls-dc-rubrica-situacao" + (classe ? " " + classe : "");
      situacao.innerHTML = "";
      var i = document.createElement("i");
      i.className = "bi " + icone;
      i.setAttribute("aria-hidden", "true");
      var s = document.createElement("span");
      s.textContent = texto;
      situacao.appendChild(i);
      situacao.appendChild(s);
    }

    function estado(previa) {
      var tem = caixa.getAttribute("data-tem") === "1";
      salvar.hidden = !previa;
      cancelar.hidden = !previa;
      remover.hidden = previa || !tem;
      escolher.querySelector("span").textContent = previa ? "Escolher outra foto" : (tem ? "Trocar a foto" : "Enviar a foto");
      caixa.classList.toggle("em-previa", Boolean(previa));
    }

    function mandar(acao, comArquivo) {
      var corpo = new FormData();
      corpo.append("action", acao);
      corpo.append("csrfmiddlewaretoken", formRubrica.querySelector("[name=csrfmiddlewaretoken]").value);
      if (comArquivo && arquivo.files[0]) corpo.append("assinatura_arquivo", arquivo.files[0]);
      ocupado = true;
      [escolher, salvar, cancelar, remover].forEach(function (b) { b.disabled = true; });
      return fetch(formRubrica.getAttribute("action"), {
        method: "POST", body: corpo, credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" }
      }).then(function (resposta) {
        return resposta.json().catch(function () { return null; }).then(function (json) {
          if (!resposta.ok || !json || json.status !== "sucesso") {
            throw new Error((json && json.msg) || "Não deu para enviar agora. Tente de novo em instantes.");
          }
          return json;
        });
      }).finally(function () {
        ocupado = false;
        [escolher, salvar, cancelar, remover].forEach(function (b) { b.disabled = false; });
      });
    }

    function falhou(erro) {
      escolher.classList.add("is-invalid");
      avisar("erro", "Não deu para usar esta imagem", erro.message);
    }

    escolher.addEventListener("click", function () { if (!ocupado) arquivo.click(); });

    arquivo.addEventListener("change", function () {
      escolher.classList.remove("is-invalid");
      if (!arquivo.files[0]) return;
      dizer("bi-hourglass-split", "Tirando o papel da foto…", "");
      mandar("assinatura_previa", true).then(function (json) {
        desenhar(json.imagem);
        dizer("bi-eye-fill", "Este é o traço que vai para os documentos (aqui na cor do tema; no papel, na cor da caneta). Ficou bom? Salve.", "previa");
        estado(true);
      }).catch(function (erro) {
        arquivo.value = "";
        desenhar(salva);
        voltarASituacao();
        estado(false);
        falhou(erro);
      });
    });

    function voltarASituacao() {
      if (caixa.getAttribute("data-tem") === "1") {
        dizer("bi-check-circle-fill", "Cadastrada. Entra no lado da Lazer & Sport em todo documento que o cliente assinou — os antigos também.", "");
      } else {
        dizer("bi-exclamation-triangle-fill", "Ainda não há assinatura cadastrada: os documentos assinados saem sem a assinatura da empresa.", "");
      }
    }

    cancelar.addEventListener("click", function () {
      arquivo.value = "";
      desenhar(salva);
      voltarASituacao();
      estado(false);
    });

    salvar.addEventListener("click", function () {
      mandar("assinatura_salvar", true).then(function (json) {
        salva = json.imagem;
        caixa.setAttribute("data-tem", "1");
        arquivo.value = "";
        desenhar(salva);
        voltarASituacao();
        estado(false);
        avisar("sucesso", "Assinatura salva", json.msg);
      }).catch(falhou);
    });

    remover.addEventListener("click", function () {
      var pergunta = window.LSAviso && window.LSAviso.confirmar
        ? window.LSAviso.confirmar({
            titulo: "Remover a assinatura?",
            texto: "Os documentos assinados voltam a sair sem a assinatura da empresa, até você enviar outra.",
            confirmar: "Remover", perigo: true
          })
        : Promise.resolve(false);
      pergunta.then(function (sim) {
        if (!sim) return;
        mandar("assinatura_remover", false).then(function (json) {
          salva = "";
          caixa.setAttribute("data-tem", "0");
          desenhar("");
          voltarASituacao();
          estado(false);
          avisar("sucesso", "Assinatura removida", json.msg);
        }).catch(falhou);
      });
    });
  }

  function pintar(campo, valor) {
    document.querySelectorAll('[data-dc-previa="' + campo + '"]').forEach(function (alvo) {
      var texto = (valor || "").replace(/\s+/g, " ").trim();
      alvo.textContent = texto || "…";
      alvo.classList.toggle("vazio", !texto);
    });
  }

  form.querySelectorAll("[data-dc-campo]").forEach(function (campo) {
    campo.addEventListener("input", function () {
      pintar(campo.getAttribute("data-dc-campo"), campo.value);
      var rotulo = campo.closest(".ls-dc-campo");
      if (rotulo) rotulo.classList.toggle("vazio", !campo.value.trim());
    });
  });

  ligarRubrica();

  if (window.Painel && window.Painel.ligar) {
    window.Painel.ligar({
      form: "formDadosContrato",
      erro: "dcErro",
      rotuloCarregando: "Salvando…",
      mensagemPronta: function (json) { return json && json.msg; }
    });
  }
})();
