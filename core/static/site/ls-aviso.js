/* =========================================================================
   ls-aviso.js — os avisos "de aplicativo", no site e no painel.
   -------------------------------------------------------------------------
   O pedido: "este tipo de mensagem deve virar um modal moderno que aparece
   estilo app para avisar, eu falei que quero estilo app em tudo" -- sobre a
   caixa do Bootstrap "A importação de ... foi descartada." no alto da tela.

   UM SISTEMA SÓ, PARA TODO AVISO DO SITE E DO PAINEL:

     * TOAST para o recado comum: no alto e no centro no celular (abaixo do
       entalhe), no alto à direita no computador. Ícone do nível, título e
       texto, botão de ação opcional. Some sozinho (5 s; o alerta, 7 s), e
       o tempo para enquanto o ponteiro ou o foco estão nele; o de ERRO fica
       até alguém fechar. Arrastar para o lado (ou para cima) dispensa.
     * FOLHA para o que precisa de atenção: cartão no meio no computador,
       folha que sobe de baixo no celular. Prende o foco, fecha no Esc, um
       botão principal. É ela que substitui o `confirm()` do navegador.

   API (window.LSAviso):

     LSAviso.toast({nivel, titulo, texto, icone, acao, duracao, fixo})
         nivel: "sucesso" | "info" | "alerta" | "erro" (vale também
         success, warning, error, ok). acao: {rotulo, url} ou
         {rotulo, aoClicar}. duracao em ms (0 = fixo). Devolve {fechar()}.
     await LSAviso.modal({nivel, titulo, texto, icone, botao, acao})
         A folha de um botão ("Entendi"). Com `acao`, o botão é a ação.
     await LSAviso.confirmar({titulo, texto, confirmar, cancelar, perigo})
         -> true / false. No lugar do window.confirm. `perigo` deixa o
         botão principal vermelho (exclusão). Aceita só o texto também.

   DECLARATIVO, para o que é formulário ou link (sem escrever JavaScript):

     <form data-ls-confirmar="Excluir esta movimentação?"
           data-ls-confirmar-titulo="Excluir movimentação"
           data-ls-confirmar-botao="Excluir" data-ls-perigo>

   O envio (ou a ida do link) só acontece depois do "sim". Vale no <form>,
   no botão de envio e no <a>. `data-ls-confirmar-cancelar` troca o rótulo
   do "Cancelar" (quando a própria ação já se chama cancelar), e
   `data-ls-confirmar-icone` o ícone (o de perigo é a lixeira).

   OS RECADOS DO SERVIDOR (o `messages` do Django) chegam como cartões com
   `data-*` (partials/ls_avisos.html, core/ls_aviso.py); este arquivo os lê
   ao abrir a página e a cada troca de tela do painel (`ls:tela`).

   Sem dependência: nem Bootstrap, nem fonte de ícones -- os ícones são
   SVG daqui mesmo, e as cores vêm do tema de quem carrega (ls-aviso.css).
   ========================================================================= */
(function (window, document) {
    "use strict";

    if (window.LSAviso) return;

    var NIVEIS = {
        sucesso: "sucesso", success: "sucesso", ok: "sucesso",
        info: "info", debug: "info",
        alerta: "alerta", aviso: "alerta", warning: "alerta",
        erro: "erro", error: "erro", danger: "erro"
    };
    var DURACAO = { sucesso: 5000, info: 5000, alerta: 7000, erro: 0 };
    var TITULO = { sucesso: "Pronto", info: "Aviso", alerta: "Atenção", erro: "Não foi possível" };
    /* Mais do que isto na tela é ruído: o mais antigo sai (o erro por último). */
    var NO_MAXIMO = 4;
    var CHAVE_VISTOS = "ls-recados-vistos";

    /* Traço de 2 px em grade de 24 (ver o CSS: fill none, stroke currentColor).
       Os nomes são os de `core/ls_aviso.py` (ICONES): há teste que confere. */
    var ARQUIVO = '<path d="M14 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8Z"/><path d="M14 3.5V8h4.5"/>';
    var ICONES = {
        sucesso: '<circle cx="12" cy="12" r="9"/><path d="m8.2 12.4 2.6 2.6 5-5.4"/>',
        info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.2M12 7.7v.1"/>',
        alerta: '<path d="M10.3 4.2 2.9 17.4a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z"/><path d="M12 9.5v4.2M12 16.9v.1"/>',
        erro: '<circle cx="12" cy="12" r="9"/><path d="m9.2 9.2 5.6 5.6M14.8 9.2l-5.6 5.6"/>',
        lixeira: '<path d="M4 6.5h16M9.5 6.5v-2h5v2M6.5 6.5l.9 12.6a1.6 1.6 0 0 0 1.6 1.4h6a1.6 1.6 0 0 0 1.6-1.4l.9-12.6M10 10.5v6M14 10.5v6"/>',
        arquivo: ARQUIVO,
        "arquivo-x": ARQUIVO + '<path d="m10 12.5 4 4M14 12.5l-4 4"/>',
        salvo: '<path d="M5.5 4h10.2l3.8 3.8v10.7a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5V5a1 1 0 0 1 1-1Z"/><path d="M8 4v4.5h7V4M8 20v-5.5h8V20"/>',
        pessoa: '<circle cx="10" cy="8" r="3.6"/><path d="M3.5 20a6.5 6.5 0 0 1 13 0M19 8.5v6M16 11.5h6"/>',
        carrinho: '<circle cx="9.5" cy="19.5" r="1.4"/><circle cx="17" cy="19.5" r="1.4"/><path d="M3 4h2.4l2.2 11h10.2l2.1-8H6.4"/>',
        email: '<rect x="3" y="5" width="18" height="14" rx="2.2"/><path d="m3.6 6.6 8.4 6.2 8.4-6.2"/>',
        endereco: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
        fechar: '<path d="m6.5 6.5 11 11M17.5 6.5l-11 11"/>'
    };

    function svg(nome) {
        return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
            (ICONES[nome] || ICONES.info) + "</svg>";
    }

    function nivelDe(valor) {
        return NIVEIS[String(valor || "").toLowerCase()] || "info";
    }

    function semMovimento() {
        return Boolean(window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }

    function noCelular() {
        return Boolean(window.matchMedia && window.matchMedia("(max-width: 640px)").matches);
    }

    function criar(tag, classe, texto) {
        var el = document.createElement(tag);
        if (classe) el.className = classe;
        if (texto) el.textContent = texto;
        return el;
    }

    /* ---------------------------------------------------------------------
       A FALA PARA QUEM USA LEITOR DE TELA

       Duas regiões fixas, criadas de saída: região viva que nasce junto com
       o texto nem sempre é lida. A educada (status) leva sucesso, info e
       alerta; a urgente (alert) interrompe, e é só do erro.
       --------------------------------------------------------------------- */
    var falas = null;

    function garantirFalas() {
        if (falas && falas.educada.isConnected) return falas;
        falas = {
            educada: criar("div", "ls-recado-fala"),
            urgente: criar("div", "ls-recado-fala")
        };
        falas.educada.setAttribute("role", "status");
        falas.educada.setAttribute("aria-live", "polite");
        falas.urgente.setAttribute("role", "alert");
        falas.urgente.setAttribute("aria-live", "assertive");
        document.body.appendChild(falas.educada);
        document.body.appendChild(falas.urgente);
        return falas;
    }

    function anunciar(nivel, frase) {
        var regiao = garantirFalas()[nivel === "erro" ? "urgente" : "educada"];
        regiao.textContent = "";
        window.setTimeout(function () { regiao.textContent = frase; }, 80);
    }

    /* ---------------------------------------------------------------------
       A PILHA DOS TOASTS

       Vai na camada de cima (`popover="manual"`) onde o navegador sabe:
       assim o toast aparece até por cima de um <dialog> aberto, que nenhum
       z-index alcança. Sem popover, o z-index do CSS resolve o resto.

       COM UMA JANELA MODAL ABERTA, A PILHA MORA DENTRO DELA. O <dialog>
       modal deixa todo o resto da página inerte -- inclusive o toast, que
       apareceria por cima mas não fecharia no X. Dentro da janela ele é
       clicável; quando ela fecha, a pilha volta para o <body>.
       --------------------------------------------------------------------- */
    var pilha = null;
    var temPopover = typeof HTMLElement !== "undefined"
        && typeof HTMLElement.prototype.showPopover === "function";

    function garantirPilha() {
        if (pilha && pilha.isConnected) return pilha;
        pilha = criar("section", "ls-recados-pilha");
        pilha.setAttribute("aria-label", "Avisos");
        if (temPopover) pilha.setAttribute("popover", "manual");
        /* Dentro de uma janela, o clique no toast é do toast: a janela que
           fecha com "clique fora do cartão" não pode fechar por causa dele. */
        ["click", "pointerdown"].forEach(function (tipo) {
            pilha.addEventListener(tipo, function (evento) {
                if (pilha.parentNode !== document.body) evento.stopPropagation();
            });
        });
        document.body.appendChild(pilha);
        return pilha;
    }

    function janelaModalAberta() {
        var abertas = document.querySelectorAll("dialog[open]");
        for (var i = abertas.length - 1; i >= 0; i -= 1) {
            try {
                if (abertas[i].matches(":modal")) return abertas[i];
            } catch (erro) {
                return null;
            }
        }
        return null;
    }

    function mostrarPilha() {
        var casa = janelaModalAberta() || document.body;
        if (pilha.parentNode !== casa) casa.appendChild(pilha);
        if (!temPopover) return;
        try {
            /* Uma janela aberta depois da pilha fica por cima dela: tirar e
               pôr de novo a devolve ao topo. */
            if (pilha.matches(":popover-open")) pilha.hidePopover();
            pilha.showPopover();
        } catch (erro) { /* sem camada de topo: fica o z-index */ }
    }

    /* A janela que hospedava a pilha fechou (ou vai sair da página): a
       pilha volta para o <body>, ou para a janela que continuar aberta. */
    function resgatarPilha(janela) {
        if (!pilha || !janela || !janela.contains(pilha)) return;
        document.body.appendChild(pilha);
        if (pilha.querySelector(".ls-recado:not(.is-saindo)")) mostrarPilha();
    }

    document.addEventListener("close", function (evento) {
        resgatarPilha(evento.target);
    }, true);

    function esconderPilhaSeVazia() {
        if (!pilha || pilha.querySelector(".ls-recado:not(.is-saindo)")) return;
        if (temPopover) {
            try { if (pilha.matches(":popover-open")) pilha.hidePopover(); } catch (erro) { /* nada */ }
        }
    }

    function normalizar(opcoes) {
        if (typeof opcoes === "string") opcoes = { texto: opcoes };
        opcoes = opcoes || {};
        var nivel = nivelDe(opcoes.nivel);
        var titulo = String(opcoes.titulo || "").trim();
        var texto = String(opcoes.texto || "").trim();
        if (!titulo) {
            /* Recado curto ("Salvo.") é o próprio título; o longo ganha o do nível. */
            if (texto && texto.length <= 44) {
                titulo = texto.replace(/\.$/, "");
                texto = "";
            } else {
                titulo = TITULO[nivel];
            }
        }
        return {
            nivel: nivel,
            titulo: titulo,
            texto: texto,
            icone: ICONES[opcoes.icone] ? opcoes.icone : nivel,
            acao: opcoes.acao && opcoes.acao.rotulo ? opcoes.acao : null,
            duracao: opcoes.fixo ? 0
                : (typeof opcoes.duracao === "number" ? opcoes.duracao : DURACAO[nivel])
        };
    }

    function botaoDeAcao(acao, aoUsar) {
        var el;
        if (acao.url) {
            el = criar("a", "ls-recado-acao", acao.rotulo);
            el.href = acao.url;
        } else {
            el = criar("button", "ls-recado-acao", acao.rotulo);
            el.type = "button";
        }
        el.addEventListener("click", function (evento) {
            if (typeof acao.aoClicar === "function") acao.aoClicar(evento);
            aoUsar();
        });
        return el;
    }

    function toast(entrada) {
        var o = normalizar(entrada);
        var caixa = garantirPilha();
        garantirFalas();

        var el = criar("div", "ls-recado ls-recado--" + o.nivel);
        el.setAttribute("data-nivel", o.nivel);
        var icone = criar("span", "ls-recado-icone");
        icone.innerHTML = svg(o.icone);
        var corpo = criar("div", "ls-recado-corpo");
        corpo.appendChild(criar("strong", "ls-recado-titulo", o.titulo));
        if (o.texto) corpo.appendChild(criar("span", "ls-recado-texto", o.texto));
        var fechar = criar("button", "ls-recado-fechar");
        fechar.type = "button";
        fechar.setAttribute("aria-label", "Fechar aviso");
        fechar.innerHTML = svg("fechar");
        el.appendChild(icone);
        el.appendChild(corpo);
        el.appendChild(fechar);

        if (o.acao) {
            var acoes = criar("div", "ls-recado-acoes");
            acoes.appendChild(botaoDeAcao(o.acao, function () { sair(); }));
            corpo.appendChild(acoes);
        }

        /* O relógio. Para quando o ponteiro ou o foco estão no aviso, quando
           ele está sendo arrastado e quando a aba está escondida: aviso que
           ninguém viu não pode ter "sumido sozinho". */
        var restante = o.duracao;
        var relogio = null;
        var inicio = 0;
        var motivos = {};
        var barra = null;
        if (o.duracao > 0) {
            var trilho = criar("span", "ls-recado-tempo");
            trilho.setAttribute("aria-hidden", "true");
            barra = criar("span");
            barra.style.animationDuration = o.duracao + "ms";
            trilho.appendChild(barra);
            el.appendChild(trilho);
        }

        function parado() {
            for (var chave in motivos) if (motivos[chave]) return true;
            return false;
        }
        function correr() {
            if (!o.duracao || relogio || parado() || el.classList.contains("is-saindo")) return;
            inicio = Date.now();
            relogio = window.setTimeout(function () { sair(); }, Math.max(restante, 0));
            el.classList.remove("is-pausado");
        }
        function pausar(motivo) {
            motivos[motivo] = true;
            if (!relogio) {
                el.classList.add("is-pausado");
                return;
            }
            window.clearTimeout(relogio);
            relogio = null;
            restante -= Date.now() - inicio;
            el.classList.add("is-pausado");
        }
        function seguir(motivo) {
            motivos[motivo] = false;
            correr();
        }

        var saiu = false;
        function sair(direcao) {
            if (saiu) return;
            saiu = true;
            if (relogio) window.clearTimeout(relogio);
            document.removeEventListener("visibilitychange", aoMudarVisibilidade);
            /* Quem estava com o foco no aviso não pode ficar no nada. */
            var tinhaFoco = el.contains(document.activeElement);
            el.setAttribute("data-saida", direcao || "");
            el.classList.add("is-saindo");
            window.setTimeout(function () {
                el.remove();
                esconderPilhaSeVazia();
            }, semMovimento() ? 0 : 260);
            if (tinhaFoco && document.body) {
                var proximo = caixa.querySelector(".ls-recado:not(.is-saindo) .ls-recado-fechar");
                if (proximo) proximo.focus();
            }
        }

        function aoMudarVisibilidade() {
            if (document.hidden) pausar("aba");
            else seguir("aba");
        }

        fechar.addEventListener("click", function () { sair(); });
        el.addEventListener("pointerenter", function (evento) {
            if (evento.pointerType === "mouse") pausar("ponteiro");
        });
        el.addEventListener("pointerleave", function (evento) {
            if (evento.pointerType === "mouse") seguir("ponteiro");
        });
        el.addEventListener("focusin", function () { pausar("foco"); });
        el.addEventListener("focusout", function (evento) {
            if (!el.contains(evento.relatedTarget)) seguir("foco");
        });
        el.addEventListener("keydown", function (evento) {
            if (evento.key === "Escape") {
                evento.stopPropagation();
                sair();
            }
        });
        document.addEventListener("visibilitychange", aoMudarVisibilidade);
        arrastavel(el, sair, pausar, seguir);

        /* O mais novo em cima; passou do limite, sai o mais antigo -- o de
           erro só quando não houver outro. */
        caixa.insertBefore(el, caixa.firstChild);
        var vivos = caixa.querySelectorAll(".ls-recado:not(.is-saindo)");
        if (vivos.length > NO_MAXIMO) {
            var candidatos = Array.prototype.filter.call(vivos, function (item) {
                return item !== el && item.getAttribute("data-nivel") !== "erro";
            });
            var velho = candidatos.length ? candidatos[candidatos.length - 1] : vivos[vivos.length - 1];
            if (velho && velho.lsSair) velho.lsSair();
        }
        el.lsSair = sair;
        mostrarPilha();
        anunciar(o.nivel, o.titulo + (o.texto ? ". " + o.texto : ""));
        if (document.hidden) pausar("aba");
        correr();

        return { elemento: el, fechar: function () { sair(); } };
    }

    /* Arrastar para dispensar: para o lado em qualquer tela, para cima
       também no celular (de onde ele veio). Um toque sem arrasto não faz
       nada -- o aviso não é botão. */
    function arrastavel(el, sair, pausar, seguir) {
        var inicio = null;

        el.addEventListener("pointerdown", function (evento) {
            if (evento.button !== 0 || evento.target.closest("button, a")) return;
            inicio = { x: evento.clientX, y: evento.clientY, quando: Date.now(), dx: 0, dy: 0, id: evento.pointerId };
            try { el.setPointerCapture(evento.pointerId); } catch (erro) { /* nada */ }
            pausar("arrasto");
        });

        el.addEventListener("pointermove", function (evento) {
            if (!inicio || evento.pointerId !== inicio.id) return;
            inicio.dx = evento.clientX - inicio.x;
            inicio.dy = Math.min(0, evento.clientY - inicio.y);
            if (Math.abs(inicio.dx) < 4 && Math.abs(inicio.dy) < 4) return;
            el.classList.add("is-arrastando");
            if (Math.abs(inicio.dx) >= Math.abs(inicio.dy)) {
                el.style.transform = "translateX(" + inicio.dx + "px)";
                el.style.opacity = String(Math.max(0.2, 1 - Math.abs(inicio.dx) / (el.offsetWidth || 300)));
            } else {
                el.style.transform = "translateY(" + inicio.dy + "px)";
                el.style.opacity = String(Math.max(0.2, 1 + inicio.dy / 120));
            }
        });

        function soltar(evento) {
            if (!inicio || evento.pointerId !== inicio.id) return;
            var dx = inicio.dx;
            var dy = inicio.dy;
            var tempo = Math.max(Date.now() - inicio.quando, 1);
            inicio = null;
            el.classList.remove("is-arrastando");
            var largura = el.offsetWidth || 300;
            var rapido = Math.abs(dx) / tempo > 0.6 && Math.abs(dx) > 36;
            if (Math.abs(dx) >= Math.abs(dy) && (Math.abs(dx) > largura * 0.33 || rapido)) {
                sair(dx > 0 ? "direita" : "esquerda");
                return;
            }
            if (dy < -36) {
                sair("cima");
                return;
            }
            el.style.transform = "";
            el.style.opacity = "";
            seguir("arrasto");
        }
        el.addEventListener("pointerup", soltar);
        el.addEventListener("pointercancel", soltar);
    }

    /* ---------------------------------------------------------------------
       A FOLHA (modal e confirmação)

       Um <dialog> de verdade, aberto com showModal: o navegador põe na
       camada de cima, deixa o resto da página inerte (o foco não sai dela)
       e entrega o Esc. Uma de cada vez: a segunda espera a primeira fechar.
       --------------------------------------------------------------------- */
    var fila = Promise.resolve();
    var contador = 0;

    function folha(o) {
        var resultado = fila.then(function () { return abrirFolha(o); });
        fila = resultado.then(function () {}, function () {});
        return resultado;
    }

    function abrirFolha(o) {
        return new Promise(function (resolver) {
            contador += 1;
            var id = "lsAvisoFolha" + contador;
            var janela = criar("dialog", "ls-recado-folha ls-recado--" + o.nivel + (o.perigo ? " is-perigo" : ""));
            janela.setAttribute("aria-labelledby", id + "Titulo");
            if (o.texto) janela.setAttribute("aria-describedby", id + "Texto");

            var cartao = criar("form", "ls-recado-folha-cartao");
            cartao.method = "dialog";
            var alca = criar("span", "ls-recado-folha-alca");
            alca.setAttribute("aria-hidden", "true");
            var icone = criar("span", "ls-recado-folha-icone");
            icone.innerHTML = svg(o.icone);
            var titulo = criar("h2", "ls-recado-folha-titulo", o.titulo);
            titulo.id = id + "Titulo";
            cartao.appendChild(alca);
            cartao.appendChild(icone);
            cartao.appendChild(titulo);
            if (o.texto) {
                var texto = criar("p", "ls-recado-folha-texto", o.texto);
                texto.id = id + "Texto";
                cartao.appendChild(texto);
            }

            var botoes = criar("div", "ls-recado-folha-botoes");
            var principal = criar("button", "ls-recado-botao ls-recado-botao--primario", o.confirmar);
            principal.type = "submit";
            principal.value = "sim";
            if (o.cancelar) {
                var cancelar = criar("button", "ls-recado-botao", o.cancelar);
                cancelar.type = "submit";
                cancelar.value = "nao";
                botoes.appendChild(cancelar);
            }
            botoes.appendChild(principal);
            cartao.appendChild(botoes);
            janela.appendChild(cartao);

            /* No que apaga, o foco começa no "Cancelar": um Enter distraído
               não exclui nada. No resto, no botão principal. */
            var primeiroFoco = o.perigo && cancelar ? cancelar : principal;
            var anterior = document.activeElement;
            var fechada = false;

            function fecharCom(valor) {
                if (fechada) return;
                fechada = true;
                janela.classList.add("is-saindo");
                window.setTimeout(function () {
                    try { if (janela.open) janela.close(valor); } catch (erro) { /* nada */ }
                    resgatarPilha(janela);
                    janela.remove();
                    document.documentElement.classList.remove("ls-recado-travado");
                    if (anterior && anterior.isConnected && typeof anterior.focus === "function") {
                        try { anterior.focus({ preventScroll: true }); } catch (erro) { /* nada */ }
                    }
                    resolver(valor === "sim");
                }, semMovimento() ? 0 : 170);
            }

            /* O envio deste <form> é só da folha: nem a navegação suave do
               painel nem a barra de carregamento do site precisam saber. */
            cartao.addEventListener("submit", function (evento) {
                evento.preventDefault();
                evento.stopPropagation();
                fecharCom(evento.submitter ? evento.submitter.value : "nao");
            });
            janela.addEventListener("cancel", function (evento) {
                evento.preventDefault();
                fecharCom("nao");
            });
            /* Toque no véu, fora do cartão, é "não". */
            janela.addEventListener("click", function (evento) {
                if (evento.target === janela) fecharCom("nao");
            });
            janela.addEventListener("keydown", function (evento) {
                if (evento.key === "Escape") {
                    evento.preventDefault();
                    evento.stopPropagation();
                    fecharCom("nao");
                }
            });
            puxarParaBaixo(cartao, function () { fecharCom("nao"); });

            document.body.appendChild(janela);
            document.documentElement.classList.add("ls-recado-travado");
            if (typeof janela.showModal === "function") {
                janela.showModal();
            } else {
                /* Navegador sem <dialog> modal: a folha abre do mesmo jeito,
                   com o véu desenhado pelo CSS. */
                janela.setAttribute("open", "");
                janela.classList.add("sem-camada");
            }
            primeiroFoco.focus();
            anunciar(o.nivel, o.titulo + (o.texto ? ". " + o.texto : ""));
        });
    }

    /* No celular a folha desce com o dedo, como as do aparelho. */
    function puxarParaBaixo(cartao, fechar) {
        var inicio = null;
        cartao.addEventListener("pointerdown", function (evento) {
            if (!noCelular() || evento.button !== 0 || evento.target.closest("button, a, input, textarea, select")) return;
            inicio = { y: evento.clientY, id: evento.pointerId, dy: 0 };
            try { cartao.setPointerCapture(evento.pointerId); } catch (erro) { /* nada */ }
        });
        cartao.addEventListener("pointermove", function (evento) {
            if (!inicio || evento.pointerId !== inicio.id) return;
            inicio.dy = Math.max(0, evento.clientY - inicio.y);
            cartao.classList.add("is-arrastando");
            cartao.style.transform = "translateY(" + inicio.dy + "px)";
        });
        function soltar(evento) {
            if (!inicio || evento.pointerId !== inicio.id) return;
            var dy = inicio.dy;
            inicio = null;
            cartao.classList.remove("is-arrastando");
            if (dy > 90) {
                fechar();
                return;
            }
            cartao.style.transform = "";
        }
        cartao.addEventListener("pointerup", soltar);
        cartao.addEventListener("pointercancel", soltar);
    }

    function confirmar(opcoes) {
        if (typeof opcoes === "string") opcoes = { texto: opcoes };
        opcoes = opcoes || {};
        var perigo = Boolean(opcoes.perigo);
        return folha({
            nivel: perigo ? "erro" : nivelDe(opcoes.nivel || "alerta"),
            titulo: String(opcoes.titulo || "Tem certeza?"),
            texto: String(opcoes.texto || ""),
            icone: ICONES[opcoes.icone] ? opcoes.icone : (perigo ? "lixeira" : "alerta"),
            confirmar: String(opcoes.confirmar || "Confirmar"),
            cancelar: String(opcoes.cancelar || "Cancelar"),
            perigo: perigo
        });
    }

    function modal(opcoes) {
        var o = normalizar(opcoes);
        var acao = o.acao;
        return folha({
            nivel: o.nivel,
            titulo: o.titulo,
            texto: o.texto,
            icone: o.icone,
            confirmar: String((opcoes && opcoes.botao) || (acao ? acao.rotulo : "Entendi")),
            cancelar: acao ? "Fechar" : "",
            perigo: false
        }).then(function (sim) {
            if (sim && acao) {
                if (typeof acao.aoClicar === "function") acao.aoClicar();
                if (acao.url) window.location.href = acao.url;
            }
        });
    }

    /* ---------------------------------------------------------------------
       OS RECADOS DO SERVIDOR

       Cada bloco tem uma chave única por resposta. A aba lembra as últimas
       que mostrou: a tela que volta do cache da navegação suave (ou do
       "voltar") traz o mesmo HTML, e o aviso não pode aparecer duas vezes.
       --------------------------------------------------------------------- */
    function vistos() {
        try {
            var lista = JSON.parse(window.sessionStorage.getItem(CHAVE_VISTOS) || "[]");
            return Array.isArray(lista) ? lista : [];
        } catch (erro) {
            return [];
        }
    }

    function lembrar(chave) {
        try {
            var lista = vistos();
            lista.push(chave);
            window.sessionStorage.setItem(CHAVE_VISTOS, JSON.stringify(lista.slice(-30)));
        } catch (erro) { /* armazenamento bloqueado: segue */ }
    }

    function lerDoServidor(raiz) {
        var blocos = (raiz || document).querySelectorAll("[data-ls-recados]");
        Array.prototype.forEach.call(blocos, function (bloco) {
            var chave = bloco.getAttribute("data-ls-recados");
            var repetido = chave && vistos().indexOf(chave) !== -1;
            var cartoes = bloco.querySelectorAll("[data-ls-recado]");
            bloco.remove();
            if (repetido) return;
            if (chave) lembrar(chave);
            Array.prototype.forEach.call(cartoes, function (cartao) {
                var texto = cartao.querySelector(".ls-recado-texto");
                var opcoes = {
                    nivel: cartao.getAttribute("data-nivel"),
                    titulo: cartao.getAttribute("data-titulo"),
                    texto: texto ? texto.textContent : "",
                    icone: cartao.getAttribute("data-icone"),
                    fixo: cartao.hasAttribute("data-fixo"),
                    acao: cartao.hasAttribute("data-acao-url") ? {
                        url: cartao.getAttribute("data-acao-url"),
                        rotulo: cartao.getAttribute("data-acao-rotulo")
                    } : null
                };
                if (cartao.hasAttribute("data-modal")) modal(opcoes);
                else toast(opcoes);
            });
        });
    }

    /* ---------------------------------------------------------------------
       DECLARATIVO: data-ls-confirmar

       Na captura, antes de qualquer outro ouvinte do envio (o fetch do
       painel, a barra de carregamento): o primeiro envio é segurado, a
       pergunta é feita e, no "sim", o mesmo envio é refeito com o mesmo
       botão -- e aí passa direto.
       --------------------------------------------------------------------- */
    function opcoesDe(el) {
        return {
            texto: el.getAttribute("data-ls-confirmar") || "",
            titulo: el.getAttribute("data-ls-confirmar-titulo") || "",
            confirmar: el.getAttribute("data-ls-confirmar-botao") || "",
            cancelar: el.getAttribute("data-ls-confirmar-cancelar") || "",
            icone: el.getAttribute("data-ls-confirmar-icone") || "",
            perigo: el.hasAttribute("data-ls-perigo")
        };
    }

    function reenviar(form, botao) {
        form.lsConfirmado = true;
        try {
            if (typeof form.requestSubmit === "function") {
                try {
                    form.requestSubmit(botao && botao.form === form ? botao : undefined);
                } catch (erro) {
                    form.requestSubmit();
                }
            } else {
                if (botao && botao.name) {
                    var campo = document.createElement("input");
                    campo.type = "hidden";
                    campo.name = botao.name;
                    campo.value = botao.value;
                    form.appendChild(campo);
                }
                form.submit();
            }
        } finally {
            form.lsConfirmado = false;
        }
    }

    document.addEventListener("submit", function (evento) {
        var form = evento.target;
        if (!form || form.tagName !== "FORM" || form.lsConfirmado) return;
        var botao = evento.submitter;
        var fonte = botao && botao.hasAttribute && botao.hasAttribute("data-ls-confirmar")
            ? botao
            : (form.hasAttribute("data-ls-confirmar") ? form : null);
        if (!fonte) return;
        evento.preventDefault();
        evento.stopImmediatePropagation();
        confirmar(opcoesDe(fonte)).then(function (sim) {
            if (sim) reenviar(form, botao);
        });
    }, true);

    document.addEventListener("click", function (evento) {
        var link = evento.target.closest ? evento.target.closest("a[data-ls-confirmar][href]") : null;
        if (!link || evento.button !== 0) return;
        evento.preventDefault();
        evento.stopImmediatePropagation();
        confirmar(opcoesDe(link)).then(function (sim) {
            if (!sim) return;
            if (link.target && link.target !== "_self") window.open(link.href, link.target);
            else window.location.href = link.href;
        });
    }, true);

    window.LSAviso = {
        toast: toast,
        modal: modal,
        confirmar: confirmar,
        lerDoServidor: lerDoServidor,
        icones: Object.keys(ICONES)
    };

    function iniciar() {
        garantirFalas();
        lerDoServidor(document);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
    /* A troca de tela do painel (ls-soft-navigation.js) traz a área de
       conteúdo nova, com os recados dela. */
    document.addEventListener("ls:tela", function () { lerDoServidor(document); });
})(window, document);
