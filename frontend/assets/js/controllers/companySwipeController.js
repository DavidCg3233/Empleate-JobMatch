// Empresa: revisar aspirantes para una vacante (tarjetas tipo Tinder).
// Primero salen quienes dijeron "me interesa" a la vacante; luego, si se quiere, perfiles sugeridos.
import { getCandidates, listCompanyJobs, swipeCandidate, undoCandidateSwipe } from "../api/companyApi.js";
import { createCandidateCard, openCandidateDetail } from "../components/candidateCard.js";
import { createChipFilter } from "../components/filters.js";
import { showMatch } from "../components/matchOverlay.js";
import { renderNav } from "../components/navbar.js";
import { createSwipeDeck } from "../components/swipeDeck.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { initials } from "../utils/format.js";

const allowed = requireRole("empresa");
if (allowed) renderNav("empresa", "swipe");

const jobSelect = document.getElementById("job-select");
let jobs = [];          // vacantes que se pueden revisar (activas o pausadas, habilitadas)
let jobId = null;
let onlyInterested = false;
let loadedJobs = false;

const currentJob = () => jobs.find((j) => j.id === jobId);

// =====================================================================
// Selector de vacante
// =====================================================================
function optionLabel(job) {
  const pending = job.stats.pending ? ` · ${job.stats.pending} por revisar` : "";
  return `${job.title}${job.status === "pausada" ? " (pausada)" : ""}${pending}`;
}

function renderJobOptions() {
  jobSelect.replaceChildren(...jobs.map((j) => new Option(optionLabel(j), j.id, false, j.id === jobId)));
  jobSelect.disabled = jobs.length === 0;
}

function selectJob(id) {
  jobId = id;
  const url = new URL(window.location.href);
  url.searchParams.set("job", id);
  history.replaceState(null, "", url);
  deck.reset();
}

// =====================================================================
// Pantalla vacía
// =====================================================================
function emptyContent({ fetching, loadError, retry }) {
  if (!loadedJobs || fetching) {
    return [el("span", { class: "spinner", "aria-hidden": "true" }), el("p", { textContent: "Buscando candidatos..." })];
  }
  if (loadError) {
    return [
      el("h3", { textContent: "No pudimos cargar los candidatos" }),
      el("p", { textContent: loadError }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: () => (jobs.length ? retry() : loadJobs()) }),
    ];
  }
  if (!jobs.length) {
    return [
      el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "📋" }),
      el("h3", { textContent: "No tienes vacantes abiertas" }),
      el("p", { textContent: "Publica una vacante (o reabre una cerrada) para empezar a revisar candidatos." }),
      el("a", { href: "job_form.html", class: "btn btn-primary btn-sm", textContent: "Publicar vacante" }),
    ];
  }
  return [
    el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "🎉" }),
    el("h3", { textContent: onlyInterested ? "Revisaste a todos los interesados" : "¡Revisaste a todos los candidatos!" }),
    el("p", {
      textContent: onlyInterested
        ? "Mira también los perfiles sugeridos: personas compatibles que aún no han visto tu vacante."
        : "Cuando más aspirantes se interesen en tu vacante, aparecerán aquí.",
    }),
    el("div", { class: "row" },
      onlyInterested
        ? el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Ver perfiles sugeridos", onclick: () => { poolFilter.set("todos"); applyPool("todos"); } })
        : null,
      el("a", { href: `matches.html?job=${jobId}`, class: "btn btn-outline btn-sm", textContent: "Ver matches" }),
      el("a", { href: "jobs.html", class: "btn btn-outline btn-sm", textContent: "Mis vacantes" }),
    ),
  ];
}

// =====================================================================
// Pila de candidatos
// =====================================================================
const deck = createSwipeDeck({
  stage: document.getElementById("stage"),
  emptyBox: document.getElementById("swipe-empty"),
  buttons: {
    like: document.getElementById("btn-like"),
    nope: document.getElementById("btn-nope"),
    undo: document.getElementById("btn-undo"),
    info: document.getElementById("btn-info"),
  },
  getId: (c) => c.applicant_id,
  buildCard: createCandidateCard,
  fetchPage: async (exclude) => (await getCandidates(jobId, { onlyInterested, exclude })).items,
  sendDecision: (c, action) => swipeCandidate(jobId, c.applicant_id, action),
  sendUndo: (c) => undoCandidateSwipe(jobId, c.applicant_id),
  renderEmpty: emptyContent,
  openDetail: (c, decide) => {
    const close = openCandidateDetail(c, {
      onAction: async (action) => {
        close();
        await decide(action);
      },
    });
  },
  onDecided: (c, action, result) => {
    const job = currentJob();
    if (job && c.interested && job.stats.pending > 0) {
      job.stats.pending -= 1; // un interesado menos por revisar
      renderJobOptions();
    }
    if (result.matched) {
      showMatch({
        avatars: ["🏢", initials(c.display_name)],
        message: `A ${c.display_name} también le interesa "${job?.title ?? "tu vacante"}". Ya puedes ver sus datos de contacto y su hoja de vida.`,
        href: `matches.html?job=${jobId}`,
        linkText: "Ver el match",
      });
    }
  },
  messages: { undone: "Listo, el candidato volvió a la pila.", gone: "Este aspirante ya no está disponible." },
});

function applyPool(value) {
  onlyInterested = value === "interesados";
  if (jobId) deck.reset();
}

const poolFilter = createChipFilter(
  document.getElementById("pool-filters"),
  [
    { value: "todos", label: "Todos los perfiles" },
    { value: "interesados", label: "💚 Solo interesados" },
  ],
  { value: "todos", onChange: applyPool },
);

jobSelect.addEventListener("change", () => selectJob(Number(jobSelect.value)));

// =====================================================================
// Inicio
// =====================================================================
async function loadJobs() {
  loadedJobs = false;
  deck.reset({ load: false });
  try {
    const all = await listCompanyJobs();
    jobs = all
      .filter((j) => j.is_enabled && j.status !== "cerrada")
      // Primero las que tienen interesados por revisar; a igual número, las activas antes que las pausadas
      .sort((a, b) => b.stats.pending - a.stats.pending || Number(b.status === "activa") - Number(a.status === "activa"));
    loadedJobs = true;
    const requested = Number(new URLSearchParams(window.location.search).get("job"));
    const initial = jobs.find((j) => j.id === requested) ?? jobs[0];
    jobId = initial?.id ?? null;
    renderJobOptions();
    if (jobId) selectJob(jobId);
    else deck.reset({ load: false });
  } catch (err) {
    loadedJobs = true;
    jobs = [];
    renderJobOptions();
    document.getElementById("swipe-empty").replaceChildren(
      el("h3", { textContent: "No pudimos cargar tus vacantes" }),
      el("p", { textContent: err.message }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: loadJobs }),
    );
  }
}

if (allowed) loadJobs();
