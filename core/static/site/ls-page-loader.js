/* =========================================================================
   ls-page-loader.js — overlay de carregamento das áreas internas.
   -------------------------------------------------------------------------
   Uso automático: qualquer clique em link interno ou envio de formulário.
   Uso manual:     LSLoader.show("Gerando relatório…") / LSLoader.hide()
   ========================================================================= */
(function (window, document) {
    "use strict";

    /* Só aparece se a navegação passar disso. Abaixo, a página nova já
       chegou e o overlay só piscaria na tela. */
    var ATRASO_MS = 140;

    var overlay = null;
    var elTexto = null;
    var timer = null;
    var tetoTimer = null;
    var aberto = false;

    function montar() {
        if (overlay) return overlay;

        overlay = document.querySelector(".ls-page-loader");

        if (!overlay) {
            /* Sem marcação no template: o overlay é criado aqui mesmo. */
            overlay = document.createElement("div");
            overlay.className = "ls-page-loader";
            overlay.setAttribute("role", "status");
            overlay.setAttribute("aria-live", "polite");
            overlay.setAttribute("aria-hidden", "true");
            overlay.innerHTML =
                '<div class="ls-page-loader-card">' +
                '  <div class="ls-page-loader-ring">' +
                '    <div class="ls-page-loader-mark"></div>' +
                '  </div>' +
                '  <strong class="ls-page-loader-title">Carregando</strong>' +
                '  <span class="ls-page-loader-text"></span>' +
                '  <div class="ls-page-loader-bar"></div>' +
                '</div>';
            document.body.appendChild(overlay);
        }

        elTexto = overlay.querySelector(".ls-page-loader-text");

        /* A marca vem do data-logo do <body>, para o arquivo servir tanto a
           /adm quanto ao subdomínio interno sem hardcode de caminho. */
        var marca = overlay.querySelector(".ls-page-loader-mark");
        var logo = document.body.getAttribute("data-loader-logo");
        if (marca && logo && !marca.querySelector("img")) {
            var img = document.createElement("img");
            img.src = logo;
            img.alt = "";
            img.setAttribute("aria-hidden", "true");
            marca.appendChild(img);
        }

        return overlay;
    }

    function mostrar(mensagem) {
        montar();
        if (elTexto) elTexto.textContent = mensagem || "Preparando os dados…";
        overlay.classList.add("is-open");
        overlay.setAttribute("aria-hidden", "false");
        aberto = true;
    }

    function esconder() {
        if (timer) {
            window.clearTimeout(timer);
            timer = null;
        }
        if (tetoTimer) {
            window.clearTimeout(tetoTimer);
            tetoTimer = null;
        }
        if (!overlay || !aberto) return;
        overlay.classList.remove("is-open");
        overlay.setAttribute("aria-hidden", "true");
        aberto = false;
    }

    function agendar(mensagem) {
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(function () {
            timer = null;
            mostrar(mensagem);
            armarTeto();
        }, ATRASO_MS);
    }

    /* ---------------------------------------------------------------------
       Navegação por link
       --------------------------------------------------------------------- */

    function ehNavegacaoInterna(link, evento) {
        if (evento.defaultPrevented) return false;
        if (evento.button !== 0) return false;
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return false;

        if (link.hasAttribute("download")) return false;
        if (link.getAttribute("target") === "_blank") return false;
        if (link.dataset.noLoader === "true") return false;

        var href = link.getAttribute("href") || "";
        if (!href) return false;
        if (href.charAt(0) === "#") return false;
        if (/^(mailto:|tel:|javascript:|whatsapp:|blob:|data:)/i.test(href)) return false;

        /* Link para outro host abre fora do painel: o overlay ficaria preso. */
        if (link.host && link.host !== window.location.host) return false;

        /* Mesma página, só mudando a âncora. */
        if (
            link.pathname === window.location.pathname &&
            link.search === window.location.search &&
            link.hash
        ) {
            return false;
        }

        return true;
    }

    /* Os dois ouvintes ficam na fase de bolha de propósito: assim rodam depois
       do código da própria tela e enxergam o preventDefault de quem trata o
       evento por fetch — como os modais do painel, que salvam sem sair da
       página e deixariam o overlay girando à toa. */
    document.addEventListener("click", function (evento) {
        var link = evento.target.closest ? evento.target.closest("a[href]") : null;
        if (!link) return;
        if (!ehNavegacaoInterna(link, evento)) return;

        agendar(link.dataset.loaderMsg || "Abrindo " + (link.textContent || "").trim().slice(0, 40));
    });

    /* ---------------------------------------------------------------------
       Envio de formulário
       --------------------------------------------------------------------- */

    document.addEventListener("submit", function (evento) {
        var form = evento.target;
        if (!form || form.dataset.noLoader === "true") return;
        if (evento.defaultPrevented) return;

        /* Formulário interceptado por fetch/AJAX chama LSLoader na mão. */
        if (form.hasAttribute("data-ajax")) return;

        agendar(form.dataset.loaderMsg || "Salvando…");
    });

    /* ---------------------------------------------------------------------
       Fechamento
       --------------------------------------------------------------------- */

    /* Voltar pelo histórico traz a página do cache: o overlay precisa sumir. */
    window.addEventListener("pageshow", esconder);
    window.addEventListener("load", esconder);

    /* Rede travada, download servido com Content-Disposition ou navegação
       cancelada deixam a página no lugar. Sem este teto o overlay giraria
       para sempre por cima de uma tela que já está utilizável. */
    var TETO_MS = 20000;

    function armarTeto() {
        if (tetoTimer) window.clearTimeout(tetoTimer);
        tetoTimer = window.setTimeout(esconder, TETO_MS);
    }

    document.addEventListener("keydown", function (evento) {
        if (evento.key === "Escape") esconder();
    });

    window.LSLoader = {
        show: mostrar,
        hide: esconder,
        schedule: agendar
    };
})(window, document);
