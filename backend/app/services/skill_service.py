"""Catálogo de habilidades y herramientas.

- Las curadas (is_curated = 1) vienen de app/data/skills_catalog.py y se sugieren en los formularios.
- Las que escriben aspirantes y empresas también se guardan (el catálogo crece), pero solo se
  sugieren si alguien más ya las usa.
"""
import re
from functools import lru_cache

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.data.skills_catalog import ALIASES, CATALOG
from app.models.applicant_profile import ApplicantSkill
from app.models.catalogs import Skill
from app.models.job import JobSkill
from app.utils.helpers import normalize_text


# =====================================================================
# Nombres canónicos (sin base de datos)
# =====================================================================
@lru_cache(maxsize=1)
def _canonical_map() -> dict[str, tuple[str, str]]:
    """'python' -> ('Python', 'tecnica'), incluidos los alias ('js' -> 'JavaScript')."""
    by_key = {normalize_text(name): (name, category) for name, category in CATALOG}
    for alias, target in ALIASES.items():
        by_key.setdefault(normalize_text(alias), by_key[normalize_text(target)])
    return by_key


def canonical_skill(name: str) -> tuple[str, str | None]:
    """Devuelve el nombre como aparece en el catálogo (y su categoría), o el nombre limpio si no está."""
    clean = re.sub(r"\s+", " ", name).strip(" .,;:-–•·*")
    found = _canonical_map().get(normalize_text(clean))
    if found:
        return found
    # "comunicacion" -> "Comunicacion": al menos que empiece en mayúscula
    if clean and clean == clean.lower():
        clean = clean[0].upper() + clean[1:]
    return clean, None


def catalog_terms() -> list[tuple[str, str]]:
    """Pares (texto normalizado a buscar, nombre canónico) para reconocer habilidades en un texto.
    Se omiten nombres de 1-2 letras ("C", "R", "Go"): darían falsos positivos en texto libre."""
    terms = []
    for key, (name, _category) in _canonical_map().items():
        if len(key) >= 3 or any(ch in key for ch in "+#."):
            terms.append((key, name))
    return sorted(terms, key=lambda t: -len(t[0]))  # primero las más largas ("excel avanzado" antes que "excel")


# =====================================================================
# Base de datos
# =====================================================================
def get_or_create_skill_id(db: Session, name: str) -> int:
    """Reutiliza la habilidad si ya existe ('python' = 'Python'); si es del catálogo, usa su nombre oficial."""
    canonical, category = canonical_skill(name)
    skill_id = db.scalar(select(Skill.id).where(func.lower(Skill.name) == canonical.lower()))
    if skill_id is None:
        skill = Skill(name=canonical[:100], category=category, is_curated=category is not None)
        db.add(skill)
        db.flush()
        skill_id = skill.id
    return skill_id


def seed_curated_skills(db: Session) -> tuple[int, int]:
    """Carga el catálogo curado. Si la habilidad ya existía (escrita por un usuario), la marca como curada."""
    # Sin tildes ni mayúsculas, igual que compara MySQL (utf8mb4_unicode_ci): "comunicacion" = "Comunicación"
    existing = {normalize_text(s.name): s for s in db.scalars(select(Skill))}
    created = updated = 0
    for name, category in CATALOG:
        skill = existing.get(normalize_text(name))
        if skill is None:
            db.add(Skill(name=name, category=category, is_curated=True))
            created += 1
        elif skill.category != category or not skill.is_curated or skill.name != name:
            skill.name, skill.category, skill.is_curated = name, category, True
            updated += 1
    db.flush()
    return created, updated


def suggest_skills(db: Session, q: str, limit: int = 8) -> list[dict]:
    """Sugerencias para autocompletar: primero las que empiezan por lo escrito y las del catálogo curado."""
    q = q.strip()
    if not q:
        return []
    used = or_(
        select(JobSkill.skill_id).where(JobSkill.skill_id == Skill.id).exists(),
        select(ApplicantSkill.skill_id).where(ApplicantSkill.skill_id == Skill.id).exists(),
    )
    lowered = func.lower(Skill.name)
    starts = lowered.startswith(q.lower(), autoescape=True)
    rows = db.execute(
        select(Skill.id, Skill.name, Skill.category)
        .where(lowered.contains(q.lower(), autoescape=True), or_(Skill.is_curated.is_(True), used))
        .order_by(case((starts, 0), else_=1), Skill.is_curated.desc(), func.length(Skill.name), Skill.name)
        .limit(limit)
    ).all()
    results = [{"id": r.id, "name": r.name, "category": r.category} for r in rows]

    # Sin tildes también encuentra: "comunicacion" -> "Comunicación"
    if len(results) < limit:
        key = normalize_text(q)
        seen = {r["id"] for r in results}
        for name, category in CATALOG:
            if len(results) >= limit:
                break
            if key in normalize_text(name):
                skill_id = db.scalar(select(Skill.id).where(func.lower(Skill.name) == name.lower()))
                if skill_id is not None and skill_id not in seen:
                    results.append({"id": skill_id, "name": name, "category": category})
                    seen.add(skill_id)
    return results
