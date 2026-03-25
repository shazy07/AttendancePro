/* ═══════════════════════════════════════════════
   advances.js — Advance Salaries CRUD & Ledger
   ═══════════════════════════════════════════════ */
'use strict';

const Advances = (() => {
  let _historyList = [];
  let _ledgerList = [];
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
    
    loadLedger();
    loadHistory();
  }

  async function loadLedger() {
    const res = await API.get('/api/advances/ledger');
    if (!res.ok) { Toast.error('Could not load ledger'); return; }
    _ledgerList = res.data;
    _renderLedger(_ledgerList);
  }

  function _renderLedger(list) {
    const tbody = document.getElementById('ledgerTbody');
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="tbl-empty">No advance records found.</td></tr>';
      return;
    }
    
    tbody.innerHTML = list.map(l => `
      <tr>
        <td>
          <div style="font-weight:600">${l.employee_name}</div>
          <div style="font-size:11px;color:var(--text-muted)">#${l.employee_id}</div>
        </td>
        <td style="color:var(--text-secondary)">${parseFloat(l.total_given).toLocaleString()}</td>
        <td style="color:var(--text-secondary)">${parseFloat(l.total_repaid).toLocaleString()}</td>
        <td style="font-weight:600; color:${l.balance > 0 ? 'var(--red)' : 'var(--green)'}">
          ${parseFloat(l.balance).toLocaleString()} 
        </td>
      </tr>`).join('');
  }

  async function loadHistory() {
    const month = document.getElementById('advMonthFilter').value;
    const url = month ? `/api/advances?month=${month}` : '/api/advances';
    const res = await API.get(url);
    if (!res.ok) { Toast.error('Could not load history'); return; }
    _historyList = res.data;
    _renderHistory(_historyList);
  }

  function _renderHistory(list) {
    const tbody = document.getElementById('advancesTbody');
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="tbl-empty">No transactions found for this period.</td></tr>';
      return;
    }

    tbody.innerHTML = list.map(a => {
      let typeLabel = '';
      let color = '';
      let sign = '';
      
      switch (a.type) {
        case 'given':
          typeLabel = 'Advance Given';
          color = 'var(--red)';
          sign = '+';
          break;
        case 'deduction':
          typeLabel = 'Salary Deduction';
          color = 'var(--amber)';
          sign = '-';
          break;
        case 'repayment':
          typeLabel = 'Cash Repayment';
          color = 'var(--green)';
          sign = '-';
          break;
      }

      return `
      <tr>
        <td style="font-weight:500; font-size:13px">${formatDate(a.date)}</td>
        <td>
          <div style="font-weight:600">${a.employee_name}</div>
        </td>
        <td>
          <span style="font-size:12px; background:rgba(0,0,0,0.05); padding:2px 8px; border-radius:12px;">
            ${typeLabel}
          </span>
        </td>
        <td style="color:${color}; font-weight:600;">${sign}${parseFloat(a.amount).toLocaleString()}</td>
        <td>
          <button class="btn" style="padding:6px 10px;font-size:12px;background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)" onclick="Advances.del(${a.id},'${a.employee_name}')">
            <i class="ri-delete-bin-line"></i>
          </button>
        </td>
      </tr>`;
    }).join('');
  }

  function openAdd() {
    document.getElementById('advEmpId').value = '';
    document.getElementById('advType').value = 'given';
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
      type: document.getElementById('advType').value,
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
      Toast.success('Transaction Saved!');
      closeModal();
      loadLedger();
      loadHistory();
    } else {
      Toast.error(res.error || 'Failed to save transaction');
    }
  }

  async function del(id, name) {
    if (!confirm(`Remove this transaction record for ${name}?`)) return;
    const res = await API.del(`/api/advances/${id}`);
    if (res.ok) { 
      Toast.success('Transaction removed'); 
      loadLedger();
      loadHistory(); 
    } else {
      Toast.error(res.error || 'Delete failed');
    }
  }

  async function printReport() {
    const month = document.getElementById('advMonthFilter').value;
    Toast.info('Generating PDF...');
    const res = await API.post('/api/reports/advance-history', { month });
    if (res.ok) {
      window.open(res.data.url, '_blank');
      Toast.success('PDF generated!');
    } else {
      Toast.error(res.error || 'Failed to generate report');
    }
  }

  return { init, loadLedger, loadHistory, openAdd, closeModal, save, del, printReport };
})();
