# Empléate Jobmatch

Plataforma de empleo que conecta aspirantes y empresas con un sistema de "me interesa / no me interesa". Cuando
las dos partes dicen que sí a la misma vacante, se crea un **match** y se comparten los datos de contacto.

**Versión beta:** https://empleate-jobmatch-frontend.vercel.app

| Documento | Contenido |
|---|---|
| [DOCUMENTACION.md](DOCUMENTACION.md) | Explicación detallada: arquitectura, módulos, flujos, base de datos, API y seguridad |
| [DESPLIEGUE.md](DESPLIEGUE.md) | Cómo publicar la aplicación en Vercel y Railway |

## Funciones principales

- **Aspirantes:** registro con lectura automática de la hoja de vida, tarjetas de vacantes, buscador con filtros,
  porcentaje de compatibilidad con razones a favor y en contra, y matches.
- **Empresas:** perfil, publicación y gestión de vacantes, revisión de candidatos y descarga de la hoja de vida
  después del match.
- **Administrador:** resumen, usuarios, vacantes, matches y bitácora de actividad.
- **IA opcional:** lectura de hojas de vida, afinidad semántica y análisis de cada pareja aspirante-vacante.
  Sin IA, la aplicación sigue funcionando con reglas.

## Tecnologías

| Parte | Tecnología |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Pydantic |
| Base de datos | MySQL |
| Frontend | HTML, CSS y JavaScript con módulos, sin framework |
| Sesiones y contraseñas | JWT y bcrypt |
| IA | OpenAI o Claude (opcional) |
| Pruebas | pytest |
| Producción | Vercel (páginas) y Railway (API, MySQL y archivos) |

## Estructura del proyecto

```text
Empleate-JobMatch/
├── README.md
├── DOCUMENTACION.md                  # Explicación detallada del programa
├── DESPLIEGUE.md                     # Guía de publicación
├── Empleate JObMatch database.sql    # Crea la base de datos, las tablas y los catálogos
│
├── backend/
│   ├── main.py                       # Punto de entrada de FastAPI
│   ├── requirements.txt              # Librerías de Python
│   ├── Dockerfile                    # Imagen que Railway construye
│   ├── .env.example                  # Plantilla de configuración, sin secretos
│   ├── app/
│   │   ├── config.py                 # Lee la configuración
│   │   ├── database.py               # Conexión con MySQL
│   │   ├── controllers/              # Rutas de la API
│   │   ├── services/                 # Reglas del negocio
│   │   │   └── ai/                   # Proveedores de IA y prompts
│   │   ├── models/                   # Tablas de la base de datos
│   │   ├── schemas/                  # Validación de datos que entran y salen
│   │   ├── core/                     # Seguridad, permisos y errores
│   │   ├── data/                     # Catálogo de habilidades
│   │   └── utils/                    # Validadores y utilidades
│   ├── scripts/                      # Tareas manuales: administrador, migraciones y datos de ejemplo
│   └── tests/                        # Pruebas automáticas
│
└── frontend/
    ├── index.html                    # Página de inicio
    ├── vercel.json                   # Reenvía /api a Railway en producción
    ├── pages/                        # auth, applicant, company, admin y legal
    └── assets/
        ├── css/                      # Estilos
        └── js/
            ├── config.js             # Dirección de la API
            ├── api/                  # Llamadas al backend
            ├── controllers/          # Lógica de cada pantalla
            ├── components/           # Piezas reutilizables
            └── utils/                # Sesión, tema, formatos y validaciones
```

Estas carpetas existen solo en tu computador y no se suben a GitHub: `backend/venv/` (librerías instaladas),
`backend/.env` (configuración y secretos) y `backend/uploads/` (archivos subidos).

## Puesta en marcha local

Necesitas Python y MySQL instalados. Tu copia local usa su propia base de datos: no toca producción.

1. Crea la base de datos ejecutando `Empleate JObMatch database.sql` en MySQL Workbench.
2. Copia `backend/.env.example` como `backend/.env`, y llena `DB_USER`, `DB_PASSWORD` y `JWT_SECRET`.
3. Desde `backend/`, crea el entorno virtual e instala las librerías:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Carga las habilidades y crea el administrador, que pedirá una contraseña:

   ```powershell
   python -m scripts.migrate_skills_catalog
   python -m scripts.create_admin admin@tucorreo.com
   ```

5. Opcional: crea empresas y vacantes de ejemplo. Usan la contraseña conocida `Demo1234`, así que no lo ejecutes
   en producción. Se borran con `python -m scripts.seed_demo --borrar`.

   ```powershell
   python -m scripts.seed_demo
   ```

6. Arranca el servidor:

   ```powershell
   uvicorn main:app --reload
   ```

7. Abre **http://127.0.0.1:8000**. El mismo backend sirve la API en `/api/...` y las páginas de `frontend/`.
   La documentación interactiva de la API está en http://127.0.0.1:8000/docs.

No abras los `.html` con doble clic: el navegador bloquea los módulos de JavaScript en `file://`.

Si tu base de datos es anterior a las columnas de caché de la IA, ejecuta una vez
`python -m scripts.migrate_ai_matching`. Una base nueva ya las incluye.

## Pruebas

Desde `backend/`, con el entorno virtual activo:

```powershell
python -m pytest
```

Las pruebas usan SQLite en memoria y una carpeta temporal, así que no tocan MySQL ni llaman a servicios externos.

## Activar la IA

Agrega esto a `backend/.env`, o a las variables de Railway en producción, y reinicia el backend:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=tu_clave
```

También se admite `AI_PROVIDER=claude` con `ANTHROPIC_API_KEY`, pero la afinidad semántica solo funciona con OpenAI.
Si la IA falla o no tiene saldo, la aplicación sigue funcionando con reglas.

**Qué recibe el proveedor de IA:** para leer una hoja de vida se envía su texto, que puede incluir nombre y datos
de contacto. Para el emparejamiento solo se envía el perfil profesional, sin nombre, correo ni teléfono.

## Desarrollo y publicación

Guardar archivos o hacer `commit` no cambia la aplicación publicada. Producción se actualiza cuando el código llega
a la rama `main` de GitHub. Los cambios en tablas y variables de entorno no se aplican solos: consulta
[Pasar cambios a producción](DOCUMENTACION.md#12-pasar-cambios-a-producción).

## Limitaciones actuales

- La recuperación de contraseña en producción no envía correos: el enlace aparece en los logs de Railway.
- Los términos y la política de datos todavía tienen campos sin completar.

La lista completa está en [Limitaciones conocidas](DOCUMENTACION.md#13-limitaciones-conocidas).
