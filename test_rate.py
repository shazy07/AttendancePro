import payroll as pl
from datetime import date
from database import app as db_app

with db_app.app_context():
    print("Testing 30-day hourly rate calculation:")
    
    req = pl.get_full_month_required_hours("2026-03")
    print("Required hours for month 2026-03:", req)
    print("If Salary is 50,000, rate is:", 50000 / req)
