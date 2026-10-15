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

// ¿El token JWT ya venció? (se lee su fecha "exp"; el backend igual lo vuelve a verificar)
export function isTokenExpired(token = getToken()) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return !payload.exp || payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

// Úsalo al inicio de cada pantalla protegida: requireRole("empresa")
// Devuelve false (y envía al login) si no hay una sesión válida con ese rol.
export function requireRole(expectedRole) {
  if (!getToken() || isTokenExpired() || getRole() !== expectedRole) {
    clearSession();
    window.location.href = page("auth/login.html");
    return false;
  }
  return true;
}

export function logout() {
  clearSession();
  window.location.href = page("auth/login.html");
}