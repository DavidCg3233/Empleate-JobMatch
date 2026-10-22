// Aspirante: ver y administrar su perfil, reemplazar la hoja de vida y cambiar la contraseña.
import { downloadMyCv, getApplicantProfile, updateApplicantProfile, uploadApplicantCv } from "../api/applicantApi.js";
import { getCities, getEducationLevels, getLanguages } from "../api/catalogApi.js";
import { createMoneyInput } from "../components/moneyInput.js";
import { renderApplicantNav } from "../components/navbar.js";
import { mountChangePassword } from "../components/passwordForm.js";
import { createProfileEditor } from "../components/profileEditor.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { formatDate } from "../utils/format.js";
import { minLengthError, phoneError } from "../utils/validators.js";

const allowed = requireRole("aspirante");
if (allowed) renderApplicantNav("profile");

const MAX_CV_MB = 5;
const CV_EXTENSIONS = ["pdf", "docx", "odt", "rtf", "txt"];

const form = document.getElementById("profile-form");
const errorBox = document.getElementById("error-box");
const saveBtn = document.getElementById("save-btn");
const dirtyHint = document.getElementById("dirty-hint");
const cvInput = document.getElementById("cv-file");
const cvDrop = document.getElementById("cv-drop");
const cvStatus = document.getElementById("cv-status");
const cvReview = document.getElementById("cv-review");
const cvCurrent = document.getElementById("cv-current");
const editor = createProfileEditor(document.getElementById("profile-editor"));
const salary = createMoneyInput(form.elements.desired_salary_min);

let dirty = false;
let saving = false;

function setDirty(value) {
  dirty = value;
  dirtyHint.hidden = !value;
}

// =====================================================================
// Mensajes y errores
// =====================================================================
function setFieldError(name, message) {
  const box = form.querySelector(`[data-error-for="${name}"]`);
  if (box) {
    box.textContent = message || "";
    box.classList.toggle("hidden", !message);
  }
  form.elements[name]?.classList?.toggle("is-invalid", Boolean(message));
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function updateCounter() {
  const input = form.elements.summary;
  form.querySelector('[data-count-for="summary"]').textContent = `${input.value.trim().length} / ${input.maxLength} caracteres`;
}

function renderCompletion(profile) {
  const box = document.getElementById("completion");
  box.className = `alert ${profile.profile_completed ? "alert-success" : "alert-info"}`;
  box.textContent = profile.profile_completed
    ? "✅ Tu perfil está completo. ¡Así las empresas te encuentran más fácil!"
    : "💡 Completa tu perfil (cargo que buscas, habilidades y experiencia o estudios) para aparecer como sugerido ante las empresas.";
}

// =====================================================================
// Llenar el formulario
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

function renderCvCurrent(cv) {
  if (!cv) {
    cvCurrent.replaceChildren(el("p", { class: "text-muted", textContent: "Aún no has subido tu hoja de vida." }));
    return;
  }
  const download = el("button", { type: "button", class: "btn btn-outline btn-sm", textContent: "Descargar" });
  download.addEventListener("click", async () => {
    download.disabled = true;
    try { await downloadMyCv(); } catch (err) { showToast(err.message, "error"); } finally { download.disabled = false; }
  });
  cvCurrent.replaceChildren(el("div", { class: "row-between" },
    el("div", {},
      el("strong", { textContent: `📄 ${cv.original_name}` }),
      cv.uploaded_at ? el("p", { class: "hint", textContent: `Subida el ${formatDate(cv.uploaded_at)}` }) : null,
    ),
    download,
  ));
}

function fill(profile) {
  const set = (name, value) => { form.elements[name].value = value ?? ""; };
  set("first_name", profile.first_name);
  set("last_name", profile.last_name);
  set("phone", profile.phone);
  set("city_id", profile.city_id);
  set("desired_position", profile.desired_position);
  set("summary", profile.summary);
  set("desired_modality", profile.desired_modality);
  salary.value = profile.desired_salary_min;
  form.elements.search_status.checked = profile.search_status === "buscando_empleo";
  form.elements.willing_to_relocate.checked = profile.willing_to_relocate;
  document.getElementById("account_email").value = profile.account_email;
  editor.fill({
    experiences: profile.experiences,
    educations: profile.educations,
    skills: profile.skills,
    languages: profile.languages,
  });
  updateCounter();
  renderCompletion(profile);
  renderCvCurrent(profile.cv);
}

// =====================================================================
// Guardar
// =====================================================================
function validate() {
  const v = (name) => form.elements[name].value.trim();
  const checks = [
    ["first_name", minLengthError("Escribe tu nombre.", 2)(v("first_name"))],
    ["last_name", minLengthError("Escribe tu apellido.", 2)(v("last_name"))],
    ["phone", phoneError(v("phone"))],
  ];
  checks.forEach(([name, message]) => setFieldError(name, message));
  const first = checks.find(([, message]) => message);
  if (first) {
    form.elements[first[0]].focus();
    return false;
  }
  const problem = editor.validate();
  if (problem) {
    showError(problem);
    return false;
  }
  return true;
}

function payload() {
  const v = (name) => form.elements[name].value.trim();
  return {
    first_name: v("first_name"),
    last_name: v("last_name"),
    phone: v("phone") || null,
    city_id: v("city_id") ? Number(v("city_id")) : null,
    desired_position: v("desired_position") || null,
    summary: v("summary") || null,
    search_status: form.elements.search_status.checked ? "buscando_empleo" : "sin_busqueda_activa",
    desired_salary_min: salary.value,
    desired_modality: v("desired_modality") || null,
    willing_to_relocate: form.elements.willing_to_relocate.checked,
    ...editor.getData(),
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (saving) return;
  errorBox.classList.add("hidden");
  if (!validate()) return;

  saving = true;
  saveBtn.disabled = true;
  saveBtn.textContent = "Guardando...";
  try {
    const profile = await updateApplicantProfile(payload());
    fill(profile);
    setDirty(false);
    const navName = document.querySelector(".nav-user-name");
    if (navName) navName.textContent = `${profile.first_name} ${profile.last_name}`;
    showToast("Perfil guardado.", "success");
  } catch (err) {
    const list = err.data?.detail;
    if (err.status === 422 && Array.isArray(list)) {
      let shown = false;
      for (const item of list) {
        const field = item.loc?.[item.loc.length - 1];
        const message = String(item.msg).replace(/^Value error, /, "");
        if (typeof field === "string" && form.querySelector(`[data-error-for="${field}"]`)) { setFieldError(field, message); shown = true; }
        else if (!shown) { showError(message); shown = true; }
      }
    } else {
      showError(err.message);
    }
  } finally {
    saving = false;
    saveBtn.disabled = false;
    saveBtn.textContent = "Guardar perfil";
  }
});

// =====================================================================
// Hoja de vida nueva: se sube, se muestra lo que se leyó y la persona decide si lo usa
// =====================================================================
function setCvStatus(state, message) {
  cvStatus.classList.remove("hidden", "is-success", "is-error");
  if (state === "success") cvStatus.classList.add("is-success");
  if (state === "error") cvStatus.classList.add("is-error");
  const icon = cvStatus.querySelector(".cv-status-icon");
  icon.replaceChildren();
  if (state === "loading") icon.append(el("span", { class: "spinner" }));
  else icon.textContent = state === "success" ? "✅" : "⚠️";
  cvStatus.querySelector(".cv-status-text").textContent = message;
}

function mergeLanguages(current, parsed) {
  const order = { basico: 1, intermedio: 2, avanzado: 3, nativo: 4 };
  const byId = new Map(current.map((l) => [l.language_id, l]));
  for (const lang of parsed) {
    const existing = byId.get(lang.language_id);
    if (!existing || order[lang.proficiency] > order[existing.proficiency]) byId.set(lang.language_id, lang);
  }
  return [...byId.values()];
}

function applyParsed(data) {
  const current = editor.getData();
  const fillIfEmpty = (name, value) => {
    const input = form.elements[name];
    if (value && !input.value.trim()) input.value = value;
  };
  fillIfEmpty("phone", data.phone);
  fillIfEmpty("city_id", data.city_id);
  fillIfEmpty("desired_position", data.desired_position);
  fillIfEmpty("summary", data.summary);

  const skills = [...current.skills];
  for (const skill of data.skills) {
    if (!skills.some((s) => s.toLowerCase() === skill.toLowerCase())) skills.push(skill);
  }
  editor.fill({
    experiences: data.experiences.length ? data.experiences : current.experiences,
    educations: data.educations.length ? data.educations : current.educations,
    skills: skills.slice(0, 40),
    languages: mergeLanguages(current.languages, data.languages),
  });
  updateCounter();
  setDirty(true);
}

function renderReview(result) {
  const { data } = result;
  const found = [
    data.experiences.length && `${data.experiences.length} experiencia(s)`,
    data.educations.length && `${data.educations.length} estudio(s)`,
    data.skills.length && `${data.skills.length} habilidad(es)`,
    data.languages.length && `${data.languages.length} idioma(s)`,
  ].filter(Boolean);

  const useBtn = el("button", { type: "button", class: "btn btn-primary btn-sm", textContent: "Usar estos datos en mi perfil" });
  const skipBtn = el("button", { type: "button", class: "btn btn-ghost btn-sm", textContent: "Solo guardar el archivo" });
  useBtn.addEventListener("click", () => {
    applyParsed(data);
    cvReview.hidden = true;
    showToast("Listo. Revisa los datos y presiona \"Guardar perfil\".", "success", 5000);
    form.querySelector("#profile-editor").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  skipBtn.addEventListener("click", () => { cvReview.hidden = true; });

  cvReview.replaceChildren(
    el("p", {}, el("strong", { textContent: "Encontramos en tu nueva hoja de vida: " }),
      found.length ? found.join(", ") : "pocos datos (puede que el archivo tenga un formato difícil de leer)."),
    data.skills.length ? el("div", { class: "chips" }, data.skills.slice(0, 12).map((s) => el("span", { class: "chip", textContent: s }))) : null,
    el("p", { class: "hint", textContent: "Si los usas, reemplazamos tu experiencia y estudios, agregamos las habilidades e idiomas nuevos y completamos los campos vacíos. Nada se guarda hasta que presiones \"Guardar perfil\"." }),
    el("div", { class: "row" }, useBtn, skipBtn),
  );
  cvReview.hidden = false;
}

async function handleCvFile(file) {
  if (!file) return;
  const ext = file.name.split(".").pop().toLowerCase();
  if (!CV_EXTENSIONS.includes(ext)) {
    setCvStatus("error", ext === "doc"
      ? "El formato .doc antiguo no es compatible. Guárdalo como .docx o PDF."
      : "Formatos aceptados: PDF, Word (.docx), OpenDocument (.odt), RTF o texto (.txt).");
    return;
  }
  if (file.size > MAX_CV_MB * 1024 * 1024) {
    setCvStatus("error", `El archivo supera el máximo de ${MAX_CV_MB} MB.`);
    return;
  }
  cvDrop.classList.add("is-loading");
  cvReview.hidden = true;
  setCvStatus("loading", `Leyendo "${file.name}"... esto puede tardar unos segundos.`);
  try {
    const result = await uploadApplicantCv(file);
    renderCvCurrent(result.cv);
    setCvStatus("success", `"${result.cv.original_name}" quedó guardada como tu hoja de vida.`);
    renderReview(result);
  } catch (err) {
    setCvStatus("error", err.message);
  } finally {
    cvDrop.classList.remove("is-loading");
    cvInput.value = "";
  }
}

cvInput.addEventListener("change", () => handleCvFile(cvInput.files[0]));
cvDrop.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); cvInput.click(); }
});
["dragenter", "dragover"].forEach((type) => cvDrop.addEventListener(type, (e) => { e.preventDefault(); cvDrop.classList.add("is-dragover"); }));
["dragleave", "drop"].forEach((type) => cvDrop.addEventListener(type, () => cvDrop.classList.remove("is-dragover")));
cvDrop.addEventListener("drop", (e) => { e.preventDefault(); handleCvFile(e.dataTransfer.files[0]); });

// =====================================================================
// Eventos e inicio
// =====================================================================
form.addEventListener("input", (e) => {
  setDirty(true);
  if (e.target.name) setFieldError(e.target.name, "");
  if (e.target.name === "summary") updateCounter();
});
form.addEventListener("change", () => setDirty(true));
// Botones del editor (agregar/quitar experiencia, habilidades...) también son cambios
document.getElementById("profile-editor").addEventListener("click", (e) => {
  if (e.target.closest("button")) setDirty(true);
});
window.addEventListener("beforeunload", (e) => {
  if (dirty && !saving) { e.preventDefault(); e.returnValue = ""; }
});

async function init() {
  try {
    const [profile, cities, educationLevels, languages] = await Promise.all([
      getApplicantProfile(), getCities(), getEducationLevels(), getLanguages(),
    ]);
    fillCities(cities);
    editor.setCatalogs({ educationLevels, languages });
    fill(profile);
    document.getElementById("profile-content").hidden = false;
    mountChangePassword(document.getElementById("password-box"));
    setDirty(false);
  } catch (err) {
    showError(err.message);
  } finally {
    document.getElementById("loading").hidden = true;
  }
}

if (allowed) init();
