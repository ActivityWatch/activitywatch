=========
Changelog
=========

v0.7.0
------

.. note::
    **Unreleased**: Under development, might be preceded by `v0.7.0b4`.

- All issues assigned to the v0.7.0 milestone can be found `on GitHub <https://github.com/ActivityWatch/activitywatch/milestone/4>`_.
- The ActivityWatch WebExtension is now supported from this version forward, see the announcement `on the forum <https://forum.activitywatch.net/t/you-can-now-track-your-web-browsing-with-activitywatch/28>`_.
- Fixed bug on macOS where keyboard activity would not be used to detect AFK state.

v0.7.0b3
--------

- Major improvements to the documentation.
- Even more improvements to the web UI.

v0.7.0b2
--------

- Improved the web UI with more visualization and information for users about the state of the project.

v0.7.0b1
--------

.. note::
    If you are upgrading from a previous version, you might want to stop all loggers for the duration of your UTC offset to prevent issues which we've had difficulty debugging (or you can just start right away and expect your first hours to end up a bit weird).

- Now works on Windows.
- Working standalone packages. (edit: not reliable on all systems, but a lot easier to get running in many cases)
- All timestamps are now in UTC.
- Updated outdated parts of the documentation.
- Makefiles are now used throughout the projects to manage building, testing, and CI.
- A lot of bug fixes (and hopefully not too many bugs).
- Vastly improved code quality.

v0.6.0 and older
----------------

We haven't been keeping track of changes very well for older versions. Please refer to the git history.
