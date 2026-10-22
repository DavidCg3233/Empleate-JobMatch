// Pantalla principal del aspirante: tarjetas de vacantes para deslizar (tipo Tinder).
import { getFeed } from "../api/jobApi.js";
import { swipeJob, undoSwipe } from "../api/swipeApi.js";
import { createChipFilter } from "../components/filters.js";
import { openJobDetail } from "../components/jobDetail.js";
import { RECOMMENDED_MIN } from "../components/matchReasons.js";
import { showMatch } from "../components/matchOverlay.js";
import { renderApplicantNav } from "../components/navbar.js";
import { createSwipeCard } from "../components/swipecard.js";
import { createSwipeDeck } from "../components/swipeDeck.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { initials } from "../utils/format.js";

const allowed = requireRole("aspirante");
if (allowed) renderApplicantNav("swipe");

const filters = { min_score: RECOMMENDED_MIN }; // por defecto solo las recomendadas
let hiddenCount = 0;  // vacantes de baja compatibilidad que no se están mostrando

function emptyContent({ fetching, loadError, retry }) {
  if (fetching) {
    return [el("span", { class: "spinner", "aria-hidden": "true" }), el("p", { textContent: "Buscando vacantes para ti..." })];
  }
  if (loadError) {
    return [
      el("h3", { textContent: "No pudimos cargar las vacantes" }),
      el("p", { textContent: loadError }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: () => retry() }),
    ];
  }
  const onlyRecommended = Boolean(filters.min_score);
  const hasModality = Boolean(filters.modality);
  let message = "Vuelve más tarde: las empresas publican vacantes nuevas todos los días.";
  if (onlyRecommended && hiddenCount) {
    message = `Hay ${hiddenCount} ${hiddenCount === 1 ? "vacante" : "vacantes"} más con baja compatibilidad con tu perfil. Puedes verlas o completar tu perfil para mejorar tus recomendaciones.`;
  } else if (hasModality) {
    message = "No hay más vacantes con esta modalidad. Prueba con otra.";
  }
  return [
    el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "🎉" }),
    el("h3", { textContent: onlyRecommended ? "¡Viste todas tus vacantes recomendadas!" : "¡Viste todas las vacantes!" }),
    el("p", { textContent: message }),
    el("div", { class: "row" },
      onlyRecommended && hiddenCount
        ? el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Ver también las de baja compatibilidad", onclick: () => { matchFilter.set("todas"); applyMatch("todas"); } })
        : null,
      hasModality
        ? el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Todas las modalidades", onclick: () => { modalityFilter.set(""); applyFilter(""); } })
        : null,
      onlyRecommended && hiddenCount
        ? el("a", { href: "profile.html", class: "btn btn-outline btn-sm", textContent: "Completar mi perfil" })
        : null,
      el("a", { href: "search.html", class: "btn btn-outline btn-sm", textContent: "Ir al buscador" }),
      el("a", { href: "matches.html", class: "btn btn-outline btn-sm", textContent: "Mis matches" }),
    ),
  ];
}

const deck = createSwipeDeck({
  stage: document.getElementById("stage"),
  emptyBox: document.getElementById("swipe-empty"),
  buttons: {
    like: document.getElementById("btn-like"),
    nope: document.getElementById("btn-nope"),
    undo: document.getElementById("btn-undo"),
    info: document.getElementById("btn-info"),
  },
  getId: (job) => job.id,
  buildCard: createSwipeCard,
  fetchPage: async (exclude) => {
    const page = await getFeed(filters, exclude);
    hiddenCount = page.hidden_count || 0;
    return page.items;
  },
  sendDecision: (job, action) => swipeJob(job.id, action),
  sendUndo: (job) => undoSwipe(job.id),
  renderEmpty: emptyContent,
  openDetail: (job, decide) => {
    const close = openJobDetail(job, {
      onAction: async (action) => {
        close();
        await decide(action);
      },
    });
  },
  onDecided: (job, action, result) => {
    if (result.matched) {
      showMatch({
        avatars: ["Tú", initials(job.company.name)],
        message: `A ${job.company.name} también le interesa tu perfil para "${job.title}".`,
        href: "matches.html",
        linkText: "Ver mis matches",
        keepText: "Seguir explorando",
      });
    }
  },
  messages: { undone: "Listo, la vacante volvió a la pila.", gone: "Esa vacante ya no está disponible." },
});

function applyFilter(modality) {
  if (modality) filters.modality = modality;
  else delete filters.modality;
  deck.reset({ keepHistory: true });
}

function applyMatch(value) {
  if (value === "recomendadas") filters.min_score = RECOMMENDED_MIN;
  else delete filters.min_score;
  deck.reset({ keepHistory: true });
}

const matchFilter = createChipFilter(
  document.getElementById("match-filters"),
  [
    { value: "recomendadas", label: `✨ Recomendadas (${RECOMMENDED_MIN}% o más)` },
    { value: "todas", label: "Todas las vacantes" },
  ],
  { value: "recomendadas", onChange: applyMatch },
);

const modalityFilter = createChipFilter(
  document.getElementById("modality-filters"),
  [
    { value: "", label: "Cualquier modalidad" },
    { value: "remoto", label: "🏠 Remoto" },
    { value: "hibrido", label: "🔀 Híbrido" },
    { value: "presencial", label: "🏢 Presencial" },
  ],
  { onChange: applyFilter },
);

if (allowed) deck.reset();
