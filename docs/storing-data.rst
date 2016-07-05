Storing data
============

The server part of ActivityWatch, aw-server, by default comes with a few methods of storing data. As of 0.1.1 the default is the JSON store which simply stores each bucket in it's own JSON file.

Other methods include:

 - MongoDB
 - In-memory (non-persistent, useful in testing)

