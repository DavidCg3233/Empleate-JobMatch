// Administrador: bitácora de actividad (filtro por tipo de acción).
import { listActivity } from "../api/adminApi.js";
import {
  actionLabel, activityDetail, cell, createListLoader, fillTable, formatDateTime, renderPagination, tableLoading,
} from "../components/adminUi.js";
import { renderNav } from "../components/navbar.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";

const allowed = requireRole("administrador");
if (allowed) renderNav("administrador", "activity");

const rows = document.getElementById("rows");
const pagination = document.getElementById("pagination");
const errorBox = document.getElementById("error-box");
const actionSelect = document.getElementById("action");

// Las opciones del filtro salen de las acciones que existen en la bitácora
function fillActions(actions) {
  const current = actionSelect.value;
  const known = new Set([...actionSelect.options].map((o) => o.value));
  actions.filter((a) => !known.has(a)).forEach((a) => actionSelect.append(el("option", { value: a, textContent: actionLabel(a) })));
  actionSelect.value = current;
}

const list = createListLoader({
  fetch: listActivity,
  before: () => { errorBox.classList.add("hidden"); tableLoading(rows); },
  render: (data) => {
    fillActions(data.actions);
    fillTable(rows, data.items.map(activityRow), "No hay actividad registrada.");
    renderPagination(pagination, data, (page) => list.load({ page }), "registros");
  },
  onError: (err) => {
    fillTable(rows, [], "No se pudo cargar la bitácora.");
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
  },
});

function activityRow(item) {
  const { who, text } = activityDetail(item);
  return el("tr", {},
    cell("Acción", el("strong", { textContent: actionLabel(item.action) }), "cell-main"),
    cell("Quién", who),
    cell("Detalle", text || "—", "cell-wrap"),
    cell("Fecha", formatDateTime(item.created_at)),
  );
}

if (allowed) {
  actionSelect.addEventListener("change", () => list.load({ action: actionSelect.value, page: 1 }));
  list.load({ page: 1 });
}
