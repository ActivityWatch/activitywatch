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


Event model
-----------

The ActivityWatch event model is pretty simple, here's its representation in JSON:

.. code-block:: js

   {
     "timestamp": "2016-04-27T15:23:55Z",  # ISO8601 formatted timestamp
     "duration": 3.14,                     # Duration in seconds
     "data": {"key": "value"}  # A JSON object, the schema of this depends on the bucket type
   }

It should be noted that all timestamps are stored as UTC. Timezone information (UTC offset) is currently discarded.


API Reference
-------------

.. note::
    This reference is highly incomplete. For an interactive view of the API, try out the API playground running on your local server at: http://localhost:5600/api/

Buckets API
~~~~~~~~~~~

The most common API used by ActivityWatch clients is the API providing read and append access buckets.
Buckets are data containers used to group data together which shares some metadata (such as client type, hostname or location).

Get
^^^

.. code-block:: shell

    GET /api/0/buckets/<bucket_id>

List
^^^^

.. code-block:: shell

    GET /api/0/buckets/

Create
^^^^^^

.. code-block:: shell

    POST /api/0/buckets/<bucket_id>


Events API
~~~~~~~~~~

The most common API used by ActivityWatch clients is the API providing read and append access buckets.
Buckets are data containers used to group data together which shares some metadata (such as client type, hostname or location).

Get events
^^^^^^^^^^

.. code-block:: shell

    GET /api/0/buckets/<bucket_id>/events

Create event
^^^^^^^^^^^^

.. code-block:: shell

    POST /api/0/buckets/<bucket_id>/events

Heartbeat API
~~~~~~~~~~~~~

The heartbeat API is one of the most useful endpoints for writing watchers.

.. code-block:: shell

    POST /api/0/buckets/<bucket_id>/heartbeat

View API
~~~~~~~~~~~~~

.. warning::
   This API should not be relied on. It's messy and has a bunch of issues that we hope to resolve by designing it.

No documentation here, because you shouldn't use it (yet).
