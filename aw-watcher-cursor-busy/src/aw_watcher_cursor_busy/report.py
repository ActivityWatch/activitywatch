from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, time, timezone

from aw_client import ActivityWatchClient
from requests.exceptions import HTTPError

from aw_watcher_cursor_busy.core import WATCHER_NAME


def _local_today_start() -> datetime:
    now = datetime.now().astimezone()
    return datetime.combine(now.date(), time.min, tzinfo=now.tzinfo).astimezone(timezone.utc)


def format_seconds(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", action="store_true", help="Report only events from today.")
    parser.add_argument("--testing", action="store_true")
    args = parser.parse_args()

    client = ActivityWatchClient(client_name=f"{WATCHER_NAME}-report", testing=args.testing)
    bucket_id = f"{WATCHER_NAME}_{client.client_hostname}"
    if bucket_id not in client.get_buckets():
        print("No cursor busy events found.")
        return

    start = _local_today_start() if args.today else None
    try:
        events = client.get_events(bucket_id, start=start)
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            print("No cursor busy events found.")
            return
        raise

    totals: dict[str, float] = defaultdict(float)
    for event in events:
        app = event.data.get("app") or "unknown"
        totals[str(app)] += event.duration.total_seconds()

    if not totals:
        print("No cursor busy events found.")
        return

    width = max(len(app) for app in totals)
    for app, seconds in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        print(f"{app:<{width}}  {format_seconds(seconds)}")


if __name__ == "__main__":
    main()
