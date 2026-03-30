/* ═══════════════════════════════════════════════
   reports.js — Report Hub (3 magic buttons)
   ═══════════════════════════════════════════════ */
'use strict';

const Reports = (() => {

    async function init() {
        // Populate employee select
        const res = await API.get('/api/employees');
        if (res.ok) {
            const sel = document.getElementById('reportEmpSel');
            sel.innerHTML = '<option value="">Select employee…</option>' +
                res.data.map(e => `<option value="${e.id}">${e.name}</option>`).join('');
        }
        // Set default month to current month
        const now = new Date();
        const m = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        document.getElementById('reportMonth').value = m;
        document.getElementById('reportMonthlyPulseMonth').value = m;
    }

    async function _runBtn(btnId, msg, fn) {
        const btn = document.getElementById(btnId);
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<i class="ri-loader-4-line" style="animation:spin .8s linear infinite"></i> ${msg}`;

        try {
            await fn();
        } finally {
            btn.disabled = false;
            btn.innerHTML = orig;
        }
    }

    async function dailyPulse() {
        await _runBtn('btnDailyPulse', 'Generating…', async () => {
            const res = await API.post('/api/reports/daily-pulse');
            if (res.ok) {
                window.open(res.data.url, '_blank');
                Toast.success('Daily Pulse PDF ready!');
            } else {
                Toast.error(res.error || 'Failed to generate report');
            }
        });
    }

    let _wizardEid = null;
    let _wizardMonth = null;
    let _wizardGross = 0;
    let _wizardDeducted = 0;

    async function deepDive() {
        const eid = document.getElementById('reportEmpSel').value;
        const month = document.getElementById('reportMonth').value;
        if (!eid) { Toast.error('Please select an employee'); return; }
        if (!month) { Toast.error('Please select a month'); return; }

        const res = await API.get(`/api/payroll/monthly/${eid}/${month}`);
        if (!res.ok) { Toast.error('Failed to analyze payroll'); return; }

        _wizardEid = eid;
        _wizardMonth = month;
        _wizardGross = res.data.gross_salary || 0;
        _wizardDeducted = res.data.advance_deductions || 0;
        
        document.getElementById('swGross').innerText = _wizardGross.toLocaleString() + ' PKR';
        document.getElementById('swDeducted').innerText = _wizardDeducted.toLocaleString() + ' PKR';
        document.getElementById('swDebt').innerText = (res.data.total_outstanding_debt || 0).toLocaleString() + ' PKR';
        document.getElementById('swNewDeduction').value = 0;
        
        updateWizardNet();
        document.getElementById('salaryWizardModal').style.display = 'flex';
    }

    function updateWizardNet() {
        const newDeduct = parseFloat(document.getElementById('swNewDeduction').value) || 0;
        const net = _wizardGross - _wizardDeducted - newDeduct;
        document.getElementById('swNet').innerText = net.toLocaleString() + ' PKR';
    }

    async function confirmSalaryWizard() {
        const newDeduct = parseFloat(document.getElementById('swNewDeduction').value) || 0;
        
        await _runBtn('btnDeepDive', 'Issuing Salary…', async () => {
            document.getElementById('salaryWizardModal').style.display = 'none';

            // Permanently issue the salary and apply any deduction
            const resIssue = await API.post('/api/payroll/issue', {
                employee_id: parseInt(_wizardEid),
                month: _wizardMonth,
                deduction: newDeduct
            });

            if (!resIssue.ok) {
                Toast.error(resIssue.error || 'Failed to issue salary');
                return;
            }

            if (newDeduct > 0) {
                Toast.success(`Successfully deducted ${newDeduct} PKR`);
            }

            // Generate and open the PDF slip
            const res = await API.post('/api/reports/employee-deep-dive', { 
                employee_id: parseInt(_wizardEid), 
                month: _wizardMonth 
            });
            
            if (res.ok) {
                window.open(res.data.url, '_blank');
                Toast.success('Salary Issued & Slip ready!');
            } else {
                Toast.error(res.error || 'Failed to generate slip');
            }
        });
    }

    async function monthlyPulse() {
        const month = document.getElementById('reportMonthlyPulseMonth').value;
        if (!month) { Toast.error('Please select a month'); return; }

        await _runBtn('btnMonthlyPulse', 'Generating…', async () => {
            const res = await API.post('/api/reports/monthly-pulse', { month });
            if (res.ok) {
                window.open(res.data.url, '_blank');
                Toast.success('Monthly Pulse PDF ready!');
            } else {
                Toast.error(res.error || 'Failed to generate report');
            }
        });
    }

    async function companyLedger() {
        await _runBtn('btnLedger', 'Generating…', async () => {
            const res = await API.post('/api/reports/company-ledger', { months_back: 3 });
            if (res.ok) {
                window.open(res.data.pdf.url, '_blank');
                // Also trigger CSV download
                const a = document.createElement('a');
                a.href = res.data.csv.url;
                a.download = res.data.csv.filename;
                a.click();
                Toast.success('Company Ledger PDF + CSV ready!');
            } else {
                Toast.error(res.error || 'Failed to generate report');
            }
        });
    }

    async function testEmail() {
        Toast.info('Sending test email…');
        const res = await API.post('/api/system/test-email');
        if (res.ok) Toast.success('Test email sent! Check your inbox.');
        else Toast.error(res.error || 'Email failed — check settings');
    }

    return { init, dailyPulse, deepDive, updateWizardNet, confirmSalaryWizard, monthlyPulse, companyLedger, testEmail };
})();

/* Spin animation for loading icon */
const _styleEl = document.createElement('style');
_styleEl.textContent = '@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}';
document.head.appendChild(_styleEl);
