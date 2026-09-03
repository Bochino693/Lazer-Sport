/* Comportamento de brinquedos.
 *
 * NASCEU DE DENTRO DO HTML. Eram 14 KB de <script> no template --
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
    const toast = document.getElementById('catalogo-toast');
    let toastTimer = null;

    function mostrarToastCatalogo(mensagem, erro = false) {
        if (typeof window.mostrarToast === 'function') {
            window.mostrarToast(mensagem, erro);
            return;
        }

        if (!toast) return;
        window.clearTimeout(toastTimer);
        toast.textContent = mensagem;
        toast.classList.toggle('error', erro);
        toast.classList.add('show');
        toastTimer = window.setTimeout(() => toast.classList.remove('show'), 3200);
    }

    function paraNumero(valor) {
        if (valor === null || valor === undefined || valor === '') return 0;
        const texto = String(valor).trim();
        if (texto.includes(',') && texto.includes('.')) {
            return Number(texto.replace(/\./g, '').replace(',', '.')) || 0;
        }
        return Number(texto.replace(',', '.')) || 0;
    }

    const formatadorNumeroBR = new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    const formatadorMoedaBR = new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    function textoDecimalBR(valor) {
        return formatadorNumeroBR.format(Number(valor) || 0);
    }

    function textoMoedaBR(valor) {
        return formatadorMoedaBR.format(Number(valor) || 0);
    }

    function formatarMoedas() {
        document.querySelectorAll('.catalogo-money[data-value]').forEach(elemento => {
            const valor = paraNumero(elemento.dataset.value);
            elemento.textContent = valor.toLocaleString('pt-BR', {
                style: 'currency',
                currency: 'BRL',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        });
    }

    function estrelaPreenchida() {
        return '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896 4.664 22.774l1.402-8.176L.132 9.21l8.2-1.192z"></path></svg>';
    }

    function estrelaVazia() {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path d="M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896 4.664 22.774l1.402-8.176L.132 9.21l8.2-1.192z" stroke-width="1.35"></path></svg>';
    }

    function estrelaMetade(id) {
        return `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <defs>
                    <linearGradient id="catalog-half-${id}">
                        <stop offset="50%" stop-color="currentColor"></stop>
                        <stop offset="50%" stop-color="transparent"></stop>
                    </linearGradient>
                </defs>
                <path d="M12 .587l3.668 7.431 8.2 1.192-5.934 5.789 1.402 8.176L12 18.896 4.664 22.774l1.402-8.176L.132 9.21l8.2-1.192z" fill="url(#catalog-half-${id})"></path>
            </svg>`;
    }

    function renderizarEstrelas() {
        document.querySelectorAll('.catalogo-stars[data-rating]').forEach((container, index) => {
            const nota = Math.max(0, Math.min(5, paraNumero(container.dataset.rating)));
            let html = '';

            for (let posicao = 1; posicao <= 5; posicao += 1) {
                if (nota >= posicao) {
                    html += estrelaPreenchida();
                } else if (nota >= posicao - .5) {
                    html += estrelaMetade(`${index}-${posicao}`);
                } else {
                    html += estrelaVazia();
                }
            }

            container.innerHTML = html;
        });
    }

    window.adicionarBrinquedoCatalogo = async function (event, brinquedoId, botao) {
        event.preventDefault();
        event.stopPropagation();

        if (!botao || botao.dataset.loading === 'true') return;

        if (typeof window.adicionarAoCarrinho !== 'function') {
            mostrarToastCatalogo('Não foi possível acessar o carrinho agora.', true);
            return;
        }

        const conteudoOriginal = botao.innerHTML;
        botao.dataset.loading = 'true';
        botao.disabled = true;
        botao.setAttribute('aria-busy', 'true');
        botao.classList.add('is-loading');
        botao.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i><span>Adicionando...</span>';

        try {
            const resultado = await Promise.resolve(
                window.adicionarAoCarrinho('brinquedo', brinquedoId)
            );

            if (!resultado || !resultado.sucesso) {
                botao.innerHTML = conteudoOriginal;
                return;
            }

            botao.classList.remove('is-loading');
            botao.classList.add('is-added');
            botao.innerHTML = '<i class="fa-solid fa-check" aria-hidden="true"></i><span>Adicionado</span>';
            mostrarToastCatalogo('Brinquedo adicionado ao carrinho.');

            window.setTimeout(() => {
                botao.classList.remove('is-added');
                botao.innerHTML = conteudoOriginal;
            }, 1900);
        } catch (erro) {
            console.error(erro);
            botao.innerHTML = conteudoOriginal;
            mostrarToastCatalogo('Não foi possível adicionar este brinquedo.', true);
        } finally {
            botao.dataset.loading = 'false';
            botao.disabled = false;
            botao.removeAttribute('aria-busy');
            botao.classList.remove('is-loading');
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        formatarMoedas();
        renderizarEstrelas();

        const form = document.querySelector('.catalogo-filter-grid');
        const submit = form ? form.querySelector('.catalogo-filter-submit') : null;
        const precoMin = document.getElementById('catalogo-preco-min');
        const precoMax = document.getElementById('catalogo-preco-max');
        const rangeMin = document.getElementById('catalogo-range-min');
        const rangeMax = document.getElementById('catalogo-range-max');
        const rangeMinOutput = document.getElementById('catalogo-range-min-output');
        const rangeMaxOutput = document.getElementById('catalogo-range-max-output');
        const regraPreco = document.getElementById('catalogo-price-rule');
        const escolhas = Array.from(document.querySelectorAll('[data-choice]'));
        const mobileToggle = document.querySelector('[data-mobile-filter-toggle]');
        const ordensPorValor = new Set(['menor-preco', 'maior-preco', 'custo-beneficio']);

        function radioSelecionado(nome) {
            return form ? form.querySelector(`input[name="${nome}"]:checked`) : null;
        }

        function valorSelecionado(nome) {
            const radio = radioSelecionado(nome);
            return radio ? radio.value : '';
        }

        function atualizarResumoDaEscolha(input) {
            if (!input) return;
            const escolha = input.closest('[data-choice]');
            const opcao = input.closest('[data-choice-label]');
            const output = escolha ? escolha.querySelector('[data-choice-output]') : null;
            if (output && opcao) output.textContent = opcao.dataset.choiceLabel || '';
        }

        function selecionarValor(nome, valor) {
            if (!form) return;
            const input = Array.from(form.querySelectorAll(`input[name="${nome}"]`))
                .find(item => item.value === valor);
            if (!input) return;
            input.checked = true;
            atualizarResumoDaEscolha(input);
        }

        function atualizarBloqueioDeRolagem() {
            const escolhaAberta = escolhas.some(escolha => escolha.open);
            document.body.classList.toggle(
                'catalogo-filter-lock',
                escolhaAberta && window.matchMedia('(max-width: 680px)').matches
            );
        }

        function fecharEscolha(escolha) {
            if (escolha) escolha.removeAttribute('open');
            atualizarBloqueioDeRolagem();
        }

        escolhas.forEach(escolha => {
            escolha.querySelectorAll('.catalogo-choice-input').forEach(input => {
                if (input.checked) atualizarResumoDaEscolha(input);
                input.addEventListener('change', () => {
                    atualizarResumoDaEscolha(input);
                    fecharEscolha(escolha);
                });
            });

            escolha.querySelectorAll('[data-choice-close]').forEach(botao => {
                botao.addEventListener('click', evento => {
                    evento.preventDefault();
                    fecharEscolha(escolha);
                });
            });

            escolha.addEventListener('toggle', () => {
                if (escolha.open) {
                    escolhas.forEach(outra => {
                        if (outra !== escolha) outra.removeAttribute('open');
                    });
                }
                atualizarBloqueioDeRolagem();
            });
        });

        document.addEventListener('click', evento => {
            if (window.matchMedia('(max-width: 680px)').matches) return;
            escolhas.forEach(escolha => {
                if (escolha.open && !escolha.contains(evento.target)) fecharEscolha(escolha);
            });
        });

        document.addEventListener('keydown', evento => {
            if (evento.key !== 'Escape') return;
            escolhas.forEach(fecharEscolha);
        });

        window.addEventListener('resize', atualizarBloqueioDeRolagem, { passive: true });

        if (mobileToggle && form) {
            mobileToggle.addEventListener('click', () => {
                const aberto = form.classList.toggle('is-expanded');
                mobileToggle.setAttribute('aria-expanded', String(aberto));
            });
        }

        function possuiValor(input) {
            return Boolean(input && input.value.trim());
        }

        function atualizarSaidasDaFaixa() {
            if (rangeMinOutput && rangeMin) {
                rangeMinOutput.textContent = textoMoedaBR(rangeMin.value);
            }
            if (rangeMaxOutput && rangeMax) {
                rangeMaxOutput.textContent = textoMoedaBR(rangeMax.value);
            }
        }

        function restaurarFaixaVisual() {
            if (rangeMin) rangeMin.value = rangeMin.min;
            if (rangeMax) rangeMax.value = rangeMax.max;
            atualizarSaidasDaFaixa();
        }

        function sincronizarCampoComFaixa(input, range) {
            if (!input || !range || !input.value.trim()) return;
            const numero = paraNumero(input.value);
            if (!Number.isFinite(numero)) return;
            const minimo = Number(range.min);
            const maximo = Number(range.max);
            range.value = String(Math.min(maximo, Math.max(minimo, numero)));
            atualizarSaidasDaFaixa();
        }

        function atualizarRegraDeValor() {
            const valorAtivo = Boolean(
                ordensPorValor.has(valorSelecionado('ordenar'))
                || possuiValor(precoMin)
                || possuiValor(precoMax)
            );

            if (valorAtivo) selecionarValor('disponibilidade', 'loja');

            if (regraPreco) {
                regraPreco.classList.toggle('is-active', valorAtivo);
                regraPreco.innerHTML = valorAtivo
                    ? '<i class="fa-solid fa-circle-check" aria-hidden="true"></i><span>Disponíveis na loja aplicado automaticamente.</span>'
                    : '<i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Ao usar valores, exibiremos somente itens com preço.</span>';
            }
        }

        [precoMin, precoMax].forEach(input => {
            if (!input) return;
            input.addEventListener('input', () => {
                input.value = input.value.replace(/[^0-9.,]/g, '');
                atualizarRegraDeValor();
            });
            input.addEventListener('blur', () => {
                if (!input.value.trim()) return;
                input.value = textoDecimalBR(paraNumero(input.value));
                sincronizarCampoComFaixa(
                    input,
                    input === precoMin ? rangeMin : rangeMax
                );
            });
        });

        rangeMin?.addEventListener('input', () => {
            if (rangeMax && Number(rangeMin.value) > Number(rangeMax.value)) {
                rangeMax.value = rangeMin.value;
                if (precoMax) precoMax.value = textoDecimalBR(rangeMax.value);
            }
            if (precoMin) precoMin.value = textoDecimalBR(rangeMin.value);
            atualizarSaidasDaFaixa();
            atualizarRegraDeValor();
        });

        rangeMax?.addEventListener('input', () => {
            if (rangeMin && Number(rangeMax.value) < Number(rangeMin.value)) {
                rangeMin.value = rangeMax.value;
                if (precoMin) precoMin.value = textoDecimalBR(rangeMin.value);
            }
            if (precoMax) precoMax.value = textoDecimalBR(rangeMax.value);
            atualizarSaidasDaFaixa();
            atualizarRegraDeValor();
        });

        form?.querySelectorAll('input[name="ordenar"]').forEach(input => {
            input.addEventListener('change', atualizarRegraDeValor);
        });

        form?.querySelectorAll('input[name="disponibilidade"]').forEach(input => {
            input.addEventListener('change', () => {
                if (input.checked && input.value !== 'loja') {
                    if (precoMin) precoMin.value = '';
                    if (precoMax) precoMax.value = '';
                    restaurarFaixaVisual();
                    if (ordensPorValor.has(valorSelecionado('ordenar'))) selecionarValor('ordenar', 'novidades');
                }
                atualizarRegraDeValor();
            });
        });

        sincronizarCampoComFaixa(precoMin, rangeMin);
        sincronizarCampoComFaixa(precoMax, rangeMax);
        atualizarSaidasDaFaixa();
        atualizarRegraDeValor();

        if (form && submit) {
            form.addEventListener('submit', () => {
                atualizarRegraDeValor();
                submit.disabled = true;
                submit.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Filtrando...';
            });
        }
    });
})();
