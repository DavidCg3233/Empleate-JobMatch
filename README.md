jobmatch/
│
├── .gitignore
├── README.md
├── .vscode/
│   ├── settings.json
│   └── extensions.json
│
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── main.py                     # Punto de entrada FastAPI
│   │
│   ├── app/
│   │   ├── config.py               # Carga de variables .env
│   │   ├── database.py             # Conexión MySQL + sesión SQLAlchemy
│   │   │
│   │   ├── models/                 # MODELO (tablas)
│   │   │   ├── user.py             # Usuario base (correo, rol, intentos, bloqueo)
│   │   │   ├── applicant.py        # Perfil aspirante
│   │   │   ├── company.py          # Perfil empresa
│   │   │   ├── job.py              # Vacantes
│   │   │   ├── swipe.py            # Likes/dislikes de ambos lados
│   │   │   ├── match.py            # Matches
│   │   │   ├── match_score.py      # Cache de scores de IA
│   │   │   └── password_reset.py   # Tokens de recuperación
│   │   │
│   │   ├── schemas/                # MODELO (validación entrada/salida)
│   │   │   ├── auth_schema.py
│   │   │   ├── applicant_schema.py
│   │   │   ├── company_schema.py
│   │   │   ├── job_schema.py
│   │   │   ├── swipe_schema.py
│   │   │   └── admin_schema.py
│   │   │
│   │   ├── controllers/            # CONTROLADOR (endpoints)
│   │   │   ├── auth_controller.py
│   │   │   ├── applicant_controller.py
│   │   │   ├── company_controller.py
│   │   │   ├── job_controller.py
│   │   │   ├── swipe_controller.py
│   │   │   ├── match_controller.py
│   │   │   └── admin_controller.py
│   │   │
│   │   ├── services/               # Lógica de negocio
│   │   │   ├── auth_service.py     # Login, límite de 3 intentos, bloqueo
│   │   │   ├── email_service.py    # Recuperación de contraseña
│   │   │   ├── cv_parser_service.py# Extrae texto de PDF/DOCX
│   │   │   ├── matching_service.py # Filtros + embeddings + score
│   │   │   ├── storage_service.py  # Local hoy, Cloudinary mañana
│   │   │   └── ai/
│   │   │       ├── base.py         # Interfaz común de proveedor IA
│   │   │       ├── claude_provider.py
│   │   │       ├── openai_provider.py
│   │   │       └── prompts.py      # Prompts de CV y match
│   │   │
│   │   ├── core/
│   │   │   ├── security.py         # JWT + bcrypt
│   │   │   ├── dependencies.py     # Protección de rutas por rol
│   │   │   └── exceptions.py
│   │   │
│   │   └── utils/
│   │       ├── file_validators.py  # Tipo y tamaño de archivos
│   │       └── helpers.py
│   │
│   ├── migrations/                 # Alembic
│   │   └── versions/
│   ├── uploads/                    # CVs y logos (solo en local)
│   │   ├── cvs/
│   │   └── logos/
│   └── tests/
│       ├── test_auth.py
│       ├── test_matching.py
│       └── test_cv_parser.py
│
└── frontend/                       # VISTA
    ├── index.html                  # Landing
    │
    ├── pages/
    │   ├── auth/
    │   │   ├── login.html
    │   │   ├── register.html       # Elegir rol
    │   │   ├── forgot-password.html
    │   │   └── reset-password.html
    │   ├── applicant/
    │   │   ├── onboarding.html     # Subir CV + autocompletar
    │   │   ├── swipe.html          # Pantalla tipo Tinder
    │   │   ├── profile.html        # Perfil + estado de búsqueda
    │   │   ├── matches.html
    │   │   └── search.html         # Buscador y filtros
    │   ├── company/
    │   │   ├── profile.html
    │   │   ├── jobs.html           # CRUD de vacantes
    │   │   ├── job-form.html
    │   │   ├── swipe.html          # Perfiles de aspirantes
    │   │   └── matches.html
    │   └── admin/
    │       ├── dashboard.html
    │       ├── users.html
    │       ├── jobs.html
    │       └── matches.html
    │
    ├── assets/
    │   ├── css/
    │   │   ├── main.css
    │   │   ├── swipe.css
    │   │   └── admin.css
    │   ├── js/
    │   │   ├── config.js           # URL base de la API
    │   │   ├── api/                # Llamadas al backend (fetch)
    │   │   │   ├── http.js         # Cliente base con token JWT
    │   │   │   ├── authApi.js
    │   │   │   ├── applicantApi.js
    │   │   │   ├── companyApi.js
    │   │   │   ├── jobApi.js
    │   │   │   ├── swipeApi.js
    │   │   │   └── adminApi.js
    │   │   ├── controllers/        # Lógica de cada pantalla
    │   │   │   ├── loginController.js
    │   │   │   ├── registerController.js
    │   │   │   ├── applicantSwipeController.js
    │   │   │   ├── companySwipeController.js
    │   │   │   ├── jobsController.js
    │   │   │   └── adminController.js
    │   │   ├── components/         # Piezas reutilizables
    │   │   │   ├── swipeCard.js
    │   │   │   ├── navbar.js
    │   │   │   ├── toast.js
    │   │   │   └── filters.js
    │   │   └── utils/
    │   │       ├── auth.js         # Guardar token, guardia de rutas por rol
    │   │       └── validators.js
    │   └── img/
    └── lib/                        # Librerías locales (opcional)


    
## Puesta en marcha (desarrollo)

Desde `backend/`, con el entorno virtual activo:

```powershell
pip install -r requirements.txt
python -m scripts.migrate_skills_catalog   # columnas del catálogo de habilidades + 255 habilidades y herramientas
python -m scripts.seed_demo                # opcional: 3 empresas y 12 vacantes de ejemplo (clave Demo1234)
uvicorn main:app --reload
```

Luego abre **http://127.0.0.1:8000** en cualquier navegador: el mismo backend sirve la API (`/api/...`)
y las páginas de `frontend/`. No hace falta Live Server (si lo prefieres, también funciona en
`http://127.0.0.1:5500/frontend/index.html`). No abras los `.html` con doble clic: el navegador bloquea los
módulos de JavaScript en `file://`.

Las pruebas se ejecutan con `python -m pytest`.

`migrate_skills_catalog` se puede ejecutar varias veces sin duplicar nada; quien ya tenga la base creada
debe ejecutarlo una vez para tener las sugerencias de habilidades.
