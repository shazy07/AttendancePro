import sqlite3
c = sqlite3.connect('attendance.db')
c.row_factory = sqlite3.Row
print(dict(c.execute("SELECT * FROM employees WHERE name='Abdullah'").fetchone()))
