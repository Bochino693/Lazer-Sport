/* ======================================================================
   O ENVIO DOS ARQUIVOS DE UM JOGO DE CONSOLE (.cue/.bin, ROM, BIOS).

   Usado pelo painel (/site/jogos/: a seção "Jogo de console" da janela do
   jogo e a janela "Arquivos do jogo") e pelo /system/ (a página "Arquivos
   do jogo" do admin). O servidor do outro lado é core/emulador_envio.py.

   1. CONFERIR. Ao escolher os arquivos, vai ao site só o nome, o tamanho
      e o COMEÇO de cada um (e o fim dos .zip) -- o bastante para ler o
      .cue, ver se falta alguma faixa e reconhecer o sistema --, sem subir
      o disco. A resposta diz o que falta, pelo nome.
   2. ENVIAR. O site devolve o plano: cada arquivo em PEDAÇOS de ~9 MB (o
      que o Cloudinary aceita) ou inteiro (o balde de jogos grandes). Cada
      pedaço sai DIRETO deste navegador para o armazenamento, três de cada
      vez -- o disco não passa pelo servidor do site.
   3. CONFIRMAR. O site confere pedaço por pedaço e guarda o conjunto.

   Não depende do painel (Painel.*): a página só informa os elementos e o
   endereço que recebe as ações.
   ====================================================================== */
(function (global) {
  "use strict";

  var INDICES = ["cue", "ccd", "toc", "m3u"];
  var PAPEIS = { jogo: "abre o jogo", disco: "disco", faixa: "faixa", bios: "BIOS" };
  var SIMULTANEOS = 3;
  var ORCAMENTO_DE_TRECHOS = 8 * 1048576;

  function ext(nome) { var i = nome.lastIndexOf("."); return i < 0 ? "" : nome.slice(i + 1).toLowerCase(); }
  function mb(bytes) { return bytes >= 1048576 ? (bytes / 1048576).toFixed(bytes >= 10485760 ? 0 : 1).replace(".", ",") + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB"; }
  function ordemNatural(a, b) { return a.name.localeCompare(b.name, "pt-BR", { numeric: true, sensitivity: "base" }); }
  function el(id) { return document.getElementById(id); }
  function item(lista, conteudo, classe) { var li = document.createElement("li"); if (classe) li.className = classe; li.textContent = conteudo; lista.appendChild(li); }
  function mesmaOrigem(url) { try { return new URL(url, global.location.href).origin === global.location.origin; } catch (e) { return false; } }

  /* Um POST que volta JSON, com o progresso do envio. Do site: a resposta tem status "sucesso". */
  function postar(url, dados, aoProgresso, doSite) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      if (doSite) xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      if (aoProgresso) xhr.upload.addEventListener("progress", function (e) { aoProgresso(e.loaded); });
      xhr.onload = function () {
        var json = null;
        try { json = JSON.parse(xhr.responseText); } catch (e) { json = null; }
        if (xhr.status >= 200 && xhr.status < 300 && json && (!doSite || json.status === "sucesso")) resolve(json);
        else reject(new Error((json && (json.msg || (json.error && json.error.message))) || "o servidor recusou (erro " + xhr.status + ")"));
      };
      xhr.onerror = function () { reject(new Error("a conexão caiu durante o envio")); };
      xhr.send(dados);
    });
  }

  function Envio(o) {
    this.o = o;
    this.conferencia = null;
    this.vez = 0;
  }

  Envio.prototype.dados = function (acao, campos) {
    var dados = new FormData();
    dados.set("csrfmiddlewaretoken", this.o.csrf);
    dados.set("action", acao);
    Object.keys(campos || {}).forEach(function (k) { if (campos[k] !== undefined && campos[k] !== null) dados.set(k, campos[k]); });
    return dados;
  };
  Envio.prototype.postarAcao = function (acao, campos) {
    return postar(this.o.url, this.dados(acao, campos), null, true);
  };
  Envio.prototype.arquivos = function () { return Array.prototype.slice.call(this.o.campo.files || []); };
  Envio.prototype.temArquivos = function () { return !!(this.o.campo.files && this.o.campo.files.length); };
  Envio.prototype.limpar = function () {
    this.conferencia = null;
    this.vez += 1;
    el(this.o.prefixo + "Resultado").classList.add("d-none");
    el(this.o.prefixo + "ProgressoCaixa").classList.add("d-none");
    if (this.o.aoMudar) this.o.aoMudar(false, null);
  };
  Envio.prototype.mostrar = function (analise) {
    var p = this.o.prefixo;
    el(p + "Resultado").classList.remove("d-none");
    el(p + "Resumo").textContent = analise.ok ? "✓ " + analise.resumo : "Ainda não dá para publicar";
    el(p + "Como").textContent = analise.como === "cabeçalho" ? "reconhecido pelo conteúdo" : analise.como === "extensão" ? "reconhecido pela extensão" : analise.como === "escolhido" ? "sistema escolhido" : "";
    var lista = el(p + "Lista"); lista.innerHTML = "";
    // o que o cabeçalho do arquivo diz: título interno, formato, se a ROM está íntegra
    (analise.ficha || []).forEach(function (linha) { item(lista, "🔎 " + linha, "text-info"); });
    (analise.arquivos || []).forEach(function (a) {
      item(lista, "• " + a.nome + " — " + (PAPEIS[a.papel] || a.papel) + (a.disco ? " do disco " + a.disco : "") + " · " + mb(a.tamanho));
    });
    (analise.ignorados || []).forEach(function (nome) { item(lista, "– " + nome + " — fica de fora", "text-muted"); });
    var erros = el(p + "Erros"); erros.innerHTML = "";
    (analise.erros || []).forEach(function (e) { item(erros, e); });
    var avisos = el(p + "Avisos"); avisos.innerHTML = "";
    (analise.avisos || []).forEach(function (a) { item(avisos, a); });
  };
  Envio.prototype.progresso = function (feito, total, rotulo) {
    var p = this.o.prefixo;
    el(p + "ProgressoCaixa").classList.remove("d-none");
    var pct = total ? Math.min(100, Math.round(feito / total * 100)) : 0;
    el(p + "Progresso").style.width = pct + "%";
    var texto = rotulo + " · " + mb(feito) + " de " + mb(total) + " (" + pct + "%)";
    el(p + "ProgressoTexto").textContent = texto;
    if (this.o.aoProgresso) this.o.aoProgresso(texto, pct);
  };

  /* Confere o conjunto. Com `jogoId`, volta também o plano de envio. */
  Envio.prototype.conferir = function (jogoId) {
    var self = this, arquivos = this.arquivos(), cfg = this.o.config;
    if (!arquivos.length) { this.limpar(); return Promise.resolve(null); }
    if (arquivos.length > cfg.max_arquivos + 20) return Promise.reject(new Error("São arquivos demais: o limite é " + cfg.max_arquivos + " por jogo."));
    // o começo de cada arquivo (índices e o que não é faixa primeiro), até uns 8 MB
    var ordem = arquivos.slice().sort(function (a, b) {
      var pa = INDICES.indexOf(ext(a.name)) >= 0 ? 0 : (ext(a.name) === "bin" || ext(a.name) === "img") ? 2 : 1;
      var pb = INDICES.indexOf(ext(b.name)) >= 0 ? 0 : (ext(b.name) === "bin" || ext(b.name) === "img") ? 2 : 1;
      return pa - pb || ordemNatural(a, b);
    });
    var partes = [], pos = 0, trechoDe = new Map();
    ordem.forEach(function (arq) {
      var t = {};
      var cabeca = Math.min(arq.size, cfg.cabeca);
      if (cabeca && pos + cabeca <= ORCAMENTO_DE_TRECHOS) { partes.push(arq.slice(0, cabeca)); t.cabeca = [pos, cabeca]; pos += cabeca; }
      if ((ext(arq.name) === "zip" || ext(arq.name) === "7z") && arq.size > cfg.cabeca && pos + cfg.cauda <= ORCAMENTO_DE_TRECHOS) {
        partes.push(arq.slice(arq.size - cfg.cauda)); t.cauda = [pos, cfg.cauda]; pos += cfg.cauda;
      }
      trechoDe.set(arq, t);
    });
    var manifesto = arquivos.map(function (arq) {
      var t = trechoDe.get(arq) || {};
      return { nome: arq.name, tamanho: arq.size, cabeca: t.cabeca || null, cauda: t.cauda || null };
    });
    // o jogo particular (só a equipe vê) usa qualquer console reconhecido
    var particular = this.o.particular && this.o.particular.checked ? "1" : "";
    var dados = this.dados("emulador_conferir", { sistema: this.o.sistema.value || "auto", particular: particular, manifesto: JSON.stringify(manifesto), id: jogoId || null });
    dados.set("trechos", new Blob(partes, { type: "application/octet-stream" }), "trechos.bin");
    var minhaVez = ++this.vez;
    if (!jogoId) {
      el(this.o.prefixo + "Resultado").classList.remove("d-none");
      el(this.o.prefixo + "Resumo").textContent = "Conferindo os arquivos…";
      el(this.o.prefixo + "Como").textContent = "";
    }
    return postar(this.o.url, dados, null, true).then(function (json) {
      if (minhaVez !== self.vez) return null;  // outra seleção chegou depois
      self.conferencia = json;
      self.mostrar(json.analise);
      if (self.o.aoMudar) self.o.aoMudar(json.analise.ok, json);
      return json;
    });
  };

  /* Um pedaço: PUT no balde, ou POST para o Cloudinary/o site com os campos assinados. */
  Envio.prototype.enviarParte = function (parte, arquivo, aoProgresso) {
    var fatia = arquivo.slice(parte.inicio, parte.fim);
    if (parte.metodo === "PUT") {
      return new Promise(function (resolve, reject) {
        var xhr = new XMLHttpRequest();
        xhr.open("PUT", parte.url);
        xhr.setRequestHeader("Content-Type", "application/octet-stream");
        xhr.upload.addEventListener("progress", function (e) { aoProgresso(e.loaded); });
        xhr.onload = function () { if (xhr.status >= 200 && xhr.status < 300) resolve({}); else reject(new Error("o armazenamento recusou (erro " + xhr.status + ")")); };
        xhr.onerror = function () { reject(new Error("o envio não passou: confira a internet e o CORS do balde (LEIA-ME)")); };
        xhr.send(fatia);
      });
    }
    var dados = new FormData();
    var doSite = mesmaOrigem(parte.url);
    if (doSite) dados.set("csrfmiddlewaretoken", this.o.csrf);
    Object.keys(parte.campos || {}).forEach(function (k) { dados.set(k, parte.campos[k]); });
    dados.set("file", fatia, parte.id.split("/").pop() || "parte");
    return postar(parte.url, dados, aoProgresso, doSite);
  };

  /* Confere de novo (com o jogo salvo, para vir o plano), sobe cada pedaço e pede ao site que confira e guarde. */
  Envio.prototype.enviar = function (jogoId) {
    var self = this, arquivos = this.arquivos();
    var porNome = new Map(arquivos.map(function (a) { return [a.name.normalize("NFC"), a]; }));
    return this.conferir(jogoId).then(function (json) {
      if (!json) throw new Error("selecione os arquivos de novo.");
      if (!json.analise.ok) throw new Error(json.analise.erros[0] || "os arquivos não fecham.");
      var usados = json.analise.arquivos.map(function (a) { return a.enviado; });
      var tarefas = [];
      (json.envios || []).forEach(function (envio) {
        var arquivo = porNome.get(envio.enviado.normalize("NFC"));
        if (!arquivo) throw new Error("“" + envio.enviado + "” saiu da seleção: escolha os arquivos de novo.");
        envio.partes.forEach(function (parte, i) { tarefas.push({ envio: envio, parte: parte, arquivo: arquivo, n: i + 1 }); });
      });
      var total = tarefas.reduce(function (t, x) { return t + (x.parte.fim - x.parte.inicio); }, 0);
      var feitoPor = new Map(), respostas = {}, proxima = 0, rotulo = "Enviando";
      function contar() {
        var feito = 0;
        feitoPor.forEach(function (v) { feito += v; });
        self.progresso(feito, total, rotulo);
      }
      function trabalhador() {
        if (proxima >= tarefas.length) return Promise.resolve();
        var t = tarefas[proxima++];
        var nome = "“" + t.envio.nome + "”" + (t.envio.partes.length > 1 ? " (pedaço " + t.n + " de " + t.envio.partes.length + ")" : "");
        rotulo = "Enviando " + nome;
        return self.enviarParte(t.parte, t.arquivo, function (feito) { feitoPor.set(t.parte.id, feito); contar(); })
          .then(function (resposta) {
            feitoPor.set(t.parte.id, t.parte.fim - t.parte.inicio);
            contar();
            respostas[t.parte.id] = resposta;
            return trabalhador();
          }, function (erro) {
            throw new Error(nome + ": " + erro.message + ".");
          });
      }
      var levas = [];
      for (var i = 0; i < Math.min(SIMULTANEOS, tarefas.length); i++) levas.push(trabalhador());
      return Promise.all(levas).then(function () {
        self.progresso(total, total, "Conferindo no site");
        var dados = self.dados("emulador_confirmar", {
          id: jogoId, sistema: self.o.sistema.value || "auto", plano: json.plano, respostas: JSON.stringify(respostas),
          particular: self.o.particular && self.o.particular.checked ? "1" : "",
        });
        arquivos.forEach(function (a) {
          if (INDICES.indexOf(ext(a.name)) >= 0 && usados.indexOf(a.name.normalize("NFC")) >= 0) dados.append("indices", a, a.name);
        });
        return postar(self.o.url, dados, null, true);
      });
    });
  };

  global.LSEmuladorEnvio = {
    /* opcoes: { prefixo, campo, sistema, url, csrf, config, aoMudar, aoProgresso } -- os elementos de resultado e
       progresso têm o id <prefixo>Resultado, <prefixo>Resumo, <prefixo>Como, <prefixo>Lista,
       <prefixo>Erros, <prefixo>Avisos, <prefixo>ProgressoCaixa, <prefixo>Progresso, <prefixo>ProgressoTexto. */
    criar: function (opcoes) { return new Envio(opcoes); },
    mb: mb,
  };
})(window);
