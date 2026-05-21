from __future__ import annotations

import argparse
import logging
import platform
import time

from aw_client import ActivityWatchClient
from aw_core.log import setup_logging
from requests.exceptions import ConnectionError

from aw_watcher_cursor_busy.core import (
    DEFAULT_MIN_DURATION,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PULSETIME,
    WATCHER_NAME,
    CursorBusyWatcher,
)
from aw_watcher_cursor_busy.win32 import get_busy_sample

logger = logging.getLogger(WATCHER_NAME)


def connect_with_retries(testing: bool, retries: int = 30, delay: float = 2.0) -> ActivityWatchClient:
    client = ActivityWatchClient(client_name=WATCHER_NAME, testing=testing)
    for attempt in range(1, retries + 1):
        try:
            client.get_buckets()
            return client
        except ConnectionError:
            logger.info("ActivityWatch server is not ready yet (%s/%s)", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("Could not connect to ActivityWatch server")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--pulsetime", type=float, default=DEFAULT_PULSETIME)
    parser.add_argument("--min-duration", type=float, default=DEFAULT_MIN_DURATION)
    parser.add_argument("--testing", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if platform.system() != "Windows":
        raise RuntimeError("aw-watcher-cursor-busy only supports Windows")

    setup_logging(WATCHER_NAME, testing=args.testing, verbose=args.verbose, log_stderr=True, log_file=True)
    client = connect_with_retries(args.testing)

    with client:
        watcher = CursorBusyWatcher(client, pulsetime=args.pulsetime, min_duration=args.min_duration)
        watcher.ensure_bucket()
        logger.info("Watching busy cursor in bucket %s", watcher.bucket_id)

        while True:
            try:
                watcher.process_sample(get_busy_sample())
            except Exception:
                logger.exception("Failed to process cursor sample")
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()

