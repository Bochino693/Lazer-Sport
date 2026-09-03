/* Comportamento de gestao / promocoes_adm.
 *
 * NASCEU DE DENTRO DO HTML. Eram 7 KB de <script> no template --
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
    const promotionModal = document.getElementById("promotionModal");
    const deleteModal = document.getElementById("deleteModal");
    const promotionForm = document.getElementById("promotionForm");
    const formAction = document.getElementById("formAction");
    const promotionId = document.getElementById("promotionId");
    const description = document.getElementById("description");
    const toy = document.getElementById("toy");
    const priceDisplay = document.getElementById("priceDisplay");
    const normalizedPrice = document.getElementById("normalizedPrice");
    const activePromotion = document.getElementById("activePromotion");
    const promotionImage = document.getElementById("promotionImage");
    const imagePreview = document.getElementById("imagePreview");
    const removeImageRow = document.getElementById("removeImageRow");
    const removeImage = document.getElementById("removeImage");
    const modalTitle = document.getElementById("promotionModalTitle");
    const modalSubtitle = document.getElementById("promotionModalSubtitle");
    const saveButton = document.getElementById("saveButton");
    const deletePromotionId = document.getElementById("deletePromotionId");
    const deletePromotionName = document.getElementById("deletePromotionName");
    const deleteConfirmation = document.getElementById("deleteConfirmation");
    const deleteButton = document.getElementById("deleteButton");

    const setPageLock = () => {
        const anyOpen = document.querySelector(".promo-modal.is-open");
        document.body.classList.toggle("promo-modal-open", Boolean(anyOpen));
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
        imagePreview.replaceChildren();
        if (imageUrl) {
            const image = document.createElement("img");
            image.src = imageUrl;
            image.alt = "Prévia da promoção";
            imagePreview.appendChild(image);
        } else {
            const placeholder = document.createElement("span");
            placeholder.textContent = "🖼️";
            imagePreview.appendChild(placeholder);
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

    const currencyToDecimal = value => {
        const clean = String(value || "")
            .replace(/\s/g, "")
            .replace("R$", "")
            .replace(/\./g, "")
            .replace(",", ".");
        return clean;
    };

    const resetForm = () => {
        promotionForm.reset();
        formAction.value = "criar";
        promotionId.value = "";
        activePromotion.checked = true;
        removeImage.checked = false;
        removeImageRow.hidden = true;
        priceDisplay.value = "";
        normalizedPrice.value = "";
        setPreview("");
    };

    document.querySelector("[data-open-create]").addEventListener("click", () => {
        resetForm();
        modalTitle.textContent = "Nova promoção";
        modalSubtitle.textContent = "Preencha os dados para publicar uma nova oferta.";
        saveButton.textContent = "Criar promoção";
        openModal(promotionModal);
        window.setTimeout(() => description.focus(), 120);
    });

    document.querySelectorAll("[data-open-edit]").forEach(button => {
        button.addEventListener("click", () => {
            const card = button.closest(".promo-card");
            resetForm();

            formAction.value = "editar";
            promotionId.value = card.dataset.promoId;
            description.value = card.dataset.description;
            toy.value = card.dataset.toyId;
            priceDisplay.value = decimalToCurrency(card.dataset.price);
            activePromotion.checked = card.dataset.active === "true";
            removeImageRow.hidden = !card.dataset.image;
            setPreview(card.dataset.image);

            modalTitle.textContent = "Editar promoção";
            modalSubtitle.textContent = "Atualize os dados e salve suas alterações.";
            saveButton.textContent = "Salvar alterações";
            openModal(promotionModal);
            window.setTimeout(() => description.focus(), 120);
        });
    });

    document.querySelectorAll("[data-open-delete]").forEach(button => {
        button.addEventListener("click", () => {
            const card = button.closest(".promo-card");
            deletePromotionId.value = card.dataset.promoId;
            deletePromotionName.textContent = card.dataset.description;
            deleteConfirmation.value = "";
            deleteButton.disabled = true;
            openModal(deleteModal);
            window.setTimeout(() => deleteConfirmation.focus(), 120);
        });
    });

    document.querySelectorAll("[data-close-modal]").forEach(button => {
        button.addEventListener("click", () => closeModal(promotionModal));
    });

    document.querySelectorAll("[data-close-delete]").forEach(button => {
        button.addEventListener("click", () => closeModal(deleteModal));
    });

    priceDisplay.addEventListener("input", event => {
        event.target.value = formatCurrency(event.target.value);
    });

    promotionImage.addEventListener("change", event => {
        const [file] = event.target.files;
        if (!file) return;
        setPreview(URL.createObjectURL(file));
        removeImage.checked = false;
    });

    removeImage.addEventListener("change", () => {
        if (removeImage.checked) {
            promotionImage.value = "";
            setPreview("");
        }
    });

    promotionForm.addEventListener("submit", event => {
        const decimal = currencyToDecimal(priceDisplay.value);
        if (!decimal || Number(decimal) < 0) {
            event.preventDefault();
            priceDisplay.focus();
            return;
        }
        normalizedPrice.value = decimal;
        saveButton.disabled = true;
        saveButton.textContent = "Salvando...";
    });

    deleteConfirmation.addEventListener("input", event => {
        deleteButton.disabled = event.target.value.trim().toUpperCase() !== "EXCLUIR";
    });

    document.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        if (deleteModal.classList.contains("is-open")) {
            closeModal(deleteModal);
        } else if (promotionModal.classList.contains("is-open")) {
            closeModal(promotionModal);
        }
    });
})();
