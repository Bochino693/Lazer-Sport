/* A tela "Restaurar fotos" (LEIA-ME-V10, seção 130).

   O dono envia a exportação do Cloudinary (o ZIP da Media Library) ou as
   fotos soltas; cada uma volta para o banco pelo nome que tinha lá.

   O ENVIO EM PEDAÇOS: o arquivo é cortado em pedaços (8 MB, o servidor diz)
   e cada pedaço vai num POST -- o ZIP de centenas de MB não depende de um
   POST gigante nem de a conexão do celular aguentar. Se um pedaço falha, ele
   é mandado de novo (três vezes); se o servidor diz que tem outra posição
   (409), o envio continua dali. Depois, "processar" até o servidor dizer que
   acabou: cada ida lê uns 20 segundos de ZIP e devolve onde parou.

   Tudo como app: o progresso na fila, o erro na folha do LSAviso com o campo
   aceso, o resultado em janela e nas listas. Nada de alert() nem confirm().

   O painel troca de tela sem recarregar (ls-soft-navigation.js): o script
   roda de novo a cada visita e só liga o que está na tela agora.
*/
(function () {
  "use strict";

  var raiz = document.querySelector("[data-rf]");
  if (!raiz || raiz.__rfLigado) return;
  raiz.__rfLigado = true;

  var URL_DA_TELA = raiz.getAttribute("data-rf-url");
  var PEDACO = parseInt(raiz.getAttribute("data-rf-pedaco"), 10) || 8 * 1024 * 1024;
  var LIMITE = parseInt(raiz.getAttribute("data-rf-limite"), 10) || 500 * 1024 * 1024;
  var csrf = (raiz.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
  var entrada = raiz.querySelector("[data-rf-arquivos]");
  var zona = raiz.querySelector("[data-rf-zona]");
  var fila = raiz.querySelector("[data-rf-fila]");
  var ocupado = false;
  var acumulado = { restaurados: [], nao_referenciados: [], recusados: [], ja: 0 };

  function aviso() { return window.LSAviso || null; }

  function plural(n, um, varios) { return n + " " + (n === 1 ? um : varios); }

  function janela(opcoes) {
    var a = aviso();
    if (a && a.modal) return a.modal(opcoes);
    if (fila) {
      var li = document.createElement("li");
      li.className = "ls-rf-item " + (opcoes.nivel === "erro" ? "erro" : "ok");
      li.textContent = opcoes.titulo + ": " + opcoes.texto;
      fila.appendChild(li);
    }
    return Promise.resolve();
  }

  function toast(nivel, titulo, texto) {
    var a = aviso();
    if (a && a.toast) a.toast({ nivel: nivel, titulo: titulo, texto: texto || "" });
  }

  function erroNaTela(erro) {
    if (zona && erro && erro.campo === "arquivos") {
      zona.classList.add("ls-campo-erro");
      zona.setAttribute("aria-invalid", "true");
    }
    return janela({
      nivel: "erro",
      titulo: (erro && erro.titulo) || (erro && erro.rede ? "Sem conexão" : "Não deu para restaurar"),
      texto: (erro && erro.message) || "Tente de novo em instantes.",
      icone: erro && erro.rede ? "alerta" : "arquivo-x"
    });
  }

  function limparErro() {
    if (!zona) return;
    zona.classList.remove("ls-campo-erro");
    zona.removeAttribute("aria-invalid");
  }

  /* Um POST da tela. Erro do servidor vira Error com titulo/campo; a rede que cai, Error com `rede`. */
  function postar(campos, arquivo, nomeDoArquivo) {
    var dados = new FormData();
    Object.keys(campos).forEach(function (chave) { dados.append(chave, campos[chave]); });
    if (arquivo) dados.append("pedaco", arquivo, nomeDoArquivo || "pedaco");
    dados.append("csrfmiddlewaretoken", csrf);
    return fetch(URL_DA_TELA, {
      method: "POST", body: dados, credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf }
    }).then(function (resposta) {
      return resposta.json().catch(function () { return null; }).then(function (json) {
        if (!resposta.ok || !json || json.status !== "sucesso") {
          var erro = new Error((json && json.msg) || "O servidor não conseguiu continuar. Tente de novo em instantes.");
          erro.status = resposta.status;
          erro.titulo = json && json.titulo;
          erro.campo = json && json.campo;
          erro.json = json;
          throw erro;
        }
        return json;
      });
    }, function () {
      var queda = new Error("A conexão caiu antes de o servidor responder. Confira a internet e envie de novo.");
      queda.rede = true;
      throw queda;
    });
  }

  function tamanho(bytes) {
    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",") + " MB";
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function itemDaFila(arquivo) {
    var li = document.createElement("li");
    li.className = "ls-rf-item";
    li.innerHTML =
      '<div class="ls-rf-item-topo"><i class="bi bi-file-earmark-zip" aria-hidden="true"></i>' +
      '<strong></strong><span class="ls-rf-item-tamanho"></span></div>' +
      '<div class="ls-rf-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i></div>' +
      '<span class="ls-rf-item-estado">Na fila</span>';
    li.querySelector("strong").textContent = arquivo.name;
    li.querySelector(".ls-rf-item-tamanho").textContent = tamanho(arquivo.size);
    if (!/\.zip$/i.test(arquivo.name)) li.querySelector("i").className = "bi bi-image";
    fila.appendChild(li);
    return {
      progresso: function (fracao, texto) {
        var barra = li.querySelector(".ls-rf-barra");
        var p = Math.max(0, Math.min(100, Math.round(fracao * 100)));
        barra.querySelector("i").style.width = p + "%";
        barra.setAttribute("aria-valuenow", String(p));
        if (texto) li.querySelector(".ls-rf-item-estado").textContent = texto;
      },
      fim: function (classe, texto) {
        li.classList.add(classe);
        li.querySelector(".ls-rf-item-estado").textContent = texto;
      }
    };
  }

  function esperar(ms) { return new Promise(function (pronto) { setTimeout(pronto, ms); }); }

  function mandarPedacos(arquivo, envio, linha) {
    var posicao = 0;
    var tentativas = 0;
    function proximo() {
      if (posicao >= arquivo.size) return Promise.resolve();
      var fim = Math.min(arquivo.size, posicao + PEDACO);
      return postar({ acao: "pedaco", envio: envio, posicao: String(posicao) }, arquivo.slice(posicao, fim), "pedaco")
        .then(function (json) {
          tentativas = 0;
          posicao = json.recebido;
          linha.progresso(posicao / arquivo.size * 0.7, "Enviando " + tamanho(posicao) + " de " + tamanho(arquivo.size));
          return proximo();
        }, function (erro) {
          if (erro.status === 409 && erro.json && typeof erro.json.recebido === "number") {
            posicao = erro.json.recebido;  // o servidor já tem até aqui: continua dali
            return proximo();
          }
          if ((erro.rede || erro.status >= 500) && tentativas < 3) {
            tentativas += 1;
            linha.progresso(posicao / arquivo.size * 0.7, "A conexão oscilou; tentando de novo…");
            return esperar(1500 * tentativas).then(proximo);
          }
          throw erro;
        });
    }
    return proximo();
  }

  function processar(envio, linha) {
    return postar({ acao: "processar", envio: envio }).then(function (json) {
      var total = json.total || 1;
      linha.progresso(0.7 + 0.3 * ((json.feitos || total) / total),
        json.proximo === null ? "Pronto" : "Lendo o ZIP: " + json.feitos + " de " + total + " arquivos");
      if (json.proximo !== null && json.proximo !== undefined) return processar(envio, linha);
      return json;
    });
  }

  function juntar(json) {
    ["restaurados", "nao_referenciados", "recusados"].forEach(function (chave) {
      (json[chave] || []).forEach(function (item) { acumulado[chave].push(item); });
    });
    acumulado.ja += json.ja || 0;
  }

  function desenharResultado() {
    var caixa = raiz.querySelector("[data-rf-resultado]");
    if (!caixa) return;
    caixa.hidden = false;
    var r = acumulado;
    function lista(chave, texto) {
      var ul = caixa.querySelector('[data-rf-lista="' + chave + '"]');
      var cont = caixa.querySelector('[data-rf-c="' + chave + '"]');
      if (cont) cont.textContent = String(r[chave].length);
      if (!ul) return;
      ul.innerHTML = "";
      r[chave].slice(0, 200).forEach(function (item) {
        var li = document.createElement("li");
        li.textContent = texto(item);
        ul.appendChild(li);
      });
      if (!r[chave].length) {
        var vazio = document.createElement("li");
        vazio.className = "vazio";
        vazio.textContent = "Nenhum.";
        ul.appendChild(vazio);
      }
    }
    lista("restaurados", function (i) { return i.nome + (i.onde && i.onde.length ? " · " + i.onde.join(", ") : ""); });
    lista("nao_referenciados", function (nome) { return nome; });
    lista("recusados", function (i) { return i.nome + " (" + i.motivo + ")"; });
    var resumo = caixa.querySelector("[data-rf-resumo]");
    if (resumo) {
      resumo.textContent = plural(r.restaurados.length, "restaurada", "restauradas") + ", " +
        plural(r.ja, "já estava no banco", "já estavam no banco") + ", " +
        plural(r.nao_referenciados.length, "que nenhum cadastro usa", "que nenhum cadastro usa") + " e " +
        plural(r.recusados.length, "recusada", "recusadas") + ".";
    }
  }

  function atualizarNumeros() {
    return fetch(URL_DA_TELA + "?formato=json", { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        ["faltando_nomes", "no_banco", "reserva"].forEach(function (chave) {
          var alvo = raiz.querySelector('[data-rf-n="' + chave + '"]');
          if (alvo) alvo.textContent = String(d[chave]);
        });
        var nota = raiz.querySelector("[data-rf-nota-faltando]");
        if (nota) {
          nota.textContent = (d.faltando_nomes === 1 ? "arquivo" : "arquivos") + " só no Cloudinary, em " +
            plural(d.faltando_total, "cadastro", "cadastros");
        }
        var grade = raiz.querySelector("[data-rf-grupos]");
        if (!grade) return;
        grade.innerHTML = "";
        if (!d.grupos.length) {
          var certo = document.createElement("div");
          certo.className = "ls-rf-tudo-certo";
          certo.innerHTML = '<i class="bi bi-patch-check-fill" aria-hidden="true"></i> ';
          certo.appendChild(document.createTextNode("Tudo no banco: nenhuma foto depende do Cloudinary."));
          grade.appendChild(certo);
          return;
        }
        d.grupos.forEach(function (g) {
          var card = document.createElement("article");
          card.className = "ls-rf-grupo" + (g.privado ? " privado" : "");
          card.innerHTML = '<div class="ls-rf-grupo-topo"><strong></strong><span class="ls-rf-selo"></span></div>' +
            "<details><summary>Ver os nomes</summary><ul></ul></details>";
          card.querySelector("strong").textContent = g.titulo;
          card.querySelector(".ls-rf-selo").textContent = String(g.quantos);
          var ul = card.querySelector("ul");
          g.nomes.forEach(function (nome) {
            var li = document.createElement("li");
            li.textContent = nome;
            ul.appendChild(li);
          });
          if (g.mais) {
            var mais = document.createElement("li");
            mais.className = "mais";
            mais.textContent = "e mais " + g.mais;
            ul.appendChild(mais);
          }
          grade.appendChild(card);
        });
      })
      .catch(function () { /* os números se atualizam na próxima visita */ });
  }

  function enviarUm(arquivo) {
    var linha = itemDaFila(arquivo);
    if (arquivo.size > LIMITE) {
      linha.fim("erro", "Passa de 500 MB");
      var grande = new Error("O arquivo " + arquivo.name + " passa de 500 MB. No Cloudinary, exporte por pasta e envie cada ZIP.");
      grande.titulo = "Arquivo grande demais";
      grande.campo = "arquivos";
      return Promise.reject(grande);
    }
    linha.progresso(0, "Começando…");
    return postar({ acao: "comecar", nome: arquivo.name, tamanho: String(arquivo.size) })
      .then(function (json) {
        if (json.pedaco) PEDACO = json.pedaco;
        return mandarPedacos(arquivo, json.envio, linha).then(function () { return processar(json.envio, linha); });
      })
      .then(function (json) {
        juntar(json);
        var voltou = (json.resumo && json.resumo.restaurados) || 0;
        linha.fim("ok", voltou ? plural(voltou, "foto de volta", "fotos de volta") : "Nada novo neste arquivo");
        return json;
      }, function (erro) {
        linha.fim("erro", erro.message || "Não deu para restaurar");
        throw erro;
      });
  }

  function enviarTodos(arquivos) {
    if (ocupado || !arquivos.length) return;
    ocupado = true;
    limparErro();
    raiz.classList.add("is-ocupado");
    var lista = Array.prototype.slice.call(arquivos);
    var erros = [];
    var cadeia = Promise.resolve();
    lista.forEach(function (arquivo) {
      cadeia = cadeia.then(function () {
        return enviarUm(arquivo).catch(function (erro) { erros.push(erro); });
      });
    });
    cadeia.then(function () {
      desenharResultado();
      return atualizarNumeros();
    }).then(function () {
      ocupado = false;
      raiz.classList.remove("is-ocupado");
      if (entrada) entrada.value = "";
      if (erros.length) return erroNaTela(erros[0]);
      var voltou = acumulado.restaurados.length;
      return janela({
        nivel: voltou ? "sucesso" : "info",
        icone: voltou ? "salvo" : "info",
        titulo: voltou ? "Fotos de volta" : "Nada novo para restaurar",
        texto: voltou
          ? (voltou === 1 ? "1 foto voltou para o banco e já aparece no site."
            : voltou + " fotos voltaram para o banco e já aparecem no site.")
          : "Os arquivos enviados já estavam no banco ou nenhum cadastro os usa.",
        lista: acumulado.restaurados.slice(0, 8).map(function (i) { return i.nome; })
      });
    });
  }

  if (entrada) {
    entrada.addEventListener("change", function () { enviarTodos(entrada.files || []); });
  }
  var escolher = raiz.querySelector("[data-rf-escolher]");
  if (escolher && entrada) escolher.addEventListener("click", function () { entrada.click(); });

  if (zona) {
    ["dragenter", "dragover"].forEach(function (tipo) {
      zona.addEventListener(tipo, function (evento) {
        evento.preventDefault();
        zona.classList.add("is-sobre");
      });
    });
    ["dragleave", "drop"].forEach(function (tipo) {
      zona.addEventListener(tipo, function (evento) {
        evento.preventDefault();
        zona.classList.remove("is-sobre");
      });
    });
    zona.addEventListener("drop", function (evento) {
      var arquivos = evento.dataTransfer && evento.dataTransfer.files;
      if (arquivos && arquivos.length) enviarTodos(arquivos);
    });
  }

  var copias = raiz.querySelector("[data-rf-copias]");
  if (copias) {
    copias.addEventListener("click", function () {
      if (ocupado) return;
      ocupado = true;
      copias.disabled = true;
      var rotulo = copias.innerHTML;
      copias.innerHTML = '<i class="bi bi-arrow-repeat ls-rf-gira" aria-hidden="true"></i> Procurando cópias…';
      postar({ acao: "copias" }).then(function (json) {
        juntar(json);
        desenharResultado();
        return atualizarNumeros().then(function () {
          var j = json.janela || {};
          return janela({ nivel: j.nivel || "info", titulo: j.titulo || "Cópias do repositório",
            texto: j.texto || json.msg, icone: j.icone || "info", lista: j.lista || null });
        });
      }, erroNaTela).then(function () {
        ocupado = false;
        copias.disabled = false;
        copias.innerHTML = rotulo;
      });
    });
  }
})();
