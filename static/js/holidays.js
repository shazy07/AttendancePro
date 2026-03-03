/* ═══════════════════════════════════════════════
   holidays.js — Holiday calendar & Ramadan mode
   ═══════════════════════════════════════════════ */
'use strict';

const Holidays = (() => {

    async function load() {
        // Sync Ramadan toggle
        const sres = await API.get('/api/settings');
        if (sres.ok) {
            const ramadan = sres.data.ramadan_mode === 'true';
            document.getElementById('ramadanToggle').checked = ramadan;
            document.getElementById('ramadanPill').style.display = ramadan ? 'flex' : 'none';
        }

        const year = document.getElementById('holidayYearFilter').value;
        const res = await API.get(`/api/holidays?year=${year}`);
        const list = document.getElementById('holidayList');

        if (!res.ok) { list.innerHTML = '<p style="color:var(--red)">Failed to load holidays.</p>'; return; }
        if (!res.data.length) {
            list.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:10px 0">No holidays marked for this year.</p>';
            return;
        }

        list.innerHTML = res.data.map(h => `
      <div class="holiday-item">
        <div class="holiday-item-info">
          <div class="holiday-date">${formatDate(h.date)}</div>
          <div class="holiday-name">${h.name}</div>
          <div class="holiday-mult">★ ${h.overtime_multiplier}× overtime if worked</div>
        </div>
        <button class="btn-del" onclick="Holidays.del(${h.id},'${h.name}')" title="Remove">
          <i class="ri-delete-bin-line"></i>
        </button>
      </div>`).join('');
    }

    async function toggleRamadan(on) {
        const res = await API.post('/api/settings', { ramadan_mode: on ? 'true' : 'false' });
        if (res.ok) {
            Toast.success(`Ramadan mode ${on ? 'enabled — daily goal is now 8.5 hrs' : 'disabled — daily goal is now 11.5 hrs'}`);
            document.getElementById('ramadanPill').style.display = on ? 'flex' : 'none';
            await loadSystemInfo();
        } else {
            Toast.error('Could not update setting');
        }
    }

    function openAdd() {
        document.getElementById('holDate').value = new Date().toISOString().slice(0, 10);
        document.getElementById('holPresets').value = '';
        document.getElementById('holName').value = '';
        document.getElementById('holMult').value = '1.5';
        document.getElementById('holModal').style.display = 'flex';
        setTimeout(() => document.getElementById('holName').focus(), 100);
    }

    function closeModal() {
        document.getElementById('holModal').style.display = 'none';
    }

    async function save() {
        const date = document.getElementById('holDate').value;
        const name = document.getElementById('holName').value.trim();
        const mult = parseFloat(document.getElementById('holMult').value);

        if (!date || !name) { Toast.error('Date and name are required'); return; }

        const res = await API.post('/api/holidays', { date, name, overtime_multiplier: mult });
        if (res.ok) {
            Toast.success(`${name} marked as holiday`);
            closeModal();
            load();
        } else {
            Toast.error(res.error || 'Could not save holiday');
        }
    }

    async function del(id, name) {
        if (!confirm(`Remove "${name}" from holidays?`)) return;
        const res = await API.del(`/api/holidays/${id}`);
        if (res.ok) { Toast.success('Holiday removed'); load(); }
        else Toast.error('Failed to remove holiday');
    }

    return { load, toggleRamadan, openAdd, closeModal, save, del };
})();
