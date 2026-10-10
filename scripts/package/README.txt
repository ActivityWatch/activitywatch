ActivityWatch (Tauri edition) for Linux

aw-tauri/aw-tauri.AppImage is self-contained: the window and AFK watcher
(aw-awatcher, works on Wayland and X11), aw-sync and aw-notify (notifications,
enable them from the tray menu) are bundled inside it.
Put it wherever you like (e.g. ~/bin) and run it from there. Once autostart
is on, keep it in that place: autostart starts the AppImage from where it
was.

To install system-wide instead, use aw-tauri/aw-tauri.deb or
aw-tauri/aw-tauri.rpm. They contain the same bundled modules.

The other folders here are optional extra modules: aw-watcher-input, and the
classic aw-watcher-window / aw-watcher-afk for X11. To use one, copy its
folder into ~/.local/share/activitywatch/aw-tauri/modules/ (or
$XDG_DATA_HOME/activitywatch/aw-tauri/modules/ if you set XDG_DATA_HOME) and
restart ActivityWatch. Your own modules can go there too: the executable must
start with aw- and have no extension (e.g. no .sh).
