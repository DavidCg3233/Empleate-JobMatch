"""Lectura de hojas de vida.

1. extract_text(): saca el texto del archivo (PDF, Word .docx, OpenDocument .odt, RTF o texto plano).
2. parse_cv():     convierte ese texto en datos del perfil.
   - Si hay IA configurada (Claude u OpenAI) se usa la IA.
   - Si no hay IA, o la IA falla, se usa un lector por reglas.
3. normalize():    valida y limpia CADA campo (sin duplicados, nombres de habilidades del catálogo,
                   mayúsculas corregidas, fechas válidas) y lo traduce a los ids de la base de datos
                   (ciudad, nivel educativo, idioma) para autocompletar el formulario.
"""
import io
import logging
import re
import unicodedata
import zipfile
from datetime import date
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogs import EducationLevel, Language
from app.models.city import City
from app.services.ai.base import AIError, get_ai_provider
from app.services.ai.prompts import build_cv_extraction_prompt
from app.services.skill_service import canonical_skill, catalog_terms
from app.utils.helpers import normalize_text

logger = logging.getLogger("empleate.cv")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?57[\s-]?)?(?:\(?\d{1,3}\)?[\s.-]?)?\d{3}[\s.-]?\d{2,4}[\s.-]?\d{2,4}")
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
BULLET_RE = re.compile(r"^[\s\u2022\u25cf\u25aa\u25a0\u2023\u2043\u2219\u00b7\u27a2\u2713\u2714\ue000-\uf8ff*•·▪►✓-]+")

# Títulos de sección. El orden importa: un título como "HABILIDADES TÉCNICAS E IDIOMAS" es de habilidades.
SECTION_KEYWORDS = [
    ("experience", ["experiencia", "historial laboral", "trayectoria", "empleos", "experience", "work history", "employment"]),
    ("projects", ["proyectos", "projects", "portafolio", "portfolio"]),
    ("skills", ["habilidades", "competencias", "conocimientos", "herramientas", "aptitudes", "skills",
                "tecnologias", "stack"]),
    ("education", ["educacion", "formacion", "estudios", "academica", "academico", "education"]),
    ("courses", ["certificaciones", "certificados", "cursos", "certifications", "courses"]),
    ("languages", ["idiomas", "languages", "lenguas"]),
    ("summary", ["perfil", "resumen", "sobre mi", "acerca de mi", "objetivo", "profile", "summary", "about me"]),
    ("other", ["referencias", "contacto", "datos personales", "informacion personal", "logros", "intereses",
               "hobbies", "voluntariado", "premios", "references"]),
]
HEADER_NOISE = ("hoja de vida", "curriculum", "curriculo", "resume", "cv")
STOPWORDS = {"de", "la", "el", "en", "para", "con", "y", "a", "los", "las", "del", "mi", "mis", "por", "un", "una", "que", "e"}
SMALL_WORDS = STOPWORDS | {"o", "u", "al"}
COMPANY_SUFFIXES = {"sas": "S.A.S.", "s.a.s.": "S.A.S.", "s.a.s": "S.A.S.", "sa": "S.A.", "s.a.": "S.A.", "ltda": "Ltda.", "ltda.": "Ltda."}

LANGUAGE_ALIASES = {
    "espanol": "espanol", "castellano": "espanol", "spanish": "espanol",
    "ingles": "ingles", "english": "ingles",
    "portugues": "portugues", "portuguese": "portugues",
    "frances": "frances", "french": "frances",
    "aleman": "aleman", "german": "aleman",
    "italiano": "italiano", "italian": "italiano",
}
PROFICIENCY_ORDER = {"basico": 1, "intermedio": 2, "avanzado": 3, "nativo": 4}

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
IN_PROGRESS_RE = re.compile(r"\((?:[^)]*(?:semestre|en curso|cursando|actualidad|in progress)[^)]*)\)", re.IGNORECASE)


class CVReadError(Exception):
    """No se pudo leer el texto del archivo."""


# =====================================================================
# 1. EXTRAER TEXTO
# =====================================================================
def _docx_text(content: bytes) -> str:
    """Respeta el orden del documento (muchas plantillas de CV usan tablas) e incluye el encabezado."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(content))
    parts: list[str] = []
    for section in doc.sections[:1]:
        parts.extend(p.text for p in section.header.paragraphs)
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            parts.append(Paragraph(block, doc).text)
        elif tag == "tbl":
            for row in Table(block, doc).rows:
                seen: set[int] = set()
                for cell in row.cells:
                    if id(cell._tc) in seen:  # las celdas combinadas se repiten
                        continue
                    seen.add(id(cell._tc))
                    parts.append(cell.text)
    return "\n".join(parts)


def _odt_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        root = ElementTree.fromstring(z.read("content.xml"))
    ns_text = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    lines = []
    for el in root.iter():
        if el.tag in (f"{{{ns_text}}}p", f"{{{ns_text}}}h"):
            lines.append("".join(el.itertext()))
    return "\n".join(lines)


def _rtf_text(content: bytes) -> str:
    """Quita los códigos de formato RTF y deja el texto (suficiente para hojas de vida)."""
    text = content.decode("latin-1")
    ignored = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer", "listtable",
               "listoverridetable", "rsidtbl", "generator", "xmlnstbl", "themedata", "datastore"}
    out: list[str] = []
    stack: list[bool] = []
    skip = False
    uc_skip = 0
    token = re.compile(r"\\([a-z]{1,32})(-?\d{1,10})? ?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)", re.IGNORECASE | re.DOTALL)
    for m in token.finditer(text):
        word, arg, hexcode, symbol, brace, char = m.groups()
        if brace == "{":
            stack.append(skip)
        elif brace == "}":
            skip = stack.pop() if stack else False
        elif symbol:
            if symbol == "*":
                skip = True
            elif not skip and symbol in "\\{}":
                out.append(symbol)
            elif not skip and symbol == "~":
                out.append(" ")
        elif word:
            if word in ignored:
                skip = True
            elif skip:
                continue
            elif word in ("par", "line", "row"):
                out.append("\n")
            elif word in ("tab", "cell"):
                out.append(" ")
            elif word == "u" and arg:
                code = int(arg)
                out.append(chr(code + 65536 if code < 0 else code))
                uc_skip = 1
        elif hexcode and not skip:
            if uc_skip:
                uc_skip -= 1
            else:
                out.append(bytes([int(hexcode, 16)]).decode("cp1252", errors="ignore"))
        elif char and not skip:
            if uc_skip:
                uc_skip -= 1
            else:
                out.append(char)
    return "".join(out)


def _plain_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1", errors="ignore")


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # palabras cortadas al final de la línea: "desa-\nrrollo"
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[ \t\u00a0\u200b]+", " ", raw).strip()
        if not line or re.fullmatch(r"(p[aá]gina|page)\s*\d+(\s*(de|of)\s*\d+)?", line, re.IGNORECASE):
            continue
        # Viñetas de cualquier fuente (incluidos los símbolos privados de Word/PDF) -> "• "
        bullet = BULLET_RE.match(line)
        if bullet and bullet.group(0).strip() and not re.match(r"^-?\d", line):
            line = "• " + line[bullet.end():].strip()
        line = re.sub(r"[\ue000-\uf8ff]", "", line).strip()
        if line and line != "•":
            lines.append(line)
    return "\n".join(lines)


def extract_text(content: bytes, ext: str) -> str:
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise CVReadError("El PDF está protegido con contraseña. Quítale la protección e inténtalo de nuevo.")
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        elif ext == ".docx":
            text = _docx_text(content)
        elif ext == ".odt":
            text = _odt_text(content)
        elif ext == ".rtf":
            text = _rtf_text(content)
        elif ext == ".txt":
            text = _plain_text(content)
        else:
            raise CVReadError("Formato no compatible.")
    except CVReadError:
        raise
    except Exception as exc:  # noqa: BLE001 - archivo dañado o protegido
        raise CVReadError("No pudimos abrir el archivo. Puede estar dañado o protegido con contraseña.") from exc

    text = _clean_text(text)
    if len(text) < 40:
        raise CVReadError(
            "No encontramos texto en el archivo. Si es un PDF escaneado o una imagen, súbelo en Word "
            "o como PDF con texto seleccionable."
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


# ---------------- Lector por reglas ----------------
def _section_of(line: str) -> str | None:
    """Si la línea es un título de sección (ej: 'EXPERIENCIA LABORAL'), devuelve cuál es."""
    stripped = line.strip().rstrip(":")
    norm = normalize_text(stripped)
    words = norm.split()
    if not norm or len(norm) > 50 or len(words) > 6 or stripped.startswith("•"):
        return None
    # Un título está en MAYÚSCULAS, termina en ":" o es corto y empieza por la palabra clave
    looks_like_title = stripped.isupper() or line.strip().endswith(":") or len(words) <= 3
    for section, keywords in SECTION_KEYWORDS:
        for kw in keywords:
            if norm == kw or (looks_like_title and re.search(rf"\b{kw}\b", norm) and (stripped.isupper() or norm.startswith(kw))):
                return section
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        # "Habilidades: Excel, Python" -> título + contenido en la misma línea
        head, sep, rest = line.partition(":")
        found = _section_of(head) if sep and rest.strip() else _section_of(line)
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
        candidate = re.split(r"\s[—–|-]\s", line)[0].strip()  # "Ana Pérez — Curriculum Vitae"
        norm = normalize_text(candidate)
        if any(n in norm.split() or norm.startswith(n) for n in HEADER_NOISE) or EMAIL_RE.search(candidate) or re.search(r"\d", candidate):
            continue
        words = [w for w in re.split(r"\s+", candidate) if w]
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
        before = line[: match.start()].strip(" -|,–:()")
        context = [before] if before else []
        j = i - 1
        while j >= 0 and len(context) < 2 and j not in used and not RANGE_RE.search(lines[j]):
            if not lines[j].startswith("•"):
                context.insert(0, lines[j].strip(" -|,–:"))
            used.add(j)
            j -= 1
        position, company = None, None
        if len(context) == 1 and re.search(r"\s[-|–—]\s|\sen\s|\s@\s", context[0]):
            parts = re.split(r"\s[-|–—]\s|\sen\s|\s@\s", context[0], maxsplit=1)
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
            is_bullet = lines[k].startswith("•")
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
        if line.startswith("•"):
            continue
        norm = normalize_text(line)
        level = next((lv for kw, lv in EDUCATION_LEVEL_KEYWORDS if kw in norm), None)
        if level is None or (any(w in norm for w in INSTITUTION_WORDS) and len(norm.split()) < 3):
            continue
        # La institución suele ir justo debajo del título (si no, justo encima)
        nearby = lines[i + 1 : i + 3] + lines[max(0, i - 3) : i][::-1]
        institution = next((w for w in nearby if any(x in normalize_text(w) for x in INSTITUTION_WORDS)), None)
        window = lines[i : i + 3]
        years = YEAR_RE.findall(" ".join(window))
        in_progress = bool(re.search(CURRENT_WORDS, normalize_text(" ".join(window)))) or bool(IN_PROGRESS_RE.search(line))
        educations.append({
            "institution": institution.split(":")[0] if institution else None,
            "degree": IN_PROGRESS_RE.sub("", RANGE_RE.sub("", line)).strip(" -|,–:"),
            "field_of_study": None,
            "level": level,
            "start_date": f"{years[0]}-01" if len(years) >= 2 else None,
            "end_date": None if in_progress else (f"{years[-1]}-01" if years else None),
        })
    return educations[:8]


def _split_outside_parens(text: str) -> list[str]:
    """'Redes (Cisco, CCNA), Excel; Word' -> ['Redes (Cisco, CCNA)', 'Excel', 'Word']"""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and ch in ",;|•·/":
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [p.strip(" .:-–\t") for p in parts if p.strip(" .:-–\t")]


def _skill_candidates(item: str) -> list[str]:
    """Convierte un elemento escrito en la hoja de vida en una o varias habilidades."""
    item = item.strip(" .")
    if not item:
        return []
    canonical, category = canonical_skill(item)
    if category:
        return [canonical]
    paren = re.match(r"^(.*?)\s*\((.*)\)\s*$", item)
    if paren:  # "Redes (Cisco)" -> "Redes" y "Cisco"
        return _skill_candidates(paren.group(1)) + [c for p in _split_outside_parens(paren.group(2)) for c in _skill_candidates(p)]
    if re.search(r"\s(y|e|&)\s", item):  # "Liderazgo y Gestión" -> "Liderazgo", "Gestión"
        pieces = re.split(r"\s(?:y|e|&)\s", item)
        if all(len(p.split()) <= 4 for p in pieces):
            return [c for p in pieces for c in _skill_candidates(p)]
    return [item]


def _join_wrapped(lines: list[str]) -> list[str]:
    """Une las líneas que el PDF cortó a la mitad: '...IA (Optimización de' + 'Prompts).'"""
    joined: list[str] = []
    for line in lines:
        if joined and not line.startswith("•") and ":" not in line and (
            joined[-1].count("(") > joined[-1].count(")") or not re.search(r"[.:;]$", joined[-1])
        ) and (line[:1].islower() or joined[-1].count("(") > joined[-1].count(")")):
            joined[-1] = f"{joined[-1]} {line}"
        else:
            joined.append(line)
    return joined


def _words_outside_parens(text: str) -> int:
    return len(re.sub(r"\([^)]*\)", "", text).split())


def _parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in _join_wrapped(lines):
        if normalize_text(line.lstrip("• ")).startswith(("idiomas", "languages")):
            continue  # los idiomas van aparte
        text = line.lstrip("• ").strip()
        head, sep, rest = text.partition(":")
        if sep:
            rest = re.split(r"\.\s", rest)[0]  # "Django, SQL. Repositorio: github.com/..." -> "Django, SQL"
            items = _split_outside_parens(rest)
            # Una lista ("Python, Java, SQL") se toma completa; una frase descriptiva
            # ("Liderazgo: Capacidad para tomar la iniciativa...") solo aporta su título.
            is_list = bool(items) and all(_words_outside_parens(i) <= 4 for i in items)
            text = rest if is_list else head
        elif _words_outside_parens(text) > 6:
            continue  # una oración suelta no es una lista de habilidades
        for item in _split_outside_parens(text):
            if _words_outside_parens(item) <= 4:
                skills.extend(_skill_candidates(item))
    return skills


def _scan_catalog_skills(text: str) -> list[str]:
    """Busca en todo el texto las habilidades del catálogo (ej: 'Tecnologías: Django, Chart.js')."""
    haystack = " " + re.sub(r"\s+", " ", normalize_text(text)) + " "
    found: list[str] = []
    for key, name in catalog_terms():
        pattern = rf"(?<![\w+#.]){re.escape(key)}(?![\w+#])"
        if re.search(pattern, haystack):
            found.append(name)
            haystack = re.sub(pattern, " ", haystack)  # "excel avanzado" no cuenta también como "excel"
    return found


def _language_level(segment: str) -> str:
    seg = normalize_text(segment)
    if re.search(r"nativ|matern|native", seg):
        return "nativo"
    if re.search(r"\bc[12]\b", seg):
        return "avanzado"
    if re.search(r"\bb[12]\b", seg):
        return "intermedio"
    if re.search(r"\ba[12]\b", seg):
        return "basico"
    if re.search(r"avanzad|fluid|biling|advanced|fluent", seg):
        return "avanzado"
    if re.search(r"intermedi", seg):
        return "intermedio"
    return "basico"


def _parse_languages(lines: list[str]) -> list[dict]:
    found: dict[str, str] = {}
    for line in lines:
        text = line.lstrip("• ")
        head, sep, rest = text.partition(":")
        if sep and normalize_text(head) in ("idiomas", "languages", "lenguas"):
            text = rest
        for segment in _split_outside_parens(text) or [text]:
            norm = normalize_text(segment)
            for alias, canonical in LANGUAGE_ALIASES.items():
                if re.search(rf"\b{alias}\b", norm):
                    level = _language_level(segment)
                    if PROFICIENCY_ORDER[level] > PROFICIENCY_ORDER.get(found.get(canonical, ""), 0):
                        found[canonical] = level
    return [{"name": name, "proficiency": level} for name, level in found.items()]


def heuristic_parse(text: str) -> dict:
    lines = [line for line in text.splitlines() if line.strip()]
    sections = _split_sections(lines)
    first_name, last_name = _guess_name(sections.get("header", []) or lines)

    email = EMAIL_RE.search(text)
    phone = next((m.group(0) for m in PHONE_RE.finditer(text) if len(re.sub(r"\D", "", m.group(0))) >= 7), None)
    summary = " ".join(line.lstrip("• ") for line in sections.get("summary", [])) or None

    experiences = _parse_experiences(sections.get("experience", []))

    # Idiomas: su sección, o líneas "Idiomas: ..." dentro de otras secciones
    language_lines = sections.get("languages", []) + [
        line for line in lines if normalize_text(line.lstrip("• ")).startswith(("idiomas:", "languages:", "idiomas "))
    ]
    languages = _parse_languages(language_lines)
    if not languages:  # "Certificado en inglés B2" dentro del perfil
        languages = [lg for lg in _parse_languages(re.split(r"[.\n]", text)) if lg["name"] != "espanol"]

    # Habilidades: primero las escritas en su sección; luego las del catálogo que aparecen en el texto
    tech_lines = [line for line in lines if normalize_text(line.lstrip("• ")).startswith(("tecnologias", "herramientas", "stack"))]
    skills = _parse_skills(sections.get("skills", []) + tech_lines) + _scan_catalog_skills(text)

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
        "skills": skills,
        "languages": languages,
    }


# =====================================================================
# 3. VALIDAR Y NORMALIZAR (sirve igual para la IA y para el lector por reglas)
# =====================================================================
def _clean(value, max_len: int) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip(" ,;:-–•·*")
    return value[:max_len].strip() if value else None


def _fix_caps(value: str | None) -> str | None:
    """'DESARROLLADOR DE SOFTWARE' -> 'Desarrollador de software'... sin tocar siglas cortas (SENA, QA)."""
    if not value or not value.isupper() or len(value) <= 5:
        return value
    words = value.lower().split()
    fixed = [
        COMPANY_SUFFIXES.get(w) or (w if (i and w in SMALL_WORDS) else w.capitalize())
        for i, w in enumerate(words)
    ]
    return " ".join(fixed)


def _clean_name(value) -> str | None:
    value = _clean(value, 100)
    if not value or re.search(r"[\d@/\\]", value) or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", value):
        return None
    value = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü' .-]", "", value).strip()
    words = [w.capitalize() if (w.isupper() or w.islower()) else w for w in value.split()]
    return " ".join(words) if len(value) >= 2 else None


def _clean_phone(value) -> str | None:
    """'+57 (323) 361-3652' -> '+57 323 361 3652'  ·  '3233613652' -> '323 361 3652'."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("57") and len(digits) == 12:
        return f"+57 {digits[2:5]} {digits[5:8]} {digits[8:]}"
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    if 7 <= len(digits) <= 15:
        return digits
    return None


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


def _key(value: str | None) -> str:
    """Clave para detectar duplicados: sin tildes, mayúsculas, espacios ni puntuación ('Acme S.A.S.' = 'acme sas')."""
    return re.sub(r"[^a-z0-9+#]", "", normalize_text(value or ""))


def _valid_skill(name: str) -> bool:
    words = normalize_text(name).split()
    return (
        2 <= len(name) <= 60 or name in ("C", "R")
    ) and 1 <= len(words) <= 5 and bool(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", name)) and words[0] not in STOPWORDS and ":" not in name


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
    raw = raw if isinstance(raw, dict) else {}

    level_ids = {normalize_text(lv.name): lv.id for lv in db.scalars(select(EducationLevel))}
    language_ids = {normalize_text(lg.name): lg.id for lg in db.scalars(select(Language))}

    email = _clean(raw.get("email"), 255)
    if email and not EMAIL_RE.fullmatch(email):
        email = None

    # ---- Experiencia: limpia, sin duplicados ----
    experiences, seen_exp = [], set()
    for exp in raw.get("experiences") or []:
        if not isinstance(exp, dict):
            continue
        company = _fix_caps(_clean(exp.get("company_name"), 150))
        position = _fix_caps(_clean(exp.get("position"), 150))
        if not company and not position:
            continue
        if company and position and _key(company) == _key(position):
            company = None
        is_current = bool(exp.get("is_current"))
        start, end = _to_date(exp.get("start_date")), None if is_current else _to_date(exp.get("end_date"))
        if start and end and end < start:
            end = None
        key = (_key(position), _key(company), start)
        if key in seen_exp:
            continue
        seen_exp.add(key)
        experiences.append({
            "company_name": company, "position": position, "start_date": start, "end_date": end,
            "is_current": is_current, "description": _clean(exp.get("description"), 1000),
        })

    # ---- Educación: limpia, sin duplicados ----
    educations, seen_edu = [], set()
    for edu in raw.get("educations") or []:
        if not isinstance(edu, dict):
            continue
        institution = _fix_caps(_clean(edu.get("institution"), 150))
        degree = _fix_caps(_clean(IN_PROGRESS_RE.sub("", str(edu.get("degree") or "")), 150))
        if not institution and not degree:
            continue
        key = (_key(degree), _key(institution))
        if key in seen_edu:
            continue
        seen_edu.add(key)
        start, end = _to_date(edu.get("start_date")), _to_date(edu.get("end_date"))
        if start and end and end < start:
            start = None
        educations.append({
            "education_level_id": level_ids.get(normalize_text(edu.get("level") or "")),
            "institution": institution, "degree": degree,
            "field_of_study": _fix_caps(_clean(edu.get("field_of_study"), 150)),
            "start_date": start, "end_date": end,
        })

    # ---- Habilidades: nombre del catálogo, válidas y sin duplicados (sin importar tildes) ----
    skills, seen_skill = [], set()
    for item in raw.get("skills") or []:
        if not isinstance(item, str):
            continue
        name, _category = canonical_skill(_clean(item, 100) or "")
        key = _key(name)
        if not name or key in seen_skill or not _valid_skill(name):
            continue
        seen_skill.add(key)
        skills.append(name)

    # ---- Idiomas: uno por idioma, con el nivel más alto que se encontró ----
    best: dict[int, str] = {}
    for lang in raw.get("languages") or []:
        if not isinstance(lang, dict):
            continue
        canonical = LANGUAGE_ALIASES.get(normalize_text(lang.get("name") or ""))
        language_id = language_ids.get(canonical or normalize_text(lang.get("name") or ""))
        if not language_id:
            continue
        level = normalize_text(lang.get("proficiency") or "basico")
        level = level if level in PROFICIENCY_ORDER else "basico"
        if PROFICIENCY_ORDER[level] > PROFICIENCY_ORDER.get(best.get(language_id, ""), 0):
            best[language_id] = level
    languages = [{"language_id": lid, "proficiency": level} for lid, level in best.items()]

    return {
        "first_name": _clean_name(raw.get("first_name")),
        "last_name": _clean_name(raw.get("last_name")),
        "email": email.lower() if email else None,
        "phone": _clean_phone(raw.get("phone")),
        "city_id": _match_city(db, raw.get("city")),
        "desired_position": _fix_caps(_clean(raw.get("desired_position"), 150)),
        "summary": _clean(raw.get("summary"), 2000),
        "experiences": experiences,
        "educations": educations,
        "skills": skills[:30],
        "languages": languages,
    }
