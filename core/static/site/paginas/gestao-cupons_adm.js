/* Comportamento de gestao / cupons_adm.
 *
 * NASCEU DE DENTRO DO HTML. Eram 4 KB de <script> no template --
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
  const couponModal = document.getElementById("couponModal");
  const deleteModal = document.getElementById("deleteModal");
  const couponForm = document.getElementById("couponForm");

  const cupomId = document.getElementById("cupom_id");
  const codigo = document.getElementById("codigo");
  const desconto = document.getElementById("desconto");
  const quantidade = document.getElementById("quantidade");
  const brinquedo = document.getElementById("brinquedo");
  const categoria = document.getElementById("categoria");
  const clientes = document.getElementById("clientes");
  const cupomAtivo = document.getElementById("cupom_ativo");
  const cupomVitrine = document.getElementById("cupom_vitrine");
  const modalTitle = document.getElementById("couponModalTitle");
  const modalSubtitle = document.getElementById("couponModalSubtitle");

  const deleteCupomId = document.getElementById("deleteCupomId");
  const deleteCupomCodigo = document.getElementById("deleteCupomCodigo");
  const deleteConfirmation = document.getElementById("deleteConfirmation");
  const deleteButton = document.getElementById("deleteButton");

  const setPageLock = () => {
    const anyOpen = document.querySelector(".cup-modal.is-open");
    document.body.classList.toggle("cup-modal-open", Boolean(anyOpen));
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

  const resetForm = () => {
    couponForm.reset();
    cupomId.value = "";
    cupomAtivo.checked = true;
    cupomVitrine.checked = false;
  };

  document.querySelector("[data-open-create]").addEventListener("click", () => {
    resetForm();
    modalTitle.textContent = "Novo cupom";
    modalSubtitle.textContent = "Defina o código, o desconto e a quem ele se aplica.";
    openModal(couponModal);
    window.setTimeout(() => codigo.focus(), 120);
  });

  document.querySelectorAll("[data-open-edit]").forEach(button => {
    button.addEventListener("click", () => {
      const card = button.closest(".cup-card");
      resetForm();
      const d = card.dataset;
      cupomId.value = d.cupomId;
      codigo.value = d.codigo;
      desconto.value = d.desconto;
      quantidade.value = d.quantidade;
      cupomAtivo.checked = d.ativo === "1";
      cupomVitrine.checked = d.vitrine === "1";
      brinquedo.value = d.brinquedo || "";
      categoria.value = d.categoria || "";
      const ids = (d.clientes || "").split(",").filter(Boolean);
      for (const option of clientes.options) {
        option.selected = ids.includes(option.value);
      }

      modalTitle.textContent = "Editar cupom";
      modalSubtitle.textContent = "Atualize os dados e salve as alterações.";
      openModal(couponModal);
      window.setTimeout(() => codigo.focus(), 120);
    });
  });

  document.querySelectorAll("[data-close-modal]").forEach(button => {
    button.addEventListener("click", () => closeModal(couponModal));
  });

  document.querySelectorAll("[data-open-delete]").forEach(button => {
    button.addEventListener("click", () => {
      const card = button.closest(".cup-card");
      deleteCupomId.value = card.dataset.cupomId;
      deleteCupomCodigo.textContent = card.dataset.codigo;
      deleteConfirmation.value = "";
      deleteButton.disabled = true;
      openModal(deleteModal);
      window.setTimeout(() => deleteConfirmation.focus(), 120);
    });
  });

  document.querySelectorAll("[data-close-delete]").forEach(button => {
    button.addEventListener("click", () => closeModal(deleteModal));
  });

  deleteConfirmation.addEventListener("input", event => {
    deleteButton.disabled = event.target.value.trim().toUpperCase() !== "EXCLUIR";
  });

  codigo.addEventListener("input", event => {
    event.target.value = event.target.value.toUpperCase();
  });

  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    if (deleteModal.classList.contains("is-open")) {
      closeModal(deleteModal);
    } else if (couponModal.classList.contains("is-open")) {
      closeModal(couponModal);
    }
  });
})();
