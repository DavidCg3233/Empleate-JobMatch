// Empresa: ver y editar el perfil (datos de la empresa y contacto para los matches).
import { getCities, getIndustries } from "../api/catalogApi.js";
import { getCompanyProfile, updateCompanyProfile } from "../api/companyApi.js";
import { renderNav } from "../components/navbar.js";
import { mountChangePassword } from "../components/passwordForm.js";
import { showToast } from "../components/toast.js";
import { requireRole } from "../utils/auth.js";
import { el } from "../utils/dom.js";
import { emailError, minLengthError, phoneError, requiredError, websiteError } from "../utils/validators.js";

const allowed = requireRole("empresa");
if (allowed) renderNav("empresa", "profile");

const form = document.getElementById("profile-form");
const errorBox = document.getElementById("error-box");
const loading = document.getElementById("loading");
const saveBtn = document.getElementById("save-btn");

const FIELDS = ["name", "industry_id", "size", "city_id", "address", "website", "description", "contact_name", "contact_phone", "contact_email"];
const RULES = [
  ["name", minLengthError("Escribe el nombre de la empresa.", 2)],
  ["industry_id", requiredError("Selecciona el sector.")],
  ["city_id", requiredError("Selecciona la ciudad.")],
  ["website", websiteError],
  ["contact_name", minLengthError("Escribe el nombre de la persona de contacto.", 2)],
  ["contact_phone", phoneError],
  ["contact_email", emailError],
];

let dirty = false;

function setFieldError(name, message) {
  const box = form.querySelector(`[data-error-for="${name}"]`);
  if (box) {
    box.textContent = message || "";
    box.classList.toggle("hidden", !message);
  }
  form.elements[name]?.classList.toggle("is-invalid", Boolean(message));
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function updateCounter() {
  const input = form.elements.description;
  form.querySelector('[data-count-for="description"]').textContent = `${input.value.trim().length} / ${input.maxLength} caracteres`;
}

function values() {
  const v = {};
  for (const name of FIELDS) v[name] = form.elements[name].value.trim();
  return v;
}

function validate(v) {
  let first = null;
  for (const [name, check] of RULES) {
    const message = check(v[name]);
    setFieldError(name, message);
    if (message && !first) first = name;
  }
  if (first) form.elements[first].focus();
  return !first;
}

function fill(profile) {
  for (const name of FIELDS) form.elements[name].value = profile[name] ?? "";
  document.getElementById("tax_id").value = profile.tax_id;
  document.getElementById("account_email").value = profile.account_email;
  updateCounter();
}

function fillCities(cities) {
  const select = form.elements.city_id;
  const byDepartment = new Map();
  for (const city of cities) {
    if (!byDepartment.has(city.department)) byDepartment.set(city.department, []);
    byDepartment.get(city.department).push(city);
  }
  select.replaceChildren(new Option("Selecciona una ciudad", ""));
  for (const [department, list] of byDepartment) {
    const group = el("optgroup", { label: department });
    list.forEach((c) => group.append(new Option(c.name, c.id)));
    select.append(group);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.classList.add("hidden");
  const v = values();
  if (!validate(v)) return;

  saveBtn.disabled = true;
  saveBtn.textContent = "Guardando...";
  try {
    const orNull = (x) => (x ? x : null);
    const updated = await updateCompanyProfile({
      name: v.name,
      industry_id: Number(v.industry_id),
      size: v.size,
      city_id: Number(v.city_id),
      address: orNull(v.address),
      website: orNull(v.website),
      description: orNull(v.description),
      contact_name: v.contact_name,
      contact_phone: orNull(v.contact_phone),
      contact_email: v.contact_email,
    });
    fill(updated);
    dirty = false;
    const navName = document.querySelector(".nav-user-name");
    if (navName) navName.textContent = updated.name;
    showToast("Perfil actualizado.", "success");
  } catch (err) {
    const list = err.data?.detail;
    if (err.status === 422 && Array.isArray(list)) {
      for (const item of list) {
        const field = item.loc?.[item.loc.length - 1];
        if (typeof field === "string" && FIELDS.includes(field)) setFieldError(field, String(item.msg).replace(/^Value error, /, ""));
      }
      showError("Revisa los campos marcados.");
    } else {
      showError(err.message);
    }
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Guardar cambios";
  }
});

form.addEventListener("input", (e) => {
  dirty = true;
  if (e.target.name) setFieldError(e.target.name, "");
  if (e.target.name === "description") updateCounter();
});
form.addEventListener("change", (e) => {
  dirty = true;
  if (e.target.name) setFieldError(e.target.name, "");
});
window.addEventListener("beforeunload", (e) => {
  if (dirty) { e.preventDefault(); e.returnValue = ""; }
});

async function init() {
  try {
    const [profile, cities, industries] = await Promise.all([getCompanyProfile(), getCities(), getIndustries()]);
    fillCities(cities);
    form.elements.industry_id.replaceChildren(new Option("Selecciona un sector", ""), ...industries.map((i) => new Option(i.name, i.id)));
    fill(profile);
    form.hidden = false;
    document.getElementById("password-section").hidden = false;
    mountChangePassword(document.getElementById("password-box"));
  } catch (err) {
    showError(err.message);
  } finally {
    loading.hidden = true;
  }
}

if (allowed) init();
