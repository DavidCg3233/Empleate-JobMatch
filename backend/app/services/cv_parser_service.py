"""Lectura de hojas de vida (PDF / DOCX).

1. extract_text(): saca el texto del archivo.
2. parse_cv():     convierte ese texto en datos del perfil.
   - Si hay IA configurada (Claude u OpenAI) se usa la IA.
   - Si no hay IA, o la IA falla, se usa un lector básico por reglas (regex).
3. normalize():    limpia el resultado y lo traduce a los ids de la base de datos
                   (ciudad, nivel educativo, idioma) para autocompletar el formulario.
"""
import io
import logging
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogs import EducationLevel, Language
from app.models.city import City
from app.services.ai.base import AIError, get_ai_provider
from app.services.ai.prompts import build_cv_extraction_prompt
from app.utils.helpers import normalize_text

logger = logging.getLogger("empleate.cv")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?57[\s-]?)?(?:\(?\d{1,3}\)?[\s.-]?)?\d{3}[\s.-]?\d{2,4}[\s.-]?\d{2,4}")
VALID_PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")
YEAR_RE = re.compile(r"\b(19[6-9]\d|20[0-4]\d)\b")

MONTHS = {
    "ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12,
}
CURRENT_WORDS = r"(?:actualidad|actual|presente|la fecha|hoy|present|current|en curso)"
DATE_TOKEN = r"(?:[a-zA-ZáéíóúÁÉÍÓÚ]{3,10}\.?\s+(?:de\s+)?(?:19|20)\d{2}|\d{1,2}[/-](?:19|20)\d{2}|(?:19|20)\d{2})"
RANGE_RE = re.compile(
    rf"({DATE_TOKEN})\s*(?:-|–|—|a|al|hasta|to)\s*({DATE_TOKEN}|{CURRENT_WORDS})", re.IGNORECASE
)

SECTION_KEYWORDS = {
    "summary": ["perfil", "resumen", "sobre mi", "acerca de mi", "objetivo", "profile", "summary"],
    "experience": ["experiencia", "historial laboral", "trayectoria", "experience", "work history"],
    "education": ["educacion", "formacion", "estudios", "academic", "education"],
    "skills": ["habilidades", "competencias", "conocimientos", "herramientas", "aptitudes",
               "skills", "tecnologias"],
    "languages": ["idiomas", "languages", "lenguas"],
    "other": ["referencias", "contacto", "datos personales", "informacion personal", "certificaciones",
              "certificados", "cursos", "logros", "proyectos", "intereses", "hobbies", "references"],
}
HEADER_NOISE = ("hoja de vida", "curriculum", "curriculo", "resume", "cv")

LANGUAGE_ALIASES = {
    "espanol": "espanol", "castellano": "espanol", "spanish": "espanol",
    "ingles": "ingles", "english": "ingles",
    "portugues": "portugues", "portuguese": "portugues",
    "frances": "frances", "french": "frances",
    "aleman": "aleman", "german": "aleman",
    "italiano": "italiano", "italian": "italiano",
}

# Palabra clave -> nombre del nivel en la tabla education_levels (el orden importa)
EDUCATION_LEVEL_KEYWORDS = [
    ("doctor", "doctorado"), ("phd", "doctorado"),
    ("maestr", "maestria"), ("magister", "maestria"), ("master", "maestria"), ("mba", "maestria"),
    ("especializ", "especializacion"),
    ("tecnolog", "tecnologo"),
    ("tecnic", "tecnico"),
    ("bachiller", "bachillerato"), ("secundaria", "bachillerato"),
    ("ingenier", "pregrado"), ("licenciad", "pregrado"), ("profesional", "pregrado"),
    ("pregrado", "pregrado"), ("administrador", "pregrado"), ("contador", "pregrado"),
    ("psicolog", "pregrado"), ("abogad", "pregrado"), ("derecho", "pregrado"), ("medic", "pregrado"),
    ("economi", "pregrado"), ("arquitect", "pregrado"), ("diseñ", "pregrado"), ("disen", "pregrado"),
]
INSTITUTION_WORDS = ("universidad", "instituto", "institucion", "colegio", "sena", "escuela",
                     "corporacion", "fundacion", "politecnico", "university", "college", "academia")


class CVReadError(Exception):
    """No se pudo leer el texto del archivo."""


# =====================================================================
# 1. EXTRAER TEXTO
# =====================================================================
def extract_text(content: bytes, ext: str) -> str:
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        elif ext == ".docx":
            from docx import Document

            doc = Document(io.BytesIO(content))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:  # muchas plantillas de CV usan tablas
                for row in table.rows:
                    for cell in row.cells:
                        parts.append(cell.text)
            text = "\n".join(parts)
        else:
            raise CVReadError("Formato no compatible.")
    except CVReadError:
        raise
    except Exception as exc:  # noqa: BLE001 - archivo dañado o protegido
        raise CVReadError("No pudimos abrir el archivo. Puede estar dañado o protegido con contraseña.") from exc

    # Limpieza: espacios repetidos y líneas vacías
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)

    if len(text) < 40:
        raise CVReadError(
            "No encontramos texto en el archivo. Si es un PDF escaneado (imagen), súbelo en Word o "
            "como PDF con texto seleccionable."
        )
    return text


# =====================================================================
# 2. INTERPRETAR EL TEXTO
# =====================================================================
def parse_cv(db: Session, text: str) -> tuple[dict, str]:
    """Devuelve (datos_normalizados, fuente) donde fuente es 'ia' o 'basico'."""
    provider = get_ai_provider()
    if provider is not None:
        levels = list(db.scalars(select(EducationLevel.name).order_by(EducationLevel.rank_order)))
        system, user = build_cv_extraction_prompt(text, levels)
        try:
            raw = provider.complete_json(system, user)
            return normalize(db, raw), "ia"
        except AIError:
            logger.exception("Falló la IA (%s); se usa el lector básico.", provider.name)

    return normalize(db, heuristic_parse(text)), "basico"


# ---------------- Lector básico por reglas ----------------
def _section_of(line: str) -> str | None:
    """Si la línea es un título de sección (ej: 'EXPERIENCIA LABORAL'), devuelve cuál es."""
    norm = normalize_text(line)
    if not norm or len(norm) > 40:
        return None
    for section, words in SECTION_KEYWORDS.items():
        if any(norm == w or (norm.startswith(w) and len(norm) < 30) for w in words):
            return section
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        # "Habilidades: Excel, Python" -> título + contenido en la misma línea
        head, sep, rest = line.partition(":")
        found = _section_of(head if sep else line)
        if found:
            current = found
            sections.setdefault(current, [])
            if sep and rest.strip():
                sections[current].append(rest.strip())
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _parse_date_token(token: str) -> str | None:
    """'Ene 2020' -> '2020-01' | '03/2021' -> '2021-03' | '2019' -> '2019-01'."""
    token = normalize_text(token)
    if re.fullmatch(CURRENT_WORDS, token):
        return None
    year = YEAR_RE.search(token)
    if not year:
        return None
    month = 1
    numeric = re.match(r"(\d{1,2})[/-]", token)
    if numeric and 1 <= int(numeric.group(1)) <= 12:
        month = int(numeric.group(1))
    else:
        for key, value in MONTHS.items():
            if token.startswith(key):
                month = value
                break
    return f"{year.group(1)}-{month:02d}"


def _guess_name(header: list[str]) -> tuple[str | None, str | None]:
    for line in header[:6]:
        norm = normalize_text(line)
        if any(n in norm for n in HEADER_NOISE) or EMAIL_RE.search(line) or re.search(r"\d", line):
            continue
        words = [w for w in re.split(r"\s+", line.strip()) if w]
        if 2 <= len(words) <= 5 and all(re.fullmatch(r"[A-Za-zÁÉÍÓÚÑáéíóúñÜü'.-]+", w) for w in words):
            words = [w.capitalize() if w.isupper() else w for w in words]
            split = 2 if len(words) >= 4 else 1
            return " ".join(words[:split]), " ".join(words[split:])
    return None, None


def _parse_experiences(lines: list[str]) -> list[dict]:
    experiences: list[dict] = []
    used: set[int] = set()
    for i, line in enumerate(lines):
        match = RANGE_RE.search(line)
        if not match:
            continue
        start = _parse_date_token(match.group(1))
        end_token = match.group(2)
        is_current = bool(re.fullmatch(CURRENT_WORDS, normalize_text(end_token)))
        end = None if is_current else _parse_date_token(end_token)

        # Cargo y empresa: texto de la misma línea o de las líneas anteriores
        before = line[: match.start()].strip(" -|,–:")
        context = [before] if before else []
        j = i - 1
        while j >= 0 and len(context) < 2 and j not in used and not RANGE_RE.search(lines[j]):
            if not lines[j].lstrip().startswith(("•", "-", "*")):
                context.insert(0, lines[j].strip(" -|,–:"))
            used.add(j)
            j -= 1
        position, company = None, None
        if len(context) == 1 and re.search(r"\s[-|–]\s|\sen\s", context[0]):
            parts = re.split(r"\s[-|–]\s|\sen\s", context[0], maxsplit=1)
            position, company = parts[0], parts[1]
        elif len(context) >= 2:
            position, company = context[-2], context[-1]
        elif context:
            position = context[0]

        # Descripción: líneas siguientes hasta la próxima fecha
        desc: list[str] = []
        k = i + 1
        while k < len(lines) and not RANGE_RE.search(lines[k]) and len(desc) < 6:
            ahead = lines[k + 1 : k + 3]
            is_bullet = bool(re.match(r"^\W", lines[k]))
            if not is_bullet and any(RANGE_RE.search(a) for a in ahead):
                break  # esta línea es el cargo/empresa del siguiente empleo
            desc.append(re.sub(r"^[^\w(¿¡]+", "", lines[k]))
            used.add(k)
            k += 1

        experiences.append({
            "company_name": company, "position": position, "start_date": start, "end_date": end,
            "is_current": is_current, "description": " ".join(desc) or None,
        })
    return experiences[:10]


def _parse_educations(lines: list[str]) -> list[dict]:
    educations: list[dict] = []
    for i, line in enumerate(lines):
        norm = normalize_text(line)
        level = next((lv for kw, lv in EDUCATION_LEVEL_KEYWORDS if kw in norm), None)
        if level is None or any(w in norm for w in INSTITUTION_WORDS) and len(norm.split()) < 3:
            continue
        # La institución suele ir justo debajo del título (si no, justo encima)
        nearby = lines[i + 1 : i + 3] + lines[max(0, i - 2) : i][::-1]
        institution = next((w for w in nearby if any(x in normalize_text(w) for x in INSTITUTION_WORDS)), None)
        window = lines[i : i + 3]
        years = YEAR_RE.findall(" ".join(window))
        in_progress = re.search(CURRENT_WORDS, normalize_text(" ".join(window)))
        educations.append({
            "institution": institution,
            "degree": RANGE_RE.sub("", line).strip(" -|,–:"),
            "field_of_study": None,
            "level": level,
            "start_date": f"{years[0]}-01" if len(years) >= 2 else None,
            "end_date": None if in_progress else (f"{years[-1]}-01" if years else None),
        })
    return educations[:8]


def _parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        for item in re.split(r"[,;•·|/]|\s{2,}", line):
            item = item.strip(" -*:.\t")
            if 2 <= len(item) <= 40 and len(item.split()) <= 5:
                skills.append(item)
    return skills


def _parse_languages(lines: list[str]) -> list[dict]:
    found: list[dict] = []
    for line in lines:
        norm = normalize_text(line)
        for alias, canonical in LANGUAGE_ALIASES.items():
            if re.search(rf"\b{alias}\b", norm):
                if re.search(r"nativ|matern", norm):
                    level = "nativo"
                elif re.search(r"avanzad|fluid|\bc1\b|\bc2\b|advanced", norm):
                    level = "avanzado"
                elif re.search(r"intermedi|\bb1\b|\bb2\b", norm):
                    level = "intermedio"
                else:
                    level = "basico"
                found.append({"name": canonical, "proficiency": level})
    return found


def heuristic_parse(text: str) -> dict:
    lines = [line for line in text.splitlines() if line.strip()]
    sections = _split_sections(lines)
    first_name, last_name = _guess_name(sections.get("header", []) or lines)

    email = EMAIL_RE.search(text)
    phone = next((m.group(0) for m in PHONE_RE.finditer(text) if len(re.sub(r"\D", "", m.group(0))) >= 7), None)
    summary = " ".join(sections.get("summary", []))[:600] or None

    experiences = _parse_experiences(sections.get("experience", []))
    language_lines = sections.get("languages") or lines

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email.group(0) if email else None,
        "phone": phone,
        "city": " ".join(sections.get("header", [])[:8]),  # se busca una ciudad conocida en el encabezado
        "desired_position": experiences[0]["position"] if experiences else None,
        "summary": summary,
        "experiences": experiences,
        "educations": _parse_educations(sections.get("education", [])),
        "skills": _parse_skills(sections.get("skills", [])),
        "languages": _parse_languages(language_lines),
    }


# =====================================================================
# 3. NORMALIZAR (sirve igual para la IA y para el lector básico)
# =====================================================================
def _clean(value, max_len: int) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value[:max_len] if value else None


def _to_date(value) -> str | None:
    """'2021-03' o '2021-03-15' -> '2021-03-01' (ISO). Fechas inválidas o futuras -> None."""
    if not value:
        return None
    match = re.match(r"^((?:19|20)\d{2})(?:-(\d{1,2}))?", str(value).strip())
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2) or 1)
    if not 1 <= month <= 12:
        month = 1
    result = date(year, month, 1)
    return result.isoformat() if result <= date.today() else None


def _match_city(db: Session, raw_city: str | None) -> int | None:
    if not raw_city:
        return None
    text = normalize_text(raw_city)
    cities = db.execute(select(City.id, City.name)).all()
    # Primero la coincidencia más larga (evita que "Cali" gane sobre un nombre más específico)
    for city in sorted(cities, key=lambda c: -len(c.name)):
        if re.search(rf"\b{re.escape(normalize_text(city.name))}\b", text):
            return city.id
    return None


def normalize(db: Session, raw: dict) -> dict:
    raw = raw or {}

    level_ids = {normalize_text(lv.name): lv.id for lv in db.scalars(select(EducationLevel))}
    language_ids = {normalize_text(lg.name): lg.id for lg in db.scalars(select(Language))}

    phone = _clean(raw.get("phone"), 30)
    if phone and not VALID_PHONE_RE.match(phone):
        phone = None
    email = _clean(raw.get("email"), 255)
    if email and not EMAIL_RE.fullmatch(email):
        email = None

    experiences = []
    for exp in raw.get("experiences") or []:
        if not isinstance(exp, dict):
            continue
        company, position = _clean(exp.get("company_name"), 150), _clean(exp.get("position"), 150)
        if not company and not position:
            continue
        is_current = bool(exp.get("is_current"))
        start, end = _to_date(exp.get("start_date")), None if is_current else _to_date(exp.get("end_date"))
        if start and end and end < start:
            end = None
        experiences.append({
            "company_name": company, "position": position, "start_date": start, "end_date": end,
            "is_current": is_current, "description": _clean(exp.get("description"), 1000),
        })

    educations = []
    for edu in raw.get("educations") or []:
        if not isinstance(edu, dict):
            continue
        institution, degree = _clean(edu.get("institution"), 150), _clean(edu.get("degree"), 150)
        if not institution and not degree:
            continue
        start, end = _to_date(edu.get("start_date")), _to_date(edu.get("end_date"))
        if start and end and end < start:
            start = None
        educations.append({
            "education_level_id": level_ids.get(normalize_text(edu.get("level") or "")),
            "institution": institution, "degree": degree,
            "field_of_study": _clean(edu.get("field_of_study"), 150),
            "start_date": start, "end_date": end,
        })

    skills, seen = [], set()
    for skill in raw.get("skills") or []:
        skill = _clean(skill, 100)
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            skills.append(skill)

    languages, seen_lang = [], set()
    for lang in raw.get("languages") or []:
        if not isinstance(lang, dict):
            continue
        canonical = LANGUAGE_ALIASES.get(normalize_text(lang.get("name") or ""))
        language_id = language_ids.get(canonical or normalize_text(lang.get("name") or ""))
        if language_id and language_id not in seen_lang:
            seen_lang.add(language_id)
            level = normalize_text(lang.get("proficiency") or "basico")
            languages.append({
                "language_id": language_id,
                "proficiency": level if level in ("basico", "intermedio", "avanzado", "nativo") else "basico",
            })

    return {
        "first_name": _clean(raw.get("first_name"), 100),
        "last_name": _clean(raw.get("last_name"), 100),
        "email": email.lower() if email else None,
        "phone": phone,
        "city_id": _match_city(db, raw.get("city")),
        "desired_position": _clean(raw.get("desired_position"), 150),
        "summary": _clean(raw.get("summary"), 2000),
        "experiences": experiences,
        "educations": educations,
        "skills": skills[:25],
        "languages": languages,
    }
