/* Promoções (painel): escolher o brinquedo em grade, dar o desconto, ligar
 * e desligar no cartão. Ver o comentário do topo de promocoes_adm.html.
 */
(function () {
    'use strict';

    let brinquedos = [];
    try {
        brinquedos = JSON.parse(document.getElementById('pr-brinquedos')?.textContent || '[]') || [];
    } catch (erro) {
        brinquedos = [];
    }
    const porId = new Map(brinquedos.map((b) => [String(b.id), b]));

    const csrf = document.querySelector('[data-pr-form] input[name="csrfmiddlewaretoken"]')?.value
        || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

    /* ------------------------------------------------------------------
       Dinheiro: digitado em reais inteiros ("18000" é dezoito mil), com a
       vírgula opcional para os centavos. Colar "R$ 1.234,56" também vale.
       ------------------------------------------------------------------ */
    function numero(texto) {
        let limpo = String(texto || '').replace(/[^\d.,]/g, '');
        if (!limpo) return NaN;
        const virgula = limpo.lastIndexOf(',');
        if (virgula >= 0) {
            limpo = limpo.slice(0, virgula).replace(/[.,]/g, '') + '.' + limpo.slice(virgula + 1).replace(/\D/g, '');
        } else if ((limpo.match(/\./g) || []).length > 1 || /\.\d{3}$/.test(limpo)) {
            // "18.000" é dezoito mil, não dezoito vírgula zero
            limpo = limpo.replace(/\./g, '');
        }
        const valor = Number(limpo);
        return Number.isFinite(valor) ? valor : NaN;
    }

    function reais(valor) {
        return 'R$ ' + Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function semMoeda(valor) {
        return Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function semAcento(texto) {
        return String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    }

    function desconto(preco, promo) {
        if (!(preco > 0) || !(promo > 0) || promo >= preco) return 0;
        return Math.round((1 - promo / preco) * 100);
    }

    /* ------------------------------------------------------------------
       Os cartões: "de R$ X" riscado e o selo do desconto, a busca na página
       e a chave liga/desliga.
       ------------------------------------------------------------------ */
    const cartoes = [...document.querySelectorAll('[data-pr-oferta]')];
    // A soma dos preços de tabela de um conjunto (NaN se algum não tem preço).
    function somaTabela(ids) {
        if (!ids.length) return NaN;
        let total = 0;
        for (const id of ids) {
            const preco = Number(porId.get(String(id))?.preco);
            if (!(preco > 0)) return NaN;
            total += preco;
        }
        return total;
    }

    cartoes.forEach((cartao) => {
        const ids = (cartao.dataset.brinquedos || '').split(',').filter(Boolean);
        const tabela = Number(cartao.dataset.precoDe) > 0 ? Number(cartao.dataset.precoDe) : somaTabela(ids);
        const promo = Number(cartao.dataset.preco);
        const pct = desconto(tabela, promo);
        if (pct > 0) {
            const de = cartao.querySelector('[data-pr-de]');
            de.textContent = reais(tabela);
            de.hidden = false;
            const selo = cartao.querySelector('[data-pr-desconto]');
            selo.textContent = `-${pct}%`;
            selo.hidden = false;
        }
    });

    const buscaPagina = document.querySelector('[data-pr-busca]');
    const semResultado = document.querySelector('[data-pr-sem-resultado]');
    buscaPagina?.addEventListener('input', () => {
        const termo = semAcento(buscaPagina.value.trim());
        let visiveis = 0;
        cartoes.forEach((cartao) => {
            const ok = !termo || semAcento(cartao.dataset.busca).includes(termo);
            cartao.hidden = !ok;
            if (ok) visiveis += 1;
        });
        if (semResultado) semResultado.hidden = !(cartoes.length && termo && !visiveis);
    });

    document.querySelectorAll('[data-pr-alternar]').forEach((chave) => {
        chave.addEventListener('change', async () => {
            const cartao = chave.closest('[data-pr-oferta]');
            const rotulo = chave.closest('.pr-chave');
            const texto = cartao.querySelector('[data-pr-chave-texto]');
            const queria = chave.checked;
            rotulo.classList.add('is-ocupada');
            try {
                const dados = new FormData();
                dados.append('csrfmiddlewaretoken', csrf);
                dados.append('acao', 'alternar');
                dados.append('promocao_id', cartao.dataset.id);
                const resposta = await fetch(window.location.pathname, {
                    method: 'POST',
                    body: dados,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin',
                });
                const json = resposta.ok ? await resposta.json() : null;
                if (!json || !json.ok) throw new Error('falhou');
                chave.checked = Boolean(json.ativo);
                cartao.dataset.ativo = json.ativo ? '1' : '0';
                cartao.classList.toggle('is-off', !json.ativo);
                texto.textContent = json.ativo ? 'No site' : 'Desligada';
                const divulgar = cartao.querySelector('[data-campanha-tipo]');
                if (divulgar) {
                    divulgar.disabled = !json.ativo;
                    divulgar.title = json.ativo ? '' : 'Ligue a promoção para divulgar';
                }
            } catch (erro) {
                chave.checked = !queria;
                LSAviso.toast({
                    nivel: 'erro',
                    titulo: 'Não deu para mudar agora',
                    texto: 'Confira a conexão e tente de novo.',
                });
            } finally {
                rotulo.classList.remove('is-ocupada');
            }
        });
    });

    /* ------------------------------------------------------------------
       O editor
       ------------------------------------------------------------------ */
    const editor = document.getElementById('prEditor');
    const form = editor?.querySelector('[data-pr-form]');
    if (!editor || !form) return;

    const $ = (seletor) => form.querySelector(seletor);
    const campo = {
        acao: $('[data-pr-acao]'),
        id: $('[data-pr-id]'),
        enviados: $('[data-pr-brinquedos-enviados]'),
        precoEnviado: $('[data-pr-preco-enviado]'),
        preco: $('[data-pr-preco]'),
        titulo: $('[data-pr-titulo]'),
        imagem: $('[data-pr-imagem]'),
        remover: $('[data-pr-remover]'),
        ativo: $('[data-pr-ativo]'),
        semPreco: $('[data-pr-sem-preco]'),
        precoDe: $('[data-pr-preco-de]'),
        validade: $('[data-pr-validade]'),
        condicoes: $('[data-pr-condicoes]'),
        arte: $('[data-pr-arte]'),
        removerArte: $('[data-pr-remover-arte]'),
    };
    const tituloJanela = $('[data-pr-titulo-janela]');
    const listaEscolhidos = $('[data-pr-escolhidos]');
    const grade = $('[data-pr-brinquedos]');
    const buscaCatalogo = $('[data-pr-cat-busca]');
    const vazio = $('[data-pr-cat-vazio]');
    const ajuda = $('[data-pr-preco-ajuda]');
    const erro = $('[data-pr-erro]');
    const salvar = $('[data-pr-salvar]');
    const sugestoes = $('[data-pr-sugestoes]');
    const imagemPrevia = $('[data-pr-imagem-previa]');
    const imagemTexto = $('[data-pr-imagem-texto]');
    const removerLinha = $('[data-pr-remover-linha]');
    const previa = {
        foto: $('[data-pr-previa-foto]'),
        selo: $('[data-pr-previa-selo]'),
        titulo: $('[data-pr-previa-titulo]'),
        de: $('[data-pr-previa-de]'),
        por: $('[data-pr-previa-por]'),
    };

    let escolhidos = [];         // ids, na ordem escolhida: o primeiro é o principal
    let imagemAtual = '';        // a arte que a promoção já tem (ao editar)
    let tituloAutomatico = '';   // o título que a tela sugeriu (troca junto com o brinquedo)
    let urlTemporaria = '';

    // A grade dos brinquedos é montada uma vez; a busca e a categoria só
    // escondem e mostram.
    const tiles = brinquedos.map((b) => {
        const tile = document.createElement('label');
        tile.className = 'pr-tile';
        tile.dataset.busca = semAcento(b.nome);
        tile.dataset.categorias = JSON.stringify(b.categorias || []);
        const foto = b.foto
            ? `<img src="${b.foto}" alt="" loading="lazy" decoding="async">`
            : '<span class="pr-tile-sem-foto"><i class="bi bi-image"></i></span>';
        const nome = document.createElement('span');
        nome.textContent = b.nome;
        tile.innerHTML = `
            <input type="checkbox" value="${b.id}">
            ${foto}
            ${b.em_promocao ? '<span class="pr-tile-marca">Já em promoção</span>' : ''}
            <span class="pr-tile-texto">
                <strong>${nome.innerHTML}</strong>
                <span>${b.preco ? reais(Number(b.preco)) : 'Sem preço de tabela'}</span>
            </span>`;
        tile.querySelector('input').addEventListener('change', (e) => alternar(String(b.id), e.target.checked));
        grade.appendChild(tile);
        return tile;
    });

    function filtrarCatalogo() {
        const termo = semAcento(buscaCatalogo.value.trim());
        const categoria = form.querySelector('input[name="pr_categoria"]:checked')?.value || '';
        let visiveis = 0;
        tiles.forEach((tile) => {
            const ok = (!termo || tile.dataset.busca.includes(termo))
                && (!categoria || JSON.parse(tile.dataset.categorias).includes(categoria));
            tile.hidden = !ok;
            if (ok) visiveis += 1;
        });
        vazio.hidden = visiveis > 0;
    }

    buscaCatalogo.addEventListener('input', filtrarCatalogo);
    form.querySelectorAll('input[name="pr_categoria"]').forEach((r) => r.addEventListener('change', filtrarCatalogo));
    // Enter na busca do catálogo não manda o formulário
    buscaCatalogo.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        const primeiro = tiles.find((t) => !t.hidden && !t.querySelector('input').checked);
        primeiro?.querySelector('input').click();
    });

    function principal() {
        return porId.get(escolhidos[0]) || null;
    }

    function tituloSugerido() {
        const nomes = escolhidos.map((id) => porId.get(id)?.nome).filter(Boolean);
        if (!nomes.length) return '';
        if (nomes.length === 1) return `${nomes[0]} em oferta`;
        if (nomes.length === 2) return `${nomes[0]} + ${nomes[1]} em oferta`;
        return `${nomes[0]} e mais ${nomes.length - 1} em oferta`;
    }

    // A lista dos escolhidos, em cima da grade: o principal com a marca, e
    // cada um com o x para tirar. Tocar no nome de um faz dele o principal.
    function desenharEscolhidos() {
        listaEscolhidos.innerHTML = '';
        campo.enviados.innerHTML = '';
        escolhidos.forEach((id, posicao) => {
            const b = porId.get(id);
            if (!b) return;
            const enviado = document.createElement('input');
            enviado.type = 'hidden';
            enviado.name = 'brinquedos';
            enviado.value = id;
            campo.enviados.appendChild(enviado);

            const item = document.createElement('li');
            item.classList.toggle('is-principal', posicao === 0);
            const foto = b.foto ? document.createElement('img') : document.createElement('span');
            if (b.foto) { foto.src = b.foto; foto.alt = ''; } else { foto.className = 'pr-mini-sem-foto'; }
            const nome = document.createElement('span');
            nome.className = 'pr-escolhido-nome';
            nome.textContent = b.nome;
            nome.title = posicao === 0 ? 'Principal' : 'Tocar para fazer deste o principal';
            nome.style.cursor = posicao === 0 ? 'default' : 'pointer';
            nome.addEventListener('click', () => {
                if (posicao === 0) return;
                escolhidos = [id, ...escolhidos.filter((x) => x !== id)];
                depoisDeMudar();
            });
            item.append(foto, nome);
            if (posicao === 0 && escolhidos.length > 1) {
                const marca = document.createElement('span');
                marca.className = 'pr-escolhido-marca';
                marca.textContent = 'Principal';
                item.appendChild(marca);
            }
            const tirar = document.createElement('button');
            tirar.type = 'button';
            tirar.setAttribute('aria-label', `Tirar ${b.nome}`);
            tirar.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            tirar.addEventListener('click', () => alternar(id, false));
            item.appendChild(tirar);
            listaEscolhidos.appendChild(item);
        });
        grade.querySelectorAll('input').forEach((caixa) => {
            caixa.checked = escolhidos.includes(caixa.value);
        });
    }

    function depoisDeMudar() {
        const sugerido = tituloSugerido();
        if (!campo.titulo.value.trim() || campo.titulo.value === tituloAutomatico) {
            campo.titulo.value = sugerido;
            tituloAutomatico = sugerido;
        }
        desenharEscolhidos();
        montarSugestoes();
        atualizar();
    }

    function alternar(id, marcar) {
        escolhidos = escolhidos.filter((x) => x !== id);
        if (marcar && porId.has(id)) escolhidos.push(id);
        depoisDeMudar();
    }

    function montarSugestoes() {
        sugestoes.innerHTML = '';
        const b = principal();
        if (!b) return;
        const varios = escolhidos.length > 1;
        const nomes = varios
            ? [tituloSugerido(), `Pacote promocional: ${escolhidos.length} brinquedos`, `Leve ${escolhidos.length} com desconto`, `Oferta especial: ${b.nome} e mais`]
            : [`${b.nome} em oferta`, `Oferta especial: ${b.nome}`, `${b.nome} com desconto`, `Queima de estoque: ${b.nome}`];
        nomes.forEach((nome) => {
            if (!nome || nome.length > 120) return;
            const botao = document.createElement('button');
            botao.type = 'button';
            botao.textContent = nome;
            botao.addEventListener('click', () => {
                campo.titulo.value = nome;
                tituloAutomatico = nome;
                atualizar();
            });
            sugestoes.appendChild(botao);
        });
    }

    // Preço: só número e vírgula na digitação; formatado ao sair do campo.
    campo.preco.addEventListener('input', () => {
        const limpo = campo.preco.value.replace(/[^\d.,]/g, '');
        if (limpo !== campo.preco.value) campo.preco.value = limpo;
        atualizar();
    });
    campo.preco.addEventListener('blur', () => {
        const valor = numero(campo.preco.value);
        if (valor > 0) campo.preco.value = semMoeda(valor);
        atualizar();
    });

    // Preço "de" (o da arte): mesmo jeito de digitar do preço da oferta.
    campo.precoDe.addEventListener('input', () => {
        const limpo = campo.precoDe.value.replace(/[^\d.,]/g, '');
        if (limpo !== campo.precoDe.value) campo.precoDe.value = limpo;
        atualizar();
    });
    campo.precoDe.addEventListener('blur', () => {
        const valor = numero(campo.precoDe.value);
        if (valor > 0) campo.precoDe.value = semMoeda(valor);
        atualizar();
    });
    campo.semPreco.addEventListener('change', atualizar);

    // A arte da campanha (o cartaz inteiro): a prévia ao escolher.
    const arteArea = $('[data-pr-arte-area]');
    const artePrevia = $('[data-pr-arte-previa]');
    const removerArteLinha = $('[data-pr-remover-arte-linha]');
    let arteAtual = '';
    let arteTemporaria = '';
    function atualizarArte() {
        const foto = arteTemporaria || (arteAtual && !campo.removerArte.checked ? arteAtual : '');
        artePrevia.src = foto || '';
        artePrevia.hidden = !foto;
        arteArea.classList.toggle('tem-arte', Boolean(foto));
        removerArteLinha.hidden = !arteAtual;
    }
    campo.arte.addEventListener('change', () => {
        if (arteTemporaria) URL.revokeObjectURL(arteTemporaria);
        const arquivo = campo.arte.files?.[0];
        arteTemporaria = arquivo ? URL.createObjectURL(arquivo) : '';
        if (arquivo) campo.removerArte.checked = false;
        atualizarArte();
    });
    campo.removerArte.addEventListener('change', atualizarArte);

    function tabelaDaOferta() {
        const escrito = numero(campo.precoDe.value);
        return escrito > 0 ? escrito : somaTabela(escolhidos);
    }

    form.querySelectorAll('[data-pr-pct]').forEach((botao) => {
        botao.addEventListener('click', () => {
            const tabela = tabelaDaOferta();
            if (!(tabela > 0)) return;
            const valor = Math.round(tabela * (1 - Number(botao.dataset.prPct) / 100));
            campo.preco.value = semMoeda(valor);
            atualizar();
        });
    });

    campo.titulo.addEventListener('input', atualizar);
    campo.condicoes.addEventListener('input', atualizar);
    campo.remover.addEventListener('change', atualizarImagem);
    campo.imagem.addEventListener('change', () => {
        if (urlTemporaria) URL.revokeObjectURL(urlTemporaria);
        const arquivo = campo.imagem.files?.[0];
        urlTemporaria = arquivo ? URL.createObjectURL(arquivo) : '';
        if (arquivo) campo.remover.checked = false;
        atualizarImagem();
    });

    function fotoDaOferta() {
        if (urlTemporaria) return urlTemporaria;
        if (imagemAtual && !campo.remover.checked) return imagemAtual;
        return principal()?.foto || '';
    }

    function atualizarImagem() {
        const propria = urlTemporaria || (imagemAtual && !campo.remover.checked);
        const foto = fotoDaOferta();
        imagemPrevia.src = foto || '';
        imagemPrevia.hidden = !foto;
        imagemTexto.querySelector('span').innerHTML = propria
            ? 'Arte da promoção. <b>Toque para trocar.</b>'
            : 'Sem arte própria, vai a foto do brinquedo. <b>Toque para enviar uma arte</b> (PNG, JPG ou WEBP).';
        removerLinha.hidden = !imagemAtual;
        previa.foto.src = foto || '';
        previa.foto.hidden = !foto;
    }

    function atualizar() {
        const b = principal();
        const varios = escolhidos.length > 1;
        const tabela = tabelaDaOferta();
        const semPreco = campo.semPreco.checked;
        const promo = semPreco ? NaN : numero(campo.preco.value);
        const pct = desconto(tabela, promo);
        const deTabela = varios ? 'a soma dos preços de tabela' : 'o preço de tabela';

        form.querySelectorAll('[data-pr-pct]').forEach((botao) => { botao.disabled = semPreco || !(tabela > 0); });
        campo.preco.disabled = semPreco;

        previa.titulo.textContent = campo.titulo.value.trim() || 'Título da promoção';
        const condicao = (campo.condicoes.value.split('\n').map((l) => l.trim()).filter(Boolean)[0]) || '';
        previa.por.textContent = semPreco ? (condicao || 'Condição especial') : (promo > 0 ? reais(promo) : 'R$ 0,00');
        previa.de.hidden = !(pct > 0);
        previa.de.textContent = pct > 0 ? reais(tabela) : '';
        previa.selo.hidden = !(pct > 0);
        previa.selo.textContent = pct > 0 ? `-${pct}%` : '';

        let problema = '';
        ajuda.classList.remove('is-bom', 'is-ruim');
        if (!b) {
            ajuda.textContent = 'Escolha os brinquedos para ver o preço de tabela.';
        } else if (semPreco) {
            ajuda.textContent = condicao
                ? 'Sem preço: o site mostra as condições abaixo e o botão "Pedir orçamento".'
                : 'Sem preço: escreva a condição abaixo (por exemplo: ganhe um kit de mesinha kids).';
            if (!condicao) ajuda.classList.add('is-ruim');
        } else if (!(tabela > 0)) {
            ajuda.textContent = varios
                ? 'Algum brinquedo escolhido não tem preço de tabela no cadastro: confira o valor da oferta.'
                : 'Este brinquedo não tem preço de tabela no cadastro: confira o valor da oferta.';
        } else if (!(promo > 0)) {
            ajuda.textContent = varios
                ? `Os ${escolhidos.length} juntos somam ${reais(tabela)}. Digite o valor da oferta para o conjunto ou use um atalho.`
                : `Preço de tabela: ${reais(tabela)}. Digite o valor da oferta ou use um atalho.`;
        } else if (promo >= tabela) {
            // Pode: a oferta pelo preço cheio com uma condição (10x sem juros,
            // à vista com desconto). O site mostra só o preço e as condições.
            ajuda.textContent = `Sem desconto sobre ${deTabela} (${reais(tabela)}): o site mostra o preço e as condições.`;
        } else {
            ajuda.textContent = `De ${reais(tabela)} por ${reais(promo)}${varios ? ' (o conjunto)' : ''}: ${pct}% de desconto (economia de ${reais(tabela - promo)}).`;
            ajuda.classList.add('is-bom');
        }
        erro.textContent = '';
        salvar.disabled = Boolean(problema);
        atualizarImagem();
        return problema;
    }

    function abrir(cartao) {
        form.reset();
        if (urlTemporaria) URL.revokeObjectURL(urlTemporaria);
        urlTemporaria = '';
        buscaCatalogo.value = '';
        form.querySelector('input[name="pr_categoria"][value=""]').checked = true;
        escolhidos = [];
        filtrarCatalogo();
        tituloAutomatico = '';
        erro.textContent = '';
        if (arteTemporaria) URL.revokeObjectURL(arteTemporaria);
        arteTemporaria = '';
        arteAtual = '';

        if (cartao) {
            campo.acao.value = 'editar';
            campo.id.value = cartao.dataset.id;
            tituloJanela.textContent = 'Editar promoção';
            campo.titulo.value = cartao.dataset.descricao || '';
            const preco = Number(cartao.dataset.preco);
            campo.preco.value = preco > 0 ? semMoeda(preco) : '';
            campo.ativo.checked = cartao.dataset.ativo === '1';
            campo.semPreco.checked = !(preco > 0);
            const precoDe = Number(cartao.dataset.precoDe);
            campo.precoDe.value = precoDe > 0 ? semMoeda(precoDe) : '';
            campo.validade.value = cartao.dataset.validade || '';
            marcarSemJuros(form, cartao.dataset.semJuros);
            campo.condicoes.value = cartao.dataset.condicoes || '';
            arteAtual = cartao.dataset.arte || '';
            imagemAtual = cartao.dataset.imagem || '';
            escolhidos = (cartao.dataset.brinquedos || '').split(',').filter((id) => porId.has(id));
            tituloAutomatico = '';
            desenharEscolhidos();
            montarSugestoes();
            atualizar();
        } else {
            campo.acao.value = 'criar';
            campo.id.value = '';
            tituloJanela.textContent = 'Nova promoção';
            campo.ativo.checked = true;
            imagemAtual = '';
            desenharEscolhidos();
            sugestoes.innerHTML = '';
            atualizar();
        }
        atualizarArte();
        editor.showModal();
        if (!cartao) buscaCatalogo.focus();
    }

    function fechar(dialogo) {
        dialogo.close();
    }

    document.querySelectorAll('[data-pr-nova]').forEach((b) => b.addEventListener('click', () => abrir(null)));
    document.querySelectorAll('[data-pr-editar]').forEach((b) => {
        b.addEventListener('click', () => abrir(b.closest('[data-pr-oferta]')));
    });

    form.addEventListener('submit', (e) => {
        const problema = atualizar();
        const b = principal();
        const semPreco = campo.semPreco.checked;
        const promo = numero(campo.preco.value);
        const temCondicao = campo.condicoes.value.trim().length > 0;
        let mensagem = problema;
        if (!b) mensagem = 'Escolha pelo menos um brinquedo para a promoção.';
        else if (semPreco && !temCondicao) mensagem = 'Sem preço, escreva a condição da promoção.';
        else if (!semPreco && !(promo > 0)) mensagem = 'Digite o preço da oferta.';
        else if (!campo.titulo.value.trim()) mensagem = 'Dê um título para a promoção.';
        if (mensagem) {
            e.preventDefault();
            erro.textContent = mensagem;
            if (!b) buscaCatalogo.focus();
            return;
        }
        campo.precoEnviado.value = semPreco ? '' : promo.toFixed(2);
        const precoDe = numero(campo.precoDe.value);
        campo.precoDe.value = precoDe > 0 ? precoDe.toFixed(2) : '';
        salvar.disabled = true;
        salvar.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvando...';
    });

    /* ------------------------------------------------------------------
       Excluir
       ------------------------------------------------------------------ */
    const janelaExcluir = document.getElementById('prExcluir');
    document.querySelectorAll('[data-pr-excluir]').forEach((botao) => {
        botao.addEventListener('click', () => {
            const cartao = botao.closest('[data-pr-oferta]');
            janelaExcluir.querySelector('[data-pr-excluir-id]').value = cartao.dataset.id;
            janelaExcluir.querySelector('[data-pr-excluir-nome]').textContent = cartao.dataset.descricao;
            janelaExcluir.showModal();
        });
    });

    [editor, janelaExcluir].forEach((dialogo) => {
        if (!dialogo) return;
        dialogo.querySelectorAll('[data-pr-fechar]').forEach((b) => b.addEventListener('click', () => fechar(dialogo)));
        // clicar fora da janela fecha
        dialogo.addEventListener('click', (e) => {
            if (e.target === dialogo) fechar(dialogo);
        });
    });
})();

// As vezes sem juros (LEIA-ME seção 99): os chips de rádio do cadastro.
function marcarSemJuros(raiz, valor) {
    var alvo = String(valor || "");
    var chips = (raiz || document).querySelectorAll('input[name="parcelas_sem_juros"]');
    chips.forEach(function (chip) { chip.checked = chip.value === alvo; });
    if (![].some.call(chips, function (chip) { return chip.checked; }) && chips[0]) chips[0].checked = true;
}
