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
        '<span style="color:#A2917A;font-size:.72rem">Sem fotos.</span>';
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
    if (modalExcluir.classList.contains("open")) modalExcluir.classList.remove("open");
    else fechar();
  });

  form.addEventListener("submit", function (evento) {
    evento.preventDefault();
    aviso.classList.remove("on");
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
