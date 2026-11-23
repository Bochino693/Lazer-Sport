/* A tela "Fotos que faltam" (LEIA-ME-V10, seção 133).

   O Cloudinary pede pagamento para devolver as fotos; então cada foto que ainda
   não voltou é um CARD, com o "Enviar foto". A foto vai por AJAX (FormData) e,
   no servidor, para o banco (core.espelho_midia.gravar_conteudo), trocando o
   nome em todo cadastro que a usava. O card vira "Pronto", com a foto nova, e
   o número de cima desce.

   VÁRIAS DE UMA VEZ: o botão "Enviar várias fotos" ou as fotos soltas em
   qualquer lugar da tela. Primeiro só os NOMES vão ao servidor ("casar"): a
   foto que tem o nome de antes vai sozinha para o card dela; as outras abrem
   a folha "Escolha onde vai cada foto", uma de cada vez, com os cards que
   ainda faltam para tocar (e os sugeridos pelo nome em cima). Nada de <select>.

   Tudo como app: erro na janela do LSAviso (com o card aceso), toast no
   sucesso, nada de alert() nem confirm(). O ZIP solto na tela vai para o
   envio em pedaços de sempre (restaurar-fotos.js).

   O painel troca de tela sem recarregar (ls-soft-navigation.js): o script
   roda de novo a cada visita e só liga o que está na tela agora.
*/
(function () {
  "use strict";

  var raiz = document.querySelector("[data-rf]");
  if (!raiz || !raiz.querySelector("[data-fq]") || raiz.__fqLigado) return;
  raiz.__fqLigado = true;

  var URL_DA_TELA = raiz.getAttribute("data-rf-url");
  var POR_VEZ = parseInt(raiz.getAttribute("data-fq-por-vez"), 10) || 12;
  var LIMITE_MB = parseInt(raiz.getAttribute("data-fq-limite-mb"), 10) || 25;
  var csrf = (raiz.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
  var folha = document.querySelector("[data-fq-folha]");
  var soltar = raiz.querySelector("[data-fq-soltar]");
  var numeroFaltam = raiz.querySelector('[data-fq-n="faltam"]');
  var ocupado = 0;

  function aviso() { return window.LSAviso || null; }
  function toast(nivel, titulo, texto) {
    var a = aviso();
    if (a && a.toast) a.toast({ nivel: nivel, titulo: titulo, texto: texto || "" });
  }
  function janela(opcoes) {
    var a = aviso();
    if (a && a.modal) return a.modal(opcoes);
    return Promise.resolve();
  }
  function plural(n, um, varios) { return n + " " + (n === 1 ? um : varios); }

  /* ---------- o POST da tela (erro do servidor vira Error com titulo/campo) ---------- */
  function postar(dados) {
    dados.append("csrfmiddlewaretoken", csrf);
    return fetch(URL_DA_TELA, {
      method: "POST", body: dados, credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf }
    }).then(function (resposta) {
      return resposta.json().catch(function () { return null; }).then(function (json) {
        if (!resposta.ok || !json || (json.status !== "sucesso" && json.status !== "ja")) {
          var erro = new Error((json && json.msg) || "O servidor não conseguiu guardar a foto agora. Tente de novo em instantes.");
          erro.titulo = (json && json.titulo) || "Não deu para enviar";
          erro.campo = json && json.campo;
          throw erro;
        }
        return json;
      });
    }, function () {
      var queda = new Error("A conexão caiu antes de a foto chegar. Confira a internet e envie de novo.");
      queda.titulo = "Sem conexão";
      queda.rede = true;
      throw queda;
    });
  }

  /* ---------- os cards ---------- */
  function cards() { return Array.prototype.slice.call(raiz.querySelectorAll("[data-fq-card]")); }
  function pendentes() {
    return cards().filter(function (c) { return !c.classList.contains("is-pronto") && !c.classList.contains("provisoria"); });
  }
  function cardDoNome(nome) {
    return cards().filter(function (c) { return c.getAttribute("data-nome") === nome; })[0] || null;
  }

  function contarGrupo(card) {
    var grupo = card.closest("[data-fq-grupo]");
    if (!grupo) return;
    var selo = grupo.querySelector("[data-fq-grupo-n]");
    var falta = grupo.querySelectorAll("[data-fq-card]:not(.is-pronto)").length;
    if (selo) {
      selo.textContent = String(falta);
      selo.classList.toggle("ok", falta === 0);
    }
  }

  function atualizarFaltam(n) {
    if (!numeroFaltam || typeof n !== "number") return;
    numeroFaltam.textContent = String(n);
    var nota = numeroFaltam.parentNode.querySelector("[data-rf-nota-faltando]");
    if (nota) nota.textContent = n === 0 ? "nenhuma foto do site falta" : (n === 1 ? "foto" : "fotos") + " para enviar, uma por card";
  }

  function marcarPronto(card, url) {
    card.classList.remove("is-enviando", "is-erro");
    card.classList.add("is-pronto");
    card.removeAttribute("aria-invalid");
    var foto = card.querySelector("[data-fq-foto]");
    var estado = card.querySelector("[data-fq-estado]");
    if (foto && url) {
      var vazio = foto.querySelector(".ls-fq-card-vazio");
      if (vazio) vazio.remove();
      var img = foto.querySelector("img");
      if (!img) {
        img = document.createElement("img");
        img.decoding = "async";
        foto.insertBefore(img, foto.firstChild);
      }
      img.alt = "Foto de " + (card.getAttribute("data-titulo") || "");
      img.src = url;
    }
    if (estado) estado.innerHTML = '<i class="bi bi-check-circle-fill" aria-hidden="true"></i> Pronto';
    var botao = card.querySelector("[data-fq-enviar]");
    if (botao) {
      botao.classList.remove("ls-rf-botao--principal");
      botao.querySelector("[data-fq-rotulo]").textContent = "No site";
      botao.querySelector("i").className = "bi bi-check2-circle";
      botao.disabled = true;
    }
    contarGrupo(card);
  }

  function marcarEnviando(card, sim) {
    card.classList.toggle("is-enviando", sim);
    var botao = card.querySelector("[data-fq-enviar]");
    if (!botao) return;
    botao.disabled = sim;
    var rotulo = botao.querySelector("[data-fq-rotulo]");
    var icone = botao.querySelector("i");
    if (sim) {
      botao.__rotulo = rotulo.textContent;
      rotulo.textContent = "Enviando…";
      icone.className = "bi bi-arrow-repeat ls-rf-gira";
    } else if (botao.__rotulo) {
      rotulo.textContent = botao.__rotulo;
      icone.className = "bi bi-camera";
    }
  }

  function acender(card, erro) {
    card.classList.add("is-erro");
    card.setAttribute("aria-invalid", "true");
    if (card.hidden) mostrar(card);
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    return janela({
      nivel: "erro",
      titulo: erro.titulo || "Não deu para enviar",
      texto: (card.getAttribute("data-titulo") ? card.getAttribute("data-titulo") + ": " : "") + erro.message,
      icone: erro.rede ? "alerta" : "arquivo-x"
    });
  }

  function confere(card, arquivo) {
    var aceita = card.getAttribute("data-aceita") || "image/*";
    var foto = /^image\//.test(arquivo.type) || /\.(jpe?g|png|webp|gif|avif|heic|heif)$/i.test(arquivo.name);
    var glb = /\.glb$/i.test(arquivo.name);
    if (aceita.indexOf("glb") >= 0 ? !glb : !foto) {
      var e = new Error("O arquivo “" + arquivo.name + "” não é " + (aceita.indexOf("glb") >= 0 ? "um arquivo 3D (.glb)." : "uma foto (JPG, PNG ou WebP)."));
      e.titulo = "Este arquivo não serve";
      return e;
    }
    if (arquivo.size > LIMITE_MB * 1024 * 1024) {
      var g = new Error("A foto “" + arquivo.name + "” passa de " + LIMITE_MB + " MB. Envie uma versão menor.");
      g.titulo = "Foto grande demais";
      return g;
    }
    return null;
  }

  /* Envia UMA foto para UM card. Resolve com true (voltou) ou false (erro já mostrado). */
  function enviar(card, arquivo, silencioso) {
    var problema = confere(card, arquivo);
    if (problema) return acender(card, problema).then(function () { return false; });
    card.classList.remove("is-erro");
    card.removeAttribute("aria-invalid");
    marcarEnviando(card, true);
    ocupado += 1;
    var dados = new FormData();
    dados.append("acao", "enviar");
    dados.append("nome", card.getAttribute("data-nome"));
    dados.append("arquivo", arquivo, arquivo.name);
    return postar(dados).then(function (json) {
      ocupado -= 1;
      if (json.status === "ja") {
        marcarEnviando(card, false);
        marcarPronto(card, null);
        toast("info", json.titulo || "Esta foto já voltou", json.msg || "");
        return true;
      }
      marcarPronto(card, json.url);
      card.classList.remove("provisoria");
      atualizarFaltam(json.faltam);
      if (!silencioso) toast("sucesso", "Foto de volta", (card.getAttribute("data-titulo") || "A foto") + " já aparece no site.");
      return true;
    }, function (erro) {
      ocupado -= 1;
      marcarEnviando(card, false);
      return acender(card, erro).then(function () { return false; });
    });
  }

  /* ---------- "Mostrar mais": 12 de cada vez (a fileira de 4 sempre fecha) ---------- */
  function mostrar(card) {
    card.hidden = false;
    card.removeAttribute("data-fq-oculto");
  }
  function acertarMais(grupo) {
    var botao = grupo.querySelector("[data-fq-mais]");
    if (!botao) return;
    var resto = grupo.querySelectorAll("[data-fq-card][data-fq-oculto]").length;
    botao.hidden = resto === 0;
    var texto = botao.querySelector("[data-fq-mais-texto]");
    var proximas = Math.min(POR_VEZ, resto);
    if (texto) texto.textContent = "Mostrar mais " + plural(proximas, "foto", "fotos") + (resto > POR_VEZ ? " de " + resto : "");
  }
  Array.prototype.forEach.call(raiz.querySelectorAll("[data-fq-grupo]"), function (grupo) {
    acertarMais(grupo);
    var botao = grupo.querySelector("[data-fq-mais]");
    if (!botao) return;
    botao.addEventListener("click", function () {
      Array.prototype.slice.call(grupo.querySelectorAll("[data-fq-card][data-fq-oculto]"), 0, POR_VEZ).forEach(mostrar);
      acertarMais(grupo);
    });
  });

  /* ---------- o "Enviar foto" de cada card ---------- */
  raiz.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-fq-enviar]");
    if (!botao || botao.disabled) return;
    var card = botao.closest("[data-fq-card]");
    var entrada = card && card.querySelector("[data-fq-arquivo]");
    if (entrada) entrada.click();
  });
  raiz.addEventListener("change", function (evento) {
    var entrada = evento.target.closest("[data-fq-arquivo]");
    if (!entrada || !entrada.files || !entrada.files.length) return;
    var card = entrada.closest("[data-fq-card]");
    var arquivo = entrada.files[0];
    entrada.value = "";
    enviar(card, arquivo);
  });

  /* ---------- várias de uma vez: casar pelo nome, o resto na folha ---------- */
  var fila = [];
  var atual = null;
  var totalDaFolha = 0;
  var semLugar = 0;

  function varias(lista) {
    var arquivos = Array.prototype.slice.call(lista || []);
    if (!arquivos.length) return;
    var zips = arquivos.filter(function (a) { return /\.zip$/i.test(a.name); });
    var fotos = arquivos.filter(function (a) { return !/\.zip$/i.test(a.name); });
    if (zips.length && raiz.__rfEnviarTodos) {
      var outras = raiz.querySelector(".ls-fq-outras");
      if (outras) outras.open = true;
      raiz.__rfEnviarTodos(zips);
    }
    if (!fotos.length) return;
    if (!pendentes().length) {
      toast("info", "Nenhuma foto falta", "Todas as fotos do site já estão no banco.");
      return;
    }
    var dados = new FormData();
    dados.append("acao", "casar");
    fotos.forEach(function (a) { dados.append("arquivos", a.name); });
    postar(dados).then(function (json) {
      var resultado = json.resultado || [];
      var casadas = [];
      var soltas = [];
      resultado.forEach(function (item, i) {
        var card = item.nome ? cardDoNome(item.nome) : null;
        if (card && !card.classList.contains("is-pronto")) casadas.push({ card: card, arquivo: fotos[i] });
        else soltas.push({ arquivo: fotos[i], candidatos: item.candidatos || [] });
      });
      var voltaram = 0;
      var cadeia = Promise.resolve();
      casadas.forEach(function (par) {
        cadeia = cadeia.then(function () {
          return enviar(par.card, par.arquivo, true).then(function (ok) { if (ok) voltaram += 1; });
        });
      });
      return cadeia.then(function () {
        if (voltaram) {
          toast("sucesso", voltaram === 1 ? "1 foto foi sozinha para o card dela" : voltaram + " fotos foram sozinhas para os cards delas",
            "Pelo nome que tinham antes. Já aparecem no site.");
        }
        if (soltas.length) abrirFolha(soltas);
      });
    }, function (erro) {
      return janela({ nivel: "erro", titulo: erro.titulo, texto: erro.message, icone: erro.rede ? "alerta" : "arquivo-x" });
    });
  }

  var variasBotao = raiz.querySelector("[data-fq-varias]");
  var variasEntrada = raiz.querySelector("[data-fq-varias-arquivos]");
  if (variasBotao && variasEntrada) {
    variasBotao.addEventListener("click", function () { variasEntrada.click(); });
    variasEntrada.addEventListener("change", function () {
      var lista = Array.prototype.slice.call(variasEntrada.files || []);
      variasEntrada.value = "";
      varias(lista);
    });
  }

  /* as fotos soltas em qualquer lugar da tela (a zona do ZIP cuida das dela) */
  var arrastando = 0;
  function temArquivos(evento) {
    var tipos = evento.dataTransfer && evento.dataTransfer.types;
    return !!tipos && Array.prototype.indexOf.call(tipos, "Files") >= 0;
  }
  function naZonaDoZip(evento) { return !!(evento.target.closest && evento.target.closest("[data-rf-zona]")); }
  raiz.addEventListener("dragenter", function (evento) {
    if (!temArquivos(evento) || naZonaDoZip(evento)) return;
    evento.preventDefault();
    arrastando += 1;
    if (soltar) soltar.hidden = false;
  });
  raiz.addEventListener("dragover", function (evento) {
    if (!temArquivos(evento) || naZonaDoZip(evento)) return;
    evento.preventDefault();
    if (soltar) soltar.hidden = false;
  });
  raiz.addEventListener("dragleave", function (evento) {
    if (!temArquivos(evento)) return;
    arrastando = Math.max(0, arrastando - 1);
    if (!arrastando && soltar) soltar.hidden = true;
  });
  raiz.addEventListener("drop", function (evento) {
    arrastando = 0;
    if (soltar) soltar.hidden = true;
    if (!temArquivos(evento) || naZonaDoZip(evento)) return;
    evento.preventDefault();
    varias(evento.dataTransfer.files);
  });

  /* ---------- a folha "Escolha onde vai cada foto" ---------- */
  var folhaImg = folha && folha.querySelector("[data-fq-folha-img]");
  var folhaArquivo = folha && folha.querySelector("[data-fq-folha-arquivo]");
  var folhaContador = folha && folha.querySelector("[data-fq-folha-contador]");
  var sugeridos = folha && folha.querySelector("[data-fq-sugeridos]");
  var sugeridosRotulo = folha && folha.querySelector("[data-fq-sugeridos-rotulo]");
  var alvos = folha && folha.querySelector("[data-fq-alvos]");
  var busca = folha && folha.querySelector("[data-fq-busca]");
  var focoAntes = null;
  var urlDaPrevia = "";

  function alvo(card) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "ls-fq-alvo";
    b.setAttribute("data-fq-alvo", card.getAttribute("data-nome"));
    b.innerHTML = '<i aria-hidden="true"></i><span><strong></strong><small></small></span><b class="ls-fq-alvo-tipo"></b>';
    b.querySelector("i").className = "bi " + (card.getAttribute("data-icone") || "bi-image");
    b.querySelector("strong").textContent = card.getAttribute("data-titulo") || card.getAttribute("data-nome");
    b.querySelector("small").textContent = card.getAttribute("data-detalhe") || "";
    b.querySelector(".ls-fq-alvo-tipo").textContent = card.getAttribute("data-tipo-titulo") || "";
    b.setAttribute("data-busca", ((card.getAttribute("data-titulo") || "") + " " + (card.getAttribute("data-detalhe") || "") + " " +
      (card.getAttribute("data-tipo-titulo") || "") + " " + card.getAttribute("data-nome")).toLowerCase());
    return b;
  }

  function desenharAlvos() {
    if (!alvos || !atual) return;
    sugeridos.innerHTML = "";
    alvos.innerHTML = "";
    var lista = pendentes();
    var sugeridas = (atual.candidatos || []).map(cardDoNome).filter(function (c) { return c && lista.indexOf(c) >= 0; });
    sugeridas.forEach(function (c) { sugeridos.appendChild(alvo(c)); });
    sugeridos.hidden = !sugeridas.length;
    sugeridosRotulo.hidden = !sugeridas.length;
    lista.forEach(function (c) { alvos.appendChild(alvo(c)); });
    filtrar();
  }

  function filtrar() {
    if (!alvos) return;
    var termo = (busca && busca.value || "").trim().toLowerCase();
    Array.prototype.forEach.call(alvos.querySelectorAll("[data-fq-alvo]"), function (b) {
      b.hidden = !!termo && b.getAttribute("data-busca").indexOf(termo) < 0;
    });
  }
  if (busca) busca.addEventListener("input", filtrar);

  function abrirFolha(soltas) {
    if (!folha) return;
    soltas.forEach(function (s) { fila.push(s); });
    totalDaFolha += soltas.length;
    if (!folha.hidden) {
      atualizarContador();
      return;
    }
    semLugar = 0;
    focoAntes = document.activeElement;
    folha.hidden = false;
    document.documentElement.classList.add("ls-fq-folha-aberta");
    requestAnimationFrame(function () { folha.classList.add("is-aberta"); });
    proxima();
  }

  function atualizarContador() {
    if (!folhaContador) return;
    var feitas = totalDaFolha - fila.length;
    folhaContador.textContent = "Foto " + Math.min(totalDaFolha, feitas) + " de " + totalDaFolha +
      (fila.length ? " · depois desta, " + plural(fila.length, "foto", "fotos") : "");
  }

  function proxima() {
    if (urlDaPrevia) {
      URL.revokeObjectURL(urlDaPrevia);
      urlDaPrevia = "";
    }
    atual = fila.shift() || null;
    if (!atual) return fecharFolha(true);
    if (!pendentes().length) {
      semLugar += 1 + fila.length;
      fila = [];
      atual = null;
      return fecharFolha(true);
    }
    urlDaPrevia = URL.createObjectURL(atual.arquivo);
    folhaImg.src = urlDaPrevia;
    folhaArquivo.textContent = atual.arquivo.name;
    if (busca) busca.value = "";
    atualizarContador();
    desenharAlvos();
    var caixa = folha.querySelector(".ls-fq-folha-caixa");
    if (caixa) {
      caixa.scrollTop = 0;
      caixa.focus({ preventScroll: true });
    }
  }

  function fecharFolha(terminou) {
    if (!folha || folha.hidden) return;
    if (!terminou && atual) semLugar += 1 + fila.length;
    fila = [];
    atual = null;
    totalDaFolha = 0;
    if (urlDaPrevia) {
      URL.revokeObjectURL(urlDaPrevia);
      urlDaPrevia = "";
    }
    folha.classList.remove("is-aberta");
    document.documentElement.classList.remove("ls-fq-folha-aberta");
    setTimeout(function () { folha.hidden = true; }, 220);
    if (focoAntes && focoAntes.focus) focoAntes.focus({ preventScroll: true });
    if (semLugar) {
      toast("info", plural(semLugar, "foto ficou", "fotos ficaram") + " sem lugar",
        "Quando quiser, envie de novo e toque no card certo.");
    }
    semLugar = 0;
  }

  if (folha) {
    folha.addEventListener("click", function (evento) {
      if (evento.target.closest("[data-fq-fechar]")) return fecharFolha(false);
      if (evento.target.closest("[data-fq-pular]")) {
        semLugar += 1;
        return proxima();
      }
      var escolha = evento.target.closest("[data-fq-alvo]");
      if (!escolha || !atual || escolha.disabled) return;
      var card = cardDoNome(escolha.getAttribute("data-fq-alvo"));
      if (!card) return;
      Array.prototype.forEach.call(folha.querySelectorAll("[data-fq-alvo]"), function (b) { b.disabled = true; });
      escolha.classList.add("is-enviando");
      var arquivo = atual.arquivo;
      enviar(card, arquivo).then(function (ok) {
        if (ok) proxima();
        else desenharAlvos();
      });
    });
    folha.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") {
        evento.preventDefault();
        fecharFolha(false);
      }
    });
  }

  /* ---------- a exportação (ZIP) e as cópias do repositório também tiram cards ---------- */
  raiz.addEventListener("fq:voltaram", function (evento) {
    (evento.detail || []).forEach(function (item) {
      var card = cardDoNome(item.nome) || cardDoNome("banco/" + item.nome);
      if (card && !card.classList.contains("is-pronto")) marcarPronto(card, item.url || "");
    });
  });
  raiz.addEventListener("fq:numeros", function (evento) {
    var d = evento.detail || {};
    if (typeof d.faltando_site === "number") atualizarFaltam(d.faltando_site);
    if (!d.pendentes) return;
    var ainda = {};
    d.pendentes.forEach(function (nome) { ainda[nome] = true; });
    pendentes().forEach(function (card) {
      if (!ainda[card.getAttribute("data-nome")]) marcarPronto(card, "");
    });
  });
})();
