// Ventana modal reutilizable y diálogo de confirmación.
// const close = openModal({ labelledBy: "id-del-titulo", body: nodo, footer: nodo })
// const ok = await confirmDialog({ title, message, confirmText, danger: true })
import { el } from "../utils/dom.js";

export function openModal({ labelledBy, body, footer = null, className = "", onClose } = {}) {
  const previousFocus = document.activeElement;
  const closeBtn = el("button", { type: "button", class: "modal-close", "aria-label": "Cerrar", textContent: "×" });
  const modal = el("div", { class: `modal ${className}`.trim(), role: "dialog", "aria-modal": "true", "aria-labelledby": labelledBy },
    closeBtn, body, footer,
  );
  const overlay = el("div", { class: "modal-overlay" }, modal);

  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    document.removeEventListener("keydown", onKey);
    overlay.remove();
    if (!document.querySelector(".modal-overlay")) document.body.classList.remove("modal-open");
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
    onClose?.();
  }

  function onKey(e) {
    if (overlay !== [...document.querySelectorAll(".modal-overlay")].pop()) return; // solo la ventana de arriba
    if (e.key === "Escape") close();
    if (e.key === "Tab") { // el foco no se sale de la ventana
      const focusable = modal.querySelectorAll("button:not([disabled]), a[href], input:not([disabled]), select, textarea");
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", onKey);

  document.body.append(overlay);
  document.body.classList.add("modal-open");
  closeBtn.focus();
  return close;
}

let confirmCount = 0;

/** Pregunta antes de una acción importante. Devuelve true si la persona confirma. */
export function confirmDialog({ title, message, confirmText = "Confirmar", cancelText = "Cancelar", danger = false }) {
  return new Promise((resolve) => {
    const titleId = `confirm-title-${++confirmCount}`;
    let answer = false;
    const cancelBtn = el("button", { type: "button", class: "btn btn-outline", textContent: cancelText });
    const okBtn = el("button", { type: "button", class: danger ? "btn btn-danger" : "btn btn-primary", textContent: confirmText });
    const close = openModal({
      labelledBy: titleId,
      className: "modal-sm",
      body: el("div", { class: "modal-body" },
        el("h2", { id: titleId, class: "detail-title", textContent: title }),
        el("p", { class: "text-muted", textContent: message }),
      ),
      footer: el("div", { class: "modal-footer" }, cancelBtn, okBtn),
      onClose: () => resolve(answer),
    });
    cancelBtn.addEventListener("click", close);
    okBtn.addEventListener("click", () => { answer = true; close(); });
    cancelBtn.focus(); // por seguridad, el foco empieza en "Cancelar"
  });
}
