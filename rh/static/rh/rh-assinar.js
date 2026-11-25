/* O termo de exclusividade assinado com o dedo -- no painel e no link.

   O mesmo jeito do termo de compra (core/static/site/paginas/assinatura.js),
   escrito à parte porque aquela página tem o relógio e a folha dela:

     * O QUADRO: eventos de ponteiro (dedo, caneta e mouse), `touch-action:
       none` para o dedo não rolar a página, os pontos intermediários
       (`getCoalescedEvents`) e cada traço guardado à parte -- é o que deixa
       "Desfazer" e redesenhar quando a tela gira. Vai ao servidor um PNG de
       fundo transparente, com no máximo 1000 px de largura.
     * O ENVIO: confere na tela o que dá (nome com sobrenome, CPF com 11
       números, "Li e concordo", traço no quadro) e manda por fetch com o
       CSRF do formulário. O que o servidor recusar volta como aviso, com o
       campo marcado -- e o traço continua no quadro.
     * O RELÓGIO do link (só na página sem login): o servidor diz quantos
       segundos faltam; acabou, o botão para. O servidor confere de novo.

   Nada de alert()/confirm(): o erro aparece no próprio formulário (e, no
   painel, também no toast do LSAviso). */
(function () {
  "use strict";

  function iniciar() {
    var form = document.querySelector("[data-rh-assinar]");
    if (!form || form.dataset.rhLigado === "1") return;
    form.dataset.rhLigado = "1";

    var quadro = form.querySelector("[data-rh-quadro]");
    var canvas = quadro.querySelector("canvas");
    var campoPng = form.querySelector("[data-rh-assinatura-png]");
    var caixaErro = form.querySelector("[data-rh-assinar-erro]");
    var botao = form.querySelector("[data-rh-assinar-botao]");
    var campoCpf = form.querySelector("[name=cpf]");
    var tracos = [];
    var atual = null;

    /* ---------------- o quadro ---------------- */
    function contexto() {
      var ctx = canvas.getContext("2d");
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.lineWidth = 2.6 * (window.devicePixelRatio || 1);
      ctx.strokeStyle = getComputedStyle(form).getPropertyValue("--tinta-folha").trim() ||
        getComputedStyle(document.body).color || "currentColor";
      return ctx;
    }
    function medir() {
      var escala = window.devicePixelRatio || 1;
      var caixa = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(caixa.width * escala));
      canvas.height = Math.max(1, Math.round(caixa.height * escala));
      redesenhar();
    }
    function redesenhar() {
      var ctx = contexto();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      tracos.forEach(function (traco) { desenhar(ctx, traco); });
      quadro.classList.toggle("tem-traco", tracos.length > 0);
    }
    function desenhar(ctx, traco) {
      if (!traco.length) return;
      ctx.beginPath();
      ctx.moveTo(traco[0][0] * canvas.width, traco[0][1] * canvas.height);
      for (var i = 1; i < traco.length; i += 1) ctx.lineTo(traco[i][0] * canvas.width, traco[i][1] * canvas.height);
      if (traco.length === 1) ctx.lineTo(traco[0][0] * canvas.width + 0.5, traco[0][1] * canvas.height);
      ctx.stroke();
    }
    function ponto(evento) {
      var caixa = canvas.getBoundingClientRect();
      return [(evento.clientX - caixa.left) / caixa.width, (evento.clientY - caixa.top) / caixa.height];
    }
    canvas.addEventListener("pointerdown", function (evento) {
      evento.preventDefault();
      canvas.setPointerCapture(evento.pointerId);
      atual = [ponto(evento)];
      tracos.push(atual);
      redesenhar();
    });
    canvas.addEventListener("pointermove", function (evento) {
      if (!atual) return;
      var lista = evento.getCoalescedEvents ? evento.getCoalescedEvents() : [evento];
      lista.forEach(function (e) { atual.push(ponto(e)); });
      redesenhar();
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (nome) {
      canvas.addEventListener(nome, function () { atual = null; });
    });
    form.querySelector("[data-rh-desfazer]").addEventListener("click", function () { tracos.pop(); redesenhar(); });
    form.querySelector("[data-rh-limpar]").addEventListener("click", function () { tracos = []; redesenhar(); });
    window.addEventListener("resize", medir);
    medir();

    function pngDoQuadro() {
      var largura = Math.min(1000, canvas.width);
      var altura = Math.round(canvas.height * (largura / canvas.width));
      var saida = document.createElement("canvas");
      saida.width = largura;
      saida.height = altura;
      var ctx = saida.getContext("2d");
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.lineWidth = 3.2;
      ctx.strokeStyle = "rgb(20,18,26)";
      tracos.forEach(function (traco) {
        ctx.beginPath();
        ctx.moveTo(traco[0][0] * largura, traco[0][1] * altura);
        for (var i = 1; i < traco.length; i += 1) ctx.lineTo(traco[i][0] * largura, traco[i][1] * altura);
        if (traco.length === 1) ctx.lineTo(traco[0][0] * largura + 1, traco[0][1] * altura);
        ctx.stroke();
      });
      return saida.toDataURL("image/png");
    }

    /* ---------------- o CPF (máscara, também sem o painel) ---------------- */
    if (campoCpf && !window.Painel) {
      campoCpf.addEventListener("input", function () {
        var d = campoCpf.value.replace(/\D/g, "").slice(0, 11);
        campoCpf.value = d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
          .replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
      });
    }

    /* ---------------- o envio ---------------- */
    function erro(texto, campo) {
      caixaErro.textContent = texto;
      caixaErro.hidden = !texto;
      form.querySelectorAll(".tem-erro").forEach(function (el) { el.classList.remove("tem-erro"); });
      if (campo) {
        var mapa = { nome: "[name=nome]", documento: "[name=cpf]", concordo: "[name=concordo]", assinatura: "[data-rh-quadro]" };
        var alvo = form.querySelector(mapa[campo] || "");
        var bloco = alvo && alvo.closest(".rh-campo, .rh-consentimento");
        if (bloco) bloco.classList.add("tem-erro");
        if (alvo && alvo.focus) alvo.focus({ preventScroll: false });
      }
      if (texto) {
        caixaErro.scrollIntoView({ block: "center", behavior: "smooth" });
        if (window.LSAviso) window.LSAviso.toast({ nivel: "erro", titulo: "Assinatura não enviada", texto: texto });
      }
    }

    form.addEventListener("submit", function (evento) {
      evento.preventDefault();
      var nome = (form.querySelector("[name=nome]").value || "").trim().split(/\s+/).filter(function (p) { return p.replace(/\./g, "").length >= 2; });
      if (nome.length < 2) return erro("Escreva o nome completo (nome e sobrenome).", "nome");
      if ((campoCpf.value || "").replace(/\D/g, "").length !== 11) return erro("O CPF tem 11 números.", "documento");
      if (!tracos.length) return erro("Assine no quadro com o dedo (ou o mouse).", "assinatura");
      if (!form.querySelector("[name=concordo]").checked) return erro("Marque “Li e concordo” para assinar.", "concordo");
      erro("");
      campoPng.value = pngDoQuadro();
      botao.disabled = true;
      var rotulo = botao.innerHTML;
      botao.textContent = "Enviando…";
      fetch(form.getAttribute("action") || window.location.pathname, {
        method: "POST",
        body: new FormData(form),
        headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin"
      }).then(function (resposta) {
        return resposta.json().catch(function () { return { ok: false, msg: "O servidor não respondeu direito. Tente de novo." }; });
      }).then(function (json) {
        if (json && json.ok) {
          window.location.assign(json.destino || window.location.href);
          return;
        }
        botao.disabled = false;
        botao.innerHTML = rotulo;
        erro((json && json.msg) || "Não foi possível assinar agora.", json && json.campo);
      }).catch(function () {
        botao.disabled = false;
        botao.innerHTML = rotulo;
        erro("A conexão caiu antes de o servidor responder. Nada foi gravado: confira a internet e toque em assinar de novo.");
      });
    });
  }

  /* ---------------- o relógio do link (página sem login) ---------------- */
  function relogio() {
    var caixa = document.querySelector("[data-rh-relogio-pub]");
    if (!caixa) return;
    var texto = caixa.querySelector("span");
    var fim = Date.now() + (parseInt(caixa.getAttribute("data-restante"), 10) || 0) * 1000;
    var botao = document.querySelector("[data-rh-assinar-botao]");
    function pintar() {
      var resta = Math.max(0, Math.round((fim - Date.now()) / 1000));
      texto.textContent = resta >= 3600
        ? Math.floor(resta / 3600) + "h" + ("0" + Math.floor((resta % 3600) / 60)).slice(-2)
        : Math.floor(resta / 60) + ":" + ("0" + (resta % 60)).slice(-2);
      if (resta === 0) {
        caixa.classList.add("acabou");
        texto.textContent = "Link expirado: peça um novo";
        if (botao) botao.disabled = true;
        return false;
      }
      return true;
    }
    if (pintar()) {
      var tique = setInterval(function () { if (!pintar()) clearInterval(tique); }, 1000);
    }
  }

  if (window.LSTela) window.LSTela.pronto(iniciar);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
  relogio();
})();
