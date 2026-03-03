/* ═══════════════════════════════════════════════
   main.js — App shell, routing, utilities
   ═══════════════════════════════════════════════ */
'use strict';

// ── API ────────────────────────────────────────
const API = {
  async get(path) {
    const r = await fetch(path);
    return r.json();
  },
  async post(path, body = {}) {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return r.json();
  },
  async put(path, body = {}) {
    const r = await fetch(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    return r.json();
  },
};

// ── Toast ──────────────────────────────────────
const Toast = {
  _t: null,
  show(msg, type = 'info', duration = 3200) {
    const el = document.getElementById('toast');
    el.className = `toast ${type}`;
    el.innerHTML = `<i class="ri-${type === 'success' ? 'checkbox-circle' : 'error-warning'}-line"></i> ${msg}`;
    el.classList.add('show');
    clearTimeout(this._t);
    this._t = setTimeout(() => el.classList.remove('show'), duration);
  },
  success(m) { this.show(m, 'success'); },
  error(m) { this.show(m, 'error', 4500); },
  info(m) { this.show(m, 'info'); },
};

// ── Lottie Success Overlay ─────────────────────
const Celebrate = {
  _anim: null,
  show(msg = 'Done!') {
    const overlay = document.getElementById('lottieOverlay');
    document.getElementById('lottieMsg').textContent = msg;
    overlay.style.display = 'flex';
    const container = document.getElementById('lottieContainer');
    container.innerHTML = '';
    try {
      this._anim = lottie.loadAnimation({
        container, renderer: 'svg', loop: false, autoplay: true,
        path: 'https://assets2.lottiefiles.com/packages/lf20_jfe6gb0u.json'
      });
      this._anim.addEventListener('complete', () => this.hide());
    } catch (_) {
      // Fallback if Lottie CDN fails
      container.innerHTML = '<div style="font-size:64px;animation:spin .6s ease">✅</div>';
      setTimeout(() => this.hide(), 1400);
    }
    setTimeout(() => this.hide(), 3000);
  },
  hide() {
    document.getElementById('lottieOverlay').style.display = 'none';
    if (this._anim) { this._anim.destroy(); this._anim = null; }
  },
};
// Close on overlay click
document.getElementById('lottieOverlay').addEventListener('click', () => Celebrate.hide());

// ── Router ─────────────────────────────────────
const PAGES = {
  'dashboard': { title: 'Dashboard', init: () => Dashboard.init() },
  'employees': { title: 'Employees', init: () => Employees.load() },
  'holidays': { title: 'Holidays', init: () => Holidays.load() },
  'reports': { title: 'Report Hub', init: () => Reports.init() },
  'settings': { title: 'Settings', init: () => Settings.load() },
};

function navigate(hash) {
  const page = hash.replace('#', '') || 'dashboard';
  if (!PAGES[page]) return;

  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
  const el = document.getElementById(`page-${page}`);
  if (el) el.style.display = '';

  // Update nav
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navEl = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (navEl) navEl.classList.add('active');

  // Update page title
  document.getElementById('pageTitle').textContent = PAGES[page].title;

  // Init page
  PAGES[page].init();
}

window.addEventListener('hashchange', () => navigate(location.hash));

// ── Dark / Light Mode ──────────────────────────
const Theme = {
  current: localStorage.getItem('theme') || 'dark',
  init() {
    document.documentElement.setAttribute('data-theme', this.current);
    this._updateIcon();
  },
  toggle() {
    this.current = this.current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', this.current);
    localStorage.setItem('theme', this.current);
    this._updateIcon();
  },
  _updateIcon() {
    document.getElementById('themeIcon').className =
      this.current === 'dark' ? 'ri-sun-line' : 'ri-moon-line';
  }
};
document.getElementById('themeToggle').addEventListener('click', () => Theme.toggle());

// ── Live Clock ─────────────────────────────────
function startClock() {
  function update() {
    const now = new Date();
    document.getElementById('liveClock').textContent =
      now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
    document.getElementById('serverTime').textContent =
      now.toLocaleDateString('en-PK', { weekday: 'short', day: 'numeric', month: 'short' });
  }
  update();
  setInterval(update, 1000);
}

// ── Mobile sidebar toggle ──────────────────────
document.getElementById('menuToggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});
document.addEventListener('click', e => {
  if (!e.target.closest('.sidebar') && !e.target.closest('#menuToggle')) {
    document.getElementById('sidebar').classList.remove('open');
  }
});

// ── Manual Attendance Modal helpers ────────────
function openManualModal(empId, empName) {
  document.getElementById('manualEmpId').value = empId;
  document.getElementById('manualModalTitle').textContent = `Edit Attendance — ${empName}`;
  document.getElementById('manualDate').value = new Date().toISOString().slice(0, 10);
  document.getElementById('manualClockIn').value = '';
  document.getElementById('manualClockOut').value = '';
  document.getElementById('manualStatus').value = 'present';
  document.getElementById('manualNotes').value = '';
  document.getElementById('manualModal').style.display = 'flex';
}
function closeManualModal() {
  document.getElementById('manualModal').style.display = 'none';
}
async function saveManual() {
  const eid = parseInt(document.getElementById('manualEmpId').value);
  const dt = document.getElementById('manualDate').value;
  const ci = document.getElementById('manualClockIn').value;
  const co = document.getElementById('manualClockOut').value;
  const st = document.getElementById('manualStatus').value;
  const nt = document.getElementById('manualNotes').value;

  const ciStr = ci ? `${dt}T${ci}:00` : null;
  const coStr = co ? `${dt}T${co}:00` : null;

  const res = await API.post('/api/attendance/manual', {
    employee_id: eid, date: dt,
    clock_in: ciStr, clock_out: coStr,
    status: st, notes: nt
  });
  if (res.ok) {
    Toast.success('Attendance record saved');
    closeManualModal();
    if (typeof Dashboard !== 'undefined') Dashboard.refresh();
  } else {
    Toast.error(res.error || 'Failed to save');
  }
}

// ── System info ────────────────────────────────
async function loadSystemInfo() {
  const res = await API.get('/api/system/info');
  if (res.ok) {
    document.getElementById('companyName').textContent = res.data.company;
    const ramadan = res.data.ramadan_mode === 'true';
    document.getElementById('ramadanPill').style.display = ramadan ? 'flex' : 'none';
  }
}

// ── Utilities ──────────────────────────────────
function formatDate(d) {
  return new Date(d).toLocaleDateString('en-PK', { day: 'numeric', month: 'short', year: 'numeric' });
}
function formatTime(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
}
function minutesToHrMin(m) {
  const abs = Math.abs(m), sign = m < 0 ? '-' : '+';
  return `${sign}${Math.floor(abs / 60)}h ${(abs % 60).toString().padStart(2, '0')}m`;
}
function avatarColor(name) {
  const cols = ['#7c3aed', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#0ea5e9'];
  let h = 0;
  for (let c of name) h = ((h << 5) - h) + c.charCodeAt(0);
  return cols[Math.abs(h) % cols.length];
}
function initials(name) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

// ── Bootstrap ──────────────────────────────────
Theme.init();
startClock();
loadSystemInfo();
navigate(location.hash || '#dashboard');
