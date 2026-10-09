// Sesión en el navegador y guardia de rutas por rol.

// Las rutas se resuelven desde la ubicación de ESTE archivo (assets/js/utils/),
// así funcionan sin importar desde qué página se llamen.
const page = (path) => new URL(`../../../pages/${path}`, import.meta.url).href;

export const ROLE_HOME = {
  aspirante: "applicant/swipe.html",
  empresa: "company/jobs.html",
  administrador: "admin/dashboard.html",
};

export function saveSession({ access_token, role, email }) {
  localStorage.setItem("token", access_token);
  localStorage.setItem("role", role);
  localStorage.setItem("email", email);
}

export function getToken() {
  return localStorage.getItem("token");
}

export function getRole() {
  return localStorage.getItem("role");
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  localStorage.removeItem("email");
}

export function redirectByRole(role) {
  window.location.href = page(ROLE_HOME[role] ?? "auth/login.html");
}

// Úsalo al inicio de cada pantalla protegida: requireRole("empresa")
export function requireRole(expectedRole) {
  if (!getToken() || getRole() !== expectedRole) {
    clearSession();
    window.location.href = page("auth/login.html");
  }
}

export function logout() {
  clearSession();
  window.location.href = page("auth/login.html");
}