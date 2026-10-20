/* Experimental. Pretix's own POST performs the server-side validation. */
window.addEventListener('load', function () {
    const invoice = document.querySelector('#invoice');
    const form = invoice && invoice.closest('form');
    const source = document.querySelector('#addresses_json');
    if (!invoice || !form || !source || form.querySelector('.has-error')) return;
    let profiles;
    try { profiles = JSON.parse(source.textContent); } catch (_) { return; }
    if (!Array.isArray(profiles) || profiles.length !== 1) return;
    // Never overwrite a previously entered address.
    for (const name of ['street', 'zipcode', 'city']) {
        const input = invoice.querySelector('[name="' + name + '"]');
        if (!input || input.value.trim()) return;
    }
    const button = invoice.querySelector('.profile-apply');
    if (!button || invoice.classList.contains('profile-none-matched')) return;
    button.click();
    // If pretix's handler was not installed or did not populate the address,
    // leave the form visible. Browser checks supplement, not replace, pretix.
    const profile = profiles[0];
    for (const name of ['street', 'zipcode', 'city', 'country']) {
        const input = invoice.querySelector('[name="' + name + '"]');
        if (!input || String(input.value).trim() !== String(profile[name] || '').trim()) return;
    }
    if (!form.checkValidity() || typeof form.requestSubmit !== 'function') return;
    form.requestSubmit();
});

