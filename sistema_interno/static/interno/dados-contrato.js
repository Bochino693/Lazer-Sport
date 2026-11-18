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

  if (window.Painel && window.Painel.ligar) {
    window.Painel.ligar({
      form: "formDadosContrato",
      erro: "dcErro",
      rotuloCarregando: "Salvando…",
      mensagemPronta: function (json) { return json && json.msg; }
    });
  }
})();
