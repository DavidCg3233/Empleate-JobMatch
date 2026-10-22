"""Emparejamiento con IA. Se suma al cálculo por reglas (matching_service), nunca lo reemplaza.

Capa 1 - Afinidad semántica (embeddings):
    El perfil y la vacante se convierten en vectores de significado y se compara qué tan parecidos son
    (encuentra afinidad aunque usen palabras distintas: "programador" ~ "desarrollador de software").
    Los vectores se guardan en applicant_embeddings / job_embeddings y solo se recalculan si el texto cambia.

Capa 2 - Análisis de la pareja (modelo de lenguaje, bajo demanda):
    Al abrir el detalle, la IA explica por qué encajan, qué falta, y da un consejo al aspirante o preguntas
    de entrevista a la empresa. Se guarda en match_scores (no se paga dos veces por lo mismo).

Privacidad: a la IA solo se le envía el perfil PROFESIONAL (cargo, resumen, habilidades, experiencia, estudios,
idiomas, ciudad). Nunca el nombre, correo, teléfono ni el archivo de la hoja de vida.

Si la IA no está configurada o falla, todo sigue funcionando con las reglas.
"""
import hashlib
import json
import logging
import math
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.applicant import Applicant
from app.models.applicant_profile import ApplicantEducation, ApplicantExperience, ApplicantLanguage, ApplicantSkill
from app.models.catalogs import EducationLevel, Language, Skill
from app.models.city import City
from app.models.job import Job
from app.models.match_score import ApplicantEmbedding, JobEmbedding, MatchScore
from app.services.ai.base import AIError, AIProvider, get_ai_provider
from app.services.ai.prompts import build_match_analysis_prompt

logger = logging.getLogger("empleate.ai_matching")

MAX_TEXT = 4000            # caracteres por texto enviado a embeddings
EMBED_BATCH = 100          # textos por llamada a la API
PAUSE_AFTER_ERROR = 300    # si la IA falla, se deja de intentar durante 5 minutos
MODALITY = {"presencial": "presencial", "remoto": "remoto", "hibrido": "híbrido"}
LEVEL_LABEL = {"basico": "básico", "intermedio": "intermedio", "avanzado": "avanzado", "nativo": "nativo"}

_paused_until = {"embeddings": 0.0, "analysis": 0.0}


# =====================================================================
# Disponibilidad
# =====================================================================
def _provider() -> AIProvider | None:
    return get_ai_provider() if settings.AI_MATCHING_ENABLED else None


def _available(feature: str) -> bool:
    return time.monotonic() >= _paused_until[feature]


def _pause(feature: str, exc: Exception) -> None:
    _paused_until[feature] = time.monotonic() + PAUSE_AFTER_ERROR
    logger.warning("IA (%s) en pausa %s s por un error: %s", feature, PAUSE_AFTER_ERROR, exc)


def status() -> dict:
    provider = _provider()
    return {
        "provider": provider.name if provider else None,
        "semantic": bool(provider and provider.supports_embeddings),
        "analysis": provider is not None,
    }


def _hash(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# =====================================================================
# Textos que se comparan (solo información profesional)
# =====================================================================
def applicant_texts(db: Session, applicants: list[Applicant]) -> dict[int, str]:
    ids = [a.id for a in applicants]
    if not ids:
        return {}
    skills: dict[int, list[str]] = {i: [] for i in ids}
    for aid, name in db.execute(
        select(ApplicantSkill.applicant_id, Skill.name).join(Skill, Skill.id == ApplicantSkill.skill_id)
        .where(ApplicantSkill.applicant_id.in_(ids)).order_by(Skill.name)
    ):
        skills[aid].append(name)
    experiences: dict[int, list[str]] = {i: [] for i in ids}
    for exp in db.scalars(
        select(ApplicantExperience).where(ApplicantExperience.applicant_id.in_(ids))
        .order_by(ApplicantExperience.start_date.desc())
    ):
        period = f"{exp.start_date.year}-{'actual' if exp.is_current else (exp.end_date.year if exp.end_date else '')}"
        line = f"{exp.position} en {exp.company_name} ({period})"
        if exp.description:
            line += f": {exp.description[:300]}"
        experiences[exp.applicant_id].append(line)
    educations: dict[int, list[str]] = {i: [] for i in ids}
    for edu, level in db.execute(
        select(ApplicantEducation, EducationLevel.name)
        .join(EducationLevel, EducationLevel.id == ApplicantEducation.education_level_id)
        .where(ApplicantEducation.applicant_id.in_(ids))
    ):
        educations[edu.applicant_id].append(f"{level}: {edu.degree} - {edu.institution}")
    languages: dict[int, list[str]] = {i: [] for i in ids}
    for aid, name, level in db.execute(
        select(ApplicantLanguage.applicant_id, Language.name, ApplicantLanguage.proficiency)
        .join(Language, Language.id == ApplicantLanguage.language_id).where(ApplicantLanguage.applicant_id.in_(ids))
    ):
        languages[aid].append(f"{name} ({LEVEL_LABEL.get(level, level)})")
    cities = dict(db.execute(select(City.id, City.name)).all())

    texts = {}
    for a in applicants:
        parts = [
            f"Cargo que busca: {a.desired_position}" if a.desired_position else "",
            f"Resumen: {a.summary}" if a.summary else "",
            f"Habilidades: {', '.join(skills[a.id])}" if skills[a.id] else "",
            f"Experiencia: {'; '.join(experiences[a.id])}" if experiences[a.id] else "Experiencia: sin experiencia registrada",
            f"Educación: {'; '.join(educations[a.id])}" if educations[a.id] else "",
            f"Idiomas: {', '.join(languages[a.id])}" if languages[a.id] else "",
            f"Ciudad: {cities.get(a.city_id)}" if a.city_id else "",
            f"Modalidad preferida: {MODALITY[a.desired_modality]}" if a.desired_modality else "",
        ]
        texts[a.id] = "\n".join(p for p in parts if p)[:MAX_TEXT]
    return texts


def job_text(job: Job, city_name: str | None = None) -> str:
    required = [js.skill.name for js in job.skills if js.is_required]
    desired = [js.skill.name for js in job.skills if not js.is_required]
    parts = [
        f"Cargo: {job.title}",
        f"Descripción: {job.description}",
        f"Requisitos: {job.requirements}" if job.requirements else "",
        f"Habilidades requeridas: {', '.join(required)}" if required else "",
        f"Habilidades deseables: {', '.join(desired)}" if desired else "",
        f"Experiencia mínima: {job.min_experience_years or 0} años",
        f"Educación mínima: {job.min_education.name}" if job.min_education else "",
        f"Modalidad: {MODALITY[job.modality]}" + (f" en {city_name}" if city_name else ""),
        f"Contrato: {job.contract_type.name}",
    ]
    return "\n".join(p for p in parts if p)[:MAX_TEXT]


def _job_texts(db: Session, jobs: list[Job]) -> dict[int, str]:
    cities = dict(db.execute(select(City.id, City.name)).all())
    return {job.id: job_text(job, cities.get(job.city_id)) for job in jobs}


# =====================================================================
# Capa 1: vectores con caché y afinidad semántica
# =====================================================================
def _vectors(db: Session, model_cls, key: str, texts: dict[int, str], provider: AIProvider) -> dict[int, list[float]]:
    """Vectores de cada texto: los guardados si el texto no cambió; los demás se piden a la IA y se guardan."""
    if not texts:
        return {}
    model = provider.embedding_model
    hashes = {item_id: _hash(model, text) for item_id, text in texts.items()}
    rows = {getattr(r, key): r for r in db.scalars(select(model_cls).where(getattr(model_cls, key).in_(list(texts))))}
    result = {
        item_id: row.vector for item_id, row in rows.items()
        if row.model == model and row.content_hash == hashes[item_id] and row.vector
    }
    missing = [item_id for item_id in texts if item_id not in result]
    if not missing:
        return result

    for start in range(0, len(missing), EMBED_BATCH):
        chunk = missing[start : start + EMBED_BATCH]
        vectors = provider.embed([texts[i] for i in chunk])  # puede lanzar AIError
        for item_id, vector in zip(chunk, vectors):
            result[item_id] = vector
            row = rows.get(item_id)
            if row is None:
                db.add(model_cls(**{key: item_id}, model=model, vector=vector, content_hash=hashes[item_id]))
            else:
                row.model, row.vector, row.content_hash = model, vector, hashes[item_id]

    # Se guarda sin "expirar" los objetos ya cargados en la petición (evita volver a consultarlos)
    db.expire_on_commit = False
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # otra petición guardó el mismo vector al tiempo: no pasa nada
    finally:
        db.expire_on_commit = True
    return result


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def semantic_for_applicant(db: Session, applicant: Applicant, jobs: list[Job]) -> dict[int, float]:
    """Similitud (coseno) entre el perfil y cada vacante. {} si la IA no está disponible."""
    provider = _provider()
    if not jobs or not provider or not provider.supports_embeddings or not _available("embeddings"):
        return {}
    try:
        mine = _vectors(db, ApplicantEmbedding, "applicant_id", applicant_texts(db, [applicant]), provider)
        theirs = _vectors(db, JobEmbedding, "job_id", _job_texts(db, jobs), provider)
    except AIError as exc:
        _pause("embeddings", exc)
        return {}
    vector = mine.get(applicant.id)
    return {job_id: _cosine(vector, v) for job_id, v in theirs.items()} if vector else {}


def semantic_for_job(db: Session, job: Job, applicants: list[Applicant]) -> dict[int, float]:
    """Similitud (coseno) entre la vacante y cada aspirante. {} si la IA no está disponible."""
    provider = _provider()
    if not applicants or not provider or not provider.supports_embeddings or not _available("embeddings"):
        return {}
    try:
        theirs = _vectors(db, JobEmbedding, "job_id", _job_texts(db, [job]), provider)
        people = _vectors(db, ApplicantEmbedding, "applicant_id", applicant_texts(db, applicants), provider)
    except AIError as exc:
        _pause("embeddings", exc)
        return {}
    vector = theirs.get(job.id)
    return {aid: _cosine(vector, v) for aid, v in people.items()} if vector else {}


# =====================================================================
# Capa 2: análisis de la pareja (bajo demanda, con caché)
# =====================================================================
class AnalysisUnavailable(Exception):
    """No hay IA configurada o está en pausa por errores."""


def _clean_text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _clean_list(value, limit: int = 3, length: int = 180) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_clean_text(v, length) for v in value if isinstance(v, (str, int, float))]
    return [i for i in items if i][:limit]


def _validate_analysis(raw: dict) -> dict:
    """La respuesta de la IA se valida campo por campo antes de guardarla o mostrarla."""
    try:
        score = max(0, min(100, int(round(float(raw.get("score")))))) if raw.get("score") is not None else None
    except (TypeError, ValueError):
        score = None
    aspirante = raw.get("aspirante") if isinstance(raw.get("aspirante"), dict) else {}
    empresa = raw.get("empresa") if isinstance(raw.get("empresa"), dict) else {}
    result = {
        "score": score,
        "aspirante": {
            "resumen": _clean_text(aspirante.get("resumen"), 500),
            "fortalezas": _clean_list(aspirante.get("fortalezas")),
            "brechas": _clean_list(aspirante.get("brechas")),
            "consejo": _clean_text(aspirante.get("consejo"), 350),
        },
        "empresa": {
            "resumen": _clean_text(empresa.get("resumen"), 500),
            "fortalezas": _clean_list(empresa.get("fortalezas")),
            "brechas": _clean_list(empresa.get("brechas")),
            "preguntas": _clean_list(empresa.get("preguntas"), length=220),
        },
    }
    if score is None or not result["aspirante"]["resumen"] or not result["empresa"]["resumen"]:
        raise AIError("La IA devolvió un análisis incompleto.")
    return result


def _present(analysis: dict, audience: str, row: MatchScore, cached: bool) -> dict:
    part = analysis["aspirante" if audience == "aspirante" else "empresa"]
    return {
        "score": analysis["score"],
        "summary": part["resumen"],
        "strengths": part["fortalezas"],
        "gaps": part["brechas"],
        "advice": part.get("consejo") or None,
        "interview_questions": part.get("preguntas", []),
        "model": row.model_used,
        "generated_at": row.calculated_at,
        "cached": cached,
    }


def analyze_pair(db: Session, applicant: Applicant, job: Job, audience: str) -> dict:
    """Análisis de la IA para una pareja aspirante-vacante (desde el punto de vista de quien lo pide).
    Lanza AnalysisUnavailable si no hay IA, o AIError si la IA falla."""
    provider = _provider()
    if provider is None or not _available("analysis"):
        raise AnalysisUnavailable()

    applicant_text = applicant_texts(db, [applicant])[applicant.id]
    the_job_text = _job_texts(db, [job])[job.id]
    content_hash = _hash(provider.name, provider.model, applicant_text, the_job_text)

    row = db.scalar(select(MatchScore).where(MatchScore.applicant_id == applicant.id, MatchScore.job_id == job.id))
    if row is not None and row.content_hash == content_hash and row.explanation:
        try:
            return _present(json.loads(row.explanation), audience, row, cached=True)
        except (ValueError, KeyError):
            pass  # caché dañada: se vuelve a calcular

    system, user = build_match_analysis_prompt(applicant_text, the_job_text)
    try:
        analysis = _validate_analysis(provider.complete_json(system, user, max_tokens=1500))
    except AIError as exc:
        _pause("analysis", exc)
        raise

    semantic = None
    if provider.supports_embeddings:
        sims = semantic_for_job(db, job, [applicant])
        semantic = round(sims[applicant.id], 4) if applicant.id in sims else None

    if row is None:
        row = MatchScore(applicant_id=applicant.id, job_id=job.id)
        db.add(row)
    row.score = analysis["score"]
    row.explanation = json.dumps(analysis, ensure_ascii=False)
    row.model_used = f"{provider.name}:{provider.model}"[:80]
    row.content_hash = content_hash
    row.semantic_similarity = semantic
    row.calculated_at = datetime.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # otra petición guardó el mismo análisis al tiempo
        row = db.scalar(select(MatchScore).where(MatchScore.applicant_id == applicant.id, MatchScore.job_id == job.id))
    return _present(analysis, audience, row, cached=False)


def reset_pauses() -> None:
    """Solo para pruebas: quita las pausas por error."""
    for key in _paused_until:
        _paused_until[key] = 0.0
