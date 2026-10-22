import { http } from "./http.js";

let statusPromise = null;

/** Qué partes de la IA están activas: { provider, semantic, analysis }. Se consulta una sola vez por página. */
export function getMatchingStatus() {
  if (!statusPromise) {
    statusPromise = http("/matching/status", { auth: false }).catch(() => ({ provider: null, semantic: false, analysis: false }));
  }
  return statusPromise;
}

/** Aspirante: análisis de la IA de su compatibilidad con una vacante. */
export const getJobAnalysis = (jobId) => http(`/matching/jobs/${encodeURIComponent(jobId)}/analysis`);

/** Empresa: análisis de la IA de un candidato para una de sus vacantes. */
export const getCandidateAnalysis = (jobId, applicantId) =>
  http(`/matching/jobs/${encodeURIComponent(jobId)}/candidates/${encodeURIComponent(applicantId)}/analysis`);
