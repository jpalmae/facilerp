/* ==============================================================================
   FacilERP — Form Enhancements

   Auto-initializes Tom Select (searchable dropdowns) and Flatpickr (date pickers)
   on all WTForms-rendered fields. Works with both initial page load and HTMX
   dynamically-loaded content.
   ============================================================================== */

(function () {
  "use strict";

  // ── Tom Select — Searchable <select> dropdowns ────────────────────────────
  // Applied to all <select> that are NOT multiple and NOT [data-no-search]

  const TOM_SELECT_OPTS = {
    allowEmptyOption: true,
    placeholder: "Seleccionar…",
    noResultsText: "Sin resultados",
    searchingText: "Buscando…",
    create: false,
    maxOptions: null,
  };

  function initTomSelect(root) {
    const selects = root.querySelectorAll(
      'select:not([multiple]):not(.tomloaded):not([data-no-search])'
    );
    selects.forEach(function (sel) {
      try {
        if (typeof TomSelect !== "undefined") {
          new TomSelect(sel, {
            ...TOM_SELECT_OPTS,
            placeholder:
              sel.querySelector('option[value=""]')?.textContent ||
              TOM_SELECT_OPTS.placeholder,
          });
        }
        sel.classList.add("tomloaded");
      } catch (e) {
        console.warn("TomSelect init failed for", sel.name, e);
      }
    });
  }

  // ── Flatpickr — Consistent date pickers ──────────────────────────────────
  // Applied to all <input type="date"> and [data-datepicker]

  const FLATPICKR_OPTS = {
    dateFormat: "Y-m-d",
    allowInput: true,
    locale: "es",
    disableMobile: true,
    altInput: true,
    altFormat: "d/m/Y",
  };

  function initFlatpickr(root) {
    const dateInputs = root.querySelectorAll(
      'input[type="date"]:not(.fploaded), [data-datepicker]:not(.fploaded)'
    );
    dateInputs.forEach(function (inp) {
      try {
        if (typeof flatpickr !== "undefined") {
          const opts = { ...FLATPICKR_OPTS };
          if (inp.value) {
            opts.defaultDate = inp.value;
          }
          flatpickr(inp, opts);
        }
        inp.classList.add("fploaded");
      } catch (e) {
        console.warn("Flatpickr init failed for", inp.name, e);
      }
    });
  }

  // ── Init all enhancements ────────────────────────────────────────────────

  function initAll(root) {
    if (!root) root = document;
    initTomSelect(root);
    initFlatpickr(root);
  }

  // Initial page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initAll();
    });
  } else {
    initAll();
  }

  // HTMX dynamic content
  document.body.addEventListener("htmx:afterSettle", function (e) {
    initAll(e.detail.elt || document);
  });

  // Expose for manual use
  window.facilERPInitForms = initAll;
})();
