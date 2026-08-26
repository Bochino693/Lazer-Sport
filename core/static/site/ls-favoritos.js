/* Curtida e lista de desejos.
 *
 * Um só arquivo para o site inteiro: qualquer botão com data-favorito
 * funciona, inclusive os que chegam depois (carrossel, filtro, busca),
 * porque o clique é ouvido no documento.
 *
 * Não exige login. Quem não entrou fica preso ao próprio aparelho -- o
 * servidor devolve o estado final e é ele quem manda na aparência.
 */
(function () {
  "use strict";

  var ENDPOINT = "/favoritos/alternar/";

  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    var achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return achado ? decodeURIComponent(achado[1]) : "";
  }

  function chaveProduto(botao) {
    return botao.dataset.produto + "-" + botao.dataset.id;
  }

  /* O contador de curtidas pode aparecer em vários lugares da mesma
     página (card e detalhe); todos recebem o número novo. */
  function pintarTotais(chave, total) {
    var alvos = document.querySelectorAll(
      '[data-favorito-total="' + chave + '"]'
    );
    alvos.forEach(function (alvo) {
      alvo.textContent = total;
      alvo.hidden = total <= 0;
    });
  }

  function pintarBotoes(chave, tipo, marcado) {
    var seletor =
      '[data-favorito="' + tipo + '"][data-chave="' + chave + '"]';
    document.querySelectorAll(seletor).forEach(function (botao) {
      botao.classList.toggle("is-on", marcado);
      botao.setAttribute("aria-pressed", marcado ? "true" : "false");

      var rotulo = botao.querySelector("[data-favorito-rotulo]");
      if (!rotulo) return;

      if (tipo === "curtida") {
        rotulo.textContent = marcado ? "Curtido" : "Curtir";
      } else {
        rotulo.textContent = marcado ? "Na lista" : "Lista de desejos";
      }
    });
  }

  function pintarContadorDesejos(total) {
    document
      .querySelectorAll("[data-lista-desejos-total]")
      .forEach(function (alvo) {
        alvo.textContent = total;
        alvo.classList.toggle("vazio", total <= 0);
      });
  }

  function avisar(botao, mensagem) {
    var balao = document.createElement("span");
    balao.className = "ls-fav-aviso";
    balao.textContent = mensagem;
    botao.appendChild(balao);
    setTimeout(function () {
      balao.remove();
    }, 2200);
  }

  document.addEventListener("click", function (evento) {
    var botao = evento.target.closest("[data-favorito]");
    if (!botao) return;

    evento.preventDefault();
    if (botao.dataset.ocupado === "1") return;
    botao.dataset.ocupado = "1";

    var tipo = botao.dataset.favorito;
    var chave = chaveProduto(botao);

    fetch(ENDPOINT, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
        "X-Requested-With": "XMLHttpRequest"
      },
      body: JSON.stringify({
        tipo: tipo,
        produto: botao.dataset.produto,
        id: botao.dataset.id
      })
    })
      .then(function (resposta) {
        return resposta.json().then(function (dados) {
          return { ok: resposta.ok, dados: dados };
        });
      })
      .then(function (resultado) {
        if (!resultado.ok || !resultado.dados.ok) {
          avisar(botao, resultado.dados.erro || "Não deu para salvar agora.");
          return;
        }

        var dados = resultado.dados;
        pintarBotoes(chave, tipo, dados.marcado);
        pintarTotais(chave, dados.curtidas);
        pintarContadorDesejos(dados.total_desejos);

        botao.classList.remove("pulsa");
        void botao.offsetWidth; /* reinicia a animação */
        botao.classList.add("pulsa");

        if (!dados.logado && dados.marcado) {
          botao.dataset.avisoConta = "1";
        }
      })
      .catch(function () {
        avisar(botao, "Sem conexão agora.");
      })
      .finally(function () {
        botao.dataset.ocupado = "0";
      });
  });
})();
