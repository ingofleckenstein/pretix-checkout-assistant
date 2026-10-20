/* Experimental. Pretix's own POST performs the server-side validation. */
window.addEventListener('load', function () {
    const invoice = document.querySelector('#invoice');
    const form = invoice && invoice.closest('form');
    const source = document.querySelector('#addresses_json');
    if (!invoice || !form || !source || form.querySelector('.has-error')) return;
    let profiles;
    try { profiles = JSON.parse(source.textContent); } catch (_) { return; }
    if (!Array.isArray(profiles) || profiles.length !== 1) return;
    const profile = profiles[0];
    // Never overwrite a previously entered address.
    for (const name of ['street', 'zipcode', 'city']) {
        const input = invoice.querySelector('[name="' + name + '"]');
        if (!input || input.value.trim()) return;
    }
    // Refuse to replace other existing user/plugin-supplied text values.
    for (const input of invoice.querySelectorAll('input[name], textarea[name]')) {
        if (['hidden', 'checkbox', 'radio'].includes(input.type)) continue;
        const value = String(input.value || '').trim();
        if (value && (typeof profile[input.name] !== 'string' || value !== profile[input.name].trim())) return;
    }
    const button = invoice.querySelector('.profile-apply');
    if (!button || invoice.classList.contains('profile-none-matched')) return;
    button.click();
    const script = document.querySelector('script[data-checkout-assistant]');
    if (!script || script.dataset.checkoutAssistant !== 'submit') return;
    // Pretix temporarily disables address fields while asynchronously updating
    // country-dependent requirements. Never submit while this is in flight.
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
