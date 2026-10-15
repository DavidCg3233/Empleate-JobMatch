// Buscador de vacantes del aspirante: texto + filtros, resultados paginados y acciones rápidas.
import { getCities, getContractTypes } from "../api/catalogApi.js";
import { searchJobs } from "../api/jobApi.js";
import { swipeJob, undoSwipe } from "../api/swipeApi.js";
import { openJobDetail } from "../components/jobDetail.js";
import { renderApplicantNav } from "../components/navbar.js";
import { createJobItem } from "../components/swipecard.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";

const allowed = requireRole("aspirante");
if (allowed) renderApplicantNav("search");

const PAGE_SIZE = 12;
const FILTER_NAMES = ["q", "city_id", "modality", "contract_type_id", "salary_min", "sort", "hide_discarded"];

const form = document.getElementById("search-form");
const qInput = document.getElementById("q");
const results = document.getElementById("results");
const summary = document.getElementById("results-summary");
const moreBtn = document.getElementById("more-btn");

let page = 1;
let total = 0;
let searchToken = 0;
let debounceTimer = null;
const items = new Map(); // id -> { job, element }

// =====================================================================
// Filtros <-> formulario <-> URL (así se puede recargar o compartir la búsqueda)
// =====================================================================
function readFilters() {
  const filters = {};
  for (const name of FILTER_NAMES) {
    const input = form.elements[name];
    if (input.type === "checkbox") {
      if (input.checked) filters[name] = true;
    } else if (input.value.trim()) {
      filters[name] = input.value.trim();
    }
  }
  if (filters.sort === "relevancia") delete filters.sort; // es el valor por defecto
  return filters;
}

function writeFiltersToUrl(filters) {
  const params = new URLSearchParams(filters);
  const query = params.toString();
  history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
}

function loadFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  for (const name of FILTER_NAMES) {
    const input = form.elements[name];
    const value = params.get(name);
    if (value === null) continue;
    if (input.type === "checkbox") input.checked = value === "true";
    else if (input.tagName !== "SELECT" || [...input.options].some((o) => o.value === value)) input.value = value;
  }
}

// =====================================================================
// Resultados
// =====================================================================
function skeletons(n = 3) {
  return Array.from({ length: n }, () => el("div", { class: "job-item skeleton job-skeleton", "aria-hidden": "true" }));
}

function renderSummary() {
  if (total === 0) {
    summary.textContent = "";
    return;
  }
  summary.textContent = total === 1 ? "1 vacante encontrada" : `${total} vacantes encontradas`;
}

function emptyState() {
  const hasFilters = Object.keys(readFilters()).length > 0;
  return el("div", { class: "results-empty" },
    el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "🔍" }),
    el("h3", { textContent: "No encontramos vacantes" }),
    el("p", {
      class: "text-muted",
      textContent: hasFilters
        ? "Prueba con otras palabras o quita algunos filtros."
        : "Todavía no hay vacantes publicadas. Vuelve pronto.",
    }),
    hasFilters ? el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Limpiar filtros", onclick: clearFilters }) : null,
  );
}

function errorState(message) {
  return el("div", { class: "results-empty" },
    el("h3", { textContent: "No pudimos hacer la búsqueda" }),
    el("p", { class: "text-muted", textContent: message }),
    el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: () => runSearch(1) }),
  );
}

function renderItem(job) {
  const element = createJobItem(job, { onOpen: openDetail, onAction: quickAction });
  const previous = items.get(job.id)?.element;
  items.set(job.id, { job, element });
  if (previous) previous.replaceWith(element);
  return element;
}

async function runSearch(newPage = 1) {
  const token = ++searchToken;
  const filters = readFilters();
  page = newPage;
  if (page === 1) {
    writeFiltersToUrl(filters);
    updateFiltersToggle();
    items.clear();
    results.replaceChildren(...skeletons());
    results.setAttribute("aria-busy", "true");
    moreBtn.hidden = true;
  } else {
    moreBtn.disabled = true;
    moreBtn.textContent = "Cargando...";
  }

  try {
    const data = await searchJobs({ ...filters, page, page_size: PAGE_SIZE });
    if (token !== searchToken) return; // llegó una búsqueda más nueva
    total = data.total;
    const fresh = data.items.filter((job) => !items.has(job.id)).map(renderItem);
    if (page === 1) results.replaceChildren(...(fresh.length ? fresh : [emptyState()]));
    else results.append(...fresh);
    moreBtn.hidden = !data.has_more;
    renderSummary();
  } catch (err) {
    if (token !== searchToken) return;
    if (page === 1) {
      total = 0;
      renderSummary();
      results.replaceChildren(errorState(err.message));
    } else {
      showToast(err.message, "error");
    }
  } finally {
    if (token === searchToken) {
      results.removeAttribute("aria-busy");
      moreBtn.disabled = false;
      moreBtn.textContent = "Cargar más vacantes";
    }
  }
}

// =====================================================================
// Acciones: me interesa / no me interesa (tocar otra vez la misma opción la quita)
// =====================================================================
async function handleAction(job, action) {
  try {
    if (job.my_action === action) {
      await undoSwipe(job.id);
      job.my_action = null;
      showToast(action === "like" ? "Quitaste la vacante de tus intereses." : "La vacante ya no está descartada.");
    } else {
      const result = await swipeJob(job.id, action);
      job.my_action = action;
      if (result.matched) {
        job.matched = true;
        showToast(`💚 ¡Es un match con ${job.company.name}! Míralo en "Mis matches".`, "success", 5000);
      } else {
        showToast(action === "like" ? "¡Listo! Le contaremos a la empresa que te interesa." : "Vacante descartada.", action === "like" ? "success" : "info");
      }
    }
  } catch (err) {
    showToast(err.message, "error");
    throw err;
  }

  const hideDiscarded = form.elements.hide_discarded.checked;
  if (hideDiscarded && job.my_action === "dislike") {
    items.get(job.id)?.element.remove();
    items.delete(job.id);
    total = Math.max(0, total - 1);
    renderSummary();
    if (!items.size && moreBtn.hidden) results.replaceChildren(emptyState());
  } else {
    renderItem(job);
  }
}

function openDetail(job) {
  // La ventana de detalle necesita saber si falló (para no cambiar sus botones)
  openJobDetail(job, { onAction: (action) => handleAction(job, action) });
}

// Botones de la lista: el error ya se mostró en un mensaje, no hace falta propagarlo
function quickAction(job, action) {
  handleAction(job, action).catch(() => {});
}

// =====================================================================
// Eventos
// =====================================================================
function clearFilters() {
  form.reset();
  runSearch(1);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  clearTimeout(debounceTimer);
  runSearch(1);
});
form.addEventListener("change", (e) => {
  if (e.target !== qInput) runSearch(1);
});
qInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => runSearch(1), 400);
});
document.getElementById("clear-btn").addEventListener("click", clearFilters);
moreBtn.addEventListener("click", () => runSearch(page + 1));

// En el celular los filtros se esconden detrás de un botón que muestra cuántos hay activos
const filtersToggle = document.getElementById("filters-toggle");
filtersToggle.addEventListener("click", () => {
  const open = form.classList.toggle("filters-open");
  filtersToggle.setAttribute("aria-expanded", String(open));
});

function updateFiltersToggle() {
  const active = Object.keys(readFilters()).filter((name) => name !== "q").length;
  filtersToggle.textContent = active ? `⚙️ Filtros (${active})` : "⚙️ Filtros";
}

// =====================================================================
// Inicio
// =====================================================================
function fillCities(cities) {
  const select = form.elements.city_id;
  const byDepartment = new Map();
  for (const city of cities) {
    if (!byDepartment.has(city.department)) byDepartment.set(city.department, []);
    byDepartment.get(city.department).push(city);
  }
  for (const [department, list] of byDepartment) {
    const group = el("optgroup", { label: department });
    list.forEach((c) => group.append(new Option(c.name, c.id)));
    select.append(group);
  }
}

async function init() {
  try {
    const [cities, contractTypes] = await Promise.all([getCities(), getContractTypes()]);
    fillCities(cities);
    contractTypes.forEach((c) => form.elements.contract_type_id.append(new Option(c.name, c.id)));
  } catch (err) {
    showToast("No se pudieron cargar los filtros: " + err.message, "error");
  }
  loadFiltersFromUrl();
  runSearch(1);
}

if (allowed) init();
