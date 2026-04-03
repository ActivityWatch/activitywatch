#!/usr/bin/env python3

import os
import platform
import subprocess
import sys
import tempfile
import webbrowser

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import pystray
    from PIL import Image
else:
    import gi
    import psutil
    gi.require_version('Gtk', '3.0')
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3, Gtk
    from PIL import Image


# Detect installation directory
if IS_WINDOWS:
    if getattr(sys, 'frozen', False):
        _install_dir = os.path.dirname(sys.executable)
    else:
        _install_dir = os.path.dirname(os.path.abspath(__file__))
    binaries = [
        os.path.join(_install_dir, "aw-server-rust", "aw-server-rust.exe"),
        os.path.join(_install_dir, "aw-watcher-afk", "aw-watcher-afk.exe"),
        os.path.join(_install_dir, "aw-watcher-window", "aw-watcher-window.exe"),
    ]
else:
    binaries = [
        '/opt/activitywatch/aw-server-rust/aw-server-rust',
        '/opt/activitywatch/awatcher/aw-awatcher',
    ]


def get_icon():
    """Generate an eye icon in Odoo purple color. Returns PIL Image."""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    for x in range(64):
        for y in range(64):
            pos = (x - 32) ** 2 + (y - 32) ** 2
            if 300 < pos < 900 or pos < 100:
                img.putpixel((x, y), (128, 0, 128, 255))
    return img


def get_icon_path():
    """Save icon to temp file and return path (Linux only)."""
    img = get_icon()
    temp_dir = tempfile.gettempdir()
    icon_path = os.path.join(temp_dir, "my-aw-icon.png")
    img.save(icon_path)
    return icon_path


def systray_already_running():
    if IS_WINDOWS:
        return False
    else:
        return len([p for p in psutil.process_iter(['cmdline']) if p.info['cmdline'] and p.info['cmdline'][-1].endswith('aw-systray-odoo.py')]) > 1


def notify(message):
    if IS_WINDOWS:
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast("Odoo Activity Watch", message, duration=3)
        except ImportError:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Odoo Activity Watch", 0)
    else:
        subprocess.run(['notify-send', "Odoo Activity Watch", message], check=False)


class ActivityWatchMonitor:

    def __init__(self, indicator):
        self.procs = []
        self.indicator = indicator

    def check_extension(self):
        if IS_WINDOWS:
            return
        result = subprocess.run(['gnome-extensions', 'list', '--enabled'], capture_output=True, text=True, check=False)
        if 'focused-window-dbus@flexagoon.com' not in result.stdout.split('\n'):
            subprocess.run(['gnome-extensions', 'enable', 'focused-window-dbus@flexagoon.com'], capture_output=True, text=True, check=False)

    def stop_server(self, widget=None):
        for p in self.procs:
            p.poll()
            if p.returncode is None:
                p.terminate()
        self.procs = []

    def open_ui(self, widget=None):
        webbrowser.open("http://127.0.0.1:5600")

    def about(self, widget=None):
        webbrowser.open("https://www.odoo.com/odoo-19-1-release-notes#:~:text=the%20list%20view.-,Timesheets,-ActivityWatch%20integration")

    def start_server(self, widget=None):
        self.check_extension()
        self.stop_server()
        for binary in binaries:
            if not os.path.exists(binary):
                notify(f"Binary not found: {binary}")
                continue
            startupinfo = None
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            b = subprocess.Popen(binary, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
            b.poll()
            if b.returncode is None:
                self.procs.append(b)
            else:
                b.wait()
                notify(f"{binary} not started")

    def on_quit(self, widget=None):
        self.stop_server()
        if IS_WINDOWS:
            if self.indicator:
                self.indicator.stop()
        else:
            Gtk.main_quit()


def create_menu_linux(indicator, monitor):
    menu = Gtk.Menu()

    item_ui = Gtk.MenuItem(label="ActivityWatch UI")
    item_ui.connect("activate", monitor.open_ui)
    menu.append(item_ui)

    item_start = Gtk.MenuItem(label="Start Server")
    item_start.connect("activate", monitor.start_server)
    menu.append(item_start)

    item_stop = Gtk.MenuItem(label="Stop Server")
    item_stop.connect("activate", monitor.stop_server)
    menu.append(item_stop)

    item_about = Gtk.MenuItem(label="About")
    item_about.connect("activate", monitor.about)
    menu.append(item_about)

    menu.append(Gtk.SeparatorMenuItem())

    item_exit = Gtk.MenuItem(label="Exit")
    item_exit.connect("activate", monitor.on_quit)
    menu.append(item_exit)

    menu.show_all()
    return menu


def create_menu_windows(monitor):
    return (
        pystray.MenuItem("ActivityWatch UI", monitor.open_ui, default=True),
        pystray.MenuItem("Start Server", monitor.start_server),
        pystray.MenuItem("Stop Server", monitor.stop_server),
        pystray.MenuItem("About", monitor.about),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", monitor.on_quit),
    )


if __name__ == '__main__':
    if systray_already_running():
        notify("Systray app is already running !")
        sys.exit(0)

    if IS_WINDOWS:
        icon = get_icon()
        monitor = ActivityWatchMonitor(None)
        indicator = pystray.Icon(
            "Odoo ActivityWatch",
            icon,
            "Odoo ActivityWatch",
            create_menu_windows(monitor)
        )
        monitor.indicator = indicator
        indicator.run()
    else:
        icon_path = get_icon_path()
        indicator = AppIndicator3.Indicator.new(
            "Odoo ActivityWatch",
            icon_path,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        awmon = ActivityWatchMonitor(indicator)
        indicator.set_menu(create_menu_linux(indicator, awmon))

        Gtk.main()
