import { downloadFile, http } from "./http.js";

// ---------- Perfil ----------
export const getCompanyProfile = () => http("/company/profile");
export const updateCompanyProfile = (data) => http("/company/profile", { method: "PUT", body: data });

// ---------- Vacantes (CRUD) ----------
export const listCompanyJobs = () => http("/company/jobs");
export const getCompanyJob = (jobId) => http(`/company/jobs/${encodeURIComponent(jobId)}`);
export const createCompanyJob = (data) => http("/company/jobs", { method: "POST", body: data });
export const updateCompanyJob = (jobId, data) => http(`/company/jobs/${encodeURIComponent(jobId)}`, { method: "PUT", body: data });
/** status: "activa" (publicar) | "pausada" | "cerrada" */
export const changeJobStatus = (jobId, status) =>
  http(`/company/jobs/${encodeURIComponent(jobId)}/status`, { method: "PATCH", body: { status } });
export const deleteCompanyJob = (jobId) => http(`/company/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });

// ---------- Candidatos ----------
export function getCandidates(jobId, { onlyInterested = false, exclude = [] } = {}) {
  const query = new URLSearchParams();
  if (onlyInterested) query.append("only_interested", "true");
  exclude.forEach((id) => query.append("exclude", id));
  const text = query.toString();
  return http(`/company/jobs/${encodeURIComponent(jobId)}/candidates${text ? `?${text}` : ""}`);
}

/** action: "like" (me interesa) | "dislike" (no me interesa) */
export const swipeCandidate = (jobId, applicantId, action) =>
  http("/swipes/candidates", { method: "POST", body: { job_id: jobId, applicant_id: applicantId, action } });
export const undoCandidateSwipe = (jobId, applicantId) =>
  http(`/swipes/candidates/${encodeURIComponent(jobId)}/${encodeURIComponent(applicantId)}`, { method: "DELETE" });

// ---------- Matches ----------
export const getCompanyMatches = (jobId) => http(`/matches/company${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`);
export const downloadMatchCv = (matchId) => downloadFile(`/matches/${encodeURIComponent(matchId)}/cv`, "hoja_de_vida");
