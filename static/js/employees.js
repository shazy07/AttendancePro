/* ═══════════════════════════════════════════════
   employees.js — Employee CRUD
   ═══════════════════════════════════════════════ */
'use strict';

const Employees = (() => {
  let _list = [];

  async function load() {
    const res = await API.get('/api/employees');
    if (!res.ok) { Toast.error('Could not load employees'); return; }
    _list = res.data;
    _render(_list);
  }

  function _render(list) {
    const tbody = document.getElementById('employeeTbody');
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="tbl-empty">No employees. Click "Add Employee" to get started.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(e => `
      <tr>
        <td>
          <div style="display:flex;align-items:center;gap:10px">
            <div class="emp-avatar" style="width:32px;height:32px;font-size:12px;background:${avatarColor(e.name)}">${initials(e.name)}</div>
            <div>
              <div style="font-weight:600">${e.name}</div>
              <div style="font-size:11px;color:var(--text-muted)">#${e.id}</div>
            </div>
          </div>
        </td>
        <td>${e.designation || '—'}</td>
        <td><span style="background:rgba(124,58,237,.12);color:var(--purple);border-radius:20px;padding:2px 10px;font-size:12px">${e.department || '—'}</span></td>
        <td style="color:var(--text-secondary);font-size:12px">${e.email || '—'}<br>${e.phone || ''}</td>
        <td><strong>${e.monthly_salary ? parseFloat(e.monthly_salary).toLocaleString() : '0'} PKR</strong></td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-ghost" style="padding:6px 10px;font-size:12px" onclick="Employees.openEdit(${e.id})">
              <i class="ri-edit-line"></i>
            </button>
            <button class="btn" style="padding:6px 10px;font-size:12px;background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)" onclick="Employees.del(${e.id},'${e.name}')">
              <i class="ri-delete-bin-line"></i>
            </button>
          </div>
        </td>
      </tr>`).join('');
  }

  function openAdd() {
    document.getElementById('empId').value = '';
    document.getElementById('empName').value = '';
    document.getElementById('empDesig').value = '';
    document.getElementById('empDept').value = '';
    document.getElementById('empEmail').value = '';
    document.getElementById('empPhone').value = '';
    document.getElementById('empSalary').value = '';
    document.getElementById('empModalTitle').textContent = 'Add Employee';
    document.getElementById('empModal').style.display = 'flex';
    setTimeout(() => document.getElementById('empName').focus(), 100);
  }

  function openEdit(id) {
    const e = _list.find(x => x.id === id);
    if (!e) return;
    document.getElementById('empId').value = e.id;
    document.getElementById('empName').value = e.name || '';
    document.getElementById('empDesig').value = e.designation || '';
    document.getElementById('empDept').value = e.department || '';
    document.getElementById('empEmail').value = e.email || '';
    document.getElementById('empPhone').value = e.phone || '';
    document.getElementById('empSalary').value = e.monthly_salary || '';
    document.getElementById('empModalTitle').textContent = `Edit — ${e.name}`;
    document.getElementById('empModal').style.display = 'flex';
  }

  function closeModal() {
    document.getElementById('empModal').style.display = 'none';
  }

  async function save() {
    const id = document.getElementById('empId').value;
    const body = {
      name: document.getElementById('empName').value.trim(),
      designation: document.getElementById('empDesig').value.trim(),
      department: document.getElementById('empDept').value.trim(),
      email: document.getElementById('empEmail').value.trim(),
      phone: document.getElementById('empPhone').value.trim(),
      monthly_salary: parseFloat(document.getElementById('empSalary').value) || 0,
    };

    if (!body.name) { Toast.error('Name is required'); return; }

    const res = id
      ? await API.put(`/api/employees/${id}`, body)
      : await API.post('/api/employees', body);

    if (res.ok) {
      Toast.success(id ? 'Employee updated!' : 'Employee added!');
      closeModal();
      load();
    } else {
      Toast.error(res.error || 'Save failed');
    }
  }

  async function del(id, name) {
    if (!confirm(`Remove ${name} from the system? Their attendance history is preserved.`)) return;
    const res = await API.del(`/api/employees/${id}`);
    if (res.ok) { Toast.success(`${name} removed`); load(); }
    else Toast.error(res.error || 'Delete failed');
  }

  return { load, openAdd, openEdit, closeModal, save, del };
})();
