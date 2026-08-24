/* =========================================================================
   ls-ancoras.js — links com # que param no lugar certo.
   -------------------------------------------------------------------------
   O cabeçalho é sticky, então a rolagem nativa deixa o alvo escondido atrás
   dele. Além disso a página revela os blocos ao rolar: um alvo abaixo da
   dobra ainda pode estar invisível quando o navegador salta até ele.
   Este arquivo resolve os dois: mede o cabeçalho, revela o destino e rola
   com folga, destacando por um instante onde a pessoa parou.
   ========================================================================= */
(function () {
    "use strict";

    var DESTAQUE_MS = 1400;

    function cabecalho() {
        var header = document.querySelector("header");
        if (!header) return 0;

        var estilo = window.getComputedStyle(header);
        if (estilo.position !== "sticky" && estilo.position !== "fixed") {
            return 0;
        }
        return header.getBoundingClientRect().height;
    }

    /* A altura do cabeçalho muda entre desktop e celular (o menu quebra em
       duas linhas), então vira variável de CSS em vez de número fixo. */
    function medir() {
        var altura = Math.round(cabecalho());
        document.documentElement.style.setProperty(
            "--ls-ancora-offset",
            (altura + 16) + "px"
        );
        return altura + 16;
    }

    function semMovimento() {
        return window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    /* O alvo pode estar escondido pelo motor de revelação. Mostrar antes de
       medir a posição evita rolar para uma altura que muda logo em seguida. */
    function revelar(alvo) {
        var bloco = alvo.closest("[data-ls-reveal]");
        if (bloco) {
            bloco.classList.add("is-visible", "is-settled");
        }
        alvo.querySelectorAll("[data-ls-reveal]").forEach(function (filho) {
            filho.classList.add("is-visible", "is-settled");
        });
    }

    function destacar(alvo) {
        alvo.classList.add("ls-ancora-alvo");
        window.setTimeout(function () {
            alvo.classList.remove("ls-ancora-alvo");
        }, DESTAQUE_MS);
    }

    function irPara(alvo, suave) {
        if (!alvo) return;

        revelar(alvo);
        var folga = medir();

        /* Duas passadas: a primeira força o layout do bloco recém-revelado,
           a segunda mede a posição já definitiva. */
        window.requestAnimationFrame(function () {
            var topo =
                alvo.getBoundingClientRect().top + window.scrollY - folga;

            window.scrollTo({
                top: Math.max(topo, 0),
                behavior: suave && !semMovimento() ? "smooth" : "auto"
            });

            destacar(alvo);

            /* Foco para leitor de tela e teclado, sem roubar a rolagem que
               acabamos de calcular. */
            if (!alvo.hasAttribute("tabindex")) {
                alvo.setAttribute("tabindex", "-1");
            }
            try {
                alvo.focus({ preventScroll: true });
            } catch (erro) {
                /* navegadores antigos ignoram preventScroll */
            }
        });
    }

    function alvoDoHash(hash) {
        if (!hash || hash === "#") return null;
        try {
            return document.querySelector(hash);
        } catch (erro) {
            /* hash que não é seletor válido (#, #!, etc.) */
            return null;
        }
    }

    /* ---------------------------------------------------------------------
       Clique em link interno
       --------------------------------------------------------------------- */
    document.addEventListener("click", function (evento) {
        var link = evento.target.closest ? evento.target.closest("a[href]") : null;
        if (!link || evento.defaultPrevented) return;
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
        if (link.getAttribute("target") === "_blank") return;

        var hash = link.hash;
        if (!hash) return;

        /* Só trata âncora da própria página; link para outra página com #
           é resolvido no carregamento de lá. */
        if (link.pathname !== window.location.pathname) return;
        if (link.search !== window.location.search) return;

        var alvo = alvoDoHash(hash);
        if (!alvo) return;

        evento.preventDefault();
        irPara(alvo, true);

        if (window.history && window.history.pushState) {
            window.history.pushState(null, "", hash);
        }
    });

    /* ---------------------------------------------------------------------
       Chegada com # na URL
       --------------------------------------------------------------------- */
    function tratarHashInicial() {
        var alvo = alvoDoHash(window.location.hash);
        if (!alvo) return;

        /* O navegador já saltou (errado, por baixo do cabeçalho). Corrige
           logo e de novo depois que fontes e imagens acomodam a altura. */
        irPara(alvo, false);
        window.setTimeout(function () { irPara(alvo, false); }, 320);
    }

    window.addEventListener("hashchange", function () {
        var alvo = alvoDoHash(window.location.hash);
        if (alvo) irPara(alvo, true);
    });

    window.addEventListener("resize", medir, { passive: true });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            medir();
            tratarHashInicial();
        }, { once: true });
    } else {
        medir();
        tratarHashInicial();
    }

    window.addEventListener("load", medir);
})();
