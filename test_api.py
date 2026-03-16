import app
import json

c = app.app.test_client()

# disable login required
app.app.config['TESTING'] = True

with c.session_transaction() as sess:
    sess['user'] = 'admin'

res = c.put('/api/employees/1', json={
    'name': 'Abdullah',
    'designation': 'Sr. Worker',
    'department': 'Warehouse',
    'email': '',
    'phone': '03296576783',
    'monthly_salary': 27000
})

print("STATUS:", res.status_code)
print("BODY:", res.get_data(as_text=True))
