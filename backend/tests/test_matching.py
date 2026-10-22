"""Cálculo de compatibilidad aspirante <-> vacante (sin base de datos)."""
from datetime import date
from types import SimpleNamespace

from app.services.matching_service import ApplicantContext, _experience_years, compute_score


def job(required=(), desired=(), **fields):
    skills = [SimpleNamespace(is_required=True, skill=SimpleNamespace(name=s)) for s in required] + [
        SimpleNamespace(is_required=False, skill=SimpleNamespace(name=s)) for s in desired
    ]
    data = {"title": "Cargo", "description": "", "requirements": None, "min_experience_years": 0,
            "min_education": None, "modality": "presencial", "city_id": 1, "salary_min": None, "salary_max": None}
    data.update(fields)
    return SimpleNamespace(skills=skills, **data)


def ctx(**fields):
    data = {"applicant_id": 1, "city_id": 1, "desired_modality": None, "willing_to_relocate": False,
            "desired_salary_min": None, "skills": set(), "experience_years": 0.0, "education_rank": 0}
    data.update(fields)
    return ApplicantContext(**data)


def test_overlapping_experience_is_not_counted_twice():
    periods = [(date(2020, 1, 1), date(2022, 1, 1)), (date(2021, 1, 1), date(2023, 1, 1)),
               (date(2024, 1, 1), date(2025, 1, 1))]
    assert _experience_years(periods) == 4.0
    assert _experience_years([]) == 0.0


def test_perfect_match_scores_100():
    score, reasons, gaps, matched = compute_score(
        ctx(skills={"python", "sql"}, experience_years=5, education_rank=4, desired_salary_min=3e6),
        job(["Python"], ["SQL"], min_experience_years=2, min_education=SimpleNamespace(name="Pregrado", rank_order=4),
            salary_max=5e6),
    )
    assert score == 100
    assert matched == {"Python", "SQL"}
    assert "Es en tu ciudad" in reasons


def test_missing_skills_and_other_city_lower_the_score():
    score, reasons, gaps, matched = compute_score(ctx(city_id=2), job(["Java", "Spring"], min_experience_years=3))
    assert score < 40 and not matched and not reasons
    assert gaps == ["No registras las habilidades requeridas: Java, Spring",
                    "Pide 3 años de experiencia; registras 0 años", "La vacante es en otra ciudad"]


def test_skill_names_ignore_case_and_accents():
    matched = compute_score(ctx(skills={"atencion al cliente"}), job(["Atención al Cliente"])).matched_skills
    assert matched == {"Atención al Cliente"}


def test_remote_job_counts_as_location_match_anywhere():
    near = compute_score(ctx(city_id=1), job(modality="presencial", city_id=1)).score
    remote, reasons, _, _ = compute_score(ctx(city_id=2), job(modality="remoto", city_id=None))
    far = compute_score(ctx(city_id=2), job(modality="presencial", city_id=1)).score
    assert near == remote > far
    assert "Trabajo 100% remoto" in reasons


def test_years_use_decimal_comma():
    reasons = compute_score(ctx(experience_years=5.8), job(min_experience_years=2), audience="empresa").strengths
    assert "Cumple la experiencia mínima (2 años); registra 5,8 años" in reasons


def test_strengths_and_gaps_are_separated():
    result = compute_score(
        ctx(skills={"python"}, desired_modality="remoto", desired_salary_min=6e6),
        job(["Python", "Docker", "AWS"], modality="presencial", city_id=1, salary_max=4e6),
    )
    assert "Tienes 1 de 3 habilidades requeridas: Python" in result.strengths
    assert "Te faltan habilidades requeridas: Docker, AWS" in result.gaps
    assert "Es presencial y prefieres remoto" in result.gaps
    assert "El salario está por debajo de tu aspiración" in result.gaps
    company = compute_score(ctx(city_id=2), job(["Excel"], city_id=1), audience="empresa")
    assert "No registra las habilidades requeridas: Excel" in company.gaps
    assert "Vive en otra ciudad y no indicó que acepte trasladarse" in company.gaps
