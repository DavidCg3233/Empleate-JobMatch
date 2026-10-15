import { http } from "./http.js";

// Convierte un objeto de filtros en "?a=1&b=2" (omite los vacíos). Los arreglos se repiten: exclude=1&exclude=2
function toQuery(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) value.forEach((v) => query.append(key, v));
    else if (value !== undefined && value !== null && value !== "" && value !== false) query.append(key, value);
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

/** Tarjetas para deslizar (vacantes que aún no ha visto), de la más compatible a la menos. */
export function getFeed(filters = {}, exclude = []) {
  return http(`/jobs/feed${toQuery({ ...filters, exclude })}`);
}

/** Buscador: { q, city_id, modality, contract_type_id, salary_min, sort, hide_discarded, page, page_size } */
export function searchJobs(params = {}) {
  return http(`/jobs/search${toQuery(params)}`);
}

export function getJob(jobId) {
  return http(`/jobs/${encodeURIComponent(jobId)}`);
}
