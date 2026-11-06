/* ======================================================================
   A ABERTURA DOS JOGOS: "LAZER & SPORT GAMES apresenta" -> o jogo.

   Uns quatro segundos de cinema antes da partida, como nas máquinas de
   verdade quando ligam:
     1. faíscas nas cores da marca correm das bordas para o centro;
     2. IMPACTO: o logo aparece com onda de choque, clarão e o tranco da tela;
     3. "LAZER & SPORT GAMES" entra letra por letra e um brilho passa por cima;
     4. a marca sobe, a CAPA DO JOGO acende ao fundo e o nome do jogo bate na
        tela, com o console embaixo; um clarão leva ao jogo.
   O som é feito na hora pelo WebAudio (nada para baixar): o sopro que sobe,
   o grave do impacto, as notas da marca e o acorde do nome.

   Vale para os jogos da casa (console.js, antes do 3-2-1), para os que a
   equipe cadastra (jogo-cadastrado.js) e para os de console (jogo-emulador.js,
   enquanto o emulador liga por baixo -- a espera vira apresentação).

     LSIntroJogos.mostrar(caixa, { titulo, cor, chave, capa, console }) -> Promise

   - Só na PRIMEIRA partida de cada jogo nesta visita (`chave`).
   - Um toque (ou Enter, Espaço, Esc) pula.
   - Quem pediu menos movimento ao aparelho vê uma versão parada e curta.
   - O som segue o botão de som dos jogos (ls-jogos-som).
   ====================================================================== */
(function () {
  "use strict";
  var script = document.currentScript;
  var LOGO = (script && script.dataset.logo) || "";
  var vistos = {};
  var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var CORES = ["#ff4757", "#2f8bff", "#3fd0ff", "#ffd23f", "#ffffff"];
  // a linha do tempo (segundos); o CSS (intro-jogos.css) segue os mesmos tempos
  var T = { impacto: 0.72, letras: 1.0, nome: 2.45, fim: 4.25 };

  function somLigado() {
    try { return window.localStorage.getItem("ls-jogos-som") !== "0"; } catch (e) { return true; }
  }

  /* O ruído do sopro e do estalo: um segundo de números ao acaso, feito uma vez só (na
     preparação, antes do toque) e não no meio da apresentação. */
  var ruidoGuardado = null;
  function ruidoPronto() {
    if (!ruidoGuardado) {
      ruidoGuardado = new Float32Array(96000);
      for (var i = 0; i < ruidoGuardado.length; i++) ruidoGuardado[i] = Math.random() * 2 - 1;
    }
    return ruidoGuardado;
  }

  /* ---------------------------------------------------------------- o som */
  function tocar() {
    if (!somLigado()) return null;
    var Contexto = window.AudioContext || window.webkitAudioContext;
    if (!Contexto) return null;
    var ctx;
    try { ctx = new Contexto(); } catch (e) { return null; }
    var t0 = ctx.currentTime + 0.02;
    var mestre = ctx.createGain();
    mestre.gain.value = 0.22;
    var comp = ctx.createDynamicsCompressor();
    mestre.connect(comp); comp.connect(ctx.destination);

    var ruido = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    ruido.getChannelData(0).set(ruidoPronto().subarray(0, ctx.sampleRate));
    function sopro(inicio, dur, de, ate, volume) {
      var fonte = ctx.createBufferSource(); fonte.buffer = ruido;
      var filtro = ctx.createBiquadFilter(); filtro.type = "bandpass"; filtro.Q.value = 1.4;
      filtro.frequency.setValueAtTime(de, inicio);
      filtro.frequency.exponentialRampToValueAtTime(ate, inicio + dur);
      var g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, inicio);
      g.gain.exponentialRampToValueAtTime(volume, inicio + dur * 0.8);
      g.gain.exponentialRampToValueAtTime(0.0001, inicio + dur + 0.08);
      fonte.connect(filtro); filtro.connect(g); g.connect(mestre);
      fonte.start(inicio); fonte.stop(inicio + dur + 0.1);
    }
    function grave(inicio, volume) {
      var o = ctx.createOscillator(); o.type = "sine";
      o.frequency.setValueAtTime(110, inicio);
      o.frequency.exponentialRampToValueAtTime(38, inicio + 0.55);
      var g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, inicio);
      g.gain.exponentialRampToValueAtTime(volume, inicio + 0.015);
      g.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.9);
      o.connect(g); g.connect(mestre); o.start(inicio); o.stop(inicio + 1);
      // o estalo do impacto
      var f = ctx.createBufferSource(); f.buffer = ruido;
      var lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 1800;
      var gf = ctx.createGain();
      gf.gain.setValueAtTime(volume * 0.7, inicio);
      gf.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.25);
      f.connect(lp); lp.connect(gf); gf.connect(mestre); f.start(inicio); f.stop(inicio + 0.3);
    }
    function nota(freq, inicio, dur, volume, tipo) {
      var o = ctx.createOscillator(); o.type = tipo || "triangle"; o.frequency.value = freq;
      var g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, inicio);
      g.gain.exponentialRampToValueAtTime(volume, inicio + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, inicio + dur);
      o.connect(g); g.connect(mestre); o.start(inicio); o.stop(inicio + dur + 0.05);
    }
    sopro(t0, T.impacto, 180, 3200, 0.5);
    grave(t0 + T.impacto, 1.0);
    [2093, 2637, 3136].forEach(function (f, k) { nota(f, t0 + T.impacto + 0.02, 1.1, 0.12 - k * 0.03, "sine"); });
    [523.25, 659.25, 783.99, 1046.5].forEach(function (f, k) { nota(f, t0 + T.letras + k * 0.11, 0.35, 0.28); });
    sopro(t0 + T.nome - 0.32, 0.32, 400, 5000, 0.35);
    grave(t0 + T.nome, 0.7);
    [261.63, 329.63, 392, 523.25, 783.99].forEach(function (f) { nota(f, t0 + T.nome + 0.02, 1.5, 0.16, "sawtooth"); });
    [1568, 2093].forEach(function (f, k) { nota(f, t0 + T.nome + 0.12 + k * 0.1, 0.9, 0.1, "sine"); });
    setTimeout(function () { try { ctx.close(); } catch (e) { /* nada */ } }, (T.fim + 1.5) * 1000);
    return ctx;
  }

  /* ---------------------------------------------------------------- as faíscas */
  function faiscas(tela, cor) {
    var ctx = tela.getContext("2d");
    if (!ctx) return function () {};
    // riscos de luz macios não precisam da densidade da tela: 1 pixel por pixel da página
    var dpr = 1;
    var w = 0, h = 0;
    function medir() {
      var r = tela.getBoundingClientRect();
      w = Math.max(1, r.width); h = Math.max(1, r.height);
      tela.width = Math.round(w * dpr); tela.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    medir();
    var pequeno = Math.min(w, h) < 520;
    var paleta = CORES.concat(cor ? [cor, cor] : []);
    var n = pequeno ? 56 : 110;
    var raio = Math.hypot(w, h) * 0.6;
    var parts = [];
    for (var i = 0; i < n; i++) {
      parts.push({
        a: Math.random() * Math.PI * 2, r0: raio * (0.75 + Math.random() * 0.5), giro: (Math.random() - 0.5) * 1.4,
        atraso: Math.random() * 0.22, cor: paleta[(Math.random() * paleta.length) | 0],
        x: 0, y: 0, vx: 0, vy: 0, vida: 0, tam: 1 + Math.random() * 2.2, solta: false
      });
    }
    var brasas = [];
    for (i = 0; i < (pequeno ? 20 : 36); i++) {
      brasas.push({ x: Math.random(), y: Math.random(), v: 0.02 + Math.random() * 0.05, fase: Math.random() * 6.28,
                    tam: 0.6 + Math.random() * 1.6, cor: paleta[(Math.random() * paleta.length) | 0] });
    }
    var inicio = performance.now(), ultimo = inicio, vivo = true;
    function quadro(agora) {
      if (!vivo) return;
      var t = (agora - inicio) / 1000, dt = Math.min(0.05, (agora - ultimo) / 1000);
      ultimo = agora;
      var cx = w / 2, cy = h * 0.42;
      // apaga devagar: as faíscas deixam rastro
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      // as brasas que sobem devagar (depois do impacto)
      if (t > T.impacto) {
        var luz = Math.min(1, (t - T.impacto) / 0.6);
        brasas.forEach(function (b) {
          b.y -= b.v * dt; if (b.y < -0.05) { b.y = 1.05; b.x = Math.random(); }
          ctx.globalAlpha = (0.35 + 0.35 * Math.sin(t * 3 + b.fase)) * luz;
          ctx.fillStyle = b.cor;
          ctx.beginPath(); ctx.arc(b.x * w + Math.sin(t + b.fase) * 8, b.y * h, b.tam, 0, 6.283); ctx.fill();
        });
      }
      parts.forEach(function (p) {
        var px = p.x, py = p.y;
        if (t < T.impacto) {
          // correm das bordas para o centro, em espiral
          var k = Math.max(0, Math.min(1, (t - p.atraso) / (T.impacto - p.atraso)));
          var e = k * k * k;
          var r = p.r0 * (1 - e), a = p.a + p.giro * e;
          p.x = cx + Math.cos(a) * r; p.y = cy + Math.sin(a) * r;
          if (k === 0) { px = p.x; py = p.y; }
        } else {
          if (!p.solta) {
            // o impacto: explodem para fora
            p.solta = true;
            var forca = 260 + Math.random() * 820, dir = Math.random() * Math.PI * 2;
            p.x = cx; p.y = cy; px = cx; py = cy;
            p.vx = Math.cos(dir) * forca; p.vy = Math.sin(dir) * forca * 0.75;
            p.vida = 1;
          }
          p.vx *= Math.pow(0.18, dt); p.vy = p.vy * Math.pow(0.18, dt) + 60 * dt;
          p.x += p.vx * dt; p.y += p.vy * dt;
          p.vida -= dt * 0.75;
        }
        var alfa = t < T.impacto ? 0.9 : Math.max(0, p.vida);
        if (alfa <= 0) return;
        ctx.globalAlpha = alfa;
        ctx.strokeStyle = p.cor;
        ctx.lineWidth = p.tam;
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(p.x, p.y); ctx.stroke();
      });
      ctx.globalAlpha = 1;
      requestAnimationFrame(quadro);
    }
    requestAnimationFrame(quadro);
    window.addEventListener("resize", medir);
    return function parar() { vivo = false; window.removeEventListener("resize", medir); };
  }

  /* A capa do jogo ao fundo: desenhada UMA vez num quadro pequeno (160 x 90), já escura e
     desfocada; o navegador amplia liso. Desfocar a imagem grande a cada quadro da animação
     era o que mais pesava na placa de vídeo do celular. */
  function capaDesfocada(endereco) {
    var quadro = document.createElement("canvas");
    quadro.className = "ls-intro-capa";
    quadro.width = 160; quadro.height = 90;
    var img = new Image();
    img.decoding = "async";
    img.onload = function () {
      var ctx = quadro.getContext("2d");
      if (!ctx) return;
      // cobre o quadro inteiro (como o object-fit: cover), sem deformar
      var escala = Math.max(160 / img.width, 90 / img.height);
      var w = img.width * escala, h = img.height * escala;
      var comFiltro = "filter" in ctx;
      if (comFiltro) ctx.filter = "blur(2.5px) saturate(1.3) brightness(.55)";
      ctx.drawImage(img, (160 - w) / 2, (90 - h) / 2, w, h);
      if (!comFiltro) { ctx.fillStyle = "rgba(2, 5, 15, .5)"; ctx.fillRect(0, 0, 160, 90); }
    };
    img.onerror = function () { quadro.remove(); };
    img.src = endereco;
    return quadro;
  }

  /* ---------------------------------------------------------------- a cena */
  function elemento(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto) el.textContent = texto;
    return el;
  }
  /* A cor de cada letra, ao longo do degradê da marca (vermelho -> azul -> ciano). */
  function corNoDegrade(cores, x) {
    var trecho = Math.min(cores.length - 2, Math.floor(x * (cores.length - 1)));
    var f = x * (cores.length - 1) - trecho;
    var a = cores[trecho], b = cores[trecho + 1];
    return "rgb(" + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * f); }).join(",") + ")";
  }
  /* Cada letra num <span> (a entrada letra por letra), com o atraso e a cor de cada uma. */
  function letras(texto, classe, atraso, passo, cores) {
    var caixa = elemento("span", classe);
    var k = 0, total = Math.max(1, texto.length - 1);
    Array.prototype.forEach.call(texto, function (ch, i) {
      var l = elemento("span", "ls-intro-letra", ch === " " ? "\u00a0" : ch);
      l.style.animationDelay = (atraso + k * passo).toFixed(3) + "s";
      if (cores) l.style.color = corNoDegrade(cores, i / total);
      if (ch !== " ") k++;
      caixa.appendChild(l);
    });
    return caixa;
  }

  /* A cena inteira (os elementos, a capa já desfocada), sem começar a animar. */
  function montar(opcoes) {
    var tela = elemento("div", "ls-intro" + (reduzido ? " ls-intro--parada" : ""));
    tela.setAttribute("role", "img");
    tela.setAttribute("aria-label", "Lazer & Sport Games apresenta " + (opcoes.titulo || ""));
    if (opcoes.cor) tela.style.setProperty("--cor-intro", opcoes.cor);

    if (opcoes.capa) tela.appendChild(capaDesfocada(opcoes.capa));
    tela.appendChild(elemento("span", "ls-intro-grade"));
    tela.appendChild(elemento("span", "ls-intro-raios"));
    var canvas = null;
    if (!reduzido) { canvas = elemento("canvas", "ls-intro-faiscas"); tela.appendChild(canvas); }

    var palco = elemento("div", "ls-intro-palco");
    var grupo = elemento("div", "ls-intro-grupo");
    var miolo = elemento("div", "ls-intro-miolo");
    miolo.appendChild(elemento("span", "ls-intro-onda"));
    miolo.appendChild(elemento("span", "ls-intro-onda ls-intro-onda--2"));
    if (LOGO) {
      var logo = elemento("span", "ls-intro-logo");
      var img = document.createElement("img");
      img.src = LOGO; img.alt = "";
      logo.appendChild(img);
      miolo.appendChild(logo);
    }
    grupo.appendChild(miolo);
    var marca = elemento("strong", "ls-intro-marca");
    marca.appendChild(letras("LAZER & SPORT", "ls-intro-marca-a", T.letras, 0.045, [[255, 71, 87], [47, 139, 255], [63, 208, 255]]));
    marca.appendChild(letras("GAMES", "ls-intro-marca-b", T.letras + 0.62, 0.06));
    grupo.appendChild(marca);
    grupo.appendChild(elemento("span", "ls-intro-apresenta", "apresenta"));
    palco.appendChild(grupo);

    if (opcoes.titulo) {
      var nome = elemento("div", "ls-intro-nome");
      nome.appendChild(elemento("span", "ls-intro-titulo", opcoes.titulo));
      if (opcoes.console) nome.appendChild(elemento("span", "ls-intro-console", opcoes.console));
      palco.appendChild(nome);
    } else {
      tela.classList.add("ls-intro--sem-nome");
    }
    tela.appendChild(palco);
    tela.appendChild(elemento("span", "ls-intro-flare"));
    tela.appendChild(elemento("span", "ls-intro-clarao"));
    tela.appendChild(elemento("span", "ls-intro-pular", "toque para pular"));
    return { tela: tela, canvas: canvas };
  }

  /* PREPARAR (antes do toque, com o processador folgado): a cena já entra na página,
     escondida e com as animações paradas no começo -- estilos calculados, capa decodificada,
     texto pronto, o ruído do som feito. O toque em Jogar só dá o "play". */
  var preparadas = {};
  function preparar(caixa, opcoes) {
    opcoes = opcoes || {};
    var chave = opcoes.chave || opcoes.titulo || "jogo";
    if (!caixa || vistos[chave] || preparadas[chave]) return;
    var cena = montar(opcoes);
    cena.tela.classList.add("ls-intro--preparada");
    caixa.appendChild(cena.tela);
    preparadas[chave] = cena;
    if (!reduzido) ruidoPronto();
  }

  function mostrar(caixa, opcoes) {
    opcoes = opcoes || {};
    var chave = opcoes.chave || opcoes.titulo || "jogo";
    if (!caixa || vistos[chave]) return Promise.resolve(false);
    vistos[chave] = true;

    return new Promise(function (resolve) {
      var cena = preparadas[chave];
      delete preparadas[chave];
      if (cena && cena.tela.parentNode !== caixa) { cena.tela.remove(); cena = null; }
      if (!cena) { cena = montar(opcoes); caixa.appendChild(cena.tela); }
      var tela = cena.tela, canvas = cena.canvas;
      // o "play": tudo começa do zero agora
      tela.classList.remove("ls-intro--preparada");
      var parar = canvas ? faiscas(canvas, opcoes.cor) : function () {};
      var som = reduzido ? null : tocar();

      var fechado = false;
      var duracao = reduzido ? 1500 : (opcoes.titulo ? T.fim : T.nome + 0.4) * 1000;
      var relogio = null;
      function fechar(rapido) {
        if (fechado) return;
        fechado = true;
        clearTimeout(relogio);
        document.removeEventListener("keydown", tecla, true);
        tela.classList.add("ls-intro--saindo");
        if (rapido && som) { try { som.close(); } catch (e) { /* nada */ } }
        setTimeout(function () { parar(); tela.remove(); resolve(true); }, rapido ? 180 : 420);
      }
      function tecla(e) {
        if (e.key === "Enter" || e.key === " " || e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fechar(true); }
      }
      relogio = setTimeout(function () { fechar(false); }, duracao);
      document.addEventListener("keydown", tecla, true);
      tela.addEventListener("pointerdown", function (e) { e.preventDefault(); fechar(true); });
    });
  }

  window.LSIntroJogos = { mostrar: mostrar, preparar: preparar };
})();
