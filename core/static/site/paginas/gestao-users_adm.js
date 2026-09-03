/* Comportamento de gestao / users_adm.
 *
 * NASCEU DE DENTRO DO HTML. Eram 13 KB de <script> no template --
 * peso repetido a cada abertura da página, que o navegador não tinha
 * como guardar: script dentro do HTML não tem endereço para cachear.
 *
 * O <script src> ficou na MESMA posição do bloco antigo, e sem `defer`
 * de propósito: script clássico externo executa na ordem do documento,
 * igual ao inline. Com `defer` ele passaria para depois da análise da
 * página, e qualquer trecho que dependesse dele antes disso quebraria
 * sem aviso.
 */

LSTela.pronto(function () {
  "use strict";

  const userModal = document.getElementById("userModal");
  const statusModal = document.getElementById("statusModal");
  const deleteModal = document.getElementById("deleteModal");
  const offerModal = document.getElementById("offerModal");
  const userForm = document.getElementById("userForm");

  const usuarioId = document.getElementById("usuario_id");
  const username = document.getElementById("username");
  const email = document.getElementById("email");
  const nomeCompleto = document.getElementById("nome_completo");
  const telefone = document.getElementById("telefone");
  const password = document.getElementById("password");
  const passwordHint = document.getElementById("passwordHint");
  const isActive = document.getElementById("is_active");
  const isStaff = document.getElementById("is_staff");
  const staffCheckRow = document.getElementById("staffCheckRow");
  const superuserNote = document.getElementById("superuserNote");
  const modalTitle = document.getElementById("userModalTitle");
  const modalSubtitle = document.getElementById("userModalSubtitle");

  const statusUserId = document.getElementById("statusUserId");
  const statusNewValue = document.getElementById("statusNewValue");
  const statusConfirmation = document.getElementById("statusConfirmation");
  const statusModalTitle = document.getElementById("statusModalTitle");
  const statusModalSubtitle = document.getElementById("statusModalSubtitle");
  const statusModalText = document.getElementById("statusModalText");
  const statusModalConsequence = document.getElementById("statusModalConsequence");
  const statusButton = document.getElementById("statusButton");

  const deleteUserId = document.getElementById("deleteUserId");
  const deleteUserName = document.getElementById("deleteUserName");
  const deleteConfirmation = document.getElementById("deleteConfirmation");
  const deleteButton = document.getElementById("deleteButton");

  const offerForm = document.getElementById("offerForm");
  const offerUserId = document.getElementById("offerUserId");
  const offerModalSubtitle = document.getElementById("offerModalSubtitle");
  const offerType = document.getElementById("offerType");
  const offerObject = document.getElementById("offerObject");
  const offerEmail = document.getElementById("offerEmail");
  const offerWhatsapp = document.getElementById("offerWhatsapp");
  const offerEmailValue = document.getElementById("offerEmailValue");
  const offerWhatsappValue = document.getElementById("offerWhatsappValue");
  const offerButton = document.getElementById("offerButton");
  const offerError = document.getElementById("offerError");
  const offerSuccess = document.getElementById("offerSuccess");
  const offersNode = document.getElementById("accountOffersData");
  let offers = {};
  try {
    offers = JSON.parse(offersNode ? offersNode.textContent : "{}") || {};
  } catch (_error) {
    offers = {};
  }

  const setPageLock = () => {
    const anyOpen = document.querySelector(".usr-modal.is-open");
    document.body.classList.toggle("usr-modal-open", Boolean(anyOpen));
  };

  const openModal = modal => {
    if (!modal) return;
    document.querySelectorAll(".usr-modal.is-open").forEach(opened => {
      if (opened === modal) return;
      opened.classList.remove("is-open");
      opened.setAttribute("aria-hidden", "true");
    });
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    setPageLock();
  };

  const closeModal = modal => {
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    setPageLock();
  };

  const resetForm = () => {
    userForm.reset();
    usuarioId.value = "";
    isActive.checked = true;
    isStaff.checked = false;
    isStaff.disabled = false;
    staffCheckRow.classList.remove("is-disabled");
    superuserNote.hidden = true;
    password.required = true;
    passwordHint.textContent = "(obrigatória no cadastro, mín. 8 caracteres)";
  };

  const createButton = document.querySelector("[data-open-create]");
  if (createButton) {
    createButton.addEventListener("click", () => {
      resetForm();
      modalTitle.textContent = "Novo usuário";
      modalSubtitle.textContent = "Preencha os dados para criar uma conta.";
      openModal(userModal);
      window.setTimeout(() => username.focus(), 120);
    });
  }

  document.querySelectorAll("[data-open-edit]").forEach(button => {
    button.addEventListener("click", () => {
      resetForm();
      const d = button.dataset;
      usuarioId.value = d.id;
      username.value = d.username;
      email.value = d.email || "";
      nomeCompleto.value = d.nome || "";
      telefone.value = d.telefone || "";
      isStaff.checked = d.staff === "1";
      isActive.checked = d.active === "1";
      password.required = false;
      passwordHint.textContent = "(deixe em branco para manter a atual)";

      const superuser = d.superuser === "1";
      isStaff.disabled = superuser;
      staffCheckRow.classList.toggle("is-disabled", superuser);
      superuserNote.hidden = !superuser;
      if (superuser) isStaff.checked = true;

      modalTitle.textContent = "Editar usuário";
      modalSubtitle.textContent = "Atualize os dados e salve as alterações.";
      openModal(userModal);
      window.setTimeout(() => username.focus(), 120);
    });
  });

  document.querySelectorAll("[data-close-modal]").forEach(button => {
    button.addEventListener("click", () => closeModal(userModal));
  });

  document.querySelectorAll("[data-open-status]").forEach(button => {
    button.addEventListener("click", () => {
      const isCurrentlyActive = button.dataset.active === "1";
      const displayName = button.dataset.name || "esta conta";
      statusUserId.value = button.dataset.id;
      statusNewValue.value = isCurrentlyActive ? "0" : "1";
      statusConfirmation.value = isCurrentlyActive ? "INATIVAR" : "ATIVAR";

      if (isCurrentlyActive) {
        statusModalTitle.textContent = "Inativar conta?";
        statusModalSubtitle.textContent = "O acesso será interrompido imediatamente.";
        statusModalText.textContent = `Confirme a inativação de ${displayName}.`;
        statusModalConsequence.textContent =
          "O cliente não conseguirá entrar, mas pedidos, contatos e histórico continuarão preservados.";
        statusButton.textContent = "Confirmar inativação";
        statusButton.classList.remove("usr-save-button");
        statusButton.classList.add("usr-danger-button");
      } else {
        statusModalTitle.textContent = "Reativar conta?";
        statusModalSubtitle.textContent = "O acesso do cliente será liberado novamente.";
        statusModalText.textContent = `Confirme a reativação de ${displayName}.`;
        statusModalConsequence.textContent =
          "A conta voltará a aceitar login e manterá todo o histórico que já possuía.";
        statusButton.textContent = "Confirmar reativação";
        statusButton.classList.remove("usr-danger-button");
        statusButton.classList.add("usr-save-button");
      }
      openModal(statusModal);
    });
  });

  document.querySelectorAll("[data-close-status]").forEach(button => {
    button.addEventListener("click", () => closeModal(statusModal));
  });

  document.querySelectorAll("[data-open-delete]").forEach(button => {
    button.addEventListener("click", () => {
      deleteUserId.value = button.dataset.id;
      deleteUserName.textContent = button.dataset.name;
      deleteConfirmation.value = "";
      deleteButton.disabled = true;
      openModal(deleteModal);
      window.setTimeout(() => deleteConfirmation.focus(), 120);
    });
  });

  document.querySelectorAll("[data-close-delete]").forEach(button => {
    button.addEventListener("click", () => closeModal(deleteModal));
  });

  if (deleteConfirmation) {
    deleteConfirmation.addEventListener("input", event => {
      deleteButton.disabled = event.target.value.trim().toUpperCase() !== "EXCLUIR";
    });
  }

  const clearOfferFeedback = () => {
    offerError.hidden = true;
    offerError.textContent = "";
    offerSuccess.hidden = true;
    offerSuccess.textContent = "";
  };

  const showOfferError = message => {
    offerError.textContent = message;
    offerError.hidden = false;
  };

  const refreshOfferButton = () => {
    const hasOffer = Boolean(offerObject.value);
    const hasChannel =
      (offerEmail.checked && !offerEmail.disabled) ||
      (offerWhatsapp.checked && !offerWhatsapp.disabled);
    offerButton.disabled = !hasOffer || !hasChannel;
  };

  const fillOfferObjects = () => {
    const items = Array.isArray(offers[offerType.value]) ? offers[offerType.value] : [];
    offerObject.replaceChildren();
    if (!items.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Nenhuma oferta ativa deste tipo";
      offerObject.appendChild(option);
      offerObject.disabled = true;
    } else {
      items.forEach(item => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.rotulo;
        offerObject.appendChild(option);
      });
      offerObject.disabled = false;
    }
    refreshOfferButton();
  };

  offerType.addEventListener("change", () => {
    clearOfferFeedback();
    fillOfferObjects();
  });
  offerObject.addEventListener("change", refreshOfferButton);
  offerEmail.addEventListener("change", refreshOfferButton);
  offerWhatsapp.addEventListener("change", refreshOfferButton);

  document.querySelectorAll("[data-open-offer]").forEach(button => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      clearOfferFeedback();
      const name = button.dataset.name || "cliente";
      const emailAddress = (button.dataset.email || "").trim();
      const phoneNumber = (button.dataset.phone || "").trim();

      offerUserId.value = button.dataset.id;
      offerModalSubtitle.textContent = `Enviar exclusivamente para ${name}.`;
      offerEmailValue.textContent = emailAddress || "Não informado";
      offerWhatsappValue.textContent = phoneNumber || "Não informado";
      offerEmail.disabled = !emailAddress;
      offerWhatsapp.disabled = !phoneNumber;
      offerEmail.checked = Boolean(emailAddress);
      offerWhatsapp.checked = Boolean(phoneNumber);
      const firstAvailableType = ["promocao", "combo", "cupom"].find(type =>
        Array.isArray(offers[type]) && offers[type].length
      );
      offerType.value = firstAvailableType || "promocao";
      fillOfferObjects();

      if (!emailAddress && !phoneNumber) {
        showOfferError(
          "Cadastre um e-mail ou telefone válido nesta conta antes de preparar o envio."
        );
      } else if (!firstAvailableType) {
        showOfferError(
          "Não há promoção, combo ou cupom ativo. Cadastre ou ative uma oferta primeiro."
        );
      }
      openModal(offerModal);
    });
  });

  document.querySelectorAll("[data-close-offer]").forEach(button => {
    button.addEventListener("click", () => closeModal(offerModal));
  });

  offerForm.addEventListener("submit", event => {
    event.preventDefault();
    clearOfferFeedback();
    refreshOfferButton();
    if (offerButton.disabled) {
      showOfferError("Escolha uma oferta e pelo menos um canal disponível.");
      return;
    }

    const originalLabel = offerButton.innerHTML;
    offerButton.disabled = true;
    offerButton.textContent = "Preparando...";

    Painel.enviar(offerForm).then(json => {
      offerSuccess.textContent = `${json.msg} `;
      if (json.detalhe) {
        const detailLink = document.createElement("a");
        detailLink.href = json.detalhe;
        detailLink.textContent = "Acompanhar envio";
        offerSuccess.appendChild(detailLink);
      }
      offerSuccess.hidden = false;
    }).catch(error => {
      showOfferError(error.message || "Não foi possível preparar a oferta agora.");
    }).finally(() => {
      offerButton.innerHTML = originalLabel;
      refreshOfferButton();
    });
  });

  if (telefone) {
    telefone.addEventListener("input", event => {
      let digits = event.target.value.replace(/\D/g, "").slice(0, 11);
      let formatted = digits;
      if (digits.length > 2) {
        formatted = `(${digits.slice(0, 2)})${digits.slice(2)}`;
      }
      if (digits.length > 6 && digits.length <= 10) {
        formatted = `(${digits.slice(0, 2)})${digits.slice(2, 6)}-${digits.slice(6)}`;
      } else if (digits.length > 6) {
        formatted = `(${digits.slice(0, 2)})${digits.slice(2, 7)}-${digits.slice(7)}`;
      }
      event.target.value = formatted;
    });
  }

  if (window.__lsUsersAdminKeydown) {
    document.removeEventListener("keydown", window.__lsUsersAdminKeydown);
  }
  window.__lsUsersAdminKeydown = event => {
    if (event.key !== "Escape") return;
    if (offerModal.classList.contains("is-open")) {
      closeModal(offerModal);
    } else if (deleteModal.classList.contains("is-open")) {
      closeModal(deleteModal);
    } else if (statusModal.classList.contains("is-open")) {
      closeModal(statusModal);
    } else if (userModal.classList.contains("is-open")) {
      closeModal(userModal);
    }
  };
  document.addEventListener("keydown", window.__lsUsersAdminKeydown);
});
