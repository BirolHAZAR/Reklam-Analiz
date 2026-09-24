(function () {
  'use strict';

  const STORAGE_KEY = 'reklamanaliz-theme';
  const root = document.documentElement;

  function parseColor(value) {
    const parts = String(value || '').match(/[\d.]+/g);
    if (!parts || parts.length < 3) return null;
    return [Number(parts[0]), Number(parts[1]), Number(parts[2]), parts[3] === undefined ? 1 : Number(parts[3])];
  }

  function luminance(color) {
    const channels = color.slice(0, 3).map(value => {
      const channel = value / 255;
      return channel <= 0.04045 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
    });
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  }

  function contrast(first, second) {
    const a = luminance(first);
    const b = luminance(second);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  }

  function blend(foreground, background) {
    const alpha = foreground[3] ?? 1;
    return [
      foreground[0] * alpha + background[0] * (1 - alpha),
      foreground[1] * alpha + background[1] * (1 - alpha),
      foreground[2] * alpha + background[2] * (1 - alpha),
      1
    ];
  }

  function inheritedBackground(element) {
    let background = [255, 255, 255, 1];
    const chain = [];
    for (let node = element; node; node = node.parentElement) chain.unshift(node);
    chain.forEach(node => {
      const color = parseColor(getComputedStyle(node).backgroundColor);
      if (color) background = blend(color, background);
    });
    return background;
  }

  function gradientColors(value) {
    const colors = [];
    String(value || '').match(/rgba?\([^)]*\)/g)?.forEach(token => {
      const color = parseColor(token);
      if (color && color[3] > 0.25) colors.push(color);
    });
    return colors;
  }

  function ensureButtonContrast() {
    const selector = [
      'button', 'input[type="button"]', 'input[type="submit"]', 'input[type="reset"]',
      '.btn', '.btn-nav', '[role="button"]', 'a[class*="-btn"]', 'a[class*="button"]'
    ].join(',');
    document.querySelectorAll(selector).forEach(button => {
      button.removeAttribute('data-ra-button-tone');
      button.removeAttribute('data-ra-button-surface');
      if (root.dataset.theme !== 'light') return;
      const style = getComputedStyle(button);
      if (style.display === 'none' || style.visibility === 'hidden') return;
      const foreground = parseColor(style.color);
      if (!foreground) return;
      const fallback = inheritedBackground(button);
      const backgrounds = gradientColors(style.backgroundImage);
      const solid = parseColor(style.backgroundColor);
      if (solid && solid[3] > 0.25) backgrounds.push(blend(solid, fallback));
      if (!backgrounds.length) backgrounds.push(fallback);
      const currentMinimum = Math.min(...backgrounds.map(background => contrast(foreground, background)));
      if (currentMinimum >= 4.5) return;
      const light = [255, 255, 255, 1];
      const dark = [23, 32, 51, 1];
      const lightMinimum = Math.min(...backgrounds.map(background => contrast(light, background)));
      const darkMinimum = Math.min(...backgrounds.map(background => contrast(dark, background)));
      const useLightText = lightMinimum >= darkMinimum;
      const bestMinimum = Math.max(lightMinimum, darkMinimum);
      button.dataset.raButtonTone = useLightText ? 'dark' : 'light';
      if (bestMinimum < 4.5) {
        button.dataset.raButtonTone = 'dark';
        button.dataset.raButtonSurface = 'dark';
      }
    });
  }

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
    window.requestAnimationFrame(ensureButtonContrast);
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

    if (window.MutationObserver) {
      let scheduled = false;
      new MutationObserver(function () {
        if (scheduled) return;
        scheduled = true;
        window.requestAnimationFrame(function () {
          scheduled = false;
          ensureButtonContrast();
        });
      }).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style', 'disabled']
      });
    }
  });
})();
