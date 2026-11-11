// Etapa del proceso después del match: barra de pasos (aspirante y empresa) y selector (empresa).
import { el } from "../utils/dom.js";
import { formatDate } from "../utils/format.js";

// Posición de cada etapa en la barra. Seleccionado y descartado comparten el último paso (el resultado).
const STEP_INDEX = { match: 0, en_revision: 1, entrevista: 2, seleccionado: 3, descartado: 3 };

/** Opciones del selector de la empresa, en orden. */
export const STAGE_OPTIONS = [
  { value: "match", label: "Match (sin iniciar)" },
  { value: "en_revision", label: "En revisión" },
  { value: "entrevista", label: "Entrevista" },
  { value: "seleccionado", label: "Seleccionado" },
  { value: "descartado", label: "Descartado" },
];

const MESSAGES = {
  aspirante: {
    match: "La empresa todavía no ha iniciado el proceso con tu perfil.",
    en_revision: "La empresa está revisando tu perfil.",
    entrevista: "Estás en proceso de entrevista. Revisa tu correo y tu teléfono.",
    seleccionado: "¡Felicitaciones! La empresa te seleccionó para esta vacante.",
    descartado: "La empresa decidió continuar con otros perfiles. ¡Sigue buscando!",
  },
  empresa: {
    match: "Aún no inicias el proceso con este aspirante.",
    en_revision: "Estás revisando el perfil de este aspirante.",
    entrevista: "El aspirante está en proceso de entrevista.",
    seleccionado: "Seleccionaste a este aspirante.",
    descartado: "Descartaste a este aspirante para esta vacante.",
  },
};

/** Nombre de la etapa. Para el aspirante, "descartado" se muestra como "No seleccionado". */
export function stageLabel(stage, audience = "aspirante") {
  if (stage === "descartado") return audience === "aspirante" ? "No seleccionado" : "Descartado";
  return STAGE_OPTIONS.find((o) => o.value === stage)?.label.replace(" (sin iniciar)", "") || "Match";
}

/** Clase de color de la insignia según la etapa. */
export function stageBadgeClass(stage) {
  if (stage === "seleccionado") return "badge badge-success";
  if (stage === "descartado") return "badge badge-danger";
  return "badge badge-primary";
}

/** Barra de pasos: Match → En revisión → Entrevista → Resultado. */
export function stageBar(stage = "match", audience = "aspirante", updatedAt = null) {
  const current = STEP_INDEX[stage] ?? 0;
  const result = stage === "seleccionado" || stage === "descartado" ? stageLabel(stage, audience) : "Resultado";
  const steps = ["Match", "En revisión", "Entrevista", result];
  const outcome = stage === "seleccionado" ? " is-selected" : stage === "descartado" ? " is-rejected" : "";

  return el("div", { class: `stage-bar${outcome}`, dataset: { stage } },
    el("ol", { class: "stage-steps", "aria-label": `Etapa del proceso: ${stageLabel(stage, audience)}` },
      ...steps.map((label, i) => el("li", {
        class: `stage-step${i < current ? " is-done" : ""}${i === current ? " is-current" : ""}`,
        "aria-current": i === current ? "step" : null,
      },
        el("span", { class: "stage-dot", "aria-hidden": "true", textContent: i < current ? "✓" : String(i + 1) }),
        el("span", { class: "stage-label", textContent: label }),
      )),
    ),
    el("p", { class: "stage-message" },
      MESSAGES[audience][stage] || "",
      updatedAt ? el("span", { class: "hint", textContent: ` · Actualizado el ${formatDate(updatedAt)}` }) : null,
    ),
  );
}
