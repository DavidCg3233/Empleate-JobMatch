// Barra de navegación de las pantallas con sesión (arriba en escritorio, abajo en el celular).
// Uso: renderNav("empresa", "jobs")  ·  renderNav("administrador", "users")  ·  renderApplicantNav("swipe")
import { getMe } from "../api/authApi.js";
import { logout } from "../utils/auth.js";

const LINKS = {
  aspirante: [
    { key: "swipe", href: "swipe.html", icon: "🧭", label: "Explorar" },
    { key: "search", href: "search.html", icon: "🔎", label: "Buscar" },
    { key: "matches", href: "matches.html", icon: "💚", label: "Mis matches" },
    { key: "profile", href: "profile.html", icon: "👤", label: "Mi perfil" },
  ],
  empresa: [
    { key: "jobs", href: "jobs.html", icon: "📋", label: "Vacantes" },
    { key: "swipe", href: "swipe.html", icon: "🧭", label: "Candidatos" },
    { key: "matches", href: "matches.html", icon: "💚", label: "Matches" },
    { key: "profile", href: "company.html", icon: "🏢", label: "Empresa" },
  ],
  administrador: [
    { key: "dashboard", href: "dashboard.html", icon: "📊", label: "Resumen" },
    { key: "users", href: "users.html", icon: "👥", label: "Usuarios" },
    { key: "jobs", href: "jobs.html", icon: "📋", label: "Vacantes" },
    { key: "matches", href: "matches.html", icon: "💚", label: "Matches" },
    { key: "activity", href: "activity.html", icon: "🕑", label: "Actividad" },
  ],
};

function link({ key, href, icon, label }, active, withIcon) {
  const a = document.createElement("a");
  a.href = href;
  if (key === active) {
    a.className = "active";
    a.setAttribute("aria-current", "page");
  }
  if (withIcon) {
    const i = document.createElement("span");
    i.className = "nav-icon";
    i.setAttribute("aria-hidden", "true");
    i.textContent = icon;
    a.append(i);
  }
  a.append(label);
  return a;
}

export function renderNav(role, active) {
  const links = LINKS[role];

  const header = document.createElement("header");
  header.className = "navbar";
  const inner = document.createElement("div");
  inner.className = "navbar-inner";

  const brand = document.createElement("a");
  brand.href = links[0].href;
  brand.className = "brand brand-sm";
  const span = document.createElement("span");
  span.textContent = "Jobmatch";
  brand.append("Empléate ", span);

  const nav = document.createElement("nav");
  nav.className = "nav-links";
  nav.setAttribute("aria-label", "Secciones");
  links.forEach((l) => nav.append(link(l, active, false)));

  const user = document.createElement("div");
  user.className = "nav-user";
  const name = document.createElement("span");
  name.className = "nav-user-name";
  name.textContent = localStorage.getItem("email") || "";
  const theme = document.createElement("button");
  theme.type = "button";
  theme.className = "theme-toggle theme-toggle-inline";
  theme.setAttribute("data-theme-toggle", ""); // theme.js le pone el ícono y el clic
  theme.setAttribute("aria-label", "Cambiar tema");
  const out = document.createElement("button");
  out.type = "button";
  out.className = "btn btn-ghost btn-sm";
  out.textContent = "Salir";
  out.addEventListener("click", logout);
  user.append(name, theme, out);

  inner.append(brand, nav, user);
  header.append(inner);

  const bottom = document.createElement("nav");
  bottom.className = "bottom-nav";
  bottom.setAttribute("aria-label", "Secciones");
  links.forEach((l) => bottom.append(link(l, active, true)));

  document.body.prepend(header);
  document.body.append(bottom);
  document.body.classList.add("has-bottom-nav");

  // Nombre real del usuario o de la empresa (si falla, se queda el correo)
  getMe().then((me) => { name.textContent = me.display_name; }).catch(() => {});
}

export function renderApplicantNav(active) {
  renderNav("aspirante", active);
}
