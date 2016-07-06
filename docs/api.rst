API
===

ActivityWatch uses a REST API that binds together aw-server and it's clients.
Most applications should never need to access the API directly but should instead use the client libraries available for the language the application is written in.
If no such library yet exists for a given language, this document is meant to provide enough specification to create one.

.. warning::
    The API is currently under development, and is subject to change.
    It will be documented in better detail when first version has been frozen.

Security
--------

Clients might in the future be able to have read-only or append-only access to buckets, providing additional security and preventing compromised clients from being able to cause a severe security breach.
All clients should have a symmetric key used for encrypting data in transit, since we can't guarantee that hosts can provide valid SSL certificates.

Security is something we shouldn't dare to mess up, so the implementation is likely to be following a KISS approach awaiting further review and proposals of more sophisticated security schemes.

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




