/* Modo claro / oscuro.
   Es un script CLÁSICO (no módulo) para ejecutarse en el <head> y evitar el
   "parpadeo" de color al cargar. Uso: <script src="...utils/theme.js"></script>
   y un botón con el atributo  data-theme-toggle  */
(function () {
  var KEY = "theme";

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function systemPrefersDark() {
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  function current() {
    var saved = stored();
    if (saved === "light" || saved === "dark") return saved;
    return systemPrefersDark() ? "dark" : "light";
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].textContent = theme === "dark" ? "☀️" : "🌙";
      buttons[i].setAttribute(
        "aria-label",
        theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
      );
    }
  }

  function toggle() {
    var next = current() === "dark" ? "light" : "dark";
    try { localStorage.setItem(KEY, next); } catch (e) { /* sin almacenamiento */ }
    apply(next);
  }

  // Aplicar de inmediato (antes de pintar la página)
  document.documentElement.setAttribute("data-theme", current());

  document.addEventListener("DOMContentLoaded", function () {
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) buttons[i].addEventListener("click", toggle);
    apply(current());
  });
})();