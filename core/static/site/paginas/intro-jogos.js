/* ======================================================================
   A ABERTURA DOS JOGOS: "LAZER & SPORT GAMES apresenta" -> o jogo.

   Três segundos de marca antes da partida, como nas máquinas de verdade
   quando ligam. Vale para os jogos da casa (console.js, antes do 3-2-1) e
   para os que a equipe cadastra (jogo-cadastrado.js, enquanto o jogo
   carrega por baixo -- a espera vira apresentação).

     LSIntroJogos.mostrar(caixa, { titulo, cor, chave }) -> Promise

   - Só na PRIMEIRA partida de cada jogo nesta visita (`chave`): quem toca em
     "jogar de novo" quer jogar, não rever a abertura.
   - Um toque pula.
   - Quem pediu menos movimento ao aparelho vê uma versão parada e curta.
   - O som segue o botão de som dos jogos (ls-jogos-som): desligado lá,
     desligado aqui.
   ====================================================================== */
(function () {
  "use strict";
  var script = document.currentScript;
  var LOGO = (script && script.dataset.logo) || "";
  var vistos = {};
  var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function somLigado() {
    try { return window.localStorage.getItem("ls-jogos-som") !== "0"; } catch (e) { return true; }
  }

  /* O "plim" da abertura: um varrido que sobe e duas notas, feitos na hora
     pelo WebAudio (nada para baixar). Só toca porque a pessoa acabou de
     tocar em Jogar -- sem esse toque o navegador não deixaria. */
  function tocar() {
    if (!somLigado()) return;
    var Contexto = window.AudioContext || window.webkitAudioContext;
    if (!Contexto) return;
    var ctx;
    try { ctx = new Contexto(); } catch (e) { return; }
    var agora = ctx.currentTime;
    var mestre = ctx.createGain();
    mestre.gain.value = 0.16;
    mestre.connect(ctx.destination);
    var sopro = ctx.createOscillator();
    var gs = ctx.createGain();
    sopro.type = "sawtooth";
    sopro.frequency.setValueAtTime(180, agora);
    sopro.frequency.exponentialRampToValueAtTime(1400, agora + 0.55);
    gs.gain.setValueAtTime(0.0001, agora);
    gs.gain.exponentialRampToValueAtTime(0.25, agora + 0.12);
    gs.gain.exponentialRampToValueAtTime(0.0001, agora + 0.6);
    var filtro = ctx.createBiquadFilter();
    filtro.type = "lowpass";
    filtro.frequency.value = 2400;
    sopro.connect(filtro); filtro.connect(gs); gs.connect(mestre);
    sopro.start(agora); sopro.stop(agora + 0.62);
    [[1046.5, 0.62], [1568, 0.86], [2093, 1.1]].forEach(function (nota, i) {
      var o = ctx.createOscillator();
      var g = ctx.createGain();
      o.type = i === 2 ? "sine" : "triangle";
      o.frequency.value = nota[0];
      g.gain.setValueAtTime(0.0001, agora + nota[1]);
      g.gain.exponentialRampToValueAtTime(i === 2 ? 0.5 : 0.7, agora + nota[1] + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, agora + nota[1] + (i === 2 ? 0.9 : 0.45));
      o.connect(g); g.connect(mestre);
      o.start(agora + nota[1]); o.stop(agora + nota[1] + 1);
    });
    setTimeout(function () { try { ctx.close(); } catch (e) { /* nada */ } }, 2600);
  }

  function elemento(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto) el.textContent = texto;
    return el;
  }

  function mostrar(caixa, opcoes) {
    opcoes = opcoes || {};
    var chave = opcoes.chave || opcoes.titulo || "jogo";
    if (!caixa || vistos[chave]) return Promise.resolve(false);
    vistos[chave] = true;

    return new Promise(function (resolve) {
      var tela = elemento("div", "ls-intro" + (reduzido ? " ls-intro--parada" : ""));
      tela.setAttribute("role", "img");
      tela.setAttribute("aria-label", "Lazer & Sport Games apresenta " + (opcoes.titulo || ""));
      if (opcoes.cor) tela.style.setProperty("--cor-intro", opcoes.cor);
      tela.appendChild(elemento("span", "ls-intro-grade"));
      tela.appendChild(elemento("span", "ls-intro-brilho"));
      var centro = elemento("div", "ls-intro-centro");
      if (LOGO) {
        var logo = elemento("span", "ls-intro-logo");
        var img = document.createElement("img");
        img.src = LOGO; img.alt = "";
        logo.appendChild(img);
        centro.appendChild(logo);
      }
      var marca = elemento("strong", "ls-intro-marca");
      marca.appendChild(elemento("span", "", "LAZER & SPORT"));
      marca.appendChild(elemento("b", "", "GAMES"));
      centro.appendChild(marca);
      centro.appendChild(elemento("span", "ls-intro-apresenta", "apresenta"));
      if (opcoes.titulo) centro.appendChild(elemento("span", "ls-intro-titulo", opcoes.titulo));
      tela.appendChild(centro);
      tela.appendChild(elemento("span", "ls-intro-pular", "toque para pular"));
      caixa.appendChild(tela);
      tocar();

      var fechado = false;
      var duracao = reduzido ? 1400 : 3300;
      function fechar(rapido) {
        if (fechado) return;
        fechado = true;
        tela.classList.add("ls-intro--saindo");
        setTimeout(function () { tela.remove(); resolve(true); }, rapido ? 160 : 380);
      }
      var relogio = setTimeout(function () { fechar(false); }, duracao);
      tela.addEventListener("pointerdown", function (e) {
        e.preventDefault();
        clearTimeout(relogio);
        fechar(true);
      });
    });
  }

  window.LSIntroJogos = { mostrar: mostrar };
})();
