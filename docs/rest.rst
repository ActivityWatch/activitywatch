REST API
========

ActivityWatch uses a REST API for all communication between aw-server and clients.
Most applications should never use HTTP directly but should instead use the client libraries available.
If no such library yet exists for a given language, this document is meant to provide enough specification to create one.

.. warning::
    The API is currently under development, and is subject to change.
    It will be documented in better detail when first version has been frozen.

.. note::
    Part of the documentation might be outdated, you can get up-to-date API documentation
    in the API browser available from the web UI of your aw-server instance.


API Security
------------

.. note::
    Our current security consists only of not allowing non-localhost connections, this is likely to be the case for quite a while.

Clients might in the future be able to have read-only or append-only access to buckets, providing additional security and preventing compromised clients from being able to cause a severe security breach.
All clients will probably also encrypt data in transit.


Buckets API
-----------

The most common API used by ActivityWatch clients is the API providing read and append access buckets.
Buckets are data containers used to group data together which shares some metadata (such as client type, hostname or location).

The basic API endpoints are as follows:


Get bucket
^^^^^^^^^^

.. code-block:: shell

    GET /api/0/buckets/<bucket_id>


Create bucket
^^^^^^^^^^^^^

.. code-block:: shell

    POST /api/0/buckets/<bucket_id>


Events API
-----------

The most common API used by ActivityWatch clients is the API providing read and append access buckets.
Buckets are data containers used to group data together which shares some metadata (such as client type, hostname or location).

The basic API endpoints are as follows:

Get events
^^^^^^^^^^

.. code-block:: shell

    GET /api/0/buckets/<bucket_id>/events


Create event
^^^^^^^^^^^^

.. code-block:: shell

    POST /api/0/buckets/<bucket_id>/events


Heartbeat API
-------------

.. warning::
    Experimental API, not yet ready for use.




