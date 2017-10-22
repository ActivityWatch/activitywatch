=========
Changelog
=========

.. warning::
    We haven't gotten to the point where we keep a flawless changelog yet. Please refer to the git history for more detail and certainty.

Released
========

v0.7.0b4
--------

- The ActivityWatch WebExtension is now supported from this version forward, see the announcement `on the forum <https://forum.activitywatch.net/t/you-can-now-track-your-web-browsing-with-activitywatch/28>`_.
- Fixed pesky timezone issue in web UI (`issue #117 <https://github.com/ActivityWatch/activitywatch/issues/117>`_).
- Fixed bug on macOS where keyboard activity would not be used to detect AFK state.
- Fixed packaging bugs (macOS, PyInstaller).
- The web extension now has a better look and notifies if connection to server failed.

v0.7.0b3
--------

- Even more improvements to the web UI.
- Major improvements to the documentation, notably instructions on how to install from builds and sources.

v0.7.0b2
--------

- Improvements to the web UI: a new visualization method (the "today" view) and information for users about the state of the project on the first page.

v0.7.0b1
--------

There have been several major changes since v0.6. Much of it wont end up here but hopefully the major things will.

.. note::
    If you are upgrading from a previous version, you might want to stop all loggers for the duration of your UTC offset to prevent issues which we've had difficulty debugging (or you can just start right away and expect your first hours to end up a bit weird).

- Now works on Windows.
- Working standalone packages. (edit: not reliable on all systems, but a lot easier to get running in many cases)
- All timestamps are now in UTC.
- Updated outdated parts of the documentation.
- Makefiles are now used throughout the projects to manage building, testing, and CI.
- A lot of bug fixes (and hopefully not too many new bugs).
- Vastly improved code quality.

v0.6.0 and older
----------------

We haven't been keeping track of changes very well for older versions. Please refer to the git history.

Upcoming
========

.. warning::
    **Unreleased**: These are planned changelogs and will therefore change when plans change.

v0.7.0
------

- All issues assigned to the v0.7.0 milestone can be found `on GitHub <https://github.com/ActivityWatch/activitywatch/milestone/4>`_.
- Not much yet (since `v0.7.0b4`).

v0.7.1 (planned)
----------------

- New query2 API for querying and transforming data
- Web UI now has a view for the most-visited domains

