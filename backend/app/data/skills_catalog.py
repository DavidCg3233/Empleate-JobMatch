"""Catálogo curado de habilidades y herramientas.

Sirve para:
  - sugerir y autocompletar habilidades en los formularios (empresa y aspirante),
  - reconocer habilidades al leer una hoja de vida,
  - escribir cada habilidad siempre igual ("python" -> "Python", "comunicacion" -> "Comunicación").

Categorías:
  tecnica      conocimientos de un oficio o profesión
  herramienta  programas, plataformas, equipos o licencias
  blanda       habilidades personales y sociales

Para agregar más, súmalas aquí y ejecuta:  python -m scripts.migrate_skills_catalog
"""

TECNICAS = [
    # Tecnología: lenguajes y desarrollo
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "PHP", "Ruby", "Go", "Kotlin", "Swift", "Dart",
    "R", "SQL", "HTML", "CSS", "Bash", "PowerShell",
    "Desarrollo web", "Desarrollo backend", "Desarrollo frontend", "Desarrollo móvil", "APIs REST",
    "Programación orientada a objetos", "Estructuras de datos", "Pruebas de software", "Pruebas automatizadas",
    "Control de calidad (QA)", "Análisis de requerimientos", "Arquitectura de software", "Bases de datos",
    "Modelado de datos", "Análisis de datos", "Ciencia de datos", "Machine Learning", "Inteligencia artificial",
    "Ingeniería de prompts", "Ciberseguridad", "Redes", "Soporte técnico", "Administración de servidores",
    "Computación en la nube", "DevOps", "Integración continua", "Diseño UX/UI", "Diseño gráfico",
    "Marketing digital", "SEO", "Gestión de redes sociales", "Fotografía", "Edición de video",
    # Administración, finanzas y comercio
    "Contabilidad", "Facturación", "Facturación electrónica", "Nómina", "Tesorería", "Auditoría",
    "Presupuestos", "Análisis financiero", "Costos", "Impuestos", "Conciliaciones bancarias", "Cartera",
    "Cobranza", "Compras", "Negociación con proveedores", "Ventas", "Ventas consultivas", "Telemercadeo",
    "Atención al cliente", "Servicio al cliente", "Manejo de caja", "Gestión documental", "Archivo",
    "Asistencia administrativa", "Recepción", "Gestión de proyectos", "Metodologías ágiles", "Scrum",
    "Gestión del talento humano", "Selección de personal", "Seguridad y salud en el trabajo (SST)",
    "Gestión de calidad", "Normas ISO", "Planeación estratégica", "Inglés", "Redacción",
    # Logística, industria y oficios
    "Logística", "Manejo de inventarios", "Almacenamiento", "Despachos", "Cadena de suministro",
    "Comercio exterior", "Transporte de carga", "Producción", "Mantenimiento industrial",
    "Mantenimiento preventivo", "Electricidad", "Electrónica", "Mecánica automotriz", "Soldadura",
    "Construcción", "Lectura de planos", "Topografía", "Operación de maquinaria", "Empaque",
    "Control de procesos", "Seguridad industrial", "Manipulación de alimentos", "Cocina", "Panadería",
    "Bartender", "Mesero", "Aseo y limpieza", "Vigilancia y seguridad", "Conducción",
    # Salud y educación
    "Enfermería", "Primeros auxilios", "Atención al paciente", "Facturación en salud", "Auxiliar de farmacia",
    "Docencia", "Pedagogía", "Atención a la primera infancia", "Psicología", "Trabajo social",
    # Agro
    "Agricultura", "Ganadería", "Riego",
]

HERRAMIENTAS = [
    # Desarrollo y datos
    "Git", "GitHub", "GitLab", "Docker", "Kubernetes", "Linux", "Windows Server", "AWS", "Azure",
    "Google Cloud", "MySQL", "PostgreSQL", "SQL Server", "Oracle", "MongoDB", "SQLite", "Redis", "Firebase",
    "Django", "Flask", "FastAPI", "Node.js", "Express", "React", "Angular", "Vue.js", "Next.js", "Bootstrap",
    "Tailwind CSS", "jQuery", "Spring Boot", "Laravel", ".NET", "Flutter", "React Native", "Android Studio",
    "Gradle", "Maven", "Pandas", "NumPy", "TensorFlow", "Power BI", "Tableau", "Looker Studio", "Chart.js",
    "Postman", "Jira", "Trello", "Confluence", "Figma", "Selenium", "Visual Studio Code", "Jupyter",
    "WordPress", "Shopify", "Cisco", "Wireshark",
    # Ofimática y negocio
    "Microsoft Office", "Excel", "Excel avanzado", "Word", "PowerPoint", "Outlook", "Microsoft Teams",
    "Google Workspace", "Google Sheets", "SAP", "SIIGO", "World Office", "Helisa", "Alegra", "Odoo",
    "Salesforce", "HubSpot", "Zendesk", "Canva", "Adobe Photoshop", "Adobe Illustrator", "Adobe Premiere",
    "AutoCAD", "SolidWorks", "Revit", "SketchUp", "ChatGPT",
    # Equipos y licencias
    "Montacargas", "Licencia de conducción B1", "Licencia de conducción C1", "Licencia de conducción C2",
    "Moto propia", "Vehículo propio", "Datáfono", "Caja registradora", "Escáner de inventario",
]

BLANDAS = [
    "Comunicación", "Comunicación asertiva", "Trabajo en equipo", "Liderazgo", "Responsabilidad",
    "Compromiso", "Organización", "Planificación", "Gestión del tiempo", "Resolución de problemas",
    "Pensamiento crítico", "Pensamiento analítico", "Creatividad", "Adaptabilidad", "Proactividad",
    "Iniciativa", "Orientación al logro", "Orientación al cliente", "Empatía", "Negociación",
    "Trabajo bajo presión", "Atención al detalle", "Toma de decisiones", "Aprendizaje continuo",
    "Autonomía", "Puntualidad", "Honestidad", "Tolerancia a la frustración", "Inteligencia emocional",
    "Escucha activa", "Manejo de conflictos", "Disciplina",
]

CATALOG: list[tuple[str, str]] = (
    [(name, "tecnica") for name in TECNICAS]
    + [(name, "herramienta") for name in HERRAMIENTAS]
    + [(name, "blanda") for name in BLANDAS]
)

# Formas alternativas que se escriben en las hojas de vida -> nombre del catálogo
ALIASES = {
    "js": "JavaScript", "javascript": "JavaScript", "node": "Node.js", "nodejs": "Node.js", "node js": "Node.js",
    "reactjs": "React", "react.js": "React", "vue": "Vue.js", "vuejs": "Vue.js", "nextjs": "Next.js",
    "postgres": "PostgreSQL", "sql server": "SQL Server", "mssql": "SQL Server", "mongo": "MongoDB",
    "html5": "HTML", "css3": "CSS", "c sharp": "C#", "golang": "Go", "ms office": "Microsoft Office",
    "office": "Microsoft Office", "paquete office": "Microsoft Office", "microsoft excel": "Excel",
    "excel intermedio": "Excel", "microsoft word": "Word", "power point": "PowerPoint", "powerbi": "Power BI",
    "photoshop": "Adobe Photoshop", "illustrator": "Adobe Illustrator", "premiere": "Adobe Premiere",
    "vscode": "Visual Studio Code", "vs code": "Visual Studio Code", "gcp": "Google Cloud",
    "amazon web services": "AWS", "ia": "Inteligencia artificial", "ai": "Inteligencia artificial",
    "herramientas ia": "Inteligencia artificial", "ml": "Machine Learning", "qa": "Control de calidad (QA)",
    "control de calidad": "Control de calidad (QA)", "sst": "Seguridad y salud en el trabajo (SST)",
    "servicio al cliente": "Servicio al cliente", "manejo de presion": "Trabajo bajo presión",
    "trabajo bajo presion": "Trabajo bajo presión", "adaptabilidad al trabajo bajo presion": "Trabajo bajo presión",
    "redes cisco": "Cisco", "fundamentos de linux": "Linux", "optimizacion de prompts": "Ingeniería de prompts",
    "prompt engineering": "Ingeniería de prompts", "rest": "APIs REST", "api rest": "APIs REST", "apis": "APIs REST",
    "poo": "Programación orientada a objetos", "scrum master": "Scrum", "agile": "Metodologías ágiles",
    "inventarios": "Manejo de inventarios", "atencion a clientes": "Atención al cliente",
    "licencia c1": "Licencia de conducción C1", "licencia c2": "Licencia de conducción C2",
    "licencia b1": "Licencia de conducción B1", "teamwork": "Trabajo en equipo", "leadership": "Liderazgo",
}
