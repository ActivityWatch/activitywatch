Event model
===========

The ActivityWatch event model is pretty simple, here's its representation in JSON:

.. code-block:: js

   {
     "timestamp": "2016-04-27T15:23:55Z",  # ISO8601 formatted timestamp
     "duration": 3.14,                     # Duration in seconds
     "data": {"key": "value"}  # A JSON object, the schema of this depends on the bucket type
   }

It should be noted that all timestamps are stored as UTC. Timezone information (UTC offset) is currently discarded.
