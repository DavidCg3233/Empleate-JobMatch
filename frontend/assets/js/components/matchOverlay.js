// Ventana de celebración "¡Es un match!".
// showMatch({ avatars: ["Tú", "SA"], message: "...", href: "matches.html", linkText: "Ver mis matches" })
import { el } from "../utils/dom.js";

export function showMatch({ avatars, message, href, linkText, keepText = "Seguir revisando" }) {
  const previousFocus = document.activeElement;
  const keepBtn = el("button", { type: "button", class: "btn btn-outline btn-block", textContent: keepText });
  const overlay = el("div", { class: "match-overlay" },
    el("div", { class: "match-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "match-title" },
      el("h2", { id: "match-title", textContent: "¡Es un match!" }),
      el("div", { class: "match-avatars", "aria-hidden": "true" },
        avatars.map((text) => el("span", { class: "avatar", textContent: text })),
      ),
      el("p", { textContent: message }),
      el("div", { class: "stack" },
        el("a", { href, class: "btn btn-primary btn-block", textContent: linkText }),
        keepBtn,
      ),
    ),
  );
  const close = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    previousFocus?.focus?.();
  };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  keepBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", onKey);
  document.body.append(overlay);
  keepBtn.focus();
}
