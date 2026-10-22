// Cliente HTTP base: agrega el token JWT y normaliza los errores.
import { API_URL } from "../config.js";
import { clearSession, getToken, logout } from "../utils/auth.js";

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function extractMessage(data) {
  const detail = data?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    let msg = detail.message || "Ocurrió un error.";
    if (typeof detail.remaining_attempts === "number") {
      const n = detail.remaining_attempts;
      msg += ` Te ${n === 1 ? "queda 1 intento" : `quedan ${n} intentos`}.`;
    }
    return msg;
  }
  if (Array.isArray(detail)) return "Revisa que los datos ingresados sean válidos.";
  if (typeof detail === "string") return detail;
  return "Ocurrió un error inesperado.";
}

/**
 * http("/auth/login", { method: "POST", body: {...}, auth: false })
 * Lanza ApiError si la respuesta no es 2xx.
 */
export async function http(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  const isForm = body instanceof FormData;
  const token = auth ? getToken() : null;

  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servidor. Verifica que el backend esté encendido.", 0, null);
  }

  const data = await response.json().catch(() => ({}));
  handleExpiredSession(response, token);
  if (!response.ok) throw new ApiError(extractMessage(data), response.status, data);
  return data;
}

// La sesión venció o es inválida: se cierra y se vuelve al login (salvo que ya esté en las pantallas de acceso)
function handleExpiredSession(response, token) {
  if (response.status === 401 && token) {
    if (/\/pages\/auth\//.test(window.location.pathname)) clearSession();
    else logout();
  }
}

// 'attachment; filename="cv.pdf"'  o  "attachment; filename*=utf-8''Mi%20CV.pdf"
function filenameFrom(disposition, fallback) {
  const encoded = /filename\*=(?:UTF-8|utf-8)''([^;]+)/.exec(disposition || "");
  if (encoded) {
    try { return decodeURIComponent(encoded[1]); } catch { /* nombre mal codificado */ }
  }
  const plain = /filename="?([^";]+)"?/.exec(disposition || "");
  return plain ? plain[1] : fallback;
}

/** Descarga un archivo protegido (con el token) y lo guarda con el nombre que envía el servidor. */
export async function downloadFile(path, fallbackName = "archivo") {
  const token = getToken();
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError("No se pudo conectar con el servidor. Verifica que el backend esté encendido.", 0, null);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    handleExpiredSession(response, token);
    throw new ApiError(extractMessage(data), response.status, data);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFrom(response.headers.get("Content-Disposition"), fallbackName);
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}