"""Hojas de vida de ejemplo para las pruebas (DOCX y PDF generados en memoria)."""
import io

CV_LINES = [
    "LAURA MARCELA GÓMEZ RÍOS",
    "Desarrolladora Backend",
    "Cali, Valle del Cauca | +57 301 234 5678 | laura.gomez@correo.com",
    "PERFIL PROFESIONAL",
    "Ingeniera de sistemas con 4 años de experiencia construyendo APIs y servicios web.",
    "EXPERIENCIA LABORAL",
    "Desarrolladora Backend",
    "Soluciones Andinas S.A.S.",
    "Ene 2022 - Actualidad",
    "• Diseño y mantenimiento de APIs REST con Python y FastAPI.",
    "Desarrolladora Junior",
    "Tecnología del Pacífico",
    "Mar 2020 - Dic 2021",
    "• Soporte y desarrollo de módulos en Django.",
    "EDUCACIÓN",
    "Ingeniería de Sistemas",
    "Universidad del Valle",
    "2014 - 2019",
    "HABILIDADES",
    "Python, FastAPI, Django, MySQL, Git, Docker",
    "IDIOMAS",
    "Español - Nativo",
    "Inglés - Intermedio (B2)",
]


def make_docx() -> bytes:
    from docx import Document

    doc = Document()
    for line in CV_LINES:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf(lines: list[str] = CV_LINES) -> bytes:
    """PDF mínimo de una página con texto seleccionable (sin librerías extra)."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")

    text_ops = ["BT", "/F1 11 Tf", "50 800 Td", "14 TL"]
    for line in lines:
        text_ops.append(f"({esc(line)}) Tj T*")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("cp1252")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()
