"""Crea empresas y vacantes de ejemplo para probar la búsqueda de vacantes.

Ejecutar desde backend/ con el entorno virtual activo:
    python -m scripts.seed_demo

Se puede ejecutar varias veces: si la empresa de ejemplo ya existe, no la duplica.
Las empresas de ejemplo pueden iniciar sesión con la contraseña: Demo1234

Para borrar los datos de ejemplo:
    python -m scripts.seed_demo --borrar
"""
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

import app.models  # noqa: F401  (registra todas las tablas)
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.catalogs import EducationLevel, Skill
from app.models.city import City
from app.models.company import Company
from app.models.industry import Industry
from app.models.job import ContractType, Job, JobSkill
from app.models.role import Role
from app.models.user import User

DEMO_PASSWORD = "Demo1234"
DEMO_DOMAIN = "@demo.jobmatch.co"

COMPANIES = [
    {
        "name": "Soluciones Andinas S.A.S.", "tax_id": "900111222-3", "email": "talento" + DEMO_DOMAIN,
        "industry": "Tecnología", "size": "51-200", "city": "Cali",
        "description": "Empresa de software que desarrolla plataformas web y móviles para clientes de toda Latinoamérica.",
        "website": "https://solucionesandinas.example.com", "contact_name": "Mariana López",
        "jobs": [
            {"title": "Desarrollador Backend Python", "modality": "hibrido", "city": "Cali",
             "contract": "Término indefinido", "education": "Pregrado", "years": 2,
             "salary": (5_000_000, 7_000_000),
             "description": "Construirás APIs REST con FastAPI y bases de datos MySQL para nuestros productos. "
                            "Trabajarás con un equipo ágil, revisiones de código y despliegues continuos.",
             "requirements": "2 años de experiencia con Python. Conocimiento de SQL y control de versiones con Git.",
             "required": ["Python", "FastAPI", "SQL"], "desired": ["Docker", "Git"]},
            {"title": "Desarrolladora/or Frontend React", "modality": "remoto", "city": None,
             "contract": "Término indefinido", "education": "Tecnólogo", "years": 1,
             "salary": (4_000_000, 5_500_000),
             "description": "Crearás interfaces modernas y accesibles con React. Trabajo 100% remoto desde cualquier ciudad de Colombia.",
             "requirements": "Experiencia con React, JavaScript, HTML y CSS.",
             "required": ["React", "JavaScript", "CSS"], "desired": ["TypeScript"]},
            {"title": "Practicante de desarrollo de software", "modality": "presencial", "city": "Cali",
             "contract": "Prácticas", "education": None, "years": 0, "salary": (1_423_500, 1_423_500),
             "description": "Aprende desarrollando funcionalidades reales con el acompañamiento de un mentor.",
             "requirements": "Estudiante de últimos semestres de Ingeniería de Sistemas o afines.",
             "required": ["Python"], "desired": ["SQL", "Git"]},
            {"title": "Analista QA", "modality": "hibrido", "city": "Bogotá",
             "contract": "Término fijo", "education": "Tecnólogo", "years": 1, "salary": (3_000_000, 4_000_000),
             "description": "Diseñarás y ejecutarás pruebas manuales y automatizadas para asegurar la calidad del software.",
             "requirements": "Experiencia en pruebas de software y reporte de errores.",
             "required": ["Pruebas de software"], "desired": ["Selenium", "SQL"]},
        ],
    },
    {
        "name": "Logística Express del Pacífico", "tax_id": "800333444-5", "email": "rrhh" + DEMO_DOMAIN,
        "industry": "Logística y transporte", "size": "201-500", "city": "Buenaventura",
        "description": "Operador logístico con centros de distribución en el Valle del Cauca y Bogotá.",
        "website": None, "contact_name": "Jorge Ramírez",
        "jobs": [
            {"title": "Auxiliar de bodega", "modality": "presencial", "city": "Palmira",
             "contract": "Obra o labor", "education": "Bachillerato", "years": 0, "salary": (1_423_500, 1_600_000),
             "description": "Recepción, almacenamiento y despacho de mercancía en nuestro centro de distribución.",
             "requirements": "Bachiller. Disponibilidad para turnos rotativos.",
             "required": ["Manejo de inventarios"], "desired": ["Montacargas"]},
            {"title": "Coordinador logístico", "modality": "presencial", "city": "Cali",
             "contract": "Término indefinido", "education": "Pregrado", "years": 3, "salary": (4_500_000, 6_000_000),
             "description": "Liderarás la operación de despachos y el equipo de auxiliares de la sede Cali.",
             "requirements": "Profesional en logística, administración o ingeniería industrial con 3 años de experiencia.",
             "required": ["Logística", "Liderazgo de equipos"], "desired": ["Excel avanzado", "SAP"]},
            {"title": "Analista de datos logísticos", "modality": "hibrido", "city": "Bogotá",
             "contract": "Término indefinido", "education": "Pregrado", "years": 2, "salary": (4_000_000, 5_000_000),
             "description": "Analizarás indicadores de operación y construirás tableros para la toma de decisiones.",
             "requirements": "Manejo de Excel avanzado, SQL y herramientas de visualización.",
             "required": ["Excel avanzado", "SQL"], "desired": ["Power BI", "Python"]},
            {"title": "Conductor de reparto", "modality": "presencial", "city": "Cali",
             "contract": "Término fijo", "education": "Bachillerato", "years": 1, "salary": (1_800_000, 2_200_000),
             "description": "Entrega de pedidos en rutas urbanas de Cali y municipios cercanos.",
             "requirements": "Licencia de conducción C1 vigente.",
             "required": ["Licencia de conducción"], "desired": ["Atención al cliente"]},
        ],
    },
    {
        "name": "Clínica Salud Integral", "tax_id": "890555666-7", "email": "seleccion" + DEMO_DOMAIN,
        "industry": "Salud", "size": "501-1000", "city": "Medellín",
        "description": "Institución prestadora de servicios de salud con sedes en Medellín, Cali y Bogotá.",
        "website": "https://saludintegral.example.com", "contact_name": "Paula Restrepo",
        "jobs": [
            {"title": "Auxiliar administrativo", "modality": "presencial", "city": "Medellín",
             "contract": "Término indefinido", "education": "Técnico", "years": 1, "salary": (1_900_000, 2_300_000),
             "description": "Apoyo en facturación, archivo y atención a pacientes en la recepción.",
             "requirements": "Técnico en asistencia administrativa. Manejo de Excel.",
             "required": ["Atención al cliente", "Excel"], "desired": ["Facturación"]},
            {"title": "Contador(a) junior", "modality": "hibrido", "city": "Cali",
             "contract": "Término indefinido", "education": "Pregrado", "years": 1, "salary": (3_200_000, 3_800_000),
             "description": "Registro contable, conciliaciones bancarias y apoyo en cierres mensuales.",
             "requirements": "Contador público con tarjeta profesional.",
             "required": ["Contabilidad", "Excel"], "desired": ["SIIGO"]},
            {"title": "Agente de servicio al cliente (remoto)", "modality": "remoto", "city": None,
             "contract": "Obra o labor", "education": "Bachillerato", "years": 0, "salary": (1_600_000, 1_900_000),
             "description": "Atención telefónica y por chat para agendamiento de citas médicas.",
             "requirements": "Buena comunicación oral y escrita. Computador e internet estable.",
             "required": ["Atención al cliente"], "desired": ["Comunicación asertiva"]},
            {"title": "Jefe de talento humano", "modality": "presencial", "city": "Bogotá",
             "contract": "Término indefinido", "education": "Especialización", "years": 5,
             "salary": (8_000_000, 10_000_000),
             "description": "Dirigirás los procesos de selección, bienestar y desarrollo del personal de la clínica.",
             "requirements": "Psicólogo o administrador con especialización en gestión humana.",
             "required": ["Gestión humana", "Liderazgo de equipos"], "desired": ["Selección de personal"]},
        ],
    },
]


def _skill_id(db, name: str) -> int:
    skill_id = db.scalar(select(Skill.id).where(func.lower(Skill.name) == name.lower()))
    if skill_id is None:
        skill = Skill(name=name)
        db.add(skill)
        db.flush()
        skill_id = skill.id
    return skill_id


def _lookup(db, model, name: str | None) -> int | None:
    if name is None:
        return None
    found = db.scalar(select(model.id).where(model.name == name))
    if found is None:
        raise SystemExit(f"Falta '{name}' en la tabla {model.__tablename__}. Ejecuta primero el script SQL.")
    return found


def seed() -> None:
    with SessionLocal() as db:
        role_id = _lookup(db, Role, "empresa")
        created_companies = created_jobs = 0
        for data in COMPANIES:
            if db.scalar(select(Company.id).where(Company.tax_id == data["tax_id"])):
                print(f"- {data['name']}: ya existe, se omite.")
                continue

            user = User(role_id=role_id, email=data["email"], password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)
            db.flush()
            company = Company(
                user_id=user.id, name=data["name"], tax_id=data["tax_id"],
                industry_id=_lookup(db, Industry, data["industry"]), size=data["size"],
                description=data["description"], city_id=_lookup(db, City, data["city"]),
                website=data["website"], contact_name=data["contact_name"], contact_email=data["email"],
            )
            db.add(company)
            db.flush()
            created_companies += 1

            for i, j in enumerate(data["jobs"]):
                job = Job(
                    company_id=company.id, title=j["title"], description=j["description"],
                    requirements=j["requirements"], city_id=_lookup(db, City, j["city"]), modality=j["modality"],
                    contract_type_id=_lookup(db, ContractType, j["contract"]),
                    min_education_id=_lookup(db, EducationLevel, j["education"]),
                    min_experience_years=j["years"], salary_min=j["salary"][0], salary_max=j["salary"][1],
                    status="activa", is_enabled=True,
                    published_at=datetime.now() - timedelta(days=i * 2, hours=created_companies),
                    closes_at=date.today() + timedelta(days=45),
                )
                job.skills = [JobSkill(skill_id=_skill_id(db, s), is_required=True) for s in j["required"]] + [
                    JobSkill(skill_id=_skill_id(db, s), is_required=False) for s in j["desired"]
                ]
                db.add(job)
                created_jobs += 1
            print(f"+ {data['name']}: {len(data['jobs'])} vacantes.")

        db.commit()
        print(f"\nListo: {created_companies} empresas y {created_jobs} vacantes nuevas.")
        if created_companies:
            print(f"Las empresas de ejemplo entran con su correo ({DEMO_DOMAIN}) y la contraseña {DEMO_PASSWORD}")


def delete_demo() -> None:
    """Borra las empresas de ejemplo; sus vacantes, swipes y matches se borran en cascada."""
    with SessionLocal() as db:
        users = db.scalars(select(User).where(User.email.like(f"%{DEMO_DOMAIN}"))).all()
        for user in users:
            company = db.scalar(select(Company).where(Company.user_id == user.id))
            if company is not None:
                db.delete(company)
            db.delete(user)
        db.commit()
        print(f"Se borraron {len(users)} empresas de ejemplo.")


if __name__ == "__main__":
    delete_demo() if "--borrar" in sys.argv else seed()
