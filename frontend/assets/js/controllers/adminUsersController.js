// Administrador: usuarios (buscar, filtrar, activar / desactivar y desbloquear).
import { listUsers, setUserStatus, unlockUser } from "../api/adminApi.js";
import {
  ROLE_LABEL, cell, createListLoader, debounce, fillTable, formatDateTime, pill, renderPagination, tableLoading,
} from "../components/adminUi.js";
import { confirmDialog } from "../components/modal.js";
import { renderNav } from "../components/navbar.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";

const allowed = requireRole("administrador");
if (allowed) renderNav("administrador", "users");

const rows = document.getElementById("rows");
const pagination = document.getElementById("pagination");
const errorBox = document.getElementById("error-box");
const q = document.getElementById("q");
const role = document.getElementById("role");
const status = document.getElementById("status");

// Filtros que llegan desde el resumen (ej: users.html?role=empresa)
const params = new URLSearchParams(window.location.search);
if (["aspirante", "empresa", "administrador"].includes(params.get("role"))) role.value = params.get("role");
if (["activo", "inactivo", "bloqueado"].includes(params.get("status"))) status.value = params.get("status");

const list = createListLoader({
  fetch: listUsers,
  before: () => { errorBox.classList.add("hidden"); tableLoading(rows); },
  render: (data) => {
    fillTable(rows, data.items.map(userRow), "No hay usuarios con esos filtros.");
    renderPagination(pagination, data, (page) => list.load({ page }), "usuarios");
  },
  onError: (err) => {
    fillTable(rows, [], "No se pudo cargar la lista.");
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
  },
});

async function run(button, action, successMessage) {
  button.disabled = true;
  try {
    await action();
    showToast(successMessage, "success");
    list.reload();
  } catch (err) {
    showToast(err.message, "error");
    button.disabled = false;
  }
}

function userRow(user) {
  const isAdmin = user.role === "administrador";
  const actions = el("div", { class: "table-actions" });

  if (user.is_locked && !isAdmin) {
    const unlock = el("button", { type: "button", class: "btn btn-outline btn-sm", textContent: "Desbloquear" });
    unlock.addEventListener("click", () => run(unlock, () => unlockUser(user.id), "Cuenta desbloqueada."));
    actions.append(unlock);
  }
  if (!isAdmin) {
    const toggle = el("button", {
      type: "button", class: user.is_active ? "btn btn-danger btn-sm" : "btn btn-primary btn-sm",
      textContent: user.is_active ? "Desactivar" : "Activar",
    });
    toggle.addEventListener("click", async () => {
      if (user.is_active) {
        const ok = await confirmDialog({
          title: `¿Desactivar a ${user.display_name}?`,
          message: user.role === "empresa"
            ? "La empresa no podrá entrar y sus vacantes dejarán de verse. Puedes volver a activarla cuando quieras."
            : "El aspirante no podrá entrar ni aparecerá a las empresas. Puedes volver a activarlo cuando quieras.",
          confirmText: "Desactivar", danger: true,
        });
        if (!ok) return;
      }
      run(toggle, () => setUserStatus(user.id, !user.is_active), user.is_active ? "Cuenta desactivada." : "Cuenta activada.");
    });
    actions.append(toggle);
  } else {
    actions.append(el("span", { class: "hint", textContent: "—" }));
  }

  const state = !user.is_active ? pill("Desactivada", "inactive") : user.is_locked ? pill("Bloqueada", "paused") : pill("Activa", "active");
  return el("tr", { dataset: { userId: user.id } },
    cell("Usuario", [
      el("strong", { textContent: user.display_name }),
      el("span", { class: "cell-sub", textContent: user.email }),
      user.detail ? el("span", { class: "cell-sub", textContent: user.detail }) : null,
    ].filter(Boolean), "cell-main cell-wrap"),
    cell("Rol", pill(ROLE_LABEL[user.role] || user.role, "neutral")),
    cell("Estado", state),
    cell("Último ingreso", user.last_login_at ? formatDateTime(user.last_login_at) : "Nunca"),
    cell("Registro", formatDateTime(user.created_at)),
    cell("Acciones", actions),
  );
}

if (allowed) {
  const applyFilters = () => list.load({ q: q.value.trim(), role: role.value, status: status.value, page: 1 });
  q.addEventListener("input", debounce(applyFilters));
  role.addEventListener("change", applyFilters);
  status.addEventListener("change", applyFilters);
  applyFilters();
}
