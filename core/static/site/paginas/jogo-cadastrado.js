/* ======================================================================
   A PÁGINA DE UM JOGO QUE A EQUIPE SUBIU (JogoCadastrado).

   O jogo só baixa quando a pessoa toca em "Jogar": aí nasce um quadro
   isolado (iframe com sandbox), que roda o jogo sem enxergar o resto do
   site -- não lê os cookies, o conteúdo da página nem o login. A tela
   cheia vale para o quadro inteiro.
   ====================================================================== */
(function () {
  "use strict";
  const palco = document.querySelector("[data-jogo]");
  if (!palco) return;
  const capa = palco.querySelector("[data-jogo-capa]");
  const botao = palco.querySelector("[data-jogo-jogar]");
  const telaCheia = palco.querySelector("[data-jogo-tela-cheia]");
  const src = palco.dataset.jogoSrc;
  if (!src || !botao) return;

  /* JOGO NA HORA (jogo-guardado.js). Enquanto a pessoa lê a página, o jogo já
     vai sendo guardado no aparelho; ao tocar em Jogar, o quadro abre o que está
     guardado. Jogo grande (disco de PS1) não começa sozinho -- seria gastar o
     plano de dados de quem só passou pela página: ele baixa no toque e fica
     guardado para a próxima vez. */
  const PREPARO_AUTOMATICO = 120 * 1048576;
  const aviso = palco.querySelector("[data-jogo-preparo]");
  const arquivosBruto = document.getElementById("jogoArquivos");
  let preparo = null;
  let quadroDoJogo = null;

  function mb(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(bytes >= 10485760 ? 0 : 1).replace(".", ",") + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }
  function avisar(texto) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = !texto;
  }

  /* O emulador e o núcleo do console, adiantados -- só na primeira vez: depois
     disso o próprio emulador guarda o núcleo no aparelho, e baixar de novo a
     cada visita seria gastar dados à toa. A versão do núcleo segue a do
     emulador: sem WebGL 2 ele usa a "legacy". */
  function preCarregarEmulador(info) {
    if (!info || !info.dados) return;
    const marca = "ls-emulador-" + (info.nucleo || "base");
    try { if (localStorage.getItem(marca)) return; } catch (e) { /* sem armazenamento: adianta mesmo assim */ }
    let webgl2 = false;
    try { webgl2 = !!document.createElement("canvas").getContext("webgl2"); } catch (e) { webgl2 = false; }
    const lista = ["loader.js", "emulator.min.js", "emulator.min.css"];
    // o nome do núcleo segue o do emulador: "-thread" (PSP, DOS) e "-legacy" (sem WebGL 2)
    if (info.nucleo) lista.push("cores/" + info.nucleo + (info.threads ? "-thread" : "") + (webgl2 ? "" : "-legacy") + "-wasm.data");
    (info.extras || []).forEach(function (extra) { lista.push(extra); });
    lista.forEach(function (arquivo) {
      const link = document.createElement("link");
      link.rel = "prefetch";
      link.href = info.dados + arquivo;
      document.head.appendChild(link);
    });
    botao.addEventListener("click", function () {
      try { localStorage.setItem(marca, "1"); } catch (e) { /* nada */ }
    }, { once: true });
  }

  function prepararJogo() {
    const guardado = window.LSJogoGuardado;
    if (!arquivosBruto || !guardado || !guardado.disponivel) return;
    let preparoDoServidor;
    try { preparoDoServidor = JSON.parse(arquivosBruto.textContent || "{}"); } catch (e) { return; }
    const dados = preparoDoServidor.config || {};
    preCarregarEmulador(preparoDoServidor);
    const semEndereco = dados.arquivos || [];
    const passe = window.LSPasse;
    if (!semEndereco.length || !passe) return;
    const total = semEndereco.reduce(function (t, i) { return t + i.tamanho; }, 0);
    const economia = navigator.connection && navigator.connection.saveData;
    // de onde baixar não vem na página (core/escudo_jogos.py): a lista guardada no aparelho,
    // ou o passe (a prova de trabalho) quando o jogo é pequeno e vai ser preparado agora
    const guardada = passe.lerLista(dados.jogo);
    let itens = null;
    try { itens = guardada ? passe.juntar(semEndereco, guardada) : null; } catch (e) { itens = null; }
    const faltando = itens ? guardado.quantoFalta(itens) : Promise.resolve(total);
    faltando.then(function (falta) {
      if (!falta) { avisar("Já está no aparelho: abre na hora."); return; }
      if (falta > PREPARO_AUTOMATICO || economia) {
        avisar("Na primeira vez baixa " + mb(falta) + "; depois fica guardado e abre na hora.");
        return;
      }
      const controle = typeof AbortController !== "undefined" ? new AbortController() : null;
      preparo = controle;
      avisar("Preparando o jogo…");
      passe.pegar(dados.passe, dados.jogo).then(function (lista) {
        return guardado.preparar(dados.jogo, passe.juntar(semEndereco, lista), function (feito) {
          avisar("Preparando o jogo: " + Math.min(99, Math.floor(feito / total * 100)) + "%");
        }, controle && controle.signal);
      }).then(function (r) {
        preparo = null;
        avisar(r && r.guardado ? "Pronto: abre na hora." : "");
      }, function () { preparo = null; avisar(""); });
    });
  }
  if (arquivosBruto) {
    // depois que a página terminou de abrir, para não disputar a rede com ela
    const comecar = function () { setTimeout(prepararJogo, 400); };
    if (document.readyState === "complete") comecar(); else window.addEventListener("load", comecar, { once: true });
  }

  /* "Jogados recentemente", na biblioteca (/jogos/): o aparelho anota quando cada jogo abriu. */
  function lembrarNaBiblioteca() {
    try {
      const chave = "ls-biblioteca-recentes";
      const lista = JSON.parse(localStorage.getItem(chave) || "{}") || {};
      lista[palco.dataset.jogoSlug] = Date.now();
      const ordem = Object.keys(lista).sort(function (a, b) { return lista[b] - lista[a]; }).slice(0, 30);
      const curta = {};
      ordem.forEach(function (s) { curta[s] = lista[s]; });
      localStorage.setItem(chave, JSON.stringify(curta));
    } catch (e) { /* sem armazenamento: a biblioteca só não mostra */ }
  }

  /* OS COMANDOS SOBRE O JOGO: o botão fica no canto do palco enquanto se joga
     (também em tela cheia) e abre o como jogar por cima, sem sair do jogo. */
  const botaoComandos = palco.querySelector("[data-jogo-comandos-botao]");
  const painelComandos = palco.querySelector("[data-jogo-comandos-painel]");
  function mostrarComandos(abrir) {
    if (!painelComandos) return;
    painelComandos.hidden = !abrir;
    botaoComandos.setAttribute("aria-expanded", abrir ? "true" : "false");
    if (!abrir) { const q = palco.querySelector(".jc-quadro"); if (q) q.focus(); }
  }
  if (botaoComandos && painelComandos) {
    botaoComandos.addEventListener("click", function () { mostrarComandos(painelComandos.hidden); });
    painelComandos.querySelector("[data-jogo-comandos-fechar]").addEventListener("click", function () { mostrarComandos(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !painelComandos.hidden) mostrarComandos(false); });
  }

  function jogar() {
    // o toque manda: o preparo para, e o quadro continua do que já foi guardado
    if (preparo) { preparo.abort(); preparo = null; }
    lembrarNaBiblioteca();
    // PSP e DOS: o núcleo de várias linhas só roda numa página isolada, que não
    // pode estar num quadro -- o jogo abre na tela inteira (com "Voltar ao jogo")
    if (palco.dataset.jogoTelaPropria === "1") { location.assign(src); return; }
    const quadro = document.createElement("iframe");
    quadroDoJogo = quadro;
    quadro.className = "jc-quadro";
    quadro.src = src;
    quadro.title = palco.dataset.jogoTitulo || "Jogo";
    // o quadro roda o jogo, mas fica preso nele: sem acesso ao site.
    // "allow-same-origin" só para jogo de OUTRO endereço (Cloudinary, itch.io...):
    // ele guarda o progresso no próprio domínio. Um arquivo servido pelo
    // domínio do site, com scripts e mesma origem juntos, sairia da caixa.
    let deFora = false;
    let doEmulador = false;
    try {
      const alvo = new URL(src, location.href);
      deFora = alvo.origin !== location.origin;
      // o quadro do emulador é uma página do próprio site, só com o código
      // do emulador (nenhum .html enviado roda nela): pode ter a mesma
      // origem, para o jogo salvo ficar guardado no navegador
      doEmulador = palco.dataset.jogoEmulador === "1" && !deFora && /^\/jogos\/[a-z0-9-]+\/emulador\/$/.test(alvo.pathname);
    } catch (e) { deFora = false; }
    // (a tela cheia vem do atributo "allow" abaixo: "allow-fullscreen" não é permissão de sandbox)
    const permissoes = ["allow-scripts", "allow-pointer-lock", "allow-orientation-lock"];
    if (deFora || doEmulador) permissoes.push("allow-same-origin");
    quadro.setAttribute("sandbox", permissoes.join(" "));
    quadro.setAttribute("allow", "autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-write");
    quadro.setAttribute("referrerpolicy", "no-referrer");
    quadro.setAttribute("loading", "eager");
    if (capa) capa.remove();
    palco.insertBefore(quadro, telaCheia || null);
    palco.classList.add("jc-palco--jogando");
    if (telaCheia) telaCheia.hidden = false;
    if (botaoComandos) botaoComandos.hidden = false;
    // "LAZER & SPORT GAMES apresenta": por cima do quadro, que já está
    // carregando o jogo por baixo -- a espera do carregamento vira abertura
    const intro = window.LSIntroJogos;
    if (intro) {
      intro.mostrar(palco, { titulo: palco.dataset.jogoTitulo || "", cor: palco.dataset.jogoCor || "", chave: "cadastrado:" + src,
        capa: palco.dataset.jogoArte || "" })
        .then(function () { quadro.focus(); });
    } else {
      quadro.focus();
    }
  }

  /* A JOGADA GRÁTIS. Sem conta são 2 jogadas no total, somando todos os jogos. O toque em
     Jogar avisa o site (/jogos/abriu/), que conta a partida do "Mais jogados" e diz se ainda
     há jogada grátis. Quem GASTA a jogada é quem começa o jogo de fato: aqui o jogo HTML (e
     ela dura até 5 minutos de jogo -- o site não vê o personagem morrer); o de console gasta
     no Jogar do próprio emulador, que abre depois deste. Sem jogada, vem o convite de
     cadastro. Se o site não responder logo (rede ruim), o jogo abre do mesmo jeito. */
  const abriuUrl = palco.dataset.jogoAbriu;
  const slug = palco.dataset.jogoSlug;
  const doConsole = palco.dataset.jogoEmulador === "1";
  const portao = document.querySelector("[data-jogo-portao]");
  const avisoGratis = document.querySelector("[data-jogo-gratis]");
  const ESPERA_MAXIMA = 2500;

  function csrf() {
    const achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return achado ? decodeURIComponent(achado[1]) : "";
  }
  function perguntar() {
    const livre = { liberado: true };
    if (!abriuUrl || !slug || !window.fetch) return Promise.resolve(livre);
    const pedido = fetch(abriuUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ jogo: slug, gastar: !doConsole }),
    }).then(function (r) { return r.ok ? r.json() : livre; }).catch(function () { return livre; });
    const espera = new Promise(function (pronto) { setTimeout(function () { pronto(livre); }, ESPERA_MAXIMA); });
    return Promise.race([pedido, espera]);
  }

  function fecharPortao() {
    if (!portao || portao.hidden) return;
    portao.hidden = true;
    document.removeEventListener("keydown", teclaDoPortao);
    botao.focus();
  }
  function teclaDoPortao(evento) {
    if (evento.key === "Escape") fecharPortao();
  }
  function abrirPortao(titulo) {
    if (!portao) return;
    const cabeca = portao.querySelector("h2");
    if (cabeca) {
      if (!cabeca.dataset.original) cabeca.dataset.original = cabeca.textContent;
      cabeca.textContent = titulo || cabeca.dataset.original;
    }
    portao.hidden = false;
    const primeiro = portao.querySelector("a, button:not([data-jogo-portao-fechar])");
    if (primeiro) primeiro.focus();
    document.addEventListener("keydown", teclaDoPortao);
  }
  if (portao) {
    portao.querySelector("[data-jogo-portao-fechar]").addEventListener("click", fecharPortao);
    portao.addEventListener("click", function (evento) { if (evento.target === portao) fecharPortao(); });
  }
  // o aviso embaixo do jogo: quantas jogadas grátis sobram
  function mostrarAvisoGratis(resposta) {
    if (!avisoGratis || !resposta || !resposta.visitante) return;
    const texto = avisoGratis.querySelector("[data-jogo-gratis-texto]");
    if (texto) {
      const minutos = resposta.segundos ? Math.round(resposta.segundos / 60) : 5;
      texto.textContent = doConsole
        ? "Sem conta, são " + resposta.limite + " jogadas grátis de até " + minutos + " minutos, somando todos os jogos."
        : resposta.restantes === 0
          ? "Esta é a sua última jogada grátis (até " + minutos + " minutos)."
          : "Jogada grátis: até " + minutos + " minutos. Sobra " + resposta.restantes + " de " + resposta.limite + ".";
    }
    avisoGratis.hidden = false;
  }
  // o tempo da jogada grátis do jogo HTML: só anda com a página à vista
  function contarTempo(segundos) {
    let resta = segundos;
    const relogio = setInterval(function () {
      if (!quadroDoJogo || !quadroDoJogo.isConnected) { clearInterval(relogio); return; }
      if (document.hidden) return;
      resta -= 1;
      if (resta > 0) return;
      clearInterval(relogio);
      // acabou: o jogo sai (o quadro leva o jogo junto) e vem o convite
      if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(function () {});
      quadroDoJogo.remove();
      quadroDoJogo = null;
      palco.classList.remove("jc-palco--jogando");
      palco.classList.add("jc-palco--acabou");
      abrirPortao("Os seus " + Math.round(segundos / 60) + " minutos grátis acabaram");
    }, 1000);
  }

  let pedindo = false;
  botao.addEventListener("click", function () {
    if (pedindo) return;
    pedindo = true;
    botao.setAttribute("aria-busy", "true");
    perguntar().then(function (resposta) {
      pedindo = false;
      botao.removeAttribute("aria-busy");
      if (resposta && resposta.liberado === false) { abrirPortao("Você já usou as suas " + (resposta.limite || 2) + " jogadas grátis"); return; }
      mostrarAvisoGratis(resposta);
      jogar();
      if (resposta && resposta.segundos && !doConsole) contarTempo(resposta.segundos);
    });
  });

  // em tela cheia no celular, deita (ou levanta) a tela conforme o jogo
  function girarTela() {
    const orientacao = screen.orientation;
    if (!orientacao || !orientacao.lock) return;
    const deitado = palco.classList.contains("jc-palco--paisagem") || palco.classList.contains("jc-palco--largo");
    const emPe = palco.classList.contains("jc-palco--retrato");
    if (!deitado && !emPe) return;
    orientacao.lock(deitado ? "landscape" : "portrait").catch(function () {});
  }

  if (telaCheia) {
    telaCheia.addEventListener("click", function () {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else if (palco.requestFullscreen) {
        palco.requestFullscreen().then(girarTela).catch(function () {});
      }
    });
    document.addEventListener("fullscreenchange", function () {
      const icone = telaCheia.querySelector("i");
      if (icone) icone.className = document.fullscreenElement ? "fa-solid fa-compress" : "fa-solid fa-expand";
    });
  }
})();

/* ----------------------------------------------------------------------
   COMO JOGAR: "No computador" (tecla por tecla) e "No celular" (onde fica
   cada botão no controle da tela). Abre na aba do aparelho de quem está
   vendo; sem JavaScript, as duas listas aparecem uma embaixo da outra.
   ---------------------------------------------------------------------- */
(function () {
  "use strict";
  const caixa = document.querySelector("[data-controles]");
  const abas = caixa && caixa.querySelector("[data-controles-abas]");
  if (!abas) return;
  const botoes = Array.prototype.slice.call(abas.querySelectorAll("[data-aba]"));
  const paineis = Array.prototype.slice.call(caixa.querySelectorAll("[data-painel]"));

  function escolher(qual, focar) {
    botoes.forEach(function (b) {
      const ativo = b.dataset.aba === qual;
      b.setAttribute("aria-selected", ativo ? "true" : "false");
      b.tabIndex = ativo ? 0 : -1;
      if (ativo && focar) b.focus();
    });
    paineis.forEach(function (p) { p.hidden = p.dataset.painel !== qual; });
  }

  botoes.forEach(function (b, i) {
    b.addEventListener("click", function () { escolher(b.dataset.aba); });
    b.addEventListener("keydown", function (evento) {
      if (evento.key !== "ArrowRight" && evento.key !== "ArrowLeft") return;
      evento.preventDefault();
      const proximo = botoes[(i + (evento.key === "ArrowRight" ? 1 : botoes.length - 1)) % botoes.length];
      escolher(proximo.dataset.aba, true);
    });
  });

  let toque = false;
  try { toque = window.matchMedia("(pointer: coarse)").matches; } catch (e) { toque = false; }
  abas.hidden = false;
  caixa.classList.add("jc-controles--abas");
  // um controle já ligado (e acordado com um toque num botão) abre direto a aba dele
  let controle = false;
  try { controle = Array.prototype.some.call(navigator.getGamepads ? navigator.getGamepads() : [], function (g) { return g && g.connected; }); } catch (e) { controle = false; }
  escolher(controle ? "controle" : toque ? "celular" : "pc");
  window.addEventListener("gamepadconnected", function () { escolher("controle"); });
})();
