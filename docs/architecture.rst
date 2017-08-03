============
Architecture
============

Here we hope to clarify the architecture of ActivityWatch for you. Please file an issue or pull request if you think something is missing.

Modules
=======

Server
------

Known as aw-server, it handles storage and retrieval of all activities/entries in buckets. Usually there exists one bucket per watcher.

The server also hosts the Web UI (aw-webui) which does all communication with the server using the REST API.

Clients
-------

The server doesn't do anything very interesting on its own, for that we need clients. Most specifically a certain type of client known as watchers.
Writing these clients is something we've tried to make as easy as possible by creating client libraries with a clear API.

Currently the primary client library is written in Python (known simply as aw-client) but a client library written in JavaScript is on the way and is expected to have the same level of support in the future.

Client libraries:

 - aw-client (Python)
 - aw-client-js (JavaScript, work in progress)

Watchers
^^^^^^^^

Since aw-server doesn't do any data collection on it's own, we need watchers that observe the world and sent the data off to aw-server for storage.

Examples of watchers:

 - aw-watcher-afk
 - aw-watcher-window

User interfaces
^^^^^^^^^^^^^^^

Examples of UIs:

 - aw-webui

Libraries
---------

Some of the logic of ActivityWatch is shared across the server and clients, such as the Event model.
Due to this, we've created a common library :code:`aw-core` which includes many of the essentials in ActivityWatch.

