/* =========================================================================
   ls-page-loader.js — barra de carregamento no topo da página.
   -------------------------------------------------------------------------
   Uso automático: qualquer clique em link interno ou envio de formulário.
   Uso manual:     LSLoader.show("Gerando relatório…") / LSLoader.hide()

   O avanço é função do tempo decorrido, e não de um passo fixo por
   intervalo: p(t) = TETO * (1 - e^(-t/TAU)). A curva anda depressa no
   começo, quando quase toda navegação termina, e vai desacelerando --
   assim ela nunca encosta no fim antes de a página chegar, e nunca fica
   parada dando a impressão de travamento.
   ========================================================================= */
(function (window, document) {
    "use strict";

    /* Só aparece se a navegação passar disso. Abaixo, a página nova já
       chegou e a barra só piscaria na tela. */
    var ATRASO_MS = 140;

    /* Constante de tempo da curva: em TAU ms a barra faz ~63% do caminho
       até o teto. Calibrado para a navegação típica deste site. */
    var TAU_MS = 900;

    /* Teto do avanço automático. Os 8% que sobram são o pulo final, quando
       a página realmente chega -- é isso que faz a barra terminar em vez
       de simplesmente sumir. */
    var TETO = 0.92;

    var trilho = null;
    var barra = null;
    var aviso = null;
    var timer = null;
    var tetoTimer = null;
    var quadro = null;
    var inicio = 0;
    var aberto = false;

    function montar() {
        if (barra) return barra;

        trilho = document.querySelector(".ls-load-track");

        if (!trilho) {
            trilho = document.createElement("div");
            trilho.className = "ls-load-track";
            trilho.setAttribute("aria-hidden", "true");

            barra = document.createElement("div");
            barra.className = "ls-load-progress";
            trilho.appendChild(barra);

            document.body.appendChild(trilho);
        } else {
            barra = trilho.querySelector(".ls-load-progress");
        }

        aviso = document.querySelector(".ls-load-status");
        if (!aviso) {
            aviso = document.createElement("div");
            aviso.className = "ls-load-status";
            aviso.setAttribute("role", "status");
            aviso.setAttribute("aria-live", "polite");
            document.body.appendChild(aviso);
        }

        return barra;
    }

    function pintar(fracao) {
        barra.style.transform = "scaleX(" + fracao + ")";
    }

    function passo() {
        if (!aberto) return;
        var decorrido = window.performance.now() - inicio;
        pintar(TETO * (1 - Math.exp(-decorrido / TAU_MS)));
        quadro = window.requestAnimationFrame(passo);
    }

    function mostrar(mensagem) {
        montar();

        if (aberto) return;
        aberto = true;

        aviso.textContent = mensagem || "Carregando a página…";

        /* Volta ao zero sem animar: sem isto a barra da navegação anterior
           encolheria da direita para a esquerda na frente do visitante. */
        barra.style.transition = "none";
        pintar(0);
        /* Leitura forçada para o navegador aplicar o zero antes de a
           transição voltar -- sem ela as duas mudanças viram uma só. */
        void barra.offsetWidth;
        barra.style.transition = "";

        trilho.classList.add("is-active");

        inicio = window.performance.now();
        quadro = window.requestAnimationFrame(passo);
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
        if (!barra || !aberto) return;

        aberto = false;
        if (quadro) {
            window.cancelAnimationFrame(quadro);
            quadro = null;
        }

        /* Fecha o percurso antes de sumir. Sumir no meio pareceria erro. */
        pintar(1);
        aviso.textContent = "";

        window.setTimeout(function () {
            if (aberto) return;
            trilho.classList.remove("is-active");
        }, 220);
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

        /* Link para outro host abre fora do painel: a barra ficaria presa. */
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
       página e deixariam a barra correndo à toa. */
    document.addEventListener("click", function (evento) {
        var link = evento.target.closest ? evento.target.closest("a[href]") : null;
        if (!link) return;

        /* Quem já tratou o clique não vai trocar de página, e a barra
           ficaria correndo por cima de uma tela que continua ali.
           
           O comentário acima sempre disse que era para ser assim -- os
           ouvintes ficam na bolha justamente para enxergar o
           preventDefault de quem trata por fetch --, mas a conferência
           existia só no envio de formulário, não no clique. Resultado: no
           painel interno, onde a troca de tela é por fetch, a barra
           aparecia e sumia a cada clique. Era a "sensação de
           carregamento" numa troca que não carrega nada. */
        if (evento.defaultPrevented) return;

        if (!ehNavegacaoInterna(link, evento)) return;

        agendar(link.dataset.loaderMsg || "Carregando a página…");
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

        agendar(form.dataset.loaderMsg || "Enviando…");
    });

    /* ---------------------------------------------------------------------
       Fechamento
       --------------------------------------------------------------------- */

    /* Voltar pelo histórico traz a página do cache: a barra precisa sumir. */
    window.addEventListener("pageshow", esconder);
    window.addEventListener("load", esconder);

    /* Rede travada, download servido com Content-Disposition ou navegação
       cancelada deixam a página no lugar. Sem este teto a barra correria
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
