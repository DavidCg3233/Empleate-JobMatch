# Imagen del backend (FastAPI). Railway la construye con "Root Directory" = backend.
# Solo incluye la API: las páginas de frontend/ se publican aparte en Vercel.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --proxy-headers y --forwarded-allow-ips: la app recibe la IP real del usuario detrás de
# Vercel y Railway. Sin ellos, el límite de intentos por IP sería el mismo para todos.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
