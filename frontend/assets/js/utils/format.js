// Formatos para mostrar los datos de las vacantes.

export const MODALITY_LABEL = { presencial: "Presencial", remoto: "Remoto", hibrido: "Híbrido" };

export const COMPANY_SIZE_LABEL = {
  "1-10": "1 a 10 empleados", "11-50": "11 a 50 empleados", "51-200": "51 a 200 empleados",
  "201-500": "201 a 500 empleados", "501-1000": "501 a 1000 empleados", "1000+": "Más de 1000 empleados",
};

/** Estado que ve la empresa: "Deshabilitada" y "Vencida" tienen prioridad sobre el estado guardado. */
export function jobStatusInfo(job) {
  if (!job.is_enabled) return { label: "Deshabilitada", tone: "danger" };
  if (job.status === "cerrada") return { label: "Cerrada", tone: "neutral" };
  if (job.is_expired) return { label: "Vencida", tone: "warning" };
  if (job.status === "pausada") return { label: "Pausada", tone: "warning" };
  return { label: "Activa", tone: "success" };
}

/** 3.5 -> "3,5 años" · 1 -> "1 año" · 0 -> "Sin experiencia" */
export function formatYears(years) {
  if (!years) return "Sin experiencia";
  const text = Number.isInteger(years) ? String(years) : years.toLocaleString("es-CO", { maximumFractionDigits: 1 });
  return years === 1 ? "1 año" : `${text} años`;
}

/** "2022-03-01" -> "mar. 2022" */
export function formatMonthYear(isoDate) {
  if (!isoDate) return "";
  const [y, m] = String(isoDate).slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("es-CO", { month: "short", year: "numeric" });
}

export function formatPeriod(start, end, isCurrent = false) {
  const from = formatMonthYear(start);
  const to = isCurrent ? "actualidad" : formatMonthYear(end);
  if (from && to) return `${from} – ${to}`;
  return from || to || "";
}

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
