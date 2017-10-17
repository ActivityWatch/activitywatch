Installing from source
======================

Here's the guide to installing ActivityWatch from source. If you are just looking to try it out, see the getting started guide instead.

.. note::
   This is written for Linux and macOS. For Windows the build process is more complicated and we therefore suggest using the pre-built packages instead on that operating system.

Cloning the submodules
----------------------

Since the ActivityWatch bundlerepo uses submodules, you first need to clone the submodules.

This can either be done at the cloning stage with:

.. code-block:: sh

   git clone --recursive https://github.com/ActivityWatch/activitywatch.git

Or afterwards (if you've already cloned normally) using:

.. code-block:: sh

   git submodule update --init --recursive


Checking dependencies
---------------------

You need to ensure you have:

- Python 3.5 or later, check with :code:`python3 -V` (required to build the core components)
- Node 5 or higher, check with :code:`node -v` and :code:`npm -v` (required to build the web UI)


Using a virtualenv
------------------

You might want to set up a virtualenv so we don't install everything system-wide.

.. note::
   This is currently required, but can be avoided with some minor modifications since some commands (notably those installing Python packages) will need root if not run in a virtualenv (sorry for not making it easier).

.. code-block:: sh

    pip3 install --user virtualenv  # Assuming you don't already have it, you might want to use your systems package manager instead.
    python3 -m venv venv

Now activate the virtualenv in your current shell session:

.. code-block:: sh

    # For bash/zsh users:
    source ./venv/bin/activate
    # For fish users:
    source ./venv/bin/activate.fish


Building and installing
-----------------------

Build and install everything into the virtualenv:

.. code-block:: sh

    make build

Running
-------

Now you should be able to start ActivityWatch **from the terminal where you've activated the virtualenv**.
You have two options:

1. Use the trayicon manager (Recommended for normal use)

   - Run from your terminal with: :code:`aw-qt`

2. Start each module separately (Recommended for developing)

   - Run from your terminal with: :code:`aw-server`, :code:`aw-watcher-afk`, and :code:`aw-watcher-window`

Both methods take the :code:`--testing` flag as a command line parameter to run in testing mode. This runs the server on a different port (5666) and uses a separate database file to avoid mixing your important data with your testing data.

Now everything should be running!
Check out the web UI at http://localhost:5600/

If anything doesn't work, let us know!


Updating from source
--------------------

First pull the latest version of the repo with :code:`git pull` then get the updated submodules with :code:`git submodule update --recursive`. All that's needed then is a :code:`make build`.

If it doesn't work, you can first try to run :code:`make uninstall` and then do a fresh :code:`make build`.
