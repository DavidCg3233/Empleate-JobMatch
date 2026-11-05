# Despliegue de la versión beta

Guía para publicar Empléate Jobmatch en internet. No necesitas instalar Docker: Railway construye la imagen
desde GitHub con `backend/Dockerfile`.

| Parte | Dónde | Archivo de configuración |
|---|---|---|
| Páginas (`frontend/`) | Vercel | `frontend/vercel.json` |
| API (FastAPI) | Railway, con Docker | `backend/Dockerfile` |
| Base de datos MySQL | Railway | `Empleate JObMatch database.sql` |
| Hojas de vida | Volumen de Railway | Se monta en `/app/uploads` |

El navegador solo habla con Vercel. Vercel reenvía las rutas `/api/...` a Railway, así que no hace falta
configurar CORS ni cambiar `frontend/assets/js/config.js`.

Antes de empezar, sube a GitHub los archivos de despliegue. Railway y Vercel leen el código desde allá.

Los nombres de algunos botones pueden variar un poco.

## 1. Publica el backend en Railway

1. Entra a [railway.com](https://railway.com) e inicia sesión con GitHub.
2. Elige **New Project > Deploy from GitHub repo** y selecciona este repositorio.
   Es normal que este primer intento falle, porque aún faltan las variables.
3. Abre el servicio y, en **Settings**, pon `backend` como **Root Directory**.
4. En el proyecto, usa **+ New** y agrega **MySQL**.
5. Genera una clave para las sesiones en tu terminal:

   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

6. En la pestaña **Variables** del backend, agrega lo siguiente. `MySQL` debe coincidir con el nombre del
   servicio de base de datos en tu proyecto.

   ```
   DB_HOST=${{MySQL.MYSQLHOST}}
   DB_PORT=${{MySQL.MYSQLPORT}}
   DB_USER=${{MySQL.MYSQLUSER}}
   DB_PASSWORD=${{MySQL.MYSQLPASSWORD}}
   DB_NAME=jobmatch
   JWT_SECRET=PEGA_TU_CLAVE
   PORT=8000
   AI_PROVIDER=none
   MAX_CV_MB=4
   ```

7. Presiona `Ctrl + K`, busca **Volume**, conéctalo al backend y usa la ruta `/app/uploads`.
8. En el backend, ve a **Settings > Networking > Public Networking > Generate Domain** y usa el puerto `8000`.
   Guarda la URL, que en esta guía aparece como `TU-BACKEND.up.railway.app`.

En los logs de construcción debe aparecer `Using detected Dockerfile!`.

## 2. Carga la base de datos

1. En el servicio MySQL, ve a **Settings > Networking** y activa **Public Access**. Se crea la variable
   `MYSQL_PUBLIC_URL`, con este formato:

   ```
   mysql://USUARIO:CLAVE@HOST:PUERTO/railway
   ```

2. Crea una conexión en MySQL Workbench con esos datos.
3. Abre `Empleate JObMatch database.sql` con **File > Open SQL Script** y ejecútalo con el botón del rayo.
   El script crea la base `jobmatch`.
4. Desde `backend/`, con el entorno virtual activo, carga las habilidades y crea el administrador:

   ```powershell
   $env:DB_HOST="HOST"; $env:DB_PORT="PUERTO"; $env:DB_USER="USUARIO"; $env:DB_PASSWORD="CLAVE"; $env:DB_NAME="jobmatch"
   python -m scripts.migrate_skills_catalog
   python -m scripts.create_admin tucorreo@ejemplo.com
   ```

   Esas variables solo duran en esa terminal y tienen prioridad sobre tu `.env`, que no cambia.
   `scripts.migrate_ai_matching` no hace falta en una base nueva: el script SQL ya incluye esas columnas.

5. Desactiva **Public Access**. Ese acceso expone la base a internet y su tráfico se cobra.
6. Abre `https://TU-BACKEND.up.railway.app/api/health`. Debe responder:

   ```json
   {"status":"ok","database":"connected"}
   ```

   Que la raíz `/` de esa URL responda 404 es normal, porque ese servicio solo tiene la API.

## 3. Publica las páginas en Vercel

1. En `frontend/vercel.json`, reemplaza `TU-BACKEND.up.railway.app` por tu URL de Railway y sube el cambio a GitHub.
2. Entra a [vercel.com](https://vercel.com), inicia sesión con GitHub y elige **Add New > Project**.
3. Importa el repositorio, pon `frontend` como **Root Directory**, elige **Other** como **Framework Preset** y
   pulsa **Deploy**.
4. Copia la URL que te dé Vercel. En Railway, agrega esta variable al backend:

   ```
   FRONTEND_URL=https://TU-APP.vercel.app
   ```

## 4. Prueba la aplicación

Abre tu URL de Vercel y comprueba que puedes:

- [ ] Registrar un aspirante con una hoja de vida.
- [ ] Registrar una empresa y publicar una vacante.
- [ ] Iniciar sesión como aspirante, como empresa y como administrador.
- [ ] Descargar la hoja de vida.
- [ ] Conservar la hoja de vida después de redesplegar el backend en Railway.

## Limitaciones de la beta

- **Correo:** el plan Hobby de Railway bloquea el SMTP. Deja `SMTP_HOST` vacío y el enlace de recuperación de
  contraseña aparecerá en los logs del backend. Para enviar correos reales hay que cambiar
  `backend/app/services/email_service.py` a una API de correo por HTTPS.
- **Hojas de vida:** el máximo queda en 4 MB porque Vercel limita sus Functions a 4.5 MB por petición y no está
  confirmado si ese límite afecta al proxy.
- **IA:** con `AI_PROVIDER=none`, la app funciona solo con reglas y sin costo. Para activarla, define
  `AI_PROVIDER` y su clave únicamente en las variables de Railway.
- **Datos de ejemplo:** `scripts.seed_demo` crea empresas con la clave conocida `Demo1234`. No lo ejecutes si la
  URL será pública.
- **Redespliegues:** un servicio con volumen se detiene unos instantes cada vez que se redespliega.
- **Costo:** Railway da una prueba de $5 por una sola vez, con volumen de 0.5 GB. El plan Hobby cuesta $5 al mes e
  incluye $5 de uso. Consulta los [precios actuales](https://railway.com/pricing).

## Si algo falla

| Síntoma | Qué revisar |
|---|---|
| El build falla en Railway | Que **Root Directory** sea `backend` y que `Dockerfile` esté en GitHub |
| El backend se reinicia y los logs mencionan `DB_USER` o `JWT_SECRET` | Faltan variables en Railway |
| `/api/health` responde 500 | Que `DB_NAME` sea `jobmatch` y que el script SQL se haya ejecutado |
| La URL de Railway no responde | Que `PORT=8000` exista y que el dominio use el puerto `8000` |
| Las páginas cargan, pero iniciar sesión da error de conexión | La URL de `frontend/vercel.json` |
| No hay sugerencias de habilidades | Falta ejecutar `scripts.migrate_skills_catalog` |
| El enlace de recuperación abre otra dirección | La variable `FRONTEND_URL` |
| Las hojas de vida desaparecen al redesplegar | Que el volumen esté montado en `/app/uploads` |

Los errores del backend aparecen en **Deploy Logs**, en Railway.
