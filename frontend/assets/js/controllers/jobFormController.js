// Empresa: crear o editar una vacante (job_form.html  ·  job_form.html?id=12 para editar).
import { getCities, getContractTypes, getEducationLevels } from "../api/catalogApi.js";
import { createCompanyJob, getCompanyJob, updateCompanyJob } from "../api/companyApi.js";
import { renderNav } from "../components/navbar.js";
import { createMoneyInput } from "../components/moneyInput.js";
import { attachSkillAutocomplete } from "../components/skillAutocomplete.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { formatMoney, jobStatusInfo } from "../utils/format.js";

const allowed = requireRole("empresa");
if (allowed) renderNav("empresa", "jobs");

const MAX_SKILLS = 20;
const jobId = new URLSearchParams(window.location.search).get("id");
const isEdit = Boolean(jobId);

const form = document.getElementById("job-form");
const errorBox = document.getElementById("error-box");
const loading = document.getElementById("loading");
const skillInput = document.getElementById("skill-input");
const skillList = document.getElementById("skill-list");
const skillCount = document.getElementById("skill-count");
const salaryPreview = document.getElementById("salary-preview");
const salaryMin = createMoneyInput(form.elements.salary_min);
const salaryMax = createMoneyInput(form.elements.salary_max);

let skills = []; // [{ name, is_required }]
let dirty = false;
let saving = false;

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// =====================================================================
// Mensajes y errores
// =====================================================================
function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function hideError() {
  errorBox.classList.add("hidden");
}

function setFieldError(name, message) {
  const box = form.querySelector(`[data-error-for="${name}"]`);
  if (box) {
    box.textContent = message || "";
    box.classList.toggle("hidden", !message);
  }
  const input = form.elements[name];
  if (input && input.classList) input.classList.toggle("is-invalid", Boolean(message));
}

// =====================================================================
// Modalidad y ciudad
// =====================================================================
const modality = () => form.elements.modality.value;

function syncModality() {
  const remote = modality() === "remoto";
  document.getElementById("city-field").hidden = remote;
  document.getElementById("remote-hint").hidden = !remote;
  if (remote) setFieldError("city_id", "");
}

// =====================================================================
// Contadores de caracteres y vista previa del salario
// =====================================================================
function updateCounters() {
  form.querySelectorAll("[data-count-for]").forEach((counter) => {
    const input = form.elements[counter.dataset.countFor];
    const length = input.value.trim().length;
    const min = Number(counter.dataset.min || 0);
    counter.textContent = min && length < min
      ? `${length} / ${input.maxLength} caracteres (mínimo ${min})`
      : `${length} / ${input.maxLength} caracteres`;
    counter.classList.toggle("is-over", Boolean(min && length > 0 && length < min));
  });
}

function updateSalaryPreview() {
  const min = salaryMin.value || 0;
  const max = salaryMax.value || 0;
  const currency = form.elements.currency.value;
  form.querySelectorAll("[data-currency-prefix]").forEach((p) => { p.textContent = currency === "USD" ? "US$" : "$"; });
  if (!min && !max) salaryPreview.textContent = "Si no indicas salario, la vacante mostrará \"Salario a convenir\".";
  else if (min && max) salaryPreview.textContent = `Se mostrará: ${formatMoney(min, currency)} - ${formatMoney(max, currency)}`;
  else salaryPreview.textContent = `Se mostrará: ${min ? "Desde " + formatMoney(min, currency) : "Hasta " + formatMoney(max, currency)}`;
}

// =====================================================================
// Editor de habilidades
// =====================================================================
function renderSkills() {
  skillList.replaceChildren(...skills.map((skill, index) => {
    const toggle = el("button", {
      type: "button", class: "skill-toggle", "aria-pressed": String(skill.is_required),
      title: "Cambiar entre requerida y deseable",
      textContent: skill.is_required ? "Requerida" : "Deseable",
      onclick: () => { skill.is_required = !skill.is_required; dirty = true; renderSkills(); },
    });
    const remove = el("button", {
      type: "button", class: "skill-remove", "aria-label": `Quitar ${skill.name}`, textContent: "×",
      onclick: () => { skills.splice(index, 1); dirty = true; renderSkills(); },
    });
    return el("span", { class: `skill-pill${skill.is_required ? " is-required" : ""}` }, skill.name, toggle, remove);
  }));
  if (!skills.length) skillList.append(el("p", { class: "hint", textContent: "Aún no has agregado habilidades." }));
  const required = skills.filter((s) => s.is_required).length;
  skillCount.textContent = `${skills.length} de ${MAX_SKILLS} · ${required} requerida(s), ${skills.length - required} deseable(s)`;
}

function addSkills(text) {
  for (const raw of text.split(",")) {
    const name = raw.trim().replace(/\s+/g, " ").slice(0, 100);
    if (!name) continue;
    if (skills.length >= MAX_SKILLS) {
      showToast(`Puedes agregar hasta ${MAX_SKILLS} habilidades.`, "error");
      break;
    }
    if (skills.some((s) => s.name.toLowerCase() === name.toLowerCase())) continue;
    skills.push({ name, is_required: true });
    dirty = true;
  }
  renderSkills();
}

function addSkillFromInput() {
  addSkills(skillInput.value);
  skillInput.value = "";
  skillInput.focus();
}

// =====================================================================
// Validación y envío
// =====================================================================
function readForm() {
  const v = (name) => form.elements[name].value.trim();
  const numberOrNull = (name) => (v(name) === "" ? null : Number(v(name)));
  return {
    title: v("title"),
    description: v("description"),
    requirements: v("requirements") || null,
    modality: modality(),
    city_id: modality() === "remoto" ? null : numberOrNull("city_id"),
    contract_type_id: numberOrNull("contract_type_id"),
    min_education_id: numberOrNull("min_education_id"),
    min_experience_years: numberOrNull("min_experience_years") ?? 0,
    salary_min: salaryMin.value,
    salary_max: salaryMax.value,
    currency: v("currency"),
    closes_at: v("closes_at") || null,
    skills: skills.map((s) => ({ ...s })),
  };
}

function validate(data) {
  const errors = {};
  if (data.title.length < 3) errors.title = "Escribe el nombre del cargo (mínimo 3 caracteres).";
  if (data.description.length < 30) errors.description = "Describe la vacante con al menos 30 caracteres.";
  if (data.modality !== "remoto" && !data.city_id) errors.city_id = "Selecciona la ciudad de la vacante.";
  if (!data.contract_type_id) errors.contract_type_id = "Selecciona el tipo de contrato.";
  if (!Number.isInteger(data.min_experience_years) || data.min_experience_years < 0 || data.min_experience_years > 40) {
    errors.min_experience_years = "Escribe un número entre 0 y 40.";
  }
  if (data.salary_min !== null && (Number.isNaN(data.salary_min) || data.salary_min < 0)) errors.salary_min = "Escribe un valor válido.";
  if (data.salary_max !== null && (Number.isNaN(data.salary_max) || data.salary_max < 0)) errors.salary_max = "Escribe un valor válido.";
  if (!errors.salary_min && !errors.salary_max && data.salary_min !== null && data.salary_max !== null && data.salary_max < data.salary_min) {
    errors.salary_max = "Debe ser mayor o igual al salario desde.";
  }
  if (data.closes_at && data.closes_at < todayIso()) errors.closes_at = "La fecha de cierre no puede estar en el pasado.";

  for (const name of ["title", "description", "city_id", "contract_type_id", "min_experience_years", "salary_min", "salary_max", "closes_at"]) {
    setFieldError(name, errors[name]);
  }
  const first = Object.keys(errors)[0];
  if (first) form.elements[first]?.focus();
  return !first;
}

// Errores 422 del servidor: debajo del campo si se puede; si no, arriba
function applyServerErrors(err) {
  const list = err.data?.detail;
  if (!Array.isArray(list)) return false;
  let shownGlobal = false;
  for (const item of list) {
    const field = item.loc?.[item.loc.length - 1];
    const message = String(item.msg).replace(/^Value error, /, "");
    if (typeof field === "string" && form.querySelector(`[data-error-for="${field}"]`)) setFieldError(field, message);
    else if (!shownGlobal) { showError(message); shownGlobal = true; }
  }
  if (!shownGlobal) showError("Revisa los campos marcados.");
  return true;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (saving) return;
  hideError();
  if (skillInput.value.trim()) addSkillFromInput(); // habilidad escrita sin presionar "Agregar"
  const data = readForm();
  if (!validate(data)) return;

  const status = event.submitter?.dataset.status || "activa";
  const buttons = form.querySelectorAll('button[type="submit"]');
  const pressed = event.submitter;
  const originalText = pressed?.textContent;
  saving = true;
  buttons.forEach((b) => { b.disabled = true; });
  if (pressed) pressed.textContent = "Guardando...";

  try {
    if (isEdit) await updateCompanyJob(jobId, data);
    else await createCompanyJob({ ...data, status });
    dirty = false;
    window.location.href = `jobs.html?saved=${isEdit ? "updated" : status === "activa" ? "created" : "draft"}`;
  } catch (err) {
    if (!(err.status === 422 && applyServerErrors(err))) showError(err.message);
    saving = false;
    buttons.forEach((b) => { b.disabled = false; });
    if (pressed) pressed.textContent = originalText;
  }
});

// =====================================================================
// Eventos
// =====================================================================
form.addEventListener("input", (e) => {
  dirty = true;
  if (e.target.name) setFieldError(e.target.name, "");
  if (e.target.name === "description" || e.target.name === "requirements") updateCounters();
  if (["salary_min", "salary_max"].includes(e.target.name)) updateSalaryPreview();
});
form.addEventListener("change", (e) => {
  dirty = true;
  if (e.target.name === "modality") syncModality();
  if (e.target.name === "currency") updateSalaryPreview();
  if (e.target.name) setFieldError(e.target.name, "");
});
attachSkillAutocomplete(skillInput, { onSelect: (name) => addSkills(name), getExisting: () => skills.map((s) => s.name) });
skillInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addSkillFromInput(); } // Enter NO envía el formulario
});
document.getElementById("add-skill").addEventListener("click", addSkillFromInput);

// Aviso si sale con cambios sin guardar
window.addEventListener("beforeunload", (e) => {
  if (dirty && !saving) { e.preventDefault(); e.returnValue = ""; }
});

// =====================================================================
// Inicio
// =====================================================================
function fillCities(cities) {
  const select = form.elements.city_id;
  select.replaceChildren(new Option("Selecciona una ciudad", ""));
  const byDepartment = new Map();
  for (const city of cities) {
    if (!byDepartment.has(city.department)) byDepartment.set(city.department, []);
    byDepartment.get(city.department).push(city);
  }
  for (const [department, list] of byDepartment) {
    const group = el("optgroup", { label: department });
    list.forEach((c) => group.append(new Option(c.name, c.id)));
    select.append(group);
  }
}

function fillJob(job) {
  const set = (name, value) => { form.elements[name].value = value ?? ""; };
  set("title", job.title);
  set("description", job.description);
  set("requirements", job.requirements);
  form.querySelector(`input[name="modality"][value="${job.modality}"]`).checked = true;
  set("city_id", job.city_id);
  set("contract_type_id", job.contract_type_id);
  set("min_education_id", job.min_education_id);
  set("min_experience_years", job.min_experience_years);
  salaryMin.value = job.salary_min;
  salaryMax.value = job.salary_max;
  set("currency", job.currency);
  set("closes_at", job.closes_at);
  skills = job.skills.map((s) => ({ name: s.name, is_required: s.is_required }));
}

function setupEditMode(job) {
  document.title = `Editar: ${job.title} | Empléate Jobmatch`;
  document.getElementById("form-title").textContent = "Editar vacante";
  const { label } = jobStatusInfo(job);
  document.getElementById("form-subtitle").textContent =
    `Estado actual: ${label}. Guardar los cambios no cambia el estado; publícala, páusala o ciérrala desde "Mis vacantes".`;
  document.getElementById("draft-btn").remove();
  document.getElementById("publish-btn").textContent = "Guardar cambios";
}

async function init() {
  form.elements.closes_at.min = todayIso();
  form.hidden = true;
  loading.hidden = false;
  try {
    const [cities, contracts, levels, job] = await Promise.all([
      getCities(), getContractTypes(), getEducationLevels(), isEdit ? getCompanyJob(jobId) : Promise.resolve(null),
    ]);
    fillCities(cities);
    const contractSelect = form.elements.contract_type_id;
    contractSelect.replaceChildren(new Option("Selecciona el tipo de contrato", ""), ...contracts.map((c) => new Option(c.name, c.id)));
    levels.forEach((l) => form.elements.min_education_id.append(new Option(l.name, l.id)));
    if (job) {
      fillJob(job);
      setupEditMode(job);
    }
    form.hidden = false;
  } catch (err) {
    showError(err.status === 404 ? "No encontramos esta vacante. Puede que haya sido eliminada." : err.message);
  } finally {
    loading.hidden = true;
  }
  syncModality();
  updateCounters();
  updateSalaryPreview();
  renderSkills();
  dirty = false;
}

if (allowed) init();
