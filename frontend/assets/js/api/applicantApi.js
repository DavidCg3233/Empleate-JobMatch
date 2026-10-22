import { downloadFile, http } from "./http.js";

/** { matches: [{ match_id, matched_at, job, contact }], liked: [job] } */
export function getMyMatches() {
  return http("/matches/applicant");
}

// ---------- Perfil ----------
export const getApplicantProfile = () => http("/applicant/profile");
export const updateApplicantProfile = (data) => http("/applicant/profile", { method: "PUT", body: data });

/** Sube una hoja de vida nueva (reemplaza la anterior). Devuelve { cv, source, data } con lo que se leyó. */
export function uploadApplicantCv(file) {
  const form = new FormData();
  form.append("file", file);
  return http("/applicant/cv", { method: "POST", body: form });
}

export const downloadMyCv = () => downloadFile("/applicant/cv", "hoja_de_vida");
