FAQ
===

..
   Some of this should probably be moved to a development FAQ.


How do I programmatically use ActivityWatch?
--------------------------------------------

See the documentation for :doc:`extending` or checkout the `aw-client` repository.

How do I understand the data that is stored?
--------------------------------------------

Get some events with

.. code-block:: py

   ac = aw_client.ActivityWatchClient("")

   # Returns a dict with information about every bucket
   buckets = ac.get_buckets()

   # Get the first bucket
   bucket_id = next(buckets.keys())
   events = ac.get_events(bucket_id)

Events from the aw-watcher-afk bucket have the fields `['timestamp']`, `['duration']`, and `['data']['status']`. The status can be one of `afk`, `not-afk`, or `hibernating`. If `e0` and `e1` are consecutive events, you should expect
`e0['timestamp'] + e0['duration'] == e1['timestamp']` (within some milliseconds) and report issues when it is not the case. Actually this is only true for aw-watcher-afk, because aw-watcher-window doesn't record anything when afk or asleep.

In principle, `afk` and `not-afk` events alternate, but there are currently many edge cases where it doesn't happen.

No two events in a bucket should cover the same moment, but right now in some cases `hibernating` events overlap entirely with some `afk` events.

How to determine bucket name?
-----------------------------

`<name of watcher>` (one of `aw-watcher-afk` or `aw-watcher-window`) + `_` + `<name of your machine>` (how to determine? look in "Raw Data" tab of web UI)

What happens when AW is down or crashes?
----------------------------------------

Stored data up to the crash is not corrupted (up to few seconds before). When AW is restarted, it will first register a `not-afk` event. Several `not-afk` can come one after the other if AW is interrupted in between. No data will be stored when AW is off.

What happens when my computer is off or asleep?
-----------------------------------------------

When asleep, aw-watcher-afk will record a "hibernating" event (this might change). aw-watcher-window will record nothing, i.e. some event's timestamp+duration will not match the following event's timestamp. When turned off, no data is logged.

Some events have 0 duration. What does this mean?
-------------------------------------------------

It's a glitch (caused by 3 consecutive heartbeats having different data?).
