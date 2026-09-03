/* Comportamento de manutencao.
 *
 * NASCEU DE DENTRO DO HTML. Eram 35 KB de <script> no template --
 * peso repetido a cada abertura da página, que o navegador não tinha
 * como guardar: script dentro do HTML não tem endereço para cachear.
 *
 * O <script src> ficou na MESMA posição do bloco antigo, e sem `defer`
 * de propósito: script clássico externo executa na ordem do documento,
 * igual ao inline. Com `defer` ele passaria para depois da análise da
 * página, e qualquer trecho que dependesse dele antes disso quebraria
 * sem aviso.
 */

document.addEventListener("DOMContentLoaded", () => {
    inicializarAbasManutencao();
    inicializarFormularioManutencao();
    inicializarModalSucesso();
    inicializarDetalhesManutencao();
    inicializarFechamentoDeModais();
});

function abrirModalManutencao(modal) {
    if (!modal) return;
    modal.style.display = "block";
    document.body.style.overflow = "hidden";

    const focoInicial = modal.querySelector(
        "input:not([type='hidden']), button, a[href]"
    );
    window.setTimeout(() => focoInicial?.focus(), 40);
}

function fecharModalManutencao(modal) {
    if (!modal) return;
    modal.style.display = "none";

    const existeOutroAberto = Array.from(
        document.querySelectorAll(".modal-brinquedos")
    ).some(item => item.style.display === "block");

    if (!existeOutroAberto) {
        document.body.style.overflow = "";
    }
}

function inicializarFechamentoDeModais() {
    const modais = Array.from(
        document.querySelectorAll(".modal-brinquedos")
    );

    modais.forEach(modal => {
        modal.addEventListener("click", event => {
            if (event.target === modal) {
                fecharModalManutencao(modal);
            }
        });
    });

    document.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;

        const abertos = modais.filter(
            modal => modal.style.display === "block"
        );

        if (abertos.length) {
            fecharModalManutencao(abertos[abertos.length - 1]);
        }
    });
}

function inicializarAbasManutencao() {
    const tabs = Array.from(document.querySelectorAll(".tab-btn"));
    const contents = Array.from(document.querySelectorAll(".tab-content"));

    if (!tabs.length || !contents.length) return;

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const target = document.getElementById(tab.dataset.tab);
            if (!target) return;

            tabs.forEach(item => {
                item.classList.remove("active");
                item.setAttribute("aria-selected", "false");
            });
            contents.forEach(content => content.classList.remove("active"));

            tab.classList.add("active");
            tab.setAttribute("aria-selected", "true");
            target.classList.add("active");

            const url = new URL(window.location.href);
            url.searchParams.set("tab", tab.dataset.tab);
            window.history.replaceState({}, "", url);
        });
    });
}

function inicializarFormularioManutencao() {
    const form = document.querySelector(".manutencao-form");
    if (!form) return;

    inicializarSeletorBrinquedo(form);
    inicializarTelefone();
    inicializarCep();
    inicializarUploadFotos(form);

    form.addEventListener("submit", event => {
        if (form.dataset.uploadProcessando === "1") {
            event.preventDefault();
            window.alert(
                "Aguarde a otimização das fotos terminar antes de enviar."
            );
            return;
        }

        if (form.dataset.envioEmAndamento === "1") {
            event.preventDefault();
            return;
        }

        const brinquedoInput = document.getElementById("brinquedo-input");
        const brinquedoNaoListado = document.getElementById(
            "brinquedo-nao-listado"
        );
        const descricaoLivre = document.getElementById(
            "brinquedo-descricao-livre"
        );
        const botaoSelecionar = document.getElementById(
            "selecionar-brinquedo-btn"
        );
        const modoEquipamentoManual =
            brinquedoNaoListado?.value === "1";

        if (!brinquedoInput?.value && !modoEquipamentoManual) {
            event.preventDefault();
            window.alert(
                "Selecione um equipamento ou escolha a opção “Não encontrei meu equipamento”."
            );
            botaoSelecionar?.focus();
            return;
        }

        if (
            modoEquipamentoManual &&
            !descricaoLivre?.value.trim()
        ) {
            event.preventDefault();
            window.alert(
                "Descreva o equipamento para que nossa equipe consiga identificá-lo."
            );
            descricaoLivre?.focus();
            return;
        }

        const painelEndereco = document.getElementById("campos-endereco");
        const modoManual = document.getElementById("sem-cep");

        if (painelEndereco?.hidden) {
            event.preventDefault();
            window.alert(
                "Digite um CEP válido e aguarde a localização ou marque “Não tenho CEP” para preencher manualmente."
            );
            if (modoManual && !modoManual.checked) {
                document.getElementById("id_cep")?.focus();
            }
            return;
        }

        if (!form.checkValidity()) {
            event.preventDefault();
            form.reportValidity();
            return;
        }

        form.dataset.envioEmAndamento = "1";

        const botaoEnviar = document.getElementById(
            "btn-enviar-manutencao"
        );

        if (botaoEnviar) {
            botaoEnviar.disabled = true;
            botaoEnviar.innerHTML =
                '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>' +
                "<span>Enviando...</span>";
        }
    });
}

function inicializarSeletorBrinquedo(form) {
    const modal = document.getElementById("modal-brinquedos");
    const botaoSelecionar = document.getElementById(
        "selecionar-brinquedo-btn"
    );
    const inputHidden = document.getElementById("brinquedo-input");
    const card = document.getElementById("brinquedo-card");
    const cardManual = document.getElementById(
        "brinquedo-manual-card"
    );
    const inputManual = document.getElementById(
        "brinquedo-descricao-livre"
    );
    const flagManual = document.getElementById(
        "brinquedo-nao-listado"
    );

    if (
        !modal ||
        !botaoSelecionar ||
        !inputHidden ||
        !card ||
        !cardManual ||
        !inputManual ||
        !flagManual
    ) return;

    const fechar = modal.querySelector(".close-modal");
    const itens = Array.from(modal.querySelectorAll(".item-brinquedo"));
    const pesquisa = modal.querySelector("#pesquisa-brinquedo");
    const opcaoManual = modal.querySelector("#produto-nao-listado");
    const semResultado = modal.querySelector(
        "#sem-resultado-brinquedo"
    );
    const botoesOrdenar = Array.from(
        modal.querySelectorAll(".btn-ordenar")
    );
    const lista = modal.querySelector(".lista-brinquedos");
    const imagemSelecionada = document.getElementById("brinquedo-img");
    const nomeSelecionado = document.getElementById("brinquedo-nome");
    const remover = card.querySelector(".remove-brinquedo");
    const removerManual = cardManual.querySelector(
        ".remove-brinquedo-manual"
    );

    const exibirEstadoInicial = () => {
        const estaNoModoManual = flagManual.value === "1";

        botaoSelecionar.style.display =
            estaNoModoManual ? "none" : "flex";
        card.style.display = "none";
        cardManual.style.display =
            estaNoModoManual ? "block" : "none";
        inputManual.required = estaNoModoManual;
    };

    const selecionarManual = () => {
        inputHidden.value = "";
        flagManual.value = "1";
        inputManual.required = true;
        card.style.display = "none";
        botaoSelecionar.style.display = "none";
        cardManual.style.display = "block";
        fecharModalManutencao(modal);
        cardManual.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });
        window.setTimeout(() => inputManual.focus(), 80);
    };

    botaoSelecionar.addEventListener("click", () => {
        abrirModalManutencao(modal);
    });

    fechar?.addEventListener("click", () => {
        fecharModalManutencao(modal);
        botaoSelecionar.focus();
    });

    opcaoManual?.addEventListener("click", selecionarManual);

    itens.forEach(item => {
        item.addEventListener("click", () => {
            inputHidden.value = item.dataset.id || "";
            flagManual.value = "0";
            inputManual.value = "";
            inputManual.required = false;

            if (nomeSelecionado) {
                nomeSelecionado.textContent =
                    item.dataset.nome || "Brinquedo selecionado";
            }

            const imagemItem = item.querySelector("img");
            if (imagemSelecionada) {
                if (imagemItem?.src) {
                    imagemSelecionada.src = imagemItem.src;
                    imagemSelecionada.alt = item.dataset.nome || "";
                    imagemSelecionada.style.display = "";
                } else {
                    imagemSelecionada.removeAttribute("src");
                    imagemSelecionada.alt = "";
                    imagemSelecionada.style.display = "none";
                }
            }

            botaoSelecionar.style.display = "none";
            cardManual.style.display = "none";
            card.style.display = "flex";
            fecharModalManutencao(modal);
            card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
    });

    remover?.addEventListener("click", () => {
        inputHidden.value = "";
        card.style.display = "none";
        botaoSelecionar.style.display = "flex";
        botaoSelecionar.focus();
    });

    removerManual?.addEventListener("click", () => {
        flagManual.value = "0";
        inputManual.value = "";
        inputManual.required = false;
        cardManual.style.display = "none";
        botaoSelecionar.style.display = "flex";
        botaoSelecionar.focus();
    });

    pesquisa?.addEventListener("input", () => {
        const termo = pesquisa.value.trim().toLocaleLowerCase("pt-BR");
        let quantidadeVisivel = 0;

        itens.forEach(item => {
            const nome = (item.dataset.nome || "")
                .toLocaleLowerCase("pt-BR");
            const corresponde = nome.includes(termo);
            item.hidden = !corresponde;
            if (corresponde) quantidadeVisivel += 1;
        });

        if (semResultado) {
            semResultado.hidden =
                itens.length === 0 || quantidadeVisivel > 0;
        }
    });

    botoesOrdenar.forEach(botao => {
        botao.addEventListener("click", () => {
            botoesOrdenar.forEach(item => {
                item.classList.remove("active");
            });
            botao.classList.add("active");

            const ordem = botao.dataset.ordem;
            itens
                .sort((a, b) => {
                    const comparacao = (a.dataset.nome || "").localeCompare(
                        b.dataset.nome || "",
                        "pt-BR",
                        { sensitivity: "base" }
                    );
                    return ordem === "z-a" ? -comparacao : comparacao;
                })
                .forEach(item => lista?.appendChild(item));
        });
    });

    exibirEstadoInicial();
}

function maskTelefoneBR(value) {
    const numeros = String(value || "")
        .replace(/\D/g, "")
        .slice(0, 11);

    if (numeros.length <= 10) {
        return numeros
            .replace(/^(\d{2})(\d)/, "($1) $2")
            .replace(/(\d{4})(\d)/, "$1-$2");
    }

    return numeros
        .replace(/^(\d{2})(\d)/, "($1) $2")
        .replace(/(\d{5})(\d)/, "$1-$2");
}

function inicializarTelefone() {
    const telefone = document.querySelector(".mask-telefone");
    if (!telefone) return;

    telefone.value = maskTelefoneBR(telefone.value);
    telefone.addEventListener("input", () => {
        telefone.value = maskTelefoneBR(telefone.value);
    });
}

function formatarCep(value) {
    const numeros = String(value || "")
        .replace(/\D/g, "")
        .slice(0, 8);

    return numeros.replace(/^(\d{5})(\d)/, "$1-$2");
}

function inicializarCep() {
    const cepInput = document.getElementById("id_cep");
    const feedback = document.getElementById("cepFeedback");
    const semCepInput = document.getElementById("sem-cep");
    const cepInputGroup = document.getElementById("cepInputGroup");
    const painelEndereco = document.getElementById("campos-endereco");
    const status = document.getElementById("addressStatus");
    const statusTitulo = document.getElementById("addressStatusTitle");
    const statusTexto = document.getElementById("addressStatusText");
    const statusIcone = status?.querySelector(".address-status-icon");
    const modoBadge = document.getElementById("addressModeBadge");

    if (
        !cepInput ||
        !feedback ||
        !semCepInput ||
        !painelEndereco ||
        !status ||
        !statusTitulo ||
        !statusTexto ||
        !statusIcone ||
        !modoBadge
    ) return;

    const seletoresEndereco = [
        "#id_endereco",
        "#id_numero",
        "#id_complemento",
        "#id_bairro",
        "#id_cidade",
        "#id_estado"
    ];
    const camposEndereco = seletoresEndereco
        .map(selector => document.querySelector(selector))
        .filter(Boolean);
    const cepEraObrigatorio = cepInput.required;
    let controller = null;
    let debounceCep = null;

    function habilitarCamposEndereco(habilitar, limpar = false) {
        camposEndereco.forEach(campo => {
            if (limpar) {
                campo.value = "";
            }
            campo.disabled = !habilitar;
            campo.classList.toggle("campo-bloqueado", !habilitar);
        });
    }

    function exibirFeedback(texto, classe = "") {
        feedback.textContent = texto;
        feedback.className = `cep-feedback ${classe}`.trim();
    }

    function exibirStatus(tipo, titulo, texto) {
        const icones = {
            loading: "fa-solid fa-spinner fa-spin",
            success: "fa-solid fa-circle-check",
            error: "fa-solid fa-triangle-exclamation",
            manual: "fa-solid fa-pen-to-square"
        };

        status.hidden = false;
        status.className = `address-status is-${tipo}`;
        statusTitulo.textContent = titulo;
        statusTexto.textContent = texto;
        statusIcone.innerHTML =
            `<i class="${icones[tipo] || icones.loading}" aria-hidden="true"></i>`;
    }

    function ocultarStatus() {
        status.hidden = true;
        status.className = "address-status";
    }

    function mostrarCamposEndereco(modo, focar = false) {
        habilitarCamposEndereco(true);
        painelEndereco.hidden = false;
        painelEndereco.setAttribute("aria-hidden", "false");
        semCepInput.setAttribute("aria-expanded", "true");

        const manual = modo === "manual";
        modoBadge.innerHTML = manual
            ? '<i class="fa-solid fa-pen" aria-hidden="true"></i> Manual'
            : '<i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i> Automático';

        if (focar) {
            const destino = manual
                ? document.getElementById("id_endereco")
                : document.getElementById("id_numero");
            window.setTimeout(() => destino?.focus(), 80);
        }
    }

    function ocultarCamposEndereco(limpar = false) {
        habilitarCamposEndereco(false, limpar);
        painelEndereco.hidden = true;
        painelEndereco.setAttribute("aria-hidden", "true");
        semCepInput.setAttribute("aria-expanded", "false");
    }

    function preencherEndereco(data) {
        const mapeamento = {
            "#id_endereco": data.logradouro || "",
            "#id_bairro": data.bairro || "",
            "#id_cidade": data.localidade || "",
            "#id_estado": data.uf || ""
        };

        Object.entries(mapeamento).forEach(([selector, valor]) => {
            const campo = document.querySelector(selector);
            if (campo) campo.value = valor;
        });
    }

    function ativarModoManual({
        preservarValores = false,
        focar = true
    } = {}) {
        controller?.abort();
        window.clearTimeout(debounceCep);

        semCepInput.checked = true;
        cepInput.value = "";
        cepInput.disabled = true;
        cepInput.required = false;
        cepInput.classList.remove("campo-erro", "campo-loading");
        cepInputGroup.classList.add("is-manual");
        exibirFeedback("CEP dispensado: preencha o endereço abaixo.", "cep-success");

        if (!preservarValores) {
            habilitarCamposEndereco(true, true);
        }

        mostrarCamposEndereco("manual", focar);
        exibirStatus(
            "manual",
            "Preenchimento manual ativado",
            "Informe rua, número, bairro, cidade e estado para continuar."
        );
    }

    function desativarModoManual() {
        semCepInput.checked = false;
        cepInput.disabled = false;
        cepInput.required = cepEraObrigatorio;
        cepInputGroup.classList.remove("is-manual");
        cepInput.classList.remove("campo-erro", "campo-loading");
        exibirFeedback("");
        ocultarStatus();
        ocultarCamposEndereco(true);
        window.setTimeout(() => cepInput.focus(), 60);
    }

    async function buscarCep({ focar = true } = {}) {
        const cep = cepInput.value.replace(/\D/g, "");
        if (cep.length !== 8) return;

        controller?.abort();
        controller = new AbortController();

        cepInput.classList.remove("campo-erro");
        cepInput.classList.add("campo-loading");
        exibirFeedback("Buscando endereço…", "cep-loading");
        ocultarCamposEndereco(true);
        exibirStatus(
            "loading",
            "Consultando CEP",
            "Só um instante enquanto localizamos o endereço."
        );

        try {
            const resposta = await fetch(
                `https://viacep.com.br/ws/${cep}/json/`,
                { signal: controller.signal }
            );

            if (!resposta.ok) {
                throw new Error("Falha na consulta do CEP");
            }

            const data = await resposta.json();
            cepInput.classList.remove("campo-loading");

            if (data.erro) {
                cepInput.classList.add("campo-erro");
                ocultarCamposEndereco(true);
                exibirFeedback(
                    "CEP não encontrado. Confira o número ou use “Não tenho CEP”.",
                    "cep-error"
                );
                exibirStatus(
                    "error",
                    "Não localizamos esse CEP",
                    "Revise os números ou marque “Não tenho CEP” para preencher manualmente."
                );
                return;
            }

            preencherEndereco(data);
            mostrarCamposEndereco("automatico", focar);
            exibirFeedback("Endereço encontrado e preenchido.", "cep-success");
            exibirStatus(
                "success",
                "Endereço localizado",
                "Confira os dados encontrados e complete o número."
            );
        } catch (error) {
            if (error.name === "AbortError") return;

            cepInput.classList.remove("campo-loading");
            cepInput.classList.add("campo-erro");
            ocultarCamposEndereco(true);
            exibirFeedback(
                "Consulta indisponível. Use “Não tenho CEP” para continuar.",
                "cep-error"
            );
            exibirStatus(
                "error",
                "Não foi possível consultar agora",
                "Você pode tentar novamente ou ativar o preenchimento manual."
            );
        }
    }

    cepInput.value = formatarCep(cepInput.value);

    semCepInput.addEventListener("change", () => {
        if (semCepInput.checked) {
            ativarModoManual();
        } else {
            desativarModoManual();
        }
    });

    cepInput.addEventListener("input", () => {
        cepInput.value = formatarCep(cepInput.value);
        cepInput.classList.remove("campo-erro", "campo-loading");

        window.clearTimeout(debounceCep);
        const cep = cepInput.value.replace(/\D/g, "");

        if (cep.length < 8) {
            controller?.abort();
            ocultarCamposEndereco(true);
            ocultarStatus();
            exibirFeedback("");
            return;
        }

        debounceCep = window.setTimeout(() => buscarCep(), 220);
    });

    const enderecoJaPreenchido = camposEndereco.some(
        campo => campo.value.trim()
    );
    const cepCompleto =
        cepInput.value.replace(/\D/g, "").length === 8;

    if (!cepCompleto && enderecoJaPreenchido) {
        ativarModoManual({
            preservarValores: true,
            focar: false
        });
    } else if (cepCompleto && enderecoJaPreenchido) {
        mostrarCamposEndereco("automatico");
        exibirFeedback("Confira o endereço antes de enviar.", "cep-success");
        exibirStatus(
            "success",
            "Endereço pronto para conferência",
            "Revise os dados e complete o que estiver faltando."
        );
    } else if (cepCompleto) {
        buscarCep({ focar: false });
    } else {
        ocultarCamposEndereco();
        ocultarStatus();
    }
}

function inicializarUploadFotos(form) {
    const input = document.getElementById("imagens");
    const card = document.getElementById("uploadCard");
    const preview = document.getElementById("preview");
    const info = document.getElementById("uploadInfo");

    if (!input || !card || !preview || !info || !form) return;

    const MAX_FILES = 5;
    const MAX_FILE_BYTES = 700 * 1024;
    const MAX_TOTAL_BYTES = 3_600_000;
    const MAX_DIMENSION = 1600;
    const TIPOS_ACEITOS = new Set([
        "image/jpeg",
        "image/png",
        "image/webp"
    ]);

    let arquivos = [];

    function totalBytes() {
        return arquivos.reduce(
            (total, item) => total + item.file.size,
            0
        );
    }

    function atualizarInput() {
        const transferencia = new DataTransfer();
        arquivos.forEach(item => transferencia.items.add(item.file));
        input.files = transferencia.files;
    }

    function formatarTamanho(bytes) {
        return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
    }

    function definirInfo(texto, erro = false) {
        info.textContent = texto;
        info.style.color = erro ? "#c91f31" : "";
    }

    function carregarImagem(file) {
        return new Promise((resolve, reject) => {
            const imagem = new Image();
            const url = URL.createObjectURL(file);

            imagem.onload = () => {
                URL.revokeObjectURL(url);
                resolve(imagem);
            };
            imagem.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error("Imagem incompatível"));
            };
            imagem.src = url;
        });
    }

    function canvasParaBlob(canvas, qualidade) {
        return new Promise((resolve, reject) => {
            canvas.toBlob(
                blob => {
                    if (blob) resolve(blob);
                    else reject(new Error("Falha ao otimizar a imagem"));
                },
                "image/jpeg",
                qualidade
            );
        });
    }

    async function otimizarImagem(file) {
        if (!TIPOS_ACEITOS.has(file.type)) {
            throw new Error("Use somente fotos JPG, PNG ou WEBP.");
        }

        if (
            file.size <= MAX_FILE_BYTES &&
            file.type !== "image/png"
        ) {
            return file;
        }

        const imagem = await carregarImagem(file);
        const maiorLadoOriginal = Math.max(
            imagem.naturalWidth,
            imagem.naturalHeight
        );

        let limiteDimensao = Math.min(
            MAX_DIMENSION,
            maiorLadoOriginal
        );
        let qualidade = 0.82;
        let ultimoBlob = null;

        for (let tentativa = 0; tentativa < 10; tentativa += 1) {
            const escala = Math.min(
                1,
                limiteDimensao / maiorLadoOriginal
            );
            const largura = Math.max(
                1,
                Math.round(imagem.naturalWidth * escala)
            );
            const altura = Math.max(
                1,
                Math.round(imagem.naturalHeight * escala)
            );

            const canvas = document.createElement("canvas");
            canvas.width = largura;
            canvas.height = altura;

            const contexto = canvas.getContext("2d", {
                alpha: false
            });
            if (!contexto) {
                throw new Error("Seu navegador não conseguiu otimizar a foto.");
            }

            contexto.fillStyle = "#ffffff";
            contexto.fillRect(0, 0, largura, altura);
            contexto.drawImage(imagem, 0, 0, largura, altura);

            ultimoBlob = await canvasParaBlob(canvas, qualidade);

            if (ultimoBlob.size <= MAX_FILE_BYTES) {
                const nomeBase = file.name.replace(
                    /\.[^/.]+$/,
                    ""
                );
                return new File(
                    [ultimoBlob],
                    `${nomeBase}.jpg`,
                    {
                        type: "image/jpeg",
                        lastModified: file.lastModified
                    }
                );
            }

            if (qualidade > 0.58) {
                qualidade -= 0.08;
            } else {
                limiteDimensao = Math.max(
                    900,
                    Math.floor(limiteDimensao * 0.82)
                );
                qualidade = 0.72;
            }
        }

        throw new Error(
            "Uma das fotos continua muito pesada após a otimização."
        );
    }

    function renderizarPreview() {
        preview.innerHTML = "";

        if (!arquivos.length) {
            definirInfo(
                "Até 5 fotos — serão otimizadas automaticamente"
            );
        } else {
            definirInfo(
                `${arquivos.length} de ${MAX_FILES} fotos — ` +
                `${formatarTamanho(totalBytes())} no total`
            );
        }

        arquivos.forEach((itemArquivo, index) => {
            const item = document.createElement("div");
            item.className = "preview-item";

            const imagem = document.createElement("img");
            const urlTemporaria = URL.createObjectURL(
                itemArquivo.file
            );
            imagem.src = urlTemporaria;
            imagem.alt = `Foto selecionada ${index + 1}`;
            imagem.addEventListener(
                "load",
                () => URL.revokeObjectURL(urlTemporaria),
                { once: true }
            );

            const remover = document.createElement("button");
            remover.type = "button";
            remover.setAttribute(
                "aria-label",
                `Remover foto ${index + 1}`
            );
            remover.innerHTML =
                '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
            remover.addEventListener("click", () => {
                arquivos.splice(index, 1);
                atualizarInput();
                renderizarPreview();
            });

            item.appendChild(imagem);
            item.appendChild(remover);
            preview.appendChild(item);
        });

        atualizarInput();
    }

    async function adicionarArquivos(novosArquivos) {
        if (form.dataset.uploadProcessando === "1") return;

        form.dataset.uploadProcessando = "1";
        card.setAttribute("aria-busy", "true");
        definirInfo("Otimizando fotos para envio...");

        let ignorados = 0;
        let mensagemErro = "";

        try {
            for (const original of novosArquivos) {
                if (arquivos.length >= MAX_FILES) {
                    ignorados += 1;
                    continue;
                }

                const chave = (
                    `${original.name}-${original.size}-` +
                    `${original.lastModified}`
                );
                const duplicado = arquivos.some(
                    item => item.chave === chave
                );

                if (duplicado) {
                    ignorados += 1;
                    continue;
                }

                try {
                    const otimizado = await otimizarImagem(original);
                    const futuroTotal =
                        totalBytes() + otimizado.size;

                    if (futuroTotal > MAX_TOTAL_BYTES) {
                        ignorados += 1;
                        mensagemErro =
                            "O total das fotos ultrapassaria o limite. " +
                            "Remova uma foto ou escolha outra menor.";
                        continue;
                    }

                    arquivos.push({
                        file: otimizado,
                        chave
                    });
                } catch (error) {
                    ignorados += 1;
                    mensagemErro =
                        error.message ||
                        "Não foi possível preparar uma das fotos.";
                }
            }

            renderizarPreview();

            if (ignorados) {
                definirInfo(
                    mensagemErro ||
                    "Algumas fotos foram ignoradas. Use até 5 imagens válidas.",
                    true
                );
            }
        } finally {
            form.dataset.uploadProcessando = "0";
            card.removeAttribute("aria-busy");
        }
    }

    card.addEventListener("click", () => {
        if (form.dataset.uploadProcessando !== "1") {
            input.click();
        }
    });
    card.addEventListener("keydown", event => {
        if (
            (event.key === "Enter" || event.key === " ") &&
            form.dataset.uploadProcessando !== "1"
        ) {
            event.preventDefault();
            input.click();
        }
    });

    input.addEventListener("change", async () => {
        const selecionados = Array.from(input.files);
        await adicionarArquivos(selecionados);
    });
}

function inicializarModalSucesso() {
    const modal = document.getElementById("modal-sucesso");
    if (!modal) return;

    const botoesFechar = modal.querySelectorAll(
        ".maintenance-success-close, .btn-fechar-sucesso"
    );

    botoesFechar.forEach(botao => {
        botao.addEventListener("click", () => {
            fecharModalManutencao(modal);
        });
    });

    abrirModalManutencao(modal);

    window.setTimeout(() => {
        modal.querySelector(".btn-ver-solicitacoes")?.focus();
    }, 90);
}

function inicializarDetalhesManutencao() {
    const modal = document.getElementById("modal-detalhe");
    if (!modal) return;

    const fechar = modal.querySelector(".close-modal");
    const cancelarForm = document.getElementById(
        "form-cancelar-manutencao"
    );
    const acoesDetalhe = modal.querySelector(".detail-actions");

    fechar?.addEventListener("click", () => {
        fecharModalManutencao(modal);
    });

    document.querySelectorAll(".btn-detalhe").forEach(botao => {
        botao.addEventListener("click", () => {
            preencherTexto("det-brinquedo", botao.dataset.brinquedo);
            preencherTexto("det-descricao", botao.dataset.descricao);
            preencherTexto(
                "det-data",
                `Aberta em ${botao.dataset.data || "data não informada"}`
            );
            preencherTexto("det-telefone", botao.dataset.telefone);
            preencherTexto("det-cep", botao.dataset.cep);
            preencherTexto("det-endereco", botao.dataset.endereco);
            preencherTexto("det-numero", botao.dataset.numero);
            preencherTexto(
                "det-complemento",
                botao.dataset.complemento
                    ? ` (${botao.dataset.complemento})`
                    : ""
            );
            preencherTexto("det-bairro", botao.dataset.bairro);
            preencherTexto("det-cidade", botao.dataset.cidade);
            preencherTexto("det-estado", botao.dataset.estado);
            preencherTexto("cancelar-id", botao.dataset.id, true);

            const codigoStatus = botao.dataset.statusCode || "P";
            const status = document.getElementById("det-status");
            if (status) {
                status.textContent = botao.dataset.status || "";
                status.className =
                    `status-badge status-${codigoStatus}`;
            }

            preencherFotosDetalhe(botao.dataset.imagens);

            const whatsapp = document.getElementById("btn-whatsapp");
            if (whatsapp) {
                const protocolo = String(botao.dataset.id || "").padStart(
                    4,
                    "0"
                );
                const mensagem = encodeURIComponent(
                    `Olá! Gostaria de falar sobre a manutenção #${protocolo} ` +
                    `do equipamento ${botao.dataset.brinquedo || ""}. ` +
                    `Status atual: ${botao.dataset.status || "não informado"}.`
                );
                whatsapp.href =
                    `https://wa.me/5511960563135?text=${mensagem}`;
                whatsapp.style.display = "flex";
                whatsapp.setAttribute(
                    "aria-label",
                    `Falar com a Lazer & Sport sobre a manutenção ${protocolo}`
                );
            }

            const podeCancelar = !["C", "X"].includes(codigoStatus);
            if (cancelarForm) {
                cancelarForm.style.display = podeCancelar ? "block" : "none";
            }
            acoesDetalhe?.classList.toggle(
                "somente-whatsapp",
                !podeCancelar
            );

            abrirModalManutencao(modal);
        });
    });
}

function preencherTexto(id, valor, campoDeFormulario = false) {
    const elemento = document.getElementById(id);
    if (!elemento) return;

    const texto = valor || "";
    if (campoDeFormulario) {
        elemento.value = texto;
    } else {
        elemento.textContent = texto;
    }
}

function preencherFotosDetalhe(jsonImagens) {
    const container = document.getElementById("det-fotos");
    if (!container) return;

    container.innerHTML = "";
    let imagens = [];

    try {
        imagens = JSON.parse(jsonImagens || "[]");
    } catch (error) {
        imagens = [];
    }

    if (!imagens.length) {
        const vazio = document.createElement("span");
        vazio.className = "detalhe-info";
        vazio.textContent = "Nenhuma foto foi enviada.";
        container.appendChild(vazio);
        return;
    }

    imagens.forEach((url, index) => {
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.setAttribute(
            "aria-label",
            `Abrir foto ${index + 1} em tamanho maior`
        );

        const imagem = document.createElement("img");
        imagem.src = url;
        imagem.alt = `Foto da manutenção ${index + 1}`;
        imagem.loading = "lazy";

        link.appendChild(imagem);
        container.appendChild(link);
    });
}
