/* Onlenco dashboard shell — mobile drawer controller (Prompt 16.6).
 *
 * Progressive enhancement for the Admin (control) and Teacher shells.
 * Markup contract (set in each shell's base.html):
 *   <button data-ds-toggle="#control-sidebar" aria-controls="control-sidebar"
 *           aria-expanded="false"> ... </button>
 *   <div class="ds-overlay" data-ds-overlay></div>
 *   <aside id="control-sidebar" class="control-sidebar ds-drawer"> ... </aside>
 *
 * Desktop (toggle hidden via CSS) is untouched — the sidebar stays in the
 * grid. On mobile the sidebar becomes an off-canvas drawer toggled here.
 * RTL is handled in CSS (drawer slides from the inline-start edge).
 */
(function () {
  "use strict";

  function initDrawer() {
    var toggles = document.querySelectorAll("[data-ds-toggle]");
    if (!toggles.length) return;
    var overlay = document.querySelector("[data-ds-overlay]");

    toggles.forEach(function (btn) {
      var sel = btn.getAttribute("data-ds-toggle");
      var drawer = sel ? document.querySelector(sel) : null;
      if (!drawer) return;

      function isOpen() {
        return drawer.classList.contains("is-open");
      }
      function open() {
        // Desktop guard: the toggle is display:none on desktop, so the drawer
        // must never open there even if open() is invoked programmatically.
        if (getComputedStyle(btn).display === "none") return;
        drawer.classList.add("is-open");
        if (overlay) overlay.classList.add("is-open");
        btn.setAttribute("aria-expanded", "true");
        document.body.classList.add("ds-no-scroll");
        // Move focus to the first focusable item in the drawer.
        var first = drawer.querySelector("a, button");
        if (first) first.focus();
      }
      function close(returnFocus) {
        drawer.classList.remove("is-open");
        if (overlay) overlay.classList.remove("is-open");
        btn.setAttribute("aria-expanded", "false");
        document.body.classList.remove("ds-no-scroll");
        if (returnFocus) btn.focus();
      }
      function toggle() {
        isOpen() ? close(true) : open();
      }

      btn.addEventListener("click", toggle);
      if (overlay) overlay.addEventListener("click", function () { close(false); });

      // Tapping a nav link inside the drawer closes it (mobile navigation).
      drawer.querySelectorAll("a").forEach(function (a) {
        a.addEventListener("click", function () { close(false); });
      });

      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && isOpen()) close(true);
      });

      // If the viewport grows back to desktop (toggle hidden) while the
      // drawer is open, reset state so the sidebar returns to the grid.
      window.addEventListener("resize", function () {
        if (isOpen() && getComputedStyle(btn).display === "none") close(false);
      });
    });
  }

  if (document.readyState !== "loading") initDrawer();
  else document.addEventListener("DOMContentLoaded", initDrawer);
})();
