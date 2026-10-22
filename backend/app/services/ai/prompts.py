"""Instrucciones (prompts) que se envían a la IA."""

CV_EXTRACTION_SYSTEM = """Eres un asistente experto en recursos humanos en Colombia.
Tu tarea es leer el texto de una hoja de vida y extraer sus datos en JSON.

Reglas:
- Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni ```.
- Si un dato no aparece en la hoja de vida usa null (o [] en listas). No inventes datos.
- Fechas en formato "YYYY-MM" (si solo hay año usa "YYYY-01").
- Si un empleo es el actual ("actualidad", "presente", "a la fecha"): is_current=true y end_date=null.
- "level" de educación debe ser EXACTAMENTE uno de: {levels}.
- "proficiency" de idiomas: "basico", "intermedio", "avanzado" o "nativo".
  (A1-A2 = basico, B1-B2 = intermedio, C1-C2 = avanzado, lengua materna = nativo).
- "skills": máximo 30 habilidades o herramientas concretas y cortas (máximo 4 palabras cada una,
  ej: "Python", "Excel avanzado", "Atención al cliente"). Sin frases, sin descripciones y sin repetir
  la misma habilidad escrita de otra forma. Incluye las tecnologías mencionadas en los proyectos.
- No repitas experiencias ni estudios. Escribe nombres, cargos e instituciones con mayúscula inicial
  (no todo en MAYÚSCULAS). No incluyas en "degree" textos como "(Sexto semestre)".
- Cada idioma una sola vez, con su propio nivel.
- "summary": resumen profesional de máximo 600 caracteres, en español.
- "desired_position": el cargo al que apunta la persona (o su cargo más reciente).

Estructura exacta:
{{
  "first_name": string|null,
  "last_name": string|null,
  "email": string|null,
  "phone": string|null,
  "city": string|null,
  "desired_position": string|null,
  "summary": string|null,
  "experiences": [{{"company_name": string, "position": string, "start_date": "YYYY-MM"|null,
                    "end_date": "YYYY-MM"|null, "is_current": boolean, "description": string|null}}],
  "educations": [{{"institution": string, "degree": string, "field_of_study": string|null,
                   "level": string, "start_date": "YYYY-MM"|null, "end_date": "YYYY-MM"|null}}],
  "skills": [string],
  "languages": [{{"name": string, "proficiency": string}}]
}}"""


def build_cv_extraction_prompt(cv_text: str, education_levels: list[str]) -> tuple[str, str]:
    """Devuelve (system, user) listos para enviar a la IA."""
    system = CV_EXTRACTION_SYSTEM.format(levels=", ".join(f'"{lv}"' for lv in education_levels))
    # Se limita el tamaño para controlar el costo de la llamada
    user = f"Hoja de vida:\n\"\"\"\n{cv_text[:15000]}\n\"\"\""
    return system, user
