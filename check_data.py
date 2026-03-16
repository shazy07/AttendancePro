import sqlite3
conn = sqlite3.connect(r'd:\Attendance\attendance.db')
conn.row_factory = sqlite3.Row

# See ALL March 2026 attendance for everybody
print("=== ALL MARCH 2026 ATTENDANCE ===")
rows = conn.execute("""
    SELECT e.name, a.date, a.status, a.required_hours, a.total_hours, a.debt_minutes
    FROM attendance a JOIN employees e ON a.employee_id=e.id 
    WHERE a.date LIKE '2026-03%' 
    ORDER BY e.name, a.date
""").fetchall()
for r in rows:
    print(f"{r['name']:15s} | {r['date']} | {r['status']:10s} | req={r['required_hours']:5.1f} | worked={r['total_hours']:6.2f} | debt_m={r['debt_minutes']}")

# Count workdays
print("\n=== WORKDAYS IN MARCH 2026 (up to today Mar 11) ===")
from datetime import date, timedelta
d = date(2026, 3, 1)
today = date(2026, 3, 11)
count = 0
while d <= today:
    wd = d.weekday()  # 4=Friday
    is_friday = wd == 4
    print(f"  {d} ({d.strftime('%A'):10s}) - {'FRIDAY (off)' if is_friday else 'workday'}")
    if not is_friday:
        count += 1
    d += timedelta(days=1)
print(f"Total workdays: {count}")

conn.close()
