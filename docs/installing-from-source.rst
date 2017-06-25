Installing from source
======================

 .. code-block:: ruby

    # Ensure you have Python 3.5 or later installed
    python3 -V

    # You'll also need npm v5 or later to build the web UI.
    npm -v

    # Now you probably want to set up a virtualenv so we don't install everything system-wide.
    sudo pip3 install virtualenv  # Assuming you don't already have it, you might want to use your systems package manager instead.
    python3 -m venv venv
    # Now you need to activate the virtualenv
    # For bash/zsh users: source ./venv/bin/activate
    # For fish users:     source ./venv/bin/activate.fish

    # Now we build and install everything into the virtualenv.
    make build

    # Now you should be able to start ActivityWatch
    # Either use the trayicon manager:
    aw-qt
    # Or run each module seperately:
    aw-server
    aw-watcher-afk
    aw-watcher-window

    # Now everything should be running!
    # You can see your data at http://localhost:5600/

If anything doesn't work, let us know!
