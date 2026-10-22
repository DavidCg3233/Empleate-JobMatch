// Campo de dinero con formato colombiano mientras se escribe: 3000000 -> "3.000.000".
// HTML:  <div class="money-input"><span class="money-prefix">$</span><input class="input" ...></div>
// const salario = createMoneyInput(input);  salario.value -> 3000000 (número) o null;  salario.value = 2500000;
const MAX_DIGITS = 10; // hasta 9.999.999.999 (lo que admite la base de datos)

export function formatThousands(digits) {
  return String(digits).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function createMoneyInput(input) {
  input.type = "text";
  input.inputMode = "numeric";
  input.autocomplete = "off";

  function reformat() {
    const raw = input.value;
    const caret = input.selectionStart ?? raw.length;
    const digitsBeforeCaret = raw.slice(0, caret).replace(/\D/g, "").length;
    const digits = raw.replace(/\D/g, "").replace(/^0+(?=\d)/, "").slice(0, MAX_DIGITS);
    const formatted = digits ? formatThousands(digits) : "";
    input.value = formatted;

    // Deja el cursor después del mismo número de dígitos (no salta al final al editar en medio)
    let position = 0;
    let seen = 0;
    while (position < formatted.length && seen < digitsBeforeCaret) {
      if (/\d/.test(formatted[position])) seen++;
      position++;
    }
    if (document.activeElement === input) input.setSelectionRange(position, position);
  }

  input.addEventListener("input", reformat);
  reformat();

  return {
    get value() {
      const digits = input.value.replace(/\D/g, "");
      return digits ? Number(digits) : null;
    },
    set value(number) {
      input.value = number === null || number === undefined || number === "" ? "" : formatThousands(Math.round(Number(number)));
    },
  };
}
