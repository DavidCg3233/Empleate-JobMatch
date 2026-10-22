// Razones de la compatibilidad: a favor (score_reasons) y en contra (score_gaps).
import { el } from "../utils/dom.js";

export const GOOD_MATCH = 60;          // desde aquí la tarjeta destaca "por qué encaja"
export const RECOMMENDED_MIN = 40;     // por debajo, la vacante no sale en las recomendadas

const LABELS = {
  aspirante: { good: "Por qué encaja: ", bad: "Lo que no encaja: ", pros: "A favor", cons: "En contra" },
  empresa: { good: "Por qué encaja: ", bad: "Lo que le falta: ", pros: "A favor", cons: "En contra" },
};

/** Una línea para la tarjeta: con buena compatibilidad, lo que suma; con baja, lo que resta. */
export function cardReason(item, audience = "aspirante") {
  const t = LABELS[audience];
  const good = item.score >= GOOD_MATCH;
  const list = (good ? item.score_reasons : item.score_gaps).slice(0, 2);
  const fallback = good ? item.score_gaps : item.score_reasons; // si no hay de un lado, se muestra el otro
  if (list.length) {
    return el("p", { class: `ai-reason${good ? "" : " is-warning"}` }, el("strong", { textContent: good ? t.good : t.bad }), list.join(" · "));
  }
  if (fallback.length) {
    const showGood = !good;
    return el("p", { class: `ai-reason${showGood ? "" : " is-warning"}` },
      el("strong", { textContent: showGood ? t.good : t.bad }), fallback.slice(0, 2).join(" · "));
  }
  return null;
}

/** Dos listas para el detalle: ✓ a favor y ✗ en contra. */
export function reasonLists(item, audience = "aspirante") {
  const t = LABELS[audience];
  const block = (title, items, icon, cls) => (items.length
    ? el("div", { class: `reason-group ${cls}` },
      el("p", { class: "reason-title", textContent: title }),
      el("ul", { class: "detail-reasons" }, items.map((r) => el("li", {}, el("span", { "aria-hidden": "true", textContent: icon }), " ", r))))
    : null);
  return el("div", { class: "reason-lists" },
    block(t.pros, item.score_reasons, "✓", "is-pro"),
    block(t.cons, item.score_gaps, "✗", "is-con"),
  );
}
