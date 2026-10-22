import { http } from "./http.js";

export const getCities = () => http("/catalogs/cities", { auth: false });
export const getIndustries = () => http("/catalogs/industries", { auth: false });
export const getEducationLevels = () => http("/catalogs/education-levels", { auth: false });
export const getLanguages = () => http("/catalogs/languages", { auth: false });
export const getContractTypes = () => http("/catalogs/contract-types", { auth: false });
/** Sugerencias de habilidades y herramientas para autocompletar (sin importar tildes ni mayúsculas). */
export const searchSkills = (q, limit = 8) =>
  http(`/catalogs/skills?q=${encodeURIComponent(q)}&limit=${limit}`, { auth: false });
