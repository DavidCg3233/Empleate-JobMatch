// Administrador: resumen con indicadores, registros por día y actividad reciente.
import { getAdminStats } from "../api/adminApi.js";
import { activityDetail, actionLabel, formatDateTime } from "../components/adminUi.js";
import { renderNav } from "../components/navbar.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";

const allowed = requireRole("administrador");
if (allowed) renderNav("administrador", "dashboard");

const statsBox = document.getElementById("stats");
const signupsBox = document.getElementById("signups");
const activityBox = document.getElementById("activity");
const errorBox = document.getElementById("error-box");

const number = (n) => n.toLocaleString("es-CO");

function statCard(label, value, { hint, kind, href } = {}) {
  const card = el(href ? "a" : "div", { class: `stat-card${kind ? ` is-${kind}` : ""}`, href },
    el("div", { class: "stat-label", textContent: label }),
    el("div", { class: "stat-value", textContent: number(value) }),
    hint ? el("div", { class: "stat-hint", textContent: hint }) : null,
  );
  return card;
}

function renderStats(s) {
  statsBox.replaceChildren(
    statCard("Aspirantes", s.total_applicants, { kind: "primary", href: "users.html?role=aspirante" }),
    statCard("Empresas", s.total_companies, { kind: "primary", href: "users.html?role=empresa" }),
    statCard("Nuevos registros (7 días)", s.new_users_7d),
    statCard("Vacantes publicadas", s.active_jobs, { hint: `${number(s.total_jobs)} en total · ${number(s.disabled_jobs)} deshabilitadas`, href: "jobs.html" }),
    statCard("Matches", s.total_matches, { kind: "accent", hint: `${number(s.new_matches_7d)} en los últimos 7 días`, href: "matches.html" }),
    statCard("Decisiones (swipes)", s.total_applicant_swipes + s.total_company_swipes,
      { hint: `${number(s.total_applicant_swipes)} de aspirantes · ${number(s.total_company_swipes)} de empresas` }),
    statCard("Cuentas desactivadas", s.inactive_users, { hint: `${number(s.locked_users)} bloqueadas por intentos`, href: "users.html?status=inactivo" }),
    statCard("Análisis con IA", s.ai_analyses, { hint: `${number(s.ai_embeddings)} perfiles y vacantes vectorizados` }),
  );
}

const dayLabel = (iso) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
};

function renderSignups(days) {
  const max = Math.max(1, ...days.map((d) => d.count));
  const total = days.reduce((sum, d) => sum + d.count, 0);
  const bars = days.map((d) => {
    const text = `${dayLabel(d.date)}: ${d.count} registro${d.count === 1 ? "" : "s"}`;
    return el("div", { class: "bar-col", tabIndex: 0, role: "img", "aria-label": text },
      el("span", { class: "bar-tip", textContent: text, "aria-hidden": "true" }),
      el("div", { class: `bar${d.count ? "" : " is-zero"}`, style: `height: ${(d.count / max) * 100}%` }),
    );
  });
  signupsBox.replaceChildren(
    el("p", { class: "hint", textContent: `${total} aspirante(s) y empresa(s) nuevos en 14 días. Pasa el cursor por una barra para ver el día.` }),
    el("div", { class: "bar-chart" }, bars),
    el("div", { class: "bar-axis", "aria-hidden": "true" },
      el("span", { textContent: dayLabel(days[0].date) }),
      el("span", { textContent: "Hoy" }),
    ),
  );
}

function renderActivity(items) {
  if (!items.length) {
    activityBox.replaceChildren(el("li", { class: "text-muted", textContent: "Todavía no hay actividad." }));
    return;
  }
  activityBox.replaceChildren(...items.map((item) => {
    const { who, text } = activityDetail(item);
    return el("li", {},
      el("div", { class: "activity-main" },
        el("strong", { textContent: actionLabel(item.action) }),
        el("p", { class: "hint", textContent: [who, text].filter(Boolean).join(" · ") }),
      ),
      el("span", { class: "activity-time", textContent: formatDateTime(item.created_at) }),
    );
  }));
}

async function init() {
  try {
    const stats = await getAdminStats();
    renderStats(stats);
    renderSignups(stats.signups_by_day);
    renderActivity(stats.recent_activity);
  } catch (err) {
    statsBox.replaceChildren();
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
  }
}

if (allowed) init();
