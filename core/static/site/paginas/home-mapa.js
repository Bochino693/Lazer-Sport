/* O mapa da home: a fábrica e os clientes num mapa só (seção #contato).
 *
 * Quem carrega este arquivo é o pequeno script no fim do home.html, quando
 * a seção chega perto da tela -- e só depois do Leaflet.
 *
 * O QUE ELE FAZ
 *   * desenha o alfinete vermelho da fábrica e os azuis dos clientes, com o
 *     cartãozinho no passar do mouse e o cartão completo no clique;
 *   * as camadas "Fábrica" e "Clientes" (os botões em cima do mapa) ligam e
 *     desligam cada grupo, e o filtro por cidade vale para o mapa e para a
 *     lista ao lado;
 *   * clicar num nome da lista leva até o alfinete dele; "Ver no mapa", no
 *     cartão da fábrica, aproxima até a rua da fábrica.
 *
 * ALFINETE NO LUGAR DELE, E O NÚMERO SÓ QUANDO NÃO CABE
 *   O agrupamento antigo juntava num número tudo o que se encostasse na
 *   tela: com o Brasil inteiro aparecendo, os clientes de São Paulo viravam
 *   um "9" logo de cara. Agora:
 *     * quem se cobre primeiro SE ESPALHA: sai um pouco do lugar (até 66 px,
 *       e nunca mais que ~650 km), em volta do ponto de verdade, com uma
 *       linha fininha e uma bolinha marcando onde ele fica de fato;
 *     * o número (o grupo) só aparece onde nem espalhando cabe: muitos
 *       clientes num pedaço pequeno do mapa, ou o mapa visto bem de longe.
 *       São poucos grupos, cada um de gente vizinha de verdade, em cima de
 *       um dos clientes dele;
 *     * cliente preso debaixo da fábrica vira um selo "+N" na própria
 *       fábrica;
 *     * clicar num grupo aproxima só o necessário para soltar quem dá; se
 *       nem o zoom máximo solta (muitos no mesmo endereço), os alfinetes
 *       abrem em leque, cada um com uma linha até o ponto real.
 */
(function () {
    'use strict';

    const caixa = document.getElementById('mapa-onde');
    const fonte = document.getElementById('dados-mapa-onde');
    if (!caixa || !fonte || !window.L || caixa._leaflet_id) return;

    const secao = caixa.closest('.ls-onde') || document;
    const LOGO_PADRAO = caixa.dataset.logo || '';
    const CENTRO_DO_BRASIL = [-14.235, -51.925];
    const ZOOM_MAXIMO = 18;
    const ZOOM_DA_FABRICA = 16;

    // Tamanho dos alfinetes na tela (px). O agrupamento usa as mesmas
    // medidas: é o desenho que decide se um cobre o outro.
    const PINO_CLIENTE = { largura: 38, altura: 51, janela: 21 };
    const PINO_FABRICA = { largura: 46, altura: 62, janela: 25 };

    /* ------------------------------------------------------------------
       Os pontos
       ------------------------------------------------------------------ */
    function coordenadaValida(p) {
        const lat = Number(p.lat);
        const lng = Number(p.lng);
        return Number.isFinite(lat) && Number.isFinite(lng) &&
            lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
    }

    let brutos = [];
    try {
        brutos = JSON.parse(fonte.textContent) || [];
    } catch (erro) {
        brutos = [];
    }

    const fabricaBruta = brutos.find((p) => p.tipo === 'fabrica');
    const fabrica = fabricaBruta && coordenadaValida(fabricaBruta)
        ? { ...fabricaBruta, lat: Number(fabricaBruta.lat), lng: Number(fabricaBruta.lng) }
        : null;

    // `indice` é a posição do cliente na lista da página (o mesmo
    // forloop.counter0 do template): é assim que um nome da lista acha o
    // seu alfinete.
    const clientes = brutos
        .filter((p) => p.tipo === 'cliente')
        .map((c, indice) => ({ ...c, indice }))
        .filter(coordenadaValida)
        .map((c) => ({ ...c, lat: Number(c.lat), lng: Number(c.lng) }));
    const clientePorIndice = new Map(clientes.map((c) => [c.indice, c]));

    if (!fabrica && !clientes.length) return;

    const estado = {
        fabrica: Boolean(fabrica),
        clientes: true,
        cidade: 'todas',
    };

    const dispositivoComHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    const dispositivoCompacto = window.matchMedia('(max-width: 575px), (hover: none)').matches;

    /* ------------------------------------------------------------------
       O mapa
       ------------------------------------------------------------------ */
    caixa.querySelector('.ls-onde-reserva')?.remove();
    secao.classList.add('ls-onde--pronto');

    // Um mundo só: o mapa não se repete para os lados (arrastando muito,
    // aparecia outra América, sem nenhum alfinete). O arrasto para na beira
    // do mundo, e o zoom mínimo é o que ainda enche a caixa do mapa.
    const MUNDO = L.latLngBounds([[-85.05112878, -180], [85.05112878, 180]]);

    const mapa = L.map(caixa, {
        scrollWheelZoom: false,
        maxZoom: ZOOM_MAXIMO,
        zoomSnap: 1,
        maxBounds: MUNDO,
        maxBoundsViscosity: 1,
        worldCopyJump: false,
    });

    function zoomQueEncheACaixa() {
        const tamanho = mapa.getSize();
        const lado = Math.max(tamanho.x, tamanho.y, 1);
        return Math.max(0, Math.ceil(Math.log2(lado / 256)));
    }

    function ajustarZoomMinimo() {
        const minimo = zoomQueEncheACaixa();
        if (mapa.getMinZoom() !== minimo) mapa.setMinZoom(minimo);
    }
    ajustarZoomMinimo();
    mapa.on('resize', ajustarZoomMinimo);

    /* O servidor de mapas do OpenStreetMap recusa (o quadro "Access
       blocked") quem pede o mapa sem dizer de que site vem. O site manda
       `Referrer-Policy: same-origin` -- o padrão do Django --, que não diz
       nada para outros domínios; aqui os quadros do mapa dizem só o
       endereço do site (sem a página), como pede a regra de uso. */
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: ZOOM_MAXIMO,
        noWrap: true,
        bounds: MUNDO,
        referrerPolicy: 'strict-origin-when-cross-origin',
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'
    }).addTo(mapa);

    /* ------------------------------------------------------------------
       Textos e desenhos
       ------------------------------------------------------------------ */
    function escapeHTML(texto) {
        const div = document.createElement('div');
        div.textContent = texto || '';
        return div.innerHTML;
    }

    function normalizarUrlExterna(valor) {
        const url = String(valor || '').trim();
        if (!/^https?:\/\//i.test(url)) return '';
        try {
            const destino = new URL(url);
            return ['http:', 'https:'].includes(destino.protocol) ? destino.href : '';
        } catch (erro) {
            return '';
        }
    }

    function localDoPonto(p) {
        return [p.cidade, p.estado].filter(Boolean).join(' - ') || p.pais || '';
    }

    const CATEGORIAS_PADRAO = ['Kid Play', 'Brinquedão', 'Trampolins', 'Eletrônicos'];
    const PINO_PATH_D = 'M215.7 499.2C267 435 384 279.4 384 192C384 86 298 0 192 0S0 86 0 192c0 87.4 117 243 168.3 307.2c12.3 15.3 35.1 15.3 47.4 0z';
    let sequenciaPino = 0;

    function criarPino({ largura, altura, corPino, janela, conteudoJanela, classeSvg = '', extra = '' }) {
        const idMascara = `mascara-pino-${++sequenciaPino}`;
        const centroY = 179;
        const raioFuro = Math.round((janela / largura) * 192);
        return `
            <span class="pino-gota" style="width:${largura}px;height:${altura}px;">
                <span class="pino-gota__janela" style="width:${janela}px;height:${janela}px;">
                    ${conteudoJanela}
                </span>
                <svg class="pino-gota__corpo ${classeSvg}" viewBox="0 0 384 512"
                     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <defs>
                        <mask id="${idMascara}">
                            <rect width="384" height="512" fill="#fff"/>
                            <circle cx="192" cy="${centroY}" r="${raioFuro}" fill="#000"/>
                        </mask>
                    </defs>
                    <path d="${PINO_PATH_D}" fill="${corPino}" mask="url(#${idMascara})"/>
                </svg>
                <svg class="pino-gota__aro" viewBox="0 0 384 512"
                     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <circle cx="192" cy="${centroY}" r="${raioFuro}"
                            fill="none" stroke="#fff" stroke-width="18"/>
                </svg>
                ${extra}
            </span>
        `;
    }

    function iconeCliente(c) {
        // A marca do pino é sempre a da casa (ver `clientes_mapa`, em
        // core/views.py): o mapa diz onde a Lazer & Sport atende.
        const imagem = escapeHTML(c.logo || LOGO_PADRAO);
        const reserva = escapeHTML(LOGO_PADRAO);
        return L.divIcon({
            className: 'cliente-marker',
            html: criarPino({
                ...PINO_CLIENTE,
                corPino: '#004AAD',
                conteudoJanela: `<img src="${imagem}" alt="" onerror="this.onerror=null;this.src='${reserva}';">`
            }),
            iconSize: [PINO_CLIENTE.largura, PINO_CLIENTE.altura],
            iconAnchor: [PINO_CLIENTE.largura / 2, PINO_CLIENTE.altura],
        });
    }

    // O grupo é um alfinete do mesmo tamanho, com o número no lugar da logo
    // e dois "fantasmas" atrás (o CSS desenha), para ler como uma pilha.
    function iconeGrupo(n) {
        return L.divIcon({
            className: 'grupo-marker',
            html: criarPino({
                ...PINO_CLIENTE,
                janela: 25,
                corPino: '#0878F9',
                classeSvg: 'pino-gota__corpo--pilha',
                conteudoJanela: `<b class="pino-gota__numero">${n}</b>`
            }),
            iconSize: [PINO_CLIENTE.largura, PINO_CLIENTE.altura],
            iconAnchor: [PINO_CLIENTE.largura / 2, PINO_CLIENTE.altura],
        });
    }

    // O selo "+N" (clientes escondidos debaixo da fábrica) fica DENTRO do
    // desenho do alfinete, no corpo, abaixo da janela: não ocupa espaço
    // fora do pino e por isso nunca fica atrás de outro alfinete.
    function iconeFabrica(escondidos) {
        const selo = escondidos
            ? `<span class="pino-selo" title="Mais ${escondidos} cliente${escondidos === 1 ? '' : 's'} aqui perto">+${escondidos}</span>`
            : '';
        return L.divIcon({
            className: 'fabrica-marker',
            html: criarPino({
                ...PINO_FABRICA,
                corPino: '#E63946',
                classeSvg: 'pino-pulse',
                conteudoJanela: `
                    <svg class="pino-fabrica-icone" viewBox="0 0 64 64"
                         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                        <path d="M6 56V26l15 8V24l15 9V18h9v20l13 7v11H6zm8-8h7v-7h-7v7zm14 0h7v-7h-7v7zm14 0h7v-7h-7v7zM38 14V7h7v7h-7z"/>
                    </svg>`,
                extra: selo
            }),
            iconSize: [PINO_FABRICA.largura, PINO_FABRICA.altura],
            iconAnchor: [PINO_FABRICA.largura / 2, PINO_FABRICA.altura],
        });
    }

    function criarPopupCliente(c) {
        const nome = escapeHTML(c.nome);
        const imagem = escapeHTML(c.logo || LOGO_PADRAO);
        const reserva = escapeHTML(LOGO_PADRAO);
        const cidadeEstado = [c.cidade, c.estado].filter(Boolean).join(' - ');
        const localCompleto = [
            cidadeEstado,
            c.pais && c.pais !== 'Brasil' ? c.pais : ''
        ].filter(Boolean).join(', ') || c.pais || 'Localização disponível no mapa';
        const descricao = escapeHTML(
            c.descricao || 'Espaço atendido com equipamentos e soluções da Lazer & Sport Brinquedos.'
        );
        const urlCliente = normalizarUrlExterna(c.site || c.instagram);
        const instagram = urlCliente.includes('instagram.com');
        const link = urlCliente
            ? `<a class="cliente-popup__action ${instagram ? 'cliente-popup__action--instagram' : ''}"
                  href="${escapeHTML(urlCliente)}" target="_blank" rel="noopener"
                  aria-label="${instagram ? `Abrir Instagram de ${nome}` : `Visitar site de ${nome}`}">
                   <i class="${instagram ? 'fa-brands fa-instagram' : 'fa-solid fa-globe'}"></i>
                   ${instagram ? '<span class="cliente-popup__instagram-text">Instagram</span>' : 'Visitar site'}
               </a>`
            : '';
        const rota = `
            <a class="cliente-popup__action cliente-popup__action--route"
               href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${c.lat},${c.lng}`)}"
               target="_blank" rel="noopener">
                <i class="fa-solid fa-route"></i>
                Como chegar
            </a>`;
        const recebidas = Array.isArray(c.brinquedos)
            ? c.brinquedos
            : (Array.isArray(c.categorias) ? c.categorias : CATEGORIAS_PADRAO);
        const categorias = recebidas
            .map((item) => (typeof item === 'string' ? item : (item.nome || item.nome_brinquedo || '')))
            .filter(Boolean)
            .slice(0, 4);

        return `
            <div class="cliente-popup cliente-popup--cliente">
                <div class="cliente-popup__top">
                    <div class="cliente-popup__media">
                        <img src="${imagem}" alt="${nome}" onerror="this.onerror=null;this.src='${reserva}';">
                    </div>
                    <div class="cliente-popup__copy">
                        <span class="cliente-popup__kicker">
                            <i class="fa-solid fa-circle-check"></i>
                            Cliente Lazer &amp; Sport
                        </span>
                        <h4>${nome}</h4>
                    </div>
                </div>
                <div class="cliente-popup__location">
                    <i class="fa-solid fa-location-dot"></i>
                    <span>${escapeHTML(localCompleto)}</span>
                </div>
                <p class="cliente-popup__description">${descricao}</p>
                <div class="cliente-popup-tags">${categorias.map((t) => `<span>${escapeHTML(t)}</span>`).join('')}</div>
                <div class="cliente-popup__actions ${link ? '' : 'cliente-popup__actions--single'}">
                    ${link}
                    ${rota}
                </div>
            </div>
        `;
    }

    function criarPopupFabrica(f) {
        const nome = escapeHTML(f.nome);
        const local = escapeHTML([f.cidade, f.estado].filter(Boolean).join(' - '));
        const endereco = escapeHTML(f.endereco || '');
        const logo = escapeHTML(f.logo || LOGO_PADRAO);
        return `
            <div class="cliente-popup cliente-popup--fabrica">
                <div class="cliente-popup__top">
                    <div class="cliente-popup__media">
                        <img src="${logo}" alt="${nome}">
                    </div>
                    <div class="cliente-popup__copy">
                        <span class="cliente-popup__kicker">
                            <i class="fa-solid fa-industry"></i>
                            Nossa fábrica
                        </span>
                        <h4>${nome}</h4>
                    </div>
                </div>
                <div class="cliente-popup__location">
                    <i class="fa-solid fa-location-dot"></i>
                    <span>${[endereco, local].filter(Boolean).join(' — ')}</span>
                </div>
                <p class="cliente-popup__description">
                    Tecnologia, fabricação própria e diversão para projetos em todo o Brasil.
                </p>
                <div class="cliente-popup__actions cliente-popup__actions--single">
                    <a class="cliente-popup__action cliente-popup__action--route"
                       href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${f.lat},${f.lng}`)}"
                       target="_blank" rel="noopener">
                        <i class="fa-solid fa-route"></i>
                        Como chegar
                    </a>
                </div>
            </div>
        `;
    }

    function criarTooltip(ponto, eFabrica = false) {
        const nome = escapeHTML(ponto.nome || 'Lazer & Sport');
        const local = escapeHTML(localDoPonto(ponto));
        return `
            <div class="cliente-hover-card ${eFabrica ? 'cliente-hover-card--fabrica' : ''}">
                <strong>${nome}</strong>
                ${local ? `<span>${local}</span>` : ''}
                <small>
                    <i class="fa-solid fa-computer-mouse"></i>
                    Clique para manter as informações abertas
                </small>
            </div>
        `;
    }

    /* ------------------------------------------------------------------
       Cartão (popup) e cartãozinho (hover) de cada alfinete
       ------------------------------------------------------------------ */
    let marcadorPopupFixado = null;
    let sequenciaCentralizacao = 0;
    let sequenciaVoo = 0;   // ver voarE()

    function elevar(marcador, ativo) {
        const base = marcador._zIndexBaseLS || 0;
        marcador.getElement()?.classList.toggle('marcador-elevado', ativo);
        marcador.setZIndexOffset(ativo ? base + 1400 : base);
    }

    function abrirPopup(marcador) {
        if (!marcador._popupLS) return;
        const abrir = () => {
            if (!mapa.hasLayer(marcador)) return;
            marcadorPopupFixado = marcador;
            marcador._popupLS.setLatLng(marcador.getLatLng()).openOn(mapa);
        };

        if (!dispositivoCompacto) {
            abrir();
            return;
        }

        // No celular o cartão é quase do tamanho do mapa: antes de abrir,
        // o alfinete desce para perto do pé do mapa, e o cartão cabe em cima.
        const token = ++sequenciaCentralizacao;
        mapa.stop();
        const tamanho = mapa.getSize();
        const atual = mapa.latLngToContainerPoint(marcador.getLatLng());
        const seguro = L.point(tamanho.x / 2, tamanho.y * 0.68);
        const deslocamento = atual.subtract(seguro);
        if (Math.abs(deslocamento.x) < 5 && Math.abs(deslocamento.y) < 5) {
            abrir();
            return;
        }
        let feito = false;
        const concluir = () => {
            if (feito) return;
            feito = true;
            mapa.off('moveend', concluir);
            window.clearTimeout(reserva);
            if (token === sequenciaCentralizacao) abrir();
        };
        mapa.once('moveend', concluir);
        const reserva = window.setTimeout(concluir, 260);
        mapa.panBy(deslocamento, { animate: true, duration: 0.18, easeLinearity: 0.25 });
    }

    function fecharPopups() {
        sequenciaCentralizacao += 1;
        marcadorPopupFixado?.closeTooltip();
        marcadorPopupFixado = null;
        mapa.closePopup();
    }

    function configurarMarcador(marcador, { zIndexBase = 0, popup, tooltip, alturaPino, rotulo, aoClicar }) {
        const paddingSuperior = dispositivoCompacto ? 56 : 86;
        const paddingLateral = dispositivoCompacto ? 12 : 24;
        const paddingInferior = dispositivoCompacto ? 14 : 34;
        const deslocamentoY = -(alturaPino - 4);

        marcador._zIndexBaseLS = zIndexBase;
        marcador._rotuloLS = rotulo;
        if (popup) {
            marcador._popupLS = L.popup({
                autoClose: true,
                autoPan: true,
                autoPanPaddingTopLeft: L.point(paddingLateral, paddingSuperior),
                autoPanPaddingBottomRight: L.point(paddingLateral, paddingInferior),
                closeButton: true,
                closeOnClick: false,
                className: 'popup-cliente-lazer-sport',
                keepInView: true,
                maxWidth: dispositivoCompacto ? 252 : 320,
                minWidth: 0,
                offset: L.point(0, deslocamentoY)
            }).setContent(popup);

            marcador._popupLS.on('add', () => {
                marcador.getElement()?.setAttribute('aria-expanded', 'true');
                const elemento = marcador._popupLS.getElement?.();
                if (elemento) {
                    elemento.setAttribute('role', 'dialog');
                    elemento.setAttribute('aria-label', `Informações de ${rotulo}`);
                    elemento.querySelector('.leaflet-popup-close-button')
                        ?.setAttribute('aria-label', 'Fechar informações');
                }
                marcarNaLista(marcador._clienteLS, true);
            });
            marcador._popupLS.on('remove', () => {
                marcador.getElement()?.setAttribute('aria-expanded', 'false');
                if (marcadorPopupFixado === marcador) marcadorPopupFixado = null;
                marcarNaLista(marcador._clienteLS, false);
            });
        }

        if (dispositivoComHover && tooltip) {
            marcador.bindTooltip(tooltip, {
                className: 'cliente-hover-tooltip',
                direction: 'top',
                offset: L.point(0, deslocamentoY + 5),
                opacity: 1
            });
            marcador.on('mouseover', () => {
                elevar(marcador, true);
                // O cartão aberto já mostra tudo: o cartãozinho por cima sobra.
                if (marcador === marcadorPopupFixado) marcador.closeTooltip();
            });
            marcador.on('mouseout', () => elevar(marcador, false));
        }

        const acionar = (e) => {
            sequenciaVoo += 1;
            marcador.closeTooltip();
            if (aoClicar) {
                aoClicar(e);
                return;
            }
            abrirPopup(marcador);
        };
        marcador.on('click', (e) => {
            if (e.originalEvent) {
                L.DomEvent.stopPropagation(e.originalEvent);
                L.DomEvent.preventDefault(e.originalEvent);
            }
            acionar(e);
        });
        marcador.on('keypress', (e) => {
            const tecla = e.originalEvent?.key;
            if (tecla !== 'Enter' && tecla !== ' ') return;
            e.originalEvent.preventDefault();
            acionar(e);
        });

        const prepararElemento = () => {
            const elemento = marcador.getElement();
            if (!elemento) return;
            elemento.setAttribute('role', 'button');
            elemento.setAttribute('aria-label', rotulo);
            if (popup) {
                elemento.setAttribute('aria-haspopup', 'dialog');
                elemento.setAttribute('aria-expanded', 'false');
            }
            elemento.style.touchAction = 'manipulation';
        };
        marcador.on('add', prepararElemento);
        prepararElemento();
    }

    mapa.on('popupopen', (e) => {
        if (marcadorPopupFixado && marcadorPopupFixado._popupLS !== e.popup) {
            marcadorPopupFixado = null;
        }
        // Com o cartão aberto, a dica do topo sai (no celular ela ficava por cima dele).
        secao.classList.add('ls-onde--cartao-aberto');
    });
    mapa.on('popupclose', () => secao.classList.remove('ls-onde--cartao-aberto'));

    function clientesVisiveis() {
        if (!estado.clientes) return [];
        return estado.cidade === 'todas'
            ? clientes
            : clientes.filter((c) => c.cidade === estado.cidade);
    }

    /* ------------------------------------------------------------------
       Espalhar antes de juntar
       ------------------------------------------------------------------ */
    // Alfinetes que se cobrem saem um pouco do lugar, em volta do ponto de
    // verdade (com uma linha fininha até ele), em vez de virar um número.
    // O número (o grupo) só aparece quando nem espalhando dá: muitos
    // clientes num pedaço pequeno do mapa. Tudo em pixels do zoom pedido (e
    // não da tela atual): o resultado não muda ao arrastar o mapa.
    // Quanto um alfinete pode sair do lugar: até 66 px, e nunca mais que
    // ~650 km. Bem de longe (o mapa do mundo) 66 px seriam milhares de km e
    // o alfinete já não diria onde fica: aí o grupo (o número) volta.
    const DESLOCAMENTO_MAXIMO = 66;
    const DESLOCAMENTO_MAXIMO_KM = 650;
    const FOLGA_ALVO = 1.06;          // espalha até um pouco além de só encostar
    const FOLGA_ACEITA = 0.94;        // abaixo disso, depois de espalhar, ainda cobre
    const PERNA_MINIMA = 7;           // a partir daqui (px) desenha a linha até o ponto
    const ANGULO_DOURADO = Math.PI * (3 - Math.sqrt(5));

    function distanciaEliptica(a, b) {
        const rx = ((a.largura + b.largura) / 2) * 0.74;
        const ry = ((a.altura + b.altura) / 2) * 0.68;
        const dx = (b.x - a.x) / rx;
        const dy = (b.y - a.y) / ry;
        return { d: Math.hypot(dx, dy), dx, dy, rx, ry };
    }

    function novoNo(membros, zoom, { pino = PINO_CLIENTE, fixo = false, eFabrica = false } = {}) {
        // A âncora é um membro de verdade: o mais perto do meio do grupo.
        const pontos = membros.map((c) => mapa.project([c.lat, c.lng], zoom));
        const mx = pontos.reduce((t, q) => t + q.x, 0) / pontos.length;
        const my = pontos.reduce((t, q) => t + q.y, 0) / pontos.length;
        let k = 0;
        pontos.forEach((q, i) => {
            if (Math.hypot(q.x - mx, q.y - my) < Math.hypot(pontos[k].x - mx, pontos[k].y - my)) k = i;
        });
        const ancora = membros[k];
        const o = pontos[k];
        // Um empurrãozinho diferente para cada um: quem divide o mesmo
        // endereço sai para lados diferentes (e sempre os mesmos).
        const semente = (ancora.indice ?? -1) + 1;
        const jx = fixo ? 0 : Math.cos(semente * ANGULO_DOURADO) * 0.35;
        const jy = fixo ? 0 : Math.sin(semente * ANGULO_DOURADO) * 0.35;
        const kmPorPixel = (40075.016686 * Math.cos((ancora.lat * Math.PI) / 180)) / (256 * 2 ** zoom);
        return {
            membros, ancora, fixo, eFabrica,
            ox: o.x, oy: o.y, x: o.x + jx, y: o.y + jy,
            largura: pino.largura, altura: pino.altura,
            limite: fixo ? 0 : Math.min(DESLOCAMENTO_MAXIMO, DESLOCAMENTO_MAXIMO_KM / Math.max(kmPorPixel, 1e-6)),
        };
    }

    // Só os pares que podem se encostar (cada um sai no máximo o seu
    // `limite` do lugar) entram na conta.
    function paresPossiveis(nos) {
        const pares = [];
        for (let i = 0; i < nos.length; i++) {
            for (let j = i + 1; j < nos.length; j++) {
                const a = nos[i];
                const b = nos[j];
                if (a.fixo && b.fixo) continue;
                const alcance = a.limite + b.limite;
                const rx = ((a.largura + b.largura) / 2) * 0.74 * FOLGA_ALVO;
                const ry = ((a.altura + b.altura) / 2) * 0.68 * FOLGA_ALVO;
                if (Math.abs(a.ox - b.ox) < rx + alcance && Math.abs(a.oy - b.oy) < ry + alcance) {
                    pares.push([a, b]);
                }
            }
        }
        return pares;
    }

    function prender(n) {
        const dx = n.x - n.ox;
        const dy = n.y - n.oy;
        const dist = Math.hypot(dx, dy);
        if (dist > n.limite) {
            n.x = n.ox + (dx / dist) * n.limite;
            n.y = n.oy + (dy / dist) * n.limite;
        }
    }

    // Afasta quem se cobre e puxa cada um de volta para o seu ponto; a
    // puxada some nas últimas voltas, para terminar sem ninguém por cima.
    function espalhar(nos, pares, voltas) {
        for (let volta = 0; volta < voltas; volta++) {
            const puxada = 0.14 * Math.max(0, 1 - volta / (voltas * 0.7));
            if (puxada > 0) {
                nos.forEach((n) => {
                    if (n.fixo) return;
                    n.x += (n.ox - n.x) * puxada;
                    n.y += (n.oy - n.y) * puxada;
                });
            }
            for (const [a, b] of pares) {
                const { d, dx, dy, rx, ry } = distanciaEliptica(a, b);
                if (d >= FOLGA_ALVO) continue;
                let ux = dx;
                let uy = dy;
                if (d < 1e-9) {
                    const ang = ((a.ancora.indice ?? 0) * 7 + (b.ancora.indice ?? 0) * 13) * ANGULO_DOURADO;
                    ux = Math.cos(ang);
                    uy = Math.sin(ang);
                } else {
                    ux /= d;
                    uy /= d;
                }
                const falta = FOLGA_ALVO - d;
                const pesoA = a.fixo ? 0 : (b.fixo ? 1 : 0.5);
                const pesoB = 1 - pesoA;
                a.x -= ux * rx * falta * pesoA;
                a.y -= uy * ry * falta * pesoA;
                b.x += ux * rx * falta * pesoB;
                b.y += uy * ry * falta * pesoB;
            }
            nos.forEach((n) => { if (!n.fixo) prender(n); });
        }
    }

    const montagens = new Map();   // "zoom|camadas|cidade" -> resultado

    function montar(zoom) {
        const chave = `${zoom}|${estado.clientes}|${estado.fabrica}|${estado.cidade}`;
        if (montagens.has(chave)) return montagens.get(chave);

        let nos = clientesVisiveis().map((c) => novoNo([c], zoom));
        const noFabrica = fabrica && estado.fabrica
            ? novoNo([fabrica], zoom, { pino: PINO_FABRICA, fixo: true, eFabrica: true })
            : null;
        const debaixoDaFabrica = [];

        for (let rodada = 0; rodada < 400; rodada++) {
            const todos = noFabrica ? [noFabrica, ...nos] : nos;
            const pares = paresPossiveis(todos);
            espalhar(todos, pares, rodada === 0 ? 90 : 50);

            const cobertos = new Map();
            for (const [a, b] of pares) {
                if (distanciaEliptica(a, b).d >= FOLGA_ACEITA) continue;
                if (!cobertos.has(a)) cobertos.set(a, []);
                if (!cobertos.has(b)) cobertos.set(b, []);
                cobertos.get(a).push(b);
                cobertos.get(b).push(a);
            }
            if (!cobertos.size) break;

            // Primeiro juntam os clientes entre si: em cada região, o mais
            // disputado leva quem ainda o cobre e quem, no mapa de verdade,
            // fica no meio deles. Assim saem poucos grupos, cada um de gente
            // vizinha de verdade; regiões longe uma da outra juntam na mesma
            // rodada.
            const entreClientes = [...cobertos.entries()]
                .filter(([n]) => !n.fixo)
                .map(([n, vizinhos]) => [n, vizinhos.filter((v) => !v.fixo)])
                .filter(([, vizinhos]) => vizinhos.length)
                .sort(([a, va], [b, vb]) =>
                    (vb.length - va.length) ||
                    (b.membros.length - a.membros.length) ||
                    (a.ancora.indice - b.ancora.indice));
            if (entreClientes.length) {
                const usados = new Set();
                const centros = [];
                const novos = [];
                for (const [n, vizinhos] of entreClientes) {
                    if (usados.has(n)) continue;
                    const regiao = 2 * DESLOCAMENTO_MAXIMO + n.largura;
                    if (centros.some((c) => Math.abs(c.x - n.ox) < regiao && Math.abs(c.y - n.oy) < regiao)) continue;
                    const juntos = new Set([n, ...vizinhos.filter((v) => !usados.has(v))]);
                    if (juntos.size < 2) continue;
                    const lista = [...juntos];
                    const cx = lista.reduce((t, j) => t + j.ox, 0) / lista.length;
                    const cy = lista.reduce((t, j) => t + j.oy, 0) / lista.length;
                    const raio = Math.max(...lista.map((j) => Math.hypot(j.ox - cx, j.oy - cy))) + 2;
                    nos.forEach((o) => {
                        if (!usados.has(o) && Math.hypot(o.ox - cx, o.oy - cy) <= raio) juntos.add(o);
                    });
                    juntos.forEach((j) => usados.add(j));
                    centros.push({ x: cx, y: cy });
                    const membros = [...juntos].flatMap((j) => j.membros).sort((a, b) => a.indice - b.indice);
                    novos.push(novoNo(membros, zoom));
                }
                nos = nos.filter((n) => !usados.has(n)).concat(novos);
                continue;
            }

            // Só sobrou quem não consegue sair de baixo da fábrica: fica no
            // "+N" dela.
            const engolidos = new Set(cobertos.get(noFabrica) || []);
            engolidos.forEach((n) => debaixoDaFabrica.push(...n.membros));
            nos = nos.filter((n) => !engolidos.has(n));
            if (!engolidos.size) break;
        }

        const resultado = {
            grupos: nos.map((n) => ({
                ancora: n.ancora,
                membros: n.membros,
                deslocado: Math.hypot(n.x - n.ox, n.y - n.oy) >= PERNA_MINIMA,
                posicao: mapa.unproject(L.point(n.x, n.y), zoom),
            })),
            debaixoDaFabrica,
        };
        montagens.set(chave, resultado);
        return resultado;
    }

    // Como os `membros` aparecem no zoom `z`: soltos, num grupo (quais) ou
    // debaixo da fábrica. Serve para achar o zoom que já mostra o que dá.
    function retrato(membros, z) {
        const { grupos, debaixoDaFabrica } = montar(z);
        return membros.map((c) => {
            if (debaixoDaFabrica.includes(c)) return 'F';
            const g = grupos.find((gr) => gr.membros.includes(c));
            if (!g || g.membros.length === 1) return 's';
            return g.membros.map((m) => m.indice).join(',');
        }).join('|');
    }

    /* ------------------------------------------------------------------
       Desenho dos clientes, refeito a cada zoom
       ------------------------------------------------------------------ */
    // As linhas (de quem saiu do lugar até o ponto de verdade) ficam no
    // painel de baixo do Leaflet: nunca passam por cima de um alfinete.
    const camadaPernas = L.layerGroup().addTo(mapa);
    const camadaClientes = L.layerGroup().addTo(mapa);
    const marcadoresCliente = new Map();   // indice -> marcador do cliente
    let desenhados = new Map();            // chave -> marcador na tela
    let grupoDoCliente = new Map();        // indice -> grupo em que está

    function marcadorDoCliente(c) {
        if (marcadoresCliente.has(c.indice)) return marcadoresCliente.get(c.indice);
        const m = criarMarcadorCliente(c, [c.lat, c.lng]);
        marcadoresCliente.set(c.indice, m);
        return m;
    }

    function criarMarcadorCliente(c, posicao) {
        const m = L.marker(posicao, {
            icon: iconeCliente(c),
            riseOnHover: true,
            riseOffset: 1200,
            keyboard: true,
            bubblingMouseEvents: false,
        });
        m._clienteLS = c;
        configurarMarcador(m, {
            popup: criarPopupCliente(c),
            tooltip: criarTooltip(c),
            alturaPino: PINO_CLIENTE.altura,
            rotulo: `Ver informações de ${c.nome || 'cliente Lazer & Sport'}`,
        });
        return m;
    }

    function criarMarcadorGrupo(grupo) {
        const n = grupo.membros.length;
        const m = L.marker(grupo.posicao || [grupo.ancora.lat, grupo.ancora.lng], {
            icon: iconeGrupo(n),
            zIndexOffset: 500,
            keyboard: true,
            bubblingMouseEvents: false,
        });
        m._grupoLS = grupo;
        configurarMarcador(m, {
            zIndexBase: 500,
            alturaPino: PINO_CLIENTE.altura,
            rotulo: `${n} clientes aqui. Aproximar para ver cada um`,
            aoClicar: () => abrirGrupo(m._grupoLS.membros, { marcador: m }),
        });
        if (dispositivoComHover) {
            m.bindTooltip(`${n} clientes aqui — clique para ver cada um`, {
                direction: 'top',
                className: 'grupo-tooltip',
                offset: L.point(0, -PINO_CLIENTE.altura + 2),
            });
        }
        return m;
    }

    function chaveDoGrupo(g) {
        if (g.membros.length === 1) return `c${g.ancora.indice}`;
        return `g${g.ancora.indice}:` + g.membros.map((c) => c.indice).sort((a, b) => a - b).join(',');
    }

    // A linha fininha do ponto de verdade até a ponta do alfinete que saiu
    // do lugar, com uma bolinha no ponto: dá para ver onde é cada um.
    function desenharPerna(c, posicao) {
        const real = L.latLng(c.lat, c.lng);
        L.polyline([real, posicao], {
            className: 'mapa-perna',
            color: '#004AAD',
            weight: 1.6,
            opacity: 0.85,
            interactive: false,
        }).addTo(camadaPernas);
        L.circleMarker(real, {
            className: 'mapa-perna-ponto',
            radius: 3.5,
            color: '#ffffff',
            weight: 1.5,
            fillColor: '#004AAD',
            fillOpacity: 1,
            interactive: false,
        }).addTo(camadaPernas);
    }

    function desenhar() {
        fecharLeque();
        const { grupos, debaixoDaFabrica } = montar(mapa.getZoom());
        const novos = new Map();
        grupoDoCliente = new Map();
        camadaPernas.clearLayers();

        for (const g of grupos) {
            const chave = chaveDoGrupo(g);
            const sozinho = g.membros.length === 1;
            let m = desenhados.get(chave);
            if (!m) m = sozinho ? marcadorDoCliente(g.ancora) : criarMarcadorGrupo(g);
            if (m._grupoLS) m._grupoLS = g;
            if (!m.getLatLng().equals(g.posicao)) m.setLatLng(g.posicao);
            novos.set(chave, m);
            g.membros.forEach((c) => grupoDoCliente.set(c.indice, { grupo: g, marcador: m }));
            if (sozinho && g.deslocado) desenharPerna(g.ancora, g.posicao);
        }

        for (const [chave, m] of desenhados) {
            if (novos.has(chave)) continue;
            if (m === marcadorPopupFixado) fecharPopups();
            camadaClientes.removeLayer(m);
        }
        for (const m of novos.values()) {
            if (!camadaClientes.hasLayer(m)) camadaClientes.addLayer(m);
        }
        desenhados = novos;

        atualizarFabrica(debaixoDaFabrica);
    }

    /* ------------------------------------------------------------------
       A fábrica (com o selo "+N" dos clientes que ela cobre)
       ------------------------------------------------------------------ */
    let marcadorFabrica = null;
    let escondidosNaFabrica = [];

    if (fabrica) {
        marcadorFabrica = L.marker([fabrica.lat, fabrica.lng], {
            icon: iconeFabrica(0),
            zIndexOffset: 2000,
            keyboard: true,
            bubblingMouseEvents: false,
        });
        configurarMarcador(marcadorFabrica, {
            zIndexBase: 2000,
            popup: criarPopupFabrica(fabrica),
            tooltip: criarTooltip(fabrica, true),
            alturaPino: PINO_FABRICA.altura,
            rotulo: `Ver informações de ${fabrica.nome || 'Lazer & Sport Brinquedos'}`,
            aoClicar: (e) => {
                const noSelo = e.originalEvent?.target?.closest?.('.pino-selo');
                if (noSelo && escondidosNaFabrica.length) {
                    abrirGrupo(escondidosNaFabrica, { comFabrica: true });
                    return;
                }
                abrirPopup(marcadorFabrica);
            },
        });
    }

    function atualizarFabrica(debaixo) {
        if (!marcadorFabrica) return;
        const antes = escondidosNaFabrica.length;
        escondidosNaFabrica = debaixo;
        if (!estado.fabrica) {
            if (mapa.hasLayer(marcadorFabrica)) {
                if (marcadorPopupFixado === marcadorFabrica) fecharPopups();
                mapa.removeLayer(marcadorFabrica);
            }
            return;
        }
        if (antes !== debaixo.length || !mapa.hasLayer(marcadorFabrica)) {
            marcadorFabrica.setIcon(iconeFabrica(debaixo.length));
        }
        if (!mapa.hasLayer(marcadorFabrica)) marcadorFabrica.addTo(mapa);
        const elemento = marcadorFabrica.getElement();
        if (elemento) {
            elemento.setAttribute('aria-label', debaixo.length
                ? `Ver informações da fábrica. Mais ${debaixo.length} cliente${debaixo.length === 1 ? '' : 's'} aqui perto`
                : marcadorFabrica._rotuloLS);
        }
    }

    /* ------------------------------------------------------------------
       Abrir um grupo: aproximar só o necessário, ou abrir em leque
       ------------------------------------------------------------------ */
    function abrirGrupo(membros, { comFabrica = false, marcador = null } = {}) {
        fecharPopups();
        const zAtual = mapa.getZoom();
        const zMax = mapa.getMaxZoom();

        // Nem o zoom máximo solta mais nenhum (mesmo endereço): leque.
        const noMaximo = retrato(membros, zMax);
        if (retrato(membros, zAtual) === noMaximo) {
            if (marcador) abrirEmLeque(membros, marcador);
            else if (comFabrica) abrirEmLeque(membros, marcadorFabrica);
            return;
        }

        // O menor zoom que já solta tudo o que dá para soltar.
        let alvo = zMax;
        for (let z = zAtual + 1; z < zMax; z++) {
            if (retrato(membros, z) === noMaximo) {
                alvo = z;
                break;
            }
        }

        const pontos = membros.map((c) => [c.lat, c.lng]);
        if (comFabrica && fabrica) pontos.push([fabrica.lat, fabrica.lng]);
        const limites = L.latLngBounds(pontos);
        const cabe = mapa.getBoundsZoom(limites, false, L.point(80, 140));
        alvo = Math.max(zAtual + 1, Math.min(alvo, cabe));
        mapa.flyTo(limites.getCenter(), Math.min(alvo, zMax), { duration: 0.6 });
    }

    // Leque: os alfinetes de um mesmo ponto se abrem em volta dele, cada um
    // com uma linha até o lugar real. Fecha ao mudar o zoom ou clicar fora.
    let leque = null;

    function posicoesDoLeque(n) {
        const posicoes = [];
        if (n <= 5) {
            // arco por cima: os alfinetes crescem para cima e não cobrem o ponto
            const inicio = (200 * Math.PI) / 180;
            const fim = (340 * Math.PI) / 180;
            const passo = n > 1 ? (fim - inicio) / (n - 1) : 0;
            const raio = Math.max(42, n > 1 ? 44 / passo : 42);
            for (let k = 0; k < n; k++) {
                const ang = n > 1 ? inicio + passo * k : (270 * Math.PI) / 180;
                posicoes.push(L.point(Math.cos(ang) * raio, Math.sin(ang) * raio));
            }
            return posicoes;
        }
        const raio = Math.max(56, (44 * n) / (2 * Math.PI));
        for (let k = 0; k < n; k++) {
            const ang = -Math.PI / 2 + (2 * Math.PI * k) / n;
            posicoes.push(L.point(Math.cos(ang) * raio, Math.sin(ang) * raio));
        }
        return posicoes;
    }

    function abrirEmLeque(membros, marcadorOrigem) {
        fecharLeque();
        const camada = L.layerGroup().addTo(mapa);
        const real = L.latLng(membros[0].lat, membros[0].lng);
        const centro = mapa.latLngToLayerPoint(real);
        const posicoes = posicoesDoLeque(membros.length);
        const pinos = new Map();

        membros.forEach((c, k) => {
            const destino = mapa.layerPointToLatLng(centro.add(posicoes[k]));
            L.polyline([[c.lat, c.lng], destino], {
                className: 'leque-perna',
                color: '#7db8ff',
                weight: 2,
                opacity: 0.95,
                interactive: false,
            }).addTo(camada);
            const m = criarMarcadorCliente(c, destino);
            m.setZIndexOffset(3000);
            m._zIndexBaseLS = 3000;
            camada.addLayer(m);
            pinos.set(c.indice, m);
        });
        L.circleMarker(real, {
            radius: 5,
            color: '#ffffff',
            weight: 2,
            fillColor: '#0878F9',
            fillOpacity: 1,
            interactive: false,
        }).addTo(camada);

        // O alfinete do grupo sai enquanto o leque está aberto (e leva junto o
        // cartãozinho "2 clientes aqui"); a fábrica fica.
        if (marcadorOrigem && marcadorOrigem !== marcadorFabrica) {
            marcadorOrigem.closeTooltip();
            camadaClientes.removeLayer(marcadorOrigem);
        }
        leque = { camada, pinos, marcadorOrigem };
        return pinos;
    }

    function fecharLeque() {
        if (!leque) return;
        if ([...leque.pinos.values()].includes(marcadorPopupFixado)) fecharPopups();
        mapa.removeLayer(leque.camada);
        const origem = leque.marcadorOrigem;
        if (origem && origem !== marcadorFabrica && [...desenhados.values()].includes(origem)) {
            camadaClientes.addLayer(origem);
        }
        leque = null;
    }

    mapa.on('zoomstart', fecharLeque);
    // A distância visual entre os pinos só muda com o zoom. Redesenhar ao
    // arrastar fecharia o cartão logo depois do autoPan no celular.
    mapa.on('zoomend', desenhar);
    mapa.on('click', () => {
        sequenciaVoo += 1;
        fecharPopups();
        fecharLeque();
    });

    /* ------------------------------------------------------------------
       Enquadramento
       ------------------------------------------------------------------ */
    function enquadrar({ animar = false } = {}) {
        const pontos = clientesVisiveis().map((c) => [c.lat, c.lng]);
        const soCidade = estado.cidade !== 'todas' && pontos.length;
        if (fabrica && estado.fabrica && !soCidade) pontos.push([fabrica.lat, fabrica.lng]);

        if (!pontos.length) {
            mapa.setView(CENTRO_DO_BRASIL, 4, { animate: animar });
            return;
        }
        if (pontos.length === 1) {
            const sozinha = fabrica && pontos[0][0] === fabrica.lat && pontos[0][1] === fabrica.lng;
            mapa.setView(pontos[0], sozinha ? ZOOM_DA_FABRICA - 1 : 13, { animate: animar });
            return;
        }
        // Folga em pixels: em cima cabe a altura do alfinete e a dica.
        mapa.fitBounds(L.latLngBounds(pontos), {
            paddingTopLeft: L.point(36, dispositivoCompacto ? 96 : 104),
            paddingBottomRight: L.point(36, 28),
            maxZoom: 13,
            animate: animar,
        });
    }

    // "Mostrar tudo", embaixo do + e do −.
    const ControleTudo = L.Control.extend({
        options: { position: 'topleft' },
        onAdd() {
            const barra = L.DomUtil.create('div', 'leaflet-bar ls-onde-controle-tudo');
            const botao = L.DomUtil.create('a', '', barra);
            botao.href = '#';
            botao.setAttribute('role', 'button');
            botao.title = 'Mostrar tudo';
            botao.setAttribute('aria-label', 'Mostrar todos os pontos no mapa');
            botao.innerHTML = '<i class="fa-solid fa-expand" aria-hidden="true"></i>';
            L.DomEvent.disableClickPropagation(barra);
            L.DomEvent.on(botao, 'click', (e) => {
                L.DomEvent.preventDefault(e);
                fecharPopups();
                enquadrar({ animar: true });
            });
            return barra;
        },
    });
    new ControleTudo().addTo(mapa);

    /* ------------------------------------------------------------------
       Camadas, filtro por cidade e lista
       ------------------------------------------------------------------ */
    const contagens = secao.querySelectorAll('[data-onde-contagem]');
    const botoesCamada = secao.querySelectorAll('[data-onde-camada]');
    const filtro = document.getElementById('filtro-cidade-cliente');
    const botoesLista = [...secao.querySelectorAll('button[data-onde-cliente]')];
    const lista = secao.querySelector('.ls-onde-lista');

    function atualizarContagens() {
        const n = clientesVisiveisNoFiltro().length;
        contagens.forEach((el) => { el.textContent = String(n); });
        const contador = document.getElementById('clientes-contador');
        if (contador) {
            contador.innerHTML = `<strong data-onde-contagem>${n}</strong> cliente${n === 1 ? '' : 's'}`;
        }
    }

    function clientesVisiveisNoFiltro() {
        return estado.cidade === 'todas' ? clientes : clientes.filter((c) => c.cidade === estado.cidade);
    }

    function atualizarLista() {
        botoesLista.forEach((botao) => {
            const c = clientePorIndice.get(Number(botao.dataset.ondeCliente));
            const item = botao.closest('li');
            if (!item) return;
            const visivel = Boolean(c) && (estado.cidade === 'todas' || c.cidade === estado.cidade);
            item.hidden = !visivel;
            botao.disabled = !c;
        });
        lista?.classList.toggle('ls-onde-lista--desligada', !estado.clientes);
    }

    function marcarNaLista(c, ativo) {
        if (!c) return;
        const botao = botoesLista.find((b) => Number(b.dataset.ondeCliente) === c.indice);
        if (!botao) return;
        botao.classList.toggle('ls-onde-item--ativo', ativo);
        if (ativo) botao.setAttribute('aria-current', 'true');
        else botao.removeAttribute('aria-current');
        // Rola só a lista (nunca a página) até o nome do cliente aberto.
        if (ativo && lista && lista.scrollHeight > lista.clientHeight) {
            const item = botao.closest('li');
            const topo = item.offsetTop - lista.offsetTop;
            if (topo < lista.scrollTop || topo + item.offsetHeight > lista.scrollTop + lista.clientHeight) {
                lista.scrollTo({ top: Math.max(0, topo - 8), behavior: 'smooth' });
            }
        }
    }

    botoesCamada.forEach((botao) => {
        const camada = botao.dataset.ondeCamada;
        if (camada === 'fabrica' && !fabrica) {
            botao.hidden = true;
            return;
        }
        botao.addEventListener('click', () => {
            estado[camada] = !estado[camada];
            botao.setAttribute('aria-pressed', String(estado[camada]));
            fecharPopups();
            if (camada === 'clientes') atualizarLista();
            desenhar();
        });
    });

    if (filtro) {
        const cidades = [...new Set(clientes.map((c) => c.cidade).filter(Boolean))]
            .sort((a, b) => a.localeCompare(b, 'pt-BR'));
        cidades.forEach((cidade) => {
            const opcao = document.createElement('option');
            opcao.value = cidade;
            opcao.textContent = cidade;
            filtro.appendChild(opcao);
        });
        filtro.addEventListener('change', () => {
            estado.cidade = filtro.value;
            fecharPopups();
            atualizarContagens();
            atualizarLista();
            enquadrar({ animar: true });
            desenhar();
        });
    }

    // Zoom para mostrar um cliente da lista: pelo menos o da cidade
    // (ZOOM_DA_CIDADE), e o menor a partir daí em que ele aparece sozinho.
    // Se ele divide o ponto com outro (mesmo endereço), o zoom em que o
    // grupo dele só tem esses -- e aí o grupo abre em leque.
    const ZOOM_DA_CIDADE = 12;

    function zoomParaVerSozinho(c) {
        const zMax = mapa.getMaxZoom();
        const noMaximo = montar(zMax).grupos.find((gr) => gr.membros.includes(c));
        const juntosNoMaximo = noMaximo ? noMaximo.membros.map((m) => m.indice).join(',') : '';
        for (let z = Math.max(mapa.getZoom(), ZOOM_DA_CIDADE); z <= zMax; z++) {
            const { grupos, debaixoDaFabrica } = montar(z);
            if (debaixoDaFabrica.includes(c)) continue;
            const g = grupos.find((gr) => gr.membros.includes(c));
            if (!g) continue;
            if (g.membros.length === 1) return { zoom: z, sozinho: true };
            if (g.membros.map((m) => m.indice).join(',') === juntosNoMaximo) return { zoom: z, sozinho: false };
        }
        return { zoom: zMax, sozinho: false };
    }

    // Voa até `destino` e roda `acao` quando o voo terminar. O flyTo do Leaflet sempre
    // termina com "moveend" (até quando é interrompido); se outro pedido
    // vier antes (ou um clique no mapa), só o último vale, e um pedido
    // esquecido expira sozinho para não abrir um cartão do nada depois.
    function voarE(destino, zoom, opcoes, acao) {
        mapa.stop();   // termina antes o movimento que ainda estiver andando
        const token = ++sequenciaVoo;
        let expirou = false;
        const concluir = () => {
            if (expirou || token !== sequenciaVoo) return;
            // "moveend" de um movimento anterior (um enquadrar ainda em curso):
            // espera o do voo pedido.
            if (mapa.getZoom() !== zoom) {
                mapa.once('moveend', concluir);
                return;
            }
            window.clearTimeout(expira);
            acao();
        };
        const expira = window.setTimeout(() => {
            expirou = true;
            mapa.off('moveend', concluir);
        }, 6000);
        mapa.once('moveend', concluir);
        mapa.flyTo(destino, zoom, opcoes);
    }

    function levarAoMapa() {
        // No celular a lista fica embaixo do mapa: sobe até ele primeiro.
        const moldura = caixa.closest('.ls-onde-moldura') || caixa;
        const r = moldura.getBoundingClientRect();
        if (r.top < 0 || r.bottom > window.innerHeight) {
            moldura.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function focarCliente(c) {
        if (!c) return;
        fecharPopups();
        fecharLeque();
        if (!estado.clientes) {
            estado.clientes = true;
            secao.querySelector('[data-onde-camada="clientes"]')?.setAttribute('aria-pressed', 'true');
            atualizarLista();
            desenhar();
        }
        levarAoMapa();
        const { zoom, sozinho } = zoomParaVerSozinho(c);
        const abrirDepois = () => {
            if (sozinho) {
                const m = marcadoresCliente.get(c.indice);
                if (m && mapa.hasLayer(m)) abrirPopup(m);
                return;
            }
            const info = grupoDoCliente.get(c.indice);
            const pinos = info
                ? abrirEmLeque(info.grupo.membros, info.marcador)
                : (escondidosNaFabrica.includes(c) ? abrirEmLeque(escondidosNaFabrica, marcadorFabrica) : null);
            if (!pinos) return;
            const m = pinos.get(c.indice);
            if (m) abrirPopup(m);
        };
        const destino = L.latLng(c.lat, c.lng);
        if (zoom === mapa.getZoom() && mapa.getBounds().pad(-0.15).contains(destino)) {
            abrirDepois();
            return;
        }
        voarE(destino, zoom, { duration: 0.7 }, abrirDepois);
    }

    botoesLista.forEach((botao) => {
        botao.addEventListener('click', () => focarCliente(clientePorIndice.get(Number(botao.dataset.ondeCliente))));
        if (dispositivoComHover) {
            botao.addEventListener('mouseenter', () => {
                const m = marcadoresCliente.get(Number(botao.dataset.ondeCliente));
                if (m && mapa.hasLayer(m)) elevar(m, true);
            });
            botao.addEventListener('mouseleave', () => {
                const m = marcadoresCliente.get(Number(botao.dataset.ondeCliente));
                if (m) elevar(m, false);
            });
        }
    });

    // "Ver no mapa", no cartão da fábrica: até a rua, como no mapa do Google.
    const verFabrica = secao.querySelector('[data-onde-ver-fabrica]');
    if (verFabrica && fabrica && marcadorFabrica) {
        verFabrica.hidden = false;
        verFabrica.addEventListener('click', () => {
            fecharPopups();
            fecharLeque();
            if (!estado.fabrica) {
                estado.fabrica = true;
                secao.querySelector('[data-onde-camada="fabrica"]')?.setAttribute('aria-pressed', 'true');
                desenhar();
            }
            levarAoMapa();
            voarE([fabrica.lat, fabrica.lng], ZOOM_DA_FABRICA, { duration: 0.8 }, () => {
                if (mapa.hasLayer(marcadorFabrica)) abrirPopup(marcadorFabrica);
            });
        });
    }

    /* ------------------------------------------------------------------
       Primeira pintura
       ------------------------------------------------------------------ */
    atualizarContagens();
    atualizarLista();
    enquadrar();
    desenhar();
})();
