// Pantalla principal del aspirante: tarjetas de vacantes para deslizar (tipo Tinder).
// Derecha / botón 💚 = me interesa · Izquierda / botón ✕ = no me interesa · ↺ = deshacer.
import { getFeed } from "../api/jobApi.js";
import { swipeJob, undoSwipe } from "../api/swipeApi.js";
import { createChipFilter } from "../components/filters.js";
import { openJobDetail } from "../components/jobDetail.js";
import { renderApplicantNav } from "../components/navbar.js";
import { createSwipeCard } from "../components/swipecard.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { initials } from "../utils/format.js";

const allowed = requireRole("aspirante");
if (allowed) renderApplicantNav("swipe");

const FEED_SIZE = 20;          // tarjetas que devuelve el backend por pedido
const REFILL_AT = 3;           // con estas tarjetas o menos se piden más
const SWIPE_THRESHOLD = 110;   // px que hay que arrastrar para decidir

const stage = document.getElementById("stage");
const emptyBox = document.getElementById("swipe-empty");
const btnLike = document.getElementById("btn-like");
const btnNope = document.getElementById("btn-nope");
const btnUndo = document.getElementById("btn-undo");
const btnInfo = document.getElementById("btn-info");

let queue = [];            // vacantes en pantalla; queue[0] es la de arriba (último hijo del stage)
let history = [];          // decisiones tomadas, para deshacer
const cards = new Map();   // id de vacante -> elemento de la tarjeta
let busy = false;          // hay una decisión enviándose
let fetching = false;
let exhausted = false;     // el backend ya no tiene más vacantes con estos filtros
let loadError = "";
let feedToken = 0;         // cambia con cada filtro nuevo: descarta respuestas viejas
const filters = {};

// =====================================================================
// Tarjetas
// =====================================================================
const topCard = () => (queue.length ? cards.get(queue[0].id) : null);

function buildCard(job) {
  const card = createSwipeCard(job);
  cards.set(job.id, card);
  return card;
}

/** Agrega vacantes al fondo de la pila (debajo de las que ya están). */
function addToBottom(jobs) {
  const fresh = jobs.filter((job) => !queue.some((q) => q.id === job.id));
  queue.push(...fresh);
  // El fondo de la pila es justo después del recuadro "sin vacantes" (primer hijo)
  emptyBox.after(...fresh.slice().reverse().map(buildCard));
  return fresh.length;
}

function clearCards() {
  cards.forEach((card) => card.remove());
  cards.clear();
  queue = [];
}

// =====================================================================
// Estado de la pantalla
// =====================================================================
function emptyContent() {
  if (fetching) {
    return [el("span", { class: "spinner", "aria-hidden": "true" }), el("p", { textContent: "Buscando vacantes para ti..." })];
  }
  if (loadError) {
    return [
      el("h3", { textContent: "No pudimos cargar las vacantes" }),
      el("p", { textContent: loadError }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: resetFeed }),
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

function updateView() {
  const empty = queue.length === 0;
  emptyBox.hidden = !empty;
  if (empty) emptyBox.replaceChildren(...emptyContent());
  btnLike.disabled = btnNope.disabled = btnInfo.disabled = empty || busy;
  btnUndo.disabled = history.length === 0 || busy;
}

// =====================================================================
// Cargar vacantes
// =====================================================================
async function fetchMore() {
  const token = feedToken;
  fetching = true;
  loadError = "";
  updateView();
  try {
    const { items } = await getFeed(filters, queue.map((job) => job.id));
    if (token !== feedToken) return;
    addToBottom(items);
    exhausted = items.length < FEED_SIZE;
  } catch (err) {
    if (token !== feedToken) return;
    loadError = err.message;
  } finally {
    if (token === feedToken) {
      fetching = false;
      updateView();
    }
  }
}

function maybeLoadMore() {
  if (!fetching && !exhausted && !loadError && queue.length <= REFILL_AT) fetchMore();
}

function resetFeed() {
  feedToken++;
  fetching = false;
  exhausted = false;
  loadError = "";
  clearCards();
  fetchMore();
}

// =====================================================================
// Decidir: me interesa / no me interesa
// =====================================================================
async function decide(action) {
  if (busy || !queue.length) return;
  busy = true;
  const job = queue.shift();
  const card = cards.get(job.id);
  card.classList.remove("dragging");
  card.classList.add(action === "like" ? "leave-right" : "leave-left");
  const removeTimer = setTimeout(() => card.remove(), 300);
  updateView();

  try {
    const result = await swipeJob(job.id, action);
    cards.delete(job.id);
    job.my_action = action;
    history.push(job);
    if (result.matched) showMatch(job);
  } catch (err) {
    clearTimeout(removeTimer);
    if (err.status === 404) {
      // La vacante se cerró mientras la veía: simplemente se quita
      card.remove();
      cards.delete(job.id);
      showToast("Esa vacante ya no está disponible.", "error");
    } else {
      // Se devuelve la tarjeta a la pila
      card.classList.remove("leave-right", "leave-left");
      card.style.transform = "";
      resetStamps(card);
      queue.unshift(job);
      stage.append(card);
      showToast(err.message, "error");
    }
  } finally {
    busy = false;
    updateView();
    maybeLoadMore();
  }
}

async function undo() {
  if (busy || !history.length) return;
  busy = true;
  updateView();
  const job = history[history.length - 1];
  try {
    await undoSwipe(job.id);
    history.pop();
    job.my_action = null;
    queue.unshift(job);
    stage.append(buildCard(job));
    showToast("Listo, la vacante volvió a la pila.");
  } catch (err) {
    if (err.status === 404 || err.status === 409) history.pop(); // ya no se puede deshacer esta
    showToast(err.message, "error");
  } finally {
    busy = false;
    updateView();
  }
}

// =====================================================================
// Ventanas: detalle y "¡Es un match!"
// =====================================================================
function openTopDetail() {
  const job = queue[0];
  if (!job || busy) return;
  const close = openJobDetail(job, {
    onAction: async (action) => {
      close();
      await decide(action);
    },
  });
}

function showMatch(job) {
  const previousFocus = document.activeElement;
  const keepBtn = el("button", { type: "button", class: "btn btn-outline btn-block", textContent: "Seguir explorando" });
  const overlay = el("div", { class: "match-overlay" },
    el("div", { class: "match-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "match-title" },
      el("h2", { id: "match-title", textContent: "¡Es un match!" }),
      el("div", { class: "match-avatars", "aria-hidden": "true" },
        el("span", { class: "avatar", textContent: "Tú" }),
        el("span", { class: "avatar", textContent: initials(job.company.name) }),
      ),
      el("p", { textContent: `A ${job.company.name} también le interesa tu perfil para "${job.title}".` }),
      el("div", { class: "stack" },
        el("a", { href: "matches.html", class: "btn btn-primary btn-block", textContent: "Ver mis matches" }),
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

// =====================================================================
// Arrastrar la tarjeta (mouse y dedo, con Pointer Events)
// =====================================================================
let drag = null;

function resetStamps(card) {
  card.querySelectorAll(".swipe-stamp").forEach((s) => { s.style.opacity = ""; });
}

stage.addEventListener("pointerdown", (e) => {
  const card = e.target.closest(".swipe-card");
  if (!card || card !== topCard() || busy || e.button !== 0 || e.target.closest("button")) return;
  drag = { card, pointerId: e.pointerId, startX: e.clientX, startY: e.clientY, dx: 0, dy: 0 };
  card.setPointerCapture(e.pointerId);
  card.classList.add("dragging");
});

stage.addEventListener("pointermove", (e) => {
  if (!drag || e.pointerId !== drag.pointerId) return;
  drag.dx = e.clientX - drag.startX;
  drag.dy = e.clientY - drag.startY;
  drag.card.style.transform = `translate(${drag.dx}px, ${drag.dy * 0.3}px) rotate(${drag.dx / 18}deg)`;
  const strength = Math.min(1, Math.abs(drag.dx) / SWIPE_THRESHOLD);
  drag.card.querySelector(".swipe-stamp.like").style.opacity = drag.dx > 0 ? strength : 0;
  drag.card.querySelector(".swipe-stamp.nope").style.opacity = drag.dx < 0 ? strength : 0;
});

function endDrag(e) {
  if (!drag || e.pointerId !== drag.pointerId) return;
  const { card, dx, dy } = drag;
  drag = null;
  if (Math.abs(dx) >= SWIPE_THRESHOLD) {
    decide(dx > 0 ? "like" : "dislike");
    return;
  }
  card.classList.remove("dragging");
  card.style.transform = "";
  resetStamps(card);
  // Un toque sin arrastrar abre el detalle
  if (e.type === "pointerup" && Math.abs(dx) < 6 && Math.abs(dy) < 6) openTopDetail();
}

stage.addEventListener("pointerup", endDrag);
stage.addEventListener("pointercancel", endDrag);

stage.addEventListener("click", (e) => {
  if (e.target.closest('[data-action="detail"]')) openTopDetail();
});

// =====================================================================
// Botones, teclado y filtros
// =====================================================================
btnLike.addEventListener("click", () => decide("like"));
btnNope.addEventListener("click", () => decide("dislike"));
btnUndo.addEventListener("click", undo);
btnInfo.addEventListener("click", openTopDetail);

document.addEventListener("keydown", (e) => {
  const typing = e.target.closest?.("input, textarea, select");
  const modalOpen = document.querySelector(".modal-overlay, .match-overlay");
  if (typing || modalOpen || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "ArrowRight") { e.preventDefault(); decide("like"); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); decide("dislike"); }
  else if (e.key === "ArrowUp") { e.preventDefault(); openTopDetail(); }
  else if (e.key === "Backspace") { e.preventDefault(); undo(); }
});

function applyFilter(modality) {
  if (modality) filters.modality = modality;
  else delete filters.modality;
  resetFeed();
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

if (allowed) resetFeed();
