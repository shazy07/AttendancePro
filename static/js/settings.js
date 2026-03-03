/* ═══════════════════════════════════════════════
   settings.js — System settings page
   ═══════════════════════════════════════════════ */
'use strict';

const Settings = (() => {
    // Map of setting key → input element ID
    const FIELDS = [
        'company_name',
        'standard_shift_start', 'standard_shift_end', 'ramadan_shift_end',
        'default_overtime_multiplier',
        'email_sender', 'email_password', 'email_recipients',
        'smtp_host', 'smtp_port',
        'allowed_ip_subnet',
    ];


    async function load() {
        const res = await API.get('/api/settings');
        if (!res.ok) { Toast.error('Could not load settings'); return; }
        const s = res.data;
        for (const key of FIELDS) {
            const el = document.getElementById(`s_${key}`);
            if (el && s[key] !== undefined) el.value = s[key];
        }
    }

    async function save() {
        const body = {};
        for (const key of FIELDS) {
            const el = document.getElementById(`s_${key}`);
            if (el) body[key] = el.value;
        }

        const res = await API.post('/api/settings', body);
        if (res.ok) {
            Toast.success('Settings saved!');
            await loadSystemInfo();   // refresh company name in sidebar
        } else {
            Toast.error(res.error || 'Save failed');
        }
    }

    async function createShortcut() {
        const res = await API.post('/api/system/create-shortcut');
        if (res.ok) Toast.success('Shortcut created on Desktop!');
        else Toast.error(res.error || 'Failed to create shortcut');
    }

    return { load, save, createShortcut };
})();
