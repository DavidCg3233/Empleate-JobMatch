// Validaciones del lado del cliente. Cada función devuelve un mensaje de error
// o "" si el valor es válido. (El backend vuelve a validar todo.)

export const isEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

export function emailError(v) {
  if (!v) return "Escribe tu correo electrónico.";
  return isEmail(v) ? "" : "El correo no es válido.";
}

export function passwordError(v) {
  if (!v) return "Escribe una contraseña.";
  if (v.length < 8) return "Debe tener al menos 8 caracteres.";
  if (v.length > 64) return "No puede superar los 64 caracteres.";
  if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) return "Debe incluir letras y números.";
  return "";
}

export function phoneError(v) {
  if (!v) return ""; // opcional
  return /^\+?[0-9 ()\-]{7,20}$/.test(v) ? "" : "El teléfono no es válido.";
}

export function nitError(v) {
  if (!v) return "Escribe el NIT de la empresa.";
  const clean = v.replace(/[.\s]/g, "");
  return /^\d{5,15}(-\d)?$/.test(clean) ? "" : "El NIT no es válido. Ejemplo: 900123456-7";
}

export function websiteError(v) {
  if (!v) return ""; // opcional
  const url = /^https?:\/\//i.test(v) ? v : `https://${v}`;
  return /^https?:\/\/[^\s/]+\.[^\s/]+(\/\S*)?$/i.test(url) ? "" : "El sitio web no es válido.";
}

export const requiredError = (message) => (v) => (v ? "" : message);
export const minLengthError = (message, min) => (v) => (v && v.length >= min ? "" : message);