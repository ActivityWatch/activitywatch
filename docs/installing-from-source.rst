Installing from source
======================

Here's the guide to installing ActivityWatch from source. If you are just looking to try it out, see the getting started guide instead.

.. note::
   This guide has only been tested on Linux. It's expected to work with minimal modification on macOS as well but will require some extra (undocumented) work on Windows.

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

Running it
----------

Now you should be able to start ActivityWatch, you have two options:

1. Recommended for normal use: Use the trayicon manager (aw-qt)
2. Recommended for developing: Run each module separately (aw-server, aw-watcher-afk, aw-watcher-window)

   - Use the :code:`--testing` flag for each module to run in testing mode. This runs the server of a different port (5666) and uses a separate database file to avoid mixing your important data with your testing data.

Now everything should be running!
Check out the web UI at http://localhost:5600/

If anything doesn't work, let us know!
