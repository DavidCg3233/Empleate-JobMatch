// Formatos para mostrar los datos de las vacantes.

export const MODALITY_LABEL = { presencial: "Presencial", remoto: "Remoto", hibrido: "Híbrido" };

export function formatMoney(value, currency = "COP") {
  try {
    return new Intl.NumberFormat("es-CO", { style: "currency", currency, maximumFractionDigits: 0 }).format(value);
  } catch {
    return `${Math.round(value).toLocaleString("es-CO")} ${currency}`;
  }
}

export function formatSalary(job) {
  const { salary_min: min, salary_max: max, currency } = job;
  if (min && max) {
    return min === max ? formatMoney(min, currency) : `${formatMoney(min, currency)} - ${formatMoney(max, currency)}`;
  }
  if (min) return `Desde ${formatMoney(min, currency)}`;
  if (max) return `Hasta ${formatMoney(max, currency)}`;
  return "Salario a convenir";
}

export function formatLocation(job) {
  if (!job.city) return job.modality === "remoto" ? "Remoto (cualquier ciudad)" : "Ubicación no indicada";
  return job.department && job.department !== job.city ? `${job.city}, ${job.department}` : job.city;
}

export function formatExperience(years) {
  if (!years) return "Sin experiencia";
  return years === 1 ? "1 año de experiencia" : `${years} años de experiencia`;
}

export function timeAgo(isoDate) {
  if (!isoDate) return "";
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "";
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return "Publicada hoy";
  if (days === 1) return "Publicada ayer";
  if (days < 30) return `Publicada hace ${days} días`;
  return `Publicada el ${date.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" })}`;
}

export function formatDate(isoDate) {
  if (!isoDate) return "";
  // "2026-11-30" se arma como fecha local (no UTC) para que no se corra un día
  const [y, m, d] = String(isoDate).slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
}

export function initials(name = "") {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "") + (words[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function scoreClass(score) {
  if (score >= 75) return "score-high";
  if (score >= 50) return "score-mid";
  return "score-low";
}
