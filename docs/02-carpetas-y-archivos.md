# 2. Carpetas y archivos

Esta guía recorre el proyecto carpeta por carpeta y explica para qué sirve cada archivo. Úsala como un mapa cuando
abras el código.

> Guía anterior: [1. Qué hace la app](01-que-hace-la-app.md) · Siguiente: [3. Cómo funciona por dentro](03-como-funciona-por-dentro.md)

## Contenido

- [Vista general](#vista-general)
- [Archivos de la raíz](#archivos-de-la-raíz)
- [backend/](#backend)
- [frontend/](#frontend)
- [docs/](#docs)
- [Lo que no está en GitHub](#lo-que-no-está-en-github)

## Vista general

El proyecto tiene dos mitades que se comunican por internet:

| Carpeta | Qué es | Lenguaje | Dónde corre en producción |
|---|---|---|---|
| `backend/` | El servidor: reglas, datos, seguridad y la API | Python | Railway |
| `frontend/` | Las páginas que ve la gente | HTML, CSS y JavaScript | Vercel |

```text
Empleate-JobMatch/
├── README.md                         Presentación del proyecto y cómo arrancarlo
├── DOCUMENTACION.md                  Índice de esta documentación
├── DESPLIEGUE.md                     Pasos para publicar en Railway y Vercel desde cero
├── Empleate JObMatch database.sql    Crea la base de datos completa
├── .gitignore                        Archivos que Git no debe subir
├── .vscode/                          Configuración del editor (archivos vacíos)
├── docs/                             Estas guías
├── backend/                          El servidor (FastAPI)
└── frontend/                         Las páginas
```

## Archivos de la raíz

| Archivo | Para qué sirve |
|---|---|
| `README.md` | Lo primero que se ve en GitHub: qué es la app, cómo arrancarla y enlaces a la documentación |
| `DOCUMENTACION.md` | Índice de las guías de `docs/` y resumen rápido |
| `DESPLIEGUE.md` | Guía para publicar la app desde cero en Railway y Vercel |
| `Empleate JObMatch database.sql` | Script que crea la base `jobmatch`, sus 25 tablas y los datos iniciales: roles, departamentos, ciudades, sectores, niveles educativos, idiomas y tipos de contrato |
| `.gitignore` | Evita que se suban a GitHub `venv/`, `.env`, `backend/uploads/` y archivos temporales de Python |
| `.vscode/` | Configuración de Visual Studio Code. Hoy sus archivos están vacíos |

## backend/

```text
backend/
├── main.py              Punto de entrada: crea la aplicación y registra las rutas
├── requirements.txt     Librerías de Python que necesita el proyecto
├── Dockerfile           Receta para construir el servidor en Railway
├── .dockerignore        Archivos que no se copian al construir en Railway
├── .env.example         Plantilla de configuración, sin secretos
├── pytest.ini           Configuración de las pruebas
├── alembic.ini          Archivo vacío, no se usa
├── app/                 El código de la aplicación
├── scripts/             Tareas que se ejecutan a mano
└── tests/               Pruebas automáticas
```

| Archivo | Para qué sirve |
|---|---|
| `main.py` | Crea la aplicación FastAPI, activa CORS, registra todas las rutas, define `/api/health` y, si existe la carpeta `frontend/`, sirve también las páginas |
| `requirements.txt` | FastAPI, Uvicorn (el servidor), SQLAlchemy (base de datos), PyMySQL (conexión con MySQL), Pydantic (validación), PyJWT y bcrypt (seguridad), pypdf y python-docx (lectura de hojas de vida), anthropic y httpx (IA) y pytest (pruebas) |
| `Dockerfile` | Parte de Python 3.14, instala `requirements.txt`, copia el código y arranca Uvicorn en el puerto `PORT` |
| `.dockerignore` | Deja fuera de la imagen `.env`, `venv/`, `uploads/`, `tests/` y los archivos temporales |
| `.env.example` | Lista de todas las variables de configuración, con valores de ejemplo |
| `pytest.ini` | Indica que las pruebas están en `tests/` y que se ejecutan desde `backend/` |
| `alembic.ini` | Está vacío. El proyecto no usa Alembic: las migraciones se hacen con los scripts de `scripts/` |

### backend/app/

Aquí está toda la lógica. Está organizada en capas: cada carpeta tiene un trabajo.

```text
app/
├── config.py          Lee la configuración
├── database.py        Conexión con MySQL
├── controllers/       Rutas de la API (la puerta de entrada)
├── schemas/           Validación de lo que entra y sale
├── services/          Reglas del negocio (el trabajo de verdad)
├── models/            Tablas de la base de datos
├── core/              Seguridad, permisos y errores
├── data/              Datos fijos (catálogo de habilidades)
└── utils/             Utilidades generales
```

| Archivo | Para qué sirve |
|---|---|
| `config.py` | Reúne todas las variables de configuración en un objeto `settings`. Las lee de `backend/.env` en local o de las variables de Railway en producción |
| `database.py` | Crea la conexión con MySQL usando `DB_HOST`, `DB_USER`, etc., y entrega una sesión de base de datos a cada petición |

#### controllers/: rutas de la API

Cada archivo agrupa las rutas de un tema. Un controlador recibe la petición, comprueba quién la hace y llama al
servicio correspondiente. No contiene reglas del negocio.

| Archivo | Rutas | Quién las usa |
|---|---|---|
| `auth_controller.py` | `/api/auth/...`: inicio de sesión, lectura de hoja de vida, registro, recuperar y cambiar contraseña, eliminar cuenta | Público o con sesión |
| `catalog_controller.py` | `/api/catalogs/...`: ciudades, sectores, niveles educativos, idiomas, contratos y sugerencias de habilidades | Público |
| `applicant_controller.py` | `/api/applicant/...`: perfil y hoja de vida | Aspirante |
| `job_controller.py` | `/api/jobs/...` (tarjetas, búsqueda y detalle) y `/api/company/jobs/...` (vacantes y candidatos de la empresa) | Aspirante y empresa |
| `swipe_controller.py` | `/api/swipes/...`: registrar y deshacer decisiones | Aspirante y empresa |
| `match_controller.py` | `/api/matches/...`: matches, etapa del proceso y descarga de hoja de vida | Aspirante y empresa |
| `matching_controller.py` | `/api/matching/...`: estado de la IA y análisis de compatibilidad | Público el estado; aspirante y empresa el análisis |
| `company_controller.py` | `/api/company/profile` | Empresa |
| `admin_controller.py` | `/api/admin/...`: estadísticas, usuarios, vacantes, matches y actividad | Administrador |

#### schemas/: validación de datos

Definen la forma exacta de los datos que entran y salen de la API. Si llega un dato inválido (un correo mal escrito,
una etapa que no existe), la petición se rechaza con un error 422 antes de tocar la base de datos.

| Archivo | Valida |
|---|---|
| `auth_schema.py` | Registro, inicio de sesión, contraseñas y sus reglas |
| `applicant_schema.py` | Experiencia, educación, habilidades e idiomas del aspirante |
| `profile_schema.py` | El perfil completo que ve y edita el aspirante |
| `company_schema.py` | Perfil de empresa, vacantes, candidatos y matches de la empresa |
| `job_schema.py` | Vacantes vistas por el aspirante |
| `swipe_schema.py` | Decisiones, matches del aspirante y etapas del proceso |
| `catalog_schema.py` | Respuestas de los catálogos |
| `admin_schema.py` | Respuestas del panel de administrador |

#### services/: reglas del negocio

Aquí se toman las decisiones: quién puede ver qué, cuándo hay match, cómo se calcula la compatibilidad.

| Archivo | Responsabilidad |
|---|---|
| `auth_service.py` | Registro de aspirantes y empresas, inicio de sesión con bloqueo, recuperación y cambio de contraseña |
| `account_service.py` | Eliminar una cuenta con todos sus datos |
| `applicant_service.py` | Ver y editar el perfil del aspirante, y reemplazar su hoja de vida |
| `company_service.py` | Perfil de empresa y vacantes: crear, editar, cambiar estado y eliminar |
| `job_service.py` | Lado del aspirante: tarjetas, búsqueda, detalle, decisiones y sus matches |
| `candidate_service.py` | Lado de la empresa: candidatos, decisiones, matches, etapas y descarga de hojas de vida |
| `matching_service.py` | Porcentaje de compatibilidad por reglas, con razones a favor y en contra |
| `ai_matching_service.py` | Afinidad semántica y análisis con IA, con caché para no pagar dos veces |
| `cv_parser_service.py` | Lectura de hojas de vida: extrae el texto, lo interpreta con IA o con reglas y limpia los datos |
| `skill_service.py` | Catálogo de habilidades y sugerencias mientras se escribe |
| `storage_service.py` | Guardar, mover y borrar archivos en disco, dentro de `uploads/` |
| `email_service.py` | Enviar correos por SMTP o, si no hay SMTP configurado, imprimirlos en la consola |
| `admin_service.py` | Datos y acciones del panel de administrador |
| `audit_service.py` | Registrar acciones en la bitácora |

`services/ai/` contiene la conexión con los proveedores de IA:

| Archivo | Para qué sirve |
|---|---|
| `base.py` | Interfaz común. Elige el proveedor según `AI_PROVIDER` y devuelve "ninguno" si falta la clave |
| `openai_provider.py` | Habla con OpenAI: respuestas en JSON y embeddings |
| `claude_provider.py` | Habla con Claude (Anthropic) |
| `prompts.py` | Las instrucciones que se envían a la IA para leer hojas de vida y analizar parejas |

#### models/: tablas de la base de datos

Cada clase representa una tabla. SQLAlchemy las usa para leer y escribir sin escribir SQL a mano.

| Archivo | Tablas |
|---|---|
| `user.py` | `users`: correo, contraseña cifrada, rol, intentos fallidos y bloqueo |
| `role.py` | `roles`: aspirante, empresa y administrador |
| `applicant.py` | `applicants`: perfil del aspirante y ruta de su hoja de vida |
| `applicant_profile.py` | `applicant_experiences`, `applicant_educations`, `applicant_skills`, `applicant_languages` |
| `company.py` | `companies`: datos y contacto de la empresa |
| `job.py` | `jobs`, `job_skills` y `contract_types` |
| `swipe.py` | `applicant_swipes` y `company_swipes`: las decisiones de cada lado |
| `match.py` | `matches`: los matches y su etapa del proceso |
| `match_score.py` | `match_scores`, `applicant_embeddings`, `job_embeddings`: caché de la IA |
| `catalogs.py` | `skills`, `education_levels`, `languages` |
| `city.py` | `departments` y `cities` |
| `industry.py` | `industries`: sectores |
| `password_reset.py` | `password_resets`: enlaces de recuperación (solo su huella, nunca el enlace) |
| `audit_log.py` | `audit_logs`: la bitácora |

#### core/: seguridad y errores

| Archivo | Para qué sirve |
|---|---|
| `security.py` | Cifra y verifica contraseñas con bcrypt; crea y lee los tokens de sesión (JWT) |
| `dependencies.py` | Protege las rutas: identifica al usuario por su token y comprueba su rol |
| `exceptions.py` | Da a todos los errores el mismo formato: `{"detail": {"message": "..."}}` |

#### data/ y utils/

| Archivo | Para qué sirve |
|---|---|
| `data/skills_catalog.py` | Catálogo curado de habilidades técnicas, herramientas y habilidades blandas |
| `utils/file_validators.py` | Revisa la extensión, el tamaño y el contenido real de los archivos subidos |
| `utils/helpers.py` | Normaliza textos (sin tildes ni mayúsculas) y limita peticiones por IP |

### backend/scripts/

Tareas que se ejecutan a mano desde `backend/`, con `python -m scripts.<nombre>`:

| Script | Para qué sirve |
|---|---|
| `create_admin.py` | Crea el administrador, o le cambia la contraseña y lo desbloquea |
| `migrate_skills_catalog.py` | Prepara la tabla `skills` y carga el catálogo. Se puede repetir sin duplicar datos |
| `migrate_ai_matching.py` | Agrega las columnas de caché de la IA a una base creada antes de esa función |
| `migrate_match_stages.py` | Agrega o corrige las columnas de etapas en `matches` |
| `seed_demo.py` | Crea empresas y vacantes de ejemplo con una contraseña conocida. **Nunca en producción** |

### backend/tests/

Pruebas automáticas que comprueban que todo funcione. Usan una base SQLite en memoria, así que no tocan MySQL ni
servicios externos.

| Archivo | Qué prueba |
|---|---|
| `conftest.py` | Prepara cada prueba: base temporal, catálogos y correos capturados |
| `cv_samples.py` | Genera hojas de vida de ejemplo en Word y PDF |
| `test_auth.py` | Registro, inicio de sesión, bloqueo y recuperación de contraseña |
| `test_profile.py` | Perfil del aspirante, hoja de vida nueva, cambio de contraseña y términos |
| `test_cv_parser.py` | Lectura de hojas de vida sin IA |
| `test_jobs.py` | Tarjetas, búsqueda, detalle, decisiones y matches del aspirante |
| `test_company.py` | Perfil de empresa, vacantes, candidatos, matches, etapas y hojas de vida |
| `test_matching.py` | Cálculo de compatibilidad |
| `test_ai_matching.py` | IA simulada: afinidad, caché, análisis, permisos y privacidad |
| `test_admin.py` | Panel de administrador, bitácora y eliminación de cuentas |
| `test_frontend.py` | Que el backend sirva las páginas en local |
| `test_db.py` | Prueba manual de conexión con MySQL; no corre con las demás |

## frontend/

```text
frontend/
├── index.html         Página de inicio
├── favicon.ico        Icono de la pestaña
├── vercel.json        Configuración de Vercel
├── pages/             Una carpeta por rol
└── assets/
    ├── css/           Estilos
    └── js/            Lógica de las páginas
```

No hay framework ni paso de compilación: el navegador carga los archivos tal como están. El JavaScript usa
**módulos** (`import` y `export`), por eso las páginas deben abrirse desde un servidor y no con doble clic.

| Archivo | Para qué sirve |
|---|---|
| `index.html` | Portada con los botones "Iniciar sesión" y "Crear cuenta" |
| `vercel.json` | Le dice a Vercel que reenvíe las rutas `/api/...` al backend de Railway (ver la [guía 4](04-infraestructura-y-publicacion.md#vercel-las-páginas)) |

### frontend/pages/

Cada página HTML tiene su controlador en `assets/js/controllers/`.

| Página | Qué muestra | Controlador |
|---|---|---|
| `auth/login.html` | Inicio de sesión | `loginController.js` |
| `auth/register.html` | Registro de aspirante o empresa, con lectura de hoja de vida | `registerController.js` |
| `auth/forgot_password.html` | Pedir el enlace de recuperación | `forgotPasswordController.js` |
| `auth/reset_password.html` | Crear la contraseña nueva | `resetPasswordController.js` |
| `applicant/swipe.html` | Explorar: tarjetas de vacantes | `applicantSwipeController.js` |
| `applicant/search.html` | Buscador con filtros | `applicantSearchController.js` |
| `applicant/matches.html` | Mis matches y vacantes que me interesan | `applicantMatchesController.js` |
| `applicant/profile.html` | Mi perfil | `applicantProfileController.js` |
| `applicant/onboarding.html` | Archivo vacío, no se usa | — |
| `company/jobs.html` | Mis vacantes | `jobsController.js` |
| `company/job_form.html` | Crear o editar una vacante | `jobFormController.js` |
| `company/swipe.html` | Candidatos en tarjetas | `companySwipeController.js` |
| `company/matches.html` | Matches con contacto, hoja de vida y etapa | `companyMatchesController.js` |
| `company/company.html` | Perfil de la empresa | `companyProfileController.js` |
| `admin/dashboard.html` | Resumen | `adminController.js` |
| `admin/users.html` | Usuarios | `adminUsersController.js` |
| `admin/jobs.html` | Vacantes | `adminJobsController.js` |
| `admin/matches.html` | Matches | `adminMatchesController.js` |
| `admin/activity.html` | Bitácora | `adminActivityController.js` |
| `legal/terminos.html` | Términos y política de datos | — |

### frontend/assets/js/

```text
js/
├── config.js        Dirección de la API
├── api/             Llamadas al backend
├── controllers/     Lógica de cada página (tabla anterior)
├── components/      Piezas reutilizables
└── utils/           Sesión, tema, formatos y validaciones
```

| Archivo | Para qué sirve |
|---|---|
| `config.js` | Calcula la dirección de la API. Si la página la sirve el backend o Vercel, usa la misma dirección + `/api` |

**api/**: cada archivo agrupa las llamadas a un tema del backend.

| Archivo | Llama a |
|---|---|
| `http.js` | Base de todas las llamadas: agrega el token, convierte errores en mensajes claros y cierra la sesión si vence. También descarga archivos protegidos |
| `authApi.js` | Inicio de sesión, registro, hoja de vida y contraseñas |
| `applicantApi.js` | Perfil y matches del aspirante |
| `jobApi.js` | Tarjetas, búsqueda y detalle de vacantes |
| `swipeApi.js` | Decisiones del aspirante |
| `companyApi.js` | Perfil, vacantes, candidatos, matches, etapas y hojas de vida de la empresa |
| `matchingApi.js` | Estado y análisis de la IA |
| `catalogApi.js` | Catálogos |
| `adminApi.js` | Panel de administrador |

**components/**: piezas que se repiten en varias pantallas.

| Archivo | Qué hace |
|---|---|
| `swipeDeck.js` | La pila de tarjetas: arrastrar con el dedo o el ratón, flechas del teclado y deshacer |
| `swipecard.js` | Tarjeta de vacante para la pila y para la lista del buscador |
| `candidateCard.js` | Tarjeta del aspirante y su perfil completo, vistos por la empresa |
| `jobDetail.js` | Ventana con el detalle de una vacante |
| `matchReasons.js` | Razones a favor y en contra de la compatibilidad |
| `aiAnalysis.js` | Sección "Análisis con IA" |
| `matchStage.js` | Barra de etapas y selector de la empresa |
| `matchOverlay.js` | Celebración "¡Es un match!" |
| `navbar.js` | Menú: arriba en computador y abajo en celular |
| `modal.js` | Ventanas y confirmaciones |
| `toast.js` | Avisos cortos que desaparecen solos |
| `filters.js` | Grupo de botones de filtro |
| `profileEditor.js` | Editor de experiencia, educación, habilidades e idiomas |
| `skillAutocomplete.js` | Sugerencias de habilidades mientras se escribe |
| `moneyInput.js` | Campo de dinero con puntos de miles |
| `passwordForm.js` | Formulario de cambio de contraseña |
| `deleteAccount.js` | Sección para eliminar la cuenta |
| `adminUi.js` | Tablas, paginación y textos del panel de administrador |

**utils/**:

| Archivo | Qué hace |
|---|---|
| `auth.js` | Guarda la sesión en el navegador y protege cada página según el rol |
| `dom.js` | Crea elementos HTML de forma segura, sin `innerHTML` |
| `format.js` | Formatos de fechas, dinero y textos |
| `validators.js` | Validaciones de formularios antes de enviarlos |
| `theme.js` | Modo claro y oscuro, aplicado antes de pintar la página para evitar parpadeos |

### frontend/assets/css/

| Archivo | Estilos de |
|---|---|
| `main.css` | Base de toda la app: colores, tipografía, botones, formularios y modo oscuro |
| `swipe.css` | Pantallas con sesión: menú, tarjetas, ventanas, listas, matches y barra de etapas |
| `company.css` | Detalles propios de las pantallas de empresa |
| `admin.css` | Panel de administrador |

## docs/

| Archivo | Tema |
|---|---|
| `01-que-hace-la-app.md` | Qué hace la app y para quién |
| `02-carpetas-y-archivos.md` | Esta guía |
| `03-como-funciona-por-dentro.md` | Cómo funciona por dentro |
| `04-infraestructura-y-publicacion.md` | GitHub, Railway y Vercel |
| `05-trabajo-local-y-cambios.md` | Trabajar en local y publicar cambios |

## Lo que no está en GitHub

Estas carpetas y archivos existen solo en tu computador. `.gitignore` evita que se suban:

| Ruta | Qué es | Por qué no se sube |
|---|---|---|
| `backend/.env` | Configuración local: contraseña de MySQL, clave de sesiones y claves de IA | Contiene secretos |
| `backend/venv/` | Las librerías de Python instaladas | Pesa mucho y se vuelve a crear con `requirements.txt` |
| `backend/uploads/` | Hojas de vida subidas en local | Son datos personales |
| `__pycache__/`, `.pytest_cache/` | Archivos temporales de Python | Se generan solos |

En producción, el equivalente de `.env` son las **variables de Railway**, y el de `uploads/` es el **volumen de
Railway**.
