/* Comportamento de gestao / manutencao_adm.
 *
 * NASCEU DE DENTRO DO HTML. Eram 16 KB de <script> no template --
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

    var root      = document.getElementById("mntRoot");
    var overlay   = document.getElementById("mntLoading");
    var overlayTx = document.getElementById("mntLoadingText");
    var grid      = document.getElementById("mntGrid");
    if (!root) return;

    var travado = false;

    /* ==========================================================
       OVERLAY / TRAVA CONTRA CLIQUE DUPLO
       ========================================================== */
    function abrirLoading(texto) {
        if (overlayTx) overlayTx.textContent = texto || "Carregando...";
        if (overlay) {
            overlay.classList.add("is-on");
            overlay.setAttribute("aria-hidden", "false");
        }
        document.body.classList.add("mnt-locked");
        if (grid) grid.classList.add("is-reloading");
        travado = true;
    }

    function fecharLoading() {
        if (overlay) {
            overlay.classList.remove("is-on");
            overlay.setAttribute("aria-hidden", "true");
        }
        document.body.classList.remove("mnt-locked");
        if (grid) grid.classList.remove("is-reloading");
        travado = false;
        document.querySelectorAll(".mnt-btn.is-loading")
            .forEach(function (b) { b.classList.remove("is-loading"); });
        document.querySelectorAll(".mnt-modal.is-busy")
            .forEach(function (d) { d.classList.remove("is-busy"); });
        document.querySelectorAll("form[data-busy]")
            .forEach(function (f) { f.removeAttribute("data-busy"); });
    }

    /* Voltar pelo histórico (bfcache) não pode deixar a tela travada. */
    window.addEventListener("pageshow", fecharLoading);

    /* ==========================================================
       ENVIO DE FORMULÁRIOS — um clique só
       ========================================================== */
    document.querySelectorAll("form[data-loading-form]").forEach(function (form) {
        form.addEventListener("submit", function (evento) {
            if (form.getAttribute("data-busy")) {
                evento.preventDefault();
                return;
            }

            var botao = evento.submitter;

            /* Ações destrutivas (ex.: cancelar) pedem confirmação antes. */
            if (botao && botao.hasAttribute("data-confirm")) {
                var pergunta = botao.getAttribute("data-confirm");
                if (!window.confirm(pergunta)) {
                    evento.preventDefault();
                    return;
                }
            }

            if (form.hasAttribute("data-status-form")) {
                var escolhido = form.querySelector('input[name="status"]:checked');
                var atual = form.getAttribute("data-atual");
                if (!escolhido) {
                    evento.preventDefault();
                    return;
                }
                if (escolhido.value === atual) {
                    evento.preventDefault();
                    return;
                }
                var modal = form.closest(".mnt-modal");
                if (modal) modal.classList.add("is-busy");
            }

            form.setAttribute("data-busy", "1");
            if (botao && botao.classList.contains("mnt-btn")) {
                botao.classList.add("is-loading");
            }

            var texto = "Aplicando filtros...";
            if (form.hasAttribute("data-status-form") || form.hasAttribute("data-confirm-status")) {
                texto = "Atualizando o andamento...";
            }
            abrirLoading(texto);
        });
    });

    /* Selects da barra de filtros aplicam sozinhos. */
    document.querySelectorAll("[data-auto-submit]").forEach(function (campo) {
        campo.addEventListener("change", function () {
            var form = campo.form;
            if (form && !form.getAttribute("data-busy")) {
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit();
                } else {
                    form.submit();
                    abrirLoading("Aplicando filtros...");
                }
            }
        });
    });

    /* Links de navegação (paginação, cards de métrica, limpar). */
    document.querySelectorAll("a[data-nav]").forEach(function (link) {
        link.addEventListener("click", function (evento) {
            if (travado) { evento.preventDefault(); return; }
            if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.button !== 0) return;
            abrirLoading("Carregando solicitações...");
        });
    });

    /* ==========================================================
       BUSCA — atalho "/", limpar com um clique e auto-aplicar
       ========================================================== */
    var campoBusca   = document.getElementById("busca");
    var botaoLimpar  = document.getElementById("mntSearchClear");

    if (campoBusca) {
        var valorInicialBusca = campoBusca.value;
        var temporizadorBusca = null;

        campoBusca.addEventListener("input", function () {
            if (botaoLimpar) botaoLimpar.hidden = campoBusca.value.length === 0;

            window.clearTimeout(temporizadorBusca);
            temporizadorBusca = window.setTimeout(function () {
                if (campoBusca.value === valorInicialBusca) return;
                var form = campoBusca.form;
                if (form && !form.getAttribute("data-busy")) {
                    if (typeof form.requestSubmit === "function") {
                        form.requestSubmit();
                    } else {
                        form.submit();
                        abrirLoading("Aplicando filtros...");
                    }
                }
            }, 600);
        });

        document.addEventListener("keydown", function (evento) {
            if (evento.key !== "/") return;
            var alvo = evento.target;
            var digitando =
                alvo && (alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.isContentEditable);
            if (digitando || travado) return;
            evento.preventDefault();
            campoBusca.focus();
        });
    }

    if (botaoLimpar && campoBusca) {
        botaoLimpar.addEventListener("click", function () {
            campoBusca.value = "";
            botaoLimpar.hidden = true;
            var form = campoBusca.form;
            if (form && !form.getAttribute("data-busy")) {
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit();
                } else {
                    form.submit();
                    abrirLoading("Aplicando filtros...");
                }
            }
        });
    }

    /* ==========================================================
       MENSAGENS — some sozinhas e podem ser fechadas na hora
       ========================================================== */
    document.querySelectorAll(".adm-messages .adm-alert").forEach(function (aviso) {
        if (aviso.querySelector(".mnt-msg-close")) return;

        var fechar = document.createElement("button");
        fechar.type = "button";
        fechar.className = "mnt-msg-close";
        fechar.setAttribute("aria-label", "Dispensar aviso");
        fechar.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        aviso.style.position = "relative";
        aviso.style.paddingRight = "38px";
        aviso.appendChild(fechar);

        var sumir = function () {
            aviso.style.transition = "opacity .25s ease, transform .25s ease";
            aviso.style.opacity = "0";
            aviso.style.transform = "translateY(-4px)";
            window.setTimeout(function () { aviso.remove(); }, 260);
        };

        fechar.addEventListener("click", sumir);
        window.setTimeout(sumir, 7000);
    });

    /* ==========================================================
       CONTATO INTELIGENTE — só um menu "mais opções" aberto por vez
       ========================================================== */
    var menusContato = document.querySelectorAll(".mnt-contact-more");
    menusContato.forEach(function (menu) {
        menu.addEventListener("toggle", function () {
            if (!menu.open) return;
            menusContato.forEach(function (outro) {
                if (outro !== menu) outro.open = false;
            });
        });
    });

    document.addEventListener("click", function (evento) {
        menusContato.forEach(function (menu) {
            if (menu.open && !menu.contains(evento.target)) menu.open = false;
        });
    });

    document.addEventListener("keydown", function (evento) {
        if (evento.key !== "Escape") return;
        menusContato.forEach(function (menu) { menu.open = false; });
    });

    /* ==========================================================
       MODAIS
       ========================================================== */
    function abrirModal(id) {
        var modal = document.getElementById(id);
        if (!modal || modal.open) return;
        modal.showModal();
        document.body.classList.add("mnt-locked");
    }

    function fecharModal(modal) {
        if (!modal || !modal.open) return;
        modal.close();
        if (!document.querySelector("dialog[open]")) {
            document.body.classList.remove("mnt-locked");
        }
    }

    document.querySelectorAll("[data-open]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            abrirModal(botao.getAttribute("data-open"));
        });
    });

    document.querySelectorAll(".mnt-modal").forEach(function (modal) {
        modal.querySelectorAll("[data-close]").forEach(function (botao) {
            botao.addEventListener("click", function () { fecharModal(modal); });
        });

        /* Clique fora do conteúdo fecha — a menos que esteja salvando. */
        modal.addEventListener("click", function (evento) {
            if (modal.classList.contains("is-busy")) return;
            if (evento.target !== modal) return;
            var caixa = modal.getBoundingClientRect();
            var fora =
                evento.clientX < caixa.left || evento.clientX > caixa.right ||
                evento.clientY < caixa.top  || evento.clientY > caixa.bottom;
            if (fora) fecharModal(modal);
        });

        modal.addEventListener("cancel", function (evento) {
            if (modal.classList.contains("is-busy")) evento.preventDefault();
        });

        modal.addEventListener("close", function () {
            if (!document.querySelector("dialog[open]")) {
                document.body.classList.remove("mnt-locked");
            }
        });
    });

    /* Marca visualmente que existe alteração de status pendente. */
    document.querySelectorAll("[data-status-form]").forEach(function (form) {
        var atual = form.getAttribute("data-atual");
        form.querySelectorAll('input[name="status"]').forEach(function (radio) {
            radio.addEventListener("change", function () {
                form.classList.toggle("is-dirty", radio.value !== atual);
            });
        });
    });

    /* ==========================================================
       LIGHTBOX COM NAVEGAÇÃO
       ========================================================== */
    var lb       = document.getElementById("mntLightbox");
    var lbImg    = document.getElementById("mntLbImage");
    var lbTitle  = document.getElementById("mntLbTitle");
    var lbCount  = document.getElementById("mntLbCount");
    var lbPrev   = document.getElementById("mntLbPrev");
    var lbNext   = document.getElementById("mntLbNext");
    var lbClose  = document.getElementById("mntLbClose");
    var lbLista  = [];
    var lbIndice = 0;

    function pintarLightbox() {
        var item = lbLista[lbIndice];
        if (!item) return;
        lbImg.src = item.src;
        lbImg.alt = item.caption;
        lbTitle.textContent = item.caption;
        lbCount.textContent = (lbIndice + 1) + " / " + lbLista.length;
        var unica = lbLista.length < 2;
        lbPrev.style.visibility = unica ? "hidden" : "visible";
        lbNext.style.visibility = unica ? "hidden" : "visible";
    }

    function andarLightbox(passo) {
        if (!lbLista.length) return;
        lbIndice = (lbIndice + passo + lbLista.length) % lbLista.length;
        pintarLightbox();
    }

    document.querySelectorAll("[data-lightbox]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            var galeria = botao.closest("[data-gallery]");
            var itens = galeria
                ? Array.prototype.slice.call(galeria.querySelectorAll("[data-lightbox]"))
                : [botao];

            lbLista = itens.map(function (el) {
                return {
                    src: el.getAttribute("data-src"),
                    caption: el.getAttribute("data-caption") || "Imagem da manutenção"
                };
            });
            lbIndice = Math.max(0, itens.indexOf(botao));
            pintarLightbox();

            if (!lb.open) lb.showModal();
            document.body.classList.add("mnt-locked");
        });
    });

    if (lbPrev)  lbPrev.addEventListener("click", function () { andarLightbox(-1); });
    if (lbNext)  lbNext.addEventListener("click", function () { andarLightbox(1); });
    if (lbClose) lbClose.addEventListener("click", function () { lb.close(); });

    if (lb) {
        lb.addEventListener("close", function () {
            lbImg.src = "";
            if (!document.querySelector("dialog[open]")) {
                document.body.classList.remove("mnt-locked");
            }
        });
        lb.addEventListener("click", function (evento) {
            if (evento.target === lb) lb.close();
        });
    }

    document.addEventListener("keydown", function (evento) {
        if (!lb || !lb.open) return;
        if (evento.key === "ArrowRight") andarLightbox(1);
        if (evento.key === "ArrowLeft")  andarLightbox(-1);
    });

    /* ==========================================================
       COPIAR PARA A ÁREA DE TRANSFERÊNCIA
       ========================================================== */
    document.querySelectorAll("[data-copy]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            var texto = botao.getAttribute("data-copy") || "";
            var rotulo = botao.getAttribute("data-copy-label") || "Copiado";
            var original = botao.innerHTML;

            function confirmar() {
                var soIcone = botao.classList.contains("mnt-ico-btn");
                botao.innerHTML = soIcone
                    ? '<i class="fa-solid fa-check"></i>'
                    : '<i class="fa-solid fa-check"></i> ' + rotulo;
                setTimeout(function () { botao.innerHTML = original; }, 1700);
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(texto).then(confirmar).catch(function () {
                    window.prompt("Copie o conteúdo:", texto);
                });
            } else {
                window.prompt("Copie o conteúdo:", texto);
            }
        });
    });

    /* ==========================================================
       DESTAQUE APÓS SALVAR (?foco=<id>)
       ========================================================== */
    var foco = new URLSearchParams(window.location.search).get("foco");
    if (foco) {
        var card = document.getElementById("manutencao-" + foco);
        if (card) {
            setTimeout(function () {
                card.scrollIntoView({ behavior: "smooth", block: "center" });
                card.classList.add("is-focus");
                setTimeout(function () { card.classList.remove("is-focus"); }, 2600);
            }, 160);
        }
    }
})();
