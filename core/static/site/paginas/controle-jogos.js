/* ======================================================================
   O CONTROLE NO LAUNCHER (/jogos/) -- Xbox, PlayStation, 8BitDo, genéricos.

   Os jogos já entendiam o controle (o reprodutor dos consoles e o console
   dos jogos da casa); a BIBLIOTECA não: com o controle na mão, não dava para
   escolher um jogo, abrir a ficha nem voltar. Aqui o launcher inteiro anda
   pelo controle, e ele sabe quando o controle entra e quando sai.

   ESPETOU / TIROU. O navegador só mostra o controle depois do primeiro
   botão apertado, e o aviso de "saiu" nem sempre chega (cabo puxado,
   Bluetooth que cai, aba em segundo plano). Por isso o estado não depende só
   dos eventos: a cada meio segundo a lista de controles é conferida.
     - entrou:  body.tem-controle, aviso "Controle conectado" e a barra de
                dicas embaixo (A, B, Y, LB/RB);
     - saiu:    as duas classes saem, a barra de dicas some, o foco amarelo
                some, nenhum botão fica "preso": o launcher volta ao normal
                (mouse, toque e teclado como sempre).
   body.usando-controle só fica enquanto o controle é o que está mexendo: um
   movimento do mouse ou um toque na tela esconde o foco amarelo (o controle
   continua valendo; o próximo botão traz o foco de volta).

   OS BOTÕES (pela posição, como nos jogos):
     cruz / analógico esquerdo   andar pelos jogos e botões (segurar repete)
     analógico direito           rolar a página
     A                           abrir / apertar o que está marcado
     B                           voltar (fecha a ficha, sai da busca)
     Y                           ir para a busca
     LB / RB                     estante anterior / próxima
     COM UM JOGO ABERTO o controle é do jogo. Para voltar à biblioteca:
     SEGURAR View + B por 1 segundo.
   ====================================================================== */
(function () {
  "use strict";
  if (!navigator.getGamepads) return;
  var corpo = document.body;
  var raizDoPortal = document.querySelector("[data-portal]");
  if (!raizDoPortal) return;

  var temControle = false;
  var barra = null;
  var laco = 0;

  /* ---------------------------------------------------------------- avisos e dicas */
  var tempoAviso = null;
  function avisar(mensagem) {
    var caixa = document.querySelector("[data-app-aviso]");
    if (!caixa) return;
    caixa.textContent = mensagem;
    caixa.hidden = false;
    clearTimeout(tempoAviso);
    tempoAviso = setTimeout(function () { caixa.hidden = true; }, 4500);
  }
  function estilo() {
    if (document.getElementById("ls-controle-estilo")) return;
    var s = document.createElement("style");
    s.id = "ls-controle-estilo";
    s.textContent =
      "body.usando-controle :focus{outline:3px solid #ffd23f!important;outline-offset:3px!important;border-radius:14px;" +
      "box-shadow:0 0 0 6px rgba(255,210,63,.22),0 0 26px rgba(255,210,63,.45)!important;transition:outline-offset .12s ease}" +
      "body.usando-controle{cursor:none}" +
      ".ls-controle-dicas{position:fixed;left:50%;bottom:14px;transform:translate(-50%,20px);z-index:60;display:flex;gap:18px;" +
      "align-items:center;padding:10px 20px;border-radius:999px;background:rgba(8,12,28,.88);border:1px solid rgba(255,255,255,.14);" +
      "color:#e8edff;font:600 14px/1.2 system-ui,sans-serif;opacity:0;pointer-events:none;transition:opacity .25s ease,transform .25s ease;" +
      "backdrop-filter:blur(8px);white-space:nowrap;max-width:94vw;overflow:hidden}" +
      "body.tem-controle .ls-controle-dicas{opacity:1;transform:translate(-50%,0)}" +
      "body.app-jogando .ls-controle-dicas{display:none}" +
      ".ls-controle-dicas b{display:inline-grid;place-items:center;min-width:24px;height:24px;padding:0 6px;margin-right:6px;border-radius:999px;" +
      "font-weight:800;color:#0b1020;background:#ffd23f}" +
      ".ls-controle-dicas b.a{background:#4ade80}.ls-controle-dicas b.b{background:#f87171}.ls-controle-dicas b.y{background:#facc15}" +
      ".ls-controle-dicas b.l{background:#cbd5e1;border-radius:8px}" +
      "@media (max-width:640px){.ls-controle-dicas{gap:10px;font-size:12px;padding:8px 12px}}";
    document.head.appendChild(s);
  }
  function montarBarra() {
    if (barra) return;
    estilo();
    barra = document.createElement("div");
    barra.className = "ls-controle-dicas";
    barra.setAttribute("aria-hidden", "true");
    barra.innerHTML = "<span><b class=\"a\">A</b>Abrir</span><span><b class=\"b\">B</b>Voltar</span>" +
      "<span><b class=\"y\">Y</b>Buscar</span><span><b class=\"l\">LB</b><b class=\"l\">RB</b>Estante</span>";
    corpo.appendChild(barra);
  }

  /* ---------------------------------------------------------------- o controle entrou / saiu */
  function controles() {
    var lista = [];
    try {
      var todos = navigator.getGamepads() || [];
      for (var i = 0; i < todos.length; i++) if (todos[i] && todos[i].connected !== false && todos[i].buttons) lista.push(todos[i]);
    } catch (e) { /* sem permissão: como se não houvesse controle */ }
    return lista;
  }
  function nomeDe(pad) { return (pad && pad.id || "").replace(/\s*\(.*$/, "").trim(); }

  function conferir() {
    var lista = controles();
    var tem = lista.length > 0;
    if (tem === temControle) return;
    temControle = tem;
    if (tem) {
      montarBarra();
      corpo.classList.add("tem-controle");
      var nome = nomeDe(lista[0]);
      avisar("Controle conectado" + (nome ? ": " + nome : "") + ". Use a cruz para escolher e A para abrir.");
      antes = {}; // o botão que ligou o controle não vale como comando
      prender(lista[0]);
      if (!laco) laco = requestAnimationFrame(passo);
    } else {
      // O LAUNCHER VOLTA AO NORMAL: sem classe, sem foco amarelo, sem repetição presa
      corpo.classList.remove("tem-controle", "usando-controle");
      antes = {};
      repetir = {};
      seguraSair = 0;
      avisar("Controle desconectado. O launcher voltou ao normal.");
    }
  }
  window.addEventListener("gamepadconnected", conferir);
  window.addEventListener("gamepaddisconnected", function () { setTimeout(conferir, 0); });
  setInterval(conferir, 500);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) conferir(); });
  // mouse e toque: o foco amarelo sai da frente (o controle continua valendo)
  ["mousemove", "pointerdown", "wheel"].forEach(function (tipo) {
    window.addEventListener(tipo, function (e) {
      if (tipo === "mousemove" && !e.movementX && !e.movementY) return;
      corpo.classList.remove("usando-controle");
    }, { passive: true });
  });

  /* ---------------------------------------------------------------- por onde dá para andar */
  var SELETOR = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), [tabindex]:not([tabindex='-1'])";
  function escopo() {
    var ficha = document.querySelector("[data-bj-ficha]:not([hidden])");
    return ficha || document;
  }
  function visivel(no) {
    if (!no.getClientRects().length) return false;
    var r = no.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return false;
    var cs = getComputedStyle(no);
    return cs.visibility !== "hidden" && cs.pointerEvents !== "none" && !no.closest("[hidden], [inert], [aria-hidden='true']");
  }
  function candidatos() {
    var raiz = escopo();
    var lista = Array.prototype.slice.call(raiz.querySelectorAll(SELETOR));
    var alto = window.innerHeight;
    return lista.filter(function (no) {
      if (no.classList.contains("skip-link") || no.closest(".ls-controle-dicas")) return false;
      if (!visivel(no)) return false;
      var r = no.getBoundingClientRect();
      return r.bottom > -alto * 2 && r.top < alto * 3; // perto da tela: o resto chega rolando
    });
  }
  function centro(r) { return [r.left + r.width / 2, r.top + r.height / 2]; }
  function focar(no) {
    if (!no) return;
    corpo.classList.add("usando-controle");
    try { no.focus({ preventScroll: true }); } catch (e) { no.focus(); }
    try { no.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" }); } catch (e) { no.scrollIntoView(); }
  }
  function primeiro() {
    var lista = candidatos();
    var naTela = lista.filter(function (no) { var r = no.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight; });
    // de preferência o botão de jogar em destaque ou um jogo da estante
    var bom = (escopo() === document ? document.querySelector("[data-portal-hero] a.pg-botao, [data-portal-hero] a[href]") : escopo().querySelector("[data-bj-ficha-jogar]"));
    if (bom && visivel(bom)) return bom;
    return naTela[0] || lista[0] || null;
  }
  function andar(dx, dy) {
    var atual = document.activeElement;
    var raiz = escopo();
    if (!atual || atual === corpo || (raiz !== document && !raiz.contains(atual)) || !visivel(atual)) { focar(primeiro()); return; }
    var de = atual.getBoundingClientRect();
    var c0 = centro(de);
    var melhor = null, menor = Infinity;
    candidatos().forEach(function (no) {
      if (no === atual || no.contains(atual)) return;
      var r = no.getBoundingClientRect();
      var c = centro(r);
      var frente = (c[0] - c0[0]) * dx + (c[1] - c0[1]) * dy;
      if (frente < 6) return;
      var lado = Math.abs((c[0] - c0[0]) * dy) + Math.abs((c[1] - c0[1]) * dx);
      // quem está na mesma linha / coluna ganha de quem está na diagonal
      var alinhado = dx ? (r.top < de.bottom && r.bottom > de.top) : (r.left < de.right && r.right > de.left);
      var nota = frente + lado * (alinhado ? 0.6 : 2.6);
      if (nota < menor) { menor = nota; melhor = no; }
    });
    if (melhor) focar(melhor);
    else if (dy) window.scrollBy({ top: dy * window.innerHeight * 0.6, behavior: "smooth" });
  }

  /* ---------------------------------------------------------------- os botões */
  function apertarMarcado() {
    var no = document.activeElement;
    if (!no || no === corpo || !visivel(no)) { focar(primeiro()); return; }
    corpo.classList.add("usando-controle");
    if (no.tagName === "SELECT") {
      // a caixa de escolha não abre por programa: A passa para a próxima opção
      no.selectedIndex = (no.selectedIndex + 1) % no.options.length;
      no.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    no.click();
  }
  function tecla(nome) {
    var alvo = document.activeElement || document;
    alvo.dispatchEvent(new KeyboardEvent("keydown", { key: nome, bubbles: true, cancelable: true }));
  }
  function voltar() {
    var ali = document.activeElement;
    if (document.querySelector("[data-bj-ficha]:not([hidden])")) { tecla("Escape"); return; }
    if (ali && /^(INPUT|TEXTAREA|SELECT)$/.test(ali.tagName)) { ali.blur(); focar(primeiro()); return; }
    if (window.scrollY > 40) { window.scrollTo({ top: 0, behavior: "smooth" }); focar(primeiro()); }
  }
  function buscar() {
    var campo = document.querySelector("[data-portal-busca]");
    if (!campo) return;
    window.scrollTo({ top: 0, behavior: "auto" });
    focar(campo);
  }
  function estante(passoDaEstante) {
    var itens = Array.prototype.filter.call(document.querySelectorAll("[data-bj-lado] a[href], [data-bj-lado] button"), visivel);
    if (!itens.length) return;
    var atual = -1;
    itens.forEach(function (no, i) {
      if (no.getAttribute("aria-current") || no.getAttribute("aria-pressed") === "true" || /is-ativ|ativo|ativa/.test(no.className)) atual = i;
    });
    var novo = itens[(Math.max(atual, 0) + passoDaEstante + itens.length) % itens.length];
    corpo.classList.add("usando-controle");
    novo.click();
    focar(novo);
  }

  /* ---------------------------------------------------------------- o laço */
  var antes = {};      // botão -> estava apertado
  var repetir = {};    // direção -> quando repete
  var seguraSair = 0;
  function prender(pad) {
    // o que está apertado AGORA não dispara nada (o botão que "acordou" o controle)
    for (var i = 0; i < pad.buttons.length; i++) antes[i] = !!(pad.buttons[i] && (pad.buttons[i].pressed || pad.buttons[i].value > 0.5));
  }
  function passo() {
    laco = 0;
    if (!temControle) return;
    laco = requestAnimationFrame(passo);
    if (document.hidden) return;
    var pad = controles()[0];
    if (!pad) { conferir(); return; }
    var b = function (i) { return !!(pad.buttons[i] && (pad.buttons[i].pressed || pad.buttons[i].value > 0.5)); };
    var novo = function (i) { var agora = b(i); var foi = agora && !antes[i]; antes[i] = agora; return foi; };
    var agoraMs = Date.now();

    // COM UM JOGO ABERTO o controle é do jogo; View + B segurados voltam à biblioteca
    var jogoAberto = !!(window.LSApp && window.LSApp.jogoAberto && window.LSApp.jogoAberto());
    if (jogoAberto) {
      if (b(8) && b(1)) {
        if (!seguraSair) seguraSair = agoraMs;
        else if (agoraMs - seguraSair > 1000) { seguraSair = 0; prender(pad); window.LSApp.fechar(); avisar("De volta à biblioteca."); }
      } else seguraSair = 0;
      prender(pad);
      repetir = {};
      return;
    }
    seguraSair = 0;
    // a abertura do app ainda na tela: espera
    var abertura = document.querySelector("[data-app-abertura]");
    if (abertura && abertura.getClientRects().length && Number(getComputedStyle(abertura).opacity) > 0.5) { prender(pad); return; }

    var x = pad.axes[0] || 0, y = pad.axes[1] || 0;
    var direcoes = {
      cima: b(12) || y < -0.55, baixo: b(13) || y > 0.55,
      esquerda: b(14) || x < -0.55, direita: b(15) || x > 0.55,
    };
    var passos = { cima: [0, -1], baixo: [0, 1], esquerda: [-1, 0], direita: [1, 0] };
    Object.keys(direcoes).forEach(function (d) {
      if (!direcoes[d]) { repetir[d] = 0; return; }
      if (!repetir[d]) { repetir[d] = agoraMs + 380; andar(passos[d][0], passos[d][1]); }
      else if (agoraMs >= repetir[d]) { repetir[d] = agoraMs + 140; andar(passos[d][0], passos[d][1]); }
    });
    // o analógico direito rola a página
    var ry = pad.axes[3] || 0;
    if (Math.abs(ry) > 0.25) window.scrollBy(0, ry * 22);

    if (novo(0)) apertarMarcado();
    if (novo(1)) voltar();
    if (novo(3)) buscar();
    if (novo(4)) estante(-1);
    if (novo(5)) estante(1);
    novo(2); novo(8); novo(9);
  }

  conferir();
  window.LSControle = { ligado: function () { return temControle; }, conferir: conferir };
})();
