import { http } from "./http.js";

// ---------- Login ----------
export function login(email, password) {
  return http("/auth/login", { method: "POST", body: { email, password }, auth: false });
}

export function getMe() {
  return http("/auth/me");
}

// ---------- Registro ----------
export function registerApplicant(payload) {
  return http("/auth/register/applicant", { method: "POST", body: payload, auth: false });
}

export function registerCompany(payload) {
  return http("/auth/register/company", { method: "POST", body: payload, auth: false });
}

/** Sube la hoja de vida (PDF/DOCX) y devuelve los datos para autocompletar el registro. */
export function parseCv(file) {
  const form = new FormData();
  form.append("file", file);
  return http("/auth/cv/parse", { method: "POST", body: form, auth: false });
}

// ---------- Recuperación de contraseña ----------
export function forgotPassword(email) {
  return http("/auth/forgot-password", { method: "POST", body: { email }, auth: false });
}

export function validateResetToken(token) {
  return http(`/auth/reset-password/validate?token=${encodeURIComponent(token)}`, { auth: false });
}

export function resetPassword(token, password) {
  return http("/auth/reset-password", { method: "POST", body: { token, password }, auth: false });
}

// ---------- Contraseña (con la sesión iniciada) ----------
export function changePassword(currentPassword, newPassword) {
  return http("/auth/change-password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}
