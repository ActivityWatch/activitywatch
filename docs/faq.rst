FAQ
===

..
   Some of this should probably be moved to a development FAQ.

.. note::
   Some of these questions are technically not frequently asked.

How does ActivityWatch know when I am AFK?
------------------------------------------

On Windows and macOS, we use functionality offered by those platforms that gives us the
time since last input.

On Linux, we monitor all mouse and keyboard activity so that we can calculate the time
since last input. We do not store what that activity was, just that it happened.

With this data (seconds since last input) we then check if there is less than 3 minutes
between input activity. If there is, we consider you not-AFK.  If more than 3 minutes
passes without any input, we consider that as if you were AFK from the last input
until the next input occurs.

How do I programmatically use ActivityWatch?
--------------------------------------------

See the documentation for `extending` or checkout the aw-client repository.

How do I understand the data that is stored?
--------------------------------------------

All ActivityWatch data is represented using the `event-model`.

All events from have the fields :code:`timestamp` (ISO 8601 formatted), :code:`duration` (in seconds), and :code:`data` (a JSON object).

You can programmatically get some events yourself to inspect with the following code:

.. code-block:: py

   ac = aw_client.ActivityWatchClient("")

   # Returns a dict with information about every bucket
   buckets = ac.get_buckets()

   # Get the first bucket
   bucket_id = next(buckets.keys())
   events = ac.get_events(bucket_id)

As an example for AFK events: The data object contains has one attribute :code:`status` which can be :code:`afk` or :code:`not-afk`.

..
    If :code:`e0` and :code:`e1` are consecutive events, you should expect :code:`e0.timestamp + e0.duration == e1.timestamp` (within some milliseconds) and report issues when it is not the case.
    Actually this is only true for aw-watcher-afk, because aw-watcher-window doesn't record anything when afk or asleep.
    In principle, `afk` and `not-afk` events alternate, but there are currently many edge cases where it doesn't happen.

No two events in a bucket should cover the same moment, if that happens there is an issue with the watcher that should be resolved.

What happens if it is down or crashes?
--------------------------------------

Since ActivityWatch consists of several modules running independently, one thing crashing will have limited impact on the rest of the system.

If the server crashes, all watchers which use the heartbeat queue should simply queue heartbeats until the server becomes available again.
Since heartbeats are currently sent immediately to the server for storage, all data before the crash should be untouched.

If a watcher crashes, its bucket will simply remain untouched until it is restarted.

What happens when my computer is off or asleep?
-----------------------------------------------

If your computer is off or asleep, watchers will usually record nothing. i.e. one events ending (:code:`timestamp + duration`) will not match up with the following event's beginning (:code:`timestamp`).

Some events have 0 duration. What does this mean?
-------------------------------------------------

Watchers most commonly use a polling method called heartbeats in order to store information on the server.
Heartbeats are received regularly with some data, and when two consecutive heartbeats have identical data they get merged and the duration of the new one becomes the time difference between the previous two.
Sometimes, a single heartbeat doesn't get a following event with identical data. It is then impossible to know the duration of that event.

The assumption could be made to consider all zero-duration events actually have a duration equal to the time of the next event, but all such assumptions are left to the analysis stage.
