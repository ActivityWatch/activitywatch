Run move-to-aw-modules.sh to copy all modules except aw-tauri to ~/aw-modules/.
aw-tauri (replaces aw-qt) will use this directory to discover new modules.
You can add your own modules and scripts to this directory. The modules should
start with the aw- prefix and should not have an extension (e.g. no .sh).

In the aw-tauri folder there are AppImage, RPM, and DEB binaries. Choose the
appropriate one for your Linux distribution. If in doubt, use the AppImage as
it works on most Linux systems. If you use the AppImage, copy it to a permanent
folder like ~/bin or /usr/local/bin, since autostart relies on the AppImage
being in the same location each time.
