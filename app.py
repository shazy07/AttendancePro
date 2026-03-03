import os, json, socket, logging
from datetime import datetime, date
from functools import wraps
from flask import (Flask, request, jsonify, send_from_directory,
                   send_file, render_template, session, redirect, url_for)
import bcrypt

import database as db
import payroll   as pl
import scheduler as sc
import reports   as rp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'attendpro-dev-secret-key-change-me')

# ── Admin Credentials (from environment variables for security) ────────────────
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'Shazil')
# In production, set ADMIN_PASSWORD_HASH env var to a pre-generated bcrypt hash.
# Locally, falls back to hashing the default password on every startup.
_env_hash = os.environ.get('ADMIN_PASSWORD_HASH', '')
ADMIN_PASSWORD_HASH = _env_hash if _env_hash else bcrypt.hashpw(b'shazil786!', bcrypt.gensalt()).decode('utf-8')


def login_required(f):
    """Decorator: redirect to /login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            # API requests get 401 JSON; page requests redirect
            if request.path.startswith('/api/'):
                return jsonify({'ok': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


# ── Bootstrap ──────────────────────────────────────────────────────────────────
db.init_db()
sc.setup_scheduler()


# ── Helpers ────────────────────────────────────────────────────────────────────
def ok(data=None, **kw):
    return jsonify({'ok': True,  'data': data, **kw})

def err(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code

def today_str():
    return date.today().strftime('%Y-%m-%d')

def _check_ip_lock():
    """Return (allowed: bool, message: str)"""
    subnet = db.get_setting('allowed_ip_subnet', '').strip()
    if not subnet:
        return True, ''
    client_ip = request.remote_addr or ''
    if client_ip.startswith(subnet) or client_ip in ('127.0.0.1', '::1'):
        return True, ''
    return False, f'Access denied: IP {client_ip} not in allowed subnet {subnet}'


# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET'])
def login_page():
    if session.get('admin'):
        return redirect('/')
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login_action():
    username = (request.form.get('username') or '').strip()
    password = (request.form.get('password') or '').strip()

    if username == ADMIN_USERNAME and bcrypt.checkpw(
        password.encode('utf-8'), ADMIN_PASSWORD_HASH.encode('utf-8')
    ):
        session['admin'] = True
        session['admin_user'] = username
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Invalid username or password'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ── Shell ──────────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/reports/<path:filename>')
@login_required
def serve_report(filename):
    rdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
    return send_from_directory(rdir, filename, as_attachment=True)


# ── Employees ──────────────────────────────────────────────────────────────────
@app.route('/api/employees', methods=['GET'])
@login_required
def get_employees():
    conn = db.get_db()
    rows = db.rows_to_list(
        conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall()
    )
    conn.close()
    return ok(rows)


@app.route('/api/employees', methods=['POST'])
@login_required
def add_employee():
    d = request.json or {}
    required = ['name']
    if not all(d.get(f) for f in required):
        return err('name is required')
    conn = db.get_db()
    cur  = conn.execute(
        '''INSERT INTO employees (name,designation,department,email,phone)
           VALUES (?,?,?,?,?)''',
        (d['name'], d.get('designation',''), d.get('department',''),
         d.get('email',''), d.get('phone',''))
    )
    conn.commit()
    new_id = cur.lastrowid
    row = db.row_to_dict(conn.execute('SELECT * FROM employees WHERE id=?', (new_id,)).fetchone())
    conn.close()
    return ok(row), 201


@app.route('/api/employees/<int:eid>', methods=['PUT'])
@login_required
def update_employee(eid):
    d = request.json or {}
    conn = db.get_db()
    conn.execute(
        '''UPDATE employees SET name=?,designation=?,department=?,
           email=?,phone=? WHERE id=?''',
        (d.get('name',''), d.get('designation',''), d.get('department',''),
         d.get('email',''), d.get('phone',''), eid)
    )
    conn.commit()
    row = db.row_to_dict(conn.execute('SELECT * FROM employees WHERE id=?', (eid,)).fetchone())
    conn.close()
    return ok(row)


@app.route('/api/employees/<int:eid>', methods=['DELETE'])
@login_required
def delete_employee(eid):
    conn = db.get_db()
    conn.execute('UPDATE employees SET is_active=0 WHERE id=?', (eid,))
    conn.commit()
    conn.close()
    return ok({'deleted': eid})


# ── Attendance ──────────────────────────────────────────────────────────────────
@app.route('/api/attendance/clockin', methods=['POST'])
@login_required
def clock_in():
    allowed, msg = _check_ip_lock()
    if not allowed:
        return err(msg, 403)

    d   = request.json or {}
    eid = d.get('employee_id')
    if not eid:
        return err('employee_id required')

    ts  = today_str()
    now = datetime.now().isoformat(timespec='seconds')

    dtype, holiday = pl.get_day_type()
    req_hours      = pl.get_required_hours()
    ot_mult        = 1.0
    is_hol_work    = 0
    status         = 'present'

    if dtype == 'weekly_off':
        status = 'weekly_off'
    elif dtype == 'holiday':
        is_hol_work = 1
        ot_mult     = float(holiday['overtime_multiplier'])
        status      = 'present'

    conn = db.get_db()
    existing = conn.execute(
        'SELECT * FROM attendance WHERE employee_id=? AND date=?', (eid, ts)
    ).fetchone()

    if existing and existing['clock_in']:
        conn.close()
        return err('Already clocked in today')

    conn.execute(
        '''INSERT INTO attendance
           (employee_id,date,clock_in,required_hours,status,is_holiday_work,overtime_multiplier)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(employee_id,date) DO UPDATE SET
           clock_in=excluded.clock_in, status=excluded.status''',
        (eid, ts, now, req_hours, status, is_hol_work, ot_mult)
    )
    conn.commit()
    conn.close()

    prior_debt = pl.get_accumulated_debt_minutes(eid)
    target     = pl.get_target_leave_time(now, req_hours, prior_debt)
    return ok({'clock_in': now, 'required_hours': req_hours,
               'target_leave': target, 'day_type': dtype})


@app.route('/api/attendance/clockout', methods=['POST'])
@login_required
def clock_out():
    d   = request.json or {}
    eid = d.get('employee_id')
    if not eid:
        return err('employee_id required')

    ts  = today_str()
    now = datetime.now().isoformat(timespec='seconds')

    conn = db.get_db()
    row  = db.row_to_dict(
        conn.execute('SELECT * FROM attendance WHERE employee_id=? AND date=?', (eid, ts)).fetchone()
    )
    if not row:
        conn.close()
        return err('No clock-in record found for today')
    if row.get('clock_out'):
        conn.close()
        return err('Already clocked out today')

    clock_in_val = row.get('clock_in')
    if not clock_in_val:
        conn.close()
        return err('Invalid clock-in data')

    clock_in_str: str = str(clock_in_val)
    clock_in_iso      = clock_in_str.split('.')[0].replace(' ', 'T').partition('+')[0]
    clock_in          = datetime.fromisoformat(clock_in_iso)
    delta             = datetime.fromisoformat(now) - clock_in
    h_float: float    = float(delta.total_seconds()) / 3600.0
    total_h           = float(f"{h_float:.4f}")
    req_h             = float(row.get('required_hours') or 0.0)
    debt_m            = int((total_h - req_h) * 60)

    conn.execute(
        '''UPDATE attendance SET clock_out=?,total_hours=?,debt_minutes=?,status=?
           WHERE employee_id=? AND date=?''',
        (now, total_h, debt_m, 'present', eid, ts)
    )
    conn.commit()
    conn.close()
    return ok({'clock_out': now, 'total_hours': total_h,
               'debt_minutes': debt_m, 'required_hours': req_h})


@app.route('/api/attendance/status', methods=['GET'])
@login_required
def attendance_status():
    """Live status for all active employees today."""
    ts   = request.args.get('date', today_str())
    conn = db.get_db()
    emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall())
    conn.close()
    result = []
    for e in emps:
        s = pl.get_live_status(e['id'], ts)
        s['employee'] = e
        result.append(s)
    return ok(result)


@app.route('/api/attendance/history', methods=['GET'])
@login_required
def attendance_history():
    eid   = request.args.get('employee_id')
    month = request.args.get('month')   # YYYY-MM
    start = request.args.get('start')
    end   = request.args.get('end')

    conn  = db.get_db()
    query = 'SELECT a.*, e.name FROM attendance a JOIN employees e ON a.employee_id=e.id WHERE 1=1'
    params = []

    if eid:
        query  += ' AND a.employee_id=?'; params.append(int(eid))
    if month:
        query  += " AND strftime('%Y-%m',a.date)=?"; params.append(month)
    if start:
        query  += ' AND a.date>=?'; params.append(start)
    if end:
        query  += ' AND a.date<=?'; params.append(end)

    query += ' ORDER BY a.date DESC LIMIT 500'
    rows   = db.rows_to_list(conn.execute(query, params).fetchall())
    conn.close()
    return ok(rows)


@app.route('/api/attendance/manual', methods=['POST'])
@login_required
def manual_attendance():
    """Admin: manually set an attendance record."""
    d    = request.json or {}
    eid  = d.get('employee_id')
    dt   = d.get('date', today_str())
    ci   = d.get('clock_in')
    co   = d.get('clock_out')
    note = d.get('notes', 'Manual entry')

    if not eid:
        return err('employee_id required')

    req_h  = pl.get_required_hours(dt)
    total_h = 0.0
    debt_m  = 0
    if ci and co:
        diff = datetime.fromisoformat(co) - datetime.fromisoformat(ci)
        h_val: float = float(diff.total_seconds()) / 3600.0
        total_h = float(f"{h_val:.4f}")
        debt_m  = int((total_h - req_h) * 60)

    status = d.get('status', 'present' if ci else 'absent')
    conn = db.get_db()
    conn.execute(
        '''INSERT INTO attendance
           (employee_id,date,clock_in,clock_out,total_hours,required_hours,debt_minutes,status,notes)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(employee_id,date) DO UPDATE SET
           clock_in=excluded.clock_in, clock_out=excluded.clock_out,
           total_hours=excluded.total_hours, debt_minutes=excluded.debt_minutes,
           status=excluded.status, notes=excluded.notes''',
        (eid, dt, ci, co, total_h, req_h, debt_m, status, note)
    )
    conn.commit()
    conn.close()
    return ok({'saved': True})


# ── Holidays ────────────────────────────────────────────────────────────────────
@app.route('/api/holidays', methods=['GET'])
@login_required
def get_holidays():
    year = request.args.get('year', date.today().year)
    conn = db.get_db()
    rows = db.rows_to_list(
        conn.execute("SELECT * FROM holidays WHERE strftime('%Y',date)=? ORDER BY date",
                     (str(year),)).fetchall()
    )
    conn.close()
    return ok(rows)


@app.route('/api/holidays', methods=['POST'])
@login_required
def add_holiday():
    d = request.json or {}
    if not d.get('date') or not d.get('name'):
        return err('date and name required')
    conn = db.get_db()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO holidays (date,name,overtime_multiplier) VALUES (?,?,?)',
            (d['date'], d['name'], float(d.get('overtime_multiplier', 1.5)))
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return err(str(e))
    conn.close()
    return ok({'saved': True}), 201


@app.route('/api/holidays/<int:hid>', methods=['DELETE'])
@login_required
def delete_holiday(hid):
    conn = db.get_db()
    conn.execute('DELETE FROM holidays WHERE id=?', (hid,))
    conn.commit()
    conn.close()
    return ok({'deleted': hid})


# ── Settings ────────────────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    conn = db.get_db()
    rows = db.rows_to_list(conn.execute('SELECT * FROM settings').fetchall())
    conn.close()
    # hide password from response
    result = {r['key']: r['value'] for r in rows}
    if 'email_password' in result:
        result['email_password'] = '••••••' if result['email_password'] else ''
    return ok(result)


@app.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    d = request.json or {}
    for key, value in d.items():
        if key == 'email_password' and value == '••••••':
            continue   # don't overwrite with masked value
        db.set_setting(key, value)
    return ok({'saved': True})


# ── Payroll ─────────────────────────────────────────────────────────────────────
@app.route('/api/payroll/monthly/<int:eid>/<month>')
@login_required
def monthly_payroll(eid, month):
    summary = pl.get_monthly_summary(eid, month)
    if not summary:
        return err('Employee not found', 404)
    # daily_records contains sqlite Row dicts — already plain dicts from rows_to_list
    return ok(summary)


@app.route('/api/payroll/all/<month>')
@login_required
def all_monthly_payroll(month):
    conn = db.get_db()
    emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1').fetchall())
    conn.close()
    result = []
    for e in emps:
        s = pl.get_monthly_summary(e['id'], month)
        if s:
            s.pop('daily_records', None)   # keep it lean
            result.append(s)
    return ok(result)


# ── Reports ─────────────────────────────────────────────────────────────────────
@app.route('/api/reports/daily-pulse', methods=['POST'])
@login_required
def report_daily_pulse():
    try:
        path = rp.generate_daily_pulse()
        fname = os.path.basename(path)
        return ok({'url': f'/reports/{fname}', 'filename': fname})
    except Exception as e:
        logger.exception(e)
        return err(str(e))


@app.route('/api/reports/employee-deep-dive', methods=['POST'])
@login_required
def report_deep_dive():
    d     = request.json or {}
    eid   = d.get('employee_id')
    month = d.get('month', date.today().strftime('%Y-%m'))
    if not eid:
        return err('employee_id required')
    try:
        path  = rp.generate_employee_deep_dive(int(eid), month)
        if not path:
            return err('No attendance data found for this employee/month')
        fname = os.path.basename(path)
        return ok({'url': f'/reports/{fname}', 'filename': fname})
    except Exception as e:
        logger.exception(e)
        return err(str(e))


@app.route('/api/reports/monthly-pulse', methods=['POST'])
@login_required
def report_monthly_pulse():
    d     = request.json or {}
    month = d.get('month', date.today().strftime('%Y-%m'))
    try:
        path  = rp.generate_monthly_pulse(month)
        fname = os.path.basename(path)
        return ok({'url': f'/reports/{fname}', 'filename': fname})
    except Exception as e:
        logger.exception(e)
        return err(str(e))


@app.route('/api/reports/company-ledger', methods=['POST'])
@login_required
def report_company_ledger():
    d = request.json or {}
    months_back = int(d.get('months_back', 3))
    try:
        paths  = rp.generate_company_ledger(months_back)
        result = {
            'pdf': {'url': f'/reports/{os.path.basename(paths["pdf"])}', 'filename': os.path.basename(paths["pdf"])},
            'csv': {'url': f'/reports/{os.path.basename(paths["csv"])}', 'filename': os.path.basename(paths["csv"])},
        }
        return ok(result)
    except Exception as e:
        logger.exception(e)
        return err(str(e))


# ── Misc ────────────────────────────────────────────────────────────────────────
@app.route('/api/system/info')
@login_required
def system_info():
    return ok({
        'server_time':  datetime.now().isoformat(timespec='seconds'),
        'today':        today_str(),
        'hostname':     socket.gethostname(),
        'ramadan_mode': db.get_setting('ramadan_mode', 'false'),
        'company':      db.get_setting('company_name', 'My Company'),
    })


@app.route('/api/system/test-email', methods=['POST'])
@login_required
def test_email():
    try:
        sc.send_daily_summary()
        return ok({'sent': True})
    except Exception as e:
        return err(str(e))


@app.route('/api/system/create-shortcut', methods=['POST'])
@login_required
def create_shortcut():
    import subprocess
    try:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'create_shortcut.ps1')
        subprocess.run(['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', script], check=True)
        return ok({'created': True})
    except Exception as e:
        logger.exception(e)
        return err(str(e))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('\n' + '='*55)
    print('  OK  Attendance & Payroll System is running!')
    print(f'  URL Open http://127.0.0.1:{port} in your browser')
    print('='*55 + '\n')
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
