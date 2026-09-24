(function () {
    'use strict';
    const button = document.getElementById('raBackToTop');
    if (!button) return;
    const updateVisibility = () => { button.hidden = window.scrollY < 400; };
    window.addEventListener('scroll', updateVisibility, { passive: true });
    window.addEventListener('pageshow', updateVisibility);
    button.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
        });
    });
    updateVisibility();
})();
