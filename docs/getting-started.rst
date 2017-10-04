***************
Getting started
***************

.. note::
    We're currently working on improving the installation experience by creating proper installers and packages,
    but for now we offer standalone archives containing everything you need.

.. Content from aw-server/README.md should be moved here.

Installation
============

.. note::
    The prebuilt executables have been known to sometimes have issues on Linux and macOS.
    If they don't work for you consider `installing-from-source` and filing an issue.

1. First, grab the `latest release from GitHub <https://github.com/ActivityWatch/activitywatch/releases>`_ for your operating system.

2. Unzip the archive into an appropriate directory and you're done!

Usage
=====

The aw-qt application is the easiest way to use ActivityWatch. It creates a trayicon and automatically starts the server and the default watchers.

Simply run the :code:`./aw-qt` binary in the installation directory (either from your terminal or on Windows by double-clicking). You now should see an icon appear in your system tray (unless you're running Gnome 3, where there is no system tray).

You should now also have the web interface running at `<localhost:5600>`_ and will in a few minutes be able to view your data under the Activity section!

.. note::
    If you want more advanced ways to run ActivityWatch (including running it without aw-qt), check out the "Running" section of `installing-from-source`.

Autostart
=========

You might want to make :code:`aw-qt` start automatically on login.
We hope to automate this for you in the future but for now you'll have to do it yourself.
Searching the web for "autostart application <your operating system>" should get you some good results that don't take long.
