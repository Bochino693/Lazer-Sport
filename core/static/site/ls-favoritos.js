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
    });
  }

  function pintarBotoes(chave, tipo, marcado) {
    var seletor =
      '[data-favorito="' + tipo + '"][data-chave="' + chave + '"]';
    document.querySelectorAll(seletor).forEach(function (botao) {
      botao.classList.toggle("is-on", marcado);
      botao.setAttribute("aria-pressed", marcado ? "true" : "false");

      if (tipo === "desejo") {
        var icone = botao.querySelector("[data-favorito-icone]");
        if (icone) {
          icone.classList.toggle("fa-solid", marcado);
          icone.classList.toggle("fa-regular", !marcado);
        }
      }

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

  /* Curtir é do aplicativo. No site o coração é número: tocá-lo explica
     onde curtir, em vez de fingir que o botão não existe -- é o convite
     que faz a pessoa instalar. */
  var convite = null;

  function fecharConvite() {
    if (convite) {
      convite.remove();
      convite = null;
    }
  }

  function convidarParaOApp(botao) {
    fecharConvite();

    /* O balão vai para o <body>, e não para dentro do botão: o card do
       catálogo corta o que passa da borda (overflow), e o convite
       aparecia pela metade -- justamente a frase que precisa ser lida
       inteira. */
    convite = document.createElement("div");
    convite.className = "ls-fav-convite";
    convite.innerHTML =
      "<strong>Curtir é no aplicativo.</strong>" +
      " Cada curtida vale pontos, e pontos viram cupom de desconto." +
      ' <a href="/#aplicativo">Baixar o aplicativo</a>';
    document.body.appendChild(convite);

    var caixa = botao.getBoundingClientRect();
    var largura = Math.min(280, window.innerWidth - 24);
    var esquerda = Math.min(
      Math.max(12, caixa.left + caixa.width / 2 - largura / 2),
      window.innerWidth - largura - 12
    );

    convite.style.width = largura + "px";
    convite.style.left = esquerda + "px";

    /* Sem espaço em cima, o balão desce para baixo do coração. */
    if (caixa.top > 130) {
      convite.style.top = (caixa.top - convite.offsetHeight - 10) + "px";
    } else {
      convite.style.top = (caixa.bottom + 10) + "px";
    }

    setTimeout(fecharConvite, 6000);
  }

  /* Rolar ou tocar fora tira o balão: preso na tela ele viraria estorvo. */
  window.addEventListener("scroll", fecharConvite, true);

  /* ------------------------------------------------------------------
     Hidratação

     A home e as listas do site são cacheadas: o HTML sai igual para todo
     mundo, senão a lista de uma pessoa apareceria para as outras. Então o
     card nasce neutro e, ao carregar, uma chamada só diz o que ESTE
     visitante já guardou.
     ------------------------------------------------------------------ */
  function pintarMarcados(dados) {
    ["brinquedo", "peca"].forEach(function (produto) {
      (dados.desejo[produto] || []).forEach(function (id) {
        pintarBotoes(produto + "-" + id, "desejo", true);
      });
    });

    pintarContadorDesejos(dados.total_desejos);
  }

  function hidratar() {
    if (!document.querySelector('[data-favorito="desejo"]')) return;

    fetch("/favoritos/meus/", {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (r) { return r.json(); })
      .then(function (dados) {
        if (dados && dados.ok) pintarMarcados(dados);
      })
      .catch(function () {
        /* Sem rede o card fica neutro: melhor não marcado do que marcado
           errado, que faria a pessoa achar que já guardou. */
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hidratar);
  } else {
    hidratar();
  }

  document.addEventListener("click", function (evento) {
    var selo = evento.target.closest("[data-favorito-app]");
    if (selo && !evento.target.closest("a")) {
      evento.preventDefault();
      convidarParaOApp(selo);
      return;
    }

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
          /* O servidor recusa curtida vinda do site: a mensagem dele já
             explica o porquê, e aqui ela vira o mesmo convite. */
          if (resultado.dados.somente_app) {
            convidarParaOApp(botao);
            return;
          }
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
