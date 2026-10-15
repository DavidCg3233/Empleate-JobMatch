// Mensajes cortos que aparecen abajo y se ocultan solos.
// Uso: showToast("Guardado", "success") | showToast("Algo falló", "error")

let container = null;

export function showToast(message, type = "info", ms = 3200) {
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    container.setAttribute("role", "status");
    container.setAttribute("aria-live", "polite");
    document.body.append(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast${type === "success" ? " toast-success" : type === "error" ? " toast-error" : ""}`;
  toast.textContent = message;
  container.append(toast);
  setTimeout(() => toast.remove(), ms);
}
