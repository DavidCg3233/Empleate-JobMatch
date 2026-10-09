-- =====================================================================
--  JOBMATCH - Esquema de base de datos (MySQL 8.0.16+)
--  Motor: InnoDB | Charset: utf8mb4
--  Normalizacion: 3FN (catalogos separados, tablas puente N:M,
--  sin datos repetidos ni dependencias transitivas).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS jobmatch
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE jobmatch;
SET NAMES utf8mb4;

-- =====================================================================
-- 1. CATALOGOS (tablas de referencia)
-- =====================================================================

CREATE TABLE roles (
  id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(20) NOT NULL,                       -- aspirante, empresa, administrador
  PRIMARY KEY (id),
  UNIQUE KEY uq_roles_name (name)
) ENGINE=InnoDB;

CREATE TABLE departments (
  id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(80) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_departments_name (name)
) ENGINE=InnoDB;

CREATE TABLE cities (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  department_id  SMALLINT UNSIGNED NOT NULL,
  name           VARCHAR(100) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_cities_dept_name (department_id, name),
  CONSTRAINT fk_cities_department FOREIGN KEY (department_id)
    REFERENCES departments (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE industries (                           -- sectores de la empresa
  id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(100) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_industries_name (name)
) ENGINE=InnoDB;

CREATE TABLE contract_types (
  id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(50) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_contract_types_name (name)
) ENGINE=InnoDB;

CREATE TABLE education_levels (
  id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(50) NOT NULL,
  rank_order  TINYINT UNSIGNED NOT NULL,            -- permite comparar niveles (mayor = mas alto)
  PRIMARY KEY (id),
  UNIQUE KEY uq_education_levels_name (name),
  UNIQUE KEY uq_education_levels_rank (rank_order)
) ENGINE=InnoDB;

CREATE TABLE languages (
  id    SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(50) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_languages_name (name)
) ENGINE=InnoDB;

CREATE TABLE skills (                               -- catalogo que crece con lo que extrae la IA
  id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(100) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_skills_name (name)
) ENGINE=InnoDB;

-- =====================================================================
-- 2. USUARIOS Y AUTENTICACION
-- =====================================================================

CREATE TABLE users (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  role_id          TINYINT UNSIGNED NOT NULL,
  email            VARCHAR(255) NOT NULL,           -- login (unico, sin distinguir mayusculas)
  password_hash    VARCHAR(255) NOT NULL,           -- bcrypt
  is_active        TINYINT(1) NOT NULL DEFAULT 1,   -- el admin puede desactivar
  failed_attempts  TINYINT UNSIGNED NOT NULL DEFAULT 0,  -- maximo 3
  locked_until     DATETIME NULL,                   -- bloqueo temporal tras 3 fallos
  last_login_at    DATETIME NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_role (role_id),
  CONSTRAINT fk_users_role FOREIGN KEY (role_id)
    REFERENCES roles (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_users_attempts CHECK (failed_attempts <= 3)
) ENGINE=InnoDB;

CREATE TABLE password_resets (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     INT UNSIGNED NOT NULL,
  token_hash  CHAR(64) NOT NULL,                    -- SHA-256 del token (nunca el token en claro)
  expires_at  DATETIME NOT NULL,
  used_at     DATETIME NULL,                        -- NULL = aun no usado (un solo uso)
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_password_resets_token (token_hash),
  KEY idx_password_resets_user (user_id),
  CONSTRAINT fk_password_resets_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- 3. ASPIRANTES
-- =====================================================================

CREATE TABLE applicants (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id             INT UNSIGNED NOT NULL,
  first_name          VARCHAR(100) NOT NULL,
  last_name           VARCHAR(100) NOT NULL,
  phone               VARCHAR(30) NULL,
  city_id             INT UNSIGNED NULL,
  photo_path          VARCHAR(255) NULL,
  desired_position    VARCHAR(150) NULL,            -- cargo deseado
  summary             TEXT NULL,                    -- resumen profesional
  search_status       ENUM('buscando_empleo','sin_busqueda_activa')
                        NOT NULL DEFAULT 'buscando_empleo',
  desired_salary_min  DECIMAL(12,2) NULL,
  desired_modality    ENUM('presencial','remoto','hibrido') NULL,
  willing_to_relocate TINYINT(1) NOT NULL DEFAULT 0,
  cv_path             VARCHAR(255) NULL,            -- archivo subido
  cv_original_name    VARCHAR(255) NULL,
  cv_text             LONGTEXT NULL,                -- texto extraido (para IA)
  cv_parsed_at        DATETIME NULL,                -- cuando la IA autocompleto el perfil
  profile_completed   TINYINT(1) NOT NULL DEFAULT 0,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_applicants_user (user_id),          -- relacion 1:1 con users
  KEY idx_applicants_search (search_status, city_id),
  CONSTRAINT fk_applicants_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_applicants_city FOREIGN KEY (city_id)
    REFERENCES cities (id) ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT chk_applicants_salary CHECK (desired_salary_min IS NULL OR desired_salary_min >= 0)
) ENGINE=InnoDB;

CREATE TABLE applicant_experiences (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  applicant_id  INT UNSIGNED NOT NULL,
  company_name  VARCHAR(150) NOT NULL,
  position      VARCHAR(150) NOT NULL,
  start_date    DATE NOT NULL,
  end_date      DATE NULL,
  is_current    TINYINT(1) NOT NULL DEFAULT 0,
  description   TEXT NULL,
  PRIMARY KEY (id),
  KEY idx_experiences_applicant (applicant_id),
  CONSTRAINT fk_experiences_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT chk_experiences_dates CHECK (end_date IS NULL OR end_date >= start_date),
  CONSTRAINT chk_experiences_current CHECK (is_current = 0 OR end_date IS NULL)
) ENGINE=InnoDB;

CREATE TABLE applicant_educations (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  applicant_id        INT UNSIGNED NOT NULL,
  education_level_id  TINYINT UNSIGNED NOT NULL,
  institution         VARCHAR(150) NOT NULL,
  degree              VARCHAR(150) NOT NULL,        -- titulo obtenido
  field_of_study      VARCHAR(150) NULL,
  start_date          DATE NULL,
  end_date            DATE NULL,
  PRIMARY KEY (id),
  KEY idx_educations_applicant (applicant_id),
  KEY idx_educations_level (education_level_id),
  CONSTRAINT fk_educations_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_educations_level FOREIGN KEY (education_level_id)
    REFERENCES education_levels (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_educations_dates CHECK (start_date IS NULL OR end_date IS NULL OR end_date >= start_date)
) ENGINE=InnoDB;

-- N:M aspirante <-> habilidad
CREATE TABLE applicant_skills (
  applicant_id  INT UNSIGNED NOT NULL,
  skill_id      INT UNSIGNED NOT NULL,
  level         ENUM('basico','intermedio','avanzado','experto') NULL,
  PRIMARY KEY (applicant_id, skill_id),
  KEY idx_applicant_skills_skill (skill_id),
  CONSTRAINT fk_applicant_skills_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_applicant_skills_skill FOREIGN KEY (skill_id)
    REFERENCES skills (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- N:M aspirante <-> idioma
CREATE TABLE applicant_languages (
  applicant_id  INT UNSIGNED NOT NULL,
  language_id   SMALLINT UNSIGNED NOT NULL,
  proficiency   ENUM('basico','intermedio','avanzado','nativo') NOT NULL DEFAULT 'basico',
  PRIMARY KEY (applicant_id, language_id),
  KEY idx_applicant_languages_language (language_id),
  CONSTRAINT fk_applicant_languages_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_applicant_languages_language FOREIGN KEY (language_id)
    REFERENCES languages (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =====================================================================
-- 4. EMPRESAS Y VACANTES
-- =====================================================================

CREATE TABLE companies (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id        INT UNSIGNED NOT NULL,
  name           VARCHAR(150) NOT NULL,
  tax_id         VARCHAR(30) NOT NULL,              -- NIT
  industry_id    SMALLINT UNSIGNED NOT NULL,
  size           ENUM('1-10','11-50','51-200','201-500','501-1000','1000+') NOT NULL,
  description    TEXT NULL,
  city_id        INT UNSIGNED NOT NULL,
  address        VARCHAR(255) NULL,
  website        VARCHAR(255) NULL,
  logo_path      VARCHAR(255) NULL,
  contact_name   VARCHAR(150) NOT NULL,
  contact_phone  VARCHAR(30) NULL,
  contact_email  VARCHAR(255) NOT NULL,             -- puede diferir del correo de login
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_companies_user (user_id),           -- relacion 1:1 con users
  UNIQUE KEY uq_companies_tax_id (tax_id),
  KEY idx_companies_industry (industry_id),
  KEY idx_companies_city (city_id),
  CONSTRAINT fk_companies_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_companies_industry FOREIGN KEY (industry_id)
    REFERENCES industries (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_companies_city FOREIGN KEY (city_id)
    REFERENCES cities (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE jobs (
  id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  company_id            INT UNSIGNED NOT NULL,
  title                 VARCHAR(150) NOT NULL,
  description           TEXT NOT NULL,
  requirements          TEXT NULL,
  city_id               INT UNSIGNED NULL,          -- NULL si es 100% remoto
  modality              ENUM('presencial','remoto','hibrido') NOT NULL,
  contract_type_id      TINYINT UNSIGNED NOT NULL,
  min_education_id      TINYINT UNSIGNED NULL,
  min_experience_years  TINYINT UNSIGNED NOT NULL DEFAULT 0,
  salary_min            DECIMAL(12,2) NULL,
  salary_max            DECIMAL(12,2) NULL,
  currency              CHAR(3) NOT NULL DEFAULT 'COP',
  status                ENUM('activa','pausada','cerrada') NOT NULL DEFAULT 'activa',
  is_enabled            TINYINT(1) NOT NULL DEFAULT 1,   -- el admin puede deshabilitarla
  published_at          DATETIME NULL,
  closes_at             DATE NULL,
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_jobs_company (company_id),
  KEY idx_jobs_feed (status, is_enabled, modality, city_id),
  KEY idx_jobs_contract (contract_type_id),
  KEY idx_jobs_education (min_education_id),
  KEY idx_jobs_city (city_id),
  FULLTEXT KEY ft_jobs_search (title, description, requirements),   -- buscador
  CONSTRAINT fk_jobs_company FOREIGN KEY (company_id)
    REFERENCES companies (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jobs_city FOREIGN KEY (city_id)
    REFERENCES cities (id) ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_jobs_contract FOREIGN KEY (contract_type_id)
    REFERENCES contract_types (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_jobs_education FOREIGN KEY (min_education_id)
    REFERENCES education_levels (id) ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT chk_jobs_salary CHECK (
    (salary_min IS NULL OR salary_min >= 0)
    AND (salary_max IS NULL OR salary_max >= 0)
    AND (salary_min IS NULL OR salary_max IS NULL OR salary_max >= salary_min)
  )
) ENGINE=InnoDB;

-- N:M vacante <-> habilidad
CREATE TABLE job_skills (
  job_id       INT UNSIGNED NOT NULL,
  skill_id     INT UNSIGNED NOT NULL,
  is_required  TINYINT(1) NOT NULL DEFAULT 1,       -- 1 = obligatoria, 0 = deseable
  PRIMARY KEY (job_id, skill_id),
  KEY idx_job_skills_skill (skill_id),
  CONSTRAINT fk_job_skills_job FOREIGN KEY (job_id)
    REFERENCES jobs (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_job_skills_skill FOREIGN KEY (skill_id)
    REFERENCES skills (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =====================================================================
-- 5. SWIPES Y MATCHES
-- =====================================================================

-- Aspirante desliza una vacante
CREATE TABLE applicant_swipes (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  applicant_id  INT UNSIGNED NOT NULL,
  job_id        INT UNSIGNED NOT NULL,
  action        ENUM('like','dislike') NOT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_applicant_swipes (applicant_id, job_id),   -- no se repiten tarjetas
  KEY idx_applicant_swipes_job (job_id, action),
  CONSTRAINT fk_applicant_swipes_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_applicant_swipes_job FOREIGN KEY (job_id)
    REFERENCES jobs (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- Empresa desliza un aspirante PARA UNA VACANTE concreta
CREATE TABLE company_swipes (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id        INT UNSIGNED NOT NULL,
  applicant_id  INT UNSIGNED NOT NULL,
  action        ENUM('like','dislike') NOT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_company_swipes (job_id, applicant_id),
  KEY idx_company_swipes_applicant (applicant_id, action),
  CONSTRAINT fk_company_swipes_job FOREIGN KEY (job_id)
    REFERENCES jobs (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_company_swipes_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- Match = like del aspirante a la vacante + like de la empresa a ese aspirante.
-- El backend lo crea cuando se cumplen ambos likes (INSERT IGNORE por el UNIQUE).
CREATE TABLE matches (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id        INT UNSIGNED NOT NULL,
  applicant_id  INT UNSIGNED NOT NULL,
  matched_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_matches (job_id, applicant_id),
  KEY idx_matches_applicant (applicant_id),
  CONSTRAINT fk_matches_job FOREIGN KEY (job_id)
    REFERENCES jobs (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_matches_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- 6. IA: SCORES Y EMBEDDINGS (cache para no gastar API)
-- =====================================================================

CREATE TABLE match_scores (
  id                   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  applicant_id         INT UNSIGNED NOT NULL,
  job_id               INT UNSIGNED NOT NULL,
  semantic_similarity  DECIMAL(5,4) NULL,           -- similitud coseno (embeddings)
  score                TINYINT UNSIGNED NULL,       -- 0-100 calculado por la IA
  explanation          TEXT NULL,                   -- "por que hace match"
  model_used           VARCHAR(80) NULL,
  calculated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_match_scores (applicant_id, job_id),
  KEY idx_match_scores_job (job_id, score),
  CONSTRAINT fk_match_scores_applicant FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_match_scores_job FOREIGN KEY (job_id)
    REFERENCES jobs (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT chk_match_scores_score CHECK (score IS NULL OR score <= 100)
) ENGINE=InnoDB;

CREATE TABLE applicant_embeddings (
  applicant_id  INT UNSIGNED NOT NULL,
  model         VARCHAR(80) NOT NULL,
  vector        JSON NOT NULL,                      -- arreglo de floats
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (applicant_id),
  CONSTRAINT fk_applicant_embeddings FOREIGN KEY (applicant_id)
    REFERENCES applicants (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE job_embeddings (
  job_id      INT UNSIGNED NOT NULL,
  model       VARCHAR(80) NOT NULL,
  vector      JSON NOT NULL,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (job_id),
  CONSTRAINT fk_job_embeddings FOREIGN KEY (job_id)
    REFERENCES jobs (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- 7. ADMINISTRACION: bitacora de actividad
-- =====================================================================

CREATE TABLE audit_logs (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id      INT UNSIGNED NULL,                   -- NULL si el usuario fue eliminado
  action       VARCHAR(60) NOT NULL,                -- login, register, swipe, match, disable_user...
  entity_type  VARCHAR(40) NULL,                    -- user, job, match...
  entity_id    INT UNSIGNED NULL,
  details      JSON NULL,
  ip_address   VARCHAR(45) NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_user (user_id),
  KEY idx_audit_created (created_at),
  KEY idx_audit_action (action),
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- =====================================================================
-- 8. VISTAS
-- =====================================================================

-- Anos de experiencia calculados (evita guardar un dato derivado)
CREATE OR REPLACE VIEW v_applicant_experience_years AS
SELECT a.id AS applicant_id,
       ROUND(COALESCE(SUM(TIMESTAMPDIFF(MONTH, e.start_date,
             COALESCE(e.end_date, CURDATE()))), 0) / 12, 1) AS years_experience
FROM applicants a
LEFT JOIN applicant_experiences e ON e.applicant_id = a.id
GROUP BY a.id;

-- Contadores del dashboard del administrador
CREATE OR REPLACE VIEW v_admin_stats AS
SELECT
  (SELECT COUNT(*) FROM applicants)                              AS total_applicants,
  (SELECT COUNT(*) FROM companies)                               AS total_companies,
  (SELECT COUNT(*) FROM jobs)                                    AS total_jobs,
  (SELECT COUNT(*) FROM jobs WHERE status = 'activa' AND is_enabled = 1) AS active_jobs,
  (SELECT COUNT(*) FROM matches)                                 AS total_matches,
  (SELECT COUNT(*) FROM applicant_swipes)                        AS total_applicant_swipes,
  (SELECT COUNT(*) FROM company_swipes)                          AS total_company_swipes;

-- =====================================================================
-- 9. DATOS INICIALES (INSERT IGNORE permite re-ejecutar el script)
-- =====================================================================

INSERT IGNORE INTO roles (id, name) VALUES
  (1, 'aspirante'), (2, 'empresa'), (3, 'administrador');

INSERT IGNORE INTO contract_types (id, name) VALUES
  (1, 'Término indefinido'), (2, 'Término fijo'), (3, 'Obra o labor'),
  (4, 'Prestación de servicios'), (5, 'Aprendizaje'), (6, 'Prácticas');

INSERT IGNORE INTO education_levels (id, name, rank_order) VALUES
  (1, 'Bachillerato', 1), (2, 'Técnico', 2), (3, 'Tecnólogo', 3),
  (4, 'Pregrado', 4), (5, 'Especialización', 5), (6, 'Maestría', 6),
  (7, 'Doctorado', 7);

INSERT IGNORE INTO languages (id, name) VALUES
  (1, 'Español'), (2, 'Inglés'), (3, 'Portugués'), (4, 'Francés'),
  (5, 'Alemán'), (6, 'Italiano');

INSERT IGNORE INTO industries (id, name) VALUES
  (1, 'Tecnología'), (2, 'Salud'), (3, 'Educación'), (4, 'Finanzas'),
  (5, 'Comercio y retail'), (6, 'Manufactura'), (7, 'Construcción'),
  (8, 'Logística y transporte'), (9, 'Turismo y hotelería'),
  (10, 'Servicios profesionales'), (11, 'Agroindustria'), (12, 'Otro');

INSERT IGNORE INTO departments (id, name) VALUES
  (1, 'Valle del Cauca'), (2, 'Bogotá D.C.'), (3, 'Antioquia'),
  (4, 'Atlántico'), (5, 'Cundinamarca'), (6, 'Santander');

INSERT IGNORE INTO cities (department_id, name) VALUES
  (1, 'Cali'), (1, 'Palmira'), (1, 'Tuluá'), (1, 'Buenaventura'),
  (2, 'Bogotá'),
  (3, 'Medellín'), (3, 'Envigado'),
  (4, 'Barranquilla'),
  (5, 'Soacha'),
  (6, 'Bucaramanga');

-- NOTA: el usuario administrador se crea desde el backend (script de seed),
-- porque necesita el hash bcrypt de la contraseña.