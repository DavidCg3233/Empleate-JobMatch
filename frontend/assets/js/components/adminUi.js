// Piezas compartidas del panel de administrador: tablas, paginación, estados y textos de la bitácora.
import { el } from "../utils/dom.js";

export const ROLE_LABEL = { aspirante: "Aspirante", empresa: "Empresa", administrador: "Administrador" };

const ACTION_LABEL = {
  registro: "Nuevo registro",
  inicio_sesion: "Inicio de sesión",
  cuenta_bloqueada: "Cuenta bloqueada por intentos fallidos",
  contrasena_restablecida: "Contraseña restablecida",
  contrasena_cambiada: "Contraseña cambiada",
  vacante_creada: "Vacante creada",
  vacante_estado: "Cambio de estado de vacante",
  vacante_eliminada: "Vacante eliminada",
  match: "Nuevo match",
  usuario_activado: "Cuenta activada",
  usuario_desactivado: "Cuenta desactivada",
  usuario_desbloqueado: "Cuenta desbloqueada",
  vacante_habilitada: "Vacante habilitada",
  vacante_deshabilitada: "Vacante deshabilitada",
  cuenta_eliminada: "Cuenta eliminada por su titular",
  administrador_creado: "Administrador creado",
  administrador_actualizado: "Administrador actualizado",
};

export const actionLabel = (action) => ACTION_LABEL[action] || action.replace(/_/g, " ");

/** Detalle legible de un registro de la bitácora. */
export function activityDetail(item) {
  const d = item.details || {};
  const parts = [];
  if (d.titulo) parts.push(`“${d.titulo}”`);
  if (d.nombre) parts.push(d.nombre);
  if (d.correo) parts.push(d.correo);
  if (d.de && d.a) parts.push(`${d.de} → ${d.a}`);
  if (d.rol && item.action === "cuenta_eliminada") parts.push(ROLE_LABEL[d.rol] || d.rol);
  if (typeof d.vacantes === "number") parts.push(`${d.vacantes} vacante(s) borrada(s)`);
  if (item.action === "registro" && item.entity_type) parts.push(ROLE_LABEL[item.entity_type] || item.entity_type);
  const who = item.user_email || (item.action === "cuenta_eliminada" ? "Cuenta eliminada" : "Sistema");
  return { who, text: parts.join(" · ") };
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("es-CO", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export const pill = (text, kind) => el("span", { class: `pill pill-${kind}`, textContent: text });

/** Celda con su etiqueta (en celular la tabla se ve como tarjetas y muestra la etiqueta). */
export const cell = (label, content, className) =>
  el("td", { "data-label": label, class: className }, content ?? "—");

/** Llena el cuerpo de la tabla; si no hay filas muestra el mensaje vacío. */
export function fillTable(tbody, rows, emptyText) {
  const colspan = tbody.closest("table").querySelectorAll("thead th").length;
  tbody.replaceChildren(
    ...(rows.length ? rows : [el("tr", { class: "table-empty" }, el("td", { colSpan: colspan, textContent: emptyText }))]),
  );
}

export function tableLoading(tbody) {
  const colspan = tbody.closest("table").querySelectorAll("thead th").length;
  tbody.replaceChildren(el("tr", { class: "table-empty" },
    el("td", { colSpan: colspan }, el("span", { class: "spinner", "aria-hidden": "true" }), " Cargando...")));
}

/** Botones Anterior / Siguiente. onPage(n) se llama al cambiar de página. */
export function renderPagination(container, { page, pages, total }, onPage, noun = "resultados") {
  const prev = el("button", { type: "button", class: "btn btn-outline btn-sm", textContent: "‹ Anterior", disabled: page <= 1 });
  const next = el("button", { type: "button", class: "btn btn-outline btn-sm", textContent: "Siguiente ›", disabled: page >= pages });
  prev.addEventListener("click", () => onPage(page - 1));
  next.addEventListener("click", () => onPage(page + 1));
  container.replaceChildren(
    ...(pages > 1 ? [prev] : []),
    el("span", { class: "hint", textContent: `${total} ${noun}${pages > 1 ? ` · página ${page} de ${pages}` : ""}` }),
    ...(pages > 1 ? [next] : []),
  );
}

export function debounce(fn, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/**
 * Lista con filtros y paginación. Evita respuestas viejas (si se filtra rápido, solo cuenta la última).
 * const list = createListLoader({ fetch: (filters) => listUsers(filters), render: (data) => ... , onError })
 * list.load({ page: 1 })
 */
export function createListLoader({ fetch, render, onError, before }) {
  let token = 0;
  let filters = { page: 1 };
  async function load(changes = {}) {
    filters = { ...filters, ...changes };
    const mine = ++token;
    before?.();
    try {
      const data = await fetch(filters);
      if (mine !== token) return;
      filters.page = data.page;
      render(data);
    } catch (err) {
      if (mine === token) onError(err);
    }
  }
  return { load, reload: () => load(), get filters() { return filters; } };
}
