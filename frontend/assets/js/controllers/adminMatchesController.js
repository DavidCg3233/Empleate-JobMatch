// Administrador: matches de toda la plataforma.
import { listAdminMatches } from "../api/adminApi.js";
import {
  cell, createListLoader, debounce, fillTable, formatDateTime, pill, renderPagination, tableLoading,
} from "../components/adminUi.js";
import { renderNav } from "../components/navbar.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";

const allowed = requireRole("administrador");
if (allowed) renderNav("administrador", "matches");

const rows = document.getElementById("rows");
const pagination = document.getElementById("pagination");
const errorBox = document.getElementById("error-box");
const q = document.getElementById("q");

const list = createListLoader({
  fetch: listAdminMatches,
  before: () => { errorBox.classList.add("hidden"); tableLoading(rows); },
  render: (data) => {
    fillTable(rows, data.items.map(matchRow), "Todavía no hay matches con esos filtros.");
    renderPagination(pagination, data, (page) => list.load({ page }), "matches");
  },
  onError: (err) => {
    fillTable(rows, [], "No se pudo cargar la lista.");
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
  },
});

function matchRow(match) {
  return el("tr", { dataset: { matchId: match.id } },
    cell("Aspirante", [
      el("strong", { textContent: match.applicant_name }),
      el("span", { class: "cell-sub", textContent: match.applicant_email }),
    ], "cell-main cell-wrap"),
    cell("Vacante", match.job_title, "cell-wrap"),
    cell("Empresa", match.company_name),
    cell("Fecha", formatDateTime(match.matched_at)),
    cell("Estado", match.is_active ? pill("Activo", "active") : pill("Deshecho", "neutral")),
  );
}

if (allowed) {
  q.addEventListener("input", debounce(() => list.load({ q: q.value.trim(), page: 1 })));
  list.load({ page: 1 });
}
