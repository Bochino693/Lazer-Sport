/* =========================================================================
   ls-carrinho-rapido.js — a folha do "Adicionar ao carrinho".
   -------------------------------------------------------------------------
   O pedido: "fora o carrinho deve ser visível, opção de quantidade, então
   abra um modal para add quantidade e moderno aparecendo que há itens".

   TODO "ADICIONAR" DO SITE PASSA POR AQUI. Os botões chamam o
   `adicionarAoCarrinho(tipo, id, irParaCarrinho, opcoes)` do base.html
   (home, loja, combos, promoções, catálogo, cartão da peça, página do
   brinquedo), e ele entrega para `LSCarrinhoRapido.adicionar`, que:

     1. abre a folha na hora, com o esqueleto do produto, e busca a prévia
        (`/carrinho/previa/<tipo>/<id>/`: nome, foto e preço unitário, como
        o carrinho cobraria);
     2. mostra a foto, o nome, o preço, o − [n] + (1 a 99, também dá para
        digitar) e o subtotal, com "Adicionar ao carrinho" (ou "Comprar
        agora") e "Cancelar";
     3. adiciona e vira o "pronto": o visto desenhado, quantos itens o
        carrinho tem e quanto dá, com "Ver carrinho" e "Continuar
        comprando". O selo do carrinho no topo pula. No "Comprar agora", o
        "pronto" diz que está abrindo o carrinho, e abre.

   Quem já sabe a quantidade (`opcoes.quantidade`, ou a página da peça com
   o seu `#quantidade-input`) pula a escolha: adiciona direto e mostra o
   "pronto". Sem conta, a folha pede para entrar (com o `?next=` da página),
   no lugar do toast vermelho de antes.

   O CONTRATO COM QUEM CHAMA NÃO MUDOU. Continua voltando uma Promise que
   resolve com a resposta do servidor ({sucesso, total_itens, ...}) depois
   que a pessoa confirma e o servidor responde, ou com {sucesso: false,
   ...}: `cancelado: true` quando ela desiste, `login: true` quando falta
   entrar, `bloqueado: true` com outra inclusão em andamento. A trava de
   clique duplo (`LSCartLoading`, do base.html) segue valendo durante o
   envio.

   ACESSIBILIDADE: <dialog> modal de verdade (o resto da página fica
   inerte), o Tab dá a volta dentro da folha, Esc e toque fora fecham, e o
   foco volta para o botão que abriu. Alvos de 44 px ou mais.
   ========================================================================= */
(function (window, document) {
    "use strict";

    if (window.LSCarrinhoRapido) return;

    var script = document.currentScript;
    var config = (script && script.dataset) || {};
    var URL_CARRINHO = config.urlCarrinho || "/carrinho/#carrinho";
    var URL_LOGIN = config.urlLogin || "/login/";
    var URL_REGISTRAR = config.urlRegistrar || "/registrar/";
    var MINIMO = 1;
    var MAXIMO = 99;

    /* Traço de 2 px em grade de 24, como os ícones do ls-aviso.js. O
       Font Awesome do site é um recorte e não traz o "menos". */
    var DESENHOS = {
        fechar: '<path d="m6.5 6.5 11 11M17.5 6.5l-11 11"/>',
        menos: '<path d="M5.5 12h13"/>',
        mais: '<path d="M12 5.5v13M5.5 12h13"/>',
        visto: '<circle cx="26" cy="26" r="24"/><path d="m15.5 27 7 7L37 19.5"/>'
    };

    var moeda = (function () {
        try {
            return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
        } catch (erro) {
            return null;
        }
    })();

    function reais(valor) {
        var numero = Number(valor) || 0;
        if (moeda) return moeda.format(numero);
        return "R$ " + numero.toFixed(2).replace(".", ",");
    }

    function semMovimento() {
        return Boolean(window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }

    function noCelular() {
        return Boolean(window.matchMedia && window.matchMedia("(max-width: 640px)").matches);
    }

    function svg(nome, caixa) {
        return '<svg viewBox="' + (caixa || "0 0 24 24") + '" aria-hidden="true" focusable="false">'
            + DESENHOS[nome] + "</svg>";
    }

    /* Monta um elemento. `html` só recebe os desenhos daqui; o que vem do
       servidor (nome do produto) entra sempre como texto. */
    function el(tag, props, filhos) {
        var no = document.createElement(tag);
        Object.keys(props || {}).forEach(function (chave) {
            var valor = props[chave];
            if (valor === null || valor === undefined || valor === false) return;
            if (chave === "class") no.className = valor;
            else if (chave === "text") no.textContent = valor;
            else if (chave === "html") no.innerHTML = valor;
            else if (chave.slice(0, 2) === "on") no.addEventListener(chave.slice(2), valor);
            else no.setAttribute(chave, valor === true ? "" : valor);
        });
        (filhos || []).forEach(function (filho) {
            if (filho === null || filho === undefined || filho === false) return;
            no.appendChild(typeof filho === "string" ? document.createTextNode(filho) : filho);
        });
        return no;
    }

    function icone(classes) {
        return el("i", { class: "fa-solid " + classes, "aria-hidden": "true" });
    }

    function plural(n, um, varios) {
        return n + " " + (n === 1 ? um : varios);
    }

    function csrf() {
        var achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (achado) return decodeURIComponent(achado[1]);
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") || "" : "";
    }

    /* fetch que sempre devolve {ok, status, corpo}: erro do servidor em
       HTML (404, 500) vira corpo vazio, e quem chama decide o texto. */
    function pedir(url, opcoes) {
        return window.fetch(url, opcoes).then(function (resposta) {
            return resposta.json().catch(function () { return {}; }).then(function (corpo) {
                return { ok: resposta.ok, status: resposta.status, corpo: corpo || {} };
            });
        });
    }

    function previa(tipo, id) {
        return pedir("/carrinho/previa/" + encodeURIComponent(tipo) + "/" + encodeURIComponent(id) + "/", {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" }
        });
    }

    function mostrarErro(mensagem) {
        if (typeof window.mostrarToast === "function") {
            window.mostrarToast(mensagem, true);
        } else if (window.LSAviso) {
            window.LSAviso.toast({ nivel: "erro", texto: mensagem });
        }
    }

    /* ---------------------------------------------------------------------
       A FOLHA

       Um <dialog> só, criado no primeiro uso e reaproveitado. Cada estado
       (carregando, escolher, enviando, pronto, entrar) troca o miolo
       inteiro, que entra deslizando.
       --------------------------------------------------------------------- */
    var janela = null;
    var cartao = null;
    var corpo = null;
    var aberta = false;
    var trancada = false;      /* enviando: nem Esc nem toque fora fecham */
    var estado = "";
    var aoFechar = null;       /* quem resolve a Promise quando a pessoa desiste */
    var gatilhoFoco = null;    /* quem recebe o foco de volta */
    var contador = 0;
    /* A vez de cada abertura: a prévia que chega atrasada (a pessoa fechou
       e já abriu outro produto) não pinta por cima da folha nova. */
    var vez = 0;

    function montar() {
        if (janela && janela.isConnected) return;
        janela = el("dialog", { class: "ls-cr", role: "dialog", "aria-modal": "true" });
        cartao = el("div", { class: "ls-cr-cartao" });
        corpo = el("div", { class: "ls-cr-corpo" });
        cartao.appendChild(el("span", { class: "ls-cr-alca", "aria-hidden": "true" }));
        cartao.appendChild(el("button", {
            type: "button",
            class: "ls-cr-fechar",
            "aria-label": "Fechar",
            html: svg("fechar"),
            onclick: function () { pedirFechar(); }
        }));
        cartao.appendChild(corpo);
        janela.appendChild(cartao);

        janela.addEventListener("cancel", function (evento) {
            evento.preventDefault();
            pedirFechar();
        });
        /* Toque no véu (fora do cartão) fecha -- só se começou no véu: um
           arrasto que nasce no cartão e termina fora não conta. */
        var comecouNoVeu = false;
        janela.addEventListener("pointerdown", function (evento) {
            comecouNoVeu = evento.target === janela;
        });
        janela.addEventListener("click", function (evento) {
            if (evento.target === janela && comecouNoVeu) pedirFechar();
        });
        janela.addEventListener("keydown", prenderFoco);
        puxarParaBaixo(cartao);
        document.body.appendChild(janela);
    }

    function abrirJanela() {
        montar();
        if (aberta) return;
        aberta = true;
        vez += 1;
        liberarFechar();
        janela.classList.remove("is-saindo");
        cartao.style.transform = "";
        document.documentElement.classList.add("ls-cr-travado");
        if (typeof janela.showModal === "function") {
            try {
                janela.showModal();
                return;
            } catch (erro) { /* cai no modo sem camada */ }
        }
        janela.setAttribute("open", "");
        janela.classList.add("sem-camada");
    }

    function fecharJanela() {
        if (!aberta) return Promise.resolve();
        aberta = false;
        trancada = false;
        janela.classList.add("is-saindo");
        return new Promise(function (resolver) {
            window.setTimeout(function () {
                try { if (janela.open) janela.close(); } catch (erro) { /* nada */ }
                janela.removeAttribute("open");
                janela.classList.remove("is-saindo", "sem-camada");
                cartao.style.transform = "";
                document.documentElement.classList.remove("ls-cr-travado");
                estado = "";
                resolver();
            }, semMovimento() ? 0 : 210);
        });
    }

    /* A pessoa pediu para fechar (X, Cancelar, Esc, véu, arrasto). */
    function pedirFechar() {
        if (!aberta || trancada) return;
        var deOnde = estado;
        var fim = aoFechar;
        aoFechar = null;
        fecharJanela().then(function () {
            devolverFoco();
            /* Saindo do "pronto", o selo do topo pula de novo: é ali que o
               item "caiu", e agora dá para ver. */
            if (deOnde === "pronto") pularSelosDoTopo();
            if (fim) fim();
        });
    }

    /* O foco volta para quem abriu. O botão do card costuma estar
       desligado nesse instante (ele mostra "Adicionado" por um segundo):
       tenta de novo até ele voltar, se ninguém levou o foco antes. */
    function devolverFoco() {
        var alvo = gatilhoFoco;
        gatilhoFoco = null;
        if (!alvo || typeof alvo.focus !== "function") return;
        var tentativas = 0;
        (function tentar() {
            if (!alvo.isConnected) return;
            try { alvo.focus({ preventScroll: true }); } catch (erro) { /* nada */ }
            if (document.activeElement === alvo) return;
            var atual = document.activeElement;
            if (atual && atual !== document.body && atual !== document.documentElement) return;
            tentativas += 1;
            if (tentativas > 25) return;
            window.setTimeout(tentar, 100);
        })();
    }

    function focaveis() {
        return Array.prototype.filter.call(
            cartao.querySelectorAll('button, a[href], input, [tabindex]:not([tabindex="-1"])'),
            function (no) { return !no.disabled && no.getClientRects().length > 0; }
        );
    }

    /* O Tab dá a volta dentro da folha. */
    function prenderFoco(evento) {
        if (evento.key !== "Tab") return;
        var lista = focaveis();
        if (!lista.length) return;
        var primeiro = lista[0];
        var ultimo = lista[lista.length - 1];
        var atual = document.activeElement;
        if (evento.shiftKey && (atual === primeiro || !cartao.contains(atual))) {
            evento.preventDefault();
            ultimo.focus();
        } else if (!evento.shiftKey && (atual === ultimo || !cartao.contains(atual))) {
            evento.preventDefault();
            primeiro.focus();
        }
    }

    /* No celular a folha desce com o dedo, como as do aparelho. */
    function puxarParaBaixo(alvo) {
        var inicio = null;
        alvo.addEventListener("pointerdown", function (evento) {
            /* folha mais alta que a tela (celular deitado): o dedo rola */
            if (!noCelular() || trancada || evento.button !== 0 || alvo.classList.contains("ls-cr-rola")
                || evento.target.closest("button, a, input")) return;
            inicio = { y: evento.clientY, id: evento.pointerId, dy: 0 };
        });
        alvo.addEventListener("pointermove", function (evento) {
            if (!inicio || evento.pointerId !== inicio.id) return;
            inicio.dy = Math.max(0, evento.clientY - inicio.y);
            if (inicio.dy < 4) return;
            alvo.classList.add("is-arrastando");
            alvo.style.transform = "translateY(" + inicio.dy + "px)";
        });
        function soltar(evento) {
            if (!inicio || evento.pointerId !== inicio.id) return;
            var dy = inicio.dy;
            inicio = null;
            alvo.classList.remove("is-arrastando");
            if (dy > 90) {
                pedirFechar();
                if (aberta) alvo.style.transform = "";
                return;
            }
            alvo.style.transform = "";
        }
        alvo.addEventListener("pointerup", soltar);
        alvo.addEventListener("pointercancel", soltar);
    }

    /* Troca o miolo da folha. `titulo` é o id do que dá nome à folha; `foco`,
       quem recebe o foco. */
    function trocar(novoEstado, filhos, titulo, foco) {
        montar();
        estado = novoEstado;
        var novo = el("div", { class: "ls-cr-corpo ls-cr-corpo--" + novoEstado }, filhos);
        cartao.replaceChild(novo, corpo);
        corpo = novo;
        cartao.classList.toggle("ls-cr-rola", cartao.scrollHeight > cartao.clientHeight + 1);
        if (titulo) janela.setAttribute("aria-labelledby", titulo);
        if (foco && aberta) {
            try { foco.focus({ preventScroll: true }); } catch (erro) { /* nada */ }
        }
    }

    function novoId(prefixo) {
        contador += 1;
        return "ls-cr-" + prefixo + "-" + contador;
    }

    function fotoDo(item, classeExtra) {
        if (item && item.foto) {
            return el("span", { class: "ls-cr-foto" + (classeExtra ? " " + classeExtra : "") }, [
                el("img", { src: item.foto, alt: "", decoding: "async", width: "96", height: "96" })
            ]);
        }
        return el("span", { class: "ls-cr-foto ls-cr-foto--vazia" + (classeExtra ? " " + classeExtra : "") }, [
            icone("fa-cart-shopping")
        ]);
    }

    function blocoProduto(item, idTitulo) {
        var tipo = item.tipo || "";
        return el("div", { class: "ls-cr-produto" }, [
            fotoDo(item),
            el("div", { class: "ls-cr-produto-texto" }, [
                el("span", { class: "ls-cr-rotulo ls-cr-rotulo--" + tipo, text: item.rotulo || "Produto" }),
                el("h2", { class: "ls-cr-nome", id: idTitulo, text: item.nome || "" }),
                el("span", { class: "ls-cr-unitario" }, [
                    el("b", { text: item.preco_unitario_formatado || reais(item.preco_unitario) }),
                    " cada"
                ])
            ])
        ]);
    }

    function textoDoBotao(comprar) {
        return comprar ? "Comprar agora" : "Adicionar ao carrinho";
    }

    function botaoPrincipal(comprar, props) {
        var extra = comprar ? " ls-cr-botao--comprar" : "";
        return el("button", Object.assign({
            type: "button",
            class: "ls-cr-botao ls-cr-botao--primario" + extra
        }, props || {}), [
            icone(comprar ? "fa-bolt" : "fa-cart-plus"),
            el("span", { text: textoDoBotao(comprar) })
        ]);
    }

    /* ---------- carregando: o esqueleto, enquanto a prévia chega ---------- */
    function vistaCarregando(comprar) {
        var idTitulo = novoId("titulo");
        function osso(largura, altura) {
            return el("span", { class: "ls-cr-osso", style: "width:" + largura + ";height:" + altura + "px" });
        }
        var principal = botaoPrincipal(comprar, { disabled: true, "aria-busy": "true" });
        trocar("carregando", [
            el("h2", { class: "ls-cr-so-leitor", id: idTitulo, text: "Carregando o produto" }),
            el("div", { class: "ls-cr-produto", "aria-hidden": "true" }, [
                el("span", { class: "ls-cr-foto ls-cr-osso" }),
                el("div", { class: "ls-cr-produto-texto" }, [osso("74px", 18), osso("92%", 20), osso("54%", 16)])
            ]),
            el("div", { class: "ls-cr-qtd", "aria-hidden": "true" }, [osso("96px", 18), osso("164px", 56)]),
            el("div", { class: "ls-cr-botoes" }, [
                principal,
                el("button", { type: "button", class: "ls-cr-botao", text: "Cancelar", onclick: pedirFechar })
            ])
        ], idTitulo, null);
    }

    /* ---------- escolher: a foto, o − [n] +, o subtotal ---------- */
    function vistaEscolher(item, comprar, aoConfirmar) {
        var idTitulo = novoId("titulo");
        var idAcao = novoId("acao");
        var idCampo = novoId("qtd");
        var preco = Number(item.preco_unitario) || 0;
        var quantidade = MINIMO;

        var campo = el("input", {
            class: "ls-cr-numero",
            id: idCampo,
            type: "number",
            inputmode: "numeric",
            min: String(MINIMO),
            max: String(MAXIMO),
            step: "1",
            value: String(MINIMO),
            autocomplete: "off",
            "data-lscr-quantidade": true
        });
        var menos = el("button", {
            type: "button", class: "ls-cr-passo", "aria-label": "Diminuir quantidade",
            "aria-controls": idCampo, html: svg("menos"), "data-lscr-menos": true
        });
        var mais = el("button", {
            type: "button", class: "ls-cr-passo", "aria-label": "Aumentar quantidade",
            "aria-controls": idCampo, html: svg("mais"), "data-lscr-mais": true
        });
        var subtotal = el("strong", { "aria-live": "polite", "aria-atomic": "true", text: reais(preco) });
        var principal = botaoPrincipal(comprar, { "data-lscr-confirmar": true });
        var cancelar = el("button", {
            type: "button", class: "ls-cr-botao", text: "Cancelar",
            "data-lscr-cancelar": true, onclick: pedirFechar
        });

        function mostrar(n) {
            menos.disabled = n <= MINIMO;
            mais.disabled = n >= MAXIMO;
            subtotal.textContent = reais(preco * n);
        }

        function definir(valor, animar) {
            var n = Math.floor(Number(valor));
            if (!Number.isFinite(n) || n < MINIMO) n = MINIMO;
            if (n > MAXIMO) n = MAXIMO;
            var mudou = n !== quantidade;
            quantidade = n;
            if (campo.value !== String(n)) campo.value = String(n);
            mostrar(n);
            if (mudou && animar && !semMovimento()) {
                campo.classList.remove("is-pulando");
                void campo.offsetWidth;
                campo.classList.add("is-pulando");
            }
        }

        menos.addEventListener("click", function () { definir(quantidade - 1, true); });
        mais.addEventListener("click", function () { definir(quantidade + 1, true); });
        /* Digitando: o subtotal acompanha; o número só é corrigido (1 a 99)
           ao sair do campo, para não brigar com quem apaga para reescrever. */
        campo.addEventListener("input", function () {
            var texto = String(campo.value || "").replace(/\D/g, "");
            if (!texto) return;
            var n = Number(texto);
            if (n > MAXIMO) {
                campo.value = String(MAXIMO);
                n = MAXIMO;
            }
            if (n >= MINIMO) {
                quantidade = n;
                mostrar(n);
            }
        });
        campo.addEventListener("change", function () { definir(campo.value); });
        campo.addEventListener("blur", function () { definir(campo.value); });
        campo.addEventListener("focus", function () {
            try { campo.select(); } catch (erro) { /* nada */ }
        });
        campo.addEventListener("keydown", function (evento) {
            if (evento.key === "Enter") {
                evento.preventDefault();
                definir(campo.value);
                principal.click();
            }
        });

        principal.addEventListener("click", function () {
            if (principal.disabled) return;
            definir(campo.value || quantidade);
            aoConfirmar(quantidade);
        });

        mostrar(quantidade);
        trocar("escolher", [
            el("span", { class: "ls-cr-so-leitor", id: idAcao, text: textoDoBotao(comprar) + ":" }),
            blocoProduto(item, idTitulo),
            el("div", { class: "ls-cr-qtd" }, [
                el("label", { for: idCampo }, [
                    "Quantidade",
                    el("small", { text: "de 1 a " + MAXIMO })
                ]),
                el("div", { class: "ls-cr-stepper" }, [menos, campo, mais])
            ]),
            el("div", { class: "ls-cr-subtotal" }, [el("span", { text: "Subtotal" }), subtotal]),
            el("div", { class: "ls-cr-botoes" }, [principal, cancelar])
        ], idAcao + " " + idTitulo, principal);
    }

    /* ---------- enviando: os controles param, o botão gira ---------- */
    function vistaEnviando(comprar) {
        trancada = true;
        if (!corpo) return;
        Array.prototype.forEach.call(corpo.querySelectorAll("button, input"), function (no) {
            no.disabled = true;
        });
        var principal = corpo.querySelector("[data-lscr-confirmar]");
        if (principal) {
            principal.setAttribute("aria-busy", "true");
            principal.replaceChildren(
                icone("fa-spinner fa-spin"),
                el("span", { text: comprar ? "Preparando sua compra…" : "Adicionando…" })
            );
        }
        var fechar = cartao.querySelector(".ls-cr-fechar");
        if (fechar) fechar.disabled = true;
    }

    function liberarFechar() {
        var fechar = cartao && cartao.querySelector(".ls-cr-fechar");
        if (fechar) fechar.disabled = false;
    }

    /* ---------- pronto: o visto, quantos itens e quanto dá ---------- */
    function vistaPronto(dados, item, quantidade, comprar) {
        liberarFechar();
        var idTitulo = novoId("titulo");
        var total = Number(dados.total_itens) || 0;
        var totalTexto = dados.total_carrinho_formatado || reais(dados.total_carrinho);
        item = item || {};
        var preco = Number(item.preco_unitario) || 0;

        var detalhe = plural(quantidade, "unidade", "unidades");
        if (preco) detalhe += " · " + reais(preco * quantidade);
        if (item.adesivo) detalhe += " · adesivo " + item.adesivo;

        var filhos = [
            el("div", { class: "ls-cr-visto", html: svg("visto", "0 0 52 52") }),
            el("h2", {
                class: "ls-cr-titulo", id: idTitulo,
                text: comprar ? "Tudo certo!" : "Adicionado ao carrinho!"
            }),
            item.nome ? el("div", { class: "ls-cr-entrou" }, [
                fotoDo(item),
                el("div", { class: "ls-cr-entrou-texto" }, [
                    el("strong", { text: item.nome }),
                    el("span", { text: detalhe })
                ])
            ]) : null,
            el("div", { class: "ls-cr-resumo", role: "status" }, [
                el("span", { class: "ls-cr-resumo-icone", "aria-hidden": "true" }, [
                    icone("fa-cart-shopping"),
                    el("b", { text: String(total) })
                ]),
                el("span", { class: "ls-cr-resumo-texto" }, [
                    el("strong", { text: plural(total, "item no carrinho", "itens no carrinho") }),
                    el("span", { text: "Total em produtos" })
                ]),
                el("strong", { class: "ls-cr-resumo-total", text: totalTexto })
            ])
        ];

        var foco;
        if (comprar) {
            filhos.push(el("p", { class: "ls-cr-indo" }, [
                icone("fa-spinner fa-spin"),
                "Abrindo o carrinho…"
            ]));
            foco = cartao.querySelector(".ls-cr-fechar");
        } else {
            foco = el("a", { class: "ls-cr-botao ls-cr-botao--primario", href: URL_CARRINHO, "data-lscr-ver-carrinho": true }, [
                el("span", { text: "Ver carrinho" }),
                icone("fa-arrow-right")
            ]);
            filhos.push(el("div", { class: "ls-cr-botoes" }, [
                foco,
                el("button", {
                    type: "button", class: "ls-cr-botao", text: "Continuar comprando",
                    "data-lscr-continuar": true, onclick: pedirFechar
                })
            ]));
        }
        trocar("pronto", filhos, idTitulo, foco);
    }

    /* ---------- entrar: sem conta, a folha leva ao login ---------- */
    function vistaEntrar(item) {
        liberarFechar();
        var idTitulo = novoId("titulo");
        var aqui = window.location.pathname + window.location.search;
        var proximo = "?next=" + encodeURIComponent(aqui);
        var nome = item && item.nome;

        var entrar = el("a", {
            class: "ls-cr-botao ls-cr-botao--primario",
            href: URL_LOGIN + proximo,
            "data-lscr-entrar": true
        }, [icone("fa-right-to-bracket"), el("span", { text: "Entrar" })]);

        trocar("entrar", [
            el("div", { class: "ls-cr-cadeado", "aria-hidden": "true" }, [
                item && item.foto ? fotoDo(item) : icone("fa-user"),
                el("span", { class: "ls-cr-cadeado-selo" }, [icone("fa-lock")])
            ]),
            el("h2", { class: "ls-cr-titulo", id: idTitulo, text: "Entre para comprar" }),
            el("p", { class: "ls-cr-texto" }, nome
                ? ["Faça login para adicionar ", el("b", { text: nome }), " ao carrinho. Você volta direto para esta página."]
                : ["Faça login para usar o carrinho. Você volta direto para esta página."]),
            el("ul", { class: "ls-cr-vantagens" }, [
                el("li", {}, [icone("fa-cart-shopping"), "O carrinho fica salvo na sua conta"]),
                el("li", {}, [icone("fa-box-open"), "Acompanhe o pedido até a entrega"])
            ]),
            el("div", { class: "ls-cr-botoes" }, [
                entrar,
                el("a", { class: "ls-cr-botao", href: URL_REGISTRAR + proximo }, [
                    icone("fa-user-plus"), el("span", { text: "Criar conta" })
                ])
            ]),
            el("button", { type: "button", class: "ls-cr-link", text: "Agora não", onclick: pedirFechar })
        ], idTitulo, entrar);
    }

    /* ---------------------------------------------------------------------
       O FLUXO
       --------------------------------------------------------------------- */
    var ocupado = false;

    function quantidadeDada(tipo, opcoes) {
        var bruto = opcoes.quantidade;
        /* a página da peça tem o seu próprio campo de quantidade */
        if ((bruto === undefined || bruto === null || bruto === "") && tipo === "peca") {
            var campo = document.getElementById("quantidade-input");
            if (campo) bruto = campo.value;
        }
        if (bruto === undefined || bruto === null || bruto === "") return 0;
        var n = Number.parseInt(bruto, 10);
        if (!Number.isFinite(n) || n < MINIMO) return MINIMO;
        return Math.min(n, MAXIMO);
    }

    /* Sem conta: a folha de "entre na conta", com a foto e o nome do
       produto quando dá para saber (a prévia é pública). */
    function mostrarEntrar(tipo, id, item) {
        if (!aberta) abrirJanela();
        if (item) {
            vistaEntrar(item);
            return;
        }
        vistaCarregando(false);
        var minhaVez = vez;
        previa(tipo, id).then(function (r) {
            if (aberta && minhaVez === vez) vistaEntrar(r.ok && r.corpo.item ? r.corpo.item : null);
        }, function () {
            if (aberta && minhaVez === vez) vistaEntrar(null);
        });
    }

    function falhar(token, mensagem) {
        trancada = false;
        aoFechar = null;
        var fechando = aberta ? fecharJanela() : Promise.resolve();
        fechando.then(devolverFoco);
        var carregando = window.LSCartLoading;
        if (carregando && token !== null && token !== undefined) {
            carregando.erro(token, mensagem);   /* devolve os botões e mostra o toast */
        } else {
            mostrarErro(mensagem);
        }
        return { sucesso: false, erro: mensagem };
    }

    /* Põe no carrinho. Com a folha aberta (escolher), ela mostra o envio; sem
       ela (quantidade já dada), quem mostra é a barra do topo, e a folha abre
       direto no "pronto". */
    function enviar(tipo, id, quantidade, comprar, opcoes, gatilho, item) {
        var carregando = window.LSCartLoading;
        var token = null;
        if (carregando) {
            token = carregando.iniciar(gatilho, comprar);
            if (token === null) {
                if (aberta) fecharJanela().then(devolverFoco);
                return Promise.resolve({ sucesso: false, bloqueado: true });
            }
        }
        if (aberta) vistaEnviando(comprar);

        var dados = new URLSearchParams({ quantidade: String(quantidade) });
        if (opcoes.adesivo) dados.set("adesivo", String(opcoes.adesivo));

        return pedir("/carrinho/adicionar/" + encodeURIComponent(tipo) + "/" + encodeURIComponent(id) + "/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": csrf(),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            },
            body: dados.toString()
        }).then(function (r) {
            var resposta = r.corpo;
            if (r.ok && resposta.sucesso) {
                carrinhoNaBarra(resposta.total_itens);
                if (typeof window.atualizarBadgeCarrinho === "function") {
                    window.atualizarBadgeCarrinho(resposta.total_itens);
                }
                if (carregando) carregando.sucesso(token, comprar);
                trancada = false;
                if (!aberta) abrirJanela();
                vistaPronto(resposta, resposta.item || item, Number(resposta.quantidade) || quantidade, comprar);
                if (comprar) {
                    window.setTimeout(function () { window.location.href = URL_CARRINHO; }, 900);
                }
                return resposta;
            }

            var mensagem = resposta.erro || (r.status === 404
                ? "Este item não está à venda no momento."
                : "Não foi possível adicionar este item.");
            if (r.status === 403 && /login/i.test(mensagem)) {
                if (carregando) carregando.erro(token, "");   /* sem toast: a folha explica */
                trancada = false;
                mostrarEntrar(tipo, id, item);
                return { sucesso: false, erro: mensagem, login: true };
            }
            return falhar(token, mensagem);
        }, function () {
            return falhar(token, "Erro de conexão. Tente novamente.");
        });
    }

    /* Escolher a quantidade na folha e então enviar. */
    function escolherEEnviar(tipo, id, comprar, opcoes, gatilho) {
        return new Promise(function (resolver) {
            abrirJanela();
            vistaCarregando(comprar);
            var minhaVez = vez;
            aoFechar = function () { resolver({ sucesso: false, cancelado: true }); };

            previa(tipo, id).then(function (r) {
                /* desistiu enquanto carregava: a Promise já foi resolvida */
                if (!aberta || minhaVez !== vez) return;
                var resposta = r.corpo;
                if (!r.ok || !resposta.sucesso || !resposta.item) {
                    resolver(falhar(null, resposta.erro || (r.status === 404
                        ? "Este item não está à venda no momento."
                        : "Não foi possível abrir este item agora.")));
                    return;
                }
                if (!resposta.logado) {
                    aoFechar = null;
                    vistaEntrar(resposta.item);
                    resolver({ sucesso: false, erro: "Você precisa fazer login", login: true });
                    return;
                }
                vistaEscolher(resposta.item, comprar, function (quantidade) {
                    aoFechar = null;
                    enviar(tipo, id, quantidade, comprar, opcoes, gatilho, resposta.item).then(resolver);
                });
            }, function () {
                if (!aberta || minhaVez !== vez) return;
                resolver(falhar(null, "Erro de conexão. Tente novamente."));
            });
        });
    }

    function adicionar(tipo, id, irParaCarrinho, opcoes) {
        opcoes = opcoes || {};
        var carregando = window.LSCartLoading;
        if (ocupado || aberta || (carregando && carregando.ativo)) {
            return Promise.resolve({ sucesso: false, bloqueado: true });
        }
        var comprar = Boolean(irParaCarrinho);
        var gatilho = carregando ? carregando.consumirGatilho() : null;
        var ativo = document.activeElement;
        gatilhoFoco = gatilho || (ativo && ativo !== document.body ? ativo : null);
        ocupado = true;

        var quantidade = quantidadeDada(tipo, opcoes);
        var fluxo = quantidade
            ? enviar(tipo, id, quantidade, comprar, opcoes, gatilho, null)
            : escolherEEnviar(tipo, id, comprar, opcoes, gatilho);

        return fluxo.then(function (resultado) {
            ocupado = false;
            return resultado;
        }, function (erro) {
            ocupado = false;
            return { sucesso: false, erro: String((erro && erro.message) || erro) };
        });
    }

    /* ---------------------------------------------------------------------
       O SELO QUE PULA

       Todo selo do carrinho (`[data-carrinho-total]`: o do topo, o da barra
       de baixo, o do Menu, o do menu da conta) pula quando o número sobe --
       quem muda o número é o `atualizarBadgeCarrinho` do base.html (ou o
       da página), e aqui só se observa.
       --------------------------------------------------------------------- */
    function pular(no) {
        if (!no || semMovimento()) return;
        no.classList.remove("ls-cr-pulo");
        void no.offsetWidth;
        no.classList.add("ls-cr-pulo");
        var botao = no.closest(".ls-topo-carrinho");
        if (botao) {
            botao.classList.remove("ls-cr-pulo");
            void botao.offsetWidth;
            botao.classList.add("ls-cr-pulo");
        }
    }

    function pularSelosDoTopo() {
        Array.prototype.forEach.call(
            document.querySelectorAll(".ls-topo-carrinho [data-carrinho-total]"),
            pular
        );
    }

    function vigiar(selo) {
        if (!("MutationObserver" in window) || selo.hasAttribute("data-lscr-vigiado")) return;
        selo.setAttribute("data-lscr-vigiado", "");
        var anterior = Number(selo.textContent.trim()) || 0;
        new MutationObserver(function () {
            var agora = Number(selo.textContent.trim()) || 0;
            if (agora === anterior) return;
            var subiu = agora > anterior;
            anterior = agora;
            if (subiu) pular(selo);
        }).observe(selo, { childList: true, characterData: true, subtree: true });
    }

    function vigiarSelos() {
        document.addEventListener("animationend", function (evento) {
            var alvo = evento.target;
            if (!alvo || !alvo.classList) return;
            var dono = alvo.classList.contains("ls-cr-pulo") ? alvo : alvo.closest && alvo.closest(".ls-cr-pulo");
            if (dono) dono.classList.remove("ls-cr-pulo");
        });
        Array.prototype.forEach.call(document.querySelectorAll("[data-carrinho-total]"), vigiar);
    }

    /* A BARRA DE BAIXO DO CELULAR, AO VIVO. A quarta casa dela é o carrinho
       quando há algo nele, e a lista de desejos quando não há (base.html) --
       mas isso só valia no carregamento da página. Com o primeiro item, a
       casa vira o carrinho na hora: no celular o topo sai de vista ao
       rolar, e a barra de baixo não. */
    function carrinhoNaBarra(total) {
        if (!(Number(total) > 0)) return;
        var barra = document.querySelector(".ls-barra-app");
        if (!barra || barra.querySelector(".ls-barra-app-carrinho")) return;
        var desejos = barra.querySelector('a[href*="lista-desejos"]');
        if (!desejos) return;
        var selo = el("b", { class: "ls-barra-app-selo", "data-carrinho-total": true, text: String(Number(total)) });
        desejos.replaceWith(el("a", { href: URL_CARRINHO, class: "ls-barra-app-carrinho" }, [
            icone("fa-cart-shopping"),
            el("span", { text: "Carrinho" }),
            selo
        ]));
        vigiar(selo);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", vigiarSelos);
    } else {
        vigiarSelos();
    }

    window.LSCarrinhoRapido = {
        adicionar: adicionar,
        fechar: pedirFechar,
        get aberta() { return aberta; }
    };
})(window, document);
