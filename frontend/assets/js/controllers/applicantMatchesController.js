// Mis matches (la empresa también dijo que sí) y vacantes que me interesan (esperando respuesta).
import { getMyMatches } from "../api/applicantApi.js";
import { swipeJob, undoSwipe } from "../api/swipeApi.js";
import { openJobDetail } from "../components/jobDetail.js";
import { renderApplicantNav } from "../components/navbar.js";
import { createJobItem } from "../components/swipecard.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { formatDate, initials } from "../utils/format.js";

const allowed = requireRole("aspirante");
if (allowed) renderApplicantNav("matches");

const tabs = {
  matches: { tab: document.getElementById("tab-matches"), panel: document.getElementById("panel-matches"), count: document.getElementById("count-matches") },
  liked: { tab: document.getElementById("tab-liked"), panel: document.getElementById("panel-liked"), count: document.getElementById("count-liked") },
};

let liked = [];

// =====================================================================
// Pestañas
// =====================================================================
function selectTab(name, focus = false) {
  for (const [key, t] of Object.entries(tabs)) {
    const active = key === name;
    t.tab.setAttribute("aria-selected", String(active));
    t.tab.tabIndex = active ? 0 : -1;
    t.panel.hidden = !active;
  }
  if (focus) tabs[name].tab.focus();
}

Object.entries(tabs).forEach(([name, t]) => {
  t.tab.addEventListener("click", () => selectTab(name));
  t.tab.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") selectTab(name === "matches" ? "liked" : "matches", true);
  });
});

function setCount(name, n) {
  tabs[name].count.textContent = `(${n})`;
}

// =====================================================================
// Matches
// =====================================================================
function contactBlock(contact) {
  return el("div", { class: "match-contact" },
    el("p", { class: "card-section-title", textContent: "Contacto de la empresa" }),
    el("p", {}, el("strong", { textContent: contact.name })),
    el("p", {}, "✉️ ", el("a", { href: `mailto:${contact.email}`, textContent: contact.email })),
    contact.phone ? el("p", {}, "📞 ", el("a", { href: `tel:${contact.phone.replace(/[^\d+]/g, "")}`, textContent: contact.phone })) : null,
  );
}

function matchItem({ matched_at: matchedAt, job, contact }) {
  return el("article", { class: "match-item match-card" },
    el("div", { class: "match-item-main" },
      el("span", { class: "avatar", "aria-hidden": "true", textContent: initials(job.company.name) }),
      el("div", { class: "card-heading" },
        el("h3", { class: "match-title", textContent: job.title }),
        el("p", { class: "card-subtitle", textContent: job.company.name }),
        el("p", { class: "hint", textContent: `Match el ${formatDate(matchedAt)}` }),
      ),
      job.is_open
        ? el("span", { class: "badge badge-success", textContent: "💚 Match" })
        : el("span", { class: "badge", textContent: "Vacante cerrada" }),
    ),
    contactBlock(contact),
    el("div", { class: "row" },
      el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Ver vacante", onclick: () => openJobDetail(job) }),
    ),
  );
}

function renderMatches(matches) {
  setCount("matches", matches.length);
  const panel = tabs.matches.panel;
  if (!matches.length) {
    panel.replaceChildren(el("div", { class: "results-empty" },
      el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "💚" }),
      el("h3", { textContent: "Aún no tienes matches" }),
      el("p", { class: "text-muted", textContent: "Marca las vacantes que te interesan. Cuando una empresa también se interese en ti, aparecerá aquí con sus datos de contacto." }),
      el("a", { href: "swipe.html", class: "btn btn-primary btn-sm", textContent: "Explorar vacantes" }),
    ));
    return;
  }
  panel.replaceChildren(...matches.map(matchItem));
}

// =====================================================================
// Me interesan
// =====================================================================
function renderLiked() {
  setCount("liked", liked.length);
  const panel = tabs.liked.panel;
  if (!liked.length) {
    panel.replaceChildren(el("div", { class: "results-empty" },
      el("span", { class: "swipe-empty-icon", "aria-hidden": "true", textContent: "🔎" }),
      el("h3", { textContent: "No has marcado vacantes" }),
      el("p", { class: "text-muted", textContent: "Las vacantes a las que les des \"Me interesa\" aparecerán aquí mientras la empresa revisa tu perfil." }),
      el("a", { href: "search.html", class: "btn btn-primary btn-sm", textContent: "Buscar vacantes" }),
    ));
    return;
  }
  panel.replaceChildren(...liked.map((job) => createJobItem(job, { onOpen: openDetail, onAction: quickAction })));
}

async function handleAction(job, action) {
  try {
    if (job.my_action === action) {
      await undoSwipe(job.id); // tocar "Te interesa" otra vez la quita de la lista
      job.my_action = null;
    } else {
      const result = await swipeJob(job.id, action);
      job.my_action = action;
      if (result.matched) {
        showToast(`💚 ¡Es un match con ${job.company.name}!`, "success", 5000);
        load();
        return;
      }
    }
  } catch (err) {
    showToast(err.message, "error");
    throw err;
  }
  if (job.my_action !== "like") {
    liked = liked.filter((j) => j.id !== job.id);
    showToast("Quitaste la vacante de tus intereses.");
  }
  renderLiked();
}

function quickAction(job, action) {
  handleAction(job, action).catch(() => {});
}

function openDetail(job) {
  openJobDetail(job, { onAction: (action) => handleAction(job, action) });
}

// =====================================================================
// Inicio
// =====================================================================
async function load() {
  const loading = () => el("div", { class: "results-empty" }, el("span", { class: "spinner", "aria-hidden": "true" }));
  tabs.matches.panel.replaceChildren(loading());
  tabs.liked.panel.replaceChildren(loading());
  try {
    const data = await getMyMatches();
    liked = data.liked;
    renderMatches(data.matches);
    renderLiked();
    if (!data.matches.length && data.liked.length) selectTab("liked");
  } catch (err) {
    const error = () => el("div", { class: "results-empty" },
      el("h3", { textContent: "No pudimos cargar tus vacantes" }),
      el("p", { class: "text-muted", textContent: err.message }),
      el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Reintentar", onclick: load }),
    );
    tabs.matches.panel.replaceChildren(error());
    tabs.liked.panel.replaceChildren(error());
  }
}

if (allowed) load();
