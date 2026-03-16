import sys
sys.path.insert(0, r'd:\Attendance')
import payroll as pl
import database as db

# Test Zohaib's summary for March 2026
conn = db.get_db()
emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall())
conn.close()

for e in emps:
    s = pl.get_monthly_summary(e['id'], '2026-03')
    if not s: continue
    dm = s['net_debt_minutes']
    ds = (f"+{dm//60}h {dm%60:02d}m" if dm >= 0 else f"-{(-dm)//60}h {(-dm)%60:02d}m")
    status = "Good" if dm >= 0 else "Under"
    print(f"{e['name']:15s} | Present: {s['days_present']:2d} | Absent: {s['days_absent']:2d} | "
          f"Worked: {s['total_worked_hours']:6.1f}h | Req: {s['total_required_hours']:6.1f}h | "
          f"Debt/Surplus: {ds:>10s} | {status}")
