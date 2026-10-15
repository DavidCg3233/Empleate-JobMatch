import { http } from "./http.js";

/** { matches: [{ match_id, matched_at, job, contact }], liked: [job] } */
export function getMyMatches() {
  return http("/matches/applicant");
}
