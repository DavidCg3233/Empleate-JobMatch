// Tarjetas de vacante: la de deslizar (pantalla tipo Tinder) y la de la lista del buscador.
import { cardReason } from "./matchReasons.js";
import { el } from "../utils/dom.js";
import {
  MODALITY_LABEL, formatExperience, formatLocation, formatSalary, initials, scoreClass, timeAgo,
} from "../utils/format.js";

const MAX_CARD_SKILLS = 8;

function scoreBadge(score, extraClass = "") {
  return el("span", {
    class: `score-badge ${scoreClass(score)} ${extraClass}`.trim(),
    title: "Compatibilidad con tu perfil",
    "aria-label": `Compatibilidad con tu perfil: ${score}%`,
    textContent: `${score}%`,
  });
}

function metaList(job) {
  return el("div", { class: "card-meta" },
    el("span", { textContent: `📍 ${formatLocation(job)}` }),
    el("span", { textContent: `💼 ${MODALITY_LABEL[job.modality]}` }),
    el("span", { textContent: `📄 ${job.contract_type}` }),
    el("span", { textContent: `💰 ${formatSalary(job)}` }),
    el("span", { textContent: `⏳ ${formatExperience(job.min_experience_years)}` }),
  );
}

export function skillChips(skills, max = MAX_CARD_SKILLS) {
  const chips = el("div", { class: "chips" });
  skills.slice(0, max).forEach((s) => {
    chips.append(el("span", {
      class: s.matched ? "chip chip-match" : "chip chip-neutral",
      title: `${s.is_required ? "Requerida" : "Deseable"}${s.matched ? " · la tienes en tu perfil" : ""}`,
      textContent: s.matched ? `✓ ${s.name}` : s.name,
    }));
  });
  if (skills.length > max) chips.append(el("span", { class: "chip chip-neutral", textContent: `+${skills.length - max}` }));
  return chips;
}

/** Tarjeta para deslizar. El botón "Ver detalle" lleva data-action="detail". */
export function createSwipeCard(job) {
  return el("article", { class: "swipe-card", dataset: { jobId: job.id }, "aria-label": `${job.title} en ${job.company.name}` },
    el("span", { class: "swipe-stamp like", "aria-hidden": "true", textContent: "ME INTERESA" }),
    el("span", { class: "swipe-stamp nope", "aria-hidden": "true", textContent: "NO" }),
    scoreBadge(job.score),
    el("div", { class: "card-head" },
      el("span", { class: "avatar", "aria-hidden": "true", textContent: initials(job.company.name) }),
      el("div", { class: "card-heading" },
        el("h3", { textContent: job.title }),
        el("p", { class: "card-subtitle", textContent: job.company.name }),
      ),
    ),
    el("div", { class: "card-body" },
      metaList(job),
      job.skills.length ? el("div", {},
        el("p", { class: "card-section-title", textContent: "Habilidades" }),
        skillChips(job.skills),
      ) : null,
      cardReason(job, "aspirante"),
      el("div", {},
        el("p", { class: "card-section-title", textContent: "La vacante" }),
        el("p", { class: "card-summary", textContent: job.description }),
      ),
    ),
    el("div", { class: "card-footer" },
      el("span", { class: "hint", textContent: timeAgo(job.published_at) }),
      el("button", { type: "button", class: "btn btn-secondary btn-sm", dataset: { action: "detail" }, textContent: "Ver detalle" }),
    ),
  );
}

/** Tarjeta de la lista del buscador. handlers: { onOpen(job), onAction(job, action) } */
export function createJobItem(job, { onOpen, onAction }) {
  const likeBtn = el("button", {
    type: "button", class: "btn btn-sm job-like", "aria-pressed": String(job.my_action === "like"),
    textContent: job.my_action === "like" ? "💚 Te interesa" : "Me interesa",
    disabled: job.matched,
    onclick: () => onAction(job, "like"),
  });
  const dislikeBtn = el("button", {
    type: "button", class: "btn btn-sm job-dislike", "aria-pressed": String(job.my_action === "dislike"),
    textContent: job.my_action === "dislike" ? "Descartada" : "No me interesa",
    disabled: job.matched,
    onclick: () => onAction(job, "dislike"),
  });

  const title = el("button", { type: "button", class: "job-item-title", textContent: job.title, onclick: () => onOpen(job) });

  return el("article", { class: `job-item${job.my_action === "dislike" ? " is-discarded" : ""}`, dataset: { jobId: job.id } },
    el("div", { class: "job-item-head" },
      el("span", { class: "avatar", "aria-hidden": "true", textContent: initials(job.company.name) }),
      el("div", { class: "job-item-heading" },
        title,
        el("p", { class: "card-subtitle", textContent: job.company.name }),
      ),
      scoreBadge(job.score, "score-inline"),
    ),
    metaList(job),
    job.skills.length ? skillChips(job.skills, 6) : null,
    el("div", { class: "job-item-footer" },
      el("div", { class: "job-item-status" },
        job.matched
          ? el("span", { class: "badge badge-success", textContent: "💚 ¡Tienes match!" })
          : el("span", { class: "hint", textContent: timeAgo(job.published_at) }),
        el("button", { type: "button", class: "btn-link", textContent: "Ver detalle →", onclick: () => onOpen(job) }),
      ),
      job.matched ? null : el("div", { class: "job-item-actions" }, dislikeBtn, likeBtn),
    ),
  );
}
