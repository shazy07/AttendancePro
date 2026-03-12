import os, csv, io
from datetime import datetime, date
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import database as db
import payroll as pl

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# ── colour palette ─────────────────────────────────────────────────────────────
C_PURPLE  = colors.HexColor('#7c3aed')
C_CYAN    = colors.HexColor('#06b6d4')
C_GREEN   = colors.HexColor('#10b981')
C_AMBER   = colors.HexColor('#f59e0b')
C_RED     = colors.HexColor('#ef4444')
C_BLUE    = colors.HexColor('#3b82f6')
C_DARK    = colors.HexColor('#1e1b4b')
C_LIGHT   = colors.HexColor('#f8fafc')
C_GREY    = colors.HexColor('#94a3b8')
C_ROW_ALT = colors.HexColor('#f1f5f9')


def _base_doc(filename, page_size=A4):
    path = os.path.join(REPORTS_DIR, filename)
    return SimpleDocTemplate(path, pagesize=page_size,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=1.5*cm,  bottomMargin=1.5*cm), path


def _company():
    return db.get_setting('company_name', 'My Company')


def _header_table(title, subtitle=''):
    styles = getSampleStyleSheet()
    co_style = ParagraphStyle('co', fontSize=18, textColor=C_PURPLE,
                              fontName='Helvetica-Bold', alignment=TA_LEFT)
    ti_style = ParagraphStyle('ti', fontSize=11, textColor=C_DARK,
                              fontName='Helvetica', alignment=TA_LEFT)
    dt_style = ParagraphStyle('dt', fontSize=9, textColor=C_GREY,
                              fontName='Helvetica', alignment=TA_RIGHT)

    now = datetime.now().strftime('%d %b %Y  %H:%M')
    t   = Table([
        [Paragraph(_company(), co_style), Paragraph(f'Generated: {now}', dt_style)],
        [Paragraph(f'{title}{"  —  "+subtitle if subtitle else ""}', ti_style), ''],
    ], colWidths=['70%','30%'])
    t.setStyle(TableStyle([
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    return t


def _status_color(status, debt_minutes):
    if status in ('weekly_off', 'holiday'):  return C_BLUE
    if status == 'absent':                    return C_RED
    if debt_minutes < -30:                   return C_RED
    if debt_minutes < 0:                     return C_AMBER
    return C_GREEN


def _format_time_12h(iso_ts):
    """Convert ISO timestamp to '02:30 PM' format, no seconds."""
    if not iso_ts or iso_ts == '-': return '-'
    try:
        # iso_ts might be '2026-03-02T17:54:26' or '2026-03-02 17:54:26'
        dt = datetime.fromisoformat(str(iso_ts).replace(' ', 'T'))
        return dt.strftime('%I:%M %p')
    except Exception:
        return iso_ts


# ── Daily Pulse ────────────────────────────────────────────────────────────────

def generate_daily_pulse():
    today   = date.today()
    ts      = today.strftime('%Y-%m-%d')
    doc, path = _base_doc(f'daily_pulse_{ts}.pdf', landscape(A4))

    conn = db.get_db()
    emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall())
    conn.close()

    # Gather today's status
    rows_data = []
    reg = {"p": 0, "a": 0, "l": 0}
    for e in emps:
        s = pl.get_live_status(e['id'], ts)
        ci_raw = s.get('clock_in')
        co_raw = s.get('clock_out')
        ci = _format_time_12h(ci_raw) if ci_raw else '-'
        co = _format_time_12h(co_raw) if co_raw else '-'
        h_worked: float = float(s.get('hours_worked') or 0.0)
        hw = f"{int(h_worked)}h {int((h_worked % 1) * 60):02d}m" if ci_raw else '-'
        dm  = int(s.get('debt_minutes') or 0)
        ds_raw   = (f"+{dm//60}h {dm%60:02d}m" if dm >= 0 else f"-{(-dm)//60}h {(-dm)%60:02d}m")
        # Show debt if they clocked in OR if they are marked absent (which means they owe the full day)
        debt_str = ds_raw if (s.get('clock_in') or str(s.get('status')) == 'absent') else '-'
        color    = _status_color(str(s.get('status', 'absent')), dm)

        stat = str(s.get('status', 'absent'))
        if   stat == 'present':
            if dm >= 0: reg["p"] = reg["p"] + 1
            else:       reg["l"] = reg["l"] + 1
        elif stat == 'absent':
            reg["a"] = reg["a"] + 1

        rows_data.append((e.get('name', 'N/A'), e.get('designation', '-'), e.get('department', '-'),
                          ci, co, hw, debt_str, stat.replace('_',' ').title(), color))

    # Summary bar
    styles = getSampleStyleSheet()
    total  = len(emps)
    summ   = f"Total: {total}  |  On-Track: {reg['p']}  |  Late/Debt: {reg['l']}  |  Absent: {reg['a']}"

    # Table
    header = ['Employee', 'Role', 'Dept', 'Clock In', 'Clock Out', 'Hours', 'Debt/Surplus', 'Status']
    table_data = [header] + [r[:8] for r in rows_data]
    col_w = [4.5*cm, 4*cm, 3*cm, 3.5*cm, 3.5*cm, 2.5*cm, 3.2*cm, 3*cm]

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    style = TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), C_PURPLE),
        ('TEXTCOLOR',    (0,0), (-1,0), colors.white),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 8),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_LIGHT, C_ROW_ALT]),
        ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
    ])
    for i, r in enumerate(rows_data, 1):
        style.add('TEXTCOLOR', (7,i), (7,i), r[8])
        style.add('FONTNAME',  (7,i), (7,i), 'Helvetica-Bold')
    tbl.setStyle(style)

    s_style = ParagraphStyle('s', fontSize=9, textColor=C_DARK, fontName='Helvetica-Bold')
    elements = [
        _header_table('Daily Pulse Report', today.strftime('%A, %d %B %Y')),
        Spacer(1, 0.3*cm),
        HRFlowable(width='100%', color=C_PURPLE, thickness=1.5),
        Spacer(1, 0.2*cm),
        Paragraph(summ, s_style),
        Spacer(1, 0.3*cm),
        tbl,
    ]
    doc.build(elements)
    return path


# ── Monthly Pulse ──────────────────────────────────────────────────────────────

def generate_monthly_pulse(month=None):
    if not month:
        month = date.today().strftime('%Y-%m')
    
    doc, path = _base_doc(f'monthly_pulse_{month}.pdf', landscape(A4))
    
    conn = db.get_db()
    emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall())
    conn.close()

    rows_data = []
    
    for e in emps:
        s = pl.get_monthly_summary(e['id'], month)
        if not s: continue
        
        dm = s['net_debt_minutes']
        ds = (f"+{dm//60}h {dm%60:02d}m" if dm >= 0 else f"-{(-dm)//60}h {(-dm)%60:02d}m")
        
        # Color based on net debt
        color = C_GREEN if dm >= 0 else (C_RED if dm < -600 else C_AMBER)
        
        rows_data.append([
            e['name'],
            e['designation'],
            str(s['days_present']),
            str(s['days_absent']),
            f"{int(s['total_worked_hours'])}h {int((s['total_worked_hours'] % 1) * 60):02d}m",
            ds,
            "Good" if dm >= 0 else "Under",
            color
        ])

    # Table
    header = ['Employee', 'Designation', 'Present', 'Absent', 'Total Hours', 'Debt/Surplus', 'Status']
    table_data = [header] + [r[:7] for r in rows_data]
    col_w = [5*cm, 5*cm, 2.5*cm, 2.5*cm, 3*cm, 4*cm, 3.5*cm]

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    style = TableStyle([
        ('BACKGROUND',   (0,0), (-1,0), C_PURPLE),
        ('TEXTCOLOR',    (0,0), (-1,0), colors.white),
        ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 8.5),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_LIGHT, C_ROW_ALT]),
        ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
    ])
    for i, r in enumerate(rows_data, 1):
        style.add('TEXTCOLOR', (6,i), (6,i), r[7])
        style.add('FONTNAME',  (6,i), (6,i), 'Helvetica-Bold')
    tbl.setStyle(style)

    # Grab period info from first summary
    req_per_day = pl.get_required_hours()
    first_summary = None
    for e in emps:
        first_summary = pl.get_monthly_summary(e['id'], month)
        if first_summary:
            break
    workday_count = first_summary['workday_count'] if first_summary else 0
    cutoff_date   = first_summary['cutoff_date'] if first_summary else ''
    total_req_h   = round(workday_count * req_per_day, 1)

    dt = datetime.strptime(month, '%Y-%m')
    month_start = '01 ' + dt.strftime('%b')
    period_str = f"Period: {month_start} – {cutoff_date} {dt.strftime('%Y')}  |  Workdays: {workday_count}  |  Required: {req_per_day:.1f}h/day  ({int(total_req_h)}h {int((total_req_h % 1)*60):02d}m total)"

    styles = getSampleStyleSheet()
    info_style = ParagraphStyle('info', fontSize=9, textColor=C_DARK, fontName='Helvetica-Bold')

    elements = [
        _header_table('Monthly Pulse Report', dt.strftime('%B %Y')),
        Spacer(1, 0.3*cm),
        HRFlowable(width='100%', color=C_PURPLE, thickness=1.5),
        Spacer(1, 0.2*cm),
        Paragraph(period_str, info_style),
        Spacer(1, 0.3*cm),
        tbl,
    ]
    doc.build(elements)
    return path


# ── Employee Deep-Dive ─────────────────────────────────────────────────────────

def generate_employee_deep_dive(employee_id, month):
    summary = pl.get_monthly_summary(employee_id, month)
    if not summary:
        return None

    emp   = summary['employee']
    fname = f"deepdive_{emp['name'].replace(' ','_')}_{month}.pdf"
    doc, path = _base_doc(fname)

    # KPI boxes
    kpis  = [
        ('Days Present', str(summary['days_present']),         C_GREEN),
        ('Days Absent',  str(summary['days_absent']),          C_RED),
        ('Hours Worked', f"{int(summary['total_worked_hours'])}h {int((summary['total_worked_hours'] % 1) * 60):02d}m", C_CYAN),
        ('Surplus Hrs',  f"{int(summary['surplus_hours'])}h {int((summary['surplus_hours'] % 1) * 60):02d}m",   C_GREEN),
        ('Short Hrs',    f"{int(summary['short_hours'])}h {int((summary['short_hours'] % 1) * 60):02d}m",     C_AMBER),
    ]

    kpi_table_data = [[Paragraph(f"<b>{v}</b><br/><font size=7 color='grey'>{k}</font>", 
                                  ParagraphStyle('kp', fontSize=11, alignment=TA_CENTER,
                                                 textColor=c)) for k,v,c in kpis]]
    kpi_tbl = Table(kpi_table_data, colWidths=[2.8*cm]*5)
    kpi_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), C_ROW_ALT),
        ('BOX',           (0,0), (-1,-1), 0.5, C_GREY),
        ('INNERGRID',     (0,0), (-1,-1), 0.5, colors.white),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
    ]))

    # Daily detail table
    header = ['Date', 'Day', 'Req Hrs', 'Clock In', 'Clock Out', 'Worked', 'Debt/Surplus', 'Status']
    rows   = []
    for r in summary['daily_records']:
        d    = datetime.strptime(r['date'], '%Y-%m-%d')
        dm   = r['debt_minutes']
        ds   = (f"+{dm//60}h {dm%60:02d}m" if dm >= 0 else f"-{(-dm)//60}h {(-dm)%60:02d}m")
        ci   = _format_time_12h(r['clock_in'])
        co   = _format_time_12h(r['clock_out'])
        rows.append([d.strftime('%d %b'), d.strftime('%a'),
                     f"{r['required_hours']:.1f}",
                     ci, co, f"{int(r['total_hours'])}h {int((r['total_hours'] % 1) * 60):02d}m", ds,
                     r['status'].replace('_',' ').title()])

    tbl_data = [header] + rows
    col_w    = [2*cm, 1.4*cm, 2*cm, 2.3*cm, 2.3*cm, 2*cm, 3*cm, 3*cm]
    tbl = Table(tbl_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  C_DARK),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_LIGHT, C_ROW_ALT]),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    sub    = f"{emp['name']} - {emp['designation']} | {month}"
    styles = getSampleStyleSheet()
    elements = [
        _header_table('Employee Performance Resume', sub),
        Spacer(1, 0.3*cm),
        HRFlowable(width='100%', color=C_PURPLE, thickness=1.5),
        Spacer(1, 0.3*cm),
        kpi_tbl,
        Spacer(1, 0.4*cm),
        tbl,
    ]
    doc.build(elements)
    return path


# ── Company Ledger ─────────────────────────────────────────────────────────────

def generate_company_ledger(months_back=3):
    from dateutil.relativedelta import relativedelta
    today = date.today()
    months = [(today - relativedelta(months=i)).strftime('%Y-%m') for i in range(months_back-1, -1, -1)]

    conn = db.get_db()
    emps = db.rows_to_list(conn.execute('SELECT * FROM employees WHERE is_active=1 ORDER BY name').fetchall())
    conn.close()

    rows_all = []
    for e in emps:
        for m in months:
            s = pl.get_monthly_summary(e['id'], m)
            if s:
                rows_all.append({
                    'name':       e['name'],
                    'dept':       e['department'],
                    'month':      m,
                    'req_h':      s['total_required_hours'],
                    'worked_h':   s['total_worked_hours'],
                    'surplus_h':  s['surplus_hours'],
                    'short_h':    s['short_hours'],
                })

    # CSV
    ts       = today.strftime('%Y-%m-%d')
    csv_path = os.path.join(REPORTS_DIR, f'company_ledger_{ts}.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=rows_all[0].keys() if rows_all else [])
        w.writeheader()
        w.writerows(rows_all)

    # PDF
    doc, pdf_path = _base_doc(f'company_ledger_{ts}.pdf', landscape(A4))
    header   = ['Employee','Dept','Month','Req Hrs','Worked','Surplus','Short']
    tbl_data = [header]
    for r in rows_all:
        tbl_data.append([r['name'], r['dept'], r['month'],
                         f"{r['req_h']:.1f}", f"{r['worked_h']:.1f}",
                         f"{r['surplus_h']:.1f}", f"{r['short_h']:.1f}"])

    col_w = [4.5*cm, 3.5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    tbl   = Table(tbl_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  C_PURPLE),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 7.5),
        ('ALIGN',         (2,0), (-1,-1), 'CENTER'),
        ('ALIGN',         (0,0), (1,-1),  'LEFT'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_LIGHT, C_ROW_ALT]),
        ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',    (0,0), (-1,-1), 4), ('BOTTOMPADDING',(0,0), (-1,-1), 4),
    ]))

    elements = [
        _header_table('Company Payroll Ledger', f'Last {months_back} Months'),
        Spacer(1, 0.3*cm),
        HRFlowable(width='100%', color=C_PURPLE, thickness=1.5),
        Spacer(1, 0.3*cm),
        tbl,
    ]
    doc.build(elements)
    return {'pdf': pdf_path, 'csv': csv_path}
