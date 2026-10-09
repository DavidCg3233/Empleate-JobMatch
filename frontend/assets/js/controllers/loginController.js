import { login } from "../api/authApi.js";
import { redirectByRole, saveSession } from "../utils/auth.js";

const form = document.getElementById("login-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const togglePwd = document.getElementById("toggle-password");

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