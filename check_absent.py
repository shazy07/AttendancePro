import sqlite3
conn = sqlite3.connect(r'd:\Attendance\attendance.db')
conn.row_factory = sqlite3.Row

# Check absent records
rows = conn.execute("SELECT employee_id, date, status, required_hours, total_hours, debt_minutes FROM attendance WHERE status='absent' ORDER BY date DESC LIMIT 10").fetchall()
print("=== ABSENT RECORDS ===")
for r in rows:
    print(dict(r))

# Check Zohaib's records for March 2026
print("\n=== ZOHAIB'S MARCH RECORDS ===")
rows2 = conn.execute("SELECT e.name, a.date, a.status, a.required_hours, a.total_hours, a.debt_minutes, a.clock_in, a.clock_out FROM attendance a JOIN employees e ON a.employee_id=e.id WHERE e.name LIKE '%Zohaib%' AND a.date LIKE '2026-03%' ORDER BY a.date").fetchall()
for r in rows2:
    print(dict(r))

# Count workdays in March so far (up to today)
print("\n=== WORKDAY COUNTS FOR MARCH ===")
from datetime import date, timedelta
start = date(2026, 3, 1)
today = date(2026, 3, 11)  
d = start
workdays = 0
while d < today:
    if d.weekday() != 4:  # Not Friday
        workdays += 1
    d += timedelta(days=1)
print(f"Workdays from Mar 1 to Mar 10: {workdays}")

conn.close()
