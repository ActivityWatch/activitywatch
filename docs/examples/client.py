from time import sleep
from datetime import datetime, timezone, timedelta

from aw_core.models import Event
from aw_client import ActivityWatchClient

now = datetime.now(tz=timezone.utc)

# We'll run with testing=True so we don't mess up any production instance.
# Make sure you've started aw-server with the `--testing` flag as well.
client = ActivityWatchClient("test-client", testing=True)
bucket_id = "test-bucket"
example_data = {"label": "example"}
example_event = Event(timestamp=now, data=example_data)

# Asynchronous example
with client:
    # This context manager starts the queue dispatcher thread and stops it when done, always use it when setting queued=True.

    # First we need a bucket to send events/heartbeats to.
    client.create_bucket(bucket_id, event_type="test", queued=True)

    # Now we can send some heartbeats.
    # The duration between them will be less than pulsetime, so they will get merged.
    client.heartbeat(bucket_id, example_event, pulsetime=10, queued=True)

    example_event.timestamp += timedelta(seconds=5)
    client.heartbeat(bucket_id, example_event, pulsetime=10, queued=True)

    # Give the dispatcher thread some time to complete sending the events
    sleep(1)

# Synchronous example
example_event.timestamp += timedelta(minutes=1)
inserted_event = client.insert_event(bucket_id, example_event)

# The event returned from insert_event has been assigned an id
assert inserted_event.id is not None

events = client.get_events(bucket_id=bucket_id, limit=10)
print(events)

# Now lets clean up after us.
client.delete_bucket(bucket_id)
