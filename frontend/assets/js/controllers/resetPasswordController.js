import { resetPassword, validateResetToken } from "../api/authApi.js";
import { passwordError } from "../utils/validators.js";

const checking = document.getElementById("checking");
const invalidBox = document.getElementById("invalid-box");
const invalidMessage = document.getElementById("invalid-message");
const form = document.getElementById("reset-form");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirm");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const successBox = document.getElementById("success-box");

// El token llega en el enlace del correo: reset_password.html?token=...
const token = new URLSearchParams(window.location.search).get("token") || "";
// Se quita de la barra de direcciones para que no quede en el historial
history.replaceState(null, "", window.location.pathname);

function showInvalid(message) {
  checking.classList.add("hidden");
  form.classList.add("hidden");
  invalidMessage.textContent = message;
  invalidBox.classList.remove("hidden");
}

function setFieldError(input, box, message) {
  box.textContent = message || "";
  box.classList.toggle("hidden", !message);
  input.classList.toggle("is-invalid", Boolean(message));
}

async function init() {
  if (token.length < 20) return showInvalid("El enlace no es válido. Solicita uno nuevo.");
  try {
    await validateResetToken(token);
    checking.classList.add("hidden");
    form.classList.remove("hidden");
    passwordInput.focus();
  } catch (err) {
    showInvalid(err.message);
  }
}

document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = btn.parentElement.querySelector("input");
    const hidden = input.type === "password";
    input.type = hidden ? "text" : "password";
    btn.textContent = hidden ? "Ocultar" : "Mostrar";
  });
});

const passwordErrorBox = document.getElementById("password-error");
const confirmErrorBox = document.getElementById("confirm-error");
passwordInput.addEventListener("input", () => setFieldError(passwordInput, passwordErrorBox, ""));
confirmInput.addEventListener("input", () => setFieldError(confirmInput, confirmErrorBox, ""));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.classList.add("hidden");

  const pwdProblem = passwordError(passwordInput.value);
  const confirmProblem = confirmInput.value === passwordInput.value ? "" : "Las contraseñas no coinciden.";
  setFieldError(passwordInput, passwordErrorBox, pwdProblem);
  setFieldError(confirmInput, confirmErrorBox, confirmProblem);
  if (pwdProblem || confirmProblem) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Guardando...";
  try {
    const { message } = await resetPassword(token, passwordInput.value);
    successBox.textContent = `${message} Te llevamos al inicio de sesión...`;
    successBox.classList.remove("hidden");
    setTimeout(() => { window.location.href = "login.html?reset=ok"; }, 2200);
  } catch (err) {
    if (err.status === 400) return showInvalid(err.message); // enlace vencido o ya usado
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
    submitBtn.disabled = false;
    submitBtn.textContent = "Guardar contraseña";
  }
});

init();
