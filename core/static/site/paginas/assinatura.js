/* O termo de compra assinado no telefone (LEIA-ME-V10, seção 81).

   Três peças, todas nesta página e sem biblioteca:

   1. O RELÓGIO do link. O servidor diz quantos segundos faltam
      (`data-restante`); a conta é feita contra o relógio DESTE aparelho a
      partir daí, então um celular com a hora errada não ganha nem perde
      tempo. Acabou: o botão para e a folha "O tempo do link acabou" sobe.
      O servidor confere de novo no envio -- o relógio da tela é aviso, a
      regra é a de lá.

   2. O QUADRO de assinar. Eventos de ponteiro (dedo, caneta e mouse com o
      mesmo código), `touch-action:none` para o dedo não rolar a página,
      os pontos intermediários (`getCoalescedEvents`) para o traço sair
      liso, e cada traço guardado à parte: é isso que permite "Desfazer" e
      redesenhar quando a tela gira. A imagem que vai ao servidor é um PNG
      de fundo transparente, com no máximo 1000 px de largura.

   3. O ENVIO. Confere na tela o que dá (nome com sobrenome, CPF/CNPJ
      pelos dígitos, "Li e concordo", quadro com traço), confirma numa
      folha que sobe de baixo e manda por fetch, com o CSRF do formulário.
      O que o servidor recusar volta como aviso, com o campo marcado, e o
      traço continua no quadro.
*/
(function () {
  "use strict";

  /* ------------------------------------------------------------ avisos */
  function aviso(texto, tipo) {
    var caixa = document.getElementById("avisosApp");
    if (!caixa || !texto) return;
    var item = document.createElement("div");
    item.className = "aviso-app" + (tipo ? " " + tipo : "");
    item.setAttribute("role", tipo === "erro" ? "alert" : "status");
    var icone = document.createElement("i");
    icone.className = "bi " + (tipo === "erro" ? "bi-exclamation-circle-fill" : tipo === "ok" ? "bi-check-circle-fill" : "bi-info-circle-fill");
    icone.setAttribute("aria-hidden", "true");
    item.appendChild(icone);
    item.appendChild(document.createTextNode(" " + texto));
    caixa.appendChild(item);
    requestAnimationFrame(function () { item.classList.add("aparece"); });
    setTimeout(function () {
      item.classList.remove("aparece");
      setTimeout(function () { item.remove(); }, 300);
    }, 4200);
  }

  /* ------------------------------------------------- baixar (imprimir) */
  var baixar = document.getElementById("baixarPdf");
  if (baixar) {
    baixar.addEventListener("click", function () { window.print(); });
    if (baixar.getAttribute("data-imprimir-ao-abrir") === "1") {
      window.addEventListener("load", function () { setTimeout(function () { window.print(); }, 350); });
    }
  }

  var form = document.getElementById("formAssinatura");
  if (!form) return;

  var folha = document.getElementById("folhaConfirmar");
  var botaoAssinar = document.getElementById("botaoAssinar");
  var campoNome = document.getElementById("campoNome");
  var campoDocumento = document.getElementById("campoDocumento");
  var campoConcordo = document.getElementById("campoConcordo");
  var acabou = false;

  /* ----------------------------------------------------- a folha de baixo */
  function abrirFolha(passo) {
    folha.hidden = false;
    folha.querySelectorAll("[data-passo]").forEach(function (parte) {
      parte.hidden = parte.getAttribute("data-passo") !== passo;
    });
    document.body.style.overflow = "hidden";
    var foco = folha.querySelector("[data-passo='" + passo + "'] .botao-principal, [data-passo='" + passo + "'] .botao-secundario");
    if (foco) setTimeout(function () { foco.focus({ preventScroll: true }); }, 60);
  }
  function fecharFolha() {
    if (folha.querySelector("[data-passo='enviando']:not([hidden])")) return;
    folha.hidden = true;
    document.body.style.overflow = "";
  }
  folha.addEventListener("click", function (evento) {
    if (evento.target.closest("[data-fechar]")) fecharFolha();
  });
  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && !folha.hidden) fecharFolha();
  });

  /* ------------------------------------------------------------ relógio */
  var relogio = document.getElementById("relogio");
  var relogioTexto = document.getElementById("relogioTexto");
  var relogioArco = document.getElementById("relogioArco");
  var validade = (parseInt(relogio.getAttribute("data-validade"), 10) || 5) * 60;
  var fim = Date.now() + (parseInt(relogio.getAttribute("data-restante"), 10) || 0) * 1000;

  function pintarRelogio() {
    var resta = Math.max(0, Math.round((fim - Date.now()) / 1000));
    var min = Math.floor(resta / 60);
    var seg = resta % 60;
    relogioTexto.textContent = min + ":" + (seg < 10 ? "0" : "") + seg;
    relogioArco.style.strokeDashoffset = String(100 - Math.min(100, (resta / validade) * 100));
    relogio.classList.toggle("pouco", resta > 0 && resta <= 60);
    relogio.classList.toggle("acabou", resta === 0);
    relogio.setAttribute("aria-label", resta ? "Faltam " + min + " minutos e " + seg + " segundos" : "Link expirado");
    if (resta === 0 && !acabou) {
      acabou = true;
      botaoAssinar.disabled = true;
      botaoAssinar.innerHTML = '<i class="bi bi-hourglass-bottom" aria-hidden="true"></i> Link expirado';
      abrirFolha("expirou");
    }
    return resta;
  }
  pintarRelogio();
  var tique = setInterval(function () {
    if (pintarRelogio() === 0) clearInterval(tique);
  }, 1000);

  /* --------------------------------- o que já foi digitado neste aparelho */
  var chaveRascunho = "ls-assinatura-" + form.getAttribute("data-documento");
  try {
    var guardado = JSON.parse(sessionStorage.getItem(chaveRascunho) || "{}");
    if (guardado.nome && !campoNome.value) campoNome.value = guardado.nome;
    if (guardado.documento && !campoDocumento.value) campoDocumento.value = guardado.documento;
  } catch (erro) { /* armazenamento bloqueado: segue sem */ }
  function guardarRascunho() {
    try {
      sessionStorage.setItem(chaveRascunho, JSON.stringify({ nome: campoNome.value, documento: campoDocumento.value }));
    } catch (erro) { /* sem armazenamento, sem rascunho */ }
  }

  /* ------------------------------------------------------- CPF / CNPJ */
  function digitos(texto) { return (texto || "").replace(/\D/g, ""); }
  function mascarar(texto) {
    var d = digitos(texto).slice(0, 14);
    if (d.length <= 11) {
      return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
    }
    return d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
  }
  function dv(numeros, pesos) {
    var soma = 0;
    for (var i = 0; i < pesos.length; i += 1) soma += numeros[i] * pesos[i];
    var resto = soma % 11;
    return resto < 2 ? 0 : 11 - resto;
  }
  function cpfValido(d) {
    if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
    var n = d.split("").map(Number);
    var a = dv(n, [10, 9, 8, 7, 6, 5, 4, 3, 2]);
    var b = dv(n.slice(0, 9).concat(a), [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]);
    return n[9] === a && n[10] === b;
  }
  function cnpjValido(d) {
    if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
    var n = d.split("").map(Number);
    var a = dv(n, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
    var b = dv(n.slice(0, 12).concat(a), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
    return n[12] === a && n[13] === b;
  }
  campoDocumento.addEventListener("input", function () {
    // O CNPJ alfanumérico (2026) tem letras: aí a máscara sai do caminho.
    if (!/[A-Za-z]/.test(campoDocumento.value)) campoDocumento.value = mascarar(campoDocumento.value);
    marcar("documento", false);
    guardarRascunho();
  });
  campoNome.addEventListener("input", function () { marcar("nome", false); guardarRascunho(); });
  campoConcordo.addEventListener("change", function () { marcar("concordo", false); });

  function marcar(campo, comErro) {
    var alvo = form.querySelector("[data-campo='" + campo + "']");
    if (alvo) alvo.classList.toggle("com-erro", Boolean(comErro));
  }

  /* --------------------------------------------------------- o quadro */
  var area = document.getElementById("quadroArea");
  var canvas = document.getElementById("quadroAssinatura");
  var ctx = canvas.getContext("2d");
  var botaoDesfazer = document.getElementById("desfazerTraco");
  var botaoLimpar = document.getElementById("limparQuadro");
  var tracos = [];
  var atual = null;
  var TINTA = "#0b1b4d";

  function medir() {
    var caixa = area.getBoundingClientRect();
    var escala = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(caixa.width * escala));
    canvas.height = Math.max(1, Math.round(caixa.height * escala));
    ctx.setTransform(escala, 0, 0, escala, 0, 0);
    redesenhar(ctx);
  }

  /* Os pontos são guardados em fração do quadro (0..1): girar o telefone
     ou mudar a largura redesenha o mesmo traço no tamanho novo. */
  function ponto(evento) {
    var caixa = canvas.getBoundingClientRect();
    return {
      x: (evento.clientX - caixa.left) / caixa.width,
      y: (evento.clientY - caixa.top) / caixa.height,
      p: evento.pressure && evento.pointerType === "pen" ? evento.pressure : 0.5,
    };
  }

  function desenharTraco(c, traco, largura, altura) {
    if (!traco.length) return;
    c.strokeStyle = TINTA;
    c.fillStyle = TINTA;
    c.lineCap = "round";
    c.lineJoin = "round";
    var base = Math.max(2, Math.min(largura, altura * 2.4) / 160);
    if (traco.length === 1) {
      c.beginPath();
      c.arc(traco[0].x * largura, traco[0].y * altura, base * 0.7, 0, Math.PI * 2);
      c.fill();
      return;
    }
    for (var i = 1; i < traco.length; i += 1) {
      var a = traco[i - 1];
      var b = traco[i];
      var anterior = i > 1 ? traco[i - 2] : a;
      c.lineWidth = base * (0.75 + b.p * 0.6);
      c.beginPath();
      // Curva pelo meio dos segmentos: o traço sai liso, sem os "dentes"
      // que a linha reta ponto a ponto deixa no dedo rápido.
      c.moveTo(((anterior.x + a.x) / 2) * largura, ((anterior.y + a.y) / 2) * altura);
      c.quadraticCurveTo(a.x * largura, a.y * altura, ((a.x + b.x) / 2) * largura, ((a.y + b.y) / 2) * altura);
      c.stroke();
    }
  }

  function redesenhar(c, largura, altura) {
    var caixa = area.getBoundingClientRect();
    largura = largura || caixa.width;
    altura = altura || caixa.height;
    c.clearRect(0, 0, largura, altura);
    tracos.forEach(function (traco) { desenharTraco(c, traco, largura, altura); });
    if (atual) desenharTraco(c, atual, largura, altura);
  }

  function atualizarBotoes() {
    var tem = tracos.length > 0;
    botaoDesfazer.disabled = !tem;
    botaoLimpar.disabled = !tem;
    area.classList.toggle("com-traco", tem || Boolean(atual));
  }

  canvas.addEventListener("pointerdown", function (evento) {
    if (acabou || evento.button > 0) return;
    evento.preventDefault();
    canvas.setPointerCapture(evento.pointerId);
    atual = [ponto(evento)];
    marcar("assinatura", false);
    atualizarBotoes();
    redesenhar(ctx);
  });
  canvas.addEventListener("pointermove", function (evento) {
    if (!atual) return;
    evento.preventDefault();
    var lista = evento.getCoalescedEvents ? evento.getCoalescedEvents() : [evento];
    if (!lista.length) lista = [evento];
    lista.forEach(function (e) { atual.push(ponto(e)); });
    redesenhar(ctx);
  });
  function terminar() {
    if (!atual) return;
    tracos.push(atual);
    atual = null;
    atualizarBotoes();
    redesenhar(ctx);
  }
  canvas.addEventListener("pointerup", terminar);
  canvas.addEventListener("pointercancel", terminar);
  canvas.addEventListener("lostpointercapture", terminar);

  botaoDesfazer.addEventListener("click", function () {
    tracos.pop();
    atualizarBotoes();
    redesenhar(ctx);
  });
  botaoLimpar.addEventListener("click", function () {
    tracos = [];
    atualizarBotoes();
    redesenhar(ctx);
  });

  var esperaMedida = null;
  window.addEventListener("resize", function () {
    clearTimeout(esperaMedida);
    esperaMedida = setTimeout(medir, 120);
  });
  medir();

  /* Comprimento total do traço, em px da tela: um toque sem querer não é
     assinatura. */
  function comprimento() {
    var caixa = area.getBoundingClientRect();
    var total = 0;
    tracos.forEach(function (traco) {
      for (var i = 1; i < traco.length; i += 1) {
        total += Math.hypot((traco[i].x - traco[i - 1].x) * caixa.width, (traco[i].y - traco[i - 1].y) * caixa.height);
      }
    });
    return total;
  }

  function imagemDaAssinatura() {
    var caixa = area.getBoundingClientRect();
    var escala = Math.min(2, 1000 / Math.max(1, caixa.width));
    var saida = document.createElement("canvas");
    saida.width = Math.round(caixa.width * escala);
    saida.height = Math.round(caixa.height * escala);
    var c = saida.getContext("2d");
    c.setTransform(escala, 0, 0, escala, 0, 0);
    redesenhar(c, caixa.width, caixa.height);
    return saida.toDataURL("image/png");
  }

  /* ---------------------------------------------------------- o envio */
  function conferir() {
    var nome = campoNome.value.trim().replace(/\s+/g, " ");
    var palavras = nome.split(" ").filter(function (p) { return p.replace(/\./g, "").length >= 2; });
    if (palavras.length < 2) return { campo: "nome", msg: "Escreva o nome completo (nome e sobrenome).", alvo: campoNome };
    var bruto = campoDocumento.value.trim();
    var d = digitos(bruto);
    var alfanumerico = /[A-Za-z]/.test(bruto);
    if (!alfanumerico && !(d.length === 11 ? cpfValido(d) : cnpjValido(d))) {
      return { campo: "documento", msg: (d.length === 14 ? "CNPJ" : d.length === 11 ? "CPF" : "CPF ou CNPJ") + " inválido. Confira os números.", alvo: campoDocumento };
    }
    if (!campoConcordo.checked) return { campo: "concordo", msg: "Marque “Li e concordo” para assinar.", alvo: campoConcordo };
    if (!tracos.length || comprimento() < 40) return { campo: "assinatura", msg: "Assine no quadro com o dedo antes de enviar.", alvo: area };
    return null;
  }

  function mostrarErro(problema) {
    marcar(problema.campo, true);
    aviso(problema.msg, "erro");
    var alvo = problema.alvo || form.querySelector("[data-campo='" + problema.campo + "']");
    if (alvo) {
      alvo.scrollIntoView({ behavior: "smooth", block: "center" });
      if (alvo.focus && alvo.tagName === "INPUT" && alvo.type !== "checkbox") setTimeout(function () { alvo.focus({ preventScroll: true }); }, 250);
    }
  }

  form.addEventListener("submit", function (evento) {
    evento.preventDefault();
    if (acabou) { abrirFolha("expirou"); return; }
    var problema = conferir();
    if (problema) { mostrarErro(problema); return; }
    document.getElementById("confirmarNome").textContent = campoNome.value.trim().replace(/\s+/g, " ");
    document.getElementById("confirmarDocumento").textContent = campoDocumento.value.trim();
    document.getElementById("confirmarImagem").src = imagemDaAssinatura();
    abrirFolha("confirmar");
  });

  var enviando = false;
  document.getElementById("confirmarEnviar").addEventListener("click", function () {
    if (enviando) return;
    if (acabou) { abrirFolha("expirou"); return; }
    enviando = true;
    var dados = new FormData(form);
    dados.set("nome", campoNome.value.trim().replace(/\s+/g, " "));
    dados.set("concordo", campoConcordo.checked ? "1" : "");
    dados.set("assinatura", imagemDaAssinatura());
    abrirFolha("enviando");

    fetch(window.location.href, {
      method: "POST",
      body: dados,
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    }).then(function (resposta) {
      return resposta.json().catch(function () { return { ok: false, msg: "O servidor não respondeu como esperado. Tente de novo." }; });
    }).then(function (corpo) {
      enviando = false;
      if (corpo.ok) {
        try { sessionStorage.removeItem(chaveRascunho); } catch (erro) { /* tanto faz */ }
        window.location.replace(corpo.destino);
        return;
      }
      if (corpo.destino) { window.location.replace(corpo.destino); return; }
      folha.querySelector("[data-passo='enviando']").hidden = true;
      if (corpo.situacao === "expirado") {
        acabou = true;
        fim = Date.now();
        pintarRelogio();
        abrirFolha("expirou");
        return;
      }
      fecharFolha();
      folha.hidden = true;
      document.body.style.overflow = "";
      if (corpo.campo) {
        mostrarErro({ campo: corpo.campo, msg: corpo.msg });
      } else {
        aviso(corpo.msg || "Não deu para assinar agora. Tente de novo.", "erro");
      }
    }).catch(function () {
      enviando = false;
      folha.querySelector("[data-passo='enviando']").hidden = true;
      folha.hidden = true;
      document.body.style.overflow = "";
      aviso("Sem conexão. Confira a internet e toque em Assinar de novo.", "erro");
    });
  });
})();
