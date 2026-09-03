/* Comportamento de home.
 *
 * NASCEU DE DENTRO DO HTML. Eram 32 KB de <script> no template --
 * peso repetido a cada abertura da página, que o navegador não tinha
 * como guardar: script dentro do HTML não tem endereço para cachear.
 *
 * O <script src> ficou na MESMA posição do bloco antigo, e sem `defer`
 * de propósito: script clássico externo executa na ordem do documento,
 * igual ao inline. Com `defer` ele passaria para depois da análise da
 * página, e qualquer trecho que dependesse dele antes disso quebraria
 * sem aviso.
 */

const popupOverlay = document.getElementById('popup-overlay');

function fecharPopup() {
    if (!popupOverlay) return;
    popupOverlay.style.display = 'none';
    sessionStorage.setItem('popupCelebrashow2026', '1');
}

if (popupOverlay) {
    popupOverlay.addEventListener('click', function(e) {
        if (e.target === this) fecharPopup();
    });

    if (!sessionStorage.getItem('popupCelebrashow2026')) {
        setTimeout(function() {
            popupOverlay.style.display = 'flex';
        }, 1500);
    }
}

function abrirWhatsApp(event, nome) {
    event.preventDefault();
    event.stopPropagation();

    const mensagem =
        `Olá! 👋\n` +
        `Gostaria de um orçamento para o brinquedo abaixo:\n\n` +
        `🧸 Nome: ${nome}\n\n` +
        `Fico no aguardo 😊`;

    const url = `https://wa.me/5511960563135?text=${encodeURIComponent(mensagem)}`;
    window.open(url, '_blank');
}

function adicionarProdutoCardAoCarrinho(event, tipo, produtoId, botao) {
    event.preventDefault();
    event.stopPropagation();

    if (!botao || botao.dataset.loading === 'true') return;

    if (typeof window.adicionarAoCarrinho !== 'function') {
        if (typeof window.mostrarToast === 'function') {
            window.mostrarToast('Não foi possível abrir o carrinho agora.', true);
        }
        return;
    }

    const conteudoOriginal = botao.innerHTML;
    botao.dataset.loading = 'true';
    botao.disabled = true;
    botao.classList.add('is-loading');
    botao.innerHTML =
        '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>' +
        '<span>Adicionando...</span>';

    Promise.resolve(window.adicionarAoCarrinho(tipo, produtoId))
        .then((resultado) => {
            if (!resultado || !resultado.sucesso) return;

            botao.classList.remove('is-loading');
            botao.classList.add('is-added');
            botao.innerHTML =
                '<i class="fa-solid fa-check" aria-hidden="true"></i>' +
                '<span>Adicionado</span>';
        })
        .finally(() => {
            window.setTimeout(() => {
                botao.disabled = false;
                botao.dataset.loading = 'false';
                botao.classList.remove('is-loading', 'is-added');
                botao.innerHTML = conteudoOriginal;
            }, 1200);
        });
}

function adicionarBrinquedoAoCarrinho(event, brinquedoId, botao) {
    return adicionarProdutoCardAoCarrinho(
        event,
        'brinquedo',
        brinquedoId,
        botao
    );
}

function adicionarPecaAoCarrinho(event, pecaId, botao) {
    return adicionarProdutoCardAoCarrinho(
        event,
        'peca',
        pecaId,
        botao
    );
}

/* ======================================================
   💰 MOEDA
====================================================== */
function normalizarNumeroMoeda(valor) {
    if (valor === null || valor === undefined || valor === '') return 0;

    let texto = String(valor)
        .trim()
        .replace(/\s|\u00a0/g, '')
        .replace(/R\$/gi, '')
        .replace(/[^\d,.-]/g, '');

    const ultimaVirgula = texto.lastIndexOf(',');
    const ultimoPonto = texto.lastIndexOf('.');

    if (ultimaVirgula > -1 && ultimoPonto > -1) {
        texto = ultimaVirgula > ultimoPonto
            ? texto.replace(/\./g, '').replace(',', '.')
            : texto.replace(/,/g, '');
    } else if (ultimaVirgula > -1) {
        texto = texto.replace(/\./g, '').replace(',', '.');
    } else if ((texto.match(/\./g) || []).length > 1) {
        const partes = texto.split('.');
        const decimal = partes.pop();
        texto = partes.join('') + '.' + decimal;
    }

    const numero = Number(texto);
    return Number.isFinite(numero) ? numero : 0;
}

function formatarMoedaBR(valor) {
    return normalizarNumeroMoeda(valor).toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function renderizarMoedas(root = document) {
    root.querySelectorAll('.money').forEach(el => {
        if (el.dataset.valor) {
            el.textContent = 'R$ ' + formatarMoedaBR(el.dataset.valor);
        }
    });
}

/* ======================================================
   📏 ALTURAS
====================================================== */
function igualarAlturaGridPecas() {
    const grid = document.getElementById('grid-pecas');
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll('.pecas-card')).filter(
        card => card.closest('.pecas-card-link').offsetParent !== null
    );
    if (!cards.length) return;

    let maiorAltura = 0;

    cards.forEach(card => { card.style.height = 'auto'; });
    cards.forEach(card => { maiorAltura = Math.max(maiorAltura, card.offsetHeight); });
    cards.forEach(card => { card.style.height = maiorAltura + 'px'; });
}

function igualarAlturaCards() {
    const cards = Array.from(document.querySelectorAll('.card-produto')).filter(
        card => card.closest('.card-link').offsetParent !== null
    );
    if (!cards.length) return;

    const imagensPendentes = [];

    cards.forEach(card => {
        card.style.height = 'auto';
        const img = card.querySelector('img');
        if (img && !img.complete) imagensPendentes.push(img);
    });

    function aplicar() {
        let maior = 0;

        cards.forEach(card => {
            card.style.height = 'auto';
        });

        cards.forEach(card => {
            maior = Math.max(maior, card.offsetHeight);
        });

        cards.forEach(card => {
            card.style.height = maior + 'px';
        });
    }

    if (!imagensPendentes.length) {
        aplicar();
        return;
    }

    let carregadas = 0;

    imagensPendentes.forEach(img => {
        img.addEventListener('load', () => {
            carregadas++;
            if (carregadas === imagensPendentes.length) aplicar();
        }, { once: true });

        img.addEventListener('error', () => {
            carregadas++;
            if (carregadas === imagensPendentes.length) aplicar();
        }, { once: true });
    });
}

// Recalcula sempre que a tela muda de tamanho (o grid muda de colunas
// e a altura ideal dos cards muda junto)
let _resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(() => {
        igualarAlturaCards();
        igualarAlturaGridPecas();
    }, 200);
});


/* ======================================================
   ⭐ ESTRELAS
====================================================== */
const fullStar = `
<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896l-7.336 3.878 1.402-8.176L.132 9.21l8.2-1.192z"/>
</svg>`;

const emptyStar = `
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896l-7.336 3.878 1.402-8.176L.132 9.21l8.2-1.192z" stroke-width="1.2"/>
</svg>`;

function gerarHalfStar(id) {
    return `
    <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="halfGrad-${id}">
          <stop offset="50%" stop-color="currentColor"/>
          <stop offset="50%" stop-color="transparent"/>
        </linearGradient>
      </defs>
      <path d="M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896 4.664 22.774 l1.402-8.176L.13 9.21l8.2-1.192z" fill="url(#halfGrad-${id})"/>
    </svg>`;
}

function renderStars(container, rating) {
    let starsWrap = container.querySelector('.stars');

    if (!starsWrap) {
        starsWrap = document.createElement('div');
        starsWrap.className = 'stars';
        container.appendChild(starsWrap);
    }

    starsWrap.innerHTML = '';

    const r = parseFloat(String(rating).replace(',', '.')) || 0;

    for (let i = 1; i <= 5; i++) {
        if (r >= i) {
            starsWrap.insertAdjacentHTML('beforeend', fullStar);
        } else if (r >= i - 0.5) {
            const uid = (window.crypto && crypto.randomUUID)
                ? crypto.randomUUID()
                : `half-${Date.now()}-${i}-${Math.random().toString(16).slice(2)}`;

            starsWrap.insertAdjacentHTML('beforeend', gerarHalfStar(uid));
        } else {
            starsWrap.insertAdjacentHTML('beforeend', emptyStar);
        }
    }
}

function renderizarTodasEstrelas(root = document) {
    const elementos = root.querySelectorAll('.avaliacao');
    elementos.forEach(el => {
        renderStars(el, el.dataset.rating);
    });
}

/* ======================================================
   🎛️ PRODUTOS — filtro/ordenação/paginação no navegador
   (sem ida ao servidor: tudo já está no DOM, então é instantâneo)
====================================================== */
function scrollParaProdutos() {
    const secao = document.getElementById('brinquedos');
    if (!secao) return;

    window.scrollTo({
        top: secao.getBoundingClientRect().top + window.scrollY - 80,
        behavior: 'smooth'
    });
}

function paraNumeroBR(valor) {
    return normalizarNumeroMoeda(valor);
}

function reanimarCard(card, atraso) {
    const alvo = card.querySelector('.card-produto, .pecas-card') || card;
    alvo.style.animation = 'none';
    void alvo.offsetHeight; // força reflow pra poder reiniciar a animação
    alvo.style.animationDelay = atraso + 's';
    alvo.style.animation = '';
}

function inicializarProdutosClientSide() {
    const grid = document.getElementById('grid-cards');
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll('.card-link'));
    if (!cards.length) return;

    const porPagina = 9;
    let pagina = 1;
    let ordem = 'az';

    function ordenar() {
        const copia = cards.slice();
        copia.sort((a, b) => {
            switch (ordem) {
                case 'za':
                    return b.dataset.nome.localeCompare(a.dataset.nome, 'pt-BR');
                case 'melhor-avaliados':
                    return paraNumeroBR(b.dataset.avaliacao) - paraNumeroBR(a.dataset.avaliacao)
                        || a.dataset.nome.localeCompare(b.dataset.nome, 'pt-BR');
                case 'custo-beneficio': {
                    const precoA = paraNumeroBR(a.dataset.preco);
                    const precoB = paraNumeroBR(b.dataset.preco);
                    const scoreA = precoA > 0 ? paraNumeroBR(a.dataset.avaliacao) / precoA : -1;
                    const scoreB = precoB > 0 ? paraNumeroBR(b.dataset.avaliacao) / precoB : -1;
                    return scoreB - scoreA || a.dataset.nome.localeCompare(b.dataset.nome, 'pt-BR');
                }
                case 'novidades':
                    return paraNumeroBR(b.dataset.id) - paraNumeroBR(a.dataset.id)
                        || a.dataset.nome.localeCompare(b.dataset.nome, 'pt-BR');
                default:
                    return a.dataset.nome.localeCompare(b.dataset.nome, 'pt-BR');
            }
        });
        return copia;
    }

    function renderizar() {
        const ordenados = ordenar();
        const totalPaginas = Math.max(1, Math.ceil(ordenados.length / porPagina));
        if (pagina > totalPaginas) pagina = totalPaginas;

        const inicio = (pagina - 1) * porPagina;
        const visiveis = new Set(ordenados.slice(inicio, inicio + porPagina));

        let atraso = 0;
        ordenados.forEach(card => {
            if (visiveis.has(card)) {
                card.style.display = '';
                grid.appendChild(card);
                reanimarCard(card, atraso);
                atraso += 0.035;
            } else {
                card.style.display = 'none';
            }
        });

        document.getElementById('prod-page-info').textContent =
            `Página ${pagina} de ${totalPaginas}`;
        document.getElementById('prod-prev').disabled = pagina <= 1;
        document.getElementById('prod-next').disabled = pagina >= totalPaginas;

        renderizarTodasEstrelas(grid);
        renderizarMoedas(grid);
        requestAnimationFrame(() => requestAnimationFrame(igualarAlturaCards));
    }

    document.querySelectorAll('#filtros-bar .filtro-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#filtros-bar .filtro-btn').forEach(b => {
                b.classList.remove('ativo');
                b.setAttribute('aria-pressed', 'false');
            });
            btn.classList.add('ativo');
            btn.setAttribute('aria-pressed', 'true');
            ordem = btn.dataset.order;
            pagina = 1;
            renderizar();
            scrollParaProdutos();
        });
    });

    document.getElementById('prod-prev').addEventListener('click', () => {
        if (pagina > 1) { pagina--; renderizar(); scrollParaProdutos(); }
    });

    document.getElementById('prod-next').addEventListener('click', () => {
        pagina++; renderizar(); scrollParaProdutos();
    });

    renderizar();
}

/* ======================================================
   🎛️ PEÇAS — filtro por categoria + paginação no navegador
====================================================== */
function scrollParaPecas() {
    const secao = document.getElementById('pecas-section');
    if (!secao) return;

    window.scrollTo({
        top: secao.getBoundingClientRect().top + window.scrollY - 80,
        behavior: 'smooth'
    });
}

function inicializarPecasClientSide() {
    const grid = document.getElementById('grid-pecas');
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll('.pecas-card-link'));
    if (!cards.length) return;

    const porPagina = 9;
    let pagina = 1;
    let categoriaAtiva = '';

    function filtrados() {
        if (!categoriaAtiva) return cards.slice();
        return cards.filter(card =>
            (card.dataset.categorias || '').split(',').includes(categoriaAtiva)
        );
    }

    function renderizar() {
        const lista = filtrados();
        const totalPaginas = Math.max(1, Math.ceil(lista.length / porPagina));
        if (pagina > totalPaginas) pagina = totalPaginas;

        const inicio = (pagina - 1) * porPagina;
        const visiveis = new Set(lista.slice(inicio, inicio + porPagina));

        let atraso = 0;
        cards.forEach(card => {
            if (visiveis.has(card)) {
                card.style.display = '';
                grid.appendChild(card);
                reanimarCard(card, atraso);
                atraso += 0.035;
            } else {
                card.style.display = 'none';
            }
        });

        document.getElementById('pecas-page-info').textContent =
            `Página ${pagina} de ${totalPaginas}`;
        document.getElementById('pecas-prev').disabled = pagina <= 1;
        document.getElementById('pecas-next').disabled = pagina >= totalPaginas;

        renderizarMoedas(grid);
        requestAnimationFrame(() => requestAnimationFrame(igualarAlturaGridPecas));
    }

    document.querySelectorAll('#filtros-peca .filtro-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#filtros-peca .filtro-btn').forEach(b => b.classList.remove('ativo'));
            btn.classList.add('ativo');
            categoriaAtiva = btn.dataset.categoria || '';
            pagina = 1;
            renderizar();
            scrollParaPecas();
        });
    });

    document.getElementById('pecas-prev').addEventListener('click', () => {
        if (pagina > 1) { pagina--; renderizar(); scrollParaPecas(); }
    });

    document.getElementById('pecas-next').addEventListener('click', () => {
        pagina++; renderizar(); scrollParaPecas();
    });

    renderizar();
}

/* ======================================================
   🎛️ PAGINAÇÃO PADRÃO (eventos, projetos) — sem ordenação
   nem filtro, só mostra N por página e esconde os controles
   quando cabe tudo numa página só.
====================================================== */
function inicializarGridPaginado({ gridId, cardSelector, porPagina, prevId, nextId, infoId, paginacaoWrapperId, scrollTargetId }) {
    const grid = document.getElementById(gridId);
    const wrapper = document.getElementById(paginacaoWrapperId);
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll(cardSelector));

    if (!cards.length) {
        if (wrapper) wrapper.style.display = 'none';
        return;
    }

    const totalPaginas = Math.max(1, Math.ceil(cards.length / porPagina));
    let pagina = 1;

    // Pedido explícito: se não tem o que paginar, a paginação nem aparece
    if (wrapper) wrapper.style.display = totalPaginas <= 1 ? 'none' : '';

    function scrollParaSecao() {
        const alvo = document.getElementById(scrollTargetId);
        if (!alvo) return;
        window.scrollTo({
            top: alvo.getBoundingClientRect().top + window.scrollY - 80,
            behavior: 'smooth'
        });
    }

    function renderizar() {
        const inicio = (pagina - 1) * porPagina;
        const fim = inicio + porPagina;

        let atraso = 0;
        cards.forEach((card, i) => {
            if (i >= inicio && i < fim) {
                card.style.display = '';
                reanimarCard(card, atraso);
                atraso += 0.035;
            } else {
                card.style.display = 'none';
            }
        });

        const infoEl = document.getElementById(infoId);
        if (infoEl) infoEl.textContent = `Página ${pagina} de ${totalPaginas}`;

        const prevBtn = document.getElementById(prevId);
        const nextBtn = document.getElementById(nextId);
        if (prevBtn) prevBtn.disabled = pagina <= 1;
        if (nextBtn) nextBtn.disabled = pagina >= totalPaginas;
    }

    const prevBtn = document.getElementById(prevId);
    const nextBtn = document.getElementById(nextId);

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (pagina > 1) { pagina--; renderizar(); scrollParaSecao(); }
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (pagina < totalPaginas) { pagina++; renderizar(); scrollParaSecao(); }
        });
    }

    renderizar();
}

/* ======================================================
   COMBOS — 3 cards inteiros, setas e arraste horizontal
====================================================== */
function inicializarCarrosselCombos() {
    const trilho = document.getElementById('scroll-container-combos');
    const anterior = document.getElementById('scroll-left-combos');
    const proximo = document.getElementById('scroll-right-combos');

    if (!trilho || !anterior || !proximo) return;

    const movimentoReduzido = window.matchMedia('(prefers-reduced-motion: reduce)');
    let frameAtualizacao = null;
    let arrastando = false;
    let arrastou = false;
    let inicioX = 0;
    let scrollInicial = 0;
    let bloquearClique = false;

    function medidas() {
        const card = trilho.querySelector('.oferta-card-link');
        const estilos = window.getComputedStyle(trilho);
        const gap = Number.parseFloat(estilos.columnGap || estilos.gap) || 22;
        const largura = card ? card.getBoundingClientRect().width : trilho.clientWidth;
        const passo = largura + gap;
        const visiveis = Math.max(1, Math.round((trilho.clientWidth + gap) / passo));
        return { passo, visiveis };
    }

    function atualizarBotoes() {
        const maximo = Math.max(0, trilho.scrollWidth - trilho.clientWidth);
        anterior.disabled = trilho.scrollLeft <= 3;
        proximo.disabled = maximo <= 3 || trilho.scrollLeft >= maximo - 3;
    }

    function solicitarAtualizacao() {
        if (frameAtualizacao) return;
        frameAtualizacao = window.requestAnimationFrame(() => {
            frameAtualizacao = null;
            atualizarBotoes();
        });
    }

    function rolar(direcao) {
        const { passo, visiveis } = medidas();
        trilho.scrollBy({
            left: passo * visiveis * direcao,
            behavior: movimentoReduzido.matches ? 'auto' : 'smooth'
        });
    }

    anterior.addEventListener('click', () => rolar(-1));
    proximo.addEventListener('click', () => rolar(1));
    trilho.addEventListener('scroll', solicitarAtualizacao, { passive: true });

    /* Arraste com mouse no computador; toque continua nativo no celular. */
    trilho.addEventListener('pointerdown', event => {
        if (event.pointerType !== 'mouse' || event.button !== 0) return;
        arrastando = true;
        arrastou = false;
        inicioX = event.clientX;
        scrollInicial = trilho.scrollLeft;
        trilho.classList.add('is-dragging');
        trilho.setPointerCapture(event.pointerId);
    });

    trilho.addEventListener('pointermove', event => {
        if (!arrastando) return;
        const deslocamento = inicioX - event.clientX;
        if (Math.abs(deslocamento) > 6) arrastou = true;
        if (!arrastou) return;
        event.preventDefault();
        trilho.scrollLeft = scrollInicial + deslocamento;
    });

    function encerrarArraste(event) {
        if (!arrastando) return;
        arrastando = false;
        bloquearClique = arrastou;
        trilho.classList.remove('is-dragging');
        if (trilho.hasPointerCapture(event.pointerId)) {
            trilho.releasePointerCapture(event.pointerId);
        }
        solicitarAtualizacao();
    }

    trilho.addEventListener('pointerup', encerrarArraste);
    trilho.addEventListener('pointercancel', encerrarArraste);

    trilho.addEventListener('click', event => {
        if (!bloquearClique) return;
        event.preventDefault();
        event.stopPropagation();
        bloquearClique = false;
    }, true);

    window.addEventListener('resize', solicitarAtualizacao);
    atualizarBotoes();
}

/* ======================================================
   🚀 INIT GLOBAL
====================================================== */
document.addEventListener("DOMContentLoaded", () => {
    renderizarTodasEstrelas();
    renderizarMoedas();

    igualarAlturaCards();
    igualarAlturaGridPecas();
    inicializarCarrosselCombos();

    inicializarProdutosClientSide();
    inicializarPecasClientSide();
    inicializarGridPaginado({
        gridId: 'grid-eventos', cardSelector: '.evento-card', porPagina: 9,
        prevId: 'eventos-prev', nextId: 'eventos-next', infoId: 'eventos-page-info',
        paginacaoWrapperId: 'paginacao-eventos', scrollTargetId: 'eventos'
    });
    inicializarGridPaginado({
        gridId: 'grid-projetos', cardSelector: '.evento-card', porPagina: 9,
        prevId: 'projetos-prev', nextId: 'projetos-next', infoId: 'projetos-page-info',
        paginacaoWrapperId: 'paginacao-projetos', scrollTargetId: 'projetos'
    });

    const scrollContainer = document.getElementById("scroll-container");
    const leftBtn = document.getElementById("scroll-left");
    const rightBtn = document.getElementById("scroll-right");
    const categoriasCounter = document.getElementById("categorias-counter");

    if (scrollContainer && leftBtn && rightBtn) {
        const mediaMobile = window.matchMedia("(max-width: 768px)");
        const movimentoReduzido = window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        );
        let autoScroll = null;
        let scrollFrame = null;

        function cardsVisiveis() {
            return Array.from(
                scrollContainer.querySelectorAll(".categoria-link")
            ).filter(card => window.getComputedStyle(card).display !== "none");
        }

        function medidas() {
            const cards = cardsVisiveis();
            const primeiro = cards[0];
            const estilos = window.getComputedStyle(scrollContainer);
            const gap = Number.parseFloat(estilos.columnGap || estilos.gap) || 14;
            const larguraCard = primeiro?.getBoundingClientRect().width || 190;
            const passo = larguraCard + gap;
            const porPagina = Math.max(
                1,
                Math.floor((scrollContainer.clientWidth + gap) / passo)
            );

            return { cards, passo, porPagina };
        }

        function atualizarCarrossel() {
            const { cards, passo, porPagina } = medidas();
            const total = cards.length;

            if (mediaMobile.matches) {
                leftBtn.disabled = true;
                rightBtn.disabled = true;
                if (categoriasCounter) {
                    categoriasCounter.textContent = `${total} opções em destaque`;
                }
                return;
            }

            const maximo = Math.max(
                0,
                scrollContainer.scrollWidth - scrollContainer.clientWidth
            );
            const noInicio = scrollContainer.scrollLeft <= 3;
            const noFim = scrollContainer.scrollLeft >= maximo - 3;
            const inicio = Math.min(
                total,
                Math.max(1, Math.round(scrollContainer.scrollLeft / passo) + 1)
            );
            const fim = Math.min(total, inicio + porPagina - 1);

            leftBtn.disabled = noInicio;
            rightBtn.disabled = noFim || maximo === 0;

            if (categoriasCounter) {
                categoriasCounter.textContent = total
                    ? `${inicio}–${fim} de ${total} categorias`
                    : "Nenhuma categoria disponível";
            }
        }

        function solicitarAtualizacao() {
            if (scrollFrame) return;
            scrollFrame = window.requestAnimationFrame(() => {
                scrollFrame = null;
                atualizarCarrossel();
            });
        }

        function rolar(direcao, umaCategoria = false) {
            if (mediaMobile.matches) return;

            const { passo, porPagina } = medidas();
            const distancia = passo * (umaCategoria ? 1 : porPagina);
            scrollContainer.scrollBy({
                left: direcao === "proximo" ? distancia : -distancia,
                behavior: movimentoReduzido.matches ? "auto" : "smooth"
            });
        }

        function pararAutoScroll() {
            window.clearInterval(autoScroll);
            autoScroll = null;
        }

        function iniciarAutoScroll() {
            pararAutoScroll();
            if (
                mediaMobile.matches ||
                movimentoReduzido.matches ||
                document.hidden ||
                scrollContainer.scrollWidth <= scrollContainer.clientWidth + 3
            ) return;

            autoScroll = window.setInterval(() => {
                const maximo = Math.max(
                    0,
                    scrollContainer.scrollWidth - scrollContainer.clientWidth
                );

                if (scrollContainer.scrollLeft >= maximo - 3) {
                    scrollContainer.scrollTo({
                        left: 0,
                        behavior: "smooth"
                    });
                } else {
                    rolar("proximo", true);
                }
            }, 4200);
        }

        function reiniciarAutoScroll() {
            pararAutoScroll();
            iniciarAutoScroll();
        }

        rightBtn.addEventListener("click", () => {
            rolar("proximo");
            reiniciarAutoScroll();
        });

        leftBtn.addEventListener("click", () => {
            rolar("anterior");
            reiniciarAutoScroll();
        });

        scrollContainer.addEventListener("scroll", solicitarAtualizacao, {
            passive: true
        });
        scrollContainer.addEventListener("mouseenter", pararAutoScroll);
        scrollContainer.addEventListener("mouseleave", iniciarAutoScroll);
        scrollContainer.addEventListener("touchstart", pararAutoScroll, {
            passive: true
        });
        scrollContainer.addEventListener("touchend", iniciarAutoScroll, {
            passive: true
        });
        scrollContainer.addEventListener("focusin", pararAutoScroll);
        scrollContainer.addEventListener("focusout", iniciarAutoScroll);

        document.addEventListener("visibilitychange", () => {
            if (document.hidden) pararAutoScroll();
            else iniciarAutoScroll();
        });

        window.addEventListener("resize", () => {
            if (mediaMobile.matches) scrollContainer.scrollLeft = 0;
            solicitarAtualizacao();
            reiniciarAutoScroll();
        });

        if (typeof ResizeObserver !== "undefined") {
            new ResizeObserver(solicitarAtualizacao).observe(scrollContainer);
        }

        atualizarCarrossel();
        iniciarAutoScroll();
    }

    document.querySelectorAll(".carousel-slide").forEach(img => {
        if (img.complete) {
            img.classList.add("loaded");
        } else {
            img.addEventListener("load", () => {
                img.classList.add("loaded");
            });
        }
    });

    const messages = document.querySelectorAll('.rotating-messages .message');
    if (messages.length) {
        let currentIndex = 0;
        messages[0].classList.add('active');

        setInterval(() => {
            messages[currentIndex].classList.remove('active');
            currentIndex = (currentIndex + 1) % messages.length;
            messages[currentIndex].classList.add('active');
        }, 5000);
    }

    const params = new URLSearchParams(window.location.search);
    if (params.has("scroll")) {
        const alvo = document.querySelector(".produto-container");
        if (alvo) {
            const posicao = alvo.offsetTop - window.innerHeight / 3;
            window.scrollTo({
                top: posicao,
                behavior: "smooth"
            });
        }
    }

    document.querySelectorAll("[data-modal]").forEach(card => {
        card.addEventListener("click", () => {
            const modalId = card.dataset.modal;
            const modal = document.getElementById(modalId);
            if (!modal) return;

            modal.style.display = "block";
            document.body.style.overflow = "hidden";

            if (typeof initCarousel === 'function') {
                modal.querySelectorAll(".modal-carousel-track").forEach(track => initCarousel(track));
            }
        });
    });

    document.querySelectorAll(".modal-close").forEach(btn => {
        btn.addEventListener("click", () => {
            const modal = btn.closest(".evento-modal, .projeto-modal");
            if (!modal) return;

            modal.style.display = "none";
            document.body.style.overflow = "auto";
        });
    });

    document.querySelectorAll(".evento-modal, .projeto-modal").forEach(modal => {
        modal.addEventListener("click", e => {
            if (e.target === modal) {
                modal.style.display = "none";
                document.body.style.overflow = "auto";
            }
        });
    });

    document.querySelectorAll(".carousel-btn[data-target], .carousel-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const trackEl = document.getElementById(btn.dataset.target);
            if (!trackEl) return;

            const img = trackEl.querySelector("img");
            const cardWidth = (img ? img.offsetWidth : 288) + 12;

            if (btn.classList.contains("left")) {
                trackEl.scrollLeft -= cardWidth;
            } else {
                trackEl.scrollLeft += cardWidth;
            }
        });
    });

    const slider = document.getElementById("pecasSlider");
    if (slider) {
        const slides = slider.querySelectorAll(".peca-slide");

        if (slides.length) {
            let current = Math.floor(Math.random() * slides.length);
            slides[current].classList.add("active");

            setInterval(() => {
                slides[current].classList.remove("active");
                current = (current + 1) % slides.length;
                slides[current].classList.add("active");
            }, 3000);
        }
    }
});

/* ======================================================
   📄 CLICK GLOBAL
====================================================== */
// Filtros e paginação de brinquedos/peças agora são tratados direto em
// inicializarProdutosClientSide() e inicializarPecasClientSide() --
// cada botão já tem seu próprio listener, não precisa de delegação aqui.
