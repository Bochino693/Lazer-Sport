/* Receber aviso da loja no celular.
 *
 * O BOTÃO SÓ APARECE QUANDO ELE PODE FUNCIONAR. Três coisas precisam
 * ser verdade, e cada uma esconde o botão quando não é:
 *
 *   1. o navegador tem service worker e Push -- todo Android moderno tem;
 *   2. a hospedagem tem a chave da aplicação configurada;
 *   3. no IPHONE, a loja precisa estar ADICIONADA À TELA DE INÍCIO. A
 *      Apple não entrega notificação para site aberto no Safari, e essa
 *      é a diferença que mais confunde -- a pessoa acha que o aplicativo
 *      está com defeito. Por isso, no iPhone fora da tela de início, o
 *      texto explica o que fazer em vez de sumir calado.
 *
 * Botão que não faz nada é pior que botão nenhum.
 *
 * A permissão do navegador só pode ser pedida dentro de um clique -- é
 * por isso que existe um botão, e não um pedido automático ao abrir, que
 * aliás o navegador recusaria e alguns bloqueiam o site depois.
 */
(function (window, document) {
  "use strict";

  var caixa = document.querySelector("[data-app-avisos]");
  if (!caixa) return;

  var botao = caixa.querySelector("[data-app-avisos-botao]");
  var nota = caixa.querySelector("[data-app-avisos-nota]");
  var ROTA = caixa.dataset.appAvisosUrl || "/aplicativo/avisos/aparelho/";
  var inscricaoAtual = null;
  var chaveDoServidor = "";

  function recado(texto, mostrarBotao) {
    if (nota) {
      nota.textContent = texto || "";
      nota.hidden = !texto;
    }
    if (botao) botao.hidden = !mostrarBotao;
    caixa.hidden = !texto && !mostrarBotao;
  }

  function ehIphone() {
    return (
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent))
    );
  }

  function naTelaDeInicio() {
    return (
      window.navigator.standalone === true ||
      (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches)
    );
  }

  function plataforma() {
    if (ehIphone()) return "ios";
    if (/Android/i.test(navigator.userAgent)) return "android";
    return "outro";
  }

  /* base64url -> Uint8Array. É o formato em que a chave da aplicação
     viaja e o único que `subscribe` aceita. */
  function chaveEmBytes(base64) {
    var completo = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    var cru = window.atob(completo);
    var bytes = new Uint8Array(cru.length);
    for (var i = 0; i < cru.length; i += 1) bytes[i] = cru.charCodeAt(i);
    return bytes;
  }

  function csrf() {
    var campo = document.querySelector("[name=csrfmiddlewaretoken]");
    if (campo) return campo.value;
    var achado = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return achado ? decodeURIComponent(achado[2]) : "";
  }

  function contarAoServidor(inscricao, cancelar) {
    var dados = new FormData();
    var bruto = inscricao.toJSON();
    dados.set("endpoint", bruto.endpoint);
    if (cancelar) {
      dados.set("acao", "cancelar");
    } else {
      dados.set("p256dh", (bruto.keys && bruto.keys.p256dh) || "");
      dados.set("auth", (bruto.keys && bruto.keys.auth) || "");
      dados.set("plataforma", plataforma());
      dados.set("aparelho", navigator.userAgent.slice(0, 120));
    }
    dados.set("csrfmiddlewaretoken", csrf());

    return window.fetch(ROTA, {
      method: "POST",
      body: dados,
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    }).then(function (resposta) {
      return resposta.ok;
    });
  }

  function pintar(inscrito) {
    inscricaoAtual = inscrito ? inscricaoAtual : null;
    if (!botao) return;
    var forte = botao.querySelector("strong");
    var fraco = botao.querySelector("small");
    if (forte) {
      forte.textContent = inscrito
        ? "Avisos ligados neste celular"
        : "Receber avisos no celular";
    }
    if (fraco) {
      fraco.textContent = inscrito ? "Tocar para desligar" : "Promoções e novidades";
    }
    botao.classList.toggle("ativo", Boolean(inscrito));
  }

  function ligar() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      return; // navegador sem push: a caixa fica escondida, e ponto.
    }
    if (ehIphone() && !naTelaDeInicio()) {
      recado(
        "No iPhone, adicione a loja à tela de início (Compartilhar → " +
        "Adicionar à Tela de Início) para receber os avisos.",
        false
      );
      return;
    }

    window.fetch(ROTA, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (dados) {
        if (!dados || !dados.configurado || !dados.chave) return;
        chaveDoServidor = dados.chave;
        return navigator.serviceWorker.register("/app-sw.js", { scope: "/" });
      })
      .then(function (registro) {
        if (!registro) return null;
        return registro.pushManager.getSubscription();
      })
      .then(function (inscricao) {
        if (chaveDoServidor === "") return;
        inscricaoAtual = inscricao || null;
        pintar(Boolean(inscricao));
        recado("", true);
      })
      .catch(function () {
        /* Silêncio de propósito: um push indisponível não pode virar
           erro na tela de quem só queria ver o catálogo. */
      });
  }

  botao && botao.addEventListener("click", function () {
    botao.disabled = true;

    var acao = inscricaoAtual
      ? Promise.resolve(inscricaoAtual).then(function (inscricao) {
          return contarAoServidor(inscricao, true).then(function () {
            return inscricao.unsubscribe();
          }).then(function () {
            pintar(false);
            recado("Você não vai mais receber avisos neste celular.", true);
          });
        })
      : Notification.requestPermission().then(function (resposta) {
          if (resposta !== "granted") {
            recado(
              "A permissão foi recusada. Para receber avisos, libere as " +
              "notificações deste site nas configurações do navegador.",
              true
            );
            return null;
          }
          return navigator.serviceWorker.ready.then(function (registro) {
            return registro.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: chaveEmBytes(chaveDoServidor),
            });
          }).then(function (inscricao) {
            inscricaoAtual = inscricao;
            return contarAoServidor(inscricao, false);
          }).then(function (guardou) {
            pintar(Boolean(guardou));
            recado(
              guardou
                ? "Pronto: as novidades da loja chegam aqui."
                : "Não consegui guardar a inscrição. Tente de novo em instantes.",
              true
            );
          });
        });

    acao.catch(function () {
      recado("Não foi possível ligar os avisos agora. Tente mais tarde.", true);
    }).then(function () {
      botao.disabled = false;
    });
  });

  ligar();
})(window, document);
