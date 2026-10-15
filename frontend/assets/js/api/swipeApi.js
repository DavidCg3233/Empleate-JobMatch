import { http } from "./http.js";

/** action: "like" (me interesa) | "dislike" (no me interesa). Devuelve { matched, match_id, ... } */
export function swipeJob(jobId, action) {
  return http("/swipes/jobs", { method: "POST", body: { job_id: jobId, action } });
}

/** Deshace la decisión sobre una vacante (vuelve a aparecer en las tarjetas). */
export function undoSwipe(jobId) {
  return http(`/swipes/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
}
