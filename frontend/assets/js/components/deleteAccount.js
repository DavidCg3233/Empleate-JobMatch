// "Zona de peligro" de los perfiles: eliminar la cuenta y todos los datos (Ley 1581 de 2012).
// mountDeleteAccount(document.getElementById("delete-box"), { role: "aspirante" })
import { deleteAccount } from "../api/authApi.js";
import { openModal } from "./modal.js";
import { clearSession } from "../utils/auth.js";
import { el } from "../utils/dom.js";

const WHAT_IS_DELETED = {
  aspirante: "tu perfil, tu hoja de vida, tus decisiones y tus matches",
  empresa: "los datos de la empresa, todas sus vacantes, sus decisiones y sus matches",
};

function openDeleteDialog(role) {
  const titleId = "delete-account-title";
  const password = el("input", { id: "delete-password", type: "password", class: "input", autocomplete: "current-password", maxLength: 128 });
  const understand = el("input", { id: "delete-understand", type: "checkbox" });
  const error = el("p", { class: "field-error hidden", role: "alert" });
  const cancel = el("button", { type: "button", class: "btn btn-outline", textContent: "Cancelar" });
  const submit = el("button", { type: "submit", class: "btn btn-danger", textContent: "Eliminar definitivamente", disabled: true });

  const refresh = () => { submit.disabled = !(understand.checked && password.value); };
  password.addEventListener("input", () => { error.classList.add("hidden"); refresh(); });
  understand.addEventListener("change", refresh);

  const form = el("form", { novalidate: true },
    el("div", { class: "modal-body stack" },
    el("h2", { id: titleId, class: "detail-title", textContent: "Eliminar mi cuenta" }),
    el("p", { textContent: `Se borrarán ${WHAT_IS_DELETED[role]}. Esta acción no se puede deshacer.` }),
    el("div", { class: "field" },
      el("label", { for: "delete-password", class: "label", textContent: "Escribe tu contraseña para confirmar" }),
      password,
      error,
    ),
    el("label", { class: "checkbox", for: "delete-understand" }, understand, " Entiendo que mis datos se eliminarán para siempre."),
    ),
    el("div", { class: "modal-footer" }, cancel, submit),
  );

  const close = openModal({ labelledBy: titleId, className: "modal-sm", body: form });
  cancel.addEventListener("click", close);
  password.focus();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    submit.disabled = true;
    submit.textContent = "Eliminando...";
    try {
      await deleteAccount(password.value);
      clearSession();
      window.location.href = new URL("../../../pages/auth/login.html?cuenta=eliminada", import.meta.url).href;
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
      submit.textContent = "Eliminar definitivamente";
      refresh();
      password.focus();
    }
  });
}

export function mountDeleteAccount(container, { role }) {
  const button = el("button", { type: "button", class: "btn btn-danger", textContent: "Eliminar mi cuenta" });
  button.addEventListener("click", () => openDeleteDialog(role));
  container.replaceChildren(
    el("p", { class: "hint", textContent: `Borra ${WHAT_IS_DELETED[role]}. Podrás registrarte de nuevo con el mismo correo.` }),
    el("div", { class: "form-actions" }, button),
  );
}
