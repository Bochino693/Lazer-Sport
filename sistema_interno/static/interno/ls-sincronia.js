/* Um relógio do painel atualiza números e listas, preservando a edição. */
(function (window, document) {
  "use strict";
  var estado = null, emVoo = false, pendente = false, caminho = "", timer = null;
  /* Depois de GRAVAR, a própria gravação já pede a tela (ou a lista) nova
     (painel.js, "ls:atualizacao-a-caminho"). Enquanto ela não chega, a
     revisão do sino é mais nova que a da tela -- e pedir a lista aqui seria
     buscar duas vezes a mesma coisa. Espera a que vem ("ls:atualizada");
     o prazo é a rede de segurança se ela nunca avisar. */
  var aCaminhoDesde = 0, PRAZO_DA_TELA_A_CAMINHO = 15000;

  function ocupado() {
    var foco = document.activeElement;
    var buscaPendente = Array.prototype.some.call(document.querySelectorAll('input[type="search"]'), function (campo) {
      return campo.value !== campo.defaultValue;
    });
    return buscaPendente || !!document.querySelector('.modal.show, .modal[data-ls-modal-estado="show"], .modal[data-ls-modal-estado="hide"], .ls-action-fab.is-open')
      || !!(foco && foco.matches('input, textarea, select, [contenteditable="true"]'));
  }

  function conferir() {
    if (document.visibilityState !== "visible" || emVoo || !window.LSNavigation) return;
    if (aCaminhoDesde && Date.now() - aCaminhoDesde < PRAZO_DA_TELA_A_CAMINHO) return;
    var marcador = document.querySelector("[data-ls-sincronia]");
    if (!marcador) return;
    if (caminho !== window.location.href) { caminho = window.location.href; pendente = false; }
    var atual = estado || (window.Painel && Painel.avisos.estado());
    var revisao = atual && atual.revisoes && atual.revisoes[marcador.dataset.lsSincronia];
    if (!revisao) return;
    var mudou = revisao !== marcador.dataset.lsRevisao;
    if (!mudou && (!pendente || ocupado())) return;
    emVoo = true;
    window.LSNavigation.atualizarPartes(ocupado).then(function (resultado) {
      if (resultado) pendente = !resultado.listaAtualizada;
    }).finally(function () { emVoo = false; });
  }

  function agendar() {
    window.clearTimeout(timer);
    timer = window.setTimeout(conferir, 100);
  }
  document.addEventListener("ls:estado", function (evento) { estado = evento.detail; agendar(); });
  document.addEventListener("ls:tela", function () { pendente = false; agendar(); });
  document.addEventListener("ls:atualizacao-a-caminho", function () { aCaminhoDesde = Date.now(); });
  document.addEventListener("ls:atualizada", function () { aCaminhoDesde = 0; agendar(); });
  document.addEventListener("hidden.bs.modal", agendar);
  document.addEventListener("focusout", agendar);
  document.addEventListener("click", function () { if (pendente) agendar(); });
  document.addEventListener("visibilitychange", agendar);
  agendar();
})(window, document);
