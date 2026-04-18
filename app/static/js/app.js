/**
 * FacilERP — Main Application JS
 * Sidebar toggle, mobile menu, and initialization
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    document.body.dataset.ready = "true";

    initSidebar();
    initMobileSidebar();
    initTooltips();
  });

  /* ── Sidebar collapse/expand ─────────────────────────────────── */
  function initSidebar() {
    var shell = document.querySelector("[data-app-shell]");
    var toggle = document.querySelector("[data-sidebar-toggle]");
    if (!shell || !toggle) return;

    var expandedOnly = document.querySelectorAll("[data-sidebar-expanded-only]");
    var collapsedOnly = document.querySelectorAll("[data-sidebar-collapsed-only]");
    var storageKey = "facilerp.sidebar.collapsed";

    var collapsed = false;
    try {
      collapsed = window.localStorage.getItem(storageKey) === "true";
    } catch (e) {
      collapsed = false;
    }

    function setCollapsed(state) {
      shell.setAttribute("data-sidebar-collapsed", state ? "true" : "false");
      toggle.setAttribute("aria-label", state ? "Expandir barra lateral" : "Minimizar barra lateral");
      toggle.setAttribute("title", state ? "Expandir barra lateral" : "Minimizar barra lateral");
      toggle.setAttribute("aria-expanded", state ? "false" : "true");
      expandedOnly.forEach(function (el) { el.hidden = state; });
      collapsedOnly.forEach(function (el) { el.hidden = !state; });
    }

    setCollapsed(collapsed);

    toggle.addEventListener("click", function () {
      collapsed = shell.getAttribute("data-sidebar-collapsed") !== "true";
      setCollapsed(collapsed);
      try {
        window.localStorage.setItem(storageKey, collapsed ? "true" : "false");
      } catch (e) { /* ignore */ }
    });
  }

  /* ── Mobile sidebar ──────────────────────────────────────────── */
  function initMobileSidebar() {
    var shell = document.querySelector("[data-app-shell]");
    if (!shell) return;

    var mobileToggle = document.querySelector("[data-mobile-toggle]");
    var mobileClose = document.querySelector("[data-mobile-close]");
    var overlay = document.querySelector("[data-mobile-overlay]");

    function setOpen(open) {
      shell.setAttribute("data-mobile-sidebar-open", open ? "true" : "false");
      if (open) {
        // Focus trap: focus the close button when sidebar opens
        if (mobileClose) mobileClose.focus();
      }
    }

    if (mobileToggle) {
      mobileToggle.addEventListener("click", function () { setOpen(true); });
    }
    if (mobileClose) {
      mobileClose.addEventListener("click", function () { setOpen(false); });
    }
    if (overlay) {
      overlay.addEventListener("click", function () { setOpen(false); });
    }

    // Close on Escape key
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && shell.getAttribute("data-mobile-sidebar-open") === "true") {
        setOpen(false);
        if (mobileToggle) mobileToggle.focus();
      }
    });
  }

  /* ── Tooltips for collapsed sidebar ──────────────────────────── */
  function initTooltips() {
    var shell = document.querySelector("[data-app-shell]");
    if (!shell) return;

    var navLinks = document.querySelectorAll("[data-sidebar-nav-link]");
    navLinks.forEach(function (link) {
      var tooltip = link.querySelector("[data-sidebar-tooltip]");
      if (!tooltip) return;

      link.addEventListener("mouseenter", function () {
        if (shell.getAttribute("data-sidebar-collapsed") !== "true") return;
        tooltip.hidden = false;
      });
      link.addEventListener("mouseleave", function () {
        tooltip.hidden = true;
      });
      link.addEventListener("focus", function () {
        if (shell.getAttribute("data-sidebar-collapsed") !== "true") return;
        tooltip.hidden = false;
      });
      link.addEventListener("blur", function () {
        tooltip.hidden = true;
      });
    });
  }
})();

// ── Theme Toggle ──
(function initTheme() {
  const KEY = "facilerp.theme";
  const html = document.documentElement;
  const saved = localStorage.getItem(KEY);

  if (saved) {
    html.setAttribute("data-theme", saved);
  }

  // Update icon visibility on page load
  updateThemeIcon();
})();

function updateThemeIcon() {
  var isDark = document.documentElement.getAttribute("data-theme") === "dark" ||
    (!document.documentElement.getAttribute("data-theme") &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);

  var lightIcon = document.getElementById("theme-icon-light");
  var darkIcon = document.getElementById("theme-icon-dark");
  if (lightIcon) lightIcon.classList.toggle("hidden", isDark);
  if (darkIcon) darkIcon.classList.toggle("hidden", !isDark);
}

function toggleTheme() {
  var KEY = "facilerp.theme";
  var html = document.documentElement;
  var current = html.getAttribute("data-theme");
  var next = current === "dark" ? "light" : "dark";

  html.setAttribute("data-theme", next);
  localStorage.setItem(KEY, next);
  updateThemeIcon();
}
