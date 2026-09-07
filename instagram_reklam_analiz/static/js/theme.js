(function () {
  'use strict';

  const STORAGE_KEY = 'reklamanaliz-theme';
  const root = document.documentElement;

  function applyTheme(theme) {
    const normalized = theme === 'light' ? 'light' : 'dark';
    root.dataset.theme = normalized;
    root.style.colorScheme = normalized;

    const button = document.getElementById('raThemeToggle');
    if (!button) return;

    const light = normalized === 'light';
    button.setAttribute('aria-pressed', light ? 'true' : 'false');
    button.setAttribute('aria-label', light ? 'Koyu moda geç' : 'Açık moda geç');
    button.title = light ? 'Koyu moda geç' : 'Açık moda geç';

    const icon = button.querySelector('[data-theme-icon]');
    const label = button.querySelector('[data-theme-label]');
    if (icon) icon.className = 'fas ' + (light ? 'fa-moon' : 'fa-sun');
    if (label) label.textContent = light ? 'Koyu' : 'Açık';
  }

  function getStoredTheme() {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return value === 'light' || value === 'dark' ? value : 'dark';
    } catch (_) {
      return 'dark';
    }
  }

  function saveTheme(theme) {
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (_) {}
  }

  // base.html also applies the stored value in <head> to avoid a flash of the wrong theme.
  applyTheme(root.dataset.theme || getStoredTheme());

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(root.dataset.theme || getStoredTheme());

    const button = document.getElementById('raThemeToggle');
    if (!button || button.dataset.themeBound === '1') return;
    button.dataset.themeBound = '1';

    button.addEventListener('click', function () {
      const next = root.dataset.theme === 'light' ? 'dark' : 'light';
      saveTheme(next);
      applyTheme(next);
    });
  });
})();
