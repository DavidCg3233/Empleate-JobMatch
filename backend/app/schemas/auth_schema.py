import re
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.schemas.applicant_schema import EducationIn, ExperienceIn, LanguageIn, SkillName

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
CompanySize = Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]

PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")
WEBSITE_RE = re.compile(r"^https?://[^\s/]+\.[^\s/]+(/\S*)?$", re.IGNORECASE)


def _empty_to_none(value):
    """Los campos opcionales vacíos ("" o solo espacios) se guardan como NULL."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _check_phone(value):
    if value is None:
        return value
    value = value.strip()
    if not PHONE_RE.match(value):
        raise ValueError("El número de teléfono no es válido.")
    return value


def validate_password_rules(value: str) -> str:
    """Reglas de contraseña (registro y recuperación)."""
    if len(value) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if len(value) > 64:
        raise ValueError("La contraseña no puede superar los 64 caracteres.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("La contraseña debe incluir letras y números.")
    return value


# ---------------- Login ----------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    email: str


# ---------------- Registro ----------------
class _RegisterBase(BaseModel):
    email: EmailStr
    password: str

    _password = field_validator("password")(validate_password_rules)


class RegisterApplicantRequest(_RegisterBase):
    first_name: Name
    last_name: Name
    phone: str | None = None
    city_id: int | None = None

    # ---- Datos que se pueden autocompletar desde la hoja de vida (todos opcionales) ----
    cv_upload_id: str | None = None          # id que devolvió POST /api/auth/cv/parse
    desired_position: str | None = Field(default=None, max_length=150)
    summary: str | None = Field(default=None, max_length=2000)
    experiences: list[ExperienceIn] = Field(default_factory=list, max_length=15)
    educations: list[EducationIn] = Field(default_factory=list, max_length=10)
    skills: list[SkillName] = Field(default_factory=list, max_length=25)
    languages: list[LanguageIn] = Field(default_factory=list, max_length=10)

    _clean = field_validator(
        "phone", "city_id", "cv_upload_id", "desired_position", "summary", mode="before"
    )(_empty_to_none)
    _phone = field_validator("phone")(_check_phone)


class RegisterCompanyRequest(_RegisterBase):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
    tax_id: str
    industry_id: int
    size: CompanySize
    city_id: int
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    contact_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
    contact_phone: str | None = None
    contact_email: EmailStr | None = None  # si no viene, se usa el correo de la cuenta

    _clean = field_validator(
        "description", "address", "website", "contact_phone", "contact_email", mode="before"
    )(_empty_to_none)
    _phone = field_validator("contact_phone")(_check_phone)

    @field_validator("tax_id")
    @classmethod
    def check_tax_id(cls, value: str) -> str:
        value = re.sub(r"[.\s]", "", value)  # 900.123.456-7 -> 900123456-7
        if not re.fullmatch(r"\d{5,15}(-\d)?", value):
            raise ValueError("El NIT no es válido. Ejemplo: 900123456-7")
        return value

    @field_validator("website")
    @classmethod
    def check_website(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not re.match(r"^https?://", value, re.IGNORECASE):
            value = "https://" + value
        if not WEBSITE_RE.match(value):
            raise ValueError("El sitio web no es válido. Ejemplo: https://miempresa.com")
        return value


# ---------------- Sesión actual ----------------
class MeResponse(BaseModel):
    user_id: int
    email: str
    role: str
    display_name: str


# ---------------- Recuperación de contraseña ----------------
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str

    _password = field_validator("password")(validate_password_rules)


class MessageResponse(BaseModel):
    message: str
