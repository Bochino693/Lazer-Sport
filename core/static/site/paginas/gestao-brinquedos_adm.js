/* Brinquedos (painel): a lista em cartões, os filtros e o cadastro.
 * Ver o comentário do topo de gestao/brinquedos_adm.html.
 *
 * Roda a cada vez que a tela chega -- inclusive quando um filtro troca a
 * lista sem recarregar a página: o arquivo mora no bloco de scripts, que a
 * navegação suave recria. Por isso nada aqui se pendura no `document`: os
 * ouvintes ficam nos próprios elementos da tela, que saem junto com ela.
 */
(function () {
    'use strict';

    const form = document.getElementById('toyForm');
    if (!form) return;

    const TIPOS = ['perfil', 'verso', 'lado_direito', 'lado_esquerdo'];
    const ROTULOS = {
        perfil: 'Perfil / Frente',
        verso: 'Verso / Costas',
        lado_direito: 'Lado direito',
        lado_esquerdo: 'Lado esquerdo',
    };
    const MAX = 3;
    const MAX_BYTES = 15 * 1024 * 1024;

    let brinquedos = [];
    try {
        brinquedos = JSON.parse(document.getElementById('toysAdminData')?.textContent || '[]') || [];
    } catch (erro) {
        brinquedos = [];
    }

    const $ = (id) => document.getElementById(id);
    const toyDialog = $('toyDialog');
    const deleteDialog = $('deleteDialog');
    const categoryDialog = $('categoryDialog');
    const tagDialog = $('tagDialog');
    const lightbox = $('lightbox');
    const deleteForm = $('deleteForm');

    function semAcento(texto) {
        return String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
    }

    function reais(numero) {
        return Number(numero).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // "18000", "18.000", "18.000,50", "R$ 1.234,56": a mesma leitura do painel.
    function numeroDoCampo(texto) {
        if (window.Painel && typeof window.Painel.valorNumerico === 'function') {
            return window.Painel.valorNumerico(texto);
        }
        let limpo = String(texto || '').replace(/[^\d.,]/g, '');
        if (!limpo) return null;
        if (limpo.indexOf(',') >= 0) limpo = limpo.replace(/\./g, '').replace(',', '.');
        else if ((limpo.match(/\./g) || []).length > 1 || /^[1-9]\d{0,2}\.\d{3}$/.test(limpo)) limpo = limpo.replace(/\./g, '');
        const n = Number(limpo);
        return Number.isFinite(n) ? n : null;
    }

    /* ------------------------------------------------------------------
       A LISTA: foto que não carrega e o "ver todas" das categorias
       ------------------------------------------------------------------ */
    function semFoto(img) {
        const caixa = img.closest('.bq-foto');
        if (!caixa) return;
        const marca = document.createElement('span');
        marca.className = 'bq-sem-foto';
        marca.innerHTML = '<i class="bi bi-image" aria-hidden="true"></i><small>Foto indisponível</small>';
        img.replaceWith(marca);
    }
    document.querySelectorAll('.bq-foto img').forEach((img) => {
        if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) semFoto(img);
        else img.addEventListener('error', () => semFoto(img), { once: true });
    });

    const cats = document.querySelector('[data-bq-cats]');
    const mais = document.querySelector('[data-bq-mais]');
    if (cats && mais) {
        const total = cats.children.length;
        const ativo = cats.querySelector('.is-on');
        cats.classList.add('is-recolhido');
        const sobra = cats.scrollHeight > cats.clientHeight + 2;
        // A categoria escolhida nunca fica escondida atrás do "ver todas".
        const ativoEscondido = ativo && ativo.offsetTop + ativo.offsetHeight > cats.clientHeight + cats.offsetTop + 2;
        if (!sobra || ativoEscondido) {
            cats.classList.remove('is-recolhido');
        }
        if (sobra) {
            const texto = mais.querySelector('[data-bq-mais-texto]');
            const icone = mais.querySelector('i');
            const pintarMais = () => {
                const aberto = !cats.classList.contains('is-recolhido');
                texto.textContent = aberto ? 'Ver menos' : `Ver todas (${total})`;
                icone.className = aberto ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
                mais.setAttribute('aria-expanded', String(aberto));
            };
            mais.hidden = false;
            pintarMais();
            mais.addEventListener('click', () => {
                cats.classList.toggle('is-recolhido');
                pintarMais();
            });
        }
    }

    /* ------------------------------------------------------------------
       AS JANELAS (<dialog>)

       Esc fecha só a janela de cima (é do próprio <dialog>). Clicar fora
       fecha só as janelas descartáveis -- nova categoria, nova tag, foto
       inteira. O cadastro e a exclusão pedem Cancelar ou o x: um clique
       torto não pode apagar o que foi digitado.
       ------------------------------------------------------------------ */
    function abrir(janela) {
        if (!janela) return;
        if (typeof janela.showModal === 'function') {
            if (!janela.open) janela.showModal();
        } else {
            janela.setAttribute('open', '');
        }
    }

    function fechar(janela) {
        if (!janela) return;
        if (typeof janela.close === 'function') janela.close();
        else janela.removeAttribute('open');
    }

    document.querySelectorAll('dialog[data-close-backdrop]').forEach((janela) => {
        janela.addEventListener('click', (e) => {
            if (e.target === janela) fechar(janela);
        });
    });

    /* ------------------------------------------------------------------
       ERROS NO TOPO DO CADASTRO
       ------------------------------------------------------------------ */
    function erro(texto) {
        const caixa = $('toyError');
        $('toyErrorText').textContent = texto || '';
        caixa.hidden = !texto;
        if (texto) caixa.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    /* ------------------------------------------------------------------
       AS FOTOS: quatro vistas, no máximo três, PERFIL obrigatória
       ------------------------------------------------------------------ */
    let salvas = {};   // tipo -> foto já gravada no servidor
    const previas = {}; // tipo -> endereço temporário da foto recém-escolhida

    const entrada = (tipo) => $('img-' + tipo);
    const marcador = (tipo) => $('flag-' + tipo);
    const slot = (tipo) => form.querySelector(`[data-slot="${tipo}"]`);

    function arquivo(tipo) {
        const el = entrada(tipo);
        return el.files && el.files.length ? el.files[0] : null;
    }

    function removida(tipo) {
        return marcador(tipo).checked && !arquivo(tipo);
    }

    function ativa(tipo) {
        return Boolean(arquivo(tipo)) || (Boolean(salvas[tipo]) && !removida(tipo));
    }

    function ativas() {
        return TIPOS.filter(ativa);
    }

    function descartarPrevia(tipo) {
        if (previas[tipo]) {
            URL.revokeObjectURL(previas[tipo]);
            delete previas[tipo];
        }
    }

    function origem(tipo) {
        const f = arquivo(tipo);
        if (f) {
            if (!previas[tipo]) previas[tipo] = URL.createObjectURL(f);
            return previas[tipo];
        }
        if (removida(tipo)) return '';
        return salvas[tipo] ? salvas[tipo].url : '';
    }

    function pintarFotos() {
        const lista = ativas();
        const cheio = lista.length >= MAX;

        TIPOS.forEach((tipo) => {
            const caixa = slot(tipo);
            const img = $('prev-' + tipo);
            const quadro = caixa.querySelector(`[data-preview="${tipo}"]`);
            const marca = caixa.querySelector(`[data-flag="${tipo}"]`);
            const botao = caixa.querySelector(`[data-remove="${tipo}"]`);
            const rotulo = caixa.querySelector(`[data-pick-label="${tipo}"]`);
            const src = origem(tipo);
            const nova = Boolean(arquivo(tipo));
            const apagando = removida(tipo);
            const bloqueada = !src && cheio;

            caixa.classList.toggle('is-ativa', Boolean(src));
            caixa.classList.toggle('is-removida', apagando);
            // Bloqueado bloqueia de verdade: o arquivo nem chega a ser escolhido.
            caixa.classList.toggle('is-bloqueada', bloqueada);
            entrada(tipo).disabled = bloqueada;

            if (img.getAttribute('src') !== src) quadro.classList.remove('is-quebrada');
            if (src) img.src = src;
            else img.removeAttribute('src');
            img.alt = src ? ROTULOS[tipo] : '';
            quadro.classList.toggle('is-zoom', Boolean(src));
            quadro.tabIndex = src ? 0 : -1;

            if (nova) {
                marca.hidden = false;
                marca.textContent = 'Nova';
                marca.classList.remove('is-aviso');
            } else if (apagando) {
                marca.hidden = false;
                marca.textContent = 'Será removida';
                marca.classList.add('is-aviso');
            } else {
                marca.hidden = true;
            }

            rotulo.textContent = src && !apagando ? 'Trocar' : 'Escolher';

            // Um botão só para os dois enganos: desfazer o arquivo escolhido
            // e desistir de remover a foto que já estava lá.
            botao.classList.remove('is-desfazer');
            if (nova) {
                botao.hidden = false;
                botao.textContent = 'Descartar';
            } else if (apagando) {
                botao.hidden = false;
                botao.textContent = 'Manter foto';
                botao.classList.add('is-desfazer');
            } else if (salvas[tipo]) {
                botao.hidden = false;
                botao.textContent = 'Remover';
            } else {
                botao.hidden = true;
            }
        });

        $('imgCount').textContent = lista.length;
        const contador = $('imgCounter');
        const texto = contador.querySelector('span');
        const temPerfil = lista.includes('perfil');
        contador.classList.toggle('is-erro', !temPerfil || lista.length > MAX);
        texto.textContent = !temPerfil
            ? 'Falta a PERFIL / FRENTE: ela é obrigatória e vira a capa.'
            : cheio
                ? 'Limite de 3 fotos. Remova uma para trocar de ângulo.'
                : 'PERFIL é a capa. Dá para pôr mais ' + (MAX - lista.length) + (MAX - lista.length === 1 ? ' vista.' : ' vistas.');
    }

    function zerarFotos(brinquedo) {
        TIPOS.forEach((tipo) => {
            descartarPrevia(tipo);
            entrada(tipo).value = '';
            entrada(tipo).disabled = false;
            marcador(tipo).checked = false;
        });
        salvas = {};
        if (brinquedo && Array.isArray(brinquedo.imagens)) {
            brinquedo.imagens.forEach((foto) => {
                if (foto && foto.tipo && foto.url) salvas[foto.tipo] = foto;
            });
        }
        // Brinquedo de antes das fotos com tipo: a capa antiga entra como
        // PERFIL, para o quadro não aparecer vazio.
        if (brinquedo && !salvas.perfil && brinquedo.imagem_url) {
            salvas.perfil = { tipo: 'perfil', url: brinquedo.imagem_url };
        }
        pintarFotos();
    }

    function conferirArquivo(tipo) {
        const f = arquivo(tipo);
        if (f && !String(f.type || '').startsWith('image/')) {
            entrada(tipo).value = '';
            erro(`O arquivo escolhido para ${ROTULOS[tipo]} não é uma imagem.`);
        } else if (f && f.size > MAX_BYTES) {
            entrada(tipo).value = '';
            erro(`Cada foto pode ter até 15 MB. ${ROTULOS[tipo]} tem ${(f.size / 1048576).toFixed(1)} MB.`);
        } else {
            erro('');
        }
    }

    TIPOS.forEach((tipo) => {
        const caixa = slot(tipo);
        entrada(tipo).addEventListener('change', () => {
            descartarPrevia(tipo);
            marcador(tipo).checked = false;
            conferirArquivo(tipo);
            pintarFotos();
        });

        caixa.querySelector(`[data-remove="${tipo}"]`).addEventListener('click', () => {
            if (arquivo(tipo)) {
                // Desfaz só a escolha nova; a foto já gravada continua.
                descartarPrevia(tipo);
                entrada(tipo).value = '';
                marcador(tipo).checked = false;
            } else {
                marcador(tipo).checked = !marcador(tipo).checked;
            }
            erro('');
            pintarFotos();
        });

        const quadro = caixa.querySelector(`[data-preview="${tipo}"]`);
        // Foto gravada que não abre (arquivo que sumiu do armazenamento):
        // o quadro diz isso, em vez de mostrar o ícone de imagem quebrada.
        $('prev-' + tipo).addEventListener('error', () => {
            if ($('prev-' + tipo).getAttribute('src')) quadro.classList.add('is-quebrada');
        });
        const verInteira = () => {
            const src = origem(tipo);
            if (!src) return;
            $('lightboxImg').src = src;
            $('lightboxImg').alt = ROTULOS[tipo];
            $('lightboxCaption').textContent = ROTULOS[tipo];
            abrir(lightbox);
        };
        quadro.addEventListener('click', verInteira);
        quadro.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                verInteira();
            }
        });

        // Arrastar um arquivo do computador para cima do quadro.
        caixa.addEventListener('dragover', (e) => {
            if (entrada(tipo).disabled || !e.dataTransfer || ![...e.dataTransfer.types].includes('Files')) return;
            e.preventDefault();
            caixa.classList.add('is-arrastando');
        });
        caixa.addEventListener('dragleave', () => caixa.classList.remove('is-arrastando'));
        caixa.addEventListener('drop', (e) => {
            caixa.classList.remove('is-arrastando');
            if (entrada(tipo).disabled || !e.dataTransfer || !e.dataTransfer.files.length) return;
            e.preventDefault();
            try {
                const lote = new DataTransfer();
                lote.items.add(e.dataTransfer.files[0]);
                entrada(tipo).files = lote.files;
                entrada(tipo).dispatchEvent(new Event('change'));
            } catch (falha) { /* navegador sem DataTransfer: fica o botão */ }
        });
    });

    $('closeLightbox').addEventListener('click', () => fechar(lightbox));

    /* ------------------------------------------------------------------
       O OBJETO 3D: o arquivo atual e as cores de dentro dele
       ------------------------------------------------------------------ */
    const caixa3d = form.querySelector('[data-objeto3d]');
    const entrada3d = $('toyModel');

    function mostrarObjeto3d(brinquedo) {
        const objeto = brinquedo && brinquedo.objeto_3d;
        caixa3d.querySelector('[data-objeto3d-atual]').hidden = !objeto;
        caixa3d.querySelector('[data-objeto3d-vazio]').hidden = Boolean(objeto);
        caixa3d.querySelector('[data-objeto3d-remover]').hidden = !objeto;
        caixa3d.querySelector('[data-objeto3d-rotulo]').textContent = objeto ? 'Trocar .glb' : 'Escolher .glb';
        if (objeto) {
            caixa3d.querySelector('[data-objeto3d-nome]').textContent = objeto.arquivo;
            const medidas = (objeto.medidas || []).length === 3
                ? 'Tamanho: ' + objeto.medidas.map((v) => String(v).replace('.', ',')).join(' × ') + ' m (A × L × P) · '
                : '';
            caixa3d.querySelector('[data-objeto3d-cores]').textContent = medidas + ((objeto.cores || []).length
                ? 'Cores: ' + objeto.cores.join(', ')
                : 'Cores: os tons da adesivagem (o arquivo não traz variações)');
        }
    }

    entrada3d.addEventListener('change', () => {
        const f = entrada3d.files && entrada3d.files[0];
        if (f) caixa3d.querySelector('[data-objeto3d-rotulo]').textContent = f.name;
    });

    /* ------------------------------------------------------------------
       CATEGORIAS E TAGS: filtrar, contar, limpar
       ------------------------------------------------------------------ */
    const barras = [...form.querySelectorAll('[data-options-tools]')];

    function contarTudo() {
        barras.forEach((barra) => barra.atualizarContador && barra.atualizarContador());
    }

    barras.forEach((barra) => {
        const grade = $(barra.dataset.optionsTools);
        const busca = barra.querySelector('input[type="search"]');
        const contador = barra.querySelector('.selected-count');
        const limpar = barra.querySelector('.clear-options');
        function atualizar() {
            const marcadas = grade.querySelectorAll('input[type="checkbox"]:checked').length;
            contador.textContent = marcadas + (marcadas === 1 ? ' selecionada' : ' selecionadas');
        }
        busca.addEventListener('input', () => {
            const termo = semAcento(busca.value);
            grade.querySelectorAll('.bq-opcao').forEach((opcao) => {
                opcao.hidden = Boolean(termo) && !semAcento(opcao.textContent).includes(termo);
            });
        });
        // Enter no filtro não envia o cadastro.
        busca.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') e.preventDefault();
        });
        limpar.addEventListener('click', () => {
            grade.querySelectorAll('input[type="checkbox"]').forEach((caixa) => { caixa.checked = false; });
            atualizar();
        });
        grade.addEventListener('change', atualizar);
        barra.atualizarContador = atualizar;
        atualizar();
    });

    function marcar(nome, ids) {
        const alvo = (ids || []).map(Number);
        form.querySelectorAll(`input[name="${nome}"]`).forEach((caixa) => {
            caixa.checked = alvo.includes(Number(caixa.value));
        });
        contarTudo();
    }

    function limparFiltrosDasOpcoes() {
        barras.forEach((barra) => {
            const busca = barra.querySelector('input[type="search"]');
            busca.value = '';
            busca.dispatchEvent(new Event('input'));
        });
    }

    /* ------------------------------------------------------------------
       A VOLTAGEM: chips. "Não se aplica" grava vazio (o site esconde a
       linha). Um valor antigo fora da lista ("110") vira um chip a mais,
       já marcado, para salvar sem mexer não trocar o que estava gravado.
       ------------------------------------------------------------------ */
    const voltagens = form.querySelector('[data-bq-voltagens]');

    function marcarVoltagem(valor, editando) {
        voltagens.querySelectorAll('[data-bq-voltagem-antiga]').forEach((el) => el.remove());
        const radios = [...voltagens.querySelectorAll('input[name="voltz"]')];
        radios.forEach((r) => { r.checked = false; });
        if (!editando) return;
        const texto = String(valor || '').trim();
        if (!texto) {
            const nenhuma = voltagens.querySelector('[data-bq-sem-voltagem]');
            if (nenhuma) nenhuma.checked = true;
            return;
        }
        const igual = radios.find((r) => r.value && r.value.toLowerCase() === texto.toLowerCase());
        if (igual) {
            igual.checked = true;
            return;
        }
        const chip = document.createElement('label');
        chip.className = 'bq-opcao';
        chip.dataset.bqVoltagemAntiga = '1';
        chip.title = 'Voltagem gravada antes, fora da lista';
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'voltz';
        radio.value = texto;
        radio.checked = true;
        radio.dataset.rotulo = 'Voltagem';
        const nome = document.createElement('span');
        nome.textContent = texto;
        chip.append(radio, nome);
        voltagens.prepend(chip);
    }

    /* ------------------------------------------------------------------
       PREÇO, LOJA E DESCRIÇÃO: o recado ao lado do campo
       ------------------------------------------------------------------ */
    const preco = $('toyPrice');
    const loja = $('toyStore');
    const precoAjuda = form.querySelector('[data-bq-preco-ajuda]');
    const lojaAjuda = form.querySelector('[data-bq-loja-ajuda]');
    const descricao = $('toyDescription');
    const descricaoConta = form.querySelector('[data-bq-desc-conta]');

    function pintarPreco() {
        const valor = numeroDoCampo(preco.value);
        precoAjuda.classList.remove('is-bom', 'is-aviso');
        if (!preco.value.trim()) {
            precoAjuda.textContent = 'Em reais: 6990 vira R$ 6.990,00. Em branco, o site mostra “Sob consulta”.';
        } else if (valor === null) {
            precoAjuda.textContent = 'Use só números: 6990 ou 6.990,00.';
            precoAjuda.classList.add('is-aviso');
        } else {
            precoAjuda.textContent = `Vai aparecer: R$ ${reais(valor)}.`;
            precoAjuda.classList.add('is-bom');
        }
        const semPreco = !(valor > 0);
        lojaAjuda.classList.toggle('is-aviso', loja.checked && semPreco);
        lojaAjuda.textContent = loja.checked
            ? (semPreco
                ? 'Sem preço, a loja não põe à venda: o brinquedo só aparece no catálogo, sob orçamento.'
                : 'Aparece na loja, à venda, com o preço acima.')
            : 'A loja só põe à venda o que tem preço. Desligado, o brinquedo fica no catálogo, sob orçamento.';
    }

    function pintarDescricao() {
        descricaoConta.textContent = descricao.value.length;
    }

    preco.addEventListener('input', pintarPreco);
    preco.addEventListener('blur', () => window.setTimeout(pintarPreco, 0));
    loja.addEventListener('change', pintarPreco);
    descricao.addEventListener('input', pintarDescricao);

    /* ------------------------------------------------------------------
       ABRIR O CADASTRO (novo ou editar)
       ------------------------------------------------------------------ */
    let sujo = false;
    form.addEventListener('input', () => { sujo = true; });
    form.addEventListener('change', () => { sujo = true; });

    function valor(id, v) {
        if (window.Painel && typeof window.Painel.valor === 'function') window.Painel.valor(id, v);
        else $(id).value = v === null || v === undefined ? '' : v;
    }

    function travar(on) {
        toyDialog.classList.toggle('is-salvando', on);
        const salvar = $('submitToy');
        salvar.disabled = on;
        salvar.querySelector('span').textContent = on ? 'Salvando...' : 'Salvar brinquedo';
        $('cancelToy').disabled = on;
        $('closeToy').disabled = on;
    }

    function limparInvalidos() {
        form.querySelectorAll('[aria-invalid="true"]').forEach((el) => el.removeAttribute('aria-invalid'));
        voltagens.classList.remove('is-invalida');
    }

    function abrirBrinquedo(id) {
        form.reset();
        erro('');
        travar(false);
        limparInvalidos();
        limparFiltrosDasOpcoes();

        const brinquedo = id ? brinquedos.find((x) => Number(x.id) === Number(id)) || null : null;

        valor('toyId', brinquedo ? brinquedo.id : '');
        $('toyTitle').textContent = brinquedo ? 'Editar brinquedo' : 'Cadastrar brinquedo';

        if (brinquedo) {
            valor('toyName', brinquedo.nome_brinquedo);
            valor('toyDescription', brinquedo.descricao);
            valor('toyPrice', brinquedo.valor_brinquedo);
            valor('toyRating', brinquedo.avaliacao);
            valor('toyHeight', brinquedo.altura_m);
            valor('toyWidth', brinquedo.largura_m);
            valor('toyDepth', brinquedo.profundidade_m);
            loja.checked = Boolean(brinquedo.exibir_na_loja);
            marcar('categorias_brinquedos', brinquedo.categorias_ids);
            marcar('tags', brinquedo.tags_ids);
        } else {
            marcar('categorias_brinquedos', []);
            marcar('tags', []);
        }
        marcarVoltagem(brinquedo ? brinquedo.voltz : '', Boolean(brinquedo));

        zerarFotos(brinquedo);
        mostrarObjeto3d(brinquedo);
        pintarAdesivos(brinquedo);
        pintarPreco();
        pintarDescricao();
        form.querySelector('.bq-janela-corpo').scrollTop = 0;
        abrir(toyDialog);
        sujo = false;
        if (!brinquedo && window.matchMedia && window.matchMedia('(hover: hover)').matches) {
            $('toyName').focus();
        }
    }

    /* ------------------------------------------------------------------
       OS ADESIVOS (LEIA-ME 72): o mesmo brinquedo com outra arte, com as
       fotos e o 3D de cada um. Incluir e tirar vão à parte (action
       "adesivo_incluir" / "adesivo_tirar"), e a seção se redesenha com o que
       o servidor devolve.
       ------------------------------------------------------------------ */
    const secaoAdesivos = form.querySelector('[data-adesivos]');
    let brinquedoDosAdesivos = null;

    function escolherArquivo(aceita, aoEscolher) {
        const entrada = document.createElement('input');
        entrada.type = 'file';
        entrada.accept = aceita;
        entrada.addEventListener('change', () => { if (entrada.files[0]) aoEscolher(entrada.files[0]); });
        entrada.click();
    }

    function pintarAdesivos(brinquedo) {
        if (!secaoAdesivos) return;
        brinquedoDosAdesivos = brinquedo;
        const lista = secaoAdesivos.querySelector('[data-adesivos-lista]');
        const adesivos = (brinquedo && brinquedo.adesivos) || [];
        lista.replaceChildren(...adesivos.map((adesivo) => {
            const item = document.createElement('li');
            item.className = 'bq-adesivo' + (adesivo.padrao ? ' is-padrao' : '');
            item.dataset.adesivoId = adesivo.id;
            const topo = document.createElement('div');
            topo.className = 'bq-adesivo-topo';
            const nome = document.createElement('strong');
            nome.textContent = adesivo.nome;
            topo.append(nome);
            if (adesivo.padrao) {
                const selo = document.createElement('span');
                selo.className = 'bq-adesivo-selo';
                selo.textContent = 'Padrão · a capa, o card e a Arena';
                topo.append(selo);
            }
            if (!adesivo.padrao) {
                const tirar = document.createElement('button');
                tirar.type = 'button';
                tirar.className = 'bq-adesivo-tirar';
                tirar.innerHTML = '<i class="bi bi-trash3" aria-hidden="true"></i> Tirar';
                tirar.addEventListener('click', () => tirarAdesivo(adesivo));
                topo.append(tirar);
            }
            item.append(topo);
            // as fotos das posições: cada uma com o botão de incluir ou trocar
            const posicoes = document.createElement('div');
            posicoes.className = 'bq-adesivo-posicoes';
            (adesivo.posicoes || []).forEach((posicao) => {
                const vaga = document.createElement('button');
                vaga.type = 'button';
                vaga.className = 'bq-adesivo-posicao' + (posicao.url ? '' : ' is-vazia');
                vaga.dataset.tipo = posicao.tipo;
                vaga.title = (posicao.url ? 'Trocar a foto: ' : 'Incluir a foto: ') + posicao.rotulo;
                if (posicao.url) {
                    const img = document.createElement('img');
                    img.src = posicao.url;
                    img.alt = `${adesivo.nome}: ${posicao.rotulo}`;
                    img.loading = 'lazy';
                    vaga.append(img);
                } else {
                    vaga.innerHTML = '<i class="bi bi-plus-lg" aria-hidden="true"></i>';
                }
                const rotulo = document.createElement('span');
                rotulo.textContent = posicao.rotulo;
                vaga.append(rotulo);
                vaga.addEventListener('click', () => escolherArquivo('image/*', (foto) => {
                    pedirAdesivo({ action: 'adesivo_posicao', adesivo_id: adesivo.id, tipo: posicao.tipo, foto });
                }));
                posicoes.append(vaga);
            });
            item.append(posicoes);
            // o 3D do adesivo
            const tres = document.createElement('div');
            tres.className = 'bq-adesivo-3d';
            tres.innerHTML = '<i class="bi bi-badge-3d" aria-hidden="true"></i> ';
            tres.append(document.createTextNode(adesivo.arquivo_3d || 'Sem 3D'));
            const trocar3d = document.createElement('button');
            trocar3d.type = 'button';
            trocar3d.className = 'bq-adesivo-trocar3d';
            trocar3d.textContent = adesivo.arquivo_3d ? 'Trocar o .glb' : 'Enviar o .glb';
            trocar3d.addEventListener('click', () => escolherArquivo('.glb,model/gltf-binary', (glb) => {
                pedirAdesivo({ action: 'adesivo_posicao', adesivo_id: adesivo.id, adesivo_3d: glb });
            }));
            tres.append(trocar3d);
            item.append(tres);
            if ((adesivo.outras || []).length) {
                const outras = document.createElement('div');
                outras.className = 'bq-adesivo-fotos';
                adesivo.outras.forEach((foto) => {
                    const img = document.createElement('img');
                    img.src = foto.url;
                    img.alt = adesivo.nome;
                    img.loading = 'lazy';
                    outras.append(img);
                });
                item.append(outras);
            }
            // os recortes para artes (sem fundo): guardados no adesivo, só aqui, para baixar
            if ((adesivo.recortes || []).length) {
                const recortes = document.createElement('details');
                recortes.className = 'bq-adesivo-recortes';
                const titulo = document.createElement('summary');
                titulo.innerHTML = '<i class="bi bi-scissors" aria-hidden="true"></i> ';
                titulo.append(document.createTextNode(
                    `Recortes para artes (${adesivo.recortes.length}) · sem fundo, ficam fora do site`));
                recortes.append(titulo);
                const lista = document.createElement('div');
                lista.className = 'bq-adesivo-recortes-lista';
                adesivo.recortes.forEach((foto) => {
                    const link = document.createElement('a');
                    link.href = foto.url;
                    link.download = foto.arquivo || '';
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.title = `Baixar ${foto.arquivo || 'o recorte'}`;
                    const img = document.createElement('img');
                    img.src = foto.url;
                    img.alt = `${adesivo.nome}: recorte para artes`;
                    img.loading = 'lazy';
                    const baixar = document.createElement('span');
                    baixar.innerHTML = '<i class="bi bi-download" aria-hidden="true"></i> Baixar';
                    link.append(img, baixar);
                    lista.append(link);
                });
                recortes.append(lista);
                item.append(recortes);
            }
            return item;
        }));
        const soPadrao = adesivos.length <= 1;
        secaoAdesivos.querySelector('[data-adesivos-vazio]').hidden = !soPadrao || !brinquedo;
        secaoAdesivos.querySelector('[data-adesivos-salvar]').hidden = Boolean(brinquedo);
        secaoAdesivos.querySelector('[data-adesivos-novo]').hidden = !brinquedo;
        // o nome da arte atual só se pede no primeiro adesivo de fora (o padrão ainda se chama "Padrão")
        const padrao = adesivos.find((a) => a.padrao);
        secaoAdesivos.querySelector('[data-adesivo-padrao]').hidden = !(soPadrao && padrao && padrao.nome === 'Padrão');
        secaoAdesivos.querySelector('[data-adesivo-msg]').textContent = '';
    }

    async function pedirAdesivo(campos) {
        const dados = new FormData();
        dados.append('csrfmiddlewaretoken', form.querySelector('[name=csrfmiddlewaretoken]').value);
        dados.append('id', brinquedoDosAdesivos.id);
        Object.entries(campos).forEach(([k, v]) => {
            if (Array.isArray(v)) v.forEach((x) => dados.append(k, x));
            else if (v !== undefined && v !== null) dados.append(k, v);
        });
        const msg = secaoAdesivos.querySelector('[data-adesivo-msg]');
        msg.textContent = 'Enviando…';
        try {
            const resposta = await fetch(form.getAttribute('action'), {
                method: 'POST', body: dados, credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const json = await resposta.json().catch(() => null);
            if (!resposta.ok || !json || json.status !== 'sucesso') throw new Error((json && json.msg) || 'Não deu certo. Tente de novo.');
            brinquedoDosAdesivos.adesivos = json.adesivos;
            pintarAdesivos(brinquedoDosAdesivos);
            secaoAdesivos.querySelector('[data-adesivo-msg]').textContent = json.msg;
            mudouAdesivos = true;
        } catch (falha) {
            msg.textContent = falha.message;
        }
    }

    let mudouAdesivos = false;

    function tirarAdesivo(adesivo) {
        if (!window.confirm(`Tirar o adesivo ${adesivo.nome}? As fotos dele saem junto.`)) return;
        pedirAdesivo({ action: 'adesivo_tirar', adesivo_id: adesivo.id });
    }

    if (secaoAdesivos) {
        const nome = secaoAdesivos.querySelector('[data-adesivo-nome]');
        const padrao = secaoAdesivos.querySelector('[data-adesivo-padrao]');
        const glb = secaoAdesivos.querySelector('[data-adesivo-3d]');
        const fotos = secaoAdesivos.querySelector('[data-adesivo-fotos]');
        glb.addEventListener('change', () => {
            secaoAdesivos.querySelector('[data-adesivo-3d-rotulo]').textContent = glb.files[0] ? glb.files[0].name : '.glb do adesivo';
        });
        fotos.addEventListener('change', () => {
            secaoAdesivos.querySelector('[data-adesivo-fotos-rotulo]').textContent = fotos.files.length
                ? `${fotos.files.length} foto${fotos.files.length > 1 ? 's' : ''}` : 'Fotos do adesivo';
        });
        secaoAdesivos.querySelector('[data-adesivo-incluir]').addEventListener('click', async () => {
            if (!brinquedoDosAdesivos) return;
            if (!nome.value.trim()) {
                secaoAdesivos.querySelector('[data-adesivo-msg]').textContent = 'Diga o nome do adesivo (ex.: Alienígenas).';
                nome.focus();
                return;
            }
            await pedirAdesivo({
                action: 'adesivo_incluir',
                adesivo_nome: nome.value.trim(),
                adesivo_padrao_nome: padrao.hidden ? '' : padrao.value.trim(),
                adesivo_3d: glb.files[0] || null,
                adesivo_fotos: [...fotos.files],
            });
            nome.value = '';
            glb.value = '';
            fotos.value = '';
            glb.dispatchEvent(new Event('change'));
            fotos.dispatchEvent(new Event('change'));
        });
    }

    function fecharBrinquedo() {
        TIPOS.forEach(descartarPrevia);
        fechar(toyDialog);
        // incluiu ou tirou um adesivo: a lista (o selo "N adesivos") vem de novo
        if (mudouAdesivos) {
            mudouAdesivos = false;
            atualizarLista();
        }
    }

    $('newToy').addEventListener('click', () => abrirBrinquedo(null));
    document.querySelectorAll('[data-edit]').forEach((botao) => {
        botao.addEventListener('click', () => abrirBrinquedo(botao.dataset.edit));
    });
    $('closeToy').addEventListener('click', fecharBrinquedo);
    $('cancelToy').addEventListener('click', fecharBrinquedo);

    // Esc com coisa digitada pergunta antes: era o jeito mais fácil de
    // perder um cadastro inteiro.
    toyDialog.addEventListener('cancel', (e) => {
        if (toyDialog.classList.contains('is-salvando')) {
            e.preventDefault();
            return;
        }
        if (sujo && !window.confirm('Fechar sem salvar? O que foi digitado se perde.')) {
            e.preventDefault();
            return;
        }
        TIPOS.forEach(descartarPrevia);
    });

    /* ------------------------------------------------------------------
       ENVIAR

       Vai por fetch: um erro de validação volta como JSON e aparece no
       topo do cadastro, com tudo o que foi digitado ainda na tela.
       ------------------------------------------------------------------ */
    async function enviar(formulario) {
        // getAttribute, e não formulario.action: o form tem um
        // <input name="action">, e a propriedade devolveria esse campo.
        const resposta = await fetch(formulario.getAttribute('action'), {
            method: 'POST',
            body: new FormData(formulario),
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        });
        let dados = null;
        try {
            dados = await resposta.json();
        } catch (falha) {
            dados = null;
        }
        if (!resposta.ok || !dados || dados.status !== 'sucesso') {
            throw new Error((dados && dados.msg) || 'Não foi possível salvar. Tente de novo em instantes.');
        }
        return dados;
    }

    // Depois de gravar, a lista vem de novo (com o aviso de "salvo" no
    // topo do painel), sem recarregar cabeçalho, menu e fontes.
    function atualizarLista() {
        try {
            if (typeof window.LSAtualizarTela === 'function') {
                const pedido = window.LSAtualizarTela();
                if (pedido && typeof pedido.then === 'function') {
                    pedido.then(null, () => window.location.reload());
                }
                return;
            }
        } catch (falha) { /* cai no recarregar */ }
        window.location.reload();
    }

    function nomeDoCampo(campo) {
        if (campo.dataset && campo.dataset.rotulo) return campo.dataset.rotulo;
        const etiqueta = campo.id && form.querySelector(`label[for="${campo.id}"]`);
        return etiqueta ? etiqueta.textContent.replace('*', '').replace(/\(.*\)/, '').trim() : campo.name;
    }

    function primeiroProblema() {
        for (const campo of form.querySelectorAll('input[required], textarea[required]')) {
            if (campo.type === 'radio') {
                if (!form.querySelector(`input[name="${campo.name}"]:checked`)) {
                    return { campo, texto: `Escolha a ${nomeDoCampo(campo).toLowerCase()}.` };
                }
            } else if (!campo.value.trim()) {
                return { campo, texto: `Preencha o campo ${nomeDoCampo(campo)}.` };
            }
        }
        const nota = numeroDoCampo($('toyRating').value);
        if (nota === null || nota < 0 || nota > 5) {
            return { campo: $('toyRating'), texto: 'A avaliação vai de 0 a 5 (por exemplo, 4,8).' };
        }
        if (preco.value.trim() && numeroDoCampo(preco.value) === null) {
            return { campo: preco, texto: 'O preço não é um número. Use 6990 ou 6.990,00.' };
        }
        return null;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        erro('');
        limparInvalidos();

        const problema = primeiroProblema();
        if (problema) {
            erro(problema.texto);
            if (problema.campo.type === 'radio') {
                voltagens.classList.add('is-invalida');
                voltagens.scrollIntoView({ block: 'center', behavior: 'smooth' });
            } else {
                problema.campo.setAttribute('aria-invalid', 'true');
                problema.campo.scrollIntoView({ block: 'center', behavior: 'smooth' });
                problema.campo.focus({ preventScroll: true });
            }
            return;
        }

        const lista = ativas();
        if (!lista.includes('perfil')) {
            erro('A foto PERFIL / FRENTE é obrigatória: ela é a capa do brinquedo.');
            slot('perfil').scrollIntoView({ block: 'center', behavior: 'smooth' });
            return;
        }
        if (lista.length > MAX) {
            erro('Máximo de 3 fotos. Mantenha a PERFIL e escolha só mais duas vistas.');
            return;
        }

        // O preço sai sempre por extenso ("18.000,00"): digitado "18.000"
        // e Enter sem sair do campo, não pode virar dezoito reais.
        const numero = numeroDoCampo(preco.value);
        if (preco.value.trim() && numero !== null) preco.value = reais(numero);

        travar(true);
        try {
            await enviar(form);
            sujo = false;
            fecharBrinquedo();
            atualizarLista();
        } catch (falha) {
            erro(falha.message);
            travar(false);
        }
    });

    /* ------------------------------------------------------------------
       EXCLUIR: basta digitar o nome (sem acento e sem maiúscula valem);
       o servidor recebe a frase inteira que ele confere.
       ------------------------------------------------------------------ */
    let nomeParaExcluir = '';
    const deleteInput = $('deleteInput');
    const deleteSubmit = $('deleteSubmit');

    document.querySelectorAll('[data-delete]').forEach((botao) => {
        botao.addEventListener('click', () => {
            nomeParaExcluir = botao.dataset.name || '';
            $('deleteId').value = botao.dataset.delete;
            $('deletePhrase').textContent = nomeParaExcluir;
            deleteInput.value = '';
            $('deleteHidden').value = '';
            $('deleteMsg').textContent = '';
            deleteSubmit.disabled = true;
            deleteSubmit.querySelector('span').textContent = 'Excluir';
            abrir(deleteDialog);
            deleteInput.focus();
        });
    });

    $('cancelDelete').addEventListener('click', () => fechar(deleteDialog));

    deleteInput.addEventListener('input', () => {
        const ok = Boolean(nomeParaExcluir) && semAcento(deleteInput.value) === semAcento(nomeParaExcluir);
        deleteSubmit.disabled = !ok;
        $('deleteHidden').value = ok ? 'CONFIRMAR EXCLUSÃO ' + nomeParaExcluir : '';
    });

    deleteForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (deleteSubmit.disabled) return;
        deleteSubmit.disabled = true;
        deleteSubmit.querySelector('span').textContent = 'Excluindo...';
        try {
            await enviar(deleteForm);
            fechar(deleteDialog);
            atualizarLista();
        } catch (falha) {
            $('deleteMsg').textContent = falha.message;
            deleteSubmit.disabled = false;
            deleteSubmit.querySelector('span').textContent = 'Excluir';
        }
    });

    /* ------------------------------------------------------------------
       NOVA CATEGORIA E NOVA TAG, sem fechar o cadastro
       ------------------------------------------------------------------ */
    function anexar(gradeId, nome, id, texto) {
        const grade = $(gradeId);
        grade.querySelectorAll('[data-bq-sem-opcao]').forEach((el) => el.remove());
        const chip = document.createElement('label');
        chip.className = 'bq-opcao';
        const caixa = document.createElement('input');
        caixa.type = 'checkbox';
        caixa.name = nome;
        caixa.value = id;
        caixa.checked = true;
        // Com o atributo, o form.reset() da próxima abertura não desmarca
        // sem motivo a opção recém-criada antes de `marcar` decidir.
        caixa.setAttribute('checked', 'checked');
        const rotulo = document.createElement('span');
        rotulo.textContent = texto;
        chip.append(caixa, rotulo);
        grade.prepend(chip);
        contarTudo();
    }

    async function rapido(formulario, alvoMsg, pronto) {
        const msg = $(alvoMsg);
        msg.textContent = '';
        const botao = formulario.querySelector('button[type="submit"]');
        botao.disabled = true;
        try {
            const resposta = await fetch(formulario.getAttribute('action'), {
                method: 'POST',
                body: new FormData(formulario),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            const dados = await resposta.json();
            if (!resposta.ok || dados.status !== 'sucesso') throw new Error(dados.msg || 'Não foi possível salvar.');
            pronto(dados);
            formulario.reset();
            formulario.querySelectorAll('[data-bq-arquivo-nome]').forEach((el) => { el.textContent = 'Escolher imagem'; });
        } catch (falha) {
            msg.textContent = falha.message || 'Não foi possível salvar.';
        } finally {
            botao.disabled = false;
        }
    }

    $('openCategory').addEventListener('click', () => {
        $('categoryMsg').textContent = '';
        abrir(categoryDialog);
    });
    $('cancelCategory').addEventListener('click', () => fechar(categoryDialog));
    $('openTag').addEventListener('click', () => {
        $('tagMsg').textContent = '';
        abrir(tagDialog);
    });
    $('cancelTag').addEventListener('click', () => fechar(tagDialog));

    categoryDialog.querySelectorAll('.bq-arquivo input[type="file"]').forEach((campo) => {
        campo.addEventListener('change', () => {
            const nome = campo.closest('.bq-arquivo').querySelector('[data-bq-arquivo-nome]');
            nome.textContent = campo.files && campo.files[0] ? campo.files[0].name : 'Escolher imagem';
        });
    });

    $('categoryForm').addEventListener('submit', (e) => {
        e.preventDefault();
        rapido(e.currentTarget, 'categoryMsg', (d) => {
            anexar('categoryGrid', 'categorias_brinquedos', d.id, d.nome);
            fechar(categoryDialog);
        });
    });

    $('tagForm').addEventListener('submit', (e) => {
        e.preventDefault();
        rapido(e.currentTarget, 'tagMsg', (d) => {
            anexar('tagGrid', 'tags', d.id, d.nome);
            fechar(tagDialog);
        });
    });
})();
