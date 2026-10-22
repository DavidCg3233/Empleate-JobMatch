// Autocompletado de habilidades y herramientas con el catálogo del backend.
// attachSkillAutocomplete(input, { onSelect: (nombre) => {...}, getExisting: () => ["Python", ...] })
// Flechas ↑ ↓ para moverse, Enter para elegir, Escape para cerrar. Si no se elige ninguna sugerencia,
// Enter sigue funcionando como antes (agrega lo que se escribió).
import { searchSkills } from "../api/catalogApi.js";
import { el } from "../utils/dom.js";

const CATEGORY_LABEL = { tecnica: "Técnica", herramienta: "Herramienta", blanda: "Blanda" };
const cache = new Map();
let count = 0;

export function attachSkillAutocomplete(input, { onSelect, getExisting = () => [] }) {
  const listId = `skill-suggestions-${++count}`;
  const list = el("ul", { class: "autocomplete-list", id: listId, role: "listbox", hidden: true });
  input.parentElement.classList.add("autocomplete-host");
  input.insertAdjacentElement("afterend", list);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", listId);
  input.setAttribute("autocomplete", "off");

  let items = [];
  let active = -1;
  let timer = null;
  let token = 0;

  const term = () => input.value.split(",").pop().trim(); // si escribe "Excel, Pyt" se busca "Pyt"

  function close() {
    list.hidden = true;
    list.replaceChildren();
    items = [];
    active = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function highlight(index) {
    active = index;
    [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === index)));
    if (index >= 0) {
      input.setAttribute("aria-activedescendant", `${listId}-${index}`);
      list.children[index].scrollIntoView({ block: "nearest" });
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function choose(index) {
    const item = items[index];
    if (!item) return;
    const before = input.value.split(",").slice(0, -1).join(",");
    input.value = before; // lo anterior a la última coma lo procesa quien usa el componente
    close();
    onSelect(item.name);
    input.focus();
  }

  function render(results) {
    const existing = new Set(getExisting().map((s) => s.toLowerCase()));
    items = results.filter((r) => !existing.has(r.name.toLowerCase()));
    if (!items.length) return close();
    list.replaceChildren(...items.map((item, i) => el("li", {
      id: `${listId}-${i}`, role: "option", "aria-selected": "false", class: "autocomplete-item",
      onmousedown: (e) => { e.preventDefault(); choose(i); }, // mousedown: antes de que el campo pierda el foco
    }, el("span", { textContent: item.name }),
    item.category ? el("span", { class: `autocomplete-tag tag-${item.category}`, textContent: CATEGORY_LABEL[item.category] }) : null)));
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    highlight(-1);
  }

  async function search() {
    const q = term();
    if (!q) return close();
    const key = q.toLowerCase();
    const current = ++token;
    try {
      if (!cache.has(key)) cache.set(key, await searchSkills(q));
      if (current === token && term().toLowerCase() === key) render(cache.get(key));
    } catch {
      close(); // sin sugerencias igual se puede escribir la habilidad
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(search, 150);
  });
  input.addEventListener("blur", () => setTimeout(close, 100));
  input.addEventListener("focus", () => { if (term()) search(); });

  // Fase de captura: se ejecuta antes que el manejador de Enter de quien usa el componente
  input.addEventListener("keydown", (e) => {
    if (list.hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); highlight((active + 1) % items.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); highlight(active <= 0 ? items.length - 1 : active - 1); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); e.stopImmediatePropagation(); choose(active); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === "Tab") close();
  }, true);

  return { close };
}
