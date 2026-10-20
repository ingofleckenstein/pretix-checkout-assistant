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
    // Pretix temporarily disables address fields while asynchronously updating
    // country-dependent requirements. Never submit while this is in flight.
    const profile = profiles[0];
    let attempts = 0;
    function afterAddressUpdate() {
        if (++attempts > 50) return;
        const fields = ['street', 'zipcode', 'city', 'country'].map(
            name => invoice.querySelector('[name="' + name + '"]')
        );
        if (fields.some(input => !input)) return;
        if (fields.some(input => input.disabled) || (window.jQuery && window.jQuery.active)) {
            window.setTimeout(afterAddressUpdate, 100);
            return;
        }
        for (let i = 0; i < fields.length; i++) {
            const name = ['street', 'zipcode', 'city', 'country'][i];
            if (String(fields[i].value).trim() !== String(profile[name] || '').trim()) return;
        }
        const transmission = invoice.querySelector('[name="transmission_type"]');
        if (transmission && transmission.disabled) {
            window.setTimeout(afterAddressUpdate, 100);
            return;
        }
        if (!form.checkValidity() || typeof form.requestSubmit !== 'function') return;
        form.requestSubmit();
    }
    window.setTimeout(afterAddressUpdate, 100);
});

