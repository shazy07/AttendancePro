/* ═══════════════════════════════════════════════
   advances.js — Advance Salaries CRUD
   ═══════════════════════════════════════════════ */
'use strict';

const Advances = (() => {
  let _list = [];
  let _empList = [];

  async function init() {
    // Load employees for the select dropdown
    const res = await API.get('/api/employees');
    if (res.ok) {
      _empList = res.data;
      const select = document.getElementById('advEmpId');
      select.innerHTML = '<option value="">-- Select Employee --</option>' + 
        _empList.map(e => `<option value="${e.id}">${e.name}</option>`).join('');
    }
    
    // Set default month filter
    const now = new Date();
    const monthStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    if (!document.getElementById('advMonthFilter').value) {
      document.getElementById('advMonthFilter').value = monthStr;
    }
    
    load();
  }

  async function load() {
    const month = document.getElementById('advMonthFilter').value;
    const url = month ? `/api/advances?month=${month}` : '/api/advances';
    const res = await API.get(url);
    if (!res.ok) { Toast.error('Could not load advances'); return; }
    _list = res.data;
    _render(_list);
  }

  function _render(list) {
    const tbody = document.getElementById('advancesTbody');
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="tbl-empty">No advance salaries found for this criteria.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(a => `
      <tr>
        <td style="font-weight:500;">${formatDate(a.date)}</td>
        <td>
          <div style="font-weight:600">${a.employee_name}</div>
          <div style="font-size:11px;color:var(--text-muted)">#${a.employee_id}</div>
        </td>
        <td style="color:var(--red); font-weight:600;">${parseFloat(a.amount).toLocaleString()} PKR</td>
        <td style="color:var(--text-secondary);font-size:12px">${a.notes || '—'}</td>
        <td>
          <button class="btn" style="padding:6px 10px;font-size:12px;background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)" onclick="Advances.del(${a.id},'${a.employee_name}')">
            <i class="ri-delete-bin-line"></i>
          </button>
        </td>
      </tr>`).join('');
  }

  function openAdd() {
    document.getElementById('advEmpId').value = '';
    document.getElementById('advDate').value = new Date().toISOString().slice(0, 10);
    document.getElementById('advAmount').value = '';
    document.getElementById('advNotes').value = '';
    document.getElementById('advModal').style.display = 'flex';
  }

  function closeModal() {
    document.getElementById('advModal').style.display = 'none';
  }

  async function save() {
    const body = {
      employee_id: parseInt(document.getElementById('advEmpId').value),
      date: document.getElementById('advDate').value,
      amount: parseFloat(document.getElementById('advAmount').value) || 0,
      notes: document.getElementById('advNotes').value.trim(),
    };

    if (!body.employee_id || !body.date || body.amount <= 0) { 
      Toast.error('Employee, Date, and a valid Amount are required'); 
      return; 
    }

    const res = await API.post('/api/advances', body);

    if (res.ok) {
      Toast.success('Advance Granted!');
      closeModal();
      load();
    } else {
      Toast.error(res.error || 'Failed to grant advance');
    }
  }

  async function del(id, name) {
    if (!confirm(`Remove advance record for ${name}?`)) return;
    const res = await API.del(`/api/advances/${id}`);
    if (res.ok) { Toast.success('Advance record removed'); load(); }
    else Toast.error(res.error || 'Delete failed');
  }

  return { init, load, openAdd, closeModal, save, del };
})();
