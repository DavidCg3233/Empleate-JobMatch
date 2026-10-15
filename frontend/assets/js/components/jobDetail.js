// Ventana con el detalle completo de una vacante.
// openJobDetail(job, { onAction: async (action) => {...} })  -> devuelve la función para cerrarla.
// Si se pasa onAction, se muestran los botones "No me interesa" / "Me interesa".
import { skillChips } from "./swipecard.js";
import { el } from "../utils/dom.js";
import {
  MODALITY_LABEL, formatDate, formatExperience, formatLocation, formatSalary, initials, scoreClass, timeAgo,
} from "../utils/format.js";

const SIZE_LABEL = {
  "1-10": "1 a 10 empleados", "11-50": "11 a 50 empleados", "51-200": "51 a 200 empleados",
  "201-500": "201 a 500 empleados", "501-1000": "501 a 1000 empleados", "1000+": "Más de 1000 empleados",
};

function section(title, ...content) {
  return el("section", { class: "detail-section" }, el("h3", { class: "card-section-title", textContent: title }), ...content);
}

function infoRow(label, value) {
  return el("div", { class: "detail-info-row" }, el("dt", { textContent: label }), el("dd", { textContent: value }));
}

export function openJobDetail(job, { onAction } = {}) {
  const previousFocus = document.activeElement;
  const titleId = `job-detail-title-${job.id}`;

  const closeBtn = el("button", { type: "button", class: "modal-close", "aria-label": "Cerrar", textContent: "×" });

  // ---------- Contenido ----------
  const required = job.skills.filter((s) => s.is_required);
  const desired = job.skills.filter((s) => !s.is_required);
  const company = job.company;
  const website = company.website && /^https?:\/\//i.test(company.website) ? company.website : null;

  const body = el("div", { class: "modal-body" },
    el("div", { class: "detail-head" },
      el("span", { class: "avatar avatar-lg", "aria-hidden": "true", textContent: initials(company.name) }),
      el("div", { class: "card-heading" },
        el("h2", { id: titleId, class: "detail-title", textContent: job.title }),
        el("p", { class: "card-subtitle", textContent: company.name }),
        el("p", { class: "hint", textContent: timeAgo(job.published_at) }),
      ),
    ),

    !job.is_open ? el("p", { class: "alert alert-warning", textContent: "Esta vacante ya no está recibiendo postulaciones." }) : null,
    job.matched ? el("p", { class: "alert alert-success", textContent: "💚 ¡Tienes match con esta vacante! La empresa también está interesada en tu perfil." }) : null,

    el("div", { class: "detail-score" },
      el("span", { class: `score-badge score-inline ${scoreClass(job.score)}`, textContent: `${job.score}%` }),
      el("div", {},
        el("strong", { textContent: "Compatibilidad con tu perfil" }),
        job.score_reasons.length
          ? el("ul", { class: "detail-reasons" }, job.score_reasons.map((r) => el("li", { textContent: r })))
          : null,
      ),
    ),

    el("dl", { class: "detail-info" },
      infoRow("Ubicación", formatLocation(job)),
      infoRow("Modalidad", MODALITY_LABEL[job.modality]),
      infoRow("Contrato", job.contract_type),
      infoRow("Salario", formatSalary(job)),
      infoRow("Experiencia", formatExperience(job.min_experience_years)),
      infoRow("Educación mínima", job.min_education || "No especificada"),
      job.closes_at ? infoRow("Cierra el", formatDate(job.closes_at)) : null,
    ),

    required.length ? section("Habilidades requeridas", skillChips(required, 50)) : null,
    desired.length ? section("Habilidades deseables", skillChips(desired, 50)) : null,
    section("Descripción", el("p", { class: "detail-text", textContent: job.description })),
    job.requirements ? section("Requisitos", el("p", { class: "detail-text", textContent: job.requirements })) : null,
    section(`Sobre ${company.name}`,
      el("p", { class: "hint", textContent: [company.industry, SIZE_LABEL[company.size], company.city].filter(Boolean).join(" · ") }),
      company.description ? el("p", { class: "detail-text", textContent: company.description }) : null,
      website ? el("a", { href: website, target: "_blank", rel: "noopener noreferrer", textContent: "Visitar sitio web ↗" }) : null,
    ),
  );

  // ---------- Botones ----------
  let footer = null;
  if (onAction && job.is_open && !job.matched) {
    const dislikeBtn = el("button", { type: "button", class: "btn btn-danger" });
    const likeBtn = el("button", { type: "button", class: "btn btn-primary" });
    const paint = () => {
      dislikeBtn.textContent = job.my_action === "dislike" ? "Descartada" : "✕ No me interesa";
      likeBtn.textContent = job.my_action === "like" ? "💚 Te interesa" : "💚 Me interesa";
      dislikeBtn.setAttribute("aria-pressed", String(job.my_action === "dislike"));
      likeBtn.setAttribute("aria-pressed", String(job.my_action === "like"));
    };
    const act = async (action) => {
      dislikeBtn.disabled = likeBtn.disabled = true;
      try {
        await onAction(action);
        paint();
      } catch {
        // quien abrió la ventana ya mostró el mensaje de error
      } finally {
        dislikeBtn.disabled = likeBtn.disabled = false;
      }
    };
    dislikeBtn.addEventListener("click", () => act("dislike"));
    likeBtn.addEventListener("click", () => act("like"));
    paint();
    footer = el("div", { class: "modal-footer" }, dislikeBtn, likeBtn);
  }

  const modal = el("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-labelledby": titleId },
    closeBtn, body, footer,
  );
  const overlay = el("div", { class: "modal-overlay" }, modal);

  // ---------- Abrir / cerrar ----------
  function close() {
    document.removeEventListener("keydown", onKey);
    overlay.remove();
    document.body.classList.remove("modal-open");
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
  }

  function onKey(e) {
    if (e.key === "Escape") close();
    if (e.key === "Tab") { // el foco no se sale de la ventana
      const focusable = modal.querySelectorAll("button:not([disabled]), a[href]");
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
