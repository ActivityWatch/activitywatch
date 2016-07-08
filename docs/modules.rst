Modules
=======

Server
------

Known as aw-server, it handles storage and retrieval of all activities/entries in buckets. Usually there exists one bucket per client.

Watchers/Clients
----------------

Since aw-server doesn't do any data collection on it's own, we need watchers that observe the world and sent the data off to aw-server for storage.


Libraries
---------

Since all watchers need a common set of client functionality, such as calling the APIs and handling when a server is unavailable, this behavior has been extracted to a set of client libraries.

Currently the primary client library is written in Python, and known simply as aw-client, but a client library written in JavaScript is on the way and will have the same level of support in the future.

