<div align="center">

# ⏱️ AttendPro

### **Attendance & Workforce Management System**

A modern, full-featured attendance tracking system built with Flask — designed for small-to-medium teams who need reliable time tracking, smart hour recovery, and beautiful on-demand reports.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3%2B-lightgrey?logo=flask)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Deploy](https://img.shields.io/badge/Live-PythonAnywhere-yellow)](https://pythonanywhere.com)

</div>

---

## ✨ Features at a Glance

| Category | Features |
|---|---|
| 🕐 **Time Tracking** | One-click Clock In / Clock Out, real-time status dashboard, live 12-hour AM/PM clock |
| 📊 **Smart Analytics** | Auto-calculated work hours, debt/surplus tracking, hour recovery engine |
| 📋 **PDF Reports** | Daily Pulse, Monthly Pulse, Employee Deep-Dive resume, Company Ledger (PDF + CSV) |
| 🌙 **Ramadan Mode** | One-toggle switch from 11.5h shifts (9AM–8:30PM) to 8.5h shifts (9AM–5:30PM) |
| 📅 **Holiday Engine** | Pakistan holiday presets (Eid, Independence Day, etc.), overtime multipliers (1.5×–2×) |
| 🔒 **Security** | bcrypt-hashed admin login, session management, optional IP subnet locking |
| 📧 **Email Automation** | Auto-generated daily attendance summary via SMTP (Gmail-ready) |
| 🎨 **Premium UI** | Dark/light mode, glassmorphism design, Lottie animations, fully responsive |

---

## 🖥️ Screenshots

<details>
<summary><b>📊 Dashboard — Today's Overview</b></summary>

- Real-time employee status cards (On Track / In Debt / Absent / Day Off)
- One-click Clock In & Clock Out per employee
- Search and filter employees
- Live server clock with 12-hour AM/PM format

</details>

<details>
<summary><b>👥 Employee Management</b></summary>

- Add / Edit / Remove employees
- Track name, designation, department, email, phone
- Manual attendance override with date, time, and status

</details>

<details>
<summary><b>📅 Holiday Management</b></summary>

- Quick presets for Pakistani holidays (Eid-ul-Fitr, Independence Day, etc.)
- Custom overtime multipliers for holiday work
- Automatic Friday weekly-off logic
- Ramadan Mode toggle

</details>

<details>
<summary><b>📋 Report Hub</b></summary>

- **Daily Pulse** — Who's in, who's late, who's absent (PDF)
- **Monthly Pulse** — Full team summary for any month (PDF)
- **Employee Deep-Dive** — One-page performance resume with KPI boxes (PDF)
- **Company Ledger** — Master sheet for last 3 months (PDF + CSV)

</details>

<details>
<summary><b>⚙️ Settings</b></summary>

- Company name customization
- Configurable shift start/end times (standard + Ramadan)
- SMTP email setup (sender, password, recipients)
- IP subnet device lock
- Desktop shortcut creator

</details>

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, Flask, SQLite, APScheduler |
| **Frontend** | Vanilla JS, CSS (glassmorphism), Chart.js, Lottie, Remix Icons |
| **Reports** | ReportLab (PDF generation), CSV export |
| **Auth** | bcrypt password hashing, Flask sessions |
| **Deployment** | Gunicorn, PythonAnywhere / Render |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- pip

### Local Setup

```bash
# Clone the repository
git clone https://github.com/shazy07/AttendancePro.git
cd AttendancePro

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

### Default Login
| Field | Value |
|---|---|
| Username | `Shazil` |
| Password | `shazil786!` |

> ⚠️ **Change the default credentials** by setting `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` environment variables in production.

---

## 🌐 Deployment

### PythonAnywhere (Free)

1. Create a free account at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Clone the repo in a Bash console:
   ```bash
   git clone https://github.com/shazy07/AttendancePro.git
   cd AttendancePro
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements-prod.txt
   ```
3. Add a **Web App** → Manual Configuration → Python 3.10+
4. Edit the WSGI file with your project path and environment variables
5. Reload — your app is live!

### Render (Free Tier)

Push to GitHub and connect to [Render](https://render.com). The included `render.yaml` and `Procfile` handle the rest.

---

## 📁 Project Structure

```
AttendancePro/
├── app.py                 # Flask app — routes, API endpoints, auth
├── database.py            # SQLite schema, init, helpers
├── payroll.py             # Hour calculations, debt/surplus engine
├── scheduler.py           # APScheduler — auto-absence, daily emails
├── reports.py             # PDF report generation (ReportLab)
├── tray.py                # Windows system tray icon (local only)
├── requirements.txt       # Full dependencies (local/Windows)
├── requirements-prod.txt  # Server dependencies (no Windows packages)
├── Procfile               # Gunicorn start command
├── render.yaml            # Render deployment blueprint
├── run.bat                # Windows launcher script
├── templates/
│   ├── index.html         # Main SPA shell — dashboard, employees, etc.
│   └── login.html         # Authentication page
└── static/
    ├── css/style.css       # Full design system — dark/light, glassmorphism
    └── js/
        ├── main.js         # Router, theme, clock, utilities
        ├── dashboard.js    # Dashboard logic — status grid, clock in/out
        ├── employees.js    # Employee CRUD operations
        ├── holidays.js     # Holiday management + Ramadan toggle
        ├── reports.js      # Report generation triggers
        └── settings.js     # Settings load/save
```

---

## 🔌 API Reference

All endpoints require authentication via session cookie.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/login` | Authenticate admin user |
| `GET` | `/api/employees` | List all active employees |
| `POST` | `/api/employees` | Add new employee |
| `PUT` | `/api/employees/:id` | Update employee |
| `DELETE` | `/api/employees/:id` | Soft-delete employee |
| `POST` | `/api/attendance/clockin` | Clock in an employee |
| `POST` | `/api/attendance/clockout` | Clock out an employee |
| `GET` | `/api/attendance/status` | Live status for all employees today |
| `GET` | `/api/attendance/history` | Attendance history (filterable) |
| `POST` | `/api/attendance/manual` | Manual attendance entry/edit |
| `GET` | `/api/holidays` | List holidays for a year |
| `POST` | `/api/holidays` | Add a holiday |
| `DELETE` | `/api/holidays/:id` | Remove a holiday |
| `GET` | `/api/settings` | Get all settings |
| `POST` | `/api/settings` | Update settings |
| `POST` | `/api/reports/daily-pulse` | Generate Daily Pulse PDF |
| `POST` | `/api/reports/monthly-pulse` | Generate Monthly Pulse PDF |
| `POST` | `/api/reports/employee-deep-dive` | Generate Employee Deep-Dive PDF |
| `POST` | `/api/reports/company-ledger` | Generate Company Ledger PDF+CSV |
| `GET` | `/api/system/info` | Server time, hostname, company info |

---

## 🔧 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Flask session secret key |
| `ADMIN_USERNAME` | ❌ | Admin login username (default: `Shazil`) |
| `ADMIN_PASSWORD_HASH` | ❌ | bcrypt hash of admin password |
| `PORT` | ❌ | Server port (default: `5000`) |
| `TZ` | ❌ | Timezone (e.g. `Asia/Karachi`) |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ for efficient workforce management**

[Report Bug](https://github.com/shazy07/AttendancePro/issues) · [Request Feature](https://github.com/shazy07/AttendancePro/issues)

</div>
