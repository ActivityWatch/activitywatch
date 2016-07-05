API
===

The REST API used by ActivityWatch has a notion of buckets which are used to group data together.
Every bucket can have a set of metadata such as a client name (aw-watcher-afk for example), a hostname (such as 'erik-laptop').

Clients might in the future be able to have read-only or append-only access to buckets, providing additional security and preventing compromised clients from being able to cause a severe security breach.

The API will be described into more detail in the future when the first version has been frozen.

