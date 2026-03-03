import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'attendance.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        designation TEXT    DEFAULT '',
        department  TEXT    DEFAULT '',
        email       TEXT    DEFAULT '',
        phone       TEXT    DEFAULT '',
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_active   INTEGER DEFAULT 1
    )''')


    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id         INTEGER NOT NULL,
        date                DATE    NOT NULL,
        clock_in            DATETIME,
        clock_out           DATETIME,
        total_hours         REAL    DEFAULT 0.0,
        required_hours      REAL    DEFAULT 0.0,
        status              TEXT    DEFAULT 'absent',
        debt_minutes        INTEGER DEFAULT 0,
        is_holiday_work     INTEGER DEFAULT 0,
        overtime_multiplier REAL    DEFAULT 1.0,
        notes               TEXT    DEFAULT '',
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        UNIQUE(employee_id, date)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS holidays (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        date                DATE NOT NULL UNIQUE,
        name                TEXT NOT NULL,
        overtime_multiplier REAL DEFAULT 1.5
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payroll_summary (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id            INTEGER NOT NULL,
        month                  TEXT    NOT NULL,
        total_required_hours   REAL    DEFAULT 0.0,
        total_worked_hours     REAL    DEFAULT 0.0,
        surplus_hours          REAL    DEFAULT 0.0,
        short_hours            REAL    DEFAULT 0.0,
        holiday_overtime_hours REAL    DEFAULT 0.0,
        incentive_amount       REAL    DEFAULT 0.0,
        deduction_amount       REAL    DEFAULT 0.0,
        computed_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        UNIQUE(employee_id, month)
    )''')

    defaults = [
        ('ramadan_mode',              'false'),
        ('standard_shift_start',      '09:00'),
        ('standard_shift_end',        '20:30'),
        ('ramadan_shift_end',         '17:30'),
        ('standard_hours',            '11.5'),
        ('ramadan_hours',             '8.5'),
        ('default_overtime_multiplier','1.5'),
        ('allowed_ip_subnet',         ''),
        ('email_sender',              ''),
        ('email_password',            ''),
        ('email_recipients',          ''),
        ('smtp_host',                 'smtp.gmail.com'),
        ('smtp_port',                 '587'),
        ('company_name',              'My Company'),
    ]
    for key, value in defaults:
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))

    # Seed sample employees only once
    if c.execute('SELECT COUNT(*) FROM employees').fetchone()[0] == 0:
        samples = [
            ('Ahmed Ali',    'Software Engineer', 'IT',              'ahmed@company.com', '+92-300-0000001'),
            ('Sara Khan',    'HR Manager',        'Human Resources', 'sara@company.com',  '+92-300-0000002'),
            ('Bilal Hassan', 'Senior Accountant', 'Finance',         'bilal@company.com', '+92-300-0000003'),
            ('Zara Ahmed',   'UI/UX Designer',    'Creative',        'zara@company.com',  '+92-300-0000004'),
            ('Omar Sheikh',  'Sales Executive',   'Sales',           'omar@company.com',  '+92-300-0000005'),
        ]
        for emp in samples:
            c.execute(
                'INSERT INTO employees (name,designation,department,email,phone) VALUES (?,?,?,?,?)',
                emp
            )

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_db()
    row  = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (key, str(value)))
    conn.commit()
    conn.close()


def archive_old_records():
    """Delete attendance records (with clock_out) older than 90 days."""
    conn    = get_db()
    cutoff  = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    deleted = conn.execute(
        'DELETE FROM attendance WHERE date < ? AND clock_out IS NOT NULL', (cutoff,)
    ).rowcount
    conn.commit()
    conn.close()
    return deleted
