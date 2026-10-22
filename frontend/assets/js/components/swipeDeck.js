// Pila de tarjetas para deslizar (tipo Tinder). La usan el aspirante (vacantes) y la empresa (candidatos).
// Derecha / botón ♥ = me interesa · Izquierda / botón ✕ = no me interesa · ↺ = deshacer.
//
// const deck = createSwipeDeck({
//   stage, emptyBox, buttons: { like, nope, undo, info },
//   getId: (item) => item.id,
//   buildCard: (item) => elementoDeLaTarjeta,
//   fetchPage: async (idsEnPantalla) => [items],        // devuelve hasta pageSize elementos nuevos
//   sendDecision: async (item, "like" | "dislike") => resultado,
//   sendUndo: async (item) => {},
//   renderEmpty: ({ fetching, loadError, retry }) => [nodos],
//   openDetail: (item, decide) => {},                    // decide("like" | "dislike")
//   onDecided: (item, action, resultado) => {},          // ej: mostrar "¡Es un match!"
//   messages: { undone: "...", gone: "..." },
// });
// deck.reset();  // carga (o recarga) desde cero
import { showToast } from "./toast.js";

const SWIPE_THRESHOLD = 110; // px que hay que arrastrar para decidir

export function createSwipeDeck(options) {
  const {
    stage, emptyBox, buttons, getId, buildCard, fetchPage, sendDecision, sendUndo,
    renderEmpty, openDetail, onDecided, pageSize = 20, refillAt = 3, messages = {},
  } = options;

  let queue = [];            // queue[0] es la tarjeta de arriba (último hijo del stage)
  let history = [];          // decisiones tomadas, para deshacer
  const cards = new Map();   // id -> elemento
  let busy = false;
  let fetching = false;
  let exhausted = false;
  let loadError = "";
  let token = 0;             // cambia en cada reset: descarta respuestas viejas
  let enabled = false;

  // ---------------- Tarjetas ----------------
  const topCard = () => (queue.length ? cards.get(getId(queue[0])) : null);

  function makeCard(item) {
    const card = buildCard(item);
    card.classList.add("swipe-card");
    cards.set(getId(item), card);
    return card;
  }

  function addToBottom(items) {
    const fresh = items.filter((item) => !queue.some((q) => getId(q) === getId(item)));
    queue.push(...fresh);
    emptyBox.after(...fresh.slice().reverse().map(makeCard)); // el fondo es justo después del recuadro vacío
  }

  function clearCards() {
    cards.forEach((card) => card.remove());
    cards.clear();
    queue = [];
  }

  function resetStamps(card) {
    card.querySelectorAll(".swipe-stamp").forEach((s) => { s.style.opacity = ""; });
  }

  // ---------------- Estado de la pantalla ----------------
  function updateView() {
    const empty = queue.length === 0;
    emptyBox.hidden = !empty;
    if (empty) emptyBox.replaceChildren(...renderEmpty({ fetching, loadError, retry: reset, enabled }));
    buttons.like.disabled = buttons.nope.disabled = buttons.info.disabled = empty || busy;
    buttons.undo.disabled = history.length === 0 || busy;
  }

  // ---------------- Cargar ----------------
  async function fetchMore() {
    const current = token;
    fetching = true;
    loadError = "";
    updateView();
    try {
      const items = await fetchPage(queue.map(getId));
      if (current !== token) return;
      addToBottom(items);
      exhausted = items.length < pageSize;
    } catch (err) {
      if (current !== token) return;
      loadError = err.message;
    } finally {
      if (current === token) {
        fetching = false;
        updateView();
      }
    }
  }

  function maybeLoadMore() {
    if (enabled && !fetching && !exhausted && !loadError && queue.length <= refillAt) fetchMore();
  }

  /** Recarga desde cero. Con { load: false } solo limpia (ej: cuando no hay nada que mostrar). */
  function reset({ load = true, keepHistory = false } = {}) {
    token++;
    fetching = false;
    exhausted = false;
    loadError = "";
    enabled = load;
    if (!keepHistory) history = [];
    clearCards();
    if (load) fetchMore();
    else updateView();
  }

  // ---------------- Decidir ----------------
  async function decide(action) {
    if (busy || !queue.length) return;
    busy = true;
    const current = token;
    const item = queue.shift();
    const id = getId(item);
    const card = cards.get(id);
    card.classList.remove("dragging");
    card.classList.add(action === "like" ? "leave-right" : "leave-left");
    const removeTimer = setTimeout(() => card.remove(), 300);
    updateView();

    try {
      const result = await sendDecision(item, action);
      if (cards.get(id) === card) cards.delete(id);
      if (current === token) history.push(item);
      onDecided?.(item, action, result); // ej: el match se celebra aunque ya haya cambiado el filtro
    } catch (err) {
      clearTimeout(removeTimer);
      if (current !== token) {
        // Mientras se enviaba, se cambió de filtro o de vacante: no se devuelve a la pila nueva
        card.remove();
        showToast(err.message, "error");
      } else if (err.status === 404) {
        // Ya no está disponible (se cerró o se desactivó mientras la veía): se quita
        card.remove();
        cards.delete(id);
        showToast(messages.gone || err.message, "error");
      } else {
        // Se devuelve la tarjeta a la pila
        card.classList.remove("leave-right", "leave-left");
        card.style.transform = "";
        resetStamps(card);
        queue.unshift(item);
        stage.append(card);
        showToast(err.message, "error");
      }
    } finally {
      busy = false;
      updateView();
      maybeLoadMore();
    }
  }

  async function undo() {
    if (busy || !history.length) return;
    busy = true;
    updateView();
    const current = token;
    const item = history[history.length - 1];
    try {
      await sendUndo(item);
      history.pop();
      // Si mientras tanto se cambió de filtro o de vacante, la pila nueva ya la traerá si corresponde
      if (current === token && !queue.some((q) => getId(q) === getId(item))) {
        queue.unshift(item);
        stage.append(makeCard(item));
      }
      showToast(messages.undone || "Listo, volvió a la pila.");
    } catch (err) {
      if (err.status === 404 || err.status === 409) history.pop(); // esta ya no se puede deshacer
      showToast(err.message, "error");
    } finally {
      busy = false;
      updateView();
    }
  }

  function openTopDetail() {
    if (!queue.length || busy) return;
    openDetail(queue[0], decide);
  }

  // ---------------- Arrastrar (mouse y dedo, con Pointer Events) ----------------
  let drag = null;

  stage.addEventListener("pointerdown", (e) => {
    const card = e.target.closest(".swipe-card");
    if (!card || card !== topCard() || busy || e.button !== 0 || e.target.closest("button, a")) return;
    drag = { card, pointerId: e.pointerId, startX: e.clientX, startY: e.clientY, dx: 0, dy: 0 };
    card.setPointerCapture(e.pointerId);
    card.classList.add("dragging");
  });

  stage.addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.pointerId) return;
    drag.dx = e.clientX - drag.startX;
    drag.dy = e.clientY - drag.startY;
    drag.card.style.transform = `translate(${drag.dx}px, ${drag.dy * 0.3}px) rotate(${drag.dx / 18}deg)`;
    const strength = Math.min(1, Math.abs(drag.dx) / SWIPE_THRESHOLD);
    const like = drag.card.querySelector(".swipe-stamp.like");
    const nope = drag.card.querySelector(".swipe-stamp.nope");
    if (like) like.style.opacity = drag.dx > 0 ? strength : 0;
    if (nope) nope.style.opacity = drag.dx < 0 ? strength : 0;
  });

  function endDrag(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    const { card, dx, dy } = drag;
    drag = null;
    if (Math.abs(dx) >= SWIPE_THRESHOLD) {
      decide(dx > 0 ? "like" : "dislike");
      return;
    }
    card.classList.remove("dragging");
    card.style.transform = "";
    resetStamps(card);
    if (e.type === "pointerup" && Math.abs(dx) < 6 && Math.abs(dy) < 6) openTopDetail(); // un toque abre el detalle
  }

  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", endDrag);
  stage.addEventListener("click", (e) => {
    if (e.target.closest('[data-action="detail"]')) openTopDetail();
  });

  // ---------------- Botones y teclado ----------------
  buttons.like.addEventListener("click", () => decide("like"));
  buttons.nope.addEventListener("click", () => decide("dislike"));
  buttons.undo.addEventListener("click", undo);
  buttons.info.addEventListener("click", openTopDetail);

  document.addEventListener("keydown", (e) => {
    const typing = e.target.closest?.("input, textarea, select");
    const modalOpen = document.querySelector(".modal-overlay, .match-overlay");
    if (typing || modalOpen || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "ArrowRight") { e.preventDefault(); decide("like"); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); decide("dislike"); }
    else if (e.key === "ArrowUp") { e.preventDefault(); openTopDetail(); }
    else if (e.key === "Backspace") { e.preventDefault(); undo(); }
  });

  return {
    reset,
    decide,
    get size() { return queue.length; },
  };
}
