import { forgotPassword } from "../api/authApi.js";
import { emailError } from "../utils/validators.js";

const form = document.getElementById("forgot-form");
const emailInput = document.getElementById("email");
const submitBtn = document.getElementById("submit-btn");
const errorBox = document.getElementById("error-box");
const sentBox = document.getElementById("sent-box");
const sentMessage = document.getElementById("sent-message");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.classList.add("hidden");

  const email = emailInput.value.trim();
  const problem = emailError(email);
  if (problem) {
    emailInput.classList.add("is-invalid");
    emailInput.focus();
    return showError(problem);
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Enviando...";
  try {
    const { message } = await forgotPassword(email);
    sentMessage.textContent = message;
    form.classList.add("hidden");
    sentBox.classList.remove("hidden");
  } catch (err) {
    showError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Enviar enlace";
  }
});

emailInput.addEventListener("input", () => emailInput.classList.remove("is-invalid"));

document.getElementById("resend-btn").addEventListener("click", () => {
  sentBox.classList.add("hidden");
  form.classList.remove("hidden");
  emailInput.select();
});
