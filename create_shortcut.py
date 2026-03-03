"""
create_shortcut.py
Run ONCE after installing Python to create:
  • A Desktop shortcut (AttendPro.lnk)
  • A Start Menu shortcut
  • Optional: Windows Startup entry (auto-start with PC)
"""
import os, sys, winreg, subprocess

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PYTHONW    = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
TRAY_PY    = os.path.join(BASE_DIR, 'tray.py')
ICON_ICO   = os.path.join(BASE_DIR, 'static', 'attendpro.ico')
DESKTOP    = os.path.join(os.path.expanduser('~'), 'Desktop')
START_MENU = os.path.join(os.path.expanduser('~'),
             'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs')


def _make_ico():
    """Generate attendpro.ico from the same PIL drawing used in tray.py."""
    try:
        from PIL import Image, ImageDraw
        sizes = [16, 32, 48, 64, 128, 256]
        imgs  = []
        for s in sizes:
            img  = Image.new('RGBA', (s, s), (0,0,0,0))
            draw = ImageDraw.Draw(img)
            pad  = max(1, s//16)
            draw.ellipse([pad,pad,s-pad,s-pad], fill='#7c3aed')
            draw.ellipse([pad+s//8+1,pad+s//8+1,s-pad-s//8-1,s-pad-s//8-1], fill='#6d28d9')
            cx,cy = s//2,s//2
            r = s//2 - pad - 1
            lw = max(1, s//20)
            draw.line([cx,cy,cx-r*3//8,cy-r*3//5], fill='white', width=lw)
            draw.line([cx,cy,cx,cy-r*4//5],         fill='white', width=lw)
            dot = max(1, s//14)
            draw.ellipse([cx-dot,cy-dot,cx+dot,cy+dot], fill='white')
            imgs.append(img)
        os.makedirs(os.path.dirname(ICON_ICO), exist_ok=True)
        imgs[-1].save(ICON_ICO, format='ICO', sizes=[(s,s) for s in sizes], append_images=imgs[:-1])
        print(f'  ✓ Icon saved: {ICON_ICO}')
        return ICON_ICO
    except Exception as e:
        print(f'  ⚠ Could not create icon ({e}) — shortcut will use default icon')
        return ''


def _vbs_shortcut(link_path, target, args='', icon_path='', description='AttendPro'):
    """Create a .lnk shortcut via VBScript (no external deps needed)."""
    vbs = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
Set oLink = oWS.CreateShortcut("{link_path}")
oLink.TargetPath = "{target}"
oLink.Arguments = "{args}"
oLink.WorkingDirectory = "{BASE_DIR}"
oLink.Description = "{description}"
oLink.WindowStyle = 1
{"oLink.IconLocation = " + chr(34) + icon_path + chr(34) if icon_path else ""}
oLink.Save
'''.strip()
    vbs_path = os.path.join(BASE_DIR, '_tmp_shortcut.vbs')
    with open(vbs_path, 'w') as f:
        f.write(vbs)
    subprocess.run(['cscript', '//nologo', vbs_path], check=True, capture_output=True)
    os.remove(vbs_path)
    print(f'  ✓ Shortcut: {link_path}')


def _add_to_startup(enable=True):
    """Add/remove AttendPro from Windows Startup (HKCU run key)."""
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    cmd      = f'"{PYTHONW}" "{TRAY_PY}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, 'AttendPro', 0, winreg.REG_SZ, cmd)
                print('  ✓ Added to Windows Startup (auto-starts with PC)')
            else:
                try:
                    winreg.DeleteValue(key, 'AttendPro')
                    print('  ✓ Removed from Windows Startup')
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f'  ⚠ Could not modify startup: {e}')


def main():
    print('\n╔═══════════════════════════════════╗')
    print('║  AttendPro — Shortcut Creator     ║')
    print('╚═══════════════════════════════════╝\n')

    if not os.path.exists(PYTHONW):
        print(f'ERROR: pythonw.exe not found at {PYTHONW}')
        print('Make sure Python is properly installed and run.bat was used at least once.')
        input('\nPress Enter to exit…')
        return

    icon = _make_ico()
    args_str = f'"{TRAY_PY}"'

    print('\n[1/3] Creating Desktop shortcut…')
    _vbs_shortcut(os.path.join(DESKTOP, 'AttendPro.lnk'), PYTHONW, args_str, icon)

    print('[2/3] Creating Start Menu shortcut…')
    _vbs_shortcut(os.path.join(START_MENU, 'AttendPro.lnk'), PYTHONW, args_str, icon)

    print('[3/3] Auto-start with Windows?')
    ans = input('        Start AttendPro automatically when the PC boots? [y/N]: ').strip().lower()
    _add_to_startup(ans == 'y')

    print('\n✅  Done! You can now double-click the AttendPro icon on your Desktop.')
    print('    Right-click the tray icon (bottom-right clock area) to Quit.\n')
    input('Press Enter to exit…')


if __name__ == '__main__':
    main()
