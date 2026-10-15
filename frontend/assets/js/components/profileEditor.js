// Editor del perfil profesional del aspirante (experiencia, educación, habilidades, idiomas).
// Se llena automáticamente con los datos de la hoja de vida y el usuario puede corregirlos.
// Todo se construye con createElement/textContent (nunca innerHTML con datos del usuario).

const PROFICIENCY = [
  ["basico", "Básico"], ["intermedio", "Intermedio"], ["avanzado", "Avanzado"], ["nativo", "Nativo"],
];
const MAX_SKILLS = 25;

// ---------- Utilidades ----------
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) if (child != null) node.append(child);
  return node;
}

const thisMonth = () => new Date().toISOString().slice(0, 7);
const toMonth = (iso) => (iso ? String(iso).slice(0, 7) : "");          // "2022-01-01" -> "2022-01"
const toDate = (month) => (month ? `${month}-01` : null);               // "2022-01" -> "2022-01-01"

function field(label, input, { span2 = false } = {}) {
  return el("div", { class: `field${span2 ? " span-2" : ""}` }, el("label", { class: "label" }, label), input);
}

function select(options, value, placeholder) {
  const s = el("select", { class: "select" });
  if (placeholder) s.append(new Option(placeholder, ""));
  for (const [v, text] of options) s.append(new Option(text, v));
  s.value = value ?? "";
  return s;
}

function entryCard(title, onRemove, body) {
  const removeBtn = el("button", { type: "button", class: "btn btn-ghost btn-sm", textContent: "Quitar" });
  const card = el("div", { class: "entry-card" },
    el("div", { class: "entry-head" }, el("strong", { textContent: title }), removeBtn),
    body,
    el("p", { class: "field-error entry-error hidden" }),
  );
  removeBtn.addEventListener("click", () => { card.remove(); onRemove?.(); });
  return card;
}

function setEntryError(card, message) {
  const box = card.querySelector(".entry-error");
  box.textContent = message || "";
  box.classList.toggle("hidden", !message);
  card.classList.toggle("is-invalid", Boolean(message));
}

// =====================================================================
export function createProfileEditor(root) {
  const $ = (sel) => root.querySelector(sel);
  const expList = $("#experience-list");
  const eduList = $("#education-list");
  const langList = $("#language-list");
  const skillBox = $("#skill-chips");
  const skillInput = $("#skill-input");

  let educationLevels = [];  // [{id, name}]
  let languages = [];        // [{id, name}]
  let skills = [];

  // ---------- Experiencia ----------
  function addExperience(data = {}) {
    const position = el("input", { class: "input", maxLength: 150, value: data.position ?? "", placeholder: "Ej: Auxiliar contable" });
    const company = el("input", { class: "input", maxLength: 150, value: data.company_name ?? "", placeholder: "Nombre de la empresa" });
    const start = el("input", { class: "input", type: "month", max: thisMonth(), value: toMonth(data.start_date) });
    const end = el("input", { class: "input", type: "month", max: thisMonth(), value: toMonth(data.end_date) });
    const current = el("input", { type: "checkbox", checked: Boolean(data.is_current) });
    const description = el("textarea", { class: "textarea", maxLength: 1000, value: data.description ?? "",
      placeholder: "Funciones y logros principales (opcional)" });

    const syncCurrent = () => { end.disabled = current.checked; if (current.checked) end.value = ""; };
    current.addEventListener("change", syncCurrent);
    syncCurrent();

    const card = entryCard("Experiencia", null, el("div", { class: "form-grid" },
      field("Cargo", position),
      field("Empresa", company),
      field("Desde", start),
      field("Hasta", end),
      el("label", { class: "checkbox span-2" }, current, el("span", { textContent: "Trabajo aquí actualmente" })),
      field("Descripción", description, { span2: true }),
    ));
    card.getData = () => ({
      position: position.value.trim(), company_name: company.value.trim(),
      start_date: toDate(start.value), end_date: current.checked ? null : toDate(end.value),
      is_current: current.checked, description: description.value.trim() || null,
    });
    card.check = () => {
      const d = card.getData();
      if (d.position.length < 2) return [position, "Escribe el cargo."];
      if (d.company_name.length < 2) return [company, "Escribe el nombre de la empresa."];
      if (!d.start_date) return [start, "Indica desde cuándo trabajaste ahí."];
      if (!d.is_current && d.end_date && d.end_date < d.start_date) return [end, "La fecha final no puede ser anterior a la inicial."];
      return null;
    };
    expList.append(card);
    return card;
  }

  // ---------- Educación ----------
  function addEducation(data = {}) {
    const level = select(educationLevels.map((l) => [l.id, l.name]), data.education_level_id, "Selecciona el nivel");
    const degree = el("input", { class: "input", maxLength: 150, value: data.degree ?? "", placeholder: "Ej: Ingeniería de Sistemas" });
    const institution = el("input", { class: "input", maxLength: 150, value: data.institution ?? "", placeholder: "Universidad, instituto, SENA..." });
    const fieldOfStudy = el("input", { class: "input", maxLength: 150, value: data.field_of_study ?? "", placeholder: "Opcional" });
    const start = el("input", { class: "input", type: "month", max: thisMonth(), value: toMonth(data.start_date) });
    const end = el("input", { class: "input", type: "month", max: thisMonth(), value: toMonth(data.end_date) });

    const card = entryCard("Estudio", null, el("div", { class: "form-grid" },
      field("Nivel", level),
      field("Título", degree),
      field("Institución", institution),
      field("Área de estudio", fieldOfStudy),
      field("Inicio (opcional)", start),
      field("Fin (vacío si está en curso)", end),
    ));
    card.getData = () => ({
      education_level_id: level.value ? Number(level.value) : null,
      degree: degree.value.trim(), institution: institution.value.trim(),
      field_of_study: fieldOfStudy.value.trim() || null,
      start_date: toDate(start.value), end_date: toDate(end.value),
    });
    card.check = () => {
      const d = card.getData();
      if (!d.education_level_id) return [level, "Selecciona el nivel educativo."];
      if (d.degree.length < 2) return [degree, "Escribe el título."];
      if (d.institution.length < 2) return [institution, "Escribe la institución."];
      if (d.start_date && d.end_date && d.end_date < d.start_date) return [end, "La fecha final no puede ser anterior a la inicial."];
      return null;
    };
    eduList.append(card);
    return card;
  }

  // ---------- Idiomas ----------
  function addLanguage(data = {}) {
    const lang = select(languages.map((l) => [l.id, l.name]), data.language_id, "Idioma");
    const level = select(PROFICIENCY, data.proficiency ?? "basico");
    const removeBtn = el("button", { type: "button", class: "btn btn-ghost btn-sm", textContent: "Quitar" });
    const row = el("div", { class: "language-row" }, lang, level, removeBtn);
    removeBtn.addEventListener("click", () => row.remove());
    row.getData = () => ({ language_id: lang.value ? Number(lang.value) : null, proficiency: level.value });
    row.select = lang;
    langList.append(row);
    return row;
  }

  // ---------- Habilidades ----------
  function renderSkills() {
    skillBox.replaceChildren(...skills.map((name, i) => {
      const remove = el("button", { type: "button", class: "chip-remove", textContent: "×", "aria-label": `Quitar ${name}` });
      remove.addEventListener("click", () => { skills.splice(i, 1); renderSkills(); });
      return el("span", { class: "chip chip-removable" }, el("span", { textContent: name }), remove);
    }));
  }

  function addSkill(name) {
    name = String(name || "").trim().slice(0, 100);
    if (!name || skills.length >= MAX_SKILLS) return;
    if (skills.some((s) => s.toLowerCase() === name.toLowerCase())) return;
    skills.push(name);
    renderSkills();
  }

  function addSkillFromInput() {
    skillInput.value.split(",").forEach(addSkill);
    skillInput.value = "";
  }

  skillInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addSkillFromInput(); }  // Enter NO envía el formulario
  });
  $("#add-skill").addEventListener("click", addSkillFromInput);
  $("#add-experience").addEventListener("click", () => addExperience().querySelector("input").focus());
  $("#add-education").addEventListener("click", () => addEducation().querySelector("select").focus());
  $("#add-language").addEventListener("click", () => addLanguage().querySelector("select").focus());

  // Al editar una tarjeta, se limpia su error
  root.addEventListener("input", (e) => { const c = e.target.closest(".entry-card"); if (c) setEntryError(c, ""); });

  // ---------- API pública ----------
  return {
    setCatalogs({ educationLevels: levels = [], languages: langs = [] }) {
      educationLevels = levels;
      languages = langs;
    },

    /** Reemplaza el contenido con los datos extraídos de la hoja de vida. */
    fill(data) {
      expList.replaceChildren();
      eduList.replaceChildren();
      langList.replaceChildren();
      skills = [];
      (data.experiences || []).forEach(addExperience);
      (data.educations || []).forEach(addEducation);
      (data.languages || []).forEach(addLanguage);
      (data.skills || []).forEach(addSkill);
      renderSkills();
    },

    /** Devuelve "" si todo es válido, o un mensaje (y marca la tarjeta con error). */
    validate() {
      if (skillInput.value.trim()) addSkillFromInput();  // habilidad escrita sin presionar Enter
      for (const card of [...expList.children, ...eduList.children]) {
        const problem = card.check();
        setEntryError(card, problem?.[1]);
        if (problem) { problem[0].focus(); return problem[1]; }
      }
      const seen = new Set();
      for (const row of langList.children) {
        const id = row.getData().language_id;
        if (!id) { row.select.focus(); return "Selecciona el idioma o quita esa fila."; }
        if (seen.has(id)) { row.select.focus(); return "Hay un idioma repetido."; }
        seen.add(id);
      }
      return "";
    },

    getData() {
      return {
        experiences: [...expList.children].map((c) => c.getData()),
        educations: [...eduList.children].map((c) => c.getData()),
        languages: [...langList.children].map((r) => r.getData()),
        skills: [...skills],
      };
    },
  };
}
