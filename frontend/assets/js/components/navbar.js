// Barra de navegación del aspirante (arriba en escritorio, abajo en el celular).
// Uso: renderApplicantNav("swipe" | "search" | "matches")
import { getMe } from "../api/authApi.js";
import { logout } from "../utils/auth.js";

const LINKS = [
  { key: "swipe", href: "swipe.html", icon: "🧭", label: "Explorar" },
  { key: "search", href: "search.html", icon: "🔎", label: "Buscar" },
  { key: "matches", href: "matches.html", icon: "💚", label: "Mis matches" },
];

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

export function renderApplicantNav(active) {
  const header = document.createElement("header");
  header.className = "navbar";
  const inner = document.createElement("div");
  inner.className = "navbar-inner";

  const brand = document.createElement("a");
  brand.href = "swipe.html";
  brand.className = "brand brand-sm";
  const span = document.createElement("span");
  span.textContent = "Jobmatch";
  brand.append("Empléate ", span);

  const links = document.createElement("nav");
  links.className = "nav-links";
  links.setAttribute("aria-label", "Secciones");
  LINKS.forEach((l) => links.append(link(l, active, false)));

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

  inner.append(brand, links, user);
  header.append(inner);

  const bottom = document.createElement("nav");
  bottom.className = "bottom-nav";
  bottom.setAttribute("aria-label", "Secciones");
  LINKS.forEach((l) => bottom.append(link(l, active, true)));

  document.body.prepend(header);
  document.body.append(bottom);
  document.body.classList.add("has-bottom-nav");

  // Nombre real del usuario (si falla, se queda el correo)
  getMe().then((me) => { name.textContent = me.display_name; }).catch(() => {});
}
