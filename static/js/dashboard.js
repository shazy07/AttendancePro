/* ═══════════════════════════════════════════════
   dashboard.js — Live status grid & Clock-In/Out
   ═══════════════════════════════════════════════ */
'use strict';

const Dashboard = (() => {
  let _allCards = [];
  let _refreshTimer = null;

  function _colorClass(c) {
    return ['green', 'amber', 'red', 'blue'].includes(c) ? c : 'blue';
  }

  function _debtBar(debtM, reqH) {
    if (reqH <= 0) return '';
    const maxM = reqH * 60;
    const pct = Math.min(100, Math.max(0, ((debtM + maxM) / (2 * maxM)) * 100));
    const colour = debtM >= 0 ? 'var(--green)' : (debtM > -30 ? 'var(--amber)' : 'var(--red)');
    return `
      <div class="debt-bar-wrap">
        <div class="debt-bar-label">
          <span>${debtM < 0 ? '⚠ In Debt' : '✓ Surplus'}</span>
          <span>${minutesToHrMin(debtM)}</span>
        </div>
        <div class="debt-bar"><div class="debt-bar-fill" style="width:${pct}%;background:${colour}"></div></div>
      </div>`;
  }

  function _clockedInCard(emp, s) {
    const cc = _colorClass(s.color);
    const ci = formatTime(s.clock_in);
    const hw = s.hours_worked.toFixed(2);
    const tgt = s.target_leave || '—';
    const av = avatarColor(emp.name);

    return `
    <div class="emp-card ${cc}" data-empid="${emp.id}" data-name="${emp.name.toLowerCase()}">
      <div class="emp-card-top">
        <div class="emp-avatar" style="background:${av}">${initials(emp.name)}</div>
        <div class="emp-info">
          <div class="emp-name">${emp.name}</div>
          <div class="emp-role">${emp.designation || emp.department || '—'}</div>
        </div>
        <span class="emp-badge ${cc}">● Clocked In</span>
      </div>
      <div class="emp-stats">
        <div class="emp-stat">
          <div class="emp-stat-val">${ci}</div>
          <div class="emp-stat-lbl">Clock In</div>
        </div>
        <div class="emp-stat">
          <div class="emp-stat-val">${hw}h</div>
          <div class="emp-stat-lbl">Hours So Far</div>
        </div>
        <div class="emp-stat">
          <div class="emp-stat-val">${s.required_hours}h</div>
          <div class="emp-stat-lbl">Required</div>
        </div>
      </div>
      ${_debtBar(s.debt_minutes, s.required_hours)}
      <div class="target-leave">
        <i class="ri-logout-circle-r-line"></i>
        Target leave: <strong>${tgt}</strong>
      </div>
      <div class="emp-actions">
        <button class="btn-clock-out" onclick="Dashboard.clockOut(${emp.id},'${emp.name}')">
          <i class="ri-logout-box-line"></i> Clock Out
        </button>
        <button class="btn-edit-att" title="Manual edit" onclick="openManualModal(${emp.id},'${emp.name}')">
          <i class="ri-edit-line"></i>
        </button>
      </div>
    </div>`;
  }

  function _clockedOutCard(emp, s) {
    const cc = _colorClass(s.color);
    const av = avatarColor(emp.name);
    let badge, body;

    if (s.status === 'weekly_off') {
      badge = `<span class="emp-badge blue">📅 Friday Off</span>`;
      body = `<div style="text-align:center;padding:14px;color:var(--blue);font-size:13px">Weekly Rest Day — No Hours Required</div>`;
    } else if (s.status === 'holiday') {
      badge = `<span class="emp-badge blue">🎉 ${s.holiday_name || 'Holiday'}</span>`;
      body = `<div style="text-align:center;padding:14px;color:var(--cyan);font-size:13px">Public Holiday — Overtime if Present</div>
               <div class="emp-actions"><button class="btn-clock-in" onclick="Dashboard.clockIn(${emp.id},'${emp.name}')"><i class="ri-login-box-line"></i> Clock In (Holiday OT)</button></div>`;
    } else if (s.clock_out) {
      const hw = s.hours_worked.toFixed(2);
      badge = `<span class="emp-badge ${cc}">✓ Done — ${hw}h</span>`;
      body = `${_debtBar(s.debt_minutes, s.required_hours)}
               <div class="emp-stats">
                 <div class="emp-stat"><div class="emp-stat-val">${formatTime(s.clock_in)}</div><div class="emp-stat-lbl">In</div></div>
                 <div class="emp-stat"><div class="emp-stat-val">${formatTime(s.clock_out)}</div><div class="emp-stat-lbl">Out</div></div>
                 <div class="emp-stat"><div class="emp-stat-val">${hw}h</div><div class="emp-stat-lbl">Worked</div></div>
               </div>
               <div class="emp-actions"><button class="btn-edit-att" style="width:100%;justify-content:center;gap:6px" onclick="openManualModal(${emp.id},'${emp.name}')"><i class="ri-edit-line"></i> Edit Record</button></div>`;
    } else {
      badge = `<span class="emp-badge red">✗ Absent</span>`;
      body = `<div class="emp-actions" style="margin-top:8px">
                 <button class="btn-clock-in" onclick="Dashboard.clockIn(${emp.id},'${emp.name}')"><i class="ri-login-box-line"></i> Clock In</button>
                 <button class="btn-edit-att" title="Manual entry" onclick="openManualModal(${emp.id},'${emp.name}')"><i class="ri-edit-line"></i></button>
               </div>`;
    }

    return `
    <div class="emp-card ${cc}" data-empid="${emp.id}" data-name="${emp.name.toLowerCase()}">
      <div class="emp-card-top">
        <div class="emp-avatar" style="background:${av}">${initials(emp.name)}</div>
        <div class="emp-info">
          <div class="emp-name">${emp.name}</div>
          <div class="emp-role">${emp.designation || emp.department || '—'}</div>
        </div>
        ${badge}
      </div>
      ${body}
    </div>`;
  }

  function _render(data) {
    const grid = document.getElementById('employeeGrid');
    if (!data.length) { grid.innerHTML = '<p style="color:var(--text-muted);padding:20px">No employees found.</p>'; return; }

    let present = 0, late = 0, absent = 0, off = 0;
    let html = '';
    _allCards = data;

    for (const item of data) {
      const s = item;
      const emp = s.employee;
      if (s.status === 'weekly_off' || s.status === 'holiday') off++;
      else if (s.clock_in && !s.clock_out && s.debt_minutes >= 0) present++;
      else if (s.clock_in && s.debt_minutes < 0) late++;
      else if (s.clock_out && s.debt_minutes >= 0) present++;
      else absent++;

      html += s.clock_in && !s.clock_out
        ? _clockedInCard(emp, s)
        : _clockedOutCard(emp, s);
    }

    grid.innerHTML = html;
    document.getElementById('statPresent').textContent = present;
    document.getElementById('statLate').textContent = late;
    document.getElementById('statAbsent').textContent = absent;
    document.getElementById('statOff').textContent = off;
  }

  async function init() {
    document.getElementById('todayLabel').textContent =
      new Date().toLocaleDateString('en-PK', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

    await refresh(true);
    clearInterval(_refreshTimer);
    _refreshTimer = setInterval(() => refresh(false), 30000); // auto-refresh every 30s
  }

  async function refresh(showLoader = true) {
    if (showLoader) {
      document.getElementById('employeeGrid').innerHTML =
        '<div class="loading-ring"><div></div><div></div><div></div><div></div></div>';
    }
    const res = await API.get('/api/attendance/status');
    if (res.ok) _render(res.data);
    else Toast.error('Could not load status');
  }

  function filter(query) {
    query = query.toLowerCase();
    document.querySelectorAll('.emp-card').forEach(card => {
      card.style.display = card.dataset.name.includes(query) ? '' : 'none';
    });
  }

  async function clockIn(empId, name) {
    const btn = [...document.querySelectorAll(`[data-empid="${empId}"] .btn-clock-in`)][0];
    if (btn) { btn.disabled = true; btn.textContent = 'Clocking In…'; }

    const res = await API.post('/api/attendance/clockin', { employee_id: empId });
    if (res.ok) {
      Celebrate.show(`${name} is clocked in! 🕘`);
      await refresh(false);
    } else {
      Toast.error(res.error || 'Clock-in failed');
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ri-login-box-line"></i> Clock In'; }
    }
  }

  async function clockOut(empId, name) {
    const btn = [...document.querySelectorAll(`[data-empid="${empId}"] .btn-clock-out`)][0];
    if (btn) { btn.disabled = true; btn.textContent = 'Clocking Out…'; }

    const res = await API.post('/api/attendance/clockout', { employee_id: empId });
    if (res.ok) {
      const h = res.data.total_hours?.toFixed(2) || '?';
      const dm = res.data.debt_minutes || 0;
      const msg = dm >= 0
        ? `${name} clocked out — ${h}h worked! Surplus ${minutesToHrMin(dm)} 🎉`
        : `${name} clocked out — ${h}h worked. Debt ${minutesToHrMin(dm)}`;
      Celebrate.show(msg);
      await refresh(false);
    } else {
      Toast.error(res.error || 'Clock-out failed');
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ri-logout-box-line"></i> Clock Out'; }
    }
  }

  let _bulkMode = 'clock_in';

  async function bulkClockIn() {
    _bulkMode = 'clock_in';
    document.getElementById('bulkModalTitle').textContent = '⚡ Bulk Clock In';
    document.getElementById('bulkSaveBtn').innerHTML = '<i class="ri-save-line"></i> Save All Clock-Ins';
    document.getElementById('bulkDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('bulkFillTime').value = '09:00';
    await _loadBulkEmployees();
    document.getElementById('bulkModal').style.display = 'flex';
  }

  async function bulkClockOut() {
    _bulkMode = 'clock_out';
    document.getElementById('bulkModalTitle').textContent = '⚡ Bulk Clock Out';
    document.getElementById('bulkSaveBtn').innerHTML = '<i class="ri-save-line"></i> Save All Clock-Outs';
    document.getElementById('bulkDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('bulkFillTime').value = '20:30';
    await _loadBulkEmployees();
    document.getElementById('bulkModal').style.display = 'flex';
  }

  async function _loadBulkEmployees() {
    const res = await API.get('/api/employees');
    const tbody = document.getElementById('bulkTbody');
    if (!res.ok || !res.data.length) {
      tbody.innerHTML = '<tr><td colspan="3" class="tbl-empty">No employees found</td></tr>';
      return;
    }
    tbody.innerHTML = res.data.map((e, i) => `
      <tr>
        <td style="color:var(--text-muted)">${i + 1}</td>
        <td>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="emp-avatar" style="background:${avatarColor(e.name)};width:30px;height:30px;font-size:12px;flex-shrink:0">${initials(e.name)}</div>
            <div>
              <div style="font-weight:600;font-size:13px">${e.name}</div>
              <div style="font-size:11px;color:var(--text-muted)">${e.designation || e.department || ''}</div>
            </div>
          </div>
        </td>
        <td><input class="form-input bulk-time-input" type="time" data-eid="${e.id}" /></td>
      </tr>
    `).join('');
  }

  function fillAllTimes() {
    const val = document.getElementById('bulkFillTime').value;
    if (!val) { Toast.error('Enter a time to fill first'); return; }
    document.querySelectorAll('.bulk-time-input').forEach(inp => { inp.value = val; });
    Toast.info('All times filled with ' + val);
  }

  function closeBulkModal() {
    document.getElementById('bulkModal').style.display = 'none';
  }

  async function submitBulkEntry() {
    const dt = document.getElementById('bulkDate').value;
    if (!dt) { Toast.error('Please select a date'); return; }

    const entries = [];
    document.querySelectorAll('.bulk-time-input').forEach(inp => {
      if (inp.value) {
        entries.push({ employee_id: parseInt(inp.dataset.eid), time: inp.value });
      }
    });

    if (!entries.length) { Toast.error('Fill in at least one employee\'s time'); return; }

    const btn = document.getElementById('bulkSaveBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Saving…';

    const res = await API.post('/api/attendance/bulk-entry', {
      mode: _bulkMode,
      date: dt,
      entries
    });

    if (res.ok) {
      const d = res.data;
      const label = _bulkMode === 'clock_in' ? 'clocked in' : 'clocked out';
      let msg = `✅ ${d.saved} employee${d.saved !== 1 ? 's' : ''} ${label}!`;
      if (d.skipped) msg += ` (${d.skipped} skipped)`;
      if (d.errors && d.errors.length) msg += `\n⚠ ${d.errors.join(', ')}`;
      Celebrate.show(msg);
      closeBulkModal();
      await refresh(false);
    } else {
      Toast.error(res.error || 'Bulk save failed');
    }

    btn.disabled = false;
    btn.innerHTML = '<i class="ri-save-line"></i> Save All';
  }

  return { init, refresh, filter, clockIn, clockOut, bulkClockIn, bulkClockOut, closeBulkModal, fillAllTimes, submitBulkEntry };
})();
