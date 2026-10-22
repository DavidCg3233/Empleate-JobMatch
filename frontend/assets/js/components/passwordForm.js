// Formulario "Cambiar contraseña" para las pantallas de perfil (aspirante y empresa).
// mountChangePassword(document.getElementById("password-box"))
import { changePassword } from "../api/authApi.js";
import { showToast } from "./toast.js";
import { el } from "../utils/dom.js";
import { passwordError } from "../utils/validators.js";

let count = 0;

function passwordField(id, label, autocomplete) {
  const input = el("input", { id, type: "password", class: "input", autocomplete, maxLength: 64 });
  const toggle = el("button", { type: "button", class: "input-toggle", textContent: "Mostrar" });
  toggle.addEventListener("click", () => {
    const hidden = input.type === "password";
    input.type = hidden ? "text" : "password";
    toggle.textContent = hidden ? "Ocultar" : "Mostrar";
  });
  const error = el("p", { class: "field-error hidden" });
  const field = el("div", { class: "field" },
    el("label", { for: id, class: "label", textContent: label }),
    el("div", { class: "input-group" }, input, toggle),
    error,
  );
  return { field, input, error };
}

function setError(f, message) {
  f.error.textContent = message || "";
  f.error.classList.toggle("hidden", !message);
  f.input.classList.toggle("is-invalid", Boolean(message));
}

export function mountChangePassword(container) {
  const n = ++count;
  const current = passwordField(`pwd-current-${n}`, "Contraseña actual", "current-password");
  const next = passwordField(`pwd-new-${n}`, "Nueva contraseña", "new-password");
  const confirm = passwordField(`pwd-confirm-${n}`, "Confirmar nueva contraseña", "new-password");
  const submit = el("button", { type: "submit", class: "btn btn-outline", textContent: "Cambiar contraseña" });

  const form = el("form", { class: "stack", novalidate: true },
    el("div", { class: "form-grid" }, current.field, el("div"), next.field, confirm.field),
    el("p", { class: "hint", textContent: "Mínimo 8 caracteres, con letras y números." }),
    el("div", { class: "form-actions" }, submit),
  );
  [current, next, confirm].forEach((f) => f.input.addEventListener("input", () => setError(f, "")));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopPropagation(); // no dispara el guardado del formulario de perfil
    const errors = [
      [current, current.input.value ? "" : "Escribe tu contraseña actual."],
      [next, passwordError(next.input.value)],
      [confirm, confirm.input.value === next.input.value ? "" : "Las contraseñas no coinciden."],
    ];
    errors.forEach(([f, message]) => setError(f, message));
    const firstInvalid = errors.find(([, message]) => message);
    if (firstInvalid) return firstInvalid[0].input.focus();

    submit.disabled = true;
    submit.textContent = "Guardando...";
    try {
      await changePassword(current.input.value, next.input.value);
      form.reset();
      showToast("Tu contraseña se actualizó.", "success");
    } catch (err) {
      if (/actual/i.test(err.message)) setError(current, err.message);
      else if (/diferente/i.test(err.message)) setError(next, err.message);
      else showToast(err.message, "error");
    } finally {
      submit.disabled = false;
      submit.textContent = "Cambiar contraseña";
    }
  });

  container.replaceChildren(form);
}
