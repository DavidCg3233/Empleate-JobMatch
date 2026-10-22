import { parseCv, registerApplicant, registerCompany } from "../api/authApi.js";
import { getCities, getEducationLevels, getIndustries, getLanguages } from "../api/catalogApi.js";
import { createProfileEditor } from "../components/profileEditor.js";
import { redirectByRole, saveSession } from "../utils/auth.js";
import {
  emailError, minLengthError, nitError, passwordError, phoneError, requiredError, websiteError,
} from "../utils/validators.js";

const forms = {
  aspirante: document.getElementById("form-applicant"),
  empresa: document.getElementById("form-company"),
};
const roleButtons = document.querySelectorAll(".role-option");
const errorBox = document.getElementById("error-box");
const successBox = document.getElementById("success-box");
const profileEditor = createProfileEditor(document.getElementById("profile-editor"));

// Hoja de vida
const MAX_CV_MB = 5;
const CV_EXTENSIONS = ["pdf", "docx", "odt", "rtf", "txt"];
const IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "heic", "gif"];
const cvInput = document.getElementById("cv-file");
const cvDrop = document.getElementById("cv-drop");
const cvStatus = document.getElementById("cv-status");
const cvRemove = document.getElementById("cv-remove");
let cvUploadId = null; // id temporal que devuelve el backend; se envía al registrarse

// ---------- Reglas de validación por rol: [campo, función(valor, todos) => mensaje] ----------
const ACCOUNT_RULES = [
  ["email", (v) => emailError(v)],
  ["password", (v) => passwordError(v)],
  ["confirm_password", (v, all) => (v === all.password ? "" : "Las contraseñas no coinciden.")],
  ["terms", (v) => (v ? "" : "Debes aceptar los términos y condiciones.")],
];

const RULES = {
  aspirante: [
    ["first_name", minLengthError("Escribe tu nombre.", 2)],
    ["last_name", minLengthError("Escribe tu apellido.", 2)],
    ["phone", phoneError],
    ["city_id", requiredError("Selecciona tu ciudad.")],
    ...ACCOUNT_RULES,
  ],
  empresa: [
    ["name", minLengthError("Escribe el nombre de la empresa.", 2)],
    ["tax_id", nitError],
    ["industry_id", requiredError("Selecciona el sector.")],
    ["size", requiredError("Selecciona el tamaño.")],
    ["city_id", requiredError("Selecciona la ciudad.")],
    ["website", websiteError],
    ["contact_name", minLengthError("Escribe el nombre de la persona de contacto.", 2)],
    ["contact_phone", phoneError],
    ["contact_email", (v) => (v ? emailError(v) : "")], // opcional
    ...ACCOUNT_RULES,
  ],
};

// ---------- Utilidades de interfaz ----------
let currentRole = "aspirante";

function showGlobalError(message) {
  successBox.classList.add("hidden");
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  errorBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideMessages() {
  errorBox.classList.add("hidden");
  successBox.classList.add("hidden");
}

function setFieldError(form, name, message) {
  const input = form.elements[name];
  const box = form.querySelector(`[data-error-for="${name}"]`);
  if (box) {
    box.textContent = message || "";
    box.classList.toggle("hidden", !message);
  }
  if (input && input.type !== "checkbox") input.classList.toggle("is-invalid", Boolean(message));
}

function getValues(form) {
  const values = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") values[el.name] = el.checked;
    else if (el.type === "password") values[el.name] = el.value; // la contraseña no se recorta
    else values[el.name] = el.value.trim();
  }
  return values;
}

function validate(form, role) {
  const values = getValues(form);
  let firstInvalid = null;
  for (const [name, check] of RULES[role]) {
    const message = check(values[name], values);
    setFieldError(form, name, message);
    if (message && !firstInvalid) firstInvalid = form.elements[name];
  }
  if (firstInvalid) firstInvalid.focus();
  return !firstInvalid;
}

function buildPayload(role, v) {
  const orNull = (x) => (x ? x : null);
  if (role === "aspirante") {
    return {
      first_name: v.first_name,
      last_name: v.last_name,
      email: v.email,
      password: v.password,
      phone: orNull(v.phone),
      city_id: Number(v.city_id),
      accept_terms: v.terms,
      cv_upload_id: cvUploadId,
      desired_position: orNull(v.desired_position),
      summary: orNull(v.summary),
      ...profileEditor.getData(),
    };
  }
  return {
    name: v.name,
    tax_id: v.tax_id,
    industry_id: Number(v.industry_id),
    size: v.size,
    city_id: Number(v.city_id),
    description: orNull(v.description),
    address: orNull(v.address),
    website: orNull(v.website),
    contact_name: v.contact_name,
    contact_phone: orNull(v.contact_phone),
    contact_email: orNull(v.contact_email),
    email: v.email,
    password: v.password,
    accept_terms: v.terms,
  };
}

// Errores 422 del servidor -> se muestran debajo de cada campo
function applyServerErrors(form, err) {
  const list = err.data?.detail;
  if (!Array.isArray(list)) return false;
  let shown = false;
  for (const item of list) {
    const field = item.loc?.[item.loc.length - 1];
    if (typeof field === "string" && form.elements[field] && form.querySelector(`[data-error-for="${field}"]`)) {
      setFieldError(form, field, String(item.msg).replace(/^Value error, /, ""));
      shown = true;
    }
  }
  // Errores de experiencia/educación/idiomas: se muestra el primero arriba
  if (!shown && list.length) {
    showGlobalError(String(list[0].msg).replace(/^Value error, /, ""));
    return "global";
  }
  return shown;
}

// ---------- Hoja de vida: subir, leer y autocompletar ----------
function setCvStatus(state, message) {
  cvStatus.classList.remove("hidden", "is-success", "is-error");
  if (state === "success") cvStatus.classList.add("is-success");
  if (state === "error") cvStatus.classList.add("is-error");
  const icon = cvStatus.querySelector(".cv-status-icon");
  icon.replaceChildren();
  if (state === "loading") icon.append(Object.assign(document.createElement("span"), { className: "spinner" }));
  else icon.textContent = state === "success" ? "✅" : "⚠️";
  cvStatus.querySelector(".cv-status-text").textContent = message;
  cvRemove.classList.toggle("hidden", state !== "success");
}

const AUTOFILL_FIELDS = ["first_name", "last_name", "email", "phone", "city_id", "desired_position", "summary"];

function autofill(form, data) {
  let count = 0;
  for (const name of AUTOFILL_FIELDS) {
    const input = form.elements[name];
    const value = data[name];
    // Solo se llenan los campos vacíos: no se borra lo que la persona ya escribió
    if (!input || value == null || value === "" || input.value.trim()) continue;
    if (input.tagName === "SELECT" && ![...input.options].some((o) => o.value === String(value))) continue;
    input.value = value;
    input.classList.add("is-autofilled");
    setFieldError(form, name, "");
    count++;
  }
  profileEditor.fill(data);
  return count + data.experiences.length + data.educations.length + data.skills.length + data.languages.length;
}

async function handleCvFile(file) {
  if (!file) return;
  hideMessages();
  const ext = file.name.split(".").pop().toLowerCase();
  if (!CV_EXTENSIONS.includes(ext)) {
    setCvStatus("error", ext === "doc"
      ? "El formato .doc antiguo no es compatible. Guárdalo como .docx o PDF."
      : IMAGE_EXTENSIONS.includes(ext)
        ? "Subiste una imagen. Sube la hoja de vida en PDF o Word para poder leer su texto."
        : "Formatos aceptados: PDF, Word (.docx), OpenDocument (.odt), RTF o texto (.txt).");
    return;
  }
  if (file.size > MAX_CV_MB * 1024 * 1024) {
    setCvStatus("error", `El archivo supera el máximo de ${MAX_CV_MB} MB.`);
    return;
  }

  cvDrop.classList.add("is-loading");
  setCvStatus("loading", `Leyendo "${file.name}"... esto puede tardar unos segundos.`);
  try {
    const result = await parseCv(file);
    cvUploadId = result.cv_upload_id;
    const filled = autofill(forms.aspirante, result.data);
    const how = result.source === "ia" ? "con IA" : "con el lector automático";
    setCvStatus("success", filled
      ? `"${result.original_name}" leída ${how}. Revisa los campos resaltados y corrige lo que haga falta.`
      : `"${result.original_name}" se adjuntó, pero no pudimos extraer datos. Llena el formulario manualmente.`);
  } catch (err) {
    cvUploadId = null;
    setCvStatus("error", err.message);
  } finally {
    cvDrop.classList.remove("is-loading");
    cvInput.value = ""; // permite volver a elegir el mismo archivo
  }
}

cvInput.addEventListener("change", () => handleCvFile(cvInput.files[0]));
cvDrop.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); cvInput.click(); }
});
["dragenter", "dragover"].forEach((type) => cvDrop.addEventListener(type, (e) => {
  e.preventDefault();
  cvDrop.classList.add("is-dragover");
}));
["dragleave", "drop"].forEach((type) => cvDrop.addEventListener(type, () => cvDrop.classList.remove("is-dragover")));
cvDrop.addEventListener("drop", (e) => {
  e.preventDefault();
  handleCvFile(e.dataTransfer.files[0]);
});
cvRemove.addEventListener("click", () => {
  cvUploadId = null;
  cvStatus.classList.add("hidden");
});

function selectRole(role) {
  currentRole = role;
  roleButtons.forEach((btn) => btn.setAttribute("aria-pressed", String(btn.dataset.role === role)));
  Object.entries(forms).forEach(([name, form]) => form.classList.toggle("hidden", name !== role));
  hideMessages();
}

// ---------- Catálogos (ciudades y sectores) ----------
function fillCities(cities) {
  const byDepartment = new Map();
  for (const city of cities) {
    if (!byDepartment.has(city.department)) byDepartment.set(city.department, []);
    byDepartment.get(city.department).push(city);
  }
  document.querySelectorAll('select[data-catalog="cities"]').forEach((select) => {
    select.replaceChildren(new Option("Selecciona una ciudad", ""));
    for (const [department, list] of byDepartment) {
      const group = document.createElement("optgroup");
      group.label = department;
      list.forEach((c) => group.appendChild(new Option(c.name, c.id)));
      select.appendChild(group);
    }
  });
}

function fillIndustries(industries) {
  document.querySelectorAll('select[data-catalog="industries"]').forEach((select) => {
    select.replaceChildren(new Option("Selecciona un sector", ""));
    industries.forEach((i) => select.appendChild(new Option(i.name, i.id)));
  });
}

async function loadCatalogs() {
  try {
    const [cities, industries, educationLevels, languages] = await Promise.all([
      getCities(), getIndustries(), getEducationLevels(), getLanguages(),
    ]);
    fillCities(cities);
    fillIndustries(industries);
    profileEditor.setCatalogs({ educationLevels, languages });
  } catch (err) {
    showGlobalError("No se pudieron cargar las ciudades y sectores. " + err.message);
  }
}

// ---------- Eventos ----------
roleButtons.forEach((btn) => btn.addEventListener("click", () => selectRole(btn.dataset.role)));

document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = btn.parentElement.querySelector("input");
    const hidden = input.type === "password";
    input.type = hidden ? "text" : "password";
    btn.textContent = hidden ? "Ocultar" : "Mostrar";
  });
});

// El botón "Crear cuenta" solo se activa cuando se aceptan los términos y condiciones
function syncTerms(form) {
  const accepted = form.elements.terms.checked;
  form.querySelector('button[type="submit"]').disabled = !accepted;
  form.querySelector("[data-terms-hint]").hidden = accepted;
}

Object.entries(forms).forEach(([role, form]) => {
  // Al escribir, se limpia el error de ese campo
  form.addEventListener("input", (e) => {
    e.target.classList?.remove("is-autofilled");
    if (e.target.name) setFieldError(form, e.target.name, "");
  });
  form.addEventListener("change", (e) => {
    if (e.target.name) setFieldError(form, e.target.name, "");
    if (e.target.name === "terms") syncTerms(form);
  });
  syncTerms(form);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideMessages();
    if (!validate(form, role)) return;
    if (role === "aspirante") {
      const profileError = profileEditor.validate();
      if (profileError) return showGlobalError(profileError);
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Creando cuenta...";

    try {
      const payload = buildPayload(role, getValues(form));
      const data = role === "aspirante" ? await registerApplicant(payload) : await registerCompany(payload);

      saveSession(data);
      successBox.textContent = "¡Cuenta creada! Te estamos llevando a tu espacio...";
      successBox.classList.remove("hidden");
      setTimeout(() => redirectByRole(data.role), 900);
    } catch (err) {
      const applied = err.status === 422 ? applyServerErrors(form, err) : false;
      if (applied === true) {
        showGlobalError("Revisa los campos marcados.");
      } else if (applied === "global") {
        // ya se mostró el mensaje
      } else {
        if (/hoja de vida/i.test(err.message)) { cvUploadId = null; cvStatus.classList.add("hidden"); }
        showGlobalError(err.message);
      }
      submitBtn.textContent = originalText;
      syncTerms(form);
    }
  });
});

// ---------- Inicio ----------
const requested = new URLSearchParams(window.location.search).get("rol");
selectRole(requested === "empresa" ? "empresa" : "aspirante");
loadCatalogs();