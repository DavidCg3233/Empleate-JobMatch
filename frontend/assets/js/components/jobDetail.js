// Ventana con el detalle completo de una vacante.
// openJobDetail(job, { onAction: async (action) => {...} })  -> devuelve la función para cerrarla.
// Si se pasa onAction, se muestran los botones "No me interesa" / "Me interesa".
import { openModal } from "./modal.js";
import { skillChips } from "./swipecard.js";
import { el } from "../utils/dom.js";
import {
  COMPANY_SIZE_LABEL, MODALITY_LABEL, formatDate, formatExperience, formatLocation, formatSalary, initials, scoreClass, timeAgo,
} from "../utils/format.js";


function section(title, ...content) {
  return el("section", { class: "detail-section" }, el("h3", { class: "card-section-title", textContent: title }), ...content);
}

function infoRow(label, value) {
  return el("div", { class: "detail-info-row" }, el("dt", { textContent: label }), el("dd", { textContent: value }));
}

export function openJobDetail(job, { onAction } = {}) {
  const titleId = `job-detail-title-${job.id}`;

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
      el("p", { class: "hint", textContent: [company.industry, COMPANY_SIZE_LABEL[company.size], company.city].filter(Boolean).join(" · ") }),
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

  return openModal({ labelledBy: titleId, body, footer });
}
