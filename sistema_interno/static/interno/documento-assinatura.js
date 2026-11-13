/* O cartão do documento de assinatura (LEIA-ME-V10, seção 81).

   O pedido: "um link que vai ser gerado a cada 5 minutos, para o usuário
   assinar, com validações de tempo e tudo". O cartão faz isso sozinho:

     * ao abrir, pede um link (POST): o QR, o endereço e o anel do relógio;
     * o anel esvazia em 5 minutos e, quando zera, pede outro -- só com a
       tela à vista: aba escondida não gera link que ninguém vai mostrar;
     * "Gerar novo link" pede na hora; "Enviar no WhatsApp" pede um link
       fresco para o cliente receber os 5 minutos inteiros;
     * a cada 10 segundos pergunta se o cliente já assinou (GET leve), e
       troca o QR pelo "Assinado por ..." com o PDF -- sem recarregar.

   O painel troca de tela sem recarregar a página (ls-soft-navigation.js):
   este script roda de novo a cada visita. Por isso os relógios da visita
   anterior são parados aqui no começo, e cada um se desliga sozinho
   quando o cartão sai da tela.
*/
(function () {
  "use strict";

  if (window.LSDocAssinatura && window.LSDocAssinatura.parar) window.LSDocAssinatura.parar();

  var raiz = document.getElementById("docAssinatura");
  if (!raiz) return;

  var URL_PAGINA = raiz.getAttribute("data-url-pagina");
  var URL_LINK = raiz.getAttribute("data-url-link");
  var URL_ESTADO = raiz.getAttribute("data-url-estado");
  var folha = document.getElementById("docAssinaturaFolha");

  var link = "";
  var expira = 0;           // em ms do relógio DESTE navegador
  var validade = 300;       // segundos
  var pedindo = null;       // a promessa do link em voo
  var ultimaResposta = null;
  var relogio = null;
  var sondagem = null;
  var esperarAte = 0;       // depois de uma falha, o pedido automático espera

  /* --------------------------------------------------------- utilidades */
  function aviso(texto, tipo) {
    if (window.Painel && window.Painel.aviso) { window.Painel.aviso(texto, tipo); return; }
    var tarja = document.createElement("div");
    tarja.className = "ls-tarja" + (tipo ? " " + tipo : "");
    tarja.setAttribute("role", "status");
    tarja.textContent = texto;
    document.body.appendChild(tarja);
    requestAnimationFrame(function () { tarja.classList.add("aparece"); });
    setTimeout(function () { tarja.classList.remove("aparece"); setTimeout(function () { tarja.remove(); }, 260); }, 2600);
  }

  function csrf() {
    var campo = raiz.querySelector("input[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function postar(url, dados) {
    var corpo = new FormData();
    Object.keys(dados || {}).forEach(function (chave) { corpo.append(chave, dados[chave]); });
    var opcoes = {
      method: "POST",
      body: corpo,
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() },
    };
    var envio = window.Painel && window.Painel.rede ? window.Painel.rede.post(url, opcoes) : fetch(url, opcoes);
    return envio.then(lerJson);
  }

  function lerJson(resposta) {
    return resposta.json().catch(function () { return {}; }).then(function (corpo) {
      if (!resposta.ok || corpo.status !== "sucesso") {
        var erro = new Error(corpo.msg || "Não deu certo agora. Tente de novo em instantes.");
        erro.corpo = corpo;
        throw erro;
      }
      return corpo;
    });
  }

  function cartao() { return raiz.querySelector("[data-doc-cartao]"); }
  function situacao() { var c = cartao(); return c ? c.getAttribute("data-situacao") : ""; }
  function noAr() { return document.body.contains(raiz); }

  /* ------------------------------------------------------------- o link */
  function pedirLink() {
    if (situacao() !== "aguardando") return Promise.reject(new Error("Sem documento aguardando assinatura."));
    if (pedindo) return pedindo;
    var qr = raiz.querySelector("[data-doc-qr]");
    if (qr) qr.setAttribute("aria-busy", "true");
    pedindo = postar(URL_LINK).then(function (corpo) {
      pedindo = null;
      ultimaResposta = corpo;
      link = corpo.link;
      validade = corpo.validade || 300;
      // O prazo vem no relógio do servidor; a diferença entre os dois
      // relógios sai da conta aqui.
      expira = Date.now() + (corpo.expira_em - corpo.agora);
      pintarLink(corpo);
      tique();
      return corpo;
    }, function (erro) {
      pedindo = null;
      // Rede fora ou servidor recusando: o anel zerado não pode virar um
      // pedido por segundo. A próxima tentativa sozinha espera 15 s.
      esperarAte = Date.now() + 15000;
      if (erro.corpo && erro.corpo.situacao && erro.corpo.situacao !== situacao()) consultarEstado(true);
      throw erro;
    });
    return pedindo;
  }

  function pintarLink(corpo) {
    var qr = raiz.querySelector("[data-doc-qr]");
    if (qr) {
      qr.innerHTML = corpo.qr;
      qr.setAttribute("aria-busy", "false");
      qr.classList.remove("velho");
      qr.classList.add("novo");
      setTimeout(function () { qr.classList.remove("novo"); }, 700);
    }
    var campo = raiz.querySelector("[data-doc-link]");
    if (campo) campo.value = corpo.link;
    var numero = raiz.querySelector("[data-doc-numero]");
    if (numero) numero.textContent = "Link nº " + corpo.numero + " · renova sozinho a cada " + Math.round(validade / 60) + " minutos";
  }

  function tique() {
    if (!noAr()) { parar(); return; }
    var anel = raiz.querySelector("[data-doc-arco]");
    var tempo = raiz.querySelector("[data-doc-tempo]");
    var caixa = raiz.querySelector("[data-doc-relogio]");
    if (!anel || !tempo || !expira) return;
    var resta = Math.max(0, Math.round((expira - Date.now()) / 1000));
    var min = Math.floor(resta / 60);
    var seg = resta % 60;
    tempo.textContent = min + ":" + (seg < 10 ? "0" : "") + seg;
    anel.style.strokeDashoffset = String(100 - Math.min(100, (resta / validade) * 100));
    caixa.classList.toggle("pouco", resta > 0 && resta <= 60);
    caixa.classList.toggle("acabou", resta === 0);
    caixa.setAttribute("aria-label", "O link expira em " + min + " minutos e " + seg + " segundos");
    if (resta === 0) {
      var qr = raiz.querySelector("[data-doc-qr]");
      if (qr) qr.classList.add("velho");
      // A cada 5 minutos, um link novo -- com a tela à vista.
      if (document.visibilityState === "visible" && !pedindo && Date.now() >= esperarAte) {
        pedirLink().catch(function () { /* a sondagem conta o que mudou */ });
      }
    }
  }

  /* ---------------------------------------------------- já assinou? */
  function consultarEstado(forcar) {
    if (!noAr()) { parar(); return; }
    if (!forcar && document.visibilityState !== "visible") return;
    var c = cartao();
    var url = URL_ESTADO + "?documento=" + encodeURIComponent(c ? c.getAttribute("data-documento") : "")
      + "&situacao=" + encodeURIComponent(situacao());
    fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" }, cache: "no-store" })
      .then(lerJson)
      .then(function (corpo) {
        if (!corpo.mudou || !noAr()) return;
        trocar(corpo);
        if (corpo.assinado && corpo.msg) aviso(corpo.msg, "ok");
      })
      .catch(function () { /* rede fora: tenta na próxima volta */ });
  }

  function trocar(corpo) {
    var atual = cartao();
    if (atual && corpo.html) {
      var molde = document.createElement("div");
      molde.innerHTML = corpo.html.trim();
      atual.replaceWith(molde.firstElementChild);
    }
    var resumo = document.getElementById("docAssinaturaResumo");
    if (resumo && corpo.resumo) {
      var outro = document.createElement("div");
      outro.innerHTML = corpo.resumo.trim();
      resumo.replaceWith(outro.firstElementChild);
    }
    link = "";
    expira = 0;
    if (situacao() === "aguardando") pedirLink().catch(function (erro) { aviso(erro.message, "erro"); });
  }

  /* ------------------------------------------------------- a folha */
  var acaoDaFolha = null;
  function abrirFolha(opcoes) {
    acaoDaFolha = opcoes.acao;
    folha.querySelector("[data-doc-folha-titulo]").textContent = opcoes.titulo;
    folha.querySelector("[data-doc-folha-texto]").textContent = opcoes.texto;
    var botao = folha.querySelector("[data-doc-confirmar]");
    botao.textContent = opcoes.botao;
    botao.className = "btn btn-lg w-100 " + (opcoes.perigo ? "btn-warning" : "btn-success");
    botao.disabled = false;
    folha.hidden = false;
    requestAnimationFrame(function () { folha.classList.add("aberta"); });
    setTimeout(function () { botao.focus({ preventScroll: true }); }, 80);
  }
  function fecharFolha() {
    folha.classList.remove("aberta");
    setTimeout(function () { folha.hidden = true; }, 220);
    acaoDaFolha = null;
  }
  function aoClicarFolha(evento) {
    if (evento.target.closest("[data-doc-fechar]")) { fecharFolha(); return; }
    var confirmar = evento.target.closest("[data-doc-confirmar]");
    if (!confirmar || !acaoDaFolha) return;
    confirmar.disabled = true;
    confirmar.textContent = "Gerando…";
    var acao = acaoDaFolha;
    acao().then(function () { fecharFolha(); }, function (erro) {
      confirmar.disabled = false;
      fecharFolha();
      aviso(erro.message, "erro");
    });
  }
  function aoTeclar(evento) {
    if (evento.key === "Escape" && !folha.hidden) fecharFolha();
  }
  folha.addEventListener("click", aoClicarFolha);
  document.addEventListener("keydown", aoTeclar);

  function gerar() {
    return postar(URL_PAGINA, { action: "gerar" }).then(function (corpo) {
      trocar(corpo);
      aviso(corpo.msg, "ok");
    });
  }

  /* -------------------------------------------------------- os botões */
  function copiar(texto) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(texto);
    var campo = raiz.querySelector("[data-doc-link]");
    campo.select();
    var ok = document.execCommand && document.execCommand("copy");
    return ok ? Promise.resolve() : Promise.reject(new Error("copiar"));
  }

  function aoClicar(evento) {
    var botao = evento.target.closest("[data-doc-acao]");
    if (!botao || !raiz.contains(botao)) return;
    var acao = botao.getAttribute("data-doc-acao");

    if (acao === "gerar") {
      abrirFolha({
        titulo: "Gerar o documento para assinatura?",
        texto: "O termo de compra é montado com os itens, o total e as condições de pagamento deste orçamento aprovado, e fica congelado: editar o orçamento — ou registrar o pagamento — depois não muda o que o cliente assina.",
        botao: "Gerar documento",
        acao: gerar,
      });
    } else if (acao === "refazer") {
      abrirFolha({
        titulo: "Gerar o documento de novo?",
        texto: "Use quando o orçamento mudou. O documento atual é substituído e todos os links dele deixam de valer na hora — inclusive o que o cliente tiver aberto.",
        botao: "Gerar de novo",
        perigo: true,
        acao: gerar,
      });
    } else if (acao === "renovar") {
      botao.disabled = true;
      pedirLink().then(function () {
        aviso("Link novo gerado: vale 5 minutos a partir de agora.", "ok");
      }, function (erro) { aviso(erro.message, "erro"); }).then(function () { botao.disabled = false; });
    } else if (acao === "copiar") {
      if (!link) return;
      copiar(link).then(function () { aviso("Link copiado. Ele vale até o anel zerar.", "ok"); },
        function () { aviso("Não deu para copiar: segure o dedo sobre o link e copie.", "erro"); });
    } else if (acao === "whatsapp") {
      // A janela abre JÁ, no toque (senão o navegador a bloqueia), e recebe
      // o endereço quando o link fresco chegar.
      var janela = window.open("", "_blank");
      botao.disabled = true;
      pedirLink().then(function (corpo) {
        var destino = corpo.whatsapp || corpo.whatsapp_sem_numero;
        if (!corpo.whatsapp) aviso("O orçamento não tem WhatsApp do cliente: escolha a conversa.", "ok");
        if (janela && !janela.closed) janela.location.href = destino;
        else window.location.href = destino;
      }, function (erro) {
        if (janela) janela.close();
        aviso(erro.message, "erro");
      }).then(function () { botao.disabled = false; });
    }
  }
  raiz.addEventListener("click", aoClicar);

  function aoVoltar() {
    if (document.visibilityState !== "visible") return;
    tique();
    consultarEstado();
  }
  document.addEventListener("visibilitychange", aoVoltar);

  /* -------------------------------------------------------- começar */
  function parar() {
    clearInterval(relogio);
    clearInterval(sondagem);
    document.removeEventListener("keydown", aoTeclar);
    document.removeEventListener("visibilitychange", aoVoltar);
    if (window.LSDocAssinatura && window.LSDocAssinatura.parar === parar) window.LSDocAssinatura = null;
  }
  window.LSDocAssinatura = { parar: parar, pedirLink: pedirLink, estado: consultarEstado, ultima: function () { return ultimaResposta; } };

  relogio = setInterval(tique, 1000);
  sondagem = setInterval(consultarEstado, 10000);
  if (situacao() === "aguardando") {
    pedirLink().catch(function (erro) { aviso(erro.message, "erro"); });
  }
})();
