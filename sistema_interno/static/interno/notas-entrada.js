/* ENTRADA DE NOTA FISCAL (LEIA-ME-V10, seção 115) -- views_notas_entrada.py.

   Duas telas, um arquivo:

     * O ENVIO: o nome do arquivo escolhido aparece no quadro, e dá para
       arrastar o PDF ou o XML para cima dele. O envio continua sendo o
       formulário comum (multipart), sem fetch.
     * A CONFERÊNCIA: cada linha tem a ligação com o material num campo
       escondido (id do material, "novo" ou "fora"). "Trocar" abre a busca,
       que roda AQUI, sobre a lista que o servidor mandou junto (sem ir ao
       servidor a cada letra). Escolher um material ajusta a unidade para a
       dele; "Criar material novo" mostra o nome; "Não entra no estoque"
       apaga a parte do estoque. O custo por unidade e o resumo acompanham
       o que se digita, e duas linhas que vão para o mesmo material e o
       mesmo local avisam que serão SOMADAS no lançamento.
     * "Lançar no estoque" pergunta antes (LSAviso.confirmar, nunca a
       caixa do navegador), com o resumo do que vai acontecer.

   O painel troca de tela sem recarregar: este arquivo roda de novo a cada
   visita e só liga o que está na tela agora. */
(function (window, document) {
  "use strict";

  function semAcento(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  function moeda(valor) {
    return Number(valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function iniciar() {
    ligarEnvio();
    ligarConferencia();
  }

  /* ------------------------------------------------------------ o envio */
  function ligarEnvio() {
    var form = document.getElementById("formNotaArquivo");
    if (!form) return;
    var campo = document.getElementById("neArquivo");
    var nome = document.getElementById("neArquivoNome");
    var area = document.getElementById("neSoltar");
    var textoPadrao = nome.textContent;

    function mostrarNome() {
      var arquivo = campo.files && campo.files[0];
      nome.textContent = arquivo ? arquivo.name : textoPadrao;
      area.classList.toggle("escolhido", !!arquivo);
    }
    campo.addEventListener("change", mostrarNome);
    ["dragenter", "dragover"].forEach(function (evento) {
      area.addEventListener(evento, function (e) { e.preventDefault(); area.classList.add("arrastando"); });
    });
    ["dragleave", "drop"].forEach(function (evento) {
      area.addEventListener(evento, function (e) { e.preventDefault(); area.classList.remove("arrastando"); });
    });
    area.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
        campo.files = e.dataTransfer.files;
        mostrarNome();
      }
    });
    form.addEventListener("submit", function (e) {
      if (!campo.files || !campo.files.length) {
        e.preventDefault();
        if (window.LSAviso) {
          window.LSAviso.toast({ nivel: "alerta", titulo: "Falta o arquivo", texto: "Escolha o PDF ou o XML da nota." });
        }
        return;
      }
      var botao = document.getElementById("neLer");
      if (botao) {
        botao.disabled = true;
        botao.textContent = "Lendo a nota…";
      }
    });
  }

  /* ------------------------------------------------------- a conferência */
  function ligarConferencia() {
    var form = document.getElementById("formConferencia");
    if (!form) return;
    var fonte = document.getElementById("neMateriais");
    var materiais = [];
    try {
      materiais = JSON.parse((fonte && fonte.textContent) || "[]");
    } catch (erro) {
      materiais = [];
    }
    var porId = {};
    materiais.forEach(function (m) { porId[String(m.id)] = m; });

    var ROTULOS = {
      codigo: '<i class="bi bi-upc-scan"></i> Pelo código do fornecedor',
      nome: '<i class="bi bi-check2-circle"></i> Mesmo nome',
      manual: '<i class="bi bi-hand-index"></i> Escolhido na conferência',
      novo: '<i class="bi bi-plus-circle"></i> Material novo — será criado',
      fora: '<i class="bi bi-slash-circle"></i> Não entra no estoque'
    };

    function partes(item) {
      return {
        escolha: item.querySelector("[data-ne-escolha]"),
        estado: item.querySelector("[data-ne-estado-rotulo]"),
        material: item.querySelector("[data-ne-material]"),
        painel: item.querySelector("[data-ne-painel]"),
        trocar: item.querySelector("[data-ne-trocar]"),
        busca: item.querySelector("[data-ne-busca]"),
        resultados: item.querySelector("[data-ne-resultados]"),
        nomeGrupo: item.querySelector("[data-ne-nome-grupo]"),
        nome: item.querySelector("[data-ne-nome]"),
        quantidade: item.querySelector("[data-ne-quantidade]"),
        local: item.querySelector("[data-ne-local]"),
        custo: item.querySelector("[data-ne-custo]"),
        soma: item.querySelector("[data-ne-soma]")
      };
    }

    function marcarUnidade(item, unidade) {
      var radio = item.querySelector('[data-ne-unidade][value="' + unidade + '"]');
      if (radio) radio.checked = true;
    }

    function quantidade(item) {
      var bruto = (partes(item).quantidade.value || "").replace(/\./g, "").replace(",", ".");
      var numero = Number(bruto);
      return isFinite(numero) && numero > 0 ? numero : 0;
    }

    function atualizarCusto(item) {
      var p = partes(item);
      var total = Number(item.getAttribute("data-total") || 0);
      var qtd = quantidade(item);
      var marcada = item.querySelector("[data-ne-unidade]:checked");
      var unidade = marcada ? (marcada.getAttribute("data-curto") || marcada.value) : "";
      // até 4 casas: parafuso de R$ 0,034 não pode aparecer como R$ 0,03
      var custo = qtd ? (total / qtd).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : "";
      p.custo.textContent = qtd ? "R$ " + custo + " por " + unidade : "Informe a quantidade";
    }

    function definir(item, valor, estado) {
      var p = partes(item);
      p.escolha.value = valor;
      item.setAttribute("data-estado", estado);
      p.estado.innerHTML = ROTULOS[estado] || p.estado.innerHTML;
      if (valor === "novo") {
        p.material.textContent = p.nome.value || item.getAttribute("data-descricao") || "";
        p.nomeGrupo.hidden = false;
        if (!p.nome.value) p.nome.value = (item.getAttribute("data-descricao") || "").slice(0, 90);
      } else if (valor === "fora") {
        p.material.textContent = "—";
        p.nomeGrupo.hidden = true;
      } else {
        var m = porId[String(valor)];
        p.material.textContent = m ? m.nome : "";
        if (m && m.codigo) {
          var codigo = document.createElement("small");
          codigo.textContent = " " + m.codigo;
          p.material.appendChild(codigo);
        }
        p.nomeGrupo.hidden = true;
        if (m) marcarUnidade(item, m.unidade);
      }
      fechar(item);
      atualizarCusto(item);
      atualizarResumo();
    }

    function abrir(item) {
      var p = partes(item);
      form.querySelectorAll("[data-ne-painel]:not([hidden])").forEach(function (outro) {
        if (outro !== p.painel) fechar(outro.closest("[data-ne-item]"));
      });
      p.painel.hidden = false;
      p.trocar.setAttribute("aria-expanded", "true");
      p.busca.value = "";
      listar(item, item.getAttribute("data-descricao") || "");
      p.busca.focus();
    }

    function fechar(item) {
      if (!item) return;
      var p = partes(item);
      p.painel.hidden = true;
      p.trocar.setAttribute("aria-expanded", "false");
    }

    /* A busca: todas as palavras digitadas, sem acento, em qualquer ordem.
       Aberta sem nada digitado, mostra os parecidos com a descrição da nota. */
    function listar(item, termo, digitado) {
      var p = partes(item);
      var palavras = semAcento(termo).split(/[^a-z0-9.,]+/).filter(function (w) { return w.length > 1; });
      var achados = [];
      materiais.forEach(function (m) {
        var acertos = 0;
        palavras.forEach(function (w) { if (m.busca.indexOf(w) !== -1) acertos += 1; });
        if (!palavras.length || (digitado ? acertos === palavras.length : acertos > 0)) {
          achados.push({ m: m, acertos: acertos });
        }
      });
      achados.sort(function (a, b) { return b.acertos - a.acertos || a.m.nome.localeCompare(b.m.nome, "pt-BR"); });
      p.resultados.innerHTML = "";
      achados.slice(0, 30).forEach(function (achado) {
        var m = achado.m;
        var botao = document.createElement("button");
        botao.type = "button";
        botao.className = "ls-ne-opcao" + (String(m.id) === p.escolha.value ? " atual" : "");
        botao.setAttribute("data-ne-material-id", m.id);
        botao.setAttribute("role", "listitem");
        var nome = document.createElement("span");
        nome.textContent = m.nome;
        var extra = document.createElement("span");
        extra.className = "ls-ne-opcao-extra";
        extra.textContent = (m.codigo ? m.codigo + " · " : "") + m.saldo + " " + m.unidade + " no estoque";
        botao.appendChild(nome);
        botao.appendChild(extra);
        p.resultados.appendChild(botao);
      });
      if (!achados.length) {
        var vazio = document.createElement("p");
        vazio.className = "ls-ne-sem-resultado";
        vazio.textContent = digitado ? "Nenhum material com esse nome. Crie um novo abaixo." : "Nenhum material parecido. Busque pelo nome ou crie um novo.";
        p.resultados.appendChild(vazio);
      }
    }

    function atualizarResumo() {
      var novos = 0, fora = 0, pecas = 0;
      var destinos = {};
      form.querySelectorAll("[data-ne-item]").forEach(function (item) {
        var p = partes(item);
        var valor = p.escolha.value;
        if (valor === "fora") { fora += 1; p.soma.hidden = true; return; }
        if (valor === "novo") novos += 1;
        pecas += quantidade(item);
        var alvo = valor === "novo" ? "novo:" + semAcento(p.nome.value) : "m:" + valor;
        var chave = alvo + "|" + semAcento(p.local.value);
        (destinos[chave] = destinos[chave] || []).push(item);
      });
      Object.keys(destinos).forEach(function (chave) {
        var grupo = destinos[chave];
        grupo.forEach(function (item) {
          var p = partes(item);
          if (grupo.length < 2) { p.soma.hidden = true; return; }
          var outros = grupo.filter(function (o) { return o !== item; }).map(function (o) { return o.getAttribute("data-ordem"); });
          p.soma.querySelector("span").textContent =
            "Mesmo material e local da(s) linha(s) " + outros.join(", ") + ": entra somado numa entrada só.";
          p.soma.hidden = false;
        });
      });
      var campos = { novos: novos, fora: fora, pecas: pecas };
      Object.keys(campos).forEach(function (nome) {
        var alvo = document.querySelector('[data-ne-resumo="' + nome + '"]');
        if (alvo) alvo.textContent = campos[nome];
      });
      return campos;
    }

    form.addEventListener("click", function (evento) {
      var alvo = evento.target.closest ? evento.target : null;
      if (!alvo) return;
      var item = alvo.closest("[data-ne-item]");
      if (!item) return;
      if (alvo.closest("[data-ne-trocar]")) {
        var painel = partes(item).painel;
        if (painel.hidden) abrir(item); else fechar(item);
        return;
      }
      var opcao = alvo.closest("[data-ne-material-id]");
      if (opcao) {
        definir(item, opcao.getAttribute("data-ne-material-id"), "manual");
        return;
      }
      if (alvo.closest("[data-ne-novo]")) {
        definir(item, "novo", "novo");
        partes(item).nome.focus();
        return;
      }
      if (alvo.closest("[data-ne-fora]")) {
        definir(item, "fora", "fora");
      }
    });

    form.addEventListener("input", function (evento) {
      var item = evento.target.closest("[data-ne-item]");
      if (!item) return;
      if (evento.target.matches("[data-ne-busca]")) {
        listar(item, evento.target.value, true);
        return;
      }
      if (evento.target.matches("[data-ne-nome]") && partes(item).escolha.value === "novo") {
        partes(item).material.textContent = evento.target.value;
      }
      atualizarCusto(item);
      atualizarResumo();
    });

    form.addEventListener("change", function (evento) {
      var item = evento.target.closest("[data-ne-item]");
      if (item && evento.target.matches("[data-ne-unidade]")) atualizarCusto(item);
    });

    form.addEventListener("keydown", function (evento) {
      // Enter na busca escolhe o primeiro resultado, em vez de enviar a nota.
      if (evento.key !== "Enter" || !evento.target.matches("[data-ne-busca]")) return;
      evento.preventDefault();
      var item = evento.target.closest("[data-ne-item]");
      var primeiro = item && item.querySelector("[data-ne-material-id]");
      if (primeiro) definir(item, primeiro.getAttribute("data-ne-material-id"), "manual");
    });

    form.addEventListener("submit", function (evento) {
      var botao = evento.submitter;
      if (!botao || botao.value !== "lancar" || form.getAttribute("data-confirmado") === "1") return;
      evento.preventDefault();
      var resumo = atualizarResumo();
      var semQuantidade = [];
      form.querySelectorAll("[data-ne-item]").forEach(function (item) {
        if (partes(item).escolha.value !== "fora" && !quantidade(item)) semQuantidade.push(item.getAttribute("data-ordem"));
      });
      if (semQuantidade.length) {
        if (window.LSAviso) {
          window.LSAviso.toast({
            nivel: "alerta", titulo: "Falta a quantidade",
            texto: "Linha(s) " + semQuantidade.join(", ") + ": informe quanto entra no estoque, ou marque “não entra no estoque”."
          });
        }
        return;
      }
      var texto = resumo.pecas + " unidade(s) entram no estoque" +
        (resumo.novos ? ", " + resumo.novos + " material(is) novo(s) será(ão) cadastrado(s)" : "") +
        (resumo.fora ? ", " + resumo.fora + " linha(s) fica(m) fora do estoque" : "") +
        ". A compra de R$ " + moeda(form.getAttribute("data-total")) + " vai para o Financeiro.";
      var pergunta = window.LSAviso && window.LSAviso.confirmar
        ? window.LSAviso.confirmar({
          titulo: "Lançar a NF-e " + (form.getAttribute("data-numero") || "") + "?",
          texto: texto,
          confirmar: "Lançar no estoque",
          cancelar: "Revisar",
          icone: "arquivo"
        })
        : Promise.resolve(true);
      pergunta.then(function (sim) {
        if (!sim) return;
        form.setAttribute("data-confirmado", "1");
        botao.disabled = false;
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit(botao);
        } else {
          var campo = document.createElement("input");
          campo.type = "hidden";
          campo.name = "action";
          campo.value = "lancar";
          form.appendChild(campo);
          form.submit();
        }
      });
    });

    form.querySelectorAll("[data-ne-item]").forEach(atualizarCusto);
    atualizarResumo();
  }

  if (window.LSTela && typeof window.LSTela.pronto === "function") {
    window.LSTela.pronto(iniciar);
  } else {
    iniciar();
  }
})(window, document);
