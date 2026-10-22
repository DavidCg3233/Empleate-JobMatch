// Dirección del backend (FastAPI).
// - Si las páginas las sirve el mismo backend (http://127.0.0.1:8000/...), la API está en el mismo sitio: /api
// - Si se abren con Live Server (http://127.0.0.1:5500/frontend/...), la API está en el puerto 8000.
const servedByBackend = !window.location.pathname.startsWith("/frontend/");

export const API_URL = servedByBackend ? `${window.location.origin}/api` : "http://127.0.0.1:8000/api";
