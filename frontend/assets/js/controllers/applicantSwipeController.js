// Pantalla principal del aspirante: tarjetas de vacantes para deslizar (tipo Tinder).
import { getFeed } from "../api/jobApi.js";
import { swipeJob, undoSwipe } from "../api/swipeApi.js";
import { createChipFilter } from "../components/filters.js";
import { openJobDetail } from "../components/jobDetail.js";
import { showMatch } from "../components/matchOverlay.js";
import { renderApplicantNav } from "../components/navbar.js";
import { createSwipeCard } from "../components/swipecard.js";
import { createSwipeDeck } from "../components/swipeDeck.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { initials } from "../utils/format.js";

const allowed = requireRole("aspirante");
if (allowed) renderApplicantNav("swipe");

const filters = {};

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
  const hasFilters = Object.values(filters).some(Boolean);
  return [
    el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "🎉" }),
    el("h3", { textContent: "¡Viste todas las vacantes!" }),
    el("p", {
      textContent: hasFilters
        ? "No hay más vacantes con este filtro. Prueba con otra modalidad."
        : "Vuelve más tarde: las empresas publican vacantes nuevas todos los días.",
    }),
    el("div", { class: "row" },
      hasFilters
        ? el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Ver todas", onclick: () => { modalityFilter.set(""); applyFilter(""); } })
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
  fetchPage: async (exclude) => (await getFeed(filters, exclude)).items,
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

const modalityFilter = createChipFilter(
  document.getElementById("modality-filters"),
  [
    { value: "", label: "Todas" },
    { value: "remoto", label: "🏠 Remoto" },
    { value: "hibrido", label: "🔀 Híbrido" },
    { value: "presencial", label: "🏢 Presencial" },
  ],
  { onChange: applyFilter },
);

if (allowed) deck.reset();
