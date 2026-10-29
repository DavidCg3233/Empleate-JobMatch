// Administrador: vacantes (buscar, filtrar y habilitar / deshabilitar).
import { listAdminJobs, setJobEnabled } from "../api/adminApi.js";
import {
  cell, createListLoader, debounce, fillTable, formatDateTime, pill, renderPagination, tableLoading,
} from "../components/adminUi.js";
import { confirmDialog } from "../components/modal.js";
import { renderNav } from "../components/navbar.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { MODALITY_LABEL } from "../utils/format.js";

const allowed = requireRole("administrador");
if (allowed) renderNav("administrador", "jobs");

const rows = document.getElementById("rows");
const pagination = document.getElementById("pagination");
const errorBox = document.getElementById("error-box");
const q = document.getElementById("q");
const status = document.getElementById("status");
const enabled = document.getElementById("enabled");

const STATUS = { activa: ["Publicada", "active"], pausada: ["Pausada", "paused"], cerrada: ["Cerrada", "neutral"] };

const list = createListLoader({
  fetch: listAdminJobs,
  before: () => { errorBox.classList.add("hidden"); tableLoading(rows); },
  render: (data) => {
    fillTable(rows, data.items.map(jobRow), "No hay vacantes con esos filtros.");
    renderPagination(pagination, data, (page) => list.load({ page }), "vacantes");
  },
  onError: (err) => {
    fillTable(rows, [], "No se pudo cargar la lista.");
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
  },
});

function jobRow(job) {
  const [statusText, statusKind] = STATUS[job.status] || [job.status, "neutral"];
  const visibility = !job.is_enabled
    ? pill("Deshabilitada", "inactive")
    : !job.company_active ? pill("Empresa desactivada", "paused") : pill("Habilitada", "active");

  const toggle = el("button", {
    type: "button", class: job.is_enabled ? "btn btn-danger btn-sm" : "btn btn-primary btn-sm",
    textContent: job.is_enabled ? "Deshabilitar" : "Habilitar",
  });
  toggle.addEventListener("click", async () => {
    if (job.is_enabled) {
      const ok = await confirmDialog({
        title: `¿Deshabilitar “${job.title}”?`,
        message: "Dejará de verse para los aspirantes y la empresa no podrá volver a publicarla hasta que la habilites. Los matches que ya tiene se conservan.",
        confirmText: "Deshabilitar", danger: true,
      });
      if (!ok) return;
    }
    toggle.disabled = true;
    try {
      await setJobEnabled(job.id, !job.is_enabled);
      showToast(job.is_enabled ? "Vacante deshabilitada." : "Vacante habilitada.", "success");
      list.reload();
    } catch (err) {
      showToast(err.message, "error");
      toggle.disabled = false;
    }
  });

  const where = [MODALITY_LABEL[job.modality] || job.modality, job.city].filter(Boolean).join(" · ");
  return el("tr", { dataset: { jobId: job.id } },
    cell("Vacante", [
      el("strong", { textContent: job.title }),
      el("span", { class: "cell-sub", textContent: job.company_name }),
      el("span", { class: "cell-sub", textContent: where }),
    ], "cell-main cell-wrap"),
    cell("Estado", pill(statusText, statusKind)),
    cell("Visibilidad", visibility),
    cell("Interesados", String(job.likes), "num"),
    cell("Matches", String(job.matches), "num"),
    cell("Creada", formatDateTime(job.created_at)),
    cell("Acciones", el("div", { class: "table-actions" }, toggle)),
  );
}

if (allowed) {
  const applyFilters = () => list.load({ q: q.value.trim(), status: status.value, enabled: enabled.value, page: 1 });
  q.addEventListener("input", debounce(applyFilters));
  status.addEventListener("change", applyFilters);
  enabled.addEventListener("change", applyFilters);
  applyFilters();
}
