from datetime import datetime, date, timedelta
import database as db


# ── helpers ────────────────────────────────────────────────────────────────────

def _parse_date(d):
    if isinstance(d, str):
        s = str(d)
        return datetime.strptime(s.split(' ')[0].split('T')[0], '%Y-%m-%d').date()
    if isinstance(d, datetime):
        return d.date()
    return d


def is_friday(d):
    return _parse_date(d).weekday() == 4


def get_holiday(d):
    ds   = _parse_date(d).strftime('%Y-%m-%d')
    conn = db.get_db()
    row  = conn.execute('SELECT * FROM holidays WHERE date=?', (ds,)).fetchone()
    conn.close()
    return db.row_to_dict(row)


def get_day_type(d=None):
    """Return ('weekly_off'|'holiday'|'workday', holiday_dict|None)."""
    d = _parse_date(d or date.today())
    if is_friday(d):
        return 'weekly_off', None
    h = get_holiday(d)
    if h:
        return 'holiday', h
    return 'workday', None


def get_required_hours(d=None):
    d      = _parse_date(d or date.today())
    dtype, _ = get_day_type(d)
    if dtype in ('weekly_off', 'holiday'):
        return 0.0
    if db.get_setting('ramadan_mode', 'false').lower() == 'true':
        return float(db.get_setting('ramadan_hours', '8.5'))
    return float(db.get_setting('standard_hours', '11.5'))


def get_shift_end_str(d=None):
    d = _parse_date(d or date.today())
    if get_day_type(d)[0] != 'workday':
        return None
    if db.get_setting('ramadan_mode', 'false').lower() == 'true':
        return _to_12h(db.get_setting('ramadan_shift_end', '17:30'))
    return _to_12h(db.get_setting('standard_shift_end', '20:30'))


def _to_12h(time_str):
    """Convert 'HH:MM' (24h) to '8:30 PM' display format."""
    if not time_str:
        return time_str
    try:
        t = datetime.strptime(time_str, '%H:%M')
        return t.strftime('%I:%M %p').lstrip('0') or '12:00 AM'
    except Exception:
        return time_str


# ── debt / target-leave ────────────────────────────────────────────────────────

def get_accumulated_debt_minutes(employee_id, up_to_date=None):
    """Sum of debt_minutes for the current month before today (neg=short, pos=surplus)."""
    today        = date.today()
    up_to_date   = _parse_date(up_to_date or today)
    month_start  = up_to_date.replace(day=1).strftime('%Y-%m-%d')
    up_to_str    = up_to_date.strftime('%Y-%m-%d')

    conn = db.get_db()
    rows = conn.execute(
        '''SELECT debt_minutes FROM attendance
           WHERE employee_id=? AND date>=? AND date<? AND status NOT IN ("weekly_off","holiday")''',
        (employee_id, month_start, up_to_str)
    ).fetchall()
    conn.close()
    return sum(r['debt_minutes'] for r in rows)


def get_target_leave_time(clock_in_str, required_hours, prior_debt_minutes=0):
    """
    prior_debt_minutes: accumulated debt from previous days (negative = in debt, must stay longer).
    Returns target leave time as 'HH:MM' or None.
    """
    if not clock_in_str or required_hours <= 0:
        return None
    clock_in = datetime.fromisoformat(str(clock_in_str).split('.')[0].replace(' ', 'T'))
    # If prior_debt is negative we owe time → add those extra minutes
    extra    = max(0, -prior_debt_minutes)
    total_m  = int(required_hours * 60) + extra
    target   = clock_in + timedelta(minutes=total_m)
    return target.strftime('%I:%M %p').lstrip('0') or '12:00 AM'


def get_live_status(employee_id, today_str=None):
    """Return real-time status dict for an employee for today."""
    today_str = today_str or date.today().strftime('%Y-%m-%d')
    today     = _parse_date(today_str)
    dtype, holiday = get_day_type(today)
    req_hours      = get_required_hours(today)

    conn = db.get_db()
    row  = db.row_to_dict(conn.execute(
        'SELECT * FROM attendance WHERE employee_id=? AND date=?',
        (employee_id, today_str)
    ).fetchone())
    conn.close()

    result = {
        'day_type':       dtype,
        'required_hours': req_hours,
        'holiday_name':   holiday['name'] if holiday else None,
        'clock_in':       None,
        'clock_out':      None,
        'hours_worked':   0.0,
        'debt_minutes':   0,
        'status':         dtype if dtype != 'workday' else 'absent',
        'target_leave':   get_shift_end_str(today),
        'color':          'blue' if dtype in ('weekly_off', 'holiday') else 'red',
    }

    if row:
        result['clock_in']     = row['clock_in']
        result['clock_out']    = row['clock_out']
        result['hours_worked'] = row['total_hours']
        result['debt_minutes'] = row['debt_minutes']
        result['status']       = row['status']

        if row.get('clock_in') and not row.get('clock_out'):
            ci_str: str = str(row['clock_in'])
            ci_dt       = datetime.fromisoformat(ci_str.split('.')[0].replace(' ', 'T'))
            elapsed     = (datetime.now() - ci_dt).total_seconds() / 3600.0
            result['hours_worked'] = float(f"{float(elapsed):.2f}")
            debt_so_far = int((float(elapsed) - float(req_hours)) * 60)
            result['debt_minutes'] = debt_so_far

            prior = get_accumulated_debt_minutes(employee_id, today)
            result['target_leave'] = get_target_leave_time(ci_str, req_hours, prior)

        # colour coding
        debt_val = result.get('debt_minutes')
        debt = int(debt_val) if debt_val is not None else 0
        if result['status'] in ('weekly_off', 'holiday'):
            result['color'] = 'blue'
        elif debt >= 0 and result['status'] == 'present':
            result['color'] = 'green'
        elif debt < -30:
            result['color'] = 'red'
        else:
            result['color'] = 'amber'

    return result


# ── monthly summary ────────────────────────────────────────────────────────────

def get_monthly_summary(employee_id, month):
    """month: 'YYYY-MM'. Returns attendance summary."""
    conn = db.get_db()
    rows = db.rows_to_list(conn.execute(
        "SELECT * FROM attendance WHERE employee_id=? AND strftime('%Y-%m',date)=?",
        (employee_id, month)
    ).fetchall())
    emp  = db.row_to_dict(conn.execute('SELECT * FROM employees WHERE id=?', (employee_id,)).fetchone())
    conn.close()

    if not emp:
        return None

    total_req    = sum(r['required_hours'] for r in rows)
    total_worked = sum(r['total_hours'] for r in rows)
    net_debt_m   = sum(r['debt_minutes'] for r in rows)

    surplus_h = round(max(0,  net_debt_m) / 60, 2)
    short_h   = round(max(0, -net_debt_m) / 60, 2)

    total_required = float(f"{float(total_req):.2f}")
    total_actual   = float(f"{float(total_worked):.2f}")

    return {
        'employee':             emp,
        'month':                month,
        'days_present':         sum(1 for r in rows if r['status'] == 'present'),
        'days_absent':          sum(1 for r in rows if r['status'] == 'absent'),
        'days_off':             sum(1 for r in rows if r['status'] in ('weekly_off', 'holiday')),
        'total_required_hours': total_required,
        'total_worked_hours':   total_actual,
        'net_debt_minutes':     net_debt_m,
        'surplus_hours':        surplus_h,
        'short_hours':          short_h,
        'daily_records':        rows,
    }
