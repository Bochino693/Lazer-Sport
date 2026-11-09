/* ======================================================================
   QUEM ESTÁ AQUI -- o "estou aqui" das abas dos jogos (core/presenca_jogos.py).

   A cada 30 s (o servidor diz o intervalo na resposta) a aba conta ao site
   que está aberta e, se for a página de um jogo, qual. A resposta já traz a
   conta de todo mundo -- gente online e quantos jogam cada jogo -- e vira o
   evento "ls-presenca" no document, que o portal usa para os números da
   tela (portal-jogos.js). Nada de login, nome ou IP: o aparelho é um número
   sorteado e guardado neste navegador (ls-presenca-aparelho).

   Leve de propósito: com a aba escondida não bate (a conta esquece a aba
   em 75 s); ao voltar, bate na hora; ao fechar, avisa que saiu (sendBeacon,
   que o navegador entrega mesmo com a página indo embora).

   data-jogo: "" no portal (lá vale o jogo aberto dentro do app, LSApp),
   "auto" na página dos jogos da casa (o jogo do endereço, que muda quando
   a pessoa troca de jogo sem recarregar) ou o slug do jogo.
   ====================================================================== */
(function () {
  "use strict";
  var eu = document.currentScript;
  var URL_PRESENCA = eu && eu.getAttribute("data-presenca-url");
  if (!URL_PRESENCA || !window.fetch || !window.JSON) return;
  // navegador controlado por programa não é gente
  if (navigator.webdriver) return;

  var JOGO = eu.getAttribute("data-jogo") || "";
  var NAO_SAO_JOGOS = ["partida", "ranking", "presenca", "abriu", "anuncio", "_acervo"];
  var CHAVE = "ls-presenca-aparelho";

  function sortear(bytes) {
    var lista = new Uint8Array(bytes);
    try { window.crypto.getRandomValues(lista); } catch (e) {
      for (var i = 0; i < bytes; i++) lista[i] = Math.floor(Math.random() * 256);
    }
    return Array.prototype.map.call(lista, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
  }
  // o número do aparelho: o mesmo em todas as abas deste navegador (duas abas = uma pessoa)
  var aparelho = "";
  try { aparelho = localStorage.getItem(CHAVE) || ""; } catch (e) { aparelho = ""; }
  if (!/^[A-Za-z0-9_-]{16,40}$/.test(aparelho)) {
    aparelho = sortear(12);
    try { localStorage.setItem(CHAVE, aparelho); } catch (e) { /* aba anônima: vale só esta aba */ }
  }
  // o número desta aba (o "saí" tira só ela da conta)
  var aba = sortear(6);

  function jogoAgora() {
    if (JOGO === "auto") {
      var achado = location.pathname.match(/^\/jogos\/([a-z0-9-]+)\/(?:emulador\/)?$/);
      return achado && NAO_SAO_JOGOS.indexOf(achado[1]) === -1 ? achado[1] : "";
    }
    if (JOGO) return JOGO;
    // no portal: o jogo aberto por cima da biblioteca, dentro do app
    try { return (window.LSApp && window.LSApp.jogoAberto && window.LSApp.jogoAberto()) || ""; } catch (e) { return ""; }
  }

  var intervalo = 30000;
  var relogio = 0;
  var enviando = false;
  var deNovo = false;  // pediram outra batida enquanto uma estava no caminho
  var api = window.LSPresenca = { ultimo: null, bater: bater };

  function avisar(dados) {
    api.ultimo = dados;
    try { document.dispatchEvent(new CustomEvent("ls-presenca", { detail: dados })); } catch (e) { /* navegador antigo */ }
  }
  function agendar() {
    clearTimeout(relogio);
    if (!document.hidden) relogio = setTimeout(bater, intervalo);
  }
  function bater() {
    clearTimeout(relogio);
    if (document.hidden) return;
    if (enviando) { deNovo = true; return; }
    enviando = true;
    var jogo = jogoAgora();
    // text/plain: o mesmo corpo do "saí" (o sendBeacon manda texto) e sem pergunta prévia ao servidor
    fetch(URL_PRESENCA, {
      method: "POST", credentials: "omit", cache: "no-store",
      headers: { "Content-Type": "text/plain;charset=UTF-8" },
      body: JSON.stringify({ aparelho: aparelho, aba: aba, jogo: jogo }),
    }).then(function (r) {
      if (r.status === 429) intervalo = 60000;
      return r.status === 200 ? r.json() : null;
    }).then(function (d) {
      if (!d) return;
      if (d.intervalo) intervalo = Math.max(15, Math.min(120, Number(d.intervalo) || 30)) * 1000;
      avisar({ online: Number(d.online) || 0, jogando: d.jogando || {}, meu: jogo });
    }).catch(function () { /* sem rede: tenta de novo na próxima */ }).then(function () {
      enviando = false;
      if (deNovo) { deNovo = false; bater(); } else agendar();
    });
  }
  function sair() {
    var corpo = JSON.stringify({ aparelho: aparelho, aba: aba, saiu: true });
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(URL_PRESENCA, corpo)) return;
    } catch (e) { /* segue para o fetch */ }
    try {
      fetch(URL_PRESENCA, { method: "POST", credentials: "omit", keepalive: true, headers: { "Content-Type": "text/plain;charset=UTF-8" }, body: corpo });
    } catch (e) { /* a aba já foi */ }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) clearTimeout(relogio);
    else bater();
  });
  window.addEventListener("pagehide", function () { clearTimeout(relogio); sair(); });
  // voltou do cache de ida e volta (o "voltar" do navegador): a aba conta de novo
  window.addEventListener("pageshow", function (e) { if (e.persisted) bater(); });
  // o portal abriu ou fechou um jogo dentro do app: a conta muda já. Ao fechar, espera o quadro do
  // jogo sair (ele guarda o ponto antes, até 1,5 s, e então manda o "saí" dele)
  document.addEventListener("ls-app-jogo", function (e) { setTimeout(bater, e && e.detail ? 50 : 1800); });

  bater();
})();
