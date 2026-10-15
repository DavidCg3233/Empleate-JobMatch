// Grupo de chips para filtrar (solo uno activo a la vez).
// const f = createChipFilter(contenedor, [{ value: "", label: "Todas" }, ...], { onChange })
import { el } from "../utils/dom.js";

export function createChipFilter(container, options, { value = "", onChange } = {}) {
  let current = value;
  const buttons = options.map((opt) =>
    el("button", {
      type: "button",
      class: "filter-chip",
      textContent: opt.label,
      onclick: () => {
        if (opt.value === current) return;
        set(opt.value);
        onChange?.(current);
      },
    }),
  );

  function set(newValue) {
    current = newValue;
    buttons.forEach((btn, i) => {
      const active = options[i].value === current;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
  }

  container.replaceChildren(...buttons);
  set(current);
  return {
    get value() { return current; },
    set,
  };
}
