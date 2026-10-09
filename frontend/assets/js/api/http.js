// Cliente HTTP base: agrega el token JWT y normaliza los errores.
import { API_URL } from "../config.js";
import { getToken } from "../utils/auth.js";

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

  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

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
  if (!response.ok) throw new ApiError(extractMessage(data), response.status, data);
  return data;
}