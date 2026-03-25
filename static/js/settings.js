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

    async function recalculateAttendance() {
        const start = document.getElementById('s_fix_start').value;
        const end = document.getElementById('s_fix_end').value;
        const hours = document.getElementById('s_fix_hours').value;
        
        if (!start || !end || !hours) {
            Toast.error('Please fill all fields for Data Correction');
            return;
        }
        
        if (!confirm(`Are you sure you want to permanently change required hours to ${hours} for all present/absent records between ${start} and ${end}?`)) {
            return;
        }
        
        const res = await API.post('/api/settings/recalculate', {
            start_date: start,
            end_date: end,
            hours: parseFloat(hours)
        });
        
        if (res.ok) {
            Toast.success(`Successfully corrected ${res.data.updated} records!`);
            // Clear inputs
            document.getElementById('s_fix_start').value = '';
            document.getElementById('s_fix_end').value = '';
        } else {
            Toast.error(res.error || 'Failed to recalculate attendance');
        }
    }

    return { load, save, createShortcut, recalculateAttendance };
})();
