/* ======================================================================
   O REPRODUTOR DOS JOGOS DE CONSOLE: liga o EmulatorJS do próprio site
   a este jogo e põe por cima a interface do site.

   A configuração vem do servidor (core/views_jogos.config_do_emulador):
   o núcleo do console e TODOS os arquivos do jogo -- o que o emulador
   abre (o .cue, o .m3u, a ROM) e os que vão ao lado na pasta virtual dele
   (as faixas .bin, os outros discos, a BIOS) --, cada um com o nome exato
   que o índice pede e com a lista de partes de onde baixar.

   O CAMINHO DE QUEM JOGA
   1. A abertura "LAZER & SPORT GAMES apresenta" enquanto o jogo baixa (com
      o progresso). Da segunda vez, o jogo sai do aparelho (jogo-guardado.js).
   2. Pronto: o botão Jogar. O toque é o que o navegador exige para o som e,
      no celular, para a tela cheia deitada -- o jogo abre assim.
   3. O emulador liga por baixo da abertura; quando o jogo começa, a abertura
      sai, a barra de cima aparece e some sozinha.

   POR QUE ESTE ARQUIVO BAIXA TUDO, E NÃO O EMULADOR
   1. Arquivo grande fica guardado em PEDAÇOS (o Cloudinary aceita até 10
      MB por arquivo): aqui os pedaços são baixados e juntados, na ordem.
   2. O EmulatorJS 4.2.3 grava os "arquivos externos" que ele mesmo baixa
      num formato que a pasta virtual recusa (fica criado e VAZIO, sem erro).
      Entregando os bytes prontos, ele grava certo.
   ====================================================================== */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var bruto = document.getElementById("emuladorConfig");
  if (!bruto) return;
  var config = JSON.parse(bruto.textContent || "{}");
  if (!config.core || !(config.arquivos || []).length) return;

  var corpo = document.body;
  var $ = function (seletor) { return document.querySelector(seletor); };
  var abertura = $("[data-pl-abertura]");
  var status = $("[data-pl-status]");
  var progresso = $("[data-pl-progresso]");
  var pronto = $("[data-pl-pronto]");
  var botaoJogar = $("[data-pl-jogar]");
  var dicaPronto = $("[data-pl-pronto-dica]");
  var caixaErro = $("[data-pl-erro]");
  var barra = $("[data-pl-barra]");
  var botaoCheia = $("[data-pl-tela-cheia]");
  var botaoMenu = $("[data-pl-menu]");
  var painel = $("[data-pl-comandos]");
  var botaoComandos = $("[data-pl-abrir-comandos]");
  var girar = $("[data-pl-girar]");
  var aviso = $("[data-pl-aviso]");

  function consulta(q) { try { return window.matchMedia(q).matches; } catch (e) { return false; } }
  var celular = consulta("(pointer: coarse)");
  // o DS fica em pé (as duas telas, uma em cima da outra); o resto, deitado
  var emPe = config.core === "nds" || config.formato === "retrato";
  var dentroDeQuadro = window.self !== window.top;
  // DENTRO DO APP (o launcher /jogos/ abre o jogo por cima da biblioteca): Voltar volta à
  // biblioteca e a tela cheia é a do app inteiro -- assim ela não fecha entre um e outro
  var app = null;
  try { if (dentroDeQuadro && window.parent.LSApp) app = window.parent.LSApp; } catch (e) { app = null; }
  var jogando = false;

  corpo.classList.add("is-abrindo");
  var voltar = $("[data-pl-voltar]");
  if (config.apk && voltar) {
    // no aplicativo (APK) não há biblioteca para voltar: o voltar do Android sai do jogo
    voltar.hidden = true;
  } else if (app && voltar) {
    voltar.addEventListener("click", function (e) { e.preventDefault(); app.fechar(); });
  } else if (dentroDeQuadro && voltar) {
    // aberta num quadro de outra página: o Voltar não faz sentido aqui
    voltar.hidden = true;
  }

  function mb(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(bytes >= 10485760 ? 0 : 1).replace(".", ",") + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }
  function mostrar(mensagem, pct) {
    status.textContent = mensagem;
    progresso.hidden = pct === null;
    progresso.classList.toggle("is-sem-numero", pct === undefined);
    if (typeof pct === "number") progresso.firstElementChild.style.width = Math.max(0, Math.min(100, pct)) + "%";
  }
  function falhou(mensagem) {
    abertura.classList.add("is-erro");
    abertura.classList.remove("is-saindo");
    mostrar(mensagem, null);
    pronto.hidden = true;
    caixaErro.hidden = false;
  }
  $("[data-pl-recarregar]").addEventListener("click", function () { location.reload(); });

  var tempoAviso = null;
  function avisar(texto, duracao) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(tempoAviso);
    tempoAviso = setTimeout(function () { aviso.hidden = true; }, duracao || 4000);
  }

  /* ---------------------------------------------------------------- baixar o jogo */
  function baixarParte(url, aoProgresso) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", url);
      xhr.responseType = "arraybuffer";
      xhr.addEventListener("progress", function (e) { aoProgresso(e.loaded); });
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300 && xhr.response) resolve(new Uint8Array(xhr.response));
        else reject(new Error("erro " + xhr.status));
      };
      xhr.onerror = function () { reject(new Error("sem conexão com o armazenamento")); };
      xhr.send();
    });
  }
  /* Um arquivo: as partes, na ordem, num bloco só do tamanho certo. */
  function baixarArquivo(item, aoProgresso) {
    var bloco = new Uint8Array(item.tamanho);
    var posicao = 0;
    return item.partes.reduce(function (promessa, url, i) {
      return promessa.then(function () {
        return baixarParte(url, function (agora) { aoProgresso(posicao + agora); }).then(function (dados) {
          if (posicao + dados.length > bloco.length) throw new Error("tamanho diferente do esperado");
          bloco.set(dados, posicao);
          posicao += dados.length;
        }, function (erro) {
          throw new Error(item.nome + (item.partes.length > 1 ? " (pedaço " + (i + 1) + " de " + item.partes.length + ")" : "") + ": " + erro.message);
        });
      });
    }, Promise.resolve()).then(function () {
      if (posicao !== bloco.length) throw new Error(item.nome + ": chegou incompleto");
      return bloco;
    });
  }
  function avisoDeTamanho(total) {
    return total > 300 * 1048576 ? " · jogo grande: no celular pode não abrir" : "";
  }
  function baixarTudo(itens) {
    var total = itens.reduce(function (t, i) { return t + i.tamanho; }, 0);
    var feitos = 0;
    var bytes = {};
    return itens.reduce(function (promessa, item) {
      return promessa.then(function () {
        return baixarArquivo(item, function (agora) {
          mostrar("Baixando o jogo: " + mb(feitos + agora) + " de " + mb(total) + avisoDeTamanho(total), total ? (feitos + agora) / total * 100 : 0);
        }).then(function (dados) {
          feitos += item.tamanho;
          bytes[item.caminho] = dados;
        });
      });
    }, Promise.resolve()).then(function () { return bytes; });
  }
  /* Do aparelho quando o jogo já está guardado (jogo-guardado.js); senão baixa e guarda. */
  function pegar(itens) {
    // no APK o jogo já está no aparelho (dentro do app): nada de guardar de novo
    if (config.apk) return baixarTudo(itens);
    var guardado = window.LSJogoGuardado;
    if (!guardado || !guardado.disponivel) return baixarTudo(itens);
    return guardado.pegarTudo(config.jogo || config.nome, itens, function (feito, total, doAparelho) {
      mostrar((doAparelho ? "Abrindo o jogo guardado no aparelho" : "Baixando o jogo (fica guardado para a próxima)") +
        ": " + mb(feito) + " de " + mb(total) + (doAparelho ? "" : avisoDeTamanho(total)), total ? feito / total * 100 : 0);
    }).then(function (r) { return r.bytes; }, function () { return baixarTudo(itens); });
  }

  /* O emulador e o núcleo, adiantados enquanto o jogo baixa (na primeira vez: depois o
     próprio emulador guarda o núcleo no aparelho). O nome segue o do emulador: "-thread"
     (PSP, DOS) e "-legacy" (sem WebGL 2). */
  var marcaDoNucleo = "ls-emulador-" + (config.nucleo || config.core);
  function adiantarEmulador() {
    var arquivos = [config.dados + "loader.js", config.dados + "emulator.min.js", config.dados + "emulator.min.css",
      config.dados + "localization/pt-BR.json"];
    var jaTem = false;
    try { jaTem = !!localStorage.getItem(marcaDoNucleo); } catch (e) { jaTem = false; }
    if (!jaTem && config.nucleo) {
      var webgl2 = false;
      try { webgl2 = !!document.createElement("canvas").getContext("webgl2"); } catch (e) { webgl2 = false; }
      var nome = config.nucleo + (config.threads ? "-thread" : "") + (webgl2 ? "" : "-legacy") + "-wasm.data";
      arquivos.push((config.nucleoExterno || config.dados + "cores/") + nome);
    }
    arquivos.forEach(function (url) {
      var link = document.createElement("link");
      link.rel = "prefetch";
      link.href = url;
      if (/^https?:/.test(url) && url.indexOf(location.origin) !== 0) link.crossOrigin = "anonymous";
      document.head.appendChild(link);
    });
  }

  /* ---------------------------------------------------------------- o ritmo do jogo (liso sempre)
     O RetroArch do emulador roda UM quadro do jogo a cada quadro que o navegador
     desenha (requestAnimationFrame). Quando o navegador entrega menos de 60 por segundo
     -- economia de bateria, taxa de atualização "inteligente" do celular (Xiaomi,
     Samsung...), um quadro que atrasou --, o jogo ia junto: a 30 por segundo, rodava na
     METADE da velocidade, lento, com o som arrastando e engasgando. Medido aqui: tela a
     30 Hz -> 30 quadros do jogo por segundo.

     O MARCA-PASSO: conta o tempo de verdade e, quando o jogo ficou para trás, roda
     na hora os quadros que faltam (a tela mostra o último). O jogo fica sempre na
     velocidade dele, e o som -- que sai de cada quadro -- não engasga. Só mexe no laço
     do emulador (a função "MainLoop_runner"); o resto da página segue normal. Quem
     confere se o quadro rodou de fato é o contador do próprio RetroArch: em tela de
     120 Hz ele mesmo pula metade das chamadas, e isso não conta como quadro. */
  var QUADRO_MS = 1000 / 60;
  var MAX_EXTRAS = 3;             // no máximo 4 quadros por desenho: nunca vira uma bola de neve
  var rafDoNavegador = window.requestAnimationFrame ? window.requestAnimationFrame.bind(window) : null;
  var ritmo = { devido: 0, agora: 0, noDesenho: false, extras: 0, recuperados: 0, trabalho: 0 };
  function quadrosDoJogo() {
    var emu = window.EJS_emulator;
    try { return emu && emu.gameManager ? emu.gameManager.getFrameNum() : -1; } catch (e) { return -1; }
  }
  function rodarQuadro(cb, t) {
    var antes = quadrosDoJogo();
    cb(t);
    var depois = quadrosDoJogo();
    // rodou um quadro do jogo (ou não dá para saber): ele conta no relógio
    if (antes < 0 || depois !== antes) ritmo.devido += QUADRO_MS;
  }
  if (rafDoNavegador) {
    window.requestAnimationFrame = function (cb) {
      if (!cb || cb.name !== "MainLoop_runner") return rafDoNavegador(cb);
      // dentro do mesmo desenho, e o jogo ainda atrás do relógio: mais um quadro, já
      if (ritmo.noDesenho && ritmo.extras < MAX_EXTRAS && ritmo.agora - ritmo.devido >= 0) {
        ritmo.extras++;
        ritmo.recuperados++;
        rodarQuadro(cb, ritmo.agora);
        return 0;
      }
      return rafDoNavegador(function (t) {
        // primeira vez, ou voltando de uma pausa longa (aba escondida): sem correr atrás
        if (!ritmo.devido || t - ritmo.devido > 250 || ritmo.devido - t > 100) ritmo.devido = t;
        ritmo.agora = t;
        ritmo.extras = 0;
        ritmo.noDesenho = true;
        var inicio = performance.now();
        try { rodarQuadro(cb, t); } finally {
          ritmo.noDesenho = false;
          // a média de quanto cada desenho pesa (ms), com os quadros recuperados juntos
          ritmo.trabalho = ritmo.trabalho * 0.9 + (performance.now() - inicio) * 0.1;
        }
      });
    };
  }

  /* ---------------------------------------------------------------- a imagem na tela toda
     O RetroArch do emulador desenha a imagem no formato do console (4:3) e põe faixas
     pretas dos lados. Aqui ele desenha ESTICADA na área toda (aspect_ratio_index 24 =
     "Full" no RetroArch), já na resolução da tela -- nítida, sem ampliar uma imagem
     pequena. O formato original continua a um toque ("Imagem" na barra): aí a área do
     jogo é que encolhe para o formato do console, e o RetroArch acompanha na hora, sem
     reiniciar o jogo. O emulador grava o retroarch.cfg ao ligar o núcleo
     (EJS_GameManager.getRetroArchCfg): a página acrescenta as duas linhas assim que a
     classe chega, antes de o núcleo ligar. */
  // O que o site muda no retroarch.cfg do emulador:
  // - a imagem esticada na área toda ("Full"), que encolhe para o formato do console no botão Imagem;
  // - no celular, mais folga no som (96 ms): aparelho mais fraco atrasa um quadro e o som
  //   estala; com a folga ele continua liso (a diferença não se sente ao jogar).
  var AJUSTES_DO_RETROARCH = [["video_aspect_ratio_auto", "false"], ["aspect_ratio_index", "24"]];
  if (celular) AJUSTES_DO_RETROARCH.push(["audio_latency", "96"]);
  function ajustarCfg(cfg) {
    AJUSTES_DO_RETROARCH.forEach(function (par) {
      var linha = par[0] + " = " + (/^\d+$/.test(par[1]) ? par[1] : '"' + par[1] + '"');
      var regra = new RegExp("^" + par[0] + " = .*$", "m");
      cfg = regra.test(cfg) ? cfg.replace(regra, linha) : cfg + linha + "\n";
    });
    return cfg;
  }
  function remendarCfg(classe) {
    if (!classe || !classe.prototype || classe.prototype.__lsTelaToda) return;
    var original = classe.prototype.getRetroArchCfg;
    if (typeof original !== "function") return;
    classe.prototype.getRetroArchCfg = function () { return ajustarCfg(String(original.apply(this, arguments) || "")); };
    classe.prototype.__lsTelaToda = true;
  }
  (function () {
    var real = window.EJS_GameManager;
    try {
      Object.defineProperty(window, "EJS_GameManager", {
        configurable: true,
        get: function () { return real; },
        set: function (classe) { real = classe; remendarCfg(classe); },
      });
    } catch (e) { /* o EJS_ready ainda tenta */ }
  })();

  var CHAVE_IMAGEM = "ls-imagem-v1";
  var imagemOriginal = emPe; // o DS (duas telas) fica no formato dele
  try { var guardada = localStorage.getItem(CHAVE_IMAGEM); if (guardada && !emPe) imagemOriginal = guardada === "original"; } catch (e) { /* padrão */ }
  function proporcaoDoJogo() {
    var emu = window.EJS_emulator, a = 0;
    try { a = Number(emu && emu.gameManager && emu.gameManager.getVideoDimensions("aspect")); } catch (e) { a = 0; }
    return a > 0.2 && a < 5 ? a : (emPe ? 256 / 384 : 4 / 3);
  }
  function medirImagem() {
    var a = proporcaoDoJogo(), l = innerWidth, h = innerHeight;
    var largura = l / h > a ? Math.round(h * a) : l;
    var altura = l / h > a ? h : Math.round(l / a);
    corpo.style.setProperty("--pl-imagem-l", largura + "px");
    corpo.style.setProperty("--pl-imagem-a", altura + "px");
  }
  function aplicarImagem() {
    corpo.classList.toggle("is-imagem-original", imagemOriginal);
    if (imagemOriginal) medirImagem();
    desenharMenuImagem();
  }

  /* O MENU IMAGEM: o formato (tela toda / original) e os gráficos */
  var menuImagem = $("[data-pl-menu-imagem]");
  var botaoMenuImagem = $("[data-pl-imagem]");
  function desenharMenuImagem() {
    if (!menuImagem) return;
    Array.prototype.forEach.call(menuImagem.querySelectorAll("[data-pl-formato]"), function (b) {
      b.setAttribute("aria-checked", (b.dataset.plFormato === "original") === imagemOriginal ? "true" : "false");
    });
    Array.prototype.forEach.call(menuImagem.querySelectorAll("[data-pl-graficos]"), function (b) {
      b.setAttribute("aria-checked", b.dataset.plGraficos === escolhaGraficos ? "true" : "false");
    });
    var agora = menuImagem.querySelector("[data-pl-graficos-agora]");
    if (agora) agora.textContent = escolhaGraficos === "auto" ? "agora: " + ({ hd: "HD", leve: "Leve" }[nivelAtual] || nivelAtual) : "";
  }
  function abrirMenuImagem(abrir) {
    if (!menuImagem) return;
    menuImagem.hidden = !abrir;
    if (botaoMenuImagem) botaoMenuImagem.setAttribute("aria-expanded", abrir ? "true" : "false");
    if (abrir) { desenharMenuImagem(); mostrarBarra(60000); var marcado = menuImagem.querySelector('[aria-checked="true"]'); if (marcado) marcado.focus(); }
    else { mostrarBarra(); devolverFoco(); }
  }
  if (menuImagem && botaoMenuImagem) {
    botaoMenuImagem.addEventListener("click", function (e) { e.stopPropagation(); abrirMenuImagem(menuImagem.hidden); });
    menuImagem.addEventListener("click", function (e) {
      var formato = e.target.closest("[data-pl-formato]");
      var graficos = e.target.closest("[data-pl-graficos]");
      if (formato) {
        imagemOriginal = formato.dataset.plFormato === "original";
        try { localStorage.setItem(CHAVE_IMAGEM, imagemOriginal ? "original" : "tela-toda"); } catch (x) { /* só não guarda */ }
        aplicarImagem();
      } else if (graficos) {
        escolhaGraficos = graficos.dataset.plGraficos;
        try { localStorage.setItem(CHAVE_GRAFICOS, escolhaGraficos); } catch (x) { /* só não guarda */ }
        aplicarGraficos(escolhaGraficos === "auto" ? "hd" : escolhaGraficos);
      }
    });
    document.addEventListener("click", function (e) {
      if (!menuImagem.hidden && !menuImagem.contains(e.target) && e.target !== botaoMenuImagem) abrirMenuImagem(false);
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !menuImagem.hidden) abrirMenuImagem(false); });
  }
  window.addEventListener("resize", function () { if (imagemOriginal) medirImagem(); });

  /* ---------------------------------------------------------------- os gráficos
     O RetroArch desenha na resolução da tela inteira -- num celular com tela de 2400
     pixels, com o filtro de imagem, são 2,6 milhões de pixels a cada quadro, só para
     esticar um jogo de 256 x 224. Aqui cada escolha tem um ORÇAMENTO de pixels: o
     emulador desenha até ele e o navegador amplia (liso) o resto. HD fica no limite
     que ainda é nítido; Leve desenha pouco mais que o dobro do jogo -- leve como o
     console, e liso do mesmo jeito.
     Automático (o padrão) começa em HD e, se o aparelho não der conta (o marca-passo
     precisando recuperar quadros e cada quadro pesando), desce sozinho para Leve. */
  var TRES_D = ["psx", "n64", "psp", "segaSaturn", "nds", "3do", "pcfx", "jaguar", "dos"].indexOf(config.core) !== -1;
  var filtroHD = (config.opcoes || {}).shader || (TRES_D ? "bicubic" : "2xScaleHQ.glslp");
  if (!celular && config.opcoesNoComputador && config.opcoesNoComputador.shader) filtroHD = config.opcoesNoComputador.shader;
  var GRAFICOS = {
    hd: { filtro: filtroHD, pixels: celular ? 1.6e6 : 3.7e6 },
    nitido: { filtro: "disabled", pixels: celular ? 2.6e6 : 4.2e6 },
    tv: { filtro: "crt-easymode.glslp", pixels: celular ? 1.6e6 : 3.7e6 },
    leve: { filtro: "disabled", pixels: celular ? 0.42e6 : 0.9e6 },
  };
  var CHAVE_GRAFICOS = "ls-graficos-v1";
  var escolhaGraficos = "auto";
  try { escolhaGraficos = localStorage.getItem(CHAVE_GRAFICOS) || "auto"; } catch (e) { escolhaGraficos = "auto"; }
  if (escolhaGraficos !== "auto" && !GRAFICOS[escolhaGraficos]) escolhaGraficos = "auto";
  var nivelAtual = escolhaGraficos === "auto" ? "hd" : escolhaGraficos;
  var dprReal = window.devicePixelRatio || 1;
  function dprLimitado() {
    var area = Math.max(1, (window.innerWidth || 1) * (window.innerHeight || 1));
    return Math.max(0.5, Math.min(dprReal, Math.sqrt(GRAFICOS[nivelAtual].pixels / area)));
  }
  // o RetroArch mede a tela pelo devicePixelRatio e pelo ResizeObserver: os dois passam pelo orçamento
  try { Object.defineProperty(window, "devicePixelRatio", { configurable: true, get: dprLimitado }); } catch (e) { /* segue na resolução cheia */ }
  if (window.ResizeObserver) {
    var ObservadorDoNavegador = window.ResizeObserver;
    var ObservadorLimitado = function (cb) {
      return new ObservadorDoNavegador(function (entradas, observador) {
        cb(entradas.map(function (e) {
          if (!e.target || !e.target.classList || !e.target.classList.contains("ejs_canvas")) return e;
          // sem o tamanho em pixels do aparelho: o RetroArch usa a medida x devicePixelRatio (limitado)
          return { target: e.target, contentRect: e.contentRect, contentBoxSize: e.contentBoxSize, borderBoxSize: e.borderBoxSize };
        }), observador);
      });
    };
    ObservadorLimitado.prototype = ObservadorDoNavegador.prototype;
    window.ResizeObserver = ObservadorLimitado;
  }
  function aplicarGraficos(nivel, avisarTambem) {
    nivelAtual = nivel;
    var emu = window.EJS_emulator;
    try {
      if (emu && emu.changeSettingOption && emu.menuOptionChanged) {
        emu.changeSettingOption("shader", GRAFICOS[nivel].filtro);
        emu.menuOptionChanged("shader", GRAFICOS[nivel].filtro);
      }
    } catch (e) { /* o filtro fica o que estava */ }
    // o RetroArch mede de novo (com o orçamento novo)
    window.dispatchEvent(new Event("resize"));
    desenharMenuImagem();
    if (avisarTambem) avisar(avisarTambem, 3500);
  }

  /* o modo leve automático: olha o marca-passo a cada segundo */
  var vigiaDoPeso = { segundosPesados: 0, ultimoRecuperado: 0, trabalho: 0 };
  setInterval(function () {
    if (!jogando || escolhaGraficos !== "auto" || nivelAtual === "leve" || document.hidden) return;
    var emu = window.EJS_emulator;
    if (emu && emu.paused) return;
    var recuperados = ritmo.recuperados - vigiaDoPeso.ultimoRecuperado;
    vigiaDoPeso.ultimoRecuperado = ritmo.recuperados;
    // muitos quadros recuperados E quadro pesado: é o aparelho (não só a tela a 30 Hz)
    var pesado = recuperados >= 8 && ritmo.trabalho >= 11;
    vigiaDoPeso.segundosPesados = pesado ? vigiaDoPeso.segundosPesados + 1 : Math.max(0, vigiaDoPeso.segundosPesados - 1);
    if (vigiaDoPeso.segundosPesados >= 3) {
      vigiaDoPeso.segundosPesados = 0;
      aplicarGraficos("leve", "Gráficos no modo Leve: o jogo roda liso neste aparelho. (Imagem, no alto, troca.)");
    }
  }, 1000);

  /* ---------------------------------------------------------------- ligar o emulador */
  function ligarEmulador(jogo, externos) {
    window.EJS_player = "#jogo";
    window.EJS_core = config.core;
    // o jogo vai como bytes; o nome (com a extensão certa) diz ao emulador o que é
    window.EJS_gameUrl = jogo;
    window.EJS_gameName = config.nome;
    window.EJS_externalFiles = externos;
    window.EJS_pathtodata = config.dados;
    window.EJS_language = "pt-BR";
    window.EJS_color = config.cor || "#ff3df2";
    window.EJS_backgroundColor = "#000000";
    // o som começa alto o bastante (o padrão do emulador é a metade)
    window.EJS_volume = 0.85;
    // quem tocou em Jogar não toca de novo
    window.EJS_startOnLoaded = true;
    // o teclado que os Comandos ensinam e o controle de Xbox pela posição dos botões
    if (config.controles) window.EJS_defaultControls = config.controles;
    // o controle na tela do celular com os nomes do console (sem "Fast/Slow" no meio)
    if (config.gamepad) window.EJS_VirtualGamepadSettings = config.gamepad;
    // PSP e DOS: o núcleo de várias linhas (a página veio isolada pelo servidor)
    if (config.threads) window.EJS_threads = true;
    // O NÚCLEO QUE NÃO MORA NO SITE (Super Nintendo, Mega Drive, fliperama...) vem do
    // pacote oficial do EmulatorJS no npm (jsDelivr), com o "plano B" do CDN dele.
    if (config.nucleoExterno && config.nucleo) {
      var n = config.nucleo, caminhos = {};
      ["-wasm.data", "-legacy-wasm.data", "-thread-wasm.data", "-thread-legacy-wasm.data"].forEach(function (fim) {
        caminhos[n + fim] = config.nucleoExterno + n + fim;
      });
      caminhos[n + ".json"] = config.nucleoExterno + "reports/" + n + ".json";
      window.EJS_paths = caminhos;
    }
    // A QUALIDADE DA IMAGEM: o filtro do console e, no computador, o mais caprichado
    // (SABR na arte 2D) e mais resolução por dentro (N64, PSP); o núcleo certo
    var opcoes = {};
    Object.keys(config.opcoes || {}).forEach(function (k) { opcoes[k] = config.opcoes[k]; });
    if (!celular) Object.keys(config.opcoesNoComputador || {}).forEach(function (k) { opcoes[k] = config.opcoesNoComputador[k]; });
    // tela de toque = controle na tela. O emulador decide pelo "nome" do navegador: o iPad
    // (que se diz Mac) e o tablet no modo computador ficavam sem controle nenhum.
    if (celular) opcoes["virtual-gamepad"] = "enabled";
    opcoes.shader = GRAFICOS[nivelAtual].filtro;
    window.EJS_defaultOptions = opcoes;
    // a versão dos ajustes do site: subiu, todo mundo começa com os novos (controle pela
    // posição, filtro novo). O jogo salvo fica em outro lugar e continua.
    window.EJS_gameID = 3;
    // fora da barra do emulador: o que não tem servidor (rede, trapaça), o que confunde
    // (gravar a tela, exportar o arquivo de save, "sair") e a tela cheia dele -- a do
    // site (em cima) leva junto os Comandos e deita o celular
    window.EJS_Buttons = {
      cheat: false, netplay: false, exitEmulation: false, cacheManager: false, screenRecord: false,
      saveSavFiles: false, loadSavFiles: false, fullscreen: false, enterFullscreen: false, exitFullscreen: false,
    };
    // os ajustes técnicos saem do menu: fica o que muda a imagem, o som e a velocidade
    window.EJS_hideSettings = ["ejs_threads", "vsync", "videoRotation", "screenshotSource", "screenshotFormat",
      "screenshotUpscale", "screenRecordFPS", "screenRecordFormat", "screenRecordUpscale", "screenRecordVideoBitrate",
      "screenRecordAudioBitrate", "menubarBehavior", "altKeyboardInput"];
    // O CONTROLE NA TELA DO CELULAR. O emulador só desenha o controle quando o toque foi
    // no botão "Start" DELE; com o jogo começando sozinho (o toque foi no Jogar do site),
    // ele achava que não era celular -- e o controle nunca aparecia. Aqui ele fica sabendo.
    window.EJS_ready = function () {
      if (celular && window.EJS_emulator) window.EJS_emulator.touch = true;
      remendarCfg(window.EJS_GameManager);
    };
    window.EJS_onGameStart = function () {
      // o emulador já copiou tudo para a pasta dele: solta as cópias daqui (memória)
      Object.keys(externos).forEach(function (chave) { delete externos[chave]; });
      window.EJS_gameUrl = null;
      try { localStorage.setItem(marcaDoNucleo, "1"); } catch (e) { /* nada */ }
      comecou();
    };
    vigiarErroDoEmulador();
    var loader = document.createElement("script");
    loader.src = config.dados + "loader.js";
    loader.onerror = function () { falhou("Não deu para abrir o emulador. Confira a internet e tente de novo."); };
    document.body.appendChild(loader);
  }

  /* O emulador escreve o progresso e os erros num texto dele (que fica por baixo da
     abertura): a abertura repete, e o erro aparece com "Tentar de novo". */
  var vigiaDoTexto = null;
  function vigiarErroDoEmulador() {
    var vigia = vigiaDoTexto = new MutationObserver(function () {
      var texto = document.querySelector("#jogo .ejs_loading_text");
      if (!texto || jogando) return;
      if (texto.classList.contains("ejs_error_text")) {
        vigia.disconnect();
        falhou(texto.textContent.replace(/\s+/g, " ").trim() || "O emulador não conseguiu abrir este jogo.");
      } else if (texto.textContent.trim()) {
        mostrar(texto.textContent.trim(), undefined);
      }
    });
    vigia.observe(document.getElementById("jogo"), { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["class"] });
  }

  /* ---------------------------------------------------------------- tela cheia e celular deitado */
  var raiz = document.documentElement;
  var podeTelaCheia = app ? app.podeTelaCheia : !!(raiz.requestFullscreen || raiz.webkitRequestFullscreen);
  function emTelaCheia() { return app ? app.emTelaCheia() : !!(document.fullscreenElement || document.webkitFullscreenElement); }
  function entrarTelaCheia() {
    if (app) return app.pedirTelaCheia(emPe);
    var pedido = raiz.requestFullscreen ? raiz.requestFullscreen({ navigationUI: "hide" }) : raiz.webkitRequestFullscreen();
    return Promise.resolve(pedido).then(function () {
      if (!celular || !screen.orientation || !screen.orientation.lock) return;
      return screen.orientation.lock(emPe ? "portrait" : "landscape").catch(function () { /* o aparelho não deixa */ });
    });
  }
  function sairTelaCheia() {
    if (app) return app.telaCheia(emPe);
    if (document.exitFullscreen) return document.exitFullscreen();
    if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
  }
  function atualizarBotaoCheia() {
    var cheia = emTelaCheia();
    corpo.classList.toggle("is-tela-cheia", cheia);
    var icone = botaoCheia.querySelector("use");
    if (icone) icone.setAttribute("href", cheia ? "#i-sair-cheia" : "#i-cheia");
    botaoCheia.querySelector("[data-pl-tela-cheia-texto]").textContent = cheia ? "Sair da tela cheia" : "Tela cheia";
  }
  botaoCheia.addEventListener("click", function () {
    if (!podeTelaCheia) {
      // o iPhone não deixa um site ocupar a tela toda; o atalho na tela de início deixa
      avisar("No iPhone: toque em Compartilhar e em “Adicionar à Tela de Início”. Aberto por lá, o jogo ocupa a tela toda.", 7000);
      return;
    }
    if (emTelaCheia()) sairTelaCheia(); else entrarTelaCheia().catch(function () {});
  });
  document.addEventListener("fullscreenchange", atualizarBotaoCheia);
  document.addEventListener("webkitfullscreenchange", atualizarBotaoCheia);
  if (app) {
    app.documento.addEventListener("fullscreenchange", atualizarBotaoCheia);
    app.documento.addEventListener("webkitfullscreenchange", atualizarBotaoCheia);
    window.addEventListener("pagehide", function () {
      app.documento.removeEventListener("fullscreenchange", atualizarBotaoCheia);
      app.documento.removeEventListener("webkitfullscreenchange", atualizarBotaoCheia);
    });
    atualizarBotaoCheia();
  }

  var girarIgnorado = false;
  function conferirGiro() {
    if (!girar) return;
    var precisa = celular && !emPe && !girarIgnorado && consulta("(orientation: portrait)");
    girar.hidden = !precisa;
  }
  if (girar) {
    $("[data-pl-girar-ignorar]").addEventListener("click", function () { girarIgnorado = true; conferirGiro(); });
    window.addEventListener("resize", conferirGiro);
    window.addEventListener("orientationchange", conferirGiro);
  }

  /* As teclas vão para o quadro do emulador (#jogo) só quando ele está com o foco: depois
     de um clique na interface do site, o foco volta para o jogo -- senão o Enter (Start)
     apertaria de novo o último botão clicado. */
  function devolverFoco() {
    if (!jogando || (painel && !painel.hidden)) return;
    var quadro = document.getElementById("jogo");
    if (quadro) quadro.focus({ preventScroll: true });
  }
  barra.addEventListener("click", function (e) {
    if (e.target.closest("button") && e.detail > 0) setTimeout(devolverFoco, 0); // clique de mouse ou toque
  });

  /* ---------------------------------------------------------------- a barra de cima */
  var tempoBarra = null;
  var alca = null;
  function esconderBarra() {
    if (!jogando || (painel && !painel.hidden) || barra.matches(":hover") || barra.contains(document.activeElement)) return;
    barra.classList.add("is-escondida");
    if (alca) alca.hidden = false;
  }
  function mostrarBarra(tempo) {
    barra.classList.remove("is-escondida");
    if (alca) alca.hidden = true;
    clearTimeout(tempoBarra);
    tempoBarra = setTimeout(esconderBarra, tempo || (celular ? 4000 : 2600));
  }
  if (celular) {
    // no celular a barra volta por uma alça no alto (um toque no jogo é botão do controle)
    alca = document.createElement("button");
    alca.type = "button";
    alca.className = "pl-alca";
    alca.hidden = true;
    alca.setAttribute("aria-label", "Mostrar a barra (Voltar, Comandos, Tela cheia)");
    alca.addEventListener("click", function () { mostrarBarra(); });
    corpo.appendChild(alca);
  } else {
    document.addEventListener("mousemove", function () { if (jogando) mostrarBarra(); }, { passive: true });
  }
  barra.addEventListener("focusin", function () { mostrarBarra(8000); });

  /* "Salvar e ajustes": a barra do emulador (salvar e carregar o jogo, som, filtro de imagem) */
  if (botaoMenu) {
    botaoMenu.hidden = true;
    botaoMenu.addEventListener("click", function () {
      var emu = window.EJS_emulator;
      if (emu && emu.menu) emu.menu.open(); // ela some sozinha depois de uns segundos
    });
  }

  /* ---------------------------------------------------------------- os comandos */
  var abas = painel ? Array.prototype.slice.call(painel.querySelectorAll("[data-pl-aba]")) : [];
  var lista = painel && painel.querySelector("[data-pl-lista]");
  function escolherAba(qual, focar) {
    if (!lista) return;
    abas.forEach(function (aba) {
      var ativa = aba.dataset.plAba === qual;
      aba.setAttribute("aria-selected", ativa ? "true" : "false");
      aba.tabIndex = ativa ? 0 : -1;
      if (ativa) lista.setAttribute("aria-labelledby", aba.id);
      if (ativa && focar) aba.focus();
    });
    lista.className = "pl-lista pl-lista--" + qual;
    Array.prototype.forEach.call(painel.querySelectorAll("[data-pl-dica]"), function (p) { p.hidden = p.dataset.plDica !== qual; });
  }
  abas.forEach(function (aba, i) {
    aba.addEventListener("click", function () { escolherAba(aba.dataset.plAba); });
    aba.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      e.preventDefault();
      escolherAba(abas[(i + (e.key === "ArrowRight" ? 1 : abas.length - 1)) % abas.length].dataset.plAba, true);
    });
  });
  function controleLigado() {
    try {
      return Array.prototype.some.call(navigator.getGamepads ? navigator.getGamepads() : [], function (g) { return g && g.connected; });
    } catch (e) { return false; }
  }
  escolherAba(controleLigado() ? "controle" : celular ? "celular" : "teclado");

  var pausadoPeloPainel = false;
  function abrirComandos(abrir) {
    if (!painel) return;
    painel.hidden = !abrir;
    botaoComandos.setAttribute("aria-expanded", abrir ? "true" : "false");
    var emu = window.EJS_emulator;
    // o jogo espera enquanto a pessoa lê (e volta de onde parou)
    try {
      if (abrir && jogando && emu && !emu.paused) { emu.pause(); pausadoPeloPainel = true; }
      if (!abrir && pausadoPeloPainel && emu) { emu.play(); pausadoPeloPainel = false; }
    } catch (e) { pausadoPeloPainel = false; }
    if (abrir) {
      escolherAba(controleLigado() ? "controle" : celular ? "celular" : (lista.className.split("--")[1] || "teclado"));
      painel.querySelector("[data-pl-fechar-comandos]").focus();
      mostrarBarra(60000);
    } else {
      mostrarBarra();
      devolverFoco();
    }
  }
  if (painel && botaoComandos) {
    botaoComandos.addEventListener("click", function () { abrirComandos(painel.hidden); });
    painel.querySelector("[data-pl-fechar-comandos]").addEventListener("click", function () { abrirComandos(false); });
    painel.addEventListener("click", function (e) { if (e.target === painel) abrirComandos(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !painel.hidden) { e.stopPropagation(); abrirComandos(false); }
    }, true);
  }

  /* ---------------------------------------------------------------- o controle de Xbox */
  window.addEventListener("gamepadconnected", function (e) {
    var nome = (e.gamepad && e.gamepad.id || "").replace(/\s*\(.*$/, "").trim();
    avisar("Controle conectado" + (nome ? ": " + nome : "") + ". Já pode jogar com ele.", 4500);
    if (painel && !painel.hidden) escolherAba("controle");
    if (!jogando && !pronto.hidden) dicaPronto.textContent = "Aperte A no controle ou toque em Jogar.";
  });
  window.addEventListener("gamepadconnected", function () {
    var emu = window.EJS_emulator;
    if (celular && jogando && emu && emu.virtualGamepad) emu.virtualGamepad.style.display = "none";
  });
  window.addEventListener("gamepaddisconnected", function () {
    avisar("Controle desconectado." + (celular ? " O controle da tela voltou." : ""), 3000);
    var emu = window.EJS_emulator;
    if (celular && jogando && emu && emu.virtualGamepad && !controleLigado()) emu.virtualGamepad.style.display = "";
  });

  /* ---------------------------------------------------------------- o controle do seu jeito (HUD)
     Como nos jogos de celular: arrastar cada botão, aumentar um só ou todos, e a
     transparência. Fica guardado no aparelho, por console (o do PlayStation é um,
     o do Super Nintendo é outro). As peças mudam pelas propriedades "translate" e
     "scale" do CSS: o emulador mede o botão a cada toque, então ele continua
     respondendo no lugar novo. */
  var hud = $("[data-pl-hud]");
  var botaoHud = $("[data-pl-hud-abrir]");
  var CHAVE_HUD = "ls-hud-v1-" + config.core;
  var ajuste = { escala: 1, opacidade: 1, pecas: {} };
  try { ajuste = Object.assign(ajuste, JSON.parse(localStorage.getItem(CHAVE_HUD) || "{}")); } catch (e) { /* padrão */ }
  var pecas = [];        // [{el, chave, nome}]
  var escolhida = null;
  var editando = false;

  function acharPecas() {
    var pai = document.querySelector("#jogo .ejs_virtualGamepad_parent");
    if (!pai) return [];
    var vistas = {};
    var lista = [];
    Array.prototype.forEach.call(pai.querySelectorAll("[class*='b_']"), function (el) {
      var classe = Array.prototype.filter.call(el.classList, function (c) { return c.indexOf("b_") === 0; })[0];
      if (!classe) return;
      // o direcional: o que se vê e se toca é a cruz de dentro
      var alvo = el.classList.contains("ejs_virtualGamepad_button") ? el : (el.querySelector(".ejs_dpad_main") || el);
      var chave = classe + (vistas[classe] ? "-" + (vistas[classe] + 1) : "");
      vistas[classe] = (vistas[classe] || 0) + 1;
      var nome = el.classList.contains("ejs_virtualGamepad_button") ? "botão " + (el.getAttribute("data-letra") || el.textContent || "").trim()
        : alvo.classList.contains("ejs_dpad_main") ? "direcional" : "analógico";
      alvo.setAttribute("data-pl-peca", chave);
      lista.push({ el: alvo, chave: chave, nome: nome });
    });
    return lista;
  }
  function aplicarPeca(p) {
    var a = ajuste.pecas[p.chave] || {};
    p.el.style.translate = (a.x || a.y) ? (a.x || 0) + "px " + (a.y || 0) + "px" : "";
    var escala = (a.s || 1) * (ajuste.escala || 1);
    p.el.style.scale = escala === 1 ? "" : String(escala);
  }
  function aplicarHud() {
    if (!pecas.length) pecas = acharPecas();
    pecas.forEach(aplicarPeca);
    var pai = document.querySelector("#jogo .ejs_virtualGamepad_parent");
    if (pai) pai.style.opacity = ajuste.opacidade < 1 ? String(ajuste.opacidade) : "";
  }
  function guardarHud() {
    try { localStorage.setItem(CHAVE_HUD, JSON.stringify(ajuste)); } catch (e) { /* só não guarda */ }
  }

  var faixaTamanho = hud && hud.querySelector("[data-pl-hud-tamanho]");
  var faixaOpacidade = hud && hud.querySelector("[data-pl-hud-opacidade]");
  function mostrarFaixas() {
    var nome = hud.querySelector("[data-pl-hud-tamanho-nome]");
    var valor = escolhida ? ((ajuste.pecas[escolhida.chave] || {}).s || 1) : (ajuste.escala || 1);
    nome.textContent = escolhida ? "Tamanho do " + escolhida.nome : "Tamanho de todos";
    faixaTamanho.value = Math.round(valor * 100);
    hud.querySelector("[data-pl-hud-tamanho-valor]").textContent = Math.round(valor * 100) + "%";
    faixaOpacidade.value = Math.round((ajuste.opacidade || 1) * 100);
    hud.querySelector("[data-pl-hud-opacidade-valor]").textContent = Math.round((ajuste.opacidade || 1) * 100) + "%";
  }
  function escolher(p) {
    pecas.forEach(function (x) { x.el.classList.toggle("is-escolhida", x === p); });
    escolhida = p;
    mostrarFaixas();
  }

  /* arrastar: o toque não chega ao emulador enquanto se edita (o jogo está parado) */
  var arrasto = null;
  function pecaDoToque(alvo) {
    var el = alvo && alvo.closest ? alvo.closest("[data-pl-peca]") : null;
    return el ? pecas.filter(function (p) { return p.el === el; })[0] : null;
  }
  function bloquearToque(e) {
    if (!editando || (hud && hud.contains(e.target))) return;
    e.stopPropagation();
    if (e.cancelable) e.preventDefault();
  }
  ["touchstart", "touchmove", "touchend", "touchcancel"].forEach(function (tipo) {
    document.addEventListener(tipo, bloquearToque, { capture: true, passive: false });
  });
  document.addEventListener("pointerdown", function (e) {
    if (!editando || hud.contains(e.target)) return;
    var p = pecaDoToque(e.target);
    if (!p) { escolher(null); return; }
    var a = ajuste.pecas[p.chave] || {};
    arrasto = { p: p, x0: e.clientX, y0: e.clientY, x: a.x || 0, y: a.y || 0, mexeu: false, id: e.pointerId };
    e.preventDefault();
  }, true);
  document.addEventListener("pointermove", function (e) {
    if (!arrasto || e.pointerId !== arrasto.id) return;
    var dx = e.clientX - arrasto.x0, dy = e.clientY - arrasto.y0;
    if (!arrasto.mexeu && Math.abs(dx) + Math.abs(dy) < 6) return;
    arrasto.mexeu = true;
    var a = ajuste.pecas[arrasto.p.chave] = ajuste.pecas[arrasto.p.chave] || {};
    a.x = Math.round(arrasto.x + dx);
    a.y = Math.round(arrasto.y + dy);
    aplicarPeca(arrasto.p);
    // não deixa sair da tela
    var r = arrasto.p.el.getBoundingClientRect();
    var ajusteX = r.left < 0 ? -r.left : r.right > innerWidth ? innerWidth - r.right : 0;
    var ajusteY = r.top < 0 ? -r.top : r.bottom > innerHeight ? innerHeight - r.bottom : 0;
    if (ajusteX || ajusteY) { a.x += Math.round(ajusteX); a.y += Math.round(ajusteY); aplicarPeca(arrasto.p); }
  }, true);
  document.addEventListener("pointerup", function (e) {
    if (!arrasto || e.pointerId !== arrasto.id) return;
    if (!arrasto.mexeu) escolher(arrasto.p); // um toque sem arrastar escolhe a peça
    arrasto = null;
  }, true);

  function abrirHud() {
    if (!hud || !jogando) return;
    pecas = acharPecas();
    if (!pecas.length) { avisar("Este jogo usa o controle de toque do próprio console."); return; }
    editando = true;
    corpo.classList.add("pl-editando");
    hud.hidden = false;
    var emu = window.EJS_emulator;
    try { if (emu && !emu.paused) { emu.pause(); pausadoPeloPainel = true; } } catch (e) { /* segue */ }
    escolher(null);
  }
  function fecharHud() {
    editando = false;
    arrasto = null;
    corpo.classList.remove("pl-editando");
    hud.hidden = true;
    escolher(null);
    guardarHud();
    var emu = window.EJS_emulator;
    try { if (pausadoPeloPainel && emu) { emu.play(); pausadoPeloPainel = false; } } catch (e) { pausadoPeloPainel = false; }
    // o analógico (nipplejs) mede a área dele de novo
    window.dispatchEvent(new Event("resize"));
    devolverFoco();
    avisar("Controle guardado neste aparelho.", 2500);
  }
  if (hud && botaoHud) {
    botaoHud.addEventListener("click", abrirHud);
    hud.querySelector("[data-pl-hud-pronto]").addEventListener("click", fecharHud);
    hud.querySelector("[data-pl-hud-restaurar]").addEventListener("click", function () {
      ajuste = { escala: 1, opacidade: 1, pecas: {} };
      aplicarHud();
      escolher(null);
    });
    faixaTamanho.addEventListener("input", function () {
      var v = Number(faixaTamanho.value) / 100;
      if (escolhida) {
        var a = ajuste.pecas[escolhida.chave] = ajuste.pecas[escolhida.chave] || {};
        a.s = v;
      } else {
        ajuste.escala = v;
      }
      aplicarHud();
      mostrarFaixas();
    });
    faixaOpacidade.addEventListener("input", function () {
      ajuste.opacidade = Number(faixaOpacidade.value) / 100;
      aplicarHud();
      mostrarFaixas();
    });
  }

  /* ---------------------------------------------------------------- começar */
  var bytesProntos = null;
  var comecando = false;
  var apresentacao = Promise.resolve();
  function jogar() {
    if (comecando || !bytesProntos) return;
    comecando = true;
    pronto.hidden = true;
    mostrar("Ligando o " + (config.sistemaNome || "console") + "…", undefined);
    // "LAZER & SPORT GAMES apresenta": a espera do emulador ligando vira apresentação
    if (window.LSIntroJogos) {
      abertura.classList.add("is-apresentando");
      apresentacao = window.LSIntroJogos.mostrar(abertura, { titulo: config.titulo || "", cor: config.cor || "", chave: "emu:" + (config.jogo || "") })
        .then(function () { abertura.classList.remove("is-apresentando"); });
    }
    var depois = function () {
      var principal = config.arquivos.filter(function (a) { return a.principal; })[0];
      var jogo = bytesProntos[principal.caminho];
      delete bytesProntos[principal.caminho];
      var externos = bytesProntos;
      bytesProntos = null;
      ligarEmulador(jogo, externos);
    };
    // no celular, o toque abre a tela cheia deitada; o emulador liga logo depois
    if (celular && podeTelaCheia && !emTelaCheia()) entrarTelaCheia().then(depois, depois);
    else depois();
  }
  botaoJogar.addEventListener("click", jogar);
  document.addEventListener("keydown", function (e) {
    if (!jogando && !pronto.hidden && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); jogar(); }
  });
  // o controle também começa: o botão de baixo (A no Xbox) na tela do Jogar
  function olharControle() {
    if (jogando || comecando) return;
    if (!pronto.hidden) {
      try {
        var pads = navigator.getGamepads ? navigator.getGamepads() : [];
        for (var i = 0; i < pads.length; i++) {
          if (pads[i] && pads[i].buttons && pads[i].buttons[0] && pads[i].buttons[0].pressed) { jogar(); return; }
        }
      } catch (e) { /* sem controle */ }
    }
    requestAnimationFrame(olharControle);
  }

  function comecou() {
    jogando = true;
    // o jogo começou: para de olhar o texto do emulador (cada toque num botão mexia nele)
    if (vigiaDoTexto) { vigiaDoTexto.disconnect(); vigiaDoTexto = null; }
    var emu = window.EJS_emulator;
    if (celular && emu && emu.virtualGamepad) {
      emu.touch = true;
      // com um controle de verdade ligado no celular, o da tela sai da frente
      emu.virtualGamepad.style.display = controleLigado() ? "none" : "";
    }
    corpo.classList.remove("is-abrindo");
    corpo.classList.add("is-jogando");
    // a abertura sai quando a apresentação termina (ou na hora, se já terminou)
    apresentacao.then(function () {
      abertura.classList.add("is-saindo");
      setTimeout(function () { abertura.hidden = true; }, 500);
    });
    if (botaoMenu) botaoMenu.hidden = false;
    aplicarImagem();
    // o filtro da escolha (o emulador guarda o último que usou: aqui vale o do site)
    aplicarGraficos(nivelAtual);
    var botaoImagem = $("[data-pl-imagem]");
    if (botaoImagem) botaoImagem.hidden = false;
    // o controle da tela do jeito que a pessoa deixou (e o botão para ajustar)
    if (celular && emu && emu.virtualGamepad) {
      aplicarHud();
      if (botaoHud) botaoHud.hidden = !pecas.length;
    }
    mostrarBarra(celular ? 5000 : 3500);
    // cada botão do controle da tela: o ÍCONE do que ele faz no próprio botão (o mesmo em
    // todo jogo: pular, atacar, atirar...), e a letra do console num selinho no canto -- o
    // jogo ainda diz "aperte B". Os de ombro e START/SELECT ficam com o nome.
    var svgNS = "http://www.w3.org/2000/svg";
    Object.keys(config.legendas || {}).forEach(function (id) {
      var rotulo = config.legendas[id] || {};
      Array.prototype.forEach.call(document.querySelectorAll("#jogo .ejs_virtualGamepad_button.b_" + id), function (el) {
        if (el.classList.contains("pl-com-icone")) return;
        var letra = (el.textContent || "").trim();
        el.setAttribute("data-letra", letra);
        if (rotulo.texto) el.setAttribute("title", letra + ": " + rotulo.texto);
        var redondo = !el.closest(".ejs_virtualGamepad_bottom") && !/\bb_(l|r|l2|r2|z)\b/.test(el.className);
        if (!rotulo.icone || !redondo) {
          if (rotulo.texto && redondo) el.setAttribute("data-acao", rotulo.texto);
          return;
        }
        el.classList.add("pl-com-icone");
        el.textContent = "";
        var icone = document.createElementNS(svgNS, "svg");
        icone.setAttribute("class", "pl-ico-botao");
        icone.setAttribute("aria-hidden", "true");
        var uso = document.createElementNS(svgNS, "use");
        uso.setAttribute("href", "#a-" + rotulo.icone);
        icone.appendChild(uso);
        el.appendChild(icone);
        var selo = document.createElement("span");
        selo.className = "pl-letra";
        selo.textContent = letra;
        el.appendChild(selo);
      });
    });
    // o menu de ajustes sem as "opções do núcleo" (nomes de variável em inglês)
    Array.prototype.forEach.call(document.querySelectorAll("#jogo .ejs_settings_main_bar"), function (el) {
      if (/núcleo|Backend Core/i.test(el.textContent)) el.style.display = "none";
    });
    devolverFoco();
    if (painel) {
      avisar(controleLigado() ? "Controle conectado. Em Comandos, lá em cima, você vê o que cada botão faz."
        : celular ? "Comandos e Tela cheia ficam no alto: toque na alça para mostrar."
          : "Em Comandos, lá em cima, você vê o que cada botão faz.", 4500);
    }
  }

  /* ---------------------------------------------------------------- abrir */
  conferirGiro();
  if (config.threads && typeof window.SharedArrayBuffer !== "function") {
    falhou("Este navegador não libera o modo que o " + (config.core === "psp" ? "PSP" : "DOS") +
      " precisa. Abra no Chrome, no Edge, no Firefox ou no Safari atualizados.");
    return;
  }
  mostrar("Abrindo o jogo…", 0);
  adiantarEmulador();
  /* O passe (jogo-passe.js, core/escudo_jogos.py): de onde baixar o jogo não vem na página.
     No APK os arquivos já vêm com o caminho de dentro do app. */
  function comPasse() {
    if (config.apk || !config.passe) return Promise.resolve(config.arquivos);
    if (!window.LSPasse) return Promise.reject(new Error("faltou uma parte da página; recarregue"));
    return window.LSPasse.pegar(config.passe, config.jogo || config.nome, function () { mostrar("Conferindo o acesso ao jogo…", 2); })
      .then(function (lista) { config.arquivos = window.LSPasse.juntar(config.arquivos, lista); return config.arquivos; });
  }
  comPasse().then(pegar).then(function (bytes) {
    bytesProntos = bytes;
    mostrar("Pronto!", 100);
    progresso.hidden = true;
    pronto.hidden = false;
    dicaPronto.textContent = controleLigado() ? "Aperte A no controle ou toque em Jogar."
      : celular ? (podeTelaCheia ? "Abre em tela cheia, " + (emPe ? "em pé." : "deitado.") : "Deite o celular para ver maior.")
        : "Ou aperte Enter. Um controle de Xbox ligado no computador também vale.";
    botaoJogar.focus({ preventScroll: true });
    requestAnimationFrame(olharControle);
  }, function (erro) {
    if (erro && erro.recusado) falhou(erro.message);
    else if (erro && erro.rede) falhou("Sem internet, e este jogo ainda não estava guardado no aparelho. Conecte e tente de novo.");
    else falhou("Não deu para baixar o jogo — " + erro.message + ".");
  });
})();
