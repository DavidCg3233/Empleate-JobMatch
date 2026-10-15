import { http } from "./http.js";

export const getCities = () => http("/catalogs/cities", { auth: false });
export const getIndustries = () => http("/catalogs/industries", { auth: false });
export const getEducationLevels = () => http("/catalogs/education-levels", { auth: false });
export const getLanguages = () => http("/catalogs/languages", { auth: false });
export const getContractTypes = () => http("/catalogs/contract-types", { auth: false });
