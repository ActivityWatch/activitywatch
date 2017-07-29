Writing your first watcher
==========================

Writing watchers for ActivityWatch is pretty easy, all you need is the :code:`aw-client` library.

A good watcher to study as an example is the `window watcher <https://github.com/ActivityWatch/aw-watcher-window>`_.
Below is a simplified version:

 .. code-block:: python

    client = ActivityWatchClient("aw-watcher-window", testing=True)

    bucket_id = "{}_{}".format(client.name, client.hostname)  # Give your bucket a unique id.
    event_type = "currentwindow"  # Used to annotate what kind of data the events in a given bucket will contain.

    # Use the retry queue functionality offered by aw-client.
    # This makes sure that events don't get lost in case the server becomes unavailable.
    # Also makes all calls where `queued` is set to True run asynchronously/non-blocking.
    use_retry_queue = True

    client.create_bucket(bucket_id, event_type, queued=use_retry_queue)

    poll_time = 5  # Send an event every 5 seconds
    while True:
        window = get_current_window()

        window_event = Event(timestamp=datetime.now(timezone.utc), data={
            "app": window["appname"],
            "title": window["title"] if not args.exclude_title else "excluded"
        })

        # Set pulsetime to 1 second more than the poll_time
        # since the loop will take slightly longer than poll_time.
        # Note the `queued=use_retry_queue` that is talked about above.
        client.heartbeat(bucket_id, window_event,
                         pulsetime=poll_time + 1.0, queued=use_retry_queue)

        sleep(poll_time)



