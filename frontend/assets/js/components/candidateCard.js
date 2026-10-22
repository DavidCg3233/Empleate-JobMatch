// Aspirantes vistos por la empresa: tarjeta para deslizar y ventana con el perfil completo.
import { openModal } from "./modal.js";
import { el } from "../utils/dom.js";
import { MODALITY_LABEL, formatPeriod, formatYears, initials, scoreClass } from "../utils/format.js";

function candidateSkillChips(skills, max = 8) {
  const chips = el("div", { class: "chips" });
  skills.slice(0, max).forEach((s) => chips.append(el("span", {
    class: s.matched ? "chip chip-match" : "chip chip-neutral",
    title: s.matched ? "La vacante pide esta habilidad" : "",
    textContent: s.matched ? `✓ ${s.name}` : s.name,
  })));
  if (skills.length > max) chips.append(el("span", { class: "chip chip-neutral", textContent: `+${skills.length - max}` }));
  return chips;
}

function interestBadge(c) {
  if (c.matched) return el("span", { class: "badge badge-success", textContent: "💚 Match" });
  return c.interested
    ? el("span", { class: "badge badge-success", textContent: "💚 Le interesa tu vacante" })
    : el("span", { class: "badge", textContent: "✨ Perfil sugerido" });
}

function metaList(c) {
  return el("div", { class: "card-meta" },
    el("span", { textContent: `📍 ${c.city || "Ciudad no indicada"}` }),
    el("span", { textContent: `⏳ ${formatYears(c.experience_years)}${c.experience_years ? " de experiencia" : ""}` }),
    el("span", { textContent: `🎓 ${c.education_level || "Sin estudios registrados"}` }),
    c.willing_to_relocate ? el("span", { textContent: "🚚 Acepta trasladarse" }) : null,
  );
}

/** Tarjeta para deslizar. El botón "Ver perfil" lleva data-action="detail". */
export function createCandidateCard(c) {
  const latest = c.experiences[0];
  const reasons = c.score_reasons.slice(0, 2);
  return el("article", { class: "swipe-card candidate-card", dataset: { applicantId: c.applicant_id }, "aria-label": `Perfil de ${c.display_name}` },
    el("span", { class: "swipe-stamp like", "aria-hidden": "true", textContent: "ME INTERESA" }),
    el("span", { class: "swipe-stamp nope", "aria-hidden": "true", textContent: "NO" }),
    el("span", { class: `score-badge ${scoreClass(c.score)}`, title: "Compatibilidad con la vacante", textContent: `${c.score}%` }),
    el("div", { class: "card-head" },
      el("span", { class: "avatar", "aria-hidden": "true", textContent: initials(c.display_name) }),
      el("div", { class: "card-heading" },
        el("h3", { textContent: c.display_name }),
        el("p", { class: "card-subtitle", textContent: c.desired_position || "Sin cargo deseado registrado" }),
      ),
    ),
    el("div", { class: "card-body" },
      el("div", {}, interestBadge(c)),
      metaList(c),
      c.skills.length ? el("div", {},
        el("p", { class: "card-section-title", textContent: "Habilidades" }),
        candidateSkillChips(c.skills),
      ) : null,
      reasons.length ? el("p", { class: "ai-reason" }, el("strong", { textContent: "Por qué encaja: " }), reasons.join(" · ")) : null,
      latest ? el("div", {},
        el("p", { class: "card-section-title", textContent: "Experiencia reciente" }),
        el("p", { class: "card-summary", textContent: `${latest.position} · ${latest.company_name} (${formatPeriod(latest.start_date, latest.end_date, latest.is_current)})` }),
      ) : null,
      c.summary ? el("div", {},
        el("p", { class: "card-section-title", textContent: "Perfil" }),
        el("p", { class: "card-summary", textContent: c.summary }),
      ) : null,
    ),
    el("div", { class: "card-footer" },
      el("span", { class: "hint", textContent: `${c.experiences.length} experiencia(s) · ${c.educations.length} estudio(s)` }),
      el("button", { type: "button", class: "btn btn-secondary btn-sm", dataset: { action: "detail" }, textContent: "Ver perfil" }),
    ),
  );
}

// =====================================================================
// Perfil completo
// =====================================================================
function section(title, ...content) {
  return el("section", { class: "detail-section" }, el("h3", { class: "card-section-title", textContent: title }), ...content);
}

function infoRow(label, value) {
  return el("div", { class: "detail-info-row" }, el("dt", { textContent: label }), el("dd", { textContent: value }));
}

function timeline(items, render) {
  return el("ul", { class: "timeline" }, items.map((item) => el("li", {}, ...render(item))));
}

/**
 * openCandidateDetail(candidato, {
 *   contact,                 // datos de contacto (solo con match)
 *   onDownloadCv,            // async () => {} para descargar la hoja de vida
 *   onAction,                // async (action) => {}  muestra los botones Me interesa / No me interesa
 * })
 */
export function openCandidateDetail(c, { contact = null, onDownloadCv = null, onAction = null } = {}) {
  const titleId = `candidate-title-${c.applicant_id}`;

  let contactSection = null;
  if (contact) {
    const cvButton = contact.has_cv && onDownloadCv
      ? el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "📄 Descargar hoja de vida" })
      : null;
    cvButton?.addEventListener("click", async () => {
      cvButton.disabled = true;
      try { await onDownloadCv(); } finally { cvButton.disabled = false; }
    });
    contactSection = el("div", { class: "match-contact" },
      el("p", { class: "card-section-title", textContent: "Datos de contacto" }),
      el("p", {}, el("strong", { textContent: contact.full_name })),
      el("p", {}, "✉️ ", el("a", { href: `mailto:${contact.email}`, textContent: contact.email })),
      contact.phone ? el("p", {}, "📞 ", el("a", { href: `tel:${contact.phone.replace(/[^\d+]/g, "")}`, textContent: contact.phone })) : null,
      cvButton ? el("div", { class: "mt-1" }, cvButton) : el("p", { class: "hint", textContent: "No subió hoja de vida." }),
    );
  }

  const body = el("div", { class: "modal-body" },
    el("div", { class: "detail-head" },
      el("span", { class: "avatar avatar-lg", "aria-hidden": "true", textContent: initials(c.display_name) }),
      el("div", { class: "card-heading" },
        el("h2", { id: titleId, class: "detail-title", textContent: c.display_name }),
        el("p", { class: "card-subtitle", textContent: c.desired_position || "Sin cargo deseado registrado" }),
        el("div", { class: "mt-1" }, interestBadge(c)),
      ),
    ),
    !contact ? el("p", { class: "hint", textContent: "🔒 Su nombre completo, contacto y hoja de vida se muestran cuando hay match." }) : null,
    contactSection,

    el("div", { class: "detail-score" },
      el("span", { class: `score-badge score-inline ${scoreClass(c.score)}`, textContent: `${c.score}%` }),
      el("div", {},
        el("strong", { textContent: "Compatibilidad con la vacante" }),
        c.score_reasons.length ? el("ul", { class: "detail-reasons" }, c.score_reasons.map((r) => el("li", { textContent: r }))) : null,
      ),
    ),

    el("dl", { class: "detail-info" },
      infoRow("Ciudad", c.city || "No indicada"),
      infoRow("Experiencia total", formatYears(c.experience_years)),
      infoRow("Educación más alta", c.education_level || "Sin registrar"),
      infoRow("Modalidad preferida", c.desired_modality ? MODALITY_LABEL[c.desired_modality] : "Sin preferencia"),
      infoRow("Traslado", c.willing_to_relocate ? "Acepta trasladarse" : "No indicó"),
    ),

    c.summary ? section("Perfil profesional", el("p", { class: "detail-text", textContent: c.summary })) : null,

    section("Experiencia",
      c.experiences.length
        ? timeline(c.experiences, (e) => [
          el("strong", { textContent: e.position }),
          el("p", { class: "text-muted", textContent: `${e.company_name} · ${formatPeriod(e.start_date, e.end_date, e.is_current)}` }),
          e.description ? el("p", { class: "detail-text", textContent: e.description }) : null,
        ])
        : el("p", { class: "text-muted", textContent: "No registra experiencia laboral." }),
    ),

    section("Educación",
      c.educations.length
        ? timeline(c.educations, (e) => [
          el("strong", { textContent: e.degree }),
          el("p", { class: "text-muted", textContent: [e.institution, e.level, e.field_of_study, formatPeriod(e.start_date, e.end_date)].filter(Boolean).join(" · ") }),
        ])
        : el("p", { class: "text-muted", textContent: "No registra estudios." }),
    ),

    section("Habilidades",
      c.skills.length ? candidateSkillChips(c.skills, 60) : el("p", { class: "text-muted", textContent: "No registra habilidades." }),
    ),

    c.languages.length
      ? section("Idiomas", el("div", { class: "chips" }, c.languages.map((l) => el("span", { class: "chip chip-neutral", textContent: `${l.name} · ${l.proficiency}` }))))
      : null,
  );

  let footer = null;
  if (onAction && !c.matched) {
    const dislikeBtn = el("button", { type: "button", class: "btn btn-danger", textContent: "✕ No me interesa" });
    const likeBtn = el("button", { type: "button", class: "btn btn-primary", textContent: "💚 Me interesa" });
    const act = async (action) => {
      dislikeBtn.disabled = likeBtn.disabled = true;
      try {
        await onAction(action);
      } catch {
        // quien abrió la ventana ya mostró el mensaje de error
      } finally {
        dislikeBtn.disabled = likeBtn.disabled = false;
      }
    };
    dislikeBtn.addEventListener("click", () => act("dislike"));
    likeBtn.addEventListener("click", () => act("like"));
    footer = el("div", { class: "modal-footer" }, dislikeBtn, likeBtn);
  }

  return openModal({ labelledBy: titleId, body, footer });
}
