// Sección "Análisis con IA" para las ventanas de detalle.
// aiAnalysisSection(() => getJobAnalysis(id), "aspirante")  -> elemento (se oculta solo si la IA no está activa)
// Se pide con un botón (cada análisis nuevo tiene costo); después sale de la caché al instante.
import { getMatchingStatus } from "../api/matchingApi.js";
import { el } from "../utils/dom.js";
import { formatDate, scoreClass } from "../utils/format.js";

const TEXT = {
  aspirante: { pros: "✅ Por qué encajas", cons: "❌ Por qué no encajas del todo", extra: "💡 Consejo" },
  empresa: { pros: "✅ Por qué encaja", cons: "❌ Por qué no encaja del todo", extra: "🗣️ Preguntas para la entrevista" },
};

function list(items, icon) {
  return el("ul", { class: "ai-list" }, items.map((item) => el("li", {}, el("span", { "aria-hidden": "true", textContent: icon }), " ", item)));
}

function renderResult(box, result, audience) {
  const t = TEXT[audience];
  const extra = audience === "aspirante"
    ? (result.advice ? el("p", { class: "ai-advice", textContent: result.advice }) : null)
    : (result.interview_questions.length ? list(result.interview_questions, "❓") : null);

  box.replaceChildren(
    el("div", { class: "ai-head" },
      el("span", { class: `score-badge score-inline ${scoreClass(result.score)}`, title: "Puntaje de la IA", textContent: `${result.score}%` }),
      el("p", { class: "ai-summary", textContent: result.summary }),
    ),
    result.strengths.length ? el("div", { class: "reason-group is-pro" }, el("p", { class: "reason-title", textContent: t.pros }), list(result.strengths, "✓")) : null,
    result.gaps.length ? el("div", { class: "reason-group is-con" }, el("p", { class: "reason-title", textContent: t.cons }), list(result.gaps, "✗")) : null,
    extra ? el("div", {}, el("p", { class: "reason-title", textContent: t.extra }), extra) : null,
    el("p", { class: "hint ai-note", textContent: `Generado con IA${result.generated_at ? ` el ${formatDate(result.generated_at)}` : ""}. Puede contener errores: úsalo como apoyo, no como decisión final.` }),
  );
}

export function aiAnalysisSection(loader, audience = "aspirante") {
  const box = el("div", { class: "ai-body" });
  const section = el("section", { class: "detail-section ai-analysis", hidden: true },
    el("h3", { class: "card-section-title", textContent: "✨ Análisis con IA" }),
    box,
  );

  async function run(button) {
    if (button) button.disabled = true;
    box.replaceChildren(el("p", { class: "ai-loading" }, el("span", { class: "spinner", "aria-hidden": "true" }), " Analizando la compatibilidad..."));
    try {
      renderResult(box, await loader(), audience);
    } catch (err) {
      const retry = el("button", { type: "button", class: "btn btn-outline btn-sm", textContent: "Reintentar" });
      retry.addEventListener("click", () => run(retry));
      box.replaceChildren(el("p", { class: "text-muted", textContent: err.message }), retry);
    }
  }

  getMatchingStatus().then((status) => {
    if (!status.analysis) return; // sin IA configurada, la sección no aparece
    const start = el("button", { type: "button", class: "btn btn-secondary btn-sm", textContent: "Analizar con IA" });
    start.addEventListener("click", () => run(start));
    box.replaceChildren(
      el("p", { class: "hint", textContent: audience === "aspirante"
        ? "La IA revisa tu perfil frente a esta vacante: por qué encajas, qué te falta y un consejo."
        : "La IA revisa el perfil frente a tu vacante: fortalezas, lo que le falta y preguntas para la entrevista." }),
      start,
    );
    section.hidden = false;
  });

  return section;
}
