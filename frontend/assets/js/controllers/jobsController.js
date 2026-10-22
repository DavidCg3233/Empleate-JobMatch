// Empresa: lista de vacantes con sus números y acciones (editar, publicar, pausar, cerrar, eliminar).
import { changeJobStatus, deleteCompanyJob, listCompanyJobs } from "../api/companyApi.js";
import { confirmDialog } from "../components/modal.js";
import { renderNav } from "../components/navbar.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { MODALITY_LABEL, formatDate, formatSalary, jobStatusInfo, timeAgo } from "../utils/format.js";

const allowed = requireRole("empresa");
if (allowed) renderNav("empresa", "jobs");

const list = document.getElementById("job-list");
const tabsBox = document.getElementById("status-tabs");

const TABS = [
  { key: "todas", label: "Todas" },
  { key: "activa", label: "Activas" },
  { key: "pausada", label: "Pausadas" },
  { key: "cerrada", label: "Cerradas" },
];

let jobs = [];
let currentTab = "todas";

// =====================================================================
// Resumen y pestañas
// =====================================================================
function renderKpis() {
  const active = jobs.filter((j) => j.is_visible).length;
  const pending = jobs.filter((j) => j.status !== "cerrada").reduce((sum, j) => sum + j.stats.pending, 0);
  const matches = jobs.reduce((sum, j) => sum + j.stats.matches, 0);
  document.getElementById("kpi-active").textContent = active;
  document.getElementById("kpi-pending").textContent = pending;
  document.getElementById("kpi-matches").textContent = matches;
  document.getElementById("kpi-pending-box").classList.toggle("is-highlight", pending > 0);
}

function renderTabs() {
  tabsBox.replaceChildren(...TABS.map(({ key, label }) => {
    const count = key === "todas" ? jobs.length : jobs.filter((j) => j.status === key).length;
    const active = key === currentTab;
    return el("button", {
      type: "button", class: "tab", role: "tab", "aria-selected": String(active), tabindex: active ? "0" : "-1",
      onclick: () => { currentTab = key; renderTabs(); renderList(); },
    }, label, " ", el("span", { class: "tab-count", textContent: `(${count})` }));
  }));
}

// =====================================================================
// Tarjeta de cada vacante
// =====================================================================
function statusBadge(job) {
  const { label, tone } = jobStatusInfo(job);
  return el("span", { class: `badge badge-${tone}`, textContent: label });
}

function meta(job) {
  const place = job.modality === "remoto" ? "Remoto" : `${job.city} · ${MODALITY_LABEL[job.modality]}`;
  const when = job.published_at ? timeAgo(job.published_at) : "Sin publicar";
  return el("div", { class: "card-meta" },
    el("span", { textContent: `📍 ${place}` }),
    el("span", { textContent: `📄 ${job.contract_type}` }),
    el("span", { textContent: `💰 ${formatSalary(job)}` }),
    el("span", { textContent: `🗓️ ${when}` }),
    job.closes_at ? el("span", { textContent: `⏰ Cierra el ${formatDate(job.closes_at)}` }) : null,
  );
}

function stats(job) {
  const { interested, pending, matches } = job.stats;
  return el("div", { class: "job-stats" },
    el("span", { class: "job-stat", textContent: `👥 ${interested} ${interested === 1 ? "interesado" : "interesados"}` }),
    el("span", { class: `job-stat${pending ? " is-pending" : ""}`, textContent: `⏳ ${pending} por revisar` }),
    el("span", { class: `job-stat${matches ? " is-match" : ""}`, textContent: `💚 ${matches} ${matches === 1 ? "match" : "matches"}` }),
  );
}

function notice(job) {
  if (!job.is_enabled) return el("p", { class: "alert alert-error", textContent: "El administrador deshabilitó esta vacante. Los aspirantes no la ven." });
  if (job.status !== "cerrada" && job.is_expired) {
    return el("p", { class: "alert alert-warning", textContent: "La fecha de cierre ya pasó y los aspirantes no la ven. Edítala para volver a publicarla." });
  }
  if (job.status === "pausada") return el("p", { class: "alert alert-info", textContent: "Pausada: los aspirantes no la ven, pero puedes seguir revisando a los interesados." });
  return null;
}

function actionButton(text, className, handler) {
  const btn = el("button", { type: "button", class: `btn btn-sm ${className}`, textContent: text });
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try { await handler(); } finally { btn.disabled = false; }
  });
  return btn;
}

function actions(job) {
  const canReview = job.is_enabled && job.status !== "cerrada";
  const box = el("div", { class: "company-job-actions" });
  if (canReview) {
    box.append(el("a", {
      href: `swipe.html?job=${job.id}`, class: "btn btn-primary btn-sm",
      textContent: job.stats.pending ? `Revisar candidatos (${job.stats.pending})` : "Buscar candidatos",
    }));
  }
  if (job.stats.matches) box.append(el("a", { href: `matches.html?job=${job.id}`, class: "btn btn-secondary btn-sm", textContent: "Ver matches" }));
  box.append(el("span", { class: "spacer" }));
  box.append(el("a", { href: `job_form.html?id=${job.id}`, class: "btn btn-outline btn-sm", textContent: "Editar" }));

  if (job.is_enabled) {
    if (job.status === "activa") box.append(actionButton("Pausar", "btn-outline", () => setStatus(job, "pausada")));
    if (job.status === "pausada") box.append(actionButton("Publicar", "btn-outline", () => setStatus(job, "activa")));
    if (job.status === "cerrada") box.append(actionButton("Reabrir", "btn-outline", () => setStatus(job, "activa")));
  }
  if (job.status !== "cerrada") box.append(actionButton("Cerrar", "btn-outline", () => closeJob(job)));
  if (job.can_delete) box.append(actionButton("Eliminar", "btn-danger", () => removeJob(job)));
  return box;
}

function jobCard(job) {
  return el("article", { class: `company-job${job.is_visible ? "" : " is-inactive"}`, dataset: { jobId: job.id } },
    el("div", { class: "company-job-head" },
      el("h2", { class: "company-job-title" }, el("a", { href: `job_form.html?id=${job.id}`, textContent: job.title })),
      statusBadge(job),
    ),
    meta(job),
    stats(job),
    notice(job),
    actions(job),
  );
}

function renderList() {
  const visible = currentTab === "todas" ? jobs : jobs.filter((j) => j.status === currentTab);
  if (!jobs.length) {
    list.replaceChildren(el("div", { class: "results-empty" },
      el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "📋" }),
      el("h3", { textContent: "Aún no has publicado vacantes" }),
      el("p", { class: "text-muted", textContent: "Crea tu primera vacante: los aspirantes compatibles la verán en sus tarjetas y podrás revisar a los interesados." }),
      el("a", { href: "job_form.html", class: "btn btn-primary btn-sm", textContent: "Publicar mi primera vacante" }),
    ));
    return;
  }
  if (!visible.length) {
    list.replaceChildren(el("div", { class: "results-empty" },
      el("p", { class: "text-muted", textContent: "No tienes vacantes en este estado." }),
    ));
    return;
  }
  list.replaceChildren(...visible.map(jobCard));
}

function refresh() {
  renderKpis();
  renderTabs();
  renderList();
}

function replaceJob(updated) {
  jobs = jobs.map((j) => (j.id === updated.id ? updated : j));
  refresh();
}

// =====================================================================
// Acciones
// =====================================================================
const STATUS_MESSAGES = {
  activa: "Vacante publicada: los aspirantes ya pueden verla.",
  pausada: "Vacante pausada: dejó de aparecer para los aspirantes.",
  cerrada: "Vacante cerrada.",
};

async function setStatus(job, status) {
  try {
    replaceJob(await changeJobStatus(job.id, status));
    showToast(STATUS_MESSAGES[status], "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function closeJob(job) {
  const ok = await confirmDialog({
    title: "¿Cerrar esta vacante?",
    message: `"${job.title}" dejará de recibir aspirantes. Tus matches se conservan y puedes reabrirla después.`,
    confirmText: "Cerrar vacante",
  });
  if (ok) await setStatus(job, "cerrada");
}

async function removeJob(job) {
  const ok = await confirmDialog({
    title: "¿Eliminar esta vacante?",
    message: `"${job.title}" se borrará para siempre. Esta acción no se puede deshacer.`,
    confirmText: "Eliminar",
    danger: true,
  });
  if (!ok) return;
  try {
    await deleteCompanyJob(job.id);
    jobs = jobs.filter((j) => j.id !== job.id);
    refresh();
    showToast("Vacante eliminada.", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

// =====================================================================
// Inicio
// =====================================================================
async function load() {
  try {
    jobs = await listCompanyJobs();
    refresh();
  } catch (err) {
    list.replaceChildren(el("div", { class: "results-empty" },
      el("h3", { textContent: "No pudimos cargar tus vacantes" }),
      el("p", { class: "text-muted", textContent: err.message }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: load }),
    ));
  }
}

// Mensaje al volver del formulario
const saved = new URLSearchParams(window.location.search).get("saved");
const SAVED_MESSAGES = {
  created: "¡Vacante publicada! Los aspirantes compatibles ya pueden verla.",
  draft: "Vacante guardada sin publicar. Publícala cuando estés listo.",
  updated: "Cambios guardados.",
};
if (allowed && SAVED_MESSAGES[saved]) {
  showToast(SAVED_MESSAGES[saved], "success", 4500);
  history.replaceState(null, "", window.location.pathname);
}

if (allowed) load();
