/* =========================================================================
   ls-reveal.js — entrada por rolagem e skeletons.
   -------------------------------------------------------------------------
   Não exige marcação nova nos templates: as seções, os cards das grades e as
   imagens lazy são identificados aqui. Se algo falhar, o failsafe do <head>
   devolve a página inteira visível.
   ========================================================================= */
(function () {
    "use strict";

    var root = document.documentElement;

    /* O <head> agenda um timer que desliga o modo "escondido" se este arquivo
       não rodar. Chegamos até aqui, então o timer pode ser cancelado. */
    if (window.__lsRevealFailsafe) {
        clearTimeout(window.__lsRevealFailsafe);
        window.__lsRevealFailsafe = null;
    }

    var semMovimento = window.matchMedia
        ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
        : false;

    var temObserver = "IntersectionObserver" in window;

    /* Sem suporte a IntersectionObserver a página é entregue pronta. */
    if (!temObserver) {
        root.classList.remove("ls-reveal-on");
    }

    /* ---------------------------------------------------------------------
       1. Descoberta dos blocos que entram em cena
       --------------------------------------------------------------------- */

    var SELETOR_BLOCOS = [
        /* Blocos que ficam ENTRE o cabeçalho e o <main>. Estavam de fora
           porque a lista só olhava para dentro de main e do rodapé -- e o
           visitante passava por eles, no começo da página, sem nenhum
           efeito. É a primeira coisa que ele vê depois do topo. */
        "body > .ls-faixa-marca",
        "body > section",

        "main.content-section > section",
        "main.content-section > article",

        /* Invólucros de layout. Várias páginas embrulham o conteúdo em um
           ou dois <div> (.loja-page > .loja-shell, .maintenance-page >
           .maintenance-shell, .est-page), e as seções viravam netas ou
           bisnetas do <main> -- ficavam de fora por um ou dois degraus.
           Dois níveis cobrem todas as páginas do site hoje; mais do que
           isso começaria a pegar conteúdo de dentro das seções. */
        "main.content-section > div > section",
        "main.content-section > div > article",
        "main.content-section > div > div > section",
        "main.content-section > div > div > article",
        "main.content-section > .ls-home-hero",
        "main.content-section > .ls-home-stats",
        "footer.ls-footer > .ls-footer-grid",
        "footer.ls-footer > .ls-clientes-strip",
        "footer.ls-footer > .ls-app-strip",
        "footer.ls-footer > .ls-footer-bottom"
    ].join(",");

    /* Uma grade só vale o efeito escalonado se tiver cards de verdade. */
    var MIN_CARDS_PARA_ESCALONAR = 3;
    var MAX_CARDS_ESCALONADOS = 12;
    var PASSO_DELAY_MS = 55;

    function elementos(lista) {
        return Array.prototype.slice.call(lista);
    }

    function ehGrade(el) {
        var display = window.getComputedStyle(el).display;
        return display === "grid" || display === "flex";
    }

    /* Procura, sem descer o DOM inteiro, a primeira grade de cards da seção. */
    function acharGrade(secao) {
        var candidatos = elementos(secao.children);
        var profundidade = 0;
        /* Teto de nós visitados: a varredura acontece no carregamento e não
           pode custar mais do que o efeito que ela habilita. */
        var orcamento = 400;

        while (candidatos.length && profundidade < 4 && orcamento > 0) {
            var proximos = [];

            for (var i = 0; i < candidatos.length && orcamento > 0; i++) {
                var el = candidatos[i];
                var filhos = el.children;
                orcamento -= 1;

                if (filhos.length >= MIN_CARDS_PARA_ESCALONAR && ehGrade(el)) {
                    return el;
                }

                for (var j = 0; j < filhos.length; j++) {
                    proximos.push(filhos[j]);
                }
            }

            candidatos = proximos;
            profundidade += 1;
        }

        return null;
    }

    function marcar(el, tipo, atraso) {
        if (!el || el.hasAttribute("data-ls-reveal")) return;
        el.setAttribute("data-ls-reveal", tipo || "up");
        if (atraso) {
            el.style.setProperty("--ls-reveal-delay", atraso + "ms");
        }
    }

    function prepararBlocos() {
        var blocos = elementos(document.querySelectorAll(SELETOR_BLOCOS));

        blocos.forEach(function (bloco, indice) {
            var grade = acharGrade(bloco);
            var cards = grade ? elementos(grade.children) : [];

            if (cards.length >= MIN_CARDS_PARA_ESCALONAR) {
                /* A seção some só com opacidade; o movimento fica nos cards. */
                marcar(bloco, "fade");

                cards.slice(0, MAX_CARDS_ESCALONADOS).forEach(function (card, i) {
                    marcar(card, "up", i * PASSO_DELAY_MS);
                });

                /* Cards além do limite entram sem atraso: em listas longas o
                   escalonamento viraria espera. */
                cards.slice(MAX_CARDS_ESCALONADOS).forEach(function (card) {
                    marcar(card, "up", 0);
                });
            } else {
                marcar(bloco, "up");
            }

            /* A primeira dobra nunca espera rolagem. */
            if (indice === 0) {
                revelar(bloco);
            }
        });

        /* ls-defer-paint (content-visibility) fica como recurso opcional e não
           é aplicado em massa: as seções da home têm alturas muito diferentes
           entre si, e a altura estimada faria a barra de rolagem saltar na
           primeira descida — trocaria o espaço branco por um salto. */

        /* Marcação legada, ainda usada em páginas de produto e catálogo. */
        elementos(document.querySelectorAll("[data-scroll-reveal]"))
            .forEach(function (el) {
                marcar(el, "up");
            });
    }

    /* ---------------------------------------------------------------------
       2. Observador de entrada
       --------------------------------------------------------------------- */

    function revelar(el) {
        el.classList.add("is-visible");

        /* Depois da transição o elemento vira conteúdo comum outra vez. */
        window.setTimeout(function () {
            el.classList.add("is-settled");
        }, 900);
    }

    var observador = null;

    if (temObserver) {
        observador = new IntersectionObserver(function (entradas) {
            entradas.forEach(function (entrada) {
                if (!entrada.isIntersecting) return;
                revelar(entrada.target);
                observador.unobserve(entrada.target);
            });
        }, {
            /* Começa a animação um pouco antes de o bloco tocar a viewport:
               é isso que elimina a sensação de "esperar o conteúdo chegar". */
            rootMargin: "0px 0px -8% 0px",
            threshold: 0.04
        });
    }

    function observarTudo() {
        if (!observador) return;
        elementos(document.querySelectorAll("[data-ls-reveal]:not(.is-visible)"))
            .forEach(function (el) {
                observador.observe(el);
            });
    }

    /* ---------------------------------------------------------------------
       3. Skeleton das imagens
       --------------------------------------------------------------------- */

    function encerrarSkeleton(img, falhou) {
        img.classList.remove("ls-img-skeleton");
        img.classList.add(falhou ? "is-failed" : "is-loaded");
    }

    var FORA_DO_SKELETON = "header, .ls-quick-dock, .ls-cart-loader, .ls-page-loader";

    function prepararImagem(img) {
        if (img.hasAttribute("data-ls-img")) return;
        if (img.dataset.lsSkipSkeleton === "true") return;
        /* Logo, ícones fixos e overlays precisam aparecer na hora. */
        if (img.closest && img.closest(FORA_DO_SKELETON)) return;

        img.setAttribute("data-ls-img", "");

        /* Imagem que já veio do cache não precisa de brilho nenhum. */
        if (img.complete && img.naturalWidth > 0) {
            img.classList.add("is-loaded");
            return;
        }

        img.classList.add("ls-img-skeleton");

        img.addEventListener("load", function () {
            encerrarSkeleton(img, false);
        }, { once: true });

        img.addEventListener("error", function () {
            encerrarSkeleton(img, true);
        }, { once: true });
    }

    function prepararImagens(escopo) {
        elementos((escopo || document).querySelectorAll("img"))
            .forEach(prepararImagem);
    }

    /* ---------------------------------------------------------------------
       4. (vago) A barra do topo é só do carregamento
       ---------------------------------------------------------------------
       Existia aqui uma barra que media a posição da rolagem. Ela dividia o
       lugar -- e a aparência -- com a barra de carregamento, então o mesmo
       traço no topo ora contava quanto faltava da página, ora quanto
       faltava para a próxima chegar. Duas contas no mesmo pixel: quem olha
       não tem como saber qual das duas está vendo. A do carregamento ficou
       (ls-page-loader.js); esta saiu.
       --------------------------------------------------------------------- */

    /* ---------------------------------------------------------------------
       5. Conteúdo criado depois (modais, resultados de filtro, etc.)
       --------------------------------------------------------------------- */

    function acompanharNovosNos() {
        if (!("MutationObserver" in window)) return;

        var pendente = false;

        var mo = new MutationObserver(function (mutacoes) {
            for (var i = 0; i < mutacoes.length; i++) {
                if (mutacoes[i].addedNodes.length) {
                    pendente = true;
                    break;
                }
            }

            if (!pendente) return;
            pendente = false;

            window.requestAnimationFrame(function () {
                prepararImagens(document);
            });
        });

        mo.observe(document.body, { childList: true, subtree: true });
    }

    /* ---------------------------------------------------------------------
       6. Início
       --------------------------------------------------------------------- */

    function iniciar() {
        prepararImagens(document);

        if (temObserver && !semMovimento) {
            prepararBlocos();
            observarTudo();
        } else {
            root.classList.remove("ls-reveal-on");
        }

        acompanharNovosNos();

        /* Âncora com hash precisa do destino já pintado. */
        if (window.location.hash) {
            var alvo = document.querySelector(window.location.hash);
            if (alvo) {
                var bloco = alvo.closest("[data-ls-reveal]") || alvo;
                bloco.classList.add("is-visible", "is-settled");
                bloco.classList.remove("ls-defer-paint");
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar, { once: true });
    } else {
        iniciar();
    }
})();
