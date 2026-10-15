import { getMe, login } from "../api/authApi.js";
import { clearSession, getToken, isTokenExpired, redirectByRole, saveSession } from "../utils/auth.js";

const form = document.getElementById("login-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const togglePwd = document.getElementById("toggle-password");
const infoBox = document.getElementById("info-box");

// Si ya hay una sesión válida, se envía directo a su pantalla según el rol
if (getToken() && isTokenExpired()) {
  clearSession();
} else if (getToken()) {
  getMe()
    .then((me) => redirectByRole(me.role))
    .catch(() => clearSession()); // token vencido o inválido: se queda en el login
}

// Mensajes que llegan desde otras pantallas (ej: después de cambiar la contraseña)
const params = new URLSearchParams(window.location.search);
if (params.get("reset") === "ok") {
  infoBox.textContent = "Tu contraseña se actualizó. Ya puedes iniciar sesión.";
  infoBox.classList.remove("hidden");
}
if (params.get("email")) emailInput.value = params.get("email");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

togglePwd.addEventListener("click", () => {
  const isHidden = passwordInput.type === "password";
  passwordInput.type = isHidden ? "text" : "password";
  togglePwd.textContent = isHidden ? "Ocultar" : "Mostrar";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();
  infoBox.classList.add("hidden");

  if (!emailInput.value.trim() || !passwordInput.value) {
    showError("Escribe tu correo y tu contraseña.");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Ingresando...";

  try {
    const data = await login(emailInput.value.trim(), passwordInput.value);
    saveSession(data);
    redirectByRole(data.role);
  } catch (err) {
    showError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Iniciar sesión";
  }
});