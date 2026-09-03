/* Comportamento de gestao / combos_adm.
 *
 * NASCEU DE DENTRO DO HTML. Eram 9 KB de <script> no template --
 * peso repetido a cada abertura da página, que o navegador não tinha
 * como guardar: script dentro do HTML não tem endereço para cachear.
 *
 * O <script src> ficou na MESMA posição do bloco antigo, e sem `defer`
 * de propósito: script clássico externo executa na ordem do documento,
 * igual ao inline. Com `defer` ele passaria para depois da análise da
 * página, e qualquer trecho que dependesse dele antes disso quebraria
 * sem aviso.
 */

(() => {
    const comboModal = document.getElementById("comboModal");
    const deleteModal = document.getElementById("deleteComboModal");
    const comboForm = document.getElementById("comboForm");
    const comboFormAction = document.getElementById("comboFormAction");
    const comboId = document.getElementById("comboId");
    const comboDescription = document.getElementById("comboDescription");
    const comboPriceDisplay = document.getElementById("comboPriceDisplay");
    const normalizedComboPrice = document.getElementById("normalizedComboPrice");
    const comboImage = document.getElementById("comboImage");
    const comboImagePreview = document.getElementById("comboImagePreview");
    const activeCombo = document.getElementById("activeCombo");
    const removeImageRow = document.getElementById("removeComboImageRow");
    const removeImage = document.getElementById("removeComboImage");
    const modalTitle = document.getElementById("comboModalTitle");
    const modalSubtitle = document.getElementById("comboModalSubtitle");
    const saveButton = document.getElementById("saveComboButton");
    const toySearch = document.getElementById("comboToySearch");
    const toyOptions = Array.from(
        document.querySelectorAll(".combo-toy-option")
    );
    const selectedToyCount = document.getElementById("selectedToyCount");
    const deleteComboId = document.getElementById("deleteComboId");
    const deleteComboName = document.getElementById("deleteComboName");
    const deleteConfirmation = document.getElementById(
        "deleteComboConfirmation"
    );
    const deleteButton = document.getElementById("deleteComboButton");

    const selectedToys = () => toyOptions
        .map(option => option.querySelector('input[name="brinquedos"]'))
        .filter(input => input.checked);

    const updateSelectedCount = () => {
        const total = selectedToys().length;
        selectedToyCount.textContent = total
            ? `${total} brinquedo${total > 1 ? "s" : ""} selecionado${total > 1 ? "s" : ""}`
            : "Nenhum brinquedo selecionado";
    };

    const setPageLock = () => {
        const anyOpen = document.querySelector(".combo-modal.is-open");
        document.body.classList.toggle("combo-modal-open", Boolean(anyOpen));
    };

    const openModal = modal => {
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        setPageLock();
    };

    const closeModal = modal => {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        setPageLock();
    };

    const setPreview = imageUrl => {
        comboImagePreview.replaceChildren();
        if (imageUrl) {
            const image = document.createElement("img");
            image.src = imageUrl;
            image.alt = "Prévia do combo";
            comboImagePreview.appendChild(image);
        } else {
            const placeholder = document.createElement("span");
            placeholder.textContent = "🖼️";
            comboImagePreview.appendChild(placeholder);
        }
    };

    const formatCurrency = rawValue => {
        const digits = String(rawValue || "").replace(/\D/g, "");
        const cents = Number(digits || "0") / 100;
        return cents.toLocaleString("pt-BR", {
            style: "currency",
            currency: "BRL"
        });
    };

    const decimalToCurrency = value => {
        const normalized = String(value || "0").replace(",", ".");
        const number = Number.parseFloat(normalized);
        return Number.isFinite(number)
            ? number.toLocaleString("pt-BR", {
                style: "currency",
                currency: "BRL"
            })
            : "R$ 0,00";
    };

    const currencyToDecimal = value => String(value || "")
        .replace(/\s/g, "")
        .replace("R$", "")
        .replace(/\./g, "")
        .replace(",", ".");

    const resetForm = () => {
        comboForm.reset();
        comboFormAction.value = "criar";
        comboId.value = "";
        activeCombo.checked = true;
        removeImage.checked = false;
        removeImageRow.hidden = true;
        comboPriceDisplay.value = "";
        normalizedComboPrice.value = "";
        toySearch.value = "";
        toyOptions.forEach(option => {
            option.hidden = false;
            option.querySelector('input[name="brinquedos"]').checked = false;
        });
        setPreview("");
        updateSelectedCount();
    };

    document.querySelector("[data-open-create]").addEventListener("click", () => {
        resetForm();
        modalTitle.textContent = "Novo combo";
        modalSubtitle.textContent = "Selecione os produtos e defina o valor da oferta.";
        saveButton.textContent = "Criar combo";
        openModal(comboModal);
        window.setTimeout(() => comboDescription.focus(), 120);
    });

    document.querySelectorAll("[data-open-edit]").forEach(button => {
        button.addEventListener("click", () => {
            const card = button.closest(".combo-card");
            const ids = new Set(
                (card.dataset.toys || "").split(",").filter(Boolean)
            );

            resetForm();
            comboFormAction.value = "editar";
            comboId.value = card.dataset.comboId;
            comboDescription.value = card.dataset.description;
            comboPriceDisplay.value = decimalToCurrency(card.dataset.price);
            activeCombo.checked = card.dataset.active === "true";
            removeImageRow.hidden = !card.dataset.image;
            setPreview(card.dataset.image);

            toyOptions.forEach(option => {
                const input = option.querySelector('input[name="brinquedos"]');
                input.checked = ids.has(input.value);
            });
            updateSelectedCount();

            modalTitle.textContent = "Editar combo";
            modalSubtitle.textContent = "Atualize os produtos e os dados da oferta.";
            saveButton.textContent = "Salvar alterações";
            openModal(comboModal);
            window.setTimeout(() => comboDescription.focus(), 120);
        });
    });

    document.querySelectorAll("[data-open-delete]").forEach(button => {
        button.addEventListener("click", () => {
            const card = button.closest(".combo-card");
            deleteComboId.value = card.dataset.comboId;
            deleteComboName.textContent = card.dataset.description;
            deleteConfirmation.value = "";
            deleteButton.disabled = true;
            openModal(deleteModal);
            window.setTimeout(() => deleteConfirmation.focus(), 120);
        });
    });

    document.querySelectorAll("[data-close-combo]").forEach(button => {
        button.addEventListener("click", () => closeModal(comboModal));
    });

    document.querySelectorAll("[data-close-delete]").forEach(button => {
        button.addEventListener("click", () => closeModal(deleteModal));
    });

    comboPriceDisplay.addEventListener("input", event => {
        event.target.value = formatCurrency(event.target.value);
    });

    comboImage.addEventListener("change", event => {
        const [file] = event.target.files;
        if (!file) return;
        setPreview(URL.createObjectURL(file));
        removeImage.checked = false;
    });

    removeImage.addEventListener("change", () => {
        if (removeImage.checked) {
            comboImage.value = "";
            setPreview("");
        }
    });

    toyOptions.forEach(option => {
        option.querySelector("input").addEventListener(
            "change",
            updateSelectedCount
        );
    });

    toySearch.addEventListener("input", event => {
        const query = event.target.value.trim().toLocaleLowerCase("pt-BR");
        toyOptions.forEach(option => {
            option.hidden = !option.dataset.toyName.includes(query);
        });
    });

    comboForm.addEventListener("submit", event => {
        const decimal = currencyToDecimal(comboPriceDisplay.value);
        if (!decimal || Number(decimal) <= 0) {
            event.preventDefault();
            comboPriceDisplay.focus();
            return;
        }

        if (!selectedToys().length) {
            event.preventDefault();
            toySearch.focus();
            selectedToyCount.textContent = "Selecione pelo menos um brinquedo";
            return;
        }

        normalizedComboPrice.value = decimal;
        saveButton.disabled = true;
        saveButton.textContent = "Salvando...";
    });

    deleteConfirmation.addEventListener("input", event => {
        deleteButton.disabled =
            event.target.value.trim().toUpperCase() !== "EXCLUIR";
    });

    document.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        if (deleteModal.classList.contains("is-open")) {
            closeModal(deleteModal);
        } else if (comboModal.classList.contains("is-open")) {
            closeModal(comboModal);
        }
    });
})();
