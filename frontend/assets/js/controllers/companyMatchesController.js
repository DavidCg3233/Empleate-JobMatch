// Empresa: matches con datos de contacto y hoja de vida del aspirante.
import { downloadMatchCv, getCompanyMatches, listCompanyJobs } from "../api/companyApi.js";
import { openCandidateDetail } from "../components/candidateCard.js";
import { renderNav } from "../components/navbar.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { formatDate, initials, scoreClass } from "../utils/format.js";

const allowed = requireRole("empresa");
if (allowed) renderNav("empresa", "matches");

const list = document.getElementById("match-list");
const filter = document.getElementById("job-filter");
const countLabel = document.getElementById("match-count");
let loadToken = 0;

async function downloadCv(match) {
  try {
    await downloadMatchCv(match.match_id);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function matchCard(match) {
  const { contact, candidate, job } = match;
  const cvBtn = el("button", { type: "button", class: "btn btn-outline btn-sm", textContent: "📄 Hoja de vida", disabled: !contact.has_cv,
    title: contact.has_cv ? "Descargar la hoja de vida" : "Este aspirante no subió hoja de vida" });
  cvBtn.addEventListener("click", async () => {
    cvBtn.disabled = true;
    try { await downloadCv(match); } finally { cvBtn.disabled = false; }
  });

  return el("article", { class: "match-item match-card", dataset: { matchId: match.match_id } },
    el("div", { class: "match-item-main" },
      el("span", { class: "avatar", "aria-hidden": "true", textContent: initials(contact.full_name) }),
      el("div", { class: "card-heading" },
        el("h3", { class: "match-title", textContent: contact.full_name }),
        el("p", { class: "card-subtitle", textContent: candidate.desired_position || "Sin cargo deseado registrado" }),
        el("p", { class: "match-job", textContent: `Vacante: ${job.title}${job.status === "cerrada" ? " (cerrada)" : ""}` }),
        el("p", { class: "hint", textContent: `Match el ${formatDate(match.matched_at)}` }),
      ),
      el("span", { class: `score-badge score-inline ${scoreClass(candidate.score)}`, title: "Compatibilidad", textContent: `${candidate.score}%` }),
    ),
    el("div", { class: "match-contact" },
      el("p", { class: "card-section-title", textContent: "Contacto" }),
      el("p", {}, "✉️ ", el("a", { href: `mailto:${contact.email}`, textContent: contact.email })),
      contact.phone
        ? el("p", {}, "📞 ", el("a", { href: `tel:${contact.phone.replace(/[^\d+]/g, "")}`, textContent: contact.phone }))
        : el("p", { class: "hint", textContent: "No registró teléfono." }),
    ),
    el("div", { class: "match-actions" },
      el("button", {
        type: "button", class: "btn btn-secondary btn-sm", textContent: "Ver perfil completo",
        onclick: () => openCandidateDetail(candidate, { contact, onDownloadCv: () => downloadCv(match) }),
      }),
      cvBtn,
    ),
  );
}

async function loadMatches() {
  const token = ++loadToken;
  const jobId = filter.value ? Number(filter.value) : null;
  const url = new URL(window.location.href);
  if (jobId) url.searchParams.set("job", jobId);
  else url.searchParams.delete("job");
  history.replaceState(null, "", url);

  list.replaceChildren(el("div", { class: "results-empty" }, el("span", { class: "spinner", "aria-hidden": "true" })));
  try {
    const matches = await getCompanyMatches(jobId);
    if (token !== loadToken) return;
    countLabel.textContent = matches.length === 1 ? "1 match" : `${matches.length} matches`;
    if (!matches.length) {
      list.replaceChildren(el("div", { class: "results-empty" },
        el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "💚" }),
        el("h3", { textContent: jobId ? "Esta vacante aún no tiene matches" : "Aún no tienes matches" }),
        el("p", { class: "text-muted", textContent: "Revisa a los aspirantes interesados: cuando a los dos les interese, aparecerán aquí con sus datos de contacto." }),
        el("a", { href: jobId ? `swipe.html?job=${jobId}` : "swipe.html", class: "btn btn-primary btn-sm", textContent: "Revisar candidatos" }),
      ));
      return;
    }
    list.replaceChildren(...matches.map(matchCard));
  } catch (err) {
    if (token !== loadToken) return;
    countLabel.textContent = "";
    list.replaceChildren(el("div", { class: "results-empty" },
      el("h3", { textContent: "No pudimos cargar tus matches" }),
      el("p", { class: "text-muted", textContent: err.message }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: loadMatches }),
    ));
  }
}

async function init() {
  try {
    const jobs = await listCompanyJobs();
    jobs.forEach((j) => filter.append(new Option(`${j.title} (${j.stats.matches})`, j.id)));
    const requested = new URLSearchParams(window.location.search).get("job");
    if (requested && jobs.some((j) => String(j.id) === requested)) filter.value = requested;
  } catch {
    // Sin la lista de vacantes igual se pueden ver todos los matches
  }
  filter.addEventListener("change", loadMatches);
  loadMatches();
}

if (allowed) init();
