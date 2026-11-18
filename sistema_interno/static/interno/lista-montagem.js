/* ======================================================================
   A LISTA DE MONTAGEM (LEIA-ME-V10, seção 108). O servidor é
   sistema_interno/views_montagem.py; a regra, montagem.py.

   Tudo por delegação no documento (funciona na tela que abre direto e na
   que chega pela navegação suave do painel):

     [data-montagem-etapas]   os chips das etapas de uma máquina: marcar
                              uma da frente conclui até ela; marcar uma de
                              trás é correção e pergunta antes (a folha do
                              LSAviso, nunca a caixa do navegador);
     [data-montagem-fila]     subir e descer na fila;
     [data-montagem-entregue] o orçamento com tudo pronto foi entregue.
   ====================================================================== */
(function (window, document) {
  "use strict";

  if (window.LSMontagem) return;
  window.LSMontagem = true;

  function csrf() {
    var campo = document.querySelector("#lmTela [name=csrfmiddlewaretoken]")
      || document.querySelector("[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function endereco() {
    var formulario = document.querySelector("[data-montagem-regras]");
    return formulario ? formulario.getAttribute("action") : "/producao/montagem/";
  }

  function avisar(nivel, titulo, texto) {
    if (window.LSAviso) window.LSAviso.toast({ nivel: nivel, titulo: titulo, texto: texto || "" });
  }

  function postar(campos) {
    var dados = new FormData();
    Object.keys(campos).forEach(function (chave) { dados.append(chave, campos[chave]); });
    dados.append("csrfmiddlewaretoken", csrf());
    return fetch(endereco(), {
      method: "POST",
      body: dados,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" }
    }).then(function (resposta) {
      return resposta.json().catch(function () { return {}; }).then(function (corpo) {
        if (!resposta.ok || corpo.status !== "sucesso") {
          throw new Error((corpo && corpo.msg) || "Não foi possível gravar agora. Tente de novo.");
        }
        return corpo;
      });
    });
  }

  function recarregar() {
    if (typeof window.LSAtualizarTela === "function") window.LSAtualizarTela();
    else window.location.reload();
  }

  function perguntar(opcoes) {
    if (window.LSAviso && typeof window.LSAviso.confirmar === "function") {
      return window.LSAviso.confirmar(opcoes);
    }
    return Promise.resolve(true);
  }

  /* ---------------- as etapas ---------------- */
  function marcarOrdem(grupo, ordem) {
    var radio = grupo.querySelector('input[data-ordem="' + ordem + '"]');
    if (radio) radio.checked = true;
  }

  document.addEventListener("change", function (evento) {
    var radio = evento.target;
    if (!radio || !radio.matches || !radio.matches("[data-montagem-etapas] input[type=radio]")) return;
    var grupo = radio.closest("[data-montagem-etapas]");
    /* as feitas são seguidas: a quantidade delas é a ordem da marcada antes */
    var anterior = grupo.querySelectorAll(".lm-etapa.feita").length;
    var nova = parseInt(radio.getAttribute("data-ordem") || "0", 10);
    var nome = grupo.getAttribute("data-montagem-nome") || "a máquina";
    var pergunta = Promise.resolve(true);
    if (nova < anterior) {
      pergunta = perguntar({
        titulo: "Voltar a etapa de " + nome + "?",
        texto: "As etapas da frente perdem o dia em que foram feitas. Use só para corrigir.",
        confirmar: "Voltar a etapa",
        cancelar: "Manter como está",
        icone: "alerta"
      });
    }
    pergunta.then(function (sim) {
      if (!sim) { marcarOrdem(grupo, anterior); return; }
      grupo.setAttribute("aria-busy", "true");
      postar({ action: "etapa", id: grupo.getAttribute("data-montagem-etapas"), etapa: radio.value })
        .then(function (corpo) {
          avisar("sucesso", "Lista de montagem", corpo.msg);
          recarregar();
        })
        .catch(function (erro) {
          marcarOrdem(grupo, anterior);
          avisar("erro", "A etapa não mudou", erro.message);
        })
        .finally(function () { grupo.removeAttribute("aria-busy"); });
    });
  });

  /* ---------------- a fila e a entrega ---------------- */
  document.addEventListener("click", function (evento) {
    var alvo = evento.target && evento.target.closest ? evento.target.closest("[data-montagem-fila],[data-montagem-entregue]") : null;
    if (!alvo || alvo.disabled) return;
    evento.preventDefault();
    if (alvo.hasAttribute("data-montagem-fila")) {
      alvo.disabled = true;
      postar({ action: "fila", id: alvo.getAttribute("data-montagem-id"), direcao: alvo.getAttribute("data-montagem-fila") })
        .then(function (corpo) { avisar("sucesso", "Fila de produção", corpo.msg); recarregar(); })
        .catch(function (erro) { avisar("erro", "A fila não mudou", erro.message); alvo.disabled = false; });
      return;
    }
    var origem = alvo.getAttribute("data-montagem-origem") || "o orçamento";
    perguntar({
      titulo: "Marcar " + origem + " como entregue?",
      texto: "Todas as máquinas dele saem da lista como entregues, e o cliente vê a entrega em Meus pedidos.",
      confirmar: "Entregue",
      cancelar: "Voltar"
    }).then(function (sim) {
      if (!sim) return;
      alvo.disabled = true;
      postar({ action: "entregue", id: alvo.getAttribute("data-montagem-entregue") })
        .then(function (corpo) { avisar("sucesso", "Lista de montagem", corpo.msg); recarregar(); })
        .catch(function (erro) { avisar("erro", "Não foi marcado", erro.message); alvo.disabled = false; });
    });
  });
})(window, document);
