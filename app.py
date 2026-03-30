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
        '''INSERT INTO employees (name,designation,department,email,phone,monthly_salary)
           VALUES (?,?,?,?,?,?)''',
        (d['name'], d.get('designation',''), d.get('department',''),
         d.get('email',''), d.get('phone',''), float(d.get('monthly_salary') or 0.0))
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
    try:
        conn = db.get_db()
        conn.execute(
            '''UPDATE employees SET name=?,designation=?,department=?,
               email=?,phone=?,monthly_salary=? WHERE id=?''',
            (d.get('name',''), d.get('designation',''), d.get('department',''),
             d.get('email',''), d.get('phone',''), float(d.get('monthly_salary') or 0.0), eid)
        )
        conn.commit()
        row = db.row_to_dict(conn.execute('SELECT * FROM employees WHERE id=?', (eid,)).fetchone())
        conn.close()
        return ok(row)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return err(str(e), 500)


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


@app.route('/api/attendance/bulk-entry', methods=['POST'])
@login_required
def bulk_entry():
    """Bulk enter clock-in or clock-out times for multiple employees at once."""
    d       = request.json or {}
    mode    = d.get('mode')          # 'clock_in' or 'clock_out'
    dt      = d.get('date', today_str())
    entries = d.get('entries', [])    # [{ employee_id, time }, ...]

    if mode not in ('clock_in', 'clock_out'):
        return err('mode must be "clock_in" or "clock_out"')
    if not entries:
        return err('No entries provided')

    req_hours = pl.get_required_hours(dt)
    dtype, holiday = pl.get_day_type(dt)
    ot_mult     = 1.0
    is_hol_work = 0
    status      = 'present'

    if dtype == 'weekly_off':
        status = 'weekly_off'
    elif dtype == 'holiday':
        is_hol_work = 1
        ot_mult     = float(holiday['overtime_multiplier'])
        status      = 'present'

    conn    = db.get_db()
    saved   = 0
    skipped = 0
    errors  = []

    for entry in entries:
        eid      = entry.get('employee_id')
        time_str = (entry.get('time') or '').strip()
        if not eid or not time_str:
            skipped += 1
            continue

        full_dt = f"{dt}T{time_str}:00"   # e.g. 2026-03-05T09:15:00

        try:
            if mode == 'clock_in':
                conn.execute(
                    '''INSERT INTO attendance
                       (employee_id,date,clock_in,required_hours,status,
                        is_holiday_work,overtime_multiplier)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(employee_id,date) DO UPDATE SET
                       clock_in=excluded.clock_in, status=excluded.status,
                       required_hours=excluded.required_hours''',
                    (eid, dt, full_dt, req_hours, status, is_hol_work, ot_mult)
                )
                saved += 1

            else:  # clock_out
                row = db.row_to_dict(
                    conn.execute(
                        'SELECT * FROM attendance WHERE employee_id=? AND date=?',
                        (eid, dt)
                    ).fetchone()
                )
                ci_val = row.get('clock_in') if row else None
                if not ci_val:
                    errors.append(f"Employee {eid}: no clock-in found")
                    continue

                ci_str   = str(ci_val).split('.')[0].replace(' ', 'T').partition('+')[0]
                ci_dt    = datetime.fromisoformat(ci_str)
                co_dt    = datetime.fromisoformat(full_dt)
                delta    = co_dt - ci_dt
                h_float  = float(delta.total_seconds()) / 3600.0
                total_h  = float(f"{h_float:.4f}")
                req_h    = float(row.get('required_hours') or 0.0)
                debt_m   = int((total_h - req_h) * 60)

                conn.execute(
                    '''UPDATE attendance
                       SET clock_out=?, total_hours=?, debt_minutes=?, status=?
                       WHERE employee_id=? AND date=?''',
                    (full_dt, total_h, debt_m, 'present', eid, dt)
                )
                saved += 1

        except Exception as exc:
            errors.append(f"Employee {eid}: {str(exc)}")

    conn.commit()
    conn.close()
    return ok({'saved': saved, 'skipped': skipped, 'errors': errors})


@app.route('/api/attendance/status', methods=['GET'])
@login_required
def attendance_status():
    """Live status for all active employees today (Optimized for fast loading)."""
    ts   = request.args.get('date', today_str())
    
    # 1. Pre-fetch common data once
    dtype, holiday = pl.get_day_type(ts)
    req_hours      = pl.get_required_hours(ts)
    shift_end      = pl.get_shift_end_str(ts)
    
    # Calculate start of month for debt calculation
    try:
        ts_date_obj = datetime.strptime(ts, '%Y-%m-%d')
    except Exception:
        ts_date_obj = datetime.today()
    month_start_str = ts_date_obj.replace(day=1).strftime('%Y-%m-%d')
    
    conn = db.get_db()
    # 2. Get all active employees
    emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall())
    
    # 3. Get all attendance records for today
    att_rows = db.rows_to_list(conn.execute('SELECT * FROM attendance WHERE date=?', (ts,)).fetchall())
    att_map  = {r['employee_id']: r for r in att_rows}
    
    # 4. Get all accumulated debt for active employees up to today (this month)
    debt_rows = db.rows_to_list(conn.execute(
        '''SELECT employee_id, SUM(debt_minutes) as tot_debt FROM attendance
           WHERE date>=? AND date<? AND status NOT IN ("weekly_off","holiday")
           GROUP BY employee_id''',
        (month_start_str, ts)
    ).fetchall())
    debt_map = {r['employee_id']: r['tot_debt'] for r in debt_rows}
    
    conn.close()

    result = []
    now_dt = datetime.now()
    
    for e in emps:
        eid = e['id']
        row = att_map.get(eid)
        
        s = {
            'employee':       e,
            'day_type':       dtype,
            'required_hours': req_hours,
            'holiday_name':   holiday['name'] if holiday else None,
            'clock_in':       None,
            'clock_out':      None,
            'hours_worked':   0.0,
            'debt_minutes':   0,
            'status':         dtype if dtype != 'workday' else 'absent',
            'target_leave':   shift_end,
            'color':          'blue' if dtype in ('weekly_off', 'holiday') else 'red',
        }
        
        if row:
            s['clock_in']     = row['clock_in']
            s['clock_out']    = row['clock_out']
            s['hours_worked'] = row['total_hours']
            s['debt_minutes'] = row['debt_minutes']
            s['status']       = row['status']
            
            if row.get('clock_in') and not row.get('clock_out'):
                ci_str = str(row['clock_in'])
                ci_dt  = datetime.fromisoformat(ci_str.split('.')[0].replace(' ', 'T'))
                elapsed = (now_dt - ci_dt).total_seconds() / 3600.0
                s['hours_worked'] = float(f"{float(elapsed):.2f}")
                debt_so_far = int((float(elapsed) - float(req_hours)) * 60)
                s['debt_minutes'] = debt_so_far
                
                prior = debt_map.get(eid, 0)
                s['target_leave'] = pl.get_target_leave_time(ci_str, req_hours, prior)
            
            debt_val = s.get('debt_minutes')
            debt = int(debt_val) if debt_val is not None else 0
            if s['status'] in ('weekly_off', 'holiday'):
                s['color'] = 'blue'
            elif debt >= 0 and s['status'] == 'present':
                s['color'] = 'green'
            elif debt < -30:
                s['color'] = 'red'
            else:
                s['color'] = 'amber'
                
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
@app.route('/api/advances', methods=['GET'])
@login_required
def get_advances():
    month = request.args.get('month') # YYYY-MM
    conn = db.get_db()
    
    query = '''
        SELECT a.id, a.employee_id, a.date, a.amount, a.type, a.notes, e.name as employee_name
        FROM advance_salaries a
        JOIN employees e ON a.employee_id = e.id
        WHERE 1=1
    '''
    params = []
    if month:
        query += " AND strftime('%Y-%m', a.date) = ?"
        params.append(month)
    
    query += " ORDER BY a.date DESC"
    
    rows = db.rows_to_list(conn.execute(query, params).fetchall())
    conn.close()
    return ok(rows)


@app.route('/api/advances', methods=['POST'])
@login_required
def add_advance():
    d = request.json or {}
    required = ['employee_id', 'date', 'amount']
    if not all(d.get(f) for f in required):
        return err('employee_id, date, and amount are required')
        
    conn = db.get_db()
    adv_type = d.get('type', 'given')
    cur = conn.execute(
        '''INSERT INTO advance_salaries (employee_id, date, amount, type, notes)
           VALUES (?, ?, ?, ?, ?)''',
        (d['employee_id'], d['date'], float(d['amount']), adv_type, d.get('notes', ''))
    )
    conn.commit()
    new_id = cur.lastrowid
    
    row = db.row_to_dict(conn.execute(
        '''SELECT a.*, e.name as employee_name 
           FROM advance_salaries a 
           JOIN employees e ON a.employee_id = e.id 
           WHERE a.id=?''', 
        (new_id,)
    ).fetchone())
    conn.close()
    return ok(row), 201


@app.route('/api/advances/<int:aid>', methods=['DELETE'])
@login_required
def delete_advance(aid):
    conn = db.get_db()
    conn.execute('DELETE FROM advance_salaries WHERE id=?', (aid,))
    conn.commit()
    conn.close()
    return ok({'deleted': aid})


@app.route('/api/advances/ledger', methods=['GET'])
@login_required
def get_advances_ledger():
    conn = db.get_db()
    query = '''
        SELECT 
            e.id as employee_id,
            e.name as employee_name,
            e.designation,
            COALESCE(SUM(CASE WHEN a.type = 'given' THEN a.amount ELSE 0 END), 0) as total_given,
            COALESCE(SUM(CASE WHEN a.type != 'given' THEN a.amount ELSE 0 END), 0) as total_repaid
        FROM employees e
        LEFT JOIN advance_salaries a ON e.id = a.employee_id
        WHERE e.is_active = 1
        GROUP BY e.id
        ORDER BY e.name
    '''
    rows = db.rows_to_list(conn.execute(query).fetchall())
    conn.close()
    
    # Calculate balance
    for r in rows:
        r['balance'] = r['total_given'] - r['total_repaid']
        
    return ok(rows)
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


@app.route('/api/reports/advance-history', methods=['POST'])
@login_required
def report_advance_history():
    d = request.json or {}
    month = d.get('month', '')
    try:
        res = rp.generate_advance_history(month if month else None)
        fname = os.path.basename(res['pdf'])
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


# ── Payroll History & Issuance ──────────────────────────────────────────────

@app.route('/api/payroll/issue', methods=['POST'])
@login_required
def issue_salary():
    d = request.json or {}
    eid = d.get('employee_id')
    month = d.get('month')
    deduction = float(d.get('deduction', 0.0))
    
    if not eid or not month:
        return err('employee_id and month required')
        
    s = pl.get_monthly_summary(eid, month)
    if not s:
        return err('Summary not found for this employee/month')
        
    conn = db.get_db()
    
    # 1. Insert advance deduction into the ledger if a new one was applied in the wizard
    if deduction > 0:
        conn.execute(
            '''INSERT INTO advance_salaries (employee_id, date, amount, type, notes)
               VALUES (?, ?, ?, 'deduction', ?)''',
            (eid, date.today().strftime('%Y-%m-%d'), deduction, f'Salary Wizard Deduction for {month}')
        )
        conn.commit()
        # Re-fetch summary to get updated net salary
        s = pl.get_monthly_summary(eid, month)

    # 2. Upsert payroll_summary
    conn.execute('''
        INSERT INTO payroll_summary 
        (employee_id, month, total_required_hours, total_worked_hours, surplus_hours, short_hours, deduction_amount, net_salary, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'paid')
        ON CONFLICT(employee_id, month) DO UPDATE SET
        total_required_hours=excluded.total_required_hours,
        total_worked_hours=excluded.total_worked_hours,
        surplus_hours=excluded.surplus_hours,
        short_hours=excluded.short_hours,
        deduction_amount=excluded.deduction_amount,
        net_salary=excluded.net_salary,
        status='paid'
    ''', (
        eid, month, 
        s.get('total_required_hours', 0), 
        s.get('total_worked_hours', 0), 
        s.get('surplus_hours', 0), 
        s.get('short_hours', 0), 
        s.get('advance_deductions', 0), 
        s.get('net_salary', 0)
    ))
    conn.commit()
    conn.close()
    
    return ok({'status': 'paid'})


@app.route('/api/payroll/history', methods=['GET'])
@login_required
def get_payroll_history():
    month = request.args.get('month')
    conn = db.get_db()
    
    query = '''
        SELECT p.id, p.employee_id, p.month, p.total_required_hours, p.total_worked_hours,
               p.surplus_hours, p.short_hours, p.deduction_amount, p.net_salary, p.status,
               e.name as employee_name, e.designation
        FROM payroll_summary p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.status = 'paid'
    '''
    params = []
    if month:
        query += " AND p.month = ?"
        params.append(month)
        
    query += " ORDER BY p.month DESC, e.name ASC"
    rows = db.rows_to_list(conn.execute(query, params).fetchall())
    conn.close()
    
    return ok(rows)


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

@app.route('/api/settings/recalculate', methods=['POST'])
@login_required
def recalculate_attendance():
    """Retroactively corrects required_hours and debt_minutes for a date range."""
    d = request.json or {}
    start_date = d.get('start_date')
    end_date = d.get('end_date')
    try:
        hours = float(d.get('hours', 11.5))
    except ValueError:
        return err('Invalid hours')
        
    if not start_date or not end_date or hours <= 0:
        return err('Valid Start Date, End Date, and Hours are required.')

    conn = db.get_db()
    
    # We only update attendance records that actually have a clock_in / total_hours (status=present)
    rows = conn.execute('''
        SELECT employee_id, date, total_hours 
        FROM attendance 
        WHERE date >= ? AND date <= ? AND status IN ('present', 'absent')
    ''', (start_date, end_date)).fetchall()
    
    updated = 0
    for r in rows:
        th = float(r.get('total_hours') or 0.0)
        new_debt = int((th - hours) * 60)
        
        conn.execute('''
            UPDATE attendance 
            SET required_hours = ?, debt_minutes = ? 
            WHERE employee_id = ? AND date = ?
        ''', (hours, new_debt, r['employee_id'], r['date']))
        updated += 1
        
    conn.commit()
    conn.close()
    return ok({'updated': updated})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('\n' + '='*55)
    print('  OK  Attendance & Payroll System is running!')
    print(f'  URL Open http://127.0.0.1:{port} in your browser')
    print('='*55 + '\n')
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
