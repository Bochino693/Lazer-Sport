/* Comportamento de gestao / pecas_adm.
 *
 * NASCEU DE DENTRO DO HTML. Eram 7 KB de <script> no template --
 * peso repetido a cada abertura da página, que o navegador não tinha
 * como guardar: script dentro do HTML não tem endereço para cachear.
 *
 * O <script src> ficou na MESMA posição do bloco antigo, e sem `defer`
 * de propósito: script clássico externo executa na ordem do documento,
 * igual ao inline. Com `defer` ele passaria para depois da análise da
 * página, e qualquer trecho que dependesse dele antes disso quebraria
 * sem aviso.
 */

(function () {
  "use strict";

  var modal = document.getElementById("modalPeca");
  var form = document.getElementById("formPeca");
  var aviso = document.getElementById("avisoPeca");
  var galeria = document.getElementById("galeriaPeca");
  var acaoRapida = document.getElementById("formAcaoRapida");
  var modalExcluir = document.getElementById("modalExcluirPeca");
  var fraseExcluir = "";
  var pecaExcluir = null;

  function atualizarCategorias() {
    var total = form.querySelectorAll('input[name="categorias"]:checked').length;
    document.getElementById("categoriasPecaContador").textContent =
      total + (total === 1 ? " selecionada" : " selecionadas");
  }
  document.getElementById("buscarCategoriaPeca").addEventListener("input", function (evento) {
    var termo = evento.target.value.toLocaleLowerCase("pt-BR").trim();
    document.querySelectorAll("#categoriasBox label").forEach(function (opcao) {
      opcao.hidden = !!termo && opcao.textContent.toLocaleLowerCase("pt-BR").indexOf(termo) < 0;
    });
  });
  document.getElementById("categoriasBox").addEventListener("change", atualizarCategorias);
  document.getElementById("limparCategoriasPeca").addEventListener("click", function () {
    form.querySelectorAll('input[name="categorias"]').forEach(function (caixa) { caixa.checked = false; });
    atualizarCategorias();
  });

  var catalogo = {};
  try {
    JSON.parse(
      document.getElementById("pecas-dados").textContent
    ).forEach(function (peca) {
      catalogo[String(peca.id)] = peca;
    });
  } catch (erro) {
    catalogo = {};
  }

  /* ------------------------------------------------------------------
   * O KIT ELETRÔNICO (LEIA-ME seção 105)
   *
   * A chave "É um kit eletrônico" abre o editor: a máquina em chips de
   * rádio com busca (nunca <select>) e as linhas do que vem no kit --
   * nome, detalhe, quantidade e, se o item também é vendido sozinho, a
   * peça avulsa. As linhas se adicionam, removem e trocam de lugar; no
   * salvar, vão todas no campo `componentes_json`. Sem a chave, o campo
   * nem vai: os itens que o kit já tinha ficam guardados.
   * ------------------------------------------------------------------ */
  var kit = (function () {
    var chave = document.getElementById("pecaEhKit");
    var corpo = document.getElementById("kitCorpo");
    var linhas = document.getElementById("kitItens");
    var campoJson = document.getElementById("kitComponentesJson");
    var busca = document.getElementById("buscarMaquinaKit");
    var escolhida = document.getElementById("maquinaKitEscolhida");
    var caixaMaquinas = document.getElementById("kitMaquinas");
    var escolha = document.getElementById("kitEscolhaPeca");
    var escolhaLista = document.getElementById("kitEscolhaLista");
    var escolhaBusca = document.getElementById("kitEscolhaBusca");
    var escolhaTitulo = document.getElementById("kitEscolhaTitulo");
    var pecaAberta = null;
    var linhaEscolhendo = null;
    var avulsas = [];
    try {
      avulsas = JSON.parse(document.getElementById("pecas-avulsas-dados").textContent) || [];
    } catch (erro) {
      avulsas = [];
    }

    function nomeDaPeca(id) {
      var achada = avulsas.filter(function (p) { return String(p.id) === String(id); })[0];
      return achada ? achada.nome : "";
    }

    function texto(valor) {
      return String(valor == null ? "" : valor);
    }

    function mostrarCorpo() {
      corpo.hidden = !chave.checked;
      campoJson.disabled = !chave.checked;
      if (chave.checked && !linhas.children.length) novaLinha({}, true);
    }

    function atualizarEscolhida() {
      var marcada = caixaMaquinas.querySelector('input[name="maquina"]:checked');
      var rotulo = marcada ? marcada.parentNode.textContent.trim() : "Sem máquina";
      escolhida.textContent = rotulo;
      escolhida.classList.toggle("on", !!(marcada && marcada.value));
    }

    function numerar() {
      [].forEach.call(linhas.children, function (linha, indice) {
        linha.querySelector(".kit-linha-num").textContent = String(indice + 1);
        linha.querySelector("[data-kit-subir]").disabled = indice === 0;
        linha.querySelector("[data-kit-descer]").disabled = indice === linhas.children.length - 1;
      });
    }

    function marcarPeca(linha, id) {
      linha.dataset.peca = id ? String(id) : "";
      var botao = linha.querySelector("[data-kit-peca]");
      var nome = id ? nomeDaPeca(id) : "";
      botao.classList.toggle("on", !!id);
      botao.querySelector("span").textContent = id ? ("Peça avulsa: " + (nome || "#" + id)) : "Ligar a uma peça avulsa";
      linha.querySelector("[data-kit-desligar]").hidden = !id;
    }

    function novaLinha(item, focar) {
      var linha = document.createElement("li");
      linha.className = "kit-linha";
      linha.innerHTML =
        '<span class="kit-linha-num" aria-hidden="true"></span>' +
        '<div class="kit-linha-campos">' +
          '<input class="kit-linha-nome" maxlength="80" placeholder="Item (ex.: TV Box)" aria-label="Nome do item">' +
          '<input class="kit-linha-detalhe" maxlength="120" placeholder="Detalhe, opcional (ex.: com o jogo Strike Kids)" aria-label="Detalhe do item">' +
          '<div class="kit-linha-baixo">' +
            '<div class="kit-qtd" role="group" aria-label="Quantidade">' +
              '<button type="button" data-kit-menos aria-label="Menos um">−</button>' +
              '<input class="kit-linha-qtd" type="number" min="1" max="99" inputmode="numeric" aria-label="Quantidade">' +
              '<button type="button" data-kit-mais aria-label="Mais um">+</button>' +
            '</div>' +
            '<button type="button" class="kit-liga-peca" data-kit-peca><i class="fa-solid fa-link" aria-hidden="true"></i><span></span></button>' +
            '<button type="button" class="kit-solta-peca" data-kit-desligar aria-label="Soltar a peça avulsa" hidden>×</button>' +
          '</div>' +
        '</div>' +
        '<div class="kit-linha-ordem">' +
          '<button type="button" data-kit-subir aria-label="Subir o item"><i class="fa-solid fa-arrow-up" aria-hidden="true"></i></button>' +
          '<button type="button" data-kit-descer aria-label="Descer o item"><i class="fa-solid fa-arrow-down" aria-hidden="true"></i></button>' +
          '<button type="button" class="kit-linha-remover" data-kit-remover aria-label="Remover o item"><i class="fa-solid fa-trash-can" aria-hidden="true"></i></button>' +
        '</div>';
      linha.querySelector(".kit-linha-nome").value = texto(item.nome);
      linha.querySelector(".kit-linha-detalhe").value = texto(item.detalhe);
      linha.querySelector(".kit-linha-qtd").value = texto(item.quantidade || 1);
      linhas.appendChild(linha);
      marcarPeca(linha, item.peca || "");
      numerar();
      if (focar) linha.querySelector(".kit-linha-nome").focus();
      return linha;
    }

    function fecharEscolha() {
      escolha.hidden = true;
      linhaEscolhendo = null;
    }

    function desenharEscolha() {
      var termo = escolhaBusca.value.toLocaleLowerCase("pt-BR").trim();
      var atual = linhaEscolhendo ? linhaEscolhendo.dataset.peca : "";
      var proprio = pecaAberta ? String(pecaAberta.id) : "";
      escolhaLista.innerHTML = "";
      var achadas = avulsas.filter(function (p) {
        return String(p.id) !== proprio && (!termo || p.nome.toLocaleLowerCase("pt-BR").indexOf(termo) >= 0);
      });
      if (!achadas.length) {
        escolhaLista.innerHTML = '<span class="kit-escolha-vazia">Nenhuma peça com esse nome.</span>';
        return;
      }
      achadas.slice(0, 60).forEach(function (p) {
        var opcao = document.createElement("button");
        opcao.type = "button";
        opcao.className = "kit-escolha-opcao" + (String(p.id) === atual ? " on" : "");
        opcao.setAttribute("role", "option");
        opcao.setAttribute("aria-selected", String(String(p.id) === atual));
        opcao.dataset.kitEscolher = String(p.id);
        opcao.textContent = p.nome + (p.ativo ? "" : " · fora do site");
        escolhaLista.appendChild(opcao);
      });
    }

    function abrirEscolha(linha) {
      linhaEscolhendo = linha;
      var nome = linha.querySelector(".kit-linha-nome").value.trim();
      escolhaTitulo.textContent = nome ? ("Ligar “" + nome + "” a uma peça avulsa") : "Ligar a uma peça avulsa";
      escolhaBusca.value = nome;
      desenharEscolha();
      if (!escolhaLista.querySelector("[data-kit-escolher]")) {
        escolhaBusca.value = "";
        desenharEscolha();
      }
      escolha.hidden = false;
      escolha.scrollIntoView({ block: "nearest", behavior: "smooth" });
      escolhaBusca.focus();
    }

    chave.addEventListener("change", mostrarCorpo);
    caixaMaquinas.addEventListener("change", atualizarEscolhida);
    busca.addEventListener("input", function () {
      var termo = busca.value.toLocaleLowerCase("pt-BR").trim();
      caixaMaquinas.querySelectorAll(".kit-chip").forEach(function (chip) {
        var marcado = chip.querySelector("input").checked;
        chip.hidden = !!termo && !marcado && chip.textContent.toLocaleLowerCase("pt-BR").indexOf(termo) < 0;
      });
    });
    document.getElementById("kitAdicionarItem").addEventListener("click", function () { novaLinha({}, true); });
    escolhaBusca.addEventListener("input", desenharEscolha);
    document.getElementById("kitEscolhaFechar").addEventListener("click", fecharEscolha);
    escolhaLista.addEventListener("click", function (evento) {
      var opcao = evento.target.closest("[data-kit-escolher]");
      if (!opcao || !linhaEscolhendo) return;
      marcarPeca(linhaEscolhendo, opcao.dataset.kitEscolher);
      fecharEscolha();
    });

    linhas.addEventListener("click", function (evento) {
      var alvo = evento.target;
      var linha = alvo.closest(".kit-linha");
      if (!linha) return;
      var qtd = linha.querySelector(".kit-linha-qtd");
      if (alvo.closest("[data-kit-menos]") || alvo.closest("[data-kit-mais]")) {
        var passo = alvo.closest("[data-kit-mais]") ? 1 : -1;
        qtd.value = String(Math.max(1, Math.min(99, (parseInt(qtd.value, 10) || 1) + passo)));
      } else if (alvo.closest("[data-kit-subir]") && linha.previousElementSibling) {
        linhas.insertBefore(linha, linha.previousElementSibling);
        numerar();
        linha.querySelector("[data-kit-subir]").focus();
      } else if (alvo.closest("[data-kit-descer]") && linha.nextElementSibling) {
        linhas.insertBefore(linha.nextElementSibling, linha);
        numerar();
        linha.querySelector("[data-kit-descer]").focus();
      } else if (alvo.closest("[data-kit-remover]")) {
        if (linhaEscolhendo === linha) fecharEscolha();
        linha.remove();
        numerar();
      } else if (alvo.closest("[data-kit-desligar]")) {
        marcarPeca(linha, "");
      } else if (alvo.closest("[data-kit-peca]")) {
        abrirEscolha(linha);
      }
    });

    return {
      abrir: function (peca) {
        pecaAberta = peca;
        linhas.innerHTML = "";
        fecharEscolha();
        busca.value = "";
        caixaMaquinas.querySelectorAll(".kit-chip").forEach(function (chip) { chip.hidden = false; });
        chave.checked = !!(peca && peca.eh_kit);
        var alvo = String((peca && peca.maquina_id) || "");
        var achou = false;
        caixaMaquinas.querySelectorAll('input[name="maquina"]').forEach(function (radio) {
          radio.checked = radio.value === alvo;
          if (radio.checked) achou = true;
        });
        if (!achou) caixaMaquinas.querySelector('input[name="maquina"][value=""]').checked = true;
        ((peca && peca.componentes) || []).forEach(function (item) { novaLinha(item, false); });
        atualizarEscolhida();
        mostrarCorpo();
      },
      preparar: function () {
        var itens = [].map.call(linhas.children, function (linha) {
          return {
            nome: linha.querySelector(".kit-linha-nome").value.trim(),
            detalhe: linha.querySelector(".kit-linha-detalhe").value.trim(),
            quantidade: linha.querySelector(".kit-linha-qtd").value || "1",
            peca: linha.dataset.peca || ""
          };
        });
        campoJson.value = JSON.stringify(itens);
        campoJson.disabled = !chave.checked;
      }
    };
  })();

  function dadosDoCard(botao) {
    var card = botao.closest("[data-peca-id]");
    return card ? catalogo[card.dataset.pecaId] : null;
  }

  function abrir(peca) {
    aviso.classList.remove("on");
    form.reset();
    document.getElementById("pecaId").value = peca ? peca.id : "";
    document.getElementById("tituloModalPeca").textContent =
      peca ? "Editar peça" : "Nova peça";

    if (peca) {
      document.getElementById("pecaNome").value = peca.nome || "";
      document.getElementById("pecaDescricao").value = peca.descricao_peca || "";
      document.getElementById("pecaVenda").value = peca.preco_venda || "";
      document.getElementById("pecaFornecedor").value = peca.preco_fornecedor || "";
      marcarSemJuros(form, peca.parcelas_sem_juros);
      document.getElementById("pecaAtivo").checked = !!peca.ativo;

      var ids = peca.categorias_ids || [];
      form.querySelectorAll('input[name="categorias"]').forEach(function (caixa) {
        caixa.checked = ids.indexOf(parseInt(caixa.value, 10)) >= 0;
      });

      desenharGaleria(peca.imagens || []);
    } else {
      document.getElementById("pecaAtivo").checked = true;
      desenharGaleria([]);
    }
    kit.abrir(peca);

    document.getElementById("buscarCategoriaPeca").value = "";
    document.querySelectorAll("#categoriasBox label").forEach(function (opcao) { opcao.hidden = false; });
    atualizarCategorias();
    if (window.Painel) Painel.aplicarMascaras(form);
    modal.classList.add("open");
  }

  function desenharGaleria(imagens) {
    galeria.innerHTML = "";
    if (!imagens.length) {
      galeria.innerHTML =
        '<span style="color:var(--muted);font-size:.72rem">Sem fotos.</span>';
      return;
    }
    imagens.forEach(function (foto) {
      var figura = document.createElement("figure");
      figura.innerHTML =
        '<img src="' + foto.url + '" alt="' + (foto.posicao || "") + '">' +
        '<button type="button" data-remover-foto="' + foto.id + '" title="Remover foto">×</button>';
      galeria.appendChild(figura);
    });
  }

  function fechar() {
    modal.classList.remove("open");
  }

  function dispararAcaoRapida(acao, id, extras) {
    document.getElementById("acaoRapida").value = acao;
    document.getElementById("acaoRapidaId").value = id || "";
    document.getElementById("acaoRapidaImagem").value =
      (extras && extras.imagem) || "";
    document.getElementById("acaoRapidaConfirma").value =
      (extras && extras.confirmacao) || "";
    acaoRapida.submit();
  }

  document.addEventListener("click", function (evento) {
    var alvo = evento.target;

    if (alvo.closest("[data-nova-peca]")) return abrir(null);
    if (alvo.closest("[data-fechar]")) return fechar();

    var editar = alvo.closest("[data-editar]");
    if (editar) return abrir(dadosDoCard(editar));

    var alternar = alvo.closest("[data-alternar]");
    if (alternar) {
      var peca = dadosDoCard(alternar);
      return dispararAcaoRapida("alternar_ativo", peca.id, null);
    }

    var excluir = alvo.closest("[data-excluir]");
    if (excluir) {
      pecaExcluir = dadosDoCard(excluir);
      fraseExcluir = "CONFIRMAR EXCLUSÃO " + pecaExcluir.nome;
      document.getElementById("fraseExcluirPeca").textContent = fraseExcluir;
      document.getElementById("confirmarExcluirPeca").value = "";
      document.getElementById("executarExcluirPeca").disabled = true;
      modalExcluir.classList.add("open");
      document.getElementById("confirmarExcluirPeca").focus();
      return;
    }

    var foto = alvo.closest("[data-remover-foto]");
    if (foto) {
      return dispararAcaoRapida("imagem_excluir", "", {
        imagem: foto.dataset.removerFoto
      });
    }

    if (alvo === modal) fechar();
    if (alvo === modalExcluir || alvo.closest("[data-fechar-exclusao]")) {
      modalExcluir.classList.remove("open");
    }
  });

  document.addEventListener("keydown", function (evento) {
    if (evento.key !== "Escape") return;
    var escolhaPeca = document.getElementById("kitEscolhaPeca");
    if (escolhaPeca && !escolhaPeca.hidden) { escolhaPeca.hidden = true; return; }
    if (modalExcluir.classList.contains("open")) modalExcluir.classList.remove("open");
    else fechar();
  });

  form.addEventListener("submit", function (evento) {
    evento.preventDefault();
    aviso.classList.remove("on");
    // os itens do kit vão juntos, num campo só (na ordem da tela)
    kit.preparar();
    modal.querySelector(".pecas-card").classList.add("is-loading");

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (r) { return r.json(); })
      .then(function (dados) {
        if (dados.status === "sucesso") {
          window.location.reload();
          return;
        }
        aviso.textContent = dados.msg || "Não foi possível salvar.";
        aviso.classList.add("on");
        modal.querySelector(".pecas-card").classList.remove("is-loading");
      })
      .catch(function () {
        aviso.textContent = "Falha de conexão ao salvar.";
        aviso.classList.add("on");
        modal.querySelector(".pecas-card").classList.remove("is-loading");
      });
  });

  document.getElementById("confirmarExcluirPeca").addEventListener("input", function (evento) {
    document.getElementById("executarExcluirPeca").disabled = evento.target.value !== fraseExcluir;
  });
  document.getElementById("executarExcluirPeca").addEventListener("click", function () {
    if (!pecaExcluir || document.getElementById("confirmarExcluirPeca").value !== fraseExcluir) return;
    dispararAcaoRapida("delete", pecaExcluir.id, { confirmacao: fraseExcluir });
  });
})();

// As vezes sem juros (LEIA-ME seção 99): os chips de rádio do cadastro.
function marcarSemJuros(raiz, valor) {
    var alvo = String(valor || "");
    var chips = (raiz || document).querySelectorAll('input[name="parcelas_sem_juros"]');
    chips.forEach(function (chip) { chip.checked = chip.value === alvo; });
    if (![].some.call(chips, function (chip) { return chip.checked; }) && chips[0]) chips[0].checked = true;
}
