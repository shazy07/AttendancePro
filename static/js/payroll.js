/* ═══════════════════════════════════════════════
   payroll.js — Payroll History & Issued Salaries
   ═══════════════════════════════════════════════ */
'use strict';

window.Payroll = (() => {

  async function init() {
    // Set default month filter to current month
    const now = new Date();
    const monthStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    const mFilter = document.getElementById('payrollMonthFilter');
    if (mFilter && !mFilter.value) {
      mFilter.value = monthStr;
    }
  }

  async function load() {
    const month = document.getElementById('payrollMonthFilter').value;
    const url = month ? `/api/payroll/history?month=${month}` : '/api/payroll/history';
    
    document.getElementById('payrollTbody').innerHTML = '<tr><td colspan="7" class="tbl-empty">Loading…</td></tr>';
    
    const res = await API.get(url);
    if (!res.ok) { 
      Toast.error('Could not load payroll history'); 
      return; 
    }
    
    _renderTable(res.data);
  }

  function _formatHrs(decimalHrs) {
    if (!decimalHrs) return '0h 00m';
    const h = Math.floor(decimalHrs);
    const m = Math.round((decimalHrs % 1) * 60);
    return `${h}h ${String(m).padStart(2,'0')}m`;
  }

  function _renderTable(list) {
    const tbody = document.getElementById('payrollTbody');
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="tbl-empty">No salaries have been issued for the selected period.</td></tr>';
      return;
    }
    
    tbody.innerHTML = list.map(p => {
      // Calculate net debt/surplus representation
      let dsLabel = '-';
      let dsColor = 'var(--text-muted)';
      const netS = p.surplus_hours - p.short_hours;
      
      if (netS > 0) {
          dsLabel = `+${_formatHrs(netS)}`;
          dsColor = 'var(--green)';
      } else if (netS < 0) {
          dsLabel = `-${_formatHrs(Math.abs(netS))}`;
          dsColor = 'var(--amber)';
          if (p.short_hours > 10) dsColor = 'var(--red)';
      }

      return `
      <tr>
        <td style="font-weight:500; font-size:13px">${p.month}</td>
        <td>
          <div style="font-weight:600">${p.employee_name}</div>
          <div style="font-size:11px;color:var(--text-muted)">${p.designation}</div>
        </td>
        <td style="text-align:right">${_formatHrs(p.total_required_hours)}</td>
        <td style="text-align:right">${_formatHrs(p.total_worked_hours)}</td>
        <td style="text-align:right; color:${dsColor}; font-weight:600">${dsLabel}</td>
        <td style="text-align:right; color:var(--red)">${p.deduction_amount > 0 ? '-' + parseFloat(p.deduction_amount).toLocaleString() : '-'}</td>
        <td style="text-align:right; font-weight:600; color:var(--blue); font-size:14px">
          ${parseFloat(p.net_salary).toLocaleString()}
        </td>
      </tr>`;
    }).join('');
  }

  return { init, load };
})();
