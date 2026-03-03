"""
AttendPro — System Tray App (tray.py)
Run with: pythonw tray.py   (no console window)
Or:        python tray.py   (with console, for debugging)
"""
import sys, os, threading, webbrowser, time
import pystray
from PIL import Image, ImageDraw, ImageFont

# ── Add the app directory to sys.path ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

APP_URL   = 'http://127.0.0.1:5000'
_server   = None
_started  = threading.Event()


# ── Build tray icon (purple clock face, drawn with PIL) ────────────────────────
def _make_icon(size=64):
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad  = 4
    # Background circle — purple gradient effect
    draw.ellipse([pad, pad, size-pad, size-pad], fill='#7c3aed')
    # Inner lighter circle
    draw.ellipse([pad+6, pad+6, size-pad-6, size-pad-6], fill='#6d28d9')
    # Clock hands
    cx, cy = size//2, size//2
    r = size//2 - pad - 2
    # Hour hand (pointing ~10 o'clock)
    draw.line([cx, cy, cx-r*3//8, cy-r*3//5], fill='white', width=max(2, size//24))
    # Minute hand (pointing ~12 o'clock)
    draw.line([cx, cy, cx, cy-r*4//5], fill='white', width=max(2, size//32))
    # Centre dot
    dot = max(2, size//16)
    draw.ellipse([cx-dot, cy-dot, cx+dot, cy+dot], fill='white')
    return img


# ── Flask server thread ────────────────────────────────────────────────────────
def _run_server():
    global _server
    from app import app
    import database as db
    import scheduler as sc
    db.init_db()
    sc.setup_scheduler()

    from werkzeug.serving import make_server
    _server = make_server('0.0.0.0', 5000, app)
    _started.set()
    _server.serve_forever()


def _start_server():
    import threading
    import time
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    # Wait up to 10 seconds for server to be ready
    _started.wait(timeout=10)
    time.sleep(0.4)   # small extra grace period


# ── Tray menu actions ──────────────────────────────────────────────────────────
def _open_app(icon, item):
    webbrowser.open(APP_URL)


def _quit_app(icon, item):
    global _server
    icon.stop()
    if _server:
        _server.shutdown()
    os._exit(0)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print('[AttendPro] Starting server…')
    _start_server()
    print(f'[AttendPro] Server ready at {APP_URL}')

    # Open browser automatically on launch
    webbrowser.open(APP_URL)

    # Build tray
    icon_img = _make_icon(64)
    menu = pystray.Menu(
        pystray.MenuItem('🕐  AttendPro', None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Open AttendPro', _open_app, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', _quit_app),
    )
    tray = pystray.Icon('AttendPro', icon_img, 'AttendPro — Attendance System', menu)
    print('[AttendPro] Tray icon active. Right-click tray icon to Quit.')
    tray.run()


if __name__ == '__main__':
    main()
