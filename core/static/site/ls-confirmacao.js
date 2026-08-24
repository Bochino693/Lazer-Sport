/* =========================================================================
   ls-confirmacao.js — entrega do aviso de pagamento aprovado.
   -------------------------------------------------------------------------
   Roda em qualquer página do site para quem está logado. Pergunta ao
   servidor se existe pedido aprovado que o cliente ainda não viu e mostra o
   aviso. Se ele estiver no meio do checkout, leva direto para Meus Pedidos;
   se estiver navegando em outro lugar, apenas avisa e deixa a escolha com
   ele — sem sequestrar a navegação de quem entrou do zero.
   ========================================================================= */
(function () {
    "use strict";

    var config = document.getElementById("ls-confirmacao-config");
    if (!config) return;

    var urls;
    try {
        urls = JSON.parse(config.textContent || "{}");
    } catch (erro) {
        return;
    }

    if (!urls.consulta || !urls.baixa) return;

    /* Páginas onde o cliente está esperando justamente por esta confirmação:
       ali o redirecionamento é o que ele quer, não uma interrupção. */
    var EM_CHECKOUT = /^\/(pagamento|carrinho)\b/.test(window.location.pathname);
    var SEGUNDOS_PARA_REDIRECIONAR = 4;

    function cookie(nome) {
        var achado = null;
        document.cookie.split(";").forEach(function (bruto) {
            var par = bruto.trim();
            if (par.indexOf(nome + "=") === 0) {
                achado = decodeURIComponent(par.substring(nome.length + 1));
            }
        });
        return achado;
    }

    function moeda(valor) {
        var numero = parseFloat(valor);
        if (isNaN(numero)) return "";
        return numero.toLocaleString("pt-BR", {
            style: "currency",
            currency: "BRL"
        });
    }

    /* ---------------------------------------------------------------------
       Corrige o selo do carrinho com o número que o servidor acabou de
       informar. Antes isto zerava às cegas: se o cliente já tivesse colocado
       algo novo no carrinho, o selo sumia e reaparecia na página seguinte —
       era o carrinho "tendo e não tendo produtos".
       --------------------------------------------------------------------- */
    function ajustarCarrinho(quantidade) {
        var botao = document.getElementById("carrinho-float-btn");
        var contador = document.getElementById("carrinho-contador");
        var total = Number(quantidade);

        if (isNaN(total) || total < 0) return;

        if (contador) contador.textContent = String(total);
        if (botao) botao.classList.toggle("hidden", total === 0);
    }

    function baixarAviso(pedidoId) {
        return fetch(urls.baixa, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": cookie("csrftoken") || "",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({ pedido_id: pedidoId })
        }).catch(function () {
            /* Falhar aqui só faz o aviso reaparecer na próxima visita, que é
               melhor do que sumir sem o cliente ter visto. */
        });
    }

    function montarAviso(confirmacao) {
        var caixa = document.createElement("div");
        caixa.className = "ls-confirma";
        caixa.setAttribute("role", "status");
        caixa.setAttribute("aria-live", "polite");

        var valor = moeda(confirmacao.total);
        var itens = confirmacao.itens === 1
            ? "1 item"
            : confirmacao.itens + " itens";

        caixa.innerHTML =
            '<div class="ls-confirma-topo">' +
            '  <span class="ls-confirma-selo" aria-hidden="true">' +
            '    <i class="fa-solid fa-check"></i>' +
            '  </span>' +
            '  <span>' +
            '    <strong class="ls-confirma-titulo">Pagamento aprovado!</strong>' +
            '    <span class="ls-confirma-sub">Pedido #' + confirmacao.pedido_id +
            '      &middot; ' + itens + (valor ? " &middot; " + valor : "") + '</span>' +
            '  </span>' +
            '  <button type="button" class="ls-confirma-fechar" aria-label="Fechar aviso">' +
            '    <i class="fa-solid fa-xmark" aria-hidden="true"></i>' +
            '  </button>' +
            '</div>' +
            '<div class="ls-confirma-acoes">' +
            '  <a class="ls-confirma-btn primario" href="' + confirmacao.redirect_url + '">' +
            '    Ver meus pedidos' +
            '  </a>' +
            '</div>' +
            '<span class="ls-confirma-timer" hidden></span>';

        document.body.appendChild(caixa);
        return caixa;
    }

    function mostrar(confirmacao) {
        var caixa = montarAviso(confirmacao);
        var timer = caixa.querySelector(".ls-confirma-timer");
        var contagem = null;

        function fechar() {
            if (contagem) window.clearInterval(contagem);
            caixa.classList.remove("is-open");
            window.setTimeout(function () {
                caixa.remove();
            }, 420);
        }

        caixa.querySelector(".ls-confirma-fechar")
            .addEventListener("click", fechar);

        /* O aviso é baixado assim que aparece na tela: a partir daqui o
           cliente já foi informado, e repetir na próxima página seria
           insistência. O e-mail continua sendo o registro permanente. */
        baixarAviso(confirmacao.pedido_id);

        window.requestAnimationFrame(function () {
            caixa.classList.add("is-open");
        });

        if (!EM_CHECKOUT) return;

        /* No checkout, leva para Meus Pedidos — mas com contagem visível e
           um botão de fechar que cancela: ninguém é arrastado sem aviso. */
        var restam = SEGUNDOS_PARA_REDIRECIONAR;
        timer.hidden = false;

        function tique() {
            if (restam <= 0) {
                window.clearInterval(contagem);
                window.location.replace(confirmacao.redirect_url);
                return;
            }
            timer.textContent =
                "Levando para os seus pedidos em " + restam + "s…";
            restam -= 1;
        }

        tique();
        contagem = window.setInterval(tique, 1000);

        caixa.querySelector(".ls-confirma-fechar")
            .addEventListener("click", function () {
                window.clearInterval(contagem);
                timer.hidden = true;
            });
    }

    function consultar() {
        fetch(urls.consulta, {
            credentials: "same-origin",
            cache: "no-store",
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resposta) {
                return resposta.ok ? resposta.json() : null;
            })
            .then(function (dados) {
                if (!dados) return;

                /* O selo é acertado sempre, com ou sem aviso: é a resposta
                   mais recente do servidor sobre o carrinho. */
                ajustarCarrinho(dados.itens_carrinho);

                if (!dados.confirmacoes || !dados.confirmacoes.length) {
                    return;
                }
                /* Mais de um pedido pendente é raro (duas compras sem voltar
                   ao site). Mostra o mais recente; os outros continuam
                   marcados e aparecem na visita seguinte. */
                mostrar(dados.confirmacoes[0]);
            })
            .catch(function () {
                /* Sem rede, o aviso simplesmente espera a próxima visita. */
            });
    }

    /* A página de pagamento tem o próprio polling, que já redireciona sozinho
       quando a confirmação chega com a aba aberta. Aqui a consulta espera um
       pouco para não competir com ele nem piscar dois avisos. */
    var atraso = EM_CHECKOUT ? 2500 : 600;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            window.setTimeout(consultar, atraso);
        }, { once: true });
    } else {
        window.setTimeout(consultar, atraso);
    }
})();
