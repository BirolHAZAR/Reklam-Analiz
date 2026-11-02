(() => {
    document.querySelectorAll('[data-sync-form]').forEach(form => {
        const button = form.querySelector('button');
        const label = button.querySelector('span');
        const feedback = form.querySelector('[role="status"]');
        let checking = false;
        async function watch(url, attempts = 0) {
            try {
                const response = await fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
                if (!response.ok) throw new Error();
                const data = await response.json();
                feedback.textContent = data.message;
                if (data.status === 'completed') {
                    window.location.reload();
                } else if (data.status === 'failed') {
                    button.disabled = false;
                    label.textContent = 'Yeniden senkronize et';
                    checking = false;
                } else if (attempts < 240) {
                    setTimeout(() => watch(url, attempts + 1), 3000);
                } else {
                    feedback.textContent = 'İşlem sürüyor. Güncel durumu görmek için sayfayı yenileyin.';
                }
            } catch (_) {
                feedback.textContent = 'Durum alınamadı. Güncel durumu görmek için sayfayı yenileyin.';
            }
        }
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (checking || button.disabled) return;
            checking = true;
            button.disabled = true;
            label.textContent = 'Senkronize ediliyor...';
            feedback.textContent = 'Senkronizasyon başlatılıyor...';
            try {
                const response = await fetch(form.action, {
                    method: 'POST', body: new FormData(form), credentials: 'same-origin',
                    headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    feedback.textContent = data.message || 'Senkronizasyon başlatılamadı.';
                    button.disabled = false;
                    label.textContent = 'Yeniden dene';
                    checking = false;
                    return;
                }
                watch(data.status_url);
            } catch (_) {
                feedback.textContent = 'Bağlantı kurulamadı. Sayfayı yenileyip tekrar deneyin.';
                button.disabled = false;
                label.textContent = 'Yeniden dene';
                checking = false;
            }
        });
        if (form.dataset.statusUrl) {
            checking = true;
            watch(form.dataset.statusUrl);
        }
    });
})();
