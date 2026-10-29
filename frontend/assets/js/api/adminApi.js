// Panel de administrador: /api/admin/...
import { http } from "./http.js";

// Arma "?q=...&page=2" sin los filtros vacíos
function query(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") q.append(key, value);
  });
  const text = q.toString();
  return text ? `?${text}` : "";
}

export const getAdminStats = () => http("/admin/stats");

// ---------- Usuarios ----------
/** filtros: { q, role: "aspirante"|"empresa"|"administrador", status: "activo"|"inactivo"|"bloqueado", page } */
export const listUsers = (filters) => http(`/admin/users${query(filters)}`);
export const setUserStatus = (userId, isActive) =>
  http(`/admin/users/${encodeURIComponent(userId)}/status`, { method: "PATCH", body: { is_active: isActive } });
export const unlockUser = (userId) => http(`/admin/users/${encodeURIComponent(userId)}/unlock`, { method: "POST" });

// ---------- Vacantes ----------
/** filtros: { q, status: "activa"|"pausada"|"cerrada", enabled: true|false, page } */
export const listAdminJobs = (filters) => http(`/admin/jobs${query(filters)}`);
export const setJobEnabled = (jobId, isEnabled) =>
  http(`/admin/jobs/${encodeURIComponent(jobId)}/enabled`, { method: "PATCH", body: { is_enabled: isEnabled } });

// ---------- Matches y bitácora ----------
export const listAdminMatches = (filters) => http(`/admin/matches${query(filters)}`);
export const listActivity = (filters) => http(`/admin/activity${query(filters)}`);
